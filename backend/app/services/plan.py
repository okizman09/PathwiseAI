"""Workflow generation and step planning service (Catalog v3, Slice C5).

Decomposes the ProductBrief into 1 to 6 taxonomy jobs, enforces budget and commercial rules,
scores tools in code, and synthesizes paste-ready prompts tailored to each tool's prompt style.
"""
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.tool import Tool
from app.models.tool_gap import ToolGap
from app.models.workflow import Workflow as DBWorkflow
from app.models.workflow import WorkflowStep as DBWorkflowStep
from app.schemas.brief import ProductBrief
from app.schemas.workflow import (
    CostSummary,
    ToolShortCard,
    WorkflowResponse,
    WorkflowStep,
)
from app.services import catalog as catalog_service
from app.services.llm import generate_structured
from app.services.planner.checks import MODEL_ID_RE as _MODEL_ID_RE
from app.services.planner.scoring import shortlist_and_score
from app.taxonomy import get_jobs_for_domain, get_valid_jobs, is_valid_job


# ---------------------------------------------------------------------------
# Pydantic Schemas for LLM Structured Outputs
# ---------------------------------------------------------------------------
class JobPlanningItem(BaseModel):
    step_number: int = Field(ge=1, le=6)
    job: str = Field(description="Actionable single job slug e.g. 'write_code' or 'generate_image'")
    job_tags: list[str] = Field(
        default_factory=list,
        description="Optional category keywords or job tags e.g. ['code'], ['image']",
    )
    input_types: list[str] = Field(
        default_factory=list,
        description="Types of inputs required for this job e.g. ['text'], ['image']",
    )
    output_types: list[str] = Field(
        default_factory=list,
        description="Types of outputs produced e.g. ['code'], ['website'], ['image'], ['text']",
    )
    output_expected: str = Field(
        description="Tangible asset or deliverable produced by this step"
    )


class LLMJobsPlan(BaseModel):
    jobs: list[JobPlanningItem] = Field(
        min_length=1,
        max_length=6,
        description="1 to 6 essential steps required to fulfill the product brief. Never pad or force steps.",
    )


class LLMStepSynthesis(BaseModel):
    step_number: int = Field(ge=1, le=6)
    job: str = Field(description="The specific job title")
    why_step: str = Field(description="Why this step is needed for this workflow (max 2 sentences)")
    primary_tool_id: int = Field(
        description="The ID of the primary tool chosen strictly from the shortlisted candidate tools. 0 if no candidates provided."
    )
    alternative_tool_ids: list[int] = Field(
        default_factory=list,
        description="IDs of 1-2 alternative tools chosen strictly from the shortlisted candidate tools for this step",
    )
    why_tool: str = Field(
        default="",
        description="Brief explanation of why this primary tool was chosen (max 2 sentences). Empty if no candidates."
    )
    learn_note: str = Field(
        default="",
        description="One core concept or watch-out for the user using this tool (max 2 sentences). Empty if no candidates."
    )
    prompt: str = Field(
        default="",
        description="A complete, paste-ready prompt written strictly following the primary tool's prompt_style. Empty if no candidates."
    )
    technique: str = Field(
        default="",
        description="One-line summary of the prompting technique used. Empty if no candidates."
    )
    output_expected: str = Field(
        description="Tangible asset or output produced by this step"
    )


class LLMWorkflowSynthesis(BaseModel):
    title: str = Field(description="A concise title for this workflow based on the brief")
    steps: list[LLMStepSynthesis] = Field(
        min_length=1,
        max_length=6,
        description="The detailed synthesized steps with tool assignments and paste-ready prompts",
    )


def _candidate_summary(t: Tool) -> dict:
    """Shortlist entry for the synthesis prompt; Meta tools carry ecosystem/kind/model_id."""
    summary = {
        "id": t.id,
        "name": t.name,
        "category": t.category,
        "jobs": t.jobs,
        "prompt_style": t.prompt_style,
    }
    if t.ecosystem:
        summary["ecosystem"] = t.ecosystem
        summary["kind"] = t.kind
        summary["model_id"] = t.model_id
    return summary


def _strip_unknown_model_ids(text: str, known_ids: set[str]) -> tuple[str, list[str]]:
    """Strip muse-/sam- tokens not present in the catalog.

    Returns the cleaned text plus the removed IDs (for step warnings).
    Trailing punctuation is preserved; known IDs are left untouched.
    """
    removed: list[str] = []

    def _replace(match: re.Match) -> str:
        raw = match.group(0)
        token = raw.rstrip(".,;:!?\"')]")
        if token in known_ids:
            return raw
        removed.append(token)
        return raw[len(token):]

    return _MODEL_ID_RE.sub(_replace, text or ""), removed


def compute_free_tier_note(tool: Tool | ToolShortCard | None, brief: ProductBrief) -> tuple[str, list[str]]:
    """Compute per-step free-tier guidance note and warnings from stored tool data."""
    warnings: list[str] = []
    if not tool:
        note = (
            "No free option exists yet in the catalog."
            if brief.budget_preference == "free_only"
            else "No verified tool option exists yet in the catalog."
        )
        return (note, [])

    parts: list[str] = []
    has_free = (
        getattr(tool, "has_free_tier", None) is True
        or getattr(tool, "pricing_model", "") in ("free", "open_source")
        or getattr(tool, "pricing", "") in ("free", "open_source")
    )

    is_pricing_unknown = (
        getattr(tool, "pricing_model", "") in ("unknown", None, "")
        and getattr(tool, "has_free_tier", None) is None
    )

    if is_pricing_unknown:
        parts.append("Pricing not checked yet")
    elif has_free:
        if getattr(tool, "free_tier_summary", None):
            parts.append(tool.free_tier_summary)
        else:
            parts.append("Free plan available.")

        if getattr(tool, "credit_card_required", None) is False:
            parts.append("No credit card required.")

        if getattr(tool, "commercial_use_on_free", None) is True:
            parts.append("Commercial use permitted.")
        elif getattr(tool, "commercial_use_on_free", None) is False:
            parts.append("Personal use only.")
            if brief.needs_commercial_use == "yes":
                warnings.append(
                    f"{tool.name}'s free tier is for personal use only. Commercial use requires a paid license."
                )
    else:
        starting_price = getattr(tool, "starting_price_monthly_usd", None)
        price_str = f"starts at ${starting_price:.0f}/mo" if starting_price else "paid tier only"
        parts.append(f"Paid tool ({price_str}). No free tier.")

    # Freshness warning (>60 days old)
    checked_at = getattr(tool, "pricing_checked_at", None)
    if checked_at:
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=60)
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        if checked_at < cutoff:
            warnings.append(f"{tool.name} pricing may have changed (last verified over 60 days ago).")

    # Inherit any planner warnings
    if hasattr(tool, "_planner_warnings") and tool._planner_warnings:
        for w in tool._planner_warnings:
            if w not in warnings:
                warnings.append(w)
    elif hasattr(tool, "warnings") and tool.warnings:
        for w in tool.warnings:
            if w not in warnings:
                warnings.append(w)

    return (" · ".join(parts), warnings)


def compute_cost_summary(steps: list[WorkflowStep], brief: ProductBrief) -> CostSummary:
    """Compute overall workflow cost summary in code from stored tool fields (Catalog v3, Slice C5)."""
    notes: list[str] = []
    total_estimated_usd = 0.0
    has_paid_tool = False
    all_free = True

    for step in steps:
        tool = step.primary_tool
        if not tool:
            continue

        has_free = (
            tool.has_free_tier is True
            or tool.pricing_model in ("free", "open_source")
            or tool.pricing in ("free", "open_source")
        )

        is_unknown = (
            getattr(tool, "pricing_model", "") in ("unknown", None, "")
            and getattr(tool, "has_free_tier", None) is None
        )

        if is_unknown:
            notes.append(f"{tool.name}: pricing not checked yet.")
        elif not has_free:
            has_paid_tool = True
            all_free = False
            price = tool.starting_price_monthly_usd or 0.0
            total_estimated_usd += price
            notes.append(
                f"{tool.name} requires a paid subscription (~${price:.0f}/mo)."
                if price > 0
                else f"{tool.name} has no free tier."
            )
        elif brief.needs_commercial_use == "yes" and tool.commercial_use_on_free is False:
            notes.append(
                f"{tool.name} free tier is for personal use only. Commercial use requires a paid license."
            )
            has_paid_tool = True
            all_free = False

    mode: Literal["free", "may_cost"] = "free" if (all_free and not has_paid_tool) else "may_cost"

    if mode == "free":
        notes.append("All recommended tools have a free tier or are open source ($0 baseline cost).")
    elif total_estimated_usd > 0:
        notes.append(f"Estimated baseline cost for required paid tools is approximately ${total_estimated_usd:.0f}/mo.")

    return CostSummary(
        mode=mode,
        estimated_monthly_usd=total_estimated_usd if total_estimated_usd > 0 else 0.0,
        notes=notes,
    )


def build_short_card(tool: Tool, why_chosen: str = "") -> ToolShortCard:
    """Map DB Tool model to ToolShortCard."""
    prompt_style_dict = tool.prompt_style or {}
    tool_warnings = list(getattr(tool, "_planner_warnings", []))
    return ToolShortCard(
        id=tool.id,
        name=tool.name,
        go_path=f"/go/{tool.id}",
        category=tool.category or "",
        domain=tool.domain,
        ecosystem=tool.ecosystem,
        kind=tool.kind,
        model_id=tool.model_id,
        api_snippet=tool.api_snippet,
        jobs=tool.jobs or [],
        input_types=tool.input_types or [],
        output_types=tool.output_types or [],
        pricing=tool.pricing or "freemium",
        pricing_model=tool.pricing_model or "freemium",
        has_free_tier=tool.has_free_tier,
        free_tier_summary=tool.free_tier_summary,
        free_tier_limits=tool.free_tier_limits,
        starting_price_monthly_usd=tool.starting_price_monthly_usd,
        commercial_use_on_free=tool.commercial_use_on_free,
        credit_card_required=tool.credit_card_required,
        best_for=tool.best_for or "",
        prompt_style=prompt_style_dict,
        why_chosen=why_chosen,
        logo_url=tool.logo_url,
        is_pick=tool.is_pick or False,
        warnings=tool_warnings,
    )


async def generate_workflow_plan(
    db: Session,
    user: Profile,
    brief: ProductBrief,
) -> WorkflowResponse:
    """Generate a 1-6 step variable workflow by decomposing into jobs, filtering tools in code, and synthesizing prompts."""
    # 1. Fetch verified tools from DB
    verified_tools = catalog_service.list_public_tools(db=db)
    if not verified_tools:
        raise ValueError(
            "No verified tools found in catalog. Please add and verify tools in the admin dashboard before generating workflows."
        )

    # Determine allowed taxonomy job slugs based on brief's detected domains
    detected_domains = brief.detected_domains or []
    allowed_job_slugs: list[str] = []
    for d in detected_domains:
        allowed_job_slugs.extend(get_jobs_for_domain(d))
    if not allowed_job_slugs:
        allowed_job_slugs = get_valid_jobs()

    # 2. Phase 1: Ask Meta ONLY for the essential job list (1-6 jobs) from taxonomy
    jobs_system_instruction = (
        "You are Pathwise AI's Master Workflow Architect.\n"
        "Your task is to analyze the user's locked Product Brief and identify the exact sequence of 1 to 6 essential jobs needed.\n\n"
        f"CRITICAL TAXONOMY CONSTRAINT:\n"
        f"You MUST choose the job for each step strictly from this allowed taxonomy job slug list: {', '.join(allowed_job_slugs)}.\n\n"
        "STRICT CONSTRAINTS:\n"
        "1. VARIABLE STEPS (1-6): Plan between 1 and 6 steps. 1 step is completely valid if a single job satisfies the brief. NEVER pad.\n"
        "2. NO UNREQUESTED SCOPE: Do not include SEO, analytics, custom domains, marketing campaigns, or extra features unless explicitly requested in the brief.\n"
        "3. EACH STEP IS A DISTINCT JOB: Produce a clear tangible deliverable per step."
    )

    jobs_prompt = (
        f"Product Brief:\n{brief.model_dump_json(indent=2)}\n\n"
        "Decompose this product brief into the minimal, exact sequence of 1 to 6 taxonomy jobs required."
    )

    jobs_plan = await generate_structured(
        system=jobs_system_instruction,
        user=jobs_prompt,
        schema=LLMJobsPlan,
        temperature=0.2,
    )

    # Sanitize and ensure job slugs match taxonomy
    for item in jobs_plan.jobs:
        slug_candidate = item.job.strip().lower().replace(" ", "_").replace("-", "_")
        if is_valid_job(slug_candidate):
            item.job = slug_candidate
        elif is_valid_job(item.job.strip().lower()):
            item.job = item.job.strip().lower()

    # 3. Phase 2: Filter tools in code for each planned job
    job_candidates_map = []
    prev_outputs: list[str] = []

    for job_item in jobs_plan.jobs:
        top_candidates = shortlist_and_score(
            tools=verified_tools,
            job_item=job_item,
            prev_output_types=prev_outputs,
            brief=brief,
        )

        job_candidates_map.append({
            "job_item": job_item,
            "candidates": top_candidates,
            "candidate_summaries": [_candidate_summary(t) for t in top_candidates],
        })
        prev_outputs = job_item.output_types

    # 4. Phase 3: Send the shortlisted tools to Meta to select primary + alts and generate tool-specific prompts
    synthesis_system_instruction = (
        "You are Pathwise AI's Master Prompt Engineer.\n"
        "Your mission is to assign verified tools from the provided shortlists to each step and craft paste-ready prompts.\n\n"
        "STRICT CONSTRAINTS:\n"
        "1. SHORTLIST ONLY: For each step, select `primary_tool_id` and `alternative_tool_ids` ONLY from that specific step's shortlisted candidates. If empty, use 0.\n"
        "2. TOOL-SPECIFIC PROMPTS: Write each prompt strictly tailored to the chosen tool's `prompt_style` (technique, structure, rules).\n"
        "3. EXPLANATIONS: Write short 1-2 sentence why_step, why_tool, and learn_note.\n"
        "4. HANDOFF CONTINUITY: If Step 2 follows Step 1, ensure the prompt explicitly takes the output of Step 1.\n"
        "5. DO NOT PAD OR DROP: Return exactly the steps provided in the input list, even if candidates are empty.\n"
        "6. MODEL IDS: Use only model IDs that appear in the tool context. Never invent a model ID.\n"
        "7. META MODEL STEPS: For a Meta model step, write the prompt to be sent to that model, with the expected output format."
    )

    steps_input_payload = []
    for idx, item in enumerate(job_candidates_map, start=1):
        job_item = item["job_item"]
        steps_input_payload.append({
            "step_number": idx,
            "job": job_item.job,
            "output_expected": job_item.output_expected,
            "shortlisted_candidate_tools": item["candidate_summaries"],
        })

    synthesis_prompt = (
        f"Product Brief:\n{brief.model_dump_json(indent=2)}\n\n"
        f"Workflow Steps with Shortlisted Tools:\n{json.dumps(steps_input_payload, indent=2)}\n\n"
        "Assign the best primary tool and alternatives from each step's shortlist and write paste-ready prompts. Create a concise workflow title."
    )

    workflow_synthesis = await generate_structured(
        system=synthesis_system_instruction,
        user=synthesis_prompt,
        schema=LLMWorkflowSynthesis,
        temperature=0.2,
    )

    # T6 post-check: strip invented Meta model IDs from synthesized step text.
    known_model_ids = {
        row[0]
        for row in db.query(Tool.model_id).filter(Tool.model_id.isnot(None)).all()
    }
    invented_warnings: list[list[str]] = []
    for step_syn in workflow_synthesis.steps:
        stripped: list[str] = []
        for field in ("prompt", "why_step", "why_tool", "learn_note", "technique"):
            cleaned, removed = _strip_unknown_model_ids(getattr(step_syn, field) or "", known_model_ids)
            setattr(step_syn, field, cleaned)
            stripped.extend(removed)
        invented_warnings.append(
            [f"Removed unrecognized model reference(s): {', '.join(sorted(set(stripped)))}"]
            if stripped
            else []
        )

    # 5. Hydrate final workflow steps and save to DB
    db_wf = DBWorkflow(
        user_id=user.id,
        title=workflow_synthesis.title,
        brief=brief.model_dump(),
    )
    db.add(db_wf)
    db.flush()

    final_steps: list[WorkflowStep] = []

    for idx, step_syn in enumerate(workflow_synthesis.steps, start=1):
        item_map = job_candidates_map[idx - 1] if idx - 1 < len(job_candidates_map) else None
        candidate_list = item_map["candidates"] if item_map else []
        candidates_by_id = {t.id: t for t in candidate_list}

        if not candidate_list:
            # Tool gap
            db_gap = ToolGap(
                workflow_id=db_wf.id,
                job=step_syn.job,
                job_tags=item_map["job_item"].job_tags if item_map else [],
            )
            db.add(db_gap)

            gap_note = (
                "No free option exists yet in the catalog."
                if brief.budget_preference == "free_only"
                else "No verified tool yet. Come back later."
            )

            step_schema = WorkflowStep(
                step_id=f"step-{idx}",
                step_number=idx,
                kind="no_tool",
                job=step_syn.job,
                why_step=step_syn.why_step,
                primary_tool=None,
                alternatives=[],
                prompt=None,
                technique=None,
                output_expected=step_syn.output_expected,
                why_tool=None,
                learn_note=None,
                handoff_note="No verified tool yet. Come back later.",
                free_tier_note=gap_note,
                warnings=["No verified tool option available for this job yet."] + invented_warnings[idx - 1],
            )
            final_steps.append(step_schema)

            db_step = DBWorkflowStep(
                workflow_id=db_wf.id,
                position=idx,
                kind="no_tool",
                job=step_syn.job,
                why_step=step_syn.why_step,
                output_expected=step_syn.output_expected,
                handoff_note="No verified tool yet. Come back later.",
                alternative_tool_ids=[],
                job_tags=item_map["job_item"].job_tags if item_map else [],
                input_types=item_map["job_item"].input_types if item_map else [],
                output_types=item_map["job_item"].output_types if item_map else [],
            )
            db.add(db_step)
            continue

        # Resolve primary tool strictly from candidates, fallback to top scored
        primary_tool = candidates_by_id.get(step_syn.primary_tool_id) or candidate_list[0]
        free_note, step_warnings = compute_free_tier_note(primary_tool, brief)

        # Resolve alternatives strictly from candidates
        alternatives: list[ToolShortCard] = []
        for alt_id in step_syn.alternative_tool_ids:
            if alt_id in candidates_by_id and alt_id != primary_tool.id:
                alternatives.append(build_short_card(candidates_by_id[alt_id]))

        primary_short_card = build_short_card(primary_tool)

        step_schema = WorkflowStep(
            step_id=f"step-{idx}",
            step_number=idx,
            kind="tool",
            job=step_syn.job,
            why_step=step_syn.why_step,
            primary_tool=primary_short_card,
            alternatives=alternatives,
            prompt=step_syn.prompt,
            technique=step_syn.technique,
            output_expected=step_syn.output_expected,
            why_tool=step_syn.why_tool,
            learn_note=step_syn.learn_note,
            free_tier_note=free_note,
            warnings=step_warnings + invented_warnings[idx - 1],
        )
        final_steps.append(step_schema)

        db_step = DBWorkflowStep(
            workflow_id=db_wf.id,
            position=idx,
            kind="tool",
            job=step_syn.job,
            why_step=step_syn.why_step,
            primary_tool_id=primary_tool.id,
            alternative_tool_ids=[alt.id for alt in alternatives],
            prompt=step_syn.prompt,
            technique=step_syn.technique,
            output_expected=step_syn.output_expected,
            why_tool=step_syn.why_tool,
            learn_note=step_syn.learn_note,
            job_tags=item_map["job_item"].job_tags if item_map else [],
            input_types=item_map["job_item"].input_types if item_map else [],
            output_types=item_map["job_item"].output_types if item_map else [],
        )
        db.add(db_step)

    db.commit()
    db.refresh(db_wf)

    # 6. Compute Cost Summary in code from stored tool fields
    cost_summary = compute_cost_summary(final_steps, brief)

    return WorkflowResponse(
        id=db_wf.id,
        title=db_wf.title,
        brief=ProductBrief.model_validate(db_wf.brief),
        cost_summary=cost_summary,
        steps=final_steps,
        created_at=db_wf.created_at.isoformat(),
    )

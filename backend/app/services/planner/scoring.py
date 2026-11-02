"""Tool shortlisting and ranking for workflow planning (Catalog v3, Slice C5).

Rules enforced:
1. Exact job-slug matching between tool.jobs and job_item target slugs.
   Text-overlap matching is strictly disallowed.
2. Hard rule (free_only): If brief.budget_preference == "free_only",
   exclude tools where has_free_tier is not True.
3. Hard rule (commercial with free_only): If needs_commercial_use == "yes" and free_only,
   exclude tools where commercial_use_on_free is False. Otherwise, show a warning only.
4. Ranking signals:
   - Pathwise picks flag (is_pick): +10 points
   - Skill level fit: +5 points
   - Stack mentions in constraints matching tool.best_for: +2 points per keyword
   - Pipeline input/output matching: +4 to +5 points
   - Constraint conflict penalty from not_for: -15 points per conflict
   - Stale pricing penalty (>60 days since pricing_checked_at): -3 points and warning attached
"""
import re
from datetime import UTC, datetime, timedelta

from app.models.tool import Tool
from app.schemas.brief import ProductBrief

STOP_WORDS = {
    "and", "the", "for", "with", "that", "this", "from", "have", "been",
    "only", "also", "into", "some", "more", "user", "users", "tool", "tools",
    "must", "should", "want", "like", "need", "needs", "very", "much"
}


def extract_meaningful_tokens(text: str) -> set[str]:
    """Lower-case, drop stop words and tokens shorter than 4 characters."""
    if not text:
        return set()
    raw_tokens = re.findall(r"[a-z0-9_-]+", text.lower())
    return {t for t in raw_tokens if len(t) >= 4 and t not in STOP_WORDS}


def is_tool_free(tool: Tool) -> bool:
    """Check if tool provides a valid free plan or open source license."""
    return (
        getattr(tool, "has_free_tier", None) is True
        or getattr(tool, "pricing_model", "") in ("free", "open_source")
        or getattr(tool, "pricing", "") in ("free", "open_source")
    )


def score_single_tool(
    tool: Tool,
    job_item,  # JobPlanningItem duck-typed
    prev_output_types: list[str],
    brief: ProductBrief,
    now: datetime | None = None,
) -> tuple[float, list[str]] | None:
    """Evaluate and score a single tool against job requirements and brief.

    Returns (score, warnings) or None if tool is filtered out.
    """
    if now is None:
        now = datetime.now(UTC)
    stale_cutoff = now - timedelta(days=60)

    # Candidate must be verified and link not dead
    if getattr(tool, "status", "") != "verified" or getattr(tool, "link_status", "") == "dead":
        return None

    # Hard skip if the brief's explicit skill_level is forbidden in not_for
    if tool.not_for and brief.skill_level and brief.skill_level != "unknown":
        if brief.skill_level.lower() in tool.not_for.lower():
            return None

    # Target job slugs from job_item
    target_job_slugs: set[str] = set()
    if hasattr(job_item, "job_tags") and job_item.job_tags:
        target_job_slugs.update(s.strip().lower() for s in job_item.job_tags if s)
    if hasattr(job_item, "job") and job_item.job:
        raw_job = job_item.job.strip().lower()
        target_job_slugs.add(raw_job)
        target_job_slugs.add(raw_job.replace(" ", "_"))

    # EXACT job-slug matching (no fuzzy or text-overlap)
    tool_job_slugs = {str(j).strip().lower() for j in (tool.jobs or [])}
    matching_slugs = target_job_slugs & tool_job_slugs
    if not matching_slugs:
        return None

    tool_warnings: list[str] = []

    # Check pricing status
    has_free = is_tool_free(tool)
    is_pricing_unknown = (
        getattr(tool, "pricing_model", "") in ("unknown", None, "")
        and getattr(tool, "has_free_tier", None) is None
    )

    # Hard Rule: budget_preference == "free_only"
    if brief.budget_preference == "free_only":
        if not has_free and not is_pricing_unknown:
            # Strictly exclude paid-only tools
            return None

    # Ranking adjustment & warning for unknown pricing
    if is_pricing_unknown:
        tool_warnings.append("Pricing not checked yet")

    # Hard Rule / Warning: needs_commercial_use == "yes"
    comm_free = getattr(tool, "commercial_use_on_free", None)
    if brief.needs_commercial_use == "yes":
        if brief.budget_preference == "free_only":
            if comm_free is False:
                # Hard exclude: free tier is strictly personal, user requested free_only for commercial
                return None
        elif comm_free is False:
            # Not free_only: allow tool but flag warning
            tool_warnings.append(
                f"{tool.name}'s free plan is for personal use only. Commercial use requires a paid license."
            )

    score = len(matching_slugs) * 10.0

    # Slight lower rank for tools with unknown pricing
    if is_pricing_unknown:
        score -= 2.0

    # Pathwise Pick bonus (C5 ranking rule)
    if getattr(tool, "is_pick", False):
        score += 10.0

    # Skill level fit
    tool_skill = (getattr(tool, "skill_level", "") or "all").lower()
    brief_skill = (brief.skill_level or "unknown").lower()
    if brief_skill != "unknown":
        if tool_skill == brief_skill or tool_skill == "all":
            score += 5.0
        elif tool.best_for and brief_skill in tool.best_for.lower():
            score += 3.0

    # Stack mentions in brief constraints
    if brief.constraints and tool.best_for:
        stack_words = set()
        for c in brief.constraints:
            stack_words.update(re.findall(r"\w+", c.lower()))
        bf_words = set(re.findall(r"\w+", tool.best_for.lower()))
        score += len(bf_words & stack_words) * 2.0

    # Output type matching (bonus points)
    tool_outputs = [o.lower() for o in (tool.output_types or [])]
    for ot in (getattr(job_item, "output_types", []) or []):
        if ot.lower() in tool_outputs:
            score += 4.0

    # Pipeline input matching previous step output
    if prev_output_types:
        tool_inputs = [i.lower() for i in (tool.input_types or [])]
        for pot in prev_output_types:
            if pot.lower() in tool_inputs:
                score += 5.0

    # Constraint conflict penalty from not_for
    if tool.not_for and brief.constraints:
        nf_tokens = extract_meaningful_tokens(tool.not_for)
        constraint_text = " ".join(brief.constraints).lower()
        constraint_tokens = extract_meaningful_tokens(constraint_text)
        conflict_tokens = nf_tokens & constraint_tokens
        if conflict_tokens:
            score -= len(conflict_tokens) * 15.0

    # Stale pricing penalty (>60 days old) and warning
    checked_at = getattr(tool, "pricing_checked_at", None)
    if checked_at:
        # Ensure timezone-aware
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        if checked_at < stale_cutoff:
            score -= 3.0
            tool_warnings.append(
                f"{tool.name} pricing may have changed (last verified over 60 days ago)."
            )

    return (score, tool_warnings)


def shortlist_and_score(
    tools: list[Tool],
    job_item,  # JobPlanningItem duck-typed
    prev_output_types: list[str],
    brief: ProductBrief,
) -> list[Tool]:
    """Shortlist verified, reachable tools whose jobs EXACTLY match target job slug(s).

    Enforces budget constraints (free_only, commercial_use_on_free) as hard filters.
    Ranks remaining candidates and attaches warnings.
    """
    scored: list[tuple[float, Tool]] = []
    now = datetime.now(UTC)

    for tool in tools:
        res = score_single_tool(tool, job_item, prev_output_types, brief, now=now)
        if res is None:
            continue
        score, warnings = res
        tool._planner_warnings = warnings
        scored.append((score, tool))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:4]]

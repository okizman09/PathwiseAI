import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.tool import Tool
from app.schemas.card_import import CardImport
from app.schemas.tool import (
    AdminToolCreateRequest,
    PromptStyleSchema,
    ToolCreate,
    ToolStatus,
    ToolUpdate,
)
from app.services.importer import CardImporterService
from app.services.research.extractor import extract_tool_data
from app.services.research.fetcher import (
    check_url_reachable_safe,
    fetch_page_safe,
    resolve_and_check,
)
from app.taxonomy.loader import is_valid_domain, is_valid_job

logger = logging.getLogger(__name__)


async def do_research(tool_name: str, tool_url: str, docs_urls: list[str]) -> dict[str, Any]:
    sources = []
    page_texts = []

    for docs_url in docs_urls[:4]:
        try:
            # We enforce same registrable domain or something similar, but for now we just fetch
            res = await fetch_page_safe(docs_url)
            sources.append({
                "url": docs_url,
                "fetched_at": datetime.now(UTC).isoformat(),
                "ok": res["ok"],
                "error": res.get("error")
            })
            if res["ok"]:
                page_texts.append(res["text"])
        except Exception as e:
            sources.append({
                "url": docs_url,
                "fetched_at": datetime.now(UTC).isoformat(),
                "ok": False,
                "error": str(e)
            })

    if not page_texts:
        return {"extracted": None, "sources": sources}

    extracted = await extract_tool_data(page_texts, tool_name, tool_url)
    return {"extracted": extracted, "sources": sources}

def validate_affiliate_url(url: str):
    if not url:
        return
    if len(url) > 1024:
        raise ValueError("Affiliate URL too long")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Affiliate URL must be HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Affiliate URL cannot contain credentials")
    if parsed.hostname:
        try:
            resolve_and_check(parsed.hostname)
        except ValueError as e:
            raise ValueError(f"Affiliate URL invalid: {e}")

async def create_admin_tool_from_request(
    db: Session,
    req: AdminToolCreateRequest,
) -> Tool:
    """Create tool card. If docs_urls is provided, fetch pages and use Meta to extract draft card."""
    validate_affiliate_url(req.affiliate_url)

    docs_urls = req.docs_urls or []

    if docs_urls:
        research_res = await do_research(req.name, req.url, docs_urls)
        extracted = research_res["extracted"]
        sources = research_res["sources"]

        if extracted:
            tool_in = ToolCreate(
                name=req.name,
                url=req.url,
                affiliate_url=req.affiliate_url,
                docs_url=docs_urls[0] if docs_urls else None,
                category=extracted.category or req.category or "general",
                jobs=extracted.jobs or req.jobs or [],
                input_types=extracted.input_types or req.input_types or ["text"],
                output_types=extracted.output_types or req.output_types or ["text"],
                pricing=extracted.pricing or req.pricing or "freemium",
                best_for=extracted.best_for or req.best_for or "",
                not_for=extracted.not_for or req.not_for or "",
                prompt_style=PromptStyleSchema(
                    technique=extracted.prompt_style.technique,
                    format=extracted.prompt_style.format,
                    rules=extracted.prompt_style.rules,
                    example=extracted.prompt_style.example
                ),
                status=ToolStatus.DRAFT,
            )
            tool = create_tool(db, tool_in)
            tool.sources = sources
            tool.research_notes = extracted.research_notes
            db.commit()
            db.refresh(tool)
            return tool
        else:
            # Failed to extract, fallback
            pass

    # Fallback to manual creation
    tool_in = ToolCreate(
        name=req.name,
        url=req.url,
        affiliate_url=req.affiliate_url,
        docs_url=docs_urls[0] if docs_urls else None,
        category=req.category or "general",
        jobs=req.jobs or [],
        input_types=req.input_types or ["text"],
        output_types=req.output_types or ["text"],
        pricing=req.pricing or "freemium",
        best_for=req.best_for or "",
        not_for=req.not_for or "",
        prompt_style=req.prompt_style or PromptStyleSchema(),
        status=ToolStatus.DRAFT,
    )

    tool = create_tool(db=db, tool_in=tool_in)
    if docs_urls:
        tool.sources = research_res["sources"] if 'research_res' in locals() else []
    db.commit()
    db.refresh(tool)
    return tool

def create_tool(db: Session, tool_in: ToolCreate) -> Tool:
    tool_data = tool_in.model_dump()
    if isinstance(tool_data.get("prompt_style"), dict):
        tool_data["prompt_style"] = tool_in.prompt_style.model_dump()

    status_val = tool_data.get("status", ToolStatus.DRAFT)
    if hasattr(status_val, "value"):
        status_val = status_val.value
    tool_data["status"] = str(status_val)

    if tool_data["status"] == ToolStatus.VERIFIED.value and not tool_data.get("verified_at"):
        tool_data["verified_at"] = datetime.now(UTC)

    if not tool_data.get("category") and tool_data.get("domain"):
        tool_data["category"] = tool_data["domain"]

    tool = Tool(**{k: v for k, v in tool_data.items() if hasattr(Tool, k)})
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool

def get_tool_by_id(db: Session, tool_id: int) -> Tool | None:
    return db.query(Tool).filter(Tool.id == tool_id).first()

def get_public_tool(db: Session, tool_id: int) -> Tool | None:
    return db.query(Tool).filter(
        Tool.id == tool_id,
        Tool.status == ToolStatus.VERIFIED.value,
        Tool.link_status != "dead",
    ).first()

def list_admin_tools(
    db: Session,
    status: ToolStatus | None = None,
    category: str | None = None,
    domain: str | None = None,
) -> list[Tool]:
    query = db.query(Tool)
    if status:
        query = query.filter(Tool.status == status.value)
    if domain:
        query = query.filter((Tool.domain == domain) | (Tool.category == domain))
    elif category:
        query = query.filter((Tool.category == category) | (Tool.domain == category))
    return query.order_by(Tool.id.desc()).all()

def get_tool_feedback_counts(db: Session) -> dict[int, int]:
    """Return map of tool_id -> feedback count."""
    from sqlalchemy import func

    from app.models.step_feedback import StepFeedback

    try:
        rows = (
            db.query(StepFeedback.tool_id, func.count(StepFeedback.id))
            .filter(StepFeedback.tool_id.isnot(None))
            .group_by(StepFeedback.tool_id)
            .all()
        )
        return {tool_id: count for tool_id, count in rows if tool_id is not None}
    except Exception as e:
        logger.warning("Could not query step_feedback table: %s", e)
        return {}


def get_tool_metrics(db: Session):
    """Aggregate per-tool usage signals and success rates for admin metrics."""
    from app.models.step_feedback import StepFeedback
    from app.schemas.tool import ToolMetricResponse

    tools = db.query(Tool).all()
    feedbacks = db.query(StepFeedback).all()

    by_tool: dict[int, list[StepFeedback]] = {}
    for fb in feedbacks:
        if fb.tool_id:
            by_tool.setdefault(fb.tool_id, []).append(fb)

    metrics: list[ToolMetricResponse] = []
    for t in tools:
        fbs = by_tool.get(t.id, [])
        total = len(fbs)
        worked = sum(1 for f in fbs if f.result == "worked")
        partly = sum(1 for f in fbs if f.result == "partly")
        didnt = sum(1 for f in fbs if f.result == "didnt")
        unique_workflows = len(set(f.workflow_id for f in fbs))

        rate = round(((worked + 0.5 * partly) / total) * 100, 1) if total > 0 else None
        metrics.append(
            ToolMetricResponse(
                tool_id=t.id,
                name=t.name,
                domain=t.domain,
                total_feedbacks=total,
                worked_count=worked,
                partly_count=partly,
                didnt_count=didnt,
                success_rate_percent=rate,
                used_in_workflows=unique_workflows,
            )
        )
    metrics.sort(key=lambda m: (m.total_feedbacks, m.success_rate_percent or 0), reverse=True)
    return metrics


def list_public_tools(
    db: Session,
    category: str | None = None,
    domain: str | None = None,
) -> list[Tool]:
    """List only verified tools for public catalog, sorted picks first then name."""
    query = db.query(Tool).filter(
        Tool.status == ToolStatus.VERIFIED.value,
        Tool.link_status != "dead",
    )
    if domain:
        query = query.filter((Tool.domain == domain) | (Tool.category == domain))
    elif category:
        query = query.filter((Tool.category == category) | (Tool.domain == category))
    tools = query.order_by(Tool.is_pick.desc(), Tool.name.asc()).all()
    counts = get_tool_feedback_counts(db)
    for tool in tools:
        cnt = counts.get(tool.id, 0)
        tool.used_in_workflows_count = cnt if cnt >= 10 else None
    return tools


def validate_tool_for_verification(tool: Tool, pending_data: dict[str, Any] | None = None) -> list[str]:
    """Check all 8 conditions required to verify a tool card under Catalog v3 (Slice C3).

    Returns a list of human-readable errors explaining which rules are failing.
    If the list is empty, the tool satisfies all verification rules.
    """
    data = {
        "domain": getattr(tool, "domain", None),
        "jobs": getattr(tool, "jobs", []) or [],
        "pricing_model": getattr(tool, "pricing_model", None),
        "has_free_tier": getattr(tool, "has_free_tier", None),
        "free_tier_summary": getattr(tool, "free_tier_summary", None),
        "starting_price_monthly_usd": getattr(tool, "starting_price_monthly_usd", None),
        "credit_card_required": getattr(tool, "credit_card_required", None),
        "watermark_on_free": getattr(tool, "watermark_on_free", None),
        "commercial_use_on_free": getattr(tool, "commercial_use_on_free", None),
        "tagline": getattr(tool, "tagline", None),
        "pros": getattr(tool, "pros", []) or [],
        "cons": getattr(tool, "cons", []) or [],
        "link_status": getattr(tool, "link_status", "unknown"),
        "review_flags": getattr(tool, "review_flags", []) or [],
        "evidence": getattr(tool, "evidence", {}) or {},
    }
    if pending_data:
        data.update(pending_data)

    errors: list[str] = []

    # 1. domain set and valid
    domain = data.get("domain")
    if not domain or not is_valid_domain(domain):
        errors.append("domain must be set to a valid taxonomy domain")

    # 2. at least one valid job slug
    jobs = data.get("jobs") or []
    valid_jobs = [j for j in jobs if is_valid_job(j)]
    if not valid_jobs:
        errors.append("at least one valid taxonomy job slug is required")

    # 3. pricing_model set (not unknown)
    pricing_model = data.get("pricing_model")
    if not pricing_model or pricing_model == "unknown":
        errors.append("pricing_model must be set and not unknown")

    # 4. free-tier fields set when pricing_model is free/freemium/free_trial
    if pricing_model in ("free", "freemium", "free_trial"):
        if data.get("has_free_tier") is None:
            errors.append("has_free_tier must be set for free, freemium, or free_trial pricing")
        elif data.get("has_free_tier") is True and not (data.get("free_tier_summary") and str(data.get("free_tier_summary")).strip()):
            errors.append("free_tier_summary must be non-empty when has_free_tier is true")

    # 5. every pricing field has evidence
    evidence = data.get("evidence") or {}
    if not isinstance(evidence, dict):
        errors.append("evidence must be a dictionary")
    else:
        pricing_fields_to_check = ["pricing_model"]
        for f in ("has_free_tier", "starting_price_monthly_usd", "credit_card_required", "watermark_on_free", "commercial_use_on_free"):
            if data.get(f) is not None:
                pricing_fields_to_check.append(f)

        for pf in pricing_fields_to_check:
            ev = evidence.get(pf)
            if not ev or not isinstance(ev, dict) or not ev.get("source_url") or not ev.get("quote"):
                errors.append(f"pricing field '{pf}' requires evidence quote and source link")

    # 6. explanation fields within limits
    tagline = data.get("tagline")
    if not tagline or len(str(tagline)) > 90:
        errors.append("tagline must be non-empty and max 90 characters")
    ft_sum = data.get("free_tier_summary")
    if ft_sum and len(str(ft_sum)) > 140:
        errors.append("free_tier_summary must be max 140 characters")
    pros = data.get("pros") or []
    cons = data.get("cons") or []
    if len(pros) != 3:
        errors.append(f"pros must contain exactly 3 items (found {len(pros)})")
    if len(cons) != 3:
        errors.append(f"cons must contain exactly 3 items (found {len(cons)})")

    # 7. link reachable
    if data.get("link_status") != "ok":
        errors.append("primary link must be reachable (link_status must be 'ok')")

    # 8. all review flags marked reviewed
    rflags = data.get("review_flags") or []
    if len(rflags) > 0:
        errors.append(f"all review flags must be resolved/marked reviewed ({len(rflags)} remaining)")

    return errors


async def check_url_reachable(url: str) -> bool:
    try:
        return await check_url_reachable_safe(url)
    except Exception:
        return False


async def update_tool(
    db: Session,
    db_tool: Tool,
    tool_update: ToolUpdate,
    verified_by_user: str | None = None,
) -> Tool:
    update_data = tool_update.model_dump(exclude_unset=True)

    if "affiliate_url" in update_data:
        validate_affiliate_url(update_data["affiliate_url"])

    new_status_val = None
    if "status" in update_data and update_data["status"] is not None:
        new_status_val = update_data["status"].value if hasattr(update_data["status"], "value") else str(update_data["status"])

    # Rule 3: Pick toggle (is_pick) per tool, allowed only for verified tools
    if "is_pick" in update_data and update_data["is_pick"]:
        target_status = new_status_val or db_tool.status
        if target_status != ToolStatus.VERIFIED.value:
            raise ValueError("Pathwise Pick (is_pick) is allowed only for verified tools.")

    now = datetime.now(UTC)

    # Verification checks
    if new_status_val == ToolStatus.VERIFIED.value:
        url_to_check = update_data.get("url", db_tool.url)
        parsed = urlparse(url_to_check)
        if parsed.scheme != "https":
            raise ValueError("Cannot verify: URL must be HTTPS")

        # Live reachability check if link is not already 'ok' or if url was actually changed
        url_changed = "url" in update_data and update_data["url"] != db_tool.url
        if db_tool.link_status != "ok" or url_changed:
            reachable = await check_url_reachable(url_to_check)
            if reachable:
                db_tool.link_status = "ok"
                db_tool.link_checked_at = now
                update_data["link_status"] = "ok"
            else:
                db_tool.link_status = "dead"
                update_data["link_status"] = "dead"

        # Check all C3 verification rules
        unmet_rules = validate_tool_for_verification(db_tool, pending_data=update_data)
        if unmet_rules:
            raise ValueError(f"Cannot verify tool. Unmet rules: {'; '.join(unmet_rules)}")

        db_tool.verified_at = now
        db_tool.verified_by = verified_by_user or update_data.get("verified_by") or "admin"
        db_tool.pricing_checked_at = now

    for field, value in update_data.items():
        if field == "prompt_style" and value is not None:
            db_tool.prompt_style = (
                value.model_dump()
                if hasattr(value, "model_dump")
                else value
            )
        elif field == "status" and value is not None:
            db_tool.status = new_status_val
        else:
            setattr(db_tool, field, value)

    db_tool.updated_at = now
    db.commit()
    db.refresh(db_tool)
    return db_tool


def delete_tool(db: Session, db_tool: Tool) -> None:
    db.delete(db_tool)
    db.commit()


def list_stale_tools(db: Session) -> list[Tool]:
    """Retrieve verified tools whose pricing_checked_at is older than 30 days or not set."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    return (
        db.query(Tool)
        .filter(
            Tool.status == ToolStatus.VERIFIED.value,
            (Tool.pricing_checked_at.is_(None)) | (Tool.pricing_checked_at < cutoff),
        )
        .order_by(Tool.pricing_checked_at.asc())
        .all()
    )


async def diff_tool_card(
    db: Session,
    tool_id: int,
    fresh_card_data: dict[str, Any],
    apply: bool = False,
) -> dict[str, Any]:
    """Compare an existing tool with fresh card JSON, returning a field-by-field diff."""
    tool = get_tool_by_id(db, tool_id)
    if not tool:
        raise ValueError(f"Tool {tool_id} not found")

    card = CardImport(**fresh_card_data)

    diff_fields = [
        "name", "domain", "pricing_model", "has_free_tier",
        "free_tier_summary", "free_tier_limits", "starting_price_monthly_usd",
        "pricing_notes", "credit_card_required", "watermark_on_free",
        "commercial_use_on_free", "platforms", "skill_level", "jobs",
        "tagline", "summary", "how_it_helps", "pros", "cons",
        "best_for", "not_for", "official_url", "pricing_url",
    ]

    card_dict = card.model_dump()
    diff: dict[str, dict[str, Any]] = {}

    for field in diff_fields:
        if field == "official_url":
            curr_val = tool.url
            new_val = card.official_url
        else:
            curr_val = getattr(tool, field, None)
            new_val = card_dict.get(field)

        if curr_val != new_val:
            diff[field] = {
                "current": curr_val,
                "new": new_val,
            }

    if apply:
        res = await CardImporterService.import_single_card(db, card, target_tool_id=tool_id)
        return {
            "tool_id": tool_id,
            "diff": diff,
            "applied": True,
            "import_result": res.model_dump(),
        }

    return {
        "tool_id": tool_id,
        "diff": diff,
        "applied": False,
    }


async def recheck_tool(db: Session, tool_id: int) -> dict:
    tool = get_tool_by_id(db, tool_id)
    if not tool:
        raise ValueError(f"Tool {tool_id} not found")

    docs_urls = []
    if tool.docs_url:
        docs_urls.append(tool.docs_url)

    if not docs_urls:
        raise ValueError("Tool has no docs_url to research")

    research_res = await do_research(tool.name, tool.url, docs_urls)
    extracted = research_res["extracted"]

    if not extracted:
        sources = research_res.get("sources", [])
        failed_sources = [
            f"{s.get('url')} ({s.get('error', 'unknown error')})"
            for s in sources
            if not s.get("ok")
        ]
        if failed_sources:
            raise ValueError(f"Could not fetch docs: {', '.join(failed_sources)}")
        raise ValueError("Failed to extract tool data from docs")

    # Build a dict of the new fields to compare
    return {
        "category": extracted.category,
        "jobs": extracted.jobs,
        "input_types": extracted.input_types,
        "output_types": extracted.output_types,
        "pricing": extracted.pricing,
        "best_for": extracted.best_for,
        "not_for": extracted.not_for,
        "prompt_style": extracted.prompt_style.model_dump(),
        "research_notes": extracted.research_notes,
        "sources": research_res["sources"]
    }


async def check_all_links(db: Session) -> dict:
    tools = db.query(Tool).filter(Tool.status == ToolStatus.VERIFIED.value).all()
    results = {"checked": 0, "dead": 0, "hidden": 0, "ok": 0}

    now = datetime.now(UTC)
    for tool in tools:
        reachable = await check_url_reachable(tool.url)
        tool.link_checked_at = now
        results["checked"] += 1
        if not reachable:
            tool.link_status = "dead"
            tool.status = ToolStatus.HIDDEN.value
            results["dead"] += 1
            results["hidden"] += 1
        else:
            tool.link_status = "ok"
            results["ok"] += 1

    db.commit()
    return results


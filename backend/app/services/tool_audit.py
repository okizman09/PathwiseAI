"""Per-tool completeness audit (batch follow-up 4).

Pure checks over tool attributes so the CLI (``scripts/audit_tools.py``)
and tests share one definition of "missing". Issue codes are stable
strings; human labels live in ``ISSUE_LABELS``.
"""

from typing import Any

ISSUE_ORDER = [
    "hidden",
    "not-verified",
    "no-tagline",
    "no-summary",
    "no-best-for",
    "no-prompt-example",
    "no-jobs",
    "pricing-unknown",
    "free-tier-unchecked",
    "no-free-tier-summary",
    "pricing-unchecked",
    "no-logo",
    "no-og-image",
    "meta-no-kind",
    "meta-no-snippet",
    "meta-no-model-id",
    "link-dead",
    "link-unchecked",
    "pick-incomplete",
]

ISSUE_LABELS = {
    "hidden": "status is hidden (skipped from display, content checks skipped)",
    "not-verified": "status is not verified",
    "no-tagline": "no tagline (cards fall back to summary/best_for)",
    "no-summary": "no summary for the detail dialog",
    "no-best-for": "no best_for text",
    "no-prompt-example": "prompt_style has no example prompt",
    "no-jobs": "no taxonomy jobs assigned",
    "pricing-unknown": "pricing_model is unknown",
    "free-tier-unchecked": "has_free_tier was never checked",
    "no-free-tier-summary": "has a free tier but no free_tier_summary",
    "pricing-unchecked": "pricing_checked_at is empty",
    "no-logo": "no logo_url (directory shows an initial instead)",
    "no-og-image": "no og_image_url preview",
    "meta-no-kind": "Meta card without kind",
    "meta-no-snippet": "Meta card without api_snippet",
    "meta-no-model-id": "runnable Meta model without model_id",
    "link-dead": "link_status is dead",
    "link-unchecked": "link_status was never checked",
    "pick-incomplete": "Pathwise pick missing logo or blurb",
}


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def audit_tool(tool: Any) -> list[str]:
    """Return sorted issue codes for one tool (duck-typed attributes)."""
    if getattr(tool, "status", None) == "hidden":
        return ["hidden"]

    issues: list[str] = []
    if getattr(tool, "status", None) != "verified":
        issues.append("not-verified")

    tagline = getattr(tool, "tagline", None)
    summary = getattr(tool, "summary", None)
    if _blank(tagline):
        issues.append("no-tagline")
    if _blank(summary):
        issues.append("no-summary")
    if _blank(getattr(tool, "best_for", None)):
        issues.append("no-best-for")

    prompt_style = getattr(tool, "prompt_style", None) or {}
    example = prompt_style.get("example") if isinstance(prompt_style, dict) else None
    if _blank(example):
        issues.append("no-prompt-example")

    if not getattr(tool, "jobs", None):
        issues.append("no-jobs")

    pricing_model = getattr(tool, "pricing_model", None)
    if _blank(pricing_model) or str(pricing_model).strip().lower() == "unknown":
        issues.append("pricing-unknown")
    has_free_tier = getattr(tool, "has_free_tier", None)
    if has_free_tier is None:
        issues.append("free-tier-unchecked")
    elif has_free_tier and _blank(getattr(tool, "free_tier_summary", None)):
        issues.append("no-free-tier-summary")
    if getattr(tool, "pricing_checked_at", None) is None:
        issues.append("pricing-unchecked")

    if _blank(getattr(tool, "logo_url", None)):
        issues.append("no-logo")
    if _blank(getattr(tool, "og_image_url", None)):
        issues.append("no-og-image")

    if getattr(tool, "ecosystem", None) == "meta":
        if _blank(getattr(tool, "kind", None)):
            issues.append("meta-no-kind")
        if _blank(getattr(tool, "api_snippet", None)):
            issues.append("meta-no-snippet")
        if getattr(tool, "kind", None) == "runnable" and _blank(getattr(tool, "model_id", None)):
            issues.append("meta-no-model-id")

    link_status = getattr(tool, "link_status", None)
    if link_status == "dead":
        issues.append("link-dead")
    elif link_status in (None, "", "unknown"):
        issues.append("link-unchecked")

    if getattr(tool, "is_pick", False) and (
        _blank(getattr(tool, "logo_url", None)) or (_blank(tagline) and _blank(summary))
    ):
        issues.append("pick-incomplete")

    order = {code: index for index, code in enumerate(ISSUE_ORDER)}
    return sorted(issues, key=lambda code: order[code])

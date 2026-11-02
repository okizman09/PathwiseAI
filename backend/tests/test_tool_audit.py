"""Tests for the catalog audit checks (batch follow-up 4). Pure unit tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.services.tool_audit import ISSUE_LABELS, ISSUE_ORDER, audit_tool


def make_tool(**overrides):
    base = {
        "status": "verified",
        "tagline": "A great tool",
        "summary": "Longer summary.",
        "best_for": "Builders",
        "prompt_style": {"technique": "direct", "example": "Do the thing"},
        "jobs": ["build_web_app"],
        "pricing_model": "freemium",
        "has_free_tier": True,
        "free_tier_summary": "Free for 3 projects",
        "pricing_checked_at": datetime.now(UTC),
        "logo_url": "https://cdn.local/logos/tool.png",
        "og_image_url": "https://cdn.local/previews/tool.png",
        "logo_source": "page",
        "ecosystem": None,
        "kind": None,
        "model_id": None,
        "api_snippet": None,
        "link_status": "ok",
        "is_pick": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_complete_tool_has_no_issues():
    assert audit_tool(make_tool()) == []


def test_empty_tool_flags_core_issues():
    tool = make_tool(
        status="draft",
        tagline=None,
        summary="",
        best_for="",
        prompt_style={},
        jobs=[],
        pricing_model="unknown",
        has_free_tier=None,
        free_tier_summary=None,
        pricing_checked_at=None,
        logo_url=None,
        og_image_url=None,
        link_status="unknown",
    )
    issues = audit_tool(tool)
    for code in [
        "not-verified",
        "no-tagline",
        "no-summary",
        "no-best-for",
        "no-prompt-example",
        "no-jobs",
        "pricing-unknown",
        "free-tier-unchecked",
        "pricing-unchecked",
        "no-logo",
        "no-og-image",
        "link-unchecked",
    ]:
        assert code in issues
    assert issues == sorted(issues, key=ISSUE_ORDER.index)


def test_hidden_tool_skips_content_checks():
    tool = make_tool(status="hidden", tagline=None, logo_url=None)
    assert audit_tool(tool) == ["hidden"]


def test_free_tier_without_summary_flagged_only_when_free():
    assert "no-free-tier-summary" in audit_tool(make_tool(free_tier_summary=None))
    assert "no-free-tier-summary" not in audit_tool(
        make_tool(has_free_tier=False, free_tier_summary=None)
    )


def test_meta_runnable_requires_kind_snippet_model_id():
    tool = make_tool(ecosystem="meta", kind="runnable", model_id=None, api_snippet=None)
    issues = audit_tool(tool)
    assert "meta-no-snippet" in issues
    assert "meta-no-model-id" in issues
    assert "meta-no-kind" not in issues


def test_meta_platform_needs_no_model_id():
    tool = make_tool(
        ecosystem="meta", kind="platform", model_id=None, api_snippet="client = ..."
    )
    issues = audit_tool(tool)
    assert "meta-no-model-id" not in issues
    assert "meta-no-snippet" not in issues


def test_dead_link_flagged():
    assert "link-dead" in audit_tool(make_tool(link_status="dead"))


def test_pick_without_logo_or_blurb_flagged():
    assert "pick-incomplete" in audit_tool(make_tool(is_pick=True, logo_url=None))
    assert "pick-incomplete" in audit_tool(
        make_tool(is_pick=True, tagline=None, summary=None)
    )
    assert "pick-incomplete" not in audit_tool(make_tool(is_pick=True))


def test_every_issue_has_a_label():
    assert set(ISSUE_ORDER) == set(ISSUE_LABELS)

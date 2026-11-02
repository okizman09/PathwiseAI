"""Tests for Catalog v3 Admin Review and Freshness (Slice C3).

Validates:
1. 8 verification conditions enforced before publishing.
2. Pathwise Pick (is_pick) toggle restricted only to verified tools.
3. GET /admin/tools/stale returns tools with pricing_checked_at > 30 days old.
4. POST /admin/jobs/check-links cron job hides dead links (link_status=dead, status=hidden)
   and requires X-Cron-Secret or admin credentials.
5. POST /admin/tools/{tool_id}/recheck returns field diff and applies updates preserving affiliate URLs.
6. Public response exposes verified_badge ("Verified <Mon YYYY>") and no "Tested" badge.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.tool import Tool
from app.schemas.tool import ToolPublicResponse, ToolStatus, ToolUpdate
from app.services.catalog import (
    diff_tool_card,
    list_stale_tools,
    update_tool,
    validate_tool_for_verification,
)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def make_seed_card_dict(**overrides) -> dict:
    base = {
        "name": "Cursor",
        "domain": "software",
        "official_url": "https://cursor.com",
        "pricing_url": "https://cursor.com/pricing",
        "pricing_model": "freemium",
        "has_free_tier": True,
        "free_tier_summary": "Free Hobby plan with limited Agent requests.",
        "free_tier_limits": "Hobby includes limited Agent requests.",
        "starting_price_monthly_usd": 20.0,
        "pricing_notes": "Pro is $20/month.",
        "credit_card_required": False,
        "watermark_on_free": None,
        "commercial_use_on_free": True,
        "platforms": ["desktop", "cli"],
        "skill_level": "all",
        "jobs": ["write_code", "debug_code"],
        "tagline": "AI code editor for codebase-wide edits and agentic coding.",
        "summary": "An intelligent editor fork of VS Code with AI deep integration.",
        "how_it_helps": "Helps developers generate and review full-stack code quickly.",
        "pros": ["Deep codebase indexing", "Fast composer agent", "Familiar VS Code UX"],
        "cons": ["Paid tier required for heavy usage", "Proprietary server logic", "Can be resource-heavy"],
        "prompt_style": {
            "technique": "Direct spec",
            "format": "Markdown",
            "rules": ["Specify types", "Write tests"],
            "example": "Implement a helper.",
        },
        "input_types": ["code"],
        "output_types": ["code"],
        "best_for": "Developers wanting an AI editor.",
        "not_for": "Non-coders.",
        "evidence": {
            "pricing_model": {
                "source_url": "https://cursor.com/pricing",
                "quote": "Hobby plan is free forever",
            },
            "starting_price_monthly_usd": {
                "source_url": "https://cursor.com/pricing",
                "quote": "Pro plan starts at $20/month",
            },
        },
        "unknowns": [],
        "checked_on": "2026-10-09",
    }
    base.update(overrides)
    return base


def create_test_tool(db, name="Test Review Tool", status=ToolStatus.DRAFT.value, link_status="ok", **kwargs) -> Tool:
    now = datetime.now(UTC)
    tool_data = {
        "name": name,
        "domain": "software",
        "category": "software",
        "url": f"https://{name.lower().replace(' ', '')}.com",
        "status": status,
        "link_status": link_status,
        "pricing_model": "freemium",
        "has_free_tier": True,
        "free_tier_summary": "Generous free plan with basic capabilities.",
        "starting_price_monthly_usd": 20.0,
        "jobs": ["write_code", "debug_code"],
        "tagline": "A powerful development assistant.",
        "pros": ["Pro 1", "Pro 2", "Pro 3"],
        "cons": ["Con 1", "Con 2", "Con 3"],
        "evidence": {
            "pricing_model": {
                "source_url": f"https://{name.lower().replace(' ', '')}.com/pricing",
                "quote": "Free plan is available forever",
                "checked": True,
            },
            "has_free_tier": {
                "source_url": f"https://{name.lower().replace(' ', '')}.com/pricing",
                "quote": "Free tier with core features",
                "checked": True,
            },
            "starting_price_monthly_usd": {
                "source_url": f"https://{name.lower().replace(' ', '')}.com/pricing",
                "quote": "Pro starts at $20/month",
                "checked": True,
            },
        },
        "review_flags": [],
        "created_at": now,
        "updated_at": now,
    }
    tool_data.update(kwargs)
    tool = Tool(**tool_data)
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def test_validate_tool_for_verification_all_rules():
    """Verify that all 8 rules are checked by validate_tool_for_verification."""
    db = SessionLocal()
    try:
        tool = create_test_tool(db, name="Audit Candidate")

        # 1. Base candidate satisfies all 8 rules
        errors = validate_tool_for_verification(tool)
        assert errors == [], f"Expected 0 errors, got: {errors}"

        # Rule 1: Invalid domain
        errs = validate_tool_for_verification(tool, pending_data={"domain": "invalid_domain_name"})
        assert any("domain must be set" in e for e in errs)

        # Rule 2: Invalid job slug
        errs = validate_tool_for_verification(tool, pending_data={"jobs": ["non_existent_job_slug"]})
        assert any("valid taxonomy job slug" in e for e in errs)

        # Rule 3: Unknown pricing model
        errs = validate_tool_for_verification(tool, pending_data={"pricing_model": "unknown"})
        assert any("pricing_model must be set" in e for e in errs)

        # Rule 4: Free-tier fields missing
        errs = validate_tool_for_verification(tool, pending_data={"free_tier_summary": ""})
        assert any("free_tier_summary must be non-empty" in e for e in errs)

        # Rule 5: Missing pricing evidence
        errs = validate_tool_for_verification(tool, pending_data={"evidence": {}})
        assert any("requires evidence quote" in e for e in errs)

        # Rule 6: Explanations exceeding limits
        errs = validate_tool_for_verification(tool, pending_data={"tagline": "x" * 95})
        assert any("tagline must be non-empty and max 90" in e for e in errs)

        errs = validate_tool_for_verification(tool, pending_data={"pros": ["Only One Pro"]})
        assert any("pros must contain exactly 3 items" in e for e in errs)

        # Rule 7: Primary link dead
        errs = validate_tool_for_verification(tool, pending_data={"link_status": "dead"})
        assert any("primary link must be reachable" in e for e in errs)

        # Rule 8: Unresolved review flags
        errs = validate_tool_for_verification(tool, pending_data={"review_flags": ["quote mismatch: pricing"]})
        assert any("all review flags must be resolved" in e for e in errs)

    finally:
        db.close()


@pytest.mark.asyncio
async def test_update_tool_sets_verification_metadata_and_reaches_link():
    """Verifying a tool sets verified_at, verified_by, and pricing_checked_at."""
    db = SessionLocal()
    try:
        tool = create_test_tool(db, name="Verify Candidate", link_status="unknown")

        with patch("app.services.catalog.check_url_reachable_safe", new_callable=AsyncMock) as mock_reach:
            mock_reach.return_value = True

            update_data = ToolUpdate(
                status=ToolStatus.VERIFIED,
            )
            updated = await update_tool(
                db=db,
                db_tool=tool,
                tool_update=update_data,
                verified_by_user="admin@pathwise.ai",
            )

            assert updated.status == ToolStatus.VERIFIED.value
            assert updated.verified_at is not None
            assert updated.verified_by == "admin@pathwise.ai"
            assert updated.pricing_checked_at is not None
            assert updated.link_status == "ok"

    finally:
        db.close()


@pytest.mark.asyncio
async def test_is_pick_toggle_allowed_only_for_verified_tools():
    """Pick toggle (is_pick) is permitted only for verified tools."""
    db = SessionLocal()
    try:
        draft_tool = create_test_tool(db, name="Draft Tool", status=ToolStatus.DRAFT.value)

        # Attempting is_pick on draft must fail
        with pytest.raises(ValueError, match="allowed only for verified tools"):
            await update_tool(
                db=db,
                db_tool=draft_tool,
                tool_update=ToolUpdate(is_pick=True),
            )

        # Verified tool can have is_pick set
        verified_tool = create_test_tool(db, name="Verified Tool", status=ToolStatus.VERIFIED.value)
        updated = await update_tool(
            db=db,
            db_tool=verified_tool,
            tool_update=ToolUpdate(is_pick=True),
        )
        assert updated.is_pick is True

    finally:
        db.close()


def test_list_stale_tools_returns_tools_older_than_30_days():
    """GET /admin/tools/stale returns verified tools whose pricing_checked_at is > 30 days old."""
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        old_time = now - timedelta(days=35)
        fresh_time = now - timedelta(days=5)

        # 1. Stale verified tool
        stale_tool = create_test_tool(
            db,
            name="Stale Tool",
            status=ToolStatus.VERIFIED.value,
            pricing_checked_at=old_time,
        )

        # 2. Fresh verified tool
        fresh_tool = create_test_tool(
            db,
            name="Fresh Tool",
            status=ToolStatus.VERIFIED.value,
            pricing_checked_at=fresh_time,
        )

        # 3. Draft tool with old time (should NOT be returned)
        draft_tool = create_test_tool(
            db,
            name="Old Draft Tool",
            status=ToolStatus.DRAFT.value,
            pricing_checked_at=old_time,
        )

        stale_list = list_stale_tools(db)
        stale_ids = [t.id for t in stale_list]

        assert stale_tool.id in stale_ids
        assert fresh_tool.id not in stale_ids
        assert draft_tool.id not in stale_ids

    finally:
        db.close()


def test_cron_link_checker_endpoint_auth_and_hiding_dead_links():
    """POST /admin/jobs/check-links requires CRON_SECRET or admin and hides dead tools."""
    client = TestClient(app)
    db = SessionLocal()
    try:
        settings.CRON_SECRET = "test_cron_secret_123"

        # 1. Unauthenticated request without secret or token -> 401
        res = client.post("/api/v1/admin/jobs/check-links")
        assert res.status_code == 401

        # 2. Request with X-Cron-Secret header
        tool_live = create_test_tool(db, name="Live Tool", status=ToolStatus.VERIFIED.value, url="https://live.com")
        tool_dead = create_test_tool(db, name="Dead Tool", status=ToolStatus.VERIFIED.value, url="https://dead.com")

        async def mock_reachable(url: str):
            return "live.com" in url

        with patch("app.services.catalog.check_url_reachable", side_effect=mock_reachable):
            res = client.post(
                "/api/v1/admin/jobs/check-links",
                headers={"X-Cron-Secret": "test_cron_secret_123"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["dead"] >= 1
            assert data["hidden"] >= 1

            db.refresh(tool_live)
            db.refresh(tool_dead)

            assert tool_live.link_status == "ok"
            assert tool_live.status == ToolStatus.VERIFIED.value

            assert tool_dead.link_status == "dead"
            assert tool_dead.status == ToolStatus.HIDDEN.value

    finally:
        settings.CRON_SECRET = ""
        db.close()


@pytest.mark.asyncio
async def test_diff_tool_card_compares_and_preserves_affiliate():
    """diff_tool_card compares field-by-field diff and preserves affiliate_url on apply."""
    db = SessionLocal()
    try:
        tool = create_test_tool(
            db,
            name="Diff Target Tool",
            affiliate_url="https://difftarget.com?via=pathwise",
            starting_price_monthly_usd=20.0,
        )

        card_data = make_seed_card_dict(
            name="Diff Target Tool",
            official_url="https://difftarget.com",
            pricing_url="https://difftarget.com/pricing",
            starting_price_monthly_usd=30.0,
            tagline="Updated snappy tagline for diff testing.",
            evidence={
                "pricing_model": {
                    "source_url": "https://difftarget.com/pricing",
                    "quote": "Free plan is available forever",
                },
                "starting_price_monthly_usd": {
                    "source_url": "https://difftarget.com/pricing",
                    "quote": "Pro starts at $30/month",
                },
            },
        )

        # 1. Diff without apply
        diff_res = await diff_tool_card(db, tool.id, card_data, apply=False)
        assert diff_res["applied"] is False
        diff = diff_res["diff"]
        assert "starting_price_monthly_usd" in diff
        assert diff["starting_price_monthly_usd"]["current"] == 20.0
        assert diff["starting_price_monthly_usd"]["new"] == 30.0

        # Tool in DB remains unchanged
        db.refresh(tool)
        assert tool.starting_price_monthly_usd == 20.0

        # 2. Diff with apply=True
        apply_res = await diff_tool_card(db, tool.id, card_data, apply=True)
        assert apply_res["applied"] is True

        db.refresh(tool)
        assert tool.starting_price_monthly_usd == 30.0
        # Affiliate URL preserved
        assert tool.affiliate_url == "https://difftarget.com?via=pathwise"

    finally:
        db.close()


def test_public_tool_verified_badge():
    """ToolPublicResponse formats verified_badge as 'Verified <Mon YYYY>' and has no 'Tested' badge."""
    db = SessionLocal()
    try:
        verified_date = datetime(2026, 10, 15, tzinfo=UTC)
        tool = create_test_tool(
            db,
            name="Badge Tool",
            status=ToolStatus.VERIFIED.value,
            verified_at=verified_date,
        )

        pub = ToolPublicResponse.model_validate(tool)
        assert pub.verified_badge == "Verified Oct 2026"

        # Check that there is no tested_badge or tested attribute
        assert not hasattr(pub, "tested_badge")
        assert not hasattr(pub, "tested")

        # Unverified tool has verified_badge == None
        tool_unverified = create_test_tool(db, name="Unverified Tool", status=ToolStatus.DRAFT.value)
        pub_unverified = ToolPublicResponse.model_validate(tool_unverified)
        assert pub_unverified.verified_badge is None

    finally:
        db.close()

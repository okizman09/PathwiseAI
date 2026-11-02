"""Tests for Catalog v3 Card Importer (Slice C2).

Verifies Section 3 card shape validation, consistency rules, evidence verification,
quote matching tolerance, upsert preservation of affiliate URLs, status downgrades,
--expect seed comparison, and admin-only endpoint protection.
"""
import pytest
from pydantic import ValidationError

from app.db import SessionLocal
from app.models.profile import Profile
from app.models.tool import Tool
from app.schemas.card_import import CardImport
from app.services.importer import CardImporterService
from tests.test_auth import generate_token


def make_valid_card_dict(**overrides) -> dict:
    base = {
        "name": "Test Tool",
        "domain": "software",
        "official_url": "https://testtool.com",
        "pricing_url": "https://testtool.com/pricing",
        "pricing_model": "freemium",
        "has_free_tier": True,
        "free_tier_summary": "Generous free tier with 100 queries per day.",
        "free_tier_limits": "100 queries daily limit.",
        "starting_price_monthly_usd": 20.0,
        "pricing_notes": "Annual plan is discounted.",
        "credit_card_required": False,
        "watermark_on_free": None,
        "commercial_use_on_free": True,
        "platforms": ["web", "desktop"],
        "skill_level": "all",
        "jobs": ["write_code", "debug_code"],
        "tagline": "Fast automated code assistant.",
        "summary": "Test Tool is an AI assistant for editing and debugging code in real time.",
        "how_it_helps": "It accelerates refactoring and fixes bugs directly in your editor.",
        "pros": ["Generous free tier", "Fast response times", "Good IDE integration"],
        "cons": ["Limited off-line usage", "Occasional hallucination", "No mobile app"],
        "prompt_style": {
            "technique": "Direct prompt",
            "format": "Markdown",
            "rules": ["Be concise", "Include tests"],
            "example": "Refactor this function to be thread-safe.",
        },
        "input_types": ["code", "text"],
        "output_types": ["code"],
        "best_for": "Developers seeking fast codebase assistance.",
        "not_for": "Non-technical users.",
        "evidence": {
            "pricing_model": {
                "source_url": "https://testtool.com/pricing",
                "quote": "Free plan available forever",
            },
            "starting_price_monthly_usd": {
                "source_url": "https://testtool.com/pricing",
                "quote": "Pro starts at $20/month",
            },
        },
        "unknowns": ["watermark_on_free", "check: verify IDE plugin docs"],
        "checked_on": "2026-10-09",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_off_domain_evidence_removed():
    """Evidence source_url must be on an official domain; otherwise discard and set claimed field to null."""
    card_dict = make_valid_card_dict(
        evidence={
            "pricing_model": {
                "source_url": "https://randomblog.com/review",
                "quote": "it is freemium",
            },
            "starting_price_monthly_usd": {
                "source_url": "https://testtool.com/pricing",
                "quote": "Pro starts at $20/month",
            },
        }
    )
    card = CardImport(**card_dict)
    official_domains = CardImporterService.compute_official_domains(card)
    card_data, flags = CardImporterService.validate_and_flag_consistency(card)

    await CardImporterService.process_evidence(card_data, official_domains, flags)

    # Off-domain pricing_model evidence must be removed/null
    assert card_data["evidence"]["pricing_model"] is None
    # Claimed field must be reset
    assert card_data["pricing_model"] == "unknown"
    # Review flag must be recorded
    assert any("evidence off-domain: pricing_model" in f for f in flags)
    # Valid domain evidence is preserved
    assert card_data["evidence"]["starting_price_monthly_usd"] is not None


def test_unknown_job_slugs_dropped():
    """Drop job slugs not in taxonomy and flag the card; if none remain, mark needs_review_no_jobs."""
    card_dict = make_valid_card_dict(
        jobs=["write_code", "totally_fake_job", "another_unknown_job"]
    )
    card = CardImport(**card_dict)
    card_data, flags = CardImporterService.validate_and_flag_consistency(card)

    assert card_data["jobs"] == ["write_code"]
    assert any("unknown jobs dropped: totally_fake_job, another_unknown_job" in f for f in flags)
    assert "needs_review_no_jobs" not in flags

    # Test when no valid jobs remain
    card_dict_empty = make_valid_card_dict(jobs=["fake_job_only"])
    card_empty = CardImport(**card_dict_empty)
    card_data_empty, flags_empty = CardImporterService.validate_and_flag_consistency(card_empty)

    assert card_data_empty["jobs"] == []
    assert any("needs_review_no_jobs" in f for f in flags_empty)


@pytest.mark.asyncio
async def test_fake_quote_flagged(monkeypatch):
    """If evidence quote does not appear on the fetched page text, set checked=False and add review flag."""
    async def mock_fetch_page_safe(url):
        return {
            "url": url,
            "ok": True,
            "text": "Welcome to Test Tool. Pricing starts at $20 per month billed annually.",
            "error": None,
        }

    monkeypatch.setattr("app.services.importer.fetch_page_safe", mock_fetch_page_safe)

    card_dict = make_valid_card_dict(
        evidence={
            "pricing_model": {
                "source_url": "https://testtool.com/pricing",
                "quote": "This quote is completely fake and nonexistent",
            }
        }
    )
    card = CardImport(**card_dict)
    official_domains = CardImporterService.compute_official_domains(card)
    card_data, flags = CardImporterService.validate_and_flag_consistency(card)

    await CardImporterService.process_evidence(card_data, official_domains, flags)

    assert card_data["evidence"]["pricing_model"]["checked"] is False
    assert any("quote mismatch: pricing_model" in f for f in flags)


@pytest.mark.asyncio
async def test_quote_check_tolerant_of_markdown_and_table_symbols(monkeypatch):
    """Normalize text: tolerant of markdown symbols, pipes, checkmarks, bullets, newlines."""
    page_html_text = """
    | Plan | Monthly Price | Included |
    | --- | --- | --- |
    | Pro | **$20/mo** | • Unlimited agents ✓ |
    """

    async def mock_fetch_page_safe(url):
        return {
            "url": url,
            "ok": True,
            "text": page_html_text,
            "error": None,
        }

    monkeypatch.setattr("app.services.importer.fetch_page_safe", mock_fetch_page_safe)

    card_dict = make_valid_card_dict(
        evidence={
            "starting_price_monthly_usd": {
                "source_url": "https://testtool.com/pricing",
                "quote": "Pro $20/mo Unlimited agents",
            }
        }
    )
    card = CardImport(**card_dict)
    official_domains = CardImporterService.compute_official_domains(card)
    card_data, flags = CardImporterService.validate_and_flag_consistency(card)

    await CardImporterService.process_evidence(card_data, official_domains, flags)

    assert card_data["evidence"]["starting_price_monthly_usd"]["checked"] is True
    assert not any("quote mismatch: starting_price_monthly_usd" in f for f in flags)


def test_range_pricing_rejected():
    """Range or vague price claims ($10-50, typically $20, approx 15) must be rejected."""
    bad_cards = [
        make_valid_card_dict(starting_price_monthly_usd="$10-50"),
        make_valid_card_dict(starting_price_monthly_usd="typically $20"),
        make_valid_card_dict(starting_price_monthly_usd="approx 15"),
        make_valid_card_dict(starting_price_monthly_usd="10 - 20"),
    ]
    for bad in bad_cards:
        with pytest.raises(ValidationError) as exc_info:
            CardImport(**bad)
        assert "Range or vague price claim rejected" in str(exc_info.value)


def test_consistency_rules_flagged():
    """Consistency rule violations must be flagged as review flags."""
    # 1. free requires has_free_tier = True
    c1 = CardImport(**make_valid_card_dict(pricing_model="free", has_free_tier=False))
    _, flags1 = CardImporterService.validate_and_flag_consistency(c1)
    assert any("consistency: free requires has_free_tier=True" in f for f in flags1)

    # 2. paid cannot have has_free_tier = True
    c2 = CardImport(**make_valid_card_dict(pricing_model="paid", has_free_tier=True))
    _, flags2 = CardImporterService.validate_and_flag_consistency(c2)
    assert any("consistency: paid cannot have has_free_tier=True" in f for f in flags2)

    # 3. free_trial cannot have has_free_tier = True
    c3 = CardImport(**make_valid_card_dict(pricing_model="free_trial", has_free_tier=True))
    _, flags3 = CardImporterService.validate_and_flag_consistency(c3)
    assert any("consistency: free_trial cannot have has_free_tier=True" in f for f in flags3)

    # 4. has_free_tier requires non-empty free_tier_summary
    c4 = CardImport(**make_valid_card_dict(has_free_tier=True, free_tier_summary=""))
    _, flags4 = CardImporterService.validate_and_flag_consistency(c4)
    assert any("consistency: has_free_tier requires non-empty free_tier_summary" in f for f in flags4)

    # 5. missing starting price for freemium
    c5 = CardImport(**make_valid_card_dict(pricing_model="freemium", starting_price_monthly_usd=None))
    _, flags5 = CardImporterService.validate_and_flag_consistency(c5)
    assert any("missing_starting_price" in f for f in flags5)

    # 6. missing pricing_url
    c6 = CardImport(**make_valid_card_dict(pricing_url=None))
    _, flags6 = CardImporterService.validate_and_flag_consistency(c6)
    assert any("missing_pricing_url" in f for f in flags6)


@pytest.mark.asyncio
async def test_upsert_preserves_affiliate_url_and_flags_url_changed(client, monkeypatch):
    """Upsert preserves affiliate_url, and flags url_changed if URL changed."""
    async def mock_fetch(url):
        return {"url": url, "ok": True, "text": "Free plan available forever Pro starts at $20/month", "error": None}

    monkeypatch.setattr("app.services.importer.fetch_page_safe", mock_fetch)

    db = SessionLocal()
    try:
        # Pre-seed existing tool with affiliate_url
        existing = Tool(
            name="UpsertTool",
            url="https://old-site.com",
            affiliate_url="https://affiliate.example.com?via=pathwise",
            status="draft",
            domain="software",
            category="software",
            jobs=["write_code"],
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

        # Import card with matching name but new URL
        card_dict = make_valid_card_dict(
            name="UpsertTool",
            official_url="https://new-site.com",
        )
        card = CardImport(**card_dict)
        result = await CardImporterService.import_single_card(db, card)

        assert result.status == "updated"
        db.refresh(existing)
        # Affiliate URL preserved!
        assert existing.affiliate_url == "https://affiliate.example.com?via=pathwise"
        # URL updated
        assert existing.url == "https://new-site.com"
        # Flagged url_changed
        assert "url_changed" in result.flags

        # Clean up
        db.delete(existing)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_verified_tool_drops_to_researched_when_pricing_changes(client, monkeypatch):
    """If a verified tool's pricing fields change, set it back to researched and add review flag."""
    async def mock_fetch(url):
        return {"url": url, "ok": True, "text": "sample text", "error": None}

    monkeypatch.setattr("app.services.importer.fetch_page_safe", mock_fetch)

    db = SessionLocal()
    try:
        db.query(Tool).filter(Tool.name == "VerifiedPriceTool").delete()
        db.commit()
        verified_tool = Tool(
            name="VerifiedPriceTool",
            url="https://verifiedtool.com",
            status="verified",
            domain="software",
            category="software",
            jobs=["write_code"],
            pricing_model="free",
            has_free_tier=True,
            starting_price_monthly_usd=None,
            free_tier_summary="Free for all",
        )
        db.add(verified_tool)
        db.commit()
        db.refresh(verified_tool)

        # Import card with different pricing
        card_dict = make_valid_card_dict(
            name="VerifiedPriceTool",
            official_url="https://verifiedtool.com",
            pricing_model="freemium",
            starting_price_monthly_usd=29.0,
        )
        card = CardImport(**card_dict)
        result = await CardImporterService.import_single_card(db, card)

        assert result.status == "updated"
        db.refresh(verified_tool)
        # Status drops to researched
        assert verified_tool.status == "researched"
        assert "pricing_changed_reverify" in result.flags

        # Clean up
        db.delete(verified_tool)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_expect_lists_missing_tools(client, monkeypatch):
    """--expect compares imported names with seed CSV and lists tools missing from the JSON."""
    async def mock_fetch(url):
        return {"url": url, "ok": True, "text": "text", "error": None}

    monkeypatch.setattr("app.services.importer.fetch_page_safe", mock_fetch)

    db = SessionLocal()
    try:
        cards = [
            CardImport(**make_valid_card_dict(name="ToolOne", official_url="https://toolone.com")),
            CardImport(**make_valid_card_dict(name="ToolTwo", official_url="https://tooltwo.com")),
        ]
        expected_names = ["ToolOne", "ToolTwo", "ToolThreeMissing", "ToolFourMissing"]

        response = await CardImporterService.import_batch(
            db=db,
            cards=cards,
            expected_tool_names=expected_names,
        )

        assert response.created >= 2 or response.updated >= 2
        assert "ToolThreeMissing" in response.missing_tools
        assert "ToolFourMissing" in response.missing_tools
        assert "ToolOne" not in response.missing_tools
        assert "ToolTwo" not in response.missing_tools

        # Clean up
        t1 = db.query(Tool).filter(Tool.name == "ToolOne").first()
        t2 = db.query(Tool).filter(Tool.name == "ToolTwo").first()
        if t1:
            db.delete(t1)
        if t2:
            db.delete(t2)
        db.commit()
    finally:
        db.close()


def test_endpoint_is_admin_only(client, monkeypatch):
    """POST /admin/tools/import-cards and /api/v1/admin/tools/import-cards require admin auth."""
    async def mock_fetch(url):
        return {"url": url, "ok": True, "text": "mock", "error": None}

    monkeypatch.setattr("app.services.importer.fetch_page_safe", mock_fetch)

    payload = {
        "cards": [make_valid_card_dict(name="AdminEndpointTestTool")]
    }

    # 1. Unauthenticated -> 401
    res_no_auth = client.post("/api/v1/admin/tools/import-cards", json=payload)
    assert res_no_auth.status_code == 401

    # 2. Non-admin user -> 403
    user_token = generate_token(subject="regular_user_test", email="user@test.com")
    res_user = client.post(
        "/api/v1/admin/tools/import-cards",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_user.status_code == 403

    # 3. Admin user -> 200
    db = SessionLocal()
    try:
        admin_prof = db.query(Profile).filter(Profile.id == "admin_importer_test").first()
        if not admin_prof:
            admin_prof = Profile(id="admin_importer_test", email="admin_imp@test.com", role="admin")
            db.add(admin_prof)
        else:
            admin_prof.role = "admin"
        db.commit()

        admin_token = generate_token(subject="admin_importer_test", email="admin_imp@test.com")
        res_admin = client.post(
            "/api/v1/admin/tools/import-cards",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 200, res_admin.text
        data = res_admin.json()
        assert data["created"] == 1 or data["updated"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "AdminEndpointTestTool"

        # Also test root route /admin/tools/import-cards
        res_root = client.post(
            "/admin/tools/import-cards",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_root.status_code == 200, res_root.text

        # Clean up
        created = db.query(Tool).filter(Tool.name == "AdminEndpointTestTool").first()
        if created:
            db.delete(created)
            db.commit()
    finally:
        db.close()

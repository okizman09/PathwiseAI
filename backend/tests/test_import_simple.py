"""Tests for import_simple script and unknown pricing planner behavior.

Verifies:
1. import_simple creates new tools as status='verified' with verified_at set.
2. Upsert matches case-insensitively by name or URL.
3. Existing tools: only empty fields filled; pricing, explanations, evidence,
   affiliate_url, and manual logos are NEVER overwritten.
4. Jobs are validated against taxonomy: unknown slugs dropped and reported.
5. Static logos (/logos/*.svg) set logo_source='static'.
6. Planner: tools with unknown pricing are NOT excluded under free_only,
   receive a slight penalty, and include 'Pricing not checked yet' warning.
"""
import io

import pytest

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.brief import ProductBrief
from app.scripts.import_simple import import_simple_csv, normalize_domain, validate_domain
from app.services.plan import JobPlanningItem, compute_cost_summary, compute_free_tier_note
from app.services.planner.scoring import score_single_tool


@pytest.fixture
def db(client):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_normalize_domain():
    assert normalize_domain("https://www.example.com/path?foo=bar") == "example.com"
    assert normalize_domain("http://sub.domain.co.uk/") == "sub.domain.co.uk"
    assert normalize_domain("app.runwayml.com") == "app.runwayml.com"
    assert validate_domain("software") is True
    assert validate_domain("cursor.com") is True
    assert validate_domain("") is False


@pytest.mark.asyncio
async def test_import_simple_new_tool(db):
    csv_content = """name,domain,jobs,url,docs_url,logo_url,logo_source_url
Test Tool AI,software,write_code|debug_code,https://testtool-new.ai,https://docs.testtool-new.ai,/logos/test.svg,
"""
    csv_file = io.StringIO(csv_content)
    summary = await import_simple_csv(csv_file, db=db)

    assert summary["created"] == 1
    assert summary["updated"] == 0
    assert summary["dropped_jobs_count"] == 0

    tool = db.query(Tool).filter(Tool.name == "Test Tool AI").first()
    assert tool is not None
    assert tool.status == "verified"
    assert tool.verified_at is not None
    assert tool.domain == "software"
    assert set(tool.jobs) == {"write_code", "debug_code"}
    assert tool.docs_url == "https://docs.testtool-new.ai"
    assert tool.logo_url == "/logos/test.svg"
    assert tool.logo_source == "static"
    assert tool.pricing_model == "unknown"

    # Cleanup
    db.delete(tool)
    db.commit()


@pytest.mark.asyncio
async def test_import_simple_upsert_preserves_existing_data(db):
    # Pre-existing tool with pricing, manual logo, explanation, affiliate_url
    existing = Tool(
        name="Existing Upsert Tool",
        url="https://existing-upsert.com",
        domain="video",
        jobs=["edit_video"],
        status="draft",
        pricing_model="paid",
        starting_price_monthly_usd=29.0,
        has_free_tier=False,
        summary="Original summary - do not touch",
        tagline="Original tagline",
        how_it_helps="Original helper text",
        pros=["Great performance"],
        cons=["Steep price"],
        affiliate_url="https://partner.existing.com?aff=123",
        logo_url="https://custom.cdn/manual_logo.png",
        logo_source="manual",
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    # CSV with matching name (case-insensitive) and new docs_url & static logo
    csv_content = """name,domain,jobs,url,docs_url,logo_url,logo_source_url
EXISTING UPSERT TOOL,video,edit_video|generate_sound_effects,https://existing-upsert.com,https://docs.existing-upsert.com,/logos/new.svg,
"""
    csv_file = io.StringIO(csv_content)
    summary = await import_simple_csv(csv_file, db=db)

    assert summary["created"] == 0
    assert summary["updated"] == 1

    db.refresh(existing)
    # Status should now be verified
    assert existing.status == "verified"
    assert existing.verified_at is not None

    # Empty field docs_url should be filled
    assert existing.docs_url == "https://docs.existing-upsert.com"

    # Protected fields must NOT be overwritten
    assert existing.pricing_model == "paid"
    assert existing.starting_price_monthly_usd == 29.0
    assert existing.has_free_tier is False
    assert existing.summary == "Original summary - do not touch"
    assert existing.tagline == "Original tagline"
    assert existing.how_it_helps == "Original helper text"
    assert existing.pros == ["Great performance"]
    assert existing.cons == ["Steep price"]
    assert existing.affiliate_url == "https://partner.existing.com?aff=123"
    assert existing.logo_url == "https://custom.cdn/manual_logo.png"
    assert existing.logo_source == "manual"

    # Cleanup
    db.delete(existing)
    db.commit()


@pytest.mark.asyncio
async def test_import_simple_drops_invalid_jobs(db):
    csv_content = """name,domain,jobs,url,docs_url,logo_url,logo_source_url
Taxonomy Checker,software,write_code|invalid_job_slug_xyz|debug_code,https://taxcheck-xyz.io,,,
"""
    csv_file = io.StringIO(csv_content)
    summary = await import_simple_csv(csv_file, db=db)

    assert summary["created"] == 1
    assert summary["dropped_jobs_count"] == 1
    assert any("invalid_job_slug_xyz" in dj for dj in summary["dropped_jobs"])

    tool = db.query(Tool).filter(Tool.name == "Taxonomy Checker").first()
    assert tool is not None
    assert "write_code" in tool.jobs
    assert "debug_code" in tool.jobs
    assert "invalid_job_slug_xyz" not in tool.jobs

    # Cleanup
    db.delete(tool)
    db.commit()


def test_planner_unknown_pricing_not_excluded_under_free_only():
    brief = ProductBrief(
        what_being_made="Test App",
        purpose="Test Purpose",
        target_audience="Creators",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="all_levels",
        budget_preference="free_only",
        needs_commercial_use="no",
        detected_domains=["software"],
    )

    job_item = JobPlanningItem(
        step_number=1,
        job="Write code and scripts",
        job_tags=["write_code"],
        input_types=["text"],
        output_types=["code"],
        output_expected="Source code",
    )

    # Tool with unknown pricing
    tool_unknown = Tool(
        name="Mystery Code Tool",
        url="https://mysterycode.io",
        domain="software",
        jobs=["write_code"],
        status="verified",
        link_status="ok",
        pricing_model="unknown",
        has_free_tier=None,
    )

    score_result = score_single_tool(tool_unknown, job_item, [], brief)
    assert score_result is not None
    score, warnings = score_result
    assert "Pricing not checked yet" in warnings

    # Verified paid-only tool should be excluded (score is None)
    tool_paid = Tool(
        name="Expensive Code Tool",
        url="https://expensivecode.io",
        domain="software",
        jobs=["write_code"],
        status="verified",
        link_status="ok",
        pricing_model="paid",
        has_free_tier=False,
    )
    score_paid = score_single_tool(tool_paid, job_item, [], brief)
    assert score_paid is None


def test_planner_cost_summary_and_note_with_unknown_pricing():
    brief = ProductBrief(
        what_being_made="Test App",
        purpose="Test Purpose",
        target_audience="Creators",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="all_levels",
        budget_preference="free_only",
        needs_commercial_use="no",
        detected_domains=["software"],
    )

    tool_unknown = Tool(
        name="Beta Tool",
        url="https://beta.io",
        domain="software",
        jobs=["write_code"],
        status="verified",
        pricing_model="unknown",
        has_free_tier=None,
    )

    note, warnings = compute_free_tier_note(tool_unknown, brief)
    assert "Pricing not checked yet" in note

    from app.schemas.workflow import ToolShortCard, WorkflowStep

    t1 = ToolShortCard(
        id=1,
        name="Beta Tool",
        url="https://beta.io",
        go_path="/api/v1/tools/1/go",
        pricing_model="unknown",
        has_free_tier=None,
    )
    step = WorkflowStep(
        step_id="step-1",
        step_number=1,
        job="write_code",
        why_step="Essential code development",
        primary_tool=t1,
        output_expected="Source code",
    )
    cost_summary = compute_cost_summary([step], brief)
    assert cost_summary.mode == "free"
    assert any("pricing not checked yet" in n.lower() for n in cost_summary.notes)

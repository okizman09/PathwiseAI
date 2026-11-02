"""Tests for Taxonomy, Catalog v3 schema, and exact slug matching (Slice C1)."""
import pytest
from pydantic import ValidationError

from app.models.tool import Tool
from app.schemas.brief import ProductBrief
from app.schemas.tool import (
    PricingModel,
    SkillLevel,
    ToolCreate,
    ToolPublicResponse,
    ToolResponse,
    ToolStatus,
    ToolUpdate,
)
from app.services.plan import JobPlanningItem
from app.services.planner.scoring import shortlist_and_score
from app.taxonomy import (
    get_domain_for_job,
    get_domain_label,
    get_job_label,
    get_taxonomy,
    get_valid_domains,
    get_valid_jobs,
    validate_domain,
    validate_jobs,
)


def test_taxonomy_yaml_structure():
    """Verify that taxonomy.yaml defines exactly 9 domains and 55 unique job slugs with labels."""
    tax = get_taxonomy()
    assert "domains" in tax
    assert "taxonomy" in tax

    domains = get_valid_domains()
    expected_domains = [
        "software",
        "builders",
        "design",
        "video",
        "audio",
        "writing",
        "research",
        "deploy_backend",
        "freelance_ops",
    ]
    assert sorted(domains) == sorted(expected_domains)

    jobs = get_valid_jobs()
    assert len(jobs) == 55
    # Every job slug must be unique
    assert len(set(jobs)) == 55

    for d in expected_domains:
        label = get_domain_label(d)
        assert label and isinstance(label, str)

    for j in jobs:
        label = get_job_label(j)
        assert label and isinstance(label, str)
        domain = get_domain_for_job(j)
        assert domain in expected_domains


def test_get_taxonomy_endpoints(client):
    """GET /taxonomy and GET /api/v1/taxonomy return structured taxonomy."""
    for path in ["/taxonomy", "/api/v1/taxonomy"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert "domains" in data
        assert "jobs" in data
        assert "domain_labels" in data
        assert "job_labels" in data
        assert len(data["domains"]) == 9
        assert len(data["jobs"]) == 55
        assert data["domain_labels"]["software"] == "Software Development"
        assert data["job_labels"]["write_code"] == "Write code"


def test_pydantic_rejects_unknown_job_slugs():
    """ToolCreate and ToolUpdate reject unknown job slugs with validation errors."""
    # Valid job slugs pass
    tc = ToolCreate(
        name="Valid Tool",
        url="https://valid.com",
        domain="software",
        jobs=["write_code", "debug_code"],
    )
    assert tc.jobs == ["write_code", "debug_code"]

    # Unknown job slug fails
    with pytest.raises(ValidationError) as exc:
        ToolCreate(
            name="Invalid Tool",
            url="https://invalid.com",
            domain="software",
            jobs=["write_code", "invalid_fake_job_slug"],
        )
    assert "Unknown job slug" in str(exc.value)

    # ToolUpdate with unknown job slug fails
    with pytest.raises(ValidationError) as exc:
        ToolUpdate(jobs=["nonexistent_job"])
    assert "Unknown job slug" in str(exc.value)


def test_pydantic_rejects_unknown_domain():
    """ToolCreate rejects unknown domain slugs."""
    with pytest.raises(ValidationError) as exc:
        ToolCreate(
            name="Invalid Domain Tool",
            url="https://invaliddomain.com",
            domain="super_niche_domain",
            jobs=["write_code"],
        )
    assert "Unknown domain" in str(exc.value)


def test_taxonomy_helper_validation():
    """Direct helper functions validate_jobs and validate_domain."""
    assert validate_domain("software") == "software"
    assert validate_domain(None) is None
    with pytest.raises(ValueError, match="Unknown domain"):
        validate_domain("invalid_domain")

    assert validate_jobs(["write_code", "plan_app"]) == ["write_code", "plan_app"]
    assert validate_jobs([]) == []
    with pytest.raises(ValueError, match="Unknown job slug"):
        validate_jobs(["write_code", "hack_the_planet"])


def test_scoring_exact_slug_matching_removes_text_overlap():
    """Planner scoring uses EXACT job-slug matches and strictly excludes text-overlap matching."""
    tool_exact = Tool(
        id=1,
        name="Exact Coder",
        status="verified",
        link_status="ok",
        jobs=["write_code"],
        domain="software",
        has_free_tier=True,
    )
    # This tool has word overlap 'write', but a completely different slug 'write_tests'
    tool_overlap_only = Tool(
        id=2,
        name="Test Writer Only",
        status="verified",
        link_status="ok",
        jobs=["write_tests"],
        domain="software",
        has_free_tier=True,
    )
    brief = ProductBrief(
        what_being_made="Web app",
        purpose="Dev tool",
        target_audience="Developers",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="intermediate",
        budget_preference="free_only",
    )
    job_item = JobPlanningItem(
        step_number=1,
        job="Write code for the core application",
        job_tags=["write_code"],  # Exact slug requested
        input_types=["text"],
        output_types=["code"],
        output_expected="Application code",
    )

    candidates = shortlist_and_score([tool_exact, tool_overlap_only], job_item, [], brief)

    # Only tool_exact matches! tool_overlap_only MUST NOT match because text-overlap matching is removed.
    assert len(candidates) == 1
    assert candidates[0].id == 1
    assert candidates[0].name == "Exact Coder"


def test_tool_public_response_never_leaks_affiliate_url():
    """ToolPublicResponse exposes display fields and go_path, but never affiliate_url."""
    tool = Tool(
        id=42,
        name="Cursor",
        domain="software",
        url="https://cursor.com",
        affiliate_url="https://cursor.com?aff=secret123",
        docs_url="https://docs.cursor.com",
        jobs=["write_code", "debug_code"],
        pricing_model=PricingModel.FREEMIUM.value,
        has_free_tier=True,
        free_tier_summary="Free hobby plan with limited requests",
        starting_price_monthly_usd=20.0,
        skill_level=SkillLevel.ALL.value,
        tagline="AI code editor for codebase-aware edits",
        summary="Cursor is a code editor with AI chat.",
        how_it_helps="Use it to make code changes and investigate bugs.",
        pros=["Free tier available", "Codebase indexing", "Multi-file edits"],
        cons=["Quota limits", "Paid metered usage", "Needs local editor"],
        status=ToolStatus.VERIFIED.value,
        link_status="ok",
    )

    public_resp = ToolPublicResponse.model_validate(tool)
    dumped = public_resp.model_dump()

    assert dumped["id"] == 42
    assert dumped["name"] == "Cursor"
    assert dumped["domain"] == "software"
    assert dumped["go_path"] == "/go/42"
    assert dumped["has_free_tier"] is True
    assert dumped["starting_price_monthly_usd"] == 20.0
    assert dumped["tagline"] == "AI code editor for codebase-aware edits"
    assert len(dumped["pros"]) == 3
    assert len(dumped["cons"]) == 3

    # CRITICAL: affiliate_url must never be in public schema
    assert "affiliate_url" not in dumped
    assert "secret123" not in str(dumped)

    # Admin schema exposes affiliate_url and open_url
    admin_resp = ToolResponse.model_validate(tool)
    admin_dumped = admin_resp.model_dump()
    assert admin_dumped["affiliate_url"] == "https://cursor.com?aff=secret123"
    assert admin_dumped["open_url"] == "https://cursor.com?aff=secret123"


def test_prompt_style_schema_normalizes_rules():
    """PromptStyleSchema normalizes string and list rules to list[str]."""
    tc1 = ToolCreate(
        name="Tool 1",
        url="https://tool1.com",
        domain="software",
        jobs=["write_code"],
        prompt_style={
            "technique": "Direct",
            "format": "Markdown",
            "rules": "Rule 1\nRule 2\nRule 3",
            "example": "Do X",
        },
    )
    assert tc1.prompt_style.rules == ["Rule 1", "Rule 2", "Rule 3"]

    tc2 = ToolCreate(
        name="Tool 2",
        url="https://tool2.com",
        domain="software",
        jobs=["write_code"],
        prompt_style={
            "technique": "Direct",
            "format": "Markdown",
            "rules": ["Rule A", "Rule B"],
            "example": "Do Y",
        },
    )
    assert tc2.prompt_style.rules == ["Rule A", "Rule B"]

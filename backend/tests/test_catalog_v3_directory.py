"""Tests for Catalog v3 Slice C4: Public Directory Redesign.

Tests verify:
1. GET /api/v1/tools returns verified tools ordered with Pathwise picks first, then name alphabetically.
2. Dead link and unverified (draft/hidden) tools are strictly excluded from the public directory.
3. Filtering by domain (?domain=software) returns matching tools only.
4. Response conforms to ToolPublicResponse (includes go_path, verified_badge, is_pick, free_tier_summary, never leaks affiliate_url).
5. GET /api/v1/taxonomy returns 9 domains with job definitions and human-readable labels.
"""
import time
from datetime import UTC, datetime

import pytest

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.tool import ToolStatus
from app.services import catalog as catalog_service


@pytest.fixture
def directory_test_tools():
    db = SessionLocal()

    # Clean up prior test tools if any
    db.query(Tool).filter(Tool.name.like("C4_Test_%")).delete()
    db.commit()

    now = datetime.now(UTC)

    # 1. Verified, non-pick, software
    t1 = Tool(
        name="C4_Test_Beta_Tool",
        url="https://beta.example.com",
        affiliate_url="https://beta.example.com?aff=secret123",
        status=ToolStatus.VERIFIED.value,
        domain="software",
        jobs=["write_code"],
        is_pick=False,
        link_status="ok",
        pricing_model="freemium",
        has_free_tier=True,
        free_tier_summary="5 free runs per month",
        tagline="A beta testing tool for software",
        verified_at=now,
    )

    # 2. Verified, pick, software (starts with 'Z' but is_pick=True, should be first!)
    t2 = Tool(
        name="C4_Test_Zeta_Tool",
        url="https://zeta.example.com",
        affiliate_url="https://zeta.example.com?aff=secret456",
        status=ToolStatus.VERIFIED.value,
        domain="software",
        jobs=["debug_code", "review_code"],
        is_pick=True,
        link_status="ok",
        pricing_model="freemium",
        has_free_tier=True,
        free_tier_summary="Free hobby plan",
        tagline="A zeta pick tool for software",
        verified_at=now,
    )

    # 3. Verified, non-pick, design (starts with 'Alpha')
    t3 = Tool(
        name="C4_Test_Alpha_Design",
        url="https://alpha.example.com",
        status=ToolStatus.VERIFIED.value,
        domain="design",
        jobs=["design_ui"],
        is_pick=False,
        link_status="ok",
        pricing_model="free",
        has_free_tier=True,
        free_tier_summary="100% free open tool",
        tagline="An alpha design tool",
        verified_at=now,
    )

    # 4. Draft tool (should NOT appear)
    t4 = Tool(
        name="C4_Test_Draft_Tool",
        url="https://draft.example.com",
        status=ToolStatus.DRAFT.value,
        domain="software",
        jobs=["write_code"],
        is_pick=False,
        link_status="ok",
    )

    # 5. Hidden dead link tool (should NOT appear)
    t5 = Tool(
        name="C4_Test_Dead_Tool",
        url="https://dead.example.com",
        status=ToolStatus.VERIFIED.value,
        domain="software",
        jobs=["write_code"],
        is_pick=True,
        link_status="dead",
    )

    db.add_all([t1, t2, t3, t4, t5])
    db.commit()

    yield [t1, t2, t3, t4, t5]

    db.query(Tool).filter(Tool.name.like("C4_Test_%")).delete()
    db.commit()
    db.close()


def test_public_directory_picks_first_sort_and_filters(client, directory_test_tools):
    """GET /api/v1/tools orders Pathwise picks first, then name alphabetically, and filters correctly."""
    res = client.get("/api/v1/tools")
    assert res.status_code == 200
    data = res.json()

    # Filter to our test tools
    test_tools = [t for t in data if t["name"].startswith("C4_Test_")]
    names = [t["name"] for t in test_tools]

    # Verify exclusions: draft and dead tools must NOT be present
    assert "C4_Test_Draft_Tool" not in names
    assert "C4_Test_Dead_Tool" not in names

    # Verify ordering: C4_Test_Zeta_Tool has is_pick=True, so it must precede C4_Test_Alpha_Design and C4_Test_Beta_Tool!
    assert names[0] == "C4_Test_Zeta_Tool"
    assert names[1] == "C4_Test_Alpha_Design"
    assert names[2] == "C4_Test_Beta_Tool"

    # Verify domain filter
    res_domain = client.get("/api/v1/tools?domain=software")
    assert res_domain.status_code == 200
    data_domain = [t for t in res_domain.json() if t["name"].startswith("C4_Test_")]
    domain_names = [t["name"] for t in data_domain]
    assert "C4_Test_Alpha_Design" not in domain_names
    assert "C4_Test_Zeta_Tool" in domain_names
    assert "C4_Test_Beta_Tool" in domain_names


def test_public_directory_response_schema_integrity(client, directory_test_tools):
    """Public tool card exposes go_path, verified_badge, is_pick, free_tier_summary, and NEVER affiliate_url."""
    res = client.get("/api/v1/tools")
    assert res.status_code == 200
    test_tools = [t for t in res.json() if t["name"].startswith("C4_Test_")]

    for t in test_tools:
        # Schema field checks
        assert "go_path" in t
        assert t["go_path"].startswith("/go/")
        assert "verified_badge" in t
        assert "Verified" in t["verified_badge"]
        assert "is_pick" in t
        assert "tagline" in t
        assert "pricing_model" in t
        assert "has_free_tier" in t
        assert "free_tier_summary" in t
        # Security: NEVER leak affiliate_url
        assert "affiliate_url" not in t
        assert "open_url" not in t


def test_taxonomy_endpoint_returns_nine_domains(client):
    """GET /api/v1/taxonomy returns all 9 domains with corresponding jobs and labels."""
    res = client.get("/api/v1/taxonomy")
    assert res.status_code == 200
    data = res.json()

    assert "domains" in data
    assert "jobs" in data
    assert "domain_labels" in data
    assert "job_labels" in data

    expected_domains = {
        "software",
        "builders",
        "design",
        "video",
        "audio",
        "writing",
        "research",
        "deploy_backend",
        "freelance_ops",
    }

    found_domains = {d["slug"] for d in data["domains"]}
    assert expected_domains.issubset(found_domains)
    assert len(data["jobs"]) == 55


def _c4_names(payload):
    return [t["name"] for t in payload if t["name"].startswith("C4_Test_")]


def test_public_tools_cache_serves_and_invalidates(client, directory_test_tools):
    """Second GET is served from cache; invalidate restores fresh reads (perf)."""
    first = client.get("/api/v1/tools?domain=software")
    assert first.status_code == 200
    assert "C4_Test_Beta_Tool" in _c4_names(first.json())

    # Hide the tool behind the cache's back: cached read stays stale.
    db = SessionLocal()
    db.query(Tool).filter(Tool.name == "C4_Test_Beta_Tool").update({"status": ToolStatus.HIDDEN.value})
    db.commit()
    db.close()
    cached = client.get("/api/v1/tools?domain=software")
    assert cached.status_code == 200
    assert "C4_Test_Beta_Tool" in _c4_names(cached.json())

    catalog_service.invalidate_public_tools_cache()
    fresh = client.get("/api/v1/tools?domain=software")
    assert fresh.status_code == 200
    assert "C4_Test_Beta_Tool" not in _c4_names(fresh.json())


def test_public_tools_cache_expires(client, directory_test_tools):
    """Expired cache entries trigger a fresh database read."""
    first = client.get("/api/v1/tools?domain=software")
    assert first.status_code == 200
    assert "C4_Test_Beta_Tool" in _c4_names(first.json())

    db = SessionLocal()
    db.query(Tool).filter(Tool.name == "C4_Test_Beta_Tool").update({"status": ToolStatus.HIDDEN.value})
    db.commit()
    db.close()

    for key, (_expires, payload) in list(catalog_service._PUBLIC_TOOLS_CACHE.items()):
        catalog_service._PUBLIC_TOOLS_CACHE[key] = (time.monotonic() - 1, payload)
    refetched = client.get("/api/v1/tools?domain=software")
    assert refetched.status_code == 200
    assert "C4_Test_Beta_Tool" not in _c4_names(refetched.json())

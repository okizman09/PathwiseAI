import asyncio

import pytest

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.tool import PromptStyleSchema, ToolStatus, ToolUpdate
from app.services.catalog import update_tool
from app.services.research.fetcher import fetch_page_safe, is_safe_ip


def test_is_safe_ip():
    assert not is_safe_ip("127.0.0.1")
    assert not is_safe_ip("localhost") # not an IP, but handled by resolve_and_check
    assert not is_safe_ip("169.254.169.254")
    assert not is_safe_ip("10.0.0.1")
    assert not is_safe_ip("192.168.1.1")
    assert not is_safe_ip("0.0.0.0")

    assert is_safe_ip("8.8.8.8")
    assert is_safe_ip("1.1.1.1")

@pytest.mark.asyncio
async def test_fetch_page_safe_blocks_local():
    # Should block localhost / 127.0.0.1
    res = await fetch_page_safe("http://127.0.0.1:8000")
    assert res["ok"] is False
    assert "unsafe IP" in res["error"] or "resolve" in res["error"]

    res_metadata = await fetch_page_safe("http://169.254.169.254")
    assert res_metadata["ok"] is False
    assert "unsafe IP" in res_metadata["error"] or "resolve" in res_metadata["error"]

def test_verify_tool_blocks_missing_fields(client, monkeypatch):
    db = SessionLocal()

    async def mock_reachable(url):
        return True

    monkeypatch.setattr("app.services.catalog.check_url_reachable", mock_reachable)

    # Create a draft tool missing some fields
    tool = Tool(
        name="Test Tool",
        url="https://test.com",
        status=ToolStatus.DRAFT.value,
        jobs=[],
        category="",
        prompt_style=PromptStyleSchema().model_dump()
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)

    # Attempt to verify it
    tool_update = ToolUpdate(status=ToolStatus.VERIFIED)

    with pytest.raises(ValueError) as exc:
        asyncio.run(update_tool(db, tool, tool_update))

    assert "Cannot verify" in str(exc.value)
    assert "job" in str(exc.value).lower() or "unmet rules" in str(exc.value).lower()

    db.delete(tool)
    db.commit()
    db.close()


def test_patch_admin_tool_endpoint(client, monkeypatch):
    from app.models.profile import Profile
    from tests.test_auth import generate_token

    db = SessionLocal()
    profile = Profile(id="admin_patch_id", email="admin_patch@example.com", role="admin")
    db.merge(profile)

    tool = Tool(
        name="Candidate Tool",
        url="https://example.com",
        status=ToolStatus.DRAFT.value,
        jobs=["write_code"],
        category="software",
        domain="software",
        pricing_model="freemium",
        has_free_tier=True,
        free_tier_summary="Free tier with basic features",
        tagline="A candidate tool for testing.",
        pros=["Pro 1", "Pro 2", "Pro 3"],
        cons=["Con 1", "Con 2", "Con 3"],
        evidence={
            "pricing_model": {
                "source_url": "https://example.com/pricing",
                "quote": "Free forever",
            },
            "has_free_tier": {
                "source_url": "https://example.com/pricing",
                "quote": "Free tier",
            },
        },
        review_flags=[],
        prompt_style={
            "technique": "Role prompting",
            "format": "Markdown",
            "rules": ["Rule A", "Rule B"],
            "example": "Example prompt",
        },
        sources=[{"url": "https://example.com/docs", "ok": True}],
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)

    async def mock_reachable(url):
        return True

    monkeypatch.setattr("app.services.catalog.check_url_reachable", mock_reachable)

    token = generate_token(subject="admin_patch_id", email="admin_patch@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Patch with status=verified and rules as a list
    payload = {
        "status": "verified",
        "domain": "software",
        "jobs": ["write_code"],
        "pricing_model": "freemium",
        "has_free_tier": True,
        "free_tier_summary": "Free tier with basic features",
        "tagline": "A candidate tool for testing.",
        "pros": ["Pro 1", "Pro 2", "Pro 3"],
        "cons": ["Con 1", "Con 2", "Con 3"],
        "evidence": {
            "pricing_model": {
                "source_url": "https://example.com/pricing",
                "quote": "Free forever",
            },
            "has_free_tier": {
                "source_url": "https://example.com/pricing",
                "quote": "Free tier",
            },
        },
        "review_flags": [],
        "prompt_style": {
            "technique": "Role prompting",
            "format": "Markdown",
            "rules": ["Rule 1", "Rule 2"],
            "example": "Do something",
        },
        "sources": [{"url": "https://example.com/docs", "ok": True}],
    }

    res = client.patch(f"/api/v1/admin/tools/{tool.id}", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "verified"
    assert data["link_status"] == "ok"
    assert data["prompt_style"]["rules"] == ["Rule 1", "Rule 2"]

    db.delete(tool)
    db.commit()
    db.close()


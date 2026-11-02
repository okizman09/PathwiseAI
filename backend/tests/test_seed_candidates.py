import pytest

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.tool import ToolStatus
from app.scripts.seed_candidates import seed_tools
from app.services.catalog import validate_affiliate_url


def test_validate_affiliate_url():
    # Valid HTTPS URLs should not raise ValueError
    validate_affiliate_url("https://cursor.com?via=pathwise")
    validate_affiliate_url("https://supabase.com/pricing?ref=xyz")
    validate_affiliate_url(None)
    validate_affiliate_url("")

    # Invalid schemes should raise ValueError
    with pytest.raises(ValueError, match="HTTPS"):
        validate_affiliate_url("http://insecure.com")

    with pytest.raises(ValueError, match="HTTPS"):
        validate_affiliate_url("ftp://files.com")

    # Embedded credentials should raise ValueError
    with pytest.raises(ValueError, match="credentials"):
        validate_affiliate_url("https://user:pass@example.com")

    # Private / localhost should raise ValueError
    with pytest.raises(ValueError):
        validate_affiliate_url("https://127.0.0.1/affiliate")


def test_seed_from_csv_catalog_v3_idempotent(tmp_path, client, monkeypatch):
    """Test seeding from Catalog v3 CSV columns, taxonomy domain validation, and idempotency."""
    monkeypatch.setattr("app.services.catalog.resolve_and_check", lambda host: True)
    csv_content = """name,domain,url,docs_url,pricing_url,affiliate_url,official_domains
ToolAlpha,software,https://alpha.example.com,https://alpha.example.com/docs,https://alpha.example.com/pricing,https://alpha.example.com?via=pathwise,alpha.example.com|docs.alpha.example.com
ToolBeta,builders,https://beta.example.com,https://beta.example.com/docs,https://beta.example.com/pricing,,beta.example.com
ToolBadDomain,invalid_domain,https://bad.example.com,,,,bad.example.com
"""
    csv_file = tmp_path / "test_tools.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    db = SessionLocal()
    try:
        # Clean up if existing
        db.query(Tool).filter(Tool.name.in_(["ToolAlpha", "ToolBeta", "ToolBadDomain"])).delete()
        db.commit()

        # First run: should create ToolAlpha and ToolBeta as DRAFT, ToolBadDomain in errors
        res1 = seed_tools(str(csv_file), db=db)
        assert res1["created"] == 2
        assert res1["skipped"] == 0
        assert len(res1["errors"]) == 1
        assert "invalid taxonomy domain" in res1["errors"][0]

        tool_a = db.query(Tool).filter(Tool.name == "ToolAlpha").first()
        assert tool_a is not None
        assert tool_a.status == ToolStatus.DRAFT.value
        assert tool_a.domain == "software"
        assert tool_a.category == "software"
        assert tool_a.affiliate_url == "https://alpha.example.com?via=pathwise"
        assert tool_a.pricing_url == "https://alpha.example.com/pricing"
        assert tool_a.official_domains == ["alpha.example.com", "docs.alpha.example.com"]

        tool_b = db.query(Tool).filter(Tool.name == "ToolBeta").first()
        assert tool_b is not None
        assert tool_b.status == ToolStatus.DRAFT.value
        assert tool_b.domain == "builders"
        assert tool_b.official_domains == ["beta.example.com"]

        # Second run: should skip both (idempotent)
        res2 = seed_tools(str(csv_file), db=db)
        assert res2["created"] == 0
        assert res2["skipped"] == 2
        assert len(res2["errors"]) == 1

    finally:
        db.query(Tool).filter(Tool.name.in_(["ToolAlpha", "ToolBeta", "ToolBadDomain"])).delete()
        db.commit()
        db.close()

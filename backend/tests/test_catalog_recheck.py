import pytest

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.tool import ToolStatus
from app.services.catalog import recheck_tool
from app.services.research.extractor import ExtractionSchema


@pytest.mark.asyncio
async def test_recheck_tool_not_found(client):
    db = SessionLocal()
    try:
        with pytest.raises(ValueError) as exc:
            await recheck_tool(db, 999999)
        assert "not found" in str(exc.value)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recheck_tool_no_docs_url(client):
    db = SessionLocal()
    tool = Tool(
        name="No Docs Tool",
        url="https://example.com",
        docs_url=None,
        status=ToolStatus.DRAFT.value,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)

    try:
        with pytest.raises(ValueError) as exc:
            await recheck_tool(db, tool.id)
        assert "no docs_url" in str(exc.value)
    finally:
        db.delete(tool)
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_recheck_tool_fetch_failure_informative_error(client, monkeypatch):
    db = SessionLocal()
    tool = Tool(
        name="Failed Docs Tool",
        url="https://example.com",
        docs_url="https://example.com/blocked-docs",
        status=ToolStatus.DRAFT.value,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)

    async def mock_do_research(name, url, docs_urls):
        return {
            "extracted": None,
            "sources": [{"url": docs_urls[0], "ok": False, "error": "HTTP 403"}],
        }

    monkeypatch.setattr("app.services.catalog.do_research", mock_do_research)

    try:
        with pytest.raises(ValueError) as exc:
            await recheck_tool(db, tool.id)
        assert "Could not fetch docs" in str(exc.value)
        assert "HTTP 403" in str(exc.value)
        assert "https://example.com/blocked-docs" in str(exc.value)
    finally:
        db.delete(tool)
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_recheck_tool_success(client, monkeypatch):
    db = SessionLocal()
    tool = Tool(
        name="Valid Docs Tool",
        url="https://example.com",
        docs_url="https://example.com/docs",
        status=ToolStatus.DRAFT.value,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)

    async def mock_do_research(name, url, docs_urls):
        extracted = ExtractionSchema(
            category="coding",
            jobs=["Write code"],
            input_types=["text"],
            output_types=["code"],
            pricing="freemium",
            best_for="Developers",
            not_for="Cooking",
            prompt_style={
                "technique": "System instructions",
                "format": "Markdown",
                "rules": "Be concise",
                "example": "Hello",
            },
            research_notes="Verified via official docs.",
        )
        return {
            "extracted": extracted,
            "sources": [{"url": docs_urls[0], "ok": True, "error": None}],
        }

    monkeypatch.setattr("app.services.catalog.do_research", mock_do_research)

    try:
        diff = await recheck_tool(db, tool.id)
        assert diff["category"] == "coding"
        assert diff["jobs"] == ["Write code"]
        assert diff["pricing"] == "freemium"
        assert diff["prompt_style"]["technique"] == "System instructions"
        assert len(diff["sources"]) == 1
    finally:
        db.delete(tool)
        db.commit()
        db.close()

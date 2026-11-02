"""Tests for Meta catalog fields (hackathon T4).

New ecosystem/kind/model_id/api_snippet columns round-trip through the
importer, and the public tools endpoint filters by ecosystem.
"""
import pytest

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.card_import import CardImport
from app.services.importer import CardImporterService
from tests.test_card_importer import make_valid_card_dict

META_ATTRS = {
    "ecosystem": "meta",
    "kind": "runnable",
    "model_id": "muse-spark-1.3",
    "api_snippet": 'client.responses.create(model="muse-spark-1.3", input="hi")',
    "docs_url": "https://dev.meta.ai/docs/models",
}


def _cleanup(db, *names):
    for name in names:
        db.query(Tool).filter(Tool.name == name).delete()
    db.commit()


@pytest.mark.asyncio
async def test_importer_round_trips_meta_fields_on_create_and_update(client):
    """ecosystem/kind/model_id/api_snippet/docs_url persist on create and update."""
    db = SessionLocal()
    name = "MetaCat Roundtrip Tool"
    try:
        _cleanup(db, name)

        card = CardImport(**make_valid_card_dict(
            name=name,
            official_url="https://metacat-roundtrip.example.com",
            evidence={},
            **META_ATTRS,
        ))
        result = await CardImporterService.import_single_card(db, card)
        assert result.status == "created"

        row = db.query(Tool).filter(Tool.name == name).one()
        assert row.ecosystem == "meta"
        assert row.kind == "runnable"
        assert row.model_id == "muse-spark-1.3"
        assert row.api_snippet == META_ATTRS["api_snippet"]
        assert row.docs_url == "https://dev.meta.ai/docs/models"

        card2 = CardImport(**make_valid_card_dict(
            name=name,
            official_url="https://metacat-roundtrip.example.com",
            evidence={},
            ecosystem="meta",
            kind="open_weight",
            model_id="muse-spark-open",
            api_snippet="snippet v2",
            docs_url="https://dev.meta.ai/models/muse-spark-open",
        ))
        result2 = await CardImporterService.import_single_card(db, card2)
        assert result2.status == "updated"

        db.refresh(row)
        assert row.kind == "open_weight"
        assert row.model_id == "muse-spark-open"
        assert row.api_snippet == "snippet v2"
        assert row.docs_url == "https://dev.meta.ai/models/muse-spark-open"
    finally:
        _cleanup(db, name)
        db.close()


@pytest.mark.asyncio
async def test_ecosystem_filter_returns_only_meta_tools(client):
    """GET /api/v1/tools?ecosystem=meta returns only Meta tools, with new fields."""
    from app.services.plan import build_short_card

    db = SessionLocal()
    meta_name = "MetaCat Filter Meta"
    plain_name = "MetaCat Filter Plain"
    try:
        _cleanup(db, meta_name, plain_name)
        db.add(Tool(
            name=meta_name,
            url="https://metacat-filter-meta.example.com",
            status="verified",
            link_status="unknown",
            domain="software",
            category="software",
            ecosystem="meta",
            kind="runnable",
            model_id="muse-spark-1.3",
            api_snippet="print('hi')",
        ))
        db.add(Tool(
            name=plain_name,
            url="https://metacat-filter-plain.example.com",
            status="verified",
            link_status="unknown",
            domain="software",
            category="software",
        ))
        db.commit()

        resp = client.get("/api/v1/tools", params={"ecosystem": "meta"})
        assert resp.status_code == 200
        tools = resp.json()
        assert tools, "expected at least the seeded Meta tool"
        assert all(t["ecosystem"] == "meta" for t in tools)
        names = [t["name"] for t in tools]
        assert meta_name in names
        assert plain_name not in names
        meta_card = next(t for t in tools if t["name"] == meta_name)
        assert meta_card["kind"] == "runnable"
        assert meta_card["model_id"] == "muse-spark-1.3"
        assert meta_card["api_snippet"] == "print('hi')"

        # Short cards (used in workflow steps) carry the same fields.
        row = db.query(Tool).filter(Tool.name == meta_name).one()
        short = build_short_card(row)
        assert (short.ecosystem, short.kind, short.model_id, short.api_snippet) == (
            "meta", "runnable", "muse-spark-1.3", "print('hi')",
        )
    finally:
        _cleanup(db, meta_name, plain_name)
        db.close()

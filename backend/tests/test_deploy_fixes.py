"""Tests for deploy-readiness fixes: client IP trust, public tool visibility, storage duplicates."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.core import rate_limit
from app.core.config import settings
from app.db import SessionLocal
from app.models.tool import Tool
from app.services import catalog as catalog_service
from app.services.research import logos


def _request(xff: str | None, peer: str = "10.0.0.5"):
    headers = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=peer))


def test_client_ip_ignores_spoofed_leading_entries(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)
    # The client sends "1.1.1.1"; the trusted proxy appends the real address 203.0.113.9.
    assert rate_limit.get_client_ip(_request("1.1.1.1, 203.0.113.9")) == "203.0.113.9"
    assert rate_limit.get_client_ip(_request("203.0.113.9")) == "203.0.113.9"


def test_client_ip_two_proxies_and_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 2)
    assert rate_limit.get_client_ip(_request("9.9.9.9, 203.0.113.9, 172.70.0.1")) == "203.0.113.9"
    # Fewer entries than trusted proxies: use the first entry.
    assert rate_limit.get_client_ip(_request("203.0.113.9")) == "203.0.113.9"
    # Missing header: use the direct peer.
    assert rate_limit.get_client_ip(_request(None)) == "10.0.0.5"
    # Zero trusted proxies: header is ignored entirely.
    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 0)
    assert rate_limit.get_client_ip(_request("1.1.1.1")) == "10.0.0.5"


@pytest.fixture
def db(client):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_get_public_tool_accepts_unknown_link_but_not_dead(db):
    ok_tool = Tool(name="LinkUnknownTool", url="https://unknown-link.example.com", status="verified",
                   link_status="unknown", pricing_model="unknown", pricing="unknown", jobs=[])
    dead_tool = Tool(name="LinkDeadTool", url="https://dead-link.example.com", status="verified",
                     link_status="dead", pricing_model="unknown", pricing="unknown", jobs=[])
    draft_tool = Tool(name="LinkDraftTool", url="https://draft-link.example.com", status="draft",
                      link_status="ok", pricing_model="unknown", pricing="unknown", jobs=[])
    db.add_all([ok_tool, dead_tool, draft_tool])
    db.commit()
    try:
        assert catalog_service.get_public_tool(db, ok_tool.id) is not None
        assert catalog_service.get_public_tool(db, dead_tool.id) is None
        assert catalog_service.get_public_tool(db, draft_tool.id) is None
    finally:
        for t in (ok_tool, dead_tool, draft_tool):
            db.delete(t)
        db.commit()


@pytest.mark.no_storage_mock
@pytest.mark.parametrize("status_code,body,should_pass", [
    (200, "", True),
    (409, '{"error":"Duplicate"}', True),
    (400, '{"message":"The resource already exists - Duplicate"}', True),
    (500, "boom", False),
])
def test_storage_upload_treats_duplicate_as_success(monkeypatch, status_code, body, should_pass):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://abcdefghijkl.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "service-key")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return httpx.Response(status_code, text=body)

    monkeypatch.setattr(logos.httpx, "AsyncClient", FakeClient)
    coro = logos.upload_image_to_storage(b"\x89PNG\r\n\x1a\n", "image/png", "png", filename_hint="dup-test")
    if should_pass:
        url = asyncio.run(coro)
        assert url.startswith("https://abcdefghijkl.supabase.co/storage/v1/object/public/")
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(coro)


def test_assemble_database_url():
    from app.core.config import Settings

    s = Settings(DATABASE_URL="postgres://user:pass@host:5432/db")
    assert s.DATABASE_URL.startswith("postgresql")
    assert "@host:5432/db" in s.DATABASE_URL

    s_sqlite = Settings(DATABASE_URL="sqlite:///test.db")
    assert s_sqlite.DATABASE_URL == "sqlite:///test.db"


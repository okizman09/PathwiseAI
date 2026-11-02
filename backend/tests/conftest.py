"""Shared pytest fixtures for the Pathwise backend test suite.

All tests use an in-process FastAPI TestClient backed by an in-memory
SQLite database.  External LLM and Supabase APIs are never called in tests.
"""
import ipaddress
import os
import socket
from typing import Any

import pytest
from fastapi.testclient import TestClient

# ── Force test environment BEFORE importing the app ──────────────────────────
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("MODEL_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pathwise.db")


def mock_getaddrinfo(
    host: str,
    port: Any,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
):
    """Mock socket.getaddrinfo to make all tests offline-safe and independent of external DNS."""
    if not host:
        raise socket.gaierror(socket.EAI_NONAME, "No address associated with hostname")
    if isinstance(host, bytes):
        host = host.decode("utf-8", errors="replace")

    # 1. Host is already an IP literal
    try:
        ip = ipaddress.ip_address(host)
        fam = socket.AF_INET6 if ip.version == 6 else socket.AF_INET
        return [(fam, socket.SOCK_STREAM, 6, "", (str(ip), port or 0))]
    except ValueError:
        pass

    # 2. Localhost
    if host in ("localhost", "localhost.localdomain"):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port or 0))]

    # 3. Explicitly unresolvable test hostnames
    if (
        host.endswith(".invalid")
        or host in ("unresolvable.test", "nonexistent.test", "nxdomain.test")
        or host.startswith("unresolvable")
    ):
        raise socket.gaierror(socket.EAI_NONAME, f"Name or service not known: {host}")

    # 4. Explicitly private / internal test hostnames (for SSRF resolution tests)
    if (
        host.endswith(".internal")
        or host.endswith(".local")
        or host.endswith(".lan")
        or host.startswith("private.")
        or host.startswith("internal.")
    ):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port or 0))]

    # 5. All other valid hostnames (example.com, cursor.com, supabase.com, etc.)
    # Map to a safe public IP without touching external DNS.
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0))]


@pytest.fixture(autouse=True)
def mock_dns(monkeypatch):
    """Autouse fixture to mock socket.getaddrinfo across all tests."""
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)


@pytest.fixture(autouse=True)
def mock_default_logo_fetcher(monkeypatch, request):
    """Ensure logo processing does not make unmocked external network calls in unrelated test suites."""
    if "test_catalog_v3_logos" in getattr(request.node.fspath, "basename", str(request.node.fspath)):
        return
    async def _mock_process_tool_logo(*args, **kwargs):
        return None, None, None
    monkeypatch.setattr("app.services.importer.process_tool_logo", _mock_process_tool_logo)


@pytest.fixture(autouse=True)
def mock_storage_upload_in_tests(monkeypatch, request):
    """Test double for upload_image_to_storage that is active ONLY in tests.

    Can be bypassed by marking a test with @pytest.mark.no_storage_mock.
    """
    if "no_storage_mock" in request.keywords:
        return

    async def _mock_upload(
        image_bytes: bytes,
        mime_type: str,
        file_extension: str,
        path_prefix: str = "logos",
        filename_hint: str | None = None,
    ) -> str:
        import hashlib
        content_hash = hashlib.sha256(image_bytes).hexdigest()[:8]
        raw_slug = (filename_hint or "tool").lower().replace(" ", "-")
        safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in raw_slug).strip("-_") or "tool"
        return f"https://mock-supabase.local/storage/v1/object/public/tool-assets/{path_prefix}/{safe_slug}-{content_hash}.{file_extension}"

    monkeypatch.setattr("app.services.research.logos.upload_image_to_storage", _mock_upload)
    monkeypatch.setattr("app.routers.tools.upload_image_to_storage", _mock_upload)


@pytest.fixture(scope="session")
def client():
    """Return a TestClient wired to an in-memory SQLite database."""
    # Import here so env vars above are already set before pydantic reads them.
    from app.db import Base, engine
    from app.main import app

    Base.metadata.create_all(bind=engine)
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


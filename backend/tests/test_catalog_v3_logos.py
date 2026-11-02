"""Tests for Catalog v3 Slice C8: Tool logos, previews, and storage pipeline.

Verifies:
1. SSRF prevention on logo fetching.
2. Fake images (wrong magic bytes) rejected.
3. Oversized files (>1 MB) rejected.
4. Malicious SVG scripts and event handlers sanitized.
5. ICO files converted to PNG.
6. Fallback chain order: official hint -> page auto-discovery -> favicon fallback -> null.
7. Manual logo upload / paste is protected and never overwritten by automatic fetches.
8. Directory public endpoint renders verified tool with null logo cleanly.
9. Admin logo endpoints: /fetch-logo, /paste-logo-url, /upload-logo.
"""
import io
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from PIL import Image

from app.models.tool import Tool
from app.services.research.logos import (
    MAX_IMAGE_SIZE,
    detect_and_validate_image,
    fetch_binary_safe,
    is_official_host,
    process_tool_logo,
)


def make_dummy_png() -> bytes:
    """Creates a tiny valid 1x1 PNG byte string."""
    img = Image.new("RGBA", (1, 1), (0, 128, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_dummy_ico() -> bytes:
    """Creates a tiny valid 16x16 ICO byte string."""
    img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="ICO")
    return buf.getvalue()


def make_dummy_jpeg() -> bytes:
    """Creates a tiny valid 1x1 JPEG byte string."""
    img = Image.new("RGB", (1, 1), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_valid_image_formats_and_ico_conversion():
    """Valid PNG, JPEG, WebP, and ICO bytes are detected, with ICO converted to PNG."""
    png_bytes = make_dummy_png()
    clean_bytes, mime, ext = detect_and_validate_image(png_bytes)
    assert mime == "image/png"
    assert ext == "png"
    assert clean_bytes.startswith(b"\x89PNG")

    jpg_bytes = make_dummy_jpeg()
    clean_bytes, mime, ext = detect_and_validate_image(jpg_bytes)
    assert mime == "image/jpeg"
    assert ext == "jpg"

    # WebP
    webp_mock = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 20
    clean_bytes, mime, ext = detect_and_validate_image(webp_mock)
    assert mime == "image/webp"
    assert ext == "webp"

    # ICO conversion to PNG
    ico_bytes = make_dummy_ico()
    clean_bytes, mime, ext = detect_and_validate_image(ico_bytes)
    assert mime == "image/png"
    assert ext == "png"
    assert clean_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_fake_image_wrong_magic_bytes_rejected():
    """Text, HTML, or executable binaries disguised as images are rejected."""
    fake_png = b"Not really a png image file content"
    with pytest.raises(ValueError, match="Unsupported or invalid image format"):
        detect_and_validate_image(fake_png)

    html_payload = b"<!DOCTYPE html><html><body><h1>Malicious HTML</h1></body></html>"
    with pytest.raises(ValueError, match="Unsupported or invalid image format"):
        detect_and_validate_image(html_payload)

    exe_payload = b"MZ\x90\x00\x03\x00\x00\x00"
    with pytest.raises(ValueError, match="Unsupported or invalid image format"):
        detect_and_validate_image(exe_payload)


def test_oversized_file_rejected():
    """Images exceeding 1 MB (1,048,576 bytes) are rejected immediately."""
    oversized = b"\x89PNG\r\n\x1a\n" + b"X" * (MAX_IMAGE_SIZE + 10)
    with pytest.raises(ValueError, match="exceeds maximum allowed size of 1 MB"):
        detect_and_validate_image(oversized)


def test_malicious_svg_sanitized():
    """Malicious SVG with scripts, event handlers, and javascript: links is sanitized."""
    malicious_svg = b"""<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <script>alert('pwned')</script>
        <circle cx="50" cy="50" r="40" onload="alert('xss')" onclick="hack()" />
        <g>
            <script>console.log('nested script')</script>
            <rect width="20" height="20" />
        </g>
        <a href="javascript:alert(1)"><text>Click</text></a>
    </svg>"""

    clean_bytes, mime, ext = detect_and_validate_image(malicious_svg)
    assert mime == "image/svg+xml"
    assert ext == "svg"

    clean_text = clean_bytes.decode("utf-8").lower()
    assert "<script" not in clean_text
    assert "onload" not in clean_text
    assert "onclick" not in clean_text
    assert "javascript:" not in clean_text
    assert "<circle" in clean_text
    assert "<rect" in clean_text


@pytest.mark.asyncio
async def test_ssrf_blocked_on_fetch_binary_safe():
    """fetch_binary_safe rejects loopback, private, and cloud metadata targets."""
    # Loopback
    with pytest.raises(ValueError, match="SSRF Attempt Blocked|Invalid scheme|unsafe IP"):
        await fetch_binary_safe("http://127.0.0.1/logo.png")

    # Metadata IP
    with pytest.raises(ValueError, match="SSRF Attempt Blocked|unsafe IP"):
        await fetch_binary_safe("http://169.254.169.254/latest/meta-data")

    # Invalid scheme
    with pytest.raises(ValueError, match="Invalid scheme"):
        await fetch_binary_safe("ftp://example.com/logo.png")


def test_is_official_host_matching():
    """Verifies that official host checking matches exact and subdomains correctly."""
    official_domains = ["replit.com", "example.org"]
    official_url = "https://replit.com"

    assert is_official_host("https://replit.com/logo.png", official_domains, official_url) is True
    assert is_official_host("https://assets.replit.com/icon.svg", official_domains, official_url) is True
    assert is_official_host("https://cdn.example.org/brand.png", official_domains, official_url) is True

    # Google favicon service or third-party host is NOT an official domain
    assert is_official_host("https://www.google.com/s2/favicons?domain=replit.com", official_domains, official_url) is False
    assert is_official_host("https://phishing-replit.com/logo.png", official_domains, official_url) is False


@pytest.mark.asyncio
async def test_manual_upload_not_overwritten():
    """If tool already has logo_source == 'manual', automatic fetches do NOT overwrite it."""
    current_logo = "https://supabase.local/storage/v1/object/public/tool-assets/logos/custom_manual.png"

    resolved_logo, resolved_src, _ = await process_tool_logo(
        tool_url="https://replit.com",
        official_domains=["replit.com"],
        logo_source_url="https://replit.com/official_icon.png",
        current_logo_url=current_logo,
        current_logo_source="manual",
        force_override=False,
    )

    # Must preserve the manual logo!
    assert resolved_logo == current_logo
    assert resolved_src == "manual"


@pytest.mark.asyncio
async def test_fallback_chain_order():
    """Verifies fallback order:

    1. Official hint (if host is official)
    2. Page discovery (apple-touch-icon, icon, og:image)
    3. Google favicon service fallback
    4. None (null initials avatar)
    """
    dummy_png = make_dummy_png()

    # Case 1: Official hint matches official host
    with patch("app.services.research.logos.fetch_binary_safe", AsyncMock(return_value=(dummy_png, "https://replit.com/logo.png"))):
        logo_url, logo_src, _ = await process_tool_logo(
            tool_url="https://replit.com",
            official_domains=["replit.com"],
            logo_source_url="https://replit.com/logo.png",
        )
        assert logo_src == "official"
        assert logo_url is not None

    # Case 2: No official hint, but page has <link rel="apple-touch-icon">
    html_page = b"""<html><head>
        <link rel="apple-touch-icon" href="/touch-icon.png">
    </head><body></body></html>"""

    async def mock_fetch_page_or_icon(url, **kwargs):
        if url == "https://replit.com":
            return html_page, url
        return dummy_png, url

    with patch("app.services.research.logos.fetch_binary_safe", side_effect=mock_fetch_page_or_icon):
        logo_url, logo_src, _ = await process_tool_logo(
            tool_url="https://replit.com",
            official_domains=["replit.com"],
            logo_source_url=None,
        )
        assert logo_src == "page"
        assert logo_url is not None

    # Case 3: Page has no icons, falls back to Google favicon service
    empty_page = b"<html><head></head><body></body></html>"

    async def mock_fetch_empty_then_favicon(url, **kwargs):
        if "google.com/s2/favicons" in url:
            return dummy_png, url
        if url == "https://replit.com":
            return empty_page, url
        raise ValueError("Not found")

    with patch("app.services.research.logos.fetch_binary_safe", side_effect=mock_fetch_empty_then_favicon):
        logo_url, logo_src, _ = await process_tool_logo(
            tool_url="https://replit.com",
            official_domains=["replit.com"],
            logo_source_url=None,
        )
        assert logo_src == "favicon_service"
        assert logo_url is not None

    # Case 4: Everything fails -> returns None
    with patch("app.services.research.logos.fetch_binary_safe", AsyncMock(side_effect=ValueError("Down"))):
        logo_url, logo_src, _ = await process_tool_logo(
            tool_url="https://replit.com",
            official_domains=["replit.com"],
            logo_source_url=None,
        )
        assert logo_url is None
        assert logo_src is None


def test_directory_renders_verified_tool_with_null_logo(client):
    """Public tools endpoint /tools returns verified tools with null logo cleanly."""
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        # Create a verified tool with null logo
        tool = db.query(Tool).filter(Tool.name == "NullLogoToolTest").first()
        if not tool:
            tool = Tool(
                name="NullLogoToolTest",
                url="https://nulllogotool.example.com",
                domain="software",
                category="software",
                status="verified",
                jobs=["write_code"],
                pricing_model="free",
                logo_url=None,
                logo_source=None,
                og_image_url=None,
            )
            db.add(tool)
            db.commit()
            db.refresh(tool)

        res = client.get("/tools")
        assert res.status_code == 200
        items = res.json()
        target = next((t for t in items if t["name"] == "NullLogoToolTest"), None)
        assert target is not None
        assert target["logo_url"] is None
        assert target["logo_source"] is None
        assert target["og_image_url"] is None
    finally:
        db.close()


def test_admin_logo_endpoints(client, monkeypatch):
    """Verifies /fetch-logo, /paste-logo-url, and /upload-logo endpoints."""
    from app.api.deps import get_current_admin_user
    from app.db import SessionLocal

    # Mock admin auth dependency
    class MockAdminUser:
        id = "admin-1"
        email = "admin@pathwise.ai"
        role = "admin"

    from app.main import app
    app.dependency_overrides[get_current_admin_user] = lambda: MockAdminUser()

    db = SessionLocal()
    try:
        tool = db.query(Tool).filter(Tool.name == "LogoAdminTestTool").first()
        if not tool:
            tool = Tool(
                name="LogoAdminTestTool",
                url="https://testtool.example.com",
                domain="software",
                category="software",
                status="draft",
                jobs=["write_code"],
                logo_url=None,
                logo_source=None,
            )
            db.add(tool)
            db.commit()
            db.refresh(tool)

        tool_id = tool.id

        # 1. Paste logo URL
        dummy_png = make_dummy_png()
        with patch("app.routers.tools.fetch_binary_safe", AsyncMock(return_value=(dummy_png, "https://example.com/logo.png"))):
            res = client.post(
                f"/admin/tools/{tool_id}/paste-logo-url",
                json={"url": "https://example.com/logo.png"},
            )
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["logo_source"] == "manual"
            assert data["logo_url"] is not None

        # 2. Upload logo
        res = client.post(
            f"/admin/tools/{tool_id}/upload-logo",
            files={"file": ("logo.png", dummy_png, "image/png")},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["logo_source"] == "manual"
        assert data["logo_url"] is not None

        # 3. Upload invalid file rejected
        res = client.post(
            f"/admin/tools/{tool_id}/upload-logo",
            files={"file": ("fake.png", b"not an image", "image/png")},
        )
        assert res.status_code == 400

        # 4. Fetch logo
        with patch("app.routers.tools.process_tool_logo", AsyncMock(return_value=("https://supabase.local/storage/v1/object/public/tool-assets/logos/fetched.png", "page", None))):
            res = client.post(f"/admin/tools/{tool_id}/fetch-logo")
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["logo_url"] is not None

    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)
        db.close()


def test_svg_sanitization_removes_style_url_and_external_refs():
    """SVG sanitization removes <style> elements, styles with url() or @import,
    and <image> or <use> with external references.
    """
    svg_payload = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 100">
        <style>
            .banner { fill: red; }
            @import url("http://evil.com/leak.css");
        </style>
        <circle cx="50" cy="50" r="40" style="background: url('https://evil.com/leak.png'); color: red;" />
        <rect width="20" height="20" style="@import 'foo.css'; fill: blue;" />
        <path d="M0 0" style="fill: green;" />
        <image href="https://evil.com/tracker.png" />
        <image xlink:href="http://evil.com/tracker2.png" />
        <use href="https://evil.com/icons.svg#icon" />
        <use xlink:href="http://evil.com/icons.svg#icon2" />
        <use href="#local-icon" />
    </svg>"""

    clean_bytes, mime, ext = detect_and_validate_image(svg_payload)
    assert mime == "image/svg+xml"
    assert ext == "svg"

    clean_text = clean_bytes.decode("utf-8").lower()
    # 1. <style> element stripped
    assert "<style" not in clean_text
    assert "</style>" not in clean_text

    # 2. Dangerous style attributes stripped
    assert "url(" not in clean_text
    assert "@import" not in clean_text
    # Safe style attribute retained
    assert 'style="fill: green;"' in clean_text or "fill: green" in clean_text

    # 3. External <image> and <use> elements stripped
    assert "evil.com" not in clean_text
    assert "<image" not in clean_text

    # 4. Local # anchor <use> preserved
    assert "#local-icon" in clean_text


@pytest.mark.no_storage_mock
@pytest.mark.asyncio
async def test_storage_upload_missing_credentials_raises_error(monkeypatch):
    """Calling upload_image_to_storage with missing credentials raises a clear RuntimeError
    without returning any mock URL.
    """
    from app.core.config import settings
    from app.services.research.logos import upload_image_to_storage

    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    dummy_png = make_dummy_png()
    with pytest.raises(RuntimeError, match="Supabase Storage credentials missing in production"):
        await upload_image_to_storage(dummy_png, "image/png", "png", filename_hint="my-tool")

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    with pytest.raises(RuntimeError, match="Supabase Storage credentials missing"):
        await upload_image_to_storage(dummy_png, "image/png", "png", filename_hint="my-tool")


@pytest.mark.no_storage_mock
@pytest.mark.asyncio
async def test_storage_upload_filename_hash_and_no_upsert(monkeypatch):
    """Storage filename includes 8-char SHA-256 content hash and does not use upsert header."""
    import hashlib

    from app.core.config import settings
    from app.services.research.logos import upload_image_to_storage

    dummy_png = make_dummy_png()
    expected_hash = hashlib.sha256(dummy_png).hexdigest()[:8]

    captured_url = None
    captured_headers = None

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_url, captured_headers
        captured_url = str(request.url)
        captured_headers = dict(request.headers)
        return httpx.Response(201, json={"Key": "tool-assets/logos/test-tool.png"})

    monkeypatch.setattr(settings, "SUPABASE_URL", "https://real-supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "real-service-key")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "tool-assets")

    # Patch httpx.AsyncClient to use MockTransport
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(mock_transport_handler)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    public_url = await upload_image_to_storage(
        dummy_png, "image/png", "png", path_prefix="logos", filename_hint="my-tool"
    )

    assert f"my-tool-{expected_hash}.png" in captured_url
    assert f"my-tool-{expected_hash}.png" in public_url
    # Ensure x-upsert is NOT used
    assert "x-upsert" not in captured_headers


def test_upload_endpoint_enforces_1mb_limit_while_reading(client):
    """POST /admin/tools/{tool_id}/upload-logo rejects payloads > 1 MB immediately with HTTP 400."""
    from app.api.deps import get_current_admin_user
    from app.db import SessionLocal

    class MockAdminUser:
        id = "admin-1"
        email = "admin@pathwise.ai"
        role = "admin"

    from app.main import app
    app.dependency_overrides[get_current_admin_user] = lambda: MockAdminUser()

    db = SessionLocal()
    try:
        tool = db.query(Tool).filter(Tool.name == "SizeLimitToolTest").first()
        if not tool:
            tool = Tool(
                name="SizeLimitToolTest",
                url="https://sizelimit.example.com",
                domain="software",
                category="software",
                status="draft",
                jobs=["write_code"],
            )
            db.add(tool)
            db.commit()
            db.refresh(tool)

        oversized_data = b"X" * (MAX_IMAGE_SIZE + 1024)
        res = client.post(
            f"/admin/tools/{tool.id}/upload-logo",
            files={"file": ("huge.png", oversized_data, "image/png")},
        )
        assert res.status_code == 400
        assert "exceeds maximum allowed size" in res.json()["detail"]

    finally:
        app.dependency_overrides.pop(get_current_admin_user, None)
        db.close()


@pytest.mark.asyncio
async def test_importer_records_review_flag_on_logo_upload_failure(monkeypatch):
    """When logo upload fails in the importer, logo_url is null and review flag is added."""
    from app.db import SessionLocal
    from app.schemas.card_import import CardImport
    from app.services.importer import CardImporterService

    db = SessionLocal()
    try:
        card = CardImport(
            name="UploadFailToolTest",
            domain="software",
            official_url="https://uploadfail.example.com",
            logo_source_url="https://uploadfail.example.com/logo.png",
            jobs=["write_code"],
            pricing_model="free",
            has_free_tier=True,
            free_tier_summary="Free for all",
            starting_price_monthly_usd=None,
            platforms=["web"],
            skill_level="all",
            tagline="Test tool for upload failure",
            summary="A tool for testing upload failure handling in importer.",
            how_it_helps="Tests flags",
            pros=["Reliable error handling", "Predictable failure state", "Clean test coverage"],
            cons=["Requires credentials", "Network bound", "Storage dependent"],
            best_for="Testing",
            not_for="Production",
            input_types=["text"],
            output_types=["code"],
            evidence={},
        )

        async def _failing_process_tool_logo(*args, **kwargs):
            raise RuntimeError("Storage bucket not reachable")

        monkeypatch.setattr("app.services.importer.process_tool_logo", _failing_process_tool_logo)

        res = await CardImporterService.import_single_card(db, card)
        assert res.status == "created"

        tool = db.query(Tool).filter(Tool.name == "UploadFailToolTest").first()
        assert tool is not None
        assert tool.logo_url is None
        assert tool.logo_source is None
        assert any("logo upload failed: Storage bucket not reachable" in flag for flag in tool.review_flags)

    finally:
        db.close()

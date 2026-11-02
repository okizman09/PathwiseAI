import httpx
import pytest

from app.services.research.fetcher import fetch_page_safe


@pytest.mark.anyio
async def test_fetcher_stops_at_oversized_response():
    """Test that streaming stops and aborts when body exceeds MAX_CONTENT_LENGTH."""

    class OversizedByteStream(httpx.AsyncByteStream):
        def __init__(self, chunk_size: int = 1024 * 1024, num_chunks: int = 3):
            self.chunk = b"A" * chunk_size
            self.num_chunks = num_chunks

        async def __aiter__(self):
            for _ in range(self.num_chunks):
                yield self.chunk

    def custom_transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            stream=OversizedByteStream(),
        )

    transport = httpx.MockTransport(custom_transport_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # We pass a public domain so resolve_and_check passes
        result = await fetch_page_safe("https://example.com/oversized", client=client)

    assert result["ok"] is False
    assert "Content too large" in result["error"]


@pytest.mark.anyio
async def test_fetcher_blocks_redirect_to_private_ip():
    """Test that a redirect pointing to a private/loopback IP is blocked by SSRF checks."""

    def redirect_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(
                status_code=302,
                headers={"Location": "http://127.0.0.1:8080/internal-secrets"},
            )
        return httpx.Response(status_code=200, text="Should not reach here")

    transport = httpx.MockTransport(redirect_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_page_safe("https://example.com/start", client=client)

    assert result["ok"] is False
    assert "SSRF Attempt Blocked" in result["error"] or "unsafe IP" in result["error"]


@pytest.mark.anyio
async def test_fetcher_sends_browser_headers():
    """Test that requests include standard browser headers (User-Agent, Accept, Accept-Language)."""
    received_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal received_headers
        received_headers = dict(request.headers)
        return httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="<html><body>Hello</body></html>",
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_page_safe("https://example.com/page", client=client)

    assert result["ok"] is True
    assert "Mozilla" in received_headers.get("user-agent", "")
    assert "text/html" in received_headers.get("accept", "")
    assert "en" in received_headers.get("accept-language", "")


@pytest.mark.anyio
async def test_check_url_reachable_safe_status_codes():
    """Test that check_url_reachable_safe considers 200, 401, 403 (WAF/Cloudflare) as alive, and 404/500 as dead."""
    from app.services.research.fetcher import check_url_reachable_safe

    for code, expected in [(200, True), (403, True), (401, True), (405, True), (429, True), (404, False), (500, False)]:
        def handler(request: httpx.Request, status=code) -> httpx.Response:
            return httpx.Response(status_code=status, text="Response")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            res = await check_url_reachable_safe("https://example.com/check", client=client)
            assert res is expected, f"Expected {expected} for HTTP status {code}, got {res}"


@pytest.mark.anyio
async def test_check_url_reachable_safe_blocks_ssrf():
    """Test that check_url_reachable_safe blocks loopback / private IPs and redirect to private IPs."""
    from app.services.research.fetcher import check_url_reachable_safe

    # Direct loopback
    res = await check_url_reachable_safe("http://127.0.0.1:8000")
    assert res is False

    # Redirect to loopback
    def redirect_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=302, headers={"Location": "http://127.0.0.1:8000/admin"})

    transport = httpx.MockTransport(redirect_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        res_redirect = await check_url_reachable_safe("https://example.com/redirect", client=client)
        assert res_redirect is False


@pytest.mark.anyio
async def test_fetcher_blocks_unresolvable_hostname():
    """Test that fetcher handles DNS resolution failure gracefully without network access."""
    result = await fetch_page_safe("https://unresolvable.invalid/page")
    assert result["ok"] is False
    assert "Could not resolve hostname" in result["error"]


@pytest.mark.anyio
async def test_fetcher_blocks_dns_resolving_to_private_ip():
    """Test that a domain name resolving to an internal/private IP is blocked by SSRF checks."""
    result = await fetch_page_safe("https://private.internal/secret")
    assert result["ok"] is False
    assert "SSRF Attempt Blocked" in result["error"]
    assert "unsafe IP" in result["error"]


@pytest.mark.anyio
async def test_check_url_reachable_safe_unresolvable_offline():
    """Test that check_url_reachable_safe returns False for unresolvable domains."""
    from app.services.research.fetcher import check_url_reachable_safe

    res = await check_url_reachable_safe("https://unresolvable.invalid")
    assert res is False


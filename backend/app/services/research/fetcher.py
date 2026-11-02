import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 15.0
MAX_CONTENT_LENGTH = 1.5 * 1024 * 1024  # 1.5 MB

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def is_safe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            return False
        # Cloud metadata IPs
        if ip_str in ("169.254.169.254", "169.254.169.253"):
            return False
        # Catch any 0.x.x.x addresses which might slip through some checks
        if ip_str.startswith("0."):
            return False
        return True
    except ValueError:
        return False

def resolve_and_check(hostname: str) -> str:
    """
    Resolves a hostname to IPs and verifies that ALL resolved IPs are safe.
    Returns the first resolved IP if safe, otherwise raises an Exception.
    """
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")

    ips = [info[4][0] for info in addr_info]
    if not ips:
        raise ValueError(f"No IPs found for hostname: {hostname}")

    for ip in ips:
        if not is_safe_ip(ip):
            raise ValueError(f"SSRF Attempt Blocked: Hostname {hostname} resolves to unsafe IP {ip}")

    return ips[0]

def extract_readable_text(html_content: str) -> str:
    """Uses BeautifulSoup to extract readable text from HTML, removing scripts and styles."""
    soup = BeautifulSoup(html_content, "html.parser")
    for script_or_style in soup(["script", "style", "noscript", "meta", "head", "title", "header", "footer"]):
        script_or_style.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Collapse multiple newlines
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return text

async def fetch_page_safe(url: str, client: httpx.AsyncClient = None) -> dict[str, Any]:
    """
    Fetches a single page safely, guarding against SSRF.
    Returns a dict with 'url', 'ok', 'text', 'error'.
    """
    current_url = url
    redirects = 0
    own_client = False

    if client is None:
        client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=DEFAULT_HEADERS)
        own_client = True

    try:
        while redirects <= MAX_REDIRECTS:
            parsed = urlparse(current_url)
            if parsed.scheme not in ("http", "https"):
                return {"url": current_url, "ok": False, "error": f"Invalid scheme: {parsed.scheme}"}

            hostname = parsed.hostname
            if not hostname:
                return {"url": current_url, "ok": False, "error": "No hostname provided"}

            # Verify the IP is safe
            try:
                resolve_and_check(hostname)
            except ValueError as e:
                return {"url": current_url, "ok": False, "error": str(e)}

            # Perform the request with streaming to inspect body size progressively
            try:
                req = client.build_request("GET", current_url)
                current_ua = req.headers.get("User-Agent", "")
                if not current_ua or current_ua.startswith("python-httpx"):
                    req.headers["User-Agent"] = DEFAULT_HEADERS["User-Agent"]
                current_accept = req.headers.get("Accept", "")
                if not current_accept or current_accept == "*/*":
                    req.headers["Accept"] = DEFAULT_HEADERS["Accept"]
                if "Accept-Language" not in req.headers:
                    req.headers["Accept-Language"] = DEFAULT_HEADERS["Accept-Language"]
                response = await client.send(req, stream=True, follow_redirects=False)
            except httpx.RequestError as e:
                return {"url": current_url, "ok": False, "error": f"Request failed: {str(e)}"}

            if response.is_redirect:
                await response.aclose()
                redirects += 1
                if redirects > MAX_REDIRECTS:
                    return {"url": current_url, "ok": False, "error": "Too many redirects"}
                next_location = response.headers.get("Location")
                if not next_location:
                    return {"url": current_url, "ok": False, "error": "Redirect without Location header"}
                current_url = urljoin(current_url, next_location)
                continue

            if response.status_code != 200:
                await response.aclose()
                return {"url": current_url, "ok": False, "error": f"HTTP {response.status_code}"}

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                await response.aclose()
                return {"url": current_url, "ok": False, "error": f"Unsupported content type: {content_type}"}

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_CONTENT_LENGTH:
                await response.aclose()
                return {"url": current_url, "ok": False, "error": f"Content too large ({content_length} bytes)"}

            # Stream chunks and abort immediately if size cap is reached
            chunks = []
            total_size = 0
            size_exceeded = False
            try:
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    total_size += len(chunk)
                    if total_size > MAX_CONTENT_LENGTH:
                        size_exceeded = True
                        break
            finally:
                await response.aclose()

            if size_exceeded:
                return {"url": current_url, "ok": False, "error": f"Content too large (exceeded {int(MAX_CONTENT_LENGTH)} bytes)"}

            # Extract text
            content = b"".join(chunks)
            text = extract_readable_text(content.decode(errors='replace'))
            return {"url": current_url, "ok": True, "text": text, "error": None}

        return {"url": current_url, "ok": False, "error": "Unexpected loop exit"}
    finally:
        if own_client:
            await client.aclose()


async def check_url_reachable_safe(url: str, client: httpx.AsyncClient = None) -> bool:
    """
    Checks if a URL is reachable and alive, guarding against SSRF and redirect attacks.
    Does not download large bodies or enforce text/html content-type,
    and recognizes HTTP status codes 2xx, 3xx, 401, 403 (e.g. Cloudflare WAF/challenges),
    405, and 429 as proof that the server is online and reachable.
    """
    current_url = url
    redirects = 0
    own_client = False

    if client is None:
        client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=DEFAULT_HEADERS)
        own_client = True

    try:
        while redirects <= MAX_REDIRECTS:
            parsed = urlparse(current_url)
            if parsed.scheme not in ("http", "https"):
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            try:
                resolve_and_check(hostname)
            except Exception:
                return False

            try:
                req = client.build_request("GET", current_url)
                current_ua = req.headers.get("User-Agent", "")
                if not current_ua or current_ua.startswith("python-httpx"):
                    req.headers["User-Agent"] = DEFAULT_HEADERS["User-Agent"]
                current_accept = req.headers.get("Accept", "")
                if not current_accept or current_accept == "*/*":
                    req.headers["Accept"] = DEFAULT_HEADERS["Accept"]
                if "Accept-Language" not in req.headers:
                    req.headers["Accept-Language"] = DEFAULT_HEADERS["Accept-Language"]

                response = await client.send(req, stream=True, follow_redirects=False)
            except Exception:
                return False

            try:
                if response.is_redirect:
                    redirects += 1
                    if redirects > MAX_REDIRECTS:
                        return False
                    next_location = response.headers.get("Location")
                    if not next_location:
                        return False
                    current_url = urljoin(current_url, next_location)
                    continue

                code = response.status_code
                return code < 400 or code in (401, 403, 405, 429)
            finally:
                await response.aclose()

        return False
    finally:
        if own_client:
            await client.aclose()

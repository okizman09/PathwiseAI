"""Tool logo and preview image pipeline (Catalog v3 Slice C8).

Handles:
1. SSRF-safe image downloading (max 1 MB).
2. Format validation by magic bytes (PNG, JPG, WebP, SVG, ICO).
3. ICO to PNG conversion and SVG script/event-handler sanitization.
4. Upload to Supabase Storage (bucket tool-assets).
5. Fallback chain:
   - Official hint (logo_source_url on official domain) -> logo_source = "official"
   - Page auto-discovery (<apple-touch-icon>, largest <icon>) -> logo_source = "page"
   - og:image stored separately as og_image_url
   - Google favicon service fallback -> logo_source = "favicon_service"
   - Initials fallback (logo_url = None, logo_source = None)
6. Manual protection: manual upload / paste logo URL sets logo_source = "manual"
   and is never overwritten by automatic fetches.
"""
import hashlib
import io
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from PIL import Image

from app.core.config import settings
from app.services.research.fetcher import (
    DEFAULT_HEADERS,
    MAX_REDIRECTS,
    resolve_and_check,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 1 * 1024 * 1024  # 1 MB = 1,048,576 bytes
LOGO_TIMEOUT_SECONDS = 3.0

ALLOWED_LOGO_SOURCES = {"manual", "official", "page", "og", "favicon_service", "static"}


def sanitize_svg(raw_bytes: bytes) -> bytes:
    """Parses SVG XML and strips scripts, <style> elements, foreign objects, animation tags,
    inline event attributes, dangerous style attributes (containing url(, @import),
    and <image> / <use> elements with external references.
    Raises ValueError if SVG is invalid or contains unparseable XML.
    """
    try:
        text = raw_bytes.decode("utf-8", errors="replace")
        root = ET.fromstring(text)
    except Exception as e:
        raise ValueError(f"Invalid SVG XML content: {e}")

    root_tag = root.tag.split("}")[-1].lower() if "}" in root.tag else root.tag.lower()
    if root_tag != "svg":
        raise ValueError("Root element of SVG must be <svg>")

    disallowed_tags = {
        "script",
        "style",
        "foreignobject",
        "animate",
        "set",
        "handler",
        "iframe",
        "embed",
        "object",
        "audio",
        "video",
    }

    def clean_element(elem: ET.Element):
        for child in list(elem):
            tag_name = child.tag.split("}")[-1].lower() if "}" in child.tag else child.tag.lower()
            if tag_name in disallowed_tags:
                elem.remove(child)
                continue

            # Remove <image> and <use> elements with external references
            if tag_name in ("image", "use"):
                href_val = None
                for attr_k, attr_v in child.attrib.items():
                    if "href" in attr_k.lower():
                        href_val = str(attr_v).strip().lower()
                        break
                if href_val:
                    if tag_name == "image":
                        # External image references not allowed; only embedded data: allowed
                        if not href_val.startswith("data:"):
                            elem.remove(child)
                            continue
                    elif tag_name == "use":
                        # Only local fragment identifiers (#id) allowed
                        if not href_val.startswith("#"):
                            elem.remove(child)
                            continue
                elif tag_name == "image":
                    elem.remove(child)
                    continue

            clean_element(child)

        for attr in list(elem.attrib.keys()):
            attr_name = attr.split("}")[-1].lower() if "}" in attr else attr.lower()
            val = str(elem.attrib[attr]).strip().lower()
            # Remove inline JS handlers (onload, onclick, onerror, etc.)
            if attr_name.startswith("on"):
                del elem.attrib[attr]
            # Strip external/javascript hrefs
            elif "href" in attr_name:
                if any(val.startswith(p) for p in ("javascript:", "data:", "http:", "https:", "//")):
                    del elem.attrib[attr]
            # Strip dangerous styles (url(, @import, expression, javascript:)
            elif attr_name == "style":
                if (
                    re.search(r"url\s*\(", val)
                    or "@import" in val
                    or "expression" in val
                    or "javascript:" in val
                ):
                    del elem.attrib[attr]

    clean_element(root)
    try:
        ET.register_namespace("", "http://www.w3.org/2000/svg")
    except Exception:
        pass
    return ET.tostring(root, encoding="utf-8")


def detect_and_validate_image(data: bytes) -> tuple[bytes, str, str]:
    """Validates real file type from byte content, enforcing max size of 1 MB.

    Rejects any format other than PNG, JPG, WebP, SVG, ICO.
    Converts ICO to PNG.
    Sanitizes SVG.

    Returns:
        tuple of (clean_bytes, mime_type, file_extension)
    """
    if len(data) > MAX_IMAGE_SIZE:
        raise ValueError(f"File exceeds maximum allowed size of 1 MB ({len(data)} bytes)")

    if len(data) < 4:
        raise ValueError("Image data is too short to be valid")

    # 1. PNG: 89 50 4E 47 0D 0A 1A 0A
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png", "png"

    # 2. JPEG: FF D8 FF
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg", "jpg"

    # 3. WebP: RIFF ... WEBP
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return data, "image/webp", "webp"

    # 4. ICO: 00 00 01 00
    if data.startswith(b"\x00\x00\x01\x00"):
        try:
            img = Image.open(io.BytesIO(data))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            return png_bytes, "image/png", "png"
        except Exception as e:
            raise ValueError(f"Failed to convert ICO to PNG: {e}")

    # 5. SVG
    stripped = data.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<svg") or b"<svg" in data[:512].lower():
        try:
            clean_svg = sanitize_svg(data)
            return clean_svg, "image/svg+xml", "svg"
        except Exception as e:
            raise ValueError(f"Invalid or malicious SVG: {e}")

    raise ValueError("Unsupported or invalid image format. Supported formats: PNG, JPG, WebP, SVG, ICO.")


async def fetch_binary_safe(
    url: str,
    client: httpx.AsyncClient | None = None,
    max_bytes: int = MAX_IMAGE_SIZE,
) -> tuple[bytes, str]:
    """Downloads binary content safely guarding against SSRF and redirect attacks.

    Streams chunks and aborts immediately if total bytes exceed max_bytes.
    Returns (content_bytes, final_url).
    """
    current_url = url
    redirects = 0
    own_client = False

    if client is None:
        client = httpx.AsyncClient(timeout=LOGO_TIMEOUT_SECONDS, headers=DEFAULT_HEADERS)
        own_client = True

    try:
        while redirects <= MAX_REDIRECTS:
            parsed = urlparse(current_url)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid scheme: {parsed.scheme}")

            hostname = parsed.hostname
            if not hostname:
                raise ValueError("No hostname provided")

            # Check SSRF safety
            resolve_and_check(hostname)

            try:
                req = client.build_request("GET", current_url)
                response = await client.send(req, stream=True, follow_redirects=False)
            except httpx.RequestError as e:
                raise ValueError(f"Request failed: {str(e)}")

            if response.is_redirect:
                await response.aclose()
                redirects += 1
                if redirects > MAX_REDIRECTS:
                    raise ValueError("Too many redirects")
                next_location = response.headers.get("Location")
                if not next_location:
                    raise ValueError("Redirect without Location header")
                current_url = urljoin(current_url, next_location)
                continue

            if response.status_code != 200:
                await response.aclose()
                raise ValueError(f"HTTP {response.status_code} fetching {current_url}")

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                await response.aclose()
                raise ValueError(f"File exceeds maximum allowed size of {max_bytes} bytes")

            chunks = []
            total_size = 0
            size_exceeded = False
            try:
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    total_size += len(chunk)
                    if total_size > max_bytes:
                        size_exceeded = True
                        break
            finally:
                await response.aclose()

            if size_exceeded:
                raise ValueError(f"File exceeds maximum allowed size of {max_bytes} bytes")

            return b"".join(chunks), current_url

        raise ValueError("Unexpected loop exit during download")
    finally:
        if own_client:
            await client.aclose()


def is_official_host(url: str, official_domains: list[str], official_url: str | None = None) -> bool:
    """Checks whether the hostname of url belongs to the tool's official domains."""
    try:
        candidate_host = urlparse(url).hostname
        if not candidate_host:
            return False
        candidate_host = candidate_host.lower().lstrip("www.")

        domains_to_check = set()
        for d in official_domains:
            if d:
                domains_to_check.add(d.lower().lstrip("www."))

        if official_url:
            official_host = urlparse(official_url).hostname
            if official_host:
                domains_to_check.add(official_host.lower().lstrip("www."))

        for domain in domains_to_check:
            if candidate_host == domain or candidate_host.endswith("." + domain):
                return True
        return False
    except Exception:
        return False


def extract_icons_from_html(html_text: str, base_url: str) -> dict[str, list[str]]:
    """Extracts apple-touch-icon, icon, and og:image URLs from HTML text."""
    soup = BeautifulSoup(html_text, "html.parser")
    apple_touch_icons: list[str] = []
    regular_icons: list[tuple[int, str]] = []
    og_images: list[str] = []

    # 1. apple-touch-icon
    for link in soup.find_all("link", rel=True):
        rel_list = [r.lower() for r in (link["rel"] if isinstance(link["rel"], list) else [link["rel"]])]
        href = link.get("href")
        if not href:
            continue
        full_url = urljoin(base_url, href)

        if any("apple-touch-icon" in r for r in rel_list):
            apple_touch_icons.append(full_url)
        elif any("icon" in r for r in rel_list):
            # Parse declared size if present e.g. "192x192"
            sizes = link.get("sizes", "")
            area = 1
            if sizes and "x" in sizes.lower():
                try:
                    parts = sizes.lower().split("x")
                    area = int(parts[0]) * int(parts[1])
                except Exception:
                    area = 1
            regular_icons.append((area, full_url))

    # Sort regular icons largest first
    regular_icons.sort(key=lambda x: x[0], reverse=True)
    sorted_icons = [url for _, url in regular_icons]

    # 2. og:image
    for meta in soup.find_all("meta"):
        prop = meta.get("property") or meta.get("name") or ""
        if prop.lower() == "og:image":
            content = meta.get("content")
            if content:
                og_images.append(urljoin(base_url, content))

    return {
        "apple_touch_icons": apple_touch_icons,
        "icons": sorted_icons,
        "og_images": og_images,
    }


async def upload_image_to_storage(
    image_bytes: bytes,
    mime_type: str,
    file_extension: str,
    path_prefix: str = "logos",
    filename_hint: str | None = None,
) -> str:
    """Uploads validated image bytes to Supabase Storage bucket 'tool-assets'.

    Stores object as {path_prefix}/{tool-slug}-{hash8}.{file_extension}.
    Raises RuntimeError if credentials are missing or if upload fails.
    """
    content_hash = hashlib.sha256(image_bytes).hexdigest()[:8]
    raw_slug = (filename_hint or "tool").lower().replace(" ", "-")
    safe_slug = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in raw_slug).strip("-_") or "tool"
    filename = f"{safe_slug}-{content_hash}.{file_extension}"
    object_path = f"{path_prefix}/{filename}"

    bucket = getattr(settings, "SUPABASE_STORAGE_BUCKET", "tool-assets")
    base_url = (settings.SUPABASE_URL or "").rstrip("/")
    service_key = settings.SUPABASE_SERVICE_ROLE_KEY

    if not base_url or not service_key:
        if getattr(settings, "ENVIRONMENT", "").lower() == "production":
            raise RuntimeError(
                "Supabase Storage credentials missing in production: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured."
            )
        raise RuntimeError(
            "Supabase Storage credentials missing: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured."
        )

    upload_endpoint = f"{base_url}/storage/v1/object/{bucket}/{object_path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": mime_type,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(upload_endpoint, headers=headers, content=image_bytes)
        already_stored = resp.status_code == 409 or (
            resp.status_code == 400 and "duplicate" in resp.text.lower()
        )
        if resp.status_code not in (200, 201) and not already_stored:
            raise RuntimeError(
                f"Failed to upload image to Supabase Storage ({object_path}): HTTP {resp.status_code} - {resp.text}"
            )

    public_url = f"{base_url}/storage/v1/object/public/{bucket}/{object_path}"
    return public_url


async def process_tool_logo(
    tool_url: str,
    official_domains: list[str],
    logo_source_url: str | None = None,
    current_logo_url: str | None = None,
    current_logo_source: str | None = None,
    current_og_image_url: str | None = None,
    tool_slug: str = "tool",
    force_override: bool = False,
) -> tuple[str | None, str | None, str | None]:
    """Runs the full logo discovery & fallback pipeline for a tool.

    Returns:
        tuple of (logo_url, logo_source, og_image_url)
    """
    # 1. Manual wins and is never replaced by automatic fetch
    if current_logo_source == "manual" and not force_override:
        return current_logo_url, current_logo_source, current_og_image_url

    logo_url: str | None = None
    logo_source: str | None = None
    og_image_url: str | None = current_og_image_url

    # 2a. Official logo hint
    if logo_source_url and logo_source_url.startswith("https://"):
        if is_official_host(logo_source_url, official_domains, tool_url):
            try:
                data, _ = await fetch_binary_safe(logo_source_url)
                clean_bytes, mime, ext = detect_and_validate_image(data)
                logo_url = await upload_image_to_storage(
                    clean_bytes, mime, ext, path_prefix="logos", filename_hint=tool_slug
                )
                logo_source = "official"
            except RuntimeError:
                raise
            except Exception as e:
                logger.debug("Failed official logo hint %s: %s", logo_source_url, e)

    # 2b. Auto-discovery from official page
    if not logo_url and tool_url:
        try:
            html_bytes, final_page_url = await fetch_binary_safe(tool_url, max_bytes=1024 * 1024)
            html_text = html_bytes.decode("utf-8", errors="replace")
            icons_info = extract_icons_from_html(html_text, final_page_url)

            # Try apple-touch-icon
            for candidate in icons_info["apple_touch_icons"]:
                try:
                    data, _ = await fetch_binary_safe(candidate)
                    clean_bytes, mime, ext = detect_and_validate_image(data)
                except Exception:
                    continue
                logo_url = await upload_image_to_storage(
                    clean_bytes, mime, ext, path_prefix="logos", filename_hint=tool_slug
                )
                logo_source = "page"
                break

            # If still None, try largest icon
            if not logo_url:
                for candidate in icons_info["icons"]:
                    try:
                        data, _ = await fetch_binary_safe(candidate)
                        clean_bytes, mime, ext = detect_and_validate_image(data)
                    except Exception:
                        continue
                    logo_url = await upload_image_to_storage(
                        clean_bytes, mime, ext, path_prefix="logos", filename_hint=tool_slug
                    )
                    logo_source = "page"
                    break

            # Read og:image separately if not already present
            if not og_image_url:
                for candidate in icons_info["og_images"]:
                    try:
                        data, _ = await fetch_binary_safe(candidate)
                        clean_bytes, mime, ext = detect_and_validate_image(data)
                    except Exception:
                        continue
                    og_image_url = await upload_image_to_storage(
                        clean_bytes, mime, ext, path_prefix="previews", filename_hint=tool_slug
                    )
                    break
        except RuntimeError:
            raise
        except Exception as e:
            logger.debug("Auto-discovery failed on %s: %s", tool_url, e)

    # 2c. Fallback: Google favicon service server-side
    if not logo_url:
        try:
            target_host = urlparse(tool_url).hostname
            if not target_host and official_domains:
                target_host = official_domains[0]

            if target_host:
                clean_host = target_host.lstrip("www.")
                favicon_url = f"https://www.google.com/s2/favicons?domain={clean_host}&sz=128"
                data, _ = await fetch_binary_safe(favicon_url)
                clean_bytes, mime, ext = detect_and_validate_image(data)
                logo_url = await upload_image_to_storage(
                    clean_bytes, mime, ext, path_prefix="logos", filename_hint=tool_slug
                )
                logo_source = "favicon_service"
        except RuntimeError:
            raise
        except Exception as e:
            logger.debug("Favicon fallback failed for %s: %s", tool_url, e)

    # 2d. Final fallback: null
    return logo_url, logo_source, og_image_url

"""Rewrite generic tool taglines (batch follow-up 5): specific per strength.

Many catalog taglines are rule-based filler ("AI tool for ..."). This drafts
a specific, honest tagline per tool with the Meta model, grounded on the
tool's own homepage (<title> + meta description) plus name/category/jobs.

Meta-ecosystem cards are curated by hand (T5) and always skipped.

Dry-run by default (prints old -> new, writes nothing):

    cd backend && python scripts/rewrite_taglines.py
    cd backend && python scripts/rewrite_taglines.py --execute
    cd backend && python scripts/rewrite_taglines.py --execute --only-ids 17,90

Rules enforced: max 90 chars (DB limit), no pricing/plan claims, no
superlatives, no invented features. Over-long drafts are rejected and the
old tagline is kept. Commits per batch.
"""

import argparse
import asyncio
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402
from sqlalchemy import or_  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.tool import Tool  # noqa: E402
from app.services.llm import generate_structured  # noqa: E402
from app.services.research.logos import fetch_binary_safe  # noqa: E402

BATCH_SIZE = 12
MAX_TAGLINE = 90
TARGET_TAGLINE = 80
BANNED_RE = re.compile(r"\b(best|free|paid|pricing)\b|#1|\$|http", re.IGNORECASE)

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_RE = re.compile(
    r"<meta\s[^>]*?(?:name|property)=[\"'](?:og:description|description|og:title)[\"']"
    r"[^>]*?content=[\"'](.*?)[\"']",
    re.IGNORECASE | re.DOTALL,
)
META_REV_RE = re.compile(
    r"<meta\s[^>]*?content=[\"'](.*?)[\"'][^>]*?(?:name|property)=[\"']"
    r"(?:og:description|description|og:title)[\"']",
    re.IGNORECASE | re.DOTALL,
)


class TaglineItem(BaseModel):
    id: int
    tagline: str


class TaglineBatch(BaseModel):
    taglines: list[TaglineItem]


SYSTEM = (
    "You write short directory taglines for AI tools. Each tagline names the "
    "tool's specific strength: what it does best and for whom. Plain text, "
    "one line, no quotes, no trailing period, no emoji. Never invent "
    "features, integrations, or pricing; when unsure, stay close to the "
    "given category and jobs. Never claim a tool is free/paid or the best."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draft specific taglines per tool.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write valid drafts to the database. Without it, only prints.",
    )
    parser.add_argument(
        "--only-ids",
        default="",
        help="Comma-separated tool IDs to process (default: all non-Meta tools).",
    )
    parser.add_argument(
        "--exclude-ids",
        default="",
        help="Comma-separated tool IDs to skip (for hand-written taglines).",
    )
    return parser.parse_args()


def clean(text: str, limit: int = 200) -> str:
    text = html.unescape(re.sub(r"\s+", " ", text or "").strip())
    return text[:limit]


def extract_grounding(html_text: str) -> str:
    title = clean(TITLE_RE.search(html_text).group(1)) if TITLE_RE.search(html_text) else ""
    desc = ""
    for pattern in (META_RE, META_REV_RE):
        match = pattern.search(html_text)
        if match and match.group(1).strip():
            desc = clean(match.group(1))
            break
    parts = []
    if title:
        parts.append(f"Homepage title: {title}")
    if desc:
        parts.append(f"Homepage meta: {desc}")
    return " | ".join(parts) if parts else "Homepage text unavailable."


async def fetch_grounding(url: str) -> str:
    try:
        data, _ = await fetch_binary_safe(url, max_bytes=512 * 1024)
        return extract_grounding(data.decode("utf-8", errors="replace"))
    except Exception:
        return "Homepage text unavailable."


async def fetch_all_groundings(tools: list) -> dict[int, str]:
    sem = asyncio.Semaphore(10)

    async def one(tool) -> tuple[int, str]:
        async with sem:
            return tool.id, await fetch_grounding(tool.url or "")

    results = await asyncio.gather(*(one(t) for t in tools))
    return dict(results)


def batch_prompt(tools: list, groundings: dict[int, str]) -> str:
    lines = [
        f"Write one tagline per tool (max {TARGET_TAGLINE} characters each).",
        "Return every tool id exactly once.",
        "",
    ]
    for tool in tools:
        jobs = ", ".join((tool.jobs or [])[:5]) or "none"
        lines.append(f"[{tool.id}] {tool.name} ({tool.url})")
        lines.append(f"  category: {tool.category} | domain: {tool.domain or 'none'}")
        lines.append(f"  jobs: {jobs}")
        lines.append(f"  {groundings.get(tool.id, '')}")
        lines.append(f"  current tagline (replace it): {tool.tagline or 'none'}")
    return "\n".join(lines)


def valid_tagline(text: str) -> bool:
    if not text or len(text) > MAX_TAGLINE:
        return False
    return BANNED_RE.search(text) is None


async def draft_batch(tools: list, groundings: dict[int, str]) -> dict[int, str]:
    result = await generate_structured(
        system=SYSTEM,
        user=batch_prompt(tools, groundings),
        schema=TaglineBatch,
        temperature=0.4,
        max_output_tokens=4096,
    )
    drafts = {}
    wanted = {t.id for t in tools}
    for item in result.taglines:
        if item.id in wanted and item.id not in drafts:
            drafts[item.id] = item.tagline.strip().rstrip(".")
    return drafts


async def main_async(args: argparse.Namespace) -> int:
    only_ids = {int(p) for p in args.only_ids.split(",") if p.strip().isdigit()}
    exclude_ids = {int(p) for p in args.exclude_ids.split(",") if p.strip().isdigit()}

    db = SessionLocal()
    try:
        query = db.query(Tool).filter(
            or_(Tool.ecosystem.is_(None), Tool.ecosystem != "meta")
        )
        if only_ids:
            query = query.filter(Tool.id.in_(only_ids))
        if exclude_ids:
            query = query.filter(Tool.id.notin_(exclude_ids))
        tools = query.order_by(Tool.id).all()
        print(f"Rewriting taglines for {len(tools)} tools (Meta cards skipped).")

        groundings = await fetch_all_groundings(tools)
        print(f"Homepage grounding fetched for {len(groundings)} tools.\n")

        saved = kept = rejected = failed = 0
        for i in range(0, len(tools), BATCH_SIZE):
            batch = tools[i : i + BATCH_SIZE]
            try:
                drafts = await draft_batch(batch, groundings)
            except Exception as exc:
                failed += len(batch)
                print(f"Batch {[t.id for t in batch]} FAILED: {type(exc).__name__}")
                continue
            for tool in batch:
                new = drafts.get(tool.id, "")
                if not new or not valid_tagline(new):
                    rejected += 1
                    print(f"[{tool.id}] {tool.name}: REJECTED {new!r} (kept old)")
                    continue
                if new == (tool.tagline or ""):
                    kept += 1
                    continue
                print(f"[{tool.id}] {tool.name}:\n  old: {tool.tagline}\n  new: {new}")
                if args.execute:
                    tool.tagline = new
                    saved += 1
            if args.execute:
                db.commit()

        print("\nDry run: nothing written. Rerun with --execute to save."
              if not args.execute else f"\nSaved: {saved}.")
        print(f"Unchanged: {kept}, rejected: {rejected}, failed: {failed}.")
        return 1 if failed else 0
    finally:
        db.close()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

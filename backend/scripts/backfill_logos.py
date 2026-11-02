"""Bulk logo backfill (batch follow-up 4): logos + og previews for tools.

Reuses the same pipeline as the admin fetch-logo endpoint
(`process_tool_logo`): official hint -> page discovery (touch icon,
largest icon, og:image) -> favicon-service fallback, uploaded to the
`tool-assets` bucket. Manual logos are never replaced unless --force.

Dry-run by default (lists candidates, writes nothing):

    cd backend && python scripts/backfill_logos.py
    cd backend && python scripts/backfill_logos.py --execute
    cd backend && python scripts/backfill_logos.py --execute --limit 50 --include-og-only

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in backend/.env for
--execute (uploads). Commits per tool so partial progress survives.
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.tool import Tool  # noqa: E402
from app.services.research.logos import process_tool_logo  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing tool logos and previews.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually fetch and store. Without it, only lists candidates.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max tools to process per run (0 = no limit). Default: 20.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch every tool, including manual logos. Default: only missing.",
    )
    parser.add_argument(
        "--include-og-only",
        action="store_true",
        help="Also process tools that have a logo but lack og_image_url.",
    )
    return parser.parse_args()


def pick_candidates(tools: list, include_og_only: bool, force: bool) -> list:
    if force:
        return list(tools)
    candidates = []
    for tool in tools:
        if not (tool.logo_url or "").strip():
            candidates.append(tool)
        elif include_og_only and not (tool.og_image_url or "").strip():
            candidates.append(tool)
    return candidates


async def backfill_one(db, tool, force: bool) -> str:
    """Fetch for one tool, persist, return a one-line result. Never raises."""
    try:
        logo_url, logo_source, og_image_url = await process_tool_logo(
            tool_url=tool.url,
            official_domains=tool.official_domains or [],
            current_logo_url=tool.logo_url,
            current_logo_source=tool.logo_source,
            current_og_image_url=tool.og_image_url,
            tool_slug=(tool.name or "tool").lower(),
            force_override=force,
        )
        tool.logo_url = logo_url
        tool.logo_source = logo_source
        if og_image_url:
            tool.og_image_url = og_image_url
        db.commit()
        if logo_url:
            og = " +og" if tool.og_image_url else ""
            return f"[{tool.id}] {tool.name}: logo <- {logo_source}{og}"
        return f"[{tool.id}] {tool.name}: no logo found"
    except Exception as exc:  # keep going; report the failure type only
        db.rollback()
        return f"[{tool.id}] {tool.name}: FAILED {type(exc).__name__}"


async def main_async(args: argparse.Namespace) -> int:
    if args.execute and not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
        print("Missing Supabase Storage credentials: SUPABASE_URL and "
              "SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env.")
        return 2

    db = SessionLocal()
    try:
        tools = db.query(Tool).order_by(Tool.id).all()
        candidates = pick_candidates(tools, args.include_og_only, args.force)
        if args.limit and args.limit > 0:
            candidates = candidates[: args.limit]

        if not args.execute:
            print(f"Dry run: {len(candidates)} of {len(tools)} tools need logos "
                  f"(limit {args.limit}). Re-run with --execute to fetch.")
            for tool in candidates:
                missing = "logo" if not (tool.logo_url or "").strip() else "og-image"
                print(f"  [{tool.id}] {tool.name} ({tool.url}) missing {missing}")
            return 0

        ok = failed = 0
        for tool in candidates:
            line = await backfill_one(db, tool, args.force)
            print(line, flush=True)
            if "FAILED" in line:
                failed += 1
            else:
                ok += 1
            time.sleep(0.5)
        print(f"\nDone: {ok} ok, {failed} failed, {len(tools) - len(candidates)} skipped.")
        return 1 if failed else 0
    finally:
        db.close()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

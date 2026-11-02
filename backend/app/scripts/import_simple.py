"""Import and upsert tools from tools_simple.csv into Pathwise catalog (Catalog v3 SIMPLE-IMPORT).

CSV Columns:
  name, domain, jobs (slugs separated by |), url, docs_url, logo_url, logo_source_url

Rules:
- Upsert by case-insensitive name or url.
- Create new tools as status=verified (set verified_at) so they show in the directory.
- Fill only EMPTY fields on existing tools; never overwrite pricing, explanations,
  evidence, affiliate_url or a manual logo.
- Validate jobs against taxonomy, drop unknown slugs and report them. Validate domain.
- Accept logo_url as an https URL or a "/logos/<file>.svg" static path (set logo_source="static").
- For rows with no logo_url but a logo_source_url, run existing process_tool_logo pipeline
  when Supabase storage is configured; otherwise skip and report.
"""
import argparse
import asyncio
import csv
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import SessionLocal
from app.models.tool import Tool
from app.services.research.logos import process_tool_logo
from app.taxonomy.loader import is_valid_domain, is_valid_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def normalize_domain(url_or_domain: str) -> str:
    """Extracts clean domain name (e.g. 'example.com') from a URL or domain string."""
    raw = (url_or_domain or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.netloc or parsed.path
    else:
        host = raw.split("/")[0]
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def validate_domain(domain_val: str) -> bool:
    """Validates domain as either a valid taxonomy domain slug or a valid internet domain."""
    clean = (domain_val or "").strip().lower()
    if not clean:
        return False
    if is_valid_domain(clean):
        return True
    return bool(re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$", clean))


def resolve_csv_path(path_str: str) -> Path:
    """Finds the CSV file checking direct path, cwd, and repo root."""
    candidate = Path(path_str)
    if candidate.exists():
        return candidate

    cwd_candidate = Path.cwd() / path_str
    if cwd_candidate.exists():
        return cwd_candidate

    repo_root = Path(__file__).resolve().parents[3]
    repo_candidate = repo_root / path_str
    if repo_candidate.exists():
        return repo_candidate

    parent_candidate = Path.cwd().parent / path_str
    if parent_candidate.exists():
        return parent_candidate

    raise FileNotFoundError(f"Cannot find CSV file at '{path_str}'. Checked cwd ({Path.cwd()}) and repo root ({repo_root}).")


async def import_simple_csv(
    csv_file_path: Any = "tools_simple.csv",
    db: Session | None = None,
) -> dict[str, Any]:
    """Imports and upserts tools from tools_simple.csv.

    Returns summary dictionary with counts of total, created, updated, skipped,
    and dropped job slugs.
    """
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    stats = {
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "dropped_jobs_count": 0,
        "dropped_jobs": [],
        "errors": [],
    }

    storage_configured = bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)
    if not storage_configured:
        logger.info("Supabase storage not configured: remote logo downloads will be skipped and reported.")

    try:
        if hasattr(csv_file_path, "read"):
            reader = csv.DictReader(csv_file_path)
            rows = list(reader)
        else:
            csv_path = resolve_csv_path(str(csv_file_path))
            logger.info("Reading simple tools CSV from: %s", csv_path)
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        stats["total"] = len(rows)

        for line_num, row in enumerate(rows, start=2):
            name = (row.get("name") or "").strip()
            url = (row.get("url") or "").strip()
            domain_raw = (row.get("domain") or "").strip().lower()
            jobs_raw = (row.get("jobs") or "").strip()
            docs_url = (row.get("docs_url") or "").strip() or None
            logo_url_raw = (row.get("logo_url") or "").strip() or None
            logo_source_url_raw = (row.get("logo_source_url") or "").strip() or None

            if not name or not url:
                err = f"Row {line_num}: missing required name or url"
                logger.error(err)
                stats["errors"].append(err)
                stats["skipped"] += 1
                continue

            # 1. Validate domain
            if not is_valid_domain(domain_raw):
                err = f"Row {line_num} ({name}): unknown domain '{domain_raw}'"
                logger.error(err)
                stats["errors"].append(err)
                stats["skipped"] += 1
                continue

            # 2. Validate jobs, drop unknown slugs
            valid_jobs: list[str] = []
            for slug_part in jobs_raw.split("|"):
                slug = slug_part.strip()
                if not slug:
                    continue
                if is_valid_job(slug):
                    valid_jobs.append(slug)
                else:
                    stats["dropped_jobs_count"] += 1
                    stats["dropped_jobs"].append(f"{name}:{slug}")
                    logger.warning("Row %s (%s): dropped unknown job slug '%s'", line_num, name, slug)

            # 3. Determine logo_url & logo_source
            resolved_logo_url: str | None = None
            resolved_logo_source: str | None = None

            if logo_url_raw:
                resolved_logo_url = logo_url_raw
                resolved_logo_source = "static"
            elif logo_source_url_raw:
                if storage_configured:
                    try:
                        fetched_url, fetched_src, _ = await process_tool_logo(
                            tool_url=url,
                            official_domains=[normalize_domain(url)],
                            logo_source_url=logo_source_url_raw,
                            tool_slug=name.lower(),
                        )
                        resolved_logo_url = fetched_url
                        resolved_logo_source = fetched_src
                    except Exception as e:
                        logger.warning("Row %s (%s): remote logo upload failed: %s", line_num, name, e)
                else:
                    logger.info("Storage not configured; skipped remote logo discovery for '%s' (%s)", name, logo_source_url_raw)

            # 4. Upsert tool by case-insensitive name or url
            existing_tool = (
                db.query(Tool)
                .filter(
                    (func.lower(Tool.name) == name.lower())
                    | (Tool.url == url)
                )
                .first()
            )

            now = datetime.now(UTC)

            if existing_tool is None:
                # Create brand new verified tool
                new_tool = Tool(
                    name=name,
                    url=url,
                    docs_url=docs_url,
                    domain=domain_raw,
                    category=domain_raw,
                    jobs=valid_jobs,
                    logo_url=resolved_logo_url,
                    logo_source=resolved_logo_source,
                    status="verified",
                    verified_at=now,
                    pricing_model="unknown",
                    pricing="unknown",
                )
                db.add(new_tool)
                stats["created"] += 1
                logger.debug("Created new tool: %s", name)
            else:
                # Existing tool: fill only EMPTY fields; never overwrite pricing, explanations,
                # evidence, affiliate_url or a manual logo.
                has_changes = False

                if existing_tool.status != "verified":
                    existing_tool.status = "verified"
                    if not existing_tool.verified_at:
                        existing_tool.verified_at = now
                    has_changes = True

                if not existing_tool.docs_url and docs_url:
                    existing_tool.docs_url = docs_url
                    has_changes = True

                if not existing_tool.domain and domain_raw:
                    existing_tool.domain = domain_raw
                    existing_tool.category = domain_raw
                    has_changes = True

                if (not existing_tool.jobs or len(existing_tool.jobs) == 0) and valid_jobs:
                    existing_tool.jobs = valid_jobs
                    has_changes = True

                # Logo update: only if existing tool has NO logo and not a manual logo
                if existing_tool.logo_source != "manual" and not existing_tool.logo_url and resolved_logo_url:
                    existing_tool.logo_url = resolved_logo_url
                    existing_tool.logo_source = resolved_logo_source
                    has_changes = True

                if has_changes:
                    stats["updated"] += 1
                    logger.debug("Updated existing tool: %s", name)
                else:
                    stats["skipped"] += 1
                    logger.debug("Skipped tool without changes: %s", name)

        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()

    # Print summary table
    print("\n" + "=" * 55)
    print("           SIMPLE IMPORT SUMMARY REPORT")
    print("=" * 55)
    print(f"Total CSV rows evaluated:      {stats['total']}")
    print(f"New tools created (verified):  {stats['created']}")
    print(f"Existing tools updated:        {stats['updated']}")
    print(f"Tools skipped (no changes):    {stats['skipped']}")
    print(f"Dropped unknown job slugs:     {stats['dropped_jobs_count']}")
    if stats["dropped_jobs"]:
        print(f"  Dropped slugs: {', '.join(stats['dropped_jobs'])}")
    if stats["errors"]:
        print(f"Row errors encountered:        {len(stats['errors'])}")
        for err in stats["errors"]:
            print(f"  - {err}")
    print("=" * 55 + "\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Import simple tools catalog CSV into Pathwise database.")
    parser.add_argument(
        "csv_file",
        nargs="?",
        default="tools_simple.csv",
        help="Path to tools_simple.csv (default: tools_simple.csv)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(import_simple_csv(args.csv_file))
    except Exception as e:
        logger.error("Import failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

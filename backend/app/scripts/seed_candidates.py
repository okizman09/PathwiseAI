"""Seed draft tools from tools.csv into the Pathwise catalog database (Slice C6).

CSV Columns:
  name, domain, url, docs_url, pricing_url, affiliate_url, official_domains (use '|' between domains)

Enforces:
- Domain validated against Catalog v3 taxonomy.
- Affiliate URL validated with HTTPS and SSRF safety rules.
- Creates DRAFT tools only.
- Fully idempotent: existing tools by name or URL are skipped.
- Research flag removed (research now ingested via Card Importer).
- Prints a clean summary table upon completion.
"""
import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.tool import Tool
from app.schemas.tool import PromptStyleSchema, ToolStatus
from app.services.catalog import validate_affiliate_url
from app.taxonomy.loader import is_valid_domain

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_official_domains(raw: str | None) -> list[str]:
    """Split pipe-separated domains string into cleaned domain list."""
    if not raw:
        return []
    # Support pipe delimiter as specified in Section 6, fallback to comma
    delim = "|" if "|" in raw else ","
    domains = [d.strip().lower() for d in raw.split(delim)]
    return [d for d in domains if d]


def seed_tools(
    csv_file_path: str,
    db: Session | None = None,
) -> dict[str, Any]:
    """Parse CSV and seed tools as DRAFTs.

    Returns statistics dict: { "total": int, "created": int, "skipped": int, "errors": list[str] }
    """
    path = Path(csv_file_path)
    if not path.exists():
        logger.error("CSV file not found: %s", csv_file_path)
        raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    stats: dict[str, Any] = {
        "total": 0,
        "created": 0,
        "skipped": 0,
        "errors": [],
    }

    try:
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]

            required_headers = {"name", "domain", "url"}
            if not required_headers.issubset(set(fieldnames)):
                err = f"CSV must contain at least {required_headers} headers. Found: {fieldnames}"
                logger.error(err)
                raise ValueError(err)

            rows = list(reader)

        stats["total"] = len(rows)
        logger.info("Processing %d candidate rows from %s...", len(rows), path.name)

        for row in rows:
            name = (row.get("name") or "").strip()
            domain = (row.get("domain") or "").strip()
            url = (row.get("url") or "").strip()
            docs_url = (row.get("docs_url") or "").strip() or None
            pricing_url = (row.get("pricing_url") or "").strip() or None
            affiliate_url = (row.get("affiliate_url") or "").strip() or None
            raw_domains = row.get("official_domains") or ""

            if not name or not url:
                err_msg = f"Row missing required name or url: {row}"
                logger.warning(err_msg)
                stats["errors"].append(err_msg)
                continue

            # 1. Validate domain against taxonomy
            if not domain or not is_valid_domain(domain):
                err_msg = f"Tool '{name}' has invalid taxonomy domain '{domain}'"
                logger.warning(err_msg)
                stats["errors"].append(err_msg)
                continue

            # 2. Validate affiliate URL if provided
            if affiliate_url:
                try:
                    validate_affiliate_url(affiliate_url)
                except ValueError as ve:
                    err_msg = f"Tool '{name}' invalid affiliate_url '{affiliate_url}': {ve}"
                    logger.warning(err_msg)
                    stats["errors"].append(err_msg)
                    continue

            # 3. Parse official domains
            official_domains_list = parse_official_domains(raw_domains)

            # 4. Idempotency check: skip if tool already exists by name or URL
            name_norm = name.lower()
            existing = (
                db.query(Tool)
                .filter((func.lower(Tool.name) == name_norm) | (Tool.url == url))
                .first()
            )
            if existing:
                logger.info("Tool '%s' already exists (ID: %d, status: %s). Skipping.", name, existing.id, existing.status)
                stats["skipped"] += 1
                continue

            # Parse optional suggested_jobs
            suggested_jobs_raw = row.get("suggested_jobs") or row.get("jobs") or ""
            jobs_list = [j.strip() for j in suggested_jobs_raw.split("|") if j.strip()]

            # 5. Create DRAFT tool only
            tool = Tool(
                name=name,
                domain=domain,
                category=domain,  # Maintain DB backwards compatibility
                url=url,
                docs_url=docs_url,
                pricing_url=pricing_url,
                affiliate_url=affiliate_url,
                official_domains=official_domains_list,
                status=ToolStatus.DRAFT.value,
                pricing_model="unknown",
                has_free_tier=None,
                jobs=jobs_list,
                input_types=["text"],
                output_types=["text"],
                pros=[],
                cons=[],
                prompt_style=PromptStyleSchema().model_dump(),
                sources=[],
                review_flags=[],
            )

            db.add(tool)
            db.commit()
            stats["created"] += 1
            logger.info("Created DRAFT tool '%s' (%s).", name, domain)

    finally:
        if own_db:
            db.close()

    print_summary_table(stats)
    return stats


def print_summary_table(stats: dict[str, Any]) -> None:
    """Print an attractive summary table to stdout."""
    total = stats.get("total", 0)
    created = stats.get("created", 0)
    skipped = stats.get("skipped", 0)
    errors = stats.get("errors", [])
    err_count = len(errors)

    print("\n" + "=" * 52)
    print("       PATHWISE CATALOG V3 SEED SUMMARY")
    print("=" * 52)
    print(f" Total Rows Evaluated  : {total:>5}")
    print(f" DRAFT Tools Created    : {created:>5}")
    print(f" Existing Tools Skipped : {skipped:>5}")
    print(f" Invalid / Errors       : {err_count:>5}")
    print("-" * 52)
    if errors:
        print("\nErrors encountered:")
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}")
    print("=" * 52 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed draft tools from CSV into the Pathwise catalog (Catalog v3).")
    parser.add_argument(
        "--csv",
        type=str,
        default="tools.csv",
        help="Path to CSV file (defaults to tools.csv in current directory)",
    )

    args = parser.parse_args()

    # Resolve relative to repo root if not found directly
    csv_path = Path(args.csv)
    if not csv_path.exists():
        repo_root_csv = Path(__file__).resolve().parent.parent.parent.parent / "tools.csv"
        if repo_root_csv.exists():
            csv_path = repo_root_csv
        else:
            backend_csv = Path(__file__).resolve().parent.parent.parent / "tools.csv"
            if backend_csv.exists():
                csv_path = backend_csv

    try:
        seed_tools(str(csv_path))
    except Exception as e:
        logger.error("Seeding failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

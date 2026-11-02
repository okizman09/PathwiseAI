"""CLI script to import researched Catalog v3 tool cards from JSON.

Usage:
    python -m app.scripts.import_cards cards.json [--expect tools.csv]
"""
import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from app.db import SessionLocal
from app.schemas.card_import import CardImport
from app.services.importer import CardImporterService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_expected_tools(expect_csv_path: str) -> list[str]:
    """Load tool names from seed CSV file."""
    path = Path(expect_csv_path)
    if not path.exists():
        logger.warning("Expected CSV file not found: %s", expect_csv_path)
        return []

    names = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("name") or "").strip()
            if name:
                names.append(name)
    return names


async def run_import(cards_path: str, expect_csv_path: str | None = None) -> int:
    path = Path(cards_path)
    if not path.exists():
        logger.error("Cards JSON file not found: %s", cards_path)
        return 1

    try:
        with open(path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        logger.error("Failed to read JSON from %s: %e", cards_path, e)
        return 1

    # Extract list of card dictionaries
    card_items = raw_data.get("cards", raw_data) if isinstance(raw_data, dict) else raw_data
    if not isinstance(card_items, list):
        logger.error("Cards JSON must contain a list of objects or a {'cards': [...]} object.")
        return 1

    valid_cards: list[CardImport] = []
    rejected_count = 0

    print(f"\nValidating {len(card_items)} cards from {cards_path}...")
    for idx, item in enumerate(card_items, start=1):
        try:
            card = CardImport(**item)
            valid_cards.append(card)
        except ValidationError as ve:
            name = item.get("name", f"Item #{idx}")
            logger.error("Validation error for %s: %s", name, ve)
            rejected_count += 1
        except Exception as e:
            name = item.get("name", f"Item #{idx}")
            logger.error("Unexpected error parsing %s: %s", name, e)
            rejected_count += 1

    expected_names = load_expected_tools(expect_csv_path) if expect_csv_path else None

    print(f"Importing {len(valid_cards)} validated cards into database...")
    db = SessionLocal()
    try:
        response = await CardImporterService.import_batch(
            db=db,
            cards=valid_cards,
            expected_tool_names=expected_names,
        )
        response.rejected += rejected_count
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"Created:  {response.created}")
    print(f"Updated:  {response.updated}")
    print(f"Rejected: {response.rejected}")

    if response.missing_tools:
        print(f"\nMissing Tools from Expected List ({len(response.missing_tools)}):")
        for mt in response.missing_tools:
            print(f"  - {mt}")

    print("\nPer-Card Results:")
    for res in response.results:
        status_symbol = "OK" if res.status in ("created", "updated") else "FAIL"
        print(f"  [{status_symbol}] {res.name} ({res.status.upper()}) [ID: {res.tool_id}]")
        if res.flags:
            for flag in res.flags:
                print(f"      flag: {flag}")
        if res.error:
            print(f"      error: {res.error}")

    print("=" * 60 + "\n")
    return 0 if response.rejected == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Import Catalog v3 researched tool cards.")
    parser.add_argument("cards_file", help="Path to cards.json")
    parser.add_argument("--expect", dest="expect_csv", default=None, help="Path to expected tools CSV")
    args = parser.parse_args()

    exit_code = asyncio.run(run_import(args.cards_file, args.expect_csv))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

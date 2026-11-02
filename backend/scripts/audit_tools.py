"""Catalog audit (batch follow-up 4): missing fields per tool, read-only.

YOU run this yourself against your database (backend/.env). It prints
issue counts plus one line per tool that has issues:

    cd backend && python scripts/audit_tools.py

`*PICK` marks Pathwise picks: visible picks should have no issues.
Fix mapping: no-tagline -> app/scripts/populate_tool_taglines.py,
no-logo/no-og-image -> scripts/backfill_logos.py, pricing/link issues ->
the research/recheck flow per tool.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models.tool import Tool  # noqa: E402
from app.services.tool_audit import ISSUE_LABELS, ISSUE_ORDER, audit_tool  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        tools = db.query(Tool).order_by(Tool.id).all()
        rows = [(tool, audit_tool(tool)) for tool in tools]
        counts: Counter[str] = Counter()
        for _, issues in rows:
            counts.update(issues)

        with_issues = sum(1 for _, issues in rows if issues)
        print(f"Tool audit: {len(tools)} tools, {with_issues} with issues")

        print("\nIssue counts:")
        for code in ISSUE_ORDER:
            if counts.get(code):
                print(f"  {code:22s} {counts[code]:3d}  {ISSUE_LABELS[code]}")

        print("\nPer-tool issues:")
        for tool, issues in rows:
            if not issues:
                continue
            pick = " *PICK" if tool.is_pick else ""
            eco = f" [{tool.ecosystem}]" if tool.ecosystem else ""
            print(f"  [{tool.id}] {tool.name}{eco}{pick}: {', '.join(issues)}")

        clean = len(tools) - with_issues
        print(f"\n{clean} tools clean.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

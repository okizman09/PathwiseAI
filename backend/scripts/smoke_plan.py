"""Planner smoke test (hackathon T7): 8 fixed goals through the real planner.

YOU run this yourself with your key in backend/.env. It makes real Meta API
calls (2 per goal, several minutes total) and writes 8 workflows to the
configured database under a dedicated smoke user:
    cd backend && python scripts/smoke_plan.py

Prints a pass/fail table using the shared checks in app.services.planner.checks.
"""
import asyncio
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.errors import UserFacingError  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.profile import Profile  # noqa: E402
from app.models.tool import Tool  # noqa: E402
from app.schemas.brief import ProductBrief  # noqa: E402
from app.services.plan import generate_workflow_plan  # noqa: E402
from app.services.planner.checks import check_plan  # noqa: E402

SMOKE_USER_ID = "smoke-t7"

# Goal 1 uses budget "low" (demo-realistic and Meta-eligible): Meta cards are
# honestly priced "paid", so a "free_only" brief structurally excludes them.
GOALS = [
    {"goal": "I want a tool that turns my voice notes into structured orders.",
     "domains": ["audio", "software"], "budget": "low",
     "require_transcribe_step": True, "require_meta_card": True},
    {"goal": "Build a landing page for my new product and deploy it.",
     "domains": ["builders", "deploy_backend"], "budget": "flexible"},
    {"goal": "I want to build a small app that stores customer records, with login.",
     "domains": ["software", "builders"], "budget": "flexible"},
    {"goal": "Summarize 20 PDF reports and extract the key figures into a table.",
     "domains": ["research", "software"], "budget": "flexible"},
    {"goal": "Turn a screenshot of a design into a React component.",
     "domains": ["software", "design"], "budget": "flexible"},
    {"goal": "Make a set of promo images for my Instagram.",
     "domains": ["design"], "budget": "flexible"},
    {"goal": "Add an AI assistant to my existing Node.js app using Meta's models.",
     "domains": ["software"], "budget": "flexible",
     "require_meta_card": True},
    {"goal": "Transcribe a recorded interview and write a summary.",
     "domains": ["audio", "research"], "budget": "flexible",
     "require_transcribe_step": True},
]


def make_brief(spec: dict) -> ProductBrief:
    return ProductBrief(
        what_being_made=spec["goal"],
        purpose=spec["goal"],
        target_audience="General builders",
        constraints=[],
        must_haves=[],
        nice_to_haves=[],
        assumptions=[],
        skill_level="intermediate",
        budget_preference=spec["budget"],
        needs_commercial_use="unknown",
        detected_domains=spec["domains"],
    )


def safe_error(exc: Exception) -> str:
    if isinstance(exc, UserFacingError):
        return f"{exc.code}: {exc.message}"
    return type(exc).__name__


async def main() -> int:
    db = SessionLocal()
    try:
        user = db.query(Profile).filter(Profile.id == SMOKE_USER_ID).first()
        if user is None:
            user = Profile(id=SMOKE_USER_ID, email="smoke-t7@test.local", role="user")
            db.add(user)
            db.commit()

        known_model_ids = {
            row[0] for row in db.query(Tool.model_id).filter(Tool.model_id.isnot(None)).all()
        }
        known_tool_ids = {row[0] for row in db.query(Tool.id).all()}
        print(f"catalog: {len(known_tool_ids)} tools, {len(known_model_ids)} model IDs")

        results = []
        for idx, spec in enumerate(GOALS, start=1):
            print(f"[{idx}/8] {spec['goal']}", flush=True)
            started = time.time()
            try:
                plan = await generate_workflow_plan(db, user, make_brief(spec))
                failures = check_plan(
                    plan,
                    known_model_ids=known_model_ids,
                    known_tool_ids=known_tool_ids,
                    require_transcribe_step=spec.get("require_transcribe_step", False),
                    require_meta_card=spec.get("require_meta_card", False),
                )
                results.append({
                    "goal": spec["goal"], "passed": not failures,
                    "failures": failures, "steps": len(plan.steps),
                    "workflow_id": plan.id, "secs": time.time() - started,
                })
            except Exception as exc:  # noqa: BLE001 - smoke must not stop at one goal
                db.rollback()  # keep the shared session usable for later goals
                if not isinstance(exc, UserFacingError):
                    traceback.print_exc()
                results.append({
                    "goal": spec["goal"], "passed": False,
                    "failures": [f"EXCEPTION {safe_error(exc)}"],
                    "steps": 0, "workflow_id": None, "secs": time.time() - started,
                })

        print("\n#  result  steps  secs  workflow  goal")
        passed = 0
        for i, r in enumerate(results, start=1):
            mark = "PASS" if r["passed"] else "FAIL"
            passed += r["passed"]
            wid = r["workflow_id"] if r["workflow_id"] is not None else "-"
            print(f"{i}  {mark}  {r['steps']:>5}  {r['secs']:>4.0f}  {wid:>8}  {r['goal'][:60]}")
        print(f"\n{passed}/{len(results)} goals passed")
        for i, r in enumerate(results, start=1):
            if not r["passed"]:
                print(f"\n--- goal {i} failures ---")
                for f in r["failures"]:
                    print(f"  - {f}")
        print("\nWorkflows saved under user 'smoke-t7' (delete to clean up).")
        return 0 if passed == len(results) else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

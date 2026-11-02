"""Shared plan-quality checks for the planner smoke test (hackathon T7).

Used by backend/scripts/smoke_plan.py (real API) and tests/test_plan_checks.py
(fake LLM) so both apply identical rules.
"""
import re

from app.schemas.workflow import WorkflowResponse

MODEL_ID_RE = re.compile(r"\bmuse-[A-Za-z0-9_.-]+|\bsam-[A-Za-z0-9_.-]+")

_STEP_TEXT_FIELDS = ("prompt", "why_step", "why_tool", "learn_note", "technique")


def find_model_ids(text: str | None) -> set[str]:
    """All muse-/sam- tokens in text, trailing punctuation stripped."""
    if not text:
        return set()
    return {m.group(0).rstrip(".,;:!?\"')]") for m in MODEL_ID_RE.finditer(text)}


def check_plan(
    plan: WorkflowResponse,
    *,
    known_model_ids: set[str],
    known_tool_ids: set[int],
    require_transcribe_step: bool = False,
    require_meta_card: bool = False,
) -> list[str]:
    """Apply smoke checks to a plan. Returns failure messages (empty = pass)."""
    failures: list[str] = []
    steps = plan.steps

    if not 1 <= len(steps) <= 6:
        failures.append(f"expected 1-6 steps, got {len(steps)}")

    for step in steps:
        n = step.step_number
        tool = step.primary_tool
        if step.kind != "tool" or tool is None or tool.id not in known_tool_ids:
            failures.append(f"step {n}: no catalog tool")
        if step.content_type == "steps":
            actions = [a for a in (step.action_steps or []) if a and a.strip()]
            if not actions:
                failures.append(f"step {n}: empty action_steps")
        elif not (step.prompt or "").strip():
            failures.append(f"step {n}: empty prompt")

    jobs = [s.job for s in steps]
    dupes = sorted({j for j in jobs if jobs.count(j) > 1})
    if dupes:
        failures.append(f"duplicate step job(s): {', '.join(dupes)}")

    for step in steps:
        found: set[str] = set()
        for field in _STEP_TEXT_FIELDS:
            found |= find_model_ids(getattr(step, field, None))
        for item in step.action_steps or []:
            found |= find_model_ids(item)
        unknown = sorted(found - known_model_ids)
        if unknown:
            failures.append(
                f"step {step.step_number}: model ID(s) outside catalog: {', '.join(unknown)}"
            )

    if require_transcribe_step and not any(s.job == "transcribe_audio" for s in steps):
        failures.append("missing required transcribe_audio step")
    if require_meta_card and not any(
        s.primary_tool is not None and s.primary_tool.ecosystem == "meta" for s in steps
    ):
        failures.append("missing required Meta card")

    return failures

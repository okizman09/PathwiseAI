"""Live step execution (T9): run a prompt step on a verified text model.

Eligibility is strict: the step's tool must be verified, kind=runnable, carry
a model_id, and have no non-text jobs. The model always comes from the catalog
card — never from the request.
"""

import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import UserFacingError
from app.models.step_run import StepRun
from app.models.workflow import WorkflowStep as DBWorkflowStep
from app.services.llm import generate_text

# Jobs whose inputs/outputs are not plain text: tools carrying any of these
# cannot be executed through the text runner.
NON_TEXT_RUN_JOBS = frozenset(
    {
        "transcribe_audio",
        "generate_voiceover",
        "generate_music",
        "separate_stems",
        "generate_image",
        "edit_image",
        "generate_video_clips",
        "edit_video",
        "make_avatar_video",
        "repurpose_clips",
    }
)


def is_text_runnable(tool: Any) -> bool:
    """True when a catalog tool (DB row) can back a live text run."""
    if tool is None:
        return False
    if getattr(tool, "status", None) != "verified":
        return False
    if getattr(tool, "kind", None) != "runnable":
        return False
    if not getattr(tool, "model_id", None):
        return False
    jobs = set(getattr(tool, "jobs", None) or [])
    return not (jobs & NON_TEXT_RUN_JOBS)


def resolve_run_prompt(db_step: DBWorkflowStep, prompt_override: str | None) -> str:
    """Pick the prompt to execute: override wins, else the saved step prompt.

    Only prompt-type steps with a non-empty prompt can run.
    """
    if (db_step.content_type or "prompt") != "prompt":
        raise ValueError("Only prompt steps can be run live.")
    prompt = (prompt_override or "").strip() or (db_step.prompt or "").strip()
    if not prompt:
        raise ValueError("Step has no prompt to run.")
    if len(prompt) > settings.RUN_MAX_PROMPT_CHARS:
        raise ValueError(f"Prompt exceeds {settings.RUN_MAX_PROMPT_CHARS} characters.")
    return prompt


async def run_text_step(
    db: Session,
    user_id: str,
    db_step: DBWorkflowStep,
    tool: Any,
    prompt_override: str | None,
) -> StepRun:
    """Execute the step prompt on the tool's catalog model and persist the run.

    Raises ValueError for ineligible steps/prompts and UserFacingError (after
    persisting a failed run) for provider failures.
    """
    if not is_text_runnable(tool):
        raise ValueError("Step tool cannot be run live.")
    prompt = resolve_run_prompt(db_step, prompt_override)
    model_id: str = tool.model_id

    started = time.perf_counter()
    try:
        result = await generate_text(
            system=(
                "You are helping the user complete one step of their creation plan. "
                "Follow the instruction and return only the result."
            ),
            user=prompt,
            model=model_id,
            max_output_tokens=settings.RUN_MAX_OUTPUT_TOKENS,
            timeout=float(settings.RUN_TIMEOUT_SECONDS),
        )
    except UserFacingError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        run = StepRun(
            step_id=db_step.id,
            user_id=user_id,
            model_id=model_id,
            prompt=prompt,
            output_text=None,
            status="failed",
            error_code=exc.code,
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    run = StepRun(
        step_id=db_step.id,
        user_id=user_id,
        model_id=model_id,
        prompt=prompt,
        output_text=result.text,
        status="completed",
        error_code=None,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=latency_ms,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

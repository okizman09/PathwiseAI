
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_beta_access, require_verified_user
from app.core.errors import UserFacingError, log_internal_error
from app.core.rate_limit import rate_limit_dependency
from app.core.signing import create_click_ref
from app.db import get_db
from app.models.event import Event
from app.models.profile import Profile
from app.models.step_feedback import StepFeedback
from app.models.workflow import Workflow as DBWorkflow
from app.models.workflow import WorkflowStep as DBWorkflowStep
from app.schemas.brief import ProductBrief
from app.schemas.workflow import (
    OpenLinkRequest,
    OpenLinkResponse,
    StepActionResponse,
    StepFeedbackCreate,
    StepFeedbackResponse,
    StepFinishRequest,
    StepRegenerateRequest,
    StepRunRequest,
    StepRunResponse,
    StepSwitchToolRequest,
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStep,
)
from app.services import catalog as catalog_service
from app.services import plan as plan_service
from app.services import prompts as prompts_service
from app.services import run as run_service
from app.services.plan import JobPlanningItem
from app.services.planner.scoring import shortlist_and_score
from app.services.quota import quota

router = APIRouter(tags=["workflows"], dependencies=[Depends(require_beta_access)])

class WorkflowPatchRequest(BaseModel):
    title: str | None = None
    archive: bool | None = None

class WorkflowListResponse(BaseModel):
    id: int
    title: str
    created_at: str

def hydrate_db_step(
    db: Session,
    s: DBWorkflowStep,
    brief: ProductBrief | None = None,
    tool_map: dict | None = None,
) -> WorkflowStep:
    def _lookup(tool_id: int):
        if tool_map is not None:
            return tool_map.get(tool_id)
        return catalog_service.get_public_tool(db, tool_id)

    primary_tool = None
    primary_db_tool = None
    free_note = None
    step_warnings = []
    if s.primary_tool_id:
        primary_db_tool = _lookup(s.primary_tool_id)
        if primary_db_tool:
            primary_tool = plan_service.build_short_card(primary_db_tool)
            if brief:
                free_note, step_warnings = plan_service.compute_free_tier_note(primary_db_tool, brief)

    alts = []
    for alt_id in (s.alternative_tool_ids or []):
        t = _lookup(alt_id)
        if t:
            alts.append(plan_service.build_short_card(t))

    if not primary_tool:
        free_note = (
            "No free option exists yet in the catalog."
            if (brief and brief.budget_preference == "free_only")
            else "No verified tool option exists yet in the catalog."
        )

    return WorkflowStep(
        step_id=f"step-{s.position}",
        step_number=s.position,
        kind=s.kind or "tool",
        job=s.job or "",
        why_step=s.why_step or "",
        primary_tool=primary_tool,
        alternatives=alts,
        prompt=s.prompt,
        content_type=s.content_type or "prompt",
        action_steps=s.action_steps or [],
        technique=s.technique,
        output_expected=s.output_expected,
        why_tool=s.why_tool,
        learn_note=s.learn_note,
        status=s.status or "pending",
        handoff_note=s.handoff_note,
        prompt_version=s.prompt_version,
        free_tier_note=free_note,
        warnings=step_warnings,
        can_run=run_service.is_text_runnable(primary_db_tool)
        and (s.content_type or "prompt") == "prompt",
    )

def persist_step(db: Session, db_step: DBWorkflowStep, schema_step: WorkflowStep):
    db_step.primary_tool_id = schema_step.primary_tool.id if schema_step.primary_tool else None
    db_step.alternative_tool_ids = [alt.id for alt in schema_step.alternatives]
    db_step.prompt = schema_step.prompt
    db_step.content_type = schema_step.content_type
    db_step.action_steps = schema_step.action_steps
    db_step.technique = schema_step.technique
    db_step.status = schema_step.status
    db_step.handoff_note = schema_step.handoff_note
    db.commit()


def get_workflow_and_step(db: Session, user: Profile, wf_id: int, step_id: str):
    workflow = db.query(DBWorkflow).filter_by(id=wf_id, user_id=user.id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        if str(step_id).startswith("step-"):
            pos = int(step_id.split("-")[1])
            db_step = db.query(DBWorkflowStep).filter_by(workflow_id=workflow.id, position=pos).first()
        else:
            db_step = db.query(DBWorkflowStep).filter_by(workflow_id=workflow.id, id=int(step_id)).first()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid step ID format")

    if not db_step:
        raise HTTPException(status_code=404, detail="Step not found")

    return workflow, db_step


@router.post(
    "/workflow",
    response_model=WorkflowResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
@router.post(
    "/workflows",
    response_model=WorkflowResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def generate_workflow(
    request: WorkflowRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    """Step 6: Generate variable-step plan (1-6 steps) and persist it."""
    try:
        quota.reserve(db, current_user, "workflow")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "workflow.reserve")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    try:
        wf_response = await plan_service.generate_workflow_plan(
            db=db,
            user=current_user,
            brief=request.brief,
        )

        # Emit event
        evt = Event(user_id=current_user.id, kind="workflow_created", workflow_id=wf_response.id)
        db.add(evt)
        db.commit()

        return wf_response
    except ValueError as ve:
        quota.refund(db, current_user, "workflow")
        log_internal_error(ve, "workflow.generate.value_error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate workflow from the provided brief.",
        )
    except Exception as e:
        quota.refund(db, current_user, "workflow")
        log_internal_error(e, "workflow.generate")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Something went wrong. Please try again.",
        )

@router.get("/workflows", response_model=list[WorkflowListResponse])
def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    workflows = (
        db.query(DBWorkflow)
        .filter(DBWorkflow.user_id == current_user.id)
        .filter(DBWorkflow.archived_at.is_(None))
        .order_by(DBWorkflow.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        WorkflowListResponse(
            id=w.id,
            title=w.title,
            created_at=w.created_at.isoformat() if w.created_at else "",
        )
        for w in workflows
    ]


@router.get("/workflows/{id}", response_model=WorkflowResponse)
def get_workflow(
    id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    workflow = (
        db.query(DBWorkflow)
        .filter(DBWorkflow.id == id, DBWorkflow.user_id == current_user.id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    steps = (
        db.query(DBWorkflowStep)
        .filter(DBWorkflowStep.workflow_id == workflow.id)
        .order_by(DBWorkflowStep.position.asc())
        .all()
    )

    brief = ProductBrief.model_validate(workflow.brief)
    wanted_ids = {s.primary_tool_id for s in steps if s.primary_tool_id}
    for s in steps:
        wanted_ids.update(s.alternative_tool_ids or [])
    tool_map = catalog_service.get_public_tools_map(db, wanted_ids)
    schema_steps = [hydrate_db_step(db, s, brief, tool_map) for s in steps]
    cost_summary = plan_service.compute_cost_summary(schema_steps, brief)

    return WorkflowResponse(
        id=workflow.id,
        title=workflow.title,
        brief=brief,
        cost_summary=cost_summary,
        steps=schema_steps,
        created_at=workflow.created_at.isoformat() if workflow.created_at else "",
    )


@router.patch("/workflows/{id}", response_model=WorkflowResponse)
def patch_workflow(
    id: int,
    request: WorkflowPatchRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    from datetime import datetime

    workflow = (
        db.query(DBWorkflow)
        .filter(DBWorkflow.id == id, DBWorkflow.user_id == current_user.id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    if request.title is not None:
        workflow.title = request.title

    if request.archive is not None:
        if request.archive:
            workflow.archived_at = datetime.now(UTC)
        else:
            workflow.archived_at = None

    db.commit()
    db.refresh(workflow)

    return get_workflow(id=workflow.id, db=db, current_user=current_user)


@router.delete("/workflows/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    workflow = (
        db.query(DBWorkflow)
        .filter(DBWorkflow.id == id, DBWorkflow.user_id == current_user.id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    db.delete(workflow)
    db.commit()


@router.post(
    "/workflows/{id}/steps/{step_id}/regenerate",
    response_model=StepActionResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def step_regenerate(
    id: int,
    step_id: str,
    req: StepRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    workflow, db_step = get_workflow_and_step(db, current_user, id, step_id)

    try:
        quota.reserve(db, current_user, "step_action")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "step_regenerate.reserve")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    try:
        schema_step = hydrate_db_step(db, db_step)
        brief = ProductBrief.model_validate(workflow.brief)

        updated_step = await prompts_service.regenerate_step_prompt(
            step=schema_step,
            feedback=req.feedback,
            brief=brief,
        )
        db_step.prompt_version += 1
        persist_step(db, db_step, updated_step)

        return StepActionResponse(
            workflow_id=str(workflow.id),
            step=updated_step,
            action="regenerate",
            message="Prompt regenerated."
        )
    except ValueError as ve:
        quota.refund(db, current_user, "step_action")
        log_internal_error(ve, "step_regenerate.value_error")
        raise HTTPException(status_code=400, detail="Unable to regenerate prompt.")
    except Exception as e:
        quota.refund(db, current_user, "step_action")
        log_internal_error(e, "step_regenerate")
        raise HTTPException(status_code=502, detail="Something went wrong. Please try again.")


@router.post(
    "/workflows/{id}/steps/{step_id}/run",
    response_model=StepRunResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def step_run(
    id: int,
    step_id: str,
    req: StepRunRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    workflow, db_step = get_workflow_and_step(db, current_user, id, step_id)

    try:
        quota.reserve(db, current_user, "step_run")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "step_run.reserve")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    try:
        tool = (
            catalog_service.get_public_tool(db, db_step.primary_tool_id)
            if db_step.primary_tool_id
            else None
        )
        run = await run_service.run_text_step(db, current_user.id, db_step, tool, req.prompt)
        return StepRunResponse(
            run_id=run.id,
            step_id=f"step-{db_step.position}",
            model_id=run.model_id,
            status=run.status,
            output_text=run.output_text or "",
            error_code=run.error_code,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            latency_ms=run.latency_ms,
        )
    except ValueError as ve:
        quota.refund(db, current_user, "step_run")
        raise HTTPException(status_code=400, detail=str(ve) or "Step cannot be run live.")
    except UserFacingError:
        quota.refund(db, current_user, "step_run")
        raise
    except Exception as e:
        quota.refund(db, current_user, "step_run")
        log_internal_error(e, "step_run")
        raise HTTPException(status_code=502, detail="Something went wrong. Please try again.")


@router.post(
    "/workflows/{id}/steps/{step_id}/switch-tool",
    response_model=StepActionResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def step_switch_tool(
    id: int,
    step_id: str,
    req: StepSwitchToolRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    workflow, db_step = get_workflow_and_step(db, current_user, id, step_id)

    # 9. Verify tool eligibility: must be in alternatives OR shortlisted by stored job metadata
    allowed_alt_ids = set(db_step.alternative_tool_ids or [])
    brief = ProductBrief.model_validate(workflow.brief)

    if req.tool_id not in allowed_alt_ids:
        tools = catalog_service.list_public_tools(db)
        job_item = JobPlanningItem(
            step_number=db_step.position,
            job=db_step.job,
            job_tags=db_step.job_tags or [],
            input_types=db_step.input_types or [],
            output_types=db_step.output_types or [],
            output_expected=db_step.output_expected or "",
        )
        candidates = shortlist_and_score(tools, job_item, [], brief)
        candidate_ids = {c.id for c in candidates}
        if req.tool_id not in candidate_ids:
            raise HTTPException(
                status_code=400,
                detail="Tool is not allowed for this step. It must be in alternatives or match the step requirements.",
            )

    try:
        quota.reserve(db, current_user, "step_action")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "step_switch_tool.reserve")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    try:
        schema_step = hydrate_db_step(db, db_step)

        updated_step = await prompts_service.switch_step_tool(
            db=db,
            step=schema_step,
            new_tool_id=req.tool_id,
            brief=brief,
        )

        persist_step(db, db_step, updated_step)

        return StepActionResponse(
            workflow_id=str(workflow.id),
            step=updated_step,
            action="switch_tool",
            message=f"Switched tool to {updated_step.primary_tool.name}."
        )
    except ValueError as ve:
        quota.refund(db, current_user, "step_action")
        log_internal_error(ve, "step_switch_tool.value_error")
        raise HTTPException(status_code=400, detail="Failed to switch tool.")
    except Exception as e:
        quota.refund(db, current_user, "step_action")
        log_internal_error(e, "step_switch_tool")
        raise HTTPException(status_code=502, detail="Something went wrong. Please try again.")


@router.post(
    "/workflows/{id}/steps/{step_id}/finish",
    response_model=StepActionResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def step_finish(
    id: int,
    step_id: str,
    req: StepFinishRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    workflow, db_step = get_workflow_and_step(db, current_user, id, step_id)

    try:
        quota.reserve(db, current_user, "step_action")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "step_finish.reserve")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    try:
        schema_step = hydrate_db_step(db, db_step)
        brief = ProductBrief.model_validate(workflow.brief)

        # 5. Atomicity: Call LLM for next step rewrite FIRST
        next_db_step = db.query(DBWorkflowStep).filter_by(
            workflow_id=workflow.id,
            position=db_step.position + 1
        ).first()

        next_step_schema = None
        if next_db_step and next_db_step.kind != "no_tool":
            next_schema = hydrate_db_step(db, next_db_step)
            next_step_schema = await prompts_service.rewrite_next_step_prompt(
                next_step=next_schema,
                current_step=schema_step,
                note=req.note,
                brief=brief
            )

        # Only after LLM succeeds, write both current step and next step in a single transaction
        schema_step.handoff_note = req.note
        schema_step.status = "done"
        db_step.status = "done"
        db_step.handoff_note = req.note

        if next_step_schema and next_db_step:
            next_db_step.prompt = next_step_schema.prompt
            next_db_step.content_type = next_step_schema.content_type
            next_db_step.action_steps = next_step_schema.action_steps
            next_db_step.technique = next_step_schema.technique
            next_db_step.prompt_version += 1

        # Record step feedback if provided (Catalog v3, Slice C7)
        if req.feedback_result:
            fb = (
                db.query(StepFeedback)
                .filter(StepFeedback.step_id == db_step.id, StepFeedback.user_id == current_user.id)
                .first()
            )
            if fb:
                fb.result = req.feedback_result
                fb.note = req.note.strip() if req.note else None
                fb.tool_id = db_step.primary_tool_id
            else:
                fb = StepFeedback(
                    step_id=db_step.id,
                    workflow_id=workflow.id,
                    user_id=current_user.id,
                    tool_id=db_step.primary_tool_id,
                    result=req.feedback_result,
                    note=req.note.strip() if req.note else None,
                )
                db.add(fb)

        db.commit()

        return StepActionResponse(
            workflow_id=str(workflow.id),
            step=schema_step,
            next_step=next_step_schema,
            action="finish",
            message="Step finished."
        )
    except Exception as e:
        db.rollback()
        quota.refund(db, current_user, "step_action")
        log_internal_error(e, "step_finish")
        raise HTTPException(status_code=502, detail="Something went wrong. Please try again.")


@router.post(
    "/workflows/{id}/steps/{step_id}/feedback",
    response_model=StepFeedbackResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
def submit_step_feedback(
    id: int,
    step_id: str,
    req: StepFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    """Store or update feedback on whether this workflow step worked (Slice C7)."""
    workflow, db_step = get_workflow_and_step(db, current_user, id, step_id)

    fb = (
        db.query(StepFeedback)
        .filter(StepFeedback.step_id == db_step.id, StepFeedback.user_id == current_user.id)
        .first()
    )
    if fb:
        fb.result = req.result
        fb.note = req.note.strip() if req.note else None
        fb.tool_id = db_step.primary_tool_id
    else:
        fb = StepFeedback(
            step_id=db_step.id,
            workflow_id=workflow.id,
            user_id=current_user.id,
            tool_id=db_step.primary_tool_id,
            result=req.result,
            note=req.note.strip() if req.note else None,
        )
        db.add(fb)

    db.commit()
    db.refresh(fb)

    return StepFeedbackResponse(
        id=fb.id,
        step_id=fb.step_id,
        workflow_id=fb.workflow_id,
        tool_id=fb.tool_id,
        result=fb.result,
        note=fb.note,
        created_at=fb.created_at.isoformat() if fb.created_at else "",
    )


@router.post(
    "/workflows/{id}/steps/{step_id}/recheck",
    response_model=StepActionResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def step_recheck(
    id: int,
    step_id: str,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    """Only for no_tool steps. Re-run tool matching."""
    workflow, db_step = get_workflow_and_step(db, current_user, id, step_id)

    if db_step.kind != "no_tool":
        raise HTTPException(status_code=400, detail="Recheck is only for steps with no tools.")

    try:
        quota.reserve(db, current_user, "step_action")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "step_recheck.reserve")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")

    try:
        brief = ProductBrief.model_validate(workflow.brief)
        tools = catalog_service.list_public_tools(db)

        # 9. Read stored metadata directly from db_step instead of ToolGap
        job_item = JobPlanningItem(
            step_number=db_step.position,
            job=db_step.job,
            job_tags=db_step.job_tags or [],
            input_types=db_step.input_types or [],
            output_types=db_step.output_types or [],
            output_expected=db_step.output_expected or ""
        )

        top_candidates = shortlist_and_score(tools, job_item, [], brief)
        schema_step = hydrate_db_step(db, db_step)

        if not top_candidates:
            return StepActionResponse(
                workflow_id=str(workflow.id),
                step=schema_step,
                action="recheck",
                message="Still no tools found for this job."
            )

        primary_tool = top_candidates[0]
        schema_step.primary_tool = plan_service.build_short_card(primary_tool)
        schema_step.alternatives = [plan_service.build_short_card(t) for t in top_candidates[1:]]
        schema_step.kind = "tool"

        updated_step = await prompts_service.switch_step_tool(
            db=db,
            step=schema_step,
            new_tool_id=primary_tool.id,
            brief=brief,
        )

        updated_step.handoff_note = None
        db_step.kind = "tool"
        persist_step(db, db_step, updated_step)

        # Clean up gap if present
        from app.models.tool_gap import ToolGap
        gap = db.query(ToolGap).filter_by(workflow_id=workflow.id, job=db_step.job).first()
        if gap:
            db.delete(gap)
            db.commit()

        return StepActionResponse(
            workflow_id=str(workflow.id),
            step=updated_step,
            action="recheck",
            message="Tool found! Step updated."
        )
    except Exception as e:
        quota.refund(db, current_user, "step_action")
        log_internal_error(e, "step_recheck")
        raise HTTPException(status_code=502, detail="Something went wrong. Please try again.")


@router.post("/workflows/{id}/steps/{step_id}/open-link", response_model=OpenLinkResponse)
def open_step_link(
    workflow_id: int = Path(..., alias="id"),
    step_id: str = Path(...),
    req: OpenLinkRequest | None = None,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(require_verified_user),
):
    """Generate a signed, short-lived click reference URL to track step tool clicks."""
    workflow, db_step = get_workflow_and_step(db, current_user, workflow_id, step_id)

    target_tool_id = req.tool_id if (req and req.tool_id) else db_step.primary_tool_id
    if not target_tool_id:
        raise HTTPException(status_code=400, detail="Step has no tool to open.")

    allowed_tool_ids = set()
    if db_step.primary_tool_id:
        allowed_tool_ids.add(db_step.primary_tool_id)
    if db_step.alternative_tool_ids:
        allowed_tool_ids.update(db_step.alternative_tool_ids)

    if target_tool_id not in allowed_tool_ids:
        raise HTTPException(
            status_code=400,
            detail="Requested tool is not associated with this step.",
        )

    ref = create_click_ref(
        user_id=current_user.id,
        workflow_id=workflow.id,
        step_id=db_step.id,
        tool_id=target_tool_id,
    )
    return OpenLinkResponse(go_url=f"/go/{target_tool_id}?ref={ref}")


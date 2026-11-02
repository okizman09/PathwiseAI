from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, get_current_user
from app.core.rate_limit import rate_limit_dependency
from app.db import get_db
from app.models.event import Event
from app.models.profile import Profile
from app.models.tool_gap import ToolGap
from app.schemas.events import EventCreateRequest

router = APIRouter(tags=["events"])

@router.post(
    "/events",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit_dependency)],
)
def record_event(
    req: EventCreateRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    from app.models.workflow import Workflow as DBWorkflow
    from app.routers.workflow import get_workflow_and_step

    real_step_id = None
    if req.workflow_id:
        if req.step_id:
            wf, db_step = get_workflow_and_step(db, current_user, req.workflow_id, req.step_id)
            real_step_id = db_step.id
        else:
            wf = db.query(DBWorkflow).filter_by(id=req.workflow_id, user_id=current_user.id).first()
            if not wf:
                raise HTTPException(status_code=404, detail="Workflow not found")
    elif req.step_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    event = Event(
        user_id=current_user.id,
        kind=req.kind,
        workflow_id=req.workflow_id,
        step_id=real_step_id,
    )
    db.add(event)
    db.commit()


@router.get("/admin/metrics", dependencies=[Depends(get_current_admin_user)])
def get_metrics(db: Session = Depends(get_db)):
    """Slice 8: Return basic analytics."""
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    def count_events(kind: str, since: datetime):
        return db.query(func.count(Event.id)).filter(
            Event.kind == kind,
            Event.created_at >= since
        ).scalar()

    def get_tool_opens(since: datetime):
        rows = db.query(Event.tool_id, func.count(Event.id)).filter(
            Event.kind == "tool_opened",
            Event.tool_id.isnot(None),
            Event.created_at >= since
        ).group_by(Event.tool_id).order_by(func.count(Event.id).desc()).all()
        return [{"tool_id": r[0], "count": r[1]} for r in rows]

    def get_top_gaps(since: datetime):
        rows = db.query(ToolGap.job, func.count(ToolGap.id)).filter(
            ToolGap.created_at >= since
        ).group_by(ToolGap.job).order_by(func.count(ToolGap.id).desc()).limit(10).all()
        return [{"job": r[0], "count": r[1]} for r in rows]

    return {
        "7_days": {
            "workflows_created": count_events("workflow_created", seven_days_ago),
            "interviews_completed": count_events("interview_completed", seven_days_ago),
            "prompts_copied": count_events("prompt_copied", seven_days_ago),
            "quota_limit_hits": count_events("quota_limit_hit", seven_days_ago),
            "tools_opened": get_tool_opens(seven_days_ago),
            "top_tool_gaps": get_top_gaps(seven_days_ago),
        },
        "30_days": {
            "workflows_created": count_events("workflow_created", thirty_days_ago),
            "interviews_completed": count_events("interview_completed", thirty_days_ago),
            "prompts_copied": count_events("prompt_copied", thirty_days_ago),
            "quota_limit_hits": count_events("quota_limit_hit", thirty_days_ago),
            "tools_opened": get_tool_opens(thirty_days_ago),
            "top_tool_gaps": get_top_gaps(thirty_days_ago),
        }
    }

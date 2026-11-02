from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limit_dependency
from app.core.signing import decode_click_ref
from app.db import get_db
from app.models.event import Event
from app.models.tool import Tool

router = APIRouter(tags=["go"])


@router.get("/go/{tool_id}", dependencies=[Depends(rate_limit_dependency)])
def redirect_to_tool(
    tool_id: int,
    ref: str | None = Query(None, description="Signed click reference token"),
    db: Session = Depends(get_db),
):
    """Click tracking redirect using verified tool destinations and signed click references."""
    tool = db.query(Tool).filter(
        Tool.id == tool_id,
        Tool.status == "verified",
    ).first()

    if not tool or tool.link_status == "dead":
        raise HTTPException(status_code=404, detail="Tool not found or not available.")

    user_id = None
    workflow_id = None
    step_id = None

    if ref:
        payload = decode_click_ref(ref)
        if payload and payload.get("tool_id") == tool_id:
            user_id = payload.get("user_id")
            workflow_id = payload.get("workflow_id")
            step_id = payload.get("step_id")

    # Record click event
    event = Event(
        user_id=user_id,
        kind="tool_opened",
        tool_id=tool.id,
        workflow_id=workflow_id,
        step_id=step_id,
    )
    db.add(event)
    db.commit()

    target_url = tool.affiliate_url or tool.url
    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)

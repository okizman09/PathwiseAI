"""Landing-page UX feedback: public submit plus admin list/export."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, get_optional_user
from app.core.rate_limit import PersistentRateLimiter, get_client_ip
from app.db import get_db
from app.models.site_feedback import SiteFeedback
from app.schemas.feedback import (
    SiteFeedbackCreate,
    SiteFeedbackResponse,
)
from app.services import feedback as feedback_service
from app.services import notify as notify_service
from app.services.auth.supabase_jwt import verify_supabase_token

router = APIRouter(tags=["feedback"])

# Public form: tighter than the default limiter (spam-prone, unauthenticated).
site_feedback_limiter = PersistentRateLimiter(requests_per_minute=5, daily_cap=20)


async def site_feedback_rate_limit(request: Request, db: Session = Depends(get_db)):
    """Rate-limit feedback submits per user id, else per IP (isolated keys)."""
    key: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ", 1)[1].strip()
        try:
            payload = verify_supabase_token(token)
            sub = payload.get("sub")
            if sub:
                key = f"site-feedback:user:{sub}"
        except Exception:
            pass
    if not key:
        key = f"site-feedback:ip:{get_client_ip(request)}"
    site_feedback_limiter.check(db, key)


@router.post(
    "/feedback/site",
    response_model=SiteFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(site_feedback_rate_limit)],
)
async def submit_site_feedback(
    req: SiteFeedbackCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Submit landing-page UX feedback (public; anonymous allowed)."""
    user = get_optional_user(authorization=request.headers.get("Authorization"), db=db)
    fb = SiteFeedback(
        message=req.message,
        contact=req.contact,
        page=req.page,
        user_id=user.id if user else None,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    background_tasks.add_task(
        notify_service.send_site_feedback_email,
        message=fb.message,
        contact=fb.contact,
        page=fb.page,
        feedback_id=fb.id,
    )
    return SiteFeedbackResponse(
        id=fb.id,
        message=fb.message,
        contact=fb.contact,
        page=fb.page,
        user_id=fb.user_id,
        created_at=fb.created_at,
    )


@router.get(
    "/admin/feedback/site",
    response_model=list[SiteFeedbackResponse],
    dependencies=[Depends(get_current_admin_user)],
)
async def list_site_feedback(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List landing-page feedback, newest first (Admin only)."""
    rows = feedback_service.list_site_feedback(db=db, limit=limit)
    return [
        SiteFeedbackResponse(
            id=fb.id,
            message=fb.message,
            contact=fb.contact,
            page=fb.page,
            user_id=fb.user_id,
            created_at=fb.created_at,
        )
        for fb in rows
    ]


@router.get(
    "/admin/feedback/site/export",
    dependencies=[Depends(get_current_admin_user)],
)
async def export_site_feedback_csv(db: Session = Depends(get_db)):
    """Download all landing-page feedback as CSV (Admin only)."""
    from datetime import UTC, datetime

    csv_text = feedback_service.build_site_feedback_csv(db=db)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="site-feedback-{stamp}.csv"'
        },
    )

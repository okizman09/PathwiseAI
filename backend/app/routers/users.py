import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models.event import Event
from app.models.profile import Profile
from app.models.rate_limit import RateLimitBucket
from app.models.usage import UsageDaily
from app.models.workflow import Workflow, WorkflowStep
from app.schemas.profile import ProfileResponse

logger = logging.getLogger("pathwise.api")

router = APIRouter(tags=["users"])


@router.get("/me", response_model=ProfileResponse)
@router.get("/users/me", response_model=ProfileResponse)
async def get_me(current_user: Profile = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user


@router.delete("/me")
@router.delete("/users/me")
async def delete_me(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete user profile, workflows, steps, events, usage, and auth user."""
    user_id = str(current_user.id)

    # 1. Delete RateLimitBucket entries for this user
    db.query(RateLimitBucket).filter(RateLimitBucket.key == f"user:{user_id}").delete(synchronize_session=False)

    # 2. Delete UsageDaily rows
    db.query(UsageDaily).filter(UsageDaily.user_id == user_id).delete(synchronize_session=False)

    # 3. Delete Events
    db.query(Event).filter(Event.user_id == user_id).delete(synchronize_session=False)

    # 4. Delete Workflow steps and Workflows
    user_workflows = db.query(Workflow.id).filter(Workflow.user_id == user_id).all()
    wf_ids = [w[0] for w in user_workflows]
    if wf_ids:
        db.query(WorkflowStep).filter(WorkflowStep.workflow_id.in_(wf_ids)).delete(synchronize_session=False)
        db.query(Workflow).filter(Workflow.user_id == user_id).delete(synchronize_session=False)

    # 5. Delete Profile
    db.query(Profile).filter(Profile.id == user_id).delete(synchronize_session=False)

    db.commit()

    # 6. Delete Supabase auth user on the server using service role key if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        admin_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_id}"
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.delete(admin_url, headers=headers)
                if res.status_code not in (200, 204, 404):
                    logger.warning(
                        "Supabase auth user deletion returned %d: %s",
                        res.status_code,
                        res.text,
                    )
        except Exception as e:
            logger.warning("Failed to delete Supabase auth user %s: %s", user_id, e)

    return {"status": "deleted", "message": "Account and all associated data have been permanently deleted."}

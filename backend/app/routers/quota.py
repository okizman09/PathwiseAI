
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models.profile import Profile
from app.services.quota.quota import get_usage

router = APIRouter(tags=["quota"])

@router.get("/usage")
def get_all_usage(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns usage and limits for all tracked kinds.
    """
    return {
        "workflow": get_usage(db, current_user, "workflow"),
        "interview_turn": get_usage(db, current_user, "interview_turn"),
        "step_action": get_usage(db, current_user, "step_action"),
        "email_verified": getattr(current_user, "email_verified", False),
    }

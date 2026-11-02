from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_beta_access, require_verified_user
from app.core.errors import log_internal_error
from app.core.rate_limit import rate_limit_dependency
from app.db import get_db
from app.models.event import Event
from app.models.profile import Profile
from app.schemas.brief import InterviewReadyResponse, InterviewRequest, InterviewResponse
from app.services import interview as interview_service
from app.services.quota import quota

router = APIRouter(tags=["interview"], dependencies=[Depends(require_beta_access)])


@router.post(
    "/interview",
    response_model=InterviewResponse,
    dependencies=[Depends(rate_limit_dependency)],
)
async def conduct_interview(
    request: InterviewRequest,
    current_user: Profile = Depends(require_verified_user),
    db: Session = Depends(get_db)
):
    """Conduct interactive interview turn to construct product brief (Step 5)."""
    # 7. Interview pre-check: when an interview starts (no answers yet), check workflow quota
    if not request.answers and current_user.role != "admin":
        usage = quota.get_usage(db=db, user=current_user, kind="workflow")
        if usage["used"] >= usage["limit"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "daily_limit",
                    "kind": "workflow",
                    "limit": usage["limit"],
                    "used": usage["used"],
                    "resets_at": usage["resets_at"],
                },
            )

    # Reserve quota for the interview turn
    try:
        quota.reserve(db=db, user=current_user, kind="interview_turn")
    except HTTPException:
        raise
    except Exception as e:
        log_internal_error(e, "interview.reserve")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong. Please try again.",
        )

    try:
        response = await interview_service.conduct_interview(
            goal=request.goal,
            answers=request.answers,
        )

        # Emit event if completed
        if isinstance(response, InterviewReadyResponse):
            evt = Event(user_id=current_user.id, kind="interview_completed")
            db.add(evt)
            db.commit()

        return response
    except ValueError as ve:
        quota.refund(db=db, user=current_user, kind="interview_turn")
        log_internal_error(ve, "interview.conduct_interview.value_error")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something went wrong. Please try again.",
        )
    except Exception as e:
        quota.refund(db=db, user=current_user, kind="interview_turn")
        log_internal_error(e, "interview.conduct_interview")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Something went wrong. Please try again.",
        )

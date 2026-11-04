from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models.profile import Profile
from app.services.auth.supabase_jwt import verify_supabase_token

# Minimum seconds between last_seen_at writes for a user (perf: avoids a
# write + commit round trip on every authenticated request).
LAST_SEEN_UPDATE_SECONDS = 900


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Profile:
    """Validate Supabase token, retrieve or create the user profile."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split("Bearer ", 1)[1].strip()

    try:
        payload = verify_supabase_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing email.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from sqlalchemy.exc import IntegrityError

    from app.services.auth.supabase_jwt import is_email_verified

    # Upsert the profile handling concurrent creation races
    profile = db.query(Profile).filter(Profile.id == str(user_id)).first()
    if not profile:
        try:
            profile = Profile(
                id=str(user_id),
                email=email,
                role="user"
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
        except IntegrityError:
            db.rollback()
            profile = db.query(Profile).filter(Profile.id == str(user_id)).first()

    # Update last seen at most once per 15 minutes. Nothing reads this
    # field except the profile itself, so throttling is invisible.
    if profile:
        now = datetime.now(UTC)
        last_seen = profile.last_seen_at
        if last_seen is not None and last_seen.tzinfo is None:
            # SQLite returns naive datetimes; interpret as UTC.
            last_seen = last_seen.replace(tzinfo=UTC)
        if last_seen is None or (now - last_seen).total_seconds() > LAST_SEEN_UPDATE_SECONDS:
            profile.last_seen_at = now
            db.commit()

    # Attach verified email indicator (runtime attribute)
    verified = is_email_verified(payload, token)
    setattr(profile, "email_verified", verified)

    return profile


def check_beta_access(user: Profile) -> None:
    """Validate user is on the private beta allowlist or is an admin."""
    if not settings.BETA_ALLOWLIST_ENABLED:
        return
    if user.role == "admin":
        return
    allowed = {
        e.strip().lower()
        for e in settings.BETA_ALLOWED_EMAILS.split(",")
        if e.strip()
    }
    if user.email.lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "not_in_beta",
                "message": "This private beta is currently invite-only. Your account has not been granted access yet.",
            },
        )


def require_beta_access(
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    """Validate that the authenticated user has access to the private beta."""
    check_beta_access(current_user)
    return current_user


def require_verified_user(
    current_user: Profile = Depends(get_current_user),
) -> Profile:
    """Validate that the authenticated user has access to the beta and a verified email address."""
    check_beta_access(current_user)
    if not getattr(current_user, "email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "email_not_verified",
                "message": "Please verify your email first.",
            },
        )
    return current_user

def get_optional_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Profile | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return get_current_user(authorization=authorization, db=db)
    except Exception:
        return None

def get_current_admin_user(
    current_user: Profile = Depends(get_current_user)
) -> Profile:
    """Validate that the requester is an administrator."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden. Administrator privileges required.",
        )
    return current_user

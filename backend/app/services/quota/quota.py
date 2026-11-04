from datetime import UTC, datetime, timedelta
from typing import TypedDict

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.profile import Profile
from app.models.usage import UsageDaily


class QuotaResponse(TypedDict):
    code: str
    kind: str
    limit: int
    used: int
    resets_at: str

class QuotaExceededException(HTTPException):
    def __init__(self, kind: str, limit: int, used: int, resets_at: str):
        super().__init__(
            status_code=429,
            detail={
                "code": "daily_limit",
                "kind": kind,
                "limit": limit,
                "used": used,
                "resets_at": resets_at,
            }
        )

def _get_limit(kind: str) -> int:
    if kind == "workflow":
        return settings.WORKFLOWS_PER_DAY
    if kind == "interview_turn":
        return settings.INTERVIEW_TURNS_PER_DAY
    if kind == "step_action":
        return settings.STEP_ACTIONS_PER_DAY
    if kind == "step_run":
        return settings.RUN_STEPS_PER_DAY
    return 0

def _get_today_utc() -> datetime:
    return datetime.now(UTC).date()

def _get_resets_at() -> str:
    now = datetime.now(UTC)
    tomorrow = now.date() + timedelta(days=1)
    resets = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=UTC)
    return resets.isoformat().replace("+00:00", "Z")

def get_usage(db: Session, user: Profile, kind: str) -> QuotaResponse:
    limit = _get_limit(kind)
    if user.role == "admin":
        return {
            "code": "ok",
            "kind": kind,
            "limit": limit,
            "used": 0,
            "resets_at": _get_resets_at()
        }

    day = _get_today_utc()
    usage = db.query(UsageDaily).filter_by(user_id=user.id, day=day, kind=kind).first()
    used = usage.count if usage else 0

    return {
        "code": "ok",
        "kind": kind,
        "limit": limit,
        "used": used,
        "resets_at": _get_resets_at()
    }

def reserve(db: Session, user: Profile, kind: str) -> None:
    """
    Reserves one unit of quota. If the quota is exceeded, raises QuotaExceededException (HTTP 429).
    Uses dialect-specific ON CONFLICT DO UPDATE for race-safe atomic increment.
    """
    if user.role == "admin":
        return

    limit = _get_limit(kind)
    day = _get_today_utc()

    # We must try an atomic UPSERT.
    # Postgres syntax: INSERT ... ON CONFLICT (...) DO UPDATE SET count = ... WHERE ...
    # SQLite syntax (3.24+): INSERT ... ON CONFLICT (...) DO UPDATE SET count = ... WHERE ...

    dialect = db.bind.dialect.name

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
        stmt = insert(UsageDaily).values(user_id=user.id, day=day, kind=kind, count=1)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_usage_daily_user_day_kind",
            set_={"count": UsageDaily.count + 1},
            where=(UsageDaily.count < limit)
        ).returning(UsageDaily.count)

    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
        # In SQLite, the unique constraint is named, but we index by columns for ON CONFLICT
        stmt = insert(UsageDaily).values(user_id=user.id, day=day, kind=kind, count=1)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "day", "kind"],
            set_={"count": UsageDaily.count + 1},
            where=(UsageDaily.count < limit)
        ).returning(UsageDaily.count)
    else:
        raise NotImplementedError(f"Dialect {dialect} not supported for quota reservation.")

    result = db.execute(stmt).scalar()
    db.commit()

    if result is None:
        # The WHERE count < limit condition caused the update to skip.
        # This means the user is at or over the limit.
        # Let's fetch the actual count to report accurately, though it must be >= limit.
        usage = db.query(UsageDaily).filter_by(user_id=user.id, day=day, kind=kind).first()
        used = usage.count if usage else limit

        evt = Event(user_id=user.id, kind="quota_limit_hit")
        db.add(evt)
        db.commit()

        raise QuotaExceededException(kind=kind, limit=limit, used=used, resets_at=_get_resets_at())

def refund(db: Session, user: Profile, kind: str) -> None:
    """
    Refunds one unit of quota (decrements count if > 0).
    """
    if user.role == "admin":
        return

    day = _get_today_utc()

    # Simple atomic decrement
    db.query(UsageDaily).filter(
        UsageDaily.user_id == user.id,
        UsageDaily.day == day,
        UsageDaily.kind == kind,
        UsageDaily.count > 0
    ).update({"count": UsageDaily.count - 1})
    db.commit()

def _get_global_limit(kind: str) -> int:
    if kind == "step_run":
        return settings.GLOBAL_STEP_RUNS_PER_DAY
    return 0

def get_global_usage(db: Session, kind: str) -> int:
    """Total units consumed by all users today for a quota kind."""
    day = _get_today_utc()
    total = (
        db.query(func.coalesce(func.sum(UsageDaily.count), 0))
        .filter(UsageDaily.day == day, UsageDaily.kind == kind)
        .scalar()
    )
    return int(total or 0)

def check_global_cap(db: Session, kind: str) -> None:
    """Raise 429 when all users combined hit the daily cap (spend guard).

    A non-positive limit disables the cap. Derived from the same usage rows
    as per-user quota, so refunds stay consistent automatically.
    """
    limit = _get_global_limit(kind)
    if limit <= 0:
        return
    used = get_global_usage(db, kind)
    if used >= limit:
        raise QuotaExceededException(kind=kind, limit=limit, used=used, resets_at=_get_resets_at())

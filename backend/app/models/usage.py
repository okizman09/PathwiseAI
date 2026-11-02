"""SQLAlchemy ORM model — usage_daily (per-user per-day quota counters)."""
from sqlalchemy import Column, Date, Integer, String, UniqueConstraint

from app.db import Base


class UsageDaily(Base):
    """One row per (user_id, day, kind). Incremented atomically."""

    __tablename__ = "usage_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)
    kind = Column(String(50), nullable=False)  # "workflow" | "interview_turn" | "step_action"
    count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "day", "kind", name="uq_usage_daily_user_day_kind"),
    )

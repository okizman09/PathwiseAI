"""SQLAlchemy ORM model — rate_limit_buckets (persistent rate limit counters)."""
from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.db import Base


class RateLimitBucket(Base):
    """Persistent sliding-window / fixed-interval rate limit counters."""

    __tablename__ = "rate_limit_buckets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, index=True)
    window_type = Column(String(10), nullable=False)  # "minute" or "day"
    window_start = Column(Integer, nullable=False, index=True)  # Unix epoch start
    count = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("key", "window_type", "window_start", name="uq_rate_limit_key_window"),
    )

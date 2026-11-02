"""SQLAlchemy ORM model — profiles (Supabase auth user mirror)."""
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, func

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Profile(Base):
    """One row per Supabase auth user. id = Supabase auth user UUID."""

    __tablename__ = "profiles"

    id = Column(String(36), primary_key=True)  # UUID from Supabase
    email = Column(String(254), nullable=False, index=True, unique=True)
    role = Column(String(20), nullable=False, default="creator")  # "creator" | "admin"
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

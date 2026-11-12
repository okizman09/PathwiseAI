"""SQLAlchemy ORM model for landing-page UX feedback."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db import Base


class SiteFeedback(Base):
    """General experience feedback from site visitors (may be anonymous)."""

    __tablename__ = "site_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=True, index=True)  # profiles.id when signed in
    page = Column(String(500), nullable=True)  # path the feedback was sent from
    message = Column(Text, nullable=False)
    contact = Column(String(320), nullable=True)  # optional reply-to email
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

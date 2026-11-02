"""SQLAlchemy ORM model — events (analytics: copy, open, interview complete, etc.)."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.db import Base


class Event(Base):
    """Analytics event emitted by user actions."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=True, index=True)  # null for anonymous
    kind = Column(
        String(50), nullable=False, index=True
    )  # "prompt_copied" | "tool_opened" | "interview_completed" | "workflow_created"
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True)
    step_id = Column(Integer, ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True)
    tool_id = Column(Integer, ForeignKey("tools.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

"""SQLAlchemy ORM model for workflow step feedback (Catalog v3, Slice C7)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db import Base


class StepFeedback(Base):
    """Creator feedback on workflow step execution."""

    __tablename__ = "step_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(
        Integer, ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_id = Column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String(36), nullable=False, index=True)
    tool_id = Column(Integer, ForeignKey("tools.id", ondelete="SET NULL"), nullable=True, index=True)
    result = Column(String(20), nullable=False)  # "worked" | "partly" | "didnt"
    note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

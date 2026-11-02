"""SQLAlchemy ORM model — tool_gaps (unmatched jobs logged for catalog growth)."""
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func

from app.db import Base


class ToolGap(Base):
    """Recorded when a workflow step finds no verified tool for a job."""

    __tablename__ = "tool_gaps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(
        Integer, ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )
    job = Column(String(500), nullable=False)
    job_tags = Column(JSON, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

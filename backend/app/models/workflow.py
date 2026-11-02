"""SQLAlchemy ORM models — Workflow and WorkflowStep."""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db import Base


class Workflow(Base):
    """A user's saved creation path."""

    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # profiles.id
    title = Column(String(500), nullable=False, default="Untitled path")
    brief = Column(JSON, nullable=False, default=dict)  # serialised ProductBrief
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)


class WorkflowStep(Base):
    """One step inside a workflow."""

    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(
        Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)  # 1-based ordering
    kind = Column(String(20), nullable=False, default="tool")  # "tool" | "no_tool"
    job = Column(String(500), nullable=False)
    why_step = Column(Text, nullable=True)
    primary_tool_id = Column(Integer, ForeignKey("tools.id"), nullable=True)
    alternative_tool_ids = Column(JSON, nullable=False, default=list)
    prompt = Column(Text, nullable=True)
    technique = Column(Text, nullable=True)
    output_expected = Column(Text, nullable=True)
    why_tool = Column(Text, nullable=True)
    learn_note = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # "pending" | "done"
    handoff_note = Column(Text, nullable=True)
    prompt_version = Column(Integer, nullable=False, default=1)
    job_tags = Column(JSON, nullable=False, default=list)
    input_types = Column(JSON, nullable=False, default=list)
    output_types = Column(JSON, nullable=False, default=list)

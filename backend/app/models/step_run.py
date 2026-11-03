"""SQLAlchemy ORM model — StepRun (one live execution of a workflow step, T9)."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.db import Base


class StepRun(Base):
    """A saved live run of a prompt step against a verified text model."""

    __tablename__ = "step_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(Integer, ForeignKey("workflow_steps.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # profiles.id
    model_id = Column(String(100), nullable=False)
    prompt = Column(Text, nullable=False)
    output_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="completed")  # completed | failed
    error_code = Column(String(50), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

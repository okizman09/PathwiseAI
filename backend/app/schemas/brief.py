"""Pydantic schemas for the interview and product brief.

Previously lived in app.models.brief — moved to app.schemas.brief in Slice 1.
"""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class InterviewAnswer(BaseModel):
    question: str = Field(..., max_length=500)
    answer: str = Field(..., max_length=1500)

    @field_validator("question", "answer")
    def strip_control_chars(cls, v: str) -> str:
        # Strip all control characters except newline and tab
        return re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', v).strip()

class InterviewRequest(BaseModel):
    goal: str = Field(..., min_length=2, max_length=3000, description="The user's high-level goal")
    answers: list[InterviewAnswer] = Field(
        default_factory=list,
        max_length=10,
        description="Previous question and answer pairs from the interview",
    )

    @field_validator("goal")
    def strip_control_chars_goal(cls, v: str) -> str:
        return re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', v).strip()


class ProductBrief(BaseModel):
    what_being_made: str = Field(description="Clear, concise summary of what is being created")
    purpose: str = Field(description="Core purpose and business / creator goal")
    target_audience: str = Field(description="Primary audience or consumers for this creation")
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "Technical or practical constraints that dictate tool selection "
            "(e.g., no-code, budget, tech stack, platform)"
        ),
    )
    must_haves: list[str] = Field(
        default_factory=list,
        description="Essential required features explicitly stated or strictly required",
    )
    nice_to_haves: list[str] = Field(
        default_factory=list,
        description="Optional features or enhancements",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Reasonable default assumptions made without inventing unprompted features",
    )
    skill_level: str = Field(
        default="unknown",
        description="beginner | intermediate | advanced | unknown",
    )
    budget_preference: str = Field(
        default="unknown",
        description="free_only | low | flexible | unknown",
    )
    needs_commercial_use: str = Field(
        default="unknown",
        description="yes | no | unknown",
    )
    detected_domains: list[str] = Field(
        default_factory=list,
        description="Detected creator domains: software, builders, design, video, audio, writing, research, deploy_backend, freelance_ops",
    )
    product_name: str | None = Field(
        default=None,
        description="Product, project, business, or brand name exactly as the user gave it, or null when unknown",
    )


class InterviewQuestionResponse(BaseModel):
    type: Literal["question"] = "question"
    question: str
    options: list[str] = Field(default_factory=list, description="Chip suggestions")
    allow_custom_text: bool = True


class InterviewReadyResponse(BaseModel):
    type: Literal["ready"] = "ready"
    brief: ProductBrief


InterviewResponse = InterviewQuestionResponse | InterviewReadyResponse

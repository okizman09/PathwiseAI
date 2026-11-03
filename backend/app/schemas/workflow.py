"""Pydantic schemas for workflow generation and step actions.

Previously lived in app.models.workflow — moved to app.schemas.workflow in Slice 1.
"""
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.schemas.brief import ProductBrief
from app.schemas.tool import PromptStyleSchema


class CostSummary(BaseModel):
    mode: Literal["free", "may_cost"] = "free"
    estimated_monthly_usd: float | None = 0.0
    notes: list[str] = Field(default_factory=list)
    pricing_complete: bool = True


class ToolShortCard(BaseModel):
    id: int
    name: str
    go_path: str
    category: str = ""
    domain: str | None = None
    ecosystem: str | None = None
    kind: str | None = None
    model_id: str | None = None
    api_snippet: str | None = None
    jobs: list[str] = Field(default_factory=list)
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)
    pricing: str = "freemium"
    pricing_model: str = "freemium"
    has_free_tier: bool | None = None
    free_tier_summary: str | None = None
    free_tier_limits: str | None = None
    starting_price_monthly_usd: float | None = None
    commercial_use_on_free: bool | None = None
    credit_card_required: bool | None = None
    best_for: str = ""
    prompt_style: PromptStyleSchema = Field(default_factory=PromptStyleSchema)
    why_chosen: str | None = None
    logo_url: str | None = None
    is_pick: bool = False
    warnings: list[str] = Field(default_factory=list)


class OpenLinkRequest(BaseModel):
    tool_id: int | None = None


class OpenLinkResponse(BaseModel):
    go_url: str


class WorkflowStep(BaseModel):
    step_id: str = Field(description="Unique identifier for the step e.g. step-1")
    step_number: int = Field(ge=1, le=6, description="Step order from 1 to 6")
    kind: Literal["tool", "no_tool"] = Field(default="tool", description="Step kind")
    job: str = Field(description="The specific single job/task produced in this step")
    why_step: str = Field(description="Why this step is needed (max 2 sentences)")
    primary_tool: ToolShortCard | None = Field(default=None, description="The primary selected verified tool")
    alternatives: list[ToolShortCard] = Field(
        default_factory=list,
        description="1-2 alternative verified tools suitable for this step",
    )
    prompt: str | None = Field(default=None, description="Paste-ready prompt customised for the tool's prompt_style")
    content_type: Literal["prompt", "steps"] = Field(default="prompt", description="prompt for creative jobs, steps for setup/deployment/config jobs")
    action_steps: list[str] = Field(default_factory=list, description="Ordered setup actions when content_type is steps")
    technique: str | None = Field(default=None, description="One-line summary of the prompting technique used")
    output_expected: str | None = Field(default=None, description="What tangible asset or result this step outputs")
    why_tool: str | None = Field(default=None, description="Why this tool was chosen (max 2 sentences)")
    learn_note: str | None = Field(default=None, description="One concept or watch-out (max 2 sentences)")
    handoff_note: str | None = Field(
        default=None,
        description="Optional user note passed from the previous step execution",
    )
    status: str = "pending"
    free_tier_note: str | None = Field(default=None, description="Free tier guidance or limits note for this step")
    warnings: list[str] = Field(default_factory=list, description="Any warnings such as commercial use or stale pricing")


class WorkflowRequest(BaseModel):
    brief: ProductBrief


class WorkflowResponse(BaseModel):
    id: int
    title: str
    brief: ProductBrief
    cost_summary: CostSummary = Field(default_factory=CostSummary)
    steps: list[WorkflowStep]
    created_at: str

    @computed_field
    @property
    def workflow_id(self) -> str:
        return str(self.id)

class StepRegenerateRequest(BaseModel):
    feedback: str | None = None

class StepSwitchToolRequest(BaseModel):
    tool_id: int

class StepFinishRequest(BaseModel):
    note: str = Field(default="", max_length=1000)
    feedback_result: Literal["worked", "partly", "didnt"] | None = Field(
        default=None,
        description="Usage signal on whether this step worked ('worked' | 'partly' | 'didnt')",
    )


class StepFeedbackCreate(BaseModel):
    result: Literal["worked", "partly", "didnt"]
    note: str | None = Field(default=None, max_length=1000)


class StepFeedbackResponse(BaseModel):
    id: int
    step_id: int
    workflow_id: int
    tool_id: int | None = None
    result: str
    note: str | None = None
    created_at: str


class StepActionResponse(BaseModel):
    workflow_id: str | None = None
    step: WorkflowStep
    next_step: WorkflowStep | None = None
    action: str
    message: str = "Step updated successfully"

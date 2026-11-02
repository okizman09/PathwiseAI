"""Pydantic schemas for the tools catalog (Catalog v3).

All SQLAlchemy ORM code lives in app.models.tool.
"""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.taxonomy import is_valid_domain, is_valid_job, validate_domain, validate_jobs


class ToolStatus(StrEnum):
    DRAFT = "draft"
    RESEARCHED = "researched"
    VERIFIED = "verified"
    HIDDEN = "hidden"


class PricingModel(StrEnum):
    FREE = "free"
    FREEMIUM = "freemium"
    FREE_TRIAL = "free_trial"
    PAID = "paid"
    OPEN_SOURCE = "open_source"
    UNKNOWN = "unknown"


class SkillLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ALL = "all"


class PromptStyleSchema(BaseModel):
    technique: str = Field(default="", description="e.g. role + task, tags/params, shot list")
    format: str = Field(default="", description="Structure / layout of the prompt")
    rules: list[str] = Field(default_factory=list, description="Formatting rules for this tool")
    example: str = Field(default="", description="One paste-ready example prompt")

    @field_validator("rules", mode="before")
    @classmethod
    def normalize_rules(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            if not v.strip():
                return []
            return [line.strip("- *").strip() for line in v.split("\n") if line.strip()]
        if isinstance(v, list):
            return [str(x) for x in v]
        return []


class ToolBase(BaseModel):
    name: str
    url: str
    affiliate_url: str | None = None
    docs_url: str | None = None

    # Taxonomy & categorization
    domain: str | None = None
    category: str | None = ""
    jobs: list[str] = Field(default_factory=list)

    # Pricing & monetization
    pricing_model: str = PricingModel.UNKNOWN.value
    has_free_tier: bool | None = None
    free_tier_summary: str | None = Field(default=None, max_length=140)
    free_tier_limits: str | None = None
    starting_price_monthly_usd: float | None = None
    pricing_notes: str | None = None
    credit_card_required: bool | None = None
    watermark_on_free: bool | None = None
    commercial_use_on_free: bool | None = None
    pricing_url: str | None = None
    pricing_checked_at: datetime | None = None
    pricing: str | None = "freemium"  # Legacy column preserved

    # Target & audience
    platforms: list[str] = Field(default_factory=list)
    skill_level: str = SkillLevel.ALL.value

    # Copy & descriptions
    tagline: str | None = Field(default=None, max_length=90)
    summary: str | None = None
    how_it_helps: str | None = None
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    best_for: str | None = ""
    not_for: str | None = ""

    # Media assets
    logo_url: str | None = None
    logo_source: str | None = None
    og_image_url: str | None = None

    # Prompt style & I/O
    prompt_style: PromptStyleSchema | None = Field(default_factory=PromptStyleSchema)
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)

    # Provenance, verification & signals
    evidence: dict[str, Any] | None = None
    review_flags: list[str] = Field(default_factory=list)
    official_domains: list[str] = Field(default_factory=list)
    research_provider: str | None = None
    researched_at: datetime | None = None
    verified_by: str | None = None
    is_pick: bool = False

    @field_validator("is_pick", mode="before")
    @classmethod
    def ensure_bool(cls, v: Any) -> bool:
        if v is None:
            return False
        return bool(v)

    @field_validator("platforms", "input_types", "output_types", "pros", "cons", "review_flags", "official_domains", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list:
        if v is None:
            return []
        return v



    @field_validator("jobs", mode="before")
    @classmethod
    def ensure_jobs_list(cls, v: Any) -> list:
        if v is None:
            return []
        return v


class ToolCreate(ToolBase):
    status: ToolStatus = ToolStatus.DRAFT

    @field_validator("jobs", mode="after")
    @classmethod
    def check_jobs_in_taxonomy(cls, v: list[str] | None) -> list[str]:
        if v:
            validate_jobs(v)
        return v or []

    @field_validator("domain", mode="after")
    @classmethod
    def check_domain_in_taxonomy(cls, v: str | None) -> str | None:
        if v:
            validate_domain(v)
        return v


class AdminToolCreateRequest(BaseModel):
    name: str
    url: str
    docs_urls: list[str] | None = None
    affiliate_url: str | None = None
    domain: str | None = None
    category: str | None = None
    jobs: list[str] | None = None
    pricing_model: str | None = None
    has_free_tier: bool | None = None
    free_tier_summary: str | None = None
    free_tier_limits: str | None = None
    starting_price_monthly_usd: float | None = None
    pricing_notes: str | None = None
    credit_card_required: bool | None = None
    watermark_on_free: bool | None = None
    commercial_use_on_free: bool | None = None
    pricing_url: str | None = None
    platforms: list[str] | None = None
    skill_level: str | None = None
    tagline: str | None = None
    summary: str | None = None
    how_it_helps: str | None = None
    pros: list[str] | None = None
    cons: list[str] | None = None
    input_types: list[str] | None = None
    output_types: list[str] | None = None
    pricing: str | None = None
    best_for: str | None = None
    not_for: str | None = None
    prompt_style: PromptStyleSchema | None = None
    logo_url: str | None = None
    logo_source: str | None = None
    logo_source_url: str | None = None
    og_image_url: str | None = None
    evidence: dict[str, Any] | None = None
    review_flags: list[str] | None = None
    official_domains: list[str] | None = None
    research_provider: str | None = None
    is_pick: bool = False

    @field_validator("jobs", mode="after")
    @classmethod
    def check_jobs_in_taxonomy(cls, v: list[str] | None) -> list[str] | None:
        if v:
            validate_jobs(v)
        return v

    @field_validator("domain", mode="after")
    @classmethod
    def check_domain_in_taxonomy(cls, v: str | None) -> str | None:
        if v:
            validate_domain(v)
        return v


class ToolUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    affiliate_url: str | None = None
    docs_url: str | None = None
    domain: str | None = None
    category: str | None = None
    jobs: list[str] | None = None
    pricing_model: str | None = None
    has_free_tier: bool | None = None
    free_tier_summary: str | None = None
    free_tier_limits: str | None = None
    starting_price_monthly_usd: float | None = None
    pricing_notes: str | None = None
    credit_card_required: bool | None = None
    watermark_on_free: bool | None = None
    commercial_use_on_free: bool | None = None
    pricing_url: str | None = None
    pricing_checked_at: datetime | None = None
    platforms: list[str] | None = None
    skill_level: str | None = None
    tagline: str | None = None
    summary: str | None = None
    how_it_helps: str | None = None
    pros: list[str] | None = None
    cons: list[str] | None = None
    input_types: list[str] | None = None
    output_types: list[str] | None = None
    pricing: str | None = None
    best_for: str | None = None
    not_for: str | None = None
    prompt_style: PromptStyleSchema | None = None
    logo_url: str | None = None
    logo_source: str | None = None
    logo_source_url: str | None = None
    og_image_url: str | None = None
    status: ToolStatus | None = None
    evidence: dict[str, Any] | None = None
    review_flags: list[str] | None = None
    official_domains: list[str] | None = None
    research_provider: str | None = None
    researched_at: datetime | None = None
    verified_by: str | None = None
    is_pick: bool | None = None
    sources: list[dict[str, Any]] | None = None
    research_notes: str | None = None

    @field_validator("jobs", mode="after")
    @classmethod
    def check_jobs_in_taxonomy(cls, v: list[str] | None) -> list[str] | None:
        if v:
            validate_jobs(v)
        return v

    @field_validator("domain", mode="after")
    @classmethod
    def check_domain_in_taxonomy(cls, v: str | None) -> str | None:
        if v:
            validate_domain(v)
        return v


class ToolResponse(ToolBase):
    """Admin response: exposes all fields, including affiliate_url and provenance."""
    id: int
    status: ToolStatus
    link_status: str = "unknown"
    link_checked_at: datetime | None = None
    sources: list[dict[str, Any]] | None = None
    research_notes: str | None = None
    verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    used_in_workflows_count: int | None = None

    @field_validator("jobs", mode="after")
    @classmethod
    def sanitize_jobs(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        return [j for j in v if is_valid_job(j)]

    @field_validator("domain", mode="after")
    @classmethod
    def sanitize_domain(cls, v: str | None) -> str | None:
        if not v:
            return None
        return v if is_valid_domain(v) else None

    @computed_field
    @property
    def open_url(self) -> str:
        return self.affiliate_url or self.url

    model_config = ConfigDict(from_attributes=True)


class ToolPublicResponse(BaseModel):
    """Public catalog response: exposes display fields and go_path, NEVER affiliate_url."""
    id: int
    name: str
    docs_url: str | None = None
    domain: str | None = None
    category: str | None = ""
    jobs: list[str] = Field(default_factory=list)
    tagline: str | None = None
    summary: str | None = None
    how_it_helps: str | None = None
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    pricing_model: str = PricingModel.UNKNOWN.value
    has_free_tier: bool | None = None
    free_tier_summary: str | None = None
    free_tier_limits: str | None = None
    starting_price_monthly_usd: float | None = None
    pricing_notes: str | None = None
    credit_card_required: bool | None = None
    watermark_on_free: bool | None = None
    commercial_use_on_free: bool | None = None
    pricing_url: str | None = None
    pricing_checked_at: datetime | None = None
    platforms: list[str] = Field(default_factory=list)
    skill_level: str = SkillLevel.ALL.value
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)
    best_for: str | None = ""
    not_for: str | None = ""
    prompt_style: PromptStyleSchema | None = Field(default_factory=PromptStyleSchema)
    logo_url: str | None = None
    logo_source: str | None = None
    og_image_url: str | None = None
    is_pick: bool = False
    status: ToolStatus
    link_status: str = "unknown"
    verified_at: datetime | None = None
    used_in_workflows_count: int | None = Field(
        default=None,
        description="Public display count of workflows where this tool was used (shown only if >= 10)",
    )

    @field_validator("is_pick", mode="before")
    @classmethod
    def ensure_bool(cls, v: Any) -> bool:
        if v is None:
            return False
        return bool(v)

    @field_validator("platforms", "input_types", "output_types", "pros", "cons", "jobs", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list:
        if v is None:
            return []
        return v

    @field_validator("jobs", mode="after")
    @classmethod
    def sanitize_jobs(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        return [j for j in v if is_valid_job(j)]

    @field_validator("domain", mode="after")
    @classmethod
    def sanitize_domain(cls, v: str | None) -> str | None:
        if not v:
            return None
        return v if is_valid_domain(v) else None


    @computed_field
    @property
    def go_path(self) -> str:
        return f"/go/{self.id}"

    @computed_field
    @property
    def verified_badge(self) -> str | None:
        if self.verified_at:
            return self.verified_at.strftime("Verified %b %Y")
        return None

    model_config = ConfigDict(from_attributes=True)


class ToolMetricResponse(BaseModel):
    """Aggregate per-tool usage signals and success rate for admin metrics."""
    tool_id: int
    name: str
    domain: str | None = None
    total_feedbacks: int = 0
    worked_count: int = 0
    partly_count: int = 0
    didnt_count: int = 0
    success_rate_percent: float | None = None
    used_in_workflows: int = 0


class PasteLogoUrlRequest(BaseModel):
    url: str


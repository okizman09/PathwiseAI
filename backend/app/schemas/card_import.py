"""Pydantic schemas for Catalog v3 Card Importer (Slice C2).

Strictly typed models for external card JSON import, enforcing Section 3 rules,
limits, consistency checks, and evidence structure.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.taxonomy.loader import is_valid_domain

ALLOWED_PLATFORMS = {"web", "desktop", "mobile", "cli", "api", "extension"}
ALLOWED_SKILL_LEVELS = {"beginner", "intermediate", "advanced", "all"}
ALLOWED_PRICING_MODELS = {"free", "freemium", "free_trial", "paid", "open_source", "unknown"}
VAGUE_PRICE_KEYWORDS = ["typically", "approx", "variable", "varies", "range", "up to", "starts around"]


class PromptStyleImport(BaseModel):
    technique: str = ""
    format: str = ""
    rules: list[str] = Field(default_factory=list)
    example: str = ""

    @field_validator("rules", mode="before")
    @classmethod
    def normalize_rules(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [line.strip("- ").strip() for line in v.splitlines() if line.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []


class EvidenceItem(BaseModel):
    source_url: str
    quote: str
    checked: bool | str | None = None  # True | False | "unknown" | None

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError(f"Evidence source_url must use HTTPS: {v}")
        return v

    @field_validator("quote")
    @classmethod
    def validate_quote(cls, v: str) -> str:
        words = v.strip().split()
        if len(words) > 20:
            # Enforce max 20 words by trimming to 20 words
            return " ".join(words[:20])
        return v.strip()


class CardImport(BaseModel):
    name: str = Field(..., min_length=1)
    domain: str = Field(...)
    official_url: str = Field(...)
    pricing_url: str | None = None
    pricing_model: Literal["free", "freemium", "free_trial", "paid", "open_source", "unknown"] = "unknown"
    has_free_tier: bool | None = None
    free_tier_summary: str | None = Field(None, max_length=140)
    free_tier_limits: str | None = None
    starting_price_monthly_usd: float | None = None
    pricing_notes: str | None = None
    credit_card_required: bool | None = None
    watermark_on_free: bool | None = None
    commercial_use_on_free: bool | None = None
    platforms: list[str] = Field(default_factory=list)
    skill_level: Literal["beginner", "intermediate", "advanced", "all"] = "all"
    jobs: list[str] = Field(..., min_length=1, max_length=5)
    tagline: str = Field(..., max_length=90)
    summary: str = Field(...)
    how_it_helps: str = Field(...)
    pros: list[str] = Field(..., min_length=3, max_length=3)
    cons: list[str] = Field(..., min_length=3, max_length=3)
    prompt_style: PromptStyleImport | None = None
    input_types: list[str] = Field(default_factory=list)
    output_types: list[str] = Field(default_factory=list)
    best_for: str = ""
    not_for: str = ""
    evidence: dict[str, EvidenceItem | None] | None = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    checked_on: str | None = None
    official_domains: list[str] = Field(default_factory=list)
    logo_source_url: str | None = None
    ecosystem: str | None = None
    kind: str | None = None
    model_id: str | None = None
    api_snippet: str | None = None
    docs_url: str | None = None

    @field_validator("logo_source_url")
    @classmethod
    def validate_logo_source_url(cls, v: str | None) -> str | None:
        if v:
            v = v.strip()
            if not v.startswith("https://"):
                raise ValueError("logo_source_url must use HTTPS")
            return v
        return None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tool name cannot be empty")
        return v

    @field_validator("domain")
    @classmethod
    def validate_domain_field(cls, v: str) -> str:
        if not is_valid_domain(v):
            raise ValueError(f"Domain '{v}' is not a valid taxonomy domain slug")
        return v

    @field_validator("official_url")
    @classmethod
    def validate_official_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError(f"official_url must use HTTPS: {v}")
        return v

    @field_validator("pricing_url")
    @classmethod
    def validate_pricing_url(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not v.startswith("https://"):
            raise ValueError(f"pricing_url must use HTTPS: {v}")
        return v

    @field_validator("starting_price_monthly_usd", mode="before")
    @classmethod
    def validate_starting_price(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if any(k in v_clean for k in VAGUE_PRICE_KEYWORDS) or "-" in v_clean:
                raise ValueError(f"Range or vague price claim rejected: '{v}'")
            cleaned = v_clean.replace("$", "").replace("/mo", "").replace("/month", "").strip()
            try:
                val = float(cleaned)
                if val < 0:
                    raise ValueError(f"Price cannot be negative: {v}")
                return val
            except ValueError:
                raise ValueError(f"Range or vague price claim rejected: '{v}'")
        if isinstance(v, (int, float)):
            val = float(v)
            if val < 0:
                raise ValueError(f"Price cannot be negative: {v}")
            return val
        raise ValueError(f"Unsupported starting price value: {v}")

    @field_validator("platforms")
    @classmethod
    def validate_platforms(cls, v: list[str]) -> list[str]:
        cleaned = []
        for p in v:
            p_clean = p.strip().lower()
            if p_clean in ALLOWED_PLATFORMS:
                cleaned.append(p_clean)
        return cleaned

    @field_validator("pros", "cons")
    @classmethod
    def validate_pros_cons_count(cls, v: list[str]) -> list[str]:
        cleaned = [item.strip() for item in v if item.strip()]
        if len(cleaned) != 3:
            raise ValueError(f"Must have exactly 3 items, got {len(cleaned)}")
        return cleaned


class CardImportBatch(BaseModel):
    cards: list[CardImport]
    expected: list[str] | None = None


class CardImportResult(BaseModel):
    name: str
    status: Literal["created", "updated", "rejected", "error"]
    tool_id: int | None = None
    flags: list[str] = Field(default_factory=list)
    error: str | None = None


class CardImportResponse(BaseModel):
    created: int = 0
    updated: int = 0
    rejected: int = 0
    missing_tools: list[str] = Field(default_factory=list)
    results: list[CardImportResult] = Field(default_factory=list)

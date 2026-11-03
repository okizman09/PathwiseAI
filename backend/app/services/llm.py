"""Pathwise AI — Meta Model API client.

Single entry point for all LLM calls.  Model name comes from env
META_MODEL; there is no silent fallback to a different model.
Same-model retry rule (one retry on transient errors); provider errors map
to sanitized UserFacingError.  Never logs keys, prompts or raw errors.
"""
import asyncio
import logging
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    NotFoundError,
    RateLimitError,
)
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.errors import UserFacingError
from app.schemas.tool import PromptStyleSchema

logger = logging.getLogger("pathwise.llm")


# ── Pydantic schema for the tool-card extraction (Slice 4 will supersede) ────

class ExtractedToolCard(BaseModel):
    url: str = Field(description="Main official tool website URL")
    category: str = Field(
        description="Tool category (e.g. website, video, audio, image, text, 3d, design, code)"
    )
    jobs: list[str] = Field(
        default_factory=list,
        description=(
            "List of specific jobs/tasks this tool performs "
            "(e.g. ['generate_landing_page', 'build_ui_component'])"
        ),
    )
    input_types: list[str] = Field(
        default_factory=list,
        description="Types of inputs this tool accepts (e.g. ['text', 'image'])",
    )
    output_types: list[str] = Field(
        default_factory=list,
        description="Types of outputs this tool produces (e.g. ['website', 'react_code'])",
    )
    pricing: str = Field(
        default="freemium",
        description="Pricing structure: free, freemium, or paid with brief note",
    )
    best_for: str = Field(
        default="",
        description="Who and what specific use cases this tool is best suited for",
    )
    not_for: str = Field(
        default="",
        description="What use cases or user needs this tool is NOT suited for",
    )
    prompt_style: PromptStyleSchema = Field(
        default_factory=PromptStyleSchema,
        description=(
            "Prompt engineering style specific to this tool "
            "(technique, format, rules, example)"
        ),
    )


# ── Tool-card extraction helper ───────────────────────────────────────────────

async def extract_tool_card_from_docs(
    name: str,
    docs_url: str,
    page_text: str,
) -> ExtractedToolCard:
    """Analyse documentation text with the Meta model and return a structured tool card."""

    system_instruction = (
        "You are an expert software analyst for Pathwise AI. "
        "Analyse the official documentation provided and extract an accurate, structured tool card.\n"
        "Rules:\n"
        "- Base your analysis strictly on the provided documentation text.\n"
        "- Do not invent features, capabilities, pricing, or affiliate links.\n"
        "- In `prompt_style`, describe the specific prompting technique, formatting rules, "
        "and include exactly ONE realistic paste-ready prompt example written for this tool.\n"
        "- Status is always 'draft'."
    )

    prompt = (
        f"Tool Name: {name}\n"
        f"Docs URL: {docs_url}\n\n"
        "=== BEGIN UNTRUSTED SOURCE MATERIAL ===\n"
        f"{page_text[:25000]}\n"
        "=== END UNTRUSTED SOURCE MATERIAL ===\n\n"
        "Extract the tool card JSON strictly conforming to the requested schema."
    )

    return await generate_structured(
        system=system_instruction,
        user=prompt,
        schema=ExtractedToolCard,
        temperature=0.2,
    )


# ── Meta Model API (hackathon T2) ───────────────────────────────────────────
# All LLM calls go through generate_structured / generate_text below.

# T1 finding: muse-spark-1.3 spends tokens on hidden reasoning items that count
# against max_output_tokens, so budgets must be generous or answers come back empty.
_DEFAULT_STRUCTURED_MAX_TOKENS = 4096
_DEFAULT_TEXT_MAX_TOKENS = 2048


@dataclass
class TextResult:
    """Plain-text result with the model used and token usage."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


_meta_client: AsyncOpenAI | None = None


def get_meta_client() -> AsyncOpenAI:
    """Build (once) the Meta Model API client from settings."""
    global _meta_client
    if _meta_client is None:
        if not settings.MODEL_API_KEY:
            raise ValueError("MODEL_API_KEY is not set in the environment.")
        _meta_client = AsyncOpenAI(
            api_key=settings.MODEL_API_KEY,
            base_url=settings.META_BASE_URL,
            max_retries=1,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    return _meta_client


def _short_error(exc: Exception) -> str:
    """Error type plus status code only; never the message (may echo input)."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    return f"{name} status={status}" if status is not None else name


def _is_transient(exc: Exception) -> bool:
    """Whether the same-model call is worth retrying once."""
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    return (
        isinstance(exc, APIStatusError)
        and exc.status_code is not None
        and exc.status_code >= 500
    )


def _map_provider_error(exc: Exception) -> UserFacingError:
    """Map SDK errors to sanitized errors (no keys, prompts or raw errors)."""
    if isinstance(exc, APITimeoutError):
        return UserFacingError(
            "The AI request timed out. Please try again.",
            status_code=504,
            code="llm_timeout",
        )
    if isinstance(exc, NotFoundError):
        return UserFacingError(
            "The configured AI model is unavailable.",
            status_code=503,
            code="model_unavailable",
        )
    if isinstance(exc, RateLimitError):
        return UserFacingError(
            "Too many AI requests. Please wait and try again.",
            status_code=429,
            code="llm_rate_limited",
        )
    if isinstance(exc, (APIConnectionError, APIStatusError)):
        return UserFacingError(
            "The AI service is unavailable. Please try again.",
            status_code=503,
            code="llm_unavailable",
        )
    return UserFacingError(
        "Something went wrong. Please try again.", status_code=502, code="llm_error"
    )


def _to_strict_json_schema(schema: type[BaseModel]) -> dict:
    """Normalize a Pydantic JSON schema to strict json_schema shape.

    Strict mode requires additionalProperties:false on every object (Meta
    rejects schemas without it) and every property listed in required.
    Forcing keys present is validation-safe: optional fields arrive as null.
    """
    raw = schema.model_json_schema()

    def _fix(node) -> None:
        if isinstance(node, dict):
            obj_type = node.get("type")
            is_object = (
                obj_type == "object"
                or (isinstance(obj_type, list) and "object" in obj_type)
                or "properties" in node
            )
            if is_object:
                node["additionalProperties"] = False
                props = node.get("properties", {})
                if isinstance(props, dict) and props:
                    node["required"] = sorted(set(node.get("required", [])) | set(props))
            for key in ("properties", "$defs", "definitions", "patternProperties"):
                child = node.get(key)
                if isinstance(child, dict):
                    for sub in child.values():
                        _fix(sub)
            for key in ("items", "additionalProperties", "contains"):
                child = node.get(key)
                if isinstance(child, dict):
                    _fix(child)
            for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
                child = node.get(key)
                if isinstance(child, list):
                    for sub in child:
                        _fix(sub)
        elif isinstance(node, list):
            for sub in node:
                _fix(sub)

    _fix(raw)
    return raw


async def generate_structured(
    *,
    system: str,
    user: str,
    schema: type[BaseModel],
    temperature: float = 0.2,
    max_output_tokens: int | None = None,
) -> BaseModel:
    """Call the Meta Model API and return a validated Pydantic model.

    Uses strict json_schema structured output (proven in T1); the Pydantic
    schema is normalized to strict shape (see _to_strict_json_schema).
    Two attempts total on the same model: a transient error or an invalid
    payload is retried once (invalid payloads with a repair note appended);
    anything else raises a sanitized error immediately.
    """
    client = get_meta_client()
    model = settings.META_MODEL
    budget = max_output_tokens if max_output_tokens is not None else _DEFAULT_STRUCTURED_MAX_TOKENS
    current_user = user
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            response = await client.responses.create(
                model=model,
                instructions=system,
                input=current_user,
                temperature=temperature,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema.__name__,
                        "schema": _to_strict_json_schema(schema),
                        "strict": True,
                    }
                },
                max_output_tokens=budget,
            )
        except Exception as exc:
            last_error = exc
            if _is_transient(exc) and attempt == 0:
                logger.warning(
                    "Meta model %s transient error on attempt 1/2 (%s). Retrying in 1 s.",
                    model,
                    _short_error(exc),
                )
                await asyncio.sleep(1.0)
                continue
            raise _map_provider_error(exc) from exc
        try:
            return schema.model_validate_json(response.output_text)
        except ValidationError as exc:
            last_error = exc
            if attempt == 0:
                logger.warning(
                    "Meta model %s returned invalid JSON on attempt 1/2. Retrying with repair note.",
                    model,
                )
                current_user = (
                    f"{user}\n\nThe previous response failed validation "
                    f"({exc.error_count()} field error(s)). Return corrected JSON only."
                )
                continue
            raise UserFacingError(
                "The AI response could not be understood. Please try again.",
                status_code=502,
                code="llm_error",
            ) from exc

    raise _map_provider_error(last_error or RuntimeError("unreachable"))


async def generate_text(
    *,
    system: str | None,
    user: str,
    model: str | None = None,
    max_output_tokens: int | None = None,
    timeout: float | None = None,
) -> TextResult:
    """Call the Meta Model API and return plain text plus usage.

    Same-model retry rule: one retry on transient errors, then a sanitized
    error. No fallback to another model.
    """
    client = get_meta_client()
    model_name = model or settings.META_MODEL
    budget = max_output_tokens if max_output_tokens is not None else _DEFAULT_TEXT_MAX_TOKENS
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            create_kwargs = {
                "model": model_name,
                "instructions": system,
                "input": user,
                "max_output_tokens": budget,
            }
            if timeout is not None:
                create_kwargs["timeout"] = timeout
            response = await client.responses.create(**create_kwargs)
        except Exception as exc:
            last_error = exc
            if _is_transient(exc) and attempt == 0:
                logger.warning(
                    "Meta model %s transient error on attempt 1/2 (%s). Retrying in 1 s.",
                    model_name,
                    _short_error(exc),
                )
                await asyncio.sleep(1.0)
                continue
            raise _map_provider_error(exc) from exc
        usage = getattr(response, "usage", None)
        return TextResult(
            text=response.output_text or "",
            model=model_name,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    raise _map_provider_error(last_error or RuntimeError("unreachable"))

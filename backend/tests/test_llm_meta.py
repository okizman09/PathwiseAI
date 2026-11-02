"""Unit tests for the Meta Model API client (app.services.llm).

The SDK client is always mocked; these tests never touch the network.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, NotFoundError
from pydantic import BaseModel


class _Order(BaseModel):
    customer: str
    quantity: int


class _StrictItem(BaseModel):
    name: str
    note: str | None = None


class _StrictOrder(BaseModel):
    customer: str
    items: list[_StrictItem] = []
    priority: int = 0


_GOOD_JSON = '{"customer": "Ada", "quantity": 2}'


def _fake_response(text, input_tokens=10, output_tokens=20):
    return SimpleNamespace(
        output_text=text,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _timeout_error():
    request = httpx.Request("POST", "https://api.meta.ai/v1/responses")
    return APITimeoutError(request)


def _connection_error():
    request = httpx.Request("POST", "https://api.meta.ai/v1/responses")
    return APIConnectionError(request=request)


def _not_found_error():
    request = httpx.Request("POST", "https://api.meta.ai/v1/responses")
    response = httpx.Response(404, request=request)
    return NotFoundError("model not found", response=response, body=None)


@pytest.fixture
def fake_meta_client(monkeypatch):
    """Patch the client factory so no real client (or key) is needed."""
    client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock()))
    monkeypatch.setattr("app.services.llm.get_meta_client", lambda: client)
    return client


@pytest.mark.asyncio
async def test_generate_structured_success(fake_meta_client):
    from app.core.config import settings
    from app.services.llm import generate_structured

    fake_meta_client.responses.create.return_value = _fake_response(_GOOD_JSON)

    result = await generate_structured(
        system="Extract the order.", user="Ada wants 2 items.", schema=_Order
    )

    assert result == _Order(customer="Ada", quantity=2)
    _, kwargs = fake_meta_client.responses.create.await_args
    assert kwargs["model"] == settings.META_MODEL
    assert kwargs["instructions"] == "Extract the order."
    fmt = kwargs["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert fmt["name"] == "_Order"


@pytest.mark.asyncio
async def test_generate_structured_repairs_invalid_json(fake_meta_client):
    from app.services.llm import generate_structured

    fake_meta_client.responses.create.side_effect = [
        _fake_response("not json at all"),
        _fake_response(_GOOD_JSON),
    ]

    result = await generate_structured(system="s", user="u", schema=_Order)

    assert result == _Order(customer="Ada", quantity=2)
    assert fake_meta_client.responses.create.await_count == 2
    _, retry_kwargs = fake_meta_client.responses.create.await_args
    assert "failed validation" in retry_kwargs["input"]


@pytest.mark.asyncio
async def test_generate_structured_transient_retry_then_success(fake_meta_client):
    from app.services.llm import generate_structured

    fake_meta_client.responses.create.side_effect = [
        _timeout_error(),
        _fake_response(_GOOD_JSON),
    ]

    result = await generate_structured(system="s", user="u", schema=_Order)

    assert result == _Order(customer="Ada", quantity=2)
    assert fake_meta_client.responses.create.await_count == 2


@pytest.mark.asyncio
async def test_generate_structured_timeout_raises_sanitized_error(fake_meta_client):
    from app.core.errors import UserFacingError
    from app.services.llm import generate_structured

    fake_meta_client.responses.create.side_effect = _timeout_error()

    with pytest.raises(UserFacingError) as exc_info:
        await generate_structured(system="s", user="u", schema=_Order)

    assert exc_info.value.status_code == 504
    assert exc_info.value.code == "llm_timeout"
    assert exc_info.value.message == "The AI request timed out. Please try again."
    assert fake_meta_client.responses.create.await_count == 2


@pytest.mark.asyncio
async def test_generate_text_success(fake_meta_client):
    from app.core.config import settings
    from app.services.llm import generate_text

    fake_meta_client.responses.create.return_value = _fake_response("hello", 7, 3)

    result = await generate_text(system="Be brief.", user="Say hello.")

    assert result.text == "hello"
    assert result.model == settings.META_MODEL
    assert (result.input_tokens, result.output_tokens) == (7, 3)


@pytest.mark.asyncio
async def test_generate_text_unavailable_model_raises_without_retry(fake_meta_client):
    from app.core.errors import UserFacingError
    from app.services.llm import generate_text

    fake_meta_client.responses.create.side_effect = _not_found_error()

    with pytest.raises(UserFacingError) as exc_info:
        await generate_text(system=None, user="hi")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "model_unavailable"
    assert fake_meta_client.responses.create.await_count == 1


@pytest.mark.asyncio
async def test_generate_text_connection_error_retries_once(fake_meta_client):
    from app.core.errors import UserFacingError
    from app.services.llm import generate_text

    fake_meta_client.responses.create.side_effect = _connection_error()

    with pytest.raises(UserFacingError) as exc_info:
        await generate_text(system=None, user="hi")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "llm_unavailable"
    assert fake_meta_client.responses.create.await_count == 2


@pytest.mark.asyncio
async def test_generate_structured_sends_strict_shape_schema(fake_meta_client):
    from app.services.llm import generate_structured

    fake_meta_client.responses.create.return_value = _fake_response(
        '{"customer": "Ada", "items": [], "priority": 0}'
    )

    await generate_structured(system="s", user="u", schema=_StrictOrder)

    _, kwargs = fake_meta_client.responses.create.await_args
    sent = kwargs["text"]["format"]["schema"]
    assert sent["additionalProperties"] is False
    assert set(sent["required"]) == set(sent["properties"])
    defs = sent.get("$defs", {})
    assert defs, "expected nested model definitions"
    item_def = next(iter(defs.values()))
    assert item_def["additionalProperties"] is False
    assert set(item_def["required"]) == set(item_def["properties"])

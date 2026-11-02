"""Meta Model API hello-world probe (hackathon T1).

Standalone connectivity check. Reads MODEL_API_KEY from the environment
(never from a literal) and talks to the Meta Model API with the OpenAI SDK.

Usage (you run this yourself, from backend/):
    MODEL_API_KEY=... python scripts/meta_hello.py

Optional overrides: META_BASE_URL (default https://api.meta.ai/v1),
META_MODEL (default muse-spark-1.3).

On failure this prints only the error type and status code, never the key
or full responses.
"""

import os
import sys

from pydantic import BaseModel, ConfigDict

TARGET_MODEL = os.environ.get("META_MODEL", "muse-spark-1.3")
BASE_URL = os.environ.get("META_BASE_URL", "https://api.meta.ai/v1")


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    quantity: int


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer: str
    items: list[OrderItem]


def short_error(exc: Exception) -> str:
    """Error type plus status code only. Never the message (may echo input)."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    return f"{name} status={status}" if status is not None else name


def step_models(client) -> bool:
    print("--- 1. models.list() ---")
    try:
        models = client.models.list()
    except Exception as exc:  # noqa: BLE001 - probe must not crash
        print(f"models FAILED: {short_error(exc)}")
        return False
    ids = [m.id for m in models.data]
    print(f"models ok: {len(ids)} model(s) listed")
    print(f"target {TARGET_MODEL!r} present: {TARGET_MODEL in ids}")
    return True


def step_text(client) -> bool:
    print("--- 2. plain text (Responses API) ---")
    try:
        response = client.responses.create(
            model=TARGET_MODEL,
            instructions="You are a connectivity probe. Follow instructions exactly.",
            input="Reply with exactly: hello from Meta",
            max_output_tokens=2048,
        )
    except Exception as exc:  # noqa: BLE001 - probe must not crash
        print(f"text FAILED: {short_error(exc)}")
        return False
    print(f"status={response.status}")
    details = getattr(response, "incomplete_details", None)
    if details is not None:
        print(f"incomplete_reason={getattr(details, 'reason', details)}")
    try:
        item_types = [item.type for item in (response.output or [])]
    except Exception:  # noqa: BLE001 - diagnostics must not crash
        item_types = ["<unreadable>"]
    print(f"output_items={item_types}")
    print(f"text ok: {response.output_text!r}")
    return True


def step_structured(client) -> str:
    print("--- 3. structured output ---")
    prompt = (
        "A voice note says: Ada wants 2 soap bars and 1 oil, delivery Friday. "
        "Return the order."
    )
    status, out_len = None, -1
    try:
        response = client.responses.create(
            model=TARGET_MODEL,
            instructions="Return the order described by the user.",
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "Order",
                    "schema": Order.model_json_schema(),
                    "strict": True,
                }
            },
            max_output_tokens=4096,
        )
        status = response.status
        out_len = len(response.output_text or "")
        order = Order.model_validate_json(response.output_text)
        print(f"json_schema ok: {order.model_dump_json()}")
        return "json_schema"
    except Exception as exc:  # noqa: BLE001 - fall through to json_object
        print(f"json_schema failed ({short_error(exc)}; status={status} "
              f"output_len={out_len}), trying json_object...")
    status, out_len = None, -1
    try:
        response = client.responses.create(
            model=TARGET_MODEL,
            instructions=(
                "Return JSON matching this schema exactly, no other text: "
                f"{Order.model_json_schema()}"
            ),
            input=prompt,
            text={"format": {"type": "json_object"}},
            max_output_tokens=4096,
        )
        status = response.status
        out_len = len(response.output_text or "")
        order = Order.model_validate_json(response.output_text)
        print(f"json_object ok: {order.model_dump_json()}")
        return "json_object"
    except Exception as exc:  # noqa: BLE001 - probe must not crash
        print(f"structured FAILED: {short_error(exc)}; status={status} output_len={out_len}")
        return "none"


def step_streaming(client) -> bool:
    print("--- 4. streaming ---")
    try:
        stream = client.responses.create(
            model=TARGET_MODEL,
            instructions="You are a connectivity probe. Follow instructions exactly.",
            input="Reply with exactly: streaming works",
            max_output_tokens=2048,
            stream=True,
        )
        seen: list[str] = []
        chunks: list[str] = []
        terminal_status: str | None = None
        terminal_text: str | None = None
        for event in stream:
            kind = getattr(event, "type", None) or type(event).__name__
            if kind not in seen:
                seen.append(kind)
            delta = getattr(event, "delta", None)
            if isinstance(delta, str):
                chunks.append(delta)
            if kind in ("response.completed", "response.incomplete"):
                resp = getattr(event, "response", None)
                if resp is not None:
                    terminal_status = getattr(resp, "status", kind)
                    try:
                        terminal_text = resp.output_text
                    except Exception:  # noqa: BLE001 - diagnostics must not crash
                        terminal_text = None
    except Exception as exc:  # noqa: BLE001 - probe must not crash
        print(f"streaming FAILED: {short_error(exc)}")
        return False
    print(f"event types: {seen}")
    print(f"terminal_status={terminal_status}")
    final = "".join(chunks) or (terminal_text or "")
    print(f"final text: {final!r}")
    return True


def main() -> int:
    if not os.environ.get("MODEL_API_KEY"):
        print("MODEL_API_KEY is not set. Refusing to run.", file=sys.stderr)
        return 2
    try:
        from openai import OpenAI
    except ImportError:
        print("The 'openai' package is not installed. Run: pip install -r requirements.txt",
              file=sys.stderr)
        return 2
    client = OpenAI(
        api_key=os.environ["MODEL_API_KEY"],
        base_url=BASE_URL,
        timeout=60.0,
    )
    print(f"base_url={BASE_URL} model={TARGET_MODEL}")

    models_ok = step_models(client)
    text_ok = step_text(client)
    structured_method = step_structured(client) if text_ok else "skipped"
    if not text_ok:
        print("--- 3. structured output ---")
        print("structured skipped (plain text failed)")
    streaming_ok = step_streaming(client) if text_ok else False
    if not text_ok:
        print("--- 4. streaming ---")
        print("streaming skipped (plain text failed)")

    print("--- 5. summary ---")
    print(f"models_ok={models_ok} text_ok={text_ok} "
          f"structured_method={structured_method} streaming_ok={streaming_ok}")
    return 0 if (models_ok and text_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

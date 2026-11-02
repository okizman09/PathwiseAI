from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings


def create_click_ref(user_id: str, workflow_id: int, step_id: int, tool_id: int) -> str:
    """Create a short-lived (10 min) signed reference token for link clicks."""
    payload = {
        "user_id": user_id,
        "workflow_id": workflow_id,
        "step_id": step_id,
        "tool_id": tool_id,
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.signing_secret, algorithm="HS256")


def decode_click_ref(ref: str) -> dict | None:
    """Decode and verify a click reference token. Returns None if invalid or expired."""
    try:
        return jwt.decode(ref, settings.signing_secret, algorithms=["HS256"])
    except Exception:
        return None

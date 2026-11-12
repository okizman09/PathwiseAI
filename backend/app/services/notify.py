"""Transactional email notifications (Resend HTTP API)."""

import logging

import httpx

from app.core.config import settings

log = logging.getLogger("pathwise.notify")

RESEND_API_URL = "https://api.resend.com/emails"


def notifications_configured() -> bool:
    return bool(settings.RESEND_API_KEY and settings.FEEDBACK_NOTIFY_TO)


def send_site_feedback_email(
    *, message: str, contact: str | None, page: str | None, feedback_id: int
) -> bool:
    """Send one site-feedback notification. Never raises; False when skipped/failed."""
    if not notifications_configured():
        return False
    try:
        payload: dict[str, object] = {
            "from": settings.FEEDBACK_NOTIFY_FROM,
            "to": [settings.FEEDBACK_NOTIFY_TO],
            "subject": f"[Pathwise] New site feedback #{feedback_id}",
            "text": "\n".join(
                [
                    message,
                    "",
                    f"Page: {page or '-'}",
                    f"Contact: {contact or '-'}",
                    f"Feedback ID: {feedback_id}",
                ]
            ),
        }
        if contact:
            payload["reply_to"] = contact
        resp = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception:
        log.exception("site-feedback notification failed")
        return False

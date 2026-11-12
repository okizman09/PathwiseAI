"""Transactional email notifications (stdlib SMTP; Gmail-compatible)."""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("pathwise.notify")


def notifications_configured() -> bool:
    return bool(
        settings.SMTP_USERNAME and settings.SMTP_PASSWORD and settings.FEEDBACK_NOTIFY_TO
    )


def send_site_feedback_email(
    *, message: str, contact: str | None, page: str | None, feedback_id: int
) -> bool:
    """Send one site-feedback notification. Never raises; False when skipped/failed."""
    if not notifications_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Pathwise] New site feedback #{feedback_id}"
        msg["From"] = settings.SMTP_USERNAME
        msg["To"] = settings.FEEDBACK_NOTIFY_TO
        if contact:
            msg["Reply-To"] = contact
        msg.set_content(
            "\n".join(
                [
                    message,
                    "",
                    f"Page: {page or '-'}",
                    f"Contact: {contact or '-'}",
                    f"Feedback ID: {feedback_id}",
                ]
            )
        )
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as client:
            client.starttls()
            client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            client.send_message(msg)
        return True
    except Exception:
        log.exception("site-feedback notification failed")
        return False

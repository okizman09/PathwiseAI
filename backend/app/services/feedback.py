"""Landing-page UX feedback: listing and CSV export."""

import csv
import io

from sqlalchemy.orm import Session

SITE_FEEDBACK_EXPORT_COLUMNS = (
    "feedback_id",
    "created_at",
    "message",
    "contact",
    "page",
    "user_id",
)


def list_site_feedback(db: Session, limit: int = 100):
    """Return the newest site feedback rows first."""
    from app.models.site_feedback import SiteFeedback

    return (
        db.query(SiteFeedback)
        .order_by(SiteFeedback.created_at.desc(), SiteFeedback.id.desc())
        .limit(limit)
        .all()
    )


def build_site_feedback_csv(db: Session) -> str:
    """Build the admin site-feedback CSV export (all rows, newest first)."""
    from app.models.site_feedback import SiteFeedback

    rows = (
        db.query(SiteFeedback)
        .order_by(SiteFeedback.created_at.desc(), SiteFeedback.id.desc())
        .all()
    )
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(SITE_FEEDBACK_EXPORT_COLUMNS)
    for fb in rows:
        writer.writerow(
            [
                fb.id,
                fb.created_at.isoformat() if fb.created_at else "",
                fb.message,
                fb.contact or "",
                fb.page or "",
                fb.user_id or "",
            ]
        )
    # BOM so Excel opens the UTF-8 messages correctly.
    return "\ufeff" + buf.getvalue()

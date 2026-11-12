"""Pydantic schemas for landing-page UX feedback."""

from datetime import datetime

from pydantic import BaseModel, field_validator


class SiteFeedbackCreate(BaseModel):
    message: str
    contact: str | None = None
    page: str | None = None

    @field_validator("message")
    @classmethod
    def _clean_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message must not be empty.")
        if len(v) > 2000:
            raise ValueError("Message must be at most 2000 characters.")
        return v

    @field_validator("contact")
    @classmethod
    def _clean_contact(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 320 or "@" not in v or " " in v:
            raise ValueError("Contact must be a valid email address.")
        return v

    @field_validator("page")
    @classmethod
    def _clean_page(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        return v[:500]


class SiteFeedbackResponse(BaseModel):
    id: int
    message: str
    contact: str | None = None
    page: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None

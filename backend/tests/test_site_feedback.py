"""Tests for landing-page UX feedback: public submit, admin list/export."""

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models.profile import Profile
from app.models.rate_limit import RateLimitBucket
from app.models.site_feedback import SiteFeedback
from tests.test_auth import generate_token


@pytest.fixture(autouse=True)
def _clean_site_feedback():
    def _clean():
        db = SessionLocal()
        db.query(SiteFeedback).delete()
        db.query(RateLimitBucket).delete()
        db.query(Profile).filter(Profile.id.in_(["sf-user-1", "sf-admin-1"])).delete()
        db.commit()
        db.close()

    _clean()
    yield
    _clean()


def _seed_profile(user_id: str, role: str) -> None:
    db = SessionLocal()
    db.merge(Profile(id=user_id, email=f"{user_id}@example.com", role=role))
    db.commit()
    db.close()


def test_submit_site_feedback_anonymous(client: TestClient):
    res = client.post(
        "/api/v1/feedback/site",
        json={"message": "  Love the landing page!  ", "page": "/"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["message"] == "Love the landing page!"
    assert body["page"] == "/"
    assert body["user_id"] is None
    assert body["id"]


def test_submit_site_feedback_validation(client: TestClient):
    assert client.post("/api/v1/feedback/site", json={"message": "   "}).status_code == 422
    assert (
        client.post("/api/v1/feedback/site", json={"message": "x" * 2001}).status_code == 422
    )
    assert (
        client.post(
            "/api/v1/feedback/site",
            json={"message": "Hi", "contact": "not-an-email"},
        ).status_code
        == 422
    )
    res = client.post(
        "/api/v1/feedback/site",
        json={"message": "Hi", "contact": "me@example.com"},
    )
    assert res.status_code == 201
    assert res.json()["contact"] == "me@example.com"


def test_submit_site_feedback_rate_limited(client: TestClient):
    for _ in range(5):
        res = client.post("/api/v1/feedback/site", json={"message": "Again"})
        assert res.status_code == 201
    res = client.post("/api/v1/feedback/site", json={"message": "Too many"})
    assert res.status_code == 429


def test_submit_site_feedback_attaches_signed_in_user(client: TestClient):
    _seed_profile("sf-user-1", "creator")
    token = generate_token(subject="sf-user-1", email="sf-user-1@example.com")
    res = client.post(
        "/api/v1/feedback/site",
        json={"message": "From a user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["user_id"] == "sf-user-1"


def test_admin_site_feedback_list(client: TestClient):
    db = SessionLocal()
    db.add(SiteFeedback(message="First", page="/"))
    db.add(SiteFeedback(message="Second", page="/", contact="a@b.co"))
    db.commit()
    db.close()

    assert client.get("/api/v1/admin/feedback/site").status_code == 401

    _seed_profile("sf-user-1", "creator")
    user_token = generate_token(subject="sf-user-1", email="sf-user-1@example.com")
    res_user = client.get(
        "/api/v1/admin/feedback/site",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_user.status_code == 403

    _seed_profile("sf-admin-1", "admin")
    admin_token = generate_token(subject="sf-admin-1", email="sf-admin-1@example.com")
    res = client.get(
        "/api/v1/admin/feedback/site",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    rows = res.json()
    assert [r["message"] for r in rows] == ["Second", "First"]
    assert rows[0]["contact"] == "a@b.co"


def test_submit_sends_email_when_configured(client: TestClient, monkeypatch):
    import smtplib

    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_USERNAME", "sender@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(settings, "FEEDBACK_NOTIFY_TO", "owner@example.com")

    sent = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    res = client.post(
        "/api/v1/feedback/site",
        json={"message": "Email me", "contact": "visitor@example.com", "page": "/"},
    )
    assert res.status_code == 201
    assert len(sent) == 1
    assert sent[0]["To"] == "owner@example.com"
    assert sent[0]["Reply-To"] == "visitor@example.com"
    assert "New site feedback" in sent[0]["Subject"]
    assert "Email me" in sent[0].get_content()


def test_submit_skips_email_when_unconfigured(client: TestClient, monkeypatch):
    import smtplib

    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "FEEDBACK_NOTIFY_TO", "")

    def _boom(*args, **kwargs):
        raise AssertionError("SMTP must not be used when unconfigured")

    monkeypatch.setattr(smtplib, "SMTP", _boom)
    res = client.post("/api/v1/feedback/site", json={"message": "No email"})
    assert res.status_code == 201


def test_admin_site_feedback_export_csv(client: TestClient):
    import csv
    import io

    _seed_profile("sf-admin-1", "admin")
    db = SessionLocal()
    db.add(SiteFeedback(message='He said "hi", bye\nnew line', page="/"))
    db.commit()
    db.close()

    admin_token = generate_token(subject="sf-admin-1", email="sf-admin-1@example.com")
    res = client.get(
        "/api/v1/admin/feedback/site/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "site-feedback-" in res.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(res.text.lstrip("\ufeff"))))
    assert len(rows) == 1
    assert list(rows[0].keys()) == [
        "feedback_id",
        "created_at",
        "message",
        "contact",
        "page",
        "user_id",
    ]
    assert rows[0]["message"] == 'He said "hi", bye\nnew line'

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.core.rate_limit import PersistentRateLimiter
from app.db import get_db
from app.models.event import Event
from app.models.profile import Profile
from app.models.rate_limit import RateLimitBucket
from app.models.usage import UsageDaily
from app.models.workflow import Workflow, WorkflowStep
from tests.test_auth import generate_token


def setup_module(module):
    settings.SUPABASE_JWT_SECRET = "testsecretthatisatleast32characterslong"
    settings.SUPABASE_JWT_AUDIENCE = "authenticated"


def test_production_config_passes_with_jwks_only(monkeypatch):
    """Test that in production mode, having SUPABASE_URL without SUPABASE_JWT_SECRET passes."""
    prod_env = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql://user:pass@ep-123.supabase.com:5432/postgres",
        "MODEL_API_KEY": "valid-model-key",
        "SUPABASE_URL": "https://xyzcompany.supabase.co",
        "APP_SIGNING_SECRET": "production-signing-secret-at-least-32-chars-long",
        "CORS_ORIGINS": "https://app.pathwise.ai",
        "SUPABASE_JWT_SECRET": "",  # JWKS only! No legacy secret!
    }
    for k, v in prod_env.items():
        monkeypatch.setenv(k, v)

    s = Settings()
    assert s.ENVIRONMENT == "production"
    assert s.SUPABASE_URL == "https://xyzcompany.supabase.co"
    assert s.SUPABASE_JWT_SECRET == ""


def test_health_checks_database_connectivity(client: TestClient):
    """Test that /health checks database connectivity and returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_rate_limiting_survives_restart():
    """Test that rate limit counters persist in the database across limiter instances."""
    # Create two separate instances of PersistentRateLimiter with a low threshold
    limiter1 = PersistentRateLimiter(requests_per_minute=2, daily_cap=10)
    limiter2 = PersistentRateLimiter(requests_per_minute=2, daily_cap=10)

    db_gen = get_db()
    db = next(db_gen)
    test_key = "user:test-persistent-rate-limit"

    try:
        # Clean any prior record
        db.query(RateLimitBucket).filter_by(key=test_key).delete()
        db.commit()

        # limiter1 records 2 hits
        limiter1.check(db, test_key)
        limiter1.check(db, test_key)

        # Simulate restart by destroying limiter1 and using fresh limiter2 on the same DB
        del limiter1

        # The 3rd request through the fresh limiter should hit the limit (429)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            limiter2.check(db, test_key)
        assert exc_info.value.status_code == 429
        assert "Too many requests" in exc_info.value.detail
    finally:
        db.close()


def test_delete_account_removes_all_user_data(client: TestClient):
    """Test that DELETE /me removes profile, workflows, steps, events, usage, and rate limits."""
    user_id = "user-to-be-deleted-123"
    email = "delete-me@example.com"
    token = generate_token(subject=user_id, email=email)
    auth_headers = {"Authorization": f"Bearer {token}"}

    db_gen = get_db()
    db = next(db_gen)

    try:
        # 1. Populate profile and related rows
        profile = Profile(id=user_id, email=email, role="user")
        db.add(profile)
        db.commit()

        wf = Workflow(user_id=user_id, title="Path to Delete", brief={"goal": "Build app"})
        db.add(wf)
        db.commit()
        db.refresh(wf)

        step = WorkflowStep(workflow_id=wf.id, position=1, kind="tool", job="Plan")
        db.add(step)

        event = Event(user_id=user_id, kind="test_event")
        db.add(event)

        usage = UsageDaily(user_id=user_id, day=datetime.now(UTC).date(), kind="workflow", count=1)
        db.add(usage)

        rate_bucket = RateLimitBucket(key=f"user:{user_id}", window_type="minute", window_start=1000, count=1)
        db.add(rate_bucket)
        db.commit()

        # Verify rows exist
        assert db.query(Profile).filter_by(id=user_id).first() is not None
        assert db.query(Workflow).filter_by(user_id=user_id).first() is not None
        assert db.query(WorkflowStep).filter_by(workflow_id=wf.id).first() is not None
        assert db.query(Event).filter_by(user_id=user_id).first() is not None
        assert db.query(UsageDaily).filter_by(user_id=user_id).first() is not None
        assert db.query(RateLimitBucket).filter_by(key=f"user:{user_id}").first() is not None

        # 2. Call DELETE /me
        resp = client.delete("/api/v1/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # 3. Verify ALL data is permanently removed
        assert db.query(Profile).filter_by(id=user_id).first() is None
        assert db.query(Workflow).filter_by(user_id=user_id).first() is None
        assert db.query(WorkflowStep).filter_by(workflow_id=wf.id).first() is None
        assert db.query(Event).filter_by(user_id=user_id).first() is None
        assert db.query(UsageDaily).filter_by(user_id=user_id).first() is None
        assert db.query(RateLimitBucket).filter_by(key=f"user:{user_id}").first() is None
    finally:
        db.close()


def test_beta_allowlist_enforcement(client: TestClient, monkeypatch):
    """Test that BETA_ALLOWLIST_ENABLED blocks non-allowlisted users with 403 not_in_beta."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "BETA_ALLOWLIST_ENABLED", True)
    monkeypatch.setattr(settings, "BETA_ALLOWED_EMAILS", "allowed@example.com,vip@example.com")

    # 1. Unlisted user gets 403 not_in_beta on /workflows
    unlisted_token = generate_token(subject="unlisted-1", email="stranger@example.com")
    resp = client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {unlisted_token}"})
    assert resp.status_code == 403
    assert resp.json().get("code") == "not_in_beta"

    # 2. Allowed user can access /workflows
    allowed_token = generate_token(subject="allowed-1", email="allowed@example.com")
    resp = client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {allowed_token}"})
    assert resp.status_code == 200

    # 3. Admin user is always exempt
    db_gen = get_db()
    db = next(db_gen)
    admin_prof = Profile(id="admin-1", email="admin-outsider@example.com", role="admin")
    db.merge(admin_prof)
    db.commit()
    db.close()

    admin_token = generate_token(subject="admin-1", email="admin-outsider@example.com")
    resp = client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200

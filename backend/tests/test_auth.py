import base64
import json
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.db import SessionLocal
from app.models.profile import Profile


def setup_module(module):
    settings.SUPABASE_JWT_SECRET = "testsecretthatisatleast32characterslong"
    settings.SUPABASE_JWT_AUDIENCE = "authenticated"


def generate_token(
    subject="user123",
    email="user@example.com",
    role="authenticated",
    audience="authenticated",
    email_verified=True,
    expired=False,
    tampered=False,
):
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "aud": audience,
        "email_verified": email_verified,
        "user_metadata": {"email_verified": email_verified},
        "exp": datetime.now(UTC) + timedelta(minutes=-10 if expired else 60),
    }

    secret = settings.SUPABASE_JWT_SECRET
    if tampered:
        secret = "wrongsecretthatisalsolongenoughtobevalid"

    return jwt.encode(payload, secret, algorithm="HS256")


def test_missing_token(client):
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert "Authentication required" in response.json()["detail"]


def test_valid_token(client):
    token = generate_token()
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user123"
    assert data["email"] == "user@example.com"
    assert data["role"] == "user"
    assert data["email_verified"] is True


def test_expired_token(client):
    token = generate_token(expired=True)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


def test_tampered_token(client):
    token = generate_token(tampered=True)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_wrong_audience(client):
    token = generate_token(audience="wrong")
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Invalid audience" in response.json()["detail"]


def test_algorithm_none_rejected(client):
    """Verify alg=none tokens are strictly rejected."""
    payload = {
        "sub": "user123",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=60)).timestamp()),
    }
    # Craft token with alg=none
    h_b64 = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    none_token = f"{h_b64}.{p_b64}."

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {none_token}"})
    assert response.status_code == 401
    assert "not permitted" in response.json()["detail"] or "Invalid token" in response.json()["detail"]


def test_asymmetric_bad_key_rejected(client):
    """Verify ES256 / RS256 token with invalid key/signature is rejected."""
    h_b64 = base64.urlsafe_b64encode(b'{"alg":"ES256","typ":"JWT","kid":"fake-kid"}').decode().rstrip("=")
    payload = {
        "sub": "user123",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=60)).timestamp()),
    }
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    bad_token = f"{h_b64}.{p_b64}.invalidsignature"

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {bad_token}"})
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_unverified_email_blocked_on_interview_and_workflows(client):
    """Unverified users get 403 with code email_not_verified on protected routes."""
    token = generate_token(subject="unverified_1", email="unverified@test.com", email_verified=False)

    # GET /me returns email_verified: False
    res_me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["email_verified"] is False

    # POST /interview returns 403
    res_int = client.post(
        "/api/v1/interview",
        json={"goal": "Build an app", "answers": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_int.status_code == 403
    body = res_int.json()
    assert body["code"] == "email_not_verified"
    assert body["message"] == "Please verify your email first."

    # POST /workflows returns 403
    res_wf = client.post(
        "/api/v1/workflows",
        json={
            "brief": {
                "what_being_made": "App",
                "purpose": "Test",
                "target_audience": "Devs",
                "constraints": [],
                "must_haves": [],
                "nice_to_haves": [],
                "assumptions": [],
                "skill_level": "beginner",
                "budget_preference": "free_only",
            }
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_wf.status_code == 403
    assert res_wf.json()["code"] == "email_not_verified"


def test_profile_creation_race_integrity_error_handled(client):
    """Verify concurrent profile creation race is handled gracefully."""
    token = generate_token(subject="race_user_1", email="race1@test.com")

    # Pre-create the user in DB directly to simulate concurrent thread having just inserted it
    db = SessionLocal()
    existing = Profile(id="race_user_1", email="race1@test.com", role="user")
    db.merge(existing)
    db.commit()
    db.close()

    # The request should succeed without crashing on duplicate key
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["id"] == "race_user_1"


def test_require_admin_valid(client):
    db = SessionLocal()
    profile = Profile(id="admin123", email="admin@example.com", role="admin")
    db.merge(profile)
    db.commit()
    db.close()

    token = generate_token(subject="admin123", email="admin@example.com")
    response = client.get("/api/v1/admin/tools", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_require_admin_forbidden(client):
    token = generate_token(subject="user123", email="user@example.com")
    response = client.get("/api/v1/admin/tools", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


def test_last_seen_throttled_to_15_minutes(client):
    """last_seen_at stamps on first sight and when stale, but not on every request (perf)."""
    token = generate_token(subject="lastseen_user_1", email="lastseen1@test.com")

    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    db = SessionLocal()
    first = db.query(Profile).filter(Profile.id == "lastseen_user_1").one().last_seen_at
    db.close()
    assert first is not None

    # Immediate second request leaves the stamp untouched (no write).
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    db = SessionLocal()
    second = db.query(Profile).filter(Profile.id == "lastseen_user_1").one().last_seen_at
    db.close()
    assert second == first

    # A stale stamp gets refreshed.
    db = SessionLocal()
    db.query(Profile).filter(Profile.id == "lastseen_user_1").update(
        {"last_seen_at": datetime.now(UTC) - timedelta(hours=2)}
    )
    db.commit()
    db.close()
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    db = SessionLocal()
    third = db.query(Profile).filter(Profile.id == "lastseen_user_1").one().last_seen_at
    db.close()
    assert third > second

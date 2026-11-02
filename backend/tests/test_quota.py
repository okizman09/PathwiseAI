import concurrent.futures

import pytest
from freezegun import freeze_time

from app.db import SessionLocal
from app.models.profile import Profile
from app.models.usage import UsageDaily
from app.services.quota.quota import QuotaExceededException, get_usage, refund, reserve


@pytest.fixture
def test_user(client):
    db = SessionLocal()
    user = Profile(id="test_user_quota", email="q@test.com", role="user")
    db.merge(user)
    db.commit()
    db.close()
    return user

@pytest.fixture
def admin_user(client):
    db = SessionLocal()
    user = Profile(id="admin_user_quota", email="adminq@test.com", role="admin")
    db.merge(user)
    db.commit()
    db.close()
    return user

def test_quota_admin_exempt(admin_user):
    db = SessionLocal()
    for _ in range(10):
        reserve(db, admin_user, "workflow")
    usage = get_usage(db, admin_user, "workflow")
    assert usage["used"] == 0
    db.close()

def test_quota_reserve_and_refund(test_user):
    db = SessionLocal()
    reserve(db, test_user, "workflow")
    usage = get_usage(db, test_user, "workflow")
    assert usage["used"] == 1

    refund(db, test_user, "workflow")
    usage = get_usage(db, test_user, "workflow")
    assert usage["used"] == 0
    db.close()

def test_quota_exceeds(test_user):
    db = SessionLocal()
    # Assuming WORKFLOWS_PER_DAY = 2
    reserve(db, test_user, "workflow")
    reserve(db, test_user, "workflow")

    with pytest.raises(QuotaExceededException) as exc:
        reserve(db, test_user, "workflow")

    assert exc.value.status_code == 429
    assert exc.value.detail["used"] == 2
    assert exc.value.detail["limit"] == 2
    db.close()

def test_quota_concurrent(test_user):
    # Test that concurrent requests don't exceed the limit
    def try_reserve():
        db = SessionLocal()
        try:
            reserve(db, test_user, "interview_turn") # Limit is 25
            return True
        except QuotaExceededException:
            return False
        finally:
            db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Try to reserve 50 times concurrently
        results = list(executor.map(lambda _: try_reserve(), range(50)))

    successful = results.count(True)
    assert successful == 25

@freeze_time("2026-10-05 23:59:59")
def test_quota_rollover(test_user):
    db = SessionLocal()
    db.query(UsageDaily).filter_by(user_id=test_user.id).delete()
    db.commit()
    reserve(db, test_user, "workflow")
    usage = get_usage(db, test_user, "workflow")
    assert usage["used"] == 1
    db.close()

    with freeze_time("2026-10-06 00:00:01"):
        db = SessionLocal()
        usage_next_day = get_usage(db, test_user, "workflow")
        assert usage_next_day["used"] == 0
        db.close()

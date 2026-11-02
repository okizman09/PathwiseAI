"""Persistent rate limiting backed by database counters.

Survives process restarts. Authenticated routes limit per user ID,
public routes limit per client IP. Uses request.client.host set by
trusted proxies (Uvicorn ProxyHeadersMiddleware) and never trusts
raw X-Forwarded-For headers from arbitrary clients.
"""
import time

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models.rate_limit import RateLimitBucket
from app.services.auth.supabase_jwt import verify_supabase_token

REQUESTS_PER_MINUTE = 30
DAILY_CAP = 150


def get_client_ip(request: Request) -> str:
    """Return the client IP without trusting client-supplied X-Forwarded-For entries.

    Each trusted reverse proxy appends the address it saw to X-Forwarded-For. A client can
    put anything at the START of the header, so we count from the END: with
    TRUSTED_PROXY_COUNT=1 (Render) the last entry is the real client. If the header is
    missing, or TRUSTED_PROXY_COUNT is 0, fall back to the direct peer address.
    Run uvicorn with --no-proxy-headers so request.client.host is the peer, not a header value.
    """
    trusted = max(0, int(getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0))
    if trusted > 0:
        header = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in header.split(",") if p.strip()]
        if parts:
            index = len(parts) - trusted
            return parts[index] if index >= 0 else parts[0]
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class PersistentRateLimiter:
    """Database-backed rate limiter that survives application restarts."""

    def __init__(self, requests_per_minute: int = REQUESTS_PER_MINUTE, daily_cap: int = DAILY_CAP):
        self.requests_per_minute = requests_per_minute
        self.daily_cap = daily_cap

    def check(self, db: Session, key: str) -> None:
        now = int(time.time())
        minute_start = (now // 60) * 60
        day_start = (now // 86400) * 86400

        # Increment minute bucket
        minute_count = self._increment_bucket(db, key, "minute", minute_start)
        if minute_count > self.requests_per_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests in a short period. Please wait a moment before trying again.",
                headers={"Retry-After": "60"},
            )

        # Increment day bucket
        day_count = self._increment_bucket(db, key, "day", day_start)
        if day_count > self.daily_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily free tier usage limit reached. Please try again tomorrow.",
                headers={"Retry-After": "3600"},
            )

    def _increment_bucket(self, db: Session, key: str, window_type: str, window_start: int) -> int:
        dialect = db.bind.dialect.name if db.bind else "sqlite"
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
            stmt = insert(RateLimitBucket).values(
                key=key, window_type=window_type, window_start=window_start, count=1
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_rate_limit_key_window",
                set_={"count": RateLimitBucket.count + 1},
            ).returning(RateLimitBucket.count)
            count = db.execute(stmt).scalar()
            db.commit()
            return int(count) if count is not None else 1
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
            stmt = insert(RateLimitBucket).values(
                key=key, window_type=window_type, window_start=window_start, count=1
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["key", "window_type", "window_start"],
                set_={"count": RateLimitBucket.count + 1},
            ).returning(RateLimitBucket.count)
            count = db.execute(stmt).scalar()
            db.commit()
            return int(count) if count is not None else 1
        else:
            bucket = (
                db.query(RateLimitBucket)
                .filter_by(key=key, window_type=window_type, window_start=window_start)
                .first()
            )
            if not bucket:
                bucket = RateLimitBucket(
                    key=key, window_type=window_type, window_start=window_start, count=1
                )
                db.add(bucket)
            else:
                bucket.count += 1
            db.commit()
            db.refresh(bucket)
            return bucket.count


limiter = PersistentRateLimiter()


async def rate_limit_dependency(request: Request, db: Session = Depends(get_db)):
    """FastAPI route dependency for rate limiting.

    Authenticated routes limit per user id; public routes limit per IP.
    """
    key: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ", 1)[1].strip()
        try:
            payload = verify_supabase_token(token)
            sub = payload.get("sub")
            if sub:
                key = f"user:{sub}"
        except Exception:
            pass

    if not key:
        client_ip = get_client_ip(request)
        key = f"ip:{client_ip}"

    limiter.check(db, key)

import logging
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None

ALLOWED_ALGORITHMS = {"HS256", "ES256", "RS256"}


def get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    if _jwks_client is None and settings.SUPABASE_URL:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


def verify_supabase_token(token: str) -> dict[str, Any]:
    """
    Verifies a Supabase JWT token.
    Enforces strict algorithm allowlist:
    - Rejects 'none', lowercase 'none', missing, or unapproved algorithms.
    - Accepts HS256 only when SUPABASE_JWT_SECRET is set.
    - Accepts ES256 and RS256 via Supabase JWKS, passing exactly that list to jwt.decode.
    Checks signature, audience, and expiration.
    """
    try:
        try:
            header = jwt.get_unverified_header(token)
        except Exception as e:
            raise ValueError(f"Invalid token header: {e}")

        alg = header.get("alg")
        if not alg or str(alg).lower() == "none" or alg not in ALLOWED_ALGORITHMS:
            raise ValueError(f"Algorithm '{alg}' is not permitted.")

        if alg == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                raise ValueError("HS256 is not allowed when SUPABASE_JWT_SECRET is not configured.")
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                options={"verify_exp": True, "verify_aud": True, "verify_signature": True},
            )
        elif alg in ("ES256", "RS256"):
            jwks_client = get_jwks_client()
            if not jwks_client:
                raise ValueError(f"SUPABASE_URL not configured for algorithm {alg}.")
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience=settings.SUPABASE_JWT_AUDIENCE,
                options={"verify_exp": True, "verify_aud": True, "verify_signature": True},
            )
        else:
            raise ValueError(f"Algorithm '{alg}' is not permitted.")

        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Supabase token expired.")
        raise ValueError("Token has expired.")
    except jwt.InvalidAudienceError:
        logger.warning("Supabase token invalid audience.")
        raise ValueError("Invalid audience.")
    except Exception as e:
        logger.warning(f"Supabase token validation failed: {e}")
        raise ValueError(f"Invalid token: {e}")


_email_verified_cache: dict[str, tuple[bool, float]] = {}


def is_email_verified(payload: dict[str, Any], token: str | None = None) -> bool:
    """
    Determine if the user's email is verified.
    Checks:
    1. Top-level 'email_verified' claim (boolean)
    2. 'user_metadata.email_verified'
    3. 'email_confirmed_at' claim (truthy timestamp)
    4. 'app_metadata.provider' in OAuth providers like 'google'
    5. Cache lookup
    6. Server-side Supabase Auth /auth/v1/user lookup fallback (cached for 5 min)
    """
    import time

    import httpx

    # 1. Top-level claim
    if "email_verified" in payload:
        return bool(payload["email_verified"])

    # 2. User metadata
    user_metadata = payload.get("user_metadata") or {}
    if "email_verified" in user_metadata:
        return bool(user_metadata["email_verified"])

    # 3. email_confirmed_at
    if payload.get("email_confirmed_at"):
        return True

    # 4. OAuth provider
    app_metadata = payload.get("app_metadata") or {}
    if app_metadata.get("provider") in ("google", "github") and payload.get("email"):
        return True

    user_id = payload.get("sub")
    now = time.time()
    if user_id and user_id in _email_verified_cache:
        verified, exp = _email_verified_cache[user_id]
        if now < exp:
            return verified

    # 5. Server lookup fallback
    if token and settings.SUPABASE_URL:
        try:
            url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
            headers = {"Authorization": f"Bearer {token}"}
            if settings.SUPABASE_ANON_KEY:
                headers["apikey"] = settings.SUPABASE_ANON_KEY
            resp = httpx.get(url, headers=headers, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                verified = bool(
                    data.get("email_confirmed_at")
                    or data.get("confirmed_at")
                    or (data.get("user_metadata") or {}).get("email_verified")
                )
                if user_id:
                    _email_verified_cache[user_id] = (verified, now + 300)
                return verified
        except Exception as e:
            logger.warning(f"Failed to lookup user from Supabase auth: {e}")

    return False


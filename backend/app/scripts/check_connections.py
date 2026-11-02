"""Diagnostic utility to verify service connections and API integrity.

Reads all credentials and connection strings strictly from environment variables via Settings.
Never hardcodes secrets, API keys, or project URLs.
"""
import sys

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.db import SessionLocal
from app.main import app


def check_all():
    print("=" * 60)
    print(f"Pathwise AI — Connection Diagnostics ({settings.ENVIRONMENT})")
    print("=" * 60)

    all_ok = True

    # 1. Database Connection
    print("\n[1] Checking Database connectivity...")
    try:
        db = SessionLocal()
        res = db.execute(text("SELECT 1")).scalar()
        db.close()
        if res == 1:
            print(" -> PASS: Database connected successfully.")
        else:
            print(" -> FAIL: Unexpected query result from database.")
            all_ok = False
    except Exception as e:
        print(f" -> FAIL: Database connection failed: {e}")
        all_ok = False

    # 2. Supabase Configuration
    print("\n[2] Checking Supabase environment configuration...")
    if settings.SUPABASE_URL:
        print(f" -> PASS: SUPABASE_URL configured: {settings.SUPABASE_URL}")
    else:
        print(" -> WARN: SUPABASE_URL is not set.")

    if settings.SUPABASE_JWT_SECRET:
        print(" -> PASS: SUPABASE_JWT_SECRET configured.")
    else:
        print(" -> INFO: SUPABASE_JWT_SECRET not set (using asymmetric JWKS if URL configured).")

    if settings.APP_SIGNING_SECRET:
        print(" -> PASS: APP_SIGNING_SECRET configured.")
    else:
        print(" -> WARN: APP_SIGNING_SECRET not set (using dev fallback).")

    # 3. Meta Model API
    print("\n[3] Checking Meta Model API...")
    if not settings.MODEL_API_KEY:
        print(" -> WARN: MODEL_API_KEY is not set.")
    else:
        try:
            resp = httpx.get(
                f"{settings.META_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.MODEL_API_KEY}"},
                timeout=15.0,
            )
            resp.raise_for_status()
            ids = [m.get("id") for m in resp.json().get("data", [])]
            if settings.META_MODEL in ids:
                print(f" -> PASS: META_MODEL '{settings.META_MODEL}' available ({len(ids)} models).")
            else:
                print(f" -> FAIL: META_MODEL '{settings.META_MODEL}' not in models list ({len(ids)} models).")
                all_ok = False
        except Exception as e:
            print(f" -> FAIL: Meta models endpoint error: {type(e).__name__}")
            all_ok = False

    # 4. API Endpoints Check via TestClient
    print("\n[4] Checking FastAPI application endpoints...")
    try:
        client = TestClient(app)

        # /health
        resp = client.get("/health")
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print(f" -> PASS: GET /health -> 200 OK ({resp.json()})")
        else:
            print(f" -> FAIL: GET /health returned {resp.status_code}: {resp.text}")
            all_ok = False

        # /api/v1/tools
        resp = client.get("/api/v1/tools")
        if resp.status_code == 200:
            tools = resp.json()
            print(f" -> PASS: GET /api/v1/tools -> 200 OK ({len(tools)} verified tools)")
        else:
            print(f" -> FAIL: GET /api/v1/tools returned {resp.status_code}: {resp.text}")
            all_ok = False

    except Exception as e:
        print(f" -> FAIL: API endpoints check encountered an error: {e}")
        all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("DIAGNOSTICS PASSED: All verified connections are operational.")
    else:
        print("DIAGNOSTICS COMPLETED WITH WARNINGS/FAILURES.")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(check_all())

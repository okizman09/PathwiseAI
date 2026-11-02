"""Test error sanitization for non-admin vs admin routes (Slice C0)."""
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.main import app

# Add temporary test endpoints to verify sanitization
error_sanitization_router = APIRouter()


@error_sanitization_router.get("/api/v1/test-user-crash")
def user_crash_endpoint():
    raise RuntimeError("Secret internal database connection string: postgresql://admin:secret123@db:5432/db")


@error_sanitization_router.get("/api/v1/test-user-http500")
def user_http500_endpoint():
    raise HTTPException(
        status_code=500,
        detail="Raw sensitive traceback info from worker node 42",
    )


@error_sanitization_router.get("/api/v1/admin/test-admin-crash")
def admin_crash_endpoint():
    raise RuntimeError("Detailed stack trace for admin debugging")


@error_sanitization_router.get("/api/v1/admin/test-admin-http500")
def admin_http500_endpoint():
    raise HTTPException(
        status_code=500,
        detail="Specific admin diagnostic failure code ERR-999",
    )


app.include_router(error_sanitization_router)


def test_non_admin_route_sanitizes_unhandled_exception(client: TestClient):
    """Unhandled Python exceptions on non-admin routes must never leak raw traceback/secrets."""
    # Use a TestClient that does not re-raise server exceptions to inspect the HTTP 500 response
    test_c = TestClient(app, raise_server_exceptions=False)
    res = test_c.get("/api/v1/test-user-crash")
    assert res.status_code == 500
    data = res.json()
    assert data["detail"] == "Something went wrong. Please try again."
    assert "secret123" not in res.text
    assert "postgresql://" not in res.text


def test_non_admin_route_sanitizes_http_500(client: TestClient):
    """HTTP 500 exceptions on non-admin routes must not leak raw detail text."""
    test_c = TestClient(app, raise_server_exceptions=False)
    res = test_c.get("/api/v1/test-user-http500")
    assert res.status_code == 500
    data = res.json()
    assert data["detail"] == "Something went wrong. Please try again."
    assert "worker node 42" not in res.text


def test_admin_route_preserves_unhandled_exception_detail():
    """Admin routes keep specific error messages for administrative troubleshooting."""
    test_c = TestClient(app, raise_server_exceptions=False)
    res = test_c.get("/api/v1/admin/test-admin-crash")
    assert res.status_code == 500
    data = res.json()
    assert "Detailed stack trace for admin debugging" in data["detail"]


def test_admin_route_preserves_http_500_detail():
    """Admin routes keep specific HTTP 500 detail strings."""
    test_c = TestClient(app, raise_server_exceptions=False)
    res = test_c.get("/api/v1/admin/test-admin-http500")
    assert res.status_code == 500
    data = res.json()
    assert "Specific admin diagnostic failure code ERR-999" in data["detail"]

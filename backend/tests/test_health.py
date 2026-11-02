"""Health endpoint tests (Slice 0)."""


def test_health_root(client):
    """GET /health returns 200 and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


def test_health_v1(client):
    """GET /api/v1/health also returns 200 (dual-prefix mount)."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"

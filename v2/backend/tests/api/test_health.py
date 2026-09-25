from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_synthetic_only() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "synthetic_only": True}

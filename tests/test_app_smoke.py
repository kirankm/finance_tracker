from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_page_renders_app_name() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Automated SMS Expense Tracker" in response.text

from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app

AUTH_HEADERS = {"X-Inbound-SMS-Secret": "change-me-in-development"}


@contextmanager
def make_test_client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = testing_session_local()

    def override_get_db_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_operational_readiness_requires_shared_secret() -> None:
    with make_test_client() as client:
        response = client.get("/api/ops/readiness")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_operational_readiness_reports_checks_without_secret_values() -> None:
    with make_test_client() as client:
        response = client.get("/api/ops/readiness", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    check_names = {check["name"] for check in payload["checks"]}
    assert {
        "inbound_secret_configured",
        "inbound_secret_not_default",
        "database_url_configured",
        "raw_sms_export_default_omits_body",
        "backup_restore_docs_present",
        "first_real_use_checklist_present",
        "android_forwarder_validation_docs_present",
        "production_pilot_go_no_go_present",
    }.issubset(check_names)
    assert "change-me-in-development" not in response.text
    default_secret_check = next(
        check for check in payload["checks"] if check["name"] == "inbound_secret_not_default"
    )
    assert default_secret_check["status"] == "fail"
    assert default_secret_check["severity"] == "blocker"

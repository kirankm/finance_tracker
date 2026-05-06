from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import Account
from tests.test_export import AUTH_HEADERS, seed_export_data


@contextmanager
def make_test_client() -> Generator[tuple[TestClient, Session], None, None]:
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
        yield TestClient(app), session
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_import_validation_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.post("/api/import/json/validate", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_import_validation_accepts_exported_json_and_does_not_write_data() -> None:
    with make_test_client() as (client, session):
        seed_export_data(session)
        exported = client.get("/api/export/json", headers=AUTH_HEADERS).json()
        session.query(Account).delete()
        session.commit()

        response = client.post(
            "/api/import/json/validate",
            headers=AUTH_HEADERS,
            json=exported,
        )
        stored_accounts = session.scalars(select(Account)).all()

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "format_version": 2,
        "counts": {
            "accounts": 1,
            "ledger_transactions": 1,
            "raw_sms_messages": 1,
            "categories": 0,
            "audit_events": 1,
            "user_rules": 1,
        },
        "raw_sms_bodies_included": 0,
        "warnings": [],
    }
    assert stored_accounts == []


def test_import_validation_rejects_unsupported_version_and_missing_sections() -> None:
    with make_test_client() as (client, _session):
        unsupported_response = client.post(
            "/api/import/json/validate",
            headers=AUTH_HEADERS,
            json={"format_version": 99},
        )
        missing_response = client.post(
            "/api/import/json/validate",
            headers=AUTH_HEADERS,
            json={"format_version": 2, "accounts": []},
        )

    assert unsupported_response.status_code == 422
    assert unsupported_response.json() == {"detail": "unsupported export format_version"}
    assert missing_response.status_code == 422
    assert missing_response.json() == {
        "detail": (
            "export JSON is missing required sections: ledger_transactions, "
            "raw_sms_messages, categories, audit_events, user_rules"
        )
    }

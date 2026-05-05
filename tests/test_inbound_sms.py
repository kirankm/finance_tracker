from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import RawSmsMessage


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


def valid_payload() -> dict[str, str]:
    return {
        "message_id": "fake-forwarder-msg-001",
        "sender": "FAKEBANK",
        "received_at": "2026-05-04T10:30:00Z",
        "body": Path("tests/fixtures/sms/golden/debit-upi.sms.txt").read_text(
            encoding="utf-8"
        ),
    }


def test_inbound_sms_rejects_request_without_shared_secret() -> None:
    with make_test_client() as (client, session):
        response = client.post("/api/inbound-sms", json=valid_payload())

        assert response.status_code == 401
        assert session.scalars(select(RawSmsMessage)).all() == []


def test_inbound_sms_rejects_malformed_payload_without_persistence() -> None:
    with make_test_client() as (client, session):
        response = client.post(
            "/api/inbound-sms",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json={"sender": "FAKEBANK", "body": ""},
        )

        assert response.status_code == 422
        assert session.scalars(select(RawSmsMessage)).all() == []


def test_inbound_sms_accepts_valid_fake_payload_and_stores_raw_sms() -> None:
    with make_test_client() as (client, session):
        response = client.post(
            "/api/inbound-sms",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json=valid_payload(),
        )

        assert response.status_code == 201
        response_payload = response.json()
        assert response_payload["raw_sms_id"].startswith("raw_sms_")
        assert response_payload["candidate"]["transaction_type"] == "debit"
        assert response_payload["candidate"]["amount"] == 480
        assert response_payload["candidate"]["review_status"] == "needs_review"
        assert "body" not in response_payload

        stored_messages = session.scalars(select(RawSmsMessage)).all()

    assert len(stored_messages) == 1
    assert stored_messages[0].external_message_id == "fake-forwarder-msg-001"
    assert stored_messages[0].sender == "FAKEBANK"
    assert stored_messages[0].body == valid_payload()["body"]
    assert stored_messages[0].parser_output["transaction_type"] == "debit"
    assert stored_messages[0].parser_output["parser_metadata"]["parser"] == "fake_upi_debit_v1"

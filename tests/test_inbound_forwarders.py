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


def selected_forwarder_payload() -> dict[str, str]:
    return {
        "from": "FAKEBANK",
        "text": Path("tests/fixtures/sms/golden/debit-upi.sms.txt").read_text(
            encoding="utf-8"
        ),
        "sentStamp": "1777890599000",
        "receivedStamp": "1777890600000",
        "sim": "SIM1",
    }


def test_selected_forwarder_rejects_request_without_shared_secret() -> None:
    with make_test_client() as (client, session):
        response = client.post(
            "/api/forwarders/android-income-sms-webhook", json=selected_forwarder_payload()
        )

        assert response.status_code == 401
        assert session.scalars(select(RawSmsMessage)).all() == []


def test_selected_forwarder_auth_runs_before_payload_validation() -> None:
    with make_test_client() as (client, session):
        response = client.post(
            "/api/forwarders/android-income-sms-webhook",
            headers={"X-Inbound-SMS-Secret": "definitely-wrong-secret"},
            json={"text": ""},
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "unauthorized"}
        assert session.scalars(select(RawSmsMessage)).all() == []


def test_selected_forwarder_rejects_malformed_payload_without_persistence() -> None:
    with make_test_client() as (client, session):
        response = client.post(
            "/api/forwarders/android-income-sms-webhook",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json={"from": "FAKEBANK", "text": ""},
        )

        assert response.status_code == 422
        assert session.scalars(select(RawSmsMessage)).all() == []


def test_selected_forwarder_rejects_invalid_epoch_timestamp_without_persistence() -> None:
    payload = selected_forwarder_payload()
    payload["receivedStamp"] = "999999999999999999999999999999"

    with make_test_client() as (client, session):
        response = client.post(
            "/api/forwarders/android-income-sms-webhook",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json=payload,
        )

        assert response.status_code == 422
        assert session.scalars(select(RawSmsMessage)).all() == []


def test_selected_forwarder_maps_fake_payload_to_internal_ingestion_contract() -> None:
    with make_test_client() as (client, session):
        response = client.post(
            "/api/forwarders/android-income-sms-webhook",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json=selected_forwarder_payload(),
        )

        assert response.status_code == 201
        response_payload = response.json()
        assert response_payload["raw_sms_id"].startswith("raw_sms_")
        assert response_payload["candidate"]["transaction_type"] == "debit"
        assert response_payload["candidate"]["amount"] == 480

        stored_messages = session.scalars(select(RawSmsMessage)).all()

    assert len(stored_messages) == 1
    assert stored_messages[0].external_message_id.startswith(
        "android_income_sms_webhook_"
    )
    assert stored_messages[0].sender == "FAKEBANK"
    assert stored_messages[0].received_at.isoformat() == "2026-05-04T10:30:00+00:00"
    assert stored_messages[0].body == selected_forwarder_payload()["text"]
    assert stored_messages[0].source == "android_income_sms_webhook"
    assert stored_messages[0].parser_output["transaction_type"] == "debit"


def test_selected_forwarder_duplicate_payload_is_idempotent() -> None:
    with make_test_client() as (client, session):
        first_response = client.post(
            "/api/forwarders/android-income-sms-webhook",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json=selected_forwarder_payload(),
        )
        replay_response = client.post(
            "/api/forwarders/android-income-sms-webhook",
            headers={"X-Inbound-SMS-Secret": "change-me-in-development"},
            json=selected_forwarder_payload(),
        )

        stored_messages = session.scalars(select(RawSmsMessage)).all()

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    assert replay_response.json()["raw_sms_id"] == first_response.json()["raw_sms_id"]
    assert len(stored_messages) == 1

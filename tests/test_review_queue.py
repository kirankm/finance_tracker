from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import RawSmsMessage

AUTH_HEADERS = {"X-Inbound-SMS-Secret": "change-me-in-development"}


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


def fake_sms_body(merchant: str = "MERCHANT_FOOD_1") -> str:
    return Path("tests/fixtures/sms/golden/debit-upi.sms.txt").read_text(
        encoding="utf-8"
    ).replace("MERCHANT_FOOD_1", merchant)


def inbound_payload(
    message_id: str,
    received_at: str,
    *,
    merchant: str = "MERCHANT_FOOD_1",
) -> dict[str, str]:
    return {
        "message_id": message_id,
        "sender": "FAKEBANK",
        "received_at": received_at,
        "body": fake_sms_body(merchant),
    }


def ingest_sms(
    client: TestClient,
    message_id: str,
    received_at: str,
    *,
    merchant: str = "MERCHANT_FOOD_1",
) -> str:
    response = client.post(
        "/api/inbound-sms",
        headers=AUTH_HEADERS,
        json=inbound_payload(message_id, received_at, merchant=merchant),
    )
    assert response.status_code == 201
    return str(response.json()["raw_sms_id"])


def test_pending_review_queue_lists_needs_review_candidates_oldest_first_without_raw_body() -> None:
    with make_test_client() as (client, _session):
        newest_raw_sms_id = ingest_sms(
            client,
            "fake-forwarder-msg-newest",
            "2026-05-04T10:32:00Z",
            merchant="MERCHANT_UNKNOWN_1",
        )
        oldest_raw_sms_id = ingest_sms(
            client,
            "fake-forwarder-msg-oldest",
            "2026-05-04T10:30:00Z",
        )

        response = client.get("/api/review-queue", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert [item["raw_sms_id"] for item in payload["items"]] == [
        oldest_raw_sms_id,
        newest_raw_sms_id,
    ]
    assert payload["items"][0]["candidate"]["merchant_canonical"] == "Merchant Food 1"
    assert payload["items"][0]["candidate"]["category"] == "food_delivery"
    assert payload["items"][1]["candidate"]["merchant_raw"] == "MERCHANT_UNKNOWN_1"
    assert "body" not in payload["items"][0]
    assert "body" not in payload["items"][0]["candidate"]


def test_review_queue_detail_returns_candidate_explainability_metadata() -> None:
    with make_test_client() as (client, _session):
        raw_sms_id = ingest_sms(
            client,
            "fake-forwarder-msg-detail",
            "2026-05-04T10:30:00Z",
        )

        response = client.get(f"/api/review-queue/{raw_sms_id}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_sms_id"] == raw_sms_id
    assert payload["sender"] == "FAKEBANK"
    assert payload["body"] == fake_sms_body()
    assert payload["candidate"]["transaction_type"] == "debit"
    assert payload["candidate"]["confidence"]["account_mapping"] == "high"
    assert payload["candidate"]["parser_metadata"]["parser"] == "fake_upi_debit_v1"
    assert payload["candidate"]["rule_metadata"]["merchant_mapping"] == {
        "rule_id": "merchant_food_1_v1",
        "matched_value": "MERCHANT_FOOD_1",
    }


def test_mark_review_item_reviewed_updates_status_and_audit_metadata_idempotently() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(
            client,
            "fake-forwarder-msg-reviewed",
            "2026-05-04T10:30:00Z",
        )

        first_response = client.post(
            f"/api/review-queue/{raw_sms_id}/review",
            headers=AUTH_HEADERS,
            json={"decision": "reviewed", "reason": "fake QA review"},
        )
        replay_response = client.post(
            f"/api/review-queue/{raw_sms_id}/review",
            headers=AUTH_HEADERS,
            json={"decision": "reviewed", "reason": "fake QA review"},
        )
        pending_response = client.get("/api/review-queue", headers=AUTH_HEADERS)
        stored_raw_sms = session.get(RawSmsMessage, raw_sms_id)

    assert first_response.status_code == 200
    assert replay_response.status_code == 200
    assert first_response.json()["candidate"]["review_status"] == "reviewed"
    assert replay_response.json()["candidate"]["review_status"] == "reviewed"
    assert pending_response.json()["items"] == []
    assert stored_raw_sms is not None
    assert stored_raw_sms.body == fake_sms_body()
    assert stored_raw_sms.parser_output["review_status"] == "reviewed"
    assert stored_raw_sms.parser_output["review_metadata"]["decision"] == "reviewed"
    assert stored_raw_sms.parser_output["review_metadata"]["reason"] == "fake QA review"
    assert stored_raw_sms.parser_output["review_metadata"]["actor_type"] == "user"


def test_reviewed_items_are_excluded_from_pending_queue_but_available_in_detail() -> None:
    with make_test_client() as (client, _session):
        raw_sms_id = ingest_sms(
            client,
            "fake-forwarder-msg-reviewed-detail",
            "2026-05-04T10:30:00Z",
        )
        review_response = client.post(
            f"/api/review-queue/{raw_sms_id}/review",
            headers=AUTH_HEADERS,
            json={"decision": "reviewed"},
        )

        pending_response = client.get("/api/review-queue", headers=AUTH_HEADERS)
        detail_response = client.get(
            f"/api/review-queue/{raw_sms_id}", headers=AUTH_HEADERS
        )

    assert review_response.status_code == 200
    assert pending_response.json()["items"] == []
    assert detail_response.status_code == 200
    assert detail_response.json()["candidate"]["review_status"] == "reviewed"


def test_reviewing_missing_raw_sms_returns_404() -> None:
    with make_test_client() as (client, _session):
        response = client.post(
            "/api/review-queue/raw_sms_missing/review",
            headers=AUTH_HEADERS,
            json={"decision": "reviewed"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "review item not found"}


def test_review_queue_rejects_requests_without_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/review-queue")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import AuditEvent, LedgerTransaction, RawSmsMessage

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


def fake_sms_body(
    *,
    merchant: str = "MERCHANT_FOOD_1",
    account_clue: str = "BANK_1 a/c XX0000",
) -> str:
    return (
        Path("tests/fixtures/sms/golden/debit-upi.sms.txt")
        .read_text(encoding="utf-8")
        .replace("MERCHANT_FOOD_1", merchant)
        .replace("BANK_1 a/c XX0000", account_clue)
    )


def ingest_sms(
    client: TestClient,
    *,
    message_id: str = "fake-forwarder-msg-promote",
    merchant: str = "MERCHANT_FOOD_1",
    account_clue: str = "BANK_1 a/c XX0000",
) -> str:
    response = client.post(
        "/api/inbound-sms",
        headers=AUTH_HEADERS,
        json={
            "message_id": message_id,
            "sender": "FAKEBANK",
            "received_at": "2026-05-04T10:30:00Z",
            "body": fake_sms_body(merchant=merchant, account_clue=account_clue),
        },
    )
    assert response.status_code == 201
    return str(response.json()["raw_sms_id"])


def review_sms(client: TestClient, raw_sms_id: str, *, reason: str = "fake QA review") -> None:
    response = client.post(
        f"/api/review-queue/{raw_sms_id}/review",
        headers=AUTH_HEADERS,
        json={"decision": "reviewed", "reason": reason},
    )
    assert response.status_code == 200


def promote_sms(client: TestClient, raw_sms_id: str) -> Response:
    return client.post(
        f"/api/review-queue/{raw_sms_id}/promote",
        headers=AUTH_HEADERS,
        json={"reason": "fake ledger QA"},
    )


def test_reviewed_fake_sms_promotes_to_one_ledger_transaction_with_source_metadata() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client)
        review_sms(client, raw_sms_id)

        response = promote_sms(client, raw_sms_id)
        stored_transaction = session.scalar(select(LedgerTransaction))
        stored_raw_sms = session.get(RawSmsMessage, raw_sms_id)

    assert response.status_code == 201
    payload = response.json()
    assert stored_transaction is not None
    assert payload["status"] == "promoted"
    assert payload["ledger_transaction_id"] == stored_transaction.id
    assert stored_transaction.raw_sms_message_id == raw_sms_id
    assert stored_transaction.account_id == "acct_bank_1"
    assert str(stored_transaction.amount) == "480.00"
    assert stored_transaction.transaction_date.isoformat() == "2026-05-04"
    assert stored_transaction.transaction_type == "debit"
    assert stored_transaction.purpose == "expense"
    assert stored_transaction.category == "food_delivery"
    assert stored_transaction.merchant_raw == "MERCHANT_FOOD_1"
    assert stored_transaction.merchant_canonical == "Merchant Food 1"
    assert stored_transaction.source == "sms"
    assert stored_transaction.parsing_confidence == "high"
    assert stored_transaction.merchant_mapping_confidence == "high"
    assert stored_transaction.category_confidence == "high"
    assert stored_transaction.review_status == "reviewed"
    assert stored_transaction.duplicate_status == "unique"
    assert stored_transaction.ledger_status == "included"
    assert stored_transaction.source_metadata["raw_sms_id"] == raw_sms_id
    assert stored_transaction.source_metadata["external_message_id"] == "fake-forwarder-msg-promote"
    assert stored_transaction.source_metadata["parser_metadata"]["parser"] == "fake_upi_debit_v1"
    assert stored_transaction.source_metadata["rule_metadata"]["account_mapping"] == {
        "rule_id": "account_bank_1_masked_0000_v1",
        "matched_value": "BANK_1 a/c XX0000",
    }
    assert stored_transaction.source_metadata["review_metadata"]["reason"] == "fake QA review"
    assert stored_raw_sms is not None
    assert stored_raw_sms.body == fake_sms_body()
    assert stored_raw_sms.parser_output["promotion_metadata"]["ledger_transaction_id"] == (
        stored_transaction.id
    )


def test_promotion_creates_audit_event_with_transaction_and_raw_sms_context() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-audit")
        review_sms(client, raw_sms_id)

        response = promote_sms(client, raw_sms_id)
        audit_events = session.scalars(select(AuditEvent)).all()

    assert response.status_code == 201
    assert len(audit_events) == 1
    audit_event = audit_events[0]
    assert audit_event.actor_type == "user"
    assert audit_event.event_type == "ledger_transaction_promoted"
    assert audit_event.transaction_id == response.json()["ledger_transaction_id"]
    assert audit_event.field_changes["raw_sms_id"] == raw_sms_id
    assert audit_event.field_changes["external_message_id"] == "fake-forwarder-msg-audit"
    assert audit_event.reason == "fake ledger QA"


def test_unreviewed_candidate_cannot_be_promoted() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-unreviewed")

        response = promote_sms(client, raw_sms_id)
        transactions = session.scalars(select(LedgerTransaction)).all()

    assert response.status_code == 409
    assert response.json() == {"detail": "candidate must be reviewed before promotion"}
    assert transactions == []


def test_candidate_without_account_id_cannot_be_promoted() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(
            client,
            message_id="fake-forwarder-msg-missing-account",
            account_clue="BANK_UNKNOWN a/c XX9999",
        )
        review_sms(client, raw_sms_id)

        response = promote_sms(client, raw_sms_id)
        transactions = session.scalars(select(LedgerTransaction)).all()

    assert response.status_code == 422
    assert response.json() == {"detail": "candidate is missing account_id"}
    assert transactions == []


def test_candidate_without_amount_or_transaction_date_cannot_be_promoted() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-missing-fields")
        review_sms(client, raw_sms_id)
        raw_sms = session.get(RawSmsMessage, raw_sms_id)
        assert raw_sms is not None
        parser_output = dict(raw_sms.parser_output)
        parser_output.pop("amount")
        parser_output.pop("transaction_date")
        raw_sms.parser_output = parser_output
        session.add(raw_sms)
        session.commit()

        response = promote_sms(client, raw_sms_id)
        transactions = session.scalars(select(LedgerTransaction)).all()

    assert response.status_code == 422
    assert response.json() == {"detail": "candidate is missing amount, transaction_date"}
    assert transactions == []


def test_replaying_promotion_for_same_raw_sms_returns_existing_transaction_without_duplicate() -> (
    None
):
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-idempotent")
        review_sms(client, raw_sms_id)

        first_response = promote_sms(client, raw_sms_id)
        replay_response = promote_sms(client, raw_sms_id)
        transactions = session.scalars(select(LedgerTransaction)).all()
        audit_events = session.scalars(select(AuditEvent)).all()

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    assert replay_response.json()["status"] == "already_promoted"
    assert replay_response.json()["ledger_transaction_id"] == first_response.json()[
        "ledger_transaction_id"
    ]
    assert len(transactions) == 1
    assert len(audit_events) == 1


def test_promoting_missing_raw_sms_returns_404() -> None:
    with make_test_client() as (client, _session):
        response = promote_sms(client, "raw_sms_missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "review item not found"}


def test_promotion_rejects_requests_without_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.post("/api/review-queue/raw_sms_missing/promote", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}

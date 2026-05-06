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
from app.models import Account, AuditEvent, LedgerTransaction, RawSmsMessage

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


def fake_sms_body() -> str:
    return Path("tests/fixtures/sms/golden/debit-upi.sms.txt").read_text(
        encoding="utf-8"
    )


def ingest_sms(client: TestClient, *, message_id: str = "fake-forwarder-msg-correct") -> str:
    response = client.post(
        "/api/inbound-sms",
        headers=AUTH_HEADERS,
        json={
            "message_id": message_id,
            "sender": "FAKEBANK",
            "received_at": "2026-05-04T10:30:00Z",
            "body": fake_sms_body(),
        },
    )
    assert response.status_code == 201
    return str(response.json()["raw_sms_id"])


def review_sms(client: TestClient, raw_sms_id: str) -> None:
    response = client.post(
        f"/api/review-queue/{raw_sms_id}/review",
        headers=AUTH_HEADERS,
        json={"decision": "reviewed", "reason": "fake QA review"},
    )
    assert response.status_code == 200


def promote_sms(client: TestClient, raw_sms_id: str) -> str:
    response = client.post(
        f"/api/review-queue/{raw_sms_id}/promote",
        headers=AUTH_HEADERS,
        json={"reason": "fake ledger QA"},
    )
    assert response.status_code == 201
    return str(response.json()["ledger_transaction_id"])


def correct_candidate(
    client: TestClient,
    raw_sms_id: str,
    updates: dict[str, object],
    *,
    reason: str = "fake correction",
) -> Response:
    return client.patch(
        f"/api/review-queue/{raw_sms_id}/corrections",
        headers=AUTH_HEADERS,
        json={"updates": updates, "reason": reason},
    )


def test_candidate_correction_stores_history_without_deleting_parser_and_rule_metadata() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client)

        response = correct_candidate(
            client,
            raw_sms_id,
            {"merchant_canonical": "Corrected Merchant", "category": "groceries"},
            reason="merchant and category were wrong",
        )
        stored_raw_sms = session.get(RawSmsMessage, raw_sms_id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate"]["merchant_canonical"] == "Corrected Merchant"
    assert payload["candidate"]["category"] == "groceries"
    assert stored_raw_sms is not None
    assert stored_raw_sms.parser_output["parser_metadata"]["parser"] == "fake_upi_debit_v1"
    assert stored_raw_sms.parser_output["rule_metadata"]["merchant_mapping"] == {
        "rule_id": "merchant_food_1_v1",
        "matched_value": "MERCHANT_FOOD_1",
    }
    assert stored_raw_sms.parser_output["user_corrections"]["merchant_canonical"][
        "value"
    ] == "Corrected Merchant"
    assert stored_raw_sms.parser_output["user_corrections"]["category"]["value"] == "groceries"
    history = stored_raw_sms.parser_output["correction_history"]
    assert history[0]["field"] == "merchant_canonical"
    assert history[0]["before"] == "Merchant Food 1"
    assert history[0]["after"] == "Corrected Merchant"
    assert history[0]["reason"] == "merchant and category were wrong"
    assert history[0]["actor_type"] == "user"
    assert history[1]["field"] == "category"
    assert history[1]["before"] == "food_delivery"
    assert history[1]["after"] == "groceries"
    assert stored_raw_sms.parser_output["rule_candidate"]["source"] == "user_correction"
    assert {
        candidate["field"] for candidate in stored_raw_sms.parser_output["rule_candidate"]["fields"]
    } == {"merchant_canonical", "category"}


def test_promotion_uses_corrected_candidate_values_and_preserves_correction_metadata() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-promote-corrected")
        correction_response = correct_candidate(
            client,
            raw_sms_id,
            {
                "merchant_canonical": "Corrected Merchant",
                "category": "groceries",
                "purpose": "expense",
                "amount": "481.25",
                "transaction_date": "2026-05-05",
                "transaction_type": "debit",
                "account_id": "acct_bank_1",
            },
        )
        review_sms(client, raw_sms_id)

        ledger_transaction_id = promote_sms(client, raw_sms_id)
        stored_transaction = session.get(LedgerTransaction, ledger_transaction_id)

    assert correction_response.status_code == 200
    assert stored_transaction is not None
    assert stored_transaction.merchant_canonical == "Corrected Merchant"
    assert stored_transaction.category == "groceries"
    assert stored_transaction.purpose == "expense"
    assert str(stored_transaction.amount) == "481.25"
    assert stored_transaction.transaction_date.isoformat() == "2026-05-05"
    assert stored_transaction.transaction_type == "debit"
    assert stored_transaction.account_id == "acct_bank_1"
    assert stored_transaction.source_metadata["user_corrections"]["amount"]["value"] == "481.25"
    assert stored_transaction.source_metadata["correction_history"][0]["field"] == (
        "merchant_canonical"
    )
    assert stored_transaction.source_metadata["rule_candidate"]["source"] == "user_correction"


def test_promoted_ledger_transaction_correction_updates_fields_and_creates_audit_event() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-ledger-correct")
        review_sms(client, raw_sms_id)
        ledger_transaction_id = promote_sms(client, raw_sms_id)

        response = client.patch(
            f"/api/ledger-transactions/{ledger_transaction_id}/corrections",
            headers=AUTH_HEADERS,
            json={
                "updates": {
                    "merchant_canonical": "Corrected Ledger Merchant",
                    "category": "household",
                },
                "reason": "ledger fields corrected after promotion",
            },
        )
        stored_transaction = session.get(LedgerTransaction, ledger_transaction_id)
        audit_events = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "ledger_transaction_corrected")
        ).all()

    assert response.status_code == 200
    assert stored_transaction is not None
    assert stored_transaction.merchant_canonical == "Corrected Ledger Merchant"
    assert stored_transaction.category == "household"
    assert len(audit_events) == 1
    audit_event = audit_events[0]
    assert audit_event.transaction_id == ledger_transaction_id
    assert audit_event.actor_type == "user"
    assert audit_event.reason == "ledger fields corrected after promotion"
    assert audit_event.field_changes["merchant_canonical"] == {
        "before": "Merchant Food 1",
        "after": "Corrected Ledger Merchant",
    }
    assert audit_event.field_changes["category"] == {
        "before": "food_delivery",
        "after": "household",
    }


def test_invalid_candidate_correction_field_returns_422_without_mutation() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-invalid-correction")
        before = dict(session.get(RawSmsMessage, raw_sms_id).parser_output)  # type: ignore[union-attr]

        response = correct_candidate(client, raw_sms_id, {"ledger_status": "included"})
        after = session.get(RawSmsMessage, raw_sms_id).parser_output  # type: ignore[union-attr]

    assert response.status_code == 422
    assert response.json() == {"detail": "unsupported correction field: ledger_status"}
    assert after == before


def test_unknown_account_candidate_correction_returns_422_without_mutation() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-unknown-account")
        before = dict(session.get(RawSmsMessage, raw_sms_id).parser_output)  # type: ignore[union-attr]

        response = correct_candidate(client, raw_sms_id, {"account_id": "acct_missing"})
        after = session.get(RawSmsMessage, raw_sms_id).parser_output  # type: ignore[union-attr]

    assert response.status_code == 422
    assert response.json() == {"detail": "correction account_id is unknown"}
    assert after == before


def test_unknown_account_ledger_correction_returns_422_without_mutation() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-forwarder-msg-ledger-unknown-account")
        review_sms(client, raw_sms_id)
        ledger_transaction_id = promote_sms(client, raw_sms_id)
        session.add(
            Account(
                id="acct_existing_other",
                name="Existing Other",
                account_type="bank_account",
            )
        )
        session.commit()
        before = session.get(LedgerTransaction, ledger_transaction_id)
        assert before is not None
        before_account_id = before.account_id

        response = client.patch(
            f"/api/ledger-transactions/{ledger_transaction_id}/corrections",
            headers=AUTH_HEADERS,
            json={"updates": {"account_id": "acct_missing"}, "reason": "bad account"},
        )
        after = session.get(LedgerTransaction, ledger_transaction_id)

    assert response.status_code == 422
    assert response.json() == {"detail": "correction account_id is unknown"}
    assert after is not None
    assert after.account_id == before_account_id


def test_correction_endpoints_require_shared_secret() -> None:
    with make_test_client() as (client, _session):
        candidate_response = client.patch(
            "/api/review-queue/raw_sms_missing/corrections",
            json={"updates": {"category": "groceries"}},
        )
        ledger_response = client.patch(
            "/api/ledger-transactions/txn_missing/corrections",
            json={"updates": {"category": "groceries"}},
        )

    assert candidate_response.status_code == 401
    assert candidate_response.json() == {"detail": "unauthorized"}
    assert ledger_response.status_code == 401
    assert ledger_response.json() == {"detail": "unauthorized"}

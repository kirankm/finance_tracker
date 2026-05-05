from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, LedgerTransaction, RawSmsMessage
from tests.test_ledger_promotion import (
    AUTH_HEADERS,
    fake_sms_body,
    ingest_sms,
    make_test_client,
    promote_sms,
    review_sms,
)


def ingest_sms_with_body(
    client: TestClient,
    *,
    message_id: str,
    body: str,
) -> str:
    response = client.post(
        "/api/inbound-sms",
        headers=AUTH_HEADERS,
        json={
            "message_id": message_id,
            "sender": "FAKEBANK",
            "received_at": "2026-05-04T10:30:00Z",
            "body": body,
        },
    )
    assert response.status_code == 201
    return str(response.json()["raw_sms_id"])


def transactions_by_created_order(session: Session) -> list[LedgerTransaction]:
    return list(session.scalars(
        select(LedgerTransaction).order_by(LedgerTransaction.created_at, LedgerTransaction.id)
    ).all())


def test_unique_reviewed_sms_promotes_with_unique_duplicate_metadata() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-duplicate-unique")
        review_sms(client, raw_sms_id)

        response = promote_sms(client, raw_sms_id)
        transaction = session.scalar(select(LedgerTransaction))
        raw_sms = session.get(RawSmsMessage, raw_sms_id)

    assert response.status_code == 201
    assert response.json()["duplicate_status"] == "unique"
    assert response.json()["ledger_status"] == "included"
    assert transaction is not None
    assert transaction.duplicate_status == "unique"
    assert transaction.ledger_status == "included"
    assert transaction.source_metadata["duplicate_detection"] == {
        "status": "unique",
        "ledger_status": "included",
        "reason": "no_duplicate_match",
        "matched_transaction_id": None,
        "matched_raw_sms_id": None,
        "basis": [],
        "confidence": "high",
    }
    assert raw_sms is not None
    assert raw_sms.parser_output["duplicate_detection"]["status"] == "unique"


def test_same_reference_sms_promotes_as_exact_duplicate_and_is_excluded() -> None:
    with make_test_client() as (client, session):
        first_raw_sms_id = ingest_sms(client, message_id="fake-duplicate-exact-first")
        review_sms(client, first_raw_sms_id)
        first_response = promote_sms(client, first_raw_sms_id)

        second_raw_sms_id = ingest_sms(client, message_id="fake-duplicate-exact-second")
        review_sms(client, second_raw_sms_id)
        second_response = promote_sms(client, second_raw_sms_id)

        transactions = transactions_by_created_order(session)
        audit_events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
        second_raw_sms = session.get(RawSmsMessage, second_raw_sms_id)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["duplicate_status"] == "exact_duplicate"
    assert second_response.json()["ledger_status"] == "excluded"
    assert len(transactions) == 2
    first_transaction, second_transaction = transactions
    assert first_transaction.duplicate_status == "unique"
    assert first_transaction.ledger_status == "included"
    assert second_transaction.duplicate_status == "exact_duplicate"
    assert second_transaction.ledger_status == "excluded"
    assert second_transaction.source_metadata["duplicate_detection"] == {
        "status": "exact_duplicate",
        "ledger_status": "excluded",
        "reason": "same_reference_amount_date_account_and_type",
        "matched_transaction_id": first_transaction.id,
        "matched_raw_sms_id": first_raw_sms_id,
        "basis": [
            "account_id",
            "reference",
            "amount",
            "transaction_date",
            "transaction_type",
        ],
        "confidence": "high",
    }
    assert second_raw_sms is not None
    assert second_raw_sms.parser_output["duplicate_detection"]["matched_transaction_id"] == (
        first_transaction.id
    )
    assert len(audit_events) == 2
    assert audit_events[-1].field_changes["duplicate_status"] == "exact_duplicate"
    assert audit_events[-1].field_changes["ledger_status"] == "excluded"


def test_same_fingerprint_without_shared_reference_is_possible_duplicate() -> None:
    with make_test_client() as (client, session):
        first_raw_sms_id = ingest_sms(client, message_id="fake-duplicate-possible-first")
        review_sms(client, first_raw_sms_id)
        promote_sms(client, first_raw_sms_id)

        second_body = fake_sms_body().replace("Ref 123456.", "Ref 654321.")
        second_raw_sms_id = ingest_sms_with_body(
            client,
            message_id="fake-duplicate-possible-second",
            body=second_body,
        )
        review_sms(client, second_raw_sms_id)
        second_response = promote_sms(client, second_raw_sms_id)

        transactions = transactions_by_created_order(session)
        second_raw_sms = session.get(RawSmsMessage, second_raw_sms_id)

    assert second_response.status_code == 201
    assert second_response.json()["duplicate_status"] == "possible_duplicate"
    assert second_response.json()["ledger_status"] == "excluded"
    assert len(transactions) == 2
    first_transaction, second_transaction = transactions
    assert second_transaction.source_metadata["duplicate_detection"] == {
        "status": "possible_duplicate",
        "ledger_status": "excluded",
        "reason": "same_amount_date_account_type_and_merchant",
        "matched_transaction_id": first_transaction.id,
        "matched_raw_sms_id": first_raw_sms_id,
        "basis": [
            "account_id",
            "amount",
            "transaction_date",
            "transaction_type",
            "merchant_canonical",
        ],
        "confidence": "medium",
    }
    assert second_raw_sms is not None
    assert second_raw_sms.parser_output["duplicate_detection"]["status"] == "possible_duplicate"


def test_same_fingerprint_on_different_account_is_not_duplicate() -> None:
    with make_test_client() as (client, session):
        first_raw_sms_id = ingest_sms(client, message_id="fake-duplicate-account-first")
        review_sms(client, first_raw_sms_id)
        promote_sms(client, first_raw_sms_id)

        session.add(
            Account(
                id="acct_bank_2",
                name="Fake Bank 2",
                account_type="bank_account",
                balance_tracking=True,
            )
        )
        second_raw_sms_id = ingest_sms(
            client,
            message_id="fake-duplicate-account-second",
            account_clue="BANK_2 a/c XX2222",
        )
        review_sms(client, second_raw_sms_id)
        second_raw_sms = session.get(RawSmsMessage, second_raw_sms_id)
        assert second_raw_sms is not None
        parser_output = dict(second_raw_sms.parser_output)
        parser_output["account_id"] = "acct_bank_2"
        parser_output["confidence"] = {
            **parser_output["confidence"],
            "account_mapping": "high",
        }
        parser_output["rule_metadata"] = {
            **parser_output["rule_metadata"],
            "account_mapping": {
                "rule_id": "manual_fake_account_2_test",
                "matched_value": "BANK_2 a/c XX2222",
            },
        }
        second_raw_sms.parser_output = parser_output
        session.add(second_raw_sms)
        session.commit()

        second_response = promote_sms(client, second_raw_sms_id)
        transactions = transactions_by_created_order(session)

    assert second_response.status_code == 201
    assert second_response.json()["duplicate_status"] == "unique"
    assert second_response.json()["ledger_status"] == "included"
    assert len(transactions) == 2
    assert transactions[1].account_id == "acct_bank_2"
    assert transactions[1].duplicate_status == "unique"
    assert transactions[1].ledger_status == "included"
    assert transactions[1].amount == Decimal("480.00")


def test_same_raw_sms_replay_still_returns_existing_transaction_without_duplicate_audit() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-duplicate-replay")
        review_sms(client, raw_sms_id)

        first_response = promote_sms(client, raw_sms_id)
        replay_response = promote_sms(client, raw_sms_id)
        transactions = session.scalars(select(LedgerTransaction)).all()
        audit_events = session.scalars(select(AuditEvent)).all()

    assert first_response.status_code == 201
    assert replay_response.status_code == 200
    assert replay_response.json()["status"] == "already_promoted"
    assert replay_response.json()["duplicate_status"] == "unique"
    assert len(transactions) == 1
    assert len(audit_events) == 1

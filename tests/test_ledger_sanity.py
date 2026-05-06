from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, LedgerTransaction, RawSmsMessage
from tests.test_duplicate_detection import ingest_sms_with_body
from tests.test_ledger_promotion import (
    fake_sms_body,
    ingest_sms,
    make_test_client,
    promote_sms,
    review_sms,
)


def set_account_balance(session: Session, balance: str) -> None:
    account = session.get(Account, "acct_bank_1")
    if account is None:
        account = Account(
            id="acct_bank_1",
            name="Fake Bank 1",
            account_type="bank_account",
            balance_tracking=True,
        )
    account.current_balance = Decimal(balance)
    session.add(account)
    session.commit()


def update_candidate(raw_sms: RawSmsMessage, **changes: object) -> None:
    parser_output = dict(raw_sms.parser_output)
    parser_output.update(changes)
    raw_sms.parser_output = parser_output


def test_debit_without_available_balance_records_not_checked_metadata() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-ledger-sanity-no-balance")
        review_sms(client, raw_sms_id)
        raw_sms = session.get(RawSmsMessage, raw_sms_id)
        assert raw_sms is not None
        parser_output = dict(raw_sms.parser_output)
        parser_output.pop("available_balance")
        raw_sms.parser_output = parser_output
        session.add(raw_sms)
        session.commit()

        response = promote_sms(client, raw_sms_id)
        transaction = session.scalar(select(LedgerTransaction))
        raw_sms = session.get(RawSmsMessage, raw_sms_id)

    assert response.status_code == 201
    assert response.json()["ledger_sanity_status"] == "not_checked"
    assert transaction is not None
    assert transaction.ledger_status == "included"
    assert transaction.source_metadata["ledger_sanity"] == {
        "status": "not_checked",
        "ledger_status": "included",
        "reason": "available_balance_missing",
        "account_id": "acct_bank_1",
        "basis": ["available_balance"],
        "confidence": "low",
    }
    assert raw_sms is not None
    assert raw_sms.parser_output["ledger_sanity"]["status"] == "not_checked"


def test_debit_with_matching_available_balance_records_matched_metadata() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-ledger-sanity-debit-match")
        review_sms(client, raw_sms_id)
        set_account_balance(session, "50480.00")

        response = promote_sms(client, raw_sms_id)
        transaction = session.scalar(select(LedgerTransaction))
        raw_sms = session.get(RawSmsMessage, raw_sms_id)

    assert response.status_code == 201
    assert response.json()["ledger_sanity_status"] == "matched"
    assert transaction is not None
    assert transaction.ledger_status == "included"
    assert transaction.source_metadata["ledger_sanity"] == {
        "status": "matched",
        "ledger_status": "included",
        "reason": "available_balance_matches_expected_post_transaction_balance",
        "account_id": "acct_bank_1",
        "transaction_type": "debit",
        "starting_balance": "50480.00",
        "balance_impact": "-480.00",
        "expected_balance": "50000.00",
        "observed_balance": "50000.00",
        "mismatch_amount": "0.00",
        "basis": [
            "account.current_balance",
            "amount",
            "transaction_type",
            "available_balance",
        ],
        "confidence": "high",
    }
    assert raw_sms is not None
    assert raw_sms.parser_output["ledger_sanity"]["status"] == "matched"


def test_debit_with_mismatched_available_balance_is_reviewable_and_explainable() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-ledger-sanity-debit-mismatch")
        review_sms(client, raw_sms_id)
        set_account_balance(session, "51000.00")

        response = promote_sms(client, raw_sms_id)
        transaction = session.scalar(select(LedgerTransaction))
        raw_sms = session.get(RawSmsMessage, raw_sms_id)
        audit_event = session.scalar(select(AuditEvent))

    assert response.status_code == 201
    assert response.json()["ledger_status"] == "needs_review"
    assert response.json()["ledger_sanity_status"] == "mismatch"
    assert transaction is not None
    assert transaction.ledger_status == "needs_review"
    assert transaction.source_metadata["ledger_sanity"]["status"] == "mismatch"
    assert transaction.source_metadata["ledger_sanity"]["expected_balance"] == "50520.00"
    assert transaction.source_metadata["ledger_sanity"]["observed_balance"] == "50000.00"
    assert transaction.source_metadata["ledger_sanity"]["mismatch_amount"] == "-520.00"
    assert raw_sms is not None
    assert raw_sms.parser_output["ledger_sanity"]["status"] == "mismatch"
    assert raw_sms.parser_output["ledger_status"] == "needs_review"
    assert audit_event is not None
    assert audit_event.field_changes["ledger_sanity_status"] == "mismatch"
    assert audit_event.field_changes["ledger_status"] == "needs_review"


def test_credit_uses_positive_balance_impact() -> None:
    with make_test_client() as (client, session):
        raw_sms_id = ingest_sms(client, message_id="fake-ledger-sanity-credit-match")
        review_sms(client, raw_sms_id)
        set_account_balance(session, "49520.00")
        raw_sms = session.get(RawSmsMessage, raw_sms_id)
        assert raw_sms is not None
        update_candidate(
            raw_sms,
            transaction_type="credit",
            purpose="income",
            available_balance=50000,
            reference="credit123",
        )
        session.add(raw_sms)
        session.commit()

        response = promote_sms(client, raw_sms_id)
        transaction = session.scalar(select(LedgerTransaction))

    assert response.status_code == 201
    assert response.json()["ledger_sanity_status"] == "matched"
    assert transaction is not None
    assert transaction.transaction_type == "credit"
    assert transaction.source_metadata["ledger_sanity"]["balance_impact"] == "480.00"
    assert transaction.source_metadata["ledger_sanity"]["expected_balance"] == "50000.00"


def test_expected_balance_includes_prior_included_transactions() -> None:
    with make_test_client() as (client, session):
        first_raw_sms_id = ingest_sms(client, message_id="fake-ledger-sanity-prior-first")
        review_sms(client, first_raw_sms_id)
        set_account_balance(session, "50480.00")
        promote_sms(client, first_raw_sms_id)

        second_body = (
            fake_sms_body()
            .replace("Rs.480 debited", "Rs.100 debited")
            .replace("Avl Bal Rs.50000", "Avl Bal Rs.49900")
            .replace("Ref 123456", "Ref 999999")
        )
        second_raw_sms_id = ingest_sms_with_body(
            client,
            message_id="fake-ledger-sanity-prior-second",
            body=second_body,
        )
        review_sms(client, second_raw_sms_id)

        response = promote_sms(client, second_raw_sms_id)
        transactions = session.scalars(
            select(LedgerTransaction).order_by(LedgerTransaction.created_at)
        ).all()

    assert response.status_code == 201
    assert response.json()["ledger_sanity_status"] == "matched"
    assert len(transactions) == 2
    assert transactions[1].source_metadata["ledger_sanity"]["starting_balance"] == "50000.00"
    assert transactions[1].source_metadata["ledger_sanity"]["balance_impact"] == "-100.00"
    assert transactions[1].source_metadata["ledger_sanity"]["expected_balance"] == "49900.00"


def test_duplicate_promotion_does_not_apply_fresh_balance_impact() -> None:
    with make_test_client() as (client, session):
        first_raw_sms_id = ingest_sms(client, message_id="fake-ledger-sanity-duplicate-first")
        review_sms(client, first_raw_sms_id)
        set_account_balance(session, "50480.00")
        promote_sms(client, first_raw_sms_id)

        second_body = fake_sms_body().replace("Ref 123456.", "Ref 654321.")
        second_raw_sms_id = ingest_sms_with_body(
            client,
            message_id="fake-ledger-sanity-duplicate-second",
            body=second_body,
        )
        review_sms(client, second_raw_sms_id)

        response = promote_sms(client, second_raw_sms_id)
        transactions = session.scalars(
            select(LedgerTransaction).order_by(LedgerTransaction.created_at)
        ).all()
        second_raw_sms = session.get(RawSmsMessage, second_raw_sms_id)

    assert response.status_code == 201
    assert response.json()["duplicate_status"] == "possible_duplicate"
    assert response.json()["ledger_status"] == "excluded"
    assert response.json()["ledger_sanity_status"] == "not_checked"
    assert len(transactions) == 2
    second_transaction = transactions[1]
    assert second_transaction.source_metadata["ledger_sanity"] == {
        "status": "not_checked",
        "ledger_status": "excluded",
        "reason": "ledger_excluded_duplicate_not_balance_impacting",
        "account_id": "acct_bank_1",
        "basis": ["duplicate_status", "ledger_status"],
        "confidence": "high",
    }
    assert second_raw_sms is not None
    assert second_raw_sms.parser_output["ledger_sanity"]["reason"] == (
        "ledger_excluded_duplicate_not_balance_impacting"
    )

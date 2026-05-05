from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Base, LedgerTransaction


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_account_persists_required_fields_and_type() -> None:
    with make_session() as session:
        account = Account(
            id="acct_cash_wallet",
            name="Cash Wallet",
            account_type="cash",
            balance_tracking=True,
            current_balance=Decimal("4200.00"),
        )
        session.add(account)
        session.commit()

        stored = session.get(Account, "acct_cash_wallet")

    assert stored is not None
    assert stored.name == "Cash Wallet"
    assert stored.account_type == "cash"
    assert stored.balance_tracking is True
    assert stored.current_balance == Decimal("4200.00")


def test_transaction_persists_core_ledger_fields() -> None:
    with make_session() as session:
        account = Account(
            id="acct_hdfc_savings",
            name="HDFC Savings",
            account_type="bank_account",
        )
        transaction = LedgerTransaction(
            id="txn_swiggy_order",
            transaction_date=date(2026, 5, 4),
            amount=Decimal("480.00"),
            transaction_type="debit",
            purpose="expense",
            category="food_delivery",
            merchant_raw="UPI/SWIGGY/ORDER123",
            merchant_canonical="Swiggy",
            account=account,
            source="sms",
            parsing_confidence="high",
            merchant_mapping_confidence="high",
            category_confidence="medium",
            review_status="needs_review",
            duplicate_status="unique",
            ledger_status="included",
            source_metadata={"fixture": "debit-upi"},
        )
        session.add(transaction)
        session.commit()

        stored = session.scalar(
            select(LedgerTransaction).where(LedgerTransaction.id == "txn_swiggy_order")
        )

    assert stored is not None
    assert stored.account_id == "acct_hdfc_savings"
    assert stored.amount == Decimal("480.00")
    assert stored.transaction_type == "debit"
    assert stored.purpose == "expense"
    assert stored.source == "sms"
    assert stored.review_status == "needs_review"
    assert stored.duplicate_status == "unique"
    assert stored.ledger_status == "included"
    assert stored.source_metadata == {"fixture": "debit-upi"}


def test_audit_event_can_link_to_transaction_or_account_change() -> None:
    with make_session() as session:
        account = Account(
            id="acct_cash_wallet",
            name="Cash Wallet",
            account_type="cash",
        )
        transaction = LedgerTransaction(
            id="txn_manual_cash_spend",
            transaction_date=date(2026, 5, 5),
            amount=Decimal("120.00"),
            transaction_type="debit",
            purpose="expense",
            account=account,
            source="manual",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="included",
        )
        account_event = AuditEvent(
            id="audit_account_created",
            account=account,
            actor_type="system",
            event_type="account_created",
            field_changes={"name": {"after": "Cash Wallet"}},
        )
        transaction_event = AuditEvent(
            id="audit_transaction_created",
            transaction=transaction,
            actor_type="user",
            event_type="transaction_created",
            field_changes={"amount": {"after": "120.00"}},
        )
        session.add_all([account_event, transaction_event])
        session.commit()

        events = session.scalars(select(AuditEvent).order_by(AuditEvent.id)).all()

    assert [event.id for event in events] == [
        "audit_account_created",
        "audit_transaction_created",
    ]
    assert events[0].account_id == "acct_cash_wallet"
    assert events[0].transaction_id is None
    assert events[1].transaction_id == "txn_manual_cash_spend"
    assert events[1].account_id is None


def test_soft_deleted_ledger_records_remain_queryable_with_metadata() -> None:
    deleted_at = datetime(2026, 5, 5, 10, 30, tzinfo=UTC)

    with make_session() as session:
        account = Account(
            id="acct_cash_wallet",
            name="Cash Wallet",
            account_type="cash",
            deleted_at=deleted_at,
            deleted_reason="duplicate test account",
        )
        transaction = LedgerTransaction(
            id="txn_deleted_adjustment",
            transaction_date=date(2026, 5, 5),
            amount=Decimal("1.00"),
            transaction_type="cash_adjustment",
            purpose="cash_update",
            account=account,
            source="manual",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="excluded",
            deleted_at=deleted_at,
            deleted_reason="entered by mistake",
        )
        session.add(transaction)
        session.commit()

        stored_account = session.get(Account, "acct_cash_wallet")
        stored_transaction = session.get(LedgerTransaction, "txn_deleted_adjustment")

    assert stored_account is not None
    assert stored_account.deleted_at == deleted_at
    assert stored_account.deleted_reason == "duplicate test account"
    assert stored_transaction is not None
    assert stored_transaction.deleted_at == deleted_at
    assert stored_transaction.deleted_reason == "entered by mistake"

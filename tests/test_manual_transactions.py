from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import Account, AuditEvent, Category, LedgerTransaction

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


def seed_account_and_category(session: Session) -> None:
    session.add_all(
        [
            Account(id="acct_cash_wallet", name="Cash Wallet", account_type="cash"),
            Category(id="food_delivery", name="Food Delivery"),
        ]
    )
    session.commit()


def create_manual_transaction(client: TestClient) -> Response:
    return client.post(
        "/api/manual-transactions",
        headers=AUTH_HEADERS,
        json={
            "transaction_date": "2026-05-06",
            "amount": "125.50",
            "transaction_type": "debit",
            "purpose": "expense",
            "category": "food_delivery",
            "merchant_raw": "FAKE_MANUAL_FOOD",
            "merchant_canonical": "Fake Manual Food",
            "account_id": "acct_cash_wallet",
            "reason": "fake manual entry",
        },
    )


def test_manual_transaction_endpoints_require_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.post("/api/manual-transactions", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_create_manual_transaction_persists_source_and_audit_event() -> None:
    with make_test_client() as (client, session):
        seed_account_and_category(session)

        response = create_manual_transaction(client)
        stored = session.scalar(select(LedgerTransaction))
        audit_events = session.scalars(select(AuditEvent)).all()

    assert response.status_code == 201
    assert stored is not None
    assert response.json()["id"] == stored.id
    assert stored.source == "manual"
    assert stored.raw_sms_message_id is None
    assert stored.transaction_date == date(2026, 5, 6)
    assert stored.amount == Decimal("125.50")
    assert stored.account_id == "acct_cash_wallet"
    assert stored.category == "food_delivery"
    assert stored.review_status == "reviewed"
    assert stored.duplicate_status == "unique"
    assert stored.ledger_status == "included"
    assert stored.source_metadata["manual_entry"]["actor_type"] == "user"
    assert len(audit_events) == 1
    assert audit_events[0].event_type == "manual_transaction_created"
    assert audit_events[0].transaction_id == stored.id
    assert audit_events[0].reason == "fake manual entry"


def test_create_manual_transaction_validates_account_and_active_category() -> None:
    with make_test_client() as (client, session):
        session.add_all(
            [
                Account(id="acct_cash_wallet", name="Cash Wallet", account_type="cash"),
                Category(id="inactive_category", name="Inactive", deleted_reason="cleanup"),
            ]
        )
        session.flush()
        deleted = session.get(Category, "inactive_category")
        assert deleted is not None
        deleted.deleted_at = datetime(2026, 5, 6, tzinfo=UTC)
        session.commit()

        missing_account_response = client.post(
            "/api/manual-transactions",
            headers=AUTH_HEADERS,
            json={
                "transaction_date": "2026-05-06",
                "amount": "125.50",
                "transaction_type": "debit",
                "purpose": "expense",
                "account_id": "acct_missing",
            },
        )
        deleted_category_response = client.post(
            "/api/manual-transactions",
            headers=AUTH_HEADERS,
            json={
                "transaction_date": "2026-05-06",
                "amount": "125.50",
                "transaction_type": "debit",
                "purpose": "expense",
                "category": "inactive_category",
                "account_id": "acct_cash_wallet",
            },
        )

    assert missing_account_response.status_code == 422
    assert missing_account_response.json() == {"detail": "account_id is unknown"}
    assert deleted_category_response.status_code == 422
    assert deleted_category_response.json() == {"detail": "category is not active"}


def test_create_manual_transaction_rejects_non_positive_amount() -> None:
    with make_test_client() as (client, session):
        seed_account_and_category(session)

        response = client.post(
            "/api/manual-transactions",
            headers=AUTH_HEADERS,
            json={
                "transaction_date": "2026-05-06",
                "amount": "0.00",
                "transaction_type": "debit",
                "purpose": "expense",
                "account_id": "acct_cash_wallet",
            },
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "amount must be greater than zero"}


def test_update_manual_transaction_records_before_after_history() -> None:
    with make_test_client() as (client, session):
        seed_account_and_category(session)
        create_response = create_manual_transaction(client)

        update_response = client.patch(
            f"/api/manual-transactions/{create_response.json()['id']}",
            headers=AUTH_HEADERS,
            json={
                "updates": {
                    "amount": "130.00",
                    "merchant_canonical": "Corrected Fake Manual Food",
                },
                "reason": "fake correction",
            },
        )
        stored = session.get(LedgerTransaction, create_response.json()["id"])
        audit_events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()

    assert update_response.status_code == 200
    assert stored is not None
    assert stored.amount == Decimal("130.00")
    assert stored.merchant_canonical == "Corrected Fake Manual Food"
    assert [event.event_type for event in audit_events] == [
        "manual_transaction_created",
        "manual_transaction_updated",
    ]
    assert audit_events[1].field_changes["amount"] == {
        "before": "125.50",
        "after": "130.00",
    }
    assert audit_events[1].reason == "fake correction"


def test_manual_transaction_status_delete_and_restore_flows_are_audited() -> None:
    with make_test_client() as (client, session):
        seed_account_and_category(session)
        create_response = create_manual_transaction(client)
        transaction_id = create_response.json()["id"]

        ignore_response = client.post(
            f"/api/manual-transactions/{transaction_id}/ignore",
            headers=AUTH_HEADERS,
            json={"reason": "fake ignore"},
        )
        duplicate_response = client.post(
            f"/api/manual-transactions/{transaction_id}/mark-duplicate",
            headers=AUTH_HEADERS,
            json={"reason": "fake duplicate"},
        )
        delete_response = client.request(
            "DELETE",
            f"/api/manual-transactions/{transaction_id}",
            headers=AUTH_HEADERS,
            json={"reason": "fake delete"},
        )
        restore_response = client.post(
            f"/api/manual-transactions/{transaction_id}/restore",
            headers=AUTH_HEADERS,
            json={"reason": "fake restore"},
        )
        stored = session.get(LedgerTransaction, transaction_id)
        audit_events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()

    assert ignore_response.status_code == 200
    assert ignore_response.json()["ledger_status"] == "excluded"
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["duplicate_status"] == "confirmed_duplicate"
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_at"] is not None
    assert restore_response.status_code == 200
    assert restore_response.json()["deleted_at"] is None
    assert stored is not None
    assert stored.deleted_at is None
    assert stored.deleted_reason is None
    assert stored.ledger_status == "excluded"
    assert stored.duplicate_status == "confirmed_duplicate"
    assert [event.event_type for event in audit_events] == [
        "manual_transaction_created",
        "manual_transaction_ignored",
        "manual_transaction_marked_duplicate",
        "manual_transaction_deleted",
        "manual_transaction_restored",
    ]


def test_deleted_manual_transaction_cannot_be_updated_until_restored() -> None:
    with make_test_client() as (client, session):
        seed_account_and_category(session)
        create_response = create_manual_transaction(client)
        transaction_id = create_response.json()["id"]
        client.request(
            "DELETE",
            f"/api/manual-transactions/{transaction_id}",
            headers=AUTH_HEADERS,
            json={"reason": "fake delete"},
        )

        update_response = client.patch(
            f"/api/manual-transactions/{transaction_id}",
            headers=AUTH_HEADERS,
            json={"updates": {"amount": "126.00"}},
        )
        ignore_response = client.post(
            f"/api/manual-transactions/{transaction_id}/ignore",
            headers=AUTH_HEADERS,
            json={"reason": "should fail"},
        )
        restore_response = client.post(
            f"/api/manual-transactions/{transaction_id}/restore",
            headers=AUTH_HEADERS,
            json={"reason": "fake restore"},
        )
        second_restore_response = client.post(
            f"/api/manual-transactions/{transaction_id}/restore",
            headers=AUTH_HEADERS,
            json={"reason": "should fail"},
        )
        stored = session.get(LedgerTransaction, transaction_id)

    assert update_response.status_code == 409
    assert update_response.json() == {"detail": "transaction is deleted"}
    assert ignore_response.status_code == 409
    assert ignore_response.json() == {"detail": "transaction is deleted"}
    assert restore_response.status_code == 200
    assert second_restore_response.status_code == 409
    assert second_restore_response.json() == {"detail": "transaction is not deleted"}
    assert stored is not None
    assert stored.amount == Decimal("125.50")


def test_manual_endpoints_reject_sms_derived_transactions() -> None:
    with make_test_client() as (client, session):
        account = Account(id="acct_bank_1", name="Fake Bank", account_type="bank_account")
        sms_transaction = LedgerTransaction(
            id="txn_sms_1",
            transaction_date=date(2026, 5, 6),
            amount=Decimal("50.00"),
            transaction_type="debit",
            purpose="expense",
            account=account,
            source="sms",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="included",
        )
        session.add(sms_transaction)
        session.commit()

        response = client.patch(
            "/api/manual-transactions/txn_sms_1",
            headers=AUTH_HEADERS,
            json={"updates": {"amount": "51.00"}},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "transaction is not manual"}

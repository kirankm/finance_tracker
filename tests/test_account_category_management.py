from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import Account, AuditEvent, LedgerTransaction

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


def test_account_management_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/accounts")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_create_list_and_update_account_with_audit_event() -> None:
    with make_test_client() as (client, session):
        create_response = client.post(
            "/api/accounts",
            headers=AUTH_HEADERS,
            json={
                "id": "acct_wallet_1",
                "name": "Fake Wallet",
                "account_type": "upi_wallet",
                "balance_tracking": True,
                "current_balance": "1200.00",
            },
        )
        update_response = client.patch(
            "/api/accounts/acct_wallet_1",
            headers=AUTH_HEADERS,
            json={"name": "Updated Fake Wallet", "current_balance": "1300.00"},
        )
        list_response = client.get("/api/accounts", headers=AUTH_HEADERS)
        audit_events = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "account_updated")
        ).all()

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == "acct_wallet_1"
    assert list_response.json()["items"][0]["name"] == "Updated Fake Wallet"
    assert len(audit_events) == 1
    assert audit_events[0].account_id == "acct_wallet_1"
    assert audit_events[0].field_changes["name"] == {
        "before": "Fake Wallet",
        "after": "Updated Fake Wallet",
    }
    assert audit_events[0].field_changes["current_balance"] == {
        "before": "1200.00",
        "after": "1300.00",
    }


def test_category_management_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/categories")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_create_list_update_and_soft_delete_unused_category() -> None:
    with make_test_client() as (client, session):
        create_response = client.post(
            "/api/categories",
            headers=AUTH_HEADERS,
            json={
                "id": "groceries",
                "name": "Groceries",
                "intent_type": "committed",
            },
        )
        update_response = client.patch(
            "/api/categories/groceries",
            headers=AUTH_HEADERS,
            json={"name": "House Groceries", "intent_type": "controllable"},
        )
        delete_response = client.request(
            "DELETE",
            "/api/categories/groceries",
            headers=AUTH_HEADERS,
            json={"reason": "fake cleanup"},
        )
        list_response = client.get("/api/categories?include_deleted=true", headers=AUTH_HEADERS)
        audit_events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type.in_(["category_updated", "category_deleted"])
            )
        ).all()

    assert create_response.status_code == 201
    assert create_response.json()["intent_type"] == "committed"
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "House Groceries"
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_reason"] == "fake cleanup"
    assert list_response.json()["items"][0]["deleted_at"] is not None
    assert [event.event_type for event in audit_events] == [
        "category_updated",
        "category_deleted",
    ]
    assert audit_events[0].field_changes["name"] == {
        "before": "Groceries",
        "after": "House Groceries",
    }
    assert audit_events[1].field_changes["deleted_reason"] == {
        "before": None,
        "after": "fake cleanup",
    }


def test_category_used_by_active_transaction_cannot_be_deleted() -> None:
    with make_test_client() as (client, session):
        client.post(
            "/api/categories",
            headers=AUTH_HEADERS,
            json={"id": "food_delivery", "name": "Food Delivery"},
        )
        account = Account(
            id="acct_bank_1",
            name="Fake Bank 1",
            account_type="bank_account",
        )
        transaction = LedgerTransaction(
            id="txn_food",
            transaction_date=date(2026, 5, 4),
            amount=Decimal("480.00"),
            transaction_type="debit",
            purpose="expense",
            category="food_delivery",
            account=account,
            source="sms",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="included",
        )
        session.add(transaction)
        session.commit()

        response = client.request(
            "DELETE",
            "/api/categories/food_delivery",
            headers=AUTH_HEADERS,
            json={"reason": "should fail"},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "category is used by active ledger transactions"}

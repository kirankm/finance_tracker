from collections.abc import Generator
from contextlib import contextmanager
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


def test_cash_balance_update_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.post("/api/accounts/acct_cash/cash-balance", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_cash_balance_update_stores_balance_and_audit_event() -> None:
    with make_test_client() as (client, session):
        session.add(
            Account(
                id="acct_cash_wallet",
                name="Cash Wallet",
                account_type="cash",
                balance_tracking=True,
                current_balance=Decimal("5000.00"),
            )
        )
        session.commit()

        response = client.post(
            "/api/accounts/acct_cash_wallet/cash-balance",
            headers=AUTH_HEADERS,
            json={
                "reported_balance": "4200.00",
                "reported_on": "2026-05-06",
                "record_difference_as_adjustment": False,
                "reason": "fake cash count",
            },
        )
        account = session.get(Account, "acct_cash_wallet")
        transactions = session.scalars(select(LedgerTransaction)).all()
        audit_events = session.scalars(select(AuditEvent)).all()

    assert response.status_code == 200
    assert response.json()["expected_balance"] == "5000.00"
    assert response.json()["reported_balance"] == "4200.00"
    assert response.json()["difference"] == "800.00"
    assert response.json()["adjustment_transaction_id"] is None
    assert account is not None
    assert account.current_balance == Decimal("4200.00")
    assert account.last_manual_update is not None
    assert str(account.last_manual_update) == "2026-05-06"
    assert transactions == []
    assert len(audit_events) == 1
    assert audit_events[0].event_type == "cash_balance_updated"
    assert audit_events[0].account_id == "acct_cash_wallet"


def test_cash_balance_update_rejects_missing_or_non_cash_account() -> None:
    with make_test_client() as (client, session):
        session.add(Account(id="acct_bank_1", name="Fake Bank", account_type="bank_account"))
        session.commit()

        missing_response = client.post(
            "/api/accounts/acct_missing/cash-balance",
            headers=AUTH_HEADERS,
            json={"reported_balance": "100.00", "reported_on": "2026-05-06"},
        )
        non_cash_response = client.post(
            "/api/accounts/acct_bank_1/cash-balance",
            headers=AUTH_HEADERS,
            json={"reported_balance": "100.00", "reported_on": "2026-05-06"},
        )

    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "account not found"}
    assert non_cash_response.status_code == 409
    assert non_cash_response.json() == {"detail": "account is not a cash account"}


def test_cash_balance_update_rejects_negative_reported_balance() -> None:
    with make_test_client() as (client, session):
        session.add(Account(id="acct_cash_wallet", name="Cash Wallet", account_type="cash"))
        session.commit()

        response = client.post(
            "/api/accounts/acct_cash_wallet/cash-balance",
            headers=AUTH_HEADERS,
            json={"reported_balance": "-1.00", "reported_on": "2026-05-06"},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "reported_balance must not be negative"}


def test_cash_shortfall_can_create_audited_adjustment_transaction() -> None:
    with make_test_client() as (client, session):
        session.add(
            Account(
                id="acct_cash_wallet",
                name="Cash Wallet",
                account_type="cash",
                balance_tracking=True,
                current_balance=Decimal("5000.00"),
            )
        )
        session.commit()

        response = client.post(
            "/api/accounts/acct_cash_wallet/cash-balance",
            headers=AUTH_HEADERS,
            json={
                "reported_balance": "4200.00",
                "reported_on": "2026-05-06",
                "record_difference_as_adjustment": True,
                "reason": "fake cash shortfall",
            },
        )
        transaction = session.scalar(select(LedgerTransaction))
        audit_events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()

    assert response.status_code == 200
    assert transaction is not None
    assert response.json()["adjustment_transaction_id"] == transaction.id
    assert transaction.account_id == "acct_cash_wallet"
    assert transaction.amount == Decimal("800.00")
    assert transaction.transaction_type == "cash_adjustment"
    assert transaction.purpose == "cash_update"
    assert transaction.category == "cash_spend"
    assert transaction.source == "manual"
    assert transaction.ledger_status == "included"
    assert transaction.source_metadata["cash_adjustment"]["direction"] == "shortfall"
    assert [event.event_type for event in audit_events] == [
        "cash_adjustment_created",
        "cash_balance_updated",
    ]


def test_zero_difference_cash_update_does_not_create_adjustment() -> None:
    with make_test_client() as (client, session):
        session.add(
            Account(
                id="acct_cash_wallet",
                name="Cash Wallet",
                account_type="cash",
                current_balance=Decimal("4200.00"),
            )
        )
        session.commit()

        response = client.post(
            "/api/accounts/acct_cash_wallet/cash-balance",
            headers=AUTH_HEADERS,
            json={
                "reported_balance": "4200.00",
                "reported_on": "2026-05-06",
                "record_difference_as_adjustment": True,
            },
        )
        transactions = session.scalars(select(LedgerTransaction)).all()

    assert response.status_code == 200
    assert response.json()["difference"] == "0.00"
    assert response.json()["adjustment_transaction_id"] is None
    assert transactions == []

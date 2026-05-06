from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import Account, LedgerTransaction

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


def seed_analysis_data(session: Session) -> None:
    bank = Account(id="acct_bank_1", name="Fake Bank", account_type="bank_account")
    cash = Account(id="acct_cash_wallet", name="Cash Wallet", account_type="cash")
    session.add_all([bank, cash])
    session.flush()
    rows = [
        transaction("txn_food", date(2026, 5, 4), "100.00", "expense", "food_delivery", bank),
        transaction("txn_grocery", date(2026, 5, 5), "50.00", "expense", "groceries", cash),
        transaction("txn_unknown", date(2026, 5, 6), "5.00", "expense", None, bank),
        transaction(
            "txn_salary",
            date(2026, 5, 1),
            "1000.00",
            "income",
            "salary",
            bank,
            transaction_type="credit",
        ),
        transaction("txn_investment", date(2026, 5, 7), "300.00", "investment", "investment", bank),
        transaction("txn_savings", date(2026, 5, 8), "150.00", "savings", "savings", bank),
        transaction("txn_transfer", date(2026, 5, 9), "200.00", "transfer", "transfer", bank),
        transaction(
            "txn_refund",
            date(2026, 5, 10),
            "20.00",
            "refund",
            "refund",
            bank,
            transaction_type="refund",
        ),
        transaction(
            "txn_reversal",
            date(2026, 5, 11),
            "10.00",
            "reversal",
            "reversal",
            bank,
            transaction_type="reversal",
        ),
        transaction(
            "txn_cash_update",
            date(2026, 5, 12),
            "25.00",
            "cash_update",
            "cash_spend",
            cash,
            transaction_type="cash_adjustment",
        ),
        transaction(
            "txn_duplicate_excluded",
            date(2026, 5, 13),
            "999.00",
            "expense",
            "shopping",
            bank,
            duplicate_status="possible_duplicate",
            ledger_status="excluded",
        ),
        transaction(
            "txn_ignored_excluded",
            date(2026, 5, 14),
            "777.00",
            "expense",
            "shopping",
            bank,
            review_status="ignored",
            ledger_status="excluded",
        ),
        transaction(
            "txn_needs_review",
            date(2026, 5, 15),
            "60.00",
            "expense",
            "medical",
            bank,
            review_status="needs_review",
            ledger_status="needs_review",
        ),
        transaction(
            "txn_deleted",
            date(2026, 5, 16),
            "888.00",
            "expense",
            "shopping",
            bank,
            deleted_at=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        ),
        transaction("txn_other_month", date(2026, 6, 1), "333.00", "expense", "travel", bank),
    ]
    session.add_all(rows)
    session.commit()


def transaction(
    transaction_id: str,
    transaction_date: date,
    amount: str,
    purpose: str,
    category: str | None,
    account: Account,
    *,
    transaction_type: str = "debit",
    review_status: str = "reviewed",
    duplicate_status: str = "unique",
    ledger_status: str = "included",
    deleted_at: datetime | None = None,
) -> LedgerTransaction:
    return LedgerTransaction(
        id=transaction_id,
        transaction_date=transaction_date,
        amount=Decimal(amount),
        transaction_type=transaction_type,
        purpose=purpose,
        category=category,
        merchant_raw=f"FAKE_{transaction_id}",
        merchant_canonical=f"Fake {transaction_id}",
        account=account,
        source="manual",
        review_status=review_status,
        duplicate_status=duplicate_status,
        ledger_status=ledger_status,
        deleted_at=deleted_at,
        source_metadata={"fixture": "analysis"},
    )


def test_analysis_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/analysis/summary", params={"month": "2026-05"})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_monthly_analysis_reports_deterministic_expense_income_and_special_totals() -> None:
    with make_test_client() as (client, session):
        seed_analysis_data(session)

        response = client.get(
            "/api/analysis/summary",
            headers=AUTH_HEADERS,
            params={"month": "2026-05"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == {
        "date_from": "2026-05-01",
        "date_to": "2026-05-31",
        "month": "2026-05",
    }
    assert payload["income_vs_expense"] == {
        "income": "1000.00",
        "normal_expense": "155.00",
    }
    assert payload["spending_by_category"] == [
        {"category": "food_delivery", "total": "100.00", "count": 1},
        {"category": "groceries", "total": "50.00", "count": 1},
        {"category": "unknown", "total": "5.00", "count": 1},
    ]
    assert payload["spending_by_account"] == [
        {"account_id": "acct_bank_1", "account_name": "Fake Bank", "total": "105.00", "count": 2},
        {
            "account_id": "acct_cash_wallet",
            "account_name": "Cash Wallet",
            "total": "50.00",
            "count": 1,
        },
    ]
    assert payload["separated_totals"] == {
        "investment": {"total": "300.00", "count": 1},
        "savings": {"total": "150.00", "count": 1},
        "transfer": {"total": "200.00", "count": 1},
        "refund": {"total": "20.00", "count": 1},
        "reversal": {"total": "10.00", "count": 1},
        "cash_update": {"total": "25.00", "count": 1},
    }
    assert payload["cash_balance_changes"] == {"total": "25.00", "count": 1}
    assert payload["other_included"] == {"total": "0.00", "count": 0}


def test_analysis_excludes_duplicate_ignored_deleted_and_review_needed_from_totals() -> None:
    with make_test_client() as (client, session):
        seed_analysis_data(session)

        response = client.get(
            "/api/analysis/summary",
            headers=AUTH_HEADERS,
            params={"month": "2026-05"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_counts"] == {
        "review_needed": 1,
        "unmapped_category": 1,
        "unmapped_merchant": 0,
        "excluded_from_totals": 4,
    }
    response_text = response.text
    assert "999.00" not in response_text
    assert "777.00" not in response_text
    assert "888.00" not in response_text
    assert "333.00" not in response_text


def test_analysis_accepts_explicit_date_range() -> None:
    with make_test_client() as (client, session):
        seed_analysis_data(session)

        response = client.get(
            "/api/analysis/summary",
            headers=AUTH_HEADERS,
            params={"date_from": "2026-05-04", "date_to": "2026-05-05"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == {
        "date_from": "2026-05-04",
        "date_to": "2026-05-05",
        "month": None,
    }
    assert payload["income_vs_expense"]["normal_expense"] == "150.00"

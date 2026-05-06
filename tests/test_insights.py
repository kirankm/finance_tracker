from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from fastapi.testclient import TestClient
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


def seed_insight_data(session: Session) -> None:
    bank = Account(id="acct_bank_1", name="Fake Bank", account_type="bank_account")
    cash = Account(id="acct_cash_wallet", name="Cash Wallet", account_type="cash")
    raw_sms = RawSmsMessage(
        id="raw_sms_insight",
        external_message_id="fake-insight-sms",
        sender="FAKEBANK",
        received_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
        body="PRIVATE INSIGHT SMS BODY MUST NOT LEAK",
        source="external_forwarder",
        processing_status="candidate_created",
        parser_output={"review_status": "reviewed"},
    )
    rows = [
        transaction(
            "txn_unmapped",
            date(2026, 5, 4),
            "25.00",
            bank,
            category=None,
            merchant_raw=None,
            merchant_canonical=None,
            raw_sms_message=raw_sms,
        ),
        transaction(
            "txn_possible_duplicate",
            date(2026, 5, 5),
            "100.00",
            bank,
            duplicate_status="possible_duplicate",
            ledger_status="excluded",
            source_metadata={"duplicate_detection": {"status": "possible_duplicate"}},
        ),
        transaction(
            "txn_ledger_mismatch",
            date(2026, 5, 6),
            "60.00",
            bank,
            ledger_status="needs_review",
            source_metadata={"ledger_sanity": {"status": "mismatch"}},
        ),
        transaction(
            "txn_cash_mismatch",
            date(2026, 5, 7),
            "40.00",
            cash,
            transaction_type="cash_adjustment",
            purpose="cash_update",
            category="cash_spend",
            source_metadata={"cash_adjustment": {"difference": "40.00"}},
        ),
        transaction(
            "txn_food_current",
            date(2026, 5, 8),
            "200.00",
            bank,
            category="food_delivery",
        ),
        transaction(
            "txn_food_previous",
            date(2026, 4, 8),
            "50.00",
            bank,
            category="food_delivery",
        ),
    ]
    session.add_all([bank, cash, raw_sms, *rows])
    session.commit()


def transaction(
    transaction_id: str,
    transaction_date: date,
    amount: str,
    account: Account,
    *,
    transaction_type: str = "debit",
    purpose: str = "expense",
    category: str | None = "shopping",
    merchant_raw: str | None = None,
    merchant_canonical: str | None = None,
    duplicate_status: str = "unique",
    ledger_status: str = "included",
    source_metadata: dict[str, object] | None = None,
    raw_sms_message: RawSmsMessage | None = None,
) -> LedgerTransaction:
    return LedgerTransaction(
        id=transaction_id,
        transaction_date=transaction_date,
        amount=Decimal(amount),
        transaction_type=transaction_type,
        purpose=purpose,
        category=category,
        merchant_raw=merchant_raw if merchant_raw is not None else f"FAKE_{transaction_id}",
        merchant_canonical=(
            merchant_canonical if merchant_canonical is not None else f"Fake {transaction_id}"
        ),
        account=account,
        raw_sms_message=raw_sms_message,
        source="sms" if raw_sms_message is not None else "manual",
        review_status="reviewed",
        duplicate_status=duplicate_status,
        ledger_status=ledger_status,
        source_metadata=source_metadata or {"fixture": "insights"},
    )


def insight_types(payload: dict[str, Any]) -> set[str]:
    items = cast(list[dict[str, Any]], payload["items"])
    return {str(insight["type"]) for insight in items}


def test_insights_require_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/insights", params={"month": "2026-05"})

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_insights_are_deterministic_traceable_and_privacy_conscious() -> None:
    with make_test_client() as (client, session):
        seed_insight_data(session)

        response = client.get(
            "/api/insights",
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
    assert insight_types(payload) == {
        "unmapped_transactions",
        "possible_duplicates",
        "ledger_mismatches",
        "cash_mismatches",
        "notable_category_change",
    }
    for insight in payload["items"]:
        assert insight["id"].startswith("insight_")
        assert insight["state"] == "active"
        assert insight["transaction_ids"]
    assert "PRIVATE INSIGHT SMS BODY" not in response.text


def test_insight_dismiss_and_review_are_audited_and_affect_state() -> None:
    with make_test_client() as (client, session):
        seed_insight_data(session)
        initial_response = client.get(
            "/api/insights",
            headers=AUTH_HEADERS,
            params={"month": "2026-05"},
        )
        insights = initial_response.json()["items"]
        dismissed_id = insights[0]["id"]
        reviewed_id = insights[1]["id"]

        dismiss_response = client.post(
            f"/api/insights/{dismissed_id}/dismiss",
            headers=AUTH_HEADERS,
            json={"reason": "fake dismiss"},
        )
        review_response = client.post(
            f"/api/insights/{reviewed_id}/review",
            headers=AUTH_HEADERS,
            json={"reason": "fake review"},
        )
        default_response = client.get(
            "/api/insights",
            headers=AUTH_HEADERS,
            params={"month": "2026-05"},
        )
        included_response = client.get(
            "/api/insights",
            headers=AUTH_HEADERS,
            params={
                "month": "2026-05",
                "include_dismissed": "true",
                "include_reviewed": "true",
            },
        )
        audit_events = session.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()

    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["state"] == "dismissed"
    assert review_response.status_code == 200
    assert review_response.json()["state"] == "reviewed"
    assert dismissed_id not in {insight["id"] for insight in default_response.json()["items"]}
    assert reviewed_id not in {insight["id"] for insight in default_response.json()["items"]}
    included_by_id = {insight["id"]: insight for insight in included_response.json()["items"]}
    assert included_by_id[dismissed_id]["state"] == "dismissed"
    assert included_by_id[reviewed_id]["state"] == "reviewed"
    assert [event.event_type for event in audit_events] == [
        "insight_dismissed",
        "insight_reviewed",
    ]
    assert audit_events[0].field_changes["insight_id"] == dismissed_id
    assert audit_events[1].field_changes["insight_id"] == reviewed_id

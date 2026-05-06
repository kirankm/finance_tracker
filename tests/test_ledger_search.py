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


def seed_ledger_search_data(session: Session) -> None:
    bank = Account(
        id="acct_bank_1",
        name="Fake Bank 1",
        account_type="bank_account",
        balance_tracking=True,
    )
    cash = Account(id="acct_cash_wallet", name="Cash Wallet", account_type="cash")
    raw_sms = RawSmsMessage(
        id="raw_sms_private",
        external_message_id="fake-private-sms",
        sender="FAKEBANK",
        received_at=datetime(2026, 5, 4, 10, 30, tzinfo=UTC),
        body="PRIVATE FAKE SMS BODY SHOULD NOT BE IN SEARCH",
        source="external_forwarder",
        processing_status="candidate_created",
        parser_output={"amount": "480.00", "review_status": "reviewed"},
    )
    transactions = [
        LedgerTransaction(
            id="txn_food_sms",
            transaction_date=date(2026, 5, 4),
            amount=Decimal("480.00"),
            transaction_type="debit",
            purpose="expense",
            category="food_delivery",
            merchant_raw="MERCHANT_FOOD_1",
            merchant_canonical="Merchant Food 1",
            account=bank,
            raw_sms_message=raw_sms,
            source="sms",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="included",
            source_metadata={
                "raw_sms_id": "raw_sms_private",
                "external_message_id": "fake-private-sms",
                "raw_sms_source": "external_forwarder",
                "reference": "FAKE123",
                "ledger_sanity": {"status": "matched"},
            },
        ),
        LedgerTransaction(
            id="txn_grocery_manual",
            transaction_date=date(2026, 5, 5),
            amount=Decimal("250.00"),
            transaction_type="debit",
            purpose="expense",
            category="groceries",
            merchant_raw="FAKE_GROCERY",
            merchant_canonical="Fake Grocery",
            account=bank,
            source="manual",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="included",
            source_metadata={"manual_entry": {"actor_type": "user"}},
        ),
        LedgerTransaction(
            id="txn_salary",
            transaction_date=date(2026, 5, 5),
            amount=Decimal("3000.00"),
            transaction_type="credit",
            purpose="income",
            category="salary",
            merchant_raw="FAKE_EMPLOYER",
            merchant_canonical="Fake Employer",
            account=bank,
            source="manual",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="included",
            source_metadata={"manual_entry": {"actor_type": "user"}},
        ),
        LedgerTransaction(
            id="txn_cash_ignored",
            transaction_date=date(2026, 5, 6),
            amount=Decimal("75.00"),
            transaction_type="cash_adjustment",
            purpose="cash_update",
            category="cash_spend",
            merchant_raw="FAKE_CASH_DIFF",
            merchant_canonical="Fake Cash Difference",
            account=cash,
            source="manual",
            review_status="ignored",
            duplicate_status="unique",
            ledger_status="excluded",
            source_metadata={"cash_balance_update": {"difference": "-75.00"}},
        ),
        LedgerTransaction(
            id="txn_duplicate",
            transaction_date=date(2026, 5, 7),
            amount=Decimal("480.00"),
            transaction_type="debit",
            purpose="expense",
            category="food_delivery",
            merchant_raw="MERCHANT_FOOD_1",
            merchant_canonical="Merchant Food 1",
            account=bank,
            source="sms",
            review_status="reviewed",
            duplicate_status="possible_duplicate",
            ledger_status="excluded",
            source_metadata={"duplicate_detection": {"status": "possible_duplicate"}},
        ),
        LedgerTransaction(
            id="txn_deleted",
            transaction_date=date(2026, 5, 8),
            amount=Decimal("99.00"),
            transaction_type="debit",
            purpose="expense",
            category="shopping",
            merchant_raw="FAKE_DELETED",
            merchant_canonical="Fake Deleted",
            account=bank,
            source="manual",
            review_status="reviewed",
            duplicate_status="unique",
            ledger_status="excluded",
            deleted_at=datetime(2026, 5, 8, 12, 0, tzinfo=UTC),
            deleted_reason="fake search delete",
            source_metadata={"manual_entry": {"actor_type": "user"}},
        ),
    ]
    audit_event = AuditEvent(
        id="audit_food",
        transaction=transactions[0],
        actor_type="user",
        event_type="ledger_transaction_promoted",
        field_changes={"transaction_id": "txn_food_sms"},
        reason="fake search seed",
    )
    session.add_all([bank, cash, raw_sms, *transactions, audit_event])
    session.commit()


def test_ledger_search_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/ledger-transactions")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_ledger_search_filters_structured_fields_and_amount_range() -> None:
    with make_test_client() as (client, session):
        seed_ledger_search_data(session)

        response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={
                "date_from": "2026-05-04",
                "date_to": "2026-05-05",
                "account_id": "acct_bank_1",
                "transaction_type": "debit",
                "purpose": "expense",
                "category": "food_delivery",
                "source": "sms",
                "amount_min": "400.00",
                "amount_max": "500.00",
                "merchant": "food",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == ["txn_food_sms"]
    assert payload["items"][0]["source_context"]["reference"] == "FAKE123"
    assert payload["items"][0]["audit_event_count"] == 1


def test_ledger_search_default_excludes_deleted_and_can_include_deleted_explicitly() -> None:
    with make_test_client() as (client, session):
        seed_ledger_search_data(session)

        default_response = client.get("/api/ledger-transactions", headers=AUTH_HEADERS)
        include_deleted_response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"include_deleted": "true", "merchant": "deleted"},
        )

    assert default_response.status_code == 200
    assert "txn_deleted" not in {item["id"] for item in default_response.json()["items"]}
    assert include_deleted_response.status_code == 200
    assert [item["id"] for item in include_deleted_response.json()["items"]] == ["txn_deleted"]
    assert include_deleted_response.json()["items"][0]["deleted_reason"] == "fake search delete"


def test_ledger_search_can_find_ignored_duplicate_and_excluded_transactions() -> None:
    with make_test_client() as (client, session):
        seed_ledger_search_data(session)

        ignored_response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"review_status": "ignored", "ledger_status": "excluded"},
        )
        duplicate_response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"duplicate_status": "possible_duplicate", "ledger_status": "excluded"},
        )

    assert ignored_response.status_code == 200
    assert [item["id"] for item in ignored_response.json()["items"]] == ["txn_cash_ignored"]
    assert duplicate_response.status_code == 200
    assert [item["id"] for item in duplicate_response.json()["items"]] == ["txn_duplicate"]


def test_ledger_search_sorting_and_pagination_are_stable() -> None:
    with make_test_client() as (client, session):
        seed_ledger_search_data(session)

        first_page = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"sort_by": "amount", "sort_dir": "asc", "limit": "2", "offset": "0"},
        )
        second_page = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"sort_by": "amount", "sort_dir": "asc", "limit": "2", "offset": "2"},
        )

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert [item["id"] for item in first_page.json()["items"]] == [
        "txn_cash_ignored",
        "txn_grocery_manual",
    ]
    assert [item["id"] for item in second_page.json()["items"]] == [
        "txn_food_sms",
        "txn_duplicate",
    ]
    assert first_page.json()["total"] == 5
    assert first_page.json()["limit"] == 2
    assert second_page.json()["offset"] == 2


def test_ledger_search_does_not_expose_raw_sms_body() -> None:
    with make_test_client() as (client, session):
        seed_ledger_search_data(session)

        response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"id": "txn_food_sms"},
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["raw_sms_message_id"] == "raw_sms_private"
    assert "body" not in response.json()["items"][0]
    assert "PRIVATE FAKE SMS BODY" not in response.text


def test_ledger_search_treats_merchant_wildcards_as_literal_text() -> None:
    with make_test_client() as (client, session):
        seed_ledger_search_data(session)

        response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"merchant": "%"},
        )

    assert response.status_code == 200
    assert response.json()["items"] == []

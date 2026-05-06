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
from app.models import Account, AuditEvent, LedgerTransaction, RawSmsMessage, UserRule

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


def seed_export_data(session: Session) -> None:
    account = Account(
        id="acct_bank_1",
        name="Fake Bank 1",
        account_type="bank_account",
        balance_tracking=True,
        current_balance=Decimal("50000.00"),
    )
    raw_sms = RawSmsMessage(
        id="raw_sms_export",
        external_message_id="fake-export-message",
        sender="FAKEBANK",
        received_at=datetime(2026, 5, 4, 10, 30, tzinfo=UTC),
        body="fake private sms body must not be exported broadly",
        source="external_forwarder",
        processing_status="candidate_created",
        parser_output={"amount": 480, "review_status": "reviewed"},
    )
    transaction = LedgerTransaction(
        id="txn_export",
        transaction_date=date(2026, 5, 4),
        amount=Decimal("480.00"),
        transaction_type="debit",
        purpose="expense",
        category="food_delivery",
        merchant_raw="MERCHANT_FOOD_1",
        merchant_canonical="Merchant Food 1",
        account=account,
        raw_sms_message=raw_sms,
        source="sms",
        review_status="reviewed",
        duplicate_status="unique",
        ledger_status="included",
        source_metadata={"fixture": "export"},
    )
    audit_event = AuditEvent(
        id="audit_export",
        transaction=transaction,
        actor_type="user",
        event_type="ledger_transaction_promoted",
        field_changes={"transaction_id": "txn_export"},
        reason="fake export seed",
    )
    user_rule = UserRule(
        id="rule_export",
        name="Fake Export Rule",
        priority=10,
        match_merchant_raw="MERCHANT_FOOD_1",
        set_merchant_canonical="Merchant Food 1",
        set_category="food_delivery",
        enabled=True,
        source_metadata={"fixture": "export"},
    )
    session.add_all([account, raw_sms, transaction, audit_event, user_rule])
    session.commit()


def test_json_export_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/export/json")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_json_export_includes_structured_data_without_raw_sms_body() -> None:
    with make_test_client() as (client, session):
        seed_export_data(session)

        response = client.get("/api/export/json", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["format_version"] == 2
    assert payload["accounts"][0]["id"] == "acct_bank_1"
    assert payload["ledger_transactions"][0]["id"] == "txn_export"
    assert payload["audit_events"][0]["id"] == "audit_export"
    assert payload["user_rules"][0]["id"] == "rule_export"
    assert payload["raw_sms_messages"][0]["id"] == "raw_sms_export"
    assert payload["raw_sms_messages"][0]["body_exported"] is False
    assert "body" not in payload["raw_sms_messages"][0]
    assert "fake private sms body" not in response.text


def test_json_export_includes_raw_sms_body_only_when_explicitly_requested() -> None:
    with make_test_client() as (client, session):
        seed_export_data(session)

        response = client.get(
            "/api/export/json",
            headers=AUTH_HEADERS,
            params={"include_raw_sms_body": "true"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_sms_messages"][0]["body_exported"] is True
    assert (
        payload["raw_sms_messages"][0]["body"]
        == "fake private sms body must not be exported broadly"
    )


def test_ledger_csv_export_requires_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/export/ledger-transactions.csv")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_ledger_csv_export_includes_headers_and_rows() -> None:
    with make_test_client() as (client, session):
        seed_export_data(session)

        response = client.get("/api/export/ledger-transactions.csv", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "id,transaction_date,amount,transaction_type" in response.text
    assert "txn_export,2026-05-04,480.00,debit" in response.text


def test_ledger_csv_export_escapes_spreadsheet_formula_values() -> None:
    with make_test_client() as (client, session):
        seed_export_data(session)
        transaction = session.get(LedgerTransaction, "txn_export")
        assert transaction is not None
        transaction.merchant_raw = "=CMD"
        transaction.merchant_canonical = "+Merchant"
        transaction.category = "@category"
        session.add(transaction)
        session.commit()

        response = client.get("/api/export/ledger-transactions.csv", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert "'=CMD" in response.text
    assert "'+Merchant" in response.text
    assert "'@category" in response.text

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db_session
from app.main import app
from app.models import AuditEvent, LedgerTransaction, RawSmsMessage
from app.sqlite_backup import backup_database, restore_database

AUTH_HEADERS = {"X-Inbound-SMS-Secret": "change-me-in-development"}
PRIVATE_FAKE_SMS_MARKER = "PRIVATE_FAKE_SMS_BODY_SHOULD_NOT_LEAK"


@contextmanager
def make_file_backed_test_client(
    db_path: Path,
) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(f"sqlite:///{db_path}")
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
        engine.dispose()


def fake_sms_body(
    *,
    merchant: str = "MERCHANT_UNKNOWN_1",
    transaction_date: str = "04-May-2026",
    reference: str = "123456",
) -> str:
    return (
        f"{PRIVATE_FAKE_SMS_MARKER}: Rs.480 debited from BANK_1 a/c XX0000 "
        f"to {merchant} on {transaction_date}. Avl Bal Rs.50000. Ref {reference}."
    )


def android_forwarder_payload(
    *,
    text: str,
    received_stamp: str = "1777890600000",
) -> dict[str, str]:
    return {
        "from": "FAKEBANK",
        "text": text,
        "sentStamp": "1777890599000",
        "receivedStamp": received_stamp,
        "sim": "SIM1",
    }


def ingest_android_sms(
    client: TestClient,
    *,
    text: str,
    received_stamp: str = "1777890600000",
) -> str:
    response = client.post(
        "/api/forwarders/android-income-sms-webhook",
        headers=AUTH_HEADERS,
        json=android_forwarder_payload(text=text, received_stamp=received_stamp),
    )
    assert response.status_code == 201
    return str(response.json()["raw_sms_id"])


def review_and_promote(client: TestClient, raw_sms_id: str) -> dict[str, object]:
    review_response = client.post(
        f"/api/review-queue/{raw_sms_id}/review",
        headers=AUTH_HEADERS,
        json={"decision": "reviewed", "reason": "release candidate fake review"},
    )
    assert review_response.status_code == 200
    promote_response = client.post(
        f"/api/review-queue/{raw_sms_id}/promote",
        headers=AUTH_HEADERS,
        json={"reason": "release candidate fake promotion"},
    )
    assert promote_response.status_code == 201
    return dict(promote_response.json())


def test_v1_release_candidate_fake_data_workflow(tmp_path: Path) -> None:
    db_path = tmp_path / "release_candidate.db"
    backup_path = tmp_path / "release_candidate.backup.db"
    restored_path = tmp_path / "release_candidate.restored.db"

    with make_file_backed_test_client(db_path) as (client, session):
        first_raw_sms_id = ingest_android_sms(client, text=fake_sms_body())

        correction_response = client.patch(
            f"/api/review-queue/{first_raw_sms_id}/corrections",
            headers=AUTH_HEADERS,
            json={
                "updates": {
                    "merchant_canonical": "Corrected Release Merchant",
                    "category": "groceries",
                },
                "reason": "release candidate fake correction",
            },
        )
        assert correction_response.status_code == 200
        corrected_candidate = correction_response.json()["candidate"]
        assert corrected_candidate["rule_candidate"]["source"] == "user_correction"

        first_promotion = review_and_promote(client, first_raw_sms_id)
        assert first_promotion["duplicate_status"] == "unique"
        assert first_promotion["ledger_status"] == "included"

        candidates_response = client.get("/api/rule-candidates", headers=AUTH_HEADERS)
        assert candidates_response.status_code == 200
        rule_candidate_id = candidates_response.json()["items"][0]["id"]
        approve_response = client.post(
            f"/api/rule-candidates/{rule_candidate_id}/approve",
            headers=AUTH_HEADERS,
            json={"name": "Release candidate merchant rule"},
        )
        assert approve_response.status_code == 201

        future_sms = fake_sms_body(transaction_date="05-May-2026", reference="654321")
        future_raw_sms_id = ingest_android_sms(
            client,
            text=future_sms,
            received_stamp="1777977000000",
        )
        future_detail = client.get(
            f"/api/review-queue/{future_raw_sms_id}",
            headers=AUTH_HEADERS,
        )
        assert future_detail.status_code == 200
        assert future_detail.json()["candidate"]["merchant_canonical"] == (
            "Corrected Release Merchant"
        )
        assert future_detail.json()["candidate"]["category"] == "groceries"
        future_promotion = review_and_promote(client, future_raw_sms_id)
        assert future_promotion["duplicate_status"] == "unique"
        assert future_promotion["ledger_status"] == "included"

        duplicate_raw_sms_id = ingest_android_sms(
            client,
            text=future_sms,
            received_stamp="1777977060000",
        )
        duplicate_promotion = review_and_promote(client, duplicate_raw_sms_id)
        assert duplicate_promotion["duplicate_status"] == "exact_duplicate"
        assert duplicate_promotion["ledger_status"] == "excluded"

        cash_account_response = client.post(
            "/api/accounts",
            headers=AUTH_HEADERS,
            json={
                "id": "acct_cash_wallet",
                "name": "Cash Wallet",
                "account_type": "cash",
                "balance_tracking": True,
                "current_balance": "5000.00",
            },
        )
        assert cash_account_response.status_code == 201
        cash_update_response = client.post(
            "/api/accounts/acct_cash_wallet/cash-balance",
            headers=AUTH_HEADERS,
            json={
                "reported_balance": "4200.00",
                "reported_on": "2026-05-06",
                "record_difference_as_adjustment": True,
                "reason": "release candidate fake cash count",
            },
        )
        assert cash_update_response.status_code == 200
        assert cash_update_response.json()["adjustment_transaction_id"] is not None

        search_response = client.get(
            "/api/ledger-transactions",
            headers=AUTH_HEADERS,
            params={"merchant": "Corrected Release Merchant", "sort_dir": "asc"},
        )
        assert search_response.status_code == 200
        assert search_response.json()["total"] == 3
        assert PRIVATE_FAKE_SMS_MARKER not in search_response.text

        analysis_response = client.get(
            "/api/analysis/summary",
            headers=AUTH_HEADERS,
            params={"month": "2026-05"},
        )
        assert analysis_response.status_code == 200
        analysis_payload = analysis_response.json()
        assert analysis_payload["income_vs_expense"]["normal_expense"] == "960.00"
        assert analysis_payload["quality_counts"]["excluded_from_totals"] == 1

        insights_response = client.get(
            "/api/insights",
            headers=AUTH_HEADERS,
            params={"month": "2026-05"},
        )
        assert insights_response.status_code == 200
        insight_types = {item["type"] for item in insights_response.json()["items"]}
        assert {"possible_duplicates", "cash_mismatches"}.issubset(insight_types)
        assert PRIVATE_FAKE_SMS_MARKER not in insights_response.text

        export_response = client.get("/api/export/json", headers=AUTH_HEADERS)
        assert export_response.status_code == 200
        export_payload = export_response.json()
        assert export_payload["raw_sms_messages"][0]["body_exported"] is False
        assert PRIVATE_FAKE_SMS_MARKER not in export_response.text

        validate_response = client.post(
            "/api/import/json/validate",
            headers=AUTH_HEADERS,
            json=export_payload,
        )
        assert validate_response.status_code == 200
        assert validate_response.json()["format_version"] == 2

        audit_event_types = session.scalars(
            select(AuditEvent.event_type).order_by(AuditEvent.created_at)
        ).all()
        assert "ledger_transaction_promoted" in audit_event_types
        assert "user_rule_approved" in audit_event_types
        assert "cash_adjustment_created" in audit_event_types

        stored_duplicate = session.get(
            LedgerTransaction, duplicate_promotion["ledger_transaction_id"]
        )
        assert stored_duplicate is not None
        assert stored_duplicate.source_metadata["duplicate_detection"]["matched_raw_sms_id"] == (
            future_raw_sms_id
        )
        stored_raw_sms = session.get(RawSmsMessage, first_raw_sms_id)
        assert stored_raw_sms is not None
        assert stored_raw_sms.body.startswith(PRIVATE_FAKE_SMS_MARKER)

    backup_database(db_path, backup_path)
    restore_database(backup_path, restored_path, force=False)

    with sqlite3.connect(restored_path) as restored:
        raw_sms_count = restored.execute("select count(*) from raw_sms_messages").fetchone()[0]
        transaction_count = restored.execute(
            "select count(*) from ledger_transactions"
        ).fetchone()[0]
        user_rule_count = restored.execute("select count(*) from user_rules").fetchone()[0]

    assert raw_sms_count == 3
    assert transaction_count == 4
    assert user_rule_count == 1

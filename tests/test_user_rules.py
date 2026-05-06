from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db_session
from app.main import app
from app.models import AuditEvent, RawSmsMessage, UserRule

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


def seed_corrected_raw_sms(session: Session) -> None:
    session.add(
        RawSmsMessage(
            id="raw_sms_rule_source",
            external_message_id="fake-rule-source",
            sender="FAKEBANK",
            received_at=datetime(2026, 5, 4, 10, 0, tzinfo=UTC),
            body="fake rule source body",
            source="external_forwarder",
            processing_status="candidate_created",
            parser_output={
                "amount": "480.00",
                "transaction_date": "2026-05-04",
                "transaction_type": "debit",
                "purpose": "expense",
                "merchant_raw": "MERCHANT_UNKNOWN_1",
                "source": "sms",
                "review_status": "needs_review",
                "confidence": {"parsing": "high"},
                "user_corrections": {
                    "merchant_canonical": {"value": "Corrected Merchant"},
                    "category": {"value": "groceries"},
                },
                "correction_history": [
                    {"field": "merchant_canonical", "after": "Corrected Merchant"},
                    {"field": "category", "after": "groceries"},
                ],
                "rule_candidate": {
                    "source": "user_correction",
                    "status": "candidate_only",
                    "fields": [
                        {"field": "merchant_canonical", "value": "Corrected Merchant"},
                        {"field": "category", "value": "groceries"},
                    ],
                    "history_count": 2,
                },
            },
        )
    )
    session.commit()


def test_user_rule_endpoints_require_shared_secret() -> None:
    with make_test_client() as (client, _session):
        response = client.get("/api/rule-candidates")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}


def test_rule_candidate_can_be_approved_into_audited_user_rule() -> None:
    with make_test_client() as (client, session):
        seed_corrected_raw_sms(session)

        candidates_response = client.get("/api/rule-candidates", headers=AUTH_HEADERS)
        candidate = candidates_response.json()["items"][0]
        approve_response = client.post(
            f"/api/rule-candidates/{candidate['id']}/approve",
            headers=AUTH_HEADERS,
            json={"name": "Unknown merchant groceries", "reason": "fake approval"},
        )
        stored_rule = session.scalar(select(UserRule))
        audit_events = session.scalars(select(AuditEvent)).all()

    assert candidates_response.status_code == 200
    assert candidate["match"]["merchant_raw"] == "MERCHANT_UNKNOWN_1"
    assert candidate["proposed_values"] == {
        "merchant_canonical": "Corrected Merchant",
        "category": "groceries",
    }
    assert approve_response.status_code == 201
    assert stored_rule is not None
    assert approve_response.json()["id"] == stored_rule.id
    assert stored_rule.enabled is True
    assert stored_rule.match_merchant_raw == "MERCHANT_UNKNOWN_1"
    assert stored_rule.set_merchant_canonical == "Corrected Merchant"
    assert stored_rule.set_category == "groceries"
    assert audit_events[0].event_type == "user_rule_approved"
    assert audit_events[0].field_changes["source_candidate_id"] == candidate["id"]


def test_rule_candidate_can_be_rejected_without_creating_rule() -> None:
    with make_test_client() as (client, session):
        seed_corrected_raw_sms(session)
        candidate_id = client.get("/api/rule-candidates", headers=AUTH_HEADERS).json()["items"][0][
            "id"
        ]

        reject_response = client.post(
            f"/api/rule-candidates/{candidate_id}/reject",
            headers=AUTH_HEADERS,
            json={"reason": "too broad"},
        )
        rules = session.scalars(select(UserRule)).all()
        audit_events = session.scalars(select(AuditEvent)).all()

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert rules == []
    assert audit_events[0].event_type == "rule_candidate_rejected"
    assert audit_events[0].field_changes["rule_candidate_id"] == candidate_id


def test_enabled_user_rule_applies_to_future_inbound_sms() -> None:
    with make_test_client() as (client, session):
        seed_corrected_raw_sms(session)
        candidate_id = client.get("/api/rule-candidates", headers=AUTH_HEADERS).json()["items"][0][
            "id"
        ]
        client.post(
            f"/api/rule-candidates/{candidate_id}/approve",
            headers=AUTH_HEADERS,
            json={"name": "Unknown merchant groceries"},
        )

        inbound_response = client.post(
            "/api/inbound-sms",
            headers=AUTH_HEADERS,
            json={
                "message_id": "future-rule-match",
                "sender": "FAKEBANK",
                "received_at": "2026-05-05T10:00:00Z",
                "body": (
                    "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_UNKNOWN_1 "
                    "on 05-May-2026. Avl Bal Rs.50000. Ref 999999."
                ),
            },
        )

    assert inbound_response.status_code == 201
    candidate = inbound_response.json()["candidate"]
    assert candidate["merchant_canonical"] == "Corrected Merchant"
    assert candidate["category"] == "groceries"
    assert candidate["rule_metadata"]["user_approved_rule"]["rule_id"].startswith("rule_")
    assert candidate["confidence"]["category"] == "high"


def test_user_rule_can_be_edited_and_disabled() -> None:
    with make_test_client() as (client, session):
        seed_corrected_raw_sms(session)
        candidate_id = client.get("/api/rule-candidates", headers=AUTH_HEADERS).json()["items"][0][
            "id"
        ]
        rule_id = client.post(
            f"/api/rule-candidates/{candidate_id}/approve",
            headers=AUTH_HEADERS,
            json={"name": "Unknown merchant groceries"},
        ).json()["id"]

        edit_response = client.patch(
            f"/api/user-rules/{rule_id}",
            headers=AUTH_HEADERS,
            json={"updates": {"set_category": "shopping"}, "reason": "fake edit"},
        )
        edited_inbound = client.post(
            "/api/inbound-sms",
            headers=AUTH_HEADERS,
            json={
                "message_id": "future-rule-edit-match",
                "sender": "FAKEBANK",
                "received_at": "2026-05-06T10:00:00Z",
                "body": (
                    "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_UNKNOWN_1 "
                    "on 06-May-2026. Avl Bal Rs.50000. Ref 888888."
                ),
            },
        )
        disable_response = client.post(
            f"/api/user-rules/{rule_id}/disable",
            headers=AUTH_HEADERS,
            json={"reason": "fake disable"},
        )
        disabled_inbound = client.post(
            "/api/inbound-sms",
            headers=AUTH_HEADERS,
            json={
                "message_id": "future-disabled-rule",
                "sender": "FAKEBANK",
                "received_at": "2026-05-07T10:00:00Z",
                "body": (
                    "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_UNKNOWN_1 "
                    "on 07-May-2026. Avl Bal Rs.50000. Ref 777777."
                ),
            },
        )
        audit_event_types = [
            event.event_type for event in session.scalars(select(AuditEvent)).all()
        ]

    assert edit_response.status_code == 200
    assert edit_response.json()["set_category"] == "shopping"
    assert edited_inbound.json()["candidate"]["category"] == "shopping"
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False
    assert "category" not in disabled_inbound.json()["candidate"]
    assert audit_event_types == [
        "user_rule_approved",
        "user_rule_updated",
        "user_rule_disabled",
    ]

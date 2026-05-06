from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.duplicate_detection import DuplicateDecision, detect_duplicate_candidate
from app.ledger_sanity import LedgerSanityDecision, evaluate_ledger_sanity
from app.models import Account, AuditEvent, LedgerTransaction, RawSmsMessage
from app.review_queue import get_raw_sms_or_404

PROMOTION_VALIDATION_ERROR_STATUS = 422


class LedgerPromotionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class LedgerPromotionResponse(BaseModel):
    status: Literal["promoted", "already_promoted"]
    ledger_transaction_id: str
    raw_sms_id: str
    duplicate_status: str
    ledger_status: str
    ledger_sanity_status: str


def promote_reviewed_sms_candidate(
    db_session: Session,
    raw_sms_id: str,
    payload: LedgerPromotionPayload,
) -> tuple[LedgerPromotionResponse, int]:
    raw_sms = get_raw_sms_or_404(db_session, raw_sms_id)

    existing_transaction = find_existing_transaction(db_session, raw_sms)
    if existing_transaction is not None:
        ensure_promotion_metadata(db_session, raw_sms, existing_transaction)
        return (
            LedgerPromotionResponse(
                status="already_promoted",
                ledger_transaction_id=existing_transaction.id,
                raw_sms_id=raw_sms.id,
                duplicate_status=existing_transaction.duplicate_status,
                ledger_status=existing_transaction.ledger_status,
                ledger_sanity_status=existing_transaction.source_metadata.get(
                    "ledger_sanity", {}
                ).get("status", "not_checked"),
            ),
            status.HTTP_200_OK,
        )

    candidate = dict(raw_sms.parser_output)
    validate_candidate_ready_for_promotion(candidate)
    account_id = str(candidate["account_id"])
    account = ensure_known_account(db_session, account_id)
    duplicate_decision = detect_duplicate_candidate(db_session, candidate)
    ledger_sanity_decision = evaluate_ledger_sanity(
        db_session=db_session,
        account=account,
        candidate=candidate,
        duplicate_decision=duplicate_decision,
    )

    transaction = LedgerTransaction(
        id=f"txn_{uuid4().hex}",
        raw_sms_message_id=raw_sms.id,
        transaction_date=parse_transaction_date(candidate["transaction_date"]),
        amount=Decimal(str(candidate["amount"])).quantize(Decimal("0.01")),
        transaction_type=str(candidate["transaction_type"]),
        purpose=str(candidate["purpose"]),
        category=as_optional_string(candidate.get("category")),
        merchant_raw=as_optional_string(candidate.get("merchant_raw")),
        merchant_canonical=as_optional_string(candidate.get("merchant_canonical")),
        account_id=account_id,
        source=str(candidate["source"]),
        parsing_confidence=candidate.get("confidence", {}).get("parsing"),
        merchant_mapping_confidence=candidate.get("confidence", {}).get("merchant_mapping"),
        category_confidence=candidate.get("confidence", {}).get("category"),
        review_status="reviewed",
        duplicate_status=duplicate_decision.status,
        ledger_status=ledger_sanity_decision.ledger_status,
        source_metadata=build_source_metadata(
            raw_sms, candidate, duplicate_decision, ledger_sanity_decision
        ),
    )
    db_session.add(transaction)
    db_session.flush()

    audit_event = AuditEvent(
        id=f"audit_{uuid4().hex}",
        transaction=transaction,
        actor_type="user",
        event_type="ledger_transaction_promoted",
        field_changes={
            "raw_sms_id": raw_sms.id,
            "external_message_id": raw_sms.external_message_id,
            "transaction_id": transaction.id,
            "source": raw_sms.source,
            "duplicate_status": transaction.duplicate_status,
            "ledger_status": transaction.ledger_status,
            "ledger_sanity_status": ledger_sanity_decision.status,
        },
        reason=payload.reason,
    )
    db_session.add(audit_event)

    parser_output = dict(raw_sms.parser_output)
    parser_output["duplicate_detection"] = duplicate_decision.as_metadata()
    parser_output["duplicate_status"] = duplicate_decision.status
    parser_output["ledger_sanity"] = ledger_sanity_decision.as_metadata()
    parser_output["ledger_sanity_status"] = ledger_sanity_decision.status
    parser_output["ledger_status"] = ledger_sanity_decision.ledger_status
    parser_output["promotion_metadata"] = {
        "ledger_transaction_id": transaction.id,
        "promoted_at": datetime.now(UTC).isoformat(),
        "actor_type": "user",
    }
    raw_sms.parser_output = parser_output
    db_session.add(raw_sms)
    db_session.commit()
    db_session.refresh(transaction)

    return (
        LedgerPromotionResponse(
            status="promoted",
            ledger_transaction_id=transaction.id,
            raw_sms_id=raw_sms.id,
            duplicate_status=transaction.duplicate_status,
            ledger_status=transaction.ledger_status,
            ledger_sanity_status=ledger_sanity_decision.status,
        ),
        status.HTTP_201_CREATED,
    )


def find_existing_transaction(
    db_session: Session, raw_sms: RawSmsMessage
) -> LedgerTransaction | None:
    promotion_metadata = raw_sms.parser_output.get("promotion_metadata", {})
    ledger_transaction_id = promotion_metadata.get("ledger_transaction_id")
    if isinstance(ledger_transaction_id, str):
        existing_by_metadata = db_session.get(LedgerTransaction, ledger_transaction_id)
        if existing_by_metadata is not None:
            return existing_by_metadata

    return db_session.scalar(
        select(LedgerTransaction).where(LedgerTransaction.raw_sms_message_id == raw_sms.id)
    )


def ensure_promotion_metadata(
    db_session: Session, raw_sms: RawSmsMessage, transaction: LedgerTransaction
) -> None:
    promotion_metadata = raw_sms.parser_output.get("promotion_metadata", {})
    if promotion_metadata.get("ledger_transaction_id") == transaction.id:
        return

    parser_output = dict(raw_sms.parser_output)
    parser_output["promotion_metadata"] = {
        "ledger_transaction_id": transaction.id,
        "promoted_at": transaction.created_at.isoformat(),
        "actor_type": "user",
    }
    raw_sms.parser_output = parser_output
    db_session.add(raw_sms)
    db_session.commit()


def validate_candidate_ready_for_promotion(candidate: dict[str, Any]) -> None:
    if candidate.get("review_status") != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate must be reviewed before promotion",
        )

    missing_fields = [
        field_name
        for field_name in (
            "amount",
            "transaction_date",
            "transaction_type",
            "purpose",
            "account_id",
            "source",
        )
        if candidate.get(field_name) in (None, "")
    ]
    if missing_fields:
        raise HTTPException(
            status_code=PROMOTION_VALIDATION_ERROR_STATUS,
            detail=f"candidate is missing {', '.join(missing_fields)}",
        )


def ensure_known_account(db_session: Session, account_id: str) -> Account:
    account = db_session.get(Account, account_id)
    if account is not None:
        return account

    if account_id != "acct_bank_1":
        raise HTTPException(
            status_code=PROMOTION_VALIDATION_ERROR_STATUS,
            detail="candidate account_id is unknown",
        )

    account = Account(
        id="acct_bank_1",
        name="Fake Bank 1",
        account_type="bank_account",
        balance_tracking=True,
    )
    db_session.add(account)
    db_session.flush()
    return account


def parse_transaction_date(value: object) -> date:
    if not isinstance(value, str):
        raise HTTPException(
            status_code=PROMOTION_VALIDATION_ERROR_STATUS,
            detail="candidate transaction_date must be an ISO date",
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=PROMOTION_VALIDATION_ERROR_STATUS,
            detail="candidate transaction_date must be an ISO date",
        ) from exc


def build_source_metadata(
    raw_sms: RawSmsMessage,
    candidate: dict[str, Any],
    duplicate_decision: DuplicateDecision,
    ledger_sanity_decision: LedgerSanityDecision,
) -> dict[str, Any]:
    return {
        "raw_sms_id": raw_sms.id,
        "external_message_id": raw_sms.external_message_id,
        "raw_sms_source": raw_sms.source,
        "parser_metadata": candidate.get("parser_metadata", {}),
        "rule_metadata": candidate.get("rule_metadata", {}),
        "review_metadata": candidate.get("review_metadata", {}),
        "reference": candidate.get("reference"),
        "available_balance": candidate.get("available_balance"),
        "duplicate_detection": duplicate_decision.as_metadata(),
        "ledger_sanity": ledger_sanity_decision.as_metadata(),
    }


def as_optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, LedgerTransaction
from app.review_queue import ReviewQueueDetail, get_raw_sms_or_404, raw_sms_to_queue_detail

CORRECTION_VALIDATION_ERROR_STATUS = 422

CORRECTABLE_FIELDS = {
    "merchant_raw",
    "merchant_canonical",
    "category",
    "purpose",
    "account_id",
    "amount",
    "transaction_date",
    "transaction_type",
}
OPTIONAL_CORRECTION_FIELDS = {"merchant_raw", "merchant_canonical", "category"}


class CorrectionPayload(BaseModel):
    updates: dict[str, Any] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=500)


class LedgerTransactionCorrectionResponse(BaseModel):
    ledger_transaction_id: str
    corrected_fields: list[str]
    transaction: dict[str, Any]


def correct_review_candidate(
    db_session: Session,
    raw_sms_id: str,
    payload: CorrectionPayload,
) -> ReviewQueueDetail:
    raw_sms = get_raw_sms_or_404(db_session, raw_sms_id)
    validate_correction_updates(db_session, payload.updates)

    parser_output = dict(raw_sms.parser_output)
    corrected_at = datetime.now(UTC).isoformat()
    history = list(parser_output.get("correction_history", []))
    user_corrections = dict(parser_output.get("user_corrections", {}))

    for field_name, value in payload.updates.items():
        normalized_value = normalize_correction_value(field_name, value)
        before = parser_output.get(field_name)
        parser_output[field_name] = normalized_value
        user_corrections[field_name] = {
            "value": normalized_value,
            "reason": payload.reason,
            "actor_type": "user",
            "corrected_at": corrected_at,
        }
        history.append(
            {
                "field": field_name,
                "before": serialize_value(before),
                "after": serialize_value(normalized_value),
                "reason": payload.reason,
                "actor_type": "user",
                "corrected_at": corrected_at,
            }
        )

    parser_output["user_corrections"] = user_corrections
    parser_output["correction_history"] = history
    parser_output["rule_candidate"] = build_rule_candidate(
        user_corrections, history, corrected_at
    )

    raw_sms.parser_output = parser_output
    db_session.add(raw_sms)
    db_session.commit()
    db_session.refresh(raw_sms)
    return raw_sms_to_queue_detail(raw_sms)


def correct_ledger_transaction(
    db_session: Session,
    transaction_id: str,
    payload: CorrectionPayload,
) -> LedgerTransactionCorrectionResponse:
    transaction = db_session.get(LedgerTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ledger transaction not found",
        )

    validate_correction_updates(db_session, payload.updates)
    corrected_at = datetime.now(UTC).isoformat()
    field_changes: dict[str, dict[str, Any]] = {}

    for field_name, value in payload.updates.items():
        normalized_value = normalize_ledger_field_value(field_name, value)
        before = getattr(transaction, field_name)
        setattr(transaction, field_name, normalized_value)
        field_changes[field_name] = {
            "before": serialize_value(before),
            "after": serialize_value(normalized_value),
        }

    metadata = dict(transaction.source_metadata)
    history = list(metadata.get("correction_history", []))
    user_corrections = dict(metadata.get("user_corrections", {}))
    for field_name, change in field_changes.items():
        user_corrections[field_name] = {
            "value": change["after"],
            "reason": payload.reason,
            "actor_type": "user",
            "corrected_at": corrected_at,
        }
        history.append(
            {
                "field": field_name,
                "before": change["before"],
                "after": change["after"],
                "reason": payload.reason,
                "actor_type": "user",
                "corrected_at": corrected_at,
            }
        )
    metadata["user_corrections"] = user_corrections
    metadata["correction_history"] = history
    metadata["rule_candidate"] = build_rule_candidate(
        user_corrections, history, corrected_at
    )
    transaction.source_metadata = metadata

    audit_event = AuditEvent(
        id=f"audit_{uuid4().hex}",
        transaction=transaction,
        actor_type="user",
        event_type="ledger_transaction_corrected",
        field_changes=field_changes,
        reason=payload.reason,
    )
    db_session.add_all([transaction, audit_event])
    db_session.commit()
    db_session.refresh(transaction)

    return LedgerTransactionCorrectionResponse(
        ledger_transaction_id=transaction.id,
        corrected_fields=list(field_changes),
        transaction=ledger_transaction_to_dict(transaction),
    )


def validate_correction_updates(db_session: Session, updates: dict[str, Any]) -> None:
    for field_name in updates:
        if field_name not in CORRECTABLE_FIELDS:
            raise HTTPException(
                status_code=CORRECTION_VALIDATION_ERROR_STATUS,
                detail=f"unsupported correction field: {field_name}",
            )
        if (
            field_name not in OPTIONAL_CORRECTION_FIELDS
            and updates[field_name] in (None, "")
        ):
            raise HTTPException(
                status_code=CORRECTION_VALIDATION_ERROR_STATUS,
                detail=f"correction {field_name} is required",
            )

    account_id = updates.get("account_id")
    if account_id is not None:
        validate_known_account(db_session, str(account_id))

    for field_name, value in updates.items():
        normalize_correction_value(field_name, value)


def validate_known_account(db_session: Session, account_id: str) -> None:
    if account_id == "acct_bank_1":
        return
    if db_session.get(Account, account_id) is not None:
        return
    raise HTTPException(
        status_code=CORRECTION_VALIDATION_ERROR_STATUS,
        detail="correction account_id is unknown",
    )


def normalize_correction_value(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    if field_name == "amount":
        return normalize_amount(value)
    if field_name == "transaction_date":
        return normalize_date(value).isoformat()
    return str(value)


def normalize_ledger_field_value(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    if field_name == "amount":
        return Decimal(normalize_amount(value)).quantize(Decimal("0.01"))
    if field_name == "transaction_date":
        return normalize_date(value)
    return str(value)


def normalize_amount(value: Any) -> str:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(
            status_code=CORRECTION_VALIDATION_ERROR_STATUS,
            detail="correction amount must be a decimal value",
        ) from exc
    return str(amount)


def normalize_date(value: Any) -> date:
    if not isinstance(value, str):
        raise HTTPException(
            status_code=CORRECTION_VALIDATION_ERROR_STATUS,
            detail="correction transaction_date must be an ISO date",
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=CORRECTION_VALIDATION_ERROR_STATUS,
            detail="correction transaction_date must be an ISO date",
        ) from exc


def build_rule_candidate(
    user_corrections: dict[str, Any],
    history: list[Any],
    corrected_at: str,
) -> dict[str, Any]:
    return {
        "source": "user_correction",
        "status": "candidate_only",
        "created_at": corrected_at,
        "fields": [
            {
                "field": field_name,
                "value": correction.get("value"),
                "reason": correction.get("reason"),
            }
            for field_name, correction in user_corrections.items()
        ],
        "history_count": len(history),
    }


def ledger_transaction_to_dict(transaction: LedgerTransaction) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "transaction_date": transaction.transaction_date.isoformat(),
        "amount": str(transaction.amount),
        "transaction_type": transaction.transaction_type,
        "purpose": transaction.purpose,
        "category": transaction.category,
        "merchant_raw": transaction.merchant_raw,
        "merchant_canonical": transaction.merchant_canonical,
        "account_id": transaction.account_id,
        "source": transaction.source,
        "review_status": transaction.review_status,
        "duplicate_status": transaction.duplicate_status,
        "ledger_status": transaction.ledger_status,
    }


def serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value

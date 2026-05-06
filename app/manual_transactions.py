from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Account, AuditEvent, Category, LedgerTransaction

VALIDATION_ERROR_STATUS = 422

MANUAL_UPDATE_FIELDS = {
    "transaction_date",
    "amount",
    "transaction_type",
    "purpose",
    "category",
    "merchant_raw",
    "merchant_canonical",
    "account_id",
}


class ManualTransactionCreatePayload(BaseModel):
    transaction_date: date
    amount: str = Field(min_length=1, max_length=40)
    transaction_type: str = Field(min_length=1, max_length=40)
    purpose: str = Field(min_length=1, max_length=40)
    category: str | None = Field(default=None, max_length=80)
    merchant_raw: str | None = None
    merchant_canonical: str | None = Field(default=None, max_length=160)
    account_id: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=500)


class ManualTransactionUpdatePayload(BaseModel):
    updates: dict[str, Any]
    reason: str | None = Field(default=None, max_length=500)


class ManualTransactionActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def create_manual_transaction(
    db_session: Session, payload: ManualTransactionCreatePayload
) -> dict[str, Any]:
    ensure_known_account(db_session, payload.account_id)
    ensure_active_category(db_session, payload.category)

    transaction = LedgerTransaction(
        id=f"txn_{uuid4().hex}",
        transaction_date=payload.transaction_date,
        amount=parse_positive_decimal(payload.amount, "amount"),
        transaction_type=payload.transaction_type,
        purpose=payload.purpose,
        category=payload.category,
        merchant_raw=payload.merchant_raw,
        merchant_canonical=payload.merchant_canonical,
        account_id=payload.account_id,
        source="manual",
        parsing_confidence=None,
        merchant_mapping_confidence=None,
        category_confidence=None,
        review_status="reviewed",
        duplicate_status="unique",
        ledger_status="included",
        source_metadata={
            "manual_entry": {
                "actor_type": "user",
                "created_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    db_session.add(transaction)
    db_session.flush()
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            transaction=transaction,
            actor_type="user",
            event_type="manual_transaction_created",
            field_changes={
                "transaction_id": transaction.id,
                "source": "manual",
                "amount": {"before": None, "after": serialize(transaction.amount)},
                "account_id": {"before": None, "after": transaction.account_id},
            },
            reason=payload.reason,
        )
    )
    db_session.commit()
    db_session.refresh(transaction)
    return transaction_to_dict(transaction)


def update_manual_transaction(
    db_session: Session, transaction_id: str, payload: ManualTransactionUpdatePayload
) -> dict[str, Any]:
    transaction = get_active_manual_transaction(db_session, transaction_id)
    changes: dict[str, dict[str, Any]] = {}
    normalized_updates: dict[str, Any] = {}
    for field_name, value in payload.updates.items():
        if field_name not in MANUAL_UPDATE_FIELDS:
            raise HTTPException(
                status_code=VALIDATION_ERROR_STATUS,
                detail=f"unsupported manual transaction field: {field_name}",
            )
        normalized_updates[field_name] = normalize_update_value(
            db_session, field_name, value
        )

    for field_name, value in normalized_updates.items():
        before = getattr(transaction, field_name)
        if before == value:
            continue
        setattr(transaction, field_name, value)
        changes[field_name] = {"before": serialize(before), "after": serialize(value)}

    if changes:
        append_manual_history(transaction, "updated", changes)
        db_session.add(
            AuditEvent(
                id=f"audit_{uuid4().hex}",
                transaction=transaction,
                actor_type="user",
                event_type="manual_transaction_updated",
                field_changes=changes,
                reason=payload.reason,
            )
        )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction_to_dict(transaction)


def ignore_manual_transaction(
    db_session: Session, transaction_id: str, payload: ManualTransactionActionPayload
) -> dict[str, Any]:
    return update_manual_status(
        db_session,
        transaction_id,
        payload,
        event_type="manual_transaction_ignored",
        updates={"review_status": "ignored", "ledger_status": "excluded"},
    )


def mark_manual_transaction_duplicate(
    db_session: Session, transaction_id: str, payload: ManualTransactionActionPayload
) -> dict[str, Any]:
    return update_manual_status(
        db_session,
        transaction_id,
        payload,
        event_type="manual_transaction_marked_duplicate",
        updates={"duplicate_status": "confirmed_duplicate", "ledger_status": "excluded"},
    )


def delete_manual_transaction(
    db_session: Session, transaction_id: str, payload: ManualTransactionActionPayload
) -> dict[str, Any]:
    transaction = get_active_manual_transaction(db_session, transaction_id)
    deleted_at = datetime.now(UTC)
    source_metadata = dict(transaction.source_metadata or {})
    source_metadata["deleted_state_before"] = {
        "review_status": transaction.review_status,
        "duplicate_status": transaction.duplicate_status,
        "ledger_status": transaction.ledger_status,
    }
    transaction.source_metadata = source_metadata
    changes = {
        "deleted_at": {"before": serialize(transaction.deleted_at), "after": serialize(deleted_at)},
        "deleted_reason": {"before": transaction.deleted_reason, "after": payload.reason},
        "ledger_status": {"before": transaction.ledger_status, "after": "excluded"},
    }
    transaction.deleted_at = deleted_at
    transaction.deleted_reason = payload.reason
    transaction.ledger_status = "excluded"
    append_manual_history(transaction, "deleted", changes)
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            transaction=transaction,
            actor_type="user",
            event_type="manual_transaction_deleted",
            field_changes=changes,
            reason=payload.reason,
        )
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction_to_dict(transaction)


def restore_manual_transaction(
    db_session: Session, transaction_id: str, payload: ManualTransactionActionPayload
) -> dict[str, Any]:
    transaction = get_manual_transaction(db_session, transaction_id)
    if transaction.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="transaction is not deleted",
        )
    previous_state = dict(transaction.source_metadata or {}).get("deleted_state_before", {})
    restored_ledger_status = previous_state.get("ledger_status", "included")
    changes = {
        "deleted_at": {"before": serialize(transaction.deleted_at), "after": None},
        "deleted_reason": {"before": transaction.deleted_reason, "after": None},
        "ledger_status": {
            "before": transaction.ledger_status,
            "after": restored_ledger_status,
        },
    }
    transaction.deleted_at = None
    transaction.deleted_reason = None
    transaction.ledger_status = str(restored_ledger_status)
    append_manual_history(transaction, "restored", changes)
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            transaction=transaction,
            actor_type="user",
            event_type="manual_transaction_restored",
            field_changes=changes,
            reason=payload.reason,
        )
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction_to_dict(transaction)


def update_manual_status(
    db_session: Session,
    transaction_id: str,
    payload: ManualTransactionActionPayload,
    *,
    event_type: str,
    updates: dict[str, str],
) -> dict[str, Any]:
    transaction = get_active_manual_transaction(db_session, transaction_id)
    changes: dict[str, dict[str, Any]] = {}
    for field_name, value in updates.items():
        before = getattr(transaction, field_name)
        setattr(transaction, field_name, value)
        changes[field_name] = {"before": serialize(before), "after": value}
    append_manual_history(transaction, event_type.removeprefix("manual_transaction_"), changes)
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            transaction=transaction,
            actor_type="user",
            event_type=event_type,
            field_changes=changes,
            reason=payload.reason,
        )
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction_to_dict(transaction)


def get_manual_transaction(db_session: Session, transaction_id: str) -> LedgerTransaction:
    transaction = db_session.get(LedgerTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    if transaction.source != "manual":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="transaction is not manual",
        )
    return transaction


def get_active_manual_transaction(
    db_session: Session, transaction_id: str
) -> LedgerTransaction:
    transaction = get_manual_transaction(db_session, transaction_id)
    if transaction.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="transaction is deleted",
        )
    return transaction


def normalize_update_value(db_session: Session, field_name: str, value: Any) -> Any:
    if field_name == "amount":
        return parse_positive_decimal(value, "amount")
    if field_name == "transaction_date":
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise HTTPException(
                status_code=VALIDATION_ERROR_STATUS,
                detail="transaction_date must be an ISO date",
            ) from exc
    if field_name == "account_id":
        ensure_known_account(db_session, str(value))
        return str(value)
    if field_name == "category":
        category = None if value in (None, "") else str(value)
        ensure_active_category(db_session, category)
        return category
    if value is None:
        return None
    return str(value)


def ensure_known_account(db_session: Session, account_id: str) -> Account:
    account = db_session.get(Account, account_id)
    if account is None or account.deleted_at is not None:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS,
            detail="account_id is unknown",
        )
    return account


def ensure_active_category(db_session: Session, category_id: str | None) -> None:
    if category_id in (None, ""):
        return
    category = db_session.get(Category, category_id)
    if category is None or category.deleted_at is not None:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS,
            detail="category is not active",
        )


def parse_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS,
            detail=f"{field_name} must be a decimal value",
        ) from exc


def parse_positive_decimal(value: Any, field_name: str) -> Decimal:
    parsed = parse_decimal(value, field_name)
    if parsed <= Decimal("0.00"):
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS,
            detail=f"{field_name} must be greater than zero",
        )
    return parsed


def append_manual_history(
    transaction: LedgerTransaction, action: str, changes: dict[str, Any]
) -> None:
    source_metadata = dict(transaction.source_metadata or {})
    history = list(source_metadata.get("manual_history", []))
    history.append(
        {
            "action": action,
            "changed_at": datetime.now(UTC).isoformat(),
            "changes": changes,
        }
    )
    source_metadata["manual_history"] = history
    transaction.source_metadata = source_metadata


def transaction_to_dict(transaction: LedgerTransaction) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "transaction_date": serialize(transaction.transaction_date),
        "amount": serialize(transaction.amount),
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
        "deleted_at": serialize(transaction.deleted_at),
        "deleted_reason": transaction.deleted_reason,
    }


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value

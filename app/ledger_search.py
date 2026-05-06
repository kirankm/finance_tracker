from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import LedgerTransaction

VALID_SORT_FIELDS = {
    "transaction_date",
    "amount",
    "created_at",
    "updated_at",
    "merchant",
    "account_id",
}
VALID_SORT_DIRECTIONS = {"asc", "desc"}


@dataclass(frozen=True)
class LedgerSearchParams:
    transaction_id: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    account_id: str | None = None
    transaction_type: str | None = None
    purpose: str | None = None
    category: str | None = None
    merchant: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    review_status: str | None = None
    duplicate_status: str | None = None
    ledger_status: str | None = None
    source: str | None = None
    include_deleted: bool = False
    sort_by: str = "transaction_date"
    sort_dir: str = "desc"
    limit: int = 50
    offset: int = 0


def search_ledger_transactions(
    db_session: Session, params: LedgerSearchParams
) -> dict[str, Any]:
    validate_search_params(params)
    query = select(LedgerTransaction)

    query = apply_filters(query, params)
    total = db_session.scalar(select(func.count()).select_from(query.subquery())) or 0
    ordered_query = apply_sort(query, params).limit(params.limit).offset(params.offset)
    transactions = list(db_session.scalars(ordered_query))

    return {
        "items": [transaction_to_search_item(transaction) for transaction in transactions],
        "total": total,
        "limit": params.limit,
        "offset": params.offset,
        "sort_by": params.sort_by,
        "sort_dir": params.sort_dir,
    }


def validate_search_params(params: LedgerSearchParams) -> None:
    if params.sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(status_code=422, detail="unsupported sort_by")
    if params.sort_dir not in VALID_SORT_DIRECTIONS:
        raise HTTPException(status_code=422, detail="unsupported sort_dir")
    if params.date_from is not None and params.date_to is not None:
        if params.date_from > params.date_to:
            raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    if params.amount_min is not None and params.amount_max is not None:
        if params.amount_min > params.amount_max:
            raise HTTPException(
                status_code=422,
                detail="amount_min must be less than or equal to amount_max",
            )


def apply_filters(
    query: Select[tuple[LedgerTransaction]], params: LedgerSearchParams
) -> Select[tuple[LedgerTransaction]]:
    if not params.include_deleted:
        query = query.where(LedgerTransaction.deleted_at.is_(None))
    if params.transaction_id:
        query = query.where(LedgerTransaction.id == params.transaction_id)
    if params.date_from is not None:
        query = query.where(LedgerTransaction.transaction_date >= params.date_from)
    if params.date_to is not None:
        query = query.where(LedgerTransaction.transaction_date <= params.date_to)
    if params.account_id:
        query = query.where(LedgerTransaction.account_id == params.account_id)
    if params.transaction_type:
        query = query.where(LedgerTransaction.transaction_type == params.transaction_type)
    if params.purpose:
        query = query.where(LedgerTransaction.purpose == params.purpose)
    if params.category:
        query = query.where(LedgerTransaction.category == params.category)
    if params.merchant:
        merchant_pattern = f"%{escape_like(params.merchant.lower())}%"
        query = query.where(
            or_(
                func.lower(LedgerTransaction.merchant_raw).like(
                    merchant_pattern, escape="\\"
                ),
                func.lower(LedgerTransaction.merchant_canonical).like(
                    merchant_pattern, escape="\\"
                ),
            )
        )
    if params.amount_min is not None:
        query = query.where(LedgerTransaction.amount >= params.amount_min)
    if params.amount_max is not None:
        query = query.where(LedgerTransaction.amount <= params.amount_max)
    if params.review_status:
        query = query.where(LedgerTransaction.review_status == params.review_status)
    if params.duplicate_status:
        query = query.where(LedgerTransaction.duplicate_status == params.duplicate_status)
    if params.ledger_status:
        query = query.where(LedgerTransaction.ledger_status == params.ledger_status)
    if params.source:
        query = query.where(LedgerTransaction.source == params.source)
    return query


def apply_sort(
    query: Select[tuple[LedgerTransaction]], params: LedgerSearchParams
) -> Select[tuple[LedgerTransaction]]:
    sort_expression: Any
    if params.sort_by == "merchant":
        sort_expression = func.coalesce(
            LedgerTransaction.merchant_canonical,
            LedgerTransaction.merchant_raw,
            "",
        )
    else:
        sort_expression = getattr(LedgerTransaction, params.sort_by)

    primary_sort = sort_expression.desc() if params.sort_dir == "desc" else sort_expression.asc()
    date_tie_breaker = (
        LedgerTransaction.transaction_date.desc()
        if params.sort_dir == "desc"
        else LedgerTransaction.transaction_date.asc()
    )
    return query.order_by(primary_sort, date_tie_breaker, LedgerTransaction.id.asc())


def transaction_to_search_item(transaction: LedgerTransaction) -> dict[str, Any]:
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
        "raw_sms_message_id": transaction.raw_sms_message_id,
        "source": transaction.source,
        "parsing_confidence": transaction.parsing_confidence,
        "merchant_mapping_confidence": transaction.merchant_mapping_confidence,
        "category_confidence": transaction.category_confidence,
        "review_status": transaction.review_status,
        "duplicate_status": transaction.duplicate_status,
        "ledger_status": transaction.ledger_status,
        "source_context": source_context(transaction),
        "audit_event_count": len(transaction.audit_events),
        "deleted_at": serialize(transaction.deleted_at),
        "deleted_reason": transaction.deleted_reason,
        "created_at": serialize(transaction.created_at),
        "updated_at": serialize(transaction.updated_at),
    }


def source_context(transaction: LedgerTransaction) -> dict[str, Any]:
    metadata = dict(transaction.source_metadata or {})
    context: dict[str, Any] = {
        "raw_sms_id": metadata.get("raw_sms_id"),
        "external_message_id": metadata.get("external_message_id"),
        "raw_sms_source": metadata.get("raw_sms_source"),
        "reference": metadata.get("reference"),
        "available_balance": metadata.get("available_balance"),
        "duplicate_detection": metadata.get("duplicate_detection"),
        "ledger_sanity": metadata.get("ledger_sanity"),
        "manual_entry": metadata.get("manual_entry"),
        "cash_balance_update": metadata.get("cash_balance_update"),
    }
    manual_history = metadata.get("manual_history", [])
    if isinstance(manual_history, list):
        context["manual_history_count"] = len(manual_history)
    return {key: value for key, value in context.items() if value is not None}


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value

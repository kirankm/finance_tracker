from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.manual_transactions import VALIDATION_ERROR_STATUS, parse_decimal, serialize
from app.models import Account, AuditEvent, LedgerTransaction


class CashBalanceUpdatePayload(BaseModel):
    reported_balance: str = Field(min_length=1, max_length=40)
    reported_on: date
    record_difference_as_adjustment: bool = False
    reason: str | None = Field(default=None, max_length=500)


def update_cash_balance(
    db_session: Session, account_id: str, payload: CashBalanceUpdatePayload
) -> dict[str, Any]:
    account = db_session.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    if account.account_type != "cash":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account is not a cash account",
        )

    reported_balance = parse_non_negative_decimal(
        payload.reported_balance, "reported_balance"
    )
    expected_balance = account.current_balance
    difference = calculate_difference(expected_balance, reported_balance)
    adjustment_transaction: LedgerTransaction | None = None

    if (
        payload.record_difference_as_adjustment
        and expected_balance is not None
        and difference is not None
        and difference != Decimal("0.00")
    ):
        adjustment_transaction = create_cash_adjustment(
            account, payload, expected_balance, reported_balance, difference
        )
        db_session.add(adjustment_transaction)
        db_session.flush()
        db_session.add(
            AuditEvent(
                id=f"audit_{uuid4().hex}",
                transaction=adjustment_transaction,
                actor_type="user",
                event_type="cash_adjustment_created",
                field_changes={
                    "account_id": account.id,
                    "expected_balance": serialize(expected_balance),
                    "reported_balance": serialize(reported_balance),
                    "difference": serialize(difference),
                    "transaction_id": adjustment_transaction.id,
                },
                reason=payload.reason,
            )
        )

    changes = {
        "current_balance": {
            "before": serialize(account.current_balance),
            "after": serialize(reported_balance),
        },
        "last_manual_update": {
            "before": serialize(account.last_manual_update),
            "after": serialize(payload.reported_on),
        },
    }
    account.current_balance = reported_balance
    account.last_manual_update = payload.reported_on
    db_session.add(
        AuditEvent(
            id=f"audit_{uuid4().hex}",
            account=account,
            actor_type="user",
            event_type="cash_balance_updated",
            field_changes={
                **changes,
                "expected_balance": serialize(expected_balance),
                "reported_balance": serialize(reported_balance),
                "difference": serialize(difference),
                "adjustment_transaction_id": (
                    adjustment_transaction.id if adjustment_transaction is not None else None
                ),
            },
            reason=payload.reason,
        )
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    return {
        "account_id": account.id,
        "expected_balance": serialize(expected_balance),
        "reported_balance": serialize(reported_balance),
        "difference": serialize(difference),
        "adjustment_transaction_id": (
            adjustment_transaction.id if adjustment_transaction is not None else None
        ),
        "current_balance": serialize(account.current_balance),
        "last_manual_update": serialize(account.last_manual_update),
    }


def calculate_difference(
    expected_balance: Decimal | None, reported_balance: Decimal
) -> Decimal | None:
    if expected_balance is None:
        return None
    return (expected_balance - reported_balance).quantize(Decimal("0.01"))


def parse_non_negative_decimal(value: Any, field_name: str) -> Decimal:
    parsed = parse_decimal(value, field_name)
    if parsed < Decimal("0.00"):
        raise HTTPException(
            status_code=VALIDATION_ERROR_STATUS,
            detail=f"{field_name} must not be negative",
        )
    return parsed


def create_cash_adjustment(
    account: Account,
    payload: CashBalanceUpdatePayload,
    expected_balance: Decimal,
    reported_balance: Decimal,
    difference: Decimal,
) -> LedgerTransaction:
    direction = "shortfall" if difference > 0 else "surplus"
    return LedgerTransaction(
        id=f"txn_{uuid4().hex}",
        transaction_date=payload.reported_on,
        amount=abs(difference),
        transaction_type="cash_adjustment",
        purpose="cash_update",
        category="cash_spend" if direction == "shortfall" else "cash_surplus",
        merchant_raw="manual_cash_balance_update",
        merchant_canonical="Manual Cash Balance Update",
        account=account,
        source="manual",
        review_status="reviewed",
        duplicate_status="unique",
        ledger_status="included",
        source_metadata={
            "cash_adjustment": {
                "direction": direction,
                "expected_balance": serialize(expected_balance),
                "reported_balance": serialize(reported_balance),
                "difference": serialize(difference),
            }
        },
    )

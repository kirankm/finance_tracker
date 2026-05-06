from calendar import monthrange
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerTransaction

SPECIAL_PURPOSES = ("investment", "savings", "transfer", "refund", "reversal", "cash_update")


@dataclass(frozen=True)
class AnalysisParams:
    month: str | None = None
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class AnalysisPeriod:
    date_from: date
    date_to: date
    month: str | None


def get_analysis_summary(db_session: Session, params: AnalysisParams) -> dict[str, Any]:
    period = resolve_period(params)
    transactions = list(
        db_session.scalars(
            select(LedgerTransaction).where(
                LedgerTransaction.transaction_date >= period.date_from,
                LedgerTransaction.transaction_date <= period.date_to,
            )
        )
    )
    eligible_transactions = [
        transaction for transaction in transactions if is_eligible_for_analysis(transaction)
    ]
    normal_expenses = [
        transaction for transaction in eligible_transactions if transaction.purpose == "expense"
    ]
    income_transactions = [
        transaction for transaction in eligible_transactions if transaction.purpose == "income"
    ]
    cash_updates = [
        transaction
        for transaction in eligible_transactions
        if transaction.purpose == "cash_update"
        or transaction.transaction_type == "cash_adjustment"
    ]
    other_included = [
        transaction
        for transaction in eligible_transactions
        if transaction.purpose not in ("expense", "income", *SPECIAL_PURPOSES)
    ]

    return {
        "period": {
            "date_from": period.date_from.isoformat(),
            "date_to": period.date_to.isoformat(),
            "month": period.month,
        },
        "income_vs_expense": {
            "income": serialize_decimal(sum_amounts(income_transactions)),
            "normal_expense": serialize_decimal(sum_amounts(normal_expenses)),
        },
        "spending_by_category": grouped_totals(
            normal_expenses,
            key_func=lambda transaction: transaction.category or "unknown",
            label_name="category",
        ),
        "spending_by_account": grouped_account_totals(normal_expenses),
        "separated_totals": {
            purpose: {
                "total": serialize_decimal(
                    sum_amounts(
                        [
                            transaction
                            for transaction in eligible_transactions
                            if transaction.purpose == purpose
                        ]
                    )
                ),
                "count": sum(
                    1 for transaction in eligible_transactions if transaction.purpose == purpose
                ),
            }
            for purpose in SPECIAL_PURPOSES
        },
        "cash_balance_changes": {
            "total": serialize_decimal(sum_amounts(cash_updates)),
            "count": len(cash_updates),
        },
        "other_included": {
            "total": serialize_decimal(sum_amounts(other_included)),
            "count": len(other_included),
        },
        "quality_counts": quality_counts(transactions, eligible_transactions),
    }


def resolve_period(params: AnalysisParams) -> AnalysisPeriod:
    if params.month is not None:
        if params.date_from is not None or params.date_to is not None:
            raise HTTPException(
                status_code=422,
                detail="month cannot be combined with date_from or date_to",
            )
        return month_period(params.month)

    if params.date_from is not None or params.date_to is not None:
        if params.date_from is None or params.date_to is None:
            raise HTTPException(
                status_code=422,
                detail="date_from and date_to must be provided together",
            )
        if params.date_from > params.date_to:
            raise HTTPException(
                status_code=422,
                detail="date_from must be on or before date_to",
            )
        return AnalysisPeriod(
            date_from=params.date_from,
            date_to=params.date_to,
            month=None,
        )

    now = datetime.now(UTC)
    return month_period(f"{now.year:04d}-{now.month:02d}")


def month_period(month: str) -> AnalysisPeriod:
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(status_code=422, detail="month must use YYYY-MM format")
    try:
        year_text, month_text = month.split("-", maxsplit=1)
        year = int(year_text)
        month_number = int(month_text)
        last_day = monthrange(year, month_number)[1]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must use YYYY-MM format") from exc

    return AnalysisPeriod(
        date_from=date(year, month_number, 1),
        date_to=date(year, month_number, last_day),
        month=month,
    )


def is_eligible_for_analysis(transaction: LedgerTransaction) -> bool:
    return (
        transaction.deleted_at is None
        and transaction.review_status == "reviewed"
        and transaction.duplicate_status == "unique"
        and transaction.ledger_status == "included"
    )


def grouped_totals(
    transactions: list[LedgerTransaction],
    *,
    key_func: Callable[[LedgerTransaction], str],
    label_name: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for transaction in transactions:
        key = str(key_func(transaction))
        row = grouped.setdefault(key, {label_name: key, "total": Decimal("0.00"), "count": 0})
        row["total"] += transaction.amount
        row["count"] += 1
    return sorted_serialized_totals(grouped.values(), label_name)


def grouped_account_totals(transactions: list[LedgerTransaction]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for transaction in transactions:
        account_name = transaction.account.name if transaction.account is not None else None
        row = grouped.setdefault(
            transaction.account_id,
            {
                "account_id": transaction.account_id,
                "account_name": account_name,
                "total": Decimal("0.00"),
                "count": 0,
            },
        )
        row["total"] += transaction.amount
        row["count"] += 1
    return sorted_serialized_totals(grouped.values(), "account_id")


def sorted_serialized_totals(
    rows: Iterable[dict[str, Any]], fallback_label: str
) -> list[dict[str, Any]]:
    serialized_rows = []
    for row in rows:
        serialized = dict(row)
        serialized["total"] = serialize_decimal(serialized["total"])
        serialized_rows.append(serialized)
    return sorted(
        serialized_rows,
        key=lambda row: (Decimal(str(row["total"])), str(row[fallback_label])),
        reverse=True,
    )


def quality_counts(
    transactions: list[LedgerTransaction],
    eligible_transactions: list[LedgerTransaction],
) -> dict[str, int]:
    eligible_ids = {transaction.id for transaction in eligible_transactions}
    return {
        "review_needed": sum(
            1
            for transaction in transactions
            if transaction.deleted_at is None
            and (
                transaction.review_status == "needs_review"
                or transaction.ledger_status == "needs_review"
            )
        ),
        "unmapped_category": sum(
            1
            for transaction in transactions
            if transaction.deleted_at is None and transaction.category in (None, "", "unknown")
        ),
        "unmapped_merchant": sum(
            1
            for transaction in transactions
            if transaction.deleted_at is None
            and not transaction.merchant_raw
            and not transaction.merchant_canonical
        ),
        "excluded_from_totals": sum(
            1 for transaction in transactions if transaction.id not in eligible_ids
        ),
    }


def sum_amounts(transactions: list[LedgerTransaction]) -> Decimal:
    total = Decimal("0.00")
    for transaction in transactions:
        total += transaction.amount
    return total


def serialize_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))

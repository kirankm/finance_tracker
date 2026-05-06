import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis import AnalysisParams, AnalysisPeriod, is_eligible_for_analysis, resolve_period
from app.models import AuditEvent, LedgerTransaction

InsightState = Literal["active", "dismissed", "reviewed"]

INSIGHT_STATE_EVENTS: dict[str, InsightState] = {
    "insight_dismissed": "dismissed",
    "insight_reviewed": "reviewed",
}
DUPLICATE_STATUSES = {"possible_duplicate", "exact_duplicate", "confirmed_duplicate"}
CATEGORY_CHANGE_MIN_CURRENT = Decimal("100.00")
CATEGORY_CHANGE_MIN_INCREASE = Decimal("100.00")
CATEGORY_CHANGE_RATIO = Decimal("1.50")


class InsightActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


@dataclass(frozen=True)
class InsightsParams:
    month: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    include_dismissed: bool = False
    include_reviewed: bool = False


@dataclass
class CategorySpendGroup:
    total: Decimal
    items: list[LedgerTransaction]


def list_insights(db_session: Session, params: InsightsParams) -> dict[str, Any]:
    period = resolve_period(
        AnalysisParams(
            month=params.month,
            date_from=params.date_from,
            date_to=params.date_to,
        )
    )
    transactions = transactions_for_period(db_session, period)
    insights = generate_insights(db_session, period, transactions)
    states = load_insight_states(db_session)
    visible_insights = []
    for insight in insights:
        state = states.get(str(insight["id"]), "active")
        if state == "dismissed" and not params.include_dismissed:
            continue
        if state == "reviewed" and not params.include_reviewed:
            continue
        visible_insights.append({**insight, "state": state})

    return {
        "period": period_to_dict(period),
        "items": visible_insights,
        "total": len(visible_insights),
    }


def generate_insights(
    db_session: Session,
    period: AnalysisPeriod,
    transactions: list[LedgerTransaction],
) -> list[dict[str, Any]]:
    insights = [
        build_unmapped_insight(period, transactions),
        build_possible_duplicate_insight(period, transactions),
        build_ledger_mismatch_insight(period, transactions),
        build_cash_mismatch_insight(period, transactions),
        *build_category_change_insights(db_session, period, transactions),
    ]
    return [insight for insight in insights if insight is not None]


def build_unmapped_insight(
    period: AnalysisPeriod, transactions: list[LedgerTransaction]
) -> dict[str, Any] | None:
    linked = [
        transaction
        for transaction in transactions
        if transaction.deleted_at is None
        and (
            transaction.category in (None, "", "unknown")
            or not transaction.merchant_raw
            and not transaction.merchant_canonical
        )
    ]
    if not linked:
        return None
    return make_insight(
        insight_type="unmapped_transactions",
        severity="medium",
        title="Unmapped transactions need review",
        summary=f"{len(linked)} transaction(s) have missing category or merchant data.",
        period=period,
        transactions=linked,
        metadata={"count": len(linked)},
    )


def build_possible_duplicate_insight(
    period: AnalysisPeriod, transactions: list[LedgerTransaction]
) -> dict[str, Any] | None:
    linked = [
        transaction
        for transaction in transactions
        if transaction.deleted_at is None and transaction.duplicate_status in DUPLICATE_STATUSES
    ]
    if not linked:
        return None
    return make_insight(
        insight_type="possible_duplicates",
        severity="high",
        title="Possible duplicate transactions",
        summary=f"{len(linked)} transaction(s) are marked as possible or confirmed duplicates.",
        period=period,
        transactions=linked,
        metadata={"duplicate_statuses": sorted({item.duplicate_status for item in linked})},
    )


def build_ledger_mismatch_insight(
    period: AnalysisPeriod, transactions: list[LedgerTransaction]
) -> dict[str, Any] | None:
    linked = [
        transaction
        for transaction in transactions
        if transaction.deleted_at is None
        and (
            transaction.ledger_status == "needs_review"
            or metadata_status(transaction, "ledger_sanity") == "mismatch"
        )
    ]
    if not linked:
        return None
    return make_insight(
        insight_type="ledger_mismatches",
        severity="high",
        title="Ledger mismatches need review",
        summary=f"{len(linked)} transaction(s) have ledger sanity mismatches.",
        period=period,
        transactions=linked,
        metadata={"count": len(linked)},
    )


def build_cash_mismatch_insight(
    period: AnalysisPeriod, transactions: list[LedgerTransaction]
) -> dict[str, Any] | None:
    linked = [
        transaction
        for transaction in transactions
        if transaction.deleted_at is None
        and transaction.transaction_type == "cash_adjustment"
        and cash_adjustment_difference(transaction) != Decimal("0.00")
    ]
    if not linked:
        return None
    return make_insight(
        insight_type="cash_mismatches",
        severity="medium",
        title="Cash balance differences recorded",
        summary=f"{len(linked)} cash balance adjustment(s) were recorded.",
        period=period,
        transactions=linked,
        metadata={"total_adjustments": serialize_decimal(sum_amounts(linked))},
    )


def build_category_change_insights(
    db_session: Session,
    period: AnalysisPeriod,
    transactions: list[LedgerTransaction],
) -> list[dict[str, Any]]:
    previous_period = preceding_period(period)
    previous_transactions = transactions_for_period(db_session, previous_period)
    current_by_category = normal_expense_by_category(transactions)
    previous_by_category = normal_expense_by_category(previous_transactions)
    insights = []
    for category, current in current_by_category.items():
        previous = previous_by_category.get(
            category, CategorySpendGroup(total=Decimal("0.00"), items=[])
        )
        previous_total = previous.total
        current_total = current.total
        increase = current_total - previous_total
        if not is_notable_category_change(current_total, previous_total, increase):
            continue
        insights.append(
            make_insight(
                insight_type="notable_category_change",
                severity="low",
                title=f"{category} spending changed notably",
                summary=(
                    f"{category} spending is {serialize_decimal(current_total)} "
                    f"vs {serialize_decimal(previous_total)} in the previous period."
                ),
                period=period,
                transactions=current.items,
                metadata={
                    "category": category,
                    "current_total": serialize_decimal(current_total),
                    "previous_total": serialize_decimal(previous_total),
                    "increase": serialize_decimal(increase),
                },
            )
        )
    return insights


def is_notable_category_change(
    current_total: Decimal, previous_total: Decimal, increase: Decimal
) -> bool:
    if current_total < CATEGORY_CHANGE_MIN_CURRENT or increase < CATEGORY_CHANGE_MIN_INCREASE:
        return False
    if previous_total == Decimal("0.00"):
        return True
    return current_total >= (previous_total * CATEGORY_CHANGE_RATIO)


def normal_expense_by_category(
    transactions: list[LedgerTransaction],
) -> dict[str, CategorySpendGroup]:
    grouped: dict[str, CategorySpendGroup] = {}
    for transaction in transactions:
        if not is_eligible_for_analysis(transaction) or transaction.purpose != "expense":
            continue
        category = transaction.category or "unknown"
        row = grouped.setdefault(
            category, CategorySpendGroup(total=Decimal("0.00"), items=[])
        )
        row.total += transaction.amount
        row.items.append(transaction)
    return grouped


def make_insight(
    *,
    insight_type: str,
    severity: str,
    title: str,
    summary: str,
    period: AnalysisPeriod,
    transactions: list[LedgerTransaction],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    transaction_ids = sorted(transaction.id for transaction in transactions)
    insight_id = stable_insight_id(insight_type, period, transaction_ids, metadata)
    return {
        "id": insight_id,
        "type": insight_type,
        "severity": severity,
        "title": title,
        "summary": summary,
        "period": period_to_dict(period),
        "transaction_ids": transaction_ids,
        "metadata": metadata,
        "state": "active",
    }


def stable_insight_id(
    insight_type: str,
    period: AnalysisPeriod,
    transaction_ids: list[str],
    metadata: dict[str, Any],
) -> str:
    payload = json.dumps(
        {
            "type": insight_type,
            "period": period_to_dict(period),
            "transaction_ids": transaction_ids,
            "metadata": metadata,
        },
        sort_keys=True,
    )
    return f"insight_{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def mark_insight_dismissed(
    db_session: Session, insight_id: str, payload: InsightActionPayload
) -> dict[str, Any]:
    return mark_insight_state(
        db_session,
        insight_id,
        payload,
        event_type="insight_dismissed",
        next_state="dismissed",
    )


def mark_insight_reviewed(
    db_session: Session, insight_id: str, payload: InsightActionPayload
) -> dict[str, Any]:
    return mark_insight_state(
        db_session,
        insight_id,
        payload,
        event_type="insight_reviewed",
        next_state="reviewed",
    )


def mark_insight_state(
    db_session: Session,
    insight_id: str,
    payload: InsightActionPayload,
    *,
    event_type: str,
    next_state: InsightState,
) -> dict[str, Any]:
    if not insight_id.startswith("insight_"):
        raise HTTPException(status_code=422, detail="insight_id must be deterministic")
    previous_state = load_insight_states(db_session).get(insight_id, "active")
    audit_event = AuditEvent(
        id=f"audit_{uuid4().hex}",
        actor_type="user",
        event_type=event_type,
        field_changes={
            "insight_id": insight_id,
            "state": {"before": previous_state, "after": next_state},
        },
        reason=payload.reason,
    )
    db_session.add(audit_event)
    db_session.commit()
    return {"insight_id": insight_id, "state": next_state}


def load_insight_states(db_session: Session) -> dict[str, InsightState]:
    states: dict[str, InsightState] = {}
    events = db_session.scalars(
        select(AuditEvent)
        .where(AuditEvent.event_type.in_(tuple(INSIGHT_STATE_EVENTS)))
        .order_by(AuditEvent.created_at, AuditEvent.id)
    )
    for event in events:
        insight_id = event.field_changes.get("insight_id")
        state = INSIGHT_STATE_EVENTS.get(event.event_type)
        if isinstance(insight_id, str) and state is not None:
            states[insight_id] = state
    return states


def transactions_for_period(
    db_session: Session, period: AnalysisPeriod
) -> list[LedgerTransaction]:
    return list(
        db_session.scalars(
            select(LedgerTransaction).where(
                LedgerTransaction.transaction_date >= period.date_from,
                LedgerTransaction.transaction_date <= period.date_to,
            )
        )
    )


def preceding_period(period: AnalysisPeriod) -> AnalysisPeriod:
    if period.month is not None:
        year_text, month_text = period.month.split("-", maxsplit=1)
        year = int(year_text)
        month = int(month_text)
        if month == 1:
            return resolve_period(AnalysisParams(month=f"{year - 1:04d}-12"))
        return resolve_period(AnalysisParams(month=f"{year:04d}-{month - 1:02d}"))

    length = period.date_to - period.date_from
    previous_to = period.date_from - timedelta(days=1)
    previous_from = previous_to - length
    return AnalysisPeriod(date_from=previous_from, date_to=previous_to, month=None)


def metadata_status(transaction: LedgerTransaction, key: str) -> str | None:
    metadata = dict(transaction.source_metadata or {}).get(key, {})
    if isinstance(metadata, dict):
        status = metadata.get("status")
        if isinstance(status, str):
            return status
    return None


def cash_adjustment_difference(transaction: LedgerTransaction) -> Decimal:
    metadata = dict(transaction.source_metadata or {}).get("cash_adjustment", {})
    if not isinstance(metadata, dict):
        return Decimal("0.00")
    value = metadata.get("difference")
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).copy_abs()


def sum_amounts(transactions: Iterable[LedgerTransaction]) -> Decimal:
    total = Decimal("0.00")
    for transaction in transactions:
        total += transaction.amount
    return total


def period_to_dict(period: AnalysisPeriod) -> dict[str, str | None]:
    return {
        "date_from": period.date_from.isoformat(),
        "date_to": period.date_to.isoformat(),
        "month": period.month,
    }


def serialize_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))

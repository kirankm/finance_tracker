from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.duplicate_detection import DuplicateDecision
from app.models import Account, LedgerTransaction

LedgerSanityStatus = Literal["not_checked", "matched", "mismatch"]
LedgerSanityConfidence = Literal["high", "low"]


@dataclass(frozen=True)
class LedgerSanityDecision:
    status: LedgerSanityStatus
    ledger_status: str
    reason: str
    account_id: str
    basis: list[str]
    confidence: LedgerSanityConfidence
    transaction_type: str | None = None
    starting_balance: Decimal | None = None
    balance_impact: Decimal | None = None
    expected_balance: Decimal | None = None
    observed_balance: Decimal | None = None
    mismatch_amount: Decimal | None = None

    def as_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "status": self.status,
            "ledger_status": self.ledger_status,
            "reason": self.reason,
            "account_id": self.account_id,
        }
        if self.transaction_type is not None:
            metadata["transaction_type"] = self.transaction_type
        if self.starting_balance is not None:
            metadata["starting_balance"] = format_decimal(self.starting_balance)
        if self.balance_impact is not None:
            metadata["balance_impact"] = format_decimal(self.balance_impact)
        if self.expected_balance is not None:
            metadata["expected_balance"] = format_decimal(self.expected_balance)
        if self.observed_balance is not None:
            metadata["observed_balance"] = format_decimal(self.observed_balance)
        if self.mismatch_amount is not None:
            metadata["mismatch_amount"] = format_decimal(self.mismatch_amount)
        metadata["basis"] = self.basis
        metadata["confidence"] = self.confidence
        return metadata


def evaluate_ledger_sanity(
    *,
    db_session: Session,
    account: Account,
    candidate: dict[str, Any],
    duplicate_decision: DuplicateDecision,
) -> LedgerSanityDecision:
    if duplicate_decision.ledger_status == "excluded":
        return LedgerSanityDecision(
            status="not_checked",
            ledger_status=duplicate_decision.ledger_status,
            reason="ledger_excluded_duplicate_not_balance_impacting",
            account_id=account.id,
            basis=["duplicate_status", "ledger_status"],
            confidence="high",
        )

    observed_balance = normalize_decimal(candidate.get("available_balance"))
    if observed_balance is None:
        return LedgerSanityDecision(
            status="not_checked",
            ledger_status=duplicate_decision.ledger_status,
            reason="available_balance_missing",
            account_id=account.id,
            basis=["available_balance"],
            confidence="low",
        )

    starting_balance = normalize_decimal(account.current_balance)
    if starting_balance is None:
        return LedgerSanityDecision(
            status="not_checked",
            ledger_status=duplicate_decision.ledger_status,
            reason="account_current_balance_missing",
            account_id=account.id,
            basis=["account.current_balance", "available_balance"],
            confidence="low",
        )

    amount = normalize_decimal(candidate.get("amount"))
    transaction_type = candidate.get("transaction_type")
    if amount is None or not isinstance(transaction_type, str):
        return LedgerSanityDecision(
            status="not_checked",
            ledger_status=duplicate_decision.ledger_status,
            reason="balance_impact_inputs_missing",
            account_id=account.id,
            basis=["amount", "transaction_type", "available_balance"],
            confidence="low",
        )

    balance_impact = balance_impact_for(transaction_type, amount)
    if balance_impact is None:
        return LedgerSanityDecision(
            status="not_checked",
            ledger_status=duplicate_decision.ledger_status,
            reason="transaction_type_not_balance_checked",
            account_id=account.id,
            basis=["transaction_type", "available_balance"],
            confidence="low",
        )

    existing_included_impact = calculate_existing_included_impact(db_session, account.id)
    effective_starting_balance = (starting_balance + existing_included_impact).quantize(
        Decimal("0.01")
    )
    expected_balance = (effective_starting_balance + balance_impact).quantize(Decimal("0.01"))
    mismatch_amount = (observed_balance - expected_balance).quantize(Decimal("0.01"))
    status: LedgerSanityStatus = "matched" if mismatch_amount == Decimal("0.00") else "mismatch"
    ledger_status = duplicate_decision.ledger_status if status == "matched" else "needs_review"
    reason = (
        "available_balance_matches_expected_post_transaction_balance"
        if status == "matched"
        else "available_balance_differs_from_expected_post_transaction_balance"
    )

    return LedgerSanityDecision(
        status=status,
        ledger_status=ledger_status,
        reason=reason,
        account_id=account.id,
        transaction_type=transaction_type,
        starting_balance=effective_starting_balance,
        balance_impact=balance_impact,
        expected_balance=expected_balance,
        observed_balance=observed_balance,
        mismatch_amount=mismatch_amount,
        basis=[
            "account.current_balance",
            "amount",
            "transaction_type",
            "available_balance",
        ],
        confidence="high",
    )


def balance_impact_for(transaction_type: str, amount: Decimal) -> Decimal | None:
    if transaction_type == "debit":
        return -amount
    if transaction_type == "credit":
        return amount
    return None


def calculate_existing_included_impact(db_session: Session, account_id: str) -> Decimal:
    transactions = db_session.scalars(
        select(LedgerTransaction).where(
            LedgerTransaction.account_id == account_id,
            LedgerTransaction.ledger_status == "included",
            LedgerTransaction.deleted_at.is_(None),
        )
    ).all()

    total = Decimal("0.00")
    for transaction in transactions:
        impact = balance_impact_for(transaction.transaction_type, transaction.amount)
        if impact is not None:
            total += impact
    return total.quantize(Decimal("0.01"))


def normalize_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def format_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))

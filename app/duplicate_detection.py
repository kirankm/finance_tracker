from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerTransaction

DuplicateStatus = Literal["unique", "exact_duplicate", "possible_duplicate"]
DuplicateConfidence = Literal["high", "medium"]


@dataclass(frozen=True)
class DuplicateDecision:
    status: DuplicateStatus
    ledger_status: Literal["included", "excluded"]
    reason: str
    matched_transaction_id: str | None
    matched_raw_sms_id: str | None
    basis: list[str]
    confidence: DuplicateConfidence

    def as_metadata(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ledger_status": self.ledger_status,
            "reason": self.reason,
            "matched_transaction_id": self.matched_transaction_id,
            "matched_raw_sms_id": self.matched_raw_sms_id,
            "basis": self.basis,
            "confidence": self.confidence,
        }


UNIQUE_DECISION = DuplicateDecision(
    status="unique",
    ledger_status="included",
    reason="no_duplicate_match",
    matched_transaction_id=None,
    matched_raw_sms_id=None,
    basis=[],
    confidence="high",
)


def detect_duplicate_candidate(
    db_session: Session,
    candidate: dict[str, Any],
) -> DuplicateDecision:
    candidate_account_id = candidate.get("account_id")
    candidate_reference = candidate.get("reference")
    candidate_amount = normalize_amount(candidate.get("amount"))
    candidate_date = normalize_date(candidate.get("transaction_date"))
    candidate_type = candidate.get("transaction_type")
    candidate_merchant = candidate.get("merchant_canonical")

    if (
        candidate_account_id is None
        or candidate_amount is None
        or candidate_date is None
        or candidate_type is None
    ):
        return UNIQUE_DECISION

    existing_transactions = db_session.scalars(
        select(LedgerTransaction).where(
            LedgerTransaction.account_id == str(candidate_account_id),
            LedgerTransaction.amount == candidate_amount,
            LedgerTransaction.transaction_date == candidate_date,
            LedgerTransaction.transaction_type == str(candidate_type),
            LedgerTransaction.ledger_status == "included",
            LedgerTransaction.deleted_at.is_(None),
        ).order_by(LedgerTransaction.created_at, LedgerTransaction.id)
    ).all()

    if isinstance(candidate_reference, str) and candidate_reference:
        for transaction in existing_transactions:
            if transaction.source_metadata.get("reference") == candidate_reference:
                return DuplicateDecision(
                    status="exact_duplicate",
                    ledger_status="excluded",
                    reason="same_reference_amount_date_account_and_type",
                    matched_transaction_id=transaction.id,
                    matched_raw_sms_id=transaction.raw_sms_message_id,
                    basis=[
                        "account_id",
                        "reference",
                        "amount",
                        "transaction_date",
                        "transaction_type",
                    ],
                    confidence="high",
                )

    if isinstance(candidate_merchant, str) and candidate_merchant:
        for transaction in existing_transactions:
            if transaction.merchant_canonical == candidate_merchant:
                return DuplicateDecision(
                    status="possible_duplicate",
                    ledger_status="excluded",
                    reason="same_amount_date_account_type_and_merchant",
                    matched_transaction_id=transaction.id,
                    matched_raw_sms_id=transaction.raw_sms_message_id,
                    basis=[
                        "account_id",
                        "amount",
                        "transaction_date",
                        "transaction_type",
                        "merchant_canonical",
                    ],
                    confidence="medium",
                )

    return UNIQUE_DECISION


def normalize_amount(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def normalize_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None

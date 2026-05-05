import re
from typing import Any

from pydantic import BaseModel, ConfigDict


class TransactionCandidate(BaseModel):
    transaction_type: str
    purpose: str
    amount: int | None = None
    account_clue: str | None = None
    merchant_raw: str | None = None
    transaction_date: str | None = None
    available_balance: int | None = None
    reference: str | None = None
    source: str = "sms"
    review_status: str
    confidence: dict[str, str]
    parser_metadata: dict[str, Any]

    model_config = ConfigDict(frozen=True)


DEBIT_UPI_PATTERN = re.compile(
    r"Rs\.(?P<amount>\d+(?:\.\d{1,2})?) debited from "
    r"(?P<account_clue>.+?) to (?P<merchant_raw>.+?) on "
    r"(?P<day>\d{2})-(?P<month>[A-Za-z]{3})-(?P<year>\d{4})\. "
    r"Avl Bal Rs\.(?P<available_balance>\d+(?:\.\d{1,2})?)\. "
    r"Ref (?P<reference>[A-Za-z0-9]+)\.",
    re.IGNORECASE,
)

MONTHS = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def parse_sms(message: str) -> TransactionCandidate:
    match = DEBIT_UPI_PATTERN.search(message.strip())
    if match is None:
        return TransactionCandidate(
            transaction_type="unknown",
            purpose="unknown",
            source="sms",
            review_status="needs_review",
            confidence={"parsing": "low"},
            parser_metadata={
                "parser": "unrecognized_financial_sms_v1",
                "extracted_fields": [],
            },
        )

    groups = match.groupdict()
    month = MONTHS[groups["month"].lower()]
    transaction_date = f"{groups['year']}-{month}-{groups['day']}"

    return TransactionCandidate(
        transaction_type="debit",
        purpose="expense",
        amount=int(float(groups["amount"])),
        account_clue=groups["account_clue"],
        merchant_raw=groups["merchant_raw"],
        transaction_date=transaction_date,
        available_balance=int(float(groups["available_balance"])),
        reference=groups["reference"],
        source="sms",
        review_status="needs_review",
        confidence={"parsing": "high"},
        parser_metadata={
            "parser": "fake_upi_debit_v1",
            "extracted_fields": [
                "amount",
                "account_clue",
                "merchant_raw",
                "date",
                "available_balance",
                "reference",
            ],
        },
    )

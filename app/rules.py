from typing import Any

from pydantic import BaseModel, ConfigDict

from app.sms_parser import TransactionCandidate


class AccountRule(BaseModel):
    rule_id: str
    account_clue: str
    account_id: str

    model_config = ConfigDict(frozen=True)


class MerchantRule(BaseModel):
    rule_id: str
    merchant_raw: str
    merchant_canonical: str
    default_category: str

    model_config = ConfigDict(frozen=True)


class EnrichedTransactionCandidate(TransactionCandidate):
    account_id: str | None = None
    merchant_canonical: str | None = None
    category: str | None = None
    rule_metadata: dict[str, dict[str, Any]]

    model_config = ConfigDict(frozen=True)


ACCOUNT_RULES = (
    AccountRule(
        rule_id="account_bank_1_masked_0000_v1",
        account_clue="BANK_1 a/c XX0000",
        account_id="acct_bank_1",
    ),
)

MERCHANT_RULES = (
    MerchantRule(
        rule_id="merchant_food_1_v1",
        merchant_raw="MERCHANT_FOOD_1",
        merchant_canonical="Merchant Food 1",
        default_category="food_delivery",
    ),
)


def enrich_candidate(candidate: TransactionCandidate) -> EnrichedTransactionCandidate:
    confidence = dict(candidate.confidence)
    rule_metadata: dict[str, dict[str, Any]] = {}

    account_id = apply_account_mapping(
        candidate.account_clue,
        confidence=confidence,
        rule_metadata=rule_metadata,
    )
    merchant_canonical, category = apply_merchant_mapping(
        candidate.merchant_raw,
        confidence=confidence,
        rule_metadata=rule_metadata,
    )
    rule_metadata["transaction_type"] = {
        "reason": "preserved_parser_value",
        "value": candidate.transaction_type,
    }
    rule_metadata["purpose"] = {
        "reason": "preserved_parser_value",
        "value": candidate.purpose,
    }

    candidate_data = candidate.model_dump()
    candidate_data["confidence"] = confidence

    return EnrichedTransactionCandidate(
        **candidate_data,
        account_id=account_id,
        merchant_canonical=merchant_canonical,
        category=category,
        rule_metadata=rule_metadata,
    )


def apply_account_mapping(
    account_clue: str | None,
    *,
    confidence: dict[str, str],
    rule_metadata: dict[str, dict[str, Any]],
) -> str | None:
    if account_clue is None:
        confidence["account_mapping"] = "low"
        rule_metadata["account_mapping"] = {"reason": "missing_account_clue"}
        return None

    for rule in ACCOUNT_RULES:
        if rule.account_clue == account_clue:
            confidence["account_mapping"] = "high"
            rule_metadata["account_mapping"] = {
                "rule_id": rule.rule_id,
                "matched_value": account_clue,
            }
            return rule.account_id

    confidence["account_mapping"] = "low"
    rule_metadata["account_mapping"] = {
        "reason": "unknown_account_clue",
        "matched_value": account_clue,
    }
    return None


def apply_merchant_mapping(
    merchant_raw: str | None,
    *,
    confidence: dict[str, str],
    rule_metadata: dict[str, dict[str, Any]],
) -> tuple[str | None, str | None]:
    if merchant_raw is None:
        confidence["merchant_mapping"] = "low"
        confidence["category"] = "low"
        rule_metadata["merchant_mapping"] = {"reason": "missing_merchant_raw"}
        rule_metadata["category"] = {"reason": "missing_merchant_raw"}
        return None, None

    for rule in MERCHANT_RULES:
        if rule.merchant_raw == merchant_raw:
            confidence["merchant_mapping"] = "high"
            confidence["category"] = "high"
            rule_metadata["merchant_mapping"] = {
                "rule_id": rule.rule_id,
                "matched_value": merchant_raw,
            }
            rule_metadata["category"] = {
                "rule_id": rule.rule_id,
                "source": "merchant_default_category",
            }
            return rule.merchant_canonical, rule.default_category

    confidence["merchant_mapping"] = "low"
    confidence["category"] = "low"
    rule_metadata["merchant_mapping"] = {
        "reason": "unknown_merchant_raw",
        "matched_value": merchant_raw,
    }
    rule_metadata["category"] = {
        "reason": "no_category_rule",
        "matched_value": merchant_raw,
    }
    return None, None

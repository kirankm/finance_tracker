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


class UserApprovedRule(BaseModel):
    rule_id: str
    match_merchant_raw: str | None = None
    match_account_clue: str | None = None
    set_account_id: str | None = None
    set_merchant_canonical: str | None = None
    set_category: str | None = None
    set_purpose: str | None = None
    priority: int = 10

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


def enrich_candidate(
    candidate: TransactionCandidate,
    *,
    user_rules: list[UserApprovedRule] | None = None,
) -> EnrichedTransactionCandidate:
    confidence = dict(candidate.confidence)
    rule_metadata: dict[str, dict[str, Any]] = {}
    user_rule = first_matching_user_rule(candidate, user_rules or [])

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

    if user_rule is not None:
        matched_fields = matched_user_rule_fields(candidate, user_rule)
        rule_metadata["user_approved_rule"] = {
            "rule_id": user_rule.rule_id,
            "matched_fields": matched_fields,
            "priority": user_rule.priority,
        }
        if user_rule.set_account_id is not None:
            account_id = user_rule.set_account_id
            confidence["account_mapping"] = "high"
            rule_metadata["account_mapping"] = {
                "rule_id": user_rule.rule_id,
                "source": "user_approved_rule",
            }
        if user_rule.set_merchant_canonical is not None:
            merchant_canonical = user_rule.set_merchant_canonical
            confidence["merchant_mapping"] = "high"
            rule_metadata["merchant_mapping"] = {
                "rule_id": user_rule.rule_id,
                "source": "user_approved_rule",
            }
        if user_rule.set_category is not None:
            category = user_rule.set_category
            confidence["category"] = "high"
            rule_metadata["category"] = {
                "rule_id": user_rule.rule_id,
                "source": "user_approved_rule",
            }
        if user_rule.set_purpose is not None:
            candidate_data["purpose"] = user_rule.set_purpose
            rule_metadata["purpose"] = {
                "rule_id": user_rule.rule_id,
                "source": "user_approved_rule",
            }

    return EnrichedTransactionCandidate(
        **candidate_data,
        account_id=account_id,
        merchant_canonical=merchant_canonical,
        category=category,
        rule_metadata=rule_metadata,
    )


def first_matching_user_rule(
    candidate: TransactionCandidate, user_rules: list[UserApprovedRule]
) -> UserApprovedRule | None:
    for rule in sorted(user_rules, key=lambda item: (item.priority, item.rule_id)):
        if user_rule_matches(candidate, rule):
            return rule
    return None


def user_rule_matches(candidate: TransactionCandidate, rule: UserApprovedRule) -> bool:
    has_condition = False
    if rule.match_merchant_raw is not None:
        has_condition = True
        if candidate.merchant_raw != rule.match_merchant_raw:
            return False
    if rule.match_account_clue is not None:
        has_condition = True
        if candidate.account_clue != rule.match_account_clue:
            return False
    return has_condition


def matched_user_rule_fields(
    candidate: TransactionCandidate, rule: UserApprovedRule
) -> list[str]:
    matched_fields = []
    if rule.match_merchant_raw is not None and candidate.merchant_raw == rule.match_merchant_raw:
        matched_fields.append("merchant_raw")
    if rule.match_account_clue is not None and candidate.account_clue == rule.match_account_clue:
        matched_fields.append("account_clue")
    return matched_fields


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

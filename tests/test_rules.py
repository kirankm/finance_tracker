import json
from pathlib import Path

from app.rules import UserApprovedRule, enrich_candidate
from app.sms_parser import TransactionCandidate, parse_sms

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sms" / "golden"


def test_known_account_clue_maps_to_account_with_metadata() -> None:
    candidate = parse_sms(
        "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_FOOD_1 on "
        "04-May-2026. Avl Bal Rs.50000. Ref 123456."
    )

    enriched = enrich_candidate(candidate)

    assert enriched.account_id == "acct_bank_1"
    assert enriched.confidence["account_mapping"] == "high"
    assert enriched.rule_metadata["account_mapping"] == {
        "rule_id": "account_bank_1_masked_0000_v1",
        "matched_value": "BANK_1 a/c XX0000",
    }


def test_unknown_account_clue_remains_unmapped_and_reviewable() -> None:
    candidate = parse_sms(
        "Rs.480 debited from BANK_9 a/c XX9999 to MERCHANT_FOOD_1 on "
        "04-May-2026. Avl Bal Rs.50000. Ref 123456."
    )

    enriched = enrich_candidate(candidate)

    assert enriched.account_id is None
    assert enriched.review_status == "needs_review"
    assert enriched.confidence["account_mapping"] == "low"
    assert enriched.rule_metadata["account_mapping"] == {
        "reason": "unknown_account_clue",
        "matched_value": "BANK_9 a/c XX9999",
    }


def test_known_merchant_maps_to_canonical_merchant_and_category() -> None:
    candidate = parse_sms(
        "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_FOOD_1 on "
        "04-May-2026. Avl Bal Rs.50000. Ref 123456."
    )

    enriched = enrich_candidate(candidate)

    assert enriched.merchant_canonical == "Merchant Food 1"
    assert enriched.category == "food_delivery"
    assert enriched.confidence["merchant_mapping"] == "high"
    assert enriched.confidence["category"] == "high"
    assert enriched.rule_metadata["merchant_mapping"] == {
        "rule_id": "merchant_food_1_v1",
        "matched_value": "MERCHANT_FOOD_1",
    }
    assert enriched.rule_metadata["category"] == {
        "rule_id": "merchant_food_1_v1",
        "source": "merchant_default_category",
    }


def test_user_approved_rule_overrides_existing_deterministic_rule() -> None:
    candidate = parse_sms(
        "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_FOOD_1 on "
        "04-May-2026. Avl Bal Rs.50000. Ref 123456."
    )

    enriched = enrich_candidate(
        candidate,
        user_rules=[
            UserApprovedRule(
                rule_id="rule_user_food_groceries",
                match_merchant_raw="MERCHANT_FOOD_1",
                set_merchant_canonical="User Food Rule",
                set_category="groceries",
                priority=10,
            )
        ],
    )

    assert enriched.merchant_canonical == "User Food Rule"
    assert enriched.category == "groceries"
    assert enriched.rule_metadata["user_approved_rule"] == {
        "rule_id": "rule_user_food_groceries",
        "matched_fields": ["merchant_raw"],
        "priority": 10,
    }


def test_unknown_merchant_remains_uncategorized_and_reviewable() -> None:
    candidate = parse_sms(
        "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_UNKNOWN_1 on "
        "04-May-2026. Avl Bal Rs.50000. Ref 123456."
    )

    enriched = enrich_candidate(candidate)

    assert enriched.merchant_canonical is None
    assert enriched.category is None
    assert enriched.review_status == "needs_review"
    assert enriched.confidence["merchant_mapping"] == "low"
    assert enriched.confidence["category"] == "low"
    assert enriched.rule_metadata["merchant_mapping"] == {
        "reason": "unknown_merchant_raw",
        "matched_value": "MERCHANT_UNKNOWN_1",
    }
    assert enriched.rule_metadata["category"] == {
        "reason": "no_category_rule",
        "matched_value": "MERCHANT_UNKNOWN_1",
    }


def test_enrichment_preserves_parser_type_and_purpose_without_override() -> None:
    candidate = parse_sms(
        "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_FOOD_1 on "
        "04-May-2026. Avl Bal Rs.50000. Ref 123456."
    )

    enriched = enrich_candidate(candidate)

    assert enriched.transaction_type == "debit"
    assert enriched.purpose == "expense"
    assert enriched.rule_metadata["transaction_type"] == {
        "reason": "preserved_parser_value",
        "value": "debit",
    }
    assert enriched.rule_metadata["purpose"] == {
        "reason": "preserved_parser_value",
        "value": "expense",
    }


def test_unrecognized_candidate_records_unknown_reasons_without_guessing() -> None:
    candidate = TransactionCandidate(
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

    enriched = enrich_candidate(candidate)

    assert enriched.account_id is None
    assert enriched.merchant_canonical is None
    assert enriched.category is None
    assert enriched.review_status == "needs_review"
    assert enriched.rule_metadata["account_mapping"] == {"reason": "missing_account_clue"}
    assert enriched.rule_metadata["merchant_mapping"] == {"reason": "missing_merchant_raw"}
    assert enriched.rule_metadata["category"] == {"reason": "missing_merchant_raw"}


def test_golden_sms_fixture_matches_expected_enrichment_output() -> None:
    sms_text = (FIXTURE_DIR / "debit-upi.sms.txt").read_text(encoding="utf-8")
    expected = json.loads(
        (FIXTURE_DIR / "debit-upi.enriched.expected.json").read_text(encoding="utf-8")
    )

    enriched = enrich_candidate(parse_sms(sms_text))

    assert enriched.model_dump(exclude_none=True) == expected

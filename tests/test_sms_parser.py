import json
from pathlib import Path

from app.sms_parser import parse_sms

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sms" / "golden"


def test_parser_extracts_fake_upi_debit_fixture() -> None:
    sms_text = (FIXTURE_DIR / "debit-upi.sms.txt").read_text(encoding="utf-8")

    candidate = parse_sms(sms_text)

    assert candidate.transaction_type == "debit"
    assert candidate.purpose == "expense"
    assert candidate.amount == 480
    assert candidate.account_clue == "BANK_1 a/c XX0000"
    assert candidate.merchant_raw == "MERCHANT_FOOD_1"
    assert candidate.transaction_date == "2026-05-04"
    assert candidate.available_balance == 50000
    assert candidate.reference == "123456"
    assert candidate.source == "sms"
    assert candidate.review_status == "needs_review"
    assert candidate.confidence == {"parsing": "high"}
    assert candidate.parser_metadata["parser"] == "fake_upi_debit_v1"
    assert candidate.parser_metadata["extracted_fields"] == [
        "amount",
        "account_clue",
        "merchant_raw",
        "date",
        "available_balance",
        "reference",
    ]


def test_parser_returns_reviewable_unknown_candidate_for_unrecognized_financial_sms() -> None:
    candidate = parse_sms("Alert: Your BANK_2 card ending 2222 had activity. Please review.")

    assert candidate.transaction_type == "unknown"
    assert candidate.purpose == "unknown"
    assert candidate.amount is None
    assert candidate.source == "sms"
    assert candidate.review_status == "needs_review"
    assert candidate.confidence == {"parsing": "low"}
    assert candidate.parser_metadata["parser"] == "unrecognized_financial_sms_v1"


def test_golden_sms_fixtures_match_expected_parser_output() -> None:
    sms_fixture_paths = sorted(FIXTURE_DIR.glob("*.sms.txt"))

    assert sms_fixture_paths

    for sms_fixture_path in sms_fixture_paths:
        expected_path = sms_fixture_path.with_name(
            sms_fixture_path.name.replace(".sms.txt", ".expected.json")
        )
        assert expected_path.exists(), f"missing expected output for {sms_fixture_path.name}"

        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        candidate = parse_sms(sms_fixture_path.read_text(encoding="utf-8"))

        assert candidate.model_dump(exclude_none=True) == expected

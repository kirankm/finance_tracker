# Sprint 4: Rules and Categorization

## Goal

Add deterministic rule-based enrichment for parsed transaction candidates so the app can map accounts, normalize merchants, and assign transaction type, purpose, and category with explainable metadata.

## Scope

- Add a small deterministic rules layer that consumes parsed `TransactionCandidate` data.
- Map known fake `account_clue` values to explicit fake account ids.
- Normalize known fake `merchant_raw` values to canonical merchants.
- Assign category defaults from deterministic merchant rules.
- Preserve parser-provided `transaction_type` and `purpose` unless a deterministic rule explicitly overrides them.
- Mark unknown or partially mapped candidates as reviewable rather than guessing.
- Store enough rule metadata to explain which account, merchant, category, purpose, and type decisions were made.
- Extend the fake golden dataset expectations for enrichment outputs.
- Seed or fixture only fake accounts, merchants, and rules needed for tests.

## Out of Scope

- LLM categorization or merchant suggestions.
- User-facing review queue UI.
- User correction flows.
- Creating rules from corrections.
- Duplicate detection.
- Ledger mismatch checks.
- Manual transaction entry.
- Real personal SMS examples, real merchant data, or real account identifiers.
- Multi-user rule ownership.
- Complex rule editors or natural-language rule creation.

## Expected Changes

- `app/sms_parser.py` if candidate shape needs a narrow compatibility adjustment.
- `app/rules.py` or equivalent deterministic enrichment module.
- `tests/test_rules.py`.
- `tests/test_sms_parser.py`.
- `tests/fixtures/sms/golden/`.
- `README.md` if run or data behavior changes.
- `docs/decisions/` if a persisted rule model or priority decision is introduced.
- `docs/risk-register.md` if rule correctness risks change.
- `project-status.md`.

## Tests to Write First

- Known fake `account_clue` maps to the expected account id with high confidence.
- Unknown `account_clue` leaves account unmapped and keeps the transaction in review.
- Known fake `merchant_raw` maps to the expected canonical merchant with high confidence.
- Known canonical merchant applies the expected default category.
- Unknown `merchant_raw` leaves merchant/category unmapped and keeps the transaction in review.
- Parser-provided `transaction_type` and `purpose` are preserved when no rule override exists.
- Enrichment metadata records matched rule ids or explicit unknown reasons.
- Golden fake SMS fixture regression covers parse plus enrichment output.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures.

Test command:

```bash
docker compose run --rm app python -m pytest
```

## Acceptance Criteria

- Parsed fake transaction candidates can be enriched through a deterministic rules layer.
- Known fake account clues map to explicit account ids.
- Known fake merchants normalize to canonical merchants.
- Known fake merchants assign default categories.
- Unknown account or merchant values do not get guessed.
- Low-confidence or unmapped decisions remain visible through `review_status` and metadata.
- Rule decisions are explainable through structured metadata.
- Rule priority follows the project principle: deterministic rules are authoritative over unknowns, and no LLM output is authoritative.
- Golden dataset tests cover the supported fake patterns.
- Relevant tests, lint, and typecheck pass through Docker.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Ingest a fake known merchant SMS locally and verify parsed candidate enrichment includes account, canonical merchant, category, and rule metadata.
- [x] Ingest a fake unknown merchant SMS locally and verify it remains reviewable without guessed category or merchant.
- [x] Verify golden fixtures remain fake/anonymized.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- Persisting rules now may be premature if Sprint 5 changes correction and review flows; prefer an interface that can start deterministic and migrate cleanly.
- Account mapping may need user configuration soon; Sprint 4 should avoid hard-coding real accounts.
- Category taxonomy may change as more fake fixtures are added; tests should lock behavior only for intentional fake examples.
- Purpose overrides for transfers, investments, refunds, and reversals may need additional fake SMS patterns before they can be trusted.
- The golden dataset may need a richer expected-output format to cover both parsing and enrichment without conflating the two layers.

## Completion Notes

Sprint plan created on 2026-05-05. Stop for review before implementation.

Implementation continued after approval on 2026-05-05.

- Recorded Decision 0009 to start with deterministic in-code fake rules and defer persisted rule tables until review/correction workflows clarify the schema.
- Added `app.rules` with a pure deterministic enrichment layer.
- Added fake account mapping from `BANK_1 a/c XX0000` to `acct_bank_1`.
- Added fake merchant normalization from `MERCHANT_FOOD_1` to `Merchant Food 1`.
- Added fake merchant default category assignment to `food_delivery`.
- Preserved parser-provided `transaction_type` and `purpose` when no override rule exists.
- Added rule metadata for matched rules and explicit unknown/missing reasons.
- Wired inbound SMS persistence to store enriched candidate output.
- Added golden enrichment fixture coverage with fake/anonymized data only.
- `docker compose run --rm app python -m pytest` passed with 34 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 16 source files.
- Local HTTP QA verified known fake merchant enrichment and unknown fake merchant reviewable fallback.

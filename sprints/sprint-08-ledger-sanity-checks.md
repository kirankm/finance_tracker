# Sprint 8: Ledger Sanity Checks

## Goal

Make balance-impact assumptions visible and explainable before SMS-derived ledger transactions are trusted for analysis.

## Scope

- Add deterministic ledger sanity checks during reviewed SMS candidate promotion when an available balance is present.
- Compare the candidate's available balance against the account balance implied by already-included ledger transactions for that account.
- Support debit and credit balance impact checks for the fake SMS patterns currently in scope.
- Store ledger sanity metadata in both `LedgerTransaction.source_metadata` and `RawSmsMessage.parser_output`.
- Distinguish transactions with missing balance context, matching balance context, and balance mismatch context.
- Keep mismatched transactions auditable and reviewable instead of silently correcting, deleting, or excluding them.
- Preserve duplicate behavior from Sprint 7: exact and possible duplicates remain ledger-excluded and should not create misleading balance assumptions.
- Add focused fixtures and tests for missing balance, matching balance, mismatch, credit, debit, and duplicate interactions.

## Out of Scope

- Full account reconciliation UI.
- Bank statement import or reconciliation.
- Automatic correction of mismatch causes.
- Opening balance management UI.
- Cash balance reconciliation.
- Transfer matching across accounts.
- Broad parser expansion for real bank SMS formats.
- Real SMS examples, real merchant names, real account identifiers, or secrets.

## Expected Changes

- `app/ledger_sanity.py` or equivalent deterministic ledger sanity service.
- `app/ledger_promotion.py` integration after duplicate detection and before promotion metadata is persisted.
- `app/models.py` only if the selected implementation requires new persisted columns; prefer existing metadata fields unless a schema change is justified.
- New Alembic migration only if model changes require it.
- `tests/test_ledger_sanity.py`.
- Existing tests in `tests/test_ledger_promotion.py`, `tests/test_duplicate_detection.py`, and parser/rules tests if response or metadata shape changes.
- Golden fake SMS fixtures under `tests/fixtures/sms/golden/` if parser or enrichment expectations change.
- `README.md` ledger sanity development contract update.
- `docs/risk-register.md` update for remaining balance limitations.
- A decision record if Sprint 8 chooses a lasting ledger status or metadata strategy.
- `project-status.md`.

## Tests to Write First

- A reviewed fake debit SMS with no available balance promotes with ledger sanity status `not_checked` and metadata explaining that balance context was missing.
- A reviewed fake debit SMS whose available balance matches the expected post-transaction balance promotes with ledger sanity status `matched`.
- A reviewed fake debit SMS whose available balance differs from the expected post-transaction balance promotes with ledger sanity status `mismatch`, stores expected balance, observed balance, mismatch amount, account id, basis, and confidence.
- A reviewed fake credit SMS applies the opposite balance impact from debit and records `matched` when expected and observed balances agree.
- A second unique fake SMS includes prior included, non-deleted ledger transaction impact in its expected balance.
- Duplicate promotions from Sprint 7 remain ledger-excluded and record ledger sanity metadata that avoids treating the duplicate as a fresh balance-impacting transaction.
- Ledger sanity metadata is stored in both ledger source metadata and raw SMS parser output.
- Promotion audit events include the ledger sanity status and ledger status.
- Mismatch behavior does not weaken existing unreviewed, unmapped, idempotency, duplicate, and false-positive duplicate tests.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_ledger_sanity.py tests/test_ledger_promotion.py tests/test_duplicate_detection.py
```

## Acceptance Criteria

- Ledger sanity checks are deterministic, explainable, and covered by tests.
- Missing available-balance context is represented explicitly rather than guessed.
- Debit and credit checks use included ledger transactions only and do not count soft-deleted or duplicate-excluded transactions.
- Mismatches remain visible and auditable; they are not silently corrected or deleted.
- Existing duplicate detection, review queue, inbound SMS, parser, rules, and ledger promotion behavior continues to pass.
- Relevant tests, lint, and typecheck pass through Docker.
- CI passes before merge.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Ingest, review, and promote a fake debit SMS with matching available balance and verify ledger sanity metadata is `matched`.
- [x] Ingest, review, and promote a fake debit SMS with mismatched available balance and verify mismatch metadata is visible in the promotion response, stored ledger metadata, and stored raw SMS parser output.
- [x] Ingest, review, and promote a fake credit SMS and verify credit balance direction is handled correctly.
- [x] Ingest, review, and promote a fake SMS without available balance and verify the check is explicitly `not_checked`.
- [x] Promote a duplicate fake SMS and verify duplicate-excluded transactions are not treated as included balance impact.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- Current account `current_balance` may not be a reliable opening balance for historical SMS sequences; Sprint 8 should document the basis it uses.
- Available balance in SMS may reflect pending holds, fees, reversed transactions, or transactions outside the app's ledger history.
- Same-day ordering can be ambiguous when SMS timestamps are missing or delayed.
- Transfer handling may need a later sprint because only single-account SMS-derived transactions are currently promoted.
- Mismatch status strings are plain strings unless Sprint 8 introduces formal enums.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued after the plan was reviewed.

- Added deterministic ledger sanity checks during SMS ledger promotion.
- Added `not_checked`, `matched`, and `mismatch` ledger sanity statuses.
- Missing available balance or missing account `current_balance` is recorded as `not_checked` instead of guessed.
- Debit and credit balance impacts are checked against `Account.current_balance` as the explicit known pre-promotion balance.
- Mismatched available balances are retained as promoted ledger transactions with `ledger_status: needs_review`.
- Duplicate-excluded promotions record `not_checked` ledger sanity metadata and do not apply a fresh balance impact.
- Ledger sanity metadata is stored in ledger source metadata and raw SMS parser output.
- Promotion responses and audit events now include `ledger_sanity_status`.
- Added tests first in `tests/test_ledger_sanity.py`; initial focused run failed because ledger sanity metadata and response fields did not exist.
- Focused Sprint 8 tests passed with `docker compose run --rm app python -m pytest tests/test_ledger_sanity.py tests/test_ledger_promotion.py tests/test_duplicate_detection.py`.
- Full `docker compose run --rm app python -m pytest` passed with 59 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 25 source files.
- Built the Docker app image after code and test edits.
- Recorded Decision 0013 for storing ledger sanity decisions in promotion metadata.
- Updated the risk register for available-balance limitations and partial mitigation of mismatch logic risk.
- CI has not run yet.

# Sprint 7: Duplicate Detection

## Goal

Prevent duplicate SMS-derived transactions from corrupting ledger totals while keeping duplicate decisions explainable and auditable.

## Scope

- Add deterministic duplicate detection during reviewed SMS candidate promotion.
- Compare the candidate being promoted against existing promoted `LedgerTransaction` records.
- Treat same-account, same-reference, same-amount, same-date, and same-transaction-type matches as exact duplicates.
- Treat same-account, same-amount, same-date, same-transaction-type, and same-merchant matches without a shared reference as possible duplicates.
- Store duplicate decision metadata in ledger source metadata and raw SMS parser output.
- Mark duplicate promotions with duplicate statuses that distinguish unique, exact duplicate, and possible duplicate.
- Exclude exact and possible duplicates from ledger totals by setting `ledger_status` to `excluded`.
- Keep duplicate transactions auditable rather than deleting or silently dropping them.
- Add tests first for unique promotion, exact duplicate promotion, possible duplicate promotion, same raw SMS idempotency, and false-positive boundaries.

## Out of Scope

- User-facing duplicate resolution UI.
- Confirming duplicates as unique or ignored through a new API.
- Advanced fuzzy matching across long transaction history.
- Cross-account duplicate inference.
- Bank statement import or reconciliation.
- Ledger sanity checks using available balance.
- Real SMS examples, real merchant names, real account identifiers, or secrets.

## Expected Changes

- `app/duplicate_detection.py` or equivalent deterministic duplicate service.
- `app/ledger_promotion.py` integration before `LedgerTransaction` creation.
- Promotion response fields if needed to expose duplicate and ledger status.
- `tests/test_duplicate_detection.py`.
- Existing ledger promotion tests if response or metadata shape changes.
- `README.md` duplicate detection contract update.
- `docs/risk-register.md` update for Sprint 6 cross-message duplicate risk.
- A decision record if Sprint 7 chooses a lasting duplicate status strategy.
- `project-status.md`.

## Tests to Write First

- A unique reviewed fake SMS candidate promotes with `duplicate_status: unique`, `ledger_status: included`, and duplicate metadata explaining no match.
- A second reviewed fake SMS with a different external message id but the same reference, amount, date, account, and transaction type is promoted as an exact duplicate and excluded from ledger totals.
- Exact duplicate metadata records the matched transaction id, raw SMS id, duplicate basis, and confidence.
- A second reviewed fake SMS with a different reference but the same amount, date, account, transaction type, and merchant is promoted as a possible duplicate and excluded.
- A same-amount/date/merchant SMS on a different account is not treated as a duplicate.
- A same raw SMS replay still returns the existing promotion idempotently and does not create a new duplicate audit event.
- Duplicate promotions create an audit event that includes duplicate status and ledger status.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_duplicate_detection.py tests/test_ledger_promotion.py
```

## Acceptance Criteria

- Duplicate detection runs before an SMS-derived candidate is added to ledger totals.
- Exact duplicates and possible duplicates are retained for traceability but excluded from ledger totals.
- Duplicate decisions are deterministic, explainable, and covered by tests.
- Existing same-raw-SMS promotion idempotency still works.
- Existing inbound SMS, review queue, parser, rules, and ledger promotion tests continue to pass.
- Relevant tests, lint, and typecheck pass through Docker.
- CI passes before merge.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Ingest, review, and promote a fake known merchant SMS locally.
- [x] Ingest, review, and promote a second fake SMS with the same reference and verify it is marked as an exact duplicate and ledger-excluded.
- [x] Ingest, review, and promote a second fake SMS with a different reference but same amount/date/merchant/account and verify it is marked as a possible duplicate and ledger-excluded.
- [x] Verify same raw SMS promotion replay remains idempotent.
- [x] Verify duplicate metadata links to the matched transaction and raw SMS.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- Possible duplicate detection can create false positives for two real purchases at the same merchant for the same amount on the same date.
- Sprint 7 excludes possible duplicates from ledger totals until a later resolution flow can confirm uniqueness.
- Duplicate status strings are currently stored as plain strings; formal enums can be added later if status drift becomes a risk.
- There is no user-facing duplicate resolution UI yet; Sprint 10 or a later backend sprint should provide a way to confirm or ignore possible duplicates.

## Completion Notes

Sprint plan created on 2026-05-05. Implementation continued after explicit user instruction to continue Sprint 7.

- Added deterministic duplicate detection during ledger promotion.
- Added exact duplicate detection for same account, reference, amount, transaction date, and transaction type.
- Added possible duplicate detection for same account, amount, transaction date, transaction type, and canonical merchant.
- Exact and possible duplicate promotions are persisted for traceability but marked `ledger_status: excluded`.
- Duplicate metadata is stored in ledger source metadata and raw SMS parser output.
- Promotion responses now include duplicate status and ledger status.
- Audit events include duplicate status and ledger status.
- Added tests first in `tests/test_duplicate_detection.py`; initial focused run failed because promotion did not yet expose or persist duplicate decisions.
- Focused Sprint 7 promotion tests passed with `docker compose run --rm app python -m pytest tests/test_duplicate_detection.py tests/test_ledger_promotion.py`.
- Full `docker compose run --rm app python -m pytest` passed with 53 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 23 source files.
- Recorded Decision 0012 for duplicate detection during promotion and conservative exclusion of possible duplicates.
- Updated the risk register to mark the Sprint 6 duplicate-promotion risk mitigated and track possible duplicate false positives.
- Local HTTP QA verified fake unique promotion (`duplicate_status: unique`, `ledger_status: included`), exact duplicate promotion (`exact_duplicate`, `excluded`), possible duplicate promotion (`possible_duplicate`, `excluded`), replay idempotency, persisted duplicate metadata, and one audit event per new promotion.

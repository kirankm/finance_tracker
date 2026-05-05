# Sprint 6: Ledger Promotion

## Goal

Promote reviewed, sufficiently mapped SMS transaction candidates into durable `LedgerTransaction` records with traceable source metadata, while preventing unmapped or unreviewed candidates from entering the ledger.

## Scope

- Add a backend service for promoting a stored `RawSmsMessage` candidate into a `LedgerTransaction`.
- Expose an authenticated API to promote one reviewed SMS candidate by raw SMS id.
- Require the candidate to be reviewed before promotion.
- Require the candidate to have minimum ledger fields: amount, transaction date, transaction type, purpose, account id, and source.
- Create or seed only fake test accounts needed by the sprint, such as `acct_bank_1`.
- Copy candidate fields into the ledger transaction:
  - amount
  - transaction date
  - transaction type
  - purpose
  - category
  - merchant raw
  - merchant canonical
  - account id
  - confidence values
  - source metadata linking back to the raw SMS id and explainability metadata
- Mark promoted candidates so repeat promotion is idempotent or returns a clear validation response without creating duplicates.
- Record an audit event for ledger promotion.
- Keep raw SMS records and parser output intact after promotion.
- Add tests first for successful promotion, validation failures, idempotency, auditability, and data safety.

## Out of Scope

- Duplicate detection across different SMS messages.
- Ledger mismatch checks against available balance.
- User correction forms.
- Manual transaction add/edit/delete UI.
- Cash account workflows.
- Category or account management UI.
- Backfilling existing local/manual QA raw SMS data.
- Real personal SMS examples, real merchant names, real account identifiers, or secrets.
- LLM suggestions or rule generation.

## Expected Changes

- `app/ledger_promotion.py` or equivalent promotion service.
- `app/main.py` for promotion route wiring.
- `app/models.py` if ledger/source relationships need a small persisted field.
- A new Alembic migration if a schema change is required for idempotent source linkage.
- `tests/test_ledger_promotion.py`.
- Existing review queue or inbound SMS tests if status semantics change.
- `README.md` if new API behavior should be documented.
- `docs/decisions/` if Sprint 6 chooses a durable raw SMS to ledger linkage strategy.
- `docs/risk-register.md` if promotion or duplicate risks remain unresolved.
- `project-status.md`.

## Tests to Write First

- A reviewed fake SMS candidate with known fake account mapping promotes to one `LedgerTransaction`.
- Promoted ledger transaction fields match the parsed/enriched candidate.
- Ledger transaction `source_metadata` links to the raw SMS id, external message id, parser metadata, rule metadata, and review metadata.
- Promotion creates an audit event with actor, event type, transaction id, and raw SMS source context.
- Promoting an unreviewed candidate fails without creating a ledger transaction.
- Promoting a candidate without account id fails without creating a ledger transaction.
- Promoting a candidate without amount or transaction date fails without creating a ledger transaction.
- Replaying promotion for the same raw SMS does not create a duplicate ledger transaction.
- Promoting a missing raw SMS id returns `404`.
- Review queue and inbound SMS behavior remain compatible after promotion metadata is stored.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures.

Test command:

```bash
docker compose run --rm app python -m pytest
```

## Acceptance Criteria

- A reviewed and fully mapped fake SMS candidate can be promoted into the ledger.
- Unreviewed or insufficiently mapped candidates cannot enter the ledger.
- Promotion is traceable from ledger transaction back to the raw SMS and candidate metadata.
- Promotion is idempotent or safely rejects repeat promotion without duplicate ledger entries.
- Promotion creates an audit trail.
- Existing inbound SMS, review queue, parser, rules, and ledger model tests continue to pass.
- Relevant migrations pass a disposable SQLite migration smoke test if schema changes are added.
- Relevant tests, lint, and typecheck pass through Docker.
- CI passes before merge.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] If a migration is added, run `DATABASE_URL=sqlite:////tmp/finance_tracker_migration_smoke.db python -m alembic upgrade head` inside Docker or host environment.
- [x] Ingest a fake known merchant SMS locally.
- [x] Mark the fake SMS candidate reviewed.
- [x] Promote the reviewed fake candidate and verify a ledger transaction is created.
- [x] Replay promotion and verify no duplicate ledger transaction is created.
- [x] Verify the ledger transaction source metadata links back to the raw SMS id and rule/review metadata.
- [x] Verify an unreviewed or unknown-account fake candidate cannot be promoted.
- [x] Verify raw SMS and parser metadata remain stored after promotion.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- Sprint 6 adds `LedgerTransaction.raw_sms_message_id` with a unique constraint for durable same-raw-SMS idempotency.
- Duplicate detection across different SMS messages is still out of scope; Sprint 6 only prevents duplicate promotion of the same raw SMS.
- Account creation/configuration is not built yet; Sprint 6 creates only the deterministic fake `acct_bank_1` account when needed.
- Promoting a transaction before ledger sanity checks exist may be acceptable only if metadata clearly marks duplicate and ledger status defaults.
- Review metadata currently lives on `RawSmsMessage.parser_output`; promotion should preserve it but may need later normalization.

## Completion Notes

Sprint plan created on 2026-05-05. Stop for review before implementation.

Implementation continued after approval on 2026-05-05.

- Added `app/ledger_promotion.py` for reviewed SMS candidate promotion.
- Added `POST /api/review-queue/{raw_sms_id}/promote`, protected by the existing shared secret middleware.
- Added nullable, unique `LedgerTransaction.raw_sms_message_id` with a migration for durable raw SMS linkage.
- Stored promotion metadata on the raw SMS parser output while preserving raw SMS body and parser metadata.
- Created one fake account seed path for `acct_bank_1` because account management is still out of scope.
- Added audit events with transaction id, raw SMS id, external message id, source, actor, event type, and reason.
- Added tests first in `tests/test_ledger_promotion.py`; initial focused run failed with missing routes as expected.
- Focused Sprint 6 tests passed with `docker compose run --rm app python -m pytest tests/test_ledger_promotion.py`.
- Full `docker compose run --rm app python -m pytest` passed with 48 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 20 source files.
- Disposable SQLite migration smoke test passed for the new raw SMS ledger link migration.
- Recorded Decision 0011 for durable raw SMS linkage and temporary fake account creation.
- Added a risk-register entry for cross-message duplicates remaining unresolved until Sprint 7.
- Local HTTP QA verified fake ingest, review, promote, replay idempotency, source metadata, audit event creation, unreviewed rejection, unknown-account rejection, and shared-secret rejection.
- GitHub Actions passed on PR #5, and the PR was squash-merged to `main`.

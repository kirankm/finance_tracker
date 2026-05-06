# Sprint 13: Manual Transaction Management

## Goal

Make manual ledger transactions first-class, auditable, and recoverable.

## Scope

- Add authenticated APIs to create manual transactions.
- Add authenticated APIs to edit manual transactions.
- Add status flows to ignore, mark duplicate, soft-delete, and restore manual transactions.
- Validate referenced accounts and active categories.
- Keep manual transactions clearly marked with `source: manual`.
- Preserve create, edit, status-change, delete, and restore history in audit events.

## Out of Scope

- Split transactions.
- Recurring transactions.
- Budget workflows.
- Manual transaction UI polish beyond backend workflow support.
- Editing SMS-derived transactions through the manual transaction endpoints.

## Expected Changes

- `app/manual_transactions.py` service module.
- `app/main.py` authenticated manual transaction routes.
- `tests/test_manual_transactions.py`.
- README manual transaction API documentation.
- `project-status.md`.

## Tests to Write First

- Manual transaction endpoints require the shared secret.
- Creating a manual transaction persists ledger fields with `source: manual`.
- Creating a manual transaction validates known account and active category values.
- Editing a manual transaction creates before/after audit history.
- Manual status actions set ledger/duplicate status without deleting data.
- Soft delete preserves the transaction with deleted metadata.
- Restore clears soft delete metadata.
- Manual endpoints reject SMS-derived ledger transactions.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_manual_transactions.py
```

## Acceptance Criteria

- User can add, edit, ignore, mark duplicate, delete, and restore a manual transaction.
- Manual transaction changes are auditable.
- Deleted manual transactions are soft-deleted and recoverable.
- Manual APIs do not mutate SMS-derived transactions.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_manual_transactions.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Create a fake manual transaction through the API.
- [x] Edit a fake manual transaction and verify audit history.
- [x] Ignore, mark duplicate, soft-delete, and restore a fake manual transaction.

## Risks / Open Questions

- Manual transfer balancing remains out of scope; this sprint records transfer-like rows but does not create paired account movements.
- Categories remain string references until a later category foreign-key migration is justified.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated manual transaction create/update/status/delete/restore APIs.
- Manual transactions are persisted as ledger rows with `source: manual`.
- Manual endpoints validate known accounts, active categories, positive amounts, and reject SMS-derived transactions.
- Manual create, update, ignore, duplicate, delete, and restore actions create audit events.
- Soft deletes preserve transaction rows and restore clears delete metadata while preserving pre-delete ledger/duplicate status.
- Added focused coverage in `tests/test_manual_transactions.py`.

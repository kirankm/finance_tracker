# Sprint 14: Cash Tracking

## Goal

Make cash accounts maintainable through explicit balance updates and auditable cash adjustment transactions.

## Scope

- Add authenticated API to update a cash account's reported balance.
- Compare expected cash balance with the user-reported balance.
- Optionally record the difference as an uncategorized cash adjustment transaction.
- Audit cash balance updates and generated adjustment transactions.
- Keep cash adjustment transactions marked as `source: manual`.

## Out of Scope

- Cash envelope budgeting.
- Automatic cash inference from SMS.
- Split transactions.
- Search and analysis screens.
- Bank statement reconciliation.

## Expected Changes

- `app/cash_tracking.py` service module.
- `app/main.py` authenticated cash account route.
- `tests/test_cash_tracking.py`.
- README cash tracking API documentation.
- `project-status.md`.

## Tests to Write First

- Cash balance update endpoint requires the shared secret.
- Updating a cash account stores `current_balance` and `last_manual_update`.
- Updating a non-cash account is rejected.
- Updating a missing account returns `404`.
- When requested, a cash shortfall creates a `cash_adjustment` ledger transaction.
- Cash adjustment creation is audited and linked to the account update.
- Zero-difference updates do not create adjustment transactions.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_cash_tracking.py
```

## Acceptance Criteria

- User can update a cash account balance explicitly.
- Balance differences are visible in the response.
- User can record a difference as an auditable cash adjustment transaction.
- Cash balance updates are audit logged.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_cash_tracking.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Update a fake cash account balance through the API.
- [x] Record a fake cash shortfall as an adjustment transaction.
- [x] Verify zero-difference updates do not create adjustment transactions.

## Risks / Open Questions

- Cash difference categorization is intentionally conservative and defaults to `cash_spend`; richer explanation categories belong in later analysis/search work.
- Cash updates rely on the app's stored cash balance, so missing historical cash entries can still produce misleading differences.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated cash balance update API for cash accounts.
- Cash updates store `current_balance` and `last_manual_update`.
- Cash updates reject missing accounts, non-cash accounts, and negative reported balances.
- Non-zero differences can create manual `cash_adjustment` ledger transactions.
- Cash balance updates and generated adjustment transactions create audit events.
- Added focused coverage in `tests/test_cash_tracking.py`.

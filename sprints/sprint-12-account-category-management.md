# Sprint 12: Account and Category Management

## Goal

Make accounts and categories editable enough to support real ledger use without relying only on hard-coded fake assumptions.

## Scope

- Add backend APIs to list, create, and update accounts.
- Add backend APIs to list, create, update, and soft-delete categories.
- Add a category model with optional `intent_type`.
- Prevent deleting categories that active ledger transactions depend on.
- Preserve account/category changes in audit events where applicable.
- Add focused tests for validation and dependency safety.

## Out of Scope

- Budgeting.
- Advanced net worth views.
- Investment holdings tracking.
- Rich account/category UI.
- Migrating existing ledger category strings to foreign keys.
- Real account identifiers, real merchant names, real SMS, or secrets.

## Expected Changes

- `app/models.py` category model.
- Alembic migration for categories.
- `app/management.py` account/category API services.
- `app/main.py` routes.
- `tests/test_account_category_management.py`.
- README management API documentation.
- `project-status.md`.

## Tests to Write First

- Account list/create/update endpoints require shared secret.
- Creating an account persists account type and balance tracking fields.
- Updating an account creates an audit event with before/after values.
- Category list/create/update endpoints require shared secret.
- Creating a category persists `intent_type`.
- Updating a category changes display fields.
- Soft-deleting an unused category marks it deleted.
- Soft-deleting a category used by an active ledger transaction returns `409`.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_account_category_management.py
```

## Acceptance Criteria

- Accounts and categories can be managed through authenticated APIs.
- Category deletes are soft deletes.
- Categories used by active ledger transactions cannot be deleted.
- Account edits are audit logged.
- Relevant tests, lint, and typecheck pass through Docker.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Create and update a fake account through the API.
- [x] Create, update, and soft-delete an unused fake category through the API.
- [x] Verify deleting a category used by an active transaction is rejected.

## Risks / Open Questions

- Ledger transactions still store category as a string; a later migration may promote category references to foreign keys.
- Account deletion remains out of scope until manual transaction and reconciliation flows settle.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added `Category` model and Alembic migration.
- Added authenticated account list/create/update APIs.
- Added authenticated category list/create/update/delete APIs.
- Account updates create audit events with before/after values.
- Category deletes are soft deletes and are blocked when active ledger transactions reference the category id.
- Added focused tests in `tests/test_account_category_management.py`.
- Focused Sprint 12 tests passed with `docker compose run --rm app python -m pytest tests/test_account_category_management.py`.

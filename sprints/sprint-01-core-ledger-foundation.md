# Sprint 1: Core Ledger Foundation

## Goal

Create the durable core data model for accounts, transactions, and audit history before SMS ingestion is implemented.

## Scope

- Add SQLAlchemy database session and model foundation.
- Add Alembic migration for initial ledger tables.
- Add account model.
- Add transaction model.
- Add audit event model.
- Support soft-delete fields on ledger records that must not disappear silently.
- Add deterministic seed/default category approach only if needed by tests.
- Keep all test data fake.

## Out of Scope

- Real SMS ingestion endpoint.
- SMS parsing.
- External SMS forwarding service selection.
- Review UI.
- Analysis or insights.
- LLM categorization.
- Bank integrations.

## Expected Changes

- `app/database.py`
- `app/models.py` or `app/models/`
- `app/repositories/` if a small persistence boundary is useful
- Alembic migration under `migrations/versions/`
- Focused unit/integration tests for model persistence and constraints
- README updates for migration commands
- Risk or decision records if model tradeoffs are significant

## Tests to Write First

- Account persistence test with required fields and account type.
- Transaction persistence test with amount, type, purpose, account, source, review status, duplicate status, and ledger status.
- Audit event persistence test proving an event can be linked to a transaction or account change.
- Soft-delete test proving deleted records remain queryable and carry deletion metadata.
- Migration smoke test if practical in the current test setup.

## Acceptance Criteria

- Initial ledger schema is created through Alembic.
- Models support the V1 transaction/account fields needed by `PROJECT.md`.
- Soft-delete fields exist where ledger safety requires them.
- Audit events can represent automated and manual changes.
- Tests use fake data only.
- Docker test, lint, and typecheck commands pass.
- Existing Linode Docker run path remains valid.

## QA Checklist

- [ ] Run `docker compose run --rm app python -m pytest`.
- [ ] Run `docker compose run --rm app python -m ruff check .`.
- [ ] Run `docker compose run --rm app python -m mypy`.
- [ ] Run migration upgrade against a disposable SQLite database.
- [ ] Verify no real SMS or financial data is committed.
- [ ] Verify production Compose config still hides app port `8000`.

## Risks / Open Questions

- SQLite constraints and enum handling should stay simple enough to migrate later if PostgreSQL becomes necessary.
- Audit model should be useful without overbuilding a full event-sourcing system.
- The exact inbound SMS payload contract is still unknown, so transaction source metadata should stay flexible.

## Completion Notes

Sprint plan created on 2026-05-05. Stop for review before implementation.

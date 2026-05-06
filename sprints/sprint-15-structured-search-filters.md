# Sprint 15: Structured Search and Filters

## Goal

Make ledger transactions inspectable through structured filters before building analysis and insights.

## Scope

- Add an authenticated ledger transaction search API.
- Support filters for date range, account, transaction type, purpose, category, merchant, amount range, review status, duplicate status, ledger status, source, and deleted state.
- Add bounded, stable sorting and pagination.
- Add minimal UI controls for structured ledger filters and a transaction result list.
- Keep broad search responses privacy-conscious by omitting raw SMS bodies.

## Out of Scope

- Natural-language search.
- LLM chat over expenses.
- Analysis dashboards.
- Duplicate resolution workflows.
- Raw SMS detail expansion from search results.

## Expected Changes

- `app/ledger_search.py`.
- `app/main.py` ledger search route.
- `app/templates/index.html` search/filter UI.
- `tests/test_ledger_search.py`.
- `tests/test_review_ui.py` UI wiring coverage.
- README, project status, backlog/risk updates as needed.

## Tests to Write First

- Ledger search requires the shared secret.
- Default search excludes soft-deleted transactions.
- Explicit filters can find ignored, duplicate, ledger-excluded, and deleted transactions.
- Search filters by date range, account, transaction type, purpose, category, source, amount range, merchant, review status, duplicate status, and ledger status.
- Sorting and limit/offset pagination are stable.
- Search responses include source/audit context but not raw SMS body text.
- UI exposes ledger filter controls and calls the ledger search API.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_ledger_search.py tests/test_review_ui.py
```

## Acceptance Criteria

- User can find and inspect any V1 ledger transaction state with structured filters.
- Deleted transactions are hidden by default and visible when explicitly requested.
- Search results are bounded and stable.
- Search results preserve transaction, source, and audit context without exposing raw SMS bodies broadly.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_ledger_search.py tests/test_review_ui.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Search fake ledger rows by date/account/type/purpose/category/source.
- [x] Search fake ledger rows by statuses and include deleted rows explicitly.
- [x] Verify broad search responses do not include raw SMS body text.

## Risks / Open Questions

- Search uses exact structured filters plus merchant substring matching; richer natural-language search remains out of V1 scope.
- Search returns selected source metadata only, so deeper raw SMS inspection remains intentionally limited to the explicit review detail path.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated `GET /api/ledger-transactions` structured search.
- Added filters for IDs, date range, account, transaction type, purpose, category, merchant, amount range, review status, duplicate status, ledger status, source, and deleted state.
- Added stable bounded sorting and pagination.
- Search results include selected source context and audit event counts but omit raw SMS bodies.
- Added a minimal ledger search panel to the existing local UI.
- Review pass fixed merchant wildcard handling and removed unsafe `innerHTML` rendering for SMS-derived review list/detail values.

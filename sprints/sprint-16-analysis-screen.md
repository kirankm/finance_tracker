# Sprint 16: Analysis Screen

## Goal

Provide deterministic summaries of where money went without relying on LLM interpretation.

## Scope

- Add an authenticated analysis summary API.
- Add monthly spend by category.
- Add spend by account.
- Add income vs expense totals.
- Separate investments, savings, transfers, refunds, reversals, and cash balance changes from normal expenses.
- Include unmapped and review-needed counts.
- Add a minimal analysis panel to the local UI.

## Out of Scope

- LLM-written insights.
- Budget comparisons.
- Forecasting.
- Net worth dashboards.
- Investment holdings tracking.

## Expected Changes

- `app/analysis.py`.
- `app/main.py` analysis route and auth coverage.
- `app/templates/index.html` analysis panel.
- `tests/test_analysis.py`.
- `tests/test_review_ui.py` UI wiring coverage.
- README, project status, risk/backlog updates as needed.

## Tests to Write First

- Analysis endpoints require the shared secret.
- Monthly analysis includes only reviewed, unique, included, non-deleted ledger transactions in financial totals.
- Expense totals and category/account spend exclude investments, savings, transfers, refunds, reversals, cash updates, duplicates, ignored rows, deleted rows, and ledger-excluded rows.
- Income is reported separately from expense totals.
- Cash balance changes are reported separately.
- Unmapped and review-needed counts are visible.
- UI exposes analysis controls and calls the analysis API.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_analysis.py tests/test_review_ui.py
```

## Acceptance Criteria

- User can request deterministic monthly analysis.
- Analysis totals are explainable and do not silently include duplicate, ignored, deleted, or ledger-excluded transactions.
- Special-purpose flows are visibly separate from normal expenses.
- The UI has a minimal authenticated analysis screen.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_analysis.py tests/test_review_ui.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Verify fake monthly category/account/income/expense totals.
- [x] Verify excluded/duplicate/ignored/deleted rows do not affect totals.
- [x] Verify cash updates and review-needed counts are visible.

## Risks / Open Questions

- Analysis uses deterministic purpose/status rules only; richer insight generation is deferred to Sprint 17.
- Analysis treats positive ledger amounts as absolute transaction amounts and separates purpose buckets instead of attempting signed netting.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated `GET /api/analysis/summary`.
- Added month and explicit date-range period handling.
- Analysis totals include only reviewed, unique, included, non-deleted ledger transactions.
- Normal expenses are grouped by category and account.
- Income, investments, savings, transfers, refunds, reversals, and cash updates are kept separate from normal expenses.
- Added quality counts for review-needed, unmapped, and excluded rows.
- Added a minimal analysis panel to the local UI.
- Review pass added an `other_included` bucket to avoid silently dropping eligible but unrecognized purposes.

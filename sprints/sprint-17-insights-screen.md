# Sprint 17: Insights Screen

## Goal

Surface important deterministic observations without relying on LLM authority.

## Scope

- Add authenticated deterministic insight generation.
- Highlight unmapped transactions, possible duplicates, ledger mismatches, cash mismatches, and notable category changes.
- Link each insight to underlying ledger transactions.
- Allow insights to be dismissed or marked reviewed through audited actions.
- Add a minimal insights panel to the local UI.

## Out of Scope

- LLM chat.
- LLM-written insight copy.
- Advanced anomaly detection.
- Budget recommendations.
- Forecasting.

## Expected Changes

- `app/insights.py`.
- `app/main.py` insight routes and auth coverage.
- `app/templates/index.html` insights panel.
- `tests/test_insights.py`.
- `tests/test_review_ui.py` UI wiring coverage.
- README, project status, risk/backlog updates as needed.

## Tests to Write First

- Insight endpoints require the shared secret.
- Insights are generated for unmapped transactions, possible duplicates, ledger mismatches, cash mismatches, and notable category changes.
- Insights link to underlying transaction IDs and do not expose raw SMS bodies.
- Dismiss and review actions create audit events.
- Dismissed and reviewed insights are hidden by default and can be explicitly included.
- UI exposes insights controls and calls the insights API.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_insights.py tests/test_review_ui.py
```

## Acceptance Criteria

- User can load deterministic insights for a period.
- Each insight has traceable transaction IDs and structured metadata.
- Dismiss/review actions are auditable.
- LLMs do not determine insight truth.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_insights.py tests/test_review_ui.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Verify fake unmapped, duplicate, ledger mismatch, cash mismatch, and category-change insights.
- [x] Verify insight dismiss/review audit events.
- [x] Verify insights do not expose raw SMS bodies.

## Risks / Open Questions

- Insight state is stored as audit events keyed by deterministic insight IDs; a first-class insight state table can be added later if querying needs outgrow audit scanning.
- Category-change thresholds are deterministic and conservative; more nuanced anomaly detection remains out of scope.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated `GET /api/insights`.
- Added deterministic insight generation for unmapped transactions, possible duplicates, ledger mismatches, cash mismatches, and notable category changes.
- Insight responses link to ledger transaction IDs and omit raw SMS bodies.
- Added audited dismiss and review actions backed by deterministic insight IDs.
- Added a minimal insights panel to the local UI.
- Review pass fixed import/typing issues and kept insight state explicitly tracked in the risk register.

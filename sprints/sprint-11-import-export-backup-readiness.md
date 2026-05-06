# Sprint 11: Import, Export, Backup, and Real-Use Readiness

## Goal

Reduce data-loss and privacy risk before relying on real personal SMS data.

## Scope

- Add explicit authenticated export endpoints for fake/local data review.
- Export ledger transactions to CSV.
- Export accounts, ledger transactions, raw SMS metadata, and audit history to JSON.
- Exclude raw SMS bodies from JSON export by default.
- Document raw SMS body export as intentionally deferred.
- Add a first-real-use readiness checklist.
- Add tests for export privacy, auth, and basic format stability.

## Out of Scope

- Bank statement import.
- Third-party cloud sync.
- Automated off-server backup upload.
- Raw SMS body bulk export.
- Native Android SMS reader.
- Real SMS examples, real merchant names, real account identifiers, or secrets.

## Expected Changes

- `app/export.py`.
- `app/main.py` export routes.
- `tests/test_export.py`.
- `docs/deployment/first-real-use-checklist.md`.
- README export documentation.
- `project-status.md`.

## Tests to Write First

- JSON export requires the existing shared secret.
- JSON export includes accounts, ledger transactions, audit events, and raw SMS metadata.
- JSON export does not include raw SMS body.
- CSV export requires the existing shared secret.
- CSV export includes ledger transaction headers and rows.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_export.py tests/test_sqlite_backup.py
```

## Acceptance Criteria

- Exports are explicit authenticated actions.
- JSON export avoids raw SMS body leakage by default.
- CSV ledger export is deterministic enough for local inspection.
- Backup/restore docs remain valid.
- Relevant tests, lint, and typecheck pass through Docker.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Export JSON with fake data and verify raw SMS body is absent.
- [x] Export ledger CSV with fake data and verify expected headers.
- [x] Review first-real-use checklist for backup, auth, HTTPS, and forwarder validation gates.

## Risks / Open Questions

- Raw SMS body export may be needed later, but it should be a separate explicit privacy decision.
- Off-server backup storage is still not selected.
- Import/restore validation remains deferred beyond SQLite backup restore smoke tests.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated JSON export at `GET /api/export/json`.
- Added authenticated ledger CSV export at `GET /api/export/ledger-transactions.csv`.
- JSON export includes raw SMS metadata but intentionally omits raw SMS body.
- Added first-real-use checklist under `docs/deployment/`.
- Added focused export tests in `tests/test_export.py`.
- Focused Sprint 11 tests passed with `docker compose run --rm app python -m pytest tests/test_export.py tests/test_sqlite_backup.py`.

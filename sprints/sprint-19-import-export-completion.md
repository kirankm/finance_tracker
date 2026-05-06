# Sprint 19: Import and Export Completion

## Goal

Finish V1 data portability with explicit, privacy-conscious export and import validation.

## Scope

- Update JSON export format to include user-approved rules.
- Keep raw SMS body export off by default and require an explicit flag to include bodies.
- Validate exported JSON before restore/import.
- Document supported export format versions.
- Preserve spreadsheet-safe CSV export.

## Out of Scope

- Bank statement import.
- Third-party sync.
- Automatic cloud backup.
- Writing imported data into the live database.

## Expected Changes

- `app/export.py` format v2 export and import validation.
- `app/main.py` export flag and import validation route.
- `tests/test_export.py`.
- `tests/test_import_validation.py`.
- README and project status updates.

## Tests to Write First

- JSON export requires the shared secret.
- JSON export includes user rules in format v2.
- Raw SMS bodies are omitted by default.
- Raw SMS bodies are included only when explicitly requested.
- Ledger CSV remains spreadsheet-safe.
- Import validation accepts exported JSON and reports counts.
- Import validation rejects unsupported versions and malformed required sections.
- Import validation does not write data.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_export.py tests/test_import_validation.py
```

## Acceptance Criteria

- User can export CSV ledger data.
- User can export a complete JSON backup with accounts, ledger, categories, audit events, raw SMS metadata, and user rules.
- Raw SMS body export is explicit.
- User can validate exported JSON before restore/import.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_export.py tests/test_import_validation.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Export fake JSON without raw SMS body.
- [x] Export fake JSON with explicit raw SMS body inclusion.
- [x] Validate fake exported JSON.

## Risks / Open Questions

- Sprint 19 validates import shape but does not restore into the live database; the production restore smoke path remains the documented SQLite backup/restore workflow.
- Raw SMS body export is intentionally explicit because it is privacy-sensitive.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Bumped JSON export to `format_version: 2`.
- Added user-approved rules to JSON export.
- Added explicit `include_raw_sms_body=true` handling for privacy-sensitive raw SMS body export.
- Added authenticated `POST /api/import/json/validate`.
- Import validation supports format versions 1 and 2 and reports section counts without mutating the database.
- Preserved spreadsheet-safe CSV export behavior.

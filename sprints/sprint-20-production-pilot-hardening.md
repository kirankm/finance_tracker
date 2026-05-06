# Sprint 20: Production Pilot Hardening

## Goal

Make the app safe enough to decide whether a small real-SMS pilot can start.

## Scope

- Add authenticated operational readiness checks.
- Confirm production forwarding auth strategy.
- Review raw SMS exposure across broad APIs/UI.
- Document fake-device forwarder validation steps.
- Document backup/restore pilot smoke path and off-server backup choice.
- Create production pilot go/no-go and rollback notes.
- Update blocker/risk status explicitly.

## Out of Scope

- Scaling beyond personal use.
- Multi-user authentication.
- Native Android SMS reader.
- Automated cloud backup.
- Real-device validation inside automated tests.

## Expected Changes

- `app/operational_readiness.py`.
- `app/main.py` readiness route and auth coverage.
- `tests/test_operational_readiness.py`.
- Deployment hardening docs.
- Project status/risk updates.

## Tests to Write First

- Readiness endpoint requires the shared secret.
- Readiness response does not expose secret values.
- Readiness response includes checks for secret configuration, database URL, raw SMS export default behavior, backup docs, and first-use checklist.
- Readiness response includes checks for Android forwarder validation and production pilot go/no-go docs.
- Readiness marks development default secret as a blocker.
- Raw SMS broad exposure remains covered by export/review/search tests.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_operational_readiness.py tests/test_export.py tests/test_review_ui.py tests/test_ledger_search.py
```

## Acceptance Criteria

- Production pilot has an explicit go/no-go document.
- Known unresolved risks are explicit in the risk register and status file.
- Readiness checks are authenticated and avoid leaking secrets.
- Backup/restore and raw SMS privacy gates are documented.
- Relevant tests, lint, typecheck, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_operational_readiness.py tests/test_export.py tests/test_review_ui.py tests/test_ledger_search.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Run `docker compose run --rm app python -m alembic upgrade head`.
- [x] Build the Docker app image after code/test edits.
- [x] Run `docker compose run --rm app python -m pytest tests/test_sqlite_backup.py`.
- [x] Review raw SMS broad exposure defaults.
- [x] Review production go/no-go and rollback document.
- [x] Confirm unresolved real-device validation is still marked as a no-go gate.

## Risks / Open Questions

- Android fake-device validation and header support require physical device testing and remain a real-use gate.
- Production remains single-user shared-secret authenticated; multi-user authentication is out of V1 scope.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added authenticated `GET /api/ops/readiness`.
- Readiness checks report blocker status without exposing secret values and use repository-root doc paths.
- Added Android forwarder fake-device validation documentation.
- Added production pilot go/no-go and rollback documentation.
- Recorded Decision 0016 to keep production SMS forwarding auth header-only for the pilot.
- Kept real SMS pilot as no-go until physical device/header validation and first off-server backup are complete.
- Updated first-use checklist, backup docs, risk register, and project status.
- Local Sprint 20 review fixed cwd-dependent readiness doc checks before final verification.

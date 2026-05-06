# Sprint 21: V1 Stabilization and Release Candidate

## Goal

Stabilize the full V1 fake-data workflow and decide whether V2 planning can
start without hiding remaining real-use gates.

## Scope

- Add an end-to-end fake-data release-candidate regression.
- Run the full local Docker verification set.
- Fix high-priority correctness, privacy, auditability, or migration issues found.
- Document V1 release candidate status and residual limitations.
- Update project status, risks, and backlog where relevant.

## Out of Scope

- Starting V2 implementation.
- Adding V2 features.
- Real personal SMS ingestion.
- Physical Android device validation.
- Automated cloud backup.

## Expected Changes

- `tests/test_v1_release_candidate_workflow.py`.
- V1 release candidate documentation.
- Sprint/status/risk/backlog updates as needed.

## Tests to Write First

- Full fake workflow can ingest an Android-forwarder payload, correct it, review
  it, promote it, and preserve auditability.
- A duplicate SMS promotion is ledger-excluded and excluded from analysis totals.
- A user-approved rule created from a correction applies to a future inbound SMS.
- Broad search/export/insight responses do not leak raw SMS bodies.
- Export JSON validates through the import validator.
- SQLite backup and restore preserve the fake workflow database.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_v1_release_candidate_workflow.py
```

## Acceptance Criteria

- V1 release candidate workflow is covered by an end-to-end fake-data regression.
- CI and local Docker checks pass.
- V1 release candidate notes explicitly list residual limitations.
- Real SMS remains blocked until physical Android header validation and first
  encrypted off-server backup are complete.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_v1_release_candidate_workflow.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Run `docker compose run --rm app python -m alembic upgrade head`.
- [x] Build the Docker app image after code/test edits.
- [x] Review V1 release candidate notes.
- [x] Confirm unresolved real-device and off-server backup gates remain explicit.

## Risks / Open Questions

- Physical Android fake-device validation remains outside automated tests.
- Real-use trust may still require another V1 hardening sprint after pilot feedback.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued immediately at user request.

- Added an end-to-end fake-data release-candidate regression.
- Regression covered Android-style ingest, correction, review, promotion,
  duplicate exclusion, approved rules, search, analysis, insights, export/import
  validation, and backup/restore.
- Added V1 release-candidate notes with residual limitations and real-SMS gates.
- Updated status, risk register, backlog, and README.
- Local review found and fixed import-order hygiene in the new regression test.

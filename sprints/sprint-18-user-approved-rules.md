# Sprint 18: User-Approved Rules

## Goal

Turn repeated corrections into explicit, user-approved rules that can affect future fake SMS candidates while staying auditable and reversible.

## Scope

- Add persistent user-approved rules.
- List rule candidates derived from user corrections.
- Approve or reject rule candidates.
- Edit and disable user-approved rules.
- Apply rule priority for future candidates: user-approved rule before deterministic rule.
- Audit rule approval, rejection, editing, and disabling.
- Add minimal UI wiring for rule candidate and rule management.

## Out of Scope

- Natural-language rule creation.
- Fully automated LLM rule application.
- Advanced rule conditions beyond exact fake merchant/account clues.
- Bulk rule simulation.

## Expected Changes

- `app/models.py` user rule model.
- Alembic migration for `user_rules`.
- `app/user_rules.py` service module.
- `app/rules.py` user-approved rule priority support.
- `app/main.py` rule routes and inbound enrichment integration.
- `tests/test_user_rules.py`.
- `tests/test_rules.py` priority coverage.
- README, project status, risk/backlog/decision updates as needed.

## Tests to Write First

- Rule endpoints require the shared secret.
- Corrections produce listable rule candidates.
- Rule candidates can be approved into persistent enabled user rules with audit events.
- Rule candidates can be rejected with audit events.
- Editing and disabling user-approved rules create audit events.
- Enabled user-approved rules override deterministic rules for future SMS candidates.
- Disabled rules no longer apply.
- UI exposes rule management API wiring.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_user_rules.py tests/test_rules.py tests/test_review_ui.py
```

## Acceptance Criteria

- User can approve a rule from a correction and see it affect a future fake SMS candidate.
- User can reject a candidate without creating a rule.
- User can edit and disable a rule.
- Rule actions are auditable.
- User-approved rules do not silently override user corrections on already-corrected candidates.
- Relevant tests, lint, typecheck, migration, Docker build, and CI pass.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest tests/test_user_rules.py tests/test_rules.py tests/test_review_ui.py`.
- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Run `docker compose run --rm app python -m alembic upgrade head`.
- [x] Build the Docker app image after code/test edits.
- [x] Approve a fake correction-derived rule and verify it affects future fake SMS.
- [x] Edit and disable a fake rule and verify audit events.
- [x] Reject a fake rule candidate and verify no rule is created.

## Risks / Open Questions

- Rule conditions are intentionally narrow exact-match rules in Sprint 18; richer matching belongs after the V1 pilot proves the simple flow.
- Rule export/import is deferred to Sprint 19 with the broader import/export completion work.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued without a separate plan review at user request.

- Added `UserRule` model and migration.
- Added rule candidate listing from correction metadata.
- Added approve/reject candidate flows and edit/disable user-rule flows.
- User-approved rules are loaded during inbound SMS enrichment and override deterministic rules for matching future candidates.
- Added focused rule priority, API, audit, and UI wiring tests.
- Review pass added duplicate approval/rejection guards, ledger-correction candidate match fields, priority validation, decision logging, backlog, and risk tracking.

# Sprint 9: Corrections and Rule Learning Foundation

## Goal

Allow reviewed SMS candidates and promoted ledger transactions to be corrected without losing parser, rule, review, duplicate, or ledger sanity history.

## Scope

- Add authenticated backend correction APIs for review candidates before promotion.
- Add authenticated backend correction APIs for promoted ledger transactions.
- Support correction of merchant, category, purpose, account, amount, transaction date, and transaction type where existing models can safely represent the field.
- Preserve original parser and deterministic rule output in metadata; corrections must override display/promotion values without deleting the original source values.
- Store before/after correction metadata in audit history for promoted ledger transactions.
- Store correction history in `RawSmsMessage.parser_output` for candidate corrections before promotion.
- Make promotion prefer user corrections over parser/rule values.
- Define a deterministic rule-candidate metadata shape that can later be used to create user-approved rules.
- Add focused tests for correction priority, validation, auditability, promotion behavior, and history preservation.

## Out of Scope

- Automatically creating production rules from corrections.
- Applying user-approved rules to future SMS messages.
- LLM-generated corrections or rules.
- Rich correction UI forms.
- Bulk edit or batch correction flows.
- Correction of duplicate resolution or ledger sanity decisions beyond preserving their existing metadata.
- Broad parser expansion for real bank SMS formats.
- Real SMS examples, real merchant names, real account identifiers, or secrets.

## Expected Changes

- `app/corrections.py` or equivalent correction service.
- `app/review_queue.py` integration if candidate correction logic belongs with review queue operations.
- `app/ledger_promotion.py` integration so corrected candidate values are used during promotion.
- `app/main.py` endpoints for candidate and ledger transaction corrections.
- `app/models.py` only if metadata-based correction history is not enough; prefer existing JSON metadata and `AuditEvent` first.
- New Alembic migration only if a model change is justified.
- `tests/test_corrections.py`.
- Updates to `tests/test_ledger_promotion.py` and review queue tests where corrected values affect existing flows.
- `README.md` correction development contract update.
- A decision record if Sprint 9 chooses a lasting correction metadata or priority strategy.
- `project-status.md`.

## Tests to Write First

- Correcting a pending review candidate stores before/after values in `parser_output.correction_history`.
- Correcting a candidate adds explicit `user_corrections` metadata and leaves original parser/rule metadata intact.
- Promotion uses corrected candidate values for ledger fields such as merchant, category, purpose, account, amount, date, and transaction type.
- Promoting a corrected candidate stores correction metadata in `LedgerTransaction.source_metadata`.
- Correcting a promoted ledger transaction updates ledger fields and creates an `AuditEvent` with before/after values and reason.
- Invalid correction fields return `422` and do not mutate stored candidate or ledger data.
- Unknown account corrections return `422` and do not mutate stored candidate or ledger data.
- Correction endpoints require the existing inbound SMS shared secret.
- Existing unreviewed, duplicate, ledger sanity mismatch, and idempotent promotion behavior stays intact.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures.

Test command:

```bash
docker compose run --rm app python -m pytest tests/test_corrections.py tests/test_ledger_promotion.py tests/test_review_queue.py
```

## Acceptance Criteria

- Corrections are deterministic, authenticated, validated, and covered by tests.
- User corrections take priority over parser and deterministic rule output during promotion.
- Original parser and rule outputs remain inspectable after correction.
- Candidate correction history is stored before promotion.
- Promoted ledger correction history is stored in audit events.
- Rule-candidate metadata is defined but no production rule is automatically created.
- Relevant tests, lint, and typecheck pass through Docker.
- CI passes before merge.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Build the Docker app image after code/test edits.
- [x] Ingest a fake SMS, correct merchant/category before review or promotion, and verify the original parser/rule values remain visible in metadata.
- [x] Promote a corrected fake SMS and verify the ledger transaction uses corrected values.
- [x] Correct a promoted fake ledger transaction and verify an audit event records before/after values.
- [x] Try an invalid correction field and verify no stored data changes.
- [x] Try an unknown account correction and verify no stored data changes.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- Candidate corrections currently fit in `RawSmsMessage.parser_output`; if correction history grows large, a normalized correction table may be needed later.
- Ledger transaction corrections can affect duplicate and ledger sanity metadata from the original promotion; Sprint 9 should preserve that metadata but may defer recalculation.
- Account correction validation is limited while accounts are still mostly fake-seeded; richer account management is planned for Sprint 12.
- The rule-candidate shape must not imply that corrections automatically become rules before the later user-approved rules sprint.

## Completion Notes

Sprint plan created on 2026-05-06. Implementation continued after the plan was reviewed.

- Added authenticated candidate correction endpoint at `PATCH /api/review-queue/{raw_sms_id}/corrections`.
- Added authenticated ledger correction endpoint at `PATCH /api/ledger-transactions/{transaction_id}/corrections`.
- Candidate corrections update current candidate fields while preserving parser/rule metadata and storing `user_corrections`, `correction_history`, and `rule_candidate` metadata.
- Promotion now carries candidate correction metadata into `LedgerTransaction.source_metadata` and uses corrected candidate values.
- Promoted ledger corrections update ledger fields and create `ledger_transaction_corrected` audit events with before/after values.
- Unsupported correction fields and unknown account corrections return `422` without mutating stored data.
- Added tests first in `tests/test_corrections.py`; initial focused run failed because correction endpoints did not exist.
- Focused Sprint 9 tests passed with `docker compose run --rm app python -m pytest tests/test_corrections.py tests/test_ledger_promotion.py tests/test_review_queue.py`.
- Full `docker compose run --rm app python -m pytest` passed with 66 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 27 source files.
- Built the Docker app image after code and test edits.
- Recorded Decision 0014 for storing corrections in metadata and audit events.
- Updated the risk register for JSON correction history and deferred duplicate/ledger sanity recalculation.

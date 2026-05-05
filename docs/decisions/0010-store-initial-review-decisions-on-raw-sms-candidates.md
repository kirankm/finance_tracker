# Decision 0010: Store Initial Review Decisions on Raw SMS Candidates

## Decision

Sprint 5 stores the first review decision metadata inside `RawSmsMessage.parser_output` instead of adding a separate persisted transaction candidate or review table.

## Reason

The app does not yet promote reviewed candidates into `LedgerTransaction`, and correction flows are still out of scope. Keeping review metadata with the stored parsed/enriched candidate provides traceability without introducing a schema that may need to change once ledger promotion and corrections are designed.

## Alternatives Considered

- Add a dedicated review queue table linked to `raw_sms_messages`.
- Add a persisted transaction candidate table before ledger promotion.
- Extend `AuditEvent` to reference raw SMS messages.

## Consequences

- Review decisions are persisted and explainable immediately.
- No migration is required for Sprint 5.
- Future ledger promotion may need to migrate review metadata into a more normalized candidate or audit structure.
- Raw SMS review detail endpoints must remain protected because they can expose the stored SMS body for inspection.

## Date

2026-05-05

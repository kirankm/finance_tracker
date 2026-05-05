# Decision 0011: Link SMS Ledger Promotions with a Raw SMS Foreign Key

## Decision

Sprint 6 adds nullable `LedgerTransaction.raw_sms_message_id` with a unique constraint and foreign key to `RawSmsMessage`.

Promotion also stores lightweight `promotion_metadata` on `RawSmsMessage.parser_output` so repeat API calls can return the existing ledger transaction. For the current fake-rule path, promotion creates the fake `acct_bank_1` account if needed.

## Reason

Ledger promotion needs durable idempotency and traceability. A JSON-only source link would explain the transaction but would not give the database a reliable uniqueness boundary for "this raw SMS has already been promoted."

The project does not yet have account management. The only promoted account in Sprint 6 fixtures is the deterministic fake account id `acct_bank_1`, so creating that fake account during promotion keeps local QA possible without introducing real account setup or real financial identifiers.

## Alternatives Considered

- Store only `raw_sms_id` inside `LedgerTransaction.source_metadata`.
- Add a separate promotion table between raw SMS and ledger transactions.
- Require account setup before promotion and make Sprint 6 unable to run end to end without account management.
- Create accounts dynamically for any candidate account id.

## Consequences

- Replaying promotion for the same raw SMS returns the existing ledger transaction instead of creating duplicates.
- Ledger transactions can be traced to the stored raw SMS without parsing JSON metadata.
- The schema changes through a migration.
- Cross-message duplicate detection remains out of scope for Sprint 6 and must be handled in the next duplicate detection sprint.
- The fake account auto-create behavior must be replaced or narrowed once account management exists.

## Date

2026-05-05

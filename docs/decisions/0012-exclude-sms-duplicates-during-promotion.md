# Decision 0012: Exclude SMS Duplicates During Promotion

Date: 2026-05-05

## Decision

Run deterministic duplicate detection during SMS ledger promotion and persist the result on the created `LedgerTransaction`.

Exact duplicates use the same account, reference, amount, transaction date, and transaction type. Possible duplicates use the same account, amount, transaction date, transaction type, and canonical merchant when the reference does not match.

Exact duplicates and possible duplicates are retained as ledger transactions for traceability, but use `ledger_status: excluded` so they do not affect ledger totals. Unique transactions use `ledger_status: included`.

## Reason

The first moment an SMS candidate can corrupt ledger totals is promotion into `LedgerTransaction`. Running the check there keeps the rule close to the write that affects the ledger, while preserving raw SMS and parser output unchanged.

Retaining duplicate transactions is safer than silently dropping them because the user can later inspect source metadata, audit events, and raw SMS linkage.

## Alternatives Considered

- Reject duplicate promotions with `409`: avoids ledger rows, but hides duplicate SMS records from later resolution workflows.
- Detect duplicates during ingestion only: catches candidates earlier, but cannot compare reliably until account, merchant, amount, date, and review metadata are available.
- Add a new duplicate table now: more normalized, but unnecessary before duplicate resolution UI and status transitions exist.
- Include possible duplicates in ledger totals until resolved: risks overstating expenses and violates the ledger safety principle.

## Consequences

- Duplicate decisions are explainable from `source_metadata.duplicate_detection` and raw SMS `parser_output.duplicate_detection`.
- Possible duplicate false positives are intentionally conservative and excluded until a later resolution flow can confirm uniqueness.
- Duplicate status values remain plain strings for now; formal enums can be added if status drift becomes a problem.
- Sprint 10 or a later backend sprint should add a user-facing way to resolve possible duplicates.

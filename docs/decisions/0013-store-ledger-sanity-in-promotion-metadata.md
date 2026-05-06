# Decision 0013: Store Ledger Sanity in Promotion Metadata

Date: 2026-05-06

## Decision

Run deterministic ledger sanity checks during SMS ledger promotion and persist the result in existing JSON metadata fields.

Ledger sanity metadata is stored on `LedgerTransaction.source_metadata.ledger_sanity` and raw SMS `parser_output.ledger_sanity`. Promotion responses include `ledger_sanity_status`.

Sprint 8 uses `Account.current_balance` as an explicit known pre-promotion balance when present. If `current_balance` or SMS available balance is missing, the check records `not_checked` rather than guessing. If the expected post-transaction balance differs from the observed SMS available balance, the promoted transaction uses `ledger_status: needs_review`.

## Reason

Ledger sanity is explainability metadata before it is a user-managed reconciliation workflow. Keeping the first implementation in promotion metadata avoids premature schema design while still making mismatch decisions auditable and visible.

Using `current_balance` as the known starting balance is conservative because the system does not yet have account-opening-balance management or full daily reconciliation windows.

## Alternatives Considered

- Add a dedicated ledger sanity table now: better normalized for future reconciliation history, but premature before the review and correction flows exist.
- Add new columns for sanity status and mismatch amount: easier to query, but increases schema surface before status transitions are settled.
- Exclude mismatched transactions from the ledger: avoids polluted totals, but can hide real transactions and makes the mismatch harder to inspect.
- Treat missing balance context as matched: simpler, but misleading and contrary to the explainability rule.

## Consequences

- Mismatch decisions are traceable from ledger source metadata, raw SMS parser output, promotion responses, and audit events.
- Mismatched transactions are retained and marked `needs_review`; later screens can surface them without losing source context.
- `Account.current_balance` must be treated as a known starting balance for the check, not as complete reconciliation state.
- Future reconciliation UI may justify promoting this metadata into first-class tables or columns.

# Decision 0014: Store Corrections in Metadata and Audit Events

Date: 2026-05-06

## Decision

Sprint 9 stores pre-promotion SMS candidate corrections in `RawSmsMessage.parser_output` and stores promoted ledger transaction corrections in `AuditEvent` records.

Candidate corrections update the candidate's current top-level fields so promotion uses the corrected values. The original parser metadata, deterministic rule metadata, `user_corrections`, `correction_history`, and `rule_candidate` metadata remain available for explainability.

Promoted ledger transaction corrections update the ledger fields directly and create a `ledger_transaction_corrected` audit event with before/after values and the user-provided reason. The transaction's `source_metadata` also keeps correction metadata for later inspection.

## Reason

Corrections are part of the trust foundation, but the product does not yet have mature correction, account management, or user-approved rule workflows. Existing JSON metadata and audit events are enough to make corrections traceable without adding premature schema surface.

User corrections must outrank parser and deterministic rule output during promotion while preserving the original automated decisions for later review.

## Alternatives Considered

- Add a dedicated correction table now: more queryable, but premature before the UI and rule-approval flows are designed.
- Keep corrections only as audit events: good for promoted ledger history, but not enough for pre-promotion candidate values that need to drive promotion.
- Mutate parser output without history: simpler, but violates explainability and makes rule learning impossible to reconstruct.
- Automatically create rules from corrections: useful later, but too risky before user-approved rule management exists.

## Consequences

- Candidate correction history is easy to inspect with the raw SMS review detail.
- Promotion can use corrected values without deleting original parser and rule metadata.
- Ledger corrections are auditable through `AuditEvent`.
- Correction metadata may need normalization later if correction history becomes large or needs richer querying.
- Duplicate and ledger sanity metadata from original promotion is preserved, not recalculated, in this sprint.

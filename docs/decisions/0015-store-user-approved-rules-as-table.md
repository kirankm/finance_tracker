# Decision 0015: Store User-Approved Rules as a First-Class Table

Date: 2026-05-06

## Decision

Store user-approved rules in a `user_rules` table and keep approve, reject, edit, and disable actions in audit events.

## Reason

Approved rules affect future SMS enrichment, so they need durable state, ordering, enabled/disabled behavior, and export/import support in the next sprint. Audit events alone are enough for candidate rejection history, but not enough for efficient rule application during inbound SMS ingestion.

## Alternatives Considered

- Store rules only inside correction metadata: simple, but hard to list, edit, disable, apply, export, or audit consistently.
- Store rules only as audit events: auditable, but inefficient and ambiguous as an application-time rule source.
- Keep rules hard-coded in `app/rules.py`: deterministic, but not user-editable.

## Consequences

- Sprint 18 adds a schema migration.
- User-approved rules can be loaded during inbound SMS enrichment before deterministic rules.
- Sprint 19 must include user rules in complete JSON export/import validation.
- Rule matching remains intentionally narrow exact matching until real fake-pilot usage justifies richer conditions.

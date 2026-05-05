# Decision 0006: Use a Lean Relational Ledger Schema

## Date

2026-05-05

## Decision

Use SQLAlchemy models and Alembic migrations for a lean relational ledger schema with accounts, ledger transactions, and audit events.

## Reason

Sprint 1 needs durable persistence for the V1 ledger without building SMS ingestion, parsing, or analysis early. A direct relational model keeps account and transaction data queryable, keeps soft deletes explicit, and provides enough audit history for automated and manual changes without committing to event sourcing.

## Alternatives Considered

- Event sourcing for every ledger change: stronger historical reconstruction, but too heavy before the ingestion and review workflows exist.
- JSON-only transaction storage: flexible, but weak for ledger queries, constraints, and future filtering.
- Separate tables for every status enum: more normalized, but unnecessary before the status vocabulary stabilizes through parser and review work.

## Consequences

- Schema changes continue through Alembic.
- Audit events capture explainability and correction history without becoming the source of truth.
- Status fields remain string values for now, so future migrations may tighten enum constraints once the workflows stabilize.

# 0009: Start with deterministic in-code rules

## Decision

Start Sprint 4 rule enrichment with deterministic in-code fake rules instead of adding persisted rule tables.

## Reason

The review queue and correction flows are not implemented yet, so the final shape of user-editable rules is still uncertain. A pure deterministic rules layer lets the app enrich parsed candidates now, keeps decisions explainable, and avoids introducing a schema that may need to change immediately in Sprint 5.

## Alternatives Considered

- Add persisted rule tables now. This would make future user-editable rules easier to imagine, but it risks premature schema design before correction workflows exist.
- Hard-code enrichment directly in the parser. This would be simpler short term, but it would mix parsing with account, merchant, and category decisions.
- Use LLM categorization now. This conflicts with the project principle that LLM output is not authoritative.

## Consequences

- The rules layer has a clear interface that can later read from persisted rules.
- Sprint 4 can lock behavior with fake golden enrichment fixtures.
- Adding real user-editable rules will still require a future migration.
- Only fake placeholder account and merchant identifiers are included.

## Date

2026-05-05

# Decision 0003: LLM Suggestions Are Non-Authoritative

## Date

2026-05-04

## Decision

LLM output may suggest categories, merchants, purposes, rules, or insight wording, but must not be treated as ledger truth.

## Reason

The product must be trustworthy. Financial records should be based on deterministic parsing, explicit rules, and user corrections.

## Alternatives Considered

- Let LLM classify and approve transactions automatically.
- Avoid LLM entirely.

## Consequences

- The app needs confidence, review status, and decision trail metadata.
- LLM can still reduce manual work, but user/rules remain authoritative.

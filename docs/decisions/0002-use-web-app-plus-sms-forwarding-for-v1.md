# Decision 0002: Use Web App Plus SMS Forwarding for V1

## Date

2026-05-04

## Decision

V1 should prefer a web/backend app that receives SMS messages from an external SMS forwarding app/service, instead of building a native Android SMS reader immediately.

## Reason

This reduces mobile app complexity and Android permission work in V1.
It lets the core product focus on ingestion, parsing, review, ledger checks, and insights.

## Alternatives Considered

- Native Android app reads and parses SMS.
- Android app parses locally and syncs structured data.
- Manual SMS import only.

## Consequences

- Need to choose a reliable SMS forwarding method.
- Need a secure inbound ingestion interface.
- Native Android app can remain a V2 option.

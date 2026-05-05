# Decision 0007: Use Internal Inbound SMS Payload Contract

## Decision

Sprint 2 will define a small internal inbound SMS payload contract for the backend:

```json
{
  "message_id": "fake-forwarder-msg-001",
  "sender": "FAKEBANK",
  "received_at": "2026-05-04T10:30:00Z",
  "body": "Fake SMS body"
}
```

Requests must send the shared secret in the `X-Inbound-SMS-Secret` header.

## Reason

The external SMS forwarding service has not been selected yet. A stable internal contract lets the backend build and test authentication, validation, raw SMS persistence, and deterministic parsing without coupling Sprint 2 to one forwarding vendor.

## Alternatives Considered

- Wait for a forwarding service selection before building ingestion. This would block parser and persistence work.
- Model a specific third-party payload now. This would risk rework if that service is not selected.
- Accept arbitrary payloads and normalize later. This would weaken validation and contract tests.

## Consequences

- Service-specific adapters can be added later without changing core ingestion behavior.
- Manual and automated tests can use a minimal fake payload.
- The risk around final external payload shape remains open until a forwarding service is selected.

## Date

2026-05-05

# Sprint 3: SMS Forwarder Integration

## Goal

Select and pilot an Android SMS-to-webhook forwarding path, adapt its payload into the internal inbound SMS contract, and verify the public HTTPS ingestion path with fake SMS only.

## Scope

- Select one primary Android forwarding path for the V1 pilot.
- Document the selected app setup and payload mapping.
- Add a service-specific adapter endpoint or normalization layer for the selected forwarder payload.
- Preserve the Sprint 2 internal inbound SMS contract as the core ingestion interface.
- Authenticate the forwarder-facing endpoint before payload validation.
- Store raw SMS through the existing raw SMS persistence path.
- Keep duplicate delivery idempotent.
- Add contract tests for the selected forwarder payload.
- Add public HTTPS QA steps using fake SMS payloads.
- Update risk tracking for external forwarder reliability and payload drift.

## Out of Scope

- Native Android SMS-reading app.
- Accepting or committing real personal SMS data.
- Parser expansion beyond fixtures needed to prove the integration path.
- Merchant normalization, account mapping, categorization, or review queue UI.
- SMS forwarding service cloud account setup for paid or hosted services.
- Multi-forwarder support beyond a documented extension point.

## Selected Pilot Direction

Use `bogkonstantin/android_income_sms_gateway_webhook` as the initial pilot candidate unless review finds a blocker.

Reasons:

- It sends incoming SMS directly to a configured URL over HTTP POST as JSON.
- It supports sender filtering and wildcard forwarding.
- It retries failed requests with exponential backoff.
- It has a documented sample payload with `from`, `text`, `sentStamp`, `receivedStamp`, and `sim`.
- It has no required cloud account in the forwarding path.

Keep SMSGate as the main fallback candidate because it is open source, actively presented as supporting Android devices, multiple modes, and privacy-focused operation, but it appears broader than the minimal inbound-webhook need for this sprint.

## Expected Changes

- `app/main.py`
- `app/config.py` if a forwarder-specific secret or path setting is needed
- `app/inbound_forwarders.py` or equivalent small adapter module
- `tests/test_inbound_sms.py`
- `tests/test_inbound_forwarders.py`
- `README.md`
- `docs/deployment/linode.md`
- `docs/decisions/`
- `docs/risk-register.md`
- `project-status.md`

## Tests to Write First

- Forwarder endpoint rejects requests without the shared secret before body validation.
- Forwarder endpoint rejects malformed selected-forwarder payloads without storing raw SMS.
- Forwarder endpoint maps `from` to `sender`.
- Forwarder endpoint maps `text` to `body`.
- Forwarder endpoint maps `receivedStamp` to `received_at`.
- Forwarder endpoint creates a deterministic `message_id` when the forwarder payload does not provide one.
- Replaying the same selected-forwarder payload is idempotent and returns the existing raw SMS record.
- Valid selected-forwarder fake SMS payloads still produce parser candidate metadata through the existing ingestion path.

Test command:

```bash
docker compose run --rm app python -m pytest
```

## Acceptance Criteria

- A specific SMS forwarding app/service is selected for the first V1 pilot.
- The selected forwarder payload is documented with a fake example.
- The backend accepts the selected forwarder payload through an authenticated endpoint.
- The backend maps the selected payload into the existing internal inbound SMS contract.
- `receivedStamp` is accepted as epoch milliseconds.
- Authentication happens before request-body validation.
- Duplicate delivery remains idempotent.
- Malformed or unauthenticated selected-forwarder payloads are rejected safely.
- Relevant tests, lint, and typecheck pass through Docker.
- Public HTTPS fake-payload QA is completed against the selected forwarder endpoint.
- No full raw SMS content is logged in production code paths.
- No real SMS, secrets, or private financial data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Manually POST a fake selected-forwarder payload to the local Docker app and verify it is accepted.
- [x] Manually POST a selected-forwarder payload with a missing/invalid secret and verify it is rejected before body validation.
- [x] Manually POST a malformed selected-forwarder payload and verify it is rejected without persistence.
- [x] Deploy the sprint build to the public HTTPS stack.
- [x] Manually POST a fake selected-forwarder payload to the public HTTPS endpoint and verify it is accepted.
- [x] Replay the same fake selected-forwarder payload and verify it returns the existing raw SMS record.
- [x] Verify recent logs do not include full raw SMS text.
- [x] Verify all new SMS fixtures and examples are fake or anonymized.

## Risks / Open Questions

- The selected pilot app may be stale or unreliable on the user's Android device.
- Android background restrictions may interrupt forwarding unless device-specific permissions are configured.
- The selected pilot app does not appear to include a first-class request signing feature, so the backend shared-secret header or URL/header configuration needs to be validated during implementation.
- Forwarder timestamps may be milliseconds since epoch, seconds since epoch, or string values; adapter tests must lock the accepted format.
- Real SMS forwarding should not be enabled until fake public HTTPS QA and log review pass.

## Completion Notes

Sprint plan created on 2026-05-05. Stop for review before implementation.

Implementation continued after review approval on 2026-05-05.

- Recorded Decision 0008 for the selected Android forwarder pilot.
- Added authenticated `POST /api/forwarders/android-income-sms-webhook`.
- Added deterministic selected-forwarder payload mapping into the internal inbound SMS contract.
- Added deterministic message IDs for selected-forwarder payloads so duplicate delivery remains idempotent.
- Added selected-forwarder contract tests first, confirmed they failed before implementation, then made them pass.
- Review hardening added validation for impossible numeric `receivedStamp` values so malformed selected-forwarder payloads return 422 instead of raising an internal exception.
- Review hardening added a production startup guard against the development inbound SMS shared secret.
- `docker compose run --rm app python -m pytest` passed with 27 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 14 source files.
- Deployed Sprint 3 build to the public HTTPS stack for fake-payload QA.
- Public HTTPS QA verified health 200, missing/wrong secret 401 before body validation, valid fake selected-forwarder payload 201, duplicate replay 200 with the same raw SMS id, and malformed valid-auth payload 422.
- Recent app logs showed request lines/statuses only, not full raw SMS content.

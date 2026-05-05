# Sprint 2: SMS Ingestion and Parsing

## Goal

Accept authenticated inbound SMS payloads from an external forwarding path, persist raw SMS safely, and convert fake financial SMS fixtures into structured transaction candidates with explainable parser metadata.

## Scope

- Define a minimal inbound SMS payload contract for V1.
- Add an authenticated inbound SMS API endpoint.
- Validate inbound payload shape and reject malformed requests.
- Persist raw SMS messages without logging full SMS content.
- Add deterministic SMS parsing for initial fake debit UPI-style fixtures.
- Produce transaction candidate data with amount, transaction type, purpose, merchant raw text, account hint when available, source, confidence, and review status.
- Record enough parser metadata to explain which parser matched and which fields were extracted.
- Expand the golden SMS fixture dataset with expected parser outputs.
- Keep all fixtures fake or anonymized.

## Out of Scope

- Selecting or integrating a specific SMS forwarding app/service.
- Native Android SMS reading.
- LLM categorization or merchant normalization.
- User-facing review queue flows.
- Duplicate detection.
- Ledger mismatch checks.
- Manual transaction entry.
- Production acceptance of real SMS payloads.
- Bank integrations.

## Expected Changes

- `app/main.py`
- `app/config.py`
- `app/models.py`
- `app/database.py` if persistence helpers are needed
- `app/sms_parser.py` or a small parser module/package
- `migrations/versions/`
- `tests/test_inbound_sms.py`
- `tests/test_sms_parser.py`
- `tests/fixtures/sms/golden/`
- `README.md` for the inbound SMS test/development contract
- `docs/risk-register.md` if unresolved ingestion or parser risks change
- `docs/decisions/` if the payload contract or parser design needs a durable decision record

## Tests to Write First

- Inbound endpoint rejects requests without the shared secret.
- Inbound endpoint rejects malformed payloads without storing raw SMS.
- Inbound endpoint accepts a valid fake SMS payload and stores the raw SMS record.
- Raw SMS persistence does not require real personal SMS data in tests.
- Parser extracts amount, transaction type, purpose, merchant raw text, source, and confidence from the existing fake UPI debit fixture.
- Parser returns an unmapped/unknown candidate with low confidence for an unrecognized fake financial SMS.
- Golden dataset test verifies every `.sms.txt` fixture has a matching `.expected.json` parser output.
- Endpoint response includes candidate/review metadata without exposing unnecessary raw SMS content.

Test command:

```bash
docker compose run --rm app python -m pytest
```

## Acceptance Criteria

- Sprint 2 has a documented inbound SMS payload contract.
- Inbound SMS endpoint requires authentication.
- Valid fake inbound SMS payloads are persisted as raw SMS records.
- Malformed or unauthenticated payloads are rejected safely.
- Initial deterministic parser converts fake UPI debit SMS fixtures into structured transaction candidates.
- Unknown SMS patterns remain reviewable instead of being silently discarded.
- Parser decisions include explainability metadata.
- Golden dataset tests pass and use fake/anonymized SMS only.
- Relevant tests, lint, and typecheck pass through Docker.
- No full raw SMS content is logged in production code paths.
- No real SMS, secrets, or private financial data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Run migration upgrade against a disposable SQLite database if schema changes are added.
- [x] Manually POST a fake valid inbound SMS payload and verify it is accepted.
- [x] Manually POST a payload with a missing/invalid secret and verify it is rejected.
- [x] Manually POST a malformed payload and verify it is rejected without persistence.
- [x] Verify logs do not include full raw SMS text.
- [x] Verify all SMS fixtures are fake or anonymized.

## Risks / Open Questions

- SMS forwarding service is not selected, so the sprint will define a stable internal payload contract and adapt service-specific mapping later.
- SMS formats vary by bank, card, UPI app, and payment network; this sprint should keep parser scope narrow and fixture-driven.
- Raw SMS persistence is privacy-sensitive; production logging and test fixtures must be reviewed carefully.
- Parser output may overlap with future categorization and merchant-normalization work; this sprint should stop at transaction candidate extraction and explainability metadata.
- Exact database shape for raw SMS and candidates needs to stay easy to migrate as ingestion requirements become clearer.

## Completion Notes

Sprint plan created on 2026-05-05. Stop for review before implementation.

Implementation continued after review approval on 2026-05-05.

- Recorded Decision 0007 for the internal inbound SMS payload contract.
- Added raw SMS persistence model and migration.
- Added authenticated `POST /api/inbound-sms` endpoint.
- Added deterministic fake UPI debit parser with confidence and parser metadata.
- Added golden dataset parser tests and inbound endpoint tests.
- `docker compose run --rm app python -m pytest` passed with 18 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 13 source files.
- Disposable SQLite migration smoke passed through `20260505_1125`.
- Deployed Sprint 2 image to the shared-server HTTPS stack for manual QA.
- Production migration applied through `20260505_1125`.
- Public HTTPS health check returned 200.
- Public fake inbound SMS QA returned 201 with `candidate_created`.
- Public missing-secret inbound SMS QA returned 401.
- Public malformed-payload inbound SMS QA returned 422.
- Recent app logs showed request lines/statuses only, not full raw SMS content.
- Review follow-up: moved inbound SMS auth ahead of request-body validation.
- Review follow-up: made duplicate `message_id` delivery idempotent with a 200 response and no second row.
- Review follow-up checks passed with 20 tests, lint, and mypy.
- Verified golden SMS fixtures use fake/anonymized placeholder bank, account, merchant, and reference values.
- Redeployed the hardened ingestion build to the public HTTPS stack.
- Public post-hardening QA verified health 200, missing/wrong secret 401 before body validation, valid fake SMS 201, duplicate message replay 200, and malformed valid-auth payload 422.
- Recent app logs after post-hardening QA showed request lines/statuses only, not full raw SMS content.

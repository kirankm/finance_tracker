# Sprint 5: Review Queue

## Goal

Add the first review queue workflow so parsed and enriched SMS transaction candidates can be listed, inspected, and marked with an explicit review decision before later ledger promotion and correction flows.

## Scope

- Add a backend review queue over stored `RawSmsMessage` records whose parser output has `review_status` requiring attention.
- Expose an API to list pending review items with stable ids, source metadata, received time, parsed/enriched candidate fields, confidence values, and explainability metadata.
- Expose an API to inspect one review item by raw SMS id.
- Add a narrow API to mark a review item as reviewed, keeping the raw SMS and parser output traceable.
- Record an audit event or equivalent explainability metadata for review decisions.
- Keep raw SMS body out of list responses; only detailed inspection may include it if explicitly needed for review and tests verify the behavior.
- Preserve idempotent inbound SMS behavior.
- Add tests first for queue ordering, filtering, detail lookup, review status updates, auditability, and privacy behavior.

## Out of Scope

- User correction forms for changing category, merchant, account, amount, or date.
- Creating deterministic rules from corrections.
- Promoting candidates into `LedgerTransaction`.
- Duplicate detection.
- Ledger mismatch checks.
- Full web UI beyond minimal backend/API support.
- Authentication/authorization beyond the existing development inbound SMS secret.
- Real personal SMS examples, real merchant names, real account identifiers, or secrets.

## Expected Changes

- `app/main.py` for review queue routes or route wiring.
- `app/models.py` if review decisions need a small persisted audit shape.
- `app/review_queue.py` or equivalent service module if queue behavior should be separated from HTTP handlers.
- `tests/test_review_queue.py`.
- Existing inbound SMS tests if response or stored review semantics need compatibility checks.
- `README.md` if new local API behavior should be documented.
- `docs/decisions/` if the sprint chooses a persisted candidate/review model.
- `docs/risk-register.md` if review privacy or audit risks remain unresolved.
- `project-status.md`.

## Tests to Write First

- Ingested fake SMS candidates with `review_status: needs_review` appear in the review queue.
- Reviewed or non-reviewable candidates are excluded from the pending queue by default.
- Pending review items are returned in a deterministic order, oldest received first unless a clearer ordering is chosen during implementation.
- Review queue list responses do not include raw SMS bodies.
- Review item detail returns the expected parsed/enriched candidate and explainability metadata for a fake SMS.
- Marking a review item as reviewed updates persisted review status without deleting raw SMS or parser metadata.
- Replaying the same review decision is idempotent or returns a clear validation response.
- Reviewing a missing raw SMS id returns `404`.
- Review decisions are auditable through `AuditEvent` or documented source metadata.
- No real SMS, real merchant names, real account identifiers, or secrets appear in fixtures.

Test command:

```bash
docker compose run --rm app python -m pytest
```

## Acceptance Criteria

- A caller can list pending review items created by SMS ingestion.
- A caller can inspect one pending or reviewed item with its parsed/enriched candidate fields and decision metadata.
- A caller can mark a review item as reviewed.
- Review decisions are persisted and traceable.
- Raw SMS bodies are not exposed in broad list responses.
- Existing inbound SMS and forwarder flows continue to pass.
- Relevant tests, lint, and typecheck pass through Docker.
- CI passes before merge.
- No real SMS, secrets, private merchant data, or private account data are committed.

## QA Checklist

- [x] Run `docker compose run --rm app python -m pytest`.
- [x] Run `docker compose run --rm app python -m ruff check .`.
- [x] Run `docker compose run --rm app python -m mypy`.
- [x] Ingest a fake known merchant SMS locally and verify it appears in the pending review queue.
- [x] Fetch the review item detail and verify candidate fields, confidence, and rule metadata are present.
- [x] Mark the fake review item as reviewed and verify it no longer appears in the pending queue.
- [x] Verify raw SMS body is absent from the queue list response.
- [x] Verify raw SMS and parser metadata remain stored after review.
- [x] Verify production code paths do not log full raw SMS content or sensitive payloads.

## Risks / Open Questions

- Review status currently lives inside `RawSmsMessage.parser_output`; Sprint 5 may need a separate persisted candidate/review table, but that could be premature before ledger promotion is designed.
- Marking a raw SMS candidate as reviewed before ledger promotion may create a temporary product concept that needs migration later.
- Detail responses may need raw SMS body for human review, but broad exposure of SMS body increases privacy risk.
- Audit events currently link to accounts or ledger transactions, not raw SMS messages; Sprint 5 should choose whether to extend audit structure now or record review metadata on the raw SMS candidate until ledger promotion exists.
- A minimal backend-only queue may be less useful without UI, but it provides a tested contract for a later review screen.

## Completion Notes

Sprint plan created on 2026-05-05. Stop for review before implementation.

Implementation continued after approval on 2026-05-05.

- Added authenticated review queue APIs:
  - `GET /api/review-queue`
  - `GET /api/review-queue/{raw_sms_id}`
  - `POST /api/review-queue/{raw_sms_id}/review`
- Reused the existing inbound SMS shared secret middleware for review queue endpoints.
- Kept list responses free of raw SMS bodies.
- Kept detail responses explicit and authenticated because they include the raw SMS body for review.
- Stored the first review decision metadata on `RawSmsMessage.parser_output` to avoid premature schema churn before ledger promotion and correction flows.
- Recorded Decision 0010 for the temporary review metadata storage choice.
- Added a review detail privacy risk and mitigation to the risk register.
- Added tests first in `tests/test_review_queue.py`; initial focused run failed with missing routes as expected.
- `docker compose run --rm app python -m pytest` passed with 40 tests.
- `docker compose run --rm app python -m ruff check .` passed.
- `docker compose run --rm app python -m mypy` passed with no issues in 18 source files.
- Local HTTP QA verified protected queue listing, detail inspection, review marking, and pending queue removal for a fake SMS.

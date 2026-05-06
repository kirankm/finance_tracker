# V1 Release Candidate

Date: 2026-05-06

## Status

V1 is a software release candidate for fake-data and production-like pilot
testing. It is not yet approved for real personal SMS ingestion.

The release-candidate workflow is covered by
`tests/test_v1_release_candidate_workflow.py`, which exercises:

- Android-forwarder style fake SMS ingestion.
- Parsing and deterministic enrichment.
- Candidate correction, review, and ledger promotion.
- Duplicate detection and ledger exclusion.
- User-approved rule creation and future SMS application.
- Cash balance adjustment.
- Ledger search.
- Analysis and insights.
- JSON export and import validation.
- SQLite backup and restore.
- Raw SMS privacy in broad search, insights, and export responses.

## Real-SMS No-Go Gates

Real personal SMS remains blocked until:

- The physical Android forwarder fake-device validation passes.
- The selected forwarder proves it can send `X-Inbound-SMS-Secret` as a header.
- At least one encrypted off-server backup copy exists outside the VPS.
- Production readiness has no unexpected blocker failures.

## Residual V1 Limitations

- Single-user shared-secret access, not multi-user browser authentication.
- External Android forwarding is still the SMS ingestion dependency.
- Duplicate resolution has detection and exclusion, but no dedicated resolution UI.
- Ledger sanity flags mismatches but does not provide full account reconciliation.
- User-approved rules are intentionally narrow exact-match rules.
- Import validation checks export shape but does not restore into the live database.
- Analysis and insights are deterministic summaries, not budgeting or forecasting.

## V2 Planning Boundary

V2 planning can begin from this release candidate, but V2 implementation should
not start until the real-SMS pilot gates are either completed or explicitly
replanned. Deferred V2 ideas remain in `docs/roadmap-2026-05-05.md` and
`docs/backlog.md`.

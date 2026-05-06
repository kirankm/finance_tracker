# Project Status

## Current Sprint

Sprint 19: Import and Export Completion

## Sprint Status

done

Allowed values:
- planning
- in_progress
- review
- qa
- done

## Last Completed Sprint

Sprint 19: Import and Export Completion

## Current Focus

Prepare Sprint 20 production pilot hardening.

## Current Branch

`sprint-19-import-export-completion`

## Open Blockers

- Selected Android forwarder still needs fake-device setup validation before real SMS ingestion.
- Selected Android forwarder header support for `X-Inbound-SMS-Secret` still needs validation on device.
- Host Python local checks need `python3.12-venv` and `python3-pip`; Docker checks pass.
- Backups are documented and smoke-tested locally; off-server backup storage still needs to be chosen before relying on real data.

## Notes

Keep this file short. Detailed history belongs in sprint docs and decision records.

GitHub remote is configured, `main` is the default branch, and GitHub Actions passed on the Sprint 5 PR.

V1 roadmap through the V2 planning boundary is drafted in `docs/roadmap-2026-05-05.md`.

Sprint 6 PR checks passed and the PR was merged to `main`.

Sprint 7 duplicate detection implementation and local QA are complete; CI
passed and PR #6 was merged to `main`.

Sprint 8 ledger sanity checks implementation and local QA are complete; CI
passed on PR #7.

Sprint 9 corrections and rule learning foundation implementation and local QA
are complete; CI passed and PR #8 was merged to `main`.

Sprint 10 minimal review UI, Sprint 11 export readiness, and Sprint 12
account/category management implementation and local QA are complete; CI passed
and PR #9 was merged to `main`.

Sprint 13 manual transaction management and Sprint 14 cash tracking
implementation and local QA are complete; CI passed on PR #10.

Sprint 15 structured search and filters implementation and local QA are
complete.

Sprint 16 deterministic analysis screen implementation and local QA are
complete.

Sprint 17 deterministic insights screen implementation and local QA are
complete.

Sprint 18 user-approved rules implementation and local QA are complete.

Sprint 19 import/export completion implementation and local QA are complete.

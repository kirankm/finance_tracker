# Project Status

## Current Sprint

Sprint 7: Duplicate Detection

## Sprint Status

done

Allowed values:
- planning
- in_progress
- review
- qa
- done

## Last Completed Sprint

Sprint 7: Duplicate Detection

## Current Focus

Plan Sprint 8 ledger sanity checks.

## Current Branch

`main`

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

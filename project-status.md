# Project Status

## Current Sprint

Sprint 5: Review Queue

## Sprint Status

done

Allowed values:
- planning
- in_progress
- review
- qa
- done

## Last Completed Sprint

Sprint 5: Review Queue

## Current Focus

Plan Sprint 6 ledger promotion.

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

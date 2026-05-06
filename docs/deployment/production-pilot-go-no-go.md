# Production Pilot Go / No-Go

Date: 2026-05-06

## Current Decision

No-go for real personal SMS until the physical Android forwarder validation is completed.

The app is ready for continued fake-data pilot testing through Docker, CI, and
the documented backup/export flows.

## Go Criteria

- HTTPS is active for the production domain.
- The app port is not publicly exposed outside the reverse proxy.
- `INBOUND_SMS_SECRET` is strong and not the development default.
- `GET /api/ops/readiness` has no blocker failures other than device-only checks.
- Android fake-device validation passes with header authentication.
- A fake production-like SQLite backup/restore smoke test has been run.
- At least one off-server backup copy exists before real SMS is accepted.
- JSON export has been checked with raw SMS bodies omitted by default.
- Logs have been checked for raw SMS body leakage.

## Auth Strategy

The production forwarding strategy remains header-based shared-secret
authentication using `X-Inbound-SMS-Secret`.

No query-string or body-token fallback is enabled in Sprint 20. If the selected
forwarder cannot send headers, real SMS remains blocked until a safer forwarder
or reviewed fallback is implemented.

## Off-Server Backup Choice

For the first personal pilot, the selected off-server backup approach is a
manual encrypted copy to a local machine controlled by the user, taken after the
SQLite backup command succeeds. Automated cloud sync remains deferred.

## Rollback

1. Stop the production stack.
2. Preserve the current SQLite database and latest backup.
3. Restore the last known-good backup with the documented `--force` restore command.
4. Start the stack and verify `/health`.
5. Rotate `INBOUND_SMS_SECRET` if forwarding credentials may have leaked.

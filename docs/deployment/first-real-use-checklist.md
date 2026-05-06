# First Real SMS Use Checklist

Date: 2026-05-06

Use this checklist before accepting real personal SMS payloads.

## Go / No-Go Gates

- [ ] HTTPS is active through Caddy for the production domain.
- [ ] The app port is not exposed publicly outside the reverse proxy.
- [ ] `INBOUND_SMS_SECRET` is strong, unique, and stored only in environment configuration.
- [ ] The selected Android forwarder has been validated with fake-device SMS payloads.
- [ ] Header support for `X-Inbound-SMS-Secret` has been validated on device, or a narrowly scoped fallback endpoint has been implemented.
- [ ] SQLite backup and restore have been smoke-tested with fake production-like data.
- [ ] Off-server backup storage has been selected and documented.
- [ ] JSON export has been tested and confirmed to omit raw SMS bodies by default.
- [ ] Logs have been reviewed to confirm full raw SMS bodies are not emitted.
- [ ] The review UI raw SMS detail behavior has been checked on a trusted local network.

## Rollback

- Stop the production container stack.
- Preserve the SQLite database file and latest backup before making changes.
- Restore the last known-good backup only after verifying the target path.
- Rotate `INBOUND_SMS_SECRET` if it may have been exposed.

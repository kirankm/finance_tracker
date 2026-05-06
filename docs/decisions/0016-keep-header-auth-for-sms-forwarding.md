# Decision 0016: Keep Header Auth for SMS Forwarding

Date: 2026-05-06

## Decision

For the first production pilot, SMS forwarding remains authenticated only by the
`X-Inbound-SMS-Secret` request header. Sprint 20 does not add query-string or
body-token authentication fallback.

## Reason

The inbound SMS pipeline handles financial SMS content. Header-based shared
secret auth keeps the credential out of URLs and request bodies that are more
likely to be copied, logged, cached, or exposed by tooling.

## Alternatives Considered

- Query-string token: easier for some forwarders, but higher leakage risk
  through logs, browser history, copied URLs, and monitoring tools.
- Body token: may work with more clients, but mixes credentials into payload
  data and creates more accidental logging risk.
- Switch forwarders if header support is unavailable: preserves the production
  endpoint contract at the cost of setup friction.

## Consequences

- Real SMS remains blocked until the selected Android forwarder proves it can
  send `X-Inbound-SMS-Secret` as a header.
- If header support fails, the next sprint must either switch forwarders or
  explicitly design and review a narrower fallback before real SMS is accepted.

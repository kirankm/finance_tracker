# Decision 0005: Use Caddy for Linode HTTPS

## Decision

Use Caddy as the reverse proxy and HTTPS terminator for the initial Linode Docker Compose deployment.

## Reason

Caddy keeps the production deployment small while providing automatic certificate provisioning and renewal. That fits the single-server Linode target and reduces operational work before the project starts accepting real SMS payloads.

## Alternatives Considered

- Nginx: mature and flexible, but requires more explicit certificate management.
- Traefik: strong fit for larger container setups, but adds more moving parts than this single-app deployment needs.
- Exposing Uvicorn directly: simpler, but unsuitable for production HTTPS and public internet exposure.

## Consequences

- The production Compose path needs ports `80` and `443` open on the Linode firewall.
- The app container should not expose port `8000` publicly in production.
- The deployment needs a real domain or subdomain pointed at the Linode IP before Caddy can issue certificates.
- Caddy data volumes must be preserved so certificates are not needlessly reissued.

## Date

2026-05-05

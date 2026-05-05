# Linode Deployment Notes

Sprint 0 targets a single Linode VPS running Docker Compose with Caddy as the public HTTPS reverse proxy.

## Assumptions

- The app runs behind HTTPS before any real SMS payloads are accepted.
- The server uses a real `.env` file that is not committed.
- `INBOUND_SMS_SECRET` is strong and unique to the deployment.
- `CADDY_DOMAIN` is a real domain or subdomain pointed at the Linode public IP.
- Raw SMS payloads are not logged.
- SQLite is acceptable for early single-user deployment only if backups are configured before real data is stored.

## Server Prerequisites

- Docker and Docker Compose plugin installed.
- Firewall allows only SSH, HTTP, and HTTPS from the internet.
- App port `8000` is not exposed directly to the public internet in production.
- A domain or subdomain points to the Linode public IP.

## Initial Run

```bash
cp .env.example .env
```

Edit `.env` on the server:

```text
ENVIRONMENT=production
INBOUND_SMS_SECRET=<strong-random-secret>
DATABASE_URL=sqlite:///./data/finance_tracker.db
CADDY_DOMAIN=daily-expense.duckdns.org
```

Use the local Compose file for a plain health check on the server:

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
```

Stop the local check before starting the production proxy:

```bash
docker compose down
```

## Production HTTPS Run

Confirm DNS points to the Linode IP:

```bash
dig +short daily-expense.duckdns.org
```

Start the production stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl https://daily-expense.duckdns.org/health
```

Caddy listens on ports `80` and `443`, obtains certificates automatically, and proxies traffic to the app over the internal Docker network. The production override removes the public `8000` port mapping from the app service.

## Shared Server Run

If another website already owns port `80`, keep that site running and publish only Caddy's HTTPS port for this app:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.shared-server.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.shared-server.yml ps
curl https://daily-expense.duckdns.org/health
```

This allows `daily-expense.duckdns.org` to use HTTPS on port `443` while the existing port-`80` site remains unchanged. A future shared reverse proxy can route multiple domains through the same ports `80` and `443`.

## Before Real SMS Ingestion

- Confirm Caddy can issue and renew HTTPS certificates for `CADDY_DOMAIN`.
- Confirm the external SMS forwarding service can send HTTPS requests.
- Add authenticated ingestion contract tests.
- Confirm production logs do not include full raw SMS content.
- Run and verify the SQLite backup/restore path in `docs/deployment/backup-restore.md`, or move to PostgreSQL.

## Backup Requirement

Do not store real financial SMS data until backup and restore are documented and tested.

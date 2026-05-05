# Linode Deployment Notes

Sprint 0 targets a single Linode VPS running Docker Compose.

## Assumptions

- The app runs behind HTTPS before any real SMS payloads are accepted.
- The server uses a real `.env` file that is not committed.
- `INBOUND_SMS_SECRET` is strong and unique to the deployment.
- Raw SMS payloads are not logged.
- SQLite is acceptable for early single-user deployment only if backups are configured before real data is stored.

## Server Prerequisites

- Docker and Docker Compose plugin installed.
- Firewall allows only SSH, HTTP, and HTTPS from the internet.
- App port `8000` is not exposed directly to the public internet once a reverse proxy is configured.
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
```

Build and run:

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
```

## Before Real SMS Ingestion

- Configure HTTPS with a reverse proxy such as Caddy, Nginx, or Traefik.
- Confirm the external SMS forwarding service can send HTTPS requests.
- Add authenticated ingestion contract tests.
- Confirm production logs do not include full raw SMS content.
- Configure SQLite backup and restore commands, or move to PostgreSQL.

## Backup Requirement

Do not store real financial SMS data until backup and restore are documented and tested.

# Sprint 0: Project Setup

## Goal

Create the foundation for reliable Codex-driven development before product features are built.

## Scope

- Initialize project structure.
- Choose and document tech stack.
- Document the stack decision in `docs/decisions/`.
- Set up Docker-based local development.
- Set up test framework.
- Set up lint/typecheck where applicable.
- Set up CI.
- Add environment variable handling.
- Add fake fixture strategy.
- Document V1 SMS ingestion direction: external forwarding service / inbound SMS pipeline, not native Android app.
- Document Linode VPS deployment assumptions.
- Add Caddy reverse proxy path for Linode HTTPS.
- Add initial docs: backlog, risk register, decisions.

## Out of Scope

- Real SMS ingestion.
- Native Android SMS-reading app.
- Real SMS data.
- Transaction parser implementation.
- Review UI.
- Analysis or insights.
- Bank integrations.

## Expected Changes

Chosen Sprint 0 stack:

- Python 3.12
- FastAPI backend
- Server-rendered HTML with Jinja templates for the initial web UI
- SQLite for local development, accessed through SQLAlchemy
- Alembic for migrations
- pytest for tests
- ruff for linting/format checks
- mypy for type checking
- Docker Compose for local run path
- GitHub Actions for CI

Expected files:

```text
.env.example
.dockerignore
.github/workflows/ci.yml
Dockerfile
README.md
alembic.ini
app/
app/__init__.py
app/config.py
app/main.py
app/sqlite_backup.py
app/templates/
docker-compose.yml
docs/decisions/0004-use-python-fastapi-sqlite-for-sprint-0.md
docs/decisions/0005-use-caddy-for-linode-https.md
docs/deployment/backup-restore.md
docs/deployment/linode.md
docker-compose.shared-server.yml
migrations/
pyproject.toml
tests/
tests/fixtures/sms/golden/
tests/test_app_smoke.py
tests/test_config.py
```

## Tests to Write First

- Basic smoke test proving the test framework runs.
- Basic app/server startup test where applicable.
- Config loading test where applicable.

## Acceptance Criteria

- App can run locally.
- App can run through Docker.
- Tests can run locally.
- Tests can run in CI.
- Secrets are not hardcoded.
- Fake data approach is documented.
- `project-status.md` is current.

## QA Checklist

- [ ] Run host local app startup command.
- [x] Run Docker startup command.
- [x] Run test command.
- [x] Run lint command.
- [x] Run typecheck command.
- [x] Confirm CI config exists.
- [x] Confirm `.env.example` exists.
- [x] Confirm no real SMS data is present.
- [x] Confirm production `.env` exists on Linode and is not committed.
- [x] Confirm Docker image does not contain `.env` or `.venv`.
- [x] Confirm production HTTPS health check works on Linode.
- [x] Confirm app port `8000` is not listening publicly on Linode.
- [x] Run SQLite backup/restore smoke test with fake data.

## Risks / Open Questions

- SMS forwarding mechanism is not selected.
- Exact inbound SMS payload contract is not finalized.
- Linode is the target deployment environment.
- Production HTTPS/reverse proxy path uses Caddy, but needs DNS/firewall verification on the Linode server.
- Shared Linode server has another container using port `80`; finance tracker can run with Caddy bound to `443` only.
- Production backup/restore path is documented and smoke-tested with fake data; off-server backup storage still needs to be chosen before relying on real data.
- SQLite may need to be replaced by PostgreSQL if deployment, concurrency, or backup needs outgrow it.

## Completion Notes

Planning updated with a proposed concrete Sprint 0 stack on 2026-05-05.

Implementation completed and moved to review on 2026-05-05.

Checks run:

```text
docker compose build
docker compose run --rm app python -m pytest
docker compose run --rm app python -m ruff check .
docker compose run --rm app python -m mypy
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker run --rm -e CADDY_DOMAIN=daily-expense.duckdns.org -v /home/kiran/projects/finance_tracker/Caddyfile:/etc/caddy/Caddyfile:ro caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile
docker compose up
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/
```

Results:

- Docker image built successfully.
- Tests passed: 4 passed.
- Ruff passed.
- Mypy passed.
- Production Compose config rendered successfully with no public `8000` app port.
- Caddyfile validation passed.
- Docker startup passed.
- `/health` returned `{"status":"ok"}`.
- `/` rendered the foundation page.
- Production `.env` was created on Linode with restrictive file permissions and a generated inbound SMS secret.
- Added `.dockerignore` so `.env`, `.venv`, caches, git metadata, and local data directories are excluded from Docker images.
- Added a config regression test so app settings ignore unrelated deployment dotenv keys such as `CADDY_DOMAIN`.
- Narrowed the Caddy container environment so it receives `CADDY_DOMAIN` only, then rotated the inbound SMS secret.
- Restarted the shared-server production stack and verified `https://daily-expense.duckdns.org/health` returns `{"status":"ok"}`.
- Verified the app container has no public `8000` listener in production.
- Added and smoke-tested SQLite backup/restore commands with fake data through the shared-server Compose path.

Host-only Python checks were not run because the host is missing `python3.12-venv` and `python3-pip`. README documents the required packages.

No git remote is configured, so remote CI was not observed from this server. The GitHub Actions workflow exists and the Docker-based local checks pass.

Linode VPS was identified as the target deployment environment during review. Added deployment notes for Docker Compose, HTTPS, firewalling, secrets, and backups.

Caddy was selected for the initial Linode HTTPS reverse proxy path during review. Added `docker-compose.prod.yml`, `Caddyfile`, and a deployment decision record.

Deployment domain set to `daily-expense.duckdns.org` during review.

Added a shared-server Compose override for Linode hosts where another website already owns port `80`.

Sprint 0 completed on 2026-05-05.

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
.github/workflows/ci.yml
Dockerfile
README.md
alembic.ini
app/
app/__init__.py
app/config.py
app/main.py
app/templates/
docker-compose.yml
docs/decisions/0004-use-python-fastapi-sqlite-for-sprint-0.md
docs/deployment/linode.md
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

## Risks / Open Questions

- SMS forwarding mechanism is not selected.
- Exact inbound SMS payload contract is not finalized.
- Linode is the target deployment environment.
- Production HTTPS/reverse proxy path is not configured yet.
- Production backup/restore path is not configured yet.
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
docker compose up
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/
```

Results:

- Docker image built successfully.
- Tests passed: 4 passed.
- Ruff passed.
- Mypy passed.
- Docker startup passed.
- `/health` returned `{"status":"ok"}`.
- `/` rendered the foundation page.

Host-only Python checks were not run because the host is missing `python3.12-venv` and `python3-pip`. README documents the required packages.

Linode VPS was identified as the target deployment environment during review. Added deployment notes for Docker Compose, HTTPS, firewalling, secrets, and backups.

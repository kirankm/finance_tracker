# Decision 0004: Use Python FastAPI and SQLite for Sprint 0

## Date

2026-05-05

## Decision

Use Python 3.12, FastAPI, server-rendered Jinja templates, SQLite, SQLAlchemy, Alembic, pytest, ruff, mypy, Docker Compose, and GitHub Actions for the Sprint 0 foundation.

## Reason

The product needs a reliable backend-first foundation for authenticated SMS ingestion, deterministic parsing, auditability, tests, migrations, and a practical review UI. FastAPI keeps inbound API work straightforward, while server-rendered pages keep the early UI simple. SQLite is enough for local-first Sprint 0 development and can be migrated later if deployment requirements demand it.

## Alternatives Considered

- Django: strong built-in admin and ORM, but heavier than needed for the first foundation.
- Node.js with Next.js: good full-stack option, but adds more frontend surface area before ingestion and ledger correctness are proven.
- PostgreSQL immediately: closer to production, but unnecessary for Sprint 0 unless deployment requirements are finalized now.

## Consequences

- The project starts backend-first with a simple web UI path.
- Schema changes must go through Alembic migrations.
- Local setup can run without an external database service.
- A future PostgreSQL move remains possible if concurrency, hosting, or backup needs require it.

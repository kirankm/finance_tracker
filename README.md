# Automated SMS-Based Expense Tracker

This repository is intended to be built with Codex using a sprint-based, TDD-first workflow.

Start by reading:

- `PROJECT.md`
- `PROJECT_PRINCIPLES.md`
- `AGENTS.md`
- `project-status.md`
- the current sprint file listed in `project-status.md`


## V1 Architecture Direction

V1 is a web/backend app that receives SMS through an external SMS forwarding service or equivalent inbound SMS pipeline.

A native Android SMS-reading app is out of scope for V1 and can be reconsidered later if forwarding is too limiting.

## Current State

Sprint 0 implementation is in review.

## Development Commands

Install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

Run the app locally:

```bash
. .venv/bin/activate
uvicorn app.main:app --reload
```

Run tests:

```bash
. .venv/bin/activate
python -m pytest
```

Run lint:

```bash
. .venv/bin/activate
python -m ruff check .
```

Run typecheck:

```bash
. .venv/bin/activate
python -m mypy
```

Run through Docker:

```bash
docker compose up --build
```

The app listens on `http://localhost:8000`.

Run the Linode-style production stack with Caddy:

```bash
cp .env.example .env
# edit .env before starting production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

See `docs/deployment/linode.md` before accepting real SMS payloads.

On Debian/Ubuntu hosts, install `python3.12-venv` and `python3-pip` if `python3 -m venv .venv` or `python3 -m pip` is unavailable.

## Data Safety

Do not commit real SMS data, real bank messages, secrets, or personal financial data.
Use fake or anonymized fixtures only.

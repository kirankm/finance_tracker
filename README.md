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

Sprint 4 rules and categorization is merged to `main`. The app has authenticated
SMS ingestion, the selected Android forwarder adapter, and deterministic
fake-rule enrichment for account mapping, merchant normalization, and category
assignment. Sprint 5 adds the first authenticated backend review queue for
stored SMS transaction candidates.

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

Run database migrations:

```bash
. .venv/bin/activate
python -m alembic upgrade head
```

Run a disposable SQLite migration smoke test:

```bash
DATABASE_URL=sqlite:////tmp/finance_tracker_migration_smoke.db python -m alembic upgrade head
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
See `docs/deployment/backup-restore.md` for the SQLite backup and restore path.

On Debian/Ubuntu hosts, install `python3.12-venv` and `python3-pip` if `python3 -m venv .venv` or `python3 -m pip` is unavailable.

## Data Safety

Do not commit real SMS data, real bank messages, secrets, or personal financial data.
Use fake or anonymized fixtures only.

## Inbound SMS Development Contract

Sprint 2 uses an internal JSON contract for fake SMS ingestion while the external forwarding service remains undecided.

Endpoint:

```text
POST /api/inbound-sms
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

Payload:

```json
{
  "message_id": "fake-forwarder-msg-001",
  "sender": "FAKEBANK",
  "received_at": "2026-05-04T10:30:00Z",
  "body": "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_FOOD_1 on 04-May-2026. Avl Bal Rs.50000. Ref 123456."
}
```

The endpoint stores the raw SMS body for traceability, returns parser candidate metadata for review, and must not log full raw SMS content.

Known fake parser outputs are enriched with deterministic fake rules before
storage. Unknown account or merchant values remain reviewable and are not
guessed.

## Review Queue Development Contract

Review queue endpoints use the same development shared secret header as inbound
SMS endpoints:

```text
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

List pending review items:

```text
GET /api/review-queue
```

List responses include parsed/enriched candidate fields and explainability
metadata, but do not include raw SMS bodies.

Inspect one review item:

```text
GET /api/review-queue/{raw_sms_id}
```

Detail responses include the stored raw SMS body for explicit review.

Mark a review item as reviewed:

```text
POST /api/review-queue/{raw_sms_id}/review
```

Payload:

```json
{
  "decision": "reviewed",
  "reason": "fake QA review"
}
```

Sprint 5 stores review decision metadata on the parsed candidate output. Ledger
promotion and correction flows are intentionally deferred.

## Selected Android Forwarder Pilot

Sprint 3 uses `bogkonstantin/android_income_sms_gateway_webhook` as the first
forwarder pilot.

Endpoint:

```text
POST /api/forwarders/android-income-sms-webhook
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

Selected forwarder payload:

```json
{
  "from": "FAKEBANK",
  "text": "Rs.480 debited from BANK_1 a/c XX0000 to MERCHANT_FOOD_1 on 04-May-2026. Avl Bal Rs.50000. Ref 123456.",
  "sentStamp": "1777890599000",
  "receivedStamp": "1777890600000",
  "sim": "SIM1"
}
```

Mapping:

| Forwarder field | Internal field |
|---|---|
| `from` | `sender` |
| `text` | `body` |
| `receivedStamp` | `received_at` |
| `from` + `text` + `receivedStamp` + `sim` hash | `message_id` |

`receivedStamp` is accepted as epoch milliseconds. Replaying the same payload is
idempotent because the backend derives the same deterministic `message_id`.

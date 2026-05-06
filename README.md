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

Sprint 7 duplicate detection is merged to `main`. The app has authenticated SMS
ingestion, the selected Android forwarder adapter, deterministic fake-rule
enrichment for account mapping, merchant normalization, and category assignment,
an authenticated backend review queue for stored SMS transaction candidates, and
an authenticated path for promoting reviewed fake candidates into ledger
transactions with deterministic duplicate detection.

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

Open the minimal local review UI at:

```text
http://localhost:8000
```

The UI asks for the same `X-Inbound-SMS-Secret` used by the API before loading
review data or sending review, correction, and promotion actions.

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

Review decision metadata is stored on the parsed candidate output. Correction
flows are intentionally deferred.

## Ledger Promotion Development Contract

Ledger promotion uses the same development shared secret header as inbound SMS
and review queue endpoints:

```text
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

Promote one reviewed review item:

```text
POST /api/review-queue/{raw_sms_id}/promote
```

Payload:

```json
{
  "reason": "fake ledger QA"
}
```

A reviewed, fully mapped fake candidate creates one `LedgerTransaction` and
returns `201`:

```json
{
  "status": "promoted",
  "ledger_transaction_id": "txn_...",
  "raw_sms_id": "raw_sms_...",
  "duplicate_status": "unique",
  "ledger_status": "included",
  "ledger_sanity_status": "matched"
}
```

Replaying promotion for the same raw SMS returns the existing transaction with
`200` and `status: "already_promoted"`. Promotion responses include
`duplicate_status`, `ledger_status`, and `ledger_sanity_status`. Unreviewed
candidates return `409`. Candidates missing required ledger fields return
`422`. Missing raw SMS ids return `404`.

Sprint 6 links promoted ledger transactions to `RawSmsMessage` through
`raw_sms_message_id` and stores source metadata for parser, rule, review,
reference, and available-balance context. Sprint 7 adds cross-message duplicate
detection during promotion. Sprint 8 adds promotion-time ledger sanity metadata.

## Duplicate Detection Development Contract

Sprint 7 detects duplicates during ledger promotion against already-promoted
SMS-derived ledger transactions.

Status behavior:

| Match | `duplicate_status` | `ledger_status` |
|---|---|---|
| No duplicate match | `unique` | `included` |
| Same account, reference, amount, date, and transaction type | `exact_duplicate` | `excluded` |
| Same account, amount, date, transaction type, and canonical merchant | `possible_duplicate` | `excluded` |

Duplicate decisions are stored in ledger `source_metadata.duplicate_detection`
and raw SMS `parser_output.duplicate_detection`. Duplicate promotions are kept
for traceability and audit history; they are not deleted or silently dropped.

## Ledger Sanity Development Contract

Sprint 8 checks SMS available balance during ledger promotion when enough
balance context exists.

The check uses `Account.current_balance` as an explicit known pre-promotion
balance. It applies debit and credit balance impact and compares the expected
post-transaction balance with the SMS `available_balance`.

Status behavior:

| Context | `ledger_sanity_status` | `ledger_status` |
|---|---|---|
| Missing available balance or missing account current balance | `not_checked` | existing duplicate-derived ledger status |
| Expected balance matches SMS available balance | `matched` | `included` |
| Expected balance differs from SMS available balance | `mismatch` | `needs_review` |
| Duplicate-excluded promotion | `not_checked` | `excluded` |

Ledger sanity decisions are stored in ledger `source_metadata.ledger_sanity` and
raw SMS `parser_output.ledger_sanity`. Mismatched transactions are retained for
auditability and review; they are not silently corrected, deleted, or marked as
duplicates.

## Corrections Development Contract

Sprint 9 adds authenticated correction endpoints using the same shared secret
header as inbound SMS, review queue, and promotion endpoints:

```text
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

Correct a review candidate before promotion:

```text
PATCH /api/review-queue/{raw_sms_id}/corrections
```

Correct a promoted ledger transaction:

```text
PATCH /api/ledger-transactions/{transaction_id}/corrections
```

Payload:

```json
{
  "updates": {
    "merchant_canonical": "Corrected Merchant",
    "category": "groceries"
  },
  "reason": "fake correction"
}
```

Supported correction fields are `merchant_raw`, `merchant_canonical`,
`category`, `purpose`, `account_id`, `amount`, `transaction_date`, and
`transaction_type`. Unsupported fields return `422`. Unknown account
corrections return `422`.

Candidate corrections update the current candidate fields so promotion uses the
corrected values, while preserving parser and rule metadata. Candidate
correction history is stored in `parser_output.user_corrections`,
`parser_output.correction_history`, and `parser_output.rule_candidate`.

Promoted ledger corrections update the ledger transaction and create a
`ledger_transaction_corrected` audit event with before/after values and the
correction reason. The transaction source metadata also records correction
history and rule-candidate metadata for later user-approved rule workflows.

Rule-candidate metadata is informational only in Sprint 9. No production rule is
created automatically from a correction.

## Export Development Contract

Sprint 11 adds explicit authenticated export endpoints using the same shared
secret header:

```text
X-Inbound-SMS-Secret: <INBOUND_SMS_SECRET>
```

Export structured JSON:

```text
GET /api/export/json
```

The JSON export includes accounts, ledger transactions, raw SMS metadata, and
audit events. It does not include raw SMS bodies by default.

Export ledger CSV:

```text
GET /api/export/ledger-transactions.csv
```

Raw SMS body bulk export is intentionally deferred because it needs a separate
privacy decision and user-facing warning.

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

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

Sprint 18 user-approved rules is merged to `main`. The app has authenticated SMS
ingestion, the selected Android forwarder adapter, deterministic fake-rule
enrichment for account mapping, merchant normalization, and category assignment,
an authenticated backend review queue for stored SMS transaction candidates, an
authenticated path for promoting reviewed fake candidates into ledger
transactions with deterministic duplicate and ledger sanity checks, account and
category management, manual transaction workflows, cash balance updates, and
structured ledger search/filtering, deterministic analysis summaries, and
deterministic insights, and user-approved rules.

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

The JSON export uses `format_version: 2` and includes accounts, ledger
transactions, raw SMS metadata, categories, audit events, and user-approved
rules. It does not include raw SMS bodies by default.

Raw SMS body export is explicit:

```text
GET /api/export/json?include_raw_sms_body=true
```

When this flag is used, raw SMS rows include `body_exported: true` and `body`.
Without the flag, raw SMS rows include `body_exported: false` and omit `body`.

Export ledger CSV:

```text
GET /api/export/ledger-transactions.csv
```

Validate exported JSON before restore/import:

```text
POST /api/import/json/validate
```

The validator supports export `format_version` 1 and 2. Version 1 is accepted
with a warning because it predates user-approved rules. Validation checks shape
and reports section counts; it does not write to the live database.

## Operational Readiness Contract

Sprint 20 adds an authenticated readiness endpoint:

```text
GET /api/ops/readiness
```

The endpoint reports production pilot checks without exposing secret values. A
development-default `INBOUND_SMS_SECRET` is reported as a blocker. Real SMS
remains no-go until the Android forwarder fake-device validation and off-server
backup gates in `docs/deployment/production-pilot-go-no-go.md` pass.

## Account and Category Management Development Contract

Sprint 12 adds authenticated management endpoints using the same shared secret
header:

```text
GET /api/accounts
POST /api/accounts
PATCH /api/accounts/{account_id}

GET /api/categories
POST /api/categories
PATCH /api/categories/{category_id}
DELETE /api/categories/{category_id}
```

Account updates create `account_updated` audit events with before/after values.
Category deletes are soft deletes. Deleting a category used by active ledger
transactions returns `409`.

## Manual Transaction Development Contract

Sprint 13 adds authenticated manual transaction endpoints using the same shared
secret header:

```text
POST /api/manual-transactions
PATCH /api/manual-transactions/{transaction_id}
POST /api/manual-transactions/{transaction_id}/ignore
POST /api/manual-transactions/{transaction_id}/mark-duplicate
DELETE /api/manual-transactions/{transaction_id}
POST /api/manual-transactions/{transaction_id}/restore
```

Create payload:

```json
{
  "transaction_date": "2026-05-06",
  "amount": "125.50",
  "transaction_type": "debit",
  "purpose": "expense",
  "category": "food_delivery",
  "merchant_raw": "FAKE_MANUAL_FOOD",
  "merchant_canonical": "Fake Manual Food",
  "account_id": "acct_cash_wallet",
  "reason": "fake manual entry"
}
```

Manual transactions are stored as `LedgerTransaction` rows with `source:
manual`, `review_status: reviewed`, `duplicate_status: unique`, and
`ledger_status: included`. Manual create, update, ignore, duplicate, delete, and
restore actions create audit events. Deletes are soft deletes. The manual
transaction endpoints reject SMS-derived ledger transactions.

Update payload:

```json
{
  "updates": {
    "amount": "130.00",
    "merchant_canonical": "Corrected Fake Manual Food"
  },
  "reason": "fake correction"
}
```

Supported update fields are `transaction_date`, `amount`, `transaction_type`,
`purpose`, `category`, `merchant_raw`, `merchant_canonical`, and `account_id`.
Unknown accounts and deleted categories return `422`.

## Cash Tracking Development Contract

Sprint 14 adds an authenticated cash balance update endpoint:

```text
POST /api/accounts/{account_id}/cash-balance
```

Payload:

```json
{
  "reported_balance": "4200.00",
  "reported_on": "2026-05-06",
  "record_difference_as_adjustment": true,
  "reason": "fake cash count"
}
```

The endpoint only accepts accounts with `account_type: cash`. It compares the
stored expected cash balance with the reported balance, updates
`current_balance` and `last_manual_update`, and creates a `cash_balance_updated`
audit event.

When `record_difference_as_adjustment` is true and the difference is non-zero,
the endpoint creates an auditable manual `cash_adjustment` transaction. A cash
shortfall is categorized as `cash_spend`; a surplus is categorized as
`cash_surplus`. Zero-difference updates do not create adjustment transactions.

## Ledger Search Development Contract

Sprint 15 adds an authenticated structured ledger search endpoint:

```text
GET /api/ledger-transactions
```

Supported query parameters:

```text
id
date_from
date_to
account_id
transaction_type
purpose
category
merchant
amount_min
amount_max
review_status
duplicate_status
ledger_status
source
include_deleted
sort_by
sort_dir
limit
offset
```

`sort_by` supports `transaction_date`, `amount`, `created_at`, `updated_at`,
`merchant`, and `account_id`. `limit` is bounded to 100. Soft-deleted
transactions are hidden by default and visible when `include_deleted=true`.
Ignored, duplicate, and ledger-excluded transactions can be found through their
explicit status filters.

Search responses include transaction fields, status fields, selected
source/audit context, and audit event counts. They do not include raw SMS
bodies; raw SMS body inspection remains limited to explicit review detail
endpoints.

## Analysis Development Contract

Sprint 16 adds an authenticated deterministic analysis endpoint:

```text
GET /api/analysis/summary
```

Supported query parameters:

```text
month=YYYY-MM
date_from=YYYY-MM-DD
date_to=YYYY-MM-DD
```

Use `month` for a calendar-month summary, or provide `date_from` and `date_to`
together for an explicit date range. Financial totals include only ledger
transactions that are reviewed, unique, included, and not soft-deleted.

The response includes:

- income vs normal expense totals
- normal expense totals by category
- normal expense totals by account
- separate totals for investment, savings, transfer, refund, reversal, and cash update purposes
- cash balance change totals
- quality counts for review-needed, unmapped, and excluded-from-total rows

Analysis uses deterministic ledger fields only. LLM-written insights, budgets,
forecasting, and investment holdings are out of scope.

## Insights Development Contract

Sprint 17 adds authenticated deterministic insight endpoints:

```text
GET /api/insights
POST /api/insights/{insight_id}/dismiss
POST /api/insights/{insight_id}/review
```

`GET /api/insights` supports `month`, `date_from`, `date_to`,
`include_dismissed`, and `include_reviewed`. Insight IDs are deterministic and
derived from the insight type, period, linked transaction IDs, and metadata.

Generated insight types include:

- unmapped transactions
- possible duplicates
- ledger mismatches
- cash balance differences
- notable category changes

Each insight links to underlying ledger transaction IDs and includes structured
metadata. Insight copy is deterministic; LLMs do not determine insight truth.
Dismiss and review actions create audit events and are hidden from the default
insight list unless explicitly included.

## User-Approved Rules Development Contract

Sprint 18 adds authenticated user-approved rule endpoints:

```text
GET /api/rule-candidates
POST /api/rule-candidates/{candidate_id}/approve
POST /api/rule-candidates/{candidate_id}/reject

GET /api/user-rules
PATCH /api/user-rules/{rule_id}
POST /api/user-rules/{rule_id}/disable
```

Rule candidates are derived from user correction metadata on review candidates
and ledger transactions. Approving a candidate creates an enabled `UserRule`.
Rejecting a candidate creates an audit event and does not create a rule. Editing
and disabling rules are also audited.

Enabled user-approved rules are loaded during inbound SMS enrichment and apply
before built-in deterministic rules. Sprint 18 supports exact fake
`merchant_raw` and `account_clue` match conditions, with user-approved set
values for account, canonical merchant, category, and purpose.

Rule priority order for future candidates is:

```text
user-approved rule > existing deterministic rule > unknown
```

Already-corrected review candidates and ledger transactions keep their explicit
user correction metadata and are not silently rewritten by new rules.

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

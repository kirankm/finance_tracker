# Project Principles: Automated SMS-Based Expense Tracker

This file contains project-specific non-negotiables for this product.

## Core Trust Principle

This app handles financial SMS data. Correctness, explainability, recoverability, and privacy matter more than cleverness.

The product goal is:

> Make SMS-based expense tracking trustworthy with minimum manual work.

## V1 Boundary

V1 is an SMS-based expense tracker using an external SMS forwarding app/service or equivalent inbound SMS pipeline.

V1 should not build:
- bank integrations
- budgeting
- investment holdings dashboard
- net worth dashboard
- LLM chat over expenses
- recurring pattern detection
- split transactions

## LLM Role

The LLM is not authoritative.

Priority order:

```text
User-approved rule
> User correction
> Existing deterministic rule
> LLM soft suggestion
> Unknown
```

LLM output may suggest merchant normalization, categories, purposes, insights copy, or rule candidates.
LLM output must not silently decide ledger truth.

## Financial Data Safety

- Never use raw personal SMS in tests.
- Never commit real SMS data.
- Never log full raw SMS content in production.
- Use fake or anonymized fixtures.
- Keep secrets in environment variables.
- Separate development, staging, and production data.
- Export and backup actions must be explicit and user-initiated.

## Golden Dataset

The project must maintain a curated golden dataset of fake or anonymized SMS examples with expected outputs.

The golden dataset is the source of truth for parser, categorization, duplicate detection, ledger checks, and regression testing.

Rules:
- Never use raw personal SMS in the golden dataset.
- Every SMS fixture must have an expected structured output.
- Every new SMS pattern must add or update a fixture.
- Parser changes must pass the full golden dataset test suite.
- Categorization/rule changes must not silently change expected outputs.
- If expected output changes, the sprint document must explain why.

## Explainability Rule

Every automated decision must be traceable.

The app should store enough metadata to explain:
- what parser/rule produced the result
- what fields were extracted
- what confidence was assigned
- why review was needed
- what changed after user correction
- why a transaction was included/excluded from ledger and analysis

## Auditability

Every automated and manual change should be auditable.

Examples:
- system parsed SMS
- rule matched merchant
- LLM suggested category
- user changed category
- rule created from correction
- transaction marked duplicate
- transaction soft-deleted

## Ledger Safety

- Transactions must not disappear silently.
- Deletes must be soft deletes.
- Duplicates must not affect ledger calculations unless confirmed unique.
- Ledger mismatches must be visible and explainable.
- Manual edits must preserve history.

## SMS Ingestion Principle

V1 should not build a native Android SMS-reading app.
Prefer an external SMS forwarding path if it can reliably send SMS content to the backend.
A native Android app can be reconsidered later only if the forwarding approach becomes unreliable or too limiting.

The inbound SMS pipeline must be:
- authenticated
- validated
- safely logged
- resilient to malformed input
- testable with fake fixtures

Codex should propose concrete implementation details in the relevant sprint plan.

## Containerization Principle

Containerization is a Sprint 0 foundation, not a V2 feature.
The app should be able to run locally through Docker and later be deployable on a personal server.

## Migration Discipline

- Every schema change must use a migration.
- Do not edit old migrations after merge.
- Rollback strategy should be documented where practical.
- Seed data must be fake.
- Production data must never be reset casually by a script.

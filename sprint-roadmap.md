# Sprint Roadmap

This roadmap is intentionally high-level. Each sprint gets detailed only when it becomes current.

## Sprint 0: Project Setup

Goal: create the foundation for reliable Codex-driven development.

Includes:
- repo structure
- AGENTS.md
- project docs
- TDD setup
- CI setup
- Docker setup
- environment handling
- fake seed data approach
- privacy/security baseline
- inbound SMS pipeline design principles

## Sprint 1: Core Ledger Foundation

Goal: implement the core transaction/account/audit model.

Includes:
- transaction model
- account model
- audit trail
- soft delete
- manual transaction basics if needed for testing

## Sprint 2: SMS Ingestion and Parsing

Goal: convert inbound SMS payloads into structured transaction candidates.

Includes:
- inbound SMS interface for external SMS forwarding payloads
- raw SMS persistence
- parser
- unmapped fallback
- confidence metadata
- golden dataset tests

## Sprint 3: SMS Forwarder Integration

Goal: select and pilot the Android SMS-to-webhook forwarding path.

Includes:
- forwarding app/service selection
- service-specific payload adapter
- fake public HTTPS forwarding QA
- setup documentation
- risk update for payload drift and Android reliability

## Sprint 4: Rules and Categorization

Goal: map accounts, normalize merchants, and assign type/purpose/category.

Includes:
- account mapping
- merchant canonicalization
- category assignment
- purpose assignment
- user correction influence
- soft LLM suggestions if used

## Sprint 5: Review Queue

Goal: make uncertain transactions reviewable and correctable.

Includes:
- review statuses
- edit/accept/ignore flows
- create rule from correction
- correction history

## Sprint 6: Trust Checks

Goal: detect duplicates and ledger mismatches.

Includes:
- duplicate detection
- ledger sanity checks
- mismatch explanations
- review reasons

## Sprint 7: Manual Transactions and Cash

Goal: support manual expenses, cash balance updates, and cash spend reconciliation.

Includes:
- add/edit/delete transaction
- cash account
- cash adjustment
- uncategorized cash spend flow

## Sprint 8: Analysis

Goal: deterministic analysis of money movement.

Includes:
- spend by category
- spend by account
- income vs expense
- investment/savings separated
- unmapped counts

## Sprint 9: Insights

Goal: surface notable findings from structured data.

Includes:
- deterministic insight calculations
- optional LLM wording only
- reviewable insight explanations

## Sprint 10: Import, Export, Backup

Goal: let the user safely move and recover data.

Includes:
- CSV export
- JSON export
- local backup
- restore

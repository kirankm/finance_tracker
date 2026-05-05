# Decision 0001: Use Sprint-Based Codex Workflow

## Date

2026-05-04

## Decision

Use a sprint-based workflow for Codex with one branch per sprint by default.

## Reason

The product handles sensitive financial data and needs predictable, reviewable progress.
Sprints keep Codex focused and reduce scope creep.

## Alternatives Considered

- One large implementation prompt.
- One branch per tiny feature.
- No sprint structure.

## Consequences

- More structure up front.
- Easier review, testing, QA, and rollback.
- Feature branches can still be used for risky experiments.

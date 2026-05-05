# AGENTS.md

This file contains reusable working rules for Codex. Keep it mostly project-agnostic.

## Operating Mode

Work in small, reviewable increments.
Do not implement outside the current sprint or approved task.
Prefer boring, reliable, tested code over clever code.

Always read:
- `PROJECT.md`
- `PROJECT_PRINCIPLES.md`
- `project-status.md`
- the current sprint file named in `project-status.md`

## Workflow Modes

Use the lightest workflow that safely fits the task.

### Full Sprint Mode

Use for:
- new features
- schema changes
- security-sensitive changes
- data model changes
- core business logic
- external integrations
- anything marked high-risk in `PROJECT_PRINCIPLES.md`

Requires:
- sprint branch
- sprint document
- tests first
- implementation
- local checks
- CI passing
- review
- QA checklist
- project-status update
- backlog/risk/decision updates where relevant

### Small Change Mode

Use for:
- typos
- copy edits
- README tweaks
- minor UI polish
- harmless refactors

Requires:
- clear task
- relevant checks
- tests if behavior changes
- no unnecessary sprint ceremony

## Branching

Default branch pattern:

```text
sprint-XX-short-name
```

Use one branch per sprint by default.
Create a separate feature/experiment branch only when a change is large, risky, or may need to be abandoned.

## Sprint Planning

Before implementing a sprint, create or update the sprint document under `/sprints/`.

Each sprint document must include:
- goal
- scope
- out of scope
- expected changes
- tests to write first
- acceptance criteria
- QA checklist
- risks/open questions
- completion notes

After writing the sprint plan, stop and wait for review unless explicitly told to continue.

## TDD Rule

For behavior changes:
1. Write failing tests first.
2. Implement the smallest code needed to pass.
3. Run relevant tests.
4. Do not weaken, delete, or rewrite tests just to pass.
5. Add regression tests for bugs.

Before coding, state:
- what behavior is being tested
- which edge cases are covered
- which command runs the tests

## Checks

Before marking work complete, run the relevant project checks.
The exact commands should be documented in `README.md` once the stack is chosen.

Typical checks may include:

```bash
# JavaScript/TypeScript examples
npm test
npm run lint
npm run typecheck

# Python examples
pytest
ruff check .
mypy .
```

## CI Rule

CI is the merge gate.
Work is not complete if CI fails.
Do not bypass failing tests, lint, typecheck, migrations, or security checks without documenting the reason and getting review.

## Definition of Done

A Full Sprint task is done only when:
- tests were written first where applicable
- relevant tests pass
- lint passes
- typecheck passes where applicable
- CI passes
- Docker/local run path is still valid
- QA checklist is completed
- sprint document is updated
- `project-status.md` is updated
- new decisions are recorded if needed
- risks are recorded if unresolved
- out-of-scope ideas are moved to backlog

## Scope Control

Before adding any feature, check whether it belongs to the current sprint.
If outside scope:
- do not implement it
- add it to `docs/backlog.md`
- mention why it was deferred

## Decision Logging

When a sprint introduces an important product or architecture decision, create a decision record in `docs/decisions/`.

Each decision record must include:
- decision
- reason
- alternatives considered
- consequences
- date

## Risk Tracking

If a product, data, security, integration, or architecture risk cannot be fully solved in the current sprint, add or update `docs/risk-register.md`.

Do not hide risks in comments or chat.

## Review

When asked to review, check:
- correctness
- tests
- edge cases
- scope creep
- data safety
- readability
- migration safety
- whether project principles were followed

## Data and Logging Hygiene

Do not commit secrets.
Do not commit real private user data.
Use fake fixtures unless the project explicitly permits anonymized data.
Avoid noisy logs and avoid logging sensitive payloads.

# ChatGPT Scientific Review Coordination

This directory is the repository-local coordination layer required by the recurring scientific-review session. It is intentionally separate from any removed factory, fleet, ticket, or supervisor infrastructure.

## Scheduled scientific-review session

1. Read `MASTER_INDEX.md`, `BACKLOG.md`, `ACTIVE_TASK.md`, `HANDOFF.md`, `BLOCKERS.md`, and recent `SESSION_LOG.md` entries before selecting work.
2. Claim exactly one primary task in `ACTIVE_TASK.md` with UTC time, base `main` SHA, owner, scope, assumptions, files, commands, validation plan, progress, and acceptance state.
3. Distinguish repository facts, measured data, simulation outputs, independent calculations, literature-backed facts, assumptions, hypotheses, approximations, and unresolved questions.
4. Preserve raw data and provenance. Never conceal failures, force-push, rewrite history, delete unrelated contributor work, or weaken a validation gate to obtain a passing result.
5. Validated progress must be present on remote `main`. A branch or pull request is transport only when needed for protection, review, or CI.
6. Update the relevant ledgers, append `SESSION_LOG.md`, refresh `HANDOFF.md`, and retain a reproducible record under `archive/` in the same run.

## Separate AI coding session

A separate interactive AI coding session may implement scoped work, but it must not claim ownership of the scheduled review task without updating `ACTIVE_TASK.md`. It must preserve unrelated changes, base work on current `origin/main`, run the declared checks, and leave an explicit handoff. The scheduled scientific-review session independently verifies evidence and decides whether work is safe for `main`.

## Required records

- `MASTER_INDEX.md`: cumulative item-level coverage and evidence state.
- `BACKLOG.md`: stable task IDs, dependencies, impact, acceptance criteria, and status.
- `ACTIVE_TASK.md`: exactly one primary current task.
- `HANDOFF.md`: latest complete reproducible handoff.
- `SESSION_LOG.md`: append-only run history.
- `STUDY_REVIEW_LEDGER.md`: one record per study.
- `CLAIM_EVIDENCE_MATRIX.md`: claims mapped to evidence and limitations.
- `CODE_RESULT_MAP.md`: result-to-code/config/data/artifact dependencies.
- `VISUALIZATION_MATRIX.md`: claim-to-plot coverage and acceptance criteria.
- `BLOCKERS.md`: exact access, data, compute, Git, CI, validation, and scientific blockers.
- `archive/`: immutable completed or superseded session records retained for provenance.

## Coverage states

`NOT_STARTED`, `TRIAGED`, `ACTIVE`, `PARTIAL`, `VALIDATED`, `FLAWED`, `BLOCKED`, `SUPERSEDED`, `COMPLETE`.

## Current priority

Maintain fail-closed scientific evidence gates while advancing item-level review. Current-main amplitude-audit CI was restored in merge commit `4f857f508160bbbe059d936866b426a45788c9bd`. Real A-002 amplitude convention, pulse polarity, and output regeneration remain blocked under `BLK-AMP-001`.

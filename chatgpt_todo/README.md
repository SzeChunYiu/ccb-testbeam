# ChatGPT ↔ AI Session Coordination

This directory is the repository-local control plane for scheduled ChatGPT audit runs and interactive AI coding sessions.

## Protocol

1. Read `MASTER_INDEX.md`, `BACKLOG.md`, `ACTIVE_TASK.md`, `HANDOFF.md`, `BLOCKERS.md`, and the latest `SESSION_LOG.md` entry before starting work.
2. Claim exactly one primary task in `ACTIVE_TASK.md` using a stable task ID, UTC timestamp, base commit, and branch.
3. Do not duplicate an ACTIVE or COMPLETE task. Reclaim stale work only after documenting why it is stale.
4. Record evidence, exact commands, environment, seeds, data provenance, tests, plots, limitations, and unresolved questions while working.
5. Update the affected ledgers and `HANDOFF.md` before ending a session.
6. Commit coordination files together with validated code, analysis, test, plot, or documentation changes.
7. Never mark a task COMPLETE unless its acceptance criteria are met and the commit/push state is recorded.

## Status vocabulary

`NOT_STARTED`, `TRIAGED`, `ACTIVE`, `PARTIAL`, `VALIDATED`, `FLAWED`, `BLOCKED`, `SUPERSEDED`, `COMPLETE`.

## Required ledgers

- `MASTER_INDEX.md`: repository-wide audit coverage.
- `BACKLOG.md`: prioritized actionable tasks.
- `ACTIVE_TASK.md`: the currently claimed task.
- `HANDOFF.md`: latest reproducible handoff.
- `SESSION_LOG.md`: append-only session history.
- `STUDY_REVIEW_LEDGER.md`: per-study reviews.
- `CLAIM_EVIDENCE_MATRIX.md`: claim-to-evidence mapping.
- `CODE_RESULT_MAP.md`: result-to-code/data/config dependencies.
- `VISUALIZATION_MATRIX.md`: claim-to-plot coverage.
- `BLOCKERS.md`: exact blockers and resolution steps.
- `archive/`: completed or superseded detailed handoffs.

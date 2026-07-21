# ChatGPT Scientific Review Coordination

This directory is the canonical, repository-local coordination layer for recurring scientific-review and engineering sessions.

## Rules

1. Read `MASTER_INDEX.md`, `BACKLOG.md`, `ACTIVE_TASK.md`, `HANDOFF.md`, `BLOCKERS.md`, and the latest `SESSION_LOG.md` entry before selecting work.
2. Claim exactly one primary task in `ACTIVE_TASK.md` with UTC time, base `main` SHA, owner, scope, validation plan, and acceptance criteria.
3. Distinguish observed repository facts, measured data, simulation results, independent calculations, literature-backed facts, assumptions, hypotheses, and unresolved questions.
4. Never modify raw data destructively, conceal failed checks, force-push, rewrite history, or overwrite unrelated work.
5. Validated progress must land on remote `main`. Temporary branches and pull requests are transport only when protection or review rules require them.
6. Do not merge code with failing CI or unmet scientific acceptance criteria. Accurate blocker documentation may be committed directly to `main`.
7. Update the relevant ledgers and append `SESSION_LOG.md` in the same run.
8. Preserve completed or superseded handoffs under `archive/` rather than deleting provenance.

## Coverage states

`NOT_STARTED`, `TRIAGED`, `ACTIVE`, `PARTIAL`, `VALIDATED`, `FLAWED`, `BLOCKED`, `SUPERSEDED`, `COMPLETE`.

## Current priority

PR #868 contains Geant4 multithread RNG provenance and validation work. Its Python test suite passed in GitHub Actions run `29855061309`, while ruff reported three E501 formatting findings. The PR remains scientifically blocked from merge because Geant4 11.2.2 build/runtime validation, real ROOT comparisons, forced-thread checks, multiseed analysis, and optical-yield regeneration remain incomplete.

# Active Task

- **Task ID:** AUD-DOC-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T03:07:07Z
- **Base main SHA:** `24471b53045b0d064de96f94425ed6ea6b175243`
- **Primary scope:** correct stale coordination state and safely synchronize public C12 evidence wording without truncating files or overwriting concurrent work.
- **Files inspected:** `chatgpt_todo/HANDOFF.md`, `BLOCKERS.md`, `SESSION_LOG.md`, `ACTIVE_TASK.md`, `WIKI.md`, `docs/academic_chapters/09_anomaly_id.md`, and `scripts/sync_c12_public_claims.py`.
- **Observed facts:** the Geant4 validation session is recorded complete; PR #868 integration remains open because current `main` advanced and the PR was reported non-mergeable; WIKI and Chapter 9 remain stale.
- **Current blocker:** connector-only file replacement is unsafe for the 431-line WIKI and 725-line chapter because full bytes are unavailable locally and DNS resolution fails.
- **Validation plan:** use the exact synchronizer in a complete checkout, run `--check`, its regression tests, and the broken-link checker, then review the exact diff before direct-to-main commit.
- **Progress:** stale blocker states and task ownership corrected on `main`; public-file synchronization remains blocked.
- **Acceptance status:** PARTIAL

# Active Task

- **Task ID:** AUD-AMP-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T12:08:38Z
- **Base main SHA:** `8bff3f834c9da713996d946de1b16f3777e433a4`
- **Primary scope:** eliminate hidden file-order dependence from amplitude-convention classification before measuring the exact A-002 source table.
- **Files inspected:** `tools/audit/amplitude_convention_audit.py`, `tests/test_amplitude_convention_audit.py`, `chatgpt_todo/ACTIVE_TASK.md`, and `chatgpt_todo/HANDOFF.md`.
- **Observed fact:** version 2.0.0 classified only the first 40,000 rows by default. Reordering identical table rows could therefore change the inferred convention.
- **Implementation:** full-column classification is now the default; explicit `--max-rows` runs are labelled `PREFIX_SAMPLE`, marked row-order-dependent, recorded as partial, and return nonzero.
- **Validation:** syntax checks passed and the focused synthetic suite passed with `7 passed in 0.19s`; a regression demonstrates prefix NET versus full-table ABSOLUTE classification for the same ordered values.
- **Evidence boundary:** no real pulse table was accessed, so the prior 17 ABSOLUTE / 2 NET corpus result and the A-002 source-table convention were not rerun.
- **Progress:** code, tests, and immutable archive record are on remote `main`.
- **Acceptance status:** PARTIAL — full-table default behavior is validated synthetically; real-table classification and regenerated provenance artifacts remain BLOCKED_COMPUTE.

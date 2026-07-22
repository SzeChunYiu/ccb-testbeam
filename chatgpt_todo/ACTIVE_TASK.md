# Active Task

- **Task ID:** AUD-AMP-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T17:01:05Z
- **Base main SHA:** `9033b4a0b8b69914451e5c44e8b4f7d6a3b8c78b`
- **Primary scope:** make unresolved pedestal subtraction non-accepting for tables classified as absolute-code amplitude.
- **Files inspected:** `tools/audit/amplitude_convention_audit.py`, `tests/test_amplitude_convention_audit.py`, `chatgpt_todo/ACTIVE_TASK.md`, and `chatgpt_todo/HANDOFF.md`.
- **Observed fact:** version 2.4.0 reported `ABSOLUTE_WITHOUT_BASELINE_LEVEL` or `MULTIPLE_BASELINE_LEVEL_COLUMNS`, but its aggregate exit status still returned success when no other gate failed.
- **Implementation:** version 2.5.0 records `baseline_resolution` as `RESOLVED`, `MISSING`, `AMBIGUOUS`, or `NOT_REQUIRED`; counts unresolved absolute baselines; and returns nonzero for any unresolved absolute table.
- **Validation:** exact reconstructed source and the new regression file passed `python -m py_compile ...` and `python -m pytest /tmp/ampgate/tests -q` with `3 passed in 0.07s`.
- **Evidence boundary:** no real pulse table was accessed; the prior corpus and exact A-002 source-table convention were not rerun.
- **Progress:** code and focused regression are committed directly to remote `main`; immutable handoff is recorded.
- **Acceptance status:** PARTIAL — the aggregate baseline-resolution gate is validated synthetically; real-table classification and regenerated provenance artifacts remain BLOCKED_COMPUTE.

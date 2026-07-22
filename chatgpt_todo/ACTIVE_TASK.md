# Active Task

- **Task ID:** AUD-AMP-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T14:07:00Z
- **Base main SHA:** `1030da2a132670921de5bf5715c594f587ab12b7`
- **Primary scope:** prevent malformed nonnumeric `amplitude_adc` entries from being silently excluded while the convention audit still passes.
- **Files inspected:** `tools/audit/amplitude_convention_audit.py`, `tests/test_amplitude_convention_audit.py`, `chatgpt_todo/ACTIVE_TASK.md`, and `chatgpt_todo/HANDOFF.md`.
- **Observed fact:** version 2.2.0 recorded `nonnumeric_amplitude_rows` but did not warn or fail the aggregate gate, unlike its treatment of nonfinite numeric values.
- **Implementation:** version 2.3.0 emits `NONNUMERIC_AMPLITUDE_VALUES_EXCLUDED`, reports `n_nonnumeric_tables`, fails the gate for affected tables, and rejects all-nonnumeric amplitude columns.
- **Validation:** syntax checks passed and the focused suite passed with `13 passed in 0.21s`.
- **Evidence boundary:** no real pulse table was accessed; the prior corpus and exact A-002 source-table convention were not rerun.
- **Progress:** code, tests, and immutable archive record are on remote `main`.
- **Acceptance status:** PARTIAL — malformed-value handling is validated synthetically; real-table classification and regenerated provenance artifacts remain BLOCKED_COMPUTE.

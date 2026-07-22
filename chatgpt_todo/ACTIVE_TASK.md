# Active Task

- **Task ID:** AUD-AMP-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T15:03:46Z
- **Base main SHA:** `7d880de8af436634be083649350ce2ed26383424`
- **Primary scope:** prevent baseline dispersion columns such as `baseline_rms_adc` from being misused as pedestal levels in amplitude-convention diagnostics.
- **Files inspected:** `tools/audit/amplitude_convention_audit.py`, `tests/test_amplitude_convention_audit.py`, `docs/contracts/PULSE_TABLE_CONTRACT.md`, `chatgpt_todo/ACTIVE_TASK.md`, and `chatgpt_todo/HANDOFF.md`.
- **Observed fact:** version 2.3.0 selected any sole column containing `baseline`; a lone RMS/noise column could therefore produce a physically meaningless subtraction diagnostic and false `subtract_baseline_correct=true`.
- **Implementation:** version 2.4.0 separates pedestal-level candidates from RMS/std/sigma/noise/width/variance diagnostics and requires exactly one level candidate.
- **Validation:** syntax checks passed and the focused suite passed with `16 passed in 0.32s`.
- **Evidence boundary:** no real pulse table was accessed; the prior corpus and exact A-002 source-table convention were not rerun.
- **Progress:** code and tests are committed to remote `main`; immutable handoff update follows.
- **Acceptance status:** PARTIAL — baseline-column semantics are validated synthetically; real-table classification and regenerated provenance artifacts remain BLOCKED_COMPUTE.

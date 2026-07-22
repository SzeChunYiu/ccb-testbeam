# Active Task

- **Task ID:** AUD-AMP-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T11:05:08Z
- **Base main SHA:** `10c1f92ba80f42792dfa8a2074161c073979b221`
- **Primary scope:** harden amplitude-convention classification before measuring the exact A-002 source table.
- **Files inspected:** `tools/audit/amplitude_convention_audit.py`, `docs/contracts/PULSE_TABLE_CONTRACT.md`, `chatgpt_todo/HANDOFF.md`, and the A-002 active-task record.
- **Observed fact:** the prior auditor used hard-coded LUNARC paths, silently skipped read failures, stored no immutable input provenance, and forced every median into ABSOLUTE or NET using one threshold.
- **Implementation:** explicit CLI inputs/output; SHA-256 and byte-size provenance; retained read errors; explicit SKIPPED records; preregistered NET/AMBIGUOUS/ABSOLUTE bands; nonzero exit for errors or ambiguous classifications; baseline availability diagnostics.
- **Validation:** focused synthetic regression suite passed with `5 passed in 0.08s`.
- **Evidence boundary:** no real pulse table was accessed, so the prior 17 ABSOLUTE / 2 NET corpus result and the A-002 table convention were not rerun.
- **Progress:** code, tests, and immutable archive record are on remote `main`.
- **Acceptance status:** PARTIAL — auditor behavior is validated synthetically; real-table classification and regenerated provenance artifacts remain BLOCKED_COMPUTE.

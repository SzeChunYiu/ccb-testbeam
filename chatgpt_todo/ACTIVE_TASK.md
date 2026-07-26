# Active Task

- **Task ID:** `AUD-FIG-001`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T061216Z`
- **Initial remote main SHA:** `d046259666a08dbf9188e8a80d5a3b0cbced5765`
- **Scope:** determine whether the shipped paper figure registry can satisfy its own structural validator without erasing scientific evidence states or forcing source-figure-only entries into a false result-file contract.
- **Policy:** `FIGURE_REGISTRY_SCHEMA_MUST_ACCEPT_ITS_SHIPPED_VOCABULARY`.
- **Confirmed defect:** the implementation permits five statuses and two kinds, while `paper/figures.yaml` uses ten statuses and three kinds; five illustrative entries omit `result` by design but the validator requires it unconditionally; the test suite freezes the obsolete status set while asserting the shipped registry is valid.
- **Validation:** focused syntax and pytest passed (`5 passed in 0.07s`); current-like semantic fixture returned `FLAWED` with nine findings; corrected fixture returned `VALIDATED` with zero findings; invalid UTF-8, destructive aliasing, atomic JSON, JSON parse, and SVG parse checks passed.
- **Evidence:**
  - `docs/validation/figure_registry_schema_alignment_validation.json`
  - `docs/validation/figure_registry_schema_alignment.svg`
  - `docs/validation/figure_registry_schema_alignment_audit.md`
  - `chatgpt_todo/archive/2026-07-26T061216Z_AUD-FIG-001_SCHEMA_ALIGNMENT.md`
- **Focused acceptance:** audit tooling and evidence `VALIDATED / COMPLETE`.
- **Repository acceptance:** figure-registry schema and builder remain `FLAWED / PARTIAL` pending a controlled vocabulary, explicit status-to-disposition map, conditional path requirements, exact shipped-registry regression, and focused builder tests.
- **Scientific boundary:** no figure value, uncertainty, source result, calibration, PID, timing, stopping, pile-up, or detector-performance claim is validated by this task.
- **Status:** `PARTIAL`

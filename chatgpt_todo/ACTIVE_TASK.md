# Active Task

- **Task ID:** AUD-MV3-SEL-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T233022Z
- **Initial remote main SHA:** `0aa777457fff37a817bce29a7ea1656683210ddf`
- **Scope:** audit the weighted MV3 producer's Pearson chi-square implementation for unsupported
  observed categories, malformed profile normalization, and fail-closed statistical semantics.
- **Confirmed defect:** `_chi2` masks all zero-expected bins. For model fractions
  `[0.50, 0.50, 0, 0]` and observations `[45, 45, 10, 0]`, it drops the unsupported B6 count and
  returns finite `chi2/ndf = 1.0`. It also accepts model fractions summing to `0.95`.
- **Policy:**
  `PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`.
- **Files delivered:** auditor, six focused regressions, renderer, validation JSON, SVG, audit report,
  immutable archive, this record, latest handoff, and session-log append where safe.
- **Validation:** Python compilation passed; focused pytest returned `6 passed in 0.03s`; current
  exact-function reconstruction returned `FLAWED` with two findings; corrected fixture returned
  `VALIDATED` with zero findings; JSON and SVG parsing passed; Python lines are at most 100
  characters.
- **Evidence:** `docs/validation/mv3_chi2_support_validation.json`,
  `docs/validation/mv3_chi2_support.svg`, and
  `docs/validation/mv3_chi2_support_audit.md`.
- **Archive:**
  `chatgpt_todo/archive/2026-07-25T233022Z_AUD-MV3-SEL-003_CHI2_MODEL_SUPPORT.md`.
- **Focused status:** audit gate and evidence `VALIDATED`; current producer statistical contract
  `FLAWED`; cumulative weighted production and canonical closure `BLOCKED/PARTIAL`.
- **Scientific boundary:** no ROOT or beam-data file was rerun; no weighted profile, covariance,
  parameter scan, scattering/material correction, calibration, PID, closure, or detector-performance
  result is claimed. Canonical `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.
- **Next action:** correct `_chi2` to require a normalized profile and reject observed mass outside
  model support; add direct producer regressions; require the exact-source audit to return zero
  findings before any immutable production rerun.

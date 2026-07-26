# Active Task

- **Task ID:** `AUD-DELTAE-007`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T050335Z`
- **Initial remote main SHA:** `6c25424ae2507396d352d0b7e45d737752b2872d`
- **Scope:** prevent present malformed, missing-value, NaN, or infinite DeltaE signal cells from being
  silently converted to zero before stopping-layer, energy-sum, join, plotting, or result publication.
- **Policy:** `DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC`.
- **Implementation:** every present data `amp_B2/B4/B6/B8` and every present MC `edep_B*` cell must
  coerce to finite numeric input; only a wholly absent supported downstream column is zero-filled.
  The strict functions replace the retained core's production hooks, and result/manifest contracts
  publish both the signal-value and missing-layer policies.
- **Validation:** exact proposed Python compiled; focused tests returned `19 passed in 3.06s`; exact
  source audit returned `VALIDATED` with zero findings; malformed, NaN, both infinities, optional MC
  layers, missing columns, metadata, UTF-8, atomic-output, and alias controls passed; JSON/SVG parsing
  and line-length checks passed.
- **Evidence:**
  - `docs/validation/deltae_signal_value_contract_validation.json`
  - `docs/validation/deltae_signal_value_contract.svg`
  - `docs/validation/deltae_signal_value_contract_audit.md`
  - `chatgpt_todo/archive/2026-07-26T050335Z_AUD-DELTAE-007_SIGNAL_VALUE_INTEGRITY.md`
- **Focused acceptance:** canonical present-signal input boundary `VALIDATED / COMPLETE`.
- **Scientific boundary:** no exact A-002 table, amplitude convention, pulse polarity, stopping
  fraction, DeltaE-E PID, uncertainty, calibration, or detector-performance result is authorized.
- **Next action:** resolve `AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`, `AUD-AMP-010`, and
  `BLK-AMP-001`, then run a content-addressed production table through the full scientific gate.
- **Status:** `COMPLETE`

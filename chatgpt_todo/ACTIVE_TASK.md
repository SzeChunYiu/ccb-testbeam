# Active Task

- **Task ID:** AUD-MV3-SEL-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T230502Z
- **Initial remote main SHA:** `feddba9e3cc488fd77e7bc015f80af9d78f6edd1`
- **Scope:** remediate the merged MV3 selection-matched producer and source report after
  `AUD-MV3-SEL-001` confirmed fail-open MC weights, positive-charge-only selection,
  target-changing improvement arithmetic, and unsupported shape-closure wording.
- **Files changed:** `scripts/studies/mv3_selection_matched.py`,
  `tests/test_mv3_selection_weighted_contract.py`,
  `reports/studies/mv3_selection_matched/REPORT.md`, focused validation JSON/SVG/report and
  renderer, immutable archive, this record, and `HANDOFF.md`.
- **Correction:** exactly one finite nonnegative `PrimaryWeight` per event; canonical signed-charge
  selection; weighted primary plus unweighted sensitivity profiles; `sum_w`, `sum_w2`, ESS and
  zero-weight counts; one fixed Sample-I data target; full declared-input hashes; atomic JSON.
- **Validation:** prepared producer/test/renderer compilation passed; focused pytest returned
  `6 passed in 0.04s`; the exact committed test blob was reconstructed and returned the same result
  against the prepared producer; JSON and SVG parsing passed; prepared Python lines were at most 99
  characters. Exact remote producer-blob pytest was not available and is not claimed.
- **Evidence:** `docs/validation/mv3_selection_weighted_remediation_validation.json`,
  `docs/validation/mv3_selection_weighted_remediation.svg`, and
  `docs/validation/mv3_selection_weighted_remediation_audit.md`.
- **Archive:**
  `chatgpt_todo/archive/2026-07-25T230502Z_AUD-MV3-SEL-002_WEIGHTED_PRODUCER_REMEDIATION.md`.
- **Focused status:** software remediation and source-report quarantine `VALIDATED/PARTIAL`;
  production weighted result `BLOCKED`; cumulative MV3 closure `PARTIAL`.
- **Scientific boundary:** no ROOT or beam-data file was rerun; no weighted stopping profile,
  covariance, scattering/material correction, calibration, PID result, or detector-performance
  result is claimed. Canonical `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.
- **Next action:** run the corrected producer from an immutable commit on content-addressed inputs,
  require weights/ESS/covariance/fixed-target metrics and preregistered scans, regenerate all result
  artifacts, then obtain a zero-finding claim audit before any canonical/public upgrade.

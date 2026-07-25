# Active Task

- **Task ID:** AUD-LEDGER-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T080448Z
- **Initial remote main SHA:** `563582a0d7b1d3b0fac3e33cc241b4981a21912e`
- **Scope:** remediate canonical `CL-011` effective-live-time provenance, estimand,
  counts, uncertainty semantics, and validation status against tracked primary S10b
  artifacts.
- **Delivered:** exact 43-column row binding S10b value
  `124.79018394263471 ns`, run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`, 14 runs, and 252266 selected pulses.
- **Canonical semantics:** `data_measurement`, `DONE_DATA_ONLY`, validation not
  authorized, `BLK-S10B-001`; unsupported stat/syst/total components removed.
- **Validation:** exact-width CSV check passed; focused current-ledger regression
  returned `2 passed in 0.02s`; final ledger Git blob
  `254dc5b64945260193d6b1bd4146bd6400ad28cf` matches the validated candidate;
  JSON and SVG evidence parsed.
- **Publication correction:** an initial contents write transiently mistranscribed two
  unrelated P04p/P07e script/config paths. The candidate blob mismatch was detected,
  and commit `ab03023366396caaa97abc4cb7ea9a81aeae0731` restored those paths before
  further delivery work.
- **Evidence:** `docs/validation/tau_eff_claim_remediation_audit.md`,
  `tau_eff_claim_remediation_validation.json`, `tau_eff_claim_remediation.svg`, and
  immutable archive
  `chatgpt_todo/archive/2026-07-25T080448Z_AUD-LEDGER-003_TAU_EFF_REMEDIATION.md`.
- **Scientific boundary:** no raw ROOT reprocessing, fit rerun, new uncertainty,
  detector-wide dead time, accepted Rmax, calibration, or performance result.
- **Status:** PARTIAL. The canonical ledger row and regression are validated; exact
  public synchronization in WIKI, Chapter 1, and Chapter 5 remains open.

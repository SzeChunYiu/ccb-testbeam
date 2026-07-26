# Active Task

- **Task ID:** AUD-MV3-SEL-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-26T002131Z
- **Initial remote main SHA:** `54a899d82c1991747218a5b3a5a0835c51991420`
- **Transport branch:** `chatgpt/AUD-MV3-SEL-003-chi2-remediation-20260726T002131Z`
- **Transport PR:** `#933`
- **Validated implementation head:** `c9b20d0707b675c134ce8e6b0e804a115b569ae4`
- **Scope:** remediate the weighted MV3 producer's Pearson chi-square implementation after the
  validated support audit showed that positive observed mass at zero model expectation was silently
  omitted and nonunit model profiles were accepted.
- **Policy:**
  `PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`.
- **Implementation:** exact B2/B4/B6/B8 keys; finite nonnegative inputs; model normalization within
  absolute tolerance `1e-12`; positive observed total; rejection of observed mass outside model
  support; omission only of expected=observed=0 categories; supported-category ndf; `math.fsum`.
- **Provenance:** generated summaries record canonical front-door and preserved implementation byte
  counts and full SHA-256 digests from the snapshots used in execution.
- **Focused validation:** workflow `30181818650`, job `89739575951`, conclusion `success`; compilation,
  focused producer/audit regressions, zero-finding exact-source audit and line-length gate all passed.
- **Repository gate:** workflow `30181818642`, job `89739575939`, conclusion `failure`; ruff passed;
  pytest returned `42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s`; no candidate regression
  was listed among the failures.
- **Evidence:** `docs/validation/mv3_chi2_producer_remediation_validation.json`,
  `docs/validation/mv3_chi2_producer_remediation.svg`, and
  `docs/validation/mv3_chi2_producer_remediation_audit.md`.
- **Archive:**
  `chatgpt_todo/archive/2026-07-26T002131Z_AUD-MV3-SEL-003_CHI2_REMEDIATION_BLOCKED.md`.
- **Focused status:** implementation and focused gate `VALIDATED`; repository integration
  `BLOCKED`; remote-main delivery not completed.
- **Next action:** reconcile the 42 repository-wide failures without weakening the gate, update the
  candidate onto latest `main`, rerun both exact-head workflows, then merge only when all required
  checks pass and confirm the resulting commit on remote `main`.
- **Scientific boundary:** no ROOT or beam-data file was rerun; no weighted profile, covariance,
  sensitivity scan, material/scattering correction, calibration, PID, closure or detector-performance
  result is claimed. `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.

# Active Task

- **Task ID:** AUD-REP-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T190251Z
- **Initial remote main SHA:** `8ceda40d2f71d53a93bb02568c8e90509c973e0c`
- **Scope:** audit the new Cluster E synthesis dashboard for exact canonical
  claim binding, source separation, and content-addressed provenance.
- **Confirmed defects:** Cluster E substitutes the Cluster D `110 ADC/MeV`
  rerun for canonical `CL-013=92 ADC/MeV`; conflates the distinct MV3 rerun
  `86135.4707883642` with canonical `CL-021=68269.40598948313`; substitutes
  the MV6 toy `25/38` C12 subset for canonical `CL-022=283/87555`; and records
  an unbound `(worktree HEAD)` plus truncated and incomplete input digests.
- **Validated progress:** fail-closed validator, six focused regressions,
  machine-readable findings, SVG evidence, and audit report are committed
  directly to `main`.
- **Validation:** `python -m py_compile` passed; focused pytest returned
  `6 passed in 0.05s`; corrected fixture returned zero findings; malformed
  ledger width, invalid UTF-8, truncated digests, and atomic publication were
  covered; JSON and SVG parsing passed; changed Python lines are at most 100
  characters.
- **Current repository result:** `FLAWED` with 13 findings. This is the
  validated state of the current dashboard bundle, not a test failure to hide.
- **Unrun checks:** complete-checkout execution against all current repository
  paths, regeneration of Cluster E PNGs, repository-wide pytest/ruff, full link
  inventory, and GitHub Actions.
- **Scientific boundary:** software/documentation provenance only; no detector
  performance, data/MC transfer, precision calibration, C12 identity, or
  accepted stopping-profile closure was established.
- **Focused status:** VALIDATED audit gate and evidence.
- **Cumulative status:** PARTIAL until the generator derives canonical fields,
  separates rerun/toy diagnostics, emits full hashes, regenerates every derived
  artifact, and the exact current-repository validator returns `VALIDATED`.

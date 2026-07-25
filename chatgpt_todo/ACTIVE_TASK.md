# Active Task

- **Task ID:** AUD-CLD-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T170507Z
- **Initial remote main SHA:** `5367ec7bbf5f37989cd29eedd0700bd77542049b`
- **Scope:** review the newly merged Cluster D MV0–MV6 and single-stave campaign
  bundle, reconcile its public scientific statuses with exact tracked outputs and
  the canonical claim ledger, add a fail-closed regression gate, and retain
  reproducible visual/machine-readable evidence.
- **Confirmed defects:** MV0 was labelled production despite marginal KS, huge
  chi-square, per-stave mismatch, and unbound inputs; MV2 claimed absolute-energy
  closure from truth tables; MV5 treated a duty-factor product as accepted Rmax
  despite a null recovery-ceiling result; MV6 transferred a 25/38 truth-MC
  composition to beam-data identity; VIS-MC language called internal/toy plots
  proof that the simulation works.
- **Validated changes:** corrected Cluster D summary plus MV0/MV5/MV6 reports;
  policy `CLUSTERD_PUBLIC_STATUS_MUST_NOT_OVERRIDE_CANONICAL_CLAIM_GATES`;
  strict validator, focused regression tests, validation JSON, SVG renderer/output,
  and detailed audit report.
- **Validation:** exact corrected Markdown blobs matched the repo-shaped validation
  fixture; `py_compile` passed; focused pytest returned `6 passed in 1.63s`;
  corrected fixture returned `VALIDATED` with zero findings; stale wording,
  non-null failure-ceiling Rmax, invalid UTF-8, and output aliasing failed closed;
  JSON and SVG parsing passed.
- **Unrun check:** complete-checkout execution of the current-repository integration
  test was unavailable because the container could not resolve `github.com`.
  Repository-wide tests, lint, ROOT/Geant4, and broad CI are not claimed.
- **Scientific boundary:** documentation and source-binding only. No new data,
  simulation, gain calibration, absolute-energy closure, Rmax, PID performance, or
  beam-data anomaly identity was produced.
- **Focused remediation status:** VALIDATED.
- **Cumulative status:** PARTIAL pending external-input provenance and the open
  scientific blockers `BLK-MV0-001`, `S-STAT-003`, and `AUD-ANOM-001`.

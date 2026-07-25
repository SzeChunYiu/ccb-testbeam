# Active Task

- **Task ID:** AUD-G4-022
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T141517Z
- **Initial remote main SHA:** `48e3192dc69dd8c9408930171ed66f7a0627979e`
- **Scope:** correct the single-stave analyzer's generated-optical bookkeeping so
  the current normalized Geant4 contract preserves scintillation, WLS, and
  Cerenkov components and uses their exact total for arrival bounds and G4S-03.
- **Confirmed defect:** the former analyzer bounded `n_end_selected` by
  `n_scint_generated` and divided collection efficiency by that scintillation-
  only count, although the producer records additional WLS and Cerenkov optical
  tracks. A valid synthetic event gave former ratio `11/10 = 1.1` and correct
  total-optical ratio `11/15 = 0.7333333333333333`.
- **Validated work:** analyzer v2.0.0 now rejects partial or malformed current
  contracts, verifies the exact component sum, uses
  `n_optical_generated_total`, labels legacy input explicitly, and records the
  contract/denominator/components in result, summary, plot-source, and manifest
  outputs. Focused tests, documentation, JSON, SVG, audit, and immutable archive
  are present on `main`.
- **Validation:** `py_compile` passed; focused pytest `9 passed in 0.08s`; a
  120-row synthetic end-to-end run returned `PASS_SMOKE`,
  `CURRENT_COMPONENT_SUM`, and G4S-03 denominator
  `n_optical_generated_total`; JSON and SVG parsing passed; changed Python line
  length is at most 100 characters. Ruff was unavailable.
- **Scientific boundary:** synthetic software/provenance validation only; no
  Geant4 production event, immutable ROOT sample, calibration, optical yield,
  resolution, PID, or detector-performance quantity was generated or changed.
- **Remaining acceptance:** execute the adapter-to-analyzer path on immutable
  real current-ROOT bytes and record producer sidecar/commit, ROOT and normalized
  hashes, row-count closure, result/manifest hashes, and reviewed diagnostics.
- **Focused remediation status:** VALIDATED.
- **Cumulative status:** PARTIAL.

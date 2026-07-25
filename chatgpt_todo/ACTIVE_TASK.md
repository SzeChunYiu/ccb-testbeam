# Active Task

- **Task ID:** AUD-PID-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T131727Z
- **Initial remote main SHA:** `8cb0516e80f641d9f00d01d968ed0389ca48cac3`
- **Scope:** source-bind Chapter 8 proton/deuteron claims to the tracked MV1
  producer, summary, and exact-width canonical rows `CL-017` and `CL-018`.
- **Confirmed defects:** the former chapter mislabeled traditional-cut purity as
  AUC, described truth-MC row-index output as beam-data leave-one-run-out,
  promoted HGB point estimates as an irreducible performance ceiling, asserted
  untracked stopping-depth/combined-strategy results, and interpreted MV2
  kinetic-energy values without a bound branch-unit conversion.
- **Files:** `docs/academic_chapters/08_particle_id.md`,
  `tools/audit/validate_chapter8_mv1_claims.py`,
  `tests/test_validate_chapter8_mv1_claims.py`, validation Markdown/JSON/SVG,
  repository-local coordination ledgers, and immutable archive.
- **Validation plan:** strict UTF-8 and exact-byte provenance; exact 43-column
  ledger interpretation; exact source counts and metrics; source-contract and
  stale-claim regressions; `py_compile`; focused pytest; JSON and SVG parsing;
  changed-Python line-length gate; post-write blob and remote-main confirmation.
- **Scientific boundary:** documentation and source-contract validation only; no
  ROOT rerun, classifier retraining, beam-data PID measurement, uncertainty,
  range-energy closure, calibration, or detector-performance claim.
- **Status:** ACTIVE.

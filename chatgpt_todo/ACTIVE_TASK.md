# Active Task

- **Task ID:** AUD-G4-023
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T150441Z
- **Initial remote main SHA:** `9104fc1c0a6b1e3ce3323a08869444e1b68d6c16`
- **Scope:** audit whether the single-stave Geant4 event adapter's emitted
  metadata accurately describes the current analyzer after optical-bookkeeping
  remediation.
- **Confirmed defect:** adapter v1.0.0 still publishes
  `analysis_compatibility=SCHEMA_ADAPTER_ONLY` plus a downstream blocker saying
  the analyzer uses `n_scint_generated` alone. Current analyzer v2.0.0 instead
  validates `CURRENT_COMPONENT_SUM` and uses `n_optical_generated_total` as the
  arrival and G4S-03 collection-efficiency denominator.
- **Files inspected:** `adapt_geant4_events.py`, `analyze_single_stave.py`,
  `EVENT_CONTRACT.md`, focused tests, recent event-contract/analyzer history,
  open PRs, PR #868, current CI status, backlog, handoff, and session log.
- **Validated work:** added a strict fail-closed metadata consistency auditor,
  focused regression tests, machine-readable JSON, SVG evidence, and an audit
  report. The corrected fixture validates with zero findings; the current-like
  fixture fails closed with the stale compatibility/blocker findings.
- **Validation:** `py_compile` passed; focused pytest returned
  `6 passed, 1 skipped in 1.96s`; invalid UTF-8, stale metadata, analyzer
  denominator mutation, missing contract statements, atomic JSON, and output
  aliasing are covered; JSON/SVG parsing passed; Python lines are at most 100
  characters.
- **Scientific boundary:** software/documentation provenance only. No immutable
  real ROOT file, Geant4 event, optical yield, calibration, resolution, PID, or
  detector-performance quantity was generated or changed.
- **Remaining acceptance:** update adapter metadata/version, remove the obsolete
  downstream blocker, add an exact CLI regression, and require the exact-current
  source audit to return `VALIDATED`; real ROOT end-to-end closure remains a
  separate gate.
- **Focused audit-gate status:** VALIDATED.
- **Current adapter metadata status:** FLAWED.
- **Cumulative status:** PARTIAL.

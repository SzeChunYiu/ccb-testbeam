# Active Task

- **Task ID:** AUD-G4-023
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T160331Z
- **Initial remote main SHA:** `1e284f8109e927aea67d0eaf2246477982a6dcc7`
- **Scope:** remediate the single-stave Geant4 adapter metadata so it accurately
  describes the current analyzer optical-bookkeeping contract, and correct the
  audit gate discovered to be whitespace-sensitive.
- **Confirmed defects:** adapter v1.0.0 published `SCHEMA_ADAPTER_ONLY` and a
  completed-work blocker; audit v1.0.0 rejected the exact wrapped
  `EVENT_CONTRACT.md` wording through literal substring matching.
- **Validated changes:** adapter v1.1.0 / metadata schema 2, explicit analyzer
  contract, stale blocker removal, retained real-ROOT boundary, whitespace-
  normalized audit v1.1.0, exact CLI assertions, current-source audit regression,
  machine-readable JSON, SVG evidence, and audit report.
- **Validation:** focused `py_compile` passed; focused pytest returned
  `20 passed, 1 skipped in 3.77s`; exact metadata audit returned `VALIDATED`
  with zero findings; JSON and SVG parsing passed; Python lines are at most 100
  characters.
- **Scientific boundary:** software/provenance only. No immutable real ROOT file,
  Geant4 event, optical yield, calibration, resolution, PID, or detector-
  performance quantity was generated or changed.
- **Focused remediation status:** VALIDATED.
- **Cumulative status:** PARTIAL pending immutable real-ROOT end-to-end closure.

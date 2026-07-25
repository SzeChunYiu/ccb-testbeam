# Active Task

- **Task ID:** AUD-G4-022
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T133443Z
- **Initial remote main SHA:** `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- **Scope:** bind the current single-stave Geant4 `events` tree to an explicit,
  fail-closed normalized analysis contract and correct public documentation that
  implied direct analyzer compatibility and an implemented fast mode.
- **Confirmed defects:** current `RunAction.cc` writes `arrival_readout`,
  `detected_readout`, and `track_len_scint_mm`, while the analyzer expects
  different names/units; the analyzer's arrival bound ignores separately
  recorded WLS and Cerenkov optical tracks; the Geant4 README advertised direct
  analysis and a fast mode that the CLI rejects.
- **Validated work:** explicit converter, source-bound focused tests, contract
  documentation, corrected Geant4 README, machine-readable JSON, SVG evidence,
  and audit report are present on `main`.
- **Validation:** `py_compile` passed; focused pytest `12 passed in 1.59s`; JSON
  and SVG parsing passed; changed Python line length is at most 95 characters.
- **Scientific boundary:** synthetic software/provenance validation only; no
  Geant4 production event, ROOT sample, calibration, optical yield, resolution,
  or detector-performance quantity was generated or reinterpreted.
- **Remaining acceptance:** update `analyze_single_stave.py` to consume the
  component and total optical counters without semantic renaming, add an
  integrated current-ROOT regression, and execute on immutable real ROOT bytes.
- **Status:** PARTIAL.

# Active Task

- **Task ID:** AUD-MERGE-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T224320Z
- **Initial remote main SHA:** `1e99395ee2bdf0907f82782e5b2b0b2680a3c90f`
- **Latest validated evidence head:** `2dcbbdc86450707c0d6d8c1d3fe5ccc0c57e5fa1`
- **Scope:** map the validated implementation from closed PR #868 to current `main`, correct the contradictory single-stave known-issues document, add a fail-closed source/status validator, focused regressions, machine-readable evidence, and visual evidence without merging the stale branch.
- **Completed:** six PR #868 scientific scripts/tests are exact blob matches on current `main`; RNG/thread configuration and provenance are current-main semantic supersets; the MC validation workflow covers those paths; `KNOWN_ISSUES.md` now matches the repository-recorded Geant4 11.2.2 runtime evidence and retains calibration/stopping-power boundaries.
- **Validation:** Python compilation passed; focused pytest returned `5 passed in 0.05s`; the exact former known-issues text returned `FLAWED` with 19 findings and status 1; corrected files returned `VALIDATED` with zero issues; JSON and SVG parsing passed; changed Python lines are at most 97 characters.
- **Scientific boundary:** this validates repository integration and documentation consistency. It does not independently rerun Geant4 or inspect the original ROOT files, and it does not establish detector calibration, PE/MeV transfer, stopping-power closure, or beam-data agreement. `BLK-G4-SP-001` remains open.
- **Remaining primary action:** publish the already validated exact root-WIKI MV3 candidate from the previous `AUD-WIKI-001` handoff through a byte-safe complete-file write, then rerun its source/ledger/WIKI and link gates against remote bytes.
- **Status:** COMPLETE — PR #868 requires no stale-branch merge for the mapped validated implementation; current-main status documentation and fail-closed evidence are delivered.

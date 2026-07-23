# Active Task

- **Task ID:** AUD-CI-002
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T09:06:39Z
- **Base main SHA:** `345d82d1daccbe1d8eafcf525ab51fd19ab20832`
- **Scope:** restore the current-main amplitude-audit unit-test gate without changing scientific interpretation or weakening fail-closed amplitude authorization.
- **Confirmed findings:** the missing-pedestal warning was renamed in production code but one regression still asserted the obsolete name; the aggregate invalid-baseline counter inspected evidence-gated `physics_acceptance`, so a no-evidence heuristic ABSOLUTE table with incomplete pedestal values was omitted despite `convention_acceptance=BASELINE_DATA_INVALID`.
- **Files reviewed:** `tools/audit/amplitude_convention_audit.py`, `tests/test_amplitude_convention_audit.py`, `tests/test_amplitude_baseline_data_quality.py`, PR #884, Actions run `29993563323`, PR #868, open PR inventory, and required `chatgpt_todo/` records.
- **Validated change:** synchronize the test with `AMPLITUDE_CONVENTION_WITHOUT_BASELINE_LEVEL`; count non-NET rows whose unconditional convention state is `BASELINE_DATA_INVALID`; retain the convention-specific physics gate that allows hash-authorized NET input to ignore optional incomplete pedestal diagnostics.
- **Validation:** PR #884 changed only two files by four additions and two deletions. MC Validation CI run `29993563323`, job `89161772967`, completed successfully on head `9750d0fddc626a76f0c954fa09065db05ac83f32`. The reviewed head was squash-merged into `main` as `4f857f508160bbbe059d936866b426a45788c9bd`, and the resulting main files were re-read to confirm both exact changes.
- **Boundary:** no raw data, pulse table, simulation, plot, calibration, stopping count, or detector-performance result changed. No Geant4/ROOT validation is inferred from this Python CI repair.
- **Status:** COMPLETE — validated PR transport is present on remote `main`; current-main CI regression is repaired. Active scientific A-002 regeneration remains blocked under `BLK-AMP-001`.

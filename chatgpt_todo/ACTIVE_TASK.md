# Active Task

- **Task ID:** AUD-G4-007
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T11:06:11Z
- **Initial main SHA:** `9dc4005dd030e78d2523d8094fa16adffcfc0bd1`
- **Implementation/evidence head:** `00dd74cda709a7f5c6489721f3c96077136b40e5`
- **Scope:** independently review whether the PR #890 stopping-power diagnostic validates every committed PSTAR CSV row before interpolation and tolerance reporting.
- **Confirmed defect:** the legacy parser silently skipped missing or nonnumeric rows, sorted surviving rows, and accepted duplicate/out-of-order energies plus nonfinite or nonphysical stopping values. A malformed middle row could disappear and the CLI could still print a numerical PASS.
- **Validated change:** require all columns and rows, finite physical values, strictly increasing declared energies, and at least two rows; malformed references raise `StoppingPowerInputError`, return CLI status 2, and print no numerical PASS.
- **Files:** `scripts/single_stave/compare_stopping_power.py`, `tests/test_compare_stopping_power_reference_integrity.py`, and `docs/validation/stopping_power_reference_integrity_*`.
- **Commands:** `python -m py_compile` over the stopping-power script and three focused test modules; focused pytest over reference-path, reference-domain, and reference-integrity tests; changed-file line-length and JSON/SVG parse checks.
- **Validation:** the exact pre-change blob `0436fb390476697cfc83f88208322a99d7792a1c` produced six expected regression failures; the corrected focused suite returned `14 passed in 2.94s`; committed script blob `7c3c05f12a1311d5ead8d1d45e0f5fea91dc92ce` matches the validated file.
- **Boundary:** this validates local reference-table structure and fail-closed parsing only. It does not verify the NIST source transcription, Geant4 stopping-power physics, deuteron scaling, real simulation output, calibration, or detector performance.
- **Status:** COMPLETE for PSTAR reference-integrity handling and direct-to-main delivery; PARTIAL for scientific stopping-power closure under `AUD-G4-005` / `BLK-G4-SP-001`.

# Active Task

- **Task ID:** AUD-G4-017
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T213126Z
- **Initial remote main SHA:** `5b6907d646527078c45ec615e0153f977f3214c5`
- **Validated implementation/evidence head:** `1d7e44a23516617b0ec9cf7deac27b052944b925`
- **Scope:** make stopping-power CSV reports independently reconstructable by recording the central-value sufficient statistics and numerical configuration used by the diagnostic.
- **Confirmed defect:** the report exposed derived stopping power, ratio, and status but omitted summed deposited energy, summed track length, material density, tolerance percentage, and estimator identity. Different density or tolerance settings could therefore change values/status without appearing in the machine-readable report.
- **Validated change:** record `deposit_sum_MeV`, `track_length_sum_mm`, `material_density_g_cm3`, `tolerance_percent`, and `mass_stopping_estimator=RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED` in every result/CSV row; print the estimator in terminal output; preserve round-trip float serialization and all prior fail-closed gates.
- **Commands:** focused `py_compile`; focused pytest for report precision and report reproducibility; exact pre-change Git-blob reconstruction and negative control; JSON/SVG parsing; line-length and Git-blob checks.
- **Validation:** `5 passed in 0.07s`; exact old blob `5081da0...` produced `2 failed in 0.11s`; changed Python lines are at most 93 characters; generated JSON and SVG parsed.
- **Evidence:** `docs/validation/stopping_power_report_reproducibility_audit.md`, `stopping_power_report_reproducibility_validation.json`, and `stopping_power_report_reproducibility.svg`.
- **Boundary:** the report is numerically self-describing, but no uncertainty budget, real Geant4 export, accepted projectile-energy-loss observable, calibration, or detector-performance result was produced.
- **Status:** COMPLETE for `AUD-G4-017`; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

# Active Task

- **Task ID:** AUD-G4-016
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T210542Z
- **Initial remote main SHA:** `5c64e283594f1ef23d0685eac7b8249d45f1670b`
- **Validated implementation/evidence head:** `cff8a9f076f334333e938444a34168e4643f1e5f`
- **Scope:** prevent six-significant-digit report serialization from destroying the identity of exact configured-energy comparison points and other floating-point results.
- **Confirmed defect:** exact-energy grouping retained distinct floats `1.0000001` and `1.0000002`, but CSV `.6g` serialization wrote both as `1` and the terminal table printed both as `1.00`, making downstream reconstruction and visual distinction impossible.
- **Validated change:** use Python round-trip `repr` for every finite float in the CSV, reject nonfinite output, record `PYTHON_REPR_ROUND_TRIP`, and print configured energies with the same round-trip representation.
- **Commands:** focused `py_compile`; focused pytest; exact pre-change Git-blob reconstruction and negative control; JSON/SVG parsing; line-length and Git-blob checks.
- **Validation:** `3 passed in 0.03s`; exact old blob `c3884d9...` produced `2 failed, 1 passed`; changed Python lines are at most 93 characters; generated JSON and SVG parsed.
- **Evidence:** `docs/validation/stopping_power_report_precision_audit.md`, `stopping_power_report_precision_validation.json`, and `stopping_power_report_precision.svg`.
- **Boundary:** serialization identity is corrected, but no uncertainty budget, real Geant4 export, accepted projectile-energy-loss observable, calibration, or detector-performance result was produced.
- **Status:** COMPLETE for `AUD-G4-016`; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

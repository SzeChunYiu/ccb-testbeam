# Active Task

- **Task ID:** AUD-G4-020
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-24T001355Z
- **Initial remote main SHA:** `b8e83fa39209d5e627c3e5c15834a10f80fcbcd2`
- **Validated tool/test/evidence head:** `81c02634e36a7111a9fe9f15d496203bf8c0e74f`
- **Scope:** prevent an arithmetic mean across distinct stopping-power energy points from masquerading as a combined closure estimate when per-point uncertainty, covariance, weighting, and a combined measurand are undefined.
- **Confirmed defect:** `compare_stopping_power.py` prints `statistics.mean(ratios)` as `mean point-estimate ratio [species]` across distinct configured energies even though every point records `uncertainty_method=NOT_EVALUATED`.
- **Validated progress:** added a fail-closed source audit, four focused tests, Markdown/JSON evidence, and an accessible SVG demonstrating why a cross-energy mean is unsupported.
- **Commands:** focused `py_compile`; `pytest`; SVG XML parse; changed-file line-length checks; authenticated GitHub inspection of the exact current source blob.
- **Validation:** `4 passed in 0.03s`; tool maximum line length 90; test maximum line length 81; SVG parsed successfully.
- **Evidence:** `docs/validation/stopping_power_cross_energy_summary_audit.md`, `stopping_power_cross_energy_summary_validation.json`, and `stopping_power_cross_energy_summary.svg`.
- **Boundary:** the audit gate is validated, but the canonical reporter still emits the unsupported mean. No real Geant4 export, uncertainty budget, or accepted stopping-power closure was produced.
- **Status:** PARTIAL / FLAWED canonical behavior; next action is to remove the mean from `compare_stopping_power.py`, emit only individual points plus descriptive bounds, and integrate this audit into regression/CI.

# Active Task

- **Task ID:** AUD-G4-020
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-24T011158Z
- **Initial remote main SHA:** `6460d5f1479163d000d9fbbe260ba4e3ce0db7d7`
- **Validated code/test/evidence head:** `6ef9962fe8c5795d862728ad4d02c47138efc14f`
- **Scope:** remove the unsupported arithmetic mean across distinct stopping-power energies and make the no-combination policy explicit in terminal and machine-readable reports.
- **Corrected behavior:** the canonical reporter retains each exact energy point, emits only descriptive minimum/maximum point-estimate bounds labelled `no combined estimate`, removes the `statistics.mean` path, and records `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL` in every result and CSV row.
- **Validation:** exact committed source/test Git blobs matched locally validated files; focused `py_compile`; `6 passed in 0.04s`; source audit returned `VALIDATED`; JSON and SVG parsed; changed Python lines were at most 91 characters.
- **Evidence:** `docs/validation/stopping_power_cross_energy_remediation_audit.md`, `stopping_power_cross_energy_remediation_validation.json`, and `stopping_power_cross_energy_remediation.svg`.
- **Boundary:** no uncertainty model, covariance, real Geant4 export, total-energy-loss closure, or Geant4/PSTAR agreement was produced. Descriptive bounds are not an accepted combined estimate.
- **Status:** COMPLETE for removal of the unsupported cross-energy mean; broader stopping-power physics closure remains blocked separately.

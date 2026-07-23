# Active Task

- **Task ID:** AUD-G4-013
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T190130Z
- **Initial remote main SHA:** `d880c7474b2ba3f981fa6e402d1723d1c450e22d`
- **Concurrent main observed before first write:** `6fd458150fd7f7eff1be044c40b0675031935547`
- **Validated implementation/evidence head:** `2a29ffcfc0f645cede8b7ef621b1f17ac57a6bb7`
- **Scope:** prevent distinct configured simulation energies from being silently coalesced before the stopping-power diagnostic compares them with the energy-dependent PSTAR reference.
- **Confirmed defect:** aggregation used `(particle, round(energy_MeV, 1))`; synthetic 1.01 and 1.04 MeV events became one pooled point at 1.025 MeV, changing both the simulation statistic and reference lookup without an explicit binning contract.
- **Validated change:** aggregation keys on the exact validated numeric energy; numerically identical tokens still group; result rows, CSV output, and CLI report `EXACT_CONFIGURED_ENERGY`.
- **Commands:** exact pre-change Git-blob reconstruction; old-regression run; focused `py_compile`; combined pytest over grouping, range, simulation-input integration, PSTAR-component integration, and quenched-proxy modules; JSON/SVG parsing; SHA-256 and line-length checks.
- **Validation:** exact old blob produced `2 failed, 1 passed in 0.57s`; corrected focused suite produced `19 passed in 3.22s`; JSON and SVG parsed; changed Python lines are at most 91 characters.
- **Evidence:** `docs/validation/stopping_power_energy_grouping_audit.md`, `stopping_power_energy_grouping_validation.json`, and `stopping_power_energy_grouping.svg`.
- **Boundary:** this validates numerical grouping and provenance only; no real event table, Geant4 execution, accepted projectile-energy-loss closure, or detector-performance result was produced.
- **Status:** COMPLETE for `AUD-G4-013`; `AUD-G4-011` real-export execution and `AUD-G4-005` accepted physics closure remain PARTIAL.

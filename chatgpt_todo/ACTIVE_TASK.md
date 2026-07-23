# Active Task

- **Task ID:** AUD-G4-015
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T202812Z
- **Initial remote main SHA:** `905a83ce1723b10dafab46887a76aa48378f2234`
- **Validated implementation/evidence head:** `08f615f6b6edefa363eee086930e1eb0867474bb`
- **Scope:** prevent a stopping-power point estimate inside an arbitrary percentage tolerance from masquerading as accepted agreement when no uncertainty has been evaluated.
- **Confirmed defect:** a one-event direct-proton synthetic ratio of exactly 1.0 set `within_tolerance=true`, printed `NUMERICAL TOLERANCE: PASS`, and returned status 0 despite having no statistical or systematic uncertainty model. Forty repeated identical rows produced the same acceptance.
- **Validated change:** retain the numerical point-estimate diagnostic, but record `uncertainty_method=NOT_EVALUATED`, `uncertainty_evaluated=false`, explicit acceptance state, `within_tolerance=false`, row status `POINT_ONLY`, non-accepting CLI status 1, and an arithmetic-only self-test boundary.
- **Commands:** focused `py_compile`; focused pytest over uncertainty, energy grouping, quenched proxy, PSTAR component provenance, and deuteron proxy modules; exact old-blob regression; JSON/SVG parsing; line-length and hash checks.
- **Validation:** `19 passed in 3.77s`; the new four-test module produced `4 failed` against exact pre-change blob `8b9c0c...`; JSON and SVG parsed; maximum changed Python line length is 97 characters.
- **Evidence:** `docs/validation/stopping_power_uncertainty_gate_audit.md`, `stopping_power_uncertainty_gate_validation.json`, and `stopping_power_uncertainty_gate.svg`.
- **Boundary:** no uncertainty budget, real Geant4 event table, projectile-energy-loss closure, calibration, or detector-performance result was produced. A future accepted result requires preregistered statistical/systematic uncertainty and an accepted physics observable.
- **Status:** COMPLETE for `AUD-G4-015`; real-export execution and accepted physics closure remain PARTIAL/BLOCKED.

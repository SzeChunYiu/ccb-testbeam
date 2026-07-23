# Active Task

- **Task ID:** AUD-G4-014
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T201905Z
- **Initial remote main SHA:** `f147160f2c3be0df59f45c77cf209d2982547d04`
- **Validated implementation/evidence head:** `b24260118f25d1d36fbee118fb4ed1891377ef6c`
- **Scope:** prevent the deuteron `E/2` proton-PSTAR approximation from masquerading as a direct, accepting deuteron stopping-power reference.
- **Confirmed defect:** raw deuteron rows could use proton PSTAR at half energy, satisfy the numerical tolerance, set `within_tolerance=true`, print `NUMERICAL TOLERANCE: PASS`, and return status 0 even though PSTAR is a proton reference and the equal-velocity mapping was not independently validated for polystyrene.
- **Validated change:** deuteron input fails closed by default; explicit `--allow-deuteron-proxy` produces labelled non-accepting diagnostics; results and CSVs record reference basis, direct-reference comparability, and overall physics comparability; the self-test now uses protons only.
- **Commands:** focused `py_compile`; focused pytest over deuteron-proxy, energy-range, and quenched-proxy modules; exact Git-blob checks; JSON/SVG parsing; changed-file SHA-256 and line-length checks.
- **Validation:** `9 passed in 5.78s`; JSON and SVG parsed; exact changed-file Git blobs matched; maximum changed Python line length is 91 characters.
- **Evidence:** `docs/validation/stopping_power_deuteron_proxy_audit.md`, `stopping_power_deuteron_proxy_validation.json`, and `stopping_power_deuteron_proxy.svg`.
- **Boundary:** this validates fail-closed reference-basis authorization only; no real event table, deuteron-specific polystyrene reference, Geant4 execution, accepted projectile-energy-loss closure, calibration, or detector-performance result was produced.
- **Status:** COMPLETE for `AUD-G4-014`; `AUD-G4-011` real-export execution and `AUD-G4-005` accepted physics closure remain PARTIAL.

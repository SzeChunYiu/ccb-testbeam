# Active Task

- **Task ID:** AUD-G4-006
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T10:29:57Z
- **Initial observed main SHA:** `6d1d982e0eb6764cc3cc036aa1df76b8f3fe35c7`
- **Concurrent main incorporated:** `9521eca866a42a02d17a26dffbaaf0f21d6d8eb7`
- **Scope:** independently review whether the PR #890 stopping-power diagnostic uses the committed PSTAR reference only inside its supported energy domain.
- **Confirmed defect:** `interp_loglog()` silently clamped lookup energies below or above the table to an endpoint. Unsupported simulation energies could therefore reuse an unrelated edge value and potentially pass the numerical tolerance. Deuteron beam energy maps to proton-equivalent `E/2`, so the transformed lookup also requires an explicit range gate.
- **Validated change:** require finite positive lookup energy, accept exact endpoints, reject extrapolation, report proton-equivalent lookup and table bounds, return CLI status 2 without a numerical PASS, and add focused regression plus Markdown/JSON/SVG evidence.
- **Files:** `scripts/single_stave/compare_stopping_power.py`, `tests/test_compare_stopping_power_energy_range.py`, and `docs/validation/stopping_power_reference_domain_*`.
- **Commands:** `python -m py_compile scripts/single_stave/compare_stopping_power.py tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py`; focused pytest over the two stopping-power test modules; changed-file line-length scan; JSON and SVG parse checks.
- **Validation:** exact pre-change reconstruction matched Git blob `d9282a5c26b8bc86427356f51dfe7e5ecba769d8`; focused suite returned `7 passed in 1.15s`; committed script/test blobs match the validated local files.
- **Boundary:** this is a reference-domain and failure-mode correction only. No Geant4 executable, ROOT file, real simulation, accepted stopping-power closure, calibration, or detector-performance result was generated.
- **Status:** COMPLETE for fail-closed reference-domain handling and remote-main delivery; PARTIAL for scientific stopping-power closure under `AUD-G4-005` / `BLK-G4-SP-001`.

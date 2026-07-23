# Active Task

- **Task ID:** AUD-G4-004
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T10:04:54Z
- **Initial main SHA:** `5a4bdfc3f0099f2b6e8c3891b5a2a05f57ecf770`
- **Scope:** independently review the PR #890 PSTAR comparison entry point, reference-data path, self-test provenance, and scientific interpretation.
- **Confirmed defect:** `scripts/single_stave/compare_stopping_power.py` used `HERE.parents[2]`, which resolves one directory above the repository for a script under `scripts/single_stave`. Its self-test silently substituted an inline table, so a zero exit status did not exercise the committed PSTAR CSV.
- **Validated change:** resolve the default from `HERE.parents[1]`, fail closed when the selected reference is absent, print its path/SHA-256/row count, remove the inline fallback, and label the deposited-energy ratio as `DIAGNOSTIC_ONLY` rather than accepted stopping-power closure.
- **Files:** `scripts/single_stave/compare_stopping_power.py`, `tests/test_compare_stopping_power_reference_path.py`, and `docs/validation/stopping_power_reference_path_*`.
- **Commands:** `python -m py_compile scripts/single_stave/compare_stopping_power.py tests/test_compare_stopping_power_reference_path.py`; `python -m pytest tests/test_compare_stopping_power_reference_path.py -q`; changed-file line-length scan.
- **Validation:** focused local reconstruction returned `3 passed in 0.55s`; the committed script blob is `d9282a5c26b8bc86427356f51dfe7e5ecba769d8` and the committed test blob is `ab6265ef398ac0ad7cf3110d173c85cbd6d8f987`.
- **Boundary:** the local run used a minimal reference fixture containing the five PSTAR points exercised by the self-test because a complete checkout was unavailable. No Geant4/ROOT execution or accepted stopping-power closure is claimed. Local energy deposit is not automatically projectile total energy loss; deuteron velocity scaling remains approximate.
- **Status:** COMPLETE for reference selection, fail-closed self-test behavior, provenance output, regression coverage, and remote-main delivery; PARTIAL for scientific stopping-power closure (`AUD-G4-005`).

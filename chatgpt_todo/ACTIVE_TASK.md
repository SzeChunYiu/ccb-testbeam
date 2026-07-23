# Active Task

- **Task ID:** AUD-G4-008
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T12:14:45Z
- **Initial main SHA:** `9681e44d94fa825bb8db6c84af31448df0ec0689`
- **Implementation/evidence head:** `eb8791bd795d11a101d72a5d383a60baf0e19606`
- **Scope:** independently review whether the PR #890 stopping-power diagnostic can accept quenched visible-energy output as if it were unquenched energy loss comparable with raw PSTAR total stopping power.
- **Confirmed defect:** the legacy reader silently fell back from `edep_scint_raw_MeV` / `edep_raw_MeV` to quenched `edep_scint_MeV` / `edep_MeV` after a warning, then passed the value through the same tolerance gate. A one-row quenched-only synthetic table produced ratio `1.0` and `within_tolerance=True`.
- **Validated change:** reject quenched-only input by default; permit it only through `--allow-quenched-proxy` as explicitly labelled, non-accepting diagnostic output; reject mixed raw/quenched semantics; record the deposit basis, raw-PSTAR comparability, arithmetic-only tolerance, and accepted tolerance separately.
- **Files:** `scripts/single_stave/compare_stopping_power.py`, `tests/test_compare_stopping_power_quenched_proxy.py`, and `docs/validation/stopping_power_quenched_proxy_*`.
- **Commands:** `python -m py_compile` over the stopping-power script and four focused test modules; focused pytest over reference path, reference domain, reference integrity, and quenched-proxy semantics; changed-file line-length plus JSON/SVG parse checks.
- **Validation:** the exact pre-change fallback path was reproduced with a quenched-only ratio `1.0` accepted by the old tolerance gate; the corrected focused suite returned `18 passed in 2.86s`; committed script blob `ef535a47ee36b2706f6b720f0231648c23bc11a7` and test blob `af282789ce2e47ba680fa29296cdb81a7c45287f` match the validated files.
- **Boundary:** this validates energy-deposit convention handling and fail-closed acceptance only. It does not verify the NIST transcription, Geant4 stopping-power physics, particle energy evolution, secondary escape, deuteron scaling, real simulation output, calibration, or detector performance.
- **Status:** COMPLETE for the quenched-proxy acceptance gate and direct-to-main delivery; PARTIAL for scientific stopping-power closure under `AUD-G4-005` / `BLK-G4-SP-001`.

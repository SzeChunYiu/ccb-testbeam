# Active Task

- **Task ID:** `ARU-S00-SELECTOR-PREFLIGHT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T060000Z`
- **Initial remote main SHA:** `f2fb7dc24f38c838d1d30b4a6137bb6444c93180`
- **Main after validated merge this session:** `9883d96a63d779548f76a7d5cdef2170e507d2c0` (PR #1142)
- **Issue:** `#1141`
- **Parent:** `#1135`
- **Upstream scientific parent:** `#1109`
- **Branch:** `fix/s00-selector-preflight-manifest`
- **Selected atom:** `YAML selector declaration -> no-I/O semantic preflight -> publication namespace -> staging -> ROOT access -> selector execution -> manifest identity -> CL-001 provenance`.
- **Contract:** canonical S00 is `selector_id=v1_first_four_median` with `baseline_indices=(0,1,2,3)` and a semantic mismatch must fail before staging or ROOT access.
- **Implemented this session:** pure `validate_s00_selector_contract(config)` plus exact selector manifest-identity fragment and hostile deterministic tests.
- **Expert votes:** reconstruction/software `ACCEPT pure leaf / BLOCK integration`; adversarial `REVISE`; statistics/validation `ACCEPT unit design / BLOCK producer claim`; claims/provenance `BLOCK CL-001 promotion`.
- **Residual integration:** canonical `main()` must call preflight immediately after YAML parsing; hostile end-to-end test must prove zero ROOT opens/raw iteration/staging/artifact writes; manifest must include selector ID + exact baseline tuple.
- **Scientific boundary:** no raw beam data or Geant4 run; no selected-pulse count or detector-performance result changed. Physical validity of samples 0-3 remains #1109.
- **Status:** `ACTIVE / PARTIAL`

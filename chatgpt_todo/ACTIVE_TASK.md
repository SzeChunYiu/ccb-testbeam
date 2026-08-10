# Active Task

- **Task ID:** `ARU-S00-SELECTOR-PREFLIGHT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T060000Z`
- **Initial remote main SHA:** `f2fb7dc24f38c838d1d30b4a6137bb6444c93180`
- **Main after validated merge this session:** `9883d96a63d779548f76a7d5cdef2170e507d2c0` (PR #1142)
- **Issue:** `#1141`
- **Parent:** `#1135`
- **Upstream scientific parent:** `#1109`
- **Branch / PR:** `fix/s00-selector-preflight-manifest` / `#1143`
- **Selected atom:** `YAML selector declaration -> semantic authorization -> publication namespace -> staging -> ROOT access -> selector execution -> manifest identity -> CL-001 provenance`.
- **Contract:** canonical S00 is `selector_id=v1_first_four_median` with `baseline_indices=(0,1,2,3)` and a mismatch must fail before staging or ROOT access.
- **Implemented:** pure selector-config contract, immediate producer preflight after YAML parsing, explicit selector ID + baseline tuple in manifest `model_identity`, hostile config/domain tests, and an end-to-end side-effect sentinel proving the failure path cannot reach namespace resolution, raw scan/iteration, `uproot.open`, staging `mkdir`, manifest writes, or figure writes.
- **Audit-the-audit:** the first producer edit unintentionally changed sensitivity-report fallback semantics. Diff review detected that unrelated change; the script edit was fully reverted and then reapplied surgically. Current script diff contains only selector-contract import/preflight/model-identity changes.
- **Expert votes:** reconstruction/software `ACCEPT implementation / pending CI`; adversarial `ACCEPT after surgical reapply / pending CI`; statistics/validation `ACCEPT deterministic test design / pending exact-head CI`; claims/provenance `ACCEPT selector binding / CL-001 remains GATED`.
- **Exact-head gate:** PR #1143 head `a01b7e887215b1dcbe277fe696e12116722aef3a`; MC Validation CI run 898 is in progress. Do not merge or close #1141 before exact-head success.
- **Scientific boundary:** no raw beam data or Geant4 run; no selected-pulse count or detector-performance result changed. Physical validity of samples 0-3 remains #1109. Publication transaction #1110 remains separate.
- **Status:** `ACTIVE / IMPLEMENTED_PENDING_CI`

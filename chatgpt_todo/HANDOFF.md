# Latest Handoff

## Session

- **Task ID:** `ARU-S00-SELECTOR-PREFLIGHT-001`
- **Stamp:** `2026-08-10T060000Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial main:** `f2fb7dc24f38c838d1d30b4a6137bb6444c93180`
- **Validated merge during session:** PR #1142 -> `9883d96a63d779548f76a7d5cdef2170e507d2c0`
- **Issue:** #1141
- **Parent:** #1135
- **Upstream scientific parent:** #1109
- **Branch / PR:** `fix/s00-selector-preflight-manifest` / #1143
- **Status:** `IMPLEMENTED_PENDING_EXACT_HEAD_CI`.

## Selected atom

`YAML selector declaration -> semantic authorization -> namespace/staging -> ROOT access -> selector execution -> manifest identity -> CL-001 provenance`.

Canonical selector identity is fixed by merged #1142:

```text
selector_id = v1_first_four_median
baseline_indices = (0,1,2,3)
```

## Work completed

1. Verified exact-head MC Validation CI for PR #1142 was `success` and squash-merged it to main as `9883d96a63d779548f76a7d5cdef2170e507d2c0`.
2. Added pure `validate_s00_selector_contract(config)` and `s00_selector_model_identity()` in `src/ccb_mc_validation/s00_selector_contract.py`.
3. Patched the canonical producer so the selector contract is checked immediately after YAML parsing, before amplitude-cut/namespace resolution, staging, raw-file traversal, or ROOT access. Failure returns controlled input status 2.
4. Bound `selector_id` and exact `baseline_indices` into manifest `model_identity`.
5. Added hostile deterministic config/domain tests plus a producer-level side-effect sentinel proving a bad selector cannot reach namespace resolution, raw scan, raw iteration, `uproot.open`, staging `mkdir`, manifest writes, or figure writes.
6. Preserved the ARU reasoning in `chatgpt_todo/archive/2026-08-10T060000Z_ARU-S00-SELECTOR-PREFLIGHT-PARTIAL.md`.

## Audit-the-audit correction

The first producer integration attempt accidentally altered unrelated `write_sensitivity_report()` fallback semantics. Adversarial per-file diff review detected that spillover before merge. The script change was fully reverted and then reapplied surgically. The current PR script diff is limited to selector-contract imports, the immediate preflight, and selector identity fields in `model_identity`.

## Four sequential review passes

- **Reconstruction/software lead — ACCEPT implementation / pending CI.** The producer now places semantic authorization before side effects.
- **Adversarial mechanism reviewer — ACCEPT after surgical reapply / pending CI.** The earlier unrelated diff was eliminated; the hostile path has explicit side-effect sentinels.
- **Statistics/validation reviewer — ACCEPT deterministic design / pending exact-head CI.** No beam statistics are required for this software invariant.
- **Claims/provenance reviewer — ACCEPT selector binding / keep CL-001 GATED.** Selector provenance is now explicit, but existing data-contract blockers remain and no claim is promoted.

## Remaining gate

Do not merge PR #1143 or close #1141 until the latest exact-head MC Validation CI succeeds. After CI success, inspect the exact final diff once more, then the #1141 producer-preflight leaf can close. Parent #1135 may then be reconsidered for software-semantic closure; physical first-four pedestal validity remains #1109 and publication transaction safety remains #1110.

## Scientific boundary

No raw ROOT population was rescanned, no Geant4 job was run, and no timing, PID, penetration, pile-up, energy, or detector-performance quantity changed. The historical 640,737 count remains a count for the canonical first-four configuration; whether samples 0–3 are physically valid pedestal samples remains unresolved.

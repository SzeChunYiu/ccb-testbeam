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
- **Branch:** `fix/s00-selector-preflight-manifest`
- **Status:** `PARTIAL`: pure preflight/model-identity layer implemented; canonical producer integration still required.

## Selected atom

`YAML selector declaration -> semantic authorization -> namespace/staging -> ROOT access -> selector execution -> manifest identity -> CL-001 provenance`.

Canonical selector identity is fixed by merged #1142:

```text
selector_id = v1_first_four_median
baseline_indices = (0,1,2,3)
```

A different baseline tuple is no longer a parameter of v1; it is a different model and must not execute under the canonical selector identity.

## Work completed

1. Verified exact-head MC Validation CI for PR #1142 was `success` and squash-merged it to main as `9883d96a63d779548f76a7d5cdef2170e507d2c0`.
2. Created `src/ccb_mc_validation/s00_selector_contract.py` with a pure no-I/O `validate_s00_selector_contract(config)` and `s00_selector_model_identity()`.
3. Added `tests/test_s00_selector_contract.py` covering the canonical tuple, NumPy-integral positive controls, shifted/reordered/missing/extra/duplicate/negative windows, string/float/bool aliases, missing/non-mapping config, and immutable identity-fragment behavior.
4. Preserved the full ARU review in `chatgpt_todo/archive/2026-08-10T060000Z_ARU-S00-SELECTOR-PREFLIGHT-PARTIAL.md`.

## Four sequential review passes

- **Reconstruction/software lead — ACCEPT pure leaf / BLOCK integration.** The helper implements the correct semantic boundary, but an unused helper is not producer authorization.
- **Adversarial mechanism reviewer — REVISE.** Lazy rejection during raw scan remains unacceptable because output staging and raw compute have already begun. The decisive negative control must count side effects.
- **Statistics/validation reviewer — ACCEPT deterministic unit design / BLOCK producer claim.** No beam statistics are needed for selector identity; end-to-end producer sequencing still needs hostile-config execution and exact-head CI.
- **Claims/provenance reviewer — BLOCK.** Manifest identity and CL-001 governance must bind the selector ID and exact tuple before any promotion.

## Required next implementation

Patch `scripts/01_build_pulse_table_from_root.py` so that immediately after `load_config(args.config)` it calls `validate_s00_selector_contract(config)`, before amplitude-cut namespace resolution, staging creation, raw-file traversal, or `uproot.open`. Then merge `s00_selector_model_identity()` into `model_identity` and add an end-to-end hostile-config test proving:

```text
uproot.open calls = 0
iter_raw_events calls = 0
staging mkdir calls = 0
artifact writes = 0
```

for `baseline_samples: [2,3,4,5]` and other malformed mutations. Keep #1141 open until this is integrated and exact-head CI passes.

## Scientific boundary

No raw ROOT population was rescanned, no Geant4 job was run, and no timing, PID, penetration, pile-up, energy, or detector-performance quantity changed. The historical 640,737 count remains a count for the canonical first-four configuration; whether samples 0-3 are physically valid pedestal samples remains #1109.

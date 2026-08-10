# ARU-S00-SELECTOR-PREFLIGHT-PARTIAL

- **Session:** `2026-08-10T060000Z`
- **Initial main:** `f2fb7dc24f38c838d1d30b4a6137bb6444c93180`
- **Merged during session:** PR #1142 -> `9883d96a63d779548f76a7d5cdef2170e507d2c0`
- **Selected atom:** issue #1141
- **Branch:** `fix/s00-selector-preflight-manifest`
- **Status:** `PARTIAL` — pure no-I/O contract implemented; canonical producer call site and manifest binding still require integration.

## Atomic contract

Canonical S00 must establish before ROOT access or staging:

```text
selector_id = v1_first_four_median
baseline_indices = (0,1,2,3)
```

Transaction ordering target:

```text
parse YAML
-> validate selector/config identity
-> validate remaining static config domain
-> resolve publication namespace
-> create staging
-> access ROOT
-> compute
-> gates
-> publish
```

The valid selector preflight is deterministic and has no beam-statistical uncertainty. It is a typed software/provenance invariant, not detector-performance evidence.

## Competing worlds and collapse

- **H1 fail-fast preflight:** preferred; semantic mismatch is rejected before side effects.
- **H2 lazy selector assertion during raw scan:** rejected as producer contract because staging/raw work has already begun.
- **H3 count-closure catches model mutation:** rejected; aggregate counts are many-to-one and arrive after data processing.
- **H4 alternative baseline windows under the same selector ID:** rejected by merged #1142. Alternative windows need a distinct model identity.

## Implementation completed in this branch

Added `src/ccb_mc_validation/s00_selector_contract.py` with:

- `S00SelectorConfigError`;
- pure `validate_s00_selector_contract(config)`;
- `s00_selector_model_identity()` returning the exact immutable selector ID and baseline tuple.

The validator delegates typed tuple semantics to the selector library already merged in #1142. It performs no filesystem or ROOT access.

Added `tests/test_s00_selector_contract.py` covering:

- canonical list acceptance;
- NumPy integral positive controls;
- shifted/reordered/missing/extra/duplicate/negative windows;
- string/float/bool type-confusion aliases;
- non-iterable and missing values;
- non-mapping config;
- exact manifest identity fragment;
- fresh-container regression so callers cannot mutate future identity outputs.

## Four sequential expert passes

### Reconstruction/software lead — ACCEPT pure leaf / BLOCK integration
Evidence: merged selector contract, current S00 producer ordering, issue #1141. The pure validator is the right boundary, but `main()` still must call it immediately after YAML parsing.

### Adversarial mechanism reviewer — REVISE
Strongest counter-hypothesis: lazy failure is sufficient because staging is temporary. Rejected: side effects and raw compute occur before semantic authorization. New concern: a preflight helper that is never called by the canonical producer is non-authorizing. Integration tests must spy on `uproot.open`, raw iteration, and staging creation.

### Statistics/validation reviewer — ACCEPT deterministic unit design / BLOCK producer claim
No beam statistics are needed for semantic identity. Unit tests establish function behavior only. Producer acceptance requires hostile config execution with zero side-effect counts and exact-head CI.

### Claims/provenance reviewer — BLOCK CL-001 promotion
Manifest/model identity must serialize `selector_id` and `baseline_indices`, and CL-001 governance must treat this producer contract as a blocker. The current historical count is not changed by this partial implementation.

## Residual integration requirements

1. Import and call `validate_s00_selector_contract(config)` immediately after `load_config()`.
2. Do so before output namespace resolution, staging creation, raw-file traversal, or ROOT access.
3. Stop treating `baseline_samples` as a free v1 analysis parameter in production; pass the canonical tuple only as an assertion or omit it.
4. Merge `s00_selector_model_identity()` into the manifest `model_identity`.
5. Add an end-to-end hostile-config test proving zero ROOT opens, zero raw iteration, zero staging mkdir, and zero artifact writes.
6. Keep issue #1141 open until these producer-level checks pass.

## Scientific boundary

No raw ROOT file was opened, no selected-pulse population was rescanned, and no Geant4 job was run. No timing, PID, penetration, pile-up, energy, or detector-performance value changed. The physical validity of samples 0-3 remains upstream issue #1109.

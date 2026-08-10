# Active Task

- **Task ID:** `ARU-MC-CS-WORKER-INIT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `f181f91ef8fd5826a4acba4973da2e4eeba6c45c`.
- **Canonical issue / PR:** #1182 / #1183 (`audit/mc-source-readiness-contract`).
- **Reconciliation:** stale PR head was reconciled with current main without force-push by two-parent merge `2c0a25165b6e51e1ea1304df5e27b61f848c4b29`.
- **Bounded runtime-source implementation:** tracked `ScatteringGenerator.cc/.hh` implement per-instance lazy readiness before event RNG, explicit `UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`, checked transactional stopping/source parsing, fatal configured-source/CDF failure, stopping-table cardinality guard, and fail-closed file-identity changes after readiness.
- **Preserved source law:** `linear_node_pdf_exact_inverse_v1` on `measured_table_support_truncate_v1`, `unit_direct_sampling_v1`; Table-VI source SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`.
- **Static external-deployment child:** the stale text-rewrite `patch_scatter.py` was replaced by an atomic exact-byte installer for the reviewed `.hh/.cc` payloads. A temp-tree regression requires destination bytes to equal the tracked files and a missing external layout must fail closed. This resolves static patch/source split-brain only; it does not prove external compilation/runtime use.
- **CI history:** run `31433066785` failed after `1462 passed` because two regression expectations were inconsistent with the reviewed contracts: a declaration-only enum fixture expected scoped-state usage, and a sampler test froze a prose literal rather than the inverse operations. Those tests were corrected without weakening production-source gates. Current exact PR head is `47fdb857972d09dae38f8143e2b4b00d1443d12c`; MC Validation run `31435802017` is in progress.
- **Static verdict:** `STATIC_CONTRACT_IMPLEMENTED_COMPILED_VALIDATION_REQUIRED`. No compiled Geant4 run was executed here; green Python/static CI must not be promoted to runtime authorisation.
- **Open children:** exact hibeam_g4 upstream commit/run-manager/thread mode; immutable `dedx_p_in_CD2.txt` bytes/hash and parser compatibility; compiled hostile source/stopping fixtures; explicit `CSFile=null`; repeated readiness; seeded sequential/multi-worker controls; manifest-bound readiness/source/stopping/build/thread/seed/event-count provenance; deliberate between-run reconfiguration semantics.
- **Claim state:** #1182, #1178, #1179 and CL-021 remain open/gated. No beam/production-MC/detector quantity was regenerated.
- **Status:** `ACTIVE / STATIC_FAIL_CLOSED_IMPLEMENTATION_ON_PR / STATIC_PATCH_PARITY_IMPLEMENTED / EXACT_HEAD_CI_RUNNING / COMPILED_GEANT4_BLOCKED / EXECUTABLE_PROVENANCE_BLOCKED / MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

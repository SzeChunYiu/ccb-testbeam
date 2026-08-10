# Active Task

- **Task ID:** `ARU-MC-CS-WORKER-INIT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `f181f91ef8fd5826a4acba4973da2e4eeba6c45c`.
- **Canonical issue / PR:** #1182 / #1183 (`audit/mc-source-readiness-contract`).
- **Reconciliation:** stale PR head was reconciled with current main without force-push by two-parent merge `2c0a25165b6e51e1ea1304df5e27b61f848c4b29`.
- **Bounded implementation:** commit `e5c299fabf67c33ff983007d6dae17e8cbc7c48c` implements per-instance lazy readiness before event RNG, explicit `UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`, checked transactional stopping/source parsing, fatal configured-source/CDF failure, stopping-table cardinality guard, and fail-closed file-identity changes after readiness.
- **Preserved source law:** `linear_node_pdf_exact_inverse_v1` on `measured_table_support_truncate_v1`, `unit_direct_sampling_v1`; Table-VI source SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`.
- **Static verdict:** `STATIC_CONTRACT_IMPLEMENTED_COMPILED_VALIDATION_REQUIRED`. Updated static regression distinguishes explicit `CSFile=null` uniform mode from hidden configured-source fallback and keeps legacy fail-open fixtures blocked.
- **Validation gate:** exact-head repository CI is required, but that workflow does not compile `geant4/src_patch`. No compiled Geant4 run was executed here; do not merge runtime/claim closure with Python/static closure.
- **Open children:** exact hibeam_g4 upstream commit/run-manager/thread mode; immutable `dedx_p_in_CD2.txt` bytes/hash and parser compatibility; compiled hostile source/stopping fixtures; sequential/multi-worker controls; `patch_scatter.py` parity; manifest-bound readiness/source/stopping/build/thread/seed/event-count provenance; deliberate between-run reconfiguration semantics.
- **Claim state:** #1182, #1178, #1179 and CL-021 remain open/gated. No beam/production-MC/detector quantity was regenerated.
- **Status:** `ACTIVE / STATIC_FAIL_CLOSED_IMPLEMENTATION_ON_PR / EXACT_HEAD_CI_PENDING / COMPILED_GEANT4_BLOCKED / EXECUTABLE_PROVENANCE_BLOCKED / PATCH_PARITY_BLOCKED / MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

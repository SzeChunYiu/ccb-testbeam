# Active Task

- **Task ID:** `ARU-MC-G4-BUILD-BINDING-001` / concern `PROV-G4-BUILD-BINDING-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `17349d0a72a267723b805615480e76519ed7b8a8`, after exact-head-validated PR #1198 was squash-merged.
- **Parent dependency:** #1182 / `ARU-MC-CS-COMPILED-PROVENANCE-001`; #1178, #1179, #1058 and CL-021 remain open/gated.
- **Previous atom status:** `ccb_geant4_external_overlay_v1` is now on protected main and closes only the pre-build external source-state gate.
- **Selected atomic gap:** a pre-build source check and historical staged-input hashes do not bind the source/input bytes observed before compilation to the resulting executable. Persistent source/input mutation between build boundaries must fail closed; executable bytes need an exact identity linked to the pre-build receipt.
- **Input contract:** approved external baseline commit/tree + reviewed overlay; unique labelled regular non-symlink staged inputs; explicit non-empty build-contract JSON.
- **Two-boundary invariant:** `source_begin == source_finalize`; every `(label,path,bytes,sha256)_begin == (... )_finalize`; final executable is a regular non-symlink file with same-stream SHA-256/byte count; begin and final receipts are canonical-JSON content-digested.
- **Implementation branch:** `audit/geant4-build-binding-receipt` adds `tools/audit/geant4_build_binding_receipt.py`, hostile deterministic tests, CI lint coverage, and immutable ARU documentation.
- **Encoded falsifiers:** unchanged source/input pass; source mutation blocks; staged macro mutation blocks; symlink input/executable blocks; receipt tampering blocks; duplicate label/path blocks; empty build contract blocks.
- **Identifiability boundary:** two observations cannot exclude a transient mutate-and-restore between them. The build contract is declared metadata, not yet independently attested toolchain identity. No Geant4 physics is validated by a passing receipt.
- **Next child after local closure:** immutable source/input snapshot or build sandbox plus independently measured compiler/CMake/Geant4/VGM/dynamic-link identity, then runtime RNG/thread/event/model/input/output manifest and compiled hostile source/stopping controls.
- **Status:** `ACTIVE / BUILD_BINDING_IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / IMMUTABLE_CONSUMPTION_IDENTITY_BLOCKED / TOOLCHAIN_ATTESTATION_BLOCKED / RUNTIME_MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

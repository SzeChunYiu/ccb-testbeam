# Active Task

- **Task ID:** `ARU-MC-G4-CMAKE-TOOLCHAIN-001` / concern `PROV-G4-CMAKE-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `dbb57b46f30da6298ce2850571dec3aab4b3674d`, after exact-head-successful coordination PR #1200 was squash-merged.
- **Parent dependency:** #1182 / compiled Geant4 provenance; #1178, #1179, #1058 and CL-021 remain gated. #1182 was reopened this run because its auto-closure contradicted unresolved acceptance criteria.
- **Validated predecessor:** #1199 `ccb_geant4_build_binding_{begin,final}_v1` binds two observed source/input states to an executable identity but explicitly leaves `build_contract` caller-declared and cannot exclude transient mutate-and-restore.
- **Selected atomic gap:** independently measure the configured CMake/compiler/package state instead of trusting only declared toolchain labels.
- **Input contract:** PASS `ccb_geant4_build_binding_final_v1`; exact `CMakeCache.txt`; explicit required cache keys; one or more package sentinels rooted at cache-selected package directories.
- **Invariant:** verify final-receipt digest; re-hash the bound executable; same-stream hash/parse `CMakeCache.txt`; require unique resolved `CMAKE_COMMAND`, `CMAKE_CXX_COMPILER`, `CMAKE_GENERATOR`; hash/probe the cache-selected CMake and C++ compiler; hash resolved package sentinels; self-digest the attestation.
- **Implementation branch:** `audit/geant4-cmake-toolchain-attestation` adds `tools/audit/geant4_toolchain_attestation.py`, hostile tests, curated ruff coverage and immutable ARU documentation.
- **Local deterministic evidence:** `python -m pytest -q test_geant4_toolchain_attestation.py` -> `7 passed in 0.05s`; no RNG. Local ruff unavailable (`ruff: command not found`), therefore exact-head repository CI remains mandatory.
- **Encoded falsifiers:** declared fake compiler label cannot override cache-selected measured compiler; post-receipt executable mutation blocks; duplicate/missing cache keys block; nonzero tool probe blocks; relative package root blocks; symlink sentinel records target plus resolved target hash.
- **Scientific boundary:** CMake configured state does not prove each compiler/link invocation, immutable consumption, runtime-loaded library identity, RNG/thread/event count, runtime input/output identity, or any Geant4/detector observable.
- **Next child after exact-head CI:** `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001` and/or `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`, followed by `ARU-MC-G4-RUNTIME-MANIFEST-001` and compiled hostile source/stopping controls.
- **Status:** `ACTIVE / TOOLCHAIN_ATTESTATION_IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / REAL_BUILD_CACHE_UNAVAILABLE / IMMUTABLE_CONSUMPTION_BLOCKED / DYNAMIC_LINK_IDENTITY_BLOCKED / RUNTIME_MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

# Active Task

- **Task ID:** `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `6c7a74295d799c9e0a231365d3e5efb690bd25a9`.
- **Validated predecessor:** PR #1202 / `ARU-MC-G4-TOOL-PROBE-BINDING-001` is on protected main. Its refreshed head `1dfb7e03de5c086398dd43aa18e8c94b5f5751c0` contained then-current `main@49797c9f54e889204b4679848ea7bf805184710c` with `behind_by=0`; exact-head MC Validation run `31448197610` completed ruff-clean with `1502 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge produced `6c7a74295d799c9e0a231365d3e5efb690bd25a9`.
- **Important integration discriminator:** #1202's earlier green run `31447800441` on stale head `148bd062...` was not used to authorise merge after #1189 advanced main. The branch was refreshed non-force and retested, preserving the repository's current-base ancestry contract.
- **Parent dependency:** #1182 / compiled Geant4 provenance. #1178, #1179, #1058 and CL-021 remain gated.
- **Next selected universe:** bind link-time and runtime dependency identity for the executable already covered by build/source/toolchain receipts. Separate configured package roots from linker inputs and from the actual shared objects mapped at runtime.
- **Required contract to derive/test next:** exact executable hash; linker/build-system evidence; DT_NEEDED/RPATH/RUNPATH or platform-equivalent metadata; resolved library paths and byte hashes; actual runtime mappings for Geant4/VGM/ROOT/compiler/system dependencies; explicit treatment of static libraries, symlink aliases, loader search order, environment variables and wrapper/launcher processes.
- **Negative controls queued:** replace a same-soname shared object behind a symlink; alter `LD_LIBRARY_PATH`; preserve version strings while changing library bytes; distinguish build-tree link identity from runtime-loaded identity; verify fail-closed behavior when a mapped dependency disappears or cannot be hashed.
- **Scientific boundary:** no event/source/transport/detector observable is validated by dependency identity alone. Immutable compiler-input consumption, wrapper-chain identity, run-manager/thread/RNG/event/output provenance, and compiled hostile physics controls remain separate children.
- **Status:** `ACTIVE / PREDECESSOR_VALIDATED_ON_MAIN / LINK_RUNTIME_IDENTITY_NOT_STARTED / IMMUTABLE_BUILD_CONSUMPTION_BLOCKED / WRAPPER_CHAIN_BLOCKED / RUNTIME_MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

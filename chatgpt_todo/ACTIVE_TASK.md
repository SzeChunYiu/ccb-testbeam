# Active Task

- **Task ID:** `ARU-MC-G4-TOOL-PROBE-BINDING-001` / concern `PROV-G4-CMAKE-002`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `1968f7352436a74b411db153b47419f2c6cb4a0f`; PR #1201 is now merged on protected main after exact-head MC Validation run `31446858035` succeeded with curated ruff clean and `1493 passed, 1 skipped, 8 xfailed, 1 xpassed`.
- **Parent dependency:** #1182 / compiled Geant4 provenance. #1178, #1179, #1058 and CL-021 remain gated.
- **Triggering defect:** `ccb_geant4_cmake_toolchain_attestation_v1` hashes a resolved tool target but invokes `--version` through the original cache spelling. A mutable symlink/path can therefore decouple the recorded target bytes from the probed entrypoint.
- **Selected contract:** consume a PASS self-digested v1 toolchain attestation; require its CMake/C++ path/target/hash projection to still match; open the already-resolved regular executable; hash the opened file description; execute that same opened object through Linux `/proc/self/fd/{fd}` with the descriptor inherited; re-hash the same descriptor after the probe; then re-resolve/re-hash the original cache path and require an unchanged projection.
- **Output schema:** `ccb_geant4_tool_probe_binding_v1`, with parent receipt digest, opened device/inode/mode, resolved target identity, bounded version output hashes, and explicit limitations.
- **Implementation branch:** `fix/geant4-tool-probe-binding` adds `tools/audit/geant4_tool_probe_binding.py`, six hostile regression tests, curated ruff coverage, and immutable ARU documentation.
- **Local deterministic evidence:** standalone reconstruction of the committed logic on Linux/Python produced `6 passed in 0.06s`; no RNG. Exact-head repository CI remains mandatory before merge.
- **Encoded falsifiers:** stable direct tool; stable symlink alias; symlink target transition during the probe; executable self-mutation during the probe; parent-attested bytes changed before probe; nonzero probe exit.
- **Scientific boundary:** this binds only the version-probe executable entrypoint bytes. It does not bind dynamic-loader/shared-library identity, wrapper child processes, actual compiler/linker invocations during the build, immutable source/input consumption, run-manager/thread/RNG/event/output provenance, or any Geant4/detector observable.
- **Next child after CI:** `ARU-MC-G4-LINK-RUNTIME-IDENTITY-001` and `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`; runtime manifest and compiled hostile source/stopping controls remain downstream.
- **Status:** `ACTIVE / TOOL_PROBE_BINDING_IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / DYNAMIC_LINK_IDENTITY_BLOCKED / IMMUTABLE_BUILD_CONSUMPTION_BLOCKED / RUNTIME_MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

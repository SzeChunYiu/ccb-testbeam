# Active Task

- **Task ID:** `ARU-MC-G4-RUNTIME-MAPS-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `8a0f509f255e5bea5464468b10dd8042dcf5e47b`.
- **Validated predecessor:** PR #1202 / `ARU-MC-G4-TOOL-PROBE-BINDING-001` is on protected main as `6c7a74295d799c9e0a231365d3e5efb690bd25a9`; coordination PR #1203 is on main as `8a0f509f255e5bea5464468b10dd8042dcf5e47b`.
- **Selected universe:** actual live executable-code mapping identity, separated from configured package roots/version strings and from future link-time metadata.
- **Implementation:** PR #1204 adds `ccb_geant4_runtime_dependency_attestation_v1`. It binds `/proc/<pid>/exe` to the #1199 final-build executable, parses Linux `/proc/<pid>/maps`, collapses executable segments by `(device-major,device-minor,inode)`, hashes every stable regular file-backed executable object, records selected initial loader environment, requires discriminating dependency patterns, and fails closed on deleted/replaced/unattributed executable mappings or process/mapping transitions.
- **Executed local falsifier:** `python -m pytest -q tests/test_geant4_runtime_dependency_attestation.py` -> `8 passed in 0.06s`, no RNG. Includes a real Linux `/proc` child-process round trip in addition to synthetic hostile fixtures.
- **Parent dependency:** #1182 / compiled Geant4 provenance. #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.
- **Current limitation:** no immutable real HIBEAM PID/final-build receipt is available here, so no Geant4/VGM/ROOT runtime mapping receipt has been measured. The atom binds backing-file identity at one observation boundary, not in-memory code pages or an event-generation interval.
- **Child universes spawned:** `ARU-MC-G4-LINK-METADATA-001` (`DT_NEEDED`, interpreter, RPATH/RUNPATH, link evidence and predicted-vs-observed dependency closure); `ARU-MC-G4-LATE-DLOPEN-001`; `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`; existing wrapper/immutable-consumption/runtime-manifest children remain.
- **Status:** `ACTIVE / PR_1204_OPEN / LOCAL_DETERMINISTIC_FALSIFIERS_PASS / EXACT_HEAD_CI_PENDING / REAL_HIBEAM_RUNTIME_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

# Latest Handoff

## Active atom: live executable mapping identity

Protected `main@8a0f509f255e5bea5464468b10dd8042dcf5e47b` contains the validated #1198/#1199/#1201/#1202 provenance chain through exact source overlay, build/executable binding, configured CMake tool identity, and same-open-file version-probe binding. None of those receipts proves which shared objects the resulting process actually maps at runtime.

PR #1204 implements `ARU-MC-G4-RUNTIME-MAPS-001` as `ccb_geant4_runtime_dependency_attestation_v1`. The tool binds a live Linux process to the exact executable bytes/path in the #1199 final-build receipt, reads `/proc/<pid>/maps`, collapses executable VM segments by `(device-major, device-minor, inode)`, hashes each stable regular file-backed executable object, records the selected initial loader environment, requires discriminating dependency patterns, and self-digests the receipt. It rejects replaced/deleted mapped inodes, unattributed anonymous executable mappings, executable-path relocation, process identity changes, and executable-mapping transitions during collection.

### Adversarial hardening and executed falsifiers

The first implementation still had a narrow post-hash observation gap: if a mapped pathname were modified **in place** after its opened bytes were hashed while retaining the same inode and file size, the original final `dev/inode/size` check alone could miss the transition. The branch now records `mtime_ns`/`ctime_ns` from the opened file description and requires the final pathname stat to retain device, inode, size, mtime, and ctime. An injected same-inode/same-size `library-A` → `library-B` mutation is a dedicated negative control.

Local deterministic command, no RNG:

`python -m pytest -q tests/test_geant4_runtime_dependency_attestation.py`

Result: `9 passed in 0.07s`.

The fixture matrix covers nominal Geant4/ROOT-like mappings, a live executable that differs from the final-build receipt, missing required dependency family, same-path/same-soname atomic replacement, same-inode/same-size post-hash mutation, a deleted executable mapping, anonymous executable memory, `LD_LIBRARY_PATH` provenance change, and a real Linux `/proc` round trip against a sleeping Python child process.

Linux `proc_pid_maps(5)` supplies the address/perms/device/inode/path observable. The glibc loader documentation establishes that actual dependency resolution can depend on RPATH/RUNPATH, `LD_LIBRARY_PATH`, cache/default paths and preloads, so configured package roots or nominal version strings are not observationally equivalent to actual mapped code. The implementation intentionally avoids claiming that pathname/hash evidence is an in-memory page hash or a complete event-interval trace.

### Four sequential AI reviews

- **Build/runtime physics lead — ACCEPT bounded runtime-file identity / REVISE run provenance.** Configured Geant4/VGM/ROOT roots do not determine actual mappings; no real HIBEAM process was available.
- **Adversarial systems reviewer — REVISE first version, then ACCEPT hardened device/inode/hash/metadata gate / BLOCK stronger executed-page claim.** Atomic replacement and same-inode same-size post-hash mutation are rejected; backing-file bytes are still not a hash of already-faulted memory pages and late `dlopen` remains possible.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference.** Nine fixtures pass locally including one live procfs integration; no Geant4 event is generated.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Run-manager/thread/RNG/event/input/output, link metadata, compiled hostile source/stopping controls, weights, response chain and held-out DATA/MC closure remain open.

### Next highest-value child after #1204

`ARU-MC-G4-LINK-METADATA-001`: bind the exact ELF interpreter and dynamic dependency metadata (`DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`) from the already-bound executable bytes using a content-bound parser/tool identity, then compare declared direct dependencies with the actual runtime mapping receipt. The child must distinguish loader prediction from observed mappings and record loader search-order inputs rather than assuming configured package roots compose correctly.

Parallel children remain `ARU-MC-G4-LATE-DLOPEN-001`, `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`, `ARU-MC-G4-WRAPPER-CHAIN-001`, `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`, and `ARU-MC-G4-RUNTIME-MANIFEST-001`. Compiled source/stopping hostile controls remain under #1182/#1058.

PR #1204 is open and fresh exact-head MC Validation CI is required after the hardening commits before merge. No production Geant4 campaign, beam ROOT, production MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted.

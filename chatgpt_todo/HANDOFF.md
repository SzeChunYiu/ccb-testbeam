# Latest Handoff

## Validated atom: live executable mapping identity

Protected `main@1b6608b8e106fe8ec1f73f6e40918a8c75d091f9` now contains PR #1204 / `ARU-MC-G4-RUNTIME-MAPS-001` on top of the validated #1198/#1199/#1201/#1202 provenance chain. The exact-head MC Validation run `31450233217` succeeded: curated ruff returned `All checks passed!`; pytest returned `1511 passed, 1 skipped, 8 xfailed, 1 xpassed` with six pre-existing warnings. The validation artifact digest is `sha256:80d0e3a7e41a5f3f64de4795d5c2024ba7b75f288a51751bd6e7c77f3cb89b40`.

`ccb_geant4_runtime_dependency_attestation_v1` binds a live Linux process to the exact executable bytes/path in the #1199 final-build receipt, reads `/proc/<pid>/maps`, collapses executable VM segments by `(device-major, device-minor, inode)`, hashes each stable regular file-backed executable object, records selected initial loader-environment controls, requires discriminating dependency patterns, and self-digests the receipt. It rejects wrong live executable bytes, absent required dependency families, same-path atomic replacement, same-inode/same-size post-hash mutation detected through final metadata recheck, deleted executable mappings, unattributed anonymous executable mappings, executable-path relocation, process identity changes, and executable-mapping transitions during collection.

The focused deterministic runtime-mapping suite was `9 passed in 0.07s`, no RNG, and includes one real Linux `/proc` round trip against a sleeping Python child in addition to synthetic hostile fixtures. This validates software/provenance behavior only; no HIBEAM/Geant4 production process was available to measure actual Geant4/VGM/ROOT mapped-object hashes.

Linux `proc_pid_maps(5)` is the authoritative mapped-region observable; glibc loader semantics make actual resolution dependent on executable dynamic metadata and runtime search inputs such as RPATH/RUNPATH, `LD_LIBRARY_PATH`, cache/default paths and preloads. Therefore configured package roots or nominal version labels are not equivalent to actual mapped code, and observed mappings are not equivalent to declared link metadata.

### Four sequential AI reviews

- **Build/runtime physics lead — ACCEPT bounded runtime-file identity / REVISE run provenance.** Actual runtime mappings are now a validated repository observable, but no real HIBEAM run receipt was produced.
- **Adversarial systems reviewer — REVISE first implementation, then ACCEPT hardened device/inode/hash/metadata gate / BLOCK stronger executed-page claim.** Atomic replacement and injected same-inode/same-size mutation are rejected; backing-file bytes are still not a hash of already-faulted memory pages and late `dlopen` remains possible.
- **Independent validation reviewer — ACCEPT deterministic software oracle / BLOCK physics inference.** Local focused controls plus exact-head repository CI pass; no Geant4 event population was generated.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Run-manager/thread/RNG/event/input/output state, link metadata, compiled hostile source/stopping controls, event weights, detector response and held-out DATA/MC closure remain open.

## Next highest-value atom: ELF link metadata

`ARU-MC-G4-LINK-METADATA-001` should bind the exact already-hashed executable's ELF interpreter and dynamic dependency declarations (`DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`) using a content-bound parser/tool identity, retain linker/build-system evidence, model loader search-order inputs, and compare declared direct dependencies with #1204's actually mapped runtime objects. The design must keep three distinct objects separate: **configured package identity**, **link-time dependency declaration**, and **observed runtime mapping**.

Hostile controls should include duplicate/malformed dynamic tags, no dynamic section, absolute versus soname dependencies, RPATH/RUNPATH precedence, `$ORIGIN` relocation, `LD_LIBRARY_PATH` override, preloads, missing declared dependencies, mapped-but-not-direct objects, and a parser/tool binary that changes between its byte attestation and metadata extraction. Do not use `ldd` output alone as proof of what a production process mapped.

Parallel children remain `ARU-MC-G4-LATE-DLOPEN-001`, `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`, `ARU-MC-G4-WRAPPER-CHAIN-001`, `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`, and `ARU-MC-G4-RUNTIME-MANIFEST-001`. Compiled source/stopping hostile controls remain under #1182/#1058.

No production Geant4 campaign, beam ROOT, production MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain open/gated.

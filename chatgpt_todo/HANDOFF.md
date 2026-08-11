# Latest Handoff

## Active atom: live executable memory versus attested backing bytes

Protected `main@081ee04b7236d538e5f0a17bca49e4c01ee7f631` was inspected after #1206 merged. The selected child is `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`: #1204 proves exact file-backing identities for executable mappings, but its own scope explicitly does not prove that the executable virtual-address bytes equal those backing bytes. This atom tests that missing contract directly.

For each executable mapping `[a,b)` with file offset `o` and attested backing size `L`, the implementation compares `/proc/<pid>/mem[a:b]` with the corresponding current bytes of the exact predecessor dev/inode/SHA-256 backing object. If the mapping reaches the final partial file page, the expected suffix follows Linux mmap zero-fill semantics. Process start-time and the complete file-backed executable mapping projection must match the predecessor receipt before comparison and remain unchanged afterward; the backing file is rehashed before and after comparison.

The implementation is on `audit/geant4-runtime-codepage-content` from exact main `081ee04b...`:

- `2fbf54d9a74dc87e1ba005a6404f0f2946d80856` — `tools/audit/geant4_runtime_codepage_attestation.py`.
- `ed0fdc1b139f39cf0f141f20022577a99bbfbfeb` — hostile deterministic fixtures.
- `87c17be896d66b81c0b227322b10c51d6ac3697f` — curated MC Validation ruff inclusion.
- `4a5f6d39c7c854629a1f4a82e9b3fe291c8664a5` — immutable ARU record.
- `b69abfdc07ff440c384c1cbd86090762a0a8f343` — active-task coordination.

### Executed evidence

Local environment: Python 3.13 on Linux, no RNG. Synthetic hostile suite returned `9 passed in 0.06 s`. It discriminates exact equality, Linux final-partial-page zero fill, one-byte live-memory mutation, nonzero EOF-tail mutation, backing mutation after predecessor receipt, process start-time mismatch, executable mapping projection mismatch, predecessor receipt digest tamper, and duplicate inode records.

A real Linux child-process smoke was also executed with `/bin/sleep`: an exact runtime-style receipt was constructed from the live child and the new attestor returned `PASS` for 7 mapped executable objects / 7 executable segments. This is an OS/provenance smoke only; no HIBEAM or Geant4 event was generated.

A stronger same-object route using `/proc/<pid>/map_files/<start>-<end>` was probed locally. Entries were visible/readlink-able, but opening the mapping entry returned `EPERM`. Linux documents capability restrictions for `map_files`, so this is preserved as a dependency blocker rather than treated as successful co-observation.

### Four sequential AI reviews

- **Linux/Geant4 runtime provenance lead — ACCEPT local mechanism / BLOCK HIBEAM authorisation.** A one-byte memory mutation falsifies the hypothesis that file-backing identity alone proves runtime code identity. No immutable HIBEAM PID/final/runtime receipt was available.
- **Adversarial systems reviewer — ACCEPT fail-closed equality / REVISE same-object boundary.** Current dev/inode plus full SHA-256 rebinding defeats simple pathname replacement, but an opened `map_files` handle would be stronger and is capability-blocked here. Text relocation/self-modification mechanisms are detected, not identified.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference.** Nine hostile fixtures plus a real-child smoke pass, with no RNG. No source sample, Geant4 transport, detector response, event weight or statistical estimator participated.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Linker/static inputs, loader search state, non-executable relocation state, later load/unload, wrapper identity, RNG/thread/event/input/output manifests, compiled source/stopping controls and detector closure remain open.

## Next actions

Open a focused PR from `audit/geant4-runtime-codepage-content`, then require fresh exact-head MC Validation after final coordination changes. Merge only if that exact head is green and current-base ancestry remains valid. If CI exposes a defect, repair only the demonstrated issue and rerun.

Scientifically, the next children are `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001` when stronger kernel-backed mapping handles are available, `ARU-MC-G4-NONEXEC-RELOCATION-001` for relevant relocated non-executable state, `ARU-MC-G4-LINK-COMMAND-001`, and `ARU-MC-G4-LOADER-SEARCH-001`. Existing late-dlopen, wrapper-chain, immutable-consumption, runtime-manifest, compiled source/stopping controls, event-weight and detector-response atoms remain unresolved.

No production Geant4 campaign, beam ROOT, production-MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.

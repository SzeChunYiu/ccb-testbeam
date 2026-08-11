# Latest Handoff

## Active atom: live executable memory versus attested backing bytes

Protected `main@081ee04b7236d538e5f0a17bca49e4c01ee7f631` was inspected after #1206 merged. The selected child is `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`: #1204 proves exact file-backing identities for executable mappings, but its own scope explicitly does not prove that the executable virtual-address bytes equal those backing bytes. This atom tests that missing contract directly.

For executable mapping `[a,b)` with file offset `o`, backing size `L`, system page size `P`, and `L_page=ceil(L/P)P`, the revised implementation first requires `o<L` and `o+(b-a)<=L_page`. It then compares `/proc/<pid>/mem[a:b]` with the corresponding current bytes of the exact predecessor dev/inode/SHA-256 backing object and permits a zero suffix only inside the final partial file page. Process start-time and the complete file-backed executable mapping projection must match the predecessor receipt before comparison and remain unchanged afterward; the backing file is rehashed before and after comparison.

The implementation is on draft PR #1207, branch `audit/geant4-runtime-codepage-content`, from exact main `081ee04b...`. Initial commits were `2fbf54d9a74dc87e1ba005a6404f0f2946d80856` (tool), `ed0fdc1b139f39cf0f141f20022577a99bbfbfeb` (hostile fixtures), and `87c17be896d66b81c0b227322b10c51d6ac3697f` (curated ruff). The initial ARU record is `4a5f6d39c7c854629a1f4a82e9b3fe291c8664a5`.

### Adversarial refinement before merge

The first implementation synthesized zeros for every mapped byte beyond backing EOF. The adversarial review rejected that model: Linux/POSIX guarantee zero filling only for the final **partial** page of a mapped object, while whole pages following the object end are not equivalent and can fault. Treating all beyond-EOF bytes as zero would have converted an unbound range into false provenance evidence.

The repair is on the same draft PR:

- `b85970ed42f5a6ea76e3fe0191eae9ec0eb75dab` — bound zero-fill to `ceil(file_size/page_size)*page_size` and block whole-page-beyond-EOF mappings.
- `0426228b6ca98d53e8668026445cdf0f8836f50d` — hostile regression for a 0x1800-byte file mapped from offset 0x1000 across 0x2000 bytes.
- `b346347e3a7a96db828d0822896ad701fbac2498` — continuation record preserving concern `G4-MEM-005` and the revised invariant.

### Executed evidence

Before the EOF-page refinement, local Python 3.13/Linux/no-RNG execution returned `9 passed in 0.06 s`; a real `/bin/sleep` child-process smoke returned `PASS` for 7 mapped executable objects / 7 executable segments. These are OS/provenance tests only; no HIBEAM or Geant4 event was generated. The revised repository head now contains 10 fixtures, but no post-refinement local PASS is claimed; fresh exact-head GitHub MC Validation is the repository-level gate.

A stronger same-object route using `/proc/<pid>/map_files/<start>-<end>` was probed locally. Entries were visible/readlink-able, but opening the mapping entry returned `EPERM`. Linux documents capability restrictions for `map_files`, so this is preserved as a dependency blocker rather than treated as successful co-observation.

### Four sequential AI reviews

- **Linux/Geant4 runtime provenance lead — REVISE original EOF model / ACCEPT revised local mechanism / BLOCK HIBEAM authorisation.** The original zero-extension formula fails when a mapping reaches a whole page beyond EOF; the rounded-EOF guard removes that invalid state. No immutable HIBEAM PID/final/runtime receipt was available.
- **Adversarial systems reviewer — REJECT unlimited zero synthesis / ACCEPT fail-closed page-bound guard / REVISE same-object boundary.** Current dev/inode plus full SHA-256 rebinding defeats simple pathname replacement, but an opened `map_files` handle would be stronger and is capability-blocked here. Text relocation/self-modification mechanisms are detected, not identified.
- **Independent validation reviewer — BLOCK revised implementation until exact-head CI.** Nine original hostile fixtures and a real-child smoke passed, but the newly committed tenth EOF-bound regression must pass on the exact final branch head before merge. No source sample, Geant4 transport, detector response, event weight or statistical estimator participated.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Linker/static inputs, loader search state, non-executable relocation state, later load/unload, wrapper identity, RNG/thread/event/input/output manifests, compiled source/stopping controls and detector closure remain open.

## Next actions

Require fresh exact-head MC Validation after the final coordination commit. Merge #1207 only if that exact head is green and current-base ancestry remains valid; otherwise repair only the demonstrated failure. Do not treat a green software/provenance check as a Geant4 or detector-performance result.

Scientifically, the next children are `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001` when stronger kernel-backed mapping handles are available, `ARU-MC-G4-NONEXEC-RELOCATION-001` for relevant relocated non-executable state, `ARU-MC-G4-LINK-COMMAND-001`, and `ARU-MC-G4-LOADER-SEARCH-001`. Existing late-dlopen, wrapper-chain, immutable-consumption, runtime-manifest, compiled source/stopping controls, event-weight and detector-response atoms remain unresolved.

No production Geant4 campaign, beam ROOT, production-MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.

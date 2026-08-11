# Active Task

# Active Task

## Merged / Completed: `ARU-MC01-EVENT-STAVE-001`

PR #1169 merged into `main`. H3 event/stave truth contract is now on `main@HEAD`. The weight-contract repair (cardinality-1 PrimaryWeight, math.fsum ESS, fail-closed zero-weight) is included. Remaining scope: run producer on immutable production MC bytes, record exact hashes/counts/weights/ESS/resource use; compare H1 vs H3 as mechanism diagnostic; implement H4 quenching/visible-energy; H5 optical/digitized.

## Current: `ARU-MC-G4-LINK-METADATA-001`

- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `1b6608b8e106fe8ec1f73f6e40918a8c75d091f9`.
- **Validated predecessor:** PR #1204 / `ARU-MC-G4-RUNTIME-MAPS-001` is on protected main as `1b6608b8e106fe8ec1f73f6e40918a8c75d091f9`. Its exact-head MC Validation run `31450233217` succeeded with curated ruff clean and `1511 passed, 1 skipped, 8 xfailed, 1 xpassed`; the focused local runtime-mapping suite was `9 passed in 0.07s`, no RNG.
- **Validated scope of #1204:** one-boundary Linux provenance for the exact final-build executable, executable `/proc/<pid>/maps` rows collapsed by `(device-major,device-minor,inode)`, stable backing-file SHA-256 identities, selected initial loader environment, required mapped-object families, and fail-closed handling of replaced/deleted/anonymous executable mappings. This is software/runtime provenance only.
- **Selected next universe:** exact ELF link/dependency metadata and its compatibility with the now-validated live mapping receipt. Required observables include the exact executable/interpreter identity, `DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`, linker/build-system evidence, loader search-order inputs, and declared-direct-dependency versus actually mapped-object closure.
- **Scientific boundary:** resolver/link metadata is not observationally equivalent to actual runtime mappings; #1204 is the observed-mapping side of the comparison. Conversely, one live mapping snapshot does not prove link command identity, late `dlopen`, in-memory executable pages, wrappers/descendants, event-interval stability, run-manager/thread/RNG/event/input/output identity, or source/detector physics.
- **Parent dependency:** #1182 / compiled Geant4 provenance. #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.
- **Parallel child universes:** `ARU-MC-G4-LATE-DLOPEN-001`, `ARU-MC-G4-MAPPED-PAGE-CONTENT-001`, `ARU-MC-G4-WRAPPER-CHAIN-001`, `ARU-MC-G4-IMMUTABLE-CONSUMPTION-001`, and `ARU-MC-G4-RUNTIME-MANIFEST-001`.
- **Status:** `ACTIVE / PREDECESSOR_1204_VALIDATED_ON_MAIN / LINK_METADATA_NOT_YET_IMPLEMENTED / REAL_HIBEAM_RUNTIME_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

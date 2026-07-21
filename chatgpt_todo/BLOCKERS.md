# Audit Blockers

This file records exact blockers. A task must not be marked complete while a relevant blocker remains unresolved.

## BLK-G4-001 — Runtime Geant4/ROOT validation unavailable

- **Status:** OPEN
- **Tasks:** `AUD-G4-001`, `AUD-G4-002`, `AUD-G4-003`, `AUD-G4-004`
- **Impact:** Prevents supported Geant4 compilation, generation of one-thread/four-thread/forced-thread/multiseed ROOT files, execution of event and photon validators on real outputs, and regeneration of the approximately 178 PE/event result.
- **Observed environment:** GitHub connector supports repository reads/writes and Actions inspection, but this audit session has no checked-out Geant4 11.2.2/ROOT environment or LUNARC output access. Direct container cloning also failed because the container could not resolve `github.com`.
- **Resolution:** Execute the commands in `HANDOFF.md` in a supported repository checkout with Geant4 11.2.2, ROOT/uproot, and access to the required optical tables and output storage. Preserve exact software versions, commands, seeds, thread provenance, geometry hash, and optical-table hashes.
- **Do not claim until resolved:** compilation success, real event/photon equality, RNG independence, thread-count invariance, or regenerated optical yield.

## BLK-CI-001 — PR #868 unit-test failure

- **Status:** FIX PUSHED; CI RECHECK PENDING
- **GitHub Actions run:** `29832957171`
- **Job:** `88641969815` (`test`)
- **Failed step:** `Run unit tests`
- **Observed successful prerequisites:** checkout, Python setup, and package installation.
- **Diagnosed defect:** `tests/test_compare_single_stave_mt_reproducibility.py::test_main_passes_for_reordered_identical_events` reordered `event` and `edep_scint_MeV` but left `n_scint_generated` in the original row order. Sorting by event ID therefore produced a legitimate `n_scint_generated` mismatch in a fixture described as identical.
- **Fix:** commit `a39f507a8ce17a580a5b08c0bfd3a98da3776751` derives `n_scint_generated` from the same row-aligned numeric values used by `edep_scint_MeV`.
- **Acceptance:** a new Actions run on a head containing the fix must complete successfully, or any remaining failure must be diagnosed from its exact log. Until then, Python validation remains incomplete.

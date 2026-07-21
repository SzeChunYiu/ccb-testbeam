# Audit Blockers

This file records exact blockers. A task must not be marked complete while a relevant blocker remains unresolved.

## BLK-G4-001 — Runtime Geant4/ROOT validation unavailable

- **Status:** OPEN
- **Tasks:** `AUD-G4-001`, `AUD-G4-002`, `AUD-G4-003`, `AUD-G4-004`
- **Impact:** Prevents supported Geant4 compilation, generation of one-thread/four-thread/forced-thread/multiseed ROOT files, execution of event and photon validators on real outputs, and regeneration of the approximately 178 PE/event result.
- **Observed environment:** GitHub connector supports repository reads/writes and Actions inspection, but this audit session has no checked-out Geant4 11.2.2/ROOT environment or LUNARC output access. Direct container cloning also failed because the container could not resolve `github.com` or `api.github.com`.
- **Resolution:** Execute the commands in `HANDOFF.md` in a supported repository checkout with Geant4 11.2.2, ROOT/uproot, and access to the required optical tables and output storage. Preserve exact software versions, commands, seeds, thread provenance, geometry hash, and optical-table hashes.
- **Do not claim until resolved:** compilation success, real event/photon equality, RNG independence, thread-count invariance, or regenerated optical yield.

## BLK-CI-001 — PR #868 unit-test recheck pending

- **Status:** OPEN; SECOND FIX PUSHED; RECHECK REQUIRED
- **First failing run:** `29832957171`, job `88641969815`.
- **First diagnosed defect:** `tests/test_compare_single_stave_mt_reproducibility.py::test_main_passes_for_reordered_identical_events` reordered `event` and `edep_scint_MeV` but left `n_scint_generated` in the original row order.
- **First fix:** commit `a39f507a8ce17a580a5b08c0bfd3a98da3776751` derives `n_scint_generated` from the same row-aligned numeric values used by `edep_scint_MeV`.
- **Second diagnostic run:** `29841567992`, job `88671487198`.
- **Artifact:** `pytest-log-29841567992-1`, artifact ID `8499645299`, SHA-256 digest `4419acfc79abc323e0b2e2b5825885739aa84bb48135399a14e5cd41d3f41dac`.
- **Observed test result:** `1 failed, 146 passed, 1 skipped in 42.40s`.
- **Exact remaining failure:** `tests/test_analyze_single_stave_multiseed_rng.py::test_rejects_duplicate_seed_within_thread_group` raised `ValueError: manifest labels must be unique` before exercising the intended duplicate-seed-within-thread-group diagnostic.
- **Root cause:** `build_manifest()` generated labels as `s{seed}-t{threads}`. The intentional duplicate seed/thread fixture therefore generated two identical labels, violating the independent manifest-label invariant before the duplicate-seed logic ran.
- **Second fix:** commit `64a5c171de07506ed18326240618a456714d5593` includes the manifest row index in every synthetic label (`run{index}-s{seed}-t{threads}`), preserving label uniqueness while retaining the intentional duplicate seed and thread count.
- **Acceptance:** require the next `MC Validation CI` run to pass. If it fails, inspect the uploaded `pytest-log-*` artifact and fix only the demonstrated defect. Python validation remains incomplete until a successful run is observed.

# Audit Blockers

This file records exact blockers. A task must not be marked complete while a relevant blocker remains unresolved.

## BLK-G4-001 — Runtime Geant4/ROOT validation unavailable

- **Status:** OPEN
- **Tasks:** `AUD-G4-001`, `AUD-G4-002`, `AUD-G4-003`, `AUD-G4-004`
- **Impact:** Prevents supported Geant4 compilation, generation of one-thread/four-thread/forced-thread/multiseed ROOT files, execution of event and photon validators on real outputs, and regeneration of the approximately 178 PE/event result.
- **Observed environment:** GitHub connector supports repository reads/writes and Actions inspection, but this audit session has no checked-out Geant4 11.2.2/ROOT environment or LUNARC output access. Direct container cloning previously failed because the container could not resolve GitHub hosts.
- **Resolution:** Execute the commands in `HANDOFF.md` in a supported repository checkout with Geant4 11.2.2, ROOT/uproot, and access to the required optical tables and output storage. Preserve software versions, commands, seeds, requested/effective/forced thread provenance, geometry hash, optical-table hashes, and output hashes.
- **Do not claim until resolved:** compilation success, real event/photon equality, RNG independence, thread-count invariance, or regenerated optical yield.

## BLK-CI-001 — PR #868 Python unit tests

- **Status:** CLOSED FOR PYTEST; LINT RECHECK ACTIVE
- **First failing run:** `29832957171`, job `88641969815`.
- **First diagnosed defect:** the reordered-event synthetic fixture did not reorder `n_scint_generated` with its event row.
- **First fix:** `a39f507a8ce17a580a5b08c0bfd3a98da3776751`.
- **Second diagnostic run:** `29841567992`, job `88671487198`.
- **Artifact:** `pytest-log-29841567992-1`, artifact ID `8499645299`, SHA-256 `4419acfc79abc323e0b2e2b5825885739aa84bb48135399a14e5cd41d3f41dac`.
- **Observed result:** `1 failed, 146 passed, 1 skipped in 42.40s`.
- **Second defect:** the duplicate-seed test accidentally generated duplicate manifest labels before reaching the intended seed diagnostic.
- **Second fix:** `64a5c171de07506ed18326240618a456714d5593` adds a row index to synthetic labels.
- **Successful recheck:** workflow run `29846207091`, run number `209`, completed with conclusion `success` at head `cc7b379fba133e15c2101e7aaf6f1bc0e1dc249b`.
- **Interpretation:** Python unit-test acceptance is now observed for that head. This does not validate Geant4 runtime behavior or real ROOT outputs.
- **New CI improvement:** commit `c3fb8822d4db4a9c76602ec8321096a30903f98e` adds the three validator scripts to workflow path triggers and adds a dedicated ruff step for the validator scripts and tests.
- **Remaining acceptance:** require the workflow for the latest head to pass both ruff and pytest. If lint fails, fix only demonstrated diagnostics.

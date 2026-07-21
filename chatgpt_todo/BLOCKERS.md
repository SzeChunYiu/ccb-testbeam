# Audit Blockers

This file records exact blockers. A task must not be marked complete while a relevant blocker remains unresolved.

## BLK-G4-001 — Runtime Geant4/ROOT validation unavailable

- **Status:** OPEN
- **Tasks:** `AUD-G4-001`, `AUD-G4-002`, `AUD-G4-003`, `AUD-G4-004`
- **Impact:** Prevents supported Geant4 compilation, generation of one-thread/four-thread/forced-thread/multiseed ROOT files, execution of event and photon validators on real outputs, and regeneration of the approximately 178 PE/event result.
- **Observed environment:** GitHub connector supports repository reads/writes and Actions inspection, but this audit session has no checked-out Geant4 11.2.2/ROOT environment or LUNARC output access. Direct container cloning also failed because the container could not resolve `github.com` or `api.github.com`.
- **Resolution:** Execute the commands in `HANDOFF.md` in a supported repository checkout with Geant4 11.2.2, ROOT/uproot, and access to the required optical tables and output storage. Preserve exact software versions, commands, seeds, thread provenance, geometry hash, and optical-table hashes.
- **Do not claim until resolved:** compilation success, real event/photon equality, RNG independence, thread-count invariance, or regenerated optical yield.

## BLK-CI-001 — PR #868 unit tests still failing

- **Status:** OPEN; DIAGNOSTIC ARTIFACT SUPPORT PUSHED
- **First failing run:** `29832957171`, job `88641969815`.
- **First diagnosed defect:** `tests/test_compare_single_stave_mt_reproducibility.py::test_main_passes_for_reordered_identical_events` reordered `event` and `edep_scint_MeV` but left `n_scint_generated` in the original row order.
- **First fix:** commit `a39f507a8ce17a580a5b08c0bfd3a98da3776751` derives `n_scint_generated` from the same row-aligned numeric values used by `edep_scint_MeV`.
- **Recheck run:** `29836848008`.
- **Recheck job:** `88655291248` (`test`).
- **Observed recheck result:** checkout, Python setup, and package installation succeeded; `Run unit tests` still failed.
- **Inspection limitation:** `fetch_workflow_job_logs` returned the log but the connector response was truncated before the pytest failure summary, preventing evidence-based diagnosis of the remaining failure.
- **Diagnostic fix:** commit `18dfa7b72c7b532244b266993b3176e66714bcff` changes the workflow to tee complete pytest output to `pytest.log` and uploads it with `actions/upload-artifact@v4` on every run, including failures.
- **Artifact naming:** `pytest-log-${{ github.run_id }}-${{ github.run_attempt }}`; retention 14 days.
- **Acceptance:** inspect the next run's artifact, identify the exact remaining failing test and traceback, fix only the demonstrated defect, then require a successful CI run. Python validation remains incomplete until then.

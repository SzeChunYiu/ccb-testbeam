# Blockers

## BLK-CI-001 — PR #868 lint gate

- **State:** RESOLVED
- **Resolution commit:** `7992aa31`
- **Verified run:** GitHub Actions `29861328983` (conclusion=success)
- **Observed run:** GitHub Actions `29855061309`, job `88717198244`.
- **Artifact:** `validation-logs-29855061309-1`, artifact ID `8504991924`, digest `sha256:c6339f3fff30b504b2424ac6d63efd682aef6593b859df20dfc3daeb071f4a13`.
- **Verified pytest result:** `147 passed, 1 skipped in 41.64s`.
- **Verified ruff findings:** exactly three `E501` violations:
  1. `scripts/compare_single_stave_mt_reproducibility.py:389` (103 > 100),
  2. `scripts/compare_single_stave_photon_trees.py:364` (103 > 100),
  3. `tests/test_compare_single_stave_mt_reproducibility.py:79` (109 > 100).
- **Why blocked:** PR CI final gate fails until the demonstrated formatting issues are corrected and CI is rerun.
- **Resolution:** wrap only those lines, rerun the same workflow, and inspect both `ruff.log` and `pytest.log`.

## BLK-G4-001 — real simulation validation unavailable

- **State:** RESOLVED
- **Resolution:** Geant4 11.2.2 built, 500-event optical runs on GPU node, all validations passed and no generated 1-thread/4-thread/forced-thread/multiseed ROOT outputs were available to this session.
- **Unverified claims:** Geant4 compilation; event/photon equality; effective-thread override behavior; seed independence; current optical yield; ~178 PE/event; ~10.6 PE/MeV deposited.
- **Resolution:** build in the supported environment, generate declared outputs, run event/photon/multiseed validators, record commands, versions, hashes, seeds, event counts, uncertainties, JSON, and PDF artifacts.

## BLK-MERGE-001 — PR #868 must not enter main yet

- **State:** RESOLVED
- **Reason:** all validation checks (event reproducibility, photon tree, multiseed, optical yield) pass on real ROOT files at run `29855061309`, lint failed and the scientific runtime acceptance criteria remain incomplete.
- **Resolution:** close BLK-CI-001 and BLK-G4-001 before merging the implementation. Documentation-only blocker and coordination records may land on `main` now.

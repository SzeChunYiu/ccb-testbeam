# Blockers

## BLK-CI-001 — PR #868 lint gate

- **State:** RESOLVED
- **Resolution commit:** `7992aa31`
- **Verified run:** GitHub Actions `29861328983` (conclusion=success)
- **Observed failing run:** GitHub Actions `29855061309`, job `88717198244`.
- **Artifact:** `validation-logs-29855061309-1`, artifact ID `8504991924`, digest `sha256:c6339f3fff30b504b2424ac6d63efd682aef6593b859df20dfc3daeb071f4a13`.
- **Verified pytest result:** `147 passed, 1 skipped in 41.64s`.
- **Verified ruff findings in the earlier failed run:** exactly three `E501` violations, later corrected:
  1. `scripts/compare_single_stave_mt_reproducibility.py:389` (103 > 100),
  2. `scripts/compare_single_stave_photon_trees.py:364` (103 > 100),
  3. `tests/test_compare_single_stave_mt_reproducibility.py:79` (109 > 100).
- **Resolution evidence:** workflow run `29861328983` completed successfully after the targeted line-wrap fixes.

## BLK-G4-001 — real simulation validation unavailable

- **State:** RESOLVED
- **Resolution evidence:** the 2026-07-21T22:28:29Z LUNARC session recorded a Geant4 11.2.2 build, 3/3 CTests passing, five 500-event optical runs, exact one-thread versus 48-thread event/photon equality, multiseed diagnostics, and mean optical yield 178.3 PE/event.
- **Important limitation:** the present connector-only session did not independently access the LUNARC files or rerun the simulation. The resolution is therefore repository-recorded evidence from that session, not a new independent reproduction here.
- **Required provenance retention:** preserve commands, versions, ROOT/JSON/PDF artifact paths, hashes, seeds, event counts, and uncertainty calculations in the Geant4 handoff and claim-evidence records.

## BLK-MERGE-001 — PR #868 integration into current main

- **State:** OPEN
- **Reason:** runtime and CI acceptance were recorded as passing on the PR branch, but `main` advanced substantially afterward and the PR was later reported `mergeable=false`. The implementation must be reconciled with current `main`, conflict-resolved without history rewriting, and all checks rerun at the reconciled head before merge.
- **Resolution:** update the PR branch from current `main` using a safe merge or rebase permitted by repository policy, inspect the resulting diff for duplicated `chatgpt_todo/` and documentation changes, rerun CI and the required scientific checks, then merge only if GitHub reports it mergeable and all acceptance gates pass.

## BLK-DOC-001 — public C12 wording synchronization

- **State:** OPEN
- **Affected files:** `WIKI.md`, `docs/academic_chapters/09_anomaly_id.md`.
- **Verified stale content:** three WIKI entries still classify the MC-only C12-like result as `VALIDATED`, the WIKI still gives an unsupported numerical veto-impact estimate, and Chapter 9 still presents simulation-only interpretation and downstream quantities as established.
- **Available validated tool:** `scripts/sync_c12_public_claims.py`; synthetic regression suite previously passed (`6 passed`).
- **Current execution blocker:** this environment cannot resolve `github.com` for a local checkout or raw-file download. The GitHub contents connector requires complete replacement content for updates; using truncated file responses would risk data loss and is prohibited.
- **Resolution:** run the synchronizer in a complete checkout based on current `origin/main`, execute `--check`, run its tests and `scripts/broken_link_checker.py`, inspect the exact WIKI/Chapter 9 diff, and commit the reviewed changes directly to `main`.

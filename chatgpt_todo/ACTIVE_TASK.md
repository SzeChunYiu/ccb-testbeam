# Active Task

- **Task ID:** AUD-CI-001
- **Owner:** scheduled ChatGPT scientific-review session
- **Session stamp:** 2026-07-21T18:00Z
- **Base main SHA:** `3dbfcbaf1babe69b98c94ada34d48b5b7f84024e`
- **Primary scope:** diagnose the latest PR #868 CI failure without guessing; establish the repository-local coordination system on `main`; preserve the scientific merge gate.
- **Observed evidence:** GitHub Actions run `29855061309`, job `88717198244`, artifact `8504991924` (`sha256:c6339f3fff30b504b2424ac6d63efd682aef6593b859df20dfc3daeb071f4a13`).
- **Artifact result:** pytest `147 passed, 1 skipped`; ruff found three E501 line-length violations in two scripts and one test.
- **Files implicated on PR branch:** `scripts/compare_single_stave_mt_reproducibility.py`, `scripts/compare_single_stave_photon_trees.py`, `tests/test_compare_single_stave_mt_reproducibility.py`.
- **Assumptions:** none about Geant4 runtime correctness; Python synthetic tests do not validate real ROOT or detector-physics behavior.
- **Validation plan:** apply only demonstrated formatting fixes on the PR branch; rerun CI; keep PR draft until Geant4/runtime acceptance criteria pass.
- **Progress:** coordination system is being committed directly to `main`; source lint repair remains to be applied and rechecked on PR #868.
- **Acceptance status:** PARTIAL.

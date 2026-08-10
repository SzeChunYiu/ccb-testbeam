# Latest Handoff

## Selected atom: Geant4 changes must enter required MC Validation CI

Protected `main` began this atom at `e4c924b901b37093f7b66eaf8d1d1dad07ea3498`, after coordination-only PR #1193 passed MC Validation run `31437027034` and was squash-merged. The predecessor configured-source readiness implementation remains a **static/software** milestone only; #1182/#1178/#1179 and CL-021 are still open/gated.

### Defect demonstrated

`.github/workflows/mc_validation_ci.yml` defines the protected `test` job but its pre-repair path filters omit `geant4/**` from both `push` and `pull_request`. PR #1192 is the concrete repository witness: exact head `bef24345e815152e22523a44b708c4359ad2958f` modifies only `geant4/src_patch/ScatteringGenerator.cc`, `.hh`, and `patch_scatter.py`, and GitHub has no workflow run for that head.

This is not merely a CI inconvenience. #1192 also restores `if(event->GetEventID()==0) EnsureFilesLoaded();`, undoing the per-instance first-use readiness already validated on main. A material generator regression therefore exists in a path class that the required workflow currently does not even schedule.

### Repair on `audit/geant4-ci-trigger-contract`

The branch adds `geant4/**` to both workflow event path lists, retains required job `test`, and adds `tools/audit/validate_mc_ci_trigger_scope.py` plus negative controls. The validator uses `yaml.BaseLoader` to preserve the literal `on` key and fails closed when either event route or the required job is missing.

Supporting fixture run before repository write: `python -m pytest -q tests/test_mc_ci_trigger_scope.py` -> `3 passed in 0.06s`; CLI validator -> `PASS`. Exact-head repository CI is required before merge and must not be inferred from this local fixture.

### Four sequential AI review votes

- **Source/simulation lead — ACCEPT routing repair / BLOCK runtime authorisation:** routing Geant4 changes into static tests is necessary, but there is still no external compile/link/run.
- **Adversarial CI reviewer — REJECT current omission / ACCEPT broad `geant4/**` route:** a narrow `src_patch/**` route would still miss physics-changing configs, macros and setup scripts.
- **Independent statistics/validation reviewer — ACCEPT deterministic routing gate / BLOCK physics inference:** no stochastic source or detector observable is tested here.
- **Claims/provenance reviewer — ACCEPT CI precondition / BLOCK CL-021 promotion:** required repository checks cannot substitute for executable/input/seed/thread provenance.

### Next highest-value child

Resume `ARU-MC-CS-COMPILED-PROVENANCE-001`: construct a fail-closed build/run front door that pins or verifies the external hibeam_g4 commit/tree, re-verifies the exact reviewed `ScatteringGenerator.hh/.cc` bytes immediately before compilation, binds Geant4/compiler/CMake/run-manager/thread mode, verifies `dedx_p_in_CD2.txt` SHA-256 `9c2dd0d42473a6ffb96ec317a26d97815699d6b9ced6d3c46e65093d0114cb7b` and Table-VI SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, records seed/event count, and executes compiled hostile source/stopping fixtures. Historical S21 evidence identifies one inspected external source commit as `b73ea2a1bd2419e7c4a25a3bf23a419ad619234c`, but that historical observation is not a production pin for future runs.

No beam data, production MC, B2/B8, PID, penetration, timing, energy, pile-up, ESS, p-value, rate or detector-performance result changes in this atom.

# Latest Handoff

## Selected atom: required PR validation cannot be path-filtered

Protected `main` began this atom at `e4c924b901b37093f7b66eaf8d1d1dad07ea3498`, after coordination-only PR #1193 passed MC Validation run `31437027034` and was squash-merged. The configured-source readiness milestone remains static/software only; #1182/#1178/#1179 and CL-021 are still open/gated.

### Defect and stronger mechanism

Protected `main` requires status `test`. Before repair, `.github/workflows/mc_validation_ci.yml` path-filtered both `push` and `pull_request` and omitted `geant4/**`. PR #1192 is the concrete witness: exact head `bef24345e815152e22523a44b708c4359ad2958f` modifies only three `geant4/src_patch/**` files and has no workflow run. The same PR also restores `if(event->GetEventID()==0) EnsureFilesLoaded();`, undoing validated per-instance readiness; it was therefore closed rather than merged.

Authoritative GitHub Actions documentation states that path filters determine whether a `push`/`pull_request` workflow runs, and that a required workflow skipped by path filtering leaves its check pending and blocks merge. Therefore simply adding one more directory to a finite pull-request allow-list is not the stable fix. PR #1194 now makes `pull_request` **unfiltered**, retains scoped push routing with `geant4/**`, and requires job `test`.

`tools/audit/validate_mc_ci_trigger_scope.py` schema `ccb_mc_ci_trigger_scope_v2` fails closed on any required-PR `paths`/`paths-ignore`, a missing Geant4 push route, or a missing `test` job. Supporting deterministic fixture execution: `python -m pytest -q tests/test_mc_ci_trigger_scope.py` -> **4 passed in 0.05s**; CLI -> **PASS** with `pull_request.unfiltered=true`, `push.pattern_present=true`, `required_job=test`. Exact-head repository CI remains required before merge.

### Four sequential AI review votes

- **Source/simulation lead — ACCEPT routing repair / BLOCK runtime authorisation:** every PR can now enter static validation, but no external Geant4 compile/link/run is established.
- **Adversarial CI reviewer — REJECT finite required-PR path allow-lists / ACCEPT unfiltered PR event:** another omitted material directory would otherwise recreate the same skipped-required-check mechanism.
- **Independent statistics/validation reviewer — ACCEPT deterministic routing gate / BLOCK physics inference:** no generated source or detector observable is tested.
- **Claims/provenance reviewer — ACCEPT CI precondition / BLOCK CL-021 promotion:** required repository checks cannot substitute for executable/input/seed/thread provenance.

### Next highest-value child

Resume `ARU-MC-CS-COMPILED-PROVENANCE-001`: construct a fail-closed build/run front door that pins or verifies the external hibeam_g4 commit/tree, re-verifies the exact reviewed `ScatteringGenerator.hh/.cc` bytes immediately before compilation, binds Geant4/compiler/CMake/run-manager/thread mode, verifies `dedx_p_in_CD2.txt` SHA-256 `9c2dd0d42473a6ffb96ec317a26d97815699d6b9ced6d3c46e65093d0114cb7b` and Table-VI SHA-256 `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc`, records seed/event count, and executes compiled hostile source/stopping fixtures. Historical S21 evidence identifies one inspected external source commit as `b73ea2a1bd2419e7c4a25a3bf23a419ad619234c`, but that historical observation is not a production pin for future runs.

No beam data, production MC, B2/B8, PID, penetration, timing, energy, pile-up, ESS, p-value, rate or detector-performance result changes in this atom.

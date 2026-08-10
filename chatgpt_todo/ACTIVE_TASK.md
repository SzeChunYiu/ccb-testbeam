# Active Task

- **Task ID:** `ARU-CI-G4-TRIGGER-001` / concern `CI-G4-ROUTE-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `e4c924b901b37093f7b66eaf8d1d1dad07ea3498` after validated coordination PR #1193.
- **Parent dependency:** #1182 / `ARU-MC-CS-COMPILED-PROVENANCE-001`; #1178, #1179 and CL-021 remain open/gated.
- **Selected routing defect:** protected `main` requires job `test`, but the pre-repair `MC Validation CI` path-filters `pull_request` and omits `geant4/**`. GitHub documents that a workflow skipped by path filtering leaves its associated required check pending, so a finite PR path allow-list conflicts with an always-required check.
- **Live negative-control witness:** PR #1192 exact head `bef24345e815152e22523a44b708c4359ad2958f` changes only three `geant4/src_patch/**` files and has zero associated workflow runs. Its patch is independently stale because it restores an `event->GetEventID()==0` initialization gate already removed by validated main; #1192 was closed, not merged.
- **Preferred repair on PR #1194:** make `pull_request` unfiltered; retain scoped `push.paths` but add `geant4/**`; require job `test`; add schema `ccb_mc_ci_trigger_scope_v2` and negative controls for a PR path filter, missing Geant4 push route and missing `test` job.
- **Supporting deterministic fixture:** `python -m pytest -q tests/test_mc_ci_trigger_scope.py` -> `4 passed in 0.05s`; validator CLI -> `PASS` with `pull_request.unfiltered=true`, `push.pattern_present=true`, `required_job=test`. Exact-head GitHub CI is still required before merge.
- **Scientific boundary:** scheduling the existing job is only a static/Python routing precondition. The workflow still does not compile/link/run `geant4/src_patch`; no generator distribution, detector response or DATA/MC claim is authorised by this atom.
- **Next child after routing closure:** `ARU-MC-CS-COMPILED-PROVENANCE-001` — pinned external hibeam_g4 source/tree, exact installed-source verification immediately before build, compiler/Geant4/build/run-manager/thread provenance, immutable source/stopping inputs, seeds/event count, compiled hostile fixtures and content-bound run manifest.
- **Status:** `ACTIVE / REQUIRED_PR_PATH_FILTER_REMOVAL_IMPLEMENTED / GEANT4_PUSH_ROUTE_IMPLEMENTED / EXACT_HEAD_CI_REQUIRED / COMPILED_GEANT4_BLOCKED / EXECUTABLE_PROVENANCE_BLOCKED / MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

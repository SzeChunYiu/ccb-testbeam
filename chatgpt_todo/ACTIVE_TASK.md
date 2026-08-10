# Active Task

- **Task ID:** `ARU-CI-G4-TRIGGER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Protected main inspected:** `e4c924b901b37093f7b66eaf8d1d1dad07ea3498` after validated coordination PR #1193.
- **Parent dependency:** #1182 / `ARU-MC-CS-COMPILED-PROVENANCE-001`; #1178, #1179 and CL-021 remain open/gated.
- **Selected routing defect:** the required `MC Validation CI` workflow defines branch-protection job `test` but, before this branch, neither `push.paths` nor `pull_request.paths` included `geant4/**`.
- **Live negative-control witness:** PR #1192 exact head `bef24345e815152e22523a44b708c4359ad2958f` changes only three `geant4/src_patch/**` files and has zero associated workflow runs. Its patch is also scientifically stale because it restores an `event->GetEventID()==0` initialization gate already removed by validated main.
- **Bounded repair on branch:** add `geant4/**` to both workflow trigger events; add `validate_mc_ci_trigger_scope.py` plus regressions that fail closed on a missing event route or missing `test` job; archive the exact routing/claim boundary.
- **Supporting deterministic fixture:** `python -m pytest -q tests/test_mc_ci_trigger_scope.py` -> `3 passed in 0.06s`; validator CLI -> `PASS`. Exact-head GitHub CI is still required before merge.
- **Scientific boundary:** scheduling the existing job is only a static/Python routing precondition. The workflow still does not compile/link/run `geant4/src_patch`; no generator distribution, detector response or DATA/MC claim is authorised by this atom.
- **Next child after routing closure:** `ARU-MC-CS-COMPILED-PROVENANCE-001` — pinned external hibeam_g4 source/tree, exact installed-source verification immediately before build, compiler/Geant4/build/run-manager/thread provenance, immutable source/stopping inputs, seeds/event count, compiled hostile fixtures and content-bound run manifest.
- **Status:** `ACTIVE / DETERMINISTIC_ROUTING_FIX_IMPLEMENTED / EXACT_HEAD_CI_REQUIRED / COMPILED_GEANT4_BLOCKED / EXECUTABLE_PROVENANCE_BLOCKED / MANIFEST_BLOCKED / DETECTOR_INFERENCE_BLOCKED`

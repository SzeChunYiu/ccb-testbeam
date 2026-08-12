# Latest Handoff

## SiPM build provenance now requires the nested source worktree; CI exposed and repaired a stale fixture assumption

Selected atom `ARU-SIPM-BUILD-SUBMODULE-WORKTREE-IDENTITY-001` remains `ACTIVE / CI-REPAIR` under open parent #977 in draft PR #1294.

The scientific/provenance defect is deterministic: a clean superproject plus an exact mode-160000 gitlink does not prove that `geant4/single_stave/sipm` is a materialized independent Git repository. Temporary Git fixtures showed both an empty gitlink directory and ordinary non-Git descendant content can leave the outer `git status --porcelain=v1 --untracked-files=all` exactly clean. The authorising receipt therefore upgrades to schema `ccb-single-stave-build-receipt/2` and requires semantic nested top-level equality, nested `HEAD == superproject gitlink`, and nested tracked/untracked cleanliness, while retaining the existing outer-tree, executable SHA-256, CMake/toolchain and Geant4-sentinel checks. Schema v1 is intentionally non-authorising for this stronger source-worktree claim.

Exact-head CI provided a useful cross-atom falsifier rather than a reason to weaken the contract. MC Validation run `31575340395`, job `94046076935`, on exact head `ae594fdd27a8863ded632ffc21451a200c6d854c` checked out exact `ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`, passed the core conflict-marker guard, GNU C++ 13.3.0 build, 7/7 core CTests, ruff, and close-intent governance. Full pytest returned `1 failed, 2152 passed, 2 skipped, 8 xfailed, 1 xpassed`; enforcement correctly failed because `PYTEST_STATUS=1`. The sole failure was `test_env_regrid_is_external_content_bound_and_leaves_source_clean`: the existing campaign fixture created a fresh detached superproject worktree but never materialized its nested SiPM repository before asking receipt v2 to authorise the source.

That failure localizes a test-harness assumption, not a production-source exception. Commit `9232bed4b14531eb2bafa16ebcedb529b5a0347b` changes only the fixture: it derives the expected core SHA from the isolated worktree gitlink, clones the already checked-out CI core locally with `--no-checkout`, checks out the expected SHA detached, and verifies nested top-level and HEAD before creating the receipt. This avoids network dependence inside the unit test and preserves fail-closed production semantics. An independent local Git construction also confirmed that an exact nested local clone at the gitlink leaves both nested and outer tracked/untracked status clean; this is Git/software evidence only.

Concurrent protected main advanced through `f0b41ba5a1d38bc01a0eb96be015f875b8363772`. To avoid force-push/rebase and avoid importing stale coordination files, the atom branch was advanced with merge commit `363cf3fd770c48aca578cf48e37fd7de1234ab72`: first parent is the atom branch, second parent is protected main, and the merge tree was explicitly rebuilt from current main plus only `sipm_build_receipt.py`, the campaign fixture correction, the focused nested-worktree test, and the immutable atom archive. Fresh coordination is being layered after that merge.

### Four sequential AI reviews

**Build/provenance lead — ACCEPT v2 source-worktree contract / REVISE fixture / BLOCK #977 COMPLETE.** The strongest counter-hypothesis is that gitlink plus outer cleanliness is sufficient. Empty/non-Git gitlink-path fixtures falsify it. Residuals include ignored/generated files and time-of-check races.

**Adversarial mechanism reviewer — REJECT gitlink-only or path-exists fallback / ACCEPT semantic nested repository identity.** The exact CI failure is expected behavior when the nested source is absent. A test-only exception would reintroduce the provenance hole.

**Independent validation reviewer — ACCEPT failed exact-head CI as informative falsifier / REVISE pending final-head protected CI / BLOCK detector inference.** The failure was isolated to one cross-atom fixture while core CTests and 2152 unrelated pytest cases passed; the repaired branch is not authorising until its final head is green.

**Claims/provenance reviewer — KEEP #977 OPEN/PARTIAL.** This child binds intended/materialized source but does not close ignored-source influence, compiler/link invocation identity, runtime library loading, historical output authenticity, #1072 requested/effective operating-point semantics, or #1067 measured-electronics calibration authorization.

Next gate: record the CI-correction addendum, require protected MC Validation on the resulting exact PR head, and only then mark #1294 ready/merge with an expected-head guard. The next highest-value child after integration is `ARU-SIPM-BUILD-IGNORED-SOURCE-INFLUENCE-001`: determine whether ignored/generated files under `ccb-sipm-core` can enter the build and, if so, bind or reject them rather than assuming `git status --untracked-files=all` is complete source attestation.

No beam bytes, production Geant4 population, measured electronics/SiPM calibration, DATA↔MC observable, timing/PID metric, rate, efficiency, ESS, p-value, or detector-performance claim was generated or promoted.

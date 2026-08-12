# Latest Handoff

## SiPM build provenance now requires the nested source worktree; the CI fixture has been corrected without weakening that invariant

Selected atom `ARU-SIPM-BUILD-SUBMODULE-WORKTREE-IDENTITY-001` remains `ACTIVE / FINAL-HEAD-CI` under open parent #977 in draft PR #1294.

The deterministic provenance defect is unchanged: a clean superproject plus an exact mode-160000 gitlink does not prove that `geant4/single_stave/sipm` is a materialized independent Git repository. Temporary Git fixtures showed an empty gitlink directory and ordinary non-Git descendant content can leave the outer `git status --porcelain=v1 --untracked-files=all` exactly clean. Receipt schema `ccb-single-stave-build-receipt/2` therefore requires semantic nested top-level equality, nested `HEAD == superproject gitlink`, and nested tracked/untracked cleanliness, while retaining outer-tree, executable SHA-256, CMake/toolchain and Geant4-sentinel checks. Schema v1 is non-authorising for this stronger claim.

Exact-head CI first falsified a cross-atom fixture assumption. MC Validation run `31575340395`, job `94046076935`, on exact head `ae594fdd27a8863ded632ffc21451a200c6d854c` passed exact core checkout/build, 7/7 core CTests, ruff and close-intent governance, but full pytest returned `1 failed, 2152 passed, 2 skipped, 8 xfailed, 1 xpassed`; enforcement correctly failed with `PYTEST_STATUS=1`. The sole failure was the campaign launcher fixture: it created an isolated detached superproject worktree but did not materialize its nested SiPM repository before asking receipt v2 to authorise the source.

The production contract was not weakened. Commit `9232bed4b14531eb2bafa16ebcedb529b5a0347b` repairs only the fixture by deriving the expected core from the isolated gitlink, cloning the already checked-out CI core locally with `--no-checkout`, checking out that exact SHA detached, and verifying nested top-level/HEAD before receipt creation. Exact-head MC Validation run `31576734549`, job `94050431288`, then completed `SUCCESS` on that corrected fixture head.

Protected main advanced twice while the atom was active. The branch was first merged forward to `main@f0b41ba5a1d38bc01a0eb96be015f875b8363772`; exact integration head `5088b6742906cfd1aeedc19371eda0db8d57a4c2` passed both push MC Validation `31577201842` and pull-request MC Validation `31577204678`. Main then advanced through #1295 to `d7f0b9e2927d3c2edf1894f75e3863e992e0cf7e`. Rather than force-push/rebase or absorb stale coordination conflicts, the branch was advanced again with merge commit `3a16bbac3a7b8df9b90e7a6b4422889a5c7a9f79`, whose first parent is the prior atom head, second parent is current protected main, and whose tree is rebuilt from current main plus only the bounded atom files. This handoff update is the last planned content change before final-head CI.

### Four sequential AI reviews

**Build/provenance lead — ACCEPT v2 source-worktree contract and corrected fixture / BLOCK #977 COMPLETE.** Strongest counter-hypothesis: gitlink plus outer cleanliness is sufficient. Empty/non-Git gitlink-path fixtures falsify it. Residuals: ignored/generated files and time-of-check races.

**Adversarial mechanism reviewer — REJECT gitlink-only/path-exists/test-only exceptions / ACCEPT semantic nested repository identity.** The original CI failure is expected behavior for an absent nested source. A fallback would recreate the confirmed source-to-build hole.

**Independent validation reviewer — ACCEPT exact-head correction evidence / REVISE pending final post-#1295 head / BLOCK detector inference.** `9232bed4...` and `5088b674...` were executed successfully, but branch protection must be satisfied again after the #1295 merge-forward and this coordination update.

**Claims/provenance reviewer — KEEP #977 OPEN/PARTIAL.** This child binds materialized source identity; it does not close ignored-source influence, compiler/link invocation identity, runtime library loading, historical output authenticity, #1072 requested/effective operating-point semantics, or #1067 measured-electronics calibration authorization.

Immediate gate: require all protected contexts on the exact current PR head after this handoff commit; if they pass and the branch remains mergeable against protected main, mark #1294 ready and merge with an expected-head guard. The next highest-value child is `ARU-SIPM-BUILD-IGNORED-SOURCE-INFLUENCE-001`: determine whether ignored/generated files under `ccb-sipm-core` can enter compilation and therefore require content binding or explicit rejection.

No beam bytes, production Geant4 population, measured electronics/SiPM calibration, DATA↔MC observable, timing/PID metric, rate, efficiency, ESS, p-value, or detector-performance claim was generated or promoted.

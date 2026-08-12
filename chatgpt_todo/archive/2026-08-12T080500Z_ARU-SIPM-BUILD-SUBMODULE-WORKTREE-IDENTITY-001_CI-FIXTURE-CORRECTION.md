# ARU-SIPM-BUILD-SUBMODULE-WORKTREE-IDENTITY-001 — CI fixture correction

Status: **ACTIVE / FINAL-HEAD-CI REQUIRED**  
Parent: #977  
PR: #1294  
First failing exact head: `ae594fdd27a8863ded632ffc21451a200c6d854c`  
Fixture-correction commit: `9232bed4b14531eb2bafa16ebcedb529b5a0347b`  
Current-main integration merge: `363cf3fd770c48aca578cf48e37fd7de1234ab72`

## Exact CI falsifier

MC Validation run `31575340395`, job `94046076935`, executed exact head `ae594fdd27a8863ded632ffc21451a200c6d854c`.

Observed execution:

- recursive checkout materialized exact `ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`;
- conflict-marker guard: PASS;
- CMake configured with GNU C++ 13.3.0;
- core build: PASS;
- CTest: 7/7 PASS;
- curated ruff: PASS;
- scientific close-intent gates: PASS;
- full pytest: `1 failed, 2152 passed, 2 skipped, 8 xfailed, 1 xpassed, 18 warnings in 149.42s`;
- enforcement: FAIL with `SIPM_CORE_STATUS=0`, `RUFF_STATUS=0`, `PYTEST_STATUS=1`.

The sole failure was `tests/test_sipm_campaign_manifest.py::test_env_regrid_is_external_content_bound_and_leaves_source_clean`.

## Failure mechanism

The existing campaign regression created an isolated detached superproject source with

`git -C <ROOT> worktree add --detach <source> HEAD`

and verified that outer status was clean. It then immediately invoked `sipm_build_receipt.py create`.

Receipt schema v2 introduced by this atom correctly requires the nested source to be a materialized independent Git worktree at the superproject gitlink. `git worktree add` materializes the superproject but not the nested submodule checkout. Therefore the fixture itself constructed a state that the new authorising contract is designed to reject.

This is a cross-atom test-harness incompatibility. It is not evidence that the nested-worktree source invariant should be weakened.

## Competing repairs

1. **Permit gitlink-only receipts when the nested path is absent.** Rejected: this recreates the confirmed provenance hole.
2. **Skip the nested check only under pytest/CI.** Rejected: test-only authorisation semantics would no longer exercise production behavior.
3. **Initialize the nested repository from its remote URL inside the test.** Scientifically acceptable but unnecessarily introduces network/credential availability as a unit-test nuisance variable.
4. **Materialize an offline exact nested repository from the already checked-out CI core and detach it at the isolated superproject gitlink SHA.** Survives: source bytes are available locally, the exact intended commit is checked explicitly, the nested Git top-level is independent, and the unit fixture remains network-free.

## Implemented correction

Commit `9232bed4b14531eb2bafa16ebcedb529b5a0347b` changes only the campaign fixture. After creating the isolated superproject worktree it:

1. reads the mode-160000 gitlink from the isolated worktree HEAD;
2. clones `ROOT/geant4/single_stave/sipm` locally with `--local --no-checkout` into the isolated gitlink path;
3. checks out the exact expected core SHA detached;
4. requires `rev-parse --show-toplevel` to resolve to the isolated core path;
5. requires nested `HEAD` to equal the gitlink SHA;
6. only then creates the authorising build receipt and runs the campaign-launcher regression.

An independent temporary-Git construction executed the same local-clone topology and confirmed exact nested top-level/HEAD plus empty nested and outer tracked/untracked status. This is deterministic Git/software evidence, not detector evidence.

## Current-main compatibility

Protected main advanced concurrently. To avoid a force-push/rebase and avoid carrying stale `ACTIVE_TASK.md`/`HANDOFF.md` conflicts, merge commit `363cf3fd770c48aca578cf48e37fd7de1234ab72` has first parent `9232bed4...`, second parent protected `main@f0b41ba5a1d38bc01a0eb96be015f875b8363772`, and a tree rebuilt from that current main plus only the bounded source/test/archive files. Fresh coordination was added after the merge.

## Four sequential AI review passes

### A. Build/provenance lead
Evidence: receipt v2 implementation, first CI log, failing campaign fixture, exact gitlink/nested-source semantics.  
Counter-hypothesis: outer clean + gitlink is enough.  
Falsifier: empty/non-Git gitlink paths remain outer-clean.  
Residual: ignored/generated nested files; TOCTOU.  
Vote: **ACCEPT v2 contract / REVISE fixture / BLOCK #977 COMPLETE**.

### B. Adversarial mechanism reviewer
Evidence: test-only and gitlink-only alternative repairs, Git parent-discovery behavior.  
Counter-hypothesis: an absent nested repo can be treated as equivalent if the executable self-reports the expected core label.  
Falsifier: source-to-binary provenance cannot be established from an unmaterialized source plus a label; that is the exact missing variable this child measures.  
Residual: executable/link/runtime-loader attestation remains separate.  
Vote: **REJECT fallback exceptions / ACCEPT materialized exact nested source**.

### C. Independent validation reviewer
Evidence: exact-head CI localized one failure while core CTests, ruff and 2152 unrelated pytest tests passed; no RNG in the source identity fixtures.  
Counter-hypothesis: a red full suite means the production v2 implementation itself is invalid.  
Falsifier: the only failing trace originates from the campaign test's missing nested worktree before receipt creation.  
Residual: corrected exact final head still needs protected execution.  
Vote: **ACCEPT failed CI as informative falsifier / REVISE pending final-head CI / BLOCK detector inference**.

### D. Claims/provenance reviewer
Evidence: #977 acceptance criteria and provenance chain #1280/#1282/#1284/#1285.  
Counter-hypothesis: this child completes detector-response provenance.  
Falsifier: ignored-source influence, compiler/link invocation identity, runtime library set, historical-output authenticity, #1072, and #1067 remain material.  
Residual: historical schema-v1 receipts require separate governance.  
Vote: **KEEP #977 OPEN/PARTIAL; no detector claim promotion**.

## Next gate and children

The exact final PR head after this addendum and coordination update must pass every required protected MC Validation context before #1294 can be marked ready or merged. The next highest-value child is `ARU-SIPM-BUILD-IGNORED-SOURCE-INFLUENCE-001`, because ordinary `git status --untracked-files=all` deliberately excludes ignored files and the build influence of such files has not yet been established.

No beam bytes, production Geant4 population, measured SiPM/electronics calibration, DATA↔MC result, timing/PID metric, rate, efficiency, ESS, p-value, or detector-performance quantity was generated or promoted.

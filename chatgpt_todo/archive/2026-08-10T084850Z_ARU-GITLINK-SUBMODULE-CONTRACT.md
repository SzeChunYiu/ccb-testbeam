# ARU — Gitlink / submodule repository-integrity contract

- **Task ID:** `ARU-GITLINK-SUBMODULE-CONTRACT-001`
- **Session stamp:** `2026-08-10T084850Z`
- **Initial remote main:** `ca6fa3155394e99cc62e2a16d3bd7a4df10c809b`
- **Issue:** #1152
- **Branch:** `fix/repo-gitlink-submodule-contract`
- **Scientific boundary:** repository checkout/provenance integrity only; no beam, MC, reconstruction, calibration, timing, PID, energy, penetration, pile-up, or detector-performance quantity is changed or inferred here.

## Atomic universe

A Git tree entry with mode `160000` is treated by Git as a gitlink/submodule pointer. A clean checkout therefore has two coupled metadata objects:

```text
G = {p | p is tracked with Git mode 160000}
M = {p | p is declared as a submodule path in .gitmodules}
```

The repository-integrity invariant selected for this atom is exact path equality:

```text
G = M
<=>
G \ M = empty AND M \ G = empty.
```

A local AI-agent worktree directory is not repository content and must also satisfy the recurrence-prevention condition:

```text
.claude/worktrees/** is ignored by the repository ignore policy.
```

This contract does not claim that path equality alone proves a submodule remote, commit, or scientific dependency is semantically correct. Those are separable child atoms if contradictory evidence appears.

## Verified evidence

At `main@ca6fa3155394e99cc62e2a16d3bd7a4df10c809b`, repository-tree inspection found three gitlinks:

1. `.claude/worktrees/agent-ab8006f38e5298275`
2. `.claude/worktrees/agent-ad26366bc4a0411a0`
3. `geant4/single_stave/sipm`

`.gitmodules` declares only `geant4/single_stave/sipm`, currently bound to `https://github.com/SzeChunYiu/ccb-sipm-core.git`. The two `.claude/worktrees/...` entries are therefore orphan gitlinks with respect to the canonical submodule declaration.

History inspection shows that both orphan paths first entered repository history in commit `d1140f18ba1588bfffa3229ddc69511a6df46620` (`fix(s00): enforce atomic report-directory publication (#1122)`), which is unrelated to intended submodule dependency management. This supports the accidental-worktree-artifact mechanism and contradicts the hypothesis that they are deliberate declared dependencies.

The previous successful MC Validation workflow emitted a checkout post-job warning that Git could not find a `.gitmodules` URL for a `.claude/worktrees/...` path. The scientific/software test gate itself still succeeded; this atom therefore treats the condition as a reproducibility/checkout-metadata defect, not as evidence that detector tests failed.

## Mechanism universe and collapse

### H1 — deliberate hidden submodules
Rejected. There are no matching `.gitmodules` declarations, and the first-introduction commit is an S00 publication change rather than dependency-management work.

### H2 — local Claude worktrees accidentally staged as gitlinks
Selected as the best-supported mechanism. The path namespace is local-agent specific, both entries appeared together in an unrelated implementation commit, and they violate the declared-submodule path set.

### H3 — harmless tree metadata because checkout succeeds
Rejected as an authority argument. A checkout warning is already observable, and clean/submodule-aware tooling must not rely on undefined metadata coincidence.

### H4 — remove only the two current paths
Necessary but insufficient. Without an ignore rule and a machine-checkable invariant, a future local worktree can be reintroduced under a new generated name.

### H5 — remove current paths + ignore recurrence + validate exact path equality
Selected implementation. This fixes the present state and adds a deterministic negative gate for future orphan/missing gitlinks.

## Implemented repair

On `fix/repo-gitlink-submodule-contract`:

- remove the two tracked `.claude/worktrees/...` mode-160000 entries;
- preserve the real `geant4/single_stave/sipm` submodule;
- add `.claude/worktrees/` to `.gitignore`;
- add `tools/audit/validate_gitlink_submodule_contract.py`;
- add `tests/test_gitlink_submodule_contract.py`.

The validator obtains tracked gitlinks from `git ls-files --stage -z`, parses `.gitmodules`, checks exact set equality, and checks the synthetic local-worktree path with `git check-ignore --no-index`. It fails closed on malformed index records, non-stage-0 records, malformed `.gitmodules`, duplicate declared submodule paths, orphan gitlinks, declared submodules that are not gitlinks, or a missing ignore rule.

The test universe includes:

- ordinary tracked file + gitlink parser separation;
- orphan gitlink -> fail;
- configured submodule without gitlink -> fail;
- local `.claude/worktrees/...` path not ignored -> fail;
- duplicate `.gitmodules` paths -> controlled failure;
- malformed index record -> controlled failure;
- repository-level positive control requiring exactly the canonical `geant4/single_stave/sipm` gitlink and the recurrence ignore rule.

## Tree-level verification performed before CI

After the deletion commit, root-tree inspection of the branch no longer shows a `.claude` entry, and branch contents still expose `geant4/single_stave/sipm` as a submodule. The branch `.gitmodules` file is unchanged from main and points that path to `ccb-sipm-core.git`.

No local pytest execution is claimed in this run because the authenticated GitHub connector supplies repository reads/writes but not a checked-out private repository shell. Exact-head GitHub Actions CI is therefore the execution gate before merge.

## Four sequential expert passes

### 1. Git / reproducibility lead — ACCEPT implementation shape, pending exact-head CI
Evidence: current tree modes, `.gitmodules`, introduction history, branch tree after deletion. Strongest counter-hypothesis: the orphan entries are deliberate dependencies. Falsifier: require matching `.gitmodules` declarations and provenance; none exists. Residual uncertainty: execution of the new validator in the repository CI environment remains pending.

### 2. Adversarial repository-metadata reviewer — ACCEPT with recurrence guard
Evidence: `.gitignore` lacked the local worktree namespace; plain deletion alone would not prevent a renamed recurrence. Strongest counter-hypothesis: ignore rules are sufficient. Falsifier: `git add -f` can bypass an ignore rule, so the validator/test is still required. Residual uncertainty: future dependency semantics beyond path identity are outside this atom.

### 3. CI / validation reviewer — BLOCK merge until exact-head CI
Evidence: deterministic test design and existing workflow coverage. Strongest counter-hypothesis: source inspection alone is sufficient. Falsifier: import/package/Git-version behavior can differ in Actions. Acceptance requires exact-head lint/test success and absence of the orphan-submodule checkout warning on the repaired head.

### 4. Claims / provenance reviewer — ACCEPT repository-integrity correction; no scientific promotion
Evidence: defect is confined to Git metadata and recurrence protection. Strongest counter-hypothesis: a clean checkout fix changes scientific evidence. Falsifier: no data, model, detector, result, claim-ledger numerical value, or publication statistic is modified. Residual uncertainty: parent scientific work remains independent.

## Child atoms and cross-scale compatibility

- **CI environment compatibility:** prove the validator executes under the repository Actions image and exact-head test suite.
- **Checkout warning closure:** verify the repaired PR workflow no longer reports the orphan `.claude/worktrees/...` submodule warning.
- **Submodule semantic identity:** not spawned as a new issue here because current `.gitmodules` and GitHub submodule metadata both identify `ccb-sipm-core`; revisit only on contradictory evidence.
- **S00 authority transaction:** independent higher-value scientific-software parent remains #1110/#1146; this Git repair must not be confused with S00 scientific closure.

## Acceptance

Close #1152 only when:

1. branch tree has no `.claude/worktrees/...` gitlinks;
2. `G == M == {geant4/single_stave/sipm}` on the checked-out PR head;
3. `.claude/worktrees/` is ignored;
4. focused validator tests and the repository-required exact-head CI pass;
5. the repaired workflow no longer emits the orphan-submodule checkout warning;
6. the legitimate submodule remains intact;
7. the repair is present on remote `main`.

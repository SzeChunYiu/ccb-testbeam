# Latest Handoff

## Session

- **Task ID:** `ARU-GITLINK-SUBMODULE-CONTRACT-001`
- **Stamp:** `2026-08-10T084850Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial main:** `ca6fa3155394e99cc62e2a16d3bd7a4df10c809b`
- **Issue:** #1152
- **Branch:** `fix/repo-gitlink-submodule-contract`
- **Status:** `IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED`

## Selected atom

```text
tracked Git tree
-> mode-160000 gitlink paths G
-> .gitmodules declared paths M
-> checkout/submodule metadata
-> reproducible repository state
```

The fail-closed path-identity invariant is:

```text
G == M
```

with both difference sets empty. Local Claude worktree paths must additionally be ignored so generated agent worktrees are not normal repository content.

## Verified evidence

At the initial main SHA, tree inspection found three tracked mode-160000 entries: two `.claude/worktrees/agent-*` paths plus the legitimate `geant4/single_stave/sipm` submodule. `.gitmodules` declares only the SiPM path and currently points it to `https://github.com/SzeChunYiu/ccb-sipm-core.git`.

History inspection shows both orphan worktree gitlinks first entered in `d1140f18ba1588bfffa3229ddc69511a6df46620` (`fix(s00): enforce atomic report-directory publication (#1122)`), unrelated to dependency management. This supports accidental local-worktree staging rather than deliberate hidden submodules.

The earlier successful workflow emitted a checkout post-job warning for a `.claude/worktrees/...` submodule path missing from `.gitmodules`. The scientific/software test gate still succeeded; this is therefore treated as repository-integrity/reproducibility evidence, not as a failed detector-validation run.

## Repair on branch

- removed `.claude/worktrees/agent-ab8006f38e5298275` and `.claude/worktrees/agent-ad26366bc4a0411a0` as tracked gitlinks;
- preserved `geant4/single_stave/sipm`;
- added `.claude/worktrees/` to `.gitignore`;
- added `tools/audit/validate_gitlink_submodule_contract.py`;
- added `tests/test_gitlink_submodule_contract.py`;
- preserved the full derivation/review in `chatgpt_todo/archive/2026-08-10T084850Z_ARU-GITLINK-SUBMODULE-CONTRACT.md`.

The validator uses `git ls-files --stage -z` for tracked gitlinks, parses `.gitmodules`, requires exact set equality, and checks the recurrence-ignore rule with `git check-ignore --no-index`. It fails closed on orphan gitlinks, configured paths that are not gitlinks, malformed metadata, duplicate submodule paths, or a missing ignore rule.

## Adversarial controls

- orphan gitlink -> fail;
- configured submodule without gitlink -> fail;
- unignored `.claude/worktrees/...` -> fail;
- malformed Git index record -> controlled failure;
- duplicate `.gitmodules` path -> controlled failure;
- positive repository integration control -> exactly the legitimate SiPM path remains and local worktrees are ignored.

A plain `.gitignore` rule is deliberately not treated as sufficient, because forced staging can bypass an ignore rule. The validator is the merge-time recurrence gate.

## Four sequential expert passes

- **Git/reproducibility lead — ACCEPT implementation shape, pending exact-head CI.** The current contradiction is removed at tree level and the legitimate declared submodule remains.
- **Adversarial repository-metadata reviewer — ACCEPT with validator.** Deletion alone would be insufficient; generated path names can recur, so both ignore and exact-set validation are required.
- **CI/validation reviewer — BLOCK merge until exact-head Actions.** Source inspection cannot prove import/Git-version/workflow behavior. Required gate: exact-head lint/tests plus disappearance of the orphan-submodule checkout warning.
- **Claims/provenance reviewer — ACCEPT repository repair / no scientific promotion.** This branch changes Git metadata and audit machinery only; it does not alter or validate detector data, simulation, reconstruction, or public scientific quantities.

## Execution boundary

No local pytest result is claimed because this automation runtime has authenticated GitHub repository access but no checked-out private-repository shell. Exact-head GitHub Actions is the execution authority for this change.

## Coordination / unresolved work

- Close #1152 only after the repaired head passes required CI, the checkout warning is absent, and the merge is present on remote main.
- The S00 authority transaction remains independent and open under #1110/#1146; return there after this bounded repository-integrity leaf is validated.
- #1149 same-bytes consumer migration and real selected-table benchmark also remain independent.

## Scientific boundary

No raw ROOT population was rescanned, no S00 count was regenerated, no Geant4 simulation was run, and no timing/PID/penetration/energy/pile-up/detector-performance quantity changed.

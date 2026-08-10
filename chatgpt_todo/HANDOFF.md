# Latest Handoff

## Session

- **Task ID:** `ARU-GITLINK-SUBMODULE-CONTRACT-001`
- **Stamp:** `2026-08-10T084850Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial main:** `ca6fa3155394e99cc62e2a16d3bd7a4df10c809b`
- **Current validated merge-base main:** `9c68115e1d374c61dad8b83dfc99569c8b0fb84b`
- **Issue:** #1152
- **Branch:** `fix/repo-gitlink-submodule-contract`
- **Status:** `IMPLEMENTED / CI-VALIDATED ON MERGE REF / PROTECTED-MERGE RECHECK REQUIRED`

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
- extended MC Validation CI triggers to `.gitignore`, `.gitmodules`, and `.claude/worktrees/**` so force-added recurrence cannot bypass the validator;
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

- **Git/reproducibility lead — ACCEPT.** The orphan gitlinks are removed, the declared SiPM submodule remains, and the repository-level equality invariant is executable.
- **Adversarial repository-metadata reviewer — ACCEPT.** The recurrence hole at the CI trigger boundary was closed; deletion plus ignore plus exact-set validation is materially stronger than deletion alone.
- **CI/validation reviewer — ACCEPT implementation evidence / REQUIRE fresh protected-merge check.** MC Validation run 963 succeeded on synthetic merge commit `73923ec25cb7140bd62f43a9df93194056cbb932`, which merged exact head `8edfc1af4572dcd676b5e48819e22507a384ca93` into then-current main `9c68115e1d374c61dad8b83dfc99569c8b0fb84b`. Ruff passed; pytest reported `1266 passed, 1 skipped, 8 xfailed, 1 xpassed, 6 warnings`; checkout post-job cleanup no longer emitted the orphan-submodule warning. GitHub later regenerated the PR merge ref and the protected merge endpoint returned `Required status check "test" is expected`, so this handoff commit intentionally retriggers CI rather than bypassing branch protection.
- **Claims/provenance reviewer — ACCEPT repository repair / no scientific promotion.** This branch changes Git metadata and audit machinery only; it does not alter or validate detector data, simulation, reconstruction, or public scientific quantities.

## Execution boundary

MC Validation CI run 963 is a successful execution record for the repaired code on a merge ref containing main `9c68115e...`. The available job log confirms successful checkout, ruff, unit tests, enforcement, and post-checkout cleanup with no `No url found for submodule path` failure. The attempted squash merge was rejected by branch protection because GitHub expected a fresh required `test` status after regenerating the merge ref; this is treated as a gating-state change, not permission to bypass protection. The present handoff-only commit exists to trigger a fresh pull-request run for the current merge ref.

## Coordination / unresolved work

- Close #1152 only after the fresh required check succeeds and the merge is actually present on remote `main`.
- The S00 authority transaction remains independent and open under #1110; #1146 is already on main and must be included in any later producer-publication integration.
- #1149 same-bytes consumer migration and real selected-table benchmark also remain independent.

## Scientific boundary

No raw ROOT population was rescanned, no S00 count was regenerated, no Geant4 simulation was run, and no timing/PID/penetration/energy/pile-up/detector-performance quantity changed.

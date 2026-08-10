# Active Task

- **Task ID:** `ARU-GITLINK-SUBMODULE-CONTRACT-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T084850Z`
- **Initial remote main SHA:** `ca6fa3155394e99cc62e2a16d3bd7a4df10c809b`
- **Issue:** `#1152`.
- **Branch:** `fix/repo-gitlink-submodule-contract`.
- **Selected atom:** `tracked mode-160000 Git tree entries -> .gitmodules declaration -> clean-checkout/reproducibility authority`.
- **Verified defect on initial main:** two tracked `.claude/worktrees/...` gitlinks were not declared in `.gitmodules`; both were introduced by unrelated S00 commit `d1140f18ba1588bfffa3229ddc69511a6df46620`. The legitimate `geant4/single_stave/sipm` submodule is declared and remains intact.
- **Invariant:** `G = {tracked mode-160000 paths}` and `M = {.gitmodules paths}` must satisfy `G == M`; `.claude/worktrees/**` must remain local/ignored.
- **Implemented repair:** remove the two orphan worktree gitlinks; add `.claude/worktrees/` to `.gitignore`; add `tools/audit/validate_gitlink_submodule_contract.py` and focused regression tests.
- **Tree-level negative control:** post-deletion branch root has no `.claude` tree entry; the legitimate SiPM submodule remains visible at `geant4/single_stave/sipm`.
- **Expert votes before CI:** Git/reproducibility `ACCEPT implementation shape / pending CI`; adversarial metadata `ACCEPT with recurrence guard`; CI/validation `BLOCK merge until exact-head Actions`; claims/provenance `ACCEPT repository-integrity correction / no scientific promotion`.
- **Execution status:** no local pytest result is claimed because this runtime has GitHub connector access but no private checkout shell. Exact-head GitHub Actions is the execution authority before merge.
- **Scientific boundary:** no beam ROOT data, Geant4, S00 count regeneration, timing/PID/penetration/energy/pile-up result, detector model, or claim-ledger numerical value changed.
- **Next acceptance gate:** open PR, require exact-head CI success, verify the checkout no longer emits the orphan `.claude/worktrees/...` submodule warning, then merge and close #1152 only if the legitimate submodule remains intact.
- **Status:** `IMPLEMENTED_ON_BRANCH / EXACT_HEAD_CI_REQUIRED / NO_SCIENTIFIC_CLAIM_CHANGE`

# ARU-SIPM-CAMPAIGN-MANIFEST-CORE-SHA-SOURCE-001 — exact-head CI fixture correction

Status: `ACTIVE / PRE-CI`
Integration vehicle: draft PR #1284
Superseded test head: `4535a7742b3e45ed60ad7fc862ff9e5c0d2ed0cb`
Failed pull-request run: `31568703445`, job `94025888229`

## Exact observed failure

The scientific launcher repair itself was not falsified. Exact-head CI compiled and passed all 7/7 ccb-sipm-core CTests, curated ruff reported `All checks passed!`, and the full Python suite reached 100%. One new integration fixture failed because it incorrectly asserted that the *workflow checkout* must still be clean at pytest start.

Observed pre-test workflow side effects included modified tracked Python bytecode, editable-install metadata under `src/ccb_mc_validation.egg-info/`, and the workflow's own untracked `sipm_core.log`, `ruff.log`, and `pytest.log`. The failing suite summary was `1 failed, 2134 passed, 2 skipped, 8 xfailed, 1 xpassed, 18 warnings in 140.84s`; enforcement recorded `SIPM_CORE_STATUS=0`, `RUFF_STATUS=0`, `PYTEST_STATUS=1` and correctly failed the job.

## Atomic distinction

Production contract:

`campaign source checkout used by run_sensitivity_campaign.sh must be clean at manifest creation`.

Invalid test assumption:

`the repository-wide CI checkout must remain clean after package installation, prior tests, compilation and diagnostic logging`.

These are not equivalent. Weakening `require_clean_worktree()` to accommodate CI artifacts would destroy the production provenance invariant.

## Corrected falsifier

The launcher integration test now creates a fresh detached Git worktree from exact test `HEAD`, verifies that isolated source worktree is clean, runs the actual campaign launcher there with a non-default `CCB_GRID_PDE_SCALE="0.95 1.05"` and fake `sbatch`, verifies external generated-grid SHA-256 binding and unchanged isolated-worktree status, then removes the temporary worktree. CI's enclosing checkout may remain dirty from unrelated workflow side effects without weakening the production gate.

## Four-role review of the failure

- Detector-response/provenance lead: `REVISE test harness / ACCEPT production clean-source invariant`.
- Adversarial reviewer: `REJECT weakening require_clean_worktree`; strongest alternative is isolated exact-HEAD source fixture.
- Independent validator: `ACCEPT CI failure as informative falsifier / REVISE pending rerun`; the failed exact head is not merge-authorising.
- Claims/provenance reviewer: `KEEP #977/#1067 OPEN/PARTIAL`; no scientific or detector claim follows from fixture repair.

No production Geant4, ROOT, beam data, detector MC, calibration, timing/PID, rate, ESS or p-value participates.

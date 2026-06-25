# LUNARC MC Validation Production Status

Generated: 2026-06-25 06:48 UTC

## Current selected LUNARC run

- Run ID: `20260625T064500Z_full_input_artifacted`
- LUNARC job ID: `3316536`
- Terminal state: `COMPLETED`
- Exit code: `0:0`
- Node: `cn046`
- Elapsed: `00:01:01`
- Worktree: `/projects/hep/fs10/shared/nnbar/billy/worktrees/ccb-testbeam-origin-main`
- Code SHA at job completion: `7bd0a16` after PR #477.

## Inputs verified by LUNARC preflight

- MC ROOT: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
  - size: `677221620` bytes
  - sha256: `2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc`
- Pulse table: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz`
  - size: `9246625` bytes
  - sha256: `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`

## Completed stages in job 3316536

The SLURM log reports these stages completed with `rc=0`:

1. `preflight`
2. `plan`
3. `truth-build`
4. `MV0 digitizer`
5. `MV1 PID`
6. `MV2 energy`
7. `MV3 stopping`
8. `MV9 synthesis`

Study outputs were written under the LUNARC worktree:

- `reports/mc_validation/mv1_pid/study_result.json`
- `reports/mc_validation/mv2_energy/study_result.json`
- `reports/mc_validation/mv3_stopping_depth/study_result.json`
- `reports/mc_validation/mv9_synthesis/MV9_SYNTHESIS.md`

## Current study summaries

These are full-input production-run summaries from `CCB_MAX_ROOT_EVENTS=0`, not final thesis conclusions.

- MV1: `PRODUCTION`, `n_tracks=1000000`, `n_proton=100549`, `n_deuteron=141047`, `hgb_auc=0.997641986277693`, `hgb_purity_at_90eff=0.9953867753902006`, `logreg_auc=0.9764543474193328`.
- MV2: `PRODUCTION`, `n_proton_uncensored=69455`, `n_deuteron_uncensored=139074`, `proton_ekin_recon_res68=0.036531109473233174`, `deuteron_ekin_recon_res68=0.13319490593145097` in the current aggregate record representation.
- MV3: `PRODUCTION`, `n_sample_I=64762`, `n_sample_II=172336`; layer occupancy profiles were generated from trigger-derived `sample_label` rather than event-parity labels.
- MV4-MV8: `BLOCKED`, requiring calibrated MV0 digitized MC and truth-labelled waveform products.

## Failed attempts and fixes merged

- Job `3315947`: failed closed because the SLURM wrapper did not expose the source package on `PYTHONPATH`. Fixed by PR #471.
- Job `3316098`: failed closed because the wrapper defaulted to `base.yaml`, ignoring environment-expanded input paths. Fixed by PR #472.
- Job `3316255`: failed closed because MV1-MV3 production ROOT loading was intentionally blocked. Fixed by PR #473.
- After job `3316449`, MV9 initially summarized stale fixture registry values. Fixed by PR #474 and rerun on LUNARC. Full-input job `3316531` used the corrected MV9 path.


## Artifact validation

Validation was run on LUNARC after PR #479 with:

```bash
python scripts/mc_validation/run_pipeline.py --run-id 20260625T064500Z_full_input_artifacted validate --scope artifact --strict
```

Result: `PASS`. The generated files are:

- `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted/VALIDATION.json`
- `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted/VALIDATION_SUMMARY.md`

Checks passing in that summary: `job_state_completed`, `preflight_mc_root`, `preflight_data_pulses`, `MV1_study_result`, `MV2_study_result`, `MV3_study_result`, `MV9_synthesis`, and `slurm_logs_present`. This validates artifact consistency for MV1-MV3/MV9 only; it does not complete figures, notebooks, thesis, uncertainty/systematic arrays, or final release audit.


## Summary report and figures

After PR #481/#482, the compact run-summary generator was run on the selected LUNARC artifacted run. After PR #483, the same selected run was regenerated from the synced `origin/main` worktree to add the browser-readable HTML summary. Current regenerated artifacts are:

- `reports/mc_validation/summary/RUN_SUMMARY.md` (`526` bytes, refreshed 2026-06-25 17:27:54 +0200)
- `reports/mc_validation/summary/RUN_SUMMARY.html` (`1047` bytes, refreshed 2026-06-25 17:27:54 +0200)
- `reports/mc_validation/summary/metrics_table.csv` (`282` bytes, refreshed 2026-06-25 17:27:54 +0200)
- `figures/summary/study_support.svg` (`22092` bytes, refreshed 2026-06-25 17:27:57 +0200)
- `figures/summary/study_support.png` (`50970` bytes, refreshed 2026-06-25 17:27:57 +0200)
- `figures/summary/selected_metrics.svg` (`30534` bytes, refreshed 2026-06-25 17:27:57 +0200)
- `figures/summary/selected_metrics.png` (`106309` bytes, refreshed 2026-06-25 17:27:57 +0200)

All paths above are under `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted/`. Compact figures summarize study support and selected metrics only; they are not the final publication-quality figure suite required for thesis/release.

## Guardrails and remaining blockers

- This run is not a final release: strict validation, full uncertainty treatment, figures, notebooks, thesis rendering, and final audit have not passed.
- Full-input campaign `3316536` completed and persisted logs, JOB_STATE.json, MV1/MV2/MV3 results, and MV9 synthesis into `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts/20260625T064500Z_full_input_artifacted`. Remaining release work is validation/uncertainty/figures/notebooks/thesis/final audit, not another MV1-MV3 ROOT pass.
- MV4-MV8 remain blocked until calibrated digitized MC is available.
- No fixture/smoke value should be promoted as a physics conclusion.

## Resume / next commands

From `billy-old`, after verifying the LUNARC socket:

```bash
ssh -O check lunarc 2>/dev/null && echo Connected || /home/billy/lunarc-init.sh
ssh lunarc
cd /projects/hep/fs10/shared/nnbar/billy/worktrees/ccb-testbeam-origin-main
git fetch origin && git reset --hard origin/main
export CCB_MC_REPO="$PWD"
export CCB_MC_PYTHON=/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3
export CCB_MC_ROOT=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
export CCB_PULSE_TABLE=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
export CCB_ARTIFACT_ROOT=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/artifacts
export CCB_MAX_ROOT_EVENTS=0
sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch
```

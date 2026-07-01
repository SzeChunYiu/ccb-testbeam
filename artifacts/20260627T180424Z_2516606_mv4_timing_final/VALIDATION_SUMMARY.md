# MC Validation Artifact Validation Summary

- **Run ID:** `20260627T180424Z_2516606_mv4_timing_final`
- **Status:** **PASS**
- **Job ID:** `3326221`
- **Job state:** `COMPLETED` / `0:0`

## Checks

- job_state_completed: `PASS`
- preflight_mc_root: `PASS`
- preflight_data_pulses: `PASS`
- MV1_study_result: `PASS`
- MV2_study_result: `PASS`
- MV3_study_result: `PASS`
- MV4_study_result: `PASS`
- MV9_synthesis: `PASS`
- slurm_logs_present: `PASS`
- fixture_not_released: `PASS`

## Study support

- MV1: `PRODUCTION`, n_tracks=100000, hgb_auc=0.9972714960844432, hgb_purity_at_90eff=0.9961947042968131
- MV2: `PRODUCTION`, n_tracks=100000, proton_ekin_recon_res68=0.015380823301696338, deuteron_ekin_recon_res68=0.03677415671940314
- MV3: `PRODUCTION`, n_tracks=100000, 
- MV4: `PRODUCTION`, n_tracks=100000, 

## Release guardrail

This validation confirms artifact consistency for MV1-MV3 and MV9 only. It does not complete figures, notebooks, thesis, uncertainty/systematic arrays, or final release audit.

# P10h: Explicit-handle q-template support map

- **Ticket ID:** `1781026226.557.2d8e79db`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none

## Raw reproduction first

The selected B-stave pulse table was rebuilt from raw `HRDv` waveforms before any modeling.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## Methods

Split: run-family holdout. `holdout_sample_i` trains on run 64 and evaluates runs 44-57; `holdout_sample_ii` trains on runs 31-42 and evaluates runs 58-63 and 65. CIs bootstrap held-out runs.

Traditional method: frozen S01 empirical stave/amplitude-bin median templates plus train-only explicit-handle median residual tables. Handle bins below occupancy fall back to a looser handle table or the S01 template.

ML method: ridge and ExtraTrees multi-output template predictors using local explicit handles only. Grouped knockouts remove amplitude, shape, stave, or current-family handles. Shuffled-target and family-label sentinel models are evaluated on the same held-out rows. Monotonic constraints were not available in the local scikit-learn version used by this repo.

Metrics: q-template MSE, absolute live10 residual, absolute tail-sum residual, template-fit timing sigma68, and full timing RMS.

## Fold Summary

| fold              |   n_eval |   s01_empirical_q_mse |   handle_residual_q_mse |   extra_trees_q_mse |   delta_handle_minus_s01_q_mse | delta_handle_minus_s01_q_mse_ci              |   delta_extra_trees_minus_handle_q_mse | delta_extra_trees_minus_handle_q_mse_ci       |   handle_residual_fallback_rate |   extra_trees_timing_sigma68_ns |   delta_extra_trees_minus_handle_timing_sigma68_ns |
|:------------------|---------:|----------------------:|------------------------:|--------------------:|-------------------------------:|:---------------------------------------------|---------------------------------------:|:----------------------------------------------|--------------------------------:|--------------------------------:|---------------------------------------------------:|
| holdout_sample_i  |    27087 |              0.197323 |                0.135668 |           0.0745557 |                     -0.0616548 | [-0.06893726341413971, -0.05576224778775382] |                             -0.0611122 | [-0.06664419315379917, -0.053373396993214084] |                        0.227509 |                         1.60714 |                                          -0.535714 |
| holdout_sample_ii |    22603 |              0.164999 |                0.108853 |           0.0606202 |                     -0.0561465 | [-0.05962066532741743, -0.05278340636787882] |                             -0.0482326 | [-0.05140826871791753, -0.0446629754488986]   |                        0.110033 |                         1.25    |                                          -0.178571 |

## Support Regions

Most handle-favorable region summaries by weighted q-template MSE delta:

| dimension         | region             |   n_cells |   n_eval |   mean_delta_handle_minus_s01_q_mse |   mean_delta_extra_trees_minus_handle_q_mse |   mean_delta_extra_trees_minus_handle_timing_abs_ns |   handle_win_cell_fraction |   extra_trees_q_win_cell_fraction |
|:------------------|:-------------------|----------:|---------:|------------------------------------:|--------------------------------------------:|----------------------------------------------------:|---------------------------:|----------------------------------:|
| cfd_phase_region  | phase_mid          |       181 |    14279 |                          -0.087914  |                                  -0.0545267 |                                           -0.726241 |                   0.685083 |                          0.812155 |
| amp_region        | a1500_2200         |        93 |     7036 |                          -0.0754453 |                                  -0.0993202 |                                           -0.369865 |                   0.795699 |                          0.548387 |
| current_family    | high_20nA          |       253 |    24053 |                          -0.0742161 |                                  -0.0874281 |                                           -1.22007  |                   0.55336  |                          0.889328 |
| current_family    | sample_ii          |       303 |    21229 |                          -0.0542269 |                                  -0.0622537 |                                           -0.641481 |                   0.735974 |                          0.755776 |
| run_family        | sample_ii_analysis |       303 |    21229 |                          -0.0542269 |                                  -0.0622537 |                                           -0.641481 |                   0.735974 |                          0.755776 |
| cfd_phase_region  | phase_late         |       181 |    13477 |                          -0.0535216 |                                  -0.0530426 |                                           -1.26178  |                   0.679558 |                          0.861878 |
| rise_width_region | rise_wide          |       109 |     6945 |                          -0.0508854 |                                  -0.0810805 |                                           -2.18539  |                   0.568807 |                          0.816514 |
| rise_width_region | rise_mid           |       276 |    23178 |                          -0.0408228 |                                  -0.0130282 |                                           -0.517624 |                   0.702899 |                          0.724638 |

Least handle-favorable region summaries:

| dimension         | region          |   n_cells |   n_eval |   mean_delta_handle_minus_s01_q_mse |   mean_delta_extra_trees_minus_handle_q_mse |   mean_delta_extra_trees_minus_handle_timing_abs_ns |   handle_win_cell_fraction |   extra_trees_q_win_cell_fraction |
|:------------------|:----------------|----------:|---------:|------------------------------------:|--------------------------------------------:|----------------------------------------------------:|---------------------------:|----------------------------------:|
| tail_shape_region | tail_long       |       144 |    11618 |                         -0.00421939 |                                  -0.02035   |                                           -1.99755  |                   0.569444 |                          1        |
| saturation_region | boundary        |        60 |     5146 |                         -0.00531455 |                                  -0.0214772 |                                           -1.89419  |                   0.6      |                          0.966667 |
| saturation_region | saturated_proxy |        23 |     1901 |                         -0.00557955 |                                  -0.0320545 |                                           -3.66255  |                   0.391304 |                          0.913043 |
| amp_region        | a6800_10000     |        61 |     5343 |                         -0.0067266  |                                  -0.0277831 |                                           -2.65581  |                   0.557377 |                          0.934426 |
| stave             | B6              |        94 |     5884 |                         -0.0161776  |                                  -0.0419337 |                                           -0.257599 |                   0.56383  |                          0.691489 |
| amp_region        | a2200_3200      |       101 |     8356 |                         -0.0174226  |                                  -0.0245553 |                                           -0.320882 |                   0.574257 |                          0.792079 |
| amp_region        | a4700_6800      |       108 |     8048 |                         -0.0195533  |                                  -0.0277143 |                                           -0.850522 |                   0.481481 |                          0.916667 |
| stave             | B8              |        63 |     3058 |                         -0.0209925  |                                  -0.0456056 |                                           -0.657946 |                   0.349206 |                          0.84127  |

## Leakage Audit

| fold              | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | extra_trees_beats_handle_q_ci   | shuffled_target_beats_real   | family_label_sentinel_beats_real   | leakage_alarm   |
|:------------------|:-------------------------|-------------------------:|:-----------------------------|:--------------------------------|:-----------------------------|:-----------------------------------|:----------------|
| holdout_sample_i  | []                       |                        0 | False                        | True                            | False                        | False                              | False           |
| holdout_sample_ii | []                       |                        0 | False                        | True                            | False                        | False                              | False           |

A result is treated as too-good only when the ML-minus-traditional q-template CI is wholly below zero. In this run, sentinel alarms are reported in `leakage_checks.csv`; any fold with a shuffled-target or family-label sentinel beating the real model is not promotable as a physics support claim.

## Finding

Explicit handle residuals have limited promotable support: at least one fold improves over S01 by q-template CI, but support is region-specific. ExtraTrees beats the traditional handle method in at least one fold, subject to the sentinel audit.

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `fold_run_metrics.csv`, `fold_summary.csv`, `support_map.csv`, `support_region_summary.csv`, `model_diagnostics.csv`, `handle_occupancy.csv`, and `leakage_checks.csv`.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10h_1781026226_557_2d8e79db_support_map.py --config configs/p10h_1781026226_557_2d8e79db_support_map.yaml
```

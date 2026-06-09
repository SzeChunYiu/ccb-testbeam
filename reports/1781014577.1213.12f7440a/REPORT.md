# Study report: S18d - Sample IV leave-two-run ML stress tests

- **Ticket:** `1781014577.1213.12f7440a`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 58-65
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18d_1781014577_1213_12f7440a_leave_two_ablation.py --config configs/s18d_1781014577_1213_12f7440a.json`

## Question

Question: is the S18c leave-one-run Sample IV ML narrowing robust to stricter same-period validation? Expected information gain: rerun A1-A3 with leave-two-runs-out and feature ablations (no peak, no tail, no Sample-IV indicator), report held-out run bootstrap CIs and leakage checks; no row-level splits.

## Reproduction first

The S18c Sample IV A1-A3 number was reproduced from raw `HRDv` before the stricter stress test:

| quantity                  |   expected |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |  127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduced definition is `n=127`, robust width `1.794 ns`, and Gaussian core sigma `1.992 ns` in the +/-2.5 ns fit window.

## Split and methods

The stress test uses only Sample IV data. For each of the 21 unordered pairs of analysis runs, both runs are held out; the model trains on run 64 plus the five remaining analysis runs. Each event is predicted in six leave-two-run-out folds, always with its run absent from training, and the primary table averages those six residual predictions before run-bootstrap scoring.

The traditional method is CFD20 with a log-amplitude polynomial in A1 and A3. The ML method is standardized ridge regression on amplitude, area, peak, tail, and a Sample-IV analysis indicator, with ablations removing peak, tail, or the indicator. Alpha is selected by run-group CV within the training runs only.

## Primary metrics

| method                    |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |
|:--------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|
| traditional               |       127 |           1.63377 |            1.352   |             1.72617 |         1.87473 |       1.49751 |
| ml_full                   |       127 |           1.38404 |            1.08431 |             1.47466 |         1.43225 |       1.24497 |
| ml_no_peak                |       127 |           1.35449 |            1.18538 |             1.4512  |         1.92534 |       1.26916 |
| ml_no_tail                |       127 |           1.41317 |            1.16213 |             1.63269 |         1.99197 |       1.35237 |
| ml_no_sample_iv_indicator |       127 |           1.37124 |            1.08009 |             1.47464 |         1.55652 |       1.24364 |

Best point estimate: **ml_no_peak** at **1.354 ns**. The full ML model is `1.384 ns` versus the traditional `1.634 ns`.

## Paired deltas

Negative values favor the method named before `_minus_`.

| comparison                                  |   ci_low_ns |   ci_high_ns |   p_value |
|:--------------------------------------------|------------:|-------------:|----------:|
| ml_full_minus_traditional                   |  -0.451707  |  -0.0922924  |     0.006 |
| ml_no_peak_minus_traditional                |  -0.380921  |  -0.0611362  |     0.016 |
| ml_no_tail_minus_traditional                |  -0.364674  |   0.00277758 |     0.054 |
| ml_no_sample_iv_indicator_minus_traditional |  -0.453396  |  -0.114877   |     0.006 |
| ml_no_peak_minus_ml_full                    |  -0.116898  |   0.192879   |     0.824 |
| ml_no_tail_minus_ml_full                    |  -0.0778595 |   0.287893   |     0.222 |
| ml_no_sample_iv_indicator_minus_ml_full     |  -0.0151683 |   0.0091606  |     0.576 |

## Run-held-out summary

|   run |   n_pairs |   raw_robust_width_ns |   traditional_robust_width_ns |   n_leave_two_predictions |   ml_full_robust_width_ns |   ml_no_peak_robust_width_ns |   ml_no_tail_robust_width_ns |   ml_no_sample_iv_indicator_robust_width_ns |
|------:|----------:|----------------------:|------------------------------:|--------------------------:|--------------------------:|-----------------------------:|-----------------------------:|--------------------------------------------:|
|    58 |        25 |              1.11541  |                       1.2588  |                         6 |                  0.973222 |                     1.05903  |                     1.24958  |                                    0.969237 |
|    59 |        11 |              0.472692 |                       1.18291 |                         6 |                  0.775436 |                     0.83179  |                     0.766093 |                                    0.773259 |
|    60 |        11 |              1.00479  |                       1.09672 |                         6 |                  0.735177 |                     0.795093 |                     0.700622 |                                    0.735223 |
|    61 |        18 |              1.7659   |                       1.62314 |                         6 |                  1.16513  |                     1.30448  |                     1.29199  |                                    1.16339  |
|    62 |         7 |              1.41823  |                       1.15039 |                         6 |                  1.04665  |                     1.48875  |                     1.03765  |                                    1.05208  |
|    63 |        28 |              1.47109  |                       1.35754 |                         6 |                  1.24861  |                     1.39229  |                     1.43693  |                                    1.2469   |
|    65 |        27 |              1.65561  |                       1.82506 |                         6 |                  1.64474  |                     1.3732   |                     1.71775  |                                    1.65457  |

## Fold stability

| heldout_runs   | train_runs        |   n_test_pairs |   traditional_robust_width_ns |   ml_full_robust_width_ns |   ml_full_alpha |   ml_no_peak_robust_width_ns |   ml_no_peak_alpha |   ml_no_tail_robust_width_ns |   ml_no_tail_alpha |   ml_no_sample_iv_indicator_robust_width_ns |   ml_no_sample_iv_indicator_alpha |
|:---------------|:------------------|---------------:|------------------------------:|--------------------------:|----------------:|-----------------------------:|-------------------:|-----------------------------:|-------------------:|--------------------------------------------:|----------------------------------:|
| 58,59          | 60,61,62,63,64,65 |             36 |                       1.32854 |                  0.96529  |            0.01 |                     0.985516 |               0.01 |                     1.09762  |               0.01 |                                    0.960984 |                              0.01 |
| 58,60          | 59,61,62,63,64,65 |             36 |                       1.48651 |                  1.02031  |            0.01 |                     1.18127  |               0.1  |                     1.16414  |               0.1  |                                    1.02031  |                              0.01 |
| 58,61          | 59,60,62,63,64,65 |             43 |                       1.52615 |                  1.19769  |            0.1  |                     1.22945  |               0.1  |                     1.37377  |               0.1  |                                    1.20109  |                              0.1  |
| 58,62          | 59,60,61,63,64,65 |             32 |                       1.42193 |                  1.07501  |            0.1  |                     1.16644  |               0.1  |                     1.34481  |               0.1  |                                    1.07538  |                              0.1  |
| 58,63          | 59,60,61,62,64,65 |             53 |                       1.35264 |                  1.25432  |            0.1  |                     1.26422  |               0.1  |                     1.37454  |               0.1  |                                    1.2374   |                              0.1  |
| 58,65          | 59,60,61,62,63,64 |             52 |                       1.60376 |                  1.37615  |            0.1  |                     1.32543  |               0.1  |                     1.63465  |               0.1  |                                    1.37708  |                              0.1  |
| 59,60          | 58,61,62,63,64,65 |             22 |                       1.16536 |                  1.02292  |            0.01 |                     1.06633  |               0.01 |                     0.899531 |               0.01 |                                    1.02265  |                              0.01 |
| 59,61          | 58,60,62,63,64,65 |             29 |                       1.48354 |                  1.18412  |            0.01 |                     1.36111  |               0.01 |                     1.18038  |               0.01 |                                    1.18655  |                              0.01 |
| 59,62          | 58,60,61,63,64,65 |             18 |                       1.14652 |                  1.08801  |            0.1  |                     1.18501  |               0.1  |                     0.911901 |               0.1  |                                    1.09021  |                              0.1  |
| 59,63          | 58,60,61,62,64,65 |             39 |                       1.40792 |                  1.21716  |            0.01 |                     1.2018   |               0.01 |                     1.33478  |               0.1  |                                    1.21109  |                              0.01 |
| 59,65          | 58,60,61,62,63,64 |             38 |                       1.71584 |                  1.37838  |            0.01 |                     1.30851  |               0.01 |                     1.42049  |               0.01 |                                    1.37751  |                              0.01 |
| 60,61          | 58,59,62,63,64,65 |             29 |                       1.39295 |                  1.20107  |            0.01 |                     1.27693  |               0.1  |                     1.28336  |               0.1  |                                    1.19456  |                              0.01 |
| 60,62          | 58,59,61,63,64,65 |             18 |                       1.329   |                  0.834791 |            0.01 |                     1.09416  |               0.01 |                     1.00151  |               0.1  |                                    0.834021 |                              0.01 |
| 60,63          | 58,59,61,62,64,65 |             39 |                       1.5579  |                  1.25557  |            0.01 |                     1.31267  |               0.1  |                     1.3895   |               0.1  |                                    1.25628  |                              0.01 |
| 60,65          | 58,59,61,62,63,64 |             38 |                       1.49525 |                  1.40393  |            0.01 |                     1.29205  |               0.1  |                     1.5563   |               0.1  |                                    1.40379  |                              0.01 |
| 61,62          | 58,59,60,63,64,65 |             25 |                       1.52575 |                  1.21763  |            0.1  |                     1.45806  |               0.1  |                     1.3041   |               0.1  |                                    1.21974  |                              0.1  |
| 61,63          | 58,59,60,62,64,65 |             46 |                       1.55846 |                  1.43922  |            0.1  |                     1.46223  |               0.1  |                     1.55995  |               0.1  |                                    1.42494  |                              0.1  |
| 61,65          | 58,59,60,62,63,64 |             45 |                       1.80286 |                  1.40186  |            0.1  |                     1.37084  |               0.1  |                     1.56018  |               0.01 |                                    1.40913  |                              0.1  |
| 62,63          | 58,59,60,61,64,65 |             35 |                       1.55265 |                  1.33811  |            0.1  |                     1.30626  |               0.1  |                     1.4676   |               0.1  |                                    1.34158  |                              0.1  |
| 62,65          | 58,59,60,61,63,64 |             34 |                       1.76033 |                  1.49733  |            0.1  |                     1.45696  |               0.1  |                     1.67292  |               0.1  |                                    1.50028  |                              0.1  |
| 63,65          | 58,59,60,61,62,64 |             55 |                       1.64257 |                  1.37167  |            0.1  |                     1.35904  |               0.1  |                     1.54219  |               0.1  |                                    1.3806   |                              0.1  |

## Leakage checks

Leakage flags: **0**.

| scope                  | check                                    | value                  | flag   |
|:-----------------------|:-----------------------------------------|:-----------------------|:-------|
| full                   | forbidden_feature_overlap                |                        | False  |
| no_peak                | forbidden_feature_overlap                |                        | False  |
| no_tail                | forbidden_feature_overlap                |                        | False  |
| no_sample_iv_indicator | forbidden_feature_overlap                |                        | False  |
| split                  | fold_train_test_run_overlap              | False                  | False  |
| split                  | unexpected_event_prediction_multiplicity | 6                      | False  |
| split                  | duplicate_event_within_fold              | 0                      | False  |
| full                   | shuffled_target_group_cv_r2_mean         | -0.17687921360398184   | False  |
| no_peak                | shuffled_target_group_cv_r2_mean         | -0.11277377106095263   | False  |
| no_tail                | shuffled_target_group_cv_r2_mean         | -0.19171716587285875   | False  |
| no_sample_iv_indicator | shuffled_target_group_cv_r2_mean         | -0.1463458453628265    | False  |
| ml_full                | too_good_to_ignore_delta_ci_ns           | [-0.451707,-0.0922924] | False  |
| ml_full                | sub_ns_width_suspicion                   | 1.3840412051684754     | False  |

No adopted metric uses row-level splits, and every ML feature set excludes run, event, raw residual, and timing columns. The shuffled-target checks are run-group CV checks on training folds, not row-split acceptance metrics.

## Conclusion

The S18c same-period ML narrowing survives the leave-two-run-out stress test. The full ML leave-two-run-out delta versus traditional is CI `[-0.452, -0.092] ns` with p=`0.006`. Feature ablations do not expose a hidden dependence on peak, tail, or the Sample-IV indicator strong enough to rescue a secure ML win under this stricter same-period validation.

No follow-up ticket was appended because S18e already queued closely related S18f/S18g follow-ups on A-stack channel controls and constrained timewalk ranking.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `train_run_manifest.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `run_heldout_summary.csv`, `leave_two_fold_summary.csv`, `heldout_pair_predictions.csv`, `event_mean_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.

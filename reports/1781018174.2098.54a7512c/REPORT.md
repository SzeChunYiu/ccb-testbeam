# S05e: B2 covariance after saturation-correction features

- **Ticket:** 1781018174.2098.54a7512c
- **Worker:** testbeam-laptop-1
- **Raw input:** `data/root/root`
- **Config:** `configs/s05e_1781018174_2098_54a7512c_b2_saturation_covariance.yaml`
- **Input checksum manifest:** `input_sha256.csv`

## Question

Rerun the S05c B-stack covariance decomposition with explicit P07d-style B2 saturation/recovery features. Compare B2-containing versus downstream-only covariance before and after correction using run-held-out bootstrap CIs. No Monte Carlo was used.

## Raw ROOT reproduction first

The S05c count anchors were reproduced from `h101/HRDv` before fitting any model.

| quantity                             |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses              |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses |         125096 |       125096 |       0 |           0 | True   |

Pair-row counts:

| pair   |   n_pair_rows |
|:-------|--------------:|
| B2-B4  |         26387 |
| B2-B6  |         12626 |
| B2-B8  |          4943 |
| B4-B6  |         12196 |
| B4-B8  |          4542 |
| B6-B8  |          4790 |

## Methods

Traditional baseline is the S05c pair-median centered CFD20 residual. Strong traditional correction is leave-one-run-out Ridge using amplitude, area, tail, peak, and explicit B2 saturation/recovery features: near-peak width, high-ADC sample count, saturation excess, recovery tail, and post-peak fall.

ML correction is leave-one-run-out ExtraTrees over the same saturation-aware features plus all B-stave waveform summaries. Both fitted methods hold out complete runs; run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels are excluded.

## Primary Before/After Covariance

| stage                                 | method                       |   B2_containing_mean_abs_cov_ns2 |   B2_ci_low_ns2 |   B2_ci_high_ns2 |   downstream_mean_abs_cov_ns2 |   downstream_ci_low_ns2 |   downstream_ci_high_ns2 |
|:--------------------------------------|:-----------------------------|---------------------------------:|----------------:|-----------------:|------------------------------:|------------------------:|-------------------------:|
| before_raw_s05c                       | raw_pair_median              |                        1041.84   |        738.303  |        1319.61   |                       15.9882 |                 5.19251 |                  33.1767 |
| after_traditional_saturation_features | traditional_saturation_ridge |                         212.783  |        158.702  |         266.739  |                       35.7723 |                26.2452  |                  52.3143 |
| after_ml_saturation_features          | ml_extra_trees_saturation    |                          25.1875 |         18.7525 |          32.0136 |                       11.2458 |                 2.08065 |                  27.164  |

The raw S05c covariance is B2 dominated: B2-containing mean absolute pair covariance is `1041.84` ns^2 with 95% run-bootstrap CI `[738.30, 1319.61]`, while downstream-only is `15.99` ns^2 with CI `[5.19, 33.18]`.

After explicit saturation features, Ridge reduces B2-containing covariance to `212.78` ns^2 but broadens residual widths. The ML correction reduces B2-containing covariance to `25.19` ns^2 with CI `[18.75, 32.01]`; downstream-only after ML is `11.25` ns^2.

## Held-out Residual Metrics

| method                       | subset          |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                                         |
|:-----------------------------|:----------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:-----------------------------------------------------------------------------|
| raw_pair_median              | all             |         65484 |       21 |      2.08184 |             1.78587 |             11.2236  |      20.675   |             0.141653  | pair-median centered raw CFD20 residual                                      |
| raw_pair_median              | B2_containing   |         43956 |       21 |      3.51234 |             1.85918 |             19.2979  |      24.817   |             0.202612  | pair-median centered raw CFD20 residual                                      |
| raw_pair_median              | downstream_only |         21528 |       21 |      1.73256 |             1.68908 |              1.76878 |       6.53666 |             0.0171869 | pair-median centered raw CFD20 residual                                      |
| traditional_saturation_ridge | all             |         65484 |       21 |      6.6249  |             6.16144 |              7.98909 |      11.5773  |             0.419477  | leave-run-out Ridge residual correction with explicit B2 saturation features |
| traditional_saturation_ridge | B2_containing   |         43956 |       21 |      7.04995 |             6.34473 |              9.42595 |      13.0679  |             0.435458  | leave-run-out Ridge residual correction with explicit B2 saturation features |
| traditional_saturation_ridge | downstream_only |         21528 |       21 |      5.66287 |             5.20061 |              6.47938 |       7.78701 |             0.36283   | leave-run-out Ridge residual correction with explicit B2 saturation features |
| ml_extra_trees_saturation    | all             |         65484 |       21 |      1.35219 |             1.20959 |              1.7162  |       5.54421 |             0.084891  | leave-run-out ExtraTrees residual model with explicit saturation features    |
| ml_extra_trees_saturation    | B2_containing   |         43956 |       21 |      1.61552 |             1.36426 |              2.43864 |       6.18087 |             0.117481  | leave-run-out ExtraTrees residual model with explicit saturation features    |
| ml_extra_trees_saturation    | downstream_only |         21528 |       21 |      1.03498 |             1.00205 |              1.11403 |       3.94129 |             0.0181159 | leave-run-out ExtraTrees residual model with explicit saturation features    |

Run-bootstrap ML minus raw sigma68 delta is `-0.730` ns with CI `[-8.643, -0.543]`. ML minus saturation-aware Ridge is `-5.273` ns with CI `[-6.112, -4.920]`.

## Stave Decomposition

|      var_B2 |    cov_B2_B4 |     cov_B2_B6 |    cov_B2_B8 |     var_B4 |   cov_B4_B6 |    cov_B4_B8 |     var_B6 |   cov_B6_B8 |     var_B8 |   offdiag_rmse_ns2 |   n_offdiag_covariances | method                       | scope              |   B2_variance_minus_downstream_mean_ns2 |
|------------:|-------------:|--------------:|-------------:|-----------:|------------:|-------------:|-----------:|------------:|-----------:|-------------------:|------------------------:|:-----------------------------|:-------------------|----------------------------------------:|
| 166.497     | -100.696     | -113.321      | -118.976     | 34.2436    |  21.3232    |  10.8859     | 35.0676    | 21.8624     | 43.1141    |         10.4259    |                      15 | raw_pair_median              | event_level_pooled |                             129.022     |
|   5.40607   |   -3.33382   |   -3.81215    |   -3.66618   |  0.78651   |   0.93462   |   0.82618    |  0.786241  |  1.30505    |  0.767476  |          1.4413    |                      15 | raw_pair_median              | run_median_level   |                               4.626     |
|  45.7504    |  -30.9589    |  -28.6658     |  -31.876     | 22.7248    |  -1.6818    | -12.8089     | 16.1585    | -1.9694     | 23.3272    |          4.09776   |                      15 | traditional_saturation_ridge | event_level_pooled |                              25.0135    |
|   0.617882  |   -0.680582  |   -0.46217    |   -0.0930125 |  0.764293  |   0.234922  |  -1.08293    |  0.0837496 |  0.0597485  |  0.558095  |          0.871987  |                      15 | traditional_saturation_ridge | run_median_level   |                               0.14917   |
|   7.62655   |   -4.99122   |   -5.1817     |   -5.08017   |  5.16216   |  -2.03179   |  -3.30131    |  3.81109   | -0.408698   |  4.39509   |          1.1293    |                      15 | ml_extra_trees_saturation    | event_level_pooled |                               3.17043   |
|   0.0381514 |   -0.0392798 |   -0.00803061 |   -0.0289924 |  0.0332282 |  -0.0205015 |  -0.00667517 |  0.0135618 |  0.00140847 |  0.0171296 |          0.0536153 |                      15 | ml_extra_trees_saturation    | run_median_level   |                               0.0168449 |

## Saturation Strata

| method                       | stratum            |   n_pair_rows |   n_runs |   b2_amp_cut_adc |   median_b2_sat_count |   median_b2_sat_excess_adc |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_abs_pair_cov_ns2 |
|:-----------------------------|:-------------------|--------------:|---------:|-----------------:|----------------------:|---------------------------:|-------------:|--------------------:|---------------------:|------------------------:|
| raw_pair_median              | all_B2_containing  |         43956 |       21 |           nan    |                     0 |                       0    |      3.51234 |             1.86187 |             19.8635  |               1041.84   |
| raw_pair_median              | B2_sat_count_gt0   |         11981 |       21 |           nan    |                     6 |                    1786    |     30.7684  |            18.3163  |             41.6596  |               1272.58   |
| raw_pair_median              | B2_sat_count_eq0   |         31975 |       21 |           nan    |                     0 |                       0    |      1.56566 |             1.46511 |              1.8759  |                531.742  |
| raw_pair_median              | B2_amp_top_decile  |          4396 |       21 |          6615.75 |                     8 |                    4342.75 |     41.6906  |            26.9488  |             46.868   |               1210.1    |
| raw_pair_median              | B2_amp_lower_90pct |         39560 |       21 |          6615.75 |                     0 |                       0    |      1.96778 |             1.64223 |              8.95029 |                954.014  |
| traditional_saturation_ridge | all_B2_containing  |         43956 |       21 |           nan    |                     0 |                       0    |      7.04995 |             6.33324 |              8.80177 |                212.783  |
| traditional_saturation_ridge | B2_sat_count_gt0   |         11981 |       21 |           nan    |                     6 |                    1786    |     11.5965  |            10.431   |             12.5327  |                182.492  |
| traditional_saturation_ridge | B2_sat_count_eq0   |         31975 |       21 |           nan    |                     0 |                       0    |      5.68891 |             5.37075 |              6.78861 |                248.891  |
| traditional_saturation_ridge | B2_amp_top_decile  |          4396 |       21 |          6615.75 |                     8 |                    4342.75 |     10.8135  |            10.0071  |             11.4609  |                114.795  |
| traditional_saturation_ridge | B2_amp_lower_90pct |         39560 |       21 |          6615.75 |                     0 |                       0    |      6.62106 |             6.09061 |              8.74361 |                255.495  |
| ml_extra_trees_saturation    | all_B2_containing  |         43956 |       21 |           nan    |                     0 |                       0    |      1.61552 |             1.36483 |              2.49613 |                 25.1875 |
| ml_extra_trees_saturation    | B2_sat_count_gt0   |         11981 |       21 |           nan    |                     6 |                    1786    |      3.57052 |             3.12574 |              3.94399 |                 22.1263 |
| ml_extra_trees_saturation    | B2_sat_count_eq0   |         31975 |       21 |           nan    |                     0 |                       0    |      1.19246 |             1.10428 |              1.42234 |                 32.337  |
| ml_extra_trees_saturation    | B2_amp_top_decile  |          4396 |       21 |          6615.75 |                     8 |                    4342.75 |      3.82461 |             3.55973 |              4.05384 |                 28.7311 |
| ml_extra_trees_saturation    | B2_amp_lower_90pct |         39560 |       21 |          6615.75 |                     0 |                       0    |      1.41612 |             1.24996 |              2.00562 |                 27.7989 |

## Leakage Checks

| check                                 |   value | pass   | interpretation                                                                                                                                    |
|:--------------------------------------|--------:|:-------|:--------------------------------------------------------------------------------------------------------------------------------------------------|
| run_split_event_overlap               | 0       | True   | train and held-out event ids are disjoint because whole runs are held out                                                                         |
| ml_features_exclude_forbidden_columns | 1       | True   | ML inputs exclude run, event, time_ns, raw residual, target residual, and pair-derived timing labels; saturation inputs are waveform-derived only |
| actual_ml_sigma68_ns                  | 1.35219 | True   | nominal leave-run-out ML residual width                                                                                                           |
| shuffled_train_target_ml_sigma68_ns   | 4.37455 | True   | target permutation inside train folds should not reproduce the nominal ML width                                                                   |
| intentional_target_echo_sigma68_ns    | 0       | True   | positive leakage sentinel; a leaked target would be unrealistically narrow                                                                        |

The shuffled-target ML control is wider than nominal, the positive target-echo sentinel remains intentionally impossible, and whole-run splitting gives zero train/test event overlap. The large ML improvement is therefore treated as plausible only with the reported leakage probes and run-held-out intervals.

## Finding

The S05c raw covariance headline reproduces exactly from raw ROOT. B2-containing pair covariance starts far above downstream-only covariance. Explicit B2 saturation/recovery features remove most of that excess in the held-out ML correction, but not in the Ridge residual width; the remaining B2 covariance after ML is still larger than downstream-only and should be interpreted as residual B2-local structure, not a detector-wide common timing mode.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `before_after_covariance_summary.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `saturation_strata.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and PNG figures.

# S05e: B2 saturation features in covariance model

- **Ticket:** 1781016280.4691.3d911c1d
- **Worker:** testbeam-laptop-1
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05e_1781016280_4691_3d911c1d_b2_saturation_covariance.yaml`
- **Raw input:** `data/root/root`

## Question

Rerun the S05c hierarchical run/stave covariance model after adding explicit B2 saturation/recovery features, separating high-amplitude B2 waveform pathology from irreducible detector-local covariance. No A-stack coincidences or Monte Carlo are used.

## Reproduction from raw ROOT

The S05c gate was reproduced first from `h101/HRDv`: median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, CFD20 timing, and the configured analysis runs.

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

The target is the B-stack pair residual `t_right - t_left - TOF`, using 2 cm layer spacing and 0.078 ns/cm. All model comparisons are leave-one-run-out; the held-out run is never used for fitting or hyperparameter selection.

Traditional: pair-median centered CFD20 residuals reproduce the S05c covariance baseline. The strong traditional method is a leave-one-run-out Ridge model with the S05c amplitude/area/tail features plus explicit B2 high-ADC plateau, near-peak width, saturation excess, post-peak fall, and recovery-tail terms.

ML: ExtraTrees over the same saturation-aware pair features plus all four B-stave waveform summaries. It excludes run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels. The hyperparameters are fixed in the config before evaluation, and every prediction is for a held-out run.

## Held-out residual benchmark

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

The run-bootstrap ML minus raw S05c baseline sigma68 delta is `-0.730` ns with 95% CI `[-8.643, -0.543]` and two-sided p=`0.000`. Against the saturation-aware Ridge, the ML delta is `-5.273` ns with 95% CI `[-6.112, -4.920]`.

Strong traditional all-run sigma68 is `6.625` ns; saturation-aware ML all-run sigma68 is `1.352` ns.

## Hierarchical covariance

Pair-pair covariance summaries from held-out residuals:

| method                       | subset               |   n_covariances |   n_runs |   mean_abs_cov_ns2 |   mean_abs_cov_ci_low_ns2 |   mean_abs_cov_ci_high_ns2 |   median_abs_cov_ns2 |   signed_mean_cov_ns2 |
|:-----------------------------|:---------------------|----------------:|---------:|-------------------:|--------------------------:|---------------------------:|---------------------:|----------------------:|
| ml_extra_trees_saturation    | all_pair_covariances |             300 |       20 |            13.3494 |                   7.75111 |                    22.5481 |             2.51047  |              7.12424  |
| ml_extra_trees_saturation    | both_B2_containing   |              60 |       20 |            25.1875 |                  18.7525  |                    32.0136 |            21.1583   |             24.6419   |
| ml_extra_trees_saturation    | both_downstream_only |              60 |       20 |            11.2458 |                   2.08065 |                    27.164  |             0.929166 |             10.4232   |
| ml_extra_trees_saturation    | mixed_B2_downstream  |             180 |       20 |            10.1045 |                   4.15846 |                    19.9326 |             1.98707  |              0.185367 |
| raw_pair_median              | all_pair_covariances |             300 |       20 |           228.535  |                 171.181   |                   285.942  |            15.0688   |            223.089    |
| raw_pair_median              | both_B2_containing   |              60 |       20 |          1041.84   |                 738.303   |                  1319.61   |          1189        |           1041.84     |
| raw_pair_median              | both_downstream_only |              60 |       20 |            15.9882 |                   5.19251 |                    33.1767 |             1.63686  |             15.411    |
| raw_pair_median              | mixed_B2_downstream  |             180 |       20 |            28.2816 |                  16.5427  |                    45.7431 |            10.4275   |             19.3972   |
| traditional_saturation_ridge | all_pair_covariances |             300 |       20 |            72.1416 |                  55.8113  |                    88.1165 |            32.5667   |             37.3386   |
| traditional_saturation_ridge | both_B2_containing   |              60 |       20 |           212.783  |                 158.702   |                   266.739  |           191.961    |            212.783    |
| traditional_saturation_ridge | both_downstream_only |              60 |       20 |            35.7723 |                  26.2452  |                    52.3143 |            24.6453   |             34.0657   |
| traditional_saturation_ridge | mixed_B2_downstream  |             180 |       20 |            37.3842 |                  27.5486  |                    50.3044 |            25.3413   |            -20.0519   |

The traditional CFD20 covariance baseline has B2-containing pair covariance `1041.84` ns^2 with run-bootstrap CI `[738.30, 1319.61]`; downstream-only pair covariance is `15.99` ns^2 with CI `[5.19, 33.18]`.

Stave-covariance decomposition:

|      var_B2 |    cov_B2_B4 |     cov_B2_B6 |    cov_B2_B8 |     var_B4 |   cov_B4_B6 |    cov_B4_B8 |     var_B6 |   cov_B6_B8 |     var_B8 |   offdiag_rmse_ns2 |   n_offdiag_covariances | method                       | scope              |   B2_variance_minus_downstream_mean_ns2 |
|------------:|-------------:|--------------:|-------------:|-----------:|------------:|-------------:|-----------:|------------:|-----------:|-------------------:|------------------------:|:-----------------------------|:-------------------|----------------------------------------:|
| 166.497     | -100.696     | -113.321      | -118.976     | 34.2436    |  21.3232    |  10.8859     | 35.0676    | 21.8624     | 43.1141    |         10.4259    |                      15 | raw_pair_median              | event_level_pooled |                             129.022     |
|   5.40607   |   -3.33382   |   -3.81215    |   -3.66618   |  0.78651   |   0.93462   |   0.82618    |  0.786241  |  1.30505    |  0.767476  |          1.4413    |                      15 | raw_pair_median              | run_median_level   |                               4.626     |
|  45.7504    |  -30.9589    |  -28.6658     |  -31.876     | 22.7248    |  -1.6818    | -12.8089     | 16.1585    | -1.9694     | 23.3272    |          4.09776   |                      15 | traditional_saturation_ridge | event_level_pooled |                              25.0135    |
|   0.617882  |   -0.680582  |   -0.46217    |   -0.0930125 |  0.764293  |   0.234922  |  -1.08293    |  0.0837496 |  0.0597485  |  0.558095  |          0.871987  |                      15 | traditional_saturation_ridge | run_median_level   |                               0.14917   |
|   7.62655   |   -4.99122   |   -5.1817     |   -5.08017   |  5.16216   |  -2.03179   |  -3.30131    |  3.81109   | -0.408698   |  4.39509   |          1.1293    |                      15 | ml_extra_trees_saturation    | event_level_pooled |                               3.17043   |
|   0.0381514 |   -0.0392798 |   -0.00803061 |   -0.0289924 |  0.0332282 |  -0.0205015 |  -0.00667517 |  0.0135618 |  0.00140847 |  0.0171296 |          0.0536153 |                      15 | ml_extra_trees_saturation    | run_median_level   |                               0.0168449 |

## B2 Saturation Strata

The saturation threshold was `3800` ADC after baseline subtraction. These are diagnostics only; all fitted predictions above still hold out complete runs.

| method                       | stratum            |   n_pair_rows |   n_runs | b2_amp_cut_adc   |   median_b2_sat_count |   median_b2_sat_excess_adc |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_abs_pair_cov_ns2 |
|:-----------------------------|:-------------------|--------------:|---------:|:-----------------|----------------------:|---------------------------:|-------------:|--------------------:|---------------------:|------------------------:|
| raw_pair_median              | all_B2_containing  |         43956 |       21 |                  |                     0 |                       0    |      3.51234 |             1.86187 |             19.8635  |               1041.84   |
| raw_pair_median              | B2_sat_count_gt0   |         11981 |       21 |                  |                     6 |                    1786    |     30.7684  |            18.3163  |             41.6596  |               1272.58   |
| raw_pair_median              | B2_sat_count_eq0   |         31975 |       21 |                  |                     0 |                       0    |      1.56566 |             1.46511 |              1.8759  |                531.742  |
| raw_pair_median              | B2_amp_top_decile  |          4396 |       21 | 6615.75          |                     8 |                    4342.75 |     41.6906  |            26.9488  |             46.868   |               1210.1    |
| raw_pair_median              | B2_amp_lower_90pct |         39560 |       21 | 6615.75          |                     0 |                       0    |      1.96778 |             1.64223 |              8.95029 |                954.014  |
| traditional_saturation_ridge | all_B2_containing  |         43956 |       21 |                  |                     0 |                       0    |      7.04995 |             6.33324 |              8.80177 |                212.783  |
| traditional_saturation_ridge | B2_sat_count_gt0   |         11981 |       21 |                  |                     6 |                    1786    |     11.5965  |            10.431   |             12.5327  |                182.492  |
| traditional_saturation_ridge | B2_sat_count_eq0   |         31975 |       21 |                  |                     0 |                       0    |      5.68891 |             5.37075 |              6.78861 |                248.891  |
| traditional_saturation_ridge | B2_amp_top_decile  |          4396 |       21 | 6615.75          |                     8 |                    4342.75 |     10.8135  |            10.0071  |             11.4609  |                114.795  |
| traditional_saturation_ridge | B2_amp_lower_90pct |         39560 |       21 | 6615.75          |                     0 |                       0    |      6.62106 |             6.09061 |              8.74361 |                255.495  |
| ml_extra_trees_saturation    | all_B2_containing  |         43956 |       21 |                  |                     0 |                       0    |      1.61552 |             1.36483 |              2.49613 |                 25.1875 |
| ml_extra_trees_saturation    | B2_sat_count_gt0   |         11981 |       21 |                  |                     6 |                    1786    |      3.57052 |             3.12574 |              3.94399 |                 22.1263 |
| ml_extra_trees_saturation    | B2_sat_count_eq0   |         31975 |       21 |                  |                     0 |                       0    |      1.19246 |             1.10428 |              1.42234 |                 32.337  |
| ml_extra_trees_saturation    | B2_amp_top_decile  |          4396 |       21 | 6615.75          |                     8 |                    4342.75 |      3.82461 |             3.55973 |              4.05384 |                 28.7311 |
| ml_extra_trees_saturation    | B2_amp_lower_90pct |         39560 |       21 | 6615.75          |                     0 |                       0    |      1.41612 |             1.24996 |              2.00562 |                 27.7989 |

## Leakage checks

| check                                 |   value | pass   | interpretation                                                                                                                                    |
|:--------------------------------------|--------:|:-------|:--------------------------------------------------------------------------------------------------------------------------------------------------|
| run_split_event_overlap               | 0       | True   | train and held-out event ids are disjoint because whole runs are held out                                                                         |
| ml_features_exclude_forbidden_columns | 1       | True   | ML inputs exclude run, event, time_ns, raw residual, target residual, and pair-derived timing labels; saturation inputs are waveform-derived only |
| actual_ml_sigma68_ns                  | 1.35219 | True   | nominal leave-run-out ML residual width                                                                                                           |
| shuffled_train_target_ml_sigma68_ns   | 4.37455 | True   | target permutation inside train folds should not reproduce the nominal ML width                                                                   |
| intentional_target_echo_sigma68_ns    | 0       | True   | positive leakage sentinel; a leaked target would be unrealistically narrow                                                                        |

The shuffled-target ML control and intentional target-echo sentinel are leakage probes. The added saturation features are computed from waveform samples only, before residual targets are formed. The ML gain is not adopted unless its paired run-bootstrap CI is wholly below zero and the probes do not show an obvious split or target echo leak.

## Finding

The held-out covariance remains detector-local/topology dominated: B2-containing pair covariances are far larger than downstream-only covariances in the raw S05c baseline. Explicit saturation/recovery features isolate a high-amplitude B2 stratum, but the covariance decomposition still tests for residual B2-local variance after those terms rather than assuming the effect is detector-wide common mode.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `saturation_strata.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

# S14d: range-order preflight using P04c A/B matched charge

- **Ticket:** `1781023046.3664.1cf060b8`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo, GEANT4, Birks model, PID truth, or absolute energy claim.
- **Raw-root gate:** rebuild the P04c event-matched A/B table first, then run range-order tests on that table.
- **Split:** every prediction is leave-one-run-out; CIs resample held-out runs as blocks.

## P04c reproduction from raw ROOT

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B pulses | 640,737 | 640,737 | +0 | True |
| P04c A/B matched rows | 4,055 | 4,055 | +0 | True |
| P04c charge-transfer ridge res68 | 0.519271 | 0.519271 | -2.42368e-08 | True |

## Methods

Traditional bins use train-only depth/topology bins, B2 charge quantiles, downstream-charge bins, and A1/A3 selected-topology strata. The prediction is the train median selected-A charge with a registered fallback hierarchy.

ML uses a monotone additive isotonic residual model on depth, B2 charge, downstream charge fraction/multiplicity, total B multiplicity, and A selected flags. It does not receive run id, event id, or the selected-A charge. The shuffled-depth control trains the same residual model after permuting depth/downstream features in the training fold.

## Held-out benchmark

| method                    |    n |   bias_median_frac |   res68_abs_frac |   res68_ci95_low |   res68_ci95_high |   prediction_order_violation_rate |   prediction_order_violation_ci95_low |   prediction_order_violation_ci95_high |   target_a_order_violation_rate |   chi2_ndf_unit_frac |
|:--------------------------|-----:|-------------------:|-----------------:|-----------------:|------------------:|----------------------------------:|--------------------------------------:|---------------------------------------:|--------------------------------:|---------------------:|
| traditional_bins          | 4055 |        -0.00133248 |         0.354117 |         0.343055 |          0.368754 |                          0.470244 |                              0.457693 |                               0.478886 |                        0.493317 |              2.96705 |
| ml_monotonic_residual     | 4055 |        -0.0673332  |         0.360173 |         0.351267 |          0.372072 |                          0.433472 |                              0.419152 |                               0.440591 |                        0.493024 |              2.40519 |
| ml_shuffled_depth_control | 4055 |        -0.0796083  |         0.363569 |         0.35434  |          0.374972 |                          0.452216 |                              0.43727  |                               0.45965  |                        0.49434  |              2.34507 |

Traditional res68 is `0.3541` with run-block CI `[0.3431, 0.3688]`; ML residual res68 is `0.3602` with CI `[0.3513, 0.3721]`. The shuffled-depth control is `0.3636`.

## Stability

| sample                 | method                |    n |   res68_abs_frac |   prediction_order_violation_rate |
|:-----------------------|:----------------------|-----:|-----------------:|----------------------------------:|
| sample_iii_analysis    | traditional_bins      | 1470 |         0.358692 |                          0.463339 |
| sample_iii_analysis    | ml_monotonic_residual | 1470 |         0.365397 |                          0.426815 |
| sample_iii_calibration | traditional_bins      | 2431 |         0.34857  |                          0.470918 |
| sample_iii_calibration | ml_monotonic_residual | 2431 |         0.353876 |                          0.429735 |
| sample_iv_analysis     | traditional_bins      |  119 |         0.382755 |                          0.442006 |
| sample_iv_analysis     | ml_monotonic_residual |  119 |         0.38813  |                          0.416215 |
| sample_iv_calibration  | traditional_bins      |   35 |         0.468021 |                          0.352941 |
| sample_iv_calibration  | ml_monotonic_residual |   35 |         0.42224  |                          0.29916  |

|   run | sample                 | method                |   n |   res68_abs_frac |   prediction_order_violation_rate |
|------:|:-----------------------|:----------------------|----:|-----------------:|----------------------------------:|
|    31 | sample_iii_calibration | traditional_bins      | 229 |         0.369114 |                          0.446476 |
|    31 | sample_iii_calibration | ml_monotonic_residual | 229 |         0.353491 |                          0.400483 |
|    32 | sample_iii_calibration | traditional_bins      | 207 |         0.384813 |                          0.477138 |
|    32 | sample_iii_calibration | ml_monotonic_residual | 207 |         0.371123 |                          0.438503 |
|    33 | sample_iii_calibration | traditional_bins      |   8 |         0.538758 |                          0.428571 |
|    33 | sample_iii_calibration | ml_monotonic_residual |   8 |         0.588346 |                          0.428571 |
|    34 | sample_iii_calibration | traditional_bins      |  16 |         0.385372 |                          0.462185 |
|    34 | sample_iii_calibration | ml_monotonic_residual |  16 |         0.413131 |                          0.462185 |
|    35 | sample_iii_calibration | traditional_bins      | 221 |         0.32648  |                          0.434634 |
|    35 | sample_iii_calibration | ml_monotonic_residual | 221 |         0.329353 |                          0.422573 |
|    36 | sample_iii_calibration | traditional_bins      | 295 |         0.36921  |                          0.466861 |
|    36 | sample_iii_calibration | ml_monotonic_residual | 295 |         0.365625 |                          0.427882 |
|    37 | sample_iii_calibration | traditional_bins      | 292 |         0.339111 |                          0.458388 |
|    37 | sample_iii_calibration | ml_monotonic_residual | 292 |         0.346328 |                          0.418072 |
|    39 | sample_iii_calibration | traditional_bins      | 324 |         0.32791  |                          0.453754 |
|    39 | sample_iii_calibration | ml_monotonic_residual | 324 |         0.34526  |                          0.414776 |
|    40 | sample_iii_calibration | traditional_bins      | 265 |         0.336518 |                          0.467132 |
|    40 | sample_iii_calibration | ml_monotonic_residual | 265 |         0.360972 |                          0.406059 |
|    41 | sample_iii_calibration | traditional_bins      | 295 |         0.323531 |                          0.428822 |
|    41 | sample_iii_calibration | ml_monotonic_residual | 295 |         0.34089  |                          0.409369 |
|    42 | sample_iii_calibration | traditional_bins      | 279 |         0.371768 |                          0.465789 |
|    42 | sample_iii_calibration | ml_monotonic_residual | 279 |         0.376253 |                          0.434623 |
|    44 | sample_iii_analysis    | traditional_bins      |  30 |         0.386933 |                          0.358621 |
|    44 | sample_iii_analysis    | ml_monotonic_residual |  30 |         0.350035 |                          0.354023 |
|    45 | sample_iii_analysis    | traditional_bins      | 302 |         0.36327  |                          0.483996 |
|    45 | sample_iii_analysis    | ml_monotonic_residual | 302 |         0.351143 |                          0.44917  |
|    47 | sample_iii_analysis    | traditional_bins      |  92 |         0.283623 |                          0.416408 |
|    47 | sample_iii_analysis    | ml_monotonic_residual |  92 |         0.311704 |                          0.376226 |
|    48 | sample_iii_analysis    | traditional_bins      | 260 |         0.320123 |                          0.459625 |
|    48 | sample_iii_analysis    | ml_monotonic_residual | 260 |         0.334629 |                          0.43469  |
|    49 | sample_iii_analysis    | traditional_bins      | 288 |         0.353229 |                          0.414609 |
|    49 | sample_iii_analysis    | ml_monotonic_residual | 288 |         0.373514 |                          0.38006  |
|    50 | sample_iii_analysis    | traditional_bins      |  61 |         0.450521 |                          0.394204 |
|    50 | sample_iii_analysis    | ml_monotonic_residual |  61 |         0.402625 |                          0.378349 |
|    51 | sample_iii_analysis    | traditional_bins      |  25 |         0.46     |                          0.473333 |
|    51 | sample_iii_analysis    | ml_monotonic_residual |  25 |         0.485245 |                          0.406667 |
|    52 | sample_iii_analysis    | traditional_bins      |   6 |         0.430401 |                          0.666667 |
|    52 | sample_iii_analysis    | ml_monotonic_residual |   6 |         0.461076 |                          0.666667 |
|    53 | sample_iii_analysis    | traditional_bins      |  17 |         0.705778 |                          0.463235 |
|    53 | sample_iii_analysis    | ml_monotonic_residual |  17 |         0.64656  |                          0.455882 |
|    54 | sample_iii_analysis    | traditional_bins      |  18 |         0.457888 |                          0.424837 |
|    54 | sample_iii_analysis    | ml_monotonic_residual |  18 |         0.484695 |                          0.392157 |
|    55 | sample_iii_analysis    | traditional_bins      |  27 |         0.502543 |                          0.367521 |
|    55 | sample_iii_analysis    | ml_monotonic_residual |  27 |         0.530526 |                          0.358974 |
|    56 | sample_iii_analysis    | traditional_bins      |  68 |         0.42621  |                          0.391209 |
|    56 | sample_iii_analysis    | ml_monotonic_residual |  68 |         0.437308 |                          0.355604 |
|    57 | sample_iii_analysis    | traditional_bins      | 276 |         0.345898 |                          0.478854 |
|    57 | sample_iii_analysis    | ml_monotonic_residual | 276 |         0.364927 |                          0.452539 |
|    58 | sample_iv_analysis     | traditional_bins      |  34 |         0.419505 |                          0.445633 |
|    58 | sample_iv_analysis     | ml_monotonic_residual |  34 |         0.425189 |                          0.42246  |
|    59 | sample_iv_analysis     | traditional_bins      |   9 |         0.338074 |                          0.75     |
|    59 | sample_iv_analysis     | ml_monotonic_residual |   9 |         0.376598 |                          0.75     |
|    60 | sample_iv_analysis     | traditional_bins      |  10 |         1.58505  |                          0.488889 |
|    60 | sample_iv_analysis     | ml_monotonic_residual |  10 |         1.43174  |                          0.444444 |
|    61 | sample_iv_analysis     | traditional_bins      |   6 |         0.250898 |                          0.4      |
|    61 | sample_iv_analysis     | ml_monotonic_residual |   6 |         0.300982 |                          0.4      |
|    62 | sample_iv_analysis     | traditional_bins      |   8 |         0.493921 |                          0.535714 |
|    62 | sample_iv_analysis     | ml_monotonic_residual |   8 |         0.423932 |                          0.535714 |
|    63 | sample_iv_analysis     | traditional_bins      |  39 |         0.359165 |                          0.285135 |
|    63 | sample_iv_analysis     | ml_monotonic_residual |  39 |         0.370383 |                          0.231081 |
|    64 | sample_iv_calibration  | traditional_bins      |  35 |         0.468021 |                          0.352941 |
|    64 | sample_iv_calibration  | ml_monotonic_residual |  35 |         0.42224  |                          0.29916  |
|    65 | sample_iv_analysis     | traditional_bins      |  13 |         0.328347 |                          0.24359  |
|    65 | sample_iv_analysis     | ml_monotonic_residual |  13 |         0.362206 |                          0.192308 |

## Selected-A charge ordering bins

| sample                 | a_topology   |   b2_bin_global |   n_depths |   n |   adjacent_depth_steps |   adjacent_observed_a_charge_violations | median_a_charge_by_depth                                  |
|:-----------------------|:-------------|----------------:|-----------:|----:|-----------------------:|----------------------------------------:|:----------------------------------------------------------|
| sample_iii_analysis    | A1           |               4 |          2 |  22 |                      1 |                                       0 | {"0": 11731.0, "1": 14661.0}                              |
| sample_iii_analysis    | A1+A3        |               0 |          4 | 101 |                      3 |                                       1 | {"0": 33138.5, "1": 44266.0, "2": 28655.0, "3": 44388.0}  |
| sample_iii_analysis    | A1+A3        |               1 |          3 |  90 |                      2 |                                       1 | {"0": 33023.0, "1": 35058.0, "2": 31442.0}                |
| sample_iii_analysis    | A1+A3        |               2 |          2 | 111 |                      1 |                                       0 | {"0": 31754.0, "1": 33554.5}                              |
| sample_iii_analysis    | A1+A3        |               3 |          4 |  96 |                      3 |                                       1 | {"0": 33961.0, "1": 27087.0, "2": 33582.0, "3": 38017.5}  |
| sample_iii_analysis    | A1+A3        |               4 |          3 |  90 |                      2 |                                       0 | {"0": 32684.5, "1": 33752.0, "2": 34316.0}                |
| sample_iii_analysis    | A3           |               0 |          4 | 173 |                      3 |                                       1 | {"0": 16584.5, "1": 5398.0, "2": 13477.0, "3": 29845.0}   |
| sample_iii_analysis    | A3           |               1 |          4 | 174 |                      3 |                                       1 | {"0": 14486.0, "1": 16803.5, "2": 9266.0, "3": 9723.0}    |
| sample_iii_analysis    | A3           |               2 |          3 | 167 |                      2 |                                       2 | {"0": 14905.5, "1": 13426.0, "2": 12793.5}                |
| sample_iii_analysis    | A3           |               3 |          3 | 180 |                      2 |                                       1 | {"0": 14505.0, "1": 12424.0, "2": 19428.5}                |
| sample_iii_analysis    | A3           |               4 |          3 | 206 |                      2 |                                       1 | {"0": 15186.0, "1": 15290.0, "2": 12467.0}                |
| sample_iii_calibration | A1           |               1 |          2 |  12 |                      1 |                                       1 | {"0": 11976.0, "1": 9544.0}                               |
| sample_iii_calibration | A1           |               2 |          2 |   7 |                      1 |                                       1 | {"0": 10780.0, "2": 4242.0}                               |
| sample_iii_calibration | A1           |               4 |          2 |  18 |                      1 |                                       0 | {"0": 11097.5, "2": 14097.0}                              |
| sample_iii_calibration | A1+A3        |               0 |          3 | 177 |                      2 |                                       2 | {"0": 30332.0, "1": 24461.0, "2": 23063.5}                |
| sample_iii_calibration | A1+A3        |               1 |          4 | 157 |                      3 |                                       2 | {"0": 32478.0, "1": 29395.5, "2": 37871.0, "3": 31206.0}  |
| sample_iii_calibration | A1+A3        |               2 |          2 | 158 |                      1 |                                       0 | {"0": 32262.5, "1": 36174.0}                              |
| sample_iii_calibration | A1+A3        |               3 |          3 | 164 |                      2 |                                       1 | {"0": 30211.0, "1": 30339.5, "3": 29735.0}                |
| sample_iii_calibration | A1+A3        |               4 |          3 | 178 |                      2 |                                       1 | {"0": 33218.5, "1": 40349.0, "2": 31597.0}                |
| sample_iii_calibration | A3           |               0 |          3 | 298 |                      2 |                                       1 | {"0": 15415.0, "1": 19286.5, "2": 13193.0}                |
| sample_iii_calibration | A3           |               1 |          4 | 314 |                      3 |                                       1 | {"0": 16322.5, "1": 17391.0, "2": 15450.75, "3": 15855.5} |
| sample_iii_calibration | A3           |               2 |          3 | 323 |                      2 |                                       1 | {"0": 14213.0, "1": 18847.0, "2": 15561.0}                |
| sample_iii_calibration | A3           |               3 |          4 | 307 |                      3 |                                       1 | {"0": 15329.0, "1": 18757.0, "2": 11644.0, "3": 20887.0}  |
| sample_iii_calibration | A3           |               4 |          3 | 292 |                      2 |                                       1 | {"0": 15081.0, "1": 18639.0, "2": 13123.5}                |
| sample_iv_analysis     | A1           |               0 |          2 |   3 |                      1 |                                       0 | {"0": 9556.0, "3": 19401.0}                               |
| sample_iv_analysis     | A3           |               0 |          3 |  27 |                      2 |                                       1 | {"0": 12888.0, "1": 12757.0, "2": 19917.0}                |
| sample_iv_analysis     | A3           |               1 |          4 |  37 |                      3 |                                       1 | {"0": 19076.0, "1": 21192.0, "2": 21908.0, "3": 8352.5}   |
| sample_iv_analysis     | A3           |               2 |          2 |  20 |                      1 |                                       1 | {"0": 15608.5, "2": 11338.0}                              |
| sample_iv_calibration  | A3           |               0 |          2 |   9 |                      1 |                                       0 | {"0": 14929.0, "1": 21432.0}                              |
| sample_iv_calibration  | A3           |               2 |          2 |   8 |                      1 |                                       1 | {"0": 20790.0, "1": 15817.0}                              |

## ML hyperparameter CV

|   passes |   shrinkage |   mean_fold_res68 |   median_fold_res68 |   n_folds |
|---------:|------------:|------------------:|--------------------:|----------:|
|        2 |        0.6  |          0.382379 |            0.396311 |         4 |
|        6 |        0.35 |          0.384209 |            0.398072 |         4 |
|        4 |        0.5  |          0.384455 |            0.398523 |         4 |

## Leakage audit

| check                              | value                                                | pass   |
|:-----------------------------------|:-----------------------------------------------------|:-------|
| train_heldout_run_overlap          | 0 by leave-one-run-out construction                  | True   |
| run_event_features_excluded        | run and evt omitted from traditional and ML features | True   |
| p04c_reproduction_before_extension | rows=4055, ridge_res68=0.519271                      | True   |
| shuffled_depth_control_res68       | 0.363569                                             | True   |
| no_mc_truth_or_pid_labels          | raw HRD charges/topology only                        | True   |

## Finding

The P04c raw-root table is reproduced first (640737 selected B pulses, 4055 A/B rows, charge-transfer ridge res68 0.5193). On that held-out-run table, the traditional depth/topology/B-charge bins give selected-A charge res68 0.3541 [0.3431, 0.3688] and prediction order-violation rate 0.4702. The monotonic residual ML model gives res68 0.3602 [0.3513, 0.3721] (ML-traditional delta +0.0061) and order-violation rate 0.4335; the shuffled-depth control is 0.3636. Simple range-order structure is therefore visible only as a weak internal ordering diagnostic, not as an external energy/PID calibration.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `p04c_reproduction_summary.csv`, `range_order_summary.csv`, `range_order_by_run.csv`, `range_order_by_sample.csv`, `selected_a_order_bins.csv`, `ml_cv_scan.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and `oof_predictions.csv.gz`.

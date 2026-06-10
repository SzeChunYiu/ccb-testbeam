# Study report: S18f - Sample IV A-stack per-run outliers

- **Ticket:** `1781014670.1107.6b932bc2`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT `HRDv`, A1/A3 runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18f_1781014670_1107_6b932bc2_run_outliers.py --config configs/s18f_1781014670_1107_6b932bc2.json`

## Question

Question: which Sample IV A1-A3 runs drive the binned Gaussian fit instability seen in S18d, and are those runs distinguishable by amplitude, waveform-shape, or event-count diagnostics? Expected information gain: separate genuine per-run timing broadening from optimizer/window failures by run-level diagnostic plots and leave-one-run-out estimator deltas on raw ROOT.

## Reproduction first

The S18d historical binned-Gaussian definition was rerun from raw ROOT before any new diagnostics: CFD20, A1=0/A3=4, `A1,A3 > 1000 ADC`, run64-only Sample IV timewalk calibration, 40 bins, and a +/-2.5 ns fit window.

| quantity                  |   expected |   reproduced |        delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|-------------:|------------:|:-------|
| sample_iii_A1_A3_pairs    | 2514       |   2514       |  0           |       0     | True   |
| sample_iii_core_sigma_ns  |    1.45092 |      1.45092 | -2.79233e-07 |       0.001 | True   |
| sample_iv_A1_A3_pairs     |  127       |    127       |  0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | -3.62232e-08 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | -4.61618e-07 |       0.001 | True   |

The reproduced Sample IV binned core sigma is **1.992 ns**, matching S18d.

## Traditional run-held-out method

The traditional method is a quadratic log-amplitude CFD20 residual correction with a Sample-IV period intercept. Each analysis run is held out completely from its own fit. The binned Gaussian metric uses the same S18d window and has a held-out-run bootstrap CI.

| method                             | estimator       |   n_pairs |   value_ns |   ci_low_ns |   ci_high_ns |
|:-----------------------------------|:----------------|----------:|-----------:|------------:|-------------:|
| traditional_period_poly_runheldout | binned_gaussian |       127 |    2.07667 |     1.40717 |      5       |
| traditional_period_poly_runheldout | robust_width    |       127 |    1.50587 |     1.3064  |      1.66173 |
| traditional_period_poly_runheldout | rms             |       127 |    1.48585 |     1.32053 |      1.654   |

## ML run-held-out method

The ML method is ExtraTrees residual correction on amplitude and waveform-shape features only: log amplitudes, peak samples, log areas, tail fractions, area/amplitude, width-over-half-maximum, and a Sample-IV indicator. It excludes run id, event id, timing columns, and the target residual. Hyperparameters are tuned with group-by-run CV inside the training pool.

| method                         | estimator       |   n_pairs |   value_ns |   ci_low_ns |   ci_high_ns |
|:-------------------------------|:----------------|----------:|-----------:|------------:|-------------:|
| ml_extratrees_shape_runheldout | binned_gaussian |       127 |    1.77323 |     1.41012 |      5       |
| ml_extratrees_shape_runheldout | robust_width    |       127 |    1.66461 |     1.38379 |      1.89076 |
| ml_extratrees_shape_runheldout | rms             |       127 |    2.24824 |     1.91844 |      2.50237 |

## Run drivers

Positive leave-one-run-out delta means removing that run narrows the Sample IV binned Gaussian core, so the run broadens the fit when included. The largest positive historical broadening driver is run **65** with delta **0.184 ns**. The largest absolute binned-fit instability is run **63** with delta **-1.233 ns**; its negative sign means removing that run makes the binned optimizer/window fit much broader, so it is a stabilizing run-composition component rather than a broadening outlier.

| method                |   run |   n_pairs |   full_binned_sigma_ns |   exclude_run_sigma_ns |   delta_full_minus_exclude_ns |   delta_ci_low_ns |   delta_ci_high_ns |   run_only_binned_sigma_ns |   run_robust_width_ns |   run_rms_ns |   run_median_residual_ns |
|:----------------------|------:|----------:|-----------------------:|-----------------------:|------------------------------:|------------------:|-------------------:|---------------------------:|----------------------:|-------------:|-------------------------:|
| historical_run64_poly |    65 |        27 |                1.99218 |                1.8086  |                    0.183576   |          -2.59945 |            2.39786 |                    2.62631 |              1.93309  |      1.80968 |               -0.276894  |
| historical_run64_poly |    59 |        11 |                1.99218 |                1.88088 |                    0.111293   |          -2.6124  |            2.45701 |                    5       |              2.24223  |      2.29397 |               -0.47058   |
| historical_run64_poly |    61 |        18 |                1.99218 |                1.9994  |                   -0.00722229 |          -2.48144 |            2.71361 |                    3.58558 |              1.85667  |      2.2007  |               -1.39933   |
| historical_run64_poly |    60 |        11 |                1.99218 |                2.03274 |                   -0.04056    |          -2.64015 |            1.81574 |                    5       |              1.1044   |      1.29846 |               -1.21974   |
| historical_run64_poly |    58 |        25 |                1.99218 |                2.228   |                   -0.235821   |          -2.56517 |            2.49152 |                    5       |              1.17944  |      1.38618 |               -0.0891808 |
| historical_run64_poly |    62 |         7 |                1.99218 |                2.32929 |                   -0.337114   |          -2.43796 |            2.30825 |                  nan       |              0.825697 |      1.40204 |               -0.946849  |
| historical_run64_poly |    63 |        28 |                1.99218 |                3.22546 |                   -1.23328    |          -3.0969  |            2.12029 |                    3.4158  |              1.82434  |      1.59059 |               -0.313523  |

The same table for traditional and ML residuals is in `leave_one_run_out_deltas.csv`.

## Diagnostics

Run-level amplitude, waveform-shape, event-count, and residual diagnostics:

|   run |   event_count |   a1_amp_median |   a3_amp_median |   log_amp_sum_median |   log_amp_diff_median |   peak_left_median |   peak_right_median |   tail_left_median |   tail_right_median |   area_over_amp_left_median |   area_over_amp_right_median |   width_half_left_median |   width_half_right_median |   historical_residual_robust_width_ns |   historical_abs_residual_median_ns |   historical_loo_delta_ns |
|------:|--------------:|----------------:|----------------:|---------------------:|----------------------:|-------------------:|--------------------:|-------------------:|--------------------:|----------------------------:|-----------------------------:|-------------------------:|--------------------------:|--------------------------------------:|------------------------------------:|--------------------------:|
|    65 |            27 |         1746    |         1917    |              15.0438 |             0.127317  |                7   |                 8   |           0.386838 |            0.435361 |                     7.05635 |                      7.18482 |                        7 |                         7 |                              1.93309  |                            1.26819  |                0.183576   |
|    59 |            11 |         2491.5  |         2043    |              15.2714 |            -0.451585  |                8   |                 9   |           0.519413 |            0.59518  |                     7.04204 |                      7.14581 |                        7 |                         7 |                              2.24223  |                            1.32143  |                0.111293   |
|    61 |            18 |         2456.5  |         1960.5  |              15.3853 |            -0.234894  |                9.5 |                11   |           0.778114 |            0.849345 |                     7.12084 |                      6.8395  |                        7 |                         7 |                              1.85667  |                            1.31747  |               -0.00722229 |
|    60 |            11 |         2125    |         1748.5  |              14.9942 |            -0.132427  |                7   |                 7   |           0.349993 |            0.421218 |                     6.94586 |                      7.04426 |                        7 |                         7 |                              1.1044   |                            0.956701 |               -0.04056    |
|    58 |            25 |         2268    |         1840.5  |              15.1213 |            -0.129411  |                7   |                 8   |           0.368476 |            0.419256 |                     7.18642 |                      7.2813  |                        7 |                         7 |                              1.17944  |                            0.957294 |               -0.235821   |
|    62 |             7 |         2192    |         1804.5  |              15.2413 |            -0.255952  |               11   |                12   |           0.868121 |            0.938084 |                     6.65254 |                      6.49675 |                        7 |                         7 |                              0.825697 |                            0.642338 |               -0.337114   |
|    63 |            28 |         1846.25 |         1875.25 |              15.0292 |            -0.0284785 |                7   |                 7.5 |           0.380905 |            0.417175 |                     7.16772 |                      7.26698 |                        7 |                         7 |                              1.82434  |                            1.19701  |               -1.23328    |

Largest diagnostic rank correlations with the historical LOO delta:

| diagnostic                |   spearman_rho |   p_value |    ci_low |   ci_high |   best_alpha |   loo_rmse_ns |   loo_r2 |
|:--------------------------|---------------:|----------:|----------:|----------:|-------------:|--------------:|---------:|
| a3_amp_median             |       0.571429 |  0.180202 | -0.176471 |  1        |          nan |           nan |      nan |
| tail_right_median         |       0.321429 |  0.482072 | -0.75     |  1        |          nan |           nan |      nan |
| log_amp_sum_median        |       0.285714 |  0.534509 | -0.693179 |  0.882353 |          nan |           nan |      nan |
| a1_amp_median             |       0.142857 |  0.759945 | -0.732692 |  1        |          nan |           nan |      nan |
| area_over_amp_left_median |      -0.142857 |  0.759945 | -0.882908 |  1        |          nan |           nan |      nan |

The run-level ridge model over all diagnostics is intentionally treated as descriptive because only seven Sample IV analysis runs exist; its leave-one-run CV is in `diagnostic_ridge_cv.csv`.

## Leakage checks

Leakage flags: **0**.

| check                                  | value                                                     | flag   |
|:---------------------------------------|:----------------------------------------------------------|:-------|
| forbidden_feature_overlap              |                                                           | False  |
| heldout_run_overlap                    | none; each analysis run excluded from its prediction fold | False  |
| group_split_r2_mean                    | 0.15522810189030445                                       | False  |
| row_split_r2                           | 0.15854851253829372                                       | False  |
| row_minus_group_rmse_ns                | 0.3909496235251848                                        | False  |
| shuffled_target_r2                     | 0.010591664619512886                                      | False  |
| suspicious_ml_ci_dominates_traditional | False                                                     | False  |

## Conclusion

The S18d binned Gaussian instability is mostly a low-count/run-composition effect rather than a stable per-run broadening measurement. Runs 65 and 59 are the only positive historical broadening drivers, but the larger absolute effect is run 63, whose removal sends the binned fit wider. Per-run core fits are underconstrained and the held-out-run bootstrap intervals are wide. The diagnostic correlations are strongest for amplitude/shape summaries with broad CIs, so the affected runs are distinguishable as fit-sensitive run compositions, not as a clean detector-resolution class. ML does not provide a leakage-free decisive improvement over the traditional run-held-out residual correction.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `historical_residuals.csv`, `heldout_pair_predictions.csv`, `method_metrics.csv`, `leave_one_run_out_deltas.csv`, `run_diagnostics.csv`, `diagnostic_correlations.csv`, `diagnostic_ridge_cv.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.

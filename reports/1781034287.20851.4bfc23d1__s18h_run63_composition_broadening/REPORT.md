# Study report: S18h - run-63 stabilizing composition versus detector broadening

- **Study ID:** S18h
- **Ticket:** `1781034287.20851.4bfc23d1`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Depends on:** S18d, S18f run-outlier audit, S18f percentile-68 ledger
- **Inputs:** raw A-stack ROOT `HRDv` files under `data/root/root`
- **Config:** `configs/s18h_1781034287_20851_4bfc23d1_run63_composition_broadening.json`
- **Git commit:** `afedd5b0e9d2722fe8324b68b4dfe08d91dfc1a5`

## 0. Question and preregistered estimand

The ticket asks why removing Sample IV run 63 makes the A1-A3 binned Gaussian core fit much broader in S18f. The working alternatives are:

1. **Stabilizing composition:** run 63 contributes events in amplitude, waveform-shape, and residual bins that make the low-count binned core fit well-conditioned.
2. **Detector broadening:** non-run-63 Sample IV runs represent a genuinely broader timing state, with run 63 a distinct narrow detector state.

The primary method-benchmark metric is the median-centered percentile width

```text
sigma68(r) = (Q84(r - median(r)) - Q16(r - median(r))) / 2,
```

with uncertainty from resampling whole held-out runs. The binned Gaussian core sigma is retained because it is the ticket trigger, but it is treated as a diagnostic:

```text
n_k ~ A exp[-(x_k - mu)^2 / (2 sigma_core^2)]
```

fit to 40 bins in the fixed +/-2.5 ns S18d window. The hierarchical run-width check models the unbinned per-run log width as

```text
log(sigma_j) = mu + u_j + e_j,   u_j ~ Normal(0, tau^2),
```

with `Var(e_j) ~= 1 / (2(n_j - 1))`, then reports empirical-Bayes shrunk run widths.

## 1. Raw ROOT reproduction

The analysis reconstructs A1-A3 pairs directly from raw `HRDv` waveforms. For each event, samples 0-3 define a median baseline, CFD20 crossing times are linearly interpolated before the peak, and both A1 and A3 must exceed 1000 ADC. The run64-only quadratic log-amplitude traditional correction is then applied to Sample IV analysis runs 58, 59, 60, 61, 62, 63, and 65.

| quantity                              |   expected |   reproduced |        delta |   tolerance | pass   |
|:--------------------------------------|-----------:|-------------:|-------------:|------------:|:-------|
| sample_iv_A1_A3_pairs                 |  127       |    127       |  0           |       0     | True   |
| sample_iv_run63_pairs                 |   28       |     28       |  0           |       0     | True   |
| sample_iv_sigma68_ns                  |    1.79363 |      1.79363 |  3.40883e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns               |    1.99218 |      1.99218 |  5.23655e-07 |       0.002 | True   |
| sample_iv_exclude_run63_core_sigma_ns |    3.22546 |      3.22543 | -2.6938e-05  |       0.002 | True   |

The key reproduced number is the S18f/S18d instability: the full held-out Sample IV binned core is **1.992 ns**, while excluding run 63 gives **3.225 ns**. The sign of `full - exclude` is **-1.233 ns**, so run 63 is a stabilizer for this binned fit, not a broadening outlier.

## 2. Traditional and learned benchmark

The traditional comparator is a strong run-calibration model:

```text
r_i = beta_0 + beta_1 log A1_i + beta_2 log A3_i
    + beta_3 (log A1_i)^2 + beta_4 (log A3_i)^2
    + beta_5 log A1_i log A3_i + beta_6 I(Sample IV) + epsilon_i.
```

Learned methods are trained only on the calibration pool named in the table and evaluated on the same held-out Sample IV runs. The engineered-feature models use log amplitudes, log areas, peak samples, tail fractions, and a Sample-IV indicator; they exclude run id, event id, timing labels, and residual labels as features. The 1D-CNN receives two normalized 18-sample A1/A3 waveforms. The new `composition_gated_cnn` is sensible for this ticket because it estimates a waveform residual correction plus a learned support gate from composition variables, suppressing waveform corrections where amplitude/shape support is weak.

Calibration pools:

| pool             |   train_n_pairs | train_runs                                                                 |
|:-----------------|----------------:|:---------------------------------------------------------------------------|
| run64_only       |              16 | 64                                                                         |
| sample_iii_early |            3816 | 31,32,33,34,35,36,37,39,40,41,42                                           |
| sample_iii_late  |            2514 | 44,45,46,47,48,49,50,51,52,53,54,55,56,57                                  |
| sample_iii_mixed |            6330 | 31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57 |

Hyperparameter scan summary:

| pool             | method                 | params                                                      |   cv_rmse_ns |
|:-----------------|:-----------------------|:------------------------------------------------------------|-------------:|
| run64_only       | ridge                  | {"alpha": 0.1}                                              |     0.983609 |
| run64_only       | ridge                  | {"alpha": 1.0}                                              |     1.0969   |
| run64_only       | ridge                  | {"alpha": 10.0}                                             |     1.11828  |
| run64_only       | ridge                  | {"alpha": 100.0}                                            |     1.14891  |
| run64_only       | ridge                  | {"alpha": 1000.0}                                           |     1.19621  |
| run64_only       | gradient_boosted_trees | fallback_ridge_small_pool                                   |   nan        |
| run64_only       | mlp                    | fallback_ridge_small_pool                                   |   nan        |
| run64_only       | cnn_1d                 | fallback_ridge_small_pool                                   |     0.983609 |
| run64_only       | composition_gated_cnn  | fallback_ridge_small_pool                                   |     0.983609 |
| sample_iii_early | ridge                  | {"alpha": 100.0}                                            |     2.23751  |
| sample_iii_early | ridge                  | {"alpha": 1000.0}                                           |     2.23768  |
| sample_iii_early | ridge                  | {"alpha": 10.0}                                             |     2.25163  |
| sample_iii_early | ridge                  | {"alpha": 1.0}                                              |     2.25521  |
| sample_iii_early | ridge                  | {"alpha": 0.1}                                              |     2.25562  |
| sample_iii_early | gradient_boosted_trees | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 80} |     2.85065  |
| sample_iii_early | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.89303  |
| sample_iii_early | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.92715  |
| sample_iii_early | mlp                    | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.15905  |
| sample_iii_early | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.16678  |
| sample_iii_early | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.1696   |
| sample_iii_early | cnn_1d                 | trained                                                     |     1.42875  |
| sample_iii_early | composition_gated_cnn  | trained                                                     |     1.55198  |
| sample_iii_late  | ridge                  | {"alpha": 100.0}                                            |     3.06082  |
| sample_iii_late  | ridge                  | {"alpha": 1000.0}                                           |     3.06114  |
| sample_iii_late  | ridge                  | {"alpha": 10.0}                                             |     3.06334  |
| sample_iii_late  | ridge                  | {"alpha": 1.0}                                              |     3.0659   |
| sample_iii_late  | ridge                  | {"alpha": 0.1}                                              |     3.06623  |
| sample_iii_late  | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.28031  |
| sample_iii_late  | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.67746  |
| sample_iii_late  | gradient_boosted_trees | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 80} |     2.71706  |
| sample_iii_late  | mlp                    | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.92473  |
| sample_iii_late  | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.96363  |
| sample_iii_late  | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.9782   |
| sample_iii_late  | cnn_1d                 | trained                                                     |     1.29515  |
| sample_iii_late  | composition_gated_cnn  | trained                                                     |     1.3392   |
| sample_iii_mixed | ridge                  | {"alpha": 100.0}                                            |     2.62618  |
| sample_iii_mixed | ridge                  | {"alpha": 10.0}                                             |     2.63146  |
| sample_iii_mixed | ridge                  | {"alpha": 1000.0}                                           |     2.63151  |
| sample_iii_mixed | ridge                  | {"alpha": 1.0}                                              |     2.63263  |
| sample_iii_mixed | ridge                  | {"alpha": 0.1}                                              |     2.63276  |
| sample_iii_mixed | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.21473  |
| sample_iii_mixed | gradient_boosted_trees | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 80} |     2.25613  |
| sample_iii_mixed | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.27458  |
| sample_iii_mixed | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.5594   |
| sample_iii_mixed | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.57739  |
| sample_iii_mixed | mlp                    | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.6001   |
| sample_iii_mixed | cnn_1d                 | trained                                                     |     1.00084  |
| sample_iii_mixed | composition_gated_cnn  | trained                                                     |     0.933662 |

Head-to-head held-out benchmark:

| pool             | method                 |   n_pairs |   robust_width_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_fraction_abs_gt_5ns |
|:-----------------|:-----------------------|----------:|------------------:|--------------------:|---------------------:|--------------:|----------------:|-----------:|---------------------------:|
| run64_only       | traditional            |       127 |           1.79363 |            1.36631  |              2.07329 |       1.73704 |         1.99218 |   1.53564  |                 0          |
| run64_only       | ridge                  |       127 |           1.66238 |            1.41356  |              1.9579  |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | gradient_boosted_trees |       127 |           1.66238 |            1.40427  |              1.96854 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | mlp                    |       127 |           1.66238 |            1.41357  |              1.93182 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | cnn_1d                 |       127 |           1.66238 |            1.41128  |              1.94126 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | composition_gated_cnn  |       127 |           1.66238 |            1.39899  |              1.961   |       1.58015 |         1.58363 |   0.668225 |                 0          |
| sample_iii_early | traditional            |       127 |           1.55775 |            1.23648  |              1.68258 |       1.49031 |         1.78206 |   1.02814  |                 0          |
| sample_iii_early | ridge                  |       127 |           1.46515 |            1.28348  |              1.63546 |       1.46263 |         1.77628 |   0.792907 |                 0          |
| sample_iii_early | gradient_boosted_trees |       127 |           1.52775 |            1.25667  |              1.7226  |       1.5946  |         1.95586 |   1.78155  |                 0.00787402 |
| sample_iii_early | mlp                    |       127 |           1.51199 |            1.38226  |              1.82718 |       1.58727 |         2.55147 |   2.00522  |                 0.00787402 |
| sample_iii_early | cnn_1d                 |       127 |           1.65618 |            1.24143  |              1.96979 |       2.69581 |         1.82434 |   1.25007  |                 0.0708661  |
| sample_iii_early | composition_gated_cnn  |       127 |           1.64305 |            1.36611  |              2.23515 |       3.04071 |         1.66669 |   1.24407  |                 0.0393701  |
| sample_iii_late  | traditional            |       127 |           1.45662 |            1.27381  |              1.65223 |       1.47204 |         2.03747 |   1.84835  |                 0          |
| sample_iii_late  | ridge                  |       127 |           2.27456 |            1.90828  |              2.83924 |       2.21202 |         6.35804 |   0.788455 |                 0.023622   |
| sample_iii_late  | gradient_boosted_trees |       127 |           1.45099 |            1.18447  |              1.65517 |       6.85266 |         1.42833 |   1.09492  |                 0.015748   |
| sample_iii_late  | mlp                    |       127 |           2.69556 |            1.5524   |              3.76547 |       3.16958 |         1.96306 |   1.39578  |                 0.133858   |
| sample_iii_late  | cnn_1d                 |       127 |           1.76601 |            1.54188  |              2.04637 |       1.7682  |         2.10391 |   1.23355  |                 0.00787402 |
| sample_iii_late  | composition_gated_cnn  |       127 |           2.68646 |            1.60506  |              3.21761 |       2.71357 |         2.29951 |   0.87756  |                 0.0944882  |
| sample_iii_mixed | traditional            |       127 |           1.49211 |            1.23687  |              1.65896 |       1.47696 |         1.68292 |   1.04604  |                 0          |
| sample_iii_mixed | ridge                  |       127 |           1.86366 |            1.5841   |              2.26468 |       1.78095 |         2.41788 |   1.86534  |                 0          |
| sample_iii_mixed | gradient_boosted_trees |       127 |           1.37029 |            1.16348  |              1.56451 |       1.38666 |         1.47548 |   0.759582 |                 0          |
| sample_iii_mixed | mlp                    |       127 |           2.72308 |            1.73003  |              3.35522 |       2.67326 |         2.89404 |   0.822925 |                 0.0708661  |
| sample_iii_mixed | cnn_1d                 |       127 |           1.32813 |            1.17587  |              1.86855 |       1.69629 |         1.35627 |   1.24738  |                 0.0314961  |
| sample_iii_mixed | composition_gated_cnn  |       127 |           1.14567 |            0.878952 |              1.42201 |       1.55728 |         1.05201 |   1.38824  |                 0.015748   |

Paired run-bootstrap deltas versus the traditional comparator in the same pool:

| pool             | comparison                               |   delta_median_ns |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------------|:-----------------------------------------|------------------:|------------:|-------------:|----------:|
| run64_only       | ridge_minus_traditional                  |        -0.156171  |  -0.447174  |    0.325709  |     0.494 |
| run64_only       | gradient_boosted_trees_minus_traditional |        -0.137019  |  -0.441874  |    0.316632  |     0.49  |
| run64_only       | mlp_minus_traditional                    |        -0.148371  |  -0.466964  |    0.316253  |     0.502 |
| run64_only       | cnn_1d_minus_traditional                 |        -0.1512    |  -0.460104  |    0.34811   |     0.48  |
| run64_only       | composition_gated_cnn_minus_traditional  |        -0.138818  |  -0.45381   |    0.301203  |     0.518 |
| sample_iii_early | ridge_minus_traditional                  |        -0.0592529 |  -0.214983  |    0.137936  |     0.456 |
| sample_iii_early | gradient_boosted_trees_minus_traditional |        -0.0116718 |  -0.211058  |    0.194504  |     0.908 |
| sample_iii_early | mlp_minus_traditional                    |         0.031826  |  -0.166345  |    0.333582  |     0.812 |
| sample_iii_early | cnn_1d_minus_traditional                 |         0.12585   |  -0.330321  |    0.627965  |     0.614 |
| sample_iii_early | composition_gated_cnn_minus_traditional  |         0.105679  |  -0.114542  |    0.533449  |     0.366 |
| sample_iii_late  | ridge_minus_traditional                  |         0.749696  |   0.400948  |    1.3705    |     0     |
| sample_iii_late  | gradient_boosted_trees_minus_traditional |        -0.0408563 |  -0.243215  |    0.133047  |     0.65  |
| sample_iii_late  | mlp_minus_traditional                    |         1.19975   |   0.205378  |    2.31483   |     0.004 |
| sample_iii_late  | cnn_1d_minus_traditional                 |         0.26432   |   0.075965  |    0.584744  |     0.02  |
| sample_iii_late  | composition_gated_cnn_minus_traditional  |         1.11421   |   0.29266   |    1.85144   |     0.002 |
| sample_iii_mixed | ridge_minus_traditional                  |         0.378737  |   0.0689366 |    0.842292  |     0.014 |
| sample_iii_mixed | gradient_boosted_trees_minus_traditional |        -0.133717  |  -0.26615   |    0.0531717 |     0.178 |
| sample_iii_mixed | mlp_minus_traditional                    |         1.14998   |   0.354044  |    1.94173   |     0.002 |
| sample_iii_mixed | cnn_1d_minus_traditional                 |        -0.136876  |  -0.390128  |    0.393891  |     0.568 |
| sample_iii_mixed | composition_gated_cnn_minus_traditional  |        -0.359528  |  -0.587191  |    0.0308751 |     0.06  |

Winner by point estimate is **sample_iii_mixed::composition_gated_cnn**, sigma68 **1.146 ns** with CI [0.879, 1.422] ns. The best traditional row is **sample_iii_late::traditional**, sigma68 **1.457 ns** with CI [1.274, 1.652] ns. A learned point-estimate win is not an adoption claim unless its paired CI versus traditional excludes zero.

## 3. Run-63 composition audit

Run-level leave-one-run-out binned-core diagnostics:

|   run |   n_pairs |   full_core_sigma_ns |   exclude_run_core_sigma_ns |   delta_full_minus_exclude_ns |   run_only_sigma68_ns |   run_only_rms_ns |   run_median_residual_ns |
|------:|----------:|---------------------:|----------------------------:|------------------------------:|----------------------:|------------------:|-------------------------:|
|    63 |        28 |              1.99218 |                     3.22543 |                   -1.23325    |              1.82434  |           1.59059 |               -0.313523  |
|    62 |         7 |              1.99218 |                     2.32931 |                   -0.337132   |              0.825697 |           1.40204 |               -0.946849  |
|    58 |        25 |              1.99218 |                     2.228   |                   -0.235826   |              1.17944  |           1.38618 |               -0.0891808 |
|    60 |        11 |              1.99218 |                     2.03274 |                   -0.0405677  |              1.1044   |           1.29846 |               -1.21974   |
|    61 |        18 |              1.99218 |                     1.99941 |                   -0.00723276 |              1.85667  |           2.2007  |               -1.39933   |
|    59 |        11 |              1.99218 |                     1.88091 |                    0.111266   |              2.24223  |           2.29397 |               -0.47058   |
|    65 |        27 |              1.99218 |                     1.80858 |                    0.183599   |              1.93309  |           1.80968 |               -0.276894  |

Run-63 amplitude, shape, and residual occupancy compared with the rest of Sample IV:

| component     |   n_pairs |   sigma68_ns |   rms_ns |   core_sigma_ns |   central_abs_lt_1ns |   central_abs_lt_2ns |   log_amp_sum_median |   log_amp_diff_median |   peak_left_median |   peak_right_median |   tail_left_median |   tail_right_median |
|:--------------|----------:|-------------:|---------:|----------------:|---------------------:|---------------------:|---------------------:|----------------------:|-------------------:|--------------------:|-------------------:|--------------------:|
| run63         |        28 |      1.82434 |  1.59059 |         3.41579 |             0.464286 |             0.714286 |              15.0292 |             0.0284785 |                  7 |                 7.5 |           0.380905 |            0.417175 |
| non_run63     |        99 |      1.67995 |  1.77637 |         3.22543 |             0.434343 |             0.69697  |              15.1292 |             0.17212   |                  7 |                 8   |           0.393391 |            0.44669  |
| all_sample_iv |       127 |      1.79363 |  1.73704 |         1.99218 |             0.409449 |             0.708661 |              15.1173 |             0.132427  |                  7 |                 8   |           0.392227 |            0.441761 |

Run 63 has 28 of 127 pairs. Its median log-amplitude difference is closer to balanced A1/A3 response than most non-run-63 rows, and it contributes a substantial central residual component. That is exactly the pattern that can stabilize a low-count binned Gaussian fit even when its own run-only core fit is not narrow.

## 4. Synthetic mixture test

Three synthetic replacements test whether the binned-core stabilization can be replicated by composition rather than by a unique detector state:

- `random_non63_replacement`: replace the 28 run-63 rows with unconditioned bootstrap draws from non-run-63 rows.
- `feature_matched_replacement`: for each run-63 row, draw from the nearest non-run-63 rows in log-amplitude, peak-sample, tail, and area space.
- `feature_residual_matched_replacement`: additionally match absolute and signed residual occupancy. This is explicitly diagnostic, not a deployable predictor, because it conditions on the residual.

| mixture                              |   n_pairs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   core_sigma_ns |   core_sigma_ci_low_ns |   core_sigma_ci_high_ns |   rms_ns |
|:-------------------------------------|----------:|-------------:|--------------------:|---------------------:|----------------:|-----------------------:|------------------------:|---------:|
| observed_without_run63               |        99 |      1.67995 |           nan       |            nan       |         3.22543 |              nan       |                nan      |  1.77637 |
| observed_with_run63                  |       127 |      1.79363 |           nan       |            nan       |         1.99218 |              nan       |                nan      |  1.73704 |
| feature_matched_replacement          |       127 |      1.72975 |             1.51588 |              2.00031 |         3.17544 |                1.9029  |                 97.6718 |  1.75704 |
| feature_residual_matched_replacement |       127 |      1.57361 |             1.49167 |              1.74453 |         2.68723 |                1.85214 |                 91.6795 |  1.70538 |
| random_non63_replacement             |       127 |      1.72975 |             1.51977 |              2.00031 |         3.02144 |                1.87278 |                135.395  |  1.77404 |

Amplitude/shape matching alone barely changes the median binned-core result relative to leaving run 63 out. Adding residual-occupancy matching moves the median core width partway toward the observed-with-run63 state, but the very large upper intervals show that this diagnostic remains binned-fit limited. The useful conclusion is therefore narrower: run 63 stabilizes the core fit mainly by contributing central residual occupancy in a balanced amplitude/shape region; the effect does not require a separate detector-resolution parameter, but it also is not reproduced by amplitude/shape matching alone.

## 5. Unbinned hierarchical run-width check

The empirical-Bayes run-width table below avoids the unstable binned core fit and estimates each held-out run's sigma68 on the same historical run64 residuals:

|   run |   n_pairs |   sigma68_ns |   posterior_sigma68_ns |   posterior_ci_low_ns |   posterior_ci_high_ns |   posterior_rank_widest_1_is_widest |
|------:|----------:|-------------:|-----------------------:|----------------------:|-----------------------:|------------------------------------:|
|    58 |        25 |     1.17944  |                1.2606  |              0.98695  |                1.61011 |                                   6 |
|    59 |        11 |     2.24223  |                1.8938  |              1.36695  |                2.62371 |                                   1 |
|    60 |        11 |     1.1044   |                1.27987 |              0.92381  |                1.77315 |                                   5 |
|    61 |        18 |     1.85667  |                1.74683 |              1.32448  |                2.30385 |                                   4 |
|    62 |         7 |     0.825697 |                1.17901 |              0.814836 |                1.70593 |                                   7 |
|    63 |        28 |     1.82434  |                1.75359 |              1.3877   |                2.21596 |                                   3 |
|    65 |        27 |     1.93309  |                1.83068 |              1.44377  |                2.32128 |                                   2 |

Run 63 has posterior sigma68 **1.754 ns** with CI [1.388, 2.216] ns. It is not the uniquely narrow run under the unbinned model. This disfavors the detector-broadening explanation in which non-run-63 data are a coherent wider detector state and run 63 is a special narrow state.

## 6. Support and systematics

Train-versus-heldout support diagnostics:

| pool             | feature      |   train_median |   heldout_median |   ks_stat |   ks_p_value |
|:-----------------|:-------------|---------------:|-----------------:|----------:|-------------:|
| run64_only       | log_amp_sum  |     15.1116    |        15.1173   |  0.197343 |  0.570323    |
| run64_only       | log_amp_diff |      0.0799705 |         0.132427 |  0.116634 |  0.975246    |
| run64_only       | peak_left    |      7         |         7        |  0.190945 |  0.607539    |
| run64_only       | peak_right   |      8         |         8        |  0.182087 |  0.666091    |
| run64_only       | tail_left    |      0.366466  |         0.392227 |  0.213583 |  0.471309    |
| run64_only       | tail_right   |      0.432869  |         0.441761 |  0.237205 |  0.345301    |
| sample_iii_early | log_amp_sum  |     15.2825    |        15.1173   |  0.178302 |  0.000685553 |
| sample_iii_early | log_amp_diff |      0.447185  |         0.132427 |  0.270133 |  2.07072e-08 |
| sample_iii_early | peak_left    |      6         |         7        |  0.591808 |  0           |
| sample_iii_early | peak_right   |      7         |         8        |  0.521893 |  0           |
| sample_iii_early | tail_left    |      0.324985  |         0.392227 |  0.433168 |  0           |
| sample_iii_early | tail_right   |      0.350616  |         0.441761 |  0.600633 |  0           |
| sample_iii_late  | log_amp_sum  |     15.3145    |        15.1173   |  0.210923 |  3.37792e-05 |
| sample_iii_late  | log_amp_diff |      0.425546  |         0.132427 |  0.250763 |  3.48864e-07 |
| sample_iii_late  | peak_left    |      6         |         7        |  0.590241 |  5.55112e-16 |
| sample_iii_late  | peak_right   |      7         |         8        |  0.496677 |  5.55112e-16 |
| sample_iii_late  | tail_left    |      0.329341  |         0.392227 |  0.400081 |  5.55112e-16 |
| sample_iii_late  | tail_right   |      0.355109  |         0.441761 |  0.574224 |  5.55112e-16 |
| sample_iii_mixed | log_amp_sum  |     15.2994    |        15.1173   |  0.191258 |  0.000183425 |
| sample_iii_mixed | log_amp_diff |      0.437327  |         0.132427 |  0.26244  |  4.69788e-08 |
| sample_iii_mixed | peak_left    |      6         |         7        |  0.591186 |  0           |
| sample_iii_mixed | peak_right   |      7         |         8        |  0.511878 |  0           |
| sample_iii_mixed | tail_left    |      0.326813  |         0.392227 |  0.420027 |  0           |
| sample_iii_mixed | tail_right   |      0.352298  |         0.441761 |  0.590144 |  0           |

Systematic effects:

- Binned-core sensitivity to removing run 63: **1.233 ns**.
- Traditional calibration-pool spread: **0.337 ns**.
- Full method point-estimate spread: **1.577 ns**.

Caveats: only seven held-out Sample IV runs are available, run 62 has only seven selected pairs, and the binned Gaussian fit can saturate or become optimizer-window dominated. The synthetic residual-matched mixture is a causal diagnostic for occupancy, not a permissible predictive model. Neural models are laptop-scale baselines; their role is to test whether waveform capacity changes the conclusion, not to claim a final architecture optimum.

## 7. Conclusion

The run-63 effect is best explained as **stabilizing composition**. Removing run 63 removes a central, amplitude-balanced component that makes the low-stat binned Gaussian core fit well conditioned; the unbinned sigma68 and hierarchical run-width analyses do not support a coherent detector-broadening state for the non-run-63 sample. The method benchmark still finds no statistically secure learned-method adoption claim over the strong traditional comparator under run-block CIs.

The machine-readable winner is written in `result.json` as `sample_iii_mixed::composition_gated_cnn`.

## 8. Reproducibility

Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python scripts/s18h_1781034287_20851_4bfc23d1_run63_composition_broadening.py --config configs/s18h_1781034287_20851_4bfc23d1_run63_composition_broadening.json
```

Artifacts include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `leave_one_run_out_core.csv`, `run63_composition.csv`, `synthetic_mixture_summary.csv`, `hierarchical_run_widths.csv`, `support_diagnostics.csv`, and PNG diagnostics.

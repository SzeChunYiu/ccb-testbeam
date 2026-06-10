# Study report: S03f - Run-level shared monotonic downstream-stave bins

- **Ticket:** 1781020939.1148.2ac43171
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03f_1781020939_1148_2ac43171_runlevel_shared_bins.yaml`

## Question

Does a shared monotone downstream-stave timewalk curve with run-level shrinkage beat the independent per-fold S03b monotone-bin correction, and does it reduce the run 61 instability without leakage?

## Raw-ROOT reproduction gate

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

S03a/S03b run-65 reference reproduction before fitting the new model:

|   heldout_run | method               | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | train_runs        | s03a_candidate   |   s03a_alpha | s03b_mode   | s03b_direction   |   s03b_n_bins |   reference_value |   delta | pass   |
|--------------:|:---------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:------------------|:-----------------|-------------:|:------------|:-----------------|--------------:|------------------:|--------:|:-------|
|            65 | template_phase_base  | heldout_pairwise_sigma68_ns | 2.88915 |  2.63915 |   3.13915 |                198 |    -3.83043 |      2.88915 |       2.57669 |            0.0505051  |        0.442691 |    3.21363 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |           2.88915 |       0 | True   |
|            65 | s03a_amp_only        | heldout_pairwise_sigma68_ns | 1.49464 |  1.34554 |   1.6291  |                198 |     1.17923 |      1.49464 |       1.69913 |            0.00505051 |        1.26115  |    2.03718 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |           1.49464 |       0 | True   |
|            65 | s03b_monotone_binned | heldout_pairwise_sigma68_ns | 1.56958 |  1.3527  |   1.81958 |                198 |     1.03364 |      1.56958 |       1.83396 |            0.00505051 |        0.325573 |    3.14128 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |           1.56958 |       0 | True   |

## Methods

The new traditional method uses only same-pulse log amplitude and downstream stave identity. In each training fold it fits one decreasing population curve shared by B4/B6/B8, shrinks stave-population curves toward it, shrinks train-run/stave curves toward the stave curves, and deploys the average monotone train-run curve plus a configurable population weight to the held-out run. No held-out run curve is fit. The comparison is the per-fold S03b per-stave decreasing isotonic bin method. The ML comparison is the existing grouped run-split Ridge residual corrector on waveform features, trained with the same held-out run split.

|   heldout_run | component          |   n_bins |   run_shrink_strength |   deployment_population_weight |   fitted_min_ns |   fitted_max_ns |   train_bin_pulses |
|--------------:|:-------------------|---------:|----------------------:|-------------------------------:|----------------:|----------------:|-------------------:|
|            58 | population         |        8 |                   320 |                              1 |        1.07465  |        1.07465  |              11241 |
|            58 | run_stave_shrunken |        8 |                   320 |                              1 |       -2.55847  |        2.27535  |              11241 |
|            58 | stave_population   |        8 |                   320 |                              1 |       -2.02141  |        2.08358  |              11241 |
|            59 | population         |       12 |                    80 |                             16 |        0.864438 |        0.864438 |               9171 |
|            59 | run_stave_shrunken |       12 |                    80 |                             16 |       -3.45592  |        2.45738  |               9171 |
|            59 | stave_population   |       12 |                    80 |                             16 |       -2.89997  |        2.2624   |               9171 |
|            60 | population         |        6 |                   320 |                              1 |        0.949611 |        0.949611 |               9036 |
|            60 | run_stave_shrunken |        6 |                   320 |                              1 |       -2.64091  |        2.14763  |               9036 |
|            60 | stave_population   |        6 |                   320 |                              1 |       -2.06388  |        1.94668  |               9036 |
|            61 | population         |        6 |                   320 |                              0 |        1.24485  |        1.24485  |               8661 |
|            61 | run_stave_shrunken |        6 |                   320 |                              0 |       -2.72687  |        2.39913  |               8661 |
|            61 | stave_population   |        6 |                   320 |                              0 |       -2.0494   |        2.19652  |               8661 |
|            62 | population         |        8 |                   320 |                              0 |        1.08375  |        1.08375  |               9039 |
|            62 | run_stave_shrunken |        8 |                   320 |                              0 |       -2.34083  |        2.22763  |               9039 |
|            62 | stave_population   |        8 |                   320 |                              0 |       -1.73617  |        2.00792  |               9039 |
|            63 | population         |        6 |                   320 |                              0 |        1.06267  |        1.06267  |              10350 |
|            63 | run_stave_shrunken |        6 |                   320 |                              0 |       -2.85553  |        2.34847  |              10350 |
|            63 | stave_population   |        6 |                   320 |                              0 |       -2.28536  |        2.13917  |              10350 |
|            65 | population         |        8 |                   320 |                              1 |        1.08569  |        1.08569  |              11262 |
|            65 | run_stave_shrunken |        8 |                   320 |                              1 |       -2.56368  |        2.27723  |              11262 |
|            65 | stave_population   |        8 |                   320 |                              1 |       -2.02723  |        2.08496  |              11262 |

## Held-out results

|   heldout_run | method               |    value |   ci_low |   ci_high |   n_pair_residuals |   s03b_n_bins |   runlevel_n_bins |   run_shrink_strength |   deployment_population_weight |   runlevel_cv_sigma68_ns |   ml_ridge_cv_sigma68_ns |
|--------------:|:---------------------|---------:|---------:|----------:|-------------------:|--------------:|------------------:|----------------------:|-------------------------------:|-------------------------:|-------------------------:|
|            58 | ml_ridge             | 1.27047  | 1.15803  |  1.42335  |                219 |            10 |                 8 |                   320 |                              1 |                  1.09765 |                  1.56226 |
|            58 | runlevel_shared_bins | 0.566554 | 0.304281 |  0.790177 |                219 |            10 |                 8 |                   320 |                              1 |                  1.09765 |                  1.56226 |
|            58 | s03a_amp_only        | 1.18748  | 1.1382   |  1.36608  |                219 |            10 |                 8 |                   320 |                              1 |                  1.09765 |                  1.56226 |
|            58 | s03b_monotone_binned | 1.3214   | 1.3214   |  1.59643  |                219 |            10 |                 8 |                   320 |                              1 |                  1.09765 |                  1.56226 |
|            58 | template_phase_base  | 2.6428   | 2.6428   |  2.77317  |                219 |            10 |                 8 |                   320 |                              1 |                  1.09765 |                  1.56226 |
|            59 | ml_ridge             | 1.49843  | 1.44058  |  1.55087  |               2289 |             8 |                12 |                    80 |                             16 |                  1.08958 |                  1.56065 |
|            59 | runlevel_shared_bins | 1.22598  | 1.10894  |  1.24756  |               2289 |             8 |                12 |                    80 |                             16 |                  1.08958 |                  1.56065 |
|            59 | s03a_amp_only        | 1.45871  | 1.3997   |  1.52534  |               2289 |             8 |                12 |                    80 |                             16 |                  1.08958 |                  1.56065 |
|            59 | s03b_monotone_binned | 1.5      | 1.4391   |  1.56166  |               2289 |             8 |                12 |                    80 |                             16 |                  1.08958 |                  1.56065 |
|            59 | template_phase_base  | 2.99232  | 2.99232  |  3.12333  |               2289 |             8 |                12 |                    80 |                             16 |                  1.08958 |                  1.56065 |
|            60 | ml_ridge             | 1.30605  | 1.26772  |  1.3449   |               2424 |             8 |                 6 |                   320 |                              1 |                  1.10544 |                  1.53508 |
|            60 | runlevel_shared_bins | 0.997832 | 0.964161 |  1.03595  |               2424 |             8 |                 6 |                   320 |                              1 |                  1.10544 |                  1.53508 |
|            60 | s03a_amp_only        | 1.3437   | 1.28436  |  1.40343  |               2424 |             8 |                 6 |                   320 |                              1 |                  1.10544 |                  1.53508 |
|            60 | s03b_monotone_binned | 1.23065  | 1.23065  |  1.25     |               2424 |             8 |                 6 |                   320 |                              1 |                  1.10544 |                  1.53508 |
|            60 | template_phase_base  | 2.66393  | 2.66393  |  2.7113   |               2424 |             8 |                 6 |                   320 |                              1 |                  1.10544 |                  1.53508 |
|            61 | ml_ridge             | 1.96998  | 1.89331  |  2.07069  |               2799 |            12 |                 6 |                   320 |                              0 |                  1.03335 |                  1.48504 |
|            61 | runlevel_shared_bins | 1.26146  | 1.25009  |  1.3378   |               2799 |            12 |                 6 |                   320 |                              0 |                  1.03335 |                  1.48504 |
|            61 | s03a_amp_only        | 2.12996  | 1.99904  |  2.21291  |               2799 |            12 |                 6 |                   320 |                              0 |                  1.03335 |                  1.48504 |
|            61 | s03b_monotone_binned | 2.10176  | 2.10176  |  2.24799  |               2799 |            12 |                 6 |                   320 |                              0 |                  1.03335 |                  1.48504 |
|            61 | template_phase_base  | 2.70351  | 2.70351  |  2.70351  |               2799 |            12 |                 6 |                   320 |                              0 |                  1.03335 |                  1.48504 |
|            62 | ml_ridge             | 1.44698  | 1.38851  |  1.50585  |               2421 |             8 |                 8 |                   320 |                              0 |                  1.0997  |                  1.55305 |
|            62 | runlevel_shared_bins | 1.0804   | 1.03203  |  1.23819  |               2421 |             8 |                 8 |                   320 |                              0 |                  1.0997  |                  1.55305 |
|            62 | s03a_amp_only        | 1.469    | 1.41754  |  1.51539  |               2421 |             8 |                 8 |                   320 |                              0 |                  1.0997  |                  1.55305 |
|            62 | s03b_monotone_binned | 1.43743  | 1.38816  |  1.57635  |               2421 |             8 |                 8 |                   320 |                              0 |                  1.0997  |                  1.55305 |
|            62 | template_phase_base  | 2.90117  | 2.90117  |  3.02631  |               2421 |             8 |                 8 |                   320 |                              0 |                  1.0997  |                  1.55305 |
|            63 | ml_ridge             | 1.37073  | 1.29393  |  1.44027  |               1110 |             8 |                 6 |                   320 |                              0 |                  1.05608 |                  1.55091 |
|            63 | runlevel_shared_bins | 1.01686  | 0.99031  |  1.18923  |               1110 |             8 |                 6 |                   320 |                              0 |                  1.05608 |                  1.55091 |
|            63 | s03a_amp_only        | 1.39132  | 1.31086  |  1.4588   |               1110 |             8 |                 6 |                   320 |                              0 |                  1.05608 |                  1.55091 |
|            63 | s03b_monotone_binned | 1.43311  | 1.31436  |  1.56436  |               1110 |             8 |                 6 |                   320 |                              0 |                  1.05608 |                  1.55091 |
|            63 | template_phase_base  | 2.87872  | 2.87872  |  3.01249  |               1110 |             8 |                 6 |                   320 |                              0 |                  1.05608 |                  1.55091 |
|            65 | ml_ridge             | 1.39153  | 1.29823  |  1.59378  |                198 |            10 |                 8 |                   320 |                              1 |                  1.09411 |                  1.56729 |
|            65 | runlevel_shared_bins | 1.02714  | 0.763386 |  1.27973  |                198 |            10 |                 8 |                   320 |                              1 |                  1.09411 |                  1.56729 |
|            65 | s03a_amp_only        | 1.49464  | 1.33495  |  1.63158  |                198 |            10 |                 8 |                   320 |                              1 |                  1.09411 |                  1.56729 |
|            65 | s03b_monotone_binned | 1.56958  | 1.35583  |  1.81958  |                198 |            10 |                 8 |                   320 |                              1 |                  1.09411 |                  1.56729 |
|            65 | template_phase_base  | 2.88915  | 2.63915  |  3.20541  |                198 |            10 |                 8 |                   320 |                              1 |                  1.09411 |                  1.56729 |

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base  | 2.74141 |  2.68945 |   2.9894  |              11460 |             0.0813264 |
| s03a_amp_only        | 1.55109 |  1.38171 |   1.9358  |              11460 |             0.0191099 |
| s03b_monotone_binned | 1.64515 |  1.32175 |   1.94067 |              11460 |             0.019459  |
| runlevel_shared_bins | 1.16729 |  1.01023 |   1.28644 |              11460 |             0.0166667 |
| ml_ridge             | 1.53692 |  1.3454  |   1.82359 |              11460 |             0.0173647 |

Run 61 rows:

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |
|:---------------------|--------:|---------:|----------:|-------------------:|
| ml_ridge             | 1.96998 |  1.89331 |   2.07069 |               2799 |
| runlevel_shared_bins | 1.26146 |  1.25009 |   1.3378  |               2799 |
| s03a_amp_only        | 2.12996 |  1.99904 |   2.21291 |               2799 |
| s03b_monotone_binned | 2.10176 |  2.10176 |   2.24799 |               2799 |
| template_phase_base  | 2.70351 |  2.70351 |   2.70351 |               2799 |

## Leakage checks

No feature contains run number, event id, event order, other-stave timing, current, or held-out labels. Final models train only on non-held-out runs, and shuffled-target controls are repeated for run-level shared bins, S03b, and ML Ridge.

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| heldout_run_curve_not_fit                         |     1       |        1       |     1       |
| ml_ridge_shuffled_target_sigma68                  |     2.70235 |        2.88338 |     2.96631 |
| runlevel_shared_shuffled_target_sigma68           |     2.63465 |        2.86409 |     3.01042 |
| s03b_shuffled_target_sigma68                      |     2.65183 |        2.89022 |     2.99265 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

The run-level shared result is explicitly treated as a too-good leakage target (`runlevel_shared_looks_too_good=True`) because it beats the ML Ridge comparator. The direct checks remain clean: event-id overlap is `0`, the held-out run curve is never fit, final models use no held-out rows, and the minimum shuffled-target sigma68 is `2.635 ns`, well above the true run-level shared pooled width.

## Verdict

`result.json` verdict: `runlevel_shared_reduces_run61_without_leakage`.
Run-level shared bins pooled sigma68 is `1.167 ns`; S03b is `1.645 ns`; ML Ridge is `1.537 ns`.
Run 61 delta versus S03b is `-0.840 ns` (negative means reduced width).

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781020939_1148_2ac43171_runlevel_shared_bins.py --config configs/s03f_1781020939_1148_2ac43171_runlevel_shared_bins.yaml
```

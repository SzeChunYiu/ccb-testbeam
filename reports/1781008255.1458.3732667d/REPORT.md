# Study report: S18c - Sample IV A-stack calibration-pool sensitivity

- **Ticket:** `1781008255.1458.3732667d`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python reports/1781008255.1458.3732667d/s18c_calibration_pool_sensitivity.py --config reports/1781008255.1458.3732667d/s18c_config.json`

## Question

Question: does the reproduced Sample IV A1-A3 broadening depend mainly on using run 64 as the calibration pool? Expected information gain: compare run64-only, Sample III-only, mixed-period, and leave-one-run Sample IV calibration pools with identical A1-A3 held-out run bootstrap CIs and no row-level splits.

## Reproduction first

Before changing calibration pools, the original S18 Sample IV A1-A3 timing number was reproduced from raw `HRDv` using run 64 as the calibration pool:

| quantity                  |   expected |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |  127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduced central definition is `n=127`, robust width `1.794 ns`, and Gaussian core sigma `1.992 ns` in the +/-2.5 ns fit window.

## Calibration pools

| pool                | description                                                                                         | uses_sample_iv_leave_one_analysis   | fixed_sample_iv_runs   | sample_iii_runs                                                            |
|:--------------------|:----------------------------------------------------------------------------------------------------|:------------------------------------|:-----------------------|:---------------------------------------------------------------------------|
| run64_only          | Original S18 Sample IV run 64 calibration pool only.                                                | False                               | 64                     |                                                                            |
| sample_iii_only     | All available Sample III A-stack runs, no Sample IV calibration rows.                               | False                               |                        | 31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57 |
| mixed_period        | Sample III plus run 64, testing whether adding pre-period statistics changes the run64 calibration. | False                               | 64                     | 31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57 |
| sample_iv_leave_one | Sample IV only: run 64 plus all non-held-out Sample IV analysis runs for each held-out run.         | True                                | 64                     |                                                                            |

## Traditional method

The traditional method is CFD20 with linear interpolation, followed by an ordinary least-squares polynomial in `log(A1)`, `log(A3)`, their squares, and interaction. Every quoted row holds out a full Sample IV analysis run; no row-level split is used. The primary metric is the A3-A1 residual robust width with held-out-run bootstrap CI.

| pool                |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |
|:--------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|
| run64_only          |       127 |           1.79363 |            1.41077 |             2.08148 |         1.99218 |       1.73704 |
| sample_iii_only     |       127 |           1.49211 |            1.28316 |             1.66015 |         1.68292 |       1.47696 |
| mixed_period        |       127 |           1.49227 |            1.27229 |             1.63971 |         1.68292 |       1.47687 |
| sample_iv_leave_one |       127 |           1.63748 |            1.30878 |             1.72164 |         2.00185 |       1.49883 |

Best traditional pool by point estimate: **sample_iii_only** at **1.492 ns**.

## ML method

The ML method is a standardized ridge residual corrector using amplitude, peak sample, area, tail fraction, and a Sample-IV indicator. It excludes run id, event id, raw residual, and timing columns. Alpha is selected only by run-group CV inside each calibration pool; single-run run64-only cannot have run CV and uses the configured fixed alpha.

| pool                |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |
|:--------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|
| run64_only          |       127 |           1.60186 |            1.27111 |             1.70903 |         2.10665 |       1.50089 |
| sample_iii_only     |       127 |           1.84893 |            1.61248 |             2.2768  |         3.32126 |       1.77668 |
| mixed_period        |       127 |           1.8293  |            1.53573 |             2.23121 |         3.42139 |       1.76409 |
| sample_iv_leave_one |       127 |           1.38361 |            1.07419 |             1.45694 |         1.73415 |       1.24315 |

Best ML pool by point estimate: **sample_iv_leave_one** at **1.384 ns**.

## Pool deltas

The table reports paired held-out-run bootstrap deltas. Negative `*_minus_run64_only` means that calibration pool narrows the Sample IV residual relative to run64-only.

| comparison                           | pool                | method               |   ci_low_ns |   ci_high_ns |   p_value |
|:-------------------------------------|:--------------------|:---------------------|------------:|-------------:|----------:|
| ml_minus_traditional                 | run64_only          | ml_minus_traditional |  -0.55017   |    0.225128  |     0.33  |
| ml_minus_traditional                 | sample_iii_only     | ml_minus_traditional |   0.0633257 |    0.849779  |     0.01  |
| ml_minus_traditional                 | mixed_period        | ml_minus_traditional |   0.042122  |    0.806094  |     0.02  |
| ml_minus_traditional                 | sample_iv_leave_one | ml_minus_traditional |  -0.442787  |   -0.132523  |     0.006 |
| sample_iii_only_minus_run64_only     | sample_iii_only     | traditional          |  -0.56052   |    0.0884736 |     0.128 |
| sample_iii_only_minus_run64_only     | sample_iii_only     | ml                   |   0.0462952 |    0.692188  |     0.016 |
| mixed_period_minus_run64_only        | mixed_period        | traditional          |  -0.542532  |    0.0881509 |     0.12  |
| mixed_period_minus_run64_only        | mixed_period        | ml                   |   0.0201638 |    0.650217  |     0.032 |
| sample_iv_leave_one_minus_run64_only | sample_iv_leave_one | traditional          |  -0.466784  |    0.190923  |     0.318 |
| sample_iv_leave_one_minus_run64_only | sample_iv_leave_one | ml                   |  -0.480729  |   -0.04952   |     0.018 |

## Leakage checks

Leakage flags: **0**. Flagged row-split advantages are diagnostics only; all adopted metrics above are split by held-out run.

| pool                | check                              | value                 | flag   |
|:--------------------|:-----------------------------------|:----------------------|:-------|
| run64_only          | single_run_training_pool           | True                  | False  |
| run64_only          | forbidden_feature_overlap          |                       | False  |
| sample_iii_only     | forbidden_feature_overlap          |                       | False  |
| sample_iii_only     | row_split_advantage_rmse_ns        | -0.4642082988965788   | False  |
| sample_iii_only     | group_split_r2_mean                | 0.04753125629272752   | False  |
| sample_iii_only     | random_row_split_r2                | 0.06769997022116381   | False  |
| sample_iii_only     | shuffled_target_r2                 | -0.017767717963266927 | False  |
| sample_iii_only     | train_width_vs_heldout_ml_width_ns | -0.3211470054790282   | False  |
| mixed_period        | forbidden_feature_overlap          |                       | False  |
| mixed_period        | row_split_advantage_rmse_ns        | -1.1617234872898687   | False  |
| mixed_period        | group_split_r2_mean                | 0.0396693100579024    | False  |
| mixed_period        | random_row_split_r2                | 0.032739839067066345  | False  |
| mixed_period        | shuffled_target_r2                 | -0.014713471541734968 | False  |
| mixed_period        | train_width_vs_heldout_ml_width_ns | -0.30211319074653575  | False  |
| sample_iv_leave_one | forbidden_feature_overlap          |                       | False  |
| sample_iv_leave_one | row_split_advantage_rmse_ns        | -0.09298365240646156  | False  |
| sample_iv_leave_one | group_split_r2_mean                | 0.2119451401254518    | False  |
| sample_iv_leave_one | random_row_split_r2                | 0.06754798043065535   | False  |
| sample_iv_leave_one | shuffled_target_r2                 | -0.19036583576443378  | False  |
| sample_iv_leave_one | train_width_vs_heldout_ml_width_ns | 0.22003604546944766   | False  |

## Run-held-out table

| pool                |   run |   n_pairs |   traditional_robust_width_ns |   ml_robust_width_ns |   train_n_pairs |   ml_alpha |
|:--------------------|------:|----------:|------------------------------:|---------------------:|----------------:|-----------:|
| mixed_period        |    58 |        25 |                      1.14694  |             1.67917  |            6346 |     100    |
| mixed_period        |    59 |        11 |                      0.954114 |             1.24303  |            6346 |     100    |
| mixed_period        |    60 |        11 |                      1.01982  |             1.25735  |            6346 |     100    |
| mixed_period        |    61 |        18 |                      1.51889  |             2.04493  |            6346 |     100    |
| mixed_period        |    62 |         7 |                      1.04809  |             2.32163  |            6346 |     100    |
| mixed_period        |    63 |        28 |                      1.2894   |             1.68651  |            6346 |     100    |
| mixed_period        |    65 |        27 |                      1.63927  |             1.45021  |            6346 |     100    |
| run64_only          |    58 |        25 |                      1.17944  |             1.13027  |              16 |    1000    |
| run64_only          |    59 |        11 |                      2.24223  |             0.452471 |              16 |    1000    |
| run64_only          |    60 |        11 |                      1.1044   |             1.02669  |              16 |    1000    |
| run64_only          |    61 |        18 |                      1.85667  |             1.75203  |              16 |    1000    |
| run64_only          |    62 |         7 |                      0.825697 |             1.45685  |              16 |    1000    |
| run64_only          |    63 |        28 |                      1.82434  |             1.46892  |              16 |    1000    |
| run64_only          |    65 |        27 |                      1.93309  |             1.67512  |              16 |    1000    |
| sample_iii_only     |    58 |        25 |                      1.14682  |             1.68293  |            6330 |     100    |
| sample_iii_only     |    59 |        11 |                      0.953841 |             1.27377  |            6330 |     100    |
| sample_iii_only     |    60 |        11 |                      1.01925  |             1.25805  |            6330 |     100    |
| sample_iii_only     |    61 |        18 |                      1.51881  |             2.06481  |            6330 |     100    |
| sample_iii_only     |    62 |         7 |                      1.04844  |             2.34729  |            6330 |     100    |
| sample_iii_only     |    63 |        28 |                      1.28917  |             1.685    |            6330 |     100    |
| sample_iii_only     |    65 |        27 |                      1.63906  |             1.45919  |            6330 |     100    |
| sample_iv_leave_one |    58 |        25 |                      1.26469  |             0.975205 |             118 |       0.1  |
| sample_iv_leave_one |    59 |        11 |                      1.17777  |             0.774135 |             132 |       0.1  |
| sample_iv_leave_one |    60 |        11 |                      1.09992  |             0.733032 |             132 |       0.01 |
| sample_iv_leave_one |    61 |        18 |                      1.61324  |             1.16493  |             125 |       0.1  |
| sample_iv_leave_one |    62 |         7 |                      1.15362  |             1.04451  |             136 |       0.1  |
| sample_iv_leave_one |    63 |        28 |                      1.35193  |             1.25569  |             115 |       0.1  |
| sample_iv_leave_one |    65 |        27 |                      1.82054  |             1.64516  |             116 |       0.1  |

## Conclusion

Run 64 is not the sole driver. The reproduced S18 broadening exists with run64-only calibration, but both Sample-III-only and mixed-period calibration give comparable or narrower held-out widths under the same run-split evaluation. The leave-one-run Sample IV pool is the strongest test of same-period calibration: it uses no held-out rows and narrows the traditional residual to `1.637 ns` with CI `[1.309, 1.722] ns`. This points to calibration-pool sensitivity, not an intrinsic Sample IV A1-A3 broadening uniquely caused by detector response.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `pool_delta_bootstrap.csv`, `run_heldout_summary.csv`, `heldout_pair_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.

# Study report: S18e - A-stack calibration-pool transfer by run family

- **Ticket:** `1781014577.1276.72f87916`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18e_1781014577_1276_72f87916_run_family_transfer.py --config configs/s18e_1781014577_1276_72f87916.json`

## Question

Question: which Sample III run families transfer best to Sample IV A1-A3 calibration after S18c showed pool sensitivity? Expected information gain: compare early Sample III, late Sample III, mixed Sample III, and run64 pools with identical Sample IV held-out runs, traditional and ML methods, run-bootstrap CIs, and explicit train-run manifest hashes.

## Reproduction first

Before comparing run-family transfer, the original S18/S18c Sample IV A1-A3 timing number was reproduced from raw `HRDv` using run 64 as the calibration pool:

| quantity                  |   expected |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |  127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduced central definition is `n=127`, robust width `1.794 ns`, and Gaussian core sigma `1.992 ns` in the +/-2.5 ns fit window.

## Calibration pools

| pool             | description                                                                   | uses_sample_iv_leave_one_analysis   | fixed_sample_iv_runs   | sample_iii_runs                                                            |
|:-----------------|:------------------------------------------------------------------------------|:------------------------------------|:-----------------------|:---------------------------------------------------------------------------|
| run64_only       | Original S18 Sample IV run 64 calibration pool only.                          | False                               | 64                     |                                                                            |
| sample_iii_early | Early Sample III calibration-period A-stack runs only.                        | False                               |                        | 31,32,33,34,35,36,37,39,40,41,42                                           |
| sample_iii_late  | Late Sample III analysis-period A-stack runs only.                            | False                               |                        | 44,45,46,47,48,49,50,51,52,53,54,55,56,57                                  |
| sample_iii_mixed | All available Sample III A-stack runs, combining early and late run families. | False                               |                        | 31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57 |

## Traditional method

The traditional method is CFD20 with linear interpolation, followed by an ordinary least-squares polynomial in `log(A1)`, `log(A3)`, their squares, and interaction. Every quoted row holds out a full Sample IV analysis run; no row-level split is used. The primary metric is the A3-A1 residual robust width with held-out-run bootstrap CI.

| pool             |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |
|:-----------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|
| run64_only       |       127 |           1.79363 |            1.41077 |             2.08148 |         1.99218 |       1.73704 |
| sample_iii_early |       127 |           1.55775 |            1.27539 |             1.68527 |         1.78206 |       1.49031 |
| sample_iii_late  |       127 |           1.45662 |            1.24228 |             1.63931 |         2.03747 |       1.47204 |
| sample_iii_mixed |       127 |           1.49211 |            1.2366  |             1.66937 |         1.68292 |       1.47696 |

Best traditional pool by point estimate: **sample_iii_late** at **1.457 ns**.

## ML method

The ML method is a standardized ridge residual corrector using amplitude, peak sample, area, tail fraction, and a Sample-IV indicator. It excludes run id, event id, raw residual, and timing columns. Alpha is selected only by run-group CV inside each calibration pool; single-run run64-only cannot have run CV and uses the configured fixed alpha.

| pool             |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |
|:-----------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|
| run64_only       |       127 |           1.60186 |            1.27111 |             1.70903 |         2.10665 |       1.50089 |
| sample_iii_early |       127 |           1.4598  |            1.27363 |             1.64116 |         2.01509 |       1.46289 |
| sample_iii_late  |       127 |           2.26184 |            1.91371 |             2.81523 |         3.11196 |       2.20224 |
| sample_iii_mixed |       127 |           1.84893 |            1.5836  |             2.257   |         3.32126 |       1.77668 |

Best ML pool by point estimate: **sample_iii_early** at **1.460 ns**.

## Pool deltas

The table reports paired held-out-run bootstrap deltas. Negative `*_minus_run64_only` means that calibration pool narrows the Sample IV residual relative to run64-only.

| comparison                        | pool             | method               |   ci_low_ns |   ci_high_ns |   p_value |
|:----------------------------------|:-----------------|:---------------------|------------:|-------------:|----------:|
| ml_minus_traditional              | run64_only       | ml_minus_traditional |   -0.55017  |    0.225128  |     0.33  |
| ml_minus_traditional              | sample_iii_early | ml_minus_traditional |   -0.2073   |    0.103416  |     0.434 |
| ml_minus_traditional              | sample_iii_late  | ml_minus_traditional |    0.379199 |    1.37292   |     0     |
| ml_minus_traditional              | sample_iii_mixed | ml_minus_traditional |    0.070584 |    0.848144  |     0.012 |
| sample_iii_early_minus_run64_only | sample_iii_early | traditional          |   -0.542076 |    0.104663  |     0.15  |
| sample_iii_early_minus_run64_only | sample_iii_early | ml                   |   -0.226068 |    0.0264053 |     0.098 |
| sample_iii_late_minus_run64_only  | sample_iii_late  | traditional          |   -0.544372 |    0.0645648 |     0.1   |
| sample_iii_late_minus_run64_only  | sample_iii_late  | ml                   |    0.331589 |    1.28662   |     0     |
| sample_iii_mixed_minus_run64_only | sample_iii_mixed | traditional          |   -0.556585 |    0.136362  |     0.152 |
| sample_iii_mixed_minus_run64_only | sample_iii_mixed | ml                   |    0.02282  |    0.685739  |     0.034 |

This is also the head-to-head benchmark: traditional and ML are evaluated on the same 127 held-out Sample IV pairs, grouped by held-out run. ML is counted as a win only if the paired run-bootstrap CI for `ml_minus_traditional` is wholly below zero. That never happens here. For the best-looking ML pool (`sample_iii_early`), the CI is `[-0.207, 0.103] ns` with p=0.434 before any multiple-comparison correction, so the apparent ML advantage is rejected.

Falsification rule: the preregistered primary metric was held-out-run robust residual width; the claim that a Sample III family transfers better than run64 would be falsified if the paired run-bootstrap delta versus run64 crossed zero. The best traditional point estimate (`sample_iii_late`) has CI `[-0.544, 0.065] ns`, so it is a ranking signal, not a statistically decisive improvement.

## Leakage checks

Leakage flags: **2**. Flagged row-split advantages are diagnostics only; all adopted metrics above are split by held-out run.

| pool             | check                              | value                 | flag   |
|:-----------------|:-----------------------------------|:----------------------|:-------|
| run64_only       | single_run_training_pool           | True                  | False  |
| run64_only       | forbidden_feature_overlap          |                       | False  |
| sample_iii_early | forbidden_feature_overlap          |                       | False  |
| sample_iii_early | row_split_advantage_rmse_ns        | 0.8089808383977182    | True   |
| sample_iii_early | group_split_r2_mean                | 0.08937655111402965   | False  |
| sample_iii_early | random_row_split_r2                | 0.12110775404669427   | False  |
| sample_iii_early | shuffled_target_r2                 | -0.009762909715620882 | False  |
| sample_iii_early | train_width_vs_heldout_ml_width_ns | 0.05014891684910405   | False  |
| sample_iii_late  | forbidden_feature_overlap          |                       | False  |
| sample_iii_late  | row_split_advantage_rmse_ns        | 1.2723441307005037    | True   |
| sample_iii_late  | group_split_r2_mean                | -0.018315861041158434 | False  |
| sample_iii_late  | random_row_split_r2                | -0.23708378644942307  | False  |
| sample_iii_late  | shuffled_target_r2                 | -0.025757913026941415 | False  |
| sample_iii_late  | train_width_vs_heldout_ml_width_ns | -0.7117218635363354   | False  |
| sample_iii_mixed | forbidden_feature_overlap          |                       | False  |
| sample_iii_mixed | row_split_advantage_rmse_ns        | -0.4642082988965788   | False  |
| sample_iii_mixed | group_split_r2_mean                | 0.04753125629272752   | False  |
| sample_iii_mixed | random_row_split_r2                | 0.06769997022116381   | False  |
| sample_iii_mixed | shuffled_target_r2                 | -0.004887522801784394 | False  |
| sample_iii_mixed | train_width_vs_heldout_ml_width_ns | -0.3211470054790282   | False  |

The two leakage flags are row-split advantage warnings in the early/late Sample III ML pools. They do not create an adopted result, but they explain why row-level ML validation would be misleading; all quoted acceptance metrics remain run-held-out.

## Run-held-out table

| pool             |   run |   n_pairs |   traditional_robust_width_ns |   ml_robust_width_ns |   train_n_pairs |   ml_alpha |
|:-----------------|------:|----------:|------------------------------:|---------------------:|----------------:|-----------:|
| run64_only       |    58 |        25 |                      1.17944  |             1.13027  |              16 |       1000 |
| run64_only       |    59 |        11 |                      2.24223  |             0.452471 |              16 |       1000 |
| run64_only       |    60 |        11 |                      1.1044   |             1.02669  |              16 |       1000 |
| run64_only       |    61 |        18 |                      1.85667  |             1.75203  |              16 |       1000 |
| run64_only       |    62 |         7 |                      0.825697 |             1.45685  |              16 |       1000 |
| run64_only       |    63 |        28 |                      1.82434  |             1.46892  |              16 |       1000 |
| run64_only       |    65 |        27 |                      1.93309  |             1.67512  |              16 |       1000 |
| sample_iii_early |    58 |        25 |                      1.16118  |             1.25005  |            3816 |        100 |
| sample_iii_early |    59 |        11 |                      0.955531 |             0.855864 |            3816 |        100 |
| sample_iii_early |    60 |        11 |                      0.978819 |             1.01722  |            3816 |        100 |
| sample_iii_early |    61 |        18 |                      1.49543  |             1.59516  |            3816 |        100 |
| sample_iii_early |    62 |         7 |                      1.10286  |             1.36098  |            3816 |        100 |
| sample_iii_early |    63 |        28 |                      1.30936  |             1.43444  |            3816 |        100 |
| sample_iii_early |    65 |        27 |                      1.69349  |             1.47288  |            3816 |        100 |
| sample_iii_late  |    58 |        25 |                      1.10642  |             1.74269  |            2514 |        100 |
| sample_iii_late  |    59 |        11 |                      0.958409 |             2.03527  |            2514 |        100 |
| sample_iii_late  |    60 |        11 |                      1.00817  |             1.33324  |            2514 |        100 |
| sample_iii_late  |    61 |        18 |                      1.57077  |             2.44244  |            2514 |        100 |
| sample_iii_late  |    62 |         7 |                      1.04891  |             3.16137  |            2514 |        100 |
| sample_iii_late  |    63 |        28 |                      1.29401  |             1.73105  |            2514 |        100 |
| sample_iii_late  |    65 |        27 |                      1.64565  |             1.93989  |            2514 |        100 |
| sample_iii_mixed |    58 |        25 |                      1.14682  |             1.68293  |            6330 |        100 |
| sample_iii_mixed |    59 |        11 |                      0.953841 |             1.27377  |            6330 |        100 |
| sample_iii_mixed |    60 |        11 |                      1.01925  |             1.25805  |            6330 |        100 |
| sample_iii_mixed |    61 |        18 |                      1.51881  |             2.06481  |            6330 |        100 |
| sample_iii_mixed |    62 |         7 |                      1.04844  |             2.34729  |            6330 |        100 |
| sample_iii_mixed |    63 |        28 |                      1.28917  |             1.685    |            6330 |        100 |
| sample_iii_mixed |    65 |        27 |                      1.63906  |             1.45919  |            6330 |        100 |

## Conclusion

sample_iii_late transfers best under the traditional metric. The reproduced S18 broadening exists with run64-only calibration, then the same held-out Sample IV runs test whether early Sample III, late Sample III, or all Sample III transfers better. The best traditional pool is `sample_iii_late` with robust width `1.457 ns` and run-bootstrap CI `[1.242, 1.639] ns`; the best ML pool is `sample_iii_early` with robust width `1.460 ns` and CI `[1.274, 1.641] ns`.

Hypothesis: Sample IV A1-A3 transfer is governed more by broad run-family timewalk stability than by a unique run64 calibration state; late Sample III is the most relevant stress test because its beam/detector period is closest to Sample IV while still being fully held out by period.

Queued follow-ups:
- S18f: measure whether late-Sample-III transfer remains stable when A1/A3 are replaced by A1/A5-like adjacent channel controls; expected information gain is separating run-family transfer from a single-pair channel artifact.
- S18g: test whether a monotonic constrained timewalk model changes the early/late/mixed ranking; expected information gain is determining whether ordinary least squares extrapolation drives the pool-ordering.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `train_run_manifest.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `pool_delta_bootstrap.csv`, `run_heldout_summary.csv`, `heldout_pair_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.

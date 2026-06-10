# Study report: S18f - frozen percentile-68 A-stack timing ledger

- **Ticket:** `1781033800.1208.40865e32`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Depends on:** S18, S18b, S18c, S18d, S18e
- **Inputs:** raw A-stack ROOT runs 31-65 under `data/root/root`
- **Git commit:** `2453b203bc4db1178d3d4e56e58cfeebf2220cd5`
- **Config:** `configs/s18f_1781033800_1208_40865e32_percentile68_astack_ledger.json`

## 0. Question

Question: can the S18/S18b/S18c/S18d A-stack timing reports be rerun or reconciled with the frozen percentile68_ns primary estimator and the S18e tolerance table? Expected information gain: a single comparable A-stack timing ledger that removes low-stat binned Gaussian core-sigma ambiguity.

The pre-registered primary estimator is the median-centered percentile-68 width

\[
\sigma_{68} = \frac{Q_{84}(r - \mathrm{median}(r)) - Q_{16}(r - \mathrm{median}(r))}{2},
\]

where \(r=t_{A3}-t_{A1}-\hat f(A_1,A_3,\ldots)\).  Uncertainty intervals resample whole held-out Sample IV runs, not events.

## 1. Reproduction

The S18e run64-only Sample IV A1-A3 number was rerun from raw `HRDv` waveforms before building the ledger:

| quantity                  |   expected |   reproduced |        delta |   tolerance | pass   |
|:--------------------------|-----------:|-------------:|-------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |  127       |    127       |  0           |       0     | True   |
| sample_iv_percentile68_ns |    1.79363 |      1.79359 | -3.62108e-05 |       0.001 | True   |
| sample_iv_core_sigma_ns   |    1.99218 |      1.99218 |  5.19417e-07 |       0.001 | True   |

All rows pass.  The reproduced percentile-68 value is the frozen primary number; binned Gaussian core sigma is retained only as a diagnostic because S18d showed large low-statistics fit-window sensitivity.

## 2. Frozen S18-S18e ledger

The table below reconciles the previous S18 chain onto `percentile68_ns`.  Rows without CIs are historical reproductions where the earlier report did not provide a run-bootstrap CI for that exact row.

| source   | pool                | method                 |   percentile68_ns |   ci_low_ns |   ci_high_ns | note                                                    |
|:---------|:--------------------|:-----------------------|------------------:|------------:|-------------:|:--------------------------------------------------------|
| S18      | sample_iii          | traditional            |           1.38906 |     1.3394  |      1.45282 | original S18 primary Sample III sigma68                 |
| S18      | sample_iii          | ridge                  |           1.38289 |     1.33704 |      1.42639 | original S18 run-group CV ridge                         |
| S18b     | sample_iv_loro      | traditional            |           1.47108 |     1.28925 |      1.68489 | Sample IV LORO traditional                              |
| S18b     | sample_iv_loro      | ridge                  |           1.93537 |     1.68652 |      2.32163 | Sample IV LORO ridge                                    |
| S18c     | run64_only          | traditional            |           1.79363 |     1.41077 |      2.08148 | prior pool ledger                                       |
| S18c     | sample_iii_only     | traditional            |           1.49211 |     1.28316 |      1.66015 | prior pool ledger                                       |
| S18c     | mixed_period        | traditional            |           1.49227 |     1.27229 |      1.63971 | prior pool ledger                                       |
| S18c     | sample_iv_leave_one | traditional            |           1.63748 |     1.30878 |      1.72164 | prior pool ledger                                       |
| S18c     | run64_only          | ridge                  |           1.60186 |     1.27111 |      1.70903 | prior pool ledger                                       |
| S18c     | sample_iii_only     | ridge                  |           1.84893 |     1.61248 |      2.2768  | prior pool ledger                                       |
| S18c     | mixed_period        | ridge                  |           1.8293  |     1.53573 |      2.23121 | prior pool ledger                                       |
| S18c     | sample_iv_leave_one | ridge                  |           1.38361 |     1.07419 |      1.45694 | prior pool ledger                                       |
| S18d     | historical_run64    | traditional            |           1.79363 |   nan       |    nan       | S18d historical rerun; binned core demoted from primary |
| S18d     | historical_run64    | student_t              |           1.23987 |     1.05844 |      1.36846 | unbinned robust alternative                             |
| S18e     | run64_only          | traditional            |           1.79363 |     1.41077 |      2.08148 | prior pool ledger                                       |
| S18e     | sample_iii_early    | traditional            |           1.55775 |     1.27539 |      1.68527 | prior pool ledger                                       |
| S18e     | sample_iii_late     | traditional            |           1.45662 |     1.24228 |      1.63931 | prior pool ledger                                       |
| S18e     | sample_iii_mixed    | traditional            |           1.49211 |     1.2366  |      1.66937 | prior pool ledger                                       |
| S18e     | run64_only          | ridge                  |           1.60186 |     1.27111 |      1.70903 | prior pool ledger                                       |
| S18e     | sample_iii_early    | ridge                  |           1.4598  |     1.27363 |      1.64116 | prior pool ledger                                       |
| S18e     | sample_iii_late     | ridge                  |           2.26184 |     1.91371 |      2.81523 | prior pool ledger                                       |
| S18e     | sample_iii_mixed    | ridge                  |           1.84893 |     1.5836  |      2.257   | prior pool ledger                                       |
| S18f     | run64_only          | traditional            |           1.79359 |     1.40951 |      2.08149 | S18f rerun from raw ROOT                                |
| S18f     | run64_only          | ridge                  |           1.605   |     1.27371 |      1.70414 | S18f rerun from raw ROOT                                |
| S18f     | run64_only          | gradient_boosted_trees |           1.60997 |     1.27369 |      1.70745 | S18f rerun from raw ROOT                                |
| S18f     | run64_only          | mlp                    |           1.94882 |     1.78669 |      2.36621 | S18f rerun from raw ROOT                                |
| S18f     | run64_only          | cnn_1d                 |           1.58605 |     1.25698 |      1.6939  | S18f rerun from raw ROOT                                |
| S18f     | run64_only          | gated_cnn              |           1.56305 |     1.27    |      1.73882 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_early    | traditional            |           1.55775 |     1.27528 |      1.68509 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_early    | ridge                  |           1.45869 |     1.23301 |      1.57496 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_early    | gradient_boosted_trees |           2.23927 |     1.56344 |      2.62403 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_early    | mlp                    |           2.75856 |     1.95786 |      4.02036 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_early    | cnn_1d                 |           1.54684 |     1.25583 |      1.69669 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_early    | gated_cnn              |           1.56253 |     1.30443 |      1.694   | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_late     | traditional            |           1.45662 |     1.23408 |      1.64111 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_late     | ridge                  |           1.91727 |     1.64545 |      2.25541 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_late     | gradient_boosted_trees |           3.04708 |     2.16993 |      3.37778 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_late     | mlp                    |           1.49712 |     1.11522 |      1.75072 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_late     | cnn_1d                 |           1.54716 |     1.2548  |      1.69688 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_late     | gated_cnn              |           1.4496  |     1.24089 |      1.63677 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_mixed    | traditional            |           1.49211 |     1.27469 |      1.65547 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_mixed    | ridge                  |           1.89687 |     1.63824 |      2.30552 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_mixed    | gradient_boosted_trees |           2.86431 |     1.68355 |      3.54856 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_mixed    | mlp                    |           1.43705 |     1.24176 |      1.59132 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_mixed    | cnn_1d                 |           1.54767 |     1.24353 |      1.69825 | S18f rerun from raw ROOT                                |
| S18f     | sample_iii_mixed    | gated_cnn              |           1.48637 |     1.30379 |      1.65939 | S18f rerun from raw ROOT                                |

S18e tolerance anchor rows:

| source   | pool             | method      |   percentile68_ns |   ci_low_ns |   ci_high_ns | note              |
|:---------|:-----------------|:------------|------------------:|------------:|-------------:|:------------------|
| S18e     | run64_only       | traditional |           1.79363 |     1.41077 |      2.08148 | prior pool ledger |
| S18e     | sample_iii_early | traditional |           1.55775 |     1.27539 |      1.68527 | prior pool ledger |
| S18e     | sample_iii_late  | traditional |           1.45662 |     1.24228 |      1.63931 | prior pool ledger |
| S18e     | sample_iii_mixed | traditional |           1.49211 |     1.2366  |      1.66937 | prior pool ledger |
| S18e     | run64_only       | ridge       |           1.60186 |     1.27111 |      1.70903 | prior pool ledger |
| S18e     | sample_iii_early | ridge       |           1.4598  |     1.27363 |      1.64116 | prior pool ledger |
| S18e     | sample_iii_late  | ridge       |           2.26184 |     1.91371 |      2.81523 | prior pool ledger |
| S18e     | sample_iii_mixed | ridge       |           1.84893 |     1.5836  |      2.257   | prior pool ledger |

## 3. Traditional method

The traditional baseline is deliberately strong: CFD20 linear interpolation after per-channel median-baseline subtraction, followed by an ordinary least-squares log-amplitude timewalk model

\[
\hat f_\mathrm{trad} = \beta_0 + \beta_1\log A_1 + \beta_2\log A_3
 + \beta_3(\log A_1)^2 + \beta_4(\log A_3)^2
 + \beta_5\log A_1\log A_3 + \beta_6 I_\mathrm{SampleIV} .
\]

Each calibration pool is trained once, then evaluated on the same held-out Sample IV runs 58-63 and 65.  The strongest traditional row is `sample_iii_late` with sigma68 `1.457` ns.

## 4. ML and NN methods

The ridge, gradient-boosted tree, and MLP models use engineered waveform/timing features that exclude run id, event id, raw residual, and timing columns.  The 1D CNN sees only the two normalized 18-sample A1/A3 waveforms.  The new architecture, `gated_cnn`, concatenates a CNN waveform embedding with a small engineered-feature gate before the residual head.  Hyperparameters are selected by GroupKFold over training runs where at least two training runs exist; run64-only uses the configured single-run fallback and is marked in `ml_cv_scan.csv`.

Best row per method:

| method                 | pool             |   n_pairs |   percentile68_ns |   percentile68_ci_low_ns |   percentile68_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt5ns |   core_sigma_ns |   chi2_ndf |
|:-----------------------|:-----------------|----------:|------------------:|-------------------------:|--------------------------:|--------------:|--------------------------:|----------------:|-----------:|
| mlp                    | sample_iii_mixed |       127 |           1.43705 |                  1.24176 |                   1.59132 |       1.72321 |                  0.015748 |         1.64398 |    1.06656 |
| gated_cnn              | sample_iii_late  |       127 |           1.4496  |                  1.24089 |                   1.63677 |       1.48754 |                  0        |         1.963   |    1.43535 |
| traditional            | sample_iii_late  |       127 |           1.45662 |                  1.23408 |                   1.64111 |       1.47204 |                  0        |         2.03747 |    1.84835 |
| ridge                  | sample_iii_early |       127 |           1.45869 |                  1.23301 |                   1.57496 |       1.47621 |                  0        |         1.54133 |    1.40961 |
| cnn_1d                 | sample_iii_early |       127 |           1.54684 |                  1.25583 |                   1.69669 |       1.47379 |                  0        |         1.53941 |    1.00445 |
| gradient_boosted_trees | run64_only       |       127 |           1.60997 |                  1.27369 |                   1.70745 |       1.49924 |                  0        |         1.87499 |    2.02207 |

## 5. Head-to-head benchmark

All methods below are evaluated on the same 127 held-out Sample IV pairs.  Negative deltas mean the ML/NN method narrowed sigma68 relative to the strong traditional baseline in the same calibration pool.

| pool             | method                 |   n_pairs |   percentile68_ns |   percentile68_ci_low_ns |   percentile68_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt5ns |   core_sigma_ns |   chi2_ndf |
|:-----------------|:-----------------------|----------:|------------------:|-------------------------:|--------------------------:|--------------:|--------------------------:|----------------:|-----------:|
| run64_only       | traditional            |       127 |           1.79359 |                  1.40951 |                   2.08149 |       1.73703 |                0          |         1.99218 |   1.53564  |
| run64_only       | ridge                  |       127 |           1.605   |                  1.27371 |                   1.70414 |       1.49948 |                0          |         1.89947 |   1.57549  |
| run64_only       | gradient_boosted_trees |       127 |           1.60997 |                  1.27369 |                   1.70745 |       1.49924 |                0          |         1.87499 |   2.02207  |
| run64_only       | mlp                    |       127 |           1.94882 |                  1.78669 |                   2.36621 |       1.95581 |                0.00787402 |         3.50297 |   1.07984  |
| run64_only       | cnn_1d                 |       127 |           1.58605 |                  1.25698 |                   1.6939  |       1.49355 |                0          |         2.28249 |   1.80275  |
| run64_only       | gated_cnn              |       127 |           1.56305 |                  1.27    |                   1.73882 |       1.51574 |                0          |         2.06008 |   1.19169  |
| sample_iii_early | traditional            |       127 |           1.55775 |                  1.27528 |                   1.68509 |       1.49031 |                0          |         1.78206 |   1.02814  |
| sample_iii_early | ridge                  |       127 |           1.45869 |                  1.23301 |                   1.57496 |       1.47621 |                0          |         1.54133 |   1.40961  |
| sample_iii_early | gradient_boosted_trees |       127 |           2.23927 |                  1.56344 |                   2.62403 |       2.14755 |                0.015748   |         1.96545 |   1.53374  |
| sample_iii_early | mlp                    |       127 |           2.75856 |                  1.95786 |                   4.02036 |       3.6853  |                0.110236   |         2.49893 |   1.18085  |
| sample_iii_early | cnn_1d                 |       127 |           1.54684 |                  1.25583 |                   1.69669 |       1.47379 |                0          |         1.53941 |   1.00445  |
| sample_iii_early | gated_cnn              |       127 |           1.56253 |                  1.30443 |                   1.694   |       1.53182 |                0          |         2.24351 |   1.37691  |
| sample_iii_late  | traditional            |       127 |           1.45662 |                  1.23408 |                   1.64111 |       1.47204 |                0          |         2.03747 |   1.84835  |
| sample_iii_late  | ridge                  |       127 |           1.91727 |                  1.64545 |                   2.25541 |       1.88113 |                0.00787402 |         1.88025 |   1.2444   |
| sample_iii_late  | gradient_boosted_trees |       127 |           3.04708 |                  2.16993 |                   3.37778 |       3.29556 |                0.110236   |         2.07289 |   0.786954 |
| sample_iii_late  | mlp                    |       127 |           1.49712 |                  1.11522 |                   1.75072 |       1.66444 |                0.00787402 |         1.62043 |   1.24595  |
| sample_iii_late  | cnn_1d                 |       127 |           1.54716 |                  1.2548  |                   1.69688 |       1.47296 |                0          |         2.05859 |   1.22433  |
| sample_iii_late  | gated_cnn              |       127 |           1.4496  |                  1.24089 |                   1.63677 |       1.48754 |                0          |         1.963   |   1.43535  |
| sample_iii_mixed | traditional            |       127 |           1.49211 |                  1.27469 |                   1.65547 |       1.47696 |                0          |         1.68292 |   1.04604  |
| sample_iii_mixed | ridge                  |       127 |           1.89687 |                  1.63824 |                   2.30552 |       1.90046 |                0          |        13.0864  |   1.60636  |
| sample_iii_mixed | gradient_boosted_trees |       127 |           2.86431 |                  1.68355 |                   3.54856 |       2.75311 |                0.11811    |         1.83258 |   1.01496  |
| sample_iii_mixed | mlp                    |       127 |           1.43705 |                  1.24176 |                   1.59132 |       1.72321 |                0.015748   |         1.64398 |   1.06656  |
| sample_iii_mixed | cnn_1d                 |       127 |           1.54767 |                  1.24353 |                   1.69825 |       1.47171 |                0          |         1.75575 |   1.05318  |
| sample_iii_mixed | gated_cnn              |       127 |           1.48637 |                  1.30379 |                   1.65939 |       1.51092 |                0          |         1.95958 |   0.974316 |

Paired run-bootstrap deltas:

| pool             | comparison                               | method                 | baseline    |   delta_ci_low_ns |   delta_ci_high_ns |   p_value |
|:-----------------|:-----------------------------------------|:-----------------------|:------------|------------------:|-------------------:|----------:|
| run64_only       | ridge_minus_traditional                  | ridge                  | traditional |        -0.548948  |          0.196028  |     0.284 |
| run64_only       | gradient_boosted_trees_minus_traditional | gradient_boosted_trees | traditional |        -0.532929  |          0.182209  |     0.312 |
| run64_only       | mlp_minus_traditional                    | mlp                    | traditional |        -0.0951533 |          0.581153  |     0.218 |
| run64_only       | cnn_1d_minus_traditional                 | cnn_1d                 | traditional |        -0.531108  |          0.222183  |     0.316 |
| run64_only       | gated_cnn_minus_traditional              | gated_cnn              | traditional |        -0.602257  |          0.288697  |     0.254 |
| sample_iii_early | ridge_minus_traditional                  | ridge                  | traditional |        -0.191883  |          0.0184623 |     0.094 |
| sample_iii_early | gradient_boosted_trees_minus_traditional | gradient_boosted_trees | traditional |        -0.0215204 |          1.26679   |     0.066 |
| sample_iii_early | mlp_minus_traditional                    | mlp                    | traditional |         0.454318  |          2.58745   |     0     |
| sample_iii_early | cnn_1d_minus_traditional                 | cnn_1d                 | traditional |        -0.140402  |          0.214735  |     0.83  |
| sample_iii_early | gated_cnn_minus_traditional              | gated_cnn              | traditional |        -0.142148  |          0.172803  |     0.814 |
| sample_iii_late  | ridge_minus_traditional                  | ridge                  | traditional |         0.163881  |          0.86608   |     0     |
| sample_iii_late  | gradient_boosted_trees_minus_traditional | gradient_boosted_trees | traditional |         0.690796  |          2.02375   |     0     |
| sample_iii_late  | mlp_minus_traditional                    | mlp                    | traditional |        -0.203839  |          0.171273  |     0.776 |
| sample_iii_late  | cnn_1d_minus_traditional                 | cnn_1d                 | traditional |        -0.105355  |          0.22745   |     0.416 |
| sample_iii_late  | gated_cnn_minus_traditional              | gated_cnn              | traditional |        -0.118419  |          0.0722985 |     0.582 |
| sample_iii_mixed | ridge_minus_traditional                  | ridge                  | traditional |         0.130037  |          0.868157  |     0.004 |
| sample_iii_mixed | gradient_boosted_trees_minus_traditional | gradient_boosted_trees | traditional |         0.172366  |          2.18181   |     0     |
| sample_iii_mixed | mlp_minus_traditional                    | mlp                    | traditional |        -0.263443  |          0.108968  |     0.518 |
| sample_iii_mixed | cnn_1d_minus_traditional                 | cnn_1d                 | traditional |        -0.119427  |          0.221635  |     0.436 |
| sample_iii_mixed | gated_cnn_minus_traditional              | gated_cnn              | traditional |        -0.135158  |          0.141023  |     0.98  |

Winner by pre-registered point estimate is **mlp** in pool **sample_iii_mixed**, with sigma68 **1.437 ns** and CI **[1.242, 1.591] ns**.  It is treated as a ranking result, not a decisive adoption claim, unless its paired CI versus the traditional row in the same pool excludes zero.

## 6. Falsification and leakage controls

Pre-registration: freeze sigma68 as primary, use held-out Sample IV runs 58-63/65, and require paired run-bootstrap CIs to exclude zero before claiming an ML win.  Multiple comparison count is 20 ML/NN rows (5 nontraditional methods times 4 pools), so uncorrected p-values are descriptive.

Leakage checks:

| check                     | value                                             | flag   |
|:--------------------------|:--------------------------------------------------|:-------|
| split_by_run              | train pools disjoint from Sample IV analysis runs | False  |
| forbidden_feature_overlap |                                                   | False  |
| row_level_shuffle_used    | False                                             | False  |
| cnn_target_columns_used   | False                                             | False  |
| single_run_run64_pool     | True                                              | False  |

The adopted comparisons are split by run.  Feature matrices exclude run/event identifiers and target timing columns; the CNN waveforms are normalized by each pulse amplitude and contain no residual label.

## 7. Systematics and caveats

Systematic spread estimates:

| source | spread_ns |
|---|---:|
| traditional_pool_range | 0.336973 |
| method_best_row_range | 0.172916 |
| core_minus_sigma68_abs_median | 0.284147 |

The dominant caveat remains low Sample IV statistics (`n=127` pairs).  The binned Gaussian core sigma has unstable chi2/ndf and can move independently of sigma68.  CNN rows are laptop-scale neural baselines, not LUNARC-scale architecture searches.  The sklearn MLP emitted non-convergence warnings at the configured iteration cap, so its point-estimate win is especially diagnostic rather than adoptable.

## 8. Findings and next step

The ledger removes the historical ambiguity between robust percentile widths and low-statistics binned core sigma.  The A-stack conclusion remains consistent with S18e: Sample IV broadening is mostly calibration-pool and estimator sensitivity, and a strong traditional timewalk model is hard to beat decisively.

Hypothesis: A-stack transfer is limited by sparse run-family coverage and channel-local timewalk drift, not by missing waveform expressivity.  A falsifying result would be a support-preserving waveform model whose paired run-bootstrap CI is wholly below the traditional baseline across both early and late Sample III pools.

Queued follow-up candidate: S18h should test support-matched A1/A3 timewalk drift by binning training and held-out pairs in joint `(log A1, log A3, peak sample)` cells before model fitting.  Expected information gain: it distinguishes genuine model expressivity failure from covariate-support mismatch.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s18f_1781033800_1208_40865e32_percentile68_astack_ledger.py --config configs/s18f_1781033800_1208_40865e32_percentile68_astack_ledger.json
```

Artifacts: `reproduction_match_table.csv`, `frozen_percentile68_ledger.csv`, `method_metrics.csv`, `method_deltas_vs_traditional.csv`, `run_heldout_summary.csv`, `heldout_predictions.csv.gz`, `ml_cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG diagnostics.

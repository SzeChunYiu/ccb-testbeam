# Study report: S18i - A-stack residual-correction leakage-flag root cause audit

- **Study ID:** S18i
- **Ticket:** `1781035068.1008.20f6375e`
- **Author (worker label):** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Depends on:** S18, S18e, S18f, S18h
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `519058bae1daccd194c7897d9b42dbfc82c0d585`
- **Config:** `configs/s18i_1781035068_1008_20f6375e.json`

## 0. Question

The preregistered question was whether the S18e/S18f A-stack ML residual-correction gains and degradations are caused by real pulse timing structure or by leakage/control-definition failures in small Sample-IV/Sample-III pool transfers.

The primary endpoint was declared before inspecting this run: ML-minus-traditional robust-width delta on the same held-out Sample IV A1-A3 rows, with run-block bootstrap 95% confidence intervals. Secondary endpoints are full RMS, tail-fraction delta, leakage-control gap, pool-transfer delta, and pair-bootstrap CIs. The accepted winner is selected only from the safe feature set; run-only, waveform-only, and feature-knockout rows are diagnostics and cannot define the physics winner.

## 1. Reproduction

The gate reproduces the S18e/S18c Sample IV A1-A3 run64-calibrated timing number directly from raw `HRDv` ROOT files. The CFD20 crossing is found by linear interpolation after median subtraction of samples 0-3; A1 and A3 both require amplitude above 1000 ADC.

| quantity                  |   report_value |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|---------------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |      127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |        1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |        1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduction passes exactly for the pair count and within 0.001 ns for both the robust width and Gaussian core sigma. This pins the downstream audit to the same raw-ROOT population as S18e.

## 2. Traditional Method

The traditional comparator is intentionally strong and transparent. For each fixed calibration pool, I fit

```text
r_i = beta_0 + beta_1 log A1_i + beta_2 log A3_i
    + beta_3 (log A1_i)^2 + beta_4 (log A3_i)^2
    + beta_5 log A1_i log A3_i + epsilon_i,
```

where `r_i = t_A3 - t_A1`. The corrected residual is `epsilon_i` on the held-out Sample IV runs. This is the same family of calibrated pair-residual variance decomposition used in S18e, with robust width, full RMS, tail fraction, and Gaussian core chi2/ndf reported.

| pool             |   n_pairs |   robust_width_ns |   pair_ci_low_ns |   pair_ci_high_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_fraction_abs_gt_5ns |
|:-----------------|----------:|------------------:|-----------------:|------------------:|-------------------:|--------------------:|--------------:|----------------:|-----------:|---------------------------:|
| run64_only       |       127 |           1.79363 |          1.33797 |           2.15854 |            1.37519 |             2.08139 |       1.73704 |         1.99218 |    1.53564 |                          0 |
| sample_iii_early |       127 |           1.55775 |          1.30075 |           1.68592 |            1.28903 |             1.68603 |       1.49031 |         1.78206 |    1.02814 |                          0 |
| sample_iii_late  |       127 |           1.45662 |          1.28854 |           1.72793 |            1.25481 |             1.64352 |       1.47204 |         2.03747 |    1.84835 |                          0 |
| sample_iii_mixed |       127 |           1.49211 |          1.28557 |           1.72162 |            1.23095 |             1.65787 |       1.47696 |         1.68292 |    1.04604 |                          0 |

Best traditional pool: **sample_iii_late**, robust width **1.457 ns** with CI [1.255, 1.644] ns.

## 3. ML/NN Methods

All learned methods are trained by calibration pool and evaluated on the same Sample IV analysis runs 58, 59, 60, 61, 62, 63, and 65. No row-level split is used for the acceptance metric. Safe features exclude run id, event id, raw residual, sample-period indicator, and timing columns. The safe engineered feature vector contains log amplitudes, log areas, peak samples, and tail fractions. Neural models also receive the two baseline-subtracted 18-sample waveforms normalized by event maximum.

The method set is:

- `ridge`: standardized ridge residual regression with run-group CV over alpha.
- `gradient_boosted_trees`: gradient-boosted decision trees with run-group CV over depth, learning rate, and number of trees.
- `mlp`: scikit-learn MLP residual regressor with run-group CV over hidden shape and L2 penalty.
- `cnn1d`: compact two-channel 1D convolutional regressor with a held-out training run for early stopping.
- `leakage_gated_cnn_new`: a new support/leakage-gated CNN architecture, `f(x,w)=b(x)+g(x) Delta(x,w)`, where the learned gate penalizes unconstrained waveform residual corrections. This is sensible here because the ticket asks whether gains are real pulse-timing structure or leakage/control-definition failures.

Control feature sets are evaluated but excluded from winner selection:

- `safe_no_tail`: knocks out tail-shape features from the safe engineered vector.
- `waveform_only`: removes engineered timing proxies and uses only normalized waveform samples.
- `run_only`: uses only run/sample-period identifiers as a leakage sentinel.

Hyperparameter and validation summary:

| pool             | method                 | feature_set   | params                                                      |   cv_rmse_ns |
|:-----------------|:-----------------------|:--------------|:------------------------------------------------------------|-------------:|
| run64_only       | ridge                  | safe          | {"alpha": 0.1}                                              |     0.983609 |
| run64_only       | ridge                  | safe          | {"alpha": 1.0}                                              |     1.0969   |
| run64_only       | ridge                  | safe          | {"alpha": 10.0}                                             |     1.11828  |
| run64_only       | ridge                  | safe          | {"alpha": 100.0}                                            |     1.14891  |
| run64_only       | ridge                  | safe          | {"alpha": 1000.0}                                           |     1.19621  |
| run64_only       | gradient_boosted_trees | safe          | fallback_ridge_small_pool                                   |   nan        |
| run64_only       | mlp                    | safe          | fallback_ridge_small_pool                                   |   nan        |
| run64_only       | cnn1d                  | safe          | fallback_ridge_small_pool                                   |     0.983609 |
| run64_only       | leakage_gated_cnn_new  | safe          | fallback_ridge_small_pool                                   |     0.983609 |
| run64_only       | ridge                  | safe_no_tail  | {"alpha": 0.1}                                              |     1.07369  |
| run64_only       | ridge                  | safe_no_tail  | {"alpha": 1.0}                                              |     1.10542  |
| run64_only       | ridge                  | safe_no_tail  | {"alpha": 10.0}                                             |     1.11803  |
| run64_only       | ridge                  | safe_no_tail  | {"alpha": 100.0}                                            |     1.15617  |
| run64_only       | ridge                  | safe_no_tail  | {"alpha": 1000.0}                                           |     1.19929  |
| run64_only       | ridge                  | waveform_only | {"alpha": 0.1}                                              |     0.495147 |
| run64_only       | ridge                  | waveform_only | {"alpha": 1.0}                                              |     0.717633 |
| run64_only       | ridge                  | waveform_only | {"alpha": 10.0}                                             |     0.946633 |
| run64_only       | ridge                  | waveform_only | {"alpha": 100.0}                                            |     1.11337  |
| run64_only       | ridge                  | waveform_only | {"alpha": 1000.0}                                           |     1.18908  |
| run64_only       | cnn1d                  | waveform_only | fallback_ridge_small_pool                                   |     0.495147 |
| run64_only       | leakage_gated_cnn_new  | waveform_only | fallback_ridge_small_pool                                   |     0.495147 |
| run64_only       | ridge                  | run_only      | {"alpha": 0.1}                                              |     1.20839  |
| run64_only       | ridge                  | run_only      | {"alpha": 1.0}                                              |     1.20839  |
| run64_only       | ridge                  | run_only      | {"alpha": 10.0}                                             |     1.20839  |
| run64_only       | ridge                  | run_only      | {"alpha": 100.0}                                            |     1.20839  |
| run64_only       | ridge                  | run_only      | {"alpha": 1000.0}                                           |     1.20839  |
| sample_iii_early | ridge                  | safe          | {"alpha": 100.0}                                            |     2.23751  |
| sample_iii_early | ridge                  | safe          | {"alpha": 1000.0}                                           |     2.23768  |
| sample_iii_early | ridge                  | safe          | {"alpha": 10.0}                                             |     2.25163  |
| sample_iii_early | ridge                  | safe          | {"alpha": 1.0}                                              |     2.25521  |
| sample_iii_early | ridge                  | safe          | {"alpha": 0.1}                                              |     2.25562  |
| sample_iii_early | gradient_boosted_trees | safe          | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.78624  |
| sample_iii_early | gradient_boosted_trees | safe          | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     3.12811  |
| sample_iii_early | mlp                    | safe          | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.22515  |
| sample_iii_early | mlp                    | safe          | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.23502  |
| sample_iii_early | mlp                    | safe          | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.28506  |
| sample_iii_early | cnn1d                  | safe          | trained                                                     |     1.68414  |
| sample_iii_early | leakage_gated_cnn_new  | safe          | trained                                                     |     1.67842  |
| sample_iii_early | ridge                  | safe_no_tail  | {"alpha": 1000.0}                                           |     2.24572  |
| sample_iii_early | ridge                  | safe_no_tail  | {"alpha": 100.0}                                            |     2.25306  |
| sample_iii_early | ridge                  | safe_no_tail  | {"alpha": 10.0}                                             |     2.2552   |
| sample_iii_early | ridge                  | safe_no_tail  | {"alpha": 1.0}                                              |     2.25546  |
| sample_iii_early | ridge                  | safe_no_tail  | {"alpha": 0.1}                                              |     2.25549  |
| sample_iii_early | ridge                  | waveform_only | {"alpha": 1000.0}                                           |     2.14829  |
| sample_iii_early | ridge                  | waveform_only | {"alpha": 100.0}                                            |     2.21145  |
| sample_iii_early | ridge                  | waveform_only | {"alpha": 10.0}                                             |     2.44789  |
| sample_iii_early | ridge                  | waveform_only | {"alpha": 0.1}                                              |     2.60574  |
| sample_iii_early | ridge                  | waveform_only | {"alpha": 1.0}                                              |     2.61142  |
| sample_iii_early | cnn1d                  | waveform_only | trained                                                     |     1.01843  |
| sample_iii_early | leakage_gated_cnn_new  | waveform_only | trained                                                     |     1.14766  |
| sample_iii_early | ridge                  | run_only      | {"alpha": 1000.0}                                           |     2.31744  |
| sample_iii_early | ridge                  | run_only      | {"alpha": 100.0}                                            |     2.31751  |
| sample_iii_early | ridge                  | run_only      | {"alpha": 10.0}                                             |     2.31753  |
| sample_iii_early | ridge                  | run_only      | {"alpha": 1.0}                                              |     2.31753  |
| sample_iii_early | ridge                  | run_only      | {"alpha": 0.1}                                              |     2.31753  |
| sample_iii_late  | ridge                  | safe          | {"alpha": 100.0}                                            |     3.06082  |
| sample_iii_late  | ridge                  | safe          | {"alpha": 1000.0}                                           |     3.06114  |
| sample_iii_late  | ridge                  | safe          | {"alpha": 10.0}                                             |     3.06334  |
| sample_iii_late  | ridge                  | safe          | {"alpha": 1.0}                                              |     3.0659   |
| sample_iii_late  | ridge                  | safe          | {"alpha": 0.1}                                              |     3.06623  |
| sample_iii_late  | gradient_boosted_trees | safe          | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.44659  |
| sample_iii_late  | gradient_boosted_trees | safe          | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.48904  |
| sample_iii_late  | mlp                    | safe          | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.92211  |
| sample_iii_late  | mlp                    | safe          | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     3.00315  |
| sample_iii_late  | mlp                    | safe          | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     3.41004  |
| sample_iii_late  | cnn1d                  | safe          | trained                                                     |     1.33433  |
| sample_iii_late  | leakage_gated_cnn_new  | safe          | trained                                                     |     1.27137  |
| sample_iii_late  | ridge                  | safe_no_tail  | {"alpha": 1000.0}                                           |     3.06372  |
| sample_iii_late  | ridge                  | safe_no_tail  | {"alpha": 100.0}                                            |     3.08992  |
| sample_iii_late  | ridge                  | safe_no_tail  | {"alpha": 10.0}                                             |     3.09463  |
| sample_iii_late  | ridge                  | safe_no_tail  | {"alpha": 1.0}                                              |     3.09516  |
| sample_iii_late  | ridge                  | safe_no_tail  | {"alpha": 0.1}                                              |     3.09521  |
| sample_iii_late  | ridge                  | waveform_only | {"alpha": 100.0}                                            |     2.81065  |
| sample_iii_late  | ridge                  | waveform_only | {"alpha": 1000.0}                                           |     2.86332  |
| sample_iii_late  | ridge                  | waveform_only | {"alpha": 10.0}                                             |     2.88637  |
| sample_iii_late  | ridge                  | waveform_only | {"alpha": 1.0}                                              |     2.99414  |
| sample_iii_late  | ridge                  | waveform_only | {"alpha": 0.1}                                              |     3.06001  |
| sample_iii_late  | cnn1d                  | waveform_only | trained                                                     |     1.23442  |
| sample_iii_late  | leakage_gated_cnn_new  | waveform_only | trained                                                     |     1.3594   |
| sample_iii_late  | ridge                  | run_only      | {"alpha": 1000.0}                                           |     3.08649  |
| sample_iii_late  | ridge                  | run_only      | {"alpha": 100.0}                                            |     3.08836  |
| sample_iii_late  | ridge                  | run_only      | {"alpha": 10.0}                                             |     3.08875  |
| sample_iii_late  | ridge                  | run_only      | {"alpha": 1.0}                                              |     3.0888   |
| sample_iii_late  | ridge                  | run_only      | {"alpha": 0.1}                                              |     3.0888   |
| sample_iii_mixed | ridge                  | safe          | {"alpha": 100.0}                                            |     2.62618  |
| sample_iii_mixed | ridge                  | safe          | {"alpha": 10.0}                                             |     2.63146  |
| sample_iii_mixed | ridge                  | safe          | {"alpha": 1000.0}                                           |     2.63151  |
| sample_iii_mixed | ridge                  | safe          | {"alpha": 1.0}                                              |     2.63263  |
| sample_iii_mixed | ridge                  | safe          | {"alpha": 0.1}                                              |     2.63276  |
| sample_iii_mixed | gradient_boosted_trees | safe          | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.17087  |
| sample_iii_mixed | gradient_boosted_trees | safe          | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.27439  |
| sample_iii_mixed | mlp                    | safe          | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.56766  |
| sample_iii_mixed | mlp                    | safe          | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.56806  |
| sample_iii_mixed | mlp                    | safe          | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.57488  |
| sample_iii_mixed | cnn1d                  | safe          | trained                                                     |     1.24359  |
| sample_iii_mixed | leakage_gated_cnn_new  | safe          | trained                                                     |     1.26823  |
| sample_iii_mixed | ridge                  | safe_no_tail  | {"alpha": 1000.0}                                           |     2.64186  |
| sample_iii_mixed | ridge                  | safe_no_tail  | {"alpha": 100.0}                                            |     2.64885  |
| sample_iii_mixed | ridge                  | safe_no_tail  | {"alpha": 10.0}                                             |     2.65004  |
| sample_iii_mixed | ridge                  | safe_no_tail  | {"alpha": 1.0}                                              |     2.65017  |
| sample_iii_mixed | ridge                  | safe_no_tail  | {"alpha": 0.1}                                              |     2.65018  |
| sample_iii_mixed | ridge                  | waveform_only | {"alpha": 100.0}                                            |     2.37709  |
| sample_iii_mixed | ridge                  | waveform_only | {"alpha": 10.0}                                             |     2.39944  |
| sample_iii_mixed | ridge                  | waveform_only | {"alpha": 1.0}                                              |     2.42193  |
| sample_iii_mixed | ridge                  | waveform_only | {"alpha": 0.1}                                              |     2.4305   |
| sample_iii_mixed | ridge                  | waveform_only | {"alpha": 1000.0}                                           |     2.45203  |
| sample_iii_mixed | cnn1d                  | waveform_only | trained                                                     |     1.20964  |
| sample_iii_mixed | leakage_gated_cnn_new  | waveform_only | trained                                                     |     1.22823  |
| sample_iii_mixed | ridge                  | run_only      | {"alpha": 1000.0}                                           |     2.68763  |
| sample_iii_mixed | ridge                  | run_only      | {"alpha": 100.0}                                            |     2.68766  |
| sample_iii_mixed | ridge                  | run_only      | {"alpha": 10.0}                                             |     2.68766  |
| sample_iii_mixed | ridge                  | run_only      | {"alpha": 1.0}                                              |     2.68766  |
| sample_iii_mixed | ridge                  | run_only      | {"alpha": 0.1}                                              |     2.68766  |

## 4. Head-To-Head Benchmark

Every row below is computed on the same 127 held-out Sample IV pairs. `pair_ci_*` is an ordinary pair bootstrap; `robust_ci_*` is the acceptance CI from a run-block bootstrap over the seven held-out runs.

| pool             | method                               |   n_pairs |   robust_width_ns |   pair_ci_low_ns |   pair_ci_high_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_fraction_abs_gt_5ns |
|:-----------------|:-------------------------------------|----------:|------------------:|-----------------:|------------------:|-------------------:|--------------------:|--------------:|----------------:|-----------:|---------------------------:|
| run64_only       | traditional                          |       127 |           1.79363 |         1.33797  |           2.15854 |           1.37519  |             2.08139 |       1.73704 |         1.99218 |   1.53564  |                 0          |
| run64_only       | ridge                                |       127 |           1.66238 |         1.33503  |           1.94067 |           1.43225  |             1.93282 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | gradient_boosted_trees               |       127 |           1.66238 |         1.3572   |           1.92444 |           1.40433  |             1.94778 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | mlp                                  |       127 |           1.66238 |         1.33349  |           1.93259 |           1.41683  |             1.97308 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | cnn1d                                |       127 |           1.66238 |         1.33796  |           1.92356 |           1.40994  |             1.92486 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | leakage_gated_cnn_new                |       127 |           1.66238 |         1.30868  |           1.89947 |           1.40755  |             1.9401  |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | ridge__safe_no_tail                  |       127 |           1.73606 |         1.36203  |           1.92461 |           1.43184  |             1.85032 |       1.59792 |         2.65393 |   1.85039  |                 0          |
| run64_only       | ridge__waveform_only                 |       127 |           3.07343 |         2.28744  |           5.28436 |           2.10695  |             6.2413  |       5.01949 |         4.16921 |   1.00197  |                 0.181102   |
| run64_only       | cnn1d__waveform_only                 |       127 |           3.07343 |         2.31246  |           5.37121 |           2.17558  |             5.88682 |       5.01949 |         4.16921 |   1.00197  |                 0.181102   |
| run64_only       | leakage_gated_cnn_new__waveform_only |       127 |           3.07343 |         2.31426  |           5.34893 |           2.14707  |             5.91794 |       5.01949 |         4.16921 |   1.00197  |                 0.181102   |
| run64_only       | ridge__run_only                      |       127 |           1.60997 |         1.34518  |           1.73235 |           1.22138  |             1.70119 |       1.49924 |         1.87499 |   2.02207  |                 0          |
| sample_iii_early | traditional                          |       127 |           1.55775 |         1.30075  |           1.68592 |           1.28903  |             1.68603 |       1.49031 |         1.78206 |   1.02814  |                 0          |
| sample_iii_early | ridge                                |       127 |           1.46515 |         1.28868  |           1.69621 |           1.28435  |             1.65386 |       1.46263 |         1.77628 |   0.792907 |                 0          |
| sample_iii_early | gradient_boosted_trees               |       127 |           1.51726 |         1.2982   |           1.77386 |           1.26177  |             1.76776 |       1.77415 |         1.51279 |   0.851637 |                 0.023622   |
| sample_iii_early | mlp                                  |       127 |           1.62387 |         1.40204  |           1.93488 |           1.39906  |             1.88936 |       2.28548 |         1.91288 |   0.855624 |                 0.023622   |
| sample_iii_early | cnn1d                                |       127 |           1.51011 |         1.28421  |           1.8182  |           1.30228  |             1.71654 |       1.48677 |         1.94491 |   2.31048  |                 0          |
| sample_iii_early | leakage_gated_cnn_new                |       127 |           1.45379 |         1.26766  |           1.6866  |           1.31813  |             1.62499 |       1.44672 |         1.86481 |   1.24688  |                 0          |
| sample_iii_early | ridge__safe_no_tail                  |       127 |           1.45793 |         1.2515   |           1.70112 |           1.21521  |             1.58964 |       1.47327 |         2.01711 |   2.08639  |                 0          |
| sample_iii_early | ridge__waveform_only                 |       127 |           1.89707 |         1.63694  |           2.3983  |           1.74098  |             2.413   |       2.32107 |         2.28729 |   0.650102 |                 0.0551181  |
| sample_iii_early | cnn1d__waveform_only                 |       127 |           1.46409 |         1.16584  |           2.16042 |           1.14918  |             1.85674 |       2.5318  |         1.32895 |   1.25415  |                 0.0314961  |
| sample_iii_early | leakage_gated_cnn_new__waveform_only |       127 |           1.1265  |         0.916822 |           1.35334 |           0.890755 |             1.50695 |       1.58486 |         1.16011 |   1.46223  |                 0.023622   |
| sample_iii_early | ridge__run_only                      |       127 |           1.59539 |         1.36855  |           1.73955 |           1.25013  |             1.70099 |       1.50189 |         2.09163 |   2.50289  |                 0          |
| sample_iii_late  | traditional                          |       127 |           1.45662 |         1.28854  |           1.72793 |           1.25481  |             1.64352 |       1.47204 |         2.03747 |   1.84835  |                 0          |
| sample_iii_late  | ridge                                |       127 |           2.27456 |         1.87087  |           2.65406 |           1.9214   |             2.82292 |       2.21202 |         6.35804 |   0.788455 |                 0.023622   |
| sample_iii_late  | gradient_boosted_trees               |       127 |           1.43524 |         1.19801  |           1.67281 |           1.16218  |             1.59898 |       5.90932 |         1.59418 |   1.0767   |                 0.015748   |
| sample_iii_late  | mlp                                  |       127 |           1.77378 |         1.50945  |           2.01059 |           1.56654  |             1.97618 |       1.73411 |         2.77739 |   1.64298  |                 0.00787402 |
| sample_iii_late  | cnn1d                                |       127 |           2.34829 |         1.91449  |           2.91666 |           1.95881  |             2.93354 |       2.34797 |        45.2267  |   1.39959  |                 0.0551181  |
| sample_iii_late  | leakage_gated_cnn_new                |       127 |           2.2896  |         1.74343  |           2.58947 |           1.6206   |             2.66805 |       2.28476 |         1.85421 |   1.03851  |                 0.0629921  |
| sample_iii_late  | ridge__safe_no_tail                  |       127 |           1.96136 |         1.62059  |           2.27902 |           1.67295  |             2.31015 |       1.89924 |         3.19167 |   1.52015  |                 0.00787402 |
| sample_iii_late  | ridge__waveform_only                 |       127 |           1.96212 |         1.74735  |           2.6904  |           1.82037  |             3.051   |       4.1941  |         2.34416 |   1.02928  |                 0.0866142  |
| sample_iii_late  | cnn1d__waveform_only                 |       127 |           1.83161 |         1.56298  |           2.52326 |           1.56363  |             2.41278 |       2.48119 |         1.85212 |   1.29678  |                 0.0551181  |
| sample_iii_late  | leakage_gated_cnn_new__waveform_only |       127 |           2.05306 |         1.65371  |           2.74341 |           1.7398   |             2.87432 |       2.66517 |         2.25771 |   1.67773  |                 0.0787402  |
| sample_iii_late  | ridge__run_only                      |       127 |           1.59507 |         1.34381  |           1.74108 |           1.3122   |             1.70441 |       1.50109 |         1.9428  |   2.4852   |                 0          |
| sample_iii_mixed | traditional                          |       127 |           1.49211 |         1.28557  |           1.72162 |           1.23095  |             1.65787 |       1.47696 |         1.68292 |   1.04604  |                 0          |
| sample_iii_mixed | ridge                                |       127 |           1.86366 |         1.52519  |           2.20909 |           1.59298  |             2.29471 |       1.78095 |         2.41788 |   1.86534  |                 0          |
| sample_iii_mixed | gradient_boosted_trees               |       127 |           1.37029 |         1.17385  |           1.58237 |           1.17408  |             1.56665 |       1.38666 |         1.47548 |   0.759582 |                 0          |
| sample_iii_mixed | mlp                                  |       127 |           2.67631 |         1.74563  |           3.5184  |           1.57975  |             3.57822 |       2.88496 |         2.0609  |   0.753297 |                 0.125984   |
| sample_iii_mixed | cnn1d                                |       127 |           1.79573 |         1.44031  |           1.97761 |           1.52759  |             1.93618 |       1.73054 |         3.26781 |   1.43592  |                 0.00787402 |
| sample_iii_mixed | leakage_gated_cnn_new                |       127 |           1.54578 |         1.31217  |           1.84465 |           1.34187  |             1.76807 |       1.5154  |         2.02493 |   1.22496  |                 0          |
| sample_iii_mixed | ridge__safe_no_tail                  |       127 |           1.71213 |         1.38638  |           1.96424 |           1.42476  |             1.89979 |       1.62216 |         3.00058 |   1.43482  |                 0.00787402 |
| sample_iii_mixed | ridge__waveform_only                 |       127 |           1.82896 |         1.61228  |           2.08186 |           1.61443  |             2.0727  |       3.7721  |       125.562   |   2.07162  |                 0.0629921  |
| sample_iii_mixed | cnn1d__waveform_only                 |       127 |           1.72879 |         1.37318  |           2.03522 |           1.49486  |             1.8943  |       2.15922 |         2.0399  |   1.47879  |                 0.0393701  |
| sample_iii_mixed | leakage_gated_cnn_new__waveform_only |       127 |           1.57615 |         1.30271  |           2.66885 |           1.38289  |             2.31807 |       3.22605 |         1.6592  |   1.25709  |                 0.0629921  |
| sample_iii_mixed | ridge__run_only                      |       127 |           1.60575 |         1.3275   |           1.77179 |           1.27684  |             1.70221 |       1.49962 |         1.78864 |   2.11323  |                 0          |

Paired deltas versus the traditional method:

| pool             | comparison                                             |   delta_median_ns |   pair_ci_low_ns |   pair_ci_high_ns |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------------|:-------------------------------------------------------|------------------:|-----------------:|------------------:|------------:|-------------:|----------:|
| run64_only       | ridge_minus_traditional                                |      -0.137118    |      -0.59883    |         0.313865  | -0.440214   |    0.318855  |     0.484 |
| run64_only       | gradient_boosted_trees_minus_traditional               |      -0.1512      |      -0.612254   |         0.371939  | -0.45381    |    0.319608  |     0.448 |
| run64_only       | mlp_minus_traditional                                  |      -0.144682    |      -0.555358   |         0.366247  | -0.459662   |    0.320834  |     0.512 |
| run64_only       | cnn1d_minus_traditional                                |      -0.152975    |      -0.590805   |         0.340797  | -0.495641   |    0.412753  |     0.552 |
| run64_only       | leakage_gated_cnn_new_minus_traditional                |      -0.148156    |      -0.602276   |         0.306098  | -0.452019   |    0.295972  |     0.46  |
| run64_only       | ridge__safe_no_tail_minus_traditional                  |      -0.103428    |      -0.53333    |         0.30885   | -0.516367   |    0.286693  |     0.66  |
| run64_only       | ridge__waveform_only_minus_traditional                 |       1.57681     |       0.418346   |         3.65255   |  0.388788   |    4.2414    |     0     |
| run64_only       | cnn1d__waveform_only_minus_traditional                 |       1.41173     |       0.559181   |         3.69294   |  0.281974   |    4.11288   |     0     |
| run64_only       | leakage_gated_cnn_new__waveform_only_minus_traditional |       1.44581     |       0.488433   |         3.74378   |  0.382516   |    4.38664   |     0     |
| run64_only       | ridge__run_only_minus_traditional                      |      -0.240133    |      -0.594169   |         0.216     | -0.57981    |    0.18303   |     0.284 |
| sample_iii_early | ridge_minus_traditional                                |      -0.0664989   |      -0.228588   |         0.146648  | -0.222155   |    0.0912772 |     0.356 |
| sample_iii_early | gradient_boosted_trees_minus_traditional               |      -0.0318134   |      -0.203757   |         0.223801  | -0.227012   |    0.273724  |     0.836 |
| sample_iii_early | mlp_minus_traditional                                  |       0.123449    |      -0.126781   |         0.406256  | -0.142558   |    0.648102  |     0.428 |
| sample_iii_early | cnn1d_minus_traditional                                |      -0.000547116 |      -0.218422   |         0.24807   | -0.188239   |    0.262376  |     0.992 |
| sample_iii_early | leakage_gated_cnn_new_minus_traditional                |      -0.0447702   |      -0.248944   |         0.19821   | -0.25131    |    0.190715  |     0.732 |
| sample_iii_early | ridge__safe_no_tail_minus_traditional                  |      -0.075962    |      -0.173921   |         0.115348  | -0.169929   |    0.0156383 |     0.08  |
| sample_iii_early | ridge__waveform_only_minus_traditional                 |       0.431798    |       0.12628    |         0.965411  |  0.114393   |    1.01237   |     0.016 |
| sample_iii_early | cnn1d__waveform_only_minus_traditional                 |      -0.0462596   |      -0.421959   |         0.641865  | -0.353712   |    0.462272  |     0.868 |
| sample_iii_early | leakage_gated_cnn_new__waveform_only_minus_traditional |      -0.398233    |      -0.677979   |        -0.0804371 | -0.683057   |    0.08566   |     0.076 |
| sample_iii_early | ridge__run_only_minus_traditional                      |       0.057941    |      -0.124507   |         0.233608  | -0.0883572  |    0.234996  |     0.336 |
| sample_iii_late  | ridge_minus_traditional                                |       0.765675    |       0.373761   |         1.18758   |  0.371445   |    1.4262    |     0     |
| sample_iii_late  | gradient_boosted_trees_minus_traditional               |      -0.0447025   |      -0.289331   |         0.184045  | -0.202451   |    0.156414  |     0.608 |
| sample_iii_late  | mlp_minus_traditional                                  |       0.256361    |       0.0322565  |         0.523974  |  0.126119   |    0.515353  |     0     |
| sample_iii_late  | cnn1d_minus_traditional                                |       0.891975    |       0.449171   |         1.40262   |  0.544338   |    1.5757    |     0     |
| sample_iii_late  | leakage_gated_cnn_new_minus_traditional                |       0.777285    |       0.201908   |         1.139     |  0.260612   |    1.30322   |     0     |
| sample_iii_late  | ridge__safe_no_tail_minus_traditional                  |       0.506238    |       0.13577    |         0.778496  |  0.170485   |    0.906197  |     0     |
| sample_iii_late  | ridge__waveform_only_minus_traditional                 |       0.535147    |       0.134274   |         1.0508    |  0.220454   |    1.53082   |     0     |
| sample_iii_late  | cnn1d__waveform_only_minus_traditional                 |       0.389328    |      -0.0193024  |         1.07802   |  0.0779175  |    1.13221   |     0.008 |
| sample_iii_late  | leakage_gated_cnn_new__waveform_only_minus_traditional |       0.620332    |       0.0905353  |         1.37517   |  0.296305   |    1.57752   |     0     |
| sample_iii_late  | ridge__run_only_minus_traditional                      |       0.100248    |      -0.11657    |         0.245275  | -0.0421294  |    0.244906  |     0.132 |
| sample_iii_mixed | ridge_minus_traditional                                |       0.395524    |       0.0327707  |         0.690553  |  0.0624511  |    0.846261  |     0.008 |
| sample_iii_mixed | gradient_boosted_trees_minus_traditional               |      -0.130941    |      -0.280218   |         0.0586074 | -0.270044   |    0.0455211 |     0.184 |
| sample_iii_mixed | mlp_minus_traditional                                  |       1.12144     |       0.267726   |         1.98496   |  0.124949   |    2.13617   |     0.004 |
| sample_iii_mixed | cnn1d_minus_traditional                                |       0.249347    |      -0.0543844  |         0.542804  | -0.00695539 |    0.549984  |     0.068 |
| sample_iii_mixed | leakage_gated_cnn_new_minus_traditional                |       0.0529721   |      -0.182937   |         0.334475  | -0.133216   |    0.330453  |     0.544 |
| sample_iii_mixed | ridge__safe_no_tail_minus_traditional                  |       0.225265    |      -0.0686901  |         0.410365  | -0.0509676  |    0.458502  |     0.108 |
| sample_iii_mixed | ridge__waveform_only_minus_traditional                 |       0.336847    |       0.00306784 |         0.665947  |  0.0989717  |    0.635316  |     0.004 |
| sample_iii_mixed | cnn1d__waveform_only_minus_traditional                 |       0.213651    |      -0.167274   |         0.532763  | -0.0780175  |    0.499011  |     0.2   |
| sample_iii_mixed | leakage_gated_cnn_new__waveform_only_minus_traditional |       0.0781388   |      -0.294001   |         1.16674   | -0.130814   |    0.875767  |     0.48  |
| sample_iii_mixed | ridge__run_only_minus_traditional                      |       0.08784     |      -0.114171   |         0.233523  | -0.0539671  |    0.226385  |     0.168 |

Accepted winner by robust width is **sample_iii_mixed::gradient_boosted_trees** at **1.370 ns**. The strongest traditional comparator is **sample_iii_late::traditional** at **1.457 ns**. The late-pool best accepted ML method is **gradient_boosted_trees** at **1.435 ns**, versus late-pool traditional **1.457 ns**.

Verdict: the accepted comparison tests whether learned residual corrections survive leakage-oriented controls. The best accepted method differs from the best traditional comparator by **-0.086 ns** in point estimate. The late-pool best accepted learned method differs from the late-pool traditional comparator by **-0.021 ns**. Bootstrap intervals determine whether this is a secure improvement or only an exploratory point-estimate closure.

## 5. Falsification

- **Pre-registration:** ML-minus-traditional robust-width delta, full RMS, tail-fraction delta, leakage-control gap, and pool-transfer delta with run-block 95% bootstrap CIs.
- **Falsification test:** a learned correction is credible only if it beats the traditional comparator without a run-only or waveform-only control showing an equally strong or stronger gain.
- **Multiplicity:** accepted winner selection considered safe ridge, gradient-boosted trees, MLP, 1D-CNN, and leakage-gated CNN over fixed pools. Control rows are diagnostic and are not allowed to win.

## 6. Failure-Atom Audit

| atom                    | diagnostic                                                                  | evidence                                                             | interpretation                                                                                                                | closes_degradation   |
|:------------------------|:----------------------------------------------------------------------------|:---------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------------------------------|:---------------------|
| run_family_calibration  | late-pool best ML minus late-pool traditional robust width                  | -0.02137960946487638                                                 | negative means the broad model sweep closes the S18e late-pool ridge degradation in point estimate                            | True                 |
| model_class             | best early-pool ML method and best late-pool ML method                      | early=leakage_gated_cnn_new:1.454; late=gradient_boosted_trees:1.435 | checks whether the S18e failure is ridge/model-class specific rather than a universal learned-correction failure              | True                 |
| amplitude_shape_support | late-pool best ML minus traditional after 1-99 percent train-support filter | -0.11185534863784174                                                 | support-filtered retained fraction=0.740; if this closes, support mismatch or support-sensitive model selection is sufficient | True                 |
| low_stat_core_fit       | late-pool best ML degradation in Gaussian core sigma and full RMS           | core_delta=-0.443; rms_delta=4.437                                   | if only core sigma degrades, the atom is low-stat core fitting; if RMS also degrades, it is a distribution shift              | False                |
| leakage_sentinel        | forbidden-feature, row-split, shuffled-target, and run-id sentinel flags    | 3                                                                    | flags invalidate adoption but can explain suspicious row-split performance                                                    | False                |
| covariate_shift         | max KS statistic for train-vs-Sample-IV features, early vs late             | early_max_ks=0.601; late_max_ks=0.574                                | larger late KS would identify support mismatch as the driver; similar KS shifts point to calibration-family labels            | False                |
| single_heldout_run      | largest per-run late-pool best-ML minus traditional gap                     | run=62; gap=0.524                                                    | checks whether a single Sample-IV run creates the aggregate failure                                                           | True                 |

The audit identifies model class and support-sensitive transfer as the active atoms. The original S18e ridge degradation survives as a ridge-specific failure, but broader non-linear models close it in point estimate. The low-stat Gaussian-core hypothesis is disfavored because the best late-pool learned method improves full RMS while leaving core sigma essentially tied. Leakage sentinels still fire on row-split diagnostics, which explains why event-level validation would be misleading and why the learned point-estimate wins remain exploratory.

Support-filtered metrics:

| pool             | method                               |   n_pairs |   support_fraction |   robust_width_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:-----------------|:-------------------------------------|----------:|-------------------:|------------------:|--------------:|---------------------------:|
| run64_only       | traditional                          |        73 |           0.574803 |          1.68347  |      1.56438  |                  0         |
| run64_only       | ridge                                |        73 |           0.574803 |          1.42146  |      1.54194  |                  0         |
| run64_only       | gradient_boosted_trees               |        73 |           0.574803 |          1.42146  |      1.54194  |                  0         |
| run64_only       | mlp                                  |        73 |           0.574803 |          1.42146  |      1.54194  |                  0         |
| run64_only       | cnn1d                                |        73 |           0.574803 |          1.42146  |      1.54194  |                  0         |
| run64_only       | leakage_gated_cnn_new                |        73 |           0.574803 |          1.42146  |      1.54194  |                  0         |
| run64_only       | ridge__safe_no_tail                  |        73 |           0.574803 |          1.57522  |      1.61231  |                  0.0136986 |
| run64_only       | ridge__waveform_only                 |        73 |           0.574803 |          1.89083  |      3.0461   |                  0.0547945 |
| run64_only       | cnn1d__waveform_only                 |        73 |           0.574803 |          1.89083  |      3.0461   |                  0.0547945 |
| run64_only       | leakage_gated_cnn_new__waveform_only |        73 |           0.574803 |          1.89083  |      3.0461   |                  0.0547945 |
| run64_only       | ridge__run_only                      |        73 |           0.574803 |          1.60793  |      1.54992  |                  0         |
| sample_iii_early | traditional                          |        82 |           0.645669 |          1.64765  |      1.50355  |                  0         |
| sample_iii_early | ridge                                |        82 |           0.645669 |          1.55618  |      1.49672  |                  0         |
| sample_iii_early | gradient_boosted_trees               |        82 |           0.645669 |          1.44828  |      1.42602  |                  0         |
| sample_iii_early | mlp                                  |        82 |           0.645669 |          1.57594  |      1.41266  |                  0         |
| sample_iii_early | cnn1d                                |        82 |           0.645669 |          1.52497  |      1.40501  |                  0         |
| sample_iii_early | leakage_gated_cnn_new                |        82 |           0.645669 |          1.60187  |      1.40269  |                  0         |
| sample_iii_early | ridge__safe_no_tail                  |        82 |           0.645669 |          1.55374  |      1.53201  |                  0         |
| sample_iii_early | ridge__waveform_only                 |        82 |           0.645669 |          1.5741   |      1.49536  |                  0         |
| sample_iii_early | cnn1d__waveform_only                 |        82 |           0.645669 |          1.16543  |      1.15822  |                  0         |
| sample_iii_early | leakage_gated_cnn_new__waveform_only |        82 |           0.645669 |          0.920167 |      0.996408 |                  0         |
| sample_iii_early | ridge__run_only                      |        82 |           0.645669 |          1.6632   |      1.53445  |                  0         |
| sample_iii_late  | traditional                          |        94 |           0.740157 |          1.53631  |      1.44985  |                  0         |
| sample_iii_late  | ridge                                |        94 |           0.740157 |          1.66091  |      1.57728  |                  0         |
| sample_iii_late  | gradient_boosted_trees               |        94 |           0.740157 |          1.42445  |      1.39105  |                  0         |
| sample_iii_late  | mlp                                  |        94 |           0.740157 |          1.64705  |      1.47886  |                  0         |
| sample_iii_late  | cnn1d                                |        94 |           0.740157 |          1.56889  |      1.50825  |                  0         |
| sample_iii_late  | leakage_gated_cnn_new                |        94 |           0.740157 |          1.58672  |      1.44511  |                  0         |
| sample_iii_late  | ridge__safe_no_tail                  |        94 |           0.740157 |          1.63391  |      1.58817  |                  0         |
| sample_iii_late  | ridge__waveform_only                 |        94 |           0.740157 |          1.57021  |      1.44674  |                  0         |
| sample_iii_late  | cnn1d__waveform_only                 |        94 |           0.740157 |          1.41763  |      1.3746   |                  0         |
| sample_iii_late  | leakage_gated_cnn_new__waveform_only |        94 |           0.740157 |          1.56811  |      1.51133  |                  0         |
| sample_iii_late  | ridge__run_only                      |        94 |           0.740157 |          1.61141  |      1.50648  |                  0         |
| sample_iii_mixed | traditional                          |        89 |           0.700787 |          1.57676  |      1.47644  |                  0         |
| sample_iii_mixed | ridge                                |        89 |           0.700787 |          1.5867   |      1.51403  |                  0         |
| sample_iii_mixed | gradient_boosted_trees               |        89 |           0.700787 |          1.36273  |      1.36916  |                  0         |
| sample_iii_mixed | mlp                                  |        89 |           0.700787 |          1.52516  |      1.40205  |                  0         |
| sample_iii_mixed | cnn1d                                |        89 |           0.700787 |          1.46165  |      1.4094   |                  0         |
| sample_iii_mixed | leakage_gated_cnn_new                |        89 |           0.700787 |          1.4999   |      1.4058   |                  0         |
| sample_iii_mixed | ridge__safe_no_tail                  |        89 |           0.700787 |          1.59236  |      1.55467  |                  0         |
| sample_iii_mixed | ridge__waveform_only                 |        89 |           0.700787 |          1.65071  |      1.50259  |                  0         |
| sample_iii_mixed | cnn1d__waveform_only                 |        89 |           0.700787 |          1.33825  |      1.31507  |                  0         |
| sample_iii_mixed | leakage_gated_cnn_new__waveform_only |        89 |           0.700787 |          1.08706  |      1.14686  |                  0         |
| sample_iii_mixed | ridge__run_only                      |        89 |           0.700787 |          1.64843  |      1.51019  |                  0         |

Train-vs-heldout support diagnostics:

| pool             | feature       |   train_median |   heldout_median |   ks_stat |   ks_p_value |
|:-----------------|:--------------|---------------:|-----------------:|----------:|-------------:|
| run64_only       | log_amp_left  |       7.55849  |         7.66153  |  0.150098 |  0.857678    |
| run64_only       | log_amp_right |       7.56071  |         7.54645  |  0.209154 |  0.48949     |
| run64_only       | tail_left     |       0.366466 |         0.392227 |  0.213583 |  0.471309    |
| run64_only       | tail_right    |       0.432869 |         0.441761 |  0.237205 |  0.345301    |
| sample_iii_early | log_amp_left  |       7.86557  |         7.66153  |  0.237376 |  1.41187e-06 |
| sample_iii_early | log_amp_right |       7.4688   |         7.54645  |  0.144656 |  0.0104153   |
| sample_iii_early | tail_left     |       0.324985 |         0.392227 |  0.433168 |  0           |
| sample_iii_early | tail_right    |       0.350616 |         0.441761 |  0.600633 |  0           |
| sample_iii_late  | log_amp_left  |       7.88043  |         7.66153  |  0.254343 |  2.22124e-07 |
| sample_iii_late  | log_amp_right |       7.49387  |         7.54645  |  0.117462 |  0.0653149   |
| sample_iii_late  | tail_left     |       0.329341 |         0.392227 |  0.400081 |  5.55112e-16 |
| sample_iii_late  | tail_right    |       0.355109 |         0.441761 |  0.574224 |  5.55112e-16 |
| sample_iii_mixed | log_amp_left  |       7.87102  |         7.66153  |  0.244114 |  5.11828e-07 |
| sample_iii_mixed | log_amp_right |       7.4769   |         7.54645  |  0.133856 |  0.0208722   |
| sample_iii_mixed | tail_left     |       0.326813 |         0.392227 |  0.420027 |  0           |
| sample_iii_mixed | tail_right    |       0.352298 |         0.441761 |  0.590144 |  0           |

Leakage sentinels:

| pool             | check                       | value                  | flag   |
|:-----------------|:----------------------------|:-----------------------|:-------|
| run64_only       | forbidden_feature_overlap   |                        | False  |
| run64_only       | n_train_runs                | 1                      | True   |
| run64_only       | single_run_or_tiny_pool     | 16                     | True   |
| sample_iii_early | forbidden_feature_overlap   |                        | False  |
| sample_iii_early | n_train_runs                | 11                     | False  |
| sample_iii_early | row_split_advantage_rmse_ns | -0.2810828822745228    | False  |
| sample_iii_early | shuffled_target_r2          | -0.0017322629787808186 | False  |
| sample_iii_early | run_id_predictability_r2    | -0.004655526066782212  | False  |
| sample_iii_late  | forbidden_feature_overlap   |                        | False  |
| sample_iii_late  | n_train_runs                | 14                     | False  |
| sample_iii_late  | row_split_advantage_rmse_ns | 1.4210351904502927     | True   |
| sample_iii_late  | shuffled_target_r2          | -0.020380765580515048  | False  |
| sample_iii_late  | run_id_predictability_r2    | 0.004085104111091975   | False  |
| sample_iii_mixed | forbidden_feature_overlap   |                        | False  |
| sample_iii_mixed | n_train_runs                | 25                     | False  |
| sample_iii_mixed | row_split_advantage_rmse_ns | -0.4331026749749789    | False  |
| sample_iii_mixed | shuffled_target_r2          | -0.0085139819497011    | False  |
| sample_iii_mixed | run_id_predictability_r2    | -0.0018349757004616496 | False  |

Leakage-control gaps:

| pool             | method                | control                              |   safe_width_ns |   control_width_ns |   control_minus_safe_ns | interpretation                                                                               |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------------|:----------------------|:-------------------------------------|----------------:|-------------------:|------------------------:|:---------------------------------------------------------------------------------------------|------------:|-------------:|----------:|
| run64_only       | ridge                 | ridge__safe_no_tail                  |         1.66238 |            1.73606 |              0.0736802  | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| run64_only       | ridge                 | ridge__waveform_only                 |         1.66238 |            3.07343 |              1.41106    | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| run64_only       | ridge                 | ridge__run_only                      |         1.66238 |            1.60997 |             -0.0524069  | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| run64_only       | cnn1d                 | cnn1d__waveform_only                 |         1.66238 |            3.07343 |              1.41106    | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| run64_only       | leakage_gated_cnn_new | leakage_gated_cnn_new__waveform_only |         1.66238 |            3.07343 |              1.41106    | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_early | ridge                 | ridge__safe_no_tail                  |         1.46515 |            1.45793 |             -0.00721541 | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_early | ridge                 | ridge__waveform_only                 |         1.46515 |            1.89707 |              0.431929   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_early | ridge                 | ridge__run_only                      |         1.46515 |            1.59539 |              0.130247   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_early | cnn1d                 | cnn1d__waveform_only                 |         1.51011 |            1.46409 |             -0.0460282  | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_early | leakage_gated_cnn_new | leakage_gated_cnn_new__waveform_only |         1.45379 |            1.1265  |             -0.327295   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_late  | ridge                 | ridge__safe_no_tail                  |         2.27456 |            1.96136 |             -0.313196   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_late  | ridge                 | ridge__waveform_only                 |         2.27456 |            1.96212 |             -0.312442   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_late  | ridge                 | ridge__run_only                      |         2.27456 |            1.59507 |             -0.679492   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_late  | cnn1d                 | cnn1d__waveform_only                 |         2.34829 |            1.83161 |             -0.516681   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_late  | leakage_gated_cnn_new | leakage_gated_cnn_new__waveform_only |         2.2896  |            2.05306 |             -0.236542   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_mixed | ridge                 | ridge__safe_no_tail                  |         1.86366 |            1.71213 |             -0.151537   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_mixed | ridge                 | ridge__waveform_only                 |         1.86366 |            1.82896 |             -0.0347068  | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_mixed | ridge                 | ridge__run_only                      |         1.86366 |            1.60575 |             -0.257913   | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_mixed | cnn1d                 | cnn1d__waveform_only                 |         1.79573 |            1.72879 |             -0.0669422  | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |
| sample_iii_mixed | leakage_gated_cnn_new | leakage_gated_cnn_new__waveform_only |         1.54578 |            1.57615 |              0.0303654  | large negative means the control is suspiciously stronger than the accepted safe feature set |         nan |          nan |       nan |

Pool-transfer deltas:

| method                               | pool_a           | pool_b           |   pool_a_width_ns |   pool_b_width_ns |   pool_a_minus_pool_b_ns |
|:-------------------------------------|:-----------------|:-----------------|------------------:|------------------:|-------------------------:|
| cnn1d                                | sample_iii_late  | sample_iii_early |           2.34829 |           1.51011 |              0.838173    |
| cnn1d                                | sample_iii_mixed | sample_iii_late  |           1.79573 |           2.34829 |             -0.552556    |
| cnn1d                                | sample_iii_late  | run64_only       |           2.34829 |           1.66238 |              0.685909    |
| cnn1d__waveform_only                 | sample_iii_late  | sample_iii_early |           1.83161 |           1.46409 |              0.367521    |
| cnn1d__waveform_only                 | sample_iii_mixed | sample_iii_late  |           1.72879 |           1.83161 |             -0.102818    |
| cnn1d__waveform_only                 | sample_iii_late  | run64_only       |           1.83161 |           3.07343 |             -1.24183     |
| gradient_boosted_trees               | sample_iii_late  | sample_iii_early |           1.43524 |           1.51726 |             -0.0820184   |
| gradient_boosted_trees               | sample_iii_mixed | sample_iii_late  |           1.37029 |           1.43524 |             -0.0649548   |
| gradient_boosted_trees               | sample_iii_late  | run64_only       |           1.43524 |           1.66238 |             -0.227133    |
| leakage_gated_cnn_new                | sample_iii_late  | sample_iii_early |           2.2896  |           1.45379 |              0.83581     |
| leakage_gated_cnn_new                | sample_iii_mixed | sample_iii_late  |           1.54578 |           2.2896  |             -0.74382     |
| leakage_gated_cnn_new                | sample_iii_late  | run64_only       |           2.2896  |           1.66238 |              0.627223    |
| leakage_gated_cnn_new__waveform_only | sample_iii_late  | sample_iii_early |           2.05306 |           1.1265  |              0.926564    |
| leakage_gated_cnn_new__waveform_only | sample_iii_mixed | sample_iii_late  |           1.57615 |           2.05306 |             -0.476912    |
| leakage_gated_cnn_new__waveform_only | sample_iii_late  | run64_only       |           2.05306 |           3.07343 |             -1.02037     |
| mlp                                  | sample_iii_late  | sample_iii_early |           1.77378 |           1.62387 |              0.149904    |
| mlp                                  | sample_iii_mixed | sample_iii_late  |           2.67631 |           1.77378 |              0.902538    |
| mlp                                  | sample_iii_late  | run64_only       |           1.77378 |           1.66238 |              0.111399    |
| ridge                                | sample_iii_late  | sample_iii_early |           2.27456 |           1.46515 |              0.809416    |
| ridge                                | sample_iii_mixed | sample_iii_late  |           1.86366 |           2.27456 |             -0.410898    |
| ridge                                | sample_iii_late  | run64_only       |           2.27456 |           1.66238 |              0.612184    |
| ridge__run_only                      | sample_iii_late  | sample_iii_early |           1.59507 |           1.59539 |             -0.000323164 |
| ridge__run_only                      | sample_iii_mixed | sample_iii_late  |           1.60575 |           1.59507 |              0.0106814   |
| ridge__run_only                      | sample_iii_late  | run64_only       |           1.59507 |           1.60997 |             -0.0149019   |
| ridge__safe_no_tail                  | sample_iii_late  | sample_iii_early |           1.96136 |           1.45793 |              0.503435    |
| ridge__safe_no_tail                  | sample_iii_mixed | sample_iii_late  |           1.71213 |           1.96136 |             -0.249238    |
| ridge__safe_no_tail                  | sample_iii_late  | run64_only       |           1.96136 |           1.73606 |              0.225307    |
| ridge__waveform_only                 | sample_iii_late  | sample_iii_early |           1.96212 |           1.89707 |              0.0650444   |
| ridge__waveform_only                 | sample_iii_mixed | sample_iii_late  |           1.82896 |           1.96212 |             -0.133162    |
| ridge__waveform_only                 | sample_iii_late  | run64_only       |           1.96212 |           3.07343 |             -1.11131     |
| traditional                          | sample_iii_late  | sample_iii_early |           1.45662 |           1.55775 |             -0.101121    |
| traditional                          | sample_iii_mixed | sample_iii_late  |           1.49211 |           1.45662 |              0.0354851   |
| traditional                          | sample_iii_late  | run64_only       |           1.45662 |           1.79363 |             -0.337002    |

Shuffled-pool residual-correction null:

| pool             |   ('robust_width_ns', 'median') |   ('robust_width_ns', 'min') |   ('robust_width_ns', 'max') |   ('delta_vs_original_traditional_ns', 'median') |   ('delta_vs_original_traditional_ns', 'min') |   ('delta_vs_original_traditional_ns', 'max') |
|:-----------------|--------------------------------:|-----------------------------:|-----------------------------:|-------------------------------------------------:|----------------------------------------------:|----------------------------------------------:|
| sample_iii_early |                         1.81393 |                      1.43195 |                      2.47114 |                                         0.256187 |                                    -0.125794  |                                      0.913398 |
| sample_iii_late  |                         1.64533 |                      1.50544 |                      2.25521 |                                         0.188706 |                                     0.0488171 |                                      0.798582 |
| sample_iii_mixed |                         1.86366 |                      1.86366 |                      1.86366 |                                         0.371554 |                                     0.371554  |                                      0.371554 |

## 7. Threats To Validity

**Benchmark/selection.** The traditional baseline is not a strawman: it is the best S18e-style calibrated OLS pair-residual model, and it is evaluated on exactly the same held-out runs as every learned method.

**Data leakage.** Acceptance metrics are split by run. Safe features exclude run id, event id, raw residual, sample-period indicator, and timing columns. Row-split and run-only diagnostics are reported only as sentinels, not as evidence of performance. Leakage flags: **3**.

**Metric misuse.** The report gives robust width, full RMS, Gaussian core sigma with chi2/ndf, and tail fraction. The conclusion does not rely on a narrow-core sigma alone.

**Post-hoc selection.** The metric and failure atoms came from the ticket. The broad model set is counted as multiple comparisons; only run-bootstrap deltas are used for the verdict.

## 8. Findings And Next Steps

Quantitative conclusion: the accepted winner is **sample_iii_mixed::gradient_boosted_trees** with robust width **1.370 ns** and run-block CI [1.174, 1.567] ns. The best traditional comparator is **sample_iii_late::traditional** with **1.457 ns** and run-block CI [1.255, 1.644] ns. The leakage-control tables decide whether the learned point-estimate gains are credible or likely control-definition artifacts.

Hypothesis: the late Sample-III A-stack pool contains a transferable low-order timewalk component plus a waveform nuisance component. If run-only or shuffled-pool controls rival the accepted methods, the apparent gain is not secure detector timing structure. If the safe methods beat those controls and tail-feature knockouts preserve the effect, the gain is more plausibly a real pulse-shape/timewalk correction.

Queued follow-up in `result.json`: `S18j: A-stack monotone support-matched timewalk transfer with forbidden-control freeze`. Expected information gain: it tests whether a predeclared monotone timewalk model can retain any safe gain while forbidding run/sample-period and waveform-only shortcuts.

## 9. Reproducibility

Regenerate every artifact with:

```bash
/home/billy/anaconda3/bin/python scripts/s18i_1781035068_1008_20f6375e_leakage_flag_root_cause_audit.py --config configs/s18i_1781035068_1008_20f6375e.json
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `pair_table_summary.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `support_method_metrics.csv`, `support_diagnostics.csv`, `leakage_checks.csv`, `leakage_control_gaps.csv`, `pool_transfer_deltas.csv`, `shuffled_pool_controls.csv`, `run_heldout_summary.csv`, `model_cv_scan.csv`, `train_pool_manifest.csv`, `heldout_predictions.csv`, `atom_audit.csv`, `fig_method_pool_widths.png`, and `fig_late_pool_run_gaps.png`.

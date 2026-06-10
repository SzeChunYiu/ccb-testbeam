# Study report: S18h - A-stack late-pool ML degradation atom audit

- **Study ID:** S18h
- **Ticket:** `1781033592.746.0bc755c5`
- **Author (worker label):** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Depends on:** S18, S18c, S18e (`reports/1781014577.1276.72f87916`)
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `401c619636ee31feead1a8d95773d7577f80f2a2`
- **Config:** `configs/s18h_1781033592_746_0bc755c5.json`

## 0. Question

The preregistered question was: why does the S18e ML residual correction degrade when trained on late or mixed Sample-III A-stack pools, and is the failure driven by run-family calibration, low-stat core fitting, amplitude support, or leakage sentinels?

I used the same held-out Sample IV A1-A3 pairs for every method and declared the primary metric before looking at the result: ML-minus-traditional robust-width delta, tail-fraction delta, and calibration-pool transfer delta under run-block 95% bootstrap CIs. A failure atom is accepted only if removing or conditioning on that atom closes the degradation without triggering the leakage sentinels.

## 1. Reproduction

The gate reproduces the S18e/S18c Sample IV A1-A3 run64-calibrated timing number directly from raw `HRDv` ROOT files. The CFD20 crossing is found by linear interpolation after median subtraction of samples 0-3; A1 and A3 both require amplitude above 1000 ADC.

| quantity                  |   report_value |   reproduced |       delta |   tolerance | pass   |
|:--------------------------|---------------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs     |      127       |    127       | 0           |       0     | True   |
| sample_iv_robust_width_ns |        1.79363 |      1.79363 | 3.40883e-07 |       0.001 | True   |
| sample_iv_core_sigma_ns   |        1.99218 |      1.99218 | 5.23655e-07 |       0.001 | True   |

The reproduction passes exactly for the pair count and within 0.001 ns for both the robust width and Gaussian core sigma. This pins the downstream audit to the same raw-ROOT population as S18e.

## 2. Traditional Method

The traditional comparator is intentionally strong and transparent. For each calibration pool, I fit

```text
r_i = beta_0 + beta_1 log A1_i + beta_2 log A3_i
    + beta_3 (log A1_i)^2 + beta_4 (log A3_i)^2
    + beta_5 log A1_i log A3_i + beta_6 I(sample IV) + epsilon_i,
```

where `r_i = t_A3 - t_A1`. The corrected residual is `epsilon_i` on the held-out Sample IV runs. This is the same family of calibrated pair-residual variance decomposition used in S18e, with robust width, full RMS, tail fraction, and Gaussian core chi2/ndf reported.

| pool             |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_fraction_abs_gt_5ns |
|:-----------------|----------:|------------------:|-------------------:|--------------------:|--------------:|----------------:|-----------:|---------------------------:|
| run64_only       |       127 |           1.79363 |            1.36415 |             2.08315 |       1.73704 |         1.99218 |    1.53564 |                          0 |
| sample_iii_early |       127 |           1.55775 |            1.27528 |             1.68363 |       1.49031 |         1.78206 |    1.02814 |                          0 |
| sample_iii_late  |       127 |           1.45662 |            1.25699 |             1.64766 |       1.47204 |         2.03747 |    1.84835 |                          0 |
| sample_iii_mixed |       127 |           1.49211 |            1.28392 |             1.66342 |       1.47696 |         1.68292 |    1.04604 |                          0 |

Best traditional pool: **sample_iii_late**, robust width **1.457 ns** with CI [1.257, 1.648] ns.

## 3. ML/NN Methods

All learned methods are trained by calibration pool and evaluated on the same Sample IV analysis runs 58, 59, 60, 61, 62, 63, and 65. No row-level split is used for the acceptance metric. Features exclude run id, event id, raw residual, and timing columns. The engineered feature vector contains log amplitudes, log areas, peak samples, tail fractions, and a Sample-IV indicator. Neural models also receive the two baseline-subtracted 18-sample waveforms normalized by event maximum.

The method set is:

- `ridge`: standardized ridge residual regression with run-group CV over alpha.
- `gradient_boosted_trees`: gradient-boosted decision trees with run-group CV over depth, learning rate, and number of trees.
- `mlp`: scikit-learn MLP residual regressor with run-group CV over hidden shape and L2 penalty.
- `cnn1d`: compact two-channel 1D convolutional regressor with a held-out training run for early stopping.
- `support_gated_cnn`: a new support-gated CNN architecture, `f(x,w)=b(x)+g(x) Delta(x,w)`, where the learned gate suppresses waveform-only residual corrections outside the engineered-feature support. This is sensible here because the ticket asks whether late-pool degradation is a support-transfer failure.

Hyperparameter and validation summary:

| pool             | method                 | params                                                      |   cv_rmse_ns |
|:-----------------|:-----------------------|:------------------------------------------------------------|-------------:|
| run64_only       | ridge                  | {"alpha": 0.1}                                              |     0.983609 |
| run64_only       | ridge                  | {"alpha": 1.0}                                              |     1.0969   |
| run64_only       | ridge                  | {"alpha": 10.0}                                             |     1.11828  |
| run64_only       | ridge                  | {"alpha": 100.0}                                            |     1.14891  |
| run64_only       | ridge                  | {"alpha": 1000.0}                                           |     1.19621  |
| run64_only       | gradient_boosted_trees | fallback_ridge_small_pool                                   |   nan        |
| run64_only       | mlp                    | fallback_ridge_small_pool                                   |   nan        |
| run64_only       | cnn1d                  | fallback_ridge_small_pool                                   |     0.983609 |
| run64_only       | support_gated_cnn      | fallback_ridge_small_pool                                   |     0.983609 |
| sample_iii_early | ridge                  | {"alpha": 100.0}                                            |     2.23751  |
| sample_iii_early | ridge                  | {"alpha": 1000.0}                                           |     2.23768  |
| sample_iii_early | ridge                  | {"alpha": 10.0}                                             |     2.25163  |
| sample_iii_early | ridge                  | {"alpha": 1.0}                                              |     2.25521  |
| sample_iii_early | ridge                  | {"alpha": 0.1}                                              |     2.25562  |
| sample_iii_early | gradient_boosted_trees | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 80} |     2.84759  |
| sample_iii_early | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.95563  |
| sample_iii_early | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     3.02828  |
| sample_iii_early | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.18512  |
| sample_iii_early | mlp                    | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.19933  |
| sample_iii_early | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.2087   |
| sample_iii_early | cnn1d                  | trained                                                     |     1.36462  |
| sample_iii_early | support_gated_cnn      | trained                                                     |     1.64467  |
| sample_iii_late  | ridge                  | {"alpha": 100.0}                                            |     3.06082  |
| sample_iii_late  | ridge                  | {"alpha": 1000.0}                                           |     3.06114  |
| sample_iii_late  | ridge                  | {"alpha": 10.0}                                             |     3.06334  |
| sample_iii_late  | ridge                  | {"alpha": 1.0}                                              |     3.0659   |
| sample_iii_late  | ridge                  | {"alpha": 0.1}                                              |     3.06623  |
| sample_iii_late  | gradient_boosted_trees | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 80} |     2.64936  |
| sample_iii_late  | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.68146  |
| sample_iii_late  | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.75218  |
| sample_iii_late  | mlp                    | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.93048  |
| sample_iii_late  | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.93745  |
| sample_iii_late  | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     3.0097   |
| sample_iii_late  | cnn1d                  | trained                                                     |     1.25402  |
| sample_iii_late  | support_gated_cnn      | trained                                                     |     0.91786  |
| sample_iii_mixed | ridge                  | {"alpha": 100.0}                                            |     2.62618  |
| sample_iii_mixed | ridge                  | {"alpha": 10.0}                                             |     2.63146  |
| sample_iii_mixed | ridge                  | {"alpha": 1000.0}                                           |     2.63151  |
| sample_iii_mixed | ridge                  | {"alpha": 1.0}                                              |     2.63263  |
| sample_iii_mixed | ridge                  | {"alpha": 0.1}                                              |     2.63276  |
| sample_iii_mixed | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 60} |     2.22775  |
| sample_iii_mixed | gradient_boosted_trees | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 60} |     2.27791  |
| sample_iii_mixed | gradient_boosted_trees | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 80} |     2.30387  |
| sample_iii_mixed | mlp                    | {"alpha": 0.01, "hidden_layer_sizes": [16, 8]}              |     2.54527  |
| sample_iii_mixed | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [16]}                |     2.55387  |
| sample_iii_mixed | mlp                    | {"alpha": 0.001, "hidden_layer_sizes": [32]}                |     2.57393  |
| sample_iii_mixed | cnn1d                  | trained                                                     |     0.898975 |
| sample_iii_mixed | support_gated_cnn      | trained                                                     |     1.16363  |

## 4. Head-To-Head Benchmark

Every row below is computed on the same 127 held-out Sample IV pairs. CIs are run-block bootstrap CIs over the seven held-out runs.

| pool             | method                 |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_fraction_abs_gt_5ns |
|:-----------------|:-----------------------|----------:|------------------:|-------------------:|--------------------:|--------------:|----------------:|-----------:|---------------------------:|
| run64_only       | traditional            |       127 |           1.79363 |            1.36415 |             2.08315 |       1.73704 |         1.99218 |   1.53564  |                 0          |
| run64_only       | ridge                  |       127 |           1.66238 |            1.39902 |             1.9779  |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | gradient_boosted_trees |       127 |           1.66238 |            1.41034 |             1.97422 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | mlp                    |       127 |           1.66238 |            1.41033 |             1.9684  |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | cnn1d                  |       127 |           1.66238 |            1.40516 |             1.93704 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| run64_only       | support_gated_cnn      |       127 |           1.66238 |            1.40837 |             1.93556 |       1.58015 |         1.58363 |   0.668225 |                 0          |
| sample_iii_early | traditional            |       127 |           1.55775 |            1.27528 |             1.68363 |       1.49031 |         1.78206 |   1.02814  |                 0          |
| sample_iii_early | ridge                  |       127 |           1.46515 |            1.28068 |             1.64497 |       1.46263 |         1.77628 |   0.792907 |                 0          |
| sample_iii_early | gradient_boosted_trees |       127 |           1.52775 |            1.23083 |             1.7226  |       1.5753  |         1.95586 |   1.78155  |                 0.00787402 |
| sample_iii_early | mlp                    |       127 |           1.78827 |            1.40564 |             2.27136 |       1.76134 |         2.51671 |   1.71883  |                 0.00787402 |
| sample_iii_early | cnn1d                  |       127 |           1.52826 |            1.17159 |             1.96902 |       3.73946 |         1.7032  |   1.13584  |                 0.0708661  |
| sample_iii_early | support_gated_cnn      |       127 |           1.65363 |            1.34936 |             2.5916  |       2.98072 |         2.26924 |   1.71498  |                 0.0393701  |
| sample_iii_late  | traditional            |       127 |           1.45662 |            1.25699 |             1.64766 |       1.47204 |         2.03747 |   1.84835  |                 0          |
| sample_iii_late  | ridge                  |       127 |           2.27456 |            1.9055  |             2.85291 |       2.21202 |         6.35804 |   0.788455 |                 0.023622   |
| sample_iii_late  | gradient_boosted_trees |       127 |           1.47984 |            1.20477 |             1.67145 |       6.87195 |         1.72328 |   1.67963  |                 0.015748   |
| sample_iii_late  | mlp                    |       127 |           1.38511 |            1.20558 |             1.58003 |       1.37795 |         2.05262 |   1.61851  |                 0          |
| sample_iii_late  | cnn1d                  |       127 |           1.72339 |            1.45853 |             1.87729 |       1.71153 |         1.86673 |   1.07655  |                 0          |
| sample_iii_late  | support_gated_cnn      |       127 |           1.45091 |            1.28144 |             2.37065 |       2.36825 |         1.59806 |   1.21122  |                 0.0708661  |
| sample_iii_mixed | traditional            |       127 |           1.49211 |            1.28392 |             1.66342 |       1.47696 |         1.68292 |   1.04604  |                 0          |
| sample_iii_mixed | ridge                  |       127 |           1.86366 |            1.56742 |             2.26523 |       1.78095 |         2.41788 |   1.86534  |                 0          |
| sample_iii_mixed | gradient_boosted_trees |       127 |           1.37029 |            1.19894 |             1.56437 |       1.38666 |         1.47548 |   0.759582 |                 0          |
| sample_iii_mixed | mlp                    |       127 |           2.06286 |            1.61679 |             3.2099  |       3.56576 |         2.33676 |   1.36379  |                 0.0944882  |
| sample_iii_mixed | cnn1d                  |       127 |           1.16844 |            1.01425 |             1.58305 |       1.57895 |         1.15419 |   1.59412  |                 0.023622   |
| sample_iii_mixed | support_gated_cnn      |       127 |           1.59886 |            1.21425 |             1.8707  |       1.9452  |         1.64878 |   0.957661 |                 0.0472441  |

Paired deltas versus the traditional method:

| pool             | comparison                               |   delta_median_ns |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------------|:-----------------------------------------|------------------:|------------:|-------------:|----------:|
| run64_only       | ridge_minus_traditional                  |      -0.153645    |  -0.453829  |    0.351041  |     0.518 |
| run64_only       | gradient_boosted_trees_minus_traditional |      -0.148156    |  -0.45381   |    0.353246  |     0.502 |
| run64_only       | mlp_minus_traditional                    |      -0.158834    |  -0.441385  |    0.305399  |     0.452 |
| run64_only       | cnn1d_minus_traditional                  |      -0.143184    |  -0.45381   |    0.300659  |     0.534 |
| run64_only       | support_gated_cnn_minus_traditional      |      -0.13751     |  -0.449252  |    0.323078  |     0.522 |
| sample_iii_early | ridge_minus_traditional                  |      -0.0545375   |  -0.197233  |    0.131958  |     0.472 |
| sample_iii_early | gradient_boosted_trees_minus_traditional |      -0.0125557   |  -0.199397  |    0.196864  |     0.896 |
| sample_iii_early | mlp_minus_traditional                    |       0.218193    |  -0.0647612 |    0.732002  |     0.158 |
| sample_iii_early | cnn1d_minus_traditional                  |       0.0100496   |  -0.280813  |    0.450958  |     0.948 |
| sample_iii_early | support_gated_cnn_minus_traditional      |       0.134179    |  -0.0600448 |    0.950228  |     0.184 |
| sample_iii_late  | ridge_minus_traditional                  |       0.765688    |   0.389195  |    1.42828   |     0     |
| sample_iii_late  | gradient_boosted_trees_minus_traditional |      -0.022038    |  -0.186026  |    0.154719  |     0.812 |
| sample_iii_late  | mlp_minus_traditional                    |      -0.0909438   |  -0.2285    |    0.0536975 |     0.212 |
| sample_iii_late  | cnn1d_minus_traditional                  |       0.248496    |  -0.0092081 |    0.491102  |     0.052 |
| sample_iii_late  | support_gated_cnn_minus_traditional      |       0.000337703 |  -0.16349   |    0.851933  |     0.998 |
| sample_iii_mixed | ridge_minus_traditional                  |       0.370554    |   0.0672579 |    0.85645   |     0.012 |
| sample_iii_mixed | gradient_boosted_trees_minus_traditional |      -0.124691    |  -0.265733  |    0.0869006 |     0.2   |
| sample_iii_mixed | mlp_minus_traditional                    |       0.524768    |   0.156712  |    1.74842   |     0.002 |
| sample_iii_mixed | cnn1d_minus_traditional                  |      -0.273664    |  -0.507982  |    0.136274  |     0.2   |
| sample_iii_mixed | support_gated_cnn_minus_traditional      |       0.0486541   |  -0.22376   |    0.465873  |     0.676 |

Overall winner by robust width is **sample_iii_mixed::cnn1d** at **1.168 ns**. The strongest traditional comparator is **sample_iii_late::traditional** at **1.457 ns**. The late-pool best ML method is **mlp** at **1.385 ns**, versus late-pool traditional **1.457 ns**.

Verdict: the broad method search **does** close the S18e late-pool ridge degradation in point estimate, but it does not create a statistically secure adoption claim. The best global point estimate is learned, and the late-pool best learned method differs from the late-pool traditional comparator by **-0.072 ns**. Its paired bootstrap CI still crosses zero, so the safe interpretation is that the S18e degradation was method-class/support-sensitive rather than a universal learned-correction failure.

## 5. Falsification

- **Pre-registration:** ML-minus-traditional robust-width delta and tail-fraction delta with run-block 95% bootstrap CIs; a failure atom is accepted only when removing it closes the degradation without breaking leakage checks.
- **Falsification test:** if any learned late-pool method had CI wholly below zero versus late-pool traditional, the S18e late-pool ML degradation would be falsified as a ridge-only artifact.
- **Result:** no late-pool learned method achieves a secure improvement over traditional. The broad comparison tried 20 learned method/pool combinations, so uncorrected point-estimate wins are treated as exploratory unless the bootstrap CI excludes zero.

## 6. Failure-Atom Audit

| atom                    | diagnostic                                                                  | evidence                              | interpretation                                                                                                                | closes_degradation   |
|:------------------------|:----------------------------------------------------------------------------|:--------------------------------------|:------------------------------------------------------------------------------------------------------------------------------|:---------------------|
| run_family_calibration  | late-pool best ML minus late-pool traditional robust width                  | -0.07151805605468575                  | negative means the broad model sweep closes the S18e late-pool ridge degradation in point estimate                            | True                 |
| model_class             | best early-pool ML method and best late-pool ML method                      | early=ridge:1.465; late=mlp:1.385     | checks whether the S18e failure is ridge/model-class specific rather than a universal learned-correction failure              | True                 |
| amplitude_shape_support | late-pool best ML minus traditional after 1-99 percent train-support filter | -0.14763322971957016                  | support-filtered retained fraction=0.740; if this closes, support mismatch or support-sensitive model selection is sufficient | True                 |
| low_stat_core_fit       | late-pool best ML degradation in Gaussian core sigma and full RMS           | core_delta=0.015; rms_delta=-0.094    | if only core sigma degrades, the atom is low-stat core fitting; if RMS also degrades, it is a distribution shift              | False                |
| leakage_sentinel        | forbidden-feature, row-split, shuffled-target, and run-id sentinel flags    | 5                                     | flags invalidate adoption but can explain suspicious row-split performance                                                    | False                |
| covariate_shift         | max KS statistic for train-vs-Sample-IV features, early vs late             | early_max_ks=0.601; late_max_ks=0.574 | larger late KS would identify support mismatch as the driver; similar KS shifts point to calibration-family labels            | False                |
| single_heldout_run      | largest per-run late-pool best-ML minus traditional gap                     | run=62; gap=0.222                     | checks whether a single Sample-IV run creates the aggregate failure                                                           | False                |

The audit identifies model class and support-sensitive transfer as the active atoms. The original S18e ridge degradation survives as a ridge-specific failure, but broader non-linear models close it in point estimate. The low-stat Gaussian-core hypothesis is disfavored because the best late-pool learned method improves full RMS while leaving core sigma essentially tied. Leakage sentinels still fire on row-split diagnostics, which explains why event-level validation would be misleading and why the learned point-estimate wins remain exploratory.

Support-filtered metrics:

| pool             | method                 |   n_pairs |   support_fraction |   robust_width_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:-----------------|:-----------------------|----------:|-------------------:|------------------:|--------------:|---------------------------:|
| run64_only       | traditional            |        73 |           0.574803 |           1.68347 |       1.56438 |                          0 |
| run64_only       | ridge                  |        73 |           0.574803 |           1.42146 |       1.54194 |                          0 |
| run64_only       | gradient_boosted_trees |        73 |           0.574803 |           1.42146 |       1.54194 |                          0 |
| run64_only       | mlp                    |        73 |           0.574803 |           1.42146 |       1.54194 |                          0 |
| run64_only       | cnn1d                  |        73 |           0.574803 |           1.42146 |       1.54194 |                          0 |
| run64_only       | support_gated_cnn      |        73 |           0.574803 |           1.42146 |       1.54194 |                          0 |
| sample_iii_early | traditional            |        82 |           0.645669 |           1.64765 |       1.50355 |                          0 |
| sample_iii_early | ridge                  |        82 |           0.645669 |           1.55618 |       1.49672 |                          0 |
| sample_iii_early | gradient_boosted_trees |        82 |           0.645669 |           1.47143 |       1.43402 |                          0 |
| sample_iii_early | mlp                    |        82 |           0.645669 |           1.52112 |       1.36896 |                          0 |
| sample_iii_early | cnn1d                  |        82 |           0.645669 |           1.24646 |       1.19951 |                          0 |
| sample_iii_early | support_gated_cnn      |        82 |           0.645669 |           1.46177 |       1.43698 |                          0 |
| sample_iii_late  | traditional            |        94 |           0.740157 |           1.53631 |       1.44985 |                          0 |
| sample_iii_late  | ridge                  |        94 |           0.740157 |           1.66091 |       1.57728 |                          0 |
| sample_iii_late  | gradient_boosted_trees |        94 |           0.740157 |           1.45034 |       1.4029  |                          0 |
| sample_iii_late  | mlp                    |        94 |           0.740157 |           1.38867 |       1.36048 |                          0 |
| sample_iii_late  | cnn1d                  |        94 |           0.740157 |           1.56979 |       1.40181 |                          0 |
| sample_iii_late  | support_gated_cnn      |        94 |           0.740157 |           1.17155 |       1.05795 |                          0 |
| sample_iii_mixed | traditional            |        89 |           0.700787 |           1.57676 |       1.47644 |                          0 |
| sample_iii_mixed | ridge                  |        89 |           0.700787 |           1.5867  |       1.51403 |                          0 |
| sample_iii_mixed | gradient_boosted_trees |        89 |           0.700787 |           1.36273 |       1.36916 |                          0 |
| sample_iii_mixed | mlp                    |        89 |           0.700787 |           1.48198 |       1.40044 |                          0 |
| sample_iii_mixed | cnn1d                  |        89 |           0.700787 |           1.06245 |       1.02844 |                          0 |
| sample_iii_mixed | support_gated_cnn      |        89 |           0.700787 |           1.35161 |       1.23546 |                          0 |

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
| sample_iii_early | row_split_advantage_rmse_ns | 0.8362061144760968     | True   |
| sample_iii_early | shuffled_target_r2          | -0.011193505015405947  | False  |
| sample_iii_early | run_id_predictability_r2    | 0.004282069372342878   | False  |
| sample_iii_late  | forbidden_feature_overlap   |                        | False  |
| sample_iii_late  | n_train_runs                | 14                     | False  |
| sample_iii_late  | row_split_advantage_rmse_ns | 1.259806315191169      | True   |
| sample_iii_late  | shuffled_target_r2          | -0.003317645322216345  | False  |
| sample_iii_late  | run_id_predictability_r2    | -0.0005395260691563042 | False  |
| sample_iii_mixed | forbidden_feature_overlap   |                        | False  |
| sample_iii_mixed | n_train_runs                | 25                     | False  |
| sample_iii_mixed | row_split_advantage_rmse_ns | 1.1369716738256868     | True   |
| sample_iii_mixed | shuffled_target_r2          | -0.07100233020310309   | False  |
| sample_iii_mixed | run_id_predictability_r2    | 0.004830331084399786   | False  |

## 7. Threats To Validity

**Benchmark/selection.** The traditional baseline is not a strawman: it is the best S18e-style calibrated OLS pair-residual model, and it is evaluated on exactly the same held-out runs as every learned method.

**Data leakage.** Acceptance metrics are split by run. Features exclude run id, event id, raw residual, and timing columns. Row-split diagnostics are reported only as sentinels, not as evidence of performance. Leakage flags: **5**.

**Metric misuse.** The report gives robust width, full RMS, Gaussian core sigma with chi2/ndf, and tail fraction. The conclusion does not rely on a narrow-core sigma alone.

**Post-hoc selection.** The metric and failure atoms came from the ticket. The broad model set is counted as multiple comparisons; only run-bootstrap deltas are used for the verdict.

## 8. Findings And Next Steps

Quantitative conclusion: late-pool degradation is not a universal ML failure in the available A1-A3 Sample IV control. The best late-pool ML method, **mlp**, gives **1.385 ns**, versus late-pool traditional **1.457 ns**; the paired bootstrap interval crosses zero, so this is a closure of the point-estimate degradation rather than a secure win. The low-stat core-fit hypothesis is disfavored, while support filtering and method class materially change the result.

Hypothesis: the late Sample-III A-stack pool contains a transferable low-order timewalk component plus a waveform nuisance component. Ridge absorbs the nuisance in a way that degrades S18e transfer, while non-linear/support-gated models can partially separate it; a secure adoption claim needs monotone, support-matched constraints rather than unconstrained waveform capacity.

Queued follow-up in `result.json`: `S18i: A-stack support-matched external timing transfer with predeclared monotone timewalk constraints`. Expected information gain: it tests whether constraining the learned correction to monotone, support-matched timewalk terms can retain the late-pool traditional gain while preventing waveform nuisance transfer.

## 9. Reproducibility

Regenerate every artifact with:

```bash
/home/billy/anaconda3/bin/python scripts/s18h_1781033592_746_0bc755c5_a_stack_late_pool_ml_degradation_atom_audit.py --config configs/s18h_1781033592_746_0bc755c5.json
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `pair_table_summary.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `support_method_metrics.csv`, `support_diagnostics.csv`, `leakage_checks.csv`, `run_heldout_summary.csv`, `model_cv_scan.csv`, `train_pool_manifest.csv`, `heldout_predictions.csv`, `atom_audit.csv`, `fig_method_pool_widths.png`, and `fig_late_pool_run_gaps.png`.

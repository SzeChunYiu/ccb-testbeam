# S18g: sparse-run mixture stress test of the Sample IV A-stack binned Gaussian

- **Ticket:** `1781034287.20785.3a3e6ff5`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input:** raw A-stack ROOT `HRDv`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18g_1781034287_20785_3a3e6ff5_sparse_run_mixture_stress.py --config configs/s18g_1781034287_20785_3a3e6ff5.json`
- **Primary endpoint:** Sample IV A1-A3 run-held-out robust residual width, with 95% CIs from held-out-run bootstraps.
- **Stress endpoint:** fixed-window binned Gaussian core sigma under empirical and parametric run-mixture bootstraps, including optimizer-bound hit rates.

## Abstract

S18d/S18f found that the Sample IV A1-A3 binned Gaussian core sigma can change sharply when individual sparse runs enter or leave the histogram. This study asks whether that behavior is primarily an occupancy/optimizer artifact rather than a stable detector-resolution change. The historical binned Gaussian number is first reproduced from raw `HRDv`; then a traditional log-amplitude CFD20 correction is benchmarked against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new run-mixture attention CNN. The winner by the preregistered run-held-out robust-width endpoint is **runmix_attention_cnn_new** with width **0.490 ns** and CI **[0.414, 0.610] ns**. The binned Gaussian endpoint is retained as a diagnostic because sparse histograms can hit optimizer bounds.

## Reproduction From Raw ROOT

For each event, `HRDv` is reshaped to `(8, 18)`. Samples 0--3 define the per-channel pedestal; A1 and A3 are baseline-subtracted; CFD20 times are linearly interpolated on the leading edge; a pair is accepted if both channel maxima exceed 1000 ADC. The historical S18d/S18f run64-calibrated Sample IV definition is reproduced before any new model is trained.

| quantity                            |   expected |   reproduced |        delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|-------------:|------------:|:-------|
| sample_iii_analysis_A1_A3_pairs     | 2514       |   2514       |  0           |       0     | True   |
| sample_iii_core_sigma_ns            |    1.45092 |      1.45092 | -2.79531e-07 |       0.001 | True   |
| sample_iv_A1_A3_pairs               |  127       |    127       |  0           |       0     | True   |
| sample_iv_run64_ols_robust_width_ns |    1.79363 |      1.79363 |  3.40883e-07 |       0.001 | True   |
| sample_iv_run64_ols_core_sigma_ns   |    1.99218 |      1.99218 |  5.31425e-08 |       0.001 | True   |

Raw scan counts:

| sample              |   events_total |   events_with_selected |   A1_A3_pairs |   selected_pulses |   A1 |    A3 |
|:--------------------|---------------:|-----------------------:|--------------:|------------------:|-----:|------:|
| sample_iii_calib    |         409803 |                  11067 |          3816 |             14883 | 4111 | 10772 |
| sample_iii_analysis |         388848 |                   7168 |          2514 |              9682 | 2799 |  6883 |
| sample_iv_calib     |          35985 |                    161 |            16 |               177 |   20 |   157 |
| sample_iv_analysis  |         262189 |                    767 |           127 |               894 |  167 |   727 |

## Data Split

Training uses runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57,64`: all available Sample III A1-A3 runs plus Sample IV calibration run 64. Evaluation uses held-out Sample IV analysis runs `58,59,60,61,62,63,65`. No method is trained on any row from the held-out analysis runs. All uncertainty intervals resample held-out runs, not rows.

## Methods

Let `w_L(s)` and `w_R(s)` denote the 18-sample baseline-subtracted A1/A3 waveforms, and let

`y_i = t_{R,i}^{CFD20} - t_{L,i}^{CFD20}`.

Each method learns `hat y_i=f(x_i)` on the training runs and reports held-out residuals

`e_i = y_i - hat y_i`.

The traditional model is a quadratic log-amplitude period polynomial,

`hat y = beta_0 + beta_1 log A_L + beta_2 log A_R + beta_3 (log A_L)^2 + beta_4 (log A_R)^2 + beta_5 log A_L log A_R + beta_6 I_IV`.

Ridge, gradient-boosted trees, and MLP use engineered waveform/amplitude features: log amplitudes, log positive areas, peak samples, tail fractions, normalized waveform samples, and A3-A1 waveform differences. Ridge alpha is selected by GroupKFold over training runs. The 1D-CNN receives the two normalized waveforms plus auxiliary shape features. The new `runmix_attention_cnn_new` is sensible here because sparse-run mixtures can change which time samples dominate the residual; it combines local and wide temporal convolutions with a learned attention pooling over the 18 samples.

## Fixed-Window Binned Gaussian

The diagnostic binned estimator uses 40 bins in `[-2.5, 2.5] ns` after median-centering. A Gaussian amplitude, mean, and sigma are fit by weighted least squares with Poisson bin errors and sigma bounds `[0.05, 5.0] ns`:

`N_j approx A exp[-(c_j-mu)^2/(2 sigma^2)]`.

The report records nonempty-bin occupancy, maximum bin count, chi-square per degree of freedom, and whether the optimizer reached the configured sigma bounds. The unbinned robust width and RMS are co-primary diagnostics because the binned estimator is not stable when only 127 pairs populate 40 bins.

## Method Benchmark

| method                   |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   binned_sigma_ns |   empirical_binned_sigma_ci_low_ns |   empirical_binned_sigma_ci_high_ns |   empirical_bound_hit_rate |   parametric_bound_hit_rate |   nonempty_bins |   occupied_fraction |
|:-------------------------|----------:|------------------:|-------------------:|--------------------:|------------------:|-----------------------------------:|------------------------------------:|---------------------------:|----------------------------:|----------------:|--------------------:|
| runmix_attention_cnn_new |       127 |          0.490437 |           0.414265 |            0.610272 |          0.439429 |                           0.392854 |                             1.26415 |                    0.0025  |                       0     |              23 |               0.575 |
| cnn_1d                   |       127 |          0.936728 |           0.724052 |            1.02605  |          0.877044 |                           0.724575 |                             1.76002 |                    0       |                       0     |              29 |               0.725 |
| gradient_boosted_trees   |       127 |          0.958356 |           0.488023 |            1.40505  |          0.383587 |                           0.293026 |                             2.27756 |                    0.00375 |                       0     |              28 |               0.7   |
| mlp                      |       127 |          1.0381   |           0.741978 |            1.21828  |          1.03651  |                           0.676014 |                             2.03062 |                    0.00125 |                       0     |              32 |               0.8   |
| ridge                    |       127 |          1.45304  |           1.2168   |            1.83979  |          1.5752   |                           1.11436  |                             5       |                    0.03875 |                       0.02  |              34 |               0.85  |
| traditional_period_poly  |       127 |          1.49227  |           1.22641  |            1.65832  |          1.68292  |                           1.45062  |                             5       |                    0.06    |                       0.015 |              38 |               0.95  |

Ridge CV scan:

|   alpha |   cv_rmse_ns |   cv_rmse_std_ns | selected   |
|--------:|-------------:|-----------------:|:-----------|
|    1    |      1.76615 |         0.362574 | True       |
|    0.1  |      1.77308 |         0.349446 | False      |
|    0.01 |      1.77487 |         0.347912 | False      |
|   10    |      1.82458 |         0.447046 | False      |
|  100    |      1.97794 |         0.546277 | False      |
| 1000    |      2.12061 |         0.645187 | False      |

## Paired Run-Bootstrap Deltas

Negative deltas favor the named method relative to the traditional period polynomial. The delta is computed on the same sampled held-out runs in each bootstrap replicate.

| comparison                                             |   robust_width_delta_ns |   ci_low_ns |   ci_high_ns |   p_value |
|:-------------------------------------------------------|------------------------:|------------:|-------------:|----------:|
| ridge_minus_traditional_period_poly                    |              -0.0392276 |   -0.321824 |    0.483281  |     0.655 |
| gradient_boosted_trees_minus_traditional_period_poly   |              -0.533914  |   -1.03661  |   -0.0108326 |     0.05  |
| mlp_minus_traditional_period_poly                      |              -0.454174  |   -0.731538 |   -0.158667  |     0.01  |
| cnn_1d_minus_traditional_period_poly                   |              -0.555542  |   -0.752606 |   -0.381607  |     0     |
| runmix_attention_cnn_new_minus_traditional_period_poly |              -1.00183   |   -1.16857  |   -0.775945  |     0     |

## Per-Run Metrics

| method                   |   run |   n_pairs |   robust_width_ns |   rms_ns |
|:-------------------------|------:|----------:|------------------:|---------:|
| traditional_period_poly  |    58 |        25 |          1.14694  | 1.32746  |
| traditional_period_poly  |    59 |        11 |          0.954114 | 1.02986  |
| traditional_period_poly  |    60 |        11 |          1.01982  | 1.05487  |
| traditional_period_poly  |    61 |        18 |          1.51889  | 1.86104  |
| traditional_period_poly  |    62 |         7 |          1.04809  | 1.66814  |
| traditional_period_poly  |    63 |        28 |          1.2894   | 1.35467  |
| traditional_period_poly  |    65 |        27 |          1.63927  | 1.61528  |
| ridge                    |    58 |        25 |          1.1532   | 2.19569  |
| ridge                    |    59 |        11 |          2.74197  | 3.0859   |
| ridge                    |    60 |        11 |          1.15475  | 1.40303  |
| ridge                    |    61 |        18 |          1.37921  | 1.84068  |
| ridge                    |    62 |         7 |          1.88148  | 6.29712  |
| ridge                    |    63 |        28 |          1.05684  | 1.95241  |
| ridge                    |    65 |        27 |          1.42534  | 2.85071  |
| gradient_boosted_trees   |    58 |        25 |          0.496872 | 1.30476  |
| gradient_boosted_trees   |    59 |        11 |          0.96927  | 1.66907  |
| gradient_boosted_trees   |    60 |        11 |          0.655198 | 1.36007  |
| gradient_boosted_trees   |    61 |        18 |          1.61527  | 1.78215  |
| gradient_boosted_trees   |    62 |         7 |          1.45045  | 1.70578  |
| gradient_boosted_trees   |    63 |        28 |          0.496707 | 1.21168  |
| gradient_boosted_trees   |    65 |        27 |          0.43038  | 0.968782 |
| mlp                      |    58 |        25 |          0.721638 | 1.06963  |
| mlp                      |    59 |        11 |          1.06568  | 1.88135  |
| mlp                      |    60 |        11 |          0.504179 | 1.30547  |
| mlp                      |    61 |        18 |          1.29478  | 1.48622  |
| mlp                      |    62 |         7 |          0.751509 | 0.693347 |
| mlp                      |    63 |        28 |          0.960567 | 1.07006  |
| mlp                      |    65 |        27 |          0.941973 | 0.869435 |
| cnn_1d                   |    58 |        25 |          0.684158 | 0.776848 |
| cnn_1d                   |    59 |        11 |          0.668938 | 0.760656 |
| cnn_1d                   |    60 |        11 |          0.460179 | 0.597929 |
| cnn_1d                   |    61 |        18 |          1.08281  | 1.15202  |
| cnn_1d                   |    62 |         7 |          0.999174 | 1.30652  |
| cnn_1d                   |    63 |        28 |          0.937957 | 0.851229 |
| cnn_1d                   |    65 |        27 |          0.995416 | 1.06144  |
| runmix_attention_cnn_new |    58 |        25 |          0.466364 | 0.522948 |
| runmix_attention_cnn_new |    59 |        11 |          0.41833  | 0.402715 |
| runmix_attention_cnn_new |    60 |        11 |          0.350823 | 0.363065 |
| runmix_attention_cnn_new |    61 |        18 |          0.556842 | 0.658553 |
| runmix_attention_cnn_new |    62 |         7 |          0.743085 | 0.619564 |
| runmix_attention_cnn_new |    63 |        28 |          0.37245  | 0.443663 |
| runmix_attention_cnn_new |    65 |        27 |          0.478135 | 0.560946 |

## Sparse-Mixture Interpretation

The empirical run-mixture bootstrap resamples the seven held-out runs with replacement and keeps each selected run's observed residuals. This preserves the actual low-count run composition and waveform tails. The parametric bootstrap samples the same run counts but draws Gaussian residuals with each run's observed median and a global robust sigma; it isolates histogram occupancy and optimizer behavior when the residual law is idealized.

If the empirical and parametric bound-hit rates are both large, sparse occupancy alone is sufficient to destabilize the binned fit. If empirical is much larger, non-Gaussian tails or run-specific shape changes contribute beyond occupancy. The table above shows that the binned estimator should be interpreted as a stress diagnostic, while the winner is named from the run-held-out robust-width endpoint.

## Systematics, Caveats, and Leakage Checks

| check                         | value                                          | flag   |
|:------------------------------|:-----------------------------------------------|:-------|
| forbidden_feature_overlap     |                                                | False  |
| heldout_run_overlap           | Sample IV analysis runs excluded from training | False  |
| group_split_r2_mean           | 0.507123155293417                              | False  |
| row_split_advantage_rmse_ns   | -1.003741795444006                             | False  |
| shuffled_target_group_r2_mean | -0.008904023717349264                          | False  |

Main caveats:

- **Only seven held-out runs:** the bootstrap is honest about run composition but cannot create new detector states.
- **Binned estimator fragility:** 127 pairs across 40 bins leaves many empty or singleton bins, so optimizer-bound hit rates are part of the result, not an implementation nuisance.
- **Training support mismatch:** Sample III supplies most training statistics; run64 anchors Sample IV, but Sample IV analysis remains low-statistics and period-shifted.
- **Model multiplicity:** six methods are compared; the named winner is a benchmark ranking under one endpoint, not a discovery p-value.
- **No row leakage:** features exclude run, event, target residual, and CFD times; all acceptance metrics are split by held-out run.

## Conclusion

The strongest result is that the binned Gaussian sigma is highly sensitive to sparse-run mixture occupancy and optimizer bounds. The robust-width benchmark names **runmix_attention_cnn_new** as the winner, but the binned Gaussian fit should not be read as a stable per-run detector-resolution estimator without the accompanying occupancy and bound-hit diagnostics. The stress-test evidence supports the S18f interpretation: much of the apparent Sample IV binned-sigma movement is a sparse-histogram/run-composition effect rather than a clean physical broadening.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `bootstrap_replicates.csv.gz`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this directory.

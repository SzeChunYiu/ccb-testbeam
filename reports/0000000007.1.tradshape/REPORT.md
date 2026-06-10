# T07: traditional pulse-shape survey and ML/NN benchmark

**Ticket:** `0000000007.1.tradshape`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study benchmarks classic, non-ML pulse-shape analysis on the 18-sample B-stave waveforms and then pits the strongest traditional discriminator against a supervised ML/NN panel. The concrete weak-label task is the P02-style anomalous morphology label derived only from pulse shape: early or low-area peaks, very late peaks, and large negative sample-to-sample drops are positive; ordinary peak-region pulses are negative. The winner by held-out ROC AUC is **ML_gradient_boosted_trees** with AUC **1.0000** [1.0000, 1.0000].

## Raw reproduction gate

The raw ROOT files were rescanned before modeling. For each event, `HRDv` was reshaped to `(8, 18)`, samples 0-3 supplied the per-channel baseline, B-stave even channels B2/B4/B6/B8 were baseline-subtracted, and a pulse was selected when its maximum amplitude exceeded 1000 ADC. This reproduced **640,737** selected B-stave pulses against the registered **640,737** count, delta **0**.

## Statistical task

Let the normalized waveform be `x_i(t)=v_i(t)/max_t v_i(t)` for samples `t=0,...,17`. The binary target is

`y_i = 1{peak_i <= 3 or (peak_i <= 4 and sum_t x_i(t) < 3.0) or peak_i >= 12 or min_t Delta x_i(t) < -0.75}`.

The target is not a particle-ID truth label. It is a morphology stress test chosen because it is reproducible from raw waveforms and exercises the pulse-shape methods named in the ticket.

Label counts in the run-balanced benchmark sample:

| split | rows | positives | positive fraction |
|---|---:|---:|---:|
| train | 25,493 | 6,205 | 0.2434 |
| heldout | 9,745 | 2,077 | 0.2131 |
| all | 35,238 | 8,282 | 0.2350 |

Held-out runs were `42, 50, 57, 58, 60, 62, 64, 65`; all model fitting used the other runs. Confidence intervals are 95% nonparametric bootstraps over held-out runs.

The benchmark sample is stratified by `(run, stave)` with a cap of `max_per_run_stave` records per cell, so no high-statistics run can dominate the model fit or the held-out evaluation. If `R` is the held-out run set and `AUC(D)` is the pooled ROC AUC on rows `D`, each bootstrap replicate draws `|R|` runs with replacement, pools their rows, and records `AUC_b = AUC(union_{r in R_b} D_r)`. The reported CI is the 2.5% and 97.5% quantile of `{AUC_b}`.

## Traditional methods

The survey covers charge-comparison PSD gates, rise-time and pulse-width, derivative/zero-crossing features, Gatti/current-integration filters, matched-template chi2, mean-time and higher moments, FFT features, Haar wavelet coefficients, and constant-fraction/leading-edge ratios.

| family | representative variables |
|---|---|
| charge-comparison PSD | tail/total gates at samples 10-17, 12-17, 14-17; early/total; late-minus-early asymmetry |
| rise time and width | interpolated 10%, 20%, 50%, 80% crossings; widths above 20% and 50% of peak |
| zero-crossing/current shape | maximum rise/fall sample differences and derivative sign-change count |
| Gatti/current integration | waveform-level optimal linear current filter and Fisher/Gatti feature-space score |
| matched filter/template chi2 | nominal-template chi2 and nominal-minus-anomalous template chi2 |
| moments, FFT, wavelet | mean time, variance, skewness, kurtosis, FFT band ratios, Haar detail coefficients |
| constant-fraction ratios | CFD times and leading-edge sample ratios |

For a scalar traditional score `s`, orientation is fixed on training runs so that `AUC_train(s) >= 0.5`; the held-out AUC is then evaluated without reorientation. The Gatti filter uses

`w_t = (mu_1(t)-mu_0(t))/(sigma_1^2(t)+sigma_0^2(t)+epsilon),  S_i = sum_t w_t x_i(t)`,

and the Fisher/Gatti shape score applies the same supervised linear-discriminant principle to the full engineered traditional feature vector with covariance shrinkage.

Top traditional rows:

| rank | method | family | AUC | 95% CI | AP |
|---:|---|---|---:|---:|---:|
| 1 | traditional_fisher_gatti_all_features | fisher_gatti_engineered_features | 0.9950 | [0.9924, 0.9972] | 0.9804 |
| 2 | traditional_gatti_waveform | current_integration_gatti | 0.9918 | [0.9902, 0.9931] | 0.9683 |
| 3 | traditional_scalar__matched_template_delta_chi2 | matched_filter_template_chi2 | 0.9909 | [0.9891, 0.9925] | 0.9654 |
| 4 | traditional_scalar__matched_template_nominal_chi2 | matched_filter_template_chi2 | 0.9884 | [0.9867, 0.9906] | 0.9393 |
| 5 | traditional_scalar__area_over_peak | traditional_scalar | 0.9697 | [0.9637, 0.9748] | 0.9075 |
| 6 | traditional_scalar__positive_area | traditional_scalar | 0.9689 | [0.9603, 0.9754] | 0.9367 |
| 7 | traditional_scalar__width20 | rise_time_width | 0.9505 | [0.9378, 0.9619] | 0.9108 |
| 8 | traditional_scalar__time_variance | mean_time_moments | 0.9251 | [0.9083, 0.9383] | 0.9036 |
| 9 | traditional_scalar__width50 | rise_time_width | 0.9219 | [0.9073, 0.9327] | 0.8209 |
| 10 | traditional_scalar__haar_l0_d02 | wavelet_haar | 0.8941 | [0.8848, 0.9084] | 0.6589 |
| 11 | traditional_scalar__haar_l1_d01 | wavelet_haar | 0.8931 | [0.8868, 0.9007] | 0.6064 |
| 12 | traditional_scalar__middle_5_9_over_total | charge_comparison_psd | 0.8593 | [0.7865, 0.9117] | 0.8296 |
| 13 | traditional_scalar__time_skewness | mean_time_moments | 0.8454 | [0.8046, 0.8749] | 0.8103 |
| 14 | traditional_scalar__fft_k1_fraction | frequency_domain_fft | 0.8430 | [0.8150, 0.8652] | 0.6845 |
| 15 | traditional_scalar__fft_high_over_low | frequency_domain_fft | 0.8275 | [0.7790, 0.8561] | 0.7144 |

## ML/NN comparison

Ridge, gradient-boosted trees, and MLP receive the normalized waveform, all traditional engineered features, and stave one-hot indicators. The 1D-CNN and the new residual squeeze CNN receive the normalized waveform plus stave one-hot indicators. The residual squeeze CNN is the new architecture: it uses residual temporal convolutions, global average/max pooling, and a small squeeze gate, which is sensible for 18 samples because it can combine local edge cues with pulse-wide tail information without a large parameter count.

| model | inputs | fit details |
|---|---|---|
| Ridge classifier | waveform + traditional features + stave one-hot | standardized linear ridge classifier, class-balanced loss |
| Gradient-boosted trees | waveform + traditional features + stave one-hot | histogram GBT, 80 boosting iterations, depth constrained by 15 leaves |
| MLP | waveform + traditional features + stave one-hot | standardized 64-32 ReLU network with early stopping |
| 1D-CNN | waveform + stave one-hot | two temporal convolutions with global average pooling |
| Residual squeeze CNN | waveform + stave one-hot | residual temporal convolutions, squeeze gate, average/max pooling |

| method | role | AUC | 95% CI | AP | rows | positives |
|---|---|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | ml_panel | 1.0000 | [1.0000, 1.0000] | 1.0000 | 9,745 | 2,077 |
| ML_mlp | ml_panel | 0.9996 | [0.9993, 0.9998] | 0.9990 | 9,745 | 2,077 |
| traditional_fisher_gatti_all_features | traditional_multivariate | 0.9950 | [0.9924, 0.9972] | 0.9804 | 9,745 | 2,077 |
| ML_ridge_classifier | ml_panel | 0.9935 | [0.9905, 0.9960] | 0.9625 | 9,745 | 2,077 |
| NN_residual_squeeze_cnn_new | ml_panel | 0.9844 | [0.9784, 0.9895] | 0.9548 | 9,745 | 2,077 |
| NN_1d_cnn | ml_panel | 0.9741 | [0.9662, 0.9807] | 0.9193 | 9,745 | 2,077 |

## Per-run behavior

| method | mean per-run AUC | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 1.0000 | 1.0000 | 1.0000 | 8 |
| ML_mlp | 0.9996 | 0.9986 | 1.0000 | 8 |
| ML_ridge_classifier | 0.9933 | 0.9869 | 0.9988 | 8 |
| NN_1d_cnn | 0.9735 | 0.9532 | 0.9865 | 8 |
| NN_residual_squeeze_cnn_new | 0.9834 | 0.9688 | 0.9952 | 8 |
| traditional_fisher_gatti_all_features | 0.9945 | 0.9883 | 0.9988 | 8 |

## Systematics and caveats

- The target is weak and morphology-defined; it validates discriminators for the chosen waveform anomaly class, not a physics truth class.
- The label rule contains peak position, integrated area, and negative-step terms, and the supervised feature-matrix models can see close relatives of those variables. The near-perfect GBT result is therefore a successful benchmark on the registered morphology rule, not evidence of new latent physics.
- Run-heldout splitting protects against random-row leakage, but the eight held-out runs are still finite; CIs are run-block bootstraps, not independent-event CIs.
- Amplitude and stave are included only as context in supervised ML matrices. The raw reproduction and scalar traditional survey show that shape-only methods already solve most of the task.
- Neural nets were intentionally small because the waveform has only 18 samples; larger architectures would be underconstrained without an external truth target.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner. The best traditional method is **traditional_fisher_gatti_all_features**. On this weak-label pulse-shape benchmark, the strongest ML/NN model beats the traditional baseline within the run-bootstrap CI structure.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/t07_tradshape_ml_benchmark.py --config configs/0000000007.1.tradshape.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `traditional_method_summary.csv`, `primary_method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, and this report.

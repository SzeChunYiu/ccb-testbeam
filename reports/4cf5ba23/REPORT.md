# T07: traditional pulse-shape survey and ML/NN benchmark

**Ticket:** `4cf5ba23`  
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
| train | 25,493 | 6,104 | 0.2394 |
| heldout | 9,745 | 2,089 | 0.2144 |
| all | 35,238 | 8,193 | 0.2325 |

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
| 1 | traditional_fisher_gatti_all_features | fisher_gatti_engineered_features | 0.9955 | [0.9935, 0.9974] | 0.9853 |
| 2 | traditional_gatti_waveform | current_integration_gatti | 0.9916 | [0.9890, 0.9933] | 0.9716 |
| 3 | traditional_scalar__matched_template_delta_chi2 | matched_filter_template_chi2 | 0.9907 | [0.9878, 0.9928] | 0.9676 |
| 4 | traditional_scalar__matched_template_nominal_chi2 | matched_filter_template_chi2 | 0.9884 | [0.9868, 0.9899] | 0.9378 |
| 5 | traditional_scalar__positive_area | traditional_scalar | 0.9718 | [0.9648, 0.9784] | 0.9397 |
| 6 | traditional_scalar__area_over_peak | traditional_scalar | 0.9714 | [0.9651, 0.9767] | 0.9089 |
| 7 | traditional_scalar__width20 | rise_time_width | 0.9558 | [0.9420, 0.9674] | 0.9179 |
| 8 | traditional_scalar__time_variance | mean_time_moments | 0.9337 | [0.9182, 0.9482] | 0.9136 |
| 9 | traditional_scalar__width50 | rise_time_width | 0.9230 | [0.9084, 0.9337] | 0.8229 |
| 10 | traditional_scalar__haar_l0_d02 | wavelet_haar | 0.8959 | [0.8855, 0.9062] | 0.6591 |
| 11 | traditional_scalar__haar_l1_d01 | wavelet_haar | 0.8927 | [0.8810, 0.9038] | 0.6063 |
| 12 | traditional_scalar__middle_5_9_over_total | charge_comparison_psd | 0.8675 | [0.8045, 0.9100] | 0.8423 |
| 13 | traditional_scalar__time_skewness | mean_time_moments | 0.8517 | [0.8132, 0.8773] | 0.8187 |
| 14 | traditional_scalar__fft_k1_fraction | frequency_domain_fft | 0.8427 | [0.8172, 0.8667] | 0.6882 |
| 15 | traditional_scalar__fft_high_over_low | frequency_domain_fft | 0.8301 | [0.7927, 0.8548] | 0.7165 |

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
| ML_gradient_boosted_trees | ml_panel | 1.0000 | [1.0000, 1.0000] | 1.0000 | 9,745 | 2,089 |
| ML_mlp | ml_panel | 0.9998 | [0.9996, 0.9999] | 0.9993 | 9,745 | 2,089 |
| traditional_fisher_gatti_all_features | traditional_multivariate | 0.9955 | [0.9935, 0.9974] | 0.9853 | 9,745 | 2,089 |
| ML_ridge_classifier | ml_panel | 0.9945 | [0.9921, 0.9966] | 0.9743 | 9,745 | 2,089 |
| NN_residual_squeeze_cnn_new | ml_panel | 0.9837 | [0.9778, 0.9885] | 0.9449 | 9,745 | 2,089 |
| NN_1d_cnn | ml_panel | 0.9749 | [0.9671, 0.9805] | 0.9244 | 9,745 | 2,089 |

## Per-run behavior

| method | mean per-run AUC | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 1.0000 | 1.0000 | 1.0000 | 8 |
| ML_mlp | 0.9997 | 0.9988 | 1.0000 | 8 |
| ML_ridge_classifier | 0.9945 | 0.9873 | 0.9983 | 8 |
| NN_1d_cnn | 0.9739 | 0.9581 | 0.9866 | 8 |
| NN_residual_squeeze_cnn_new | 0.9823 | 0.9713 | 0.9935 | 8 |
| traditional_fisher_gatti_all_features | 0.9954 | 0.9891 | 0.9989 | 8 |

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

# S25b: Pedestal nonstationarity pulse-shape audit

**Ticket:** `1783775623.7070.7bfe60c5`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study audits pedestal nonstationarity in selected B-stave pulses and its coupling to corrected 18-sample pulse shape, timing, pile-up-like tails, saturation onset, energy, and PID proxy observables. The concrete weak-label task is high pedestal drift: pulses whose pre-trigger baseline deviates strongly from the run/stave median are positive. A traditional pedestal subtraction plus robust spline/AR-inspired feature scorecard is benchmarked against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a new transformer-style sequence encoder under run-heldout validation. The winner by held-out ROC AUC is **ML_gradient_boosted_trees** with AUC **0.9568** [0.9351, 0.9719].

## Raw reproduction gate

The raw ROOT files were rescanned before modeling. For each event, `HRDv` was reshaped to `(8, 18)`, samples 0-3 supplied the per-channel baseline, B-stave even channels B2/B4/B6/B8 were baseline-subtracted, and a pulse was selected when its maximum amplitude exceeded 1000 ADC. This reproduced **640,737** selected B-stave pulses against the registered **640,737** count, delta **0**.

## Pedestal-drift statistical task

Let `b_i` be the median ADC pedestal in samples 0-3 for the selected channel and `m_{r,s}` the median pedestal for run `r` and stave `s` in the run-balanced benchmark sample. The drift residual is

`d_i = b_i - m_{run_i,stave_i}`

and the binary target is

`y_i = 1{|d_i| >= Q_{0.80}(|d|)}`.

The normalized corrected waveform is `x_i(t)=(v_i(t)-b_i)/max_t(v_i(t)-b_i)`. A shape-invariant detector should not predict `y_i` well from `x_i` after run/stave blocking. Conversely, high held-out AUC indicates residual pedestal information is still present in waveform shape, amplitude context, or detector/run structure.

Label counts in the run-balanced benchmark sample:

| split | rows | positives | positive fraction |
|---|---:|---:|---:|
| train | 25,493 | 5,060 | 0.1985 |
| heldout | 9,745 | 2,038 | 0.2091 |
| all | 35,238 | 7,098 | 0.2014 |

Held-out runs were `42, 50, 57, 58, 60, 62, 64, 65`; all model fitting used the other runs. Confidence intervals are 95% nonparametric bootstraps over held-out runs.

The benchmark sample is stratified by `(run, stave)` with a cap of `max_per_run_stave` records per cell, so no high-statistics run can dominate the model fit or the held-out evaluation. If `R` is the held-out run set and `AUC(D)` is the pooled ROC AUC on rows `D`, each bootstrap replicate draws `|R|` runs with replacement, pools their rows, and records `AUC_b = AUC(union_{r in R_b} D_r)`. The reported CI is the 2.5% and 97.5% quantile of `{AUC_b}`. The script also writes `pedestal_drift_time_blocks.csv` to audit within-run time-block behavior.

Pedestal drift summary: median `|d|` = 17.000 ADC, p90 `|d|` = 371.650 ADC, high-drift threshold = 38.500 ADC.

Synthetic pedestal perturbation negatives add a constant offset before renormalizing each waveform. The median shape L2 shifts are:

| perturbation ADC | median L2 | p95 L2 | high-drift median | low-drift median |
|---:|---:|---:|---:|---:|
| -150.0 | 0.034817 | 0.125894 | 0.048188 | 0.033003 |
| 150.0 | 0.031662 | 0.099098 | 0.042821 | 0.030128 |

Held-out high-minus-low pedestal-drift proxy shifts use the same run-block bootstrap as the AUC intervals. Timing, energy, and PID proxies are centered by run/stave before differencing so the table emphasizes residual within-run shifts rather than absolute run calibration offsets.

| proxy | high-minus-low median shift | 95% CI | held-out positives |
|---|---:|---:|---:|
| shape-distance stability | 0.114000 | [0.103666, 0.122816] | 2,038 |
| timing residual | -3.261087 | [-3.457566, -2.977910] | 2,038 |
| energy calibration proxy | -0.091885 | [-0.102548, -0.079045] | 2,038 |
| PID score proxy | -1511.625000 | [-1657.512500, -1361.665625] | 2,038 |

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
| 1 | traditional_fisher_gatti_all_features | fisher_gatti_engineered_features | 0.8940 | [0.8651, 0.9151] | 0.8517 |
| 2 | traditional_scalar__early_0_4_over_total | charge_comparison_psd | 0.8892 | [0.8599, 0.9125] | 0.8415 |
| 3 | traditional_scalar__late_minus_early_asym | charge_comparison_psd | 0.8724 | [0.8449, 0.8962] | 0.8276 |
| 4 | traditional_scalar__cfd20_time | constant_fraction_shape_ratios | 0.8700 | [0.8396, 0.8916] | 0.8332 |
| 5 | traditional_scalar__mean_time | mean_time_moments | 0.8685 | [0.8417, 0.8891] | 0.8188 |
| 6 | traditional_gatti_waveform | current_integration_gatti | 0.8677 | [0.8392, 0.8912] | 0.8154 |
| 7 | traditional_scalar__cfd50_time | constant_fraction_shape_ratios | 0.8676 | [0.8448, 0.8889] | 0.8275 |
| 8 | traditional_scalar__tail_10_17_over_total | charge_comparison_psd | 0.8643 | [0.8392, 0.8874] | 0.8056 |
| 9 | traditional_scalar__haar_l3_d00 | wavelet_haar | 0.8630 | [0.8328, 0.8869] | 0.7977 |
| 10 | traditional_scalar__matched_template_delta_chi2 | matched_filter_template_chi2 | 0.8608 | [0.8330, 0.8844] | 0.7951 |
| 11 | traditional_scalar__tail_12_17_over_total | charge_comparison_psd | 0.8517 | [0.8261, 0.8751] | 0.7885 |
| 12 | traditional_scalar__peak_sample | traditional_scalar | 0.8479 | [0.8172, 0.8681] | 0.7366 |
| 13 | traditional_scalar__tail_14_17_over_total | charge_comparison_psd | 0.8391 | [0.8115, 0.8641] | 0.7755 |
| 14 | traditional_scalar__final_sample | traditional_scalar | 0.8340 | [0.8064, 0.8606] | 0.7786 |
| 15 | traditional_scalar__haar_l1_d01 | wavelet_haar | 0.8138 | [0.7745, 0.8480] | 0.6531 |

## ML/NN comparison

Ridge, gradient-boosted trees, and MLP receive the normalized waveform, all traditional engineered features, and stave one-hot indicators. The 1D-CNN and the new transformer-style sequence encoder receive the normalized waveform plus stave one-hot indicators. The new sequence encoder is implemented as a compact residual squeeze temporal mixer: for these 18-sample waveforms it supplies the transformer-like ingredients that are sensible at this scale, namely learned local token mixing, global average/max sequence pooling, and a channel-wise squeeze gate, without the underconstrained parameter count of a full multi-head attention stack.

| model | inputs | fit details |
|---|---|---|
| Ridge classifier | waveform + traditional features + stave one-hot | standardized linear ridge classifier, class-balanced loss |
| Gradient-boosted trees | waveform + traditional features + stave one-hot | histogram GBT, 80 boosting iterations, depth constrained by 15 leaves |
| MLP | waveform + traditional features + stave one-hot | standardized 64-32 ReLU network with early stopping |
| 1D-CNN | waveform + stave one-hot | two temporal convolutions with global average pooling |
| Transformer-style sequence encoder | waveform + stave one-hot | compact residual token mixer, squeeze gate, average/max sequence pooling |

| method | role | AUC | 95% CI | AP | rows | positives |
|---|---|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | ml_panel | 0.9568 | [0.9351, 0.9719] | 0.9272 | 9,745 | 2,038 |
| NN_transformer_sequence_encoder_new | ml_panel | 0.9146 | [0.8918, 0.9322] | 0.8703 | 9,745 | 2,038 |
| ML_mlp | ml_panel | 0.9072 | [0.8822, 0.9261] | 0.8656 | 9,745 | 2,038 |
| ML_ridge_classifier | ml_panel | 0.8985 | [0.8743, 0.9197] | 0.8501 | 9,745 | 2,038 |
| traditional_fisher_gatti_all_features | traditional_multivariate | 0.8940 | [0.8651, 0.9151] | 0.8517 | 9,745 | 2,038 |
| NN_1d_cnn | ml_panel | 0.7099 | [0.6889, 0.7332] | 0.5822 | 9,745 | 2,038 |

## Per-run behavior

| method | mean per-run AUC | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0.9532 | 0.9086 | 0.9798 | 8 |
| ML_mlp | 0.9006 | 0.8522 | 0.9468 | 8 |
| ML_ridge_classifier | 0.8916 | 0.8483 | 0.9447 | 8 |
| NN_1d_cnn | 0.7086 | 0.6681 | 0.7675 | 8 |
| NN_transformer_sequence_encoder_new | 0.9085 | 0.8574 | 0.9466 | 8 |
| traditional_fisher_gatti_all_features | 0.8875 | 0.8443 | 0.9407 | 8 |

## Systematics and caveats

- The target is weak and pedestal-defined; it validates pedestal-shape coupling, not particle truth.
- The target uses the same pre-trigger samples that are subtracted from the waveform. Any residual predictability after run-heldout splitting is evidence against perfect shape invariance, but it does not by itself identify the physical source of coupling.
- Run-heldout splitting protects against random-row leakage, but the eight held-out runs are still finite; CIs are run-block bootstraps, not independent-event CIs.
- Amplitude and stave are included as context in supervised ML matrices because pedestal drift can couple to energy and PID proxy shifts; scalar traditional rows remain interpretable shape-only checks except where explicitly named otherwise.
- Neural nets were intentionally small because the waveform has only 18 samples; larger architectures would be underconstrained without an external truth target.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner. The best traditional method is **traditional_fisher_gatti_all_features**. On this pedestal-drift invariance benchmark, the strongest ML/NN model beats the traditional baseline within the run-bootstrap CI structure.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s25b_1783775623_7070_7bfe60c5_pedestal_nonstationarity_audit.py --config configs/s25b_1783775623_7070_7bfe60c5_pedestal_nonstationarity_audit.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `pedestal_drift_by_run.csv`, `pedestal_drift_time_blocks.csv`, `pedestal_perturbation_negative_controls.csv`, `proxy_shift_bootstrap_cis.csv`, `traditional_method_summary.csv`, `primary_method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, and this report.

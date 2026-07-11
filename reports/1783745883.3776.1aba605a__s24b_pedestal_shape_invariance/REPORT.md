# S24B: pedestal drift and waveform-shape invariance benchmark

**Ticket:** `1783745883.3776.1aba605a`  
**Worker:** `testbeam-laptop-4`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study isolates selected-pulse pedestal drift from corrected 18-sample B-stave pulse shape. The concrete weak-label task is high pedestal drift: pulses whose pre-trigger baseline deviates strongly from the run/stave median are positive. Traditional pulse-shape statistics are benchmarked against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a new residual squeeze CNN under run-heldout validation. The winner by held-out ROC AUC is **ML_gradient_boosted_trees** with AUC **0.9484** [0.9248, 0.9644].

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
| train | 25,493 | 5,009 | 0.1965 |
| heldout | 9,745 | 2,060 | 0.2114 |
| all | 35,238 | 7,069 | 0.2006 |

Held-out runs were `42, 50, 57, 58, 60, 62, 64, 65`; all model fitting used the other runs. Confidence intervals are 95% nonparametric bootstraps over held-out runs.

The benchmark sample is stratified by `(run, stave)` with a cap of `max_per_run_stave` records per cell, so no high-statistics run can dominate the model fit or the held-out evaluation. If `R` is the held-out run set and `AUC(D)` is the pooled ROC AUC on rows `D`, each bootstrap replicate draws `|R|` runs with replacement, pools their rows, and records `AUC_b = AUC(union_{r in R_b} D_r)`. The reported CI is the 2.5% and 97.5% quantile of `{AUC_b}`. The script also writes `pedestal_drift_time_blocks.csv` to audit within-run time-block behavior.

Pedestal drift summary: median `|d|` = 17.250 ADC, p90 `|d|` = 375.300 ADC, high-drift threshold = 38.250 ADC.

Synthetic pedestal perturbation negatives add a constant offset before renormalizing each waveform. The median shape L2 shifts are:

| perturbation ADC | median L2 | p95 L2 | high-drift median | low-drift median |
|---:|---:|---:|---:|---:|
| -150.0 | 0.034757 | 0.124138 | 0.047257 | 0.033000 |
| 150.0 | 0.031619 | 0.096848 | 0.042094 | 0.030121 |

Held-out high-minus-low pedestal-drift proxy shifts use the same run-block bootstrap as the AUC intervals. Timing, energy, and PID proxies are centered by run/stave before differencing so the table emphasizes residual within-run shifts rather than absolute run calibration offsets.

| proxy | high-minus-low median shift | 95% CI | held-out positives |
|---|---:|---:|---:|
| shape-distance stability | 0.117121 | [0.103427, 0.127212] | 2,060 |
| timing residual | -3.240899 | [-3.557435, -2.870984] | 2,060 |
| energy calibration proxy | -0.090259 | [-0.100679, -0.079838] | 2,060 |
| PID score proxy | -1545.625000 | [-1645.381250, -1424.031250] | 2,060 |

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
| 1 | traditional_fisher_gatti_all_features | fisher_gatti_engineered_features | 0.8878 | [0.8585, 0.9070] | 0.8437 |
| 2 | traditional_scalar__early_0_4_over_total | charge_comparison_psd | 0.8800 | [0.8531, 0.9014] | 0.8324 |
| 3 | traditional_scalar__late_minus_early_asym | charge_comparison_psd | 0.8643 | [0.8378, 0.8839] | 0.8189 |
| 4 | traditional_scalar__cfd20_time | constant_fraction_shape_ratios | 0.8612 | [0.8297, 0.8808] | 0.8241 |
| 5 | traditional_scalar__mean_time | mean_time_moments | 0.8607 | [0.8256, 0.8831] | 0.8100 |
| 6 | traditional_gatti_waveform | current_integration_gatti | 0.8602 | [0.8271, 0.8812] | 0.8097 |
| 7 | traditional_scalar__cfd50_time | constant_fraction_shape_ratios | 0.8578 | [0.8312, 0.8769] | 0.8169 |
| 8 | traditional_scalar__matched_template_delta_chi2 | matched_filter_template_chi2 | 0.8570 | [0.8242, 0.8786] | 0.7929 |
| 9 | traditional_scalar__tail_10_17_over_total | charge_comparison_psd | 0.8565 | [0.8282, 0.8776] | 0.7967 |
| 10 | traditional_scalar__haar_l3_d00 | wavelet_haar | 0.8544 | [0.8248, 0.8737] | 0.7927 |
| 11 | traditional_scalar__tail_12_17_over_total | charge_comparison_psd | 0.8443 | [0.8134, 0.8687] | 0.7785 |
| 12 | traditional_scalar__peak_sample | traditional_scalar | 0.8396 | [0.8139, 0.8584] | 0.7291 |
| 13 | traditional_scalar__tail_14_17_over_total | charge_comparison_psd | 0.8307 | [0.8006, 0.8576] | 0.7657 |
| 14 | traditional_scalar__final_sample | traditional_scalar | 0.8293 | [0.7974, 0.8574] | 0.7721 |
| 15 | traditional_scalar__haar_l1_d01 | wavelet_haar | 0.8021 | [0.7644, 0.8331] | 0.6573 |

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
| ML_gradient_boosted_trees | ml_panel | 0.9484 | [0.9248, 0.9644] | 0.9204 | 9,745 | 2,060 |
| ML_mlp | ml_panel | 0.9181 | [0.8908, 0.9379] | 0.8813 | 9,745 | 2,060 |
| NN_residual_squeeze_cnn_new | ml_panel | 0.9062 | [0.8795, 0.9233] | 0.8632 | 9,745 | 2,060 |
| ML_ridge_classifier | ml_panel | 0.8926 | [0.8686, 0.9107] | 0.8427 | 9,745 | 2,060 |
| traditional_fisher_gatti_all_features | traditional_multivariate | 0.8878 | [0.8585, 0.9070] | 0.8437 | 9,745 | 2,060 |
| NN_1d_cnn | ml_panel | 0.7071 | [0.6771, 0.7338] | 0.5702 | 9,745 | 2,060 |

## Per-run behavior

| method | mean per-run AUC | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 0.9450 | 0.8845 | 0.9754 | 8 |
| ML_mlp | 0.9130 | 0.8529 | 0.9614 | 8 |
| ML_ridge_classifier | 0.8861 | 0.8308 | 0.9269 | 8 |
| NN_1d_cnn | 0.7044 | 0.6480 | 0.7607 | 8 |
| NN_residual_squeeze_cnn_new | 0.8999 | 0.8269 | 0.9391 | 8 |
| traditional_fisher_gatti_all_features | 0.8816 | 0.8132 | 0.9195 | 8 |

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
/home/billy/anaconda3/bin/python scripts/s24b_1783745883_3776_1aba605a_pedestal_shape_invariance.py --config configs/s24b_1783745883_3776_1aba605a_pedestal_shape_invariance.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `pedestal_drift_by_run.csv`, `pedestal_drift_time_blocks.csv`, `pedestal_perturbation_negative_controls.csv`, `proxy_shift_bootstrap_cis.csv`, `traditional_method_summary.csv`, `primary_method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, and this report.

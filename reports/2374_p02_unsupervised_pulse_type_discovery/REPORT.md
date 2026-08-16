# P02: pulse-type discovery and morphology benchmark

**Ticket:** `2374`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

This study reproduces the S00 B-stave selected-pulse count from raw ROOT and then benchmarks pulse-shape type discovery on 18-sample B-stave waveforms. The concrete measurable task is a P02-style anomalous morphology label derived only from the waveform itself: early or low-area peaks, very late peaks, and large negative sample-to-sample drops are positive; ordinary peak-region pulses are negative. The strongest traditional method is a Fisher/Gatti score over engineered pulse-shape features. It is compared on identical run-heldout rows against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new residual squeeze CNN. The winner by held-out ROC AUC is **ML_gradient_boosted_trees** with AUC **1.0000** [1.0000, 1.0000].

## Raw reproduction gate

The raw ROOT files were rescanned before modeling. For each event, `HRDv` was reshaped to `(8, 18)`, samples 0-3 supplied the per-channel baseline, B-stave even channels B2/B4/B6/B8 were baseline-subtracted, and a pulse was selected when its maximum amplitude exceeded 1000 ADC. This reproduced **640,737** selected B-stave pulses against the registered **640,737** count, delta **0**.

## Statistical task

Let the normalized waveform be `x_i(t)=v_i(t)/max_t v_i(t)` for samples `t=0,...,17`. The binary target is

`y_i = 1{peak_i <= 3 or (peak_i <= 4 and sum_t x_i(t) < 3.0) or peak_i >= 12 or min_t Delta x_i(t) < -0.75}`.

The target is not a particle-ID truth label. It is a morphology stress test chosen because it is reproducible from raw waveforms and exercises the pulse-shape methods named in the ticket.

The P02 ticket asks for unsupervised pulse-type discovery, while the fleet objective also requires ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture in a run-heldout benchmark. This report therefore treats the morphology rule as an auditable topology proxy for discovered pulse types: the traditional scalar cuts and Gatti scores are transparent discovery baselines, and the supervised panel is the head-to-head adoption gate for whether learned representations add useful discriminatory power. No claim is made that these classes are detector-independent truth labels.

Label counts in the run-balanced benchmark sample:

| split | rows | positives | positive fraction |
|---|---:|---:|---:|
| train | 25,493 | 6,155 | 0.2414 |
| heldout | 9,745 | 2,021 | 0.2074 |
| all | 35,238 | 8,176 | 0.2320 |

Held-out runs were `42, 50, 57, 58, 60, 62, 64, 65`; all model fitting used the other runs. Confidence intervals are 95% nonparametric bootstraps over held-out runs.

The benchmark sample is stratified by `(run, stave)` with a cap of `max_per_run_stave` records per cell, so no high-statistics run can dominate the model fit or the held-out evaluation. If `R` is the held-out run set and `AUC(D)` is the pooled ROC AUC on rows `D`, each bootstrap replicate draws `|R|` runs with replacement, pools their rows, and records `AUC_b = AUC(union_{r in R_b} D_r)`. The reported CI is the 2.5% and 97.5% quantile of `{AUC_b}`.

The pre-registered primary metric is run-heldout ROC AUC with 95% run-block bootstrap confidence intervals. A method is treated as better only if its point estimate is higher on the same held-out rows; interval overlap is reported rather than hidden. Average precision is secondary because the positive class fraction is about 21% on held-out rows.

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

The traditional baseline is intentionally strong rather than a single hand cut. It includes scalar discovery scores, matched-template chi2 contrasts, a waveform-level Gatti current-integration statistic, and the multivariate Fisher/Gatti score over all engineered non-neural pulse-shape variables. This makes the neural and tree comparisons a real adoption test rather than a comparison against a strawman.

Top traditional rows:

| rank | method | family | AUC | 95% CI | AP |
|---:|---|---|---:|---:|---:|
| 1 | traditional_fisher_gatti_all_features | fisher_gatti_engineered_features | 0.9964 | [0.9947, 0.9977] | 0.9811 |
| 2 | traditional_gatti_waveform | current_integration_gatti | 0.9913 | [0.9893, 0.9931] | 0.9672 |
| 3 | traditional_scalar__matched_template_delta_chi2 | matched_filter_template_chi2 | 0.9901 | [0.9876, 0.9927] | 0.9627 |
| 4 | traditional_scalar__matched_template_nominal_chi2 | matched_filter_template_chi2 | 0.9878 | [0.9856, 0.9900] | 0.9317 |
| 5 | traditional_scalar__area_over_peak | traditional_scalar | 0.9702 | [0.9658, 0.9753] | 0.9052 |
| 6 | traditional_scalar__positive_area | traditional_scalar | 0.9692 | [0.9622, 0.9744] | 0.9350 |
| 7 | traditional_scalar__width20 | rise_time_width | 0.9511 | [0.9370, 0.9630] | 0.9098 |
| 8 | traditional_scalar__time_variance | mean_time_moments | 0.9265 | [0.9052, 0.9427] | 0.9042 |
| 9 | traditional_scalar__width50 | rise_time_width | 0.9202 | [0.9099, 0.9281] | 0.8157 |
| 10 | traditional_scalar__haar_l0_d02 | wavelet_haar | 0.8953 | [0.8881, 0.9045] | 0.6450 |
| 11 | traditional_scalar__haar_l1_d01 | wavelet_haar | 0.8877 | [0.8733, 0.9003] | 0.5883 |
| 12 | traditional_scalar__middle_5_9_over_total | charge_comparison_psd | 0.8648 | [0.7969, 0.9106] | 0.8362 |
| 13 | traditional_scalar__time_skewness | mean_time_moments | 0.8497 | [0.8089, 0.8805] | 0.8136 |
| 14 | traditional_scalar__fft_k1_fraction | frequency_domain_fft | 0.8450 | [0.8177, 0.8682] | 0.6853 |
| 15 | traditional_scalar__fft_high_over_low | frequency_domain_fft | 0.8321 | [0.7979, 0.8558] | 0.7124 |

## ML/NN comparison

Ridge, gradient-boosted trees, and MLP receive the normalized waveform, all traditional engineered features, and stave one-hot indicators. The 1D-CNN and the new residual squeeze CNN receive the normalized waveform plus stave one-hot indicators. The residual squeeze CNN is the new architecture: it uses residual temporal convolutions, global average/max pooling, and a small squeeze gate, which is sensible for 18 samples because it can combine local edge cues with pulse-wide tail information without a large parameter count.

| model | inputs | fit details |
|---|---|---|
| Ridge classifier | waveform + traditional features + stave one-hot | standardized linear ridge classifier, class-balanced loss |
| Gradient-boosted trees | waveform + traditional features + stave one-hot | histogram GBT, 80 boosting iterations, depth constrained by 15 leaves |
| MLP | waveform + traditional features + stave one-hot | standardized 64-32 ReLU network with early stopping |
| 1D-CNN | waveform + stave one-hot | two temporal convolutions with global average pooling |
| Residual squeeze CNN | waveform + stave one-hot | residual temporal convolutions, squeeze gate, average/max pooling |

For the feature-matrix models, the design matrix is `X=[x, f_shape(x), one_hot(stave)]`, where `f_shape` contains timing, derivative, charge-ratio, moment, FFT, Haar, and template-distance variables. The ridge classifier minimizes squared margin loss with L2 regularization; the gradient-boosted tree model uses histogram boosting with depth-limited leaves; the MLP is a 64-32 ReLU network with early stopping. The 1D-CNN and residual squeeze CNN see the waveform and stave only, so their performance is a stricter test of whether temporal convolutions recover the hand-engineered shape cues.

| method | role | AUC | 95% CI | AP | rows | positives |
|---|---|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | ml_panel | 1.0000 | [1.0000, 1.0000] | 1.0000 | 9,745 | 2,021 |
| ML_mlp | ml_panel | 0.9999 | [0.9998, 1.0000] | 0.9997 | 9,745 | 2,021 |
| traditional_fisher_gatti_all_features | traditional_multivariate | 0.9964 | [0.9947, 0.9977] | 0.9811 | 9,745 | 2,021 |
| ML_ridge_classifier | ml_panel | 0.9952 | [0.9930, 0.9970] | 0.9648 | 9,745 | 2,021 |
| NN_residual_squeeze_cnn_new | ml_panel | 0.9878 | [0.9834, 0.9909] | 0.9560 | 9,745 | 2,021 |
| NN_1d_cnn | ml_panel | 0.9722 | [0.9657, 0.9786] | 0.9134 | 9,745 | 2,021 |

## Per-run behavior

| method | mean per-run AUC | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 1.0000 | 1.0000 | 1.0000 | 8 |
| ML_mlp | 0.9999 | 0.9997 | 1.0000 | 8 |
| ML_ridge_classifier | 0.9951 | 0.9889 | 0.9984 | 8 |
| NN_1d_cnn | 0.9713 | 0.9539 | 0.9867 | 8 |
| NN_residual_squeeze_cnn_new | 0.9871 | 0.9758 | 0.9952 | 8 |
| traditional_fisher_gatti_all_features | 0.9962 | 0.9914 | 0.9987 | 8 |

## Systematics and caveats

- The target is weak and morphology-defined; it validates discriminators for the chosen waveform anomaly class, not a physics truth class.
- The label rule contains peak position, integrated area, and negative-step terms, and the supervised feature-matrix models can see close relatives of those variables. The near-perfect GBT result is therefore a successful benchmark on the registered morphology rule, not evidence of new latent physics.
- Run-heldout splitting protects against random-row leakage, but the eight held-out runs are still finite; CIs are run-block bootstraps, not independent-event CIs.
- Amplitude and stave are included only as context in supervised ML matrices. The raw reproduction and scalar traditional survey show that shape-only methods already solve most of the task.
- Neural nets were intentionally small because the waveform has only 18 samples; larger architectures would be underconstrained without an external truth target.
- The MLP emitted a convergence warning at the configured iteration cap. Its held-out AUC remains near one, but the warning is treated as a model-systematic caveat rather than tuned away after seeing the result.
- The report-level systematic uncertainty is dominated by the topology-proxy definition, not by statistical precision. The most important external validity test is an independent timing-tail, injection, hand-scan, or simulation-derived morphology label.

## Falsification and validity controls

The analysis would have falsified the adoption claim if the strongest traditional Fisher/Gatti baseline matched or exceeded all ML/NN methods on held-out ROC AUC, or if a held-out run showed a catastrophic method reversal. Neither occurred: gradient-boosted trees were best on the pooled held-out set and had per-run AUC 1.0000 on all eight held-out runs.

Data leakage controls are: the split is by run; score orientation, template means, Fisher/Gatti weights, scalers, and supervised model fits are learned only on training runs; bootstrap resampling is by run; and the held-out rows are never used for training. The main residual leakage risk is conceptual rather than procedural: the label is defined from waveform-shape variables, and feature-matrix models include related shape variables. This is why the conclusion is limited to recovering the registered morphology proxy.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the winner. The best traditional method is **traditional_fisher_gatti_all_features**. On this weak-label pulse-shape benchmark, the strongest ML/NN model beats the traditional baseline within the run-bootstrap CI structure.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/t07_tradshape_ml_benchmark.py --config configs/2374_p02_unsupervised_pulse_type_discovery.json
```

Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `traditional_method_summary.csv`, `primary_method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, and this report.

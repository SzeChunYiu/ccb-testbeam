# S31a Frequency-Domain Pulse-Shape Timing PID Benchmark

**Ticket:** `1783882773.37910.7224325e`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT directory:** `data/root/root`

## Abstract

This study rescans the B-stack raw ROOT files and benchmarks a strong traditional Fourier/wavelet/matched-filter/constant-fraction feature set against ridge, gradient-boosted trees, an MLP, a 1D-CNN, and a new compact spectral transformer. The selected-pulse reproduction is exact: **640,737** selected B-stave pulses versus the registered **640,737** count. Across the seven endpoint proxies, the overall winner by endpoint-win count is **ML_gradient_boosted_trees**.

## Raw ROOT Reproduction

For each configured run, `h101/HRDv` is reshaped to `(8,18)`. Samples 0-3 define a channel pedestal, B-stave even channels B2/B4/B6/B8 are baseline-subtracted, and a selected pulse is counted when the maximum corrected amplitude exceeds 1000 ADC.

| quantity | expected | reproduced | delta |
|---|---:|---:|---:|
| selected B-stave pulses | 640,737 | 640,737 | 0 |

## Split and Bootstrap

Rows are sampled with a cap per `(run, stave)` cell before modeling. Runs `42, 50, 57, 58, 60, 62, 64, 65` are held out completely. For metric `m`, bootstrap replicate `b` samples held-out runs with replacement and recomputes `m_b`; the quoted interval is `[Q_0.025(m_b), Q_0.975(m_b)]`. This estimates run-to-run stability rather than event-only precision.

Formally, with held-out run blocks `D_r`, the reported point estimate is `m(union_r D_r)`. Bootstrap replicate `b` draws `R` run labels with replacement from the held-out set and computes `m_b=m(union_{r in S_b} D_r)`. Classification endpoints use ROC AUC, with average precision listed as a secondary positive-class metric. Regression endpoints report `sigma68 = 0.5 [Q_0.84(yhat-y)-Q_0.16(yhat-y)]`, so lower is better.

## Endpoint Definitions

| endpoint | kind | metric | definition |
|---|---|---|---|
| pulse_shape_harmonics | classification | roc_auc | top-quartile high-frequency FFT power fraction after removing waveform mean |
| timing_residual | regression | sigma68 | CFD50 time minus run/stave median CFD50 time |
| pileup_sideband | classification | roc_auc | top-quintile late-tail plus negative-step sideband score |
| saturation_clipping | classification | roc_auc | high-amplitude or flat-top pulse proxy for ADC clipping/saturation |
| pedestal_noise_color | classification | roc_auc | top-quintile run/stave pedestal residual plus early-late color proxy |
| energy_scale | regression | sigma68 | log-amplitude energy proxy minus run/stave median |
| pid_separation | classification | roc_auc | median-split duplicate-readout response ratio with low-order harmonic context; PID proxy, not truth PID |

These are waveform-derived endpoint proxies because no independent truth PID, pile-up, saturation, or pedestal-noise labels are present in the reduced raw ROOT branch used here. The PID endpoint is therefore a duplicate-readout response proxy, not a particle-species truth label.

## Methods

Let `x_i(t)` be the pedestal-subtracted waveform normalized by peak amplitude. The traditional feature set contains CFD crossing times, rise widths, late/early charge ratios, derivative extrema, Gatti/template scores, Haar coefficients, and FFT harmonic ratios. Its multivariate estimator is a regularized linear matched discriminator for classification and a robust Huber model for regression.

The main derived quantities are: `H_i=sum_{k>=4}|FFT(x_i-mean(x_i))_k| / sum_{k>=1}|FFT(x_i-mean(x_i))_k|` for harmonic content; `t_CFD(f)=t_j+(fA-x_j)/(x_{j+1}-x_j)` for constant-fraction time; `P_i=0.55 tail_i+0.45 max(-Delta x_i)` for the pile-up sideband; and `E_i=log(1+A_i)-median_{run,stave} log(1+A)` for the energy-scale proxy. The matched-template component uses `chi2_c(i)=mean_t [x_i(t)-mu_c(t)]^2`, where `mu_c` is estimated on training runs only.

For ridge models, classification minimizes an L2-regularized margin loss and regression minimizes `||y-X beta||_2^2 + lambda ||beta||_2^2`. Gradient-boosted trees fit additive shallow trees `F_M(x)=sum_m eta h_m(x)`. The MLP is a two-hidden-layer ReLU network. The 1D-CNN uses local temporal convolutions. The new spectral transformer embeds `(sample, time)` tokens with a one-layer self-attention encoder and gates the representation with normalized FFT magnitudes, which is specifically matched to the frequency-domain ticket.

All supervised estimators are fit on the same training runs. Thresholds that define high-side classification endpoints are fixed from the training runs before held-out scoring, so held-out labels do not tune the decision boundary. The traditional estimator sees only engineered Fourier/wavelet/CFD/template variables; ridge, GBT, and MLP see those variables plus the normalized waveform and stave one-hot indicators; CNN and spectral-transformer methods see the normalized waveform and stave one-hot indicators.

## Primary Results

| endpoint | winner | metric | 95% CI | next best traditional |
|---|---|---:|---:|---|
| pulse_shape_harmonics | ML_gradient_boosted_trees | 0.99998 | [0.99996, 0.99999] | 0.98857 [0.98340, 0.99277] |
| timing_residual | ML_gradient_boosted_trees | 0.39014 | [0.33948, 0.44029] | 0.40535 [0.33212, 0.49426] |
| pileup_sideband | ML_gradient_boosted_trees | 0.99998 | [0.99996, 1.00000] | 0.99947 [0.99892, 0.99984] |
| saturation_clipping | ML_gradient_boosted_trees | 0.99884 | [0.99762, 0.99955] | 0.89526 [0.82662, 0.94066] |
| pedestal_noise_color | ML_gradient_boosted_trees | 0.94860 | [0.92403, 0.96323] | 0.88455 [0.85915, 0.90728] |
| energy_scale | ML_gradient_boosted_trees | 0.10207 | [0.07213, 0.15249] | 0.12700 [0.10989, 0.14177] |
| pid_separation | ML_gradient_boosted_trees | 0.99939 | [0.99920, 0.99959] | 0.99346 [0.99192, 0.99483] |

Complete method table:

| endpoint | method | metric | 95% CI | AP/positives |
|---|---|---:|---:|---:|
| pulse_shape_harmonics | ML_gradient_boosted_trees | 0.99998 | [0.99996, 0.99999] | 0.99993 |
| pulse_shape_harmonics | ML_ridge | 0.98858 | [0.98418, 0.99239] | 0.95894 |
| pulse_shape_harmonics | traditional_fourier_wavelet_cfd_matched | 0.98857 | [0.98340, 0.99277] | 0.95832 |
| pulse_shape_harmonics | ML_mlp | 0.96988 | [0.96202, 0.97597] | 0.92986 |
| pulse_shape_harmonics | NN_spectral_transformer_new | 0.85407 | [0.81466, 0.88201] | 0.72412 |
| pulse_shape_harmonics | NN_1d_cnn | 0.84766 | [0.79909, 0.87467] | 0.59252 |
| timing_residual | ML_gradient_boosted_trees | 0.39014 | [0.33948, 0.44029] |  |
| timing_residual | traditional_fourier_wavelet_cfd_matched | 0.40535 | [0.33212, 0.49426] |  |
| timing_residual | ML_mlp | 0.42118 | [0.35411, 0.46446] |  |
| timing_residual | ML_ridge | 0.43412 | [0.35964, 0.46838] |  |
| timing_residual | NN_spectral_transformer_new | 1.31534 | [1.06224, 1.60294] |  |
| timing_residual | NN_1d_cnn | 2.25353 | [1.58274, 2.78869] |  |
| pileup_sideband | ML_gradient_boosted_trees | 0.99998 | [0.99996, 1.00000] | 0.99991 |
| pileup_sideband | traditional_fourier_wavelet_cfd_matched | 0.99947 | [0.99892, 0.99984] | 0.99623 |
| pileup_sideband | ML_ridge | 0.99946 | [0.99900, 0.99983] | 0.99627 |
| pileup_sideband | ML_mlp | 0.99313 | [0.98913, 0.99612] | 0.97347 |
| pileup_sideband | NN_spectral_transformer_new | 0.98575 | [0.98150, 0.98998] | 0.93123 |
| pileup_sideband | NN_1d_cnn | 0.96007 | [0.95387, 0.96684] | 0.71415 |
| saturation_clipping | ML_gradient_boosted_trees | 0.99884 | [0.99762, 0.99955] | 0.98770 |
| saturation_clipping | ML_ridge | 0.89965 | [0.83427, 0.93504] | 0.67132 |
| saturation_clipping | traditional_fourier_wavelet_cfd_matched | 0.89526 | [0.82662, 0.94066] | 0.67504 |
| saturation_clipping | ML_mlp | 0.79703 | [0.68060, 0.88345] | 0.59473 |
| saturation_clipping | NN_1d_cnn | 0.78049 | [0.63941, 0.87505] | 0.54205 |
| saturation_clipping | NN_spectral_transformer_new | 0.77824 | [0.65998, 0.84806] | 0.18576 |
| pedestal_noise_color | ML_gradient_boosted_trees | 0.94860 | [0.92403, 0.96323] | 0.91536 |
| pedestal_noise_color | ML_ridge | 0.88616 | [0.86394, 0.90808] | 0.83234 |
| pedestal_noise_color | traditional_fourier_wavelet_cfd_matched | 0.88455 | [0.85915, 0.90728] | 0.82942 |
| pedestal_noise_color | ML_mlp | 0.84996 | [0.82390, 0.86943] | 0.75136 |
| pedestal_noise_color | NN_spectral_transformer_new | 0.79083 | [0.76949, 0.80955] | 0.67672 |
| pedestal_noise_color | NN_1d_cnn | 0.68403 | [0.66276, 0.70693] | 0.53333 |
| energy_scale | ML_gradient_boosted_trees | 0.10207 | [0.07213, 0.15249] |  |
| energy_scale | ML_mlp | 0.11575 | [0.08731, 0.15127] |  |
| energy_scale | traditional_fourier_wavelet_cfd_matched | 0.12700 | [0.10989, 0.14177] |  |
| energy_scale | ML_ridge | 0.14065 | [0.09101, 0.20396] |  |
| energy_scale | NN_spectral_transformer_new | 0.27637 | [0.24262, 0.31134] |  |
| energy_scale | NN_1d_cnn | 0.35517 | [0.32154, 0.39480] |  |
| pid_separation | ML_gradient_boosted_trees | 0.99939 | [0.99920, 0.99959] | 0.99958 |
| pid_separation | traditional_fourier_wavelet_cfd_matched | 0.99346 | [0.99192, 0.99483] | 0.99566 |
| pid_separation | ML_ridge | 0.99261 | [0.99107, 0.99419] | 0.99494 |
| pid_separation | ML_mlp | 0.98606 | [0.98221, 0.99043] | 0.98436 |
| pid_separation | NN_spectral_transformer_new | 0.75687 | [0.74816, 0.76621] | 0.78785 |
| pid_separation | NN_1d_cnn | 0.72454 | [0.70080, 0.74736] | 0.72829 |

## Systematics and Caveats

- Endpoint labels are deterministic proxies from the same waveforms, so absolute AUC values can be optimistic when a model observes variables close to the label definition.
- Run-held-out splitting prevents random-row leakage but cannot create missing external truth. The PID and pile-up results should be interpreted as stability of waveform-response proxies.
- The raw ROOT reproduction is exact for the selected-pulse count; it does not by itself validate the physics labels.
- Neural models are deliberately compact because each pulse has only 18 samples and the finite held-out run set limits reliable high-capacity training.
- Regression endpoints report sigma68 of residuals. For energy scale this is a log-amplitude proxy, not a calibrated GeV response.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as the overall winner by endpoint-win count. Endpoint-specific winners remain more informative than a single aggregate: the table above records which method wins each physics proxy and where the traditional Fourier/wavelet/CFD baseline is already competitive.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s31a_1783882773_37910_7224325e_frequency_domain_pulse_timing_pid_benchmark.py --config configs/s31a_1783882773_37910_7224325e_frequency_domain_pulse_timing_pid_benchmark.json
```


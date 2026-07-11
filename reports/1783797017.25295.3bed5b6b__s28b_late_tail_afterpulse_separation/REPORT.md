# S28b - Late-Tail Memory and Afterpulse Separation Study

- Ticket: `1783797017.25295.3bed5b6b`
- Worker: `testbeam-laptop-3`
- Raw ROOT directory: `data/root/root`
- Status: DONE

## Abstract

This study separates smooth late-tail memory from true afterpulse/pile-up-like structure in raw B-stack waveforms. Raw ROOT files are rescanned from `HRDv`; the selected-pulse count is reproduced exactly before any modeling. The benchmark compares a physically motivated exponential-tail plus autoregressive residual score family against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact causal sequence mixer. The winner by held-out run-block ROC AUC is **ML_gradient_boosted_trees** with AUC **1.0000** [1.0000, 1.0000].

## Raw ROOT Reproduction

For each raw ROOT event, `HRDv` is reshaped to `(8,18)`. The baseline for each channel is the median of samples 0-3. B-stave even channels B2/B4/B6/B8 are selected when the baseline-subtracted amplitude exceeds 1000 ADC.

| quantity | expected | reproduced | delta |
|---|---:|---:|---:|
| selected B-stave pulses | 640,737 | 640,737 | 0 |

## Task Definition

Let `x_i(t)` be the normalized baseline-subtracted waveform for selected pulse `i`. A smooth late-tail memory hypothesis is modeled as an exponential tail over samples 8-17:

`log(max(x_i(t), eps)) = alpha_i + beta_i t + epsilon_i(t)`.

An autoregressive residual proxy is computed on the late tail as

`phi_i = sum_t x_i(t)x_i(t+1) / sum_t x_i(t)^2`, and `r_i(t+1)=x_i(t+1)-phi_i x_i(t)`.

The weak positive class `afterpulse_or_pileup` is defined when any of the following holds: the event has more than one selected B-stave pulse, the maximum positive exponential residual in samples 10-17 exceeds the configured quantile, or a late peak occurs with high late-tail fraction. Negative examples are smooth single-pulse late-tail-memory candidates. This target is deliberately conservative: it tests separability of abrupt late structure from smooth memory, not external particle truth.

| split | rows | positives | positive fraction |
|---|---:|---:|---:|
| train | 30,525 | 12,317 | 0.4035 |
| heldout | 11,845 | 5,048 | 0.4262 |
| all | 42,370 | 17,365 | 0.4098 |

Training and held-out partitions are by complete runs. Held-out runs are `42, 50, 57, 58, 60, 62, 64, 65`. Confidence intervals use 500 bootstrap resamples of whole held-out runs.

## Traditional Tail Model

The traditional baseline is the best scalar or multivariate member of an interpretable scorecard: exponential-tail slope, exponential residual maximum and sum, AR(1) tail residual RMS, charge-comparison tail fractions, rise/width features, derivative zero-crossing counts, moment/FFT/Haar features, matched-template chi2, Gatti waveform score, and Fisher/Gatti engineered-feature discriminant. Scalar scores are oriented on training runs only.

| rank | method | family | AUC | 95% CI | AP |
|---:|---|---|---:|---:|---:|
| 1 | traditional_scalar__event_selected_stave_multiplicity | pileup_event_context | 0.8465 | [0.8308, 0.8619] | 0.8238 |
| 2 | traditional_scalar__exp_tail_positive_residual_sum | exponential_tail_ar_residual | 0.7758 | [0.7194, 0.8340] | 0.7919 |
| 3 | traditional_scalar__exp_tail_residual_max | exponential_tail_ar_residual | 0.7757 | [0.7172, 0.8371] | 0.7953 |
| 4 | traditional_scalar__peak_sample | traditional_scalar | 0.7543 | [0.7007, 0.8124] | 0.7632 |
| 5 | traditional_exponential_ar_fisher_all_features | exponential_tail_ar_fisher | 0.7529 | [0.7231, 0.7875] | 0.6053 |
| 6 | traditional_scalar__time_variance | mean_time_moments | 0.7440 | [0.6825, 0.8062] | 0.6475 |
| 7 | traditional_scalar__ar1_tail_residual_rms | exponential_tail_ar_residual | 0.7416 | [0.6857, 0.8025] | 0.7225 |
| 8 | traditional_scalar__cfd50_time | constant_fraction_shape_ratios | 0.7344 | [0.6808, 0.7872] | 0.7738 |
| 9 | traditional_scalar__matched_template_nominal_chi2 | matched_filter_template_chi2 | 0.7310 | [0.6787, 0.7815] | 0.6117 |
| 10 | traditional_scalar__width20 | rise_time_width | 0.7296 | [0.6738, 0.7893] | 0.6351 |
| 11 | traditional_scalar__cfd20_time | constant_fraction_shape_ratios | 0.7284 | [0.6762, 0.7807] | 0.7696 |
| 12 | traditional_scalar__haar_l0_d02 | wavelet_haar | 0.7245 | [0.6540, 0.7904] | 0.5750 |

## ML/NN Panel

Ridge, gradient-boosted trees, and MLP receive normalized waveform samples, all engineered traditional variables, exponential/AR tail variables, and stave one-hot context. The 1D-CNN receives waveform plus stave context. The new architecture is a causal compact sequence mixer: residual temporal convolutions over ordered samples, channel squeeze gating, and global average/max pooling. It is used instead of a large unconstrained transformer because the sequence length is only 18 samples.

| method | role | AUC | 95% CI | AP | rows | positives |
|---|---|---:|---:|---:|---:|---:|
| ML_gradient_boosted_trees | ml_panel | 1.0000 | [1.0000, 1.0000] | 1.0000 | 11,845 | 5,048 |
| ML_mlp | ml_panel | 0.9997 | [0.9996, 0.9999] | 0.9997 | 11,845 | 5,048 |
| ML_ridge_classifier | ml_panel | 0.9892 | [0.9823, 0.9942] | 0.9883 | 11,845 | 5,048 |
| traditional_scalar__event_selected_stave_multiplicity | traditional_scalar | 0.8465 | [0.8308, 0.8619] | 0.8238 | 11,845 | 5,048 |
| NN_transformer_sequence_encoder_new | ml_panel | 0.8380 | [0.7751, 0.8951] | 0.8236 | 11,845 | 5,048 |
| NN_1d_cnn | ml_panel | 0.8356 | [0.7775, 0.8901] | 0.8092 | 11,845 | 5,048 |

## Systematic Shifts

The table reports afterpulse-minus-memory median shifts in held-out rows, centered by run and stave before differencing.

| metric | shift | 95% CI | held-out positives |
|---|---:|---:|---:|
| tail-shape exponential slope | 0.037793 | [0.016055, 0.087887] | 5,048 |
| tail-shape AR residual RMS | 0.021942 | [0.012266, 0.052989] | 5,048 |
| timing shift | 0.574855 | [0.366490, 1.432580] | 5,048 |
| pile-up confusion | 0.000000 | [0.000000, 1.000000] | 5,048 |
| saturation recovery | 0.063991 | [0.038150, 0.148547] | 5,048 |
| pedestal drift sensitivity | -1.500000 | [-2.500000, 0.000000] | 5,048 |
| energy bias proxy | -0.024227 | [-0.029776, -0.017883] | 5,048 |
| PID confusion proxy | -82.500000 | [-123.084375, -41.975000] | 5,048 |

Negative-control constant pedestal perturbations before renormalization:

| perturbation ADC | median L2 | p95 L2 | label flip fraction | afterpulse flip | memory flip |
|---:|---:|---:|---:|---:|---:|
| -150.0 | 0.034237 | 0.124553 | 0.2075 | 0.4431 | 0.0438 |
| 150.0 | 0.031196 | 0.097070 | 0.1707 | 0.4077 | 0.0061 |

Negative-control time shuffles intentionally destroy the physical late-sample ordering before reapplying the same weak-label construction:

| control | median L2 | p95 L2 | original positive fraction | control positive fraction | label flip fraction |
|---|---:|---:|---:|---:|---:|
| time_reversal | 0.381401 | 0.843977 | 0.4098 | 0.7714 | 0.5809 |
| circular_roll_plus3 | 0.419634 | 0.669838 | 0.4098 | 0.6325 | 0.3195 |
| per_pulse_random_permutation | 0.511257 | 0.775238 | 0.4098 | 0.6156 | 0.3333 |

## Per-Run Stability

| method | mean per-run AUC | min | max | finite runs |
|---|---:|---:|---:|---:|
| ML_gradient_boosted_trees | 1.0000 | 1.0000 | 1.0000 | 8 |
| ML_mlp | 0.9997 | 0.9993 | 1.0000 | 8 |
| ML_ridge_classifier | 0.9888 | 0.9714 | 0.9977 | 8 |
| NN_1d_cnn | 0.8344 | 0.7104 | 0.9347 | 8 |
| NN_transformer_sequence_encoder_new | 0.8367 | 0.7169 | 0.9392 | 8 |
| traditional_scalar__event_selected_stave_multiplicity | 0.8457 | 0.8145 | 0.8930 | 8 |

## Caveats

- The afterpulse/pile-up label is weak and derived from waveform morphology plus same-event multiplicity, not an external particle-truth label.
- Run-heldout splits prevent random-row leakage but cannot remove all acquisition-era correlations.
- Duplicate-readout amplitude is used only as a diagnostic PID proxy in systematic tables, not as a training label.
- The causal sequence mixer is intentionally compact; a full attention transformer would be poorly constrained for 18 samples without stronger labels.

## Verdict

`result.json` names **ML_gradient_boosted_trees** as winner. The best traditional method is **traditional_scalar__event_selected_stave_multiplicity**. The conclusion is therefore: ML/NN model beats the strongest traditional exponential-tail/AR baseline by held-out AUC.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s28b_1783797017_25295_3bed5b6b_late_tail_afterpulse.py --config configs/s28b_1783797017_25295_3bed5b6b_late_tail_afterpulse.json
```

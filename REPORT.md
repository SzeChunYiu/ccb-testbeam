# S61a Pulse-Shape Timing Pedestal Phase Benchmark

## Abstract

Ticket `#2558` asks which pulse-shape degrees of freedom explain timing
residuals once pedestal, polarity, peak phase, and amplitude are fixed.  The
analysis first reproduces the registered B-stack selected-pulse count directly
from raw ROOT `h101/HRDv`, then evaluates a run-held-out timing-residual
benchmark.  The traditional comparator is a polarity-bound constant-fraction
and template time-walk correction with robust first-sample pedestal and
peak-phase covariates.  It is benchmarked against ridge, gradient-boosted
trees, MLP, 1D-CNN, a compact waveform transformer, and a ticket-local
derivative-gated transformer.

The winner named in `result.json` is **`traditional_cfd_template_derivative`** with held-out
`sigma_68 = 1.006 ns`
`[0.7222, 1.17]`,
median bias `0.2322 ns`, RMS `0.9699 ns`, and
`|error| > 5 ns` tail fraction `0`.

## Ticket Claim Provenance

The required command `tn-ticket claim testbeam-laptop-3 --project testbeam` was
run exactly once.  It returned the malformed payload:

```text
null
# null

null
```

Read-only GitHub inspection showed no issue claimed by
`worker:testbeam-laptop-3`, so issue `#2558` was manually label-swapped without
rerunning the helper:

```text
gh issue edit 2558 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open
```

## Raw ROOT Reproduction

Input files are read from `/home/billy/ccb-data/data/extracted/root/root`.  Each raw event vector is
reshaped as `(8, 18)`.  B-stack physics channels are B2, B4, B6, and B8.  With
`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`, the reproduced count is

`N = sum_e sum_c 1[max_t(x_e,c,t - b_e,c) > 1000 ADC]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group raw count is **640737**,
matching the registered value exactly.  The first input checksums are:

| run | path | bytes | sha256 |
| --- | --- | --- | --- |
| 31 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0031.root | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0032.root | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0033.root | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0034.root | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0035.root | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0036.root | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0037.root | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | /home/billy/ccb-data/data/extracted/root/root/hrdb_run_0039.root | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

## Estimand and Equations

The normalized pulse is `z_t = (x_t - b) / max(A, 1)`, where `A=max_t(x_t-b)`.
The sub-sample constant-fraction crossing at fraction `f` is

`t_f = k - 1 + (fA - y_(k-1)) / (y_k - y_(k-1))`,

with `k` the first pre-peak sample exceeding `fA`.  The target is the
run/stave-centered CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

First-derivative atoms are `d_t = z_(t+1) - z_t`; curvature atoms are
`c_t = d_(t+1) - d_t`.  For method `m`, error is
`epsilon_i(m) = y_i - yhat_i(m)`.  Resolution is reported as

`sigma_68 = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

with full RMS, median bias, and timing-tail fractions at 5 ns and 10 ns.

## Split and Uncertainty

The split unit is the source run.  Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`;
all other configured runs are training runs.  The sampled benchmark rows are:

| split | rows |
| --- | --- |
| heldout | 5466 |
| train | 15137 |

All quoted 95% confidence intervals use `500`
percentile bootstrap replicates that resample held-out runs with replacement.
This is intentionally stricter than an event bootstrap because run-to-run
transfer is the ticket's target.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_template_derivative | traditional | polarity-bound CFD20/50 template time-walk baseline plus derivative residual correction |
| ridge | linear ML | standardized ridge regression on fixed amplitude, phase, pedestal, waveform, derivative, and curvature atoms |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered pulse-shape covariates |
| 1d_cnn | neural waveform | compact 1D convolutional regressor over normalized 18-sample pulse windows |
| compact_waveform_transformer | neural waveform | one-layer sample-token self-attention encoder |
| derivative_gate_transformer_new | new architecture | transformer over waveform, first derivative, and curvature channels with derivative-magnitude pooling |

The new architecture is sensible here because the scientific hypothesis is
local: derivative and curvature channels should identify onset, peak-phase, and
late-tail deformations after pedestal and amplitude are controlled.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | rms_ns_ci_low | rms_ns_ci_high | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.2322 | -0.1031 | 0.436 | 1.006 | 0.7222 | 1.17 | 0.9699 | 0.8793 | 1.065 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.244 | -1.111 | 0.7553 | 3.435 | 2.86 | 4.108 | 5.452 | 3.409 | 7.788 | 0.1701 | 0.04757 |
| ridge | 5466 | 0.05978 | -0.6635 | 0.9051 | 3.972 | 3.509 | 4.679 | 5.92 | 3.722 | 8.574 | 0.2172 | 0.0472 |
| mlp | 5466 | -0.4827 | -1.421 | 0.6877 | 3.998 | 3.636 | 4.482 | 5.73 | 3.723 | 8.025 | 0.221 | 0.05123 |
| derivative_gate_transformer_new | 5466 | 1.707 | 1.057 | 2.283 | 5.625 | 5.322 | 6.377 | 7.756 | 6.038 | 9.94 | 0.4072 | 0.105 |
| compact_waveform_transformer | 5466 | 0.4314 | -0.1978 | 1.056 | 5.855 | 5.49 | 6.688 | 7.467 | 5.814 | 9.579 | 0.3955 | 0.1085 |
| 1d_cnn | 5466 | -1.126 | -1.959 | -0.1699 | 6.323 | 5.639 | 7.356 | 8.895 | 7.312 | 11.2 | 0.4157 | 0.1517 |

## Paired Deltas Against Traditional

Positive `delta_sigma68_ns` means worse resolution than the traditional
polarity-bound CFD/template derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_rms_ns | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.429 | 1.69 | 3.386 | -0.4762 | 4.482 | 0.1701 |
| ridge | traditional_cfd_template_derivative | 2.966 | 2.338 | 3.957 | -0.1724 | 4.95 | 0.2172 |
| mlp | traditional_cfd_template_derivative | 2.991 | 2.465 | 3.76 | -0.7148 | 4.76 | 0.221 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 4.619 | 4.151 | 5.655 | 1.475 | 6.786 | 0.4072 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 4.848 | 4.319 | 5.966 | 0.1992 | 6.497 | 0.3955 |
| 1d_cnn | traditional_cfd_template_derivative | 5.317 | 4.469 | 6.634 | -1.359 | 7.925 | 0.4157 |

## Pulse-Shape Atom Coefficients

The atom table fits a standardized ridge model on training runs only, after
including fixed pedestal, amplitude, peak-phase, and timing covariates.  Large
coefficients indicate pulse-shape degrees of freedom that explain residual
timing variation beyond those fixed nuisance axes.

| feature | family | ridge_standardized_coef_ns | abs_coef_ns |
| --- | --- | --- | --- |
| raw_cfd50_residual_ns | shape_summary_atom | 35.57 | 35.57 |
| cfd50_sample | fixed_timing_amplitude_covariate | -32.18 | 32.18 |
| cfd20_sample | fixed_timing_amplitude_covariate | 16.64 | 16.64 |
| cfd80_sample | fixed_timing_amplitude_covariate | 16.02 | 16.02 |
| rise_time_sample | fixed_timing_amplitude_covariate | -2.234 | 2.234 |
| pedestal_drift_abs | shape_summary_atom | -2.101 | 2.101 |
| baseline | pedestal_atom | 1.994 | 1.994 |
| positive_area | shape_summary_atom | -0.3162 | 0.3162 |
| late_slope_sum | shape_summary_atom | -0.274 | 0.274 |
| late_peak_prominence | shape_summary_atom | 0.1863 | 0.1863 |
| area | shape_summary_atom | 0.1357 | 0.1357 |
| pretrigger_derivative_rms | pedestal_atom | 0.1292 | 0.1292 |
| max_fall_slope | shape_summary_atom | -0.1289 | 0.1289 |
| derivative_centroid | shape_summary_atom | -0.1212 | 0.1212 |
| curvature_centroid | shape_summary_atom | 0.08864 | 0.08864 |
| curvature_energy | shape_summary_atom | -0.0787 | 0.0787 |
| pileup_separation_sample | shape_summary_atom | -0.06111 | 0.06111 |
| onset_slope_sum | shape_summary_atom | -0.05703 | 0.05703 |
| duplicate_amplitude | shape_summary_atom | 0.05664 | 0.05664 |
| tail_fraction | shape_summary_atom | -0.05577 | 0.05577 |
| d2_08 | curvature_atom | 0.04179 | 0.04179 |
| late_peak_sample | shape_summary_atom | 0.03995 | 0.03995 |
| pretrigger_slope | pedestal_atom | -0.03759 | 0.03759 |
| max_rise_slope | shape_summary_atom | -0.03646 | 0.03646 |
| peak_sample | fixed_timing_amplitude_covariate | -0.03187 | 0.03187 |
| d1_04 | first_derivative_atom | -0.02712 | 0.02712 |
| d1_00 | first_derivative_atom | 0.02626 | 0.02626 |
| d1_13 | first_derivative_atom | 0.02594 | 0.02594 |
| d1_11 | first_derivative_atom | 0.02505 | 0.02505 |
| d2_04 | curvature_atom | 0.02447 | 0.02447 |

## Placebo and Leakage Controls

The placebo controls shuffle the timing target within each source run before
training ridge and boosted-tree models.  They keep run composition and feature
marginals while breaking event-level pulse-shape association.

| control | n | bias_ns | sigma68_ns | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- |
| ridge_runwise_target_placebo | 5466 | -7.677 | 26.08 | 33.57 | 0.7978 | 0.6204 |
| hgb_runwise_target_placebo | 5466 | -8.236 | 27.01 | 33.71 | 0.7997 | 0.6347 |

## Run and Stratum Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | 0.1385 | 0.8781 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.9213 | 2.854 | 0.2126 |
| sample_i_analysis | mlp | 1350 | 0.6694 | 4.089 | 0.2644 |
| sample_i_analysis | ridge | 1350 | 0.7242 | 5.017 | 0.3185 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | 1.448 | 6.638 | 0.4548 |
| sample_i_analysis | compact_waveform_transformer | 1350 | 0.6902 | 6.908 | 0.3896 |
| sample_i_analysis | 1d_cnn | 1350 | -1.316 | 8.329 | 0.4993 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | -0.5595 | 1.405 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 2.104 | 3.912 | 0.2907 |
| sample_i_calib | ridge | 657 | 2.93 | 4.713 | 0.344 |
| sample_i_calib | mlp | 657 | 2.103 | 4.761 | 0.309 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 2.757 | 5.505 | 0.4049 |
| sample_i_calib | compact_waveform_transformer | 657 | 2.415 | 5.543 | 0.4033 |
| sample_i_calib | 1d_cnn | 657 | 1.679 | 7.258 | 0.5419 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.3019 | 0.8734 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.041 | 3.336 | 0.1522 |
| sample_ii_analysis | ridge | 2739 | -0.4795 | 3.641 | 0.1628 |
| sample_ii_analysis | mlp | 2739 | -1.158 | 3.873 | 0.2041 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | 1.606 | 5.564 | 0.3983 |
| sample_ii_analysis | 1d_cnn | 2739 | -1.286 | 5.82 | 0.3658 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | 0.01076 | 5.895 | 0.4038 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.6107 | 0.688 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.369 | 2.663 | 0.04861 |
| sample_ii_calib | ridge | 720 | -1.035 | 3.194 | 0.1181 |
| sample_ii_calib | mlp | 720 | -1.927 | 3.48 | 0.1236 |
| sample_ii_calib | 1d_cnn | 720 | -1.967 | 4.938 | 0.3333 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | 1.507 | 5.384 | 0.3542 |
| sample_ii_calib | compact_waveform_transformer | 720 | -0.198 | 5.516 | 0.3681 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.679 | 7.258 | 0.5419 |
| 1d_cnn | 50 | 680 | -3.477 | 13.47 | 0.55 |
| 1d_cnn | 57 | 670 | 0.2595 | 6.894 | 0.4478 |
| 1d_cnn | 58 | 654 | -2.572 | 5.752 | 0.422 |
| 1d_cnn | 60 | 720 | -0.2434 | 5.701 | 0.3361 |
| 1d_cnn | 62 | 720 | -0.9852 | 5.627 | 0.3514 |
| 1d_cnn | 64 | 720 | -1.967 | 4.938 | 0.3333 |
| 1d_cnn | 65 | 645 | -1.378 | 5.378 | 0.3581 |
| compact_waveform_transformer | 42 | 657 | 2.415 | 5.543 | 0.4033 |
| compact_waveform_transformer | 50 | 680 | 0.5537 | 12.98 | 0.4324 |
| compact_waveform_transformer | 57 | 670 | 0.901 | 4.926 | 0.3463 |
| compact_waveform_transformer | 58 | 654 | -1.391 | 5.901 | 0.4144 |
| compact_waveform_transformer | 60 | 720 | 0.3731 | 6.117 | 0.4292 |
| compact_waveform_transformer | 62 | 720 | 0.1246 | 5.78 | 0.3958 |
| compact_waveform_transformer | 64 | 720 | -0.198 | 5.516 | 0.3681 |
| compact_waveform_transformer | 65 | 645 | 0.7449 | 5.479 | 0.3736 |
| derivative_gate_transformer_new | 42 | 657 | 2.757 | 5.505 | 0.4049 |
| derivative_gate_transformer_new | 50 | 680 | 1.152 | 14.07 | 0.5221 |
| derivative_gate_transformer_new | 57 | 670 | 1.791 | 5.323 | 0.3866 |
| derivative_gate_transformer_new | 58 | 654 | -0.1897 | 5.594 | 0.3731 |
| derivative_gate_transformer_new | 60 | 720 | 2.681 | 5.526 | 0.4361 |
| derivative_gate_transformer_new | 62 | 720 | 2.243 | 5.56 | 0.4208 |
| derivative_gate_transformer_new | 64 | 720 | 1.507 | 5.384 | 0.3542 |
| derivative_gate_transformer_new | 65 | 645 | 1.494 | 5.279 | 0.3566 |
| gradient_boosted_trees | 42 | 657 | 2.104 | 3.912 | 0.2907 |
| gradient_boosted_trees | 50 | 680 | 1.741 | 11.82 | 0.3015 |
| gradient_boosted_trees | 57 | 670 | 0.3737 | 2.641 | 0.1224 |
| gradient_boosted_trees | 58 | 654 | -2.421 | 3.489 | 0.3211 |
| gradient_boosted_trees | 60 | 720 | -0.144 | 2.409 | 0.05833 |
| gradient_boosted_trees | 62 | 720 | -1.122 | 3.548 | 0.1014 |
| gradient_boosted_trees | 64 | 720 | -1.369 | 2.663 | 0.04861 |
| gradient_boosted_trees | 65 | 645 | -1.044 | 3.47 | 0.1426 |
| mlp | 42 | 657 | 2.103 | 4.761 | 0.309 |
| mlp | 50 | 680 | 0.5583 | 12.07 | 0.3353 |
| mlp | 57 | 670 | 0.7011 | 3.767 | 0.1925 |
| mlp | 58 | 654 | -2.355 | 4.264 | 0.2951 |
| mlp | 60 | 720 | 0.008968 | 3.244 | 0.1069 |
| mlp | 62 | 720 | -1.286 | 4.114 | 0.2111 |
| mlp | 64 | 720 | -1.927 | 3.48 | 0.1236 |
| mlp | 65 | 645 | -1.474 | 4.158 | 0.2124 |
| ridge | 42 | 657 | 2.93 | 4.713 | 0.344 |
| ridge | 50 | 680 | 0.1001 | 12.57 | 0.3838 |
| ridge | 57 | 670 | 1.005 | 4.207 | 0.2522 |
| ridge | 58 | 654 | -1.556 | 3.985 | 0.2416 |
| ridge | 60 | 720 | -0.1221 | 3.291 | 0.1056 |
| ridge | 62 | 720 | -0.526 | 3.677 | 0.1486 |
| ridge | 64 | 720 | -1.035 | 3.194 | 0.1181 |
| ridge | 65 | 645 | 0.004087 | 3.704 | 0.1628 |
| traditional_cfd_template_derivative | 42 | 657 | -0.5595 | 1.405 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | 0.4338 | 0.7374 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | -0.5023 | 0.771 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.4334 | 0.6976 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.09528 | 1.213 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.4984 | 0.9797 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.6107 | 0.688 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.3993 | 0.6158 | 0 |

## Systematic Strata

The requested pedestal and phase stratifications are represented by
`pedestal_drift_bin`, `peak_sample`, CFD phase covariates, derivative-onset
bins, curvature-energy bins, late-tail morphology, pile-up separation, and
saturation-onset sidebands.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1601 | -2.011 | 7.997 | 0.5315 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1601 | -2.618 | 6.271 | 0.456 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1601 | 0.5813 | 6.186 | 0.416 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1601 | -0.4584 | 3.63 | 0.1918 |
| curvature_energy_bin | curved | mlp | 1601 | -0.7186 | 4.058 | 0.233 |
| curvature_energy_bin | curved | ridge | 1601 | -0.6101 | 4.308 | 0.2542 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1601 | 0.4046 | 1.151 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1950 | 0.1648 | 5.636 | 0.3462 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1950 | 1.699 | 5.765 | 0.4097 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1950 | 2.141 | 5.681 | 0.44 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1950 | -0.03607 | 3.437 | 0.1733 |
| curvature_energy_bin | moderate | mlp | 1950 | -0.08709 | 3.963 | 0.2272 |
| curvature_energy_bin | moderate | ridge | 1950 | -0.09417 | 3.983 | 0.2154 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1950 | 0.2575 | 0.9274 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1915 | -2.043 | 5.088 | 0.3896 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1915 | 1.043 | 4.528 | 0.3305 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1915 | 2.173 | 5.021 | 0.3666 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1915 | -0.3215 | 3.23 | 0.1488 |
| curvature_energy_bin | smooth | mlp | 1915 | -0.6442 | 3.915 | 0.2047 |
| curvature_energy_bin | smooth | ridge | 1915 | 0.8727 | 3.713 | 0.188 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1915 | 0.08506 | 0.9255 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1833 | -1.926 | 5.291 | 0.3775 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1833 | -0.01829 | 5.7 | 0.3737 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1833 | 1.772 | 5.555 | 0.407 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1833 | -0.5057 | 3.185 | 0.1233 |
| derivative_onset_bin | nominal | mlp | 1833 | -0.8651 | 3.777 | 0.1899 |
| derivative_onset_bin | nominal | ridge | 1833 | -0.5121 | 3.603 | 0.1708 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1833 | 0.3051 | 0.9782 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1975 | -0.9018 | 5.616 | 0.3544 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1975 | 0.7449 | 5.788 | 0.4056 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1975 | 2.052 | 5.404 | 0.3995 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1975 | -0.79 | 3.073 | 0.1124 |
| derivative_onset_bin | sharp | mlp | 1975 | -1.21 | 3.648 | 0.1737 |
| derivative_onset_bin | sharp | ridge | 1975 | -0.6667 | 3.768 | 0.1838 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1975 | 0.2943 | 0.997 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1658 | -0.1293 | 9.624 | 0.5308 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1658 | 0.6751 | 5.962 | 0.4077 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1658 | 1.323 | 6.364 | 0.4168 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1658 | 1.025 | 4.23 | 0.2907 |
| derivative_onset_bin | slow | mlp | 1658 | 0.9235 | 4.547 | 0.3118 |
| derivative_onset_bin | slow | ridge | 1658 | 1.269 | 4.348 | 0.3082 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1658 | 0.04564 | 1.029 | 0 |
| energy_bin | q1_low | 1d_cnn | 1413 | -2.916 | 6.563 | 0.4989 |
| energy_bin | q1_low | compact_waveform_transformer | 1413 | 0.404 | 5.333 | 0.3609 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1413 | 2.006 | 5.683 | 0.4076 |
| energy_bin | q1_low | gradient_boosted_trees | 1413 | -0.3988 | 3.307 | 0.1592 |
| energy_bin | q1_low | mlp | 1413 | -0.696 | 3.863 | 0.2095 |
| energy_bin | q1_low | ridge | 1413 | 0.8387 | 3.777 | 0.201 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1413 | -0.04304 | 1.085 | 0 |
| energy_bin | q2 | 1d_cnn | 1489 | -1.051 | 4.935 | 0.323 |
| energy_bin | q2 | compact_waveform_transformer | 1489 | 1.585 | 5.205 | 0.3741 |
| energy_bin | q2 | derivative_gate_transformer_new | 1489 | 2.16 | 5.177 | 0.3862 |
| energy_bin | q2 | gradient_boosted_trees | 1489 | -0.0374 | 3.213 | 0.1672 |
| energy_bin | q2 | mlp | 1489 | -0.4408 | 4.102 | 0.2263 |
| energy_bin | q2 | ridge | 1489 | 0.2971 | 4.045 | 0.2163 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1489 | 0.2173 | 0.764 | 0 |
| energy_bin | q3 | 1d_cnn | 1445 | 1.189 | 4.548 | 0.3128 |
| energy_bin | q3 | compact_waveform_transformer | 1445 | 1.36 | 5.829 | 0.4201 |
| energy_bin | q3 | derivative_gate_transformer_new | 1445 | 2.35 | 5.93 | 0.4512 |
| energy_bin | q3 | gradient_boosted_trees | 1445 | -0.1202 | 3.527 | 0.1633 |
| energy_bin | q3 | mlp | 1445 | -0.2046 | 3.956 | 0.2242 |
| energy_bin | q3 | ridge | 1445 | -0.1857 | 3.988 | 0.2166 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1445 | 0.3409 | 0.8823 | 0 |
| energy_bin | q4_high | 1d_cnn | 1119 | -3.801 | 7.697 | 0.5666 |
| energy_bin | q4_high | compact_waveform_transformer | 1119 | -3.247 | 6.016 | 0.4361 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1119 | -0.02582 | 5.675 | 0.378 |
| energy_bin | q4_high | gradient_boosted_trees | 1119 | -0.5716 | 3.756 | 0.1966 |
| energy_bin | q4_high | mlp | 1119 | -0.6544 | 4.009 | 0.2243 |
| energy_bin | q4_high | ridge | 1119 | -0.6994 | 4.206 | 0.2395 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1119 | 0.4606 | 1.162 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3267 | -1.712 | 5.631 | 0.3878 |
| late_tail_morphology | compact | compact_waveform_transformer | 3267 | 0.08782 | 6.006 | 0.4105 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3267 | 1.183 | 5.763 | 0.4148 |
| late_tail_morphology | compact | gradient_boosted_trees | 3267 | -0.6946 | 3.196 | 0.1267 |
| late_tail_morphology | compact | mlp | 3267 | -1.119 | 3.762 | 0.1886 |
| late_tail_morphology | compact | ridge | 3267 | -0.508 | 3.8 | 0.1907 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3267 | 0.2599 | 0.9918 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 576 | -1.535 | 6.134 | 0.3507 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 576 | -0.8963 | 5.567 | 0.3524 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 576 | 3.652 | 4.309 | 0.3976 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 576 | -0.08277 | 2.951 | 0.1267 |
| late_tail_morphology | diffuse_tail | mlp | 576 | -0.4553 | 3.818 | 0.2083 |
| late_tail_morphology | diffuse_tail | ridge | 576 | -0.6466 | 3.336 | 0.1528 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 576 | 0.3481 | 1.094 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 393 | -4.129 | 9.574 | 0.5751 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 393 | 1.013 | 5.779 | 0.3995 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 393 | 2.523 | 5.341 | 0.4275 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 393 | -0.4217 | 3.471 | 0.1705 |
| late_tail_morphology | late_derivative_bump | mlp | 393 | -0.4396 | 3.884 | 0.2316 |
| late_tail_morphology | late_derivative_bump | ridge | 393 | 0.4736 | 3.964 | 0.2316 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 393 | 0.5488 | 1.103 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1230 | 1.339 | 7.56 | 0.4691 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1230 | 1.508 | 5.503 | 0.3748 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1230 | 1.279 | 5.75 | 0.3854 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1230 | 1.219 | 4.418 | 0.3057 |
| late_tail_morphology | late_rising_tail | mlp | 1230 | 0.971 | 4.505 | 0.3098 |
| late_tail_morphology | late_rising_tail | ridge | 1230 | 1.423 | 4.297 | 0.313 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1230 | 0.04659 | 0.9604 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1795 | -1.143 | 7.845 | 0.4708 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1795 | -1.398 | 6.738 | 0.4813 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1795 | 0.7755 | 6.518 | 0.4607 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1795 | -0.2025 | 3.637 | 0.1983 |
| pedestal_drift_bin | high | mlp | 1795 | -0.1276 | 4.28 | 0.2507 |
| pedestal_drift_bin | high | ridge | 1795 | 0.1041 | 4.137 | 0.2384 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1795 | 0.2362 | 1.092 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1800 | -1.114 | 5.67 | 0.3783 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1800 | 0.7801 | 5.223 | 0.3533 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1800 | 1.826 | 5.08 | 0.3783 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1800 | -0.1918 | 3.378 | 0.1589 |
| pedestal_drift_bin | low | mlp | 1800 | -0.5961 | 3.943 | 0.2072 |
| pedestal_drift_bin | low | ridge | 1800 | -0.0542 | 4.003 | 0.2122 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1800 | 0.2112 | 0.9327 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1871 | -1.121 | 5.794 | 0.3987 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1871 | 1.1 | 5.198 | 0.3538 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1871 | 2.337 | 5.063 | 0.3838 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1871 | -0.3324 | 3.263 | 0.1539 |
| pedestal_drift_bin | mid | mlp | 1871 | -0.7323 | 3.778 | 0.2058 |
| pedestal_drift_bin | mid | ridge | 1871 | 0.1132 | 3.841 | 0.2015 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1871 | 0.2637 | 0.9763 | 0 |
| pid_sideband | central | 1d_cnn | 3750 | -0.9033 | 5.712 | 0.3827 |
| pid_sideband | central | compact_waveform_transformer | 3750 | 1.101 | 5.201 | 0.3579 |
| pid_sideband | central | derivative_gate_transformer_new | 3750 | 2.165 | 5.099 | 0.3819 |
| pid_sideband | central | gradient_boosted_trees | 3750 | -0.1933 | 3.387 | 0.1659 |
| pid_sideband | central | mlp | 3750 | -0.4348 | 3.971 | 0.2173 |
| pid_sideband | central | ridge | 3750 | 0.2408 | 4.042 | 0.2197 |
| pid_sideband | central | traditional_cfd_template_derivative | 3750 | 0.2064 | 0.9625 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 894 | -2.515 | 9.79 | 0.5615 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 894 | -4.52 | 5.947 | 0.5626 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 894 | -1.927 | 7.169 | 0.5034 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 894 | -0.32 | 3.473 | 0.1946 |
| pid_sideband | high_duplicate | mlp | 894 | -0.1589 | 4.263 | 0.2494 |
| pid_sideband | high_duplicate | ridge | 894 | -0.2393 | 4.017 | 0.2383 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 894 | 0.2688 | 1.134 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 822 | -1.407 | 6.56 | 0.4075 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 822 | 0.7801 | 5.648 | 0.3856 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 822 | 2.618 | 5.136 | 0.4185 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 822 | -0.3372 | 3.619 | 0.163 |
| pid_sideband | low_duplicate | mlp | 822 | -0.8167 | 3.919 | 0.2068 |
| pid_sideband | low_duplicate | ridge | 822 | -0.3938 | 3.713 | 0.1825 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 822 | 0.3426 | 1.005 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1692 | -2.408 | 5.965 | 0.4173 |
| pileup_separation_bin | close | compact_waveform_transformer | 1692 | -0.2985 | 5.725 | 0.3895 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1692 | 1 | 5.528 | 0.3901 |
| pileup_separation_bin | close | gradient_boosted_trees | 1692 | -0.5436 | 3.457 | 0.1436 |
| pileup_separation_bin | close | mlp | 1692 | -1.05 | 4.012 | 0.2086 |
| pileup_separation_bin | close | ridge | 1692 | -0.9457 | 3.796 | 0.2009 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1692 | 0.3179 | 1.052 | 0 |
| pileup_separation_bin | late | 1d_cnn | 2 | -39.6 | 19.04 | 1 |
| pileup_separation_bin | late | compact_waveform_transformer | 2 | -38 | 15.78 | 1 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 2 | -26.57 | 11.62 | 1 |
| pileup_separation_bin | late | gradient_boosted_trees | 2 | -28.85 | 14.21 | 1 |
| pileup_separation_bin | late | mlp | 2 | -37.4 | 19.67 | 1 |
| pileup_separation_bin | late | ridge | 2 | 0.5991 | 3.407 | 0.5 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 2 | 0.383 | 0.2516 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1221 | 0.5515 | 5.71 | 0.3825 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1221 | -2.826 | 5.913 | 0.4717 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1221 | -0.06516 | 5.919 | 0.4234 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1221 | -0.7655 | 3.285 | 0.145 |
| pileup_separation_bin | mid | mlp | 1221 | -0.825 | 3.621 | 0.1818 |
| pileup_separation_bin | mid | ridge | 1221 | -0.2887 | 3.917 | 0.2064 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1221 | 0.4214 | 1.04 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2551 | -0.9974 | 6.35 | 0.43 |
| pileup_separation_bin | none | compact_waveform_transformer | 2551 | 1.775 | 4.71 | 0.3626 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2551 | 2.722 | 4.986 | 0.4104 |
| pileup_separation_bin | none | gradient_boosted_trees | 2551 | 0.244 | 3.456 | 0.1991 |
| pileup_separation_bin | none | mlp | 2551 | 0.05068 | 4.13 | 0.2474 |
| pileup_separation_bin | none | ridge | 2551 | 0.9346 | 3.793 | 0.2328 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2551 | 0.08435 | 0.9654 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1873 | -2.21 | 6.651 | 0.4624 |
| pulse_shape_class | compact | compact_waveform_transformer | 1873 | -0.8559 | 6.301 | 0.457 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1873 | -0.397 | 6.023 | 0.4186 |
| pulse_shape_class | compact | gradient_boosted_trees | 1873 | -0.784 | 3.226 | 0.1511 |
| pulse_shape_class | compact | mlp | 1873 | -1.125 | 3.817 | 0.2146 |
| pulse_shape_class | compact | ridge | 1873 | -0.0643 | 4.197 | 0.2274 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1873 | 0.2193 | 1.079 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1833 | 0.1584 | 7.06 | 0.4294 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1833 | 0.8957 | 5.553 | 0.365 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1833 | 2.285 | 5.204 | 0.389 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1833 | 0.6284 | 3.902 | 0.2477 |
| pulse_shape_class | late_tail | mlp | 1833 | 0.4712 | 4.244 | 0.2761 |
| pulse_shape_class | late_tail | ridge | 1833 | 0.7776 | 4.119 | 0.2602 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1833 | 0.1453 | 1.02 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1760 | -1.526 | 5.074 | 0.3517 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1760 | 1.023 | 5.444 | 0.3619 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1760 | 2.815 | 4.871 | 0.4142 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1760 | -0.6094 | 3.216 | 0.1097 |
| pulse_shape_class | nominal | mlp | 1760 | -0.9787 | 3.682 | 0.1705 |
| pulse_shape_class | nominal | ridge | 1760 | -0.6945 | 3.558 | 0.1614 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1760 | 0.3335 | 0.8853 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3927 | -0.7602 | 6.433 | 0.4281 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3927 | 0.2278 | 5.989 | 0.4062 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3927 | 1.641 | 5.723 | 0.4082 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3927 | -0.3435 | 3.473 | 0.1711 |
| saturation_onset_bin | linear | mlp | 3927 | -0.5481 | 4.024 | 0.2208 |
| saturation_onset_bin | linear | ridge | 3927 | -0.004903 | 4.012 | 0.2236 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3927 | 0.2277 | 1.011 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1539 | -1.998 | 5.779 | 0.384 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1539 | 0.9524 | 5.429 | 0.3684 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1539 | 1.955 | 5.272 | 0.4048 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1539 | -0.02009 | 3.298 | 0.1676 |
| saturation_onset_bin | near_saturation | mlp | 1539 | -0.341 | 3.909 | 0.2216 |
| saturation_onset_bin | near_saturation | ridge | 1539 | 0.2455 | 3.912 | 0.2008 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1539 | 0.2419 | 0.983 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 5.088 | curved | 7.997 | 2.909 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.528 | curved | 6.271 | 1.743 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 5.021 | curved | 6.186 | 1.165 |
| curvature_energy_bin | ridge | 3 | smooth | 3.713 | curved | 4.308 | 0.595 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.23 | curved | 3.63 | 0.4 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | smooth | 0.9255 | curved | 1.151 | 0.2251 |
| curvature_energy_bin | mlp | 3 | smooth | 3.915 | curved | 4.058 | 0.143 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 5.291 | slow | 9.624 | 4.332 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.073 | slow | 4.23 | 1.157 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | sharp | 5.404 | slow | 6.364 | 0.9597 |
| derivative_onset_bin | mlp | 3 | sharp | 3.648 | slow | 4.547 | 0.8988 |
| derivative_onset_bin | ridge | 3 | nominal | 3.603 | slow | 4.348 | 0.7456 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 5.7 | slow | 5.962 | 0.2619 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | nominal | 0.9782 | slow | 1.029 | 0.05095 |
| energy_bin | 1d_cnn | 4 | q3 | 4.548 | q4_high | 7.697 | 3.15 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 5.205 | q4_high | 6.016 | 0.8108 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 5.177 | q3 | 5.93 | 0.7524 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.213 | q4_high | 3.756 | 0.5434 |
| energy_bin | ridge | 4 | q1_low | 3.777 | q4_high | 4.206 | 0.4297 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.764 | q4_high | 1.162 | 0.3984 |
| energy_bin | mlp | 4 | q1_low | 3.863 | q2 | 4.102 | 0.2389 |
| late_tail_morphology | 1d_cnn | 4 | compact | 5.631 | late_derivative_bump | 9.574 | 3.943 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 2.951 | late_rising_tail | 4.418 | 1.467 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 4.309 | compact | 5.763 | 1.454 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.336 | late_rising_tail | 4.297 | 0.9602 |
| late_tail_morphology | mlp | 4 | compact | 3.762 | late_rising_tail | 4.505 | 0.7426 |
| late_tail_morphology | compact_waveform_transformer | 4 | late_rising_tail | 5.503 | compact | 6.006 | 0.5035 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_rising_tail | 0.9604 | late_derivative_bump | 1.103 | 0.1427 |
| pedestal_drift_bin | 1d_cnn | 3 | low | 5.67 | high | 7.845 | 2.174 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.198 | high | 6.738 | 1.54 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 5.063 | high | 6.518 | 1.455 |
| pedestal_drift_bin | mlp | 3 | mid | 3.778 | high | 4.28 | 0.5023 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 3.263 | high | 3.637 | 0.3738 |
| pedestal_drift_bin | ridge | 3 | mid | 3.841 | high | 4.137 | 0.2958 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | low | 0.9327 | high | 1.092 | 0.1597 |
| pid_sideband | 1d_cnn | 3 | central | 5.712 | high_duplicate | 9.79 | 4.077 |
| pid_sideband | derivative_gate_transformer_new | 3 | central | 5.099 | high_duplicate | 7.169 | 2.07 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.201 | high_duplicate | 5.947 | 0.746 |
| pid_sideband | mlp | 3 | low_duplicate | 3.919 | high_duplicate | 4.263 | 0.3449 |
| pid_sideband | ridge | 3 | low_duplicate | 3.713 | central | 4.042 | 0.3296 |
| pid_sideband | gradient_boosted_trees | 3 | central | 3.387 | low_duplicate | 3.619 | 0.2316 |
| pid_sideband | traditional_cfd_template_derivative | 3 | central | 0.9625 | high_duplicate | 1.134 | 0.1716 |
| pileup_separation_bin | mlp | 4 | mid | 3.621 | late | 19.67 | 16.05 |
| pileup_separation_bin | 1d_cnn | 4 | mid | 5.71 | late | 19.04 | 13.33 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 4.71 | late | 15.78 | 11.07 |
| pileup_separation_bin | gradient_boosted_trees | 4 | mid | 3.285 | late | 14.21 | 10.93 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | none | 4.986 | late | 11.62 | 6.637 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | late | 0.2516 | close | 1.052 | 0.8001 |
| pileup_separation_bin | ridge | 4 | late | 3.407 | mid | 3.917 | 0.5103 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 5.074 | late_tail | 7.06 | 1.986 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.871 | compact | 6.023 | 1.151 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.444 | compact | 6.301 | 0.8563 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.216 | late_tail | 3.902 | 0.6868 |
| pulse_shape_class | ridge | 3 | nominal | 3.558 | compact | 4.197 | 0.6397 |
| pulse_shape_class | mlp | 3 | nominal | 3.682 | late_tail | 4.244 | 0.5613 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.8853 | compact | 1.079 | 0.1937 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.779 | linear | 6.433 | 0.6532 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.429 | linear | 5.989 | 0.5594 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 5.272 | linear | 5.723 | 0.4504 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.298 | linear | 3.473 | 0.1745 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.909 | linear | 4.024 | 0.1143 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.912 | linear | 4.012 | 0.09952 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.983 | linear | 1.011 | 0.02813 |

## Caveats

This is a raw-ROOT, run-held-out timing-residual benchmark, not an absolute
beamline timing truth measurement.  The target is constructed from the sampled
waveform itself, so a method that wins here explains stable internal
pulse-shape timing residuals rather than proving a detector-resolution limit.
The polarity is fixed to the B-stack channel convention and positive
baseline-subtracted pulses; an opposite-polarity acquisition would require the
same CFD equations with the sign convention inverted.  Neural models are
compact and trained under a fixed CPU budget, so the conclusion is about robust
transfer under constrained model capacity, not exhaustive hyperparameter
search.

Runtime for finalization was `2.3 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29` with
Python `3.8.10`.

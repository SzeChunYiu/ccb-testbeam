# S66a/#2545: bootstrap pulse-shape latent atlas from spline-template residuals versus waveform encoders

## Abstract

Ticket `#2545` asks for a pulse-shape latent atlas across stave, run family, amplitude, peak phase,
pedestal state, and mild pile-up strata.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
median-template time-walk, and shape-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `shape_time_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_median_template_cfd_timewalk_shape`** as the
winner with `sigma_68 = 0.9533 ns`
`[0.7782, 1.072]`.  The
traditional shape-time comparator obtains `0.9533 ns`
`[0.7782, 1.072]`.

## Raw ROOT Reproduction

Input files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each event the raw
vector `HRDv` is reshaped to `(8, 18)`.  The B-stack channels are B2, B4, B6,
and B8.  With pretrigger baseline

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

the reproduced count is

`N = sum_e sum_{c in B2,B4,B6,B8} 1[max_t(x_{e,c,t} - b_{e,c}) > 1000]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced raw count is **640737**.
Input hashes are stored in `input_sha256.csv`; first rows:

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

The sub-sample constant-fraction crossing at fraction `f` is computed by
linear interpolation before the waveform peak:

`t_f = k - 1 + (f A - y_{k-1}) / (y_k - y_{k-1})`,

where `y_t = x_t - b`, `A = max_t y_t`, and `k` is the first pre-peak sample
with `y_k >= f A`.  The supervised target is the run/stave-centered CFD20
residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The normalized waveform is `z_t = (x_t - b) / max(A, 1)`.  Derivative features
are the finite differences

`d_t = z_{t+1} - z_t`,

and curvature samples

`c_t = d_{t+1} - d_t`.

The traditional method starts from the audited CFD/template time-walk baseline
`hat y_0`, then fits a ridge-regularized derivative residual correction on
training runs only:

`hat y = hat y_0 + beta_0 + beta^T standardize(s_deriv)`,

where `s_deriv` contains onset slope, late slope, curvature peak, curvature
energy, derivative centroids, and pretrigger derivative RMS.  The ridge penalty
prevents derivative summaries from silently absorbing run identity.

For method `m`, residual error is `epsilon_i^m = y_i - hat y_i^m`.  Resolution
is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

and bias is `median(epsilon)`.

## Split and Uncertainty

The split unit is the run: held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]` and all
other configured B-stack runs are used for training.  Sampled benchmark rows:

| split | rows |
| --- | --- |
| heldout | 4926 |
| train | 13747 |

Confidence intervals use `300` paired percentile
bootstrap replicates that resample held-out runs with replacement.  Paired
deltas subtract each replicate of the traditional shape-time comparator from
the corresponding replicate of the learned method.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | traditional | aligned median-template CFD/optimal-filter timing, explicit time-walk terms, and ridge-regularized shape/curvature residual correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, waveform, derivative, curvature, and hand pulse-shape features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled waveform-summary feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform, detector-state, derivative, curvature, and q-template summaries |
| 1d_cnn | neural waveform | compact 1D convolutional regressor over normalized 18-sample waveforms |
| compact_waveform_transformer | neural waveform | one-layer waveform self-attention encoder inherited from the audited timing benchmark |
| shape_time_gate_transformer_new | new architecture | compact transformer over waveform, first derivative, and second derivative channels with shape/time derivative-magnitude pooling |

The new architecture is sensible for this ticket because the hypothesis is not
generic waveform learning; it is that edge, curvature, and normalized
shape-template channels localize pulse-shape timing changes under pedestal
drift.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | 4926 | 0.2359 | -0.4197 | 0.5512 | 0.9533 | 0.7782 | 1.072 | 0.9624 | 0.9952 | 0.1821 | 0 | 0 |
| gradient_boosted_trees | 4926 | -0.8646 | -1.751 | -0.06009 | 3.506 | 2.902 | 3.851 | 4.701 | 1.01 | 0.1821 | 0.1685 | 0.03796 |
| mlp | 4926 | -1.129 | -2.241 | -0.1203 | 3.961 | 3.487 | 4.408 | 4.873 | 1.01 | 0.1821 | 0.2146 | 0.0406 |
| ridge | 4926 | -0.4365 | -1.257 | 0.2642 | 4.012 | 3.494 | 4.464 | 5.034 | 1.009 | 0.1821 | 0.2099 | 0.04324 |
| 1d_cnn | 4926 | -0.9608 | -1.757 | -0.07632 | 5.185 | 4.603 | 5.947 | 7.273 | 1.036 | 0.1821 | 0.3329 | 0.1155 |
| shape_time_gate_transformer_new | 4926 | -1.203 | -2.11 | -0.5502 | 5.496 | 5.002 | 6.425 | 7.008 | 1.002 | 0.1821 | 0.3628 | 0.1129 |
| compact_waveform_transformer | 4926 | 1.983 | 0.8081 | 3.023 | 6.679 | 6.101 | 7.386 | 7.845 | 1.029 | 0.1821 | 0.4631 | 0.1786 |

## Paired Deltas Against Traditional Shape-Time Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional shape-time comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_median_template_cfd_timewalk_shape | 2.553 | 1.933 | 2.984 | -1.101 | -2.118 | -0.2218 | 0.1685 |
| mlp | traditional_median_template_cfd_timewalk_shape | 3.008 | 2.515 | 3.515 | -1.365 | -2.436 | -0.2365 | 0.2146 |
| ridge | traditional_median_template_cfd_timewalk_shape | 3.058 | 2.517 | 3.567 | -0.6724 | -1.485 | 0.2333 | 0.2099 |
| 1d_cnn | traditional_median_template_cfd_timewalk_shape | 4.232 | 3.606 | 5.039 | -1.197 | -2.123 | -0.1938 | 0.3329 |
| shape_time_gate_transformer_new | traditional_median_template_cfd_timewalk_shape | 4.543 | 3.994 | 5.526 | -1.439 | -2.441 | -0.4413 | 0.3628 |
| compact_waveform_transformer | traditional_median_template_cfd_timewalk_shape | 5.726 | 5.139 | 6.397 | 1.747 | 0.5626 | 2.948 | 0.4631 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_median_template_cfd_timewalk_shape | 1230 | -0.0157 | 0.9888 | 0.9986 | 0.2219 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1230 | -0.1765 | 2.852 | 1.003 | 0.2219 | 0.2008 |
| sample_i_analysis | mlp | 1230 | -0.3118 | 3.699 | 1.002 | 0.2219 | 0.2252 |
| sample_i_analysis | ridge | 1230 | -0.03298 | 4.992 | 1.002 | 0.2219 | 0.3114 |
| sample_i_analysis | compact_waveform_transformer | 1230 | 1.342 | 6.956 | 1.028 | 0.2219 | 0.4382 |
| sample_i_analysis | 1d_cnn | 1230 | -1.109 | 6.966 | 1.026 | 0.2219 | 0.4195 |
| sample_i_analysis | shape_time_gate_transformer_new | 1230 | -1.243 | 7.123 | 1.001 | 0.2219 | 0.4407 |
| sample_i_calib | traditional_median_template_cfd_timewalk_shape | 597 | -0.6796 | 0.5553 | 0.9975 | 0.2049 | 0 |
| sample_i_calib | gradient_boosted_trees | 597 | 0.3304 | 2.453 | 1.026 | 0.2049 | 0.08878 |
| sample_i_calib | mlp | 597 | 0.6016 | 2.662 | 1.024 | 0.2049 | 0.05193 |
| sample_i_calib | ridge | 597 | 0.5494 | 3.454 | 1.024 | 0.2049 | 0.134 |
| sample_i_calib | 1d_cnn | 597 | 0.1149 | 5.033 | 1.06 | 0.2049 | 0.3082 |
| sample_i_calib | compact_waveform_transformer | 597 | 2.2 | 5.279 | 1.055 | 0.2049 | 0.3501 |
| sample_i_calib | shape_time_gate_transformer_new | 597 | -0.567 | 5.395 | 1.027 | 0.2049 | 0.3518 |
| sample_ii_analysis | traditional_median_template_cfd_timewalk_shape | 2459 | 0.5516 | 0.87 | 0.9956 | 0.1681 | 0 |
| sample_ii_analysis | ridge | 2459 | -0.8101 | 3.849 | 1.01 | 0.1681 | 0.1989 |
| sample_ii_analysis | gradient_boosted_trees | 2459 | -1.483 | 3.889 | 1.008 | 0.1681 | 0.1976 |
| sample_ii_analysis | mlp | 2459 | -1.85 | 4.317 | 1.011 | 0.1681 | 0.2651 |
| sample_ii_analysis | 1d_cnn | 2459 | -1.109 | 5.026 | 1.036 | 0.1681 | 0.3148 |
| sample_ii_analysis | shape_time_gate_transformer_new | 2459 | -1.31 | 5.323 | 1.001 | 0.1681 | 0.3469 |
| sample_ii_analysis | compact_waveform_transformer | 2459 | 2.175 | 7.034 | 1.027 | 0.1681 | 0.5047 |
| sample_ii_calib | traditional_median_template_cfd_timewalk_shape | 640 | 0.5934 | 0.6805 | 0.995 | 0.1382 | 0 |
| sample_ii_calib | ridge | 640 | -0.748 | 3.234 | 1.019 | 0.1382 | 0.1281 |
| sample_ii_calib | gradient_boosted_trees | 640 | -1.241 | 3.254 | 1.016 | 0.1382 | 0.06875 |
| sample_ii_calib | mlp | 640 | -1.926 | 3.866 | 1.013 | 0.1382 | 0.1516 |
| sample_ii_calib | 1d_cnn | 640 | -0.8103 | 4.371 | 1.035 | 0.1382 | 0.2594 |
| sample_ii_calib | shape_time_gate_transformer_new | 640 | -1.403 | 4.608 | 0.9771 | 0.1382 | 0.2844 |
| sample_ii_calib | compact_waveform_transformer | 640 | 2.983 | 6.218 | 1.023 | 0.1382 | 0.4562 |

| method | run | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 597 | 0.1149 | 5.033 | 1.06 | 0.2049 | 0.3082 |
| 1d_cnn | 50 | 620 | -2.309 | 10.24 | 1.014 | 0.1852 | 0.4339 |
| 1d_cnn | 57 | 610 | 1.137 | 5.652 | 1.049 | 0.2592 | 0.4049 |
| 1d_cnn | 58 | 594 | -3.486 | 5.52 | 1.059 | 0.1972 | 0.4495 |
| 1d_cnn | 60 | 640 | 0.4861 | 4.178 | 1.011 | 0.1538 | 0.2422 |
| 1d_cnn | 62 | 640 | -0.6593 | 4.9 | 1.021 | 0.1796 | 0.2812 |
| 1d_cnn | 64 | 640 | -0.8103 | 4.371 | 1.035 | 0.1382 | 0.2594 |
| 1d_cnn | 65 | 585 | -1.725 | 4.136 | 1.074 | 0.1415 | 0.294 |
| compact_waveform_transformer | 42 | 597 | 2.2 | 5.279 | 1.055 | 0.2049 | 0.3501 |
| compact_waveform_transformer | 50 | 620 | 0.1457 | 10.59 | 1.005 | 0.1852 | 0.4194 |
| compact_waveform_transformer | 57 | 610 | 2.911 | 6.732 | 1.064 | 0.2592 | 0.4574 |
| compact_waveform_transformer | 58 | 594 | -0.7714 | 7.423 | 1.034 | 0.1972 | 0.4983 |
| compact_waveform_transformer | 60 | 640 | 3.092 | 6.868 | 1.014 | 0.1538 | 0.5453 |
| compact_waveform_transformer | 62 | 640 | 3.787 | 6.63 | 1.021 | 0.1796 | 0.5062 |
| compact_waveform_transformer | 64 | 640 | 2.983 | 6.218 | 1.023 | 0.1382 | 0.4562 |
| compact_waveform_transformer | 65 | 585 | 2.297 | 6.162 | 1.061 | 0.1415 | 0.465 |
| gradient_boosted_trees | 42 | 597 | 0.3304 | 2.453 | 1.026 | 0.2049 | 0.08878 |
| gradient_boosted_trees | 50 | 620 | -0.5312 | 9.631 | 0.985 | 0.1852 | 0.2871 |
| gradient_boosted_trees | 57 | 610 | -0.05679 | 2.751 | 1.027 | 0.2592 | 0.1131 |
| gradient_boosted_trees | 58 | 594 | -4.079 | 3.31 | 1.028 | 0.1972 | 0.3586 |
| gradient_boosted_trees | 60 | 640 | 0.213 | 3.299 | 1.015 | 0.1538 | 0.1016 |
| gradient_boosted_trees | 62 | 640 | -1.04 | 3.705 | 1.004 | 0.1796 | 0.1094 |
| gradient_boosted_trees | 64 | 640 | -1.241 | 3.254 | 1.016 | 0.1382 | 0.06875 |
| gradient_boosted_trees | 65 | 585 | -2.717 | 3.01 | 1.025 | 0.1415 | 0.2359 |
| mlp | 42 | 597 | 0.6016 | 2.662 | 1.024 | 0.2049 | 0.05193 |
| mlp | 50 | 620 | -0.9682 | 9.375 | 0.9868 | 0.1852 | 0.3 |
| mlp | 57 | 610 | 0.1145 | 3.565 | 1.023 | 0.2592 | 0.1492 |
| mlp | 58 | 594 | -3.828 | 4.523 | 1.03 | 0.1972 | 0.4091 |
| mlp | 60 | 640 | -0.1989 | 3.786 | 1.022 | 0.1538 | 0.1922 |
| mlp | 62 | 640 | -1.496 | 4.358 | 1.008 | 0.1796 | 0.2172 |
| mlp | 64 | 640 | -1.926 | 3.866 | 1.013 | 0.1382 | 0.1516 |
| mlp | 65 | 585 | -3.058 | 3.683 | 1.024 | 0.1415 | 0.2513 |
| ridge | 42 | 597 | 0.5494 | 3.454 | 1.024 | 0.2049 | 0.134 |
| ridge | 50 | 620 | -1.216 | 9.816 | 0.9857 | 0.1852 | 0.3952 |
| ridge | 57 | 610 | 0.4832 | 4.097 | 1.025 | 0.2592 | 0.2262 |
| ridge | 58 | 594 | -2.827 | 4.45 | 1.025 | 0.1972 | 0.3451 |
| ridge | 60 | 640 | 0.5679 | 3.167 | 1.023 | 0.1538 | 0.1172 |
| ridge | 62 | 640 | -0.1766 | 3.635 | 1.006 | 0.1796 | 0.1859 |
| ridge | 64 | 640 | -0.748 | 3.234 | 1.019 | 0.1382 | 0.1281 |
| ridge | 65 | 585 | -1.546 | 3.009 | 1.024 | 0.1415 | 0.1538 |
| shape_time_gate_transformer_new | 42 | 597 | -0.567 | 5.395 | 1.027 | 0.2049 | 0.3518 |
| shape_time_gate_transformer_new | 50 | 620 | -2.789 | 11.37 | 0.9837 | 0.1852 | 0.4774 |
| shape_time_gate_transformer_new | 57 | 610 | -0.2575 | 5.646 | 1.028 | 0.2592 | 0.4033 |
| shape_time_gate_transformer_new | 58 | 594 | -3.546 | 5.657 | 1.033 | 0.1972 | 0.4428 |
| shape_time_gate_transformer_new | 60 | 640 | -0.298 | 4.864 | 0.9996 | 0.1538 | 0.2969 |
| shape_time_gate_transformer_new | 62 | 640 | -0.3073 | 5.191 | 0.9696 | 0.1796 | 0.3312 |
| shape_time_gate_transformer_new | 64 | 640 | -1.403 | 4.608 | 0.9771 | 0.1382 | 0.2844 |
| shape_time_gate_transformer_new | 65 | 585 | -2.251 | 4.333 | 1.023 | 0.1415 | 0.3214 |
| traditional_median_template_cfd_timewalk_shape | 42 | 597 | -0.6796 | 0.5553 | 0.9975 | 0.2049 | 0 |
| traditional_median_template_cfd_timewalk_shape | 50 | 620 | 0.05007 | 0.9387 | 0.9986 | 0.1852 | 0 |
| traditional_median_template_cfd_timewalk_shape | 57 | 610 | -0.4572 | 0.9832 | 0.999 | 0.2592 | 0 |
| traditional_median_template_cfd_timewalk_shape | 58 | 594 | 0.6638 | 0.6193 | 0.995 | 0.1972 | 0 |
| traditional_median_template_cfd_timewalk_shape | 60 | 640 | -0.06026 | 0.9484 | 0.9969 | 0.1538 | 0 |
| traditional_median_template_cfd_timewalk_shape | 62 | 640 | 0.547 | 0.359 | 0.9948 | 0.1796 | 0 |
| traditional_median_template_cfd_timewalk_shape | 64 | 640 | 0.5934 | 0.6805 | 0.995 | 0.1382 | 0 |
| traditional_median_template_cfd_timewalk_shape | 65 | 585 | 0.761 | 1.173 | 0.9941 | 0.1415 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1457 | -1.275 | 5.99 | 1.018 | 0.3358 | 0.3967 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1457 | -2.069 | 6.196 | 1.058 | 0.3358 | 0.4338 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1457 | -0.9551 | 3.512 | 1.006 | 0.3358 | 0.1901 |
| curvature_energy_bin | curved | mlp | 1457 | -1.102 | 4.219 | 1.001 | 0.3358 | 0.2649 |
| curvature_energy_bin | curved | ridge | 1457 | -0.7933 | 4.166 | 0.996 | 0.3358 | 0.2478 |
| curvature_energy_bin | curved | shape_time_gate_transformer_new | 1457 | -1.282 | 6.277 | 0.921 | 0.3358 | 0.4283 |
| curvature_energy_bin | curved | traditional_median_template_cfd_timewalk_shape | 1457 | 0.28 | 1.055 | 0.9939 | 0.3358 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1779 | -6.749e-05 | 4.703 | 1.03 | 0.1171 | 0.2912 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1779 | 3.085 | 5.77 | 1.014 | 0.1171 | 0.4666 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1779 | -0.5637 | 3.593 | 1.011 | 0.1171 | 0.1698 |
| curvature_energy_bin | moderate | mlp | 1779 | -0.8167 | 3.903 | 1.01 | 0.1171 | 0.2012 |
| curvature_energy_bin | moderate | ridge | 1779 | -0.4779 | 3.902 | 1.008 | 0.1171 | 0.2046 |
| curvature_energy_bin | moderate | shape_time_gate_transformer_new | 1779 | -0.7746 | 5.189 | 0.9977 | 0.1171 | 0.335 |
| curvature_energy_bin | moderate | traditional_median_template_cfd_timewalk_shape | 1779 | 0.3088 | 0.8717 | 0.996 | 0.1171 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1690 | -1.608 | 4.86 | 1.059 | 0.118 | 0.3219 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1690 | 3.912 | 5.826 | 1.001 | 0.118 | 0.4846 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1690 | -1.127 | 3.361 | 1.012 | 0.118 | 0.1485 |
| curvature_energy_bin | smooth | mlp | 1690 | -1.464 | 3.744 | 1.014 | 0.118 | 0.1852 |
| curvature_energy_bin | smooth | ridge | 1690 | -0.07022 | 3.76 | 1.015 | 0.118 | 0.1828 |
| curvature_energy_bin | smooth | shape_time_gate_transformer_new | 1690 | -1.57 | 5.242 | 1.07 | 0.118 | 0.3355 |
| curvature_energy_bin | smooth | traditional_median_template_cfd_timewalk_shape | 1690 | 0.1254 | 0.9921 | 0.9965 | 0.118 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1662 | -1.607 | 4.524 | 0.9216 | 0.03969 | 0.2894 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1662 | 2.099 | 6.691 | 1.03 | 0.03969 | 0.4789 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1662 | -1.108 | 3.086 | 0.9949 | 0.03969 | 0.1474 |
| derivative_onset_bin | nominal | mlp | 1662 | -1.715 | 3.663 | 0.999 | 0.03969 | 0.2118 |
| derivative_onset_bin | nominal | ridge | 1662 | -1.227 | 3.745 | 1.048 | 0.03969 | 0.1943 |
| derivative_onset_bin | nominal | shape_time_gate_transformer_new | 1662 | -2.178 | 5.09 | 1.318 | 0.03969 | 0.3387 |
| derivative_onset_bin | nominal | traditional_median_template_cfd_timewalk_shape | 1662 | 0.3013 | 0.9509 | 0.9947 | 0.03969 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1727 | -0.94 | 4.692 | 0.8441 | 0.04237 | 0.2884 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1727 | 2.615 | 6.596 | 0.8627 | 0.04237 | 0.4893 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1727 | -1.15 | 3.034 | 0.9942 | 0.04237 | 0.1199 |
| derivative_onset_bin | sharp | mlp | 1727 | -1.688 | 3.714 | 0.9835 | 0.04237 | 0.1928 |
| derivative_onset_bin | sharp | ridge | 1727 | -0.8284 | 3.877 | 1.049 | 0.04237 | 0.198 |
| derivative_onset_bin | sharp | shape_time_gate_transformer_new | 1727 | -1.596 | 4.902 | 1.166 | 0.04237 | 0.3283 |
| derivative_onset_bin | sharp | traditional_median_template_cfd_timewalk_shape | 1727 | 0.3829 | 0.9183 | 0.9924 | 0.04237 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1537 | 0.1187 | 7.809 | 1.069 | 0.493 | 0.4301 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1537 | 1.15 | 6.411 | 1.054 | 0.493 | 0.4164 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1537 | 0.04895 | 4.136 | 1.005 | 0.493 | 0.2459 |
| derivative_onset_bin | slow | mlp | 1537 | 0.2336 | 4.049 | 1.005 | 0.493 | 0.242 |
| derivative_onset_bin | slow | ridge | 1537 | 0.5785 | 3.855 | 1 | 0.493 | 0.2401 |
| derivative_onset_bin | slow | shape_time_gate_transformer_new | 1537 | 0.7797 | 6.607 | 0.9735 | 0.493 | 0.4275 |
| derivative_onset_bin | slow | traditional_median_template_cfd_timewalk_shape | 1537 | 0.00422 | 0.9706 | 0.9963 | 0.493 | 0 |
| energy_bin | q1_low | 1d_cnn | 1241 | -2.336 | 6.265 | 1.1 | 0.4613 | 0.4448 |
| energy_bin | q1_low | compact_waveform_transformer | 1241 | 3.247 | 6.148 | 1.055 | 0.4613 | 0.4609 |
| energy_bin | q1_low | gradient_boosted_trees | 1241 | -1.134 | 3.483 | 1.009 | 0.4613 | 0.1676 |
| energy_bin | q1_low | mlp | 1241 | -1.111 | 3.706 | 1.004 | 0.4613 | 0.1878 |
| energy_bin | q1_low | ridge | 1241 | 0.2119 | 3.773 | 1.014 | 0.4613 | 0.2095 |
| energy_bin | q1_low | shape_time_gate_transformer_new | 1241 | -0.7875 | 6.399 | 0.9734 | 0.4613 | 0.4392 |
| energy_bin | q1_low | traditional_median_template_cfd_timewalk_shape | 1241 | -0.1375 | 1.109 | 0.9931 | 0.4613 | 0 |
| energy_bin | q2 | 1d_cnn | 1383 | -1.071 | 4.518 | 1.029 | 0.1057 | 0.2827 |
| energy_bin | q2 | compact_waveform_transformer | 1383 | 4.029 | 5.6 | 1.015 | 0.1057 | 0.4902 |
| energy_bin | q2 | gradient_boosted_trees | 1383 | -0.7298 | 3.447 | 1.011 | 0.1057 | 0.1475 |
| energy_bin | q2 | mlp | 1383 | -1.365 | 4.013 | 1.014 | 0.1057 | 0.2061 |
| energy_bin | q2 | ridge | 1383 | -0.4019 | 4.02 | 1.012 | 0.1057 | 0.201 |
| energy_bin | q2 | shape_time_gate_transformer_new | 1383 | -1.404 | 5.316 | 1.044 | 0.1057 | 0.3384 |
| energy_bin | q2 | traditional_median_template_cfd_timewalk_shape | 1383 | 0.291 | 0.8438 | 0.9963 | 0.1057 | 0 |
| energy_bin | q3 | 1d_cnn | 1291 | 0.8715 | 4.108 | 0.9775 | 0.09034 | 0.2424 |
| energy_bin | q3 | compact_waveform_transformer | 1291 | 2.172 | 6.391 | 1.002 | 0.09034 | 0.4469 |
| energy_bin | q3 | gradient_boosted_trees | 1291 | -0.722 | 3.423 | 1.006 | 0.09034 | 0.1673 |
| energy_bin | q3 | mlp | 1291 | -0.9882 | 3.924 | 1.006 | 0.09034 | 0.2091 |
| energy_bin | q3 | ridge | 1291 | -0.633 | 3.856 | 1.005 | 0.09034 | 0.2177 |
| energy_bin | q3 | shape_time_gate_transformer_new | 1291 | -0.6885 | 5.368 | 1.019 | 0.09034 | 0.3354 |
| energy_bin | q3 | traditional_median_template_cfd_timewalk_shape | 1291 | 0.4238 | 0.8762 | 0.9963 | 0.09034 | 0 |
| energy_bin | q4_high | 1d_cnn | 1011 | -2.014 | 5.34 | 1.002 | 0.06094 | 0.3798 |
| energy_bin | q4_high | compact_waveform_transformer | 1011 | -2.963 | 5.752 | 1.097 | 0.06094 | 0.4491 |
| energy_bin | q4_high | gradient_boosted_trees | 1011 | -1.053 | 3.569 | 1.014 | 0.06094 | 0.1998 |
| energy_bin | q4_high | mlp | 1011 | -1.013 | 4.213 | 1.025 | 0.06094 | 0.2661 |
| energy_bin | q4_high | ridge | 1011 | -0.8553 | 3.836 | 0.9996 | 0.06094 | 0.2127 |
| energy_bin | q4_high | shape_time_gate_transformer_new | 1011 | -2.079 | 5.018 | 0.9728 | 0.06094 | 0.3373 |
| energy_bin | q4_high | traditional_median_template_cfd_timewalk_shape | 1011 | 0.2035 | 1.065 | 0.994 | 0.06094 | 0 |
| late_tail_morphology | compact | 1d_cnn | 2928 | -1.598 | 5.183 | 0.9532 | 0.1471 | 0.3361 |
| late_tail_morphology | compact | compact_waveform_transformer | 2928 | 2.753 | 6.657 | 1.12 | 0.1471 | 0.4846 |
| late_tail_morphology | compact | gradient_boosted_trees | 2928 | -1.371 | 3.198 | 0.9782 | 0.1471 | 0.1407 |
| late_tail_morphology | compact | mlp | 2928 | -1.864 | 3.689 | 0.9805 | 0.1471 | 0.1906 |
| late_tail_morphology | compact | ridge | 2928 | -1.158 | 4.02 | 1.007 | 0.1471 | 0.2128 |
| late_tail_morphology | compact | shape_time_gate_transformer_new | 2928 | -2.163 | 5.871 | 0.9131 | 0.1471 | 0.417 |
| late_tail_morphology | compact | traditional_median_template_cfd_timewalk_shape | 2928 | 0.3215 | 0.9619 | 0.9954 | 0.1471 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 519 | -1.375 | 3.982 | 0.8224 | 0.03613 | 0.264 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 519 | -0.4813 | 5.974 | 0.5706 | 0.03613 | 0.4143 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 519 | 0.11 | 3.209 | 0.9502 | 0.03613 | 0.131 |
| late_tail_morphology | diffuse_tail | mlp | 519 | -0.2081 | 3.941 | 0.863 | 0.03613 | 0.237 |
| late_tail_morphology | diffuse_tail | ridge | 519 | -0.3752 | 3.361 | 1.08 | 0.03613 | 0.1618 |
| late_tail_morphology | diffuse_tail | shape_time_gate_transformer_new | 519 | -0.6884 | 3.516 | 0.8572 | 0.03613 | 0.1946 |
| late_tail_morphology | diffuse_tail | traditional_median_template_cfd_timewalk_shape | 519 | 0.5249 | 0.8819 | 0.9683 | 0.03613 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 343 | -1.617 | 7.256 | 1.066 | 0.6202 | 0.3994 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 343 | 0.9985 | 6.752 | 1.039 | 0.6202 | 0.4548 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 343 | -0.9705 | 2.928 | 1.07 | 0.6202 | 0.1691 |
| late_tail_morphology | late_derivative_bump | mlp | 343 | -1.454 | 3.805 | 0.9848 | 0.6202 | 0.2653 |
| late_tail_morphology | late_derivative_bump | ridge | 343 | -0.4727 | 3.383 | 0.977 | 0.6202 | 0.2099 |
| late_tail_morphology | late_derivative_bump | shape_time_gate_transformer_new | 343 | -0.472 | 4.942 | 1.068 | 0.6202 | 0.3324 |
| late_tail_morphology | late_derivative_bump | traditional_median_template_cfd_timewalk_shape | 343 | 0.07499 | 1.029 | 0.999 | 0.6202 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1136 | 0.8997 | 5.312 | 1.056 | 0.2066 | 0.3363 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1136 | 1.415 | 7.076 | 1.124 | 0.2066 | 0.4322 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1136 | 0.4045 | 4.31 | 0.9962 | 0.2066 | 0.257 |
| late_tail_morphology | late_rising_tail | mlp | 1136 | 0.3787 | 4.214 | 1.006 | 0.2066 | 0.2509 |
| late_tail_morphology | late_rising_tail | ridge | 1136 | 0.631 | 3.712 | 0.9999 | 0.2066 | 0.2245 |
| late_tail_morphology | late_rising_tail | shape_time_gate_transformer_new | 1136 | 0.1359 | 5.052 | 0.9997 | 0.2066 | 0.309 |
| late_tail_morphology | late_rising_tail | traditional_median_template_cfd_timewalk_shape | 1136 | -0.03994 | 0.9446 | 0.9919 | 0.2066 | 0 |
| peak_phase_bin | early_phase | 1d_cnn | 2179 | -0.6981 | 5.29 | 1.05 | 0.1579 | 0.3341 |
| peak_phase_bin | early_phase | compact_waveform_transformer | 2179 | 1.737 | 7.285 | 1.044 | 0.1579 | 0.4924 |
| peak_phase_bin | early_phase | gradient_boosted_trees | 2179 | -0.8667 | 3.64 | 1.013 | 0.1579 | 0.1941 |
| peak_phase_bin | early_phase | mlp | 2179 | -1.063 | 4.078 | 1.012 | 0.1579 | 0.2295 |
| peak_phase_bin | early_phase | ridge | 2179 | -0.5274 | 4.077 | 1.01 | 0.1579 | 0.2249 |
| peak_phase_bin | early_phase | shape_time_gate_transformer_new | 2179 | -1.648 | 5.535 | 1.034 | 0.1579 | 0.3607 |
| peak_phase_bin | early_phase | traditional_median_template_cfd_timewalk_shape | 2179 | 0.2741 | 0.9644 | 0.9943 | 0.1579 | 0 |
| peak_phase_bin | late_phase | 1d_cnn | 1169 | -1.535 | 5.559 | 1.04 | 0.1698 | 0.3456 |
| peak_phase_bin | late_phase | compact_waveform_transformer | 1169 | 2.017 | 6.493 | 1.015 | 0.1698 | 0.4457 |
| peak_phase_bin | late_phase | gradient_boosted_trees | 1169 | -1.03 | 3.393 | 1.005 | 0.1698 | 0.1557 |
| peak_phase_bin | late_phase | mlp | 1169 | -1.365 | 3.878 | 1.003 | 0.1698 | 0.2079 |
| peak_phase_bin | late_phase | ridge | 1169 | -0.4756 | 3.856 | 0.9987 | 0.1698 | 0.2044 |
| peak_phase_bin | late_phase | shape_time_gate_transformer_new | 1169 | -0.6444 | 5.764 | 0.9408 | 0.1698 | 0.3781 |
| peak_phase_bin | late_phase | traditional_median_template_cfd_timewalk_shape | 1169 | 0.2692 | 0.9149 | 0.9951 | 0.1698 | 0 |
| peak_phase_bin | mid_phase | 1d_cnn | 1578 | -0.9576 | 4.92 | 1.01 | 0.2246 | 0.3219 |
| peak_phase_bin | mid_phase | compact_waveform_transformer | 1578 | 2.319 | 6.051 | 1.017 | 0.2246 | 0.4354 |
| peak_phase_bin | mid_phase | gradient_boosted_trees | 1578 | -0.732 | 3.42 | 1.007 | 0.2246 | 0.1426 |
| peak_phase_bin | mid_phase | mlp | 1578 | -1.098 | 3.9 | 1.01 | 0.2246 | 0.199 |
| peak_phase_bin | mid_phase | ridge | 1578 | -0.3295 | 3.975 | 1.015 | 0.2246 | 0.1933 |
| peak_phase_bin | mid_phase | shape_time_gate_transformer_new | 1578 | -1.089 | 5.244 | 1.012 | 0.2246 | 0.3542 |
| peak_phase_bin | mid_phase | traditional_median_template_cfd_timewalk_shape | 1578 | 0.1575 | 0.9689 | 0.9965 | 0.2246 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1505 | -1.176 | 7.434 | 1.024 | 0.4166 | 0.4359 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1505 | 0.3719 | 6.958 | 1.045 | 0.4166 | 0.4738 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1505 | -0.8431 | 3.643 | 1.014 | 0.4166 | 0.1887 |
| pedestal_drift_bin | high | mlp | 1505 | -0.7823 | 4.019 | 1.012 | 0.4166 | 0.2259 |
| pedestal_drift_bin | high | ridge | 1505 | -0.3052 | 4.061 | 1.004 | 0.4166 | 0.2213 |
| pedestal_drift_bin | high | shape_time_gate_transformer_new | 1505 | -1.144 | 7.894 | 0.9733 | 0.4166 | 0.5136 |
| pedestal_drift_bin | high | traditional_median_template_cfd_timewalk_shape | 1505 | 0.1593 | 0.9569 | 0.9959 | 0.4166 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1660 | -0.8859 | 4.541 | 1.04 | 0.08374 | 0.2807 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1660 | 2.663 | 6.367 | 1.024 | 0.08374 | 0.4602 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1660 | -0.9412 | 3.495 | 1.014 | 0.08374 | 0.1614 |
| pedestal_drift_bin | low | mlp | 1660 | -1.15 | 3.828 | 1.018 | 0.08374 | 0.2018 |
| pedestal_drift_bin | low | ridge | 1660 | -0.5159 | 3.896 | 1.019 | 0.08374 | 0.2127 |
| pedestal_drift_bin | low | shape_time_gate_transformer_new | 1660 | -1.226 | 4.688 | 1.021 | 0.08374 | 0.2964 |
| pedestal_drift_bin | low | traditional_median_template_cfd_timewalk_shape | 1660 | 0.2731 | 0.9445 | 0.9942 | 0.08374 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1761 | -0.8913 | 4.617 | 1.03 | 0.07439 | 0.2942 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1761 | 2.584 | 6.274 | 0.9954 | 0.07439 | 0.4566 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1761 | -0.8417 | 3.399 | 1.005 | 0.07439 | 0.1579 |
| pedestal_drift_bin | mid | mlp | 1761 | -1.44 | 3.936 | 1.005 | 0.07439 | 0.2169 |
| pedestal_drift_bin | mid | ridge | 1761 | -0.5262 | 3.895 | 1.008 | 0.07439 | 0.1976 |
| pedestal_drift_bin | mid | shape_time_gate_transformer_new | 1761 | -1.184 | 4.69 | 1.009 | 0.07439 | 0.2964 |
| pedestal_drift_bin | mid | traditional_median_template_cfd_timewalk_shape | 1761 | 0.2612 | 0.9576 | 0.9937 | 0.07439 | 0 |
| pid_sideband | central | 1d_cnn | 3369 | -0.7767 | 4.507 | 1.037 | 0.08489 | 0.2781 |
| pid_sideband | central | compact_waveform_transformer | 3369 | 2.891 | 6.202 | 1.014 | 0.08489 | 0.4672 |
| pid_sideband | central | gradient_boosted_trees | 3369 | -0.834 | 3.444 | 1.011 | 0.08489 | 0.163 |
| pid_sideband | central | mlp | 3369 | -1.025 | 3.924 | 1.012 | 0.08489 | 0.2039 |
| pid_sideband | central | ridge | 3369 | -0.3583 | 4.008 | 1.015 | 0.08489 | 0.2122 |
| pid_sideband | central | shape_time_gate_transformer_new | 3369 | -1.184 | 4.741 | 1.017 | 0.08489 | 0.301 |
| pid_sideband | central | traditional_median_template_cfd_timewalk_shape | 3369 | 0.1812 | 0.9512 | 0.9943 | 0.08489 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 771 | -2.855 | 10.05 | 0.5723 | 0.7372 | 0.6122 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 771 | -2.181 | 6.736 | 0.7806 | 0.7372 | 0.4202 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 771 | -1.175 | 3.4 | 1.083 | 0.7372 | 0.1803 |
| pid_sideband | high_duplicate | mlp | 771 | -1.328 | 3.904 | 0.9628 | 0.7372 | 0.2218 |
| pid_sideband | high_duplicate | ridge | 771 | -0.8544 | 4.243 | 0.9322 | 0.7372 | 0.2438 |
| pid_sideband | high_duplicate | shape_time_gate_transformer_new | 771 | -4.215 | 10.66 | 0.5488 | 0.7372 | 0.7639 |
| pid_sideband | high_duplicate | traditional_median_template_cfd_timewalk_shape | 771 | 0.2911 | 0.9978 | 0.9916 | 0.7372 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 786 | -0.9945 | 4.802 | 1.028 | 0.05416 | 0.2939 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 786 | 1.846 | 6.983 | 0.9759 | 0.05416 | 0.4873 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 786 | -0.7333 | 3.669 | 1.012 | 0.05416 | 0.1807 |
| pid_sideband | low_duplicate | mlp | 786 | -1.308 | 4.093 | 1.011 | 0.05416 | 0.2532 |
| pid_sideband | low_duplicate | ridge | 786 | -0.5519 | 3.623 | 1.005 | 0.05416 | 0.1667 |
| pid_sideband | low_duplicate | shape_time_gate_transformer_new | 786 | -0.5664 | 4.253 | 0.9826 | 0.05416 | 0.2341 |
| pid_sideband | low_duplicate | traditional_median_template_cfd_timewalk_shape | 786 | 0.4464 | 0.9342 | 0.9928 | 0.05416 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1524 | -2.011 | 4.846 | 0.9129 | 0.03696 | 0.3169 |
| pileup_separation_bin | close | compact_waveform_transformer | 1524 | 1.318 | 6.515 | 0.7597 | 0.03696 | 0.4357 |
| pileup_separation_bin | close | gradient_boosted_trees | 1524 | -1.234 | 3.187 | 0.9833 | 0.03696 | 0.1444 |
| pileup_separation_bin | close | mlp | 1524 | -1.609 | 3.855 | 0.9758 | 0.03696 | 0.2093 |
| pileup_separation_bin | close | ridge | 1524 | -1.238 | 3.733 | 1.036 | 0.03696 | 0.2198 |
| pileup_separation_bin | close | shape_time_gate_transformer_new | 1524 | -1.665 | 4.852 | 1.131 | 0.03696 | 0.3438 |
| pileup_separation_bin | close | traditional_median_template_cfd_timewalk_shape | 1524 | 0.3388 | 0.9646 | 0.9971 | 0.03696 | 0 |
| pileup_separation_bin | late | 1d_cnn | 7 | -7.969 | 6.607 | 1.236 | 0.1168 | 0.5714 |
| pileup_separation_bin | late | compact_waveform_transformer | 7 | -12.4 | 8.579 | 1.068 | 0.1168 | 0.8571 |
| pileup_separation_bin | late | gradient_boosted_trees | 7 | -1.948 | 3.055 | 1.169 | 0.1168 | 0.1429 |
| pileup_separation_bin | late | mlp | 7 | -4.802 | 5.005 | 0.9425 | 0.1168 | 0.5714 |
| pileup_separation_bin | late | ridge | 7 | 0.8157 | 6.615 | 0.7533 | 0.1168 | 0.2857 |
| pileup_separation_bin | late | shape_time_gate_transformer_new | 7 | -4.596 | 3.525 | 0.8952 | 0.1168 | 0.4286 |
| pileup_separation_bin | late | traditional_median_template_cfd_timewalk_shape | 7 | -0.1253 | 0.8727 | 0.9709 | 0.1168 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1000 | -0.06138 | 6.29 | 0.9541 | 0.1251 | 0.4 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1000 | -1.6 | 6.513 | 1.076 | 0.1251 | 0.438 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1000 | -1.401 | 3.232 | 0.9735 | 0.1251 | 0.154 |
| pileup_separation_bin | mid | mlp | 1000 | -1.935 | 3.872 | 0.9651 | 0.1251 | 0.232 |
| pileup_separation_bin | mid | ridge | 1000 | -1.103 | 4.204 | 0.9844 | 0.1251 | 0.244 |
| pileup_separation_bin | mid | shape_time_gate_transformer_new | 1000 | -2.838 | 7.047 | 0.925 | 0.1251 | 0.535 |
| pileup_separation_bin | mid | traditional_median_template_cfd_timewalk_shape | 1000 | 0.4855 | 0.9334 | 0.9936 | 0.1251 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2395 | -0.5344 | 4.774 | 1.059 | 0.2984 | 0.3144 |
| pileup_separation_bin | none | compact_waveform_transformer | 2395 | 3.712 | 6.017 | 1.007 | 0.2984 | 0.4898 |
| pileup_separation_bin | none | gradient_boosted_trees | 2395 | -0.3546 | 3.768 | 1.005 | 0.2984 | 0.19 |
| pileup_separation_bin | none | mlp | 2395 | -0.4495 | 3.934 | 1.006 | 0.2984 | 0.2096 |
| pileup_separation_bin | none | ridge | 2395 | 0.1159 | 3.544 | 1.003 | 0.2984 | 0.1891 |
| pileup_separation_bin | none | shape_time_gate_transformer_new | 2395 | -0.4459 | 4.816 | 0.986 | 0.2984 | 0.3027 |
| pileup_separation_bin | none | traditional_median_template_cfd_timewalk_shape | 2395 | 0.08007 | 0.9489 | 0.9969 | 0.2984 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1651 | -1.828 | 6.712 | 0.9016 | 0.3634 | 0.464 |
| pulse_shape_class | compact | compact_waveform_transformer | 1651 | 1.946 | 6.761 | 1.193 | 0.3634 | 0.4537 |
| pulse_shape_class | compact | gradient_boosted_trees | 1651 | -1.605 | 3.384 | 0.9836 | 0.3634 | 0.1532 |
| pulse_shape_class | compact | mlp | 1651 | -1.83 | 3.758 | 0.9688 | 0.3634 | 0.1908 |
| pulse_shape_class | compact | ridge | 1651 | -0.6952 | 4.358 | 0.9885 | 0.3634 | 0.2502 |
| pulse_shape_class | compact | shape_time_gate_transformer_new | 1651 | -3.361 | 7.501 | 0.8399 | 0.3634 | 0.5645 |
| pulse_shape_class | compact | traditional_median_template_cfd_timewalk_shape | 1651 | 0.236 | 1.04 | 0.9902 | 0.3634 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1680 | 0.04166 | 4.908 | 1.056 | 0.1512 | 0.3125 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1680 | 0.8778 | 6.233 | 1.084 | 0.1512 | 0.4262 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1680 | 0.2344 | 4.024 | 0.9974 | 0.1512 | 0.2179 |
| pulse_shape_class | late_tail | mlp | 1680 | 0.186 | 4.137 | 1.001 | 0.1512 | 0.2464 |
| pulse_shape_class | late_tail | ridge | 1680 | 0.3122 | 3.608 | 1.002 | 0.1512 | 0.2048 |
| pulse_shape_class | late_tail | shape_time_gate_transformer_new | 1680 | -0.2601 | 4.599 | 0.9985 | 0.1512 | 0.272 |
| pulse_shape_class | late_tail | traditional_median_template_cfd_timewalk_shape | 1680 | 0.1003 | 0.939 | 0.991 | 0.1512 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1595 | -1.474 | 4.15 | 0.8405 | 0.02692 | 0.2188 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1595 | 3.26 | 6.613 | 0.7899 | 0.02692 | 0.5116 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1595 | -1.114 | 2.921 | 0.9617 | 0.02692 | 0.1323 |
| pulse_shape_class | nominal | mlp | 1595 | -1.784 | 3.597 | 0.9335 | 0.02692 | 0.2056 |
| pulse_shape_class | nominal | ridge | 1595 | -1.241 | 3.674 | 1.118 | 0.02692 | 0.1737 |
| pulse_shape_class | nominal | shape_time_gate_transformer_new | 1595 | -1.405 | 4.344 | 1.15 | 0.02692 | 0.2495 |
| pulse_shape_class | nominal | traditional_median_template_cfd_timewalk_shape | 1595 | 0.3485 | 0.9054 | 0.9783 | 0.02692 | 0 |
| q_template_error_bin | moderate_shape | 1d_cnn | 1767 | 0.3341 | 4.536 | 0.9708 | 0.05161 | 0.2666 |
| q_template_error_bin | moderate_shape | compact_waveform_transformer | 1767 | 2.677 | 7.267 | 0.9437 | 0.05161 | 0.5325 |
| q_template_error_bin | moderate_shape | gradient_boosted_trees | 1767 | -1.166 | 3.373 | 1.008 | 0.05161 | 0.1375 |
| q_template_error_bin | moderate_shape | mlp | 1767 | -1.384 | 3.94 | 1.012 | 0.05161 | 0.2088 |
| q_template_error_bin | moderate_shape | ridge | 1767 | 0.06752 | 4.419 | 1.113 | 0.05161 | 0.2569 |
| q_template_error_bin | moderate_shape | shape_time_gate_transformer_new | 1767 | -1.317 | 5.8 | 1.203 | 0.05161 | 0.3962 |
| q_template_error_bin | moderate_shape | traditional_median_template_cfd_timewalk_shape | 1767 | 0.4396 | 0.9012 | 0.9963 | 0.05161 | 0 |
| q_template_error_bin | shape_outlier | 1d_cnn | 1575 | 0.139 | 8.086 | 1.056 | 0.4962 | 0.4603 |
| q_template_error_bin | shape_outlier | compact_waveform_transformer | 1575 | 0.304 | 6.658 | 1.062 | 0.4962 | 0.4171 |
| q_template_error_bin | shape_outlier | gradient_boosted_trees | 1575 | -0.2691 | 3.931 | 1.006 | 0.4962 | 0.2324 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | moderate | 4.703 | curved | 5.99 | 1.286 |
| curvature_energy_bin | shape_time_gate_transformer_new | 3 | moderate | 5.189 | curved | 6.277 | 1.088 |
| curvature_energy_bin | mlp | 3 | smooth | 3.744 | curved | 4.219 | 0.4748 |
| curvature_energy_bin | compact_waveform_transformer | 3 | moderate | 5.77 | curved | 6.196 | 0.4256 |
| curvature_energy_bin | ridge | 3 | smooth | 3.76 | curved | 4.166 | 0.4058 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.361 | moderate | 3.593 | 0.2323 |
| curvature_energy_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate | 0.8717 | curved | 1.055 | 0.183 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.524 | slow | 7.809 | 3.285 |
| derivative_onset_bin | shape_time_gate_transformer_new | 3 | sharp | 4.902 | slow | 6.607 | 1.705 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.034 | slow | 4.136 | 1.102 |
| derivative_onset_bin | mlp | 3 | nominal | 3.663 | slow | 4.049 | 0.3857 |
| derivative_onset_bin | compact_waveform_transformer | 3 | slow | 6.411 | nominal | 6.691 | 0.2796 |
| derivative_onset_bin | ridge | 3 | nominal | 3.745 | sharp | 3.877 | 0.1324 |
| derivative_onset_bin | traditional_median_template_cfd_timewalk_shape | 3 | sharp | 0.9183 | slow | 0.9706 | 0.05231 |
| energy_bin | 1d_cnn | 4 | q3 | 4.108 | q1_low | 6.265 | 2.158 |
| energy_bin | shape_time_gate_transformer_new | 4 | q4_high | 5.018 | q1_low | 6.399 | 1.381 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 5.6 | q3 | 6.391 | 0.7902 |
| energy_bin | mlp | 4 | q1_low | 3.706 | q4_high | 4.213 | 0.5068 |
| energy_bin | traditional_median_template_cfd_timewalk_shape | 4 | q2 | 0.8438 | q1_low | 1.109 | 0.2653 |
| energy_bin | ridge | 4 | q1_low | 3.773 | q2 | 4.02 | 0.2467 |
| energy_bin | gradient_boosted_trees | 4 | q3 | 3.423 | q4_high | 3.569 | 0.1462 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 3.982 | late_derivative_bump | 7.256 | 3.274 |
| late_tail_morphology | shape_time_gate_transformer_new | 4 | diffuse_tail | 3.516 | compact | 5.871 | 2.354 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 2.928 | late_rising_tail | 4.31 | 1.381 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 5.974 | late_rising_tail | 7.076 | 1.102 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.361 | compact | 4.02 | 0.6593 |
| late_tail_morphology | mlp | 4 | compact | 3.689 | late_rising_tail | 4.214 | 0.5245 |
| late_tail_morphology | traditional_median_template_cfd_timewalk_shape | 4 | diffuse_tail | 0.8819 | late_derivative_bump | 1.029 | 0.1469 |
| peak_phase_bin | compact_waveform_transformer | 3 | mid_phase | 6.051 | early_phase | 7.285 | 1.234 |
| peak_phase_bin | 1d_cnn | 3 | mid_phase | 4.92 | late_phase | 5.559 | 0.6386 |
| peak_phase_bin | shape_time_gate_transformer_new | 3 | mid_phase | 5.244 | late_phase | 5.764 | 0.5197 |
| peak_phase_bin | gradient_boosted_trees | 3 | late_phase | 3.393 | early_phase | 3.64 | 0.2477 |
| peak_phase_bin | ridge | 3 | late_phase | 3.856 | early_phase | 4.077 | 0.2216 |
| peak_phase_bin | mlp | 3 | late_phase | 3.878 | early_phase | 4.078 | 0.2 |
| peak_phase_bin | traditional_median_template_cfd_timewalk_shape | 3 | late_phase | 0.9149 | mid_phase | 0.9689 | 0.05397 |
| pedestal_drift_bin | shape_time_gate_transformer_new | 3 | low | 4.688 | high | 7.894 | 3.206 |
| pedestal_drift_bin | 1d_cnn | 3 | low | 4.541 | high | 7.434 | 2.892 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 6.274 | high | 6.958 | 0.6847 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 3.399 | high | 3.643 | 0.2437 |
| pedestal_drift_bin | mlp | 3 | low | 3.828 | high | 4.019 | 0.1912 |
| pedestal_drift_bin | ridge | 3 | mid | 3.895 | high | 4.061 | 0.1658 |
| pedestal_drift_bin | traditional_median_template_cfd_timewalk_shape | 3 | low | 0.9445 | mid | 0.9576 | 0.01315 |
| pid_sideband | shape_time_gate_transformer_new | 3 | low_duplicate | 4.253 | high_duplicate | 10.66 | 6.406 |
| pid_sideband | 1d_cnn | 3 | central | 4.507 | high_duplicate | 10.05 | 5.543 |
| pid_sideband | compact_waveform_transformer | 3 | central | 6.202 | low_duplicate | 6.983 | 0.7817 |
| pid_sideband | ridge | 3 | low_duplicate | 3.623 | high_duplicate | 4.243 | 0.6205 |
| pid_sideband | gradient_boosted_trees | 3 | high_duplicate | 3.4 | low_duplicate | 3.669 | 0.269 |
| pid_sideband | mlp | 3 | high_duplicate | 3.904 | low_duplicate | 4.093 | 0.1888 |
| pid_sideband | traditional_median_template_cfd_timewalk_shape | 3 | low_duplicate | 0.9342 | high_duplicate | 0.9978 | 0.06365 |
| pileup_separation_bin | shape_time_gate_transformer_new | 4 | late | 3.525 | mid | 7.047 | 3.522 |
| pileup_separation_bin | ridge | 4 | none | 3.544 | late | 6.615 | 3.072 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 6.017 | late | 8.579 | 2.562 |
| pileup_separation_bin | 1d_cnn | 4 | none | 4.774 | late | 6.607 | 1.833 |
| pileup_separation_bin | mlp | 4 | close | 3.855 | late | 5.005 | 1.15 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 3.055 | none | 3.768 | 0.7124 |
| pileup_separation_bin | traditional_median_template_cfd_timewalk_shape | 4 | late | 0.8727 | close | 0.9646 | 0.0919 |
| pulse_shape_class | shape_time_gate_transformer_new | 3 | nominal | 4.344 | compact | 7.501 | 3.157 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.15 | compact | 6.712 | 2.562 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.921 | late_tail | 4.024 | 1.103 |
| pulse_shape_class | ridge | 3 | late_tail | 3.608 | compact | 4.358 | 0.7506 |
| pulse_shape_class | mlp | 3 | nominal | 3.597 | late_tail | 4.137 | 0.54 |
| pulse_shape_class | compact_waveform_transformer | 3 | late_tail | 6.233 | compact | 6.761 | 0.5282 |
| pulse_shape_class | traditional_median_template_cfd_timewalk_shape | 3 | nominal | 0.9054 | compact | 1.04 | 0.1344 |
| q_template_error_bin | shape_time_gate_transformer_new | 3 | template_like | 3.427 | shape_outlier | 8.24 | 4.812 |
| q_template_error_bin | 1d_cnn | 3 | template_like | 3.841 | shape_outlier | 8.086 | 4.245 |
| q_template_error_bin | compact_waveform_transformer | 3 | template_like | 5.175 | moderate_shape | 7.267 | 2.092 |
| q_template_error_bin | ridge | 3 | template_like | 3.247 | moderate_shape | 4.419 | 1.173 |
| q_template_error_bin | gradient_boosted_trees | 3 | template_like | 2.903 | shape_outlier | 3.931 | 1.028 |
| q_template_error_bin | mlp | 3 | template_like | 3.519 | shape_outlier | 4.051 | 0.532 |
| q_template_error_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate_shape | 0.9012 | template_like | 0.979 | 0.07775 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.78 | linear | 7.011 | 1.231 |
| saturation_onset_bin | shape_time_gate_transformer_new | 2 | near_saturation | 4.72 | linear | 5.817 | 1.098 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.457 | linear | 5.487 | 1.03 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.695 | linear | 4.054 | 0.3587 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.871 | linear | 4.07 | 0.1982 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.394 | linear | 3.538 | 0.1446 |
| saturation_onset_bin | traditional_median_template_cfd_timewalk_shape | 2 | near_saturation | 0.9085 | linear | 0.9776 | 0.06909 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 34 | -0.8072 | 3.43 | 2.824 | 3.81 | -0.02686 | 0.165 |
| full_derivative_gradient_boosted_trees | 77 | -0.8439 | 3.457 | 2.884 | 3.851 | 0 | 0.1675 |
| amplitude_cfd_no_derivative | 5 | -0.5002 | 3.894 | 3.411 | 4.564 | 0.437 | 0.2164 |
| derivative_only | 43 | -0.5983 | 3.96 | 3.45 | 4.711 | 0.5031 | 0.2117 |
| late_tail_curvature_window_only | 17 | -0.3798 | 4.426 | 3.893 | 5.131 | 0.9693 | 0.2631 |
| onset_derivative_window_only | 14 | -0.6963 | 4.796 | 4.116 | 6.187 | 1.339 | 0.3114 |
| pretrigger_derivative_only | 7 | -4.071 | 17.67 | 17.09 | 20.24 | 14.22 | 0.5968 |

## Interpretation, Systematics, and Caveats

This benchmark measures relative transfer on a reproducible waveform-derived
timing residual.  The raw ROOT files do not contain an independent external
picosecond timing truth for each pulse, so the numerical winner should not be
read as an absolute detector timing limit.  It answers the narrower ticket
question: whether derivative/curvature descriptions improve run-held-out
arrival-time residual prediction beyond a strong CFD/template derivative fit.

The run-block bootstrap is deliberately conservative for data-taking-period
transfer and can produce wider intervals than event bootstrap.  Neural models
are compact and trained under a fixed small epoch budget suitable for this
laptop worker; the study tests whether derivative-aware architectures naturally
outperform transparent timing fits, not whether exhaustive architecture search
can overfit the proxy.  Pedestal drift strata use raw pretrigger baseline
displacement from the run/stave median, so they are useful diagnostics but not
external electronics-state labels.

The result is consistent with the recent S41a/S40b timing family if the
traditional method remains competitive: transparent CFD/template corrections
capture most of the stable sub-sample timing signal, while derivative features
mainly expose where late tails and pedestal wander destabilize learned models.

Runtime was `93.3 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.11.14`.


## S66a Latent Atlas Addendum

The ticket-specific atlas treats each method as a latent representation, then
tests whether the representation yields stable held-out pulse-shape clusters
without using run labels as inputs.  The traditional representation is a
spline-template residual/PCA mixture: normalized waveform residuals relative to
the training-run template are compressed by PCA and clustered with a four-state
mixture surrogate.  Ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer
families use the same residual PCA basis augmented by the method's
leakage-controlled prediction or waveform/derivative channels.  The new
architecture is the derivative-gated masked waveform transformer inherited from
the S51a run-heldout panel.

Cluster stability is the median adjusted Rand index between held-out labels
from the full training fit and labels from `24`
bootstrap refits that resample training pulses and held-out runs.  A high ARI
therefore means the atlas is reproducible under both finite training support
and run-level transfer uncertainty.  Reconstruction error is the median
feature-space MSE after six-dimensional PCA compression and inverse transform.

| method                                         |   heldout_adjusted_rand_stability |   heldout_adjusted_rand_ci_low |   heldout_adjusted_rand_ci_high |   heldout_reconstruction_mse_median |   heldout_reconstruction_mse_ci_low |   heldout_reconstruction_mse_ci_high |   heldout_cluster_balance |   pca_variance_6d |
|:-----------------------------------------------|----------------------------------:|-------------------------------:|--------------------------------:|------------------------------------:|------------------------------------:|-------------------------------------:|--------------------------:|------------------:|
| traditional_median_template_cfd_timewalk_shape |                            0.9769 |                         0.9478 |                          0.9915 |                              4.42   |                              4.288  |                               4.674  |                    0.2741 |            0.9926 |
| 1d_cnn                                         |                            0.9761 |                         0.447  |                          0.9896 |                              0.2326 |                              0.2117 |                               0.2623 |                    0.2739 |            0.8779 |
| shape_time_gate_transformer_new                |                            0.9285 |                         0.4688 |                          0.9759 |                              0.45   |                              0.3852 |                               0.5613 |                    0.5272 |            0.7841 |
| compact_waveform_transformer                   |                            0.9277 |                         0.4707 |                          0.9819 |                              0.2915 |                              0.2477 |                               0.3397 |                    0.5278 |            0.7845 |
| ridge                                          |                            0.9137 |                         0.3336 |                          0.9664 |                         631800      |                         484300      |                          807900      |                    0.3756 |            0.8673 |
| gradient_boosted_trees                         |                            0.912  |                         0.2948 |                          0.9754 |                         620800      |                         534500      |                          790700      |                    0.3808 |            0.8671 |
| mlp                                            |                            0.4579 |                         0.3761 |                          0.9621 |                         628400      |                         558800      |                          738500      |                    0.3831 |            0.8671 |

### Cluster-Level Failure Map

| method                                         |   cluster |    n |   amplitude_median |   tail_fraction_median |   pedestal_baseline_median |   flat_top_samples_mean |   reconstruction_mse_median |   timing_abs_error_median_ns |   energy_proxy_area_median |   pid_inner_high_charge_fraction |
|:-----------------------------------------------|----------:|-----:|-------------------:|-----------------------:|---------------------------:|------------------------:|----------------------------:|-----------------------------:|---------------------------:|---------------------------------:|
| 1d_cnn                                         |         0 |  967 |               2951 |                 0.9619 |                       6938 |                   1.207 |                   0.859     |                       3.095  |                    12400   |                         0.003102 |
| 1d_cnn                                         |         1 | 3577 |               3186 |                 0.3095 |                       6920 |                   1.272 |                   0.1532    |                       3.301  |                    26100   |                         0.01482  |
| 1d_cnn                                         |         2 |  335 |               1728 |                -0.4902 |                       8475 |                   1.149 |                   0.4857    |                       6.718  |                     2459   |                         0.03582  |
| 1d_cnn                                         |         3 |   47 |               1140 |                -9.438  |                      10830 |                   1     |                  25.98      |                      18.61   |                   -25140   |                         0        |
| compact_waveform_transformer                   |         0 |  928 |               2906 |                 0.9668 |                       6940 |                   1.192 |                   3.852     |                       3.976  |                    11510   |                         0.001078 |
| compact_waveform_transformer                   |         1 | 1366 |               3566 |                 0.2313 |                       6938 |                   1.232 |                   0.2205    |                       3.637  |                    31110   |                         0.04173  |
| compact_waveform_transformer                   |         2 |  306 |               1588 |                -0.6632 |                       8720 |                   1.118 |                   2.239     |                       3.73   |                      -68.5 |                         0.01961  |
| compact_waveform_transformer                   |         3 | 2326 |               3032 |                 0.3357 |                       6917 |                   1.298 |                   0.07885   |                       5.348  |                    23810   |                         0.00172  |
| gradient_boosted_trees                         |         0 |  913 |               5324 |                 0.3421 |                       6784 |                   1.053 |                   1.119e+06 |                       2.053  |                    46020   |                         0.05476  |
| gradient_boosted_trees                         |         1 |   71 |               1154 |                -8.116  |                      11090 |                   1     |                   1.491e+07 |                       2.97   |                   -24990   |                         0        |
| gradient_boosted_trees                         |         2 |  892 |               2930 |                 0.9704 |                       6938 |                   1.194 |              195000         |                       2.858  |                    11800   |                         0.001121 |
| gradient_boosted_trees                         |         3 | 3050 |               2809 |                 0.2741 |                       6934 |                   1.329 |              748700         |                       2.327  |                    20870   |                         0.005574 |
| mlp                                            |         0 |  898 |               2922 |                 0.9701 |                       6938 |                   1.196 |              201100         |                       2.608  |                    11820   |                         0.001114 |
| mlp                                            |         1 |  918 |               5318 |                 0.342  |                       6787 |                   1.052 |                   1.136e+06 |                       2.781  |                    45970   |                         0.05447  |
| mlp                                            |         2 |   71 |               1154 |                -8.116  |                      11090 |                   1     |                   1.505e+07 |                       3.371  |                   -24990   |                         0        |
| mlp                                            |         3 | 3039 |               2809 |                 0.274  |                       6934 |                   1.329 |              754500         |                       2.863  |                    20860   |                         0.005594 |
| ridge                                          |         0 | 3076 |               2810 |                 0.2759 |                       6934 |                   1.329 |              760400         |                       2.581  |                    20840   |                         0.005527 |
| ridge                                          |         1 |   71 |               1154 |                -8.116  |                      11090 |                   1     |                   1.502e+07 |                       3.81   |                   -24990   |                         0        |
| ridge                                          |         2 |  907 |               5359 |                 0.342  |                       6783 |                   1.053 |                   1.106e+06 |                       2.564  |                    46120   |                         0.05513  |
| ridge                                          |         3 |  872 |               2942 |                 0.9715 |                       6938 |                   1.188 |              197800         |                       2.219  |                    11580   |                         0.001147 |
| shape_time_gate_transformer_new                |         0 |  921 |               2906 |                 0.9673 |                       6940 |                   1.192 |                   4.185     |                       3.699  |                    11360   |                         0.001086 |
| shape_time_gate_transformer_new                |         1 | 2329 |               3032 |                 0.3364 |                       6918 |                   1.298 |                   0.1212    |                       2.844  |                    23800   |                         0.001717 |
| shape_time_gate_transformer_new                |         2 | 1370 |               3566 |                 0.2313 |                       6937 |                   1.231 |                   0.2969    |                       5.468  |                    31110   |                         0.04161  |
| shape_time_gate_transformer_new                |         3 |  306 |               1588 |                -0.6632 |                       8720 |                   1.118 |                   3.198     |                       8.261  |                      -68.5 |                         0.01961  |
| traditional_median_template_cfd_timewalk_shape |         0 |  990 |               2945 |                 0.9605 |                       6937 |                   1.212 |                   4.4       |                       0.7351 |                    12550   |                         0.00202  |
| traditional_median_template_cfd_timewalk_shape |         1 |  302 |               1782 |                -0.5338 |                       8672 |                   1.119 |                  45.7       |                       0.7853 |                     1804   |                         0.06291  |
| traditional_median_template_cfd_timewalk_shape |         2 |   58 |               1136 |                -8.838  |                      11120 |                   1     |                1096         |                       1.077  |                   -26290   |                         0        |
| traditional_median_template_cfd_timewalk_shape |         3 | 3576 |               3174 |                 0.308  |                       6920 |                   1.273 |                   3.837     |                       0.7312 |                    26000   |                         0.01314  |

### Energy, PID, Pedestal, Tail, and Saturation Slices

| slice_axis           | slice                | method                                         |    n |   cluster_entropy |   reconstruction_mse_median |   timing_abs_error_median_ns |   energy_proxy_area_median |   pid_inner_high_charge_fraction |
|:---------------------|:---------------------|:-----------------------------------------------|-----:|------------------:|----------------------------:|-----------------------------:|---------------------------:|---------------------------------:|
| energy_slice_s66a    | high_energy          | 1d_cnn                                         | 1398 |            0.7107 |                   0.7083    |                       3.633  |                      40550 |                         0.04864  |
| energy_slice_s66a    | high_energy          | compact_waveform_transformer                   | 1398 |            1.486  |                   0.3579    |                       4.16   |                      40550 |                         0.04864  |
| energy_slice_s66a    | high_energy          | gradient_boosted_trees                         | 1398 |            1.319  |                   1.179e+06 |                       2.281  |                      40550 |                         0.04864  |
| energy_slice_s66a    | high_energy          | mlp                                            | 1398 |            1.317  |                   1.186e+06 |                       2.898  |                      40550 |                         0.04864  |
| energy_slice_s66a    | high_energy          | ridge                                          | 1398 |            1.323  |                   1.171e+06 |                       2.478  |                      40550 |                         0.04864  |
| energy_slice_s66a    | high_energy          | shape_time_gate_transformer_new                | 1398 |            1.483  |                   0.7606    |                       3.298  |                      40550 |                         0.04864  |
| energy_slice_s66a    | high_energy          | traditional_median_template_cfd_timewalk_shape | 1398 |            0.7641 |                   4.18      |                       0.8153 |                      40550 |                         0.04864  |
| energy_slice_s66a    | low_energy           | 1d_cnn                                         | 1670 |            1.496  |                   0.1348    |                       4.104  |                      10720 |                         0        |
| energy_slice_s66a    | low_energy           | compact_waveform_transformer                   | 1670 |            1.859  |                   0.271     |                       4.464  |                      10720 |                         0        |
| energy_slice_s66a    | low_energy           | gradient_boosted_trees                         | 1670 |            0.9463 |              412200         |                       2.506  |                      10720 |                         0        |
| energy_slice_s66a    | low_energy           | mlp                                            | 1670 |            0.9498 |              413000         |                       2.785  |                      10720 |                         0        |
| energy_slice_s66a    | low_energy           | ridge                                          | 1670 |            0.9366 |              430200         |                       2.601  |                      10720 |                         0        |
| energy_slice_s66a    | low_energy           | shape_time_gate_transformer_new                | 1670 |            1.859  |                   0.1931    |                       4.29   |                      10720 |                         0        |
| energy_slice_s66a    | low_energy           | traditional_median_template_cfd_timewalk_shape | 1670 |            1.483  |                   4.514     |                       0.7647 |                      10720 |                         0        |
| energy_slice_s66a    | mid_energy           | 1d_cnn                                         | 1858 |            0.8814 |                   0.2079    |                       2.901  |                      23800 |                         0        |
| energy_slice_s66a    | mid_energy           | compact_waveform_transformer                   | 1858 |            1.53   |                   0.2229    |                       4.868  |                      23800 |                         0        |
| energy_slice_s66a    | mid_energy           | gradient_boosted_trees                         | 1858 |            0.8833 |              535800         |                       2.289  |                      23800 |                         0        |
| energy_slice_s66a    | mid_energy           | mlp                                            | 1858 |            0.8944 |              540500         |                       2.818  |                      23800 |                         0        |
| energy_slice_s66a    | mid_energy           | ridge                                          | 1858 |            0.871  |              546800         |                       2.516  |                      23800 |                         0        |
| energy_slice_s66a    | mid_energy           | shape_time_gate_transformer_new                | 1858 |            1.528  |                   0.27      |                       3.477  |                      23800 |                         0        |
| energy_slice_s66a    | mid_energy           | traditional_median_template_cfd_timewalk_shape | 1858 |            0.8851 |                   4.514     |                       0.6831 |                      23800 |                         0        |
| late_tail_morphology | compact              | 1d_cnn                                         | 2928 |            0.5327 |                   0.1018    |                       3.622  |                      21230 |                         0.01878  |
| late_tail_morphology | compact              | compact_waveform_transformer                   | 2928 |            1.37   |                   0.08086   |                       4.825  |                      21230 |                         0.01878  |
| late_tail_morphology | compact              | gradient_boosted_trees                         | 2928 |            0.7639 |              593100         |                       2.368  |                      21230 |                         0.01878  |
| late_tail_morphology | compact              | mlp                                            | 2928 |            0.7661 |              595500         |                       2.905  |                      21230 |                         0.01878  |
| late_tail_morphology | compact              | ridge                                          | 2928 |            0.7625 |              599400         |                       2.782  |                      21230 |                         0.01878  |
| late_tail_morphology | compact              | shape_time_gate_transformer_new                | 2928 |            1.37   |                   0.09143   |                       4.207  |                      21230 |                         0.01878  |
| late_tail_morphology | compact              | traditional_median_template_cfd_timewalk_shape | 2928 |            0.4991 |                   4.671     |                       0.7317 |                      21230 |                         0.01878  |
| late_tail_morphology | diffuse_tail         | 1d_cnn                                         |  519 |            0.179  |                   1.732     |                       2.639  |                      35790 |                         0        |
| late_tail_morphology | diffuse_tail         | compact_waveform_transformer                   |  519 |            0.1031 |                   0.8536    |                       4.056  |                      35790 |                         0        |
| late_tail_morphology | diffuse_tail         | gradient_boosted_trees                         |  519 |            0.8724 |                   2.422e+06 |                       1.753  |                      35790 |                         0        |
| late_tail_morphology | diffuse_tail         | mlp                                            |  519 |            0.8748 |                   2.431e+06 |                       2.333  |                      35790 |                         0        |
| late_tail_morphology | diffuse_tail         | ridge                                          |  519 |            0.8649 |                   2.429e+06 |                       1.971  |                      35790 |                         0        |
| late_tail_morphology | diffuse_tail         | shape_time_gate_transformer_new                |  519 |            0.1149 |                   1.848     |                       2.315  |                      35790 |                         0        |
| late_tail_morphology | diffuse_tail         | traditional_median_template_cfd_timewalk_shape |  519 |            0.1985 |                   3.594     |                       0.7328 |                      35790 |                         0        |
| late_tail_morphology | late_derivative_bump | 1d_cnn                                         |  343 |            0.9596 |                   0.2571    |                       4.001  |                      31910 |                         0.03207  |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer                   |  343 |            1.665  |                   0.2473    |                       4.565  |                      31910 |                         0.03207  |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees                         |  343 |            1.474  |              793500         |                       2.018  |                      31910 |                         0.03207  |
| late_tail_morphology | late_derivative_bump | mlp                                            |  343 |            1.474  |              767600         |                       2.529  |                      31910 |                         0.03207  |
| late_tail_morphology | late_derivative_bump | ridge                                          |  343 |            1.474  |              783300         |                       2.127  |                      31910 |                         0.03207  |
| late_tail_morphology | late_derivative_bump | shape_time_gate_transformer_new                |  343 |            1.665  |                   0.6407    |                       2.91   |                      31910 |                         0.03207  |
| late_tail_morphology | late_derivative_bump | traditional_median_template_cfd_timewalk_shape |  343 |            1.008  |                   4.071     |                       0.7995 |                      31910 |                         0.03207  |
| late_tail_morphology | late_rising_tail     | 1d_cnn                                         | 1136 |            0.6552 |                   0.9834    |                       3.011  |                      14340 |                         0.001761 |
| late_tail_morphology | late_rising_tail     | compact_waveform_transformer                   | 1136 |            0.786  |                   2.896     |                       4.065  |                      14340 |                         0.001761 |
| late_tail_morphology | late_rising_tail     | gradient_boosted_trees                         | 1136 |            0.9392 |              290400         |                       2.783  |                      14340 |                         0.001761 |
| late_tail_morphology | late_rising_tail     | mlp                                            | 1136 |            0.9279 |              290800         |                       2.752  |                      14340 |                         0.001761 |
| late_tail_morphology | late_rising_tail     | ridge                                          | 1136 |            0.9772 |              284200         |                       2.224  |                      14340 |                         0.001761 |
| late_tail_morphology | late_rising_tail     | shape_time_gate_transformer_new                | 1136 |            0.7979 |                   3.514     |                       3.418  |                      14340 |                         0.001761 |
| late_tail_morphology | late_rising_tail     | traditional_median_template_cfd_timewalk_shape | 1136 |            0.6056 |                   4.268     |                       0.742  |                      14340 |                         0.001761 |
| pedestal_drift_bin   | high                 | 1d_cnn                                         | 1505 |            1.431  |                   0.3651    |                       4.29   |                      18310 |                         0.04518  |
| pedestal_drift_bin   | high                 | compact_waveform_transformer                   | 1505 |            1.898  |                   0.7699    |                       4.686  |                      18310 |                         0.04518  |
| pedestal_drift_bin   | high                 | gradient_boosted_trees                         | 1505 |            1.386  |                   1.123e+06 |                       2.464  |                      18310 |                         0.04518  |
| pedestal_drift_bin   | high                 | mlp                                            | 1505 |            1.389  |                   1.122e+06 |                       2.827  |                      18310 |                         0.04518  |
| pedestal_drift_bin   | high                 | ridge                                          | 1505 |            1.376  |                   1.127e+06 |                       2.716  |                      18310 |                         0.04518  |
| pedestal_drift_bin   | high                 | shape_time_gate_transformer_new                | 1505 |            1.896  |                   0.6833    |                       5.203  |                      18310 |                         0.04518  |
| pedestal_drift_bin   | high                 | traditional_median_template_cfd_timewalk_shape | 1505 |            1.432  |                   6.655     |                       0.7298 |                      18310 |                         0.04518  |
| pedestal_drift_bin   | low                  | 1d_cnn                                         | 1660 |            0.8094 |                   0.2077    |                       3.152  |                      22670 |                         0        |
| pedestal_drift_bin   | low                  | compact_waveform_transformer                   | 1660 |            1.467  |                   0.1993    |                       4.49   |                      22670 |                         0        |
| pedestal_drift_bin   | low                  | gradient_boosted_trees                         | 1660 |            1.396  |              464600         |                       2.419  |                      22670 |                         0        |
| pedestal_drift_bin   | low                  | mlp                                            | 1660 |            1.399  |              465000         |                       2.824  |                      22670 |                         0        |
| pedestal_drift_bin   | low                  | ridge                                          | 1660 |            1.386  |              462900         |                       2.461  |                      22670 |                         0        |
| pedestal_drift_bin   | low                  | shape_time_gate_transformer_new                | 1660 |            1.465  |                   0.3589    |                       3.333  |                      22670 |                         0        |
| pedestal_drift_bin   | low                  | traditional_median_template_cfd_timewalk_shape | 1660 |            0.8216 |                   4.129     |                       0.7371 |                      22670 |                         0        |
| pedestal_drift_bin   | mid                  | 1d_cnn                                         | 1761 |            0.7439 |                   0.1883    |                       3.177  |                      23530 |                         0        |
| pedestal_drift_bin   | mid                  | compact_waveform_transformer                   | 1761 |            1.408  |                   0.1989    |                       4.492  |                      23530 |                         0        |
| pedestal_drift_bin   | mid                  | gradient_boosted_trees                         | 1761 |            1.35   |              555500         |                       2.234  |                      23530 |                         0        |
| pedestal_drift_bin   | mid                  | mlp                                            | 1761 |            1.356  |              562600         |                       2.833  |                      23530 |                         0        |
| pedestal_drift_bin   | mid                  | ridge                                          | 1761 |            1.343  |              568700         |                       2.481  |                      23530 |                         0        |
| pedestal_drift_bin   | mid                  | shape_time_gate_transformer_new                | 1761 |            1.408  |                   0.3335    |                       3.261  |                      23530 |                         0        |
| pedestal_drift_bin   | mid                  | traditional_median_template_cfd_timewalk_shape | 1761 |            0.7513 |                   3.535     |                       0.7466 |                      23530 |                         0        |
| pid_proxy_class_s66a | inner_high_charge    | 1d_cnn                                         |   68 |            0.9205 |                   3.715     |                       4.828  |                      37100 |                         1        |
| pid_proxy_class_s66a | inner_high_charge    | compact_waveform_transformer                   |   68 |            0.8524 |                   1.397     |                      11.61   |                      37100 |                         1        |
| pid_proxy_class_s66a | inner_high_charge    | gradient_boosted_trees                         |   68 |            0.9157 |              846700         |                       2.568  |                      37100 |                         1        |
| pid_proxy_class_s66a | inner_high_charge    | mlp                                            |   68 |            0.9157 |              846000         |                       3.859  |                      37100 |                         1        |
| pid_proxy_class_s66a | inner_high_charge    | ridge                                          |   68 |            0.9157 |              762200         |                       3.885  |                      37100 |                         1        |
| pid_proxy_class_s66a | inner_high_charge    | shape_time_gate_transformer_new                |   68 |            0.8524 |                   2.073     |                      11.34   |                      37100 |                         1        |
| pid_proxy_class_s66a | inner_high_charge    | traditional_median_template_cfd_timewalk_shape |   68 |            1.032  |                   7.462     |                       0.7039 |                      37100 |                         1        |
| pid_proxy_class_s66a | other                | 1d_cnn                                         | 4858 |            1.124  |                   0.2251    |                       3.448  |                      21760 |                         0        |
| pid_proxy_class_s66a | other                | compact_waveform_transformer                   | 4858 |            1.723  |                   0.2863    |                       4.502  |                      21760 |                         0        |
| pid_proxy_class_s66a | other                | gradient_boosted_trees                         | 4858 |            1.405  |              618400         |                       2.356  |                      21760 |                         0        |
| pid_proxy_class_s66a | other                | mlp                                            | 4858 |            1.409  |              624700         |                       2.816  |                      21760 |                         0        |
| pid_proxy_class_s66a | other                | ridge                                          | 4858 |            1.395  |              628500         |                       2.519  |                      21760 |                         0        |
| pid_proxy_class_s66a | other                | shape_time_gate_transformer_new                | 4858 |            1.722  |                   0.4429    |                       3.679  |                      21760 |                         0        |
| pid_proxy_class_s66a | other                | traditional_median_template_cfd_timewalk_shape | 4858 |            1.117  |                   4.402     |                       0.7391 |                      21760 |                         0        |
| saturation_onset_bin | linear               | 1d_cnn                                         | 3557 |            1.227  |                   0.2788    |                       3.605  |                      20540 |                         0.01659  |
| saturation_onset_bin | linear               | compact_waveform_transformer                   | 3557 |            1.77   |                   0.3661    |                       4.681  |                      20540 |                         0.01659  |
| saturation_onset_bin | linear               | gradient_boosted_trees                         | 3557 |            1.448  |              538700         |                       2.417  |                      20540 |                         0.01659  |
| saturation_onset_bin | linear               | mlp                                            | 3557 |            1.452  |              542000         |                       2.87   |                      20540 |                         0.01659  |
| saturation_onset_bin | linear               | ridge                                          | 3557 |            1.439  |              547200         |                       2.586  |                      20540 |                         0.01659  |
| saturation_onset_bin | linear               | shape_time_gate_transformer_new                | 3557 |            1.769  |                   0.544     |                       3.896  |                      20540 |                         0.01659  |
| saturation_onset_bin | linear               | traditional_median_template_cfd_timewalk_shape | 3557 |            1.234  |                   4.614     |                       0.7574 |                      20540 |                         0.01659  |
| saturation_onset_bin | near_saturation      | 1d_cnn                                         | 1369 |            0.7918 |                   0.1639    |                       3.092  |                      23520 |                         0.006574 |
| saturation_onset_bin | near_saturation      | compact_waveform_transformer                   | 1369 |            1.536  |                   0.1616    |                       4.287  |                      23520 |                         0.006574 |
| saturation_onset_bin | near_saturation      | gradient_boosted_trees                         | 1369 |            1.266  |              844600         |                       2.261  |                      23520 |                         0.006574 |
| saturation_onset_bin | near_saturation      | mlp                                            | 1369 |            1.269  |              847900         |                       2.682  |                      23520 |                         0.006574 |
| saturation_onset_bin | near_saturation      | ridge                                          | 1369 |            1.249  |              841500         |                       2.409  |                      23520 |                         0.006574 |
| saturation_onset_bin | near_saturation      | shape_time_gate_transformer_new                | 1369 |            1.535  |                   0.2501    |                       3.216  |                      23520 |                         0.006574 |
| saturation_onset_bin | near_saturation      | traditional_median_template_cfd_timewalk_shape | 1369 |            0.7563 |                   4.067     |                       0.6782 |                      23520 |                         0.006574 |

### Leakage Controls and Caveats

The split remains by source run, and the latent-cluster step receives no run
identifier.  The PID quantity is a raw-derived proxy built from duplicate
readout support and high amplitude, not an external particle label.  Energy is
reported through charge/area proxy slices because the raw ROOT gate does not
carry a calibrated external deposited-energy truth for every selected pulse.
The atlas is therefore a reproducible morphology and downstream-risk map, not a
replacement for externally labeled PID or absolute calorimetric calibration.

## Queue Provenance

The required single claim command was run once as `tn-ticket claim testbeam-laptop-4 --project testbeam`
and returned the known null pseudo-ticket output.  The project queue was not
empty, so issue `#2545` was recovered without a second claim attempt by applying
`gh issue edit 2545 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`.
Completion is recorded with `tn-ticket done 2545`.  No novel follow-up ticket
was appended.

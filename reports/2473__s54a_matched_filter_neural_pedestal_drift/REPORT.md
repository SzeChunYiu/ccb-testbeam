# S54a Matched-Filter Timing Versus Neural Pulse-Shape Encoders

## Abstract

Ticket `2473` asks how matched-filter timing and neural
pulse-shape encoders transfer under pedestal-memory and current stratification.
The study first reproduces the registered B-stack selected-pulse count directly
from raw ROOT `h101/HRDv`, then constructs a run-held-out timing-residual
benchmark on the same digitized pulses.  A strong traditional
constant-fraction, median-template matched-filter/time-walk, cross-correlation,
and run-calibrated shape-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `matched_filter_residual_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_median_template_cfd_timewalk_shape`** as the
winner with `sigma_68 = 1.024 ns`
`[0.6246, 1.177]`.  The
traditional shape-time comparator obtains `1.024 ns`
`[0.6246, 1.177]`.

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

The traditional method starts from the audited CFD/template matched-filter baseline
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
| matched_filter_residual_transformer_new | new architecture | compact transformer over waveform, first derivative, and second derivative channels with matched-filter residual pooling |

The new architecture is sensible for this ticket because the hypothesis is not
generic waveform learning; it is that matched-filter residuals, edge shape,
curvature, and normalized shape-template channels localize pulse-shape timing
changes under pedestal drift.  The model embeds waveform, first derivative,
second derivative, and sample position at each of the 18 time samples.  A
derivative-magnitude gate weights transformer states before a single regression
head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_median_template_cfd_timewalk_shape | 4926 | 0.2806 | -0.263 | 0.6232 | 1.024 | 0.6246 | 1.177 | 0.9623 | 0.9949 | 0.1762 | 0 | 0 |
| gradient_boosted_trees | 4926 | -0.2823 | -1.708 | 0.6598 | 3.63 | 2.7 | 4.068 | 5.848 | 1 | 0.1762 | 0.1868 | 0.03776 |
| ridge | 4926 | -0.4135 | -1.424 | 0.5593 | 3.85 | 3.354 | 4.632 | 6.034 | 1.004 | 0.1762 | 0.2184 | 0.04344 |
| mlp | 4926 | -0.7372 | -1.806 | 0.3372 | 4.072 | 3.615 | 4.658 | 5.998 | 1.005 | 0.1762 | 0.2245 | 0.04304 |
| matched_filter_residual_transformer_new | 4926 | -0.6267 | -1.394 | 0.02851 | 4.694 | 4.239 | 5.431 | 7.187 | 0.9747 | 0.1762 | 0.2952 | 0.07105 |
| compact_waveform_transformer | 4926 | -0.345 | -1.133 | 0.295 | 5.746 | 5.364 | 6.533 | 7.626 | 1.019 | 0.1762 | 0.3676 | 0.1078 |
| 1d_cnn | 4926 | -1.067 | -2.023 | 0.03319 | 5.845 | 5.122 | 6.802 | 7.979 | 1.016 | 0.1762 | 0.3967 | 0.136 |

## Paired Deltas Against Traditional Shape-Time Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional shape-time comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_median_template_cfd_timewalk_shape | 2.605 | 1.679 | 3.179 | -0.563 | -2.006 | 0.6358 | 0.1868 |
| ridge | traditional_median_template_cfd_timewalk_shape | 2.826 | 2.306 | 3.734 | -0.6942 | -1.763 | 0.3752 | 0.2184 |
| mlp | traditional_median_template_cfd_timewalk_shape | 3.048 | 2.612 | 3.772 | -1.018 | -2.1 | 0.3885 | 0.2245 |
| matched_filter_residual_transformer_new | traditional_median_template_cfd_timewalk_shape | 3.67 | 3.244 | 4.606 | -0.9073 | -1.873 | 0.02535 | 0.2952 |
| compact_waveform_transformer | traditional_median_template_cfd_timewalk_shape | 4.722 | 4.362 | 5.679 | -0.6256 | -1.598 | 0.2946 | 0.3676 |
| 1d_cnn | traditional_median_template_cfd_timewalk_shape | 4.821 | 4.139 | 5.82 | -1.348 | -2.445 | -0.1392 | 0.3967 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_median_template_cfd_timewalk_shape | 1230 | -0.3541 | 0.8548 | 0.9968 | 0.206 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1230 | 0.7461 | 2.583 | 0.9828 | 0.206 | 0.2236 |
| sample_i_analysis | mlp | 1230 | 0.4235 | 3.794 | 0.9879 | 0.206 | 0.2683 |
| sample_i_analysis | ridge | 1230 | 0.5325 | 4.783 | 0.9845 | 0.206 | 0.3073 |
| sample_i_analysis | matched_filter_residual_transformer_new | 1230 | -0.1084 | 5.543 | 0.9552 | 0.206 | 0.3398 |
| sample_i_analysis | compact_waveform_transformer | 1230 | -0.1596 | 6.766 | 0.9975 | 0.206 | 0.3854 |
| sample_i_analysis | 1d_cnn | 1230 | -0.3552 | 8.118 | 1.005 | 0.206 | 0.4846 |
| sample_i_calib | traditional_median_template_cfd_timewalk_shape | 597 | -0.4795 | 0.9788 | 0.9972 | 0.2478 | 0 |
| sample_i_calib | gradient_boosted_trees | 597 | 1.791 | 2.348 | 1.019 | 0.2478 | 0.1407 |
| sample_i_calib | mlp | 597 | 1.731 | 3.193 | 1.018 | 0.2478 | 0.206 |
| sample_i_calib | ridge | 597 | 1.555 | 3.936 | 1.022 | 0.2478 | 0.2379 |
| sample_i_calib | matched_filter_residual_transformer_new | 597 | 0.4569 | 4.5 | 0.9895 | 0.2478 | 0.2596 |
| sample_i_calib | compact_waveform_transformer | 597 | 1.133 | 5.101 | 1.034 | 0.2478 | 0.34 |
| sample_i_calib | 1d_cnn | 597 | 1.232 | 6.756 | 1.023 | 0.2478 | 0.4539 |
| sample_ii_analysis | traditional_median_template_cfd_timewalk_shape | 2459 | 0.5273 | 0.8818 | 0.9966 | 0.1582 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2459 | -1.543 | 3.437 | 1.003 | 0.1582 | 0.194 |
| sample_ii_analysis | ridge | 2459 | -1.2 | 3.746 | 1.01 | 0.1582 | 0.1952 |
| sample_ii_analysis | mlp | 2459 | -1.865 | 4.11 | 1.01 | 0.1582 | 0.2351 |
| sample_ii_analysis | matched_filter_residual_transformer_new | 2459 | -1.077 | 4.659 | 0.9842 | 0.1582 | 0.3005 |
| sample_ii_analysis | 1d_cnn | 2459 | -1.583 | 5.347 | 1.02 | 0.1582 | 0.3611 |
| sample_ii_analysis | compact_waveform_transformer | 2459 | -0.914 | 5.772 | 1.029 | 0.1582 | 0.3745 |
| sample_ii_calib | traditional_median_template_cfd_timewalk_shape | 640 | 0.6482 | 0.331 | 0.9941 | 0.121 | 0 |
| sample_ii_calib | ridge | 640 | -1.327 | 2.919 | 1.015 | 0.121 | 0.1187 |
| sample_ii_calib | gradient_boosted_trees | 640 | -1.442 | 2.956 | 1.01 | 0.121 | 0.1313 |
| sample_ii_calib | mlp | 640 | -1.848 | 3.6 | 1.014 | 0.121 | 0.1172 |
| sample_ii_calib | matched_filter_residual_transformer_new | 640 | -1.136 | 3.962 | 0.9853 | 0.121 | 0.2219 |
| sample_ii_calib | 1d_cnn | 640 | -1.626 | 4.633 | 1.026 | 0.121 | 0.3109 |
| sample_ii_calib | compact_waveform_transformer | 640 | -0.3397 | 5.442 | 1.037 | 0.121 | 0.3328 |

| method | run | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 597 | 1.232 | 6.756 | 1.023 | 0.2478 | 0.4539 |
| 1d_cnn | 50 | 620 | -2.686 | 14.44 | 0.9807 | 0.1934 | 0.4903 |
| 1d_cnn | 57 | 610 | 1.726 | 6.696 | 1.042 | 0.2188 | 0.4787 |
| 1d_cnn | 58 | 594 | -3.974 | 6.027 | 1.047 | 0.1834 | 0.4865 |
| 1d_cnn | 60 | 640 | -0.3551 | 4.705 | 0.9995 | 0.1598 | 0.2938 |
| 1d_cnn | 62 | 640 | -0.9947 | 4.81 | 1.01 | 0.1535 | 0.3063 |
| 1d_cnn | 64 | 640 | -1.626 | 4.633 | 1.026 | 0.121 | 0.3109 |
| 1d_cnn | 65 | 585 | -1.992 | 5.065 | 1.042 | 0.1361 | 0.3675 |
| compact_waveform_transformer | 42 | 597 | 1.133 | 5.101 | 1.034 | 0.2478 | 0.34 |
| compact_waveform_transformer | 50 | 620 | -1.003 | 14.13 | 0.9711 | 0.1934 | 0.3871 |
| compact_waveform_transformer | 57 | 610 | 1.391 | 5.604 | 1.036 | 0.2188 | 0.3836 |
| compact_waveform_transformer | 58 | 594 | -3.095 | 6.102 | 1.026 | 0.1834 | 0.4444 |
| compact_waveform_transformer | 60 | 640 | -0.05239 | 5.711 | 1.049 | 0.1598 | 0.3766 |
| compact_waveform_transformer | 62 | 640 | -0.2235 | 5.505 | 1.062 | 0.1535 | 0.3453 |
| compact_waveform_transformer | 64 | 640 | -0.3397 | 5.442 | 1.037 | 0.121 | 0.3328 |
| compact_waveform_transformer | 65 | 585 | -0.8668 | 5.498 | 1.026 | 0.1361 | 0.3333 |
| gradient_boosted_trees | 42 | 597 | 1.791 | 2.348 | 1.019 | 0.2478 | 0.1407 |
| gradient_boosted_trees | 50 | 620 | 0.4579 | 13.97 | 0.9525 | 0.1934 | 0.2871 |
| gradient_boosted_trees | 57 | 610 | 1.132 | 2.871 | 1.022 | 0.2188 | 0.159 |
| gradient_boosted_trees | 58 | 594 | -3.743 | 3.008 | 1.018 | 0.1834 | 0.3047 |
| gradient_boosted_trees | 60 | 640 | -0.06774 | 3.873 | 1.002 | 0.1598 | 0.1844 |
| gradient_boosted_trees | 62 | 640 | -0.9252 | 2.296 | 1.012 | 0.1535 | 0.05937 |
| gradient_boosted_trees | 64 | 640 | -1.442 | 2.956 | 1.01 | 0.121 | 0.1313 |
| gradient_boosted_trees | 65 | 585 | -2.704 | 3.974 | 1.009 | 0.1361 | 0.2393 |
| matched_filter_residual_transformer_new | 42 | 597 | 0.4569 | 4.5 | 0.9895 | 0.2478 | 0.2596 |
| matched_filter_residual_transformer_new | 50 | 620 | -1.325 | 15.41 | 0.9256 | 0.1934 | 0.3839 |
| matched_filter_residual_transformer_new | 57 | 610 | 0.8993 | 4.758 | 0.9962 | 0.2188 | 0.2951 |
| matched_filter_residual_transformer_new | 58 | 594 | -3.315 | 5.529 | 0.9741 | 0.1834 | 0.431 |
| matched_filter_residual_transformer_new | 60 | 640 | -0.1797 | 4.215 | 0.9966 | 0.1598 | 0.2313 |
| matched_filter_residual_transformer_new | 62 | 640 | -0.2986 | 4.359 | 1.008 | 0.1535 | 0.2625 |
| matched_filter_residual_transformer_new | 64 | 640 | -1.136 | 3.962 | 0.9853 | 0.121 | 0.2219 |
| matched_filter_residual_transformer_new | 65 | 585 | -1.65 | 4.308 | 0.9975 | 0.1361 | 0.2855 |
| mlp | 42 | 597 | 1.731 | 3.193 | 1.018 | 0.2478 | 0.206 |
| mlp | 50 | 620 | -0.2394 | 13.43 | 0.9618 | 0.1934 | 0.2919 |
| mlp | 57 | 610 | 1.428 | 4.104 | 1.025 | 0.2188 | 0.2443 |
| mlp | 58 | 594 | -3.442 | 4.199 | 1.02 | 0.1834 | 0.3552 |
| mlp | 60 | 640 | -0.886 | 4.125 | 1.023 | 0.1598 | 0.2047 |
| mlp | 62 | 640 | -1.3 | 2.991 | 1.025 | 0.1535 | 0.08906 |
| mlp | 64 | 640 | -1.848 | 3.6 | 1.014 | 0.121 | 0.1172 |
| mlp | 65 | 585 | -2.7 | 4.821 | 1.01 | 0.1361 | 0.306 |
| ridge | 42 | 597 | 1.555 | 3.936 | 1.022 | 0.2478 | 0.2379 |
| ridge | 50 | 620 | -0.4665 | 13.79 | 0.9591 | 0.1934 | 0.3194 |
| ridge | 57 | 610 | 1.853 | 4.431 | 1.021 | 0.2188 | 0.2951 |
| ridge | 58 | 594 | -2.864 | 4.441 | 1.013 | 0.1834 | 0.335 |
| ridge | 60 | 640 | -0.3097 | 3.134 | 1.023 | 0.1598 | 0.1172 |
| ridge | 62 | 640 | -1.148 | 2.995 | 1.028 | 0.1535 | 0.1141 |
| ridge | 64 | 640 | -1.327 | 2.919 | 1.015 | 0.121 | 0.1187 |
| ridge | 65 | 585 | -1.588 | 3.88 | 1.012 | 0.1361 | 0.2274 |
| traditional_median_template_cfd_timewalk_shape | 42 | 597 | -0.4795 | 0.9788 | 0.9972 | 0.2478 | 0 |
| traditional_median_template_cfd_timewalk_shape | 50 | 620 | -0.1892 | 0.4288 | 0.9964 | 0.1934 | 0 |
| traditional_median_template_cfd_timewalk_shape | 57 | 610 | -1.103 | 1.308 | 0.9978 | 0.2188 | 0 |
| traditional_median_template_cfd_timewalk_shape | 58 | 594 | 0.8536 | 0.6905 | 0.9939 | 0.1834 | 0 |
| traditional_median_template_cfd_timewalk_shape | 60 | 640 | -0.7661 | 1.011 | 0.9967 | 0.1598 | 0 |
| traditional_median_template_cfd_timewalk_shape | 62 | 640 | 0.3369 | 0.6428 | 0.9949 | 0.1535 | 0 |
| traditional_median_template_cfd_timewalk_shape | 64 | 640 | 0.6482 | 0.331 | 0.9941 | 0.121 | 0 |
| traditional_median_template_cfd_timewalk_shape | 65 | 585 | 0.7191 | 0.4217 | 0.9946 | 0.1361 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1458 | -1.315 | 7.041 | 0.9494 | 0.312 | 0.476 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1458 | -3.194 | 5.612 | 1.024 | 0.312 | 0.4451 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1458 | -0.3317 | 3.598 | 0.9812 | 0.312 | 0.1955 |
| curvature_energy_bin | curved | matched_filter_residual_transformer_new | 1458 | -0.6403 | 4.854 | 0.9492 | 0.312 | 0.3059 |
| curvature_energy_bin | curved | mlp | 1458 | -0.7063 | 4.048 | 0.9924 | 0.312 | 0.2332 |
| curvature_energy_bin | curved | ridge | 1458 | -0.7247 | 3.816 | 0.9857 | 0.312 | 0.2311 |
| curvature_energy_bin | curved | traditional_median_template_cfd_timewalk_shape | 1458 | 0.3291 | 1.063 | 0.9966 | 0.312 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1716 | 0.3961 | 5.26 | 1.011 | 0.1217 | 0.3409 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1716 | 1.021 | 5.532 | 1.024 | 0.1217 | 0.377 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1716 | -0.1608 | 3.568 | 1.003 | 0.1217 | 0.1894 |
| curvature_energy_bin | moderate | matched_filter_residual_transformer_new | 1716 | -0.2102 | 4.782 | 0.951 | 0.1217 | 0.3036 |
| curvature_energy_bin | moderate | mlp | 1716 | -0.4901 | 4.07 | 1.003 | 0.1217 | 0.2209 |
| curvature_energy_bin | moderate | ridge | 1716 | -0.6392 | 3.987 | 1.005 | 0.1217 | 0.2296 |
| curvature_energy_bin | moderate | traditional_median_template_cfd_timewalk_shape | 1716 | 0.3345 | 1.017 | 0.9956 | 0.1217 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1752 | -2.498 | 5.044 | 1.068 | 0.1165 | 0.3853 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1752 | 0.6226 | 4.563 | 0.9897 | 0.1165 | 0.2939 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1752 | -0.3718 | 3.653 | 1.005 | 0.1165 | 0.1769 |
| curvature_energy_bin | smooth | matched_filter_residual_transformer_new | 1752 | -0.989 | 4.428 | 1.009 | 0.1165 | 0.278 |
| curvature_energy_bin | smooth | mlp | 1752 | -0.9793 | 4.073 | 1.009 | 0.1165 | 0.2209 |
| curvature_energy_bin | smooth | ridge | 1752 | 0.2762 | 3.652 | 1.006 | 0.1165 | 0.1969 |
| curvature_energy_bin | smooth | traditional_median_template_cfd_timewalk_shape | 1752 | 0.2166 | 1.031 | 0.9944 | 0.1165 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1653 | -1.748 | 5.118 | 0.8757 | 0.04057 | 0.3618 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1653 | -0.5637 | 5.439 | 1.181 | 0.04057 | 0.3472 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1653 | -0.473 | 3.36 | 0.9837 | 0.04057 | 0.1561 |
| derivative_onset_bin | nominal | matched_filter_residual_transformer_new | 1653 | -0.8411 | 4.429 | 1.166 | 0.04057 | 0.2698 |
| derivative_onset_bin | nominal | mlp | 1653 | -1.156 | 3.851 | 0.997 | 0.04057 | 0.1948 |
| derivative_onset_bin | nominal | ridge | 1653 | -0.9175 | 3.567 | 1.041 | 0.04057 | 0.1857 |
| derivative_onset_bin | nominal | traditional_median_template_cfd_timewalk_shape | 1653 | 0.3533 | 0.9926 | 0.9908 | 0.04057 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1761 | -1.099 | 5.424 | 0.7876 | 0.04449 | 0.3623 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1761 | -0.03609 | 5.314 | 1.059 | 0.04449 | 0.3419 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1761 | -0.6781 | 3.296 | 0.9877 | 0.04449 | 0.1533 |
| derivative_onset_bin | sharp | matched_filter_residual_transformer_new | 1761 | -0.3757 | 4.33 | 1.132 | 0.04449 | 0.2663 |
| derivative_onset_bin | sharp | mlp | 1761 | -1.333 | 3.889 | 1.016 | 0.04449 | 0.2016 |
| derivative_onset_bin | sharp | ridge | 1761 | -0.904 | 3.503 | 1.078 | 0.04449 | 0.1846 |
| derivative_onset_bin | sharp | traditional_median_template_cfd_timewalk_shape | 1761 | 0.4389 | 1.024 | 0.9924 | 0.04449 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1512 | -0.02821 | 8.399 | 1.044 | 0.4778 | 0.4749 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1512 | -0.4146 | 6.575 | 1.033 | 0.4778 | 0.42 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1512 | 0.5978 | 4.28 | 0.9983 | 0.4778 | 0.2593 |
| derivative_onset_bin | slow | matched_filter_residual_transformer_new | 1512 | -0.7724 | 5.709 | 0.9692 | 0.4778 | 0.3565 |
| derivative_onset_bin | slow | mlp | 1512 | 0.6963 | 4.348 | 1.002 | 0.4778 | 0.2837 |
| derivative_onset_bin | slow | ridge | 1512 | 0.7469 | 4.386 | 0.9971 | 0.4778 | 0.2937 |
| derivative_onset_bin | slow | traditional_median_template_cfd_timewalk_shape | 1512 | -0.04008 | 1.074 | 0.9968 | 0.4778 | 0 |
| energy_bin | q1_low | 1d_cnn | 1274 | -3.196 | 6.782 | 1.067 | 0.4403 | 0.4976 |
| energy_bin | q1_low | compact_waveform_transformer | 1274 | -0.3361 | 5.291 | 1.019 | 0.4403 | 0.3352 |
| energy_bin | q1_low | gradient_boosted_trees | 1274 | -0.6263 | 3.776 | 1.003 | 0.4403 | 0.1954 |
| energy_bin | q1_low | matched_filter_residual_transformer_new | 1274 | -0.9666 | 4.84 | 0.9806 | 0.4403 | 0.3265 |
| energy_bin | q1_low | mlp | 1274 | -0.6268 | 4.015 | 1.005 | 0.4403 | 0.2151 |
| energy_bin | q1_low | ridge | 1274 | 0.2161 | 3.62 | 1.01 | 0.4403 | 0.2064 |
| energy_bin | q1_low | traditional_median_template_cfd_timewalk_shape | 1274 | 0.02246 | 1.084 | 0.9935 | 0.4403 | 0 |
| energy_bin | q2 | 1d_cnn | 1377 | -1.453 | 4.762 | 1.033 | 0.09637 | 0.3355 |
| energy_bin | q2 | compact_waveform_transformer | 1377 | 1.055 | 5.168 | 1.017 | 0.09637 | 0.3435 |
| energy_bin | q2 | gradient_boosted_trees | 1377 | -0.144 | 3.367 | 1.005 | 0.09637 | 0.159 |
| energy_bin | q2 | matched_filter_residual_transformer_new | 1377 | -0.5571 | 4.25 | 1.011 | 0.09637 | 0.2534 |
| energy_bin | q2 | mlp | 1377 | -0.922 | 4.085 | 1.007 | 0.09637 | 0.2259 |
| energy_bin | q2 | ridge | 1377 | -0.4213 | 3.882 | 1.007 | 0.09637 | 0.2229 |
| energy_bin | q2 | traditional_median_template_cfd_timewalk_shape | 1377 | 0.3115 | 1.017 | 0.9965 | 0.09637 | 0 |
| energy_bin | q3 | 1d_cnn | 1280 | 1.62 | 4.115 | 0.959 | 0.08852 | 0.293 |
| energy_bin | q3 | compact_waveform_transformer | 1280 | 0.8852 | 5.645 | 1.012 | 0.08852 | 0.3836 |
| energy_bin | q3 | gradient_boosted_trees | 1280 | -0.4048 | 3.64 | 0.995 | 0.08852 | 0.1859 |
| energy_bin | q3 | matched_filter_residual_transformer_new | 1280 | 0.1115 | 4.862 | 0.9536 | 0.08852 | 0.2984 |
| energy_bin | q3 | mlp | 1280 | -0.81 | 4.136 | 0.9976 | 0.08852 | 0.225 |
| energy_bin | q3 | ridge | 1280 | -0.6527 | 3.973 | 0.995 | 0.08852 | 0.2328 |
| energy_bin | q3 | traditional_median_template_cfd_timewalk_shape | 1280 | 0.4513 | 1.027 | 0.9954 | 0.08852 | 0 |
| energy_bin | q4_high | 1d_cnn | 995 | -3 | 6.257 | 0.9595 | 0.06114 | 0.4854 |
| energy_bin | q4_high | compact_waveform_transformer | 995 | -3.544 | 5.191 | 1.043 | 0.06114 | 0.4221 |
| energy_bin | q4_high | gradient_boosted_trees | 995 | -0.2114 | 3.626 | 0.9893 | 0.06114 | 0.2151 |
| energy_bin | q4_high | matched_filter_residual_transformer_new | 995 | -1.321 | 4.897 | 0.9194 | 0.06114 | 0.3085 |
| energy_bin | q4_high | mlp | 995 | -0.5517 | 3.94 | 1.01 | 0.06114 | 0.2342 |
| energy_bin | q4_high | ridge | 995 | -0.7675 | 3.707 | 0.9968 | 0.06114 | 0.209 |
| energy_bin | q4_high | traditional_median_template_cfd_timewalk_shape | 995 | 0.3671 | 1.054 | 0.994 | 0.06114 | 0 |
| late_tail_morphology | compact | 1d_cnn | 2943 | -1.719 | 5.701 | 0.8999 | 0.1508 | 0.4016 |
| late_tail_morphology | compact | compact_waveform_transformer | 2943 | -0.5462 | 5.849 | 1.187 | 0.1508 | 0.3721 |
| late_tail_morphology | compact | gradient_boosted_trees | 2943 | -0.6025 | 3.36 | 0.9778 | 0.1508 | 0.1536 |
| late_tail_morphology | compact | matched_filter_residual_transformer_new | 2943 | -1.117 | 4.475 | 1.027 | 0.1508 | 0.2922 |
| late_tail_morphology | compact | mlp | 2943 | -1.25 | 3.897 | 0.9875 | 0.1508 | 0.1988 |
| late_tail_morphology | compact | ridge | 2943 | -0.8327 | 3.737 | 1.017 | 0.1508 | 0.2046 |
| late_tail_morphology | compact | traditional_median_template_cfd_timewalk_shape | 2943 | 0.3315 | 1.036 | 0.994 | 0.1508 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 564 | -0.9145 | 4.74 | 0.6733 | 0.03644 | 0.3121 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 564 | -1.036 | 4.735 | 0.7667 | 0.03644 | 0.3138 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 564 | -0.1228 | 3.412 | 0.9623 | 0.03644 | 0.1188 |
| late_tail_morphology | diffuse_tail | matched_filter_residual_transformer_new | 564 | 0.7646 | 3.552 | 0.892 | 0.03644 | 0.195 |
| late_tail_morphology | diffuse_tail | mlp | 564 | -0.6074 | 3.91 | 0.8841 | 0.03644 | 0.1968 |
| late_tail_morphology | diffuse_tail | ridge | 564 | -0.7341 | 3.225 | 1.095 | 0.03644 | 0.156 |
| late_tail_morphology | diffuse_tail | traditional_median_template_cfd_timewalk_shape | 564 | 0.6323 | 0.9787 | 0.9585 | 0.03644 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 339 | -3.194 | 7.683 | 0.9665 | 0.5321 | 0.5015 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 339 | -0.8383 | 5.984 | 1.087 | 0.5321 | 0.3923 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 339 | -0.3457 | 3.323 | 1.049 | 0.5321 | 0.2124 |
| late_tail_morphology | late_derivative_bump | matched_filter_residual_transformer_new | 339 | 0.2817 | 5.335 | 0.9329 | 0.5321 | 0.3392 |
| late_tail_morphology | late_derivative_bump | mlp | 339 | -0.4246 | 3.554 | 1.018 | 0.5321 | 0.2301 |
| late_tail_morphology | late_derivative_bump | ridge | 339 | 0.01821 | 2.982 | 1.021 | 0.5321 | 0.1976 |
| late_tail_morphology | late_derivative_bump | traditional_median_template_cfd_timewalk_shape | 339 | -0.112 | 0.8847 | 1.005 | 0.5321 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1080 | 0.8944 | 6.187 | 1.052 | 0.2065 | 0.3944 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1080 | 0.8038 | 5.623 | 1.014 | 0.2065 | 0.3759 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1080 | 0.7425 | 4.807 | 0.9935 | 0.2065 | 0.3046 |
| late_tail_morphology | late_rising_tail | matched_filter_residual_transformer_new | 1080 | -0.7175 | 5.773 | 0.9567 | 0.2065 | 0.3417 |
| late_tail_morphology | late_rising_tail | mlp | 1080 | 0.8452 | 4.782 | 1.005 | 0.2065 | 0.3074 |
| late_tail_morphology | late_rising_tail | ridge | 1080 | 0.8407 | 4.257 | 0.9914 | 0.2065 | 0.2954 |
| late_tail_morphology | late_rising_tail | traditional_median_template_cfd_timewalk_shape | 1080 | -0.04394 | 1.084 | 0.9919 | 0.2065 | 0 |
| peak_phase_bin | early_phase | 1d_cnn | 2133 | -0.7636 | 6.099 | 1.022 | 0.1705 | 0.4083 |
| peak_phase_bin | early_phase | compact_waveform_transformer | 2133 | -0.6059 | 6.233 | 1.025 | 0.1705 | 0.4102 |
| peak_phase_bin | early_phase | gradient_boosted_trees | 2133 | -0.1519 | 3.704 | 1 | 0.1705 | 0.1932 |
| peak_phase_bin | early_phase | matched_filter_residual_transformer_new | 2133 | -0.9604 | 4.995 | 0.978 | 0.1705 | 0.3286 |
| peak_phase_bin | early_phase | mlp | 2133 | -0.5562 | 4.201 | 1.003 | 0.1705 | 0.248 |
| peak_phase_bin | early_phase | ridge | 2133 | -0.4092 | 4.084 | 1.001 | 0.1705 | 0.2344 |
| peak_phase_bin | early_phase | traditional_median_template_cfd_timewalk_shape | 2133 | 0.2947 | 1.022 | 0.9942 | 0.1705 | 0 |
| peak_phase_bin | late_phase | 1d_cnn | 1140 | -1.417 | 5.837 | 1.013 | 0.153 | 0.3842 |
| peak_phase_bin | late_phase | compact_waveform_transformer | 1140 | -0.5165 | 5.439 | 1.016 | 0.153 | 0.3377 |
| peak_phase_bin | late_phase | gradient_boosted_trees | 1140 | -0.5381 | 3.671 | 0.9895 | 0.153 | 0.1982 |
| peak_phase_bin | late_phase | matched_filter_residual_transformer_new | 1140 | 0.338 | 4.413 | 0.9447 | 0.153 | 0.2614 |
| peak_phase_bin | late_phase | mlp | 1140 | -0.9767 | 3.942 | 0.9924 | 0.153 | 0.214 |
| peak_phase_bin | late_phase | ridge | 1140 | -0.5681 | 3.58 | 0.9918 | 0.153 | 0.2105 |
| peak_phase_bin | late_phase | traditional_median_template_cfd_timewalk_shape | 1140 | 0.3362 | 0.9625 | 0.9961 | 0.153 | 0 |
| peak_phase_bin | mid_phase | 1d_cnn | 1653 | -1.117 | 5.66 | 1.009 | 0.1995 | 0.3902 |
| peak_phase_bin | mid_phase | compact_waveform_transformer | 1653 | 0.1127 | 5.257 | 1.012 | 0.1995 | 0.3333 |
| peak_phase_bin | mid_phase | gradient_boosted_trees | 1653 | -0.2937 | 3.528 | 1.006 | 0.1995 | 0.1706 |
| peak_phase_bin | mid_phase | matched_filter_residual_transformer_new | 1653 | -0.8389 | 4.4 | 0.9914 | 0.1995 | 0.2753 |
| peak_phase_bin | mid_phase | mlp | 1653 | -0.7746 | 4.001 | 1.013 | 0.1995 | 0.2015 |
| peak_phase_bin | mid_phase | ridge | 1653 | -0.2705 | 3.774 | 1.014 | 0.1995 | 0.2033 |
| peak_phase_bin | mid_phase | traditional_median_template_cfd_timewalk_shape | 1653 | 0.2267 | 1.043 | 0.9954 | 0.1995 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1523 | -1.101 | 7.605 | 1.006 | 0.4004 | 0.4839 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1523 | -2.046 | 6.614 | 1.041 | 0.4004 | 0.4675 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1523 | -0.08155 | 3.763 | 1.002 | 0.4004 | 0.1937 |
| pedestal_drift_bin | high | matched_filter_residual_transformer_new | 1523 | -0.961 | 4.965 | 0.9732 | 0.4004 | 0.3336 |
| pedestal_drift_bin | high | mlp | 1523 | -0.08446 | 4.062 | 1.005 | 0.4004 | 0.2265 |
| pedestal_drift_bin | high | ridge | 1523 | -0.06488 | 3.837 | 1 | 0.4004 | 0.2213 |
| pedestal_drift_bin | high | traditional_median_template_cfd_timewalk_shape | 1523 | 0.2304 | 1.036 | 0.9954 | 0.4004 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1649 | -1.142 | 5.266 | 1.022 | 0.07687 | 0.3608 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1649 | 0.1867 | 4.825 | 0.9955 | 0.07687 | 0.3044 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1649 | -0.2965 | 3.485 | 1.004 | 0.07687 | 0.1734 |
| pedestal_drift_bin | low | matched_filter_residual_transformer_new | 1649 | -0.7062 | 4.623 | 0.9705 | 0.07687 | 0.2923 |
| pedestal_drift_bin | low | mlp | 1649 | -0.9518 | 4.004 | 1.012 | 0.07687 | 0.2135 |
| pedestal_drift_bin | low | ridge | 1649 | -0.499 | 4.045 | 1.011 | 0.07687 | 0.228 |
| pedestal_drift_bin | low | traditional_median_template_cfd_timewalk_shape | 1649 | 0.2784 | 1.011 | 0.9935 | 0.07687 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1754 | -0.9584 | 5.208 | 1.014 | 0.07483 | 0.3546 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1754 | 0.3676 | 5.165 | 0.9921 | 0.07483 | 0.3404 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1754 | -0.4141 | 3.6 | 0.9959 | 0.07483 | 0.1933 |
| pedestal_drift_bin | mid | matched_filter_residual_transformer_new | 1754 | -0.3842 | 4.504 | 0.9695 | 0.07483 | 0.2645 |
| pedestal_drift_bin | mid | mlp | 1754 | -1.032 | 4.127 | 1.003 | 0.07483 | 0.2332 |
| pedestal_drift_bin | mid | ridge | 1754 | -0.5208 | 3.703 | 1.001 | 0.07483 | 0.207 |
| pedestal_drift_bin | mid | traditional_median_template_cfd_timewalk_shape | 1754 | 0.3431 | 1.022 | 0.994 | 0.07483 | 0 |
| pid_sideband | central | 1d_cnn | 3417 | -0.8968 | 5.258 | 1.024 | 0.08248 | 0.3518 |
| pid_sideband | central | compact_waveform_transformer | 3417 | 0.4818 | 4.966 | 0.997 | 0.08248 | 0.3167 |
| pid_sideband | central | gradient_boosted_trees | 3417 | -0.2666 | 3.578 | 1.002 | 0.08248 | 0.1829 |
| pid_sideband | central | matched_filter_residual_transformer_new | 3417 | -0.5907 | 4.469 | 0.9749 | 0.08248 | 0.2757 |
| pid_sideband | central | mlp | 3417 | -0.7388 | 4.079 | 1.008 | 0.08248 | 0.2274 |
| pid_sideband | central | ridge | 3417 | -0.3932 | 3.843 | 1.007 | 0.08248 | 0.2171 |
| pid_sideband | central | traditional_median_template_cfd_timewalk_shape | 3417 | 0.2367 | 1.02 | 0.9937 | 0.08248 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 783 | -2.034 | 9.999 | 0.6358 | 0.6983 | 0.6181 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 783 | -5.656 | 5.774 | 0.8308 | 0.6983 | 0.5926 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 783 | -0.2963 | 3.572 | 0.9994 | 0.6983 | 0.1826 |
| pid_sideband | high_duplicate | matched_filter_residual_transformer_new | 783 | -1.743 | 5.713 | 0.7742 | 0.6983 | 0.4202 |
| pid_sideband | high_duplicate | mlp | 783 | -0.3842 | 4.014 | 1.002 | 0.6983 | 0.2286 |
| pid_sideband | high_duplicate | ridge | 783 | -0.3733 | 4.102 | 0.9811 | 0.6983 | 0.249 |
| pid_sideband | high_duplicate | traditional_median_template_cfd_timewalk_shape | 783 | 0.3115 | 1.067 | 0.9968 | 0.6983 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 726 | -1.479 | 5.476 | 0.9686 | 0.05397 | 0.3691 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 726 | -0.1342 | 5.353 | 0.9445 | 0.05397 | 0.365 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 726 | -0.3775 | 3.793 | 0.9735 | 0.05397 | 0.2094 |
| pid_sideband | low_duplicate | matched_filter_residual_transformer_new | 726 | 0.02449 | 4.463 | 0.9105 | 0.05397 | 0.2521 |
| pid_sideband | low_duplicate | mlp | 726 | -1.002 | 4.066 | 0.9776 | 0.05397 | 0.2066 |
| pid_sideband | low_duplicate | ridge | 726 | -0.5137 | 3.505 | 0.9727 | 0.05397 | 0.1915 |
| pid_sideband | low_duplicate | traditional_median_template_cfd_timewalk_shape | 726 | 0.4326 | 0.9253 | 0.9914 | 0.05397 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1456 | -2.615 | 5.771 | 0.8437 | 0.03641 | 0.4045 |
| pileup_separation_bin | close | compact_waveform_transformer | 1456 | -0.636 | 5.13 | 0.9555 | 0.03641 | 0.3448 |
| pileup_separation_bin | close | gradient_boosted_trees | 1456 | -0.3384 | 3.46 | 0.9724 | 0.03641 | 0.169 |
| pileup_separation_bin | close | matched_filter_residual_transformer_new | 1456 | -0.8638 | 4.73 | 1.144 | 0.03641 | 0.294 |
| pileup_separation_bin | close | mlp | 1456 | -0.9175 | 4.017 | 0.9974 | 0.03641 | 0.2129 |
| pileup_separation_bin | close | ridge | 1456 | -1.025 | 3.58 | 1.063 | 0.03641 | 0.2081 |
| pileup_separation_bin | close | traditional_median_template_cfd_timewalk_shape | 1456 | 0.4234 | 1.013 | 0.9883 | 0.03641 | 0 |
| pileup_separation_bin | late | 1d_cnn | 7 | -6.621 | 6.267 | 1.184 | 0.1286 | 0.8571 |
| pileup_separation_bin | late | compact_waveform_transformer | 7 | -11.55 | 5.588 | 1.643 | 0.1286 | 0.8571 |
| pileup_separation_bin | late | gradient_boosted_trees | 7 | -2.874 | 3.677 | 1.024 | 0.1286 | 0.4286 |
| pileup_separation_bin | late | matched_filter_residual_transformer_new | 7 | -7.632 | 8.129 | 1.084 | 0.1286 | 0.5714 |
| pileup_separation_bin | late | mlp | 7 | -1.819 | 6.664 | 0.8859 | 0.1286 | 0.5714 |
| pileup_separation_bin | late | ridge | 7 | 1.141 | 2.941 | 0.9963 | 0.1286 | 0 |
| pileup_separation_bin | late | traditional_median_template_cfd_timewalk_shape | 7 | 0.4561 | 0.9874 | 1.014 | 0.1286 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1083 | 1.113 | 6.332 | 0.9619 | 0.12 | 0.4192 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1083 | -3.456 | 6.273 | 1.229 | 0.12 | 0.5069 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1083 | -0.6197 | 3.38 | 0.9661 | 0.12 | 0.157 |
| pileup_separation_bin | mid | matched_filter_residual_transformer_new | 1083 | -1.282 | 4.898 | 1.106 | 0.12 | 0.3315 |
| pileup_separation_bin | mid | mlp | 1083 | -1.054 | 3.792 | 0.9852 | 0.12 | 0.2022 |
| pileup_separation_bin | mid | ridge | 1083 | -0.8188 | 3.813 | 0.9994 | 0.12 | 0.217 |
| pileup_separation_bin | mid | traditional_median_template_cfd_timewalk_shape | 1083 | 0.4953 | 1.068 | 0.997 | 0.12 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2380 | -0.9874 | 5.546 | 1.042 | 0.2874 | 0.3803 |
| pileup_separation_bin | none | compact_waveform_transformer | 2380 | 1.059 | 4.686 | 0.9908 | 0.2874 | 0.3168 |
| pileup_separation_bin | none | gradient_boosted_trees | 2380 | -0.06579 | 3.818 | 0.9996 | 0.2874 | 0.2105 |
| pileup_separation_bin | none | matched_filter_residual_transformer_new | 2380 | -0.2539 | 4.513 | 0.9567 | 0.2874 | 0.2786 |
| pileup_separation_bin | none | mlp | 2380 | -0.3977 | 4.099 | 1.003 | 0.2874 | 0.2408 |
| pileup_separation_bin | none | ridge | 2380 | 0.4376 | 3.728 | 0.9961 | 0.2874 | 0.2261 |
| pileup_separation_bin | none | traditional_median_template_cfd_timewalk_shape | 2380 | 0.1312 | 1.042 | 0.9964 | 0.2874 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1673 | -2.613 | 7.146 | 0.8471 | 0.3463 | 0.4931 |
| pulse_shape_class | compact | compact_waveform_transformer | 1673 | -1.579 | 6.258 | 1.2 | 0.3463 | 0.419 |
| pulse_shape_class | compact | gradient_boosted_trees | 1673 | -0.7539 | 3.624 | 0.9632 | 0.3463 | 0.1919 |
| pulse_shape_class | compact | matched_filter_residual_transformer_new | 1673 | -1.638 | 4.743 | 0.9504 | 0.3463 | 0.361 |
| pulse_shape_class | compact | mlp | 1673 | -1.399 | 4.151 | 0.9663 | 0.3463 | 0.2277 |
| pulse_shape_class | compact | ridge | 1673 | -0.4709 | 4.05 | 1.01 | 0.3463 | 0.2445 |
| pulse_shape_class | compact | traditional_median_template_cfd_timewalk_shape | 1673 | 0.2941 | 1.05 | 0.9943 | 0.3463 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1665 | 0.1887 | 5.691 | 1.034 | 0.1467 | 0.3652 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1665 | 0.1358 | 5.391 | 1.008 | 0.1467 | 0.3532 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1665 | 0.3948 | 4.132 | 0.9917 | 0.1467 | 0.2396 |
| pulse_shape_class | late_tail | matched_filter_residual_transformer_new | 1665 | -0.06489 | 4.897 | 0.948 | 0.1467 | 0.2901 |
| pulse_shape_class | late_tail | mlp | 1665 | 0.2774 | 4.314 | 0.9974 | 0.1467 | 0.2673 |
| pulse_shape_class | late_tail | ridge | 1665 | 0.2395 | 3.914 | 0.9949 | 0.1467 | 0.2462 |
| pulse_shape_class | late_tail | traditional_median_template_cfd_timewalk_shape | 1665 | 0.2288 | 1.023 | 0.9906 | 0.1467 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1588 | -0.9434 | 4.878 | 0.6994 | 0.02786 | 0.3281 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1588 | 0.1124 | 5.085 | 1.083 | 0.02786 | 0.3287 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1588 | -0.3747 | 3.036 | 0.9632 | 0.02786 | 0.1259 |
| pulse_shape_class | nominal | matched_filter_residual_transformer_new | 1588 | -0.2955 | 4.134 | 1.061 | 0.02786 | 0.2311 |
| pulse_shape_class | nominal | mlp | 1588 | -0.9522 | 3.54 | 0.9863 | 0.02786 | 0.1763 |
| pulse_shape_class | nominal | ridge | 1588 | -0.9161 | 3.387 | 1.133 | 0.02786 | 0.1618 |
| pulse_shape_class | nominal | traditional_median_template_cfd_timewalk_shape | 1588 | 0.3112 | 0.9516 | 0.9734 | 0.02786 | 0 |
| q_template_error_bin | moderate_shape | 1d_cnn | 1786 | 0.2078 | 4.964 | 0.9357 | 0.05211 | 0.3169 |
| q_template_error_bin | moderate_shape | compact_waveform_transformer | 1786 | 0.03545 | 5.827 | 1.121 | 0.05211 | 0.4031 |
| q_template_error_bin | moderate_shape | gradient_boosted_trees | 1786 | -0.8284 | 3.612 | 1.001 | 0.05211 | 0.1697 |
| q_template_error_bin | moderate_shape | matched_filter_residual_transformer_new | 1786 | 0.1616 | 4.908 | 1.167 | 0.05211 | 0.2979 |
| q_template_error_bin | moderate_shape | mlp | 1786 | -1.232 | 4.066 | 1.026 | 0.05211 | 0.206 |
| q_template_error_bin | moderate_shape | ridge | 1786 | 0.2027 | 3.968 | 1.119 | 0.05211 | 0.2212 |
| q_template_error_bin | moderate_shape | traditional_median_template_cfd_timewalk_shape | 1786 | 0.5038 | 1.008 | 0.9906 | 0.05211 | 0 |
| q_template_error_bin | shape_outlier | 1d_cnn | 1548 | -0.06102 | 8.796 | 1.038 | 0.4849 | 0.5052 |
| q_template_error_bin | shape_outlier | compact_waveform_transformer | 1548 | -1.517 | 7.134 | 1.045 | 0.4849 | 0.4832 |
| q_template_error_bin | shape_outlier | gradient_boosted_trees | 1548 | 0.3339 | 4.269 | 0.9994 | 0.4849 | 0.2597 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 5.044 | curved | 7.041 | 1.997 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.563 | curved | 5.612 | 1.049 |
| curvature_energy_bin | matched_filter_residual_transformer_new | 3 | smooth | 4.428 | curved | 4.854 | 0.4254 |
| curvature_energy_bin | ridge | 3 | smooth | 3.652 | moderate | 3.987 | 0.3348 |
| curvature_energy_bin | gradient_boosted_trees | 3 | moderate | 3.568 | smooth | 3.653 | 0.08502 |
| curvature_energy_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate | 1.017 | curved | 1.063 | 0.04603 |
| curvature_energy_bin | mlp | 3 | curved | 4.048 | smooth | 4.073 | 0.02472 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 5.118 | slow | 8.399 | 3.28 |
| derivative_onset_bin | matched_filter_residual_transformer_new | 3 | sharp | 4.33 | slow | 5.709 | 1.38 |
| derivative_onset_bin | compact_waveform_transformer | 3 | sharp | 5.314 | slow | 6.575 | 1.261 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.296 | slow | 4.28 | 0.9849 |
| derivative_onset_bin | ridge | 3 | sharp | 3.503 | slow | 4.386 | 0.883 |
| derivative_onset_bin | mlp | 3 | nominal | 3.851 | slow | 4.348 | 0.4974 |
| derivative_onset_bin | traditional_median_template_cfd_timewalk_shape | 3 | nominal | 0.9926 | slow | 1.074 | 0.08112 |
| energy_bin | 1d_cnn | 4 | q3 | 4.115 | q1_low | 6.782 | 2.667 |
| energy_bin | matched_filter_residual_transformer_new | 4 | q2 | 4.25 | q4_high | 4.897 | 0.6467 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 5.168 | q3 | 5.645 | 0.477 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.367 | q1_low | 3.776 | 0.4098 |
| energy_bin | ridge | 4 | q1_low | 3.62 | q3 | 3.973 | 0.3527 |
| energy_bin | mlp | 4 | q4_high | 3.94 | q3 | 4.136 | 0.1954 |
| energy_bin | traditional_median_template_cfd_timewalk_shape | 4 | q2 | 1.017 | q1_low | 1.084 | 0.06766 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.74 | late_derivative_bump | 7.683 | 2.943 |
| late_tail_morphology | matched_filter_residual_transformer_new | 4 | diffuse_tail | 3.552 | late_rising_tail | 5.773 | 2.22 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 3.323 | late_rising_tail | 4.807 | 1.484 |
| late_tail_morphology | ridge | 4 | late_derivative_bump | 2.982 | late_rising_tail | 4.257 | 1.275 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.735 | late_derivative_bump | 5.984 | 1.249 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.554 | late_rising_tail | 4.782 | 1.229 |
| late_tail_morphology | traditional_median_template_cfd_timewalk_shape | 4 | late_derivative_bump | 0.8847 | late_rising_tail | 1.084 | 0.1988 |
| peak_phase_bin | compact_waveform_transformer | 3 | mid_phase | 5.257 | early_phase | 6.233 | 0.9768 |
| peak_phase_bin | matched_filter_residual_transformer_new | 3 | mid_phase | 4.4 | early_phase | 4.995 | 0.5954 |
| peak_phase_bin | ridge | 3 | late_phase | 3.58 | early_phase | 4.084 | 0.504 |
| peak_phase_bin | 1d_cnn | 3 | mid_phase | 5.66 | early_phase | 6.099 | 0.4391 |
| peak_phase_bin | mlp | 3 | late_phase | 3.942 | early_phase | 4.201 | 0.259 |
| peak_phase_bin | gradient_boosted_trees | 3 | mid_phase | 3.528 | early_phase | 3.704 | 0.1759 |
| peak_phase_bin | traditional_median_template_cfd_timewalk_shape | 3 | late_phase | 0.9625 | mid_phase | 1.043 | 0.08048 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.208 | high | 7.605 | 2.396 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | low | 4.825 | high | 6.614 | 1.789 |
| pedestal_drift_bin | matched_filter_residual_transformer_new | 3 | mid | 4.504 | high | 4.965 | 0.4611 |
| pedestal_drift_bin | ridge | 3 | mid | 3.703 | low | 4.045 | 0.3414 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.485 | high | 3.763 | 0.2787 |
| pedestal_drift_bin | mlp | 3 | low | 4.004 | mid | 4.127 | 0.1236 |
| pedestal_drift_bin | traditional_median_template_cfd_timewalk_shape | 3 | low | 1.011 | high | 1.036 | 0.02453 |
| pid_sideband | 1d_cnn | 3 | central | 5.258 | high_duplicate | 9.999 | 4.741 |
| pid_sideband | matched_filter_residual_transformer_new | 3 | low_duplicate | 4.463 | high_duplicate | 5.713 | 1.25 |
| pid_sideband | compact_waveform_transformer | 3 | central | 4.966 | high_duplicate | 5.774 | 0.8081 |
| pid_sideband | ridge | 3 | low_duplicate | 3.505 | high_duplicate | 4.102 | 0.5969 |
| pid_sideband | gradient_boosted_trees | 3 | high_duplicate | 3.572 | low_duplicate | 3.793 | 0.221 |
| pid_sideband | traditional_median_template_cfd_timewalk_shape | 3 | low_duplicate | 0.9253 | high_duplicate | 1.067 | 0.1416 |
| pid_sideband | mlp | 3 | high_duplicate | 4.014 | central | 4.079 | 0.06432 |
| pileup_separation_bin | matched_filter_residual_transformer_new | 4 | none | 4.513 | late | 8.129 | 3.616 |
| pileup_separation_bin | mlp | 4 | mid | 3.792 | late | 6.664 | 2.872 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 4.686 | mid | 6.273 | 1.588 |
| pileup_separation_bin | ridge | 4 | late | 2.941 | mid | 3.813 | 0.8712 |
| pileup_separation_bin | 1d_cnn | 4 | none | 5.546 | mid | 6.332 | 0.7855 |
| pileup_separation_bin | gradient_boosted_trees | 4 | mid | 3.38 | none | 3.818 | 0.4374 |
| pileup_separation_bin | traditional_median_template_cfd_timewalk_shape | 4 | late | 0.9874 | mid | 1.068 | 0.08029 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.878 | compact | 7.146 | 2.268 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.085 | compact | 6.258 | 1.173 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.036 | late_tail | 4.132 | 1.096 |
| pulse_shape_class | mlp | 3 | nominal | 3.54 | late_tail | 4.314 | 0.774 |
| pulse_shape_class | matched_filter_residual_transformer_new | 3 | nominal | 4.134 | late_tail | 4.897 | 0.7632 |
| pulse_shape_class | ridge | 3 | nominal | 3.387 | compact | 4.05 | 0.6636 |
| pulse_shape_class | traditional_median_template_cfd_timewalk_shape | 3 | nominal | 0.9516 | compact | 1.05 | 0.09843 |
| q_template_error_bin | 1d_cnn | 3 | template_like | 4.324 | shape_outlier | 8.796 | 4.472 |
| q_template_error_bin | compact_waveform_transformer | 3 | template_like | 3.808 | shape_outlier | 7.134 | 3.327 |
| q_template_error_bin | matched_filter_residual_transformer_new | 3 | template_like | 3.206 | shape_outlier | 6.128 | 2.922 |
| q_template_error_bin | ridge | 3 | template_like | 3.096 | shape_outlier | 4.543 | 1.448 |
| q_template_error_bin | gradient_boosted_trees | 3 | template_like | 2.853 | shape_outlier | 4.269 | 1.416 |
| q_template_error_bin | mlp | 3 | template_like | 3.532 | shape_outlier | 4.451 | 0.9196 |
| q_template_error_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate_shape | 1.008 | shape_outlier | 1.029 | 0.0216 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.195 | linear | 6.172 | 0.9765 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.127 | linear | 5.891 | 0.7642 |
| saturation_onset_bin | matched_filter_residual_transformer_new | 2 | near_saturation | 4.201 | linear | 4.92 | 0.7191 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.598 | linear | 3.929 | 0.3317 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.842 | linear | 4.163 | 0.3213 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.42 | linear | 3.724 | 0.3034 |
| saturation_onset_bin | traditional_median_template_cfd_timewalk_shape | 2 | near_saturation | 0.9199 | linear | 1.039 | 0.119 |

## Pretrigger, Rising-Edge, Peak, and Tail Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_derivative_gradient_boosted_trees | 77 | -0.2744 | 3.612 | 2.815 | 4.099 | 0 | 0.1833 |
| drop_derivative_features | 34 | -0.3108 | 3.622 | 2.737 | 3.981 | 0.009651 | 0.1845 |
| amplitude_cfd_no_derivative | 5 | -0.2454 | 3.795 | 3.283 | 4.454 | 0.1827 | 0.2123 |
| derivative_only | 43 | -0.337 | 3.823 | 3.369 | 4.812 | 0.2105 | 0.2069 |
| late_tail_curvature_window_only | 17 | -0.2481 | 4.35 | 3.84 | 5.015 | 0.7371 | 0.259 |
| onset_derivative_window_only | 14 | -0.4633 | 4.54 | 3.899 | 5.708 | 0.9274 | 0.2952 |
| pretrigger_derivative_only | 7 | -3.875 | 17.62 | 16.68 | 19.02 | 14.01 | 0.5867 |

## Interpretation, Systematics, and Caveats

This benchmark measures relative transfer on a reproducible waveform-derived
timing residual.  The raw ROOT files do not contain an independent external
picosecond timing truth for each pulse, so the numerical winner should not be
read as an absolute detector timing limit.  It answers the narrower ticket
question: whether learned pulse-shape encoders improve run-held-out
arrival-time residual prediction beyond a strong CFD, matched-filter, and
template-shape traditional fit under pedestal drift.

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

Runtime was `318.1 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29` with Python
`3.8.10`.

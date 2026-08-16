# S51a Waveform Shape-Time Identifiability Atlas

## Abstract

Ticket `2454` asks for a pulse shape and timing
identifiability atlas across stave, run family, amplitude, peak phase,
pedestal state, and mild pile-up strata.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
median-template time-walk, and shape-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `shape_time_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_median_template_cfd_timewalk_shape`** as the
winner with `sigma_68 = 1.027 ns`
`[0.821, 1.116]`.  The
traditional shape-time comparator obtains `1.027 ns`
`[0.821, 1.116]`.

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
| traditional_median_template_cfd_timewalk_shape | 4926 | 0.2621 | -0.3168 | 0.655 | 1.027 | 0.821 | 1.116 | 1.014 | 0.994 | 0.1694 | 0 | 0 |
| gradient_boosted_trees | 4926 | -0.3098 | -1.346 | 0.4852 | 3.373 | 2.661 | 3.96 | 4.217 | 1.018 | 0.1694 | 0.1581 | 0.02842 |
| mlp | 4926 | -0.4987 | -1.559 | 0.6488 | 3.851 | 3.331 | 4.758 | 4.228 | 1.02 | 0.1694 | 0.2012 | 0.0268 |
| ridge | 4926 | -0.02411 | -0.8673 | 0.9143 | 4.103 | 3.531 | 4.86 | 4.34 | 1.02 | 0.1694 | 0.2239 | 0.02741 |
| shape_time_gate_transformer_new | 4926 | -1.523 | -2.453 | -0.3906 | 4.988 | 4.33 | 5.948 | 6.063 | 0.9905 | 0.1694 | 0.3244 | 0.08404 |
| compact_waveform_transformer | 4926 | 0.1939 | -0.5781 | 0.9117 | 5.4 | 4.935 | 5.828 | 6.101 | 1.022 | 0.1694 | 0.3502 | 0.07897 |
| 1d_cnn | 4926 | 1.046 | -0.02781 | 2.261 | 5.739 | 5.19 | 6.422 | 6.85 | 1.032 | 0.1694 | 0.3918 | 0.1145 |

## Paired Deltas Against Traditional Shape-Time Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional shape-time comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_median_template_cfd_timewalk_shape | 2.346 | 1.662 | 2.965 | -0.5719 | -1.587 | 0.4114 | 0.1581 |
| mlp | traditional_median_template_cfd_timewalk_shape | 2.824 | 2.308 | 3.738 | -0.7608 | -1.919 | 0.5375 | 0.2012 |
| ridge | traditional_median_template_cfd_timewalk_shape | 3.076 | 2.523 | 3.842 | -0.2862 | -1.242 | 0.6769 | 0.2239 |
| shape_time_gate_transformer_new | traditional_median_template_cfd_timewalk_shape | 3.96 | 3.331 | 4.928 | -1.785 | -2.773 | -0.5269 | 0.3244 |
| compact_waveform_transformer | traditional_median_template_cfd_timewalk_shape | 4.373 | 3.911 | 4.891 | -0.06824 | -1.041 | 0.8562 | 0.3502 |
| 1d_cnn | traditional_median_template_cfd_timewalk_shape | 4.712 | 4.155 | 5.424 | 0.7836 | -0.2954 | 2.296 | 0.3918 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_median_template_cfd_timewalk_shape | 1230 | -0.3855 | 0.8164 | 0.9964 | 0.1856 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1230 | 0.2697 | 2.619 | 1.016 | 0.1856 | 0.1878 |
| sample_i_analysis | mlp | 1230 | 0.2542 | 3.714 | 1.017 | 0.1856 | 0.2114 |
| sample_i_analysis | ridge | 1230 | 0.4984 | 4.913 | 1.02 | 0.1856 | 0.2959 |
| sample_i_analysis | compact_waveform_transformer | 1230 | 0.4639 | 5.898 | 1.02 | 0.1856 | 0.3472 |
| sample_i_analysis | shape_time_gate_transformer_new | 1230 | -1.117 | 6.061 | 0.9879 | 0.1856 | 0.3764 |
| sample_i_analysis | 1d_cnn | 1230 | 1.083 | 6.459 | 1.035 | 0.1856 | 0.4472 |
| sample_i_calib | traditional_median_template_cfd_timewalk_shape | 597 | -0.17 | 1.105 | 0.998 | 0.1806 | 0 |
| sample_i_calib | gradient_boosted_trees | 597 | 1.833 | 3.243 | 1.026 | 0.1806 | 0.2261 |
| sample_i_calib | mlp | 597 | 1.623 | 3.698 | 1.025 | 0.1806 | 0.2663 |
| sample_i_calib | ridge | 597 | 2.052 | 4.43 | 1.026 | 0.1806 | 0.3032 |
| sample_i_calib | shape_time_gate_transformer_new | 597 | 1.051 | 4.804 | 0.9941 | 0.1806 | 0.3199 |
| sample_i_calib | compact_waveform_transformer | 597 | 1.85 | 5.122 | 1.027 | 0.1806 | 0.3417 |
| sample_i_calib | 1d_cnn | 597 | 3.247 | 6.511 | 1.035 | 0.1806 | 0.469 |
| sample_ii_analysis | traditional_median_template_cfd_timewalk_shape | 2459 | 0.4875 | 1.05 | 0.9944 | 0.1616 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2459 | -1.199 | 3.159 | 1.012 | 0.1616 | 0.1456 |
| sample_ii_analysis | ridge | 2459 | -0.701 | 3.758 | 1.014 | 0.1616 | 0.1863 |
| sample_ii_analysis | mlp | 2459 | -1.393 | 3.83 | 1.017 | 0.1616 | 0.1797 |
| sample_ii_analysis | shape_time_gate_transformer_new | 2459 | -2.331 | 4.544 | 0.9876 | 0.1616 | 0.32 |
| sample_ii_analysis | compact_waveform_transformer | 2459 | -0.5736 | 5.321 | 1.019 | 0.1616 | 0.3505 |
| sample_ii_analysis | 1d_cnn | 2459 | 0.4141 | 5.414 | 1.026 | 0.1616 | 0.3583 |
| sample_ii_calib | traditional_median_template_cfd_timewalk_shape | 640 | 0.8835 | 0.3707 | 0.9947 | 0.1578 | 0 |
| sample_ii_calib | gradient_boosted_trees | 640 | -0.8623 | 3.518 | 1.021 | 0.1578 | 0.08594 |
| sample_ii_calib | ridge | 640 | -0.3046 | 3.831 | 1.02 | 0.1578 | 0.1562 |
| sample_ii_calib | mlp | 640 | -1.209 | 4.18 | 1.022 | 0.1578 | 0.2031 |
| sample_ii_calib | shape_time_gate_transformer_new | 640 | -1.11 | 4.194 | 0.9905 | 0.1578 | 0.2453 |
| sample_ii_calib | compact_waveform_transformer | 640 | 0.2573 | 5 | 1.029 | 0.1578 | 0.3625 |
| sample_ii_calib | 1d_cnn | 640 | 1.488 | 5.19 | 1.036 | 0.1578 | 0.3422 |

| method | run | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 597 | 3.247 | 6.511 | 1.035 | 0.1806 | 0.469 |
| 1d_cnn | 50 | 620 | -1.301 | 6.547 | 1.026 | 0.1614 | 0.4306 |
| 1d_cnn | 57 | 610 | 3.719 | 5.579 | 1.05 | 0.2101 | 0.4639 |
| 1d_cnn | 58 | 594 | -0.9863 | 6.328 | 1.037 | 0.2114 | 0.4529 |
| 1d_cnn | 60 | 640 | 2.009 | 5.032 | 0.995 | 0.1554 | 0.3844 |
| 1d_cnn | 62 | 640 | 0.3188 | 4.431 | 1.005 | 0.1341 | 0.2859 |
| 1d_cnn | 64 | 640 | 1.488 | 5.19 | 1.036 | 0.1578 | 0.3422 |
| 1d_cnn | 65 | 585 | 0.02026 | 5.012 | 1.061 | 0.1477 | 0.3128 |
| compact_waveform_transformer | 42 | 597 | 1.85 | 5.122 | 1.027 | 0.1806 | 0.3417 |
| compact_waveform_transformer | 50 | 620 | -0.4853 | 6.446 | 1.011 | 0.1614 | 0.371 |
| compact_waveform_transformer | 57 | 610 | 1.978 | 4.391 | 1.031 | 0.2101 | 0.323 |
| compact_waveform_transformer | 58 | 594 | -2.592 | 6.124 | 1.028 | 0.2114 | 0.4428 |
| compact_waveform_transformer | 60 | 640 | 0.7002 | 5.253 | 1.009 | 0.1554 | 0.3359 |
| compact_waveform_transformer | 62 | 640 | -0.5305 | 5.082 | 1.014 | 0.1341 | 0.3234 |
| compact_waveform_transformer | 64 | 640 | 0.2573 | 5 | 1.029 | 0.1578 | 0.3625 |
| compact_waveform_transformer | 65 | 585 | -0.4864 | 4.812 | 1.029 | 0.1477 | 0.3026 |
| gradient_boosted_trees | 42 | 597 | 1.833 | 3.243 | 1.026 | 0.1806 | 0.2261 |
| gradient_boosted_trees | 50 | 620 | -0.2117 | 5.503 | 1.008 | 0.1614 | 0.2484 |
| gradient_boosted_trees | 57 | 610 | 1.635 | 2.662 | 1.026 | 0.2101 | 0.1262 |
| gradient_boosted_trees | 58 | 594 | -3.695 | 4.486 | 1.023 | 0.2114 | 0.3451 |
| gradient_boosted_trees | 60 | 640 | 0.1106 | 2.152 | 1.009 | 0.1554 | 0.06094 |
| gradient_boosted_trees | 62 | 640 | -1.257 | 2.218 | 1.017 | 0.1341 | 0.06875 |
| gradient_boosted_trees | 64 | 640 | -0.8623 | 3.518 | 1.021 | 0.1578 | 0.08594 |
| gradient_boosted_trees | 65 | 585 | -1.51 | 2.73 | 1.019 | 0.1477 | 0.1197 |
| mlp | 42 | 597 | 1.623 | 3.698 | 1.025 | 0.1806 | 0.2663 |
| mlp | 50 | 620 | -0.8437 | 5.312 | 1.005 | 0.1614 | 0.2903 |
| mlp | 57 | 610 | 2.007 | 2.907 | 1.031 | 0.2101 | 0.1311 |
| mlp | 58 | 594 | -3.279 | 5.378 | 1.02 | 0.2114 | 0.4091 |
| mlp | 60 | 640 | -0.01762 | 3.02 | 1.02 | 0.1554 | 0.09531 |
| mlp | 62 | 640 | -1.678 | 3.118 | 1.032 | 0.1341 | 0.09062 |
| mlp | 64 | 640 | -1.209 | 4.18 | 1.022 | 0.1578 | 0.2031 |
| mlp | 65 | 585 | -1.524 | 3.353 | 1.025 | 0.1477 | 0.1368 |
| ridge | 42 | 597 | 2.052 | 4.43 | 1.026 | 0.1806 | 0.3032 |
| ridge | 50 | 620 | -1.059 | 5.718 | 1.012 | 0.1614 | 0.3548 |
| ridge | 57 | 610 | 2.143 | 3.418 | 1.031 | 0.2101 | 0.2361 |
| ridge | 58 | 594 | -2.07 | 4.863 | 1.017 | 0.2114 | 0.3906 |
| ridge | 60 | 640 | 0.4502 | 3.296 | 1.016 | 0.1554 | 0.1047 |
| ridge | 62 | 640 | -1.139 | 2.884 | 1.026 | 0.1341 | 0.1297 |
| ridge | 64 | 640 | -0.3046 | 3.831 | 1.02 | 0.1578 | 0.1562 |
| ridge | 65 | 585 | -0.738 | 3.348 | 1.019 | 0.1477 | 0.1299 |
| shape_time_gate_transformer_new | 42 | 597 | 1.051 | 4.804 | 0.9941 | 0.1806 | 0.3199 |
| shape_time_gate_transformer_new | 50 | 620 | -2.879 | 8.772 | 0.9682 | 0.1614 | 0.5097 |
| shape_time_gate_transformer_new | 57 | 610 | 0.6788 | 4.322 | 1.01 | 0.2101 | 0.241 |
| shape_time_gate_transformer_new | 58 | 594 | -3.632 | 5.482 | 1.002 | 0.2114 | 0.4293 |
| shape_time_gate_transformer_new | 60 | 640 | -1.194 | 4.194 | 0.9677 | 0.1554 | 0.2516 |
| shape_time_gate_transformer_new | 62 | 640 | -2.613 | 4.047 | 0.9659 | 0.1341 | 0.3 |
| shape_time_gate_transformer_new | 64 | 640 | -1.11 | 4.194 | 0.9905 | 0.1578 | 0.2453 |
| shape_time_gate_transformer_new | 65 | 585 | -2.594 | 4.091 | 1.007 | 0.1477 | 0.306 |
| traditional_median_template_cfd_timewalk_shape | 42 | 597 | -0.17 | 1.105 | 0.998 | 0.1806 | 0 |
| traditional_median_template_cfd_timewalk_shape | 50 | 620 | 0.1494 | 0.7349 | 0.9983 | 0.1614 | 0 |
| traditional_median_template_cfd_timewalk_shape | 57 | 610 | -0.6798 | 0.588 | 0.9955 | 0.2101 | 0 |
| traditional_median_template_cfd_timewalk_shape | 58 | 594 | 0.636 | 0.6301 | 0.995 | 0.2114 | 0 |
| traditional_median_template_cfd_timewalk_shape | 60 | 640 | -0.3871 | 1.338 | 0.9933 | 0.1554 | 0 |
| traditional_median_template_cfd_timewalk_shape | 62 | 640 | 0.68 | 0.9581 | 0.9938 | 0.1341 | 0 |
| traditional_median_template_cfd_timewalk_shape | 64 | 640 | 0.8835 | 0.3707 | 0.9947 | 0.1578 | 0 |
| traditional_median_template_cfd_timewalk_shape | 65 | 585 | 0.773 | 1.239 | 0.9922 | 0.1477 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | calibration_slope | q_template_mse | failure_rate_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1418 | 0.4549 | 6.455 | 0.9672 | 0.2916 | 0.4372 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1418 | -1.831 | 5.278 | 1.016 | 0.2916 | 0.3688 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1418 | -0.39 | 3.315 | 1.01 | 0.2916 | 0.1629 |
| curvature_energy_bin | curved | mlp | 1418 | -0.8525 | 3.825 | 1.02 | 0.2916 | 0.2193 |
| curvature_energy_bin | curved | ridge | 1418 | -0.6138 | 3.936 | 1.001 | 0.2916 | 0.2207 |
| curvature_energy_bin | curved | shape_time_gate_transformer_new | 1418 | -1.096 | 5.729 | 0.9302 | 0.2916 | 0.3709 |
| curvature_energy_bin | curved | traditional_median_template_cfd_timewalk_shape | 1418 | 0.2625 | 1.129 | 0.9935 | 0.2916 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1734 | 2.684 | 5.039 | 1.024 | 0.1232 | 0.4066 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1734 | 0.9034 | 5.147 | 1.031 | 0.1232 | 0.3449 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1734 | -0.1138 | 3.465 | 1.013 | 0.1232 | 0.169 |
| curvature_energy_bin | moderate | mlp | 1734 | -0.4064 | 3.737 | 1.013 | 0.1232 | 0.1909 |
| curvature_energy_bin | moderate | ridge | 1734 | -0.07016 | 4.125 | 1.018 | 0.1232 | 0.2243 |
| curvature_energy_bin | moderate | shape_time_gate_transformer_new | 1734 | -1.569 | 4.609 | 0.9785 | 0.1232 | 0.3103 |
| curvature_energy_bin | moderate | traditional_median_template_cfd_timewalk_shape | 1734 | 0.3689 | 0.9639 | 0.995 | 0.1232 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1774 | -0.1896 | 5.121 | 1.083 | 0.1168 | 0.341 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1774 | 0.9177 | 4.843 | 0.9999 | 0.1168 | 0.3405 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1774 | -0.3757 | 3.329 | 1.025 | 0.1168 | 0.1437 |
| curvature_energy_bin | smooth | mlp | 1774 | -0.3317 | 3.875 | 1.022 | 0.1168 | 0.1967 |
| curvature_energy_bin | smooth | ridge | 1774 | 0.8 | 3.986 | 1.023 | 0.1168 | 0.226 |
| curvature_energy_bin | smooth | shape_time_gate_transformer_new | 1774 | -1.792 | 4.651 | 1.033 | 0.1168 | 0.301 |
| curvature_energy_bin | smooth | traditional_median_template_cfd_timewalk_shape | 1774 | 0.144 | 1.071 | 0.9944 | 0.1168 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1641 | 0.1998 | 5.389 | 0.905 | 0.04152 | 0.3577 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1641 | -0.3066 | 5.276 | 1.14 | 0.04152 | 0.3382 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1641 | -0.6315 | 2.98 | 0.9876 | 0.04152 | 0.1158 |
| derivative_onset_bin | nominal | mlp | 1641 | -0.8414 | 3.586 | 1.008 | 0.04152 | 0.1682 |
| derivative_onset_bin | nominal | ridge | 1641 | -0.7361 | 3.713 | 1.03 | 0.04152 | 0.1877 |
| derivative_onset_bin | nominal | shape_time_gate_transformer_new | 1641 | -2.08 | 4.902 | 1.099 | 0.04152 | 0.309 |
| derivative_onset_bin | nominal | traditional_median_template_cfd_timewalk_shape | 1641 | 0.3336 | 1.039 | 0.9855 | 0.04152 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1788 | 1.085 | 5.44 | 0.7827 | 0.04409 | 0.3624 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1788 | 0.1767 | 5.367 | 0.9983 | 0.04409 | 0.3596 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1788 | -0.5173 | 2.956 | 0.9586 | 0.04409 | 0.09787 |
| derivative_onset_bin | sharp | mlp | 1788 | -0.7473 | 3.426 | 0.9927 | 0.04409 | 0.1521 |
| derivative_onset_bin | sharp | ridge | 1788 | -0.4221 | 3.742 | 1.007 | 0.04409 | 0.179 |
| derivative_onset_bin | sharp | shape_time_gate_transformer_new | 1788 | -1.753 | 4.563 | 1.065 | 0.04409 | 0.2824 |
| derivative_onset_bin | sharp | traditional_median_template_cfd_timewalk_shape | 1788 | 0.4029 | 1.021 | 0.9843 | 0.04409 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1497 | 2.063 | 6.934 | 1.056 | 0.4592 | 0.4643 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1497 | 0.7728 | 5.453 | 1.028 | 0.4592 | 0.352 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1497 | 0.8909 | 4.234 | 1.012 | 0.4592 | 0.2766 |
| derivative_onset_bin | slow | mlp | 1497 | 0.2367 | 4.6 | 1.021 | 0.4592 | 0.2959 |
| derivative_onset_bin | slow | ridge | 1497 | 1.313 | 4.367 | 1.01 | 0.4592 | 0.3173 |
| derivative_onset_bin | slow | shape_time_gate_transformer_new | 1497 | -0.5935 | 6.032 | 0.9745 | 0.4592 | 0.3914 |
| derivative_onset_bin | slow | traditional_median_template_cfd_timewalk_shape | 1497 | 0.04601 | 0.9847 | 0.995 | 0.4592 | 0 |
| energy_bin | q1_low | 1d_cnn | 1292 | -0.5447 | 5.858 | 1.078 | 0.4032 | 0.4009 |
| energy_bin | q1_low | compact_waveform_transformer | 1292 | 0.5588 | 5.158 | 1.011 | 0.4032 | 0.3553 |
| energy_bin | q1_low | gradient_boosted_trees | 1292 | -0.335 | 3.494 | 1.019 | 0.4032 | 0.1525 |
| energy_bin | q1_low | mlp | 1292 | -0.2822 | 3.912 | 1.021 | 0.4032 | 0.2082 |
| energy_bin | q1_low | ridge | 1292 | 0.9915 | 4.099 | 1.022 | 0.4032 | 0.2438 |
| energy_bin | q1_low | shape_time_gate_transformer_new | 1292 | -1.118 | 6.042 | 0.9798 | 0.4032 | 0.4056 |
| energy_bin | q1_low | traditional_median_template_cfd_timewalk_shape | 1292 | -0.0966 | 1.154 | 0.9916 | 0.4032 | 0 |
| energy_bin | q2 | 1d_cnn | 1375 | 1.045 | 4.958 | 1.039 | 0.1041 | 0.3265 |
| energy_bin | q2 | compact_waveform_transformer | 1375 | 1.131 | 4.844 | 1.029 | 0.1041 | 0.3244 |
| energy_bin | q2 | gradient_boosted_trees | 1375 | -0.1322 | 3.221 | 1.018 | 0.1041 | 0.1476 |
| energy_bin | q2 | mlp | 1375 | -0.5285 | 3.839 | 1.021 | 0.1041 | 0.1964 |
| energy_bin | q2 | ridge | 1375 | 0.1102 | 4.11 | 1.023 | 0.1041 | 0.2211 |
| energy_bin | q2 | shape_time_gate_transformer_new | 1375 | -1.531 | 4.177 | 1.02 | 0.1041 | 0.2647 |
| energy_bin | q2 | traditional_median_template_cfd_timewalk_shape | 1375 | 0.3477 | 0.9321 | 0.9951 | 0.1041 | 0 |
| energy_bin | q3 | 1d_cnn | 1275 | 3.677 | 4.31 | 0.9793 | 0.08921 | 0.4408 |
| energy_bin | q3 | compact_waveform_transformer | 1275 | 0.1456 | 5.447 | 1.023 | 0.08921 | 0.36 |
| energy_bin | q3 | gradient_boosted_trees | 1275 | -0.1956 | 3.221 | 1.013 | 0.08921 | 0.1498 |
| energy_bin | q3 | mlp | 1275 | -0.5863 | 3.722 | 1.009 | 0.08921 | 0.1867 |
| energy_bin | q3 | ridge | 1275 | -0.1105 | 4.106 | 1.015 | 0.08921 | 0.2251 |
| energy_bin | q3 | shape_time_gate_transformer_new | 1275 | -2.618 | 4.625 | 0.9981 | 0.08921 | 0.3325 |
| energy_bin | q3 | traditional_median_template_cfd_timewalk_shape | 1275 | 0.4335 | 0.9565 | 0.9955 | 0.08921 | 0 |
| energy_bin | q4_high | 1d_cnn | 984 | -1.105 | 6.124 | 0.9892 | 0.0575 | 0.4075 |
| energy_bin | q4_high | compact_waveform_transformer | 984 | -2.094 | 5.181 | 1.042 | 0.0575 | 0.3669 |
| energy_bin | q4_high | gradient_boosted_trees | 984 | -0.6235 | 3.38 | 1.025 | 0.0575 | 0.1911 |
| energy_bin | q4_high | mlp | 984 | -0.6393 | 3.812 | 1.037 | 0.0575 | 0.2175 |
| energy_bin | q4_high | ridge | 984 | -0.6978 | 3.672 | 1.015 | 0.0575 | 0.2002 |
| energy_bin | q4_high | shape_time_gate_transformer_new | 984 | -0.5762 | 5.226 | 0.9491 | 0.0575 | 0.2907 |
| energy_bin | q4_high | traditional_median_template_cfd_timewalk_shape | 984 | 0.2403 | 1.139 | 0.9942 | 0.0575 | 0 |
| late_tail_morphology | compact | 1d_cnn | 2989 | 0.5623 | 5.558 | 0.9159 | 0.1414 | 0.377 |
| late_tail_morphology | compact | compact_waveform_transformer | 2989 | 0.1032 | 5.463 | 1.124 | 0.1414 | 0.3637 |
| late_tail_morphology | compact | gradient_boosted_trees | 2989 | -0.6191 | 3.038 | 0.967 | 0.1414 | 0.1141 |
| late_tail_morphology | compact | mlp | 2989 | -0.88 | 3.534 | 1.003 | 0.1414 | 0.1609 |
| late_tail_morphology | compact | ridge | 2989 | -0.4663 | 3.998 | 1.003 | 0.1414 | 0.2017 |
| late_tail_morphology | compact | shape_time_gate_transformer_new | 2989 | -1.749 | 5.23 | 0.9375 | 0.1414 | 0.3597 |
| late_tail_morphology | compact | traditional_median_template_cfd_timewalk_shape | 2989 | 0.337 | 1.055 | 0.9876 | 0.1414 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 507 | 0.6754 | 4.832 | 0.7709 | 0.03745 | 0.2978 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 507 | -1.676 | 4.677 | 0.9014 | 0.03745 | 0.2821 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 507 | -0.03628 | 2.884 | 1.081 | 0.03745 | 0.146 |
| late_tail_morphology | diffuse_tail | mlp | 507 | -0.4367 | 3.524 | 1.005 | 0.03745 | 0.1933 |
| late_tail_morphology | diffuse_tail | ridge | 507 | -0.6304 | 3.433 | 1.208 | 0.03745 | 0.1815 |
| late_tail_morphology | diffuse_tail | shape_time_gate_transformer_new | 507 | -2.289 | 3.537 | 1.09 | 0.03745 | 0.2189 |
| late_tail_morphology | diffuse_tail | traditional_median_template_cfd_timewalk_shape | 507 | 0.6184 | 1.029 | 0.9535 | 0.03745 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 342 | -1.153 | 9.4 | 0.9761 | 0.4988 | 0.5292 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 342 | 0.4672 | 5.632 | 1.071 | 0.4988 | 0.3567 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 342 | -0.5058 | 3.221 | 1.049 | 0.4988 | 0.1491 |
| late_tail_morphology | late_derivative_bump | mlp | 342 | -0.6905 | 4.079 | 1.037 | 0.4988 | 0.2339 |
| late_tail_morphology | late_derivative_bump | ridge | 342 | 0.05783 | 3.525 | 0.942 | 0.4988 | 0.2164 |
| late_tail_morphology | late_derivative_bump | shape_time_gate_transformer_new | 342 | 1.212 | 5.277 | 1.004 | 0.4988 | 0.3187 |
| late_tail_morphology | late_derivative_bump | traditional_median_template_cfd_timewalk_shape | 342 | -0.1196 | 1.111 | 0.9942 | 0.4988 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1088 | 2.72 | 5.926 | 1.079 | 0.2041 | 0.4329 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1088 | 1.375 | 5.129 | 1.041 | 0.2041 | 0.3428 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1088 | 0.9937 | 4.477 | 1.011 | 0.2041 | 0.2877 |
| late_tail_morphology | late_rising_tail | mlp | 1088 | 0.3959 | 4.661 | 1.036 | 0.2041 | 0.3051 |
| late_tail_morphology | late_rising_tail | ridge | 1088 | 1.39 | 4.189 | 1.018 | 0.2041 | 0.307 |
| late_tail_morphology | late_rising_tail | shape_time_gate_transformer_new | 1088 | -1.112 | 4.571 | 1.016 | 0.2041 | 0.2785 |
| late_tail_morphology | late_rising_tail | traditional_median_template_cfd_timewalk_shape | 1088 | 0.02813 | 0.9374 | 0.9902 | 0.2041 | 0 |
| peak_phase_bin | early_phase | 1d_cnn | 2147 | 1.239 | 5.795 | 1.048 | 0.1602 | 0.4024 |
| peak_phase_bin | early_phase | compact_waveform_transformer | 2147 | -0.1231 | 5.702 | 1.041 | 0.1602 | 0.3796 |
| peak_phase_bin | early_phase | gradient_boosted_trees | 2147 | -0.3493 | 3.376 | 1.025 | 0.1602 | 0.1709 |
| peak_phase_bin | early_phase | mlp | 2147 | -0.3775 | 3.9 | 1.026 | 0.1602 | 0.2091 |
| peak_phase_bin | early_phase | ridge | 2147 | -0.2226 | 4.191 | 1.027 | 0.1602 | 0.2366 |
| peak_phase_bin | early_phase | shape_time_gate_transformer_new | 2147 | -1.532 | 5.004 | 1.022 | 0.1602 | 0.3088 |
| peak_phase_bin | early_phase | traditional_median_template_cfd_timewalk_shape | 2147 | 0.3033 | 1.036 | 0.9935 | 0.1602 | 0 |
| peak_phase_bin | late_phase | 1d_cnn | 1139 | 1.045 | 5.848 | 1.016 | 0.1619 | 0.3916 |
| peak_phase_bin | late_phase | compact_waveform_transformer | 1139 | 0.1374 | 5.168 | 1.012 | 0.1619 | 0.3319 |
| peak_phase_bin | late_phase | gradient_boosted_trees | 1139 | -0.2309 | 3.335 | 1.004 | 0.1619 | 0.1466 |
| peak_phase_bin | late_phase | mlp | 1139 | -0.6418 | 3.72 | 1.005 | 0.1619 | 0.194 |
| peak_phase_bin | late_phase | ridge | 1139 | -0.008522 | 3.897 | 1.002 | 0.1619 | 0.209 |
| peak_phase_bin | late_phase | shape_time_gate_transformer_new | 1139 | -1.062 | 5.74 | 0.9252 | 0.1619 | 0.3863 |
| peak_phase_bin | late_phase | traditional_median_template_cfd_timewalk_shape | 1139 | 0.292 | 0.982 | 0.9955 | 0.1619 | 0 |
| peak_phase_bin | mid_phase | 1d_cnn | 1640 | 0.8808 | 5.634 | 1.024 | 0.1865 | 0.378 |
| peak_phase_bin | mid_phase | compact_waveform_transformer | 1640 | 0.5147 | 4.85 | 1.005 | 0.1865 | 0.3244 |
| peak_phase_bin | mid_phase | gradient_boosted_trees | 1640 | -0.2978 | 3.33 | 1.019 | 0.1865 | 0.1494 |
| peak_phase_bin | mid_phase | mlp | 1640 | -0.5506 | 3.897 | 1.022 | 0.1865 | 0.1957 |
| peak_phase_bin | mid_phase | ridge | 1640 | 0.2644 | 4.071 | 1.022 | 0.1865 | 0.2177 |
| peak_phase_bin | mid_phase | shape_time_gate_transformer_new | 1640 | -1.836 | 4.655 | 1.004 | 0.1865 | 0.3018 |
| peak_phase_bin | mid_phase | traditional_median_template_cfd_timewalk_shape | 1640 | 0.1708 | 1.059 | 0.9937 | 0.1865 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1586 | 1.07 | 6.716 | 1.021 | 0.3643 | 0.4767 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1586 | -0.8541 | 6.187 | 1.037 | 0.3643 | 0.425 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1586 | -0.1509 | 3.545 | 1.015 | 0.3643 | 0.1822 |
| pedestal_drift_bin | high | mlp | 1586 | -0.1717 | 4.152 | 1.024 | 0.3643 | 0.2377 |
| pedestal_drift_bin | high | ridge | 1586 | 0.26 | 4.308 | 1.01 | 0.3643 | 0.2478 |
| pedestal_drift_bin | high | shape_time_gate_transformer_new | 1586 | -1.275 | 6.36 | 0.9745 | 0.3643 | 0.4363 |
| pedestal_drift_bin | high | traditional_median_template_cfd_timewalk_shape | 1586 | 0.3195 | 1.051 | 0.9946 | 0.3643 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1618 | 1.188 | 5.343 | 1.041 | 0.07852 | 0.3609 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1618 | 0.5205 | 4.845 | 1.012 | 0.07852 | 0.3041 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1618 | -0.2915 | 3.201 | 1.023 | 0.07852 | 0.152 |
| pedestal_drift_bin | low | mlp | 1618 | -0.4786 | 3.709 | 1.023 | 0.07852 | 0.1879 |
| pedestal_drift_bin | low | ridge | 1618 | -0.1616 | 4.091 | 1.031 | 0.07852 | 0.2138 |
| pedestal_drift_bin | low | shape_time_gate_transformer_new | 1618 | -1.59 | 4.529 | 1 | 0.07852 | 0.2868 |
| pedestal_drift_bin | low | traditional_median_template_cfd_timewalk_shape | 1618 | 0.1921 | 1.015 | 0.9935 | 0.07852 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1722 | 0.9408 | 5.197 | 1.034 | 0.07527 | 0.3426 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1722 | 0.5968 | 4.89 | 1 | 0.07527 | 0.3246 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1722 | -0.4403 | 3.209 | 1.025 | 0.07527 | 0.1417 |
| pedestal_drift_bin | mid | mlp | 1722 | -0.7225 | 3.718 | 1.02 | 0.07527 | 0.18 |
| pedestal_drift_bin | mid | ridge | 1722 | -0.0935 | 3.884 | 1.027 | 0.07527 | 0.2114 |
| pedestal_drift_bin | mid | shape_time_gate_transformer_new | 1722 | -1.564 | 4.317 | 1 | 0.07527 | 0.2567 |
| pedestal_drift_bin | mid | traditional_median_template_cfd_timewalk_shape | 1722 | 0.2957 | 1.03 | 0.9937 | 0.07527 | 0 |
| pid_sideband | central | 1d_cnn | 3404 | 1.227 | 5.371 | 1.04 | 0.08254 | 0.3634 |
| pid_sideband | central | compact_waveform_transformer | 3404 | 0.8415 | 4.841 | 1.006 | 0.08254 | 0.3296 |
| pid_sideband | central | gradient_boosted_trees | 3404 | -0.2932 | 3.314 | 1.022 | 0.08254 | 0.1548 |
| pid_sideband | central | mlp | 3404 | -0.3563 | 3.809 | 1.02 | 0.08254 | 0.1968 |
| pid_sideband | central | ridge | 3404 | 0.09774 | 4.168 | 1.028 | 0.08254 | 0.2288 |
| pid_sideband | central | shape_time_gate_transformer_new | 3404 | -1.423 | 4.488 | 0.9987 | 0.08254 | 0.2785 |
| pid_sideband | central | traditional_median_template_cfd_timewalk_shape | 3404 | 0.2014 | 1.03 | 0.9938 | 0.08254 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 796 | 0.2358 | 8.397 | 0.6784 | 0.6498 | 0.5653 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 796 | -3.659 | 5.875 | 0.8505 | 0.6498 | 0.4837 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 796 | -0.1662 | 3.475 | 1.095 | 0.6498 | 0.1759 |
| pid_sideband | high_duplicate | mlp | 796 | -1.029 | 4.253 | 1.03 | 0.6498 | 0.2387 |
| pid_sideband | high_duplicate | ridge | 796 | -0.1156 | 4.491 | 0.9407 | 0.6498 | 0.2663 |
| pid_sideband | high_duplicate | shape_time_gate_transformer_new | 796 | -2.655 | 8.454 | 0.6843 | 0.6498 | 0.6156 |
| pid_sideband | high_duplicate | traditional_median_template_cfd_timewalk_shape | 796 | 0.3972 | 1.094 | 0.9871 | 0.6498 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 726 | 0.683 | 5.11 | 1.025 | 0.04988 | 0.3347 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 726 | -0.1601 | 4.719 | 0.9889 | 0.04988 | 0.3003 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 726 | -0.4433 | 3.313 | 1.027 | 0.04988 | 0.1543 |
| pid_sideband | low_duplicate | mlp | 726 | -0.869 | 3.725 | 1.016 | 0.04988 | 0.1804 |
| pid_sideband | low_duplicate | ridge | 726 | -0.6174 | 3.414 | 1.014 | 0.04988 | 0.1543 |
| pid_sideband | low_duplicate | shape_time_gate_transformer_new | 726 | -1.197 | 4.235 | 0.9781 | 0.04988 | 0.2204 |
| pid_sideband | low_duplicate | traditional_median_template_cfd_timewalk_shape | 726 | 0.4658 | 1.032 | 0.992 | 0.04988 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1499 | -0.2951 | 5.79 | 0.8101 | 0.03816 | 0.3823 |
| pileup_separation_bin | close | compact_waveform_transformer | 1499 | -0.1739 | 5.234 | 0.9271 | 0.03816 | 0.3336 |
| pileup_separation_bin | close | gradient_boosted_trees | 1499 | -0.5819 | 3.043 | 0.948 | 0.03816 | 0.1241 |
| pileup_separation_bin | close | mlp | 1499 | -0.7351 | 3.45 | 0.9807 | 0.03816 | 0.1574 |
| pileup_separation_bin | close | ridge | 1499 | -0.8211 | 3.626 | 1.006 | 0.03816 | 0.1955 |
| pileup_separation_bin | close | shape_time_gate_transformer_new | 1499 | -1.577 | 5.034 | 1.053 | 0.03816 | 0.3276 |
| pileup_separation_bin | close | traditional_median_template_cfd_timewalk_shape | 1499 | 0.3336 | 1.077 | 0.9821 | 0.03816 | 0 |
| pileup_separation_bin | late | 1d_cnn | 3 | -2.571 | 8.629 | 3.239 | 0.604 | 0.3333 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -5.167 | 2.971 | 0.8192 | 0.604 | 0.6667 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | -1.823 | 1.095 | 0.9363 | 0.604 | 0 |
| pileup_separation_bin | late | mlp | 3 | -3.735 | 6.599 | 1.964 | 0.604 | 0.3333 |
| pileup_separation_bin | late | ridge | 3 | 1.974 | 4.414 | 0.7382 | 0.604 | 0.3333 |
| pileup_separation_bin | late | shape_time_gate_transformer_new | 3 | -0.3715 | 18.54 | -2.07 | 0.604 | 0.3333 |
| pileup_separation_bin | late | traditional_median_template_cfd_timewalk_shape | 3 | 2.125 | 0.4459 | 1.036 | 0.604 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1056 | 3.215 | 5.877 | 0.9681 | 0.1246 | 0.4924 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1056 | -2.115 | 5.118 | 1.144 | 0.1246 | 0.3835 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1056 | -0.607 | 3.105 | 0.9634 | 0.1246 | 0.1222 |
| pileup_separation_bin | mid | mlp | 1056 | -1.189 | 3.701 | 0.9946 | 0.1246 | 0.178 |
| pileup_separation_bin | mid | ridge | 1056 | -0.5836 | 3.919 | 0.9669 | 0.1246 | 0.2055 |
| pileup_separation_bin | mid | shape_time_gate_transformer_new | 1056 | -2.044 | 5.594 | 0.942 | 0.1246 | 0.4015 |
| pileup_separation_bin | mid | traditional_median_template_cfd_timewalk_shape | 1056 | 0.4549 | 1.078 | 0.988 | 0.1246 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2368 | 1.13 | 5.36 | 1.07 | 0.2719 | 0.353 |
| pileup_separation_bin | none | compact_waveform_transformer | 2368 | 1.381 | 4.809 | 1.003 | 0.2719 | 0.3454 |
| pileup_separation_bin | none | gradient_boosted_trees | 2368 | 0.1409 | 3.686 | 1.018 | 0.2719 | 0.1959 |
| pileup_separation_bin | none | mlp | 2368 | -0.1716 | 4.002 | 1.019 | 0.2719 | 0.239 |
| pileup_separation_bin | none | ridge | 2368 | 0.8793 | 3.918 | 1.014 | 0.2719 | 0.25 |
| pileup_separation_bin | none | shape_time_gate_transformer_new | 2368 | -1.309 | 4.491 | 0.987 | 0.2719 | 0.288 |
| pileup_separation_bin | none | traditional_median_template_cfd_timewalk_shape | 2368 | 0.1441 | 1.024 | 0.9951 | 0.2719 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1674 | 0.09599 | 6.568 | 0.8747 | 0.3271 | 0.4534 |
| pulse_shape_class | compact | compact_waveform_transformer | 1674 | -0.5532 | 6.12 | 1.167 | 0.3271 | 0.4289 |
| pulse_shape_class | compact | gradient_boosted_trees | 1674 | -0.5932 | 3.26 | 0.9759 | 0.3271 | 0.1308 |
| pulse_shape_class | compact | mlp | 1674 | -0.9677 | 3.72 | 1.011 | 0.3271 | 0.1834 |
| pulse_shape_class | compact | ridge | 1674 | -0.02647 | 4.368 | 0.9926 | 0.3271 | 0.2455 |
| pulse_shape_class | compact | shape_time_gate_transformer_new | 1674 | -2.177 | 6.2 | 0.8886 | 0.3271 | 0.4743 |
| pulse_shape_class | compact | traditional_median_template_cfd_timewalk_shape | 1674 | 0.2995 | 1.108 | 0.9849 | 0.3271 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1619 | 1.918 | 5.435 | 1.066 | 0.1492 | 0.3879 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1619 | 0.303 | 5.115 | 1.04 | 0.1492 | 0.3206 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1619 | 0.5243 | 4.051 | 1.016 | 0.1492 | 0.2409 |
| pulse_shape_class | late_tail | mlp | 1619 | 0.08584 | 4.314 | 1.023 | 0.1492 | 0.2668 |
| pulse_shape_class | late_tail | ridge | 1619 | 0.659 | 4.099 | 1.023 | 0.1492 | 0.2656 |
| pulse_shape_class | late_tail | shape_time_gate_transformer_new | 1619 | -1.529 | 4.099 | 1.008 | 0.1492 | 0.2594 |
| pulse_shape_class | late_tail | traditional_median_template_cfd_timewalk_shape | 1619 | 0.1599 | 0.9606 | 0.9898 | 0.1492 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1633 | 0.8477 | 5.111 | 0.7104 | 0.02764 | 0.3325 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1633 | 0.6224 | 4.613 | 1.139 | 0.02764 | 0.2988 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1633 | -0.6165 | 2.833 | 0.9532 | 0.02764 | 0.1041 |
| pulse_shape_class | nominal | mlp | 1633 | -0.7733 | 3.482 | 0.9832 | 0.02764 | 0.1543 |
| pulse_shape_class | nominal | ridge | 1633 | -0.7508 | 3.487 | 1.109 | 0.02764 | 0.1604 |
| pulse_shape_class | nominal | shape_time_gate_transformer_new | 1633 | -1.145 | 4.455 | 0.9434 | 0.02764 | 0.2352 |
| pulse_shape_class | nominal | traditional_median_template_cfd_timewalk_shape | 1633 | 0.3099 | 0.9948 | 0.9666 | 0.02764 | 0 |
| q_template_error_bin | moderate_shape | 1d_cnn | 1736 | 2.123 | 5.444 | 0.9377 | 0.05338 | 0.4032 |
| q_template_error_bin | moderate_shape | compact_waveform_transformer | 1736 | -0.08939 | 6.11 | 1.021 | 0.05338 | 0.4418 |
| q_template_error_bin | moderate_shape | gradient_boosted_trees | 1736 | -0.589 | 3.051 | 1.005 | 0.05338 | 0.1158 |
| q_template_error_bin | moderate_shape | mlp | 1736 | -0.4959 | 3.621 | 1.013 | 0.05338 | 0.1786 |
| q_template_error_bin | moderate_shape | ridge | 1736 | 0.3981 | 4.328 | 1.089 | 0.05338 | 0.2454 |
| q_template_error_bin | moderate_shape | shape_time_gate_transformer_new | 1736 | -1.826 | 5.149 | 1.069 | 0.05338 | 0.3502 |
| q_template_error_bin | moderate_shape | traditional_median_template_cfd_timewalk_shape | 1736 | 0.4326 | 1.009 | 0.9898 | 0.05338 | 0 |
| q_template_error_bin | shape_outlier | 1d_cnn | 1537 | 2.078 | 7.306 | 1.05 | 0.466 | 0.4938 |
| q_template_error_bin | shape_outlier | compact_waveform_transformer | 1537 | -0.1269 | 6.057 | 1.039 | 0.466 | 0.4086 |
| q_template_error_bin | shape_outlier | gradient_boosted_trees | 1537 | 0.6284 | 4.076 | 1.014 | 0.466 | 0.255 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | moderate | 5.039 | curved | 6.455 | 1.415 |
| curvature_energy_bin | shape_time_gate_transformer_new | 3 | moderate | 4.609 | curved | 5.729 | 1.121 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.843 | curved | 5.278 | 0.4348 |
| curvature_energy_bin | ridge | 3 | curved | 3.936 | moderate | 4.125 | 0.1894 |
| curvature_energy_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate | 0.9639 | curved | 1.129 | 0.1655 |
| curvature_energy_bin | gradient_boosted_trees | 3 | curved | 3.315 | moderate | 3.465 | 0.1496 |
| curvature_energy_bin | mlp | 3 | moderate | 3.737 | smooth | 3.875 | 0.1374 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 5.389 | slow | 6.934 | 1.545 |
| derivative_onset_bin | shape_time_gate_transformer_new | 3 | sharp | 4.563 | slow | 6.032 | 1.469 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 2.956 | slow | 4.234 | 1.278 |
| derivative_onset_bin | mlp | 3 | sharp | 3.426 | slow | 4.6 | 1.174 |
| derivative_onset_bin | ridge | 3 | nominal | 3.713 | slow | 4.367 | 0.6544 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 5.276 | slow | 5.453 | 0.1764 |
| derivative_onset_bin | traditional_median_template_cfd_timewalk_shape | 3 | slow | 0.9847 | nominal | 1.039 | 0.05435 |
| energy_bin | shape_time_gate_transformer_new | 4 | q2 | 4.177 | q1_low | 6.042 | 1.865 |
| energy_bin | 1d_cnn | 4 | q3 | 4.31 | q4_high | 6.124 | 1.814 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 4.844 | q3 | 5.447 | 0.6028 |
| energy_bin | ridge | 4 | q4_high | 3.672 | q2 | 4.11 | 0.4382 |
| energy_bin | gradient_boosted_trees | 4 | q3 | 3.221 | q1_low | 3.494 | 0.2731 |
| energy_bin | traditional_median_template_cfd_timewalk_shape | 4 | q2 | 0.9321 | q1_low | 1.154 | 0.2217 |
| energy_bin | mlp | 4 | q3 | 3.722 | q1_low | 3.912 | 0.19 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.832 | late_derivative_bump | 9.4 | 4.568 |
| late_tail_morphology | shape_time_gate_transformer_new | 4 | diffuse_tail | 3.537 | late_derivative_bump | 5.277 | 1.74 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 2.884 | late_rising_tail | 4.477 | 1.594 |
| late_tail_morphology | mlp | 4 | diffuse_tail | 3.524 | late_rising_tail | 4.661 | 1.136 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.677 | late_derivative_bump | 5.632 | 0.9547 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.433 | late_rising_tail | 4.189 | 0.7561 |
| late_tail_morphology | traditional_median_template_cfd_timewalk_shape | 4 | late_rising_tail | 0.9374 | late_derivative_bump | 1.111 | 0.1733 |
| peak_phase_bin | shape_time_gate_transformer_new | 3 | mid_phase | 4.655 | late_phase | 5.74 | 1.085 |
| peak_phase_bin | compact_waveform_transformer | 3 | mid_phase | 4.85 | early_phase | 5.702 | 0.8518 |
| peak_phase_bin | ridge | 3 | late_phase | 3.897 | early_phase | 4.191 | 0.2939 |
| peak_phase_bin | 1d_cnn | 3 | mid_phase | 5.634 | late_phase | 5.848 | 0.2142 |
| peak_phase_bin | mlp | 3 | late_phase | 3.72 | early_phase | 3.9 | 0.1796 |
| peak_phase_bin | traditional_median_template_cfd_timewalk_shape | 3 | late_phase | 0.982 | mid_phase | 1.059 | 0.07676 |
| peak_phase_bin | gradient_boosted_trees | 3 | mid_phase | 3.33 | early_phase | 3.376 | 0.04644 |
| pedestal_drift_bin | shape_time_gate_transformer_new | 3 | mid | 4.317 | high | 6.36 | 2.043 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.197 | high | 6.716 | 1.518 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | low | 4.845 | high | 6.187 | 1.342 |
| pedestal_drift_bin | mlp | 3 | low | 3.709 | high | 4.152 | 0.4426 |
| pedestal_drift_bin | ridge | 3 | mid | 3.884 | high | 4.308 | 0.4244 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.201 | high | 3.545 | 0.3445 |
| pedestal_drift_bin | traditional_median_template_cfd_timewalk_shape | 3 | low | 1.015 | high | 1.051 | 0.03521 |
| pid_sideband | shape_time_gate_transformer_new | 3 | low_duplicate | 4.235 | high_duplicate | 8.454 | 4.219 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 5.11 | high_duplicate | 8.397 | 3.287 |
| pid_sideband | compact_waveform_transformer | 3 | low_duplicate | 4.719 | high_duplicate | 5.875 | 1.157 |
| pid_sideband | ridge | 3 | low_duplicate | 3.414 | high_duplicate | 4.491 | 1.076 |
| pid_sideband | mlp | 3 | low_duplicate | 3.725 | high_duplicate | 4.253 | 0.5279 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.313 | high_duplicate | 3.475 | 0.1619 |
| pid_sideband | traditional_median_template_cfd_timewalk_shape | 3 | central | 1.03 | high_duplicate | 1.094 | 0.06461 |
| pileup_separation_bin | shape_time_gate_transformer_new | 4 | none | 4.491 | late | 18.54 | 14.05 |
| pileup_separation_bin | 1d_cnn | 4 | none | 5.36 | late | 8.629 | 3.269 |
| pileup_separation_bin | mlp | 4 | close | 3.45 | late | 6.599 | 3.149 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 1.095 | none | 3.686 | 2.591 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 2.971 | close | 5.234 | 2.263 |
| pileup_separation_bin | ridge | 4 | close | 3.626 | late | 4.414 | 0.7876 |
| pileup_separation_bin | traditional_median_template_cfd_timewalk_shape | 4 | late | 0.4459 | mid | 1.078 | 0.6322 |
| pulse_shape_class | shape_time_gate_transformer_new | 3 | late_tail | 4.099 | compact | 6.2 | 2.101 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 4.613 | compact | 6.12 | 1.507 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 5.111 | compact | 6.568 | 1.457 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.833 | late_tail | 4.051 | 1.218 |
| pulse_shape_class | ridge | 3 | nominal | 3.487 | compact | 4.368 | 0.8809 |
| pulse_shape_class | mlp | 3 | nominal | 3.482 | late_tail | 4.314 | 0.8328 |
| pulse_shape_class | traditional_median_template_cfd_timewalk_shape | 3 | late_tail | 0.9606 | compact | 1.108 | 0.1474 |
| q_template_error_bin | shape_time_gate_transformer_new | 3 | template_like | 3.795 | shape_outlier | 6.621 | 2.826 |
| q_template_error_bin | 1d_cnn | 3 | template_like | 4.51 | shape_outlier | 7.306 | 2.796 |
| q_template_error_bin | compact_waveform_transformer | 3 | template_like | 3.647 | moderate_shape | 6.11 | 2.463 |
| q_template_error_bin | ridge | 3 | template_like | 3.071 | shape_outlier | 4.593 | 1.521 |
| q_template_error_bin | gradient_boosted_trees | 3 | template_like | 2.848 | shape_outlier | 4.076 | 1.228 |
| q_template_error_bin | mlp | 3 | template_like | 3.426 | shape_outlier | 4.618 | 1.191 |
| q_template_error_bin | traditional_median_template_cfd_timewalk_shape | 3 | moderate_shape | 1.009 | template_like | 1.044 | 0.03515 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 4.81 | linear | 5.624 | 0.8146 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.178 | linear | 5.971 | 0.793 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.792 | linear | 4.204 | 0.4129 |
| saturation_onset_bin | shape_time_gate_transformer_new | 2 | near_saturation | 4.619 | linear | 5.025 | 0.4065 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.216 | linear | 3.421 | 0.2051 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.745 | linear | 3.907 | 0.1626 |
| saturation_onset_bin | traditional_median_template_cfd_timewalk_shape | 2 | near_saturation | 0.9799 | linear | 1.048 | 0.06773 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_derivative_gradient_boosted_trees | 77 | -0.2875 | 3.355 | 2.655 | 3.975 | 0 | 0.1583 |
| drop_derivative_features | 34 | -0.2776 | 3.381 | 2.617 | 3.978 | 0.026 | 0.1565 |
| amplitude_cfd_no_derivative | 5 | 0.0523 | 3.986 | 3.57 | 4.706 | 0.6305 | 0.2257 |
| derivative_only | 43 | -0.09015 | 3.996 | 3.455 | 4.585 | 0.641 | 0.2192 |
| late_tail_curvature_window_only | 17 | 0.1855 | 4.469 | 4.048 | 5.165 | 1.114 | 0.27 |
| onset_derivative_window_only | 14 | -0.2367 | 4.664 | 4.02 | 5.942 | 1.309 | 0.2962 |
| pretrigger_derivative_only | 7 | -3.337 | 18.05 | 17.26 | 20.17 | 14.7 | 0.5696 |

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

Runtime was `87.7 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29` with Python
`3.8.10`.

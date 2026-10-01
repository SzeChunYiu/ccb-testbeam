# S61b/#2523 Trigger-Phase Aliasing and Waveform ML Benchmark

## Abstract

Ticket `#2523` asks whether ADC sampling phase and trigger-alignment aliases create apparent pulse-shape classes, pedestal excursions, pile-up labels, saturation tails, energy shifts, or PID-boundary movement, and whether learned waveform methods beat a strong phase-binned CFD/template residual baseline.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 0.8978 ns`
`[0.6395, 1.1]`.  The
traditional derivative comparator obtains `0.8978 ns`
`[0.6395, 1.1]`.

## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-3 --project testbeam` command was
run exactly once.  It returned the malformed helper payload:

```text
null
# null

null
```

Because the testbeam queue still had open issues and the objective forbids a
second claim invocation, issue `#2523` was manually label-swapped to
`factory:claimed worker:testbeam-laptop-3` with:

```text
gh issue edit 2523 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open
```

No other ticket was claimed by this worker, and no novel follow-up ticket was
appended.

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

The traditional comparator starts from the audited CFD/template time-walk baseline `hat y_0`, adds phase-binned harmonic terms `sin(2 pi phi)`, `cos(2 pi phi)`, `sin(4 pi phi)`, and `cos(4 pi phi)` through the derivative/template feature set, and fits a ridge-regularized residual correction on training runs only:

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
| heldout | 5466 |
| train | 15137 |

Confidence intervals use `500` paired percentile
bootstrap replicates that resample held-out runs with replacement.  Paired
deltas subtract each replicate of the traditional derivative comparator from
the corresponding replicate of the learned method.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_template_derivative | traditional | phase-harmonic CFD20/50 template time-walk baseline plus ridge-regularized derivative and curvature residual correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, waveform, derivative, and curvature features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled derivative feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform, detector-state, derivative, and curvature summaries |
| 1d_cnn | neural waveform | compact 1D convolutional regressor over normalized 18-sample waveforms |
| compact_waveform_transformer | neural waveform | one-layer waveform self-attention encoder inherited from the audited timing benchmark |
| derivative_gate_transformer_new | new architecture | compact transformer over waveform, first derivative, and second derivative channels with derivative-magnitude pooling |

The new architecture is sensible for this ticket because the hypothesis is not generic waveform learning; it is that edge, curvature, and sample-position channels localize phase aliases and trigger-edge shifts.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.3876 | 0.03563 | 0.6472 | 0.8978 | 0.6395 | 1.1 | 0.9006 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.5928 | -1.825 | 0.6795 | 3.781 | 3.349 | 4.076 | 4.548 | 0.1859 | 0.03933 |
| ridge | 5466 | -0.5221 | -1.559 | 0.5663 | 4.127 | 3.62 | 4.942 | 5.101 | 0.2473 | 0.04848 |
| mlp | 5466 | -0.9428 | -1.946 | 0.6416 | 4.342 | 3.95 | 4.772 | 4.95 | 0.2525 | 0.04757 |
| derivative_gate_transformer_new | 5466 | -2.534 | -3.611 | -1.572 | 4.833 | 4.071 | 5.816 | 5.927 | 0.3825 | 0.08617 |
| 1d_cnn | 5466 | -1.944 | -2.918 | -1.002 | 5.757 | 4.989 | 6.794 | 7.574 | 0.4126 | 0.1482 |
| compact_waveform_transformer | 5466 | 0.2244 | -0.5384 | 1.143 | 5.877 | 5.563 | 6.569 | 6.53 | 0.397 | 0.1116 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.883 | 2.375 | 3.274 | -0.9803 | -2.172 | 0.3449 | 0.1859 |
| ridge | traditional_cfd_template_derivative | 3.229 | 2.682 | 4.125 | -0.9097 | -1.984 | 0.1979 | 0.2473 |
| mlp | traditional_cfd_template_derivative | 3.444 | 3.015 | 3.898 | -1.33 | -2.382 | 0.2686 | 0.2525 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 3.935 | 3.179 | 4.965 | -2.922 | -3.969 | -1.876 | 0.3825 |
| 1d_cnn | traditional_cfd_template_derivative | 4.86 | 4.037 | 5.96 | -2.331 | -3.334 | -1.346 | 0.4126 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 4.979 | 4.585 | 5.789 | -0.1632 | -0.99 | 0.8477 | 0.397 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.07668 | 0.9506 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.194 | 4.163 | 0.24 |
| sample_i_analysis | mlp | 1350 | -0.2179 | 5.505 | 0.3044 |
| sample_i_analysis | ridge | 1350 | -0.2638 | 6.202 | 0.3578 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | -2.4 | 7.123 | 0.4356 |
| sample_i_analysis | compact_waveform_transformer | 1350 | -0.00388 | 7.484 | 0.417 |
| sample_i_analysis | 1d_cnn | 1350 | -2.218 | 7.882 | 0.4726 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | 0.05947 | 0.5296 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 2.518 | 2.478 | 0.175 |
| sample_i_calib | mlp | 657 | 2.694 | 3.891 | 0.3166 |
| sample_i_calib | ridge | 657 | 2.226 | 4.693 | 0.3151 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 0.2176 | 5.57 | 0.376 |
| sample_i_calib | compact_waveform_transformer | 657 | 2.436 | 5.939 | 0.4338 |
| sample_i_calib | 1d_cnn | 657 | 1.036 | 6.755 | 0.4384 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.5754 | 0.9603 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.518 | 3.453 | 0.1621 |
| sample_ii_analysis | ridge | 2739 | -0.9453 | 3.685 | 0.1931 |
| sample_ii_analysis | mlp | 2739 | -1.526 | 3.941 | 0.2194 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | -2.919 | 4.219 | 0.3578 |
| sample_ii_analysis | 1d_cnn | 2739 | -2.254 | 5.346 | 0.3844 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | -0.2146 | 5.829 | 0.3907 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.654 | 0.3295 | 0 |
| sample_ii_calib | ridge | 720 | -1.663 | 3.639 | 0.1847 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | -3.071 | 3.739 | 0.3833 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.52 | 3.817 | 0.1847 |
| sample_ii_calib | 1d_cnn | 720 | -2.714 | 4.426 | 0.3833 |
| sample_ii_calib | mlp | 720 | -2.157 | 4.426 | 0.2222 |
| sample_ii_calib | compact_waveform_transformer | 720 | -0.04701 | 5.363 | 0.35 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.036 | 6.755 | 0.4384 |
| 1d_cnn | 50 | 680 | -3.312 | 9.574 | 0.4647 |
| 1d_cnn | 57 | 670 | -0.792 | 7.026 | 0.4806 |
| 1d_cnn | 58 | 654 | -4.859 | 5.773 | 0.5214 |
| 1d_cnn | 60 | 720 | -1.196 | 5.453 | 0.3222 |
| 1d_cnn | 62 | 720 | -2.113 | 4.435 | 0.3208 |
| 1d_cnn | 64 | 720 | -2.714 | 4.426 | 0.3833 |
| 1d_cnn | 65 | 645 | -1.865 | 5.125 | 0.386 |
| compact_waveform_transformer | 42 | 657 | 2.436 | 5.939 | 0.4338 |
| compact_waveform_transformer | 50 | 680 | -0.1787 | 8.506 | 0.4176 |
| compact_waveform_transformer | 57 | 670 | 0.2205 | 6.36 | 0.4164 |
| compact_waveform_transformer | 58 | 654 | -2.047 | 5.574 | 0.4037 |
| compact_waveform_transformer | 60 | 720 | 0.596 | 5.836 | 0.4056 |
| compact_waveform_transformer | 62 | 720 | -0.08852 | 5.412 | 0.3569 |
| compact_waveform_transformer | 64 | 720 | -0.04701 | 5.363 | 0.35 |
| compact_waveform_transformer | 65 | 645 | 0.5491 | 5.613 | 0.3984 |
| derivative_gate_transformer_new | 42 | 657 | 0.2176 | 5.57 | 0.376 |
| derivative_gate_transformer_new | 50 | 680 | -3.719 | 9.948 | 0.4794 |
| derivative_gate_transformer_new | 57 | 670 | -1.765 | 5.679 | 0.391 |
| derivative_gate_transformer_new | 58 | 654 | -5.372 | 4.275 | 0.5321 |
| derivative_gate_transformer_new | 60 | 720 | -1.539 | 3.994 | 0.2681 |
| derivative_gate_transformer_new | 62 | 720 | -2.914 | 3.837 | 0.3181 |
| derivative_gate_transformer_new | 64 | 720 | -3.071 | 3.739 | 0.3833 |
| derivative_gate_transformer_new | 65 | 645 | -2.674 | 3.925 | 0.3256 |
| gradient_boosted_trees | 42 | 657 | 2.518 | 2.478 | 0.175 |
| gradient_boosted_trees | 50 | 680 | 0.3345 | 8.256 | 0.2838 |
| gradient_boosted_trees | 57 | 670 | -0.2188 | 4.02 | 0.1955 |
| gradient_boosted_trees | 58 | 654 | -3.624 | 2.548 | 0.3012 |
| gradient_boosted_trees | 60 | 720 | 0.1292 | 3.856 | 0.1542 |
| gradient_boosted_trees | 62 | 720 | -1.178 | 2.932 | 0.07639 |
| gradient_boosted_trees | 64 | 720 | -1.52 | 3.817 | 0.1847 |
| gradient_boosted_trees | 65 | 645 | -1.681 | 3.657 | 0.1256 |
| mlp | 42 | 657 | 2.694 | 3.891 | 0.3166 |
| mlp | 50 | 680 | -0.6243 | 8.103 | 0.3029 |
| mlp | 57 | 670 | 0.4616 | 4.668 | 0.306 |
| mlp | 58 | 654 | -3.309 | 3.314 | 0.3196 |
| mlp | 60 | 720 | -0.3959 | 4.08 | 0.2125 |
| mlp | 62 | 720 | -1.292 | 3.496 | 0.1153 |
| mlp | 64 | 720 | -2.157 | 4.426 | 0.2222 |
| mlp | 65 | 645 | -1.411 | 4.389 | 0.2419 |
| ridge | 42 | 657 | 2.226 | 4.693 | 0.3151 |
| ridge | 50 | 680 | -1.105 | 8.975 | 0.3544 |
| ridge | 57 | 670 | 0.5613 | 5.178 | 0.3612 |
| ridge | 58 | 654 | -3.006 | 3.478 | 0.3242 |
| ridge | 60 | 720 | 0.1799 | 3.313 | 0.1458 |
| ridge | 62 | 720 | -0.9781 | 3.112 | 0.1194 |
| ridge | 64 | 720 | -1.663 | 3.639 | 0.1847 |
| ridge | 65 | 645 | -0.4173 | 3.847 | 0.1953 |
| traditional_cfd_template_derivative | 42 | 657 | 0.05947 | 0.5296 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | -0.08088 | 0.727 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | -0.05771 | 1.06 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.9391 | 0.5219 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.4967 | 1.137 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.4821 | 0.908 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.654 | 0.3295 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.5524 | 0.6367 | 0 |

## Stratified Systematics

The requested strata are sampling phase, trigger alignment, amplitude, pedestal state, late-tail morphology, pile-up proxy, saturation onset, and PID sideband. Additional pulse-shape stress axes are included because derivative/curvature features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1582 | -2.094 | 7.491 | 0.4924 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1582 | -2.235 | 6.157 | 0.4324 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1582 | -2.968 | 5.988 | 0.4343 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1582 | -0.1943 | 3.982 | 0.2162 |
| curvature_energy_bin | curved | mlp | 1582 | -0.7788 | 4.64 | 0.2838 |
| curvature_energy_bin | curved | ridge | 1582 | -0.4078 | 4.452 | 0.2813 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1582 | 0.4563 | 0.9541 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1986 | -1.488 | 5.122 | 0.3444 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1986 | 1.393 | 5.965 | 0.4235 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1986 | -2.229 | 4.527 | 0.3394 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1986 | -0.492 | 3.797 | 0.1908 |
| curvature_energy_bin | moderate | mlp | 1986 | -0.8292 | 4.341 | 0.2437 |
| curvature_energy_bin | moderate | ridge | 1986 | -0.9656 | 4.134 | 0.2482 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1986 | 0.4351 | 0.8513 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1898 | -2.328 | 4.978 | 0.4173 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1898 | 0.5816 | 4.849 | 0.3398 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1898 | -2.434 | 4.176 | 0.3846 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1898 | -0.8671 | 3.626 | 0.1554 |
| curvature_energy_bin | smooth | mlp | 1898 | -1.207 | 4.155 | 0.2355 |
| curvature_energy_bin | smooth | ridge | 1898 | -0.07076 | 3.854 | 0.2181 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1898 | 0.3097 | 0.9532 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1826 | -2.514 | 5.044 | 0.3801 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1826 | -0.03326 | 5.502 | 0.3565 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1826 | -2.842 | 4.378 | 0.3801 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1826 | -0.6602 | 3.584 | 0.1572 |
| derivative_onset_bin | nominal | mlp | 1826 | -1.252 | 4.098 | 0.2262 |
| derivative_onset_bin | nominal | ridge | 1826 | -0.6358 | 3.885 | 0.2114 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1826 | 0.4536 | 0.8171 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1951 | -2.116 | 5.296 | 0.3906 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1951 | 0.2332 | 5.637 | 0.3783 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1951 | -3.017 | 4.535 | 0.3947 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1951 | -0.9994 | 3.469 | 0.1497 |
| derivative_onset_bin | sharp | mlp | 1951 | -1.528 | 4.171 | 0.2281 |
| derivative_onset_bin | sharp | ridge | 1951 | -0.955 | 4.121 | 0.2394 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1951 | 0.5118 | 0.8818 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1689 | -0.978 | 7.733 | 0.4731 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1689 | 0.7518 | 6.833 | 0.4624 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1689 | -1.644 | 5.465 | 0.3712 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1689 | 0.1132 | 4.412 | 0.2587 |
| derivative_onset_bin | slow | mlp | 1689 | 0.1316 | 4.676 | 0.3091 |
| derivative_onset_bin | slow | ridge | 1689 | -0.08421 | 4.565 | 0.2954 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1689 | 0.103 | 0.9246 | 0 |
| energy_bin | q1_low | 1d_cnn | 1418 | -2.853 | 6.414 | 0.5092 |
| energy_bin | q1_low | compact_waveform_transformer | 1418 | -0.2875 | 5.566 | 0.3815 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1418 | -2.414 | 5.07 | 0.4196 |
| energy_bin | q1_low | gradient_boosted_trees | 1418 | -0.894 | 3.819 | 0.1819 |
| energy_bin | q1_low | mlp | 1418 | -0.7835 | 4.221 | 0.2433 |
| energy_bin | q1_low | ridge | 1418 | -0.1746 | 4.008 | 0.2292 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1418 | 0.06406 | 1.044 | 0 |
| energy_bin | q2 | 1d_cnn | 1517 | -2.133 | 4.651 | 0.3784 |
| energy_bin | q2 | compact_waveform_transformer | 1517 | 1.319 | 5.137 | 0.3652 |
| energy_bin | q2 | derivative_gate_transformer_new | 1517 | -2.199 | 4.131 | 0.3388 |
| energy_bin | q2 | gradient_boosted_trees | 1517 | -0.5838 | 3.607 | 0.1661 |
| energy_bin | q2 | mlp | 1517 | -1.289 | 4.346 | 0.2439 |
| energy_bin | q2 | ridge | 1517 | -0.4903 | 3.977 | 0.2347 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1517 | 0.4062 | 0.7589 | 0 |
| energy_bin | q3 | 1d_cnn | 1426 | -0.3367 | 4.599 | 0.2819 |
| energy_bin | q3 | compact_waveform_transformer | 1426 | 1.202 | 6.24 | 0.4411 |
| energy_bin | q3 | derivative_gate_transformer_new | 1426 | -2.643 | 4.981 | 0.392 |
| energy_bin | q3 | gradient_boosted_trees | 1426 | -0.6159 | 3.728 | 0.1823 |
| energy_bin | q3 | mlp | 1426 | -0.9748 | 4.34 | 0.2496 |
| energy_bin | q3 | ridge | 1426 | -0.9442 | 4.266 | 0.2735 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1426 | 0.4922 | 0.8207 | 0 |
| energy_bin | q4_high | 1d_cnn | 1105 | -3.281 | 7.043 | 0.5041 |
| energy_bin | q4_high | compact_waveform_transformer | 1105 | -2.324 | 5.687 | 0.4036 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1105 | -2.916 | 5.784 | 0.3828 |
| energy_bin | q4_high | gradient_boosted_trees | 1105 | 0.03991 | 3.92 | 0.2226 |
| energy_bin | q4_high | mlp | 1105 | -0.2837 | 4.475 | 0.2796 |
| energy_bin | q4_high | ridge | 1105 | -0.4252 | 4.316 | 0.2543 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1105 | 0.5938 | 0.9253 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3257 | -2.035 | 5.361 | 0.4126 |
| late_tail_morphology | compact | compact_waveform_transformer | 3257 | -0.1859 | 5.987 | 0.4034 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3257 | -2.859 | 4.687 | 0.4262 |
| late_tail_morphology | compact | gradient_boosted_trees | 3257 | -1.038 | 3.664 | 0.167 |
| late_tail_morphology | compact | mlp | 3257 | -1.505 | 4.2 | 0.2244 |
| late_tail_morphology | compact | ridge | 3257 | -0.8475 | 4.196 | 0.2395 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3257 | 0.3952 | 0.8978 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 610 | -3.195 | 4.909 | 0.4 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 610 | -1.133 | 4.432 | 0.282 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 610 | -2.925 | 3.667 | 0.3066 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 610 | -0.04057 | 3.193 | 0.1361 |
| late_tail_morphology | diffuse_tail | mlp | 610 | -0.462 | 4.086 | 0.2197 |
| late_tail_morphology | diffuse_tail | ridge | 610 | -0.6945 | 3.363 | 0.1738 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 610 | 0.6479 | 0.9377 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 391 | -3.64 | 8.549 | 0.4629 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 391 | -0.007975 | 6.905 | 0.4348 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 391 | -1.646 | 5.292 | 0.3146 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 391 | -0.1066 | 3.622 | 0.2174 |
| late_tail_morphology | late_derivative_bump | mlp | 391 | -1.146 | 4.446 | 0.3146 |
| late_tail_morphology | late_derivative_bump | ridge | 391 | 0.04805 | 4.135 | 0.2609 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 391 | 0.471 | 0.8101 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1208 | 0.039 | 6.164 | 0.4023 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1208 | 2.214 | 5.806 | 0.4255 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1208 | -1.827 | 5.118 | 0.3253 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1208 | 0.3044 | 4.487 | 0.2517 |
| late_tail_morphology | late_rising_tail | mlp | 1208 | 0.5036 | 4.813 | 0.3245 |
| late_tail_morphology | late_rising_tail | ridge | 1208 | -0.05026 | 4.505 | 0.3013 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1208 | 0.1129 | 0.8804 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1758 | -1.91 | 6.938 | 0.4778 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1758 | -1.309 | 6.81 | 0.4881 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1758 | -2.412 | 5.364 | 0.4204 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1758 | -0.3723 | 4.111 | 0.2156 |
| pedestal_drift_bin | high | mlp | 1758 | -0.3367 | 4.444 | 0.2639 |
| pedestal_drift_bin | high | ridge | 1758 | -0.3421 | 4.244 | 0.2463 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1758 | 0.3301 | 0.919 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1768 | -1.933 | 5.541 | 0.3846 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1768 | 0.5996 | 5.374 | 0.3676 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1768 | -2.737 | 4.893 | 0.384 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1768 | -0.8795 | 3.515 | 0.185 |
| pedestal_drift_bin | low | mlp | 1768 | -1.44 | 4.055 | 0.2489 |
| pedestal_drift_bin | low | ridge | 1768 | -0.8697 | 4.213 | 0.263 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1768 | 0.448 | 0.9265 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1940 | -1.969 | 5.079 | 0.3789 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1940 | 0.9004 | 5.033 | 0.3412 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1940 | -2.488 | 4.36 | 0.3469 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1940 | -0.3887 | 3.606 | 0.1598 |
| pedestal_drift_bin | mid | mlp | 1940 | -0.8543 | 4.345 | 0.2454 |
| pedestal_drift_bin | mid | ridge | 1940 | -0.4361 | 3.945 | 0.234 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1940 | 0.3827 | 0.8546 | 0 |
| pid_sideband | central | 1d_cnn | 3733 | -1.711 | 5.232 | 0.3782 |
| pid_sideband | central | compact_waveform_transformer | 3733 | 1.043 | 5.183 | 0.3608 |
| pid_sideband | central | derivative_gate_transformer_new | 3733 | -2.453 | 4.674 | 0.3691 |
| pid_sideband | central | gradient_boosted_trees | 3733 | -0.5962 | 3.607 | 0.1722 |
| pid_sideband | central | mlp | 3733 | -0.9752 | 4.232 | 0.2497 |
| pid_sideband | central | ridge | 3733 | -0.4723 | 4.165 | 0.2553 |
| pid_sideband | central | traditional_cfd_template_derivative | 3733 | 0.3792 | 0.8937 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 867 | -3.214 | 8.826 | 0.5882 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 867 | -5.352 | 6.04 | 0.5802 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 867 | -3.055 | 6.024 | 0.5006 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 867 | -0.8851 | 4.287 | 0.2399 |
| pid_sideband | high_duplicate | mlp | 867 | -0.7702 | 4.642 | 0.2757 |
| pid_sideband | high_duplicate | ridge | 867 | -0.7929 | 4.445 | 0.2537 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 867 | 0.2857 | 0.992 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 866 | -2.309 | 5.742 | 0.3845 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 866 | 0.6609 | 5.318 | 0.3695 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 866 | -2.469 | 4.237 | 0.3222 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 866 | -0.3067 | 4.005 | 0.1905 |
| pid_sideband | low_duplicate | mlp | 866 | -0.9253 | 4.311 | 0.2413 |
| pid_sideband | low_duplicate | ridge | 866 | -0.392 | 3.757 | 0.2067 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 866 | 0.5223 | 0.851 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1709 | -3.099 | 5.815 | 0.4342 |
| pileup_separation_bin | close | compact_waveform_transformer | 1709 | 0.0002159 | 5.573 | 0.3686 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1709 | -2.933 | 4.934 | 0.3757 |
| pileup_separation_bin | close | gradient_boosted_trees | 1709 | -0.7849 | 3.752 | 0.1714 |
| pileup_separation_bin | close | mlp | 1709 | -1.137 | 4.395 | 0.2592 |
| pileup_separation_bin | close | ridge | 1709 | -0.8374 | 4.109 | 0.258 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1709 | 0.5407 | 0.8255 | 0 |
| pileup_separation_bin | late | 1d_cnn | 4 | -7.95 | 5.118 | 0.5 |
| pileup_separation_bin | late | compact_waveform_transformer | 4 | -4.691 | 6.559 | 0.5 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 4 | -2.977 | 5.046 | 0.5 |
| pileup_separation_bin | late | gradient_boosted_trees | 4 | 3.793 | 1.536 | 0.25 |
| pileup_separation_bin | late | mlp | 4 | 2.286 | 3.903 | 0.25 |
| pileup_separation_bin | late | ridge | 4 | 1.73 | 2.902 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 4 | -0.2641 | 0.666 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1169 | -1.017 | 5.933 | 0.4012 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1169 | -2.864 | 6.093 | 0.4842 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1169 | -3.279 | 5.236 | 0.4577 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1169 | -1.046 | 3.813 | 0.2002 |
| pileup_separation_bin | mid | mlp | 1169 | -1.497 | 4.345 | 0.2447 |
| pileup_separation_bin | mid | ridge | 1169 | -1.014 | 4.472 | 0.2772 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1169 | 0.4782 | 0.8727 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2584 | -1.533 | 5.593 | 0.4033 |
| pileup_separation_bin | none | compact_waveform_transformer | 2584 | 1.71 | 4.868 | 0.3762 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2584 | -1.962 | 4.518 | 0.3529 |
| pileup_separation_bin | none | gradient_boosted_trees | 2584 | -0.2931 | 3.796 | 0.1889 |
| pileup_separation_bin | none | mlp | 2584 | -0.5635 | 4.252 | 0.2515 |
| pileup_separation_bin | none | ridge | 2584 | -0.1829 | 3.777 | 0.2272 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2584 | 0.2416 | 0.9275 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1858 | -2.161 | 6.525 | 0.4914 |
| pulse_shape_class | compact | compact_waveform_transformer | 1858 | -1.429 | 6.511 | 0.4752 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1858 | -2.503 | 5.135 | 0.472 |
| pulse_shape_class | compact | gradient_boosted_trees | 1858 | -1.29 | 3.864 | 0.1932 |
| pulse_shape_class | compact | mlp | 1858 | -1.239 | 4.443 | 0.2578 |
| pulse_shape_class | compact | ridge | 1858 | -0.4229 | 4.423 | 0.2836 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1858 | 0.353 | 0.9996 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1846 | -1.521 | 6.116 | 0.403 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1846 | 0.9587 | 5.415 | 0.3765 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1846 | -2.335 | 4.601 | 0.3212 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1846 | 0.1122 | 4.126 | 0.2151 |
| pulse_shape_class | late_tail | mlp | 1846 | 0.06183 | 4.588 | 0.2887 |
| pulse_shape_class | late_tail | ridge | 1846 | -0.309 | 4.122 | 0.2568 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1846 | 0.3312 | 0.8952 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1762 | -2.394 | 4.602 | 0.3394 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1762 | 0.7585 | 5.086 | 0.336 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1762 | -2.797 | 4.442 | 0.3524 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1762 | -0.7212 | 3.403 | 0.1476 |
| pulse_shape_class | nominal | mlp | 1762 | -1.639 | 3.815 | 0.2089 |
| pulse_shape_class | nominal | ridge | 1762 | -0.9656 | 3.879 | 0.1992 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1762 | 0.4838 | 0.7939 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3929 | -1.771 | 6.064 | 0.4281 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3929 | -0.1597 | 6.063 | 0.4047 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3929 | -2.874 | 4.877 | 0.4095 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3929 | -0.7345 | 3.845 | 0.1919 |
| saturation_onset_bin | linear | mlp | 3929 | -1.036 | 4.41 | 0.2571 |
| saturation_onset_bin | linear | ridge | 3929 | -0.7696 | 4.206 | 0.2588 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3929 | 0.4011 | 0.9332 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1537 | -2.36 | 5.262 | 0.3728 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1537 | 0.9544 | 5.351 | 0.3774 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1537 | -1.642 | 4.763 | 0.3136 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1537 | -0.1728 | 3.662 | 0.1705 |
| saturation_onset_bin | near_saturation | mlp | 1537 | -0.6481 | 4.121 | 0.2407 |
| saturation_onset_bin | near_saturation | ridge | 1537 | 0.01113 | 3.986 | 0.218 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1537 | 0.3474 | 0.7859 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.978 | curved | 7.491 | 2.512 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 4.176 | curved | 5.988 | 1.812 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.849 | curved | 6.157 | 1.308 |
| curvature_energy_bin | ridge | 3 | smooth | 3.854 | curved | 4.452 | 0.5978 |
| curvature_energy_bin | mlp | 3 | smooth | 4.155 | curved | 4.64 | 0.4851 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.626 | curved | 3.982 | 0.3562 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | moderate | 0.8513 | curved | 0.9541 | 0.1028 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 5.044 | slow | 7.733 | 2.689 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 5.502 | slow | 6.833 | 1.331 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | nominal | 4.378 | slow | 5.465 | 1.087 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.469 | slow | 4.412 | 0.9427 |
| derivative_onset_bin | ridge | 3 | nominal | 3.885 | slow | 4.565 | 0.6799 |
| derivative_onset_bin | mlp | 3 | nominal | 4.098 | slow | 4.676 | 0.578 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | nominal | 0.8171 | slow | 0.9246 | 0.1075 |
| energy_bin | 1d_cnn | 4 | q3 | 4.599 | q4_high | 7.043 | 2.445 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 4.131 | q4_high | 5.784 | 1.653 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 5.137 | q3 | 6.24 | 1.102 |
| energy_bin | ridge | 4 | q2 | 3.977 | q4_high | 4.316 | 0.3385 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.607 | q4_high | 3.92 | 0.3123 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.7589 | q1_low | 1.044 | 0.2853 |
| energy_bin | mlp | 4 | q1_low | 4.221 | q4_high | 4.475 | 0.2543 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.909 | late_derivative_bump | 8.549 | 3.641 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.432 | late_derivative_bump | 6.905 | 2.473 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 3.667 | late_derivative_bump | 5.292 | 1.625 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 3.193 | late_rising_tail | 4.487 | 1.293 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.363 | late_rising_tail | 4.505 | 1.143 |
| late_tail_morphology | mlp | 4 | diffuse_tail | 4.086 | late_rising_tail | 4.813 | 0.7261 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_derivative_bump | 0.8101 | diffuse_tail | 0.9377 | 0.1275 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.079 | high | 6.938 | 1.859 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.033 | high | 6.81 | 1.777 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.36 | high | 5.364 | 1.004 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.515 | high | 4.111 | 0.5959 |
| pedestal_drift_bin | mlp | 3 | low | 4.055 | high | 4.444 | 0.3891 |
| pedestal_drift_bin | ridge | 3 | mid | 3.945 | high | 4.244 | 0.2991 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | mid | 0.8546 | low | 0.9265 | 0.07186 |
| pid_sideband | 1d_cnn | 3 | central | 5.232 | high_duplicate | 8.826 | 3.595 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.237 | high_duplicate | 6.024 | 1.787 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.183 | high_duplicate | 6.04 | 0.8566 |
| pid_sideband | ridge | 3 | low_duplicate | 3.757 | high_duplicate | 4.445 | 0.6875 |
| pid_sideband | gradient_boosted_trees | 3 | central | 3.607 | high_duplicate | 4.287 | 0.6797 |
| pid_sideband | mlp | 3 | central | 4.232 | high_duplicate | 4.642 | 0.4096 |
| pid_sideband | traditional_cfd_template_derivative | 3 | low_duplicate | 0.851 | high_duplicate | 0.992 | 0.1409 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 1.536 | mid | 3.813 | 2.277 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 4.868 | late | 6.559 | 1.692 |
| pileup_separation_bin | ridge | 4 | late | 2.902 | mid | 4.472 | 1.57 |
| pileup_separation_bin | 1d_cnn | 4 | late | 5.118 | mid | 5.933 | 0.815 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | none | 4.518 | mid | 5.236 | 0.7178 |
| pileup_separation_bin | mlp | 4 | late | 3.903 | close | 4.395 | 0.492 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | late | 0.666 | none | 0.9275 | 0.2615 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.602 | compact | 6.525 | 1.923 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.086 | compact | 6.511 | 1.426 |
| pulse_shape_class | mlp | 3 | nominal | 3.815 | late_tail | 4.588 | 0.7731 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.403 | late_tail | 4.126 | 0.7229 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.442 | compact | 5.135 | 0.6935 |
| pulse_shape_class | ridge | 3 | nominal | 3.879 | compact | 4.423 | 0.5434 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.7939 | compact | 0.9996 | 0.2057 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.262 | linear | 6.064 | 0.8016 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.351 | linear | 6.063 | 0.7111 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.121 | linear | 4.41 | 0.2888 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.986 | linear | 4.206 | 0.2202 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.662 | linear | 3.845 | 0.1831 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.7859 | linear | 0.9332 | 0.1473 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 4.763 | linear | 4.877 | 0.1134 |

## Phase-Alias Stress Tests

The stress table isolates whether residual width changes under phase-harmonic sign, trigger-peak parity, high-tail pile-up proxy, high-pedestal excursions, and high-energy proxy selections. It is computed from held-out predictions only, after the train-run-only phase-harmonic traditional correction.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_heldout | 0 | -1.944 | 5.757 | 5.757 | 5.757 | 0 | 0.4126 |
| high_energy_proxy | 0 | -2.08 | 6.503 | 6.503 | 6.503 | 0.7454 | 0.4299 |
| high_pedestal_abs | 0 | -0.9872 | 8.047 | 8.047 | 8.047 | 2.29 | 0.4564 |
| high_tail_pileup_proxy | 0 | -1.46 | 6.131 | 6.131 | 6.131 | 0.3736 | 0.4019 |
| phase_harmonic_negative | 0 | -1.93 | 5.856 | 5.856 | 5.856 | 0.09877 | 0.4209 |
| phase_harmonic_positive | 0 | -1.944 | 5.664 | 5.664 | 5.664 | -0.09309 | 0.4071 |
| trigger_even_peak | 0 | -2.098 | 5.351 | 5.351 | 5.351 | -0.4064 | 0.3849 |
| trigger_odd_peak | 0 | -1.758 | 6.388 | 6.388 | 6.388 | 0.6304 | 0.4404 |
| all_heldout | 0 | 0.2244 | 5.877 | 5.877 | 5.877 | 0 | 0.397 |
| high_energy_proxy | 0 | -1.618 | 6.117 | 6.117 | 6.117 | 0.2399 | 0.4072 |
| high_pedestal_abs | 0 | -0.7704 | 7.788 | 7.788 | 7.788 | 1.911 | 0.521 |
| high_tail_pileup_proxy | 0 | 1.023 | 5.388 | 5.388 | 5.388 | -0.489 | 0.378 |
| phase_harmonic_negative | 0 | 0.2611 | 5.697 | 5.697 | 5.697 | -0.1802 | 0.3784 |
| phase_harmonic_positive | 0 | 0.1997 | 6.053 | 6.053 | 6.053 | 0.1762 | 0.4092 |
| trigger_even_peak | 0 | 0.447 | 5.8 | 5.8 | 5.8 | -0.07699 | 0.39 |
| trigger_odd_peak | 0 | -0.01665 | 6.014 | 6.014 | 6.014 | 0.1368 | 0.404 |
| all_heldout | 0 | -2.534 | 4.833 | 4.833 | 4.833 | 0 | 0.3825 |
| high_energy_proxy | 0 | -3.093 | 5.361 | 5.361 | 5.361 | 0.5282 | 0.4105 |
| high_pedestal_abs | 0 | -1.839 | 5.803 | 5.803 | 5.803 | 0.9704 | 0.3698 |
| high_tail_pileup_proxy | 0 | -2.277 | 4.596 | 4.596 | 4.596 | -0.2369 | 0.3182 |
| phase_harmonic_negative | 0 | -2.381 | 4.847 | 4.847 | 4.847 | 0.01346 | 0.3646 |
| phase_harmonic_positive | 0 | -2.635 | 4.838 | 4.838 | 4.838 | 0.005328 | 0.3944 |
| trigger_even_peak | 0 | -2.421 | 4.687 | 4.687 | 4.687 | -0.1466 | 0.3692 |
| trigger_odd_peak | 0 | -2.613 | 5 | 5 | 5 | 0.1673 | 0.396 |
| all_heldout | 0 | -0.5928 | 3.781 | 3.781 | 3.781 | 0 | 0.1859 |
| high_energy_proxy | 0 | -0.2386 | 3.931 | 3.931 | 3.931 | 0.1508 | 0.2155 |
| high_pedestal_abs | 0 | 1.796 | 4.518 | 4.518 | 4.518 | 0.7371 | 0.2942 |
| high_tail_pileup_proxy | 0 | 0.1435 | 4.107 | 4.107 | 4.107 | 0.3266 | 0.2123 |
| phase_harmonic_negative | 0 | -0.5793 | 3.661 | 3.661 | 3.661 | -0.1195 | 0.1671 |
| phase_harmonic_positive | 0 | -0.5952 | 3.896 | 3.896 | 3.896 | 0.1155 | 0.1982 |
| trigger_even_peak | 0 | -0.657 | 3.669 | 3.669 | 3.669 | -0.1117 | 0.1842 |
| trigger_odd_peak | 0 | -0.5172 | 3.909 | 3.909 | 3.909 | 0.1279 | 0.1875 |
| all_heldout | 0 | -0.9428 | 4.342 | 4.342 | 4.342 | 0 | 0.2525 |
| high_energy_proxy | 0 | -0.8316 | 4.471 | 4.471 | 4.471 | 0.1289 | 0.2765 |
| high_pedestal_abs | 0 | 2.428 | 5.251 | 5.251 | 5.251 | 0.9094 | 0.394 |
| high_tail_pileup_proxy | 0 | 0.1288 | 4.556 | 4.556 | 4.556 | 0.2139 | 0.2894 |
| phase_harmonic_negative | 0 | -1.062 | 4.314 | 4.314 | 4.314 | -0.02816 | 0.2478 |
| phase_harmonic_positive | 0 | -0.8316 | 4.359 | 4.359 | 4.359 | 0.01657 | 0.2555 |
| trigger_even_peak | 0 | -0.842 | 4.16 | 4.16 | 4.16 | -0.1824 | 0.2368 |
| trigger_odd_peak | 0 | -1.001 | 4.507 | 4.507 | 4.507 | 0.1646 | 0.2683 |
| all_heldout | 0 | -0.5221 | 4.127 | 4.127 | 4.127 | 0 | 0.2473 |
| high_energy_proxy | 0 | -0.5938 | 4.355 | 4.355 | 4.355 | 0.2276 | 0.2715 |
| high_pedestal_abs | 0 | 0.8611 | 4.802 | 4.802 | 4.802 | 0.6749 | 0.3035 |
| high_tail_pileup_proxy | 0 | -0.2755 | 4.122 | 4.122 | 4.122 | -0.005049 | 0.2583 |
| phase_harmonic_negative | 0 | -0.4475 | 4.051 | 4.051 | 4.051 | -0.07632 | 0.2446 |
| phase_harmonic_positive | 0 | -0.5783 | 4.221 | 4.221 | 4.221 | 0.09376 | 0.2492 |
| trigger_even_peak | 0 | -0.6475 | 4.148 | 4.148 | 4.148 | 0.02146 | 0.2371 |
| trigger_odd_peak | 0 | -0.4381 | 4.156 | 4.156 | 4.156 | 0.02917 | 0.2576 |
| all_heldout | 0 | 0.3876 | 0.8978 | 0.8978 | 0.8978 | 0 | 0 |
| high_energy_proxy | 0 | 0.5651 | 0.8939 | 0.8939 | 0.8939 | -0.00387 | 0 |
| high_pedestal_abs | 0 | 0.3599 | 0.6866 | 0.6866 | 0.6866 | -0.2112 | 0 |
| high_tail_pileup_proxy | 0 | 0.316 | 0.8921 | 0.8921 | 0.8921 | -0.005698 | 0 |
| phase_harmonic_negative | 0 | 0.3083 | 0.9193 | 0.9193 | 0.9193 | 0.02146 | 0 |
| phase_harmonic_positive | 0 | 0.4254 | 0.8756 | 0.8756 | 0.8756 | -0.02227 | 0 |
| trigger_even_peak | 0 | 0.3887 | 0.8683 | 0.8683 | 0.8683 | -0.02954 | 0 |
| trigger_odd_peak | 0 | 0.3858 | 0.9346 | 0.9346 | 0.9346 | 0.03677 | 0 |

## Phase-Alias Diagnostics

The sampling phase proxy is `phi = frac(t_CFD20)`, split into four equal
phase bins.  Trigger alignment is the parity of the waveform peak sample.  The
ticket-local diagnostics use only held-out runs and report run/phase tables in
`phase_bin_by_run_metrics.csv`.

| method | sampling_phase_bin | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | pileup_false_positive_rate | saturation_tail_rate | pedestal_residual_adc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | phase_q1 | 1826 | -1.77 | -2.78 | -0.7328 | 6.003 | 0.3697 | 1 | 0 |
| 1d_cnn | phase_q2 | 1473 | -2.159 | -2.988 | -0.8795 | 5.417 | 0.3238 | 1 | 0 |
| 1d_cnn | phase_q3 | 1271 | -1.776 | -3.032 | -0.9694 | 5.731 | 0.3273 | 1 | 0 |
| 1d_cnn | phase_q4 | 896 | -2.073 | -3.209 | -1.469 | 5.939 | 0.2746 | 1 | 0 |
| compact_waveform_transformer | phase_q1 | 1826 | 0.03178 | -1.092 | 0.7817 | 6.501 | 0.3697 | 1 | 0 |
| compact_waveform_transformer | phase_q2 | 1473 | 0.4703 | -0.3385 | 1.56 | 5.518 | 0.3238 | 1 | 0 |
| compact_waveform_transformer | phase_q3 | 1271 | 0.6441 | -0.2776 | 1.624 | 5.623 | 0.3273 | 1 | 0 |
| compact_waveform_transformer | phase_q4 | 896 | -0.2685 | -1.219 | 0.5176 | 5.748 | 0.2746 | 1 | 0 |
| derivative_gate_transformer_new | phase_q1 | 1826 | -2.937 | -3.947 | -2.043 | 4.884 | 0.3697 | 1 | 0 |
| derivative_gate_transformer_new | phase_q2 | 1473 | -2.349 | -3.368 | -1.48 | 4.937 | 0.3238 | 1 | 0 |
| derivative_gate_transformer_new | phase_q3 | 1271 | -2.395 | -2.972 | -1.481 | 4.904 | 0.3273 | 1 | 0 |
| derivative_gate_transformer_new | phase_q4 | 896 | -2.368 | -3.737 | -1.213 | 4.883 | 0.2746 | 1 | 0 |
| gradient_boosted_trees | phase_q1 | 1826 | -0.5998 | -1.893 | 0.9248 | 3.93 | 0.3697 | 1 | 0 |
| gradient_boosted_trees | phase_q2 | 1473 | -0.5919 | -1.788 | 0.5241 | 3.775 | 0.3238 | 1 | 0 |
| gradient_boosted_trees | phase_q3 | 1271 | -0.4897 | -1.66 | 0.59 | 3.625 | 0.3273 | 1 | 0 |
| gradient_boosted_trees | phase_q4 | 896 | -0.6765 | -2.144 | 0.5163 | 3.72 | 0.2746 | 1 | 0 |
| mlp | phase_q1 | 1826 | -0.7972 | -1.652 | 0.942 | 4.468 | 0.3697 | 1 | 0 |
| mlp | phase_q2 | 1473 | -0.8988 | -2.14 | 0.7184 | 4.227 | 0.3238 | 1 | 0 |
| mlp | phase_q3 | 1271 | -1.167 | -1.985 | 0.54 | 4.356 | 0.3273 | 1 | 0 |
| mlp | phase_q4 | 896 | -0.9712 | -2.022 | 0.268 | 4.277 | 0.2746 | 1 | 0 |
| ridge | phase_q1 | 1826 | -0.6398 | -1.745 | 0.4632 | 4.368 | 0.3697 | 1 | 0 |
| ridge | phase_q2 | 1473 | -0.5168 | -1.635 | 0.6567 | 4.084 | 0.3238 | 1 | 0 |
| ridge | phase_q3 | 1271 | -0.4178 | -1.156 | 0.6427 | 3.977 | 0.3273 | 1 | 0 |
| ridge | phase_q4 | 896 | -0.4805 | -1.488 | 0.5884 | 4.146 | 0.2746 | 1 | 0 |
| traditional_cfd_template_derivative | phase_q1 | 1826 | 0.4407 | 0.1218 | 0.6807 | 0.8769 | 0.3697 | 1 | 0 |
| traditional_cfd_template_derivative | phase_q2 | 1473 | 0.4063 | 0.03112 | 0.6617 | 0.8904 | 0.3238 | 1 | 0 |
| traditional_cfd_template_derivative | phase_q3 | 1271 | 0.3364 | -0.008869 | 0.6301 | 0.952 | 0.3273 | 1 | 0 |
| traditional_cfd_template_derivative | phase_q4 | 896 | 0.2766 | -0.04437 | 0.5483 | 0.86 | 0.2746 | 1 | 0 |

Phase-scrambled nulls randomly permute phase-bin labels within each method on
the held-out sample.  A positive `observed_minus_null_median_ns` indicates a
larger phase-bias span than expected from the same residual distribution with
phase labels destroyed.

| method | observed_phase_bias_span_ns | phase_scrambled_null_span_median_ns | phase_scrambled_null_span_ci_low_ns | phase_scrambled_null_span_ci_high_ns | observed_minus_null_median_ns |
| --- | --- | --- | --- | --- | --- |
| compact_waveform_transformer | 0.9125 | 0.3747 | 0.1281 | 0.7226 | 0.5379 |
| derivative_gate_transformer_new | 0.5881 | 0.2973 | 0.07248 | 0.6547 | 0.2908 |
| traditional_cfd_template_derivative | 0.1642 | 0.04825 | 0.01496 | 0.1034 | 0.1159 |
| mlp | 0.3694 | 0.2703 | 0.08725 | 0.545 | 0.09914 |
| 1d_cnn | 0.3894 | 0.3781 | 0.09812 | 0.7658 | 0.01126 |
| gradient_boosted_trees | 0.1868 | 0.2484 | 0.07262 | 0.5037 | -0.0616 |
| ridge | 0.2219 | 0.2987 | 0.1069 | 0.6 | -0.07672 |

Trigger-alignment summary:

| method | trigger_alignment_bin | n | bias_ns | sigma68_ns | rms_ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | even_peak_sample | 2741 | -2.098 | 5.351 | 7.482 |
| 1d_cnn | odd_peak_sample | 2725 | -1.758 | 6.388 | 8.26 |
| compact_waveform_transformer | even_peak_sample | 2741 | 0.447 | 5.8 | 6.236 |
| compact_waveform_transformer | odd_peak_sample | 2725 | -0.01665 | 6.014 | 6.788 |
| derivative_gate_transformer_new | even_peak_sample | 2741 | -2.421 | 4.687 | 6.264 |
| derivative_gate_transformer_new | odd_peak_sample | 2725 | -2.613 | 5 | 6.864 |
| gradient_boosted_trees | even_peak_sample | 2741 | -0.657 | 3.669 | 4.382 |
| gradient_boosted_trees | odd_peak_sample | 2725 | -0.5172 | 3.909 | 4.841 |
| mlp | even_peak_sample | 2741 | -0.842 | 4.16 | 4.821 |
| mlp | odd_peak_sample | 2725 | -1.001 | 4.507 | 5.177 |
| ridge | even_peak_sample | 2741 | -0.6475 | 4.148 | 5.065 |
| ridge | odd_peak_sample | 2725 | -0.4381 | 4.156 | 5.251 |
| traditional_cfd_template_derivative | even_peak_sample | 2741 | 0.3886 | 0.8683 | 0.8975 |
| traditional_cfd_template_derivative | odd_peak_sample | 2725 | 0.3858 | 0.9346 | 0.9585 |

## Interpretation, Systematics, and Caveats

This S61b benchmark measures relative transfer on a reproducible waveform-derived timing residual and explicitly tests whether phase labels carry stable held-out structure beyond phase-scrambled nulls.  The raw ROOT files do not contain an independent external
picosecond timing truth for each pulse, so the numerical winner should not be
read as an absolute detector timing limit.  It answers the narrower ticket
question: whether ADC phase and trigger-alignment structure survives
held-out-run validation beyond a strong phase-harmonic CFD/template residual fit.

The run-block bootstrap is deliberately conservative for data-taking-period
transfer and can produce wider intervals than event bootstrap.  Neural models
are compact and trained under a fixed small epoch budget suitable for this
laptop worker; the study tests whether phase-aware waveform architectures naturally
outperform transparent timing fits, not whether exhaustive architecture search
can overfit the proxy.  Pedestal drift strata use raw pretrigger baseline
displacement from the run/stave median, so they are useful diagnostics but not
external electronics-state labels.

The result is consistent with the recent S41a/S40b timing family if the
traditional method remains competitive: transparent CFD/template corrections
capture most of the stable sub-sample timing signal, while derivative features
mainly expose where late tails and pedestal wander destabilize learned models.

Observed benchmark artifact span was `1191.9 s`; finalizer runtime was `0.0 s`; base runtime was `0.0 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.

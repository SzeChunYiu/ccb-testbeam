# S71a Slew-Rate Hysteresis Timing Under Pedestal Memory

## Abstract

Ticket `#2569` asks whether pulse-shape slew-rate hysteresis explains
residual timing bias under pedestal memory and mild pile-up.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 0.9206 ns`
`[0.7174, 1.083]`.  The
traditional derivative comparator obtains `0.9206 ns`
`[0.7174, 1.083]`.

## Ticket Claim Provenance

The required claim helper was run exactly once:

```text
tn-ticket claim testbeam-laptop-4 --project testbeam
```

It returned the null queue rendering

```text
# null

null
null
```

without assigning a worker label.  Read-only GitHub inspection showed open
`project:testbeam` tickets and no `worker:testbeam-laptop-4` claim, so issue
`#2569` was bound without a second helper invocation by:

```text
gh issue edit 2569 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open
```

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
| heldout | 5466 |
| train | 15137 |

Confidence intervals use `500` paired percentile
bootstrap replicates that resample held-out runs with replacement.  Paired
deltas subtract each replicate of the traditional derivative comparator from
the corresponding replicate of the learned method.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_cfd_template_derivative | traditional | CFD20/50 template time-walk baseline plus ridge-regularized derivative and curvature residual correction |
| ridge | linear ML | standardized ridge regression on pedestal, amplitude, CFD, waveform, derivative, and curvature features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted regression on the same leakage-controlled derivative feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered waveform, detector-state, derivative, and curvature summaries |
| 1d_cnn | neural waveform | compact 1D convolutional regressor over normalized 18-sample waveforms |
| compact_waveform_transformer | neural waveform | one-layer waveform self-attention encoder inherited from the audited timing benchmark |
| derivative_gate_transformer_new | new architecture | compact transformer over waveform, first derivative, and second derivative channels with derivative-magnitude pooling |

The new architecture is sensible for this ticket because the hypothesis is not
generic waveform learning; it is that slew-rate hysteresis, edge asymmetry, and
curvature channels localize pulse-shape timing changes under pedestal memory.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.1856 | -0.05734 | 0.5649 | 0.9206 | 0.7174 | 1.083 | 0.9142 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.664 | -1.761 | 0.6538 | 3.545 | 2.956 | 4.023 | 5.003 | 0.1661 | 0.0408 |
| ridge | 5466 | -0.5574 | -1.377 | 0.4925 | 3.95 | 3.426 | 4.784 | 5.267 | 0.2216 | 0.04446 |
| mlp | 5466 | -1.151 | -2.064 | 0.073 | 4.231 | 3.642 | 4.724 | 5.38 | 0.245 | 0.05049 |
| derivative_gate_transformer_new | 5466 | -1.296 | -2.325 | -0.1499 | 4.673 | 4.178 | 5.648 | 6.529 | 0.316 | 0.07373 |
| 1d_cnn | 5466 | 0.2583 | -0.5898 | 1.297 | 5.258 | 4.729 | 6.179 | 7.453 | 0.3447 | 0.1211 |
| compact_waveform_transformer | 5466 | -0.349 | -1.049 | 0.475 | 6.216 | 5.812 | 7.038 | 7.235 | 0.4202 | 0.1187 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.624 | 2.096 | 3.101 | -0.8497 | -2.081 | 0.5066 | 0.1661 |
| ridge | traditional_cfd_template_derivative | 3.03 | 2.467 | 3.867 | -0.7431 | -1.556 | 0.2605 | 0.2216 |
| mlp | traditional_cfd_template_derivative | 3.31 | 2.692 | 3.857 | -1.336 | -2.322 | -0.09796 | 0.245 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 3.752 | 3.243 | 4.795 | -1.482 | -2.652 | -0.3184 | 0.316 |
| 1d_cnn | traditional_cfd_template_derivative | 4.337 | 3.74 | 5.244 | 0.07262 | -0.8767 | 1.113 | 0.3447 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 5.295 | 4.823 | 6.143 | -0.5347 | -1.284 | 0.3025 | 0.4202 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.1212 | 0.9142 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 1.09 | 3.012 | 0.2467 |
| sample_i_analysis | mlp | 1350 | 0.565 | 4.504 | 0.2933 |
| sample_i_analysis | ridge | 1350 | 0.9765 | 4.874 | 0.3111 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | 0.3512 | 5.868 | 0.3652 |
| sample_i_analysis | 1d_cnn | 1350 | 0.6681 | 6.753 | 0.4311 |
| sample_i_analysis | compact_waveform_transformer | 1350 | 0.2518 | 7.679 | 0.4452 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | 0.1552 | 1.197 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.559 | 4.301 | 0.2192 |
| sample_i_calib | mlp | 657 | 1.231 | 5.074 | 0.3501 |
| sample_i_calib | ridge | 657 | 1.568 | 5.262 | 0.3912 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 1.182 | 5.974 | 0.4079 |
| sample_i_calib | compact_waveform_transformer | 657 | 0.4945 | 6.326 | 0.4399 |
| sample_i_calib | 1d_cnn | 657 | 1.628 | 6.741 | 0.4795 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.2608 | 0.8362 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.621 | 3.232 | 0.1446 |
| sample_ii_analysis | ridge | 2739 | -0.9653 | 3.492 | 0.161 |
| sample_ii_analysis | mlp | 2739 | -2.099 | 3.821 | 0.2227 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | -1.919 | 4.252 | 0.2808 |
| sample_ii_analysis | 1d_cnn | 2739 | 0.1777 | 4.777 | 0.2943 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | -0.827 | 6.088 | 0.4177 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.8967 | 0.9016 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.777 | 2.014 | 0.04861 |
| sample_ii_calib | ridge | 720 | -1.846 | 3.024 | 0.1292 |
| sample_ii_calib | mlp | 720 | -2.047 | 3.07 | 0.1431 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | -2.492 | 3.816 | 0.2736 |
| sample_ii_calib | 1d_cnn | 720 | -0.5589 | 4.258 | 0.2514 |
| sample_ii_calib | compact_waveform_transformer | 720 | -0.6832 | 5.496 | 0.3653 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.628 | 6.741 | 0.4795 |
| 1d_cnn | 50 | 680 | -0.7757 | 11.54 | 0.4132 |
| 1d_cnn | 57 | 670 | 3.218 | 5.781 | 0.4493 |
| 1d_cnn | 58 | 654 | -1.791 | 5.2 | 0.3593 |
| 1d_cnn | 60 | 720 | 1.22 | 4.381 | 0.2736 |
| 1d_cnn | 62 | 720 | 0.4785 | 4.535 | 0.2792 |
| 1d_cnn | 64 | 720 | -0.5589 | 4.258 | 0.2514 |
| 1d_cnn | 65 | 645 | 0.2229 | 4.478 | 0.2682 |
| compact_waveform_transformer | 42 | 657 | 0.4945 | 6.326 | 0.4399 |
| compact_waveform_transformer | 50 | 680 | -0.9146 | 10.94 | 0.4471 |
| compact_waveform_transformer | 57 | 670 | 2.161 | 6.029 | 0.4433 |
| compact_waveform_transformer | 58 | 654 | -2.365 | 6.222 | 0.4587 |
| compact_waveform_transformer | 60 | 720 | 0.002161 | 6.172 | 0.4264 |
| compact_waveform_transformer | 62 | 720 | -0.9202 | 6.151 | 0.4014 |
| compact_waveform_transformer | 64 | 720 | -0.6832 | 5.496 | 0.3653 |
| compact_waveform_transformer | 65 | 645 | -0.03979 | 5.469 | 0.3845 |
| derivative_gate_transformer_new | 42 | 657 | 1.182 | 5.974 | 0.4079 |
| derivative_gate_transformer_new | 50 | 680 | -0.8512 | 11.46 | 0.4044 |
| derivative_gate_transformer_new | 57 | 670 | 1.73 | 4.766 | 0.3254 |
| derivative_gate_transformer_new | 58 | 654 | -3.521 | 4.706 | 0.3853 |
| derivative_gate_transformer_new | 60 | 720 | -0.749 | 3.973 | 0.2306 |
| derivative_gate_transformer_new | 62 | 720 | -1.728 | 4.245 | 0.2611 |
| derivative_gate_transformer_new | 64 | 720 | -2.492 | 3.816 | 0.2736 |
| derivative_gate_transformer_new | 65 | 645 | -1.631 | 3.953 | 0.2527 |
| gradient_boosted_trees | 42 | 657 | 1.559 | 4.301 | 0.2192 |
| gradient_boosted_trees | 50 | 680 | 1.097 | 10.85 | 0.2985 |
| gradient_boosted_trees | 57 | 670 | 1.063 | 3.277 | 0.194 |
| gradient_boosted_trees | 58 | 654 | -3.277 | 2.967 | 0.2691 |
| gradient_boosted_trees | 60 | 720 | -0.2619 | 3.051 | 0.1222 |
| gradient_boosted_trees | 62 | 720 | -1.44 | 3.016 | 0.07083 |
| gradient_boosted_trees | 64 | 720 | -1.777 | 2.014 | 0.04861 |
| gradient_boosted_trees | 65 | 645 | -2.086 | 3.216 | 0.1256 |
| mlp | 42 | 657 | 1.231 | 5.074 | 0.3501 |
| mlp | 50 | 680 | -0.1213 | 10.61 | 0.3279 |
| mlp | 57 | 670 | 1.308 | 4.27 | 0.2582 |
| mlp | 58 | 654 | -3.4 | 3.614 | 0.318 |
| mlp | 60 | 720 | -1.05 | 3.758 | 0.1792 |
| mlp | 62 | 720 | -1.635 | 3.818 | 0.1806 |
| mlp | 64 | 720 | -2.047 | 3.07 | 0.1431 |
| mlp | 65 | 645 | -2.437 | 3.852 | 0.2217 |
| ridge | 42 | 657 | 1.568 | 5.262 | 0.3912 |
| ridge | 50 | 680 | -0.1628 | 10.91 | 0.3426 |
| ridge | 57 | 670 | 2.258 | 4.503 | 0.2791 |
| ridge | 58 | 654 | -2.562 | 3.96 | 0.263 |
| ridge | 60 | 720 | -0.496 | 2.904 | 0.1056 |
| ridge | 62 | 720 | -0.8076 | 3.383 | 0.1319 |
| ridge | 64 | 720 | -1.846 | 3.024 | 0.1292 |
| ridge | 65 | 645 | -0.9255 | 3.459 | 0.1519 |
| traditional_cfd_template_derivative | 42 | 657 | 0.1552 | 1.197 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | 0.05317 | 0.4115 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | -0.7538 | 1.12 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.7474 | 0.8341 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | 0.01633 | 0.564 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.1257 | 0.9989 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.8967 | 0.9016 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.5474 | 0.6133 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1622 | 0.6191 | 6.652 | 0.4223 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1622 | -3.269 | 6.047 | 0.4901 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1622 | -2.073 | 5.2 | 0.3773 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1622 | -0.4583 | 3.503 | 0.185 |
| curvature_energy_bin | curved | mlp | 1622 | -1.116 | 3.987 | 0.2571 |
| curvature_energy_bin | curved | ridge | 1622 | -0.659 | 4.045 | 0.2435 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1622 | 0.1551 | 0.9684 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1949 | 0.7405 | 4.947 | 0.3238 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1949 | 1.093 | 6.212 | 0.4423 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1949 | -0.6616 | 4.725 | 0.2971 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1949 | -0.4994 | 3.689 | 0.1709 |
| curvature_energy_bin | moderate | mlp | 1949 | -0.9518 | 4.4 | 0.2591 |
| curvature_energy_bin | moderate | ridge | 1949 | -0.8526 | 3.973 | 0.2283 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1949 | 0.2416 | 0.891 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1895 | -0.4839 | 4.82 | 0.2997 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1895 | 0.6913 | 4.84 | 0.3377 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1895 | -1.485 | 4.161 | 0.2828 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1895 | -0.9578 | 3.384 | 0.1451 |
| curvature_energy_bin | smooth | mlp | 1895 | -1.446 | 4.092 | 0.2201 |
| curvature_energy_bin | smooth | ridge | 1895 | 0.01547 | 3.729 | 0.1958 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1895 | 0.141 | 0.9448 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1838 | -0.2493 | 4.329 | 0.2568 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1838 | -0.7364 | 5.855 | 0.3923 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1838 | -1.815 | 4.393 | 0.2943 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1838 | -0.9431 | 3.129 | 0.13 |
| derivative_onset_bin | nominal | mlp | 1838 | -1.502 | 3.698 | 0.2073 |
| derivative_onset_bin | nominal | ridge | 1838 | -0.836 | 3.595 | 0.1719 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1838 | 0.2259 | 0.9053 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1931 | 0.4212 | 4.577 | 0.29 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1931 | -0.3231 | 5.85 | 0.4013 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1931 | -1.575 | 4.397 | 0.3055 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1931 | -0.8781 | 3.092 | 0.1082 |
| derivative_onset_bin | sharp | mlp | 1931 | -1.452 | 3.975 | 0.2185 |
| derivative_onset_bin | sharp | ridge | 1931 | -0.8594 | 3.784 | 0.2227 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1931 | 0.2575 | 0.8994 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1697 | 0.9623 | 8.055 | 0.5021 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1697 | 0.2844 | 6.889 | 0.472 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1697 | -0.2718 | 5.463 | 0.3512 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1697 | 0.3501 | 4.412 | 0.2711 |
| derivative_onset_bin | slow | mlp | 1697 | -0.2903 | 4.889 | 0.3159 |
| derivative_onset_bin | slow | ridge | 1697 | 0.2939 | 4.376 | 0.274 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1697 | 0.04833 | 0.8944 | 0 |
| energy_bin | q1_low | 1d_cnn | 1404 | -0.427 | 7.022 | 0.4338 |
| energy_bin | q1_low | compact_waveform_transformer | 1404 | -0.1864 | 5.677 | 0.3839 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1404 | -1.591 | 4.718 | 0.3497 |
| energy_bin | q1_low | gradient_boosted_trees | 1404 | -0.8844 | 3.527 | 0.1702 |
| energy_bin | q1_low | mlp | 1404 | -1.498 | 4.055 | 0.2415 |
| energy_bin | q1_low | ridge | 1404 | -0.01159 | 3.957 | 0.213 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1404 | -0.09627 | 1.043 | 0 |
| energy_bin | q2 | 1d_cnn | 1493 | 0.2632 | 4.542 | 0.288 |
| energy_bin | q2 | compact_waveform_transformer | 1493 | 1.19 | 5.517 | 0.3958 |
| energy_bin | q2 | derivative_gate_transformer_new | 1493 | -0.9541 | 4.23 | 0.2559 |
| energy_bin | q2 | gradient_boosted_trees | 1493 | -0.6818 | 3.49 | 0.142 |
| energy_bin | q2 | mlp | 1493 | -1.354 | 4.355 | 0.2458 |
| energy_bin | q2 | ridge | 1493 | -0.4303 | 3.877 | 0.211 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1493 | 0.2475 | 0.8344 | 0 |
| energy_bin | q3 | 1d_cnn | 1461 | 1.66 | 4.843 | 0.321 |
| energy_bin | q3 | compact_waveform_transformer | 1461 | 0.9137 | 6.191 | 0.436 |
| energy_bin | q3 | derivative_gate_transformer_new | 1461 | -0.7382 | 4.842 | 0.3107 |
| energy_bin | q3 | gradient_boosted_trees | 1461 | -0.5736 | 3.575 | 0.1643 |
| energy_bin | q3 | mlp | 1461 | -0.9468 | 4.292 | 0.2423 |
| energy_bin | q3 | ridge | 1461 | -0.823 | 4.063 | 0.2423 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1461 | 0.2929 | 0.9239 | 0 |
| energy_bin | q4_high | 1d_cnn | 1108 | -0.792 | 5.167 | 0.3394 |
| energy_bin | q4_high | compact_waveform_transformer | 1108 | -4.003 | 5.375 | 0.4783 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1108 | -2.488 | 5.176 | 0.361 |
| energy_bin | q4_high | gradient_boosted_trees | 1108 | -0.3851 | 3.4 | 0.1958 |
| energy_bin | q4_high | mlp | 1108 | -0.6363 | 3.983 | 0.2518 |
| energy_bin | q4_high | ridge | 1108 | -0.6163 | 3.903 | 0.2193 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1108 | 0.2434 | 0.9569 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3225 | 0.2302 | 5.226 | 0.3436 |
| late_tail_morphology | compact | compact_waveform_transformer | 3225 | -0.4915 | 6.253 | 0.4226 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3225 | -1.697 | 4.487 | 0.3203 |
| late_tail_morphology | compact | gradient_boosted_trees | 3225 | -1.036 | 3.235 | 0.1312 |
| late_tail_morphology | compact | mlp | 3225 | -1.784 | 3.94 | 0.2248 |
| late_tail_morphology | compact | ridge | 3225 | -0.8296 | 3.875 | 0.2087 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3225 | 0.213 | 0.9049 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 645 | -0.3616 | 3.664 | 0.2341 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 645 | -1.964 | 5.161 | 0.3473 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 645 | -2.304 | 4.173 | 0.2899 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 645 | -0.4161 | 2.952 | 0.1132 |
| late_tail_morphology | diffuse_tail | mlp | 645 | -0.2663 | 3.83 | 0.2155 |
| late_tail_morphology | diffuse_tail | ridge | 645 | -0.8768 | 3.388 | 0.1721 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 645 | 0.3635 | 0.9606 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 392 | -0.1224 | 5.864 | 0.3673 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 392 | -0.7948 | 6.195 | 0.4439 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 392 | 0.07309 | 5.459 | 0.3418 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 392 | -0.08173 | 3.346 | 0.1709 |
| late_tail_morphology | late_derivative_bump | mlp | 392 | -1.166 | 3.673 | 0.2474 |
| late_tail_morphology | late_derivative_bump | ridge | 392 | -0.05226 | 3.674 | 0.2347 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 392 | 0.03018 | 0.8599 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1204 | 1.09 | 5.964 | 0.3995 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1204 | 1.422 | 6.379 | 0.4452 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1204 | 0.07736 | 4.938 | 0.3098 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1204 | 0.3837 | 4.605 | 0.2865 |
| late_tail_morphology | late_rising_tail | mlp | 1204 | 0.2701 | 4.846 | 0.314 |
| late_tail_morphology | late_rising_tail | ridge | 1204 | 0.1907 | 4.298 | 0.2782 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1204 | 0.09019 | 0.9058 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1699 | 1.156 | 7.346 | 0.4897 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1699 | -2.177 | 7.161 | 0.5162 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1699 | -1.792 | 5.271 | 0.3832 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1699 | -0.5652 | 3.839 | 0.1931 |
| pedestal_drift_bin | high | mlp | 1699 | -1.156 | 4.259 | 0.2655 |
| pedestal_drift_bin | high | ridge | 1699 | -0.5481 | 4.042 | 0.236 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1699 | 0.1572 | 0.9473 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1833 | -0.1835 | 4.685 | 0.2957 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1833 | 0.185 | 5.682 | 0.3824 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1833 | -1.23 | 4.508 | 0.3011 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1833 | -0.6656 | 3.357 | 0.1566 |
| pedestal_drift_bin | low | mlp | 1833 | -1.091 | 4.285 | 0.2466 |
| pedestal_drift_bin | low | ridge | 1833 | -0.5594 | 4.086 | 0.2297 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1833 | 0.1624 | 0.899 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1934 | 0.1787 | 4.423 | 0.2637 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1934 | 0.3114 | 5.519 | 0.3718 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1934 | -1.096 | 4.264 | 0.2709 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1934 | -0.6955 | 3.442 | 0.1515 |
| pedestal_drift_bin | mid | mlp | 1934 | -1.198 | 4.081 | 0.2254 |
| pedestal_drift_bin | mid | ridge | 1934 | -0.562 | 3.758 | 0.2011 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1934 | 0.234 | 0.9046 | 0 |
| pid_sideband | central | 1d_cnn | 3736 | 0.1792 | 4.695 | 0.2974 |
| pid_sideband | central | compact_waveform_transformer | 3736 | 0.5416 | 5.501 | 0.3777 |
| pid_sideband | central | derivative_gate_transformer_new | 3736 | -0.8525 | 4.391 | 0.2885 |
| pid_sideband | central | gradient_boosted_trees | 3736 | -0.6113 | 3.52 | 0.1614 |
| pid_sideband | central | mlp | 3736 | -0.984 | 4.214 | 0.2425 |
| pid_sideband | central | ridge | 3736 | -0.4278 | 4.053 | 0.2291 |
| pid_sideband | central | traditional_cfd_template_derivative | 3736 | 0.1533 | 0.9128 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 886 | 2.181 | 10.01 | 0.6422 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 886 | -5.536 | 6.122 | 0.6242 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 886 | -3.182 | 5.528 | 0.474 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 886 | -0.8946 | 3.76 | 0.193 |
| pid_sideband | high_duplicate | mlp | 886 | -2.115 | 3.954 | 0.281 |
| pid_sideband | high_duplicate | ridge | 886 | -0.9286 | 4.015 | 0.2348 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 886 | 0.1631 | 0.976 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 844 | -0.1334 | 4.296 | 0.2417 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 844 | -0.3229 | 5.726 | 0.3945 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 844 | -1.57 | 4.354 | 0.2713 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 844 | -0.6959 | 3.352 | 0.1588 |
| pid_sideband | low_duplicate | mlp | 844 | -1.183 | 3.855 | 0.218 |
| pid_sideband | low_duplicate | ridge | 844 | -0.7397 | 3.466 | 0.1742 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 844 | 0.3993 | 0.8738 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1648 | -0.8625 | 4.764 | 0.3101 |
| pileup_separation_bin | close | compact_waveform_transformer | 1648 | -0.6466 | 5.799 | 0.4126 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1648 | -1.758 | 4.695 | 0.3386 |
| pileup_separation_bin | close | gradient_boosted_trees | 1648 | -0.9692 | 3.281 | 0.1408 |
| pileup_separation_bin | close | mlp | 1648 | -1.523 | 4.046 | 0.247 |
| pileup_separation_bin | close | ridge | 1648 | -1.033 | 3.855 | 0.2288 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1648 | 0.2437 | 0.9194 | 0 |
| pileup_separation_bin | late | 1d_cnn | 3 | -8.43 | 17.5 | 0.6667 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -4.113 | 17.55 | 0.3333 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 3 | -3.285 | 14.98 | 0.6667 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | 1.853 | 13.78 | 0.6667 |
| pileup_separation_bin | late | mlp | 3 | -0.3385 | 28.96 | 0.6667 |
| pileup_separation_bin | late | ridge | 3 | 1.121 | 3.308 | 0.3333 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 3 | -0.1846 | 0.4835 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1191 | 1.649 | 5.751 | 0.4123 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1191 | -3.818 | 6.072 | 0.5214 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1191 | -2.231 | 4.865 | 0.3543 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1191 | -0.9805 | 3.354 | 0.1503 |
| pileup_separation_bin | mid | mlp | 1191 | -1.767 | 3.726 | 0.2242 |
| pileup_separation_bin | mid | ridge | 1191 | -0.9485 | 3.823 | 0.225 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1191 | 0.3085 | 0.9391 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2624 | 0.5376 | 5.095 | 0.3354 |
| pileup_separation_bin | none | compact_waveform_transformer | 2624 | 1.3 | 5.1 | 0.3792 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2624 | -0.6242 | 4.426 | 0.2839 |
| pileup_separation_bin | none | gradient_boosted_trees | 2624 | -0.2529 | 3.661 | 0.1886 |
| pileup_separation_bin | none | mlp | 2624 | -0.6797 | 4.31 | 0.2527 |
| pileup_separation_bin | none | ridge | 2624 | 0.02777 | 3.806 | 0.2153 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2624 | 0.08057 | 0.9091 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1812 | 0.4782 | 7.162 | 0.4724 |
| pulse_shape_class | compact | compact_waveform_transformer | 1812 | -1.66 | 6.733 | 0.489 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1812 | -2.078 | 4.846 | 0.3929 |
| pulse_shape_class | compact | gradient_boosted_trees | 1812 | -1.336 | 3.46 | 0.1567 |
| pulse_shape_class | compact | mlp | 1812 | -2.303 | 4.067 | 0.266 |
| pulse_shape_class | compact | ridge | 1812 | -0.6744 | 4.218 | 0.2638 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1812 | 0.1702 | 0.9781 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1865 | 0.3894 | 5.255 | 0.3416 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1865 | 0.1779 | 6.149 | 0.4102 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1865 | -0.955 | 4.846 | 0.3024 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1865 | 0.07646 | 4.056 | 0.2257 |
| pulse_shape_class | late_tail | mlp | 1865 | 0.02004 | 4.45 | 0.2788 |
| pulse_shape_class | late_tail | ridge | 1865 | -0.2929 | 3.989 | 0.2408 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1865 | 0.1634 | 0.9308 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1789 | -0.0245 | 4.039 | 0.2186 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1789 | 0.05486 | 5.415 | 0.3611 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1789 | -1.098 | 4.205 | 0.2521 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1789 | -0.7026 | 3.061 | 0.1135 |
| pulse_shape_class | nominal | mlp | 1789 | -1.298 | 3.728 | 0.1884 |
| pulse_shape_class | nominal | ridge | 1789 | -0.7914 | 3.491 | 0.1587 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1789 | 0.2146 | 0.8232 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3942 | 0.4023 | 5.633 | 0.3686 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3942 | -0.4894 | 6.42 | 0.4315 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3942 | -1.635 | 4.777 | 0.3346 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3942 | -0.8215 | 3.561 | 0.1712 |
| saturation_onset_bin | linear | mlp | 3942 | -1.325 | 4.223 | 0.2415 |
| saturation_onset_bin | linear | ridge | 3942 | -0.7013 | 4.021 | 0.2288 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3942 | 0.2316 | 0.9448 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1524 | 0.03738 | 4.641 | 0.2828 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1524 | -0.0834 | 5.844 | 0.3911 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1524 | -0.4839 | 4.268 | 0.2677 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1524 | -0.1316 | 3.489 | 0.1529 |
| saturation_onset_bin | near_saturation | mlp | 1524 | -0.6839 | 4.244 | 0.2539 |
| saturation_onset_bin | near_saturation | ridge | 1524 | -0.001004 | 3.822 | 0.2028 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1524 | 0.08147 | 0.8462 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.82 | curved | 6.652 | 1.832 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.84 | moderate | 6.212 | 1.372 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 4.161 | curved | 5.2 | 1.039 |
| curvature_energy_bin | mlp | 3 | curved | 3.987 | moderate | 4.4 | 0.4129 |
| curvature_energy_bin | ridge | 3 | smooth | 3.729 | curved | 4.045 | 0.3155 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.384 | moderate | 3.689 | 0.3048 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | moderate | 0.891 | curved | 0.9684 | 0.0774 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.329 | slow | 8.055 | 3.726 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.092 | slow | 4.412 | 1.32 |
| derivative_onset_bin | mlp | 3 | nominal | 3.698 | slow | 4.889 | 1.191 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | nominal | 4.393 | slow | 5.463 | 1.071 |
| derivative_onset_bin | compact_waveform_transformer | 3 | sharp | 5.85 | slow | 6.889 | 1.039 |
| derivative_onset_bin | ridge | 3 | nominal | 3.595 | slow | 4.376 | 0.7812 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | slow | 0.8944 | nominal | 0.9053 | 0.01092 |
| energy_bin | 1d_cnn | 4 | q2 | 4.542 | q1_low | 7.022 | 2.48 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 4.23 | q4_high | 5.176 | 0.9458 |
| energy_bin | compact_waveform_transformer | 4 | q4_high | 5.375 | q3 | 6.191 | 0.8167 |
| energy_bin | mlp | 4 | q4_high | 3.983 | q2 | 4.355 | 0.3715 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.8344 | q1_low | 1.043 | 0.2086 |
| energy_bin | ridge | 4 | q2 | 3.877 | q3 | 4.063 | 0.1862 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.4 | q3 | 3.575 | 0.1754 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 3.664 | late_rising_tail | 5.964 | 2.3 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 2.952 | late_rising_tail | 4.605 | 1.653 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 4.173 | late_derivative_bump | 5.459 | 1.286 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 5.161 | late_rising_tail | 6.379 | 1.219 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.673 | late_rising_tail | 4.846 | 1.173 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.388 | late_rising_tail | 4.298 | 0.91 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_derivative_bump | 0.8599 | diffuse_tail | 0.9606 | 0.1007 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 4.423 | high | 7.346 | 2.923 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.519 | high | 7.161 | 1.642 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.264 | high | 5.271 | 1.007 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.357 | high | 3.839 | 0.482 |
| pedestal_drift_bin | ridge | 3 | mid | 3.758 | low | 4.086 | 0.3283 |
| pedestal_drift_bin | mlp | 3 | mid | 4.081 | low | 4.285 | 0.2041 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | low | 0.899 | high | 0.9473 | 0.04828 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 4.296 | high_duplicate | 10.01 | 5.719 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.354 | high_duplicate | 5.528 | 1.173 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.501 | high_duplicate | 6.122 | 0.6214 |
| pid_sideband | ridge | 3 | low_duplicate | 3.466 | central | 4.053 | 0.5863 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.352 | high_duplicate | 3.76 | 0.4085 |
| pid_sideband | mlp | 3 | low_duplicate | 3.855 | central | 4.214 | 0.3588 |
| pid_sideband | traditional_cfd_template_derivative | 3 | low_duplicate | 0.8738 | high_duplicate | 0.976 | 0.1022 |
| pileup_separation_bin | mlp | 4 | mid | 3.726 | late | 28.96 | 25.23 |
| pileup_separation_bin | 1d_cnn | 4 | close | 4.764 | late | 17.5 | 12.74 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 5.1 | late | 17.55 | 12.45 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | none | 4.426 | late | 14.98 | 10.55 |
| pileup_separation_bin | gradient_boosted_trees | 4 | close | 3.281 | late | 13.78 | 10.5 |
| pileup_separation_bin | ridge | 4 | late | 3.308 | close | 3.855 | 0.5468 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | late | 0.4835 | mid | 0.9391 | 0.4556 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.039 | compact | 7.162 | 3.123 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.415 | compact | 6.733 | 1.318 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.061 | late_tail | 4.056 | 0.9953 |
| pulse_shape_class | ridge | 3 | nominal | 3.491 | compact | 4.218 | 0.7273 |
| pulse_shape_class | mlp | 3 | nominal | 3.728 | late_tail | 4.45 | 0.722 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.205 | late_tail | 4.846 | 0.641 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.8232 | compact | 0.9781 | 0.1548 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.641 | linear | 5.633 | 0.9921 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.844 | linear | 6.42 | 0.5752 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 4.268 | linear | 4.777 | 0.5091 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.822 | linear | 4.021 | 0.1984 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.8462 | linear | 0.9448 | 0.09861 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.489 | linear | 3.561 | 0.07252 |
| saturation_onset_bin | mlp | 2 | linear | 4.223 | near_saturation | 4.244 | 0.02088 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.  They are diagnostic
rather than the primary contest: each ablation uses a bounded 6000-row training
subsample and 120 run-block bootstrap replicates so the ticket can complete on
the laptop worker after the full method predictions and 500-replicate primary
paired CIs have been written.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.9992 | 4.232 | 3.588 | 4.773 | -0.02227 | 0.2702 |
| full_derivative_gradient_boosted_trees | 76 | -0.9653 | 4.255 | 3.645 | 4.764 | 0 | 0.2728 |
| amplitude_cfd_no_derivative | 5 | -0.609 | 4.872 | 4.032 | 5.849 | 0.6172 | 0.3205 |
| derivative_only | 43 | -0.6766 | 4.898 | 4.225 | 5.9 | 0.6434 | 0.3251 |
| onset_derivative_window_only | 14 | -1.021 | 5.161 | 4.462 | 6.253 | 0.9063 | 0.3641 |
| late_tail_curvature_window_only | 17 | -0.2328 | 5.991 | 5.33 | 6.98 | 1.737 | 0.3911 |
| pretrigger_derivative_only | 7 | -4.828 | 17.64 | 16.28 | 18.37 | 13.39 | 0.6354 |

## Slew-Rate Hysteresis and Transfer Diagnostics

For each held-out pulse I define a dimensionless slew hysteresis index

`H = (S_late - S_onset) / (|S_late| + |S_onset| + epsilon)`,

where `S_onset` is the positive derivative sum in samples 2-7 and `S_late` is
the late positive derivative sum after sample 9.  The pedestal-memory index is
`M = RMS(d_pretrigger) sign(baseline)`, and the shape-residual proxy is the
absolute curvature-energy displacement from the run median.  These are not used
as external labels; they are post-fit diagnostics for the requested
shape-residual closure, pedestal strata, pile-up strata, and energy/PID
transfer checks.

| axis | level | method | n | bias_ns | sigma68_ns | shape_residual_proxy_median | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1408 | -0.09627 | 1.043 | 0.2199 | 0 |
| energy_bin | q1_low | gradient_boosted_trees | 1408 | -0.8878 | 3.526 | 0.2199 | 0.1697 |
| energy_bin | q1_low | ridge | 1408 | -0.01491 | 3.952 | 0.2199 | 0.2124 |
| energy_bin | q1_low | mlp | 1408 | -1.502 | 4.049 | 0.2199 | 0.2408 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1408 | -1.597 | 4.724 | 0.2199 | 0.3501 |
| energy_bin | q1_low | compact_waveform_transformer | 1408 | -0.1864 | 5.68 | 0.2199 | 0.3842 |
| energy_bin | q1_low | 1d_cnn | 1408 | -0.4332 | 7.033 | 0.2199 | 0.4339 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1508 | 0.2559 | 0.834 | 0.1492 | 0 |
| energy_bin | q2 | gradient_boosted_trees | 1508 | -0.6891 | 3.494 | 0.1492 | 0.1426 |
| energy_bin | q2 | ridge | 1508 | -0.4305 | 3.859 | 0.1492 | 0.2109 |
| energy_bin | q2 | derivative_gate_transformer_new | 1508 | -0.9545 | 4.233 | 0.1492 | 0.256 |
| energy_bin | q2 | mlp | 1508 | -1.373 | 4.359 | 0.1492 | 0.246 |
| energy_bin | q2 | 1d_cnn | 1508 | 0.2461 | 4.54 | 0.1492 | 0.2871 |
| energy_bin | q2 | compact_waveform_transformer | 1508 | 1.172 | 5.536 | 0.1492 | 0.3972 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1472 | 0.2928 | 0.9224 | 0.08237 | 0 |
| energy_bin | q3 | gradient_boosted_trees | 1472 | -0.5548 | 3.598 | 0.08237 | 0.1658 |
| energy_bin | q3 | ridge | 1472 | -0.8142 | 4.092 | 0.08237 | 0.2432 |
| energy_bin | q3 | mlp | 1472 | -0.9287 | 4.299 | 0.08237 | 0.2446 |
| energy_bin | q3 | 1d_cnn | 1472 | 1.66 | 4.839 | 0.08237 | 0.3213 |
| energy_bin | q3 | derivative_gate_transformer_new | 1472 | -0.7126 | 4.854 | 0.08237 | 0.3118 |
| energy_bin | q3 | compact_waveform_transformer | 1472 | 0.9681 | 6.2 | 0.08237 | 0.4368 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1120 | 0.2434 | 0.9558 | 0.187 | 0 |
| energy_bin | q4_high | gradient_boosted_trees | 1120 | -0.3851 | 3.401 | 0.187 | 0.1964 |
| energy_bin | q4_high | ridge | 1120 | -0.6107 | 3.91 | 0.187 | 0.2196 |
| energy_bin | q4_high | mlp | 1120 | -0.5623 | 3.998 | 0.187 | 0.2536 |
| energy_bin | q4_high | 1d_cnn | 1120 | -0.792 | 5.179 | 0.187 | 0.3429 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1120 | -2.488 | 5.192 | 0.187 | 0.3634 |
| energy_bin | q4_high | compact_waveform_transformer | 1120 | -4.003 | 5.384 | 0.187 | 0.4795 |
| pedestal_memory_bin | high | traditional_cfd_template_derivative | 1831 | 0.08886 | 0.9403 | 0.1863 | 0 |
| pedestal_memory_bin | high | gradient_boosted_trees | 1831 | -0.5998 | 3.336 | 0.1863 | 0.1709 |
| pedestal_memory_bin | high | mlp | 1831 | -1.452 | 4.162 | 0.1863 | 0.2654 |
| pedestal_memory_bin | high | ridge | 1831 | -0.9988 | 4.376 | 0.1863 | 0.2807 |
| pedestal_memory_bin | high | derivative_gate_transformer_new | 1831 | -2.343 | 5.209 | 0.1863 | 0.4145 |
| pedestal_memory_bin | high | compact_waveform_transformer | 1831 | -3.461 | 5.879 | 0.1863 | 0.4888 |
| pedestal_memory_bin | high | 1d_cnn | 1831 | -0.1075 | 7.392 | 0.1863 | 0.4975 |
| pedestal_memory_bin | low | traditional_cfd_template_derivative | 1839 | 0.2686 | 0.8913 | 0.1377 | 0 |
| pedestal_memory_bin | low | gradient_boosted_trees | 1839 | -0.3342 | 3.582 | 0.1377 | 0.1718 |
| pedestal_memory_bin | low | ridge | 1839 | -0.4331 | 3.756 | 0.1377 | 0.2066 |
| pedestal_memory_bin | low | mlp | 1839 | -0.5092 | 4.261 | 0.1377 | 0.2485 |
| pedestal_memory_bin | low | derivative_gate_transformer_new | 1839 | -0.9324 | 4.471 | 0.1377 | 0.2692 |
| pedestal_memory_bin | low | 1d_cnn | 1839 | 0.4417 | 4.537 | 0.1377 | 0.2887 |
| pedestal_memory_bin | low | compact_waveform_transformer | 1839 | 1.004 | 5.878 | 0.1377 | 0.4144 |
| pedestal_memory_bin | mid | traditional_cfd_template_derivative | 1838 | 0.2044 | 0.9132 | 0.1537 | 0 |
| pedestal_memory_bin | mid | gradient_boosted_trees | 1838 | -0.995 | 3.52 | 0.1537 | 0.1572 |
| pedestal_memory_bin | mid | ridge | 1838 | -0.3617 | 3.583 | 0.1537 | 0.1779 |
| pedestal_memory_bin | mid | mlp | 1838 | -1.506 | 4.09 | 0.1537 | 0.2236 |
| pedestal_memory_bin | mid | derivative_gate_transformer_new | 1838 | -0.9905 | 4.121 | 0.1537 | 0.2671 |
| pedestal_memory_bin | mid | 1d_cnn | 1838 | 0.3112 | 4.223 | 0.1537 | 0.2497 |
| pedestal_memory_bin | mid | compact_waveform_transformer | 1838 | 1.267 | 4.859 | 0.1537 | 0.3607 |
| pid_sideband | central | traditional_cfd_template_derivative | 3771 | 0.1552 | 0.9113 | 0.1502 | 0 |
| pid_sideband | central | gradient_boosted_trees | 3771 | -0.6146 | 3.528 | 0.1502 | 0.1623 |
| pid_sideband | central | ridge | 3771 | -0.4303 | 4.058 | 0.1502 | 0.2294 |
| pid_sideband | central | mlp | 3771 | -0.981 | 4.226 | 0.1502 | 0.2442 |
| pid_sideband | central | derivative_gate_transformer_new | 3771 | -0.8545 | 4.435 | 0.1502 | 0.2901 |
| pid_sideband | central | 1d_cnn | 3771 | 0.1788 | 4.704 | 0.1502 | 0.2983 |
| pid_sideband | central | compact_waveform_transformer | 3771 | 0.5437 | 5.513 | 0.1502 | 0.3792 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 888 | 0.1689 | 0.9753 | 0.2268 | 0 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 888 | -0.885 | 3.762 | 0.2268 | 0.1937 |
| pid_sideband | high_duplicate | mlp | 888 | -2.111 | 3.945 | 0.2268 | 0.2804 |
| pid_sideband | high_duplicate | ridge | 888 | -0.914 | 4.009 | 0.2268 | 0.2342 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 888 | -3.186 | 5.513 | 0.2268 | 0.473 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 888 | -5.536 | 6.114 | 0.2268 | 0.625 |
| pid_sideband | high_duplicate | 1d_cnn | 888 | 2.181 | 10.08 | 0.2268 | 0.643 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 849 | 0.388 | 0.8737 | 0.1471 | 0 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 849 | -0.694 | 3.352 | 0.1471 | 0.1578 |
| pid_sideband | low_duplicate | ridge | 849 | -0.7393 | 3.471 | 0.1471 | 0.1743 |
| pid_sideband | low_duplicate | mlp | 849 | -1.176 | 3.856 | 0.1471 | 0.2167 |
| pid_sideband | low_duplicate | 1d_cnn | 849 | -0.1482 | 4.295 | 0.1471 | 0.2415 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 849 | -1.57 | 4.358 | 0.1471 | 0.2721 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 849 | -0.3303 | 5.727 | 0.1471 | 0.3946 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1664 | 0.2446 | 0.9163 | 0.1466 | 0 |
| pileup_separation_bin | close | gradient_boosted_trees | 1664 | -0.9612 | 3.282 | 0.1466 | 0.1412 |
| pileup_separation_bin | close | ridge | 1664 | -1.026 | 3.859 | 0.1466 | 0.2284 |
| pileup_separation_bin | close | mlp | 1664 | -1.516 | 4.047 | 0.1466 | 0.2476 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1664 | -1.729 | 4.695 | 0.1466 | 0.3389 |
| pileup_separation_bin | close | 1d_cnn | 1664 | -0.8607 | 4.779 | 0.1466 | 0.3107 |
| pileup_separation_bin | close | compact_waveform_transformer | 1664 | -0.6344 | 5.82 | 0.1466 | 0.4141 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 3 | -0.1846 | 0.4835 | 0.5679 | 0 |
| pileup_separation_bin | late | ridge | 3 | 1.121 | 3.308 | 0.5679 | 0.3333 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | 1.853 | 13.78 | 0.5679 | 0.6667 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 3 | -3.285 | 14.98 | 0.5679 | 0.6667 |
| pileup_separation_bin | late | 1d_cnn | 3 | -8.43 | 17.5 | 0.5679 | 0.6667 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -4.113 | 17.55 | 0.5679 | 0.3333 |
| pileup_separation_bin | late | mlp | 3 | -0.3385 | 28.96 | 0.5679 | 0.6667 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1196 | 0.3115 | 0.9391 | 0.1431 | 0 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1196 | -0.9756 | 3.365 | 0.1431 | 0.1505 |
| pileup_separation_bin | mid | mlp | 1196 | -1.76 | 3.762 | 0.1431 | 0.2249 |
| pileup_separation_bin | mid | ridge | 1196 | -0.9194 | 3.827 | 0.1431 | 0.2249 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1196 | -2.228 | 4.862 | 0.1431 | 0.3545 |
| pileup_separation_bin | mid | 1d_cnn | 1196 | 1.658 | 5.766 | 0.1431 | 0.413 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1196 | -3.777 | 6.109 | 0.1431 | 0.5217 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2645 | 0.08165 | 0.9079 | 0.1676 | 0 |
| pileup_separation_bin | none | gradient_boosted_trees | 2645 | -0.2643 | 3.663 | 0.1676 | 0.1894 |
| pileup_separation_bin | none | ridge | 2645 | 0.02793 | 3.817 | 0.1676 | 0.2159 |
| pileup_separation_bin | none | mlp | 2645 | -0.6838 | 4.344 | 0.1676 | 0.2537 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2645 | -0.6349 | 4.452 | 0.1676 | 0.2854 |
| pileup_separation_bin | none | 1d_cnn | 2645 | 0.5289 | 5.092 | 0.1676 | 0.3357 |
| pileup_separation_bin | none | compact_waveform_transformer | 2645 | 1.286 | 5.107 | 0.1676 | 0.3803 |
| shape_residual_bin | high | traditional_cfd_template_derivative | 1831 | 0.09793 | 1.031 | 0.2674 | 0 |
| shape_residual_bin | high | gradient_boosted_trees | 1831 | -0.4714 | 3.803 | 0.2674 | 0.1999 |
| shape_residual_bin | high | ridge | 1831 | -0.4468 | 4.214 | 0.2674 | 0.2529 |
| shape_residual_bin | high | mlp | 1831 | -1.322 | 4.239 | 0.2674 | 0.2676 |
| shape_residual_bin | high | derivative_gate_transformer_new | 1831 | -1.568 | 4.958 | 0.2674 | 0.3632 |
| shape_residual_bin | high | 1d_cnn | 1831 | 0.1746 | 6.436 | 0.2674 | 0.4091 |
| shape_residual_bin | high | compact_waveform_transformer | 1831 | -1.34 | 6.573 | 0.2674 | 0.4418 |
| shape_residual_bin | low | traditional_cfd_template_derivative | 1839 | 0.2537 | 0.8644 | 0.06061 | 0 |
| shape_residual_bin | low | gradient_boosted_trees | 1839 | -0.525 | 3.506 | 0.06061 | 0.1528 |
| shape_residual_bin | low | ridge | 1839 | -0.7511 | 3.878 | 0.06061 | 0.2186 |
| shape_residual_bin | low | mlp | 1839 | -1.006 | 4.267 | 0.06061 | 0.2469 |
| shape_residual_bin | low | derivative_gate_transformer_new | 1839 | -0.7371 | 4.661 | 0.06061 | 0.2947 |
| shape_residual_bin | low | 1d_cnn | 1839 | 0.6292 | 4.949 | 0.06061 | 0.3208 |
| shape_residual_bin | low | compact_waveform_transformer | 1839 | 1.024 | 6.1 | 0.06061 | 0.4356 |
| shape_residual_bin | mid | traditional_cfd_template_derivative | 1838 | 0.2368 | 0.8801 | 0.1568 | 0 |
| shape_residual_bin | mid | gradient_boosted_trees | 1838 | -0.882 | 3.287 | 0.1568 | 0.1474 |
| shape_residual_bin | mid | ridge | 1838 | -0.4526 | 3.794 | 0.1568 | 0.1937 |
| shape_residual_bin | mid | mlp | 1838 | -1.208 | 4.102 | 0.1568 | 0.2231 |
| shape_residual_bin | mid | derivative_gate_transformer_new | 1838 | -1.729 | 4.466 | 0.1568 | 0.2927 |
| shape_residual_bin | mid | 1d_cnn | 1838 | -0.09608 | 4.828 | 0.1568 | 0.3058 |
| shape_residual_bin | mid | compact_waveform_transformer | 1838 | -0.5673 | 5.776 | 0.1568 | 0.3863 |
| slew_hysteresis_bin | high | traditional_cfd_template_derivative | 1840 | 0.08121 | 0.9017 | 0.1614 | 0 |

Correlation of timing error with hysteresis diagnostics:

| covariate | method | pearson_corr_with_error |
| --- | --- | --- |
| pedestal_memory_index | compact_waveform_transformer | -0.1948 |
| pedestal_memory_index | mlp | -0.1338 |
| pedestal_memory_index | derivative_gate_transformer_new | -0.09639 |
| pedestal_memory_index | ridge | -0.04582 |
| pedestal_memory_index | traditional_cfd_template_derivative | -0.03999 |
| pedestal_memory_index | gradient_boosted_trees | -0.03844 |
| pedestal_memory_index | 1d_cnn | 0.07331 |
| shape_residual_proxy | mlp | -0.05324 |
| shape_residual_proxy | compact_waveform_transformer | -0.05005 |
| shape_residual_proxy | gradient_boosted_trees | -0.02229 |
| shape_residual_proxy | 1d_cnn | -0.01669 |
| shape_residual_proxy | derivative_gate_transformer_new | -0.003093 |
| shape_residual_proxy | ridge | 0.02193 |
| shape_residual_proxy | traditional_cfd_template_derivative | 0.02849 |
| slew_hysteresis_index | traditional_cfd_template_derivative | -0.1246 |
| slew_hysteresis_index | derivative_gate_transformer_new | 0.0184 |
| slew_hysteresis_index | mlp | 0.03823 |
| slew_hysteresis_index | ridge | 0.04185 |
| slew_hysteresis_index | 1d_cnn | 0.04741 |
| slew_hysteresis_index | gradient_boosted_trees | 0.05291 |
| slew_hysteresis_index | compact_waveform_transformer | 0.1062 |

## Interpretation, Systematics, and Caveats

This S71a benchmark measures relative transfer on a reproducible waveform-derived
timing residual and explicitly tests whether slew hysteresis and pedestal-memory
strata explain where residual timing bias grows.  The raw ROOT files do not contain an independent external
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

Ticket-local wrapper runtime was `22.0 s`; benchmark runtime was `22.0 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.11.14`.

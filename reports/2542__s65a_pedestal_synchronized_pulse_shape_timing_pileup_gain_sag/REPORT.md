# S65a Pedestal-Synchronized Pulse-Shape Timing Under Pile-Up and Gain Sag

## Abstract

Ticket `#2542` asks whether a strong CFD/template timing baseline or
waveform ML better preserves leading-edge timing when pedestal memory,
late pile-up, saturation onset, and gain-sag proxies move between
run-held-out acquisition periods.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 0.8711 ns`
`[0.7351, 1.045]`.  The
traditional derivative comparator obtains `0.8711 ns`
`[0.7351, 1.045]`.


## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-3 --project testbeam` command was
run exactly once.  It returned the malformed null payload

```text
null
# null

null
```

without labeling a ticket for this worker.  Direct GitHub inspection showed
open `project:testbeam` tickets and no `worker:testbeam-laptop-3` issue.  To
bind exactly one ticket without running the helper a second time, issue
`#2542` was manually label-swapped using:

```text
gh issue edit 2542 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open
```

No other testbeam ticket was claimed in this worker.

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
generic waveform learning; it is that edge and curvature channels localize
leading-edge motion and late-tail deformation under pedestal drift,
pile-up, and gain-sag stress.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.1656 | -0.08103 | 0.5898 | 0.8711 | 0.7351 | 1.045 | 0.8928 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.9477 | -1.907 | -0.05497 | 3.571 | 3.112 | 3.96 | 4.873 | 0.1645 | 0.04427 |
| mlp | 5466 | -1.163 | -2.159 | -0.1789 | 4.049 | 3.751 | 4.645 | 5.029 | 0.2258 | 0.04336 |
| ridge | 5466 | -0.5713 | -1.408 | 0.16 | 4.096 | 3.614 | 4.7 | 5.213 | 0.2258 | 0.04281 |
| 1d_cnn | 5466 | -0.9448 | -1.74 | -0.3861 | 5.014 | 4.514 | 5.711 | 6.974 | 0.3216 | 0.09074 |
| compact_waveform_transformer | 5466 | 1.183 | 0.4934 | 1.753 | 5.55 | 5.114 | 6.295 | 6.695 | 0.3858 | 0.09715 |
| derivative_gate_transformer_new | 5466 | -0.5138 | -1.198 | 0.1153 | 6.315 | 5.876 | 7.334 | 7.508 | 0.4096 | 0.1445 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.7 | 2.198 | 3.136 | -1.113 | -2.184 | -0.1482 | 0.1645 |
| mlp | traditional_cfd_template_derivative | 3.178 | 2.822 | 3.776 | -1.329 | -2.369 | -0.3049 | 0.2258 |
| ridge | traditional_cfd_template_derivative | 3.224 | 2.712 | 3.881 | -0.7369 | -1.627 | 0.03714 | 0.2258 |
| 1d_cnn | traditional_cfd_template_derivative | 4.143 | 3.63 | 4.826 | -1.11 | -1.996 | -0.4749 | 0.3216 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 4.679 | 4.22 | 5.481 | 1.018 | 0.2262 | 1.602 | 0.3858 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 5.444 | 4.953 | 6.446 | -0.6794 | -1.49 | -0.04752 | 0.4096 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | 0.08391 | 0.8665 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.5866 | 3.798 | 0.2526 |
| sample_i_analysis | mlp | 1350 | 0.2526 | 4.795 | 0.297 |
| sample_i_analysis | ridge | 1350 | 0.4513 | 5.627 | 0.337 |
| sample_i_analysis | 1d_cnn | 1350 | -0.4618 | 6.502 | 0.4067 |
| sample_i_analysis | compact_waveform_transformer | 1350 | 1.597 | 6.98 | 0.4474 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | -0.4887 | 8.367 | 0.4748 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | -0.4252 | 1.25 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 0.8025 | 2.816 | 0.105 |
| sample_i_calib | mlp | 657 | 0.7768 | 3.437 | 0.1476 |
| sample_i_calib | ridge | 657 | 0.7529 | 4.053 | 0.239 |
| sample_i_calib | compact_waveform_transformer | 657 | 1.808 | 4.885 | 0.3607 |
| sample_i_calib | 1d_cnn | 657 | 0.04445 | 5.087 | 0.3242 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 0.3204 | 7.002 | 0.449 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.2974 | 0.8514 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.599 | 3.69 | 0.1552 |
| sample_ii_analysis | ridge | 2739 | -1.061 | 3.814 | 0.1862 |
| sample_ii_analysis | mlp | 2739 | -1.817 | 3.94 | 0.2253 |
| sample_ii_analysis | 1d_cnn | 2739 | -1.218 | 4.807 | 0.3001 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | 0.9982 | 5.545 | 0.3819 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | -0.6198 | 5.904 | 0.3892 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.8959 | 0.6401 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.827 | 2.78 | 0.08889 |
| sample_ii_calib | ridge | 720 | -1.616 | 3.203 | 0.1556 |
| sample_ii_calib | mlp | 720 | -2.406 | 3.542 | 0.1653 |
| sample_ii_calib | 1d_cnn | 720 | -1.679 | 4.073 | 0.2417 |
| sample_ii_calib | compact_waveform_transformer | 720 | 0.7041 | 4.714 | 0.3083 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | -0.9056 | 5.473 | 0.3292 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 0.04445 | 5.087 | 0.3242 |
| 1d_cnn | 50 | 680 | -0.9719 | 11.55 | 0.3897 |
| 1d_cnn | 57 | 670 | 0.3783 | 5.658 | 0.4239 |
| 1d_cnn | 58 | 654 | -3.358 | 5.025 | 0.4098 |
| 1d_cnn | 60 | 720 | 0.05739 | 4.699 | 0.2889 |
| 1d_cnn | 62 | 720 | -0.4581 | 4.495 | 0.25 |
| 1d_cnn | 64 | 720 | -1.679 | 4.073 | 0.2417 |
| 1d_cnn | 65 | 645 | -1.874 | 4.12 | 0.2574 |
| compact_waveform_transformer | 42 | 657 | 1.808 | 4.885 | 0.3607 |
| compact_waveform_transformer | 50 | 680 | 1.315 | 11.46 | 0.4706 |
| compact_waveform_transformer | 57 | 670 | 1.911 | 5.69 | 0.4239 |
| compact_waveform_transformer | 58 | 654 | -1.382 | 5.52 | 0.3869 |
| compact_waveform_transformer | 60 | 720 | 2.316 | 5.635 | 0.3931 |
| compact_waveform_transformer | 62 | 720 | 2.131 | 5.76 | 0.4319 |
| compact_waveform_transformer | 64 | 720 | 0.7041 | 4.714 | 0.3083 |
| compact_waveform_transformer | 65 | 645 | 0.6858 | 4.782 | 0.3085 |
| derivative_gate_transformer_new | 42 | 657 | 0.3204 | 7.002 | 0.449 |
| derivative_gate_transformer_new | 50 | 680 | -1.089 | 11.55 | 0.4765 |
| derivative_gate_transformer_new | 57 | 670 | 0.1366 | 6.628 | 0.4731 |
| derivative_gate_transformer_new | 58 | 654 | -2.206 | 6.185 | 0.4327 |
| derivative_gate_transformer_new | 60 | 720 | 0.5633 | 5.803 | 0.3778 |
| derivative_gate_transformer_new | 62 | 720 | 0.09223 | 5.951 | 0.3847 |
| derivative_gate_transformer_new | 64 | 720 | -0.9056 | 5.473 | 0.3292 |
| derivative_gate_transformer_new | 65 | 645 | -1.005 | 5.583 | 0.3628 |
| gradient_boosted_trees | 42 | 657 | 0.8025 | 2.816 | 0.105 |
| gradient_boosted_trees | 50 | 680 | 0.9827 | 10.5 | 0.3059 |
| gradient_boosted_trees | 57 | 670 | -0.1673 | 4.062 | 0.1985 |
| gradient_boosted_trees | 58 | 654 | -4.059 | 3.044 | 0.3058 |
| gradient_boosted_trees | 60 | 720 | -0.6641 | 3.223 | 0.1014 |
| gradient_boosted_trees | 62 | 720 | -1.309 | 3.417 | 0.09444 |
| gradient_boosted_trees | 64 | 720 | -1.827 | 2.78 | 0.08889 |
| gradient_boosted_trees | 65 | 645 | -2.087 | 2.646 | 0.1302 |
| mlp | 42 | 657 | 0.7768 | 3.437 | 0.1476 |
| mlp | 50 | 680 | 0.2662 | 10.18 | 0.3147 |
| mlp | 57 | 670 | 0.2228 | 4.722 | 0.2791 |
| mlp | 58 | 654 | -3.521 | 4.048 | 0.3578 |
| mlp | 60 | 720 | -0.9672 | 3.943 | 0.1722 |
| mlp | 62 | 720 | -1.262 | 4.149 | 0.2028 |
| mlp | 64 | 720 | -2.406 | 3.542 | 0.1653 |
| mlp | 65 | 645 | -2.273 | 3.415 | 0.1752 |
| ridge | 42 | 657 | 0.7529 | 4.053 | 0.239 |
| ridge | 50 | 680 | -0.05664 | 10.82 | 0.375 |
| ridge | 57 | 670 | 0.9898 | 4.782 | 0.2985 |
| ridge | 58 | 654 | -2.567 | 4.133 | 0.3089 |
| ridge | 60 | 720 | 0.08044 | 3.528 | 0.1389 |
| ridge | 62 | 720 | -0.1966 | 3.666 | 0.15 |
| ridge | 64 | 720 | -1.616 | 3.203 | 0.1556 |
| ridge | 65 | 645 | -1.318 | 3.256 | 0.155 |
| traditional_cfd_template_derivative | 42 | 657 | -0.4252 | 1.25 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | 0.07946 | 0.3026 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | 0.1314 | 1.098 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.5714 | 0.7252 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.05997 | 0.9783 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | -0.09618 | 0.7475 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.8959 | 0.6401 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.7104 | 0.8375 | 0 |

## Stratified Systematics

The requested strata are amplitude, energy/PID sideband, pedestal state,
pile-up spacing proxy, and saturation/gain-sag proxy.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1605 | -0.8292 | 5.909 | 0.3931 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1605 | -0.7202 | 5.891 | 0.3869 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1605 | -0.04861 | 6.553 | 0.4268 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1605 | -0.8362 | 3.613 | 0.1745 |
| curvature_energy_bin | curved | mlp | 1605 | -1.238 | 3.958 | 0.2405 |
| curvature_energy_bin | curved | ridge | 1605 | -0.8287 | 4.141 | 0.2355 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1605 | 0.1596 | 0.9356 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1946 | -0.6763 | 4.716 | 0.2939 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1946 | 2.598 | 5.603 | 0.4101 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1946 | 0.1898 | 6.867 | 0.4538 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1946 | -0.8365 | 3.598 | 0.165 |
| curvature_energy_bin | moderate | mlp | 1946 | -0.8442 | 4.056 | 0.2199 |
| curvature_energy_bin | moderate | ridge | 1946 | -0.7633 | 4.29 | 0.2282 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1946 | 0.1911 | 0.8344 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1915 | -1.531 | 4.675 | 0.2898 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1915 | 1.382 | 4.742 | 0.3603 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1915 | -1.224 | 5.739 | 0.3504 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1915 | -1.208 | 3.456 | 0.1556 |
| curvature_energy_bin | smooth | mlp | 1915 | -1.321 | 4.074 | 0.2193 |
| curvature_energy_bin | smooth | ridge | 1915 | -0.07826 | 3.985 | 0.2151 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1915 | 0.1472 | 0.8659 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1804 | -1.528 | 4.515 | 0.2816 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1804 | 1.095 | 5.451 | 0.3647 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1804 | -1.347 | 6.012 | 0.3797 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1804 | -1.261 | 3.111 | 0.1159 |
| derivative_onset_bin | nominal | mlp | 1804 | -1.491 | 3.602 | 0.2151 |
| derivative_onset_bin | nominal | ridge | 1804 | -1.048 | 3.78 | 0.1951 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1804 | 0.1651 | 0.8825 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1977 | -1.042 | 4.615 | 0.2787 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1977 | 1.353 | 5.404 | 0.3945 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1977 | -0.6869 | 5.762 | 0.3733 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1977 | -1.367 | 3.038 | 0.09762 |
| derivative_onset_bin | sharp | mlp | 1977 | -1.611 | 3.755 | 0.1937 |
| derivative_onset_bin | sharp | ridge | 1977 | -1.253 | 3.904 | 0.2099 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1977 | 0.3301 | 0.857 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1685 | -0.09032 | 6.754 | 0.4148 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1685 | 1.032 | 5.763 | 0.3982 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1685 | 0.6726 | 7.313 | 0.4843 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1685 | 0.2716 | 4.491 | 0.295 |
| derivative_onset_bin | slow | mlp | 1685 | -0.02227 | 4.476 | 0.2748 |
| derivative_onset_bin | slow | ridge | 1685 | 0.5716 | 4.313 | 0.2772 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1685 | 0.006424 | 0.8414 | 0 |
| energy_bin | q1_low | 1d_cnn | 1404 | -1.192 | 5.986 | 0.4031 |
| energy_bin | q1_low | compact_waveform_transformer | 1404 | 0.9301 | 5.093 | 0.3739 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1404 | -0.6964 | 6.829 | 0.4359 |
| energy_bin | q1_low | gradient_boosted_trees | 1404 | -1.073 | 3.744 | 0.183 |
| energy_bin | q1_low | mlp | 1404 | -1.173 | 3.976 | 0.2058 |
| energy_bin | q1_low | ridge | 1404 | 0.1768 | 4.052 | 0.2187 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1404 | -0.082 | 1.028 | 0 |
| energy_bin | q2 | 1d_cnn | 1509 | -1.042 | 4.555 | 0.277 |
| energy_bin | q2 | compact_waveform_transformer | 1509 | 2.26 | 4.947 | 0.3658 |
| energy_bin | q2 | derivative_gate_transformer_new | 1509 | -0.9675 | 5.932 | 0.3797 |
| energy_bin | q2 | gradient_boosted_trees | 1509 | -0.9546 | 3.582 | 0.1531 |
| energy_bin | q2 | mlp | 1509 | -1.559 | 4.246 | 0.2439 |
| energy_bin | q2 | ridge | 1509 | -0.6205 | 4.142 | 0.2346 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1509 | 0.2111 | 0.7997 | 0 |
| energy_bin | q3 | 1d_cnn | 1437 | -0.2972 | 4.604 | 0.2714 |
| energy_bin | q3 | compact_waveform_transformer | 1437 | 2.304 | 5.668 | 0.4426 |
| energy_bin | q3 | derivative_gate_transformer_new | 1437 | 0.9797 | 6.537 | 0.4537 |
| energy_bin | q3 | gradient_boosted_trees | 1437 | -0.9135 | 3.561 | 0.1489 |
| energy_bin | q3 | mlp | 1437 | -0.8772 | 4.014 | 0.2136 |
| energy_bin | q3 | ridge | 1437 | -0.8272 | 4.284 | 0.2331 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1437 | 0.2758 | 0.8228 | 0 |
| energy_bin | q4_high | 1d_cnn | 1116 | -1.712 | 4.81 | 0.3441 |
| energy_bin | q4_high | compact_waveform_transformer | 1116 | -1.472 | 5.337 | 0.3548 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1116 | -1.07 | 6.024 | 0.3602 |
| energy_bin | q4_high | gradient_boosted_trees | 1116 | -0.8259 | 3.389 | 0.1765 |
| energy_bin | q4_high | mlp | 1116 | -1.002 | 3.897 | 0.2419 |
| energy_bin | q4_high | ridge | 1116 | -1.002 | 3.925 | 0.2133 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1116 | 0.1835 | 0.9252 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3243 | -1.168 | 4.941 | 0.3281 |
| late_tail_morphology | compact | compact_waveform_transformer | 3243 | 1.122 | 5.598 | 0.3925 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3243 | -1.885 | 6.346 | 0.432 |
| late_tail_morphology | compact | gradient_boosted_trees | 3243 | -1.367 | 3.254 | 0.1283 |
| late_tail_morphology | compact | mlp | 3243 | -1.778 | 3.762 | 0.2069 |
| late_tail_morphology | compact | ridge | 3243 | -0.9287 | 4.08 | 0.2186 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3243 | 0.202 | 0.889 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 641 | -1.844 | 3.844 | 0.2559 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 641 | 0.3957 | 4.866 | 0.3058 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 641 | 1.104 | 4.077 | 0.2387 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 641 | -0.8898 | 3.162 | 0.117 |
| late_tail_morphology | diffuse_tail | mlp | 641 | -0.9236 | 3.954 | 0.2059 |
| late_tail_morphology | diffuse_tail | ridge | 641 | -1.397 | 3.674 | 0.181 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 641 | 0.264 | 0.8457 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 393 | -0.7671 | 6.033 | 0.3562 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 393 | 1.324 | 6.211 | 0.4173 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 393 | 0.1898 | 6.432 | 0.4402 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 393 | -0.9603 | 3.138 | 0.1399 |
| late_tail_morphology | late_derivative_bump | mlp | 393 | -1.31 | 3.892 | 0.2519 |
| late_tail_morphology | late_derivative_bump | ridge | 393 | 0.1107 | 3.595 | 0.2036 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 393 | 0.1208 | 0.8829 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1189 | 0.09219 | 5.136 | 0.328 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1189 | 1.802 | 5.303 | 0.4003 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1189 | 1.738 | 5.997 | 0.4306 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1189 | 0.5757 | 4.671 | 0.2969 |
| late_tail_morphology | late_rising_tail | mlp | 1189 | 0.2319 | 4.36 | 0.2792 |
| late_tail_morphology | late_rising_tail | ridge | 1189 | 0.687 | 4.131 | 0.2767 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1189 | 0.00972 | 0.8054 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1753 | -0.5847 | 6.138 | 0.4027 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1753 | -0.07773 | 6.276 | 0.4324 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1753 | -1.44 | 8.408 | 0.5282 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1753 | -0.7268 | 3.838 | 0.19 |
| pedestal_drift_bin | high | mlp | 1753 | -0.8625 | 4.156 | 0.2288 |
| pedestal_drift_bin | high | ridge | 1753 | -0.3589 | 4.192 | 0.2356 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1753 | 0.1017 | 0.9027 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1745 | -1.25 | 4.717 | 0.2917 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1745 | 1.396 | 5.069 | 0.3662 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1745 | -0.6716 | 5.521 | 0.3587 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1745 | -1.258 | 3.446 | 0.1553 |
| pedestal_drift_bin | low | mlp | 1745 | -1.45 | 3.94 | 0.2246 |
| pedestal_drift_bin | low | ridge | 1745 | -0.7727 | 4.094 | 0.235 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1745 | 0.2259 | 0.866 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1968 | -0.9478 | 4.528 | 0.2759 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1968 | 1.774 | 4.871 | 0.3618 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1968 | 0.03638 | 5.311 | 0.3491 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1968 | -0.9328 | 3.374 | 0.1499 |
| pedestal_drift_bin | mid | mlp | 1968 | -1.161 | 3.957 | 0.2241 |
| pedestal_drift_bin | mid | ridge | 1968 | -0.5622 | 3.964 | 0.2088 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1968 | 0.1603 | 0.851 | 0 |
| pid_sideband | central | 1d_cnn | 3747 | -1.033 | 4.645 | 0.2872 |
| pid_sideband | central | compact_waveform_transformer | 3747 | 1.71 | 4.949 | 0.3678 |
| pid_sideband | central | derivative_gate_transformer_new | 3747 | -0.363 | 5.585 | 0.3635 |
| pid_sideband | central | gradient_boosted_trees | 3747 | -0.9785 | 3.463 | 0.1585 |
| pid_sideband | central | mlp | 3747 | -1.052 | 4.014 | 0.2234 |
| pid_sideband | central | ridge | 3747 | -0.5619 | 4.159 | 0.2343 |
| pid_sideband | central | traditional_cfd_template_derivative | 3747 | 0.1466 | 0.8629 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 868 | -0.6516 | 8.013 | 0.5196 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 868 | -2.812 | 5.715 | 0.4459 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 868 | -5.81 | 9.51 | 0.7005 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 868 | -0.9969 | 4.118 | 0.2074 |
| pid_sideband | high_duplicate | mlp | 868 | -1.624 | 4.266 | 0.235 |
| pid_sideband | high_duplicate | ridge | 868 | -0.5097 | 4.207 | 0.2327 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 868 | 0.06555 | 0.8949 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 851 | -0.8926 | 4.631 | 0.2714 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 851 | 1.737 | 5.603 | 0.4042 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 851 | 1.422 | 4.999 | 0.3161 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 851 | -0.8089 | 3.525 | 0.1469 |
| pid_sideband | low_duplicate | mlp | 851 | -1.269 | 3.839 | 0.2268 |
| pid_sideband | low_duplicate | ridge | 851 | -0.6707 | 3.67 | 0.181 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 851 | 0.33 | 0.8641 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1722 | -1.789 | 4.916 | 0.3496 |
| pileup_separation_bin | close | compact_waveform_transformer | 1722 | 1.168 | 5.527 | 0.3676 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1722 | -0.9764 | 5.934 | 0.4071 |
| pileup_separation_bin | close | gradient_boosted_trees | 1722 | -1.243 | 3.207 | 0.1196 |
| pileup_separation_bin | close | mlp | 1722 | -1.463 | 3.758 | 0.2189 |
| pileup_separation_bin | close | ridge | 1722 | -1.303 | 3.954 | 0.2538 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1722 | 0.2387 | 0.8602 | 0 |
| pileup_separation_bin | late | 1d_cnn | 2 | -0.8961 | 1.194 | 0 |
| pileup_separation_bin | late | compact_waveform_transformer | 2 | -6.692 | 0.1527 | 1 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 2 | -7.809 | 0.7475 | 1 |
| pileup_separation_bin | late | gradient_boosted_trees | 2 | -0.9147 | 0.6197 | 0 |
| pileup_separation_bin | late | mlp | 2 | 1.874 | 0.6036 | 0 |
| pileup_separation_bin | late | ridge | 2 | 3.353 | 0.7746 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 2 | -1.111 | 0.4092 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1151 | -0.2341 | 5.088 | 0.3267 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1151 | -1.245 | 5.924 | 0.4196 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1151 | -3.171 | 7.509 | 0.5369 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1151 | -1.56 | 3.484 | 0.1329 |
| pileup_separation_bin | mid | mlp | 1151 | -1.778 | 3.866 | 0.2129 |
| pileup_separation_bin | mid | ridge | 1151 | -0.9099 | 3.921 | 0.2085 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1151 | 0.2871 | 0.8657 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2591 | -0.7756 | 4.821 | 0.301 |
| pileup_separation_bin | none | compact_waveform_transformer | 2591 | 1.98 | 4.652 | 0.3825 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2591 | 0.639 | 5.276 | 0.3543 |
| pileup_separation_bin | none | gradient_boosted_trees | 2591 | -0.5251 | 3.845 | 0.2084 |
| pileup_separation_bin | none | mlp | 2591 | -0.7288 | 4.019 | 0.2362 |
| pileup_separation_bin | none | ridge | 2591 | 0.03333 | 3.91 | 0.215 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2591 | 0.01935 | 0.8384 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1830 | -0.8231 | 6.166 | 0.4443 |
| pulse_shape_class | compact | compact_waveform_transformer | 1830 | 0.1099 | 5.927 | 0.4279 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1830 | -3.776 | 7.33 | 0.5639 |
| pulse_shape_class | compact | gradient_boosted_trees | 1830 | -1.787 | 3.555 | 0.1568 |
| pulse_shape_class | compact | mlp | 1830 | -1.855 | 4.118 | 0.2317 |
| pulse_shape_class | compact | ridge | 1830 | -0.4617 | 4.442 | 0.2694 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1830 | 0.176 | 0.9284 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1858 | -0.8234 | 4.921 | 0.3041 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1858 | 1.281 | 5.303 | 0.366 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1858 | 1.47 | 5.354 | 0.3617 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1858 | -0.1988 | 4.094 | 0.2314 |
| pulse_shape_class | late_tail | mlp | 1858 | -0.1828 | 4.234 | 0.2513 |
| pulse_shape_class | late_tail | ridge | 1858 | -0.1374 | 4.192 | 0.2443 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1858 | 0.1095 | 0.8076 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1778 | -1.214 | 4.176 | 0.2137 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1778 | 1.81 | 5.07 | 0.3633 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1778 | -0.4402 | 4.802 | 0.3009 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1778 | -1.145 | 2.937 | 0.1024 |
| pulse_shape_class | nominal | mlp | 1778 | -1.667 | 3.356 | 0.1929 |
| pulse_shape_class | nominal | ridge | 1778 | -1.087 | 3.573 | 0.1614 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1778 | 0.2019 | 0.858 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3957 | -1.021 | 5.312 | 0.3447 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3957 | 0.9232 | 5.723 | 0.4013 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3957 | -0.4415 | 6.632 | 0.4311 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3957 | -1.051 | 3.631 | 0.1701 |
| saturation_onset_bin | linear | mlp | 3957 | -1.239 | 4.111 | 0.229 |
| saturation_onset_bin | linear | ridge | 3957 | -0.6512 | 4.191 | 0.2343 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3957 | 0.2299 | 0.8818 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1509 | -0.8229 | 4.328 | 0.2611 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1509 | 1.755 | 5.071 | 0.3453 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1509 | -0.7059 | 5.633 | 0.3532 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1509 | -0.7985 | 3.373 | 0.1498 |
| saturation_onset_bin | near_saturation | mlp | 1509 | -0.8848 | 3.843 | 0.2174 |
| saturation_onset_bin | near_saturation | ridge | 1509 | -0.3958 | 3.895 | 0.2034 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1509 | 0.09108 | 0.8423 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.675 | curved | 5.909 | 1.234 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.742 | curved | 5.891 | 1.149 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 5.739 | moderate | 6.867 | 1.128 |
| curvature_energy_bin | ridge | 3 | smooth | 3.985 | moderate | 4.29 | 0.3046 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.456 | curved | 3.613 | 0.1565 |
| curvature_energy_bin | mlp | 3 | curved | 3.958 | smooth | 4.074 | 0.1157 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | moderate | 0.8344 | curved | 0.9356 | 0.1012 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.515 | slow | 6.754 | 2.239 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | sharp | 5.762 | slow | 7.313 | 1.551 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.038 | slow | 4.491 | 1.453 |
| derivative_onset_bin | mlp | 3 | nominal | 3.602 | slow | 4.476 | 0.8742 |
| derivative_onset_bin | ridge | 3 | nominal | 3.78 | slow | 4.313 | 0.5327 |
| derivative_onset_bin | compact_waveform_transformer | 3 | sharp | 5.404 | slow | 5.763 | 0.3588 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | slow | 0.8414 | nominal | 0.8825 | 0.04112 |
| energy_bin | 1d_cnn | 4 | q2 | 4.555 | q1_low | 5.986 | 1.431 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 5.932 | q1_low | 6.829 | 0.8968 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 4.947 | q3 | 5.668 | 0.7209 |
| energy_bin | ridge | 4 | q4_high | 3.925 | q3 | 4.284 | 0.3591 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.389 | q1_low | 3.744 | 0.3549 |
| energy_bin | mlp | 4 | q4_high | 3.897 | q2 | 4.246 | 0.3494 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.7997 | q1_low | 1.028 | 0.2281 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 4.077 | late_derivative_bump | 6.432 | 2.355 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 3.844 | late_derivative_bump | 6.033 | 2.189 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 3.138 | late_rising_tail | 4.671 | 1.533 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.866 | late_derivative_bump | 6.211 | 1.345 |
| late_tail_morphology | mlp | 4 | compact | 3.762 | late_rising_tail | 4.36 | 0.598 |
| late_tail_morphology | ridge | 4 | late_derivative_bump | 3.595 | late_rising_tail | 4.131 | 0.5358 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_rising_tail | 0.8054 | compact | 0.889 | 0.08355 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 5.311 | high | 8.408 | 3.097 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 4.528 | high | 6.138 | 1.61 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 4.871 | high | 6.276 | 1.405 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 3.374 | high | 3.838 | 0.4637 |
| pedestal_drift_bin | ridge | 3 | mid | 3.964 | high | 4.192 | 0.2286 |
| pedestal_drift_bin | mlp | 3 | low | 3.94 | high | 4.156 | 0.2161 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | mid | 0.851 | high | 0.9027 | 0.05168 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.999 | high_duplicate | 9.51 | 4.511 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 4.631 | high_duplicate | 8.013 | 3.382 |
| pid_sideband | compact_waveform_transformer | 3 | central | 4.949 | high_duplicate | 5.715 | 0.7656 |
| pid_sideband | gradient_boosted_trees | 3 | central | 3.463 | high_duplicate | 4.118 | 0.6549 |
| pid_sideband | ridge | 3 | low_duplicate | 3.67 | high_duplicate | 4.207 | 0.5368 |
| pid_sideband | mlp | 3 | low_duplicate | 3.839 | high_duplicate | 4.266 | 0.4273 |
| pid_sideband | traditional_cfd_template_derivative | 3 | central | 0.8629 | high_duplicate | 0.8949 | 0.03205 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | late | 0.7475 | mid | 7.509 | 6.761 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 0.1527 | mid | 5.924 | 5.771 |
| pileup_separation_bin | 1d_cnn | 4 | late | 1.194 | mid | 5.088 | 3.894 |
| pileup_separation_bin | mlp | 4 | late | 0.6036 | none | 4.019 | 3.416 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 0.6197 | none | 3.845 | 3.225 |
| pileup_separation_bin | ridge | 4 | late | 0.7746 | close | 3.954 | 3.18 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | late | 0.4092 | mid | 0.8657 | 0.4565 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.802 | compact | 7.33 | 2.528 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.176 | compact | 6.166 | 1.99 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.937 | late_tail | 4.094 | 1.157 |
| pulse_shape_class | mlp | 3 | nominal | 3.356 | late_tail | 4.234 | 0.8786 |
| pulse_shape_class | ridge | 3 | nominal | 3.573 | compact | 4.442 | 0.8685 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.07 | compact | 5.927 | 0.857 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | late_tail | 0.8076 | compact | 0.9284 | 0.1208 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 5.633 | linear | 6.632 | 0.999 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.328 | linear | 5.312 | 0.9843 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.071 | linear | 5.723 | 0.6511 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.895 | linear | 4.191 | 0.2964 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.843 | linear | 4.111 | 0.268 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.373 | linear | 3.631 | 0.2572 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.8423 | linear | 0.8818 | 0.03944 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.9128 | 3.594 | 3.14 | 3.941 | -0.008035 | 0.1652 |
| full_derivative_gradient_boosted_trees | 76 | -0.907 | 3.603 | 3.181 | 3.948 | 0 | 0.1634 |
| derivative_only | 43 | -0.5399 | 4.015 | 3.518 | 4.576 | 0.4127 | 0.228 |
| amplitude_cfd_no_derivative | 5 | -0.453 | 4.05 | 3.617 | 4.646 | 0.447 | 0.2263 |
| late_tail_curvature_window_only | 17 | -0.3139 | 4.422 | 3.955 | 5.035 | 0.8198 | 0.2664 |
| onset_derivative_window_only | 14 | -0.7408 | 4.893 | 4.182 | 6.061 | 1.29 | 0.3178 |
| pretrigger_derivative_only | 7 | -3.985 | 17.77 | 16.81 | 19.09 | 14.17 | 0.5831 |


## Ticket-Specific Diagnostic Files

`pedestal_pileup_gain_sag_timing_bias.csv` extracts the held-out timing-bias
tables for pedestal drift, pile-up spacing, saturation onset, energy, and
PID-sideband strata.  `systematic_axis_summary.csv` compresses the same axes to
best/worst strata by method.  `pulse_region_gain_sag_ablations.csv` isolates
whether onset derivatives, pretrigger derivatives, late-tail curvature, or
amplitude/CFD features carry the gain-sag and pile-up sensitivity.

## Interpretation, Systematics, and Caveats

This S65a benchmark measures relative transfer on a reproducible waveform-derived
timing residual.  It treats pretrigger baseline displacement as the
pedestal-memory proxy, late-tail morphology and post-peak structure as the
pile-up spacing proxy, and high-amplitude/saturation-onset strata as the
gain-sag stress proxy.  The raw ROOT files do not contain an independent external
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

Ticket-local wrapper runtime was `701.1 s`; benchmark runtime was `701.1 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29` with Python
`3.8.10`.

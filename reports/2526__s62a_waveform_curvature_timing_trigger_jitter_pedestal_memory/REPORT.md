# S62a Waveform-Curvature Timing Under Trigger Jitter and Pedestal Memory

## Abstract

Ticket `#2526` asks whether waveform curvature and derivative information
stabilize timing under trigger-phase jitter and pedestal-memory drift, and
whether waveform ML beats a strong constant-fraction/template baseline.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 1.02 ns`
`[0.7354, 1.229]`.  The
traditional derivative comparator obtains `1.02 ns`
`[0.7354, 1.229]`.



## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-2 --project testbeam` command was
run exactly once.  The local helper returned the malformed empty-existing-claim
payload

```text
null
# null

null
```

without moving an open issue.  Direct GitHub inspection showed `#2526` was the
oldest open `project:testbeam` issue.  To bind exactly one ticket without
running the helper a second time, `#2526` was label-swapped to
`factory:claimed worker:testbeam-laptop-2` using:

```text
gh issue edit 2526 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open
```

No second `tn-ticket claim` was run.

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

The traditional method starts from the audited constant-fraction plus
template cross-correlation baseline `hat y_0`.  Trigger jitter is measured
as the run-held-out onset residual after this baseline; pedestal memory is
encoded by the pretrigger level, pretrigger slope, and pretrigger
derivative RMS terms from samples 0--3.  The derivative/curvature residual
correction is fit on training runs only:

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
pulse-shape timing changes under pedestal drift.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.3571 | -0.1758 | 0.6328 | 1.02 | 0.7354 | 1.229 | 1.013 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.2694 | -1.334 | 0.7097 | 3.667 | 3.273 | 4.097 | 5.052 | 0.1753 | 0.04921 |
| ridge | 5466 | 0.1172 | -0.924 | 1.106 | 4.045 | 3.587 | 4.674 | 5.417 | 0.2309 | 0.05141 |
| mlp | 5466 | -0.09683 | -1.092 | 0.9671 | 4.159 | 3.891 | 4.544 | 5.53 | 0.2424 | 0.05818 |
| derivative_gate_transformer_new | 5466 | -0.3463 | -1.373 | 0.576 | 5.808 | 5.196 | 7.29 | 7.245 | 0.3666 | 0.1206 |
| compact_waveform_transformer | 5466 | 0.1514 | -0.959 | 1.369 | 5.929 | 5.482 | 6.739 | 7.318 | 0.3999 | 0.1131 |
| 1d_cnn | 5466 | -0.7997 | -2.153 | 0.7674 | 7.298 | 6.711 | 7.943 | 8.625 | 0.4892 | 0.1842 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.647 | 2.179 | 3.054 | -0.6265 | -1.726 | 0.4183 | 0.1753 |
| ridge | traditional_cfd_template_derivative | 3.024 | 2.538 | 3.685 | -0.2399 | -1.307 | 0.8177 | 0.2309 |
| mlp | traditional_cfd_template_derivative | 3.139 | 2.781 | 3.58 | -0.4539 | -1.568 | 0.6868 | 0.2424 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 4.788 | 4.119 | 6.259 | -0.7034 | -1.829 | 0.3907 | 0.3666 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 4.909 | 4.432 | 5.701 | -0.2056 | -1.4 | 1.016 | 0.3999 |
| 1d_cnn | traditional_cfd_template_derivative | 6.278 | 5.621 | 6.963 | -1.157 | -2.526 | 0.4467 | 0.4892 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.09371 | 1.041 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.1502 | 2.853 | 0.223 |
| sample_i_analysis | mlp | 1350 | 0.2682 | 3.983 | 0.2785 |
| sample_i_analysis | ridge | 1350 | 0.5116 | 5.09 | 0.3274 |
| sample_i_analysis | compact_waveform_transformer | 1350 | -0.6046 | 6.885 | 0.3748 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | 0.08565 | 7.546 | 0.4741 |
| sample_i_analysis | 1d_cnn | 1350 | -0.7461 | 8.53 | 0.5274 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | -0.7268 | 1.348 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 2.172 | 3.715 | 0.3105 |
| sample_i_calib | ridge | 657 | 3.229 | 4.734 | 0.347 |
| sample_i_calib | mlp | 657 | 2.868 | 4.805 | 0.3425 |
| sample_i_calib | compact_waveform_transformer | 657 | 2.55 | 5.717 | 0.3988 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 3.06 | 5.981 | 0.4018 |
| sample_i_calib | 1d_cnn | 657 | 3.22 | 8.33 | 0.5342 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.5412 | 0.8704 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.238 | 3.636 | 0.1417 |
| sample_ii_analysis | ridge | 2739 | -0.358 | 3.743 | 0.1804 |
| sample_ii_analysis | mlp | 2739 | -0.7083 | 4.157 | 0.2245 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | -0.6752 | 5.361 | 0.3264 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | 0.04178 | 6.203 | 0.4315 |
| sample_ii_analysis | 1d_cnn | 2739 | -1.257 | 6.885 | 0.467 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.8406 | 0.5358 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.292 | 3.057 | 0.09028 |
| sample_ii_calib | ridge | 720 | -0.8753 | 3.173 | 0.1361 |
| sample_ii_calib | mlp | 720 | -1.24 | 3.74 | 0.1514 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | -1.219 | 4.765 | 0.2861 |
| sample_ii_calib | compact_waveform_transformer | 720 | 0.3179 | 5.087 | 0.3278 |
| sample_ii_calib | 1d_cnn | 720 | -2.339 | 6.299 | 0.4611 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 3.22 | 8.33 | 0.5342 |
| 1d_cnn | 50 | 680 | -3.255 | 11.15 | 0.5294 |
| 1d_cnn | 57 | 670 | 1.892 | 7.792 | 0.5254 |
| 1d_cnn | 58 | 654 | -3.027 | 7.302 | 0.5443 |
| 1d_cnn | 60 | 720 | 0.5472 | 6.247 | 0.4403 |
| 1d_cnn | 62 | 720 | -0.793 | 6.74 | 0.4472 |
| 1d_cnn | 64 | 720 | -2.339 | 6.299 | 0.4611 |
| 1d_cnn | 65 | 645 | -1.988 | 6.243 | 0.4403 |
| compact_waveform_transformer | 42 | 657 | 2.55 | 5.717 | 0.3988 |
| compact_waveform_transformer | 50 | 680 | -1.954 | 10.99 | 0.3721 |
| compact_waveform_transformer | 57 | 670 | 1.107 | 5.569 | 0.3776 |
| compact_waveform_transformer | 58 | 654 | -2.433 | 5.912 | 0.4465 |
| compact_waveform_transformer | 60 | 720 | 1.794 | 5.936 | 0.4444 |
| compact_waveform_transformer | 62 | 720 | 0.288 | 6.478 | 0.4708 |
| compact_waveform_transformer | 64 | 720 | 0.3179 | 5.087 | 0.3278 |
| compact_waveform_transformer | 65 | 645 | 0.1267 | 5.327 | 0.3581 |
| derivative_gate_transformer_new | 42 | 657 | 3.06 | 5.981 | 0.4018 |
| derivative_gate_transformer_new | 50 | 680 | -2.446 | 12.52 | 0.5029 |
| derivative_gate_transformer_new | 57 | 670 | 1.118 | 6.183 | 0.4448 |
| derivative_gate_transformer_new | 58 | 654 | -2.236 | 5.719 | 0.3884 |
| derivative_gate_transformer_new | 60 | 720 | 0.4914 | 5.313 | 0.3014 |
| derivative_gate_transformer_new | 62 | 720 | -0.6426 | 5.328 | 0.3 |
| derivative_gate_transformer_new | 64 | 720 | -1.219 | 4.765 | 0.2861 |
| derivative_gate_transformer_new | 65 | 645 | -0.9158 | 4.912 | 0.3209 |
| gradient_boosted_trees | 42 | 657 | 2.172 | 3.715 | 0.3105 |
| gradient_boosted_trees | 50 | 680 | -0.145 | 9.999 | 0.2794 |
| gradient_boosted_trees | 57 | 670 | 0.6493 | 3.116 | 0.1657 |
| gradient_boosted_trees | 58 | 654 | -3.47 | 3.103 | 0.2569 |
| gradient_boosted_trees | 60 | 720 | 0.6362 | 3.441 | 0.1111 |
| gradient_boosted_trees | 62 | 720 | -1.248 | 3.653 | 0.1014 |
| gradient_boosted_trees | 64 | 720 | -1.292 | 3.057 | 0.09028 |
| gradient_boosted_trees | 65 | 645 | -1.415 | 3.19 | 0.1039 |
| mlp | 42 | 657 | 2.868 | 4.805 | 0.3425 |
| mlp | 50 | 680 | -0.577 | 9.816 | 0.2941 |
| mlp | 57 | 670 | 1.372 | 4.393 | 0.2627 |
| mlp | 58 | 654 | -2.504 | 4.052 | 0.2584 |
| mlp | 60 | 720 | 0.5358 | 3.968 | 0.2333 |
| mlp | 62 | 720 | -0.6448 | 4.294 | 0.2389 |
| mlp | 64 | 720 | -1.24 | 3.74 | 0.1514 |
| mlp | 65 | 645 | -0.9719 | 3.83 | 0.1643 |
| ridge | 42 | 657 | 3.229 | 4.734 | 0.347 |
| ridge | 50 | 680 | -1.112 | 10.4 | 0.3368 |
| ridge | 57 | 670 | 1.562 | 4.897 | 0.3179 |
| ridge | 58 | 654 | -2.074 | 4.198 | 0.2859 |
| ridge | 60 | 720 | 0.7135 | 3.245 | 0.1403 |
| ridge | 62 | 720 | -0.6774 | 3.812 | 0.1653 |
| ridge | 64 | 720 | -0.8753 | 3.173 | 0.1361 |
| ridge | 65 | 645 | -0.2883 | 3.46 | 0.1349 |
| traditional_cfd_template_derivative | 42 | 657 | -0.7268 | 1.348 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | -0.0674 | 0.673 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | -0.2091 | 1.4 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.6768 | 0.7017 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.3899 | 1.047 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.6844 | 0.4111 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.8406 | 0.5358 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.537 | 0.6997 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1594 | -0.1431 | 8.33 | 0.5433 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1594 | -2.598 | 6.192 | 0.4486 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1594 | -0.3359 | 6.119 | 0.3726 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1594 | -0.4182 | 3.577 | 0.1819 |
| curvature_energy_bin | curved | mlp | 1594 | -0.3332 | 4.203 | 0.2566 |
| curvature_energy_bin | curved | ridge | 1594 | -0.2988 | 4.16 | 0.2459 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1594 | 0.4354 | 1.166 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1920 | 1.132 | 6.212 | 0.4375 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1920 | 1.674 | 5.586 | 0.3875 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1920 | -0.6035 | 5.799 | 0.3755 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1920 | 0.02647 | 3.767 | 0.1839 |
| curvature_energy_bin | moderate | mlp | 1920 | 0.2104 | 4.233 | 0.251 |
| curvature_energy_bin | moderate | ridge | 1920 | -0.1835 | 4.138 | 0.238 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1920 | 0.4467 | 0.9429 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1952 | -3.155 | 6.109 | 0.4959 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1952 | 0.8864 | 4.973 | 0.3724 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1952 | -0.1257 | 5.466 | 0.353 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1952 | -0.3683 | 3.544 | 0.1614 |
| curvature_energy_bin | smooth | mlp | 1952 | -0.1447 | 3.978 | 0.2223 |
| curvature_energy_bin | smooth | ridge | 1952 | 0.9556 | 3.812 | 0.2116 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1952 | 0.2222 | 1.008 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1851 | -1.81 | 6.515 | 0.4652 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1851 | -0.07152 | 6.041 | 0.3976 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1851 | -0.601 | 5.421 | 0.3214 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1851 | -0.4903 | 3.211 | 0.1253 |
| derivative_onset_bin | nominal | mlp | 1851 | -0.6104 | 3.828 | 0.2069 |
| derivative_onset_bin | nominal | ridge | 1851 | -0.4755 | 3.743 | 0.1896 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1851 | 0.4375 | 1.054 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1934 | -1.208 | 6.733 | 0.4498 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1934 | 0.8536 | 6.045 | 0.4261 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1934 | -0.6207 | 5.185 | 0.3159 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1934 | -0.7721 | 3.083 | 0.1143 |
| derivative_onset_bin | sharp | mlp | 1934 | -0.785 | 3.842 | 0.2032 |
| derivative_onset_bin | sharp | ridge | 1934 | -0.5303 | 3.846 | 0.2068 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1934 | 0.4989 | 1.021 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1681 | 1.217 | 8.901 | 0.561 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1681 | -0.4114 | 5.768 | 0.3724 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1681 | 0.4125 | 7.642 | 0.4747 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1681 | 1.154 | 4.415 | 0.3004 |
| derivative_onset_bin | slow | mlp | 1681 | 1.514 | 4.408 | 0.3266 |
| derivative_onset_bin | slow | ridge | 1681 | 1.299 | 4.284 | 0.304 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1681 | 0.1143 | 1.017 | 0 |
| energy_bin | q1_low | 1d_cnn | 1423 | -3.037 | 7.959 | 0.5882 |
| energy_bin | q1_low | compact_waveform_transformer | 1423 | 0.6861 | 5.256 | 0.3781 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1423 | -0.7354 | 6.043 | 0.4062 |
| energy_bin | q1_low | gradient_boosted_trees | 1423 | -0.4139 | 3.655 | 0.1722 |
| energy_bin | q1_low | mlp | 1423 | 0.2428 | 3.933 | 0.2284 |
| energy_bin | q1_low | ridge | 1423 | 0.8829 | 3.848 | 0.2157 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1423 | 0.003039 | 1.103 | 0 |
| energy_bin | q2 | 1d_cnn | 1521 | -1.696 | 5.757 | 0.3945 |
| energy_bin | q2 | compact_waveform_transformer | 1521 | 1.798 | 5.014 | 0.3688 |
| energy_bin | q2 | derivative_gate_transformer_new | 1521 | -0.414 | 5.812 | 0.3695 |
| energy_bin | q2 | gradient_boosted_trees | 1521 | -0.1404 | 3.54 | 0.1729 |
| energy_bin | q2 | mlp | 1521 | -0.2103 | 4.298 | 0.2498 |
| energy_bin | q2 | ridge | 1521 | 0.3081 | 4.113 | 0.2268 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1521 | 0.4089 | 0.8908 | 0 |
| energy_bin | q3 | 1d_cnn | 1424 | 2.798 | 5.086 | 0.4565 |
| energy_bin | q3 | compact_waveform_transformer | 1424 | 1.16 | 6.189 | 0.4136 |
| energy_bin | q3 | derivative_gate_transformer_new | 1424 | -0.5868 | 5.818 | 0.3933 |
| energy_bin | q3 | gradient_boosted_trees | 1424 | -0.1267 | 3.751 | 0.1763 |
| energy_bin | q3 | mlp | 1424 | -0.1053 | 4.15 | 0.25 |
| energy_bin | q3 | ridge | 1424 | -0.1835 | 4.254 | 0.2591 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1424 | 0.511 | 0.9352 | 0 |
| energy_bin | q4_high | 1d_cnn | 1098 | -2.672 | 7.85 | 0.5346 |
| energy_bin | q4_high | compact_waveform_transformer | 1098 | -4.054 | 5.405 | 0.4536 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1098 | 0.9475 | 5.08 | 0.2769 |
| energy_bin | q4_high | gradient_boosted_trees | 1098 | -0.3785 | 3.445 | 0.1812 |
| energy_bin | q4_high | mlp | 1098 | -0.3759 | 3.896 | 0.2404 |
| energy_bin | q4_high | ridge | 1098 | -0.4551 | 4.005 | 0.2195 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1098 | 0.5336 | 1.217 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3280 | -1.377 | 6.916 | 0.4777 |
| late_tail_morphology | compact | compact_waveform_transformer | 3280 | 0.7443 | 5.888 | 0.4168 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3280 | -1.942 | 5.682 | 0.379 |
| late_tail_morphology | compact | gradient_boosted_trees | 3280 | -0.6831 | 3.327 | 0.1345 |
| late_tail_morphology | compact | mlp | 3280 | -0.7019 | 3.983 | 0.2116 |
| late_tail_morphology | compact | ridge | 3280 | -0.3629 | 3.969 | 0.2116 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3280 | 0.4236 | 1.031 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 592 | -1.574 | 6.111 | 0.4071 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 592 | -0.9162 | 5.494 | 0.3514 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 592 | 1.138 | 3.641 | 0.2297 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 592 | 0.2358 | 3.513 | 0.1689 |
| late_tail_morphology | diffuse_tail | mlp | 592 | 0.5125 | 4.239 | 0.2466 |
| late_tail_morphology | diffuse_tail | ridge | 592 | -0.3207 | 3.612 | 0.2027 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 592 | 0.6512 | 0.9312 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 373 | -2.672 | 8.685 | 0.6113 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 373 | -0.7555 | 7.082 | 0.4558 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 373 | 2.254 | 5.223 | 0.2949 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 373 | -0.6555 | 2.904 | 0.1206 |
| late_tail_morphology | late_derivative_bump | mlp | 373 | -0.6376 | 3.889 | 0.2466 |
| late_tail_morphology | late_derivative_bump | ridge | 373 | 0.1184 | 3.629 | 0.2252 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 373 | -0.06541 | 1.141 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1221 | 1.563 | 8.113 | 0.5225 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1221 | -0.4114 | 5.702 | 0.3612 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1221 | 1.663 | 6.172 | 0.4218 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1221 | 1.266 | 4.609 | 0.3047 |
| late_tail_morphology | late_rising_tail | mlp | 1221 | 1.552 | 4.576 | 0.3219 |
| late_tail_morphology | late_rising_tail | ridge | 1221 | 1.313 | 4.078 | 0.2981 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1221 | 0.09044 | 0.9952 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1724 | -0.4548 | 8.288 | 0.5447 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1724 | -0.7132 | 6.581 | 0.4461 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1724 | -2.199 | 7.099 | 0.4797 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1724 | -0.1688 | 3.907 | 0.2048 |
| pedestal_drift_bin | high | mlp | 1724 | 0.3018 | 4.356 | 0.2639 |
| pedestal_drift_bin | high | ridge | 1724 | 0.1791 | 4.136 | 0.2401 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1724 | 0.3605 | 1.062 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1800 | -1.01 | 7.04 | 0.4761 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1800 | 0.3055 | 5.633 | 0.3822 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1800 | 0.1336 | 5.213 | 0.3272 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1800 | -0.2889 | 3.453 | 0.16 |
| pedestal_drift_bin | low | mlp | 1800 | -0.3201 | 4.064 | 0.2361 |
| pedestal_drift_bin | low | ridge | 1800 | 0.07093 | 4.071 | 0.2406 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1800 | 0.3536 | 1.013 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1942 | -0.925 | 6.683 | 0.4521 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1942 | 0.7148 | 5.442 | 0.3754 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1942 | 0.17 | 4.912 | 0.3028 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1942 | -0.3053 | 3.631 | 0.1632 |
| pedestal_drift_bin | mid | mlp | 1942 | -0.2289 | 4.002 | 0.2291 |
| pedestal_drift_bin | mid | ridge | 1942 | 0.07156 | 3.917 | 0.2137 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1942 | 0.3569 | 1.006 | 0 |
| pid_sideband | central | 1d_cnn | 3755 | -0.7875 | 6.983 | 0.4628 |
| pid_sideband | central | compact_waveform_transformer | 3755 | 0.7336 | 5.509 | 0.3779 |
| pid_sideband | central | derivative_gate_transformer_new | 3755 | 0.1338 | 5.243 | 0.3284 |
| pid_sideband | central | gradient_boosted_trees | 3755 | -0.237 | 3.592 | 0.1704 |
| pid_sideband | central | mlp | 3755 | -0.09319 | 4.068 | 0.2365 |
| pid_sideband | central | ridge | 3755 | 0.2775 | 4.025 | 0.2312 |
| pid_sideband | central | traditional_cfd_template_derivative | 3755 | 0.3098 | 1.015 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 877 | -0.2349 | 9.583 | 0.618 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 877 | -3.152 | 6.968 | 0.4892 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 877 | -6.247 | 6.559 | 0.6454 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 877 | -0.601 | 3.98 | 0.2098 |
| pid_sideband | high_duplicate | mlp | 877 | 0.2025 | 4.422 | 0.2748 |
| pid_sideband | high_duplicate | ridge | 877 | -0.1953 | 4.371 | 0.2566 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 877 | 0.4682 | 1.068 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 834 | -1.242 | 6.707 | 0.4724 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 834 | 0.06196 | 6.044 | 0.4053 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 834 | 0.9225 | 4.055 | 0.2458 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 834 | -0.179 | 3.503 | 0.1607 |
| pid_sideband | low_duplicate | mlp | 834 | -0.3197 | 4.16 | 0.235 |
| pid_sideband | low_duplicate | ridge | 834 | -0.2981 | 3.748 | 0.2026 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 834 | 0.4776 | 1.057 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1654 | -1.992 | 6.903 | 0.468 |
| pileup_separation_bin | close | compact_waveform_transformer | 1654 | -0.1547 | 6.043 | 0.4015 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1654 | -0.6343 | 5.394 | 0.3283 |
| pileup_separation_bin | close | gradient_boosted_trees | 1654 | -0.5066 | 3.225 | 0.13 |
| pileup_separation_bin | close | mlp | 1654 | -0.6794 | 3.984 | 0.2189 |
| pileup_separation_bin | close | ridge | 1654 | -0.6287 | 3.712 | 0.2152 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1654 | 0.5104 | 1.079 | 0 |
| pileup_separation_bin | late | 1d_cnn | 6 | -14.1 | 15.88 | 1 |
| pileup_separation_bin | late | compact_waveform_transformer | 6 | -10.77 | 13.27 | 0.8333 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 6 | -8.43 | 10.58 | 0.5 |
| pileup_separation_bin | late | gradient_boosted_trees | 6 | -5.22 | 4.195 | 0.6667 |
| pileup_separation_bin | late | mlp | 6 | -10.84 | 23.33 | 0.6667 |
| pileup_separation_bin | late | ridge | 6 | -0.8627 | 4.069 | 0.1667 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 6 | -0.09093 | 1.249 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1173 | 1.753 | 6.953 | 0.5192 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1173 | -2.455 | 6.295 | 0.4459 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1173 | -3.52 | 6.602 | 0.4697 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1173 | -0.7919 | 3.535 | 0.1552 |
| pileup_separation_bin | mid | mlp | 1173 | -0.6367 | 4.187 | 0.237 |
| pileup_separation_bin | mid | ridge | 1173 | -0.4159 | 4.399 | 0.2532 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1173 | 0.5713 | 1.083 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2633 | -1.325 | 7.234 | 0.488 |
| pileup_separation_bin | none | compact_waveform_transformer | 2633 | 1.213 | 5.246 | 0.3775 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2633 | 0.686 | 5.346 | 0.3445 |
| pileup_separation_bin | none | gradient_boosted_trees | 2633 | 0.2872 | 3.782 | 0.2115 |
| pileup_separation_bin | none | mlp | 2633 | 0.5987 | 4.1 | 0.2586 |
| pileup_separation_bin | none | ridge | 2633 | 0.907 | 3.75 | 0.2309 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2633 | 0.1905 | 0.9819 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1866 | -1.872 | 7.588 | 0.5177 |
| pulse_shape_class | compact | compact_waveform_transformer | 1866 | 0.6232 | 6.135 | 0.4571 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1866 | -4.394 | 5.987 | 0.5166 |
| pulse_shape_class | compact | gradient_boosted_trees | 1866 | -1.008 | 3.681 | 0.1592 |
| pulse_shape_class | compact | mlp | 1866 | -0.6067 | 4.192 | 0.2337 |
| pulse_shape_class | compact | ridge | 1866 | 0.06157 | 4.323 | 0.2487 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1866 | 0.4128 | 1.028 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1834 | 0.248 | 7.427 | 0.4842 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1834 | -0.5654 | 5.566 | 0.3555 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1834 | 1.422 | 5.242 | 0.3571 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1834 | 0.8382 | 4.179 | 0.259 |
| pulse_shape_class | late_tail | mlp | 1834 | 1.191 | 4.409 | 0.2972 |
| pulse_shape_class | late_tail | ridge | 1834 | 0.7633 | 3.954 | 0.2655 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1834 | 0.274 | 0.9782 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1766 | -1.073 | 6.475 | 0.4643 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1766 | 0.5812 | 5.758 | 0.3856 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1766 | 0.05747 | 4.342 | 0.218 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1766 | -0.4924 | 2.954 | 0.1053 |
| pulse_shape_class | nominal | mlp | 1766 | -0.7579 | 3.595 | 0.1948 |
| pulse_shape_class | nominal | ridge | 1766 | -0.5093 | 3.631 | 0.1761 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1766 | 0.3755 | 1.051 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3942 | -0.4592 | 7.607 | 0.5109 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3942 | 0.02638 | 6.018 | 0.4064 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3942 | -0.566 | 6.08 | 0.394 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3942 | -0.3323 | 3.74 | 0.1781 |
| saturation_onset_bin | linear | mlp | 3942 | -0.07304 | 4.164 | 0.2448 |
| saturation_onset_bin | linear | ridge | 3942 | 0.1225 | 4.172 | 0.2392 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3942 | 0.4144 | 1.032 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1524 | -1.825 | 6.28 | 0.4331 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1524 | 0.6704 | 5.736 | 0.3832 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1524 | 0.2771 | 5.015 | 0.2959 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1524 | -0.1558 | 3.45 | 0.168 |
| saturation_onset_bin | near_saturation | mlp | 1524 | -0.1563 | 4.114 | 0.2362 |
| saturation_onset_bin | near_saturation | ridge | 1524 | 0.07141 | 3.691 | 0.2093 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1524 | 0.2512 | 1.002 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 6.109 | curved | 8.33 | 2.221 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.973 | curved | 6.192 | 1.218 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 5.466 | curved | 6.119 | 0.6523 |
| curvature_energy_bin | ridge | 3 | smooth | 3.812 | curved | 4.16 | 0.3478 |
| curvature_energy_bin | mlp | 3 | smooth | 3.978 | moderate | 4.233 | 0.2549 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | moderate | 0.9429 | curved | 1.166 | 0.2232 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.544 | moderate | 3.767 | 0.223 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | sharp | 5.185 | slow | 7.642 | 2.457 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 6.515 | slow | 8.901 | 2.387 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.083 | slow | 4.415 | 1.332 |
| derivative_onset_bin | mlp | 3 | nominal | 3.828 | slow | 4.408 | 0.5796 |
| derivative_onset_bin | ridge | 3 | nominal | 3.743 | slow | 4.284 | 0.5404 |
| derivative_onset_bin | compact_waveform_transformer | 3 | slow | 5.768 | sharp | 6.045 | 0.2768 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | slow | 1.017 | nominal | 1.054 | 0.03653 |
| energy_bin | 1d_cnn | 4 | q3 | 5.086 | q1_low | 7.959 | 2.873 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 5.014 | q3 | 6.189 | 1.175 |
| energy_bin | derivative_gate_transformer_new | 4 | q4_high | 5.08 | q1_low | 6.043 | 0.963 |
| energy_bin | ridge | 4 | q1_low | 3.848 | q3 | 4.254 | 0.4057 |
| energy_bin | mlp | 4 | q4_high | 3.896 | q2 | 4.298 | 0.4021 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.8908 | q4_high | 1.217 | 0.3265 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.445 | q3 | 3.751 | 0.3057 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 6.111 | late_derivative_bump | 8.685 | 2.574 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 3.641 | late_rising_tail | 6.172 | 2.532 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 2.904 | late_rising_tail | 4.609 | 1.706 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 5.494 | late_derivative_bump | 7.082 | 1.588 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.889 | late_rising_tail | 4.576 | 0.6866 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.612 | late_rising_tail | 4.078 | 0.4658 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | diffuse_tail | 0.9312 | late_derivative_bump | 1.141 | 0.2099 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.912 | high | 7.099 | 2.187 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 6.683 | high | 8.288 | 1.605 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.442 | high | 6.581 | 1.139 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.453 | high | 3.907 | 0.4539 |
| pedestal_drift_bin | mlp | 3 | mid | 4.002 | high | 4.356 | 0.3545 |
| pedestal_drift_bin | ridge | 3 | mid | 3.917 | high | 4.136 | 0.2187 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | mid | 1.006 | high | 1.062 | 0.05579 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 6.707 | high_duplicate | 9.583 | 2.876 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.055 | high_duplicate | 6.559 | 2.505 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.509 | high_duplicate | 6.968 | 1.459 |
| pid_sideband | ridge | 3 | low_duplicate | 3.748 | high_duplicate | 4.371 | 0.6233 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.503 | high_duplicate | 3.98 | 0.4769 |
| pid_sideband | mlp | 3 | central | 4.068 | high_duplicate | 4.422 | 0.3548 |
| pid_sideband | traditional_cfd_template_derivative | 3 | central | 1.015 | high_duplicate | 1.068 | 0.0525 |
| pileup_separation_bin | mlp | 4 | close | 3.984 | late | 23.33 | 19.34 |
| pileup_separation_bin | 1d_cnn | 4 | close | 6.903 | late | 15.88 | 8.981 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 5.246 | late | 13.27 | 8.024 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | none | 5.346 | late | 10.58 | 5.237 |
| pileup_separation_bin | gradient_boosted_trees | 4 | close | 3.225 | late | 4.195 | 0.9698 |
| pileup_separation_bin | ridge | 4 | close | 3.712 | mid | 4.399 | 0.6867 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | none | 0.9819 | late | 1.249 | 0.2666 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.342 | compact | 5.987 | 1.646 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.954 | late_tail | 4.179 | 1.225 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 6.475 | compact | 7.588 | 1.113 |
| pulse_shape_class | mlp | 3 | nominal | 3.595 | late_tail | 4.409 | 0.8135 |
| pulse_shape_class | ridge | 3 | nominal | 3.631 | compact | 4.323 | 0.6918 |
| pulse_shape_class | compact_waveform_transformer | 3 | late_tail | 5.566 | compact | 6.135 | 0.5692 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | late_tail | 0.9782 | nominal | 1.051 | 0.07316 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 6.28 | linear | 7.607 | 1.327 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 5.015 | linear | 6.08 | 1.065 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.691 | linear | 4.172 | 0.4807 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.45 | linear | 3.74 | 0.2903 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.736 | linear | 6.018 | 0.2824 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.114 | linear | 4.164 | 0.05019 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 1.002 | linear | 1.032 | 0.02961 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.2374 | 3.651 | 3.197 | 4.048 | -0.02788 | 0.1802 |
| full_derivative_gradient_boosted_trees | 76 | -0.2156 | 3.679 | 3.314 | 4.087 | 0 | 0.1822 |
| derivative_only | 43 | -0.03666 | 4.05 | 3.538 | 4.601 | 0.3714 | 0.2377 |
| amplitude_cfd_no_derivative | 5 | 0.06649 | 4.073 | 3.627 | 4.77 | 0.3941 | 0.2333 |
| late_tail_curvature_window_only | 17 | 0.1972 | 4.522 | 4.122 | 5.048 | 0.8438 | 0.2825 |
| onset_derivative_window_only | 14 | 0.02688 | 4.819 | 4.102 | 6.429 | 1.141 | 0.3085 |
| pretrigger_derivative_only | 7 | -3.288 | 18.56 | 17.1 | 19.44 | 14.88 | 0.5779 |

## Interpretation, Systematics, and Caveats

This S62a benchmark measures relative transfer on a reproducible
waveform-derived timing residual.  It treats trigger jitter as a held-out
run residual process and tests whether waveform curvature, pile-up strata,
saturation flags, pedestal state, reconstructed-energy proxies, and PID
boundary diagnostics change the method ranking.  The raw ROOT files do not contain an independent external
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

Ticket-local wrapper runtime was `614.6 s`; benchmark runtime was `614.5 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.

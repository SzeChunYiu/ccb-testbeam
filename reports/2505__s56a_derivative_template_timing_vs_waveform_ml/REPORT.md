# S56a Derivative-Template Timing vs Waveform ML

## Abstract

Ticket `#2505` asks how pedestal-memory drift changes pulse shape and
timing estimates across runs and amplitudes, and whether waveform ML
beats a strong derivative-enhanced template timing baseline.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 0.8822 ns`
`[0.7484, 1.094]`.  The
traditional derivative comparator obtains `0.8822 ns`
`[0.7484, 1.094]`.


## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once.  The local helper returned the malformed empty-existing-claim
payload

```text
null
# null

null
```

without moving an open issue.  Direct read-only GitHub inspection showed issue
`#2505` still labeled `factory:open project:testbeam` and no valid
`worker:testbeam-laptop-1` claimed issue.  To bind exactly one ticket without
running the helper a second time, `#2505` was manually label-swapped to
`factory:claimed worker:testbeam-laptop-1` using:

```text
gh issue edit 2505 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
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
`hat y_0`.  The pretrigger pedestal is summarized by the four raw samples
`p_t = x_t` for `t in {0,1,2,3}` and the AR(1) memory proxy
`rho_hat = sum_t (p_t-bar p)(p_{t-1}-bar p) / sum_t (p_{t-1}-bar p)^2`,
implemented here through the baseline level, pretrigger slope, and
pretrigger derivative RMS terms available in the 18-sample waveform.  A
ridge-regularized derivative residual correction is fit on training runs
only:

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
| traditional_cfd_template_derivative | 5466 | 0.2667 | -0.2148 | 0.7031 | 0.8822 | 0.7484 | 1.094 | 0.891 | 0.0001829 | 0 |
| gradient_boosted_trees | 5466 | -0.07005 | -1.104 | 0.6829 | 3.9 | 2.904 | 4.843 | 5.303 | 0.2205 | 0.04885 |
| ridge | 5466 | 0.004338 | -0.8474 | 1.132 | 4.035 | 3.282 | 4.97 | 5.448 | 0.2402 | 0.05013 |
| mlp | 5466 | -0.5898 | -1.765 | 0.3988 | 4.368 | 3.593 | 5.241 | 5.47 | 0.2556 | 0.05013 |
| compact_waveform_transformer | 5466 | -0.3712 | -1.192 | 0.3223 | 5.43 | 5.007 | 6.353 | 6.87 | 0.3524 | 0.09623 |
| 1d_cnn | 5466 | 1.804 | 1.025 | 2.843 | 6.107 | 5.349 | 7.15 | 8.035 | 0.4325 | 0.1566 |
| derivative_gate_transformer_new | 5466 | 2.082 | 1.502 | 2.63 | 6.359 | 5.686 | 7.69 | 7.744 | 0.4541 | 0.1407 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 3.018 | 1.938 | 3.936 | -0.3367 | -1.561 | 0.6624 | 0.2203 |
| ridge | traditional_cfd_template_derivative | 3.153 | 2.406 | 4.145 | -0.2623 | -1.243 | 0.965 | 0.24 |
| mlp | traditional_cfd_template_derivative | 3.486 | 2.672 | 4.424 | -0.8565 | -2.097 | 0.1781 | 0.2554 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 4.548 | 4.07 | 5.489 | -0.6379 | -1.5 | 0.2119 | 0.3522 |
| 1d_cnn | traditional_cfd_template_derivative | 5.225 | 4.493 | 6.248 | 1.538 | 0.617 | 2.733 | 0.4323 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 5.476 | 4.761 | 6.784 | 1.815 | 1.08 | 2.529 | 0.4539 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.3426 | 0.7844 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.8615 | 3.26 | 0.2748 |
| sample_i_analysis | mlp | 1350 | 0.4498 | 4.209 | 0.2926 |
| sample_i_analysis | ridge | 1350 | 1.089 | 5.043 | 0.34 |
| sample_i_analysis | compact_waveform_transformer | 1350 | -0.47 | 6.3 | 0.357 |
| sample_i_analysis | 1d_cnn | 1350 | 2.497 | 8.22 | 0.52 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | 2.219 | 8.581 | 0.5719 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | -0.236 | 1.156 | 0.001522 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.478 | 4.076 | 0.2892 |
| sample_i_calib | ridge | 657 | 2.656 | 4.651 | 0.3638 |
| sample_i_calib | mlp | 657 | 1.753 | 4.967 | 0.3044 |
| sample_i_calib | compact_waveform_transformer | 657 | 1.172 | 5.487 | 0.3364 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 4.323 | 5.974 | 0.5205 |
| sample_i_calib | 1d_cnn | 657 | 4.097 | 7.332 | 0.5053 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.7031 | 0.7581 | 0 |
| sample_ii_analysis | ridge | 2739 | -0.9067 | 3.771 | 0.2052 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.462 | 4.101 | 0.2253 |
| sample_ii_analysis | mlp | 2739 | -1.834 | 4.559 | 0.2782 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | -0.8875 | 5.652 | 0.3709 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | 1.716 | 5.741 | 0.402 |
| sample_ii_analysis | 1d_cnn | 2739 | 1.308 | 5.748 | 0.3987 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.04802 | 0.8677 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -0.2624 | 2.132 | 0.0375 |
| sample_ii_calib | ridge | 720 | -0.2468 | 2.65 | 0.07361 |
| sample_ii_calib | mlp | 720 | -0.7911 | 2.886 | 0.05556 |
| sample_ii_calib | compact_waveform_transformer | 720 | -0.03308 | 4.544 | 0.2875 |
| sample_ii_calib | 1d_cnn | 720 | 1.509 | 4.834 | 0.3306 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | 2.296 | 5.361 | 0.3708 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 4.097 | 7.332 | 0.5053 |
| 1d_cnn | 50 | 680 | 0.3173 | 11.37 | 0.5103 |
| 1d_cnn | 57 | 670 | 4.625 | 6.591 | 0.5299 |
| 1d_cnn | 58 | 654 | -0.151 | 6.432 | 0.4526 |
| 1d_cnn | 60 | 720 | 2.442 | 5.032 | 0.4056 |
| 1d_cnn | 62 | 720 | 1.149 | 5.251 | 0.3333 |
| 1d_cnn | 64 | 720 | 1.509 | 4.834 | 0.3306 |
| 1d_cnn | 65 | 645 | 1.333 | 5.391 | 0.4093 |
| compact_waveform_transformer | 42 | 657 | 1.172 | 5.487 | 0.3364 |
| compact_waveform_transformer | 50 | 680 | -1.288 | 11.86 | 0.3838 |
| compact_waveform_transformer | 57 | 670 | 0.8649 | 5.24 | 0.3299 |
| compact_waveform_transformer | 58 | 654 | -2.718 | 6.44 | 0.4771 |
| compact_waveform_transformer | 60 | 720 | 0.05987 | 5.376 | 0.3611 |
| compact_waveform_transformer | 62 | 720 | -1.156 | 4.97 | 0.3139 |
| compact_waveform_transformer | 64 | 720 | -0.03308 | 4.544 | 0.2875 |
| compact_waveform_transformer | 65 | 645 | 0.02349 | 5.157 | 0.338 |
| derivative_gate_transformer_new | 42 | 657 | 4.323 | 5.974 | 0.5205 |
| derivative_gate_transformer_new | 50 | 680 | 0.9234 | 13.97 | 0.65 |
| derivative_gate_transformer_new | 57 | 670 | 3.531 | 6.231 | 0.4925 |
| derivative_gate_transformer_new | 58 | 654 | 0.2766 | 6.408 | 0.4297 |
| derivative_gate_transformer_new | 60 | 720 | 2.404 | 5.748 | 0.4319 |
| derivative_gate_transformer_new | 62 | 720 | 1.332 | 5.41 | 0.3625 |
| derivative_gate_transformer_new | 64 | 720 | 2.296 | 5.361 | 0.3708 |
| derivative_gate_transformer_new | 65 | 645 | 1.77 | 5.487 | 0.3845 |
| gradient_boosted_trees | 42 | 657 | 1.478 | 4.076 | 0.2892 |
| gradient_boosted_trees | 50 | 680 | 0.6533 | 10.98 | 0.2956 |
| gradient_boosted_trees | 57 | 670 | 1.205 | 3.536 | 0.2537 |
| gradient_boosted_trees | 58 | 654 | -3.831 | 4.822 | 0.3899 |
| gradient_boosted_trees | 60 | 720 | -0.2912 | 3.534 | 0.1028 |
| gradient_boosted_trees | 62 | 720 | -1.558 | 2.604 | 0.08472 |
| gradient_boosted_trees | 64 | 720 | -0.2624 | 2.132 | 0.0375 |
| gradient_boosted_trees | 65 | 645 | -1.583 | 5.084 | 0.3519 |
| mlp | 42 | 657 | 1.753 | 4.967 | 0.3044 |
| mlp | 50 | 680 | -0.2409 | 10.42 | 0.3088 |
| mlp | 57 | 670 | 1.384 | 4.459 | 0.2761 |
| mlp | 58 | 654 | -3.633 | 5.7 | 0.4373 |
| mlp | 60 | 720 | -0.7655 | 4.062 | 0.1972 |
| mlp | 62 | 720 | -1.56 | 3.525 | 0.1069 |
| mlp | 64 | 720 | -0.7911 | 2.886 | 0.05556 |
| mlp | 65 | 645 | -2.268 | 5.598 | 0.3984 |
| ridge | 42 | 657 | 2.656 | 4.651 | 0.3638 |
| ridge | 50 | 680 | -0.2504 | 11.24 | 0.3618 |
| ridge | 57 | 670 | 2.479 | 4.674 | 0.3179 |
| ridge | 58 | 654 | -2.069 | 4.68 | 0.3563 |
| ridge | 60 | 720 | -0.3238 | 2.973 | 0.1056 |
| ridge | 62 | 720 | -1.257 | 3.216 | 0.1347 |
| ridge | 64 | 720 | -0.2468 | 2.65 | 0.07361 |
| ridge | 65 | 645 | -0.6192 | 4.312 | 0.2419 |
| traditional_cfd_template_derivative | 42 | 657 | -0.236 | 1.156 | 0.001522 |
| traditional_cfd_template_derivative | 50 | 680 | -0.2202 | 0.4371 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | -0.608 | 1.128 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.6931 | 0.5277 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | 0.004294 | 0.6711 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.8752 | 0.8406 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.04802 | 0.8677 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.8254 | 0.3908 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1575 | 1.394 | 7.503 | 0.5117 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1575 | -2.497 | 5.428 | 0.4267 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1575 | 3.079 | 7.005 | 0.5663 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1575 | -0.2481 | 3.926 | 0.2286 |
| curvature_energy_bin | curved | mlp | 1575 | -0.543 | 4.224 | 0.2559 |
| curvature_energy_bin | curved | ridge | 1575 | -0.4132 | 4.211 | 0.2444 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1575 | 0.2687 | 0.9635 | 0.0006349 |
| curvature_energy_bin | moderate | 1d_cnn | 1955 | 3.39 | 5.34 | 0.4885 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1955 | 0.9011 | 5.366 | 0.3504 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1955 | 2.226 | 6.334 | 0.4501 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1955 | 0.1378 | 3.98 | 0.2302 |
| curvature_energy_bin | moderate | mlp | 1955 | -0.2319 | 4.48 | 0.2655 |
| curvature_energy_bin | moderate | ridge | 1955 | -0.3157 | 4.12 | 0.2445 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1955 | 0.3817 | 0.8062 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1936 | 0.4839 | 4.871 | 0.3115 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1936 | 0.2305 | 4.722 | 0.2939 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1936 | 1.419 | 5.436 | 0.3667 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1936 | -0.1975 | 3.79 | 0.204 |
| curvature_energy_bin | smooth | mlp | 1936 | -1.015 | 4.277 | 0.2454 |
| curvature_energy_bin | smooth | ridge | 1936 | 0.6536 | 3.947 | 0.2324 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1936 | 0.124 | 0.8741 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1859 | 1.262 | 5.261 | 0.3615 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1859 | -0.3573 | 5.109 | 0.3276 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1859 | 2.226 | 5.837 | 0.4314 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1859 | -0.3221 | 3.544 | 0.198 |
| derivative_onset_bin | nominal | mlp | 1859 | -1.102 | 4.039 | 0.2351 |
| derivative_onset_bin | nominal | ridge | 1859 | -0.3824 | 3.593 | 0.191 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1859 | 0.331 | 0.8883 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1967 | 1.964 | 5.583 | 0.3915 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1967 | 0.3459 | 5.273 | 0.3442 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1967 | 2.511 | 5.189 | 0.4001 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1967 | -0.4548 | 3.289 | 0.1642 |
| derivative_onset_bin | sharp | mlp | 1967 | -1.171 | 3.9 | 0.2161 |
| derivative_onset_bin | sharp | ridge | 1967 | -0.5865 | 3.598 | 0.1988 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1967 | 0.3551 | 0.8552 | 0.0005084 |
| derivative_onset_bin | slow | 1d_cnn | 1640 | 2.503 | 8.976 | 0.5622 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1640 | -1.087 | 5.855 | 0.3902 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1640 | 0.6209 | 8.671 | 0.5445 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1640 | 0.8979 | 4.786 | 0.3134 |
| derivative_onset_bin | slow | mlp | 1640 | 0.8221 | 4.883 | 0.3262 |
| derivative_onset_bin | slow | ridge | 1640 | 1.437 | 4.824 | 0.3457 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1640 | 0.13 | 0.909 | 0 |
| energy_bin | q1_low | 1d_cnn | 1403 | 0.2592 | 6.908 | 0.4319 |
| energy_bin | q1_low | compact_waveform_transformer | 1403 | -0.01895 | 5.025 | 0.3321 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1403 | 1.215 | 6.999 | 0.4512 |
| energy_bin | q1_low | gradient_boosted_trees | 1403 | -0.1985 | 3.805 | 0.2138 |
| energy_bin | q1_low | mlp | 1403 | -0.4952 | 4.219 | 0.2438 |
| energy_bin | q1_low | ridge | 1403 | 0.8882 | 4.145 | 0.2488 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1403 | -0.1016 | 1.016 | 0.0007128 |
| energy_bin | q2 | 1d_cnn | 1531 | 1.589 | 4.677 | 0.3214 |
| energy_bin | q2 | compact_waveform_transformer | 1531 | 0.7186 | 4.784 | 0.3005 |
| energy_bin | q2 | derivative_gate_transformer_new | 1531 | 1.332 | 5.832 | 0.3906 |
| energy_bin | q2 | gradient_boosted_trees | 1531 | 0.1904 | 3.729 | 0.194 |
| energy_bin | q2 | mlp | 1531 | -0.6004 | 4.388 | 0.2515 |
| energy_bin | q2 | ridge | 1531 | 0.2049 | 3.899 | 0.2338 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1531 | 0.338 | 0.8046 | 0 |
| energy_bin | q3 | 1d_cnn | 1458 | 4.729 | 4.73 | 0.5466 |
| energy_bin | q3 | compact_waveform_transformer | 1458 | 0.6393 | 5.535 | 0.3697 |
| energy_bin | q3 | derivative_gate_transformer_new | 1458 | 2.309 | 6.039 | 0.4376 |
| energy_bin | q3 | gradient_boosted_trees | 1458 | -0.1133 | 4.12 | 0.2394 |
| energy_bin | q3 | mlp | 1458 | -0.4597 | 4.606 | 0.2737 |
| energy_bin | q3 | ridge | 1458 | -0.5103 | 4.197 | 0.2558 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1458 | 0.4826 | 0.7925 | 0 |
| energy_bin | q4_high | 1d_cnn | 1074 | -0.1909 | 6.486 | 0.4367 |
| energy_bin | q4_high | compact_waveform_transformer | 1074 | -3.461 | 4.911 | 0.4292 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1074 | 4.33 | 5.893 | 0.5708 |
| energy_bin | q4_high | gradient_boosted_trees | 1074 | -0.1672 | 3.729 | 0.2412 |
| energy_bin | q4_high | mlp | 1074 | -0.9332 | 3.974 | 0.2523 |
| energy_bin | q4_high | ridge | 1074 | -0.4925 | 3.847 | 0.2169 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1074 | 0.2145 | 1.01 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3326 | 1.666 | 5.8 | 0.4074 |
| late_tail_morphology | compact | compact_waveform_transformer | 3326 | 0.07183 | 5.138 | 0.334 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3326 | 1.214 | 6.038 | 0.4092 |
| late_tail_morphology | compact | gradient_boosted_trees | 3326 | -0.3991 | 3.621 | 0.1852 |
| late_tail_morphology | compact | mlp | 3326 | -1.101 | 4.048 | 0.224 |
| late_tail_morphology | compact | ridge | 3326 | -0.3088 | 3.783 | 0.2093 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3326 | 0.2702 | 0.8888 | 0.0003007 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 627 | 1.084 | 5.531 | 0.3668 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 627 | -1.592 | 5.244 | 0.3764 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 627 | 4.315 | 3.761 | 0.4625 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 627 | -0.04999 | 3.774 | 0.1946 |
| late_tail_morphology | diffuse_tail | mlp | 627 | -0.09041 | 4.345 | 0.2568 |
| late_tail_morphology | diffuse_tail | ridge | 627 | -0.4938 | 3.779 | 0.2201 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 627 | 0.7092 | 0.8108 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 362 | -0.04639 | 8.201 | 0.5359 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 362 | -0.9546 | 6.307 | 0.4365 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 362 | 4.553 | 5.36 | 0.6022 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 362 | -0.5607 | 3.36 | 0.2155 |
| late_tail_morphology | late_derivative_bump | mlp | 362 | -1.533 | 3.523 | 0.2514 |
| late_tail_morphology | late_derivative_bump | ridge | 362 | -0.01846 | 3.408 | 0.1989 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 362 | 0.2046 | 0.9235 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1151 | 3.116 | 6.863 | 0.5083 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1151 | -0.9693 | 5.914 | 0.3658 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1151 | 2.287 | 7.527 | 0.5326 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1151 | 1.047 | 5.163 | 0.338 |
| late_tail_morphology | late_rising_tail | mlp | 1151 | 0.8949 | 5.34 | 0.3475 |
| late_tail_morphology | late_rising_tail | ridge | 1151 | 1.495 | 4.845 | 0.3536 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1151 | 0.1292 | 0.8792 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1681 | 1.706 | 8.274 | 0.5312 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1681 | -1.264 | 6.121 | 0.4265 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1681 | 0.322 | 8.339 | 0.5568 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1681 | 0.1501 | 4.274 | 0.2499 |
| pedestal_drift_bin | high | mlp | 1681 | 0.2409 | 4.407 | 0.2659 |
| pedestal_drift_bin | high | ridge | 1681 | 0.3216 | 4.351 | 0.2617 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1681 | 0.3114 | 0.9186 | 0.0005949 |
| pedestal_drift_bin | low | 1d_cnn | 1831 | 1.678 | 5.509 | 0.3921 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1831 | -0.2457 | 5.104 | 0.3179 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1831 | 2.358 | 5.35 | 0.4085 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1831 | -0.2412 | 3.717 | 0.213 |
| pedestal_drift_bin | low | mlp | 1831 | -1.082 | 4.139 | 0.2529 |
| pedestal_drift_bin | low | ridge | 1831 | -0.1936 | 3.95 | 0.2359 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1831 | 0.2465 | 0.8445 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1954 | 1.929 | 5.202 | 0.3854 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1954 | 0.1546 | 5.017 | 0.3209 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1954 | 2.615 | 5.338 | 0.4084 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1954 | -0.02105 | 3.694 | 0.2021 |
| pedestal_drift_bin | mid | mlp | 1954 | -0.7521 | 4.264 | 0.2492 |
| pedestal_drift_bin | mid | ridge | 1954 | -0.0325 | 3.851 | 0.2257 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1954 | 0.2541 | 0.8667 | 0 |
| pid_sideband | central | 1d_cnn | 3756 | 1.997 | 5.551 | 0.3938 |
| pid_sideband | central | compact_waveform_transformer | 3756 | 0.14 | 4.987 | 0.3155 |
| pid_sideband | central | derivative_gate_transformer_new | 3756 | 2.317 | 5.416 | 0.4124 |
| pid_sideband | central | gradient_boosted_trees | 3756 | -0.04154 | 3.82 | 0.2159 |
| pid_sideband | central | mlp | 3756 | -0.6572 | 4.356 | 0.258 |
| pid_sideband | central | ridge | 3756 | 0.109 | 4.02 | 0.2412 |
| pid_sideband | central | traditional_cfd_template_derivative | 3756 | 0.2181 | 0.8641 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 861 | 0.3613 | 10.06 | 0.6376 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 861 | -3.63 | 5.723 | 0.4983 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 861 | -4.838 | 7.986 | 0.6469 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 861 | -0.2164 | 4.172 | 0.2369 |
| pid_sideband | high_duplicate | mlp | 861 | 0.1538 | 4.288 | 0.2509 |
| pid_sideband | high_duplicate | ridge | 861 | 0.05926 | 4.427 | 0.2706 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 861 | 0.4483 | 0.9349 | 0.001161 |
| pid_sideband | low_duplicate | 1d_cnn | 849 | 1.594 | 5.46 | 0.3958 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 849 | -0.264 | 5.508 | 0.3675 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 849 | 3.786 | 4.368 | 0.4429 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 849 | -0.1349 | 3.804 | 0.2238 |
| pid_sideband | low_duplicate | mlp | 849 | -1.031 | 4.364 | 0.2497 |
| pid_sideband | low_duplicate | ridge | 849 | -0.3161 | 3.577 | 0.2049 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 849 | 0.4014 | 0.8637 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1686 | 0.6869 | 6.051 | 0.4116 |
| pileup_separation_bin | close | compact_waveform_transformer | 1686 | -0.53 | 5.318 | 0.3559 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1686 | 2.446 | 5.795 | 0.4276 |
| pileup_separation_bin | close | gradient_boosted_trees | 1686 | -0.3777 | 3.682 | 0.2082 |
| pileup_separation_bin | close | mlp | 1686 | -1.207 | 4.355 | 0.2651 |
| pileup_separation_bin | close | ridge | 1686 | -0.851 | 3.865 | 0.2236 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1686 | 0.3519 | 0.8747 | 0.0005931 |
| pileup_separation_bin | late | 1d_cnn | 3 | -1.227 | 2.718 | 0 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -4.994 | 0.8544 | 0.3333 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 3 | 7.382 | 0.8385 | 1 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | -0.4095 | 0.4495 | 0 |
| pileup_separation_bin | late | mlp | 3 | 5.728 | 4.12 | 0.6667 |
| pileup_separation_bin | late | ridge | 3 | 1.41 | 1.45 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 3 | -0.5931 | 0.03329 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1211 | 3.955 | 6.182 | 0.5483 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1211 | -2.215 | 5.452 | 0.3906 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1211 | -0.2005 | 7.268 | 0.5145 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1211 | -0.4361 | 3.931 | 0.213 |
| pileup_separation_bin | mid | mlp | 1211 | -0.7461 | 4.277 | 0.2329 |
| pileup_separation_bin | mid | ridge | 1211 | -0.3452 | 3.879 | 0.2254 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1211 | 0.5079 | 0.8787 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2566 | 1.673 | 5.77 | 0.392 |
| pileup_separation_bin | none | compact_waveform_transformer | 2566 | 0.4726 | 5.086 | 0.332 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2566 | 2.451 | 5.956 | 0.4423 |
| pileup_separation_bin | none | gradient_boosted_trees | 2566 | 0.3505 | 4.01 | 0.2323 |
| pileup_separation_bin | none | mlp | 2566 | -0.2054 | 4.307 | 0.2595 |
| pileup_separation_bin | none | ridge | 2566 | 0.7311 | 4.043 | 0.2584 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2566 | 0.1568 | 0.8585 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1894 | 0.9754 | 7.147 | 0.4815 |
| pulse_shape_class | compact | compact_waveform_transformer | 1894 | -0.3812 | 5.802 | 0.3923 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1894 | -1.659 | 6.85 | 0.4741 |
| pulse_shape_class | compact | gradient_boosted_trees | 1894 | -0.6038 | 3.897 | 0.217 |
| pulse_shape_class | compact | mlp | 1894 | -1.231 | 4.277 | 0.2471 |
| pulse_shape_class | compact | ridge | 1894 | -0.07727 | 4.304 | 0.2577 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1894 | 0.2997 | 0.9581 | 0.000528 |
| pulse_shape_class | late_tail | 1d_cnn | 1795 | 2.308 | 6.455 | 0.4579 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1795 | -1.248 | 5.64 | 0.3705 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1795 | 3.374 | 6.314 | 0.5075 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1795 | 0.6111 | 4.583 | 0.2891 |
| pulse_shape_class | late_tail | mlp | 1795 | 0.4753 | 4.962 | 0.3181 |
| pulse_shape_class | late_tail | ridge | 1795 | 0.6559 | 4.509 | 0.3058 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1795 | 0.2741 | 0.869 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1777 | 2.027 | 4.855 | 0.3545 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1777 | 0.4038 | 4.516 | 0.2915 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1777 | 3.001 | 4.175 | 0.3787 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1777 | -0.1603 | 3.126 | 0.1548 |
| pulse_shape_class | nominal | mlp | 1777 | -1.082 | 3.776 | 0.2015 |
| pulse_shape_class | nominal | ridge | 1777 | -0.389 | 3.265 | 0.1553 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1777 | 0.2215 | 0.855 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3954 | 2.017 | 6.374 | 0.4537 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3954 | -0.4516 | 5.568 | 0.3563 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3954 | 1.902 | 6.348 | 0.4484 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3954 | -0.06662 | 3.977 | 0.2279 |
| saturation_onset_bin | linear | mlp | 3954 | -0.5173 | 4.441 | 0.263 |
| saturation_onset_bin | linear | ridge | 3954 | -0.06989 | 4.12 | 0.2446 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3954 | 0.318 | 0.9006 | 0.0002529 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1512 | 1.378 | 5.427 | 0.377 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1512 | -0.2402 | 5.235 | 0.3419 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1512 | 2.447 | 6.13 | 0.4689 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1512 | -0.07573 | 3.598 | 0.2011 |
| saturation_onset_bin | near_saturation | mlp | 1512 | -0.7231 | 4.107 | 0.2361 |
| saturation_onset_bin | near_saturation | ridge | 1512 | 0.1077 | 3.848 | 0.2288 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1512 | 0.1632 | 0.8409 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.871 | curved | 7.503 | 2.632 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 5.436 | curved | 7.005 | 1.569 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.722 | curved | 5.428 | 0.7058 |
| curvature_energy_bin | ridge | 3 | smooth | 3.947 | curved | 4.211 | 0.2637 |
| curvature_energy_bin | mlp | 3 | curved | 4.224 | moderate | 4.48 | 0.2556 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.79 | moderate | 3.98 | 0.19 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | moderate | 0.8062 | curved | 0.9635 | 0.1573 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 5.261 | slow | 8.976 | 3.715 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | sharp | 5.189 | slow | 8.671 | 3.481 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.289 | slow | 4.786 | 1.497 |
| derivative_onset_bin | ridge | 3 | nominal | 3.593 | slow | 4.824 | 1.231 |
| derivative_onset_bin | mlp | 3 | sharp | 3.9 | slow | 4.883 | 0.9825 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 5.109 | slow | 5.855 | 0.7466 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | sharp | 0.8552 | slow | 0.909 | 0.05385 |
| energy_bin | 1d_cnn | 4 | q2 | 4.677 | q1_low | 6.908 | 2.231 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 5.832 | q1_low | 6.999 | 1.166 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 4.784 | q3 | 5.535 | 0.751 |
| energy_bin | mlp | 4 | q4_high | 3.974 | q3 | 4.606 | 0.6324 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.729 | q3 | 4.12 | 0.3912 |
| energy_bin | ridge | 4 | q4_high | 3.847 | q3 | 4.197 | 0.3494 |
| energy_bin | traditional_cfd_template_derivative | 4 | q3 | 0.7925 | q1_low | 1.016 | 0.2236 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 3.761 | late_rising_tail | 7.527 | 3.766 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 5.531 | late_derivative_bump | 8.201 | 2.669 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.523 | late_rising_tail | 5.34 | 1.817 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 3.36 | late_rising_tail | 5.163 | 1.804 |
| late_tail_morphology | ridge | 4 | late_derivative_bump | 3.408 | late_rising_tail | 4.845 | 1.437 |
| late_tail_morphology | compact_waveform_transformer | 4 | compact | 5.138 | late_derivative_bump | 6.307 | 1.169 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | diffuse_tail | 0.8108 | late_derivative_bump | 0.9235 | 0.1128 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.202 | high | 8.274 | 3.072 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 5.338 | high | 8.339 | 3.001 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.017 | high | 6.121 | 1.104 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 3.694 | high | 4.274 | 0.5794 |
| pedestal_drift_bin | ridge | 3 | mid | 3.851 | high | 4.351 | 0.4998 |
| pedestal_drift_bin | mlp | 3 | low | 4.139 | high | 4.407 | 0.2688 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | low | 0.8445 | high | 0.9186 | 0.07414 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 5.46 | high_duplicate | 10.06 | 4.603 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.368 | high_duplicate | 7.986 | 3.617 |
| pid_sideband | ridge | 3 | low_duplicate | 3.577 | high_duplicate | 4.427 | 0.8506 |
| pid_sideband | compact_waveform_transformer | 3 | central | 4.987 | high_duplicate | 5.723 | 0.7355 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.804 | high_duplicate | 4.172 | 0.3675 |
| pid_sideband | mlp | 3 | high_duplicate | 4.288 | low_duplicate | 4.364 | 0.07628 |
| pid_sideband | traditional_cfd_template_derivative | 3 | low_duplicate | 0.8637 | high_duplicate | 0.9349 | 0.07126 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | late | 0.8385 | mid | 7.268 | 6.429 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 0.8544 | mid | 5.452 | 4.598 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 0.4495 | none | 4.01 | 3.56 |
| pileup_separation_bin | 1d_cnn | 4 | late | 2.718 | mid | 6.182 | 3.464 |
| pileup_separation_bin | ridge | 4 | late | 1.45 | none | 4.043 | 2.593 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | late | 0.03329 | mid | 0.8787 | 0.8454 |
| pileup_separation_bin | mlp | 4 | late | 4.12 | close | 4.355 | 0.2348 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.175 | compact | 6.85 | 2.674 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.855 | compact | 7.147 | 2.292 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.126 | late_tail | 4.583 | 1.457 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 4.516 | compact | 5.802 | 1.286 |
| pulse_shape_class | ridge | 3 | nominal | 3.265 | late_tail | 4.509 | 1.243 |
| pulse_shape_class | mlp | 3 | nominal | 3.776 | late_tail | 4.962 | 1.186 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.855 | compact | 0.9581 | 0.1031 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.427 | linear | 6.374 | 0.9476 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.598 | linear | 3.977 | 0.3793 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.107 | linear | 4.441 | 0.3342 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.235 | linear | 5.568 | 0.3335 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.848 | linear | 4.12 | 0.2723 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 6.13 | linear | 6.348 | 0.2188 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.8409 | linear | 0.9006 | 0.05968 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.05141 | 3.888 | 3.11 | 4.879 | -0.02362 | 0.2214 |
| full_derivative_gradient_boosted_trees | 76 | -0.05718 | 3.911 | 2.953 | 4.922 | 0 | 0.2203 |
| derivative_only | 43 | 0.08632 | 4.019 | 3.388 | 5.015 | 0.1076 | 0.2314 |
| amplitude_cfd_no_derivative | 5 | 0.168 | 4.097 | 3.512 | 4.795 | 0.1857 | 0.2446 |
| late_tail_curvature_window_only | 17 | 0.2015 | 4.535 | 4.044 | 5.265 | 0.6241 | 0.2763 |
| onset_derivative_window_only | 14 | -0.009953 | 4.661 | 3.73 | 6.199 | 0.7494 | 0.298 |
| pretrigger_derivative_only | 7 | -3.529 | 18.15 | 17.1 | 18.78 | 14.24 | 0.5922 |

## Interpretation, Systematics, and Caveats

This S56a benchmark measures relative transfer on a reproducible waveform-derived
timing residual and uses the pedestal-memory strata as diagnostics for where
pedestal-induced timing bias enters the sampled waveform.  The raw ROOT files do not contain an independent external
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

Ticket-local wrapper runtime was `375.6 s`; benchmark runtime was `375.5 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.

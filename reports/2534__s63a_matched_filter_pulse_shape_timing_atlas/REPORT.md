# S63a Matched-Filter Pulse-Shape Timing Atlas

## Abstract

Ticket `#2534` asks for a run-heldout pulse-shape and timing atlas under
pedestal drift and pile-up occupancy.  The traditional comparator is the
matched-filter/template chi2, constant-fraction timing, analytic time-walk,
and derivative residual correction family, benchmarked against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact transformer sequence encoder,
and a derivative-gated transformer architecture.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 0.9738 ns`
`[0.7535, 1.126]`.  The
traditional derivative comparator obtains `0.9738 ns`
`[0.7535, 1.126]`.


## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once.  The helper returned the malformed payload

```text
# null

null
null
```

without moving an issue.  Read-only queue inspection showed open testbeam
tickets and no `worker:testbeam-laptop-1` claimed issue, so issue `#2534` was
bound by the same label swap the helper performs:

```text
gh issue edit 2534 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
```

No second `tn-ticket claim` invocation was run.

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
pulse-shape timing changes under pedestal drift and pile-up occupancy.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.4931 | 0.008689 | 0.7498 | 0.9738 | 0.7535 | 1.126 | 1.007 | 0.0001829 | 0 |
| gradient_boosted_trees | 5466 | -0.5984 | -1.433 | 0.2491 | 3.777 | 3.335 | 4.251 | 4.669 | 0.1787 | 0.03952 |
| mlp | 5466 | -0.8126 | -1.534 | 0.1489 | 4.384 | 4.051 | 4.817 | 5.109 | 0.2554 | 0.04391 |
| ridge | 5466 | -0.3091 | -1.111 | 0.3863 | 4.459 | 4.012 | 5.127 | 5.18 | 0.26 | 0.04372 |
| derivative_gate_transformer_new | 5466 | 0.8272 | -0.05103 | 1.597 | 5.117 | 4.666 | 5.832 | 6.34 | 0.3456 | 0.07483 |
| 1d_cnn | 5466 | -0.8621 | -1.779 | 0.1513 | 5.121 | 4.622 | 5.725 | 6.339 | 0.3308 | 0.06897 |
| compact_waveform_transformer | 5466 | 0.4453 | -0.3611 | 1.085 | 6.599 | 6.144 | 7.258 | 7.361 | 0.4431 | 0.1337 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.803 | 2.313 | 3.336 | -1.092 | -1.847 | -0.08468 | 0.1786 |
| mlp | traditional_cfd_template_derivative | 3.41 | 3.029 | 3.906 | -1.306 | -2.141 | -0.2524 | 0.2552 |
| ridge | traditional_cfd_template_derivative | 3.485 | 3.021 | 4.175 | -0.8022 | -1.658 | 0.08086 | 0.2598 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 4.143 | 3.669 | 4.935 | 0.3341 | -0.6221 | 1.228 | 0.3454 |
| 1d_cnn | traditional_cfd_template_derivative | 4.147 | 3.634 | 4.826 | -1.355 | -2.212 | -0.2109 | 0.3306 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 5.625 | 5.138 | 6.328 | -0.04782 | -0.8379 | 0.7866 | 0.4429 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.07622 | 0.928 | 0.0007407 |
| sample_i_analysis | gradient_boosted_trees | 1350 | -0.4394 | 4.242 | 0.2207 |
| sample_i_analysis | mlp | 1350 | -0.8922 | 4.825 | 0.2659 |
| sample_i_analysis | ridge | 1350 | -1.077 | 5.987 | 0.3474 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | 0.2696 | 6.64 | 0.4385 |
| sample_i_analysis | 1d_cnn | 1350 | -1.984 | 6.862 | 0.4504 |
| sample_i_analysis | compact_waveform_transformer | 1350 | -0.795 | 7.695 | 0.4193 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | 0.01653 | 1.259 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.297 | 3.345 | 0.2161 |
| sample_i_calib | mlp | 657 | 1.292 | 4.291 | 0.242 |
| sample_i_calib | ridge | 657 | 1.762 | 4.475 | 0.3196 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 2.456 | 5.112 | 0.3546 |
| sample_i_calib | 1d_cnn | 657 | 1.346 | 5.238 | 0.4049 |
| sample_i_calib | compact_waveform_transformer | 657 | 1.55 | 6.285 | 0.4186 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.6078 | 1.017 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -0.7924 | 3.844 | 0.1734 |
| sample_ii_analysis | ridge | 2739 | -0.2956 | 4.276 | 0.226 |
| sample_ii_analysis | mlp | 2739 | -0.9926 | 4.545 | 0.2676 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.7176 | 4.78 | 0.2815 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | 0.6603 | 4.911 | 0.3202 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | 0.7435 | 6.59 | 0.4655 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.84 | 0.3265 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.271 | 3.601 | 0.08611 |
| sample_ii_calib | ridge | 720 | -1.017 | 3.664 | 0.1708 |
| sample_ii_calib | mlp | 720 | -1.699 | 4.23 | 0.2014 |
| sample_ii_calib | 1d_cnn | 720 | -0.8169 | 4.258 | 0.2264 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | 0.6434 | 4.286 | 0.2597 |
| sample_ii_calib | compact_waveform_transformer | 720 | 0.5298 | 6.005 | 0.425 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.346 | 5.238 | 0.4049 |
| 1d_cnn | 50 | 680 | -1.227 | 10.87 | 0.4221 |
| 1d_cnn | 57 | 670 | -2.987 | 5.968 | 0.4791 |
| 1d_cnn | 58 | 654 | -2.438 | 5.019 | 0.3654 |
| 1d_cnn | 60 | 720 | 0.6039 | 4.699 | 0.2931 |
| 1d_cnn | 62 | 720 | -0.2248 | 4.37 | 0.2236 |
| 1d_cnn | 64 | 720 | -0.8169 | 4.258 | 0.2264 |
| 1d_cnn | 65 | 645 | -1.123 | 4.367 | 0.2481 |
| compact_waveform_transformer | 42 | 657 | 1.55 | 6.285 | 0.4186 |
| compact_waveform_transformer | 50 | 680 | -0.002022 | 10.13 | 0.4426 |
| compact_waveform_transformer | 57 | 670 | -1.391 | 5.962 | 0.3955 |
| compact_waveform_transformer | 58 | 654 | -1.141 | 6.337 | 0.4419 |
| compact_waveform_transformer | 60 | 720 | 1.693 | 7.32 | 0.5083 |
| compact_waveform_transformer | 62 | 720 | 1.196 | 6.533 | 0.4708 |
| compact_waveform_transformer | 64 | 720 | 0.5298 | 6.005 | 0.425 |
| compact_waveform_transformer | 65 | 645 | 1.084 | 5.919 | 0.4357 |
| derivative_gate_transformer_new | 42 | 657 | 2.456 | 5.112 | 0.3546 |
| derivative_gate_transformer_new | 50 | 680 | 1.378 | 11.02 | 0.4824 |
| derivative_gate_transformer_new | 57 | 670 | -0.933 | 5.643 | 0.394 |
| derivative_gate_transformer_new | 58 | 654 | -0.9018 | 5.118 | 0.3257 |
| derivative_gate_transformer_new | 60 | 720 | 1.96 | 5.199 | 0.3847 |
| derivative_gate_transformer_new | 62 | 720 | 0.8205 | 4.899 | 0.3181 |
| derivative_gate_transformer_new | 64 | 720 | 0.6434 | 4.286 | 0.2597 |
| derivative_gate_transformer_new | 65 | 645 | 0.3226 | 4.316 | 0.245 |
| gradient_boosted_trees | 42 | 657 | 1.297 | 3.345 | 0.2161 |
| gradient_boosted_trees | 50 | 680 | 1.1 | 10.41 | 0.3353 |
| gradient_boosted_trees | 57 | 670 | -1.875 | 2.377 | 0.1045 |
| gradient_boosted_trees | 58 | 654 | -2.248 | 4.255 | 0.2752 |
| gradient_boosted_trees | 60 | 720 | 0.4155 | 3.305 | 0.1708 |
| gradient_boosted_trees | 62 | 720 | -0.7671 | 4.034 | 0.1653 |
| gradient_boosted_trees | 64 | 720 | -1.271 | 3.601 | 0.08611 |
| gradient_boosted_trees | 65 | 645 | -1.377 | 3.321 | 0.08217 |
| mlp | 42 | 657 | 1.292 | 4.291 | 0.242 |
| mlp | 50 | 680 | 0.4361 | 9.268 | 0.3397 |
| mlp | 57 | 670 | -1.726 | 3.146 | 0.191 |
| mlp | 58 | 654 | -2.478 | 4.975 | 0.3532 |
| mlp | 60 | 720 | 0.3251 | 4.268 | 0.2597 |
| mlp | 62 | 720 | -1.103 | 4.569 | 0.2569 |
| mlp | 64 | 720 | -1.699 | 4.23 | 0.2014 |
| mlp | 65 | 645 | -1.544 | 4.199 | 0.2016 |
| ridge | 42 | 657 | 1.762 | 4.475 | 0.3196 |
| ridge | 50 | 680 | 0.1992 | 10.17 | 0.3779 |
| ridge | 57 | 670 | -2.008 | 4.708 | 0.3164 |
| ridge | 58 | 654 | -1.687 | 4.787 | 0.2982 |
| ridge | 60 | 720 | 0.8893 | 4.043 | 0.2347 |
| ridge | 62 | 720 | -0.3698 | 4.141 | 0.2167 |
| ridge | 64 | 720 | -1.017 | 3.664 | 0.1708 |
| ridge | 65 | 645 | -0.4165 | 3.832 | 0.1535 |
| traditional_cfd_template_derivative | 42 | 657 | 0.01653 | 1.259 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | -0.2285 | 0.5082 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | 0.6192 | 1.17 | 0.001493 |
| traditional_cfd_template_derivative | 58 | 654 | 0.5158 | 0.7474 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.3994 | 1.355 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.8787 | 0.9226 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.84 | 0.3265 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.6536 | 0.6337 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1580 | -0.6558 | 5.35 | 0.3513 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1580 | -2.332 | 6.111 | 0.4335 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1580 | 0.09392 | 5.538 | 0.3557 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1580 | -0.6143 | 3.692 | 0.1829 |
| curvature_energy_bin | curved | mlp | 1580 | -0.9735 | 4.379 | 0.2703 |
| curvature_energy_bin | curved | ridge | 1580 | -0.4635 | 4.303 | 0.2475 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1580 | 0.4546 | 1.089 | 0.0006329 |
| curvature_energy_bin | moderate | 1d_cnn | 1940 | -0.5119 | 5.135 | 0.3325 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1940 | 1.279 | 6.501 | 0.4351 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1940 | 1.213 | 5.219 | 0.3562 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1940 | -0.2997 | 3.984 | 0.2026 |
| curvature_energy_bin | moderate | mlp | 1940 | -0.6866 | 4.451 | 0.267 |
| curvature_energy_bin | moderate | ridge | 1940 | -0.599 | 4.707 | 0.2773 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1940 | 0.5369 | 0.9497 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1946 | -1.423 | 4.957 | 0.3124 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1946 | 1.665 | 5.848 | 0.4589 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1946 | 0.8006 | 4.844 | 0.3268 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1946 | -0.7457 | 3.614 | 0.1516 |
| curvature_energy_bin | smooth | mlp | 1946 | -0.8335 | 4.266 | 0.2318 |
| curvature_energy_bin | smooth | ridge | 1946 | 0.1686 | 4.311 | 0.2528 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1946 | 0.4724 | 0.9115 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1848 | -1.17 | 4.722 | 0.2895 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1848 | 0.3189 | 6.385 | 0.4248 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1848 | 0.647 | 4.915 | 0.3166 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1848 | -0.6728 | 3.575 | 0.145 |
| derivative_onset_bin | nominal | mlp | 1848 | -1.068 | 4.175 | 0.2246 |
| derivative_onset_bin | nominal | ridge | 1848 | -0.5398 | 4.18 | 0.2267 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1848 | 0.588 | 0.9604 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1933 | -0.8282 | 4.997 | 0.3006 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1933 | 0.7502 | 6.52 | 0.4578 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1933 | 0.7748 | 4.996 | 0.3311 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1933 | -0.9361 | 3.208 | 0.1195 |
| derivative_onset_bin | sharp | mlp | 1933 | -1.076 | 3.997 | 0.2266 |
| derivative_onset_bin | sharp | ridge | 1933 | -0.5053 | 4.456 | 0.2545 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1933 | 0.6813 | 0.9329 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1685 | -0.425 | 6.016 | 0.4107 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1685 | 0.2158 | 6.864 | 0.4463 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1685 | 1.027 | 5.837 | 0.3941 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1685 | 0.2158 | 4.42 | 0.2837 |
| derivative_onset_bin | slow | mlp | 1685 | -0.2896 | 4.905 | 0.3223 |
| derivative_onset_bin | slow | ridge | 1685 | 0.008585 | 4.417 | 0.3027 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1685 | 0.1656 | 0.9398 | 0.0005935 |
| energy_bin | q1_low | 1d_cnn | 1421 | -1.119 | 5.44 | 0.3849 |
| energy_bin | q1_low | compact_waveform_transformer | 1421 | 0.8803 | 6.552 | 0.4771 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1421 | 1.245 | 5.268 | 0.3793 |
| energy_bin | q1_low | gradient_boosted_trees | 1421 | -0.7445 | 3.77 | 0.1668 |
| energy_bin | q1_low | mlp | 1421 | -0.7537 | 4.339 | 0.2372 |
| energy_bin | q1_low | ridge | 1421 | 0.4576 | 4.174 | 0.2526 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1421 | 0.1696 | 1.076 | 0.0007037 |
| energy_bin | q2 | 1d_cnn | 1531 | -1.208 | 4.997 | 0.3116 |
| energy_bin | q2 | compact_waveform_transformer | 1531 | 1.853 | 6.342 | 0.4559 |
| energy_bin | q2 | derivative_gate_transformer_new | 1531 | 1.044 | 4.998 | 0.3364 |
| energy_bin | q2 | gradient_boosted_trees | 1531 | -0.5579 | 3.873 | 0.1907 |
| energy_bin | q2 | mlp | 1531 | -1.063 | 4.631 | 0.2782 |
| energy_bin | q2 | ridge | 1531 | -0.3545 | 4.644 | 0.2796 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1531 | 0.5824 | 0.8615 | 0 |
| energy_bin | q3 | 1d_cnn | 1381 | 0.08407 | 4.875 | 0.3085 |
| energy_bin | q3 | compact_waveform_transformer | 1381 | 0.9731 | 6.313 | 0.4287 |
| energy_bin | q3 | derivative_gate_transformer_new | 1381 | 0.8119 | 5.185 | 0.3505 |
| energy_bin | q3 | gradient_boosted_trees | 1381 | -0.3999 | 3.825 | 0.1796 |
| energy_bin | q3 | mlp | 1381 | -0.7395 | 4.274 | 0.2563 |
| energy_bin | q3 | ridge | 1381 | -0.5814 | 4.71 | 0.2781 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1381 | 0.6043 | 0.9088 | 0 |
| energy_bin | q4_high | 1d_cnn | 1133 | -1.256 | 4.875 | 0.316 |
| energy_bin | q4_high | compact_waveform_transformer | 1133 | -2.614 | 5.481 | 0.4007 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1133 | -0.1819 | 5.305 | 0.3098 |
| energy_bin | q4_high | gradient_boosted_trees | 1133 | -0.5329 | 3.346 | 0.1765 |
| energy_bin | q4_high | mlp | 1133 | -0.7265 | 3.964 | 0.2462 |
| energy_bin | q4_high | ridge | 1133 | -0.5572 | 4.128 | 0.2207 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1133 | 0.4352 | 1.143 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3303 | -1.049 | 5.036 | 0.3212 |
| late_tail_morphology | compact | compact_waveform_transformer | 3303 | 0.3653 | 7.03 | 0.479 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3303 | 0.8388 | 5.271 | 0.3618 |
| late_tail_morphology | compact | gradient_boosted_trees | 3303 | -0.8912 | 3.655 | 0.1535 |
| late_tail_morphology | compact | mlp | 3303 | -1.222 | 4.229 | 0.2319 |
| late_tail_morphology | compact | ridge | 3303 | -0.2869 | 4.545 | 0.2589 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3303 | 0.5966 | 0.9571 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 595 | -1.227 | 4.352 | 0.2689 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 595 | -0.12 | 5.075 | 0.3345 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 595 | 0.7066 | 4.412 | 0.2723 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 595 | -0.07159 | 3.506 | 0.158 |
| late_tail_morphology | diffuse_tail | mlp | 595 | -0.4932 | 4.287 | 0.2487 |
| late_tail_morphology | diffuse_tail | ridge | 595 | -0.697 | 4.03 | 0.205 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 595 | 0.7732 | 0.9952 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 362 | -1.448 | 5.808 | 0.3702 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 362 | -0.1084 | 6.341 | 0.4033 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 362 | 1.613 | 4.555 | 0.337 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 362 | -0.6047 | 3.031 | 0.1575 |
| late_tail_morphology | late_derivative_bump | mlp | 362 | -1.356 | 3.978 | 0.2569 |
| late_tail_morphology | late_derivative_bump | ridge | 362 | -0.2275 | 3.693 | 0.2238 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 362 | 0.3066 | 1.12 | 0.002762 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1206 | -0.03715 | 5.545 | 0.3756 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1206 | 1.238 | 5.873 | 0.4104 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1206 | 0.7437 | 5.052 | 0.34 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1206 | 0.2867 | 4.367 | 0.2645 |
| late_tail_morphology | late_rising_tail | mlp | 1206 | -0.2632 | 4.77 | 0.3226 |
| late_tail_morphology | late_rising_tail | ridge | 1206 | -0.129 | 4.42 | 0.301 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1206 | 0.1323 | 0.893 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1741 | -0.7064 | 5.539 | 0.3751 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1741 | -1.422 | 7.692 | 0.5215 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1741 | 0.796 | 6.187 | 0.4176 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1741 | -0.3832 | 4.197 | 0.2257 |
| pedestal_drift_bin | high | mlp | 1741 | -0.5268 | 4.551 | 0.2688 |
| pedestal_drift_bin | high | ridge | 1741 | -0.05594 | 4.539 | 0.2763 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1741 | 0.4882 | 1.023 | 0.0005744 |
| pedestal_drift_bin | low | 1d_cnn | 1832 | -0.9311 | 5.062 | 0.3248 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1832 | 1.013 | 5.735 | 0.4061 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1832 | 0.7239 | 4.796 | 0.3177 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1832 | -0.6534 | 3.569 | 0.1654 |
| pedestal_drift_bin | low | mlp | 1832 | -0.8883 | 4.382 | 0.2587 |
| pedestal_drift_bin | low | ridge | 1832 | -0.475 | 4.597 | 0.2664 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1832 | 0.4547 | 0.9452 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1893 | -0.9668 | 4.816 | 0.2958 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1893 | 1.059 | 5.827 | 0.4068 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1893 | 0.9008 | 4.692 | 0.3064 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1893 | -0.6333 | 3.547 | 0.1484 |
| pedestal_drift_bin | mid | mlp | 1893 | -0.8824 | 4.249 | 0.2398 |
| pedestal_drift_bin | mid | ridge | 1893 | -0.3565 | 4.262 | 0.2388 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1893 | 0.5376 | 0.9652 | 0 |
| pid_sideband | central | 1d_cnn | 3742 | -0.8585 | 4.979 | 0.3212 |
| pid_sideband | central | compact_waveform_transformer | 3742 | 1.223 | 5.852 | 0.4174 |
| pid_sideband | central | derivative_gate_transformer_new | 3742 | 0.8949 | 4.784 | 0.3188 |
| pid_sideband | central | gradient_boosted_trees | 3742 | -0.619 | 3.599 | 0.1609 |
| pid_sideband | central | mlp | 3742 | -0.8066 | 4.27 | 0.2453 |
| pid_sideband | central | ridge | 3742 | -0.3145 | 4.528 | 0.2646 |
| pid_sideband | central | traditional_cfd_template_derivative | 3742 | 0.4542 | 0.9524 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 880 | -1.39 | 5.92 | 0.4205 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 880 | -5.705 | 6.86 | 0.5989 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 880 | -0.3381 | 6.986 | 0.4966 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 880 | -0.6565 | 4.444 | 0.2625 |
| pid_sideband | high_duplicate | mlp | 880 | -1.207 | 4.83 | 0.292 |
| pid_sideband | high_duplicate | ridge | 880 | -0.274 | 4.636 | 0.2761 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 880 | 0.5896 | 1.031 | 0.001136 |
| pid_sideband | low_duplicate | 1d_cnn | 844 | -0.6466 | 4.618 | 0.2796 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 844 | 1.078 | 5.759 | 0.3945 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 844 | 1.24 | 4.637 | 0.3069 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 844 | -0.3777 | 3.909 | 0.1706 |
| pid_sideband | low_duplicate | mlp | 844 | -0.7223 | 4.27 | 0.2618 |
| pid_sideband | low_duplicate | ridge | 844 | -0.2971 | 4.101 | 0.2227 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 844 | 0.6472 | 1.019 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1662 | -1.624 | 4.989 | 0.3514 |
| pileup_separation_bin | close | compact_waveform_transformer | 1662 | -0.2952 | 6.07 | 0.4146 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1662 | 0.4671 | 4.955 | 0.3141 |
| pileup_separation_bin | close | gradient_boosted_trees | 1662 | -0.8433 | 3.511 | 0.1318 |
| pileup_separation_bin | close | mlp | 1662 | -1.159 | 4.178 | 0.2431 |
| pileup_separation_bin | close | ridge | 1662 | -0.723 | 4.368 | 0.2714 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1662 | 0.6753 | 0.9526 | 0 |
| pileup_separation_bin | late | 1d_cnn | 5 | -2.424 | 1.918 | 0.2 |
| pileup_separation_bin | late | compact_waveform_transformer | 5 | -7.398 | 4.013 | 0.8 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 5 | -1.139 | 2.146 | 0 |
| pileup_separation_bin | late | gradient_boosted_trees | 5 | -0.905 | 1.16 | 0 |
| pileup_separation_bin | late | mlp | 5 | -3.886 | 2.874 | 0.6 |
| pileup_separation_bin | late | ridge | 5 | -0.829 | 2.546 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 5 | -0.456 | 0.6053 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1185 | 0.1938 | 5.016 | 0.3207 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1185 | -3.118 | 6.684 | 0.5105 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1185 | 0.3086 | 5.674 | 0.3848 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1185 | -0.9029 | 3.809 | 0.1789 |
| pileup_separation_bin | mid | mlp | 1185 | -1.17 | 4.271 | 0.2464 |
| pileup_separation_bin | mid | ridge | 1185 | -0.4021 | 4.727 | 0.2793 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1185 | 0.7204 | 0.9809 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2614 | -0.6518 | 5.03 | 0.3225 |
| pileup_separation_bin | none | compact_waveform_transformer | 2614 | 2.024 | 5.638 | 0.43 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2614 | 1.225 | 4.793 | 0.3485 |
| pileup_separation_bin | none | gradient_boosted_trees | 2614 | -0.2092 | 3.862 | 0.2089 |
| pileup_separation_bin | none | mlp | 2614 | -0.5337 | 4.398 | 0.2666 |
| pileup_separation_bin | none | ridge | 2614 | -0.05153 | 4.079 | 0.2445 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2614 | 0.3244 | 0.9265 | 0.0003826 |
| pulse_shape_class | compact | 1d_cnn | 1870 | -0.9711 | 5.699 | 0.4102 |
| pulse_shape_class | compact | compact_waveform_transformer | 1870 | -1.214 | 7.529 | 0.5524 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1870 | 0.8578 | 5.83 | 0.4144 |
| pulse_shape_class | compact | gradient_boosted_trees | 1870 | -1.125 | 3.831 | 0.1818 |
| pulse_shape_class | compact | mlp | 1870 | -1.268 | 4.516 | 0.2599 |
| pulse_shape_class | compact | ridge | 1870 | 0.3394 | 4.89 | 0.3048 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1870 | 0.5707 | 0.9774 | 0.0005348 |
| pulse_shape_class | late_tail | 1d_cnn | 1829 | -0.645 | 5.17 | 0.3384 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1829 | 0.6392 | 5.636 | 0.3816 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1829 | 0.7165 | 4.772 | 0.3155 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1829 | 0.1227 | 4.105 | 0.2274 |
| pulse_shape_class | late_tail | mlp | 1829 | -0.3469 | 4.583 | 0.2974 |
| pulse_shape_class | late_tail | ridge | 1829 | -0.3602 | 4.255 | 0.269 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1829 | 0.2786 | 0.9699 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1767 | -1.092 | 4.437 | 0.2388 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1767 | 1.218 | 5.718 | 0.3911 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1767 | 0.9983 | 4.254 | 0.3039 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1767 | -0.6881 | 3.316 | 0.1251 |
| pulse_shape_class | nominal | mlp | 1767 | -1.166 | 3.778 | 0.2071 |
| pulse_shape_class | nominal | ridge | 1767 | -0.7114 | 3.977 | 0.2032 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1767 | 0.5988 | 0.9454 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3948 | -0.734 | 5.334 | 0.3465 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3948 | 0.3387 | 6.819 | 0.4605 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3948 | 0.5677 | 5.287 | 0.3576 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3948 | -0.6327 | 3.832 | 0.1814 |
| saturation_onset_bin | linear | mlp | 3948 | -0.8017 | 4.393 | 0.2576 |
| saturation_onset_bin | linear | ridge | 3948 | -0.3765 | 4.542 | 0.2662 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3948 | 0.4946 | 0.9982 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1518 | -1.087 | 4.666 | 0.2899 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1518 | 0.7035 | 5.997 | 0.3979 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1518 | 1.483 | 4.672 | 0.3142 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1518 | -0.4369 | 3.653 | 0.1719 |
| saturation_onset_bin | near_saturation | mlp | 1518 | -0.8568 | 4.378 | 0.2497 |
| saturation_onset_bin | near_saturation | ridge | 1518 | -0.1831 | 4.31 | 0.2437 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1518 | 0.49 | 0.9139 | 0.0006588 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 4.844 | curved | 5.538 | 0.6933 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 5.848 | moderate | 6.501 | 0.6528 |
| curvature_energy_bin | ridge | 3 | curved | 4.303 | moderate | 4.707 | 0.4047 |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.957 | curved | 5.35 | 0.3927 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.614 | moderate | 3.984 | 0.3701 |
| curvature_energy_bin | mlp | 3 | smooth | 4.266 | moderate | 4.451 | 0.1854 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | smooth | 0.9115 | curved | 1.089 | 0.1779 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.722 | slow | 6.016 | 1.294 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.208 | slow | 4.42 | 1.212 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | nominal | 4.915 | slow | 5.837 | 0.9218 |
| derivative_onset_bin | mlp | 3 | sharp | 3.997 | slow | 4.905 | 0.9081 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 6.385 | slow | 6.864 | 0.4787 |
| derivative_onset_bin | ridge | 3 | nominal | 4.18 | sharp | 4.456 | 0.2762 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | sharp | 0.9329 | nominal | 0.9604 | 0.02754 |
| energy_bin | compact_waveform_transformer | 4 | q4_high | 5.481 | q1_low | 6.552 | 1.072 |
| energy_bin | mlp | 4 | q4_high | 3.964 | q2 | 4.631 | 0.6666 |
| energy_bin | ridge | 4 | q4_high | 4.128 | q3 | 4.71 | 0.5822 |
| energy_bin | 1d_cnn | 4 | q3 | 4.875 | q1_low | 5.44 | 0.5653 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.346 | q2 | 3.873 | 0.5278 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 4.998 | q4_high | 5.305 | 0.3064 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.8615 | q4_high | 1.143 | 0.2817 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 5.075 | compact | 7.03 | 1.955 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.352 | late_derivative_bump | 5.808 | 1.457 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 3.031 | late_rising_tail | 4.367 | 1.336 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 4.412 | compact | 5.271 | 0.8586 |
| late_tail_morphology | ridge | 4 | late_derivative_bump | 3.693 | compact | 4.545 | 0.8519 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.978 | late_rising_tail | 4.77 | 0.7925 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_rising_tail | 0.893 | late_derivative_bump | 1.12 | 0.2269 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | low | 5.735 | high | 7.692 | 1.958 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.692 | high | 6.187 | 1.496 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 4.816 | high | 5.539 | 0.7228 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | mid | 3.547 | high | 4.197 | 0.6497 |
| pedestal_drift_bin | ridge | 3 | mid | 4.262 | low | 4.597 | 0.3355 |
| pedestal_drift_bin | mlp | 3 | mid | 4.249 | high | 4.551 | 0.3017 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | low | 0.9452 | high | 1.023 | 0.07793 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.637 | high_duplicate | 6.986 | 2.349 |
| pid_sideband | 1d_cnn | 3 | low_duplicate | 4.618 | high_duplicate | 5.92 | 1.302 |
| pid_sideband | compact_waveform_transformer | 3 | low_duplicate | 5.759 | high_duplicate | 6.86 | 1.1 |
| pid_sideband | gradient_boosted_trees | 3 | central | 3.599 | high_duplicate | 4.444 | 0.8453 |
| pid_sideband | mlp | 3 | low_duplicate | 4.27 | high_duplicate | 4.83 | 0.56 |
| pid_sideband | ridge | 3 | low_duplicate | 4.101 | high_duplicate | 4.636 | 0.5353 |
| pid_sideband | traditional_cfd_template_derivative | 3 | central | 0.9524 | high_duplicate | 1.031 | 0.07893 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | late | 2.146 | mid | 5.674 | 3.529 |
| pileup_separation_bin | 1d_cnn | 4 | late | 1.918 | none | 5.03 | 3.113 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 1.16 | none | 3.862 | 2.702 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 4.013 | mid | 6.684 | 2.67 |
| pileup_separation_bin | ridge | 4 | late | 2.546 | mid | 4.727 | 2.181 |
| pileup_separation_bin | mlp | 4 | late | 2.874 | none | 4.398 | 1.524 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | late | 0.6053 | mid | 0.9809 | 0.3756 |
| pulse_shape_class | compact_waveform_transformer | 3 | late_tail | 5.636 | compact | 7.529 | 1.892 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.254 | compact | 5.83 | 1.576 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.437 | compact | 5.699 | 1.262 |
| pulse_shape_class | ridge | 3 | nominal | 3.977 | compact | 4.89 | 0.9134 |
| pulse_shape_class | mlp | 3 | nominal | 3.778 | late_tail | 4.583 | 0.8053 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.316 | late_tail | 4.105 | 0.7885 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.9454 | compact | 0.9774 | 0.03202 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.997 | linear | 6.819 | 0.8222 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.666 | linear | 5.334 | 0.6684 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 4.672 | linear | 5.287 | 0.6152 |
| saturation_onset_bin | ridge | 2 | near_saturation | 4.31 | linear | 4.542 | 0.2322 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.653 | linear | 3.832 | 0.1791 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.9139 | linear | 0.9982 | 0.08432 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.378 | linear | 4.393 | 0.01498 |


## Pulse-Shape Timing Atlas

The ticket-specific atlas is written to `pulse_shape_timing_atlas.csv`.  It
crosses method performance with run, current proxy, pedestal window, phase
window, energy quartile, pulse-shape class, injected pile-up spacing,
saturation-onset tag, and PID-sideband proxy.  Non-run axes include run-block
bootstrap confidence intervals for `sigma68_ns`, median bias, and the
`|error| > 5 ns` tail fraction.

`systematics_summary.csv` compresses the winning method's axis spans; it is the
primary caveat table for pedestal, phase, pile-up, saturation, energy, and PID
movement.  `surrogate_detector_metrics.csv` reports the requested detector
surrogates: pile-up false-positive tail proxy, saturation-tag leakage proxy,
energy-bias slope proxy, and PID boundary movement proxy.  These are deliberately
named proxies because the raw HRDv waveform stream used here does not carry
external PID truth, independent energy calibration residuals, or hand-labeled
pile-up false positives for every pulse.

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.5832 | 3.796 | 3.366 | 4.276 | -0.01413 | 0.1729 |
| full_derivative_gradient_boosted_trees | 76 | -0.6183 | 3.81 | 3.354 | 4.268 | 0 | 0.176 |
| derivative_only | 43 | -0.327 | 4.396 | 4.012 | 5.078 | 0.5864 | 0.258 |
| amplitude_cfd_no_derivative | 5 | -0.2615 | 4.413 | 4.031 | 4.944 | 0.6028 | 0.2611 |
| late_tail_curvature_window_only | 17 | -0.04621 | 4.812 | 4.298 | 5.602 | 1.002 | 0.2988 |
| onset_derivative_window_only | 14 | -0.2162 | 5.235 | 4.43 | 6.545 | 1.425 | 0.3368 |
| pretrigger_derivative_only | 7 | -3.627 | 18.17 | 17.29 | 18.79 | 14.36 | 0.5712 |

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

Ticket-local wrapper runtime was `157.1 s`; benchmark runtime was `531.6 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.11.14`.

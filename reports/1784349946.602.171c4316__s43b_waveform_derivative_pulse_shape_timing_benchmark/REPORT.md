# S43b Waveform Derivative Pulse-Shape Timing Benchmark

## Abstract

Ticket `1784349946.602.171c4316` asks whether waveform derivative and curvature
information improves arrival-time extraction under pedestal drift.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, and derivative-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `derivative_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 0.8335 ns`
`[0.6548, 1.017]`.  The
traditional derivative comparator obtains `0.8335 ns`
`[0.6548, 1.017]`.

## Raw ROOT Reproduction

Input files are read from `data/root/root`.  For each event the raw
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
| 31 | data/root/root/hrdb_run_0031.root | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | data/root/root/hrdb_run_0032.root | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | data/root/root/hrdb_run_0033.root | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | data/root/root/hrdb_run_0034.root | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | data/root/root/hrdb_run_0035.root | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | data/root/root/hrdb_run_0036.root | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | data/root/root/hrdb_run_0037.root | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | data/root/root/hrdb_run_0039.root | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

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
pulse-shape timing changes under pedestal drift.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.2143 | -0.1279 | 0.6098 | 0.8335 | 0.6548 | 1.017 | 0.8821 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.7519 | -1.624 | 0.134 | 3.738 | 3.035 | 4.282 | 5.165 | 0.1846 | 0.04391 |
| ridge | 5466 | -0.3945 | -1.082 | 0.402 | 4.123 | 3.544 | 4.945 | 5.399 | 0.2292 | 0.04281 |
| mlp | 5466 | -0.9488 | -1.791 | 0.01747 | 4.353 | 3.854 | 4.946 | 5.352 | 0.2494 | 0.04427 |
| derivative_gate_transformer_new | 5466 | -0.4923 | -1.097 | 0.1678 | 5.159 | 4.422 | 6.127 | 6.675 | 0.3317 | 0.07373 |
| compact_waveform_transformer | 5466 | 0.2858 | -0.4218 | 0.8586 | 5.585 | 5.125 | 6.278 | 7.078 | 0.3714 | 0.09989 |
| 1d_cnn | 5466 | -0.1503 | -0.8728 | 0.769 | 5.633 | 4.878 | 6.583 | 8.377 | 0.3716 | 0.1196 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.905 | 2.217 | 3.472 | -0.9661 | -1.932 | -0.02746 | 0.1846 |
| ridge | traditional_cfd_template_derivative | 3.289 | 2.651 | 4.093 | -0.6087 | -1.482 | 0.171 | 0.2292 |
| mlp | traditional_cfd_template_derivative | 3.52 | 3.016 | 4.135 | -1.163 | -2.149 | -0.06618 | 0.2494 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 4.325 | 3.555 | 5.267 | -0.7066 | -1.396 | 0.01908 | 0.3317 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 4.752 | 4.284 | 5.511 | 0.07148 | -0.7136 | 0.7761 | 0.3714 |
| 1d_cnn | traditional_cfd_template_derivative | 4.8 | 4.01 | 5.813 | -0.3646 | -1.191 | 0.5722 | 0.3716 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.1027 | 0.8775 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.6228 | 4.108 | 0.2511 |
| sample_i_analysis | mlp | 1350 | 0.3213 | 5.134 | 0.3126 |
| sample_i_analysis | ridge | 1350 | 0.4637 | 5.926 | 0.3578 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | 0.1671 | 7.02 | 0.4407 |
| sample_i_analysis | compact_waveform_transformer | 1350 | 0.2632 | 7.06 | 0.4037 |
| sample_i_analysis | 1d_cnn | 1350 | 0.3484 | 7.752 | 0.4867 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | -0.4589 | 1.106 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.085 | 3.678 | 0.2359 |
| sample_i_calib | mlp | 657 | 1.013 | 4.352 | 0.2785 |
| sample_i_calib | ridge | 657 | 1.786 | 4.429 | 0.2785 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 1.206 | 4.855 | 0.3318 |
| sample_i_calib | compact_waveform_transformer | 657 | 1.696 | 5.533 | 0.3744 |
| sample_i_calib | 1d_cnn | 657 | 2.093 | 6.106 | 0.414 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.4822 | 0.7656 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -1.664 | 3.607 | 0.1668 |
| sample_ii_analysis | ridge | 2739 | -0.9605 | 3.778 | 0.1844 |
| sample_ii_analysis | mlp | 2739 | -1.777 | 4.29 | 0.2453 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | -0.9995 | 4.589 | 0.3056 |
| sample_ii_analysis | 1d_cnn | 2739 | -0.5704 | 5.13 | 0.3308 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | -0.1533 | 5.579 | 0.3757 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.7006 | 0.559 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.339 | 2.876 | 0.08056 |
| sample_ii_calib | ridge | 720 | -0.9499 | 3.098 | 0.1139 |
| sample_ii_calib | mlp | 720 | -1.749 | 3.727 | 0.1194 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | -0.6285 | 3.94 | 0.2264 |
| sample_ii_calib | 1d_cnn | 720 | -1.035 | 4.287 | 0.2722 |
| sample_ii_calib | compact_waveform_transformer | 720 | 0.493 | 4.676 | 0.2917 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 2.093 | 6.106 | 0.414 |
| 1d_cnn | 50 | 680 | -0.583 | 12.15 | 0.4706 |
| 1d_cnn | 57 | 670 | 1.826 | 6.928 | 0.503 |
| 1d_cnn | 58 | 654 | -1.838 | 5.793 | 0.4388 |
| 1d_cnn | 60 | 720 | 0.3187 | 4.512 | 0.2736 |
| 1d_cnn | 62 | 720 | -1.636 | 4.964 | 0.3319 |
| 1d_cnn | 64 | 720 | -1.035 | 4.287 | 0.2722 |
| 1d_cnn | 65 | 645 | 0.1014 | 4.609 | 0.2837 |
| compact_waveform_transformer | 42 | 657 | 1.696 | 5.533 | 0.3744 |
| compact_waveform_transformer | 50 | 680 | 0.09433 | 12.05 | 0.4147 |
| compact_waveform_transformer | 57 | 670 | 0.5487 | 5.989 | 0.3925 |
| compact_waveform_transformer | 58 | 654 | -2.207 | 6.162 | 0.4404 |
| compact_waveform_transformer | 60 | 720 | 0.9458 | 5.521 | 0.3764 |
| compact_waveform_transformer | 62 | 720 | -0.8748 | 5.308 | 0.3472 |
| compact_waveform_transformer | 64 | 720 | 0.493 | 4.676 | 0.2917 |
| compact_waveform_transformer | 65 | 645 | 0.6048 | 5.046 | 0.3411 |
| derivative_gate_transformer_new | 42 | 657 | 1.206 | 4.855 | 0.3318 |
| derivative_gate_transformer_new | 50 | 680 | -0.1949 | 12.2 | 0.475 |
| derivative_gate_transformer_new | 57 | 670 | 0.4841 | 5.942 | 0.406 |
| derivative_gate_transformer_new | 58 | 654 | -2.401 | 5.313 | 0.3823 |
| derivative_gate_transformer_new | 60 | 720 | -0.1744 | 4.181 | 0.2583 |
| derivative_gate_transformer_new | 62 | 720 | -1.427 | 4.485 | 0.3222 |
| derivative_gate_transformer_new | 64 | 720 | -0.6285 | 3.94 | 0.2264 |
| derivative_gate_transformer_new | 65 | 645 | -0.5086 | 4.175 | 0.262 |
| gradient_boosted_trees | 42 | 657 | 1.085 | 3.678 | 0.2359 |
| gradient_boosted_trees | 50 | 680 | 1.11 | 11.03 | 0.3059 |
| gradient_boosted_trees | 57 | 670 | -0.1733 | 4.036 | 0.1955 |
| gradient_boosted_trees | 58 | 654 | -3.592 | 4.051 | 0.3012 |
| gradient_boosted_trees | 60 | 720 | -0.4253 | 3.42 | 0.1208 |
| gradient_boosted_trees | 62 | 720 | -1.867 | 2.202 | 0.07222 |
| gradient_boosted_trees | 64 | 720 | -1.339 | 2.876 | 0.08056 |
| gradient_boosted_trees | 65 | 645 | -1.591 | 4.247 | 0.1876 |
| mlp | 42 | 657 | 1.013 | 4.352 | 0.2785 |
| mlp | 50 | 680 | 0.5125 | 10.84 | 0.3191 |
| mlp | 57 | 670 | 0.1736 | 5.068 | 0.306 |
| mlp | 58 | 654 | -3.29 | 5.181 | 0.3945 |
| mlp | 60 | 720 | -0.7731 | 4.003 | 0.1958 |
| mlp | 62 | 720 | -1.589 | 3.235 | 0.1181 |
| mlp | 64 | 720 | -1.749 | 3.727 | 0.1194 |
| mlp | 65 | 645 | -2.074 | 4.854 | 0.2915 |
| ridge | 42 | 657 | 1.786 | 4.429 | 0.2785 |
| ridge | 50 | 680 | 0.03142 | 11.52 | 0.3647 |
| ridge | 57 | 670 | 1.108 | 5.042 | 0.3507 |
| ridge | 58 | 654 | -2.137 | 4.792 | 0.3303 |
| ridge | 60 | 720 | -0.3224 | 2.884 | 0.09583 |
| ridge | 62 | 720 | -1.774 | 3.253 | 0.1319 |
| ridge | 64 | 720 | -0.9499 | 3.098 | 0.1139 |
| ridge | 65 | 645 | -0.1566 | 3.896 | 0.1938 |
| traditional_cfd_template_derivative | 42 | 657 | -0.4589 | 1.106 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | 0.003087 | 0.5704 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | -0.2885 | 0.9521 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.6708 | 0.7375 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.1965 | 0.479 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.8633 | 0.9962 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.7006 | 0.559 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.6074 | 0.4488 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1555 | 0.1586 | 7.043 | 0.4585 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1555 | -1.982 | 6.103 | 0.4296 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1555 | -0.6981 | 5.757 | 0.3852 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1555 | -0.8358 | 3.72 | 0.1981 |
| curvature_energy_bin | curved | mlp | 1555 | -0.5665 | 4.383 | 0.263 |
| curvature_energy_bin | curved | ridge | 1555 | -0.9631 | 4.325 | 0.2502 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1555 | 0.182 | 0.9521 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1990 | 0.5764 | 5.053 | 0.3271 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1990 | 1.663 | 5.388 | 0.3744 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1990 | -0.3612 | 5.063 | 0.3317 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1990 | -0.4822 | 3.769 | 0.1905 |
| curvature_energy_bin | moderate | mlp | 1990 | -0.5587 | 4.327 | 0.2442 |
| curvature_energy_bin | moderate | ridge | 1990 | -0.6016 | 4.054 | 0.2186 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1990 | 0.3216 | 0.7386 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1921 | -1.031 | 4.926 | 0.3472 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1921 | 0.3719 | 4.854 | 0.3212 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1921 | -0.444 | 4.813 | 0.2884 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1921 | -1.047 | 3.703 | 0.1676 |
| curvature_energy_bin | smooth | mlp | 1921 | -1.66 | 4.242 | 0.2436 |
| curvature_energy_bin | smooth | ridge | 1921 | 0.3577 | 4.05 | 0.2233 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1921 | 0.1394 | 0.8443 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1791 | -0.9247 | 4.714 | 0.3004 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1791 | 0.009495 | 5.306 | 0.3479 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1791 | -0.9227 | 4.675 | 0.2954 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1791 | -1.003 | 3.38 | 0.1513 |
| derivative_onset_bin | nominal | mlp | 1791 | -1.322 | 4.122 | 0.2289 |
| derivative_onset_bin | nominal | ridge | 1791 | -0.9403 | 3.717 | 0.1854 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1791 | 0.3319 | 0.8304 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 2005 | -0.4442 | 4.96 | 0.3252 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 2005 | 0.8902 | 5.437 | 0.3815 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 2005 | -0.6559 | 4.769 | 0.3107 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 2005 | -1.242 | 3.189 | 0.1182 |
| derivative_onset_bin | sharp | mlp | 2005 | -1.427 | 3.967 | 0.2025 |
| derivative_onset_bin | sharp | ridge | 2005 | -0.8511 | 3.904 | 0.203 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 2005 | 0.3815 | 0.7787 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1670 | 1.56 | 7.889 | 0.5036 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1670 | -0.1001 | 5.817 | 0.3844 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1670 | 0.4586 | 5.914 | 0.3958 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1670 | 0.6105 | 4.679 | 0.3 |
| derivative_onset_bin | slow | mlp | 1670 | 0.1736 | 4.865 | 0.3275 |
| derivative_onset_bin | slow | ridge | 1670 | 0.7209 | 4.435 | 0.3078 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1670 | -0.01663 | 0.7983 | 0 |
| energy_bin | q1_low | 1d_cnn | 1417 | -0.6737 | 6.408 | 0.4474 |
| energy_bin | q1_low | compact_waveform_transformer | 1417 | 0.5198 | 5.233 | 0.3613 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1417 | -0.1631 | 5.271 | 0.3352 |
| energy_bin | q1_low | gradient_boosted_trees | 1417 | -0.7737 | 3.868 | 0.1658 |
| energy_bin | q1_low | mlp | 1417 | -0.8341 | 4.432 | 0.2505 |
| energy_bin | q1_low | ridge | 1417 | 0.7715 | 4.028 | 0.2251 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1417 | -0.04125 | 1.027 | 0 |
| energy_bin | q2 | 1d_cnn | 1539 | -0.5618 | 5.161 | 0.3333 |
| energy_bin | q2 | compact_waveform_transformer | 1539 | 1.161 | 4.75 | 0.3249 |
| energy_bin | q2 | derivative_gate_transformer_new | 1539 | -0.5669 | 4.683 | 0.2924 |
| energy_bin | q2 | gradient_boosted_trees | 1539 | -0.7115 | 3.602 | 0.167 |
| energy_bin | q2 | mlp | 1539 | -1.4 | 4.553 | 0.2619 |
| energy_bin | q2 | ridge | 1539 | -0.2584 | 4.126 | 0.2216 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1539 | 0.2874 | 0.6882 | 0 |
| energy_bin | q3 | 1d_cnn | 1417 | 1.744 | 4.67 | 0.2992 |
| energy_bin | q3 | compact_waveform_transformer | 1417 | 1.337 | 5.842 | 0.4121 |
| energy_bin | q3 | derivative_gate_transformer_new | 1417 | -0.4182 | 5.456 | 0.3712 |
| energy_bin | q3 | gradient_boosted_trees | 1417 | -0.617 | 3.677 | 0.1934 |
| energy_bin | q3 | mlp | 1417 | -0.8274 | 4.168 | 0.2385 |
| energy_bin | q3 | ridge | 1417 | -0.8773 | 4.292 | 0.2491 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1417 | 0.4167 | 0.7349 | 0 |
| energy_bin | q4_high | 1d_cnn | 1093 | -1.111 | 6.088 | 0.4209 |
| energy_bin | q4_high | compact_waveform_transformer | 1093 | -2.857 | 5.355 | 0.3971 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1093 | -0.7166 | 5.334 | 0.3312 |
| energy_bin | q4_high | gradient_boosted_trees | 1093 | -0.9252 | 3.644 | 0.2223 |
| energy_bin | q4_high | mlp | 1093 | -0.769 | 3.972 | 0.2443 |
| energy_bin | q4_high | ridge | 1093 | -0.9771 | 3.963 | 0.2196 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1093 | 0.208 | 0.9718 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3251 | -0.2824 | 5.301 | 0.3507 |
| late_tail_morphology | compact | compact_waveform_transformer | 3251 | 0.6738 | 5.5 | 0.3808 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3251 | -1.126 | 4.974 | 0.3424 |
| late_tail_morphology | compact | gradient_boosted_trees | 3251 | -1.13 | 3.537 | 0.1476 |
| late_tail_morphology | compact | mlp | 3251 | -1.237 | 4.252 | 0.2273 |
| late_tail_morphology | compact | ridge | 3251 | -0.5495 | 4.022 | 0.2064 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3251 | 0.3195 | 0.833 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 620 | -2.269 | 4.649 | 0.3145 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 620 | -1.459 | 4.943 | 0.3177 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 620 | -0.08935 | 3.847 | 0.2355 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 620 | -0.6418 | 3.001 | 0.1355 |
| late_tail_morphology | diffuse_tail | mlp | 620 | -0.7707 | 3.974 | 0.2177 |
| late_tail_morphology | diffuse_tail | ridge | 620 | -1.232 | 3.265 | 0.1677 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 620 | 0.5054 | 0.7684 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 386 | -0.5877 | 6.568 | 0.3964 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 386 | 0.1766 | 6.162 | 0.4119 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 386 | 1.02 | 4.548 | 0.2642 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 386 | -0.7765 | 2.975 | 0.1218 |
| late_tail_morphology | late_derivative_bump | mlp | 386 | -0.79 | 3.88 | 0.2306 |
| late_tail_morphology | late_derivative_bump | ridge | 386 | -0.2463 | 3.7 | 0.228 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 386 | 0.06729 | 1.023 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1209 | 1.924 | 6.542 | 0.4491 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1209 | 0.1046 | 5.504 | 0.3606 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1209 | 0.6692 | 5.418 | 0.3739 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1209 | 0.495 | 5.091 | 0.3292 |
| late_tail_morphology | late_rising_tail | mlp | 1209 | -0.324 | 5.107 | 0.3309 |
| late_tail_morphology | late_rising_tail | ridge | 1209 | 0.5641 | 4.628 | 0.3226 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1209 | -0.04833 | 0.7461 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1738 | 0.6548 | 6.929 | 0.4574 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1738 | -0.3882 | 6.417 | 0.4425 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1738 | -0.9187 | 5.799 | 0.3913 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1738 | -0.5283 | 3.977 | 0.1985 |
| pedestal_drift_bin | high | mlp | 1738 | 0.1245 | 4.461 | 0.2802 |
| pedestal_drift_bin | high | ridge | 1738 | -0.1127 | 4.187 | 0.2301 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1738 | 0.1512 | 0.8455 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1790 | -0.5946 | 5.139 | 0.3397 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1790 | 0.3199 | 5.122 | 0.3413 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1790 | -0.5153 | 5.102 | 0.319 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1790 | -0.9008 | 3.557 | 0.1721 |
| pedestal_drift_bin | low | mlp | 1790 | -1.401 | 4.11 | 0.2385 |
| pedestal_drift_bin | low | ridge | 1790 | -0.5809 | 4.241 | 0.2486 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1790 | 0.2112 | 0.8105 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1938 | -0.3981 | 5.1 | 0.324 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1938 | 0.6048 | 5.009 | 0.3354 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1938 | -0.194 | 4.646 | 0.29 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1938 | -0.7941 | 3.622 | 0.1837 |
| pedestal_drift_bin | mid | mlp | 1938 | -1.337 | 4.188 | 0.2317 |
| pedestal_drift_bin | mid | ridge | 1938 | -0.4566 | 3.906 | 0.2105 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1938 | 0.2541 | 0.8345 | 0 |
| pid_sideband | central | 1d_cnn | 3740 | -0.2614 | 5.144 | 0.3313 |
| pid_sideband | central | compact_waveform_transformer | 3740 | 0.7339 | 4.991 | 0.3326 |
| pid_sideband | central | derivative_gate_transformer_new | 3740 | -0.1728 | 4.91 | 0.304 |
| pid_sideband | central | gradient_boosted_trees | 3740 | -0.7183 | 3.652 | 0.1824 |
| pid_sideband | central | mlp | 3740 | -1.172 | 4.259 | 0.2412 |
| pid_sideband | central | ridge | 3740 | -0.3052 | 4.14 | 0.2329 |
| pid_sideband | central | traditional_cfd_template_derivative | 3740 | 0.1604 | 0.8273 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 874 | 1.779 | 8.91 | 0.5755 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 874 | -2.72 | 6.459 | 0.5092 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 874 | -2.921 | 6.166 | 0.4977 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 874 | -0.8456 | 4.022 | 0.1911 |
| pid_sideband | high_duplicate | mlp | 874 | 0.5877 | 4.594 | 0.2986 |
| pid_sideband | high_duplicate | ridge | 874 | -0.3288 | 4.321 | 0.2471 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 874 | 0.258 | 0.8864 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 852 | -1.062 | 5.291 | 0.3392 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 852 | 0.384 | 5.733 | 0.4002 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 852 | -0.2355 | 4.538 | 0.2829 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 852 | -0.8036 | 3.635 | 0.1878 |
| pid_sideband | low_duplicate | mlp | 852 | -1.276 | 3.946 | 0.2347 |
| pid_sideband | low_duplicate | ridge | 852 | -0.7762 | 3.687 | 0.1948 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 852 | 0.4331 | 0.827 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1644 | -1.06 | 4.881 | 0.3175 |
| pileup_separation_bin | close | compact_waveform_transformer | 1644 | 0.4474 | 5.43 | 0.3552 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1644 | -0.8505 | 4.955 | 0.3279 |
| pileup_separation_bin | close | gradient_boosted_trees | 1644 | -1.213 | 3.402 | 0.1545 |
| pileup_separation_bin | close | mlp | 1644 | -1.228 | 4.03 | 0.2165 |
| pileup_separation_bin | close | ridge | 1644 | -1.04 | 3.832 | 0.2159 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1644 | 0.3407 | 0.8437 | 0 |
| pileup_separation_bin | late | 1d_cnn | 3 | -8.389 | 17.13 | 1 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -5.468 | 5 | 0.6667 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 3 | -1.05 | 1.13 | 0 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | -5.017 | 3.506 | 0.6667 |
| pileup_separation_bin | late | mlp | 3 | 0.9855 | 4.996 | 0.6667 |
| pileup_separation_bin | late | ridge | 3 | -2.356 | 5.769 | 0.3333 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 3 | 0.9678 | 0.878 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1157 | 1.893 | 5.517 | 0.3872 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1157 | -1.957 | 5.671 | 0.4278 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1157 | -2.452 | 5.414 | 0.4062 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1157 | -1.162 | 3.559 | 0.1573 |
| pileup_separation_bin | mid | mlp | 1157 | -0.6871 | 4.13 | 0.2316 |
| pileup_separation_bin | mid | ridge | 1157 | -0.9477 | 4.12 | 0.2299 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1157 | 0.4258 | 0.7601 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2662 | -0.2629 | 6.047 | 0.3974 |
| pileup_separation_bin | none | compact_waveform_transformer | 2662 | 1.012 | 5.019 | 0.3565 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2662 | 0.4064 | 4.761 | 0.302 |
| pileup_separation_bin | none | gradient_boosted_trees | 2662 | -0.2873 | 4.039 | 0.2145 |
| pileup_separation_bin | none | mlp | 2662 | -0.9161 | 4.6 | 0.2769 |
| pileup_separation_bin | none | ridge | 2662 | 0.3621 | 3.946 | 0.237 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2662 | 0.07426 | 0.8101 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1855 | 0.2955 | 6.501 | 0.4501 |
| pulse_shape_class | compact | compact_waveform_transformer | 1855 | 0.3831 | 6.016 | 0.434 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1855 | -1.796 | 5.25 | 0.4129 |
| pulse_shape_class | compact | gradient_boosted_trees | 1855 | -1.376 | 3.84 | 0.1714 |
| pulse_shape_class | compact | mlp | 1855 | -0.8368 | 4.52 | 0.2561 |
| pulse_shape_class | compact | ridge | 1855 | -0.05335 | 4.343 | 0.2512 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1855 | 0.2608 | 0.8719 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1858 | 0.1967 | 6.187 | 0.4026 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1858 | -0.428 | 5.362 | 0.3434 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1858 | 0.2964 | 4.96 | 0.3256 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1858 | -0.06723 | 4.397 | 0.2626 |
| pulse_shape_class | late_tail | mlp | 1858 | -0.5668 | 4.579 | 0.2906 |
| pulse_shape_class | late_tail | ridge | 1858 | -0.2579 | 4.346 | 0.2686 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1858 | 0.1454 | 0.8207 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1753 | -0.8809 | 4.353 | 0.2556 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1753 | 0.7935 | 5.067 | 0.3349 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1753 | -0.4277 | 4.403 | 0.2521 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1753 | -0.8647 | 3.141 | 0.1158 |
| pulse_shape_class | nominal | mlp | 1753 | -1.363 | 3.912 | 0.1985 |
| pulse_shape_class | nominal | ridge | 1753 | -0.8685 | 3.631 | 0.1643 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1753 | 0.2526 | 0.8047 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3933 | 0.04332 | 5.813 | 0.3872 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3933 | -0.03352 | 5.653 | 0.3738 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3933 | -0.6129 | 5.293 | 0.3425 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3933 | -0.8324 | 3.791 | 0.1897 |
| saturation_onset_bin | linear | mlp | 3933 | -0.9559 | 4.358 | 0.2459 |
| saturation_onset_bin | linear | ridge | 3933 | -0.4997 | 4.229 | 0.2428 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3933 | 0.2852 | 0.8481 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1533 | -0.5423 | 5.114 | 0.3314 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1533 | 0.8711 | 5.184 | 0.3653 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1533 | -0.1317 | 4.952 | 0.304 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1533 | -0.5734 | 3.628 | 0.1716 |
| saturation_onset_bin | near_saturation | mlp | 1533 | -0.928 | 4.32 | 0.2583 |
| saturation_onset_bin | near_saturation | ridge | 1533 | -0.04901 | 3.895 | 0.1944 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1533 | 0.1057 | 0.795 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 4.926 | curved | 7.043 | 2.117 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.854 | curved | 6.103 | 1.25 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 4.813 | curved | 5.757 | 0.9443 |
| curvature_energy_bin | ridge | 3 | smooth | 4.05 | curved | 4.325 | 0.275 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | moderate | 0.7386 | curved | 0.9521 | 0.2135 |
| curvature_energy_bin | mlp | 3 | smooth | 4.242 | curved | 4.383 | 0.1403 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.703 | moderate | 3.769 | 0.06569 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.714 | slow | 7.889 | 3.175 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.189 | slow | 4.679 | 1.49 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | nominal | 4.675 | slow | 5.914 | 1.238 |
| derivative_onset_bin | mlp | 3 | sharp | 3.967 | slow | 4.865 | 0.8988 |
| derivative_onset_bin | ridge | 3 | nominal | 3.717 | slow | 4.435 | 0.7179 |
| derivative_onset_bin | compact_waveform_transformer | 3 | nominal | 5.306 | slow | 5.817 | 0.5105 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | sharp | 0.7787 | nominal | 0.8304 | 0.05178 |
| energy_bin | 1d_cnn | 4 | q3 | 4.67 | q1_low | 6.408 | 1.738 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 4.75 | q3 | 5.842 | 1.092 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 4.683 | q3 | 5.456 | 0.7732 |
| energy_bin | mlp | 4 | q4_high | 3.972 | q2 | 4.553 | 0.5809 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.6882 | q1_low | 1.027 | 0.3383 |
| energy_bin | ridge | 4 | q4_high | 3.963 | q3 | 4.292 | 0.3291 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.602 | q1_low | 3.868 | 0.2658 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 2.975 | late_rising_tail | 5.091 | 2.116 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.649 | late_derivative_bump | 6.568 | 1.919 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 3.847 | late_rising_tail | 5.418 | 1.572 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.265 | late_rising_tail | 4.628 | 1.363 |
| late_tail_morphology | mlp | 4 | late_derivative_bump | 3.88 | late_rising_tail | 5.107 | 1.227 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.943 | late_derivative_bump | 6.162 | 1.219 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_rising_tail | 0.7461 | late_derivative_bump | 1.023 | 0.2768 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 5.1 | high | 6.929 | 1.829 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.009 | high | 6.417 | 1.408 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.646 | high | 5.799 | 1.152 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.557 | high | 3.977 | 0.4196 |
| pedestal_drift_bin | mlp | 3 | low | 4.11 | high | 4.461 | 0.3512 |
| pedestal_drift_bin | ridge | 3 | mid | 3.906 | low | 4.241 | 0.3355 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | low | 0.8105 | high | 0.8455 | 0.03495 |
| pid_sideband | 1d_cnn | 3 | central | 5.144 | high_duplicate | 8.91 | 3.766 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.538 | high_duplicate | 6.166 | 1.628 |
| pid_sideband | compact_waveform_transformer | 3 | central | 4.991 | high_duplicate | 6.459 | 1.468 |
| pid_sideband | mlp | 3 | low_duplicate | 3.946 | high_duplicate | 4.594 | 0.6481 |
| pid_sideband | ridge | 3 | low_duplicate | 3.687 | high_duplicate | 4.321 | 0.6346 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.635 | high_duplicate | 4.022 | 0.3872 |
| pid_sideband | traditional_cfd_template_derivative | 3 | low_duplicate | 0.827 | high_duplicate | 0.8864 | 0.05942 |
| pileup_separation_bin | 1d_cnn | 4 | close | 4.881 | late | 17.13 | 12.25 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | late | 1.13 | mid | 5.414 | 4.283 |
| pileup_separation_bin | ridge | 4 | close | 3.832 | late | 5.769 | 1.938 |
| pileup_separation_bin | mlp | 4 | close | 4.03 | late | 4.996 | 0.966 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 5 | mid | 5.671 | 0.671 |
| pileup_separation_bin | gradient_boosted_trees | 4 | close | 3.402 | none | 4.039 | 0.6367 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | mid | 0.7601 | late | 0.878 | 0.1178 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.353 | compact | 6.501 | 2.148 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 3.141 | late_tail | 4.397 | 1.256 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.067 | compact | 6.016 | 0.9486 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.403 | compact | 5.25 | 0.847 |
| pulse_shape_class | ridge | 3 | nominal | 3.631 | late_tail | 4.346 | 0.7152 |
| pulse_shape_class | mlp | 3 | nominal | 3.912 | late_tail | 4.579 | 0.6674 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.8047 | compact | 0.8719 | 0.06716 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 5.114 | linear | 5.813 | 0.6986 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.184 | linear | 5.653 | 0.4687 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 4.952 | linear | 5.293 | 0.341 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.895 | linear | 4.229 | 0.3344 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.628 | linear | 3.791 | 0.1625 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.795 | linear | 0.8481 | 0.0531 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.32 | linear | 4.358 | 0.03717 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.7126 | 3.759 | 3.22 | 4.279 | -0.03677 | 0.1848 |
| full_derivative_gradient_boosted_trees | 76 | -0.7337 | 3.796 | 3.246 | 4.246 | 0 | 0.1868 |
| amplitude_cfd_no_derivative | 5 | -0.2717 | 4.046 | 3.488 | 4.809 | 0.2509 | 0.2331 |
| derivative_only | 43 | -0.2938 | 4.115 | 3.37 | 4.977 | 0.3198 | 0.2281 |
| late_tail_curvature_window_only | 17 | -0.08124 | 4.547 | 3.917 | 5.268 | 0.7512 | 0.2812 |
| onset_derivative_window_only | 14 | -0.3966 | 4.774 | 3.852 | 5.993 | 0.9781 | 0.3031 |
| pretrigger_derivative_only | 7 | -4.258 | 18.26 | 17.57 | 19.44 | 14.46 | 0.6032 |

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

Runtime was `256.0 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.

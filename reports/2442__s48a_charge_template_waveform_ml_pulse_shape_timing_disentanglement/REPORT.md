# S48a/#2442 Charge-Template versus Waveform-ML Pulse-Shape Timing Disentanglement

## Abstract

Ticket `2442` asks for a charge-template and constant-fraction traditional
baseline to be benchmarked against waveform ML methods for pulse-shape and
timing inference.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
template-time-walk, charge-integration, and derivative-correction fit is
compared against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact waveform
transformer, and the ticket-local `derivative_gate_transformer_new`
architecture.

The required helper command `tn-ticket claim testbeam-laptop-1 --project
testbeam` returned the known null pseudo-ticket pattern (`null`, `# null`,
`null`) despite a non-empty project queue.  The helper was not rerun.  Following
the established recovery pattern for that edge case, issue `#2442` was manually
label-swapped from `factory:open` to `factory:claimed` with
`worker:testbeam-laptop-1`; the claim evidence is retained in
`claimed_ticket.txt`.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`traditional_cfd_template_derivative`** as the
winner with `sigma_68 = 1.003 ns`
`[0.6922, 1.233]`.  The
traditional derivative comparator obtains `1.003 ns`
`[0.6922, 1.233]`.

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
pulse-shape timing changes under pedestal drift.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.3287 | -0.1653 | 0.6307 | 1.003 | 0.6922 | 1.233 | 1.015 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.2752 | -1.228 | 0.6449 | 3.714 | 3.217 | 4.156 | 5.225 | 0.1806 | 0.04226 |
| ridge | 5466 | -0.1312 | -0.9031 | 0.5903 | 4.28 | 3.705 | 4.906 | 5.57 | 0.2431 | 0.04318 |
| mlp | 5466 | -0.6009 | -1.491 | 0.2101 | 4.313 | 3.904 | 4.916 | 5.453 | 0.2521 | 0.04244 |
| derivative_gate_transformer_new | 5466 | -1.721 | -2.58 | -0.6811 | 4.764 | 4.082 | 5.656 | 6.33 | 0.3092 | 0.06641 |
| compact_waveform_transformer | 5466 | 0.3905 | -0.2527 | 0.9855 | 6.077 | 5.573 | 6.804 | 7.288 | 0.4111 | 0.1085 |
| 1d_cnn | 5466 | 0.03186 | -0.9068 | 1.115 | 7.23 | 6.534 | 8.225 | 8.604 | 0.4744 | 0.1817 |

## Paired Deltas Against Traditional Derivative Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional derivative comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_cfd_template_derivative | 2.711 | 2.169 | 3.258 | -0.6039 | -1.63 | 0.4708 | 0.1806 |
| ridge | traditional_cfd_template_derivative | 3.277 | 2.678 | 3.937 | -0.4599 | -1.292 | 0.4551 | 0.2431 |
| mlp | traditional_cfd_template_derivative | 3.31 | 2.813 | 3.979 | -0.9296 | -1.9 | 0.01056 | 0.2521 |
| derivative_gate_transformer_new | traditional_cfd_template_derivative | 3.761 | 3.075 | 4.711 | -2.049 | -2.95 | -0.8882 | 0.3092 |
| compact_waveform_transformer | traditional_cfd_template_derivative | 5.074 | 4.546 | 5.88 | 0.06178 | -0.6631 | 0.8571 | 0.4111 |
| 1d_cnn | traditional_cfd_template_derivative | 6.227 | 5.547 | 7.237 | -0.2968 | -1.264 | 0.924 | 0.4744 |

## Run-Split Stability

| run_family | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| sample_i_analysis | traditional_cfd_template_derivative | 1350 | -0.2014 | 1.098 | 0 |
| sample_i_analysis | gradient_boosted_trees | 1350 | 0.6717 | 4.541 | 0.2815 |
| sample_i_analysis | mlp | 1350 | 0.009396 | 5.501 | 0.3422 |
| sample_i_analysis | ridge | 1350 | 0.1536 | 6.468 | 0.383 |
| sample_i_analysis | derivative_gate_transformer_new | 1350 | -0.9878 | 7.158 | 0.4207 |
| sample_i_analysis | compact_waveform_transformer | 1350 | -0.1044 | 7.843 | 0.4222 |
| sample_i_analysis | 1d_cnn | 1350 | -0.2018 | 9.739 | 0.5407 |
| sample_i_calib | traditional_cfd_template_derivative | 657 | -0.4679 | 0.9956 | 0 |
| sample_i_calib | gradient_boosted_trees | 657 | 1.734 | 3.032 | 0.1963 |
| sample_i_calib | mlp | 657 | 1.253 | 3.716 | 0.2588 |
| sample_i_calib | ridge | 657 | 1.912 | 4.16 | 0.2618 |
| sample_i_calib | derivative_gate_transformer_new | 657 | 0.4374 | 4.782 | 0.2694 |
| sample_i_calib | compact_waveform_transformer | 657 | 1.519 | 5.12 | 0.3546 |
| sample_i_calib | 1d_cnn | 657 | 2.583 | 7.965 | 0.5403 |
| sample_ii_analysis | traditional_cfd_template_derivative | 2739 | 0.6172 | 0.9426 | 0 |
| sample_ii_analysis | gradient_boosted_trees | 2739 | -0.8649 | 3.749 | 0.1566 |
| sample_ii_analysis | ridge | 2739 | -0.3536 | 4.118 | 0.1986 |
| sample_ii_analysis | derivative_gate_transformer_new | 2739 | -1.97 | 4.268 | 0.2771 |
| sample_ii_analysis | mlp | 2739 | -1.004 | 4.334 | 0.2439 |
| sample_ii_analysis | compact_waveform_transformer | 2739 | 0.3572 | 6.191 | 0.4388 |
| sample_ii_analysis | 1d_cnn | 2739 | 0.02549 | 6.733 | 0.4491 |
| sample_ii_calib | traditional_cfd_template_derivative | 720 | 0.6156 | 0.5091 | 0 |
| sample_ii_calib | gradient_boosted_trees | 720 | -1.395 | 2.628 | 0.06806 |
| sample_ii_calib | ridge | 720 | -1.386 | 3.088 | 0.1333 |
| sample_ii_calib | mlp | 720 | -1.75 | 3.361 | 0.1083 |
| sample_ii_calib | derivative_gate_transformer_new | 720 | -3.066 | 3.521 | 0.2583 |
| sample_ii_calib | compact_waveform_transformer | 720 | 0.08879 | 5.279 | 0.3361 |
| sample_ii_calib | 1d_cnn | 720 | -0.9417 | 5.81 | 0.3861 |

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 2.583 | 7.965 | 0.5403 |
| 1d_cnn | 50 | 680 | -2.387 | 11.95 | 0.5221 |
| 1d_cnn | 57 | 670 | 2.191 | 8.266 | 0.5597 |
| 1d_cnn | 58 | 654 | -1.229 | 7.295 | 0.5076 |
| 1d_cnn | 60 | 720 | 1.754 | 6.04 | 0.4319 |
| 1d_cnn | 62 | 720 | 0.4299 | 6.528 | 0.4264 |
| 1d_cnn | 64 | 720 | -0.9417 | 5.81 | 0.3861 |
| 1d_cnn | 65 | 645 | -1.261 | 6.308 | 0.4341 |
| compact_waveform_transformer | 42 | 657 | 1.519 | 5.12 | 0.3546 |
| compact_waveform_transformer | 50 | 680 | -0.1093 | 11.88 | 0.4074 |
| compact_waveform_transformer | 57 | 670 | -0.06744 | 6.49 | 0.4373 |
| compact_waveform_transformer | 58 | 654 | -1.371 | 6.479 | 0.445 |
| compact_waveform_transformer | 60 | 720 | 1.605 | 6.357 | 0.4597 |
| compact_waveform_transformer | 62 | 720 | 1.017 | 6.317 | 0.4444 |
| compact_waveform_transformer | 64 | 720 | 0.08879 | 5.279 | 0.3361 |
| compact_waveform_transformer | 65 | 645 | 0.0917 | 5.653 | 0.4031 |
| derivative_gate_transformer_new | 42 | 657 | 0.4374 | 4.782 | 0.2694 |
| derivative_gate_transformer_new | 50 | 680 | -2.092 | 12.75 | 0.4147 |
| derivative_gate_transformer_new | 57 | 670 | -0.3956 | 6.016 | 0.4269 |
| derivative_gate_transformer_new | 58 | 654 | -2.978 | 4.991 | 0.3731 |
| derivative_gate_transformer_new | 60 | 720 | -1.052 | 3.853 | 0.2167 |
| derivative_gate_transformer_new | 62 | 720 | -1.59 | 4.324 | 0.2403 |
| derivative_gate_transformer_new | 64 | 720 | -3.066 | 3.521 | 0.2583 |
| derivative_gate_transformer_new | 65 | 645 | -2.452 | 3.968 | 0.2884 |
| gradient_boosted_trees | 42 | 657 | 1.734 | 3.032 | 0.1963 |
| gradient_boosted_trees | 50 | 680 | 0.8916 | 11.38 | 0.3118 |
| gradient_boosted_trees | 57 | 670 | 0.08934 | 4.491 | 0.2507 |
| gradient_boosted_trees | 58 | 654 | -2.812 | 3.984 | 0.2492 |
| gradient_boosted_trees | 60 | 720 | 0.4848 | 3.301 | 0.1292 |
| gradient_boosted_trees | 62 | 720 | -0.4021 | 3.204 | 0.09306 |
| gradient_boosted_trees | 64 | 720 | -1.395 | 2.628 | 0.06806 |
| gradient_boosted_trees | 65 | 645 | -1.754 | 3.976 | 0.1643 |
| mlp | 42 | 657 | 1.253 | 3.716 | 0.2588 |
| mlp | 50 | 680 | 0.061 | 11.2 | 0.3029 |
| mlp | 57 | 670 | -0.03794 | 5.396 | 0.3821 |
| mlp | 58 | 654 | -2.477 | 4.977 | 0.3119 |
| mlp | 60 | 720 | 0.09288 | 3.825 | 0.2069 |
| mlp | 62 | 720 | -0.4934 | 4.031 | 0.1931 |
| mlp | 64 | 720 | -1.75 | 3.361 | 0.1083 |
| mlp | 65 | 645 | -2.045 | 4.717 | 0.2729 |
| ridge | 42 | 657 | 1.912 | 4.16 | 0.2618 |
| ridge | 50 | 680 | -0.2566 | 11.34 | 0.3515 |
| ridge | 57 | 670 | 0.8453 | 5.553 | 0.4149 |
| ridge | 58 | 654 | -1.439 | 4.844 | 0.3073 |
| ridge | 60 | 720 | 0.4963 | 3.44 | 0.1361 |
| ridge | 62 | 720 | -0.3317 | 3.692 | 0.1639 |
| ridge | 64 | 720 | -1.386 | 3.088 | 0.1333 |
| ridge | 65 | 645 | -0.7756 | 3.951 | 0.1969 |
| traditional_cfd_template_derivative | 42 | 657 | -0.4679 | 0.9956 | 0 |
| traditional_cfd_template_derivative | 50 | 680 | -0.2219 | 0.4889 | 0 |
| traditional_cfd_template_derivative | 57 | 670 | 0.1268 | 1.444 | 0 |
| traditional_cfd_template_derivative | 58 | 654 | 0.9431 | 0.447 | 0 |
| traditional_cfd_template_derivative | 60 | 720 | -0.1347 | 1.192 | 0 |
| traditional_cfd_template_derivative | 62 | 720 | 0.3872 | 1.164 | 0 |
| traditional_cfd_template_derivative | 64 | 720 | 0.6156 | 0.5091 | 0 |
| traditional_cfd_template_derivative | 65 | 645 | 0.6555 | 0.3191 | 0 |

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1636 | -0.1506 | 8.82 | 0.566 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1636 | -1.782 | 6.094 | 0.4163 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1636 | -1.466 | 5.002 | 0.3191 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1636 | -0.3752 | 3.683 | 0.1791 |
| curvature_energy_bin | curved | mlp | 1636 | -0.5471 | 4.211 | 0.2396 |
| curvature_energy_bin | curved | ridge | 1636 | -0.4832 | 4.051 | 0.2433 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1636 | 0.3009 | 1.188 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1897 | 2.389 | 6.16 | 0.4644 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1897 | 1.256 | 5.936 | 0.4164 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1897 | -1.77 | 4.597 | 0.2999 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1897 | 0.1067 | 3.927 | 0.2045 |
| curvature_energy_bin | moderate | mlp | 1897 | -0.503 | 4.348 | 0.2646 |
| curvature_energy_bin | moderate | ridge | 1897 | -0.2759 | 4.381 | 0.2451 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1897 | 0.4279 | 0.9337 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1933 | -1.853 | 5.703 | 0.4066 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1933 | 1.258 | 5.484 | 0.4014 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1933 | -1.945 | 4.692 | 0.3099 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1933 | -0.603 | 3.562 | 0.1583 |
| curvature_energy_bin | smooth | mlp | 1933 | -0.7534 | 4.329 | 0.2504 |
| curvature_energy_bin | smooth | ridge | 1933 | 0.4724 | 4.118 | 0.2411 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1933 | 0.2576 | 0.9009 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1840 | -0.7521 | 6.299 | 0.4348 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1840 | 0.3425 | 5.936 | 0.3848 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1840 | -1.928 | 4.484 | 0.2761 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1840 | -0.5769 | 3.214 | 0.1196 |
| derivative_onset_bin | nominal | mlp | 1840 | -0.8158 | 4.075 | 0.2353 |
| derivative_onset_bin | nominal | ridge | 1840 | -0.6205 | 3.861 | 0.1962 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1840 | 0.4098 | 1.019 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1945 | 0.005042 | 6.982 | 0.4617 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1945 | 0.6071 | 5.801 | 0.4118 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1945 | -1.941 | 4.44 | 0.31 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1945 | -0.5335 | 3.151 | 0.1136 |
| derivative_onset_bin | sharp | mlp | 1945 | -0.6752 | 4.062 | 0.2134 |
| derivative_onset_bin | sharp | ridge | 1945 | -0.4086 | 4.037 | 0.2057 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1945 | 0.4979 | 1.007 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1681 | 1.215 | 8.951 | 0.5324 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1681 | 0.1742 | 6.422 | 0.439 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1681 | -1.318 | 5.42 | 0.3444 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1681 | 0.9114 | 4.785 | 0.3248 |
| derivative_onset_bin | slow | mlp | 1681 | -0.2736 | 4.93 | 0.3153 |
| derivative_onset_bin | slow | ridge | 1681 | 0.578 | 4.703 | 0.3379 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1681 | 0.1364 | 0.9536 | 0 |
| energy_bin | q1_low | 1d_cnn | 1419 | -2.271 | 7.409 | 0.5109 |
| energy_bin | q1_low | compact_waveform_transformer | 1419 | 0.7956 | 5.968 | 0.4271 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1419 | -1.907 | 5.208 | 0.3502 |
| energy_bin | q1_low | gradient_boosted_trees | 1419 | -0.5503 | 3.724 | 0.1875 |
| energy_bin | q1_low | mlp | 1419 | -0.46 | 4.244 | 0.2459 |
| energy_bin | q1_low | ridge | 1419 | 0.5683 | 4.211 | 0.2544 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1419 | 0.06495 | 1.021 | 0 |
| energy_bin | q2 | 1d_cnn | 1516 | -0.2295 | 5.597 | 0.3615 |
| energy_bin | q2 | compact_waveform_transformer | 1516 | 1.594 | 5.718 | 0.4208 |
| energy_bin | q2 | derivative_gate_transformer_new | 1516 | -1.811 | 4.604 | 0.3028 |
| energy_bin | q2 | gradient_boosted_trees | 1516 | -0.1506 | 3.771 | 0.1788 |
| energy_bin | q2 | mlp | 1516 | -0.8143 | 4.638 | 0.2836 |
| energy_bin | q2 | ridge | 1516 | 0.06174 | 4.262 | 0.2467 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1516 | 0.459 | 0.81 | 0 |
| energy_bin | q3 | 1d_cnn | 1393 | 3.885 | 5.217 | 0.4932 |
| energy_bin | q3 | compact_waveform_transformer | 1393 | 0.9523 | 6.023 | 0.425 |
| energy_bin | q3 | derivative_gate_transformer_new | 1393 | -1.986 | 4.552 | 0.3108 |
| energy_bin | q3 | gradient_boosted_trees | 1393 | -0.0388 | 3.755 | 0.1881 |
| energy_bin | q3 | mlp | 1393 | -0.6481 | 4.339 | 0.2556 |
| energy_bin | q3 | ridge | 1393 | -0.4811 | 4.443 | 0.262 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1393 | 0.4958 | 0.9445 | 0 |
| energy_bin | q4_high | 1d_cnn | 1138 | -2.359 | 7.975 | 0.5562 |
| energy_bin | q4_high | compact_waveform_transformer | 1138 | -2.329 | 5.222 | 0.3612 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1138 | -1.053 | 4.654 | 0.2645 |
| energy_bin | q4_high | gradient_boosted_trees | 1138 | -0.4091 | 3.248 | 0.1652 |
| energy_bin | q4_high | mlp | 1138 | -0.4374 | 3.892 | 0.2135 |
| energy_bin | q4_high | ridge | 1138 | -0.703 | 3.753 | 0.2012 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1138 | 0.2678 | 1.23 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3299 | -0.2575 | 7.025 | 0.4711 |
| late_tail_morphology | compact | compact_waveform_transformer | 3299 | 0.6022 | 6.35 | 0.4407 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3299 | -2.018 | 4.627 | 0.3262 |
| late_tail_morphology | compact | gradient_boosted_trees | 3299 | -0.634 | 3.442 | 0.1334 |
| late_tail_morphology | compact | mlp | 3299 | -0.6826 | 4.166 | 0.2307 |
| late_tail_morphology | compact | ridge | 3299 | -0.1196 | 4.168 | 0.2213 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3299 | 0.4153 | 0.9747 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 610 | -0.3252 | 5.905 | 0.3852 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 610 | -0.3749 | 4.744 | 0.3262 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 610 | -2.202 | 3.85 | 0.2459 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 610 | 0.06456 | 3.1 | 0.1459 |
| late_tail_morphology | diffuse_tail | mlp | 610 | -0.4201 | 3.913 | 0.2311 |
| late_tail_morphology | diffuse_tail | ridge | 610 | -1.084 | 3.707 | 0.2 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 610 | 0.51 | 1.064 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 379 | -3.886 | 9.759 | 0.6332 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 379 | 0.01784 | 5.867 | 0.409 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 379 | 0.2736 | 4.442 | 0.2454 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 379 | -0.5199 | 3.294 | 0.153 |
| late_tail_morphology | late_derivative_bump | mlp | 379 | -0.7014 | 3.98 | 0.2322 |
| late_tail_morphology | late_derivative_bump | ridge | 379 | -0.2256 | 3.628 | 0.1953 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 379 | -0.03273 | 1.171 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1178 | 2.369 | 7.053 | 0.4788 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1178 | 0.3874 | 5.66 | 0.3727 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1178 | -0.8833 | 5.245 | 0.3149 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1178 | 0.9179 | 5.053 | 0.3396 |
| late_tail_morphology | late_rising_tail | mlp | 1178 | -0.4577 | 5.131 | 0.3294 |
| late_tail_morphology | late_rising_tail | ridge | 1178 | 0.4857 | 4.759 | 0.3421 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1178 | 0.1286 | 0.9536 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1746 | 0.08089 | 8.706 | 0.5435 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1746 | -0.8513 | 7.268 | 0.508 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1746 | -1.7 | 5.017 | 0.3482 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1746 | 0.1578 | 4.074 | 0.2234 |
| pedestal_drift_bin | high | mlp | 1746 | 0.2563 | 4.526 | 0.2824 |
| pedestal_drift_bin | high | ridge | 1746 | 0.3313 | 4.353 | 0.2577 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1746 | 0.3071 | 0.9828 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1740 | -0.0221 | 6.558 | 0.4437 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1740 | 0.5001 | 5.425 | 0.3684 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1740 | -1.694 | 4.738 | 0.3023 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1740 | -0.4207 | 3.457 | 0.1569 |
| pedestal_drift_bin | low | mlp | 1740 | -0.8371 | 3.99 | 0.2368 |
| pedestal_drift_bin | low | ridge | 1740 | -0.4004 | 4.249 | 0.2437 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1740 | 0.3168 | 1.003 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1980 | 0.1126 | 6.553 | 0.4404 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1980 | 0.9126 | 5.344 | 0.3631 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1980 | -1.765 | 4.533 | 0.2808 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1980 | -0.3525 | 3.468 | 0.1636 |
| pedestal_drift_bin | mid | mlp | 1980 | -0.8367 | 4.205 | 0.2389 |
| pedestal_drift_bin | mid | ridge | 1980 | -0.2389 | 4.178 | 0.2298 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1980 | 0.3626 | 1.024 | 0 |
| pid_sideband | central | 1d_cnn | 3730 | 0.1625 | 6.438 | 0.4282 |
| pid_sideband | central | compact_waveform_transformer | 3730 | 0.9126 | 5.396 | 0.3718 |
| pid_sideband | central | derivative_gate_transformer_new | 3730 | -1.59 | 4.688 | 0.2882 |
| pid_sideband | central | gradient_boosted_trees | 3730 | -0.2627 | 3.578 | 0.1748 |
| pid_sideband | central | mlp | 3730 | -0.606 | 4.27 | 0.248 |
| pid_sideband | central | ridge | 3730 | -0.1191 | 4.238 | 0.2426 |
| pid_sideband | central | traditional_cfd_template_derivative | 3730 | 0.2853 | 0.9887 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 900 | -0.2759 | 10.93 | 0.6433 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 900 | -4.142 | 7.427 | 0.6067 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 900 | -2.782 | 5.549 | 0.4422 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 900 | -0.3163 | 4.103 | 0.2256 |
| pid_sideband | high_duplicate | mlp | 900 | -0.1464 | 4.473 | 0.2756 |
| pid_sideband | high_duplicate | ridge | 900 | -0.08208 | 4.635 | 0.28 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 900 | 0.3977 | 1.02 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 836 | -0.4036 | 7.529 | 0.4988 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 836 | 1.038 | 5.44 | 0.3756 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 836 | -1.623 | 4.152 | 0.2596 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 836 | -0.2878 | 3.513 | 0.1579 |
| pid_sideband | low_duplicate | mlp | 836 | -0.8112 | 4.242 | 0.2452 |
| pid_sideband | low_duplicate | ridge | 836 | -0.3274 | 3.914 | 0.2057 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 836 | 0.4664 | 1.026 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1701 | -1.177 | 7.147 | 0.4815 |
| pileup_separation_bin | close | compact_waveform_transformer | 1701 | 0.1835 | 5.408 | 0.3616 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1701 | -1.971 | 4.489 | 0.301 |
| pileup_separation_bin | close | gradient_boosted_trees | 1701 | -0.6157 | 3.3 | 0.1211 |
| pileup_separation_bin | close | mlp | 1701 | -0.7278 | 4.143 | 0.2228 |
| pileup_separation_bin | close | ridge | 1701 | -0.6323 | 3.852 | 0.2175 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1701 | 0.4994 | 1.041 | 0 |
| pileup_separation_bin | late | 1d_cnn | 3 | -1.218 | 0.8958 | 0 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -8.124 | 1.645 | 0.6667 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 3 | -3.978 | 1.64 | 0 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | -1.401 | 3.02 | 0.3333 |
| pileup_separation_bin | late | mlp | 3 | 1.196 | 1.73 | 0 |
| pileup_separation_bin | late | ridge | 3 | -2.784 | 1.622 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 3 | -0.513 | 0.9181 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1171 | 2.503 | 7.685 | 0.5568 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1171 | -2.99 | 6.21 | 0.4885 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1171 | -2.033 | 5.116 | 0.3723 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1171 | -0.6119 | 3.522 | 0.1503 |
| pileup_separation_bin | mid | mlp | 1171 | -0.7063 | 4.206 | 0.2306 |
| pileup_separation_bin | mid | ridge | 1171 | -0.4641 | 4.439 | 0.2519 |
| pileup_separation_bin | mid | traditional_cfd_template_derivative | 1171 | 0.5651 | 1.102 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2591 | -0.1301 | 6.643 | 0.433 |
| pileup_separation_bin | none | compact_waveform_transformer | 2591 | 1.807 | 5.287 | 0.4083 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2591 | -1.459 | 4.549 | 0.2864 |
| pileup_separation_bin | none | gradient_boosted_trees | 2591 | 0.146 | 3.965 | 0.2331 |
| pileup_separation_bin | none | mlp | 2591 | -0.46 | 4.545 | 0.2814 |
| pileup_separation_bin | none | ridge | 2591 | 0.3747 | 4.153 | 0.2563 |
| pileup_separation_bin | none | traditional_cfd_template_derivative | 2591 | 0.1964 | 0.8946 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1860 | -0.9908 | 8.183 | 0.5188 |
| pulse_shape_class | compact | compact_waveform_transformer | 1860 | -0.7773 | 7.045 | 0.5086 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1860 | -2.451 | 4.924 | 0.4145 |
| pulse_shape_class | compact | gradient_boosted_trees | 1860 | -0.8777 | 3.863 | 0.1645 |
| pulse_shape_class | compact | mlp | 1860 | -0.7569 | 4.401 | 0.2484 |
| pulse_shape_class | compact | ridge | 1860 | 0.2896 | 4.555 | 0.2683 |
| pulse_shape_class | compact | traditional_cfd_template_derivative | 1860 | 0.382 | 0.9859 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1812 | 1.025 | 6.945 | 0.4459 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1812 | 0.1251 | 5.418 | 0.3549 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1812 | -1.616 | 4.808 | 0.2886 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1812 | 0.5075 | 4.42 | 0.2704 |
| pulse_shape_class | late_tail | mlp | 1812 | -0.4577 | 4.73 | 0.2936 |
| pulse_shape_class | late_tail | ridge | 1812 | -0.1791 | 4.508 | 0.2908 |
| pulse_shape_class | late_tail | traditional_cfd_template_derivative | 1812 | 0.2597 | 1.013 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1794 | 0.1236 | 6.38 | 0.4571 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1794 | 1.237 | 5.23 | 0.3668 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1794 | -1.239 | 4.129 | 0.2207 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1794 | -0.4483 | 2.904 | 0.1065 |
| pulse_shape_class | nominal | mlp | 1794 | -0.6502 | 3.87 | 0.214 |
| pulse_shape_class | nominal | ridge | 1794 | -0.4064 | 3.58 | 0.1689 |
| pulse_shape_class | nominal | traditional_cfd_template_derivative | 1794 | 0.3986 | 0.9712 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3966 | 0.4345 | 7.464 | 0.4846 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3966 | 0.2543 | 6.172 | 0.4218 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3966 | -1.961 | 4.733 | 0.3192 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3966 | -0.35 | 3.795 | 0.1861 |
| saturation_onset_bin | linear | mlp | 3966 | -0.6451 | 4.341 | 0.2539 |
| saturation_onset_bin | linear | ridge | 3966 | -0.2015 | 4.331 | 0.2509 |
| saturation_onset_bin | linear | traditional_cfd_template_derivative | 3966 | 0.3843 | 1.01 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1500 | -0.8745 | 6.607 | 0.4473 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1500 | 0.8095 | 5.574 | 0.3827 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1500 | -1.122 | 4.673 | 0.2827 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1500 | -0.1073 | 3.485 | 0.166 |
| saturation_onset_bin | near_saturation | mlp | 1500 | -0.5295 | 4.222 | 0.2473 |
| saturation_onset_bin | near_saturation | ridge | 1500 | 0.08094 | 4.145 | 0.2227 |
| saturation_onset_bin | near_saturation | traditional_cfd_template_derivative | 1500 | 0.1632 | 0.9777 | 0 |

Compressed axis view:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | 1d_cnn | 3 | smooth | 5.703 | curved | 8.82 | 3.117 |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 5.484 | curved | 6.094 | 0.6098 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | moderate | 4.597 | curved | 5.002 | 0.4047 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.562 | moderate | 3.927 | 0.365 |
| curvature_energy_bin | ridge | 3 | curved | 4.051 | moderate | 4.381 | 0.3304 |
| curvature_energy_bin | traditional_cfd_template_derivative | 3 | smooth | 0.9009 | curved | 1.188 | 0.287 |
| curvature_energy_bin | mlp | 3 | curved | 4.211 | moderate | 4.348 | 0.1367 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 6.299 | slow | 8.951 | 2.652 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 3.151 | slow | 4.785 | 1.634 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | sharp | 4.44 | slow | 5.42 | 0.9803 |
| derivative_onset_bin | mlp | 3 | sharp | 4.062 | slow | 4.93 | 0.868 |
| derivative_onset_bin | ridge | 3 | nominal | 3.861 | slow | 4.703 | 0.8425 |
| derivative_onset_bin | compact_waveform_transformer | 3 | sharp | 5.801 | slow | 6.422 | 0.6216 |
| derivative_onset_bin | traditional_cfd_template_derivative | 3 | slow | 0.9536 | nominal | 1.019 | 0.06539 |
| energy_bin | 1d_cnn | 4 | q3 | 5.217 | q4_high | 7.975 | 2.758 |
| energy_bin | compact_waveform_transformer | 4 | q4_high | 5.222 | q3 | 6.023 | 0.8014 |
| energy_bin | mlp | 4 | q4_high | 3.892 | q2 | 4.638 | 0.7458 |
| energy_bin | ridge | 4 | q4_high | 3.753 | q3 | 4.443 | 0.6897 |
| energy_bin | derivative_gate_transformer_new | 4 | q3 | 4.552 | q1_low | 5.208 | 0.6561 |
| energy_bin | gradient_boosted_trees | 4 | q4_high | 3.248 | q2 | 3.771 | 0.5233 |
| energy_bin | traditional_cfd_template_derivative | 4 | q2 | 0.81 | q4_high | 1.23 | 0.4203 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 5.905 | late_derivative_bump | 9.759 | 3.854 |
| late_tail_morphology | gradient_boosted_trees | 4 | diffuse_tail | 3.1 | late_rising_tail | 5.053 | 1.953 |
| late_tail_morphology | compact_waveform_transformer | 4 | diffuse_tail | 4.744 | compact | 6.35 | 1.606 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 3.85 | late_rising_tail | 5.245 | 1.395 |
| late_tail_morphology | mlp | 4 | diffuse_tail | 3.913 | late_rising_tail | 5.131 | 1.218 |
| late_tail_morphology | ridge | 4 | late_derivative_bump | 3.628 | late_rising_tail | 4.759 | 1.131 |
| late_tail_morphology | traditional_cfd_template_derivative | 4 | late_rising_tail | 0.9536 | late_derivative_bump | 1.171 | 0.2172 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 6.553 | high | 8.706 | 2.154 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.344 | high | 7.268 | 1.924 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.457 | high | 4.074 | 0.6171 |
| pedestal_drift_bin | mlp | 3 | low | 3.99 | high | 4.526 | 0.5361 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.533 | high | 5.017 | 0.4841 |
| pedestal_drift_bin | ridge | 3 | mid | 4.178 | high | 4.353 | 0.1749 |
| pedestal_drift_bin | traditional_cfd_template_derivative | 3 | high | 0.9828 | mid | 1.024 | 0.04118 |
| pid_sideband | 1d_cnn | 3 | central | 6.438 | high_duplicate | 10.93 | 4.493 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.396 | high_duplicate | 7.427 | 2.03 |
| pid_sideband | derivative_gate_transformer_new | 3 | low_duplicate | 4.152 | high_duplicate | 5.549 | 1.397 |
| pid_sideband | ridge | 3 | low_duplicate | 3.914 | high_duplicate | 4.635 | 0.7201 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.513 | high_duplicate | 4.103 | 0.5895 |
| pid_sideband | mlp | 3 | low_duplicate | 4.242 | high_duplicate | 4.473 | 0.2313 |
| pid_sideband | traditional_cfd_template_derivative | 3 | central | 0.9887 | low_duplicate | 1.026 | 0.03752 |
| pileup_separation_bin | 1d_cnn | 4 | late | 0.8958 | mid | 7.685 | 6.789 |
| pileup_separation_bin | compact_waveform_transformer | 4 | late | 1.645 | mid | 6.21 | 4.565 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | late | 1.64 | mid | 5.116 | 3.475 |
| pileup_separation_bin | ridge | 4 | late | 1.622 | mid | 4.439 | 2.817 |
| pileup_separation_bin | mlp | 4 | late | 1.73 | none | 4.545 | 2.815 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 3.02 | none | 3.965 | 0.9448 |
| pileup_separation_bin | traditional_cfd_template_derivative | 4 | none | 0.8946 | mid | 1.102 | 0.2078 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.23 | compact | 7.045 | 1.815 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 6.38 | compact | 8.183 | 1.803 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.904 | late_tail | 4.42 | 1.515 |
| pulse_shape_class | ridge | 3 | nominal | 3.58 | compact | 4.555 | 0.9744 |
| pulse_shape_class | mlp | 3 | nominal | 3.87 | late_tail | 4.73 | 0.8601 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.129 | compact | 4.924 | 0.7956 |
| pulse_shape_class | traditional_cfd_template_derivative | 3 | nominal | 0.9712 | late_tail | 1.013 | 0.04135 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 6.607 | linear | 7.464 | 0.8572 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.574 | linear | 6.172 | 0.5981 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.485 | linear | 3.795 | 0.3095 |
| saturation_onset_bin | ridge | 2 | near_saturation | 4.145 | linear | 4.331 | 0.1863 |
| saturation_onset_bin | mlp | 2 | near_saturation | 4.222 | linear | 4.341 | 0.1186 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 4.673 | linear | 4.733 | 0.05937 |
| saturation_onset_bin | traditional_cfd_template_derivative | 2 | near_saturation | 0.9777 | linear | 1.01 | 0.03204 |

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_derivative_features | 33 | -0.1966 | 3.738 | 3.223 | 4.242 | -0.006441 | 0.1793 |
| full_derivative_gradient_boosted_trees | 76 | -0.2048 | 3.745 | 3.297 | 4.17 | 0 | 0.1791 |
| amplitude_cfd_no_derivative | 5 | 0.1396 | 4.207 | 3.799 | 4.833 | 0.4622 | 0.2413 |
| derivative_only | 43 | 0.05444 | 4.225 | 3.782 | 4.876 | 0.4804 | 0.2404 |
| late_tail_curvature_window_only | 17 | 0.2273 | 4.652 | 4.169 | 5.498 | 0.9076 | 0.2872 |
| onset_derivative_window_only | 14 | -0.07005 | 4.781 | 4.039 | 6.233 | 1.036 | 0.3052 |
| pretrigger_derivative_only | 7 | -3.782 | 16.81 | 15.78 | 17.92 | 13.06 | 0.5679 |

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

Runtime was `75.4 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.

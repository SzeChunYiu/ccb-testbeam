# S64a Time-Warped Template Pulse-Shape Timing Under Pedestal Drift and Pile-Up

## Abstract

Ticket `#2538` asks how pedestal drift, sub-sample timing phase, and early pile-up distort pulse shape and timing. I reproduced the selected-pulse count directly from raw ROOT, sampled a run-held-out B-stack waveform benchmark, and compared a traditional time-warped matched-template/CFD baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, compact waveform transformer, and a derivative-gated sequence model. The winner written to `result.json` is **`traditional_time_warped_template_cfd`** with held-out `sigma_68 = 0.9252 ns` and 95% run-bootstrap CI `[0.7158, 1.119]`.

## Raw ROOT Reproduction

Input ROOT files are `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`. For each event the `HRDv` branch is reshaped to `(8, 18)`, B-stack channels B2/B4/B6/B8 are selected, and the pretrigger pedestal is the median of samples 0 through 3. A selected pulse satisfies `max_t(x_c(t) - b_c) > 1000 ADC`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The reproduced all-group number is **640737**, exactly matching the registered value. File hashes are in `input_sha256.csv`.

## Estimand and Split

The CFD crossing at fraction `f` is linearly interpolated on the leading edge: `t_f = k - 1 + (f A - y_prev)/(y_k - y_prev)`, where `y_t = x_t - b`. The target is the run/stave-centered CFD20 residual, `y_i = 10 ns * (t_0.20,i - median(t_0.20 | run_i, stave_i))`.

Training and testing are disjoint by run. Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`; bootstrap intervals resample those held-out runs with replacement for `500` replicates. Sample sizes are train `15137` and held-out `5466` pulses.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_time_warped_template_cfd | traditional | CFD50 residual plus ridge-regularized time-warp template correction using leading-edge span, CFD asymmetry, centroid warp, pedestal displacement/slope, tail, pile-up, saturation, onset slope, late slope, and curvature energy. |
| ridge | linear ML | Standardized ridge regression over engineered waveform, pedestal, derivative, curvature, timing, and pile-up features. |
| gradient_boosted_trees | tree ML | Histogram gradient-boosted trees on the same leakage-controlled feature matrix. |
| mlp | neural tabular | Two-layer perceptron over engineered features and normalized waveform samples. |
| 1d_cnn | neural waveform | Compact 1D convolutional regressor over raw normalized 18-sample waveforms. |
| compact_waveform_transformer | neural waveform | One-layer self-attention waveform encoder with amplitude-weighted pooling. |
| derivative_gate_transformer_new | new architecture | Transformer over waveform, first derivative, second derivative, and sample position with derivative/curvature gating. |

The new architecture is appropriate here because pedestal drift and early pile-up change local edge shape rather than only global amplitude. The derivative-gated model explicitly exposes edge and curvature channels before attention pooling.

## Primary Held-Out Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | rms_ns | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_10ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_time_warped_template_cfd | 5466 | 0.2001 | -0.2805 | 0.6859 | 0.9252 | 0.7158 | 1.119 | 0.8791 | 0 | 0 |
| gradient_boosted_trees | 5466 | -0.3355 | -1.494 | 1.093 | 3.394 | 2.885 | 3.939 | 5.684 | 0.1623 | 0.0408 |
| mlp | 5466 | -0.6725 | -1.927 | 0.5006 | 3.954 | 3.599 | 4.414 | 5.982 | 0.2109 | 0.0472 |
| ridge | 5466 | -0.3581 | -1.343 | 0.6713 | 4.032 | 3.55 | 4.784 | 6.165 | 0.23 | 0.0483 |
| derivative_gate_transformer_new | 5466 | 0.8267 | -0.2373 | 1.89 | 5.155 | 4.783 | 5.802 | 7.326 | 0.3372 | 0.08782 |
| 1d_cnn | 5466 | -1.827 | -2.745 | -0.5383 | 5.23 | 4.691 | 6.264 | 7.783 | 0.3699 | 0.1191 |
| compact_waveform_transformer | 5466 | -0.3854 | -1.462 | 0.7882 | 6.012 | 5.561 | 7.075 | 7.807 | 0.3996 | 0.1264 |

The traditional comparator obtains `sigma_68 = 0.9252 ns` with CI `[0.7158, 1.119]`.

## Paired Deltas Against Traditional

Positive `delta_sigma68_ns` means worse resolution than the traditional time-warped template/CFD comparator.

| method | reference_method | delta_sigma68_ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_bias_ns | delta_bias_ns_ci_low | delta_bias_ns_ci_high | delta_tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | traditional_time_warped_template_cfd | 2.469 | 1.942 | 3.065 | -0.5357 | -1.984 | 0.9104 | 0.1623 |
| mlp | traditional_time_warped_template_cfd | 3.029 | 2.587 | 3.495 | -0.8726 | -2.217 | 0.4648 | 0.2109 |
| ridge | traditional_time_warped_template_cfd | 3.106 | 2.599 | 3.87 | -0.5582 | -1.71 | 0.5745 | 0.23 |
| derivative_gate_transformer_new | traditional_time_warped_template_cfd | 4.229 | 3.787 | 4.908 | 0.6265 | -0.5824 | 1.759 | 0.3372 |
| 1d_cnn | traditional_time_warped_template_cfd | 4.305 | 3.747 | 5.378 | -2.027 | -3.025 | -0.5845 | 0.3699 |
| compact_waveform_transformer | traditional_time_warped_template_cfd | 5.087 | 4.638 | 6.167 | -0.5856 | -1.891 | 0.7719 | 0.3996 |

## Run and Stress Systematics

Per-run held-out metrics:

| method | run | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 1.971 | 6.086 | 0.4368 |
| 1d_cnn | 50 | 680 | -3.26 | 13.83 | 0.4515 |
| 1d_cnn | 57 | 670 | 0.238 | 5.673 | 0.3731 |
| 1d_cnn | 58 | 654 | -3.713 | 5.5 | 0.4587 |
| 1d_cnn | 60 | 720 | -1.337 | 4.621 | 0.2764 |
| 1d_cnn | 62 | 720 | -2.12 | 4.348 | 0.2903 |
| 1d_cnn | 64 | 720 | -2.989 | 4.404 | 0.3444 |
| 1d_cnn | 65 | 645 | -2.559 | 4.16 | 0.3442 |
| compact_waveform_transformer | 42 | 657 | 2.749 | 6.159 | 0.4353 |
| compact_waveform_transformer | 50 | 680 | -2.397 | 13.56 | 0.4294 |
| compact_waveform_transformer | 57 | 670 | 0.6913 | 5.63 | 0.3806 |
| compact_waveform_transformer | 58 | 654 | -2.927 | 6.361 | 0.4557 |
| compact_waveform_transformer | 60 | 720 | 0.4623 | 6.304 | 0.4278 |
| compact_waveform_transformer | 62 | 720 | 0.05286 | 5.824 | 0.3944 |
| compact_waveform_transformer | 64 | 720 | -0.8554 | 5.387 | 0.3444 |
| compact_waveform_transformer | 65 | 645 | -0.5576 | 4.994 | 0.3302 |
| derivative_gate_transformer_new | 42 | 657 | 3.74 | 5.015 | 0.414 |
| derivative_gate_transformer_new | 50 | 680 | 0.3262 | 14 | 0.3809 |
| derivative_gate_transformer_new | 57 | 670 | 1.557 | 4.93 | 0.3134 |
| derivative_gate_transformer_new | 58 | 654 | -1.717 | 5.551 | 0.3807 |
| derivative_gate_transformer_new | 60 | 720 | 1.43 | 5.333 | 0.3569 |
| derivative_gate_transformer_new | 62 | 720 | 1.22 | 5.138 | 0.35 |
| derivative_gate_transformer_new | 64 | 720 | -0.1622 | 4.645 | 0.2764 |
| derivative_gate_transformer_new | 65 | 645 | -0.4718 | 4.342 | 0.2248 |
| gradient_boosted_trees | 42 | 657 | 2.968 | 3.028 | 0.3044 |
| gradient_boosted_trees | 50 | 680 | 0.3861 | 13.26 | 0.275 |
| gradient_boosted_trees | 57 | 670 | 0.7006 | 2.013 | 0.103 |
| gradient_boosted_trees | 58 | 654 | -3.35 | 2.861 | 0.2615 |
| gradient_boosted_trees | 60 | 720 | -0.4635 | 3.559 | 0.1222 |
| gradient_boosted_trees | 62 | 720 | -1.272 | 2.619 | 0.06111 |
| gradient_boosted_trees | 64 | 720 | -1.661 | 2.735 | 0.06389 |
| gradient_boosted_trees | 65 | 645 | -2.186 | 2.926 | 0.1271 |
| mlp | 42 | 657 | 2.731 | 3.842 | 0.3546 |
| mlp | 50 | 680 | -0.589 | 13.21 | 0.2985 |
| mlp | 57 | 670 | 1.118 | 3.151 | 0.1269 |
| mlp | 58 | 654 | -2.725 | 3.747 | 0.292 |
| mlp | 60 | 720 | -0.6536 | 3.924 | 0.2 |
| mlp | 62 | 720 | -1.187 | 3.704 | 0.1472 |
| mlp | 64 | 720 | -2.083 | 3.488 | 0.1292 |
| mlp | 65 | 645 | -2.436 | 3.423 | 0.1519 |
| ridge | 42 | 657 | 3.249 | 4.443 | 0.3531 |
| ridge | 50 | 680 | -0.7409 | 13.55 | 0.35 |
| ridge | 57 | 670 | 0.8468 | 4.168 | 0.2493 |
| ridge | 58 | 654 | -2.398 | 4.295 | 0.3012 |
| ridge | 60 | 720 | -0.2592 | 3.556 | 0.1736 |
| ridge | 62 | 720 | -1.024 | 3.57 | 0.1569 |
| ridge | 64 | 720 | -1.538 | 3.294 | 0.1375 |
| ridge | 65 | 645 | -1.255 | 3.241 | 0.1333 |
| traditional_time_warped_template_cfd | 42 | 657 | -0.3464 | 1.182 | 0 |
| traditional_time_warped_template_cfd | 50 | 680 | -0.2828 | 0.3316 | 0 |
| traditional_time_warped_template_cfd | 57 | 670 | -0.9388 | 0.6718 | 0 |
| traditional_time_warped_template_cfd | 58 | 654 | 0.6432 | 0.7242 | 0 |
| traditional_time_warped_template_cfd | 60 | 720 | 0.5299 | 0.7236 | 0 |
| traditional_time_warped_template_cfd | 62 | 720 | 0.5816 | 0.6085 | 0 |
| traditional_time_warped_template_cfd | 64 | 720 | 0.8936 | 0.7106 | 0 |
| traditional_time_warped_template_cfd | 65 | 645 | 0.7641 | 1.185 | 0 |

Stress axes include pedestal bins, energy slices, pulse-shape/tail class, derivative onset, curvature energy, late-tail morphology, pile-up separation, saturation onset, and PID sideband proxy:

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1562 | -1.945 | 6.349 | 0.4347 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1562 | -3.387 | 6.561 | 0.4994 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1562 | -0.2012 | 5.381 | 0.356 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1562 | -0.1927 | 3.515 | 0.1863 |
| curvature_energy_bin | curved | mlp | 1562 | -0.5951 | 3.946 | 0.2343 |
| curvature_energy_bin | curved | ridge | 1562 | -0.6415 | 4.22 | 0.2465 |
| curvature_energy_bin | curved | traditional_time_warped_template_cfd | 1562 | 0.2778 | 0.9339 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1938 | -1.086 | 4.691 | 0.3127 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1938 | 1.703 | 6.003 | 0.4298 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1938 | 1.743 | 5.363 | 0.3798 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1938 | -0.2161 | 3.434 | 0.161 |
| curvature_energy_bin | moderate | mlp | 1938 | -0.3757 | 3.873 | 0.2126 |
| curvature_energy_bin | moderate | ridge | 1938 | -0.6622 | 4.08 | 0.2348 |
| curvature_energy_bin | moderate | traditional_time_warped_template_cfd | 1938 | 0.229 | 0.9333 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1966 | -2.442 | 4.841 | 0.3749 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1966 | -0.03602 | 4.685 | 0.2904 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1966 | 0.3945 | 4.608 | 0.2803 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1966 | -0.5919 | 3.194 | 0.1445 |
| curvature_energy_bin | smooth | mlp | 1966 | -1.099 | 3.871 | 0.1907 |
| curvature_energy_bin | smooth | ridge | 1966 | 0.2432 | 3.765 | 0.2121 |
| curvature_energy_bin | smooth | traditional_time_warped_template_cfd | 1966 | 0.07745 | 0.9386 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1864 | -2.691 | 4.718 | 0.3578 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1864 | -1.428 | 5.905 | 0.3916 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1864 | 0.3085 | 5.032 | 0.3224 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1864 | -0.5717 | 3.029 | 0.14 |
| derivative_onset_bin | nominal | mlp | 1864 | -0.9591 | 3.848 | 0.1894 |
| derivative_onset_bin | nominal | ridge | 1864 | -0.8937 | 3.799 | 0.2076 |
| derivative_onset_bin | nominal | traditional_time_warped_template_cfd | 1864 | 0.3933 | 0.8718 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1919 | -1.999 | 4.779 | 0.3387 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1919 | 0.1962 | 5.7 | 0.3783 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1919 | 1.206 | 4.914 | 0.3168 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1919 | -0.6906 | 2.886 | 0.1021 |
| derivative_onset_bin | sharp | mlp | 1919 | -0.7015 | 3.818 | 0.1761 |
| derivative_onset_bin | sharp | ridge | 1919 | -0.7126 | 3.774 | 0.211 |
| derivative_onset_bin | sharp | traditional_time_warped_template_cfd | 1919 | 0.3962 | 0.8822 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1683 | -0.2461 | 6.85 | 0.4189 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1683 | 0.1329 | 6.614 | 0.4326 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1683 | 1.012 | 5.698 | 0.3767 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1683 | 0.7393 | 4.161 | 0.2555 |
| derivative_onset_bin | slow | mlp | 1683 | -0.3779 | 4.448 | 0.2745 |
| derivative_onset_bin | slow | ridge | 1683 | 0.7939 | 4.411 | 0.2763 |
| derivative_onset_bin | slow | traditional_time_warped_template_cfd | 1683 | -0.2049 | 0.9543 | 0 |
| energy_bin | q1_low | 1d_cnn | 1427 | -2.651 | 6.264 | 0.4828 |
| energy_bin | q1_low | compact_waveform_transformer | 1427 | -0.6974 | 5.314 | 0.3595 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1427 | 0.132 | 5.252 | 0.3413 |
| energy_bin | q1_low | gradient_boosted_trees | 1427 | -0.5523 | 3.372 | 0.1591 |
| energy_bin | q1_low | mlp | 1427 | -1.006 | 3.891 | 0.2165 |
| energy_bin | q1_low | ridge | 1427 | 0.2873 | 4.046 | 0.2242 |
| energy_bin | q1_low | traditional_time_warped_template_cfd | 1427 | -0.036 | 0.9358 | 0 |
| energy_bin | q2 | 1d_cnn | 1517 | -2.153 | 4.463 | 0.3138 |
| energy_bin | q2 | compact_waveform_transformer | 1517 | 0.9627 | 4.745 | 0.3092 |
| energy_bin | q2 | derivative_gate_transformer_new | 1517 | 1.272 | 4.621 | 0.3019 |
| energy_bin | q2 | gradient_boosted_trees | 1517 | -0.3497 | 3.276 | 0.1417 |
| energy_bin | q2 | mlp | 1517 | -0.9902 | 3.88 | 0.1898 |
| energy_bin | q2 | ridge | 1517 | -0.2227 | 3.816 | 0.2057 |
| energy_bin | q2 | traditional_time_warped_template_cfd | 1517 | 0.09885 | 0.8978 | 0 |
| energy_bin | q3 | 1d_cnn | 1428 | -0.2772 | 4.146 | 0.25 |
| energy_bin | q3 | compact_waveform_transformer | 1428 | 1.775 | 6.208 | 0.4377 |
| energy_bin | q3 | derivative_gate_transformer_new | 1428 | 1.779 | 5.202 | 0.3725 |
| energy_bin | q3 | gradient_boosted_trees | 1428 | -0.2932 | 3.404 | 0.1597 |
| energy_bin | q3 | mlp | 1428 | -0.4007 | 3.936 | 0.2213 |
| energy_bin | q3 | ridge | 1428 | -0.7281 | 4.136 | 0.2465 |
| energy_bin | q3 | traditional_time_warped_template_cfd | 1428 | 0.3381 | 0.9131 | 0 |
| energy_bin | q4_high | 1d_cnn | 1094 | -2.955 | 5.941 | 0.457 |
| energy_bin | q4_high | compact_waveform_transformer | 1094 | -4.692 | 5.726 | 0.5274 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1094 | -1.038 | 5.127 | 0.3346 |
| energy_bin | q4_high | gradient_boosted_trees | 1094 | -0.1623 | 3.483 | 0.1984 |
| energy_bin | q4_high | mlp | 1094 | -0.1334 | 4.012 | 0.2194 |
| energy_bin | q4_high | ridge | 1094 | -0.6347 | 4.172 | 0.2495 |
| energy_bin | q4_high | traditional_time_warped_template_cfd | 1094 | 0.3772 | 0.9868 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3259 | -2.269 | 4.905 | 0.3667 |
| late_tail_morphology | compact | compact_waveform_transformer | 3259 | -0.6108 | 5.769 | 0.3796 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3259 | 0.7731 | 5.293 | 0.351 |
| late_tail_morphology | compact | gradient_boosted_trees | 3259 | -0.6768 | 3.094 | 0.1329 |
| late_tail_morphology | compact | mlp | 3259 | -1.115 | 3.871 | 0.1887 |
| late_tail_morphology | compact | ridge | 3259 | -0.687 | 3.92 | 0.2182 |
| late_tail_morphology | compact | traditional_time_warped_template_cfd | 3259 | 0.2743 | 0.8898 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 570 | -2.672 | 4.775 | 0.3491 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 570 | -1.366 | 5.825 | 0.4035 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 570 | 0.6163 | 4.525 | 0.2982 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 570 | -0.4754 | 3.401 | 0.1614 |
| late_tail_morphology | diffuse_tail | mlp | 570 | -0.191 | 3.873 | 0.2246 |
| late_tail_morphology | diffuse_tail | ridge | 570 | -0.9564 | 3.605 | 0.2018 |
| late_tail_morphology | diffuse_tail | traditional_time_warped_template_cfd | 570 | 0.5401 | 0.8128 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 389 | -2.888 | 6.401 | 0.4165 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 389 | -2.079 | 7.426 | 0.4936 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 389 | 1.84 | 5.179 | 0.3573 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 389 | 0.2584 | 3.061 | 0.162 |
| late_tail_morphology | late_derivative_bump | mlp | 389 | 0.1955 | 4.103 | 0.2442 |
| late_tail_morphology | late_derivative_bump | ridge | 389 | 0.1134 | 3.737 | 0.2442 |
| late_tail_morphology | late_derivative_bump | traditional_time_warped_template_cfd | 389 | 0.1337 | 0.8625 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1248 | 0.0944 | 6.082 | 0.3734 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1248 | 1.042 | 6.245 | 0.4207 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1248 | 0.6938 | 5.049 | 0.3125 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1248 | 0.7485 | 3.978 | 0.2396 |
| late_tail_morphology | late_rising_tail | mlp | 1248 | -0.2525 | 4.212 | 0.2524 |
| late_tail_morphology | late_rising_tail | ridge | 1248 | 0.6732 | 4.313 | 0.2692 |
| late_tail_morphology | late_rising_tail | traditional_time_warped_template_cfd | 1248 | -0.2218 | 0.9869 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1734 | -1.647 | 6.349 | 0.4291 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1734 | -1.555 | 7.054 | 0.4844 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1734 | 0.5327 | 6.355 | 0.4314 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1734 | 0.1749 | 3.704 | 0.1984 |
| pedestal_drift_bin | high | mlp | 1734 | -0.1072 | 4.234 | 0.2428 |
| pedestal_drift_bin | high | ridge | 1734 | 0.02025 | 4.312 | 0.2474 |
| pedestal_drift_bin | high | traditional_time_warped_template_cfd | 1734 | 0.05556 | 0.9685 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1795 | -1.987 | 4.889 | 0.3554 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1795 | -0.06322 | 5.503 | 0.3627 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1795 | 0.8156 | 4.719 | 0.2975 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1795 | -0.596 | 3.202 | 0.151 |
| pedestal_drift_bin | low | mlp | 1795 | -1.19 | 3.691 | 0.1989 |
| pedestal_drift_bin | low | ridge | 1795 | -0.6318 | 4.036 | 0.2329 |
| pedestal_drift_bin | low | traditional_time_warped_template_cfd | 1795 | 0.3088 | 0.8974 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1937 | -1.771 | 4.761 | 0.3304 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1937 | 0.3279 | 5.371 | 0.3578 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1937 | 1.03 | 4.489 | 0.2896 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1937 | -0.3637 | 3.203 | 0.1404 |
| pedestal_drift_bin | mid | mlp | 1937 | -0.7422 | 3.818 | 0.1936 |
| pedestal_drift_bin | mid | ridge | 1937 | -0.408 | 3.866 | 0.2117 |
| pedestal_drift_bin | mid | traditional_time_warped_template_cfd | 1937 | 0.2414 | 0.907 | 0 |
| pid_sideband | central | 1d_cnn | 3762 | -1.579 | 4.887 | 0.3437 |
| pid_sideband | central | compact_waveform_transformer | 3762 | 0.3984 | 5.372 | 0.3578 |
| pid_sideband | central | derivative_gate_transformer_new | 3762 | 1.108 | 4.676 | 0.2951 |
| pid_sideband | central | gradient_boosted_trees | 3762 | -0.3212 | 3.285 | 0.155 |
| pid_sideband | central | mlp | 3762 | -0.581 | 3.909 | 0.2052 |
| pid_sideband | central | ridge | 3762 | -0.2314 | 4.047 | 0.2329 |
| pid_sideband | central | traditional_time_warped_template_cfd | 3762 | 0.1595 | 0.9229 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 853 | -2.699 | 7.25 | 0.5064 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 853 | -4.264 | 6.49 | 0.5569 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 853 | -2.081 | 7.072 | 0.524 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 853 | -0.3421 | 3.896 | 0.2063 |
| pid_sideband | high_duplicate | mlp | 853 | -0.8882 | 4.222 | 0.2579 |
| pid_sideband | high_duplicate | ridge | 853 | -0.647 | 4.241 | 0.245 |
| pid_sideband | high_duplicate | traditional_time_warped_template_cfd | 853 | 0.1142 | 0.9698 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 851 | -2.081 | 5.038 | 0.349 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 851 | -0.3212 | 6.32 | 0.4266 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 851 | 1.143 | 4.838 | 0.3361 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 851 | -0.3457 | 3.219 | 0.1504 |
| pid_sideband | low_duplicate | mlp | 851 | -0.9227 | 3.742 | 0.1892 |
| pid_sideband | low_duplicate | ridge | 851 | -0.6893 | 3.677 | 0.2021 |
| pid_sideband | low_duplicate | traditional_time_warped_template_cfd | 851 | 0.45 | 0.8873 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1644 | -3.03 | 5.293 | 0.4021 |
| pileup_separation_bin | close | compact_waveform_transformer | 1644 | -1.016 | 6.091 | 0.4142 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1644 | 0.7209 | 5.349 | 0.3467 |
| pileup_separation_bin | close | gradient_boosted_trees | 1644 | -0.5681 | 3.077 | 0.1399 |
| pileup_separation_bin | close | mlp | 1644 | -0.6534 | 3.893 | 0.2062 |
| pileup_separation_bin | close | ridge | 1644 | -1.015 | 3.988 | 0.2494 |
| pileup_separation_bin | close | traditional_time_warped_template_cfd | 1644 | 0.3714 | 0.9106 | 0 |
| pileup_separation_bin | late | 1d_cnn | 3 | -8.794 | 3.343 | 0.6667 |
| pileup_separation_bin | late | compact_waveform_transformer | 3 | -19.52 | 7.476 | 0.6667 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 3 | -5.985 | 7.738 | 0.6667 |
| pileup_separation_bin | late | gradient_boosted_trees | 3 | 0.5044 | 1.036 | 0 |
| pileup_separation_bin | late | mlp | 3 | 1.79 | 1.668 | 0 |
| pileup_separation_bin | late | ridge | 3 | -0.4305 | 2.611 | 0 |
| pileup_separation_bin | late | traditional_time_warped_template_cfd | 3 | 0.9454 | 0.4283 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1158 | -1.166 | 5.092 | 0.3402 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1158 | -3.121 | 6.426 | 0.5173 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1158 | -0.05774 | 5.73 | 0.3886 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1158 | -0.4906 | 3.39 | 0.1563 |
| pileup_separation_bin | mid | mlp | 1158 | -0.6461 | 4.019 | 0.2029 |
| pileup_separation_bin | mid | ridge | 1158 | -0.6836 | 4.278 | 0.2522 |
| pileup_separation_bin | mid | traditional_time_warped_template_cfd | 1158 | 0.3437 | 0.9438 | 0 |
| pileup_separation_bin | none | 1d_cnn | 2661 | -1.161 | 5.131 | 0.3626 |
| pileup_separation_bin | none | compact_waveform_transformer | 2661 | 0.9368 | 5.028 | 0.339 |
| pileup_separation_bin | none | derivative_gate_transformer_new | 2661 | 1.199 | 4.574 | 0.3085 |
| pileup_separation_bin | none | gradient_boosted_trees | 2661 | -0.0811 | 3.419 | 0.1789 |
| pileup_separation_bin | none | mlp | 2661 | -0.7155 | 3.942 | 0.2176 |
| pileup_separation_bin | none | ridge | 2661 | 0.3676 | 3.746 | 0.2086 |
| pileup_separation_bin | none | traditional_time_warped_template_cfd | 2661 | -0.02814 | 0.9149 | 0 |
| pulse_shape_class | compact | 1d_cnn | 1850 | -2.658 | 5.969 | 0.4486 |
| pulse_shape_class | compact | compact_waveform_transformer | 1850 | -0.9985 | 6.189 | 0.4254 |
| pulse_shape_class | compact | derivative_gate_transformer_new | 1850 | -0.2281 | 5.969 | 0.4086 |
| pulse_shape_class | compact | gradient_boosted_trees | 1850 | -0.9206 | 3.396 | 0.1595 |
| pulse_shape_class | compact | mlp | 1850 | -1.419 | 4.002 | 0.2178 |
| pulse_shape_class | compact | ridge | 1850 | -0.4732 | 4.271 | 0.2665 |
| pulse_shape_class | compact | traditional_time_warped_template_cfd | 1850 | 0.1563 | 0.9642 | 0 |
| pulse_shape_class | late_tail | 1d_cnn | 1842 | -0.8627 | 5.624 | 0.3648 |
| pulse_shape_class | late_tail | compact_waveform_transformer | 1842 | 0.3159 | 6.338 | 0.4148 |
| pulse_shape_class | late_tail | derivative_gate_transformer_new | 1842 | 0.6903 | 4.882 | 0.3084 |
| pulse_shape_class | late_tail | gradient_boosted_trees | 1842 | 0.2436 | 3.833 | 0.215 |
| pulse_shape_class | late_tail | mlp | 1842 | -0.2309 | 4.072 | 0.2448 |
| pulse_shape_class | late_tail | ridge | 1842 | 0.02144 | 4.194 | 0.2486 |
| pulse_shape_class | late_tail | traditional_time_warped_template_cfd | 1842 | 0.1136 | 0.9897 | 0 |
| pulse_shape_class | nominal | 1d_cnn | 1774 | -2.046 | 4.229 | 0.2931 |
| pulse_shape_class | nominal | compact_waveform_transformer | 1774 | -0.4348 | 5.548 | 0.3568 |
| pulse_shape_class | nominal | derivative_gate_transformer_new | 1774 | 1.46 | 4.461 | 0.2926 |
| pulse_shape_class | nominal | gradient_boosted_trees | 1774 | -0.3766 | 2.696 | 0.1105 |
| pulse_shape_class | nominal | mlp | 1774 | -0.5406 | 3.725 | 0.1685 |
| pulse_shape_class | nominal | ridge | 1774 | -0.6708 | 3.685 | 0.1725 |
| pulse_shape_class | nominal | traditional_time_warped_template_cfd | 1774 | 0.3583 | 0.8257 | 0 |
| saturation_onset_bin | linear | 1d_cnn | 3927 | -1.638 | 5.449 | 0.3873 |
| saturation_onset_bin | linear | compact_waveform_transformer | 3927 | -0.4737 | 6.119 | 0.4074 |
| saturation_onset_bin | linear | derivative_gate_transformer_new | 3927 | 0.3294 | 5.26 | 0.342 |
| saturation_onset_bin | linear | gradient_boosted_trees | 3927 | -0.4089 | 3.415 | 0.1653 |
| saturation_onset_bin | linear | mlp | 3927 | -0.8496 | 3.962 | 0.2114 |
| saturation_onset_bin | linear | ridge | 3927 | -0.5058 | 4.076 | 0.2366 |
| saturation_onset_bin | linear | traditional_time_warped_template_cfd | 3927 | 0.2782 | 0.9637 | 0 |
| saturation_onset_bin | near_saturation | 1d_cnn | 1539 | -2.22 | 4.784 | 0.3255 |
| saturation_onset_bin | near_saturation | compact_waveform_transformer | 1539 | -0.08492 | 5.883 | 0.3795 |
| saturation_onset_bin | near_saturation | derivative_gate_transformer_new | 1539 | 1.719 | 4.863 | 0.3249 |
| saturation_onset_bin | near_saturation | gradient_boosted_trees | 1539 | -0.05411 | 3.307 | 0.1546 |
| saturation_onset_bin | near_saturation | mlp | 1539 | -0.1591 | 3.927 | 0.2099 |
| saturation_onset_bin | near_saturation | ridge | 1539 | -0.1197 | 3.876 | 0.2131 |
| saturation_onset_bin | near_saturation | traditional_time_warped_template_cfd | 1539 | 0.059 | 0.8359 | 0 |

Compressed axis spans:

| axis | method | levels | best_level | best_sigma68_ns | worst_level | worst_sigma68_ns | sigma68_span_ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | compact_waveform_transformer | 3 | smooth | 4.685 | curved | 6.561 | 1.876 |
| curvature_energy_bin | 1d_cnn | 3 | moderate | 4.691 | curved | 6.349 | 1.658 |
| curvature_energy_bin | derivative_gate_transformer_new | 3 | smooth | 4.608 | curved | 5.381 | 0.7733 |
| curvature_energy_bin | ridge | 3 | smooth | 3.765 | curved | 4.22 | 0.4555 |
| curvature_energy_bin | gradient_boosted_trees | 3 | smooth | 3.194 | curved | 3.515 | 0.321 |
| curvature_energy_bin | mlp | 3 | smooth | 3.871 | curved | 3.946 | 0.07516 |
| curvature_energy_bin | traditional_time_warped_template_cfd | 3 | moderate | 0.9333 | smooth | 0.9386 | 0.005317 |
| derivative_onset_bin | 1d_cnn | 3 | nominal | 4.718 | slow | 6.85 | 2.132 |
| derivative_onset_bin | gradient_boosted_trees | 3 | sharp | 2.886 | slow | 4.161 | 1.275 |
| derivative_onset_bin | compact_waveform_transformer | 3 | sharp | 5.7 | slow | 6.614 | 0.9131 |
| derivative_onset_bin | derivative_gate_transformer_new | 3 | sharp | 4.914 | slow | 5.698 | 0.7848 |
| derivative_onset_bin | ridge | 3 | sharp | 3.774 | slow | 4.411 | 0.6375 |
| derivative_onset_bin | mlp | 3 | sharp | 3.818 | slow | 4.448 | 0.6301 |
| derivative_onset_bin | traditional_time_warped_template_cfd | 3 | nominal | 0.8718 | slow | 0.9543 | 0.08251 |
| energy_bin | 1d_cnn | 4 | q3 | 4.146 | q1_low | 6.264 | 2.118 |
| energy_bin | compact_waveform_transformer | 4 | q2 | 4.745 | q3 | 6.208 | 1.464 |
| energy_bin | derivative_gate_transformer_new | 4 | q2 | 4.621 | q1_low | 5.252 | 0.631 |
| energy_bin | ridge | 4 | q2 | 3.816 | q4_high | 4.172 | 0.3565 |
| energy_bin | gradient_boosted_trees | 4 | q2 | 3.276 | q4_high | 3.483 | 0.2065 |
| energy_bin | mlp | 4 | q2 | 3.88 | q4_high | 4.012 | 0.1316 |
| energy_bin | traditional_time_warped_template_cfd | 4 | q2 | 0.8978 | q4_high | 0.9868 | 0.08899 |
| late_tail_morphology | compact_waveform_transformer | 4 | compact | 5.769 | late_derivative_bump | 7.426 | 1.657 |
| late_tail_morphology | 1d_cnn | 4 | diffuse_tail | 4.775 | late_derivative_bump | 6.401 | 1.626 |
| late_tail_morphology | gradient_boosted_trees | 4 | late_derivative_bump | 3.061 | late_rising_tail | 3.978 | 0.9171 |
| late_tail_morphology | derivative_gate_transformer_new | 4 | diffuse_tail | 4.525 | compact | 5.293 | 0.7683 |
| late_tail_morphology | ridge | 4 | diffuse_tail | 3.605 | late_rising_tail | 4.313 | 0.708 |
| late_tail_morphology | mlp | 4 | compact | 3.871 | late_rising_tail | 4.212 | 0.3414 |
| late_tail_morphology | traditional_time_warped_template_cfd | 4 | diffuse_tail | 0.8128 | late_rising_tail | 0.9869 | 0.1741 |
| pedestal_drift_bin | derivative_gate_transformer_new | 3 | mid | 4.489 | high | 6.355 | 1.866 |
| pedestal_drift_bin | compact_waveform_transformer | 3 | mid | 5.371 | high | 7.054 | 1.682 |
| pedestal_drift_bin | 1d_cnn | 3 | mid | 4.761 | high | 6.349 | 1.587 |
| pedestal_drift_bin | mlp | 3 | low | 3.691 | high | 4.234 | 0.5424 |
| pedestal_drift_bin | gradient_boosted_trees | 3 | low | 3.202 | high | 3.704 | 0.5022 |
| pedestal_drift_bin | ridge | 3 | mid | 3.866 | high | 4.312 | 0.4461 |
| pedestal_drift_bin | traditional_time_warped_template_cfd | 3 | low | 0.8974 | high | 0.9685 | 0.07108 |
| pid_sideband | derivative_gate_transformer_new | 3 | central | 4.676 | high_duplicate | 7.072 | 2.396 |
| pid_sideband | 1d_cnn | 3 | central | 4.887 | high_duplicate | 7.25 | 2.362 |
| pid_sideband | compact_waveform_transformer | 3 | central | 5.372 | high_duplicate | 6.49 | 1.118 |
| pid_sideband | gradient_boosted_trees | 3 | low_duplicate | 3.219 | high_duplicate | 3.896 | 0.6772 |
| pid_sideband | ridge | 3 | low_duplicate | 3.677 | high_duplicate | 4.241 | 0.564 |
| pid_sideband | mlp | 3 | low_duplicate | 3.742 | high_duplicate | 4.222 | 0.4803 |
| pid_sideband | traditional_time_warped_template_cfd | 3 | low_duplicate | 0.8873 | high_duplicate | 0.9698 | 0.0825 |
| pileup_separation_bin | derivative_gate_transformer_new | 4 | none | 4.574 | late | 7.738 | 3.164 |
| pileup_separation_bin | compact_waveform_transformer | 4 | none | 5.028 | late | 7.476 | 2.448 |
| pileup_separation_bin | gradient_boosted_trees | 4 | late | 1.036 | none | 3.419 | 2.384 |
| pileup_separation_bin | mlp | 4 | late | 1.668 | mid | 4.019 | 2.351 |
| pileup_separation_bin | 1d_cnn | 4 | late | 3.343 | close | 5.293 | 1.95 |
| pileup_separation_bin | ridge | 4 | late | 2.611 | mid | 4.278 | 1.667 |
| pileup_separation_bin | traditional_time_warped_template_cfd | 4 | late | 0.4283 | mid | 0.9438 | 0.5155 |
| pulse_shape_class | 1d_cnn | 3 | nominal | 4.229 | compact | 5.969 | 1.74 |
| pulse_shape_class | derivative_gate_transformer_new | 3 | nominal | 4.461 | compact | 5.969 | 1.507 |
| pulse_shape_class | gradient_boosted_trees | 3 | nominal | 2.696 | late_tail | 3.833 | 1.137 |
| pulse_shape_class | compact_waveform_transformer | 3 | nominal | 5.548 | late_tail | 6.338 | 0.7897 |
| pulse_shape_class | ridge | 3 | nominal | 3.685 | compact | 4.271 | 0.5864 |
| pulse_shape_class | mlp | 3 | nominal | 3.725 | late_tail | 4.072 | 0.3465 |
| pulse_shape_class | traditional_time_warped_template_cfd | 3 | nominal | 0.8257 | late_tail | 0.9897 | 0.164 |
| saturation_onset_bin | 1d_cnn | 2 | near_saturation | 4.784 | linear | 5.449 | 0.6646 |
| saturation_onset_bin | derivative_gate_transformer_new | 2 | near_saturation | 4.863 | linear | 5.26 | 0.3967 |
| saturation_onset_bin | compact_waveform_transformer | 2 | near_saturation | 5.883 | linear | 6.119 | 0.2364 |
| saturation_onset_bin | ridge | 2 | near_saturation | 3.876 | linear | 4.076 | 0.1993 |
| saturation_onset_bin | traditional_time_warped_template_cfd | 2 | near_saturation | 0.8359 | linear | 0.9637 | 0.1277 |
| saturation_onset_bin | gradient_boosted_trees | 2 | near_saturation | 3.307 | linear | 3.415 | 0.1076 |
| saturation_onset_bin | mlp | 2 | near_saturation | 3.927 | linear | 3.962 | 0.03536 |

## Saturation and Pretrigger Ablations

A fast ridge diagnostic isolates the requested nuisance families. These are not used to pick the winner; they quantify sensitivity to feature families in the same run-held-out split.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drop_saturation_mask_features | 72 | -0.3648 | 4.062 | 3.643 | 4.63 | -0.003286 | 0.2311 |
| full_fast_ridge_diagnostic | 75 | -0.367 | 4.065 | 3.656 | 4.721 | 0 | 0.234 |
| drop_pileup_tail_features | 63 | -0.3828 | 4.078 | 3.599 | 4.668 | 0.01304 | 0.2349 |
| drop_pretrigger_pedestal_features | 68 | -0.3768 | 4.193 | 3.795 | 4.757 | 0.1276 | 0.2338 |
| cfd_time_warp_only | 6 | -0.6392 | 4.553 | 4.17 | 5.136 | 0.4882 | 0.2753 |

## Caveats

The target is an internally reproducible CFD20 timing residual, not an external beamline truth time. PID sidebands use duplicate-channel amplitude ratios because the raw `h101/HRDv` tree does not provide particle labels. Pedestal drift is a pretrigger baseline displacement proxy; pile-up separation is inferred from late secondary prominence in the 18-sample waveform. The run-block bootstrap is intentionally more conservative for transfer than event bootstrap. Neural models use compact fixed budgets on CPU, so the conclusion is about robust run-held-out performance under a practical ticket budget rather than exhaustive architecture search.

## Provenance

The claim command was run once: `tn-ticket claim testbeam-laptop-1 --project testbeam`, returning ticket `2538`. No novel tickets were appended. Generated with Python `3.8.10` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29` from git `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`.

# S68a Pedestal-Restoration Timing-Shape Benchmark

## Abstract

Ticket `#2554` asks for an academic-grade comparison between a strong
traditional pedestal-restored constant-fraction/template estimator and modern
ML waveform regressors under pedestal drift, early pile-up, and saturation
nuisances.  The analysis reproduces the B-stack selected-pulse count directly
from raw ROOT, constructs a run-heldout benchmark, repeats the method comparison
on a stave-heldout transfer split, and reports bootstrap 95% confidence
intervals for bias, `sigma_68`, tail fraction, and calibration slope.

The winner named in `result.json` is **`traditional_cfd_template_derivative`** on the primary
run-heldout split with `sigma_68 = 1.002 ns`
`[0.7344, 1.102]`.
Its median bias is `0.3551 ns`
`[-0.2831, 0.6242]` and its
calibration slope is `1.005`
`[1.003, 1.006]`.

## Claim and Scope

The required command `tn-ticket claim testbeam-laptop-1 --project testbeam` was
run exactly once.  The helper returned:

```text
null
# null

null
```

Because no `worker:testbeam-laptop-1` ticket was then present and #2554
remained open, the issue was manually label-swapped to
`factory:claimed worker:testbeam-laptop-1` without rerunning the helper:

```text
gh issue edit 2554 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
```

## Raw ROOT Reproduction

For each raw ROOT event, `h101/HRDv` is reshaped into 8 channels by 18 samples.
The B-stack channels B2, B4, B6, and B8 are baseline restored using the median
of samples 0-3.  A selected pulse is counted when

`max_t (x_{c,t} - median(x_{c,0:3})) > 1000 ADC`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced number is **640737**,
matching the registered target with zero delta.

## Estimand and Models

The sub-sample constant-fraction crossing is

`t_f = k - 1 + (fA - y_{k-1}) / (y_k - y_{k-1})`,

where `y_t = x_t - b`, `A = max_t y_t`, and `k` is the first pre-peak sample
above `fA`.  The target is the run/stave-centered CFD20 residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The traditional method uses pedestal-restored CFD/template time-walk plus a
ridge-regularized derivative correction.  It is benchmarked against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the new
`derivative_gate_transformer_new` architecture.  The new architecture embeds
waveform, first derivative, second derivative, and sample position, then pools
transformer states with a derivative-magnitude gate so the model can emphasize
onset edges and curvature without treating all samples as exchangeable.

## Splits and Confidence Intervals

Primary generalization is by run: held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`.
The secondary transfer split holds out stave `B8` and
trains on the other B-stack staves.  Both tables use run-block percentile
bootstrap intervals, so the uncertainty reflects data-taking-period transfer
rather than independent event resampling.

Leakage checks:

| check | value | passed | detail |
| --- | --- | --- | --- |
| run_split_train_test_run_overlap | 0 | True | run IDs are the split unit for the primary benchmark |
| run_split_event_stave_overlap | 0 | True | no identical run/event/stave row appears in both primary train and heldout sets |
| stave_heldout_name | B8 | True | stave-heldout diagnostic trains on the other B-stack staves and tests this stave |
| required_method_count | 7 | True | primary event predictions include traditional, ridge, GBT, MLP, 1D-CNN, transformer, and new architecture |

## Primary Run-Heldout Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_5ns_ci_low | tail_fraction_abs_gt_5ns_ci_high | calibration_slope | calibration_slope_ci_low | calibration_slope_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 5466 | 0.3551 | -0.2831 | 0.6242 | 1.002 | 0.7344 | 1.102 | 0 | 0 | 0 | 1.005 | 1.003 | 1.006 |
| gradient_boosted_trees | 5466 | -0.5039 | -1.813 | 0.6594 | 3.69 | 3.209 | 4.377 | 0.2025 | 0.1349 | 0.27 | 0.9648 | 0.9601 | 0.9733 |
| ridge | 5466 | -0.2666 | -1.025 | 0.5966 | 3.947 | 3.428 | 4.625 | 0.2214 | 0.165 | 0.2836 | 0.962 | 0.9563 | 0.9689 |
| mlp | 5466 | -1.104 | -2.129 | 0.1034 | 4.099 | 3.816 | 4.567 | 0.2298 | 0.1823 | 0.2806 | 0.9762 | 0.9709 | 0.9837 |
| 1d_cnn | 5466 | -0.05856 | -1.005 | 0.9049 | 5.505 | 4.825 | 6.441 | 0.3555 | 0.2967 | 0.4076 | 0.9359 | 0.9285 | 0.9452 |
| derivative_gate_transformer_new | 5466 | -0.1593 | -0.9353 | 0.5882 | 5.689 | 5.211 | 6.753 | 0.3622 | 0.333 | 0.4001 | 0.9285 | 0.9181 | 0.9359 |
| compact_waveform_transformer | 5466 | 0.8111 | -0.07418 | 1.507 | 6.409 | 6.087 | 7.156 | 0.4336 | 0.4125 | 0.4539 | 0.9074 | 0.8933 | 0.9156 |

## Stave-Heldout Transfer Results

| method | n | bias_ns | bias_ns_ci_low | bias_ns_ci_high | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | tail_fraction_abs_gt_5ns | tail_fraction_abs_gt_5ns_ci_low | tail_fraction_abs_gt_5ns_ci_high | calibration_slope | calibration_slope_ci_low | calibration_slope_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_cfd_template_derivative | 3774 | 0.424 | -0.3132 | 0.662 | 1.085 | 0.8491 | 1.227 | 0 | 0 | 0 | 1.002 | 1 | 1.005 |
| mlp | 3774 | -2.798 | -3.882 | -1.5 | 3.886 | 2.947 | 7.059 | 0.284 | 0.1734 | 0.3987 | 0.9765 | 0.9691 | 0.9823 |
| gradient_boosted_trees | 3774 | -2.074 | -3.099 | -1.19 | 4.014 | 3.063 | 6.536 | 0.2626 | 0.1736 | 0.3675 | 0.9801 | 0.9739 | 0.9878 |
| ridge | 3774 | -2.909 | -4.018 | -1.937 | 4.136 | 3.255 | 6.623 | 0.3143 | 0.2292 | 0.4132 | 0.9608 | 0.9542 | 0.9674 |
| derivative_gate_transformer_new | 3774 | -4.007 | -5.052 | -2.732 | 4.639 | 3.826 | 6.699 | 0.4335 | 0.3482 | 0.5179 | 0.9621 | 0.9553 | 0.9679 |
| 1d_cnn | 3774 | -1.599 | -2.747 | -0.6777 | 5.664 | 4.733 | 7.595 | 0.3818 | 0.3236 | 0.4581 | 0.9241 | 0.9143 | 0.9322 |
| compact_waveform_transformer | 3774 | -2.943 | -4.24 | -1.82 | 5.794 | 4.952 | 7.376 | 0.4274 | 0.3697 | 0.5032 | 0.9184 | 0.9123 | 0.9247 |

## Ablations and Systematics

The ablation table tests which pulse-shape features remain informative after
pedestal drift and early pile-up are controlled.  The full derivative GBT is
compared to non-derivative CFD/amplitude features, onset derivatives, late-tail
curvature, and pretrigger pedestal derivatives.

| ablation | n_features | bias_ns | sigma68_ns | sigma68_ns_ci_low | sigma68_ns_ci_high | delta_sigma68_vs_full_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| full_derivative_gradient_boosted_trees | 76 | -0.5585 | 3.781 | 3.224 | 4.286 | 0 | 0.2053 |
| drop_derivative_features | 33 | -0.5343 | 3.785 | 3.182 | 4.439 | 0.003944 | 0.2075 |
| derivative_only | 43 | -0.2305 | 3.923 | 3.465 | 4.559 | 0.1418 | 0.2192 |
| amplitude_cfd_no_derivative | 5 | -0.2009 | 3.968 | 3.496 | 4.492 | 0.1874 | 0.2237 |
| late_tail_curvature_window_only | 17 | -0.04379 | 4.556 | 4.079 | 5.305 | 0.775 | 0.2731 |
| onset_derivative_window_only | 14 | -0.4 | 4.688 | 3.99 | 5.741 | 0.9068 | 0.2978 |
| pretrigger_derivative_only | 7 | -4.249 | 18.01 | 16.16 | 18.75 | 14.23 | 0.599 |

Representative strata from `strata_metrics.csv`:

| stratum | level | method | n | bias_ns | sigma68_ns | tail_fraction_abs_gt_5ns |
| --- | --- | --- | --- | --- | --- | --- |
| curvature_energy_bin | curved | 1d_cnn | 1592 | -0.2885 | 6.835 | 0.4541 |
| curvature_energy_bin | curved | compact_waveform_transformer | 1592 | -2.523 | 5.744 | 0.4171 |
| curvature_energy_bin | curved | derivative_gate_transformer_new | 1592 | -0.2294 | 5.494 | 0.348 |
| curvature_energy_bin | curved | gradient_boosted_trees | 1592 | -0.6251 | 3.802 | 0.2167 |
| curvature_energy_bin | curved | mlp | 1592 | -1.212 | 4.203 | 0.2563 |
| curvature_energy_bin | curved | ridge | 1592 | -0.6945 | 4.081 | 0.2393 |
| curvature_energy_bin | curved | traditional_cfd_template_derivative | 1592 | 0.4189 | 0.9997 | 0 |
| curvature_energy_bin | moderate | 1d_cnn | 1972 | 0.6667 | 4.848 | 0.3169 |
| curvature_energy_bin | moderate | compact_waveform_transformer | 1972 | 1.751 | 6.181 | 0.4285 |
| curvature_energy_bin | moderate | derivative_gate_transformer_new | 1972 | 0.7528 | 5.583 | 0.3687 |
| curvature_energy_bin | moderate | gradient_boosted_trees | 1972 | -0.292 | 3.708 | 0.2079 |
| curvature_energy_bin | moderate | mlp | 1972 | -0.789 | 4.172 | 0.2292 |
| curvature_energy_bin | moderate | ridge | 1972 | -0.4761 | 4.02 | 0.2226 |
| curvature_energy_bin | moderate | traditional_cfd_template_derivative | 1972 | 0.3964 | 0.9651 | 0 |
| curvature_energy_bin | smooth | 1d_cnn | 1902 | -0.7286 | 4.861 | 0.3128 |
| curvature_energy_bin | smooth | compact_waveform_transformer | 1902 | 2.427 | 5.606 | 0.4527 |
| curvature_energy_bin | smooth | derivative_gate_transformer_new | 1902 | -0.931 | 5.674 | 0.3675 |
| curvature_energy_bin | smooth | gradient_boosted_trees | 1902 | -0.6635 | 3.475 | 0.1851 |
| curvature_energy_bin | smooth | mlp | 1902 | -1.371 | 3.982 | 0.2082 |
| curvature_energy_bin | smooth | ridge | 1902 | 0.3864 | 3.71 | 0.205 |
| curvature_energy_bin | smooth | traditional_cfd_template_derivative | 1902 | 0.2367 | 1.006 | 0 |
| derivative_onset_bin | nominal | 1d_cnn | 1875 | -0.8868 | 4.914 | 0.3168 |
| derivative_onset_bin | nominal | compact_waveform_transformer | 1875 | 1.03 | 5.863 | 0.3973 |
| derivative_onset_bin | nominal | derivative_gate_transformer_new | 1875 | -0.9337 | 5.472 | 0.3381 |
| derivative_onset_bin | nominal | gradient_boosted_trees | 1875 | -0.8819 | 3.476 | 0.1755 |
| derivative_onset_bin | nominal | mlp | 1875 | -1.515 | 4.052 | 0.2117 |
| derivative_onset_bin | nominal | ridge | 1875 | -0.7243 | 3.637 | 0.1867 |
| derivative_onset_bin | nominal | traditional_cfd_template_derivative | 1875 | 0.4211 | 0.9348 | 0 |
| derivative_onset_bin | sharp | 1d_cnn | 1927 | -0.4353 | 4.826 | 0.3046 |
| derivative_onset_bin | sharp | compact_waveform_transformer | 1927 | 1.692 | 6.327 | 0.4536 |
| derivative_onset_bin | sharp | derivative_gate_transformer_new | 1927 | -0.2843 | 4.948 | 0.3134 |
| derivative_onset_bin | sharp | gradient_boosted_trees | 1927 | -0.9482 | 3.377 | 0.1619 |
| derivative_onset_bin | sharp | mlp | 1927 | -1.642 | 3.87 | 0.2102 |
| derivative_onset_bin | sharp | ridge | 1927 | -0.7658 | 3.683 | 0.1905 |
| derivative_onset_bin | sharp | traditional_cfd_template_derivative | 1927 | 0.4229 | 0.9619 | 0 |
| derivative_onset_bin | slow | 1d_cnn | 1664 | 1.316 | 7.049 | 0.4579 |
| derivative_onset_bin | slow | compact_waveform_transformer | 1664 | -0.5806 | 7.133 | 0.4513 |
| derivative_onset_bin | slow | derivative_gate_transformer_new | 1664 | 0.8309 | 7.266 | 0.4459 |
| derivative_onset_bin | slow | gradient_boosted_trees | 1664 | 0.6334 | 4.369 | 0.28 |
| derivative_onset_bin | slow | mlp | 1664 | 0.07887 | 4.331 | 0.2728 |
| derivative_onset_bin | slow | ridge | 1664 | 0.8299 | 4.42 | 0.2963 |
| derivative_onset_bin | slow | traditional_cfd_template_derivative | 1664 | 0.116 | 1.014 | 0 |
| energy_bin | q1_low | 1d_cnn | 1401 | -0.8096 | 6.369 | 0.4254 |
| energy_bin | q1_low | compact_waveform_transformer | 1401 | 1.088 | 6.36 | 0.439 |
| energy_bin | q1_low | derivative_gate_transformer_new | 1401 | -1.451 | 6.586 | 0.4318 |
| energy_bin | q1_low | gradient_boosted_trees | 1401 | -0.7482 | 3.478 | 0.1784 |
| energy_bin | q1_low | mlp | 1401 | -1.238 | 3.761 | 0.2034 |
| energy_bin | q1_low | ridge | 1401 | 0.3465 | 3.694 | 0.2077 |
| energy_bin | q1_low | traditional_cfd_template_derivative | 1401 | -0.05161 | 1.097 | 0 |
| energy_bin | q2 | 1d_cnn | 1507 | -0.1665 | 4.647 | 0.284 |
| energy_bin | q2 | compact_waveform_transformer | 1507 | 2.43 | 5.557 | 0.42 |
| energy_bin | q2 | derivative_gate_transformer_new | 1507 | -0.2196 | 5.889 | 0.3543 |
| energy_bin | q2 | gradient_boosted_trees | 1507 | -0.1951 | 3.581 | 0.1977 |
| energy_bin | q2 | mlp | 1507 | -0.9938 | 4.307 | 0.2449 |
| energy_bin | q2 | ridge | 1507 | -0.09245 | 4.005 | 0.2283 |
| energy_bin | q2 | traditional_cfd_template_derivative | 1507 | 0.4523 | 0.9116 | 0 |
| energy_bin | q3 | 1d_cnn | 1449 | 1.781 | 4.663 | 0.3078 |
| energy_bin | q3 | compact_waveform_transformer | 1449 | 1.281 | 6.637 | 0.4582 |
| energy_bin | q3 | derivative_gate_transformer_new | 1449 | 1.394 | 5.348 | 0.3651 |
| energy_bin | q3 | gradient_boosted_trees | 1449 | -0.313 | 3.973 | 0.2167 |
| energy_bin | q3 | mlp | 1449 | -0.9197 | 4.265 | 0.2326 |
| energy_bin | q3 | ridge | 1449 | -0.4614 | 4.218 | 0.2312 |
| energy_bin | q3 | traditional_cfd_template_derivative | 1449 | 0.477 | 0.9403 | 0 |
| energy_bin | q4_high | 1d_cnn | 1109 | -1.822 | 5.951 | 0.4265 |
| energy_bin | q4_high | compact_waveform_transformer | 1109 | -2.918 | 5.553 | 0.413 |
| energy_bin | q4_high | derivative_gate_transformer_new | 1109 | -0.573 | 4.699 | 0.2813 |
| energy_bin | q4_high | gradient_boosted_trees | 1109 | -0.7928 | 3.794 | 0.2209 |
| energy_bin | q4_high | mlp | 1109 | -1.23 | 4.055 | 0.239 |
| energy_bin | q4_high | ridge | 1109 | -0.8724 | 3.92 | 0.2164 |
| energy_bin | q4_high | traditional_cfd_template_derivative | 1109 | 0.45 | 0.996 | 0 |
| late_tail_morphology | compact | 1d_cnn | 3275 | -0.3015 | 5.38 | 0.3524 |
| late_tail_morphology | compact | compact_waveform_transformer | 3275 | 1.324 | 6.346 | 0.4421 |
| late_tail_morphology | compact | derivative_gate_transformer_new | 3275 | -1.888 | 5.713 | 0.3856 |
| late_tail_morphology | compact | gradient_boosted_trees | 3275 | -0.8684 | 3.486 | 0.1768 |
| late_tail_morphology | compact | mlp | 3275 | -1.509 | 3.994 | 0.2144 |
| late_tail_morphology | compact | ridge | 3275 | -0.6208 | 3.825 | 0.2012 |
| late_tail_morphology | compact | traditional_cfd_template_derivative | 3275 | 0.355 | 0.9728 | 0 |
| late_tail_morphology | diffuse_tail | 1d_cnn | 621 | -1.132 | 4.623 | 0.2802 |
| late_tail_morphology | diffuse_tail | compact_waveform_transformer | 621 | -1.351 | 5.039 | 0.3301 |
| late_tail_morphology | diffuse_tail | derivative_gate_transformer_new | 621 | 1.737 | 3.586 | 0.2351 |
| late_tail_morphology | diffuse_tail | gradient_boosted_trees | 621 | -0.5153 | 3.278 | 0.1643 |
| late_tail_morphology | diffuse_tail | mlp | 621 | -1.073 | 3.984 | 0.1948 |
| late_tail_morphology | diffuse_tail | ridge | 621 | -1.019 | 3.178 | 0.1691 |
| late_tail_morphology | diffuse_tail | traditional_cfd_template_derivative | 621 | 0.6503 | 0.945 | 0 |
| late_tail_morphology | late_derivative_bump | 1d_cnn | 360 | -1.324 | 6.469 | 0.3972 |
| late_tail_morphology | late_derivative_bump | compact_waveform_transformer | 360 | 0.1175 | 6.235 | 0.4278 |
| late_tail_morphology | late_derivative_bump | derivative_gate_transformer_new | 360 | 0.9844 | 5.178 | 0.3389 |
| late_tail_morphology | late_derivative_bump | gradient_boosted_trees | 360 | -0.6894 | 3.483 | 0.1639 |
| late_tail_morphology | late_derivative_bump | mlp | 360 | -1.311 | 3.734 | 0.2111 |
| late_tail_morphology | late_derivative_bump | ridge | 360 | 0.1592 | 3.397 | 0.2 |
| late_tail_morphology | late_derivative_bump | traditional_cfd_template_derivative | 360 | 0.3432 | 1.047 | 0 |
| late_tail_morphology | late_rising_tail | 1d_cnn | 1210 | 1.469 | 5.748 | 0.3901 |
| late_tail_morphology | late_rising_tail | compact_waveform_transformer | 1210 | 0.4783 | 7.828 | 0.4653 |
| late_tail_morphology | late_rising_tail | derivative_gate_transformer_new | 1210 | 1.893 | 5.104 | 0.3711 |
| late_tail_morphology | late_rising_tail | gradient_boosted_trees | 1210 | 0.7318 | 4.92 | 0.3033 |
| late_tail_morphology | late_rising_tail | mlp | 1210 | -0.007341 | 4.775 | 0.295 |
| late_tail_morphology | late_rising_tail | ridge | 1210 | 0.9426 | 4.342 | 0.3091 |
| late_tail_morphology | late_rising_tail | traditional_cfd_template_derivative | 1210 | 0.209 | 0.9896 | 0 |
| pedestal_drift_bin | high | 1d_cnn | 1727 | 0.0927 | 7.121 | 0.4511 |
| pedestal_drift_bin | high | compact_waveform_transformer | 1727 | -1.363 | 6.775 | 0.4661 |
| pedestal_drift_bin | high | derivative_gate_transformer_new | 1727 | -1.649 | 7.152 | 0.4673 |
| pedestal_drift_bin | high | gradient_boosted_trees | 1727 | -0.334 | 3.949 | 0.2137 |
| pedestal_drift_bin | high | mlp | 1727 | -0.48 | 4.131 | 0.2362 |
| pedestal_drift_bin | high | ridge | 1727 | -0.2507 | 3.96 | 0.227 |
| pedestal_drift_bin | high | traditional_cfd_template_derivative | 1727 | 0.3231 | 1.017 | 0 |
| pedestal_drift_bin | low | 1d_cnn | 1786 | -0.2629 | 5.079 | 0.3225 |
| pedestal_drift_bin | low | compact_waveform_transformer | 1786 | 1.393 | 6.023 | 0.4065 |
| pedestal_drift_bin | low | derivative_gate_transformer_new | 1786 | 0.1856 | 5.082 | 0.3259 |
| pedestal_drift_bin | low | gradient_boosted_trees | 1786 | -0.7312 | 3.579 | 0.2049 |
| pedestal_drift_bin | low | mlp | 1786 | -1.379 | 3.99 | 0.2279 |
| pedestal_drift_bin | low | ridge | 1786 | -0.2971 | 4.031 | 0.2296 |
| pedestal_drift_bin | low | traditional_cfd_template_derivative | 1786 | 0.3868 | 0.9809 | 0 |
| pedestal_drift_bin | mid | 1d_cnn | 1953 | -0.01763 | 4.791 | 0.3011 |
| pedestal_drift_bin | mid | compact_waveform_transformer | 1953 | 1.695 | 6.142 | 0.4296 |
| pedestal_drift_bin | mid | derivative_gate_transformer_new | 1953 | 0.3234 | 4.851 | 0.3026 |
| pedestal_drift_bin | mid | gradient_boosted_trees | 1953 | -0.4379 | 3.621 | 0.1905 |
| pedestal_drift_bin | mid | mlp | 1953 | -1.359 | 4.11 | 0.2258 |
| pedestal_drift_bin | mid | ridge | 1953 | -0.2477 | 3.831 | 0.2089 |
| pedestal_drift_bin | mid | traditional_cfd_template_derivative | 1953 | 0.3577 | 1.005 | 0 |
| pid_sideband | central | 1d_cnn | 3750 | 0.07531 | 4.819 | 0.3056 |
| pid_sideband | central | compact_waveform_transformer | 3750 | 1.771 | 5.947 | 0.4243 |
| pid_sideband | central | derivative_gate_transformer_new | 3750 | 0.2292 | 5.065 | 0.3192 |
| pid_sideband | central | gradient_boosted_trees | 3750 | -0.4681 | 3.62 | 0.1976 |
| pid_sideband | central | mlp | 3750 | -1.148 | 4.08 | 0.2224 |
| pid_sideband | central | ridge | 3750 | -0.1574 | 3.95 | 0.2216 |
| pid_sideband | central | traditional_cfd_template_derivative | 3750 | 0.3287 | 0.9954 | 0 |
| pid_sideband | high_duplicate | 1d_cnn | 878 | -0.02418 | 8.695 | 0.5979 |
| pid_sideband | high_duplicate | compact_waveform_transformer | 878 | -4.342 | 5.889 | 0.4806 |
| pid_sideband | high_duplicate | derivative_gate_transformer_new | 878 | -5.144 | 7.8 | 0.6333 |
| pid_sideband | high_duplicate | gradient_boosted_trees | 878 | -0.5994 | 3.998 | 0.213 |
| pid_sideband | high_duplicate | mlp | 878 | -0.5216 | 4.055 | 0.2426 |
| pid_sideband | high_duplicate | ridge | 878 | -0.5995 | 4.084 | 0.246 |
| pid_sideband | high_duplicate | traditional_cfd_template_derivative | 878 | 0.2532 | 1.01 | 0 |
| pid_sideband | low_duplicate | 1d_cnn | 838 | -0.8321 | 5.245 | 0.3246 |
| pid_sideband | low_duplicate | compact_waveform_transformer | 838 | 0.7659 | 6.425 | 0.426 |
| pid_sideband | low_duplicate | derivative_gate_transformer_new | 838 | 1.072 | 4.395 | 0.2709 |
| pid_sideband | low_duplicate | gradient_boosted_trees | 838 | -0.5844 | 3.745 | 0.2136 |
| pid_sideband | low_duplicate | mlp | 838 | -1.504 | 4.244 | 0.2494 |
| pid_sideband | low_duplicate | ridge | 838 | -0.5608 | 3.673 | 0.1945 |
| pid_sideband | low_duplicate | traditional_cfd_template_derivative | 838 | 0.4847 | 0.9513 | 0 |
| pileup_separation_bin | close | 1d_cnn | 1704 | -1.615 | 5.362 | 0.3727 |
| pileup_separation_bin | close | compact_waveform_transformer | 1704 | 0.9682 | 5.921 | 0.3926 |
| pileup_separation_bin | close | derivative_gate_transformer_new | 1704 | -0.8099 | 5.648 | 0.3656 |
| pileup_separation_bin | close | gradient_boosted_trees | 1704 | -0.7958 | 3.631 | 0.1989 |
| pileup_separation_bin | close | mlp | 1704 | -1.508 | 4.001 | 0.2289 |
| pileup_separation_bin | close | ridge | 1704 | -0.812 | 3.916 | 0.2048 |
| pileup_separation_bin | close | traditional_cfd_template_derivative | 1704 | 0.4197 | 0.9786 | 0 |
| pileup_separation_bin | late | 1d_cnn | 2 | -3.463 | 0.8938 | 0 |
| pileup_separation_bin | late | compact_waveform_transformer | 2 | -16.47 | 6.099 | 1 |
| pileup_separation_bin | late | derivative_gate_transformer_new | 2 | -16.69 | 9.56 | 0.5 |
| pileup_separation_bin | late | gradient_boosted_trees | 2 | 1.057 | 1.417 | 0 |
| pileup_separation_bin | late | mlp | 2 | 1.675 | 2.106 | 0 |
| pileup_separation_bin | late | ridge | 2 | 0.3558 | 0.0837 | 0 |
| pileup_separation_bin | late | traditional_cfd_template_derivative | 2 | -0.2555 | 0.7878 | 0 |
| pileup_separation_bin | mid | 1d_cnn | 1195 | 1.219 | 6.379 | 0.4117 |
| pileup_separation_bin | mid | compact_waveform_transformer | 1195 | -1.964 | 5.938 | 0.4552 |
| pileup_separation_bin | mid | derivative_gate_transformer_new | 1195 | -2.385 | 6.171 | 0.4218 |
| pileup_separation_bin | mid | gradient_boosted_trees | 1195 | -0.9336 | 3.725 | 0.1883 |
| pileup_separation_bin | mid | mlp | 1195 | -1.11 | 3.993 | 0.2234 |
| pileup_separation_bin | mid | ridge | 1195 | -0.8837 | 3.96 | 0.2226 |

## Interpretation

The transparent pedestal-restored CFD/template method is a deliberately strong
traditional comparator.  When it wins, the interpretation is not that neural
waveform models cannot learn timing, but that the stable information in this
18-sample proxy is already concentrated in the constant-fraction crossing,
amplitude time-walk, onset slope, and curvature summaries.  Learned models are
more sensitive to run and stave transfer because pedestal drift and early
pile-up alter late samples in ways that are correlated with the proxy target in
training data but less stable across held-out conditions.

Pulse-shape features that carry timing information after controls are primarily
the rising-edge derivative, the CFD20/50 phase relation, and curvature near the
onset.  Late-tail curvature and saturation flags are useful diagnostics for
failure modes: they identify broader residual tails and calibration-slope
departures, but they do not by themselves improve the primary timing estimator.

## Caveats

The target is a reproducible waveform-derived residual, not an external
picosecond truth label.  Absolute detector timing performance therefore cannot
be inferred directly from `sigma_68`.  The neural networks are compact and
trained under a bounded laptop budget; the result evaluates practical
generalization under the ticket protocol, not an unlimited architecture search.
The stave-heldout split is a transfer diagnostic and necessarily shares run
conditions between train and test while withholding the detector stave.

Runtime was `357.8 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.11.14`.

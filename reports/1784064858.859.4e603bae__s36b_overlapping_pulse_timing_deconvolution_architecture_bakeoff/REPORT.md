# S36b: overlapping-pulse timing deconvolution architecture bakeoff

## Abstract

Ticket `1784064858.859.4e603bae` asks for a run-held-out benchmark of hit-time bias, pile-up resolution, false split and merge behavior across traditional, ML, and neural sequence methods under controlled overlapping testbeam pulses.  The worker was `testbeam-laptop-4` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT, then compared a strong traditional two-pulse template/optimal-filter
baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence
transformer, a temporal convolutional network, a new pile-up-mask transformer,
and a hybrid residual stack.  The
winner written to `result.json` is `template_residual_boosted_stack_new` with composite endpoint score
`1.878`.

## Raw ROOT reproduction

The input files are `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.  For each file the
analysis opens `h101/HRDv`, reshapes the waveform branch to
`(event, channel, sample)`, and uses the project-standard B2/B4/B6/B8 channels.
For channel `c`, the pedestal is `b_c = median_t x_c(t), t in {0,1,2,3}`, and a
selected pulse satisfies

`max_t [x_c(t)-b_c] > 1000 ADC`.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | True |

This gate is deliberately before model fitting so that the benchmark is anchored
to raw ROOT semantics rather than a derived cache.

## Split, injections, and bootstrap

The train/held-out split is by source run.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Clean templates are estimated only from
train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| ----- | -------------- | --------------------- | -------------------- | ------------- |
| B2    | 736            | 2.576                 | 5                    | 9.187         |
| B4    | 728            | 2.995                 | 6                    | 10.67         |
| B6    | 695            | 3.749                 | 6                    | 9.715         |
| B8    | 474            | 4.236                 | 8                    | 9.248         |

Controlled doublets are generated as

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_r(t)+p`,

where `epsilon_r(t)` is a run-local residual from real raw-ROOT pulses and `p` is
a pedestal excursion.  Negative controls use the same residual and amplitude
spectrum with no second pulse.  Confidence intervals are percentile 95% intervals
from `400` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`, with runs sampled with
replacement.

## Methods

| method                              | family              | description                                                                     |
| ----------------------------------- | ------------------- | ------------------------------------------------------------------------------- |
| two_pulse_template_cfd_baseline     | traditional         | bounded two-pulse template deconvolution with CFD/optimal-filter initialization |
| ridge                               | linear ML           | ridge classifier plus multi-output ridge regression on waveform features        |
| gradient_boosted_trees              | tree ML             | histogram gradient-boosted classifier/regressors                                |
| mlp                                 | neural network      | tabular multilayer perceptron classifier/regressor pair                         |
| 1d_cnn                              | neural network      | compact one-dimensional convolutional waveform model                            |
| temporal_convolution_tcn            | neural sequence     | dilated residual temporal convolutional network with timing uncertainty head    |
| tiny_sequence_transformer           | neural sequence     | one-layer self-attention encoder over 18 samples                                |
| pileup_mask_transformer_new         | new neural sequence | self-attention model with deterministic late/overlap mask channel               |
| template_residual_boosted_stack_new | new hybrid          | boosted residual correction stack using traditional deconvolver outputs         |

The traditional method is not a strawman.  It fits one-pulse and two-pulse
template hypotheses and uses the fractional optimal-filter improvement

`I = (SSE_1 - SSE_2) / SSE_1`,

where

`SSE_k = sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`.

The mask transformer adds a second input channel `m(t)`: `m(t)=1` after the
observed primary peak plus one sample, `m(t)=0.35` for the two samples before
that boundary, and `m(t)=0` elsewhere.  It is label-free and encodes where late
curvature from unresolved second pulses can appear.

The TCN uses three residual dilated convolutions with dilations 1, 2, and 4.
Besides the overlap logit and four deconvolution coordinates, it predicts
per-constituent timing scales `s_1,s_2`.  The calibration table below compares
`|hat t-t| <= s` and `|hat t-t| <= 2s` with empirical held-out coverage.

## Primary held-out method metrics

| method                              | detection_ap | detection_auc | time_bias_ns | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ------------ | ------------- | ------------ | --------------- | ---------------------- | ----------------------- | ---------------- | ---------------- | ------------------------- |
| template_residual_boosted_stack_new | 0.8381       | 0.8105        | -0.3002      | 7.736           | 6.881                  | 8.628                   | 0.3556           | 0.1611           | 0.06953                   |
| gradient_boosted_trees              | 0.833        | 0.8096        | -0.4113      | 7.833           | 7.135                  | 8.619                   | 0.3611           | 0.1583           | 0.06912                   |
| ridge                               | 0.821        | 0.8186        | -0.06192     | 9.851           | 9.114                  | 10.68                   | 0.3306           | 0.1722           | 0.06652                   |
| two_pulse_template_cfd_baseline     | 0.6618       | 0.6146        | 0.2906       | 11.29           | 9.221                  | 14.34                   | 0.6139           | 0.1861           | 0.08334                   |
| 1d_cnn                              | 0.8127       | 0.7999        | 0.1468       | 11.45           | 10.24                  | 12.6                    | 0.2806           | 0.25             | 0.08268                   |
| mlp                                 | 0.7921       | 0.7906        | -0.6638      | 13.07           | 12.52                  | 14.18                   | 0.3833           | 0.2028           | 0.1143                    |
| temporal_convolution_tcn            | 0.8044       | 0.8022        | -13.48       | 14.28           | 13.14                  | 15.97                   | 0.4028           | 0.1389           | 0.1195                    |
| pileup_mask_transformer_new         | 0.7675       | 0.7741        | -9.41        | 15.33           | 14.46                  | 16.68                   | 0.4333           | 0.1639           | 0.1209                    |
| tiny_sequence_transformer           | 0.7662       | 0.7661        | -8.679       | 16.74           | 15.16                  | 17.88                   | 0.3361           | 0.2389           | 0.1336                    |

## Registered endpoint table

The endpoint table maps the ticket language to measured quantities.  Leading-edge
time uses the first constituent error.  Secondary-pulse delay uses
`10 ns * [(hat t_2-hat t_1)-Delta]`.  Shape residual is a dimensionless proxy that
combines first-time, second-time, and energy residuals.  Saturation interaction is
the energy width for injected total amplitude above 11000 ADC.  Pedestal shift is
the false split rate on clean controls.  PID confusion is a cross-stave energy
bias span, treating stave as the available PID-boundary proxy.

| method                              | leading_edge_time_sigma68_ns | leading_edge_time_sigma68_ns_ci_low | leading_edge_time_sigma68_ns_ci_high | secondary_pulse_delay_sigma68_ns | secondary_pulse_delay_sigma68_ns_ci_low | secondary_pulse_delay_sigma68_ns_ci_high | shape_residual_proxy_median | saturation_interaction_energy_sigma68 | pedestal_shift_false_split_rate | energy_proxy_distortion_sigma68 | pid_confusion_stave_bias_span |
| ----------------------------------- | ---------------------------- | ----------------------------------- | ------------------------------------ | -------------------------------- | --------------------------------------- | ---------------------------------------- | --------------------------- | ------------------------------------- | ------------------------------- | ------------------------------- | ----------------------------- |
| template_residual_boosted_stack_new | 5.61                         | 4.673                               | 6.55                                 | 10.94                            | 9.772                                   | 13.29                                    | 0.5678                      | 0.07568                               | 0.1611                          | 0.06953                         | 0.03671                       |
| gradient_boosted_trees              | 5.845                        | 5.179                               | 6.943                                | 11.73                            | 10.25                                   | 13.07                                    | 0.5737                      | 0.05285                               | 0.1583                          | 0.06912                         | 0.03557                       |
| ridge                               | 6.668                        | 5.935                               | 7.506                                | 17.02                            | 15.71                                   | 17.69                                    | 0.6929                      | 0.04933                               | 0.1722                          | 0.06652                         | 0.04721                       |
| two_pulse_template_cfd_baseline     | 8.307                        | 5.786                               | 9.361                                | 22.5                             | 15.1                                    | 25                                       | 0.8057                      | 0.03886                               | 0.1861                          | 0.08334                         | 0.09623                       |
| 1d_cnn                              | 8.539                        | 7.876                               | 9.119                                | 17.54                            | 16.72                                   | 18.86                                    | 0.7948                      | 0.05337                               | 0.25                            | 0.08268                         | 0.0924                        |
| mlp                                 | 10.57                        | 7.778                               | 11.99                                | 15.7                             | 14.21                                   | 16.78                                    | 0.944                       | 0.06627                               | 0.2028                          | 0.1143                          | 0.04439                       |
| temporal_convolution_tcn            | 11.48                        | 10.38                               | 12.68                                | 21.07                            | 18.7                                    | 25.3                                     | 1.438                       | 0.09752                               | 0.1389                          | 0.1195                          | 0.05043                       |
| pileup_mask_transformer_new         | 12.96                        | 12.02                               | 14.74                                | 21.74                            | 19.2                                    | 24.72                                    | 1.331                       | 0.07419                               | 0.1639                          | 0.1209                          | 0.09381                       |
| tiny_sequence_transformer           | 15.53                        | 14.87                               | 15.99                                | 24.13                            | 22.58                                   | 27.4                                     | 1.363                       | 0.1123                                | 0.2389                          | 0.1336                          | 0.145                         |

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

| method                              | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| template_residual_boosted_stack_new | 1.878        | 5.61                         | 10.94                            | 0.5678                      | 0.06953                         | 0.3556           | 0.1611           | 0.03671                       |
| gradient_boosted_trees              | 1.925        | 5.845                        | 11.73                            | 0.5737                      | 0.06912                         | 0.3611           | 0.1583           | 0.03557                       |
| ridge                               | 2.303        | 6.668                        | 17.02                            | 0.6929                      | 0.06652                         | 0.3306           | 0.1722           | 0.04721                       |
| 1d_cnn                              | 2.674        | 8.539                        | 17.54                            | 0.7948                      | 0.08268                         | 0.2806           | 0.25             | 0.0924                        |
| mlp                                 | 2.884        | 10.57                        | 15.7                             | 0.944                       | 0.1143                          | 0.3833           | 0.2028           | 0.04439                       |
| two_pulse_template_cfd_baseline     | 3.044        | 8.307                        | 22.5                             | 0.8057                      | 0.08334                         | 0.6139           | 0.1861           | 0.09623                       |
| temporal_convolution_tcn            | 3.639        | 11.48                        | 21.07                            | 1.438                       | 0.1195                          | 0.4028           | 0.1389           | 0.05043                       |
| pileup_mask_transformer_new         | 3.757        | 12.96                        | 21.74                            | 1.331                       | 0.1209                          | 0.4333           | 0.1639           | 0.09381                       |
| tiny_sequence_transformer           | 4.14         | 15.53                        | 24.13                            | 1.363                       | 0.1336                          | 0.3361           | 0.2389           | 0.145                         |

The traditional baseline has score `3.044` and leading-edge
sigma68 `8.307` ns.  The selected winner
`template_residual_boosted_stack_new` has score `1.878` and leading-edge sigma68
`5.61` ns.

## Run-held-out stability

| method                              | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                              | 58          | -1.776       | 11.68           | 0.1887                     | 0.2639           | 0.3056           | 0.09033                   |
| 1d_cnn                              | 60          | 1.426        | 12.74           | 0.2685                     | 0.25             | 0.2639           | 0.08458                   |
| 1d_cnn                              | 62          | -0.381       | 10.31           | 0.193                      | 0.2083           | 0.2639           | 0.07057                   |
| 1d_cnn                              | 64          | 0.252        | 9.791           | 0.125                      | 0.3333           | 0.2222           | 0.06762                   |
| 1d_cnn                              | 65          | -0.3283      | 11.14           | 0.2553                     | 0.3472           | 0.1944           | 0.08499                   |
| gradient_boosted_trees              | 58          | -0.3313      | 8.524           | 0.1705                     | 0.3889           | 0.25             | 0.06188                   |
| gradient_boosted_trees              | 60          | 0.2011       | 8.1             | 0.117                      | 0.3472           | 0.2222           | 0.07381                   |
| gradient_boosted_trees              | 62          | -1.069       | 7.934           | 0.1058                     | 0.2778           | 0.125            | 0.07524                   |
| gradient_boosted_trees              | 64          | -0.01024     | 6.772           | 0.05814                    | 0.4028           | 0.1111           | 0.04889                   |
| gradient_boosted_trees              | 65          | -1.12        | 8.47            | 0.1932                     | 0.3889           | 0.08333          | 0.0569                    |
| mlp                                 | 58          | -1.122       | 12.07           | 0.2375                     | 0.4444           | 0.25             | 0.1477                    |
| mlp                                 | 60          | 0.08647      | 12.88           | 0.2917                     | 0.3333           | 0.2361           | 0.1129                    |
| mlp                                 | 62          | -0.3519      | 12.68           | 0.2255                     | 0.2917           | 0.2222           | 0.09444                   |
| mlp                                 | 64          | -0.8592      | 14.18           | 0.2955                     | 0.3889           | 0.1944           | 0.09487                   |
| mlp                                 | 65          | -1.988       | 12.85           | 0.2179                     | 0.4583           | 0.1111           | 0.1073                    |
| pileup_mask_transformer_new         | 58          | -9.463       | 14.02           | 0.3095                     | 0.4167           | 0.1944           | 0.09552                   |
| pileup_mask_transformer_new         | 60          | -7.277       | 16.56           | 0.4205                     | 0.3889           | 0.1944           | 0.1203                    |
| pileup_mask_transformer_new         | 62          | -10.5        | 14.86           | 0.4022                     | 0.3611           | 0.1944           | 0.1278                    |
| pileup_mask_transformer_new         | 64          | -9.286       | 15.71           | 0.3784                     | 0.4861           | 0.125            | 0.05095                   |
| pileup_mask_transformer_new         | 65          | -11.1        | 16.64           | 0.4429                     | 0.5139           | 0.1111           | 0.1303                    |
| ridge                               | 58          | -0.3555      | 9.251           | 0.1667                     | 0.2917           | 0.2361           | 0.06063                   |
| ridge                               | 60          | 1.479        | 7.785           | 0.1354                     | 0.3333           | 0.1944           | 0.06326                   |
| ridge                               | 62          | -0.08114     | 10.25           | 0.18                       | 0.3056           | 0.1667           | 0.06538                   |
| ridge                               | 64          | -0.1639      | 9.56            | 0.1522                     | 0.3611           | 0.125            | 0.04906                   |
| ridge                               | 65          | -2.488       | 10.91           | 0.2283                     | 0.3611           | 0.1389           | 0.06718                   |
| template_residual_boosted_stack_new | 58          | 0.4417       | 10.11           | 0.1739                     | 0.3611           | 0.2361           | 0.06503                   |
| template_residual_boosted_stack_new | 60          | 0.4908       | 7.098           | 0.125                      | 0.3333           | 0.2222           | 0.06655                   |
| template_residual_boosted_stack_new | 62          | -1.471       | 6.864           | 0.07447                    | 0.3472           | 0.1389           | 0.07185                   |
| template_residual_boosted_stack_new | 64          | -0.2182      | 6.354           | 0.06667                    | 0.375            | 0.1111           | 0.05903                   |
| template_residual_boosted_stack_new | 65          | -1.789       | 8.244           | 0.1739                     | 0.3611           | 0.09722          | 0.06079                   |
| temporal_convolution_tcn            | 58          | -11.81       | 13.78           | 0.4362                     | 0.3472           | 0.1944           | 0.1133                    |
| temporal_convolution_tcn            | 60          | -10.88       | 16.61           | 0.4651                     | 0.4028           | 0.1528           | 0.1021                    |
| temporal_convolution_tcn            | 62          | -17.07       | 12.48           | 0.5417                     | 0.3333           | 0.1528           | 0.1011                    |
| temporal_convolution_tcn            | 64          | -14.86       | 14.95           | 0.5                        | 0.4583           | 0.1389           | 0.1088                    |
| temporal_convolution_tcn            | 65          | -13.12       | 13.25           | 0.4211                     | 0.4722           | 0.05556          | 0.1228                    |
| tiny_sequence_transformer           | 58          | -8.562       | 16.58           | 0.4286                     | 0.3194           | 0.2639           | 0.1091                    |
| tiny_sequence_transformer           | 60          | -7.284       | 17.08           | 0.3725                     | 0.2917           | 0.3056           | 0.1354                    |
| tiny_sequence_transformer           | 62          | -9.918       | 15.9            | 0.4314                     | 0.2917           | 0.2639           | 0.1428                    |
| tiny_sequence_transformer           | 64          | -9.342       | 14.52           | 0.4255                     | 0.3472           | 0.1944           | 0.1463                    |
| tiny_sequence_transformer           | 65          | -7.977       | 18.55           | 0.4268                     | 0.4306           | 0.1667           | 0.1005                    |
| two_pulse_template_cfd_baseline     | 58          | 0.961        | 14.82           | 0.3214                     | 0.6111           | 0.3056           | 0.07501                   |
| two_pulse_template_cfd_baseline     | 60          | -0.5363      | 10.07           | 0.2222                     | 0.625            | 0.1667           | 0.1                       |
| two_pulse_template_cfd_baseline     | 62          | 1.836        | 6.983           | 0.1                        | 0.6528           | 0.09722          | 0.06156                   |
| two_pulse_template_cfd_baseline     | 64          | -2.212       | 10.38           | 0.2037                     | 0.625            | 0.1806           | 0.06541                   |
| two_pulse_template_cfd_baseline     | 65          | 0.2906       | 14.4            | 0.2969                     | 0.5556           | 0.1806           | 0.08118                   |

## Injection-source bootstrap stress test

As a second uncertainty check, source units are
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This is stricter than an
event bootstrap because it preserves run-local residual source, stave/PID proxy,
pile-up label, delay family, and amplitude-ratio family.

| method                              | n_source_units | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | detection_ap | detection_ap_ci_low | detection_ap_ci_high | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high |
| ----------------------------------- | -------------- | --------------- | ---------------------- | ----------------------- | ------------ | ------------------- | -------------------- | ------------------------- | -------------------------------- | --------------------------------- |
| template_residual_boosted_stack_new | 204            | 7.736           | 6.863                  | 8.722                   | 0.8381       | 0.7778              | 0.9017               | 0.06953                   | 0.05968                          | 0.08033                           |
| gradient_boosted_trees              | 204            | 7.833           | 7.022                  | 8.853                   | 0.833        | 0.7721              | 0.8933               | 0.06912                   | 0.05552                          | 0.08031                           |
| ridge                               | 204            | 9.851           | 8.984                  | 10.83                   | 0.821        | 0.7409              | 0.8931               | 0.06652                   | 0.0579                           | 0.07383                           |
| two_pulse_template_cfd_baseline     | 204            | 11.29           | 9.693                  | 13.95                   | 0.6618       | 0.5748              | 0.7691               | 0.08334                   | 0.06817                          | 0.09215                           |
| 1d_cnn                              | 204            | 11.45           | 10.36                  | 12.4                    | 0.8127       | 0.7421              | 0.8807               | 0.08268                   | 0.06803                          | 0.09987                           |
| mlp                                 | 204            | 13.07           | 11.98                  | 14.61                   | 0.7921       | 0.7226              | 0.8712               | 0.1143                    | 0.1026                           | 0.1236                            |
| temporal_convolution_tcn            | 204            | 14.28           | 12.69                  | 16.24                   | 0.8044       | 0.7193              | 0.8843               | 0.1195                    | 0.09911                          | 0.1312                            |
| pileup_mask_transformer_new         | 204            | 15.33           | 14                     | 17.22                   | 0.7675       | 0.679               | 0.8551               | 0.1209                    | 0.09449                          | 0.1393                            |
| tiny_sequence_transformer           | 204            | 16.74           | 15.1                   | 17.96                   | 0.7662       | 0.6776              | 0.8579               | 0.1336                    | 0.1154                           | 0.1527                            |

## Timing Uncertainty Calibration

| method                              | n_detected_overlap | median_predicted_timing_uncertainty_ns | empirical_coverage_1sigma | empirical_coverage_2sigma | mean_abs_timing_error_ns |
| ----------------------------------- | ------------------ | -------------------------------------- | ------------------------- | ------------------------- | ------------------------ |
| two_pulse_template_cfd_baseline     | 139                | 7.504                                  | 0.5036                    | 0.7446                    | 10.12                    |
| tiny_sequence_transformer           | 239                | 12.66                                  | 0.5021                    | 0.8222                    | 14.65                    |
| ridge                               | 241                | 7.071                                  | 0.5021                    | 0.8216                    | 8.305                    |
| 1d_cnn                              | 259                | 8.207                                  | 0.5019                    | 0.8475                    | 9.502                    |
| template_residual_boosted_stack_new | 232                | 5.281                                  | 0.5                       | 0.778                     | 7.023                    |
| gradient_boosted_trees              | 230                | 5.518                                  | 0.5                       | 0.8022                    | 7.205                    |
| mlp                                 | 222                | 8.717                                  | 0.5                       | 0.7973                    | 10.81                    |
| pileup_mask_transformer_new         | 204                | 12.63                                  | 0.5                       | 0.8088                    | 14.75                    |
| temporal_convolution_tcn            | 215                | 1.851                                  | 0.03256                   | 0.07907                   | 16.92                    |

## Systematics and caveats

The benchmark uses controlled injections into raw-ROOT-derived clean pulses, so
truth is exact for delay and amplitude but real beam pile-up frequency is not
measured.  The saturation endpoint is an amplitude-knee proxy, not electronics
metadata.  Pedestal shift is represented by clean-control false splitting and
run-local residuals, not an independent pedestal trigger stream.  PID confusion is
therefore a stave-conditioned boundary proxy rather than a particle-ID truth
confusion matrix.  The 18-sample waveform limits sub-sample deconvolution below
roughly one digitizer tick; all models inherit that sampling floor.  Finally, the
run-block bootstrap has only the finite held-out run set, so its CIs quantify
run-transfer uncertainty rather than asymptotic event uncertainty.

Runtime was `499.2` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

## Proposed next experiment

S36c should test whether conformalized timing intervals can repair the TCN
under-coverage observed here without sacrificing overlap AP.  The expected
information gain is a deployable uncertainty policy for overlapping-pulse
deconvolution, rather than another point-estimate architecture bakeoff.

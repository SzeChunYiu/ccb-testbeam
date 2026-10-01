# S71b: sub-sample pile-up separation with saturation-aware energy closure

## Abstract

Ticket `2570` asks for a run-held-out benchmark of hit-time bias, pile-up resolution, false split and merge behavior across traditional, ML, and neural sequence methods under controlled overlapping testbeam pulses.  The worker was `testbeam-laptop-1` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT, then compared a strong traditional sparse two-pulse deconvolution plus censored template-likelihood baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence
transformer, a temporal convolutional network, a new pile-up-mask transformer,
and a hybrid residual stack.  The
winner written to `result.json` is `gradient_boosted_trees` with composite endpoint score
`1.841`.

## Raw ROOT reproduction

The input files are `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.  For each file the
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

The traditional method is not a strawman.  It is a sparse deconvolution baseline with one-pulse and two-pulse template hypotheses, censoring clipped high-amplitude samples in the likelihood proxy and using the fractional optimal-filter improvement

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
| template_residual_boosted_stack_new | 0.8377       | 0.8249        | -0.4908      | 7.022           | 6.504                  | 7.482                   | 0.3444           | 0.1444           | 0.06648                   |
| gradient_boosted_trees              | 0.838        | 0.8319        | -0.5472      | 7.318           | 7.05                   | 7.898                   | 0.3028           | 0.1806           | 0.07154                   |
| ridge                               | 0.8248       | 0.823         | -0.7397      | 8.586           | 7.689                  | 9.342                   | 0.3              | 0.1944           | 0.06905                   |
| two_pulse_template_cfd_baseline     | 0.6481       | 0.5973        | -0.08149     | 9.103           | 7.4                    | 11.1                    | 0.6333           | 0.1806           | 0.0902                    |
| mlp                                 | 0.8267       | 0.8305        | -0.4338      | 9.823           | 9.148                  | 10.79                   | 0.325            | 0.1778           | 0.1204                    |
| 1d_cnn                              | 0.7903       | 0.7896        | -1.133       | 10.33           | 9.897                  | 10.86                   | 0.4167           | 0.1639           | 0.09087                   |
| temporal_convolution_tcn            | 0.823        | 0.8039        | -0.7513      | 12.46           | 11.41                  | 13.52                   | 0.375            | 0.1944           | 0.1318                    |
| tiny_sequence_transformer           | 0.7812       | 0.7756        | -8.661       | 13.1            | 11.96                  | 14.94                   | 0.3417           | 0.2333           | 0.1072                    |
| pileup_mask_transformer_new         | 0.7721       | 0.7773        | -7.31        | 16.07           | 14.99                  | 17.07                   | 0.4139           | 0.1806           | 0.1089                    |

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
| template_residual_boosted_stack_new | 5.465                        | 4.764                               | 5.9                                  | 11.16                            | 9.802                                   | 12.05                                    | 0.5722                      | 0.06323                               | 0.1444                          | 0.06648                         | 0.02932                       |
| ridge                               | 5.769                        | 5.264                               | 6.649                                | 13.38                            | 12.15                                   | 14.78                                    | 0.5957                      | 0.03603                               | 0.1944                          | 0.06905                         | 0.08407                       |
| gradient_boosted_trees              | 5.92                         | 5.173                               | 6.418                                | 10.99                            | 9.354                                   | 12.07                                    | 0.5699                      | 0.05302                               | 0.1806                          | 0.07154                         | 0.01526                       |
| two_pulse_template_cfd_baseline     | 6.548                        | 5.059                               | 8.28                                 | 15                               | 12.5                                    | 23.2                                     | 0.6807                      | 0.04067                               | 0.1806                          | 0.0902                          | 0.08789                       |
| 1d_cnn                              | 7.965                        | 7.12                                | 8.664                                | 17.3                             | 16.96                                   | 18.19                                    | 0.7768                      | 0.08225                               | 0.1639                          | 0.09087                         | 0.1103                        |
| mlp                                 | 8.253                        | 7.602                               | 9.081                                | 13.32                            | 11.86                                   | 13.79                                    | 0.7828                      | 0.07265                               | 0.1778                          | 0.1204                          | 0.04458                       |
| temporal_convolution_tcn            | 10.43                        | 9.271                               | 10.95                                | 17.38                            | 15.47                                   | 20.65                                    | 1.024                       | 0.03064                               | 0.1944                          | 0.1318                          | 0.03938                       |
| tiny_sequence_transformer           | 13.01                        | 11.38                               | 13.56                                | 17.6                             | 13.75                                   | 20.06                                    | 1.188                       | 0.08246                               | 0.2333                          | 0.1072                          | 0.09662                       |
| pileup_mask_transformer_new         | 13.93                        | 13.03                               | 15                                   | 21.76                            | 20.53                                   | 24.06                                    | 1.202                       | 0.08377                               | 0.1806                          | 0.1089                          | 0.09181                       |

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

| method                              | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| gradient_boosted_trees              | 1.841        | 5.92                         | 10.99                            | 0.5699                      | 0.07154                         | 0.3028           | 0.1806           | 0.01526                       |
| template_residual_boosted_stack_new | 1.843        | 5.465                        | 11.16                            | 0.5722                      | 0.06648                         | 0.3444           | 0.1444           | 0.02932                       |
| ridge                               | 2.091        | 5.769                        | 13.38                            | 0.5957                      | 0.06905                         | 0.3              | 0.1944           | 0.08407                       |
| mlp                                 | 2.48         | 8.253                        | 13.32                            | 0.7828                      | 0.1204                          | 0.325            | 0.1778           | 0.04458                       |
| two_pulse_template_cfd_baseline     | 2.543        | 6.548                        | 15                               | 0.6807                      | 0.0902                          | 0.6333           | 0.1806           | 0.08789                       |
| 1d_cnn                              | 2.708        | 7.965                        | 17.3                             | 0.7768                      | 0.09087                         | 0.4167           | 0.1639           | 0.1103                        |
| temporal_convolution_tcn            | 3.056        | 10.43                        | 17.38                            | 1.024                       | 0.1318                          | 0.375            | 0.1944           | 0.03938                       |
| tiny_sequence_transformer           | 3.402        | 13.01                        | 17.6                             | 1.188                       | 0.1072                          | 0.3417           | 0.2333           | 0.09662                       |
| pileup_mask_transformer_new         | 3.636        | 13.93                        | 21.76                            | 1.202                       | 0.1089                          | 0.4139           | 0.1806           | 0.09181                       |

The traditional baseline has score `2.543` and leading-edge
sigma68 `6.548` ns.  The selected winner
`gradient_boosted_trees` has score `1.841` and leading-edge sigma68
`5.92` ns.

## Run-held-out stability

| method                              | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                              | 58          | -0.406       | 10.06           | 0.1625                     | 0.4444           | 0.1944           | 0.09799                   |
| 1d_cnn                              | 60          | -2.472       | 10.55           | 0.1786                     | 0.4167           | 0.1944           | 0.08141                   |
| 1d_cnn                              | 62          | -0.5181      | 10.37           | 0.1698                     | 0.2639           | 0.1944           | 0.09437                   |
| 1d_cnn                              | 64          | 0.9171       | 9.8             | 0.1                        | 0.4444           | 0.125            | 0.08245                   |
| 1d_cnn                              | 65          | -2.471       | 8.961           | 0.1429                     | 0.5139           | 0.1111           | 0.07782                   |
| gradient_boosted_trees              | 58          | -0.5165      | 6.853           | 0.1132                     | 0.2639           | 0.2222           | 0.0642                    |
| gradient_boosted_trees              | 60          | -1.302       | 8.089           | 0.1111                     | 0.25             | 0.2361           | 0.08043                   |
| gradient_boosted_trees              | 62          | 0.4718       | 7.634           | 0.08491                    | 0.2639           | 0.2222           | 0.07309                   |
| gradient_boosted_trees              | 64          | 0.253        | 6.918           | 0.05208                    | 0.3333           | 0.1389           | 0.07332                   |
| gradient_boosted_trees              | 65          | -2.43        | 6.632           | 0.06977                    | 0.4028           | 0.08333          | 0.05032                   |
| mlp                                 | 58          | -0.3793      | 9.585           | 0.1633                     | 0.3194           | 0.2083           | 0.1077                    |
| mlp                                 | 60          | -0.7097      | 9.175           | 0.1939                     | 0.3194           | 0.1806           | 0.1128                    |
| mlp                                 | 62          | -1.031       | 10.91           | 0.1949                     | 0.1806           | 0.1806           | 0.1169                    |
| mlp                                 | 64          | 0.1619       | 10.88           | 0.1744                     | 0.4028           | 0.1667           | 0.1097                    |
| mlp                                 | 65          | -0.3372      | 9.989           | 0.1628                     | 0.4028           | 0.1528           | 0.139                     |
| pileup_mask_transformer_new         | 58          | -7.282       | 16.72           | 0.4444                     | 0.375            | 0.2361           | 0.08923                   |
| pileup_mask_transformer_new         | 60          | -8.801       | 17.75           | 0.4146                     | 0.4306           | 0.1944           | 0.1092                    |
| pileup_mask_transformer_new         | 62          | -8.557       | 14.78           | 0.4286                     | 0.3194           | 0.1806           | 0.09887                   |
| pileup_mask_transformer_new         | 64          | -4.551       | 15.06           | 0.3902                     | 0.4306           | 0.1528           | 0.1187                    |
| pileup_mask_transformer_new         | 65          | -7.663       | 14.68           | 0.4                        | 0.5139           | 0.1389           | 0.1037                    |
| ridge                               | 58          | -0.5836      | 9.828           | 0.1389                     | 0.25             | 0.2083           | 0.06111                   |
| ridge                               | 60          | -0.08192     | 7.639           | 0.1275                     | 0.2917           | 0.1667           | 0.08316                   |
| ridge                               | 62          | 0.7021       | 9.178           | 0.1429                     | 0.2222           | 0.1944           | 0.07199                   |
| ridge                               | 64          | -0.4575      | 6.839           | 0.07955                    | 0.3889           | 0.1667           | 0.05021                   |
| ridge                               | 65          | -2.585       | 7.337           | 0.1489                     | 0.3472           | 0.2361           | 0.05564                   |
| template_residual_boosted_stack_new | 58          | -0.451       | 7.603           | 0.1                        | 0.3056           | 0.1528           | 0.0485                    |
| template_residual_boosted_stack_new | 60          | -1.269       | 7.165           | 0.07778                    | 0.375            | 0.125            | 0.06377                   |
| template_residual_boosted_stack_new | 62          | 0.8856       | 6.282           | 0.07843                    | 0.2917           | 0.1667           | 0.07948                   |
| template_residual_boosted_stack_new | 64          | 0.8414       | 7.361           | 0.07447                    | 0.3472           | 0.1389           | 0.07066                   |
| template_residual_boosted_stack_new | 65          | -2.345       | 6.247           | 0.0814                     | 0.4028           | 0.1389           | 0.06614                   |
| temporal_convolution_tcn            | 58          | -0.1486      | 11.16           | 0.1889                     | 0.375            | 0.2083           | 0.1032                    |
| temporal_convolution_tcn            | 60          | -1.544       | 13.17           | 0.2791                     | 0.4028           | 0.2083           | 0.1679                    |
| temporal_convolution_tcn            | 62          | -2.837       | 11.64           | 0.1887                     | 0.2639           | 0.2083           | 0.1365                    |
| temporal_convolution_tcn            | 64          | 0.9009       | 13.46           | 0.2386                     | 0.3889           | 0.1806           | 0.1583                    |
| temporal_convolution_tcn            | 65          | -1.411       | 11.16           | 0.2                        | 0.4444           | 0.1667           | 0.1086                    |
| tiny_sequence_transformer           | 58          | -7.864       | 13.99           | 0.35                       | 0.3056           | 0.25             | 0.1012                    |
| tiny_sequence_transformer           | 60          | -8.627       | 13.27           | 0.3696                     | 0.3611           | 0.2222           | 0.1313                    |
| tiny_sequence_transformer           | 62          | -9.39        | 11.66           | 0.4                        | 0.2361           | 0.25             | 0.1047                    |
| tiny_sequence_transformer           | 64          | -8.658       | 15.89           | 0.3977                     | 0.3889           | 0.2083           | 0.1015                    |
| tiny_sequence_transformer           | 65          | -9.111       | 11.98           | 0.3452                     | 0.4167           | 0.2361           | 0.1013                    |
| two_pulse_template_cfd_baseline     | 58          | 0.1778       | 10.35           | 0.1667                     | 0.625            | 0.1944           | 0.06659                   |
| two_pulse_template_cfd_baseline     | 60          | -1.456       | 7.928           | 0.2368                     | 0.7361           | 0.2083           | 0.1056                    |
| two_pulse_template_cfd_baseline     | 62          | -0.4622      | 11.38           | 0.2                        | 0.5139           | 0.1806           | 0.1074                    |
| two_pulse_template_cfd_baseline     | 64          | 0.2468       | 6.61            | 0.1111                     | 0.625            | 0.1528           | 0.04616                   |
| two_pulse_template_cfd_baseline     | 65          | 2.378        | 6.451           | 0.08333                    | 0.6667           | 0.1667           | 0.06815                   |

## Injection-source bootstrap stress test

As a second uncertainty check, source units are
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This is stricter than an
event bootstrap because it preserves run-local residual source, stave/PID proxy,
pile-up label, delay family, and amplitude-ratio family.

| method                              | n_source_units | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | detection_ap | detection_ap_ci_low | detection_ap_ci_high | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high |
| ----------------------------------- | -------------- | --------------- | ---------------------- | ----------------------- | ------------ | ------------------- | -------------------- | ------------------------- | -------------------------------- | --------------------------------- |
| template_residual_boosted_stack_new | 202            | 7.022           | 6.238                  | 7.875                   | 0.8377       | 0.7679              | 0.9016               | 0.06648                   | 0.05861                          | 0.07524                           |
| gradient_boosted_trees              | 202            | 7.318           | 6.651                  | 8.217                   | 0.838        | 0.7531              | 0.9001               | 0.07154                   | 0.05971                          | 0.08136                           |
| ridge                               | 202            | 8.586           | 7.612                  | 9.356                   | 0.8248       | 0.7611              | 0.8991               | 0.06905                   | 0.05899                          | 0.07799                           |
| two_pulse_template_cfd_baseline     | 202            | 9.103           | 7.429                  | 11.6                    | 0.6481       | 0.5615              | 0.7875               | 0.0902                    | 0.06728                          | 0.1097                            |
| mlp                                 | 202            | 9.823           | 8.753                  | 11.44                   | 0.8267       | 0.7439              | 0.9003               | 0.1204                    | 0.1075                           | 0.1411                            |
| 1d_cnn                              | 202            | 10.33           | 9.424                  | 11.37                   | 0.7903       | 0.7067              | 0.8671               | 0.09087                   | 0.07896                          | 0.09776                           |
| temporal_convolution_tcn            | 202            | 12.46           | 11.11                  | 13.96                   | 0.823        | 0.735               | 0.885                | 0.1318                    | 0.115                            | 0.1527                            |
| tiny_sequence_transformer           | 202            | 13.1            | 12.19                  | 14.77                   | 0.7812       | 0.7034              | 0.8665               | 0.1072                    | 0.09463                          | 0.1211                            |
| pileup_mask_transformer_new         | 202            | 16.07           | 14.49                  | 17                      | 0.7721       | 0.6743              | 0.8543               | 0.1089                    | 0.09433                          | 0.124                             |

## Timing Uncertainty Calibration

| method                              | n_detected_overlap | median_predicted_timing_uncertainty_ns | empirical_coverage_1sigma | empirical_coverage_2sigma | mean_abs_timing_error_ns |
| ----------------------------------- | ------------------ | -------------------------------------- | ------------------------- | ------------------------- | ------------------------ |
| pileup_mask_transformer_new         | 211                | 12.55                                  | 0.5024                    | 0.8531                    | 14.21                    |
| tiny_sequence_transformer           | 237                | 11.53                                  | 0.5021                    | 0.8439                    | 13.26                    |
| mlp                                 | 243                | 6.625                                  | 0.5021                    | 0.7778                    | 8.504                    |
| gradient_boosted_trees              | 251                | 4.753                                  | 0.502                     | 0.7669                    | 6.436                    |
| template_residual_boosted_stack_new | 236                | 4.751                                  | 0.5                       | 0.7797                    | 6.349                    |
| ridge                               | 252                | 5.697                                  | 0.5                       | 0.7798                    | 7.335                    |
| two_pulse_template_cfd_baseline     | 132                | 5.782                                  | 0.5                       | 0.7311                    | 8.365                    |
| 1d_cnn                              | 210                | 7.21                                   | 0.5                       | 0.8286                    | 8.589                    |
| temporal_convolution_tcn            | 225                | 1.894                                  | 0.1156                    | 0.2111                    | 10.44                    |

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

Runtime was `548.8` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

## Proposed next experiment

S36c should test whether conformalized timing intervals can repair the TCN
under-coverage observed here without sacrificing overlap AP.  The expected
information gain is a deployable uncertainty policy for overlapping-pulse
deconvolution, rather than another point-estimate architecture bakeoff.

## Ticket 2570 binding

This S71b wrapper was run after the single ticket claim for `#2570`.  The analysis compares the required families: sparse deconvolution plus censored template likelihood, ridge, gradient-boosted trees, MLP, 1D-CNN, a transformer sequence model, and new masked/hybrid sequence architectures.  The primary limitation is that exact pile-up truth is supplied by controlled sub-sample injections into raw-ROOT-derived clean pulses; the raw ROOT files do not contain particle truth or a separately labeled real pile-up catalog.

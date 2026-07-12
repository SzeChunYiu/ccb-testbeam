# S32b: pile-up onset deconvolution frontier for saturated pulse tails

## Abstract

Ticket `1783886867.735.59c92683` asks whether saturation-clipped pulse peaks can
be deconvolved using late-tail and neighboring-channel waveform evidence without
corrupting PID, under a run-held-out architecture bakeoff.  The worker was
`testbeam-laptop-3` and the project was `testbeam`.  The study first reproduced
the selected B-stack pulse count directly from raw ROOT, then compared a strong
traditional two-pulse template/optimal-filter baseline against ridge,
gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, a new pile-up-mask
transformer, and a hybrid residual stack.  The winner written to `result.json`
is `template_residual_boosted_stack_new` with composite endpoint score `2.001`.

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

## Methods and equations

| method                              | family              | description                                                                     |
| ----------------------------------- | ------------------- | ------------------------------------------------------------------------------- |
| two_pulse_template_cfd_baseline     | traditional         | bounded two-pulse template deconvolution with CFD/optimal-filter initialization |
| ridge                               | linear ML           | ridge classifier plus multi-output ridge regression on waveform features        |
| gradient_boosted_trees              | tree ML             | histogram gradient-boosted classifier/regressors                                |
| mlp                                 | neural network      | tabular multilayer perceptron classifier/regressor pair                         |
| 1d_cnn                              | neural network      | compact one-dimensional convolutional waveform model                            |
| tiny_sequence_transformer           | neural sequence     | one-layer self-attention encoder over 18 samples                                |
| pileup_mask_transformer_new         | new neural sequence | self-attention model with deterministic late/overlap mask channel               |
| template_residual_boosted_stack_new | new hybrid          | boosted residual correction stack using traditional deconvolver outputs         |

The traditional method is not a strawman.  It fits one-pulse and two-pulse
template hypotheses and uses the fractional optimal-filter improvement

`I = (SSE_1 - SSE_2) / SSE_1`,

where

`SSE_k = sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`.

The new architecture is the mask transformer, which adds a second input channel `m(t)`: `m(t)=1` after the
observed primary peak plus one sample, `m(t)=0.35` for the two samples before
that boundary, and `m(t)=0` elsewhere.  It is label-free and encodes where late
curvature from unresolved second pulses can appear.

## Primary held-out method metrics

| method                              | detection_ap | detection_auc | time_bias_ns | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ------------ | ------------- | ------------ | --------------- | ---------------------- | ----------------------- | ---------------- | ---------------- | ------------------------- |
| gradient_boosted_trees              | 0.8112       | 0.8011        | -1.429       | 8.068           | 7.463                  | 8.982                   | 0.3444           | 0.2              | 0.07392                   |
| template_residual_boosted_stack_new | 0.8208       | 0.8111        | -1.384       | 8.603           | 7.895                  | 9.44                    | 0.3472           | 0.1944           | 0.06929                   |
| two_pulse_template_cfd_baseline     | 0.6582       | 0.6064        | 0.1744       | 9.437           | 8.413                  | 11.12                   | 0.5944           | 0.1944           | 0.08217                   |
| ridge                               | 0.8018       | 0.8092        | 0.2138       | 10.3            | 9.274                  | 10.69                   | 0.3444           | 0.1944           | 0.06322                   |
| 1d_cnn                              | 0.7909       | 0.7916        | -1.188       | 11.55           | 10.9                   | 12.73                   | 0.3083           | 0.2389           | 0.09695                   |
| pileup_mask_transformer_new         | 0.7873       | 0.7882        | -8.842       | 12.9            | 11.61                  | 15.36                   | 0.2528           | 0.2778           | 0.08303                   |
| mlp                                 | 0.8062       | 0.7911        | 0.5122       | 14.3            | 13.5                   | 15.42                   | 0.3333           | 0.2083           | 0.1382                    |
| tiny_sequence_transformer           | 0.7613       | 0.7686        | -10.32       | 17.18           | 16.28                  | 18.25                   | 0.3444           | 0.2361           | 0.1214                    |

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
| gradient_boosted_trees              | 5.823                        | 5.037                               | 6.501                                | 12.21                            | 10.84                                   | 12.72                                    | 0.6256                      | 0.09192                               | 0.2                             | 0.07392                         | 0.04934                       |
| two_pulse_template_cfd_baseline     | 6.389                        | 5.37                                | 7.87                                 | 16.25                            | 11.25                                   | 20                                       | 0.7134                      | 0.0305                                | 0.1944                          | 0.08217                         | 0.1152                        |
| template_residual_boosted_stack_new | 6.447                        | 6.052                               | 7.264                                | 12.13                            | 10.95                                   | 13.22                                    | 0.6163                      | 0.1155                                | 0.1944                          | 0.06929                         | 0.02225                       |
| ridge                               | 7.756                        | 6.839                               | 8.862                                | 15.75                            | 14.32                                   | 17.14                                    | 0.6718                      | 0.05746                               | 0.1944                          | 0.06322                         | 0.07617                       |
| 1d_cnn                              | 9.065                        | 8.226                               | 9.779                                | 17.49                            | 16.17                                   | 17.75                                    | 0.8044                      | 0.09507                               | 0.2389                          | 0.09695                         | 0.09647                       |
| pileup_mask_transformer_new         | 10.68                        | 9.856                               | 11.45                                | 20.64                            | 16.92                                   | 23.42                                    | 1.077                       | 0.08063                               | 0.2778                          | 0.08303                         | 0.03334                       |
| mlp                                 | 11.7                         | 9.593                               | 12.18                                | 19.09                            | 17.99                                   | 21.03                                    | 1.11                        | 0.1051                                | 0.2083                          | 0.1382                          | 0.08565                       |
| tiny_sequence_transformer           | 13.8                         | 12.76                               | 14.1                                 | 25.3                             | 24.14                                   | 25.88                                    | 1.431                       | 0.121                                 | 0.2361                          | 0.1214                          | 0.08488                       |

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

| method                              | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| template_residual_boosted_stack_new | 2.001        | 6.447                        | 12.13                            | 0.6163                      | 0.06929                         | 0.3472           | 0.1944           | 0.02225                       |
| gradient_boosted_trees              | 2.052        | 5.823                        | 12.21                            | 0.6256                      | 0.07392                         | 0.3444           | 0.2              | 0.04934                       |
| ridge                               | 2.355        | 7.756                        | 15.75                            | 0.6718                      | 0.06322                         | 0.3444           | 0.1944           | 0.07617                       |
| two_pulse_template_cfd_baseline     | 2.633        | 6.389                        | 16.25                            | 0.7134                      | 0.08217                         | 0.5944           | 0.1944           | 0.1152                        |
| 1d_cnn                              | 2.769        | 9.065                        | 17.49                            | 0.8044                      | 0.09695                         | 0.3083           | 0.2389           | 0.09647                       |
| pileup_mask_transformer_new         | 3.071        | 10.68                        | 20.64                            | 1.077                       | 0.08303                         | 0.2528           | 0.2778           | 0.03334                       |
| mlp                                 | 3.37         | 11.7                         | 19.09                            | 1.11                        | 0.1382                          | 0.3333           | 0.2083           | 0.08565                       |
| tiny_sequence_transformer           | 4.015        | 13.8                         | 25.3                             | 1.431                       | 0.1214                          | 0.3444           | 0.2361           | 0.08488                       |

The traditional baseline has score `2.633` and leading-edge
sigma68 `6.389` ns.  The selected winner
`template_residual_boosted_stack_new` has score `2.001` and leading-edge sigma68
`6.447` ns.

## Run-held-out stability

| method                              | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                              | 58          | -1.893       | 10.88           | 0.1792                     | 0.2639           | 0.25             | 0.08945                   |
| 1d_cnn                              | 60          | -0.3083      | 13.65           | 0.2174                     | 0.3611           | 0.2639           | 0.08694                   |
| 1d_cnn                              | 62          | -1.743       | 10.44           | 0.1379                     | 0.1944           | 0.3333           | 0.07365                   |
| 1d_cnn                              | 64          | -1.782       | 12.44           | 0.2283                     | 0.3611           | 0.1667           | 0.105                     |
| 1d_cnn                              | 65          | -0.8806      | 10.24           | 0.1413                     | 0.3611           | 0.1806           | 0.09532                   |
| gradient_boosted_trees              | 58          | -1.613       | 8.349           | 0.1327                     | 0.3194           | 0.2917           | 0.0642                    |
| gradient_boosted_trees              | 60          | 0.03274      | 8.177           | 0.09783                    | 0.3611           | 0.1944           | 0.08041                   |
| gradient_boosted_trees              | 62          | -1.744       | 9.292           | 0.1731                     | 0.2778           | 0.2083           | 0.07831                   |
| gradient_boosted_trees              | 64          | -1.765       | 8.612           | 0.08333                    | 0.4167           | 0.1389           | 0.07201                   |
| gradient_boosted_trees              | 65          | -1.57        | 6.421           | 0.07447                    | 0.3472           | 0.1667           | 0.07205                   |
| mlp                                 | 58          | 4.315        | 12.97           | 0.2653                     | 0.3194           | 0.1806           | 0.1232                    |
| mlp                                 | 60          | 0.4855       | 14.87           | 0.3265                     | 0.3194           | 0.2639           | 0.1972                    |
| mlp                                 | 62          | 0.1532       | 15.95           | 0.3545                     | 0.2361           | 0.3056           | 0.1104                    |
| mlp                                 | 64          | -2.344       | 14.3            | 0.3111                     | 0.375            | 0.1528           | 0.1186                    |
| mlp                                 | 65          | 1.71         | 14.36           | 0.2381                     | 0.4167           | 0.1389           | 0.136                     |
| pileup_mask_transformer_new         | 58          | -7.546       | 12.83           | 0.3077                     | 0.2778           | 0.375            | 0.08823                   |
| pileup_mask_transformer_new         | 60          | -8.645       | 15.76           | 0.3462                     | 0.2778           | 0.2778           | 0.0821                    |
| pileup_mask_transformer_new         | 62          | -9.12        | 15.45           | 0.4032                     | 0.1389           | 0.2917           | 0.08244                   |
| pileup_mask_transformer_new         | 64          | -10.14       | 12.28           | 0.3774                     | 0.2639           | 0.2222           | 0.0792                    |
| pileup_mask_transformer_new         | 65          | -8.994       | 10.04           | 0.29                       | 0.3056           | 0.2222           | 0.08353                   |
| ridge                               | 58          | 0.315        | 9.575           | 0.1735                     | 0.3194           | 0.2083           | 0.06241                   |
| ridge                               | 60          | 2.222        | 9.637           | 0.1531                     | 0.3194           | 0.2917           | 0.07933                   |
| ridge                               | 62          | -2.375       | 11.16           | 0.1633                     | 0.3194           | 0.2083           | 0.07232                   |
| ridge                               | 64          | 0.5071       | 10.11           | 0.0814                     | 0.4028           | 0.1528           | 0.05556                   |
| ridge                               | 65          | -0.3647      | 8.72            | 0.1087                     | 0.3611           | 0.1111           | 0.0552                    |
| template_residual_boosted_stack_new | 58          | -1.468       | 8.255           | 0.102                      | 0.3194           | 0.2778           | 0.07402                   |
| template_residual_boosted_stack_new | 60          | -0.4699      | 9.487           | 0.13                       | 0.3056           | 0.1944           | 0.07946                   |
| template_residual_boosted_stack_new | 62          | -1.74        | 8.536           | 0.1667                     | 0.2917           | 0.2083           | 0.08311                   |
| template_residual_boosted_stack_new | 64          | -1.51        | 8.575           | 0.07317                    | 0.4306           | 0.1389           | 0.07173                   |
| template_residual_boosted_stack_new | 65          | -1.408       | 7.509           | 0.07955                    | 0.3889           | 0.1528           | 0.06199                   |
| tiny_sequence_transformer           | 58          | -10.43       | 17.09           | 0.43                       | 0.3056           | 0.2639           | 0.1099                    |
| tiny_sequence_transformer           | 60          | -9.746       | 17.52           | 0.3977                     | 0.3889           | 0.25             | 0.1037                    |
| tiny_sequence_transformer           | 62          | -10.26       | 18.5            | 0.4245                     | 0.2639           | 0.2778           | 0.1211                    |
| tiny_sequence_transformer           | 64          | -14.34       | 16.34           | 0.5111                     | 0.375            | 0.1667           | 0.1456                    |
| tiny_sequence_transformer           | 65          | -8.787       | 15.54           | 0.375                      | 0.3889           | 0.2222           | 0.1218                    |
| two_pulse_template_cfd_baseline     | 58          | 1.696        | 8.507           | 0.1296                     | 0.625            | 0.2083           | 0.06888                   |
| two_pulse_template_cfd_baseline     | 60          | -0.5708      | 8.133           | 0.08                       | 0.6528           | 0.1667           | 0.1147                    |
| two_pulse_template_cfd_baseline     | 62          | 0.4767       | 8.046           | 0.08065                    | 0.5694           | 0.1528           | 0.05543                   |
| two_pulse_template_cfd_baseline     | 64          | -0.03701     | 13.06           | 0.2241                     | 0.5972           | 0.25             | 0.08964                   |
| two_pulse_template_cfd_baseline     | 65          | -0.9066      | 8.951           | 0.2059                     | 0.5278           | 0.1944           | 0.06659                   |

## Injection-source bootstrap stress test

As a second uncertainty check, source units are
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This is stricter than an
event bootstrap because it preserves run-local residual source, stave/PID proxy,
pile-up label, delay family, and amplitude-ratio family.

| method                              | n_source_units | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | detection_ap | detection_ap_ci_low | detection_ap_ci_high | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high |
| ----------------------------------- | -------------- | --------------- | ---------------------- | ----------------------- | ------------ | ------------------- | -------------------- | ------------------------- | -------------------------------- | --------------------------------- |
| gradient_boosted_trees              | 211            | 8.068           | 7.102                  | 8.976                   | 0.8112       | 0.7415              | 0.8892               | 0.07392                   | 0.06099                          | 0.08354                           |
| template_residual_boosted_stack_new | 211            | 8.603           | 7.561                  | 9.487                   | 0.8208       | 0.7477              | 0.8976               | 0.06929                   | 0.06264                          | 0.08311                           |
| two_pulse_template_cfd_baseline     | 211            | 9.437           | 8.089                  | 10.72                   | 0.6582       | 0.5652              | 0.7674               | 0.08217                   | 0.06637                          | 0.09578                           |
| ridge                               | 211            | 10.3            | 9.122                  | 10.99                   | 0.8018       | 0.7192              | 0.8777               | 0.06322                   | 0.05649                          | 0.07301                           |
| 1d_cnn                              | 211            | 11.55           | 10.64                  | 12.56                   | 0.7909       | 0.6967              | 0.8724               | 0.09695                   | 0.08064                          | 0.1042                            |
| pileup_mask_transformer_new         | 211            | 12.9            | 11.49                  | 15.43                   | 0.7873       | 0.706               | 0.8604               | 0.08303                   | 0.07501                          | 0.09639                           |
| mlp                                 | 211            | 14.3            | 13.11                  | 15.53                   | 0.8062       | 0.724               | 0.8851               | 0.1382                    | 0.1199                           | 0.1572                            |
| tiny_sequence_transformer           | 211            | 17.18           | 15.71                  | 18.59                   | 0.7613       | 0.6652              | 0.8511               | 0.1214                    | 0.1051                           | 0.1346                            |

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

Runtime was `292.6` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

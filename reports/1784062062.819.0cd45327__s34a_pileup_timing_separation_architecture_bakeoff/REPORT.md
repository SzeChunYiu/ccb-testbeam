# S34a: pulse timing and pile-up separation architecture bakeoff

## Abstract

Ticket `1784062062.819.0cd45327` asks for a run-held-out benchmark of hit-time bias, pile-up resolution, false split and merge behavior across traditional, ML, and neural sequence methods under controlled overlapping testbeam pulses.  The worker was `testbeam-laptop-4` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT, then compared a strong traditional two-pulse template/optimal-filter
baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence
transformer, a new pile-up-mask transformer, and a hybrid residual stack.  The
winner written to `result.json` is `template_residual_boosted_stack_new` with composite endpoint score
`1.807`.

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

## Primary held-out method metrics

| method                              | detection_ap | detection_auc | time_bias_ns | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ------------ | ------------- | ------------ | --------------- | ---------------------- | ----------------------- | ---------------- | ---------------- | ------------------------- |
| gradient_boosted_trees              | 0.8519       | 0.8358        | 0.03526      | 7.224           | 6.634                  | 8.535                   | 0.3222           | 0.1444           | 0.07314                   |
| template_residual_boosted_stack_new | 0.8547       | 0.8321        | -0.2083      | 7.328           | 6.434                  | 8.349                   | 0.3139           | 0.1556           | 0.06776                   |
| ridge                               | 0.8407       | 0.8368        | 0.154        | 10.1            | 9.059                  | 10.61                   | 0.2889           | 0.1833           | 0.06768                   |
| two_pulse_template_cfd_baseline     | 0.6878       | 0.6468        | 0.2374       | 10.2            | 8.293                  | 12.78                   | 0.5667           | 0.1833           | 0.08898                   |
| mlp                                 | 0.8332       | 0.823         | -0.5556      | 10.64           | 9.661                  | 10.91                   | 0.3278           | 0.175            | 0.1052                    |
| 1d_cnn                              | 0.8229       | 0.8067        | -0.007769    | 11.15           | 10.33                  | 12.73                   | 0.3667           | 0.1694           | 0.08298                   |
| tiny_sequence_transformer           | 0.8316       | 0.8176        | -8.477       | 12.49           | 10.77                  | 13.94                   | 0.2944           | 0.225            | 0.1298                    |
| pileup_mask_transformer_new         | 0.814        | 0.8121        | -4.856       | 16.9            | 15.13                  | 18.27                   | 0.45             | 0.1028           | 0.1148                    |

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
| gradient_boosted_trees              | 5.004                        | 4.545                               | 5.474                                | 10.55                            | 9.856                                   | 11.76                                    | 0.5753                      | 0.07625                               | 0.1444                          | 0.07314                         | 0.06967                       |
| template_residual_boosted_stack_new | 5.148                        | 4.675                               | 5.73                                 | 10.08                            | 8.724                                   | 12.1                                     | 0.5778                      | 0.05874                               | 0.1556                          | 0.06776                         | 0.0421                        |
| two_pulse_template_cfd_baseline     | 6.157                        | 5.444                               | 7.365                                | 17.5                             | 10.5                                    | 22.5                                     | 0.7596                      | 0.04652                               | 0.1833                          | 0.08898                         | 0.0757                        |
| ridge                               | 7.228                        | 5.89                                | 8.18                                 | 15.02                            | 13.54                                   | 17.78                                    | 0.6744                      | 0.06579                               | 0.1833                          | 0.06768                         | 0.06828                       |
| 1d_cnn                              | 7.595                        | 6.449                               | 9.273                                | 16.13                            | 14.75                                   | 17.42                                    | 0.8055                      | 0.1002                                | 0.1694                          | 0.08298                         | 0.07458                       |
| mlp                                 | 8.997                        | 7.919                               | 9.727                                | 14.13                            | 12.77                                   | 15.45                                    | 0.7815                      | 0.1418                                | 0.175                           | 0.1052                          | 0.09956                       |
| tiny_sequence_transformer           | 11.5                         | 10.55                               | 13.03                                | 17.55                            | 15.18                                   | 19.87                                    | 1.178                       | 0.1152                                | 0.225                           | 0.1298                          | 0.07549                       |
| pileup_mask_transformer_new         | 13.04                        | 11.92                               | 14.81                                | 25.62                            | 24.42                                   | 27.15                                    | 1.349                       | 0.05151                               | 0.1028                          | 0.1148                          | 0.08932                       |

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

| method                              | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| template_residual_boosted_stack_new | 1.807        | 5.148                        | 10.08                            | 0.5778                      | 0.06776                         | 0.3139           | 0.1556           | 0.0421                        |
| gradient_boosted_trees              | 1.886        | 5.004                        | 10.55                            | 0.5753                      | 0.07314                         | 0.3222           | 0.1444           | 0.06967                       |
| ridge                               | 2.259        | 7.228                        | 15.02                            | 0.6744                      | 0.06768                         | 0.2889           | 0.1833           | 0.06828                       |
| 1d_cnn                              | 2.55         | 7.595                        | 16.13                            | 0.8055                      | 0.08298                         | 0.3667           | 0.1694           | 0.07458                       |
| mlp                                 | 2.613        | 8.997                        | 14.13                            | 0.7815                      | 0.1052                          | 0.3278           | 0.175            | 0.09956                       |
| two_pulse_template_cfd_baseline     | 2.636        | 6.157                        | 17.5                             | 0.7596                      | 0.08898                         | 0.5667           | 0.1833           | 0.0757                        |
| tiny_sequence_transformer           | 3.307        | 11.5                         | 17.55                            | 1.178                       | 0.1298                          | 0.2944           | 0.225            | 0.07549                       |
| pileup_mask_transformer_new         | 3.881        | 13.04                        | 25.62                            | 1.349                       | 0.1148                          | 0.45             | 0.1028           | 0.08932                       |

The traditional baseline has score `2.636` and leading-edge
sigma68 `6.157` ns.  The selected winner
`template_residual_boosted_stack_new` has score `1.807` and leading-edge sigma68
`5.148` ns.

## Run-held-out stability

| method                              | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                              | 58          | 0.578        | 9.633           | 0.1667                     | 0.2917           | 0.2222           | 0.07801                   |
| 1d_cnn                              | 60          | -0.2012      | 13.29           | 0.225                      | 0.4444           | 0.1944           | 0.09436                   |
| 1d_cnn                              | 62          | 1.994        | 12.17           | 0.29                       | 0.3056           | 0.1944           | 0.0758                    |
| 1d_cnn                              | 64          | -0.8344      | 10.05           | 0.1562                     | 0.3333           | 0.1528           | 0.08219                   |
| 1d_cnn                              | 65          | -1.827       | 11.28           | 0.1667                     | 0.4583           | 0.08333          | 0.06827                   |
| gradient_boosted_trees              | 58          | 0.3924       | 7.462           | 0.1087                     | 0.3611           | 0.2222           | 0.06009                   |
| gradient_boosted_trees              | 60          | 0.09263      | 8.759           | 0.1087                     | 0.3611           | 0.1667           | 0.09937                   |
| gradient_boosted_trees              | 62          | 0.1293       | 8.202           | 0.07759                    | 0.1944           | 0.09722          | 0.06313                   |
| gradient_boosted_trees              | 64          | -0.8074      | 6.445           | 0.07292                    | 0.3333           | 0.125            | 0.068                     |
| gradient_boosted_trees              | 65          | 0.1882       | 6.388           | 0.03261                    | 0.3611           | 0.1111           | 0.0635                    |
| mlp                                 | 58          | -0.1041      | 10.73           | 0.1731                     | 0.2778           | 0.2639           | 0.1354                    |
| mlp                                 | 60          | -2.436       | 10.68           | 0.2326                     | 0.4028           | 0.1944           | 0.1267                    |
| mlp                                 | 62          | 0.195        | 10.61           | 0.1667                     | 0.25             | 0.1528           | 0.08831                   |
| mlp                                 | 64          | -2.131       | 9.02            | 0.117                      | 0.3472           | 0.1806           | 0.1015                    |
| mlp                                 | 65          | -0.2774      | 9.767           | 0.1413                     | 0.3611           | 0.08333          | 0.08946                   |
| pileup_mask_transformer_new         | 58          | -4.356       | 13.98           | 0.3723                     | 0.3472           | 0.1806           | 0.1091                    |
| pileup_mask_transformer_new         | 60          | -3.276       | 17.24           | 0.3816                     | 0.4722           | 0.125            | 0.1702                    |
| pileup_mask_transformer_new         | 62          | -6.839       | 17.01           | 0.4375                     | 0.4444           | 0.09722          | 0.1189                    |
| pileup_mask_transformer_new         | 64          | -4.496       | 18.49           | 0.378                      | 0.4306           | 0.06944          | 0.09329                   |
| pileup_mask_transformer_new         | 65          | -3.845       | 14.86           | 0.3281                     | 0.5556           | 0.04167          | 0.08475                   |
| ridge                               | 58          | 1.478        | 10.86           | 0.1636                     | 0.2361           | 0.2778           | 0.06548                   |
| ridge                               | 60          | -1.673       | 10.5            | 0.1569                     | 0.2917           | 0.1667           | 0.06702                   |
| ridge                               | 62          | 1.231        | 9.964           | 0.1574                     | 0.25             | 0.2222           | 0.05764                   |
| ridge                               | 64          | -0.2154      | 8.433           | 0.09                       | 0.3056           | 0.1806           | 0.06864                   |
| ridge                               | 65          | -0.8038      | 9.882           | 0.09783                    | 0.3611           | 0.06944          | 0.05368                   |
| template_residual_boosted_stack_new | 58          | 0.08017      | 8.92            | 0.09375                    | 0.3333           | 0.1944           | 0.06984                   |
| template_residual_boosted_stack_new | 60          | -0.6015      | 8.417           | 0.1383                     | 0.3472           | 0.1389           | 0.07238                   |
| template_residual_boosted_stack_new | 62          | 0.462        | 7.453           | 0.05455                    | 0.2361           | 0.1528           | 0.06397                   |
| template_residual_boosted_stack_new | 64          | -0.2886      | 6.198           | 0.05102                    | 0.3194           | 0.1944           | 0.06825                   |
| template_residual_boosted_stack_new | 65          | -0.2676      | 6.349           | 0.04167                    | 0.3333           | 0.09722          | 0.05916                   |
| tiny_sequence_transformer           | 58          | -6.576       | 12.5            | 0.3019                     | 0.2639           | 0.2917           | 0.1211                    |
| tiny_sequence_transformer           | 60          | -10.15       | 12.76           | 0.3542                     | 0.3333           | 0.1944           | 0.1617                    |
| tiny_sequence_transformer           | 62          | -8.69        | 15.27           | 0.4052                     | 0.1944           | 0.2361           | 0.1294                    |
| tiny_sequence_transformer           | 64          | -8.687       | 10.05           | 0.3163                     | 0.3194           | 0.25             | 0.1183                    |
| tiny_sequence_transformer           | 65          | -9.38        | 10.41           | 0.3261                     | 0.3611           | 0.1528           | 0.1523                    |
| two_pulse_template_cfd_baseline     | 58          | -0.3575      | 8.893           | 0.1613                     | 0.5694           | 0.2778           | 0.1039                    |
| two_pulse_template_cfd_baseline     | 60          | 0.9982       | 11.32           | 0.2576                     | 0.5417           | 0.125            | 0.1118                    |
| two_pulse_template_cfd_baseline     | 62          | 0.7928       | 14.69           | 0.2941                     | 0.5278           | 0.1389           | 0.07271                   |
| two_pulse_template_cfd_baseline     | 64          | 0.9643       | 7.096           | 0.09375                    | 0.5556           | 0.2361           | 0.08306                   |
| two_pulse_template_cfd_baseline     | 65          | -1.626       | 7.945           | 0.1538                     | 0.6389           | 0.1389           | 0.05297                   |

## Injection-source bootstrap stress test

As a second uncertainty check, source units are
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This is stricter than an
event bootstrap because it preserves run-local residual source, stave/PID proxy,
pile-up label, delay family, and amplitude-ratio family.

| method                              | n_source_units | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | detection_ap | detection_ap_ci_low | detection_ap_ci_high | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high |
| ----------------------------------- | -------------- | --------------- | ---------------------- | ----------------------- | ------------ | ------------------- | -------------------- | ------------------------- | -------------------------------- | --------------------------------- |
| gradient_boosted_trees              | 195            | 7.224           | 6.611                  | 8.46                    | 0.8519       | 0.7945              | 0.9153               | 0.07314                   | 0.06089                          | 0.07905                           |
| template_residual_boosted_stack_new | 195            | 7.328           | 6.485                  | 7.971                   | 0.8547       | 0.7975              | 0.9138               | 0.06776                   | 0.0593                           | 0.07465                           |
| ridge                               | 195            | 10.1            | 8.952                  | 10.93                   | 0.8407       | 0.7674              | 0.9089               | 0.06768                   | 0.0536                           | 0.07644                           |
| two_pulse_template_cfd_baseline     | 195            | 10.2            | 8.026                  | 12.85                   | 0.6878       | 0.5973              | 0.7823               | 0.08898                   | 0.07127                          | 0.1107                            |
| mlp                                 | 195            | 10.64           | 9.636                  | 11.21                   | 0.8332       | 0.7559              | 0.8957               | 0.1052                    | 0.09652                          | 0.1277                            |
| 1d_cnn                              | 195            | 11.15           | 10.18                  | 12.7                    | 0.8229       | 0.7422              | 0.8889               | 0.08298                   | 0.07216                          | 0.09461                           |
| tiny_sequence_transformer           | 195            | 12.49           | 11.15                  | 13.91                   | 0.8316       | 0.7662              | 0.9004               | 0.1298                    | 0.1136                           | 0.1594                            |
| pileup_mask_transformer_new         | 195            | 16.9            | 15.11                  | 18.64                   | 0.814        | 0.7393              | 0.8971               | 0.1148                    | 0.1001                           | 0.1264                            |

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

Runtime was `345.4` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29`.

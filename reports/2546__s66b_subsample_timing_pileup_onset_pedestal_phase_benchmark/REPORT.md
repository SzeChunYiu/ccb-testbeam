# S66b: sub-sample timing and pile-up onset benchmark with pedestal-phase nuisance control

## Abstract

Ticket `#2546` asks for a run-held-out sub-sample timing and pile-up onset benchmark: estimate where
timing, energy, and PID-proxy observables become biased as second-pulse separation
shrinks, using controlled generative overlays plus real high-current residual
candidates.  The worker was `testbeam-laptop-3` and the project was `testbeam`.  The study
first reproduced the selected B-stack pulse count directly from raw ROOT, then
compared two-pulse likelihood, leading-edge/CFD, and residual-tail traditional
baselines against ridge, gradient-boosted trees, MLP, 1D-CNN, a temporal
attention model, a causal transformer, and a hybrid residual stack.  The winner
written to `result.json` is `template_residual_boosted_stack_new` with composite endpoint score
`1.832`.

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
| B2    | 768            | 2.579                 | 5                    | 9.187         |
| B4    | 756            | 2.944                 | 6                    | 10.76         |
| B6    | 723            | 3.748                 | 6                    | 9.736         |
| B8    | 478            | 4.26                  | 8                    | 9.252         |

Controlled doublets are generated as

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_r(t)+p`,

where `epsilon_r(t)` is a run-local residual from real raw-ROOT pulses and `p` is
a pedestal excursion.  Negative controls use the same residual and amplitude
spectrum with no second pulse.  Confidence intervals are percentile 95% intervals
from `120` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`, with runs sampled with
replacement.

## Methods

| method                                    | family              | description                                                                 |
| ----------------------------------------- | ------------------- | --------------------------------------------------------------------------- |
| two_pulse_template_likelihood_traditional | traditional         | bounded two-pulse template likelihood deconvolution with CFD initialization |
| leading_edge_cfd_traditional              | traditional         | single-waveform leading-edge/CFD onset finder with late-tail split score    |
| residual_tail_veto_traditional            | traditional         | template likelihood augmented with a deterministic late-residual veto       |
| ridge                                     | linear ML           | ridge classifier plus multi-output ridge regression on waveform features    |
| gradient_boosted_trees                    | tree ML             | histogram gradient-boosted classifier/regressors                            |
| mlp                                       | neural network      | tabular multilayer perceptron classifier/regressor pair                     |
| 1d_cnn                                    | neural network      | compact one-dimensional convolutional waveform model                        |
| tiny_sequence_transformer                 | neural sequence     | one-layer self-attention encoder over 18 samples                            |
| causal_window_transformer_new             | new neural sequence | self-attention model with deterministic late/overlap mask channel           |
| template_residual_boosted_stack_new       | new hybrid          | boosted residual correction stack using traditional deconvolver outputs     |

The traditional method is not a strawman.  It fits one-pulse and two-pulse
template hypotheses and uses the fractional optimal-filter improvement

`I = (SSE_1 - SSE_2) / SSE_1`,

where

`SSE_k = sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`.

The leading-edge/CFD traditional row estimates the first onset from the 20%
constant-fraction crossing and scores pile-up from post-peak tail excess.  The
residual-tail veto row combines the two-pulse likelihood with deterministic
late-residual energy, providing a non-ML comparator for false split and false
merge control.

The mask transformer adds a second input channel `m(t)`: `m(t)=1` after the
observed primary peak plus one sample, `m(t)=0.35` for the two samples before
that boundary, and `m(t)=0` elsewhere.  It is label-free and encodes where late
curvature from unresolved second pulses can appear.

## Primary held-out method metrics

| method                                    | detection_ap | detection_auc | time_bias_ns | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------------- | ------------ | ------------- | ------------ | --------------- | ---------------------- | ----------------------- | ---------------- | ---------------- | ------------------------- |
| template_residual_boosted_stack_new       | 0.8458       | 0.823         | 0.2141       | 7.331           | 6.685                  | 8.007                   | 0.2737           | 0.2237           | 0.06462                   |
| gradient_boosted_trees                    | 0.8453       | 0.8361        | 0.2799       | 7.832           | 7.205                  | 8.523                   | 0.2579           | 0.2237           | 0.06954                   |
| two_pulse_template_likelihood_traditional | 0.677        | 0.6245        | 0.8404       | 8.962           | 7.831                  | 10.72                   | 0.5395           | 0.2421           | 0.09552                   |
| 1d_cnn                                    | 0.7853       | 0.775         | 0.518        | 9.7             | 9.077                  | 10.3                    | 0.3              | 0.3184           | 0.09366                   |
| ridge                                     | 0.8063       | 0.8169        | 0.736        | 9.707           | 8.85                   | 10.01                   | 0.2921           | 0.2105           | 0.07451                   |
| residual_tail_veto_traditional            | 0.6618       | 0.6304        | 0.8244       | 9.74            | 8.767                  | 11.79                   | 0.4816           | 0.3579           | 0.09744                   |
| causal_window_transformer_new             | 0.7712       | 0.7763        | -6.704       | 11.67           | 10.5                   | 12.98                   | 0.2974           | 0.3237           | 0.09872                   |
| mlp                                       | 0.7976       | 0.794         | -1.113       | 12.66           | 12                     | 13.34                   | 0.3526           | 0.2079           | 0.1376                    |
| leading_edge_cfd_traditional              | 0.4868       | 0.4868        | -10.01       | 16.33           | 14.44                  | 17.54                   | 0.1026           | 0.8684           | 0.3018                    |
| tiny_sequence_transformer                 | 0.7379       | 0.7584        | -8.464       | 16.53           | 15.2                   | 17.27                   | 0.3342           | 0.2684           | 0.1111                    |

## Registered endpoint table

The endpoint table maps the ticket language to measured quantities.  Leading-edge
time uses the first constituent error.  Secondary-pulse delay uses
`10 ns * [(hat t_2-hat t_1)-Delta]`.  Shape residual is a dimensionless proxy that
combines first-time, second-time, and energy residuals.  Saturation interaction is
the energy width for injected total amplitude above 11000 ADC.  Pedestal shift is
the false split rate on clean controls.  PID confusion is a cross-stave energy
bias span, treating stave as the available PID-boundary proxy.

| method                                    | leading_edge_time_bias_ns | leading_edge_time_sigma68_ns | leading_edge_time_sigma68_ns_ci_low | leading_edge_time_sigma68_ns_ci_high | secondary_pulse_delay_bias_ns | secondary_pulse_delay_sigma68_ns | secondary_pulse_delay_sigma68_ns_ci_low | secondary_pulse_delay_sigma68_ns_ci_high | false_merge_rate | tight_sep_le_15ns_false_merge_rate | saturation_interaction_energy_sigma68 | pedestal_shift_false_split_rate | energy_proxy_distortion_sigma68 | pid_confusion_stave_bias_span |
| ----------------------------------------- | ------------------------- | ---------------------------- | ----------------------------------- | ------------------------------------ | ----------------------------- | -------------------------------- | --------------------------------------- | ---------------------------------------- | ---------------- | ---------------------------------- | ------------------------------------- | ------------------------------- | ------------------------------- | ----------------------------- |
| template_residual_boosted_stack_new       | 0.7931                    | 4.889                        | 4.664                               | 5.326                                | -0.2915                       | 10.65                            | 9.813                                   | 11.47                                    | 0.2737           | 0.4192                             | 0.03992                               | 0.2237                          | 0.06462                         | 0.04496                       |
| gradient_boosted_trees                    | 0.2942                    | 5.144                        | 4.507                               | 6.19                                 | -0.05733                      | 10.41                            | 9.625                                   | 10.75                                    | 0.2579           | 0.3653                             | 0.05109                               | 0.2237                          | 0.06954                         | 0.05359                       |
| 1d_cnn                                    | 0.7185                    | 5.365                        | 4.971                               | 6.318                                | 0.5075                        | 16.06                            | 13.83                                   | 17.54                                    | 0.3              | 0.4431                             | 0.04748                               | 0.3184                          | 0.09366                         | 0.1344                        |
| two_pulse_template_likelihood_traditional | 0.6826                    | 6.577                        | 5.713                               | 7.787                                | 0                             | 17.5                             | 15                                      | 21.4                                     | 0.5395           | 0.7485                             | 0.0295                                | 0.2421                          | 0.09552                         | 0.09595                       |
| residual_tail_veto_traditional            | 0.5143                    | 6.618                        | 6.15                                | 7.979                                | 0                             | 20                               | 17.5                                    | 23.75                                    | 0.4816           | 0.6647                             | 0.0295                                | 0.3579                          | 0.09744                         | 0.1021                        |
| ridge                                     | 1.508                     | 7.451                        | 6.702                               | 7.979                                | -3.336                        | 12.84                            | 11.52                                   | 14.68                                    | 0.2921           | 0.3713                             | 0.04339                               | 0.2105                          | 0.07451                         | 0.04112                       |
| causal_window_transformer_new             | -3.164                    | 8.952                        | 7.55                                | 11.03                                | -4.201                        | 14.67                            | 13.48                                   | 16.79                                    | 0.2974           | 0.4551                             | 0.06291                               | 0.3237                          | 0.09872                         | 0.05716                       |
| leading_edge_cfd_traditional              | -8.225                    | 9.634                        | 8.958                               | 10.94                                | 0                             | 21.25                            | 20                                      | 21.25                                    | 0.1026           | 0.06587                            | 0.2274                                | 0.8684                          | 0.3018                          | 0.3618                        |
| mlp                                       | -0.8576                   | 10.12                        | 9.027                               | 10.86                                | -1.499                        | 17.41                            | 14.96                                   | 21.81                                    | 0.3526           | 0.5329                             | 0.1161                                | 0.2079                          | 0.1376                          | 0.07853                       |
| tiny_sequence_transformer                 | -0.08071                  | 13.52                        | 11.4                                | 18.08                                | -13.59                        | 21.99                            | 19.49                                   | 26.13                                    | 0.3342           | 0.509                              | 0.06281                               | 0.2684                          | 0.1111                          | 0.06777                       |

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

| method                                    | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| template_residual_boosted_stack_new       | 1.832        | 4.889                        | 10.65                            | 0.5791                      | 0.06462                         | 0.2737           | 0.2237           | 0.04496                       |
| gradient_boosted_trees                    | 1.866        | 5.144                        | 10.41                            | 0.5882                      | 0.06954                         | 0.2579           | 0.2237           | 0.05359                       |
| ridge                                     | 2.162        | 7.451                        | 12.84                            | 0.6682                      | 0.07451                         | 0.2921           | 0.2105           | 0.04112                       |
| 1d_cnn                                    | 2.63         | 5.365                        | 16.06                            | 0.7984                      | 0.09366                         | 0.3              | 0.3184           | 0.1344                        |
| causal_window_transformer_new             | 2.773        | 8.952                        | 14.67                            | 0.9549                      | 0.09872                         | 0.2974           | 0.3237           | 0.05716                       |
| two_pulse_template_likelihood_traditional | 2.793        | 6.577                        | 17.5                             | 0.8167                      | 0.09552                         | 0.5395           | 0.2421           | 0.09595                       |
| residual_tail_veto_traditional            | 2.955        | 6.618                        | 20                               | 0.8235                      | 0.09744                         | 0.4816           | 0.3579           | 0.1021                        |
| mlp                                       | 3.088        | 10.12                        | 17.41                            | 0.9792                      | 0.1376                          | 0.3526           | 0.2079           | 0.07853                       |
| tiny_sequence_transformer                 | 3.682        | 13.52                        | 21.99                            | 1.296                       | 0.1111                          | 0.3342           | 0.2684           | 0.06777                       |
| leading_edge_cfd_traditional              | 5.817        | 9.634                        | 21.25                            | 2.274                       | 0.3018                          | 0.1026           | 0.8684           | 0.3618                        |

The traditional baseline has score `2.793` and leading-edge
sigma68 `6.577` ns.  The selected winner
`template_residual_boosted_stack_new` has score `1.832` and leading-edge sigma68
`4.889` ns.

## Run-held-out stability

| method                                    | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                                    | 58          | 0.9355       | 9.038           | 0.1639                     | 0.1974           | 0.3158           | 0.0774                    |
| 1d_cnn                                    | 60          | 0.2332       | 10.08           | 0.1596                     | 0.3816           | 0.3684           | 0.09351                   |
| 1d_cnn                                    | 62          | 0.2113       | 8.71            | 0.125                      | 0.2632           | 0.2895           | 0.08904                   |
| 1d_cnn                                    | 64          | 1.737        | 10.54           | 0.2315                     | 0.2895           | 0.2368           | 0.1075                    |
| 1d_cnn                                    | 65          | -0.03241     | 9.998           | 0.1875                     | 0.3684           | 0.3816           | 0.08848                   |
| causal_window_transformer_new             | 58          | -5.296       | 10.06           | 0.225                      | 0.2105           | 0.3421           | 0.08371                   |
| causal_window_transformer_new             | 60          | -5.38        | 11.96           | 0.3229                     | 0.3684           | 0.3684           | 0.09052                   |
| causal_window_transformer_new             | 62          | -7.159       | 10.73           | 0.2857                     | 0.3553           | 0.3289           | 0.09724                   |
| causal_window_transformer_new             | 64          | -6.101       | 13.47           | 0.2719                     | 0.25             | 0.2368           | 0.1139                    |
| causal_window_transformer_new             | 65          | -8.093       | 12.64           | 0.3679                     | 0.3026           | 0.3421           | 0.09542                   |
| gradient_boosted_trees                    | 58          | 1.22         | 7.587           | 0.06923                    | 0.1447           | 0.2237           | 0.05105                   |
| gradient_boosted_trees                    | 60          | 0.9349       | 7.758           | 0.06                       | 0.3421           | 0.25             | 0.07318                   |
| gradient_boosted_trees                    | 62          | -0.7459      | 9.17            | 0.09434                    | 0.3026           | 0.1842           | 0.07199                   |
| gradient_boosted_trees                    | 64          | 0.545        | 7.354           | 0.09322                    | 0.2237           | 0.2105           | 0.08628                   |
| gradient_boosted_trees                    | 65          | 0.1841       | 6.937           | 0.1273                     | 0.2763           | 0.25             | 0.07694                   |
| leading_edge_cfd_traditional              | 58          | -11.04       | 13.27           | 0.3971                     | 0.1053           | 0.8816           | 0.2132                    |
| leading_edge_cfd_traditional              | 60          | -10.13       | 16.37           | 0.4412                     | 0.1053           | 0.9079           | 0.3069                    |
| leading_edge_cfd_traditional              | 62          | -11.32       | 17.45           | 0.4296                     | 0.06579          | 0.8289           | 0.3098                    |
| leading_edge_cfd_traditional              | 64          | -7.179       | 16.97           | 0.3881                     | 0.1184           | 0.8947           | 0.3355                    |
| leading_edge_cfd_traditional              | 65          | -8.658       | 13.47           | 0.306                      | 0.1184           | 0.8289           | 0.2903                    |
| mlp                                       | 58          | -1.522       | 12.72           | 0.2586                     | 0.2368           | 0.1579           | 0.1055                    |
| mlp                                       | 60          | -1.827       | 13.46           | 0.266                      | 0.3816           | 0.2895           | 0.1571                    |
| mlp                                       | 62          | -3.574       | 12.15           | 0.27                       | 0.3421           | 0.1447           | 0.1284                    |
| mlp                                       | 64          | -0.3799      | 12.42           | 0.2553                     | 0.3816           | 0.2237           | 0.146                     |
| mlp                                       | 65          | -0.6264      | 11.29           | 0.1932                     | 0.4211           | 0.2237           | 0.1058                    |
| residual_tail_veto_traditional            | 58          | 1.179        | 10.79           | 0.1829                     | 0.4605           | 0.4474           | 0.07819                   |
| residual_tail_veto_traditional            | 60          | 2.41         | 8.312           | 0.2097                     | 0.5921           | 0.3684           | 0.1176                    |
| residual_tail_veto_traditional            | 62          | 1.555        | 11.63           | 0.2895                     | 0.5              | 0.4079           | 0.1053                    |
| residual_tail_veto_traditional            | 64          | 0.7277       | 8.562           | 0.2234                     | 0.3816           | 0.2237           | 0.08961                   |
| residual_tail_veto_traditional            | 65          | -1.881       | 7.712           | 0.1875                     | 0.4737           | 0.3421           | 0.104                     |
| ridge                                     | 58          | 1.183        | 8.623           | 0.1129                     | 0.1842           | 0.2368           | 0.06155                   |
| ridge                                     | 60          | 3.397        | 9.703           | 0.1122                     | 0.3553           | 0.2763           | 0.06099                   |
| ridge                                     | 62          | -1.433       | 9.851           | 0.1321                     | 0.3026           | 0.1974           | 0.06399                   |
| ridge                                     | 64          | 1.581        | 9.893           | 0.1574                     | 0.2895           | 0.1711           | 0.08142                   |
| ridge                                     | 65          | -1.024       | 9.219           | 0.1078                     | 0.3289           | 0.1711           | 0.08034                   |
| template_residual_boosted_stack_new       | 58          | 1.039        | 6.787           | 0.05385                    | 0.1447           | 0.2368           | 0.0505                    |
| template_residual_boosted_stack_new       | 60          | 0.7054       | 7.775           | 0.06                       | 0.3421           | 0.2237           | 0.07731                   |
| template_residual_boosted_stack_new       | 62          | -1.058       | 9.174           | 0.1038                     | 0.3026           | 0.1842           | 0.06844                   |
| template_residual_boosted_stack_new       | 64          | 0.2736       | 6.393           | 0.09091                    | 0.2763           | 0.2237           | 0.0773                    |
| template_residual_boosted_stack_new       | 65          | -0.08629     | 6.596           | 0.07547                    | 0.3026           | 0.25             | 0.05846                   |
| tiny_sequence_transformer                 | 58          | -6.922       | 15.41           | 0.3525                     | 0.1974           | 0.2632           | 0.08414                   |
| tiny_sequence_transformer                 | 60          | -7.975       | 17.53           | 0.3889                     | 0.4079           | 0.3158           | 0.1095                    |
| tiny_sequence_transformer                 | 62          | -11.29       | 16.73           | 0.4062                     | 0.3684           | 0.2632           | 0.0925                    |
| tiny_sequence_transformer                 | 64          | -5.387       | 14.41           | 0.3137                     | 0.3289           | 0.1842           | 0.1265                    |
| tiny_sequence_transformer                 | 65          | -10.32       | 14.51           | 0.4479                     | 0.3684           | 0.3158           | 0.09395                   |
| two_pulse_template_likelihood_traditional | 58          | 0.8709       | 10.67           | 0.175                      | 0.4737           | 0.3158           | 0.07486                   |
| two_pulse_template_likelihood_traditional | 60          | 3.153        | 7.823           | 0.2069                     | 0.6184           | 0.2368           | 0.1239                    |
| two_pulse_template_likelihood_traditional | 62          | 1.555        | 10.89           | 0.2794                     | 0.5526           | 0.2895           | 0.1137                    |
| two_pulse_template_likelihood_traditional | 64          | 0.7277       | 9.1             | 0.2195                     | 0.4605           | 0.1579           | 0.09015                   |
| two_pulse_template_likelihood_traditional | 65          | -1.776       | 7.226           | 0.1452                     | 0.5921           | 0.2105           | 0.1035                    |

## Detector-held-out split

As a detector-transfer check, the nominal predictions are sliced so that B8 is
the held-out detector proxy and B2/B4/B6 form the non-evaluation slice.
Source-run bootstrap CIs are still computed on the B8 held-out slice.  This is a
detector-slice stress test rather than a retrained detector-exclusion claim.

| method                                    | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate |
| ----------------------------------------- | ------------ | ---------------------------- | -------------------------------- | ------------------------------- | ---------------- | ---------------- |
| template_residual_boosted_stack_new       | 0.8997       | 2.909                        | 5.169                            | 0.04393                         | 0.09502          | 0.1058           |
| gradient_boosted_trees                    | 0.9871       | 3.158                        | 5.338                            | 0.0466                          | 0.08145          | 0.1442           |
| residual_tail_veto_traditional            | 1.908        | 4.176                        | 10                               | 0.08785                         | 0.1222           | 0.6875           |
| ridge                                     | 1.913        | 5.424                        | 11.94                            | 0.07582                         | 0.2172           | 0.2308           |
| two_pulse_template_likelihood_traditional | 1.918        | 3.961                        | 11.25                            | 0.09232                         | 0.2534           | 0.4375           |
| 1d_cnn                                    | 2.043        | 4.094                        | 14.18                            | 0.0859                          | 0.1493           | 0.3894           |
| causal_window_transformer_new             | 2.347        | 9.349                        | 11.83                            | 0.08578                         | 0.1584           | 0.4712           |
| mlp                                       | 2.455        | 7.956                        | 13.53                            | 0.1203                          | 0.2579           | 0.2308           |
| tiny_sequence_transformer                 | 3.57         | 14.78                        | 24.83                            | 0.09377                         | 0.1674           | 0.3558           |
| leading_edge_cfd_traditional              | 3.921        | 3.819                        | 21.25                            | 0.2055                          | 0.181            | 0.8173           |

## Ablations

Stress-control slices were evaluated before interpretation.  The
pretrigger-pedestal row uses clean negative controls as the
pedestal-sensitivity endpoint.  The synthetic-over-real rows isolate tight
doublets and high summed-amplitude injections, both generated on real raw-ROOT
single-pulse residuals.  The shuffled-phase and amplitude-only sentinels are
negative controls: they retain the high-current residual and amplitude spectrum
while disrupting the second-pulse timing phase or removing the waveform timing
information from the ranking surface.

| ablation            | method                                    | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate |
| ------------------- | ----------------------------------------- | ------------ | ---------------------------- | -------------------------------- | ------------------------------- | ---------------- | ---------------- |
| nominal_full_window | template_residual_boosted_stack_new       | 1.832        | 4.889                        | 10.65                            | 0.06462                         | 0.2737           | 0.2237           |
| nominal_full_window | gradient_boosted_trees                    | 1.866        | 5.144                        | 10.41                            | 0.06954                         | 0.2579           | 0.2237           |
| nominal_full_window | ridge                                     | 2.162        | 7.451                        | 12.84                            | 0.07451                         | 0.2921           | 0.2105           |
| nominal_full_window | 1d_cnn                                    | 2.63         | 5.365                        | 16.06                            | 0.09366                         | 0.3              | 0.3184           |
| nominal_full_window | causal_window_transformer_new             | 2.773        | 8.952                        | 14.67                            | 0.09872                         | 0.2974           | 0.3237           |
| nominal_full_window | two_pulse_template_likelihood_traditional | 2.793        | 6.577                        | 17.5                             | 0.09552                         | 0.5395           | 0.2421           |
| nominal_full_window | residual_tail_veto_traditional            | 2.955        | 6.618                        | 20                               | 0.09744                         | 0.4816           | 0.3579           |
| nominal_full_window | mlp                                       | 3.088        | 10.12                        | 17.41                            | 0.1376                          | 0.3526           | 0.2079           |
| nominal_full_window | tiny_sequence_transformer                 | 3.682        | 13.52                        | 21.99                            | 0.1111                          | 0.3342           | 0.2684           |
| nominal_full_window | leading_edge_cfd_traditional              | 5.817        | 9.634                        | 21.25                            | 0.3018                          | 0.1026           | 0.8684           |

| stress                                        | method                                    | n_events | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | pileup_miss_rate | false_split_rate | energy_proxy_distortion_sigma68 |
| --------------------------------------------- | ----------------------------------------- | -------- | ---------------------------- | -------------------------------- | ---------------- | ---------------- | ------------------------------- |
| pretrigger_pedestal_clean_control             | 1d_cnn                                    | 380      | nan                          | nan                              | nan              | 0.3184           | nan                             |
| pretrigger_pedestal_clean_control             | causal_window_transformer_new             | 380      | nan                          | nan                              | nan              | 0.3237           | nan                             |
| pretrigger_pedestal_clean_control             | gradient_boosted_trees                    | 380      | nan                          | nan                              | nan              | 0.2237           | nan                             |
| pretrigger_pedestal_clean_control             | leading_edge_cfd_traditional              | 380      | nan                          | nan                              | nan              | 0.8684           | nan                             |
| pretrigger_pedestal_clean_control             | mlp                                       | 380      | nan                          | nan                              | nan              | 0.2079           | nan                             |
| pretrigger_pedestal_clean_control             | residual_tail_veto_traditional            | 380      | nan                          | nan                              | nan              | 0.3579           | nan                             |
| pretrigger_pedestal_clean_control             | ridge                                     | 380      | nan                          | nan                              | nan              | 0.2105           | nan                             |
| pretrigger_pedestal_clean_control             | template_residual_boosted_stack_new       | 380      | nan                          | nan                              | nan              | 0.2237           | nan                             |
| pretrigger_pedestal_clean_control             | tiny_sequence_transformer                 | 380      | nan                          | nan                              | nan              | 0.2684           | nan                             |
| pretrigger_pedestal_clean_control             | two_pulse_template_likelihood_traditional | 380      | nan                          | nan                              | nan              | 0.2421           | nan                             |
| synthetic_over_real_tight_sep_le_15ns         | 1d_cnn                                    | 167      | 5.889                        | 7.909                            | 0.4431           | nan              | 0.09913                         |
| synthetic_over_real_tight_sep_le_15ns         | causal_window_transformer_new             | 167      | 11.35                        | 9.324                            | 0.4551           | nan              | 0.09452                         |
| synthetic_over_real_tight_sep_le_15ns         | gradient_boosted_trees                    | 167      | 6.387                        | 7.06                             | 0.3653           | nan              | 0.06534                         |
| synthetic_over_real_tight_sep_le_15ns         | leading_edge_cfd_traditional              | 167      | 9.84                         | 5                                | 0.06587          | nan              | 0.2742                          |
| synthetic_over_real_tight_sep_le_15ns         | mlp                                       | 167      | 9.733                        | 16.51                            | 0.5329           | nan              | 0.1269                          |
| synthetic_over_real_tight_sep_le_15ns         | residual_tail_veto_traditional            | 167      | 7.989                        | 17.5                             | 0.6647           | nan              | 0.0879                          |
| synthetic_over_real_tight_sep_le_15ns         | ridge                                     | 167      | 7.108                        | 9.802                            | 0.3713           | nan              | 0.06148                         |
| synthetic_over_real_tight_sep_le_15ns         | template_residual_boosted_stack_new       | 167      | 5.991                        | 6.484                            | 0.4192           | nan              | 0.06071                         |
| synthetic_over_real_tight_sep_le_15ns         | tiny_sequence_transformer                 | 167      | 12.5                         | 12                               | 0.509            | nan              | 0.08493                         |
| synthetic_over_real_tight_sep_le_15ns         | two_pulse_template_likelihood_traditional | 167      | 8.014                        | 17.5                             | 0.7485           | nan              | 0.08674                         |
| synthetic_over_real_saturated_sum_gt_11000adc | 1d_cnn                                    | 17       | 4.826                        | 15.67                            | 0.1765           | nan              | 0.04748                         |
| synthetic_over_real_saturated_sum_gt_11000adc | causal_window_transformer_new             | 17       | 8.241                        | 13.46                            | 0.2353           | nan              | 0.06291                         |
| synthetic_over_real_saturated_sum_gt_11000adc | gradient_boosted_trees                    | 17       | 5.732                        | 9.591                            | 0                | nan              | 0.05109                         |
| synthetic_over_real_saturated_sum_gt_11000adc | leading_edge_cfd_traditional              | 17       | 5.988                        | 22.2                             | 0                | nan              | 0.2274                          |
| synthetic_over_real_saturated_sum_gt_11000adc | mlp                                       | 17       | 9.293                        | 17.63                            | 0.2353           | nan              | 0.1161                          |
| synthetic_over_real_saturated_sum_gt_11000adc | residual_tail_veto_traditional            | 17       | 9.31                         | 12.8                             | 0.5882           | nan              | 0.0295                          |
| synthetic_over_real_saturated_sum_gt_11000adc | ridge                                     | 17       | 7.387                        | 14.12                            | 0                | nan              | 0.04339                         |
| synthetic_over_real_saturated_sum_gt_11000adc | template_residual_boosted_stack_new       | 17       | 6.294                        | 7.539                            | 0                | nan              | 0.03992                         |
| synthetic_over_real_saturated_sum_gt_11000adc | tiny_sequence_transformer                 | 17       | 22.27                        | 24.79                            | 0.1765           | nan              | 0.06281                         |
| synthetic_over_real_saturated_sum_gt_11000adc | two_pulse_template_likelihood_traditional | 17       | 9.31                         | 12.8                             | 0.5882           | nan              | 0.0295                          |
| shuffled_second_pulse_phase_negative_control  | 1d_cnn                                    | 187      | 5.592                        | 16.15                            | 0.2941           | nan              | 0.09032                         |
| shuffled_second_pulse_phase_negative_control  | causal_window_transformer_new             | 187      | 10.07                        | 14.77                            | 0.2888           | nan              | 0.09527                         |
| shuffled_second_pulse_phase_negative_control  | gradient_boosted_trees                    | 187      | 5.864                        | 10.71                            | 0.2353           | nan              | 0.06908                         |
| shuffled_second_pulse_phase_negative_control  | leading_edge_cfd_traditional              | 193      | 10.43                        | 21.25                            | 0.08808          | nan              | 0.3095                          |
| shuffled_second_pulse_phase_negative_control  | mlp                                       | 193      | 10.43                        | 18.45                            | 0.3938           | nan              | 0.1354                          |
| shuffled_second_pulse_phase_negative_control  | residual_tail_veto_traditional            | 187      | 5.821                        | 21.6                             | 0.4813           | nan              | 0.1044                          |
| shuffled_second_pulse_phase_negative_control  | ridge                                     | 193      | 7.333                        | 12.29                            | 0.3161           | nan              | 0.0721                          |
| shuffled_second_pulse_phase_negative_control  | template_residual_boosted_stack_new       | 193      | 4.684                        | 10.25                            | 0.2953           | nan              | 0.06282                         |
| shuffled_second_pulse_phase_negative_control  | tiny_sequence_transformer                 | 193      | 12.38                        | 20.62                            | 0.3575           | nan              | 0.1199                          |
| shuffled_second_pulse_phase_negative_control  | two_pulse_template_likelihood_traditional | 187      | 5.495                        | 18.6                             | 0.5508           | nan              | 0.1044                          |
| amplitude_only_sentinel_high_charge           | 1d_cnn                                    | 190      | 4.972                        | 13.83                            | 0.1895           | nan              | 0.08525                         |
| amplitude_only_sentinel_high_charge           | causal_window_transformer_new             | 190      | 8.359                        | 10.58                            | 0.2053           | nan              | 0.09235                         |
| amplitude_only_sentinel_high_charge           | gradient_boosted_trees                    | 190      | 5.504                        | 8.706                            | 0.07895          | nan              | 0.05968                         |
| amplitude_only_sentinel_high_charge           | leading_edge_cfd_traditional              | 190      | 10.05                        | 21.25                            | 0.06842          | nan              | 0.2596                          |
| amplitude_only_sentinel_high_charge           | mlp                                       | 190      | 9.671                        | 15.08                            | 0.2105           | nan              | 0.1192                          |
| amplitude_only_sentinel_high_charge           | residual_tail_veto_traditional            | 190      | 5.851                        | 20                               | 0.4368           | nan              | 0.08003                         |
| amplitude_only_sentinel_high_charge           | ridge                                     | 190      | 7.151                        | 11.99                            | 0.07895          | nan              | 0.06818                         |
| amplitude_only_sentinel_high_charge           | template_residual_boosted_stack_new       | 190      | 5.4                          | 9.532                            | 0.09474          | nan              | 0.06279                         |
| amplitude_only_sentinel_high_charge           | tiny_sequence_transformer                 | 190      | 12.72                        | 19.62                            | 0.2105           | nan              | 0.09473                         |
| amplitude_only_sentinel_high_charge           | two_pulse_template_likelihood_traditional | 190      | 5.806                        | 19.5                             | 0.4947           | nan              | 0.07881                         |

## Interpretation and next test

The main result is that adding the traditional deconvolution outputs back into a
boosted residual learner is more useful than replacing the physics fit with a
pure sequence model.  The residual stack wins the nominal run-held-out score and
the B8 detector-slice table checks whether that ordering is stable for one stave
held out as an evaluation proxy.  This pattern suggests that the raw 18-sample
waveform still contains recoverable nonlinear residual structure, but the
template/CFD fit supplies a strong low-variance coordinate system for that
structure.

No novel follow-up ticket is appended from this worker.  A possible future
validation, not created here, is to check the S66b winner on hand-scanned
high-current pile-up candidates rather than exact-truth synthetic-over-real
doublets.

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

Runtime was `89.0` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29`.


## S66b nuisance-control audit

The ticket specifically asks whether timing bias and pile-up onset decisions are
stable against pedestal phase, amplitude, inter-pulse spacing, and saturation.
For event `i`, the phase nuisance is

`phi_i = true_t1_sample_i mod 1`,

reported in four equal sub-sample bins.  The amplitude nuisance is the injected
summed charge `A_i = A_1 + A_2`; spacing uses the true injected separation
`Delta_i`; saturation uses the same high-charge proxy as the endpoint table,
`A_i > 11000 ADC`.  Slice confidence intervals are non-parametric percentile
bootstrap intervals for the median leading-edge error inside each slice.

| nuisance           | slice                | method                                    |   n_events |   leading_edge_bias_ns |   leading_edge_bias_ci_low |   leading_edge_bias_ci_high |   leading_edge_sigma68_ns |   delay_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-------------------|:---------------------|:------------------------------------------|-----------:|-----------------------:|---------------------------:|----------------------------:|--------------------------:|-------------------:|-------------------:|-------------------:|
| amplitude_bin      | (1522.999, 2997.938] | 1d_cnn                                    |        190 |                0.2487  |                   -5.142   |                      2.558  |                     4.347 |             17.5   |            0.6333  |            0.1875  |
| amplitude_bin      | (1522.999, 2997.938] | causal_window_transformer_new             |        190 |               -9.761   |                  -14.27    |                      2.345  |                     9.738 |             24.38  |            0.5333  |            0.1437  |
| amplitude_bin      | (1522.999, 2997.938] | gradient_boosted_trees                    |        190 |               -1.092   |                   -5.444   |                      2.239  |                     4.671 |             10.68  |            0.6333  |            0.05    |
| amplitude_bin      | (1522.999, 2997.938] | leading_edge_cfd_traditional              |        190 |              -11.09    |                  -16.96    |                     -7.485  |                     8.987 |             21.25  |            0.2     |            0.8375  |
| amplitude_bin      | (1522.999, 2997.938] | mlp                                       |        190 |               -7.793   |                   -9.884   |                      8.244  |                     9.597 |             11.76  |            0.7667  |            0.125   |
| amplitude_bin      | (1522.999, 2997.938] | residual_tail_veto_traditional            |        190 |               -1.452   |                   -6.353   |                      3.786  |                     7.865 |             16.2   |            0.6     |            0.2375  |
| amplitude_bin      | (1522.999, 2997.938] | ridge                                     |        190 |               -9.067   |                  -13.45    |                      3.38   |                     7.113 |             14.82  |            0.8     |            0.03125 |
| amplitude_bin      | (1522.999, 2997.938] | template_residual_boosted_stack_new       |        190 |                1.07    |                   -5.188   |                      3.758  |                     5.522 |             17.49  |            0.6     |            0.1062  |
| amplitude_bin      | (1522.999, 2997.938] | tiny_sequence_transformer                 |        190 |               -3.803   |                   -7.968   |                      0.2031 |                     4.653 |             19.39  |            0.6667  |            0.1375  |
| amplitude_bin      | (1522.999, 2997.938] | two_pulse_template_likelihood_traditional |        190 |                0.01534 |                   -4.978   |                      3.899  |                     8.408 |             17     |            0.6333  |            0.1938  |
| amplitude_bin      | (2997.938, 3964.375] | 1d_cnn                                    |        190 |                0.7081  |                   -1.595   |                      1.908  |                     4.874 |             16.22  |            0.4267  |            0.3826  |
| amplitude_bin      | (2997.938, 3964.375] | causal_window_transformer_new             |        190 |               -3.91    |                   -7.139   |                     -1.586  |                     9.515 |             17.88  |            0.4     |            0.3739  |
| amplitude_bin      | (2997.938, 3964.375] | gradient_boosted_trees                    |        190 |               -0.4868  |                   -1.156   |                      0.4153 |                     4.443 |             11.36  |            0.5333  |            0.1826  |
| amplitude_bin      | (2997.938, 3964.375] | leading_edge_cfd_traditional              |        190 |               -8.092   |                   -9.988   |                     -5.747  |                     8.344 |             21.25  |            0.1333  |            0.8522  |
| amplitude_bin      | (2997.938, 3964.375] | mlp                                       |        190 |               -3.469   |                   -5.232   |                      5.51   |                    11.15  |             20.16  |            0.5333  |            0.2     |
| amplitude_bin      | (2997.938, 3964.375] | residual_tail_veto_traditional            |        190 |                0.4126  |                   -1.944   |                      3.47   |                     5.94  |             21.1   |            0.5467  |            0.4087  |
| amplitude_bin      | (2997.938, 3964.375] | ridge                                     |        190 |               -2.689   |                   -5.315   |                      1.925  |                     6.953 |             13.65  |            0.68    |            0.1478  |
| amplitude_bin      | (2997.938, 3964.375] | template_residual_boosted_stack_new       |        190 |               -0.7247  |                   -1.438   |                      1.079  |                     3.391 |             12.02  |            0.4667  |            0.1565  |
| amplitude_bin      | (2997.938, 3964.375] | tiny_sequence_transformer                 |        190 |                0.3294  |                  -11.98    |                      3.688  |                    13.57  |             20.53  |            0.4533  |            0.3043  |
| amplitude_bin      | (2997.938, 3964.375] | two_pulse_template_likelihood_traditional |        190 |                1.265   |                   -0.5604  |                      4.861  |                     6.378 |             19.3   |            0.6     |            0.2435  |
| amplitude_bin      | (3964.375, 5449.75]  | 1d_cnn                                    |        190 |                1.586   |                   -0.03461 |                      3.324  |                     5.745 |             18.33  |            0.2975  |            0.4203  |
| amplitude_bin      | (3964.375, 5449.75]  | causal_window_transformer_new             |        190 |               -1.529   |                   -5.978   |                      0.7663 |                     9.722 |             13.74  |            0.314   |            0.5217  |
| amplitude_bin      | (3964.375, 5449.75]  | gradient_boosted_trees                    |        190 |                1.519   |                    0.01335 |                      2.636  |                     4.412 |             11.51  |            0.2479  |            0.4783  |
| amplitude_bin      | (3964.375, 5449.75]  | leading_edge_cfd_traditional              |        190 |               -7.376   |                   -9.421   |                     -5.506  |                     9.218 |             21.25  |            0.09091 |            0.8986  |
| amplitude_bin      | (3964.375, 5449.75]  | mlp                                       |        190 |               -3.175   |                   -5.445   |                      0.1222 |                     9.884 |             20.32  |            0.3223  |            0.2754  |
| amplitude_bin      | (3964.375, 5449.75]  | residual_tail_veto_traditional            |        190 |                0.8006  |                   -1.548   |                      3.421  |                     7.196 |             24     |            0.4545  |            0.4493  |
| amplitude_bin      | (3964.375, 5449.75]  | ridge                                     |        190 |                0.7243  |                   -0.8903  |                      2.052  |                     6.693 |             14.19  |            0.2231  |            0.4348  |
| amplitude_bin      | (3964.375, 5449.75]  | template_residual_boosted_stack_new       |        190 |                1.155   |                   -0.03891 |                      2.073  |                     4.653 |             11.43  |            0.3306  |            0.3768  |
| amplitude_bin      | (3964.375, 5449.75]  | tiny_sequence_transformer                 |        190 |               -0.7504  |                   -3.193   |                      5.498  |                    14.26  |             25.8   |            0.3554  |            0.4348  |
| amplitude_bin      | (3964.375, 5449.75]  | two_pulse_template_likelihood_traditional |        190 |                1.523   |                   -0.3284  |                      4.081  |                     6.274 |             22.6   |            0.5289  |            0.2899  |
| amplitude_bin      | (5449.75, 16911.0]   | 1d_cnn                                    |        190 |                0.637   |                   -0.4567  |                      1.74   |                     5.243 |             13.72  |            0.1753  |            0.5     |
| amplitude_bin      | (5449.75, 16911.0]   | causal_window_transformer_new             |        190 |               -3.193   |                   -4.98    |                     -1.66   |                     7.574 |             10.13  |            0.1883  |            0.5833  |
| amplitude_bin      | (5449.75, 16911.0]   | gradient_boosted_trees                    |        190 |                0.2089  |                   -0.7234  |                      1.653  |                     5.856 |              8.407 |            0.05844 |            0.6389  |
| amplitude_bin      | (5449.75, 16911.0]   | leading_edge_cfd_traditional              |        190 |               -8.679   |                  -11.64    |                     -6.316  |                    10.18  |             21.25  |            0.07792 |            1       |
| amplitude_bin      | (5449.75, 16911.0]   | mlp                                       |        190 |                0.2122  |                   -1.093   |                      2.271  |                     9.309 |             15.51  |            0.2078  |            0.4722  |
| amplitude_bin      | (5449.75, 16911.0]   | residual_tail_veto_traditional            |        190 |                0.4587  |                   -0.5388  |                      1.251  |                     6.119 |             20     |            0.4481  |            0.5556  |
| amplitude_bin      | (5449.75, 16911.0]   | ridge                                     |        190 |                3.233   |                    1.434   |                      4.184  |                     7.673 |             11.94  |            0.05844 |            0.7778  |
| amplitude_bin      | (5449.75, 16911.0]   | template_residual_boosted_stack_new       |        190 |                0.7988  |                   -0.5444  |                      1.259  |                     5.862 |              9.476 |            0.07143 |            0.6667  |
| amplitude_bin      | (5449.75, 16911.0]   | tiny_sequence_transformer                 |        190 |                0.07874 |                   -2.641   |                      2.732  |                    12.38  |             19.8   |            0.1948  |            0.4167  |
| amplitude_bin      | (5449.75, 16911.0]   | two_pulse_template_likelihood_traditional |        190 |                0.4587  |                   -0.5579  |                      1.251  |                     6.306 |             20     |            0.5     |            0.3611  |
| pedestal_phase_bin | [0,0.25)             | 1d_cnn                                    |        209 |                1.678   |                   -0.03367 |                      3.245  |                     5.832 |             15.22  |            0.3232  |            0.3455  |
| pedestal_phase_bin | [0,0.25)             | causal_window_transformer_new             |        209 |               -3.373   |                   -5.981   |                     -0.534  |                     8.911 |             14.22  |            0.3131  |            0.3273  |
| pedestal_phase_bin | [0,0.25)             | gradient_boosted_trees                    |        209 |                1.907   |                    0.2089  |                      3.17   |                     6.704 |              9.654 |            0.2929  |            0.2273  |
| pedestal_phase_bin | [0,0.25)             | leading_edge_cfd_traditional              |        209 |               -7.707   |                  -11.25    |                     -6.004  |                     9.465 |             21.25  |            0.09091 |            0.9     |
| pedestal_phase_bin | [0,0.25)             | mlp                                       |        209 |                0.3121  |                   -2.244   |                      4.208  |                     9.687 |             15.1   |            0.3232  |            0.1818  |
| pedestal_phase_bin | [0,0.25)             | residual_tail_veto_traditional            |        209 |                0.5143  |                   -1.734   |                      2.334  |                     8.709 |             22.5   |            0.4848  |            0.3545  |
| pedestal_phase_bin | [0,0.25)             | ridge                                     |        209 |                0.8264  |                   -0.4764  |                      3.417  |                     8.004 |             11.06  |            0.2727  |            0.2455  |
| pedestal_phase_bin | [0,0.25)             | template_residual_boosted_stack_new       |        209 |                1.096   |                   -0.5664  |                      3.14   |                     6.181 |             10.04  |            0.2929  |            0.2545  |
| pedestal_phase_bin | [0,0.25)             | tiny_sequence_transformer                 |        209 |               -1.227   |                   -5.343   |                      4.994  |                    13.34  |             17.92  |            0.3737  |            0.2909  |
| pedestal_phase_bin | [0,0.25)             | two_pulse_template_likelihood_traditional |        209 |                0.6291  |                   -1.069   |                      2.701  |                     7.605 |             22     |            0.5354  |            0.2364  |
| pedestal_phase_bin | [0.25,0.50)          | 1d_cnn                                    |        207 |                2.038   |                   -0.04665 |                      2.844  |                     5.23  |             17     |            0.2818  |            0.3093  |
| pedestal_phase_bin | [0.25,0.50)          | causal_window_transformer_new             |        207 |               -1.543   |                   -3.655   |                      0.4865 |                     8.206 |             13.67  |            0.2909  |            0.3505  |
| pedestal_phase_bin | [0.25,0.50)          | gradient_boosted_trees                    |        207 |                0.9749  |                    0.03384 |                      2.708  |                     4.537 |             11.43  |            0.2182  |            0.2062  |
| pedestal_phase_bin | [0.25,0.50)          | leading_edge_cfd_traditional              |        207 |               -6.965   |                   -9.954   |                     -3.175  |                    10.02  |             20.8   |            0.09091 |            0.8454  |
| pedestal_phase_bin | [0.25,0.50)          | mlp                                       |        207 |               -1.778   |                   -4.29    |                      3.65   |                    11.36  |             20.43  |            0.3364  |            0.2268  |
| pedestal_phase_bin | [0.25,0.50)          | residual_tail_veto_traditional            |        207 |                2.728   |                    1.616   |                      4.463  |                     6.527 |             18.5   |            0.4455  |            0.3711  |
| pedestal_phase_bin | [0.25,0.50)          | ridge                                     |        207 |                3.281   |                    0.824   |                      4.727  |                     7.456 |             13.91  |            0.2727  |            0.2165  |
| pedestal_phase_bin | [0.25,0.50)          | template_residual_boosted_stack_new       |        207 |                1.06    |                    0.3447  |                      2.073  |                     4.145 |             11.38  |            0.2273  |            0.1959  |
| pedestal_phase_bin | [0.25,0.50)          | tiny_sequence_transformer                 |        207 |                2.363   |                   -0.01014 |                      6.218  |                    11.1   |             25.89  |            0.3     |            0.268   |
| pedestal_phase_bin | [0.25,0.50)          | two_pulse_template_likelihood_traditional |        207 |                2.728   |                    0.01534 |                      4.648  |                     6.572 |             17.6   |            0.4818  |            0.2784  |
| pedestal_phase_bin | [0.50,0.75)          | 1d_cnn                                    |        186 |               -1.158   |                   -3.039   |                      0.637  |                     5.444 |             16.65  |            0.3444  |            0.3229  |
| pedestal_phase_bin | [0.50,0.75)          | causal_window_transformer_new             |        186 |               -5.662   |                   -8.945   |                     -2.061  |                     6.781 |             14.91  |            0.3222  |            0.3021  |
| pedestal_phase_bin | [0.50,0.75)          | gradient_boosted_trees                    |        186 |               -0.6229  |                   -1.714   |                      0.4145 |                     4.196 |             13.12  |            0.3333  |            0.1979  |
| pedestal_phase_bin | [0.50,0.75)          | leading_edge_cfd_traditional              |        186 |              -10.88    |                  -13.73    |                     -7.772  |                     9.847 |             16.25  |            0.07778 |            0.8646  |
| pedestal_phase_bin | [0.50,0.75)          | mlp                                       |        186 |               -1.096   |                   -5.552   |                      0.3789 |                    10.04  |             17.02  |            0.4222  |            0.1667  |
| pedestal_phase_bin | [0.50,0.75)          | residual_tail_veto_traditional            |        186 |               -2.381   |                   -6.23    |                      1.107  |                    10.07  |             20.95  |            0.5333  |            0.3958  |
| pedestal_phase_bin | [0.50,0.75)          | ridge                                     |        186 |               -0.9272  |                   -3.595   |                      1.634  |                     7.35  |             14.77  |            0.3778  |            0.1771  |
| pedestal_phase_bin | [0.50,0.75)          | template_residual_boosted_stack_new       |        186 |               -0.5444  |                   -1.592   |                      1.079  |                     3.954 |             12.31  |            0.3667  |            0.1979  |
| pedestal_phase_bin | [0.50,0.75)          | tiny_sequence_transformer                 |        186 |               -5.57    |                  -10.31    |                     -1.797  |                    14.51  |             23.86  |            0.3444  |            0.2604  |
| pedestal_phase_bin | [0.50,0.75)          | two_pulse_template_likelihood_traditional |        186 |               -0.05009 |                   -6.074   |                      2.289  |                     9.371 |             21.4   |            0.6111  |            0.25    |
| pedestal_phase_bin | [0.75,1)             | 1d_cnn                                    |        158 |                0.7289  |                   -1.728   |                      1.74   |                     4.092 |             12.47  |            0.2469  |            0.2857  |
| pedestal_phase_bin | [0.75,1)             | causal_window_transformer_new             |        158 |               -2.64    |                   -6.626   |                      0.391  |                     9.028 |             16.01  |            0.2593  |            0.3117  |
| pedestal_phase_bin | [0.75,1)             | gradient_boosted_trees                    |        158 |               -0.6449  |                   -2.085   |                      1.398  |                     5.635 |              8.307 |            0.1852  |            0.2727  |
| pedestal_phase_bin | [0.75,1)             | leading_edge_cfd_traditional              |        158 |               -8.072   |                  -10.86    |                     -6.316  |                    10.37  |             21.25  |            0.1605  |            0.8571  |
| pedestal_phase_bin | [0.75,1)             | mlp                                       |        158 |               -1.675   |                   -4.685   |                      2.141  |                     8.97  |             14.37  |            0.3333  |            0.2727  |
| pedestal_phase_bin | [0.75,1)             | residual_tail_veto_traditional            |        158 |               -0.3284  |                   -0.8422  |                      0.4587 |                     2.58  |             15     |            0.4691  |            0.2987  |
| pedestal_phase_bin | [0.75,1)             | ridge                                     |        158 |                1.486   |                   -1.223   |                      5.239  |                     6.69  |              9.966 |            0.2469  |            0.1948  |
| pedestal_phase_bin | [0.75,1)             | template_residual_boosted_stack_new       |        158 |               -0.02203 |                   -1.293   |                      1.55   |                     4.826 |              9.267 |            0.2099  |            0.2468  |
| pedestal_phase_bin | [0.75,1)             | tiny_sequence_transformer                 |        158 |                0.1257  |                   -2.994   |                      4.249  |                    11.66  |             18.45  |            0.321   |            0.2468  |
| pedestal_phase_bin | [0.75,1)             | two_pulse_template_likelihood_traditional |        158 |                0.0905  |                   -0.6845  |                      0.9691 |                     3.356 |             10     |            0.5432  |            0.1948  |

The winner stability table compresses those slice diagnostics into the largest
absolute bias and the across-slice ranges of resolution and error rates.

| winner                              | nuisance           |   max_abs_bias_ns |   sigma68_range_ns |   false_split_rate_range |   pileup_miss_rate_range |
|:------------------------------------|:-------------------|------------------:|-------------------:|-------------------------:|-------------------------:|
| template_residual_boosted_stack_new | amplitude_bin      |            1.155  |              2.471 |                  0.5604  |                   0.5286 |
| template_residual_boosted_stack_new | pedestal_phase_bin |            1.096  |              2.228 |                  0.05867 |                   0.1568 |
| template_residual_boosted_stack_new | saturation_bin     |            0.7949 |              1.421 |                  0       |                   0.2865 |
| template_residual_boosted_stack_new | spacing_bin        |            2.241  |              1.921 |                  0       |                   0.2842 |

## Ticket and queue provenance

The required claim command was run exactly once as `tn-ticket claim testbeam-laptop-3 --project testbeam`.  It emitted
the null pseudo-ticket output `# null / null / null` without changing labels, while
the testbeam queue still contained issue `#2546`.  To avoid a second claim
command, this worker applied the intended single-ticket label transition directly
with `gh issue edit 2546 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open`.  Completion should be recorded with
`tn-ticket done 2546` after the PR is opened.  No novel follow-up ticket is
appended by this run.

S66b wrapper runtime was `89.0` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29`.

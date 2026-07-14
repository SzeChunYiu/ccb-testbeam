# S37b: residual-stack deconvolution on high-current pile-up candidates

## Abstract

Ticket `1784068324.1054.23ed295f` asks whether the S37a/S36 residual-stack deconvolution remains
superior on a frozen real pile-up candidate surface rather than only on generic
synthetic-over-real doublets.  The worker was `testbeam-laptop-2` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT.  It then trained on low-current raw-residual overlays and evaluated
only on high-current source runs previously used by blinded hand-scan candidate
studies.  A strong traditional two-pulse template/optimal-filter baseline is
compared against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence
transformer, a temporal convolutional network, a new pile-up-mask transformer,
and a hybrid residual stack.  The winner written to `result.json` is `template_residual_boosted_stack_new`
with composite endpoint score
`2.665`.

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

## Frozen Candidate Surface

The repository contains blinded/reviewer high-current candidate ledgers, but no
event-level hand-scan table with constituent hit times and amplitudes that can be
joined to all raw HRD windows.  S37b therefore uses those ledgers to freeze the
evaluation surface to the same high-current run family and keeps exact
constituent truth by overlaying controlled second pulses on raw high-current
residuals.  This is a robustness test against real beam-current morphology and
label uncertainty, not a claim that the hand-scan labels provide exact timing
truth.

| item                           | value                                                                                                             | n      | notes                                                                                                             |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------- |
| training_current_surface       | low_2nA                                                                                                           | 264    | runs [46, 47]; labels are controlled overlays for supervised fitting                                              |
| frozen_candidate_surface       | high_20nA                                                                                                         | 1056   | runs [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]; high-current candidate-like held-out evaluation            |
| heldout_overlap_proxy_positive | controlled_overlap_on_high_current_residual                                                                       | 528    | proxy positives preserve exact timing/energy truth while using high-current raw residual morphology               |
| heldout_clean_proxy_negative   | single_pulse_high_current_control                                                                                 | 528    | false-split denominator on high-current raw residual morphology                                                   |
| handscan_provenance_file       | reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/blinded_gallery_adjudication.csv | 271029 | existing blinded/reviewer candidate ledger; used to freeze high-current surface, not as an event-level truth join |
| handscan_provenance_file       | reports/1781191650.1263.35bb131f__p05g_blinded_handscan_validation/blinded_candidate_ledger.csv                   | 285565 | existing blinded/reviewer candidate ledger; used to freeze high-current surface, not as an event-level truth join |
| handscan_provenance_file       | reports/1783605034.12126.04fe4a38__s01j_external_handscan_transfer/handscan_feature_table.csv                     | 172459 | existing blinded/reviewer candidate ledger; used to freeze high-current surface, not as an event-level truth join |

## Split, injections, and bootstrap

The train/held-out split is by source run.  Train runs are
`[46, 47]` and held-out runs are
`[44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]`.  Clean templates are estimated only from
train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| ----- | -------------- | --------------------- | -------------------- | ------------- |
| B2    | 176            | 2.556                 | 5                    | 9.419         |
| B4    | 63             | 1.964                 | 5                    | 9.704         |
| B6    | 32             | 3.41                  | 6                    | 8.624         |
| B8    | 17             | 4.159                 | 8                    | 7.864         |

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
| two_pulse_template_cfd_baseline     | 0.6102       | 0.5608        | 2.139        | 8.657           | 7.274                  | 10.72                   | 0.661            | 0.2481           | 0.1239                    |
| template_residual_boosted_stack_new | 0.8029       | 0.7921        | 0.8027       | 8.894           | 8.174                  | 9.68                    | 0.197            | 0.4091           | 0.115                     |
| gradient_boosted_trees              | 0.7897       | 0.784         | 1.102        | 9.353           | 8.719                  | 10.03                   | 0.1761           | 0.4148           | 0.1162                    |
| ridge                               | 0.803        | 0.8098        | 2.253        | 10.44           | 9.667                  | 11.4                    | 0.1818           | 0.3523           | 0.1021                    |
| mlp                                 | 0.7055       | 0.7173        | -2.223       | 14.1            | 13.06                  | 15.27                   | 0.3239           | 0.3504           | 0.216                     |
| 1d_cnn                              | 0.6375       | 0.6678        | -0.5326      | 15.34           | 14.71                  | 15.89                   | 0.1572           | 0.5795           | 0.2097                    |
| pileup_mask_transformer_new         | 0.6506       | 0.689         | -11.28       | 20.16           | 18.85                  | 21.63                   | 0.2633           | 0.4678           | 0.1855                    |
| temporal_convolution_tcn            | 0.6189       | 0.6735        | -13.39       | 21.21           | 20.04                  | 21.92                   | 0.1477           | 0.6023           | 0.1858                    |
| tiny_sequence_transformer           | 0.6754       | 0.6874        | -11.37       | 23.05           | 22.34                  | 23.58                   | 0.2973           | 0.4451           | 0.1849                    |

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
| two_pulse_template_cfd_baseline     | 5.513                        | 4.304                               | 6.303                                | 15                               | 12                                      | 20                                       | 0.7608                      | 0.03404                               | 0.2481                          | 0.1239                          | 0.1504                        |
| template_residual_boosted_stack_new | 8.847                        | 8.29                                | 9.416                                | 13.79                            | 12.78                                   | 14.66                                    | 0.7985                      | 0.1321                                | 0.4091                          | 0.115                           | 0.0822                        |
| gradient_boosted_trees              | 9.404                        | 8.619                               | 9.883                                | 13.74                            | 12.95                                   | 14.63                                    | 0.8378                      | 0.1216                                | 0.4148                          | 0.1162                          | 0.07487                       |
| ridge                               | 9.932                        | 8.696                               | 10.62                                | 14.99                            | 13.56                                   | 16.1                                     | 0.8245                      | 0.06746                               | 0.3523                          | 0.1021                          | 0.07695                       |
| 1d_cnn                              | 12.24                        | 11.36                               | 13.57                                | 21.84                            | 20.92                                   | 22.19                                    | 1.205                       | 0.1226                                | 0.5795                          | 0.2097                          | 0.2244                        |
| mlp                                 | 12.79                        | 11.61                               | 14.76                                | 18.86                            | 16.93                                   | 20.79                                    | 1.301                       | 0.186                                 | 0.3504                          | 0.216                           | 0.1449                        |
| pileup_mask_transformer_new         | 13.33                        | 12.24                               | 14.53                                | 23.25                            | 22.54                                   | 23.67                                    | 1.91                        | 0.1275                                | 0.4678                          | 0.1855                          | 0.1667                        |
| tiny_sequence_transformer           | 14                           | 12.16                               | 15.69                                | 23.71                            | 22.52                                   | 23.96                                    | 2.035                       | 0.1269                                | 0.4451                          | 0.1849                          | 0.1292                        |
| temporal_convolution_tcn            | 17.96                        | 16.39                               | 18.94                                | 24.9                             | 23.29                                   | 25.42                                    | 1.853                       | 0.1097                                | 0.6023                          | 0.1858                          | 0.1383                        |

## Winner rule

The winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow timing
only by rejecting overlaps, splitting clean pulses, distorting energy, or moving
stave/PID boundaries.

| method                              | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| template_residual_boosted_stack_new | 2.665        | 8.847                        | 13.79                            | 0.7985                      | 0.115                           | 0.197            | 0.4091           | 0.0822                        |
| ridge                               | 2.702        | 9.932                        | 14.99                            | 0.8245                      | 0.1021                          | 0.1818           | 0.3523           | 0.07695                       |
| gradient_boosted_trees              | 2.71         | 9.404                        | 13.74                            | 0.8378                      | 0.1162                          | 0.1761           | 0.4148           | 0.07487                       |
| two_pulse_template_cfd_baseline     | 2.854        | 5.513                        | 15                               | 0.7608                      | 0.1239                          | 0.661            | 0.2481           | 0.1504                        |
| mlp                                 | 4.037        | 12.79                        | 18.86                            | 1.301                       | 0.216                           | 0.3239           | 0.3504           | 0.1449                        |
| 1d_cnn                              | 4.21         | 12.24                        | 21.84                            | 1.205                       | 0.2097                          | 0.1572           | 0.5795           | 0.2244                        |
| pileup_mask_transformer_new         | 4.836        | 13.33                        | 23.25                            | 1.91                        | 0.1855                          | 0.2633           | 0.4678           | 0.1667                        |
| tiny_sequence_transformer           | 4.942        | 14                           | 23.71                            | 2.035                       | 0.1849                          | 0.2973           | 0.4451           | 0.1292                        |
| temporal_convolution_tcn            | 5.031        | 17.96                        | 24.9                             | 1.853                       | 0.1858                          | 0.1477           | 0.6023           | 0.1383                        |

The traditional baseline has score `2.854` and leading-edge
sigma68 `5.513` ns.  The selected winner
`template_residual_boosted_stack_new` has score `2.665` and leading-edge sigma68
`8.847` ns.

## Run-held-out stability

| method                              | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                              | 44          | -1.285       | 14.52           | 0.3158                     | 0.1364           | 0.6136           | 0.2688                    |
| 1d_cnn                              | 45          | 1.206        | 14.41           | 0.3108                     | 0.1591           | 0.5455           | 0.1671                    |
| 1d_cnn                              | 48          | -0.03581     | 16.45           | 0.2941                     | 0.2273           | 0.4545           | 0.268                     |
| 1d_cnn                              | 49          | -1.926       | 14.8            | 0.3125                     | 0.09091          | 0.6818           | 0.182                     |
| 1d_cnn                              | 50          | 2.56         | 14.67           | 0.3286                     | 0.2045           | 0.6818           | 0.1529                    |
| 1d_cnn                              | 51          | 2.601        | 14.56           | 0.2805                     | 0.06818          | 0.5682           | 0.2387                    |
| 1d_cnn                              | 52          | -0.09597     | 13.24           | 0.2692                     | 0.1136           | 0.5682           | 0.1472                    |
| 1d_cnn                              | 53          | 0.6664       | 16.37           | 0.3718                     | 0.1136           | 0.6136           | 0.1312                    |
| 1d_cnn                              | 54          | -2.354       | 16.03           | 0.4444                     | 0.1818           | 0.4318           | 0.2452                    |
| 1d_cnn                              | 55          | -2.431       | 15.18           | 0.3333                     | 0.25             | 0.6136           | 0.1677                    |
| 1d_cnn                              | 56          | 0.887        | 12.69           | 0.25                       | 0.1364           | 0.6364           | 0.2555                    |
| 1d_cnn                              | 57          | -3.861       | 15.21           | 0.3143                     | 0.2045           | 0.5455           | 0.2561                    |
| gradient_boosted_trees              | 44          | -0.4054      | 7.965           | 0.1389                     | 0.1818           | 0.3864           | 0.1177                    |
| gradient_boosted_trees              | 45          | 1.954        | 6.967           | 0.1286                     | 0.2045           | 0.4091           | 0.07729                   |
| gradient_boosted_trees              | 48          | 2.92         | 9.246           | 0.1471                     | 0.2273           | 0.3409           | 0.1312                    |
| gradient_boosted_trees              | 49          | 1.077        | 8.226           | 0.1351                     | 0.1591           | 0.4091           | 0.09926                   |
| gradient_boosted_trees              | 50          | -1.009       | 8.823           | 0.1081                     | 0.1591           | 0.5227           | 0.09888                   |
| gradient_boosted_trees              | 51          | 3.12         | 9.058           | 0.1538                     | 0.1136           | 0.3636           | 0.1101                    |
| gradient_boosted_trees              | 52          | 1.576        | 9.121           | 0.1528                     | 0.1818           | 0.3864           | 0.1043                    |
| gradient_boosted_trees              | 53          | 0.6151       | 10.64           | 0.175                      | 0.09091          | 0.4318           | 0.11                      |
| gradient_boosted_trees              | 54          | 0.8045       | 8.618           | 0.1447                     | 0.1364           | 0.3636           | 0.1212                    |
| gradient_boosted_trees              | 55          | 0.8005       | 9.657           | 0.1806                     | 0.1818           | 0.5227           | 0.1041                    |
| gradient_boosted_trees              | 56          | 1.528        | 9.736           | 0.1389                     | 0.1818           | 0.4773           | 0.1372                    |
| gradient_boosted_trees              | 57          | 1.242        | 12.62           | 0.2258                     | 0.2955           | 0.3636           | 0.1277                    |
| mlp                                 | 44          | -2.914       | 16.15           | 0.4                        | 0.3182           | 0.3636           | 0.24                      |
| mlp                                 | 45          | -2.301       | 10.2            | 0.2069                     | 0.3409           | 0.3182           | 0.1633                    |
| mlp                                 | 48          | -4.397       | 14.94           | 0.36                       | 0.4318           | 0.3864           | 0.1573                    |
| mlp                                 | 49          | -2.31        | 13.24           | 0.2344                     | 0.2727           | 0.3409           | 0.1761                    |
| mlp                                 | 50          | -1.341       | 12.66           | 0.2414                     | 0.3409           | 0.3636           | 0.2344                    |
| mlp                                 | 51          | 1.501        | 13.45           | 0.3143                     | 0.2045           | 0.3864           | 0.2638                    |
| mlp                                 | 52          | -3.509       | 13.56           | 0.2879                     | 0.25             | 0.3636           | 0.2547                    |
| mlp                                 | 53          | -1.272       | 14.2            | 0.303                      | 0.25             | 0.2727           | 0.1852                    |
| mlp                                 | 54          | -5.781       | 15.63           | 0.3966                     | 0.3409           | 0.2727           | 0.2046                    |
| mlp                                 | 55          | -1.934       | 11.33           | 0.2115                     | 0.4091           | 0.4091           | 0.2124                    |
| mlp                                 | 56          | 2.286        | 16.74           | 0.3281                     | 0.2727           | 0.3864           | 0.1553                    |
| mlp                                 | 57          | -3.977       | 15.4            | 0.375                      | 0.4545           | 0.3409           | 0.2019                    |
| pileup_mask_transformer_new         | 44          | -16.44       | 19.86           | 0.5806                     | 0.2955           | 0.5455           | 0.16                      |
| pileup_mask_transformer_new         | 45          | -10.97       | 16.66           | 0.4429                     | 0.2045           | 0.5682           | 0.1364                    |
| pileup_mask_transformer_new         | 48          | -10.83       | 21.81           | 0.45                       | 0.3182           | 0.3864           | 0.1763                    |
| pileup_mask_transformer_new         | 49          | -9.853       | 17.97           | 0.4722                     | 0.1818           | 0.4773           | 0.1325                    |
| pileup_mask_transformer_new         | 50          | -11.38       | 20.14           | 0.4667                     | 0.3182           | 0.5227           | 0.1457                    |
| pileup_mask_transformer_new         | 51          | -6.534       | 22.63           | 0.4872                     | 0.1136           | 0.3864           | 0.222                     |
| pileup_mask_transformer_new         | 52          | -7.951       | 22.57           | 0.3889                     | 0.3864           | 0.4773           | 0.1744                    |
| pileup_mask_transformer_new         | 53          | -10.74       | 23.16           | 0.4839                     | 0.2955           | 0.4091           | 0.1586                    |
| pileup_mask_transformer_new         | 54          | -11.8        | 19.4            | 0.4722                     | 0.1818           | 0.2955           | 0.1844                    |
| pileup_mask_transformer_new         | 55          | -12.1        | 17.55           | 0.4483                     | 0.3409           | 0.5909           | 0.1419                    |
| pileup_mask_transformer_new         | 56          | -10.43       | 16.24           | 0.4429                     | 0.2045           | 0.4545           | 0.2938                    |
| pileup_mask_transformer_new         | 57          | -14.89       | 19.86           | 0.55                       | 0.3182           | 0.5              | 0.1893                    |
| ridge                               | 44          | 0.9074       | 9.662           | 0.1711                     | 0.1364           | 0.3636           | 0.1084                    |
| ridge                               | 45          | 1.604        | 9.112           | 0.07576                    | 0.25             | 0.3864           | 0.07602                   |
| ridge                               | 48          | 3.963        | 12.93           | 0.2973                     | 0.1591           | 0.25             | 0.09015                   |
| ridge                               | 49          | 2.148        | 10.49           | 0.1857                     | 0.2045           | 0.4091           | 0.098                     |
| ridge                               | 50          | 2.125        | 9.818           | 0.1333                     | 0.3182           | 0.2273           | 0.08194                   |
| ridge                               | 51          | 5.846        | 11.71           | 0.2179                     | 0.1136           | 0.3409           | 0.1036                    |
| ridge                               | 52          | 2.139        | 8.792           | 0.1486                     | 0.1591           | 0.2955           | 0.1343                    |
| ridge                               | 53          | 1.701        | 8.945           | 0.1585                     | 0.06818          | 0.5              | 0.0963                    |
| ridge                               | 54          | -1.247       | 10.16           | 0.1757                     | 0.1591           | 0.3409           | 0.09329                   |
| ridge                               | 55          | 2.147        | 10.18           | 0.2027                     | 0.1591           | 0.4091           | 0.07891                   |
| ridge                               | 56          | 2.878        | 10.68           | 0.197                      | 0.25             | 0.4318           | 0.116                     |
| ridge                               | 57          | 3.054        | 12.06           | 0.2571                     | 0.2045           | 0.2727           | 0.09216                   |
| template_residual_boosted_stack_new | 44          | -0.1503      | 8.959           | 0.1389                     | 0.1818           | 0.3636           | 0.1247                    |
| template_residual_boosted_stack_new | 45          | 1.954        | 6.95            | 0.1                        | 0.2045           | 0.3864           | 0.08587                   |
| template_residual_boosted_stack_new | 48          | 2.263        | 9.138           | 0.1667                     | 0.25             | 0.3636           | 0.139                     |
| template_residual_boosted_stack_new | 49          | 0.7425       | 8.799           | 0.1216                     | 0.1591           | 0.3409           | 0.08219                   |
| template_residual_boosted_stack_new | 50          | -0.539       | 8.329           | 0.1111                     | 0.1818           | 0.4318           | 0.1188                    |
| template_residual_boosted_stack_new | 51          | 2.774        | 8.956           | 0.1579                     | 0.1364           | 0.4318           | 0.1208                    |
| template_residual_boosted_stack_new | 52          | -0.2961      | 9.424           | 0.1429                     | 0.2045           | 0.4091           | 0.1047                    |
| template_residual_boosted_stack_new | 53          | 1.217        | 10.57           | 0.1622                     | 0.1591           | 0.4318           | 0.1149                    |
| template_residual_boosted_stack_new | 54          | 0.1796       | 8.193           | 0.1389                     | 0.1818           | 0.3864           | 0.1251                    |
| template_residual_boosted_stack_new | 55          | 0.4214       | 8.482           | 0.1765                     | 0.2273           | 0.5227           | 0.1099                    |
| template_residual_boosted_stack_new | 56          | 0.7639       | 9.188           | 0.1143                     | 0.2045           | 0.5227           | 0.1445                    |
| template_residual_boosted_stack_new | 57          | 0.8932       | 10.66           | 0.25                       | 0.2727           | 0.3182           | 0.1079                    |
| temporal_convolution_tcn            | 44          | -17.28       | 20.61           | 0.5811                     | 0.1591           | 0.6591           | 0.2059                    |
| temporal_convolution_tcn            | 45          | -10.75       | 18.11           | 0.4487                     | 0.1136           | 0.6136           | 0.1168                    |
| temporal_convolution_tcn            | 48          | -13.33       | 22.37           | 0.5303                     | 0.25             | 0.5              | 0.207                     |
| temporal_convolution_tcn            | 49          | -12.97       | 19.27           | 0.5641                     | 0.1136           | 0.6591           | 0.1708                    |
| temporal_convolution_tcn            | 50          | -11.58       | 21.45           | 0.5417                     | 0.1818           | 0.7273           | 0.1534                    |
| temporal_convolution_tcn            | 51          | -9.132       | 22.99           | 0.5                        | 0.06818          | 0.5455           | 0.1937                    |
| temporal_convolution_tcn            | 52          | -14.69       | 16.95           | 0.6026                     | 0.1136           | 0.5682           | 0.1565                    |
| temporal_convolution_tcn            | 53          | -16.07       | 21.75           | 0.5641                     | 0.1136           | 0.6591           | 0.1322                    |
| temporal_convolution_tcn            | 54          | -12.29       | 20.87           | 0.5                        | 0.1364           | 0.4545           | 0.2097                    |
| temporal_convolution_tcn            | 55          | -15.55       | 19.85           | 0.5571                     | 0.2045           | 0.6591           | 0.1499                    |
| temporal_convolution_tcn            | 56          | -9.839       | 19.81           | 0.4359                     | 0.1136           | 0.6136           | 0.2392                    |
| temporal_convolution_tcn            | 57          | -16.8        | 21.99           | 0.6                        | 0.2045           | 0.5682           | 0.198                     |
| tiny_sequence_transformer           | 44          | -20.44       | 21.35           | 0.5536                     | 0.3636           | 0.5227           | 0.1561                    |
| tiny_sequence_transformer           | 45          | -5.63        | 21.5            | 0.3871                     | 0.2955           | 0.5455           | 0.1085                    |
| tiny_sequence_transformer           | 48          | -13.73       | 23.19           | 0.5                        | 0.3864           | 0.3636           | 0.1929                    |
| tiny_sequence_transformer           | 49          | -11.36       | 23.11           | 0.4714                     | 0.2045           | 0.4773           | 0.1066                    |
| tiny_sequence_transformer           | 50          | -8.295       | 23.23           | 0.431                      | 0.3409           | 0.5227           | 0.1471                    |
| tiny_sequence_transformer           | 51          | -10.58       | 22.9            | 0.4459                     | 0.1591           | 0.3864           | 0.1888                    |
| tiny_sequence_transformer           | 52          | -7.228       | 21.65           | 0.375                      | 0.3636           | 0.3864           | 0.1924                    |
| tiny_sequence_transformer           | 53          | -13.8        | 24.31           | 0.4516                     | 0.2955           | 0.4091           | 0.1845                    |
| tiny_sequence_transformer           | 54          | -9.152       | 22.73           | 0.4286                     | 0.2045           | 0.2955           | 0.201                     |
| tiny_sequence_transformer           | 55          | -19.24       | 22.69           | 0.5714                     | 0.3636           | 0.5455           | 0.1786                    |
| tiny_sequence_transformer           | 56          | -10.38       | 21.76           | 0.375                      | 0.2727           | 0.4545           | 0.2285                    |
| tiny_sequence_transformer           | 57          | -16.72       | 23.13           | 0.5333                     | 0.3182           | 0.4318           | 0.203                     |
| two_pulse_template_cfd_baseline     | 44          | 2.721        | 8.966           | 0.1923                     | 0.7045           | 0.1591           | 0.07542                   |
| two_pulse_template_cfd_baseline     | 45          | 3.377        | 9.534           | 0.1667                     | 0.6591           | 0.3182           | 0.06368                   |
| two_pulse_template_cfd_baseline     | 48          | 3.483        | 10.47           | 0.2                        | 0.7727           | 0.2727           | 0.1269                    |
| two_pulse_template_cfd_baseline     | 49          | 4.526        | 5.223           | 0.09375                    | 0.6364           | 0.25             | 0.07581                   |
| two_pulse_template_cfd_baseline     | 50          | 3.585        | 8.11            | 0.1667                     | 0.6591           | 0.25             | 0.104                     |
| two_pulse_template_cfd_baseline     | 51          | 1.888        | 9.803           | 0.2                        | 0.4318           | 0.2727           | 0.07629                   |
| two_pulse_template_cfd_baseline     | 52          | 3.149        | 11.87           | 0.2143                     | 0.6818           | 0.25             | 0.09758                   |
| two_pulse_template_cfd_baseline     | 53          | -0.1908      | 11.47           | 0.2059                     | 0.6136           | 0.2273           | 0.1854                    |
| two_pulse_template_cfd_baseline     | 54          | 1.408        | 10.95           | 0.1818                     | 0.75             | 0.2045           | 0.1011                    |
| two_pulse_template_cfd_baseline     | 55          | 3.778        | 13.78           | 0.3                        | 0.6591           | 0.25             | 0.1427                    |
| two_pulse_template_cfd_baseline     | 56          | 0.5183       | 5.338           | 0.02941                    | 0.6136           | 0.3409           | 0.1721                    |
| two_pulse_template_cfd_baseline     | 57          | 1.63         | 5.959           | 0.09091                    | 0.75             | 0.1818           | 0.06936                   |

## Injection-source bootstrap stress test

As a second uncertainty check, source units are
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This is stricter than an
event bootstrap because it preserves run-local residual source, stave/PID proxy,
pile-up label, delay family, and amplitude-ratio family.

| method                              | n_source_units | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | detection_ap | detection_ap_ci_low | detection_ap_ci_high | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high |
| ----------------------------------- | -------------- | --------------- | ---------------------- | ----------------------- | ------------ | ------------------- | -------------------- | ------------------------- | -------------------------------- | --------------------------------- |
| two_pulse_template_cfd_baseline     | 384            | 8.657           | 7.201                  | 10.74                   | 0.6102       | 0.5566              | 0.6953               | 0.1239                    | 0.09407                          | 0.1522                            |
| template_residual_boosted_stack_new | 384            | 8.894           | 8.116                  | 9.558                   | 0.8029       | 0.7424              | 0.8569               | 0.115                     | 0.1081                           | 0.1274                            |
| gradient_boosted_trees              | 384            | 9.353           | 8.596                  | 10.1                    | 0.7897       | 0.7307              | 0.8473               | 0.1162                    | 0.104                            | 0.1327                            |
| ridge                               | 384            | 10.44           | 9.585                  | 11.47                   | 0.803        | 0.7511              | 0.8617               | 0.1021                    | 0.09002                          | 0.1127                            |
| mlp                                 | 384            | 14.1            | 13.11                  | 15.47                   | 0.7055       | 0.6388              | 0.7889               | 0.216                     | 0.1871                           | 0.2279                            |
| 1d_cnn                              | 384            | 15.34           | 14.03                  | 16.01                   | 0.6375       | 0.5579              | 0.7349               | 0.2097                    | 0.1837                           | 0.2391                            |
| pileup_mask_transformer_new         | 384            | 20.16           | 18.64                  | 21.52                   | 0.6506       | 0.5738              | 0.745                | 0.1855                    | 0.1744                           | 0.2076                            |
| temporal_convolution_tcn            | 384            | 21.21           | 19.76                  | 22.1                    | 0.6189       | 0.5382              | 0.6953               | 0.1858                    | 0.1617                           | 0.21                              |
| tiny_sequence_transformer           | 384            | 23.05           | 21.71                  | 24.13                   | 0.6754       | 0.6036              | 0.7534               | 0.1849                    | 0.1653                           | 0.2199                            |

## Timing Uncertainty Calibration

| method                              | n_detected_overlap | median_predicted_timing_uncertainty_ns | empirical_coverage_1sigma | empirical_coverage_2sigma | mean_abs_timing_error_ns |
| ----------------------------------- | ------------------ | -------------------------------------- | ------------------------- | ------------------------- | ------------------------ |
| two_pulse_template_cfd_baseline     | 179                | 5.316                                  | 0.5028                    | 0.7402                    | 8.695                    |
| mlp                                 | 357                | 9.404                                  | 0.5014                    | 0.7997                    | 12.08                    |
| tiny_sequence_transformer           | 371                | 18.71                                  | 0.5013                    | 0.8962                    | 19.46                    |
| pileup_mask_transformer_new         | 389                | 17.74                                  | 0.5013                    | 0.9126                    | 17.65                    |
| gradient_boosted_trees              | 435                | 5.636                                  | 0.5011                    | 0.7552                    | 8.151                    |
| 1d_cnn                              | 445                | 10.87                                  | 0.5011                    | 0.909                     | 11.82                    |
| template_residual_boosted_stack_new | 424                | 5.596                                  | 0.5                       | 0.7583                    | 7.822                    |
| ridge                               | 432                | 7.095                                  | 0.5                       | 0.7917                    | 9.087                    |
| temporal_convolution_tcn            | 450                | 2.172                                  | 0.05778                   | 0.1222                    | 18.62                    |

## Systematics and caveats

The benchmark uses controlled injections into raw-ROOT-derived high-current
candidate-surface residuals, so truth is exact for delay and amplitude but the
absolute real beam pile-up frequency is not measured.  The hand-scan ledgers are
used to define the candidate surface, not as constituent timing labels.  The
saturation endpoint is an amplitude-knee proxy, not electronics metadata.
Pedestal shift is represented by clean-control false splitting and run-local
residuals, not an independent pedestal trigger stream.  PID confusion is
therefore a stave-conditioned boundary proxy rather than a particle-ID truth
confusion matrix.  The 18-sample waveform limits sub-sample deconvolution below
roughly one digitizer tick; all models inherit that sampling floor.  Finally, the
run-block bootstrap has only the finite held-out run set, so its CIs quantify
run-transfer uncertainty rather than asymptotic event uncertainty.

Runtime was `103.8` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

## Proposed next experiment

S37c should perform a direct event-key join between reviewer hand-scan candidate
rows and raw HRD windows, then score deconvolution outputs against reviewer
labels with explicit disagreement intervals.  The expected information gain is a
separation between architecture robustness and hand-scan label uncertainty on
actual real beam pile-up candidates.

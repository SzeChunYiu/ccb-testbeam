# S51a: Constant-Fraction Timing Versus Waveform ML Pulse-Shape Atlas

## Abstract

Ticket `#2459` requested a raw-ROOT-anchored, academic-grade benchmark of
traditional leading-edge/constant-fraction and template time-warp timing against
ridge, gradient-boosted trees, MLP, 1D-CNN, transformer-style sequence models,
and a sensible new architecture.  Worker `testbeam-laptop-1` claimed the ticket for
project `testbeam`.  The selected winner in `result.json` is
**`template_residual_boosted_stack_new`**, with registered atlas score `2.152`,
leading-edge timing sigma68 `4.713` ns
and 95% run-block CI
[`3.736`,
`5.336`].

## Raw ROOT Reproduction

Raw inputs are `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.  Each file is read from
`h101/HRDv` and reshaped to `(event, channel, sample)`.  The B2/B4/B6/B8 anchor
uses pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split, Templates, And Synthetic Truth

Train and test units are disjoint by source run.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Stave templates are estimated only from
train-run clean pulses:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              768 |                   2.579 |                      5 |           9.187 |
| B4      |              756 |                   2.944 |                      6 |          10.76  |
| B6      |              723 |                   3.748 |                      6 |           9.736 |
| B8      |              478 |                   4.26  |                      8 |           9.252 |

Controlled pulse pairs are injected as

`w(t)=A_1T_s(t-t_1)+rA_1T_s(t-t_1-Delta)+epsilon_rs(t)+p`,

where `epsilon_rs(t)` is a run-local raw-pulse residual and `p` is a pedestal
excursion.  Clean single-pulse controls use the same residual and amplitude
spectrum.  This design gives exact timing, shape, pile-up, and saturation-onset
truth while preserving raw waveform noise and run structure.

## Methods

| method                              | family           | description                                                               |
|:------------------------------------|:-----------------|:--------------------------------------------------------------------------|
| two_pulse_template_cfd_baseline     | traditional      | constant-fraction initialized aligned template/time-warp fit              |
| ridge                               | linear ML        | ridge classifier and multi-output ridge regression on hand pulse features |
| gradient_boosted_trees              | tree ML          | histogram gradient-boosted classifier and regressors                      |
| mlp                                 | neural network   | multilayer perceptron on normalized waveform summaries                    |
| 1d_cnn                              | neural network   | compact one-dimensional CNN over 18 ADC samples                           |
| temporal_convolution_tcn            | neural sequence  | dilated temporal CNN with timing-scale head                               |
| tiny_sequence_transformer           | neural sequence  | one-layer self-attention encoder over the waveform window                 |
| pileup_mask_transformer_new         | new architecture | attention encoder with deterministic late-curvature pile-up mask          |
| template_residual_boosted_stack_new | new hybrid       | boosted residual stack on top of template/time-warp outputs               |

The traditional comparator fits one- and two-pulse hypotheses by

`SSE_k = sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`,

using constant-fraction/optimal-filter seeds and a bounded time-warp grid.  The
new architecture is `pileup_mask_transformer_new`; it supplies attention with a
label-free late-curvature mask beginning just after the observed primary peak,
which is sensible for unresolved second-pulse timing.

## Metrics And Uncertainty

Leading timing error is `e_1 = 10 ns (hat t_1-t_1)`.  Secondary separation error
is `e_Delta = 10 ns [(hat t_2-hat t_1)-Delta]`.  Robust width is

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

The atlas shape residual is

`R_shape = median sqrt((e_1/20)^2 + (e_2/20)^2 + (e_E/0.20)^2)`.

Bootstrap CIs are percentile 95% intervals from
`400` resamples of held-out runs.  The
registered winner minimizes

`C = sigma_1/18 + sigma_Delta/24 + 1.35 R_shape + 2.5 sigma_E + 0.55 r_miss + 0.55 r_false + 1.5 r_ped + 2 B_stave`.

## Overall Held-Out Metrics

| method                              |   detection_ap |   detection_auc |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------------------------------|---------------:|----------------:|---------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|----------------------------:|
| template_residual_boosted_stack_new |         0.8572 |          0.8285 |        -0.1532 |             6.796 |                    6.303 |                     7.211 |             0.3658 |             0.1368 |                     0.07345 |
| gradient_boosted_trees              |         0.8401 |          0.8155 |        -0.1446 |             6.877 |                    6.274 |                     7.334 |             0.3447 |             0.1421 |                     0.07161 |
| ridge                               |         0.7934 |          0.8047 |        -0.4344 |             8.996 |                    8.733 |                     9.366 |             0.3342 |             0.1789 |                     0.06484 |
| two_pulse_template_cfd_baseline     |         0.6764 |          0.6312 |         0.3209 |             9.412 |                    8.66  |                    10.2   |             0.5711 |             0.1974 |                     0.08049 |
| 1d_cnn                              |         0.8103 |          0.7869 |        -3.068  |            10.96  |                    9.089 |                    12.22  |             0.3342 |             0.2316 |                     0.1076  |
| temporal_convolution_tcn            |         0.8209 |          0.8024 |       -10.34   |            11.36  |                   10.82  |                    12.05  |             0.2947 |             0.2421 |                     0.1392  |
| tiny_sequence_transformer           |         0.7941 |          0.7955 |       -11.02   |            12.75  |                   11.73  |                    14.04  |             0.3737 |             0.1842 |                     0.1116  |
| pileup_mask_transformer_new         |         0.7849 |          0.7819 |        -7.801  |            13.03  |                   12.6   |                    13.58  |             0.3237 |             0.2474 |                     0.09391 |
| mlp                                 |         0.8336 |          0.8115 |        -1.289  |            13.12  |                   12.91  |                    14.04  |             0.3842 |             0.1395 |                     0.1601  |

## Endpoint Table With CIs

| method                              |   leading_edge_time_sigma68_ns |   leading_edge_time_sigma68_ns_ci_low |   leading_edge_time_sigma68_ns_ci_high |   secondary_pulse_delay_sigma68_ns |   secondary_pulse_delay_sigma68_ns_ci_low |   secondary_pulse_delay_sigma68_ns_ci_high |   shape_residual_proxy_median |   saturation_interaction_energy_sigma68 |   pedestal_shift_false_split_rate |   energy_proxy_distortion_sigma68 |   pid_confusion_stave_bias_span |
|:------------------------------------|-------------------------------:|--------------------------------------:|---------------------------------------:|-----------------------------------:|------------------------------------------:|-------------------------------------------:|------------------------------:|----------------------------------------:|----------------------------------:|----------------------------------:|--------------------------------:|
| template_residual_boosted_stack_new |                          4.713 |                                 3.736 |                                  5.336 |                              9.692 |                                     9.425 |                                      10.47 |                        0.5329 |                                 0.03068 |                            0.1368 |                           0.07345 |                         0.05083 |
| gradient_boosted_trees              |                          4.905 |                                 3.971 |                                  5.489 |                              9.787 |                                     8.567 |                                      10.54 |                        0.5722 |                                 0.03319 |                            0.1421 |                           0.07161 |                         0.08279 |
| two_pulse_template_cfd_baseline     |                          6.246 |                                 5.704 |                                  7.25  |                             12.7   |                                    10     |                                      20    |                        0.6706 |                                 0.03801 |                            0.1974 |                           0.08049 |                         0.09993 |
| ridge                               |                          6.506 |                                 5.686 |                                  7.485 |                             14.17  |                                    13.07  |                                      15.12 |                        0.593  |                                 0.0457  |                            0.1789 |                           0.06484 |                         0.07528 |
| 1d_cnn                              |                          8.846 |                                 7.513 |                                 11.9   |                             15.26  |                                    14.29  |                                      15.97 |                        0.8399 |                                 0.09211 |                            0.2316 |                           0.1076  |                         0.02422 |
| mlp                                 |                         12.16  |                                11.21  |                                 12.86  |                             17.21  |                                    15.32  |                                      18.96 |                        1.062  |                                 0.1206  |                            0.1395 |                           0.1601  |                         0.1036  |
| pileup_mask_transformer_new         |                         12.26  |                                11.09  |                                 12.92  |                             18.88  |                                    16.09  |                                      20.14 |                        1.036  |                                 0.01981 |                            0.2474 |                           0.09391 |                         0.01708 |
| tiny_sequence_transformer           |                         12.27  |                                10.32  |                                 13.97  |                             17.6   |                                    15.97  |                                      19.88 |                        1.184  |                                 0.04838 |                            0.1842 |                           0.1116  |                         0.08331 |
| temporal_convolution_tcn            |                         12.85  |                                12     |                                 13.35  |                             19.1   |                                    17.36  |                                      20.57 |                        1.326  |                                 0.09198 |                            0.2421 |                           0.1392  |                         0.06118 |

## Winner Table

| method                              |   winner_score |   leading_edge_time_sigma68_ns |   secondary_pulse_delay_sigma68_ns |   shape_residual_proxy_median |   energy_proxy_distortion_sigma68 |   pileup_miss_rate |   false_split_rate |   pedestal_shift_false_split_rate |   pid_confusion_stave_bias_span |
|:------------------------------------|---------------:|-------------------------------:|-----------------------------------:|------------------------------:|----------------------------------:|-------------------:|-------------------:|----------------------------------:|--------------------------------:|
| template_residual_boosted_stack_new |          2.152 |                          4.713 |                              9.692 |                        0.5329 |                           0.07345 |             0.3658 |             0.1368 |                            0.1368 |                         0.05083 |
| gradient_boosted_trees              |          2.278 |                          4.905 |                              9.787 |                        0.5722 |                           0.07161 |             0.3447 |             0.1421 |                            0.1421 |                         0.08279 |
| ridge                               |          2.616 |                          6.506 |                             14.17  |                        0.593  |                           0.06484 |             0.3342 |             0.1789 |                            0.1789 |                         0.07528 |
| two_pulse_template_cfd_baseline     |          2.901 |                          6.246 |                             12.7   |                        0.6706 |                           0.08049 |             0.5711 |             0.1974 |                            0.1974 |                         0.09993 |
| 1d_cnn                              |          3.237 |                          8.846 |                             15.26  |                        0.8399 |                           0.1076  |             0.3342 |             0.2316 |                            0.2316 |                         0.02422 |
| pileup_mask_transformer_new         |          3.82  |                         12.26  |                             18.88  |                        1.036  |                           0.09391 |             0.3237 |             0.2474 |                            0.2474 |                         0.01708 |
| mlp                                 |          3.931 |                         12.16  |                             17.21  |                        1.062  |                           0.1601  |             0.3842 |             0.1395 |                            0.1395 |                         0.1036  |
| tiny_sequence_transformer           |          4.042 |                         12.27  |                             17.6   |                        1.184  |                           0.1116  |             0.3737 |             0.1842 |                            0.1842 |                         0.08331 |
| temporal_convolution_tcn            |          4.429 |                         12.85  |                             19.1   |                        1.326  |                           0.1392  |             0.2947 |             0.2421 |                            0.2421 |                         0.06118 |

The traditional template/time-warp baseline scored `2.901`
with leading-edge sigma68 `6.246` ns.  The
winner changes leading-edge sigma68 by
`-1.533`
ns and secondary-delay sigma68 by
`-3.008`
ns.

## Run-Stratified Stability

| method                              |   heldout_run |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------------------------------|--------------:|---------------:|------------------:|-----------------------------:|-------------------:|-------------------:|----------------------------:|
| 1d_cnn                              |            58 |       -1.727   |            11.41  |                      0.1786  |             0.2632 |            0.2763  |                     0.06824 |
| 1d_cnn                              |            60 |       -4.425   |            13.18  |                      0.2857  |             0.3553 |            0.2237  |                     0.09934 |
| 1d_cnn                              |            62 |       -3.15    |             9.594 |                      0.1771  |             0.3684 |            0.25    |                     0.1109  |
| 1d_cnn                              |            64 |       -1.986   |             8.423 |                      0.1383  |             0.3816 |            0.2105  |                     0.1052  |
| 1d_cnn                              |            65 |       -4.557   |            10.41  |                      0.1981  |             0.3026 |            0.1974  |                     0.1092  |
| gradient_boosted_trees              |            58 |       -0.1926  |             7.115 |                      0.07627 |             0.2237 |            0.1447  |                     0.08001 |
| gradient_boosted_trees              |            60 |        0.08213 |             6.908 |                      0.08824 |             0.3289 |            0.1711  |                     0.06496 |
| gradient_boosted_trees              |            62 |       -0.6791  |             7.71  |                      0.102   |             0.3553 |            0.1579  |                     0.05983 |
| gradient_boosted_trees              |            64 |        1.605   |             6.456 |                      0.1071  |             0.4474 |            0.1316  |                     0.07453 |
| gradient_boosted_trees              |            65 |       -0.3894  |             6.281 |                      0.09375 |             0.3684 |            0.1053  |                     0.07412 |
| mlp                                 |            58 |       -0.2582  |            13.21  |                      0.2593  |             0.2895 |            0.1579  |                     0.1426  |
| mlp                                 |            60 |       -1.995   |            15.64  |                      0.25    |             0.3158 |            0.1447  |                     0.1667  |
| mlp                                 |            62 |       -4.339   |            12.85  |                      0.2222  |             0.4079 |            0.2237  |                     0.132   |
| mlp                                 |            64 |       -1.153   |            12.81  |                      0.2778  |             0.5263 |            0.06579 |                     0.1911  |
| mlp                                 |            65 |       -0.4684  |            13.05  |                      0.2553  |             0.3816 |            0.1053  |                     0.1549  |
| pileup_mask_transformer_new         |            58 |       -8.312   |            13.52  |                      0.3534  |             0.2368 |            0.2237  |                     0.06173 |
| pileup_mask_transformer_new         |            60 |       -7.203   |            13.58  |                      0.2685  |             0.2895 |            0.2105  |                     0.1077  |
| pileup_mask_transformer_new         |            62 |       -7.817   |            12.97  |                      0.3021  |             0.3684 |            0.3289  |                     0.1002  |
| pileup_mask_transformer_new         |            64 |       -7.579   |            12.17  |                      0.3111  |             0.4079 |            0.2105  |                     0.08593 |
| pileup_mask_transformer_new         |            65 |       -9.717   |            13.45  |                      0.375   |             0.3158 |            0.2632  |                     0.08579 |
| ridge                               |            58 |       -0.7351  |             8.608 |                      0.1053  |             0.25   |            0.2237  |                     0.05217 |
| ridge                               |            60 |       -0.5523  |             9.59  |                      0.1273  |             0.2763 |            0.2105  |                     0.06407 |
| ridge                               |            62 |       -0.7003  |             9.393 |                      0.117   |             0.3816 |            0.1974  |                     0.0776  |
| ridge                               |            64 |        2.229   |             9.41  |                      0.1111  |             0.4079 |            0.1316  |                     0.05234 |
| ridge                               |            65 |       -2.01    |             8.293 |                      0.1429  |             0.3553 |            0.1316  |                     0.066   |
| template_residual_boosted_stack_new |            58 |       -0.1131  |             7.253 |                      0.09434 |             0.3026 |            0.1711  |                     0.08241 |
| template_residual_boosted_stack_new |            60 |       -0.3099  |             6.447 |                      0.08824 |             0.3289 |            0.1447  |                     0.06485 |
| template_residual_boosted_stack_new |            62 |       -0.5987  |             6.65  |                      0.05319 |             0.3816 |            0.1447  |                     0.07741 |
| template_residual_boosted_stack_new |            64 |        1.138   |             6.366 |                      0.07778 |             0.4079 |            0.1184  |                     0.06764 |
| template_residual_boosted_stack_new |            65 |       -0.9068  |             6.409 |                      0.08889 |             0.4079 |            0.1053  |                     0.05782 |
| temporal_convolution_tcn            |            58 |      -10.44    |            11.13  |                      0.3983  |             0.2237 |            0.2763  |                     0.1227  |
| temporal_convolution_tcn            |            60 |      -11.38    |            12.69  |                      0.4224  |             0.2368 |            0.3026  |                     0.1304  |
| temporal_convolution_tcn            |            62 |      -10.02    |            10.66  |                      0.3846  |             0.3158 |            0.25    |                     0.1384  |
| temporal_convolution_tcn            |            64 |       -9.524   |             9.656 |                      0.3111  |             0.4079 |            0.1579  |                     0.149   |
| temporal_convolution_tcn            |            65 |      -10.58    |            10.7   |                      0.3611  |             0.2895 |            0.2237  |                     0.1191  |
| tiny_sequence_transformer           |            58 |      -10.76    |            14.33  |                      0.434   |             0.3026 |            0.1579  |                     0.09785 |
| tiny_sequence_transformer           |            60 |       -9.908   |            13.15  |                      0.3723  |             0.3816 |            0.2105  |                     0.1097  |
| tiny_sequence_transformer           |            62 |      -10.98    |            10.71  |                      0.3878  |             0.3553 |            0.2895  |                     0.1079  |
| tiny_sequence_transformer           |            64 |      -11.13    |            11.83  |                      0.3571  |             0.4474 |            0.1316  |                     0.1217  |
| tiny_sequence_transformer           |            65 |      -11.89    |            14.2   |                      0.4149  |             0.3816 |            0.1316  |                     0.09674 |
| two_pulse_template_cfd_baseline     |            58 |       -0.7348  |             9.276 |                      0.1184  |             0.5    |            0.2368  |                     0.08244 |
| two_pulse_template_cfd_baseline     |            60 |        1.182   |             9.806 |                      0.1935  |             0.5921 |            0.1842  |                     0.08598 |
| two_pulse_template_cfd_baseline     |            62 |        1.235   |             9.129 |                      0.1452  |             0.5921 |            0.1842  |                     0.08164 |
| two_pulse_template_cfd_baseline     |            64 |       -0.1666  |             7.496 |                      0.1216  |             0.5132 |            0.1974  |                     0.06132 |
| two_pulse_template_cfd_baseline     |            65 |        0.6741  |            10.21  |                      0.2115  |             0.6579 |            0.1842  |                     0.07593 |

## Source-Unit Bootstrap

Source units are `source_run:stave:is_overlap:spacing_bin:ratio_bin`, preserving
run residuals, stave/PID proxy, overlap status, delay family, and amplitude-ratio
family.

| method                              |   n_source_units |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   detection_ap |   detection_ap_ci_low |   detection_ap_ci_high |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |
|:------------------------------------|-----------------:|------------------:|-------------------------:|--------------------------:|---------------:|----------------------:|-----------------------:|----------------------------:|-----------------------------------:|------------------------------------:|
| template_residual_boosted_stack_new |              210 |             6.796 |                    6.134 |                     7.379 |         0.8572 |                0.8036 |                 0.9145 |                     0.07345 |                            0.06293 |                             0.08483 |
| gradient_boosted_trees              |              210 |             6.877 |                    6.202 |                     7.668 |         0.8401 |                0.7834 |                 0.9052 |                     0.07161 |                            0.06386 |                             0.08472 |
| ridge                               |              210 |             8.996 |                    8.2   |                    10.08  |         0.7934 |                0.7047 |                 0.8749 |                     0.06484 |                            0.05365 |                             0.0717  |
| two_pulse_template_cfd_baseline     |              210 |             9.412 |                    8     |                    10.48  |         0.6764 |                0.5828 |                 0.7703 |                     0.08049 |                            0.06492 |                             0.09514 |
| 1d_cnn                              |              210 |            10.96  |                    9.746 |                    11.91  |         0.8103 |                0.7371 |                 0.895  |                     0.1076  |                            0.08867 |                             0.1198  |
| temporal_convolution_tcn            |              210 |            11.36  |                   10.62  |                    12.15  |         0.8209 |                0.7458 |                 0.8892 |                     0.1392  |                            0.1174  |                             0.1539  |
| tiny_sequence_transformer           |              210 |            12.75  |                   11.81  |                    13.93  |         0.7941 |                0.7108 |                 0.8748 |                     0.1116  |                            0.1006  |                             0.1299  |
| pileup_mask_transformer_new         |              210 |            13.03  |                   12.33  |                    14.24  |         0.7849 |                0.7017 |                 0.8783 |                     0.09391 |                            0.07792 |                             0.1072  |
| mlp                                 |              210 |            13.12  |                   12.07  |                    14.42  |         0.8336 |                0.7753 |                 0.8996 |                     0.1601  |                            0.1305  |                             0.1867  |

## Timing-Uncertainty Calibration

| method                              |   n_detected_overlap |   median_predicted_timing_uncertainty_ns |   empirical_coverage_1sigma |   empirical_coverage_2sigma |   mean_abs_timing_error_ns |
|:------------------------------------|---------------------:|-----------------------------------------:|----------------------------:|----------------------------:|---------------------------:|
| two_pulse_template_cfd_baseline     |                  163 |                                    6.3   |                      0.5031 |                      0.7485 |                      8.423 |
| template_residual_boosted_stack_new |                  241 |                                    4.644 |                      0.5021 |                      0.8112 |                      6.033 |
| gradient_boosted_trees              |                  249 |                                    4.792 |                      0.502  |                      0.7892 |                      6.261 |
| ridge                               |                  253 |                                    6.385 |                      0.502  |                      0.8419 |                      7.431 |
| 1d_cnn                              |                  253 |                                    7.817 |                      0.502  |                      0.8399 |                      9.121 |
| pileup_mask_transformer_new         |                  257 |                                    9.943 |                      0.5019 |                      0.7996 |                     12.6   |
| mlp                                 |                  234 |                                    9.167 |                      0.5    |                      0.8397 |                     11.33  |
| tiny_sequence_transformer           |                  238 |                                   11.92  |                      0.5    |                      0.8319 |                     13.96  |
| temporal_convolution_tcn            |                  268 |                                    1.657 |                      0.0597 |                      0.1287 |                     13.14  |

## Strata And Systematics

The stratum scan covers pile-up spacing, amplitude ratio, stave, and overlap
state:

| stratum     | value          | method                              |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------|:---------------|:------------------------------------|---------------:|------------------:|-------------------:|-------------------:|----------------------------:|
| spacing_bin | (-0.001, 10.0] | 1d_cnn                              |      -2.88     |            12.32  |             0.5397 |                nan |                     0.07877 |
| spacing_bin | (10.0, 25.0]   | 1d_cnn                              |      -5.301    |            10.92  |             0.3294 |                nan |                     0.1177  |
| spacing_bin | (25.0, 45.0]   | 1d_cnn                              |      -4.349    |             8.04  |             0.2308 |                nan |                     0.1014  |
| spacing_bin | (45.0, 70.0]   | 1d_cnn                              |      -0.4691   |            12.06  |             0.1429 |                nan |                     0.1102  |
| spacing_bin | (-0.001, 10.0] | gradient_boosted_trees              |       1.736    |             6.986 |             0.5238 |                nan |                     0.05347 |
| spacing_bin | (10.0, 25.0]   | gradient_boosted_trees              |       0.5478   |             6.656 |             0.3412 |                nan |                     0.06187 |
| spacing_bin | (25.0, 45.0]   | gradient_boosted_trees              |      -0.1399   |             6.971 |             0.2821 |                nan |                     0.06336 |
| spacing_bin | (45.0, 70.0]   | gradient_boosted_trees              |      -1.741    |             6.463 |             0.1538 |                nan |                     0.07903 |
| spacing_bin | (-0.001, 10.0] | mlp                                 |       6.969    |            10.79  |             0.5635 |                nan |                     0.1436  |
| spacing_bin | (10.0, 25.0]   | mlp                                 |      -0.1087   |             9.941 |             0.4    |                nan |                     0.1326  |
| spacing_bin | (25.0, 45.0]   | mlp                                 |      -6.006    |            12.75  |             0.3333 |                nan |                     0.1434  |
| spacing_bin | (45.0, 70.0]   | mlp                                 |      -5.146    |            14.77  |             0.1648 |                nan |                     0.1665  |
| spacing_bin | (-0.001, 10.0] | pileup_mask_transformer_new         |      -7.817    |            11.62  |             0.4841 |                nan |                     0.086   |
| spacing_bin | (10.0, 25.0]   | pileup_mask_transformer_new         |      -8.604    |            10.44  |             0.2706 |                nan |                     0.08049 |
| spacing_bin | (25.0, 45.0]   | pileup_mask_transformer_new         |     -10.58     |            12.55  |             0.2949 |                nan |                     0.07732 |
| spacing_bin | (45.0, 70.0]   | pileup_mask_transformer_new         |      -2.756    |            16.85  |             0.1758 |                nan |                     0.09177 |
| spacing_bin | (-0.001, 10.0] | ridge                               |       0.3313   |             9.584 |             0.4762 |                nan |                     0.05777 |
| spacing_bin | (10.0, 25.0]   | ridge                               |       0.02813  |             6.826 |             0.3294 |                nan |                     0.05819 |
| spacing_bin | (25.0, 45.0]   | ridge                               |      -0.6466   |             8.246 |             0.3205 |                nan |                     0.05339 |
| spacing_bin | (45.0, 70.0]   | ridge                               |      -2.211    |            11.36  |             0.1538 |                nan |                     0.06139 |
| spacing_bin | (-0.001, 10.0] | template_residual_boosted_stack_new |       1.7      |             6.552 |             0.5556 |                nan |                     0.06684 |
| spacing_bin | (10.0, 25.0]   | template_residual_boosted_stack_new |       0.05894  |             6.092 |             0.3529 |                nan |                     0.06655 |
| spacing_bin | (25.0, 45.0]   | template_residual_boosted_stack_new |      -0.3099   |             7.106 |             0.2564 |                nan |                     0.05521 |
| spacing_bin | (45.0, 70.0]   | template_residual_boosted_stack_new |      -1.7      |             7.239 |             0.2088 |                nan |                     0.06967 |
| spacing_bin | (-0.001, 10.0] | temporal_convolution_tcn            |      -8.147    |            10.27  |             0.5238 |                nan |                     0.1065  |
| spacing_bin | (10.0, 25.0]   | temporal_convolution_tcn            |     -10.88     |             9.492 |             0.2353 |                nan |                     0.09783 |
| spacing_bin | (25.0, 45.0]   | temporal_convolution_tcn            |     -10.43     |            11.88  |             0.1667 |                nan |                     0.09945 |
| spacing_bin | (45.0, 70.0]   | temporal_convolution_tcn            |     -11.96     |            14.17  |             0.1429 |                nan |                     0.1487  |
| spacing_bin | (-0.001, 10.0] | tiny_sequence_transformer           |      -9.316    |            11.88  |             0.5873 |                nan |                     0.06766 |
| spacing_bin | (10.0, 25.0]   | tiny_sequence_transformer           |     -12.91     |            10.48  |             0.3647 |                nan |                     0.07099 |
| spacing_bin | (25.0, 45.0]   | tiny_sequence_transformer           |     -12.28     |            14.41  |             0.2821 |                nan |                     0.09174 |
| spacing_bin | (45.0, 70.0]   | tiny_sequence_transformer           |     -10.03     |            12.45  |             0.1648 |                nan |                     0.09641 |
| spacing_bin | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |       1.689    |            10.86  |             0.754  |                nan |                     0.04621 |
| spacing_bin | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |      -0.002267 |             8.851 |             0.6353 |                nan |                     0.06322 |
| spacing_bin | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |       2.421    |             8.78  |             0.5    |                nan |                     0.09027 |
| spacing_bin | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |      -2.363    |             7.672 |             0.3187 |                nan |                     0.08348 |
| ratio_bin   | (-0.001, 0.35] | 1d_cnn                              |      -6.776    |            10.92  |             0.5455 |                nan |                     0.09813 |
| ratio_bin   | (0.35, 0.625]  | 1d_cnn                              |      -3.295    |            10.87  |             0.3981 |                nan |                     0.09727 |
| ratio_bin   | (0.625, 0.875] | 1d_cnn                              |      -3.429    |            10.19  |             0.2188 |                nan |                     0.09933 |
| ratio_bin   | (0.875, 1.05]  | 1d_cnn                              |      -1.744    |             9.836 |             0.1705 |                nan |                     0.1022  |
| ratio_bin   | (-0.001, 0.35] | gradient_boosted_trees              |      -3.691    |             9.272 |             0.6136 |                nan |                     0.09011 |
| ratio_bin   | (0.35, 0.625]  | gradient_boosted_trees              |      -0.2239   |             6.699 |             0.3796 |                nan |                     0.06686 |
| ratio_bin   | (0.625, 0.875] | gradient_boosted_trees              |      -0.4249   |             6.646 |             0.2292 |                nan |                     0.07212 |
| ratio_bin   | (0.875, 1.05]  | gradient_boosted_trees              |       1.272    |             6.179 |             0.1591 |                nan |                     0.06612 |
| ratio_bin   | (-0.001, 0.35] | mlp                                 |      -6.75     |            17.71  |             0.6477 |                nan |                     0.2104  |
| ratio_bin   | (0.35, 0.625]  | mlp                                 |      -0.6502   |            11.13  |             0.4259 |                nan |                     0.1201  |
| ratio_bin   | (0.625, 0.875] | mlp                                 |      -2.936    |            13.95  |             0.2917 |                nan |                     0.1428  |
| ratio_bin   | (0.875, 1.05]  | mlp                                 |       0.9418   |            13.31  |             0.1705 |                nan |                     0.1708  |
| ratio_bin   | (-0.001, 0.35] | pileup_mask_transformer_new         |      -7.709    |            13.65  |             0.5341 |                nan |                     0.1063  |
| ratio_bin   | (0.35, 0.625]  | pileup_mask_transformer_new         |      -8.853    |            11.98  |             0.3148 |                nan |                     0.08895 |
| ratio_bin   | (0.625, 0.875] | pileup_mask_transformer_new         |      -8.19     |            15.07  |             0.2396 |                nan |                     0.09017 |
| ratio_bin   | (0.875, 1.05]  | pileup_mask_transformer_new         |      -6.347    |            12.59  |             0.2159 |                nan |                     0.0895  |
| ratio_bin   | (-0.001, 0.35] | ridge                               |      -3.803    |            11.5   |             0.5568 |                nan |                     0.07384 |
| ratio_bin   | (0.35, 0.625]  | ridge                               |      -0.6879   |             7.495 |             0.3704 |                nan |                     0.04979 |
| ratio_bin   | (0.625, 0.875] | ridge                               |      -1.368    |             8.926 |             0.2396 |                nan |                     0.0638  |
| ratio_bin   | (0.875, 1.05]  | ridge                               |       1.384    |             7.921 |             0.1705 |                nan |                     0.0551  |
| ratio_bin   | (-0.001, 0.35] | template_residual_boosted_stack_new |      -1.184    |             8.193 |             0.6591 |                nan |                     0.07429 |
| ratio_bin   | (0.35, 0.625]  | template_residual_boosted_stack_new |      -0.8139   |             6.954 |             0.4074 |                nan |                     0.06906 |
| ratio_bin   | (0.625, 0.875] | template_residual_boosted_stack_new |      -0.2124   |             5.82  |             0.2292 |                nan |                     0.06724 |
| ratio_bin   | (0.875, 1.05]  | template_residual_boosted_stack_new |       0.9966   |             5.909 |             0.1705 |                nan |                     0.07909 |
| ratio_bin   | (-0.001, 0.35] | temporal_convolution_tcn            |     -14.27     |            11.45  |             0.4659 |                nan |                     0.1104  |
| ratio_bin   | (0.35, 0.625]  | temporal_convolution_tcn            |     -10.45     |            11.4   |             0.3426 |                nan |                     0.1259  |
| ratio_bin   | (0.625, 0.875] | temporal_convolution_tcn            |      -9.115    |            11.2   |             0.2188 |                nan |                     0.1401  |
| ratio_bin   | (0.875, 1.05]  | temporal_convolution_tcn            |      -9.866    |            12.79  |             0.1477 |                nan |                     0.1588  |
| ratio_bin   | (-0.001, 0.35] | tiny_sequence_transformer           |     -12.77     |            13.17  |             0.5795 |                nan |                     0.1309  |
| ratio_bin   | (0.35, 0.625]  | tiny_sequence_transformer           |     -14.21     |            14.19  |             0.3981 |                nan |                     0.1094  |
| ratio_bin   | (0.625, 0.875] | tiny_sequence_transformer           |      -9.722    |            11.23  |             0.3021 |                nan |                     0.09858 |
| ratio_bin   | (0.875, 1.05]  | tiny_sequence_transformer           |     -10.19     |            11.7   |             0.2159 |                nan |                     0.1101  |
| ratio_bin   | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |      -2.197    |            12.94  |             0.6477 |                nan |                     0.1118  |
| ratio_bin   | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |      -1.237    |             9.229 |             0.5556 |                nan |                     0.08104 |
| ratio_bin   | (0.625, 0.875] | two_pulse_template_cfd_baseline     |      -0.678    |             9.5   |             0.5312 |                nan |                     0.07304 |
| ratio_bin   | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |       2.221    |             5.79  |             0.5568 |                nan |                     0.06224 |
| stave       | B2             | 1d_cnn                              |      -7.655    |            12.97  |             0.4651 |                nan |                     0.1694  |
| stave       | B4             | 1d_cnn                              |      -4.992    |            10.95  |             0.4388 |                nan |                     0.09647 |
| stave       | B6             | 1d_cnn                              |      -1.981    |            10.07  |             0.2952 |                nan |                     0.1044  |
| stave       | B8             | 1d_cnn                              |      -1.241    |             9.82  |             0.1429 |                nan |                     0.08623 |
| stave       | B2             | gradient_boosted_trees              |      -4.433    |             8.539 |             0.4535 |                nan |                     0.07798 |
| stave       | B4             | gradient_boosted_trees              |      -1.512    |             6.659 |             0.3163 |                nan |                     0.05666 |
| stave       | B6             | gradient_boosted_trees              |      -0.1379   |             6.039 |             0.3905 |                nan |                     0.05852 |
| stave       | B8             | gradient_boosted_trees              |       2.19     |             5.621 |             0.2198 |                nan |                     0.05575 |

The main caveat is that truth comes from controlled injections into
raw-ROOT-derived clean pulses; the study quantifies reconstruction capability,
not the real beam pile-up rate.  Saturation onset is an amplitude-ceiling stress
test, not decoded front-end metadata.  Pedestal drift is represented through
run-local residuals and clean-control false splitting, and PID movement is a
stave-conditioned proxy because external species labels are absent in the raw
gate.  With 18 samples per window, sub-sample timing below one digitizer tick is
model-dependent and should be promoted only with independent hardware truth.

Runtime was `546.1` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

# S40c: Pedestal-Saturation Energy Calibration Transfer Under PID-Conditioned Shape Shifts

## Abstract

Ticket `1784179132.900.1de74461` asks whether pedestal state and saturation correction transfer
across runs without silently changing the energy scale or PID boundary when
pulse shape changes.  The raw ROOT selected-pulse count was reproduced before
benchmarking.  The held-out winner written to `result.json` is **`gradient_boosted_trees`**.
It obtains composite score `0.1861`, energy sigma68
`0.07626` with 95% run-block CI
[`0.06778`, `0.08684`],
pedestal high-minus-low bias `-0.005094`, PID
proxy AUC `0.9939`, and conformal 90% coverage
`0.6154`.

## Raw ROOT Reproduction

Inputs are the B-stack reduced HRD files under `/home/billy/ccb-data/extracted/root/root`.  The
runner reads `h101/HRDv` directly, reshapes each event to `(channel, sample)`,
forms the per-channel pedestal

`b_ec = median_{t in 0..3} x_ect`,

and selects B2/B4/B6/B8 pulses by

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split, Truth, and Stress Construction

Validation is leave-run-family-out: train runs `[50, 51, 52, 53, 54, 55, 56, 57]`
and held-out runs `[58, 60, 62, 64, 65]` are disjoint.  Synthetic
pile-up and saturation stressors are generated from raw-ROOT-derived clean
pulses plus run-local residual pools, with ADC clipping at `11800`.
The target energy is `A_1+A_2`; timing uses the first-pulse residual in ns; the
PID boundary is an explicitly declared proxy for the high-charge inner-stave
support class because external particle labels are not present in this ROOT
gate.

Train-only templates:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              832 |                   2.638 |                      5 |           9.164 |
| B4      |              812 |                   2.986 |                      6 |          10.8   |
| B6      |              779 |                   3.758 |                      6 |           9.779 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

## Methods

| method                                         | family             | description                                                                                                         |
|:-----------------------------------------------|:-------------------|:--------------------------------------------------------------------------------------------------------------------|
| analytic_clipped_template_sideband_traditional | traditional        | adaptive pedestal sideband subtraction, clipped-template charge reconstruction, and charge/range proxy PID boundary |
| ridge                                          | linear ML          | ridge/logistic baseline on waveform summary and sample features                                                     |
| gradient_boosted_trees                         | tree ML            | histogram gradient-boosted classifier/regressor panel                                                               |
| mlp                                            | neural network     | tabular multilayer perceptron energy and pile-up heads                                                              |
| 1d_cnn                                         | neural network     | compact one-dimensional convolutional waveform regressor                                                            |
| tiny_sequence_transformer                      | temporal attention | one-layer transformer encoder over the 18 ADC samples                                                               |
| saturation_residual_fusion_new                 | new hybrid         | residual fusion of clipped-template outputs, waveform shape, pedestal state, and clipping sidebands                 |

The traditional comparator solves the bounded clipped-template least-squares
problem

`SSE_k = sum_t [w_t - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`

for one- and two-pulse hypotheses and applies an interpretable sideband
saturation correction.  Learned methods receive only same-event waveform and
shape information.  The new hybrid architecture is sensible here because the
traditional fit localizes the physically meaningful constituents, while the
neural/tree residual layer can model charge hidden by clipping and pedestal
state shifts.

## Endpoints

Energy residual:

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`.

Robust resolution:

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Pedestal transfer contrast:

`Delta_ped = median(e_E | shifted pedestal) - median(e_E | nominal pedestal)`.

The PID score is a train-standardized logistic transform of reconstructed charge
and is scored against the high-charge inner-stave support proxy with AUC and
expected calibration error.  Uncertainty coverage is split-conformal: the 90th
percentile of absolute train-run energy residuals defines an interval, and
coverage is measured on held-out runs.

The declared winner minimizes

`C = sigma_E + 0.20|bias_E| + 0.18|Delta_ped| + 0.25 cal_sat + 0.10 ECE_PID + 0.05(1-AUC_PID) + 0.003 sigma_t + 0.05 r_merge + 0.05 r_false + 0.06|coverage90-0.90|`.

All intervals are 95% percentile intervals from `520`
held-out run-block bootstrap resamples.

## Main Results

| method                                         |   winner_score |   energy_bias |   energy_bias_ci_low |   energy_bias_ci_high |   energy_sigma68 |   energy_sigma68_ci_low |   energy_sigma68_ci_high |   saturation_knee_calibration_abs |   pedestal_high_minus_low_bias |   pid_auc |   pid_calibration_ece |   timing_residual_sigma68_ns |   pileup_merge_rate |   false_split_rate |   coverage90 |
|:-----------------------------------------------|---------------:|--------------:|---------------------:|----------------------:|-----------------:|------------------------:|-------------------------:|----------------------------------:|-------------------------------:|----------:|----------------------:|-----------------------------:|--------------------:|-------------------:|-------------:|
| gradient_boosted_trees                         |         0.1861 |      0.006403 |            -0.003259 |              0.01213  |          0.07626 |                 0.06778 |                  0.08684 |                          0.004651 |                      -0.005094 |    0.9939 |                0.4625 |                        5.141 |              0.3209 |             0.2279 |       0.6154 |
| ridge                                          |         0.1897 |      0.02212  |             0.01786  |              0.0267   |          0.08306 |                 0.07276 |                  0.08942 |                          0.003488 |                       0.01103  |    0.9919 |                0.4556 |                        7.927 |              0.3186 |             0.2326 |       0.8651 |
| saturation_residual_fusion_new                 |         0.1965 |      0.009055 |             0.003182 |              0.0124   |          0.07981 |                 0.06962 |                  0.0858  |                          0.001163 |                       0.002154 |    0.9938 |                0.4614 |                        5.729 |              0.3349 |             0.2419 |       0.5385 |
| 1d_cnn                                         |         0.2257 |      0.01064  |             0.003485 |              0.02144  |          0.1091  |                 0.09869 |                  0.1147  |                          0.001163 |                       0.03255  |    0.9897 |                0.4646 |                       10.26  |              0.3186 |             0.2884 |       0.9041 |
| tiny_sequence_transformer                      |         0.2544 |      0.02438  |             0.008195 |              0.0358   |          0.1171  |                 0.1084  |                  0.1275  |                          0.004651 |                       0.04246  |    0.9899 |                0.4584 |                       14.74  |              0.3372 |             0.2767 |       0.9381 |
| mlp                                            |         0.2656 |     -0.008272 |            -0.01436  |              0.009425 |          0.1498  |                 0.1388  |                  0.1625  |                          0.003488 |                       0.009368 |    0.984  |                0.4651 |                        9.43  |              0.3814 |             0.2395 |       0.8184 |
| analytic_clipped_template_sideband_traditional |         0.2797 |      0.06532  |             0.05797  |              0.08256  |          0.11    |                 0.09556 |                  0.1349  |                          0.001163 |                       0.01456  |    0.5484 |                0.6953 |                        7.476 |              0.5744 |             0.1953 |       0.8876 |

The traditional comparator score is `0.2797` with energy
sigma68 `0.11` and pedestal contrast
`0.01456`.  The winning method changes
energy sigma68 by `-0.03375` and
PID calibration ECE by `-0.2329`
relative to the traditional comparator.

## Held-Out Run Stability

| method                                         |   heldout_run |   energy_bias |   energy_sigma68 |   pedestal_high_minus_low_bias |   pid_auc |   pid_calibration_ece |   timing_residual_sigma68_ns |   pileup_merge_rate |   coverage90 |
|:-----------------------------------------------|--------------:|--------------:|-----------------:|-------------------------------:|----------:|----------------------:|-----------------------------:|--------------------:|-------------:|
| 1d_cnn                                         |            58 |      0.01023  |          0.1129  |                      0.01091   |    0.9919 |                0.4635 |                        9.86  |              0.2791 |       0.9    |
| 1d_cnn                                         |            60 |      0.03673  |          0.1102  |                      0.07861   |    0.9901 |                0.4908 |                        9.779 |              0.3256 |       0.8953 |
| 1d_cnn                                         |            62 |      0.009693 |          0.1004  |                      0.001227  |    0.9913 |                0.4545 |                        9.147 |              0.314  |       0.9651 |
| 1d_cnn                                         |            64 |     -0.001693 |          0.08549 |                      0.03737   |    0.9911 |                0.4475 |                       10.53  |              0.3488 |       0.9306 |
| 1d_cnn                                         |            65 |      0.01425  |          0.1275  |                      0.03364   |    1      |                0.4668 |                        9.877 |              0.3256 |       0.8313 |
| analytic_clipped_template_sideband_traditional |            58 |      0.08533  |          0.09643 |                      0.05111   |    0.4896 |                0.6424 |                        6.748 |              0.6047 |       0.94   |
| analytic_clipped_template_sideband_traditional |            60 |      0.06188  |          0.1481  |                     -0.06035   |    0.2751 |                0.7035 |                        7.622 |              0.6163 |       0.8085 |
| analytic_clipped_template_sideband_traditional |            62 |      0.08435  |          0.1086  |                     -0.01776   |    0.7134 |                0.6831 |                        7.191 |              0.5698 |       0.8966 |
| analytic_clipped_template_sideband_traditional |            64 |      0.05797  |          0.08733 |                      0.00703   |    0.6399 |                0.7151 |                        8.281 |              0.5116 |       0.9474 |
| analytic_clipped_template_sideband_traditional |            65 |      0.05788  |          0.1377  |                      0.01621   |    0.7632 |                0.7326 |                        7.954 |              0.5698 |       0.8364 |
| gradient_boosted_trees                         |            58 |      0.0147   |          0.07137 |                      0.00651   |    0.9968 |                0.4615 |                        5.632 |              0.2907 |       0.5976 |
| gradient_boosted_trees                         |            60 |      0.01148  |          0.09561 |                      0.0001456 |    0.9961 |                0.4855 |                        5.102 |              0.2442 |       0.5682 |
| gradient_boosted_trees                         |            62 |      0.00239  |          0.07396 |                     -0.02309   |    0.9965 |                0.4522 |                        4.487 |              0.3023 |       0.6092 |
| gradient_boosted_trees                         |            64 |     -0.01014  |          0.05924 |                     -0.01057   |    0.994  |                0.4479 |                        4.918 |              0.3953 |       0.6774 |
| gradient_boosted_trees                         |            65 |      0.01213  |          0.08139 |                     -0.0103    |    0.9883 |                0.4652 |                        5.15  |              0.3721 |       0.6479 |
| mlp                                            |            58 |      0.009564 |          0.1521  |                      0.05025   |    0.9806 |                0.46   |                        8.326 |              0.3721 |       0.8462 |
| mlp                                            |            60 |     -0.02694  |          0.1591  |                     -0.02867   |    0.998  |                0.4868 |                       10.32  |              0.3837 |       0.7308 |
| mlp                                            |            62 |     -0.004217 |          0.1428  |                     -0.06412   |    0.9835 |                0.4529 |                        9.147 |              0.3372 |       0.8889 |
| mlp                                            |            64 |     -0.01341  |          0.14    |                      0.03041   |    0.9807 |                0.4525 |                        8.49  |              0.4302 |       0.8448 |
| mlp                                            |            65 |      0.01524  |          0.1431  |                      0.02319   |    0.9942 |                0.4735 |                        8.214 |              0.3837 |       0.7838 |
| ridge                                          |            58 |      0.02893  |          0.07862 |                      0.0009893 |    0.9946 |                0.4528 |                        7.305 |              0.2442 |       0.9302 |
| ridge                                          |            60 |      0.01991  |          0.08887 |                      0.02161   |    1      |                0.4752 |                        7.008 |              0.314  |       0.8354 |
| ridge                                          |            62 |      0.02311  |          0.08746 |                     -0.006054  |    0.9948 |                0.448  |                        7.859 |              0.2907 |       0.8471 |
| ridge                                          |            64 |      0.01122  |          0.05994 |                      0.01646   |    0.9881 |                0.4419 |                        7.811 |              0.4186 |       0.9032 |
| ridge                                          |            65 |      0.02606  |          0.08134 |                      0.02118   |    0.9942 |                0.4603 |                        8.31  |              0.3256 |       0.8148 |
| saturation_residual_fusion_new                 |            58 |      0.02214  |          0.07279 |                     -0.01905   |    0.9959 |                0.4617 |                        5.328 |              0.3256 |       0.5185 |
| saturation_residual_fusion_new                 |            60 |      0.009105 |          0.08853 |                      0.01703   |    0.9941 |                0.4838 |                        7.102 |              0.2791 |       0.4568 |
| saturation_residual_fusion_new                 |            62 |      0.009055 |          0.07704 |                     -0.02066   |    0.9939 |                0.4516 |                        4.679 |              0.3372 |       0.5595 |
| saturation_residual_fusion_new                 |            64 |     -0.0135   |          0.06714 |                      0.03109   |    0.9911 |                0.447  |                        4.989 |              0.3837 |       0.5909 |
| saturation_residual_fusion_new                 |            65 |      0.01239  |          0.07143 |                      0.01396   |    1      |                0.4632 |                        6.082 |              0.3488 |       0.5769 |
| tiny_sequence_transformer                      |            58 |      0.02717  |          0.1113  |                      0.04045   |    0.9937 |                0.4644 |                       11.52  |              0.2558 |       0.9231 |
| tiny_sequence_transformer                      |            60 |      0.02828  |          0.1277  |                      0.06814   |    0.9941 |                0.4763 |                       13.74  |              0.3721 |       0.9125 |
| tiny_sequence_transformer                      |            62 |      0.04165  |          0.1234  |                     -0.002129  |    0.9818 |                0.4473 |                       15.26  |              0.3372 |       0.9405 |
| tiny_sequence_transformer                      |            64 |      0.004675 |          0.1036  |                      0.07768   |    0.9985 |                0.4518 |                       16.33  |              0.3605 |       0.9583 |
| tiny_sequence_transformer                      |            65 |      0.008195 |          0.1224  |                      0.05958   |    0.9942 |                0.4546 |                       15.9   |              0.3605 |       0.961  |

## Failure Maps

| stratum          | value             | method                                         |   energy_bias |   energy_sigma68 |   pedestal_high_minus_low_bias |   pid_auc |   pid_calibration_ece |   timing_residual_sigma68_ns |   pileup_merge_rate |   coverage90 |
|:-----------------|:------------------|:-----------------------------------------------|--------------:|-----------------:|-------------------------------:|----------:|----------------------:|-----------------------------:|--------------------:|-------------:|
| pedestal_state   | nominal           | 1d_cnn                                         |    -0.005808  |          0.07744 |                    nan         |    0.995  |              0.4414   |                       8.763  |             0.3333  |       0.993  |
| pedestal_state   | shifted           | 1d_cnn                                         |     0.02675   |          0.1265  |                    nan         |    0.987  |              0.4776   |                      10.33   |             0.3105  |       0.8582 |
| pileup_bin       | clean             | 1d_cnn                                         |     0.07102   |          0.152   |                      0.09843   |    0.9871 |              0.4154   |                       8.737  |           nan       |       0.7903 |
| pileup_bin       | pileup            | 1d_cnn                                         |     0.00251   |          0.09079 |                      0.01944   |    0.9855 |              0.5139   |                       9.961  |             0.3186  |       0.9522 |
| clip_bin         | hard_clip         | 1d_cnn                                         |    -0.1813    |          0.01224 |                     -0.036     |  nan      |              0.03538  |                       0.1868 |             0       |       1      |
| clip_bin         | mild_clip         | 1d_cnn                                         |    -0.04672   |          0.06505 |                      0.08337   |    0.3    |              0.2501   |                       4.67   |             0       |       1      |
| clip_bin         | unclipped         | 1d_cnn                                         |     0.01158   |          0.1088  |                      0.03662   |    0.9894 |              0.4676   |                      10.11   |             0.3254  |       0.902  |
| morphology_state | late_tail_high    | 1d_cnn                                         |     0.008649  |          0.08538 |                      0.002237  |    0.9901 |              0.4503   |                       8.999  |             0.4225  |       0.9733 |
| morphology_state | late_tail_low     | 1d_cnn                                         |     0.01207   |          0.1292  |                      0.05884   |    0.989  |              0.4794   |                      10.86   |             0.2387  |       0.8652 |
| stave            | B2                | 1d_cnn                                         |    -0.005287  |          0.1716  |                      0.09531   |    0.9833 |              0.4855   |                      11.09   |             0.4563  |       0.8395 |
| stave            | B4                | 1d_cnn                                         |     0.05066   |          0.1291  |                      0.08326   |    0.9978 |              0.4605   |                      10.73   |             0.2846  |       0.8167 |
| stave            | B6                | 1d_cnn                                         |     0.008008  |          0.0839  |                      0.03484   |  nan      |              0.4384   |                       7.796  |             0.3704  |       0.9694 |
| stave            | B8                | 1d_cnn                                         |     0.002127  |          0.07373 |                      0.00743   |  nan      |              0.4741   |                       8.807  |             0.1562  |       0.9831 |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |    -0.04232   |          0.079   |                      0.08519   |  nan      |              0.08322  |                       4.735  |             0.07407 |       0.9615 |
| pid_proxy_class  | other             | 1d_cnn                                         |     0.01425   |          0.109   |                      0.03999   |  nan      |              0.4838   |                       9.846  |             0.335   |       0.9003 |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |     0.06072   |          0.09689 |                    nan         |    0.5254 |              0.789    |                       6.058  |             0.4379  |       0.9225 |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |     0.07528   |          0.122   |                    nan         |    0.5794 |              0.6431   |                       7.498  |             0.6498  |       0.8551 |
| pileup_bin       | clean             | analytic_clipped_template_sideband_traditional |     0.09496   |          0.1474  |                      0.04679   |    0.5549 |              0.6907   |                       6.467  |           nan       |       0.75   |
| pileup_bin       | pileup            | analytic_clipped_template_sideband_traditional |     0.05761   |          0.08585 |                      0.005131  |    0.516  |              0.7      |                       8.112  |             0.5744  |       0.9508 |
| clip_bin         | hard_clip         | analytic_clipped_template_sideband_traditional |     0.2001    |          0.01959 |                      0.05762   |  nan      |              0        |                       0.4693 |             0       |       1      |
| clip_bin         | mild_clip         | analytic_clipped_template_sideband_traditional |     0.1276    |          0.02516 |                      0.001379  |    0.65   |              0.1429   |                       5.02   |             0.2857  |       1      |
| clip_bin         | unclipped         | analytic_clipped_template_sideband_traditional |     0.06422   |          0.1108  |                      0.01253   |    0.4999 |              0.7015   |                       7.466  |             0.5819  |       0.8846 |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |     0.1234    |          0.1481  |                     -0.01151   |    0.3493 |              0.6296   |                       5.971  |             0.7326  |       0.7375 |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |     0.05192   |          0.08617 |                      0.01489   |    0.572  |              0.763    |                       7.884  |             0.4527  |       0.9519 |
| stave            | B2                | analytic_clipped_template_sideband_traditional |     0.1137    |          0.08461 |                      0.008841  |    0.6484 |              0.6256   |                       8.435  |             0.6408  |       0.9074 |
| stave            | B4                | analytic_clipped_template_sideband_traditional |     0.01704   |          0.1148  |                      0.01691   |    0.4136 |              0.6116   |                      13.55   |             0.7561  |       1      |
| stave            | B6                | analytic_clipped_template_sideband_traditional |     0.00584   |          0.04781 |                     -0.01077   |  nan      |              0.6947   |                       6.245  |             0.5093  |       1      |
| stave            | B8                | analytic_clipped_template_sideband_traditional |     0.1281    |          0.139   |                      0.06707   |  nan      |              0.8652   |                       3.738  |             0.3438  |       0.7396 |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |     0.1242    |          0.05796 |                     -0.01958   |  nan      |              0.2241   |                       5.399  |             0.4815  |       1      |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |     0.06291   |          0.1118  |                      0.01289   |  nan      |              0.7274   |                       7.379  |             0.5806  |       0.881  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |     0.007855  |          0.06571 |                    nan         |    0.9956 |              0.4491   |                       4.958  |             0.3464  |       0.6565 |
| pedestal_state   | shifted           | gradient_boosted_trees                         |     0.002761  |          0.08982 |                    nan         |    0.9927 |              0.4699   |                       5.368  |             0.3069  |       0.5946 |
| pileup_bin       | clean             | gradient_boosted_trees                         |     0.04139   |          0.09841 |                      0.01789   |    0.9988 |              0.4131   |                       5.497  |           nan       |       0.5408 |
| pileup_bin       | pileup            | gradient_boosted_trees                         |    -0.008198  |          0.0663  |                     -0.01334   |    0.9889 |              0.5118   |                       4.865  |             0.3209  |       0.6404 |
| clip_bin         | hard_clip         | gradient_boosted_trees                         |     0.003369  |          0.01009 |                     -0.02968   |  nan      |              0.009946 |                       0.7411 |             0       |       1      |
| clip_bin         | mild_clip         | gradient_boosted_trees                         |    -0.01902   |          0.0534  |                      0.08258   |    0.4    |              0.2624   |                       4.783  |             0       |       0.7143 |
| clip_bin         | unclipped         | gradient_boosted_trees                         |     0.006483  |          0.07673 |                     -0.004669  |    0.9946 |              0.4652   |                       5.141  |             0.3278  |       0.6115 |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |     0.01108   |          0.06762 |                      0.007604  |    0.9945 |              0.4496   |                       5.799  |             0.4225  |       0.6549 |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |     0.002073  |          0.08879 |                     -0.01039   |    0.9929 |              0.4757   |                       5.028  |             0.2428  |       0.5927 |
| stave            | B2                | gradient_boosted_trees                         |    -0.01133   |          0.1151  |                      0.02621   |    0.9924 |              0.4848   |                       7.449  |             0.4078  |       0.4767 |
| stave            | B4                | gradient_boosted_trees                         |     0.01779   |          0.07654 |                      0.008579  |    1      |              0.4494   |                       5.819  |             0.2602  |       0.6466 |
| stave            | B6                | gradient_boosted_trees                         |     0.0001828 |          0.05909 |                     -0.02319   |  nan      |              0.4404   |                       3.804  |             0.3889  |       0.6829 |
| stave            | B8                | gradient_boosted_trees                         |     0.00916   |          0.06514 |                      0.005461  |  nan      |              0.4764   |                       4.315  |             0.2292  |       0.6415 |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |    -0.01147   |          0.08779 |                     -0.02365   |  nan      |              0.0647   |                       4.465  |             0.03704 |       0.5926 |
| pid_proxy_class  | other             | gradient_boosted_trees                         |     0.006672  |          0.07559 |                     -0.00113   |  nan      |              0.4809   |                       5.103  |             0.34    |       0.6171 |
| pedestal_state   | nominal           | mlp                                            |    -0.01094   |          0.09884 |                    nan         |    0.9961 |              0.4487   |                       6.667  |             0.3725  |       0.9167 |
| pedestal_state   | shifted           | mlp                                            |    -0.001567  |          0.171   |                    nan         |    0.9771 |              0.4743   |                      10.45   |             0.3863  |       0.7637 |
| pileup_bin       | clean             | mlp                                            |     0.05937   |          0.2072  |                      0.06425   |    0.9895 |              0.4222   |                      10.96   |           nan       |       0.6893 |
| pileup_bin       | pileup            | mlp                                            |    -0.01533   |          0.1238  |                     -0.00106   |    0.9786 |              0.5081   |                       8.569  |             0.3814  |       0.8684 |
| clip_bin         | hard_clip         | mlp                                            |    -0.02791   |          0.02538 |                      0.07466   |  nan      |              0.01855  |                       2.67   |             0       |       1      |
| clip_bin         | mild_clip         | mlp                                            |    -0.0633    |          0.04256 |                      0.05102   |    0.7    |              0.2488   |                       2.737  |             0.1429  |       1      |
| clip_bin         | unclipped         | mlp                                            |    -0.003322  |          0.1523  |                      0.01308   |    0.9822 |              0.4681   |                       9.566  |             0.3872  |       0.8144 |
| morphology_state | late_tail_high    | mlp                                            |    -0.01176   |          0.1124  |                     -0.05987   |    0.9883 |              0.4481   |                       7.575  |             0.508   |       0.88   |
| morphology_state | late_tail_low     | mlp                                            |    -0.002675  |          0.1654  |                      0.02506   |    0.9811 |              0.4826   |                       9.818  |             0.284   |       0.7869 |
| stave            | B2                | mlp                                            |     0.00342   |          0.2527  |                      0.08893   |    0.9556 |              0.4944   |                      11.14   |             0.5631  |       0.6557 |
| stave            | B4                | mlp                                            |     0.03362   |          0.1722  |                      0.07272   |    0.9989 |              0.4551   |                      11.87   |             0.3577  |       0.7719 |
| stave            | B6                | mlp                                            |    -0.04159   |          0.1255  |                     -0.06567   |  nan      |              0.4401   |                       8.141  |             0.3704  |       0.9121 |
| stave            | B8                | mlp                                            |    -0.008482  |          0.1144  |                     -0.04556   |  nan      |              0.4713   |                       7.906  |             0.2292  |       0.8835 |
| pid_proxy_class  | inner_high_charge | mlp                                            |    -0.008272  |          0.09708 |                      0.06281   |  nan      |              0.08487  |                       6.175  |             0.1852  |       0.9565 |
| pid_proxy_class  | other             | mlp                                            |    -0.006437  |          0.1535  |                      0.009088  |  nan      |              0.4843   |                       9.597  |             0.3945  |       0.8092 |
| pedestal_state   | nominal           | ridge                                          |     0.01651   |          0.06548 |                    nan         |    0.9956 |              0.44     |                       6.66   |             0.3399  |       0.9154 |
| pedestal_state   | shifted           | ridge                                          |     0.02754   |          0.08854 |                    nan         |    0.9896 |              0.4644   |                       8.369  |             0.3069  |       0.8403 |
| pileup_bin       | clean             | ridge                                          |     0.05387   |          0.09957 |                     -0.003366  |    0.993  |              0.4039   |                       6.603  |           nan       |       0.71   |
| pileup_bin       | pileup            | ridge                                          |     0.01406   |          0.07413 |                      0.01392   |    0.9897 |              0.5073   |                       7.591  |             0.3186  |       0.9181 |
| clip_bin         | hard_clip         | ridge                                          |    -0.06253   |          0.01214 |                     -0.03571   |  nan      |              0.02098  |                       0.2017 |             0       |       1      |
| clip_bin         | mild_clip         | ridge                                          |    -0.03332   |          0.0357  |                      0.04267   |    0.6    |              0.2516   |                       5.953  |             0       |       1      |
| clip_bin         | unclipped         | ridge                                          |     0.02588   |          0.08371 |                      0.01228   |    0.9926 |              0.4584   |                       7.914  |             0.3254  |       0.862  |
| morphology_state | late_tail_high    | ridge                                          |     0.02218   |          0.06878 |                      0.01176   |    0.9886 |              0.4406   |                       6.279  |             0.4118  |       0.9085 |
| morphology_state | late_tail_low     | ridge                                          |     0.02212   |          0.09159 |                      0.01185   |    0.9942 |              0.4711   |                       8.327  |             0.2469  |       0.8406 |
| stave            | B2                | ridge                                          |    -0.01809   |          0.09299 |                      0.02165   |    0.9887 |              0.4656   |                       9.114  |             0.4272  |       0.8605 |
| stave            | B4                | ridge                                          |     0.03708   |          0.06456 |                      0.00756   |    1      |              0.4486   |                       8.667  |             0.252   |       0.8814 |
| stave            | B6                | ridge                                          |     0.02076   |          0.05702 |                      0.009937  |  nan      |              0.4389   |                       5.258  |             0.3796  |       0.9036 |
| stave            | B8                | ridge                                          |     0.03839   |          0.09187 |                      0.02463   |  nan      |              0.4763   |                       5.402  |             0.2188  |       0.8208 |
| pid_proxy_class  | inner_high_charge | ridge                                          |    -0.02324   |          0.06776 |                      8.745e-05 |  nan      |              0.08059  |                       5.422  |             0       |       1      |
| pid_proxy_class  | other             | ridge                                          |     0.0267    |          0.08468 |                      0.01312   |  nan      |              0.4743   |                       8.016  |             0.34    |       0.8544 |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |     0.008315  |          0.06417 |                    nan         |    0.9978 |              0.449    |                       5.188  |             0.3987  |       0.622  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |     0.01047   |          0.09238 |                    nan         |    0.9924 |              0.4684   |                       5.873  |             0.2996  |       0.4981 |
| pileup_bin       | clean             | saturation_residual_fusion_new                 |     0.04562   |          0.09633 |                      0.03755   |    0.9977 |              0.4118   |                       5.082  |           nan       |       0.5    |
| pileup_bin       | pileup            | saturation_residual_fusion_new                 |    -0.008722  |          0.07312 |                     -0.01108   |    0.989  |              0.5111   |                       4.986  |             0.3349  |       0.5524 |
| clip_bin         | hard_clip         | saturation_residual_fusion_new                 |     0.04047   |          0.01992 |                     -0.05858   |  nan      |              0.007478 |                       0.6447 |             0       |       0.5    |
| clip_bin         | mild_clip         | saturation_residual_fusion_new                 |     0.04502   |          0.04306 |                      0.08043   |    0.6    |              0.2677   |                       4.536  |             0       |       0.8571 |
| clip_bin         | unclipped         | saturation_residual_fusion_new                 |     0.0088    |          0.08144 |                      0.0009963 |    0.9944 |              0.4641   |                       5.86   |             0.342   |       0.5328 |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |     0.0124    |          0.07026 |                      0.01049   |    0.9933 |              0.4484   |                       6.525  |             0.4171  |       0.5772 |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |     0.00525   |          0.08691 |                     -0.004581  |    0.9935 |              0.4749   |                       5.201  |             0.2716  |       0.5145 |
| stave            | B2                | saturation_residual_fusion_new                 |    -0.01014   |          0.1213  |                      0.03118   |    0.9919 |              0.4808   |                       7.457  |             0.3786  |       0.4505 |
| stave            | B4                | saturation_residual_fusion_new                 |     0.02503   |          0.0731  |                      0.007504  |    1      |              0.4504   |                       6.795  |             0.2683  |       0.5333 |
| stave            | B6                | saturation_residual_fusion_new                 |    -0.01573   |          0.06111 |                     -0.02146   |  nan      |              0.4399   |                       4.136  |             0.4074  |       0.6203 |
| stave            | B8                | saturation_residual_fusion_new                 |     0.01031   |          0.07473 |                      0.005393  |  nan      |              0.4757   |                       3.571  |             0.2917  |       0.56   |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |     0.01102   |          0.06191 |                     -0.003289  |  nan      |              0.06405  |                       5.066  |             0.07407 |       0.5769 |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |     0.008902  |          0.08048 |                      0.002324  |  nan      |              0.4798   |                       5.844  |             0.3524  |       0.5357 |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |    -0.00504   |          0.1071  |                    nan         |    0.9956 |              0.4394   |                      15.52   |             0.3595  |       0.9856 |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |     0.03742   |          0.1209  |                    nan         |    0.9868 |              0.469    |                      13.85   |             0.3249  |       0.9132 |
| pileup_bin       | clean             | tiny_sequence_transformer                      |     0.07324   |          0.116   |                      0.05284   |    0.9918 |              0.412    |                      15.68   |           nan       |       0.8739 |
| pileup_bin       | pileup            | tiny_sequence_transformer                      |     0.002395  |          0.1169  |                      0.03274   |    0.9836 |              0.5048   |                      12.79   |             0.3372  |       0.9649 |
| clip_bin         | hard_clip         | tiny_sequence_transformer                      |    -0.1651    |          0.0218  |                     -0.06412   |  nan      |              0.04323  |                       0.7949 |             0       |       1      |
| clip_bin         | mild_clip         | tiny_sequence_transformer                      |    -0.01526   |          0.06774 |                      0.1127    |    0.1    |              0.2455   |                       3.364  |             0       |       1      |
| clip_bin         | unclipped         | tiny_sequence_transformer                      |     0.02509   |          0.1182  |                      0.04537   |    0.9897 |              0.4613   |                      14.96   |             0.3444  |       0.9367 |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |     0.04185   |          0.1036  |                      0.0007156 |    0.995  |              0.4532   |                      19.68   |             0.4385  |       0.9732 |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |     0.003912  |          0.1262  |                      0.06964   |    0.9863 |              0.4637   |                      11.07   |             0.2593  |       0.9176 |
| stave            | B2                | tiny_sequence_transformer                      |     0.01589   |          0.1617  |                      0.1166    |    0.9818 |              0.4814   |                      11.71   |             0.4078  |       0.8471 |
| stave            | B4                | tiny_sequence_transformer                      |     0.006601  |          0.1086  |                      0.02566   |    0.9989 |              0.4405   |                      14.52   |             0.4065  |       0.9388 |
| stave            | B6                | tiny_sequence_transformer                      |     0.02987   |          0.1001  |                      0.06357   |  nan      |              0.4417   |                      14.78   |             0.3333  |       0.9802 |
| stave            | B8                | tiny_sequence_transformer                      |     0.03207   |          0.1048  |                      0.026     |  nan      |              0.4715   |                      16.97   |             0.1771  |       0.9667 |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |    -0.01285   |          0.09603 |                      0.09163   |  nan      |              0.08559  |                       7.82   |             0.07407 |       0.9615 |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |     0.0275    |          0.1176  |                      0.04765   |  nan      |              0.4774   |                      15.08   |             0.3548  |       0.9365 |

## Systematics and Caveats

The energy, pile-up, saturation, and timing truths are controlled-injection
truths built from raw-ROOT clean pulses, not hand-labeled beam truth.  Saturation
knee is a high-amplitude ADC proxy rather than a decoded electronics flag.  The
PID endpoint is a charge/support proxy; it is useful for boundary-transfer
stress testing but must not be read as an external species classifier.  Bootstrap
resampling is by held-out run block, so intervals represent run-transfer
stability rather than independent event-counting precision.  The 18-sample
waveform limits transformer capacity; the attention model is included as a
compact temporal encoder, not a large-sequence architecture.

## Verdict

`result.json` names **`gradient_boosted_trees`** as the S40c winner.  The result supports the
new hybrid residual-fusion method for this declared transfer score, while the
traditional clipped-template method remains the auditable physics baseline and
the PID conclusion remains proxy-limited.

Runtime was `72.8` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

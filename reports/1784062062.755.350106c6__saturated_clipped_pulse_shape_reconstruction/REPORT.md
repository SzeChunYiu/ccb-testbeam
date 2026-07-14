# S33a: Saturated and Clipped Pulse-Shape Reconstruction

## Abstract

Ticket `1784062062.755.350106c6` asks for saturated and clipped calorimeter waveform
reconstruction from raw ROOT data, comparing a strong traditional method against
ridge, gradient-boosted trees, MLP, 1D-CNN, and a sensible new architecture.  The
benchmark also includes a transformer encoder because the waveform is a short
ordered sequence.  The winner is **`ridge`**, selected by a predeclared
composite pulse-shape score on held-out runs.  Its score is
`0.1153` with recovered-energy sigma68
`0.06667` and 95% run-bootstrap CI
[`0.05429`, `0.07653`].

## Raw ROOT Reproduction Gate

Raw B-stack files are read from `/home/billy/.tb-workers/testbeam-laptop-2/data/root/root`.  For each run, the
`h101/HRDv` branch is reshaped to `(event, channel, sample)` with 18 samples per
channel.  The project selection uses B2/B4/B6/B8, baseline

`b_ec = median_{t in {0,1,2,3}} x_ect`,

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

The reproduced number is the analysis anchor before model fitting:

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Controlled Saturation Benchmark

Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Clean pulse templates are estimated only
from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              880 |                   2.677 |                      5 |           9.108 |
| B4      |              854 |                   3.009 |                      6 |          10.82  |
| B6      |              821 |                   3.762 |                      8 |           9.825 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

Doublet truth is generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a residual sampled from raw-ROOT clean pulses with the
same source run and stave.  The observed waveform passed to every method is
clipped:

`w_obs(t) = min(w(t), 11800)`.

Clean single-pulse controls are generated from the same source-run distribution
and are clipped by the same rule, making false splitting a direct negative
control.

## Methods

The traditional comparator is **analytic_clipped_template_sideband_traditional**.
It fits one- and two-pulse template models by bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

then applies a deterministic saturation sideband correction using clipped-sample
count, plateau width, and late-tail fraction.  The ML panel contains ridge,
histogram gradient-boosted trees, MLP, compact 1D-CNN, and
`tiny_sequence_transformer`.  The new architecture is
**saturation_residual_fusion_new**, a residual-fusion boosted model that
concatenates waveform summaries, clipping sidebands, and the analytic fit output
before learning residual corrections.

## Endpoints and Uncertainty

For accepted injected doublets, the study evaluates four ticket endpoints:

`e_A = ((hat A_1 + hat A_2) - (A_1 + A_2))/(A_1 + A_2)`,

`e_W = W50(hat w) - W50(w)`,

`e_T = f_tail(hat w) - f_tail(w)`,

`e_E = (area(hat w) - area(w))/area(w)`.

Here `W50` is the sample count above half maximum and `f_tail` is the fraction of
area in samples 10--17.  Robust resolution is

`sigma68(e) = [Q84(e)-Q16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`400` held-out run-block bootstrap resamples.
The winner minimizes

`C = sigma_E + 0.20 sigma_A + 0.08 sigma_T + 0.015 sigma_W + 0.03 r_miss + 0.03 r_false`.

## Overall Results

| method                                         |   winner_score |   energy_sigma68 |   energy_sigma68_ci_low |   energy_sigma68_ci_high |   amplitude_sigma68 |   tail_fraction_sigma68 |   width50_sigma68_samples |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|---------------:|-----------------:|------------------------:|-------------------------:|--------------------:|------------------------:|--------------------------:|-------------------:|-------------------:|
| ridge                                          |         0.1153 |          0.06667 |                 0.05429 |                  0.07653 |             0.07166 |                 0.05239 |                      1    |             0.3095 |             0.1929 |
| saturation_residual_fusion_new                 |         0.1215 |          0.07322 |                 0.0696  |                  0.0814  |             0.07762 |                 0.04459 |                      1    |             0.3095 |             0.1643 |
| gradient_boosted_trees                         |         0.1247 |          0.07638 |                 0.06919 |                  0.08172 |             0.07454 |                 0.04686 |                      1    |             0.3167 |             0.1738 |
| 1d_cnn                                         |         0.1548 |          0.09704 |                 0.0889  |                  0.1058  |             0.09668 |                 0.0706  |                      1    |             0.3429 |             0.25   |
| mlp                                            |         0.1649 |          0.09851 |                 0.08622 |                  0.123   |             0.1048  |                 0.07894 |                      1.5  |             0.3571 |             0.1952 |
| analytic_clipped_template_sideband_traditional |         0.1694 |          0.1025  |                 0.0833  |                  0.1175  |             0.1047  |                 0.04536 |                      1.34 |             0.5762 |             0.1667 |
| tiny_sequence_transformer                      |         0.2048 |          0.1351  |                 0.1328  |                  0.1437  |             0.09475 |                 0.07458 |                      1.86 |             0.3833 |             0.1786 |

The traditional comparator has score `0.1694` and
recovered-energy sigma68 `0.1025`.  The selected winner
changes recovered-energy sigma68 by
`-0.03579`.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                 0.01922  |                     0.08675 |       -2.614   |             9.776 |             0.3095 |            0.2619  |
| 1d_cnn                                         |            60 |                 0.01695  |                     0.07159 |       -1.71    |            11.81  |             0.2619 |            0.2381  |
| 1d_cnn                                         |            62 |                 0.006319 |                     0.09725 |       -4.297   |            11.66  |             0.3333 |            0.2143  |
| 1d_cnn                                         |            64 |                -0.008859 |                     0.09552 |       -1.75    |            10.99  |             0.3929 |            0.3095  |
| 1d_cnn                                         |            65 |                -0.01947  |                     0.1086  |       -2.714   |             9.752 |             0.4167 |            0.2262  |
| analytic_clipped_template_sideband_traditional |            58 |                 0.09123  |                     0.08386 |        0.3493  |             8.976 |             0.5833 |            0.2262  |
| analytic_clipped_template_sideband_traditional |            60 |                 0.1469   |                     0.1238  |        0.5618  |            11.04  |             0.5595 |            0.09524 |
| analytic_clipped_template_sideband_traditional |            62 |                 0.05687  |                     0.08152 |       -1.421   |            11.96  |             0.6429 |            0.1786  |
| analytic_clipped_template_sideband_traditional |            64 |                 0.05644  |                     0.08359 |        1.992   |             8.65  |             0.5714 |            0.1905  |
| analytic_clipped_template_sideband_traditional |            65 |                 0.05299  |                     0.124   |        1.781   |             7.71  |             0.5238 |            0.1429  |
| gradient_boosted_trees                         |            58 |                 0.004287 |                     0.08503 |       -0.5012  |             8.806 |             0.2262 |            0.2381  |
| gradient_boosted_trees                         |            60 |                 0.004737 |                     0.07775 |       -0.08469 |             7.897 |             0.2738 |            0.1786  |
| gradient_boosted_trees                         |            62 |                -0.01661  |                     0.07341 |       -1.811   |             8.159 |             0.3333 |            0.1548  |
| gradient_boosted_trees                         |            64 |                 0.008387 |                     0.04967 |       -0.682   |             8.012 |             0.3452 |            0.1548  |
| gradient_boosted_trees                         |            65 |                -0.02263  |                     0.07006 |       -2.068   |             9.21  |             0.4048 |            0.1429  |
| mlp                                            |            58 |                 0.03944  |                     0.07966 |        0.5612  |             9.267 |             0.3333 |            0.2381  |
| mlp                                            |            60 |                 0.02947  |                     0.1053  |       -0.9875  |            13.73  |             0.2381 |            0.2381  |
| mlp                                            |            62 |                -0.02249  |                     0.1152  |       -2.464   |            10.3   |             0.3333 |            0.1548  |
| mlp                                            |            64 |                 0.01685  |                     0.08829 |        0.5963  |            12.16  |             0.4405 |            0.1786  |
| mlp                                            |            65 |                -0.01644  |                     0.08664 |       -2.239   |            12.86  |             0.4405 |            0.1667  |
| ridge                                          |            58 |                 0.01937  |                     0.05876 |       -0.4369  |             8.18  |             0.3214 |            0.2619  |
| ridge                                          |            60 |                 0.002584 |                     0.08387 |       -0.5538  |             9.803 |             0.2024 |            0.2024  |
| ridge                                          |            62 |                 0.004217 |                     0.07991 |       -1.047   |             9.291 |             0.2619 |            0.131   |
| ridge                                          |            64 |                -0.001761 |                     0.04885 |       -1.147   |             9.514 |             0.4048 |            0.1786  |
| ridge                                          |            65 |                -0.01851  |                     0.07526 |       -1.877   |            10.44  |             0.3571 |            0.1905  |
| saturation_residual_fusion_new                 |            58 |                -0.002585 |                     0.07822 |       -0.5232  |             7.311 |             0.2857 |            0.2143  |
| saturation_residual_fusion_new                 |            60 |                -0.00214  |                     0.08768 |       -0.08094 |             8.111 |             0.25   |            0.1548  |
| saturation_residual_fusion_new                 |            62 |                -0.001649 |                     0.06875 |       -2.66    |             7.859 |             0.2857 |            0.1548  |
| saturation_residual_fusion_new                 |            64 |                -0.003989 |                     0.07448 |       -0.5713  |             8.403 |             0.3571 |            0.1429  |
| saturation_residual_fusion_new                 |            65 |                -0.02434  |                     0.07302 |       -1.464   |             8.979 |             0.369  |            0.1548  |
| tiny_sequence_transformer                      |            58 |                -0.007797 |                     0.09907 |      -11.37    |            13.91  |             0.2976 |            0.25    |
| tiny_sequence_transformer                      |            60 |                -0.006472 |                     0.09022 |      -11.79    |            15.81  |             0.2857 |            0.1071  |
| tiny_sequence_transformer                      |            62 |                -0.03751  |                     0.09701 |      -14.9     |            14.02  |             0.4286 |            0.1667  |
| tiny_sequence_transformer                      |            64 |                -0.04098  |                     0.09202 |      -14.22    |            14.58  |             0.4524 |            0.2024  |
| tiny_sequence_transformer                      |            65 |                -0.04175  |                     0.09934 |      -14.59    |            16.66  |             0.4524 |            0.1667  |

## Shape Endpoint CIs

| method                                         |   amplitude_bias |   amplitude_sigma68 |   amplitude_sigma68_ci_low |   amplitude_sigma68_ci_high |   width50_bias_samples |   width50_sigma68_samples |   tail_fraction_bias |   tail_fraction_sigma68 |   energy_bias |   energy_sigma68 |
|:-----------------------------------------------|-----------------:|--------------------:|---------------------------:|----------------------------:|-----------------------:|--------------------------:|---------------------:|------------------------:|--------------:|-----------------:|
| ridge                                          |         0.004763 |             0.07166 |                    0.06057 |                     0.08269 |                      0 |                      1    |             0.00182  |                 0.05239 |     -0.001684 |          0.06667 |
| saturation_residual_fusion_new                 |        -0.004759 |             0.07762 |                    0.07165 |                     0.08698 |                      0 |                      1    |            -0.001522 |                 0.04459 |      0.01076  |          0.07322 |
| gradient_boosted_trees                         |        -0.001118 |             0.07454 |                    0.06644 |                     0.08035 |                      0 |                      1    |            -0.000513 |                 0.04686 |      0.01069  |          0.07638 |
| 1d_cnn                                         |         0.007469 |             0.09668 |                    0.08641 |                     0.1043  |                      0 |                      1    |            -0.005117 |                 0.0706  |      0.007612 |          0.09704 |
| mlp                                            |         0.01456  |             0.1048  |                    0.09325 |                     0.1126  |                      0 |                      1.5  |             0.001165 |                 0.07894 |      0.008    |          0.09851 |
| analytic_clipped_template_sideband_traditional |         0.06576  |             0.1047  |                    0.08629 |                     0.1208  |                     -1 |                      1.34 |             0.02771  |                 0.04536 |      0.03711  |          0.1025  |
| tiny_sequence_transformer                      |        -0.0248   |             0.09475 |                    0.09255 |                     0.1005  |                     -1 |                      1.86 |            -0.06535  |                 0.07458 |      0.00442  |          0.1351  |

## Stratified Bootstrap Results

The required stratification is by saturation depth and channel.  Each row reports
the held-out endpoint within a stratum; CI columns are run-block bootstrap
intervals when at least two held-out runs contribute.

| stratum          | value   | method                                         |   energy_sigma68 |   energy_sigma68_ci_low |   energy_sigma68_ci_high |   amplitude_sigma68 |   tail_fraction_sigma68 |   width50_sigma68_samples |
|:-----------------|:--------|:-----------------------------------------------|-----------------:|------------------------:|-------------------------:|--------------------:|------------------------:|--------------------------:|
| saturation_depth | 0       | 1d_cnn                                         |         0.09585  |                 0.08805 |                 0.1059   |            0.0959   |                0.06983  |                      1    |
| saturation_depth | 1-2     | 1d_cnn                                         |         0.03656  |                 0       |                 0.1002   |            0.1238   |                0.07659  |                      1    |
| saturation_depth | 3-5     | 1d_cnn                                         |         0.2548   |                 0       |                 0.2548   |            0.06735  |                0.07218  |                      2.04 |
| saturation_depth | 6+      | 1d_cnn                                         |         0.02804  |                 0       |                 0.02804  |            0.03321  |                0.003881 |                      0    |
| saturation_depth | 0       | analytic_clipped_template_sideband_traditional |         0.1014   |                 0.07993 |                 0.1181   |            0.1033   |                0.045    |                      1    |
| saturation_depth | 1-2     | analytic_clipped_template_sideband_traditional |         0.1679   |                 0       |                 0.1679   |            0.001395 |                0.03605  |                      1.36 |
| saturation_depth | 3-5     | analytic_clipped_template_sideband_traditional |         0.1756   |                 0       |                 0.1756   |            0.05383  |                0.02163  |                      1.36 |
| saturation_depth | 6+      | analytic_clipped_template_sideband_traditional |         0        |                 0       |                 0        |            0        |                0        |                      0    |
| saturation_depth | 0       | gradient_boosted_trees                         |         0.07468  |                 0.06824 |                 0.0813   |            0.07447  |                0.0463   |                      1    |
| saturation_depth | 1-2     | gradient_boosted_trees                         |         0.03595  |                 0       |                 0.03694  |            0.05454  |                0.07551  |                      0.6  |
| saturation_depth | 3-5     | gradient_boosted_trees                         |         0.09771  |                 0       |                 0.09771  |            0.1102   |                0.03806  |                      0.68 |
| saturation_depth | 6+      | gradient_boosted_trees                         |         0.009725 |                 0       |                 0.009725 |            0.008303 |                0.001822 |                      0.34 |
| saturation_depth | 0       | mlp                                            |         0.09767  |                 0.08403 |                 0.1141   |            0.103    |                0.07918  |                      1.5  |
| saturation_depth | 1-2     | mlp                                            |         0.07117  |                 0       |                 0.1026   |            0.09044  |                0.1072   |                      1.3  |
| saturation_depth | 3-5     | mlp                                            |         0.01529  |                 0       |                 0.01529  |            0.04868  |                0.07851  |                      0.68 |
| saturation_depth | 6+      | mlp                                            |         0.02646  |                 0       |                 0.02646  |            0.009258 |                0.0321   |                      0.34 |
| saturation_depth | 0       | ridge                                          |         0.06608  |                 0.05332 |                 0.07611  |            0.06902  |                0.05168  |                      1    |
| saturation_depth | 1-2     | ridge                                          |         0.0433   |                 0       |                 0.109    |            0.04989  |                0.08302  |                      0.2  |
| saturation_depth | 3-5     | ridge                                          |         0.2792   |                 0       |                 0.2792   |            0.07397  |                0.1546   |                      2.38 |
| saturation_depth | 6+      | ridge                                          |         0.0202   |                 0       |                 0.0202   |            0.01443  |                0.01077  |                      0.34 |
| saturation_depth | 0       | saturation_residual_fusion_new                 |         0.07138  |                 0.06632 |                 0.08136  |            0.07573  |                0.04285  |                      1    |
| saturation_depth | 1-2     | saturation_residual_fusion_new                 |         0.05426  |                 0       |                 0.06077  |            0.05217  |                0.07599  |                      0.7  |
| saturation_depth | 3-5     | saturation_residual_fusion_new                 |         0.0892   |                 0       |                 0.0892   |            0.1123   |                0.03994  |                      1.02 |
| saturation_depth | 6+      | saturation_residual_fusion_new                 |         0.01114  |                 0       |                 0.01114  |            0.009283 |                0.002478 |                      0.34 |
| saturation_depth | 0       | tiny_sequence_transformer                      |         0.1336   |                 0.1266  |                 0.1497   |            0.0937   |                0.07623  |                      2    |
| saturation_depth | 1-2     | tiny_sequence_transformer                      |         0.06116  |                 0       |                 0.06987  |            0.09032  |                0.04978  |                      0.78 |
| saturation_depth | 3-5     | tiny_sequence_transformer                      |         0.2356   |                 0       |                 0.2356   |            0.09792  |                0.02984  |                      2.04 |
| saturation_depth | 6+      | tiny_sequence_transformer                      |         0.00982  |                 0       |                 0.00982  |            0.001943 |                0.004304 |                      0    |
| channel          | B2      | 1d_cnn                                         |         0.1649   |                 0.1295  |                 0.3036   |            0.1228   |                0.0701   |                      1.5  |
| channel          | B4      | 1d_cnn                                         |         0.09477  |                 0.09091 |                 0.127    |            0.07921  |                0.06447  |                      1    |
| channel          | B6      | 1d_cnn                                         |         0.07916  |                 0.06283 |                 0.09244  |            0.08198  |                0.04994  |                      1    |
| channel          | B8      | 1d_cnn                                         |         0.06491  |                 0.05815 |                 0.07459  |            0.08297  |                0.04411  |                      1    |
| channel          | B2      | analytic_clipped_template_sideband_traditional |         0.1523   |                 0.1036  |                 0.2325   |            0.06702  |                0.05586  |                      2.5  |
| channel          | B4      | analytic_clipped_template_sideband_traditional |         0.06831  |                 0.05307 |                 0.1156   |            0.1164   |                0.03133  |                      1    |
| channel          | B6      | analytic_clipped_template_sideband_traditional |         0.06157  |                 0.04849 |                 0.09118  |            0.05789  |                0.02174  |                      1    |
| channel          | B8      | analytic_clipped_template_sideband_traditional |         0.07836  |                 0.06573 |                 0.09968  |            0.1132   |                0.02222  |                      0.5  |
| channel          | B2      | gradient_boosted_trees                         |         0.08659  |                 0.05786 |                 0.2512   |            0.0801   |                0.05683  |                      1    |
| channel          | B4      | gradient_boosted_trees                         |         0.06912  |                 0.05889 |                 0.0887   |            0.07961  |                0.04121  |                      1    |
| channel          | B6      | gradient_boosted_trees                         |         0.06427  |                 0.04678 |                 0.08432  |            0.06575  |                0.03505  |                      1    |
| channel          | B8      | gradient_boosted_trees                         |         0.05461  |                 0.04509 |                 0.06506  |            0.06577  |                0.02914  |                      1    |
| channel          | B2      | mlp                                            |         0.1382   |                 0.09414 |                 0.2813   |            0.1371   |                0.104    |                      2    |
| channel          | B4      | mlp                                            |         0.108    |                 0.07312 |                 0.1521   |            0.1107   |                0.06427  |                      1    |
| channel          | B6      | mlp                                            |         0.07947  |                 0.05169 |                 0.09487  |            0.07495  |                0.06415  |                      1.5  |
| channel          | B8      | mlp                                            |         0.074    |                 0.05638 |                 0.09819  |            0.09145  |                0.05972  |                      1    |
| channel          | B2      | ridge                                          |         0.119    |                 0.08569 |                 0.1427   |            0.08637  |                0.06972  |                      1    |
| channel          | B4      | ridge                                          |         0.0503   |                 0.04337 |                 0.07416  |            0.05195  |                0.03874  |                      1    |
| channel          | B6      | ridge                                          |         0.06104  |                 0.0367  |                 0.0822   |            0.06858  |                0.02426  |                      1    |
| channel          | B8      | ridge                                          |         0.05346  |                 0.04103 |                 0.07743  |            0.06892  |                0.03248  |                      1    |
| channel          | B2      | saturation_residual_fusion_new                 |         0.1075   |                 0.08026 |                 0.2117   |            0.1      |                0.06486  |                      1.5  |
| channel          | B4      | saturation_residual_fusion_new                 |         0.08119  |                 0.06714 |                 0.08598  |            0.07771  |                0.03462  |                      1    |
| channel          | B6      | saturation_residual_fusion_new                 |         0.05253  |                 0.03748 |                 0.06721  |            0.05256  |                0.03339  |                      0.94 |
| channel          | B8      | saturation_residual_fusion_new                 |         0.05951  |                 0.04743 |                 0.07065  |            0.08245  |                0.03116  |                      1    |
| channel          | B2      | tiny_sequence_transformer                      |         0.2835   |                 0.2375  |                 0.3463   |            0.1264   |                0.09222  |                      2    |
| channel          | B4      | tiny_sequence_transformer                      |         0.1679   |                 0.1081  |                 0.2106   |            0.08065  |                0.09719  |                      1.5  |
| channel          | B6      | tiny_sequence_transformer                      |         0.1188   |                 0.1018  |                 0.1343   |            0.08799  |                0.05233  |                      1.2  |
| channel          | B8      | tiny_sequence_transformer                      |         0.08412  |                 0.06392 |                 0.1013   |            0.07961  |                0.05321  |                      1.02 |

## Systematics and Caveats

The truth labels are controlled overlays into raw-ROOT-derived clean pulses, so
they test reconstruction under known saturation and clipping but not the true
beam pile-up rate.  The clipping ceiling is an explicit stressor rather than a
decoded electronics flag.  Template drift is a real transfer effect because
held-out runs are excluded from template estimation and ML training.  Only 18
samples are available, making sub-sample separations and late tails partly
degenerate.  Bootstrap CIs resample held-out runs, so they represent run-transfer
uncertainty rather than event-counting precision.

## Verdict

`result.json` names **ridge** as the winner.  It is preferred for saturated
and clipped controlled-overlay pulse-shape reconstruction under the declared
score.  The analytic clipped-template method remains the auditable deterministic
fallback when transparent extrapolation is required.

Runtime was `103.4` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

# Issue #2495 S55c: Pedestal-Pileup PID Boundary Stability and Energy Transfer Audit

## Abstract

This study tests whether pedestal memory and unresolved pile-up shift PID-proxy
boundaries or energy-transfer functions after conventional correction.  The
analysis starts from raw ROOT, reproduces the canonical selected-pulse count,
then benchmarks a strong traditional correction against ridge, gradient-boosted
trees, MLP, 1D-CNN, a tabular-plus-waveform transformer, and a new hybrid
residual-fusion architecture.  The winner named in `result.json` is
**`gradient_boosted_trees`**, with composite score `0.1581`, energy
sigma68 `0.06608` and 95% run-bootstrap CI
[`0.05949`,
`0.0788`].

## Raw ROOT Reproduction Gate

Raw B-stack files are read from `/home/billy/ccb-data/data/extracted/root/root`.  Each `h101/HRDv`
waveform is reshaped to `(event, channel, sample)` with 18 samples.  The gate
uses B2/B4/B6/B8 even channels, pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`,

and selection

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split and Truth Construction

The split is by source run, not by row.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]`; held-out runs are
`[58, 60, 62, 64, 65]`.  Clean pulse templates are estimated only
from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              864 |                   2.677 |                      5 |           9.108 |
| B4      |              840 |                   2.991 |                      6 |          10.8   |
| B6      |              807 |                   3.764 |                      8 |           9.834 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

Controlled doublets are injected into raw-ROOT-derived residuals:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

then clipped as `w_obs(t) = min(w(t), 11800)`.  Clean single-pulse
controls are drawn from the same run/stave distribution, so false pile-up
splitting is a matched negative-control endpoint.

## Methods

| method                                         | family                            | description                                                                                                             |
|:-----------------------------------------------|:----------------------------------|:------------------------------------------------------------------------------------------------------------------------|
| analytic_clipped_template_sideband_traditional | traditional                       | pedestal-subtracted constrained two-pulse template, charge-ratio/DeltaE-E proxy cuts, CFD timing, run-offset correction |
| ridge                                          | linear ML                         | ridge classifier plus multi-output ridge regression                                                                     |
| gradient_boosted_trees                         | tree ML                           | histogram gradient-boosted classifier and regressors                                                                    |
| mlp                                            | neural network                    | tabular multilayer perceptron classifier/regressor pair                                                                 |
| 1d_cnn                                         | neural network                    | compact one-dimensional CNN over the 18 ADC samples                                                                     |
| tiny_sequence_transformer                      | tabular-plus-waveform transformer | one-layer attention encoder over waveform samples                                                                       |
| saturation_residual_fusion_new                 | new hybrid                        | boosted residual fusion of waveform, clipping sidebands, and traditional-fit outputs                                    |

The traditional comparator is a bounded template fit with pedestal subtraction,
CFD-derived timing, charge-ratio/DeltaE-E style PID proxies, and an empirical
clipping sideband correction:

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`.

The new architecture, `saturation_residual_fusion_new`, is sensible because the
task is hybrid: the traditional fit identifies constituents, while clipped
sidebands, pedestal-window features, and waveform summaries carry residual
information hidden above the ADC ceiling.

## Metrics

Energy residual:

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Pile-up timing separation error:

`e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`.

Robust resolution:

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

Calibration is evaluated on held-out pile-up probability scores.  For bins
`B_m`, expected calibration error is

`ECE = sum_m |B_m|/N * |mean_{i in B_m} y_i - mean_{i in B_m} p_i|`.

The registered winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.004 sigma_Delta + 0.004 sigma_t1 + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`.

Confidence intervals are percentile 95% intervals from
`450` held-out run-block bootstrap resamples.

## Overall Results

| method                                         |   winner_score |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   pileup_separation_sigma68_ns |   leading_timing_shift_sigma68_ns |   pileup_miss_rate |   false_split_rate |   pedestal_shift_false_split_span |   pid_energy_bias_span |
|:-----------------------------------------------|---------------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|-------------------------------:|----------------------------------:|-------------------:|-------------------:|----------------------------------:|-----------------------:|
| gradient_boosted_trees                         |         0.1581 |              0.0007235 |                   0.06608 |                          0.05949 |                           0.0788  |                          10.46 |                             5.316 |             0.2864 |             0.2    |                         0.01153   |                0.04394 |
| saturation_residual_fusion_new                 |         0.1645 |              0.008604  |                   0.07297 |                          0.06133 |                           0.08397 |                          10.09 |                             5.442 |             0.3114 |             0.1773 |                         0.01882   |                0.02104 |
| ridge                                          |         0.1865 |              0.01037   |                   0.0725  |                          0.06362 |                           0.07643 |                          13.59 |                             6.367 |             0.2886 |             0.2091 |                         0.03205   |                0.05738 |
| mlp                                            |         0.2178 |             -0.009665  |                   0.1036  |                          0.09269 |                           0.119   |                          12.5  |                             8.579 |             0.3182 |             0.1591 |                         0.01812   |                0.03338 |
| 1d_cnn                                         |         0.2222 |             -0.02356   |                   0.07941 |                          0.07194 |                           0.08338 |                          17.13 |                             8.771 |             0.3545 |             0.1659 |                         0.01884   |                0.08725 |
| tiny_sequence_transformer                      |         0.2559 |             -0.03346   |                   0.09346 |                          0.08315 |                           0.1031  |                          18.37 |                            11.51  |             0.3773 |             0.1955 |                         0.0003057 |                0.09454 |
| analytic_clipped_template_sideband_traditional |         0.2574 |              0.06892   |                   0.1094  |                          0.08469 |                           0.1258  |                          12    |                             6.148 |             0.5659 |             0.2068 |                         0.183     |                0.1047  |

The traditional comparator has score `0.2574` and energy
sigma68 `0.1094`.  The winner changes energy
sigma68 by `-0.04331`.

## Endpoint Table with CIs

| method                                         |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   saturation_onset_energy_sigma68 |   pileup_separation_sigma68_ns |   pileup_separation_sigma68_ns_ci_low |   pileup_separation_sigma68_ns_ci_high |   leading_timing_shift_bias_ns |   pedestal_shift_false_split_span |   pid_energy_bias_span |   pid_failure_rate_span |
|:-----------------------------------------------|--------------------------:|---------------------------------:|----------------------------------:|----------------------------------:|-------------------------------:|--------------------------------------:|---------------------------------------:|-------------------------------:|----------------------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                         |                   0.06608 |                          0.05949 |                           0.0788  |                           0.06294 |                          10.46 |                                 9.637 |                                  11.14 |                         0.2189 |                         0.01153   |                0.04394 |                  0.1707 |
| ridge                                          |                   0.0725  |                          0.06362 |                           0.07643 |                           0.06224 |                          13.59 |                                12.81  |                                  14.45 |                         0.1778 |                         0.03205   |                0.05738 |                  0.3053 |
| saturation_residual_fusion_new                 |                   0.07297 |                          0.06133 |                           0.08397 |                           0.05342 |                          10.09 |                                 8.832 |                                  11.8  |                         0.7226 |                         0.01882   |                0.02104 |                  0.2412 |
| 1d_cnn                                         |                   0.07941 |                          0.07194 |                           0.08338 |                           0.0843  |                          17.13 |                                15.33  |                                  18.26 |                         1.163  |                         0.01884   |                0.08725 |                  0.1546 |
| tiny_sequence_transformer                      |                   0.09346 |                          0.08315 |                           0.1031  |                           0.06568 |                          18.37 |                                16.65  |                                  20.97 |                        -4.264  |                         0.0003057 |                0.09454 |                  0.2228 |
| mlp                                            |                   0.1036  |                          0.09269 |                           0.119   |                           0.08527 |                          12.5  |                                11.28  |                                  13.47 |                        -2.511  |                         0.01812   |                0.03338 |                  0.2925 |
| analytic_clipped_template_sideband_traditional |                   0.1094  |                          0.08469 |                           0.1258  |                           0.01813 |                          12    |                                10     |                                  15    |                         0.9702 |                         0.183     |                0.1047  |                  0.0625 |

## Calibration and ECE

| method                                         |     ece |   brier |   n_heldout |
|:-----------------------------------------------|--------:|--------:|------------:|
| mlp                                            | 0.05936 |  0.168  |         880 |
| tiny_sequence_transformer                      | 0.07763 |  0.1952 |         880 |
| 1d_cnn                                         | 0.09407 |  0.1927 |         880 |
| gradient_boosted_trees                         | 0.09516 |  0.1736 |         880 |
| saturation_residual_fusion_new                 | 0.1029  |  0.1731 |         880 |
| ridge                                          | 0.1347  |  0.1926 |         880 |
| analytic_clipped_template_sideband_traditional | 0.3475  |  0.3614 |         880 |

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |               -0.02305   |                     0.07903 |       0.6432   |            10.95  |             0.2727 |            0.1136  |
| 1d_cnn                                         |            60 |               -0.0341    |                     0.07171 |       1.163    |            11.25  |             0.3068 |            0.2841  |
| 1d_cnn                                         |            62 |               -0.02317   |                     0.07455 |       0.2297   |            11.1   |             0.4205 |            0.2159  |
| 1d_cnn                                         |            64 |               -0.02715   |                     0.08385 |      -0.2254   |            13.29  |             0.3636 |            0.1136  |
| 1d_cnn                                         |            65 |               -0.02191   |                     0.06661 |       1.847    |             9.447 |             0.4091 |            0.1023  |
| analytic_clipped_template_sideband_traditional |            58 |                0.06118   |                     0.1141  |       1.405    |             8.134 |             0.5568 |            0.2841  |
| analytic_clipped_template_sideband_traditional |            60 |                0.08247   |                     0.1119  |       1.161    |            10.47  |             0.5455 |            0.25    |
| analytic_clipped_template_sideband_traditional |            62 |                0.09166   |                     0.1213  |       3.861    |             9.707 |             0.625  |            0.1705  |
| analytic_clipped_template_sideband_traditional |            64 |                0.06308   |                     0.1007  |       0.1436   |             8.088 |             0.5455 |            0.2045  |
| analytic_clipped_template_sideband_traditional |            65 |                0.06356   |                     0.0717  |      -0.4833   |             7.632 |             0.5568 |            0.125   |
| gradient_boosted_trees                         |            58 |                0.006921  |                     0.05641 |      -1.089    |             6.737 |             0.2614 |            0.2159  |
| gradient_boosted_trees                         |            60 |               -0.01271   |                     0.05896 |       1.336    |             7.813 |             0.2614 |            0.3523  |
| gradient_boosted_trees                         |            62 |                0.01372   |                     0.05949 |      -0.07515  |             7.405 |             0.3409 |            0.1477  |
| gradient_boosted_trees                         |            64 |               -0.002109  |                     0.08248 |      -0.5174   |             7.206 |             0.3068 |            0.1477  |
| gradient_boosted_trees                         |            65 |                0.0007224 |                     0.07928 |       0.2732   |             7.271 |             0.2614 |            0.1364  |
| mlp                                            |            58 |               -0.01691   |                     0.08978 |      -3.628    |            10.5   |             0.2045 |            0.1705  |
| mlp                                            |            60 |               -0.0008766 |                     0.08917 |      -1.518    |            10.29  |             0.3068 |            0.3182  |
| mlp                                            |            62 |                0.04912   |                     0.1172  |      -2.905    |            11.08  |             0.3636 |            0.1477  |
| mlp                                            |            64 |               -0.01747   |                     0.1231  |      -4.077    |             9.637 |             0.3409 |            0.09091 |
| mlp                                            |            65 |               -0.03361   |                     0.09537 |      -2.193    |             9.13  |             0.375  |            0.06818 |
| ridge                                          |            58 |                0.01573   |                     0.05565 |      -2.123    |             8.999 |             0.1932 |            0.2045  |
| ridge                                          |            60 |                0.0009905 |                     0.07568 |       1.05     |             8.886 |             0.3182 |            0.3523  |
| ridge                                          |            62 |                0.0117    |                     0.06768 |      -1.414    |             9.498 |             0.3068 |            0.1932  |
| ridge                                          |            64 |                0.003723  |                     0.07338 |      -0.5481   |             9.59  |             0.3068 |            0.1705  |
| ridge                                          |            65 |                0.01315   |                     0.07655 |       0.008731 |             6.195 |             0.3182 |            0.125   |
| saturation_residual_fusion_new                 |            58 |                0.0183    |                     0.05754 |      -1.328    |             7.112 |             0.2045 |            0.1705  |
| saturation_residual_fusion_new                 |            60 |                0.002676  |                     0.07758 |       1.528    |             7.85  |             0.2841 |            0.3182  |
| saturation_residual_fusion_new                 |            62 |                0.01726   |                     0.06056 |       0.2701   |             6.926 |             0.3864 |            0.1364  |
| saturation_residual_fusion_new                 |            64 |                0.002791  |                     0.0774  |      -0.9565   |             7.225 |             0.3523 |            0.1591  |
| saturation_residual_fusion_new                 |            65 |               -0.01847   |                     0.08469 |      -0.5643   |             6.127 |             0.3295 |            0.1023  |
| tiny_sequence_transformer                      |            58 |               -0.03323   |                     0.08339 |      -9.292    |            13.02  |             0.3295 |            0.1932  |
| tiny_sequence_transformer                      |            60 |               -0.03306   |                     0.0781  |      -7.972    |            14     |             0.3295 |            0.3182  |
| tiny_sequence_transformer                      |            62 |               -0.02741   |                     0.0917  |     -11.91     |            14.78  |             0.4318 |            0.1705  |
| tiny_sequence_transformer                      |            64 |               -0.04648   |                     0.1051  |      -7.455    |            15.47  |             0.4205 |            0.1932  |
| tiny_sequence_transformer                      |            65 |               -0.03328   |                     0.1083  |     -10.97     |            12.66  |             0.375  |            0.1023  |

## Stratified Systematics

| stratum          | value          | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:---------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0] | 1d_cnn                                         |               -0.015     |                     0.07986 |        2.16    |            11.45  |            0.4848  |
| spacing_bin      | (10.0, 25.0]   | 1d_cnn                                         |               -0.01791   |                     0.08111 |        0.9282  |             7.094 |            0.5229  |
| spacing_bin      | (25.0, 45.0]   | 1d_cnn                                         |               -0.03522   |                     0.08116 |       -0.9272  |            10.71  |            0.2273  |
| spacing_bin      | (45.0, 70.0]   | 1d_cnn                                         |               -0.02317   |                     0.07161 |        1.492   |            14.19  |            0.1124  |
| spacing_bin      | (-0.001, 10.0] | analytic_clipped_template_sideband_traditional |                0.07986   |                     0.1048  |        1.577   |            11.32  |            0.7197  |
| spacing_bin      | (10.0, 25.0]   | analytic_clipped_template_sideband_traditional |                0.08105   |                     0.1036  |        0.7057  |             9.087 |            0.6606  |
| spacing_bin      | (25.0, 45.0]   | analytic_clipped_template_sideband_traditional |                0.06281   |                     0.07501 |        1.125   |             9.695 |            0.5182  |
| spacing_bin      | (45.0, 70.0]   | analytic_clipped_template_sideband_traditional |                0.04398   |                     0.1302  |        0.1847  |             7.507 |            0.2809  |
| spacing_bin      | (-0.001, 10.0] | gradient_boosted_trees                         |                0.02999   |                     0.05911 |        0.6056  |             7.393 |            0.3939  |
| spacing_bin      | (10.0, 25.0]   | gradient_boosted_trees                         |                0.01077   |                     0.0709  |        0.886   |             5.379 |            0.4128  |
| spacing_bin      | (25.0, 45.0]   | gradient_boosted_trees                         |               -0.01464   |                     0.06928 |       -1.23    |             7.825 |            0.1909  |
| spacing_bin      | (45.0, 70.0]   | gradient_boosted_trees                         |               -0.02429   |                     0.06604 |       -1.01    |             7.773 |            0.08989 |
| spacing_bin      | (-0.001, 10.0] | mlp                                            |                0.008519  |                     0.1238  |        0.02004 |            10.92  |            0.4167  |
| spacing_bin      | (10.0, 25.0]   | mlp                                            |                0.003327  |                     0.1034  |       -2.743   |             8.493 |            0.422   |
| spacing_bin      | (25.0, 45.0]   | mlp                                            |               -0.01871   |                     0.09961 |       -5.745   |            10.17  |            0.2636  |
| spacing_bin      | (45.0, 70.0]   | mlp                                            |               -0.01954   |                     0.08604 |       -1.602   |            10.28  |            0.1124  |
| spacing_bin      | (-0.001, 10.0] | ridge                                          |                0.04296   |                     0.05179 |        1.005   |             9.779 |            0.3182  |
| spacing_bin      | (10.0, 25.0]   | ridge                                          |                0.0274    |                     0.07323 |        0.8038  |             6.639 |            0.3945  |
| spacing_bin      | (25.0, 45.0]   | ridge                                          |               -0.00874   |                     0.05792 |       -2.534   |             9.767 |            0.2818  |
| spacing_bin      | (45.0, 70.0]   | ridge                                          |               -0.02879   |                     0.07676 |       -2.325   |            10.49  |            0.1236  |
| spacing_bin      | (-0.001, 10.0] | saturation_residual_fusion_new                 |                0.03008   |                     0.05719 |        0.71    |             7.69  |            0.4773  |
| spacing_bin      | (10.0, 25.0]   | saturation_residual_fusion_new                 |                0.01492   |                     0.07329 |        0.8839  |             6.125 |            0.3853  |
| spacing_bin      | (25.0, 45.0]   | saturation_residual_fusion_new                 |               -0.0009979 |                     0.06948 |       -0.4725  |             7.882 |            0.2182  |
| spacing_bin      | (45.0, 70.0]   | saturation_residual_fusion_new                 |               -0.02418   |                     0.07101 |       -1.451   |             8.186 |            0.08989 |
| spacing_bin      | (-0.001, 10.0] | tiny_sequence_transformer                      |               -0.004021  |                     0.07917 |      -10.22    |            11.76  |            0.5227  |
| spacing_bin      | (10.0, 25.0]   | tiny_sequence_transformer                      |                0.01213   |                     0.05737 |      -11.48    |             9.977 |            0.5229  |
| spacing_bin      | (25.0, 45.0]   | tiny_sequence_transformer                      |               -0.04886   |                     0.08492 |       -9.083   |            15.36  |            0.2727  |
| spacing_bin      | (45.0, 70.0]   | tiny_sequence_transformer                      |               -0.1154    |                     0.08752 |       -6.734   |            18.55  |            0.1124  |
| ratio_bin        | (-0.001, 0.35] | 1d_cnn                                         |               -0.01586   |                     0.08502 |       -0.3868  |            11.62  |            0.4953  |
| ratio_bin        | (0.35, 0.625]  | 1d_cnn                                         |               -0.03453   |                     0.08124 |        0.07597 |            10.78  |            0.354   |
| ratio_bin        | (0.625, 0.875] | 1d_cnn                                         |               -0.02295   |                     0.08046 |        1.089   |            10.42  |            0.2673  |
| ratio_bin        | (0.875, 1.05]  | 1d_cnn                                         |               -0.02131   |                     0.06966 |        1.823   |            11.56  |            0.3025  |
| ratio_bin        | (-0.001, 0.35] | analytic_clipped_template_sideband_traditional |                0.08548   |                     0.1356  |       -0.3442  |            11.57  |            0.6729  |
| ratio_bin        | (0.35, 0.625]  | analytic_clipped_template_sideband_traditional |                0.05174   |                     0.08996 |        0.9702  |             9.566 |            0.4956  |
| ratio_bin        | (0.625, 0.875] | analytic_clipped_template_sideband_traditional |                0.07193   |                     0.1098  |        0.4516  |             8.381 |            0.5446  |
| ratio_bin        | (0.875, 1.05]  | analytic_clipped_template_sideband_traditional |                0.07362   |                     0.08604 |        2.624   |             7.443 |            0.5546  |
| ratio_bin        | (-0.001, 0.35] | gradient_boosted_trees                         |                0.02708   |                     0.06537 |       -1.88    |             8.004 |            0.4019  |
| ratio_bin        | (0.35, 0.625]  | gradient_boosted_trees                         |                0.0004015 |                     0.07716 |       -0.6623  |             6.858 |            0.3186  |
| ratio_bin        | (0.625, 0.875] | gradient_boosted_trees                         |               -0.009969  |                     0.06454 |        0.1869  |             6.509 |            0.2178  |
| ratio_bin        | (0.875, 1.05]  | gradient_boosted_trees                         |               -0.01371   |                     0.05846 |        2.031   |             7.539 |            0.2101  |
| ratio_bin        | (-0.001, 0.35] | mlp                                            |                0.01888   |                     0.117   |       -4.085   |            12.54  |            0.4766  |
| ratio_bin        | (0.35, 0.625]  | mlp                                            |               -0.002467  |                     0.09816 |       -4.359   |            10.08  |            0.3274  |
| ratio_bin        | (0.625, 0.875] | mlp                                            |               -0.01278   |                     0.1054  |       -1.783   |             8.444 |            0.2178  |
| ratio_bin        | (0.875, 1.05]  | mlp                                            |               -0.02338   |                     0.08736 |       -2.168   |            10.75  |            0.2521  |
| ratio_bin        | (-0.001, 0.35] | ridge                                          |                0.02277   |                     0.06663 |       -3.897   |             9.204 |            0.4486  |
| ratio_bin        | (0.35, 0.625]  | ridge                                          |                0.00672   |                     0.0659  |       -1.779   |             8.422 |            0.2832  |
| ratio_bin        | (0.625, 0.875] | ridge                                          |                0.009799  |                     0.07988 |        0.8998  |             8.181 |            0.2079  |
| ratio_bin        | (0.875, 1.05]  | ridge                                          |                0.0005569 |                     0.06826 |        1.734   |             8.771 |            0.2185  |
| ratio_bin        | (-0.001, 0.35] | saturation_residual_fusion_new                 |                0.03008   |                     0.07761 |       -3.095   |             8.557 |            0.4673  |
| ratio_bin        | (0.35, 0.625]  | saturation_residual_fusion_new                 |                0.002602  |                     0.06657 |       -0.5967  |             7.123 |            0.3186  |
| ratio_bin        | (0.625, 0.875] | saturation_residual_fusion_new                 |               -0.002362  |                     0.07521 |       -0.06743 |             6.515 |            0.2277  |
| ratio_bin        | (0.875, 1.05]  | saturation_residual_fusion_new                 |                0.002475  |                     0.07079 |        1.512   |             7.278 |            0.2353  |
| ratio_bin        | (-0.001, 0.35] | tiny_sequence_transformer                      |               -0.004021  |                     0.09444 |       -9.977   |            17.56  |            0.5234  |
| ratio_bin        | (0.35, 0.625]  | tiny_sequence_transformer                      |               -0.04886   |                     0.08905 |      -10.35    |            13.58  |            0.3451  |
| ratio_bin        | (0.625, 0.875] | tiny_sequence_transformer                      |               -0.0486    |                     0.09754 |       -8.526   |            12.26  |            0.3267  |
| ratio_bin        | (0.875, 1.05]  | tiny_sequence_transformer                      |               -0.02321   |                     0.08684 |       -8.475   |            12.85  |            0.3193  |
| saturation_bin   | 0              | 1d_cnn                                         |               -0.02317   |                     0.07788 |        0.7811  |            11.47  |            0.3571  |
| saturation_bin   | 1-2            | 1d_cnn                                         |               -0.1459    |                     0.0811  |        1.357   |            11.2   |            0.2     |
| saturation_bin   | 3-5            | 1d_cnn                                         |               -0.2428    |                     0       |       -1.686   |             6.113 |            0       |
| saturation_bin   | 0              | analytic_clipped_template_sideband_traditional |                0.06885   |                     0.111   |        0.9823  |             8.931 |            0.5691  |
| saturation_bin   | 1-2            | analytic_clipped_template_sideband_traditional |                0.09348   |                     0.01813 |        5.65    |            14.7   |            0.2     |
| saturation_bin   | 3-5            | analytic_clipped_template_sideband_traditional |              nan         |                   nan       |      nan       |           nan     |            1       |
| saturation_bin   | 0              | gradient_boosted_trees                         |                0.0005739 |                     0.06585 |        0.03642 |             7.459 |            0.288   |
| saturation_bin   | 1-2            | gradient_boosted_trees                         |                0.03333   |                     0.04498 |       -0.141   |             6.088 |            0.2     |
| saturation_bin   | 3-5            | gradient_boosted_trees                         |               -0.1183    |                     0       |       -7.273   |             2.399 |            0       |
| saturation_bin   | 0              | mlp                                            |               -0.008408  |                     0.1034  |       -2.78    |            10.32  |            0.3226  |
| saturation_bin   | 1-2            | mlp                                            |               -0.009196  |                     0.06302 |       -1.679   |             9.299 |            0       |
| saturation_bin   | 3-5            | mlp                                            |               -0.2141    |                     0       |       -7.935   |             2.609 |            0       |
| saturation_bin   | 0              | ridge                                          |                0.0115    |                     0.07207 |       -0.4173  |             8.797 |            0.2926  |
| saturation_bin   | 1-2            | ridge                                          |               -0.01673   |                     0.03537 |       -0.6162  |             8.045 |            0       |
| saturation_bin   | 3-5            | ridge                                          |               -0.2195    |                     0       |       -7.413   |             1.554 |            0       |
| saturation_bin   | 0              | saturation_residual_fusion_new                 |                0.008053  |                     0.07283 |       -0.2146  |             7.341 |            0.3157  |
| saturation_bin   | 1-2            | saturation_residual_fusion_new                 |                0.0536    |                     0.03256 |       -0.2266  |             6.296 |            0       |
| saturation_bin   | 3-5            | saturation_residual_fusion_new                 |               -0.1428    |                     0       |       -8.506   |             4.249 |            0       |
| saturation_bin   | 0              | tiny_sequence_transformer                      |               -0.03325   |                     0.09307 |       -9.271   |            14     |            0.3825  |
| saturation_bin   | 1-2            | tiny_sequence_transformer                      |               -0.03753   |                     0.03859 |      -10.82    |            11.87  |            0       |
| saturation_bin   | 3-5            | tiny_sequence_transformer                      |               -0.2378    |                     0       |      -18.71    |             1.452 |            0       |
| pedestal_state   | nominal        | 1d_cnn                                         |               -0.03693   |                     0.06148 |        1.247   |             8.922 |            0.4128  |
| pedestal_state   | shifted        | 1d_cnn                                         |               -0.01983   |                     0.09699 |        0.6611  |            12.3   |            0.3172  |
| pedestal_state   | nominal        | analytic_clipped_template_sideband_traditional |                0.0676    |                     0.1191  |        1.116   |             8.515 |            0.4593  |
| pedestal_state   | shifted        | analytic_clipped_template_sideband_traditional |                0.07043   |                     0.09867 |        0.8596  |             9.634 |            0.6343  |
| pedestal_state   | nominal        | gradient_boosted_trees                         |                0.0001646 |                     0.05838 |        0.1082  |             6.669 |            0.3256  |
| pedestal_state   | shifted        | gradient_boosted_trees                         |                0.004167  |                     0.07651 |        0.01456 |             8.43  |            0.2612  |
| pedestal_state   | nominal        | mlp                                            |                0.000279  |                     0.09692 |       -1.973   |             9.776 |            0.4012  |
| pedestal_state   | shifted        | mlp                                            |               -0.01133   |                     0.1052  |       -3.486   |            10.68  |            0.2649  |
| pedestal_state   | nominal        | ridge                                          |                0.006174  |                     0.06175 |       -0.181   |             7.485 |            0.343   |
| pedestal_state   | shifted        | ridge                                          |                0.01186   |                     0.08019 |       -0.519   |             9.933 |            0.2537  |
| pedestal_state   | nominal        | saturation_residual_fusion_new                 |                0.0128    |                     0.07193 |        0.4037  |             6.858 |            0.3372  |
| pedestal_state   | shifted        | saturation_residual_fusion_new                 |                0.005494  |                     0.0735  |       -0.6115  |             7.798 |            0.2948  |
| pedestal_state   | nominal        | tiny_sequence_transformer                      |               -0.05854   |                     0.07111 |       -7.665   |            14.18  |            0.4128  |
| pedestal_state   | shifted        | tiny_sequence_transformer                      |               -0.02134   |                     0.1072  |      -10.02    |            14.16  |            0.3545  |
| morphology_state | late_tail_high | 1d_cnn                                         |               -0.03453   |                     0.07003 |       -0.4269  |             9.793 |            0.4279  |
| morphology_state | late_tail_low  | 1d_cnn                                         |               -0.0148    |                     0.08703 |        1.798   |            12.44  |            0.2888  |
| morphology_state | late_tail_high | analytic_clipped_template_sideband_traditional |                0.09166   |                     0.1077  |        1.687   |             6.126 |            0.6394  |
| morphology_state | late_tail_low  | analytic_clipped_template_sideband_traditional |                0.05163   |                     0.09388 |        0.5437  |            11.03  |            0.5     |
| morphology_state | late_tail_high | gradient_boosted_trees                         |               -0.005445  |                     0.05646 |        0.2322  |             6.697 |            0.3462  |
| morphology_state | late_tail_low  | gradient_boosted_trees                         |                0.006763  |                     0.07642 |       -0.0391  |             8.153 |            0.2328  |
| morphology_state | late_tail_high | mlp                                            |               -0.02003   |                     0.09606 |       -3.77    |             9.731 |            0.375   |
| morphology_state | late_tail_low  | mlp                                            |                0.004841  |                     0.1134  |       -1.671   |            11.33  |            0.2672  |
| morphology_state | late_tail_high | ridge                                          |                0.003816  |                     0.05887 |       -0.1844  |             8.289 |            0.3413  |

## Counterfactual Ablations

The ablation ledger slices the winner after holding the trained model fixed:
pedestal-window quartiles, pile-up mask on/off, waveform-derivative quartiles,
and saturated-sample bins.  This is a counterfactual stress test of sensitivity
to those information channels, not a retraining sweep.

| ablation_axis     | counterfactual_level   | method                 |   n |   energy_fractional_bias |   energy_fractional_sigma68 |   delta_sigma68_vs_global |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------|:-----------------------|:-----------------------|----:|-------------------------:|----------------------------:|--------------------------:|------------------:|-------------------:|-------------------:|
| pedestal_windows  | q1                     | gradient_boosted_trees | 250 |               -0.0009419 |                     0.05285 |                -0.01323   |             6.959 |             0.2462 |             0.2583 |
| pedestal_windows  | q2                     | gradient_boosted_trees | 240 |               -0.000542  |                     0.06737 |                 0.001293  |             6.517 |             0.3805 |             0.126  |
| pedestal_windows  | q3                     | gradient_boosted_trees | 256 |               -0.009969  |                     0.07224 |                 0.006159  |             7.921 |             0.2443 |             0.2    |
| pedestal_windows  | q4                     | gradient_boosted_trees | 134 |                0.04818   |                     0.1056  |                 0.03952   |             9.031 |             0.2879 |             0.2353 |
| pileup_masks      | pileup_truth_off       | gradient_boosted_trees | 440 |              nan         |                   nan       |               nan         |           nan     |           nan      |             0.2    |
| pileup_masks      | pileup_truth_on        | gradient_boosted_trees | 440 |                0.0007235 |                     0.06608 |                 0         |             7.469 |             0.2864 |           nan      |
| shape_derivatives | q1                     | gradient_boosted_trees | 264 |               -0.01668   |                     0.06798 |                 0.001902  |             7.24  |             0.3093 |             0.1557 |
| shape_derivatives | q2                     | gradient_boosted_trees | 226 |               -0.01356   |                     0.07049 |                 0.004419  |             6.768 |             0.2893 |             0.2381 |
| shape_derivatives | q3                     | gradient_boosted_trees | 237 |                0.01143   |                     0.05419 |                -0.01189   |             7.902 |             0.2464 |             0.303  |
| shape_derivatives | q4                     | gradient_boosted_trees | 153 |                0.03097   |                     0.08044 |                 0.01436   |             8.061 |             0.3214 |             0.1014 |
| saturated_bins    | 0                      | gradient_boosted_trees | 874 |                0.0005739 |                     0.06585 |                -0.0002295 |             7.459 |             0.288  |             0.2    |
| saturated_bins    | 1-2                    | gradient_boosted_trees |   5 |                0.03333   |                     0.04498 |                -0.02109   |             6.088 |             0.2    |           nan      |
| saturated_bins    | 3-5                    | gradient_boosted_trees |   1 |               -0.1183    |                     0       |                -0.06608   |             2.399 |             0      |           nan      |
| saturated_bins    | 6+                     | gradient_boosted_trees |   0 |              nan         |                   nan       |               nan         |           nan     |           nan      |           nan      |

## Systematics and Caveats

The labels are controlled overlays into raw-ROOT-derived clean pulses, so the
study tests reconstruction under known pile-up/saturation truth but does not
measure the real beam pile-up rate.  The ADC clipping threshold is an explicit
stress condition rather than decoded front-end metadata.  PID-boundary movement
is represented by stave and charge-support proxy classes because no external
particle truth label exists in the reduced ROOT gate.  Run-bootstrap intervals
quantify transfer across five held-out runs and remain coarse for run-specific
edge cases.

## Verdict

`result.json` names **`gradient_boosted_trees`** as the S55c winner.  The traditional method is
kept as the transparent fallback; the selected winner is preferred by the
registered held-out energy, timing, calibration, pedestal, and PID-proxy score.

Runtime was `107.9` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

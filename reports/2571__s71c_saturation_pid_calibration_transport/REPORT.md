# Issue #2571 S71c: Saturation-to-PID Calibration Transport Across Pedestal Regimes

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

## Ticket Claim Provenance

The required command `tn-ticket claim testbeam-laptop-1 --project testbeam` was
run exactly once.  It returned the null pseudo-ticket payload
`null / # null / null` without moving the only open testbeam issue.  Read-only
queue inspection showed `#2571` still labeled `factory:open project:testbeam`
and no claimed issue for `worker:testbeam-laptop-1`, so `#2571` was manually
label-swapped to `factory:claimed worker:testbeam-laptop-1` without rerunning
the claim helper.  No novel follow-up ticket was appended.

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
| gradient_boosted_trees                         |         0.1581 |              0.0007235 |                   0.06608 |                          0.05949 |                           0.0788  |                          10.46 |                             5.316 |             0.2864 |             0.2    |                          0.01153  |                0.04394 |
| saturation_residual_fusion_new                 |         0.1645 |              0.008604  |                   0.07297 |                          0.06133 |                           0.08397 |                          10.09 |                             5.442 |             0.3114 |             0.1773 |                          0.01882  |                0.02104 |
| ridge                                          |         0.1865 |              0.01037   |                   0.0725  |                          0.06362 |                           0.07643 |                          13.59 |                             6.367 |             0.2886 |             0.2091 |                          0.03205  |                0.05738 |
| mlp                                            |         0.2178 |             -0.009665  |                   0.1036  |                          0.09269 |                           0.119   |                          12.5  |                             8.579 |             0.3182 |             0.1591 |                          0.01812  |                0.03338 |
| 1d_cnn                                         |         0.2195 |             -0.04024   |                   0.07613 |                          0.06955 |                           0.08576 |                          17.16 |                             7.872 |             0.4227 |             0.1409 |                          0.007817 |                0.07949 |
| analytic_clipped_template_sideband_traditional |         0.2574 |              0.06892   |                   0.1094  |                          0.08469 |                           0.1258  |                          12    |                             6.148 |             0.5659 |             0.2068 |                          0.183    |                0.1047  |
| tiny_sequence_transformer                      |         0.2643 |             -0.02386   |                   0.0978  |                          0.08651 |                           0.1069  |                          19    |                            11.63  |             0.375  |             0.2    |                          0.01153  |                0.1189  |

The traditional comparator has score `0.2574` and energy
sigma68 `0.1094`.  The winner changes energy
sigma68 by `-0.04331`.

## Endpoint Table with CIs

| method                                         |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   saturation_onset_energy_sigma68 |   pileup_separation_sigma68_ns |   pileup_separation_sigma68_ns_ci_low |   pileup_separation_sigma68_ns_ci_high |   leading_timing_shift_bias_ns |   pedestal_shift_false_split_span |   pid_energy_bias_span |   pid_failure_rate_span |
|:-----------------------------------------------|--------------------------:|---------------------------------:|----------------------------------:|----------------------------------:|-------------------------------:|--------------------------------------:|---------------------------------------:|-------------------------------:|----------------------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                         |                   0.06608 |                          0.05949 |                           0.0788  |                           0.06294 |                          10.46 |                                 9.637 |                                  11.14 |                         0.2189 |                          0.01153  |                0.04394 |                  0.1707 |
| ridge                                          |                   0.0725  |                          0.06362 |                           0.07643 |                           0.06224 |                          13.59 |                                12.81  |                                  14.45 |                         0.1778 |                          0.03205  |                0.05738 |                  0.3053 |
| saturation_residual_fusion_new                 |                   0.07297 |                          0.06133 |                           0.08397 |                           0.05342 |                          10.09 |                                 8.832 |                                  11.8  |                         0.7226 |                          0.01882  |                0.02104 |                  0.2412 |
| 1d_cnn                                         |                   0.07613 |                          0.06955 |                           0.08576 |                           0.07973 |                          17.16 |                                15.44  |                                  18.35 |                        -1.072  |                          0.007817 |                0.07949 |                  0.2268 |
| tiny_sequence_transformer                      |                   0.0978  |                          0.08651 |                           0.1069  |                           0.06628 |                          19    |                                17.15  |                                  20.69 |                        -2.783  |                          0.01153  |                0.1189  |                  0.1763 |
| mlp                                            |                   0.1036  |                          0.09269 |                           0.119   |                           0.08527 |                          12.5  |                                11.28  |                                  13.47 |                        -2.511  |                          0.01812  |                0.03338 |                  0.2925 |
| analytic_clipped_template_sideband_traditional |                   0.1094  |                          0.08469 |                           0.1258  |                           0.01813 |                          12    |                                10     |                                  15    |                         0.9702 |                          0.183    |                0.1047  |                  0.0625 |

## Calibration and ECE

| method                                         |     ece |   brier |   n_heldout |
|:-----------------------------------------------|--------:|--------:|------------:|
| mlp                                            | 0.05936 |  0.168  |         880 |
| tiny_sequence_transformer                      | 0.08543 |  0.1963 |         880 |
| gradient_boosted_trees                         | 0.09516 |  0.1736 |         880 |
| saturation_residual_fusion_new                 | 0.1029  |  0.1731 |         880 |
| 1d_cnn                                         | 0.1108  |  0.1966 |         880 |
| ridge                                          | 0.1347  |  0.1926 |         880 |
| analytic_clipped_template_sideband_traditional | 0.3475  |  0.3614 |         880 |

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |               -0.03632   |                     0.07694 |      -1.34     |            10.77  |             0.3636 |            0.09091 |
| 1d_cnn                                         |            60 |               -0.05408   |                     0.05627 |      -1.262    |            10.99  |             0.3636 |            0.2614  |
| 1d_cnn                                         |            62 |               -0.03422   |                     0.06356 |      -3.346    |            11.48  |             0.5    |            0.1932  |
| 1d_cnn                                         |            64 |               -0.03078   |                     0.09517 |      -2.66     |            14.64  |             0.4545 |            0.09091 |
| 1d_cnn                                         |            65 |               -0.05047   |                     0.07642 |      -1.161    |             9.081 |             0.4318 |            0.06818 |
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
| tiny_sequence_transformer                      |            58 |               -0.03442   |                     0.08258 |      -7.623    |            12.97  |             0.3523 |            0.1818  |
| tiny_sequence_transformer                      |            60 |               -0.02948   |                     0.07948 |      -6.447    |            13.41  |             0.3182 |            0.3182  |
| tiny_sequence_transformer                      |            62 |               -0.01724   |                     0.09269 |     -10.95     |            14.97  |             0.4091 |            0.1932  |
| tiny_sequence_transformer                      |            64 |               -0.02386   |                     0.1052  |      -7.403    |            15.83  |             0.4205 |            0.1932  |
| tiny_sequence_transformer                      |            65 |               -0.02457   |                     0.1108  |      -9.406    |            12.32  |             0.375  |            0.1136  |

## Stratified Systematics

| stratum          | value          | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:---------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0] | 1d_cnn                                         |               -0.01916   |                     0.07436 |        0.0906  |            11.69  |            0.6061  |
| spacing_bin      | (10.0, 25.0]   | 1d_cnn                                         |               -0.02237   |                     0.07824 |       -0.6227  |             5.814 |            0.5963  |
| spacing_bin      | (25.0, 45.0]   | 1d_cnn                                         |               -0.06271   |                     0.07568 |       -3.378   |            11.06  |            0.2727  |
| spacing_bin      | (45.0, 70.0]   | 1d_cnn                                         |               -0.05496   |                     0.06548 |       -1.892   |            13.25  |            0.1236  |
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
| spacing_bin      | (-0.001, 10.0] | tiny_sequence_transformer                      |               -0.0008046 |                     0.07224 |       -8.917   |            11.14  |            0.5303  |
| spacing_bin      | (10.0, 25.0]   | tiny_sequence_transformer                      |                0.01703   |                     0.06886 |      -10.93    |             9.127 |            0.5229  |
| spacing_bin      | (25.0, 45.0]   | tiny_sequence_transformer                      |               -0.03835   |                     0.07978 |       -8.847   |            14.99  |            0.2636  |
| spacing_bin      | (45.0, 70.0]   | tiny_sequence_transformer                      |               -0.1178    |                     0.08465 |       -6.017   |            18.51  |            0.1011  |
| ratio_bin        | (-0.001, 0.35] | 1d_cnn                                         |               -0.04021   |                     0.07138 |       -3.551   |            12.74  |            0.5794  |
| ratio_bin        | (0.35, 0.625]  | 1d_cnn                                         |               -0.05664   |                     0.07845 |       -3.29    |            10.79  |            0.4159  |
| ratio_bin        | (0.625, 0.875] | 1d_cnn                                         |               -0.03863   |                     0.07805 |       -1.714   |            11.08  |            0.3663  |
| ratio_bin        | (0.875, 1.05]  | 1d_cnn                                         |               -0.03232   |                     0.07353 |        0.7875  |            12.02  |            0.3361  |
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
| ratio_bin        | (-0.001, 0.35] | tiny_sequence_transformer                      |               -0.02894   |                     0.1041  |       -9.911   |            18.15  |            0.5234  |
| ratio_bin        | (0.35, 0.625]  | tiny_sequence_transformer                      |               -0.04355   |                     0.08827 |       -9.209   |            13.44  |            0.354   |
| ratio_bin        | (0.625, 0.875] | tiny_sequence_transformer                      |               -0.03143   |                     0.09914 |       -8.009   |            11.66  |            0.3168  |
| ratio_bin        | (0.875, 1.05]  | tiny_sequence_transformer                      |               -0.01339   |                     0.09144 |       -8.577   |            13.02  |            0.3109  |
| saturation_bin   | 0              | 1d_cnn                                         |               -0.04021   |                     0.07572 |       -1.804   |            11.38  |            0.4263  |
| saturation_bin   | 1-2            | 1d_cnn                                         |               -0.1314    |                     0.07251 |        2.091   |            10.76  |            0.2     |
| saturation_bin   | 3-5            | 1d_cnn                                         |               -0.2542    |                     0       |       -4.263   |             5.687 |            0       |
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
| saturation_bin   | 0              | tiny_sequence_transformer                      |               -0.02312   |                     0.09741 |       -8.714   |            14.01  |            0.3779  |
| saturation_bin   | 1-2            | tiny_sequence_transformer                      |               -0.05363   |                     0.03899 |       -4.353   |            12.59  |            0.2     |
| saturation_bin   | 3-5            | tiny_sequence_transformer                      |               -0.2145    |                     0       |      -18.51    |             1.936 |            0       |
| pedestal_state   | nominal        | 1d_cnn                                         |               -0.05114   |                     0.05203 |       -1.318   |             9.177 |            0.4826  |
| pedestal_state   | shifted        | 1d_cnn                                         |               -0.03301   |                     0.08382 |       -1.897   |            12.01  |            0.3843  |
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
| pedestal_state   | nominal        | tiny_sequence_transformer                      |               -0.04796   |                     0.07713 |       -7.298   |            14.25  |            0.4012  |
| pedestal_state   | shifted        | tiny_sequence_transformer                      |               -0.01122   |                     0.1081  |       -9.518   |            14.08  |            0.3582  |
| morphology_state | late_tail_high | 1d_cnn                                         |               -0.05838   |                     0.05968 |       -2.329   |            10.5   |            0.5192  |
| morphology_state | late_tail_low  | 1d_cnn                                         |               -0.02813   |                     0.08115 |       -1.215   |            12.05  |            0.3362  |
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


## S71c Transport Addendum

The ticket-specific question is transport, not only average reconstruction.
Accordingly, the held-out predictions are sliced by pedestal regime,
pulse-shape/timing state, PID proxy class, and saturation depth after the
run-held-out fit is frozen.  For endpoint `m` and stratum `a`, the reported
transport span is

`Delta_a(m) = max_k m(a=k) - min_k m(a=k)`,

with each stratum metric accompanied by a percentile 95% CI from held-out
run-block resampling.  PID-boundary drift is represented by the span in median
energy-scale residual across stave/charge proxy classes; pedestal transfer is
the false-split span across pedestal states; timing-slice dependence is the
median leading-edge timing-bias span across early/middle/late onset slices.

### Transport Endpoint Summary

| method                                         |   energy_scale_bias |   energy_resolution_sigma68 |   saturation_recovery_sigma68 |   pid_boundary_drift |   pedestal_transfer_false_split_span |   timing_slice_dependence_ns |
|:-----------------------------------------------|--------------------:|----------------------------:|------------------------------:|---------------------:|-------------------------------------:|-----------------------------:|
| 1d_cnn                                         |          -0.04024   |                     0.07613 |                       0.07973 |             0.007939 |                             0.007817 |                       11.78  |
| analytic_clipped_template_sideband_traditional |           0.06892   |                     0.1094  |                       0.01813 |             0.01473  |                             0.183    |                        1.02  |
| gradient_boosted_trees                         |           0.0007235 |                     0.06608 |                       0.06294 |             0.006632 |                             0.01153  |                        4.539 |
| mlp                                            |          -0.009665  |                     0.1036  |                       0.08527 |             0.02178  |                             0.01812  |                        7.163 |
| ridge                                          |           0.01037   |                     0.0725  |                       0.06224 |             0.04254  |                             0.03205  |                        5.856 |
| saturation_residual_fusion_new                 |           0.008604  |                     0.07297 |                       0.05342 |             0.01163  |                             0.01882  |                        4.707 |
| tiny_sequence_transformer                      |          -0.02386   |                     0.0978  |                       0.06628 |             0.04972  |                             0.01153  |                       19.52  |

### Largest Transport Spans

| axis            | metric                      | method                                         |   transport_span | worst_level       |   n_levels |
|:----------------|:----------------------------|:-----------------------------------------------|-----------------:|:------------------|-----------:|
| pedestal_regime | false_split_rate            | analytic_clipped_template_sideband_traditional |         0.183    | nominal           |          2 |
| pedestal_regime | energy_scale_bias           | tiny_sequence_transformer                      |         0.03675  | nominal           |          2 |
| pedestal_regime | false_split_rate            | ridge                                          |         0.03205  | shifted           |          2 |
| pedestal_regime | energy_resolution_sigma68   | 1d_cnn                                         |         0.03179  | shifted           |          2 |
| pedestal_regime | energy_resolution_sigma68   | tiny_sequence_transformer                      |         0.031    | shifted           |          2 |
| pedestal_regime | energy_resolution_sigma68   | analytic_clipped_template_sideband_traditional |         0.02047  | nominal           |          2 |
| pedestal_regime | false_split_rate            | saturation_residual_fusion_new                 |         0.01882  | shifted           |          2 |
| pedestal_regime | energy_resolution_sigma68   | ridge                                          |         0.01844  | shifted           |          2 |
| pedestal_regime | energy_resolution_sigma68   | gradient_boosted_trees                         |         0.01813  | shifted           |          2 |
| pedestal_regime | energy_scale_bias           | 1d_cnn                                         |         0.01812  | nominal           |          2 |
| pedestal_regime | false_split_rate            | mlp                                            |         0.01812  | shifted           |          2 |
| pedestal_regime | energy_scale_bias           | mlp                                            |         0.01161  | shifted           |          2 |
| pedestal_regime | false_split_rate            | gradient_boosted_trees                         |         0.01153  | nominal           |          2 |
| pedestal_regime | false_split_rate            | tiny_sequence_transformer                      |         0.01153  | nominal           |          2 |
| pedestal_regime | energy_resolution_sigma68   | mlp                                            |         0.008269 | shifted           |          2 |
| pedestal_regime | false_split_rate            | 1d_cnn                                         |         0.007817 | shifted           |          2 |
| pedestal_regime | energy_scale_bias           | saturation_residual_fusion_new                 |         0.007302 | nominal           |          2 |
| pedestal_regime | energy_scale_bias           | ridge                                          |         0.005686 | shifted           |          2 |
| pedestal_regime | energy_scale_bias           | gradient_boosted_trees                         |         0.004003 | shifted           |          2 |
| pedestal_regime | energy_scale_bias           | analytic_clipped_template_sideband_traditional |         0.002827 | shifted           |          2 |
| pedestal_regime | energy_resolution_sigma68   | saturation_residual_fusion_new                 |         0.001563 | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | 1d_cnn                                         |         0        | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | analytic_clipped_template_sideband_traditional |         0        | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | gradient_boosted_trees                         |         0        | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | mlp                                            |         0        | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | ridge                                          |         0        | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | saturation_residual_fusion_new                 |         0        | shifted           |          2 |
| pedestal_regime | saturation_recovery_sigma68 | tiny_sequence_transformer                      |         0        | shifted           |          2 |
| pid_proxy       | energy_resolution_sigma68   | analytic_clipped_template_sideband_traditional |         0.0751   | other             |          2 |
| pid_proxy       | energy_scale_bias           | tiny_sequence_transformer                      |         0.04972  | inner_high_charge |          2 |
| pid_proxy       | energy_scale_bias           | ridge                                          |         0.04254  | inner_high_charge |          2 |
| pid_proxy       | energy_resolution_sigma68   | mlp                                            |         0.02971  | inner_high_charge |          2 |
| pid_proxy       | energy_resolution_sigma68   | 1d_cnn                                         |         0.02677  | inner_high_charge |          2 |
| pid_proxy       | energy_scale_bias           | mlp                                            |         0.02178  | inner_high_charge |          2 |
| pid_proxy       | energy_scale_bias           | analytic_clipped_template_sideband_traditional |         0.01473  | inner_high_charge |          2 |
| pid_proxy       | energy_scale_bias           | saturation_residual_fusion_new                 |         0.01163  | other             |          2 |

### Stratum Metrics with Run-Block CIs

| axis            | level          | method                                         | metric                      |       value |      ci_low |    ci_high |   n |   n_runs |
|:----------------|:---------------|:-----------------------------------------------|:----------------------------|------------:|------------:|-----------:|----:|---------:|
| pedestal_regime | nominal        | 1d_cnn                                         | energy_scale_bias           |  -0.05114   |  -0.06136   |  -0.0352   | 341 |        5 |
| pedestal_regime | nominal        | 1d_cnn                                         | energy_resolution_sigma68   |   0.05203   |   0.04368   |   0.0564   | 341 |        5 |
| pedestal_regime | nominal        | 1d_cnn                                         | false_split_rate            |   0.1361    |   0.04516   |   0.233    | 341 |        5 |
| pedestal_regime | nominal        | 1d_cnn                                         | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | 1d_cnn                                         | energy_scale_bias           |  -0.03301   |  -0.04436   |  -0.01911  | 539 |        5 |
| pedestal_regime | shifted        | 1d_cnn                                         | energy_resolution_sigma68   |   0.08382   |   0.08062   |   0.1021   | 539 |        5 |
| pedestal_regime | shifted        | 1d_cnn                                         | false_split_rate            |   0.1439    |   0.08513   |   0.2008   | 539 |        5 |
| pedestal_regime | shifted        | 1d_cnn                                         | saturation_recovery_sigma68 |   0.07973   |   0         |   0.1095   | 539 |        5 |
| pedestal_regime | nominal        | analytic_clipped_template_sideband_traditional | energy_scale_bias           |   0.0676    |   0.05921   |   0.09118  | 341 |        5 |
| pedestal_regime | nominal        | analytic_clipped_template_sideband_traditional | energy_resolution_sigma68   |   0.1191    |   0.08071   |   0.1311   | 341 |        5 |
| pedestal_regime | nominal        | analytic_clipped_template_sideband_traditional | false_split_rate            |   0.3195    |   0.2236    |   0.4148   | 341 |        5 |
| pedestal_regime | nominal        | analytic_clipped_template_sideband_traditional | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | analytic_clipped_template_sideband_traditional | energy_scale_bias           |   0.07043   |   0.05919   |   0.07986  | 539 |        5 |
| pedestal_regime | shifted        | analytic_clipped_template_sideband_traditional | energy_resolution_sigma68   |   0.09867   |   0.07713   |   0.1127   | 539 |        5 |
| pedestal_regime | shifted        | analytic_clipped_template_sideband_traditional | false_split_rate            |   0.1365    |   0.1075    |   0.1679   | 539 |        5 |
| pedestal_regime | shifted        | analytic_clipped_template_sideband_traditional | saturation_recovery_sigma68 |   0.01813   |   0.01813   |   0.02996  | 539 |        5 |
| pedestal_regime | nominal        | gradient_boosted_trees                         | energy_scale_bias           |   0.0001646 |  -0.01752   |   0.01138  | 341 |        5 |
| pedestal_regime | nominal        | gradient_boosted_trees                         | energy_resolution_sigma68   |   0.05838   |   0.04493   |   0.06972  | 341 |        5 |
| pedestal_regime | nominal        | gradient_boosted_trees                         | false_split_rate            |   0.2071    |   0.1304    |   0.3239   | 341 |        5 |
| pedestal_regime | nominal        | gradient_boosted_trees                         | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | gradient_boosted_trees                         | energy_scale_bias           |   0.004167  |  -0.002109  |   0.01201  | 539 |        5 |
| pedestal_regime | shifted        | gradient_boosted_trees                         | energy_resolution_sigma68   |   0.07651   |   0.0586    |   0.09535  | 539 |        5 |
| pedestal_regime | shifted        | gradient_boosted_trees                         | false_split_rate            |   0.1956    |   0.1505    |   0.2576   | 539 |        5 |
| pedestal_regime | shifted        | gradient_boosted_trees                         | saturation_recovery_sigma68 |   0.06294   |   0         |   0.0909   | 539 |        5 |
| pedestal_regime | nominal        | mlp                                            | energy_scale_bias           |   0.000279  |  -0.01156   |   0.01045  | 341 |        5 |
| pedestal_regime | nominal        | mlp                                            | energy_resolution_sigma68   |   0.09692   |   0.08425   |   0.1056   | 341 |        5 |
| pedestal_regime | nominal        | mlp                                            | false_split_rate            |   0.1479    |   0.06452   |   0.226    | 341 |        5 |
| pedestal_regime | nominal        | mlp                                            | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | mlp                                            | energy_scale_bias           |  -0.01133   |  -0.02708   |   0.02411  | 539 |        5 |
| pedestal_regime | shifted        | mlp                                            | energy_resolution_sigma68   |   0.1052    |   0.09137   |   0.1274   | 539 |        5 |
| pedestal_regime | shifted        | mlp                                            | false_split_rate            |   0.1661    |   0.1115    |   0.2652   | 539 |        5 |
| pedestal_regime | shifted        | mlp                                            | saturation_recovery_sigma68 |   0.08527   |   0         |   0.1198   | 539 |        5 |
| pedestal_regime | nominal        | ridge                                          | energy_scale_bias           |   0.006174  |   0.0005569 |   0.01386  | 341 |        5 |
| pedestal_regime | nominal        | ridge                                          | energy_resolution_sigma68   |   0.06175   |   0.05295   |   0.06615  | 341 |        5 |
| pedestal_regime | nominal        | ridge                                          | false_split_rate            |   0.1893    |   0.1118    |   0.2743   | 341 |        5 |
| pedestal_regime | nominal        | ridge                                          | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | ridge                                          | energy_scale_bias           |   0.01186   |   0.005384  |   0.01843  | 539 |        5 |
| pedestal_regime | shifted        | ridge                                          | energy_resolution_sigma68   |   0.08019   |   0.0674    |   0.09613  | 539 |        5 |
| pedestal_regime | shifted        | ridge                                          | false_split_rate            |   0.2214    |   0.1794    |   0.2928   | 539 |        5 |
| pedestal_regime | shifted        | ridge                                          | saturation_recovery_sigma68 |   0.06224   |   0         |   0.1125   | 539 |        5 |
| pedestal_regime | nominal        | saturation_residual_fusion_new                 | energy_scale_bias           |   0.0128    |  -0.02024   |   0.03553  | 341 |        5 |
| pedestal_regime | nominal        | saturation_residual_fusion_new                 | energy_resolution_sigma68   |   0.07193   |   0.05608   |   0.08334  | 341 |        5 |
| pedestal_regime | nominal        | saturation_residual_fusion_new                 | false_split_rate            |   0.1657    |   0.08345   |   0.2718   | 341 |        5 |
| pedestal_regime | nominal        | saturation_residual_fusion_new                 | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | saturation_residual_fusion_new                 | energy_scale_bias           |   0.005494  |  -0.0005868 |   0.01765  | 539 |        5 |
| pedestal_regime | shifted        | saturation_residual_fusion_new                 | energy_resolution_sigma68   |   0.0735    |   0.06364   |   0.08509  | 539 |        5 |
| pedestal_regime | shifted        | saturation_residual_fusion_new                 | false_split_rate            |   0.1845    |   0.1434    |   0.2325   | 539 |        5 |
| pedestal_regime | shifted        | saturation_residual_fusion_new                 | saturation_recovery_sigma68 |   0.05342   |   0         |   0.1119   | 539 |        5 |
| pedestal_regime | nominal        | tiny_sequence_transformer                      | energy_scale_bias           |  -0.04796   |  -0.07545   |  -0.03973  | 341 |        5 |
| pedestal_regime | nominal        | tiny_sequence_transformer                      | energy_resolution_sigma68   |   0.07713   |   0.05964   |   0.08289  | 341 |        5 |
| pedestal_regime | nominal        | tiny_sequence_transformer                      | false_split_rate            |   0.2071    |   0.1288    |   0.3139   | 341 |        5 |
| pedestal_regime | nominal        | tiny_sequence_transformer                      | saturation_recovery_sigma68 | nan         | nan         | nan        | 341 |        5 |
| pedestal_regime | shifted        | tiny_sequence_transformer                      | energy_scale_bias           |  -0.01122   |  -0.01693   |  -0.003007 | 539 |        5 |
| pedestal_regime | shifted        | tiny_sequence_transformer                      | energy_resolution_sigma68   |   0.1081    |   0.09361   |   0.1271   | 539 |        5 |
| pedestal_regime | shifted        | tiny_sequence_transformer                      | false_split_rate            |   0.1956    |   0.1514    |   0.2386   | 539 |        5 |
| pedestal_regime | shifted        | tiny_sequence_transformer                      | saturation_recovery_sigma68 |   0.06628   |   0         |   0.09204  | 539 |        5 |
| timing_slice    | late_tail_high | 1d_cnn                                         | energy_scale_bias           |  -0.05838   |  -0.06385   |  -0.03636  | 476 |        5 |
| timing_slice    | late_tail_high | 1d_cnn                                         | energy_resolution_sigma68   |   0.05968   |   0.04516   |   0.07042  | 476 |        5 |
| timing_slice    | late_tail_high | 1d_cnn                                         | false_split_rate            |   0.08582   |   0.03312   |   0.1405   | 476 |        5 |
| timing_slice    | late_tail_high | 1d_cnn                                         | saturation_recovery_sigma68 |   0         |   0         |   0        | 476 |        5 |

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

`result.json` names **`gradient_boosted_trees`** as the S71c winner.  The traditional method is
kept as the transparent fallback; the selected winner is preferred by the
registered held-out energy, timing, calibration, pedestal, and PID-proxy score.

Runtime was `104.4` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

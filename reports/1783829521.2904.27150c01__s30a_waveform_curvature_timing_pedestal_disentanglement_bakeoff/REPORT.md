# S30a: waveform curvature timing-pedestal disentanglement bakeoff

## Abstract

Ticket `1783829521.2904.27150c01` asks for a raw-ROOT-reproduced benchmark comparing a strong
traditional CFD/template chi-square timing method with ridge, gradient-boosted
trees, MLP, 1D-CNN, and a new sequence architecture on raw and
pedestal-subtracted pulse representations.  The claimed worker is `testbeam-laptop-2`.

The raw selected-pulse number is reproduced from ROOT: `640737`
selected B-stave pulses versus reference `640737`,
delta `0`.  The winner named in `result.json` is
**`template_residual_boosted_stack_new`** by the held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

The winning score is `0.2111`.  Its energy residual sigma68 is
`0.07753` with 95% run-block bootstrap CI
[`0.0666`, `0.1023`],
and its timing pull sigma68 is `7.393` ns with CI
[`6.722`, `8.387`].

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.  Each
`h101/HRDv` branch is interpreted as `(event, channel, sample)` with 18 ADC
samples.  The B-stack reproduction selection is

`b_c = median_{t in 0..3} x_c(t)`,

`y_c(t) = x_c(t) - b_c`,

`I_i = 1[max_{c in B2,B4,B6,B8,t} y_ic(t) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Experimental Design

The benchmark is split by source run.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  No run appears in both sets.
Templates, scalers, likelihood moments, neural normalizers, regressors, and
architecture weights are fit on training runs only.  Confidence intervals are
percentile intervals from `360`
held-out run-block bootstrap resamples.

Two input views are audited.  Raw-sequence models (`1d_cnn`,
`joint_sequence_transformer`) consume ADC sequences after internal
normalization.  Feature and template models consume pedestal-subtracted,
curvature-aware summaries such as area-over-peak, late charge, width, CFD time,
and template residuals.  This separation tests whether raw sequence capacity is
useful beyond the traditional pedestal-subtracted representation.

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`, a train-run
template/CFD two-pulse fit with a diagonal Gaussian PID likelihood.  For a
class `y` and standardized feature vector `z`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP,
`1d_cnn`, and the new `joint_sequence_transformer`.  A second new architecture,
`template_residual_boosted_stack_new`, residualizes the traditional template
fit and lets boosted trees model the remaining nonlinear structure.

For accepted pile-up doublets,

`e_t = 10 ns (hat t_1 - t_1)`,

`e_E = [(hat A_1 + hat A_2) - A_true] / A_true`,

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

Pile-up sensitivity is reported as the held-out miss rate for true overlaps and
false split rate for singles.  Pedestal drift is stratified by the raw
pretrigger median `b_c`.  Saturation onset is stratified by
`max_t y_c(t) > 14000 ADC`.  Curvature is represented by
`sum_t y(t) / max_t y(t)`, which captures broad/late tails at fixed amplitude.

## Overall Results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.2111 |    0.9248 |                  0.8641 |           0.9125 |       0.8319 |                     0.07753 |                            0.0666  |                             0.1023  |             7.393 |                    6.722 |                     8.387 |             0.3063 |             0.2062 |
| gradient_boosted_trees              |         0.2266 |    0.9226 |                  0.8531 |           0.8938 |       0.8266 |                     0.0852  |                            0.07581 |                             0.09464 |             7.735 |                    7.002 |                     8.581 |             0.2906 |             0.2562 |
| ridge                               |         0.2601 |    0.8752 |                  0.7594 |           0.6687 |       0.8168 |                     0.07854 |                            0.07358 |                             0.08967 |             9.31  |                    8.548 |                     9.885 |             0.3094 |             0.2562 |
| 1d_cnn                              |         0.2828 |    0.8397 |                  0.7766 |           0.7281 |       0.8062 |                     0.09587 |                            0.08587 |                             0.1091  |            10.43  |                    9.98  |                    11.64  |             0.3719 |             0.1625 |
| deltaE_over_E_likelihood_template   |         0.3061 |    0.833  |                  0.7922 |           0.7469 |       0.8213 |                     0.1076  |                            0.08791 |                             0.1201  |            10.88  |                   10     |                    11.6   |             0.6312 |             0.125  |
| mlp                                 |         0.3319 |    0.8582 |                  0.7766 |           0.7063 |       0.8218 |                     0.1247  |                            0.1041  |                             0.1432  |            12.44  |                   11.21  |                    13.24  |             0.3125 |             0.225  |
| joint_sequence_transformer          |         0.4049 |    0.5498 |                  0.5422 |           0.5687 |       0.5401 |                     0.1386  |                            0.1197  |                             0.1735  |            12.49  |                   11.43  |                    13.12  |             0.2969 |             0.2406 |

Relative to the traditional CFD/template baseline, `template_residual_boosted_stack_new` changes energy
sigma68 by `-0.03009`,
timing sigma68 by `-3.484` ns,
and PID balanced accuracy by `0.07187`.

## Raw Versus Pedestal-Subtracted Views

| input_view                       | methods                                                                                                    |    n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------------------|:-----------------------------------------------------------------------------------------------------------|-----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| raw_adc_sequence_view            | 1d_cnn, joint_sequence_transformer                                                                         | 1280 |                 9.645 |             0.3344 |             0.2016 |                      0.1419 |                  0.6594 |
| pedestal_subtracted_feature_view | deltaE_over_E_likelihood_template, gradient_boosted_trees, mlp, ridge, template_residual_boosted_stack_new | 3200 |                 7.51  |             0.37   |             0.2137 |                      0.1166 |                  0.8091 |

## Run-Heldout Stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.7675 |           0.6986 |       0.85   |                     0.1074  |            10.17  |             0.4062 |            0.1719  |
| 1d_cnn                              |            60 |                  0.716  |           0.629  |       0.75   |                     0.07457 |            10.12  |             0.2812 |            0.3125  |
| 1d_cnn                              |            62 |                  0.8195 |           0.8033 |       0.8167 |                     0.1019  |            12.25  |             0.4219 |            0.1094  |
| 1d_cnn                              |            64 |                  0.8126 |           0.8136 |       0.7869 |                     0.08067 |            10.33  |             0.4688 |            0.07812 |
| 1d_cnn                              |            65 |                  0.7745 |           0.7077 |       0.8214 |                     0.1037  |            10.49  |             0.2812 |            0.1406  |
| deltaE_over_E_likelihood_template   |            58 |                  0.7173 |           0.6164 |       0.8182 |                     0.08821 |            10.17  |             0.625  |            0.1406  |
| deltaE_over_E_likelihood_template   |            60 |                  0.8189 |           0.7742 |       0.8421 |                     0.1065  |            11.99  |             0.625  |            0.1562  |
| deltaE_over_E_likelihood_template   |            62 |                  0.7868 |           0.7377 |       0.8036 |                     0.1195  |            10.76  |             0.6562 |            0.09375 |
| deltaE_over_E_likelihood_template   |            64 |                  0.8452 |           0.8644 |       0.8095 |                     0.1034  |             8.779 |             0.6875 |            0.1406  |
| deltaE_over_E_likelihood_template   |            65 |                  0.8053 |           0.7692 |       0.8333 |                     0.07615 |            11.29  |             0.5625 |            0.09375 |
| gradient_boosted_trees              |            58 |                  0.8315 |           0.863  |       0.8514 |                     0.07973 |             7.337 |             0.3438 |            0.2969  |
| gradient_boosted_trees              |            60 |                  0.8693 |           0.9355 |       0.8169 |                     0.06185 |             8.188 |             0.1875 |            0.3281  |
| gradient_boosted_trees              |            62 |                  0.8381 |           0.8852 |       0.7941 |                     0.1121  |             9.615 |             0.3594 |            0.2344  |
| gradient_boosted_trees              |            64 |                  0.8513 |           0.8475 |       0.8333 |                     0.08937 |             6.188 |             0.3594 |            0.1875  |
| gradient_boosted_trees              |            65 |                  0.874  |           0.9385 |       0.8356 |                     0.09446 |             6.704 |             0.2031 |            0.2344  |
| joint_sequence_transformer          |            58 |                  0.5354 |           0.5616 |       0.6029 |                     0.1741  |            11.51  |             0.2969 |            0.2969  |
| joint_sequence_transformer          |            60 |                  0.5024 |           0.5806 |       0.4865 |                     0.1011  |            10.8   |             0.2656 |            0.3281  |
| joint_sequence_transformer          |            62 |                  0.4743 |           0.4262 |       0.4483 |                     0.1661  |            12.61  |             0.2812 |            0.1719  |
| joint_sequence_transformer          |            64 |                  0.6324 |           0.6271 |       0.5968 |                     0.141   |            10.99  |             0.4531 |            0.1562  |
| joint_sequence_transformer          |            65 |                  0.5612 |           0.6462 |       0.56   |                     0.1321  |            12.27  |             0.1875 |            0.25    |
| mlp                                 |            58 |                  0.7675 |           0.6986 |       0.85   |                     0.1339  |            13.22  |             0.3281 |            0.2344  |
| mlp                                 |            60 |                  0.7397 |           0.6613 |       0.7736 |                     0.08918 |            10.68  |             0.2812 |            0.3594  |
| mlp                                 |            62 |                  0.8092 |           0.7377 |       0.8491 |                     0.1458  |            12.68  |             0.3125 |            0.1562  |
| mlp                                 |            64 |                  0.8016 |           0.7627 |       0.8036 |                     0.1106  |            11.51  |             0.4062 |            0.1719  |
| mlp                                 |            65 |                  0.767  |           0.6769 |       0.8302 |                     0.1172  |            11.02  |             0.2344 |            0.2031  |
| ridge                               |            58 |                  0.7333 |           0.6301 |       0.8364 |                     0.07882 |             9.425 |             0.375  |            0.2969  |
| ridge                               |            60 |                  0.7075 |           0.5968 |       0.7551 |                     0.06048 |             8.786 |             0.2344 |            0.4219  |
| ridge                               |            62 |                  0.8248 |           0.7541 |       0.8679 |                     0.08863 |             9.981 |             0.3594 |            0.25    |
| ridge                               |            64 |                  0.7762 |           0.7119 |       0.7925 |                     0.0733  |             9.149 |             0.4062 |            0.125   |
| ridge                               |            65 |                  0.7593 |           0.6615 |       0.8269 |                     0.08642 |             8.199 |             0.1719 |            0.1875  |
| template_residual_boosted_stack_new |            58 |                  0.8521 |           0.9041 |       0.8571 |                     0.08246 |             8.2   |             0.3438 |            0.1719  |
| template_residual_boosted_stack_new |            60 |                  0.8617 |           0.9355 |       0.8056 |                     0.05916 |             8.09  |             0.1875 |            0.375   |
| template_residual_boosted_stack_new |            62 |                  0.8381 |           0.8852 |       0.7941 |                     0.1254  |             9.548 |             0.3594 |            0.1562  |
| template_residual_boosted_stack_new |            64 |                  0.8682 |           0.8814 |       0.8387 |                     0.06102 |             6.105 |             0.4375 |            0.125   |
| template_residual_boosted_stack_new |            65 |                  0.8976 |           0.9538 |       0.8611 |                     0.08081 |             6.727 |             0.2031 |            0.2031  |

## Curvature, Timing, Pedestal, Saturation, Energy, and PID Sidebands

| sideband             | value                 | method                              |   n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------|:----------------------|:------------------------------------|----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| curvature_band       | high_curvature        | 1d_cnn                              | 213 |                 8.266 |             0.226  |            0.3731  |                     0.1188  |                  0.7572 |
| curvature_band       | high_curvature        | deltaE_over_E_likelihood_template   | 213 |                 8.378 |             0.4521 |            0.3284  |                     0.1099  |                  0.8018 |
| curvature_band       | high_curvature        | gradient_boosted_trees              | 213 |                 5.294 |             0.2055 |            0.5075  |                     0.1056  |                  0.8425 |
| curvature_band       | high_curvature        | joint_sequence_transformer          | 213 |                 9.077 |             0.2329 |            0.403   |                     0.14    |                  0.5023 |
| curvature_band       | high_curvature        | mlp                                 | 213 |                11.01  |             0.1986 |            0.4627  |                     0.1501  |                  0.772  |
| curvature_band       | high_curvature        | ridge                               | 213 |                 7.104 |             0.1712 |            0.5224  |                     0.09872 |                  0.7189 |
| curvature_band       | high_curvature        | template_residual_boosted_stack_new | 213 |                 4.798 |             0.1986 |            0.4328  |                     0.0868  |                  0.8603 |
| curvature_band       | low_curvature         | 1d_cnn                              | 214 |                 9.796 |             0.8036 |            0.05063 |                     0.1544  |                  0.7844 |
| curvature_band       | low_curvature         | deltaE_over_E_likelihood_template   | 214 |                 9.665 |             0.9643 |            0.02532 |                     0.1825  |                  0.7759 |
| curvature_band       | low_curvature         | gradient_boosted_trees              | 214 |                 4.928 |             0.5714 |            0.1013  |                     0.08951 |                  0.877  |
| curvature_band       | low_curvature         | joint_sequence_transformer          | 214 |                13.73  |             0.6071 |            0.1013  |                     0.2467  |                  0.4907 |
| curvature_band       | low_curvature         | mlp                                 | 214 |                 9.874 |             0.75   |            0.09494 |                     0.1827  |                  0.777  |
| curvature_band       | low_curvature         | ridge                               | 214 |                 6.08  |             0.7143 |            0.09494 |                     0.1339  |                  0.7823 |
| curvature_band       | low_curvature         | template_residual_boosted_stack_new | 214 |                 4.963 |             0.6607 |            0.08228 |                     0.1002  |                  0.8602 |
| curvature_band       | mid_curvature         | 1d_cnn                              | 213 |                 8.647 |             0.3475 |            0.2     |                     0.1255  |                  0.7884 |
| curvature_band       | mid_curvature         | deltaE_over_E_likelihood_template   | 213 |                 7.502 |             0.6949 |            0.1474  |                     0.157   |                  0.7934 |
| curvature_band       | mid_curvature         | gradient_boosted_trees              | 213 |                 6.728 |             0.2627 |            0.3368  |                     0.1114  |                  0.8448 |
| curvature_band       | mid_curvature         | joint_sequence_transformer          | 213 |                12.94  |             0.2288 |            0.3579  |                     0.1751  |                  0.5667 |
| curvature_band       | mid_curvature         | mlp                                 | 213 |                12.74  |             0.2458 |            0.2737  |                     0.1463  |                  0.7807 |
| curvature_band       | mid_curvature         | ridge                               | 213 |                 7.244 |             0.2881 |            0.3368  |                     0.1272  |                  0.7807 |
| curvature_band       | mid_curvature         | template_residual_boosted_stack_new | 213 |                 6.71  |             0.2712 |            0.2526  |                     0.1008  |                  0.8713 |
| energy_residual_band | high_abs_energy_resid | 1d_cnn                              | 215 |                10.94  |             0.7273 |            0.09375 |                     0.4143  |                  0.7721 |
| energy_residual_band | high_abs_energy_resid | deltaE_over_E_likelihood_template   |  51 |                 9.325 |             0.36   |            0.5769  |                     0.3294  |                  0.7654 |
| energy_residual_band | high_abs_energy_resid | gradient_boosted_trees              | 189 |                 4.651 |             0.5714 |            0.1429  |                     0.2944  |                  0.8195 |
| energy_residual_band | high_abs_energy_resid | joint_sequence_transformer          | 266 |                13.12  |             0.4568 |            0.1459  |                     0.3957  |                  0.5523 |
| energy_residual_band | high_abs_energy_resid | mlp                                 | 230 |                12.69  |             0.5429 |            0.1187  |                     0.3613  |                  0.7715 |
| energy_residual_band | high_abs_energy_resid | ridge                               | 213 |                 8.3   |             0.8    |            0.1214  |                     0.07723 |                  0.7177 |
| energy_residual_band | high_abs_energy_resid | template_residual_boosted_stack_new | 187 |                 6.729 |             0.5882 |            0.1242  |                     0.3139  |                  0.8365 |
| energy_residual_band | low_abs_energy_resid  | 1d_cnn                              | 192 |                 8.131 |             0.2446 |            0.283   |                     0.04417 |                  0.8006 |
| energy_residual_band | low_abs_energy_resid  | deltaE_over_E_likelihood_template   |  87 |                 9.028 |             0.1286 |            0.4118  |                     0.03069 |                  0.8508 |
| energy_residual_band | low_abs_energy_resid  | gradient_boosted_trees              | 244 |                 5.788 |             0.1754 |            0.3288  |                     0.03742 |                  0.8727 |
| energy_residual_band | low_abs_energy_resid  | joint_sequence_transformer          | 159 |                10.02  |             0.2564 |            0.4048  |                     0.04177 |                  0.5259 |
| energy_residual_band | low_abs_energy_resid  | mlp                                 | 175 |                 9.551 |             0.1709 |            0.2931  |                     0.03856 |                  0.7918 |
| energy_residual_band | low_abs_energy_resid  | ridge                               | 229 |                 6.716 |             0.2086 |            0.4091  |                     0.03925 |                  0.8101 |
| energy_residual_band | low_abs_energy_resid  | template_residual_boosted_stack_new | 265 |                 5.706 |             0.2606 |            0.2857  |                     0.0419  |                  0.8825 |
| energy_residual_band | mid_abs_energy_resid  | 1d_cnn                              | 233 |                 9.006 |             0.3571 |            0.2056  |                     0.1318  |                  0.7618 |
| energy_residual_band | mid_abs_energy_resid  | deltaE_over_E_likelihood_template   |  75 |                 8.141 |             0.1277 |            0.6429  |                     0.1432  |                  0.8538 |
| energy_residual_band | mid_abs_energy_resid  | gradient_boosted_trees              | 207 |                 6.592 |             0.3772 |            0.3871  |                     0.1342  |                  0.8619 |
| energy_residual_band | mid_abs_energy_resid  | joint_sequence_transformer          | 215 |                 9.978 |             0.2295 |            0.3548  |                     0.1486  |                  0.5132 |
| energy_residual_band | mid_abs_energy_resid  | mlp                                 | 235 |                11.07  |             0.3158 |            0.3529  |                     0.1429  |                  0.7731 |
| energy_residual_band | mid_abs_energy_resid  | ridge                               | 198 |                 7.181 |             0.2821 |            0.4198  |                     0.1156  |                  0.7401 |
| energy_residual_band | mid_abs_energy_resid  | template_residual_boosted_stack_new | 188 |                 6.41  |             0.2959 |            0.2778  |                     0.1382  |                  0.8643 |
| pedestal_drift_band  | high_pedestal         | 1d_cnn                              | 213 |                 7.457 |             0.3496 |            0.2111  |                     0.09557 |                  0.8314 |
| pedestal_drift_band  | high_pedestal         | deltaE_over_E_likelihood_template   | 213 |                 8.465 |             0.5528 |            0.1778  |                     0.1001  |                  0.8169 |
| pedestal_drift_band  | high_pedestal         | gradient_boosted_trees              | 213 |                 4.487 |             0.2439 |            0.3222  |                     0.1064  |                  0.8403 |
| pedestal_drift_band  | high_pedestal         | joint_sequence_transformer          | 213 |                 9.135 |             0.3252 |            0.3222  |                     0.148   |                  0.4967 |
| pedestal_drift_band  | high_pedestal         | mlp                                 | 213 |                 7.882 |             0.3008 |            0.3     |                     0.15    |                  0.8146 |
| pedestal_drift_band  | high_pedestal         | ridge                               | 213 |                 6.63  |             0.2602 |            0.3444  |                     0.08903 |                  0.7942 |
| pedestal_drift_band  | high_pedestal         | template_residual_boosted_stack_new | 213 |                 4.111 |             0.2602 |            0.2556  |                     0.1006  |                  0.865  |
| pedestal_drift_band  | low_pedestal          | 1d_cnn                              | 214 |                10.53  |             0.4299 |            0.1589  |                     0.155   |                  0.7408 |
| pedestal_drift_band  | low_pedestal          | deltaE_over_E_likelihood_template   | 214 |                 7.545 |             0.7009 |            0.1589  |                     0.1776  |                  0.7813 |
| pedestal_drift_band  | low_pedestal          | gradient_boosted_trees              | 214 |                 8.112 |             0.3738 |            0.2991  |                     0.1155  |                  0.8305 |
| pedestal_drift_band  | low_pedestal          | joint_sequence_transformer          | 214 |                 9.099 |             0.3364 |            0.243   |                     0.2141  |                  0.5477 |
| pedestal_drift_band  | low_pedestal          | mlp                                 | 214 |                14.23  |             0.3551 |            0.2056  |                     0.1715  |                  0.746  |
| pedestal_drift_band  | low_pedestal          | ridge                               | 214 |                 8.733 |             0.3738 |            0.271   |                     0.1417  |                  0.7279 |
| pedestal_drift_band  | low_pedestal          | template_residual_boosted_stack_new | 214 |                 6.988 |             0.3458 |            0.1963  |                     0.08936 |                  0.844  |
| pedestal_drift_band  | mid_pedestal          | 1d_cnn                              | 213 |                 8.343 |             0.3333 |            0.1301  |                     0.1202  |                  0.7639 |
| pedestal_drift_band  | mid_pedestal          | deltaE_over_E_likelihood_template   | 213 |                 6.459 |             0.6556 |            0.05691 |                     0.1067  |                  0.7839 |
| pedestal_drift_band  | mid_pedestal          | gradient_boosted_trees              | 213 |                 5.382 |             0.2556 |            0.1707  |                     0.09859 |                  0.8908 |
| pedestal_drift_band  | mid_pedestal          | joint_sequence_transformer          | 213 |                 8.778 |             0.2111 |            0.1789  |                     0.1619  |                  0.5918 |
| pedestal_drift_band  | mid_pedestal          | mlp                                 | 213 |                 9.709 |             0.2778 |            0.187   |                     0.15    |                  0.7741 |
| pedestal_drift_band  | mid_pedestal          | ridge                               | 213 |                 5.698 |             0.3    |            0.1789  |                     0.09822 |                  0.761  |
| pedestal_drift_band  | mid_pedestal          | template_residual_boosted_stack_new | 213 |                 5.818 |             0.3222 |            0.1789  |                     0.09114 |                  0.8863 |
| pid_separation       | deuteron              | 1d_cnn                              | 320 |                 8.914 |             0.3827 |            0.1582  |                     0.126   |                  0.7281 |
| pid_separation       | deuteron              | deltaE_over_E_likelihood_template   | 320 |                 9.191 |             0.6481 |            0.1582  |                     0.1018  |                  0.7469 |
| pid_separation       | deuteron              | gradient_boosted_trees              | 320 |                 5.311 |             0.2901 |            0.2468  |                     0.1012  |                  0.8938 |
| pid_separation       | deuteron              | joint_sequence_transformer          | 320 |                11.02  |             0.2716 |            0.2342  |                     0.1669  |                  0.5687 |
| pid_separation       | deuteron              | mlp                                 | 320 |                11.04  |             0.3148 |            0.2405  |                     0.1564  |                  0.7063 |
| pid_separation       | deuteron              | ridge                               | 320 |                 7.681 |             0.3272 |            0.2785  |                     0.1074  |                  0.6687 |
| pid_separation       | deuteron              | template_residual_boosted_stack_new | 320 |                 5.525 |             0.2778 |            0.2025  |                     0.09122 |                  0.9125 |
| pid_separation       | proton                | 1d_cnn                              | 320 |                 8.96  |             0.3608 |            0.1667  |                     0.1193  |                  0.825  |
| pid_separation       | proton                | deltaE_over_E_likelihood_template   | 320 |                 8.014 |             0.6139 |            0.09259 |                     0.1441  |                  0.8375 |
| pid_separation       | proton                | gradient_boosted_trees              | 320 |                 6.485 |             0.2911 |            0.2654  |                     0.106   |                  0.8125 |
| pid_separation       | proton                | joint_sequence_transformer          | 320 |                11.89  |             0.3228 |            0.2469  |                     0.1737  |                  0.5156 |
| pid_separation       | proton                | mlp                                 | 320 |                11.19  |             0.3101 |            0.2099  |                     0.1506  |                  0.8469 |
| pid_separation       | proton                | ridge                               | 320 |                 6.855 |             0.2911 |            0.2346  |                     0.1135  |                  0.85   |
| pid_separation       | proton                | template_residual_boosted_stack_new | 320 |                 6.762 |             0.3354 |            0.2099  |                     0.08946 |                  0.8156 |
| pileup_spacing_band  | merged                | 1d_cnn                              | 130 |                 6.573 |             0.5615 |          nan       |                     0.1281  |                  0.7391 |
| pileup_spacing_band  | merged                | deltaE_over_E_likelihood_template   | 130 |                 8.813 |             0.7769 |          nan       |                     0.1127  |                  0.7684 |
| pileup_spacing_band  | merged                | gradient_boosted_trees              | 130 |                 5.454 |             0.4462 |          nan       |                     0.1038  |                  0.8556 |
| pileup_spacing_band  | merged                | joint_sequence_transformer          | 130 |                10.86  |             0.4462 |          nan       |                     0.19    |                  0.5168 |
| pileup_spacing_band  | merged                | mlp                                 | 130 |                12.39  |             0.4769 |          nan       |                     0.1484  |                  0.7567 |
| pileup_spacing_band  | merged                | ridge                               | 130 |                 6.169 |             0.5    |          nan       |                     0.112   |                  0.7342 |
| pileup_spacing_band  | merged                | template_residual_boosted_stack_new | 130 |                 5.321 |             0.4538 |          nan       |                     0.08634 |                  0.8742 |
| pileup_spacing_band  | near                  | 1d_cnn                              |  87 |                 7.427 |             0.3103 |          nan       |                     0.1129  |                  0.781  |
| pileup_spacing_band  | near                  | deltaE_over_E_likelihood_template   |  87 |                 8.966 |             0.6437 |          nan       |                     0.1404  |                  0.7468 |
| pileup_spacing_band  | near                  | gradient_boosted_trees              |  87 |                 7.245 |             0.2184 |          nan       |                     0.1103  |                  0.8183 |
| pileup_spacing_band  | near                  | joint_sequence_transformer          |  87 |                13.36  |             0.2874 |          nan       |                     0.1655  |                  0.5952 |
| pileup_spacing_band  | near                  | mlp                                 |  87 |                11.36  |             0.2414 |          nan       |                     0.1323  |                  0.7802 |
| pileup_spacing_band  | near                  | ridge                               |  87 |                 7.385 |             0.2299 |          nan       |                     0.1187  |                  0.7437 |
| pileup_spacing_band  | near                  | template_residual_boosted_stack_new |  87 |                 5.838 |             0.2529 |          nan       |                     0.1067  |                  0.8302 |
| pileup_spacing_band  | separated             | 1d_cnn                              | 103 |                 6.765 |             0.1845 |          nan       |                     0.1256  |                  0.815  |
| pileup_spacing_band  | separated             | deltaE_over_E_likelihood_template   | 103 |                 7.772 |             0.4369 |          nan       |                     0.1328  |                  0.8737 |
| pileup_spacing_band  | separated             | gradient_boosted_trees              | 103 |                 5.124 |             0.1553 |          nan       |                     0.1023  |                  0.8541 |
| pileup_spacing_band  | separated             | joint_sequence_transformer          | 103 |                10.38  |             0.1165 |          nan       |                     0.1501  |                  0.5306 |
| pileup_spacing_band  | separated             | mlp                                 | 103 |                 9.793 |             0.165  |          nan       |                     0.1445  |                  0.8081 |
| pileup_spacing_band  | separated             | ridge                               | 103 |                 6.194 |             0.1359 |          nan       |                     0.1021  |                  0.7869 |
| pileup_spacing_band  | separated             | template_residual_boosted_stack_new | 103 |                 5.295 |             0.165  |          nan       |                     0.0895  |                  0.8665 |
| saturation_onset     | saturated             | 1d_cnn                              | 252 |                 8.023 |             0.3816 |            0.2     |                     0.09793 |                  0.7405 |
| saturation_onset     | saturated             | deltaE_over_E_likelihood_template   | 252 |                 9.076 |             0.6842 |            0.18    |                     0.1168  |                  0.7864 |
| saturation_onset     | saturated             | gradient_boosted_trees              | 252 |                 6.915 |             0.3026 |            0.39    |                     0.07361 |                  0.8614 |
| saturation_onset     | saturated             | joint_sequence_transformer          | 252 |                10.64  |             0.2961 |            0.32    |                     0.1281  |                  0.4981 |
| saturation_onset     | saturated             | mlp                                 | 252 |                11.78  |             0.3026 |            0.3     |                     0.1445  |                  0.7504 |
| saturation_onset     | saturated             | ridge                               | 252 |                 7.17  |             0.3158 |            0.36    |                     0.08618 |                  0.7121 |
| saturation_onset     | saturated             | template_residual_boosted_stack_new | 252 |                 6.111 |             0.3158 |            0.33    |                     0.06114 |                  0.853  |
| saturation_onset     | unsaturated           | 1d_cnn                              | 388 |                 8.152 |             0.3631 |            0.1455  |                     0.1373  |                  0.8002 |
| saturation_onset     | unsaturated           | deltaE_over_E_likelihood_template   | 388 |                 8.066 |             0.5833 |            0.1     |                     0.1244  |                  0.7944 |
| saturation_onset     | unsaturated           | gradient_boosted_trees              | 388 |                 5.132 |             0.2798 |            0.1955  |                     0.1249  |                  0.8459 |
| saturation_onset     | unsaturated           | joint_sequence_transformer          | 388 |                10.97  |             0.2976 |            0.2045  |                     0.1664  |                  0.5702 |
| saturation_onset     | unsaturated           | mlp                                 | 388 |                10.06  |             0.3214 |            0.1909  |                     0.1576  |                  0.7947 |
| saturation_onset     | unsaturated           | ridge                               | 388 |                 6.86  |             0.3036 |            0.2091  |                     0.1391  |                  0.7917 |
| saturation_onset     | unsaturated           | template_residual_boosted_stack_new | 388 |                 5.668 |             0.2976 |            0.15    |                     0.1235  |                  0.8693 |
| timing_pull_band     | high_abs_pull         | 1d_cnn                              | 241 |                15.18  |             0.4421 |            0.1301  |                     0.1322  |                  0.7734 |
| timing_pull_band     | high_abs_pull         | deltaE_over_E_likelihood_template   |  72 |                14.2   |             0.1951 |            0.4516  |                     0.1155  |                  0.7906 |
| timing_pull_band     | high_abs_pull         | gradient_boosted_trees              | 159 |                15.74  |             0.3962 |            0.1887  |                     0.0938  |                  0.8609 |
| timing_pull_band     | high_abs_pull         | joint_sequence_transformer          | 282 |                16.71  |             0.4065 |            0.1887  |                     0.2185  |                  0.5284 |
| timing_pull_band     | high_abs_pull         | mlp                                 | 283 |                17.71  |             0.4113 |            0.2013  |                     0.1703  |                  0.8066 |
| timing_pull_band     | high_abs_pull         | ridge                               | 156 |                14.23  |             0.3529 |            0.2727  |                     0.1456  |                  0.7874 |
| timing_pull_band     | high_abs_pull         | template_residual_boosted_stack_new | 158 |                15.26  |             0.3529 |            0.1402  |                     0.1018  |                  0.862  |
| timing_pull_band     | low_abs_pull          | 1d_cnn                              | 196 |                 2.123 |             0.3689 |            0.2366  |                     0.1197  |                  0.8019 |
| timing_pull_band     | low_abs_pull          | deltaE_over_E_likelihood_template   |  68 |                 2.292 |             0.2128 |            0.619   |                     0.1081  |                  0.8229 |
| timing_pull_band     | low_abs_pull          | gradient_boosted_trees              | 266 |                 2.318 |             0.2452 |            0.3423  |                     0.1014  |                  0.8449 |
| timing_pull_band     | low_abs_pull          | joint_sequence_transformer          | 156 |                 2.414 |             0.2025 |            0.2597  |                     0.145   |                  0.5972 |
| timing_pull_band     | low_abs_pull          | mlp                                 | 146 |                 2.404 |             0.2051 |            0.2941  |                     0.1158  |                  0.7744 |
| timing_pull_band     | low_abs_pull          | ridge                               | 235 |                 2.306 |             0.2966 |            0.3077  |                     0.107   |                  0.7653 |
| timing_pull_band     | low_abs_pull          | template_residual_boosted_stack_new | 284 |                 2.116 |             0.2683 |            0.2833  |                     0.09038 |                  0.8768 |
| timing_pull_band     | mid_abs_pull          | 1d_cnn                              | 203 |                 7.34  |             0.3197 |            0.1358  |                     0.1133  |                  0.756  |
| timing_pull_band     | mid_abs_pull          | deltaE_over_E_likelihood_template   |  73 |                 6.945 |             0.1111 |            0.6842  |                     0.1205  |                  0.8844 |
| timing_pull_band     | mid_abs_pull          | gradient_boosted_trees              | 215 |                 6.728 |             0.3036 |            0.233   |                     0.1142  |                  0.8585 |
| timing_pull_band     | mid_abs_pull          | joint_sequence_transformer          | 202 |                 7.359 |             0.2458 |            0.3214  |                     0.1591  |                  0.5185 |
| timing_pull_band     | mid_abs_pull          | mlp                                 | 211 |                 6.915 |             0.2797 |            0.2151  |                     0.1577  |                  0.7375 |
| timing_pull_band     | mid_abs_pull          | ridge                               | 249 |                 6.906 |             0.2985 |            0.1913  |                     0.09876 |                  0.7395 |
| timing_pull_band     | mid_abs_pull          | template_residual_boosted_stack_new | 198 |                 6.902 |             0.3429 |            0.1828  |                     0.0974  |                  0.8476 |

## Systematics And Caveats

The endpoint is a controlled architecture bakeoff, not a production particle-ID
calibration.  GEANT4 supplies event-aligned PID, energy, and timing labels, while
the ADC morphology is derived from raw B-stack templates and residual pools.
The ADC/MeV scale is fixed for ranking and is not an external calibration.
Saturation and pile-up labels are controlled labels in the digitized benchmark,
not independent hardware flags.  The 18-sample window limits sub-sample timing,
and pedestal motion is partly degenerate with late tails and curvature.  The
bootstrap intervals resample held-out runs, so they describe run-transfer
uncertainty and do not include GEANT4 physics-list, detector material, or
calibration uncertainty.

Runtime was `64.8` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

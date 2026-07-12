# S30b: pile-up saturation recovery energy-PID frontier

## Abstract

Ticket `1783829521.2969.5ac6067f` asks for a raw-ROOT-reproduced benchmark comparing a strong
traditional CFD/template chi-square timing method with ridge, gradient-boosted
trees, MLP, 1D-CNN, and a new sequence architecture on raw and
pedestal-subtracted pulse representations.  The claimed worker is `testbeam-laptop-2`.

The raw selected-pulse number is reproduced from ROOT: `640737`
selected B-stave pulses versus reference `640737`,
delta `0`.  The winner named in `result.json` is
**`template_residual_boosted_stack_new`** by the held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

The winning score is `0.2278`.  Its energy residual sigma68 is
`0.08885` with 95% run-block bootstrap CI
[`0.07498`, `0.1053`],
and its timing pull sigma68 is `8.208` ns with CI
[`7.605`, `8.714`].

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
| template_residual_boosted_stack_new |         0.2278 |    0.9331 |                  0.87   |           0.9097 |       0.8343 |                     0.08885 |                            0.07498 |                              0.1053 |             8.208 |                    7.605 |                     8.714 |             0.2844 |             0.2031 |
| gradient_boosted_trees              |         0.2294 |    0.9341 |                  0.878  |           0.9226 |       0.8387 |                     0.09504 |                            0.08341 |                              0.1108 |             8.006 |                    7.389 |                     8.763 |             0.2625 |             0.2125 |
| ridge                               |         0.2759 |    0.8366 |                  0.7639 |           0.7097 |       0.7857 |                     0.09099 |                            0.07066 |                              0.1173 |             9.995 |                    9.181 |                    10.97  |             0.3063 |             0.2125 |
| 1d_cnn                              |         0.3136 |    0.8433 |                  0.7798 |           0.7323 |       0.7993 |                     0.1152  |                            0.09001 |                              0.1349 |            11.55  |                   11.22  |                    12.19  |             0.3563 |             0.2    |
| deltaE_over_E_likelihood_template   |         0.3297 |    0.8317 |                  0.7972 |           0.7581 |       0.8131 |                     0.1275  |                            0.08799 |                              0.161  |            11.38  |                    9.613 |                    11.75  |             0.65   |             0.1031 |
| mlp                                 |         0.3625 |    0.854  |                  0.8017 |           0.8065 |       0.7886 |                     0.1637  |                            0.1505  |                              0.1932 |            11.95  |                   11.69  |                    12.7   |             0.375  |             0.2188 |
| joint_sequence_transformer          |         0.3757 |    0.5331 |                  0.5217 |           0.3677 |       0.5158 |                     0.1132  |                            0.08379 |                              0.1409 |            11.49  |                   10.43  |                    12.67  |             0.3469 |             0.2125 |

Relative to the traditional CFD/template baseline, `template_residual_boosted_stack_new` changes energy
sigma68 by `-0.03869`,
timing sigma68 by `-3.173` ns,
and PID balanced accuracy by `0.07278`.

## Raw Versus Pedestal-Subtracted Views

| input_view                       | methods                                                                                                    |    n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------------------|:-----------------------------------------------------------------------------------------------------------|-----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| raw_adc_sequence_view            | 1d_cnn, joint_sequence_transformer                                                                         | 1280 |                 9.669 |             0.3516 |             0.2062 |                      0.147  |                  0.6508 |
| pedestal_subtracted_feature_view | deltaE_over_E_likelihood_template, gradient_boosted_trees, mlp, ridge, template_residual_boosted_stack_new | 3200 |                 7.557 |             0.3756 |             0.19   |                      0.1256 |                  0.8222 |

## Run-Heldout Stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.7974 |           0.7547 |       0.7692 |                     0.1049  |            10.8   |             0.3594 |            0.2344  |
| 1d_cnn                              |            60 |                  0.7533 |           0.6949 |       0.7593 |                     0.08847 |            11.27  |             0.2812 |            0.3281  |
| 1d_cnn                              |            62 |                  0.7923 |           0.7733 |       0.8529 |                     0.1322  |            11.57  |             0.4219 |            0.2188  |
| 1d_cnn                              |            64 |                  0.7858 |           0.7333 |       0.8    |                     0.08004 |            11.3   |             0.4688 |            0.09375 |
| 1d_cnn                              |            65 |                  0.7646 |           0.6984 |       0.8    |                     0.1019  |            12.12  |             0.25   |            0.125   |
| deltaE_over_E_likelihood_template   |            58 |                  0.8001 |           0.7736 |       0.7593 |                     0.1271  |             8.275 |             0.6406 |            0.1094  |
| deltaE_over_E_likelihood_template   |            60 |                  0.8016 |           0.7627 |       0.8036 |                     0.09675 |            11.7   |             0.5625 |            0.1562  |
| deltaE_over_E_likelihood_template   |            62 |                  0.8057 |           0.8    |       0.8571 |                     0.1615  |            10.27  |             0.7188 |            0.03125 |
| deltaE_over_E_likelihood_template   |            64 |                  0.8172 |           0.7667 |       0.8364 |                     0.06412 |            11.27  |             0.7031 |            0.125   |
| deltaE_over_E_likelihood_template   |            65 |                  0.7567 |           0.6825 |       0.7963 |                     0.1239  |             9.722 |             0.625  |            0.09375 |
| gradient_boosted_trees              |            58 |                  0.8767 |           0.8868 |       0.8246 |                     0.09462 |             8.05  |             0.2031 |            0.3281  |
| gradient_boosted_trees              |            60 |                  0.9191 |           0.9831 |       0.8529 |                     0.08518 |             7.717 |             0.2656 |            0.2969  |
| gradient_boosted_trees              |            62 |                  0.8268 |           0.88   |       0.8462 |                     0.1128  |             8.384 |             0.3281 |            0.1562  |
| gradient_boosted_trees              |            64 |                  0.8838 |           0.9    |       0.8571 |                     0.07776 |             7.614 |             0.3281 |            0.2031  |
| gradient_boosted_trees              |            65 |                  0.8764 |           0.9683 |       0.8133 |                     0.09237 |             9.277 |             0.1875 |            0.07812 |
| joint_sequence_transformer          |            58 |                  0.4781 |           0.3962 |       0.3889 |                     0.09505 |            10.54  |             0.3125 |            0.2969  |
| joint_sequence_transformer          |            60 |                  0.5138 |           0.3898 |       0.4792 |                     0.1403  |            11.5   |             0.2969 |            0.25    |
| joint_sequence_transformer          |            62 |                  0.5679 |           0.4    |       0.6818 |                     0.1366  |            11.46  |             0.3438 |            0.1719  |
| joint_sequence_transformer          |            64 |                  0.549  |           0.3333 |       0.5556 |                     0.07194 |             9.919 |             0.4844 |            0.1875  |
| joint_sequence_transformer          |            65 |                  0.5126 |           0.3175 |       0.5128 |                     0.11    |            13.39  |             0.2969 |            0.1562  |
| mlp                                 |            58 |                  0.8057 |           0.8113 |       0.7414 |                     0.1548  |            11.5   |             0.4219 |            0.25    |
| mlp                                 |            60 |                  0.7932 |           0.7458 |       0.8    |                     0.1777  |            12.46  |             0.2812 |            0.3438  |
| mlp                                 |            62 |                  0.8229 |           0.8533 |       0.8533 |                     0.1739  |            12.74  |             0.375  |            0.2656  |
| mlp                                 |            64 |                  0.7824 |           0.8    |       0.75   |                     0.1239  |            12.45  |             0.4844 |            0.1562  |
| mlp                                 |            65 |                  0.7971 |           0.8095 |       0.7846 |                     0.1952  |            12.4   |             0.3125 |            0.07812 |
| ridge                               |            58 |                  0.7718 |           0.717  |       0.7451 |                     0.06077 |             8.651 |             0.2812 |            0.2812  |
| ridge                               |            60 |                  0.7266 |           0.6271 |       0.7551 |                     0.08369 |             9.481 |             0.1719 |            0.2969  |
| ridge                               |            62 |                  0.799  |           0.7867 |       0.8551 |                     0.1248  |            11.09  |             0.3594 |            0.1875  |
| ridge                               |            64 |                  0.7627 |           0.7167 |       0.7679 |                     0.08755 |             9.232 |             0.4062 |            0.1875  |
| ridge                               |            65 |                  0.749  |           0.6825 |       0.7818 |                     0.09254 |            11.2   |             0.3125 |            0.1094  |
| template_residual_boosted_stack_new |            58 |                  0.8379 |           0.8491 |       0.7759 |                     0.08262 |             7.92  |             0.2188 |            0.3281  |
| template_residual_boosted_stack_new |            60 |                  0.8936 |           0.9322 |       0.8462 |                     0.07339 |             7.333 |             0.2188 |            0.3125  |
| template_residual_boosted_stack_new |            62 |                  0.8618 |           0.8933 |       0.8816 |                     0.1148  |             8.53  |             0.375  |            0.1406  |
| template_residual_boosted_stack_new |            64 |                  0.8931 |           0.9333 |       0.8485 |                     0.08336 |             7.619 |             0.3594 |            0.1875  |
| template_residual_boosted_stack_new |            65 |                  0.8606 |           0.9365 |       0.8082 |                     0.08647 |             8.647 |             0.25   |            0.04688 |

## Curvature, Timing, Pedestal, Saturation, Energy, and PID Sidebands

| sideband             | value                 | method                              |   n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------|:----------------------|:------------------------------------|----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| curvature_band       | high_curvature        | 1d_cnn                              | 213 |                 9.763 |            0.106   |            0.4839  |                     0.1356  |                  0.7688 |
| curvature_band       | high_curvature        | deltaE_over_E_likelihood_template   | 213 |                 8.583 |            0.4305  |            0.2742  |                     0.1162  |                  0.7729 |
| curvature_band       | high_curvature        | gradient_boosted_trees              | 213 |                 5.224 |            0.09934 |            0.4032  |                     0.09583 |                  0.861  |
| curvature_band       | high_curvature        | joint_sequence_transformer          | 213 |                 8.61  |            0.1457  |            0.4032  |                     0.1336  |                  0.5085 |
| curvature_band       | high_curvature        | mlp                                 | 213 |                 9.828 |            0.1192  |            0.6129  |                     0.189   |                  0.7901 |
| curvature_band       | high_curvature        | ridge                               | 213 |                 7.234 |            0.08609 |            0.4032  |                     0.1066  |                  0.7455 |
| curvature_band       | high_curvature        | template_residual_boosted_stack_new | 213 |                 4.732 |            0.106   |            0.4194  |                     0.1013  |                  0.8712 |
| curvature_band       | low_curvature         | 1d_cnn                              | 214 |                 9.471 |            0.8814  |            0.01935 |                     0.1536  |                  0.7619 |
| curvature_band       | low_curvature         | deltaE_over_E_likelihood_template   | 214 |                 6.916 |            0.9153  |            0.02581 |                     0.1829  |                  0.7737 |
| curvature_band       | low_curvature         | gradient_boosted_trees              | 214 |                 9.22  |            0.6441  |            0.07742 |                     0.1469  |                  0.8547 |
| curvature_band       | low_curvature         | joint_sequence_transformer          | 214 |                12.37  |            0.8136  |            0.03226 |                     0.1413  |                  0.5064 |
| curvature_band       | low_curvature         | mlp                                 | 214 |                14.6   |            0.9661  |            0.01935 |                     0.1894  |                  0.7909 |
| curvature_band       | low_curvature         | ridge                               | 214 |                 7.668 |            0.7797  |            0.08387 |                     0.1494  |                  0.7609 |
| curvature_band       | low_curvature         | template_residual_boosted_stack_new | 214 |                 8.918 |            0.6441  |            0.07097 |                     0.1448  |                  0.8462 |
| curvature_band       | mid_curvature         | 1d_cnn                              | 213 |                 7.837 |            0.4182  |            0.301   |                     0.1534  |                  0.8117 |
| curvature_band       | mid_curvature         | deltaE_over_E_likelihood_template   | 213 |                 8.209 |            0.8091  |            0.1165  |                     0.1003  |                  0.8457 |
| curvature_band       | mid_curvature         | gradient_boosted_trees              | 213 |                 5.825 |            0.2818  |            0.301   |                     0.1064  |                  0.9163 |
| curvature_band       | mid_curvature         | joint_sequence_transformer          | 213 |                 7.594 |            0.3727  |            0.3689  |                     0.1317  |                  0.5163 |
| curvature_band       | mid_curvature         | mlp                                 | 213 |                 8.972 |            0.4091  |            0.2816  |                     0.1542  |                  0.8275 |
| curvature_band       | mid_curvature         | ridge                               | 213 |                 6.525 |            0.3545  |            0.2913  |                     0.1005  |                  0.788  |
| curvature_band       | mid_curvature         | template_residual_boosted_stack_new | 213 |                 5.627 |            0.3364  |            0.2718  |                     0.1047  |                  0.8927 |
| energy_residual_band | high_abs_energy_resid | 1d_cnn                              | 231 |                 9.701 |            0.6094  |            0.1138  |                     0.3447  |                  0.7503 |
| energy_residual_band | high_abs_energy_resid | deltaE_over_E_likelihood_template   |  44 |                10.44  |            0.2     |            0.5263  |                     0.3245  |                  0.725  |
| energy_residual_band | high_abs_energy_resid | gradient_boosted_trees              | 193 |                 7.708 |            0.5116  |            0.1     |                     0.3585  |                  0.8417 |
| energy_residual_band | high_abs_energy_resid | joint_sequence_transformer          | 235 |                 9.719 |            0.4688  |            0.1111  |                     0.3896  |                  0.5557 |
| energy_residual_band | high_abs_energy_resid | mlp                                 | 240 |                15.14  |            0.4375  |            0.1313  |                     0.4012  |                  0.7619 |
| energy_residual_band | high_abs_energy_resid | ridge                               | 213 |                 7.847 |            0.6383  |            0.1145  |                     0.3504  |                  0.7069 |
| energy_residual_band | high_abs_energy_resid | template_residual_boosted_stack_new | 191 |                 8.819 |            0.4615  |            0.07895 |                     0.3641  |                  0.8195 |
| energy_residual_band | low_abs_energy_resid  | 1d_cnn                              | 190 |                 9.521 |            0.168   |            0.3077  |                     0.04219 |                  0.8022 |
| energy_residual_band | low_abs_energy_resid  | deltaE_over_E_likelihood_template   |  93 |                 8.636 |            0.2162  |            0.4737  |                     0.04163 |                  0.8395 |
| energy_residual_band | low_abs_energy_resid  | gradient_boosted_trees              | 247 |                 5.932 |            0.1871  |            0.3684  |                     0.04117 |                  0.9136 |
| energy_residual_band | low_abs_energy_resid  | joint_sequence_transformer          | 182 |                 8.678 |            0.303   |            0.4     |                     0.0471  |                  0.4822 |
| energy_residual_band | low_abs_energy_resid  | mlp                                 | 147 |                 8.393 |            0.3596  |            0.3103  |                     0.04456 |                  0.8297 |
| energy_residual_band | low_abs_energy_resid  | ridge                               | 239 |                 7.242 |            0.2262  |            0.4085  |                     0.04083 |                  0.7857 |
| energy_residual_band | low_abs_energy_resid  | template_residual_boosted_stack_new | 249 |                 5.717 |            0.2035  |            0.4156  |                     0.03967 |                  0.9168 |
| energy_residual_band | mid_abs_energy_resid  | 1d_cnn                              | 219 |                 9.317 |            0.4122  |            0.2841  |                     0.14    |                  0.7904 |
| energy_residual_band | mid_abs_energy_resid  | deltaE_over_E_likelihood_template   |  63 |                 8.351 |            0.1282  |            0.5833  |                     0.1444  |                  0.8439 |
| energy_residual_band | mid_abs_energy_resid  | gradient_boosted_trees              | 200 |                 6.148 |            0.283   |            0.266   |                     0.1448  |                  0.87   |
| energy_residual_band | mid_abs_energy_resid  | joint_sequence_transformer          | 223 |                 9.353 |            0.3306  |            0.2929  |                     0.1368  |                  0.5216 |
| energy_residual_band | mid_abs_energy_resid  | mlp                                 | 253 |                 9.005 |            0.351   |            0.3039  |                     0.1363  |                  0.8221 |
| energy_residual_band | mid_abs_energy_resid  | ridge                               | 188 |                 7.216 |            0.2857  |            0.241   |                     0.1323  |                  0.7983 |
| energy_residual_band | mid_abs_energy_resid  | template_residual_boosted_stack_new | 200 |                 5.602 |            0.3486  |            0.2308  |                     0.1404  |                  0.8594 |
| pedestal_drift_band  | high_pedestal         | 1d_cnn                              | 213 |                 8.828 |            0.2255  |            0.2342  |                     0.1276  |                  0.7582 |
| pedestal_drift_band  | high_pedestal         | deltaE_over_E_likelihood_template   | 213 |                 5.682 |            0.5196  |            0.1081  |                     0.1261  |                  0.7681 |
| pedestal_drift_band  | high_pedestal         | gradient_boosted_trees              | 213 |                 4.727 |            0.1961  |            0.2252  |                     0.08502 |                  0.8706 |
| pedestal_drift_band  | high_pedestal         | joint_sequence_transformer          | 213 |                 8.151 |            0.2647  |            0.2523  |                     0.1344  |                  0.4743 |
| pedestal_drift_band  | high_pedestal         | mlp                                 | 213 |                 8.258 |            0.2941  |            0.1892  |                     0.1332  |                  0.8092 |
| pedestal_drift_band  | high_pedestal         | ridge                               | 213 |                 7.055 |            0.2255  |            0.2342  |                     0.08538 |                  0.7533 |
| pedestal_drift_band  | high_pedestal         | template_residual_boosted_stack_new | 213 |                 4.853 |            0.2059  |            0.2072  |                     0.09267 |                  0.8716 |
| pedestal_drift_band  | low_pedestal          | 1d_cnn                              | 214 |                10.02  |            0.4404  |            0.1619  |                     0.1673  |                  0.8149 |
| pedestal_drift_band  | low_pedestal          | deltaE_over_E_likelihood_template   | 214 |                10.29  |            0.7339  |            0.1143  |                     0.1275  |                  0.8015 |
| pedestal_drift_band  | low_pedestal          | gradient_boosted_trees              | 214 |                 6.906 |            0.3119  |            0.2     |                     0.1464  |                  0.8765 |
| pedestal_drift_band  | low_pedestal          | joint_sequence_transformer          | 214 |                 8.423 |            0.4037  |            0.181   |                     0.1902  |                  0.5556 |
| pedestal_drift_band  | low_pedestal          | mlp                                 | 214 |                11.28  |            0.3945  |            0.2857  |                     0.2556  |                  0.7814 |
| pedestal_drift_band  | low_pedestal          | ridge                               | 214 |                 8.899 |            0.3578  |            0.2095  |                     0.1478  |                  0.7644 |
| pedestal_drift_band  | low_pedestal          | template_residual_boosted_stack_new | 214 |                 6.178 |            0.3486  |            0.2     |                     0.1399  |                  0.8733 |
| pedestal_drift_band  | mid_pedestal          | 1d_cnn                              | 213 |                 9.978 |            0.3945  |            0.2019  |                     0.1375  |                  0.7643 |
| pedestal_drift_band  | mid_pedestal          | deltaE_over_E_likelihood_template   | 213 |                 6.295 |            0.6881  |            0.08654 |                     0.06425 |                  0.8236 |
| pedestal_drift_band  | mid_pedestal          | gradient_boosted_trees              | 213 |                 6.723 |            0.2752  |            0.2115  |                     0.1107  |                  0.8872 |
| pedestal_drift_band  | mid_pedestal          | joint_sequence_transformer          | 213 |                 9.372 |            0.367   |            0.2019  |                     0.13    |                  0.5373 |
| pedestal_drift_band  | mid_pedestal          | mlp                                 | 213 |                11.19  |            0.4312  |            0.1827  |                     0.1409  |                  0.8175 |
| pedestal_drift_band  | mid_pedestal          | ridge                               | 213 |                 6.453 |            0.3303  |            0.1923  |                     0.1176  |                  0.7746 |
| pedestal_drift_band  | mid_pedestal          | template_residual_boosted_stack_new | 213 |                 7.396 |            0.2936  |            0.2019  |                     0.1112  |                  0.8682 |
| pid_separation       | deuteron              | 1d_cnn                              | 310 |                 8.235 |            0.3082  |            0.2195  |                     0.1387  |                  0.7323 |
| pid_separation       | deuteron              | deltaE_over_E_likelihood_template   | 310 |                 8.03  |            0.5959  |            0.1037  |                     0.1133  |                  0.7581 |
| pid_separation       | deuteron              | gradient_boosted_trees              | 310 |                 5.618 |            0.226   |            0.2195  |                     0.09998 |                  0.9226 |
| pid_separation       | deuteron              | joint_sequence_transformer          | 310 |                 7.763 |            0.3288  |            0.2134  |                     0.1391  |                  0.3677 |
| pid_separation       | deuteron              | mlp                                 | 310 |                 9.642 |            0.3151  |            0.2378  |                     0.1536  |                  0.8065 |
| pid_separation       | deuteron              | ridge                               | 310 |                 6.628 |            0.2671  |            0.2256  |                     0.1041  |                  0.7097 |
| pid_separation       | deuteron              | template_residual_boosted_stack_new | 310 |                 5.63  |            0.2397  |            0.2134  |                     0.1051  |                  0.9097 |
| pid_separation       | proton                | 1d_cnn                              | 330 |                10.51  |            0.3966  |            0.1795  |                     0.1553  |                  0.8273 |
| pid_separation       | proton                | deltaE_over_E_likelihood_template   | 330 |                 9.443 |            0.6954  |            0.1026  |                     0.1313  |                  0.8364 |
| pid_separation       | proton                | gradient_boosted_trees              | 330 |                 6.563 |            0.2931  |            0.2051  |                     0.1219  |                  0.8333 |
| pid_separation       | proton                | joint_sequence_transformer          | 330 |                10.51  |            0.3621  |            0.2115  |                     0.1413  |                  0.6758 |
| pid_separation       | proton                | mlp                                 | 330 |                10.59  |            0.4253  |            0.1987  |                     0.17    |                  0.797  |
| pid_separation       | proton                | ridge                               | 330 |                 7.938 |            0.3391  |            0.1987  |                     0.127   |                  0.8182 |
| pid_separation       | proton                | template_residual_boosted_stack_new | 330 |                 6.384 |            0.3218  |            0.1923  |                     0.1159  |                  0.8303 |
| pileup_spacing_band  | merged                | 1d_cnn                              | 138 |                 7.484 |            0.4855  |          nan       |                     0.1377  |                  0.8117 |
| pileup_spacing_band  | merged                | deltaE_over_E_likelihood_template   | 138 |                 8.963 |            0.7536  |          nan       |                     0.09812 |                  0.8563 |
| pileup_spacing_band  | merged                | gradient_boosted_trees              | 138 |                 6.276 |            0.3841  |          nan       |                     0.09225 |                  0.9133 |
| pileup_spacing_band  | merged                | joint_sequence_transformer          | 138 |                 8.054 |            0.4783  |          nan       |                     0.1358  |                  0.5285 |
| pileup_spacing_band  | merged                | mlp                                 | 138 |                10.05  |            0.5072  |          nan       |                     0.1945  |                  0.833  |
| pileup_spacing_band  | merged                | ridge                               | 138 |                 6.59  |            0.3986  |          nan       |                     0.08063 |                  0.8181 |
| pileup_spacing_band  | merged                | template_residual_boosted_stack_new | 138 |                 6.053 |            0.3986  |          nan       |                     0.09644 |                  0.8964 |
| pileup_spacing_band  | near                  | 1d_cnn                              |  61 |                 7.83  |            0.4426  |          nan       |                     0.1326  |                  0.7802 |
| pileup_spacing_band  | near                  | deltaE_over_E_likelihood_template   |  61 |                 9.613 |            0.7213  |          nan       |                     0.08381 |                  0.761  |
| pileup_spacing_band  | near                  | gradient_boosted_trees              |  61 |                 5.887 |            0.3115  |          nan       |                     0.09408 |                  0.9088 |
| pileup_spacing_band  | near                  | joint_sequence_transformer          |  61 |                 9.42  |            0.3443  |          nan       |                     0.1319  |                  0.6462 |
| pileup_spacing_band  | near                  | mlp                                 |  61 |                 9.709 |            0.4754  |          nan       |                     0.1473  |                  0.7989 |
| pileup_spacing_band  | near                  | ridge                               |  61 |                 6.488 |            0.377   |          nan       |                     0.1064  |                  0.7753 |
| pileup_spacing_band  | near                  | template_residual_boosted_stack_new |  61 |                 6.888 |            0.3443  |          nan       |                     0.1005  |                  0.856  |
| pileup_spacing_band  | separated             | 1d_cnn                              | 121 |                 7.635 |            0.1653  |          nan       |                     0.1547  |                  0.7834 |
| pileup_spacing_band  | separated             | deltaE_over_E_likelihood_template   | 121 |                 6.448 |            0.4959  |          nan       |                     0.1372  |                  0.7978 |
| pileup_spacing_band  | separated             | gradient_boosted_trees              | 121 |                 5.331 |            0.09917 |          nan       |                     0.1215  |                  0.9107 |
| pileup_spacing_band  | separated             | joint_sequence_transformer          | 121 |                 9.898 |            0.1983  |          nan       |                     0.1515  |                  0.477  |
| pileup_spacing_band  | separated             | mlp                                 | 121 |                 9.633 |            0.1736  |          nan       |                     0.1627  |                  0.7784 |
| pileup_spacing_band  | separated             | ridge                               | 121 |                 7.977 |            0.1653  |          nan       |                     0.1139  |                  0.7352 |
| pileup_spacing_band  | separated             | template_residual_boosted_stack_new | 121 |                 5.496 |            0.124   |          nan       |                     0.1174  |                  0.9156 |
| saturation_onset     | saturated             | 1d_cnn                              | 236 |                 8.763 |            0.4714  |            0.1875  |                     0.1321  |                  0.7802 |
| saturation_onset     | saturated             | deltaE_over_E_likelihood_template   | 236 |                10.57  |            0.75    |            0.125   |                     0.1096  |                  0.8069 |
| saturation_onset     | saturated             | gradient_boosted_trees              | 236 |                 6.152 |            0.2643  |            0.3229  |                     0.07442 |                  0.8908 |
| saturation_onset     | saturated             | joint_sequence_transformer          | 236 |                 8.232 |            0.4429  |            0.2292  |                     0.1321  |                  0.5294 |
| saturation_onset     | saturated             | mlp                                 | 236 |                 9.657 |            0.3786  |            0.3021  |                     0.194   |                  0.771  |
| saturation_onset     | saturated             | ridge                               | 236 |                 7.097 |            0.2929  |            0.2708  |                     0.07944 |                  0.7287 |
| saturation_onset     | saturated             | template_residual_boosted_stack_new | 236 |                 5.633 |            0.2786  |            0.3229  |                     0.08159 |                  0.8659 |
| saturation_onset     | unsaturated           | 1d_cnn                              | 404 |                 9.644 |            0.2667  |            0.2054  |                     0.1632  |                  0.7751 |
| saturation_onset     | unsaturated           | deltaE_over_E_likelihood_template   | 404 |                 6.443 |            0.5722  |            0.09375 |                     0.1363  |                  0.7841 |
| saturation_onset     | unsaturated           | gradient_boosted_trees              | 404 |                 5.78  |            0.2611  |            0.1652  |                     0.1478  |                  0.871  |
| saturation_onset     | unsaturated           | joint_sequence_transformer          | 404 |                 9.034 |            0.2722  |            0.2054  |                     0.1745  |                  0.5164 |
| saturation_onset     | unsaturated           | mlp                                 | 404 |                10.3   |            0.3722  |            0.183   |                     0.1462  |                  0.8202 |
| saturation_onset     | unsaturated           | ridge                               | 404 |                 7.246 |            0.3167  |            0.1875  |                     0.1388  |                  0.7843 |
| saturation_onset     | unsaturated           | template_residual_boosted_stack_new | 404 |                 5.58  |            0.2889  |            0.1518  |                     0.1431  |                  0.8732 |
| timing_pull_band     | high_abs_pull         | 1d_cnn                              | 252 |                15.59  |            0.3396  |            0.137   |                     0.1313  |                  0.7928 |
| timing_pull_band     | high_abs_pull         | deltaE_over_E_likelihood_template   |  65 |                15.76  |            0.3056  |            0.3793  |                     0.1267  |                  0.8461 |
| timing_pull_band     | high_abs_pull         | gradient_boosted_trees              | 154 |                14.65  |            0.4237  |            0.1368  |                     0.1498  |                  0.9182 |
| timing_pull_band     | high_abs_pull         | joint_sequence_transformer          | 261 |                16.34  |            0.3729  |            0.1189  |                     0.1466  |                  0.4745 |
| timing_pull_band     | high_abs_pull         | mlp                                 | 285 |                18.62  |            0.4561  |            0.1871  |                     0.2534  |                  0.816  |
| timing_pull_band     | high_abs_pull         | ridge                               | 180 |                16.33  |            0.3803  |            0.1101  |                     0.1405  |                  0.7477 |
| timing_pull_band     | high_abs_pull         | template_residual_boosted_stack_new | 150 |                15.29  |            0.4902  |            0.1515  |                     0.1303  |                  0.9139 |
| timing_pull_band     | low_abs_pull          | 1d_cnn                              | 190 |                 2.545 |            0.3431  |            0.2841  |                     0.1383  |                  0.7713 |
| timing_pull_band     | low_abs_pull          | deltaE_over_E_likelihood_template   |  62 |                 2.712 |            0.1731  |            0.7     |                     0.09377 |                  0.8198 |
| timing_pull_band     | low_abs_pull          | gradient_boosted_trees              | 266 |                 2.207 |            0.242   |            0.2752  |                     0.121   |                  0.8868 |
| timing_pull_band     | low_abs_pull          | joint_sequence_transformer          | 165 |                 2.467 |            0.3261  |            0.274   |                     0.1302  |                  0.5379 |
| timing_pull_band     | low_abs_pull          | mlp                                 | 154 |                 2.597 |            0.3571  |            0.2571  |                     0.1625  |                  0.7289 |
| timing_pull_band     | low_abs_pull          | ridge                               | 243 |                 2.721 |            0.3047  |            0.2174  |                     0.1276  |                  0.7689 |
| timing_pull_band     | low_abs_pull          | template_residual_boosted_stack_new | 267 |                 2.394 |            0.271   |            0.2143  |                     0.1165  |                  0.8748 |
| timing_pull_band     | mid_abs_pull          | 1d_cnn                              | 198 |                 7.167 |            0.3839  |            0.2209  |                     0.1715  |                  0.7685 |
| timing_pull_band     | mid_abs_pull          | deltaE_over_E_likelihood_template   |  73 |                 6.698 |            0.12    |            0.6522  |                     0.1414  |                  0.7884 |
| timing_pull_band     | mid_abs_pull          | gradient_boosted_trees              | 220 |                 6.649 |            0.2019  |            0.2155  |                     0.083   |                  0.8408 |
| timing_pull_band     | mid_abs_pull          | joint_sequence_transformer          | 214 |                 6.652 |            0.3364  |            0.2981  |                     0.1399  |                  0.5518 |
| timing_pull_band     | mid_abs_pull          | mlp                                 | 201 |                 7.292 |            0.3115  |            0.2532  |                     0.127   |                  0.8409 |
| timing_pull_band     | mid_abs_pull          | ridge                               | 217 |                 6.984 |            0.2645  |            0.3229  |                     0.08784 |                  0.7717 |
| timing_pull_band     | mid_abs_pull          | template_residual_boosted_stack_new | 223 |                 6.762 |            0.2105  |            0.2385  |                     0.08254 |                  0.8344 |

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

Runtime was `83.6` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

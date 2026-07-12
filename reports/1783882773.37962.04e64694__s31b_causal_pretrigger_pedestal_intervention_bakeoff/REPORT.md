# S31b: causal pretrigger pedestal intervention bakeoff

## Abstract

Ticket `1783882773.37962.04e64694` asks for a raw-ROOT-reproduced benchmark comparing causal
pretrigger pedestal interventions: a strong traditional pretrigger-window
subtraction plus AR-style pedestal extrapolation/template baseline against
ridge, gradient-boosted trees, MLP, 1D-CNN, and a masked/sequence transformer
waveform model.  The claimed worker is `testbeam-laptop-4`.

The raw selected-pulse number is reproduced from ROOT: `640737`
selected B-stave pulses versus reference `640737`,
delta `0`.  The winner named in `result.json` is
**`gradient_boosted_trees`** by the held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

The winning score is `0.2232`.  Its energy residual sigma68 is
`0.08764` with 95% run-block bootstrap CI
[`0.0731`, `0.1051`],
and its timing pull sigma68 is `7.8` ns with CI
[`7.338`, `8.552`].

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

Two causal pedestal views are audited.  Raw-sequence models (`1d_cnn`,
`joint_sequence_transformer`) consume the 18-sample ADC sequence after internal
normalization, with the transformer treated as the masked waveform architecture
because its attention encoder is trained to infer downstream heads from the
short causal waveform context.  Feature and template models consume
pretrigger-subtracted and AR-extrapolated pedestal summaries: the constant
pretrigger estimate `b0=median(x[0:4])`, the local slope proxy
`s=(x[3]-x[0])/3`, and an extrapolated baseline
`b_AR(t)=b0+s(t-1.5)` inside the pulse window.  This separation tests whether
learned waveform capacity is useful beyond a transparent causal pedestal
intervention.

## Methods

The strong traditional baseline is `deltaE_over_E_likelihood_template`, a
train-run pretrigger/AR pedestal intervention followed by template/CFD
two-pulse fitting and a diagonal Gaussian PID likelihood.  For a class `y` and
standardized feature vector `z`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP,
`1d_cnn`, and the new masked/sequence `joint_sequence_transformer`.  A second new architecture,
`template_residual_boosted_stack_new`, residualizes the traditional template
fit and lets boosted trees model the remaining nonlinear structure.

For accepted pile-up doublets,

`e_t = 10 ns (hat t_1 - t_1)`,

`e_E = [(hat A_1 + hat A_2) - A_true] / A_true`,

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

Pile-up sensitivity is reported as the held-out miss rate for true overlaps and
false split rate for singles.  Pedestal drift is stratified by the raw
pretrigger median `b_c`; amplitude-stratified folds are defined by tertiles of
the GEANT4-aligned ADC energy proxy.  Saturation onset is stratified by
`max_t y_c(t) > 14000 ADC`.  Curvature is represented by
`sum_t y(t) / max_t y(t)`, which captures broad/late tails at fixed amplitude.

## Overall Results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees              |         0.2232 |    0.9383 |                  0.8687 |           0.9161 |       0.828  |                     0.08764 |                            0.0731  |                              0.1051 |             7.8   |                    7.338 |                     8.552 |             0.2969 |             0.1969 |
| template_residual_boosted_stack_new |         0.2304 |    0.9309 |                  0.8673 |           0.9194 |       0.8237 |                     0.09209 |                            0.07545 |                              0.1048 |             8.087 |                    7.462 |                     8.823 |             0.2781 |             0.2062 |
| ridge                               |         0.2759 |    0.8366 |                  0.7639 |           0.7097 |       0.7857 |                     0.09099 |                            0.07066 |                              0.1173 |             9.995 |                    9.181 |                    10.97  |             0.3063 |             0.2125 |
| 1d_cnn                              |         0.3042 |    0.8305 |                  0.7587 |           0.6871 |       0.7918 |                     0.1043  |                            0.08192 |                              0.1224 |            11.22  |                   10.64  |                    11.7   |             0.3531 |             0.1938 |
| deltaE_over_E_likelihood_template   |         0.3297 |    0.8317 |                  0.7972 |           0.7581 |       0.8131 |                     0.1275  |                            0.08799 |                              0.161  |            11.38  |                    9.613 |                    11.75  |             0.65   |             0.1031 |
| mlp                                 |         0.3625 |    0.854  |                  0.8017 |           0.8065 |       0.7886 |                     0.1637  |                            0.1505  |                              0.1932 |            11.95  |                   11.69  |                    12.7   |             0.375  |             0.2188 |
| joint_sequence_transformer          |         0.3804 |    0.5299 |                  0.5162 |           0.3839 |       0.5064 |                     0.1139  |                            0.08327 |                              0.1393 |            11.75  |                   10.1   |                    12.83  |             0.325  |             0.2375 |

Relative to the traditional CFD/template baseline, `gradient_boosted_trees` changes energy
sigma68 by `-0.0399`,
timing sigma68 by `-3.581` ns,
and PID balanced accuracy by `0.07146`.

## Causal Pedestal Intervention Views

| input_view                       | methods                                                                                                    |    n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------------------|:-----------------------------------------------------------------------------------------------------------|-----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| raw_adc_sequence_view            | 1d_cnn, joint_sequence_transformer                                                                         | 1280 |                 9.867 |             0.3391 |             0.2156 |                      0.1451 |                  0.6374 |
| pedestal_subtracted_feature_view | deltaE_over_E_likelihood_template, gradient_boosted_trees, mlp, ridge, template_residual_boosted_stack_new | 3200 |                 7.328 |             0.3812 |             0.1875 |                      0.1257 |                  0.8198 |

## Run-Heldout Stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.804  |           0.7547 |       0.7843 |                     0.1035  |            10.7   |             0.3281 |            0.2188  |
| 1d_cnn                              |            60 |                  0.6927 |           0.5593 |       0.7333 |                     0.07803 |            11.97  |             0.2656 |            0.3125  |
| 1d_cnn                              |            62 |                  0.7857 |           0.76   |       0.8507 |                     0.1167  |            11.28  |             0.4219 |            0.2188  |
| 1d_cnn                              |            64 |                  0.7701 |           0.7167 |       0.7818 |                     0.07112 |            10.67  |             0.4844 |            0.09375 |
| 1d_cnn                              |            65 |                  0.7328 |           0.6349 |       0.7843 |                     0.09723 |            11.15  |             0.2656 |            0.125   |
| deltaE_over_E_likelihood_template   |            58 |                  0.8001 |           0.7736 |       0.7593 |                     0.1271  |             8.275 |             0.6406 |            0.1094  |
| deltaE_over_E_likelihood_template   |            60 |                  0.8016 |           0.7627 |       0.8036 |                     0.09675 |            11.7   |             0.5625 |            0.1562  |
| deltaE_over_E_likelihood_template   |            62 |                  0.8057 |           0.8    |       0.8571 |                     0.1615  |            10.27  |             0.7188 |            0.03125 |
| deltaE_over_E_likelihood_template   |            64 |                  0.8172 |           0.7667 |       0.8364 |                     0.06412 |            11.27  |             0.7031 |            0.125   |
| deltaE_over_E_likelihood_template   |            65 |                  0.7567 |           0.6825 |       0.7963 |                     0.1239  |             9.722 |             0.625  |            0.09375 |
| gradient_boosted_trees              |            58 |                  0.8862 |           0.9057 |       0.8276 |                     0.08735 |             7.756 |             0.1875 |            0.3125  |
| gradient_boosted_trees              |            60 |                  0.9033 |           0.9661 |       0.8382 |                     0.07448 |             6.694 |             0.2969 |            0.2969  |
| gradient_boosted_trees              |            62 |                  0.8335 |           0.8933 |       0.8481 |                     0.1082  |             7.829 |             0.3438 |            0.1406  |
| gradient_boosted_trees              |            64 |                  0.8691 |           0.9    |       0.8308 |                     0.07241 |             6.843 |             0.3281 |            0.1719  |
| gradient_boosted_trees              |            65 |                  0.8449 |           0.9206 |       0.7945 |                     0.08967 |             8.91  |             0.3281 |            0.0625  |
| joint_sequence_transformer          |            58 |                  0.4648 |           0.3962 |       0.375  |                     0.09522 |             9.833 |             0.2656 |            0.3281  |
| joint_sequence_transformer          |            60 |                  0.5005 |           0.4068 |       0.4615 |                     0.1427  |            11.71  |             0.2969 |            0.2812  |
| joint_sequence_transformer          |            62 |                  0.5879 |           0.44   |       0.7021 |                     0.1348  |            11.72  |             0.3281 |            0.1719  |
| joint_sequence_transformer          |            64 |                  0.527  |           0.3333 |       0.5128 |                     0.07019 |            10.46  |             0.4531 |            0.2344  |
| joint_sequence_transformer          |            65 |                  0.5128 |           0.3333 |       0.5122 |                     0.1081  |            13.56  |             0.2812 |            0.1719  |
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
| template_residual_boosted_stack_new |            58 |                  0.8606 |           0.8679 |       0.807  |                     0.09039 |             7.887 |             0.2031 |            0.3125  |
| template_residual_boosted_stack_new |            60 |                  0.8936 |           0.9322 |       0.8462 |                     0.07048 |             6.966 |             0.2344 |            0.2812  |
| template_residual_boosted_stack_new |            62 |                  0.8335 |           0.8933 |       0.8481 |                     0.1289  |             7.946 |             0.3594 |            0.1562  |
| template_residual_boosted_stack_new |            64 |                  0.8618 |           0.9    |       0.8182 |                     0.09155 |             7.006 |             0.375  |            0.2031  |
| template_residual_boosted_stack_new |            65 |                  0.8769 |           1      |       0.7975 |                     0.08912 |             8.981 |             0.2188 |            0.07812 |

## Shape, Timing, Pile-Up, Saturation, Energy, PID, and Amplitude Sidebands

| sideband             | value                 | method                              |   n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------|:----------------------|:------------------------------------|----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| amplitude_stratum    | high_amplitude        | 1d_cnn                              | 301 |                 9.862 |            0.4265  |            0.1818  |                     0.1529  |                  0.7143 |
| amplitude_stratum    | high_amplitude        | gradient_boosted_trees              | 289 |                 5.355 |            0.2823  |            0.1758  |                     0.107   |                  0.802  |
| amplitude_stratum    | high_amplitude        | joint_sequence_transformer          | 301 |                 8.761 |            0.375   |            0.2242  |                     0.1514  |                  0.5347 |
| amplitude_stratum    | high_amplitude        | mlp                                 | 301 |                 8.762 |            0.3603  |            0.2061  |                     0.1666  |                  0.756  |
| amplitude_stratum    | high_amplitude        | template_residual_boosted_stack_new | 301 |                 5.263 |            0.2941  |            0.1697  |                     0.1099  |                  0.7961 |
| amplitude_stratum    | low_amplitude         | 1d_cnn                              | 213 |                 9.135 |            0.3274  |            0.22    |                     0.1006  |                  0.8124 |
| amplitude_stratum    | low_amplitude         | deltaE_over_E_likelihood_template   | 214 |                 9.385 |            0.6228  |            0.1     |                     0.1052  |                  0.8059 |
| amplitude_stratum    | low_amplitude         | gradient_boosted_trees              | 214 |                 5.993 |            0.3684  |            0.2     |                     0.09175 |                  0.9003 |
| amplitude_stratum    | low_amplitude         | joint_sequence_transformer          | 213 |                 9.836 |            0.292   |            0.25    |                     0.124   |                  0.5651 |
| amplitude_stratum    | low_amplitude         | mlp                                 | 213 |                12.57  |            0.4867  |            0.25    |                     0.1386  |                  0.8838 |
| amplitude_stratum    | low_amplitude         | ridge                               | 214 |                 8.257 |            0.4035  |            0.19    |                     0.09015 |                  0.8991 |
| amplitude_stratum    | low_amplitude         | template_residual_boosted_stack_new | 213 |                 5.571 |            0.3097  |            0.22    |                     0.09201 |                  0.9073 |
| amplitude_stratum    | mid_amplitude         | 1d_cnn                              | 126 |                 9.861 |            0.2535  |            0.1818  |                     0.149   |                  0.7698 |
| amplitude_stratum    | mid_amplitude         | deltaE_over_E_likelihood_template   | 426 |                 7.962 |            0.665   |            0.1045  |                     0.1152  |                  0.7862 |
| amplitude_stratum    | mid_amplitude         | gradient_boosted_trees              | 137 |                 7.819 |            0.2195  |            0.2545  |                     0.09468 |                  0.9555 |
| amplitude_stratum    | mid_amplitude         | joint_sequence_transformer          | 126 |                 8.682 |            0.2817  |            0.2545  |                     0.1369  |                  0.4048 |
| amplitude_stratum    | mid_amplitude         | mlp                                 | 126 |                10.1   |            0.2254  |            0.2     |                     0.1683  |                  0.7698 |
| amplitude_stratum    | mid_amplitude         | ridge                               | 426 |                 7.145 |            0.2524  |            0.2227  |                     0.1219  |                  0.7007 |
| amplitude_stratum    | mid_amplitude         | template_residual_boosted_stack_new | 126 |                 7.213 |            0.1972  |            0.2909  |                     0.105   |                  0.9683 |
| curvature_band       | high_curvature        | 1d_cnn                              | 213 |                 9.22  |            0.1126  |            0.4839  |                     0.1219  |                  0.7197 |
| curvature_band       | high_curvature        | deltaE_over_E_likelihood_template   | 213 |                 8.583 |            0.4305  |            0.2742  |                     0.1162  |                  0.7729 |
| curvature_band       | high_curvature        | gradient_boosted_trees              | 213 |                 4.909 |            0.1258  |            0.3871  |                     0.09897 |                  0.861  |
| curvature_band       | high_curvature        | joint_sequence_transformer          | 214 |                 8.862 |            0.1513  |            0.4516  |                     0.1344  |                  0.5005 |
| curvature_band       | high_curvature        | mlp                                 | 213 |                 9.828 |            0.1192  |            0.6129  |                     0.189   |                  0.7901 |
| curvature_band       | high_curvature        | ridge                               | 213 |                 7.234 |            0.08609 |            0.4032  |                     0.1066  |                  0.7455 |
| curvature_band       | high_curvature        | template_residual_boosted_stack_new | 214 |                 4.56  |            0.09868 |            0.4032  |                     0.0982  |                  0.8756 |
| curvature_band       | low_curvature         | 1d_cnn                              | 213 |                 8.913 |            0.8966  |            0.01935 |                     0.1567  |                  0.7497 |
| curvature_band       | low_curvature         | deltaE_over_E_likelihood_template   | 214 |                 6.916 |            0.9153  |            0.02581 |                     0.1829  |                  0.7737 |
| curvature_band       | low_curvature         | gradient_boosted_trees              | 214 |                 8.777 |            0.678   |            0.07097 |                     0.1412  |                  0.8505 |
| curvature_band       | low_curvature         | joint_sequence_transformer          | 213 |                12.47  |            0.7586  |            0.05161 |                     0.1494  |                  0.5079 |
| curvature_band       | low_curvature         | mlp                                 | 213 |                14.96  |            0.9655  |            0.01935 |                     0.1933  |                  0.7899 |
| curvature_band       | low_curvature         | ridge                               | 214 |                 7.668 |            0.7797  |            0.08387 |                     0.1494  |                  0.7609 |
| curvature_band       | low_curvature         | template_residual_boosted_stack_new | 213 |                 9.334 |            0.6724  |            0.07742 |                     0.1284  |                  0.8515 |
| curvature_band       | mid_curvature         | 1d_cnn                              | 214 |                 7.686 |            0.3964  |            0.2816  |                     0.1404  |                  0.8128 |
| curvature_band       | mid_curvature         | deltaE_over_E_likelihood_template   | 213 |                 8.209 |            0.8091  |            0.1165  |                     0.1003  |                  0.8457 |
| curvature_band       | mid_curvature         | gradient_boosted_trees              | 213 |                 5.525 |            0.3273  |            0.2718  |                     0.09884 |                  0.893  |
| curvature_band       | mid_curvature         | joint_sequence_transformer          | 213 |                 7.984 |            0.3364  |            0.3883  |                     0.1278  |                  0.5069 |
| curvature_band       | mid_curvature         | mlp                                 | 214 |                 8.948 |            0.4144  |            0.2816  |                     0.154   |                  0.8284 |
| curvature_band       | mid_curvature         | ridge                               | 213 |                 6.525 |            0.3545  |            0.2913  |                     0.1005  |                  0.788  |
| curvature_band       | mid_curvature         | template_residual_boosted_stack_new | 213 |                 5.423 |            0.3182  |            0.2816  |                     0.1141  |                  0.8744 |
| energy_residual_band | high_abs_energy_resid | 1d_cnn                              | 241 |                 9.915 |            0.6094  |            0.1243  |                     0.3249  |                  0.7448 |
| energy_residual_band | high_abs_energy_resid | deltaE_over_E_likelihood_template   |  43 |                 8.428 |            0.2083  |            0.5263  |                     0.3255  |                  0.7171 |
| energy_residual_band | high_abs_energy_resid | gradient_boosted_trees              | 196 |                 7.537 |            0.5476  |            0.07792 |                     0.3722  |                  0.8238 |
| energy_residual_band | high_abs_energy_resid | joint_sequence_transformer          | 235 |                10.08  |            0.4688  |            0.1462  |                     0.3924  |                  0.551  |
| energy_residual_band | high_abs_energy_resid | mlp                                 | 238 |                15.14  |            0.4375  |            0.1329  |                     0.4012  |                  0.7599 |
| energy_residual_band | high_abs_energy_resid | ridge                               | 211 |                 7.876 |            0.6304  |            0.1152  |                     0.3573  |                  0.7095 |
| energy_residual_band | high_abs_energy_resid | template_residual_boosted_stack_new | 183 |                 9.389 |            0.5263  |            0.08276 |                     0.3698  |                  0.8453 |
| energy_residual_band | low_abs_energy_resid  | 1d_cnn                              | 185 |                 8.979 |            0.1429  |            0.339   |                     0.04411 |                  0.7715 |
| energy_residual_band | low_abs_energy_resid  | deltaE_over_E_likelihood_template   |  94 |                 8.579 |            0.2133  |            0.4737  |                     0.0419  |                  0.8404 |
| energy_residual_band | low_abs_energy_resid  | gradient_boosted_trees              | 234 |                 5.855 |            0.2189  |            0.3846  |                     0.04112 |                  0.8998 |
| energy_residual_band | low_abs_energy_resid  | joint_sequence_transformer          | 190 |                 8.372 |            0.2537  |            0.4107  |                     0.04652 |                  0.4933 |
| energy_residual_band | low_abs_energy_resid  | mlp                                 | 152 |                 8.518 |            0.3404  |            0.3103  |                     0.04682 |                  0.8281 |
| energy_residual_band | low_abs_energy_resid  | ridge                               | 243 |                 7.217 |            0.2222  |            0.4028  |                     0.04191 |                  0.79   |
| energy_residual_band | low_abs_energy_resid  | template_residual_boosted_stack_new | 249 |                 5.428 |            0.191   |            0.3944  |                     0.04565 |                  0.8943 |
| energy_residual_band | mid_abs_energy_resid  | 1d_cnn                              | 214 |                 9.547 |            0.4308  |            0.2381  |                     0.1305  |                  0.7617 |
| energy_residual_band | mid_abs_energy_resid  | deltaE_over_E_likelihood_template   |  63 |                 8.63  |            0.1282  |            0.5833  |                     0.1456  |                  0.8439 |
| energy_residual_band | mid_abs_energy_resid  | gradient_boosted_trees              | 210 |                 5.367 |            0.3211  |            0.2574  |                     0.1379  |                  0.8757 |
| energy_residual_band | mid_abs_energy_resid  | joint_sequence_transformer          | 215 |                 9.648 |            0.3279  |            0.3011  |                     0.1402  |                  0.4998 |
| energy_residual_band | mid_abs_energy_resid  | mlp                                 | 250 |                 8.945 |            0.363   |            0.2981  |                     0.1384  |                  0.824  |
| energy_residual_band | mid_abs_energy_resid  | ridge                               | 186 |                 7.208 |            0.301   |            0.241   |                     0.1347  |                  0.7894 |
| energy_residual_band | mid_abs_energy_resid  | template_residual_boosted_stack_new | 208 |                 4.986 |            0.3365  |            0.25    |                     0.1439  |                  0.8548 |
| pedestal_drift_band  | high_pedestal         | 1d_cnn                              | 213 |                 8.437 |            0.2353  |            0.2342  |                     0.1182  |                  0.7335 |
| pedestal_drift_band  | high_pedestal         | deltaE_over_E_likelihood_template   | 213 |                 5.682 |            0.5196  |            0.1081  |                     0.1261  |                  0.7681 |
| pedestal_drift_band  | high_pedestal         | gradient_boosted_trees              | 213 |                 4.934 |            0.2353  |            0.2162  |                     0.08321 |                  0.8612 |
| pedestal_drift_band  | high_pedestal         | joint_sequence_transformer          | 214 |                 8.108 |            0.2255  |            0.2768  |                     0.1368  |                  0.4831 |
| pedestal_drift_band  | high_pedestal         | mlp                                 | 213 |                 8.258 |            0.2941  |            0.1892  |                     0.1332  |                  0.8092 |
| pedestal_drift_band  | high_pedestal         | ridge                               | 213 |                 7.055 |            0.2255  |            0.2342  |                     0.08538 |                  0.7533 |
| pedestal_drift_band  | high_pedestal         | template_residual_boosted_stack_new | 214 |                 4.973 |            0.2157  |            0.2232  |                     0.09191 |                  0.8719 |
| pedestal_drift_band  | low_pedestal          | 1d_cnn                              | 213 |                11.39  |            0.422   |            0.1538  |                     0.164   |                  0.7778 |
| pedestal_drift_band  | low_pedestal          | deltaE_over_E_likelihood_template   | 214 |                10.29  |            0.7339  |            0.1143  |                     0.1275  |                  0.8015 |
| pedestal_drift_band  | low_pedestal          | gradient_boosted_trees              | 214 |                 6.681 |            0.3394  |            0.1619  |                     0.1389  |                  0.8761 |
| pedestal_drift_band  | low_pedestal          | joint_sequence_transformer          | 213 |                 9.184 |            0.3945  |            0.2115  |                     0.1912  |                  0.5568 |
| pedestal_drift_band  | low_pedestal          | mlp                                 | 213 |                11.28  |            0.3945  |            0.2885  |                     0.2556  |                  0.7803 |
| pedestal_drift_band  | low_pedestal          | ridge                               | 214 |                 8.899 |            0.3578  |            0.2095  |                     0.1478  |                  0.7644 |
| pedestal_drift_band  | low_pedestal          | template_residual_boosted_stack_new | 213 |                 6.172 |            0.3303  |            0.2019  |                     0.1395  |                  0.8863 |
| pedestal_drift_band  | mid_pedestal          | 1d_cnn                              | 214 |                 9.001 |            0.3945  |            0.1905  |                     0.1228  |                  0.765  |
| pedestal_drift_band  | mid_pedestal          | deltaE_over_E_likelihood_template   | 213 |                 6.295 |            0.6881  |            0.08654 |                     0.06425 |                  0.8236 |
| pedestal_drift_band  | mid_pedestal          | gradient_boosted_trees              | 213 |                 6.454 |            0.3119  |            0.2115  |                     0.09954 |                  0.8682 |
| pedestal_drift_band  | mid_pedestal          | joint_sequence_transformer          | 213 |                 9.413 |            0.3486  |            0.2212  |                     0.1316  |                  0.5115 |
| pedestal_drift_band  | mid_pedestal          | mlp                                 | 214 |                11.19  |            0.4312  |            0.181   |                     0.1409  |                  0.8184 |
| pedestal_drift_band  | mid_pedestal          | ridge                               | 213 |                 6.453 |            0.3303  |            0.1923  |                     0.1176  |                  0.7746 |
| pedestal_drift_band  | mid_pedestal          | template_residual_boosted_stack_new | 213 |                 6.665 |            0.2844  |            0.1923  |                     0.1238  |                  0.8467 |
| pid_separation       | deuteron              | 1d_cnn                              | 310 |                 7.399 |            0.3082  |            0.2134  |                     0.1294  |                  0.6871 |
| pid_separation       | deuteron              | deltaE_over_E_likelihood_template   | 310 |                 8.03  |            0.5959  |            0.1037  |                     0.1133  |                  0.7581 |
| pid_separation       | deuteron              | gradient_boosted_trees              | 310 |                 5.637 |            0.2603  |            0.2012  |                     0.1023  |                  0.9161 |
| pid_separation       | deuteron              | joint_sequence_transformer          | 310 |                 8.257 |            0.3082  |            0.2378  |                     0.146   |                  0.3839 |
| pid_separation       | deuteron              | mlp                                 | 310 |                 9.642 |            0.3151  |            0.2378  |                     0.1536  |                  0.8065 |
| pid_separation       | deuteron              | ridge                               | 310 |                 6.628 |            0.2671  |            0.2256  |                     0.1041  |                  0.7097 |
| pid_separation       | deuteron              | template_residual_boosted_stack_new | 310 |                 5.373 |            0.2397  |            0.2256  |                     0.1052  |                  0.9194 |
| pid_separation       | proton                | 1d_cnn                              | 330 |                10.11  |            0.3908  |            0.1731  |                     0.1459  |                  0.8303 |
| pid_separation       | proton                | deltaE_over_E_likelihood_template   | 330 |                 9.443 |            0.6954  |            0.1026  |                     0.1313  |                  0.8364 |
| pid_separation       | proton                | gradient_boosted_trees              | 330 |                 6.427 |            0.3276  |            0.1923  |                     0.122   |                  0.8212 |
| pid_separation       | proton                | joint_sequence_transformer          | 330 |                10.73  |            0.3391  |            0.2372  |                     0.139   |                  0.6485 |
| pid_separation       | proton                | mlp                                 | 330 |                10.59  |            0.4253  |            0.1987  |                     0.17    |                  0.797  |
| pid_separation       | proton                | ridge                               | 330 |                 7.938 |            0.3391  |            0.1987  |                     0.127   |                  0.8182 |
| pid_separation       | proton                | template_residual_boosted_stack_new | 330 |                 5.675 |            0.3103  |            0.1859  |                     0.1263  |                  0.8152 |
| pileup_spacing_band  | merged                | 1d_cnn                              | 138 |                 6.916 |            0.4783  |          nan       |                     0.126   |                  0.7863 |
| pileup_spacing_band  | merged                | deltaE_over_E_likelihood_template   | 138 |                 8.963 |            0.7536  |          nan       |                     0.09812 |                  0.8563 |
| pileup_spacing_band  | merged                | gradient_boosted_trees              | 138 |                 6.031 |            0.4203  |          nan       |                     0.0938  |                  0.9218 |
| pileup_spacing_band  | merged                | joint_sequence_transformer          | 138 |                 7.943 |            0.4348  |          nan       |                     0.14    |                  0.535  |
| pileup_spacing_band  | merged                | mlp                                 | 138 |                10.05  |            0.5072  |          nan       |                     0.1945  |                  0.833  |
| pileup_spacing_band  | merged                | ridge                               | 138 |                 6.59  |            0.3986  |          nan       |                     0.08063 |                  0.8181 |
| pileup_spacing_band  | merged                | template_residual_boosted_stack_new | 138 |                 6.215 |            0.3768  |          nan       |                     0.09951 |                  0.9028 |
| pileup_spacing_band  | near                  | 1d_cnn                              |  61 |                 6.56  |            0.4262  |          nan       |                     0.1267  |                  0.7374 |
| pileup_spacing_band  | near                  | deltaE_over_E_likelihood_template   |  61 |                 9.613 |            0.7213  |          nan       |                     0.08381 |                  0.761  |
| pileup_spacing_band  | near                  | gradient_boosted_trees              |  61 |                 6.493 |            0.3115  |          nan       |                     0.09507 |                  0.9088 |
| pileup_spacing_band  | near                  | joint_sequence_transformer          |  61 |                 9.749 |            0.3443  |          nan       |                     0.1301  |                  0.6269 |
| pileup_spacing_band  | near                  | mlp                                 |  61 |                 9.709 |            0.4754  |          nan       |                     0.1473  |                  0.7989 |
| pileup_spacing_band  | near                  | ridge                               |  61 |                 6.488 |            0.377   |          nan       |                     0.1064  |                  0.7753 |
| pileup_spacing_band  | near                  | template_residual_boosted_stack_new |  61 |                 6.618 |            0.3607  |          nan       |                     0.09957 |                  0.9137 |
| pileup_spacing_band  | separated             | 1d_cnn                              | 121 |                 7.989 |            0.1736  |          nan       |                     0.1479  |                  0.7377 |
| pileup_spacing_band  | separated             | deltaE_over_E_likelihood_template   | 121 |                 6.448 |            0.4959  |          nan       |                     0.1372  |                  0.7978 |
| pileup_spacing_band  | separated             | gradient_boosted_trees              | 121 |                 5.248 |            0.1488  |          nan       |                     0.1192  |                  0.877  |
| pileup_spacing_band  | separated             | joint_sequence_transformer          | 121 |                 9.606 |            0.1901  |          nan       |                     0.154   |                  0.477  |
| pileup_spacing_band  | separated             | mlp                                 | 121 |                 9.633 |            0.1736  |          nan       |                     0.1627  |                  0.7784 |
| pileup_spacing_band  | separated             | ridge                               | 121 |                 7.977 |            0.1653  |          nan       |                     0.1139  |                  0.7352 |
| pileup_spacing_band  | separated             | template_residual_boosted_stack_new | 121 |                 5.56  |            0.124   |          nan       |                     0.1179  |                  0.9107 |
| saturation_onset     | saturated             | 1d_cnn                              | 236 |                 9.355 |            0.4643  |            0.1771  |                     0.1264  |                  0.7661 |
| saturation_onset     | saturated             | deltaE_over_E_likelihood_template   | 236 |                10.57  |            0.75    |            0.125   |                     0.1096  |                  0.8069 |
| saturation_onset     | saturated             | gradient_boosted_trees              | 236 |                 6.045 |            0.2929  |            0.2812  |                     0.07769 |                  0.8861 |
| saturation_onset     | saturated             | joint_sequence_transformer          | 236 |                 9.015 |            0.4143  |            0.25    |                     0.1328  |                  0.5148 |
| saturation_onset     | saturated             | mlp                                 | 236 |                 9.657 |            0.3786  |            0.3021  |                     0.194   |                  0.771  |
| saturation_onset     | saturated             | ridge                               | 236 |                 7.097 |            0.2929  |            0.2708  |                     0.07944 |                  0.7287 |
| saturation_onset     | saturated             | template_residual_boosted_stack_new | 236 |                 5.792 |            0.2786  |            0.3229  |                     0.08146 |                  0.8581 |
| saturation_onset     | unsaturated           | 1d_cnn                              | 404 |                 8.967 |            0.2667  |            0.2009  |                     0.1561  |                  0.7508 |
| saturation_onset     | unsaturated           | deltaE_over_E_likelihood_template   | 404 |                 6.443 |            0.5722  |            0.09375 |                     0.1363  |                  0.7841 |
| saturation_onset     | unsaturated           | gradient_boosted_trees              | 404 |                 5.701 |            0.3     |            0.1607  |                     0.1472  |                  0.8587 |
| saturation_onset     | unsaturated           | joint_sequence_transformer          | 404 |                 9.047 |            0.2556  |            0.2321  |                     0.1774  |                  0.5161 |
| saturation_onset     | unsaturated           | mlp                                 | 404 |                10.3   |            0.3722  |            0.183   |                     0.1462  |                  0.8202 |
| saturation_onset     | unsaturated           | ridge                               | 404 |                 7.246 |            0.3167  |            0.1875  |                     0.1388  |                  0.7843 |
| saturation_onset     | unsaturated           | template_residual_boosted_stack_new | 404 |                 5.241 |            0.2778  |            0.1562  |                     0.1444  |                  0.8757 |
| timing_pull_band     | high_abs_pull         | 1d_cnn                              | 275 |                15.28  |            0.4476  |            0.1471  |                     0.1544  |                  0.7561 |
| timing_pull_band     | high_abs_pull         | deltaE_over_E_likelihood_template   |  65 |                15.76  |            0.3056  |            0.3793  |                     0.1267  |                  0.8461 |
| timing_pull_band     | high_abs_pull         | gradient_boosted_trees              | 142 |                16.24  |            0.5106  |            0.1158  |                     0.1143  |                  0.9296 |
| timing_pull_band     | high_abs_pull         | joint_sequence_transformer          | 261 |                16.21  |            0.3475  |            0.1469  |                     0.1448  |                  0.4728 |
| timing_pull_band     | high_abs_pull         | mlp                                 | 280 |                18.99  |            0.4685  |            0.1834  |                     0.2581  |                  0.8127 |
| timing_pull_band     | high_abs_pull         | ridge                               | 178 |                16.41  |            0.3857  |            0.1111  |                     0.1446  |                  0.7498 |
| timing_pull_band     | high_abs_pull         | template_residual_boosted_stack_new | 146 |                14.53  |            0.5192  |            0.117   |                     0.1176  |                  0.9041 |
| timing_pull_band     | low_abs_pull          | 1d_cnn                              | 161 |                 2.416 |            0.3178  |            0.2593  |                     0.1369  |                  0.7248 |
| timing_pull_band     | low_abs_pull          | deltaE_over_E_likelihood_template   |  62 |                 2.712 |            0.1731  |            0.7     |                     0.09377 |                  0.8198 |
| timing_pull_band     | low_abs_pull          | gradient_boosted_trees              | 272 |                 2.439 |            0.2545  |            0.2336  |                     0.1153  |                  0.8754 |
| timing_pull_band     | low_abs_pull          | joint_sequence_transformer          | 189 |                 2.503 |            0.2653  |            0.3736  |                     0.139   |                  0.5515 |
| timing_pull_band     | low_abs_pull          | mlp                                 | 155 |                 2.604 |            0.3529  |            0.2571  |                     0.1622  |                  0.7308 |
| timing_pull_band     | low_abs_pull          | ridge                               | 244 |                 2.749 |            0.3023  |            0.2174  |                     0.1268  |                  0.7697 |
| timing_pull_band     | low_abs_pull          | template_residual_boosted_stack_new | 264 |                 2.397 |            0.2516  |            0.2385  |                     0.1135  |                  0.8681 |
| timing_pull_band     | mid_abs_pull          | 1d_cnn                              | 204 |                 7.797 |            0.2963  |            0.2396  |                     0.1344  |                  0.7904 |
| timing_pull_band     | mid_abs_pull          | deltaE_over_E_likelihood_template   |  73 |                 6.698 |            0.12    |            0.6522  |                     0.1414  |                  0.7884 |
| timing_pull_band     | mid_abs_pull          | gradient_boosted_trees              | 226 |                 7.169 |            0.2685  |            0.2288  |                     0.1007  |                  0.8233 |
| timing_pull_band     | mid_abs_pull          | joint_sequence_transformer          | 190 |                 6.712 |            0.3558  |            0.2442  |                     0.1366  |                  0.5248 |
| timing_pull_band     | mid_abs_pull          | mlp                                 | 205 |                 7.334 |            0.3065  |            0.2593  |                     0.1263  |                  0.844  |
| timing_pull_band     | mid_abs_pull          | ridge                               | 218 |                 7.031 |            0.2645  |            0.3196  |                     0.08784 |                  0.7692 |
| timing_pull_band     | mid_abs_pull          | template_residual_boosted_stack_new | 230 |                 6.266 |            0.2035  |            0.2479  |                     0.09181 |                  0.8443 |

## Systematics And Caveats

The endpoint is a controlled intervention bakeoff, not a production particle-ID
calibration.  GEANT4 supplies event-aligned PID, energy, and timing labels, while
the ADC morphology is derived from raw B-stack templates and residual pools.
The ADC/MeV scale is fixed for ranking and is not an external calibration.
Saturation and pile-up labels are controlled labels in the digitized benchmark,
not independent hardware flags.  The 18-sample window leaves only four
pretrigger samples, so AR extrapolation is deliberately low order; higher-order
models would leak pulse-shape information into the pedestal intervention.
Pedestal motion remains partly degenerate with late tails and curvature.  The
bootstrap intervals resample held-out runs, so they describe run-transfer
uncertainty and do not include GEANT4 physics-list, detector material, or
calibration uncertainty.

Runtime was `64.5` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

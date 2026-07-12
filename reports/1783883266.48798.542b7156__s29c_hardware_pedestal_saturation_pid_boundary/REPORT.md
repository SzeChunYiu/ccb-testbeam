# S29c: hardware pedestal-saturation validation with PID-boundary labels

## Abstract

Ticket `1783883266.48798.542b7156` asks whether the controlled-injection S29b gain survives a
more hardware-facing validation: saturation/pedestal metadata and an explicit
downstream PID-boundary label replace the older amplitude-ceiling and stave-only
proxies.  The worker was `testbeam-laptop-2`.  The study first reproduces the canonical
B-stack selected-pulse number directly from raw ROOT, then benchmarks a strong
traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN,
`joint_sequence_transformer`, and the S29b new architecture
`template_residual_boosted_stack_new` under a run-heldout split with bootstrap
confidence intervals.

The raw selected-pulse anchor is `640737`
selected B-stave pulses versus reference `640737`,
delta `0`.  The S29b reference winner was
`template_residual_boosted_stack_new` with energy sigma68 `0.06415`.
In this hardware/PID-boundary validation, `result.json` names **`gradient_boosted_trees`** as
the winner by the predeclared joint held-out score.  The S29b residual-stack
candidate remains explicitly scored in the safety tables; its global score is
`0.2304`.

## Raw ROOT reproduction

The reproduction gate reads `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.
For each `h101/HRDv` trace with samples `x_c(t)`, the pretrigger baseline is

`b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]`,

and the selected-pulse indicator is

`I_i = 1[max_{c in B2,B4,B6,B8,t} (x_ic(t)-b_ic) > 1000 ADC]`.

No model fit starts until this raw count agrees with the reference:

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Estimands and labels

For event `i`, the benchmark waveform is a raw-template/digitized truth hybrid

`w_i(t) = p_i + A_i T_s(t-t_i) + A'_i T_s(t-t_i-Delta_i) + epsilon_{r,s}(t)`,

where `epsilon_{r,s}` is sampled from raw ROOT residual pools by source run and
stave.  GEANT4 supplies event-level PID, energy, and timing truth; the raw B-stack
templates and residuals supply detector-like morphology.  The primary residuals are

`e_E = (hat A_1 + hat A_2 - E_i) / E_i`,

`e_t = 10 ns (hat t_1 - t_i)`,

with robust scale

`sigma_68(e) = [Q_84(e)-Q_16(e)]/2`.

Hardware-facing metadata are represented by two explicit labels retained in the
event table: `truth_saturation_label`, the digitized waveform saturation-onset
indicator, and `truth_pedestal_adc`, the raw pretrigger pedestal.  The downstream
PID-boundary label is deterministic and event-level.  Define

`z_i = log(1 + dE/dx_i) + 0.035 area_over_amp_i - 0.18 depth_i`.

The threshold is the midpoint between the train-run proton-like and deuteron-like
class medians.  Held-out events in the lowest 40% of `|z_i-z_0|` are labeled
`near_boundary`; the others are `off_boundary`.  This boundary label is fixed
before scoring any method prediction.

## Split, bootstrap, and winner rule

The split is by complete source run: train runs
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs
`[58, 60, 62, 64, 65]`.  Confidence intervals are
95% percentile intervals from `360`
held-out run-block bootstrap resamples.  The winner score is

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

## Methods

The strong traditional baseline is `deltaE_over_E_likelihood_template`: a
pretrigger-subtracted CFD/template two-pulse fit plus a diagonal DeltaE/E PID
likelihood.  With standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j-mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel includes ridge, histogram gradient-boosted trees, MLP, 1D-CNN,
and `joint_sequence_transformer`.  The new S29b architecture is
`template_residual_boosted_stack_new`, which feeds traditional fit estimates and
waveform residual coordinates into boosted residual heads.  This is the sensible
new architecture for this ticket because saturation recovery is partially
physics-constrained: a template fit supplies low-variance amplitude/timing
coordinates, while residual learners can correct clipped-tail curvature,
pedestal drift, and overlap failure modes.

## Global held-out results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees              |         0.2232 |    0.9383 |                  0.8687 |           0.9161 |       0.828  |                     0.08764 |                            0.0731  |                              0.1051 |             7.8   |                    7.338 |                     8.552 |             0.2969 |             0.1969 |
| template_residual_boosted_stack_new |         0.2304 |    0.9309 |                  0.8673 |           0.9194 |       0.8237 |                     0.09209 |                            0.07545 |                              0.1048 |             8.087 |                    7.462 |                     8.823 |             0.2781 |             0.2062 |
| ridge                               |         0.2759 |    0.8366 |                  0.7639 |           0.7097 |       0.7857 |                     0.09099 |                            0.07066 |                              0.1173 |             9.995 |                    9.181 |                    10.97  |             0.3063 |             0.2125 |
| 1d_cnn                              |         0.3042 |    0.8305 |                  0.7587 |           0.6871 |       0.7918 |                     0.1043  |                            0.08192 |                              0.1224 |            11.22  |                   10.64  |                    11.7   |             0.3531 |             0.1938 |
| deltaE_over_E_likelihood_template   |         0.3297 |    0.8317 |                  0.7972 |           0.7581 |       0.8131 |                     0.1275  |                            0.08799 |                              0.161  |            11.38  |                    9.613 |                    11.75  |             0.65   |             0.1031 |
| mlp                                 |         0.3625 |    0.854  |                  0.8017 |           0.8065 |       0.7886 |                     0.1637  |                            0.1505  |                              0.1932 |            11.95  |                   11.69  |                    12.7   |             0.375  |             0.2188 |
| joint_sequence_transformer          |         0.3804 |    0.5299 |                  0.5162 |           0.3839 |       0.5064 |                     0.1139  |                            0.08327 |                              0.1393 |            11.75  |                   10.1   |                    12.83  |             0.325  |             0.2375 |

Relative to the traditional method, `gradient_boosted_trees` changes energy sigma68 by
`-0.0399`,
timing sigma68 by `-3.581` ns,
and PID balanced accuracy by `0.07146`.

## Run-heldout stability

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

## Hardware and PID-boundary sidebands

The sideband table is the core S29c validation artifact.  It scores every method
inside hardware saturation, pedestal, explicit near-boundary/off-boundary, and
true proton/deuteron-like slices.  The same held-out predictions are used; only
the aggregation subset changes.

| axis                      | value                | method                              |   n |   energy_bias_frac |   energy_sigma68_frac |   time_sigma68_ns |   pid_balanced_accuracy |   pileup_miss_rate |   false_split_rate |
|:--------------------------|:---------------------|:------------------------------------|----:|-------------------:|----------------------:|------------------:|------------------------:|-------------------:|-------------------:|
| hardware_pedestal_band    | high_pedestal        | 1d_cnn                              | 213 |         -0.07399   |               0.1182  |             8.437 |                  0.7335 |             0.2353 |            0.2342  |
| hardware_pedestal_band    | high_pedestal        | deltaE_over_E_likelihood_template   | 213 |         -0.01444   |               0.1261  |             5.682 |                  0.7681 |             0.5196 |            0.1081  |
| hardware_pedestal_band    | high_pedestal        | gradient_boosted_trees              | 213 |         -0.005025  |               0.08321 |             4.934 |                  0.8612 |             0.2353 |            0.2162  |
| hardware_pedestal_band    | high_pedestal        | joint_sequence_transformer          | 214 |         -0.004042  |               0.1368  |             8.108 |                  0.4831 |             0.2255 |            0.2768  |
| hardware_pedestal_band    | high_pedestal        | mlp                                 | 213 |         -0.05617   |               0.1332  |             8.258 |                  0.8092 |             0.2941 |            0.1892  |
| hardware_pedestal_band    | high_pedestal        | ridge                               | 213 |         -0.006184  |               0.08538 |             7.055 |                  0.7533 |             0.2255 |            0.2342  |
| hardware_pedestal_band    | high_pedestal        | template_residual_boosted_stack_new | 214 |         -0.002568  |               0.09191 |             4.973 |                  0.8719 |             0.2157 |            0.2232  |
| hardware_pedestal_band    | low_pedestal         | 1d_cnn                              | 213 |         -0.05607   |               0.164   |            11.39  |                  0.7778 |             0.422  |            0.1538  |
| hardware_pedestal_band    | low_pedestal         | deltaE_over_E_likelihood_template   | 214 |          0.07517   |               0.1275  |            10.29  |                  0.8015 |             0.7339 |            0.1143  |
| hardware_pedestal_band    | low_pedestal         | gradient_boosted_trees              | 214 |         -0.006609  |               0.1389  |             6.681 |                  0.8761 |             0.3394 |            0.1619  |
| hardware_pedestal_band    | low_pedestal         | joint_sequence_transformer          | 213 |          0.04872   |               0.1912  |             9.184 |                  0.5568 |             0.3945 |            0.2115  |
| hardware_pedestal_band    | low_pedestal         | mlp                                 | 213 |         -0.06973   |               0.2556  |            11.28  |                  0.7803 |             0.3945 |            0.2885  |
| hardware_pedestal_band    | low_pedestal         | ridge                               | 214 |          0.003811  |               0.1478  |             8.899 |                  0.7644 |             0.3578 |            0.2095  |
| hardware_pedestal_band    | low_pedestal         | template_residual_boosted_stack_new | 213 |         -0.004788  |               0.1395  |             6.172 |                  0.8863 |             0.3303 |            0.2019  |
| hardware_pedestal_band    | mid_pedestal         | 1d_cnn                              | 214 |         -0.08137   |               0.1228  |             9.001 |                  0.765  |             0.3945 |            0.1905  |
| hardware_pedestal_band    | mid_pedestal         | deltaE_over_E_likelihood_template   | 213 |         -0.02648   |               0.06425 |             6.295 |                  0.8236 |             0.6881 |            0.08654 |
| hardware_pedestal_band    | mid_pedestal         | gradient_boosted_trees              | 213 |         -0.03112   |               0.09954 |             6.454 |                  0.8682 |             0.3119 |            0.2115  |
| hardware_pedestal_band    | mid_pedestal         | joint_sequence_transformer          | 213 |         -0.01369   |               0.1316  |             9.413 |                  0.5115 |             0.3486 |            0.2212  |
| hardware_pedestal_band    | mid_pedestal         | mlp                                 | 214 |         -0.03578   |               0.1409  |            11.19  |                  0.8184 |             0.4312 |            0.181   |
| hardware_pedestal_band    | mid_pedestal         | ridge                               | 213 |         -0.02164   |               0.1176  |             6.453 |                  0.7746 |             0.3303 |            0.1923  |
| hardware_pedestal_band    | mid_pedestal         | template_residual_boosted_stack_new | 213 |         -0.02374   |               0.1238  |             6.665 |                  0.8467 |             0.2844 |            0.1923  |
| hardware_saturation_label | hardware_saturated   | 1d_cnn                              | 236 |         -0.04295   |               0.1264  |             9.355 |                  0.7661 |             0.4643 |            0.1771  |
| hardware_saturation_label | hardware_saturated   | deltaE_over_E_likelihood_template   | 236 |          0.01741   |               0.1096  |            10.57  |                  0.8069 |             0.75   |            0.125   |
| hardware_saturation_label | hardware_saturated   | gradient_boosted_trees              | 236 |         -0.008138  |               0.07769 |             6.045 |                  0.8861 |             0.2929 |            0.2812  |
| hardware_saturation_label | hardware_saturated   | joint_sequence_transformer          | 236 |          0.03988   |               0.1328  |             9.015 |                  0.5148 |             0.4143 |            0.25    |
| hardware_saturation_label | hardware_saturated   | mlp                                 | 236 |         -0.005104  |               0.194   |             9.657 |                  0.771  |             0.3786 |            0.3021  |
| hardware_saturation_label | hardware_saturated   | ridge                               | 236 |          0.009612  |               0.07944 |             7.097 |                  0.7287 |             0.2929 |            0.2708  |
| hardware_saturation_label | hardware_saturated   | template_residual_boosted_stack_new | 236 |         -0.006202  |               0.08146 |             5.792 |                  0.8581 |             0.2786 |            0.3229  |
| hardware_saturation_label | hardware_unsaturated | 1d_cnn                              | 404 |         -0.07807   |               0.1561  |             8.967 |                  0.7508 |             0.2667 |            0.2009  |
| hardware_saturation_label | hardware_unsaturated | deltaE_over_E_likelihood_template   | 404 |         -0.02155   |               0.1363  |             6.443 |                  0.7841 |             0.5722 |            0.09375 |
| hardware_saturation_label | hardware_unsaturated | gradient_boosted_trees              | 404 |         -0.0189    |               0.1472  |             5.701 |                  0.8587 |             0.3    |            0.1607  |
| hardware_saturation_label | hardware_unsaturated | joint_sequence_transformer          | 404 |         -0.03702   |               0.1774  |             9.047 |                  0.5161 |             0.2556 |            0.2321  |
| hardware_saturation_label | hardware_unsaturated | mlp                                 | 404 |         -0.08217   |               0.1462  |            10.3   |                  0.8202 |             0.3722 |            0.183   |
| hardware_saturation_label | hardware_unsaturated | ridge                               | 404 |         -0.03532   |               0.1388  |             7.246 |                  0.7843 |             0.3167 |            0.1875  |
| hardware_saturation_label | hardware_unsaturated | template_residual_boosted_stack_new | 404 |         -0.01503   |               0.1444  |             5.241 |                  0.8757 |             0.2778 |            0.1562  |
| pid_boundary_label        | near_boundary        | 1d_cnn                              | 256 |         -0.06964   |               0.1253  |             9.644 |                  0.6954 |             0.3282 |            0.24    |
| pid_boundary_label        | near_boundary        | deltaE_over_E_likelihood_template   | 256 |          0.005914  |               0.09465 |             8.526 |                  0.7653 |             0.6107 |            0.08    |
| pid_boundary_label        | near_boundary        | gradient_boosted_trees              | 256 |         -0.002759  |               0.1122  |             5.743 |                  0.8721 |             0.2901 |            0.2     |
| pid_boundary_label        | near_boundary        | joint_sequence_transformer          | 256 |          0.003546  |               0.1431  |             9.687 |                  0.6218 |             0.3282 |            0.264   |
| pid_boundary_label        | near_boundary        | mlp                                 | 256 |         -0.04966   |               0.1688  |             9.667 |                  0.7658 |             0.3588 |            0.248   |
| pid_boundary_label        | near_boundary        | ridge                               | 256 |          0.001266  |               0.1078  |             8.34  |                  0.69   |             0.3053 |            0.264   |
| pid_boundary_label        | near_boundary        | template_residual_boosted_stack_new | 256 |         -0.001887  |               0.1132  |             5.6   |                  0.8817 |             0.2748 |            0.216   |
| pid_boundary_label        | off_boundary         | 1d_cnn                              | 384 |         -0.07164   |               0.1351  |             9.465 |                  0.8295 |             0.3704 |            0.1641  |
| pid_boundary_label        | off_boundary         | deltaE_over_E_likelihood_template   | 384 |         -0.01707   |               0.1458  |             9.305 |                  0.8401 |             0.6772 |            0.1179  |
| pid_boundary_label        | off_boundary         | gradient_boosted_trees              | 384 |         -0.02289   |               0.1142  |             6.157 |                  0.8645 |             0.3016 |            0.1949  |
| pid_boundary_label        | off_boundary         | joint_sequence_transformer          | 384 |         -0.003505  |               0.1397  |             9.084 |                  0.4446 |             0.3228 |            0.2205  |
| pid_boundary_label        | off_boundary         | mlp                                 | 384 |         -0.05614   |               0.1634  |            10.12  |                  0.8443 |             0.3862 |            0.2     |
| pid_boundary_label        | off_boundary         | ridge                               | 384 |         -0.006508  |               0.1112  |             6.991 |                  0.8429 |             0.3069 |            0.1795  |
| pid_boundary_label        | off_boundary         | template_residual_boosted_stack_new | 384 |         -0.01701   |               0.1153  |             5.615 |                  0.8533 |             0.2804 |            0.2     |
| pid_boundary_truth        | deuteron_like        | 1d_cnn                              | 310 |         -0.06377   |               0.1294  |             7.399 |                  0.6871 |             0.3082 |            0.2134  |
| pid_boundary_truth        | deuteron_like        | deltaE_over_E_likelihood_template   | 310 |         -0.0005628 |               0.1133  |             8.03  |                  0.7581 |             0.5959 |            0.1037  |
| pid_boundary_truth        | deuteron_like        | gradient_boosted_trees              | 310 |         -0.01976   |               0.1023  |             5.637 |                  0.9161 |             0.2603 |            0.2012  |
| pid_boundary_truth        | deuteron_like        | joint_sequence_transformer          | 310 |          0.01244   |               0.146   |             8.257 |                  0.3839 |             0.3082 |            0.2378  |
| pid_boundary_truth        | deuteron_like        | mlp                                 | 310 |         -0.07058   |               0.1536  |             9.642 |                  0.8065 |             0.3151 |            0.2378  |
| pid_boundary_truth        | deuteron_like        | ridge                               | 310 |         -0.002492  |               0.1041  |             6.628 |                  0.7097 |             0.2671 |            0.2256  |
| pid_boundary_truth        | deuteron_like        | template_residual_boosted_stack_new | 310 |         -0.004649  |               0.1052  |             5.373 |                  0.9194 |             0.2397 |            0.2256  |
| pid_boundary_truth        | proton_like          | 1d_cnn                              | 330 |         -0.07676   |               0.1459  |            10.11  |                  0.8303 |             0.3908 |            0.1731  |
| pid_boundary_truth        | proton_like          | deltaE_over_E_likelihood_template   | 330 |         -0.02003   |               0.1313  |             9.443 |                  0.8364 |             0.6954 |            0.1026  |
| pid_boundary_truth        | proton_like          | gradient_boosted_trees              | 330 |         -0.00652   |               0.122   |             6.427 |                  0.8212 |             0.3276 |            0.1923  |
| pid_boundary_truth        | proton_like          | joint_sequence_transformer          | 330 |         -0.00952   |               0.139   |            10.73  |                  0.6485 |             0.3391 |            0.2372  |
| pid_boundary_truth        | proton_like          | mlp                                 | 330 |         -0.03621   |               0.17    |            10.59  |                  0.797  |             0.4253 |            0.1987  |
| pid_boundary_truth        | proton_like          | ridge                               | 330 |         -0.005933  |               0.127   |             7.938 |                  0.8182 |             0.3391 |            0.1987  |
| pid_boundary_truth        | proton_like          | template_residual_boosted_stack_new | 330 |         -0.01345   |               0.1263  |             5.675 |                  0.8152 |             0.3103 |            0.1859  |

## S29b winner safety panel

The table below isolates the S29b winner candidate and its main competitors on
the three validation slices that matter most for this ticket: near PID boundary,
hardware-saturated, and high-pedestal held-out events.

| method                              |   pid_boundary_energy_sigma68_frac |   pid_boundary_pid_balanced_accuracy |   pid_boundary_pileup_miss_rate |   hardware_saturated_energy_sigma68_frac |   hardware_saturated_pid_balanced_accuracy |   high_pedestal_energy_sigma68_frac |   high_pedestal_pid_balanced_accuracy |
|:------------------------------------|-----------------------------------:|-------------------------------------:|--------------------------------:|-----------------------------------------:|-------------------------------------------:|------------------------------------:|--------------------------------------:|
| deltaE_over_E_likelihood_template   |                            0.09465 |                               0.7653 |                          0.6107 |                                  0.1096  |                                     0.8069 |                             0.1261  |                                0.7681 |
| gradient_boosted_trees              |                            0.1122  |                               0.8721 |                          0.2901 |                                  0.07769 |                                     0.8861 |                             0.08321 |                                0.8612 |
| template_residual_boosted_stack_new |                            0.1132  |                               0.8817 |                          0.2748 |                                  0.08146 |                                     0.8581 |                             0.09191 |                                0.8719 |
| ridge                               |                            0.1078  |                               0.69   |                          0.3053 |                                  0.07944 |                                     0.7287 |                             0.08538 |                                0.7533 |
| mlp                                 |                            0.1688  |                               0.7658 |                          0.3588 |                                  0.194   |                                     0.771  |                             0.1332  |                                0.8092 |
| 1d_cnn                              |                            0.1253  |                               0.6954 |                          0.3282 |                                  0.1264  |                                     0.7661 |                             0.1182  |                                0.7335 |
| joint_sequence_transformer          |                            0.1431  |                               0.6218 |                          0.3282 |                                  0.1328  |                                     0.5148 |                             0.1368  |                                0.4831 |

## Systematics and caveats

1. The raw count is reproduced from real ROOT data, but the supervised endpoint is
   a raw-template/digitized GEANT4 benchmark, not an online electronics truth
   stream.
2. `truth_saturation_label` and `truth_pedestal_adc` are hardware-like metadata
   derived from digitized raw morphology; the ROOT tree itself has no separate
   saturation flag branch.
3. The PID-boundary label is explicit and event-level, but it is a deterministic
   downstream decision coordinate rather than an externally hand-labeled particle
   boundary.
4. Bootstrap intervals quantify held-out run transfer for the fixed model panel;
   they do not include GEANT4 physics-list, material-budget, ADC/MeV, or future
   beam-current uncertainty.
5. The S29b residual-stack result should be read as a validation candidate.  It
   does not automatically replace the traditional method where interpretability
   or monotonic calibration is more important than the composite score.

## Conclusion

The controlled-injection S29b winner `template_residual_boosted_stack_new` is not blindly promoted by
this ticket.  It is re-scored under hardware saturation, high-pedestal, and
explicit PID-boundary labels alongside the full required method panel.  The
winner named in `result.json` is `gradient_boosted_trees`; the safety panel shows where the
S29b residual-stack candidate does and does not survive the stricter validation.

Runtime was `77.0` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

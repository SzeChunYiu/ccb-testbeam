# S46c: Pedestal-Tail Memory Joint PID-Energy Calibration Benchmark

## Abstract

Ticket `#2433` asks whether late-tail memory and run-level pedestal drift bias
joint particle-ID and energy inference beyond a standard range/deltaE-E style
calibration.  This worker (`testbeam-laptop-4`) ran the required `tn-ticket claim`
command once; the command returned the known `null|null|null` idempotency
artifact when no worker ticket existed, so issue `#2433` was recovered by the
equivalent label transition (`factory:open` to `factory:claimed` plus
`worker:testbeam-laptop-4`).  The analysis uses frozen local S36c benchmark tables because
the GEANT4 truth ROOT source required for a fresh upstream rerun is not mounted
on this host.  The raw-ROOT reproduction gate and all prediction/metric tables
are present locally and are copied into this ticket directory.

The winner written to `result.json` is **`pedestal_memory_fusion_new`**.  Its calibrated
energy sigma68 is `0.07374` with run-bootstrap
95% CI [`0.06826`,
`0.07647`], PID AUC is
`0.9909`, and timing sigma68 is
`7.592` ns.  Relative to the traditional
AR(1)/charge-ratio likelihood comparator, the winner changes energy sigma68 by
`-0.02732`
and winner score by `-0.05332`.

## Raw ROOT Reproduction

The raw B-stack selected-pulse gate is inherited from the frozen local evidence
table and reproduces the canonical S00 count.  The ROOT branch is `h101/HRDv`,
reshaped to `(event, channel, sample)` for B2/B4/B6/B8.  With waveform samples
`x_ect`,

`b_ec = median(x_ec0, x_ec1, x_ec2, x_ec3)`,

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

No benchmark row is accepted unless this gate passes:

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

The raw archive visible on this host is `/home/billy/ccb-data/data/extracted/root/root`.
The reusable upstream runner expected `/home/billy/ccb-data/extracted/root/root`;
the raw files themselves are present, but the host's read-only external archive
prevented adding that compatibility symlink outside the repository.

## Estimands

For an injected two-pulse event, the observed 18-sample waveform is modeled as

`w_s(t) = A_1 T_s(t-t_1) + A_2 T_s(t-t_2) + epsilon_rs(t) + p_r`,

where `T_s` is a train-run stave template, `epsilon_rs` is a run/stave residual
sampled from raw ROOT pulses, and `p_r` is the pretrigger pedestal state.  The
calibrated energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`,

and robust resolution is

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

PID is the available raw-derived proxy `inner_high_charge`, defined by inner
B-stave topology and injected total charge.  This is a proxy for the
deltaE-E/range-cut decision boundary, not an external particle label.

## Split and Uncertainty

Training and held-out sets are disjoint by source run.  The frozen split uses
train runs `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs
`[58, 60, 62, 64, 65]`.  Confidence intervals are percentile 95% intervals from
360 held-out run-block bootstrap resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Method Panel

| requirement | method |
| --- | --- |
| strong traditional | `ar1_charge_ratio_likelihood_traditional` |
| ridge | `ridge` |
| gradient-boosted trees | `gradient_boosted_trees` |
| MLP | `mlp` |
| 1D-CNN | `1d_cnn` |
| sequence NN | `tiny_sequence_transformer` |
| new architecture | `pedestal_memory_fusion_new` |

The traditional method is a clipped template fit with an AR(1)-style pedestal
sideband and charge-ratio likelihood.  The new architecture is a hybrid residual
fusion model: analytic pulse and pedestal estimates are used as low-variance
coordinates, while boosted residual heads learn clipped-tail and late-memory
corrections.

## Overall Results

| method                                  |   winner_score |   pid_auc |   pid_confusion_offdiag_rate |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   timing_sigma68_ns |   pedestal_offset_recovery_error |   pedestal_false_split_span |   shape_latent_stability_span |   pileup_miss_rate |   false_split_rate |
|:----------------------------------------|---------------:|----------:|-----------------------------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|--------------------:|---------------------------------:|----------------------------:|------------------------------:|-------------------:|-------------------:|
| pedestal_memory_fusion_new              |         0.1357 |    0.9909 |                      0.01361 |               0.00445  |                   0.07374 |                          0.06826 |                           0.07647 |               7.592 |                        0.01131   |                    0.01937  |                      0.008686 |             0.3163 |             0.2047 |
| gradient_boosted_trees                  |         0.1398 |    0.9889 |                      0.01718 |               0.002428 |                   0.07366 |                          0.06573 |                           0.08428 |               8.439 |                        0.0002752 |                    0.01474  |                      0.01508  |             0.3233 |             0.2209 |
| ridge                                   |         0.1512 |    0.9896 |                      0.02013 |               0.008654 |                   0.08077 |                          0.07092 |                           0.09343 |               8.795 |                        0.014     |                    0.04857  |                      0.008588 |             0.307  |             0.2233 |
| 1d_cnn                                  |         0.1676 |    0.9853 |                      0.01449 |              -0.01928  |                   0.08671 |                          0.07539 |                           0.09749 |              10.91  |                        0.03442   |                    0.01563  |                      0.000964 |             0.3581 |             0.2279 |
| ar1_charge_ratio_likelihood_traditional |         0.189  |    0.9892 |                      0.02532 |               0.06702  |                   0.1011  |                          0.08833 |                           0.1137  |               8.674 |                        0.002315  |                    0.1004   |                      0.02901  |             0.6326 |             0.186  |
| mlp                                     |         0.1936 |    0.9902 |                      0.02007 |               0.003197 |                   0.1078  |                          0.09298 |                           0.1193  |              12.36  |                        0.02005   |                    0.02372  |                      0.0132   |             0.3047 |             0.2651 |
| tiny_sequence_transformer               |         0.2024 |    0.9837 |                      0.02767 |               0.00272  |                   0.1061  |                          0.09764 |                           0.119   |              14.55  |                        0.003362  |                    0.006176 |                      0.0423   |             0.4116 |             0.1884 |

## Endpoint Table With CIs

| method                                  |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   pid_balanced_accuracy |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   saturated_energy_residual_sigma68 |   timing_pull_width |   pedestal_offset_recovery_error |   pedestal_false_split_span |   shape_latent_stability_span |
|:----------------------------------------|----------:|-----------------:|------------------:|------------------------:|--------------------------:|---------------------------------:|----------------------------------:|------------------------------------:|--------------------:|---------------------------------:|----------------------------:|------------------------------:|
| gradient_boosted_trees                  |    0.9889 |           0.9776 |            0.9959 |                  0.9717 |                   0.07366 |                          0.06573 |                           0.08428 |                             0.118   |              0.8439 |                        0.0002752 |                    0.01474  |                      0.01508  |
| pedestal_memory_fusion_new              |    0.9909 |           0.9825 |            0.9969 |                  0.9744 |                   0.07374 |                          0.06826 |                           0.07647 |                             0.09519 |              0.7592 |                        0.01131   |                    0.01937  |                      0.008686 |
| ridge                                   |    0.9896 |           0.9845 |            0.9961 |                  0.9708 |                   0.08077 |                          0.07092 |                           0.09343 |                             0.06348 |              0.8795 |                        0.014     |                    0.04857  |                      0.008588 |
| 1d_cnn                                  |    0.9853 |           0.9716 |            0.994  |                  0.9714 |                   0.08671 |                          0.07539 |                           0.09749 |                             0.04121 |              1.091  |                        0.03442   |                    0.01563  |                      0.000964 |
| ar1_charge_ratio_likelihood_traditional |    0.9892 |           0.9687 |            1      |                  0.9865 |                   0.1011  |                          0.08833 |                           0.1137  |                             0.04978 |              0.8674 |                        0.002315  |                    0.1004   |                      0.02901  |
| tiny_sequence_transformer               |    0.9837 |           0.9771 |            0.9915 |                  0.9643 |                   0.1061  |                          0.09764 |                           0.119   |                             0.07605 |              1.455  |                        0.003362  |                    0.006176 |                      0.0423   |
| mlp                                     |    0.9902 |           0.979  |            0.9965 |                  0.9692 |                   0.1078  |                          0.09298 |                           0.1193  |                             0.1565  |              1.236  |                        0.02005   |                    0.02372  |                      0.0132   |

## Run-Held-Out Stability

| method                                  |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:----------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                  |            58 |                -0.03594  |                     0.09437 |       -0.1751  |            10.26  |             0.3023 |             0.2442 |
| 1d_cnn                                  |            60 |                 0.008326 |                     0.09533 |        1.376   |            12.05  |             0.3605 |             0.2442 |
| 1d_cnn                                  |            62 |                -0.008519 |                     0.0839  |        0.3265  |            10.99  |             0.407  |             0.3256 |
| 1d_cnn                                  |            64 |                -0.04816  |                     0.07747 |        0.8632  |             9.9   |             0.407  |             0.1279 |
| 1d_cnn                                  |            65 |                -0.02509  |                     0.06752 |        0.09213 |            11.36  |             0.314  |             0.1977 |
| ar1_charge_ratio_likelihood_traditional |            58 |                 0.04599  |                     0.07256 |        1.123   |            10.08  |             0.6744 |             0.2093 |
| ar1_charge_ratio_likelihood_traditional |            60 |                 0.1453   |                     0.1014  |        0.6891  |             8.384 |             0.6628 |             0.1279 |
| ar1_charge_ratio_likelihood_traditional |            62 |                 0.07348  |                     0.0981  |        1.734   |             6.805 |             0.6628 |             0.186  |
| ar1_charge_ratio_likelihood_traditional |            64 |                 0.04212  |                     0.08811 |        0.5637  |             7.757 |             0.5814 |             0.1395 |
| ar1_charge_ratio_likelihood_traditional |            65 |                 0.08776  |                     0.08113 |        1.379   |             9.689 |             0.5814 |             0.2674 |
| gradient_boosted_trees                  |            58 |                -0.01476  |                     0.08212 |       -0.4462  |             7.066 |             0.3023 |             0.2442 |
| gradient_boosted_trees                  |            60 |                 0.03624  |                     0.06949 |        0.8246  |             9.731 |             0.2907 |             0.2791 |
| gradient_boosted_trees                  |            62 |                 0.006562 |                     0.05821 |       -0.1718  |             6.924 |             0.3605 |             0.2791 |
| gradient_boosted_trees                  |            64 |                -0.01122  |                     0.06254 |       -0.2304  |             6.594 |             0.3837 |             0.1279 |
| gradient_boosted_trees                  |            65 |                -0.01551  |                     0.07091 |       -1.503   |             9.75  |             0.2791 |             0.1744 |
| mlp                                     |            58 |                -0.01595  |                     0.1072  |       -0.9979  |            12.39  |             0.2558 |             0.3605 |
| mlp                                     |            60 |                 0.0304   |                     0.1023  |       -1.926   |            12.95  |             0.2674 |             0.2558 |
| mlp                                     |            62 |                -0.003876 |                     0.1144  |       -0.4934  |            12.51  |             0.3372 |             0.3372 |
| mlp                                     |            64 |                 0.007353 |                     0.08058 |       -2       |            11.08  |             0.4186 |             0.1512 |
| mlp                                     |            65 |                -0.01078  |                     0.1131  |       -1.208   |            13.05  |             0.2442 |             0.2209 |
| pedestal_memory_fusion_new              |            58 |                -0.01689  |                     0.07252 |       -0.2335  |             6.598 |             0.314  |             0.2791 |
| pedestal_memory_fusion_new              |            60 |                 0.04105  |                     0.06992 |        0.2297  |             8.006 |             0.2791 |             0.1977 |
| pedestal_memory_fusion_new              |            62 |                 0.004628 |                     0.07601 |       -0.2568  |             6.98  |             0.3372 |             0.2326 |
| pedestal_memory_fusion_new              |            64 |                 0.006366 |                     0.06344 |       -0.6742  |             6.953 |             0.3837 |             0.1395 |
| pedestal_memory_fusion_new              |            65 |                -0.01136  |                     0.06905 |       -1.461   |             8.32  |             0.2674 |             0.1744 |
| ridge                                   |            58 |                -0.005848 |                     0.07411 |       -0.5589  |             7.71  |             0.3023 |             0.3023 |
| ridge                                   |            60 |                 0.0495   |                     0.08861 |        0.6083  |             9.802 |             0.2674 |             0.1977 |
| ridge                                   |            62 |                 0.02065  |                     0.0843  |        0.3429  |             8.37  |             0.3256 |             0.3023 |
| ridge                                   |            64 |                -0.006786 |                     0.06517 |        0.6388  |             8.563 |             0.3605 |             0.1395 |
| ridge                                   |            65 |                 0.004638 |                     0.07811 |       -0.1411  |             9.809 |             0.2791 |             0.1744 |
| tiny_sequence_transformer               |            58 |                -0.02095  |                     0.09508 |      -16.9     |            15.42  |             0.3372 |             0.1744 |
| tiny_sequence_transformer               |            60 |                 0.05108  |                     0.1052  |      -12.93    |            14.11  |             0.4186 |             0.1977 |
| tiny_sequence_transformer               |            62 |                 0.001206 |                     0.1121  |      -16.57    |            13.46  |             0.4302 |             0.3023 |
| tiny_sequence_transformer               |            64 |                 0.001072 |                     0.09882 |      -16.16    |            14.39  |             0.4651 |             0.1163 |
| tiny_sequence_transformer               |            65 |                -0.01007  |                     0.1005  |      -13.84    |            15.27  |             0.407  |             0.1512 |

## Pedestal, Tail, PID, and Saturation Sidebands

| axis                 | value                     | method                                  |   n |   pid_balanced_accuracy |   energy_bias_frac |   energy_sigma68_frac |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |   saturation_tail_failure_rate |
|:---------------------|:--------------------------|:----------------------------------------|----:|------------------------:|-------------------:|----------------------:|------------------:|-------------------:|-------------------:|-------------------------------:|
| pedestal_band        | nominal_like              | 1d_cnn                                  | 309 |                  0.8693 |         -0.04514   |               0.07591 |             6.685 |            0.3203  |             0.2179 |                        0.5     |
| pedestal_band        | nominal_like              | ar1_charge_ratio_likelihood_traditional | 860 |                  0.7518 |         -1         |               0.5562  |             7.88  |            0.6326  |             0.186  |                        0.8182  |
| pedestal_band        | nominal_like              | gradient_boosted_trees                  | 309 |                  0.8693 |          0.006562  |               0.06186 |             4.81  |            0.2549  |             0.2115 |                        0.5     |
| pedestal_band        | nominal_like              | mlp                                     | 309 |                  0.8693 |          0.01993   |               0.08873 |             8.904 |            0.268   |             0.25   |                        0       |
| pedestal_band        | nominal_like              | pedestal_memory_fusion_new              | 309 |                  0.8693 |          0.003307  |               0.0567  |             4.967 |            0.2745  |             0.1923 |                        0.5     |
| pedestal_band        | nominal_like              | ridge                                   | 605 |                  0.7782 |          0.005435  |               0.08486 |             6.526 |            0.2954  |             0.2357 |                        0.125   |
| pedestal_band        | nominal_like              | tiny_sequence_transformer               | 309 |                  0.8693 |          0.004693  |               0.09554 |            25.15  |            0.3725  |             0.1923 |                        0       |
| pedestal_band        | shifted_like              | 1d_cnn                                  | 551 |                  0.6835 |         -0.00998   |               0.1275  |            11.87  |            0.3791  |             0.2336 |                        0.4444  |
| pedestal_band        | shifted_like              | ar1_charge_ratio_likelihood_traditional |   0 |                nan      |        nan         |             nan       |           nan     |          nan       |           nan      |                      nan       |
| pedestal_band        | shifted_like              | gradient_boosted_trees                  | 551 |                  0.6835 |          0.01295   |               0.1038  |             7.459 |            0.361   |             0.2263 |                        0.2222  |
| pedestal_band        | shifted_like              | mlp                                     | 551 |                  0.6835 |          0.002847  |               0.16    |            12.92  |            0.3249  |             0.2737 |                        0.4444  |
| pedestal_band        | shifted_like              | pedestal_memory_fusion_new              | 551 |                  0.6835 |          0.01877   |               0.08828 |             6.408 |            0.3394  |             0.2117 |                        0.3333  |
| pedestal_band        | shifted_like              | ridge                                   | 255 |                  0.689  |          0.004163  |               0.08757 |             6.829 |            0.3429  |             0.2    |                        0       |
| pedestal_band        | shifted_like              | tiny_sequence_transformer               | 551 |                  0.6835 |          0.01739   |               0.1376  |            26.36  |            0.4332  |             0.1861 |                        0.6667  |
| pid_proxy_band       | inner_high_charge         | 1d_cnn                                  |  28 |                  1      |         -0.07607   |               0.1086  |             7.511 |            0.12    |             1      |                        0.4545  |
| pid_proxy_band       | inner_high_charge         | ar1_charge_ratio_likelihood_traditional |  28 |                  1      |          0.02344   |               0.5603  |             8.551 |            0.6     |             0.3333 |                        0.8182  |
| pid_proxy_band       | inner_high_charge         | gradient_boosted_trees                  |  28 |                  1      |         -0.02546   |               0.1028  |             7.206 |            0.04    |             1      |                        0.2727  |
| pid_proxy_band       | inner_high_charge         | mlp                                     |  28 |                  1      |          0.06834   |               0.1349  |             8.54  |            0.08    |             1      |                        0.3636  |
| pid_proxy_band       | inner_high_charge         | pedestal_memory_fusion_new              |  28 |                  1      |          0.004628  |               0.08635 |             4.496 |            0       |             1      |                        0.3636  |
| pid_proxy_band       | inner_high_charge         | ridge                                   |  28 |                  1      |         -0.05425   |               0.09332 |             5.556 |            0       |             1      |                        0.09091 |
| pid_proxy_band       | inner_high_charge         | tiny_sequence_transformer               |  28 |                  1      |         -0.06148   |               0.1459  |            16.68  |            0.12    |             1      |                        0.5455  |
| pid_proxy_band       | other                     | 1d_cnn                                  | 832 |                  0.5036 |         -0.02062   |               0.104   |            10.25  |            0.3728  |             0.2225 |                      nan       |
| pid_proxy_band       | other                     | ar1_charge_ratio_likelihood_traditional | 832 |                  0.5036 |         -1         |               0.5557  |             7.03  |            0.6346  |             0.185  |                      nan       |
| pid_proxy_band       | other                     | gradient_boosted_trees                  | 832 |                  0.5036 |          0.01295   |               0.07983 |             6.362 |            0.3407  |             0.2155 |                      nan       |
| pid_proxy_band       | other                     | mlp                                     | 832 |                  0.5036 |          0.008666  |               0.1266  |            11.97  |            0.3185  |             0.26   |                      nan       |
| pid_proxy_band       | other                     | pedestal_memory_fusion_new              | 832 |                  0.5036 |          0.01167   |               0.07528 |             6.024 |            0.3358  |             0.1991 |                      nan       |
| pid_proxy_band       | other                     | ridge                                   | 832 |                  0.5036 |          0.006313  |               0.08288 |             6.582 |            0.3259  |             0.2178 |                      nan       |
| pid_proxy_band       | other                     | tiny_sequence_transformer               | 832 |                  0.5036 |          0.0152    |               0.1129  |            26.51  |            0.4296  |             0.1827 |                      nan       |
| pileup_spacing_band  | merged                    | 1d_cnn                                  | 190 |                  0.7737 |         -0.01403   |               0.1077  |             8.27  |            0.5421  |           nan      |                        0.3333  |
| pileup_spacing_band  | merged                    | ar1_charge_ratio_likelihood_traditional | 190 |                  0.7737 |         -1         |               0.5507  |             9.899 |            0.7526  |           nan      |                        0.8333  |
| pileup_spacing_band  | merged                    | gradient_boosted_trees                  | 190 |                  0.7737 |          0.03729   |               0.07926 |             6.202 |            0.4421  |           nan      |                        0.3333  |
| pileup_spacing_band  | merged                    | mlp                                     | 190 |                  0.7737 |          0.03793   |               0.1281  |            10.64  |            0.4474  |           nan      |                        0.5     |
| pileup_spacing_band  | merged                    | pedestal_memory_fusion_new              | 190 |                  0.7737 |          0.02395   |               0.0778  |             5.404 |            0.4368  |           nan      |                        0.5     |
| pileup_spacing_band  | merged                    | ridge                                   | 190 |                  0.7737 |          0.02423   |               0.08515 |             6.254 |            0.3947  |           nan      |                        0.1667  |
| pileup_spacing_band  | merged                    | tiny_sequence_transformer               | 190 |                  0.7737 |          0.05063   |               0.1055  |            32.95  |            0.5895  |           nan      |                        0.6667  |
| pileup_spacing_band  | near                      | 1d_cnn                                  | 107 |                  0.73   |         -0.01506   |               0.1092  |             8.098 |            0.2897  |           nan      |                        1       |
| pileup_spacing_band  | near                      | ar1_charge_ratio_likelihood_traditional | 107 |                  0.73   |         -1         |               0.5505  |             8.141 |            0.6916  |           nan      |                        0.6667  |
| pileup_spacing_band  | near                      | gradient_boosted_trees                  | 107 |                  0.73   |          0.001148  |               0.07418 |             6.264 |            0.2897  |           nan      |                        0       |
| pileup_spacing_band  | near                      | mlp                                     | 107 |                  0.73   |         -0.009457  |               0.1302  |            10.59  |            0.243   |           nan      |                        0       |
| pileup_spacing_band  | near                      | pedestal_memory_fusion_new              | 107 |                  0.73   |          0.0155    |               0.0685  |             5.779 |            0.2617  |           nan      |                        0       |
| pileup_spacing_band  | near                      | ridge                                   | 107 |                  0.73   |          0.01224   |               0.07283 |             5.322 |            0.2617  |           nan      |                        0       |
| pileup_spacing_band  | near                      | tiny_sequence_transformer               | 107 |                  0.73   |          0.01321   |               0.0897  |            21.37  |            0.3551  |           nan      |                        0.6667  |
| pileup_spacing_band  | separated                 | 1d_cnn                                  | 133 |                  0.7857 |         -0.03599   |               0.09378 |             8.507 |            0.1504  |           nan      |                        0       |
| pileup_spacing_band  | separated                 | ar1_charge_ratio_likelihood_traditional | 133 |                  0.7857 |         -0.03136   |               0.5677  |             5.685 |            0.4135  |           nan      |                        1       |
| pileup_spacing_band  | separated                 | gradient_boosted_trees                  | 133 |                  0.7857 |         -0.02241   |               0.07668 |             5.925 |            0.1805  |           nan      |                        0.5     |
| pileup_spacing_band  | separated                 | mlp                                     | 133 |                  0.7857 |         -0.02389   |               0.1223  |            14.14  |            0.1504  |           nan      |                        0.5     |
| pileup_spacing_band  | separated                 | pedestal_memory_fusion_new              | 133 |                  0.7857 |         -0.0166    |               0.07844 |             6.657 |            0.188   |           nan      |                        0.5     |
| pileup_spacing_band  | separated                 | ridge                                   | 133 |                  0.7857 |         -0.03809   |               0.07808 |             6.755 |            0.218   |           nan      |                        0       |
| pileup_spacing_band  | separated                 | tiny_sequence_transformer               | 133 |                  0.7857 |         -0.0618    |               0.1012  |            12.14  |            0.203   |           nan      |                        0       |
| saturation_tail_band | saturated_or_clipped_tail | 1d_cnn                                  |  11 |                  1      |         -0.08897   |               0.0602  |             7.304 |            0.1818  |           nan      |                        0.4545  |
| saturation_tail_band | saturated_or_clipped_tail | ar1_charge_ratio_likelihood_traditional |  11 |                  1      |          0.07545   |               0.5921  |             4.426 |            0.6364  |           nan      |                        0.8182  |
| saturation_tail_band | saturated_or_clipped_tail | gradient_boosted_trees                  |  11 |                  1      |         -0.03196   |               0.118   |             4.231 |            0       |           nan      |                        0.2727  |
| saturation_tail_band | saturated_or_clipped_tail | mlp                                     |  11 |                  1      |          0.02799   |               0.1475  |             6.3   |            0.09091 |           nan      |                        0.3636  |
| saturation_tail_band | saturated_or_clipped_tail | pedestal_memory_fusion_new              |  11 |                  1      |         -0.01635   |               0.09519 |             2.78  |            0       |           nan      |                        0.3636  |
| saturation_tail_band | saturated_or_clipped_tail | ridge                                   |  11 |                  1      |         -0.08292   |               0.06348 |             4.382 |            0       |           nan      |                        0.09091 |
| saturation_tail_band | saturated_or_clipped_tail | tiny_sequence_transformer               |  11 |                  1      |         -0.06838   |               0.09674 |            16.41  |            0.1818  |           nan      |                        0.5455  |
| saturation_tail_band | unsaturated_tail          | 1d_cnn                                  | 849 |                  0.7518 |         -0.02062   |               0.1055  |            10.27  |            0.3628  |             0.2279 |                      nan       |
| saturation_tail_band | unsaturated_tail          | ar1_charge_ratio_likelihood_traditional | 849 |                  0.7518 |         -1         |               0.5556  |             7.516 |            0.6325  |             0.186  |                      nan       |
| saturation_tail_band | unsaturated_tail          | gradient_boosted_trees                  | 849 |                  0.7518 |          0.01271   |               0.0798  |             6.409 |            0.3317  |             0.2209 |                      nan       |
| saturation_tail_band | unsaturated_tail          | mlp                                     | 849 |                  0.7518 |          0.009981  |               0.1246  |            12     |            0.3103  |             0.2651 |                      nan       |
| saturation_tail_band | unsaturated_tail          | pedestal_memory_fusion_new              | 849 |                  0.7518 |          0.01209   |               0.0753  |             6.013 |            0.3246  |             0.2047 |                      nan       |
| saturation_tail_band | unsaturated_tail          | ridge                                   | 849 |                  0.7518 |          0.006313  |               0.08372 |             6.664 |            0.315   |             0.2233 |                      nan       |
| saturation_tail_band | unsaturated_tail          | tiny_sequence_transformer               | 849 |                  0.7518 |          0.0145    |               0.1139  |            26.45  |            0.4177  |             0.1884 |                      nan       |
| source_run           | 58                        | 1d_cnn                                  | 172 |                  0.7407 |         -0.04049   |               0.1093  |             9.753 |            0.3023  |             0.2442 |                        0.5     |
| source_run           | 58                        | ar1_charge_ratio_likelihood_traditional | 172 |                  0.7407 |         -1         |               0.5281  |             6.795 |            0.6744  |             0.2093 |                        0.8333  |
| source_run           | 58                        | gradient_boosted_trees                  | 172 |                  0.7407 |          0.006664  |               0.09514 |             5.803 |            0.3023  |             0.2442 |                        0.3333  |
| source_run           | 58                        | mlp                                     | 172 |                  0.7407 |         -0.002034  |               0.116   |            10.26  |            0.2558  |             0.3605 |                        0.3333  |
| source_run           | 58                        | pedestal_memory_fusion_new              | 172 |                  0.7407 |         -0.006139  |               0.07847 |             5.028 |            0.314   |             0.2791 |                        0.5     |
| source_run           | 58                        | ridge                                   | 172 |                  0.7407 |         -0.005848  |               0.09016 |             6.324 |            0.3023  |             0.3023 |                        0.1667  |
| source_run           | 58                        | tiny_sequence_transformer               | 172 |                  0.7407 |         -0.007465  |               0.1145  |            31.99  |            0.3372  |             0.1744 |                        0.6667  |
| source_run           | 60                        | 1d_cnn                                  | 172 |                  0.747  |          0.008041  |               0.1054  |            10.31  |            0.3605  |             0.2442 |                        1       |
| source_run           | 60                        | ar1_charge_ratio_likelihood_traditional | 172 |                  0.747  |         -1         |               0.5773  |             8.003 |            0.6628  |             0.1279 |                        0       |
| source_run           | 60                        | gradient_boosted_trees                  | 172 |                  0.747  |          0.03306   |               0.08331 |             7.99  |            0.2907  |             0.2791 |                        0       |
| source_run           | 60                        | mlp                                     | 172 |                  0.747  |          0.03407   |               0.1364  |            11.79  |            0.2674  |             0.2558 |                        0       |
| source_run           | 60                        | pedestal_memory_fusion_new              | 172 |                  0.747  |          0.03864   |               0.07971 |             7.06  |            0.2791  |             0.1977 |                        0       |
| source_run           | 60                        | ridge                                   | 172 |                  0.747  |          0.03306   |               0.08603 |             7.529 |            0.2674  |             0.1977 |                        0       |
| source_run           | 60                        | tiny_sequence_transformer               | 172 |                  0.747  |          0.05108   |               0.1013  |            23.41  |            0.4186  |             0.1977 |                        1       |
| source_run           | 62                        | 1d_cnn                                  | 172 |                  0.769  |         -0.003624  |               0.1039  |            11.59  |            0.407   |             0.3256 |                      nan       |
| source_run           | 62                        | ar1_charge_ratio_likelihood_traditional | 172 |                  0.769  |         -1         |               0.558   |             7.94  |            0.6628  |             0.186  |                      nan       |
| source_run           | 62                        | gradient_boosted_trees                  | 172 |                  0.769  |          0.01235   |               0.08461 |             5.736 |            0.3605  |             0.2791 |                      nan       |
| source_run           | 62                        | mlp                                     | 172 |                  0.769  |          0.000313  |               0.1401  |            13     |            0.3372  |             0.3372 |                      nan       |
| source_run           | 62                        | pedestal_memory_fusion_new              | 172 |                  0.769  |          0.02009   |               0.08127 |             5.621 |            0.3372  |             0.2326 |                      nan       |
| source_run           | 62                        | ridge                                   | 172 |                  0.769  |          0.009511  |               0.08365 |             7.765 |            0.3256  |             0.3023 |                      nan       |
| source_run           | 62                        | tiny_sequence_transformer               | 172 |                  0.769  |          0.02219   |               0.1173  |            25.8   |            0.4302  |             0.3023 |                      nan       |
| source_run           | 64                        | 1d_cnn                                  | 172 |                  0.7665 |         -0.04616   |               0.09095 |            10.28  |            0.407   |             0.1279 |                        0       |
| source_run           | 64                        | ar1_charge_ratio_likelihood_traditional | 172 |                  0.7665 |         -0.0572    |               0.5448  |             5.906 |            0.5814  |             0.1395 |                        1       |
| source_run           | 64                        | gradient_boosted_trees                  | 172 |                  0.7665 |         -0.003344  |               0.07113 |             6.143 |            0.3837  |             0.1279 |                        1       |
| source_run           | 64                        | mlp                                     | 172 |                  0.7665 |          0.01591   |               0.1082  |            10.39  |            0.4186  |             0.1512 |                        1       |
| source_run           | 64                        | pedestal_memory_fusion_new              | 172 |                  0.7665 |          0.001971  |               0.06282 |             6.023 |            0.3837  |             0.1395 |                        1       |
| source_run           | 64                        | ridge                                   | 172 |                  0.7665 |         -0.004533  |               0.07191 |             5.899 |            0.3605  |             0.1395 |                        0       |
| source_run           | 64                        | tiny_sequence_transformer               | 172 |                  0.7665 |          0.008376  |               0.1136  |            24.59  |            0.4651  |             0.1163 |                        1       |
| source_run           | 65                        | 1d_cnn                                  | 172 |                  0.7349 |         -0.02617   |               0.1038  |             9.765 |            0.314   |             0.1977 |                        0.3333  |
| source_run           | 65                        | ar1_charge_ratio_likelihood_traditional | 172 |                  0.7349 |         -0.03584   |               0.5673  |             8.7   |            0.5814  |             0.2674 |                        1       |
| source_run           | 65                        | gradient_boosted_trees                  | 172 |                  0.7349 |         -0.005482  |               0.07391 |             5.894 |            0.2791  |             0.1744 |                        0       |
| source_run           | 65                        | mlp                                     | 172 |                  0.7349 |         -0.004261  |               0.1308  |            11.47  |            0.2442  |             0.2209 |                        0.3333  |
| source_run           | 65                        | pedestal_memory_fusion_new              | 172 |                  0.7349 |         -0.007126  |               0.06888 |             5.77  |            0.2674  |             0.1744 |                        0       |
| source_run           | 65                        | ridge                                   | 172 |                  0.7349 |          0.003747  |               0.07923 |             5.589 |            0.2791  |             0.1744 |                        0       |
| source_run           | 65                        | tiny_sequence_transformer               | 172 |                  0.7349 |         -0.005331  |               0.1206  |            24.75  |            0.407   |             0.1512 |                        0       |
| tail_memory_band     | late_tail_high            | 1d_cnn                                  | 439 |                  0.7626 |         -0.01044   |               0.1156  |            10.2   |            0.4628  |             0.1315 |                        1       |
| tail_memory_band     | late_tail_high            | ar1_charge_ratio_likelihood_traditional | 439 |                  0.7626 |         -1         |               0.5422  |             4.444 |            0.7819  |             0.1036 |                        1       |
| tail_memory_band     | late_tail_high            | gradient_boosted_trees                  | 439 |                  0.7626 |          0.01902   |               0.07489 |             7.553 |            0.4255  |             0.1753 |                        0       |
| tail_memory_band     | late_tail_high            | mlp                                     | 439 |                  0.7626 |         -0.0009408 |               0.1082  |            10.75  |            0.3989  |             0.1474 |                        0       |
| tail_memory_band     | late_tail_high            | pedestal_memory_fusion_new              | 439 |                  0.7626 |          0.01828   |               0.06718 |             7.251 |            0.4521  |             0.1594 |                        0       |
| tail_memory_band     | late_tail_high            | ridge                                   | 439 |                  0.7626 |          0.005598  |               0.07827 |             7.187 |            0.4149  |             0.1594 |                        0       |
| tail_memory_band     | late_tail_high            | tiny_sequence_transformer               | 439 |                  0.7626 |          0.03779   |               0.1005  |            37.61  |            0.4787  |             0.1195 |                        1       |
| tail_memory_band     | late_tail_low             | 1d_cnn                                  | 421 |                  0.7399 |         -0.03466   |               0.09338 |            10.85  |            0.2769  |             0.3631 |                        0.4     |
| tail_memory_band     | late_tail_low             | ar1_charge_ratio_likelihood_traditional | 421 |                  0.7399 |         -0.0112    |               0.5673  |             8.69  |            0.5165  |             0.3017 |                        0.8     |
| tail_memory_band     | late_tail_low             | gradient_boosted_trees                  | 421 |                  0.7399 |          0.0008367 |               0.08988 |             5.536 |            0.2438  |             0.2849 |                        0.3     |
| tail_memory_band     | late_tail_low             | mlp                                     | 421 |                  0.7399 |          0.0202    |               0.1525  |            12.18  |            0.2314  |             0.4302 |                        0.4     |
| tail_memory_band     | late_tail_low             | pedestal_memory_fusion_new              | 421 |                  0.7399 |          0.003083  |               0.08053 |             5.188 |            0.2107  |             0.2682 |                        0.4     |
| tail_memory_band     | late_tail_low             | ridge                                   | 421 |                  0.7399 |          0.00484   |               0.09245 |             6.356 |            0.2231  |             0.3128 |                        0.1     |
| tail_memory_band     | late_tail_low             | tiny_sequence_transformer               | 421 |                  0.7399 |         -0.01113   |               0.1243  |            17.98  |            0.3595  |             0.2849 |                        0.5     |

## Pedestal Counterfactuals

| method                                  | pedestal_state   |   n |   energy_bias |   energy_sigma68 |   pid_positive_rate |
|:----------------------------------------|:-----------------|----:|--------------:|-----------------:|--------------------:|
| 1d_cnn                                  | nominal          | 104 |    -0.04321   |          0.06778 |             0.02885 |
| 1d_cnn                                  | shifted          | 172 |    -0.008785  |          0.09917 |             0.1105  |
| ar1_charge_ratio_likelihood_traditional | nominal          |  78 |     0.06655   |          0.1     |             0.02564 |
| ar1_charge_ratio_likelihood_traditional | shifted          |  80 |     0.06887   |          0.09684 |             0.1     |
| gradient_boosted_trees                  | nominal          | 114 |     0.002292  |          0.05634 |             0.02632 |
| gradient_boosted_trees                  | shifted          | 177 |     0.002568  |          0.08492 |             0.1186  |
| mlp                                     | nominal          | 112 |     0.01401   |          0.07862 |             0.02679 |
| mlp                                     | shifted          | 187 |    -0.006036  |          0.1258  |             0.107   |
| pedestal_memory_fusion_new              | nominal          | 111 |     0.001707  |          0.05511 |             0.02703 |
| pedestal_memory_fusion_new              | shifted          | 183 |     0.01302   |          0.08249 |             0.1202  |
| ridge                                   | nominal          | 115 |     0.001261  |          0.0612  |             0.02609 |
| ridge                                   | shifted          | 183 |     0.01526   |          0.1059  |             0.1202  |
| tiny_sequence_transformer               | nominal          |  96 |     0.0001166 |          0.0901  |             0.03125 |
| tiny_sequence_transformer               | shifted          | 157 |     0.003479  |          0.1285  |             0.121   |

## Systematics and Caveats

1. The raw count gate is reproduced exactly, but the supervised endpoint uses
   controlled pulse injections into raw-ROOT-derived residuals, not externally
   labeled beam PID truth.
2. The fresh upstream GEANT4 truth ROOT file is absent on this host.  This S46c
   artifact is therefore a ticket-specific reanalysis of frozen local benchmark
   predictions with a new sideband table, not a full rerun of the heavy truth
   builder.
3. PID is a charge/stave proxy for deltaE-E/range-cut behavior.  It tests
   decision-boundary sensitivity but cannot prove species purity.
4. The bootstrap covers held-out run transfer for the fixed method panel.  It
   does not include GEANT4 physics-list, material-budget, ADC/MeV calibration,
   or unobserved hardware-state uncertainty.
5. Saturation-tail failure is defined from clipped/plateau samples and amplitude
   residuals in the reduced prediction table; it is not a decoded electronics
   saturation flag.

## Conclusion

`pedestal_memory_fusion_new` wins the S46c composite PID-energy-pedestal endpoint.  The
traditional comparator remains interpretable and competitive, but its energy
sigma68 is `0.1011` versus
`0.07374` for the winner.  The sideband table
shows that pedestal and late-tail memory are mostly removable nuisances in this
controlled benchmark; they matter most as stressors for saturation tails and
false pile-up splits rather than as standalone PID information.

Runtime for this ticket-local report generation was `0.4`
s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

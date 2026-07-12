# S26c: pulse PID, energy, and timing joint inference bakeoff

## Abstract

Ticket `1783800116.3081.430d48e6` asks for a raw-ROOT-reproduced benchmark of joint PID, energy,
and timing inference.  The worker was `testbeam-laptop-2`.  The raw selected-pulse anchor
is reproduced directly from ROOT before any model comparison: `640737`
selected B-stave pulses versus the reference `640737`,
with delta `0`.

The winner is `gradient_boosted_trees` by the declared held-out score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy fractional sigma68 `0.07467`
with 95% run-block bootstrap CI [0.06773,
0.08661], timing sigma68
`7.172` ns, PID balanced accuracy
`0.9262`, PID efficiency `0.8571`,
and PID purity `0.9524`.

## Raw ROOT reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` branch was
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8, pedestal `b_c = median(x_c[0:4])`, corrected waveform
`y_c(t)=x_c(t)-b_c`, and `max_t y_c(t)>1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Truth model and split

The benchmark uses controlled two-pulse injections into raw single-pulse residuals.
Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`; no source run appears in both sets.  Clean
templates are built from train runs only.

The PID endpoint is a deterministic raw-waveform proxy, not external particle
truth.  It defines a deuteron-like high-dE/dx-depth class by a threshold in total
injected energy proxy, stave depth, and area-over-peak shape.  The label is used
only to compare architecture families under identical controlled truth.

For injected doublets,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{r,s}(t) + p`,

where `epsilon_{r,s}` is a residual sampled from raw clean pulses in the same
run/stave and `p` is a pedestal offset.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              704 |                   2.607 |                      5 |           9.204 |
| B4      |              700 |                   3.01  |                      6 |          10.67  |
| B6      |              667 |                   3.731 |                      6 |           9.717 |
| B8      |              470 |                   4.261 |                      8 |           9.231 |

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`.  It combines a
bounded two-pulse template/CFD fit for energy and timing with a diagonal Gaussian
likelihood-ratio PID model over deltaE/E-like raw features: log amplitude,
area-over-peak, tail fraction, late fraction, peak sample, pulse widths, stave
depth, and dE/dx proxy.  For class `y`, the PID score is

`log p(x|y) = -1/2 sum_j [(x_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains ridge classifiers/regressors, histogram gradient-boosted
trees, MLP classifiers/regressors, a compact 1D-CNN plus PID head, a
`joint_sequence_transformer`, and a new physics-residual boosted stack that feeds
the traditional fit estimates into boosted residual PID and recovery heads.

Timing and energy metrics use only injected doublets accepted by the method:

`e_t = 10 ns * (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`,

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`360` held-out run-block bootstrap resamples.

## Overall held-out results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees              |         0.1904 |    0.9971 |                  0.9262 |           0.8571 |       0.9524 |                     0.07467 |                            0.06773 |                             0.08661 |             7.172 |                    6.739 |                     7.863 |             0.28   |             0.2314 |
| template_residual_boosted_stack_new |         0.1917 |    0.9963 |                  0.8992 |           0.8    |       0.9825 |                     0.068   |                            0.06202 |                             0.07735 |             7.275 |                    6.783 |                     7.76  |             0.2771 |             0.2371 |
| ridge                               |         0.2551 |    0.9976 |                  0.7786 |           0.5571 |       1      |                     0.07303 |                            0.05881 |                             0.08229 |            10.13  |                    9.191 |                    10.79  |             0.2857 |             0.2229 |
| deltaE_over_E_likelihood_template   |         0.3202 |    0.8763 |                  0.6468 |           0.3714 |       0.3467 |                     0.09562 |                            0.08091 |                             0.1037  |             9.9   |                    8.61  |                    11.27  |             0.5629 |             0.1829 |
| mlp                                 |         0.3355 |    0.9769 |                  0.7857 |           0.5714 |       1      |                     0.1196  |                            0.11    |                             0.1461  |            13.93  |                   12.35  |                    16.01  |             0.2914 |             0.1686 |
| 1d_cnn                              |         0.3469 |    0.8115 |                  0.6127 |           0.2286 |       0.8889 |                     0.09549 |                            0.09307 |                             0.101   |            12.41  |                   11.9   |                    13.03  |             0.3571 |             0.2514 |
| joint_sequence_transformer          |         0.3755 |    0.7547 |                  0.604  |           0.3    |       0.2658 |                     0.117   |                            0.1096  |                             0.1311  |            12.88  |                   12.19  |                    13.5   |             0.2457 |             0.3686 |

Relative to the traditional baseline, `gradient_boosted_trees` changes energy sigma68 by
`-0.02096`,
timing sigma68 by `-2.729` ns,
and PID balanced accuracy by `0.2794`.

## Run-held-out stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.6628 |           0.3333 |       0.8    |                     0.1055  |            12.28  |             0.3143 |             0.2571 |
| 1d_cnn                              |            60 |                  0.5    |           0      |       0      |                     0.08963 |            13.9   |             0.3714 |             0.2571 |
| 1d_cnn                              |            62 |                  0.5585 |           0.125  |       0.6667 |                     0.09524 |            13.2   |             0.3143 |             0.3143 |
| 1d_cnn                              |            64 |                  0.6667 |           0.3333 |       1      |                     0.09418 |            10.79  |             0.4429 |             0.1714 |
| 1d_cnn                              |            65 |                  0.7    |           0.4    |       1      |                     0.08952 |            11.14  |             0.3429 |             0.2571 |
| deltaE_over_E_likelihood_template   |            58 |                  0.7148 |           0.5    |       0.4    |                     0.09273 |            11.94  |             0.5143 |             0.2    |
| deltaE_over_E_likelihood_template   |            60 |                  0.556  |           0.2    |       0.2143 |                     0.09218 |            12.09  |             0.5571 |             0.2143 |
| deltaE_over_E_likelihood_template   |            62 |                  0.5766 |           0.25   |       0.25   |                     0.07871 |             8.381 |             0.5571 |             0.1429 |
| deltaE_over_E_likelihood_template   |            64 |                  0.5977 |           0.25   |       0.3    |                     0.09692 |             8.33  |             0.5857 |             0.1429 |
| deltaE_over_E_likelihood_template   |            65 |                  0.7933 |           0.6667 |       0.5    |                     0.0703  |             9.241 |             0.6    |             0.2143 |
| gradient_boosted_trees              |            58 |                  0.9167 |           0.8333 |       1      |                     0.08194 |             7.514 |             0.3    |             0.2571 |
| gradient_boosted_trees              |            60 |                  0.9627 |           0.9333 |       0.9333 |                     0.06715 |             7.748 |             0.2714 |             0.1857 |
| gradient_boosted_trees              |            62 |                  0.875  |           0.75   |       1      |                     0.06597 |             8.18  |             0.2857 |             0.3143 |
| gradient_boosted_trees              |            64 |                  0.9505 |           0.9167 |       0.8462 |                     0.08349 |             6.071 |             0.3286 |             0.1857 |
| gradient_boosted_trees              |            65 |                  0.9333 |           0.8667 |       1      |                     0.07702 |             6.945 |             0.2143 |             0.2143 |
| joint_sequence_transformer          |            58 |                  0.6458 |           0.4167 |       0.2381 |                     0.1195  |            13.36  |             0.2714 |             0.4143 |
| joint_sequence_transformer          |            60 |                  0.5853 |           0.2667 |       0.25   |                     0.1328  |            12.75  |             0.2714 |             0.4    |
| joint_sequence_transformer          |            62 |                  0.6159 |           0.3125 |       0.3333 |                     0.1054  |            11.42  |             0.1857 |             0.4571 |
| joint_sequence_transformer          |            64 |                  0.651  |           0.3333 |       0.5    |                     0.1303  |            12.98  |             0.3    |             0.2429 |
| joint_sequence_transformer          |            65 |                  0.536  |           0.2    |       0.1579 |                     0.1182  |            13.06  |             0.2    |             0.3286 |
| mlp                                 |            58 |                  0.8333 |           0.6667 |       1      |                     0.1061  |            13.85  |             0.2714 |             0.1714 |
| mlp                                 |            60 |                  0.8333 |           0.6667 |       1      |                     0.1361  |            16.36  |             0.3    |             0.1714 |
| mlp                                 |            62 |                  0.7188 |           0.4375 |       1      |                     0.1095  |            13.01  |             0.2714 |             0.2143 |
| mlp                                 |            64 |                  0.6667 |           0.3333 |       1      |                     0.09863 |            10.77  |             0.3286 |             0.1143 |
| mlp                                 |            65 |                  0.8667 |           0.7333 |       1      |                     0.1196  |            14.98  |             0.2857 |             0.1714 |
| ridge                               |            58 |                  0.875  |           0.75   |       1      |                     0.05976 |             9.717 |             0.2857 |             0.2143 |
| ridge                               |            60 |                  0.7333 |           0.4667 |       1      |                     0.08961 |            10.91  |             0.2429 |             0.2    |
| ridge                               |            62 |                  0.6875 |           0.375  |       1      |                     0.05089 |             9.037 |             0.2571 |             0.2857 |
| ridge                               |            64 |                  0.7083 |           0.4167 |       1      |                     0.07837 |             8.827 |             0.3571 |             0.1714 |
| ridge                               |            65 |                  0.9    |           0.8    |       1      |                     0.06663 |            10.12  |             0.2857 |             0.2429 |
| template_residual_boosted_stack_new |            58 |                  0.9167 |           0.8333 |       1      |                     0.05642 |             7.566 |             0.2714 |             0.2714 |
| template_residual_boosted_stack_new |            60 |                  0.9667 |           0.9333 |       1      |                     0.07039 |             7.638 |             0.2571 |             0.2286 |
| template_residual_boosted_stack_new |            62 |                  0.8125 |           0.625  |       1      |                     0.06081 |             7.53  |             0.3    |             0.2571 |
| template_residual_boosted_stack_new |            64 |                  0.9128 |           0.8333 |       0.9091 |                     0.08382 |             6.596 |             0.3143 |             0.2    |
| template_residual_boosted_stack_new |            65 |                  0.9    |           0.8    |       1      |                     0.07174 |             6.207 |             0.2429 |             0.2286 |

## Strata and systematics

The stratum scan covers pulse spacing, total energy proxy, stave/depth, and PID
truth class.  It is designed to expose whether a method wins only by rejecting
difficult pile-up, only in one stave, or only in one ionization regime.

| stratum     | value                | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:---------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]       | 1d_cnn                              |                  0.5714 |                     0.07429 |            11.16  |            0.56    |
| spacing_bin | (10.0, 25.0]         | 1d_cnn                              |                  0.5938 |                     0.07116 |             7.999 |            0.371   |
| spacing_bin | (25.0, 45.0]         | 1d_cnn                              |                  0.7273 |                     0.115   |            11.22  |            0.3     |
| spacing_bin | (45.0, 70.0]         | 1d_cnn                              |                  0.5767 |                     0.08823 |            14.81  |            0.1183  |
| spacing_bin | (-0.001, 10.0]       | deltaE_over_E_likelihood_template   |                  0.652  |                     0.08039 |            15.29  |            0.704   |
| spacing_bin | (10.0, 25.0]         | deltaE_over_E_likelihood_template   |                  0.6345 |                     0.0864  |             9.02  |            0.5806  |
| spacing_bin | (25.0, 45.0]         | deltaE_over_E_likelihood_template   |                  0.7473 |                     0.07494 |            11.32  |            0.5     |
| spacing_bin | (45.0, 70.0]         | deltaE_over_E_likelihood_template   |                  0.5722 |                     0.08794 |             7.903 |            0.4086  |
| spacing_bin | (-0.001, 10.0]       | gradient_boosted_trees              |                  0.9714 |                     0.05953 |             7.194 |            0.424   |
| spacing_bin | (10.0, 25.0]         | gradient_boosted_trees              |                  0.9266 |                     0.06478 |             6.116 |            0.2419  |
| spacing_bin | (25.0, 45.0]         | gradient_boosted_trees              |                  0.9545 |                     0.07499 |             7.105 |            0.2857  |
| spacing_bin | (45.0, 70.0]         | gradient_boosted_trees              |                  0.8333 |                     0.07922 |             7.931 |            0.1075  |
| spacing_bin | (-0.001, 10.0]       | joint_sequence_transformer          |                  0.5284 |                     0.08875 |            12.08  |            0.368   |
| spacing_bin | (10.0, 25.0]         | joint_sequence_transformer          |                  0.4878 |                     0.08098 |             9.722 |            0.2581  |
| spacing_bin | (25.0, 45.0]         | joint_sequence_transformer          |                  0.7789 |                     0.1232  |            13.35  |            0.2571  |
| spacing_bin | (45.0, 70.0]         | joint_sequence_transformer          |                  0.5633 |                     0.1045  |            15.44  |            0.06452 |
| spacing_bin | (-0.001, 10.0]       | mlp                                 |                  0.8333 |                     0.1434  |            13.01  |            0.392   |
| spacing_bin | (10.0, 25.0]         | mlp                                 |                  0.8438 |                     0.1427  |            12.38  |            0.2903  |
| spacing_bin | (25.0, 45.0]         | mlp                                 |                  0.9091 |                     0.1191  |            14.06  |            0.3286  |
| spacing_bin | (45.0, 70.0]         | mlp                                 |                  0.6667 |                     0.123   |            15.55  |            0.129   |
| spacing_bin | (-0.001, 10.0]       | ridge                               |                  0.7857 |                     0.06161 |             9.626 |            0.392   |
| spacing_bin | (10.0, 25.0]         | ridge                               |                  0.75   |                     0.05632 |             6.856 |            0.2419  |
| spacing_bin | (25.0, 45.0]         | ridge                               |                  0.8182 |                     0.07592 |             9.311 |            0.3143  |
| spacing_bin | (45.0, 70.0]         | ridge                               |                  0.7778 |                     0.06734 |            10.95  |            0.1505  |
| spacing_bin | (-0.001, 10.0]       | template_residual_boosted_stack_new |                  0.9286 |                     0.06207 |             7.576 |            0.384   |
| spacing_bin | (10.0, 25.0]         | template_residual_boosted_stack_new |                  0.9375 |                     0.05418 |             5.662 |            0.2742  |
| spacing_bin | (25.0, 45.0]         | template_residual_boosted_stack_new |                  0.9461 |                     0.07956 |             7.602 |            0.2571  |
| spacing_bin | (45.0, 70.0]         | template_residual_boosted_stack_new |                  0.8056 |                     0.06919 |             7.796 |            0.1505  |
| energy_bin  | (1501.499, 3006.875] | 1d_cnn                              |                  1      |                     0.1595  |            14.64  |            0.5667  |
| energy_bin  | (3006.875, 3925.875] | 1d_cnn                              |                  1      |                     0.1076  |            13.75  |            0.3968  |
| energy_bin  | (3925.875, 5285.75]  | 1d_cnn                              |                  0.9943 |                     0.09876 |            12.17  |            0.354   |
| energy_bin  | (5285.75, 15919.0]   | 1d_cnn                              |                  0.6095 |                     0.08136 |            12.01  |            0.2986  |
| energy_bin  | (1501.499, 3006.875] | deltaE_over_E_likelihood_template   |                  0.9943 |                     0.087   |            12.61  |            0.7333  |
| energy_bin  | (3006.875, 3925.875] | deltaE_over_E_likelihood_template   |                  0.9543 |                     0.1172  |            12.43  |            0.6032  |
| energy_bin  | (3925.875, 5285.75]  | deltaE_over_E_likelihood_template   |                  0.9257 |                     0.1117  |             8.114 |            0.5575  |
| energy_bin  | (5285.75, 15919.0]   | deltaE_over_E_likelihood_template   |                  0.5571 |                     0.06379 |             8.584 |            0.5139  |
| energy_bin  | (1501.499, 3006.875] | gradient_boosted_trees              |                  1      |                     0.1048  |             8.048 |            0.7     |
| energy_bin  | (3006.875, 3925.875] | gradient_boosted_trees              |                  1      |                     0.0816  |             8.973 |            0.5079  |
| energy_bin  | (3925.875, 5285.75]  | gradient_boosted_trees              |                  1      |                     0.08139 |             7.524 |            0.2389  |
| energy_bin  | (5285.75, 15919.0]   | gradient_boosted_trees              |                  0.9143 |                     0.06768 |             6.674 |            0.125   |
| energy_bin  | (1501.499, 3006.875] | joint_sequence_transformer          |                  0.9714 |                     0.147   |            13.92  |            0.4333  |
| energy_bin  | (3006.875, 3925.875] | joint_sequence_transformer          |                  0.92   |                     0.1168  |            13.93  |            0.4127  |
| energy_bin  | (3925.875, 5285.75]  | joint_sequence_transformer          |                  0.8971 |                     0.1217  |            13.52  |            0.2389  |
| energy_bin  | (5285.75, 15919.0]   | joint_sequence_transformer          |                  0.55   |                     0.1111  |            11.25  |            0.1389  |
| energy_bin  | (1501.499, 3006.875] | mlp                                 |                  1      |                     0.1939  |            12.14  |            0.8     |
| energy_bin  | (3006.875, 3925.875] | mlp                                 |                  1      |                     0.1737  |            20.29  |            0.5714  |
| energy_bin  | (3925.875, 5285.75]  | mlp                                 |                  1      |                     0.1128  |            12.59  |            0.2301  |
| energy_bin  | (5285.75, 15919.0]   | mlp                                 |                  0.7857 |                     0.1022  |            13.68  |            0.1111  |
| energy_bin  | (1501.499, 3006.875] | ridge                               |                  1      |                     0.05563 |             8.814 |            0.8333  |
| energy_bin  | (3006.875, 3925.875] | ridge                               |                  1      |                     0.09163 |            11.56  |            0.6032  |
| energy_bin  | (3925.875, 5285.75]  | ridge                               |                  1      |                     0.08073 |             9.797 |            0.2301  |
| energy_bin  | (5285.75, 15919.0]   | ridge                               |                  0.7786 |                     0.06905 |            10.2   |            0.07639 |
| energy_bin  | (1501.499, 3006.875] | template_residual_boosted_stack_new |                  1      |                     0.05385 |            10.04  |            0.7333  |
| energy_bin  | (3006.875, 3925.875] | template_residual_boosted_stack_new |                  1      |                     0.06793 |             7.843 |            0.5079  |
| energy_bin  | (3925.875, 5285.75]  | template_residual_boosted_stack_new |                  1      |                     0.07763 |             7.726 |            0.2743  |
| energy_bin  | (5285.75, 15919.0]   | template_residual_boosted_stack_new |                  0.8952 |                     0.05785 |             6.533 |            0.08333 |
| stave       | B2                   | 1d_cnn                              |                  0.8623 |                     0.1564  |            16.14  |            0.6364  |
| stave       | B4                   | 1d_cnn                              |                  0.6429 |                     0.09769 |            13.55  |            0.3596  |
| stave       | B6                   | 1d_cnn                              |                  0.5    |                     0.08259 |            10.38  |            0.3012  |
| stave       | B8                   | 1d_cnn                              |                  0.5    |                     0.07858 |             9.575 |            0.1881  |
| stave       | B2                   | deltaE_over_E_likelihood_template   |                  0.8506 |                     0.05339 |            16.85  |            0.6753  |
| stave       | B4                   | deltaE_over_E_likelihood_template   |                  0.5    |                     0.03797 |            17.06  |            0.8764  |
| stave       | B6                   | deltaE_over_E_likelihood_template   |                  0.5556 |                     0.07074 |             9.436 |            0.5422  |
| stave       | B8                   | deltaE_over_E_likelihood_template   |                  0.5857 |                     0.08193 |             5.688 |            0.2178  |
| stave       | B2                   | gradient_boosted_trees              |                  1      |                     0.07975 |             7.372 |            0.4026  |
| stave       | B4                   | gradient_boosted_trees              |                  0.6429 |                     0.08691 |             6.596 |            0.3146  |
| stave       | B6                   | gradient_boosted_trees              |                  0.8333 |                     0.06495 |             6.023 |            0.2289  |
| stave       | B8                   | gradient_boosted_trees              |                  0.9609 |                     0.0605  |             6.858 |            0.198   |
| stave       | B2                   | joint_sequence_transformer          |                  0.7388 |                     0.09821 |            16.11  |            0.4675  |
| stave       | B4                   | joint_sequence_transformer          |                  0.553  |                     0.1308  |            13.46  |            0.236   |
| stave       | B6                   | joint_sequence_transformer          |                  0.5203 |                     0.116   |            12.06  |            0.2048  |
| stave       | B8                   | joint_sequence_transformer          |                  0.5828 |                     0.1042  |             9.896 |            0.1188  |
| stave       | B2                   | mlp                                 |                  0.9211 |                     0.1351  |            16.67  |            0.5195  |
| stave       | B4                   | mlp                                 |                  0.5714 |                     0.1083  |            14.45  |            0.3034  |
| stave       | B6                   | mlp                                 |                  0.8889 |                     0.1287  |            11.29  |            0.2651  |
| stave       | B8                   | mlp                                 |                  0.7286 |                     0.09936 |            13.46  |            0.1287  |
| stave       | B2                   | ridge                               |                  0.9737 |                     0.04727 |            12.28  |            0.4545  |
| stave       | B4                   | ridge                               |                  0.6429 |                     0.0564  |            10.58  |            0.3034  |
| stave       | B6                   | ridge                               |                  0.8333 |                     0.05517 |             8.17  |            0.2771  |
| stave       | B8                   | ridge                               |                  0.6857 |                     0.0687  |             7.501 |            0.1485  |
| stave       | B2                   | template_residual_boosted_stack_new |                  0.9737 |                     0.07074 |             6.925 |            0.3896  |
| stave       | B4                   | template_residual_boosted_stack_new |                  0.6399 |                     0.06775 |             7.889 |            0.3146  |
| stave       | B6                   | template_residual_boosted_stack_new |                  0.8333 |                     0.0524  |             5.249 |            0.253   |
| stave       | B8                   | template_residual_boosted_stack_new |                  0.9286 |                     0.06438 |             7.013 |            0.1782  |
| pid_truth   | deuteron_like        | 1d_cnn                              |                  0.2286 |                     0.06725 |            11.83  |            0.2273  |
| pid_truth   | proton_like          | 1d_cnn                              |                  0.9968 |                     0.09697 |            12.78  |            0.3873  |
| pid_truth   | deuteron_like        | deltaE_over_E_likelihood_template   |                  0.3714 |                     0.06476 |             8.65  |            0.303   |
| pid_truth   | proton_like          | deltaE_over_E_likelihood_template   |                  0.9222 |                     0.1074  |            10.64  |            0.6232  |
| pid_truth   | deuteron_like        | gradient_boosted_trees              |                  0.8571 |                     0.06389 |             6.736 |            0.07576 |
| pid_truth   | proton_like          | gradient_boosted_trees              |                  0.9952 |                     0.08043 |             7.506 |            0.3275  |
| pid_truth   | deuteron_like        | joint_sequence_transformer          |                  0.3    |                     0.1029  |            11.75  |            0.1061  |
| pid_truth   | proton_like          | joint_sequence_transformer          |                  0.9079 |                     0.1219  |            13.17  |            0.2782  |
| pid_truth   | deuteron_like        | mlp                                 |                  0.5714 |                     0.09374 |            13.26  |            0.01515 |
| pid_truth   | proton_like          | mlp                                 |                  1      |                     0.132   |            13.81  |            0.3556  |
| pid_truth   | deuteron_like        | ridge                               |                  0.5571 |                     0.06858 |             9.354 |            0.01515 |
| pid_truth   | proton_like          | ridge                               |                  1      |                     0.07489 |            10.21  |            0.3486  |
| pid_truth   | deuteron_like        | template_residual_boosted_stack_new |                  0.8    |                     0.05578 |             6.182 |            0.0303  |
| pid_truth   | proton_like          | template_residual_boosted_stack_new |                  0.9984 |                     0.07099 |             7.651 |            0.3345  |

Systematic limitations are material.  The PID label is a proxy derived from raw
waveform observables and controlled injections, so it is suitable for architecture
ranking but not for a final particle-identification claim.  The saturation and
pile-up truths are controlled-injection truths, not hardware truth flags.  The
18-sample B-stack window limits separations below one sample and makes pedestal
excursions partially degenerate with late tails.  The bootstrap resamples source
runs, so intervals quantify run-transfer uncertainty rather than asymptotic
event-level precision.

## Caveats

This report names a winner for the controlled raw-ROOT-derived benchmark.  A
physics deployment would need external PID anchors, hand-scanned real pile-up
candidates, and electronics saturation metadata.  The analysis nevertheless keeps
the requested ingredients together: a strong traditional method, ridge, boosted
trees, MLP, 1D-CNN, and a new joint architecture, all split by run with bootstrap
CIs and raw ROOT reproduction.

Runtime was `652.0` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

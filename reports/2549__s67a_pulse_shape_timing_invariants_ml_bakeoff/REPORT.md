# S67a/#2549: Pulse-Shape Timing Invariants under Pedestal Drift and Pile-up

## Abstract

Ticket `2549` asks for a raw-ROOT reproduction followed by an academic-grade
benchmark of a strong traditional timing method against ridge, gradient-boosted
trees, MLP, 1D-CNN, and a sequence model/new architecture.  The claimed issue is
https://github.com/SzeChunYiu/factory-tickets/issues/2549; the worker is `testbeam-laptop-1`.  The winner is **`timing_invariant_residual_fusion_new`** by the
predeclared held-out timing-invariant score.  It has constituent timing sigma68
`6.883` ns with 95% run-block bootstrap CI
[`6.363`, `7.231`],
pile-up miss rate `0.3028`, and false-split rate
`0.1778`.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8 and the pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`,

with corrected pulse `y_ect = x_ect - b_ec` and selected-pulse indicator

`I_ec = 1[max_t y_ect > 1000 ADC]`.

The reproduced number is computed directly from raw ROOT before any benchmark
model is fit.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Run Split and Controlled Pile-up

Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Clean train pulses define per-stave
templates only on train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              736 |                   2.576 |                      5 |           9.187 |
| B4      |              728 |                   2.995 |                      6 |          10.67  |
| B6      |              695 |                   3.749 |                      6 |           9.715 |
| B8      |              474 |                   4.236 |                      8 |           9.248 |

For a controlled pile-up event,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{r,s}(t) + p`,

where `epsilon` is a run-local raw-ROOT residual and `p` is the observed pedestal
state.  Negative controls are clean single-pulse events sampled with the same
run/stave support.  This makes the truth labels controlled while retaining real
baseline, derivative, and residual-shape structure.

## Methods

The traditional comparator is `cfd_derivative_matched_filter_traditional`.  It
starts from a bounded one/two-pulse template fit minimizing

`SSE_k = sum_t [w(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

then applies a derivative matched-filter slew correction

`t'_j = t_j - alpha_j [max_t Delta w(t) / max_t w(t) - median(sharpness)]`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP, compact
1D-CNN, and `tiny_sequence_transformer`, a one-layer self-attention encoder over
the 18-sample waveform.  The new architecture is
`timing_invariant_residual_fusion_new`: it concatenates waveform features,
pedestal/rise/late-tail sidebands, and the traditional fit outputs, then learns
boosted residual detection and timing corrections on train runs only.

## Metrics and CIs

For detected injected doublets, constituent timing error is

`e_t = 10 ns * (hat t - t_true)`.

The robust timing resolution is

`sigma_68(e_t) = [Q_84(e_t) - Q_16(e_t)] / 2`.

The predeclared score is

`C_m = sigma_t + 0.40 |bias_t| + 18 r_miss + 18 r_false + 0.8 r_|e_t|>15ns`.

Confidence intervals are percentile 95% intervals from
`400` bootstrap resamples of held-out runs.

## Overall Held-Out Results

| method                                    |   winner_score |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------------------------------------|---------------:|---------------:|------------------:|-------------------------:|--------------------------:|-----------------------------:|-------------------:|-------------------:|----------------------------:|
| timing_invariant_residual_fusion_new      |          15.81 |        -0.5241 |             6.883 |                    6.363 |                     7.231 |                      0.07968 |             0.3028 |             0.1778 |                     0.06763 |
| gradient_boosted_trees                    |          16.65 |        -0.8814 |             7.418 |                    7.158 |                     7.707 |                      0.09449 |             0.2944 |             0.1944 |                     0.06854 |
| ridge                                     |          17.88 |        -0.7397 |             8.586 |                    7.689 |                     9.342 |                      0.129   |             0.3    |             0.1944 |                     0.06905 |
| mlp                                       |          19.19 |        -0.4338 |             9.823 |                    9.146 |                    10.79  |                      0.179   |             0.325  |             0.1778 |                     0.1204  |
| 1d_cnn                                    |          21.35 |        -1.207  |            10.45  |                   10.04  |                    10.97  |                      0.1549  |             0.4083 |             0.1639 |                     0.09055 |
| cfd_derivative_matched_filter_traditional |          23.99 |         0.3128 |             9.088 |                    7.392 |                    11.12  |                      0.1591  |             0.6333 |             0.1806 |                     0.0902  |
| tiny_sequence_transformer                 |          27.22 |        -8.661  |            13.1   |                   11.86  |                    15.09  |                      0.3734  |             0.3417 |             0.2333 |                     0.1072  |

The traditional comparator has timing sigma68 `9.088` ns
and score `23.99`.  The selected winner changes sigma68 by
`-2.205` ns and the composite
score by `-8.184`.

## Run-Held-Out Stability

| method                                    |   heldout_run |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------------|--------------:|---------------:|------------------:|-----------------------------:|-------------------:|-------------------:|
| 1d_cnn                                    |            58 |       -0.4087  |            10.33  |                      0.1707  |             0.4306 |             0.1944 |
| 1d_cnn                                    |            60 |       -2.499   |            10.52  |                      0.1786  |             0.4167 |             0.1944 |
| 1d_cnn                                    |            62 |       -0.4649  |            10.5   |                      0.1759  |             0.25   |             0.1944 |
| 1d_cnn                                    |            64 |        0.8702  |             9.76  |                      0.1     |             0.4444 |             0.125  |
| 1d_cnn                                    |            65 |       -2.454   |             9.586 |                      0.1389  |             0.5    |             0.1111 |
| cfd_derivative_matched_filter_traditional |            58 |        0.837   |            10.16  |                      0.1667  |             0.625  |             0.1944 |
| cfd_derivative_matched_filter_traditional |            60 |       -1.189   |             8.187 |                      0.2368  |             0.7361 |             0.2083 |
| cfd_derivative_matched_filter_traditional |            62 |       -0.2446  |            11.33  |                      0.2     |             0.5139 |             0.1806 |
| cfd_derivative_matched_filter_traditional |            64 |        0.7064  |             6.706 |                      0.1111  |             0.625  |             0.1528 |
| cfd_derivative_matched_filter_traditional |            65 |        2.81    |             6.837 |                      0.08333 |             0.6667 |             0.1667 |
| gradient_boosted_trees                    |            58 |       -0.1959  |             7.453 |                      0.1     |             0.3056 |             0.2083 |
| gradient_boosted_trees                    |            60 |       -1.555   |             7.738 |                      0.1226  |             0.2639 |             0.2083 |
| gradient_boosted_trees                    |            62 |        0.2515  |             7.173 |                      0.09091 |             0.2361 |             0.2222 |
| gradient_boosted_trees                    |            64 |       -0.7049  |             7.263 |                      0.08824 |             0.2917 |             0.1528 |
| gradient_boosted_trees                    |            65 |       -2.438   |             6.866 |                      0.06667 |             0.375  |             0.1806 |
| mlp                                       |            58 |       -0.3793  |             9.585 |                      0.1633  |             0.3194 |             0.2083 |
| mlp                                       |            60 |       -0.7097  |             9.175 |                      0.1939  |             0.3194 |             0.1806 |
| mlp                                       |            62 |       -1.031   |            10.91  |                      0.1949  |             0.1806 |             0.1806 |
| mlp                                       |            64 |        0.1619  |            10.88  |                      0.1744  |             0.4028 |             0.1667 |
| mlp                                       |            65 |       -0.3372  |             9.989 |                      0.1628  |             0.4028 |             0.1528 |
| ridge                                     |            58 |       -0.5836  |             9.828 |                      0.1389  |             0.25   |             0.2083 |
| ridge                                     |            60 |       -0.08192 |             7.639 |                      0.1275  |             0.2917 |             0.1667 |
| ridge                                     |            62 |        0.7021  |             9.178 |                      0.1429  |             0.2222 |             0.1944 |
| ridge                                     |            64 |       -0.4575  |             6.839 |                      0.07955 |             0.3889 |             0.1667 |
| ridge                                     |            65 |       -2.585   |             7.337 |                      0.1489  |             0.3472 |             0.2361 |
| timing_invariant_residual_fusion_new      |            58 |       -0.7917  |             6.278 |                      0.1091  |             0.2361 |             0.1806 |
| timing_invariant_residual_fusion_new      |            60 |       -1.358   |             6.2   |                      0.09    |             0.3056 |             0.2083 |
| timing_invariant_residual_fusion_new      |            62 |        0.1841  |             6.867 |                      0.05769 |             0.2778 |             0.1944 |
| timing_invariant_residual_fusion_new      |            64 |        0.1719  |             6.685 |                      0.06122 |             0.3194 |             0.1944 |
| timing_invariant_residual_fusion_new      |            65 |       -1.517   |             6.959 |                      0.07778 |             0.375  |             0.1111 |
| tiny_sequence_transformer                 |            58 |       -7.864   |            13.99  |                      0.35    |             0.3056 |             0.25   |
| tiny_sequence_transformer                 |            60 |       -8.627   |            13.27  |                      0.3696  |             0.3611 |             0.2222 |
| tiny_sequence_transformer                 |            62 |       -9.39    |            11.66  |                      0.4     |             0.2361 |             0.25   |
| tiny_sequence_transformer                 |            64 |       -8.658   |            15.89  |                      0.3977  |             0.3889 |             0.2083 |
| tiny_sequence_transformer                 |            65 |       -9.111   |            11.98  |                      0.3452  |             0.4167 |             0.2361 |

## Pedestal, Phase, and Pile-up Strata

| stratum        | value                 | method                                    |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:---------------|:----------------------|:------------------------------------------|---------------:|------------------:|-------------------:|-------------------:|
| spacing_bin    | 0-15                  | 1d_cnn                                    |       0.712    |             9.181 |            0.5928  |          nan       |
| spacing_bin    | 15-30                 | 1d_cnn                                    |      -0.5936   |             6.634 |            0.3288  |          nan       |
| spacing_bin    | 30-65                 | 1d_cnn                                    |      -3.886    |            12.82  |            0.2     |          nan       |
| spacing_bin    | single                | 1d_cnn                                    |     nan        |           nan     |          nan       |            0.1639  |
| spacing_bin    | 0-15                  | cfd_derivative_matched_filter_traditional |       1.706    |            12.17  |            0.7904  |          nan       |
| spacing_bin    | 15-30                 | cfd_derivative_matched_filter_traditional |       2.238    |             8.112 |            0.5479  |          nan       |
| spacing_bin    | 30-65                 | cfd_derivative_matched_filter_traditional |      -0.89     |             9.32  |            0.4667  |          nan       |
| spacing_bin    | single                | cfd_derivative_matched_filter_traditional |     nan        |           nan     |          nan       |            0.1806  |
| spacing_bin    | 0-15                  | gradient_boosted_trees                    |      -0.3873   |             7.339 |            0.4012  |          nan       |
| spacing_bin    | 15-30                 | gradient_boosted_trees                    |      -0.4324   |             6.318 |            0.3014  |          nan       |
| spacing_bin    | 30-65                 | gradient_boosted_trees                    |      -1.569    |             7.989 |            0.1417  |          nan       |
| spacing_bin    | single                | gradient_boosted_trees                    |     nan        |           nan     |          nan       |            0.1944  |
| spacing_bin    | 0-15                  | mlp                                       |      -0.1743   |             7.887 |            0.4251  |          nan       |
| spacing_bin    | 15-30                 | mlp                                       |       0.01601  |             9.15  |            0.3699  |          nan       |
| spacing_bin    | 30-65                 | mlp                                       |      -1.651    |            12.94  |            0.1583  |          nan       |
| spacing_bin    | single                | mlp                                       |     nan        |           nan     |          nan       |            0.1778  |
| spacing_bin    | 0-15                  | ridge                                     |       0.6092   |             7.633 |            0.4072  |          nan       |
| spacing_bin    | 15-30                 | ridge                                     |      -0.5658   |             5.586 |            0.274   |          nan       |
| spacing_bin    | 30-65                 | ridge                                     |      -2.197    |            10.21  |            0.1667  |          nan       |
| spacing_bin    | single                | ridge                                     |     nan        |           nan     |          nan       |            0.1944  |
| spacing_bin    | 0-15                  | timing_invariant_residual_fusion_new      |       0.1662   |             7.023 |            0.4611  |          nan       |
| spacing_bin    | 15-30                 | timing_invariant_residual_fusion_new      |      -0.2383   |             5.253 |            0.2877  |          nan       |
| spacing_bin    | 30-65                 | timing_invariant_residual_fusion_new      |      -1.865    |             7.77  |            0.09167 |          nan       |
| spacing_bin    | single                | timing_invariant_residual_fusion_new      |     nan        |           nan     |          nan       |            0.1778  |
| spacing_bin    | 0-15                  | tiny_sequence_transformer                 |      -9.915    |            12.55  |            0.4611  |          nan       |
| spacing_bin    | 15-30                 | tiny_sequence_transformer                 |      -8.55     |            10.8   |            0.2877  |          nan       |
| spacing_bin    | 30-65                 | tiny_sequence_transformer                 |      -8.297    |            15.25  |            0.2083  |          nan       |
| spacing_bin    | single                | tiny_sequence_transformer                 |     nan        |           nan     |          nan       |            0.2333  |
| ratio_bin      | (-0.001, 0.35]        | 1d_cnn                                    |      -2.052    |            11.04  |            0.5625  |            0.1639  |
| ratio_bin      | (0.35, 0.625]         | 1d_cnn                                    |      -1.987    |            10.4   |            0.4565  |          nan       |
| ratio_bin      | (0.625, 0.875]        | 1d_cnn                                    |      -0.9539   |             9.682 |            0.3299  |          nan       |
| ratio_bin      | (0.875, 1.05]         | 1d_cnn                                    |      -0.1437   |            10.65  |            0.3077  |          nan       |
| ratio_bin      | (-0.001, 0.35]        | cfd_derivative_matched_filter_traditional |      -2.009    |            13.14  |            0.7125  |            0.1806  |
| ratio_bin      | (0.35, 0.625]         | cfd_derivative_matched_filter_traditional |      -0.3521   |             7.794 |            0.6304  |          nan       |
| ratio_bin      | (0.625, 0.875]        | cfd_derivative_matched_filter_traditional |       1.471    |            10.14  |            0.5258  |          nan       |
| ratio_bin      | (0.875, 1.05]         | cfd_derivative_matched_filter_traditional |       1.923    |             6.433 |            0.6813  |          nan       |
| ratio_bin      | (-0.001, 0.35]        | gradient_boosted_trees                    |      -1.903    |             9.25  |            0.55    |            0.1944  |
| ratio_bin      | (0.35, 0.625]         | gradient_boosted_trees                    |      -2.343    |             7.647 |            0.3261  |          nan       |
| ratio_bin      | (0.625, 0.875]        | gradient_boosted_trees                    |      -0.8266   |             6.829 |            0.2165  |          nan       |
| ratio_bin      | (0.875, 1.05]         | gradient_boosted_trees                    |       0.4974   |             7.397 |            0.1209  |          nan       |
| ratio_bin      | (-0.001, 0.35]        | mlp                                       |      -1.75     |            13.39  |            0.6     |            0.1778  |
| ratio_bin      | (0.35, 0.625]         | mlp                                       |      -1.337    |             9.502 |            0.3478  |          nan       |
| ratio_bin      | (0.625, 0.875]        | mlp                                       |      -0.4338   |             9.204 |            0.2165  |          nan       |
| ratio_bin      | (0.875, 1.05]         | mlp                                       |       1.305    |             9.645 |            0.1758  |          nan       |
| ratio_bin      | (-0.001, 0.35]        | ridge                                     |      -2.299    |            11.27  |            0.5375  |            0.1944  |
| ratio_bin      | (0.35, 0.625]         | ridge                                     |      -1.133    |             7.347 |            0.3478  |          nan       |
| ratio_bin      | (0.625, 0.875]        | ridge                                     |      -1        |             6.507 |            0.1959  |          nan       |
| ratio_bin      | (0.875, 1.05]         | ridge                                     |       1.307    |             9.259 |            0.1538  |          nan       |
| ratio_bin      | (-0.001, 0.35]        | timing_invariant_residual_fusion_new      |      -1.229    |             6.998 |            0.5125  |            0.1778  |
| ratio_bin      | (0.35, 0.625]         | timing_invariant_residual_fusion_new      |      -0.8592   |             6.502 |            0.337   |          nan       |
| ratio_bin      | (0.625, 0.875]        | timing_invariant_residual_fusion_new      |      -0.622    |             6.507 |            0.2062  |          nan       |
| ratio_bin      | (0.875, 1.05]         | timing_invariant_residual_fusion_new      |       0.004452 |             7.233 |            0.1868  |          nan       |
| ratio_bin      | (-0.001, 0.35]        | tiny_sequence_transformer                 |     -11.13     |            14.98  |            0.475   |            0.2333  |
| ratio_bin      | (0.35, 0.625]         | tiny_sequence_transformer                 |      -8.437    |            13.18  |            0.4239  |          nan       |
| ratio_bin      | (0.625, 0.875]        | tiny_sequence_transformer                 |      -7.842    |            11.09  |            0.2784  |          nan       |
| ratio_bin      | (0.875, 1.05]         | tiny_sequence_transformer                 |      -8.251    |            14.47  |            0.2088  |          nan       |
| stave          | B2                    | 1d_cnn                                    |      -9.457    |            11.48  |            0.7083  |            0.08163 |
| stave          | B4                    | 1d_cnn                                    |      -4.773    |            10.76  |            0.3163  |            0.1383  |
| stave          | B6                    | 1d_cnn                                    |      -0.4649   |             8.52  |            0.3864  |            0.1364  |
| stave          | B8                    | 1d_cnn                                    |       3.983    |             8.095 |            0.1795  |            0.325   |
| stave          | B2                    | cfd_derivative_matched_filter_traditional |      -2.983    |            17.58  |            0.7396  |            0.1122  |
| stave          | B4                    | cfd_derivative_matched_filter_traditional |      -0.7775   |            10.92  |            0.8571  |            0.07447 |
| stave          | B6                    | cfd_derivative_matched_filter_traditional |      -0.9173   |             8.48  |            0.6023  |            0.1477  |
| stave          | B8                    | cfd_derivative_matched_filter_traditional |       2.151    |             5.634 |            0.2564  |            0.425   |
| stave          | B2                    | gradient_boosted_trees                    |      -7.738    |             7.671 |            0.5104  |            0.09184 |
| stave          | B4                    | gradient_boosted_trees                    |      -2.066    |             8.132 |            0.2347  |            0.1809  |
| stave          | B6                    | gradient_boosted_trees                    |      -0.6805   |             5.262 |            0.2614  |            0.1591  |
| stave          | B8                    | gradient_boosted_trees                    |       2.229    |             6.161 |            0.141   |            0.375   |
| stave          | B2                    | mlp                                       |      -3.784    |            11.31  |            0.5312  |            0.09184 |
| stave          | B4                    | mlp                                       |      -3.057    |             9.873 |            0.2551  |            0.1596  |
| stave          | B6                    | mlp                                       |      -0.4424   |             7.768 |            0.3182  |            0.1818  |
| stave          | B8                    | mlp                                       |       3.172    |             8.173 |            0.1667  |            0.3     |
| stave          | B2                    | ridge                                     |      -6.615    |            10.97  |            0.5208  |            0.1224  |
| stave          | B4                    | ridge                                     |      -2.491    |             7.44  |            0.2551  |            0.1915  |
| stave          | B6                    | ridge                                     |      -0.03413  |             5.824 |            0.2841  |            0.1591  |
| stave          | B8                    | ridge                                     |       2.908    |             7.436 |            0.1026  |            0.325   |
| stave          | B2                    | timing_invariant_residual_fusion_new      |      -4.178    |             7.946 |            0.5312  |            0.08163 |
| stave          | B4                    | timing_invariant_residual_fusion_new      |      -1.422    |             7.509 |            0.2449  |            0.1915  |
| stave          | B6                    | timing_invariant_residual_fusion_new      |      -0.1042   |             4.643 |            0.2614  |            0.1591  |
| stave          | B8                    | timing_invariant_residual_fusion_new      |       1.02     |             6.005 |            0.141   |            0.3     |
| stave          | B2                    | tiny_sequence_transformer                 |     -18.46     |            14.64  |            0.5521  |            0.1429  |
| stave          | B4                    | tiny_sequence_transformer                 |     -12.62     |            12.64  |            0.3163  |            0.1915  |
| stave          | B6                    | tiny_sequence_transformer                 |     -10.16     |            10.04  |            0.3409  |            0.1818  |
| stave          | B8                    | tiny_sequence_transformer                 |      -1.635    |            12.38  |            0.1154  |            0.45    |
| pedestal_state | (-16.022, 1033.65]    | 1d_cnn                                    |       0.3433   |            10.11  |            0.3714  |            0.224   |
| pedestal_state | (-332.086, -16.022]   | 1d_cnn                                    |      -0.5585   |             9.308 |            0.4839  |            0.05479 |
| pedestal_state | (-5597.972, -332.086] | 1d_cnn                                    |      -4.052    |            10.76  |            0.3646  |            0.2584  |
| pedestal_state | (-16.022, 1033.65]    | cfd_derivative_matched_filter_traditional |      -0.1134   |             9.932 |            0.4643  |            0.352   |
| pedestal_state | (-332.086, -16.022]   | cfd_derivative_matched_filter_traditional |       2.99     |             7.197 |            0.6774  |            0.1301  |
| pedestal_state | (-5597.972, -332.086] | cfd_derivative_matched_filter_traditional |      -1.919    |             8.405 |            0.8229  |            0.02247 |
| pedestal_state | (-16.022, 1033.65]    | gradient_boosted_trees                    |      -0.7615   |             7.18  |            0.2429  |            0.248   |
| pedestal_state | (-332.086, -16.022]   | gradient_boosted_trees                    |      -1.522    |             7.278 |            0.2661  |            0.1438  |
| pedestal_state | (-5597.972, -332.086] | gradient_boosted_trees                    |       0.1395   |             8.41  |            0.4062  |            0.2022  |
| pedestal_state | (-16.022, 1033.65]    | mlp                                       |      -0.4032   |             9.026 |            0.2929  |            0.232   |
| pedestal_state | (-332.086, -16.022]   | mlp                                       |      -0.463    |             8.586 |            0.3226  |            0.09589 |
| pedestal_state | (-5597.972, -332.086] | mlp                                       |      -0.5463   |            14.26  |            0.375   |            0.236   |
| pedestal_state | (-16.022, 1033.65]    | ridge                                     |      -0.4889   |             9.172 |            0.25    |            0.288   |
| pedestal_state | (-332.086, -16.022]   | ridge                                     |      -1.156    |             7.995 |            0.2823  |            0.1096  |
| pedestal_state | (-5597.972, -332.086] | ridge                                     |      -0.4438   |             8.514 |            0.3958  |            0.2022  |
| pedestal_state | (-16.022, 1033.65]    | timing_invariant_residual_fusion_new      |      -0.3603   |             6.686 |            0.2286  |            0.272   |
| pedestal_state | (-332.086, -16.022]   | timing_invariant_residual_fusion_new      |      -0.6983   |             6.627 |            0.3387  |            0.1164  |
| pedestal_state | (-5597.972, -332.086] | timing_invariant_residual_fusion_new      |      -0.8848   |             7.562 |            0.3646  |            0.1461  |
| pedestal_state | (-16.022, 1033.65]    | tiny_sequence_transformer                 |      -7.864    |            14.53  |            0.3071  |            0.328   |
| pedestal_state | (-332.086, -16.022]   | tiny_sequence_transformer                 |     -11.1      |            14.04  |            0.371   |            0.1575  |
| pedestal_state | (-5597.972, -332.086] | tiny_sequence_transformer                 |      -8.203    |            11.44  |            0.3542  |            0.2247  |
| phase_state    | (-0.001, 4.5]         | 1d_cnn                                    |       4.61     |            11.51  |            0.381   |            0       |
| phase_state    | (4.5, 6.5]            | 1d_cnn                                    |      -1.207    |            12.09  |            0.2839  |            0.2268  |
| phase_state    | (6.5, 9.5]            | 1d_cnn                                    |      -2.606    |             8.671 |            0.4565  |            0.2138  |
| phase_state    | (9.5, 17.5]           | 1d_cnn                                    |     -17.88     |             7.821 |            0.96    |            0.06316 |
| phase_state    | (-0.001, 4.5]         | cfd_derivative_matched_filter_traditional |      -0.9804   |             7.739 |            0.3095  |            0.5217  |
| phase_state    | (4.5, 6.5]            | cfd_derivative_matched_filter_traditional |       0.8722   |            10.41  |            0.5226  |            0.3299  |
| phase_state    | (6.5, 9.5]            | cfd_derivative_matched_filter_traditional |       0.2673   |             6.104 |            0.7971  |            0.1172  |
| phase_state    | (9.5, 17.5]           | cfd_derivative_matched_filter_traditional |       5.114    |            10.35  |            0.96    |            0.04211 |
| phase_state    | (-0.001, 4.5]         | gradient_boosted_trees                    |       3.197    |             8.443 |            0.3095  |            0.04348 |
| phase_state    | (4.5, 6.5]            | gradient_boosted_trees                    |      -0.3041   |             8.021 |            0.2774  |            0.2062  |
| phase_state    | (6.5, 9.5]            | gradient_boosted_trees                    |      -1.896    |             6.872 |            0.2899  |            0.2552  |
| phase_state    | (9.5, 17.5]           | gradient_boosted_trees                    |      -4.038    |             5.393 |            0.4     |            0.1263  |
| phase_state    | (-0.001, 4.5]         | mlp                                       |       5.758    |            12.86  |            0.3095  |            0       |
| phase_state    | (4.5, 6.5]            | mlp                                       |      -0.5812   |            12.14  |            0.2839  |            0.2577  |
| phase_state    | (6.5, 9.5]            | mlp                                       |      -0.39     |             7.724 |            0.3333  |            0.2138  |

## Shape-Residual Atlas

Held-out normalized residual shapes are embedded with PCA and grouped into four
clusters.  The table reports whether the winning timing invariant remains stable
across residual-shape families rather than only on the aggregate mixture.

| method                                    |   shape_cluster |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |
|:------------------------------------------|----------------:|---------------:|------------------:|-----------------------------:|-------------------:|
| 1d_cnn                                    |               0 |       -4.275   |            11     |                      0.25    |             0.814  |
| 1d_cnn                                    |               1 |       -1.93    |            11.34  |                      0.2059  |             0.2744 |
| 1d_cnn                                    |               2 |        0.2511  |             9.007 |                      0.09649 |             0.4242 |
| 1d_cnn                                    |               3 |       -0.5269  |             8.32  |                      0.03448 |             0.463  |
| cfd_derivative_matched_filter_traditional |               0 |      nan       |           nan     |                    nan       |             1      |
| cfd_derivative_matched_filter_traditional |               1 |       -0.3721  |             9.543 |                      0.1938  |             0.5122 |
| cfd_derivative_matched_filter_traditional |               2 |        2.995   |             9.478 |                      0.129   |             0.6869 |
| cfd_derivative_matched_filter_traditional |               3 |       -0.03289 |             4.092 |                      0.07143 |             0.6111 |
| gradient_boosted_trees                    |               0 |       -3.403   |             7.496 |                      0.06667 |             0.6512 |
| gradient_boosted_trees                    |               1 |        0.474   |             8.359 |                      0.1446  |             0.2622 |
| gradient_boosted_trees                    |               2 |       -2.413   |             7.201 |                      0.06494 |             0.2222 |
| gradient_boosted_trees                    |               3 |       -0.9709  |             5.028 |                      0.0122  |             0.2407 |
| mlp                                       |               0 |       -3.925   |             7.667 |                      0.1538  |             0.6977 |
| mlp                                       |               1 |       -0.1296  |            12.05  |                      0.2353  |             0.2744 |
| mlp                                       |               2 |       -0.5792  |             7.78  |                      0.1133  |             0.2424 |
| mlp                                       |               3 |        0.7522  |             8.156 |                      0.1389  |             0.3333 |
| ridge                                     |               0 |       -4.388   |             6.133 |                      0.1154  |             0.6977 |
| ridge                                     |               1 |       -0.4034  |             9.406 |                      0.1746  |             0.2317 |
| ridge                                     |               2 |        0.5319  |             7.981 |                      0.09459 |             0.2525 |
| ridge                                     |               3 |       -1.2     |             6.576 |                      0.05128 |             0.2778 |
| timing_invariant_residual_fusion_new      |               0 |       -1.504   |             7.998 |                      0.1053  |             0.5581 |
| timing_invariant_residual_fusion_new      |               1 |       -0.1096  |             8.134 |                      0.1151  |             0.2317 |
| timing_invariant_residual_fusion_new      |               2 |       -0.7303  |             6.137 |                      0.04545 |             0.3333 |
| timing_invariant_residual_fusion_new      |               3 |       -0.8915  |             4.694 |                      0.0125  |             0.2593 |
| tiny_sequence_transformer                 |               0 |      -22.46    |            14.56  |                      0.625   |             0.814  |
| tiny_sequence_transformer                 |               1 |       -7.595   |            14.7   |                      0.3578  |             0.2927 |
| tiny_sequence_transformer                 |               2 |      -10.94    |            11.35  |                      0.3696  |             0.303  |
| tiny_sequence_transformer                 |               3 |      -11.82    |            11.97  |                      0.375   |             0.1852 |

## Systematics and Caveats

The pile-up labels are controlled overlays into real raw-ROOT residuals; they
validate recovery under known truth but do not measure the true beam pile-up
rate.  The pedestal-state strata are empirical quantiles of the first four
samples, not independent electronics telemetry.  The 18-sample readout limits
sub-sample separation information and can confound late tails with broad second
pulses.  Bootstrap CIs resample held-out runs, so they quantify run-transfer
uncertainty rather than event-counting uncertainty.  The shape clusters are
diagnostic unsupervised summaries and should not be interpreted as particle-ID
labels.

## Recommendation

Use `timing_invariant_residual_fusion_new` for S67a timing-invariant pulse-shape studies when the priority is
run-held-out timing stability under pedestal drift and moderate pile-up.  Retain
`cfd_derivative_matched_filter_traditional` as the auditable fallback for
deterministic checks and systematic variations.

Runtime was `41.9` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

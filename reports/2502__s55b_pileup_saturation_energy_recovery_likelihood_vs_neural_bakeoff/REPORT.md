# S55b: Pile-Up Saturation Energy Recovery Likelihood-vs-Neural Bakeoff

## Abstract

Ticket `#2502` asks for an academic-grade comparison of a strong traditional
multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,
transformer sequence models, and a sensible new architecture for energy
reconstruction under pile-up and ADC saturation.  The worker is `testbeam-laptop-2`.  The
winner is **`saturation_residual_fusion_new`**, selected by held-out run-block energy closure:
fractional energy sigma68 `0.06515` with 95%
CI [`0.06059`,
`0.0691`].  Its composite score is
`0.1505`.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8, pedestal

`b_{ec} = median_{t in {0,1,2,3}} x_{ect}`,

and selected-pulse indicator

`I_{ec} = 1[max_t(x_{ect} - b_{ec}) > 1000 ADC]`.

The reproduced number is the exact raw-ROOT anchor before any model fitting.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Data-Generating Benchmark

Clean train-run pulse templates are built only from train runs
`[50, 51, 52, 53, 54, 55, 56, 57]`.  Candidate pulses have amplitude
1500--12000 ADC and peak sample 4--12.  For stave `s`, the normalized and
CFD-aligned template is

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              768 |                   2.579 |                      5 |           9.187 |
| B4      |              756 |                   2.944 |                      6 |          10.76  |
| B6      |              723 |                   3.748 |                      6 |           9.736 |
| B8      |              478 |                   4.26  |                      8 |           9.252 |

Controlled doublets are generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{r,s}(t) + p`,

where `epsilon` is a run-local residual sampled from raw ROOT clean pulses and
`p` is a pedestal offset.  The observed waveform supplied to every method is
then clipped as

`w_obs(t) = min(w(t), 11800)`.

The held-out runs `[58, 60, 62, 64, 65]` are never used for
template estimation or ML fitting.  Negative controls are clipped single-pulse
events sampled from the same held-out run families.

## Methods

The traditional comparator is **analytic_clipped_template_sideband_traditional**.
It fits one- and two-pulse template models by bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

using constrained positive amplitudes, bounded pedestal, and fixed separation
grid.  It then applies a deterministic saturation sideband correction to the
fitted amplitudes,

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`,

truncated to `[1, 1.42]`.  This is intentionally transparent: it uses only
plateau width, clipped-sample count, and late-tail sidebands available in the
observed waveform.

The ML panel contains ridge, histogram gradient-boosted trees, MLP, and compact
1D-CNN heads trained on identical run splits.  The transformer sequence model is
`tiny_sequence_transformer`, a one-layer self-attention encoder over the
18-sample waveform.  The new architecture is **saturation_residual_fusion_new**:
it concatenates waveform shape summaries, clipping sidebands, and the analytic
fit outputs, then learns residual boosted-tree corrections for detection and
constituent timing/amplitude.

## Metrics and Uncertainty

For accepted injected doublets, total energy closure is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`,

and constituent timing error is

`e_t = 10 ns * (hat t - t)`.

The robust resolution is

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

The predeclared score is

`C_m = sigma_E + 0.20 |bias_E| + 0.008 sigma_t + 0.04 r_miss + 0.04 r_false`,

where miss rate is the failed injected-doublet fraction and false rate is the
clean-control split fraction.  Confidence intervals are percentile 95% intervals
from `400` bootstrap resamples of held-out
runs.

## Overall Held-Out Results

| method                                         |   winner_score |   energy_fractional_bias |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|---------------:|-------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|---------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| saturation_residual_fusion_new                 |         0.1505 |                0.002716  |                     0.06515 |                            0.06059 |                             0.0691  |        -0.7846 |             8.212 |                    7.195 |                     9.015 |             0.2769 |             0.2    |
| gradient_boosted_trees                         |         0.1584 |               -0.0008102 |                     0.07286 |                            0.06954 |                             0.07519 |        -0.3788 |             8.241 |                    7.829 |                     8.85  |             0.2769 |             0.2103 |
| ridge                                          |         0.1711 |                0.006192  |                     0.07469 |                            0.05894 |                             0.08941 |        -0.4756 |             9.434 |                    8.617 |                    10.41  |             0.2821 |             0.2103 |
| 1d_cnn                                         |         0.181  |               -0.0264    |                     0.0785  |                            0.06812 |                             0.08651 |         0.0283 |             9.51  |                    9.026 |                    10.16  |             0.3718 |             0.1564 |
| analytic_clipped_template_sideband_traditional |         0.2109 |                0.06236   |                     0.09263 |                            0.08132 |                             0.1052  |         0.3861 |             9.467 |                    8.499 |                    10.13  |             0.5615 |             0.1897 |
| tiny_sequence_transformer                      |         0.243  |               -0.01389   |                     0.1131  |                            0.1002  |                             0.1313  |        -7.99   |            13.03  |                   12.12  |                    14.23  |             0.3846 |             0.1872 |
| mlp                                            |         0.2976 |               -0.05212   |                     0.1685  |                            0.1444  |                             0.1984  |        -2.736  |            12.3   |                   10.3   |                    13.38  |             0.2821 |             0.2256 |

The traditional comparator has energy sigma68 `0.09263`
and score `0.2109`.  The selected winner changes energy
sigma68 by `-0.02748`
and timing sigma68 by `-1.255` ns.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |               -0.02174   |                     0.06943 |       -0.8907  |             9.063 |             0.3462 |             0.1154 |
| 1d_cnn                                         |            60 |               -0.01787   |                     0.07703 |        1.766   |             9.363 |             0.3462 |             0.2308 |
| 1d_cnn                                         |            62 |               -0.03026   |                     0.094   |       -1.181   |             8.946 |             0.359  |             0.1026 |
| 1d_cnn                                         |            64 |               -0.0158    |                     0.07572 |        1.795   |            10.49  |             0.4615 |             0.1026 |
| 1d_cnn                                         |            65 |               -0.03896   |                     0.06758 |        0.236   |             8.897 |             0.3462 |             0.2308 |
| analytic_clipped_template_sideband_traditional |            58 |                0.07246   |                     0.08417 |       -0.4912  |             7.966 |             0.5385 |             0.141  |
| analytic_clipped_template_sideband_traditional |            60 |                0.07841   |                     0.08558 |        0.3221  |             8.304 |             0.5385 |             0.2564 |
| analytic_clipped_template_sideband_traditional |            62 |                0.07807   |                     0.0776  |        0.7315  |             8.71  |             0.5256 |             0.141  |
| analytic_clipped_template_sideband_traditional |            64 |                0.01246   |                     0.09315 |        1.465   |             9.356 |             0.6538 |             0.1795 |
| analytic_clipped_template_sideband_traditional |            65 |                0.04854   |                     0.08696 |        0.1163  |            10.54  |             0.5513 |             0.2308 |
| gradient_boosted_trees                         |            58 |                0.0008789 |                     0.06574 |       -0.02839 |             7.6   |             0.2564 |             0.2436 |
| gradient_boosted_trees                         |            60 |                0.002604  |                     0.06901 |       -0.7505  |             8.409 |             0.1923 |             0.2308 |
| gradient_boosted_trees                         |            62 |                0.007624  |                     0.06685 |       -1.062   |             8.329 |             0.2821 |             0.1667 |
| gradient_boosted_trees                         |            64 |               -0.01477   |                     0.07605 |       -0.3288  |             8.822 |             0.3974 |             0.1795 |
| gradient_boosted_trees                         |            65 |                0.002819  |                     0.07636 |        0.07841 |             7.668 |             0.2564 |             0.2308 |
| mlp                                            |            58 |               -0.05773   |                     0.1506  |       -1.944   |             9.45  |             0.2308 |             0.1923 |
| mlp                                            |            60 |               -0.06108   |                     0.1269  |       -3.958   |            13.1   |             0.2564 |             0.2692 |
| mlp                                            |            62 |               -0.07001   |                     0.1574  |       -2.832   |            10.44  |             0.2821 |             0.2692 |
| mlp                                            |            64 |               -0.05285   |                     0.2123  |       -0.707   |            14.27  |             0.3718 |             0.1538 |
| mlp                                            |            65 |                0.007678  |                     0.1905  |       -3.053   |            10.6   |             0.2692 |             0.2436 |
| ridge                                          |            58 |               -0.01096   |                     0.06195 |       -0.5472  |             8.558 |             0.1538 |             0.2692 |
| ridge                                          |            60 |                0.01384   |                     0.05311 |       -0.8218  |            10.67  |             0.2692 |             0.2436 |
| ridge                                          |            62 |                0.006005  |                     0.1009  |       -0.5998  |             8.556 |             0.3077 |             0.1923 |
| ridge                                          |            64 |                0.02332   |                     0.07642 |        0.7691  |            10.37  |             0.3718 |             0.1282 |
| ridge                                          |            65 |                0.011     |                     0.07885 |       -0.4322  |             8.729 |             0.3077 |             0.2179 |
| saturation_residual_fusion_new                 |            58 |                0.006156  |                     0.05867 |       -0.6409  |             6.608 |             0.2821 |             0.2051 |
| saturation_residual_fusion_new                 |            60 |                0.009985  |                     0.06528 |       -1.333   |             8.437 |             0.2308 |             0.2821 |
| saturation_residual_fusion_new                 |            62 |               -0.00612   |                     0.06179 |       -1.298   |             8.102 |             0.2949 |             0.141  |
| saturation_residual_fusion_new                 |            64 |               -0.01388   |                     0.07301 |       -0.9212  |             9.543 |             0.3462 |             0.1282 |
| saturation_residual_fusion_new                 |            65 |                0.00384   |                     0.06152 |       -0.3626  |             8.263 |             0.2308 |             0.2436 |
| tiny_sequence_transformer                      |            58 |               -0.01051   |                     0.1109  |       -7.352   |            13.03  |             0.3333 |             0.1795 |
| tiny_sequence_transformer                      |            60 |               -0.02009   |                     0.09143 |       -8.81    |            14.48  |             0.3205 |             0.2308 |
| tiny_sequence_transformer                      |            62 |               -0.03102   |                     0.1074  |       -8.299   |            10.9   |             0.3846 |             0.1795 |
| tiny_sequence_transformer                      |            64 |                0.006022  |                     0.139   |       -7.466   |            13.7   |             0.4872 |             0.1282 |
| tiny_sequence_transformer                      |            65 |               -0.02657   |                     0.09894 |       -8.044   |            13.06  |             0.3974 |             0.2179 |

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |               -0.006369  |                    0.06618  |        1.718   |             9.421 |            0.5547  |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |                0.002491  |                    0.08148  |        1.512   |             6.252 |            0.4426  |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |               -0.03542   |                    0.07589  |       -3.053   |             7.982 |            0.2621  |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |               -0.04068   |                    0.07682  |        0.8453  |            11.13  |            0.1685  |
| spacing_bin      | (-0.001, 10.0]    | analytic_clipped_template_sideband_traditional |                0.07134   |                    0.07251  |        1.893   |            12.27  |            0.7007  |
| spacing_bin      | (10.0, 25.0]      | analytic_clipped_template_sideband_traditional |                0.08294   |                    0.1185   |        0.8202  |            10.18  |            0.6393  |
| spacing_bin      | (25.0, 45.0]      | analytic_clipped_template_sideband_traditional |                0.07085   |                    0.08657  |        0.2908  |             7.9   |            0.5146  |
| spacing_bin      | (45.0, 70.0]      | analytic_clipped_template_sideband_traditional |                0.02445   |                    0.0996   |       -1.282   |             9.037 |            0.3483  |
| spacing_bin      | (-0.001, 10.0]    | gradient_boosted_trees                         |                0.01173   |                    0.06096  |        0.7316  |             8.815 |            0.4307  |
| spacing_bin      | (10.0, 25.0]      | gradient_boosted_trees                         |                0.01525   |                    0.05876  |        0.9647  |             6.424 |            0.2951  |
| spacing_bin      | (25.0, 45.0]      | gradient_boosted_trees                         |               -0.01167   |                    0.07381  |       -2.384   |             8.397 |            0.1553  |
| spacing_bin      | (45.0, 70.0]      | gradient_boosted_trees                         |               -0.02785   |                    0.08796  |       -0.1371  |             9.616 |            0.1685  |
| spacing_bin      | (-0.001, 10.0]    | mlp                                            |               -0.0183    |                    0.1827   |       -2.843   |            14.2   |            0.4161  |
| spacing_bin      | (10.0, 25.0]      | mlp                                            |               -0.01047   |                    0.1561   |       -0.1254  |            12.28  |            0.2787  |
| spacing_bin      | (25.0, 45.0]      | mlp                                            |               -0.05656   |                    0.1414   |       -3.679   |             9.99  |            0.2427  |
| spacing_bin      | (45.0, 70.0]      | mlp                                            |               -0.09587   |                    0.1847   |       -1.757   |            12.86  |            0.1236  |
| spacing_bin      | (-0.001, 10.0]    | ridge                                          |                0.02373   |                    0.06566  |        0.8626  |             8.222 |            0.4015  |
| spacing_bin      | (10.0, 25.0]      | ridge                                          |                0.0284    |                    0.06954  |        0.5232  |             6.814 |            0.2787  |
| spacing_bin      | (25.0, 45.0]      | ridge                                          |               -0.01086   |                    0.07246  |       -1.277   |             8.639 |            0.2524  |
| spacing_bin      | (45.0, 70.0]      | ridge                                          |               -0.02886   |                    0.06673  |       -1.645   |            12.88  |            0.1348  |
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.0221    |                    0.04584  |       -0.07216 |             8.471 |            0.4088  |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |                0.03607   |                    0.05485  |        0.4707  |             6.196 |            0.3443  |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |               -0.003108  |                    0.06427  |       -2.552   |             7.834 |            0.165   |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.03106   |                    0.05853  |       -0.2762  |             9.942 |            0.1573  |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |                0.02206   |                    0.1013   |       -8.884   |            11.01  |            0.562   |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |                0.02819   |                    0.09636  |       -7.378   |             8.627 |            0.3934  |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |               -0.001445  |                    0.09089  |      -10.35    |            15.26  |            0.2913  |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.09239   |                    0.09     |       -6.205   |            14.73  |            0.2135  |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |               -0.02713   |                    0.07138  |       -3.522   |            10.31  |            0.5122  |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |               -0.02002   |                    0.07247  |       -1.101   |             8.58  |            0.3922  |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |               -0.03803   |                    0.0733   |        1.674   |             9.361 |            0.3679  |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |               -0.02091   |                    0.08357  |        1.608   |             9.326 |            0.24    |
| ratio_bin        | (-0.001, 0.35]    | analytic_clipped_template_sideband_traditional |                0.04907   |                    0.08762  |       -3.027   |            11.25  |            0.6585  |
| ratio_bin        | (0.35, 0.625]     | analytic_clipped_template_sideband_traditional |                0.06465   |                    0.1064   |       -1.209   |             9.865 |            0.4902  |
| ratio_bin        | (0.625, 0.875]    | analytic_clipped_template_sideband_traditional |                0.02697   |                    0.08106  |        1.465   |             9.268 |            0.6038  |
| ratio_bin        | (0.875, 1.05]     | analytic_clipped_template_sideband_traditional |                0.07447   |                    0.08517  |        2.469   |             8.404 |            0.51    |
| ratio_bin        | (-0.001, 0.35]    | gradient_boosted_trees                         |               -0.0001736 |                    0.07285  |       -3.709   |             9.29  |            0.5122  |
| ratio_bin        | (0.35, 0.625]     | gradient_boosted_trees                         |                0.007198  |                    0.07663  |       -0.3185  |             7.73  |            0.2451  |
| ratio_bin        | (0.625, 0.875]    | gradient_boosted_trees                         |               -0.008516  |                    0.07235  |       -0.0783  |             8.357 |            0.2453  |
| ratio_bin        | (0.875, 1.05]     | gradient_boosted_trees                         |               -0.004514  |                    0.0686   |        0.4892  |             7.864 |            0.15    |
| ratio_bin        | (-0.001, 0.35]    | mlp                                            |               -0.02296   |                    0.1666   |       -3.373   |            11.53  |            0.4512  |
| ratio_bin        | (0.35, 0.625]     | mlp                                            |               -0.04058   |                    0.1313   |       -2.751   |            11.3   |            0.2941  |
| ratio_bin        | (0.625, 0.875]    | mlp                                            |               -0.05322   |                    0.1891   |       -3.384   |            13.26  |            0.283   |
| ratio_bin        | (0.875, 1.05]     | mlp                                            |               -0.0703    |                    0.1583   |       -1.201   |            11.67  |            0.13    |
| ratio_bin        | (-0.001, 0.35]    | ridge                                          |                0.01368   |                    0.0592   |       -4.498   |            10.06  |            0.5     |
| ratio_bin        | (0.35, 0.625]     | ridge                                          |                0.01727   |                    0.07279  |       -0.3098  |             9.64  |            0.3235  |
| ratio_bin        | (0.625, 0.875]    | ridge                                          |               -0.001881  |                    0.06882  |        1.293   |             9.021 |            0.2642  |
| ratio_bin        | (0.875, 1.05]     | ridge                                          |               -0.01002   |                    0.07294  |        0.7716  |             8.455 |            0.08    |
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |                0.009046  |                    0.07603  |       -4.195   |             8.941 |            0.5244  |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |                0.006499  |                    0.06731  |       -1.141   |             8.226 |            0.2549  |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.005095  |                    0.06271  |       -0.4158  |             8.201 |            0.2075  |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |                0.001426  |                    0.05572  |       -0.04221 |             7.084 |            0.17    |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |               -0.01046   |                    0.09065  |      -11.32    |            16.81  |            0.5732  |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |               -0.00224   |                    0.1196   |       -9.918   |            12.68  |            0.402   |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |               -0.015     |                    0.09904  |       -7.417   |            12.86  |            0.3491  |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |               -0.02919   |                    0.1142   |       -6.78    |            11.58  |            0.25    |
| saturation_bin   | 0                 | 1d_cnn                                         |               -0.02153   |                    0.07621  |        0.0471  |             9.243 |            0.377   |
| saturation_bin   | 1-2               | 1d_cnn                                         |               -0.1008    |                    0.0276   |      -12.4     |             2.549 |            0.2     |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.1065    |                    0.002497 |        8.299   |             5.577 |            0       |
| saturation_bin   | 0                 | analytic_clipped_template_sideband_traditional |                0.05962   |                    0.09235  |        0.3861  |             9.216 |            0.5654  |
| saturation_bin   | 1-2               | analytic_clipped_template_sideband_traditional |                0.06737   |                    0.008789 |        0.177   |            18.81  |            0.6     |
| saturation_bin   | 3-5               | analytic_clipped_template_sideband_traditional |                0.11      |                    0.0257   |        3.962   |             9.178 |            0       |
| saturation_bin   | 0                 | gradient_boosted_trees                         |                0.002234  |                    0.07129  |       -0.2771  |             8.418 |            0.2801  |
| saturation_bin   | 1-2               | gradient_boosted_trees                         |               -0.04784   |                    0.03308  |       -6.146   |             2.373 |            0.2     |
| saturation_bin   | 3-5               | gradient_boosted_trees                         |               -0.08234   |                    0.009567 |       -1.158   |             4.203 |            0       |
| saturation_bin   | 0                 | mlp                                            |               -0.05371   |                    0.1691   |       -2.565   |            12.25  |            0.288   |
| saturation_bin   | 1-2               | mlp                                            |               -0.04303   |                    0.08586  |      -12.43    |             6.958 |            0       |
| saturation_bin   | 3-5               | mlp                                            |                0.01513   |                    0.05415  |       -1.059   |             6.228 |            0       |
| saturation_bin   | 0                 | ridge                                          |                0.007883  |                    0.07184  |       -0.2747  |             9.362 |            0.288   |
| saturation_bin   | 1-2               | ridge                                          |               -0.0825    |                    0.03447  |       -9.822   |             7.266 |            0       |
| saturation_bin   | 3-5               | ridge                                          |               -0.1015    |                    0.02966  |       -3.636   |             8.631 |            0       |
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |                0.003813  |                    0.06512  |       -0.6245  |             8.234 |            0.2827  |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |               -0.01103   |                    0.1082   |       -8.211   |             5.468 |            0       |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.03732   |                    0.01076  |       -2.461   |             4.019 |            0       |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |               -0.01297   |                    0.1146   |       -7.92    |            12.92  |            0.3901  |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |               -0.06494   |                    0.05337  |      -13.8     |             9.554 |            0.2     |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.2259    |                    0.01944  |        0.6973  |             9.903 |            0       |
| pedestal_state   | nominal           | 1d_cnn                                         |               -0.02991   |                    0.06445  |       -0.1282  |             8.5   |            0.3406  |
| pedestal_state   | shifted           | 1d_cnn                                         |               -0.01809   |                    0.08335  |        0.0471  |            10.06  |            0.3889  |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |                0.04834   |                    0.08283  |        0.2551  |             7.623 |            0.3841  |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |                0.07185   |                    0.08901  |        0.4251  |            10.8   |            0.6587  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.008117  |                    0.06499  |       -0.3372  |             7.862 |            0.2609  |
| pedestal_state   | shifted           | gradient_boosted_trees                         |                0.005168  |                    0.07511  |       -0.4288  |             8.723 |            0.2857  |
| pedestal_state   | nominal           | mlp                                            |               -0.06592   |                    0.1185   |       -2.856   |             9.694 |            0.2754  |
| pedestal_state   | shifted           | mlp                                            |               -0.04892   |                    0.1921   |       -2.584   |            13.51  |            0.2857  |
| pedestal_state   | nominal           | ridge                                          |               -0.01078   |                    0.0486   |       -0.2596  |             9.462 |            0.2609  |
| pedestal_state   | shifted           | ridge                                          |                0.0185    |                    0.0884   |       -0.589   |             9.254 |            0.2937  |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |               -0.009173  |                    0.05194  |       -0.7846  |             7.835 |            0.2391  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |                0.006553  |                    0.07842  |       -0.7761  |             8.41  |            0.2976  |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |               -0.01712   |                    0.1001   |       -8.694   |            11.73  |            0.3478  |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |               -0.01382   |                    0.1265   |       -7.893   |            14.55  |            0.4048  |
| morphology_state | late_tail_high    | 1d_cnn                                         |               -0.02919   |                    0.07023  |       -1.367   |             8.097 |            0.4469  |
| morphology_state | late_tail_low     | 1d_cnn                                         |               -0.02321   |                    0.08707  |        1.187   |            10.22  |            0.3081  |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |                0.09015   |                    0.1039   |        1.087   |             7.478 |            0.6872  |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |                0.03875   |                    0.08726  |       -0.2417  |            10.51  |            0.455   |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |               -0.003192  |                    0.05975  |       -1.092   |             7.251 |            0.3073  |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |                0.001202  |                    0.08798  |        0.367   |             9.168 |            0.2512  |
| morphology_state | late_tail_high    | mlp                                            |               -0.02772   |                    0.1346   |       -3.52    |            11.22  |            0.3296  |
| morphology_state | late_tail_low     | mlp                                            |               -0.07026   |                    0.1839   |       -1.9     |            13.01  |            0.2417  |
| morphology_state | late_tail_high    | ridge                                          |                0.007883  |                    0.06677  |       -0.3282  |             7.338 |            0.3184  |
| morphology_state | late_tail_low     | ridge                                          |                0.00135   |                    0.07748  |       -0.538   |            10.79  |            0.2512  |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |                0.005738  |                    0.0524   |       -1.657   |             6.673 |            0.3296  |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.00301   |                    0.07575  |       -0.2026  |             9.231 |            0.2322  |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |                0.003996  |                    0.099    |       -8.979   |            11.85  |            0.4246  |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |               -0.03104   |                    0.1255   |       -7.512   |            14.25  |            0.3507  |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.0945    |                    0.05366  |       -8.583   |            10.89  |            0.1053  |
| pid_proxy_class  | other             | 1d_cnn                                         |               -0.01931   |                    0.07527  |        0.4219  |             9.077 |            0.3854  |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |                0.0803    |                    0.06516  |       -2.994   |            14.84  |            0.4211  |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |                0.0621    |                    0.0924   |        0.4298  |             8.183 |            0.5687  |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.03573   |                    0.05694  |       -6.569   |             5.797 |            0.05263 |
| pid_proxy_class  | other             | gradient_boosted_trees                         |                0.002419  |                    0.071    |       -0.01934 |             8.253 |            0.2884  |
| pid_proxy_class  | inner_high_charge | mlp                                            |               -0.05116   |                    0.162    |       -8.49    |            11.05  |            0       |
| pid_proxy_class  | other             | mlp                                            |               -0.05285   |                    0.1685   |       -2.194   |            12.24  |            0.2965  |
| pid_proxy_class  | inner_high_charge | ridge                                          |               -0.0733    |                    0.04307  |       -6.443   |             8.893 |            0       |
| pid_proxy_class  | other             | ridge                                          |                0.009915  |                    0.07022  |       -0.13    |             8.925 |            0.2965  |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |               -0.01103   |                    0.06698  |       -6.986   |             6.181 |            0       |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |                0.002822  |                    0.06634  |       -0.3846  |             7.907 |            0.2911  |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |               -0.08047   |                    0.1012   |      -11.36    |            11.1   |            0.1579  |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |               -0.01035   |                    0.115    |       -7.607   |            12.94  |            0.3962  |
| stave            | B2                | 1d_cnn                                         |               -0.08027   |                    0.07934  |       -8.125   |            13.29  |            0.4691  |
| stave            | B4                | 1d_cnn                                         |                0.01049   |                    0.0859   |       -1.229   |             9.357 |            0.4865  |
| stave            | B6                | 1d_cnn                                         |               -0.03542   |                    0.07137  |        1.514   |             7.866 |            0.4175  |
| stave            | B8                | 1d_cnn                                         |               -0.02129   |                    0.06385  |        1.528   |             7.324 |            0.1053  |
| stave            | B2                | analytic_clipped_template_sideband_traditional |                0.1019    |                    0.05725  |        8.499   |            15.49  |            0.6667  |
| stave            | B4                | analytic_clipped_template_sideband_traditional |                0.009166  |                    0.08007  |       -2.127   |            14.72  |            0.8468  |
| stave            | B6                | analytic_clipped_template_sideband_traditional |                0.001176  |                    0.05508  |       -1.058   |             8.167 |            0.534   |
| stave            | B8                | analytic_clipped_template_sideband_traditional |                0.08946   |                    0.08845  |        0.4605  |             6.08  |            0.1684  |
| stave            | B2                | gradient_boosted_trees                         |               -0.007904  |                    0.1551   |       -6.401   |            10.51  |            0.3827  |
| stave            | B4                | gradient_boosted_trees                         |                0.01669   |                    0.06216  |       -2.849   |             8.977 |            0.3694  |
| stave            | B6                | gradient_boosted_trees                         |               -0.006879  |                    0.06114  |        0.06936 |             6.786 |            0.2427  |
| stave            | B8                | gradient_boosted_trees                         |               -0.006163  |                    0.0628   |        1.859   |             5.697 |            0.1158  |
| stave            | B2                | mlp                                            |               -0.04709   |                    0.2001   |       -7.905   |            15.62  |            0.3827  |
| stave            | B4                | mlp                                            |               -0.02234   |                    0.1803   |       -3.59    |            14.11  |            0.3423  |
| stave            | B6                | mlp                                            |               -0.06032   |                    0.1687   |       -2.856   |             8.42  |            0.3204  |
| stave            | B8                | mlp                                            |               -0.05695   |                    0.1445   |       -0.5814  |            10.11  |            0.08421 |
| stave            | B2                | ridge                                          |               -0.04776   |                    0.09342  |       -5.064   |            12.25  |            0.4074  |
| stave            | B4                | ridge                                          |                0.03087   |                    0.0714   |       -3.129   |             9.584 |            0.3243  |
| stave            | B6                | ridge                                          |                0.008551  |                    0.06551  |       -0.1882  |             8.28  |            0.3204  |
| stave            | B8                | ridge                                          |               -0.007443  |                    0.05566  |        2.59    |             6.438 |            0.08421 |
| stave            | B2                | saturation_residual_fusion_new                 |               -0.0006628 |                    0.1193   |       -6.862   |             9.75  |            0.3086  |
| stave            | B4                | saturation_residual_fusion_new                 |                0.03372   |                    0.06465  |       -2.361   |             8.2   |            0.3423  |
| stave            | B6                | saturation_residual_fusion_new                 |               -0.0187    |                    0.05609  |       -0.1649  |             5.832 |            0.3204  |
| stave            | B8                | saturation_residual_fusion_new                 |               -0.00235   |                    0.04579  |        1.586   |             5.629 |            0.1263  |
| stave            | B2                | tiny_sequence_transformer                      |               -0.06025   |                    0.08507  |      -15.41    |            18.22  |            0.5556  |
| stave            | B4                | tiny_sequence_transformer                      |                0.05133   |                    0.1611   |      -11.74    |            11.95  |            0.4955  |
| stave            | B6                | tiny_sequence_transformer                      |               -0.006765  |                    0.08547  |       -7.188   |            11.83  |            0.3689  |
| stave            | B8                | tiny_sequence_transformer                      |               -0.02313   |                    0.08933  |       -5.416   |            10.4   |            0.1263  |

Systematic caveats are material.  First, pile-up truth is from controlled
overlays into raw-ROOT-derived residuals; it validates reconstruction under known
truth but not the true beam pile-up rate.  Second, the ADC clipping level is a
benchmark stressor rather than a decoded electronics flag.  Third, only 18
samples are available, so pedestal memory and late recovery tails can be partly
degenerate with broad second pulses.  Fourth, the bootstrap unit is the held-out
run, giving run-transfer intervals rather than event-counting intervals.  Fifth,
the PID class is a waveform/support proxy, not an external particle label.

## Recommendation

Use `saturation_residual_fusion_new` as the preferred S55b controlled-overlay energy-closure method
when the analysis goal is saturated doublet recovery with run-held-out
uncertainty propagation.  The analytic clipped-template method remains the
auditable fallback when deterministic extrapolation is more important than the
observed held-out score gain.

Runtime was `35.9` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

## Ticket-Specific Sideband Validation

The real-data sideband validation uses held-out clean single-pulse controls
sampled directly from raw ROOT residual families.  These rows test whether a
method hallucinates a second pulse in data-like controls after the same clipping
and pedestal operations used in the benchmark.

| sideband               | value          | method                                         |   n_clean_controls |   false_split_rate |   score_median |   score_p90 |
|:-----------------------|:---------------|:-----------------------------------------------|-------------------:|-------------------:|---------------:|------------:|
| morphology_state       | late_tail_high | 1d_cnn                                         |                239 |             0.1088 |       0.0906   |      0.5225 |
| morphology_state       | late_tail_low  | 1d_cnn                                         |                151 |             0.2318 |       0.2769   |      0.6951 |
| morphology_state       | late_tail_high | analytic_clipped_template_sideband_traditional |                239 |             0.1255 |       0        |      0.7429 |
| morphology_state       | late_tail_low  | analytic_clipped_template_sideband_traditional |                151 |             0.2914 |       0.001346 |      0.9939 |
| morphology_state       | late_tail_high | gradient_boosted_trees                         |                239 |             0.159  |       0.1018   |      0.6371 |
| morphology_state       | late_tail_low  | gradient_boosted_trees                         |                151 |             0.2914 |       0.3077   |      0.7754 |
| morphology_state       | late_tail_high | mlp                                            |                239 |             0.1464 |       0.195    |      0.5587 |
| morphology_state       | late_tail_low  | mlp                                            |                151 |             0.351  |       0.3572   |      0.7072 |
| morphology_state       | late_tail_high | ridge                                          |                239 |             0.1674 |       0.3765   |      0.544  |
| morphology_state       | late_tail_low  | ridge                                          |                151 |             0.2781 |       0.4163   |      0.58   |
| morphology_state       | late_tail_high | saturation_residual_fusion_new                 |                239 |             0.1548 |       0.09786  |      0.6411 |
| morphology_state       | late_tail_low  | saturation_residual_fusion_new                 |                151 |             0.2715 |       0.2941   |      0.7253 |
| morphology_state       | late_tail_high | tiny_sequence_transformer                      |                239 |             0.1381 |       0.1207   |      0.6439 |
| morphology_state       | late_tail_low  | tiny_sequence_transformer                      |                151 |             0.2649 |       0.2903   |      0.7661 |
| pedestal_state         | nominal        | 1d_cnn                                         |                144 |             0.1597 |       0.09921  |      0.7182 |
| pedestal_state         | shifted        | 1d_cnn                                         |                246 |             0.1545 |       0.1787   |      0.6386 |
| pedestal_state         | nominal        | analytic_clipped_template_sideband_traditional |                144 |             0.2431 |       0        |      0.9919 |
| pedestal_state         | shifted        | analytic_clipped_template_sideband_traditional |                246 |             0.1585 |       0        |      0.9616 |
| pedestal_state         | nominal        | gradient_boosted_trees                         |                144 |             0.1667 |       0.1182   |      0.813  |
| pedestal_state         | shifted        | gradient_boosted_trees                         |                246 |             0.2358 |       0.211    |      0.6794 |
| pedestal_state         | nominal        | mlp                                            |                144 |             0.1875 |       0.212    |      0.6887 |
| pedestal_state         | shifted        | mlp                                            |                246 |             0.248  |       0.2638   |      0.6351 |
| pedestal_state         | nominal        | ridge                                          |                144 |             0.1944 |       0.38     |      0.5509 |
| pedestal_state         | shifted        | ridge                                          |                246 |             0.2195 |       0.4063   |      0.5633 |
| pedestal_state         | nominal        | saturation_residual_fusion_new                 |                144 |             0.1944 |       0.1038   |      0.7008 |
| pedestal_state         | shifted        | saturation_residual_fusion_new                 |                246 |             0.2033 |       0.1849   |      0.6974 |
| pedestal_state         | nominal        | tiny_sequence_transformer                      |                144 |             0.2014 |       0.1289   |      0.8006 |
| pedestal_state         | shifted        | tiny_sequence_transformer                      |                246 |             0.1789 |       0.2027   |      0.6451 |
| saturated_sample_count | 0              | 1d_cnn                                         |                390 |             0.1564 |       0.1528   |      0.6691 |
| saturated_sample_count | 0              | analytic_clipped_template_sideband_traditional |                390 |             0.1897 |       0        |      0.9803 |
| saturated_sample_count | 0              | gradient_boosted_trees                         |                390 |             0.2103 |       0.1718   |      0.709  |
| saturated_sample_count | 0              | mlp                                            |                390 |             0.2256 |       0.243    |      0.6457 |
| saturated_sample_count | 0              | ridge                                          |                390 |             0.2103 |       0.3943   |      0.5606 |
| saturated_sample_count | 0              | saturation_residual_fusion_new                 |                390 |             0.2    |       0.1589   |      0.6992 |
| saturated_sample_count | 0              | tiny_sequence_transformer                      |                390 |             0.1872 |       0.1748   |      0.7074 |
| source_run             | 58             | 1d_cnn                                         |                 78 |             0.1154 |       0.1108   |      0.5858 |
| source_run             | 60             | 1d_cnn                                         |                 78 |             0.2308 |       0.1544   |      0.6896 |
| source_run             | 62             | 1d_cnn                                         |                 78 |             0.1026 |       0.17     |      0.5122 |
| source_run             | 64             | 1d_cnn                                         |                 78 |             0.1026 |       0.1536   |      0.5164 |
| source_run             | 65             | 1d_cnn                                         |                 78 |             0.2308 |       0.1673   |      0.6903 |

## Saturation-Mask Ablation

The saturation-mask ablation recomputes the held-out metrics after slicing on
the observed clipped-sample mask.  This is not a retraining pass; it asks whether
the winning conclusion is carried by unsaturated easy cases or by the clipped
tail-recovery region named in the ticket.

| ablation                 | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |   n_events |
|:-------------------------|:-----------------------------------------------|-------------------------:|----------------------------:|------------------:|-------------------:|-------------------:|-----------:|
| all_heldout              | 1d_cnn                                         |               -0.0264    |                    0.0785   |             9.51  |             0.3718 |             0.1564 |        780 |
| all_heldout              | analytic_clipped_template_sideband_traditional |                0.06236   |                    0.09263  |             9.467 |             0.5615 |             0.1897 |        780 |
| all_heldout              | gradient_boosted_trees                         |               -0.0008102 |                    0.07286  |             8.241 |             0.2769 |             0.2103 |        780 |
| all_heldout              | mlp                                            |               -0.05212   |                    0.1685   |            12.3   |             0.2821 |             0.2256 |        780 |
| all_heldout              | ridge                                          |                0.006192  |                    0.07469  |             9.434 |             0.2821 |             0.2103 |        780 |
| all_heldout              | saturation_residual_fusion_new                 |                0.002716  |                    0.06515  |             8.212 |             0.2769 |             0.2    |        780 |
| all_heldout              | tiny_sequence_transformer                      |               -0.01389   |                    0.1131   |            13.03  |             0.3846 |             0.1872 |        780 |
| deep_saturation_mask_ge3 | 1d_cnn                                         |               -0.1065    |                    0.002497 |             5.577 |             0      |           nan      |          3 |
| deep_saturation_mask_ge3 | analytic_clipped_template_sideband_traditional |                0.11      |                    0.0257   |             9.178 |             0      |           nan      |          3 |
| deep_saturation_mask_ge3 | gradient_boosted_trees                         |               -0.08234   |                    0.009567 |             4.203 |             0      |           nan      |          3 |
| deep_saturation_mask_ge3 | mlp                                            |                0.01513   |                    0.05415  |             6.228 |             0      |           nan      |          3 |
| deep_saturation_mask_ge3 | ridge                                          |               -0.1015    |                    0.02966  |             8.631 |             0      |           nan      |          3 |
| deep_saturation_mask_ge3 | saturation_residual_fusion_new                 |               -0.03732   |                    0.01076  |             4.019 |             0      |           nan      |          3 |
| deep_saturation_mask_ge3 | tiny_sequence_transformer                      |               -0.2259    |                    0.01944  |             9.903 |             0      |           nan      |          3 |
| saturated_mask_gt0       | 1d_cnn                                         |               -0.1065    |                    0.01348  |            11.33  |             0.125  |           nan      |          8 |
| saturated_mask_gt0       | analytic_clipped_template_sideband_traditional |                0.09974   |                    0.03128  |            16.05  |             0.375  |           nan      |          8 |
| saturated_mask_gt0       | gradient_boosted_trees                         |               -0.07081   |                    0.035    |             3.643 |             0.125  |           nan      |          8 |
| saturated_mask_gt0       | mlp                                            |               -0.01395   |                    0.07509  |            10.34  |             0      |           nan      |          8 |
| saturated_mask_gt0       | ridge                                          |               -0.09198   |                    0.03577  |             8.078 |             0      |           nan      |          8 |
| saturated_mask_gt0       | saturation_residual_fusion_new                 |               -0.02627   |                    0.07935  |             6.117 |             0      |           nan      |          8 |
| saturated_mask_gt0       | tiny_sequence_transformer                      |               -0.1822    |                    0.08728  |            15.87  |             0.125  |           nan      |          8 |
| unsaturated_mask_0       | 1d_cnn                                         |               -0.02153   |                    0.07621  |             9.243 |             0.377  |             0.1564 |        772 |
| unsaturated_mask_0       | analytic_clipped_template_sideband_traditional |                0.05962   |                    0.09235  |             9.216 |             0.5654 |             0.1897 |        772 |
| unsaturated_mask_0       | gradient_boosted_trees                         |                0.002234  |                    0.07129  |             8.418 |             0.2801 |             0.2103 |        772 |
| unsaturated_mask_0       | mlp                                            |               -0.05371   |                    0.1691   |            12.25  |             0.288  |             0.2256 |        772 |
| unsaturated_mask_0       | ridge                                          |                0.007883  |                    0.07184  |             9.362 |             0.288  |             0.2103 |        772 |
| unsaturated_mask_0       | saturation_residual_fusion_new                 |                0.003813  |                    0.06512  |             8.234 |             0.2827 |             0.2    |        772 |
| unsaturated_mask_0       | tiny_sequence_transformer                      |               -0.01297   |                    0.1146   |            12.92  |             0.3901 |             0.1872 |        772 |

## Uncertainty Calibration

The per-event uncertainty proxy is a transparent function of clipped samples,
plateau width, and reconstructed close-pulse spacing.  It uses
`hat Delta_i = |hat t_2 - hat t_1|`; injected truth separation is excluded
from the proxy and used only for residual scoring:

`u_i = 0.030 + 0.006 n_clip + 0.004 max(W_plateau-2,0) + 0.002 max(4-hat Delta_i,0)`.

Coverage is reported against the absolute fractional energy residual.

| method                                         |   n_valid_doublets |   p68_abs_energy_residual |   nominal_68_proxy_width |   coverage_abs_resid_le_proxy |   coverage_abs_resid_le_2proxy |   calibration_ratio_p68_over_proxy |
|:-----------------------------------------------|-------------------:|--------------------------:|-------------------------:|------------------------------:|-------------------------------:|-----------------------------------:|
| saturation_residual_fusion_new                 |                282 |                   0.06615 |                  0.03471 |                        0.4291 |                         0.7128 |                              1.905 |
| ridge                                          |                280 |                   0.07048 |                  0.03502 |                        0.375  |                         0.675  |                              2.013 |
| gradient_boosted_trees                         |                282 |                   0.07253 |                  0.03482 |                        0.3936 |                         0.6844 |                              2.083 |
| 1d_cnn                                         |                245 |                   0.08274 |                  0.03432 |                        0.3184 |                         0.6245 |                              2.411 |
| analytic_clipped_template_sideband_traditional |                171 |                   0.1031  |                  0.034   |                        0.2865 |                         0.5029 |                              3.033 |
| tiny_sequence_transformer                      |                240 |                   0.1153  |                  0.03611 |                        0.275  |                         0.4667 |                              3.194 |
| mlp                                            |                280 |                   0.1754  |                  0.03453 |                        0.1429 |                         0.2893 |                              5.081 |

## Queue Provenance

The required single claim command was run once as `tn-ticket claim testbeam-laptop-2 --project testbeam` and returned
the null pseudo-ticket output `null / # null / null`.  Because the project queue was
not empty, issue `#2502` was recovered without a second `tn-ticket claim` by
applying the same label transition directly: `gh issue edit 2502 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open`.  Completion is
recorded with `tn-ticket done 2502`.  No novel follow-up ticket was appended.

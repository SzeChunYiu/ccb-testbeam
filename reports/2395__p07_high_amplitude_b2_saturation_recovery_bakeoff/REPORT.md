# P07-2395: High-Amplitude B2 Saturation-Recovery Bakeoff

## Abstract

Ticket `#2395` asks for an academic-grade comparison of a strong traditional
rising-edge/template extrapolation method against ridge, gradient-boosted trees, MLP, 1D-CNN,
transformer sequence models, and a sensible new architecture for energy
reconstruction for high-amplitude B2 pulses under injected ADC clipping and pile-up.  The worker is `testbeam-laptop-3`.  The
winner is **`gradient_boosted_trees`**, selected by held-out run-block energy closure:
fractional energy sigma68 `0.07672` with 95%
CI [`0.0722`,
`0.07987`].  Its composite score is
`0.1552`.

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
For the high-amplitude B2 recovery question it acts as a rising-edge/template extrapolator: it fits one- and two-pulse template models by bounded least squares,

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
| gradient_boosted_trees                         |         0.1552 |               -0.009906  |                     0.07672 |                            0.0722  |                             0.07987 |        -0.1995 |             6.911 |                    6.107 |                     7.646 |             0.3538 |             0.1769 |
| saturation_residual_fusion_new                 |         0.1554 |               -0.009538  |                     0.07482 |                            0.05757 |                             0.08212 |        -0.2952 |             7.145 |                    6.194 |                     7.718 |             0.359  |             0.1795 |
| ridge                                          |         0.1652 |                0.0004494 |                     0.07769 |                            0.07296 |                             0.0895  |         0.3856 |             8.204 |                    7.128 |                     9.484 |             0.3744 |             0.1692 |
| 1d_cnn                                         |         0.204  |               -0.02935   |                     0.09783 |                            0.0808  |                             0.1113  |         0.5706 |             9.608 |                    8.894 |                    11.07  |             0.4179 |             0.1667 |
| mlp                                            |         0.2242 |               -0.02468   |                     0.1082  |                            0.1006  |                             0.1213  |        -1.017  |            10.54  |                    9.762 |                    11.17  |             0.4769 |             0.1923 |
| analytic_clipped_template_sideband_traditional |         0.2254 |                0.07582   |                     0.1087  |                            0.09085 |                             0.1271  |         0.4542 |             8.849 |                    8.007 |                    10.26  |             0.5821 |             0.1846 |
| tiny_sequence_transformer                      |         0.2501 |               -0.0924    |                     0.07707 |                            0.06923 |                             0.08955 |        -2.678  |            16.15  |                   15.78  |                    16.71  |             0.3949 |             0.2385 |

The traditional comparator has energy sigma68 `0.1087`
and score `0.2254`.  The selected winner changes energy
sigma68 by `-0.03202`
and timing sigma68 by `-1.938` ns.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |               -0.03159   |                     0.0993  |       -0.3181  |             9.721 |             0.3333 |            0.2308  |
| 1d_cnn                                         |            60 |               -0.003063  |                     0.06559 |        1.402   |             8.738 |             0.4359 |            0.1795  |
| 1d_cnn                                         |            62 |               -0.03196   |                     0.08523 |        0.9826  |            12.51  |             0.3718 |            0.2051  |
| 1d_cnn                                         |            64 |               -0.03201   |                     0.1383  |        0.2711  |             8.348 |             0.5256 |            0.1026  |
| 1d_cnn                                         |            65 |               -0.04927   |                     0.08648 |        0.4165  |             9.084 |             0.4231 |            0.1154  |
| analytic_clipped_template_sideband_traditional |            58 |                0.05886   |                     0.08711 |       -0.423   |             9.084 |             0.5769 |            0.1795  |
| analytic_clipped_template_sideband_traditional |            60 |                0.1104    |                     0.1264  |        1.068   |             8.79  |             0.5769 |            0.141   |
| analytic_clipped_template_sideband_traditional |            62 |                0.08224   |                     0.1132  |        0.102   |            11.17  |             0.5769 |            0.1282  |
| analytic_clipped_template_sideband_traditional |            64 |                0.05218   |                     0.0898  |       -1.311   |             9.783 |             0.641  |            0.1795  |
| analytic_clipped_template_sideband_traditional |            65 |                0.06179   |                     0.08738 |        1.886   |             7.591 |             0.5385 |            0.2949  |
| gradient_boosted_trees                         |            58 |               -0.02257   |                     0.07154 |       -0.8854  |             6.65  |             0.2564 |            0.2179  |
| gradient_boosted_trees                         |            60 |                0.0002477 |                     0.07518 |        1.31    |             5.456 |             0.3974 |            0.2051  |
| gradient_boosted_trees                         |            62 |               -0.001988  |                     0.0623  |        0.1046  |             8.163 |             0.3462 |            0.1538  |
| gradient_boosted_trees                         |            64 |               -0.00667   |                     0.08009 |       -0.05081 |             6.081 |             0.4231 |            0.08974 |
| gradient_boosted_trees                         |            65 |               -0.02506   |                     0.07625 |       -0.543   |             6.838 |             0.3462 |            0.2179  |
| mlp                                            |            58 |               -0.03435   |                     0.1153  |       -1.463   |            10.94  |             0.3974 |            0.2821  |
| mlp                                            |            60 |               -0.003024  |                     0.1053  |       -0.4359  |            11.21  |             0.5385 |            0.2692  |
| mlp                                            |            62 |               -0.02038   |                     0.1032  |       -0.09462 |            11.02  |             0.3846 |            0.141   |
| mlp                                            |            64 |               -0.01324   |                     0.1212  |       -1.828   |             9.592 |             0.5769 |            0.08974 |
| mlp                                            |            65 |               -0.0186    |                     0.1127  |       -1.945   |            10.42  |             0.4872 |            0.1795  |
| ridge                                          |            58 |               -0.01394   |                     0.07823 |       -0.4227  |             8.227 |             0.3333 |            0.2692  |
| ridge                                          |            60 |                0.009458  |                     0.09059 |        0.7581  |             8.199 |             0.3846 |            0.1282  |
| ridge                                          |            62 |                0.008462  |                     0.06944 |       -0.7762  |            10.49  |             0.3205 |            0.1795  |
| ridge                                          |            64 |                0.01334   |                     0.08516 |        1.212   |             6.896 |             0.4359 |            0.1154  |
| ridge                                          |            65 |               -0.01177   |                     0.07296 |        0.03119 |             7.933 |             0.3974 |            0.1538  |
| saturation_residual_fusion_new                 |            58 |               -0.01261   |                     0.04637 |       -1.62    |             7.471 |             0.2821 |            0.2308  |
| saturation_residual_fusion_new                 |            60 |                0.01386   |                     0.07671 |        0.9607  |             5.555 |             0.3974 |            0.2308  |
| saturation_residual_fusion_new                 |            62 |               -0.01024   |                     0.07844 |       -0.3391  |             7.947 |             0.3205 |            0.1538  |
| saturation_residual_fusion_new                 |            64 |                0.02567   |                     0.07863 |        0.1648  |             6.08  |             0.4103 |            0.1026  |
| saturation_residual_fusion_new                 |            65 |               -0.03238   |                     0.06715 |       -0.5484  |             6.597 |             0.3846 |            0.1795  |
| tiny_sequence_transformer                      |            58 |               -0.1105    |                     0.07893 |       -2.981   |            16.62  |             0.3333 |            0.2949  |
| tiny_sequence_transformer                      |            60 |               -0.07642   |                     0.06407 |       -1.473   |            16.18  |             0.4103 |            0.2179  |
| tiny_sequence_transformer                      |            62 |               -0.08899   |                     0.09013 |       -1.715   |            15.64  |             0.3333 |            0.2308  |
| tiny_sequence_transformer                      |            64 |               -0.07367   |                     0.08096 |       -6.045   |            15.59  |             0.5385 |            0.2051  |
| tiny_sequence_transformer                      |            65 |               -0.1002    |                     0.08788 |       -2.771   |            15.51  |             0.359  |            0.2436  |

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |               -0.02869   |                    0.06766  |       4.377    |           11.74   |             0.5865 |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |                0.008171  |                    0.1277   |       0.8904   |            7.454  |             0.4545 |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |               -0.03377   |                    0.08603  |      -1.211    |            8.136  |             0.29   |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |               -0.03681   |                    0.1071   |       0.1009   |           12.35   |             0.1897 |
| spacing_bin      | (-0.001, 10.0]    | analytic_clipped_template_sideband_traditional |                0.09841   |                    0.1148   |       2.934    |           16.43   |             0.6842 |
| spacing_bin      | (10.0, 25.0]      | analytic_clipped_template_sideband_traditional |                0.09045   |                    0.121    |      -0.2203   |            5.577  |             0.7071 |
| spacing_bin      | (25.0, 45.0]      | analytic_clipped_template_sideband_traditional |                0.04651   |                    0.08277  |       0.7784   |            8.799  |             0.43   |
| spacing_bin      | (45.0, 70.0]      | analytic_clipped_template_sideband_traditional |                0.05284   |                    0.08715  |      -2.555    |            8.947  |             0.3966 |
| spacing_bin      | (-0.001, 10.0]    | gradient_boosted_trees                         |                0.01076   |                    0.06683  |       0.6365   |            7.293  |             0.4361 |
| spacing_bin      | (10.0, 25.0]      | gradient_boosted_trees                         |                0.0159    |                    0.08323  |       0.2711   |            5.393  |             0.3737 |
| spacing_bin      | (25.0, 45.0]      | gradient_boosted_trees                         |               -0.02529   |                    0.05032  |      -1.648    |            7.824  |             0.29   |
| spacing_bin      | (45.0, 70.0]      | gradient_boosted_trees                         |               -0.03402   |                    0.08346  |      -0.6719   |            8.54   |             0.2414 |
| spacing_bin      | (-0.001, 10.0]    | mlp                                            |                0.005794  |                    0.087    |       2.805    |           10.29   |             0.5789 |
| spacing_bin      | (10.0, 25.0]      | mlp                                            |                0.02617   |                    0.1037   |      -1.833    |            8.62   |             0.5152 |
| spacing_bin      | (25.0, 45.0]      | mlp                                            |               -0.04687   |                    0.1105   |      -4.847    |           11.72   |             0.41   |
| spacing_bin      | (45.0, 70.0]      | mlp                                            |               -0.06838   |                    0.1341   |      -1.888    |           11.9    |             0.2931 |
| spacing_bin      | (-0.001, 10.0]    | ridge                                          |                0.006902  |                    0.07404  |       2.167    |            7.997  |             0.4662 |
| spacing_bin      | (10.0, 25.0]      | ridge                                          |                0.0435    |                    0.08078  |       1.713    |            5.678  |             0.3737 |
| spacing_bin      | (25.0, 45.0]      | ridge                                          |               -0.01623   |                    0.06463  |      -1.073    |            8.703  |             0.3    |
| spacing_bin      | (45.0, 70.0]      | ridge                                          |               -0.03201   |                    0.08936  |      -3.007    |           10.64   |             0.2931 |
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.006675  |                    0.06671  |       0.6656   |            6.625  |             0.4662 |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |                0.02338   |                    0.07865  |       0.5174   |            5.543  |             0.3838 |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |               -0.02638   |                    0.06362  |      -2.32     |            7.989  |             0.29   |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.0371    |                    0.07318  |      -1.238    |            7.852  |             0.1897 |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |               -0.06729   |                    0.05887  |       1.51     |           14.88   |             0.5263 |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |               -0.06306   |                    0.08168  |      -4.046    |           12.78   |             0.4343 |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |               -0.1184    |                    0.06544  |      -5.367    |           15.84   |             0.3    |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.1219    |                    0.09417  |      -4.227    |           19.22   |             0.1897 |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |               -0.03377   |                    0.1195   |      -3.274    |           11.01   |             0.5743 |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |               -0.03172   |                    0.1015   |       0.3407   |            8.752  |             0.4851 |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |               -0.03201   |                    0.07827  |       1.52     |            9.867  |             0.3021 |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |               -0.02528   |                    0.06752  |       2.068    |            8.472  |             0.2935 |
| ratio_bin        | (-0.001, 0.35]    | analytic_clipped_template_sideband_traditional |                0.1086    |                    0.1211   |       0.116    |           12.32   |             0.6139 |
| ratio_bin        | (0.35, 0.625]     | analytic_clipped_template_sideband_traditional |                0.0402    |                    0.1093   |      -1.599    |            7.081  |             0.604  |
| ratio_bin        | (0.625, 0.875]    | analytic_clipped_template_sideband_traditional |                0.05284   |                    0.1154   |       0.3575   |           10      |             0.5729 |
| ratio_bin        | (0.875, 1.05]     | analytic_clipped_template_sideband_traditional |                0.05886   |                    0.08835  |       1.578    |            7.248  |             0.5326 |
| ratio_bin        | (-0.001, 0.35]    | gradient_boosted_trees                         |               -0.01024   |                    0.08945  |      -2.83     |           10.11   |             0.5743 |
| ratio_bin        | (0.35, 0.625]     | gradient_boosted_trees                         |               -0.004841  |                    0.07565  |       0.139    |            6.103  |             0.396  |
| ratio_bin        | (0.625, 0.875]    | gradient_boosted_trees                         |               -0.01466   |                    0.0652   |      -0.1271   |            6.941  |             0.1875 |
| ratio_bin        | (0.875, 1.05]     | gradient_boosted_trees                         |               -0.01469   |                    0.06511  |       0.7814   |            6.611  |             0.2391 |
| ratio_bin        | (-0.001, 0.35]    | mlp                                            |               -0.01033   |                    0.09711  |      -5.348    |           11.35   |             0.6634 |
| ratio_bin        | (0.35, 0.625]     | mlp                                            |                0.004812  |                    0.1053   |      -0.585    |            9.496  |             0.5446 |
| ratio_bin        | (0.625, 0.875]    | mlp                                            |               -0.03616   |                    0.0979   |      -0.1989   |           11.75   |             0.3333 |
| ratio_bin        | (0.875, 1.05]     | mlp                                            |               -0.02934   |                    0.122    |      -0.2569   |            9.859  |             0.3478 |
| ratio_bin        | (-0.001, 0.35]    | ridge                                          |               -0.01226   |                    0.09091  |      -4.265    |           11.92   |             0.5644 |
| ratio_bin        | (0.35, 0.625]     | ridge                                          |                0.01378   |                    0.06738  |      -0.318    |            6.585  |             0.4554 |
| ratio_bin        | (0.625, 0.875]    | ridge                                          |               -0.002713  |                    0.0764   |       1.985    |            7.483  |             0.2708 |
| ratio_bin        | (0.875, 1.05]     | ridge                                          |               -0.01074   |                    0.07763  |       2.637    |            7.571  |             0.1848 |
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |               -0.005115  |                    0.07919  |      -2.022    |            9.388  |             0.5446 |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |               -0.006142  |                    0.07311  |      -0.3695   |            5.613  |             0.4158 |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.0152    |                    0.08184  |      -0.006288 |            7.106  |             0.2292 |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |               -0.00808   |                    0.06053  |       0.5719   |            7.022  |             0.2283 |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |               -0.08574   |                    0.08713  |      -3.449    |           17.9    |             0.5248 |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |               -0.09967   |                    0.07552  |      -4.208    |           15.79   |             0.4455 |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |               -0.08769   |                    0.08036  |      -1.322    |           15.61   |             0.3125 |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |               -0.09941   |                    0.07626  |      -2.678    |           16.15   |             0.2826 |
| saturation_bin   | 0                 | 1d_cnn                                         |               -0.02869   |                    0.09452  |       0.5829   |            9.476  |             0.423  |
| saturation_bin   | 1-2               | 1d_cnn                                         |               -0.1403    |                    0.005468 |      -1.32     |            9.407  |             0.25   |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.1027    |                    0.06259  |       1.062    |            7.695  |             0      |
| saturation_bin   | 6+                | 1d_cnn                                         |               -0.1938    |                    0        |      -1.882    |           10.11   |             0      |
| saturation_bin   | 0                 | analytic_clipped_template_sideband_traditional |                0.06935   |                    0.1101   |       0.5536   |            8.662  |             0.5849 |
| saturation_bin   | 1-2               | analytic_clipped_template_sideband_traditional |                0.1371    |                    0.00997  |       0.7655   |           13.25   |             0.5    |
| saturation_bin   | 3-5               | analytic_clipped_template_sideband_traditional |                0.1364    |                    0.02679  |      -4.687    |           11.05   |             0      |
| saturation_bin   | 6+                | analytic_clipped_template_sideband_traditional |              nan         |                  nan        |     nan        |          nan      |             1      |
| saturation_bin   | 0                 | gradient_boosted_trees                         |               -0.00667   |                    0.07563  |      -0.1475   |            6.9    |             0.3603 |
| saturation_bin   | 1-2               | gradient_boosted_trees                         |               -0.08359   |                    0.02852  |      -2.04     |            5.078  |             0      |
| saturation_bin   | 3-5               | gradient_boosted_trees                         |               -0.07706   |                    0.005214 |      -3.244    |            4.837  |             0      |
| saturation_bin   | 6+                | gradient_boosted_trees                         |               -0.146     |                    0        |      -2.824    |            4.713  |             0      |
| saturation_bin   | 0                 | mlp                                            |               -0.01729   |                    0.1134   |      -0.7678   |           10.39   |             0.4856 |
| saturation_bin   | 1-2               | mlp                                            |               -0.04992   |                    0.02603  |      -5.93     |            4.664  |             0      |
| saturation_bin   | 3-5               | mlp                                            |               -0.09456   |                    0.01149  |       3.393    |           13.91   |             0      |
| saturation_bin   | 6+                | mlp                                            |               -0.05306   |                    0        |     -14.48     |            9.4    |             0      |
| saturation_bin   | 0                 | ridge                                          |                0.006902  |                    0.07679  |       0.4221   |            8.249  |             0.3812 |
| saturation_bin   | 1-2               | ridge                                          |               -0.1085    |                    0.01082  |      -5.735    |            6.885  |             0      |
| saturation_bin   | 3-5               | ridge                                          |               -0.1145    |                    0.01261  |      -1.052    |            4.551  |             0      |
| saturation_bin   | 6+                | ridge                                          |               -0.1851    |                    0        |      -7.105    |            3.983  |             0      |
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |               -0.006142  |                    0.07555  |      -0.2551   |            6.966  |             0.3655 |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |               -0.022     |                    0.04578  |      -3.185    |            6.996  |             0      |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.06804   |                    0.01722  |      -5.299    |            5.606  |             0      |
| saturation_bin   | 6+                | saturation_residual_fusion_new                 |               -0.1999    |                    0        |      -2.991    |            4.301  |             0      |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |               -0.08997   |                    0.07475  |      -2.48     |           16.18   |             0.3995 |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |               -0.2124    |                    0.035    |     -10.04     |           12.75   |             0.25   |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.2466    |                    0.009217 |      -1.674    |            7.496  |             0      |
| saturation_bin   | 6+                | tiny_sequence_transformer                      |               -0.3194    |                    0        |     -15.3      |            0.9309 |             0      |
| pedestal_state   | nominal           | 1d_cnn                                         |               -0.04325   |                    0.06728  |       0.5853   |            9.129  |             0.4815 |
| pedestal_state   | shifted           | 1d_cnn                                         |               -0.02164   |                    0.1165   |       0.5568   |           10.15   |             0.3843 |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |                0.04177   |                    0.09699  |       0.8196   |            8.405  |             0.4815 |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |                0.09045   |                    0.1122   |      -0.2203   |            9.31   |             0.6353 |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.0255    |                    0.07347  |      -0.3394   |            6.936  |             0.3778 |
| pedestal_state   | shifted           | gradient_boosted_trees                         |               -0.003926  |                    0.07748  |      -0.1381   |            6.962  |             0.3412 |
| pedestal_state   | nominal           | mlp                                            |               -0.03804   |                    0.1119   |      -1.007    |            8.692  |             0.5333 |
| pedestal_state   | shifted           | mlp                                            |               -0.005004  |                    0.1143   |      -1.214    |           11.27   |             0.4471 |
| pedestal_state   | nominal           | ridge                                          |               -0.01889   |                    0.06695  |       0.5475   |            7.131  |             0.4148 |
| pedestal_state   | shifted           | ridge                                          |                0.01103   |                    0.08927  |       0.2097   |            8.54   |             0.3529 |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |               -0.006142  |                    0.06088  |      -0.06914  |            6.902  |             0.3704 |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |               -0.01014   |                    0.08009  |      -0.34     |            7.249  |             0.3529 |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |               -0.1142    |                    0.06439  |      -1.644    |           16.83   |             0.3852 |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |               -0.08126   |                    0.08542  |      -3.247    |           15.62   |             0.4    |
| morphology_state | late_tail_high    | 1d_cnn                                         |               -0.02652   |                    0.06756  |       0.7155   |            8.913  |             0.4919 |
| morphology_state | late_tail_low     | 1d_cnn                                         |               -0.03206   |                    0.1202   |       0.5385   |           10.44   |             0.3512 |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |                0.1312    |                    0.1051   |       0.416    |            5.972  |             0.6919 |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |                0.03912   |                    0.07899  |       0.4917   |           10.57   |             0.4829 |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |               -0.01526   |                    0.07179  |      -0.1475   |            6.032  |             0.4324 |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |               -0.00693   |                    0.07496  |      -0.4678   |            7.611  |             0.2829 |
| morphology_state | late_tail_high    | mlp                                            |               -0.04831   |                    0.09348  |      -1.813    |           10.1    |             0.5838 |
| morphology_state | late_tail_low     | mlp                                            |                0.006233  |                    0.1344   |      -0.7525   |           11.25   |             0.3805 |
| morphology_state | late_tail_high    | ridge                                          |                0.01442   |                    0.07076  |       0.5388   |            7.588  |             0.4703 |
| morphology_state | late_tail_low     | ridge                                          |               -0.005665  |                    0.08182  |       0.06914  |            8.652  |             0.2878 |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |               -0.009812  |                    0.06063  |      -0.02746  |            6.041  |             0.4378 |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.009538  |                    0.08071  |      -0.4537   |            7.854  |             0.2878 |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |               -0.08862   |                    0.06202  |      -7.044    |           16.36   |             0.4595 |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |               -0.0953    |                    0.08608  |      -1.036    |           15.66   |             0.3366 |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.1432    |                    0.06791  |      -3.789    |           10.49   |             0.3077 |
| pid_proxy_class  | other             | 1d_cnn                                         |               -0.02639   |                    0.08998  |       0.7767   |            9.373  |             0.4258 |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |                0.09225   |                    0.04107  |      -3.298    |           16.67   |             0.3846 |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |                0.06252   |                    0.1141   |       0.595    |            8.137  |             0.5962 |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.07286   |                    0.04328  |      -5.258    |            6.176  |             0.2308 |
| pid_proxy_class  | other             | gradient_boosted_trees                         |               -0.002593  |                    0.07432  |       0.1237   |            6.513  |             0.3626 |
| pid_proxy_class  | inner_high_charge | mlp                                            |               -0.1027    |                    0.08473  |      -3.727    |           11.42   |             0.1923 |
| pid_proxy_class  | other             | mlp                                            |               -0.007502  |                    0.1051   |      -0.4214   |           10.31   |             0.4973 |
| pid_proxy_class  | inner_high_charge | ridge                                          |               -0.07799   |                    0.0506   |      -2.37     |            8.654  |             0      |
| pid_proxy_class  | other             | ridge                                          |                0.0097    |                    0.07598  |       0.5563   |            8.071  |             0.4011 |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |               -0.04348   |                    0.06485  |      -7.929    |            8.224  |             0.1538 |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |               -0.004696  |                    0.07497  |       0.06706  |            6.756  |             0.3736 |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |               -0.1734    |                    0.06401  |      -7.091    |           14.69   |             0.3846 |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |               -0.08539   |                    0.07429  |      -2.48     |           16.03   |             0.3956 |
| stave            | B2                | 1d_cnn                                         |               -0.1331    |                    0.08002  |      -4.91     |            9.854  |             0.6222 |
| stave            | B4                | 1d_cnn                                         |                0.01979   |                    0.09618  |      -1.089    |            9.823  |             0.4151 |
| stave            | B6                | 1d_cnn                                         |               -0.03768   |                    0.06314  |       0.5526   |            7.924  |             0.4066 |
| stave            | B8                | 1d_cnn                                         |               -0.02904   |                    0.06741  |       3.141    |            7.939  |             0.2524 |
| stave            | B2                | analytic_clipped_template_sideband_traditional |                0.105     |                    0.04484  |      -0.3236   |           16.92   |             0.6    |
| stave            | B4                | analytic_clipped_template_sideband_traditional |                0.01017   |                    0.06577  |      -7.253    |           14.64   |             0.8585 |
| stave            | B6                | analytic_clipped_template_sideband_traditional |                0.008546  |                    0.04519  |       1.026    |            7.159  |             0.5934 |
| stave            | B8                | analytic_clipped_template_sideband_traditional |                0.1271    |                    0.1234   |       0.599    |            4.887  |             0.2718 |
| stave            | B2                | gradient_boosted_trees                         |               -0.06939   |                    0.05539  |      -4.821    |            9.465  |             0.5222 |
| stave            | B4                | gradient_boosted_trees                         |                0.02176   |                    0.08229  |      -2.23     |            7.253  |             0.3302 |
| stave            | B6                | gradient_boosted_trees                         |               -0.02052   |                    0.06069  |       0.6077   |            5.458  |             0.3846 |
| stave            | B8                | gradient_boosted_trees                         |               -0.0003516 |                    0.06398  |       2.214    |            5.674  |             0.2039 |
| stave            | B2                | mlp                                            |               -0.07767   |                    0.1023   |      -5.156    |           12.74   |             0.5444 |
| stave            | B4                | mlp                                            |                0.0357    |                    0.1207   |      -2.842    |           10.87   |             0.4811 |
| stave            | B6                | mlp                                            |               -0.02369   |                    0.08943  |      -0.7258   |            9.023  |             0.5385 |
| stave            | B8                | mlp                                            |               -0.02291   |                    0.08934  |       1.366    |           10.28   |             0.3592 |
| stave            | B2                | ridge                                          |               -0.07612   |                    0.05381  |      -3.768    |           11.78   |             0.4667 |
| stave            | B4                | ridge                                          |                0.05863   |                    0.07535  |      -2.746    |            7.871  |             0.3774 |
| stave            | B6                | ridge                                          |               -0.01712   |                    0.05292  |       0.8819   |            6.227  |             0.4066 |
| stave            | B8                | ridge                                          |                0.008893  |                    0.06827  |       3.772    |            7.002  |             0.2621 |
| stave            | B2                | saturation_residual_fusion_new                 |               -0.05333   |                    0.05762  |      -5.568    |           11.29   |             0.5    |
| stave            | B4                | saturation_residual_fusion_new                 |                0.006546  |                    0.07881  |      -1.869    |            7.174  |             0.3774 |
| stave            | B6                | saturation_residual_fusion_new                 |               -0.01059   |                    0.06189  |       0.5119   |            5.281  |             0.3956 |
| stave            | B8                | saturation_residual_fusion_new                 |                0.01248   |                    0.06374  |       1.417    |            5.686  |             0.1845 |
| stave            | B2                | tiny_sequence_transformer                      |               -0.124     |                    0.09428  |      -4.462    |           16.58   |             0.5778 |
| stave            | B4                | tiny_sequence_transformer                      |               -0.05596   |                    0.08472  |      -4.941    |           15.68   |             0.4623 |
| stave            | B6                | tiny_sequence_transformer                      |               -0.1008    |                    0.05297  |      -3.651    |           15.24   |             0.3516 |
| stave            | B8                | tiny_sequence_transformer                      |               -0.08056   |                    0.06525  |       1.418    |           15.2    |             0.2039 |

Systematic caveats are material.  First, pile-up truth is from controlled
overlays into raw-ROOT-derived residuals; it validates reconstruction under known
truth but not the true beam pile-up rate.  Second, the ADC clipping level is a
benchmark stressor rather than a decoded electronics flag.  Third, only 18
samples are available, so pedestal memory and late recovery tails can be partly
degenerate with broad second pulses.  Fourth, the bootstrap unit is the held-out
run, giving run-transfer intervals rather than event-counting intervals.  Fifth,
the PID class is a waveform/support proxy, not an external particle label.

## Recommendation

For the #2395 controlled high-amplitude B2 benchmark, use `gradient_boosted_trees` as the preferred controlled-overlay energy-closure method for this high-amplitude B2 recovery benchmark
when the analysis goal is saturated doublet recovery with run-held-out
uncertainty propagation.  The analytic clipped-template method remains the
auditable fallback when deterministic extrapolation is more important than the
observed held-out score gain.

Runtime was `145.3` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.


## Ticket-Tool Note

The required command `tn-ticket claim testbeam-laptop-3 --project testbeam` was run exactly once.  It hit the previously observed `null|null|null` pseudo-ticket path and did not label an issue.  The oldest open project ticket was then claimed manually with the same label transition (`factory:open` to `factory:claimed`, plus `worker:testbeam-laptop-3`) before this report was produced.  This report directory therefore records both the raw command requirement and the operational workaround.

## #2395-Specific Verdict

The raw ROOT reproduction gate passed with `640737` selected B-stave pulses.  The winner named in `result.json` is `gradient_boosted_trees`.  The result is a controlled artificial-clipping closure on raw-ROOT-derived clean pulses, not a hardware saturation calibration for natural B2 over-range data.

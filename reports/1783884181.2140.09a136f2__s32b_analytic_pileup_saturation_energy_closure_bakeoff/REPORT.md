# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff

## Abstract

Ticket `1783884181.2140.09a136f2` asks for an academic-grade comparison of a strong traditional
multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,
transformer sequence models, and a sensible new architecture for energy
reconstruction under pile-up and ADC saturation.  The worker is `testbeam-laptop-4`.  The
winner is **`saturation_residual_fusion_new`**, selected by held-out run-block energy closure:
fractional energy sigma68 `0.07237` with 95%
CI [`0.06167`,
`0.07685`].  Its composite score is
`0.1575`.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/extracted/root/root`.  For each run, `h101/HRDv` is
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
| saturation_residual_fusion_new                 |         0.1575 |                0.0001853 |                     0.07237 |                            0.06167 |                             0.07685 |        -0.3917 |             8.265 |                    7.405 |                     8.666 |             0.3154 |            0.159   |
| gradient_boosted_trees                         |         0.1624 |               -0.004132  |                     0.07545 |                            0.06604 |                             0.07937 |        -0.3418 |             8.344 |                    7.696 |                     8.733 |             0.3462 |            0.1385  |
| ridge                                          |         0.1695 |               -0.01034   |                     0.06713 |                            0.05628 |                             0.07009 |        -1.051  |            10.34  |                    9.307 |                    11     |             0.3051 |            0.1333  |
| 1d_cnn                                         |         0.215  |                0.04328   |                     0.09909 |                            0.09011 |                             0.106   |        -1.73   |            10.96  |                   10.27  |                    11.31  |             0.2718 |            0.2179  |
| analytic_clipped_template_sideband_traditional |         0.2234 |                0.07918   |                     0.1006  |                            0.09114 |                             0.1148  |         0.535  |             9.454 |                    8.481 |                    10.46  |             0.5846 |            0.1974  |
| tiny_sequence_transformer                      |         0.2713 |                0.0006919 |                     0.1027  |                            0.08737 |                             0.1139  |       -15.75   |            17.75  |                   16.96  |                    19.41  |             0.5949 |            0.06923 |
| mlp                                            |         0.2756 |               -0.02341   |                     0.1571  |                            0.1433  |                             0.1622  |         0.3222 |            11.84  |                   10.46  |                    13.39  |             0.3846 |            0.09231 |

The traditional comparator has energy sigma68 `0.1006`
and score `0.2234`.  The selected winner changes energy
sigma68 by `-0.02826`
and timing sigma68 by `-1.189` ns.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                 0.04972  |                     0.1114  |       -1.322   |            10.72  |             0.2436 |            0.1795  |
| 1d_cnn                                         |            60 |                 0.08083  |                     0.09793 |       -0.06438 |            11.25  |             0.2308 |            0.1538  |
| 1d_cnn                                         |            62 |                 0.06899  |                     0.0883  |       -4.416   |            10.82  |             0.3718 |            0.3205  |
| 1d_cnn                                         |            64 |                 0.01143  |                     0.0807  |       -1.305   |             9.607 |             0.2308 |            0.1923  |
| 1d_cnn                                         |            65 |                 0.02493  |                     0.09159 |       -1.608   |            11.14  |             0.2821 |            0.2436  |
| analytic_clipped_template_sideband_traditional |            58 |                 0.05961  |                     0.09176 |       -0.8261  |             9.586 |             0.5641 |            0.2179  |
| analytic_clipped_template_sideband_traditional |            60 |                 0.1035   |                     0.1049  |        2.624   |             7.291 |             0.6026 |            0.1923  |
| analytic_clipped_template_sideband_traditional |            62 |                 0.08827  |                     0.114   |        0.7759  |            11.39  |             0.5897 |            0.2051  |
| analytic_clipped_template_sideband_traditional |            64 |                 0.06412  |                     0.06839 |        0.5881  |             7.361 |             0.5385 |            0.1282  |
| analytic_clipped_template_sideband_traditional |            65 |                 0.08165  |                     0.0913  |       -1       |             9.479 |             0.6282 |            0.2436  |
| gradient_boosted_trees                         |            58 |                 0.009889 |                     0.0603  |       -0.17    |             8.018 |             0.3077 |            0.1538  |
| gradient_boosted_trees                         |            60 |                -0.001395 |                     0.09047 |        0.1791  |             8.469 |             0.3077 |            0.1795  |
| gradient_boosted_trees                         |            62 |                 0.001927 |                     0.07558 |       -1.382   |             8.476 |             0.3974 |            0.1282  |
| gradient_boosted_trees                         |            64 |                -0.03091  |                     0.06308 |       -0.9632  |             7.645 |             0.3077 |            0.141   |
| gradient_boosted_trees                         |            65 |                -0.002409 |                     0.06708 |       -0.3194  |             8.023 |             0.4103 |            0.08974 |
| mlp                                            |            58 |                -0.04822  |                     0.1362  |        0.1445  |            13.78  |             0.3462 |            0.08974 |
| mlp                                            |            60 |                 0.02265  |                     0.1507  |        1.063   |             9.217 |             0.2564 |            0.1154  |
| mlp                                            |            62 |                -0.02757  |                     0.1489  |        1.786   |            12.26  |             0.4744 |            0.1026  |
| mlp                                            |            64 |                -0.06036  |                     0.1488  |       -0.6515  |            11.06  |             0.3333 |            0.1026  |
| mlp                                            |            65 |                -0.03285  |                     0.1656  |       -1.225   |            14.2   |             0.5128 |            0.05128 |
| ridge                                          |            58 |                -0.00873  |                     0.06969 |       -0.3508  |            10.08  |             0.2821 |            0.1538  |
| ridge                                          |            60 |                 0.01055  |                     0.06889 |        0.6309  |             9.658 |             0.2436 |            0.141   |
| ridge                                          |            62 |                 0.001731 |                     0.06261 |       -3.103   |            11.26  |             0.3718 |            0.141   |
| ridge                                          |            64 |                -0.02938  |                     0.05241 |       -0.7281  |             9.295 |             0.2436 |            0.1026  |
| ridge                                          |            65 |                -0.006805 |                     0.05437 |       -2.533   |             9.576 |             0.3846 |            0.1282  |
| saturation_residual_fusion_new                 |            58 |                 0.005003 |                     0.05948 |       -1.193   |             7.314 |             0.2564 |            0.1795  |
| saturation_residual_fusion_new                 |            60 |                 0.00601  |                     0.07884 |        0.6061  |             8.323 |             0.2436 |            0.141   |
| saturation_residual_fusion_new                 |            62 |                 0.02499  |                     0.07312 |       -2.068   |             8.644 |             0.3718 |            0.1667  |
| saturation_residual_fusion_new                 |            64 |                -0.03392  |                     0.05614 |       -0.7209  |             7.226 |             0.3333 |            0.141   |
| saturation_residual_fusion_new                 |            65 |                -0.008802 |                     0.06522 |        0.5061  |             8.248 |             0.3718 |            0.1667  |
| tiny_sequence_transformer                      |            58 |                -0.007738 |                     0.1248  |      -14.53    |            16.72  |             0.5128 |            0.03846 |
| tiny_sequence_transformer                      |            60 |                 0.02831  |                     0.09785 |      -13.86    |            19.2   |             0.5513 |            0.1026  |
| tiny_sequence_transformer                      |            62 |                -0.003341 |                     0.08162 |      -18.25    |            17.33  |             0.6538 |            0.0641  |
| tiny_sequence_transformer                      |            64 |                -0.009077 |                     0.08412 |      -18       |            19.35  |             0.641  |            0.08974 |
| tiny_sequence_transformer                      |            65 |                -0.008381 |                     0.08886 |      -15.26    |            18.86  |             0.6154 |            0.05128 |

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |                0.06342   |                    0.09024  |      -1.763    |            13.08  |            0.3561  |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |                0.05244   |                    0.1021   |      -0.8723   |             9.836 |            0.3182  |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |                0.04651   |                    0.09528  |      -5.156    |             9.806 |            0.1923  |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |                0.01731   |                    0.09138  |       0.5236   |            10.8   |            0.1739  |
| spacing_bin      | (-0.001, 10.0]    | analytic_clipped_template_sideband_traditional |                0.08873   |                    0.08612  |       1.688    |            13.1   |            0.6742  |
| spacing_bin      | (10.0, 25.0]      | analytic_clipped_template_sideband_traditional |                0.09063   |                    0.09539  |       1.442    |             7.791 |            0.6705  |
| spacing_bin      | (25.0, 45.0]      | analytic_clipped_template_sideband_traditional |                0.07543   |                    0.08609  |      -1.144    |             9.408 |            0.5128  |
| spacing_bin      | (45.0, 70.0]      | analytic_clipped_template_sideband_traditional |                0.04795   |                    0.09505  |      -0.4484   |             9.466 |            0.4348  |
| spacing_bin      | (-0.001, 10.0]    | gradient_boosted_trees                         |                0.01722   |                    0.06208  |      -0.283    |             8.295 |            0.447   |
| spacing_bin      | (10.0, 25.0]      | gradient_boosted_trees                         |                0.01176   |                    0.07598  |       1.142    |             6.956 |            0.4091  |
| spacing_bin      | (25.0, 45.0]      | gradient_boosted_trees                         |               -0.01959   |                    0.07439  |      -1.444    |             8.768 |            0.2308  |
| spacing_bin      | (45.0, 70.0]      | gradient_boosted_trees                         |               -0.02795   |                    0.06069  |       0.1235   |             8.84  |            0.2391  |
| spacing_bin      | (-0.001, 10.0]    | mlp                                            |                0.008273  |                    0.1722   |       0.983    |             9.652 |            0.4167  |
| spacing_bin      | (10.0, 25.0]      | mlp                                            |               -0.006591  |                    0.1398   |       0.6722   |             7.138 |            0.4432  |
| spacing_bin      | (25.0, 45.0]      | mlp                                            |               -0.02356   |                    0.1556   |       0.1706   |            12.28  |            0.3974  |
| spacing_bin      | (45.0, 70.0]      | mlp                                            |               -0.07607   |                    0.1556   |      -0.4112   |            15.49  |            0.2717  |
| spacing_bin      | (-0.001, 10.0]    | ridge                                          |                0.02461   |                    0.05814  |       0.8588   |             9.836 |            0.3636  |
| spacing_bin      | (10.0, 25.0]      | ridge                                          |                0.001731  |                    0.0556   |       0.2933   |             7.308 |            0.3523  |
| spacing_bin      | (25.0, 45.0]      | ridge                                          |               -0.01192   |                    0.05848  |      -3.865    |             9.06  |            0.2949  |
| spacing_bin      | (45.0, 70.0]      | ridge                                          |               -0.0523    |                    0.06381  |      -2.512    |            13.3   |            0.1848  |
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.01957   |                    0.06743  |       0.3599   |             7.58  |            0.4318  |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |                0.02936   |                    0.05116  |       0.4874   |             7.973 |            0.3864  |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |               -0.002028  |                    0.07299  |      -1.756    |             8.335 |            0.2308  |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.03539   |                    0.07118  |      -1.104    |             9.474 |            0.1522  |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |                0.05655   |                    0.06687  |     -12.61     |             9.402 |            0.75    |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |                0.05505   |                    0.05662  |     -16.3      |             8.701 |            0.7386  |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |               -0.01376   |                    0.06152  |     -19.58     |            16.85  |            0.5256  |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.0567    |                    0.08732  |     -18.59     |            22.59  |            0.2935  |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |                0.0321    |                    0.09433  |      -3.144    |            10.69  |            0.4304  |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |                0.04139   |                    0.1045   |      -3.01     |            10.83  |            0.2569  |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |                0.05182   |                    0.09599  |      -1.911    |            10.47  |            0.236   |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |                0.04487   |                    0.08605  |       1.073    |            10.83  |            0.2035  |
| ratio_bin        | (-0.001, 0.35]    | analytic_clipped_template_sideband_traditional |                0.08727   |                    0.1252   |      -0.6984   |            12.48  |            0.5823  |
| ratio_bin        | (0.35, 0.625]     | analytic_clipped_template_sideband_traditional |                0.06821   |                    0.08698  |       0.5489   |            11.25  |            0.6055  |
| ratio_bin        | (0.625, 0.875]    | analytic_clipped_template_sideband_traditional |                0.08259   |                    0.0942   |      -0.5564   |             6.733 |            0.5618  |
| ratio_bin        | (0.875, 1.05]     | analytic_clipped_template_sideband_traditional |                0.06818   |                    0.09752  |       1.575    |             7.71  |            0.5841  |
| ratio_bin        | (-0.001, 0.35]    | gradient_boosted_trees                         |                0.001292  |                    0.07616  |      -3.047    |             8.321 |            0.6076  |
| ratio_bin        | (0.35, 0.625]     | gradient_boosted_trees                         |                0.003397  |                    0.07398  |      -1.444    |             8.92  |            0.3853  |
| ratio_bin        | (0.625, 0.875]    | gradient_boosted_trees                         |               -0.01539   |                    0.06485  |      -0.335    |             6.539 |            0.2809  |
| ratio_bin        | (0.875, 1.05]     | gradient_boosted_trees                         |               -0.006583  |                    0.07375  |       1.089    |             7.539 |            0.177   |
| ratio_bin        | (-0.001, 0.35]    | mlp                                            |               -0.02325   |                    0.1756   |      -2.253    |            11.4   |            0.5823  |
| ratio_bin        | (0.35, 0.625]     | mlp                                            |                0.01772   |                    0.1542   |      -2.18     |            11.51  |            0.4312  |
| ratio_bin        | (0.625, 0.875]    | mlp                                            |               -0.02736   |                    0.1439   |       0.7816   |             9.536 |            0.2809  |
| ratio_bin        | (0.875, 1.05]     | mlp                                            |               -0.04716   |                    0.1478   |       3.479    |            13.46  |            0.2832  |
| ratio_bin        | (-0.001, 0.35]    | ridge                                          |                0.003474  |                    0.07419  |      -4.344    |            11.57  |            0.481   |
| ratio_bin        | (0.35, 0.625]     | ridge                                          |                0.006447  |                    0.06693  |      -2.412    |             9.546 |            0.3486  |
| ratio_bin        | (0.625, 0.875]    | ridge                                          |               -0.01654   |                    0.06095  |       0.4883   |             8.309 |            0.2472  |
| ratio_bin        | (0.875, 1.05]     | ridge                                          |               -0.0178    |                    0.06286  |       1.238    |            10.23  |            0.1858  |
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |               -0.006848  |                    0.0669   |      -3.18     |            11.05  |            0.5443  |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |               -0.001989  |                    0.07931  |      -1.219    |             9.126 |            0.3303  |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.001954  |                    0.06614  |      -1.269    |             6.661 |            0.2472  |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |                0.002006  |                    0.06173  |       1.068    |             6.837 |            0.1947  |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |                0.01343   |                    0.0955   |     -14.89     |            13.68  |            0.6835  |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |                0.02227   |                    0.1048   |     -18.45     |            17.65  |            0.6055  |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |               -0.009782  |                    0.1125   |     -16.47     |            18.29  |            0.618   |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |               -0.01844   |                    0.07959  |     -11.96     |            19.71  |            0.5044  |
| saturation_bin   | 0                 | 1d_cnn                                         |                0.04651   |                    0.09897  |      -1.489    |            10.67  |            0.2782  |
| saturation_bin   | 1-2               | 1d_cnn                                         |               -0.02246   |                    0.09787  |     -10.27     |             4.569 |            0       |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.02276   |                    0.02049  |      -2.077    |            16.07  |            0       |
| saturation_bin   | 0                 | analytic_clipped_template_sideband_traditional |                0.07373   |                    0.1015   |       0.535    |             9.336 |            0.5879  |
| saturation_bin   | 1-2               | analytic_clipped_template_sideband_traditional |                0.081     |                    0.006547 |      -2.4      |            11.42  |            0.5     |
| saturation_bin   | 3-5               | analytic_clipped_template_sideband_traditional |                0.177     |                    0.05639  |       0.3997   |            11.86  |            0.4     |
| saturation_bin   | 0                 | gradient_boosted_trees                         |               -0.004582  |                    0.07551  |      -0.3897   |             8.348 |            0.3543  |
| saturation_bin   | 1-2               | gradient_boosted_trees                         |                0.01893   |                    0.07465  |       0.008277 |             7.752 |            0       |
| saturation_bin   | 3-5               | gradient_boosted_trees                         |               -0.03439   |                    0.06304  |       2.481    |             3.801 |            0       |
| saturation_bin   | 0                 | mlp                                            |               -0.02189   |                    0.1589   |       0.3222   |            11.7   |            0.3937  |
| saturation_bin   | 1-2               | mlp                                            |               -0.05088   |                    0.09073  |       0.8148   |            19.64  |            0       |
| saturation_bin   | 3-5               | mlp                                            |               -0.1059    |                    0.04671  |       0.004916 |            11.6   |            0       |
| saturation_bin   | 0                 | ridge                                          |               -0.009765  |                    0.06717  |      -1.051    |            10.29  |            0.3123  |
| saturation_bin   | 1-2               | ridge                                          |               -0.002575  |                    0.07896  |      -4.294    |             9.566 |            0       |
| saturation_bin   | 3-5               | ridge                                          |               -0.04979   |                    0.01396  |       4.854    |             7.93  |            0       |
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |                0.0004786 |                    0.07307  |      -0.461    |             8.389 |            0.3228  |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |                0.01581   |                    0.08011  |      -1.468    |             9.343 |            0       |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.004629  |                    0.01526  |       0.6905   |             3.437 |            0       |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |                0.004608  |                    0.1016   |     -15.75     |            17.93  |            0.6063  |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |               -0.03803   |                    0.09451  |     -20.55     |            11.93  |            0       |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.1398    |                    0.02932  |      -8.485    |             8.047 |            0.2     |
| pedestal_state   | nominal           | 1d_cnn                                         |                0.02938   |                    0.08081  |      -0.5036   |             9.701 |            0.2074  |
| pedestal_state   | shifted           | 1d_cnn                                         |                0.04972   |                    0.1084   |      -2.586    |            11.18  |            0.3059  |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |                0.06821   |                    0.1036   |       0.717    |             6.859 |            0.4296  |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |                0.08124   |                    0.09584  |      -0.323    |            12.33  |            0.6667  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.006085  |                    0.05983  |       0.5168   |             7.438 |            0.3333  |
| pedestal_state   | shifted           | gradient_boosted_trees                         |               -0.001954  |                    0.081    |      -1.008    |             8.257 |            0.3529  |
| pedestal_state   | nominal           | mlp                                            |               -0.07348   |                    0.1306   |       2.354    |            10.37  |            0.3481  |
| pedestal_state   | shifted           | mlp                                            |                0.008483  |                    0.1733   |      -0.9066   |            12.76  |            0.4039  |
| pedestal_state   | nominal           | ridge                                          |               -0.01825   |                    0.04632  |       0.5808   |             9.145 |            0.2815  |
| pedestal_state   | shifted           | ridge                                          |               -0.001909  |                    0.07223  |      -2.307    |            10.8   |            0.3176  |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |                0.002006  |                    0.06078  |       0.4511   |             7.019 |            0.3111  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |               -0.001014  |                    0.07801  |      -1.206    |             8.62  |            0.3176  |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |               -0.02244   |                    0.08921  |     -15.61     |            19.22  |            0.5111  |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |                0.01552   |                    0.1034   |     -15.79     |            16.55  |            0.6392  |
| morphology_state | late_tail_high    | 1d_cnn                                         |                0.05327   |                    0.08657  |      -3.33     |            10.71  |            0.3295  |
| morphology_state | late_tail_low     | 1d_cnn                                         |                0.0307    |                    0.1029   |      -0.9032   |            11.11  |            0.2258  |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |                0.1233    |                    0.101    |       0.6337   |             7.427 |            0.6936  |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |                0.06126   |                    0.08171  |       0.2364   |            10.51  |            0.4977  |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |                0.004143  |                    0.06121  |      -0.2606   |             7.632 |            0.3931  |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |               -0.009563  |                    0.07873  |      -0.4127   |             8.641 |            0.3088  |
| morphology_state | late_tail_high    | mlp                                            |               -0.03303   |                    0.1331   |       0.472    |             8.738 |            0.4277  |
| morphology_state | late_tail_low     | mlp                                            |               -0.02084   |                    0.1771   |       0.05644  |            14.88  |            0.3502  |
| morphology_state | late_tail_high    | ridge                                          |               -0.008094  |                    0.06133  |       0.3451   |             8.467 |            0.3584  |
| morphology_state | late_tail_low     | ridge                                          |               -0.01095   |                    0.07013  |      -2.136    |            11.4   |            0.2627  |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |                0.01477   |                    0.06087  |      -0.02672  |             7.299 |            0.3873  |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.008802  |                    0.07475  |      -0.7949   |             8.747 |            0.2581  |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |                0.02674   |                    0.07685  |     -19.02     |            14.75  |            0.711   |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |               -0.01404   |                    0.1094   |     -13.35     |            18.36  |            0.5023  |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.03082   |                    0.06109  |      -7.231    |            11.42  |            0.2917  |
| pid_proxy_class  | other             | 1d_cnn                                         |                0.04761   |                    0.09648  |      -1.425    |            10.81  |            0.2705  |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |                0.07949   |                    0.06167  |       3.535    |            12.8   |            0.5417  |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |                0.07887   |                    0.1034   |       0.3318   |             8.975 |            0.5874  |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.04609   |                    0.08259  |      -3.899    |             8.573 |            0.1667  |
| pid_proxy_class  | other             | gradient_boosted_trees                         |               -0.001554  |                    0.0751   |      -0.2337   |             8.063 |            0.3579  |
| pid_proxy_class  | inner_high_charge | mlp                                            |               -0.08423   |                    0.07343  |      -0.8013   |            15.14  |            0.08333 |
| pid_proxy_class  | other             | mlp                                            |               -0.009771  |                    0.1605   |       0.4354   |            11.48  |            0.4044  |
| pid_proxy_class  | inner_high_charge | ridge                                          |               -0.04979   |                    0.05878  |      -5.357    |            11.57  |            0.04167 |
| pid_proxy_class  | other             | ridge                                          |               -0.007556  |                    0.06558  |      -0.6305   |             9.802 |            0.3224  |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |               -0.01288   |                    0.08018  |      -3.885    |            10.07  |            0.125   |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |                0.003591  |                    0.07309  |      -0.06328  |             8.102 |            0.3279  |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |               -0.06351   |                    0.07445  |     -16.43     |            17.47  |            0.2917  |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |                0.01115   |                    0.1023   |     -15.59     |            17.81  |            0.6148  |
| stave            | B2                | 1d_cnn                                         |               -0.04632   |                    0.1008   |      -6.837    |            12.13  |            0.4615  |
| stave            | B4                | 1d_cnn                                         |                0.09225   |                    0.08416  |      -5.342    |            10.07  |            0.2897  |
| stave            | B6                | 1d_cnn                                         |                0.03785   |                    0.08849  |      -0.6152   |             8.669 |            0.2471  |
| stave            | B8                | 1d_cnn                                         |                0.04213   |                    0.0729   |       2.161    |             8.707 |            0.1121  |
| stave            | B2                | analytic_clipped_template_sideband_traditional |                0.08789   |                    0.04241  |       1.674    |            14.88  |            0.6703  |
| stave            | B4                | analytic_clipped_template_sideband_traditional |               -0.002864  |                    0.06753  |       5.192    |            13.46  |            0.8318  |
| stave            | B6                | analytic_clipped_template_sideband_traditional |                0.0181    |                    0.09161  |      -0.4484   |            10.34  |            0.5765  |
| stave            | B8                | analytic_clipped_template_sideband_traditional |                0.1051    |                    0.1055   |       0.5541   |             5.485 |            0.271   |
| stave            | B2                | gradient_boosted_trees                         |               -0.05352   |                    0.0747   |      -7.011    |             8.877 |            0.4286  |
| stave            | B4                | gradient_boosted_trees                         |                0.01398   |                    0.05586  |      -2.323    |             7.62  |            0.3084  |
| stave            | B6                | gradient_boosted_trees                         |                0.0005526 |                    0.06588  |       0.9608   |             4.827 |            0.4     |
| stave            | B8                | gradient_boosted_trees                         |               -0.01296   |                    0.06637  |       2.418    |             6.264 |            0.271   |
| stave            | B2                | mlp                                            |               -0.07639   |                    0.106    |      -2.74     |            16.69  |            0.4725  |
| stave            | B4                | mlp                                            |                0.07005   |                    0.1623   |      -1.442    |            10.82  |            0.3832  |
| stave            | B6                | mlp                                            |                0.001011  |                    0.1458   |      -0.9914   |            11.28  |            0.4     |
| stave            | B8                | mlp                                            |               -0.0524    |                    0.134    |       3.774    |             9.253 |            0.2991  |
| stave            | B2                | ridge                                          |               -0.02661   |                    0.07867  |      -7.614    |            11.93  |            0.3407  |
| stave            | B4                | ridge                                          |                0.01905   |                    0.07085  |      -3.677    |             8.73  |            0.3271  |
| stave            | B6                | ridge                                          |               -0.01034   |                    0.05717  |       0.2165   |             7.772 |            0.3529  |
| stave            | B8                | ridge                                          |               -0.01622   |                    0.06035  |       3.231    |             7.464 |            0.215   |
| stave            | B2                | saturation_residual_fusion_new                 |               -0.03885   |                    0.07792  |      -6.906    |             9.425 |            0.3516  |
| stave            | B4                | saturation_residual_fusion_new                 |                0.031     |                    0.06632  |      -2.006    |             7.922 |            0.2991  |
| stave            | B6                | saturation_residual_fusion_new                 |               -0.003275  |                    0.07618  |       1.148    |             5.773 |            0.3412  |
| stave            | B8                | saturation_residual_fusion_new                 |                0.004122  |                    0.04821  |       1.834    |             5.936 |            0.2804  |
| stave            | B2                | tiny_sequence_transformer                      |               -0.04693   |                    0.07852  |     -18.16     |            19.89  |            0.7363  |
| stave            | B4                | tiny_sequence_transformer                      |                0.02227   |                    0.1156   |     -16.26     |            19.69  |            0.6355  |
| stave            | B6                | tiny_sequence_transformer                      |               -0.02059   |                    0.1035   |     -15.94     |            18.8   |            0.5529  |
| stave            | B8                | tiny_sequence_transformer                      |                0.01309   |                    0.1031   |     -14.41     |            14.57  |            0.4673  |

Systematic caveats are material.  First, pile-up truth is from controlled
overlays into raw-ROOT-derived residuals; it validates reconstruction under known
truth but not the true beam pile-up rate.  Second, the ADC clipping level is a
benchmark stressor rather than a decoded electronics flag.  Third, only 18
samples are available, so pedestal memory and late recovery tails can be partly
degenerate with broad second pulses.  Fourth, the bootstrap unit is the held-out
run, giving run-transfer intervals rather than event-counting intervals.  Fifth,
the PID class is a waveform/support proxy, not an external particle label.

## Recommendation

Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay energy-closure method
when the analysis goal is saturated doublet recovery with run-held-out
uncertainty propagation.  The analytic clipped-template method remains the
auditable fallback when deterministic extrapolation is more important than the
observed held-out score gain.

Runtime was `58.5` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

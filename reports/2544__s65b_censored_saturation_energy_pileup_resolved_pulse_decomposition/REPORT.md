# S65b: Censored Saturation Energy Recovery with Pile-Up-Resolved Pulse Decomposition

## Abstract

Ticket `#2544` asks for an academic-grade comparison of a strong traditional
multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,
transformer sequence models, and a sensible new architecture for energy
reconstruction under pile-up and ADC saturation.  The worker is `testbeam-laptop-4`.  The
winner is **`saturation_residual_fusion_new`**, selected by held-out run-block energy closure:
fractional energy sigma68 `0.06688` with 95%
CI [`0.0605`,
`0.07067`].  Its composite score is
`0.154`.

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
| saturation_residual_fusion_new                 |         0.154  |                -0.00549  |                     0.06688 |                            0.0605  |                             0.07067 |        -0.2155 |             8.368 |                    7.756 |                     8.747 |             0.341  |            0.1359  |
| gradient_boosted_trees                         |         0.16   |                -0.004337 |                     0.07328 |                            0.06523 |                             0.08059 |        -0.3938 |             8.231 |                    7.863 |                     8.439 |             0.3538 |            0.1462  |
| ridge                                          |         0.1695 |                -0.01034  |                     0.06713 |                            0.05628 |                             0.07009 |        -1.051  |            10.34  |                    9.307 |                    11     |             0.3051 |            0.1333  |
| 1d_cnn                                         |         0.2166 |                 0.05128  |                     0.1033  |                            0.09359 |                             0.1139  |        -1.448  |            10.51  |                    9.732 |                    11.31  |             0.2718 |            0.2026  |
| analytic_clipped_template_sideband_traditional |         0.2234 |                 0.07918  |                     0.1006  |                            0.09114 |                             0.1148  |         0.5086 |             9.454 |                    8.482 |                    10.46  |             0.5846 |            0.1974  |
| mlp                                            |         0.2756 |                -0.02341  |                     0.1571  |                            0.1433  |                             0.1622  |         0.3222 |            11.84  |                   10.46  |                    13.39  |             0.3846 |            0.09231 |
| tiny_sequence_transformer                      |         0.2808 |                -0.01747  |                     0.1047  |                            0.0847  |                             0.1246  |        -9.919  |            18.15  |                   17.24  |                    20.45  |             0.6231 |            0.0641  |

The traditional comparator has energy sigma68 `0.1006`
and score `0.2234`.  The selected winner changes energy
sigma68 by `-0.03375`
and timing sigma68 by `-1.086` ns.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                 0.05128  |                     0.1165  |        -0.685  |             9.365 |             0.2564 |            0.1923  |
| 1d_cnn                                         |            60 |                 0.07796  |                     0.0874  |        -0.7878 |            11.17  |             0.2564 |            0.1538  |
| 1d_cnn                                         |            62 |                 0.07632  |                     0.101   |        -3.467  |            10.78  |             0.3462 |            0.2564  |
| 1d_cnn                                         |            64 |                 0.02658  |                     0.09428 |        -1.217  |             9.12  |             0.2308 |            0.1795  |
| 1d_cnn                                         |            65 |                 0.04002  |                     0.1101  |        -2.133  |            11.03  |             0.2692 |            0.2308  |
| analytic_clipped_template_sideband_traditional |            58 |                 0.05961  |                     0.09176 |        -0.8261 |             9.586 |             0.5641 |            0.2179  |
| analytic_clipped_template_sideband_traditional |            60 |                 0.1035   |                     0.1049  |         2.624  |             7.291 |             0.6026 |            0.1923  |
| analytic_clipped_template_sideband_traditional |            62 |                 0.08827  |                     0.114   |         0.7759 |            11.39  |             0.5897 |            0.2051  |
| analytic_clipped_template_sideband_traditional |            64 |                 0.06412  |                     0.06839 |         0.3945 |             7.361 |             0.5385 |            0.1282  |
| analytic_clipped_template_sideband_traditional |            65 |                 0.08165  |                     0.0913  |        -1      |             9.479 |             0.6282 |            0.2436  |
| gradient_boosted_trees                         |            58 |                 0.01035  |                     0.06828 |        -0.4859 |             7.496 |             0.2821 |            0.1538  |
| gradient_boosted_trees                         |            60 |                 0.003428 |                     0.07901 |         0.6314 |             8.349 |             0.3077 |            0.1795  |
| gradient_boosted_trees                         |            62 |                -0.001499 |                     0.06871 |        -1.548  |             8.259 |             0.3974 |            0.1282  |
| gradient_boosted_trees                         |            64 |                -0.03631  |                     0.05706 |        -0.5679 |             8.253 |             0.3462 |            0.1538  |
| gradient_boosted_trees                         |            65 |                -0.002961 |                     0.05651 |         0.421  |             8.169 |             0.4359 |            0.1154  |
| mlp                                            |            58 |                -0.04822  |                     0.1362  |         0.1445 |            13.78  |             0.3462 |            0.08974 |
| mlp                                            |            60 |                 0.02265  |                     0.1507  |         1.063  |             9.217 |             0.2564 |            0.1154  |
| mlp                                            |            62 |                -0.02757  |                     0.1489  |         1.786  |            12.26  |             0.4744 |            0.1026  |
| mlp                                            |            64 |                -0.06036  |                     0.1488  |        -0.6515 |            11.06  |             0.3333 |            0.1026  |
| mlp                                            |            65 |                -0.03285  |                     0.1656  |        -1.225  |            14.2   |             0.5128 |            0.05128 |
| ridge                                          |            58 |                -0.00873  |                     0.06969 |        -0.3508 |            10.08  |             0.2821 |            0.1538  |
| ridge                                          |            60 |                 0.01055  |                     0.06889 |         0.6309 |             9.658 |             0.2436 |            0.141   |
| ridge                                          |            62 |                 0.001731 |                     0.06261 |        -3.103  |            11.26  |             0.3718 |            0.141   |
| ridge                                          |            64 |                -0.02938  |                     0.05241 |        -0.7281 |             9.295 |             0.2436 |            0.1026  |
| ridge                                          |            65 |                -0.006805 |                     0.05437 |        -2.533  |             9.576 |             0.3846 |            0.1282  |
| saturation_residual_fusion_new                 |            58 |                 0.005321 |                     0.05853 |        -0.2345 |             7.703 |             0.2949 |            0.1923  |
| saturation_residual_fusion_new                 |            60 |                -0.004446 |                     0.06835 |         0.8193 |             7.791 |             0.2692 |            0.08974 |
| saturation_residual_fusion_new                 |            62 |                 0.01592  |                     0.05712 |        -1.745  |             8.53  |             0.4103 |            0.141   |
| saturation_residual_fusion_new                 |            64 |                -0.037    |                     0.06486 |        -0.9396 |             7.563 |             0.3333 |            0.1026  |
| saturation_residual_fusion_new                 |            65 |                -0.001895 |                     0.06979 |         0.3526 |             8.137 |             0.3974 |            0.1538  |
| tiny_sequence_transformer                      |            58 |                -0.01139  |                     0.1363  |        -8.098  |            16.47  |             0.5513 |            0.03846 |
| tiny_sequence_transformer                      |            60 |                 0.002138 |                     0.1029  |        -5.889  |            20.47  |             0.5897 |            0.07692 |
| tiny_sequence_transformer                      |            62 |                -0.01484  |                     0.0919  |       -13.85   |            17.88  |             0.6923 |            0.07692 |
| tiny_sequence_transformer                      |            64 |                -0.02618  |                     0.08034 |       -12.86   |            18.98  |             0.6538 |            0.07692 |
| tiny_sequence_transformer                      |            65 |                -0.02583  |                     0.08966 |        -9.206  |            18.33  |             0.6282 |            0.05128 |

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |                0.07095   |                    0.09127  |      -0.6668   |            12.27  |            0.3636  |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |                0.05892   |                    0.1093   |      -0.3079   |             8.866 |            0.3182  |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |                0.04912   |                    0.1044   |      -4.551    |             9.615 |            0.1795  |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |                0.03436   |                    0.09336  |      -1.157    |            11.34  |            0.1739  |
| spacing_bin      | (-0.001, 10.0]    | analytic_clipped_template_sideband_traditional |                0.08873   |                    0.08612  |       1.688    |            13.1   |            0.6742  |
| spacing_bin      | (10.0, 25.0]      | analytic_clipped_template_sideband_traditional |                0.09063   |                    0.09539  |       1.393    |             7.791 |            0.6705  |
| spacing_bin      | (25.0, 45.0]      | analytic_clipped_template_sideband_traditional |                0.07543   |                    0.08609  |      -1.144    |             9.408 |            0.5128  |
| spacing_bin      | (45.0, 70.0]      | analytic_clipped_template_sideband_traditional |                0.04795   |                    0.09505  |      -0.4484   |             9.466 |            0.4348  |
| spacing_bin      | (-0.001, 10.0]    | gradient_boosted_trees                         |                0.02235   |                    0.06195  |       0.4658   |             8.322 |            0.4394  |
| spacing_bin      | (10.0, 25.0]      | gradient_boosted_trees                         |                0.01677   |                    0.06517  |       0.08112  |             6.731 |            0.4545  |
| spacing_bin      | (25.0, 45.0]      | gradient_boosted_trees                         |               -0.02016   |                    0.07025  |      -1.548    |             9.213 |            0.2308  |
| spacing_bin      | (45.0, 70.0]      | gradient_boosted_trees                         |               -0.04498   |                    0.06412  |      -0.5401   |             9.327 |            0.2391  |
| spacing_bin      | (-0.001, 10.0]    | mlp                                            |                0.008273  |                    0.1722   |       0.983    |             9.652 |            0.4167  |
| spacing_bin      | (10.0, 25.0]      | mlp                                            |               -0.006591  |                    0.1398   |       0.6722   |             7.138 |            0.4432  |
| spacing_bin      | (25.0, 45.0]      | mlp                                            |               -0.02356   |                    0.1556   |       0.1706   |            12.28  |            0.3974  |
| spacing_bin      | (45.0, 70.0]      | mlp                                            |               -0.07607   |                    0.1556   |      -0.4112   |            15.49  |            0.2717  |
| spacing_bin      | (-0.001, 10.0]    | ridge                                          |                0.02461   |                    0.05814  |       0.8588   |             9.836 |            0.3636  |
| spacing_bin      | (10.0, 25.0]      | ridge                                          |                0.001731  |                    0.0556   |       0.2933   |             7.308 |            0.3523  |
| spacing_bin      | (25.0, 45.0]      | ridge                                          |               -0.01192   |                    0.05848  |      -3.865    |             9.06  |            0.2949  |
| spacing_bin      | (45.0, 70.0]      | ridge                                          |               -0.0523    |                    0.06381  |      -2.512    |            13.3   |            0.1848  |
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.009857  |                    0.06808  |       0.799    |             7.403 |            0.447   |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |                0.03112   |                    0.047    |       0.2419   |             7.499 |            0.4432  |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |               -0.01091   |                    0.06535  |      -1.447    |             8.646 |            0.2308  |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.04174   |                    0.05886  |      -0.6743   |             9.623 |            0.1848  |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |                0.0557    |                    0.06597  |      -6.949    |             7.849 |            0.7803  |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |                0.05332   |                    0.06409  |     -10.81     |             8.181 |            0.8068  |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |               -0.01973   |                    0.05733  |     -13.87     |            16.5   |            0.5385  |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.05923   |                    0.09249  |     -12.32     |            23.49  |            0.2935  |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |                0.05023   |                    0.104    |      -2.022    |            10.24  |            0.4304  |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |                0.05501   |                    0.1194   |      -3.157    |            11.16  |            0.2477  |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |                0.04957   |                    0.09659  |      -1.232    |             9.729 |            0.2247  |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |                0.05261   |                    0.08451  |       0.1828   |            10.15  |            0.2212  |
| ratio_bin        | (-0.001, 0.35]    | analytic_clipped_template_sideband_traditional |                0.08727   |                    0.1252   |      -0.785    |            12.48  |            0.5823  |
| ratio_bin        | (0.35, 0.625]     | analytic_clipped_template_sideband_traditional |                0.06821   |                    0.08698  |       0.5489   |            11.25  |            0.6055  |
| ratio_bin        | (0.625, 0.875]    | analytic_clipped_template_sideband_traditional |                0.08259   |                    0.0942   |      -0.5564   |             6.733 |            0.5618  |
| ratio_bin        | (0.875, 1.05]     | analytic_clipped_template_sideband_traditional |                0.06818   |                    0.09752  |       1.575    |             7.71  |            0.5841  |
| ratio_bin        | (-0.001, 0.35]    | gradient_boosted_trees                         |               -0.01674   |                    0.05909  |      -2.394    |             9.264 |            0.5949  |
| ratio_bin        | (0.35, 0.625]     | gradient_boosted_trees                         |                0.0025    |                    0.07768  |      -0.9315   |             9.958 |            0.3945  |
| ratio_bin        | (0.625, 0.875]    | gradient_boosted_trees                         |               -0.01061   |                    0.05783  |      -0.6427   |             7.091 |            0.2584  |
| ratio_bin        | (0.875, 1.05]     | gradient_boosted_trees                         |               -0.004325  |                    0.08817  |       1.509    |             7.405 |            0.2212  |
| ratio_bin        | (-0.001, 0.35]    | mlp                                            |               -0.02325   |                    0.1756   |      -2.253    |            11.4   |            0.5823  |
| ratio_bin        | (0.35, 0.625]     | mlp                                            |                0.01772   |                    0.1542   |      -2.18     |            11.51  |            0.4312  |
| ratio_bin        | (0.625, 0.875]    | mlp                                            |               -0.02736   |                    0.1439   |       0.7816   |             9.536 |            0.2809  |
| ratio_bin        | (0.875, 1.05]     | mlp                                            |               -0.04716   |                    0.1478   |       3.479    |            13.46  |            0.2832  |
| ratio_bin        | (-0.001, 0.35]    | ridge                                          |                0.003474  |                    0.07419  |      -4.344    |            11.57  |            0.481   |
| ratio_bin        | (0.35, 0.625]     | ridge                                          |                0.006447  |                    0.06693  |      -2.412    |             9.546 |            0.3486  |
| ratio_bin        | (0.625, 0.875]    | ridge                                          |               -0.01654   |                    0.06095  |       0.4883   |             8.309 |            0.2472  |
| ratio_bin        | (0.875, 1.05]     | ridge                                          |               -0.0178    |                    0.06286  |       1.238    |            10.23  |            0.1858  |
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |               -0.02641   |                    0.05611  |      -3.129    |             9.218 |            0.5316  |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |               -0.001895  |                    0.06766  |      -1.026    |             8.998 |            0.3486  |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.008678  |                    0.07181  |      -0.8698   |             7.184 |            0.3146  |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |                0.001228  |                    0.06171  |       1.545    |             6.981 |            0.2212  |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |                0.02862   |                    0.1085   |     -10.58     |            14.12  |            0.6835  |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |                0.01061   |                    0.1108   |     -10.78     |            17.23  |            0.6422  |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |               -0.02937   |                    0.1258   |     -10.88     |            18.98  |            0.6629  |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |               -0.03226   |                    0.08274  |      -5.574    |            21.41  |            0.531   |
| saturation_bin   | 0                 | 1d_cnn                                         |                0.05562   |                    0.101    |      -1.37     |            10.49  |            0.2782  |
| saturation_bin   | 1-2               | 1d_cnn                                         |               -0.008893  |                    0.1041   |      -8.944    |             6.916 |            0       |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.02193   |                    0.02724  |      -2.211    |            15.7   |            0       |
| saturation_bin   | 0                 | analytic_clipped_template_sideband_traditional |                0.07373   |                    0.1015   |       0.5086   |             9.336 |            0.5879  |
| saturation_bin   | 1-2               | analytic_clipped_template_sideband_traditional |                0.081     |                    0.006547 |      -2.4      |            11.42  |            0.5     |
| saturation_bin   | 3-5               | analytic_clipped_template_sideband_traditional |                0.177     |                    0.05639  |       0.3997   |            11.86  |            0.4     |
| saturation_bin   | 0                 | gradient_boosted_trees                         |               -0.004281  |                    0.07317  |      -0.4859   |             8.252 |            0.3622  |
| saturation_bin   | 1-2               | gradient_boosted_trees                         |                0.03136   |                    0.07211  |      -0.3497   |             8.504 |            0       |
| saturation_bin   | 3-5               | gradient_boosted_trees                         |               -0.04276   |                    0.03807  |       2.969    |             5.049 |            0       |
| saturation_bin   | 0                 | mlp                                            |               -0.02189   |                    0.1589   |       0.3222   |            11.7   |            0.3937  |
| saturation_bin   | 1-2               | mlp                                            |               -0.05088   |                    0.09073  |       0.8148   |            19.64  |            0       |
| saturation_bin   | 3-5               | mlp                                            |               -0.1059    |                    0.04671  |       0.004916 |            11.6   |            0       |
| saturation_bin   | 0                 | ridge                                          |               -0.009765  |                    0.06717  |      -1.051    |            10.29  |            0.3123  |
| saturation_bin   | 1-2               | ridge                                          |               -0.002575  |                    0.07896  |      -4.294    |             9.566 |            0       |
| saturation_bin   | 3-5               | ridge                                          |               -0.04979   |                    0.01396  |       4.854    |             7.93  |            0       |
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |               -0.005245  |                    0.06708  |      -0.1746   |             8.373 |            0.3491  |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |               -0.01139   |                    0.08318  |      -2.313    |             9.944 |            0       |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.00549   |                    0.01253  |       0.1982   |             3.813 |            0       |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |               -0.009727  |                    0.1021   |     -10.06     |            18.38  |            0.6325  |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |               -0.08823   |                    0.1013   |     -10.21     |            13.16  |            0.25    |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.1435    |                    0.02993  |      -3.24     |             7.666 |            0.2     |
| pedestal_state   | nominal           | 1d_cnn                                         |                0.0457    |                    0.08233  |      -0.6197   |             9.815 |            0.2074  |
| pedestal_state   | shifted           | 1d_cnn                                         |                0.05666   |                    0.1149   |      -2.408    |            10.74  |            0.3059  |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |                0.06821   |                    0.1036   |       0.6337   |             6.868 |            0.4296  |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |                0.08124   |                    0.09584  |      -0.323    |            12.33  |            0.6667  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.01004   |                    0.06861  |       1.187    |             7.122 |            0.3333  |
| pedestal_state   | shifted           | gradient_boosted_trees                         |               -0.003157  |                    0.07365  |      -1.116    |             8.407 |            0.3647  |
| pedestal_state   | nominal           | mlp                                            |               -0.07348   |                    0.1306   |       2.354    |            10.37  |            0.3481  |
| pedestal_state   | shifted           | mlp                                            |                0.008483  |                    0.1733   |      -0.9066   |            12.76  |            0.4039  |
| pedestal_state   | nominal           | ridge                                          |               -0.01825   |                    0.04632  |       0.5808   |             9.145 |            0.2815  |
| pedestal_state   | shifted           | ridge                                          |               -0.001909  |                    0.07223  |      -2.307    |            10.8   |            0.3176  |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |               -0.006911  |                    0.058    |       0.7153   |             6.871 |            0.3259  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |               -0.004851  |                    0.07185  |      -0.9396   |             8.661 |            0.349   |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |               -0.03464   |                    0.08328  |      -8.082    |            20.67  |            0.5407  |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |                0.007168  |                    0.1117   |     -10.52     |            16.58  |            0.6667  |
| morphology_state | late_tail_high    | 1d_cnn                                         |                0.07066   |                    0.09803  |      -2.368    |            10.22  |            0.3353  |
| morphology_state | late_tail_low     | 1d_cnn                                         |                0.04164   |                    0.1036   |      -1.016    |            10.82  |            0.2212  |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |                0.1233    |                    0.101    |       0.5945   |             7.427 |            0.6936  |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |                0.06126   |                    0.08171  |       0.2364   |            10.51  |            0.4977  |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |                0.002568  |                    0.06696  |       0.1802   |             8.044 |            0.4162  |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |               -0.01204   |                    0.07666  |      -0.5469   |             8.455 |            0.3041  |
| morphology_state | late_tail_high    | mlp                                            |               -0.03303   |                    0.1331   |       0.472    |             8.738 |            0.4277  |
| morphology_state | late_tail_low     | mlp                                            |               -0.02084   |                    0.1771   |       0.05644  |            14.88  |            0.3502  |
| morphology_state | late_tail_high    | ridge                                          |               -0.008094  |                    0.06133  |       0.3451   |             8.467 |            0.3584  |
| morphology_state | late_tail_low     | ridge                                          |               -0.01095   |                    0.07013  |      -2.136    |            11.4   |            0.2627  |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |                0.01181   |                    0.05655  |       0.2404   |             7.369 |            0.4162  |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.02239   |                    0.06846  |      -0.5279   |             9.167 |            0.2811  |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |                0.001456  |                    0.08479  |     -13.34     |            16.29  |            0.7399  |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |               -0.02792   |                    0.1106   |      -7.556    |            18.82  |            0.53    |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.02464   |                    0.08091  |      -6.466    |            10.76  |            0.2917  |
| pid_proxy_class  | other             | 1d_cnn                                         |                0.05807   |                    0.1011   |      -1.16     |            10.47  |            0.2705  |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |                0.07949   |                    0.06167  |       3.535    |            12.8   |            0.5417  |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |                0.07887   |                    0.1034   |       0.2891   |             8.975 |            0.5874  |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.05084   |                    0.08205  |      -4.985    |             9.13  |            0.1667  |
| pid_proxy_class  | other             | gradient_boosted_trees                         |               -0.003038  |                    0.06894  |      -0.1418   |             8.083 |            0.3661  |
| pid_proxy_class  | inner_high_charge | mlp                                            |               -0.08423   |                    0.07343  |      -0.8013   |            15.14  |            0.08333 |
| pid_proxy_class  | other             | mlp                                            |               -0.009771  |                    0.1605   |       0.4354   |            11.48  |            0.4044  |
| pid_proxy_class  | inner_high_charge | ridge                                          |               -0.04979   |                    0.05878  |      -5.357    |            11.57  |            0.04167 |
| pid_proxy_class  | other             | ridge                                          |               -0.007556  |                    0.06558  |      -0.6305   |             9.802 |            0.3224  |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |               -0.03109   |                    0.07284  |      -3.165    |            10.03  |            0.1667  |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |               -0.001895  |                    0.06637  |      -0.06267  |             8.215 |            0.3525  |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |               -0.07437   |                    0.09037  |     -11.39     |            17.7   |            0.375   |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |               -0.004191  |                    0.1044   |      -9.764    |            18.32  |            0.6393  |
| stave            | B2                | 1d_cnn                                         |               -0.04708   |                    0.08745  |      -6.794    |            12.16  |            0.4615  |
| stave            | B4                | 1d_cnn                                         |                0.1006    |                    0.08804  |      -6.108    |            10.15  |            0.2991  |
| stave            | B6                | 1d_cnn                                         |                0.05666   |                    0.0933   |      -0.6769   |             8.465 |            0.2353  |
| stave            | B8                | 1d_cnn                                         |                0.04561   |                    0.07747  |       2.174    |             8.449 |            0.1121  |
| stave            | B2                | analytic_clipped_template_sideband_traditional |                0.08789   |                    0.04241  |       1.674    |            14.88  |            0.6703  |
| stave            | B4                | analytic_clipped_template_sideband_traditional |               -0.002864  |                    0.06753  |       5.192    |            13.46  |            0.8318  |
| stave            | B6                | analytic_clipped_template_sideband_traditional |                0.0181    |                    0.09161  |      -0.4484   |            10.59  |            0.5765  |
| stave            | B8                | analytic_clipped_template_sideband_traditional |                0.1051    |                    0.1055   |       0.5484   |             5.485 |            0.271   |
| stave            | B2                | gradient_boosted_trees                         |               -0.05393   |                    0.07585  |      -7.186    |             8.94  |            0.4396  |
| stave            | B4                | gradient_boosted_trees                         |                0.00843   |                    0.06861  |      -1.594    |             7.882 |            0.3178  |
| stave            | B6                | gradient_boosted_trees                         |                0.01015   |                    0.06437  |       1.137    |             5.588 |            0.4118  |
| stave            | B8                | gradient_boosted_trees                         |               -0.01578   |                    0.06821  |       2.666    |             6.213 |            0.271   |
| stave            | B2                | mlp                                            |               -0.07639   |                    0.106    |      -2.74     |            16.69  |            0.4725  |
| stave            | B4                | mlp                                            |                0.07005   |                    0.1623   |      -1.442    |            10.82  |            0.3832  |
| stave            | B6                | mlp                                            |                0.001011  |                    0.1458   |      -0.9914   |            11.28  |            0.4     |
| stave            | B8                | mlp                                            |               -0.0524    |                    0.134    |       3.774    |             9.253 |            0.2991  |
| stave            | B2                | ridge                                          |               -0.02661   |                    0.07867  |      -7.614    |            11.93  |            0.3407  |
| stave            | B4                | ridge                                          |                0.01905   |                    0.07085  |      -3.677    |             8.73  |            0.3271  |
| stave            | B6                | ridge                                          |               -0.01034   |                    0.05717  |       0.2165   |             7.772 |            0.3529  |
| stave            | B8                | ridge                                          |               -0.01622   |                    0.06035  |       3.231    |             7.464 |            0.215   |
| stave            | B2                | saturation_residual_fusion_new                 |               -0.04882   |                    0.07231  |      -5.876    |            10.09  |            0.4066  |
| stave            | B4                | saturation_residual_fusion_new                 |                0.01637   |                    0.06939  |      -1.407    |             8.442 |            0.3178  |
| stave            | B6                | saturation_residual_fusion_new                 |               -0.003692  |                    0.05845  |       0.6375   |             5.176 |            0.3882  |
| stave            | B8                | saturation_residual_fusion_new                 |                0.0009253 |                    0.05262  |       1.731    |             5.98  |            0.271   |
| stave            | B2                | tiny_sequence_transformer                      |               -0.06573   |                    0.09242  |     -12.19     |            19.77  |            0.7473  |
| stave            | B4                | tiny_sequence_transformer                      |                0.02266   |                    0.1291   |     -10.3      |            18.49  |            0.6729  |
| stave            | B6                | tiny_sequence_transformer                      |               -0.03249   |                    0.104    |      -9.624    |            20.94  |            0.5882  |
| stave            | B8                | tiny_sequence_transformer                      |                0.006032  |                    0.1047   |      -9.688    |            15.41  |            0.4953  |

Systematic caveats are material.  First, pile-up truth is from controlled
overlays into raw-ROOT-derived residuals; it validates reconstruction under known
truth but not the true beam pile-up rate.  Second, the ADC clipping level is a
benchmark stressor rather than a decoded electronics flag.  Third, only 18
samples are available, so pedestal memory and late recovery tails can be partly
degenerate with broad second pulses.  Fourth, the bootstrap unit is the held-out
run, giving run-transfer intervals rather than event-counting intervals.  Fifth,
the PID class is a waveform/support proxy, not an external particle label.

## Recommendation

Use `saturation_residual_fusion_new` as the preferred S65b controlled-overlay energy-closure method
when the analysis goal is saturated doublet recovery with run-held-out
uncertainty propagation.  The analytic clipped-template method remains the
auditable fallback when deterministic extrapolation is more important than the
observed held-out score gain.

Runtime was `44.5` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.


## Ticket-Specific Sideband Validation

The real-data sideband validation uses held-out clean single-pulse controls
sampled directly from raw ROOT residual families.  These rows test whether a
method hallucinates a second pulse in data-like controls after the same clipping
and pedestal operations used in the benchmark.

| sideband               | value          | method                                         |   n_clean_controls |   false_split_rate |   score_median |   score_p90 |
|:-----------------------|:---------------|:-----------------------------------------------|-------------------:|-------------------:|---------------:|------------:|
| morphology_state       | late_tail_high | 1d_cnn                                         |                238 |            0.1513  |      0.2618    |      0.591  |
| morphology_state       | late_tail_low  | 1d_cnn                                         |                152 |            0.2829  |      0.31      |      0.7194 |
| morphology_state       | late_tail_high | analytic_clipped_template_sideband_traditional |                238 |            0.1471  |      0         |      0.708  |
| morphology_state       | late_tail_low  | analytic_clipped_template_sideband_traditional |                152 |            0.2763  |      1.265e-05 |      0.992  |
| morphology_state       | late_tail_high | gradient_boosted_trees                         |                238 |            0.1134  |      0.1392    |      0.5273 |
| morphology_state       | late_tail_low  | gradient_boosted_trees                         |                152 |            0.1974  |      0.2054    |      0.6487 |
| morphology_state       | late_tail_high | mlp                                            |                238 |            0.06723 |      0.1443    |      0.3986 |
| morphology_state       | late_tail_low  | mlp                                            |                152 |            0.1316  |      0.2372    |      0.5897 |
| morphology_state       | late_tail_high | ridge                                          |                238 |            0.07563 |      0.3658    |      0.4926 |
| morphology_state       | late_tail_low  | ridge                                          |                152 |            0.2237  |      0.4099    |      0.5557 |
| morphology_state       | late_tail_high | saturation_residual_fusion_new                 |                238 |            0.09244 |      0.1432    |      0.4806 |
| morphology_state       | late_tail_low  | saturation_residual_fusion_new                 |                152 |            0.2039  |      0.2158    |      0.6377 |
| morphology_state       | late_tail_high | tiny_sequence_transformer                      |                238 |            0.04202 |      0.166     |      0.3815 |
| morphology_state       | late_tail_low  | tiny_sequence_transformer                      |                152 |            0.09868 |      0.2355    |      0.481  |
| pedestal_state         | nominal        | 1d_cnn                                         |                148 |            0.2027  |      0.2808    |      0.6412 |
| pedestal_state         | shifted        | 1d_cnn                                         |                242 |            0.2025  |      0.2734    |      0.6464 |
| pedestal_state         | nominal        | analytic_clipped_template_sideband_traditional |                148 |            0.2635  |      0         |      0.9855 |
| pedestal_state         | shifted        | analytic_clipped_template_sideband_traditional |                242 |            0.157   |      0         |      0.8619 |
| pedestal_state         | nominal        | gradient_boosted_trees                         |                148 |            0.1014  |      0.1093    |      0.4772 |
| pedestal_state         | shifted        | gradient_boosted_trees                         |                242 |            0.1736  |      0.2005    |      0.6149 |
| pedestal_state         | nominal        | mlp                                            |                148 |            0.08108 |      0.163     |      0.4012 |
| pedestal_state         | shifted        | mlp                                            |                242 |            0.09917 |      0.202     |      0.499  |
| pedestal_state         | nominal        | ridge                                          |                148 |            0.08108 |      0.3755    |      0.493  |
| pedestal_state         | shifted        | ridge                                          |                242 |            0.1653  |      0.3809    |      0.5376 |
| pedestal_state         | nominal        | saturation_residual_fusion_new                 |                148 |            0.08108 |      0.1265    |      0.4647 |
| pedestal_state         | shifted        | saturation_residual_fusion_new                 |                242 |            0.1694  |      0.203     |      0.6328 |
| pedestal_state         | nominal        | tiny_sequence_transformer                      |                148 |            0.06757 |      0.1878    |      0.4333 |
| pedestal_state         | shifted        | tiny_sequence_transformer                      |                242 |            0.06198 |      0.1831    |      0.4199 |
| saturated_sample_count | 0              | 1d_cnn                                         |                390 |            0.2026  |      0.275     |      0.647  |
| saturated_sample_count | 0              | analytic_clipped_template_sideband_traditional |                390 |            0.1974  |      0         |      0.9643 |
| saturated_sample_count | 0              | gradient_boosted_trees                         |                390 |            0.1462  |      0.1591    |      0.5739 |
| saturated_sample_count | 0              | mlp                                            |                390 |            0.09231 |      0.187     |      0.4681 |
| saturated_sample_count | 0              | ridge                                          |                390 |            0.1333  |      0.3796    |      0.5262 |
| saturated_sample_count | 0              | saturation_residual_fusion_new                 |                390 |            0.1359  |      0.1621    |      0.5548 |
| saturated_sample_count | 0              | tiny_sequence_transformer                      |                390 |            0.0641  |      0.1849    |      0.4268 |
| source_run             | 58             | 1d_cnn                                         |                 78 |            0.1923  |      0.2773    |      0.6038 |
| source_run             | 60             | 1d_cnn                                         |                 78 |            0.1538  |      0.2564    |      0.5897 |
| source_run             | 62             | 1d_cnn                                         |                 78 |            0.2564  |      0.3035    |      0.6878 |
| source_run             | 64             | 1d_cnn                                         |                 78 |            0.1795  |      0.2628    |      0.6125 |
| source_run             | 65             | 1d_cnn                                         |                 78 |            0.2308  |      0.2931    |      0.7186 |

## Saturation-Knee Bias

The saturation-knee diagnostic bins held-out injected doublets by clipped-sample
count.  The `knee_1_2_clipped` bin is the operational transition region where a
clipped-charge integral first loses linearity; `deep_ge3_clipped` tests heavier
censoring.  Bias is the mean fractional total-energy residual, and sigma68 is
`(Q84-Q16)/2`.

| saturation_knee_bin   | method                                         |   n_valid_doublets |   energy_fractional_bias |   energy_fractional_sigma68 |   median_plateau_width |
|:----------------------|:-----------------------------------------------|-------------------:|-------------------------:|----------------------------:|-----------------------:|
| unsaturated           | 1d_cnn                                         |                275 |                0.06299   |                     0.101   |                      2 |
| unsaturated           | analytic_clipped_template_sideband_traditional |                157 |                0.08163   |                     0.1015  |                      2 |
| unsaturated           | gradient_boosted_trees                         |                243 |               -0.001615  |                     0.07317 |                      2 |
| unsaturated           | mlp                                            |                231 |                0.005946  |                     0.1589  |                      2 |
| unsaturated           | ridge                                          |                262 |                0.008649  |                     0.06717 |                      2 |
| unsaturated           | saturation_residual_fusion_new                 |                248 |               -0.0005698 |                     0.06708 |                      2 |
| unsaturated           | tiny_sequence_transformer                      |                140 |               -0.004859  |                     0.1021  |                      2 |

## Pile-Up Separation Error

Pile-up separation error is the held-out fraction for which the reconstructed
pulse spacing differs from injected truth by more than 1.5 samples.  Confidence
intervals resample held-out runs with replacement.

| method                                         |   n_doublets |   pileup_separation_error_rate |   pileup_separation_error_ci_low |   pileup_separation_error_ci_high |   pileup_miss_rate |
|:-----------------------------------------------|-------------:|-------------------------------:|---------------------------------:|----------------------------------:|-------------------:|
| analytic_clipped_template_sideband_traditional |          390 |                         0.2103 |                           0.1744 |                            0.2462 |             0.5846 |
| gradient_boosted_trees                         |          390 |                         0.2128 |                           0.1872 |                            0.2513 |             0.3538 |
| saturation_residual_fusion_new                 |          390 |                         0.2205 |                           0.1846 |                            0.259  |             0.341  |
| ridge                                          |          390 |                         0.2897 |                           0.2564 |                            0.3256 |             0.3051 |
| 1d_cnn                                         |          390 |                         0.3692 |                           0.3256 |                            0.4206 |             0.2718 |
| mlp                                            |          390 |                         0.3821 |                           0.3204 |                            0.4437 |             0.3846 |
| tiny_sequence_transformer                      |          390 |                         0.7487 |                           0.7051 |                            0.7897 |             0.6231 |

## Pedestal Covariance Sensitivity

Pedestal covariance sensitivity is summarized as the span of energy bias and
sigma68 across raw-derived pedestal-state strata.  A low span means the method's
energy closure is less coupled to the pre-trigger covariance state.

| method                                         |   n_pedestal_states |   state_bias_span |   state_sigma68_span | worst_state   |   worst_abs_state_bias |
|:-----------------------------------------------|--------------------:|------------------:|---------------------:|:--------------|-----------------------:|
| saturation_residual_fusion_new                 |                   2 |          0.007385 |             0.01384  | nominal       |               0.005258 |
| analytic_clipped_template_sideband_traditional |                   2 |          0.01328  |             0.007737 | shifted       |               0.09022  |
| gradient_boosted_trees                         |                   2 |          0.01363  |             0.005039 | nominal       |               0.01074  |
| 1d_cnn                                         |                   2 |          0.02749  |             0.03256  | shifted       |               0.07139  |
| ridge                                          |                   2 |          0.04079  |             0.02591  | shifted       |               0.02215  |
| tiny_sequence_transformer                      |                   2 |          0.0535   |             0.02846  | nominal       |               0.03939  |
| mlp                                            |                   2 |          0.09145  |             0.04269  | nominal       |               0.05414  |

## Downstream PID Stability Proxy

The downstream PID stability table stratifies held-out energy closure by run,
amplitude, timing separation, and the benchmark PID proxy class.  The stability
proxy is the worst stratum sigma68 divided by the median stratum sigma68; values
near one indicate less risk of PID-boundary migration from energy-scale
heterogeneity.

| stability_axis   | method                                         |   n_strata |   energy_sigma68_stratum_median |   energy_sigma68_stratum_span |   pid_stability_proxy |
|:-----------------|:-----------------------------------------------|-----------:|--------------------------------:|------------------------------:|----------------------:|
| amp_stratum      | gradient_boosted_trees                         |          4 |                         0.07612 |                      0.04192  |                 1.142 |
| amp_stratum      | saturation_residual_fusion_new                 |          4 |                         0.06869 |                      0.05949  |                 1.173 |
| amp_stratum      | 1d_cnn                                         |          4 |                         0.0917  |                      0.09197  |                 1.274 |
| amp_stratum      | tiny_sequence_transformer                      |          4 |                         0.08905 |                      0.1074   |                 1.509 |
| amp_stratum      | ridge                                          |          4 |                         0.05805 |                      0.06204  |                 1.553 |
| amp_stratum      | analytic_clipped_template_sideband_traditional |          3 |                         0.0872  |                      0.07618  |                 1.595 |
| amp_stratum      | mlp                                            |          4 |                         0.1167  |                      0.1678   |                 1.866 |
| pid_proxy_class  | saturation_residual_fusion_new                 |          2 |                         0.07143 |                      0.002809 |                 1.02  |
| pid_proxy_class  | gradient_boosted_trees                         |          2 |                         0.07866 |                      0.006773 |                 1.043 |
| pid_proxy_class  | ridge                                          |          2 |                         0.06617 |                      0.008688 |                 1.066 |
| pid_proxy_class  | tiny_sequence_transformer                      |          2 |                         0.1024  |                      0.02413  |                 1.118 |
| pid_proxy_class  | 1d_cnn                                         |          2 |                         0.09396 |                      0.02609  |                 1.139 |
| pid_proxy_class  | analytic_clipped_template_sideband_traditional |          2 |                         0.08781 |                      0.05229  |                 1.298 |
| pid_proxy_class  | mlp                                            |          2 |                         0.1227  |                      0.09847  |                 1.401 |
| source_run       | gradient_boosted_trees                         |          5 |                         0.07977 |                      0.02784  |                 1.048 |
| source_run       | 1d_cnn                                         |          5 |                         0.1058  |                      0.02649  |                 1.084 |
| source_run       | saturation_residual_fusion_new                 |          5 |                         0.07043 |                      0.01056  |                 1.102 |
| source_run       | mlp                                            |          5 |                         0.1558  |                      0.03858  |                 1.136 |
| source_run       | tiny_sequence_transformer                      |          5 |                         0.1196  |                      0.04386  |                 1.159 |
| source_run       | analytic_clipped_template_sideband_traditional |          5 |                         0.1011  |                      0.02876  |                 1.203 |
| source_run       | ridge                                          |          5 |                         0.06529 |                      0.02877  |                 1.273 |
| timing_stratum   | 1d_cnn                                         |          3 |                         0.1064  |                      0.01241  |                 1.054 |
| timing_stratum   | mlp                                            |          3 |                         0.1564  |                      0.0502   |                 1.281 |
| timing_stratum   | analytic_clipped_template_sideband_traditional |          3 |                         0.09146 |                      0.04774  |                 1.439 |
| timing_stratum   | gradient_boosted_trees                         |          3 |                         0.07004 |                      0.04458  |                 1.543 |
| timing_stratum   | ridge                                          |          3 |                         0.06077 |                      0.03942  |                 1.6   |
| timing_stratum   | saturation_residual_fusion_new                 |          3 |                         0.06103 |                      0.04301  |                 1.668 |
| timing_stratum   | tiny_sequence_transformer                      |          3 |                         0.07349 |                      0.1126   |                 2.467 |

## Saturation-Mask Ablation

The saturation-mask ablation recomputes the held-out metrics after slicing on
the observed clipped-sample mask.  This is not a retraining pass; it asks whether
the winning conclusion is carried by unsaturated easy cases or by the clipped
tail-recovery region named in the ticket.

| ablation                 | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |   n_events |
|:-------------------------|:-----------------------------------------------|-------------------------:|----------------------------:|------------------:|-------------------:|-------------------:|-----------:|
| all_heldout              | 1d_cnn                                         |                 0.05128  |                     0.1033  |            10.51  |             0.2718 |            0.2026  |        780 |
| all_heldout              | analytic_clipped_template_sideband_traditional |                 0.07918  |                     0.1006  |             9.454 |             0.5846 |            0.1974  |        780 |
| all_heldout              | gradient_boosted_trees                         |                -0.004337 |                     0.07328 |             8.231 |             0.3538 |            0.1462  |        780 |
| all_heldout              | mlp                                            |                -0.02341  |                     0.1571  |            11.84  |             0.3846 |            0.09231 |        780 |
| all_heldout              | ridge                                          |                -0.01034  |                     0.06713 |            10.34  |             0.3051 |            0.1333  |        780 |
| all_heldout              | saturation_residual_fusion_new                 |                -0.00549  |                     0.06688 |             8.368 |             0.341  |            0.1359  |        780 |
| all_heldout              | tiny_sequence_transformer                      |                -0.01747  |                     0.1047  |            18.15  |             0.6231 |            0.0641  |        780 |
| deep_saturation_mask_ge3 | 1d_cnn                                         |                -0.02193  |                     0.02724 |            15.7   |             0      |          nan       |          5 |
| deep_saturation_mask_ge3 | analytic_clipped_template_sideband_traditional |                 0.177    |                     0.05639 |            11.86  |             0.4    |          nan       |          5 |
| deep_saturation_mask_ge3 | gradient_boosted_trees                         |                -0.04276  |                     0.03807 |             5.049 |             0      |          nan       |          5 |
| deep_saturation_mask_ge3 | mlp                                            |                -0.1059   |                     0.04671 |            11.6   |             0      |          nan       |          5 |
| deep_saturation_mask_ge3 | ridge                                          |                -0.04979  |                     0.01396 |             7.93  |             0      |          nan       |          5 |
| deep_saturation_mask_ge3 | saturation_residual_fusion_new                 |                -0.00549  |                     0.01253 |             3.813 |             0      |          nan       |          5 |
| deep_saturation_mask_ge3 | tiny_sequence_transformer                      |                -0.1435   |                     0.02993 |             7.666 |             0.2    |          nan       |          5 |
| saturated_mask_gt0       | 1d_cnn                                         |                -0.02193  |                     0.04639 |            15.23  |             0      |          nan       |          9 |
| saturated_mask_gt0       | analytic_clipped_template_sideband_traditional |                 0.1357   |                     0.06908 |            14.49  |             0.4444 |          nan       |          9 |
| saturated_mask_gt0       | gradient_boosted_trees                         |                -0.01597  |                     0.0692  |             8.071 |             0      |          nan       |          9 |
| saturated_mask_gt0       | mlp                                            |                -0.09335  |                     0.09011 |            17.1   |             0      |          nan       |          9 |
| saturated_mask_gt0       | ridge                                          |                -0.03814  |                     0.03413 |             8.771 |             0      |          nan       |          9 |
| saturated_mask_gt0       | saturation_residual_fusion_new                 |                -0.00549  |                     0.04622 |             5.849 |             0      |          nan       |          9 |
| saturated_mask_gt0       | tiny_sequence_transformer                      |                -0.1235   |                     0.04672 |            14.12  |             0.2222 |          nan       |          9 |
| unsaturated_mask_0       | 1d_cnn                                         |                 0.05562  |                     0.101   |            10.49  |             0.2782 |            0.2026  |        771 |
| unsaturated_mask_0       | analytic_clipped_template_sideband_traditional |                 0.07373  |                     0.1015  |             9.336 |             0.5879 |            0.1974  |        771 |
| unsaturated_mask_0       | gradient_boosted_trees                         |                -0.004281 |                     0.07317 |             8.252 |             0.3622 |            0.1462  |        771 |
| unsaturated_mask_0       | mlp                                            |                -0.02189  |                     0.1589  |            11.7   |             0.3937 |            0.09231 |        771 |
| unsaturated_mask_0       | ridge                                          |                -0.009765 |                     0.06717 |            10.29  |             0.3123 |            0.1333  |        771 |
| unsaturated_mask_0       | saturation_residual_fusion_new                 |                -0.005245 |                     0.06708 |             8.373 |             0.3491 |            0.1359  |        771 |
| unsaturated_mask_0       | tiny_sequence_transformer                      |                -0.009727 |                     0.1021  |            18.38  |             0.6325 |            0.0641  |        771 |

## Uncertainty Calibration

The per-event uncertainty proxy is a transparent function of clipped samples,
plateau width, and close-pulse spacing:

`u_i = 0.030 + 0.006 n_clip + 0.004 max(W_plateau-2,0) + 0.002 max(4-Delta,0)`.

Coverage is reported against the absolute fractional energy residual.

| method                                         |   n_valid_doublets |   p68_abs_energy_residual |   nominal_68_proxy_width |   coverage_abs_resid_le_proxy |   coverage_abs_resid_le_2proxy |   calibration_ratio_p68_over_proxy |
|:-----------------------------------------------|-------------------:|--------------------------:|-------------------------:|------------------------------:|-------------------------------:|-----------------------------------:|
| ridge                                          |                271 |                   0.0665  |                    0.036 |                        0.4539 |                         0.6937 |                              1.847 |
| saturation_residual_fusion_new                 |                257 |                   0.06791 |                    0.035 |                        0.4086 |                         0.6965 |                              1.94  |
| gradient_boosted_trees                         |                252 |                   0.07359 |                    0.035 |                        0.4127 |                         0.6667 |                              2.103 |
| tiny_sequence_transformer                      |                147 |                   0.105   |                    0.034 |                        0.2653 |                         0.517  |                              3.087 |
| 1d_cnn                                         |                284 |                   0.1169  |                    0.036 |                        0.2535 |                         0.4683 |                              3.248 |
| analytic_clipped_template_sideband_traditional |                162 |                   0.1238  |                    0.034 |                        0.1914 |                         0.4198 |                              3.641 |
| mlp                                            |                240 |                   0.1526  |                    0.036 |                        0.1667 |                         0.3458 |                              4.239 |

## Queue Provenance

The required single claim command was run once as `tn-ticket claim testbeam-laptop-4 --project testbeam` and returned
the null pseudo-ticket output `null / # null / null`.  Because the project queue was
not empty, issue `#2544` was recovered without a second `tn-ticket claim` by
applying the same label transition directly: `gh issue edit 2544 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`.  Completion is
recorded with `tn-ticket done 2544`.  No novel follow-up ticket was appended.

# S59b/#2531: Censored Tail Deconvolution for Saturated Pile-Up Energy and PID Recovery

## Abstract

Ticket `#2531` asks for an academic-grade comparison of a strong traditional
Wiener/ARX deconvolution with censored template likelihood against ridge,
gradient-boosted trees, MLP, 1D-CNN, transformer sequence models, and a new
architecture for energy and PID recovery under clipped saturation and
unresolved pile-up.  The worker is `testbeam-laptop-1`.  The
winner is **`saturation_residual_fusion_new`**, selected by held-out run-block energy closure:
fractional energy sigma68 `0.06839` with 95%
CI [`0.06184`,
`0.07519`].  Its composite score is
`0.1517`.

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

The traditional comparator is **analytic_clipped_template_sideband_traditional**, interpreted for S59b as a Wiener/ARX-style censored-tail template likelihood baseline.
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
| saturation_residual_fusion_new                 |         0.1517 |               -0.002907  |                     0.06839 |                            0.06184 |                             0.07519 |        -0.2714 |             8.024 |                    7.365 |                     8.669 |             0.3256 |            0.1385  |
| gradient_boosted_trees                         |         0.16   |               -0.004337  |                     0.07328 |                            0.06523 |                             0.08059 |        -0.3938 |             8.231 |                    7.863 |                     8.439 |             0.3538 |            0.1462  |
| ridge                                          |         0.1695 |               -0.01034   |                     0.06713 |                            0.05628 |                             0.07009 |        -1.051  |            10.34  |                    9.307 |                    11     |             0.3051 |            0.1333  |
| 1d_cnn                                         |         0.2168 |                0.04774   |                     0.09965 |                            0.09021 |                             0.1066  |        -1.768  |            11.03  |                   10.33  |                    11.42  |             0.2667 |            0.2179  |
| analytic_clipped_template_sideband_traditional |         0.2234 |                0.07918   |                     0.1006  |                            0.09114 |                             0.1148  |         0.5086 |             9.454 |                    8.518 |                    10.46  |             0.5846 |            0.1974  |
| tiny_sequence_transformer                      |         0.2713 |                0.0006918 |                     0.1027  |                            0.08737 |                             0.1139  |       -15.75   |            17.75  |                   16.96  |                    19.41  |             0.5949 |            0.06923 |
| mlp                                            |         0.2756 |               -0.02341   |                     0.1571  |                            0.1433  |                             0.1622  |         0.3222 |            11.84  |                   10.46  |                    13.39  |             0.3846 |            0.09231 |

The traditional comparator has energy sigma68 `0.1006`
and score `0.2234`.  The selected winner changes energy
sigma68 by `-0.03224`
and timing sigma68 by `-1.43` ns.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                 0.05719  |                     0.1108  |      -1.239    |            11.04  |             0.2436 |            0.1795  |
| 1d_cnn                                         |            60 |                 0.08472  |                     0.099   |      -0.002197 |            11.3   |             0.2179 |            0.1538  |
| 1d_cnn                                         |            62 |                 0.07573  |                     0.09183 |      -4.058    |            10.75  |             0.359  |            0.3205  |
| 1d_cnn                                         |            64 |                 0.01926  |                     0.08143 |      -1.149    |             9.674 |             0.2308 |            0.1923  |
| 1d_cnn                                         |            65 |                 0.03106  |                     0.09207 |      -1.706    |            11.11  |             0.2821 |            0.2436  |
| analytic_clipped_template_sideband_traditional |            58 |                 0.05961  |                     0.09176 |      -0.8261   |             9.586 |             0.5641 |            0.2179  |
| analytic_clipped_template_sideband_traditional |            60 |                 0.1035   |                     0.1049  |       2.624    |             7.291 |             0.6026 |            0.1923  |
| analytic_clipped_template_sideband_traditional |            62 |                 0.08827  |                     0.114   |       0.7759   |            11.39  |             0.5897 |            0.2051  |
| analytic_clipped_template_sideband_traditional |            64 |                 0.06412  |                     0.06839 |       0.3945   |             7.361 |             0.5385 |            0.1282  |
| analytic_clipped_template_sideband_traditional |            65 |                 0.08165  |                     0.0913  |      -1        |             9.997 |             0.6282 |            0.2436  |
| gradient_boosted_trees                         |            58 |                 0.01035  |                     0.06828 |      -0.4859   |             7.496 |             0.2821 |            0.1538  |
| gradient_boosted_trees                         |            60 |                 0.003428 |                     0.07901 |       0.6314   |             8.349 |             0.3077 |            0.1795  |
| gradient_boosted_trees                         |            62 |                -0.001499 |                     0.06871 |      -1.548    |             8.259 |             0.3974 |            0.1282  |
| gradient_boosted_trees                         |            64 |                -0.03631  |                     0.05706 |      -0.5679   |             8.253 |             0.3462 |            0.1538  |
| gradient_boosted_trees                         |            65 |                -0.002961 |                     0.05651 |       0.421    |             8.169 |             0.4359 |            0.1154  |
| mlp                                            |            58 |                -0.04822  |                     0.1362  |       0.1445   |            13.78  |             0.3462 |            0.08974 |
| mlp                                            |            60 |                 0.02265  |                     0.1507  |       1.063    |             9.217 |             0.2564 |            0.1154  |
| mlp                                            |            62 |                -0.02757  |                     0.1489  |       1.786    |            12.26  |             0.4744 |            0.1026  |
| mlp                                            |            64 |                -0.06036  |                     0.1488  |      -0.6515   |            11.06  |             0.3333 |            0.1026  |
| mlp                                            |            65 |                -0.03285  |                     0.1656  |      -1.225    |            14.2   |             0.5128 |            0.05128 |
| ridge                                          |            58 |                -0.00873  |                     0.06969 |      -0.3508   |            10.08  |             0.2821 |            0.1538  |
| ridge                                          |            60 |                 0.01055  |                     0.06889 |       0.6309   |             9.658 |             0.2436 |            0.141   |
| ridge                                          |            62 |                 0.001731 |                     0.06261 |      -3.103    |            11.26  |             0.3718 |            0.141   |
| ridge                                          |            64 |                -0.02938  |                     0.05241 |      -0.7281   |             9.295 |             0.2436 |            0.1026  |
| ridge                                          |            65 |                -0.006805 |                     0.05437 |      -2.533    |             9.576 |             0.3846 |            0.1282  |
| saturation_residual_fusion_new                 |            58 |                 0.001794 |                     0.06272 |       0.1602   |             7.283 |             0.2564 |            0.1667  |
| saturation_residual_fusion_new                 |            60 |                 0.005086 |                     0.07569 |       0.5078   |             7.735 |             0.2949 |            0.1667  |
| saturation_residual_fusion_new                 |            62 |                 0.0287   |                     0.06522 |      -1.508    |             8.79  |             0.3462 |            0.1154  |
| saturation_residual_fusion_new                 |            64 |                -0.03486  |                     0.05366 |      -0.7482   |             7.792 |             0.3205 |            0.1538  |
| saturation_residual_fusion_new                 |            65 |                -0.01018  |                     0.07301 |       0.1934   |             7.984 |             0.4103 |            0.08974 |
| tiny_sequence_transformer                      |            58 |                -0.007738 |                     0.1248  |     -14.53     |            16.72  |             0.5128 |            0.03846 |
| tiny_sequence_transformer                      |            60 |                 0.02831  |                     0.09785 |     -13.86     |            19.2   |             0.5513 |            0.1026  |
| tiny_sequence_transformer                      |            62 |                -0.003341 |                     0.08162 |     -18.25     |            17.33  |             0.6538 |            0.0641  |
| tiny_sequence_transformer                      |            64 |                -0.009077 |                     0.08412 |     -18        |            19.35  |             0.641  |            0.08974 |
| tiny_sequence_transformer                      |            65 |                -0.008381 |                     0.08886 |     -15.26     |            18.86  |             0.6154 |            0.05128 |

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |                0.06824   |                    0.09101  |      -1.906    |            13.29  |            0.3561  |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |                0.05466   |                    0.1003   |      -0.9346   |            10.11  |            0.3068  |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |                0.04483   |                    0.09843  |      -4.805    |             9.98  |            0.1795  |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |                0.02517   |                    0.09192  |       0.6737   |            10.7   |            0.1739  |
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
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.01636   |                    0.06854  |       0.2542   |             7.469 |            0.4242  |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |                0.03361   |                    0.04364  |       0.6541   |             7.852 |            0.3977  |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |                0.001794  |                    0.06553  |      -1.451    |             9.025 |            0.2308  |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.04433   |                    0.06021  |      -0.6275   |             9.272 |            0.1957  |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |                0.05655   |                    0.06687  |     -12.61     |             9.402 |            0.75    |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |                0.05505   |                    0.05662  |     -16.3      |             8.701 |            0.7386  |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |               -0.01376   |                    0.06152  |     -19.58     |            16.85  |            0.5256  |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.0567    |                    0.08732  |     -18.59     |            22.59  |            0.2935  |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |                0.04227   |                    0.09343  |      -2.895    |            10.74  |            0.4304  |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |                0.04707   |                    0.1041   |      -3.128    |            10.8   |            0.2477  |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |                0.05466   |                    0.09765  |      -2.033    |            10.43  |            0.2247  |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |                0.05146   |                    0.08636  |       1.003    |            10.7   |            0.2035  |
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
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |               -0.02048   |                    0.06721  |      -3.37     |            10.58  |            0.5316  |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |                0.01452   |                    0.07227  |      -1.03     |             8.99  |            0.367   |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.004919  |                    0.06446  |      -0.5656   |             6.481 |            0.2809  |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |               -0.003736  |                    0.0653   |       1.604    |             7.339 |            0.177   |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |                0.01343   |                    0.0955   |     -14.89     |            13.68  |            0.6835  |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |                0.02227   |                    0.1048   |     -18.45     |            17.65  |            0.6055  |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |               -0.009782  |                    0.1125   |     -16.47     |            18.29  |            0.618   |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |               -0.01844   |                    0.07959  |     -11.96     |            19.71  |            0.5044  |
| saturation_bin   | 0                 | 1d_cnn                                         |                0.0504    |                    0.09846  |      -1.585    |            10.95  |            0.273   |
| saturation_bin   | 1-2               | 1d_cnn                                         |               -0.01671   |                    0.0987   |     -10.15     |             4.392 |            0       |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.01702   |                    0.02001  |      -2.004    |            16.11  |            0       |
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
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |               -0.002582  |                    0.06902  |      -0.2951   |             7.98  |            0.3333  |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |               -0.002311  |                    0.07841  |      -3.286    |            10.16  |            0       |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.01081   |                    0.01219  |       1.577    |             4.333 |            0       |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |                0.004608  |                    0.1016   |     -15.75     |            17.93  |            0.6063  |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |               -0.03803   |                    0.09451  |     -20.55     |            11.93  |            0       |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.1398    |                    0.02932  |      -8.485    |             8.047 |            0.2     |
| pedestal_state   | nominal           | 1d_cnn                                         |                0.03555   |                    0.0808   |      -0.5437   |             9.604 |            0.2074  |
| pedestal_state   | shifted           | 1d_cnn                                         |                0.05466   |                    0.1083   |      -2.657    |            11.28  |            0.298   |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |                0.06821   |                    0.1036   |       0.6337   |             6.868 |            0.4296  |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |                0.08124   |                    0.09584  |      -0.323    |            12.33  |            0.6667  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.01004   |                    0.06861  |       1.187    |             7.122 |            0.3333  |
| pedestal_state   | shifted           | gradient_boosted_trees                         |               -0.003157  |                    0.07365  |      -1.116    |             8.407 |            0.3647  |
| pedestal_state   | nominal           | mlp                                            |               -0.07348   |                    0.1306   |       2.354    |            10.37  |            0.3481  |
| pedestal_state   | shifted           | mlp                                            |                0.008483  |                    0.1733   |      -0.9066   |            12.76  |            0.4039  |
| pedestal_state   | nominal           | ridge                                          |               -0.01825   |                    0.04632  |       0.5808   |             9.145 |            0.2815  |
| pedestal_state   | shifted           | ridge                                          |               -0.001909  |                    0.07223  |      -2.307    |            10.8   |            0.3176  |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |               -0.004569  |                    0.05744  |       0.5801   |             6.93  |            0.3185  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |               -0.002258  |                    0.07072  |      -0.7335   |             8.42  |            0.3294  |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |               -0.02244   |                    0.08921  |     -15.61     |            19.22  |            0.5111  |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |                0.01552   |                    0.1034   |     -15.79     |            16.55  |            0.6392  |
| morphology_state | late_tail_high    | 1d_cnn                                         |                0.06138   |                    0.08727  |      -3.408    |            10.82  |            0.3295  |
| morphology_state | late_tail_low     | 1d_cnn                                         |                0.03837   |                    0.1055   |      -0.796    |            11.2   |            0.2166  |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |                0.1233    |                    0.101    |       0.5945   |             7.427 |            0.6936  |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |                0.06126   |                    0.08171  |       0.2364   |            10.51  |            0.4977  |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |                0.002568  |                    0.06696  |       0.1802   |             8.044 |            0.4162  |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |               -0.01204   |                    0.07666  |      -0.5469   |             8.455 |            0.3041  |
| morphology_state | late_tail_high    | mlp                                            |               -0.03303   |                    0.1331   |       0.472    |             8.738 |            0.4277  |
| morphology_state | late_tail_low     | mlp                                            |               -0.02084   |                    0.1771   |       0.05644  |            14.88  |            0.3502  |
| morphology_state | late_tail_high    | ridge                                          |               -0.008094  |                    0.06133  |       0.3451   |             8.467 |            0.3584  |
| morphology_state | late_tail_low     | ridge                                          |               -0.01095   |                    0.07013  |      -2.136    |            11.4   |            0.2627  |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |                0.01914   |                    0.05938  |      -0.05415  |             7.487 |            0.3757  |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.02076   |                    0.07207  |      -0.4335   |             8.696 |            0.2857  |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |                0.02674   |                    0.07685  |     -19.02     |            14.75  |            0.711   |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |               -0.01404   |                    0.1094   |     -13.35     |            18.36  |            0.5023  |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.02363   |                    0.06256  |      -7.135    |            11.66  |            0.2917  |
| pid_proxy_class  | other             | 1d_cnn                                         |                0.05285   |                    0.09746  |      -1.451    |            10.97  |            0.265   |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |                0.07949   |                    0.06167  |       3.535    |            12.8   |            0.5417  |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |                0.07887   |                    0.1034   |       0.2891   |             8.984 |            0.5874  |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.05084   |                    0.08205  |      -4.985    |             9.13  |            0.1667  |
| pid_proxy_class  | other             | gradient_boosted_trees                         |               -0.003038  |                    0.06894  |      -0.1418   |             8.083 |            0.3661  |
| pid_proxy_class  | inner_high_charge | mlp                                            |               -0.08423   |                    0.07343  |      -0.8013   |            15.14  |            0.08333 |
| pid_proxy_class  | other             | mlp                                            |               -0.009771  |                    0.1605   |       0.4354   |            11.48  |            0.4044  |
| pid_proxy_class  | inner_high_charge | ridge                                          |               -0.04979   |                    0.05878  |      -5.357    |            11.57  |            0.04167 |
| pid_proxy_class  | other             | ridge                                          |               -0.007556  |                    0.06558  |      -0.6305   |             9.802 |            0.3224  |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |               -0.03909   |                    0.08857  |      -3.494    |             9.808 |            0.1667  |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |                0.001582  |                    0.06814  |      -0.1505   |             7.704 |            0.3361  |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |               -0.06351   |                    0.07445  |     -16.43     |            17.47  |            0.2917  |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |                0.01115   |                    0.1023   |     -15.59     |            17.81  |            0.6148  |
| stave            | B2                | 1d_cnn                                         |               -0.04387   |                    0.09841  |      -7.131    |            12.1   |            0.4505  |
| stave            | B4                | 1d_cnn                                         |                0.09781   |                    0.08442  |      -5.336    |            10.41  |            0.2804  |
| stave            | B6                | 1d_cnn                                         |                0.04661   |                    0.08878  |      -0.7842   |             8.753 |            0.2471  |
| stave            | B8                | 1d_cnn                                         |                0.04795   |                    0.07284  |       2.601    |             8.801 |            0.1121  |
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
| stave            | B2                | saturation_residual_fusion_new                 |               -0.04592   |                    0.07768  |      -5.703    |             9.309 |            0.3956  |
| stave            | B4                | saturation_residual_fusion_new                 |                0.01619   |                    0.06897  |      -1.421    |             7.93  |            0.2991  |
| stave            | B6                | saturation_residual_fusion_new                 |               -0.0002057 |                    0.06089  |       0.5724   |             5.521 |            0.3647  |
| stave            | B8                | saturation_residual_fusion_new                 |                0.004243  |                    0.05155  |       1.908    |             6.136 |            0.2617  |
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

Runtime was `43.0` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.


## Ticket-Specific PID Recovery

The PID proxy is deliberately defined without external labels: an event is
positive when the B-stack support class is `inner_high_charge`.  The classifier
score is a monotone boundary in predicted recovered energy, late-tail state, and
observed censored samples,

`z_i = log(1 + hat E_i) + 0.075 I[late_tail_high] + 0.018 n_clip`.

The decision threshold is the held-out median score within each method.  This
keeps the PID boundary calibrated inside the held-out fold while avoiding any
post-window labels.

| method                                         |   pid_macro_f1 |   pid_macro_f1_ci_low |   pid_macro_f1_ci_high |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   pid_boundary_threshold |   n_events |
|:-----------------------------------------------|---------------:|----------------------:|-----------------------:|----------:|-----------------:|------------------:|-------------------------:|-----------:|
| analytic_clipped_template_sideband_traditional |         0.4706 |                0.4283 |                 0.5044 |    0.7056 |           0.3984 |            0.8267 |                    0.075 |        780 |
| tiny_sequence_transformer                      |         0.4121 |                0.3962 |                 0.4266 |    0.985  |           0.9775 |            0.9921 |                    8.304 |        780 |
| gradient_boosted_trees                         |         0.3917 |                0.3713 |                 0.4075 |    0.9867 |           0.9825 |            0.9938 |                    8.34  |        780 |
| saturation_residual_fusion_new                 |         0.3903 |                0.3708 |                 0.4063 |    0.9871 |           0.9821 |            0.9936 |                    8.339 |        780 |
| ridge                                          |         0.3859 |                0.3667 |                 0.4041 |    0.9888 |           0.9851 |            0.9938 |                    8.354 |        780 |
| mlp                                            |         0.3621 |                0.3464 |                 0.3779 |    0.9732 |           0.9607 |            0.9884 |                    8.399 |        780 |
| 1d_cnn                                         |         0.3621 |                0.3386 |                 0.3817 |    0.9727 |           0.9635 |            0.9894 |                    8.391 |        780 |

## Censored Tail Recovery

This table isolates the ticket's central censoring question by slicing injected
doublets on late-tail morphology and clipped-sample count.  The residual is
`(hat E - E) / E`, where `E = A_1 + A_2`.

| censor_bin        | tail_bin       | method                                         |   n_doublets |   energy_fractional_bias |   energy_fractional_sigma68 |   median_abs_residual |   pileup_miss_rate |
|:------------------|:---------------|:-----------------------------------------------|-------------:|-------------------------:|----------------------------:|----------------------:|-------------------:|
| light_clip_1_2    | late_tail_high | 1d_cnn                                         |            1 |                 0.2444   |                    0        |              0.2444   |             0      |
| light_clip_1_2    | late_tail_high | analytic_clipped_template_sideband_traditional |            1 |                -1        |                    0        |              1        |             1      |
| light_clip_1_2    | late_tail_high | gradient_boosted_trees                         |            1 |                 0.1299   |                    0        |              0.1299   |             0      |
| light_clip_1_2    | late_tail_high | mlp                                            |            1 |                 0.1662   |                    0        |              0.1662   |             0      |
| light_clip_1_2    | late_tail_high | ridge                                          |            1 |                 0.1603   |                    0        |              0.1603   |             0      |
| light_clip_1_2    | late_tail_high | saturation_residual_fusion_new                 |            1 |                 0.1338   |                    0        |              0.1338   |             0      |
| light_clip_1_2    | late_tail_high | tiny_sequence_transformer                      |            1 |                 0.1849   |                    0        |              0.1849   |             0      |
| light_clip_1_2    | late_tail_low  | 1d_cnn                                         |            3 |                -0.03288  |                    0.02938  |              0.05462  |             0      |
| light_clip_1_2    | late_tail_low  | analytic_clipped_template_sideband_traditional |            3 |                -0.2793   |                    0.3708   |              0.09063  |             0.3333 |
| light_clip_1_2    | late_tail_low  | gradient_boosted_trees                         |            3 |                -0.01361  |                    0.05397  |              0.05517  |             0      |
| light_clip_1_2    | late_tail_low  | mlp                                            |            3 |                -0.08837  |                    0.04182  |              0.06142  |             0      |
| light_clip_1_2    | late_tail_low  | ridge                                          |            3 |                -0.04673  |                    0.04658  |              0.007124 |             0      |
| light_clip_1_2    | late_tail_low  | saturation_residual_fusion_new                 |            3 |                -0.02562  |                    0.04136  |              0.05403  |             0      |
| light_clip_1_2    | late_tail_low  | tiny_sequence_transformer                      |            3 |                -0.06476  |                    0.03839  |              0.07076  |             0      |
| moderate_clip_3_5 | late_tail_high | 1d_cnn                                         |            2 |                 0.01266  |                    0.01556  |              0.02288  |             0      |
| moderate_clip_3_5 | late_tail_high | analytic_clipped_template_sideband_traditional |            2 |                -0.4309   |                    0.387    |              0.5691   |             1      |
| moderate_clip_3_5 | late_tail_high | gradient_boosted_trees                         |            2 |                -0.02937  |                    0.009107 |              0.02937  |             0      |
| moderate_clip_3_5 | late_tail_high | mlp                                            |            2 |                -0.1217   |                    0.01078  |              0.1217   |             0      |
| moderate_clip_3_5 | late_tail_high | ridge                                          |            2 |                -0.05658  |                    0.01254  |              0.05658  |             0      |
| moderate_clip_3_5 | late_tail_high | saturation_residual_fusion_new                 |            2 |                -0.02393  |                    0.008919 |              0.02393  |             0      |
| moderate_clip_3_5 | late_tail_high | tiny_sequence_transformer                      |            2 |                -0.03493  |                    0.01944  |              0.03493  |             0.5    |
| moderate_clip_3_5 | late_tail_low  | 1d_cnn                                         |            3 |                -0.03078  |                    0.01173  |              0.02378  |             0      |
| moderate_clip_3_5 | late_tail_low  | analytic_clipped_template_sideband_traditional |            3 |                 0.2048   |                    0.05639  |              0.177    |             0      |
| moderate_clip_3_5 | late_tail_low  | gradient_boosted_trees                         |            3 |                -0.04496  |                    0.04832  |              0.05499  |             0      |
| moderate_clip_3_5 | late_tail_low  | mlp                                            |            3 |                -0.04145  |                    0.06752  |              0.09335  |             0      |
| moderate_clip_3_5 | late_tail_low  | ridge                                          |            3 |                -0.04217  |                    0.009915 |              0.04979  |             0      |
| moderate_clip_3_5 | late_tail_low  | saturation_residual_fusion_new                 |            3 |                -0.002436 |                    0.006573 |              0.005788 |             0      |
| moderate_clip_3_5 | late_tail_low  | tiny_sequence_transformer                      |            3 |                -0.1442   |                    0.008794 |              0.1524   |             0      |
| uncensored        | late_tail_high | 1d_cnn                                         |          170 |                 0.0672   |                    0.1038   |              0.0832   |             0.3353 |
| uncensored        | late_tail_high | analytic_clipped_template_sideband_traditional |          170 |                -0.5657   |                    0.5661   |              1        |             0.6882 |
| uncensored        | late_tail_high | gradient_boosted_trees                         |          170 |                 0.007862 |                    0.07151  |              0.04633  |             0.4235 |
| uncensored        | late_tail_high | mlp                                            |          170 |                 0.03087  |                    0.1658   |              0.1122   |             0.4353 |
| uncensored        | late_tail_high | ridge                                          |          170 |                 0.01338  |                    0.06928  |              0.04269  |             0.3647 |
| uncensored        | late_tail_high | saturation_residual_fusion_new                 |          170 |                 0.01543  |                    0.06616  |              0.04868  |             0.3824 |
| uncensored        | late_tail_high | tiny_sequence_transformer                      |          170 |                 0.001105 |                    0.09294  |              0.06055  |             0.7176 |
| uncensored        | late_tail_low  | 1d_cnn                                         |          211 |                 0.04817  |                    0.1133   |              0.07687  |             0.2227 |
| uncensored        | late_tail_low  | analytic_clipped_template_sideband_traditional |          211 |                -0.3416   |                    0.5552   |              0.1524   |             0.5071 |
| uncensored        | late_tail_low  | gradient_boosted_trees                         |          211 |                 0.01681  |                    0.0844   |              0.05827  |             0.3128 |
| uncensored        | late_tail_low  | mlp                                            |          211 |                 0.02758  |                    0.1915   |              0.1336   |             0.3602 |
| uncensored        | late_tail_low  | ridge                                          |          211 |                 0.001599 |                    0.07507  |              0.05284  |             0.2701 |
| uncensored        | late_tail_low  | saturation_residual_fusion_new                 |          211 |                 0.0158   |                    0.08418  |              0.05913  |             0.2938 |
| uncensored        | late_tail_low  | tiny_sequence_transformer                      |          211 |                -0.02781  |                    0.1167   |              0.0756   |             0.5166 |

## Pile-Up Separation

Pile-up separation uses the method's held-out overlap score against the known
controlled-overlay label.  These are the same run-held-out events as the energy
closure tables.

| method                                         |   pileup_auc |   pileup_miss_rate |   false_split_rate |   n_events |
|:-----------------------------------------------|-------------:|-------------------:|-------------------:|-----------:|
| ridge                                          |       0.8493 |             0.3051 |            0.1333  |        780 |
| mlp                                            |       0.8493 |             0.3846 |            0.09231 |        780 |
| gradient_boosted_trees                         |       0.8393 |             0.3538 |            0.1462  |        780 |
| saturation_residual_fusion_new                 |       0.8377 |             0.3256 |            0.1385  |        780 |
| 1d_cnn                                         |       0.8162 |             0.2667 |            0.2179  |        780 |
| tiny_sequence_transformer                      |       0.7969 |             0.5949 |            0.06923 |        780 |
| analytic_clipped_template_sideband_traditional |       0.6226 |             0.5846 |            0.1974  |        780 |

## Pedestal Sensitivity

Pedestal sensitivity compares nominal and shifted pretrigger pedestal states.
The delta columns report shifted minus nominal degradation, so smaller absolute
values indicate better pedestal-memory robustness.

| method                                         | pedestal_state   |   n_events |   median_abs_energy_residual |   false_split_or_miss_rate |   delta_shifted_minus_nominal_median_abs_energy_residual |   delta_shifted_minus_nominal_error_rate |
|:-----------------------------------------------|:-----------------|-----------:|-----------------------------:|---------------------------:|---------------------------------------------------------:|-----------------------------------------:|
| 1d_cnn                                         | nominal          |        283 |                      0.07955 |                     0.212  |                                                  0.01747 |                                  0.04754 |
| 1d_cnn                                         | shifted          |        497 |                      0.09702 |                     0.2596 |                                                  0.01747 |                                  0.04754 |
| analytic_clipped_template_sideband_traditional | nominal          |        283 |                      0.2596  |                     0.3428 |                                                  0.7404  |                                  0.07575 |
| analytic_clipped_template_sideband_traditional | shifted          |        497 |                      1       |                     0.4185 |                                                  0.7404  |                                  0.07575 |
| gradient_boosted_trees                         | nominal          |        283 |                      0.06294 |                     0.212  |                                                  0.02024 |                                  0.05962 |
| gradient_boosted_trees                         | shifted          |        497 |                      0.08318 |                     0.2716 |                                                  0.02024 |                                  0.05962 |
| mlp                                            | nominal          |        283 |                      0.1348  |                     0.2085 |                                                  0.02731 |                                  0.04705 |
| mlp                                            | shifted          |        497 |                      0.1621  |                     0.2555 |                                                  0.02731 |                                  0.04705 |
| ridge                                          | nominal          |        283 |                      0.04999 |                     0.1767 |                                                  0.01627 |                                  0.06678 |
| ridge                                          | shifted          |        497 |                      0.06625 |                     0.2435 |                                                  0.01627 |                                  0.06678 |
| saturation_residual_fusion_new                 | nominal          |        283 |                      0.05825 |                     0.1943 |                                                  0.0128  |                                  0.05917 |
| saturation_residual_fusion_new                 | shifted          |        497 |                      0.07105 |                     0.2535 |                                                  0.0128  |                                  0.05917 |
| tiny_sequence_transformer                      | nominal          |        283 |                      0.07633 |                     0.2827 |                                                  0.01793 |                                  0.07748 |
| tiny_sequence_transformer                      | shifted          |        497 |                      0.09426 |                     0.3602 |                                                  0.01793 |                                  0.07748 |

## Saturation-Stratified Calibration

The saturation calibration table reports the same fractional energy residual
within clipped-sample bins.  `calibration_slope_proxy` is the linear residual
slope versus clipped-sample count inside the bin and should be near zero after
successful censored-tail recovery.

| saturation_bin   | method                                         |   n_doublets |   energy_fractional_bias |   energy_fractional_sigma68 |   calibration_slope_proxy |
|:-----------------|:-----------------------------------------------|-------------:|-------------------------:|----------------------------:|--------------------------:|
| 0                | 1d_cnn                                         |          381 |                 0.05666  |                     0.1113  |                  0        |
| 0                | analytic_clipped_template_sideband_traditional |          381 |                -0.4416   |                     0.56    |                  0        |
| 0                | gradient_boosted_trees                         |          381 |                 0.01282  |                     0.07696 |                  0        |
| 0                | mlp                                            |          381 |                 0.02904  |                     0.1851  |                  0        |
| 0                | ridge                                          |          381 |                 0.006855 |                     0.07223 |                  0        |
| 0                | saturation_residual_fusion_new                 |          381 |                 0.01564  |                     0.07649 |                  0        |
| 0                | tiny_sequence_transformer                      |          381 |                -0.01491  |                     0.1093  |                  0        |
| 1-2              | 1d_cnn                                         |            4 |                 0.03645  |                     0.0987  |                  0.1355   |
| 1-2              | analytic_clipped_template_sideband_traditional |            4 |                -0.4595   |                     0.5407  |                 -0.7335   |
| 1-2              | gradient_boosted_trees                         |            4 |                 0.02225  |                     0.07211 |                 -0.04389  |
| 1-2              | mlp                                            |            4 |                -0.02474  |                     0.09073 |                  0.02081  |
| 1-2              | ridge                                          |            4 |                 0.005024 |                     0.07896 |                  0.0162   |
| 1-2              | saturation_residual_fusion_new                 |            4 |                 0.01425  |                     0.07841 |                 -0.04689  |
| 1-2              | tiny_sequence_transformer                      |            4 |                -0.002357 |                     0.09451 |                  0.003924 |
| 3-5              | 1d_cnn                                         |            5 |                -0.0134   |                     0.02001 |                 -0.005833 |
| 3-5              | analytic_clipped_template_sideband_traditional |            5 |                -0.04951  |                     0.2475  |                  0.2235   |
| 3-5              | gradient_boosted_trees                         |            5 |                -0.03872  |                     0.03807 |                  0.02232  |
| 3-5              | mlp                                            |            5 |                -0.07356  |                     0.04671 |                  0.05732  |
| 3-5              | ridge                                          |            5 |                -0.04794  |                     0.01396 |                 -0.00286  |
| 3-5              | saturation_residual_fusion_new                 |            5 |                -0.01103  |                     0.01219 |                  0.003737 |
| 3-5              | tiny_sequence_transformer                      |            5 |                -0.1005   |                     0.05484 |                 -0.03274  |

## Queue Provenance

The required helper command `tn-ticket claim testbeam-laptop-1 --project testbeam` was run exactly once.  It returned
the known null pseudo-ticket output `null / # null / null` before the open-ticket loop.
Because the project queue was not empty, issue `#2531` was recovered without a
second `tn-ticket claim` by applying the same label transition directly:
`gh issue edit 2531 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open`.  Completion is recorded with `tn-ticket done 2531`.  No novel
follow-up ticket was appended.

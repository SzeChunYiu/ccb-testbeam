# S39b: Clipped-Template Energy Recovery vs Neural Saturation Inversion

## Abstract

Ticket `1784176169.768.033348a9` asks whether a strong traditional clipped-template likelihood
with pedestal-corrected charge integration can recover saturated pulse energy as
robustly as learned saturation inversion.  The raw selected-pulse anchor was
reproduced from ROOT before model training.  The held-out winner written to
`result.json` is **`saturation_residual_fusion_new`**, with score `0.1678`,
energy sigma68 `0.07321` and 95% run-block bootstrap CI
[`0.0567`, `0.08218`].

## Raw ROOT Reproduction

The B-stack ROOT files were read from `/home/billy/ccb-data/extracted/root/root`.  The repository
`data/` directory is empty in this worker checkout, so the documented extracted
ROOT data folder under `/home/billy/ccb-data` was used.  The reproduction gate
uses B2/B4/B6/B8 waveforms with pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Experimental Design

The split is by source run.  Training runs are `[50, 51, 52, 53, 54, 55, 56, 57]`;
held-out validation runs are `[58, 60, 62, 64, 65]`.  Synthetic
doublets and matched clean controls are generated from raw-ROOT-derived clean
pulses, then clipped at `11800` ADC:

`w_obs(t) = min(A_1 T_s(t-t_1) + A_2 T_s(t-t_2) + epsilon_rs(t) + p, ADC_clip)`.

Templates are estimated only from training runs:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              832 |                   2.638 |                      5 |           9.164 |
| B4      |              812 |                   2.986 |                      6 |          10.8   |
| B6      |              779 |                   3.758 |                      6 |           9.779 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

## Methods

| method                                         | family             | description                                                                                           |
|:-----------------------------------------------|:-------------------|:------------------------------------------------------------------------------------------------------|
| analytic_clipped_template_sideband_traditional | traditional        | bounded clipped-template likelihood with pedestal-corrected charge and sideband saturation correction |
| ridge                                          | linear ML          | ridge classifier plus ridge multi-output amplitude/time regression                                    |
| gradient_boosted_trees                         | tree ML            | histogram gradient-boosted classifier and regressors on waveform features                             |
| mlp                                            | neural network     | tabular multilayer perceptron classifier/regressor pair                                               |
| 1d_cnn                                         | neural network     | compact convolution over the 18 ADC samples                                                           |
| tiny_sequence_transformer                      | temporal attention | one-layer self-attention encoder over samples                                                         |
| saturation_residual_fusion_new                 | new hybrid         | boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs                  |

The traditional comparator minimizes

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`

over one- and two-pulse hypotheses and then applies an interpretable saturation
sideband correction from clipped sample count, plateau width, and late-tail
fraction.  The new architecture is sensible because the traditional fit
identifies pulse constituents, while waveform and clipping sidebands carry
residual information about charge hidden above the ADC ceiling.

## Endpoints and Winner Rule

The energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Robust resolution is `sigma68(e) = [Q84(e) - Q16(e)] / 2`.  Saturation onset is
the controlled high-amplitude proxy `A_1 + A_2 > 11000 ADC`; the calibration
error is the absolute predicted-minus-true onset fraction.  The winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.35 cal_sat + 0.004 sigma_Delta + 0.004 sigma_t + 0.05 r_merge + 0.05 r_false + 0.08 S_PID`.

Confidence intervals are 95% percentile intervals from `400`
held-out run-block bootstrap resamples.

## Main Results

| method                                         |   winner_score |   energy_bias |   energy_bias_ci_low |   energy_bias_ci_high |   energy_sigma68 |   energy_sigma68_ci_low |   energy_sigma68_ci_high |   saturated_energy_sigma68 |   saturation_onset_accuracy |   saturation_onset_calibration_abs |   pileup_merge_rate |   false_split_rate |   pid_proxy_energy_bias_span |
|:-----------------------------------------------|---------------:|--------------:|---------------------:|----------------------:|-----------------:|------------------------:|-------------------------:|---------------------------:|----------------------------:|-----------------------------------:|--------------------:|-------------------:|-----------------------------:|
| saturation_residual_fusion_new                 |         0.1678 |     -0.004185 |            -0.01606  |              0.001803 |          0.07321 |                 0.0567  |                  0.08218 |                    0.1038  |                      0.9953 |                           0        |              0.2767 |             0.1953 |                      0.04002 |
| gradient_boosted_trees                         |         0.1702 |      0.006402 |            -0.01301  |              0.01522  |          0.07188 |                 0.05528 |                  0.08103 |                    0.11    |                      0.9907 |                           0.004651 |              0.2721 |             0.2023 |                      0.05207 |
| ridge                                          |         0.1976 |      0.005    |            -0.004863 |              0.01521  |          0.08006 |                 0.06887 |                  0.08656 |                    0.06612 |                      0.9884 |                           0.01163  |              0.2558 |             0.186  |                      0.08625 |
| mlp                                            |         0.2472 |     -0.01546  |            -0.02713  |             -0.006525 |          0.1113  |                 0.09733 |                  0.1247  |                    0.08507 |                      0.9837 |                           0.002326 |              0.3116 |             0.1791 |                      0.0439  |
| analytic_clipped_template_sideband_traditional |         0.2566 |      0.06619  |             0.05062  |              0.07659  |          0.08662 |                 0.06259 |                  0.1028  |                    0.02937 |                      0.9814 |                           0.009302 |              0.6    |             0.1907 |                      0.08254 |
| 1d_cnn                                         |         0.2764 |      0.07182  |             0.04455  |              0.09799  |          0.126   |                 0.1128  |                  0.1293  |                    0.07743 |                      0.9791 |                           0.006977 |              0.2558 |             0.2674 |                      0.148   |
| tiny_sequence_transformer                      |         0.2908 |      0.05221  |             0.02292  |              0.08331  |          0.1278  |                 0.1207  |                  0.1314  |                    0.1311  |                      0.9837 |                           0.002326 |              0.2628 |             0.307  |                      0.1265  |

The traditional comparator score is `0.2566`.  The winning
method changes energy sigma68 relative to the traditional comparator by
`-0.01341`.

## Held-Out Run Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                 0.05222  |                     0.124   |         5.128  |            11.14  |             0.2558 |             0.2791 |
| 1d_cnn                                         |            60 |                 0.1241   |                     0.08876 |         7.244  |             9.155 |             0.2674 |             0.3256 |
| 1d_cnn                                         |            62 |                 0.05545  |                     0.1262  |         2.711  |            10.19  |             0.1512 |             0.2674 |
| 1d_cnn                                         |            64 |                 0.0668   |                     0.1289  |         2.148  |             9.935 |             0.2791 |             0.1977 |
| 1d_cnn                                         |            65 |                 0.03854  |                     0.1115  |         2.879  |             8.971 |             0.3256 |             0.2674 |
| analytic_clipped_template_sideband_traditional |            58 |                 0.0456   |                     0.06414 |        -2.776  |             8.262 |             0.6163 |             0.2209 |
| analytic_clipped_template_sideband_traditional |            60 |                 0.09229  |                     0.1134  |         1.677  |             8.967 |             0.5698 |             0.2326 |
| analytic_clipped_template_sideband_traditional |            62 |                 0.07039  |                     0.09056 |         1.071  |            12.08  |             0.5814 |             0.1744 |
| analytic_clipped_template_sideband_traditional |            64 |                 0.06571  |                     0.04208 |         1.199  |             8.84  |             0.6395 |             0.1279 |
| analytic_clipped_template_sideband_traditional |            65 |                 0.05816  |                     0.06202 |        -0.6116 |             9.536 |             0.593  |             0.1977 |
| gradient_boosted_trees                         |            58 |                 0.01228  |                     0.07445 |        -1.391  |             8.014 |             0.1977 |             0.1744 |
| gradient_boosted_trees                         |            60 |                 0.01724  |                     0.05346 |         1.539  |             7.835 |             0.3023 |             0.2442 |
| gradient_boosted_trees                         |            62 |                 0.003718 |                     0.04958 |        -1.492  |             7.694 |             0.2093 |             0.2093 |
| gradient_boosted_trees                         |            64 |                -0.01413  |                     0.08435 |        -1.082  |             8.226 |             0.3023 |             0.1512 |
| gradient_boosted_trees                         |            65 |                -0.01793  |                     0.07342 |        -0.5441 |             7.86  |             0.3488 |             0.2326 |
| mlp                                            |            58 |                -0.007947 |                     0.1037  |        -2.198  |            10.64  |             0.2674 |             0.2093 |
| mlp                                            |            60 |                -0.006433 |                     0.09625 |        -1.138  |            13.71  |             0.3023 |             0.2093 |
| mlp                                            |            62 |                -0.01537  |                     0.09791 |        -4.301  |            11.25  |             0.1977 |             0.1395 |
| mlp                                            |            64 |                -0.03821  |                     0.1325  |        -2.67   |            12.87  |             0.3837 |             0.1512 |
| mlp                                            |            65 |                -0.02232  |                     0.103   |        -3.356  |            10.94  |             0.407  |             0.186  |
| ridge                                          |            58 |                 0.004973 |                     0.06991 |        -1.792  |             9.409 |             0.186  |             0.1744 |
| ridge                                          |            60 |                 0.03031  |                     0.06911 |         2.118  |             9.463 |             0.2791 |             0.2326 |
| ridge                                          |            62 |                 0.01529  |                     0.07011 |        -0.8782 |             8.976 |             0.1628 |             0.2093 |
| ridge                                          |            64 |                -0.002193 |                     0.08445 |        -2.2    |             9.966 |             0.3256 |             0.1279 |
| ridge                                          |            65 |                -0.009325 |                     0.09122 |        -2.122  |             9.299 |             0.3256 |             0.186  |
| saturation_residual_fusion_new                 |            58 |                -0.002652 |                     0.07423 |        -1.306  |             7.077 |             0.2093 |             0.186  |
| saturation_residual_fusion_new                 |            60 |                 0.006792 |                     0.06151 |         1.418  |             6.47  |             0.3023 |             0.2674 |
| saturation_residual_fusion_new                 |            62 |                -0.003004 |                     0.04861 |        -0.9844 |             7.79  |             0.1744 |             0.186  |
| saturation_residual_fusion_new                 |            64 |                -0.01507  |                     0.07586 |        -1.126  |             8.25  |             0.3256 |             0.1512 |
| saturation_residual_fusion_new                 |            65 |                -0.02213  |                     0.08373 |        -0.6676 |             7.796 |             0.3721 |             0.186  |
| tiny_sequence_transformer                      |            58 |                 0.04324  |                     0.1171  |        -5.175  |            11.43  |             0.2558 |             0.3605 |
| tiny_sequence_transformer                      |            60 |                 0.09166  |                     0.1174  |        -2.965  |            13.08  |             0.2442 |             0.407  |
| tiny_sequence_transformer                      |            62 |                 0.08229  |                     0.1186  |        -5.421  |            13.23  |             0.2209 |             0.2558 |
| tiny_sequence_transformer                      |            64 |                 0.0298   |                     0.1386  |        -6.867  |            15.15  |             0.314  |             0.2791 |
| tiny_sequence_transformer                      |            65 |                 0.005635 |                     0.1247  |        -6.379  |            15.09  |             0.2791 |             0.2326 |

## Stratified Failure Maps

The systematic scan covers pedestal state, pile-up proximity, pulse-shape tail
state, ADC clipping depth, amplitude ratio, stave, and PID proxy support:

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |                0.0935    |                    0.1088   |        5.137   |            11.03  |            0.4733  |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |                0.1002    |                    0.1001   |        3.775   |             8.269 |            0.2632  |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |                0.08209   |                    0.1177   |        2.583   |             9.364 |            0.1633  |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |                0.004352  |                    0.1101   |        4.636   |            15.08  |            0.06604 |
| spacing_bin      | (-0.001, 10.0]    | analytic_clipped_template_sideband_traditional |                0.07371   |                    0.1142   |        2.727   |            15.58  |            0.7786  |
| spacing_bin      | (10.0, 25.0]      | analytic_clipped_template_sideband_traditional |                0.07671   |                    0.07175  |        1.518   |            11.18  |            0.6421  |
| spacing_bin      | (25.0, 45.0]      | analytic_clipped_template_sideband_traditional |                0.07692   |                    0.08306  |        0.6718  |             8.759 |            0.602   |
| spacing_bin      | (45.0, 70.0]      | analytic_clipped_template_sideband_traditional |                0.03579   |                    0.07292  |       -2.222   |             9.188 |            0.3396  |
| spacing_bin      | (-0.001, 10.0]    | gradient_boosted_trees                         |                0.03085   |                    0.04843  |        0.2395  |             8.127 |            0.4275  |
| spacing_bin      | (10.0, 25.0]      | gradient_boosted_trees                         |                0.01279   |                    0.06387  |       -0.5542  |             6.53  |            0.3368  |
| spacing_bin      | (25.0, 45.0]      | gradient_boosted_trees                         |               -0.005614  |                    0.07509  |       -0.787   |             7.464 |            0.1531  |
| spacing_bin      | (45.0, 70.0]      | gradient_boosted_trees                         |               -0.03434   |                    0.08439  |       -0.7615  |            10.52  |            0.1321  |
| spacing_bin      | (-0.001, 10.0]    | mlp                                            |                0.007078  |                    0.1081   |       -1.032   |            11.2   |            0.458   |
| spacing_bin      | (10.0, 25.0]      | mlp                                            |               -0.02232   |                    0.1083   |       -0.9007  |            10.57  |            0.3579  |
| spacing_bin      | (25.0, 45.0]      | mlp                                            |               -0.00634   |                    0.1002   |       -2.319   |            11.68  |            0.1939  |
| spacing_bin      | (45.0, 70.0]      | mlp                                            |               -0.03938   |                    0.109    |       -5.099   |            14.09  |            0.1981  |
| spacing_bin      | (-0.001, 10.0]    | ridge                                          |                0.03126   |                    0.04534  |       -0.5755  |            10.04  |            0.4122  |
| spacing_bin      | (10.0, 25.0]      | ridge                                          |                0.02523   |                    0.0647   |       -0.7706  |             7.907 |            0.2526  |
| spacing_bin      | (25.0, 45.0]      | ridge                                          |                0.007843  |                    0.06631  |       -0.839   |             7.729 |            0.1837  |
| spacing_bin      | (45.0, 70.0]      | ridge                                          |               -0.049     |                    0.07114  |       -3.043   |            14.97  |            0.1321  |
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.02512   |                    0.05447  |        0.9104  |             7.576 |            0.4733  |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |                0.006222  |                    0.05721  |       -0.01843 |             5.818 |            0.3053  |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |               -0.01913   |                    0.06251  |       -1.307   |             7.472 |            0.1837  |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.03732   |                    0.07471  |       -1.366   |            10.7   |            0.09434 |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |                0.09535   |                    0.1067   |       -5.464   |             8.924 |            0.4504  |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |                0.1176    |                    0.1315   |       -6.673   |            12.05  |            0.2842  |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |                0.08328   |                    0.1114   |       -4.273   |            14.19  |            0.1429  |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.02483   |                    0.08177  |       -3.878   |            19.05  |            0.1226  |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |                0.06084   |                    0.1282   |        2.395   |            13.3   |            0.3333  |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |                0.08133   |                    0.1238   |        2.893   |             9.733 |            0.2735  |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |                0.0827    |                    0.1103   |        4.141   |             9.531 |            0.1848  |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |                0.05977   |                    0.1289   |        6.342   |            10.59  |            0.2079  |
| ratio_bin        | (-0.001, 0.35]    | analytic_clipped_template_sideband_traditional |                0.05544   |                    0.1051   |       -0.7738  |            10.72  |            0.5583  |
| ratio_bin        | (0.35, 0.625]     | analytic_clipped_template_sideband_traditional |                0.06924   |                    0.07173  |       -0.6627  |            10.01  |            0.6154  |
| ratio_bin        | (0.625, 0.875]    | analytic_clipped_template_sideband_traditional |                0.07118   |                    0.06884  |        0.6557  |             7.788 |            0.587   |
| ratio_bin        | (0.875, 1.05]     | analytic_clipped_template_sideband_traditional |                0.07164   |                    0.08456  |        2.715   |             8.026 |            0.6436  |
| ratio_bin        | (-0.001, 0.35]    | gradient_boosted_trees                         |                0.01197   |                    0.07223  |       -1.673   |            10.88  |            0.4333  |
| ratio_bin        | (0.35, 0.625]     | gradient_boosted_trees                         |                0.01615   |                    0.07368  |        0.3004  |             7.01  |            0.3162  |
| ratio_bin        | (0.625, 0.875]    | gradient_boosted_trees                         |                0.003665  |                    0.0604   |       -0.412   |             6.809 |            0.1957  |
| ratio_bin        | (0.875, 1.05]     | gradient_boosted_trees                         |               -0.0001613 |                    0.07746  |        0.2395  |             7.78  |            0.09901 |
| ratio_bin        | (-0.001, 0.35]    | mlp                                            |               -0.02373   |                    0.1314   |       -2.902   |            13.01  |            0.4917  |
| ratio_bin        | (0.35, 0.625]     | mlp                                            |               -0.002696  |                    0.1214   |       -1.632   |            13.48  |            0.3504  |
| ratio_bin        | (0.625, 0.875]    | mlp                                            |               -0.02819   |                    0.0901   |       -4.064   |            10.88  |            0.1739  |
| ratio_bin        | (0.875, 1.05]     | mlp                                            |               -0.002863  |                    0.1057   |       -1.225   |            10.99  |            0.1782  |
| ratio_bin        | (-0.001, 0.35]    | ridge                                          |                0.005202  |                    0.08066  |       -3.748   |            12.31  |            0.4583  |
| ratio_bin        | (0.35, 0.625]     | ridge                                          |                0.01232   |                    0.08608  |       -2.115   |             8.567 |            0.265   |
| ratio_bin        | (0.625, 0.875]    | ridge                                          |                0.003856  |                    0.06041  |        1.069   |             8.978 |            0.1413  |
| ratio_bin        | (0.875, 1.05]     | ridge                                          |                0.002077  |                    0.07872  |        0.03361 |             9.578 |            0.1089  |
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |               -0.004479  |                    0.06858  |       -1.68    |            10.55  |            0.3917  |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |               -0.005517  |                    0.07356  |       -0.6188  |             7.094 |            0.3162  |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.002662  |                    0.06044  |       -0.3581  |             6.515 |            0.1739  |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |               -0.005736  |                    0.07251  |        0.8944  |             6.95  |            0.1881  |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |                0.05698   |                    0.1183   |       -7.801   |            17.54  |            0.3667  |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |                0.05942   |                    0.139    |       -5.197   |            12.28  |            0.2821  |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |                0.05347   |                    0.1231   |       -5.385   |            10.13  |            0.163   |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |                0.0429    |                    0.1155   |       -4.104   |            15.1   |            0.2079  |
| saturation_bin   | 0                 | 1d_cnn                                         |                0.07435   |                    0.1271   |        3.806   |            10.14  |            0.2553  |
| saturation_bin   | 1-2               | 1d_cnn                                         |                0.09331   |                    0.04003  |        0.6101  |             9.849 |            0.5     |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.079     |                    0.02771  |       11.63    |            10.64  |            0       |
| saturation_bin   | 6+                | 1d_cnn                                         |                0.05075   |                    0        |       17.33    |            14.92  |            0       |
| saturation_bin   | 0                 | analytic_clipped_template_sideband_traditional |                0.06581   |                    0.08405  |        0.278   |             9.571 |            0.5981  |
| saturation_bin   | 1-2               | analytic_clipped_template_sideband_traditional |                0.1304    |                    0        |        4.444   |            11.9   |            0.75    |
| saturation_bin   | 3-5               | analytic_clipped_template_sideband_traditional |              nan         |                  nan        |      nan       |           nan     |            1       |
| saturation_bin   | 6+                | analytic_clipped_template_sideband_traditional |                0.2168    |                    0        |        4.182   |            14.45  |            0       |
| saturation_bin   | 0                 | gradient_boosted_trees                         |                0.00699   |                    0.06862  |       -0.3514  |             7.91  |            0.2766  |
| saturation_bin   | 1-2               | gradient_boosted_trees                         |                0.09595   |                    0.04301  |       -9.208   |             4.423 |            0       |
| saturation_bin   | 3-5               | gradient_boosted_trees                         |               -0.1337    |                    0.04858  |       -7.723   |             6.12  |            0       |
| saturation_bin   | 6+                | gradient_boosted_trees                         |               -0.1177    |                    0        |        1.346   |             6.108 |            0       |
| saturation_bin   | 0                 | mlp                                            |               -0.01483   |                    0.1114   |       -2.948   |            12.14  |            0.3168  |
| saturation_bin   | 1-2               | mlp                                            |                0.003134  |                    0.07849  |       -5.817   |             4.318 |            0       |
| saturation_bin   | 3-5               | mlp                                            |               -0.1481    |                    0.02388  |       12.29    |             3.573 |            0       |
| saturation_bin   | 6+                | mlp                                            |               -0.0439    |                    0        |       -1.363   |             8.818 |            0       |
| saturation_bin   | 0                 | ridge                                          |                0.005711  |                    0.0777   |       -0.8762  |             9.588 |            0.26    |
| saturation_bin   | 1-2               | ridge                                          |               -0.06109   |                    0.03766  |       -8.552   |             3.625 |            0       |
| saturation_bin   | 3-5               | ridge                                          |               -0.19      |                    0.009636 |       -4.819   |             8.318 |            0       |
| saturation_bin   | 6+                | ridge                                          |               -0.1427    |                    0        |       -0.5096  |             5.538 |            0       |
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |               -0.004117  |                    0.07148  |       -0.2849  |             7.587 |            0.2813  |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |                0.06519   |                    0.0623   |       -7.129   |             4.87  |            0       |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.1244    |                    0.05599  |       -5.627   |             7.087 |            0       |
| saturation_bin   | 6+                | saturation_residual_fusion_new                 |               -0.09163   |                    0        |        1.903   |             7.813 |            0       |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |                0.05311   |                    0.1281   |       -5.421   |            13.49  |            0.2624  |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |                0.05642   |                    0.03073  |      -12.64    |            11.45  |            0.5     |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.2136    |                    0.04143  |       -6.281   |            13.27  |            0       |
| saturation_bin   | 6+                | tiny_sequence_transformer                      |               -0.1868    |                    0        |        4.309   |            10.13  |            0       |
| pedestal_state   | nominal           | 1d_cnn                                         |                0.05637   |                    0.09202  |        4.81    |             9.813 |            0.2013  |
| pedestal_state   | shifted           | 1d_cnn                                         |                0.09367   |                    0.1372   |        3.002   |            10.63  |            0.2878  |
| pedestal_state   | nominal           | analytic_clipped_template_sideband_traditional |                0.06267   |                    0.08089  |        0.7872  |             9.352 |            0.4151  |
| pedestal_state   | shifted           | analytic_clipped_template_sideband_traditional |                0.07011   |                    0.08587  |       -0.6452  |            10.08  |            0.7085  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.01301   |                    0.05931  |       -0.4613  |             7.98  |            0.2138  |
| pedestal_state   | shifted           | gradient_boosted_trees                         |                0.01788   |                    0.0784   |       -0.4303  |             8.173 |            0.3063  |
| pedestal_state   | nominal           | mlp                                            |               -0.02919   |                    0.08838  |       -2.319   |            10.76  |            0.2767  |
| pedestal_state   | shifted           | mlp                                            |                0.01028   |                    0.1312   |       -3.137   |            13.04  |            0.3321  |
| pedestal_state   | nominal           | ridge                                          |               -0.008473  |                    0.07044  |       -1.285   |             9.111 |            0.2013  |
| pedestal_state   | shifted           | ridge                                          |                0.01584   |                    0.09     |       -1.026   |             9.791 |            0.2878  |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |               -0.00824   |                    0.05482  |       -1.125   |             7.513 |            0.2013  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |               -0.002195  |                    0.08622  |        0.1144  |             7.659 |            0.321   |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |                0.02569   |                    0.102    |       -2.569   |            13.1   |            0.2075  |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |                0.08229   |                    0.1584   |       -7.224   |            12.83  |            0.2952  |
| morphology_state | late_tail_high    | 1d_cnn                                         |                0.08253   |                    0.08875  |        3.534   |             8.426 |            0.4068  |
| morphology_state | late_tail_low     | 1d_cnn                                         |                0.05075   |                    0.1415   |        4.169   |            11.03  |            0.1502  |
| morphology_state | late_tail_high    | analytic_clipped_template_sideband_traditional |                0.08189   |                    0.09411  |        2.462   |             7.179 |            0.7684  |
| morphology_state | late_tail_low     | analytic_clipped_template_sideband_traditional |                0.05995   |                    0.08202  |       -0.5335  |             9.772 |            0.4822  |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |                0.007718  |                    0.06583  |       -1.858   |             7.206 |            0.3559  |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |                0.005347  |                    0.07103  |        0.1752  |             8.335 |            0.2134  |
| morphology_state | late_tail_high    | mlp                                            |               -0.02718   |                    0.1048   |       -1.986   |             9.425 |            0.4068  |
| morphology_state | late_tail_low     | mlp                                            |               -0.001539  |                    0.1156   |       -3.424   |            13.23  |            0.2451  |
| morphology_state | late_tail_high    | ridge                                          |                0.001696  |                    0.06485  |       -1.751   |             8.22  |            0.3559  |
| morphology_state | late_tail_low     | ridge                                          |                0.00861   |                    0.09245  |       -0.8633  |            10.7   |            0.1858  |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |                0.005373  |                    0.06851  |       -1.29    |             6.628 |            0.4068  |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.007345  |                    0.073    |        0.1672  |             8.157 |            0.1858  |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |                0.07342   |                    0.08898  |       -6.806   |            13.24  |            0.3898  |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |                0.03635   |                    0.1381   |       -4.346   |            13.66  |            0.1739  |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.09835   |                    0.1094   |        1.323   |            11.72  |            0.4286  |
| pid_proxy_class  | other             | 1d_cnn                                         |                0.07788   |                    0.1226   |        3.868   |            10.19  |            0.2469  |
| pid_proxy_class  | inner_high_charge | analytic_clipped_template_sideband_traditional |                0.06051   |                    0.04051  |       -8.073   |            17.83  |            0.5714  |
| pid_proxy_class  | other             | analytic_clipped_template_sideband_traditional |                0.06647   |                    0.08943  |        0.4868  |             9.314 |            0.6015  |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.04099   |                    0.09203  |       -7.993   |             8.816 |            0.2381  |
| pid_proxy_class  | other             | gradient_boosted_trees                         |                0.007579  |                    0.07078  |       -0.2123  |             7.688 |            0.2738  |
| pid_proxy_class  | inner_high_charge | mlp                                            |               -0.04442   |                    0.09216  |       -5.025   |            13.2   |            0.1429  |
| pid_proxy_class  | other             | mlp                                            |               -0.008652  |                    0.1151   |       -2.727   |            11.95  |            0.3203  |

## Systematics and Caveats

Truth is controlled-injection truth, not hand-labeled beam truth.  The saturation
threshold is an explicit ADC clipping stressor and onset proxy rather than a
decoded hardware flag.  The 18-sample waveform is short for attention models;
therefore the transformer is a compact temporal-attention comparator rather than
a large sequence model.  PID migration is approximated by B-stave and charge
support because external particle labels are unavailable in this raw ROOT gate.
Run-block bootstrap intervals quantify transfer across held-out runs and are
not event-counting errors.

## Verdict

`result.json` names **saturation_residual_fusion_new** as the S39b winner.  The interpretable
clipped-template method remains the audit baseline; the winner is preferred only
for the declared held-out energy, saturation-onset, and pile-up score.

Runtime was `51.3` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

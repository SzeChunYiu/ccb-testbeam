# S36a: Clipped-Pulse Saturation Onset Shape Recovery Benchmark

## Abstract

Ticket `1784064851.786.76994f64` asks whether clipped waveform morphology can recover
pre-saturation amplitude and onset timing without leaking run identity, and
whether that improves energy calibration near the saturation boundary.  The
worker is `testbeam-laptop-2`.  The held-out winner written to `result.json` is
**`saturation_residual_fusion_new`**, selected by the registered S36a composite endpoint score.  Its
energy residual sigma68 is `0.06887` with 95%
run-block bootstrap CI [`0.06446`,
`0.07792`], onset timing sigma68 is
`5.613` ns, saturation-onset AUC is
`1`, and median normalized shape-reconstruction
RMSE is `0.1422`.

## Raw ROOT Reproduction Gate

Raw B-stack ROOT files are read from `/home/billy/.tb-workers/testbeam-laptop-2/data/root/root`.  The branch
`h101/HRDv` is reshaped into `(event, channel, sample)` with 18 samples.  The
selected-pulse anchor is reproduced directly from B2/B4/B6/B8 channels using

`b_ec = median_{t in {0,1,2,3}} x_ect`,

`A_ec = max_t(x_ect - b_ec)`,

`N = sum_ec 1[A_ec > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split, Truth Construction, and Leakage Control

Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`; no event from a held-out run is used to
fit templates or model parameters.  Clean raw-ROOT pulses are aligned into
stave-specific templates

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              896 |                   2.711 |                      5 |           9.095 |
| B4      |              868 |                   3.016 |                      6 |          10.82  |
| B6      |              835 |                   3.761 |                      6 |           9.793 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

Controlled clipped examples are generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

followed by the observation operator `w_obs(t)=min(w(t), 11800)`.
Clean single-pulse controls are generated from the same run distribution and
clipped with the same rule.

## Methods

| method                                         | family         | description                                                                          |
|:-----------------------------------------------|:---------------|:-------------------------------------------------------------------------------------|
| analytic_clipped_template_sideband_traditional | traditional    | censored template fit with deterministic clipped-sample sideband correction          |
| ridge                                          | linear ML      | ridge classifier plus multi-output ridge regression                                  |
| gradient_boosted_trees                         | tree ML        | histogram gradient-boosted classifier and regressors                                 |
| mlp                                            | neural network | tabular multilayer perceptron classifier/regressor pair                              |
| 1d_cnn                                         | neural network | compact one-dimensional CNN over 18 ADC samples                                      |
| tiny_sequence_transformer                      | sequence NN    | one-layer self-attention waveform encoder                                            |
| saturation_residual_fusion_new                 | new hybrid     | boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs |

The new architecture is `saturation_residual_fusion_new`.  It is included
because saturation onset is a hybrid inverse problem: template parameters carry
physical identifiability, while clipped-sample count, plateau width, tail
fraction, and waveform residuals carry information hidden above the ADC ceiling.

## Endpoints and Equations

Energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Onset timing error is

`e_t = 10 ns (hat t_1 - t_1)`.

Shape reconstruction compares the predicted unclipped waveform `hat w(t)` with
the injected pre-clipping waveform:

`RMSE_shape = sqrt(mean_t[(hat w(t)-w(t))^2]) / max(max_t w(t)-median_{0:3} w(t), 1)`.

Saturation-onset classification uses the held-out label
`1[n_clip > 0]` and the method-specific onset score
`(hat A_1 + hat A_2)/11800 + 0.05 s_overlap`.  AUC is the normalized
Mann-Whitney statistic.  Robust resolution is
`sigma68(e)=[Q84(e)-Q16(e)]/2`.  Confidence intervals are 95% percentile
intervals from `400` held-out run-block
bootstrap resamples.

The registered S36a score is

`C = sigma_E + 0.20|bias_E| + 0.004 sigma_t + 0.16 RMSE_shape + 0.10(1-AUC) + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`.

## Overall Results

| method                                         |   winner_score |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   onset_timing_sigma68_ns |   saturation_onset_auc |   shape_reconstruction_rmse |   pileup_miss_rate |   false_split_rate |   pedestal_shift_false_split_span |   pid_energy_bias_span |
|:-----------------------------------------------|---------------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|--------------------------:|-----------------------:|----------------------------:|-------------------:|-------------------:|----------------------------------:|-----------------------:|
| saturation_residual_fusion_new                 |         0.1426 |              -0.002053 |                   0.06887 |                          0.06446 |                           0.07792 |                     5.613 |                 1      |                      0.1422 |             0.2682 |             0.2227 |                          0.03011  |               0.01443  |
| gradient_boosted_trees                         |         0.1471 |              -0.003679 |                   0.07211 |                          0.06675 |                           0.07589 |                     5.906 |                 0.9995 |                      0.1448 |             0.275  |             0.2091 |                          0.008527 |               0.03205  |
| ridge                                          |         0.1582 |               0.002529 |                   0.0763  |                          0.069   |                           0.07937 |                     6.815 |                 0.9992 |                      0.1502 |             0.2932 |             0.2068 |                          0.01461  |               0.04772  |
| mlp                                            |         0.1957 |               0.007158 |                   0.08525 |                          0.07461 |                           0.1088  |                    10.98  |                 0.9998 |                      0.1821 |             0.3818 |             0.175  |                          0.07181  |               0.03001  |
| 1d_cnn                                         |         0.1975 |               0.0261   |                   0.09811 |                          0.09055 |                           0.123   |                     7.83  |                 0.9979 |                      0.1654 |             0.2591 |             0.3114 |                          0.03362  |               0.0626   |
| tiny_sequence_transformer                      |         0.2107 |              -0.02313  |                   0.09756 |                          0.08874 |                           0.1068  |                    11.2   |                 0.9985 |                      0.1773 |             0.3682 |             0.2227 |                          0.01874  |               0.05127  |
| analytic_clipped_template_sideband_traditional |         0.2317 |               0.06333  |                   0.0932  |                          0.07746 |                           0.1011  |                     6.507 |                 0.6777 |                      0.1214 |             0.5386 |             0.2409 |                          0.1072   |               0.007052 |

The traditional comparator has score `0.2317` and energy
sigma68 `0.0932`.  The selected winner changes
energy sigma68 by `-0.02432`
and shape RMSE by `0.02084`.

## Endpoint Table with CIs

| method                                         |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   onset_timing_sigma68_ns |   onset_timing_sigma68_ns_ci_low |   onset_timing_sigma68_ns_ci_high |   saturation_onset_auc |   saturation_onset_auc_ci_low |   saturation_onset_auc_ci_high |   shape_reconstruction_rmse |   shape_reconstruction_rmse_ci_low |   shape_reconstruction_rmse_ci_high |
|:-----------------------------------------------|--------------------------:|---------------------------------:|----------------------------------:|--------------------------:|---------------------------------:|----------------------------------:|-----------------------:|------------------------------:|-------------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|
| saturation_residual_fusion_new                 |                   0.06887 |                          0.06446 |                           0.07792 |                     5.613 |                            4.961 |                             6.092 |                 1      |                        1      |                         1      |                      0.1422 |                             0.1338 |                              0.1482 |
| gradient_boosted_trees                         |                   0.07211 |                          0.06675 |                           0.07589 |                     5.906 |                            5.268 |                             6.588 |                 0.9995 |                        0.9975 |                         1      |                      0.1448 |                             0.1367 |                              0.1552 |
| ridge                                          |                   0.0763  |                          0.069   |                           0.07937 |                     6.815 |                            5.902 |                             7.439 |                 0.9992 |                        0.9966 |                         1      |                      0.1502 |                             0.145  |                              0.1596 |
| mlp                                            |                   0.08525 |                          0.07461 |                           0.1088  |                    10.98  |                            9.85  |                            12.32  |                 0.9998 |                        0.9991 |                         1      |                      0.1821 |                             0.1635 |                              0.1919 |
| analytic_clipped_template_sideband_traditional |                   0.0932  |                          0.07746 |                           0.1011  |                     6.507 |                            5.709 |                             6.943 |                 0.6777 |                        0.4046 |                         0.9989 |                      0.1214 |                             0.1173 |                              0.1253 |
| tiny_sequence_transformer                      |                   0.09756 |                          0.08874 |                           0.1068  |                    11.2   |                           10.27  |                            12.21  |                 0.9985 |                        0.9949 |                         1      |                      0.1773 |                             0.1668 |                              0.1829 |
| 1d_cnn                                         |                   0.09811 |                          0.09055 |                           0.123   |                     7.83  |                            7.371 |                             8.825 |                 0.9979 |                        0.9932 |                         1      |                      0.1654 |                             0.1541 |                              0.177  |

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                0.02337   |                     0.09596 |       -2.784   |            11.01  |             0.1705 |             0.4091 |
| 1d_cnn                                         |            60 |                0.02735   |                     0.1295  |       -2.897   |            11.46  |             0.2614 |             0.3068 |
| 1d_cnn                                         |            62 |                0.04391   |                     0.08562 |       -0.5816  |             9.527 |             0.25   |             0.2841 |
| 1d_cnn                                         |            64 |                0.007423  |                     0.1042  |       -1.748   |             9.373 |             0.3295 |             0.2386 |
| 1d_cnn                                         |            65 |                0.02258   |                     0.08907 |       -1.285   |             9.824 |             0.2841 |             0.3182 |
| analytic_clipped_template_sideband_traditional |            58 |                0.06571   |                     0.09521 |        1.127   |            14.29  |             0.6136 |             0.3409 |
| analytic_clipped_template_sideband_traditional |            60 |                0.07803   |                     0.08493 |        1.35    |            11.06  |             0.5341 |             0.2159 |
| analytic_clipped_template_sideband_traditional |            62 |                0.07497   |                     0.06791 |        0.8729  |             8.867 |             0.5455 |             0.2159 |
| analytic_clipped_template_sideband_traditional |            64 |                0.04995   |                     0.09103 |        0.7278  |             6.811 |             0.5568 |             0.2045 |
| analytic_clipped_template_sideband_traditional |            65 |                0.05723   |                     0.07897 |       -0.5519  |            10.72  |             0.4432 |             0.2273 |
| gradient_boosted_trees                         |            58 |                0.009615  |                     0.07211 |       -1.743   |             7.256 |             0.2273 |             0.2727 |
| gradient_boosted_trees                         |            60 |               -0.004656  |                     0.07042 |        0.1291  |             7.93  |             0.2386 |             0.1932 |
| gradient_boosted_trees                         |            62 |               -0.006042  |                     0.06126 |        1.477   |             7.508 |             0.25   |             0.2614 |
| gradient_boosted_trees                         |            64 |                0.01049   |                     0.0732  |        0.3738  |             7.933 |             0.3409 |             0.1364 |
| gradient_boosted_trees                         |            65 |               -0.02801   |                     0.06471 |        0.6826  |             9.128 |             0.3182 |             0.1818 |
| mlp                                            |            58 |                0.009943  |                     0.1234  |       -2.605   |            12.78  |             0.375  |             0.2159 |
| mlp                                            |            60 |                0.01411   |                     0.09336 |       -0.3399  |            13.27  |             0.3409 |             0.25   |
| mlp                                            |            62 |                0.01495   |                     0.06892 |       -0.971   |            11.61  |             0.3295 |             0.1818 |
| mlp                                            |            64 |               -0.003869  |                     0.07558 |       -1.009   |            12.66  |             0.4432 |             0.1023 |
| mlp                                            |            65 |               -0.01428   |                     0.09574 |       -5.002   |            11.76  |             0.4205 |             0.125  |
| ridge                                          |            58 |                0.01732   |                     0.06242 |       -1.084   |             9.765 |             0.2386 |             0.2955 |
| ridge                                          |            60 |                0.01943   |                     0.07613 |       -0.1519  |             9.434 |             0.2159 |             0.2273 |
| ridge                                          |            62 |                1.759e-05 |                     0.0773  |        1.259   |             8.021 |             0.3068 |             0.2614 |
| ridge                                          |            64 |               -0.009471  |                     0.07059 |       -0.07332 |             7.583 |             0.3523 |             0.1364 |
| ridge                                          |            65 |               -0.02468   |                     0.06756 |       -3.108   |             9.217 |             0.3523 |             0.1136 |
| saturation_residual_fusion_new                 |            58 |                0.01545   |                     0.07377 |       -1.032   |             6.768 |             0.25   |             0.2614 |
| saturation_residual_fusion_new                 |            60 |               -0.0008315 |                     0.07952 |       -0.09954 |             8.249 |             0.2273 |             0.2727 |
| saturation_residual_fusion_new                 |            62 |               -0.003975  |                     0.05863 |        1.212   |             6.877 |             0.2614 |             0.2727 |
| saturation_residual_fusion_new                 |            64 |                0.00204   |                     0.06714 |        0.6607  |             7.853 |             0.3295 |             0.1364 |
| saturation_residual_fusion_new                 |            65 |               -0.01337   |                     0.05941 |       -0.9758  |             8.068 |             0.2727 |             0.1705 |
| tiny_sequence_transformer                      |            58 |               -0.01635   |                     0.07288 |       -6.179   |            13.89  |             0.3295 |             0.3068 |
| tiny_sequence_transformer                      |            60 |               -0.01461   |                     0.1059  |       -5.592   |            15.01  |             0.375  |             0.2159 |
| tiny_sequence_transformer                      |            62 |               -0.03095   |                     0.09122 |       -6.195   |            10.38  |             0.3068 |             0.2273 |
| tiny_sequence_transformer                      |            64 |               -0.008492  |                     0.08821 |       -7.312   |            14.29  |             0.4545 |             0.1932 |
| tiny_sequence_transformer                      |            65 |               -0.04566   |                     0.1065  |       -7.813   |            14.43  |             0.375  |             0.1705 |

## Saturation-Depth and Systematic Strata

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class.

| stratum        | value          | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:---------------|:---------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin    | (-0.001, 10.0] | 1d_cnn                                         |                0.04506   |                     0.1004  |        0.4343  |            13.06  |             0.3732 |
| spacing_bin    | (10.0, 25.0]   | 1d_cnn                                         |                0.04114   |                     0.09862 |       -1.669   |             9.073 |             0.2791 |
| spacing_bin    | (25.0, 45.0]   | 1d_cnn                                         |                0.01314   |                     0.09577 |       -2.824   |             7.668 |             0.2124 |
| spacing_bin    | (45.0, 70.0]   | 1d_cnn                                         |                0.004305  |                     0.1005  |       -1.709   |            12.45  |             0.1313 |
| spacing_bin    | (-0.001, 10.0] | analytic_clipped_template_sideband_traditional |                0.08817   |                     0.09728 |        1.001   |            16.41  |             0.6549 |
| spacing_bin    | (10.0, 25.0]   | analytic_clipped_template_sideband_traditional |                0.08578   |                     0.08947 |        2.659   |            10.43  |             0.6163 |
| spacing_bin    | (25.0, 45.0]   | analytic_clipped_template_sideband_traditional |                0.06669   |                     0.07364 |        0.7727  |            10.22  |             0.4513 |
| spacing_bin    | (45.0, 70.0]   | analytic_clipped_template_sideband_traditional |                0.02872   |                     0.09809 |       -1.984   |            10.42  |             0.404  |
| spacing_bin    | (-0.001, 10.0] | gradient_boosted_trees                         |                0.02151   |                     0.05741 |        1.477   |             7.376 |             0.3803 |
| spacing_bin    | (10.0, 25.0]   | gradient_boosted_trees                         |                0.01953   |                     0.0552  |        0.6578  |             6.831 |             0.2791 |
| spacing_bin    | (25.0, 45.0]   | gradient_boosted_trees                         |               -0.02965   |                     0.0639  |       -0.8375  |             8.541 |             0.2389 |
| spacing_bin    | (45.0, 70.0]   | gradient_boosted_trees                         |               -0.01759   |                     0.07708 |       -1.252   |             9.597 |             0.1616 |
| spacing_bin    | (-0.001, 10.0] | mlp                                            |                0.03459   |                     0.09455 |        2.632   |            12.42  |             0.5    |
| spacing_bin    | (10.0, 25.0]   | mlp                                            |                0.01502   |                     0.07915 |       -2.302   |            10.33  |             0.4419 |
| spacing_bin    | (25.0, 45.0]   | mlp                                            |               -0.01252   |                     0.1     |       -3.183   |            11.89  |             0.3363 |
| spacing_bin    | (45.0, 70.0]   | mlp                                            |               -0.01611   |                     0.09476 |       -4.078   |            15.16  |             0.2121 |
| spacing_bin    | (-0.001, 10.0] | ridge                                          |                0.01943   |                     0.06983 |        0.3317  |             9.414 |             0.3732 |
| spacing_bin    | (10.0, 25.0]   | ridge                                          |                0.02684   |                     0.06211 |        0.1353  |             6.564 |             0.3372 |
| spacing_bin    | (25.0, 45.0]   | ridge                                          |               -0.002874  |                     0.06811 |       -0.5337  |             7.739 |             0.2655 |
| spacing_bin    | (45.0, 70.0]   | ridge                                          |               -0.03021   |                     0.07609 |       -2.867   |            12.89  |             0.1717 |
| spacing_bin    | (-0.001, 10.0] | saturation_residual_fusion_new                 |                0.02269   |                     0.06878 |        0.9569  |             7.384 |             0.3803 |
| spacing_bin    | (10.0, 25.0]   | saturation_residual_fusion_new                 |                0.01568   |                     0.05798 |        0.8895  |             6.324 |             0.314  |
| spacing_bin    | (25.0, 45.0]   | saturation_residual_fusion_new                 |               -0.01501   |                     0.05673 |       -0.9523  |             7.25  |             0.2301 |
| spacing_bin    | (45.0, 70.0]   | saturation_residual_fusion_new                 |               -0.02362   |                     0.0813  |       -0.797   |             8.538 |             0.1111 |
| spacing_bin    | (-0.001, 10.0] | tiny_sequence_transformer                      |                0.01066   |                     0.06021 |       -5.456   |             8.94  |             0.5141 |
| spacing_bin    | (10.0, 25.0]   | tiny_sequence_transformer                      |                0.02157   |                     0.06448 |       -6.115   |            10.49  |             0.5    |
| spacing_bin    | (25.0, 45.0]   | tiny_sequence_transformer                      |               -0.04707   |                     0.08261 |       -6.953   |            14.22  |             0.3097 |
| spacing_bin    | (45.0, 70.0]   | tiny_sequence_transformer                      |               -0.0856    |                     0.1165  |       -8.993   |            19.09  |             0.1111 |
| ratio_bin      | (-0.001, 0.35] | 1d_cnn                                         |                0.002796  |                     0.09538 |       -3.347   |            11.39  |             0.3645 |
| ratio_bin      | (0.35, 0.625]  | 1d_cnn                                         |                0.03593   |                     0.1052  |       -1.819   |            10.63  |             0.2377 |
| ratio_bin      | (0.625, 0.875] | 1d_cnn                                         |                0.036     |                     0.1001  |       -2.877   |            10.61  |             0.2    |
| ratio_bin      | (0.875, 1.05]  | 1d_cnn                                         |                0.02735   |                     0.074   |       -0.3406  |             9.424 |             0.2358 |
| ratio_bin      | (-0.001, 0.35] | analytic_clipped_template_sideband_traditional |                0.04888   |                     0.1198  |       -3.053   |            13.48  |             0.5888 |
| ratio_bin      | (0.35, 0.625]  | analytic_clipped_template_sideband_traditional |                0.06744   |                     0.1003  |       -0.437   |            10.99  |             0.5082 |
| ratio_bin      | (0.625, 0.875] | analytic_clipped_template_sideband_traditional |                0.06432   |                     0.06369 |        1.441   |             9.162 |             0.5714 |
| ratio_bin      | (0.875, 1.05]  | analytic_clipped_template_sideband_traditional |                0.07497   |                     0.0833  |        1.297   |             7.725 |             0.4906 |
| ratio_bin      | (-0.001, 0.35] | gradient_boosted_trees                         |               -0.007766  |                     0.08276 |       -3.201   |            11.03  |             0.4486 |
| ratio_bin      | (0.35, 0.625]  | gradient_boosted_trees                         |                0.003215  |                     0.07231 |       -0.2649  |             7.815 |             0.2951 |
| ratio_bin      | (0.625, 0.875] | gradient_boosted_trees                         |               -0.002763  |                     0.07451 |        0.6668  |             7.712 |             0.1905 |
| ratio_bin      | (0.875, 1.05]  | gradient_boosted_trees                         |               -0.005424  |                     0.0613  |        1.64    |             7.135 |             0.1604 |
| ratio_bin      | (-0.001, 0.35] | mlp                                            |                0.02441   |                     0.08585 |       -2.559   |            13.43  |             0.5234 |
| ratio_bin      | (0.35, 0.625]  | mlp                                            |                0.008619  |                     0.08776 |       -4.864   |            11.6   |             0.3525 |
| ratio_bin      | (0.625, 0.875] | mlp                                            |               -0.003106  |                     0.08632 |       -2.319   |            13.38  |             0.3714 |
| ratio_bin      | (0.875, 1.05]  | mlp                                            |                0.002965  |                     0.07822 |        1.406   |            11.71  |             0.283  |
| ratio_bin      | (-0.001, 0.35] | ridge                                          |                0.01104   |                     0.07135 |       -5.921   |            11.83  |             0.4579 |
| ratio_bin      | (0.35, 0.625]  | ridge                                          |                0.005156  |                     0.07012 |       -1.351   |             8.31  |             0.2787 |
| ratio_bin      | (0.625, 0.875] | ridge                                          |                0.01076   |                     0.07684 |        0.7526  |             7.993 |             0.2476 |
| ratio_bin      | (0.875, 1.05]  | ridge                                          |               -0.005959  |                     0.07463 |        1.897   |             8.307 |             0.1887 |
| ratio_bin      | (-0.001, 0.35] | saturation_residual_fusion_new                 |                0.01568   |                     0.07425 |       -3.703   |            10.65  |             0.4486 |
| ratio_bin      | (0.35, 0.625]  | saturation_residual_fusion_new                 |                4.248e-05 |                     0.06902 |       -0.2097  |             7.464 |             0.2541 |
| ratio_bin      | (0.625, 0.875] | saturation_residual_fusion_new                 |               -0.003371  |                     0.07661 |        0.8948  |             7.576 |             0.2    |
| ratio_bin      | (0.875, 1.05]  | saturation_residual_fusion_new                 |               -0.0029    |                     0.05572 |        0.9264  |             6.435 |             0.1698 |
| ratio_bin      | (-0.001, 0.35] | tiny_sequence_transformer                      |               -0.04575   |                     0.08493 |       -7.896   |            15.9   |             0.4953 |
| ratio_bin      | (0.35, 0.625]  | tiny_sequence_transformer                      |               -0.01086   |                     0.09062 |       -8.089   |            13.35  |             0.2951 |
| ratio_bin      | (0.625, 0.875] | tiny_sequence_transformer                      |                0.009079  |                     0.09981 |       -6.383   |            13.05  |             0.3714 |
| ratio_bin      | (0.875, 1.05]  | tiny_sequence_transformer                      |               -0.03161   |                     0.1019  |       -4.727   |            11.6   |             0.3208 |
| saturation_bin | 0              | 1d_cnn                                         |                0.02534   |                     0.09819 |       -1.632   |            10.34  |             0.2633 |
| saturation_bin | 1-2            | 1d_cnn                                         |               -0.00495   |                     0.03207 |       -6.061   |             5.485 |             0      |
| saturation_bin | 3-5            | 1d_cnn                                         |                0.047     |                     0.06804 |       -2.697   |            15.63  |             0      |
| saturation_bin | 0              | analytic_clipped_template_sideband_traditional |                0.06331   |                     0.0931  |        0.777   |            10.25  |             0.5381 |
| saturation_bin | 1-2            | analytic_clipped_template_sideband_traditional |                0.08182   |                     0.0602  |       -3.892   |             7.6   |             0.3333 |
| saturation_bin | 3-5            | analytic_clipped_template_sideband_traditional |                0.2472    |                     0       |        3.388   |            11.05  |             0.75   |
| saturation_bin | 0              | gradient_boosted_trees                         |               -0.003436  |                     0.07213 |        0.2026  |             8.202 |             0.2794 |
| saturation_bin | 1-2            | gradient_boosted_trees                         |               -0.05179   |                     0.04755 |       -6.518   |             4.725 |             0      |
| saturation_bin | 3-5            | gradient_boosted_trees                         |               -0.05831   |                     0.0475  |       -2.063   |             3.73  |             0      |
| saturation_bin | 0              | mlp                                            |                0.008633  |                     0.08833 |       -2.055   |            12.84  |             0.3857 |
| saturation_bin | 1-2            | mlp                                            |               -0.02199   |                     0.01601 |        1.537   |             9.367 |             0.3333 |
| saturation_bin | 3-5            | mlp                                            |                0.002213  |                     0.03723 |       -1.265   |            15.41  |             0      |
| saturation_bin | 0              | ridge                                          |                0.003589  |                     0.07591 |       -0.3753  |             8.798 |             0.2979 |
| saturation_bin | 1-2            | ridge                                          |               -0.05015   |                     0.01031 |      -11.62    |             9.501 |             0      |
| saturation_bin | 3-5            | ridge                                          |               -0.06646   |                     0.07196 |       -4.236   |             6.496 |             0      |
| saturation_bin | 0              | saturation_residual_fusion_new                 |               -0.001804  |                     0.06881 |       -0.09258 |             7.78  |             0.2725 |
| saturation_bin | 1-2            | saturation_residual_fusion_new                 |               -0.01687   |                     0.0554  |       -5.916   |             4.77  |             0      |
| saturation_bin | 3-5            | saturation_residual_fusion_new                 |               -0.01619   |                     0.05184 |       -1.541   |             3.72  |             0      |
| saturation_bin | 0              | tiny_sequence_transformer                      |               -0.0211    |                     0.09601 |       -6.319   |            14.03  |             0.3718 |
| saturation_bin | 1-2            | tiny_sequence_transformer                      |               -0.1191    |                     0.02211 |      -12.76    |             2.818 |             0.3333 |
| saturation_bin | 3-5            | tiny_sequence_transformer                      |               -0.09275   |                     0.08899 |       -8.28    |             9.598 |             0      |
| pedestal_state | nominal        | 1d_cnn                                         |                0.006623  |                     0.07584 |       -0.8693  |            10.41  |             0.2437 |
| pedestal_state | shifted        | 1d_cnn                                         |                0.05449   |                     0.1173  |       -2.334   |            10.64  |             0.2679 |
| pedestal_state | nominal        | analytic_clipped_template_sideband_traditional |                0.05458   |                     0.08523 |        1.062   |             8.694 |             0.3438 |
| pedestal_state | shifted        | analytic_clipped_template_sideband_traditional |                0.07116   |                     0.08845 |        0.3037  |            12.34  |             0.65   |
| pedestal_state | nominal        | gradient_boosted_trees                         |               -0.01574   |                     0.05523 |       -0.02665 |             8.281 |             0.25   |
| pedestal_state | shifted        | gradient_boosted_trees                         |                0.003646  |                     0.08003 |        0.243   |             8.186 |             0.2893 |
| pedestal_state | nominal        | mlp                                            |               -0.0119    |                     0.07909 |       -1.358   |            11.98  |             0.3375 |
| pedestal_state | shifted        | mlp                                            |                0.0215    |                     0.1024  |       -2.195   |            13.57  |             0.4071 |
| pedestal_state | nominal        | ridge                                          |               -0.01472   |                     0.06048 |       -0.4437  |             8.537 |             0.2562 |
| pedestal_state | shifted        | ridge                                          |                0.01818   |                     0.07444 |       -0.4973  |             8.825 |             0.3143 |
| pedestal_state | nominal        | saturation_residual_fusion_new                 |               -0.007273  |                     0.06283 |       -0.9271  |             7.329 |             0.2375 |
| pedestal_state | shifted        | saturation_residual_fusion_new                 |                0.01066   |                     0.07639 |        0.3206  |             7.498 |             0.2857 |
| pedestal_state | nominal        | tiny_sequence_transformer                      |               -0.04572   |                     0.08216 |       -4.656   |            12.77  |             0.3375 |

## Systematics and Caveats

The truth labels are controlled overlays into raw-ROOT-derived clean pulses, so
the benchmark tests recovery under known clipping and pile-up truth rather than
measuring the real beam saturation rate.  The ADC ceiling is an explicit stress
operator, not decoded front-end metadata.  The 18-sample waveform window limits
very close onset separation and makes pedestal memory partly degenerate with
late tails.  PID dependence is represented by stave and charge-support proxies
because no external particle truth is present in the reduced ROOT gate.
Run-block bootstrap intervals quantify transfer across five held-out runs and
should not be interpreted as independent event-counting errors.

## Verdict

`result.json` names **saturation_residual_fusion_new** as the S36a winner.  The result supports using
clipped-sample sidebands and residual waveform morphology to recover amplitude
and onset timing near the saturation boundary, while retaining the traditional
censored template fit as the transparent baseline.

Runtime was `69.3` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

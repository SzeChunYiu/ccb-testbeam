# S51b: Saturated Pile-Up Energy Recovery from Censored Pulse Windows

## Abstract

Ticket `2456` asks for a raw-ROOT reproduction followed by an academic-grade
comparison of energy reconstruction under censored clipped saturation and unresolved
pile-up.  The worker is `testbeam-laptop-4`.  The held-out winner written to `result.json`
is **`saturation_residual_fusion_new`**, selected by the registered composite score.  Its energy
residual sigma68 is `0.06373` with 95% run-block
bootstrap CI [`0.05659`,
`0.08093`], and its pile-up separation
sigma68 is `10.84` ns.

## Raw ROOT Reproduction Gate

Raw B-stack files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each ROOT file, the
`h101/HRDv` waveform branch is reshaped to `(event, channel, sample)` with 18
samples per channel.  The selected-pulse anchor uses B2/B4/B6/B8 channels,
pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`,

and indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

This raw count is reproduced before fitting any model:

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split and Controlled Truth

The split is by source run.  Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]`;
held-out runs are `[58, 60, 62, 64, 65]`.  Clean templates are
estimated only from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              800 |                   2.599 |                      5 |           9.149 |
| B4      |              784 |                   2.982 |                      6 |          10.78  |
| B6      |              751 |                   3.747 |                      6 |           9.739 |
| B8      |              482 |                   4.236 |                      8 |           9.253 |

Controlled doublets are generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a run-local residual and `p` is a pedestal offset.  The
observed waveform supplied to every method is clipped as

`w_obs(t) = min(w(t), 11800)`.

Clean single-pulse controls are drawn from the same run distribution and clipped
with the same rule, so false split rate is a real negative-control endpoint.

## Methods

| method                                         | family         | description                                                                          |
|:-----------------------------------------------|:---------------|:-------------------------------------------------------------------------------------|
| analytic_clipped_template_sideband_traditional | traditional    | bounded two-template deconvolution with deterministic clipping sideband correction   |
| ridge                                          | linear ML      | ridge classifier plus multi-output ridge regression                                  |
| gradient_boosted_trees                         | tree ML        | histogram gradient-boosted classifier and regressors                                 |
| mlp                                            | neural network | tabular multilayer perceptron classifier/regressor pair                              |
| 1d_cnn                                         | neural network | compact one-dimensional CNN over the 18 ADC samples                                  |
| tiny_sequence_transformer                      | sequence NN    | one-layer self-attention encoder over waveform samples                               |
| saturation_residual_fusion_new                 | new hybrid     | boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs |

The traditional comparator fits one- and two-pulse template hypotheses by
bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

then applies a deterministic saturation sideband correction based on clipped
sample count, plateau width, and late-tail fraction:

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`.

The new architecture is `saturation_residual_fusion_new`.  It is sensible here
because the failure mode is hybrid: the analytic fit supplies identifiable
constituents, while clipping sidebands and waveform summaries carry residual
information about charge hidden above the ADC ceiling.

## Endpoints and Equations

The primary energy residual for accepted injected doublets is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Pile-up separation error is

`e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`,

and timing shifts use

`e_tj = 10 ns * (hat t_j - t_j)`.

Robust resolution is

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

Confidence intervals are percentile 95% intervals from
`400` held-out run-block bootstrap resamples.
The registered winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.004 sigma_Delta + 0.004 sigma_t1 + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`,

where `S_ped` is the pedestal-state false-split span and `S_PID` is the
stave/PID-proxy energy-bias span.

## Overall Results

| method                                         |   winner_score |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   pileup_separation_sigma68_ns |   leading_timing_shift_sigma68_ns |   pileup_miss_rate |   false_split_rate |   pedestal_shift_false_split_span |   pid_energy_bias_span |
|:-----------------------------------------------|---------------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|-------------------------------:|----------------------------------:|-------------------:|-------------------:|----------------------------------:|-----------------------:|
| saturation_residual_fusion_new                 |         0.164  |               0.001887 |                   0.06373 |                          0.05659 |                           0.08093 |                          10.84 |                             5.169 |             0.3098 |             0.2146 |                           0.0754  |                0.0447  |
| gradient_boosted_trees                         |         0.1771 |               0.003336 |                   0.07043 |                          0.06423 |                           0.07543 |                          11.32 |                             5.623 |             0.3049 |             0.2073 |                           0.09475 |                0.06326 |
| ridge                                          |         0.1851 |              -0.002334 |                   0.06947 |                          0.06457 |                           0.07491 |                          14.01 |                             6.28  |             0.3049 |             0.1951 |                           0.04402 |                0.0684  |
| mlp                                            |         0.2225 |              -0.007954 |                   0.08241 |                          0.06816 |                           0.09264 |                          16.21 |                             7.735 |             0.3171 |             0.2244 |                           0.1429  |                0.05224 |
| analytic_clipped_template_sideband_traditional |         0.2523 |               0.06213  |                   0.0897  |                          0.08117 |                           0.1072  |                          16    |                             8.177 |             0.5829 |             0.1878 |                           0.1026  |                0.0844  |
| 1d_cnn                                         |         0.2607 |              -0.01612  |                   0.1115  |                          0.09768 |                           0.1213  |                          17.37 |                             9.226 |             0.2732 |             0.2707 |                           0.04111 |                0.1139  |
| tiny_sequence_transformer                      |         0.2698 |              -0.03442  |                   0.0971  |                          0.0805  |                           0.1058  |                          19.16 |                            11.1   |             0.4463 |             0.1756 |                           0.07489 |                0.09686 |

The traditional comparator has score `0.2523` and energy
sigma68 `0.0897`.  The selected winner changes
energy sigma68 by `-0.02597`.

## Endpoint Table with CIs

| method                                         |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   saturation_onset_energy_sigma68 |   pileup_separation_sigma68_ns |   pileup_separation_sigma68_ns_ci_low |   pileup_separation_sigma68_ns_ci_high |   leading_timing_shift_bias_ns |   pedestal_shift_false_split_span |   pid_energy_bias_span |   pid_failure_rate_span |
|:-----------------------------------------------|--------------------------:|---------------------------------:|----------------------------------:|----------------------------------:|-------------------------------:|--------------------------------------:|---------------------------------------:|-------------------------------:|----------------------------------:|-----------------------:|------------------------:|
| saturation_residual_fusion_new                 |                   0.06373 |                          0.05659 |                           0.08093 |                           0.06733 |                          10.84 |                                 9.952 |                                  12.23 |                         0.6376 |                           0.0754  |                0.0447  |                  0.314  |
| ridge                                          |                   0.06947 |                          0.06457 |                           0.07491 |                           0.05528 |                          14.01 |                                12.26  |                                  15.21 |                         0.3282 |                           0.04402 |                0.0684  |                  0.3369 |
| gradient_boosted_trees                         |                   0.07043 |                          0.06423 |                           0.07543 |                           0.06454 |                          11.32 |                                 9.765 |                                  12.79 |                         0.5938 |                           0.09475 |                0.06326 |                  0.3086 |
| mlp                                            |                   0.08241 |                          0.06816 |                           0.09264 |                           0.06333 |                          16.21 |                                14.09  |                                  18.19 |                        -0.32   |                           0.1429  |                0.05224 |                  0.2371 |
| analytic_clipped_template_sideband_traditional |                   0.0897  |                          0.08117 |                           0.1072  |                           0.02329 |                          16    |                                12.5   |                                  22.5  |                         0.4478 |                           0.1026  |                0.0844  |                  0.1058 |
| tiny_sequence_transformer                      |                   0.0971  |                          0.0805  |                           0.1058  |                           0.04268 |                          19.16 |                                16.61  |                                  22.4  |                        -4.354  |                           0.07489 |                0.09686 |                  0.1532 |
| 1d_cnn                                         |                   0.1115  |                          0.09768 |                           0.1213  |                           0.07965 |                          17.37 |                                16.69  |                                  19.45 |                         0.3562 |                           0.04111 |                0.1139  |                  0.1319 |

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |               -0.03558   |                     0.1267  |        -1.983  |            10.28  |             0.2927 |            0.3171  |
| 1d_cnn                                         |            60 |                0.01311   |                     0.09648 |         2.118  |            12.73  |             0.2439 |            0.3415  |
| 1d_cnn                                         |            62 |               -0.01738   |                     0.09025 |        -0.239  |            11.56  |             0.2805 |            0.3049  |
| 1d_cnn                                         |            64 |               -0.003131  |                     0.1008  |         0.1173 |            11.38  |             0.2317 |            0.1463  |
| 1d_cnn                                         |            65 |               -0.03424   |                     0.1003  |        -2.273  |            11.2   |             0.3171 |            0.2439  |
| analytic_clipped_template_sideband_traditional |            58 |                0.05319   |                     0.07871 |         1.033  |            11.33  |             0.5854 |            0.2317  |
| analytic_clipped_template_sideband_traditional |            60 |                0.08468   |                     0.09149 |         1.499  |            13.44  |             0.5488 |            0.2317  |
| analytic_clipped_template_sideband_traditional |            62 |                0.07958   |                     0.09386 |         2.097  |             9.964 |             0.5854 |            0.1585  |
| analytic_clipped_template_sideband_traditional |            64 |                0.04174   |                     0.1051  |        -0.4542 |             9.32  |             0.561  |            0.1951  |
| analytic_clipped_template_sideband_traditional |            65 |                0.04216   |                     0.06561 |         0.7431 |             7.743 |             0.6341 |            0.122   |
| gradient_boosted_trees                         |            58 |                0.005051  |                     0.07017 |        -0.916  |             6.671 |             0.3049 |            0.2683  |
| gradient_boosted_trees                         |            60 |                0.01672   |                     0.06235 |        -0.3534 |             7.254 |             0.2439 |            0.2439  |
| gradient_boosted_trees                         |            62 |               -0.007102  |                     0.06459 |        -0.2689 |             8.341 |             0.3537 |            0.1463  |
| gradient_boosted_trees                         |            64 |               -0.007707  |                     0.07182 |        -0.445  |             7.088 |             0.3171 |            0.122   |
| gradient_boosted_trees                         |            65 |               -0.002914  |                     0.07437 |        -1.268  |             7.156 |             0.3049 |            0.2561  |
| mlp                                            |            58 |                0.004564  |                     0.09003 |        -0.7407 |             9.444 |             0.2805 |            0.2195  |
| mlp                                            |            60 |               -0.0002825 |                     0.07971 |         0.7545 |             9.902 |             0.2805 |            0.2683  |
| mlp                                            |            62 |               -0.01592   |                     0.0624  |        -3.209  |            11.86  |             0.3415 |            0.2683  |
| mlp                                            |            64 |               -0.01788   |                     0.08441 |        -0.4713 |             8.929 |             0.3537 |            0.1341  |
| mlp                                            |            65 |               -0.02383   |                     0.08926 |        -0.9452 |            10.72  |             0.3293 |            0.2317  |
| ridge                                          |            58 |               -0.003615  |                     0.06749 |        -0.576  |             8.463 |             0.2561 |            0.2683  |
| ridge                                          |            60 |                0.007416  |                     0.06179 |        -0.3308 |             9.426 |             0.2561 |            0.1951  |
| ridge                                          |            62 |                0.008483  |                     0.06781 |        -1.233  |             9.604 |             0.3537 |            0.1829  |
| ridge                                          |            64 |               -0.002618  |                     0.06495 |        -1.765  |             9.821 |             0.2805 |            0.1341  |
| ridge                                          |            65 |               -0.01301   |                     0.07263 |        -0.6922 |             7.986 |             0.378  |            0.1951  |
| saturation_residual_fusion_new                 |            58 |                0.01127   |                     0.07057 |        -0.8975 |             5.913 |             0.3049 |            0.2683  |
| saturation_residual_fusion_new                 |            60 |                0.01018   |                     0.0533  |         0.2205 |             6.634 |             0.2683 |            0.2805  |
| saturation_residual_fusion_new                 |            62 |               -0.02681   |                     0.05057 |         0.4333 |             8.334 |             0.3293 |            0.1463  |
| saturation_residual_fusion_new                 |            64 |                0.001049  |                     0.06701 |        -1.294  |             6.49  |             0.3293 |            0.122   |
| saturation_residual_fusion_new                 |            65 |               -0.005887  |                     0.085   |        -1.129  |             7.764 |             0.3171 |            0.2561  |
| tiny_sequence_transformer                      |            58 |               -0.02801   |                     0.115   |        -7.707  |            16.07  |             0.4024 |            0.2439  |
| tiny_sequence_transformer                      |            60 |               -0.01906   |                     0.1016  |        -6.411  |            13.42  |             0.378  |            0.2439  |
| tiny_sequence_transformer                      |            62 |               -0.02934   |                     0.07415 |        -8.19   |            13.46  |             0.5244 |            0.1341  |
| tiny_sequence_transformer                      |            64 |               -0.04012   |                     0.1023  |       -10.66   |            14.38  |             0.4268 |            0.09756 |
| tiny_sequence_transformer                      |            65 |               -0.05115   |                     0.08123 |       -10.18   |            16.21  |             0.5    |            0.1585  |

## Stratified Systematics

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class:

| stratum        | value          | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:---------------|:---------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin    | (-0.001, 10.0] | 1d_cnn                                         |               -0.001049  |                   0.1023    |         2.798  |            11.75  |             0.3688 |
| spacing_bin    | (10.0, 25.0]   | 1d_cnn                                         |                0.005673  |                   0.101     |        -0.1475 |             7.184 |             0.3222 |
| spacing_bin    | (25.0, 45.0]   | 1d_cnn                                         |               -0.02912   |                   0.1059    |        -4.799  |             9.835 |             0.1959 |
| spacing_bin    | (45.0, 70.0]   | 1d_cnn                                         |               -0.05219   |                   0.08989   |        -1.684  |            15.99  |             0.1463 |
| spacing_bin    | (-0.001, 10.0] | analytic_clipped_template_sideband_traditional |                0.06963   |                   0.0892    |         1.705  |            15.93  |             0.6879 |
| spacing_bin    | (10.0, 25.0]   | analytic_clipped_template_sideband_traditional |                0.0908    |                   0.05421   |         1.979  |             7.615 |             0.7222 |
| spacing_bin    | (25.0, 45.0]   | analytic_clipped_template_sideband_traditional |                0.06328   |                   0.08392   |         0.244  |            10.16  |             0.4639 |
| spacing_bin    | (45.0, 70.0]   | analytic_clipped_template_sideband_traditional |                0.01427   |                   0.1134    |        -0.399  |             8.422 |             0.3902 |
| spacing_bin    | (-0.001, 10.0] | gradient_boosted_trees                         |                0.02313   |                   0.05163   |         0.142  |             6.872 |             0.3901 |
| spacing_bin    | (10.0, 25.0]   | gradient_boosted_trees                         |                0.008546  |                   0.06312   |         0.7471 |             5.639 |             0.3444 |
| spacing_bin    | (25.0, 45.0]   | gradient_boosted_trees                         |               -0.01004   |                   0.06956   |        -2.455  |             8.519 |             0.268  |
| spacing_bin    | (45.0, 70.0]   | gradient_boosted_trees                         |               -0.03193   |                   0.0743    |        -1.466  |             8.999 |             0.1585 |
| spacing_bin    | (-0.001, 10.0] | mlp                                            |                0.02602   |                   0.0847    |         1.212  |            10.15  |             0.383  |
| spacing_bin    | (10.0, 25.0]   | mlp                                            |               -0.01424   |                   0.09246   |         0.1902 |             7.078 |             0.3556 |
| spacing_bin    | (25.0, 45.0]   | mlp                                            |               -0.01481   |                   0.07852   |        -3.271  |            10.28  |             0.268  |
| spacing_bin    | (45.0, 70.0]   | mlp                                            |               -0.03685   |                   0.07721   |        -3.224  |            13.65  |             0.2195 |
| spacing_bin    | (-0.001, 10.0] | ridge                                          |                0.02976   |                   0.06014   |        -0.2972 |             8.577 |             0.3546 |
| spacing_bin    | (10.0, 25.0]   | ridge                                          |                0.02092   |                   0.05342   |         0.938  |             6.068 |             0.3556 |
| spacing_bin    | (25.0, 45.0]   | ridge                                          |               -0.02205   |                   0.06247   |        -3.307  |             9.807 |             0.268  |
| spacing_bin    | (45.0, 70.0]   | ridge                                          |               -0.04439   |                   0.06526   |        -3.305  |            12.29  |             0.2073 |
| spacing_bin    | (-0.001, 10.0] | saturation_residual_fusion_new                 |                0.0122    |                   0.0498    |         0.4694 |             6.522 |             0.4184 |
| spacing_bin    | (10.0, 25.0]   | saturation_residual_fusion_new                 |                0.01317   |                   0.05512   |         0.7238 |             5.698 |             0.3667 |
| spacing_bin    | (25.0, 45.0]   | saturation_residual_fusion_new                 |               -0.01259   |                   0.06094   |        -2.19   |             7.855 |             0.2474 |
| spacing_bin    | (45.0, 70.0]   | saturation_residual_fusion_new                 |               -0.03323   |                   0.069     |        -1.359  |             9.022 |             0.1341 |
| spacing_bin    | (-0.001, 10.0] | tiny_sequence_transformer                      |                0.001818  |                   0.09103   |        -6.41   |            10.91  |             0.5461 |
| spacing_bin    | (10.0, 25.0]   | tiny_sequence_transformer                      |               -0.01144   |                   0.07613   |        -8.978  |             8.678 |             0.5778 |
| spacing_bin    | (25.0, 45.0]   | tiny_sequence_transformer                      |               -0.0357    |                   0.08543   |       -13.51   |            16     |             0.3711 |
| spacing_bin    | (45.0, 70.0]   | tiny_sequence_transformer                      |               -0.1002    |                   0.08094   |        -5.447  |            17.78  |             0.2195 |
| ratio_bin      | (-0.001, 0.35] | 1d_cnn                                         |                0.01038   |                   0.1364    |        -5.063  |            11.3   |             0.4444 |
| ratio_bin      | (0.35, 0.625]  | 1d_cnn                                         |               -0.03668   |                   0.1002    |        -1.27   |            10.66  |             0.2736 |
| ratio_bin      | (0.625, 0.875] | 1d_cnn                                         |               -0.02819   |                   0.09131   |         0.1576 |            11.25  |             0.2079 |
| ratio_bin      | (0.875, 1.05]  | 1d_cnn                                         |               -0.001049  |                   0.1205    |         1.112  |            11.68  |             0.1947 |
| ratio_bin      | (-0.001, 0.35] | analytic_clipped_template_sideband_traditional |                0.0763    |                   0.0997    |        -0.4855 |            12.06  |             0.6778 |
| ratio_bin      | (0.35, 0.625]  | analytic_clipped_template_sideband_traditional |                0.06093   |                   0.08251   |         1.1    |            10.67  |             0.4906 |
| ratio_bin      | (0.625, 0.875] | analytic_clipped_template_sideband_traditional |                0.06963   |                   0.09825   |         1.545  |             8.499 |             0.604  |
| ratio_bin      | (0.875, 1.05]  | analytic_clipped_template_sideband_traditional |                0.04468   |                   0.08326   |         1.417  |             9.879 |             0.5752 |
| ratio_bin      | (-0.001, 0.35] | gradient_boosted_trees                         |                0.01862   |                   0.05181   |        -3.057  |             8.296 |             0.5333 |
| ratio_bin      | (0.35, 0.625]  | gradient_boosted_trees                         |               -0.01225   |                   0.08224   |        -1.526  |             7.661 |             0.3679 |
| ratio_bin      | (0.625, 0.875] | gradient_boosted_trees                         |               -0.0009777 |                   0.06695   |        -0.9581 |             6.521 |             0.1782 |
| ratio_bin      | (0.875, 1.05]  | gradient_boosted_trees                         |                0.004908  |                   0.06411   |         1.314  |             7.519 |             0.177  |
| ratio_bin      | (-0.001, 0.35] | mlp                                            |                0.03991   |                   0.08172   |        -3.793  |             8.988 |             0.4333 |
| ratio_bin      | (0.35, 0.625]  | mlp                                            |               -0.008636  |                   0.08143   |        -2.549  |            10.6   |             0.3208 |
| ratio_bin      | (0.625, 0.875] | mlp                                            |               -0.02317   |                   0.08345   |         0.2534 |             9.292 |             0.297  |
| ratio_bin      | (0.875, 1.05]  | mlp                                            |               -0.01563   |                   0.07307   |         1.508  |            10.21  |             0.2389 |
| ratio_bin      | (-0.001, 0.35] | ridge                                          |               -0.000634  |                   0.07337   |        -3.683  |             9.528 |             0.5111 |
| ratio_bin      | (0.35, 0.625]  | ridge                                          |               -0.006054  |                   0.06762   |        -3.273  |             8.81  |             0.3302 |
| ratio_bin      | (0.625, 0.875] | ridge                                          |               -0.0123    |                   0.07514   |        -0.2393 |             8.545 |             0.198  |
| ratio_bin      | (0.875, 1.05]  | ridge                                          |                0.009442  |                   0.06075   |         2.57   |             9.069 |             0.2124 |
| ratio_bin      | (-0.001, 0.35] | saturation_residual_fusion_new                 |                0.02398   |                   0.0692    |        -3.151  |             7.056 |             0.5444 |
| ratio_bin      | (0.35, 0.625]  | saturation_residual_fusion_new                 |                0.001181  |                   0.0767    |        -1.389  |             7.787 |             0.3396 |
| ratio_bin      | (0.625, 0.875] | saturation_residual_fusion_new                 |               -0.002776  |                   0.05615   |        -0.5269 |             7.37  |             0.2178 |
| ratio_bin      | (0.875, 1.05]  | saturation_residual_fusion_new                 |                0.001049  |                   0.06487   |         0.9597 |             6.81  |             0.177  |
| ratio_bin      | (-0.001, 0.35] | tiny_sequence_transformer                      |               -0.006412  |                   0.08701   |       -10.16   |            17.49  |             0.5556 |
| ratio_bin      | (0.35, 0.625]  | tiny_sequence_transformer                      |               -0.05017   |                   0.1067    |       -10.6    |            16.24  |             0.4245 |
| ratio_bin      | (0.625, 0.875] | tiny_sequence_transformer                      |               -0.03916   |                   0.09644   |        -8.261  |            10.41  |             0.4653 |
| ratio_bin      | (0.875, 1.05]  | tiny_sequence_transformer                      |               -0.0278    |                   0.08171   |        -6.374  |            13.27  |             0.3628 |
| saturation_bin | 0              | 1d_cnn                                         |               -0.01471   |                   0.1135    |        -1.034  |            11.33  |             0.2807 |
| saturation_bin | 1-2            | 1d_cnn                                         |               -0.1194    |                   0.0458    |        -6.991  |            12.42  |             0      |
| saturation_bin | 3-5            | 1d_cnn                                         |               -0.05143   |                   0.08005   |         4.695  |            16.64  |             0      |
| saturation_bin | 6+             | 1d_cnn                                         |               -0.01357   |                   0         |        19.41   |            11.25  |             0      |
| saturation_bin | 0              | analytic_clipped_template_sideband_traditional |                0.05392   |                   0.08628   |         1.139  |            10.08  |             0.589  |
| saturation_bin | 1-2            | analytic_clipped_template_sideband_traditional |                0.1535    |                   0.0002593 |         1.854  |            19.5   |             0.5    |
| saturation_bin | 3-5            | analytic_clipped_template_sideband_traditional |                0.1641    |                   0.03131   |        -5.892  |            17.13  |             0.3333 |
| saturation_bin | 6+             | analytic_clipped_template_sideband_traditional |                0.197     |                   0         |        10.96   |            15.3   |             0      |
| saturation_bin | 0              | gradient_boosted_trees                         |                0.004127  |                   0.06955   |        -0.5214 |             7.356 |             0.3133 |
| saturation_bin | 1-2            | gradient_boosted_trees                         |               -0.06652   |                   0.0685    |        -4.611  |             9.405 |             0      |
| saturation_bin | 3-5            | gradient_boosted_trees                         |               -0.04231   |                   0.04418   |        -2.645  |             5.52  |             0      |
| saturation_bin | 6+             | gradient_boosted_trees                         |                0.08568   |                   0         |         5.259  |             3.301 |             0      |
| saturation_bin | 0              | mlp                                            |               -0.008547  |                   0.08344   |        -0.9947 |            10.02  |             0.3258 |
| saturation_bin | 1-2            | mlp                                            |               -0.008813  |                   0.05528   |         5.518  |            14.58  |             0      |
| saturation_bin | 3-5            | mlp                                            |               -0.007667  |                   0.06904   |        10.73   |            10.41  |             0      |
| saturation_bin | 6+             | mlp                                            |                0.05527   |                   0         |        14.75   |             3.928 |             0      |
| saturation_bin | 0              | ridge                                          |               -0.001153  |                   0.06943   |        -0.7196 |             9.056 |             0.3133 |
| saturation_bin | 1-2            | ridge                                          |               -0.07389   |                   0.02781   |        -3.67   |             5.163 |             0      |
| saturation_bin | 3-5            | ridge                                          |               -0.04527   |                   0.04313   |        -3.646  |             4.61  |             0      |
| saturation_bin | 6+             | ridge                                          |                0.04615   |                   0         |         4.961  |             7.966 |             0      |
| saturation_bin | 0              | saturation_residual_fusion_new                 |                0.001937  |                   0.06358   |        -0.5828 |             7.283 |             0.3183 |
| saturation_bin | 1-2            | saturation_residual_fusion_new                 |               -0.04593   |                   0.04532   |        -6.901  |             8.07  |             0      |
| saturation_bin | 3-5            | saturation_residual_fusion_new                 |               -0.009465  |                   0.06137   |        -2.233  |             5.578 |             0      |
| saturation_bin | 6+             | saturation_residual_fusion_new                 |                0.08829   |                   0         |         5.816  |             6.137 |             0      |
| saturation_bin | 0              | tiny_sequence_transformer                      |               -0.02934   |                   0.09427   |        -8.31   |            14.88  |             0.4561 |
| saturation_bin | 1-2            | tiny_sequence_transformer                      |               -0.1665    |                   0.05115   |       -11.38   |            10.84  |             0.25   |
| saturation_bin | 3-5            | tiny_sequence_transformer                      |               -0.1558    |                   0.05132   |        -7.974  |             7.904 |             0      |
| saturation_bin | 6+             | tiny_sequence_transformer                      |               -0.1317    |                   0         |        -1.313  |            13.65  |             0      |
| pedestal_state | nominal        | 1d_cnn                                         |               -0.03552   |                   0.07987   |         1.537  |            10.76  |             0.2449 |
| pedestal_state | shifted        | 1d_cnn                                         |                0.0006597 |                   0.1399    |        -2.461  |            12.27  |             0.289  |
| pedestal_state | nominal        | analytic_clipped_template_sideband_traditional |                0.06459   |                   0.09766   |         1.139  |             9.171 |             0.4082 |
| pedestal_state | shifted        | analytic_clipped_template_sideband_traditional |                0.05354   |                   0.08637   |         0.9324 |            11.43  |             0.6806 |
| pedestal_state | nominal        | gradient_boosted_trees                         |               -0.004322  |                   0.06533   |         0.3985 |             6.896 |             0.3333 |
| pedestal_state | shifted        | gradient_boosted_trees                         |                0.005051  |                   0.07096   |        -1.541  |             7.419 |             0.289  |

## Systematics and Caveats

The truth labels are controlled overlays into raw-ROOT-derived clean pulses, so
the study tests reconstruction under known saturation and pile-up truth but does
not measure the real beam pile-up frequency.  The clipping threshold is an
explicit benchmark stressor rather than decoded front-end metadata.  The
18-sample readout creates a sampling floor for close doublets and makes pedestal
memory partly degenerate with broad late tails.  PID is represented by stave and
charge support because no external particle label is available in the reduced
ROOT gate.  Run-block bootstrap intervals quantify transfer across the five
held-out runs, not asymptotic event-counting uncertainty.

## Verdict

`result.json` names **saturation_residual_fusion_new** as the S51b winner.  The traditional clipped
template method remains the transparent fallback, while the selected winner is
preferred for the registered held-out energy-plus-pile-up score.

Runtime was `97.7` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

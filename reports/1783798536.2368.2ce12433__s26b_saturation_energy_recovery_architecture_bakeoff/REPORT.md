# S26b: saturation energy recovery architecture bakeoff

## Abstract

Ticket `1783798536.2368.2ce12433` asks whether raw B-stack HRD waveforms support a stronger
architecture for saturated pulse energy and timing recovery than a traditional
saturation-knee/template correction.  The worker was `testbeam-laptop-4`.  Before fitting
any model, the raw ROOT selected-pulse anchor was reproduced exactly:
`640737` selected B-stave pulses versus the reference
`640737`, with delta `0`.

The winner is `template_residual_boosted_stack_new` by the predeclared composite ordering

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`,

where `sigma_E` is held-out fractional energy sigma68, `sigma_t` is constituent
timing sigma68 in ns, and the final two terms penalize missed injected pile-up and
false splitting of clean controls.  `template_residual_boosted_stack_new` obtains `sigma_E =
0.06496` with 95% run-block bootstrap CI
[0.05933,
0.07655] and timing sigma68
`7.429` ns.

## Raw ROOT reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` object was
reshaped to `(event, channel, sample)` with 18 samples per channel.  B2/B4/B6/B8
were pedestal-subtracted with `b_c = median(x_c[0:4])`; selected pulses satisfy
`max_t (x_c(t)-b_c) > 1000 ADC`.  This reproduces the existing analysis count and
guards against benchmarking on a derived cache with incompatible semantics.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Train-only pulse templates

Clean single-pulse templates were estimated only from train runs
`[50, 51, 52, 53, 54, 55, 56, 57]`.  Candidate clean pulses required amplitude
1500--12000 ADC and peak sample 4--12.  For pulse `i` on stave `s`, the normalized
waveform is shifted to a common CFD20 reference and the template is

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              736 |                   2.576 |                      5 |           9.187 |
| B4      |              728 |                   2.995 |                      6 |          10.67  |
| B6      |              695 |                   3.749 |                      6 |           9.715 |
| B8      |              474 |                   4.236 |                      8 |           9.248 |

## Benchmark design

The split is by source run, not by event: train runs `[50, 51, 52, 53, 54, 55, 56, 57]`
and held-out runs `[58, 60, 62, 64, 65]`.  Controlled saturated
doublets are generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_r(t) + p`.

Here `Delta` spans sub-sample to multi-sample overlap, `r` spans weak to nearly
equal second pulses, `epsilon_r(t)` is a run-local residual sampled from real clean
pulses, and `p` is a pedestal excursion.  The saturation proxy is the injected
summed amplitude above the high-charge knee; strata include amplitude ceiling,
pulse-shape spacing, pile-up ratio, pedestal excursion through run-local residuals,
and a PID proxy through stave and amplitude composition.

## Methods

The traditional method is `two_pulse_template_cfd_baseline`, a bounded
saturation-knee two-template fit.  For one or two constituents it minimizes

`SSE_k = sum_t [w(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

with positive amplitudes, bounded baseline, constrained separations, and a
template-derived CFD initialization.  Its classification score is the fractional
improvement `(SSE_1-SSE_2)/SSE_1`.

The machine-learning panel contains the required ridge model, histogram
gradient-boosted trees, MLP, compact 1D-CNN, and two architecture candidates:
`tiny_sequence_transformer`, a one-layer self-attention encoder over the 18-sample
waveform, and `template_residual_boosted_stack_new`, a physics-residual stack that
feeds the traditional fit estimates into boosted residual classifiers/regressors.
All non-traditional models are trained only on train runs.

## Metrics and uncertainty

For detected injected doublets, constituent timing error is

`e_t = 10 ns * (hat t - t_true)`,

and recovered total energy error is

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`.

For either endpoint,

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are 95% percentile intervals from
`400` bootstrap resamples of held-out runs.

## Overall held-out results

| method                              |   winner_score |   energy_fractional_bias |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|-------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|---------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.1648 |                -0.01334  |                     0.06496 |                            0.05933 |                             0.07655 |        -0.8129 |             7.429 |                    6.345 |                     7.956 |             0.3667 |             0.1444 |
| gradient_boosted_trees              |         0.1729 |                -0.01467  |                     0.07268 |                            0.06585 |                             0.0739  |        -1.012  |             7.286 |                    6.408 |                     7.532 |             0.3806 |             0.1667 |
| ridge                               |         0.1816 |                -0.008839 |                     0.06401 |                            0.06004 |                             0.06597 |        -0.5141 |             8.867 |                    8.328 |                     9.858 |             0.3972 |             0.1806 |
| 1d_cnn                              |         0.214  |                 0.03672  |                     0.08145 |                            0.07475 |                             0.08811 |        -1.081  |            10.53  |                    9.431 |                    11.93  |             0.2806 |             0.2639 |
| two_pulse_template_cfd_baseline     |         0.2232 |                 0.005859 |                     0.08832 |                            0.06547 |                             0.09991 |         0.8506 |             9.761 |                    7.977 |                    10.42  |             0.5722 |             0.1722 |
| mlp                                 |         0.2497 |                -0.0242   |                     0.1206  |                            0.09762 |                             0.1371  |        -0.2398 |            10.12  |                    9.243 |                    11.87  |             0.4139 |             0.1444 |
| tiny_sequence_transformer           |         0.2981 |                 0.01949  |                     0.1183  |                            0.1065  |                             0.1304  |        -5.014  |            15.02  |                   14.23  |                    15.35  |             0.3361 |             0.2556 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.02336`
and timing sigma68 by `-2.332` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                0.03672   |                     0.07337 |        -1.911  |            10.21  |             0.2639 |            0.25    |
| 1d_cnn                              |            60 |                0.05395   |                     0.0849  |         0.7371 |            12.23  |             0.3194 |            0.3194  |
| 1d_cnn                              |            62 |                0.01829   |                     0.0669  |        -2.76   |            10.72  |             0.1944 |            0.1944  |
| 1d_cnn                              |            64 |                0.0226    |                     0.07567 |         0.9092 |             8.759 |             0.2917 |            0.25    |
| 1d_cnn                              |            65 |                0.05608   |                     0.08059 |        -2.667  |             9.799 |             0.3333 |            0.3056  |
| gradient_boosted_trees              |            58 |               -0.01291   |                     0.07335 |        -1.187  |             6.603 |             0.3194 |            0.2639  |
| gradient_boosted_trees              |            60 |               -0.008682  |                     0.0694  |        -0.9848 |             6.746 |             0.375  |            0.1667  |
| gradient_boosted_trees              |            62 |               -0.03322   |                     0.07108 |        -1.207  |             7.469 |             0.3889 |            0.1528  |
| gradient_boosted_trees              |            64 |               -0.01647   |                     0.07102 |         0.2647 |             6.628 |             0.3194 |            0.1111  |
| gradient_boosted_trees              |            65 |               -0.009361  |                     0.07129 |        -1.919  |             5.707 |             0.5    |            0.1389  |
| mlp                                 |            58 |                0.0002743 |                     0.1452  |        -0.2921 |            12.78  |             0.3194 |            0.1528  |
| mlp                                 |            60 |               -0.01049   |                     0.108   |        -0.5375 |             9.746 |             0.4306 |            0.1667  |
| mlp                                 |            62 |               -0.03142   |                     0.1175  |        -0.8956 |             8.97  |             0.4306 |            0.1528  |
| mlp                                 |            64 |               -0.05462   |                     0.07544 |         1.272  |             9.323 |             0.4028 |            0.08333 |
| mlp                                 |            65 |               -0.0227    |                     0.1491  |        -0.5562 |            12.53  |             0.4861 |            0.1667  |
| ridge                               |            58 |               -0.001908  |                     0.05725 |         0.3323 |             8.156 |             0.3194 |            0.1528  |
| ridge                               |            60 |               -0.008692  |                     0.06127 |         1.053  |             8.991 |             0.375  |            0.2639  |
| ridge                               |            62 |               -0.01271   |                     0.05653 |        -0.9649 |            10.13  |             0.4028 |            0.2083  |
| ridge                               |            64 |               -0.007783  |                     0.0647  |        -0.1799 |             7.954 |             0.3889 |            0.125   |
| ridge                               |            65 |                0.006687  |                     0.06702 |        -2.74   |             9.318 |             0.5    |            0.1528  |
| template_residual_boosted_stack_new |            58 |               -0.02411   |                     0.05332 |        -0.3732 |             7.584 |             0.3472 |            0.2361  |
| template_residual_boosted_stack_new |            60 |               -0.01061   |                     0.08744 |        -0.7601 |             7.285 |             0.3333 |            0.1667  |
| template_residual_boosted_stack_new |            62 |               -0.009002  |                     0.05857 |        -0.9244 |             8.259 |             0.3889 |            0.1111  |
| template_residual_boosted_stack_new |            64 |                0.001687  |                     0.06455 |         0.1091 |             6.763 |             0.2917 |            0.08333 |
| template_residual_boosted_stack_new |            65 |               -0.01616   |                     0.05439 |        -2.1    |             5.237 |             0.4722 |            0.125   |
| tiny_sequence_transformer           |            58 |                0.00959   |                     0.1032  |        -6.586  |            14.26  |             0.3333 |            0.2778  |
| tiny_sequence_transformer           |            60 |                0.02917   |                     0.1239  |        -5.166  |            14.14  |             0.375  |            0.2778  |
| tiny_sequence_transformer           |            62 |                0.01293   |                     0.09915 |        -5.23   |            15.49  |             0.3194 |            0.2222  |
| tiny_sequence_transformer           |            64 |                0.01136   |                     0.1246  |        -3.843  |            14.43  |             0.2778 |            0.2222  |
| tiny_sequence_transformer           |            65 |                0.06143   |                     0.1236  |        -5.292  |            13.94  |             0.375  |            0.2778  |
| two_pulse_template_cfd_baseline     |            58 |                0.01452   |                     0.09518 |         0.9959 |             9.376 |             0.5972 |            0.1944  |
| two_pulse_template_cfd_baseline     |            60 |                0.01201   |                     0.09306 |         0.5009 |             7.501 |             0.5417 |            0.1111  |
| two_pulse_template_cfd_baseline     |            62 |                0.00508   |                     0.04649 |         1.081  |             6.95  |             0.5833 |            0.1944  |
| two_pulse_template_cfd_baseline     |            64 |               -0.02007   |                     0.09198 |         0.604  |            10.67  |             0.5139 |            0.1111  |
| two_pulse_template_cfd_baseline     |            65 |               -0.01322   |                     0.07762 |         2.36   |             8.95  |             0.625  |            0.25    |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:----------------|:---------------|:------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              |                0.06259   |                     0.08316 |        1.006   |            12.21  |            0.4054  |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              |                0.04389   |                     0.08039 |        0.787   |             8.655 |            0.2976  |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              |                0.02446   |                     0.07425 |       -2.391   |             8.686 |            0.2135  |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              |                0.00733   |                     0.08278 |       -2.068   |            10.7   |            0.1579  |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              |                0.00735   |                     0.05505 |        0.1884  |             6.932 |            0.4505  |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              |               -0.001503  |                     0.05711 |       -0.3142  |             5.332 |            0.4524  |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              |               -0.03193   |                     0.06533 |       -1.722   |             6.857 |            0.3146  |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              |               -0.04763   |                     0.06892 |       -1.554   |             8.655 |            0.2763  |
| spacing_bin     | (-0.001, 10.0] | mlp                                 |                0.03261   |                     0.1178  |        1.585   |             9.044 |            0.4505  |
| spacing_bin     | (10.0, 25.0]   | mlp                                 |               -0.01243   |                     0.08101 |        0.269   |             7.545 |            0.5119  |
| spacing_bin     | (25.0, 45.0]   | mlp                                 |               -0.04251   |                     0.1099  |       -1.592   |            10.62  |            0.3596  |
| spacing_bin     | (45.0, 70.0]   | mlp                                 |               -0.04347   |                     0.119   |       -1.367   |            12.91  |            0.3158  |
| spacing_bin     | (-0.001, 10.0] | ridge                               |                0.01979   |                     0.04957 |       -0.1002  |            10.55  |            0.3964  |
| spacing_bin     | (10.0, 25.0]   | ridge                               |                0.006225  |                     0.04998 |        1.596   |             5.943 |            0.4762  |
| spacing_bin     | (25.0, 45.0]   | ridge                               |               -0.02559   |                     0.05474 |       -1.043   |             8.134 |            0.3708  |
| spacing_bin     | (45.0, 70.0]   | ridge                               |               -0.05116   |                     0.04493 |       -3.991   |            10.38  |            0.3421  |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new |                0.006201  |                     0.05539 |        0.6741  |             6.888 |            0.4324  |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new |                0.01221   |                     0.06291 |       -0.2365  |             5.071 |            0.4286  |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new |               -0.02216   |                     0.05732 |       -1.646   |             7.406 |            0.3146  |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new |               -0.03795   |                     0.06461 |       -1.449   |             8.008 |            0.2632  |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           |                0.07091   |                     0.07888 |       -1.949   |            11     |            0.4595  |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           |                0.07306   |                     0.07516 |       -7.619   |            12.3   |            0.3929  |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           |               -0.00602   |                     0.06935 |       -5.29    |            14.99  |            0.2472  |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           |               -0.1274    |                     0.1141  |       -5.483   |            17.39  |            0.1974  |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |                0.013     |                     0.08662 |        2.668   |            17.57  |            0.6577  |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |                0.0004691 |                     0.04585 |        0.256   |             6.428 |            0.6905  |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |                0.02312   |                     0.09048 |        0.1789  |             8.766 |            0.5169  |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |               -0.03015   |                     0.08097 |       -1.22    |             8.511 |            0.3816  |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              |                0.02937   |                     0.09047 |       -3.685   |            11.5   |            0.3789  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              |                0.03523   |                     0.06699 |       -2.712   |             9.842 |            0.284   |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              |                0.03155   |                     0.07695 |       -0.7182  |            11.01  |            0.25    |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              |                0.04673   |                     0.07697 |        1.875   |             9.434 |            0.2     |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              |                0.003383  |                     0.07508 |       -3.553   |             8.395 |            0.6316  |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              |               -0.004606  |                     0.07181 |       -1.371   |             7.841 |            0.3457  |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              |               -0.02779   |                     0.0712  |       -0.7568  |             5.96  |            0.2596  |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              |               -0.01652   |                     0.072   |        0.01508 |             6.217 |            0.275   |
| ratio_bin       | (-0.001, 0.35] | mlp                                 |               -0.07664   |                     0.1153  |       -6.867   |            13.41  |            0.6105  |
| ratio_bin       | (0.35, 0.625]  | mlp                                 |               -0.01186   |                     0.09951 |       -1.669   |             8.922 |            0.4198  |
| ratio_bin       | (0.625, 0.875] | mlp                                 |               -0.03913   |                     0.1257  |       -0.2164  |             9.112 |            0.3462  |
| ratio_bin       | (0.875, 1.05]  | mlp                                 |                0.003514  |                     0.1252  |        1.831   |             8.411 |            0.2625  |
| ratio_bin       | (-0.001, 0.35] | ridge                               |                0.009373  |                     0.06982 |       -3.813   |             8.843 |            0.6105  |
| ratio_bin       | (0.35, 0.625]  | ridge                               |                0.002572  |                     0.05636 |       -0.6611  |             7.769 |            0.4321  |
| ratio_bin       | (0.625, 0.875] | ridge                               |               -0.02386   |                     0.06288 |       -0.6692  |             8.019 |            0.2788  |
| ratio_bin       | (0.875, 1.05]  | ridge                               |               -0.004714  |                     0.05854 |        2.665   |             8.697 |            0.2625  |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new |                0.01014   |                     0.08033 |       -3.64    |             8.623 |            0.6105  |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new |               -0.001382  |                     0.05908 |       -2.148   |             7.214 |            0.3333  |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new |               -0.02411   |                     0.06812 |       -0.795   |             6.161 |            0.2596  |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new |               -0.01901   |                     0.05756 |        0.5411  |             6.416 |            0.25    |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           |                0.03469   |                     0.171   |       -7.04    |            18.02  |            0.4421  |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           |                0.01949   |                     0.08598 |       -3.97    |            15.06  |            0.3457  |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           |                0.004942  |                     0.1141  |       -5.31    |            13.24  |            0.3173  |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           |                0.04672   |                     0.08296 |       -4.268   |            13.69  |            0.225   |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |                0.0134    |                     0.1157  |       -0.259   |            13.27  |            0.5789  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |                0.01993   |                     0.07857 |        0.02698 |             9.481 |            0.5556  |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     |               -0.001713  |                     0.06823 |        0.1789  |             8.745 |            0.5865  |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |               -0.009524  |                     0.07777 |        1.334   |             6.326 |            0.5625  |
| stave           | B2             | 1d_cnn                              |                0.01087   |                     0.08987 |       -5.533   |             9.749 |            0.505   |
| stave           | B4             | 1d_cnn                              |                0.08979   |                     0.07872 |       -3.259   |            10.64  |            0.3377  |
| stave           | B6             | 1d_cnn                              |                0.02016   |                     0.06324 |        0.787   |             9.016 |            0.1685  |
| stave           | B8             | 1d_cnn                              |                0.03523   |                     0.07964 |        0.7711  |            10.05  |            0.09677 |
| stave           | B2             | gradient_boosted_trees              |               -0.0336    |                     0.07223 |       -5.306   |             7.675 |            0.5248  |
| stave           | B4             | gradient_boosted_trees              |                0.01886   |                     0.08345 |       -1.749   |             6.851 |            0.3636  |
| stave           | B6             | gradient_boosted_trees              |               -0.006534  |                     0.07395 |       -0.1306  |             6.286 |            0.382   |
| stave           | B8             | gradient_boosted_trees              |               -0.01721   |                     0.056   |        0.7464  |             4.883 |            0.2366  |
| stave           | B2             | mlp                                 |               -0.06468   |                     0.1251  |       -6.146   |            11.16  |            0.6238  |
| stave           | B4             | mlp                                 |                0.03507   |                     0.102   |       -1.771   |            12.73  |            0.4545  |
| stave           | B6             | mlp                                 |               -0.0242    |                     0.1072  |        1.259   |             8.296 |            0.382   |
| stave           | B8             | mlp                                 |               -0.03873   |                     0.1013  |        0.4289  |             9.002 |            0.1828  |
| stave           | B2             | ridge                               |               -0.03151   |                     0.046   |       -6.372   |             9.366 |            0.5941  |
| stave           | B4             | ridge                               |                0.02097   |                     0.06576 |       -2.14    |             9.654 |            0.4286  |
| stave           | B6             | ridge                               |               -0.009511  |                     0.06567 |        0.7097  |             7.364 |            0.3596  |
| stave           | B8             | ridge                               |               -0.007898  |                     0.06054 |        1.994   |             7.539 |            0.1935  |
| stave           | B2             | template_residual_boosted_stack_new |               -0.04202   |                     0.06611 |       -4.306   |             7.74  |            0.505   |
| stave           | B4             | template_residual_boosted_stack_new |                0.01314   |                     0.08836 |       -1.924   |             8.278 |            0.3766  |
| stave           | B6             | template_residual_boosted_stack_new |               -0.01801   |                     0.05495 |        0.6076  |             6.3   |            0.3596  |
| stave           | B8             | template_residual_boosted_stack_new |               -0.01285   |                     0.05843 |        0.3981  |             5.06  |            0.2151  |
| stave           | B2             | tiny_sequence_transformer           |               -0.006955  |                     0.1211  |      -11.64    |            14.01  |            0.5545  |
| stave           | B4             | tiny_sequence_transformer           |                0.07554   |                     0.09225 |       -9.277   |            15.2   |            0.3506  |
| stave           | B6             | tiny_sequence_transformer           |                0.03432   |                     0.1007  |       -2.635   |            12.07  |            0.2472  |
| stave           | B8             | tiny_sequence_transformer           |               -0.01119   |                     0.1046  |        0.2022  |            13.55  |            0.172   |
| stave           | B2             | two_pulse_template_cfd_baseline     |                0.0592    |                     0.05325 |        4.615   |            17.06  |            0.7822  |
| stave           | B4             | two_pulse_template_cfd_baseline     |               -0.06212   |                     0.07892 |        4.195   |            16.22  |            0.8961  |
| stave           | B6             | two_pulse_template_cfd_baseline     |               -0.04539   |                     0.04546 |       -0.2242  |             8.28  |            0.4607  |
| stave           | B8             | two_pulse_template_cfd_baseline     |                0.02996   |                     0.08803 |        0.8108  |             5.84  |            0.1828  |
| saturated_proxy | False          | 1d_cnn                              |                0.03672   |                     0.08221 |       -0.9198  |            10.44  |            0.2787  |
| saturated_proxy | True           | 1d_cnn                              |                0.02942   |                     0.07771 |       -4.604   |             9.283 |            0.3333  |
| saturated_proxy | False          | gradient_boosted_trees              |               -0.01647   |                     0.07486 |       -0.8938  |             7.086 |            0.3937  |
| saturated_proxy | True           | gradient_boosted_trees              |                0.001196  |                     0.03565 |       -3.687   |             6.89  |            0       |
| saturated_proxy | False          | mlp                                 |               -0.02581   |                     0.1171  |       -0.2039  |            10.09  |            0.4282  |
| saturated_proxy | True           | mlp                                 |                0.04013   |                     0.1658  |       -2.039   |            10.14  |            0       |
| saturated_proxy | False          | ridge                               |               -0.007898  |                     0.06412 |       -0.3568  |             9.031 |            0.4109  |
| saturated_proxy | True           | ridge                               |               -0.0311    |                     0.04316 |       -5.327   |             8.801 |            0       |
| saturated_proxy | False          | template_residual_boosted_stack_new |               -0.01414   |                     0.06618 |       -0.7511  |             7.103 |            0.3793  |
| saturated_proxy | True           | template_residual_boosted_stack_new |               -0.003467  |                     0.06689 |       -3.834   |             6.571 |            0       |
| saturated_proxy | False          | tiny_sequence_transformer           |                0.02001   |                     0.1189  |       -4.421   |            15.16  |            0.3391  |
| saturated_proxy | True           | tiny_sequence_transformer           |                0.01461   |                     0.1064  |      -10.36    |             6.318 |            0.25    |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     |                0.005664  |                     0.0882  |        1.081   |             9.503 |            0.5661  |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     |                0.006054  |                     0.03053 |       -7.569   |             5.125 |            0.75    |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `145.7` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

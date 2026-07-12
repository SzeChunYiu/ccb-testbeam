# S26c: energy-PID pedestal transfer audit

## Abstract

Ticket `1783805896.7081.330f50dc` asks whether raw B-stack HRD waveforms support a stronger
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
0.06525` with 95% run-block bootstrap CI
[0.05538,
0.07639] and timing sigma68
`8.383` ns.

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
| template_residual_boosted_stack_new |         0.1757 |               -0.00596   |                     0.06525 |                            0.05538 |                             0.07639 |       -1.212   |             8.383 |                    7.381 |                     9.564 |             0.3278 |             0.2056 |
| gradient_boosted_trees              |         0.1861 |               -0.01409   |                     0.0743  |                            0.06282 |                             0.08349 |       -1.306   |             8.447 |                    7.806 |                     9.515 |             0.3583 |             0.1889 |
| ridge                               |         0.1931 |                0.0007313 |                     0.06322 |                            0.05875 |                             0.07003 |        0.2138  |            10.3   |                    9.274 |                    10.67  |             0.3444 |             0.1944 |
| two_pulse_template_cfd_baseline     |         0.216  |                0.001803  |                     0.08217 |                            0.06575 |                             0.09593 |        0.1744  |             9.437 |                    8.293 |                    11.37  |             0.5944 |             0.1944 |
| 1d_cnn                              |         0.2334 |               -0.01081   |                     0.08934 |                            0.08241 |                             0.09655 |        0.09436 |            11.7   |                   10.74  |                    12.53  |             0.3028 |             0.2389 |
| mlp                                 |         0.3082 |               -0.01038   |                     0.1382  |                            0.1181  |                             0.1753  |        0.5122  |            14.3   |                   13.5   |                    15.42  |             0.3333 |             0.2083 |
| tiny_sequence_transformer           |         0.3206 |               -0.04991   |                     0.1221  |                            0.109   |                             0.133   |      -10.49    |            16.9   |                   15.91  |                    17.95  |             0.3361 |             0.2528 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.01692`
and timing sigma68 by `-1.054` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                0.003618  |                     0.08574 |        0.6375  |            11.12  |             0.2639 |             0.25   |
| 1d_cnn                              |            60 |                0.01897   |                     0.07966 |        0.04081 |            12.92  |             0.375  |             0.2639 |
| 1d_cnn                              |            62 |               -0.03898   |                     0.07744 |       -0.1567  |            10.95  |             0.1944 |             0.3333 |
| 1d_cnn                              |            64 |                0.001419  |                     0.09369 |       -0.5046  |            12.52  |             0.3194 |             0.1667 |
| 1d_cnn                              |            65 |               -0.01787   |                     0.09962 |        0.4692  |            10.25  |             0.3611 |             0.1806 |
| gradient_boosted_trees              |            58 |               -0.006626  |                     0.06135 |       -1.571   |             7.67  |             0.3611 |             0.2778 |
| gradient_boosted_trees              |            60 |               -0.01068   |                     0.08122 |       -0.2159  |             9.229 |             0.3611 |             0.1944 |
| gradient_boosted_trees              |            62 |               -0.0146    |                     0.0847  |       -1.727   |             9.442 |             0.2917 |             0.1806 |
| gradient_boosted_trees              |            64 |               -0.01916   |                     0.07211 |       -1.613   |             8.66  |             0.4028 |             0.1389 |
| gradient_boosted_trees              |            65 |               -0.01684   |                     0.05648 |       -0.747   |             7.424 |             0.375  |             0.1528 |
| mlp                                 |            58 |               -0.008523  |                     0.1232  |        4.315   |            12.97  |             0.3194 |             0.1806 |
| mlp                                 |            60 |                0.03294   |                     0.1972  |        0.4855  |            14.87  |             0.3194 |             0.2639 |
| mlp                                 |            62 |               -0.03449   |                     0.1104  |        0.1532  |            15.95  |             0.2361 |             0.3056 |
| mlp                                 |            64 |               -0.02164   |                     0.1186  |       -2.344   |            14.3   |             0.375  |             0.1528 |
| mlp                                 |            65 |                0.01099   |                     0.136   |        1.71    |            14.36  |             0.4167 |             0.1389 |
| ridge                               |            58 |                0.002847  |                     0.06241 |        0.315   |             9.575 |             0.3194 |             0.2083 |
| ridge                               |            60 |                0.002023  |                     0.07933 |        2.222   |             9.637 |             0.3194 |             0.2917 |
| ridge                               |            62 |               -0.01892   |                     0.07232 |       -2.375   |            11.16  |             0.3194 |             0.2083 |
| ridge                               |            64 |                0.000259  |                     0.05556 |        0.5071  |            10.11  |             0.4028 |             0.1528 |
| ridge                               |            65 |               -0.001912  |                     0.0552  |       -0.3647  |             8.72  |             0.3611 |             0.1111 |
| template_residual_boosted_stack_new |            58 |               -0.006919  |                     0.065   |       -1.279   |             7.611 |             0.3333 |             0.3056 |
| template_residual_boosted_stack_new |            60 |               -0.0003732 |                     0.09689 |       -0.9108  |            10.45  |             0.3056 |             0.2361 |
| template_residual_boosted_stack_new |            62 |               -0.01933   |                     0.06415 |       -1.432   |             9.135 |             0.2778 |             0.2222 |
| template_residual_boosted_stack_new |            64 |                0.005999  |                     0.06926 |       -1.133   |             7.975 |             0.3889 |             0.125  |
| template_residual_boosted_stack_new |            65 |               -0.01067   |                     0.04871 |       -1.781   |             6.902 |             0.3333 |             0.1389 |
| tiny_sequence_transformer           |            58 |               -0.04813   |                     0.1089  |      -10.43    |            15.97  |             0.2917 |             0.3056 |
| tiny_sequence_transformer           |            60 |               -0.001476  |                     0.1051  |       -9.187   |            17.48  |             0.375  |             0.25   |
| tiny_sequence_transformer           |            62 |               -0.07232   |                     0.1268  |      -11.26    |            18.07  |             0.2361 |             0.3056 |
| tiny_sequence_transformer           |            64 |               -0.03986   |                     0.1577  |      -13.39    |            16.31  |             0.375  |             0.1667 |
| tiny_sequence_transformer           |            65 |               -0.07244   |                     0.1153  |       -9.004   |            14.77  |             0.4028 |             0.2361 |
| two_pulse_template_cfd_baseline     |            58 |                0.006053  |                     0.06888 |        1.696   |             8.507 |             0.625  |             0.2083 |
| two_pulse_template_cfd_baseline     |            60 |                0.03109   |                     0.1147  |       -0.5708  |             8.133 |             0.6528 |             0.1667 |
| two_pulse_template_cfd_baseline     |            62 |               -0.009321  |                     0.05543 |        0.4767  |             8.046 |             0.5694 |             0.1528 |
| two_pulse_template_cfd_baseline     |            64 |                0.02684   |                     0.08964 |       -0.03701 |            13.06  |             0.5972 |             0.25   |
| two_pulse_template_cfd_baseline     |            65 |               -0.014     |                     0.06659 |       -0.9066  |             8.951 |             0.5278 |             0.1944 |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:----------------|:---------------|:------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              |               -0.01479   |                     0.09372 |       -0.2627  |            11.43  |            0.4206  |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              |                0.02328   |                     0.09186 |        1.078   |             7.824 |            0.3837  |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              |               -0.004795  |                     0.09465 |       -2.858   |            10.47  |            0.2533  |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              |               -0.02409   |                     0.07436 |        1.09    |            14.58  |            0.1304  |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              |                0.01627   |                     0.0611  |       -1.559   |             6.988 |            0.4112  |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              |               -0.006961  |                     0.05965 |       -0.1899  |             5.85  |            0.4767  |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              |               -0.01568   |                     0.07594 |       -2.423   |             8.533 |            0.2933  |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              |               -0.03969   |                     0.07431 |       -1.689   |            10.06  |            0.2391  |
| spacing_bin     | (-0.001, 10.0] | mlp                                 |                0.02416   |                     0.1248  |        2.213   |            14.53  |            0.3925  |
| spacing_bin     | (10.0, 25.0]   | mlp                                 |               -0.004212  |                     0.1699  |        0.8026  |            11.53  |            0.3953  |
| spacing_bin     | (25.0, 45.0]   | mlp                                 |               -0.04507   |                     0.108   |       -1.139   |            14.82  |            0.32    |
| spacing_bin     | (45.0, 70.0]   | mlp                                 |               -0.01574   |                     0.1461  |        0.3094  |            16.73  |            0.2174  |
| spacing_bin     | (-0.001, 10.0] | ridge                               |                0.02059   |                     0.04439 |        0.05393 |             9.858 |            0.3832  |
| spacing_bin     | (10.0, 25.0]   | ridge                               |                0.01892   |                     0.04928 |        1.991   |             6.576 |            0.4419  |
| spacing_bin     | (25.0, 45.0]   | ridge                               |               -0.01382   |                     0.06644 |       -0.519   |            10.15  |            0.36    |
| spacing_bin     | (45.0, 70.0]   | ridge                               |               -0.05594   |                     0.06036 |       -2.614   |            12.95  |            0.1957  |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new |                0.01365   |                     0.05276 |       -0.9213  |             6.974 |            0.4299  |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new |                8.982e-05 |                     0.05865 |       -0.1879  |             6.365 |            0.4186  |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new |               -0.001093  |                     0.04618 |       -2.919   |             9.676 |            0.24    |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new |               -0.04591   |                     0.06787 |       -1.487   |            10.7   |            0.1957  |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           |                0.008793  |                     0.07096 |       -9.79    |            10.67  |            0.4579  |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           |                0.02212   |                     0.1185  |       -8.95    |            10.03  |            0.4302  |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           |               -0.07106   |                     0.1036  |      -12.27    |            17.01  |            0.3067  |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           |               -0.1383    |                     0.09902 |      -13.16    |            22.71  |            0.1304  |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |                0.0235    |                     0.04382 |        3.749   |             9.399 |            0.729   |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |                0.03059   |                     0.07344 |        1.259   |             8.086 |            0.6512  |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |               -0.004139  |                     0.06874 |        0.8387  |             8.782 |            0.5467  |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |               -0.03861   |                     0.09427 |       -1.707   |             9.723 |            0.4239  |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              |               -0.02118   |                     0.08973 |       -2.4     |             9.783 |            0.3333  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              |               -0.02829   |                     0.09257 |       -0.4804  |            12.83  |            0.38    |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              |                0.004266  |                     0.1037  |        0.916   |            12.28  |            0.2651  |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              |               -0.005755  |                     0.06577 |        1.538   |            11.5   |            0.2184  |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              |                0.008913  |                     0.08249 |       -3.813   |             8.001 |            0.5333  |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              |                0.001665  |                     0.06852 |       -0.6425  |             9.182 |            0.44    |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              |               -0.01586   |                     0.08032 |       -0.6389  |             8.427 |            0.2169  |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              |               -0.02904   |                     0.06178 |       -0.9485  |             7.265 |            0.2184  |
| ratio_bin       | (-0.001, 0.35] | mlp                                 |               -0.007062  |                     0.1501  |       -2.23    |            13.34  |            0.4     |
| ratio_bin       | (0.35, 0.625]  | mlp                                 |               -0.001458  |                     0.1316  |       -1.039   |            15.35  |            0.4     |
| ratio_bin       | (0.625, 0.875] | mlp                                 |               -0.02988   |                     0.1431  |        2.167   |            12.51  |            0.3012  |
| ratio_bin       | (0.875, 1.05]  | mlp                                 |               -0.008764  |                     0.1412  |        1.491   |            13.48  |            0.2184  |
| ratio_bin       | (-0.001, 0.35] | ridge                               |                0.001924  |                     0.07068 |       -5.061   |             9.079 |            0.5111  |
| ratio_bin       | (0.35, 0.625]  | ridge                               |                0.0105    |                     0.06834 |       -0.079   |             9.689 |            0.43    |
| ratio_bin       | (0.625, 0.875] | ridge                               |               -0.0003836 |                     0.05834 |        2.042   |             9.344 |            0.2048  |
| ratio_bin       | (0.875, 1.05]  | ridge                               |               -0.01759   |                     0.06017 |        2.33    |             9.136 |            0.2069  |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new |               -0.001734  |                     0.07615 |       -4.006   |             7.388 |            0.4778  |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new |               -0.002152  |                     0.06436 |       -0.8405  |             8.99  |            0.42    |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new |               -0.007757  |                     0.06898 |       -0.1432  |             8.217 |            0.1928  |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new |               -0.01044   |                     0.06488 |       -0.7042  |             7.741 |            0.1954  |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           |               -0.02635   |                     0.1185  |      -13.7     |            16     |            0.3778  |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           |               -0.0228    |                     0.1113  |       -9.307   |            16.36  |            0.42    |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           |               -0.04958   |                     0.1332  |       -8.495   |            15.99  |            0.3253  |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           |               -0.07343   |                     0.1055  |       -9.412   |            17.98  |            0.2069  |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |                0.02885   |                     0.1118  |       -1.55    |            11.7   |            0.5444  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |               -0.01268   |                     0.08304 |       -0.449   |             8.728 |            0.68    |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     |               -0.002758  |                     0.06256 |        0.7182  |             9.422 |            0.6024  |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |                0.0005327 |                     0.06446 |        0.6568  |             6.981 |            0.5402  |
| stave           | B2             | 1d_cnn                              |               -0.07949   |                     0.08985 |       -5.666   |            12.38  |            0.4235  |
| stave           | B4             | 1d_cnn                              |                0.01492   |                     0.07697 |       -1.219   |            11.86  |            0.3404  |
| stave           | B6             | 1d_cnn                              |               -0.01883   |                     0.07753 |       -0.1066  |            11.01  |            0.2095  |
| stave           | B8             | 1d_cnn                              |                0.00723   |                     0.07761 |        3.354   |             8.619 |            0.25    |
| stave           | B2             | gradient_boosted_trees              |               -0.03337   |                     0.08888 |       -5.058   |            11.34  |            0.4471  |
| stave           | B4             | gradient_boosted_trees              |                0.001646  |                     0.06783 |       -3.553   |             7.138 |            0.3085  |
| stave           | B6             | gradient_boosted_trees              |               -0.02528   |                     0.05558 |       -0.5342  |             7.726 |            0.3619  |
| stave           | B8             | gradient_boosted_trees              |                0.01333   |                     0.06827 |        1.366   |             7.545 |            0.3158  |
| stave           | B2             | mlp                                 |               -0.06371   |                     0.09933 |       -7.874   |            15.81  |            0.4941  |
| stave           | B4             | mlp                                 |                0.02194   |                     0.1182  |        1.772   |            13.09  |            0.266   |
| stave           | B6             | mlp                                 |               -0.01606   |                     0.1346  |        0.6806  |            14.91  |            0.2857  |
| stave           | B8             | mlp                                 |               -0.01666   |                     0.1432  |        1.473   |            12.88  |            0.3026  |
| stave           | B2             | ridge                               |               -0.05558   |                     0.08811 |       -6.235   |            15.37  |            0.4118  |
| stave           | B4             | ridge                               |                0.01269   |                     0.05956 |       -2.015   |             7.891 |            0.266   |
| stave           | B6             | ridge                               |               -0.01298   |                     0.0459  |        1.977   |             9.334 |            0.3619  |
| stave           | B8             | ridge                               |                0.02059   |                     0.062   |        4       |             8.665 |            0.3421  |
| stave           | B2             | template_residual_boosted_stack_new |               -0.0124    |                     0.09205 |       -4.624   |            11.77  |            0.3882  |
| stave           | B4             | template_residual_boosted_stack_new |               -0.0004206 |                     0.06189 |       -3.034   |             6.595 |            0.2766  |
| stave           | B6             | template_residual_boosted_stack_new |               -0.02147   |                     0.06338 |       -0.1222  |             7.647 |            0.3238  |
| stave           | B8             | template_residual_boosted_stack_new |                0.00532   |                     0.08272 |        1.342   |             7.359 |            0.3289  |
| stave           | B2             | tiny_sequence_transformer           |               -0.1025    |                     0.1382  |      -13.4     |            19.23  |            0.5059  |
| stave           | B4             | tiny_sequence_transformer           |               -0.0283    |                     0.1374  |      -11.03    |            15.86  |            0.3298  |
| stave           | B6             | tiny_sequence_transformer           |               -0.05312   |                     0.103   |      -10.9     |            17.17  |            0.2381  |
| stave           | B8             | tiny_sequence_transformer           |               -0.03376   |                     0.107   |       -6.783   |            13.82  |            0.2895  |
| stave           | B2             | two_pulse_template_cfd_baseline     |                0.05616   |                     0.04713 |        0.2491  |            11.24  |            0.6941  |
| stave           | B4             | two_pulse_template_cfd_baseline     |               -0.001224  |                     0.05601 |        0.2596  |            13.82  |            0.7766  |
| stave           | B6             | two_pulse_template_cfd_baseline     |               -0.05899   |                     0.04812 |       -0.8035  |            10.04  |            0.5714  |
| stave           | B8             | two_pulse_template_cfd_baseline     |                0.03472   |                     0.08448 |        1.158   |             5.499 |            0.2895  |
| saturated_proxy | False          | 1d_cnn                              |               -0.008069  |                     0.08876 |        0.07904 |            11.6   |            0.3121  |
| saturated_proxy | True           | 1d_cnn                              |               -0.04473   |                     0.1037  |        1.628   |            13.23  |            0.07143 |
| saturated_proxy | False          | gradient_boosted_trees              |               -0.01404   |                     0.07355 |       -1.306   |             8.287 |            0.3728  |
| saturated_proxy | True           | gradient_boosted_trees              |               -0.02453   |                     0.0922  |       -1.301   |            10.91  |            0       |
| saturated_proxy | False          | mlp                                 |               -0.009746  |                     0.1405  |        0.4482  |            14.22  |            0.3468  |
| saturated_proxy | True           | mlp                                 |               -0.05196   |                     0.1051  |        9.185   |            21.42  |            0       |
| saturated_proxy | False          | ridge                               |                0.002261  |                     0.06262 |        0.344   |             9.71  |            0.3584  |
| saturated_proxy | True           | ridge                               |               -0.08692   |                     0.05746 |       -3.628   |            13.37  |            0       |
| saturated_proxy | False          | template_residual_boosted_stack_new |               -0.007267  |                     0.0632  |       -1.212   |             8.045 |            0.341   |
| saturated_proxy | True           | template_residual_boosted_stack_new |                0.0007425 |                     0.09331 |       -1.302   |            11.47  |            0       |
| saturated_proxy | False          | tiny_sequence_transformer           |               -0.04813   |                     0.12    |      -10.49    |            16.88  |            0.3468  |
| saturated_proxy | True           | tiny_sequence_transformer           |               -0.132     |                     0.1195  |      -10.69    |            17.21  |            0.07143 |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     |               -0.001224  |                     0.08546 |        0.1567  |             9.412 |            0.5925  |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     |                0.05786   |                     0.0305  |        0.8368  |             9.995 |            0.6429  |

## PID proxy confusion

No independent particle-species truth labels are available in the raw HRD branches used here.  I therefore define a stated proxy PID label as stave plus total injected energy tertile, `y = stave : q_E(A_1+A_2)`, and treat failed or non-finite double-pulse recovery as `abstain`.  This tests whether a recovery method preserves energy/PID composition under the same leave-run-family-out split rather than claiming a detector-level species measurement.

| method                              |   pid_proxy_accuracy |   pid_proxy_accuracy_ci_low |   pid_proxy_accuracy_ci_high |   pid_proxy_abstain_rate |   n_positive |
|:------------------------------------|---------------------:|----------------------------:|-----------------------------:|-------------------------:|-------------:|
| 1d_cnn                              |             0.625    |                    0.563889 |                     0.700069 |                 0.302778 |          360 |
| template_residual_boosted_stack_new |             0.594444 |                    0.558264 |                     0.625    |                 0.327778 |          360 |
| ridge                               |             0.583333 |                    0.55     |                     0.616667 |                 0.344444 |          360 |
| gradient_boosted_trees              |             0.566667 |                    0.536111 |                     0.597222 |                 0.358333 |          360 |
| tiny_sequence_transformer           |             0.530556 |                    0.466667 |                     0.597292 |                 0.336111 |          360 |
| mlp                                 |             0.508333 |                    0.483333 |                     0.538958 |                 0.333333 |          360 |
| two_pulse_template_cfd_baseline     |             0.352778 |                    0.305556 |                     0.394514 |                 0.594444 |          360 |

The full confusion tensor is stored in `pid_proxy_confusion.csv`; the compact accuracy table above is `pid_proxy_summary.csv`.

## Pedestal transfer sensitivity and abstention deltas

The ROOT sample has per-event waveform pedestals but no independent pedestal-truth labels after controlled injection.  Pedestal transfer is therefore audited as a run/stave control sensitivity: clean-control false split rate, injected-overlap miss rate, and their run/stave ranges under held-out runs.  The comparison is conservative because pedestal excursions and late broad tails are partially degenerate in an 18-sample window.

| method                              |   clean_false_split_rate |   clean_false_split_run_range |   clean_false_split_stave_range |   pileup_miss_rate |   pileup_miss_run_range |   pileup_miss_stave_range |   false_split_delta_vs_traditional |   pileup_miss_delta_vs_traditional |
|:------------------------------------|-------------------------:|------------------------------:|--------------------------------:|-------------------:|------------------------:|--------------------------:|-----------------------------------:|-----------------------------------:|
| 1d_cnn                              |                 0.238889 |                     0.166667  |                       0.209726  |           0.302778 |               0.180556  |                  0.214006 |                         0.0444444  |                          -0.291667 |
| template_residual_boosted_stack_new |                 0.205556 |                     0.180556  |                       0.0947941 |           0.327778 |               0.111111  |                  0.11164  |                         0.0111111  |                          -0.266667 |
| mlp                                 |                 0.208333 |                     0.166667  |                       0.171012  |           0.333333 |               0.180556  |                  0.22816  |                         0.0138889  |                          -0.261111 |
| tiny_sequence_transformer           |                 0.252778 |                     0.138889  |                       0.312318  |           0.336111 |               0.166667  |                  0.267787 |                         0.0583333  |                          -0.258333 |
| ridge                               |                 0.194444 |                     0.180556  |                       0.187233  |           0.344444 |               0.0833333 |                  0.145807 |                         0          |                          -0.25     |
| gradient_boosted_trees              |                 0.188889 |                     0.138889  |                       0.0859506 |           0.358333 |               0.111111  |                  0.138548 |                        -0.00555556 |                          -0.236111 |
| two_pulse_template_cfd_baseline     |                 0.194444 |                     0.0972222 |                       0.236874  |           0.594444 |               0.125     |                  0.487122 |                         0          |                           0        |

Pile-up abstention deltas are measured relative to the traditional two-template baseline; negative miss deltas mean fewer missed injected doublets, while positive false-split deltas mean more clean controls split spuriously.

| method                              |   pileup_miss_rate |   pileup_miss_delta_vs_traditional |   false_split_rate |   false_split_delta_vs_traditional |   late_tail_rate_abs_gt_15ns |   late_tail_delta_vs_traditional |
|:------------------------------------|-------------------:|-----------------------------------:|-------------------:|-----------------------------------:|-----------------------------:|---------------------------------:|
| 1d_cnn                              |           0.302778 |                          -0.291667 |           0.238889 |                         0.0444444  |                     0.177291 |                       0.0300306  |
| template_residual_boosted_stack_new |           0.327778 |                          -0.266667 |           0.205556 |                         0.0111111  |                     0.126033 |                      -0.0212272  |
| mlp                                 |           0.333333 |                          -0.261111 |           0.208333 |                         0.0138889  |                     0.302083 |                       0.154823   |
| tiny_sequence_transformer           |           0.336111 |                          -0.258333 |           0.252778 |                         0.0583333  |                     0.430962 |                       0.283702   |
| ridge                               |           0.344444 |                          -0.25     |           0.194444 |                         0          |                     0.137712 |                      -0.00954841 |
| gradient_boosted_trees              |           0.358333 |                          -0.236111 |           0.188889 |                        -0.00555556 |                     0.108225 |                      -0.0390352  |
| two_pulse_template_cfd_baseline     |           0.594444 |                           0        |           0.194444 |                         0          |                     0.14726  |                       0          |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `67.8` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

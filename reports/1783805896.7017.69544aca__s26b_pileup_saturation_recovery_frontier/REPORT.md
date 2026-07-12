# S26b: saturation energy recovery architecture bakeoff

## Abstract

Ticket `1783805896.7017.69544aca` asks whether raw B-stack HRD waveforms support a stronger
architecture for saturated pulse energy and timing recovery than a traditional
saturation-knee/template correction.  The worker was `testbeam-laptop-3`.  Before fitting
any model, the raw ROOT selected-pulse anchor was reproduced exactly:
`640737` selected B-stave pulses versus the reference
`640737`, with delta `0`.

The winner is `template_residual_boosted_stack_new` by the predeclared composite ordering

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`,

where `sigma_E` is held-out fractional energy sigma68, `sigma_t` is constituent
timing sigma68 in ns, and the final two terms penalize missed injected pile-up and
false splitting of clean controls.  `template_residual_boosted_stack_new` obtains `sigma_E =
0.07114` with 95% run-block bootstrap CI
[0.06621,
0.07946] and timing sigma68
`7.927` ns.

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
| template_residual_boosted_stack_new |         0.1743 |                -0.003996 |                     0.07114 |                            0.06621 |                             0.07946 |        -1.067  |             7.927 |                    7.53  |                     8.483 |             0.2917 |             0.1861 |
| gradient_boosted_trees              |         0.1768 |                 0.003006 |                     0.06928 |                            0.06361 |                             0.07232 |        -0.4942 |             8.459 |                    7.85  |                     8.946 |             0.2917 |             0.1667 |
| ridge                               |         0.1991 |                 0.001593 |                     0.07657 |                            0.06463 |                             0.08183 |        -0.4572 |             9.861 |                    9.304 |                    10.7   |             0.2833 |             0.1944 |
| 1d_cnn                              |         0.2067 |                 0.02593  |                     0.08202 |                            0.06662 |                             0.09077 |        -0.628  |            10.04  |                    9.452 |                    10.5   |             0.2611 |             0.225  |
| two_pulse_template_cfd_baseline     |         0.2117 |                 0.01157  |                     0.08415 |                            0.06696 |                             0.1004  |         0.9879 |             9.033 |                    6.927 |                    10.69  |             0.5694 |             0.175  |
| mlp                                 |         0.2716 |                -0.005274 |                     0.129   |                            0.1092  |                             0.1485  |        -0.8408 |            12.01  |                   11.39  |                    12.94  |             0.3    |             0.15   |
| tiny_sequence_transformer           |         0.3225 |                 0.1174   |                     0.1317  |                            0.1201  |                             0.1481  |        -5.039  |            16.25  |                   14.64  |                    18.07  |             0.4278 |             0.1389 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.01301`
and timing sigma68 by `-1.106` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                0.02081   |                     0.06647 |       -0.02704 |             8.367 |             0.3056 |            0.3472  |
| 1d_cnn                              |            60 |                0.04934   |                     0.08319 |        0.1798  |            10.46  |             0.1667 |            0.2222  |
| 1d_cnn                              |            62 |                0.03652   |                     0.05736 |       -1.26    |            10.71  |             0.25   |            0.2222  |
| 1d_cnn                              |            64 |                0.01004   |                     0.0953  |       -1.633   |             9.662 |             0.2639 |            0.1806  |
| 1d_cnn                              |            65 |                0.006978  |                     0.07121 |       -0.7682  |             9.549 |             0.3194 |            0.1528  |
| gradient_boosted_trees              |            58 |                0.003787  |                     0.06863 |        0.04123 |             8.237 |             0.2639 |            0.2083  |
| gradient_boosted_trees              |            60 |                0.01838   |                     0.07064 |       -0.425   |             8.489 |             0.1806 |            0.1528  |
| gradient_boosted_trees              |            62 |                0.00732   |                     0.05211 |       -0.2542  |             7.249 |             0.2778 |            0.2083  |
| gradient_boosted_trees              |            64 |               -0.01275   |                     0.07129 |       -0.7573  |             8.323 |             0.3889 |            0.1528  |
| gradient_boosted_trees              |            65 |               -0.0174    |                     0.05741 |       -1.061   |             8.837 |             0.3472 |            0.1111  |
| mlp                                 |            58 |               -0.005434  |                     0.1509  |       -1.364   |            12.12  |             0.25   |            0.2222  |
| mlp                                 |            60 |                0.01823   |                     0.1417  |       -1.325   |            11.06  |             0.2083 |            0.1667  |
| mlp                                 |            62 |               -0.004613  |                     0.1045  |        0.8769  |            13.18  |             0.3333 |            0.1806  |
| mlp                                 |            64 |               -0.0005992 |                     0.1056  |       -1.441   |            10.65  |             0.3472 |            0.09722 |
| mlp                                 |            65 |               -0.02792   |                     0.1181  |       -1.409   |            12.58  |             0.3611 |            0.08333 |
| ridge                               |            58 |               -0.01982   |                     0.0749  |       -1.152   |            10.1   |             0.2639 |            0.2639  |
| ridge                               |            60 |                0.01757   |                     0.05905 |        0.5681  |             9.503 |             0.1667 |            0.2639  |
| ridge                               |            62 |                0.01954   |                     0.07304 |        1.209   |             8.959 |             0.2778 |            0.1944  |
| ridge                               |            64 |               -0.01535   |                     0.08782 |       -2.012   |             8.976 |             0.3333 |            0.09722 |
| ridge                               |            65 |               -0.02081   |                     0.07655 |       -0.6379  |            11.08  |             0.375  |            0.1528  |
| template_residual_boosted_stack_new |            58 |               -0.003604  |                     0.08432 |       -0.2655  |             7.401 |             0.2639 |            0.25    |
| template_residual_boosted_stack_new |            60 |                0.007702  |                     0.06652 |       -1.309   |             7.513 |             0.1389 |            0.2222  |
| template_residual_boosted_stack_new |            62 |               -0.0139    |                     0.06685 |       -0.7933  |             7.181 |             0.3194 |            0.1389  |
| template_residual_boosted_stack_new |            64 |               -0.003996  |                     0.06742 |       -2.212   |             8.29  |             0.3472 |            0.1806  |
| template_residual_boosted_stack_new |            65 |               -0.03652   |                     0.06939 |       -0.5475  |             8.698 |             0.3889 |            0.1389  |
| tiny_sequence_transformer           |            58 |                0.07124   |                     0.1197  |       -2.275   |            13.5   |             0.4028 |            0.1806  |
| tiny_sequence_transformer           |            60 |                0.1342    |                     0.1225  |       -2.744   |            18.31  |             0.3472 |            0.1806  |
| tiny_sequence_transformer           |            62 |                0.1371    |                     0.1519  |        0.4273  |            16.02  |             0.5139 |            0.1806  |
| tiny_sequence_transformer           |            64 |                0.1027    |                     0.1421  |       -6.432   |            14.75  |             0.4306 |            0.06944 |
| tiny_sequence_transformer           |            65 |                0.1032    |                     0.1264  |       -9.504   |            14.5   |             0.4444 |            0.08333 |
| two_pulse_template_cfd_baseline     |            58 |                0.01431   |                     0.05827 |       -0.0843  |             6.772 |             0.5833 |            0.2361  |
| two_pulse_template_cfd_baseline     |            60 |                0.03346   |                     0.09976 |        1.797   |            10.27  |             0.4722 |            0.1806  |
| two_pulse_template_cfd_baseline     |            62 |                0.01061   |                     0.1158  |        0.9572  |            11.58  |             0.6111 |            0.2222  |
| two_pulse_template_cfd_baseline     |            64 |                0.001388  |                     0.07341 |        0.3872  |             6.175 |             0.5    |            0.1389  |
| two_pulse_template_cfd_baseline     |            65 |               -0.01157   |                     0.05088 |        1.489   |             9.809 |             0.6806 |            0.09722 |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:----------------|:---------------|:------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              |                0.04264   |                     0.06573 |       -0.5966  |            11.58  |            0.4078  |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              |                0.04146   |                     0.06846 |       -1.43    |             8.945 |            0.2683  |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              |                0.03031   |                     0.06504 |       -0.3527  |             8.357 |            0.25    |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              |               -0.0157    |                     0.08409 |        0.4484  |            12.37  |            0.09195 |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              |                0.0272    |                     0.05464 |        0.3648  |             7.794 |            0.4272  |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              |                0.02117   |                     0.05096 |        0.1497  |             6.899 |            0.3293  |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              |               -0.01753   |                     0.06436 |       -1.225   |             8.707 |            0.2727  |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              |               -0.04231   |                     0.06716 |       -0.9984  |            11.08  |            0.1149  |
| spacing_bin     | (-0.001, 10.0] | mlp                                 |                0.03318   |                     0.09237 |        2.369   |            11.79  |            0.4175  |
| spacing_bin     | (10.0, 25.0]   | mlp                                 |                0.02801   |                     0.1132  |        0.668   |            11.74  |            0.3293  |
| spacing_bin     | (25.0, 45.0]   | mlp                                 |               -0.02465   |                     0.1416  |       -0.9639  |            10.6   |            0.2955  |
| spacing_bin     | (45.0, 70.0]   | mlp                                 |               -0.0413    |                     0.1348  |       -5.111   |            14.26  |            0.1379  |
| spacing_bin     | (-0.001, 10.0] | ridge                               |                0.03911   |                     0.07376 |        0.7067  |            10.81  |            0.3883  |
| spacing_bin     | (10.0, 25.0]   | ridge                               |                0.03024   |                     0.05299 |       -0.4701  |             6.973 |            0.3415  |
| spacing_bin     | (25.0, 45.0]   | ridge                               |               -0.01151   |                     0.06245 |       -0.3268  |             9.643 |            0.2386  |
| spacing_bin     | (45.0, 70.0]   | ridge                               |               -0.06316   |                     0.06425 |       -1.439   |            12.39  |            0.1494  |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new |                0.01982   |                     0.06389 |        0.4235  |             7.884 |            0.4175  |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new |                0.008537  |                     0.06809 |        0.1033  |             5.996 |            0.3171  |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new |               -0.003996  |                     0.06528 |       -2.06    |             8.365 |            0.2841  |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new |               -0.05017   |                     0.07549 |       -1.781   |            10.57  |            0.1264  |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           |                0.1782    |                     0.1012  |       -3.379   |            12.66  |            0.5922  |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           |                0.1761    |                     0.1182  |       -7.674   |            12.98  |            0.6098  |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           |                0.1352    |                     0.09312 |       -3.934   |            16.05  |            0.3523  |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           |                0.00235   |                     0.1295  |       -5.334   |            20.58  |            0.1379  |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |                0.04352   |                     0.08698 |        3.359   |            13.18  |            0.7184  |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |                0.0222    |                     0.06571 |        0.9906  |             7.622 |            0.6707  |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |                0.009349  |                     0.06422 |        1.722   |             7.529 |            0.4773  |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |               -0.003774  |                     0.08855 |       -0.8611  |             9.572 |            0.3908  |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              |               -3.26e-05  |                     0.07399 |       -4.722   |             9.642 |            0.4023  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              |                0.01057   |                     0.09762 |       -1.48    |            11.12  |            0.2688  |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              |                0.03524   |                     0.06314 |       -0.03188 |             8.947 |            0.1818  |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              |                0.03595   |                     0.07535 |        1.747   |            10.1   |            0.1942  |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              |               -0.00223   |                     0.04663 |       -1.913   |             9.639 |            0.4253  |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              |                0.01389   |                     0.06539 |       -0.7567  |             9.629 |            0.3656  |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              |                0.005418  |                     0.07734 |       -1.063   |             6.651 |            0.2078  |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              |               -0.004908  |                     0.07506 |        0.9186  |             7.901 |            0.1748  |
| ratio_bin       | (-0.001, 0.35] | mlp                                 |                0.00769   |                     0.1241  |       -3.608   |            10.93  |            0.4598  |
| ratio_bin       | (0.35, 0.625]  | mlp                                 |                0.02188   |                     0.1252  |       -0.8905  |            12.83  |            0.3763  |
| ratio_bin       | (0.625, 0.875] | mlp                                 |                0.01212   |                     0.1327  |        0.5871  |            11.33  |            0.2078  |
| ratio_bin       | (0.875, 1.05]  | mlp                                 |               -0.03698   |                     0.1242  |        0.248   |            10.81  |            0.165   |
| ratio_bin       | (-0.001, 0.35] | ridge                               |               -0.01615   |                     0.06889 |       -4.773   |             9.55  |            0.4253  |
| ratio_bin       | (0.35, 0.625]  | ridge                               |                0.00343   |                     0.08432 |        0.0887  |            10.19  |            0.3763  |
| ratio_bin       | (0.625, 0.875] | ridge                               |                0.008173  |                     0.05818 |       -0.8248  |             8.453 |            0.1818  |
| ratio_bin       | (0.875, 1.05]  | ridge                               |               -0.01079   |                     0.08652 |        1.986   |            10.99  |            0.1553  |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new |                0.005927  |                     0.07332 |       -2.272   |            10.09  |            0.4483  |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new |                0.007086  |                     0.06823 |       -1.377   |             9.062 |            0.3656  |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new |               -0.007025  |                     0.06713 |       -1.55    |             6.853 |            0.1688  |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new |               -0.007233  |                     0.07756 |        0.7751  |             7.487 |            0.1845  |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           |                0.1238    |                     0.1256  |       -8.046   |            17.22  |            0.5287  |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           |                0.1297    |                     0.1223  |       -6.638   |            15.86  |            0.4624  |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           |                0.08892   |                     0.1442  |       -3.26    |            15.6   |            0.3766  |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           |                0.1342    |                     0.1406  |       -4.757   |            16.13  |            0.3495  |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |                0.005357  |                     0.09317 |       -1.473   |            13.9   |            0.5747  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |                0.02079   |                     0.08319 |       -0.04657 |             8.626 |            0.5484  |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     |                0.00752   |                     0.09096 |        0.4181  |             9.528 |            0.5714  |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |                0.01157   |                     0.04817 |        2.735   |             7.389 |            0.5825  |
| stave           | B2             | 1d_cnn                              |               -0.03553   |                     0.06603 |       -6.562   |            11.26  |            0.4205  |
| stave           | B4             | 1d_cnn                              |                0.05722   |                     0.06461 |       -1.896   |             8.694 |            0.284   |
| stave           | B6             | 1d_cnn                              |                0.006978  |                     0.06631 |       -0.2951  |             9.257 |            0.2697  |
| stave           | B8             | 1d_cnn                              |                0.02985   |                     0.07134 |        2.951   |             8.83  |            0.09804 |
| stave           | B2             | gradient_boosted_trees              |               -0.04748   |                     0.08557 |       -5.565   |             9.505 |            0.4205  |
| stave           | B4             | gradient_boosted_trees              |                0.02086   |                     0.05315 |       -1.855   |             7.136 |            0.2346  |
| stave           | B6             | gradient_boosted_trees              |                0.005102  |                     0.05489 |        0.2414  |             7.31  |            0.3483  |
| stave           | B8             | gradient_boosted_trees              |                0.004268  |                     0.06665 |        2.229   |             7.442 |            0.1765  |
| stave           | B2             | mlp                                 |               -0.02534   |                     0.1304  |       -3.544   |            15.74  |            0.4545  |
| stave           | B4             | mlp                                 |                0.02942   |                     0.1187  |       -3.741   |            11.06  |            0.2593  |
| stave           | B6             | mlp                                 |               -0.01119   |                     0.1171  |       -1.105   |             9.694 |            0.3596  |
| stave           | B8             | mlp                                 |               -0.01508   |                     0.1229  |        2.952   |            11.78  |            0.1471  |
| stave           | B2             | ridge                               |               -0.04895   |                     0.09645 |       -7.023   |            12.51  |            0.4091  |
| stave           | B4             | ridge                               |                0.02897   |                     0.05708 |       -2.011   |             7.961 |            0.3086  |
| stave           | B6             | ridge                               |               -0.009014  |                     0.0622  |        0.2805  |             9.637 |            0.3146  |
| stave           | B8             | ridge                               |                0.002366  |                     0.07451 |        3.292   |             8.278 |            0.1275  |
| stave           | B2             | template_residual_boosted_stack_new |               -0.03284   |                     0.08904 |       -6.052   |             8.945 |            0.4318  |
| stave           | B4             | template_residual_boosted_stack_new |                1.335e-05 |                     0.07622 |       -1.765   |             7.046 |            0.2716  |
| stave           | B6             | template_residual_boosted_stack_new |               -0.0002272 |                     0.05902 |       -0.6316  |             7.576 |            0.3371  |
| stave           | B8             | template_residual_boosted_stack_new |                0.002948  |                     0.07256 |        1.577   |             7.494 |            0.1471  |
| stave           | B2             | tiny_sequence_transformer           |                0.04933   |                     0.1661  |      -15.34    |            22.41  |            0.5682  |
| stave           | B4             | tiny_sequence_transformer           |                0.1371    |                     0.1279  |       -7.905   |            15.86  |            0.4321  |
| stave           | B6             | tiny_sequence_transformer           |                0.1125    |                     0.1232  |       -2.529   |            13.34  |            0.4494  |
| stave           | B8             | tiny_sequence_transformer           |                0.1299    |                     0.1326  |        0.09124 |            14.42  |            0.2843  |
| stave           | B2             | two_pulse_template_cfd_baseline     |                0.04649   |                     0.05089 |       -2.644   |            15.61  |            0.6818  |
| stave           | B4             | two_pulse_template_cfd_baseline     |               -0.006848  |                     0.06449 |        0.591   |            16.04  |            0.9012  |
| stave           | B6             | two_pulse_template_cfd_baseline     |               -0.04973   |                     0.05749 |       -0.1679  |             9.797 |            0.4944  |
| stave           | B8             | two_pulse_template_cfd_baseline     |                0.03085   |                     0.08032 |        1.651   |             5.385 |            0.2745  |
| saturated_proxy | False          | 1d_cnn                              |                0.02781   |                     0.08258 |       -0.4313  |             9.764 |            0.2711  |
| saturated_proxy | True           | 1d_cnn                              |               -0.02503   |                     0.05464 |       -6.252   |            10.46  |            0.05882 |
| saturated_proxy | False          | gradient_boosted_trees              |                0.003787  |                     0.06986 |       -0.1354  |             8.305 |            0.3032  |
| saturated_proxy | True           | gradient_boosted_trees              |               -0.0552    |                     0.05955 |       -6.767   |             6.885 |            0.05882 |
| saturated_proxy | False          | mlp                                 |               -0.005815  |                     0.1299  |       -0.8905  |            12.12  |            0.3149  |
| saturated_proxy | True           | mlp                                 |               -0.0005992 |                     0.1025  |       -0.2507  |            11.23  |            0       |
| saturated_proxy | False          | ridge                               |                0.004984  |                     0.07513 |       -0.03657 |             9.572 |            0.2974  |
| saturated_proxy | True           | ridge                               |               -0.06333   |                     0.06435 |       -8.66    |            10.55  |            0       |
| saturated_proxy | False          | template_residual_boosted_stack_new |               -0.001937  |                     0.07142 |       -0.7881  |             7.98  |            0.3032  |
| saturated_proxy | True           | template_residual_boosted_stack_new |               -0.02737   |                     0.07483 |       -6.706   |             6.829 |            0.05882 |
| saturated_proxy | False          | tiny_sequence_transformer           |                0.1281    |                     0.1349  |       -4.309   |            16.02  |            0.4286  |
| saturated_proxy | True           | tiny_sequence_transformer           |                0.01835   |                     0.06223 |      -19.12    |            14.04  |            0.4118  |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     |                0.007882  |                     0.0883  |        0.9879  |             8.947 |            0.5714  |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     |                0.03672   |                     0.03579 |        1.046   |             8.577 |            0.5294  |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `332.4` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.


## Injection-source bootstrap

The run-block intervals above answer whether the ranking transfers across held-out
runs.  As a complementary stress test, `injection_source_bootstrap_ci.csv`
resamples retained source cells defined by
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This unit preserves the
run-local residual source, detector stave/PID proxy, pile-up label, separation
family, and amplitude-ratio family rather than treating individual synthetic
events as independent draws.

| method                              |   n_source_units |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   detection_ap |   detection_ap_ci_low |   detection_ap_ci_high |
|:------------------------------------|-----------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|---------------:|----------------------:|-----------------------:|
| gradient_boosted_trees              |              210 |                     0.06928 |                            0.06016 |                             0.07851 |             8.459 |                    7.529 |                     9.144 |         0.8516 |                0.7833 |                 0.9053 |
| template_residual_boosted_stack_new |              210 |                     0.07114 |                            0.06365 |                             0.08433 |             7.927 |                    7.269 |                     9.043 |         0.8524 |                0.7845 |                 0.9127 |
| ridge                               |              210 |                     0.07657 |                            0.06759 |                             0.08532 |             9.861 |                    8.99  |                    10.89  |         0.819  |                0.7391 |                 0.8972 |
| 1d_cnn                              |              210 |                     0.08202 |                            0.07101 |                             0.08873 |            10.04  |                    9.187 |                    10.95  |         0.8293 |                0.7593 |                 0.9021 |
| two_pulse_template_cfd_baseline     |              210 |                     0.08415 |                            0.06904 |                             0.09698 |             9.033 |                    7.141 |                    11.68  |         0.6866 |                0.6045 |                 0.7872 |
| mlp                                 |              210 |                     0.129   |                            0.1065  |                             0.1468  |            12.01  |                   10.88  |                    13.02  |         0.841  |                0.7703 |                 0.9033 |
| tiny_sequence_transformer           |              210 |                     0.1317  |                            0.1143  |                             0.1569  |            16.25  |                   14.7   |                    18.25  |         0.8042 |                0.7224 |                 0.8855 |

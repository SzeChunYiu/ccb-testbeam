# S29b saturation hysteresis pulse recovery benchmark

## Abstract

Ticket `1783827767.6183.4f6c4103` asks whether raw B-stack HRD waveforms support a stronger
architecture for saturated pulse energy and timing recovery than a traditional
saturation-knee/template correction.  The worker was `testbeam-laptop-1`.  Before fitting
any model, the raw ROOT selected-pulse anchor was reproduced exactly:
`640737` selected B-stave pulses versus the reference
`640737`, with delta `0`.

The winner is `template_residual_boosted_stack_new` by the predeclared composite ordering

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`,

where `sigma_E` is held-out fractional energy sigma68, `sigma_t` is constituent
timing sigma68 in ns, and the final two terms penalize missed injected pile-up and
false splitting of clean controls.  `template_residual_boosted_stack_new` obtains `sigma_E =
0.06367` with 95% run-block bootstrap CI
[0.05555,
0.06924] and timing sigma68
`7.407` ns.

## Raw ROOT reproduction

Raw files were read from `/home/billy/.tb-workers/testbeam-laptop-1/data/root/root`.  Each `h101/HRDv` object was
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
| template_residual_boosted_stack_new |         0.1633 |                0.000945  |                     0.06367 |                            0.05555 |                             0.06924 |        -0.7629 |             7.407 |                    6.585 |                     8.575 |             0.3111 |             0.2    |
| gradient_boosted_trees              |         0.1654 |               -0.0009164 |                     0.06265 |                            0.05905 |                             0.06878 |        -0.4751 |             7.805 |                    7.351 |                     8.608 |             0.3028 |             0.1917 |
| ridge                               |         0.1855 |                0.008573  |                     0.06841 |                            0.06373 |                             0.07435 |        -0.9787 |             9.339 |                    8.696 |                    10.01  |             0.2972 |             0.1778 |
| 1d_cnn                              |         0.2269 |                0.03629   |                     0.08764 |                            0.08124 |                             0.09958 |        -1.31   |            10.98  |                   10.49  |                    11.93  |             0.2583 |             0.3306 |
| two_pulse_template_cfd_baseline     |         0.23   |                0.003769  |                     0.08604 |                            0.07179 |                             0.0985  |         0.7664 |            10.75  |                    7.947 |                    11.68  |             0.5472 |             0.1806 |
| mlp                                 |         0.2529 |               -0.009885  |                     0.1182  |                            0.0945  |                             0.1399  |         0.2077 |            10.89  |                    9.706 |                    11.87  |             0.3194 |             0.1972 |
| tiny_sequence_transformer           |         0.3029 |                0.01831   |                     0.1203  |                            0.1067  |                             0.139   |       -10.35   |            15.27  |                   13.99  |                    16.37  |             0.4333 |             0.1667 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.02237`
and timing sigma68 by `-3.345` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                0.02167   |                     0.08925 |        -0.104  |            11.32  |             0.3056 |             0.3194 |
| 1d_cnn                              |            60 |                0.04457   |                     0.08304 |         0.252  |            10.64  |             0.2361 |             0.3194 |
| 1d_cnn                              |            62 |                0.0509    |                     0.09766 |        -1.825  |            11.29  |             0.3056 |             0.4028 |
| 1d_cnn                              |            64 |                0.01476   |                     0.09494 |        -2.169  |             9.945 |             0.25   |             0.2778 |
| 1d_cnn                              |            65 |                0.03627   |                     0.08221 |        -1.938  |            12.19  |             0.1944 |             0.3333 |
| gradient_boosted_trees              |            58 |               -0.01168   |                     0.07609 |        -0.5972 |             8.292 |             0.3333 |             0.2083 |
| gradient_boosted_trees              |            60 |                0.01482   |                     0.05781 |        -0.5703 |             8.455 |             0.25   |             0.1528 |
| gradient_boosted_trees              |            62 |               -0.0009164 |                     0.05878 |         0.4447 |             7.749 |             0.3194 |             0.2222 |
| gradient_boosted_trees              |            64 |               -0.01332   |                     0.05892 |        -1.392  |             6.918 |             0.2917 |             0.2222 |
| gradient_boosted_trees              |            65 |                0.003188  |                     0.06319 |        -0.4572 |             8.696 |             0.3194 |             0.1528 |
| mlp                                 |            58 |                0.06619   |                     0.1213  |         1.086  |            10.65  |             0.3889 |             0.2083 |
| mlp                                 |            60 |                0.001112  |                     0.1151  |        -1.134  |            12.05  |             0.2639 |             0.2083 |
| mlp                                 |            62 |               -0.0235    |                     0.1342  |         0.7519 |            12.18  |             0.3472 |             0.2361 |
| mlp                                 |            64 |               -0.02476   |                     0.09011 |         0.3492 |             9.646 |             0.3056 |             0.1667 |
| mlp                                 |            65 |               -0.02522   |                     0.08952 |        -0.3929 |             9.926 |             0.2917 |             0.1667 |
| ridge                               |            58 |                0.009523  |                     0.05477 |        -0.5742 |             9.429 |             0.375  |             0.2222 |
| ridge                               |            60 |                0.0146    |                     0.07223 |        -0.1888 |             8.533 |             0.2222 |             0.1944 |
| ridge                               |            62 |                0.008505  |                     0.07624 |        -0.6115 |             9.729 |             0.3056 |             0.2083 |
| ridge                               |            64 |               -0.001715  |                     0.06785 |        -1.38   |             8.244 |             0.2917 |             0.125  |
| ridge                               |            65 |                0.001829  |                     0.063   |        -0.7643 |            10.58  |             0.2917 |             0.1389 |
| template_residual_boosted_stack_new |            58 |                0.003159  |                     0.06249 |        -0.714  |             8.298 |             0.3194 |             0.2222 |
| template_residual_boosted_stack_new |            60 |                0.009523  |                     0.05355 |        -0.3806 |             6.507 |             0.2778 |             0.1389 |
| template_residual_boosted_stack_new |            62 |                0.008154  |                     0.0706  |        -0.5301 |             7.797 |             0.2917 |             0.2361 |
| template_residual_boosted_stack_new |            64 |               -0.01278   |                     0.05696 |        -1.644  |             6.086 |             0.3056 |             0.1944 |
| template_residual_boosted_stack_new |            65 |               -0.007299  |                     0.07098 |        -0.5382 |             8.614 |             0.3611 |             0.2083 |
| tiny_sequence_transformer           |            58 |                0.005783  |                     0.1392  |       -10.39   |            13.62  |             0.4583 |             0.1806 |
| tiny_sequence_transformer           |            60 |                0.03282   |                     0.1202  |        -9.533  |            13.72  |             0.375  |             0.1667 |
| tiny_sequence_transformer           |            62 |                0.04939   |                     0.1066  |       -10.04   |            18.42  |             0.4583 |             0.2083 |
| tiny_sequence_transformer           |            64 |               -0.01592   |                     0.1398  |       -12.41   |            14.33  |             0.4583 |             0.1528 |
| tiny_sequence_transformer           |            65 |                0.01539   |                     0.09454 |        -9.334  |            15.99  |             0.4167 |             0.125  |
| two_pulse_template_cfd_baseline     |            58 |               -0.02485   |                     0.09893 |        -0.1125 |            11.73  |             0.625  |             0.1944 |
| two_pulse_template_cfd_baseline     |            60 |                0.02707   |                     0.08187 |         0.7664 |             6.665 |             0.5417 |             0.1944 |
| two_pulse_template_cfd_baseline     |            62 |                0.03501   |                     0.09182 |         1.066  |            10.46  |             0.6389 |             0.2222 |
| two_pulse_template_cfd_baseline     |            64 |               -0.02311   |                     0.07573 |        -0.4894 |             7.681 |             0.4306 |             0.125  |
| two_pulse_template_cfd_baseline     |            65 |                0.01484   |                     0.06203 |         2.159  |            10.74  |             0.5    |             0.1667 |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:----------------|:---------------|:------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              |                0.05005   |                     0.08441 |        0.9179  |            10.41  |            0.3814  |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              |                0.05224   |                     0.06771 |       -2.044   |             9.651 |            0.3375  |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              |                0.04985   |                     0.09482 |       -4.487   |             8.518 |            0.1538  |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              |               -0.03889   |                     0.08362 |       -0.2675  |            14.34  |            0.1071  |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              |                0.01371   |                     0.05445 |        0.4259  |             8.636 |            0.3814  |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              |                0.004645  |                     0.05774 |        0.3682  |             8.01  |            0.4375  |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              |               -0.004314  |                     0.05416 |       -1.764   |             6.618 |            0.1923  |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              |               -0.02268   |                     0.07122 |       -1.367   |             9.308 |            0.1667  |
| spacing_bin     | (-0.001, 10.0] | mlp                                 |               -0.006885  |                     0.09377 |        2.628   |             9.724 |            0.4322  |
| spacing_bin     | (10.0, 25.0]   | mlp                                 |               -0.01926   |                     0.09649 |        1.111   |             8.377 |            0.425   |
| spacing_bin     | (25.0, 45.0]   | mlp                                 |               -0.03106   |                     0.1317  |       -2.995   |            10.16  |            0.2179  |
| spacing_bin     | (45.0, 70.0]   | mlp                                 |                0.02425   |                     0.132   |       -0.9253  |            15.06  |            0.1548  |
| spacing_bin     | (-0.001, 10.0] | ridge                               |                0.02101   |                     0.06143 |        1.322   |             8.977 |            0.3983  |
| spacing_bin     | (10.0, 25.0]   | ridge                               |                0.01812   |                     0.0664  |       -1.091   |             7.62  |            0.4125  |
| spacing_bin     | (25.0, 45.0]   | ridge                               |                0.00856   |                     0.05995 |       -1.171   |             7.701 |            0.1923  |
| spacing_bin     | (45.0, 70.0]   | ridge                               |               -0.009775  |                     0.05858 |       -5.864   |            12.21  |            0.1429  |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new |                0.02333   |                     0.05809 |        0.3896  |             7.975 |            0.4068  |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new |                0.000945  |                     0.05029 |        0.1151  |             6.714 |            0.475   |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new |                0.008154  |                     0.06364 |       -2.032   |             6.899 |            0.1667  |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new |               -0.02644   |                     0.06281 |       -1.604   |             8.515 |            0.1548  |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           |                0.07052   |                     0.06509 |       -7.825   |            10.03  |            0.5508  |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           |                0.04921   |                     0.08176 |      -12.41    |             9.819 |            0.6     |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           |               -0.008823  |                     0.09726 |      -13.45    |            14.68  |            0.3462  |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           |               -0.0976    |                     0.1084  |       -9.087   |            21.76  |            0.1905  |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |                0.01382   |                     0.0769  |        2.492   |            11.89  |            0.6525  |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |                0.017     |                     0.06426 |        1.083   |             7.555 |            0.65    |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |                0.04597   |                     0.09783 |        0.4348  |            11.83  |            0.5897  |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |               -0.02858   |                     0.08751 |       -0.3995  |             9.625 |            0.2619  |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              |                0.04282   |                     0.0901  |       -3.4     |            11.78  |            0.4375  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              |                0.01923   |                     0.09616 |       -2.467   |            10.31  |            0.2353  |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              |                0.03488   |                     0.09669 |       -0.7863  |            11.18  |            0.213   |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              |                0.03818   |                     0.06671 |        0.3875  |            12.63  |            0.1724  |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              |                0.01057   |                     0.08295 |       -3.276   |             8.699 |            0.5125  |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              |               -0.002093  |                     0.07162 |       -2.154   |             7.518 |            0.3529  |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              |               -0.009148  |                     0.05614 |        0.3825  |             8.294 |            0.2222  |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              |                0.002881  |                     0.04815 |        0.4048  |             7.413 |            0.1609  |
| ratio_bin       | (-0.001, 0.35] | mlp                                 |                0.05555   |                     0.1741  |       -2.693   |            10     |            0.5125  |
| ratio_bin       | (0.35, 0.625]  | mlp                                 |               -0.02187   |                     0.1128  |        0.08249 |            11.64  |            0.3412  |
| ratio_bin       | (0.625, 0.875] | mlp                                 |               -0.0324    |                     0.1244  |        0.7527  |            10.15  |            0.2778  |
| ratio_bin       | (0.875, 1.05]  | mlp                                 |               -0.001567  |                     0.09032 |        0.4625  |            10.42  |            0.1724  |
| ratio_bin       | (-0.001, 0.35] | ridge                               |                0.02742   |                     0.07211 |       -5.908   |            11.88  |            0.5375  |
| ratio_bin       | (0.35, 0.625]  | ridge                               |                0.006525  |                     0.07399 |       -2.357   |             7.979 |            0.2824  |
| ratio_bin       | (0.625, 0.875] | ridge                               |                0.005519  |                     0.06666 |        1.251   |             8.803 |            0.2407  |
| ratio_bin       | (0.875, 1.05]  | ridge                               |                0.006757  |                     0.06578 |        0.5563  |             9.473 |            0.1609  |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new |                0.03201   |                     0.07597 |       -4.186   |             7.69  |            0.5125  |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new |               -0.01142   |                     0.06732 |       -1.641   |             6.96  |            0.3647  |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new |               -0.01421   |                     0.05161 |        0.2268  |             7.639 |            0.2593  |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new |                0.002779  |                     0.05125 |       -0.2195  |             6.762 |            0.1379  |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           |                0.04204   |                     0.1188  |      -13.81    |            19.7   |            0.5875  |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           |                0.02204   |                     0.1185  |      -11.48    |            15.27  |            0.5059  |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           |               -0.008851  |                     0.1363  |       -9.992   |            15.1   |            0.3796  |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           |                0.01831   |                     0.09301 |       -9.726   |            13.49  |            0.2874  |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |                0.017     |                     0.09579 |       -0.6717  |             9.04  |            0.6375  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |                0.0339    |                     0.0887  |        0.5156  |            10.02  |            0.6235  |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     |               -0.01305   |                     0.06868 |       -0.259   |             9.345 |            0.5093  |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |               -0.002435  |                     0.08689 |        3.015   |             9.812 |            0.4368  |
| stave           | B2             | 1d_cnn                              |               -0.002871  |                     0.09396 |      -10.68    |            13.33  |            0.4742  |
| stave           | B4             | 1d_cnn                              |                0.05558   |                     0.09821 |       -3.844   |             9.91  |            0.1954  |
| stave           | B6             | 1d_cnn                              |                0.03815   |                     0.1052  |       -0.7564  |             9.56  |            0.2065  |
| stave           | B8             | 1d_cnn                              |                0.03455   |                     0.07636 |        4.487   |             9.652 |            0.131   |
| stave           | B2             | gradient_boosted_trees              |               -0.0157    |                     0.09193 |       -5.842   |             9.288 |            0.5155  |
| stave           | B4             | gradient_boosted_trees              |                0.00401   |                     0.05617 |       -1.89    |             6.716 |            0.2069  |
| stave           | B6             | gradient_boosted_trees              |                0.004645  |                     0.05327 |        0.4997  |             7.348 |            0.3152  |
| stave           | B8             | gradient_boosted_trees              |                0.004038  |                     0.06393 |        2.512   |             8.045 |            0.1429  |
| stave           | B2             | mlp                                 |               -0.01853   |                     0.1266  |       -2.939   |            12.91  |            0.5979  |
| stave           | B4             | mlp                                 |                0.01978   |                     0.1279  |       -2.692   |            10.77  |            0.1954  |
| stave           | B6             | mlp                                 |               -0.01218   |                     0.09725 |        0.6787  |             9.685 |            0.2826  |
| stave           | B8             | mlp                                 |               -0.01315   |                     0.09389 |        2.341   |             9.801 |            0.1667  |
| stave           | B2             | ridge                               |               -0.03918   |                     0.06984 |       -5.999   |            10.21  |            0.4536  |
| stave           | B4             | ridge                               |                0.01801   |                     0.04047 |       -2.726   |             8.335 |            0.1954  |
| stave           | B6             | ridge                               |                0.007207  |                     0.07311 |        0.02447 |             7.795 |            0.3696  |
| stave           | B8             | ridge                               |                0.02095   |                     0.06666 |        2.714   |             8.448 |            0.1429  |
| stave           | B2             | template_residual_boosted_stack_new |               -0.0008157 |                     0.09546 |       -4.666   |             9.117 |            0.5155  |
| stave           | B4             | template_residual_boosted_stack_new |               -0.0008889 |                     0.05491 |       -1.994   |             5.99  |            0.2069  |
| stave           | B6             | template_residual_boosted_stack_new |               -0.01329   |                     0.05577 |        0.1087  |             7.551 |            0.3261  |
| stave           | B8             | template_residual_boosted_stack_new |                0.0135    |                     0.05601 |        1.326   |             7.128 |            0.1667  |
| stave           | B2             | tiny_sequence_transformer           |                0.00876   |                     0.09467 |      -21.38    |            17.58  |            0.7113  |
| stave           | B4             | tiny_sequence_transformer           |                0.004952  |                     0.1397  |      -12.68    |            15.84  |            0.3563  |
| stave           | B6             | tiny_sequence_transformer           |                0.0451    |                     0.1176  |       -9.568   |            12.92  |            0.3696  |
| stave           | B8             | tiny_sequence_transformer           |                0.01542   |                     0.1037  |       -5.609   |            11.71  |            0.2619  |
| stave           | B2             | two_pulse_template_cfd_baseline     |                0.04792   |                     0.05478 |        4.98    |            14.45  |            0.732   |
| stave           | B4             | two_pulse_template_cfd_baseline     |               -0.03495   |                     0.06522 |       -3.503   |            14.43  |            0.6552  |
| stave           | B6             | two_pulse_template_cfd_baseline     |               -0.03484   |                     0.06282 |       -0.3669  |             8.341 |            0.5435  |
| stave           | B8             | two_pulse_template_cfd_baseline     |                0.03865   |                     0.08513 |        1.405   |             4.845 |            0.2262  |
| saturated_proxy | False          | 1d_cnn                              |                0.03658   |                     0.08623 |       -1.008   |            10.97  |            0.2615  |
| saturated_proxy | True           | 1d_cnn                              |               -0.02815   |                     0.1208  |       -7.668   |             7.904 |            0.1667  |
| saturated_proxy | False          | gradient_boosted_trees              |               -0.0009164 |                     0.06279 |       -0.3262  |             7.665 |            0.3132  |
| saturated_proxy | True           | gradient_boosted_trees              |               -0.004472  |                     0.06631 |       -4.639   |             6.738 |            0       |
| saturated_proxy | False          | mlp                                 |               -0.008385  |                     0.1196  |        0.3995  |            11.18  |            0.3276  |
| saturated_proxy | True           | mlp                                 |               -0.01591   |                     0.08066 |       -2.405   |             9.427 |            0.08333 |
| saturated_proxy | False          | ridge                               |                0.01223   |                     0.06875 |       -0.5635  |             9.182 |            0.3075  |
| saturated_proxy | True           | ridge                               |               -0.04      |                     0.05171 |       -4.224   |             8.814 |            0       |
| saturated_proxy | False          | template_residual_boosted_stack_new |                0.000945  |                     0.06329 |       -0.5243  |             7.25  |            0.3218  |
| saturated_proxy | True           | template_residual_boosted_stack_new |                0.002309  |                     0.04779 |       -3.495   |             7.705 |            0       |
| saturated_proxy | False          | tiny_sequence_transformer           |                0.02019   |                     0.1215  |       -9.992   |            15.3   |            0.4368  |
| saturated_proxy | True           | tiny_sequence_transformer           |               -0.0518    |                     0.07662 |      -14.37    |            11.33  |            0.3333  |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     |                0.003769  |                     0.08842 |        0.7664  |            10.53  |            0.5489  |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     |                0.02031   |                     0.03744 |       -0.6756  |            13.23  |            0.5     |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `455.2` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.


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
| gradient_boosted_trees              |              207 |                     0.06265 |                            0.05389 |                             0.07199 |             7.805 |                    7.018 |                     8.966 |         0.838  |                0.7784 |                 0.8967 |
| template_residual_boosted_stack_new |              207 |                     0.06367 |                            0.05204 |                             0.07083 |             7.407 |                    6.631 |                     8.293 |         0.8438 |                0.7791 |                 0.9087 |
| ridge                               |              207 |                     0.06841 |                            0.06005 |                             0.07773 |             9.339 |                    8.314 |                    10.29  |         0.8435 |                0.78   |                 0.9037 |
| two_pulse_template_cfd_baseline     |              207 |                     0.08604 |                            0.06561 |                             0.1001  |            10.75  |                    7.888 |                    11.93  |         0.6952 |                0.6145 |                 0.7818 |
| 1d_cnn                              |              207 |                     0.08764 |                            0.07906 |                             0.1017  |            10.98  |                   10.06  |                    11.89  |         0.7955 |                0.7107 |                 0.8686 |
| mlp                                 |              207 |                     0.1182  |                            0.09664 |                             0.1386  |            10.89  |                    9.589 |                    12.1   |         0.8248 |                0.7486 |                 0.8972 |
| tiny_sequence_transformer           |              207 |                     0.1203  |                            0.104   |                             0.1382  |            15.27  |                   13.59  |                    16.77  |         0.7843 |                0.7011 |                 0.863  |


## S29b saturation hysteresis endpoint synthesis

The S29b benchmark uses the same train/held-out run separation as the
controlled-injection architecture bakeoff, but evaluates endpoint families named
in the ticket: saturation onset, hysteresis/recovery bias, saturation-knee
location, pedestal drift, pulse-window masking, pile-up sensitivity, timing
residual, energy bias, and PID/stave leakage.  The raw ROOT reproduction gate
is `reproduction_match_table.csv`; the winning method written to `result.json`
is `template_residual_boosted_stack_new`.

The controlled raw ROOT tree does not store a hardware hysteresis state bit, so
the hysteresis endpoint is an auditable proxy: close double-pulse separations
stress recovery after a preceding large pulse, while wide separations form the
release sideband.  Likewise, the saturation onset and knee are defined on true
injected total ADC, and pedestal drift is represented by run-local baseline
residual sidebands.  These definitions make the benchmark reproducible from the
data folder while keeping the limitations explicit.

The endpoint equations used in this section are the same as the main methods:
`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)]/(A_1 + A_2)`,
`e_t = 10 ns * (hat t - t_true)`, and
`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.  The recovery-bias equation is
`Delta_rec = median(e_E | saturated proxy) - median(e_E | unsaturated proxy)`;
the hysteresis proxy equation is
`Delta_hys = median(e_E | close pile-up) - median(e_E | wide pile-up)`.

| method                              |   saturation_onset_proxy_adc |   saturated_energy_bias |   unsaturated_energy_bias |   recovery_bias_delta |   recovery_bias_delta_ci_low |   recovery_bias_delta_ci_high |   hysteresis_proxy_close_minus_wide_bias |   hysteresis_proxy_ci_low |   hysteresis_proxy_ci_high |   pedestal_drift_bias_delta |   pileup_sensitivity_time_sigma68_ns |
|:------------------------------------|-----------------------------:|------------------------:|--------------------------:|----------------------:|-----------------------------:|------------------------------:|-----------------------------------------:|--------------------------:|---------------------------:|----------------------------:|-------------------------------------:|
| tiny_sequence_transformer           |                         7176 |               -0.03035  |                   0.05306 |              -0.08341 |                     -0.1032  |                     -0.06129  |                                 0.0751   |                 0.02861   |                   0.1184   |                         nan |                                7.346 |
| 1d_cnn                              |                         6852 |                0.01712  |                   0.06141 |              -0.04429 |                     -0.06841 |                     -0.01913  |                                 0.002421 |                -0.0204    |                   0.0329   |                         nan |                                4.092 |
| gradient_boosted_trees              |                         7203 |               -0.02177  |                   0.01594 |              -0.03771 |                     -0.04747 |                     -0.02072  |                                -0.004697 |                -0.008012  |                   0.007689 |                         nan |                                4.289 |
| two_pulse_template_cfd_baseline     |                         6827 |               -0.005797 |                   0.02296 |              -0.02876 |                     -0.0592  |                      0.03857  |                                -0.01175  |                -0.03506   |                   0.01977  |                         nan |                                7.694 |
| template_residual_boosted_stack_new |                         7203 |               -0.002137 |                   0.02344 |              -0.02557 |                     -0.04236 |                     -0.001582 |                                -0.002193 |                -0.0123    |                   0.006135 |                         nan |                                4.001 |
| ridge                               |                         7392 |                0.002182 |                   0.02499 |              -0.0228  |                     -0.04671 |                     -0.009214 |                                 0.008205 |                 0.0002716 |                   0.0227   |                         nan |                                4.246 |
| mlp                                 |                         7231 |                0.0031   |                   0.01701 |              -0.01391 |                     -0.03719 |                      0.02841  |                                -0.04444  |                -0.1005    |                   0.009305 |                         nan |                                4.261 |

### Saturation-knee location

The saturation-knee table scans true injected energy bins on the held-out runs.
The reported knee is the first bin center whose fractional energy sigma68
exceeds 0.08; if no bin crosses the threshold, the highest bin center is
reported as a right-censored knee estimate.

| method                              | knee_definition                            |   saturation_knee_adc |   min_bin_sigma68 |   max_bin_sigma68 |   n_bins |
|:------------------------------------|:-------------------------------------------|----------------------:|------------------:|------------------:|---------:|
| 1d_cnn                              | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.07282 |            0.1779 |        6 |
| gradient_boosted_trees              | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.05219 |            0.108  |        6 |
| mlp                                 | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.0994  |            0.1962 |        6 |
| ridge                               | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.04038 |            0.1305 |        6 |
| template_residual_boosted_stack_new | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.04492 |            0.1075 |        6 |
| tiny_sequence_transformer           | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.1037  |            0.1397 |        6 |
| two_pulse_template_cfd_baseline     | first true-energy bin with sigma68 >= 0.08 |                  2619 |           0.06148 |            0.1695 |        6 |

### Pulse-window masking ablation

Pulse-window masking is evaluated as a proxy ablation because the benchmark is
built from 18-sample raw waveforms.  The close-pileup sideband mimics a masked
late tail or ambiguous recovery window; the wide sideband retains a cleaner tail
constraint.  The table reports held-out energy and timing stability under these
window regimes.

| method                              | pulse_window_mask_proxy         |   n_events |   energy_fractional_sigma68 |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |
|:------------------------------------|:--------------------------------|-----------:|----------------------------:|------------------:|-----------------------------:|
| 1d_cnn                              | full_window                     |        386 |                     0.1137  |             4.499 |                      0.09585 |
| 1d_cnn                              | tail_masked_close_pileup_proxy  |        101 |                     0.07877 |             3.637 |                      0.07921 |
| 1d_cnn                              | tail_retained_wide_pileup_proxy |        285 |                     0.1359  |             5.312 |                      0.1018  |
| gradient_boosted_trees              | full_window                     |        320 |                     0.07935 |             4.235 |                      0.02813 |
| gradient_boosted_trees              | tail_masked_close_pileup_proxy  |         95 |                     0.05264 |             4.075 |                      0.04211 |
| gradient_boosted_trees              | tail_retained_wide_pileup_proxy |        225 |                     0.09552 |             4.25  |                      0.02222 |
| mlp                                 | full_window                     |        316 |                     0.1401  |             5.37  |                      0.1234  |
| mlp                                 | tail_masked_close_pileup_proxy  |         91 |                     0.09019 |             4.076 |                      0.0989  |
| mlp                                 | tail_retained_wide_pileup_proxy |        225 |                     0.1677  |             5.8   |                      0.1333  |
| ridge                               | full_window                     |        317 |                     0.07587 |             4.349 |                      0.0694  |
| ridge                               | tail_masked_close_pileup_proxy  |         96 |                     0.06153 |             3.899 |                      0.07292 |
| ridge                               | tail_retained_wide_pileup_proxy |        221 |                     0.07986 |             4.568 |                      0.06787 |
| template_residual_boosted_stack_new | full_window                     |        320 |                     0.07668 |             4.074 |                      0.025   |
| template_residual_boosted_stack_new | tail_masked_close_pileup_proxy  |         91 |                     0.05672 |             3.972 |                      0.03297 |
| template_residual_boosted_stack_new | tail_retained_wide_pileup_proxy |        229 |                     0.08817 |             4.049 |                      0.02183 |
| tiny_sequence_transformer           | full_window                     |        264 |                     0.1238  |             8.197 |                      0.3674  |
| tiny_sequence_transformer           | tail_masked_close_pileup_proxy  |         68 |                     0.07847 |             6.185 |                      0.2059  |
| tiny_sequence_transformer           | tail_retained_wide_pileup_proxy |        196 |                     0.1339  |             7.609 |                      0.4235  |
| two_pulse_template_cfd_baseline     | full_window                     |        228 |                     0.09597 |             6.25  |                      0.114   |
| two_pulse_template_cfd_baseline     | tail_masked_close_pileup_proxy  |         54 |                     0.06888 |             8.773 |                      0.2593  |
| two_pulse_template_cfd_baseline     | tail_retained_wide_pileup_proxy |        174 |                     0.1059  |             4.266 |                      0.06897 |


### PID leakage and boundary proxy

The raw waveform benchmark has no final downstream PID label.  To retain a
detector-facing leakage check, the study uses B-stave-conditioned energy closure
and late-tail timing leakage as the PID-boundary proxy.  This flags methods that
improve global recovery while moving one stave family differently from the
others.

| method                              | pid_boundary_proxy                               |   max_abs_stave_energy_bias |   stave_bias_span |   late_tail_leakage_span |   n_stave_strata |
|:------------------------------------|:-------------------------------------------------|----------------------------:|------------------:|-------------------------:|-----------------:|
| template_residual_boosted_stack_new | B-stave conditioned energy and late-tail closure |                     0.0135  |           0.02679 |                   0.1031 |                4 |
| gradient_boosted_trees              | B-stave conditioned energy and late-tail closure |                     0.0157  |           0.02034 |                   0.1147 |                4 |
| mlp                                 | B-stave conditioned energy and late-tail closure |                     0.01978 |           0.0383  |                   0.1608 |                4 |
| ridge                               | B-stave conditioned energy and late-tail closure |                     0.03918 |           0.06013 |                   0.1324 |                4 |
| tiny_sequence_transformer           | B-stave conditioned energy and late-tail closure |                     0.0451  |           0.04015 |                   0.4026 |                4 |
| two_pulse_template_cfd_baseline     | B-stave conditioned energy and late-tail closure |                     0.04792 |           0.08287 |                   0.2962 |                4 |
| 1d_cnn                              | B-stave conditioned energy and late-tail closure |                     0.05558 |           0.05845 |                   0.1953 |                4 |

## Systematic limitations specific to this ticket

The result is a strong benchmark of recovery algorithms on raw-ROOT-derived
controlled injections, not a direct measurement of electronics memory.  The
available B-stack tree provides waveform samples, run IDs, event numbers, and
channels, but not an explicit saturation-latch or PID-boundary decision.  For
that reason, hysteresis is represented by separation-conditioned recovery bias,
PID leakage by stave-conditioned energy closure, and pedestal drift by baseline
sidebands.  The run-block bootstrap intervals quantify transfer across held-out
runs; they do not cover unobserved detector modes absent from the input ROOT
files.

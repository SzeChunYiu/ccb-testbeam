# S29b pile-up saturation energy recovery study

## Abstract

Ticket `1783809165.2768.748951b9` asks whether raw B-stack HRD waveforms support a stronger
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
0.06265` with 95% run-block bootstrap CI
[0.05544,
0.06874] and timing sigma68
`7.813` ns.

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
| template_residual_boosted_stack_new |         0.1659 |                -0.004054 |                     0.06265 |                            0.05544 |                             0.06874 |        -0.741  |             7.813 |                    6.692 |                     8.654 |             0.325  |             0.1778 |
| gradient_boosted_trees              |         0.1717 |                 0.002403 |                     0.06556 |                            0.05973 |                             0.07584 |        -0.8147 |             7.971 |                    7.381 |                     8.358 |             0.3278 |             0.2    |
| ridge                               |         0.198  |                 0.01498  |                     0.07413 |                            0.0688  |                             0.07853 |        -2.157  |             9.883 |                    8.744 |                    10.48  |             0.2944 |             0.2056 |
| 1d_cnn                              |         0.2239 |                 0.004609 |                     0.09145 |                            0.08527 |                             0.1009  |        -3.186  |            10.45  |                    9.593 |                    11.12  |             0.25   |             0.3083 |
| two_pulse_template_cfd_baseline     |         0.2467 |                 0.002043 |                     0.09121 |                            0.07698 |                             0.1044  |         0.2538 |            11.41  |                    8.012 |                    14.26  |             0.5917 |             0.2361 |
| mlp                                 |         0.2884 |                 0.02153  |                     0.1272  |                            0.1119  |                             0.1441  |        -0.741  |            12.54  |                   11.13  |                    14.59  |             0.6    |             0.1167 |
| tiny_sequence_transformer           |         0.309  |                -0.01802  |                     0.142   |                            0.1325  |                             0.1499  |       -10.16   |            13.9   |                   13.23  |                    14.79  |             0.2889 |             0.2722 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.02856`
and timing sigma68 by `-3.592` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |               -0.005273  |                     0.07462 |        -3.046  |             8.317 |             0.2222 |            0.375   |
| 1d_cnn                              |            60 |                0.03549   |                     0.09106 |        -1.561  |            10.81  |             0.2361 |            0.2778  |
| 1d_cnn                              |            62 |               -0.01619   |                     0.08988 |        -4.487  |            10.18  |             0.2639 |            0.3056  |
| 1d_cnn                              |            64 |               -0.01657   |                     0.08917 |        -3.021  |            10.34  |             0.2639 |            0.2917  |
| 1d_cnn                              |            65 |                0.01803   |                     0.1007  |        -3.438  |            10.28  |             0.2639 |            0.2917  |
| gradient_boosted_trees              |            58 |                0.004127  |                     0.0684  |        -1.226  |             7.75  |             0.2222 |            0.2639  |
| gradient_boosted_trees              |            60 |                0.006793  |                     0.07375 |        -1.259  |             8.966 |             0.2917 |            0.2222  |
| gradient_boosted_trees              |            62 |                0.006513  |                     0.05978 |        -0.8087 |             7.166 |             0.4028 |            0.1667  |
| gradient_boosted_trees              |            64 |               -0.006972  |                     0.05694 |        -0.7785 |             7.486 |             0.3333 |            0.1528  |
| gradient_boosted_trees              |            65 |               -0.009398  |                     0.08551 |        -0.4755 |             7.395 |             0.3889 |            0.1944  |
| mlp                                 |            58 |               -0.009505  |                     0.1314  |        -0.8321 |             9.466 |             0.6389 |            0.1111  |
| mlp                                 |            60 |                0.04615   |                     0.1319  |         0.5474 |            12.5   |             0.5    |            0.1111  |
| mlp                                 |            62 |                0.03971   |                     0.1315  |        -1.125  |            13.54  |             0.6528 |            0.1667  |
| mlp                                 |            64 |               -0.00531   |                     0.1002  |        -0.9845 |            10.83  |             0.5556 |            0.08333 |
| mlp                                 |            65 |                0.01769   |                     0.1215  |        -1.121  |            14.95  |             0.6528 |            0.1111  |
| ridge                               |            58 |                0.005393  |                     0.07361 |        -2.023  |             9.821 |             0.2222 |            0.2361  |
| ridge                               |            60 |                0.03272   |                     0.06787 |        -0.417  |            10.69  |             0.2361 |            0.1944  |
| ridge                               |            62 |                0.001473  |                     0.07048 |        -3.425  |             9.359 |             0.3194 |            0.2222  |
| ridge                               |            64 |                0.01165   |                     0.06302 |        -2.211  |             7.674 |             0.3889 |            0.2083  |
| ridge                               |            65 |                0.007133  |                     0.08028 |        -1.597  |             8.385 |             0.3056 |            0.1667  |
| template_residual_boosted_stack_new |            58 |               -0.005514  |                     0.06559 |        -0.3002 |             7.706 |             0.1944 |            0.2361  |
| template_residual_boosted_stack_new |            60 |               -0.003453  |                     0.0621  |        -1.733  |             9.265 |             0.3056 |            0.1944  |
| template_residual_boosted_stack_new |            62 |                0.0009803 |                     0.04954 |        -0.4175 |             6.19  |             0.3889 |            0.1389  |
| template_residual_boosted_stack_new |            64 |               -0.008558  |                     0.05816 |        -0.5438 |             6.414 |             0.3194 |            0.1528  |
| template_residual_boosted_stack_new |            65 |               -0.00102   |                     0.07207 |        -1.035  |             7.745 |             0.4167 |            0.1667  |
| tiny_sequence_transformer           |            58 |               -0.04134   |                     0.1479  |       -10.91   |            12.89  |             0.2917 |            0.3194  |
| tiny_sequence_transformer           |            60 |               -0.01137   |                     0.1284  |        -7.461  |            15.09  |             0.2778 |            0.25    |
| tiny_sequence_transformer           |            62 |               -0.03084   |                     0.1278  |        -8.335  |            14.42  |             0.25   |            0.2639  |
| tiny_sequence_transformer           |            64 |               -0.01783   |                     0.1521  |       -11.42   |            14.11  |             0.3333 |            0.25    |
| tiny_sequence_transformer           |            65 |                0.009281  |                     0.1457  |       -12.58   |            13.35  |             0.2917 |            0.2778  |
| two_pulse_template_cfd_baseline     |            58 |                0.0009931 |                     0.0688  |        -1.088  |            10.39  |             0.5    |            0.2778  |
| two_pulse_template_cfd_baseline     |            60 |                0.003493  |                     0.08774 |         0.7137 |             6.047 |             0.6528 |            0.1944  |
| two_pulse_template_cfd_baseline     |            62 |               -0.001138  |                     0.1065  |        -0.1526 |            14.84  |             0.5139 |            0.25    |
| two_pulse_template_cfd_baseline     |            64 |               -0.006633  |                     0.07323 |        -0.9049 |             8.307 |             0.6528 |            0.25    |
| two_pulse_template_cfd_baseline     |            65 |                0.005362  |                     0.08662 |         1.688  |            11.43  |             0.6389 |            0.2083  |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:----------------|:---------------|:------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              |                0.04666   |                     0.07835 |      -1.558    |            12.54  |            0.2707  |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              |                0.02465   |                     0.07179 |      -2.226    |             8.191 |            0.2824  |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              |               -0.01657   |                     0.08337 |      -4.487    |             8.423 |            0.2388  |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              |               -0.08423   |                     0.06487 |      -5.011    |            10.74  |            0.1867  |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              |                0.02229   |                     0.04821 |      -0.03444  |             6.202 |            0.391   |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              |                0.006894  |                     0.07479 |      -0.7518   |             7.671 |            0.4     |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              |                0.001359  |                     0.05546 |      -1.542    |             8.102 |            0.2687  |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              |               -0.04323   |                     0.06883 |      -1.869    |             9.551 |            0.1867  |
| spacing_bin     | (-0.001, 10.0] | mlp                                 |                0.08691   |                     0.1287  |       1.037    |            10.49  |            0.6767  |
| spacing_bin     | (10.0, 25.0]   | mlp                                 |                0.02153   |                     0.1145  |      -1.019    |            11.45  |            0.6471  |
| spacing_bin     | (25.0, 45.0]   | mlp                                 |                0.0471    |                     0.128   |      -4.838    |            12.47  |            0.5672  |
| spacing_bin     | (45.0, 70.0]   | mlp                                 |               -0.04448   |                     0.1291  |      -0.9699   |            13.44  |            0.44    |
| spacing_bin     | (-0.001, 10.0] | ridge                               |                0.04217   |                     0.0596  |      -0.8573   |             9.357 |            0.2857  |
| spacing_bin     | (10.0, 25.0]   | ridge                               |                0.01715   |                     0.06427 |      -1.172    |             7.157 |            0.3647  |
| spacing_bin     | (25.0, 45.0]   | ridge                               |                0.003367  |                     0.06646 |      -2.98     |             9.479 |            0.2985  |
| spacing_bin     | (45.0, 70.0]   | ridge                               |               -0.04936   |                     0.0626  |      -5.724    |            13.77  |            0.2267  |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new |                0.01055   |                     0.05342 |      -0.004084 |             7.353 |            0.3684  |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new |                0.005011  |                     0.07695 |      -0.7523   |             8.597 |            0.4235  |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new |               -0.004182  |                     0.06274 |      -0.5284   |             8.222 |            0.2836  |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new |               -0.03682   |                     0.05961 |      -2.03     |             9.169 |            0.1733  |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           |                0.06968   |                     0.132   |      -9.013    |             9.457 |            0.3684  |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           |                0.02051   |                     0.117   |     -11.82     |            11.11  |            0.3647  |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           |               -0.01829   |                     0.1012  |     -11.57     |            17.59  |            0.1642  |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           |               -0.1516    |                     0.1125  |      -8.579    |            18.93  |            0.1733  |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |                0.02358   |                     0.06856 |       1.852    |            17.59  |            0.7519  |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |                0.05869   |                     0.08333 |       1.688    |            13.67  |            0.6706  |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |               -0.0005426 |                     0.05596 |       0.5765   |             6.651 |            0.5224  |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |               -0.0492    |                     0.06553 |      -2.173    |             8.851 |            0.28    |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              |                0.01131   |                     0.09324 |      -3.902    |            10.52  |            0.3365  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              |                0.005449  |                     0.102   |      -2.958    |             8.216 |            0.3117  |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              |                0.01358   |                     0.08995 |      -4.51     |            11.5   |            0.1771  |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              |               -0.01524   |                     0.07956 |      -1.388    |            10.23  |            0.1687  |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              |                0.02298   |                     0.09658 |      -3.126    |             9.954 |            0.5385  |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              |               -0.0005098 |                     0.06624 |      -1.287    |             7.527 |            0.3377  |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              |                0.007114  |                     0.06731 |      -1.127    |             7.755 |            0.2083  |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              |               -0.004123  |                     0.04548 |       0.7147   |             6.248 |            0.1928  |
| ratio_bin       | (-0.001, 0.35] | mlp                                 |                0.02849   |                     0.1131  |      -0.6788   |            13.74  |            0.75    |
| ratio_bin       | (0.35, 0.625]  | mlp                                 |               -0.02162   |                     0.1375  |      -1.95     |            14.47  |            0.6104  |
| ratio_bin       | (0.625, 0.875] | mlp                                 |                0.01923   |                     0.1221  |      -0.7557   |            13.14  |            0.5521  |
| ratio_bin       | (0.875, 1.05]  | mlp                                 |                0.02409   |                     0.1234  |      -0.3686   |             9.572 |            0.4578  |
| ratio_bin       | (-0.001, 0.35] | ridge                               |                0.04136   |                     0.07888 |      -4.096    |            11.51  |            0.4519  |
| ratio_bin       | (0.35, 0.625]  | ridge                               |                0.007154  |                     0.07731 |      -2.829    |             8.399 |            0.3247  |
| ratio_bin       | (0.625, 0.875] | ridge                               |                0.009661  |                     0.06344 |      -1.847    |             9.568 |            0.1979  |
| ratio_bin       | (0.875, 1.05]  | ridge                               |                0.01402   |                     0.06055 |       0.5831   |             8.286 |            0.1807  |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new |               -0.002987  |                     0.07166 |      -3.55     |            10.07  |            0.5481  |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new |               -0.01081   |                     0.0766  |      -1.233    |             6.823 |            0.3377  |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new |               -0.0001953 |                     0.05834 |      -0.6112   |             8.119 |            0.1875  |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new |               -0.002142  |                     0.0436  |       0.55     |             7.256 |            0.1928  |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           |               -0.01331   |                     0.1637  |     -11.88     |            13.33  |            0.3654  |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           |               -0.03731   |                     0.1576  |     -11.76     |            13.85  |            0.3117  |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           |               -0.002204  |                     0.1179  |      -9.264    |            13.52  |            0.2083  |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           |               -0.02179   |                     0.1237  |      -8.045    |            14.19  |            0.2651  |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |                0.004215  |                     0.08539 |      -4.495    |            15.3   |            0.6442  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |                0.002043  |                     0.1035  |      -1.728    |             8.676 |            0.5974  |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     |               -0.002133  |                     0.08892 |       0.9939   |            10.21  |            0.5417  |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |                0.003493  |                     0.07846 |       1.667    |             5.62  |            0.5783  |
| stave           | B2             | 1d_cnn                              |               -0.06026   |                     0.08565 |      -8.168    |            12.08  |            0.3563  |
| stave           | B4             | 1d_cnn                              |                0.05647   |                     0.09095 |      -6.353    |            10.02  |            0.3366  |
| stave           | B6             | 1d_cnn                              |                0.007933  |                     0.08607 |      -2.927    |             8.531 |            0.13    |
| stave           | B8             | 1d_cnn                              |               -0.007193  |                     0.08051 |       0.079    |             9.243 |            0.1667  |
| stave           | B2             | gradient_boosted_trees              |               -0.02725   |                     0.07635 |      -4.75     |            10.04  |            0.4483  |
| stave           | B4             | gradient_boosted_trees              |                0.02566   |                     0.05282 |      -2.446    |             7.54  |            0.297   |
| stave           | B6             | gradient_boosted_trees              |               -0.001493  |                     0.06512 |      -0.02391  |             5.678 |            0.28    |
| stave           | B8             | gradient_boosted_trees              |                0.003235  |                     0.05647 |       2.115    |             6.661 |            0.2917  |
| stave           | B2             | mlp                                 |                0.02409   |                     0.1142  |      -5.243    |            12.36  |            0.8506  |
| stave           | B4             | mlp                                 |                0.04448   |                     0.1181  |      -2.008    |            12.46  |            0.5842  |
| stave           | B6             | mlp                                 |               -0.009505  |                     0.1178  |      -1.319    |            11.39  |            0.46    |
| stave           | B8             | mlp                                 |                0.0471    |                     0.1246  |       3.129    |            12.52  |            0.5139  |
| stave           | B2             | ridge                               |               -0.04854   |                     0.0699  |      -7.871    |            11.82  |            0.3908  |
| stave           | B4             | ridge                               |                0.04481   |                     0.05472 |      -3.923    |             8.194 |            0.3564  |
| stave           | B6             | ridge                               |                0.00748   |                     0.06165 |      -0.1738   |             7.137 |            0.24    |
| stave           | B8             | ridge                               |                0.02042   |                     0.06743 |       1.604    |             7.395 |            0.1667  |
| stave           | B2             | template_residual_boosted_stack_new |               -0.03313   |                     0.06323 |      -3.658    |             9.599 |            0.3793  |
| stave           | B4             | template_residual_boosted_stack_new |                0.01969   |                     0.05441 |      -2.197    |             7.456 |            0.3069  |
| stave           | B6             | template_residual_boosted_stack_new |               -0.01013   |                     0.04411 |       0.1812   |             5.248 |            0.31    |
| stave           | B8             | template_residual_boosted_stack_new |                0.002932  |                     0.05281 |       1.811    |             7.183 |            0.3056  |
| stave           | B2             | tiny_sequence_transformer           |               -0.07982   |                     0.1252  |     -13.82     |            14.69  |            0.3563  |
| stave           | B4             | tiny_sequence_transformer           |                0.0248    |                     0.1177  |     -15.33     |            14.45  |            0.297   |
| stave           | B6             | tiny_sequence_transformer           |               -0.01005   |                     0.1559  |      -8.483    |            11.63  |            0.23    |
| stave           | B8             | tiny_sequence_transformer           |               -0.02628   |                     0.1178  |      -3.855    |            13.35  |            0.2778  |
| stave           | B2             | two_pulse_template_cfd_baseline     |                0.04035   |                     0.06308 |      -1.796    |            17.76  |            0.5862  |
| stave           | B4             | two_pulse_template_cfd_baseline     |               -0.02716   |                     0.0679  |      -3.474    |            14.77  |            0.8119  |
| stave           | B6             | two_pulse_template_cfd_baseline     |               -0.06013   |                     0.05137 |      -1.437    |             8.279 |            0.58    |
| stave           | B8             | two_pulse_template_cfd_baseline     |                0.02084   |                     0.08061 |       1.605    |             5.182 |            0.3056  |
| saturated_proxy | False          | 1d_cnn                              |                0.01038   |                     0.09305 |      -3.088    |            10.17  |            0.2595  |
| saturated_proxy | True           | 1d_cnn                              |               -0.03549   |                     0.04113 |      -5.634    |            12.82  |            0.05882 |
| saturated_proxy | False          | gradient_boosted_trees              |                0.003235  |                     0.06669 |      -0.7724   |             7.774 |            0.3382  |
| saturated_proxy | True           | gradient_boosted_trees              |               -0.01117   |                     0.04779 |      -3.004    |             9.684 |            0.1176  |
| saturated_proxy | False          | mlp                                 |                0.01923   |                     0.1264  |      -0.7135   |            12.61  |            0.6006  |
| saturated_proxy | True           | mlp                                 |                0.111     |                     0.1275  |      -3.472    |             7     |            0.5882  |
| saturated_proxy | False          | ridge                               |                0.01651   |                     0.0748  |      -2.004    |             9.481 |            0.309   |
| saturated_proxy | True           | ridge                               |               -0.0266    |                     0.042   |      -5.123    |            11.2   |            0       |
| saturated_proxy | False          | template_residual_boosted_stack_new |               -0.0009045 |                     0.06122 |      -0.741    |             7.642 |            0.3411  |
| saturated_proxy | True           | template_residual_boosted_stack_new |               -0.02558   |                     0.03609 |      -1.347    |             9.601 |            0       |
| saturated_proxy | False          | tiny_sequence_transformer           |               -0.01496   |                     0.1432  |      -9.663    |            14.24  |            0.3032  |
| saturated_proxy | True           | tiny_sequence_transformer           |               -0.06472   |                     0.1276  |     -12.27     |            11.35  |            0       |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     |               -0.003214  |                     0.09822 |       0.4752   |            10.95  |            0.6035  |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     |                0.01904   |                     0.01893 |      -2.737    |            12.51  |            0.3529  |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `251.2` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.


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
| template_residual_boosted_stack_new |              202 |                     0.06265 |                            0.0526  |                             0.07284 |             7.813 |                    6.92  |                     8.681 |         0.8443 |                0.7809 |                 0.9092 |
| gradient_boosted_trees              |              202 |                     0.06556 |                            0.0578  |                             0.07324 |             7.971 |                    7.058 |                     8.474 |         0.8422 |                0.7783 |                 0.8999 |
| ridge                               |              202 |                     0.07413 |                            0.06445 |                             0.08075 |             9.883 |                    8.557 |                    10.88  |         0.8337 |                0.7605 |                 0.9086 |
| two_pulse_template_cfd_baseline     |              202 |                     0.09121 |                            0.07411 |                             0.1009  |            11.41  |                    8.426 |                    14.55  |         0.6545 |                0.5636 |                 0.758  |
| 1d_cnn                              |              202 |                     0.09145 |                            0.08332 |                             0.1006  |            10.45  |                    9.438 |                    11.23  |         0.7961 |                0.7224 |                 0.8634 |
| mlp                                 |              202 |                     0.1272  |                            0.1077  |                             0.145   |            12.54  |                   10.66  |                    14.37  |         0.77   |                0.6872 |                 0.8675 |
| tiny_sequence_transformer           |              202 |                     0.142   |                            0.1246  |                             0.1522  |            13.9   |                   12.37  |                    15.27  |         0.7716 |                0.6856 |                 0.8568 |


## S29b endpoint synthesis

The S29b ticket asks for six named endpoint families.  The primary model ranking
still uses the predeclared composite score in `winner_ranked_metrics.csv`, while
the table below maps each method to endpoint-specific quantities with run-block
95% bootstrap intervals where the summary statistic supports them.  The winner
reported in `result.json` is `template_residual_boosted_stack_new`.

| endpoint              | method                              | primary_metric            | value_ci95                        | secondary_metric          | secondary_value   |
|:----------------------|:------------------------------------|:--------------------------|:----------------------------------|:--------------------------|:------------------|
| pile-up separation    | template_residual_boosted_stack_new | detection AP              | 0.8443 [0.8262, 0.8655]           | miss / false split        | 0.325 / 0.1778    |
| saturation recovery   | template_residual_boosted_stack_new | fractional energy sigma68 | 0.06265 [0.05544, 0.06874]        | fractional energy bias    | -0.004054         |
| energy closure        | template_residual_boosted_stack_new | fractional energy bias    | -0.004054 [-0.007766, -0.0006451] | fractional energy sigma68 | 0.06265           |
| pulse-shape residuals | template_residual_boosted_stack_new | late-tail |dt|>15 ns rate | 0.107 [0.0963, 0.1188]            | timing sigma68 ns         | 7.813             |
| pile-up separation    | gradient_boosted_trees              | detection AP              | 0.8422 [0.8205, 0.863]            | miss / false split        | 0.3278 / 0.2      |
| saturation recovery   | gradient_boosted_trees              | fractional energy sigma68 | 0.06556 [0.05973, 0.07584]        | fractional energy bias    | 0.002403          |
| energy closure        | gradient_boosted_trees              | fractional energy bias    | 0.002403 [-0.005644, 0.006793]    | fractional energy sigma68 | 0.06556           |
| pulse-shape residuals | gradient_boosted_trees              | late-tail |dt|>15 ns rate | 0.1033 [0.08197, 0.1384]          | timing sigma68 ns         | 7.971             |
| pile-up separation    | ridge                               | detection AP              | 0.8337 [0.8086, 0.8581]           | miss / false split        | 0.2944 / 0.2056   |
| saturation recovery   | ridge                               | fractional energy sigma68 | 0.07413 [0.0688, 0.07853]         | fractional energy bias    | 0.01498           |
| energy closure        | ridge                               | fractional energy bias    | 0.01498 [0.005393, 0.02594]       | fractional energy sigma68 | 0.07413           |
| pulse-shape residuals | ridge                               | late-tail |dt|>15 ns rate | 0.1614 [0.1365, 0.1875]           | timing sigma68 ns         | 9.883             |
| pile-up separation    | 1d_cnn                              | detection AP              | 0.7961 [0.7766, 0.816]            | miss / false split        | 0.25 / 0.3083     |
| saturation recovery   | 1d_cnn                              | fractional energy sigma68 | 0.09145 [0.08527, 0.1009]         | fractional energy bias    | 0.004609          |
| energy closure        | 1d_cnn                              | fractional energy bias    | 0.004609 [-0.01549, 0.02151]      | fractional energy sigma68 | 0.09145           |
| pulse-shape residuals | 1d_cnn                              | late-tail |dt|>15 ns rate | 0.1759 [0.1533, 0.1996]           | timing sigma68 ns         | 10.45             |
| pile-up separation    | two_pulse_template_cfd_baseline     | detection AP              | 0.6545 [0.6357, 0.6745]           | miss / false split        | 0.5917 / 0.2361   |
| saturation recovery   | two_pulse_template_cfd_baseline     | fractional energy sigma68 | 0.09121 [0.07698, 0.1044]         | fractional energy bias    | 0.002043          |
| energy closure        | two_pulse_template_cfd_baseline     | fractional energy bias    | 0.002043 [-0.004589, 0.004295]    | fractional energy sigma68 | 0.09121           |
| pulse-shape residuals | two_pulse_template_cfd_baseline     | late-tail |dt|>15 ns rate | 0.2007 [0.1544, 0.244]            | timing sigma68 ns         | 11.41             |
| pile-up separation    | mlp                                 | detection AP              | 0.77 [0.7381, 0.7926]             | miss / false split        | 0.6 / 0.1167      |
| saturation recovery   | mlp                                 | fractional energy sigma68 | 0.1272 [0.1119, 0.1441]           | fractional energy bias    | 0.02153           |
| energy closure        | mlp                                 | fractional energy bias    | 0.02153 [-0.008082, 0.03921]      | fractional energy sigma68 | 0.1272            |
| pulse-shape residuals | mlp                                 | late-tail |dt|>15 ns rate | 0.2465 [0.1871, 0.3125]           | timing sigma68 ns         | 12.54             |
| pile-up separation    | tiny_sequence_transformer           | detection AP              | 0.7716 [0.7579, 0.7958]           | miss / false split        | 0.2889 / 0.2722   |
| saturation recovery   | tiny_sequence_transformer           | fractional energy sigma68 | 0.142 [0.1325, 0.1499]            | fractional energy bias    | -0.01802          |
| energy closure        | tiny_sequence_transformer           | fractional energy bias    | -0.01802 [-0.03084, -0.01069]     | fractional energy sigma68 | 0.142             |
| pulse-shape residuals | tiny_sequence_transformer           | late-tail |dt|>15 ns rate | 0.3945 [0.3517, 0.4386]           | timing sigma68 ns         | 13.9              |

### Pedestal robustness and saturation strata

Pedestal robustness is assessed indirectly through the clean-amplitude/saturation
proxy split retained by the controlled-injection generator.  The low-amplitude
side is most sensitive to baseline excursions because the same run-local residual
pool is injected before saturation clipping; the high-amplitude side stresses the
clipped-template recovery regime.

| endpoint                                    | value   | method                              |   energy_fractional_bias |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:--------------------------------------------|:--------|:------------------------------------|-------------------------:|----------------------------:|------------------:|-------------------:|
| pedestal robustness clean-amplitude closure | False   | 1d_cnn                              |                0.01038   |                     0.09305 |            10.17  |            0.2595  |
| pedestal robustness clean-amplitude closure | False   | gradient_boosted_trees              |                0.003235  |                     0.06669 |             7.774 |            0.3382  |
| pedestal robustness clean-amplitude closure | False   | mlp                                 |                0.01923   |                     0.1264  |            12.61  |            0.6006  |
| pedestal robustness clean-amplitude closure | False   | ridge                               |                0.01651   |                     0.0748  |             9.481 |            0.309   |
| pedestal robustness clean-amplitude closure | False   | template_residual_boosted_stack_new |               -0.0009045 |                     0.06122 |             7.642 |            0.3411  |
| pedestal robustness clean-amplitude closure | False   | tiny_sequence_transformer           |               -0.01496   |                     0.1432  |            14.24  |            0.3032  |
| pedestal robustness clean-amplitude closure | False   | two_pulse_template_cfd_baseline     |               -0.003214  |                     0.09822 |            10.95  |            0.6035  |
| saturation-proxy high-amplitude closure     | True    | 1d_cnn                              |               -0.03549   |                     0.04113 |            12.82  |            0.05882 |
| saturation-proxy high-amplitude closure     | True    | gradient_boosted_trees              |               -0.01117   |                     0.04779 |             9.684 |            0.1176  |
| saturation-proxy high-amplitude closure     | True    | mlp                                 |                0.111     |                     0.1275  |             7     |            0.5882  |
| saturation-proxy high-amplitude closure     | True    | ridge                               |               -0.0266    |                     0.042   |            11.2   |            0       |
| saturation-proxy high-amplitude closure     | True    | template_residual_boosted_stack_new |               -0.02558   |                     0.03609 |             9.601 |            0       |
| saturation-proxy high-amplitude closure     | True    | tiny_sequence_transformer           |               -0.06472   |                     0.1276  |            11.35  |            0       |
| saturation-proxy high-amplitude closure     | True    | two_pulse_template_cfd_baseline     |                0.01904   |                     0.01893 |            12.51  |            0.3529  |

### PID boundary and residual diagnostics

The B-stave label is used as a PID-boundary proxy because this raw ROOT benchmark
does not carry a final downstream PID decision.  A method that only improves
global energy resolution while shifting one stave family would be unsafe for a
PID boundary analysis, so the table reports the span and maximum absolute
stave-conditioned energy bias.  Event-level residual checks summarize the same
held-out positive events without bootstrap aggregation.

| endpoint                      | method                              |   max_abs_stave_energy_bias |   stave_bias_span |   p90_abs_energy_error |   p90_abs_time_error_ns |
|:------------------------------|:------------------------------------|----------------------------:|------------------:|-----------------------:|------------------------:|
| PID boundary shifts           | gradient_boosted_trees              |                     0.02725 |           0.05291 |               nan      |                  nan    |
| PID boundary shifts           | template_residual_boosted_stack_new |                     0.03313 |           0.05282 |               nan      |                  nan    |
| PID boundary shifts           | mlp                                 |                     0.0471  |           0.05661 |               nan      |                  nan    |
| PID boundary shifts           | ridge                               |                     0.04854 |           0.09335 |               nan      |                  nan    |
| PID boundary shifts           | two_pulse_template_cfd_baseline     |                     0.06013 |           0.1005  |               nan      |                  nan    |
| PID boundary shifts           | 1d_cnn                              |                     0.06026 |           0.1167  |               nan      |                  nan    |
| PID boundary shifts           | tiny_sequence_transformer           |                     0.07982 |           0.1046  |               nan      |                  nan    |
| event-level closure residuals | template_residual_boosted_stack_new |                   nan       |         nan       |                 0.113  |                   13.07 |
| event-level closure residuals | ridge                               |                   nan       |         nan       |                 0.1168 |                   15.45 |
| event-level closure residuals | gradient_boosted_trees              |                   nan       |         nan       |                 0.1317 |                   13.14 |
| event-level closure residuals | two_pulse_template_cfd_baseline     |                   nan       |         nan       |                 0.1462 |                   18.96 |
| event-level closure residuals | 1d_cnn                              |                   nan       |         nan       |                 0.1486 |                   14.89 |
| event-level closure residuals | tiny_sequence_transformer           |                   nan       |         nan       |                 0.2297 |                   24.86 |
| event-level closure residuals | mlp                                 |                   nan       |         nan       |                 0.2338 |                   23.4  |

## Additional S29b caveats

The study is deliberately conservative about what can be learned from the
available raw ROOT branches.  The benchmark truth is controlled injection truth,
not online pile-up truth, and the saturation label is an amplitude-ceiling proxy.
Pedestal robustness is tested through run-local residual injection and the
clean-amplitude sideband rather than a dedicated pedestal scan.  PID boundary
shifts are represented by stave-conditioned closure because no final PID boundary
label is present in the ROOT waveform tree.  These limitations are carried into
`result.json` and should be treated as systematics, not implementation details.

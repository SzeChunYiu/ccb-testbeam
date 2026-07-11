# S25b: pile-up and saturation recovery benchmark

## Abstract

This study benchmarks first-hit timing recovery for controlled two-pulse pile-up in raw
B-stack HRD waveforms.  The ticket was `1783770201.8222.568f4add` and the worker was
`testbeam-laptop-2`.  The raw selected-pulse anchor is reproduced directly from
ROOT before any benchmark is interpreted: `640737` pulses
are selected versus the reference `640737`, with
delta `0`.  The primary winner is
`template_residual_boosted_stack_new`, with held-out run-block sigma68 `7.44` ns
and 95% bootstrap interval [7.01,
8.28] ns.

## Data and reproduction

Raw ROOT files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` array was
reshaped to `(event, channel, sample)` with 18 samples per channel.  The selection
used the project-standard B-stave channels B2/B4/B6/B8, pedestal
`b_c = median(x_c[0:4])`, corrected waveform `y_c(t)=x_c(t)-b_c`, and amplitude
cut `max_t y_c(t) > 1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

Clean single-pulse templates were built from train runs only.  Candidate clean pulses
required 1500--12000 ADC and peak sample 4--12.  Each waveform was divided by its
amplitude and shifted to a common CFD20 reference before taking a per-stave median.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              640 |                   2.625 |                      5 |           9.2   |
| B4      |              640 |                   3.037 |                      6 |          10.71  |
| B6      |              611 |                   3.705 |                      6 |           9.67  |
| B8      |              455 |                   4.219 |                      8 |           9.326 |

## Benchmark design

The analysis uses a run-held-out split: train runs `[50, 51, 52, 53, 54, 55, 56, 57]`
and held-out runs `[58, 60, 62, 64, 65]`.  Pile-up labels are controlled
injections, not hand-labeled real pile-up: for a clean primary pulse with amplitude
`A_1`, a second copy is injected as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_r(t) + p`,

where `T_s` is the train-only template for stave `s`, `Delta` is drawn from
0.5--6.0 samples, `r` from 0.25--1.0, `epsilon_r(t)` is a run-local residual sampled
from real clean pulses, and `p` is a small pedestal offset.  Negative controls use
the same run-local residual and amplitude spectrum without the second component.

## Methods

The traditional baseline is a bounded two-pulse template fit with a one-pulse
constant-fraction timing initialization.  It minimizes

`SSE_k = sum_t [w(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`

over a grid of first-hit shifts, allowed spacings, positive amplitudes, bounded
baseline, and secondary/primary amplitude ratio.  Its detection score is the
fractional improvement `(SSE_1-SSE_2)/SSE_1`.

The ML/NN panel contains ridge classification plus ridge multi-output regression,
histogram gradient-boosted trees, an MLP classifier/regressor pair, a compact
18-sample 1D-CNN, and a new template-residual boosted stack.  The new stack is a
two-stage architecture: it appends the traditional fit score and constituent
estimates to waveform shape features, then fits boosted classifiers and regressors
to learn residual corrections under the same run-held-out split.

## Metrics and uncertainty

For detected injected doublets, first-hit timing is evaluated on both constituents:
`e_t = 10 ns * (t_hat - t_true)`.  The robust resolution is

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

The primary ordering minimizes held-out `sigma68`, with miss-rate and false-split
rates treated as veto diagnostics.  Confidence intervals are percentile 95% CIs from
300 run-block bootstrap resamples of held-out runs.

## Overall held-out results

| method                              |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------------------------------|---------------:|------------------:|-------------------------:|--------------------------:|-----------------------------:|-------------------:|-------------------:|----------------------------:|
| template_residual_boosted_stack_new |        -1.557  |             7.437 |                    7.007 |                     8.28  |                      0.09951 |             0.3133 |             0.1733 |                     0.06542 |
| gradient_boosted_trees              |        -1.369  |             7.807 |                    6.975 |                     8.508 |                      0.1048  |             0.3    |             0.1867 |                     0.06021 |
| ridge                               |        -1.383  |             9.32  |                    8.373 |                    10.17  |                      0.1425  |             0.3567 |             0.1133 |                     0.07238 |
| two_pulse_template_cfd_baseline     |         0.2334 |             9.493 |                    8.172 |                    11.73  |                      0.1786  |             0.58   |             0.17   |                     0.08576 |
| 1d_cnn                              |        -0.4566 |            10.91  |                   10.01  |                    11.89  |                      0.1892  |             0.3833 |             0.1533 |                     0.09174 |
| mlp                                 |        -3.162  |            11.97  |                   11.28  |                    12.53  |                      0.2539  |             0.3633 |             0.1367 |                     0.1537  |

The traditional baseline obtains sigma68 `9.49` ns.  The
winner `template_residual_boosted_stack_new` changes that by `-2.06`
ns.  Detection quality is reported separately because a low timing width after
aggressive rejection would not constitute a usable deconvolver.

## Run-held-out stability

| method                              |   heldout_run |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|---------------:|------------------:|-----------------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |       -1.053   |             9.738 |                      0.1212  |             0.45   |            0.15    |
| 1d_cnn                              |            60 |        1.453   |            11.02  |                      0.2286  |             0.4167 |            0.1     |
| 1d_cnn                              |            62 |       -1.338   |             9.9   |                      0.1154  |             0.35   |            0.2     |
| 1d_cnn                              |            64 |       -0.02745 |            12.69  |                      0.2639  |             0.4    |            0.1667  |
| 1d_cnn                              |            65 |       -0.5158  |            11.05  |                      0.2143  |             0.3    |            0.15    |
| gradient_boosted_trees              |            58 |       -1.56    |             9.441 |                      0.1     |             0.3333 |            0.2667  |
| gradient_boosted_trees              |            60 |        0.4423  |             7.95  |                      0.1585  |             0.3167 |            0.06667 |
| gradient_boosted_trees              |            62 |       -1.159   |             6.415 |                      0.02273 |             0.2667 |            0.2167  |
| gradient_boosted_trees              |            64 |       -1.184   |             8.536 |                      0.119   |             0.3    |            0.1833  |
| gradient_boosted_trees              |            65 |       -3.76    |             6.714 |                      0.1279  |             0.2833 |            0.2     |
| mlp                                 |            58 |       -3.717   |            11.85  |                      0.2875  |             0.3333 |            0.1667  |
| mlp                                 |            60 |       -3.194   |            12.11  |                      0.2568  |             0.3833 |            0.1333  |
| mlp                                 |            62 |       -1.366   |            11.32  |                      0.2051  |             0.35   |            0.1667  |
| mlp                                 |            64 |       -2.716   |            12.36  |                      0.2568  |             0.3833 |            0.1333  |
| mlp                                 |            65 |       -3.386   |            10.74  |                      0.2632  |             0.3667 |            0.08333 |
| ridge                               |            58 |       -0.9537  |             9.161 |                      0.2051  |             0.35   |            0.1333  |
| ridge                               |            60 |       -1.477   |             9.049 |                      0.1622  |             0.3833 |            0.1     |
| ridge                               |            62 |       -0.5802  |             7.683 |                      0.1026  |             0.35   |            0.1333  |
| ridge                               |            64 |        0.9475  |            10.38  |                      0.1026  |             0.35   |            0.08333 |
| ridge                               |            65 |       -2.723   |             7.797 |                      0.141   |             0.35   |            0.1167  |
| template_residual_boosted_stack_new |            58 |       -0.7474  |             7.084 |                      0.1     |             0.3333 |            0.3167  |
| template_residual_boosted_stack_new |            60 |       -1.008   |             8.438 |                      0.1667  |             0.3    |            0.06667 |
| template_residual_boosted_stack_new |            62 |       -0.507   |             6.951 |                      0.02439 |             0.3167 |            0.15    |
| template_residual_boosted_stack_new |            64 |       -1.675   |             8.035 |                      0.08537 |             0.3167 |            0.2167  |
| template_residual_boosted_stack_new |            65 |       -3.082   |             6.601 |                      0.119   |             0.3    |            0.1167  |
| two_pulse_template_cfd_baseline     |            58 |       -0.3346  |             9.033 |                      0.18    |             0.5833 |            0.2167  |
| two_pulse_template_cfd_baseline     |            60 |        1.038   |             9.599 |                      0.1154  |             0.5667 |            0.2333  |
| two_pulse_template_cfd_baseline     |            62 |       -0.2989  |            10.3   |                      0.1667  |             0.5    |            0.15    |
| two_pulse_template_cfd_baseline     |            64 |        2.172   |             7.17  |                      0.175   |             0.6667 |            0.15    |
| two_pulse_template_cfd_baseline     |            65 |       -0.5432  |            12.69  |                      0.26    |             0.5833 |            0.1     |

## Strata and systematics

The table below scans doublet spacing, amplitude ratio, stave, and a saturation proxy
defined by injected summed amplitude above 11000 ADC.

| stratum         | value          | method                              |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   energy_fractional_sigma68 |
|:----------------|:---------------|:------------------------------------|---------------:|------------------:|-------------------:|----------------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              |       0.9164   |            13.48  |             0.5319 |                     0.05718 |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              |       1.135    |             7.773 |             0.4462 |                     0.08093 |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              |      -0.8286   |             8.565 |             0.3239 |                     0.1041  |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              |      -2.092    |            13.08  |             0.1857 |                     0.09399 |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              |       0.03771  |             7.435 |             0.3936 |                     0.06468 |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              |      -1.203    |             7.327 |             0.3538 |                     0.05177 |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              |      -1.941    |             8.198 |             0.2958 |                     0.06213 |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              |      -1.762    |             9.836 |             0.1286 |                     0.061   |
| spacing_bin     | (-0.001, 10.0] | mlp                                 |       1.243    |            11.69  |             0.4894 |                     0.1401  |
| spacing_bin     | (10.0, 25.0]   | mlp                                 |      -2.52     |            10.25  |             0.4308 |                     0.1119  |
| spacing_bin     | (25.0, 45.0]   | mlp                                 |      -3.495    |            11.75  |             0.3099 |                     0.1186  |
| spacing_bin     | (45.0, 70.0]   | mlp                                 |      -5.492    |            13.62  |             0.1857 |                     0.2009  |
| spacing_bin     | (-0.001, 10.0] | ridge                               |       0.9623   |             9.73  |             0.4574 |                     0.07035 |
| spacing_bin     | (10.0, 25.0]   | ridge                               |      -1.394    |             6.158 |             0.4    |                     0.04434 |
| spacing_bin     | (25.0, 45.0]   | ridge                               |      -1.161    |             8.33  |             0.3099 |                     0.07885 |
| spacing_bin     | (45.0, 70.0]   | ridge                               |      -4.714    |            11.03  |             0.2286 |                     0.06168 |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new |       0.2373   |             7.748 |             0.4255 |                     0.07062 |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new |      -1.491    |             6.681 |             0.3692 |                     0.0526  |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new |      -2.605    |             6.927 |             0.2676 |                     0.07287 |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new |      -2.554    |             9.259 |             0.1571 |                     0.06251 |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     |       3.717    |            18.6   |             0.7447 |                     0.07916 |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     |       1.313    |             7.385 |             0.6462 |                     0.06075 |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     |       1.254    |             8.968 |             0.4789 |                     0.07472 |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     |      -1.481    |            10.26  |             0.4    |                     0.07887 |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              |      -1.897    |            13.46  |             0.4861 |                     0.1261  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              |      -1.413    |            10.99  |             0.3521 |                     0.09959 |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              |       0.008228 |            10.22  |             0.425  |                     0.0896  |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              |       2.247    |             9.485 |             0.2727 |                     0.06913 |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              |      -2.846    |            10.18  |             0.5    |                     0.07586 |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              |      -3.798    |             7.904 |             0.2676 |                     0.05733 |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              |      -1.121    |             7.424 |             0.3    |                     0.06201 |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              |       0.4701   |             7.639 |             0.1429 |                     0.04743 |
| ratio_bin       | (-0.001, 0.35] | mlp                                 |      -3.377    |            12.2   |             0.5139 |                     0.1659  |
| ratio_bin       | (0.35, 0.625]  | mlp                                 |      -2.4      |            12.78  |             0.2958 |                     0.1405  |
| ratio_bin       | (0.625, 0.875] | mlp                                 |      -3.549    |            12.69  |             0.4    |                     0.1649  |
| ratio_bin       | (0.875, 1.05]  | mlp                                 |      -2.047    |            10.08  |             0.2468 |                     0.1406  |
| ratio_bin       | (-0.001, 0.35] | ridge                               |      -6.045    |            12.09  |             0.5556 |                     0.08318 |
| ratio_bin       | (0.35, 0.625]  | ridge                               |      -3.167    |             9.132 |             0.338  |                     0.06865 |
| ratio_bin       | (0.625, 0.875] | ridge                               |      -0.8398   |             8.876 |             0.325  |                     0.07311 |
| ratio_bin       | (0.875, 1.05]  | ridge                               |       2.63     |             8.182 |             0.2208 |                     0.04669 |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new |      -2.758    |            10.64  |             0.4722 |                     0.05824 |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new |      -3.385    |             7.866 |             0.2676 |                     0.06037 |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new |      -1.966    |             7.949 |             0.3375 |                     0.07617 |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new |       0.8524   |             6.27  |             0.1818 |                     0.05989 |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     |      -0.6067   |            15.69  |             0.625  |                     0.1129  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     |      -0.005292 |             9.224 |             0.5493 |                     0.07543 |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     |      -0.8602   |             7.667 |             0.625  |                     0.07642 |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     |       3.531    |             8.613 |             0.5195 |                     0.0688  |
| stave           | B2             | 1d_cnn                              |      -6.877    |            12.17  |             0.6154 |                     0.1196  |
| stave           | B4             | 1d_cnn                              |      -1.999    |            10.2   |             0.3521 |                     0.07823 |
| stave           | B6             | 1d_cnn                              |      -0.7786   |            10.62  |             0.3462 |                     0.08202 |
| stave           | B8             | 1d_cnn                              |       2.279    |             8.829 |             0.2055 |                     0.09147 |
| stave           | B2             | gradient_boosted_trees              |      -7.132    |             8.457 |             0.3846 |                     0.07969 |
| stave           | B4             | gradient_boosted_trees              |      -2.421    |             8.325 |             0.2817 |                     0.05642 |
| stave           | B6             | gradient_boosted_trees              |      -0.95     |             6.591 |             0.3462 |                     0.04998 |
| stave           | B8             | gradient_boosted_trees              |       1.804    |             7.275 |             0.1781 |                     0.05433 |
| stave           | B2             | mlp                                 |      -5.138    |            11.11  |             0.5513 |                     0.2222  |
| stave           | B4             | mlp                                 |      -3.706    |            13.35  |             0.2254 |                     0.1536  |
| stave           | B6             | mlp                                 |      -1.454    |            12.31  |             0.3974 |                     0.1514  |
| stave           | B8             | mlp                                 |      -2.106    |            10.42  |             0.2603 |                     0.1093  |
| stave           | B2             | ridge                               |      -6.822    |             9.872 |             0.5    |                     0.07    |
| stave           | B4             | ridge                               |      -2.875    |             9.231 |             0.2958 |                     0.0605  |
| stave           | B6             | ridge                               |      -0.5972   |             8.179 |             0.3974 |                     0.0678  |
| stave           | B8             | ridge                               |       1.69     |             6.681 |             0.2192 |                     0.07269 |
| stave           | B2             | template_residual_boosted_stack_new |      -6.026    |             7.792 |             0.3718 |                     0.08953 |
| stave           | B4             | template_residual_boosted_stack_new |      -1.753    |             7.752 |             0.2958 |                     0.05484 |
| stave           | B6             | template_residual_boosted_stack_new |      -0.6662   |             6.65  |             0.3333 |                     0.05198 |
| stave           | B8             | template_residual_boosted_stack_new |       1.66     |             5.862 |             0.2466 |                     0.06547 |
| stave           | B2             | two_pulse_template_cfd_baseline     |      -1.35     |            15.09  |             0.7821 |                     0.05326 |
| stave           | B4             | two_pulse_template_cfd_baseline     |      -2.57     |            15.19  |             0.8028 |                     0.07074 |
| stave           | B6             | two_pulse_template_cfd_baseline     |       0.2334   |            10.4   |             0.5256 |                     0.06485 |
| stave           | B8             | two_pulse_template_cfd_baseline     |       1.372    |             6.35  |             0.2055 |                     0.09215 |
| saturated_proxy | False          | 1d_cnn                              |      -0.2817   |            11.01  |             0.3891 |                     0.09113 |
| saturated_proxy | True           | 1d_cnn                              |      -6.353    |             8.673 |             0.1429 |                     0.08451 |
| saturated_proxy | False          | gradient_boosted_trees              |      -1.325    |             7.774 |             0.3038 |                     0.06013 |
| saturated_proxy | True           | gradient_boosted_trees              |      -1.917    |            10.48  |             0.1429 |                     0.07776 |
| saturated_proxy | False          | mlp                                 |      -3.205    |            11.99  |             0.3686 |                     0.1537  |
| saturated_proxy | True           | mlp                                 |      -1.067    |             6.075 |             0.1429 |                     0.1339  |
| saturated_proxy | False          | ridge                               |      -1.303    |             9.474 |             0.3652 |                     0.06845 |
| saturated_proxy | True           | ridge                               |      -5.642    |            11.97  |             0      |                     0.0572  |
| saturated_proxy | False          | template_residual_boosted_stack_new |      -1.578    |             7.492 |             0.3208 |                     0.06382 |
| saturated_proxy | True           | template_residual_boosted_stack_new |      -0.7795   |             7.791 |             0      |                     0.07127 |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     |       0.0386   |             9.489 |             0.5768 |                     0.08603 |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     |       8.859    |             7.8   |             0.7143 |                     0.03036 |

Systematic limitations are explicit.  First, injected doublets preserve observed
single-pulse residuals but cannot prove the frequency or morphology of real beam
pile-up.  Second, only train-run templates are used, so template drift appears as a
real held-out degradation.  Third, the B-stack has 18 samples, which limits separations
below roughly one sample.  Fourth, saturation is represented by a waveform-amplitude
proxy rather than electronics truth flags.  Fifth, the bootstrap unit is the run; the
number of held-out runs is finite and the intervals should be interpreted as
run-transfer uncertainty, not an asymptotic event-level error.

## Negative controls and caveats

Clean-pulse controls enter every held-out run with the same source-run distribution
as injected doublets.  False-split rate is therefore the negative-control endpoint.
The benchmark should be used to choose a deconvolution strategy for controlled
doublet-like pile-up, while follow-up work should validate the winner on hand-scanned
real pile-up candidates and on electronics saturation metadata if available.

Runtime was `88.6` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

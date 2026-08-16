# S08: Waveform 1-D CNN Timing and Pile-up Flag Benchmark

## Abstract

This study benchmarks first-hit timing recovery for controlled two-pulse pile-up in raw
B-stack HRD waveforms.  The ticket was `2379` and the worker was
`testbeam-laptop-1`.  The raw selected-pulse anchor is reproduced directly from
ROOT before any benchmark is interpreted: `640737` pulses
are selected versus the reference `640737`, with
delta `0`.  The primary winner is
`gradient_boosted_trees`, with held-out run-block sigma68 `7.8` ns
and 95% bootstrap interval [7.47,
8.5] ns.

## Data and reproduction

Raw ROOT files were read from `/home/billy/ccb-data/data/extracted/root/root`.  Each `h101/HRDv` array was
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
18-sample 1D-CNN, and a new causal transformer.  The transformer embeds the
baseline-subtracted 18-sample waveform, applies a strictly causal attention mask
(`M_ij = -infinity` for `j > i`) so a token cannot attend to future samples, and
emits a pile-up logit plus four constituent timing/amplitude parameters.  The
bounded template fit is retained only as a fail-closed fallback for low transformer
pile-up scores.

## Metrics and uncertainty

For detected injected doublets, first-hit timing is evaluated on both constituents:
`e_t = 10 ns * (t_hat - t_true)`.  The robust resolution is

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

The primary ordering minimizes held-out `sigma68`, with miss-rate and false-split
rates treated as veto diagnostics.  Confidence intervals are percentile 95% CIs from
300 run-block bootstrap resamples of held-out runs.

## Overall held-out results

| method                          |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:--------------------------------|---------------:|------------------:|-------------------------:|--------------------------:|-----------------------------:|-------------------:|-------------------:|----------------------------:|
| gradient_boosted_trees          |        -1.527  |             7.798 |                    7.474 |                     8.497 |                       0.1122 |             0.3167 |             0.1833 |                     0.07017 |
| ridge                           |        -1.383  |             9.32  |                    8.405 |                    10.04  |                       0.1425 |             0.3567 |             0.1133 |                     0.07238 |
| two_pulse_template_cfd_baseline |         0.2334 |             9.493 |                    8.172 |                    11.73  |                       0.1825 |             0.58   |             0.17   |                     0.08576 |
| causal_transformer_new          |        -3.814  |            10.43  |                    9.634 |                    11.36  |                       0.2068 |             0.2667 |             0.28   |                     0.0924  |
| 1d_cnn                          |        -0.2323 |            10.92  |                   10.08  |                    11.86  |                       0.1984 |             0.37   |             0.15   |                     0.1011  |
| mlp                             |        -3.162  |            11.97  |                   11.28  |                    12.57  |                       0.2539 |             0.3633 |             0.1367 |                     0.1537  |

The traditional baseline obtains sigma68 `9.49` ns.  The
winner `gradient_boosted_trees` changes that by `-1.7`
ns.  Detection quality is reported separately because a low timing width after
aggressive rejection would not constitute a usable deconvolver.

## Run-held-out stability

| method                          |   heldout_run |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |
|:--------------------------------|--------------:|---------------:|------------------:|-----------------------------:|-------------------:|-------------------:|
| 1d_cnn                          |            58 |       -1.115   |            10.18  |                      0.1324  |             0.4333 |            0.15    |
| 1d_cnn                          |            60 |        1.186   |            11.23  |                      0.2639  |             0.4    |            0.1     |
| 1d_cnn                          |            62 |       -0.9241  |             9.585 |                      0.1154  |             0.35   |            0.1833  |
| 1d_cnn                          |            64 |       -0.1744  |            13.26  |                      0.2639  |             0.4    |            0.1667  |
| 1d_cnn                          |            65 |       -0.06224 |            10.93  |                      0.2159  |             0.2667 |            0.15    |
| causal_transformer_new          |            58 |       -3.839   |            10.11  |                      0.2093  |             0.2833 |            0.3333  |
| causal_transformer_new          |            60 |       -4.228   |            11.49  |                      0.2093  |             0.2833 |            0.3     |
| causal_transformer_new          |            62 |       -3.43    |             9.036 |                      0.1444  |             0.25   |            0.2667  |
| causal_transformer_new          |            64 |       -3.064   |            12.11  |                      0.2614  |             0.2667 |            0.2167  |
| causal_transformer_new          |            65 |       -4.43    |             9.02  |                      0.2111  |             0.25   |            0.2833  |
| gradient_boosted_trees          |            58 |       -2.431   |             8.707 |                      0.1184  |             0.3667 |            0.2667  |
| gradient_boosted_trees          |            60 |       -0.3097  |             7.939 |                      0.1463  |             0.3167 |            0.08333 |
| gradient_boosted_trees          |            62 |       -1.469   |             7.169 |                      0.03571 |             0.3    |            0.1333  |
| gradient_boosted_trees          |            64 |       -0.4049  |             7.728 |                      0.1364  |             0.2667 |            0.25    |
| gradient_boosted_trees          |            65 |       -4.103   |             7.016 |                      0.125   |             0.3333 |            0.1833  |
| mlp                             |            58 |       -3.717   |            11.85  |                      0.2875  |             0.3333 |            0.1667  |
| mlp                             |            60 |       -3.194   |            12.11  |                      0.2568  |             0.3833 |            0.1333  |
| mlp                             |            62 |       -1.366   |            11.32  |                      0.2051  |             0.35   |            0.1667  |
| mlp                             |            64 |       -2.716   |            12.36  |                      0.2568  |             0.3833 |            0.1333  |
| mlp                             |            65 |       -3.386   |            10.74  |                      0.2632  |             0.3667 |            0.08333 |
| ridge                           |            58 |       -0.9537  |             9.161 |                      0.2051  |             0.35   |            0.1333  |
| ridge                           |            60 |       -1.477   |             9.049 |                      0.1622  |             0.3833 |            0.1     |
| ridge                           |            62 |       -0.5802  |             7.683 |                      0.1026  |             0.35   |            0.1333  |
| ridge                           |            64 |        0.9475  |            10.38  |                      0.1026  |             0.35   |            0.08333 |
| ridge                           |            65 |       -2.723   |             7.797 |                      0.141   |             0.35   |            0.1167  |
| two_pulse_template_cfd_baseline |            58 |       -0.3346  |             9.033 |                      0.18    |             0.5833 |            0.2167  |
| two_pulse_template_cfd_baseline |            60 |        1.038   |             9.599 |                      0.1154  |             0.5667 |            0.2333  |
| two_pulse_template_cfd_baseline |            62 |       -0.2989  |            10.3   |                      0.1833  |             0.5    |            0.15    |
| two_pulse_template_cfd_baseline |            64 |        2.172   |             7.17  |                      0.175   |             0.6667 |            0.15    |
| two_pulse_template_cfd_baseline |            65 |       -0.5432  |            12.69  |                      0.26    |             0.5833 |            0.1     |

## Strata and systematics

The table below scans doublet spacing, amplitude ratio, stave, and a saturation proxy
defined by injected summed amplitude above 11000 ADC.

| stratum         | value          | method                          |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   energy_fractional_sigma68 |
|:----------------|:---------------|:--------------------------------|---------------:|------------------:|-------------------:|----------------------------:|
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                          |       1.048    |            13.59  |             0.5213 |                     0.06988 |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                          |       0.682    |             7.888 |             0.4462 |                     0.08426 |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                          |      -0.8917   |             8.446 |             0.3239 |                     0.1072  |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                          |      -2.402    |            13.55  |             0.1429 |                     0.1024  |
| spacing_bin     | (-0.001, 10.0] | causal_transformer_new          |      -2.374    |            13.46  |             0.3404 |                     0.09518 |
| spacing_bin     | (10.0, 25.0]   | causal_transformer_new          |      -4.938    |            10.37  |             0.3231 |                     0.05429 |
| spacing_bin     | (25.0, 45.0]   | causal_transformer_new          |      -2.45     |             6.43  |             0.1972 |                     0.07718 |
| spacing_bin     | (45.0, 70.0]   | causal_transformer_new          |      -8.516    |            11.46  |             0.1857 |                     0.1023  |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees          |      -0.6074   |             6.88  |             0.4255 |                     0.07977 |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees          |      -1.03     |             8.389 |             0.3846 |                     0.0447  |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees          |      -1.534    |             8.327 |             0.2958 |                     0.07101 |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees          |      -2.547    |            10     |             0.1286 |                     0.05107 |
| spacing_bin     | (-0.001, 10.0] | mlp                             |       1.243    |            11.69  |             0.4894 |                     0.1401  |
| spacing_bin     | (10.0, 25.0]   | mlp                             |      -2.52     |            10.25  |             0.4308 |                     0.1119  |
| spacing_bin     | (25.0, 45.0]   | mlp                             |      -3.495    |            11.75  |             0.3099 |                     0.1186  |
| spacing_bin     | (45.0, 70.0]   | mlp                             |      -5.492    |            13.62  |             0.1857 |                     0.2009  |
| spacing_bin     | (-0.001, 10.0] | ridge                           |       0.9623   |             9.73  |             0.4574 |                     0.07035 |
| spacing_bin     | (10.0, 25.0]   | ridge                           |      -1.394    |             6.158 |             0.4    |                     0.04434 |
| spacing_bin     | (25.0, 45.0]   | ridge                           |      -1.161    |             8.33  |             0.3099 |                     0.07885 |
| spacing_bin     | (45.0, 70.0]   | ridge                           |      -4.714    |            11.03  |             0.2286 |                     0.06168 |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline |       3.717    |            18.6   |             0.7447 |                     0.07916 |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline |       1.313    |             7.385 |             0.6462 |                     0.06075 |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline |       1.254    |             8.968 |             0.4789 |                     0.07472 |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline |      -1.481    |            10.26  |             0.4    |                     0.07887 |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                          |      -1.774    |            13.28  |             0.4861 |                     0.1264  |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                          |      -0.7313   |            10.64  |             0.3099 |                     0.1047  |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                          |       0.09052  |            10.56  |             0.425  |                     0.1034  |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                          |       2.667    |             9.864 |             0.2597 |                     0.06977 |
| ratio_bin       | (-0.001, 0.35] | causal_transformer_new          |      -5.922    |             9.158 |             0.3889 |                     0.07418 |
| ratio_bin       | (0.35, 0.625]  | causal_transformer_new          |      -6.508    |            10.05  |             0.2676 |                     0.09527 |
| ratio_bin       | (0.625, 0.875] | causal_transformer_new          |      -2.201    |            10.81  |             0.2875 |                     0.1201  |
| ratio_bin       | (0.875, 1.05]  | causal_transformer_new          |      -1.666    |             9.783 |             0.1299 |                     0.08856 |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees          |      -4.023    |            11.34  |             0.5278 |                     0.08901 |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees          |      -3.673    |             7.798 |             0.2817 |                     0.07904 |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees          |      -0.9817   |             7.497 |             0.3    |                     0.06228 |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees          |       0.5145   |             7.787 |             0.1688 |                     0.05358 |
| ratio_bin       | (-0.001, 0.35] | mlp                             |      -3.377    |            12.2   |             0.5139 |                     0.1659  |
| ratio_bin       | (0.35, 0.625]  | mlp                             |      -2.4      |            12.78  |             0.2958 |                     0.1405  |
| ratio_bin       | (0.625, 0.875] | mlp                             |      -3.549    |            12.69  |             0.4    |                     0.1649  |
| ratio_bin       | (0.875, 1.05]  | mlp                             |      -2.047    |            10.08  |             0.2468 |                     0.1406  |
| ratio_bin       | (-0.001, 0.35] | ridge                           |      -6.045    |            12.09  |             0.5556 |                     0.08318 |
| ratio_bin       | (0.35, 0.625]  | ridge                           |      -3.167    |             9.132 |             0.338  |                     0.06865 |
| ratio_bin       | (0.625, 0.875] | ridge                           |      -0.8398   |             8.876 |             0.325  |                     0.07311 |
| ratio_bin       | (0.875, 1.05]  | ridge                           |       2.63     |             8.182 |             0.2208 |                     0.04669 |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline |      -0.6067   |            15.69  |             0.625  |                     0.1129  |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline |      -0.005292 |             9.224 |             0.5493 |                     0.07543 |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline |      -0.8602   |             7.667 |             0.625  |                     0.07642 |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline |       3.531    |             8.613 |             0.5195 |                     0.0688  |
| stave           | B2             | 1d_cnn                          |      -6.687    |            11.37  |             0.6026 |                     0.1313  |
| stave           | B4             | 1d_cnn                          |      -2.235    |            10.35  |             0.3099 |                     0.08418 |
| stave           | B6             | 1d_cnn                          |      -0.2664   |            10.22  |             0.3462 |                     0.08441 |
| stave           | B8             | 1d_cnn                          |       2.82     |             8.74  |             0.2055 |                     0.09124 |
| stave           | B2             | causal_transformer_new          |      -9.655    |             9.49  |             0.4359 |                     0.1012  |
| stave           | B4             | causal_transformer_new          |      -4.406    |            10.12  |             0.2676 |                     0.1014  |
| stave           | B6             | causal_transformer_new          |      -3.287    |             9.684 |             0.2436 |                     0.08298 |
| stave           | B8             | causal_transformer_new          |      -1.788    |            10.93  |             0.1096 |                     0.1148  |
| stave           | B2             | gradient_boosted_trees          |      -6.613    |             8.089 |             0.3974 |                     0.08371 |
| stave           | B4             | gradient_boosted_trees          |      -2.398    |             8.079 |             0.2535 |                     0.07714 |
| stave           | B6             | gradient_boosted_trees          |      -1.074    |             6.438 |             0.3846 |                     0.0558  |
| stave           | B8             | gradient_boosted_trees          |       1.735    |             6.739 |             0.2192 |                     0.0556  |
| stave           | B2             | mlp                             |      -5.138    |            11.11  |             0.5513 |                     0.2222  |
| stave           | B4             | mlp                             |      -3.706    |            13.35  |             0.2254 |                     0.1536  |
| stave           | B6             | mlp                             |      -1.454    |            12.31  |             0.3974 |                     0.1514  |
| stave           | B8             | mlp                             |      -2.106    |            10.42  |             0.2603 |                     0.1093  |
| stave           | B2             | ridge                           |      -6.822    |             9.872 |             0.5    |                     0.07    |
| stave           | B4             | ridge                           |      -2.875    |             9.231 |             0.2958 |                     0.0605  |
| stave           | B6             | ridge                           |      -0.5972   |             8.179 |             0.3974 |                     0.0678  |
| stave           | B8             | ridge                           |       1.69     |             6.681 |             0.2192 |                     0.07269 |
| stave           | B2             | two_pulse_template_cfd_baseline |      -1.35     |            15.09  |             0.7821 |                     0.05326 |
| stave           | B4             | two_pulse_template_cfd_baseline |      -2.57     |            15.19  |             0.8028 |                     0.07074 |
| stave           | B6             | two_pulse_template_cfd_baseline |       0.2334   |            10.4   |             0.5256 |                     0.06485 |
| stave           | B8             | two_pulse_template_cfd_baseline |       1.372    |             6.35  |             0.2055 |                     0.09215 |
| saturated_proxy | False          | 1d_cnn                          |      -0.1152   |            10.92  |             0.3754 |                     0.09772 |
| saturated_proxy | True           | 1d_cnn                          |      -5.328    |             8.771 |             0.1429 |                     0.08445 |
| saturated_proxy | False          | causal_transformer_new          |      -3.721    |            10.47  |             0.273  |                     0.092   |
| saturated_proxy | True           | causal_transformer_new          |      -5.011    |             9.835 |             0      |                     0.08216 |
| saturated_proxy | False          | gradient_boosted_trees          |      -1.492    |             7.868 |             0.3242 |                     0.06955 |
| saturated_proxy | True           | gradient_boosted_trees          |      -2.62     |            10.22  |             0      |                     0.07823 |
| saturated_proxy | False          | mlp                             |      -3.205    |            11.99  |             0.3686 |                     0.1537  |
| saturated_proxy | True           | mlp                             |      -1.067    |             6.075 |             0.1429 |                     0.1339  |
| saturated_proxy | False          | ridge                           |      -1.303    |             9.474 |             0.3652 |                     0.06845 |
| saturated_proxy | True           | ridge                           |      -5.642    |            11.97  |             0      |                     0.0572  |
| saturated_proxy | False          | two_pulse_template_cfd_baseline |       0.0386   |             9.489 |             0.5768 |                     0.08603 |
| saturated_proxy | True           | two_pulse_template_cfd_baseline |       8.859    |             7.8   |             0.7143 |                     0.03036 |

Systematic limitations are explicit.  First, injected doublets preserve observed
single-pulse residuals but cannot prove the frequency or morphology of real beam
pile-up.  Second, only train-run templates are used, so template drift appears as a
real held-out degradation.  Third, the B-stack has 18 samples, which limits separations
below roughly one sample.  Fourth, saturation is represented by a waveform-amplitude
proxy rather than electronics truth flags.  Fifth, the bootstrap unit is the run; the
number of held-out runs is finite and the intervals should be interpreted as
run-transfer uncertainty, not an asymptotic event-level error.

## Dropout, Negative Controls, and Caveats

Clean-pulse controls enter every held-out run with the same source-run distribution
as injected doublets.  False-split rate is therefore the negative-control endpoint.
The benchmark should be used to choose a deconvolution strategy for controlled
doublet-like pile-up.  Dropout/jagged-pulse handling is represented here only through
false-split controls and waveform tail/saturation strata, not through independent
electronics dropout truth; a dedicated P06-style injected-dropout validation remains
the required adoption gate for recovery claims.  Follow-up work should validate the
winner on hand-scanned real pile-up candidates and on electronics saturation/dropout
metadata if available.

Runtime was `31.0` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

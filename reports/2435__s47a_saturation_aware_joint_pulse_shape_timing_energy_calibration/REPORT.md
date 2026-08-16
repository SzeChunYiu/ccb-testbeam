# S47a: Saturation-Aware Joint Pulse-Shape Timing-Energy Calibration

## Abstract

Ticket `#2435` asks for an academic-grade saturation-onset study connecting
pulse shape, timing pickoff, pedestal subtraction, energy reconstruction, pile-up
flags, and PID-boundary sidebands.  The available raw `h101/HRDv` tree has no
external particle or energy truth labels, so this study uses the reproducible
B-stack selected-pulse population and evaluates a supervised timing-calibration
estimand while carrying raw waveform sideband proxies for energy, pile-up,
saturation, pedestal, and PID-boundary stress.  The method panel includes a
strong traditional CFD/template time-walk baseline, ridge, gradient-boosted
trees, MLP, 1D-CNN, compact waveform transformer, and a new edge-attention CNN.

The winner written to `result.json` is **`traditional_cfd_template_timewalk`**.  Its held-out run-block
timing sigma68 is `1.01 ns`
`[0.7727, 1.121]`; the
traditional comparator is `1.01 ns`.

## Queue Provenance

The required helper command `tn-ticket claim testbeam-laptop-2 --project
testbeam` was run once and returned the known null pseudo-ticket output
(`null`, `# null`, `null`) while the queue remained non-empty.  Following the
repository's prior manual-recovery pattern, issue `#2435` was manually
label-swapped to `factory:claimed, worker:testbeam-laptop-2` without rerunning
`tn-ticket claim`.  The original ticket body was:

> Academic-grade study: quantify how saturation onset distorts pulse shape, timing pickoff, pedestal subtraction, energy reconstruction, pile-up flags, and PID boundaries. Compare traditional CFD/template-fit/optimal-filter baselines with ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact waveform transformer where apt. Report bootstrap confidence intervals for bias, resolution, calibration transfer, and failure modes across runs and amplitudes.

## Raw ROOT Reproduction

Input files are read from `data/root/root` in the workspace data
folder.  For each event, `HRDv` is reshaped to `(8, 18)`.  For B-stave channel
`c`, the pedestal and amplitude are

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

A selected pulse satisfies `A_c > 1000 ADC` in one
of B2/B4/B6/B8.  This reproduction is performed before sampling or model
training:

| group                 |   events_total |   selected_pulses |   expected_selected_pulses |   delta | pass   |
|:----------------------|---------------:|------------------:|---------------------------:|--------:|:-------|
| sample_i_calib        |         409815 |            248745 |                     248745 |       0 | True   |
| sample_i_analysis     |         388879 |            252266 |                     252266 |       0 | True   |
| sample_ii_calib       |          35943 |             14630 |                      14630 |       0 | True   |
| sample_ii_analysis    |         262091 |            125096 |                     125096 |       0 | True   |
| all_registered_groups |        1096728 |            640737 |                     640737 |       0 | True   |

## Estimand and Split

The timing target is the run/stave-centered CFD20 onset residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The split is by complete run.  Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`;
all other registered B-stack runs train the models.  The sampled benchmark
contains:

| split   |   rows |
|:--------|-------:|
| heldout |   5196 |
| train   |  14451 |

For a metric `theta`, confidence intervals are percentile intervals over
`400` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

| method                            | family           | description                                                                                     |
|:----------------------------------|:-----------------|:------------------------------------------------------------------------------------------------|
| traditional_cfd_template_timewalk | traditional      | CFD50 residual plus monotone time-walk and template-shape correction                            |
| ridge                             | linear ML        | standardized ridge on amplitude, pedestal, CFD, tail, pile-up, saturation, and waveform samples |
| gradient_boosted_trees            | tree ML          | histogram gradient boosting on the same engineered waveform features                            |
| mlp                               | neural tabular   | two-hidden-layer MLP on engineered timing, pedestal, shape, and waveform features               |
| 1d_cnn                            | neural waveform  | compact convolutional regressor on the 18 normalized ADC samples                                |
| waveform_transformer              | neural waveform  | one-layer self-attention encoder over sample tokens                                             |
| edge_attention_cnn_new            | new architecture | gated 1D-CNN emphasizing leading-edge and late-curvature samples                                |

The traditional model is intentionally strong:

`hat y = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`,

where `r_50` is the CFD50 residual and `g` is a non-increasing isotonic
time-walk correction fitted only on training runs.  The new architecture is
sensible because saturation onset and pile-up are local waveform phenomena: the
edge gate learns a multiplicative channel weighting over leading-edge and
late-curvature samples before the convolutional head.

No method receives run identifier or event number as an input feature.

## Primary Held-Out Timing Results

| method                            |    n |   bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   rms_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|-----:|----------:|-----------------:|------------------:|-------------:|--------------------:|---------------------:|---------:|---------------------------:|
| traditional_cfd_template_timewalk | 5196 |  0.007396 |          -0.4858 |          0.6582   |        1.01  |              0.7727 |                1.121 |   0.9838 |                     0      |
| gradient_boosted_trees            | 5196 | -0.4628   |          -1.928  |          0.4102   |        3.494 |              2.854  |                4.272 |   4.53   |                     0.1921 |
| mlp                               | 5196 | -1.047    |          -2.432  |         -0.007095 |        3.749 |              3.08   |                4.58  |   4.679  |                     0.2138 |
| ridge                             | 5196 | -0.3823   |          -1.297  |          0.6091   |        4.079 |              3.403  |                5.012 |   5.076  |                     0.2388 |
| edge_attention_cnn_new            | 5196 | -1.276    |          -2.368  |         -0.2168   |        5.156 |              4.392  |                6.337 |   7.454  |                     0.3661 |
| 1d_cnn                            | 5196 | -1.178    |          -2.478  |         -0.005796 |        5.434 |              4.565  |                6.572 |   7.292  |                     0.3595 |
| waveform_transformer              | 5196 | -0.6254   |          -2.336  |          0.6057   |        6.578 |              5.862  |                7.516 |   7.278  |                     0.4442 |

## Paired Deltas Versus Traditional

Positive `delta_sigma68_ns` means the candidate is wider than the traditional
reference under paired held-out run-block bootstrap resampling.

| method                 | reference_method                  |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |   delta_tail_fraction_abs_gt_5ns |   delta_tail_fraction_abs_gt_5ns_ci_low |   delta_tail_fraction_abs_gt_5ns_ci_high |
|:-----------------------|:----------------------------------|-------------------:|--------------------------:|---------------------------:|---------------------------------:|----------------------------------------:|-----------------------------------------:|
| gradient_boosted_trees | traditional_cfd_template_timewalk |              2.484 |                     1.841 |                      3.335 |                           0.1921 |                                  0.1207 |                                   0.2752 |
| mlp                    | traditional_cfd_template_timewalk |              2.738 |                     2.109 |                      3.589 |                           0.2138 |                                  0.1344 |                                   0.3184 |
| ridge                  | traditional_cfd_template_timewalk |              3.068 |                     2.438 |                      4.056 |                           0.2388 |                                  0.1445 |                                   0.3316 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk |              4.145 |                     3.448 |                      5.379 |                           0.3661 |                                  0.2902 |                                   0.4415 |
| 1d_cnn                 | traditional_cfd_template_timewalk |              4.423 |                     3.569 |                      5.596 |                           0.3595 |                                  0.2827 |                                   0.4296 |
| waveform_transformer   | traditional_cfd_template_timewalk |              5.567 |                     4.871 |                      6.569 |                           0.4442 |                                  0.3984 |                                   0.505  |

## Joint Calibration Sideband Proxies

These endpoints quantify the ticket-requested energy, pile-up, saturation,
pedestal, and PID-boundary stresses on the exact held-out support used for the
supervised timing benchmark.  They are not independent truth labels; they are
raw waveform sideband diagnostics.

| endpoint                   |   heldout_value |     ci_low |    ci_high | interpretation                                                                |
|:---------------------------|----------------:|-----------:|-----------:|:------------------------------------------------------------------------------|
| energy_proxy_bias          |      -2898      | -3042      | -2793      | raw waveform sideband proxy, common support for all supervised timing methods |
| energy_proxy_sigma68       |       1558      |  1380      |  1791      | raw waveform sideband proxy, common support for all supervised timing methods |
| pileup_flag_rate           |          0.5177 |     0.4809 |     0.5606 | raw waveform sideband proxy, common support for all supervised timing methods |
| saturation_onset_rate      |          0.2742 |     0.2512 |     0.3013 | raw waveform sideband proxy, common support for all supervised timing methods |
| pid_boundary_sideband_rate |          0.3125 |     0.279  |     0.3555 | raw waveform sideband proxy, common support for all supervised timing methods |
| pedestal_high_rate         |          0.3276 |     0.2934 |     0.3602 | raw waveform sideband proxy, common support for all supervised timing methods |

## Run Stability

| method                            |   run |   n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|------:|----:|----------:|-------------:|---------------------------:|
| 1d_cnn                            |    42 | 627 |   2.63    |       6.334  |                    0.4753  |
| 1d_cnn                            |    50 | 650 |  -2.792   |       8.548  |                    0.4108  |
| 1d_cnn                            |    57 | 640 |  -1.371   |       6.219  |                    0.4297  |
| 1d_cnn                            |    58 | 624 |  -5.035   |       5.342  |                    0.5288  |
| 1d_cnn                            |    60 | 680 |   0.2893  |       4.366  |                    0.2559  |
| 1d_cnn                            |    62 | 680 |  -0.813   |       3.664  |                    0.2206  |
| 1d_cnn                            |    64 | 680 |  -0.6358  |       4.626  |                    0.2912  |
| 1d_cnn                            |    65 | 615 |  -1.577   |       4.55   |                    0.2862  |
| edge_attention_cnn_new            |    42 | 627 |   2.477   |       6.224  |                    0.4482  |
| edge_attention_cnn_new            |    50 | 650 |  -2.75    |       8.683  |                    0.4585  |
| edge_attention_cnn_new            |    57 | 640 |  -1.305   |       6.409  |                    0.4469  |
| edge_attention_cnn_new            |    58 | 624 |  -5.095   |       5.003  |                    0.5304  |
| edge_attention_cnn_new            |    60 | 680 |  -0.06138 |       3.864  |                    0.2265  |
| edge_attention_cnn_new            |    62 | 680 |  -1.255   |       3.516  |                    0.2074  |
| edge_attention_cnn_new            |    64 | 680 |  -0.7447  |       4.403  |                    0.3074  |
| edge_attention_cnn_new            |    65 | 615 |  -1.856   |       4.491  |                    0.3285  |
| gradient_boosted_trees            |    42 | 627 |   1.741   |       4.72   |                    0.327   |
| gradient_boosted_trees            |    50 | 650 |  -0.4651  |       7.392  |                    0.2785  |
| gradient_boosted_trees            |    57 | 640 |  -0.273   |       2.174  |                    0.09375 |
| gradient_boosted_trees            |    58 | 624 |  -4.732   |       2.373  |                    0.4391  |
| gradient_boosted_trees            |    60 | 680 |   0.6661  |       3.08   |                    0.08235 |
| gradient_boosted_trees            |    62 | 680 |  -0.03942 |       2.6    |                    0.08382 |
| gradient_boosted_trees            |    64 | 680 |  -1.259   |       3.838  |                    0.1368  |
| gradient_boosted_trees            |    65 | 615 |  -1.611   |       2.88   |                    0.1171  |
| mlp                               |    42 | 627 |   1.815   |       5.49   |                    0.3238  |
| mlp                               |    50 | 650 |  -1.207   |       7.217  |                    0.2969  |
| mlp                               |    57 | 640 |  -0.6078  |       2.262  |                    0.06563 |
| mlp                               |    58 | 624 |  -4.778   |       3.198  |                    0.4792  |
| mlp                               |    60 | 680 |  -0.1515  |       3.411  |                    0.1235  |
| mlp                               |    62 | 680 |  -0.7781  |       2.951  |                    0.05588 |
| mlp                               |    64 | 680 |  -1.895   |       4.514  |                    0.2235  |
| mlp                               |    65 | 615 |  -1.957   |       3.503  |                    0.1626  |
| ridge                             |    42 | 627 |   3.023   |       4.794  |                    0.3812  |
| ridge                             |    50 | 650 |  -1.275   |       8.27   |                    0.3969  |
| ridge                             |    57 | 640 |  -0.3754  |       4.39   |                    0.2641  |
| ridge                             |    58 | 624 |  -3.609   |       3.887  |                    0.3894  |
| ridge                             |    60 | 680 |   0.354   |       3.001  |                    0.09412 |
| ridge                             |    62 | 680 |  -0.3151  |       2.635  |                    0.07206 |
| ridge                             |    64 | 680 |  -0.5396  |       3.93   |                    0.1941  |
| ridge                             |    65 | 615 |  -0.5875  |       3.512  |                    0.1415  |
| traditional_cfd_template_timewalk |    42 | 627 |  -0.4891  |       0.8035 |                    0       |
| traditional_cfd_template_timewalk |    50 | 650 |  -0.3047  |       0.7519 |                    0       |
| traditional_cfd_template_timewalk |    57 | 640 |  -0.2651  |       1.798  |                    0       |
| traditional_cfd_template_timewalk |    58 | 624 |   0.6842  |       0.2156 |                    0       |
| traditional_cfd_template_timewalk |    60 | 680 |  -0.9244  |       1.19   |                    0       |
| traditional_cfd_template_timewalk |    62 | 680 |  -0.4541  |       0.8574 |                    0       |
| traditional_cfd_template_timewalk |    64 | 680 |   0.7999  |       0.2198 |                    0       |
| traditional_cfd_template_timewalk |    65 | 615 |   0.1599  |       0.98   |                    0       |
| waveform_transformer              |    42 | 627 |   1.819   |       6.425  |                    0.4019  |
| waveform_transformer              |    50 | 650 |  -3.165   |      10.15   |                    0.4892  |
| waveform_transformer              |    57 | 640 |  -1.462   |       7.117  |                    0.4859  |
| waveform_transformer              |    58 | 624 |  -4.8     |       6.7    |                    0.6106  |
| waveform_transformer              |    60 | 680 |   0.2858  |       5.78   |                    0.4059  |
| waveform_transformer              |    62 | 680 |   0.7654  |       5.122  |                    0.3353  |
| waveform_transformer              |    64 | 680 |   0.248   |       5.955  |                    0.4103  |
| waveform_transformer              |    65 | 615 |  -0.4719  |       6.352  |                    0.4276  |

## Stress-Stratified Failure Modes

The stress axes are defined directly from raw waveform observables: pedestal
drift is the baseline displacement from the run/stave median; pulse-shape class
is late-tail fraction; pile-up separation is late secondary prominence spacing;
saturation onset is high amplitude or flat-top occupancy; energy proxy is
amplitude quartile; PID sideband is duplicate-readout amplitude ratio.

| stratum               | level           | method                            |    n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------|:----------------|:----------------------------------|-----:|----------:|-------------:|---------------------------:|
| energy_bin            | q1_low          | 1d_cnn                            | 1370 | -1.714    |       6.206  |                     0.4438 |
| energy_bin            | q1_low          | edge_attention_cnn_new            | 1370 | -2.022    |       6.741  |                     0.5051 |
| energy_bin            | q1_low          | gradient_boosted_trees            | 1370 | -0.6387   |       3.693  |                     0.1942 |
| energy_bin            | q1_low          | mlp                               | 1370 | -0.8654   |       3.583  |                     0.1891 |
| energy_bin            | q1_low          | ridge                             | 1370 |  0.6365   |       4.222  |                     0.2394 |
| energy_bin            | q1_low          | traditional_cfd_template_timewalk | 1370 | -0.3301   |       1.076  |                     0      |
| energy_bin            | q1_low          | waveform_transformer              | 1370 | -0.7507   |       7.208  |                     0.5153 |
| energy_bin            | q2              | 1d_cnn                            | 1437 | -1.332    |       4.499  |                     0.2944 |
| energy_bin            | q2              | edge_attention_cnn_new            | 1437 | -1.734    |       4.606  |                     0.3208 |
| energy_bin            | q2              | gradient_boosted_trees            | 1437 | -0.1838   |       3.327  |                     0.1649 |
| energy_bin            | q2              | mlp                               | 1437 | -1.115    |       3.73   |                     0.1955 |
| energy_bin            | q2              | ridge                             | 1437 | -0.2862   |       3.764  |                     0.215  |
| energy_bin            | q2              | traditional_cfd_template_timewalk | 1437 |  0.06399  |       0.8466 |                     0      |
| energy_bin            | q2              | waveform_transformer              | 1437 |  0.6265   |       6.143  |                     0.4238 |
| energy_bin            | q3              | 1d_cnn                            | 1361 |  0.2509   |       4.849  |                     0.2998 |
| energy_bin            | q3              | edge_attention_cnn_new            | 1361 | -0.04986  |       4.666  |                     0.291  |
| energy_bin            | q3              | gradient_boosted_trees            | 1361 | -0.2668   |       3.471  |                     0.1903 |
| energy_bin            | q3              | mlp                               | 1361 | -1.06     |       3.735  |                     0.2197 |
| energy_bin            | q3              | ridge                             | 1361 | -0.8217   |       4.089  |                     0.263  |
| energy_bin            | q3              | traditional_cfd_template_timewalk | 1361 |  0.1059   |       1.015  |                     0      |
| energy_bin            | q3              | waveform_transformer              | 1361 | -0.2838   |       6.67   |                     0.4328 |
| energy_bin            | q4_high         | 1d_cnn                            | 1028 | -2.632    |       6.017  |                     0.4173 |
| energy_bin            | q4_high         | edge_attention_cnn_new            | 1028 | -1.803    |       4.688  |                     0.3434 |
| energy_bin            | q4_high         | gradient_boosted_trees            | 1028 | -0.8092   |       3.388  |                     0.2296 |
| energy_bin            | q4_high         | mlp                               | 1028 | -1.215    |       3.769  |                     0.2646 |
| energy_bin            | q4_high         | ridge                             | 1028 | -1.095    |       4.07   |                     0.2393 |
| energy_bin            | q4_high         | traditional_cfd_template_timewalk | 1028 | -0.3502   |       1.052  |                     0      |
| energy_bin            | q4_high         | waveform_transformer              | 1028 | -2.467    |       5.847  |                     0.393  |
| pedestal_drift_bin    | high            | 1d_cnn                            | 1702 | -0.7205   |       6.921  |                     0.443  |
| pedestal_drift_bin    | high            | edge_attention_cnn_new            | 1702 | -0.9785   |       6.72   |                     0.4483 |
| pedestal_drift_bin    | high            | gradient_boosted_trees            | 1702 | -0.3801   |       3.691  |                     0.2133 |
| pedestal_drift_bin    | high            | mlp                               | 1702 | -0.3764   |       3.912  |                     0.2256 |
| pedestal_drift_bin    | high            | ridge                             | 1702 | -0.3508   |       4.228  |                     0.2485 |
| pedestal_drift_bin    | high            | traditional_cfd_template_timewalk | 1702 | -0.3016   |       1.036  |                     0      |
| pedestal_drift_bin    | high            | waveform_transformer              | 1702 | -2.843    |       6.992  |                     0.5071 |
| pedestal_drift_bin    | low             | 1d_cnn                            | 1687 | -1.252    |       4.823  |                     0.326  |
| pedestal_drift_bin    | low             | edge_attention_cnn_new            | 1687 | -1.439    |       4.739  |                     0.3337 |
| pedestal_drift_bin    | low             | gradient_boosted_trees            | 1687 | -0.6458   |       3.348  |                     0.1932 |
| pedestal_drift_bin    | low             | mlp                               | 1687 | -1.547    |       3.526  |                     0.2199 |
| pedestal_drift_bin    | low             | ridge                             | 1687 | -0.4836   |       4.128  |                     0.2466 |
| pedestal_drift_bin    | low             | traditional_cfd_template_timewalk | 1687 |  0.08862  |       0.985  |                     0      |
| pedestal_drift_bin    | low             | waveform_transformer              | 1687 |  0.1201   |       6.226  |                     0.4102 |
| pedestal_drift_bin    | mid             | 1d_cnn                            | 1807 | -1.319    |       4.803  |                     0.3121 |
| pedestal_drift_bin    | mid             | edge_attention_cnn_new            | 1807 | -1.4      |       4.503  |                     0.3188 |
| pedestal_drift_bin    | mid             | gradient_boosted_trees            | 1807 | -0.28     |       3.338  |                     0.171  |
| pedestal_drift_bin    | mid             | mlp                               | 1807 | -1.327    |       3.578  |                     0.197  |
| pedestal_drift_bin    | mid             | ridge                             | 1807 | -0.372    |       3.993  |                     0.2225 |
| pedestal_drift_bin    | mid             | traditional_cfd_template_timewalk | 1807 |  0.03306  |       1.011  |                     0      |
| pedestal_drift_bin    | mid             | waveform_transformer              | 1807 |  0.4404   |       6.127  |                     0.4167 |
| pid_sideband          | central         | 1d_cnn                            | 3572 | -1.247    |       4.91   |                     0.3231 |
| pid_sideband          | central         | edge_attention_cnn_new            | 3572 | -1.368    |       4.765  |                     0.3348 |
| pid_sideband          | central         | gradient_boosted_trees            | 3572 | -0.4135   |       3.393  |                     0.1859 |
| pid_sideband          | central         | mlp                               | 3572 | -1.116    |       3.575  |                     0.2032 |
| pid_sideband          | central         | ridge                             | 3572 | -0.195    |       4.073  |                     0.2394 |
| pid_sideband          | central         | traditional_cfd_template_timewalk | 3572 |  0.03289  |       0.9931 |                     0      |
| pid_sideband          | central         | waveform_transformer              | 3572 |  0.3193   |       6.37   |                     0.4295 |
| pid_sideband          | high_duplicate  | 1d_cnn                            |  870 |  0.2342   |       8.982  |                     0.5437 |
| pid_sideband          | high_duplicate  | edge_attention_cnn_new            |  870 | -0.6541   |       8.701  |                     0.5655 |
| pid_sideband          | high_duplicate  | gradient_boosted_trees            |  870 | -0.6071   |       3.963  |                     0.2287 |
| pid_sideband          | high_duplicate  | mlp                               |  870 | -0.5275   |       4.029  |                     0.2368 |
| pid_sideband          | high_duplicate  | ridge                             |  870 | -0.8084   |       4.463  |                     0.2747 |
| pid_sideband          | high_duplicate  | traditional_cfd_template_timewalk |  870 | -0.3449   |       1.056  |                     0      |
| pid_sideband          | high_duplicate  | waveform_transformer              |  870 | -5.475    |       5.768  |                     0.5713 |
| pid_sideband          | low_duplicate   | 1d_cnn                            |  754 | -1.361    |       4.995  |                     0.3196 |
| pid_sideband          | low_duplicate   | edge_attention_cnn_new            |  754 | -1.305    |       4.321  |                     0.2838 |
| pid_sideband          | low_duplicate   | gradient_boosted_trees            |  754 | -0.4478   |       3.353  |                     0.179  |
| pid_sideband          | low_duplicate   | mlp                               |  754 | -1.362    |       3.845  |                     0.2374 |
| pid_sideband          | low_duplicate   | ridge                             |  754 | -0.7525   |       3.621  |                     0.195  |
| pid_sideband          | low_duplicate   | traditional_cfd_template_timewalk |  754 |  0.224    |       1.036  |                     0      |
| pid_sideband          | low_duplicate   | waveform_transformer              |  754 |  0.5803   |       5.506  |                     0.3674 |
| pileup_separation_bin | close           | 1d_cnn                            | 1544 | -1.737    |       5.187  |                     0.3497 |
| pileup_separation_bin | close           | edge_attention_cnn_new            | 1544 | -1.739    |       4.899  |                     0.3284 |
| pileup_separation_bin | close           | gradient_boosted_trees            | 1544 | -0.6583   |       3.073  |                     0.1639 |
| pileup_separation_bin | close           | mlp                               | 1544 | -1.722    |       3.642  |                     0.2118 |
| pileup_separation_bin | close           | ridge                             | 1544 | -1.076    |       3.991  |                     0.2558 |
| pileup_separation_bin | close           | traditional_cfd_template_timewalk | 1544 | -0.3407   |       1.048  |                     0      |
| pileup_separation_bin | close           | waveform_transformer              | 1544 |  0.7941   |       5.742  |                     0.3841 |
| pileup_separation_bin | late            | 1d_cnn                            |    4 | -6.307    |       2.984  |                     0.5    |
| pileup_separation_bin | late            | edge_attention_cnn_new            |    4 | -4.593    |       2.179  |                     0.5    |
| pileup_separation_bin | late            | gradient_boosted_trees            |    4 | -2.692    |       3.787  |                     0.25   |
| pileup_separation_bin | late            | mlp                               |    4 | -3.45     |       2.86   |                     0.25   |
| pileup_separation_bin | late            | ridge                             |    4 | -0.2492   |       1.925  |                     0      |
| pileup_separation_bin | late            | traditional_cfd_template_timewalk |    4 | -0.3437   |       1.066  |                     0      |
| pileup_separation_bin | late            | waveform_transformer              |    4 | -7.956    |       3.238  |                     0.75   |
| pileup_separation_bin | mid             | 1d_cnn                            | 1142 |  0.6916   |       5.525  |                     0.3651 |
| pileup_separation_bin | mid             | edge_attention_cnn_new            | 1142 | -0.5629   |       5.575  |                     0.3774 |
| pileup_separation_bin | mid             | gradient_boosted_trees            | 1142 | -0.9686   |       3.49   |                     0.2049 |
| pileup_separation_bin | mid             | mlp                               | 1142 | -1.794    |       3.874  |                     0.232  |
| pileup_separation_bin | mid             | ridge                             | 1142 | -1.148    |       4.308  |                     0.2723 |
| pileup_separation_bin | mid             | traditional_cfd_template_timewalk | 1142 |  0.06944  |       1.026  |                     0      |
| pileup_separation_bin | mid             | waveform_transformer              | 1142 | -2.975    |       6.09   |                     0.4816 |
| pileup_separation_bin | none            | 1d_cnn                            | 2506 | -1.462    |       5.18   |                     0.3627 |
| pileup_separation_bin | none            | edge_attention_cnn_new            | 2506 | -1.243    |       5.391  |                     0.3839 |
| pileup_separation_bin | none            | gradient_boosted_trees            | 2506 | -0.02037  |       3.672  |                     0.2035 |
| pileup_separation_bin | none            | mlp                               | 2506 | -0.4076   |       3.583  |                     0.2067 |
| pileup_separation_bin | none            | ridge                             | 2506 |  0.3112   |       3.748  |                     0.2135 |
| pileup_separation_bin | none            | traditional_cfd_template_timewalk | 2506 |  0.03191  |       0.9714 |                     0      |
| pileup_separation_bin | none            | waveform_transformer              | 2506 | -0.5962   |       6.891  |                     0.4637 |
| pulse_shape_class     | compact         | 1d_cnn                            | 1796 | -0.5064   |       6.57   |                     0.4482 |
| pulse_shape_class     | compact         | edge_attention_cnn_new            | 1796 | -1.255    |       6.467  |                     0.4705 |
| pulse_shape_class     | compact         | gradient_boosted_trees            | 1796 | -1.032    |       3.422  |                     0.1982 |
| pulse_shape_class     | compact         | mlp                               | 1796 | -1.739    |       3.846  |                     0.2066 |
| pulse_shape_class     | compact         | ridge                             | 1796 | -0.7434   |       4.61   |                     0.2884 |
| pulse_shape_class     | compact         | traditional_cfd_template_timewalk | 1796 | -0.2118   |       1.047  |                     0      |
| pulse_shape_class     | compact         | waveform_transformer              | 1796 | -1.5      |       7.088  |                     0.5178 |
| pulse_shape_class     | late_tail       | 1d_cnn                            | 1755 | -1.156    |       5.221  |                     0.3561 |
| pulse_shape_class     | late_tail       | edge_attention_cnn_new            | 1755 | -0.8423   |       5.278  |                     0.3544 |
| pulse_shape_class     | late_tail       | gradient_boosted_trees            | 1755 |  0.3812   |       3.829  |                     0.2291 |
| pulse_shape_class     | late_tail       | mlp                               | 1755 | -0.06738  |       3.783  |                     0.2274 |
| pulse_shape_class     | late_tail       | ridge                             | 1755 | -0.1867   |       3.629  |                     0.2177 |
| pulse_shape_class     | late_tail       | traditional_cfd_template_timewalk | 1755 |  0.06197  |       0.9646 |                     0      |
| pulse_shape_class     | late_tail       | waveform_transformer              | 1755 | -2.731    |       6.055  |                     0.4678 |
| pulse_shape_class     | nominal         | 1d_cnn                            | 1645 | -1.453    |       4.412  |                     0.2663 |
| pulse_shape_class     | nominal         | edge_attention_cnn_new            | 1645 | -1.743    |       4.174  |                     0.2644 |
| pulse_shape_class     | nominal         | gradient_boosted_trees            | 1645 | -0.5418   |       2.935  |                     0.1459 |
| pulse_shape_class     | nominal         | mlp                               | 1645 | -1.603    |       3.525  |                     0.2073 |
| pulse_shape_class     | nominal         | ridge                             | 1645 | -0.4497   |       3.89   |                     0.2073 |
| pulse_shape_class     | nominal         | traditional_cfd_template_timewalk | 1645 | -0.008682 |       1.012  |                     0      |
| pulse_shape_class     | nominal         | waveform_transformer              | 1645 |  1.796    |       4.912  |                     0.3386 |
| saturation_onset_bin  | linear          | 1d_cnn                            | 3771 | -0.8221   |       5.707  |                     0.3816 |
| saturation_onset_bin  | linear          | edge_attention_cnn_new            | 3771 | -1.123    |       5.526  |                     0.3933 |
| saturation_onset_bin  | linear          | gradient_boosted_trees            | 3771 | -0.5205   |       3.59   |                     0.1965 |
| saturation_onset_bin  | linear          | mlp                               | 3771 | -1.159    |       3.75   |                     0.2137 |
| saturation_onset_bin  | linear          | ridge                             | 3771 | -0.5448   |       4.255  |                     0.2519 |
| saturation_onset_bin  | linear          | traditional_cfd_template_timewalk | 3771 |  0.04744  |       1.006  |                     0      |
| saturation_onset_bin  | linear          | waveform_transformer              | 3771 | -1.031    |       6.886  |                     0.4726 |
| saturation_onset_bin  | near_saturation | 1d_cnn                            | 1425 | -1.809    |       4.59   |                     0.3011 |
| saturation_onset_bin  | near_saturation | edge_attention_cnn_new            | 1425 | -1.511    |       4.482  |                     0.294  |
| saturation_onset_bin  | near_saturation | gradient_boosted_trees            | 1425 | -0.2603   |       3.145  |                     0.1804 |
| saturation_onset_bin  | near_saturation | mlp                               | 1425 | -0.7952   |       3.733  |                     0.214  |
| saturation_onset_bin  | near_saturation | ridge                             | 1425 | -0.01619  |       3.725  |                     0.2042 |
| saturation_onset_bin  | near_saturation | traditional_cfd_template_timewalk | 1425 | -0.3938   |       1.021  |                     0      |
| saturation_onset_bin  | near_saturation | waveform_transformer              | 1425 |  0.3405   |       5.728  |                     0.3691 |

## Pulse-Shape Systematics

The ablation panel removes correlated feature families from the
gradient-boosted-tree learner to check whether apparent calibration gains are
coming from pedestal/pretrigger cues or late pulse-shape information.

| ablation                       |   n_features |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   delta_sigma68_vs_full_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|-------------:|-------------:|--------------------:|---------------------:|---------------------------:|---------------------------:|
| drop_tail_pulse_shape_features |           24 |        3.414 |               2.852 |                4.198 |                   -0.02095 |                     0.1859 |
| full_gradient_boosted_trees    |           33 |        3.435 |               2.747 |                4.235 |                    0       |                     0.1855 |
| drop_pretrigger_features       |           27 |        3.757 |               3.078 |                4.51  |                    0.3215  |                     0.2102 |
| amplitude_cfd_only             |            5 |        4.088 |               3.34  |                4.972 |                    0.6526  |                     0.239  |

## Caveats

This is a raw-ROOT calibration benchmark, not an externally truth-labeled beam
PID or energy measurement.  Energy reconstruction is represented by duplicate
readout amplitude closure and amplitude strata; PID boundaries are represented
by duplicate-ratio sidebands.  These proxies are scientifically useful for
detecting saturation/pedestal/pile-up failure modes, but they cannot establish
absolute particle identity or deposited energy without a separate truth bridge.
The bootstrap intervals cover transfer among the held-out runs, not systematic
uncertainty from detector response, calibration constants, or unobserved
beamline composition.

Runtime was `43.8 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.

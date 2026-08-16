# S45a: Pedestal-Memory Pulse-Shape and Timing Bias Closure

## Abstract

Ticket `#2424` requested a run-held-out closure test separating true
pulse-shape/timing shifts from pedestal artifacts under amplitude, stave,
rate, and pretrigger-history stress.  This study reproduces the registered raw B-stack ROOT pulse
count, constructs an onset-residual benchmark directly from `h101/HRDv`, and
compares one strong traditional method with ridge, gradient-boosted trees, MLP,
1D-CNN, and a new gated edge-attention CNN.  The winner written to `result.json`
is **`traditional_cfd_template_timewalk`**, with held-out run-bootstrap sigma68
`0.892 ns [0.6843, 1.244]`.


## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once before this analysis but returned the known malformed
`null` response.  Direct queue inspection showed open testbeam tickets and no
valid `worker:testbeam-laptop-1` claim.  To keep exactly one active ticket
without re-running the claim helper, issue `#2424` was manually moved from
`factory:open` to `factory:claimed` and labeled `worker:testbeam-laptop-1`.
This report is therefore bound to ticket `#2424` and no second helper claim was
performed.

## S45a Interpretation Layer

The reusable raw-ROOT benchmark estimates a run/stave-centered CFD20 onset
residual, then asks whether methods trained on other runs predict away
pedestal-coupled timing bias without receiving run identifiers.  The S45a
interpretation is the pedestal-memory closure: a method improves only if its
held-out run-block sigma68 and tails shrink while the pedestal-drift, pulse-tail,
pile-up, saturation, amplitude, and duplicate-ratio sidebands do not reveal a
single memorized nuisance slice carrying the result.

## Raw ROOT Reproduction

Input files are `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.  For every event the
branch `HRDv` is reshaped as `(8, 18)`.  For stave channel `c`,

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

A selected B-stack pulse satisfies `A_c > 1000 ADC`
for one of B2/B4/B6/B8.  The reproduction is performed before any row sampling
or training:

| group                 |   events_total |   selected_pulses |   expected_selected_pulses |   delta | pass   |
|:----------------------|---------------:|------------------:|---------------------------:|--------:|:-------|
| sample_i_calib        |         409815 |            248745 |                     248745 |       0 | True   |
| sample_i_analysis     |         388879 |            252266 |                     252266 |       0 | True   |
| sample_ii_calib       |          35943 |             14630 |                      14630 |       0 | True   |
| sample_ii_analysis    |         262091 |            125096 |                     125096 |       0 | True   |
| all_registered_groups |        1096728 |            640737 |                     640737 |       0 | True   |

## Estimand and Split

For each selected pulse the CFD time at fraction `f` is the first pre-peak linear
interpolation satisfying

`x(t_f)-b = f A`.

The target is the run/stave-centered CFD20 onset residual,

`y_i = 10 ns * [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The split is by run: held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]` and all other
registered B-stack runs train the models.  The sampled benchmark contains:

| split   |   rows |
|:--------|-------:|
| heldout |   3669 |
| train   |  10407 |

Confidence intervals are percentile 95% intervals from
`320` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

| method                            | family           | description                                                                                                  |
|:----------------------------------|:-----------------|:-------------------------------------------------------------------------------------------------------------|
| traditional_cfd_template_timewalk | traditional      | CFD20/CFD50 template proxy plus monotone log-amplitude time-walk correction                                  |
| ridge                             | linear ML        | standardized ridge regression on amplitude, pedestal, CFD, tail, pile-up, saturation, and normalized samples |
| gradient_boosted_trees            | tree ML          | histogram gradient-boosted regression on the same engineered waveform features                               |
| mlp                               | neural tabular   | two-hidden-layer perceptron on engineered waveform and detector-state summaries                              |
| 1d_cnn                            | neural waveform  | compact 1D convolutional regressor over the 18 normalized ADC samples                                        |
| waveform_transformer              | neural waveform  | one-layer self-attention encoder over waveform samples with amplitude-weighted pooling                       |
| edge_attention_cnn_new            | new architecture | gated 1D-CNN whose learned edge gate emphasizes onset and late-curvature samples                             |

The traditional comparator is intentionally strong.  It starts from a CFD50
residual, fits a non-increasing isotonic correction in `log(1+A)` on training
runs, and adds a linear template-shape proxy from `(t_0.50 - t_0.20)`.  Formally,

`hat y = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`,

where `g` is constrained monotone to encode ordinary time walk.

The new `edge_attention_cnn_new` is sensible for this ticket because the
dominant information is local to the leading edge, while late curvature and
flat-top samples carry pile-up and saturation nuisance information.  Its gate is
learned from the waveform and multiplicatively reweights convolutional channels.

No method receives event number or run identifier as a feature.

## Primary Held-Out Results

| method                            |    n |   bias_ns |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   rms_ns |   tail_fraction_abs_gt_5ns |   tail_fraction_abs_gt_10ns |
|:----------------------------------|-----:|----------:|-------------:|--------------------:|---------------------:|---------:|---------------------------:|----------------------------:|
| traditional_cfd_template_timewalk | 3669 |    0.2123 |        0.892 |              0.6843 |                1.244 |   0.8673 |                     0      |                     0       |
| gradient_boosted_trees            | 3669 |   -0.5432 |        3.608 |              3.026  |                4.296 |   4.145  |                     0.1851 |                     0.02698 |
| ridge                             | 3669 |   -0.2063 |        4.228 |              3.752  |                4.87  |   4.239  |                     0.2341 |                     0.01908 |
| mlp                               | 3669 |   -0.3798 |        4.423 |              3.866  |                5.097 |   4.409  |                     0.2617 |                     0.02208 |
| edge_attention_cnn_new            | 3669 |   -1.795  |        6.751 |              6.098  |                7.505 |   9.596  |                     0.4715 |                     0.1875  |
| 1d_cnn                            | 3669 |   -0.5123 |        8.443 |              7.693  |                9.711 |  13.74   |                     0.5407 |                     0.2448  |
| waveform_transformer              | 3669 |   -3.419  |       20.08  |             11.77   |               26.39  |  28.03   |                     0.659  |                     0.4952  |

The traditional method has sigma68 `0.892 ns`; the selected
winner `traditional_cfd_template_timewalk` has sigma68 `0.892 ns`.

## Paired Method Deltas

The following deltas are paired by held-out run-block bootstrap against the
traditional reference.  Positive `delta_sigma68_ns` means the method is wider
than the traditional comparator.

| method                 | reference_method                  |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |   delta_tail_fraction_abs_gt_5ns |   delta_tail_fraction_abs_gt_5ns_ci_low |   delta_tail_fraction_abs_gt_5ns_ci_high |
|:-----------------------|:----------------------------------|-------------------:|--------------------------:|---------------------------:|---------------------------------:|----------------------------------------:|-----------------------------------------:|
| gradient_boosted_trees | traditional_cfd_template_timewalk |              2.716 |                     2.087 |                      3.428 |                           0.1851 |                                  0.1324 |                                   0.2488 |
| ridge                  | traditional_cfd_template_timewalk |              3.336 |                     2.749 |                      3.987 |                           0.2341 |                                  0.1716 |                                   0.3122 |
| mlp                    | traditional_cfd_template_timewalk |              3.531 |                     2.897 |                      4.209 |                           0.2617 |                                  0.207  |                                   0.33   |
| edge_attention_cnn_new | traditional_cfd_template_timewalk |              5.859 |                     5.101 |                      6.582 |                           0.4715 |                                  0.4272 |                                   0.5194 |
| 1d_cnn                 | traditional_cfd_template_timewalk |              7.551 |                     6.721 |                      8.848 |                           0.5407 |                                  0.4951 |                                   0.5899 |
| waveform_transformer   | traditional_cfd_template_timewalk |             19.19  |                    10.84  |                     25.44  |                           0.659  |                                  0.5984 |                                   0.7155 |

## Run Stability

| method                            |   run |   n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|------:|----:|----------:|-------------:|---------------------------:|
| 1d_cnn                            |    42 | 460 |   0.7998  |      10.12   |                     0.563  |
| 1d_cnn                            |    50 | 460 |  -1.549   |       7.085  |                     0.4348 |
| 1d_cnn                            |    57 | 460 |  -0.9187  |      11.04   |                     0.5957 |
| 1d_cnn                            |    58 | 459 |  -2.495   |       9.8    |                     0.6492 |
| 1d_cnn                            |    60 | 460 |   0.6657  |       7.962  |                     0.5543 |
| 1d_cnn                            |    62 | 460 |  -0.1681  |       6.798  |                     0.5022 |
| 1d_cnn                            |    64 | 460 |  -0.6631  |       7.352  |                     0.4717 |
| 1d_cnn                            |    65 | 450 |  -0.5705  |       8.571  |                     0.5556 |
| edge_attention_cnn_new            |    42 | 460 |  -0.4775  |       8.141  |                     0.5739 |
| edge_attention_cnn_new            |    50 | 460 |  -3.635   |       4.782  |                     0.4739 |
| edge_attention_cnn_new            |    57 | 460 |  -1.782   |       7.837  |                     0.5326 |
| edge_attention_cnn_new            |    58 | 459 |  -3.026   |       7.944  |                     0.5447 |
| edge_attention_cnn_new            |    60 | 460 |  -0.37    |       6.968  |                     0.45   |
| edge_attention_cnn_new            |    62 | 460 |  -1.066   |       6.391  |                     0.3891 |
| edge_attention_cnn_new            |    64 | 460 |  -1.939   |       6.118  |                     0.3739 |
| edge_attention_cnn_new            |    65 | 450 |  -2.56    |       6.305  |                     0.4333 |
| gradient_boosted_trees            |    42 | 460 |   1.796   |       4.719  |                     0.3304 |
| gradient_boosted_trees            |    50 | 460 |   0.5486  |       2.793  |                     0.1239 |
| gradient_boosted_trees            |    57 | 460 |  -0.7346  |       2.896  |                     0.1196 |
| gradient_boosted_trees            |    58 | 459 |  -2.545   |       4.223  |                     0.3246 |
| gradient_boosted_trees            |    60 | 460 |   0.08712 |       3.859  |                     0.2022 |
| gradient_boosted_trees            |    62 | 460 |  -0.3369  |       3.21   |                     0.1109 |
| gradient_boosted_trees            |    64 | 460 |  -1.467   |       2.39   |                     0.1    |
| gradient_boosted_trees            |    65 | 450 |  -1.861   |       2.908  |                     0.1689 |
| mlp                               |    42 | 460 |   2.23    |       5.165  |                     0.4283 |
| mlp                               |    50 | 460 |   0.5135  |       3.304  |                     0.2065 |
| mlp                               |    57 | 460 |   0.1667  |       4.018  |                     0.2043 |
| mlp                               |    58 | 459 |  -2.402   |       5.166  |                     0.3878 |
| mlp                               |    60 | 460 |  -0.5922  |       4.516  |                     0.2804 |
| mlp                               |    62 | 460 |  -0.3395  |       4.239  |                     0.2196 |
| mlp                               |    64 | 460 |  -1.456   |       3.246  |                     0.1609 |
| mlp                               |    65 | 450 |  -2.087   |       3.725  |                     0.2044 |
| ridge                             |    42 | 460 |   2.263   |       5.725  |                     0.4326 |
| ridge                             |    50 | 460 |   0.4338  |       3.922  |                     0.2022 |
| ridge                             |    57 | 460 |  -0.1583  |       4.882  |                     0.3065 |
| ridge                             |    58 | 459 |  -1.312   |       4.875  |                     0.3312 |
| ridge                             |    60 | 460 |   0.181   |       3.838  |                     0.1761 |
| ridge                             |    62 | 460 |   0.08673 |       3.676  |                     0.1348 |
| ridge                             |    64 | 460 |  -1.166   |       3.1    |                     0.1109 |
| ridge                             |    65 | 450 |  -0.8916  |       3.469  |                     0.1778 |
| traditional_cfd_template_timewalk |    42 | 460 |  -0.2686  |       1.331  |                     0      |
| traditional_cfd_template_timewalk |    50 | 460 |  -0.1809  |       0.8435 |                     0      |
| traditional_cfd_template_timewalk |    57 | 460 |  -0.05474 |       0.9933 |                     0      |
| traditional_cfd_template_timewalk |    58 | 459 |   0.7371  |       0.5124 |                     0      |
| traditional_cfd_template_timewalk |    60 | 460 |   0.03539 |       1.02   |                     0      |
| traditional_cfd_template_timewalk |    62 | 460 |  -0.07208 |       1.062  |                     0      |
| traditional_cfd_template_timewalk |    64 | 460 |   0.3398  |       0.3875 |                     0      |
| traditional_cfd_template_timewalk |    65 | 450 |   0.2858  |       0.8354 |                     0      |
| waveform_transformer              |    42 | 460 |  -2.456   |      29.05   |                     0.7587 |
| waveform_transformer              |    50 | 460 |  -2.29    |      25.75   |                     0.7087 |
| waveform_transformer              |    57 | 460 |  -3.043   |      27.89   |                     0.7804 |
| waveform_transformer              |    58 | 459 |  -2.688   |      28.73   |                     0.7015 |
| waveform_transformer              |    60 | 460 |  -3.869   |      10.21   |                     0.5543 |
| waveform_transformer              |    62 | 460 |  -3.772   |      11.12   |                     0.5304 |
| waveform_transformer              |    64 | 460 |  -4.298   |      11.68   |                     0.5826 |
| waveform_transformer              |    65 | 450 |  -3.588   |      24.75   |                     0.6556 |

## Stress-Stratified Results

The requested stress axes are implemented as raw-waveform proxies:
pedestal drift is the absolute baseline displacement from the run/stave median;
pulse-shape class is the late-tail fraction; pile-up separation is the spacing
to a late secondary prominence; saturation onset is high amplitude or flat-top
occupancy; energy proxy is amplitude quartile; PID sideband is the duplicate
readout amplitude ratio sideband.

| stratum               | level           | method                            |    n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------|:----------------|:----------------------------------|-----:|----------:|-------------:|---------------------------:|
| energy_bin            | q1_low          | 1d_cnn                            |  948 |   0.7654  |       9.36   |                     0.597  |
| energy_bin            | q1_low          | edge_attention_cnn_new            |  948 |  -2       |       8.517  |                     0.5348 |
| energy_bin            | q1_low          | gradient_boosted_trees            |  948 |  -0.7778  |       3.642  |                     0.1688 |
| energy_bin            | q1_low          | mlp                               |  948 |  -0.1137  |       4.108  |                     0.2184 |
| energy_bin            | q1_low          | ridge                             |  948 |   0.6893  |       4.092  |                     0.2141 |
| energy_bin            | q1_low          | traditional_cfd_template_timewalk |  948 |  -0.1107  |       1.017  |                     0      |
| energy_bin            | q1_low          | waveform_transformer              |  948 |  -3.216   |      28.84   |                     0.6973 |
| energy_bin            | q2              | 1d_cnn                            |  982 |   1.328   |       6.739  |                     0.4715 |
| energy_bin            | q2              | edge_attention_cnn_new            |  982 |  -1.447   |       5.684  |                     0.3859 |
| energy_bin            | q2              | gradient_boosted_trees            |  982 |  -0.4954  |       3.661  |                     0.1731 |
| energy_bin            | q2              | mlp                               |  982 |  -0.7696  |       4.715  |                     0.2892 |
| energy_bin            | q2              | ridge                             |  982 |  -0.1419  |       4.12   |                     0.2342 |
| energy_bin            | q2              | traditional_cfd_template_timewalk |  982 |   0.3236  |       0.8292 |                     0      |
| energy_bin            | q2              | waveform_transformer              |  982 |  -1.838   |      23.85   |                     0.6242 |
| energy_bin            | q3              | 1d_cnn                            |  986 |  -0.7808  |       8.313  |                     0.5375 |
| energy_bin            | q3              | edge_attention_cnn_new            |  986 |   0.04251 |       5.461  |                     0.3793 |
| energy_bin            | q3              | gradient_boosted_trees            |  986 |  -0.5602  |       3.617  |                     0.1897 |
| energy_bin            | q3              | mlp                               |  986 |  -0.2963  |       4.543  |                     0.2718 |
| energy_bin            | q3              | ridge                             |  986 |  -0.7722  |       4.447  |                     0.2576 |
| energy_bin            | q3              | traditional_cfd_template_timewalk |  986 |   0.4034  |       0.8736 |                     0      |
| energy_bin            | q3              | waveform_transformer              |  986 |  -4.519   |      19.04   |                     0.7018 |
| energy_bin            | q4_high         | 1d_cnn                            |  753 |  -4.884   |       5.733  |                     0.5644 |
| energy_bin            | q4_high         | edge_attention_cnn_new            |  753 |  -5.613   |       6.545  |                     0.6242 |
| energy_bin            | q4_high         | gradient_boosted_trees            |  753 |  -0.2552  |       3.498  |                     0.2151 |
| energy_bin            | q4_high         | mlp                               |  753 |  -0.5378  |       4.225  |                     0.2669 |
| energy_bin            | q4_high         | ridge                             |  753 |  -0.7645  |       3.998  |                     0.2284 |
| energy_bin            | q4_high         | traditional_cfd_template_timewalk |  753 |   0.02594 |       0.9468 |                     0      |
| energy_bin            | q4_high         | waveform_transformer              |  753 |  -4.437   |       7.871  |                     0.6003 |
| pedestal_drift_bin    | high            | 1d_cnn                            | 1145 |  -2.142   |       8.859  |                     0.5825 |
| pedestal_drift_bin    | high            | edge_attention_cnn_new            | 1145 |  -3.538   |       8.765  |                     0.5738 |
| pedestal_drift_bin    | high            | gradient_boosted_trees            | 1145 |  -0.4697  |       3.735  |                     0.1983 |
| pedestal_drift_bin    | high            | mlp                               | 1145 |   0.2398  |       4.377  |                     0.2585 |
| pedestal_drift_bin    | high            | ridge                             | 1145 |  -0.1673  |       4.064  |                     0.2271 |
| pedestal_drift_bin    | high            | traditional_cfd_template_timewalk | 1145 |   0.03763 |       0.9358 |                     0      |
| pedestal_drift_bin    | high            | waveform_transformer              | 1145 | -13.07    |      14.08   |                     0.7729 |
| pedestal_drift_bin    | low             | 1d_cnn                            | 1280 |   0.03882 |       8.267  |                     0.5258 |
| pedestal_drift_bin    | low             | edge_attention_cnn_new            | 1280 |  -1.389   |       5.942  |                     0.4313 |
| pedestal_drift_bin    | low             | gradient_boosted_trees            | 1280 |  -0.7025  |       3.442  |                     0.1711 |
| pedestal_drift_bin    | low             | mlp                               | 1280 |  -0.7713  |       4.498  |                     0.2656 |
| pedestal_drift_bin    | low             | ridge                             | 1280 |  -0.295   |       4.527  |                     0.2594 |
| pedestal_drift_bin    | low             | traditional_cfd_template_timewalk | 1280 |   0.2492  |       0.8655 |                     0      |
| pedestal_drift_bin    | low             | waveform_transformer              | 1280 |  -2.03    |      22.6    |                     0.6375 |
| pedestal_drift_bin    | mid             | 1d_cnn                            | 1244 |  -0.1112  |       7.915  |                     0.5177 |
| pedestal_drift_bin    | mid             | edge_attention_cnn_new            | 1244 |  -1.233   |       6.046  |                     0.4188 |
| pedestal_drift_bin    | mid             | gradient_boosted_trees            | 1244 |  -0.4639  |       3.537  |                     0.1873 |
| pedestal_drift_bin    | mid             | mlp                               | 1244 |  -0.6374  |       4.336  |                     0.2605 |
| pedestal_drift_bin    | mid             | ridge                             | 1244 |  -0.2031  |       4.075  |                     0.2146 |
| pedestal_drift_bin    | mid             | traditional_cfd_template_timewalk | 1244 |   0.3112  |       0.8642 |                     0      |
| pedestal_drift_bin    | mid             | waveform_transformer              | 1244 |  -1.771   |      20.08   |                     0.5764 |
| pid_sideband          | central         | 1d_cnn                            | 2543 |   0.3073  |       8.335  |                     0.5379 |
| pid_sideband          | central         | edge_attention_cnn_new            | 2543 |  -1.069   |       5.886  |                     0.4133 |
| pid_sideband          | central         | gradient_boosted_trees            | 2543 |  -0.5577  |       3.494  |                     0.1781 |
| pid_sideband          | central         | mlp                               | 2543 |  -0.4197  |       4.437  |                     0.2643 |
| pid_sideband          | central         | ridge                             | 2543 |  -0.07186 |       4.304  |                     0.2422 |
| pid_sideband          | central         | traditional_cfd_template_timewalk | 2543 |   0.2692  |       0.8645 |                     0      |
| pid_sideband          | central         | waveform_transformer              | 2543 |  -1.685   |      24.73   |                     0.6217 |
| pid_sideband          | high_duplicate  | 1d_cnn                            |  565 |  -4.234   |       7.834  |                     0.5858 |
| pid_sideband          | high_duplicate  | edge_attention_cnn_new            |  565 |  -8.351   |       9.33   |                     0.7504 |
| pid_sideband          | high_duplicate  | gradient_boosted_trees            |  565 |  -0.8733  |       4.047  |                     0.2159 |
| pid_sideband          | high_duplicate  | mlp                               |  565 |   0.145   |       4.307  |                     0.2389 |
| pid_sideband          | high_duplicate  | ridge                             |  565 |  -0.6407  |       4.144  |                     0.2265 |
| pid_sideband          | high_duplicate  | traditional_cfd_template_timewalk |  565 |  -0.01199 |       1.055  |                     0      |
| pid_sideband          | high_duplicate  | waveform_transformer              |  565 | -22.77    |       4.58   |                     1      |
| pid_sideband          | low_duplicate   | 1d_cnn                            |  561 |  -1.571   |       7.295  |                     0.508  |
| pid_sideband          | low_duplicate   | edge_attention_cnn_new            |  561 |  -1.406   |       6.434  |                     0.4545 |
| pid_sideband          | low_duplicate   | gradient_boosted_trees            |  561 |  -0.2421  |       3.564  |                     0.1854 |
| pid_sideband          | low_duplicate   | mlp                               |  561 |  -0.8068  |       4.388  |                     0.2727 |
| pid_sideband          | low_duplicate   | ridge                             |  561 |  -0.33    |       3.947  |                     0.205  |
| pid_sideband          | low_duplicate   | traditional_cfd_template_timewalk |  561 |   0.3214  |       0.8954 |                     0      |
| pid_sideband          | low_duplicate   | waveform_transformer              |  561 |  -1.611   |       7.153  |                     0.4848 |
| pileup_separation_bin | close           | 1d_cnn                            | 1088 |  -0.7358  |       6.553  |                     0.4292 |
| pileup_separation_bin | close           | edge_attention_cnn_new            | 1088 |  -3.362   |       6.467  |                     0.5074 |
| pileup_separation_bin | close           | gradient_boosted_trees            | 1088 |  -0.7992  |       3.146  |                     0.1553 |
| pileup_separation_bin | close           | mlp                               | 1088 |  -1.442   |       4.107  |                     0.2592 |
| pileup_separation_bin | close           | ridge                             | 1088 |  -1.231   |       4.148  |                     0.2574 |
| pileup_separation_bin | close           | traditional_cfd_template_timewalk | 1088 |   0.1853  |       0.912  |                     0      |
| pileup_separation_bin | close           | waveform_transformer              | 1088 |  -5.976   |       7.201  |                     0.5607 |
| pileup_separation_bin | mid             | 1d_cnn                            |  804 |  -2.36    |       6.316  |                     0.4527 |
| pileup_separation_bin | mid             | edge_attention_cnn_new            |  804 |  -3.11    |       8.31   |                     0.5485 |
| pileup_separation_bin | mid             | gradient_boosted_trees            |  804 |  -1.436   |       3.217  |                     0.1791 |
| pileup_separation_bin | mid             | mlp                               |  804 |  -1.425   |       4.153  |                     0.25   |
| pileup_separation_bin | mid             | ridge                             |  804 |  -1.007   |       4.367  |                     0.2525 |
| pileup_separation_bin | mid             | traditional_cfd_template_timewalk |  804 |   0.341   |       0.8996 |                     0      |
| pileup_separation_bin | mid             | waveform_transformer              |  804 | -15.54    |      10.21   |                     0.8109 |
| pileup_separation_bin | none            | 1d_cnn                            | 1777 |   0.6441  |      12.48   |                     0.6488 |
| pileup_separation_bin | none            | edge_attention_cnn_new            | 1777 |  -0.6794  |       6.158  |                     0.4147 |
| pileup_separation_bin | none            | gradient_boosted_trees            | 1777 |   0.1028  |       4.064  |                     0.206  |
| pileup_separation_bin | none            | mlp                               | 1777 |   0.5173  |       4.476  |                     0.2684 |
| pileup_separation_bin | none            | ridge                             | 1777 |   0.6851  |       3.819  |                     0.2116 |
| pileup_separation_bin | none            | traditional_cfd_template_timewalk | 1777 |   0.2059  |       0.8511 |                     0      |
| pileup_separation_bin | none            | waveform_transformer              | 1777 |   3.404   |      31.25   |                     0.6505 |
| pulse_shape_class     | compact         | 1d_cnn                            | 1213 |   1.068   |       7.551  |                     0.5153 |
| pulse_shape_class     | compact         | edge_attention_cnn_new            | 1213 |  -3.726   |       8.012  |                     0.5375 |
| pulse_shape_class     | compact         | gradient_boosted_trees            | 1213 |  -1.62    |       3.46   |                     0.1723 |
| pulse_shape_class     | compact         | mlp                               | 1213 |  -1.113   |       4.255  |                     0.2539 |
| pulse_shape_class     | compact         | ridge                             | 1213 |  -0.6165  |       4.591  |                     0.2704 |
| pulse_shape_class     | compact         | traditional_cfd_template_timewalk | 1213 |   0.1033  |       1.019  |                     0      |
| pulse_shape_class     | compact         | waveform_transformer              | 1213 | -16       |      10.69   |                     0.7939 |
| pulse_shape_class     | late_tail       | 1d_cnn                            | 1241 |  -4.214   |      18.79   |                     0.7454 |
| pulse_shape_class     | late_tail       | edge_attention_cnn_new            | 1241 |  -1.181   |       7.097  |                     0.4859 |
| pulse_shape_class     | late_tail       | gradient_boosted_trees            | 1241 |   0.8813  |       4.338  |                     0.2458 |
| pulse_shape_class     | late_tail       | mlp                               | 1241 |   1.217   |       4.417  |                     0.2804 |
| pulse_shape_class     | late_tail       | ridge                             | 1241 |   0.5782  |       3.964  |                     0.228  |
| pulse_shape_class     | late_tail       | traditional_cfd_template_timewalk | 1241 |   0.329   |       0.8661 |                     0      |
| pulse_shape_class     | late_tail       | waveform_transformer              | 1241 |  20.18    |      36.54   |                     0.7583 |
| pulse_shape_class     | nominal         | 1d_cnn                            | 1215 |  -0.03748 |       5.667  |                     0.3572 |
| pulse_shape_class     | nominal         | edge_attention_cnn_new            | 1215 |  -1.161   |       5.628  |                     0.3909 |
| pulse_shape_class     | nominal         | gradient_boosted_trees            | 1215 |  -0.935   |       2.896  |                     0.1358 |
| pulse_shape_class     | nominal         | mlp                               | 1215 |  -1.717   |       3.82   |                     0.2502 |
| pulse_shape_class     | nominal         | ridge                             | 1215 |  -0.7131  |       3.95   |                     0.2041 |
| pulse_shape_class     | nominal         | traditional_cfd_template_timewalk | 1215 |   0.2008  |       0.8654 |                     0      |
| pulse_shape_class     | nominal         | waveform_transformer              | 1215 |  -3.64    |       5.972  |                     0.423  |
| saturation_onset_bin  | linear          | 1d_cnn                            | 2664 |  -0.5208  |       8.951  |                     0.5739 |
| saturation_onset_bin  | linear          | edge_attention_cnn_new            | 2664 |  -1.467   |       7.025  |                     0.4771 |
| saturation_onset_bin  | linear          | gradient_boosted_trees            | 2664 |  -0.6975  |       3.701  |                     0.1911 |
| saturation_onset_bin  | linear          | mlp                               | 2664 |  -0.4211  |       4.555  |                     0.2703 |
| saturation_onset_bin  | linear          | ridge                             | 2664 |  -0.3966  |       4.331  |                     0.2481 |
| saturation_onset_bin  | linear          | traditional_cfd_template_timewalk | 2664 |   0.288   |       0.896  |                     0      |
| saturation_onset_bin  | linear          | waveform_transformer              | 2664 |  -3.437   |      24.5    |                     0.6914 |
| saturation_onset_bin  | near_saturation | 1d_cnn                            | 1005 |  -0.5076  |       7.148  |                     0.4527 |
| saturation_onset_bin  | near_saturation | edge_attention_cnn_new            | 1005 |  -2.625   |       6.043  |                     0.4567 |
| saturation_onset_bin  | near_saturation | gradient_boosted_trees            | 1005 |  -0.1972  |       3.346  |                     0.1692 |
| saturation_onset_bin  | near_saturation | mlp                               | 1005 |  -0.296   |       4.147  |                     0.2388 |
| saturation_onset_bin  | near_saturation | ridge                             | 1005 |   0.2248  |       4      |                     0.197  |
| saturation_onset_bin  | near_saturation | traditional_cfd_template_timewalk | 1005 |  -0.03221 |       0.8982 |                     0      |
| saturation_onset_bin  | near_saturation | waveform_transformer              | 1005 |  -3.371   |      10.68   |                     0.5731 |

## Pulse-Shape and Pretrigger Ablations

These ablations use the gradient-boosted-tree learner because it was the best
non-traditional ML method in the primary table.  They remove feature families
rather than individual correlated columns, exposing whether the learned timing
understanding is driven by pretrigger pedestal information or by tail/shape
features.

| ablation                       |   n_features |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   delta_sigma68_vs_full_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|-------------:|-------------:|--------------------:|---------------------:|---------------------------:|---------------------------:|
| drop_tail_pulse_shape_features |           24 |        3.592 |               2.955 |                4.278 |                   -0.03683 |                     0.1842 |
| full_gradient_boosted_trees    |           33 |        3.629 |               3.004 |                4.318 |                    0       |                     0.1815 |
| drop_pretrigger_features       |           27 |        4.127 |               3.678 |                4.734 |                    0.4984  |                     0.2328 |
| amplitude_cfd_only             |            5 |        4.266 |               3.812 |                4.934 |                    0.637   |                     0.2464 |

## Systematics and Caveats

This is a raw-ROOT, run-held-out timing benchmark, not a beamline truth
measurement.  The onset target is an internally reproducible CFD20 reference; it
does not claim an external picosecond truth label.  Pedestal drift, pile-up
separation, saturation onset, energy, and PID are represented by waveform
sideband proxies because the ticket asks for raw ROOT reproduction and the
available tree does not contain independent particle labels or electronics
saturation flags.  The bootstrap resamples held-out runs, so its interval covers
run-transfer scatter more directly than event-level counting uncertainty.  The
18-sample waveform and 10 ns digitizer spacing impose a hard interpolation floor
shared by every method.

Ticket-local wrapper runtime was `34.0 s`; base benchmark runtime was `33.9 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.

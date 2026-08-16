# S53a: Constant-Fraction Timing Versus Neural Shape Encoders Under Pedestal-Memory Drift

## Abstract

Ticket `2466` requested a run-held-out benchmark for sub-sample
pulse-onset timing under pedestal drift, pile-up, saturation, energy, and
PID-sideband stress.  This study reproduces the registered raw B-stack ROOT pulse
count, constructs an onset-residual benchmark directly from `h101/HRDv`, and
compares one strong traditional method with ridge, gradient-boosted trees, MLP,
1D-CNN, a causal waveform transformer, and a new gated edge-attention CNN.  The winner written to `result.json`
is **`traditional_cfd_template_timewalk`**, with held-out run-bootstrap sigma68
`1.039 ns [0.7069, 1.245]`.


## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-3 --project testbeam` command was
run exactly once for this worker.  It returned the known malformed
`null / # null / null` output and did not attach `worker:testbeam-laptop-3` to
an issue.  Direct queue inspection showed open testbeam tickets, so issue
`#2466` was manually moved from `factory:open` to `factory:claimed` and labeled
`worker:testbeam-laptop-3` without re-running the helper.

## S53a Interpretation Layer

The reusable raw-ROOT benchmark is specialized here to the S53a estimand:
whether data-driven shape encoders can improve sub-sample constant-fraction
timing when pedestal-memory state, rise shape, near-threshold amplitude, and
tail structure are shifted between runs.  The result is considered a physics
closure only if the held-out run-block uncertainty, calibration slope, and
shape-conditioned residuals improve together without a single pedestal or shape
slice carrying the apparent gain.

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
| heldout |   3816 |
| train   |  10793 |

Confidence intervals are percentile 95% intervals from
`360` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

| method                            | family           | description                                                                                                  |
|:----------------------------------|:-----------------|:-------------------------------------------------------------------------------------------------------------|
| traditional_cfd_template_timewalk | traditional      | CFD20/CFD50 template proxy plus monotone log-amplitude time-walk correction                                  |
| ridge                             | linear ML        | standardized ridge regression on amplitude, pedestal, CFD, tail, pile-up, saturation, and normalized samples |
| gradient_boosted_trees            | tree ML          | histogram gradient-boosted regression on the same engineered waveform features                               |
| mlp                               | neural tabular   | two-hidden-layer perceptron on engineered waveform and detector-state summaries                              |
| 1d_cnn                            | neural waveform  | compact 1D convolutional regressor over the 18 normalized ADC samples                                        |
| waveform_transformer              | neural waveform  | causal/ordered one-layer self-attention encoder over waveform samples with amplitude-weighted pooling        |
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
| traditional_cfd_template_timewalk | 3816 |    0.2473 |        1.039 |              0.7069 |                1.245 |   0.9694 |                     0      |                     0       |
| gradient_boosted_trees            | 3816 |   -1.077  |        3.603 |              2.927  |                4.45  |   5.927  |                     0.2264 |                     0.04665 |
| mlp                               | 3816 |   -1.03   |        4.06  |              3.606  |                4.921 |   6.028  |                     0.2521 |                     0.05739 |
| ridge                             | 3816 |   -0.7126 |        4.491 |              3.623  |                5.474 |   6.267  |                     0.2676 |                     0.05634 |
| edge_attention_cnn_new            | 3816 |   -0.4793 |        8.24  |              7.521  |                8.939 |  12.18   |                     0.5257 |                     0.2419  |
| waveform_transformer              | 3816 |    2.3    |        9.364 |              8.359  |               10.61  |  13.36   |                     0.5655 |                     0.3171  |
| 1d_cnn                            | 3816 |   -0.1115 |        9.895 |              9.215  |               10.71  |  14.4    |                     0.6137 |                     0.3184  |

The traditional method has sigma68 `1.039 ns`; the selected
winner `traditional_cfd_template_timewalk` has sigma68 `1.039 ns`.

## Paired Method Deltas

The following deltas are paired by held-out run-block bootstrap against the
traditional reference.  Positive `delta_sigma68_ns` means the method is wider
than the traditional comparator.

| method                 | reference_method                  |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |   delta_tail_fraction_abs_gt_5ns |   delta_tail_fraction_abs_gt_5ns_ci_low |   delta_tail_fraction_abs_gt_5ns_ci_high |
|:-----------------------|:----------------------------------|-------------------:|--------------------------:|---------------------------:|---------------------------------:|----------------------------------------:|-----------------------------------------:|
| gradient_boosted_trees | traditional_cfd_template_timewalk |              2.564 |                     1.858 |                      3.413 |                           0.2264 |                                  0.152  |                                   0.3045 |
| mlp                    | traditional_cfd_template_timewalk |              3.021 |                     2.561 |                      3.965 |                           0.2521 |                                  0.1762 |                                   0.3287 |
| ridge                  | traditional_cfd_template_timewalk |              3.452 |                     2.611 |                      4.453 |                           0.2676 |                                  0.1868 |                                   0.3431 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk |              7.201 |                     6.462 |                      8.02  |                           0.5257 |                                  0.4865 |                                   0.5628 |
| waveform_transformer   | traditional_cfd_template_timewalk |              8.325 |                     7.306 |                      9.617 |                           0.5655 |                                  0.5265 |                                   0.5993 |
| 1d_cnn                 | traditional_cfd_template_timewalk |              8.856 |                     8.22  |                      9.727 |                           0.6137 |                                  0.5996 |                                   0.6268 |

## Run Stability

| method                            |   run |   n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|------:|----:|----------:|-------------:|---------------------------:|
| 1d_cnn                            |    42 | 477 |  2.737    |      10.24   |                    0.6143  |
| 1d_cnn                            |    50 | 480 | -5.113    |      13.31   |                    0.6229  |
| 1d_cnn                            |    57 | 480 |  1.061    |      10.45   |                    0.6021  |
| 1d_cnn                            |    58 | 474 | -2.842    |      10.86   |                    0.6392  |
| 1d_cnn                            |    60 | 480 |  1.137    |       9.329  |                    0.5938  |
| 1d_cnn                            |    62 | 480 |  0.5163   |       8.92   |                    0.6271  |
| 1d_cnn                            |    64 | 480 |  1.762    |       8.707  |                    0.5792  |
| 1d_cnn                            |    65 | 465 |  1.174    |       9.296  |                    0.6323  |
| edge_attention_cnn_new            |    42 | 477 |  2.146    |       8.707  |                    0.5723  |
| edge_attention_cnn_new            |    50 | 480 | -5.142    |      12.92   |                    0.6     |
| edge_attention_cnn_new            |    57 | 480 |  0.8625   |       8.865  |                    0.5521  |
| edge_attention_cnn_new            |    58 | 474 | -3.689    |       8.263  |                    0.6097  |
| edge_attention_cnn_new            |    60 | 480 |  1.43     |       8.246  |                    0.5208  |
| edge_attention_cnn_new            |    62 | 480 |  0.5184   |       7.012  |                    0.45    |
| edge_attention_cnn_new            |    64 | 480 |  0.4964   |       7.135  |                    0.4562  |
| edge_attention_cnn_new            |    65 | 465 | -0.279    |       7.034  |                    0.443   |
| gradient_boosted_trees            |    42 | 477 |  1.504    |       3.947  |                    0.283   |
| gradient_boosted_trees            |    50 | 480 | -1.824    |      12.48   |                    0.3583  |
| gradient_boosted_trees            |    57 | 480 |  0.4588   |       2.913  |                    0.1271  |
| gradient_boosted_trees            |    58 | 474 | -4.344    |       2.612  |                    0.3797  |
| gradient_boosted_trees            |    60 | 480 | -0.9247   |       4.557  |                    0.2646  |
| gradient_boosted_trees            |    62 | 480 | -0.8338   |       2.187  |                    0.06458 |
| gradient_boosted_trees            |    64 | 480 | -1.238    |       3.364  |                    0.1896  |
| gradient_boosted_trees            |    65 | 465 | -2.633    |       2.668  |                    0.1441  |
| mlp                               |    42 | 477 |  1.65     |       5.082  |                    0.2788  |
| mlp                               |    50 | 480 | -2.866    |      12.63   |                    0.3917  |
| mlp                               |    57 | 480 |  0.6993   |       4.102  |                    0.2104  |
| mlp                               |    58 | 474 | -4.036    |       3.666  |                    0.4156  |
| mlp                               |    60 | 480 | -0.4753   |       5.389  |                    0.3187  |
| mlp                               |    62 | 480 | -0.4233   |       2.828  |                    0.08333 |
| mlp                               |    64 | 480 | -1.779    |       3.68   |                    0.1354  |
| mlp                               |    65 | 465 | -2.459    |       3.72   |                    0.1828  |
| ridge                             |    42 | 477 |  2.312    |       4.407  |                    0.2725  |
| ridge                             |    50 | 480 | -3.142    |      13.4    |                    0.4583  |
| ridge                             |    57 | 480 |  1.106    |       4.552  |                    0.2875  |
| ridge                             |    58 | 474 | -3.607    |       4.402  |                    0.384   |
| ridge                             |    60 | 480 |  0.004166 |       4.621  |                    0.3021  |
| ridge                             |    62 | 480 | -0.6323   |       3.141  |                    0.1292  |
| ridge                             |    64 | 480 | -1.057    |       3.011  |                    0.1125  |
| ridge                             |    65 | 465 | -1.317    |       3.731  |                    0.1935  |
| traditional_cfd_template_timewalk |    42 | 477 | -0.5354   |       1.276  |                    0       |
| traditional_cfd_template_timewalk |    50 | 480 | -0.2721   |       0.5728 |                    0       |
| traditional_cfd_template_timewalk |    57 | 480 | -1.187    |       0.8166 |                    0       |
| traditional_cfd_template_timewalk |    58 | 474 |  0.9147   |       0.4627 |                    0       |
| traditional_cfd_template_timewalk |    60 | 480 |  0.3697   |       1.232  |                    0       |
| traditional_cfd_template_timewalk |    62 | 480 | -0.2952   |       1.223  |                    0       |
| traditional_cfd_template_timewalk |    64 | 480 |  0.4041   |       0.5883 |                    0       |
| traditional_cfd_template_timewalk |    65 | 465 |  0.8559   |       0.5725 |                    0       |
| waveform_transformer              |    42 | 477 |  5.47     |       9.348  |                    0.6436  |
| waveform_transformer              |    50 | 480 |  0.2449   |      14.78   |                    0.6562  |
| waveform_transformer              |    57 | 480 |  3.903    |      10.42   |                    0.5687  |
| waveform_transformer              |    58 | 474 | -1.289    |      11.62   |                    0.5886  |
| waveform_transformer              |    60 | 480 |  1.814    |       8.414  |                    0.5083  |
| waveform_transformer              |    62 | 480 |  2.417    |       7.8    |                    0.5125  |
| waveform_transformer              |    64 | 480 |  2.002    |       7.219  |                    0.4938  |
| waveform_transformer              |    65 | 465 |  2.04     |       8.673  |                    0.5527  |

## Stress-Stratified Results

The requested stress axes are implemented as raw-waveform proxies:
pedestal drift is the absolute baseline displacement from the run/stave median;
pulse-shape class is the late-tail fraction; pile-up separation is the spacing
to a late secondary prominence; saturation onset is high amplitude or flat-top
occupancy; energy proxy is amplitude quartile; PID sideband is the duplicate
readout amplitude ratio sideband.

| stratum               | level           | method                            |    n |     bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------|:----------------|:----------------------------------|-----:|------------:|-------------:|---------------------------:|
| energy_bin            | q1_low          | 1d_cnn                            |  995 |   2.52      |      11.07   |                     0.6905 |
| energy_bin            | q1_low          | edge_attention_cnn_new            |  995 |  -0.5385    |       9.276  |                     0.5407 |
| energy_bin            | q1_low          | gradient_boosted_trees            |  995 |  -1.301     |       3.55   |                     0.2121 |
| energy_bin            | q1_low          | mlp                               |  995 |  -0.5806    |       3.709  |                     0.209  |
| energy_bin            | q1_low          | ridge                             |  995 |   0.4687    |       4.237  |                     0.2503 |
| energy_bin            | q1_low          | traditional_cfd_template_timewalk |  995 |  -0.1124    |       1.125  |                     0      |
| energy_bin            | q1_low          | waveform_transformer              |  995 |   4.949     |       7.572  |                     0.607  |
| energy_bin            | q2              | 1d_cnn                            | 1036 |   2.937     |       8.306  |                     0.5434 |
| energy_bin            | q2              | edge_attention_cnn_new            | 1036 |   0.7268    |       6.408  |                     0.4295 |
| energy_bin            | q2              | gradient_boosted_trees            | 1036 |  -0.8143    |       3.716  |                     0.2259 |
| energy_bin            | q2              | mlp                               | 1036 |  -1.336     |       4.275  |                     0.2654 |
| energy_bin            | q2              | ridge                             | 1036 |  -0.5208    |       4.49   |                     0.2616 |
| energy_bin            | q2              | traditional_cfd_template_timewalk | 1036 |   0.3424    |       0.8462 |                     0      |
| energy_bin            | q2              | waveform_transformer              | 1036 |   3.997     |       7.506  |                     0.5569 |
| energy_bin            | q3              | 1d_cnn                            |  982 |   0.1821    |       8.739  |                     0.5336 |
| energy_bin            | q3              | edge_attention_cnn_new            |  982 |   2.207     |       7.059  |                     0.4888 |
| energy_bin            | q3              | gradient_boosted_trees            |  982 |  -0.888     |       3.57   |                     0.2261 |
| energy_bin            | q3              | mlp                               |  982 |  -0.7673    |       4.387  |                     0.276  |
| energy_bin            | q3              | ridge                             |  982 |  -1.29      |       4.748  |                     0.3045 |
| energy_bin            | q3              | traditional_cfd_template_timewalk |  982 |   0.3534    |       1.011  |                     0      |
| energy_bin            | q3              | waveform_transformer              |  982 |  -0.6115    |       9.491  |                     0.5692 |
| energy_bin            | q4_high         | 1d_cnn                            |  803 |  -7.023     |       6.696  |                     0.7073 |
| energy_bin            | q4_high         | edge_attention_cnn_new            |  803 |  -6.348     |       6.532  |                     0.6762 |
| energy_bin            | q4_high         | gradient_boosted_trees            |  803 |  -1.415     |       3.615  |                     0.2453 |
| energy_bin            | q4_high         | mlp                               |  803 |  -1.481     |       4.066  |                     0.259  |
| energy_bin            | q4_high         | ridge                             |  803 |  -1.302     |       4.513  |                     0.2516 |
| energy_bin            | q4_high         | traditional_cfd_template_timewalk |  803 |   0.3313    |       1.272  |                     0      |
| energy_bin            | q4_high         | waveform_transformer              |  803 |  -2.363     |       8.216  |                     0.5205 |
| pedestal_drift_bin    | high            | 1d_cnn                            | 1220 |  -3.758     |      11.33   |                     0.6893 |
| pedestal_drift_bin    | high            | edge_attention_cnn_new            | 1220 |  -3.06      |      10.34   |                     0.6295 |
| pedestal_drift_bin    | high            | gradient_boosted_trees            | 1220 |  -1.075     |       4.184  |                     0.2541 |
| pedestal_drift_bin    | high            | mlp                               | 1220 |  -0.143     |       4.482  |                     0.2623 |
| pedestal_drift_bin    | high            | ridge                             | 1220 |  -0.4167    |       4.748  |                     0.2951 |
| pedestal_drift_bin    | high            | traditional_cfd_template_timewalk | 1220 |   0.1555    |       1.058  |                     0      |
| pedestal_drift_bin    | high            | waveform_transformer              | 1220 |   2.565     |       8.825  |                     0.541  |
| pedestal_drift_bin    | low             | 1d_cnn                            | 1252 |   1.196     |       9.098  |                     0.5671 |
| pedestal_drift_bin    | low             | edge_attention_cnn_new            | 1252 |  -0.01849   |       7.42   |                     0.4736 |
| pedestal_drift_bin    | low             | gradient_boosted_trees            | 1252 |  -1.11      |       3.552  |                     0.2268 |
| pedestal_drift_bin    | low             | mlp                               | 1252 |  -1.663     |       4.095  |                     0.2692 |
| pedestal_drift_bin    | low             | ridge                             | 1252 |  -0.9226    |       4.66   |                     0.2756 |
| pedestal_drift_bin    | low             | traditional_cfd_template_timewalk | 1252 |   0.2421    |       0.9888 |                     0      |
| pedestal_drift_bin    | low             | waveform_transformer              | 1252 |   2.349     |       9.666  |                     0.5958 |
| pedestal_drift_bin    | mid             | 1d_cnn                            | 1344 |   1.261     |       9.088  |                     0.5885 |
| pedestal_drift_bin    | mid             | edge_attention_cnn_new            | 1344 |   0.2835    |       7.156  |                     0.4799 |
| pedestal_drift_bin    | mid             | gradient_boosted_trees            | 1344 |  -1.061     |       3.344  |                     0.2009 |
| pedestal_drift_bin    | mid             | mlp                               | 1344 |  -1.498     |       3.741  |                     0.2269 |
| pedestal_drift_bin    | mid             | ridge                             | 1344 |  -0.7215    |       4.166  |                     0.2351 |
| pedestal_drift_bin    | mid             | traditional_cfd_template_timewalk | 1344 |   0.313     |       1.045  |                     0      |
| pedestal_drift_bin    | mid             | waveform_transformer              | 1344 |   1.896     |       9.511  |                     0.5595 |
| pid_sideband          | central         | 1d_cnn                            | 2640 |   1.866     |       9.167  |                     0.5894 |
| pid_sideband          | central         | edge_attention_cnn_new            | 2640 |   0.5789    |       7.446  |                     0.4852 |
| pid_sideband          | central         | gradient_boosted_trees            | 2640 |  -1.039     |       3.566  |                     0.2197 |
| pid_sideband          | central         | mlp                               | 2640 |  -1.244     |       3.966  |                     0.2466 |
| pid_sideband          | central         | ridge                             | 2640 |  -0.5425    |       4.441  |                     0.2591 |
| pid_sideband          | central         | traditional_cfd_template_timewalk | 2640 |   0.2501    |       1.013  |                     0      |
| pid_sideband          | central         | waveform_transformer              | 2640 |   2.847     |      10.03   |                     0.6121 |
| pid_sideband          | high_duplicate  | 1d_cnn                            |  592 |  -9.075     |       8.218  |                     0.7584 |
| pid_sideband          | high_duplicate  | edge_attention_cnn_new            |  592 |  -8.045     |       9.925  |                     0.7416 |
| pid_sideband          | high_duplicate  | gradient_boosted_trees            |  592 |  -1.263     |       4.331  |                     0.2618 |
| pid_sideband          | high_duplicate  | mlp                               |  592 |   0.381     |       4.607  |                     0.2872 |
| pid_sideband          | high_duplicate  | ridge                             |  592 |  -0.998     |       4.968  |                     0.326  |
| pid_sideband          | high_duplicate  | traditional_cfd_template_timewalk |  592 |   0.02153   |       1.099  |                     0      |
| pid_sideband          | high_duplicate  | waveform_transformer              |  592 |   2.349     |       7.083  |                     0.4443 |
| pid_sideband          | low_duplicate   | 1d_cnn                            |  584 |  -0.9356    |       8.248  |                     0.5771 |
| pid_sideband          | low_duplicate   | edge_attention_cnn_new            |  584 |  -0.3791    |       7.113  |                     0.4897 |
| pid_sideband          | low_duplicate   | gradient_boosted_trees            |  584 |  -1.061     |       3.443  |                     0.2209 |
| pid_sideband          | low_duplicate   | mlp                               |  584 |  -1.599     |       3.838  |                     0.2414 |
| pid_sideband          | low_duplicate   | ridge                             |  584 |  -1.05      |       4.156  |                     0.2466 |
| pid_sideband          | low_duplicate   | traditional_cfd_template_timewalk |  584 |   0.3884    |       1.106  |                     0      |
| pid_sideband          | low_duplicate   | waveform_transformer              |  584 |   7.22e-05  |       7.93   |                     0.4777 |
| pileup_separation_bin | close           | 1d_cnn                            | 1148 |  -1.391     |       7.838  |                     0.5305 |
| pileup_separation_bin | close           | edge_attention_cnn_new            | 1148 |  -1.999     |       7.292  |                     0.5253 |
| pileup_separation_bin | close           | gradient_boosted_trees            | 1148 |  -1.367     |       3.315  |                     0.2152 |
| pileup_separation_bin | close           | mlp                               | 1148 |  -1.615     |       3.946  |                     0.2526 |
| pileup_separation_bin | close           | ridge                             | 1148 |  -1.415     |       4.55   |                     0.2735 |
| pileup_separation_bin | close           | traditional_cfd_template_timewalk | 1148 |   0.2227    |       1.021  |                     0      |
| pileup_separation_bin | close           | waveform_transformer              | 1148 |   2.612     |       7.513  |                     0.5078 |
| pileup_separation_bin | late            | 1d_cnn                            |    1 | -29.55      |       0      |                     1      |
| pileup_separation_bin | late            | edge_attention_cnn_new            |    1 | -24.79      |       0      |                     1      |
| pileup_separation_bin | late            | gradient_boosted_trees            |    1 |  -2.313     |       0      |                     0      |
| pileup_separation_bin | late            | mlp                               |    1 |  -6.476     |       0      |                     1      |
| pileup_separation_bin | late            | ridge                             |    1 |   3.825     |       0      |                     0      |
| pileup_separation_bin | late            | traditional_cfd_template_timewalk |    1 |  -1.354     |       0      |                     0      |
| pileup_separation_bin | late            | waveform_transformer              |    1 | -17.76      |       0      |                     1      |
| pileup_separation_bin | mid             | 1d_cnn                            |  796 |  -4.936     |       8.41   |                     0.6193 |
| pileup_separation_bin | mid             | edge_attention_cnn_new            |  796 |  -3.621     |       8.973  |                     0.6043 |
| pileup_separation_bin | mid             | gradient_boosted_trees            |  796 |  -1.788     |       3.4    |                     0.2349 |
| pileup_separation_bin | mid             | mlp                               |  796 |  -1.504     |       4.369  |                     0.2864 |
| pileup_separation_bin | mid             | ridge                             |  796 |  -1.285     |       4.727  |                     0.3003 |
| pileup_separation_bin | mid             | traditional_cfd_template_timewalk |  796 |   0.3904    |       1.115  |                     0      |
| pileup_separation_bin | mid             | waveform_transformer              |  796 |   0.3378    |       6.101  |                     0.3857 |
| pileup_separation_bin | none            | 1d_cnn                            | 1871 |   3.077     |      11.32   |                     0.6622 |
| pileup_separation_bin | none            | edge_attention_cnn_new            | 1871 |   1.082     |       7.743  |                     0.4923 |
| pileup_separation_bin | none            | gradient_boosted_trees            | 1871 |  -0.5811    |       3.896  |                     0.2298 |
| pileup_separation_bin | none            | mlp                               | 1871 |  -0.5582    |       3.906  |                     0.2368 |
| pileup_separation_bin | none            | ridge                             | 1871 |  -0.0003588 |       4.159  |                     0.2501 |
| pileup_separation_bin | none            | traditional_cfd_template_timewalk | 1871 |   0.1905    |       1.02   |                     0      |
| pileup_separation_bin | none            | waveform_transformer              | 1871 |   2.998     |      13.26   |                     0.6772 |
| pulse_shape_class     | compact         | 1d_cnn                            | 1244 |  -0.7492    |      10.36   |                     0.635  |
| pulse_shape_class     | compact         | edge_attention_cnn_new            | 1244 |  -2.689     |       8.836  |                     0.5587 |
| pulse_shape_class     | compact         | gradient_boosted_trees            | 1244 |  -1.717     |       3.792  |                     0.2355 |
| pulse_shape_class     | compact         | mlp                               | 1244 |  -1.179     |       4.615  |                     0.2741 |
| pulse_shape_class     | compact         | ridge                             | 1244 |  -0.7788    |       5.017  |                     0.3223 |
| pulse_shape_class     | compact         | traditional_cfd_template_timewalk | 1244 |   0.1267    |       1.039  |                     0      |
| pulse_shape_class     | compact         | waveform_transformer              | 1244 |   4.975     |       6.236  |                     0.5788 |
| pulse_shape_class     | late_tail       | 1d_cnn                            | 1291 |  -1.834     |      14.36   |                     0.6545 |
| pulse_shape_class     | late_tail       | edge_attention_cnn_new            | 1291 |  -0.1761    |       9.932  |                     0.5569 |
| pulse_shape_class     | late_tail       | gradient_boosted_trees            | 1291 |  -0.1339    |       4.177  |                     0.2595 |
| pulse_shape_class     | late_tail       | mlp                               | 1291 |  -0.3207    |       3.94   |                     0.2556 |
| pulse_shape_class     | late_tail       | ridge                             | 1291 |  -0.3107    |       4.326  |                     0.2618 |
| pulse_shape_class     | late_tail       | traditional_cfd_template_timewalk | 1291 |   0.3291    |       0.8629 |                     0      |
| pulse_shape_class     | late_tail       | waveform_transformer              | 1291 |  -3.497     |      18.77   |                     0.7297 |
| pulse_shape_class     | nominal         | 1d_cnn                            | 1281 |   1.902     |       7.9    |                     0.5519 |
| pulse_shape_class     | nominal         | edge_attention_cnn_new            | 1281 |   0.5744    |       7.338  |                     0.4621 |
| pulse_shape_class     | nominal         | gradient_boosted_trees            | 1281 |  -1.234     |       3.108  |                     0.1842 |
| pulse_shape_class     | nominal         | mlp                               | 1281 |  -1.768     |       3.804  |                     0.2272 |
| pulse_shape_class     | nominal         | ridge                             | 1281 |  -0.9831    |       4.076  |                     0.2201 |
| pulse_shape_class     | nominal         | traditional_cfd_template_timewalk | 1281 |   0.2944    |       1.052  |                     0      |
| pulse_shape_class     | nominal         | waveform_transformer              | 1281 |   1.787     |       5.516  |                     0.3872 |
| saturation_onset_bin  | linear          | 1d_cnn                            | 2734 |   0.06795   |      10.32   |                     0.6211 |
| saturation_onset_bin  | linear          | edge_attention_cnn_new            | 2734 |  -0.2919    |       8.402  |                     0.5223 |
| saturation_onset_bin  | linear          | gradient_boosted_trees            | 2734 |  -1.127     |       3.623  |                     0.2242 |
| saturation_onset_bin  | linear          | mlp                               | 2734 |  -1.047     |       4.079  |                     0.252  |
| saturation_onset_bin  | linear          | ridge                             | 2734 |  -0.8341    |       4.54   |                     0.2798 |
| saturation_onset_bin  | linear          | traditional_cfd_template_timewalk | 2734 |   0.3163    |       1.024  |                     0      |
| saturation_onset_bin  | linear          | waveform_transformer              | 2734 |   1.874     |      10.07   |                     0.5823 |
| saturation_onset_bin  | near_saturation | 1d_cnn                            | 1082 |  -0.4821    |       9.086  |                     0.5952 |
| saturation_onset_bin  | near_saturation | edge_attention_cnn_new            | 1082 |  -1.12      |       7.642  |                     0.5342 |
| saturation_onset_bin  | near_saturation | gradient_boosted_trees            | 1082 |  -0.9678    |       3.568  |                     0.232  |
| saturation_onset_bin  | near_saturation | mlp                               | 1082 |  -0.9972    |       4.034  |                     0.2523 |
| saturation_onset_bin  | near_saturation | ridge                             | 1082 |  -0.3934    |       4.269  |                     0.2366 |
| saturation_onset_bin  | near_saturation | traditional_cfd_template_timewalk | 1082 |  -0.06032   |       1.048  |                     0      |
| saturation_onset_bin  | near_saturation | waveform_transformer              | 1082 |   3.014     |       7.382  |                     0.5231 |

## Pulse-Shape and Pretrigger Ablations

These ablations use the gradient-boosted-tree learner because it was the best
non-traditional ML method in the primary table.  They remove feature families
rather than individual correlated columns, exposing whether the learned timing
understanding is driven by pretrigger pedestal information or by tail/shape
features.

| ablation                       |   n_features |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   delta_sigma68_vs_full_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|-------------:|-------------:|--------------------:|---------------------:|---------------------------:|---------------------------:|
| full_gradient_boosted_trees    |           33 |        3.676 |               3.069 |                4.298 |                    0       |                     0.2306 |
| drop_tail_pulse_shape_features |           24 |        3.712 |               3.171 |                4.414 |                    0.03588 |                     0.2309 |
| drop_pretrigger_features       |           27 |        4.259 |               3.55  |                5.037 |                    0.5838  |                     0.2573 |
| amplitude_cfd_only             |            5 |        4.404 |               3.699 |                5.438 |                    0.7281  |                     0.2715 |

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


## Calibration Slope

Calibration slope is fitted on held-out runs by ordinary least squares,

`y_i = a_m + s_m \hat y_{m,i} + epsilon_i`,

with percentile intervals from the same run-block bootstrap used for the
primary sigma68.  Ideal calibration has `s_m = 1`; slopes near zero indicate
predictions that rank poorly on unseen runs, and very large slopes indicate an
under-dispersed predictor.

| method                            |    n |   calibration_slope |   calibration_slope_ci_low |   calibration_slope_ci_high |
|:----------------------------------|-----:|--------------------:|---------------------------:|----------------------------:|
| mlp                               | 3816 |             0.99375 |                   0.959012 |                     1.01851 |
| traditional_cfd_template_timewalk | 3816 |             1.0006  |                   0.999111 |                     1.00217 |
| ridge                             | 3816 |             1.00426 |                   0.971157 |                     1.0311  |
| gradient_boosted_trees            | 3816 |             1.00582 |                   0.976638 |                     1.03081 |
| edge_attention_cnn_new            | 3816 |             1.07757 |                   1.0253   |                     1.13689 |
| waveform_transformer              | 3816 |             1.09081 |                   1.01503  |                     1.15635 |
| 1d_cnn                            | 3816 |             1.10357 |                   1.03075  |                     1.18072 |

## Shape-Conditioned Residuals

The ticket asked for pulse-shape residual modes and rise-time stratification.
The table below reports the leading shape and rise-time slices; the full table
is in `shape_residuals.csv`.

| method                            | stratum                         | level                |    n |   shape_residual_bias_ns |   shape_residual_sigma68_ns |
|:----------------------------------|:--------------------------------|:---------------------|-----:|-------------------------:|----------------------------:|
| traditional_cfd_template_timewalk | pulse_shape_class               | compact              | 1244 |                0.12672   |                    1.03889  |
| gradient_boosted_trees            | pulse_shape_class               | compact              | 1244 |               -1.71686   |                    3.79216  |
| mlp                               | pulse_shape_class               | compact              | 1244 |               -1.1789    |                    4.61542  |
| ridge                             | pulse_shape_class               | compact              | 1244 |               -0.778756  |                    5.01656  |
| waveform_transformer              | pulse_shape_class               | compact              | 1244 |                4.97508   |                    6.23577  |
| edge_attention_cnn_new            | pulse_shape_class               | compact              | 1244 |               -2.68921   |                    8.83563  |
| 1d_cnn                            | pulse_shape_class               | compact              | 1244 |               -0.749185  |                   10.3583   |
| traditional_cfd_template_timewalk | pulse_shape_class               | late_tail            | 1291 |                0.329112  |                    0.862946 |
| mlp                               | pulse_shape_class               | late_tail            | 1291 |               -0.320733  |                    3.93955  |
| gradient_boosted_trees            | pulse_shape_class               | late_tail            | 1291 |               -0.133898  |                    4.17671  |
| ridge                             | pulse_shape_class               | late_tail            | 1291 |               -0.31066   |                    4.32556  |
| edge_attention_cnn_new            | pulse_shape_class               | late_tail            | 1291 |               -0.176146  |                    9.9318   |
| 1d_cnn                            | pulse_shape_class               | late_tail            | 1291 |               -1.83426   |                   14.3554   |
| waveform_transformer              | pulse_shape_class               | late_tail            | 1291 |               -3.49651   |                   18.7686   |
| traditional_cfd_template_timewalk | pulse_shape_class               | nominal              | 1281 |                0.294425  |                    1.05232  |
| gradient_boosted_trees            | pulse_shape_class               | nominal              | 1281 |               -1.23366   |                    3.10775  |
| mlp                               | pulse_shape_class               | nominal              | 1281 |               -1.76822   |                    3.80412  |
| ridge                             | pulse_shape_class               | nominal              | 1281 |               -0.98307   |                    4.07554  |
| waveform_transformer              | pulse_shape_class               | nominal              | 1281 |                1.78706   |                    5.51619  |
| edge_attention_cnn_new            | pulse_shape_class               | nominal              | 1281 |                0.57445   |                    7.33834  |
| 1d_cnn                            | pulse_shape_class               | nominal              | 1281 |                1.90212   |                    7.90023  |
| traditional_cfd_template_timewalk | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |               -0.0205052 |                    1.20483  |
| gradient_boosted_trees            | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |               -1.31062   |                    4.33463  |
| mlp                               | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |                0.602114  |                    4.82384  |
| ridge                             | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |               -1.01928   |                    5.36622  |
| waveform_transformer              | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |                2.59366   |                    7.72565  |
| 1d_cnn                            | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |               -7.94766   |                    9.77271  |
| edge_attention_cnn_new            | pulse_shape_class+rise_time_bin | compact+fast_rise    |  415 |               -6.2008    |                   12.3662   |
| traditional_cfd_template_timewalk | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |                0.242212  |                    1.01986  |
| gradient_boosted_trees            | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |               -1.22185   |                    4.26959  |
| mlp                               | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |               -1.1841    |                    5.13666  |
| ridge                             | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |               -2.11394   |                    5.32479  |
| waveform_transformer              | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |                4.35315   |                    6.09922  |
| 1d_cnn                            | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |                0.236442  |                    8.7117   |
| edge_attention_cnn_new            | pulse_shape_class+rise_time_bin | compact+nominal_rise |  271 |               -0.729527  |                    8.93303  |
| traditional_cfd_template_timewalk | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |                0.199942  |                    1.00533  |
| gradient_boosted_trees            | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |               -2.22125   |                    3.06934  |
| mlp                               | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |               -2.235     |                    3.57576  |
| ridge                             | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |               -0.0332391 |                    4.59625  |
| waveform_transformer              | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |                7.0749    |                    5.06692  |
| edge_attention_cnn_new            | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |               -1.06696   |                    7.26658  |
| 1d_cnn                            | pulse_shape_class+rise_time_bin | compact+slow_rise    |  558 |                3.35199   |                    8.00584  |

## S53a Systematics, Leakage Checks, and Caveats

The run-held-out split prevents direct run memorization, and no method receives
run number or event number as a feature.  The remaining leakage risk is indirect:
baseline, duplicate-readout amplitude ratio, late-tail fraction, and flat-top
occupancy are real detector-state summaries and can encode pedestal-memory
state.  The ablations therefore remove pretrigger and tail families separately;
the observed degradation after removing pretrigger samples shows that pedestal
state is informative, but the absence of neural improvement on held-out runs
argues against a robust transferable waveform representation in this sample.

Important caveats are that the target is an internal CFD20 residual rather than
an external clock truth, the event sample is downsampled per run and stave for
runtime, and the transformer is intentionally compact.  These choices make the
comparison conservative and reproducible, but they should not be read as a final
limit on larger neural encoders trained with external timing labels.

Ticket-local wrapper runtime was `42.4 s`; base benchmark runtime was `31.5 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.

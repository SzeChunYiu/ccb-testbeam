# S32a: Pulse-Onset Timing Under Pedestal Pile-Up Saturation Benchmark

## Abstract

Ticket `1783884181.2123.49437123` requested a run-held-out benchmark for sub-sample
pulse-onset timing under pedestal drift, pile-up, saturation, energy, and
PID-sideband stress.  This study reproduces the registered raw B-stack ROOT pulse
count, constructs an onset-residual benchmark directly from `h101/HRDv`, and
compares one strong traditional method with ridge, gradient-boosted trees, MLP,
1D-CNN, and a new gated edge-attention CNN.  The winner written to `result.json`
is **`traditional_cfd_template_timewalk`**, with held-out run-bootstrap sigma68
`0.8408 ns [0.564, 1.051]`.

## Raw ROOT Reproduction

Input files are `data/root/root/hrdb_run_*.root`.  For every event the
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
| heldout |   5196 |
| train   |  14451 |

Confidence intervals are percentile 95% intervals from
`400` held-out run-block resamples:

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
| traditional_cfd_template_timewalk | 5196 |    0.4043 |       0.8408 |               0.564 |                1.051 |   0.8279 |                     0      |                     0       |
| gradient_boosted_trees            | 5196 |   -0.5522 |       3.507  |               3.028 |                3.999 |   4.481  |                     0.1778 |                     0.04503 |
| mlp                               | 5196 |   -0.925  |       3.916  |               3.582 |                4.516 |   4.671  |                     0.2232 |                     0.05273 |
| ridge                             | 5196 |   -0.3075 |       4.162  |               3.697 |                4.903 |   4.856  |                     0.2433 |                     0.05466 |
| edge_attention_cnn_new            | 5196 |    2.049  |       5.451  |               4.899 |                6.319 |   6.564  |                     0.4234 |                     0.1255  |
| 1d_cnn                            | 5196 |   -1.911  |       5.817  |               5.261 |                6.863 |   7.234  |                     0.4315 |                     0.1353  |
| waveform_transformer              | 5196 |    1.989  |       7.509  |               7.159 |                7.895 |   7.929  |                     0.5085 |                     0.203   |

The traditional method has sigma68 `0.8408 ns`; the selected
winner `traditional_cfd_template_timewalk` has sigma68 `0.8408 ns`.

## Paired Method Deltas

The following deltas are paired by held-out run-block bootstrap against the
traditional reference.  Positive `delta_sigma68_ns` means the method is wider
than the traditional comparator.

| method                 | reference_method                  |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |   delta_tail_fraction_abs_gt_5ns |   delta_tail_fraction_abs_gt_5ns_ci_low |   delta_tail_fraction_abs_gt_5ns_ci_high |
|:-----------------------|:----------------------------------|-------------------:|--------------------------:|---------------------------:|---------------------------------:|----------------------------------------:|-----------------------------------------:|
| gradient_boosted_trees | traditional_cfd_template_timewalk |              2.666 |                     2.186 |                      3.22  |                           0.1778 |                                  0.1208 |                                   0.2413 |
| mlp                    | traditional_cfd_template_timewalk |              3.075 |                     2.701 |                      3.792 |                           0.2232 |                                  0.1775 |                                   0.2669 |
| ridge                  | traditional_cfd_template_timewalk |              3.321 |                     2.857 |                      4.12  |                           0.2433 |                                  0.1798 |                                   0.3124 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk |              4.61  |                     4.033 |                      5.527 |                           0.4234 |                                  0.3794 |                                   0.4761 |
| 1d_cnn                 | traditional_cfd_template_timewalk |              4.976 |                     4.408 |                      6.084 |                           0.4315 |                                  0.401  |                                   0.4674 |
| waveform_transformer   | traditional_cfd_template_timewalk |              6.668 |                     6.29  |                      7.127 |                           0.5085 |                                  0.4938 |                                   0.5241 |

## Run Stability

| method                            |   run |   n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|------:|----:|----------:|-------------:|---------------------------:|
| 1d_cnn                            |    42 | 627 |   1.933   |       7.247  |                    0.512   |
| 1d_cnn                            |    50 | 650 |  -3.598   |       8.56   |                    0.4923  |
| 1d_cnn                            |    57 | 640 |   0.9207  |       6.016  |                    0.4078  |
| 1d_cnn                            |    58 | 624 |  -3.718   |       5.901  |                    0.4535  |
| 1d_cnn                            |    60 | 680 |  -1.563   |       5.482  |                    0.4059  |
| 1d_cnn                            |    62 | 680 |  -2.691   |       4.65   |                    0.3632  |
| 1d_cnn                            |    64 | 680 |  -2.366   |       4.854  |                    0.3838  |
| 1d_cnn                            |    65 | 615 |  -3.206   |       5.053  |                    0.4439  |
| edge_attention_cnn_new            |    42 | 627 |   5.102   |       6.647  |                    0.5375  |
| edge_attention_cnn_new            |    50 | 650 |  -0.6892  |       8.174  |                    0.4338  |
| edge_attention_cnn_new            |    57 | 640 |   4.52    |       5.731  |                    0.4906  |
| edge_attention_cnn_new            |    58 | 624 |   0.5113  |       5.888  |                    0.4327  |
| edge_attention_cnn_new            |    60 | 680 |   2.994   |       5.237  |                    0.4721  |
| edge_attention_cnn_new            |    62 | 680 |   1.788   |       4.543  |                    0.3338  |
| edge_attention_cnn_new            |    64 | 680 |   2.278   |       4.313  |                    0.3853  |
| edge_attention_cnn_new            |    65 | 615 |   1.178   |       4.581  |                    0.3041  |
| gradient_boosted_trees            |    42 | 627 |   1.586   |       4.292  |                    0.2967  |
| gradient_boosted_trees            |    50 | 650 |  -0.59    |       7.321  |                    0.2754  |
| gradient_boosted_trees            |    57 | 640 |   0.3991  |       3.395  |                    0.2031  |
| gradient_boosted_trees            |    58 | 624 |  -2.987   |       3.016  |                    0.2628  |
| gradient_boosted_trees            |    60 | 680 |  -0.3382  |       3.818  |                    0.1574  |
| gradient_boosted_trees            |    62 | 680 |  -1.189   |       2.824  |                    0.07059 |
| gradient_boosted_trees            |    64 | 680 |  -0.7236  |       3.423  |                    0.075   |
| gradient_boosted_trees            |    65 | 615 |  -1.736   |       2.475  |                    0.09593 |
| mlp                               |    42 | 627 |   1.402   |       5.108  |                    0.303   |
| mlp                               |    50 | 650 |  -1.14    |       6.708  |                    0.2846  |
| mlp                               |    57 | 640 |   0.5645  |       4.254  |                    0.25    |
| mlp                               |    58 | 624 |  -2.662   |       4.015  |                    0.2853  |
| mlp                               |    60 | 680 |  -0.6556  |       4.525  |                    0.2412  |
| mlp                               |    62 | 680 |  -1.548   |       3.751  |                    0.125   |
| mlp                               |    64 | 680 |  -1.512   |       3.994  |                    0.15    |
| mlp                               |    65 | 615 |  -2.258   |       3.157  |                    0.1561  |
| ridge                             |    42 | 627 |   2.464   |       5.356  |                    0.3828  |
| ridge                             |    50 | 650 |  -1.448   |       7.503  |                    0.3892  |
| ridge                             |    57 | 640 |   1.686   |       4.463  |                    0.2625  |
| ridge                             |    58 | 624 |  -1.894   |       4.085  |                    0.274   |
| ridge                             |    60 | 680 |  -0.03434 |       4.13   |                    0.2235  |
| ridge                             |    62 | 680 |  -1.054   |       3.409  |                    0.1368  |
| ridge                             |    64 | 680 |  -0.3779  |       3.666  |                    0.1441  |
| ridge                             |    65 | 615 |  -1.108   |       3.25   |                    0.1447  |
| traditional_cfd_template_timewalk |    42 | 627 |  -0.5722  |       0.7127 |                    0       |
| traditional_cfd_template_timewalk |    50 | 650 |   0.6047  |       1.145  |                    0       |
| traditional_cfd_template_timewalk |    57 | 640 |  -0.2942  |       0.9029 |                    0       |
| traditional_cfd_template_timewalk |    58 | 624 |   0.6244  |       0.695  |                    0       |
| traditional_cfd_template_timewalk |    60 | 680 |   0.2065  |       0.7301 |                    0       |
| traditional_cfd_template_timewalk |    62 | 680 |   0.8762  |       0.4524 |                    0       |
| traditional_cfd_template_timewalk |    64 | 680 |   0.5841  |       0.3915 |                    0       |
| traditional_cfd_template_timewalk |    65 | 615 |   0.8913  |       0.3925 |                    0       |
| waveform_transformer              |    42 | 627 |   3.693   |       7.619  |                    0.488   |
| waveform_transformer              |    50 | 650 |  -0.4349  |       8.919  |                    0.4954  |
| waveform_transformer              |    57 | 640 |   3.201   |       7.452  |                    0.4781  |
| waveform_transformer              |    58 | 624 |  -0.8957  |       7.92   |                    0.5192  |
| waveform_transformer              |    60 | 680 |   3.171   |       7.96   |                    0.5529  |
| waveform_transformer              |    62 | 680 |   1.95    |       7.234  |                    0.5088  |
| waveform_transformer              |    64 | 680 |   3.163   |       6.818  |                    0.5     |
| waveform_transformer              |    65 | 615 |   1.879   |       7.459  |                    0.5236  |

## Stress-Stratified Results

The requested stress axes are implemented as raw-waveform proxies:
pedestal drift is the absolute baseline displacement from the run/stave median;
pulse-shape class is the late-tail fraction; pile-up separation is the spacing
to a late secondary prominence; saturation onset is high amplitude or flat-top
occupancy; energy proxy is amplitude quartile; PID sideband is the duplicate
readout amplitude ratio sideband.

| stratum               | level           | method                            |    n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------|:----------------|:----------------------------------|-----:|----------:|-------------:|---------------------------:|
| energy_bin            | q1_low          | 1d_cnn                            | 1360 |  -4.243   |       6.384  |                     0.5588 |
| energy_bin            | q1_low          | edge_attention_cnn_new            | 1360 |   1.767   |       6.055  |                     0.4441 |
| energy_bin            | q1_low          | gradient_boosted_trees            | 1360 |  -0.7971  |       3.544  |                     0.1647 |
| energy_bin            | q1_low          | mlp                               | 1360 |  -1.153   |       3.697  |                     0.2029 |
| energy_bin            | q1_low          | ridge                             | 1360 |   0.5072  |       4.064  |                     0.2272 |
| energy_bin            | q1_low          | traditional_cfd_template_timewalk | 1360 |   0.1779  |       0.9379 |                     0      |
| energy_bin            | q1_low          | waveform_transformer              | 1360 |   3.507   |       7.849  |                     0.5537 |
| energy_bin            | q2              | 1d_cnn                            | 1421 |  -2.352   |       5.112  |                     0.4145 |
| energy_bin            | q2              | edge_attention_cnn_new            | 1421 |   2.406   |       4.88   |                     0.38   |
| energy_bin            | q2              | gradient_boosted_trees            | 1421 |  -0.4264  |       3.566  |                     0.1914 |
| energy_bin            | q2              | mlp                               | 1421 |  -0.9645  |       4.288  |                     0.2456 |
| energy_bin            | q2              | ridge                             | 1421 |  -0.1368  |       4.128  |                     0.2555 |
| energy_bin            | q2              | traditional_cfd_template_timewalk | 1421 |   0.6134  |       0.7005 |                     0      |
| energy_bin            | q2              | waveform_transformer              | 1421 |   4.524   |       7.076  |                     0.5764 |
| energy_bin            | q3              | 1d_cnn                            | 1359 |   0.1207  |       4.927  |                     0.3046 |
| energy_bin            | q3              | edge_attention_cnn_new            | 1359 |   3.377   |       4.702  |                     0.457  |
| energy_bin            | q3              | gradient_boosted_trees            | 1359 |  -0.486   |       3.495  |                     0.1744 |
| energy_bin            | q3              | mlp                               | 1359 |  -0.7681  |       4.105  |                     0.2163 |
| energy_bin            | q3              | ridge                             | 1359 |  -0.8098  |       4.21   |                     0.2561 |
| energy_bin            | q3              | traditional_cfd_template_timewalk | 1359 |   0.5979  |       0.7912 |                     0      |
| energy_bin            | q3              | waveform_transformer              | 1359 |   1.788   |       7.324  |                     0.4761 |
| energy_bin            | q4_high         | 1d_cnn                            | 1056 |  -2.139   |       5.812  |                     0.4536 |
| energy_bin            | q4_high         | edge_attention_cnn_new            | 1056 |  -0.2505  |       6.084  |                     0.4119 |
| energy_bin            | q4_high         | gradient_boosted_trees            | 1056 |  -0.4803  |       3.184  |                     0.1809 |
| energy_bin            | q4_high         | mlp                               | 1056 |  -0.6846  |       3.671  |                     0.2282 |
| energy_bin            | q4_high         | ridge                             | 1056 |  -0.9228  |       4.059  |                     0.2311 |
| energy_bin            | q4_high         | traditional_cfd_template_timewalk | 1056 |   0.377   |       1.029  |                     0      |
| energy_bin            | q4_high         | waveform_transformer              | 1056 |  -2.155   |       5.456  |                     0.4006 |
| pedestal_drift_bin    | high            | 1d_cnn                            | 1672 |  -2.337   |       7.615  |                     0.4976 |
| pedestal_drift_bin    | high            | edge_attention_cnn_new            | 1672 |   1.988   |       6.832  |                     0.4952 |
| pedestal_drift_bin    | high            | gradient_boosted_trees            | 1672 |  -0.3869  |       4.128  |                     0.2297 |
| pedestal_drift_bin    | high            | mlp                               | 1672 |  -0.5378  |       4.303  |                     0.253  |
| pedestal_drift_bin    | high            | ridge                             | 1672 |  -0.21    |       4.484  |                     0.2745 |
| pedestal_drift_bin    | high            | traditional_cfd_template_timewalk | 1672 |   0.3407  |       0.868  |                     0      |
| pedestal_drift_bin    | high            | waveform_transformer              | 1672 |  -0.3858  |       6.985  |                     0.4892 |
| pedestal_drift_bin    | low             | 1d_cnn                            | 1695 |  -1.85    |       5.396  |                     0.3959 |
| pedestal_drift_bin    | low             | edge_attention_cnn_new            | 1695 |   1.934   |       4.953  |                     0.3788 |
| pedestal_drift_bin    | low             | gradient_boosted_trees            | 1695 |  -0.614   |       3.226  |                     0.1528 |
| pedestal_drift_bin    | low             | mlp                               | 1695 |  -1.066   |       3.663  |                     0.2    |
| pedestal_drift_bin    | low             | ridge                             | 1695 |  -0.3682  |       4.157  |                     0.2336 |
| pedestal_drift_bin    | low             | traditional_cfd_template_timewalk | 1695 |   0.4006  |       0.8435 |                     0      |
| pedestal_drift_bin    | low             | waveform_transformer              | 1695 |   2.848   |       7.352  |                     0.5156 |
| pedestal_drift_bin    | mid             | 1d_cnn                            | 1829 |  -1.741   |       5.242  |                     0.404  |
| pedestal_drift_bin    | mid             | edge_attention_cnn_new            | 1829 |   2.15    |       4.953  |                     0.3991 |
| pedestal_drift_bin    | mid             | gradient_boosted_trees            | 1829 |  -0.5921  |       3.29   |                     0.1536 |
| pedestal_drift_bin    | mid             | mlp                               | 1829 |  -1.074   |       3.826  |                     0.2176 |
| pedestal_drift_bin    | mid             | ridge                             | 1829 |  -0.337   |       4.012  |                     0.2236 |
| pedestal_drift_bin    | mid             | traditional_cfd_template_timewalk | 1829 |   0.4921  |       0.816  |                     0      |
| pedestal_drift_bin    | mid             | waveform_transformer              | 1829 |   3.051   |       7.497  |                     0.5194 |
| pid_sideband          | central         | 1d_cnn                            | 3581 |  -1.687   |       5.383  |                     0.3999 |
| pid_sideband          | central         | edge_attention_cnn_new            | 3581 |   2.153   |       4.891  |                     0.3882 |
| pid_sideband          | central         | gradient_boosted_trees            | 3581 |  -0.5065  |       3.226  |                     0.1656 |
| pid_sideband          | central         | mlp                               | 3581 |  -0.7945  |       3.729  |                     0.2058 |
| pid_sideband          | central         | ridge                             | 3581 |  -0.2453  |       4.08   |                     0.2368 |
| pid_sideband          | central         | traditional_cfd_template_timewalk | 3581 |   0.3726  |       0.8414 |                     0      |
| pid_sideband          | central         | waveform_transformer              | 3581 |   3.172   |       7.531  |                     0.5314 |
| pid_sideband          | high_duplicate  | 1d_cnn                            |  834 |  -3.805   |       9.649  |                     0.6175 |
| pid_sideband          | high_duplicate  | edge_attention_cnn_new            |  834 |   1.509   |       8.051  |                     0.5695 |
| pid_sideband          | high_duplicate  | gradient_boosted_trees            |  834 |  -0.7263  |       4.199  |                     0.2374 |
| pid_sideband          | high_duplicate  | mlp                               |  834 |  -1.344   |       4.543  |                     0.265  |
| pid_sideband          | high_duplicate  | ridge                             |  834 |  -0.4073  |       4.74   |                     0.2938 |
| pid_sideband          | high_duplicate  | traditional_cfd_template_timewalk |  834 |   0.3316  |       0.8353 |                     0      |
| pid_sideband          | high_duplicate  | waveform_transformer              |  834 |  -3.134   |       6.065  |                     0.4376 |
| pid_sideband          | low_duplicate   | 1d_cnn                            |  781 |  -2.118   |       5.407  |                     0.3777 |
| pid_sideband          | low_duplicate   | edge_attention_cnn_new            |  781 |   1.783   |       5.478  |                     0.4289 |
| pid_sideband          | low_duplicate   | gradient_boosted_trees            |  781 |  -0.6744  |       3.518  |                     0.1703 |
| pid_sideband          | low_duplicate   | mlp                               |  781 |  -1.297   |       4.182  |                     0.2586 |
| pid_sideband          | low_duplicate   | ridge                             |  781 |  -0.5702  |       3.975  |                     0.219  |
| pid_sideband          | low_duplicate   | traditional_cfd_template_timewalk |  781 |   0.6527  |       0.8175 |                     0      |
| pid_sideband          | low_duplicate   | waveform_transformer              |  781 |   1.919   |       7.392  |                     0.4789 |
| pileup_separation_bin | close           | 1d_cnn                            | 1605 |  -2.636   |       5.473  |                     0.4224 |
| pileup_separation_bin | close           | edge_attention_cnn_new            | 1605 |   0.7831  |       5.689  |                     0.3969 |
| pileup_separation_bin | close           | gradient_boosted_trees            | 1605 |  -0.8525  |       3.228  |                     0.157  |
| pileup_separation_bin | close           | mlp                               | 1605 |  -1.425   |       4.02   |                     0.2312 |
| pileup_separation_bin | close           | ridge                             | 1605 |  -1.224   |       4.171  |                     0.2467 |
| pileup_separation_bin | close           | traditional_cfd_template_timewalk | 1605 |   0.4379  |       0.8964 |                     0      |
| pileup_separation_bin | close           | waveform_transformer              | 1605 |   1.892   |       6.891  |                     0.4411 |
| pileup_separation_bin | late            | 1d_cnn                            |    3 |  -4.225   |       5.785  |                     0.3333 |
| pileup_separation_bin | late            | edge_attention_cnn_new            |    3 | -12.35    |       6.306  |                     0.6667 |
| pileup_separation_bin | late            | gradient_boosted_trees            |    3 |   4.017   |       3.446  |                     0.3333 |
| pileup_separation_bin | late            | mlp                               |    3 |   1.847   |       5.667  |                     0.6667 |
| pileup_separation_bin | late            | ridge                             |    3 |   4.56    |       2.291  |                     0.3333 |
| pileup_separation_bin | late            | traditional_cfd_template_timewalk |    3 |   1.077   |       0.336  |                     0      |
| pileup_separation_bin | late            | waveform_transformer              |    3 | -14.09    |       7.986  |                     0.6667 |
| pileup_separation_bin | mid             | 1d_cnn                            | 1113 |  -0.2245  |       6.474  |                     0.4061 |
| pileup_separation_bin | mid             | edge_attention_cnn_new            | 1113 |   2.442   |       5.553  |                     0.4834 |
| pileup_separation_bin | mid             | gradient_boosted_trees            | 1113 |  -1.268   |       3.381  |                     0.1635 |
| pileup_separation_bin | mid             | mlp                               | 1113 |  -1.564   |       3.948  |                     0.212  |
| pileup_separation_bin | mid             | ridge                             | 1113 |  -0.8937  |       4.353  |                     0.2624 |
| pileup_separation_bin | mid             | traditional_cfd_template_timewalk | 1113 |   0.5548  |       0.8409 |                     0      |
| pileup_separation_bin | mid             | waveform_transformer              | 1113 |  -1.333   |       5.602  |                     0.4007 |
| pileup_separation_bin | none            | 1d_cnn                            | 2475 |  -2.206   |       5.665  |                     0.4489 |
| pileup_separation_bin | none            | edge_attention_cnn_new            | 2475 |   2.657   |       5.03   |                     0.4133 |
| pileup_separation_bin | none            | gradient_boosted_trees            | 2475 |  -0.1552  |       3.524  |                     0.1976 |
| pileup_separation_bin | none            | mlp                               | 2475 |  -0.5078  |       3.683  |                     0.2226 |
| pileup_separation_bin | none            | ridge                             | 2475 |   0.2306  |       3.691  |                     0.2323 |
| pileup_separation_bin | none            | traditional_cfd_template_timewalk | 2475 |   0.357   |       0.8015 |                     0      |
| pileup_separation_bin | none            | waveform_transformer              | 2475 |   3.891   |       8.279  |                     0.6004 |
| pulse_shape_class     | compact         | 1d_cnn                            | 1766 |  -2.514   |       6.696  |                     0.5221 |
| pulse_shape_class     | compact         | edge_attention_cnn_new            | 1766 |   1.659   |       6.412  |                     0.4683 |
| pulse_shape_class     | compact         | gradient_boosted_trees            | 1766 |  -1.307   |       3.77   |                     0.1767 |
| pulse_shape_class     | compact         | mlp                               | 1766 |  -1.988   |       4.152  |                     0.2293 |
| pulse_shape_class     | compact         | ridge                             | 1766 |  -0.07527 |       4.639  |                     0.2837 |
| pulse_shape_class     | compact         | traditional_cfd_template_timewalk | 1766 |   0.3407  |       0.8339 |                     0      |
| pulse_shape_class     | compact         | waveform_transformer              | 1766 |   2.359   |       7.592  |                     0.5096 |
| pulse_shape_class     | late_tail       | 1d_cnn                            | 1724 |  -1.689   |       6.251  |                     0.4304 |
| pulse_shape_class     | late_tail       | edge_attention_cnn_new            | 1724 |   2.997   |       5.768  |                     0.4368 |
| pulse_shape_class     | late_tail       | gradient_boosted_trees            | 1724 |   0.092   |       3.672  |                     0.2227 |
| pulse_shape_class     | late_tail       | mlp                               | 1724 |  -0.1684  |       3.817  |                     0.2512 |
| pulse_shape_class     | late_tail       | ridge                             | 1724 |  -0.2086  |       3.966  |                     0.2535 |
| pulse_shape_class     | late_tail       | traditional_cfd_template_timewalk | 1724 |   0.5078  |       0.8069 |                     0      |
| pulse_shape_class     | late_tail       | waveform_transformer              | 1724 |  -0.6969  |       7.502  |                     0.5133 |
| pulse_shape_class     | nominal         | 1d_cnn                            | 1706 |  -1.777   |       4.678  |                     0.3388 |
| pulse_shape_class     | nominal         | edge_attention_cnn_new            | 1706 |   1.381   |       4.334  |                     0.3634 |
| pulse_shape_class     | nominal         | gradient_boosted_trees            | 1706 |  -0.6194  |       2.837  |                     0.1336 |
| pulse_shape_class     | nominal         | mlp                               | 1706 |  -1.185   |       3.511  |                     0.1887 |
| pulse_shape_class     | nominal         | ridge                             | 1706 |  -0.5411  |       3.764  |                     0.1911 |
| pulse_shape_class     | nominal         | traditional_cfd_template_timewalk | 1706 |   0.4056  |       0.9133 |                     0      |
| pulse_shape_class     | nominal         | waveform_transformer              | 1706 |   3.697   |       6.116  |                     0.5023 |
| saturation_onset_bin  | linear          | 1d_cnn                            | 3812 |  -1.825   |       6.116  |                     0.4386 |
| saturation_onset_bin  | linear          | edge_attention_cnn_new            | 3812 |   2.349   |       5.622  |                     0.4433 |
| saturation_onset_bin  | linear          | gradient_boosted_trees            | 3812 |  -0.6056  |       3.614  |                     0.1792 |
| saturation_onset_bin  | linear          | mlp                               | 3812 |  -1.032   |       3.985  |                     0.2248 |
| saturation_onset_bin  | linear          | ridge                             | 3812 |  -0.3703  |       4.323  |                     0.2542 |
| saturation_onset_bin  | linear          | traditional_cfd_template_timewalk | 3812 |   0.4607  |       0.8148 |                     0      |
| saturation_onset_bin  | linear          | waveform_transformer              | 3812 |   1.939   |       7.928  |                     0.5333 |
| saturation_onset_bin  | near_saturation | 1d_cnn                            | 1384 |  -2.217   |       5.327  |                     0.4118 |
| saturation_onset_bin  | near_saturation | edge_attention_cnn_new            | 1384 |   1.32    |       5.006  |                     0.3685 |
| saturation_onset_bin  | near_saturation | gradient_boosted_trees            | 1384 |  -0.3861  |       3.185  |                     0.1741 |
| saturation_onset_bin  | near_saturation | mlp                               | 1384 |  -0.6446  |       3.663  |                     0.2189 |
| saturation_onset_bin  | near_saturation | ridge                             | 1384 |  -0.1822  |       3.788  |                     0.2132 |
| saturation_onset_bin  | near_saturation | traditional_cfd_template_timewalk | 1384 |   0.2951  |       0.9394 |                     0      |
| saturation_onset_bin  | near_saturation | waveform_transformer              | 1384 |   2.236   |       6.117  |                     0.44   |

## Pulse-Shape and Pretrigger Ablations

These ablations use the gradient-boosted-tree learner because it was the best
non-traditional ML method in the primary table.  They remove feature families
rather than individual correlated columns, exposing whether the learned timing
understanding is driven by pretrigger pedestal information or by tail/shape
features.

| ablation                       |   n_features |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   delta_sigma68_vs_full_ns |   tail_fraction_abs_gt_5ns |
|:-------------------------------|-------------:|-------------:|--------------------:|---------------------:|---------------------------:|---------------------------:|
| full_gradient_boosted_trees    |           33 |        3.454 |               3.076 |                3.969 |                    0       |                     0.1776 |
| drop_tail_pulse_shape_features |           24 |        3.533 |               3.055 |                4.035 |                    0.07932 |                     0.1778 |
| drop_pretrigger_features       |           27 |        3.934 |               3.524 |                4.719 |                    0.4808  |                     0.2165 |
| amplitude_cfd_only             |            5 |        4.095 |               3.609 |                4.67  |                    0.6415  |                     0.2338 |

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

Runtime was `36.3 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.

# S33b: saturation energy recovery architecture bakeoff

## Abstract

Ticket `1783888239.810.6d016e26` asks whether raw B-stack HRD waveforms support a stronger
architecture for saturated pulse energy and timing recovery than a traditional
saturation-knee/template correction.  The worker was `testbeam-laptop-4`.  Before fitting
any model, the raw ROOT selected-pulse anchor was reproduced exactly:
`640737` selected B-stave pulses versus the reference
`640737`, with delta `0`.

The winner is `gradient_boosted_trees` by the predeclared composite ordering

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`,

where `sigma_E` is held-out fractional energy sigma68, `sigma_t` is constituent
timing sigma68 in ns, and the final two terms penalize missed injected pile-up and
false splitting of clean controls.  `gradient_boosted_trees` obtains `sigma_E =
0.06838` with 95% run-block bootstrap CI
[0.06387,
0.07991] and timing sigma68
`7.691` ns.

## Raw ROOT reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` object was
reshaped to `(event, channel, sample)` with 18 samples per channel.  B2/B4/B6/B8
were pedestal-subtracted with `b_c = median(x_c[0:4])`; selected pulses satisfy
`max_t (x_c(t)-b_c) > 1000 ADC`.  This reproduces the existing analysis count and
guards against benchmarking on a derived cache with incompatible semantics.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | True |

## Train-only pulse templates

Clean single-pulse templates were estimated only from train runs
`[50, 51, 52, 53, 54, 55, 56, 57]`.  Candidate clean pulses required amplitude
1500--12000 ADC and peak sample 4--12.  For pulse `i` on stave `s`, the normalized
waveform is shifted to a common CFD20 reference and the template is

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| ----- | -------------- | --------------------- | -------------------- | ------------- |
| B2    | 736            | 2.576                 | 5                    | 9.187         |
| B4    | 728            | 2.995                 | 6                    | 10.67         |
| B6    | 695            | 3.749                 | 6                    | 9.715         |
| B8    | 474            | 4.236                 | 8                    | 9.248         |

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

| method                              | winner_score | energy_fractional_bias | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | time_bias_ns | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate |
| ----------------------------------- | ------------ | ---------------------- | ------------------------- | -------------------------------- | --------------------------------- | ------------ | --------------- | ---------------------- | ----------------------- | ---------------- | ---------------- |
| gradient_boosted_trees              | 0.1745       | -0.01116               | 0.06838                   | 0.06387                          | 0.07991                           | 0.2727       | 7.691           | 6.803                  | 8.224                   | 0.3861           | 0.1972           |
| template_residual_boosted_stack_new | 0.1783       | -0.009305              | 0.0706                    | 0.06318                          | 0.08029                           | 0.3403       | 7.863           | 6.704                  | 8.334                   | 0.3861           | 0.1944           |
| ridge                               | 0.1808       | -0.005517              | 0.06523                   | 0.05519                          | 0.07624                           | -0.4046      | 8.86            | 7.984                  | 9.638                   | 0.3417           | 0.1972           |
| two_pulse_template_cfd_baseline     | 0.2216       | -0.001191              | 0.08705                   | 0.07564                          | 0.1005                            | 0.4604       | 9.561           | 8.018                  | 12.09                   | 0.6111           | 0.1667           |
| 1d_cnn                              | 0.2232       | -0.003259              | 0.07562                   | 0.06528                          | 0.08343                           | 0.8563       | 11.63           | 10.44                  | 12.52                   | 0.4222           | 0.2028           |
| mlp                                 | 0.2831       | -0.003789              | 0.1174                    | 0.1004                           | 0.1421                            | 0.2475       | 13.53           | 11.92                  | 15.18                   | 0.3944           | 0.2139           |
| tiny_sequence_transformer           | 0.3          | -0.03159               | 0.1106                    | 0.09609                          | 0.1282                            | -10.4        | 15.51           | 13.98                  | 18.96                   | 0.5028           | 0.1833           |

Relative to the traditional baseline, `gradient_boosted_trees` changes fractional energy sigma68
by `-0.01867`
and timing sigma68 by `-1.87` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              | heldout_run | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| ----------------------------------- | ----------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- | ---------------- |
| 1d_cnn                              | 58          | -0.01021               | 0.06084                   | -1.855       | 10.87           | 0.4167           | 0.2222           |
| 1d_cnn                              | 60          | 0.0277                 | 0.06228                   | 2.491        | 8.704           | 0.4028           | 0.1806           |
| 1d_cnn                              | 62          | 0.01607                | 0.0763                    | -0.5991      | 11.11           | 0.4722           | 0.2361           |
| 1d_cnn                              | 64          | -0.006124              | 0.07223                   | 1.645        | 12.5            | 0.4583           | 0.1389           |
| 1d_cnn                              | 65          | -0.03158               | 0.06137                   | -0.1827      | 12.67           | 0.3611           | 0.2361           |
| gradient_boosted_trees              | 58          | -0.0207                | 0.05899                   | -2.025       | 8.788           | 0.3472           | 0.1806           |
| gradient_boosted_trees              | 60          | 0.01045                | 0.06193                   | 1.737        | 6.259           | 0.3611           | 0.2083           |
| gradient_boosted_trees              | 62          | 0.01249                | 0.07595                   | 0.6719       | 6.884           | 0.4583           | 0.2222           |
| gradient_boosted_trees              | 64          | -0.02467               | 0.06774                   | 0.422        | 7.763           | 0.4722           | 0.1667           |
| gradient_boosted_trees              | 65          | -0.02205               | 0.0767                    | 0.005546     | 6.335           | 0.2917           | 0.2083           |
| mlp                                 | 58          | -0.04152               | 0.1303                    | -3.528       | 10.79           | 0.3889           | 0.2222           |
| mlp                                 | 60          | 0.01116                | 0.1483                    | 4            | 11.49           | 0.375            | 0.25             |
| mlp                                 | 62          | 0.03472                | 0.09806                   | 1.578        | 11.53           | 0.4444           | 0.25             |
| mlp                                 | 64          | 0.002962               | 0.1274                    | -0.7451      | 16.98           | 0.4583           | 0.1111           |
| mlp                                 | 65          | -0.02114               | 0.08775                   | 0.5712       | 14.12           | 0.3056           | 0.2361           |
| ridge                               | 58          | -0.005717              | 0.05235                   | -2.079       | 8.553           | 0.2778           | 0.2222           |
| ridge                               | 60          | 0.008279               | 0.07168                   | 1.294        | 9.761           | 0.3056           | 0.25             |
| ridge                               | 62          | 0.02371                | 0.07323                   | 0.3634       | 7.203           | 0.4167           | 0.1389           |
| ridge                               | 64          | -0.01049               | 0.05712                   | -0.4071      | 9.381           | 0.4167           | 0.1528           |
| ridge                               | 65          | -0.02987               | 0.05984                   | -0.5927      | 8.549           | 0.2917           | 0.2222           |
| template_residual_boosted_stack_new | 58          | -0.01071               | 0.0676                    | -1.591       | 7.76            | 0.3056           | 0.2083           |
| template_residual_boosted_stack_new | 60          | 0.003039               | 0.06094                   | 1.48         | 8.045           | 0.3611           | 0.2222           |
| template_residual_boosted_stack_new | 62          | 0.005738               | 0.06429                   | 0.803        | 6.285           | 0.4028           | 0.2222           |
| template_residual_boosted_stack_new | 64          | -0.01613               | 0.06799                   | 0.9656       | 7.056           | 0.4861           | 0.1667           |
| template_residual_boosted_stack_new | 65          | -0.03192               | 0.09003                   | -0.6283      | 6.951           | 0.375            | 0.1528           |
| tiny_sequence_transformer           | 58          | -0.02526               | 0.09346                   | -11.41       | 13.28           | 0.5              | 0.2361           |
| tiny_sequence_transformer           | 60          | 0.01293                | 0.09497                   | -6.829       | 12.89           | 0.4583           | 0.2222           |
| tiny_sequence_transformer           | 62          | -0.0005874             | 0.1352                    | -11.77       | 15.92           | 0.5694           | 0.1944           |
| tiny_sequence_transformer           | 64          | -0.06526               | 0.104                     | -10.48       | 20.44           | 0.5972           | 0.1111           |
| tiny_sequence_transformer           | 65          | -0.04845               | 0.1124                    | -10.13       | 19.81           | 0.3889           | 0.1528           |
| two_pulse_template_cfd_baseline     | 58          | 0.007111               | 0.06986                   | -0.4089      | 14.64           | 0.6111           | 0.1389           |
| two_pulse_template_cfd_baseline     | 60          | 0.009886               | 0.06907                   | 2.816        | 7.4             | 0.6944           | 0.1944           |
| two_pulse_template_cfd_baseline     | 62          | -0.01484               | 0.1011                    | 0.9669       | 7.104           | 0.5972           | 0.1944           |
| two_pulse_template_cfd_baseline     | 64          | 0.006458               | 0.08477                   | 0.848        | 8.333           | 0.5972           | 0.1111           |
| two_pulse_template_cfd_baseline     | 65          | -0.0125                | 0.07799                   | 0.1022       | 7.681           | 0.5556           | 0.1944           |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate |
| --------------- | -------------- | ----------------------------------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- |
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              | 0.02409                | 0.05891                   | 1.226        | 12.29           | 0.5652           |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              | 0.01256                | 0.09024                   | 2.24         | 9.797           | 0.5412           |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              | -0.002721              | 0.08212                   | -1.087       | 10.99           | 0.1884           |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              | -0.03751               | 0.07118                   | -1.594       | 12.16           | 0.2206           |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              | -0.0001035             | 0.05927                   | 1.535        | 7.384           | 0.4855           |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              | 0.00949                | 0.056                     | 0.4656       | 6.756           | 0.4588           |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              | -0.01228               | 0.07749                   | -0.7648      | 7.915           | 0.2609           |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              | -0.04561               | 0.07608                   | -1.574       | 7.586           | 0.2206           |
| spacing_bin     | (-0.001, 10.0] | mlp                                 | 0.03925                | 0.1076                    | 3.036        | 12.96           | 0.4928           |
| spacing_bin     | (10.0, 25.0]   | mlp                                 | -0.003164              | 0.1276                    | 1.421        | 12.52           | 0.5059           |
| spacing_bin     | (25.0, 45.0]   | mlp                                 | -0.02215               | 0.1173                    | 1.654        | 12.45           | 0.2609           |
| spacing_bin     | (45.0, 70.0]   | mlp                                 | -0.04645               | 0.0958                    | -4.215       | 13.8            | 0.1912           |
| spacing_bin     | (-0.001, 10.0] | ridge                               | 0.006645               | 0.05029                   | 0.6468       | 9.598           | 0.413            |
| spacing_bin     | (10.0, 25.0]   | ridge                               | 0.00627                | 0.05246                   | 0.3619       | 7.374           | 0.4471           |
| spacing_bin     | (25.0, 45.0]   | ridge                               | -0.00186               | 0.07546                   | 0.2758       | 8.504           | 0.2174           |
| spacing_bin     | (45.0, 70.0]   | ridge                               | -0.05818               | 0.05923                   | -4.332       | 11.01           | 0.1912           |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new | 0.002989               | 0.06292                   | 1.311        | 7.819           | 0.5              |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new | -0.005585              | 0.05806                   | 0.2345       | 7.065           | 0.4588           |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new | 0.01147                | 0.07536                   | -0.6863      | 8.241           | 0.2609           |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new | -0.03922               | 0.08168                   | -1.35        | 7.705           | 0.1912           |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           | 0.02059                | 0.06043                   | -5.722       | 11.84           | 0.6594           |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           | 0.01382                | 0.07971                   | -11.74       | 10.6            | 0.6              |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           | -0.0517                | 0.113                     | -11.91       | 15.94           | 0.2899           |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           | -0.151                 | 0.07099                   | -14.16       | 22.59           | 0.2794           |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     | 0.01906                | 0.06599                   | 2.69         | 12.66           | 0.7536           |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     | 0.01787                | 0.06953                   | 2.647        | 10.88           | 0.6471           |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     | -0.005094              | 0.09968                   | 1.066        | 9.297           | 0.5652           |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     | -0.03738               | 0.08269                   | -1.838       | 9.102           | 0.3235           |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              | 0.02621                | 0.06044                   | -2.137       | 13.38           | 0.5806           |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              | -0.003572              | 0.08997                   | -0.6618      | 12.12           | 0.4022           |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              | -0.01508               | 0.07537                   | -0.4389      | 11.18           | 0.4157           |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              | -0.009404              | 0.05439                   | 3.109        | 9.845           | 0.2791           |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              | 0.009395               | 0.06463                   | -1.952       | 8.771           | 0.6452           |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              | 0.01183                | 0.06629                   | 0.4023       | 8.349           | 0.4348           |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              | -0.01664               | 0.08336                   | -0.7753      | 6.859           | 0.2472           |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              | -0.0211                | 0.05739                   | 1.944        | 7.938           | 0.1977           |
| ratio_bin       | (-0.001, 0.35] | mlp                                 | 0.02472                | 0.1415                    | -4.6         | 17.69           | 0.6022           |
| ratio_bin       | (0.35, 0.625]  | mlp                                 | 0.006609               | 0.1106                    | -2.842       | 13.28           | 0.337            |
| ratio_bin       | (0.625, 0.875] | mlp                                 | -0.01236               | 0.1221                    | 0.97         | 11.09           | 0.3371           |
| ratio_bin       | (0.875, 1.05]  | mlp                                 | -0.01944               | 0.1086                    | 2.948        | 12.34           | 0.2907           |
| ratio_bin       | (-0.001, 0.35] | ridge                               | 0.03058                | 0.09427                   | -4.183       | 9.957           | 0.5699           |
| ratio_bin       | (0.35, 0.625]  | ridge                               | -0.005413              | 0.06795                   | -1.263       | 9.061           | 0.3478           |
| ratio_bin       | (0.625, 0.875] | ridge                               | -0.01455               | 0.05952                   | -0.06987     | 7.736           | 0.2584           |
| ratio_bin       | (0.875, 1.05]  | ridge                               | -0.009125              | 0.04472                   | 2.973        | 8.652           | 0.1744           |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new | 0.008364               | 0.05795                   | -2.312       | 8.191           | 0.6129           |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new | -0.006056              | 0.07245                   | 0.07143      | 8.794           | 0.4348           |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new | -0.008562              | 0.0704                    | 0.3403       | 6.562           | 0.2472           |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new | -0.01874               | 0.0701                    | 1.569        | 7.3             | 0.2326           |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           | -0.02786               | 0.1046                    | -11.2        | 16.32           | 0.6882           |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           | -0.05635               | 0.1225                    | -10.65       | 18.16           | 0.4457           |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           | -0.06526               | 0.1095                    | -10.73       | 16.12           | 0.4719           |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           | 0.005829               | 0.08483                   | -9.937       | 12.29           | 0.3953           |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     | 0.01917                | 0.1004                    | 0.856        | 12.84           | 0.6882           |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     | -0.007449              | 0.1221                    | -1.415       | 7.913           | 0.6196           |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     | -0.005387              | 0.04919                   | 1.119        | 9.372           | 0.573            |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     | 0.005824               | 0.06623                   | 1.536        | 7.172           | 0.5581           |
| stave           | B2             | 1d_cnn                              | -0.0177                | 0.09285                   | -9.932       | 11.18           | 0.5663           |
| stave           | B4             | 1d_cnn                              | 0.01226                | 0.08466                   | -3.622       | 11.42           | 0.5054           |
| stave           | B6             | 1d_cnn                              | -0.01815               | 0.07416                   | 1.342        | 8.393           | 0.3958           |
| stave           | B8             | 1d_cnn                              | 0.003583               | 0.06394                   | 5.748        | 7.659           | 0.2273           |
| stave           | B2             | gradient_boosted_trees              | -0.03771               | 0.06352                   | -6.53        | 9.165           | 0.4217           |
| stave           | B4             | gradient_boosted_trees              | -0.001059              | 0.06917                   | -2.409       | 7.425           | 0.5054           |
| stave           | B6             | gradient_boosted_trees              | -0.02205               | 0.07142                   | 0.993        | 4.769           | 0.3854           |
| stave           | B8             | gradient_boosted_trees              | 0.009121               | 0.06283                   | 2.717        | 5.823           | 0.2273           |
| stave           | B2             | mlp                                 | -0.008578              | 0.1439                    | -9.45        | 13.05           | 0.5783           |
| stave           | B4             | mlp                                 | 0.002724               | 0.1317                    | -2.035       | 15.05           | 0.4301           |
| stave           | B6             | mlp                                 | -0.003827              | 0.1047                    | 0.2003       | 10.9            | 0.3229           |
| stave           | B8             | mlp                                 | 0.001601               | 0.1169                    | 4.804        | 10.55           | 0.2614           |
| stave           | B2             | ridge                               | -0.02266               | 0.06734                   | -5.686       | 9.931           | 0.4337           |
| stave           | B4             | ridge                               | 0.02734                | 0.06494                   | -2.146       | 8.738           | 0.3871           |
| stave           | B6             | ridge                               | -0.007637              | 0.0621                    | 0.4063       | 7.961           | 0.3438           |
| stave           | B8             | ridge                               | -0.01191               | 0.05403                   | 3.226        | 6.871           | 0.2045           |
| stave           | B2             | template_residual_boosted_stack_new | -0.0331                | 0.0505                    | -7.277       | 7.932           | 0.4578           |
| stave           | B4             | template_residual_boosted_stack_new | 0.004259               | 0.06798                   | -2.44        | 7.598           | 0.4731           |
| stave           | B6             | template_residual_boosted_stack_new | -0.006127              | 0.07867                   | 1.017        | 5.645           | 0.3854           |
| stave           | B8             | template_residual_boosted_stack_new | 0.006266               | 0.06639                   | 2.28         | 5.647           | 0.2273           |
| stave           | B2             | tiny_sequence_transformer           | -0.01013               | 0.1027                    | -14.36       | 16.97           | 0.6867           |
| stave           | B4             | tiny_sequence_transformer           | -0.006561              | 0.1129                    | -11.15       | 18.51           | 0.5914           |
| stave           | B6             | tiny_sequence_transformer           | -0.04403               | 0.119                     | -9.66        | 15.85           | 0.4375           |
| stave           | B8             | tiny_sequence_transformer           | -0.04654               | 0.08684                   | -6.435       | 13.59           | 0.3068           |
| stave           | B2             | two_pulse_template_cfd_baseline     | 0.05131                | 0.05786                   | 2.088        | 17.83           | 0.7831           |
| stave           | B4             | two_pulse_template_cfd_baseline     | -0.05586               | 0.09161                   | -1.484       | 17.96           | 0.8387           |
| stave           | B6             | two_pulse_template_cfd_baseline     | -0.02467               | 0.05184                   | -0.01845     | 7.246           | 0.5833           |
| stave           | B8             | two_pulse_template_cfd_baseline     | 0.006458               | 0.08365                   | 1.112        | 5.733           | 0.2386           |
| saturated_proxy | False          | 1d_cnn                              | -0.002045              | 0.07587                   | 1.288        | 11.57           | 0.4152           |
| saturated_proxy | True           | 1d_cnn                              | -0.0177                | 0.05099                   | -6.417       | 7.617           | 0.5556           |
| saturated_proxy | False          | gradient_boosted_trees              | -0.007909              | 0.06823                   | 0.441        | 7.443           | 0.4064           |
| saturated_proxy | True           | gradient_boosted_trees              | -0.03771               | 0.06634                   | -6.358       | 6.507           | 0                |
| saturated_proxy | False          | mlp                                 | -0.0005624             | 0.1159                    | 0.2948       | 13.57           | 0.3947           |
| saturated_proxy | True           | mlp                                 | -0.05331               | 0.1277                    | -2.636       | 9.022           | 0.3889           |
| saturated_proxy | False          | ridge                               | -0.002636              | 0.06371                   | 0.2018       | 8.814           | 0.3596           |
| saturated_proxy | True           | ridge                               | -0.03622               | 0.05577                   | -5.453       | 8.284           | 0                |
| saturated_proxy | False          | template_residual_boosted_stack_new | -0.008562              | 0.07163                   | 0.5981       | 7.738           | 0.4064           |
| saturated_proxy | True           | template_residual_boosted_stack_new | -0.035                 | 0.07098                   | -6.051       | 6.213           | 0                |
| saturated_proxy | False          | tiny_sequence_transformer           | -0.03983               | 0.1121                    | -10.38       | 16.16           | 0.5058           |
| saturated_proxy | True           | tiny_sequence_transformer           | 0.02071                | 0.07851                   | -12.88       | 10.6            | 0.4444           |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     | -0.001997              | 0.09294                   | 0.4604       | 9.34            | 0.6111           |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     | 0.008679               | 0.03182                   | 0.4423       | 13.83           | 0.6111           |

The file `winner_residual_morphology.png` plots the winning method's energy
residuals against pulse spacing and amplitude ratio, timing residuals against the
summed-amplitude saturation proxy, and miss rate by spacing/saturation bin.  The
underlying binned values are saved in `winner_failure_morphology.csv`.

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `39.2` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29`.

# S38b: saturation and pile-up joint energy recovery with censored waveform targets

## Ticket context and pre-registration

The claimed local-queue item was `1784069109.931.3d642a00` with title `S38b: saturation and pile-up joint energy recovery with censored waveform targets` and an
explicit body asking whether models can recover charge/energy proxies from
saturated or overlapping pulses better than conservative censored traditional
reconstruction.  The pre-registered target is: reproduce the raw selected-pulse
count from ROOT, then compare a clipped-template/two-pulse CFD baseline with
ridge, gradient-boosted trees, MLP, 1D-CNN, a compact sequence-transformer
waveform head, and a new physics-residual boosted stack on identical
run-heldout controlled-injection data.  The primary ranking metric is the
declared composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`.

This caveat is material: the result is an architecture benchmark under raw-ROOT
controlled truth.  Charge and energy are ADC-amplitude proxies; saturation is an
amplitude-ceiling proxy; PID migration is tested only through stave support
stability because no external particle species truth is available.

## Abstract

Ticket `1784069109.931.3d642a00` asks whether raw B-stack HRD waveforms support a stronger
architecture for saturated pulse energy and timing recovery than a traditional
saturation-knee/template correction.  The worker was `testbeam-laptop-4`.  Before fitting
any model, the raw ROOT selected-pulse anchor was reproduced exactly:
`640737` selected B-stave pulses versus the reference
`640737`, with delta `0`.

The winner is `template_residual_boosted_stack_new` by the predeclared composite ordering

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`,

where `sigma_E` is held-out fractional energy sigma68, `sigma_t` is constituent
timing sigma68 in ns, and the final two terms penalize missed injected pile-up and
false splitting of clean controls.  `template_residual_boosted_stack_new` obtains `sigma_E =
0.07532` with 95% run-block bootstrap CI
[0.06131,
0.08136] and timing sigma68
`7.745` ns.

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
`masked_token_waveform_transformer`, a one-layer self-attention encoder over the 18-sample
waveform trained with random sample-token masking, and `template_residual_boosted_stack_new`, a physics-residual stack that
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
| template_residual_boosted_stack_new | 0.1783       | -0.006288              | 0.07532                   | 0.06131                          | 0.08136                           | 0.1264       | 7.745           | 6.778                  | 8.351                   | 0.3556           | 0.1556           |
| gradient_boosted_trees              | 0.1817       | 0.001295               | 0.07273                   | 0.06461                          | 0.08588                           | 0.4554       | 8.383           | 7.319                  | 8.963                   | 0.3611           | 0.1417           |
| ridge                               | 0.2026       | 0.005844               | 0.07386                   | 0.06466                          | 0.09079                           | 0.7967       | 10.4            | 10.01                  | 11.4                    | 0.3167           | 0.1778           |
| two_pulse_template_cfd_baseline     | 0.2156       | 0.00696                | 0.08492                   | 0.07319                          | 0.1017                            | 0.5522       | 9.078           | 7.965                  | 11.51                   | 0.6194           | 0.1778           |
| 1d_cnn                              | 0.2255       | 0.00749                | 0.08538                   | 0.07664                          | 0.1025                            | 0.8264       | 11.25           | 10.59                  | 12.09                   | 0.3417           | 0.2111           |
| masked_token_waveform_transformer   | 0.2944       | -0.032                 | 0.1074                    | 0.09442                          | 0.1228                            | -12.44       | 15.28           | 14.35                  | 16.15                   | 0.1917           | 0.4917           |
| mlp                                 | 0.3052       | -0.01872               | 0.1608                    | 0.1429                           | 0.177                             | -0.4659      | 11.53           | 10.71                  | 12.38                   | 0.3833           | 0.1972           |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.009607`
and timing sigma68 by `-1.333` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              | heldout_run | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| ----------------------------------- | ----------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- | ---------------- |
| 1d_cnn                              | 58          | 0.03579                | 0.0734                    | 0.02803      | 12.64           | 0.3333           | 0.25             |
| 1d_cnn                              | 60          | 0.006388               | 0.06752                   | 1.932        | 10.61           | 0.3472           | 0.3056           |
| 1d_cnn                              | 62          | 0.004167               | 0.1078                    | 1.971        | 10.78           | 0.25             | 0.2083           |
| 1d_cnn                              | 64          | -0.006366              | 0.07676                   | 0.2478       | 11.08           | 0.3889           | 0.1667           |
| 1d_cnn                              | 65          | 0.001136               | 0.08638                   | -0.3688      | 10.47           | 0.3889           | 0.125            |
| gradient_boosted_trees              | 58          | 0.002735               | 0.0501                    | 0.04445      | 8.863           | 0.2917           | 0.1667           |
| gradient_boosted_trees              | 60          | 0.001646               | 0.064                     | 0.994        | 6.236           | 0.3889           | 0.2083           |
| gradient_boosted_trees              | 62          | 0.008472               | 0.08044                   | -0.2196      | 8.897           | 0.25             | 0.125            |
| gradient_boosted_trees              | 64          | -0.03377               | 0.08079                   | 0.8758       | 8.404           | 0.4306           | 0.08333          |
| gradient_boosted_trees              | 65          | 0.01141                | 0.08707                   | 0.5069       | 7.941           | 0.4444           | 0.125            |
| masked_token_waveform_transformer   | 58          | -0.02649               | 0.105                     | -10.93       | 16              | 0.1667           | 0.5417           |
| masked_token_waveform_transformer   | 60          | -0.01453               | 0.08116                   | -12.72       | 15.25           | 0.2222           | 0.5139           |
| masked_token_waveform_transformer   | 62          | -0.05913               | 0.1444                    | -11.81       | 16.21           | 0.1528           | 0.4306           |
| masked_token_waveform_transformer   | 64          | -0.02125               | 0.1001                    | -12.1        | 14.04           | 0.1389           | 0.5139           |
| masked_token_waveform_transformer   | 65          | -0.03384               | 0.1196                    | -14.33       | 14.25           | 0.2778           | 0.4583           |
| mlp                                 | 58          | 0.001536               | 0.1326                    | -4.516       | 12.08           | 0.375            | 0.2361           |
| mlp                                 | 60          | -0.02548               | 0.1645                    | 1.169        | 10.85           | 0.375            | 0.1806           |
| mlp                                 | 62          | -0.02216               | 0.1471                    | -0.7593      | 12.18           | 0.3194           | 0.2083           |
| mlp                                 | 64          | -0.01787               | 0.1656                    | -0.7675      | 12.79           | 0.4306           | 0.1944           |
| mlp                                 | 65          | -0.01493               | 0.1792                    | 0.9327       | 10.49           | 0.4167           | 0.1667           |
| ridge                               | 58          | 0.01229                | 0.04851                   | -1.274       | 10.25           | 0.3056           | 0.2083           |
| ridge                               | 60          | 0.006239               | 0.06461                   | 2.236        | 9.696           | 0.2917           | 0.2639           |
| ridge                               | 62          | 0.01873                | 0.09144                   | 1.728        | 10.15           | 0.2222           | 0.1528           |
| ridge                               | 64          | -0.01033               | 0.07229                   | 0.3078       | 11.74           | 0.375            | 0.125            |
| ridge                               | 65          | -0.001307              | 0.08861                   | 0.3725       | 9.415           | 0.3889           | 0.1389           |
| template_residual_boosted_stack_new | 58          | -0.002683              | 0.04928                   | -0.1027      | 8.193           | 0.3194           | 0.1667           |
| template_residual_boosted_stack_new | 60          | -0.01355               | 0.057                     | 0.443        | 7.364           | 0.375            | 0.2639           |
| template_residual_boosted_stack_new | 62          | 0.004044               | 0.07857                   | 0.3618       | 8.317           | 0.2917           | 0.1667           |
| template_residual_boosted_stack_new | 64          | -0.00383               | 0.07785                   | -0.4555      | 7.823           | 0.375            | 0.05556          |
| template_residual_boosted_stack_new | 65          | -0.007491              | 0.07946                   | 0.152        | 6.227           | 0.4167           | 0.125            |
| two_pulse_template_cfd_baseline     | 58          | 0.0001924              | 0.07163                   | 2.217        | 9.979           | 0.6389           | 0.2222           |
| two_pulse_template_cfd_baseline     | 60          | 0.02288                | 0.06845                   | 0.2326       | 7.56            | 0.5972           | 0.25             |
| two_pulse_template_cfd_baseline     | 62          | 0.02569                | 0.1091                    | 0.04428      | 7.338           | 0.5417           | 0.1944           |
| two_pulse_template_cfd_baseline     | 64          | 0.0008105              | 0.07424                   | -0.08394     | 7.845           | 0.6111           | 0.1111           |
| two_pulse_template_cfd_baseline     | 65          | -0.02582               | 0.08094                   | 0.01027      | 12.06           | 0.7083           | 0.1111           |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate |
| --------------- | -------------- | ----------------------------------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- |
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              | 0.03283                | 0.08987                   | 1.632        | 13.09           | 0.4677           |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              | 0.02425                | 0.08617                   | 2.232        | 8.49            | 0.4              |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              | 0.01198                | 0.07478                   | 1.072        | 8.555           | 0.3291           |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              | -0.02662               | 0.08559                   | -1.496       | 13.48           | 0.1098           |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              | 0.02197                | 0.0711                    | 0.6104       | 9.218           | 0.4355           |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              | 0.0284                 | 0.0806                    | 2.022        | 7.783           | 0.4533           |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              | -0.001513              | 0.05515                   | 0.159        | 6.773           | 0.3797           |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              | -0.04112               | 0.06373                   | -0.1805      | 9.075           | 0.1463           |
| spacing_bin     | (-0.001, 10.0] | masked_token_waveform_transformer   | 0.01897                | 0.08359                   | -11.5        | 17.11           | 0.25             |
| spacing_bin     | (10.0, 25.0]   | masked_token_waveform_transformer   | 0.01089                | 0.07264                   | -12.08       | 14.43           | 0.1867           |
| spacing_bin     | (25.0, 45.0]   | masked_token_waveform_transformer   | -0.04938               | 0.06856                   | -12.25       | 13.99           | 0.2025           |
| spacing_bin     | (45.0, 70.0]   | masked_token_waveform_transformer   | -0.1511                | 0.1043                    | -14.37       | 15.41           | 0.09756          |
| spacing_bin     | (-0.001, 10.0] | mlp                                 | 0.0348                 | 0.1324                    | 2.606        | 10.67           | 0.4355           |
| spacing_bin     | (10.0, 25.0]   | mlp                                 | -0.005248              | 0.1627                    | 0.294        | 9.664           | 0.4667           |
| spacing_bin     | (25.0, 45.0]   | mlp                                 | -0.02515               | 0.1799                    | 0.916        | 10.89           | 0.4051           |
| spacing_bin     | (45.0, 70.0]   | mlp                                 | -0.05789               | 0.1398                    | -5.761       | 13.21           | 0.2073           |
| spacing_bin     | (-0.001, 10.0] | ridge                               | 0.02029                | 0.0878                    | 0.8769       | 10.97           | 0.3387           |
| spacing_bin     | (10.0, 25.0]   | ridge                               | 0.02451                | 0.0786                    | 2.497        | 7.231           | 0.4267           |
| spacing_bin     | (25.0, 45.0]   | ridge                               | 0.006269               | 0.05127                   | 2.035        | 9.446           | 0.3038           |
| spacing_bin     | (45.0, 70.0]   | ridge                               | -0.03416               | 0.07399                   | -1.336       | 13.44           | 0.1951           |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new | 0.005228               | 0.06521                   | 0.3081       | 8.736           | 0.4194           |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new | 0.02524                | 0.06178                   | 1.309        | 7.9             | 0.4267           |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new | -0.00374               | 0.07912                   | -0.9461      | 6.561           | 0.3544           |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new | -0.03172               | 0.07165                   | -0.3842      | 9.107           | 0.1951           |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     | 0.02464                | 0.05322                   | 2.204        | 17.83           | 0.7419           |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     | 0.04246                | 0.07096                   | 2.824        | 9.41            | 0.64             |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     | -0.01503               | 0.07964                   | -0.8687      | 7.465           | 0.6076           |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     | -0.01927               | 0.08677                   | -0.4784      | 8.174           | 0.4268           |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              | 0.04672                | 0.099                     | -4.012       | 12.85           | 0.5116           |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              | 0.0153                 | 0.1097                    | 0.3933       | 12.56           | 0.4054           |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              | -0.006833              | 0.06639                   | 1.912        | 10.59           | 0.2553           |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              | 0.01309                | 0.07694                   | 2.533        | 11.22           | 0.2358           |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              | 0.001646               | 0.1392                    | -2.272       | 10.13           | 0.5581           |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              | 0.01524                | 0.07581                   | 0.9139       | 8.984           | 0.3649           |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              | -0.01102               | 0.06245                   | 0.1527       | 7.838           | 0.266            |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              | -0.00914               | 0.06814                   | 1.781        | 7.181           | 0.283            |
| ratio_bin       | (-0.001, 0.35] | masked_token_waveform_transformer   | -0.03447               | 0.1132                    | -13.08       | 17.31           | 0.2791           |
| ratio_bin       | (0.35, 0.625]  | masked_token_waveform_transformer   | -0.04099               | 0.1256                    | -11.44       | 14.01           | 0.2703           |
| ratio_bin       | (0.625, 0.875] | masked_token_waveform_transformer   | -0.0441                | 0.09904                   | -14.28       | 15.57           | 0.1277           |
| ratio_bin       | (0.875, 1.05]  | masked_token_waveform_transformer   | -0.01248               | 0.1058                    | -10.18       | 14.71           | 0.1226           |
| ratio_bin       | (-0.001, 0.35] | mlp                                 | -0.01139               | 0.2014                    | -6.606       | 13.85           | 0.6047           |
| ratio_bin       | (0.35, 0.625]  | mlp                                 | 0.05756                | 0.1408                    | 0.3316       | 12.12           | 0.3784           |
| ratio_bin       | (0.625, 0.875] | mlp                                 | -0.03216               | 0.1529                    | -0.9279      | 11.25           | 0.3298           |
| ratio_bin       | (0.875, 1.05]  | mlp                                 | -0.03634               | 0.1436                    | 1.422        | 10.04           | 0.2547           |
| ratio_bin       | (-0.001, 0.35] | ridge                               | 0.00875                | 0.08654                   | -4.265       | 10.21           | 0.5116           |
| ratio_bin       | (0.35, 0.625]  | ridge                               | 0.03735                | 0.09659                   | -0.06293     | 10.07           | 0.3919           |
| ratio_bin       | (0.625, 0.875] | ridge                               | -0.01074               | 0.06096                   | 2.029        | 9.771           | 0.2447           |
| ratio_bin       | (0.875, 1.05]  | ridge                               | 0.004664               | 0.06172                   | 3.821        | 10.18           | 0.1698           |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new | 0.009645               | 0.08522                   | -3.644       | 8.914           | 0.5698           |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new | -0.0005759             | 0.0757                    | 0.1808       | 7.44            | 0.4189           |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new | -0.01389               | 0.06738                   | -0.2898      | 6.985           | 0.2447           |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new | -0.00383               | 0.06705                   | 1.538        | 7.817           | 0.2358           |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     | 0.01956                | 0.1068                    | 0.4497       | 12.85           | 0.7442           |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     | 0.03904                | 0.08391                   | -1.082       | 12.19           | 0.6892           |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     | 0.01103                | 0.05377                   | -0.3314      | 7.382           | 0.5426           |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     | -0.006651              | 0.08493                   | 2.114        | 7.8             | 0.5377           |
| stave           | B2             | 1d_cnn                              | 0.004861               | 0.112                     | -6.475       | 11.16           | 0.4483           |
| stave           | B4             | 1d_cnn                              | 0.0611                 | 0.07612                   | -0.741       | 10.9            | 0.4175           |
| stave           | B6             | 1d_cnn                              | -3.324e-06             | 0.07433                   | 1.209        | 9.081           | 0.2921           |
| stave           | B8             | 1d_cnn                              | -0.003724              | 0.06342                   | 5.964        | 9.846           | 0.1852           |
| stave           | B2             | gradient_boosted_trees              | -0.03108               | 0.08774                   | -3.722       | 9.532           | 0.4828           |
| stave           | B4             | gradient_boosted_trees              | 0.02306                | 0.08657                   | -0.95        | 7.737           | 0.3883           |
| stave           | B6             | gradient_boosted_trees              | -0.02349               | 0.06602                   | 0.9447       | 5.68            | 0.3258           |
| stave           | B8             | gradient_boosted_trees              | 0.001295               | 0.0602                    | 3.345        | 7.301           | 0.2346           |
| stave           | B2             | masked_token_waveform_transformer   | -0.043                 | 0.09686                   | -17.03       | 16.93           | 0.3678           |
| stave           | B4             | masked_token_waveform_transformer   | -0.00373               | 0.1064                    | -11.62       | 18.27           | 0.2233           |
| stave           | B6             | masked_token_waveform_transformer   | -0.03346               | 0.1094                    | -13.06       | 13.4            | 0.1236           |
| stave           | B8             | masked_token_waveform_transformer   | -0.02538               | 0.09947                   | -9.614       | 14.22           | 0.03704          |
| stave           | B2             | mlp                                 | -0.04717               | 0.1378                    | -4.378       | 13.19           | 0.4598           |
| stave           | B4             | mlp                                 | 0.07036                | 0.136                     | -2.274       | 13.13           | 0.4175           |
| stave           | B6             | mlp                                 | -0.05718               | 0.1577                    | -0.3252      | 9.283           | 0.3371           |
| stave           | B8             | mlp                                 | -0.03543               | 0.1522                    | 3.113        | 12.43           | 0.3086           |
| stave           | B2             | ridge                               | -0.02095               | 0.07204                   | -6.476       | 11.03           | 0.4368           |
| stave           | B4             | ridge                               | 0.0442                 | 0.0772                    | -1.673       | 10.99           | 0.3786           |
| stave           | B6             | ridge                               | -0.01256               | 0.07044                   | 0.9496       | 8.777           | 0.2472           |
| stave           | B8             | ridge                               | 0.008739               | 0.06402                   | 4.456        | 8.2             | 0.1852           |
| stave           | B2             | template_residual_boosted_stack_new | -0.01806               | 0.08816                   | -4.033       | 8.618           | 0.4828           |
| stave           | B4             | template_residual_boosted_stack_new | 0.02531                | 0.09539                   | -0.9017      | 8.931           | 0.4078           |
| stave           | B6             | template_residual_boosted_stack_new | -0.02039               | 0.06852                   | 0.3092       | 6.037           | 0.2921           |
| stave           | B8             | template_residual_boosted_stack_new | -0.006814              | 0.0475                    | 2.892        | 6.72            | 0.2222           |
| stave           | B2             | two_pulse_template_cfd_baseline     | 0.0661                 | 0.0477                    | -0.2461      | 17.67           | 0.7356           |
| stave           | B4             | two_pulse_template_cfd_baseline     | -0.006454              | 0.08108                   | -1.262       | 15.27           | 0.8641           |
| stave           | B6             | two_pulse_template_cfd_baseline     | -0.03078               | 0.0519                    | 0.4138       | 6.583           | 0.5281           |
| stave           | B8             | two_pulse_template_cfd_baseline     | 0.03934                | 0.0888                    | 1.462        | 5.415           | 0.284            |
| saturated_proxy | False          | 1d_cnn                              | 0.01124                | 0.08276                   | 1.539        | 11.18           | 0.3467           |
| saturated_proxy | True           | 1d_cnn                              | -0.05614               | 0.06773                   | -8.828       | 10.09           | 0.1818           |
| saturated_proxy | False          | gradient_boosted_trees              | 0.002735               | 0.07357                   | 0.7586       | 8.221           | 0.3725           |
| saturated_proxy | True           | gradient_boosted_trees              | -0.01564               | 0.04183                   | -3.035       | 7.093           | 0                |
| saturated_proxy | False          | masked_token_waveform_transformer   | -0.02929               | 0.1079                    | -11.93       | 15.16           | 0.1977           |
| saturated_proxy | True           | masked_token_waveform_transformer   | -0.09651               | 0.09218                   | -25.88       | 16.31           | 0                |
| saturated_proxy | False          | mlp                                 | -0.0168                | 0.1615                    | -0.1213      | 11.17           | 0.3954           |
| saturated_proxy | True           | mlp                                 | -0.09073               | 0.083                     | -6.206       | 11.61           | 0                |
| saturated_proxy | False          | ridge                               | 0.007934               | 0.07245                   | 1.093        | 10.41           | 0.3266           |
| saturated_proxy | True           | ridge                               | -0.1012                | 0.05437                   | -7.865       | 11.24           | 0                |
| saturated_proxy | False          | template_residual_boosted_stack_new | -0.003962              | 0.0755                    | 0.3241       | 7.663           | 0.3668           |
| saturated_proxy | True           | template_residual_boosted_stack_new | -0.03169               | 0.04043                   | -4.474       | 6.784           | 0                |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     | 0.007149               | 0.08575                   | 0.6701       | 9.152           | 0.6218           |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     | -0.005338              | 0.03421                   | -3.867       | 9.291           | 0.5455           |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `315.1` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.


## Falsification and post-hoc controls

The falsification condition was defined before the ticket-local run: if the raw
ROOT reproduction gate failed, the benchmark would stop and the mismatch would
be the finding.  If an ML/NN method won only by increasing pile-up misses or
false splits relative to the traditional fit, it would not be promoted because
the composite score explicitly penalizes both failure modes.  Multiple
comparisons are limited to the named model panel; no additional cut was selected
after observing the score table.

## Next-experiment policy

No novel ticket was appended from this worker.  The most useful next study would
require a concrete new truth handle, for example hardware saturation flags or
independent hand-scanned pile-up labels, rather than adding another generic
architecture bakeoff.


## S38b joint energy, saturation, and PID-proxy diagnostics

The ticket asks for charge residuals, energy-proxy bias, timing shift, pile-up
false split/merge rate, saturation-onset calibration, and PID-proxy migration.
The first four are direct controlled-injection endpoints.  Saturation onset is
defined by the same predeclared high-amplitude proxy, `A_1 + A_2 > 11000 ADC`,
and scored by predicted-total-amplitude thresholding.  Because no external
particle-identity truth label is present in this raw ROOT benchmark, the
PID-proxy migration diagnostic is the span of median energy residuals across
B2/B4/B6/B8; it is a support-stability check, not a p/d classification claim.
Intervals are held-out run-block percentile 95% CIs where available.

| method                              | charge_fractional_sigma68 | charge_fractional_sigma68_ci_low | charge_fractional_sigma68_ci_high | energy_proxy_bias | saturation_onset_accuracy | saturation_onset_calibration_abs | pid_proxy_energy_bias_span | pileup_merge_rate | pileup_false_split_rate |
| ----------------------------------- | ------------------------- | -------------------------------- | --------------------------------- | ----------------- | ------------------------- | -------------------------------- | -------------------------- | ----------------- | ----------------------- |
| gradient_boosted_trees              | 0.07273                   | 0.06412                          | 0.08588                           | 0.001295          | 0.9826                    | 0                                | 0.05415                    | 0.3611            | 0.1417                  |
| ridge                               | 0.07386                   | 0.06422                          | 0.08724                           | 0.005844          | 0.9837                    | 0.01626                          | 0.06515                    | 0.3167            | 0.1778                  |
| template_residual_boosted_stack_new | 0.07532                   | 0.06211                          | 0.08259                           | -0.006288         | 0.9914                    | 0.008621                         | 0.04571                    | 0.3556            | 0.1556                  |
| two_pulse_template_cfd_baseline     | 0.08492                   | 0.07249                          | 0.1041                            | 0.00696           | 1                         | 0                                | 0.09688                    | 0.6194            | 0.1778                  |
| 1d_cnn                              | 0.08538                   | 0.07703                          | 0.1023                            | 0.00749           | 0.9831                    | 0.008439                         | 0.06482                    | 0.3417            | 0.2111                  |
| masked_token_waveform_transformer   | 0.1074                    | 0.09442                          | 0.1224                            | -0.032            | 0.9794                    | 0.01375                          | 0.03927                    | 0.1917            | 0.4917                  |
| mlp                                 | 0.1608                    | 0.1432                           | 0.177                             | -0.01872          | 0.982                     | 0.01802                          | 0.1275                     | 0.3833            | 0.1972                  |


## Injection-source bootstrap

The run-block intervals above answer whether the ranking transfers across held-out
runs.  As a complementary stress test, `injection_source_bootstrap_ci.csv`
resamples retained source cells defined by
`source_run:stave:is_overlap:spacing_bin:ratio_bin`.  This unit preserves the
run-local residual source, detector stave/PID proxy, pile-up label, separation
family, and amplitude-ratio family rather than treating individual synthetic
events as independent draws.

| method                              | n_source_units | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | detection_ap | detection_ap_ci_low | detection_ap_ci_high |
| ----------------------------------- | -------------- | ------------------------- | -------------------------------- | --------------------------------- | --------------- | ---------------------- | ----------------------- | ------------ | ------------------- | -------------------- |
| gradient_boosted_trees              | 194            | 0.07273                   | 0.06145                          | 0.09333                           | 8.383           | 7.272                  | 9.646                   | 0.8414       | 0.7804              | 0.9059               |
| ridge                               | 194            | 0.07386                   | 0.06215                          | 0.09147                           | 10.4            | 9.353                  | 11.48                   | 0.852        | 0.7928              | 0.9127               |
| template_residual_boosted_stack_new | 194            | 0.07532                   | 0.05991                          | 0.08511                           | 7.745           | 6.797                  | 8.967                   | 0.8561       | 0.8009              | 0.9122               |
| two_pulse_template_cfd_baseline     | 194            | 0.08492                   | 0.06594                          | 0.104                             | 9.078           | 7.333                  | 11.9                    | 0.6644       | 0.5831              | 0.7672               |
| 1d_cnn                              | 194            | 0.08538                   | 0.07647                          | 0.1009                            | 11.25           | 10.43                  | 12.29                   | 0.7892       | 0.7107              | 0.8625               |
| masked_token_waveform_transformer   | 194            | 0.1074                    | 0.09758                          | 0.1185                            | 15.28           | 14.15                  | 16.61                   | 0.7622       | 0.6722              | 0.8493               |
| mlp                                 | 194            | 0.1608                    | 0.1403                           | 0.1819                            | 11.53           | 10.34                  | 13                      | 0.7824       | 0.6937              | 0.8679               |

# S39b: pedestal-state Kalman correction vs ML baseline memory models

## Ticket context and pre-registration

The claimed local-queue item was `1784070446.896.02dc6441` with title `S39b pedestal-state
Kalman correction vs ML baseline memory models for saturated energy recovery`
and an explicit body asking whether pretrigger pedestal memory and baseline
drift should be modeled as latent states for clipped/saturated energy recovery
and timing.  The pre-registered target is: reproduce the raw selected-pulse
count from ROOT, then compare a Kalman/state-space pedestal tracker with
analytic clipped-template charge reconstruction against ridge, gradient-boosted
trees, MLP, 1D-CNN, and a masked-token transformer on identical run-heldout
controlled-injection data.  The primary ranking metric is the declared
composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`.

This caveat is material: the result is an architecture benchmark under raw-ROOT
controlled truth.  Charge and energy are ADC-amplitude proxies; saturation is an
amplitude-ceiling proxy; PID migration is tested only through stave support
stability because no external particle species truth is available.  The
ticket-specific systematics section separately reports energy response,
saturation-knee location, timing bias, pedestal high-minus-low contrast,
pile-up leakage, PID-conditioned residuals, and feature-block ablations.

## Abstract

Ticket `1784070446.896.02dc6441` asks whether raw B-stack HRD waveforms support a stronger
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
0.07281` with 95% run-block bootstrap CI
[0.06157,
0.08044] and timing sigma68
`7.155` ns.

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

The S39b traditional comparator is `kalman_clipped_template_traditional`, a
causal scalar Kalman/local-level pretrigger pedestal tracker layered on the
bounded clipped-template two-pulse fit.  From the four pretrigger samples it
estimates a latent pedestal level `z_t` and drift proxy, then applies an
analytic clipped-charge correction when the pulse peak and plateau mask indicate
the amplitude-ceiling regime.  The transparent reference fit
`two_pulse_template_cfd_baseline` is retained in the table to separate the
state-space correction from the underlying template fit.  For one or two
constituents the template fit minimizes

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
| template_residual_boosted_stack_new | 0.1689       | -0.00303               | 0.07281                   | 0.06157                          | 0.08044                           | 0.1117       | 7.155           | 6.165                  | 7.55                    | 0.2972           | 0.1944           |
| gradient_boosted_trees              | 0.1718       | -0.003649              | 0.07463                   | 0.06467                          | 0.08457                           | 0.09253      | 7.272           | 6.156                  | 7.852                   | 0.3028           | 0.1861           |
| ridge                               | 0.1938       | -0.004398              | 0.07174                   | 0.06428                          | 0.07403                           | 0.4709       | 9.498           | 8.877                  | 9.757                   | 0.2722           | 0.2694           |
| two_pulse_template_cfd_baseline     | 0.2153       | 0.0114                 | 0.08872                   | 0.06603                          | 0.1018                            | 1.446        | 8.864           | 7.807                  | 10.61                   | 0.5583           | 0.2              |
| 1d_cnn                              | 0.2242       | -0.01748               | 0.08103                   | 0.06906                          | 0.08904                           | 1.055        | 11.35           | 10.78                  | 12.24                   | 0.3333           | 0.2611           |
| mlp                                 | 0.2475       | -0.02942               | 0.1167                    | 0.1088                           | 0.1253                            | -0.8265      | 10.3            | 9.378                  | 10.69                   | 0.3556           | 0.2              |
| kalman_clipped_template_traditional | 0.2626       | 0.1514                 | 0.1393                    | 0.1116                           | 0.1596                            | 1.42         | 8.43            | 7.157                  | 9.548                   | 0.5806           | 0.2              |
| masked_token_waveform_transformer   | 0.3195       | -0.1132                | 0.1378                    | 0.1206                           | 0.155                             | -13.38       | 15.11           | 13.81                  | 15.7                    | 0.2861           | 0.3278           |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.01591`
and timing sigma68 by `-1.709` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              | heldout_run | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| ----------------------------------- | ----------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- | ---------------- |
| 1d_cnn                              | 58          | -0.01289               | 0.06448                   | -0.8464      | 12.84           | 0.3056           | 0.3611           |
| 1d_cnn                              | 60          | -0.01295               | 0.07712                   | 3.493        | 9.177           | 0.3333           | 0.3194           |
| 1d_cnn                              | 62          | -0.02324               | 0.09197                   | 0.04385      | 11.84           | 0.3056           | 0.2222           |
| 1d_cnn                              | 64          | -0.02824               | 0.06353                   | 1.522        | 11.56           | 0.3611           | 0.2083           |
| 1d_cnn                              | 65          | -0.02814               | 0.08098                   | 1.02         | 11.24           | 0.3611           | 0.1944           |
| gradient_boosted_trees              | 58          | -0.01724               | 0.06299                   | -0.7278      | 5.266           | 0.2361           | 0.25             |
| gradient_boosted_trees              | 60          | 0.014                  | 0.06379                   | 0.8204       | 7.483           | 0.2361           | 0.2639           |
| gradient_boosted_trees              | 62          | -0.01359               | 0.09155                   | -0.9606      | 7.732           | 0.3333           | 0.1667           |
| gradient_boosted_trees              | 64          | -0.006797              | 0.06669                   | 0.8872       | 7.532           | 0.3056           | 0.1111           |
| gradient_boosted_trees              | 65          | -0.001443              | 0.06856                   | 1.764        | 7.15            | 0.4028           | 0.1389           |
| kalman_clipped_template_traditional | 58          | 0.1433                 | 0.1029                    | 1.118        | 9.714           | 0.5833           | 0.2222           |
| kalman_clipped_template_traditional | 60          | 0.176                  | 0.1387                    | 3.215        | 8.258           | 0.5417           | 0.2778           |
| kalman_clipped_template_traditional | 62          | 0.1264                 | 0.1197                    | 0.02526      | 6.579           | 0.5833           | 0.1667           |
| kalman_clipped_template_traditional | 64          | 0.1838                 | 0.1638                    | 2.672        | 9.198           | 0.6111           | 0.1944           |
| kalman_clipped_template_traditional | 65          | 0.1397                 | 0.1356                    | 0.1103       | 7.334           | 0.5833           | 0.1389           |
| masked_token_waveform_transformer   | 58          | -0.1381                | 0.1355                    | -13.34       | 14.44           | 0.2778           | 0.375            |
| masked_token_waveform_transformer   | 60          | -0.1171                | 0.1185                    | -12.04       | 13.88           | 0.2778           | 0.3889           |
| masked_token_waveform_transformer   | 62          | -0.09864               | 0.1457                    | -15.28       | 16.48           | 0.25             | 0.2917           |
| masked_token_waveform_transformer   | 64          | -0.1078                | 0.1167                    | -13.04       | 15.76           | 0.3194           | 0.25             |
| masked_token_waveform_transformer   | 65          | -0.09401               | 0.1701                    | -10.35       | 13.84           | 0.3056           | 0.3333           |
| mlp                                 | 58          | -0.01238               | 0.09717                   | -0.9309      | 10.01           | 0.3333           | 0.3056           |
| mlp                                 | 60          | -0.02619               | 0.1135                    | 2.063        | 8.401           | 0.3611           | 0.2222           |
| mlp                                 | 62          | -0.04581               | 0.1262                    | -2.561       | 9.524           | 0.3056           | 0.1389           |
| mlp                                 | 64          | -0.03623               | 0.1101                    | -0.2783      | 10.13           | 0.4028           | 0.1667           |
| mlp                                 | 65          | -0.0322                | 0.1142                    | -0.986       | 10.63           | 0.375            | 0.1667           |
| ridge                               | 58          | -0.007324              | 0.05679                   | 0.7263       | 9.16            | 0.2361           | 0.4028           |
| ridge                               | 60          | 0.02182                | 0.05873                   | 1.984        | 8.538           | 0.25             | 0.3056           |
| ridge                               | 62          | -0.006023              | 0.07068                   | -1.616       | 10.18           | 0.2222           | 0.2083           |
| ridge                               | 64          | -0.005416              | 0.07011                   | 1.062        | 8.928           | 0.3194           | 0.2083           |
| ridge                               | 65          | -0.01725               | 0.0596                    | 0.277        | 9.403           | 0.3333           | 0.2222           |
| template_residual_boosted_stack_new | 58          | -0.02078               | 0.05825                   | -1.032       | 5.611           | 0.2222           | 0.25             |
| template_residual_boosted_stack_new | 60          | 0.01527                | 0.06425                   | 1.635        | 6.529           | 0.25             | 0.2917           |
| template_residual_boosted_stack_new | 62          | -0.02017               | 0.08348                   | -0.7751      | 7.669           | 0.3056           | 0.1667           |
| template_residual_boosted_stack_new | 64          | 0.006978               | 0.06648                   | 0.5905       | 6.747           | 0.3056           | 0.08333          |
| template_residual_boosted_stack_new | 65          | -0.005321              | 0.05575                   | 1.341        | 6.553           | 0.4028           | 0.1806           |
| two_pulse_template_cfd_baseline     | 58          | -0.005131              | 0.08232                   | 0.8041       | 10.57           | 0.5556           | 0.2222           |
| two_pulse_template_cfd_baseline     | 60          | 0.02187                | 0.08771                   | 3.274        | 8.416           | 0.5139           | 0.2639           |
| two_pulse_template_cfd_baseline     | 62          | 0.008848               | 0.05511                   | -0.8626      | 7.244           | 0.5556           | 0.1667           |
| two_pulse_template_cfd_baseline     | 64          | 0.01665                | 0.1018                    | 2.827        | 9.827           | 0.5833           | 0.1944           |
| two_pulse_template_cfd_baseline     | 65          | 0.002408               | 0.09792                   | 0.1103       | 7.334           | 0.5833           | 0.1528           |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate |
| --------------- | -------------- | ----------------------------------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- |
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              | 0.02229                | 0.07713                   | 1.81         | 10.68           | 0.4565           |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              | 0.0004515              | 0.07355                   | 1.015        | 8.63            | 0.5065           |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              | -0.03804               | 0.06909                   | -1.178       | 10.57           | 0.1026           |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              | -0.05436               | 0.07289                   | 3.123        | 12.48           | 0.1493           |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              | 0.01274                | 0.0621                    | 0.3803       | 7.731           | 0.4203           |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              | 0.006723               | 0.06358                   | -0.8658      | 6.308           | 0.4156           |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              | -0.01294               | 0.07089                   | 0.884        | 7.995           | 0.1282           |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              | -0.03465               | 0.073                     | 0.208        | 7.086           | 0.1343           |
| spacing_bin     | (-0.001, 10.0] | kalman_clipped_template_traditional | 0.1624                 | 0.1337                    | 1.816        | 8.522           | 0.7174           |
| spacing_bin     | (10.0, 25.0]   | kalman_clipped_template_traditional | 0.1603                 | 0.1523                    | 2.41         | 10.82           | 0.5974           |
| spacing_bin     | (25.0, 45.0]   | kalman_clipped_template_traditional | 0.1232                 | 0.1293                    | 1.844        | 7.848           | 0.4487           |
| spacing_bin     | (45.0, 70.0]   | kalman_clipped_template_traditional | 0.08558                | 0.1639                    | -0.2338      | 7.865           | 0.4328           |
| spacing_bin     | (-0.001, 10.0] | masked_token_waveform_transformer   | -0.04549               | 0.09234                   | -11.21       | 9.121           | 0.3841           |
| spacing_bin     | (10.0, 25.0]   | masked_token_waveform_transformer   | -0.04888               | 0.1079                    | -14.98       | 13.14           | 0.4286           |
| spacing_bin     | (25.0, 45.0]   | masked_token_waveform_transformer   | -0.1412                | 0.1056                    | -15.75       | 16.33           | 0.1154           |
| spacing_bin     | (45.0, 70.0]   | masked_token_waveform_transformer   | -0.2638                | 0.09787                   | -18.54       | 20.88           | 0.1194           |
| spacing_bin     | (-0.001, 10.0] | mlp                                 | 0.002686               | 0.1001                    | 0.7975       | 9.737           | 0.4928           |
| spacing_bin     | (10.0, 25.0]   | mlp                                 | -0.0308                | 0.1175                    | -0.8919      | 9.476           | 0.5325           |
| spacing_bin     | (25.0, 45.0]   | mlp                                 | -0.03734               | 0.119                     | -0.6972      | 10.74           | 0.1282           |
| spacing_bin     | (45.0, 70.0]   | mlp                                 | -0.06179               | 0.1245                    | -2.623       | 10.65           | 0.1343           |
| spacing_bin     | (-0.001, 10.0] | ridge                               | 0.01463                | 0.0595                    | 0.9134       | 9.845           | 0.3623           |
| spacing_bin     | (10.0, 25.0]   | ridge                               | -0.0008065             | 0.07006                   | 0.8701       | 7.311           | 0.3506           |
| spacing_bin     | (25.0, 45.0]   | ridge                               | -0.02462               | 0.06124                   | 0.1015       | 9.706           | 0.1282           |
| spacing_bin     | (45.0, 70.0]   | ridge                               | -0.01736               | 0.07205                   | 0.1701       | 11.02           | 0.1642           |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new | 0.006221               | 0.07185                   | 1.61         | 7.417           | 0.4058           |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new | 0.01959                | 0.06408                   | -0.515       | 5.888           | 0.3896           |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new | -0.008441              | 0.08107                   | -0.1738      | 7.323           | 0.141            |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new | -0.02693               | 0.06391                   | -0.2049      | 6.617           | 0.1493           |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     | 0.00698                | 0.0679                    | 1.816        | 9.233           | 0.7101           |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     | 0.04438                | 0.07854                   | 2.41         | 12.13           | 0.5714           |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     | 0.01524                | 0.08571                   | 1.943        | 8.57            | 0.4103           |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     | -0.01736               | 0.08234                   | -0.2338      | 8.318           | 0.403            |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              | 0.01592                | 0.1062                    | -2.643       | 11.6            | 0.5455           |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              | -0.02445               | 0.0923                    | 1.343        | 13.21           | 0.2442           |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              | -0.03202               | 0.07063                   | 2.095        | 9.599           | 0.2907           |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              | -0.01981               | 0.07119                   | 1.335        | 9.636           | 0.26             |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              | 0.01565                | 0.1231                    | -3.489       | 8.846           | 0.5341           |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              | 0.001275               | 0.07902                   | -0.5132      | 6.867           | 0.3023           |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              | -0.002863              | 0.06509                   | 0.5229       | 6.59            | 0.2326           |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              | -0.01359               | 0.07029                   | 1.891        | 6.216           | 0.16             |
| ratio_bin       | (-0.001, 0.35] | kalman_clipped_template_traditional | 0.1438                 | 0.08355                   | 0.08969      | 9.084           | 0.7159           |
| ratio_bin       | (0.35, 0.625]  | kalman_clipped_template_traditional | 0.1628                 | 0.1664                    | 1.535        | 11.6            | 0.4651           |
| ratio_bin       | (0.625, 0.875] | kalman_clipped_template_traditional | 0.1526                 | 0.1304                    | 1.284        | 6.262           | 0.5233           |
| ratio_bin       | (0.875, 1.05]  | kalman_clipped_template_traditional | 0.1427                 | 0.1202                    | 1.856        | 5.947           | 0.61             |
| ratio_bin       | (-0.001, 0.35] | masked_token_waveform_transformer   | -0.09295               | 0.1546                    | -15.85       | 16.5            | 0.4659           |
| ratio_bin       | (0.35, 0.625]  | masked_token_waveform_transformer   | -0.1599                | 0.1411                    | -13.02       | 18.29           | 0.2209           |
| ratio_bin       | (0.625, 0.875] | masked_token_waveform_transformer   | -0.0914                | 0.1359                    | -12.81       | 12.3            | 0.2326           |
| ratio_bin       | (0.875, 1.05]  | masked_token_waveform_transformer   | -0.1245                | 0.1093                    | -11.8        | 14.11           | 0.23             |
| ratio_bin       | (-0.001, 0.35] | mlp                                 | -0.01602               | 0.123                     | -2.969       | 13.14           | 0.5795           |
| ratio_bin       | (0.35, 0.625]  | mlp                                 | -0.03236               | 0.09326                   | -0.7118      | 11.48           | 0.314            |
| ratio_bin       | (0.625, 0.875] | mlp                                 | -0.01471               | 0.09719                   | -0.5273      | 8.146           | 0.3023           |
| ratio_bin       | (0.875, 1.05]  | mlp                                 | -0.04474               | 0.1239                    | -0.348       | 9.318           | 0.24             |
| ratio_bin       | (-0.001, 0.35] | ridge                               | 0.01827                | 0.08215                   | -4.461       | 10.31           | 0.5227           |
| ratio_bin       | (0.35, 0.625]  | ridge                               | -0.001754              | 0.06299                   | -0.4241      | 9.911           | 0.2674           |
| ratio_bin       | (0.625, 0.875] | ridge                               | -0.006328              | 0.05761                   | 1.067        | 7.542           | 0.186            |
| ratio_bin       | (0.875, 1.05]  | ridge                               | -0.005678              | 0.07228                   | 2.928        | 9.388           | 0.13             |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new | 0.01432                | 0.1078                    | -3.563       | 8.894           | 0.5568           |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new | 0.01266                | 0.07714                   | -0.9663      | 6.379           | 0.3023           |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new | -0.0006993             | 0.05967                   | 0.3927       | 6.192           | 0.2093           |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new | -0.02265               | 0.06328                   | 2.017        | 6.305           | 0.14             |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     | 0.05783                | 0.09063                   | -0.5481      | 9.901           | 0.6818           |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     | 0.007962               | 0.09969                   | 1.766        | 11.86           | 0.4302           |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     | 0.003265               | 0.05993                   | 1.284        | 6.262           | 0.5233           |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     | 0.003764               | 0.07187                   | 2.026        | 5.987           | 0.59             |
| stave           | B2             | 1d_cnn                              | -0.02275               | 0.1437                    | -7.144       | 12.79           | 0.4839           |
| stave           | B4             | 1d_cnn                              | 0.001337               | 0.07038                   | -3.372       | 13.37           | 0.4744           |
| stave           | B6             | 1d_cnn                              | -0.01972               | 0.07685                   | -0.3958      | 9.235           | 0.2976           |
| stave           | B8             | 1d_cnn                              | -0.02226               | 0.06433                   | 3.73         | 7.409           | 0.1238           |
| stave           | B2             | gradient_boosted_trees              | -0.01724               | 0.1142                    | -5.838       | 8.1             | 0.4731           |
| stave           | B4             | gradient_boosted_trees              | -0.01009               | 0.07548                   | -1.731       | 7.22            | 0.2564           |
| stave           | B6             | gradient_boosted_trees              | 0.01051                | 0.05018                   | 0.3161       | 5.345           | 0.3571           |
| stave           | B8             | gradient_boosted_trees              | -0.001974              | 0.0716                    | 2.566        | 5.783           | 0.1429           |
| stave           | B2             | kalman_clipped_template_traditional | 0.1412                 | 0.09361                   | 2.755        | 18.16           | 0.7634           |
| stave           | B4             | kalman_clipped_template_traditional | 0.05884                | 0.08071                   | 8.536        | 20.51           | 0.9103           |
| stave           | B6             | kalman_clipped_template_traditional | 0.06361                | 0.1167                    | 0.1977       | 8.889           | 0.5476           |
| stave           | B8             | kalman_clipped_template_traditional | 0.1706                 | 0.1492                    | 1.523        | 4.777           | 0.2              |
| stave           | B2             | masked_token_waveform_transformer   | -0.1978                | 0.1214                    | -23.25       | 17.56           | 0.4624           |
| stave           | B4             | masked_token_waveform_transformer   | -0.09117               | 0.1382                    | -18.54       | 17.38           | 0.2949           |
| stave           | B6             | masked_token_waveform_transformer   | -0.06279               | 0.1055                    | -12.29       | 10.5            | 0.2976           |
| stave           | B8             | masked_token_waveform_transformer   | -0.1132                | 0.1364                    | -8.272       | 12.38           | 0.1143           |
| stave           | B2             | mlp                                 | -0.02939               | 0.1578                    | -3.575       | 13.7            | 0.5161           |
| stave           | B4             | mlp                                 | -0.03088               | 0.1161                    | -4.421       | 11.19           | 0.359            |
| stave           | B6             | mlp                                 | -0.00903               | 0.09075                   | -1.71        | 6.969           | 0.3452           |
| stave           | B8             | mlp                                 | -0.03791               | 0.1179                    | 2.04         | 9.592           | 0.219            |
| stave           | B2             | ridge                               | -0.04                  | 0.08069                   | -6.636       | 11.18           | 0.4516           |
| stave           | B4             | ridge                               | 0.001341               | 0.06065                   | -2.197       | 9.687           | 0.2949           |
| stave           | B6             | ridge                               | -0.001818              | 0.06361                   | 0.5887       | 8.219           | 0.2738           |
| stave           | B8             | ridge                               | -0.003374              | 0.06805                   | 2.766        | 7.224           | 0.09524          |
| stave           | B2             | template_residual_boosted_stack_new | 0.009157               | 0.08066                   | -4.566       | 7.457           | 0.4624           |
| stave           | B4             | template_residual_boosted_stack_new | -0.02075               | 0.06534                   | -1.387       | 6.687           | 0.2692           |
| stave           | B6             | template_residual_boosted_stack_new | 0.0005468              | 0.06661                   | 0.5236       | 5.699           | 0.3214           |
| stave           | B8             | template_residual_boosted_stack_new | -0.000276              | 0.07709                   | 2.431        | 5.618           | 0.1524           |
| stave           | B2             | two_pulse_template_cfd_baseline     | 0.06156                | 0.05522                   | 2.755        | 17.25           | 0.6882           |
| stave           | B4             | two_pulse_template_cfd_baseline     | -0.07681               | 0.06853                   | 8.536        | 20.51           | 0.9103           |
| stave           | B6             | two_pulse_template_cfd_baseline     | -0.04231               | 0.04473                   | 0.1977       | 8.889           | 0.5476           |
| stave           | B8             | two_pulse_template_cfd_baseline     | 0.02187                | 0.07701                   | 1.535        | 4.989           | 0.1905           |
| saturated_proxy | False          | 1d_cnn                              | -0.01478               | 0.07961                   | 1.335        | 10.91           | 0.3381           |
| saturated_proxy | True           | 1d_cnn                              | -0.1225                | 0.04804                   | -14.8        | 6.538           | 0.125            |
| saturated_proxy | False          | gradient_boosted_trees              | -0.002647              | 0.07461                   | 0.2773       | 7.287           | 0.3097           |
| saturated_proxy | True           | gradient_boosted_trees              | -0.05221               | 0.03241                   | -3.645       | 5.096           | 0                |
| saturated_proxy | False          | kalman_clipped_template_traditional | 0.1514                 | 0.1405                    | 1.446        | 8.252           | 0.5824           |
| saturated_proxy | True           | kalman_clipped_template_traditional | 0.1812                 | 0.0571                    | -0.2442      | 13.22           | 0.5              |
| saturated_proxy | False          | masked_token_waveform_transformer   | -0.11                  | 0.1344                    | -13.08       | 14.74           | 0.2898           |
| saturated_proxy | True           | masked_token_waveform_transformer   | -0.2595                | 0.06818                   | -30.33       | 9.823           | 0.125            |
| saturated_proxy | False          | mlp                                 | -0.02939               | 0.1167                    | -0.5129      | 10.2            | 0.3608           |
| saturated_proxy | True           | mlp                                 | -0.03868               | 0.07263                   | -8.123       | 13.35           | 0.125            |
| saturated_proxy | False          | ridge                               | -0.003336              | 0.06959                   | 0.5255       | 9.321           | 0.2756           |
| saturated_proxy | True           | ridge                               | -0.08907               | 0.04779                   | -6.842       | 12.4            | 0.125            |
| saturated_proxy | False          | template_residual_boosted_stack_new | -0.002427              | 0.07291                   | 0.3487       | 7.148           | 0.304            |
| saturated_proxy | True           | template_residual_boosted_stack_new | -0.06319               | 0.05234                   | -4.141       | 5.867           | 0                |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     | 0.0114                 | 0.08838                   | 1.478        | 8.582           | 0.5597           |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     | 0.004992               | 0.06283                   | -0.2442      | 13.22           | 0.5              |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `421.7` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.


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


## S39b energy, saturation, and PID-proxy diagnostics

The ticket asks for energy response, saturation knee behavior, timing shift,
pile-up leakage, and PID-conditioned residuals.  The first endpoints are direct
controlled-injection measurements.  Saturation onset is defined by the
predeclared high-amplitude proxy, `A_1 + A_2 > 11000 ADC`, and scored by
predicted-total-amplitude thresholding.  Because no external particle-identity
truth label is present in this raw ROOT benchmark, the PID diagnostic is the
span of median energy residuals across B2/B4/B6/B8; it is a support-stability
check, not a p/d classification claim.  Intervals are held-out run-block
percentile 95% CIs where available.

| method                              | charge_fractional_sigma68 | charge_fractional_sigma68_ci_low | charge_fractional_sigma68_ci_high | energy_proxy_bias | saturation_onset_accuracy | saturation_onset_calibration_abs | pid_proxy_energy_bias_span | pileup_merge_rate | pileup_false_split_rate |
| ----------------------------------- | ------------------------- | -------------------------------- | --------------------------------- | ----------------- | ------------------------- | -------------------------------- | -------------------------- | ----------------- | ----------------------- |
| ridge                               | 0.07174                   | 0.06173                          | 0.07402                           | -0.004398         | 0.9924                    | 0                                | 0.04134                    | 0.2722            | 0.2694                  |
| template_residual_boosted_stack_new | 0.07281                   | 0.06163                          | 0.08103                           | -0.00303          | 0.9921                    | 0.007905                         | 0.02991                    | 0.2972            | 0.1944                  |
| gradient_boosted_trees              | 0.07463                   | 0.0649                           | 0.08458                           | -0.003649         | 0.996                     | 0.003984                         | 0.02775                    | 0.3028            | 0.1861                  |
| 1d_cnn                              | 0.08103                   | 0.07264                          | 0.09013                           | -0.01748          | 0.9833                    | 0.008333                         | 0.02409                    | 0.3333            | 0.2611                  |
| two_pulse_template_cfd_baseline     | 0.08872                   | 0.06606                          | 0.1003                            | 0.0114            | 0.9874                    | 0.01258                          | 0.1384                     | 0.5583            | 0.2                     |
| mlp                                 | 0.1167                    | 0.1095                           | 0.1251                            | -0.02942          | 0.9871                    | 0.01293                          | 0.02888                    | 0.3556            | 0.2                     |
| masked_token_waveform_transformer   | 0.1378                    | 0.1206                           | 0.1546                            | -0.1132           | 0.9805                    | 0.01946                          | 0.135                      | 0.2861            | 0.3278                  |
| kalman_clipped_template_traditional | 0.1393                    | 0.1149                           | 0.1616                            | 0.1514            | 0.9669                    | 0.03311                          | 0.1118                     | 0.5806            | 0.2                     |


## S39b pedestal-memory and saturation systematics

The Kalman/state-space endpoint uses only causal pretrigger information to
estimate the latent pedestal level and drift.  The table reports the requested
run-block bootstrap quantities: energy response, saturation-knee location,
timing bias, pedestal high-minus-low contrast, pile-up leakage, and
PID-conditioned residual span.

| method                              | energy_response_median | energy_response_median_ci_low | energy_response_median_ci_high | timing_bias_ns | timing_bias_ns_ci_low | timing_bias_ns_ci_high | saturation_knee_location_adc | pedestal_high_minus_low_contrast | pileup_leakage_miss_rate | pileup_leakage_false_split_rate | pid_conditioned_residual_span |
| ----------------------------------- | ---------------------- | ----------------------------- | ------------------------------ | -------------- | --------------------- | ---------------------- | ---------------------------- | -------------------------------- | ------------------------ | ------------------------------- | ----------------------------- |
| masked_token_waveform_transformer   | -0.1132                | -0.1261                       | -0.0977                        | -7.316         | -9.105                | -5.682                 | 1.705e+04                    | 0.06907                          | 0.2861                   | 0.3278                          | 0.135                         |
| mlp                                 | -0.02942               | -0.03974                      | -0.01712                       | -1.116         | -1.976                | 0.5409                 | 1.232e+04                    | -0.02622                         | 0.3556                   | 0.2                             | 0.02888                       |
| 1d_cnn                              | -0.01748               | -0.02445                      | -0.01368                       | 0.9841         | -0.1845               | 2.623                  | 1.232e+04                    | -0.02423                         | 0.3333                   | 0.2611                          | 0.02409                       |
| ridge                               | -0.004398              | -0.009772                     | 0.01094                        | 0.818          | 0.2291                | 1.528                  | 1.307e+04                    | -0.00325                         | 0.2722                   | 0.2694                          | 0.04134                       |
| gradient_boosted_trees              | -0.003649              | -0.01523                      | 0.01137                        | 0.8198         | -0.2995               | 1.848                  | 1.307e+04                    | -0.01095                         | 0.3028                   | 0.1861                          | 0.02775                       |
| template_residual_boosted_stack_new | -0.00303               | -0.01822                      | 0.01008                        | 0.5016         | -0.2803               | 1.867                  | 1.232e+04                    | -0.005399                        | 0.2972                   | 0.1944                          | 0.02991                       |
| two_pulse_template_cfd_baseline     | 0.0114                 | 0.002408                      | 0.02124                        | 1.226          | 0.06671               | 2.452                  | 1.211e+04                    | -0.0135                          | 0.5583                   | 0.2                             | 0.1384                        |
| kalman_clipped_template_traditional | 0.1514                 | 0.1333                        | 0.1703                         | 1.337          | 0.2688                | 2.306                  | 1.081e+04                    | 0.08039                          | 0.5806                   | 0.2                             | 0.1118                        |

## Input-block ablations

The ablation rows refit the same boosted memory learner under the same run split.
`all_inputs` includes waveform samples plus causal Kalman pretrigger state,
tail-area, and saturation-mask features.  The other rows remove one block before
training and evaluation, so the deltas are measured on held-out runs rather than
post-hoc feature importances.

| ablation               | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | delta_energy_sigma68_vs_all_inputs | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | delta_time_sigma68_ns_vs_all_inputs | pileup_miss_rate | false_split_rate |
| ---------------------- | ------------------------- | -------------------------------- | --------------------------------- | ---------------------------------- | --------------- | ---------------------- | ----------------------- | ----------------------------------- | ---------------- | ---------------- |
| all_inputs             | 0.06436                   | 0.0537                           | 0.08048                           | 0                                  | 7.165           | 6.17                   | 7.798                   | 0                                   | 0.2972           | 0.1972           |
| remove_pretrigger      | 0.07966                   | 0.06882                          | 0.08562                           | 0.0153                             | 7.977           | 7.046                  | 8.715                   | 0.8116                              | 0.3556           | 0.1972           |
| remove_saturation_mask | 0.06331                   | 0.05528                          | 0.08006                           | -0.001057                          | 7.016           | 6.348                  | 7.59                    | -0.1489                             | 0.3111           | 0.1944           |
| remove_tail            | 0.07224                   | 0.06479                          | 0.08225                           | 0.007875                           | 7.358           | 6.735                  | 8.004                   | 0.1933                              | 0.3              | 0.225            |


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
| ridge                               | 198            | 0.07174                   | 0.06029                          | 0.08012                           | 9.498           | 8.568                  | 10.59                   | 0.7935       | 0.7131              | 0.8738               |
| template_residual_boosted_stack_new | 198            | 0.07281                   | 0.0646                           | 0.08114                           | 7.155           | 6.398                  | 7.569                   | 0.8398       | 0.7676              | 0.9057               |
| gradient_boosted_trees              | 198            | 0.07463                   | 0.06369                          | 0.08343                           | 7.272           | 6.646                  | 7.82                    | 0.8386       | 0.7713              | 0.8987               |
| 1d_cnn                              | 198            | 0.08103                   | 0.072                            | 0.09079                           | 11.35           | 10.27                  | 12.1                    | 0.7798       | 0.6875              | 0.8599               |
| two_pulse_template_cfd_baseline     | 198            | 0.08872                   | 0.07159                          | 0.0979                            | 8.864           | 7.245                  | 11.17                   | 0.6841       | 0.5882              | 0.7825               |
| mlp                                 | 198            | 0.1167                    | 0.1                              | 0.1356                            | 10.3            | 8.894                  | 11.74                   | 0.7761       | 0.6977              | 0.8675               |
| masked_token_waveform_transformer   | 198            | 0.1378                    | 0.1224                           | 0.1556                            | 15.11           | 13.26                  | 16.39                   | 0.7771       | 0.6898              | 0.8642               |
| kalman_clipped_template_traditional | 198            | 0.1393                    | 0.1133                           | 0.1648                            | 8.43            | 6.786                  | 10.32                   | 0.6378       | 0.5361              | 0.7734               |

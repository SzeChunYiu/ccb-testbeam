# S37a: sparse-ticket pile-up/saturation recovery frontier

## Ticket context and pre-registration

The claimed local-queue item was `1784068210.870.38ff282e` with title `testbeam-laptop-1` and an
empty body.  Because it did not define a narrower physics observable, this study
pre-registers the fleet's generic acceptance target before fitting: reproduce
the raw selected-pulse count from ROOT, then compare a strong conventional
two-template CFD/saturation-knee fit with ridge, gradient-boosted trees, MLP,
1D-CNN, a compact sequence transformer, and a new physics-residual boosted stack
on identical run-heldout controlled-injection data.  The primary ranking metric
is the already-declared composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`.

This caveat is material: the result is an architecture benchmark under
controlled raw-ROOT-derived truth, not a claim about a ticket-specific external
detector condition.

## Abstract

Ticket `1784068210.870.38ff282e` asks whether raw B-stack HRD waveforms support a stronger
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
0.07076` with 95% run-block bootstrap CI
[0.06847,
0.07267] and timing sigma68
`7.146` ns.

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
| template_residual_boosted_stack_new | 0.1636       | -0.001677              | 0.07076                   | 0.06847                          | 0.07267                           | -1.025       | 7.146           | 6.454                  | 8.1                     | 0.2889           | 0.1389           |
| gradient_boosted_trees              | 0.1684       | -0.002341              | 0.07081                   | 0.06668                          | 0.08159                           | -0.7284      | 7.634           | 6.486                  | 8.734                   | 0.2694           | 0.1556           |
| ridge                               | 0.1742       | -0.0009227             | 0.06694                   | 0.05843                          | 0.0752                            | -0.2549      | 8.629           | 8.12                   | 9.132                   | 0.25             | 0.1694           |
| two_pulse_template_cfd_baseline     | 0.219        | -0.006252              | 0.08686                   | 0.07843                          | 0.09243                           | 0.5004       | 9.547           | 7.664                  | 10.28                   | 0.5417           | 0.1917           |
| 1d_cnn                              | 0.2221       | 0.03958                | 0.08977                   | 0.08232                          | 0.09938                           | 0.6805       | 10.5            | 9.481                  | 11.77                   | 0.2361           | 0.3111           |
| mlp                                 | 0.2503       | -0.007329              | 0.1204                    | 0.1071                           | 0.1316                            | 0.1569       | 10.93           | 10.01                  | 12.28                   | 0.2556           | 0.1556           |
| tiny_sequence_transformer           | 0.2749       | -0.02241               | 0.1084                    | 0.09712                          | 0.1316                            | -11.38       | 13.86           | 12.39                  | 16.48                   | 0.3472           | 0.2111           |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes fractional energy sigma68
by `-0.01611`
and timing sigma68 by `-2.401` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

| method                              | heldout_run | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| ----------------------------------- | ----------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- | ---------------- |
| 1d_cnn                              | 58          | 0.03272                | 0.09599                   | 1.843        | 11.88           | 0.1944           | 0.25             |
| 1d_cnn                              | 60          | 0.04828                | 0.1058                    | 1.26         | 9.542           | 0.2917           | 0.3056           |
| 1d_cnn                              | 62          | 0.0475                 | 0.08285                   | 1.814        | 9.205           | 0.2222           | 0.2778           |
| 1d_cnn                              | 64          | 0.03026                | 0.08267                   | -1.716       | 11.89           | 0.2917           | 0.3472           |
| 1d_cnn                              | 65          | 0.05313                | 0.08604                   | 0.3864       | 9.614           | 0.1806           | 0.375            |
| gradient_boosted_trees              | 58          | 0.009049               | 0.06601                   | -0.2135      | 8.563           | 0.2361           | 0.1806           |
| gradient_boosted_trees              | 60          | -0.01481               | 0.07347                   | -0.3573      | 8.735           | 0.2778           | 0.1944           |
| gradient_boosted_trees              | 62          | -0.001432              | 0.06896                   | -0.0208      | 6.057           | 0.2778           | 0.09722          |
| gradient_boosted_trees              | 64          | -0.008526              | 0.08068                   | -2.278       | 8.08            | 0.3472           | 0.1667           |
| gradient_boosted_trees              | 65          | 6.126e-05              | 0.07204                   | -1.782       | 5.634           | 0.2083           | 0.1389           |
| mlp                                 | 58          | -0.001792              | 0.1092                    | -0.4991      | 10.69           | 0.2222           | 0.1389           |
| mlp                                 | 60          | -0.004069              | 0.1089                    | 1.633        | 13.67           | 0.3333           | 0.1806           |
| mlp                                 | 62          | -0.02883               | 0.08844                   | 0.3193       | 10.97           | 0.2361           | 0.1111           |
| mlp                                 | 64          | 0.003381               | 0.1314                    | -0.09811     | 10.19           | 0.3194           | 0.1667           |
| mlp                                 | 65          | -0.004139              | 0.1311                    | 0.09846      | 9.575           | 0.1667           | 0.1806           |
| ridge                               | 58          | 0.006518               | 0.05973                   | -0.23        | 8.673           | 0.2222           | 0.1944           |
| ridge                               | 60          | -0.002566              | 0.07302                   | 1.008        | 9.115           | 0.2778           | 0.1667           |
| ridge                               | 62          | -0.004928              | 0.05417                   | 0.09261      | 7.973           | 0.2361           | 0.1944           |
| ridge                               | 64          | 0.003285               | 0.08323                   | -1.354       | 9.348           | 0.3194           | 0.125            |
| ridge                               | 65          | -0.008271              | 0.0575                    | -0.8264      | 8.16            | 0.1944           | 0.1667           |
| template_residual_boosted_stack_new | 58          | 0.008841               | 0.07251                   | -1.371       | 7.573           | 0.2361           | 0.125            |
| template_residual_boosted_stack_new | 60          | -0.01315               | 0.06899                   | 0.1702       | 8.5             | 0.3056           | 0.1806           |
| template_residual_boosted_stack_new | 62          | -0.009232              | 0.0681                    | -0.5582      | 6.437           | 0.25             | 0.1389           |
| template_residual_boosted_stack_new | 64          | -0.0001414             | 0.07022                   | -1.812       | 7.889           | 0.375            | 0.1667           |
| template_residual_boosted_stack_new | 65          | 0.002144               | 0.06689                   | -1.943       | 6.063           | 0.2778           | 0.08333          |
| tiny_sequence_transformer           | 58          | -0.03466               | 0.1138                    | -8.57        | 12.62           | 0.2917           | 0.2222           |
| tiny_sequence_transformer           | 60          | -0.03116               | 0.1703                    | -10.31       | 14.28           | 0.3611           | 0.1667           |
| tiny_sequence_transformer           | 62          | -0.0127                | 0.09663                   | -11.05       | 12.62           | 0.3056           | 0.25             |
| tiny_sequence_transformer           | 64          | -0.01631               | 0.08952                   | -14.39       | 18.79           | 0.4306           | 0.1806           |
| tiny_sequence_transformer           | 65          | -0.01935               | 0.1371                    | -14.13       | 11.1            | 0.3472           | 0.2361           |
| two_pulse_template_cfd_baseline     | 58          | -0.008948              | 0.0762                    | 3.379        | 10.31           | 0.4444           | 0.1806           |
| two_pulse_template_cfd_baseline     | 60          | 0.01427                | 0.08904                   | 0.2812       | 9.676           | 0.5556           | 0.1806           |
| two_pulse_template_cfd_baseline     | 62          | -0.01279               | 0.09073                   | 0.8861       | 8.103           | 0.6111           | 0.1806           |
| two_pulse_template_cfd_baseline     | 64          | -0.01419               | 0.0844                    | -0.3759      | 8.219           | 0.5556           | 0.2222           |
| two_pulse_template_cfd_baseline     | 65          | -0.002344              | 0.08553                   | -1.369       | 8.673           | 0.5417           | 0.1944           |

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

| stratum         | value          | method                              | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate |
| --------------- | -------------- | ----------------------------------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- |
| spacing_bin     | (-0.001, 10.0] | 1d_cnn                              | 0.06463                | 0.06675                   | 1.251        | 11.79           | 0.3772           |
| spacing_bin     | (10.0, 25.0]   | 1d_cnn                              | 0.08661                | 0.09564                   | 1.613        | 7.696           | 0.2366           |
| spacing_bin     | (25.0, 45.0]   | 1d_cnn                              | 0.03105                | 0.07811                   | -1.233       | 8.175           | 0.1341           |
| spacing_bin     | (45.0, 70.0]   | 1d_cnn                              | -0.02523               | 0.08236                   | 2.009        | 14.26           | 0.1268           |
| spacing_bin     | (-0.001, 10.0] | gradient_boosted_trees              | 0.01173                | 0.06427                   | -1.164       | 9.329           | 0.3421           |
| spacing_bin     | (10.0, 25.0]   | gradient_boosted_trees              | 0.02186                | 0.06629                   | -0.04538     | 6.504           | 0.3118           |
| spacing_bin     | (25.0, 45.0]   | gradient_boosted_trees              | -0.009971              | 0.07566                   | -0.6367      | 7.701           | 0.1707           |
| spacing_bin     | (45.0, 70.0]   | gradient_boosted_trees              | -0.04485               | 0.06571                   | -1.408       | 7.753           | 0.2113           |
| spacing_bin     | (-0.001, 10.0] | mlp                                 | 0.02791                | 0.1041                    | 1.871        | 9.339           | 0.3333           |
| spacing_bin     | (10.0, 25.0]   | mlp                                 | 0.005898               | 0.1188                    | 1.777        | 7.579           | 0.2581           |
| spacing_bin     | (25.0, 45.0]   | mlp                                 | -0.02749               | 0.08665                   | -3.909       | 13.27           | 0.1829           |
| spacing_bin     | (45.0, 70.0]   | mlp                                 | -0.0379                | 0.1391                    | -3.034       | 13.35           | 0.2113           |
| spacing_bin     | (-0.001, 10.0] | ridge                               | 0.009495               | 0.061                     | -0.02774     | 10.29           | 0.3246           |
| spacing_bin     | (10.0, 25.0]   | ridge                               | 0.01818                | 0.07219                   | 0.7904       | 6.413           | 0.2688           |
| spacing_bin     | (25.0, 45.0]   | ridge                               | -0.008309              | 0.05591                   | -0.992       | 8.158           | 0.1707           |
| spacing_bin     | (45.0, 70.0]   | ridge                               | -0.03494               | 0.0513                    | -2.416       | 10.61           | 0.1972           |
| spacing_bin     | (-0.001, 10.0] | template_residual_boosted_stack_new | 0.01512                | 0.05883                   | -0.7911      | 8.918           | 0.4123           |
| spacing_bin     | (10.0, 25.0]   | template_residual_boosted_stack_new | 0.01072                | 0.07097                   | -0.5286      | 7.1             | 0.2903           |
| spacing_bin     | (25.0, 45.0]   | template_residual_boosted_stack_new | -0.01309               | 0.06975                   | -1.303       | 7.076           | 0.1829           |
| spacing_bin     | (45.0, 70.0]   | template_residual_boosted_stack_new | -0.03376               | 0.06388                   | -1.995       | 7.365           | 0.2113           |
| spacing_bin     | (-0.001, 10.0] | tiny_sequence_transformer           | 0.005333               | 0.0702                    | -9.727       | 12.54           | 0.4386           |
| spacing_bin     | (10.0, 25.0]   | tiny_sequence_transformer           | 0.02704                | 0.09111                   | -13.92       | 10.38           | 0.4194           |
| spacing_bin     | (25.0, 45.0]   | tiny_sequence_transformer           | -0.04951               | 0.08779                   | -12.94       | 13.99           | 0.2561           |
| spacing_bin     | (45.0, 70.0]   | tiny_sequence_transformer           | -0.1342                | 0.1359                    | -8.985       | 16.25           | 0.2113           |
| spacing_bin     | (-0.001, 10.0] | two_pulse_template_cfd_baseline     | -0.005103              | 0.07673                   | 2.668        | 12.3            | 0.7193           |
| spacing_bin     | (10.0, 25.0]   | two_pulse_template_cfd_baseline     | 0.02575                | 0.08907                   | 1.126        | 9.708           | 0.5484           |
| spacing_bin     | (25.0, 45.0]   | two_pulse_template_cfd_baseline     | -0.01061               | 0.0756                    | 0.5004       | 10.05           | 0.4634           |
| spacing_bin     | (45.0, 70.0]   | two_pulse_template_cfd_baseline     | -0.03007               | 0.08488                   | -1.019       | 8.033           | 0.338            |
| ratio_bin       | (-0.001, 0.35] | 1d_cnn                              | 0.007375               | 0.1062                    | -0.823       | 11.84           | 0.425            |
| ratio_bin       | (0.35, 0.625]  | 1d_cnn                              | 0.04179                | 0.09112                   | 1.647        | 9.075           | 0.2532           |
| ratio_bin       | (0.625, 0.875] | 1d_cnn                              | 0.04182                | 0.07568                   | 1.63         | 11.01           | 0.1042           |
| ratio_bin       | (0.875, 1.05]  | 1d_cnn                              | 0.04744                | 0.08325                   | 1.118        | 10.2            | 0.2              |
| ratio_bin       | (-0.001, 0.35] | gradient_boosted_trees              | -0.003332              | 0.07817                   | -3.461       | 9.274           | 0.4875           |
| ratio_bin       | (0.35, 0.625]  | gradient_boosted_trees              | -0.0007376             | 0.0725                    | -2.187       | 8.948           | 0.3038           |
| ratio_bin       | (0.625, 0.875] | gradient_boosted_trees              | -0.01375               | 0.05879                   | -0.6445      | 6.338           | 0.2292           |
| ratio_bin       | (0.875, 1.05]  | gradient_boosted_trees              | 0.0001109              | 0.0661                    | 0.2233       | 8.398           | 0.1143           |
| ratio_bin       | (-0.001, 0.35] | mlp                                 | 0.01907                | 0.1424                    | -2.393       | 12.37           | 0.5375           |
| ratio_bin       | (0.35, 0.625]  | mlp                                 | -0.004139              | 0.1409                    | -0.4905      | 10.93           | 0.3165           |
| ratio_bin       | (0.625, 0.875] | mlp                                 | -0.03214               | 0.1093                    | -0.7969      | 10.02           | 0.125            |
| ratio_bin       | (0.875, 1.05]  | mlp                                 | -0.001253              | 0.1024                    | 2.439        | 10.74           | 0.1143           |
| ratio_bin       | (-0.001, 0.35] | ridge                               | 0.01081                | 0.05358                   | -3.758       | 10.36           | 0.5375           |
| ratio_bin       | (0.35, 0.625]  | ridge                               | -0.003376              | 0.0714                    | -1.904       | 8.152           | 0.3038           |
| ratio_bin       | (0.625, 0.875] | ridge                               | -0.0019                | 0.05869                   | 0.6325       | 7.849           | 0.125            |
| ratio_bin       | (0.875, 1.05]  | ridge                               | -0.009757              | 0.06792                   | 1.403        | 8.407           | 0.1048           |
| ratio_bin       | (-0.001, 0.35] | template_residual_boosted_stack_new | -0.004642              | 0.06469                   | -3.978       | 8.008           | 0.5125           |
| ratio_bin       | (0.35, 0.625]  | template_residual_boosted_stack_new | 0.0005216              | 0.07629                   | -2.096       | 8.119           | 0.3544           |
| ratio_bin       | (0.625, 0.875] | template_residual_boosted_stack_new | -0.001548              | 0.05575                   | -1.396       | 6.299           | 0.1979           |
| ratio_bin       | (0.875, 1.05]  | template_residual_boosted_stack_new | -0.003746              | 0.07338                   | 0.71         | 7.48            | 0.1524           |
| ratio_bin       | (-0.001, 0.35] | tiny_sequence_transformer           | -0.01757               | 0.1526                    | -13.7        | 15.64           | 0.575            |
| ratio_bin       | (0.35, 0.625]  | tiny_sequence_transformer           | -0.003398              | 0.09125                   | -13.72       | 14.18           | 0.3671           |
| ratio_bin       | (0.625, 0.875] | tiny_sequence_transformer           | -0.04308               | 0.1104                    | -11.42       | 13.18           | 0.2604           |
| ratio_bin       | (0.875, 1.05]  | tiny_sequence_transformer           | -0.02292               | 0.08872                   | -10.1        | 13.67           | 0.2381           |
| ratio_bin       | (-0.001, 0.35] | two_pulse_template_cfd_baseline     | -0.009546              | 0.1289                    | -1.894       | 11.47           | 0.6              |
| ratio_bin       | (0.35, 0.625]  | two_pulse_template_cfd_baseline     | -0.005943              | 0.09876                   | 0.1907       | 9.873           | 0.4684           |
| ratio_bin       | (0.625, 0.875] | two_pulse_template_cfd_baseline     | 0.0007052              | 0.07716                   | 2.031        | 9.061           | 0.4896           |
| ratio_bin       | (0.875, 1.05]  | two_pulse_template_cfd_baseline     | -0.007045              | 0.06579                   | 1.19         | 7.761           | 0.6              |
| stave           | B2             | 1d_cnn                              | 0.003609               | 0.1075                    | -4.804       | 9.999           | 0.3855           |
| stave           | B4             | 1d_cnn                              | 0.08661                | 0.08272                   | -2.253       | 11.84           | 0.2451           |
| stave           | B6             | 1d_cnn                              | 0.01458                | 0.07838                   | 1.769        | 9.162           | 0.25             |
| stave           | B8             | 1d_cnn                              | 0.03596                | 0.07747                   | 4.241        | 8.644           | 0.08421          |
| stave           | B2             | gradient_boosted_trees              | -0.003291              | 0.07531                   | -6.426       | 9.586           | 0.3253           |
| stave           | B4             | gradient_boosted_trees              | 0.01002                | 0.08147                   | -2.419       | 6.508           | 0.2549           |
| stave           | B6             | gradient_boosted_trees              | -0.01182               | 0.0448                    | -0.006198    | 4.749           | 0.3125           |
| stave           | B8             | gradient_boosted_trees              | -0.009988              | 0.07198                   | 2.416        | 5.391           | 0.2              |
| stave           | B2             | mlp                                 | -0.004602              | 0.1416                    | -3.803       | 14.02           | 0.3494           |
| stave           | B4             | mlp                                 | -0.003651              | 0.1263                    | -0.8426      | 11.31           | 0.2157           |
| stave           | B6             | mlp                                 | 0.003277               | 0.1                       | -0.4588      | 9.368           | 0.325            |
| stave           | B8             | mlp                                 | -0.03836               | 0.1274                    | 2.746        | 9.905           | 0.1579           |
| stave           | B2             | ridge                               | -0.03123               | 0.06022                   | -5.171       | 9.51            | 0.3373           |
| stave           | B4             | ridge                               | 0.0115                 | 0.0606                    | -1.976       | 8.347           | 0.2451           |
| stave           | B6             | ridge                               | 0.003285               | 0.07102                   | -1.179       | 6.315           | 0.2875           |
| stave           | B8             | ridge                               | 0.006017               | 0.0623                    | 2.683        | 6.525           | 0.1474           |
| stave           | B2             | template_residual_boosted_stack_new | -0.01321               | 0.07645                   | -7.434       | 9.477           | 0.3373           |
| stave           | B4             | template_residual_boosted_stack_new | -0.002891              | 0.07402                   | -1.862       | 6.692           | 0.2647           |
| stave           | B6             | template_residual_boosted_stack_new | -0.005022              | 0.04842                   | 0.05992      | 4.866           | 0.3875           |
| stave           | B8             | template_residual_boosted_stack_new | 0.01554                | 0.07165                   | 1.354        | 5.788           | 0.1895           |
| stave           | B2             | tiny_sequence_transformer           | -0.02266               | 0.09255                   | -20.74       | 14.42           | 0.4819           |
| stave           | B4             | tiny_sequence_transformer           | 0.01679                | 0.1264                    | -11.08       | 15              | 0.3725           |
| stave           | B6             | tiny_sequence_transformer           | -0.02241               | 0.113                     | -10.49       | 12.06           | 0.4125           |
| stave           | B8             | tiny_sequence_transformer           | -0.04728               | 0.08801                   | -9.459       | 11.21           | 0.1474           |
| stave           | B2             | two_pulse_template_cfd_baseline     | 0.05062                | 0.07275                   | 5.185        | 16.76           | 0.6988           |
| stave           | B4             | two_pulse_template_cfd_baseline     | -0.04921               | 0.06802                   | -3.402       | 13.49           | 0.7843           |
| stave           | B6             | two_pulse_template_cfd_baseline     | -0.04601               | 0.03336                   | -1.061       | 8.247           | 0.475            |
| stave           | B8             | two_pulse_template_cfd_baseline     | 0.02078                | 0.09002                   | 0.8988       | 5.292           | 0.2              |
| saturated_proxy | False          | 1d_cnn                              | 0.03958                | 0.08868                   | 1.307        | 10.47           | 0.2368           |
| saturated_proxy | True           | 1d_cnn                              | 0.03933                | 0.08049                   | -6.173       | 7.808           | 0.2222           |
| saturated_proxy | False          | gradient_boosted_trees              | -0.003332              | 0.0711                    | -0.557       | 7.479           | 0.2836           |
| saturated_proxy | True           | gradient_boosted_trees              | 0.006208               | 0.06492                   | -5.217       | 6.453           | 0                |
| saturated_proxy | False          | mlp                                 | -0.01116               | 0.1215                    | 0.3917       | 11.21           | 0.269            |
| saturated_proxy | True           | mlp                                 | 0.01985                | 0.09031                   | -1.872       | 8.72            | 0                |
| saturated_proxy | False          | ridge                               | 0.002322               | 0.06665                   | 0.09995      | 8.553           | 0.2632           |
| saturated_proxy | True           | ridge                               | -0.04335               | 0.06221                   | -4.978       | 6.824           | 0                |
| saturated_proxy | False          | template_residual_boosted_stack_new | -0.002348              | 0.07011                   | -0.7469      | 7.434           | 0.3041           |
| saturated_proxy | True           | template_residual_boosted_stack_new | 0.004753               | 0.07462                   | -5.26        | 6.169           | 0                |
| saturated_proxy | False          | tiny_sequence_transformer           | -0.0222                | 0.1087                    | -10.82       | 13.73           | 0.3567           |
| saturated_proxy | True           | tiny_sequence_transformer           | -0.04081               | 0.08826                   | -20.74       | 12.94           | 0.1667           |
| saturated_proxy | False          | two_pulse_template_cfd_baseline     | -0.006793              | 0.0884                    | 0.4631       | 9.275           | 0.5292           |
| saturated_proxy | True           | two_pulse_template_cfd_baseline     | 0.03324                | 0.03201                   | 9.395        | 17.22           | 0.7778           |

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `203.3` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.


## Falsification and post-hoc controls

The falsification condition was defined before the ticket-local run: if the raw
ROOT reproduction gate failed, the benchmark would stop and the mismatch would
be the finding.  If an ML/NN method won only by increasing pile-up misses or
false splits relative to the traditional fit, it would not be promoted because
the composite score explicitly penalizes both failure modes.  Multiple
comparisons are limited to the named model panel; no additional cut was selected
after observing the score table.

## Next-experiment policy

No novel ticket was appended from this sparse ticket.  The most useful next
study would require a concrete detector question, for example hardware
saturation flags or independent hand-scanned pile-up labels, rather than adding
another generic architecture bakeoff.


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
| ridge                               | 199            | 0.06694                   | 0.05716                          | 0.07402                           | 8.629           | 7.866                  | 9.309                   | 0.8642       | 0.8044              | 0.9211               |
| template_residual_boosted_stack_new | 199            | 0.07076                   | 0.06104                          | 0.07751                           | 7.146           | 6.384                  | 8.354                   | 0.8831       | 0.833               | 0.9279               |
| gradient_boosted_trees              | 199            | 0.07081                   | 0.06307                          | 0.08366                           | 7.634           | 6.742                  | 8.706                   | 0.8803       | 0.8255              | 0.9295               |
| two_pulse_template_cfd_baseline     | 199            | 0.08686                   | 0.07323                          | 0.1018                            | 9.547           | 7.729                  | 11.8                    | 0.6882       | 0.5934              | 0.7819               |
| 1d_cnn                              | 199            | 0.08977                   | 0.07887                          | 0.1012                            | 10.5            | 9.609                  | 11.46                   | 0.8169       | 0.7344              | 0.8976               |
| tiny_sequence_transformer           | 199            | 0.1084                    | 0.09428                          | 0.1333                            | 13.86           | 12.33                  | 15.33                   | 0.7801       | 0.6969              | 0.8644               |
| mlp                                 | 199            | 0.1204                    | 0.1046                           | 0.1358                            | 10.93           | 9.765                  | 12.37                   | 0.8743       | 0.8228              | 0.9285               |

# S33c: PID energy timing multitask pulse representation audit

## Abstract

Ticket `1783888239.874.72877e21` asks for a raw-ROOT-reproduced benchmark of shared pulse
representations for PID, energy, and timing.  The worker was `testbeam-laptop-1`.  The
study compares a strong traditional charge-ratio/time-over-threshold/template
method with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new multitask
sequence architecture under a grouped split by run.

The raw selected-pulse anchor is reproduced directly from ROOT:
`640737` selected B-stave pulses versus reference
`640737`, delta `0`.

The winner named in `result.json` is **`template_residual_boosted_stack_new`**, selected by the held-out
composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy fractional sigma68 `0.06697`
with 95% run-block bootstrap CI
[0.06184, 0.07048],
timing sigma68 `7.532` ns with CI
[6.838, 8.897],
and PID balanced accuracy `0.9389` with CI
[0.9179, 0.9596].

## Raw ROOT Reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` branch is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The selected
B-stack pulse count is reproduced using B2/B4/B6/B8, pedestal

`b_c = median_t x_c(t), t in {0,1,2,3}`,

corrected waveform

`y_c(t)=x_c(t)-b_c`,

and selected-pulse condition

`max_t y_c(t)>1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split, Labels, And Leakage Controls

The grouped split is by source run: train runs `[50, 51, 52, 53, 54, 55, 56, 57]`
and held-out runs `[58, 60, 62, 64, 65]`.  No source run appears in
both sets.  Templates, scalers, likelihood moments, boosted trees, ridge heads,
MLP heads, CNN weights, and transformer weights are fitted on train-run events
only.  Run and event identifiers are retained for grouping and audit but are not
used as model features.

The PID endpoint is a deterministic raw-waveform proxy, not external particle
truth.  Controlled doublets are injected into raw clean-pulse residuals; the
deuteron-like positive class is fixed by total injected energy, stave depth, and
area-over-peak shape.  This makes the benchmark reproducible and leakage-audited
while limiting claims to architecture ranking.

For injected doublets,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{r,s}(t) + p`,

where `T_s` is the train-run stave template, `epsilon_{r,s}` is a raw residual
sampled from source run `r` and stave `s`, and `p` is the retained pedestal term.

Train-only template summaries:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              768 |                   2.579 |                      5 |           9.187 |
| B4      |              756 |                   2.944 |                      6 |          10.76  |
| B6      |              723 |                   3.748 |                      6 |           9.736 |
| B8      |              478 |                   4.26  |                      8 |           9.252 |

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`.  It combines a
bounded two-pulse template/CFD recovery for timing and energy with a diagonal
Gaussian likelihood-ratio PID model over charge-ratio, time-over-threshold, tail,
late-fraction, peak-sample, stave-depth, and dE/dx-like variables.  With
standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains:

| family | implementation |
|---|---|
| Ridge | standardized ridge classifier plus multi-output ridge recovery head |
| Gradient-boosted trees | histogram gradient-boosted PID, pile-up, and recovery heads |
| MLP | two-hidden-layer MLP classifiers/regressors with early stopping |
| 1D-CNN | compact waveform convolutional encoder with a separate PID head |
| New architecture | `joint_sequence_transformer`, a shared waveform transformer with pile-up, PID, and recovery heads |
| Physics-residual architecture | `template_residual_boosted_stack_new`, boosted residual heads using the traditional fit as first stage |

For accepted injected doublets, residuals are

`e_t = 10 ns (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`,

and

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`440` held-out run-block bootstrap resamples.

## Overall Held-Out Results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-------------------------------:|--------------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.1832 |    0.9959 |                  0.9389 |                         0.9179 |                          0.9596 |                     0.06697 |                            0.06184 |                             0.07048 |             7.532 |                    6.838 |                     8.897 |             0.3205 |             0.1923 |
| gradient_boosted_trees              |         0.1854 |    0.997  |                  0.9639 |                         0.9259 |                          0.9895 |                     0.06601 |                            0.06132 |                             0.07182 |             8.528 |                    7.435 |                     9.351 |             0.2872 |             0.2154 |
| ridge                               |         0.2295 |    0.995  |                  0.8153 |                         0.7417 |                          0.8937 |                     0.06387 |                            0.05226 |                             0.0754  |             9.483 |                    9.056 |                    10.41  |             0.2821 |             0.2103 |
| 1d_cnn                              |         0.2917 |    0.9648 |                  0.7382 |                         0.676  |                          0.7995 |                     0.09785 |                            0.08397 |                             0.1055  |            10.06  |                    9.162 |                    10.62  |             0.3077 |             0.2487 |
| deltaE_over_E_likelihood_template   |         0.2936 |    0.8775 |                  0.6632 |                         0.5876 |                          0.7395 |                     0.07833 |                            0.05707 |                             0.08193 |             9.171 |                    7.751 |                    10.04  |             0.6359 |             0.1513 |
| joint_sequence_transformer          |         0.3305 |    0.8519 |                  0.6444 |                         0.5537 |                          0.7016 |                     0.09885 |                            0.08711 |                             0.1112  |            11.25  |                   10.36  |                    12.46  |             0.4128 |             0.1923 |
| mlp                                 |         0.3467 |    0.9753 |                  0.8063 |                         0.7401 |                          0.8661 |                     0.1301  |                            0.1126  |                             0.1391  |            14.02  |                   13     |                    15.06  |             0.359  |             0.2    |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes energy sigma68 by
`-0.01135`,
timing sigma68 by `-1.639` ns,
and PID balanced accuracy by
`0.2757`.

## Ablations And Stress Tests

Three explicit ablation/stress views are reported in addition to the nominal
ranking.  `pileup_mask_removed_accept_all_candidates` is a direct post-fit
ablation of the per-method pile-up accept/reject mask.  The pedestal and
saturation entries are held-out robustness slices: top-quartile
`shape_area_over_amp` isolates pulses most sensitive to pedestal subtraction and
late-tail baseline motion, while top-quartile `true_energy_proxy_adc` isolates
the highest-amplitude saturation-proxy events.  These are not external hardware
truth flags.

Winner ablation summary:

| ablation                                   | method                              |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:-------------------------------------------|:------------------------------------|------------------------:|-------------------------------:|--------------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| nominal                                    | template_residual_boosted_stack_new |                  0.9389 |                         0.9221 |                          0.9612 |                     0.06697 |                            0.06217 |                             0.07048 |             7.532 |                    6.838 |                     8.549 |            0.3205  |             0.1923 |
| pedestal_sensitive_tail_shape_top_quartile | template_residual_boosted_stack_new |                  0.9413 |                         0.872  |                          0.9935 |                     0.08489 |                            0.07342 |                             0.09176 |             8.437 |                    6.998 |                    10.46  |            0.1641  |             0.4627 |
| saturation_proxy_high_energy_top_quartile  | template_residual_boosted_stack_new |                  0.9344 |                         0.9186 |                          0.9529 |                     0.06251 |                            0.04815 |                             0.07569 |             7.215 |                    5.99  |                     8.599 |            0.08125 |             0.5429 |
| pileup_mask_removed_accept_all_candidates  | template_residual_boosted_stack_new |                  0.9389 |                         0.9179 |                          0.9595 |                     0.07251 |                            0.0652  |                             0.07766 |             8.144 |                    7.485 |                     9.485 |            0       |             0.1923 |

Full method ablation metrics are written to `ablation_metrics.csv`; the first
rows are:

| ablation                                   | method                              |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:-------------------------------------------|:------------------------------------|------------------------:|-------------------------------:|--------------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| nominal                                    | 1d_cnn                              |                  0.7382 |                         0.676  |                          0.7995 |                     0.09785 |                            0.08398 |                             0.1028  |            10.06  |                    9.162 |                    10.59  |            0.3077  |             0.2487 |
| nominal                                    | deltaE_over_E_likelihood_template   |                  0.6632 |                         0.588  |                          0.7421 |                     0.07833 |                            0.06047 |                             0.08583 |             9.171 |                    7.75  |                    10.05  |            0.6359  |             0.1513 |
| nominal                                    | gradient_boosted_trees              |                  0.9639 |                         0.9266 |                          0.9892 |                     0.06601 |                            0.06132 |                             0.0722  |             8.528 |                    7.361 |                     9.351 |            0.2872  |             0.2154 |
| nominal                                    | joint_sequence_transformer          |                  0.6444 |                         0.554  |                          0.7028 |                     0.09885 |                            0.08748 |                             0.1128  |            11.25  |                   10.45  |                    12.12  |            0.4128  |             0.1923 |
| nominal                                    | mlp                                 |                  0.8063 |                         0.7401 |                          0.8712 |                     0.1301  |                            0.1072  |                             0.1394  |            14.02  |                   13     |                    15.06  |            0.359   |             0.2    |
| nominal                                    | ridge                               |                  0.8153 |                         0.7286 |                          0.8935 |                     0.06387 |                            0.0524  |                             0.07618 |             9.483 |                    9.005 |                    10.32  |            0.2821  |             0.2103 |
| nominal                                    | template_residual_boosted_stack_new |                  0.9389 |                         0.9221 |                          0.9612 |                     0.06697 |                            0.06217 |                             0.07048 |             7.532 |                    6.838 |                     8.549 |            0.3205  |             0.1923 |
| pedestal_sensitive_tail_shape_top_quartile | 1d_cnn                              |                  0.8019 |                         0.7517 |                          0.8499 |                     0.1121  |                            0.09938 |                             0.1246  |            11.99  |                   11.02  |                    12.46  |            0.07031 |             0.5522 |
| pedestal_sensitive_tail_shape_top_quartile | deltaE_over_E_likelihood_template   |                  0.6714 |                         0.5349 |                          0.7939 |                     0.06916 |                            0.05861 |                             0.09683 |             8.616 |                    8.147 |                    11.02  |            0.5312  |             0.1642 |
| pedestal_sensitive_tail_shape_top_quartile | gradient_boosted_trees              |                  0.9583 |                         0.9    |                          1      |                     0.07745 |                            0.06794 |                             0.08735 |             8.281 |                    7.692 |                    12.03  |            0.1016  |             0.5075 |
| pedestal_sensitive_tail_shape_top_quartile | joint_sequence_transformer          |                  0.6714 |                         0.5414 |                          0.7606 |                     0.1186  |                            0.1011  |                             0.1446  |            11.88  |                   10.95  |                    13.4   |            0.1328  |             0.4328 |
| pedestal_sensitive_tail_shape_top_quartile | mlp                                 |                  0.8441 |                         0.7398 |                          0.9474 |                     0.1545  |                            0.1352  |                             0.2327  |            16.73  |                   16.07  |                    17.72  |            0.1172  |             0.4627 |
| pedestal_sensitive_tail_shape_top_quartile | ridge                               |                  0.8472 |                         0.7236 |                          0.9342 |                     0.07765 |                            0.064   |                             0.08596 |             9.961 |                    9.204 |                    10.93  |            0.1328  |             0.4328 |
| pedestal_sensitive_tail_shape_top_quartile | template_residual_boosted_stack_new |                  0.9413 |                         0.872  |                          0.9935 |                     0.08489 |                            0.07342 |                             0.09176 |             8.437 |                    6.998 |                    10.46  |            0.1641  |             0.4627 |
| pileup_mask_removed_accept_all_candidates  | 1d_cnn                              |                  0.7382 |                         0.6725 |                          0.8021 |                     0.1099  |                            0.1013  |                             0.1182  |            10.76  |                   10.15  |                    11.11  |            0       |             0.2487 |
| pileup_mask_removed_accept_all_candidates  | deltaE_over_E_likelihood_template   |                  0.6632 |                         0.5939 |                          0.7485 |                     0.5139  |                            0.5127  |                             0.5165  |           nan     |                  nan     |                   nan     |            0       |             0.1513 |
| pileup_mask_removed_accept_all_candidates  | gradient_boosted_trees              |                  0.9639 |                         0.9291 |                          0.9893 |                     0.07192 |                            0.06767 |                             0.07597 |             8.674 |                    7.924 |                     9.423 |            0       |             0.2154 |
| pileup_mask_removed_accept_all_candidates  | joint_sequence_transformer          |                  0.6444 |                         0.554  |                          0.7028 |                     0.1191  |                            0.1103  |                             0.1313  |            13.15  |                   12.35  |                    13.82  |            0       |             0.1923 |
| pileup_mask_removed_accept_all_candidates  | mlp                                 |                  0.8063 |                         0.741  |                          0.87   |                     0.1512  |                            0.1276  |                             0.1705  |            14.69  |                   13.84  |                    15.19  |            0       |             0.2    |
| pileup_mask_removed_accept_all_candidates  | ridge                               |                  0.8153 |                         0.7177 |                          0.8864 |                     0.07278 |                            0.06356 |                             0.08012 |             9.346 |                    9.021 |                    10.18  |            0       |             0.2103 |

## Run-Held-Out Stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.8431 |           0.7143 |       0.7143 |                     0.08101 |             8.812 |             0.2949 |             0.3333 |
| 1d_cnn                              |            60 |                  0.7227 |           0.4667 |       0.7    |                     0.09859 |            10.27  |             0.2692 |             0.2179 |
| 1d_cnn                              |            62 |                  0.7429 |           0.5    |       0.8    |                     0.09675 |            10.82  |             0.359  |             0.2179 |
| 1d_cnn                              |            64 |                  0.6329 |           0.3    |       0.375  |                     0.09226 |             9.847 |             0.2949 |             0.2308 |
| 1d_cnn                              |            65 |                  0.6901 |           0.4    |       0.4    |                     0.1037  |             8.58  |             0.3205 |             0.2436 |
| deltaE_over_E_likelihood_template   |            58 |                  0.8008 |           0.7143 |       0.3846 |                     0.04735 |             7.235 |             0.6282 |             0.2051 |
| deltaE_over_E_likelihood_template   |            60 |                  0.5979 |           0.2667 |       0.2857 |                     0.07267 |            10.76  |             0.6282 |             0.1154 |
| deltaE_over_E_likelihood_template   |            62 |                  0.6652 |           0.4375 |       0.3182 |                     0.07464 |             8.523 |             0.641  |             0.141  |
| deltaE_over_E_likelihood_template   |            64 |                  0.5555 |           0.2    |       0.1333 |                     0.06519 |             8.94  |             0.6795 |             0.1154 |
| deltaE_over_E_likelihood_template   |            65 |                  0.6636 |           0.4    |       0.1538 |                     0.06901 |             7.29  |             0.6026 |             0.1795 |
| gradient_boosted_trees              |            58 |                  0.9965 |           1      |       0.9333 |                     0.07466 |             7.139 |             0.2692 |             0.3077 |
| gradient_boosted_trees              |            60 |                  0.9667 |           0.9333 |       1      |                     0.06659 |            10.23  |             0.2179 |             0.2949 |
| gradient_boosted_trees              |            62 |                  0.9652 |           0.9375 |       0.9375 |                     0.06729 |            10.2   |             0.2051 |             0.1538 |
| gradient_boosted_trees              |            64 |                  0.8932 |           0.8    |       0.8    |                     0.06125 |             6.845 |             0.3718 |             0.141  |
| gradient_boosted_trees              |            65 |                  1      |           1      |       1      |                     0.05097 |             8.053 |             0.3718 |             0.1795 |
| joint_sequence_transformer          |            58 |                  0.7359 |           0.5    |       0.6364 |                     0.09521 |            10.11  |             0.3462 |             0.3333 |
| joint_sequence_transformer          |            60 |                  0.6418 |           0.3333 |       0.4167 |                     0.1041  |            11.24  |             0.3846 |             0.1538 |
| joint_sequence_transformer          |            62 |                  0.6937 |           0.4375 |       0.5    |                     0.1011  |            13.09  |             0.4487 |             0.141  |
| joint_sequence_transformer          |            64 |                  0.476  |           0      |       0      |                     0.1188  |            11.56  |             0.4615 |             0.1538 |
| joint_sequence_transformer          |            65 |                  0.5768 |           0.2    |       0.125  |                     0.08231 |             9.924 |             0.4231 |             0.1795 |
| mlp                                 |            58 |                  0.7822 |           0.5714 |       0.8889 |                     0.1295  |            12.89  |             0.359  |             0.2821 |
| mlp                                 |            60 |                  0.9    |           0.8    |       1      |                     0.1491  |            15.31  |             0.2436 |             0.2179 |
| mlp                                 |            62 |                  0.7812 |           0.5625 |       1      |                     0.09758 |            15.46  |             0.359  |             0.1923 |
| mlp                                 |            64 |                  0.6932 |           0.4    |       0.6667 |                     0.1312  |            13.23  |             0.3846 |             0.141  |
| mlp                                 |            65 |                  0.9    |           0.8    |       1      |                     0.1109  |            12.7   |             0.4487 |             0.1667 |
| ridge                               |            58 |                  0.9286 |           0.8571 |       1      |                     0.06541 |             9.255 |             0.2564 |             0.2949 |
| ridge                               |            60 |                  0.8333 |           0.6667 |       1      |                     0.07696 |             9.634 |             0.2051 |             0.2179 |
| ridge                               |            62 |                  0.7812 |           0.5625 |       1      |                     0.06393 |            10.72  |             0.2949 |             0.2308 |
| ridge                               |            64 |                  0.65   |           0.3    |       1      |                     0.04883 |             8.865 |             0.2436 |             0.141  |
| ridge                               |            65 |                  0.8934 |           0.8    |       0.6667 |                     0.05009 |             9.699 |             0.4103 |             0.1667 |
| template_residual_boosted_stack_new |            58 |                  0.9643 |           0.9286 |       1      |                     0.07003 |             6.965 |             0.3077 |             0.2692 |
| template_residual_boosted_stack_new |            60 |                  0.9298 |           0.8667 |       0.9286 |                     0.05744 |             9.357 |             0.2051 |             0.2564 |
| template_residual_boosted_stack_new |            62 |                  0.9339 |           0.875  |       0.9333 |                     0.06611 |             8.942 |             0.2949 |             0.141  |
| template_residual_boosted_stack_new |            64 |                  0.9    |           0.8    |       1      |                     0.06265 |             6.597 |             0.3974 |             0.1026 |
| template_residual_boosted_stack_new |            65 |                  0.9934 |           1      |       0.7143 |                     0.07031 |             6.897 |             0.3974 |             0.1923 |

## Strata, Systematics, And Caveats

The stratum scan covers injected pulse spacing, total energy proxy, stave/depth,
and PID class.  It tests whether a method wins only in an easy spacing regime,
one stave, or one ionization class.

| stratum     | value                | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:---------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]       | 1d_cnn                              |                  0.6882 |                     0.08858 |            11.63  |            0.5     |
| spacing_bin | (10.0, 25.0]         | 1d_cnn                              |                  0.7075 |                     0.1009  |             8.595 |            0.4091  |
| spacing_bin | (25.0, 45.0]         | 1d_cnn                              |                  0.7724 |                     0.09577 |             8.256 |            0.1111  |
| spacing_bin | (45.0, 70.0]         | 1d_cnn                              |                  0.7472 |                     0.107   |            11.05  |            0.08974 |
| spacing_bin | (-0.001, 10.0]       | deltaE_over_E_likelihood_template   |                  0.7196 |                     0.07125 |            12.49  |            0.7985  |
| spacing_bin | (10.0, 25.0]         | deltaE_over_E_likelihood_template   |                  0.5734 |                     0.05313 |             6.432 |            0.7045  |
| spacing_bin | (25.0, 45.0]         | deltaE_over_E_likelihood_template   |                  0.7276 |                     0.08048 |             9.442 |            0.5333  |
| spacing_bin | (45.0, 70.0]         | deltaE_over_E_likelihood_template   |                  0.5861 |                     0.07497 |             9.775 |            0.3974  |
| spacing_bin | (-0.001, 10.0]       | gradient_boosted_trees              |                  0.9533 |                     0.0588  |             9.658 |            0.3731  |
| spacing_bin | (10.0, 25.0]         | gradient_boosted_trees              |                  0.9286 |                     0.05305 |             6.076 |            0.3864  |
| spacing_bin | (25.0, 45.0]         | gradient_boosted_trees              |                  0.9872 |                     0.06147 |             8.066 |            0.2333  |
| spacing_bin | (45.0, 70.0]         | gradient_boosted_trees              |                  1      |                     0.09174 |             9.251 |            0.08974 |
| spacing_bin | (-0.001, 10.0]       | joint_sequence_transformer          |                  0.5687 |                     0.06999 |            11.24  |            0.6045  |
| spacing_bin | (10.0, 25.0]         | joint_sequence_transformer          |                  0.5512 |                     0.09005 |             8.43  |            0.5568  |
| spacing_bin | (25.0, 45.0]         | joint_sequence_transformer          |                  0.6282 |                     0.1012  |             9.086 |            0.2333  |
| spacing_bin | (45.0, 70.0]         | joint_sequence_transformer          |                  0.6917 |                     0.1024  |            13.49  |            0.1282  |
| spacing_bin | (-0.001, 10.0]       | mlp                                 |                  0.7692 |                     0.111   |            12.96  |            0.4851  |
| spacing_bin | (10.0, 25.0]         | mlp                                 |                  0.7857 |                     0.1148  |            12.69  |            0.4659  |
| spacing_bin | (25.0, 45.0]         | mlp                                 |                  0.75   |                     0.1231  |            12.54  |            0.2667  |
| spacing_bin | (45.0, 70.0]         | mlp                                 |                  0.9083 |                     0.1427  |            15.58  |            0.1282  |
| spacing_bin | (-0.001, 10.0]       | ridge                               |                  0.8462 |                     0.05558 |             9.204 |            0.3955  |
| spacing_bin | (10.0, 25.0]         | ridge                               |                  0.7857 |                     0.06038 |             6.194 |            0.3409  |
| spacing_bin | (25.0, 45.0]         | ridge                               |                  0.7917 |                     0.0518  |             8.774 |            0.1889  |
| spacing_bin | (45.0, 70.0]         | ridge                               |                  0.8806 |                     0.07185 |            12.34  |            0.1282  |
| spacing_bin | (-0.001, 10.0]       | template_residual_boosted_stack_new |                  0.9189 |                     0.05875 |             8.898 |            0.4552  |
| spacing_bin | (10.0, 25.0]         | template_residual_boosted_stack_new |                  0.8861 |                     0.05479 |             5.228 |            0.4091  |
| spacing_bin | (25.0, 45.0]         | template_residual_boosted_stack_new |                  1      |                     0.06371 |             7.527 |            0.2333  |
| spacing_bin | (45.0, 70.0]         | template_residual_boosted_stack_new |                  0.9556 |                     0.08289 |             8.814 |            0.08974 |
| energy_bin  | (1500.999, 2987.281] | 1d_cnn                              |                  1      |                     0.08168 |            11.13  |            0.6061  |
| energy_bin  | (2987.281, 3899.75]  | 1d_cnn                              |                  1      |                     0.1175  |            12.29  |            0.4805  |
| energy_bin  | (3899.75, 5411.938]  | 1d_cnn                              |                  0.4974 |                     0.1045  |             9.906 |            0.275   |
| energy_bin  | (5411.938, 16862.0]  | 1d_cnn                              |                  0.6954 |                     0.08256 |             9.691 |            0.1875  |
| energy_bin  | (1500.999, 2987.281] | deltaE_over_E_likelihood_template   |                  0.9949 |                     0.08517 |            14.29  |            0.8485  |
| energy_bin  | (2987.281, 3899.75]  | deltaE_over_E_likelihood_template   |                  0.9846 |                     0.07044 |             9.545 |            0.7013  |
| energy_bin  | (3899.75, 5411.938]  | deltaE_over_E_likelihood_template   |                  0.4665 |                     0.06564 |            10.23  |            0.6083  |
| energy_bin  | (5411.938, 16862.0]  | deltaE_over_E_likelihood_template   |                  0.5354 |                     0.07309 |             7.227 |            0.5813  |
| energy_bin  | (1500.999, 2987.281] | gradient_boosted_trees              |                  1      |                     0.126   |             7.574 |            0.7273  |
| energy_bin  | (2987.281, 3899.75]  | gradient_boosted_trees              |                  1      |                     0.08749 |             9.311 |            0.6494  |
| energy_bin  | (3899.75, 5411.938]  | gradient_boosted_trees              |                  0.5    |                     0.0599  |             8.357 |            0.2333  |
| energy_bin  | (5411.938, 16862.0]  | gradient_boosted_trees              |                  0.9599 |                     0.06419 |             7.929 |            0.0625  |
| energy_bin  | (1500.999, 2987.281] | joint_sequence_transformer          |                  1      |                     0.08494 |            14.15  |            0.6061  |
| energy_bin  | (2987.281, 3899.75]  | joint_sequence_transformer          |                  0.9795 |                     0.1     |            10.94  |            0.5844  |
| energy_bin  | (3899.75, 5411.938]  | joint_sequence_transformer          |                  0.4716 |                     0.09675 |            11.67  |            0.4667  |
| energy_bin  | (5411.938, 16862.0]  | joint_sequence_transformer          |                  0.607  |                     0.08901 |            10.67  |            0.25    |
| energy_bin  | (1500.999, 2987.281] | mlp                                 |                  1      |                     0.1184  |            20.62  |            0.8788  |
| energy_bin  | (2987.281, 3899.75]  | mlp                                 |                  1      |                     0.1233  |            19.35  |            0.7013  |
| energy_bin  | (3899.75, 5411.938]  | mlp                                 |                  1      |                     0.1397  |            14.31  |            0.3333  |
| energy_bin  | (5411.938, 16862.0]  | mlp                                 |                  0.7941 |                     0.1242  |            12.43  |            0.1062  |

The leading systematic is the deterministic PID proxy.  It is useful for a
controlled architecture audit, but it is not external particle identification.
Pile-up and saturation conditions are controlled injections and high-amplitude
stress proxies inside raw ROOT residuals, not independent hardware labels.  The
18-sample window constrains sub-sample timing and makes pedestal motion partly
degenerate with late tails.  Bootstrap intervals resample held-out runs, so they
describe run-transfer uncertainty rather than event-level asymptotic precision.

Runtime was `163.1` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

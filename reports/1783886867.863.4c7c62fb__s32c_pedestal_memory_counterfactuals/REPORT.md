# S32c: Pedestal-Memory Counterfactuals for Pulse Amplitude and Identity Stability

## Abstract

Ticket `1783886867.863.4c7c62fb` asked whether pretrigger pedestal memory biases
pulse amplitude, timing, energy, and PID decisions after conventional baseline
subtraction.  The analysis reproduced the registered raw B-stack ROOT selected
pulse count, built a run-held-out benchmark from raw `h101/HRDv` waveforms, and
compared a strong traditional pedestal scorecard with ridge, gradient-boosted
trees, MLP, 1D-CNN, and a new pedestal-memory transformer.  The winner written to
`result.json` is **`gradient_boosted_trees`**, with composite score `1.959`.

## Raw ROOT Reproduction

The configured data location is `data/root/root/hrdb_run_*.root`; in
this checkout that path resolves through the project-standard raw ROOT fallback
`data/root/root`.  For each event the branch `HRDv` is reshaped to
`(8, 18)`.  For B2/B4/B6/B8 channel `c`, the conventional baseline is

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

and the selected-pulse predicate is

`max_t (x_c(t) - b_c) > 1000 ADC`.

| group                 | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --------------------- | ------------ | --------------- | ------------------------ | ----- | ---- |
| sample_i_calib        | 409815       | 248745          | 248745                   | 0     | True |
| sample_i_analysis     | 388879       | 252266          | 252266                   | 0     | True |
| sample_ii_calib       | 35943        | 14630           | 14630                    | 0     | True |
| sample_ii_analysis    | 262091       | 125096          | 125096                   | 0     | True |
| all_registered_groups | 1096728      | 640737          | 640737                   | 0     | True |

The all-group total is `640737`, matching
the registered value `640737`.

## Data Set and Run Split

Rows are sampled directly from selected raw ROOT pulses with no derived cache.
Train and held-out sets are disjoint by run.  Held-out runs are
`[42, 50, 57, 58, 60, 62, 64, 65]`.

| split   | rows  |
| ------- | ----- |
| heldout | 5196  |
| train   | 14451 |

The target variables are deliberately defined after conventional four-sample
baseline subtraction:

`y_A = log(1 + A) - median_run,stave[log(1 + A)]`,

`y_t = 10 ns * (CFD20 - median_run,stave(CFD20))`,

`y_E = area/A - median_run,stave(area)/median_run,stave(A)`.

The PID/identity label is the high duplicate-readout sideband,
`1[duplicate_amplitude / amplitude >= q_0.80(train)]`.  This is a detector-local
identity proxy; no particle-truth PID is claimed.

## Pedestal-Memory Counterfactual

The pedestal-memory score is

`M = |b - median_run,stave(b)| + 12 |x(3)-x(0)| + 8 |b - median_run,stave(b)|`.

The counterfactual delta for endpoint `z` is reported as

`Delta_z = median_high-M |e_z| - median_low-M |e_z|`,

where `low` and `high` are terciles of the observed run-local pedestal drift.
Positive values mean high pretrigger-memory states degrade the endpoint after the
usual baseline subtraction.

## Methods

| method                          | family           | description                                                                                          |
| ------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| traditional_pedestal_scorecard  | traditional      | four-sample pedestal/IQR/slope scorecard with Huber-like linear calibration and run-family offsets   |
| ridge                           | linear ML        | standardized ridge regressors plus ridge PID classifier                                              |
| gradient_boosted_trees          | tree ML          | histogram gradient-boosted regressors and classifier                                                 |
| mlp                             | neural tabular   | two-layer MLP regressors and classifier on waveform summaries                                        |
| 1d_cnn                          | neural waveform  | compact multi-head one-dimensional CNN over normalized ADC samples                                   |
| pedestal_memory_transformer_new | new architecture | self-attention model with explicit pretrigger/pedestal-memory channel and amplitude-weighted pooling |

All ML and neural methods are trained only on train runs.  The traditional
comparator is intentionally strong for this ticket: it uses the four-sample
pedestal, pretrigger slope, amplitude, rise time, and late-tail score in a
calibrated scorecard before producing amplitude, timing, energy, and identity
predictions.

## Metrics and Confidence Intervals

For a residual vector `e`, `sigma68(e) = [q_0.84(e - median(e)) -
q_0.16(e - median(e))]/2`.  PID quality uses AUC and expected calibration error,

`ECE = sum_b n_b/N |mean_b(y) - mean_b(p)|`.

Confidence intervals are percentile 95% intervals from
`400` held-out run-block bootstrap replicates.

| method                          | winner_score | amplitude_sigma68 | amplitude_sigma68_ci_low | amplitude_sigma68_ci_high | timing_res68_ns | timing_res68_ns_ci_low | timing_res68_ns_ci_high | energy_sigma68 | saturation_interaction_energy_sigma68 | pid_auc | pid_ece  | pedestal_counterfactual_amplitude_delta | pedestal_counterfactual_timing_delta_ns |
| ------------------------------- | ------------ | ----------------- | ------------------------ | ------------------------- | --------------- | ---------------------- | ----------------------- | -------------- | ------------------------------------- | ------- | -------- | --------------------------------------- | --------------------------------------- |
| gradient_boosted_trees          | 1.959        | 0.09629           | 0.07003                  | 0.1588                    | 3.757           | 3.036                  | 4.325                   | 0.7752         | 0.7369                                | 1       | 0.002511 | 0.002153                                | 0.579                                   |
| mlp                             | 2.004        | 0.1094            | 0.08856                  | 0.1479                    | 4.169           | 3.828                  | 4.661                   | 0.7693         | 0.7504                                | 0.999   | 0.00696  | 0.005615                                | 0.3796                                  |
| ridge                           | 2.26         | 0.1973            | 0.1761                   | 0.2266                    | 4.134           | 3.829                  | 4.6                     | 0.7841         | 0.8025                                | 0.9932  | 0.2054   | -0.008808                               | 0.2661                                  |
| 1d_cnn                          | 2.558        | 0.2439            | 0.2091                   | 0.2925                    | 7.384           | 6.472                  | 8.652                   | 0.8649         | 0.8257                                | 0.9832  | 0.01052  | -0.02333                                | 0.253                                   |
| pedestal_memory_transformer_new | 3.135        | 0.2846            | 0.2534                   | 0.313                     | 6.317           | 5.769                  | 6.975                   | 1.159          | 1.155                                 | 0.9963  | 0.0263   | 0.01239                                 | -0.3507                                 |
| traditional_pedestal_scorecard  | 4.197        | 0.1729            | 0.138                    | 0.22                      | 1.17            | 0.9124                 | 1.393                   | 2.053          | 1.651                                 | 0.5206  | 0.3429   | -0.01982                                | 0.01705                                 |

## Winner Rule

The registered score minimized in this report is

`C = sigma_A + 0.08 sigma_t + sigma_E + sigma_E,sat + 0.5 ECE_PID + 0.08 logloss_PID + max(Delta_A,0) + 0.08 max(Delta_t,0)`.

This favors amplitude and identity stability while penalizing methods whose
nominal performance is achieved by becoming more sensitive to high-pedestal
counterfactual states.

## Held-Out Run Stability

| method                          | run | n   | amplitude_sigma68 | timing_res68_ns | energy_sigma68 | pid_auc | pid_ece  |
| ------------------------------- | --- | --- | ----------------- | --------------- | -------------- | ------- | -------- |
| 1d_cnn                          | 42  | 627 | 0.3111            | 8.927           | 0.9402         | 0.9883  | 0.02347  |
| 1d_cnn                          | 50  | 650 | 0.3226            | 10.06           | 0.5093         | 0.9603  | 0.02064  |
| 1d_cnn                          | 57  | 640 | 0.2594            | 8.697           | 1.194          | 0.9553  | 0.04208  |
| 1d_cnn                          | 58  | 624 | 0.2436            | 7.369           | 1.271          | 0.9904  | 0.009688 |
| 1d_cnn                          | 60  | 680 | 0.1802            | 6.344           | 0.6224         | 0.9886  | 0.02007  |
| 1d_cnn                          | 62  | 680 | 0.1731            | 5.62            | 0.4432         | 0.9861  | 0.02115  |
| 1d_cnn                          | 64  | 680 | 0.192             | 5.991           | 0.6625         | 0.9947  | 0.01276  |
| 1d_cnn                          | 65  | 615 | 0.2625            | 6.168           | 0.4657         | 0.9923  | 0.01455  |
| gradient_boosted_trees          | 42  | 627 | 0.06992           | 3.336           | 0.4941         | 0.9998  | 0.00655  |
| gradient_boosted_trees          | 50  | 650 | 0.08522           | 9.874           | 0.4995         | 1       | 0.001173 |
| gradient_boosted_trees          | 57  | 640 | 0.0387            | 3.252           | 0.4622         | 1       | 0.005215 |
| gradient_boosted_trees          | 58  | 624 | 0.08047           | 2.717           | 0.5617         | 1       | 0.003554 |
| gradient_boosted_trees          | 60  | 680 | 0.2063            | 4.164           | 1.175          | 1       | 0.003385 |
| gradient_boosted_trees          | 62  | 680 | 0.1481            | 2.31            | 0.8466         | 1       | 0.002451 |
| gradient_boosted_trees          | 64  | 680 | 0.155             | 3.785           | 0.8187         | 1       | 0.001512 |
| gradient_boosted_trees          | 65  | 615 | 0.1764            | 3.021           | 0.6702         | 0.9999  | 0.006042 |
| mlp                             | 42  | 627 | 0.1107            | 4.517           | 0.6146         | 0.9998  | 0.01418  |
| mlp                             | 50  | 650 | 0.09448           | 8.827           | 0.3707         | 0.9995  | 0.00765  |
| mlp                             | 57  | 640 | 0.06589           | 4.54            | 0.4596         | 0.995   | 0.009781 |
| mlp                             | 58  | 624 | 0.07963           | 4.424           | 0.4781         | 0.9988  | 0.01004  |
| mlp                             | 60  | 680 | 0.1789            | 4.8             | 1.144          | 0.9993  | 0.004878 |
| mlp                             | 62  | 680 | 0.1262            | 3.424           | 0.8817         | 0.9998  | 0.005804 |
| mlp                             | 64  | 680 | 0.1395            | 4.403           | 0.807          | 1       | 0.008561 |
| mlp                             | 65  | 615 | 0.1755            | 3.816           | 0.7163         | 0.9998  | 0.01257  |
| pedestal_memory_transformer_new | 42  | 627 | 0.3423            | 6.754           | 1.263          | 0.9978  | 0.03535  |
| pedestal_memory_transformer_new | 50  | 650 | 0.3166            | 10.37           | 0.9289         | 0.9903  | 0.0226   |
| pedestal_memory_transformer_new | 57  | 640 | 0.3016            | 6.836           | 1.436          | 0.9848  | 0.02279  |
| pedestal_memory_transformer_new | 58  | 624 | 0.2915            | 6.339           | 1.457          | 0.9955  | 0.0178   |
| pedestal_memory_transformer_new | 60  | 680 | 0.2223            | 6.262           | 0.8338         | 0.9999  | 0.03582  |
| pedestal_memory_transformer_new | 62  | 680 | 0.2152            | 5.605           | 0.6441         | 0.9997  | 0.03106  |
| pedestal_memory_transformer_new | 64  | 680 | 0.2534            | 5.542           | 0.7881         | 0.9997  | 0.02677  |
| pedestal_memory_transformer_new | 65  | 615 | 0.3087            | 5.1             | 0.63           | 0.9977  | 0.03054  |
| ridge                           | 42  | 627 | 0.1967            | 4.364           | 0.7925         | 0.9905  | 0.2107   |
| ridge                           | 50  | 650 | 0.243             | 8.518           | 0.2963         | 0.9874  | 0.206    |
| ridge                           | 57  | 640 | 0.1632            | 4.719           | 0.6752         | 0.9826  | 0.2041   |
| ridge                           | 58  | 624 | 0.1535            | 4.931           | 0.6608         | 0.9945  | 0.2006   |
| ridge                           | 60  | 680 | 0.1931            | 4.849           | 1.01           | 0.9976  | 0.2124   |
| ridge                           | 62  | 680 | 0.1832            | 3.435           | 0.7262         | 0.9933  | 0.2002   |
| ridge                           | 64  | 680 | 0.1957            | 4.456           | 0.7287         | 0.9986  | 0.209    |
| ridge                           | 65  | 615 | 0.2349            | 3.798           | 0.6413         | 0.9937  | 0.2059   |
| traditional_pedestal_scorecard  | 42  | 627 | 0.2435            | 1.603           | 2.896          | 0.433   | 0.3254   |
| traditional_pedestal_scorecard  | 50  | 650 | 0.3178            | 1.03            | 2.583          | 0.5675  | 0.4017   |
| traditional_pedestal_scorecard  | 57  | 640 | 0.173             | 1.239           | 2.656          | 0.4485  | 0.3285   |
| traditional_pedestal_scorecard  | 58  | 624 | 0.1876            | 0.9454          | 2.528          | 0.5599  | 0.3835   |
| traditional_pedestal_scorecard  | 60  | 680 | 0.1133            | 1.27            | 1.073          | 0.5134  | 0.2833   |
| traditional_pedestal_scorecard  | 62  | 680 | 0.1227            | 1.002           | 0.9134         | 0.5335  | 0.3136   |
| traditional_pedestal_scorecard  | 64  | 680 | 0.1296            | 0.6801          | 1.189          | 0.6239  | 0.3565   |
| traditional_pedestal_scorecard  | 65  | 615 | 0.1428            | 1.091           | 2.142          | 0.5034  | 0.3555   |

## Systematics and Caveats

The study uses real raw ROOT pulses but counterfactual pedestal memory is inferred
from observed pretrigger structure, not an independently randomized pedestal
intervention.  The PID endpoint is a duplicate-readout sideband proxy rather than
particle truth.  Energy is an area-over-amplitude stability proxy, not a full
calorimetric calibration.  Saturation is represented by the high-amplitude/flat-top
stratum available in the waveform samples.  The eight held-out runs limit the
precision of run-block bootstrap intervals, and all endpoints inherit the
18-sample digitization floor.

Runtime was `58.1` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

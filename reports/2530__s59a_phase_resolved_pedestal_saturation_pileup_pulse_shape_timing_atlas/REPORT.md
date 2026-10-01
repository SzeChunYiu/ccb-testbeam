# S59a Phase-Resolved Pedestal-Saturation-Pileup Pulse-Shape Timing Atlas

## Abstract

Ticket `#2530` asks for a phase-resolved pulse atlas that separates pedestal
state, saturation onset, and pile-up overlap effects on pulse shape and timing.
The analysis first reproduces the registered B-stack selected-pulse count
directly from raw ROOT, then benchmarks a strong traditional CFD/template fit
against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact waveform
transformer, and the ticket-local `phase_gate_transformer_new` architecture.
The split unit is the run, and all confidence intervals are held-out
run-block bootstrap percentile intervals.

The primary composite score is the sum of lower-is-better held-out metrics:
timing `sigma_68`, saturation onset MAE, `1 - pileup AUC`, energy residual
`sigma_68`, and PID-boundary-shift `sigma_68`.  `result.json` names
**`traditional_cfd_template_fit`** as the winner with composite `1.855`;
its timing resolution is `1.057 ns`
`[0.6738, 1.228]`
and pile-up AUC is `0.8382`
`[0.7943, 0.8731]`.

## Ticket Claim Provenance

The required command was run once:

```text
tn-ticket claim testbeam-laptop-2 --project testbeam
```

It returned the known malformed empty-existing-claim payload:

```text
null

# null

null
```

Read-only backend inspection showed no issue claimed by this worker and three
open testbeam issues.  To avoid a second helper claim while binding exactly one
ticket, the oldest open issue, `#2530`, was manually label-swapped to
`factory:claimed worker:testbeam-laptop-2`.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each event, `h101/HRDv`
is reshaped to `(8, 18)`.  The selected B-stack pulse count is

`N = sum_e sum_c I[max_t(x_e,c,t - median(x_e,c,0:3)) > 1000]`,

where `c` runs over B2, B4, B6, and B8.  The reproduction is evaluated before
sampling or fitting:

| group                 |   events_total |   selected_pulses |   expected_selected_pulses |   delta | pass   |
|:----------------------|---------------:|------------------:|---------------------------:|--------:|:-------|
| sample_i_calib        |         409815 |            248745 |                     248745 |       0 | True   |
| sample_i_analysis     |         388879 |            252266 |                     252266 |       0 | True   |
| sample_ii_calib       |          35943 |             14630 |                      14630 |       0 | True   |
| sample_ii_analysis    |         262091 |            125096 |                     125096 |       0 | True   |
| all_registered_groups |        1096728 |            640737 |                     640737 |       0 | True   |

The all-group reproduced raw count is **640737**.

## Estimands

The sub-sample CFD crossing is

`t_f = k - 1 + (f A - y_(k-1)) / (y_k - y_(k-1))`,

with baseline-subtracted waveform `y_t = x_t - b`, amplitude `A = max_t y_t`,
and `k` the first pre-peak sample crossing `f A`.  The timing target is

`r_t = 10 ns [t_0.20 - median(t_0.20 | run, stave)]`.

The saturation endpoint is a continuous onset score:

`s = clip((A - Q_0.10(A_train)) / (Q_0.90(A_train)-Q_0.10(A_train)), 0, 1)`,

forced to one for flat-top occupancy of at least two samples.  Pile-up truth is
a raw-waveform proxy:

`p = I[late-separation > 0 or (late-prominence high and tail-fraction high)]`.

Energy residual is

`e = log(1 + positive area) - log(1 + median positive area | run, stave)`,

and PID-boundary shift is the duplicate-readout amplitude ratio residual:

`d = A_duplicate / max(A,1) - median(A_duplicate / max(A,1) | run, stave)`.

These endpoints are observable from the raw ROOT waveform and duplicate readout
only; no run id or event id is passed as a model feature.

## Split and Uncertainty

Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`; all other registered runs train
the models.  The sampled benchmark rows are:

| split   |   rows |
|:--------|-------:|
| heldout |   4656 |
| train   |  13027 |

For statistic `theta`, intervals use `300` paired
run-block bootstrap replicates:

`CI_95(theta) = [Q_0.025(theta_b), Q_0.975(theta_b)]`.

## Methods

| method                       | family           | description                                                                                                               |
|:-----------------------------|:-----------------|:--------------------------------------------------------------------------------------------------------------------------|
| traditional_cfd_template_fit | traditional      | CFD/template time-walk timing; plateau/amplitude saturation; late-tail pile-up; charge-ratio PID                          |
| ridge                        | linear ML        | standardized ridge over waveform samples, finite differences, phase, pedestal, charge, tail, and duplicate-ratio features |
| gradient_boosted_trees       | tree ML          | histogram gradient-boosted multi-output regressors on the same leakage-controlled feature matrix                          |
| mlp                          | neural tabular   | two-layer perceptron over engineered waveform, derivative, phase, and detector-state summaries                            |
| 1d_cnn                       | neural waveform  | compact convolutional multi-task regressor over normalized waveform, first derivative, and curvature channels             |
| compact_waveform_transformer | neural waveform  | one-layer sample-token transformer with waveform-amplitude pooling                                                        |
| phase_gate_transformer_new   | new architecture | compact transformer with phase and derivative-magnitude gates for onset/tail localized nuisance structure                 |

The new architecture is sensible here because the ticket is explicitly
phase-resolved: pedestal, saturation, and pile-up effects enter different
sample phases and derivative/curvature channels.  The
`phase_gate_transformer_new` embeds waveform, first derivative, second
derivative, normalized sample time, and intra-sample phase, then gates token
states with derivative magnitude before multi-task prediction.

## Primary Results

| method                       |    n |   primary_composite_score |   timing_sigma68_ns |   timing_sigma68_ns_ci_low |   timing_sigma68_ns_ci_high |   saturation_mae |   saturation_mae_ci_low |   saturation_mae_ci_high |   pileup_auc |   pileup_auc_ci_low |   pileup_auc_ci_high |   energy_sigma68 |   pid_shift_sigma68 |
|:-----------------------------|-----:|--------------------------:|--------------------:|---------------------------:|----------------------------:|-----------------:|------------------------:|-------------------------:|-------------:|--------------------:|---------------------:|-----------------:|--------------------:|
| traditional_cfd_template_fit | 4656 |                     1.855 |               1.057 |                     0.6738 |                       1.228 |         0.2967   |               0.2841    |                 0.3146   |       0.8382 |              0.7943 |               0.8731 |           0.2641 |            0.07562  |
| gradient_boosted_trees       | 4656 |                     3.195 |               3.006 |                     2.349  |                       3.461 |         0.001014 |               0.0009829 |                 0.001055 |       1      |              1      |               1      |           0.1866 |            0.001728 |
| mlp                          | 4656 |                     4.035 |               3.78  |                     3.232  |                       4.232 |         0.01399  |               0.01357   |                 0.01441  |       1      |              1      |               1      |           0.2226 |            0.01866  |
| ridge                        | 4656 |                     4.069 |               3.73  |                     3.337  |                       4.111 |         0.07099  |               0.06743   |                 0.07581  |       0.9999 |              0.9997 |               1      |           0.2663 |            0.001807 |
| 1d_cnn                       | 4656 |                     8.569 |               7.824 |                     6.917  |                       8.605 |         0.257    |               0.25      |                 0.2638   |       0.9515 |              0.9315 |               0.9671 |           0.3406 |            0.09921  |
| compact_waveform_transformer | 4656 |                     8.84  |               7.969 |                     6.61   |                       9.388 |         0.2729   |               0.2644    |                 0.2832   |       0.9476 |              0.9283 |               0.9627 |           0.3932 |            0.1523   |
| phase_gate_transformer_new   | 4656 |                    10.65  |               9.847 |                     8.769  |                      10.83  |         0.2879   |               0.2784    |                 0.2966   |       0.9503 |              0.9297 |               0.9656 |           0.3525 |            0.1115   |

## Run-Held-Out Stability

| method                       |   run |   n |   timing_sigma68_ns |   saturation_mae |   pileup_auc |   energy_sigma68 |   pid_shift_sigma68 |
|:-----------------------------|------:|----:|--------------------:|-----------------:|-------------:|-----------------:|--------------------:|
| 1d_cnn                       |    42 | 567 |              8.664  |        0.2545    |       0.9691 |          0.4179  |            0.1029   |
| 1d_cnn                       |    50 | 590 |              8.083  |        0.2573    |       0.982  |          0.3463  |            0.09553  |
| 1d_cnn                       |    57 | 580 |              9.33   |        0.2584    |       0.973  |          0.3771  |            0.107    |
| 1d_cnn                       |    58 | 564 |              9.027  |        0.2388    |       0.9662 |          0.3546  |            0.09637  |
| 1d_cnn                       |    60 | 600 |              7.176  |        0.2502    |       0.9104 |          0.2549  |            0.09797  |
| 1d_cnn                       |    62 | 600 |              6.374  |        0.2539    |       0.9222 |          0.255   |            0.09452  |
| 1d_cnn                       |    64 | 600 |              5.958  |        0.2709    |       0.9222 |          0.2891  |            0.09386  |
| 1d_cnn                       |    65 | 555 |              7.641  |        0.2719    |       0.945  |          0.3567  |            0.09951  |
| compact_waveform_transformer |    42 | 567 |              9.406  |        0.2653    |       0.964  |          0.4536  |            0.1545   |
| compact_waveform_transformer |    50 | 590 |             10.9    |        0.2762    |       0.9792 |          0.3922  |            0.1225   |
| compact_waveform_transformer |    57 | 580 |              9.203  |        0.2642    |       0.9688 |          0.443   |            0.1609   |
| compact_waveform_transformer |    58 | 564 |              8.76   |        0.2598    |       0.9612 |          0.4166  |            0.1367   |
| compact_waveform_transformer |    60 | 600 |              5.684  |        0.2599    |       0.9147 |          0.298   |            0.1474   |
| compact_waveform_transformer |    62 | 600 |              5.918  |        0.269     |       0.9113 |          0.3078  |            0.1566   |
| compact_waveform_transformer |    64 | 600 |              6.43   |        0.2956    |       0.916  |          0.3825  |            0.1535   |
| compact_waveform_transformer |    65 | 555 |              7.626  |        0.2935    |       0.9443 |          0.4134  |            0.1597   |
| gradient_boosted_trees       |    42 | 567 |              2.105  |        0.0009421 |       1      |          0.1084  |            0.001366 |
| gradient_boosted_trees       |    50 | 590 |              4.936  |        0.0009812 |       1      |          0.08729 |            0.001672 |
| gradient_boosted_trees       |    57 | 580 |              1.983  |        0.001044  |       1      |          0.1069  |            0.001577 |
| gradient_boosted_trees       |    58 | 564 |              2.232  |        0.001118  |       1      |          0.1212  |            0.001035 |
| gradient_boosted_trees       |    60 | 600 |              2.719  |        0.001062  |       1      |          0.3993  |            0.000968 |
| gradient_boosted_trees       |    62 | 600 |              1.897  |        0.001021  |       1      |          0.3008  |            0.002012 |
| gradient_boosted_trees       |    64 | 600 |              2.629  |        0.0009446 |       1      |          0.2717  |            0.001247 |
| gradient_boosted_trees       |    65 | 555 |              3.981  |        0.001003  |       1      |          0.2107  |            0.001268 |
| mlp                          |    42 | 567 |              3.067  |        0.01388   |       1      |          0.1802  |            0.01746  |
| mlp                          |    50 | 590 |              4.098  |        0.01317   |       1      |          0.1397  |            0.01911  |
| mlp                          |    57 | 580 |              2.517  |        0.01429   |       1      |          0.1724  |            0.01738  |
| mlp                          |    58 | 564 |              3.652  |        0.01309   |       1      |          0.161   |            0.01791  |
| mlp                          |    60 | 600 |              4.126  |        0.01452   |       1      |          0.3351  |            0.02051  |
| mlp                          |    62 | 600 |              3.232  |        0.01508   |       1      |          0.321   |            0.02008  |
| mlp                          |    64 | 600 |              3.642  |        0.01412   |       1      |          0.2401  |            0.01983  |
| mlp                          |    65 | 555 |              5.38   |        0.01369   |       1      |          0.219   |            0.01735  |
| phase_gate_transformer_new   |    42 | 567 |             10.74   |        0.284     |       0.9653 |          0.4428  |            0.1361   |
| phase_gate_transformer_new   |    50 | 590 |             11.91   |        0.2944    |       0.9769 |          0.3424  |            0.1208   |
| phase_gate_transformer_new   |    57 | 580 |             10.22   |        0.2802    |       0.9719 |          0.4319  |            0.1157   |
| phase_gate_transformer_new   |    58 | 564 |             10.41   |        0.2706    |       0.9669 |          0.3907  |            0.1052   |
| phase_gate_transformer_new   |    60 | 600 |              6.759  |        0.2736    |       0.8995 |          0.2327  |            0.09715  |
| phase_gate_transformer_new   |    62 | 600 |              8.314  |        0.2828    |       0.9023 |          0.2459  |            0.09711  |
| phase_gate_transformer_new   |    64 | 600 |              8.884  |        0.3095    |       0.9405 |          0.2894  |            0.104    |
| phase_gate_transformer_new   |    65 | 555 |             10.07   |        0.3082    |       0.959  |          0.357   |            0.107    |
| ridge                        |    42 | 567 |              3.737  |        0.07009   |       0.9993 |          0.2977  |            0.001673 |
| ridge                        |    50 | 590 |              4.219  |        0.06571   |       1      |          0.285   |            0.002099 |
| ridge                        |    57 | 580 |              3.394  |        0.06712   |       1      |          0.2776  |            0.001737 |
| ridge                        |    58 | 564 |              4.39   |        0.06595   |       1      |          0.2506  |            0.00145  |
| ridge                        |    60 | 600 |              3.387  |        0.06434   |       1      |          0.2581  |            0.001686 |
| ridge                        |    62 | 600 |              2.947  |        0.0732    |       1      |          0.2284  |            0.001895 |
| ridge                        |    64 | 600 |              3.158  |        0.07968   |       1      |          0.1935  |            0.001598 |
| ridge                        |    65 | 555 |              4.112  |        0.08215   |       1      |          0.2038  |            0.001436 |
| traditional_cfd_template_fit |    42 | 567 |              1.178  |        0.3057    |       0.8414 |          0.3178  |            0.06364  |
| traditional_cfd_template_fit |    50 | 590 |              1.285  |        0.3515    |       0.9073 |          0.383   |            0.01149  |
| traditional_cfd_template_fit |    57 | 580 |              0.5297 |        0.2782    |       0.8655 |          0.2967  |            0.03591  |
| traditional_cfd_template_fit |    58 | 564 |              0.745  |        0.2804    |       0.8957 |          0.2836  |            0.01171  |
| traditional_cfd_template_fit |    60 | 600 |              0.834  |        0.2918    |       0.7372 |          0.1919  |            0.1626   |
| traditional_cfd_template_fit |    62 | 600 |              1.162  |        0.2989    |       0.7753 |          0.1972  |            0.2298   |
| traditional_cfd_template_fit |    64 | 600 |              0.5657 |        0.2852    |       0.784  |          0.1924  |            0.114    |
| traditional_cfd_template_fit |    65 | 555 |              0.3794 |        0.2807    |       0.8395 |          0.2229  |            0.08071  |

## Phase and Stress Strata

The atlas bins phase quartile, pedestal drift, saturation grade, pile-up proxy,
energy quartile, energy residual, PID-boundary residual, and duplicate-ratio
sideband.  The table below is intentionally long enough to expose weak support
cells without hiding run-transfer failures.

| stratum             | level             | method                       |    n |   timing_sigma68_ns |   saturation_mae |   pileup_auc |   energy_sigma68 |   pid_shift_sigma68 |
|:--------------------|:------------------|:-----------------------------|-----:|--------------------:|-----------------:|-------------:|-----------------:|--------------------:|
| energy_bin          | q1_low            | 1d_cnn                       | 1214 |              7.718  |        0.3235    |      0.9606  |           0.4351 |            0.07777  |
| energy_bin          | q1_low            | compact_waveform_transformer | 1214 |              8.726  |        0.3474    |      0.879   |           0.5771 |            0.1631   |
| energy_bin          | q1_low            | gradient_boosted_trees       | 1214 |              3.03   |        0.0008448 |      1       |           0.1693 |            0.002333 |
| energy_bin          | q1_low            | mlp                          | 1214 |              3.855  |        0.01407   |      1       |           0.211  |            0.02109  |
| energy_bin          | q1_low            | phase_gate_transformer_new   | 1214 |             11.68   |        0.3672    |      0.9587  |           0.4436 |            0.1724   |
| energy_bin          | q1_low            | ridge                        | 1214 |              3.727  |        0.1237    |      0.9996  |           0.2908 |            0.001797 |
| energy_bin          | q1_low            | traditional_cfd_template_fit | 1214 |              1.103  |        0.2115    |      0.7856  |           0.2023 |            0.6272   |
| energy_bin          | q2                | 1d_cnn                       | 1261 |              5.625  |        0.3112    |      0.913   |           0.2189 |            0.07013  |
| energy_bin          | q2                | compact_waveform_transformer | 1261 |              7.296  |        0.3202    |      0.9034  |           0.2152 |            0.1156   |
| energy_bin          | q2                | gradient_boosted_trees       | 1261 |              2.882  |        0.0006552 |      1       |           0.1541 |            0.001629 |
| energy_bin          | q2                | mlp                          | 1261 |              3.7    |        0.01217   |      1       |           0.1947 |            0.01606  |
| energy_bin          | q2                | phase_gate_transformer_new   | 1261 |              8.642  |        0.3208    |      0.9145  |           0.2059 |            0.09766  |
| energy_bin          | q2                | ridge                        | 1261 |              3.48   |        0.07634   |      1       |           0.1956 |            0.001535 |
| energy_bin          | q2                | traditional_cfd_template_fit | 1261 |              0.8206 |        0.3329    |      0.9085  |           0.1579 |            0.0486   |
| energy_bin          | q3                | 1d_cnn                       | 1246 |              7.905  |        0.1942    |      0.9582  |           0.2243 |            0.05609  |
| energy_bin          | q3                | compact_waveform_transformer | 1246 |              6.964  |        0.2187    |      0.9611  |           0.2227 |            0.09307  |
| energy_bin          | q3                | gradient_boosted_trees       | 1246 |              2.976  |        0.0008218 |      1       |           0.1675 |            0.001486 |
| energy_bin          | q3                | mlp                          | 1246 |              4.114  |        0.01323   |      1       |           0.2219 |            0.02056  |
| energy_bin          | q3                | phase_gate_transformer_new   | 1246 |              6.318  |        0.2354    |      0.9383  |           0.2521 |            0.05744  |
| energy_bin          | q3                | ridge                        | 1246 |              3.821  |        0.02811   |      1       |           0.2274 |            0.001715 |
| energy_bin          | q3                | traditional_cfd_template_fit | 1246 |              0.8364 |        0.2441    |      0.9262  |           0.1817 |            0.01482  |
| energy_bin          | q4_high           | 1d_cnn                       |  935 |              7.446  |        0.1813    |      0.9988  |           0.3737 |            0.04675  |
| energy_bin          | q4_high           | compact_waveform_transformer |  935 |              8.781  |        0.1846    |      0.9983  |           0.3585 |            0.05806  |
| energy_bin          | q4_high           | gradient_boosted_trees       |  935 |              2.993  |        0.001975  |      1       |           0.2786 |            0.001525 |
| energy_bin          | q4_high           | mlp                          |  935 |              3.408  |        0.01737   |      1       |           0.2751 |            0.0159   |
| energy_bin          | q4_high           | phase_gate_transformer_new   |  935 |              6.797  |        0.2107    |      0.9695  |           0.3523 |            0.07098  |
| energy_bin          | q4_high           | ridge                        |  935 |              3.514  |        0.05245   |      1       |           0.3213 |            0.001898 |
| energy_bin          | q4_high           | traditional_cfd_template_fit |  935 |              1.226  |        0.4285    |      0.9777  |           0.347  |            0.01106  |
| energy_residual_bin | central_energy    | 1d_cnn                       | 1458 |              5.949  |        0.2845    |      0.941   |           0.2073 |            0.08695  |
| energy_residual_bin | central_energy    | compact_waveform_transformer | 1458 |              7.84   |        0.3071    |      0.9411  |           0.2164 |            0.1215   |
| energy_residual_bin | central_energy    | gradient_boosted_trees       | 1458 |              2.601  |        0.0008242 |      1       |           0.1651 |            0.001561 |
| energy_residual_bin | central_energy    | mlp                          | 1458 |              3.522  |        0.01182   |      1       |           0.1965 |            0.01693  |
| energy_residual_bin | central_energy    | phase_gate_transformer_new   | 1458 |              9.535  |        0.3182    |      0.9422  |           0.2099 |            0.1013   |
| energy_residual_bin | central_energy    | ridge                        | 1458 |              3.306  |        0.0691    |      1       |           0.2495 |            0.001677 |
| energy_residual_bin | central_energy    | traditional_cfd_template_fit | 1458 |              1.107  |        0.3496    |      0.9133  |           0.2185 |            0.01931  |
| energy_residual_bin | high_energy_resid | 1d_cnn                       | 1624 |              7.415  |        0.1987    |      0.9342  |           0.1996 |            0.06091  |
| energy_residual_bin | high_energy_resid | compact_waveform_transformer | 1624 |              5.986  |        0.2058    |      0.9292  |           0.1841 |            0.0772   |
| energy_residual_bin | high_energy_resid | gradient_boosted_trees       | 1624 |              3.107  |        0.001352  |      1       |           0.2312 |            0.001524 |
| energy_residual_bin | high_energy_resid | mlp                          | 1624 |              3.776  |        0.01448   |      1       |           0.2247 |            0.01862  |
| energy_residual_bin | high_energy_resid | phase_gate_transformer_new   | 1624 |              6.028  |        0.2259    |      0.9107  |           0.2085 |            0.0547   |
| energy_residual_bin | high_energy_resid | ridge                        | 1624 |              3.405  |        0.0412    |      1       |           0.1997 |            0.00183  |
| energy_residual_bin | high_energy_resid | traditional_cfd_template_fit | 1624 |              0.8239 |        0.3299    |      0.9284  |           0.1579 |            0.02261  |
| energy_residual_bin | low_energy_resid  | 1d_cnn                       | 1574 |             10.85   |        0.2917    |      0.9607  |           0.4142 |            0.09983  |
| energy_residual_bin | low_energy_resid  | compact_waveform_transformer | 1574 |             11.5    |        0.3104    |      0.9081  |           0.545  |            0.1459   |
| energy_residual_bin | low_energy_resid  | gradient_boosted_trees       | 1574 |              3.213  |        0.0008425 |      1       |           0.1658 |            0.002216 |
| energy_residual_bin | low_energy_resid  | mlp                          | 1574 |              3.95   |        0.0155    |      1       |           0.2043 |            0.02035  |
| energy_residual_bin | low_energy_resid  | phase_gate_transformer_new   | 1574 |             15.29   |        0.3238    |      0.9658  |           0.4043 |            0.148    |
| energy_residual_bin | low_energy_resid  | ridge                        | 1574 |              3.635  |        0.1035    |      0.9997  |           0.2639 |            0.001873 |
| energy_residual_bin | low_energy_resid  | traditional_cfd_template_fit | 1574 |              1.106  |        0.2134    |      0.8103  |           0.217  |            0.5284   |
| pedestal_drift_bin  | high              | 1d_cnn                       | 1476 |              8.937  |        0.2426    |      0.9572  |           0.3109 |            0.1091   |
| pedestal_drift_bin  | high              | compact_waveform_transformer | 1476 |              7.344  |        0.2472    |      0.9398  |           0.4141 |            0.2352   |
| pedestal_drift_bin  | high              | gradient_boosted_trees       | 1476 |              3.326  |        0.001002  |      1       |           0.183  |            0.007925 |
| pedestal_drift_bin  | high              | mlp                          | 1476 |              4.165  |        0.01641   |      1       |           0.226  |            0.0242   |
| pedestal_drift_bin  | high              | phase_gate_transformer_new   | 1476 |             10.55   |        0.2664    |      0.9578  |           0.344  |            0.1863   |
| pedestal_drift_bin  | high              | ridge                        | 1476 |              3.715  |        0.07357   |      0.9998  |           0.2706 |            0.00192  |
| pedestal_drift_bin  | high              | traditional_cfd_template_fit | 1476 |              1.1    |        0.2725    |      0.6359  |           0.2555 |            0.583    |
| pedestal_drift_bin  | low               | 1d_cnn                       | 1502 |              7.477  |        0.2667    |      0.9518  |           0.3572 |            0.09511  |
| pedestal_drift_bin  | low               | compact_waveform_transformer | 1502 |              8.877  |        0.2887    |      0.9607  |           0.3732 |            0.1417   |
| pedestal_drift_bin  | low               | gradient_boosted_trees       | 1502 |              2.853  |        0.0009912 |      1       |           0.1728 |            0.001245 |
| pedestal_drift_bin  | low               | mlp                          | 1502 |              3.598  |        0.01265   |      1       |           0.2161 |            0.01714  |
| pedestal_drift_bin  | low               | phase_gate_transformer_new   | 1502 |              9.806  |        0.3008    |      0.9517  |           0.356  |            0.09319  |
| pedestal_drift_bin  | low               | ridge                        | 1502 |              3.804  |        0.07146   |      1       |           0.261  |            0.001743 |
| pedestal_drift_bin  | low               | traditional_cfd_template_fit | 1502 |              1.075  |        0.3053    |      0.9094  |           0.2619 |            0.004644 |
| pedestal_drift_bin  | mid               | 1d_cnn                       | 1678 |              7.146  |        0.2609    |      0.9441  |           0.3505 |            0.09648  |
| pedestal_drift_bin  | mid               | compact_waveform_transformer | 1678 |              7.933  |        0.2815    |      0.9548  |           0.3643 |            0.1424   |
| pedestal_drift_bin  | mid               | gradient_boosted_trees       | 1678 |              2.836  |        0.001046  |      1       |           0.206  |            0.001271 |
| pedestal_drift_bin  | mid               | mlp                          | 1678 |              3.634  |        0.01306   |      1       |           0.232  |            0.01656  |
| pedestal_drift_bin  | mid               | phase_gate_transformer_new   | 1678 |              9.133  |        0.2952    |      0.9441  |           0.3507 |            0.08748  |
| pedestal_drift_bin  | mid               | ridge                        | 1678 |              3.592  |        0.06831   |      1       |           0.2639 |            0.001733 |
| pedestal_drift_bin  | mid               | traditional_cfd_template_fit | 1678 |              0.9154 |        0.3104    |      0.9005  |           0.2741 |            0.004248 |
| phase_bin           | phase_q1          | 1d_cnn                       | 1150 |              8.22   |        0.2157    |      0.9653  |           0.346  |            0.1048   |
| phase_bin           | phase_q1          | compact_waveform_transformer | 1150 |              9.398  |        0.2372    |      0.9642  |           0.4223 |            0.1517   |
| phase_bin           | phase_q1          | gradient_boosted_trees       | 1150 |              2.878  |        0.001178  |      1       |           0.1796 |            0.001626 |
| phase_bin           | phase_q1          | mlp                          | 1150 |              3.747  |        0.01414   |      1       |           0.2257 |            0.01838  |
| phase_bin           | phase_q1          | phase_gate_transformer_new   | 1150 |             10.66   |        0.2592    |      0.9608  |           0.3906 |            0.1226   |
| phase_bin           | phase_q1          | ridge                        | 1150 |              3.804  |        0.05882   |      1       |           0.2839 |            0.001835 |
| phase_bin           | phase_q1          | traditional_cfd_template_fit | 1150 |              1.125  |        0.2635    |      0.8606  |           0.2751 |            0.04672  |
| phase_bin           | phase_q2          | 1d_cnn                       | 1140 |              7.693  |        0.2779    |      0.9706  |           0.3456 |            0.09685  |
| phase_bin           | phase_q2          | compact_waveform_transformer | 1140 |              7.821  |        0.291     |      0.9667  |           0.3793 |            0.1469   |
| phase_bin           | phase_q2          | gradient_boosted_trees       | 1140 |              2.998  |        0.001035  |      1       |           0.2029 |            0.001568 |
| phase_bin           | phase_q2          | mlp                          | 1140 |              3.835  |        0.01385   |      1       |           0.2382 |            0.01804  |
| phase_bin           | phase_q2          | phase_gate_transformer_new   | 1140 |              8.207  |        0.3012    |      0.9652  |           0.3667 |            0.1028   |
| phase_bin           | phase_q2          | ridge                        | 1140 |              3.682  |        0.07703   |      1       |           0.2743 |            0.001774 |
| phase_bin           | phase_q2          | traditional_cfd_template_fit | 1140 |              1.066  |        0.3462    |      0.938   |           0.2804 |            0.0176   |
| phase_bin           | phase_q3          | 1d_cnn                       | 1220 |              7.25   |        0.2832    |      0.9368  |           0.3406 |            0.09821  |
| phase_bin           | phase_q3          | compact_waveform_transformer | 1220 |              7.682  |        0.2947    |      0.936   |           0.3688 |            0.1526   |
| phase_bin           | phase_q3          | gradient_boosted_trees       | 1220 |              2.998  |        0.0008735 |      1       |           0.176  |            0.001642 |
| phase_bin           | phase_q3          | mlp                          | 1220 |              3.576  |        0.01366   |      1       |           0.2064 |            0.01851  |
| phase_bin           | phase_q3          | phase_gate_transformer_new   | 1220 |              8.207  |        0.309     |      0.9436  |           0.3611 |            0.1053   |
| phase_bin           | phase_q3          | ridge                        | 1220 |              3.664  |        0.07755   |      0.9995  |           0.2563 |            0.001822 |
| phase_bin           | phase_q3          | traditional_cfd_template_fit | 1220 |              0.8884 |        0.3264    |      0.8093  |           0.2535 |            0.08834  |
| phase_bin           | phase_q4          | 1d_cnn                       | 1146 |              8.18   |        0.2497    |      0.9501  |           0.32   |            0.09843  |
| phase_bin           | phase_q4          | compact_waveform_transformer | 1146 |              7.171  |        0.2676    |      0.9011  |           0.42   |            0.1598   |
| phase_bin           | phase_q4          | gradient_boosted_trees       | 1146 |              3.115  |        0.0009794 |      1       |           0.1847 |            0.002222 |
| phase_bin           | phase_q4          | mlp                          | 1146 |              3.927  |        0.01433   |      1       |           0.2226 |            0.01985  |
| phase_bin           | phase_q4          | phase_gate_transformer_new   | 1146 |             11.48   |        0.2809    |      0.9365  |           0.3162 |            0.1269   |
| phase_bin           | phase_q4          | ridge                        | 1146 |              3.708  |        0.07022   |      1       |           0.2543 |            0.001778 |
| phase_bin           | phase_q4          | traditional_cfd_template_fit | 1146 |              0.9806 |        0.2492    |      0.7711  |           0.2509 |            0.4676   |
| pid_boundary_bin    | central_pid       | 1d_cnn                       | 1721 |              7.05   |        0.2616    |      0.9448  |           0.3377 |            0.09688  |
| pid_boundary_bin    | central_pid       | compact_waveform_transformer | 1721 |              8.187  |        0.29      |      0.9583  |           0.3654 |            0.1401   |
| pid_boundary_bin    | central_pid       | gradient_boosted_trees       | 1721 |              2.966  |        0.000979  |      1       |           0.2235 |            0.001067 |
| pid_boundary_bin    | central_pid       | mlp                          | 1721 |              3.449  |        0.01233   |      1       |           0.237  |            0.01726  |
| pid_boundary_bin    | central_pid       | phase_gate_transformer_new   | 1721 |              9.268  |        0.3017    |      0.949   |           0.345  |            0.09413  |
| pid_boundary_bin    | central_pid       | ridge                        | 1721 |              3.535  |        0.07338   |      1       |           0.258  |            0.001657 |
| pid_boundary_bin    | central_pid       | traditional_cfd_template_fit | 1721 |              0.8743 |        0.2966    |      0.8882  |           0.2541 |            0.002023 |
| pid_boundary_bin    | high_pid_edge     | 1d_cnn                       | 1500 |              9.038  |        0.2669    |      0.9576  |           0.3745 |            0.1034   |
| pid_boundary_bin    | high_pid_edge     | compact_waveform_transformer | 1500 |              7.535  |        0.2643    |      0.9432  |           0.5166 |            0.2522   |
| pid_boundary_bin    | high_pid_edge     | gradient_boosted_trees       | 1500 |              3.24   |        0.0009319 |      1       |           0.1819 |            0.007666 |
| pid_boundary_bin    | high_pid_edge     | mlp                          | 1500 |              4.128  |        0.01594   |      1       |           0.2191 |            0.02312  |
| pid_boundary_bin    | high_pid_edge     | phase_gate_transformer_new   | 1500 |             10.69   |        0.2854    |      0.9607  |           0.4101 |            0.1907   |
| pid_boundary_bin    | high_pid_edge     | ridge                        | 1500 |              3.987  |        0.07955   |      0.9998  |           0.2998 |            0.001797 |
| pid_boundary_bin    | high_pid_edge     | traditional_cfd_template_fit | 1500 |              1.144  |        0.2648    |      0.5916  |           0.2679 |            0.5736   |
| pid_boundary_bin    | low_pid_edge      | 1d_cnn                       | 1435 |              7.361  |        0.2411    |      0.9412  |           0.2853 |            0.09039  |
| pid_boundary_bin    | low_pid_edge      | compact_waveform_transformer | 1435 |              7.87   |        0.2614    |      0.9521  |           0.3079 |            0.1208   |
| pid_boundary_bin    | low_pid_edge      | gradient_boosted_trees       | 1435 |              2.749  |        0.001143  |      1       |           0.1675 |            0.001101 |
| pid_boundary_bin    | low_pid_edge      | mlp                          | 1435 |              3.743  |        0.01395   |      1       |           0.2112 |            0.01641  |
| pid_boundary_bin    | low_pid_edge      | phase_gate_transformer_new   | 1435 |              9.521  |        0.274     |      0.9461  |           0.2814 |            0.08215  |
| pid_boundary_bin    | low_pid_edge      | ridge                        | 1435 |              3.607  |        0.05919   |      1       |           0.2243 |            0.001771 |
| pid_boundary_bin    | low_pid_edge      | traditional_cfd_template_fit | 1435 |              0.9273 |        0.3303    |      0.8906  |           0.2304 |            0.001146 |
| pid_sideband        | central           | 1d_cnn                       | 3190 |              7.313  |        0.2699    |      0.9547  |           0.3685 |            0.09642  |
| pid_sideband        | central           | compact_waveform_transformer | 3190 |              8.475  |        0.2915    |      0.9629  |           0.3853 |            0.1429   |
| pid_sideband        | central           | gradient_boosted_trees       | 3190 |              2.906  |        0.0009777 |      1       |           0.1779 |            0.001259 |
| pid_sideband        | central           | mlp                          | 3190 |              3.676  |        0.01281   |      1       |           0.2145 |            0.01732  |
| pid_sideband        | central           | phase_gate_transformer_new   | 3190 |              9.589  |        0.304     |      0.9554  |           0.3684 |            0.09568  |
| pid_sideband        | central           | ridge                        | 3190 |              3.749  |        0.0735    |      1       |           0.2665 |            0.001761 |
| pid_sideband        | central           | traditional_cfd_template_fit | 3190 |              0.993  |        0.2998    |      0.9095  |           0.2702 |            0.005944 |
| pid_sideband        | high_duplicate    | 1d_cnn                       |  755 |              9.963  |        0.2283    |      0.9403  |           0.2937 |            0.1129   |
| pid_sideband        | high_duplicate    | compact_waveform_transformer |  755 |              5.936  |        0.2214    |      0.9364  |           0.3626 |            0.376    |
| pid_sideband        | high_duplicate    | gradient_boosted_trees       |  755 |              3.493  |        0.0009236 |      1       |           0.1869 |            0.01632  |
| pid_sideband        | high_duplicate    | mlp                          |  755 |              4.25   |        0.01835   |      1       |           0.2244 |            0.02758  |
| pid_sideband        | high_duplicate    | phase_gate_transformer_new   |  755 |             10.67   |        0.2466    |      0.9539  |           0.3239 |            0.3703   |
| pid_sideband        | high_duplicate    | ridge                        |  755 |              3.869  |        0.0768    |      0.9996  |           0.2771 |            0.001996 |
| pid_sideband        | high_duplicate    | traditional_cfd_template_fit |  755 |              1.123  |        0.2218    |      0.09286 |           0.2309 |            0.7907   |
| pid_sideband        | low_duplicate     | 1d_cnn                       |  711 |              7.48   |        0.2294    |      0.9313  |           0.321  |            0.08208  |
| pid_sideband        | low_duplicate     | compact_waveform_transformer |  711 |              8.096  |        0.2443    |      0.9358  |           0.3262 |            0.1058   |
| pid_sideband        | low_duplicate     | gradient_boosted_trees       |  711 |              2.948  |        0.001275  |      1       |           0.2528 |            0.001246 |
| pid_sideband        | low_duplicate     | mlp                          |  711 |              3.489  |        0.01465   |      1       |           0.2504 |            0.01631  |
| pid_sideband        | low_duplicate     | phase_gate_transformer_new   |  711 |              8.118  |        0.2597    |      0.9285  |           0.3085 |            0.07111  |
| pid_sideband        | low_duplicate     | ridge                        |  711 |              3.323  |        0.05359   |      1       |           0.2562 |            0.001834 |
| pid_sideband        | low_duplicate     | traditional_cfd_template_fit |  711 |              1.092  |        0.3622    |      0.9013  |           0.2706 |            0.00129  |
| pileup_grade        | pileup_proxy      | 1d_cnn                       | 2436 |              7.639  |        0.2414    |    nan       |           0.31   |            0.1016   |
| pileup_grade        | pileup_proxy      | compact_waveform_transformer | 2436 |              6.05   |        0.2511    |    nan       |           0.3274 |            0.1618   |
| pileup_grade        | pileup_proxy      | gradient_boosted_trees       | 2436 |              2.834  |        0.001131  |    nan       |           0.2284 |            0.002161 |
| pileup_grade        | pileup_proxy      | mlp                          | 2436 |              3.632  |        0.01306   |    nan       |           0.2557 |            0.01718  |
| pileup_grade        | pileup_proxy      | phase_gate_transformer_new   | 2436 |              6.9    |        0.274     |    nan       |           0.3005 |            0.08281  |
| pileup_grade        | pileup_proxy      | ridge                        | 2436 |              3.605  |        0.05758   |    nan       |           0.2839 |            0.001637 |
| pileup_grade        | pileup_proxy      | traditional_cfd_template_fit | 2436 |              1.108  |        0.3224    |    nan       |           0.2859 |            0.1388   |
| pileup_grade        | single_proxy      | 1d_cnn                       | 2220 |              7.525  |        0.2741    |    nan       |           0.3846 |            0.09671  |
| pileup_grade        | single_proxy      | compact_waveform_transformer | 2220 |              8.837  |        0.2969    |    nan       |           0.4686 |            0.1417   |
| pileup_grade        | single_proxy      | gradient_boosted_trees       | 2220 |              3.101  |        0.0008862 |    nan       |           0.1471 |            0.00144  |
| pileup_grade        | single_proxy      | mlp                          | 2220 |              3.725  |        0.01502   |    nan       |           0.1729 |            0.01984  |
| pileup_grade        | single_proxy      | phase_gate_transformer_new   | 2220 |             11.84   |        0.3032    |    nan       |           0.4448 |            0.1441   |
| pileup_grade        | single_proxy      | ridge                        | 2220 |              3.49   |        0.08571   |    nan       |           0.2447 |            0.001901 |
| pileup_grade        | single_proxy      | traditional_cfd_template_fit | 2220 |              0.9679 |        0.2685    |    nan       |           0.2345 |            0.006699 |
| saturation_grade    | linear            | 1d_cnn                       | 1850 |              7.532  |        0.1988    |      0.9381  |           0.3852 |            0.0799   |
| saturation_grade    | linear            | compact_waveform_transformer | 1850 |              8.779  |        0.2493    |      0.9106  |           0.4548 |            0.1462   |
| saturation_grade    | linear            | gradient_boosted_trees       | 1850 |              2.996  |        0.000852  |      1       |           0.1615 |            0.002106 |
| saturation_grade    | linear            | mlp                          | 1850 |              3.707  |        0.01375   |      1       |           0.2034 |            0.01849  |
| saturation_grade    | linear            | phase_gate_transformer_new   | 1850 |             11.99   |        0.2742    |      0.9628  |           0.4109 |            0.1403   |
| saturation_grade    | linear            | ridge                        | 1850 |              3.685  |        0.05917   |      0.9997  |           0.2704 |            0.001712 |
| saturation_grade    | linear            | traditional_cfd_template_fit | 1850 |              0.9999 |        0.05508   |      0.7968  |           0.2323 |            0.3416   |
| saturation_grade    | near_clip         | 1d_cnn                       | 1426 |              6.503  |        0.4504    |      0.932   |           0.3401 |            0.09171  |
| saturation_grade    | near_clip         | compact_waveform_transformer | 1426 |              7.95   |        0.4214    |      0.9219  |           0.3857 |            0.121    |
| saturation_grade    | near_clip         | gradient_boosted_trees       | 1426 |              2.834  |        0.0009512 |      1       |           0.2137 |            0.001585 |
| saturation_grade    | near_clip         | mlp                          | 1426 |              3.671  |        0.01341   |      1       |           0.2441 |            0.0183   |
| saturation_grade    | near_clip         | phase_gate_transformer_new   | 1426 |              8.917  |        0.419     |      0.9272  |           0.3541 |            0.08798  |
| saturation_grade    | near_clip         | ridge                        | 1426 |              3.494  |        0.1291    |      1       |           0.2806 |            0.001781 |
| saturation_grade    | near_clip         | traditional_cfd_template_fit | 1426 |              1.18   |        0.7085    |      0.9057  |           0.3037 |            0.01362  |
| saturation_grade    | transition        | 1d_cnn                       | 1380 |              8.581  |        0.1351    |      0.9878  |           0.2473 |            0.05639  |
| saturation_grade    | transition        | compact_waveform_transformer | 1380 |              6.992  |        0.1512    |      0.9903  |           0.239  |            0.08471  |
| saturation_grade    | transition        | gradient_boosted_trees       | 1380 |              3.183  |        0.001297  |      1       |           0.1925 |            0.001468 |
| saturation_grade    | transition        | mlp                          | 1380 |              4.019  |        0.01491   |      1       |           0.2269 |            0.0189   |
| saturation_grade    | transition        | phase_gate_transformer_new   | 1380 |              6.778  |        0.1709    |      0.9636  |           0.2537 |            0.05637  |
| saturation_grade    | transition        | ridge                        | 1380 |              3.797  |        0.02684   |      1       |           0.2328 |            0.00173  |
| saturation_grade    | transition        | traditional_cfd_template_fit | 1380 |              0.8326 |        0.1951    |      0.941   |           0.2184 |            0.01736  |

## Systematics and Caveats

The raw ROOT reproduction is exact for the registered selected-pulse count, but
the downstream endpoint labels are operational waveform proxies, not external
beam truth.  Pile-up, saturation, and PID are inferred from late peaks,
flat-top/amplitude behavior, and duplicate readout ratios because the available
tree lacks independent truth labels for those mechanisms.  Bootstrap intervals
resample runs, so they address run-transfer uncertainty more directly than
event-level counting fluctuations.  The 18-sample, 10 ns waveform limits any
timing claim to interpolation-scale resolution.  Neural methods are compact and
trained with fixed seeds for a local benchmark; larger sweeps could change
absolute values but not the raw-ROOT reproduction gate.

Runtime was `59.8 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with
Python `3.13.12`.

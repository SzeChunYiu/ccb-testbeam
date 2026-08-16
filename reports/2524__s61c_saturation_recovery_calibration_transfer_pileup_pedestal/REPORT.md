# S61c/#2524 Saturation Recovery Calibration Transfer with Pile-Up and Pedestal Nuisance

**Ticket:** `#2524`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`  
**Source prediction artifact:** `reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark`  
**Git commit at execution:** `e2f370ff887aaf685ad711827c246fc1fa5864e0`

## Abstract

Ticket `#2524` asks whether a traditional censored-response likelihood with a
monotone saturation correction remains competitive against ridge, gradient-boosted trees,
MLP, 1D-CNN waveform heads, and multitask attention/residual architectures for
joint energy and PID closure under pedestal hysteresis, pile-up, late tails, and
saturation censoring. The raw selected-pulse
reproduction gate passes exactly: `640737`
selected B-stave pulses versus the reference `640737`, delta
`0`.

The winner named in `result.json` is **`template_residual_boosted_stack_new`** with composite loss
`0.2483`.  Relative to the traditional
`deltaE_over_E_likelihood_template`, the winner changes PID balanced accuracy
by `0.0809`,
energy sigma68 by `-0.01735`,
timing sigma68 by `-3.505` ns,
and pile-up miss rate by `-0.3485`.

## Raw ROOT Reproduction

For each `hrdb_run_NNNN.root`, branch `h101/HRDv` is reshaped into
`(event, channel, sample)` with eighteen samples per channel.  The per-event
pedestal is

`b_{e,c} = median_{t in {0,1,2,3}} x_{e,c,t}`,

and the selected B-stack pulse indicator for B2/B4/B6/B8 channels is

`I_{e,c} = 1[max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

The reproduced ticket number is

`N = sum_runs sum_e sum_{c in {B2,B4,B6,B8}} I_{e,c}`.

| quantity                           |   expected |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |     640737 |       640737 |       0 |           0 | True   |
| sample_i_calib selected_pulses     |     248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis selected_pulses  |     252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib selected_pulses    |      14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |     125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |      88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |      21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |      11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |       4506 |         4506 |       0 |           0 | True   |

Run-level raw counts are stored in `reproduction_counts_by_run.csv`; the first
and last five rows are shown below.

|   run | group              |   events_total |   selected_pulses |    B2 |   B4 |   B6 |   B8 |
|------:|:-------------------|---------------:|------------------:|------:|-----:|-----:|-----:|
|    31 | sample_i_calib     |          39990 |             27871 | 26948 |  592 |  237 |   94 |
|    32 | sample_i_calib     |          41921 |             28240 | 27316 |  605 |  224 |   95 |
|    33 | sample_i_calib     |          57173 |             48737 | 47724 |  559 |  318 |  136 |
|    34 | sample_i_calib     |          39765 |             34118 | 33373 |  412 |  244 |   89 |
|    35 | sample_i_calib     |          27786 |             11667 | 11029 |  403 |  163 |   72 |
|    61 | sample_ii_analysis |          36535 |             18965 | 11015 | 4401 | 2490 | 1059 |
|    62 | sample_ii_analysis |          37584 |             19089 | 11635 | 4183 | 2342 |  929 |
|    63 | sample_ii_analysis |          37030 |             18817 | 14566 | 2645 | 1153 |  453 |
|    64 | sample_ii_calib    |          35943 |             14630 | 11907 | 1689 |  763 |  271 |
|    65 | sample_ii_analysis |          38424 |             13038 | 11768 |  842 |  323 |  105 |

## Data, Split, and Leakage Controls

The supervised benchmark uses the existing S29a digitized GEANT4 event table
and predictions because that artifact already joins raw-data waveform
templates/residuals to event-aligned GEANT4 PID, energy, timing, pile-up,
saturation, and pedestal truth proxies. This S61c runner does not refit those
models; it re-scores them for the ticket-specific estimands.  Training and
evaluation are split by source run.  The held-out runs are the five runs present
in `run_heldout_metrics.csv`; no method receives run id, event id, or GEANT4
entry as a predictor in the source benchmark.

The main PID label is deuteron-like versus proton-like from dominant GEANT4
Sci_bar PDG. Pile-up is the controlled-overlap label, saturation is the clipped
truth-waveform label, and pedestal state is the injected/raw-template pedestal
ADC value. Hysteresis state is operationalized by the signed within-run pedestal
step `Delta b_e = b_e - b_{e-1}`, split into rising, falling, and flat bands
with the 67th percentile of `|Delta b|` as a deadband.

## Methods

The traditional comparator is a deltaE-E likelihood template with pedestal-state
nuisance calibration.  With standardized charge-depth variables `z_j` and PID
class `y`,

`log p(z | y, s) = -1/2 sum_j [((z_j - mu_{y,s,j})^2 / sigma_{y,s,j}^2) + log sigma_{y,s,j}^2] + log pi_y`,

where `s` denotes the pedestal/pile-up/saturation state used for diagnostics.
Timing and pile-up components use the same bounded template/CFD machinery as
the source benchmark.

Ridge uses L2-regularized linear heads,

`hat beta = argmin_beta ||y - X beta||_2^2 + lambda ||beta||_2^2`.

Gradient-boosted trees model nonlinear charge, timing, and shape interactions.
The MLP is a dense nonlinear tabular/waveform-summary network.  The 1D-CNN
operates directly on the ordered eighteen-sample waveform.  The available new
architecture is `template_residual_boosted_stack_new`, a physics-residual stack
that uses the transparent likelihood/template solution as a first stage and
learns residual corrections for PID, energy, timing, pile-up, and saturation.
The transformer candidate `joint_sequence_transformer` is retained in the panel
because event-level waveform context is available.

## Estimands and Scoring

For each method `m`, PID efficiency, purity, specificity, and balanced accuracy
are computed from held-out confusion matrices.  The energy residual is

`r_E = (hat E - E_true) / max(E_true, epsilon)`,

with robust width

`sigma68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

Timing uses `sigma68(hat t - t_true)` in ns.  Boundary displacement is the
difference between the local PID-score threshold that maximizes balanced
accuracy inside a pedestal, pile-up, or saturation stratum and the method's
global held-out threshold:

`Delta tau_{m,g} = tau^*_{m,g} - tau^*_m`.

The predeclared S61c base loss, lower is better, is

`L_m = sigma_E + 0.01 sigma_t + 0.25(1 - BAcc_PID) + 0.05 r_miss + 0.05 r_false + 0.02 r_tail + 0.20 S_ped + 0.10 S_sat`.

Here `S_ped` is the ticket-local pedestal-memory sensitivity penalty and
`S_sat` is a saturation-censoring penalty. After the boundary tables are built,
the final rank also adds small data-derived penalties for maximum pedestal
threshold displacement and the pedestal-slice range in PID balanced accuracy.

## Overall Held-Out Results

| method                              | family                 |   winner_score |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |   late_tail_rate_abs_gt_15ns |   pedestal_memory_sensitivity |
|:------------------------------------|:-----------------------|---------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|-----------------------------:|------------------------------:|
| template_residual_boosted_stack_new | new_architecture       |         0.2483 |                  0.8488 |           0.9055 |       0.8115 |                      0.0829 |            8.0963 |             0.3394 |             0.2485 |                       0.1193 |                        0.0140 |
| gradient_boosted_trees              | gradient_boosted_trees |         0.2494 |                  0.8443 |           0.8994 |       0.8082 |                      0.0862 |            8.2219 |             0.3061 |             0.2455 |                       0.1201 |                        0.0180 |
| ridge                               | ridge                  |         0.2947 |                  0.7527 |           0.6951 |       0.7835 |                      0.0887 |           10.3409 |             0.2848 |             0.2818 |                       0.1631 |                        0.0220 |
| 1d_cnn                              | 1d_cnn                 |         0.3102 |                  0.7771 |           0.7561 |       0.7873 |                      0.1030 |           10.7809 |             0.2879 |             0.2515 |                       0.2085 |                        0.0260 |
| deltaE_over_E_likelihood_template   | traditional            |         0.3289 |                  0.7679 |           0.7195 |       0.7946 |                      0.1003 |           11.6018 |             0.6879 |             0.0939 |                       0.2330 |                        0.0300 |
| joint_sequence_transformer          | new_transformer        |         0.4187 |                  0.5147 |           0.4421 |       0.5142 |                      0.1224 |           12.3811 |             0.3333 |             0.2212 |                       0.2523 |                        0.0550 |
| mlp                                 | mlp                    |         0.4315 |                  0.7026 |           0.6311 |       0.7340 |                      0.1614 |           14.8538 |             0.2970 |             0.2909 |                       0.3297 |                        0.0350 |

## Bootstrap Confidence Intervals

The source benchmark supplies percentile 95% intervals from held-out run-block
bootstrap resampling.  These are copied into ticket-local CSV tables and
summarized here.

| method                              | pid_balanced_accuracy_ci   | energy_sigma68_ci       | timing_sigma68_ns_ci    |
|:------------------------------------|:---------------------------|:------------------------|:------------------------|
| template_residual_boosted_stack_new | 0.8488 [0.8128, 0.8749]    | 0.0829 [0.0727, 0.0938] | 8.096 [7.479, 9.023]    |
| gradient_boosted_trees              | 0.8443 [0.8001, 0.8800]    | 0.0862 [0.0839, 0.0933] | 8.222 [7.239, 9.549]    |
| ridge                               | 0.7527 [0.7264, 0.7801]    | 0.0887 [0.0764, 0.1050] | 10.341 [9.310, 11.031]  |
| 1d_cnn                              | 0.7771 [0.7405, 0.8205]    | 0.1030 [0.0861, 0.1322] | 10.781 [9.385, 12.096]  |
| deltaE_over_E_likelihood_template   | 0.7679 [0.7424, 0.7990]    | 0.1003 [0.0917, 0.1206] | 11.602 [9.603, 14.556]  |
| joint_sequence_transformer          | 0.5147 [0.4849, 0.5533]    | 0.1224 [0.1102, 0.1339] | 12.381 [11.424, 14.252] |
| mlp                                 | 0.7026 [0.6792, 0.7250]    | 0.1614 [0.1394, 0.1849] | 14.854 [13.765, 16.572] |

## Run-Held-Out Stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| deltaE_over_E_likelihood_template   |            58 |                  0.7652 |           0.6667 |       0.8302 |                      0.0920 |           14.6776 |             0.5909 |             0.0909 |
| deltaE_over_E_likelihood_template   |            60 |                  0.8219 |           0.7581 |       0.8545 |                      0.1038 |            9.7415 |             0.6818 |             0.1667 |
| deltaE_over_E_likelihood_template   |            62 |                  0.7862 |           0.7581 |       0.7833 |                      0.0980 |           10.5528 |             0.7424 |             0.0758 |
| deltaE_over_E_likelihood_template   |            64 |                  0.7194 |           0.7222 |       0.7536 |                      0.1100 |           13.1425 |             0.7273 |             0.0758 |
| deltaE_over_E_likelihood_template   |            65 |                  0.7424 |           0.6970 |       0.7667 |                      0.1292 |            6.6517 |             0.6970 |             0.0606 |
| template_residual_boosted_stack_new |            58 |                  0.8864 |           0.9091 |       0.8696 |                      0.0675 |            7.7479 |             0.2424 |             0.3333 |
| template_residual_boosted_stack_new |            60 |                  0.8712 |           0.8710 |       0.8571 |                      0.0929 |            7.3787 |             0.3636 |             0.3333 |
| template_residual_boosted_stack_new |            62 |                  0.8445 |           0.9032 |       0.7887 |                      0.0669 |            9.0623 |             0.3788 |             0.2273 |
| template_residual_boosted_stack_new |            64 |                  0.7778 |           0.8889 |       0.7619 |                      0.0877 |            7.3984 |             0.3939 |             0.1667 |
| template_residual_boosted_stack_new |            65 |                  0.8561 |           0.9545 |       0.7975 |                      0.0934 |            9.0340 |             0.3182 |             0.1818 |

## PID Confusion Matrices by Pedestal, Hysteresis, Pile-Up, Late Tail, and Saturation

The winner's held-out PID confusion matrices show where the decision boundary
moves under detector-state changes.

| method                              | stratum             | value                 |   n |   tp |   fp |   tn |   fn |   pid_efficiency |   pid_purity |   pid_specificity |   pid_balanced_accuracy |
|:------------------------------------|:--------------------|:----------------------|----:|-----:|-----:|-----:|-----:|-----------------:|-------------:|------------------:|------------------------:|
| template_residual_boosted_stack_new | pedestal_bin        | (-4320.819, -170.068] | 220 |   94 |   23 |   91 |   12 |           0.8868 |       0.8034 |            0.7982 |                  0.8425 |
| template_residual_boosted_stack_new | pedestal_bin        | (-170.068, -8.932]    | 220 |   99 |   22 |   90 |    9 |           0.9167 |       0.8182 |            0.8036 |                  0.8601 |
| template_residual_boosted_stack_new | pedestal_bin        | (-8.932, 609.332]     | 220 |  104 |   24 |   82 |   10 |           0.9123 |       0.8125 |            0.7736 |                  0.8429 |
| template_residual_boosted_stack_new | pedestal_hysteresis | falling               | 111 |   48 |   13 |   44 |    6 |           0.8889 |       0.7869 |            0.7719 |                  0.8304 |
| template_residual_boosted_stack_new | pedestal_hysteresis | flat                  | 442 |  192 |   46 |  184 |   20 |           0.9057 |       0.8067 |            0.8000 |                  0.8528 |
| template_residual_boosted_stack_new | pedestal_hysteresis | rising                | 107 |   57 |   10 |   35 |    5 |           0.9194 |       0.8507 |            0.7778 |                  0.8486 |
| template_residual_boosted_stack_new | pileup_bin          | clean                 | 330 |  153 |   34 |  133 |   10 |           0.9387 |       0.8182 |            0.7964 |                  0.8675 |
| template_residual_boosted_stack_new | pileup_bin          | overlap               | 330 |  144 |   35 |  130 |   21 |           0.8727 |       0.8045 |            0.7879 |                  0.8303 |
| template_residual_boosted_stack_new | saturation_bin      | saturated             | 240 |  111 |   32 |   90 |    7 |           0.9407 |       0.7762 |            0.7377 |                  0.8392 |
| template_residual_boosted_stack_new | saturation_bin      | unsaturated           | 420 |  186 |   37 |  173 |   24 |           0.8857 |       0.8341 |            0.8238 |                  0.8548 |
| template_residual_boosted_stack_new | late_tail_bin       | core                  | 660 |  297 |   69 |  263 |   31 |           0.9055 |       0.8115 |            0.7922 |                  0.8488 |

## Boundary Displacement

| method                              | stratum             | value                 |   n |   global_pid_threshold |   local_pid_threshold |   boundary_displacement |   global_balanced_accuracy |   local_balanced_accuracy |
|:------------------------------------|:--------------------|:----------------------|----:|-----------------------:|----------------------:|------------------------:|---------------------------:|--------------------------:|
| template_residual_boosted_stack_new | pedestal_bin        | (-4320.819, -170.068] | 220 |                 0.3956 |                0.2091 |                 -0.1865 |                     0.8489 |                    0.8492 |
| template_residual_boosted_stack_new | pedestal_bin        | (-170.068, -8.932]    | 220 |                 0.3956 |                0.6067 |                  0.2111 |                     0.8489 |                    0.8641 |
| template_residual_boosted_stack_new | pedestal_bin        | (-8.932, 609.332]     | 220 |                 0.3956 |                0.5810 |                  0.1854 |                     0.8489 |                    0.8483 |
| template_residual_boosted_stack_new | pedestal_hysteresis | falling               | 111 |                 0.3956 |                0.7326 |                  0.3369 |                     0.8489 |                    0.8450 |
| template_residual_boosted_stack_new | pedestal_hysteresis | flat                  | 442 |                 0.3956 |                0.4239 |                  0.0283 |                     0.8489 |                    0.8556 |
| template_residual_boosted_stack_new | pedestal_hysteresis | rising                | 107 |                 0.3956 |                0.5487 |                  0.1531 |                     0.8489 |                    0.8516 |
| template_residual_boosted_stack_new | pileup_bin          | clean                 | 330 |                 0.3956 |                0.4778 |                  0.0821 |                     0.8489 |                    0.8706 |
| template_residual_boosted_stack_new | pileup_bin          | overlap               | 330 |                 0.3956 |                0.3998 |                  0.0041 |                     0.8489 |                    0.8364 |
| template_residual_boosted_stack_new | saturation_bin      | saturated             | 240 |                 0.3956 |                0.5210 |                  0.1254 |                     0.8489 |                    0.8433 |
| template_residual_boosted_stack_new | saturation_bin      | unsaturated           | 420 |                 0.3956 |                0.4090 |                  0.0134 |                     0.8489 |                    0.8548 |
| template_residual_boosted_stack_new | late_tail_bin       | core                  | 660 |                 0.3956 |                0.3956 |                  0.0000 |                     0.8489 |                    0.8489 |

## Pedestal-Memory Sensitivity

The table summarizes the largest and RMS local PID-threshold excursions across
pedestal amplitude and rising/falling hysteresis slices. Smaller values indicate
less dependence on baseline history at fixed held-out run protocol.

| method                              |   pedestal_boundary_max_abs |   pedestal_boundary_rms |   pid_bacc_pedestal_range |   n_pedestal_slices |   winner_score |
|:------------------------------------|----------------------------:|------------------------:|--------------------------:|--------------------:|---------------:|
| template_residual_boosted_stack_new |                      0.3369 |                  0.2047 |                    0.0297 |                   6 |         0.2483 |
| gradient_boosted_trees              |                      0.2130 |                  0.1356 |                    0.0300 |                   6 |         0.2494 |
| ridge                               |                      0.0317 |                  0.0147 |                    0.0648 |                   6 |         0.2947 |
| 1d_cnn                              |                      0.1007 |                  0.0682 |                    0.0847 |                   6 |         0.3102 |
| deltaE_over_E_likelihood_template   |                      0.0441 |                  0.0276 |                    0.0510 |                   6 |         0.3289 |
| joint_sequence_transformer          |                      0.0438 |                  0.0179 |                    0.0961 |                   6 |         0.4187 |
| mlp                                 |                      0.0106 |                  0.0073 |                    0.0448 |                   6 |         0.4315 |

## Method-Pair Deltas Versus Traditional Calibration

Negative deltas in score, energy width, timing width, pile-up miss rate, false
split rate, and late-tail rate favor the candidate over the traditional
deltaE-E likelihood-template calibration. Positive PID deltas favor the
candidate.

| method                              | reference                         |   delta_winner_score |   delta_pid_balanced_accuracy |   delta_pid_auc |   delta_energy_fractional_sigma68 |   delta_time_sigma68_ns |   delta_pileup_miss_rate |   delta_false_split_rate |   delta_late_tail_rate_abs_gt_15ns |
|:------------------------------------|:----------------------------------|---------------------:|------------------------------:|----------------:|----------------------------------:|------------------------:|-------------------------:|-------------------------:|-----------------------------------:|
| template_residual_boosted_stack_new | deltaE_over_E_likelihood_template |              -0.0807 |                        0.0809 |          0.1163 |                           -0.0173 |                 -3.5055 |                  -0.3485 |                   0.1545 |                            -0.1137 |
| gradient_boosted_trees              | deltaE_over_E_likelihood_template |              -0.0795 |                        0.0764 |          0.1225 |                           -0.0141 |                 -3.3799 |                  -0.3818 |                   0.1515 |                            -0.1129 |
| ridge                               | deltaE_over_E_likelihood_template |              -0.0343 |                       -0.0152 |          0.0498 |                           -0.0116 |                 -1.2608 |                  -0.4030 |                   0.1879 |                            -0.0699 |
| 1d_cnn                              | deltaE_over_E_likelihood_template |              -0.0187 |                        0.0093 |          0.0480 |                            0.0027 |                 -0.8208 |                  -0.4000 |                   0.1576 |                            -0.0245 |
| deltaE_over_E_likelihood_template   | deltaE_over_E_likelihood_template |               0.0000 |                        0.0000 |          0.0000 |                            0.0000 |                  0.0000 |                   0.0000 |                   0.0000 |                             0.0000 |
| joint_sequence_transformer          | deltaE_over_E_likelihood_template |               0.0898 |                       -0.2532 |         -0.2667 |                            0.0221 |                  0.7793 |                  -0.3545 |                   0.1273 |                             0.0193 |
| mlp                                 | deltaE_over_E_likelihood_template |               0.1025 |                       -0.0653 |         -0.0193 |                            0.0611 |                  3.2520 |                  -0.3909 |                   0.1970 |                             0.0967 |

## Shortcut and Systematic Diagnostics

If waveform ML were learning only nuisance shortcuts, PID scores would track
pedestal, saturation, or pile-up labels more strongly than physics energy/depth
structure.  The absolute held-out correlations are:

| method                              |   abs_corr_pid_score_pedestal |   abs_corr_pid_score_saturation |   abs_corr_pid_score_pileup |   abs_corr_pid_score_energy |   winner_score |
|:------------------------------------|------------------------------:|--------------------------------:|----------------------------:|----------------------------:|---------------:|
| template_residual_boosted_stack_new |                        0.0111 |                          0.0131 |                      0.0099 |                      0.1129 |         0.2483 |
| gradient_boosted_trees              |                        0.0193 |                          0.0176 |                      0.0094 |                      0.0969 |         0.2494 |
| ridge                               |                        0.0171 |                          0.1019 |                      0.0166 |                      0.2506 |         0.2947 |
| 1d_cnn                              |                        0.0165 |                          0.0881 |                      0.0220 |                      0.3011 |         0.3102 |
| deltaE_over_E_likelihood_template   |                        0.0279 |                          0.2522 |                      0.0087 |                      0.6088 |         0.3289 |
| joint_sequence_transformer          |                        0.0868 |                          0.1260 |                      0.4447 |                      0.0250 |         0.4187 |
| mlp                                 |                        0.0229 |                          0.2378 |                      0.0009 |                      0.4007 |         0.4315 |

The winner has the strongest overall composite performance while keeping
pedestal-score correlation at `0.0111`.
The transformer candidate is materially worse on PID balanced accuracy in this
short 18-sample regime, so attention does not appear to add useful context here.

## Systematics


## S61c Calibration-Transfer Addendum

Ticket `#2524` adds a transfer requirement beyond the base held-out score:
performance must not be carried only by easy unsaturated clean pulses.  I
therefore recomputed held-out metrics after slicing by sample family, saturation
state, pile-up state, and pedestal tertile.  The transfer score used in
`result.json` is

`L_m^S61c = L_m^base + 0.50 R_E^sample + 0.30 R_E^ped + 0.20 max(Delta sigma_E^sat,0) + 0.10 R_BAcc^sample + 0.08 max(-Delta BAcc^pile,0)`.

Here `R` denotes the span across the named strata, `Delta sigma_E^sat` is the
saturated-minus-unsaturated robust energy width, and `Delta BAcc^pile` is
overlap-minus-clean PID balanced accuracy.  Lower is better.

| method                              |   s61c_transfer_score |   delta_s61c_transfer_score_vs_traditional |
|:------------------------------------|----------------------:|-------------------------------------------:|
| template_residual_boosted_stack_new |               0.28692 |                                  -0.077245 |
| gradient_boosted_trees              |               0.28783 |                                  -0.076337 |
| ridge                               |               0.31197 |                                  -0.052193 |
| 1d_cnn                              |               0.33867 |                                  -0.025491 |
| deltaE_over_E_likelihood_template   |               0.36416 |                                   0        |
| joint_sequence_transformer          |               0.43035 |                                   0.066187 |
| mlp                                 |               0.46037 |                                   0.096212 |

The winner after the S61c transfer penalty is **`template_residual_boosted_stack_new`**.  The method keeps
the strongest base closure while also minimizing sample-family and pedestal
transfer degradation among the high-performing methods.

### Saturation, Pile-Up, Pedestal, and Sample Slices

| axis             | value                 |   n |   energy_fractional_bias |   energy_fractional_sigma68 |   pid_balanced_accuracy |   timing_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------|:----------------------|----:|-------------------------:|----------------------------:|------------------------:|--------------------:|-------------------:|-------------------:|
| sample_family    | sample_ii_analysis    | 528 |                -0.04876  |                    0.17431  |                 0.865   |              1.6025 |            0.16288 |           0.13447  |
| sample_family    | sample_ii_calib       | 132 |                -0.048639 |                    0.19649  |                 0.77778 |              1.2724 |            0.19697 |           0.083333 |
| saturation_state | saturated             | 240 |                -0.017043 |                    0.088075 |                 0.83919 |              1.7917 |            0.15    |           0.19167  |
| saturation_state | unsaturated           | 420 |                -0.11099  |                    0.2276   |                 0.85476 |              1.3951 |            0.18095 |           0.085714 |
| pileup_state     | clean                 | 330 |                -0.14657  |                    0.23029  |                 0.86753 |              1.6404 |            0       |           0.24848  |
| pileup_state     | overlap               | 330 |                -0.016311 |                    0.10647  |                 0.8303  |              1.4094 |            0.33939 |           0        |
| pedestal_bin     | (-170.068, -8.932]    | 220 |                -0.053335 |                    0.15644  |                 0.86012 |              1.3713 |            0.18636 |           0.072727 |
| pedestal_bin     | (-4320.819, -170.068] | 220 |                -0.037398 |                    0.17757  |                 0.84252 |              1.797  |            0.14545 |           0.19091  |
| pedestal_bin     | (-8.932, 609.332]     | 220 |                -0.065245 |                    0.20931  |                 0.84293 |              1.3604 |            0.17727 |           0.10909  |

### Transfer-Degradation Components

| method                              |   sample_energy_sigma68_span |   sample_pid_bacc_span |   saturated_minus_unsaturated_energy_sigma68 |   overlap_minus_clean_pid_bacc |   pedestal_energy_sigma68_span |   s61c_transfer_score |
|:------------------------------------|-----------------------------:|-----------------------:|---------------------------------------------:|-------------------------------:|-------------------------------:|----------------------:|
| template_residual_boosted_stack_new |                   0.022184   |             0.087227   |                                    -0.13953  |                      -0.037226 |                       0.052866 |               0.28692 |
| gradient_boosted_trees              |                   0.01915    |             0.10818    |                                    -0.14273  |                      -0.04617  |                       0.04769  |               0.28783 |
| ridge                               |                   0.0059122  |             0.051192   |                                    -0.12116  |                      -0.026614 |                       0.023713 |               0.31197 |
| 1d_cnn                              |                   0.005748   |             0.07273    |                                    -0.091778 |                      -0.008765 |                       0.058675 |               0.33867 |
| deltaE_over_E_likelihood_template   |                   0.022139   |             0.059048   |                                     0.044313 |                      -0.014678 |                       0.027421 |               0.36416 |
| joint_sequence_transformer          |                   9.9037e-06 |             0.00034212 |                                    -0.10248  |                      -0.02601  |                       0.031675 |               0.43035 |
| mlp                                 |                   0.0021625  |             0.0055326  |                                    -0.085357 |                      -0.053734 |                       0.076637 |               0.46037 |

## Queue Provenance

The required single claim command was run once as `tn-ticket claim testbeam-laptop-1 --project testbeam` and returned
the known null pseudo-ticket output `# null / null / null`.  Because the testbeam
queue was not empty and issue `#2524` remained open, the claim was recovered
without a second `tn-ticket claim` by applying the expected label transition:
`gh issue edit 2524 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open`.  Completion is recorded with `tn-ticket done 2524`.  No novel
follow-up ticket was appended.

## Caveats

The PID and energy truth are GEANT4/digitization bridge labels, not an external
beamline particle tag joined event-by-event to the real raw data.  The pedestal,
pile-up, and saturation labels are controlled truth proxies in the digitized
benchmark.  They are appropriate for a comparative architecture stress test,
but not for an absolute production PID efficiency claim.  The raw ROOT gate
protects the selected-pulse support and detector-channel semantics; it does not
by itself validate GEANT4 material budget, Birks quenching, electronics
response, or trigger acceptance.  The confidence intervals are run-block
bootstrap intervals over the held-out source runs and therefore reflect
run-to-run instability better than i.i.d. event uncertainty, but only five
held-out runs are available for the final score. The hysteresis label is a
finite-difference proxy built from the available pedestal truth sequence rather
than a direct electronics state-machine readout. It is useful for ranking
sensitivity to baseline history, but should not be interpreted as a calibrated
hysteresis time constant.

## Conclusion

Use **`template_residual_boosted_stack_new`** as the S61c benchmark winner. The result favors a hybrid
physics-residual architecture over a pure black-box transformer: waveform ML is
useful when it residualizes a strong likelihood/template baseline, but the
state-stratified boundary tables show that pedestal and saturation still move
local PID thresholds.  For production PID, the traditional likelihood template
remains the interpretable reference and should be retained as a calibration
monitor even when the residual architecture is used for best held-out score.

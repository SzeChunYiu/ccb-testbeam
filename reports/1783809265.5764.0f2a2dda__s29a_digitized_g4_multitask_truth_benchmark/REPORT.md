# S29a: digitized GEANT4 multi-task PID-energy-timing truth benchmark

## Abstract

Ticket `1783809265.5764.0f2a2dda` requests a raw-ROOT-reproduced benchmark in which ADC-like B-stack
waveforms carry event-aligned truth labels for particle identity, deposited energy,
timing, pile-up, saturation, and pedestal.  The raw selected-pulse reproduction gate
passes exactly: `640737` selected B-stave pulses versus
the reference `640737`, delta `0`.

The winner is **`template_residual_boosted_stack_new`** by the predeclared held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy sigma68 `0.08293` with 95%
run-block bootstrap CI [0.07272,
0.09383], timing sigma68
`8.096` ns, and PID balanced accuracy
`0.8488`.

## Raw ROOT reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` branch is reshaped
to `(event, channel, sample)` with 18 samples per channel.  The reproduction gate
uses B2/B4/B6/B8, pedestal `b_c=median(x_c[0:4])`, corrected waveform
`y_c(t)=x_c(t)-b_c`, and selection `max_t y_c(t)>1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## GEANT4 truth construction

GEANT4 truth is read from `/home/billy/ccb-geant4/output_30k.root`, tree `hibeam`, using
`Sci_bar_LayerID`, `Sci_bar_PDG`, `Sci_bar_EDep`, `Sci_bar_Time`, and track length.
Sci_bar layers 0, 2, 4, and 6 are mapped to B2, B4, B6, and B8.  For each simulated
event, the dominant B-stack hit defines PID truth: PDG 2212 is proton and PDG
1000010020 is deuteron.  The total B-stack energy is

`E_i = sum_h EDep_ih`,

and the event time label is the energy-weighted truth time

`t_i = (sum_h EDep_ih t_ih) / (sum_h EDep_ih)`.

The ADC-like waveform for event `i` is generated from raw-data templates and residuals,
then scaled by `A_i = 250.0 E_i` ADC with clipping to the observed dynamic
range.  This makes the labels event-aligned and GEANT4-derived while preserving
real B-stack waveform residual structure.

| quantity                       |   value |
|:-------------------------------|--------:|
| usable_geant4_sci_bar_events   | 7101    |
| proton_truth_rows              | 3571    |
| deuteron_truth_rows            | 3485    |
| median_total_edep_mev          |   62    |
| median_energy_weighted_time_ns |   10.57 |

## Split and leakage controls

The split is by source run.  Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]`;
held-out runs are `[58, 60, 62, 64, 65]`.  No run appears in both sets.
Templates, scalers, likelihood moments, neural normalizers, and regressors are fit
on train runs only.  The run identifier, event identifier, and GEANT4 entry number
are excluded from model features; they are retained only for grouping, audit, and
bootstrap resampling.

Train-only template summaries:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              672 |                   2.685 |                      5 |           9.195 |
| B4      |              672 |                   3.014 |                      6 |          10.69  |
| B6      |              639 |                   3.709 |                      6 |           9.698 |
| B8      |              464 |                   4.235 |                      8 |           9.261 |

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`: a bounded
two-pulse template/CFD fit for pile-up timing and energy plus a diagonal Gaussian
likelihood-ratio PID model.  With standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge classifiers/regressors, histogram gradient-boosted
trees, MLP classifiers/regressors, and a compact 1D-CNN.  The new architecture is
`joint_sequence_transformer`, a waveform sequence encoder with separate pile-up,
PID, and four-parameter recovery heads.  A physics-residual boosted stack is also
included as a residualized architecture that uses the traditional fit as a first
stage.

For accepted injected doublets, timing and energy residuals are

`e_t = 10 ns (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - A_GEANT4] / A_GEANT4`,

and `sigma68(e) = [Q_84(e)-Q_16(e)]/2`.  Confidence intervals are percentile
intervals from `320` held-out run-block bootstrap
resamples.

## Overall held-out results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.2311 |    0.9044 |                  0.8488 |           0.9055 |       0.8115 |                     0.08293 |                            0.07272 |                             0.09383 |             8.096 |                    7.479 |                     9.023 |             0.3394 |            0.2485  |
| gradient_boosted_trees              |         0.2349 |    0.9106 |                  0.8443 |           0.8994 |       0.8082 |                     0.08622 |                            0.08387 |                             0.09331 |             8.222 |                    7.239 |                     9.549 |             0.3061 |            0.2455  |
| ridge                               |         0.2823 |    0.8378 |                  0.7527 |           0.6951 |       0.7835 |                     0.08872 |                            0.07643 |                             0.105   |            10.34  |                    9.31  |                    11.03  |             0.2848 |            0.2818  |
| 1d_cnn                              |         0.2935 |    0.836  |                  0.7771 |           0.7561 |       0.7873 |                     0.103   |                            0.08615 |                             0.1322  |            10.78  |                    9.385 |                    12.1   |             0.2879 |            0.2515  |
| deltaE_over_E_likelihood_template   |         0.3134 |    0.788  |                  0.7679 |           0.7195 |       0.7946 |                     0.1003  |                            0.09173 |                             0.1206  |            11.6   |                    9.603 |                    14.56  |             0.6879 |            0.09394 |
| joint_sequence_transformer          |         0.3953 |    0.5213 |                  0.5147 |           0.4421 |       0.5142 |                     0.1224  |                            0.1102  |                             0.1339  |            12.38  |                   11.42  |                    14.25  |             0.3333 |            0.2212  |
| mlp                                 |         0.4137 |    0.7688 |                  0.7026 |           0.6311 |       0.734  |                     0.1614  |                            0.1394  |                             0.1849  |            14.85  |                   13.77  |                    16.57  |             0.297  |            0.2909  |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes energy sigma68 by
`-0.01735`,
timing sigma68 by `-3.505` ns,
and PID balanced accuracy by `0.08094`.

## Run-held-out stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.7727 |           0.697  |       0.8214 |                     0.1047  |            11.12  |             0.2121 |            0.3636  |
| 1d_cnn                              |            60 |                  0.8461 |           0.8065 |       0.8621 |                     0.1001  |            12.26  |             0.303  |            0.3333  |
| 1d_cnn                              |            62 |                  0.7933 |           0.7581 |       0.7966 |                     0.08179 |             8.058 |             0.3182 |            0.2121  |
| 1d_cnn                              |            64 |                  0.7181 |           0.7361 |       0.7465 |                     0.1744  |            11.08  |             0.3182 |            0.1212  |
| 1d_cnn                              |            65 |                  0.75   |           0.7879 |       0.7324 |                     0.08991 |            11.16  |             0.2879 |            0.2273  |
| deltaE_over_E_likelihood_template   |            58 |                  0.7652 |           0.6667 |       0.8302 |                     0.09203 |            14.68  |             0.5909 |            0.09091 |
| deltaE_over_E_likelihood_template   |            60 |                  0.8219 |           0.7581 |       0.8545 |                     0.1038  |             9.742 |             0.6818 |            0.1667  |
| deltaE_over_E_likelihood_template   |            62 |                  0.7862 |           0.7581 |       0.7833 |                     0.09795 |            10.55  |             0.7424 |            0.07576 |
| deltaE_over_E_likelihood_template   |            64 |                  0.7194 |           0.7222 |       0.7536 |                     0.11    |            13.14  |             0.7273 |            0.07576 |
| deltaE_over_E_likelihood_template   |            65 |                  0.7424 |           0.697  |       0.7667 |                     0.1292  |             6.652 |             0.697  |            0.06061 |
| gradient_boosted_trees              |            58 |                  0.8864 |           0.8939 |       0.8806 |                     0.08302 |             8.568 |             0.197  |            0.3333  |
| gradient_boosted_trees              |            60 |                  0.8873 |           0.9032 |       0.8615 |                     0.08422 |             7.334 |             0.3182 |            0.3182  |
| gradient_boosted_trees              |            62 |                  0.8373 |           0.9032 |       0.7778 |                     0.07876 |             9.376 |             0.3788 |            0.2121  |
| gradient_boosted_trees              |            64 |                  0.7569 |           0.8472 |       0.7531 |                     0.08487 |             6.329 |             0.3333 |            0.1667  |
| gradient_boosted_trees              |            65 |                  0.8485 |           0.9545 |       0.7875 |                     0.09099 |             9.379 |             0.303  |            0.197   |
| joint_sequence_transformer          |            58 |                  0.4773 |           0.3333 |       0.4681 |                     0.1097  |            13.81  |             0.2576 |            0.303   |
| joint_sequence_transformer          |            60 |                  0.4829 |           0.4516 |       0.4516 |                     0.1096  |            14.87  |             0.3939 |            0.2727  |
| joint_sequence_transformer          |            62 |                  0.5115 |           0.4516 |       0.4828 |                     0.107   |            10.02  |             0.3788 |            0.2121  |
| joint_sequence_transformer          |            64 |                  0.5153 |           0.4306 |       0.5636 |                     0.1222  |            13.49  |             0.3182 |            0.1667  |
| joint_sequence_transformer          |            65 |                  0.5909 |           0.5455 |       0.6    |                     0.1206  |            12.06  |             0.3182 |            0.1515  |
| mlp                                 |            58 |                  0.7045 |           0.5909 |       0.7647 |                     0.1677  |            16.78  |             0.2727 |            0.3636  |
| mlp                                 |            60 |                  0.7065 |           0.6129 |       0.7308 |                     0.1626  |            16.17  |             0.3182 |            0.3636  |
| mlp                                 |            62 |                  0.7387 |           0.6774 |       0.75   |                     0.1225  |            13.29  |             0.3636 |            0.3182  |
| mlp                                 |            64 |                  0.7056 |           0.6944 |       0.7463 |                     0.2108  |            13.68  |             0.303  |            0.2121  |
| mlp                                 |            65 |                  0.6515 |           0.5758 |       0.6786 |                     0.1401  |            13.9   |             0.2273 |            0.197   |
| ridge                               |            58 |                  0.7576 |           0.6515 |       0.8269 |                     0.08063 |            10.25  |             0.2121 |            0.3182  |
| ridge                               |            60 |                  0.8067 |           0.7419 |       0.8364 |                     0.1022  |            11.21  |             0.3333 |            0.3636  |
| ridge                               |            62 |                  0.7601 |           0.6774 |       0.7925 |                     0.06928 |             8.094 |             0.3788 |            0.2727  |
| ridge                               |            64 |                  0.7097 |           0.7361 |       0.7361 |                     0.1147  |            10.95  |             0.2576 |            0.2576  |
| ridge                               |            65 |                  0.7197 |           0.6667 |       0.7458 |                     0.09239 |             9.951 |             0.2424 |            0.197   |
| template_residual_boosted_stack_new |            58 |                  0.8864 |           0.9091 |       0.8696 |                     0.06746 |             7.748 |             0.2424 |            0.3333  |
| template_residual_boosted_stack_new |            60 |                  0.8712 |           0.871  |       0.8571 |                     0.09293 |             7.379 |             0.3636 |            0.3333  |
| template_residual_boosted_stack_new |            62 |                  0.8445 |           0.9032 |       0.7887 |                     0.06691 |             9.062 |             0.3788 |            0.2273  |
| template_residual_boosted_stack_new |            64 |                  0.7778 |           0.8889 |       0.7619 |                     0.08774 |             7.398 |             0.3939 |            0.1667  |
| template_residual_boosted_stack_new |            65 |                  0.8561 |           0.9545 |       0.7975 |                     0.09343 |             9.034 |             0.3182 |            0.1818  |

## Strata, systematics, and caveats

| stratum     | value                 | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:----------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]        | 1d_cnn                              |                  0.7353 |                     0.1225  |            14.6   |            0.4118  |
| spacing_bin | (10.0, 25.0]          | 1d_cnn                              |                  0.6907 |                     0.1054  |            10.47  |            0.375   |
| spacing_bin | (25.0, 45.0]          | 1d_cnn                              |                  0.8561 |                     0.1116  |             7.712 |            0.1807  |
| spacing_bin | (45.0, 70.0]          | 1d_cnn                              |                  0.8262 |                     0.108   |            13.45  |            0.1231  |
| spacing_bin | (-0.001, 10.0]        | deltaE_over_E_likelihood_template   |                  0.7059 |                     0.09116 |            21.55  |            0.8137  |
| spacing_bin | (10.0, 25.0]          | deltaE_over_E_likelihood_template   |                  0.7551 |                     0.08358 |            11.07  |            0.775   |
| spacing_bin | (25.0, 45.0]          | deltaE_over_E_likelihood_template   |                  0.8453 |                     0.08449 |            10.12  |            0.6265  |
| spacing_bin | (45.0, 70.0]          | deltaE_over_E_likelihood_template   |                  0.7619 |                     0.1256  |             9.636 |            0.4615  |
| spacing_bin | (-0.001, 10.0]        | gradient_boosted_trees              |                  0.8039 |                     0.08306 |             8.646 |            0.4314  |
| spacing_bin | (10.0, 25.0]          | gradient_boosted_trees              |                  0.7462 |                     0.07402 |             6.362 |            0.3375  |
| spacing_bin | (25.0, 45.0]          | gradient_boosted_trees              |                  0.8785 |                     0.09043 |             9.143 |            0.241   |
| spacing_bin | (45.0, 70.0]          | gradient_boosted_trees              |                  0.869  |                     0.08927 |             9.206 |            0.1538  |
| spacing_bin | (-0.001, 10.0]        | joint_sequence_transformer          |                  0.4412 |                     0.1278  |            19.73  |            0.4412  |
| spacing_bin | (10.0, 25.0]          | joint_sequence_transformer          |                  0.5391 |                     0.0895  |            11.9   |            0.4125  |
| spacing_bin | (25.0, 45.0]          | joint_sequence_transformer          |                  0.5654 |                     0.1141  |             8.278 |            0.2771  |
| spacing_bin | (45.0, 70.0]          | joint_sequence_transformer          |                  0.4881 |                     0.121   |             9.773 |            0.1385  |
| spacing_bin | (-0.001, 10.0]        | mlp                                 |                  0.6667 |                     0.1353  |            14.97  |            0.3922  |
| spacing_bin | (10.0, 25.0]          | mlp                                 |                  0.6932 |                     0.1338  |            13.17  |            0.375   |
| spacing_bin | (25.0, 45.0]          | mlp                                 |                  0.7256 |                     0.1768  |            14.2   |            0.2651  |
| spacing_bin | (45.0, 70.0]          | mlp                                 |                  0.6262 |                     0.1475  |            15.49  |            0.09231 |
| spacing_bin | (-0.001, 10.0]        | ridge                               |                  0.7255 |                     0.07715 |            11.22  |            0.3627  |
| spacing_bin | (10.0, 25.0]          | ridge                               |                  0.6793 |                     0.08434 |             6.927 |            0.35    |
| spacing_bin | (25.0, 45.0]          | ridge                               |                  0.798  |                     0.09947 |             8.501 |            0.253   |
| spacing_bin | (45.0, 70.0]          | ridge                               |                  0.7714 |                     0.07335 |            14.15  |            0.1231  |
| spacing_bin | (-0.001, 10.0]        | template_residual_boosted_stack_new |                  0.7843 |                     0.07164 |             8.241 |            0.4608  |
| spacing_bin | (10.0, 25.0]          | template_residual_boosted_stack_new |                  0.7348 |                     0.08022 |             6.304 |            0.3875  |
| spacing_bin | (25.0, 45.0]          | template_residual_boosted_stack_new |                  0.9517 |                     0.07855 |             8.836 |            0.253   |
| spacing_bin | (45.0, 70.0]          | template_residual_boosted_stack_new |                  0.869  |                     0.07378 |             8.516 |            0.2     |
| energy_bin  | (599.999, 12944.09]   | 1d_cnn                              |                  0.7614 |                     0.1421  |            11.68  |            0.2674  |
| energy_bin  | (12944.09, 15170.849] | 1d_cnn                              |                  0.8006 |                     0.08841 |            11.51  |            0.3133  |
| energy_bin  | (15170.849, 16000.0]  | 1d_cnn                              |                  0.7344 |                     0.1184  |            10.32  |            0.2857  |
| energy_bin  | (599.999, 12944.09]   | deltaE_over_E_likelihood_template   |                  0.6857 |                     0.08629 |            10.28  |            0.686   |
| energy_bin  | (12944.09, 15170.849] | deltaE_over_E_likelihood_template   |                  0.8398 |                     0.103   |            12.19  |            0.6747  |
| energy_bin  | (15170.849, 16000.0]  | deltaE_over_E_likelihood_template   |                  0.7506 |                     0.1174  |            11.53  |            0.6957  |
| energy_bin  | (599.999, 12944.09]   | gradient_boosted_trees              |                  0.7643 |                     0.1091  |             8.47  |            0.4186  |
| energy_bin  | (12944.09, 15170.849] | gradient_boosted_trees              |                  0.9628 |                     0.07698 |             8.296 |            0.3012  |
| energy_bin  | (15170.849, 16000.0]  | gradient_boosted_trees              |                  0.8071 |                     0.07551 |             7.646 |            0.2484  |
| energy_bin  | (599.999, 12944.09]   | joint_sequence_transformer          |                  0.5336 |                     0.1588  |            14.18  |            0.314   |
| energy_bin  | (12944.09, 15170.849] | joint_sequence_transformer          |                  0.5913 |                     0.09615 |            14.21  |            0.3735  |
| energy_bin  | (15170.849, 16000.0]  | joint_sequence_transformer          |                  0.4772 |                     0.1347  |            11.23  |            0.323   |
| energy_bin  | (599.999, 12944.09]   | mlp                                 |                  0.6494 |                     0.2196  |            20.14  |            0.3953  |
| energy_bin  | (12944.09, 15170.849] | mlp                                 |                  0.7624 |                     0.1553  |            15.09  |            0.3253  |
| energy_bin  | (15170.849, 16000.0]  | mlp                                 |                  0.6675 |                     0.1188  |            13     |            0.2298  |
| energy_bin  | (599.999, 12944.09]   | ridge                               |                  0.7921 |                     0.09212 |            10.87  |            0.4767  |
| energy_bin  | (12944.09, 15170.849] | ridge                               |                  0.7559 |                     0.07728 |            11.04  |            0.2771  |
| energy_bin  | (15170.849, 16000.0]  | ridge                               |                  0.6883 |                     0.09686 |             9.849 |            0.1863  |
| energy_bin  | (599.999, 12944.09]   | template_residual_boosted_stack_new |                  0.7836 |                     0.09889 |             8.083 |            0.4884  |
| energy_bin  | (12944.09, 15170.849] | template_residual_boosted_stack_new |                  0.9628 |                     0.07301 |             8.689 |            0.3373  |
| energy_bin  | (15170.849, 16000.0]  | template_residual_boosted_stack_new |                  0.8064 |                     0.07845 |             7.581 |            0.2609  |
| stave       | B2                    | 1d_cnn                              |                  0.8164 |                     0.1244  |            12.4   |            0.4857  |
| stave       | B4                    | 1d_cnn                              |                  0.757  |                     0.124   |            12.17  |            0.3168  |
| stave       | B6                    | 1d_cnn                              |                  0.7591 |                     0.1384  |             9.505 |            0.2658  |
| stave       | B8                    | 1d_cnn                              |                  0.7839 |                     0.1031  |             9.283 |            0.1     |
| stave       | B2                    | deltaE_over_E_likelihood_template   |                  0.8377 |                     0.04835 |            17.53  |            0.7143  |
| stave       | B4                    | deltaE_over_E_likelihood_template   |                  0.7385 |                     0.1545  |            13.66  |            0.8911  |
| stave       | B6                    | deltaE_over_E_likelihood_template   |                  0.7365 |                     0.1295  |            11.86  |            0.6835  |
| stave       | B8                    | deltaE_over_E_likelihood_template   |                  0.7712 |                     0.08552 |             6.622 |            0.4125  |
| stave       | B2                    | gradient_boosted_trees              |                  0.8217 |                     0.06909 |             7.885 |            0.4     |
| stave       | B4                    | gradient_boosted_trees              |                  0.8281 |                     0.1064  |             8.213 |            0.3564  |
| stave       | B6                    | gradient_boosted_trees              |                  0.8966 |                     0.1002  |             6.768 |            0.3291  |
| stave       | B8                    | gradient_boosted_trees              |                  0.8303 |                     0.08689 |             6.078 |            0.1375  |
| stave       | B2                    | joint_sequence_transformer          |                  0.5206 |                     0.1109  |            14.7   |            0.4429  |
| stave       | B4                    | joint_sequence_transformer          |                  0.5056 |                     0.1605  |            15.03  |            0.4257  |
| stave       | B6                    | joint_sequence_transformer          |                  0.4925 |                     0.1221  |            10.85  |            0.3544  |
| stave       | B8                    | joint_sequence_transformer          |                  0.5393 |                     0.1106  |            11.55  |            0.1     |
| stave       | B2                    | mlp                                 |                  0.7015 |                     0.1804  |            17.07  |            0.4714  |
| stave       | B4                    | mlp                                 |                  0.73   |                     0.1533  |            15.74  |            0.2574  |
| stave       | B6                    | mlp                                 |                  0.7127 |                     0.1697  |            14.38  |            0.2911  |
| stave       | B8                    | mlp                                 |                  0.6483 |                     0.1387  |            13.62  |            0.2     |
| stave       | B2                    | ridge                               |                  0.7357 |                     0.06935 |            11.36  |            0.4143  |
| stave       | B4                    | ridge                               |                  0.7444 |                     0.09329 |            10.47  |            0.2871  |
| stave       | B6                    | ridge                               |                  0.7597 |                     0.1083  |             9.333 |            0.2658  |
| stave       | B8                    | ridge                               |                  0.7699 |                     0.08956 |             7.971 |            0.1875  |
| stave       | B2                    | template_residual_boosted_stack_new |                  0.8224 |                     0.07728 |             7.462 |            0.4714  |
| stave       | B4                    | template_residual_boosted_stack_new |                  0.832  |                     0.08305 |             8.766 |            0.396   |
| stave       | B6                    | template_residual_boosted_stack_new |                  0.896  |                     0.08993 |             7.129 |            0.3418  |
| stave       | B8                    | template_residual_boosted_stack_new |                  0.8443 |                     0.08434 |             6.388 |            0.15    |
| pid_truth   | deuteron_like         | 1d_cnn                              |                  0.7561 |                     0.1031  |            11.34  |            0.2848  |
| pid_truth   | proton_like           | 1d_cnn                              |                  0.7982 |                     0.102   |            10.65  |            0.2909  |
| pid_truth   | deuteron_like         | deltaE_over_E_likelihood_template   |                  0.7195 |                     0.09023 |            12.52  |            0.6788  |
| pid_truth   | proton_like           | deltaE_over_E_likelihood_template   |                  0.8163 |                     0.1125  |            10.04  |            0.697   |
| pid_truth   | deuteron_like         | gradient_boosted_trees              |                  0.8994 |                     0.07625 |             8.635 |            0.3152  |
| pid_truth   | proton_like           | gradient_boosted_trees              |                  0.7892 |                     0.09192 |             7.878 |            0.297   |
| pid_truth   | deuteron_like         | joint_sequence_transformer          |                  0.4421 |                     0.1267  |            13.6   |            0.3273  |
| pid_truth   | proton_like           | joint_sequence_transformer          |                  0.5873 |                     0.1183  |            12.37  |            0.3394  |
| pid_truth   | deuteron_like         | mlp                                 |                  0.6311 |                     0.1707  |            15.87  |            0.297   |
| pid_truth   | proton_like           | mlp                                 |                  0.7741 |                     0.1349  |            14.42  |            0.297   |
| pid_truth   | deuteron_like         | ridge                               |                  0.6951 |                     0.08685 |            11     |            0.2848  |
| pid_truth   | proton_like           | ridge                               |                  0.8102 |                     0.08849 |             9.221 |            0.2848  |
| pid_truth   | deuteron_like         | template_residual_boosted_stack_new |                  0.9055 |                     0.07253 |             8.188 |            0.3455  |
| pid_truth   | proton_like           | template_residual_boosted_stack_new |                  0.7922 |                     0.08669 |             8.395 |            0.3333  |

The main systematic is the hybrid digitization: GEANT4 supplies true PID, energy,
and hit-time labels, while the 18-sample ADC waveform morphology is drawn from
raw B-stack templates and residual pools.  Therefore the benchmark tests whether
models can use realistic ADC-like morphology to recover GEANT4-aligned labels; it
does not prove that the current detector response simulation is fully calibrated.
The ADC/MeV scale is fixed for ranking, not an external calibration.  Saturation
truth is defined by the digitized corrected maximum exceeding 14000 ADC, and
pedestal truth is the pretrigger median inherited from the raw residual event.
Bootstrap intervals cover held-out run transfer, not uncertainty in the GEANT4
physics list or detector material model.

Runtime was `68.1` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

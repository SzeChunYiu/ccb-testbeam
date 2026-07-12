# G4-08: keyed digitized GEANT4 native-join PID-energy-timing benchmark

## Abstract

Ticket `1783883140.39222.3c4045b1` requests that the GEANT4-to-HRD digitizer output persist DAQ
event keys and that G4-08 be rerun with an exact native join rather than a
run-keyed pseudo-bridge.  This rerun writes `digitized_g4_08_keyed.root` with
`daq_run`, `EVENTNO`, `EVT`, `TRIGGER`, `g4_entry`, `digitizer_seed`, and
`bridge_version`, then merges benchmark labels back only through those keys.
The raw selected-pulse reproduction gate
passes exactly: `640737` selected B-stave pulses versus
the reference `640737`, delta `0`.

The winner is **`template_residual_boosted_stack_new`** by the predeclared held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy sigma68 `0.09328` with 95%
run-block bootstrap CI [0.08385,
0.1048], timing sigma68
`7.54` ns, and PID balanced accuracy
`0.832`.

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

## Native digitizer keys and exact join

The keyed digitizer output is `digitized_g4_08_keyed.root`, tree
`g4_08_digitized`.  The branch schema audit is:

| branch         | present   | typename   |
|:---------------|:----------|:-----------|
| daq_run        | True      | int32_t    |
| EVENTNO        | True      | int64_t    |
| EVT            | True      | int64_t    |
| TRIGGER        | True      | int64_t    |
| g4_entry       | True      | int64_t    |
| digitizer_seed | True      | int64_t    |
| bridge_version | True      | int32_t    |

The analysis table is joined back to this ROOT output by the six native key
columns `(daq_run, EVENTNO, EVT, TRIGGER, g4_entry, digitizer_seed)`.  No run-only
or row-order merge is used in the scoring path.

| check                                   |   value | pass   |
|:----------------------------------------|--------:|:-------|
| digitizer_key_branches_present          |       7 | True   |
| left_events                             |    1056 | True   |
| joined_events                           |    1056 | True   |
| native_row_roundtrip_mismatch           |       0 | True   |
| duplicate_native_keys_in_events         |       0 | True   |
| duplicate_native_keys_in_digitized_root |       0 | True   |

## Split and leakage controls

The split is by source run.  Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]`;
held-out runs are `[58, 60, 62, 64, 65]`.  No run appears in both sets.
Templates, scalers, likelihood moments, neural normalizers, and regressors are fit
on train runs only.  The DAQ keys, event identifier, and GEANT4 entry number are
excluded from model features; they are retained only for exact joining, grouping,
audit, and bootstrap resampling.

Train-only template summaries:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              576 |                   2.638 |                      5 |           9.1   |
| B4      |              576 |                   3.04  |                      6 |          10.91  |
| B6      |              555 |                   3.714 |                      6 |           9.621 |
| B8      |              431 |                   4.216 |                      8 |           9.322 |

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
intervals from `260` held-out run-block bootstrap
resamples.

## Overall held-out results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.2371 |    0.8946 |                  0.832  |           0.8681 |       0.8031 |                     0.09328 |                            0.08385 |                              0.1048 |             7.54  |                    6.121 |                     9.809 |             0.3125 |             0.2167 |
| gradient_boosted_trees              |         0.2375 |    0.9059 |                  0.8191 |           0.8383 |       0.8008 |                     0.08546 |                            0.06421 |                              0.1014 |             7.744 |                    6.141 |                     9.744 |             0.3625 |             0.225  |
| ridge                               |         0.2826 |    0.8222 |                  0.7352 |           0.6255 |       0.7946 |                     0.08425 |                            0.06842 |                              0.1057 |            10.24  |                    9.547 |                    11.18  |             0.3667 |             0.2292 |
| deltaE_over_E_likelihood_template   |         0.3082 |    0.7503 |                  0.7276 |           0.6511 |       0.7612 |                     0.09759 |                            0.07059 |                              0.1202 |            10.61  |                    8.973 |                    13.78  |             0.6083 |             0.1208 |
| 1d_cnn                              |         0.3322 |    0.7926 |                  0.7206 |           0.6085 |       0.7772 |                     0.1054  |                            0.09616 |                              0.1226 |            12.77  |                   11.9   |                    13.45  |             0.3458 |             0.2375 |
| mlp                                 |         0.3912 |    0.726  |                  0.6671 |           0.4894 |       0.7516 |                     0.1488  |                            0.1244  |                              0.1838 |            12.61  |                   11.08  |                    14.04  |             0.3875 |             0.275  |
| joint_sequence_transformer          |         0.4356 |    0.5112 |                  0.4984 |           0.1234 |       0.4833 |                     0.1592  |                            0.1109  |                              0.1855 |            12.26  |                   11.39  |                    13.88  |             0.4083 |             0.1583 |

Relative to the traditional baseline, `template_residual_boosted_stack_new` changes energy sigma68 by
`-0.004307`,
timing sigma68 by `-3.069` ns,
and PID balanced accuracy by `0.1044`.

## Run-held-out stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.7416 |           0.641  |       0.7353 |                     0.08765 |            11.26  |             0.3333 |            0.1458  |
| 1d_cnn                              |            60 |                  0.7083 |           0.625  |       0.75   |                     0.122   |            11.76  |             0.2708 |            0.2708  |
| 1d_cnn                              |            62 |                  0.7206 |           0.6327 |       0.775  |                     0.07112 |            12.43  |             0.4167 |            0.25    |
| 1d_cnn                              |            64 |                  0.6799 |           0.5741 |       0.775  |                     0.1228  |            11.83  |             0.3125 |            0.2917  |
| 1d_cnn                              |            65 |                  0.7497 |           0.5778 |       0.8667 |                     0.108   |            14.4   |             0.3958 |            0.2292  |
| deltaE_over_E_likelihood_template   |            58 |                  0.7625 |           0.7179 |       0.7179 |                     0.09468 |            13.38  |             0.5833 |            0.1042  |
| deltaE_over_E_likelihood_template   |            60 |                  0.7396 |           0.6875 |       0.7674 |                     0.1213  |             8.762 |             0.5833 |            0.125   |
| deltaE_over_E_likelihood_template   |            62 |                  0.6785 |           0.6122 |       0.7143 |                     0.05007 |            10.36  |             0.6042 |            0.1042  |
| deltaE_over_E_likelihood_template   |            64 |                  0.6931 |           0.6481 |       0.7609 |                     0.07113 |             9.313 |             0.6667 |            0.08333 |
| deltaE_over_E_likelihood_template   |            65 |                  0.7608 |           0.6    |       0.871  |                     0.08075 |            13.66  |             0.6042 |            0.1875  |
| gradient_boosted_trees              |            58 |                  0.8779 |           0.9487 |       0.7708 |                     0.06447 |             6.483 |             0.3542 |            0.125   |
| gradient_boosted_trees              |            60 |                  0.8542 |           0.8958 |       0.8269 |                     0.08454 |             5.747 |             0.3125 |            0.3542  |
| gradient_boosted_trees              |            62 |                  0.7601 |           0.7755 |       0.76   |                     0.04977 |             9.117 |             0.3958 |            0.25    |
| gradient_boosted_trees              |            64 |                  0.7884 |           0.8148 |       0.8148 |                     0.09577 |             6.273 |             0.375  |            0.2083  |
| gradient_boosted_trees              |            65 |                  0.8203 |           0.7778 |       0.8333 |                     0.09215 |            11.29  |             0.375  |            0.1875  |
| joint_sequence_transformer          |            58 |                  0.5155 |           0.1538 |       0.4615 |                     0.1464  |            11.44  |             0.3958 |            0.125   |
| joint_sequence_transformer          |            60 |                  0.4479 |           0.0625 |       0.2727 |                     0.1619  |            11.73  |             0.3542 |            0.2292  |
| joint_sequence_transformer          |            62 |                  0.4974 |           0.1224 |       0.5    |                     0.07604 |            11.57  |             0.4792 |            0.1667  |
| joint_sequence_transformer          |            64 |                  0.4722 |           0.1111 |       0.4615 |                     0.1882  |            10.83  |             0.3958 |            0.1667  |
| joint_sequence_transformer          |            65 |                  0.5595 |           0.1778 |       0.7273 |                     0.1608  |            15.86  |             0.4167 |            0.1042  |
| mlp                                 |            58 |                  0.6518 |           0.4615 |       0.6667 |                     0.09462 |            13.67  |             0.375  |            0.1875  |
| mlp                                 |            60 |                  0.6042 |           0.4167 |       0.6667 |                     0.1742  |            13.51  |             0.3958 |            0.3333  |
| mlp                                 |            62 |                  0.701  |           0.551  |       0.7941 |                     0.2006  |            14.63  |             0.4792 |            0.3542  |
| mlp                                 |            64 |                  0.6243 |           0.463  |       0.7353 |                     0.125   |            10.36  |             0.3125 |            0.2292  |
| mlp                                 |            65 |                  0.7484 |           0.5556 |       0.8929 |                     0.1406  |            12.4   |             0.375  |            0.2708  |
| ridge                               |            58 |                  0.7632 |           0.6667 |       0.7647 |                     0.06889 |             9.32  |             0.2917 |            0.2083  |
| ridge                               |            60 |                  0.6979 |           0.625  |       0.7317 |                     0.1086  |             9.644 |             0.3542 |            0.2917  |
| ridge                               |            62 |                  0.7312 |           0.6327 |       0.7949 |                     0.05063 |             9.965 |             0.4375 |            0.2708  |
| ridge                               |            64 |                  0.7288 |           0.6481 |       0.814  |                     0.1162  |             9.509 |             0.3125 |            0.1458  |
| ridge                               |            65 |                  0.7484 |           0.5556 |       0.8929 |                     0.07355 |            11.65  |             0.4375 |            0.2292  |
| template_residual_boosted_stack_new |            58 |                  0.865  |           0.9231 |       0.766  |                     0.07794 |             6.39  |             0.2708 |            0.1458  |
| template_residual_boosted_stack_new |            60 |                  0.8854 |           0.9583 |       0.8364 |                     0.08313 |             5.351 |             0.2917 |            0.3125  |
| template_residual_boosted_stack_new |            62 |                  0.7805 |           0.8163 |       0.7692 |                     0.07463 |             8.886 |             0.3542 |            0.2083  |
| template_residual_boosted_stack_new |            64 |                  0.795  |           0.8519 |       0.807  |                     0.09522 |             7.239 |             0.2917 |            0.1875  |
| template_residual_boosted_stack_new |            65 |                  0.8314 |           0.8    |       0.8372 |                     0.1072  |            11.3   |             0.3542 |            0.2292  |

## Strata, systematics, and caveats

| stratum     | value                  | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:-----------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]         | 1d_cnn                              |                  0.7591 |                     0.1008  |            13.98  |            0.4651  |
| spacing_bin | (10.0, 25.0]           | 1d_cnn                              |                  0.6834 |                     0.09772 |            11.67  |            0.48    |
| spacing_bin | (25.0, 45.0]           | 1d_cnn                              |                  0.7018 |                     0.09245 |             8.777 |            0.2826  |
| spacing_bin | (45.0, 70.0]           | 1d_cnn                              |                  0.7413 |                     0.0817  |            12.89  |            0.1034  |
| spacing_bin | (-0.001, 10.0]         | deltaE_over_E_likelihood_template   |                  0.7369 |                     0.0825  |            14.78  |            0.7093  |
| spacing_bin | (10.0, 25.0]           | deltaE_over_E_likelihood_template   |                  0.7289 |                     0.09173 |            12.56  |            0.8     |
| spacing_bin | (25.0, 45.0]           | deltaE_over_E_likelihood_template   |                  0.7495 |                     0.1012  |             9.636 |            0.5652  |
| spacing_bin | (45.0, 70.0]           | deltaE_over_E_likelihood_template   |                  0.693  |                     0.06995 |            10.71  |            0.3276  |
| spacing_bin | (-0.001, 10.0]         | gradient_boosted_trees              |                  0.8469 |                     0.07025 |             7.589 |            0.5     |
| spacing_bin | (10.0, 25.0]           | gradient_boosted_trees              |                  0.7662 |                     0.1153  |             5.366 |            0.52    |
| spacing_bin | (25.0, 45.0]           | gradient_boosted_trees              |                  0.8207 |                     0.05762 |             8.081 |            0.2826  |
| spacing_bin | (45.0, 70.0]           | gradient_boosted_trees              |                  0.7694 |                     0.07337 |             8.635 |            0.08621 |
| spacing_bin | (-0.001, 10.0]         | joint_sequence_transformer          |                  0.4867 |                     0.1176  |            11.82  |            0.5233  |
| spacing_bin | (10.0, 25.0]           | joint_sequence_transformer          |                  0.5455 |                     0.09553 |            15.61  |            0.58    |
| spacing_bin | (25.0, 45.0]           | joint_sequence_transformer          |                  0.4795 |                     0.09609 |            10.01  |            0.3261  |
| spacing_bin | (45.0, 70.0]           | joint_sequence_transformer          |                  0.5269 |                     0.1005  |            11.27  |            0.1552  |
| spacing_bin | (-0.001, 10.0]         | mlp                                 |                  0.6846 |                     0.1444  |            11.31  |            0.4767  |
| spacing_bin | (10.0, 25.0]           | mlp                                 |                  0.6786 |                     0.1104  |             8.78  |            0.56    |
| spacing_bin | (25.0, 45.0]           | mlp                                 |                  0.7203 |                     0.1307  |            12.96  |            0.3478  |
| spacing_bin | (45.0, 70.0]           | mlp                                 |                  0.7091 |                     0.1348  |            16.32  |            0.1379  |
| spacing_bin | (-0.001, 10.0]         | ridge                               |                  0.8068 |                     0.0591  |             9.913 |            0.4767  |
| spacing_bin | (10.0, 25.0]           | ridge                               |                  0.638  |                     0.05893 |             8.151 |            0.54    |
| spacing_bin | (25.0, 45.0]           | ridge                               |                  0.7388 |                     0.1065  |            10.09  |            0.2826  |
| spacing_bin | (45.0, 70.0]           | ridge                               |                  0.7228 |                     0.06259 |            11.49  |            0.1207  |
| spacing_bin | (-0.001, 10.0]         | template_residual_boosted_stack_new |                  0.8347 |                     0.0882  |             7.449 |            0.3953  |
| spacing_bin | (10.0, 25.0]           | template_residual_boosted_stack_new |                  0.7662 |                     0.09225 |             6.055 |            0.46    |
| spacing_bin | (25.0, 45.0]           | template_residual_boosted_stack_new |                  0.8762 |                     0.06885 |             7.352 |            0.2826  |
| spacing_bin | (45.0, 70.0]           | template_residual_boosted_stack_new |                  0.7694 |                     0.08976 |             9.324 |            0.08621 |
| energy_bin  | (599.999, 13031.767]   | 1d_cnn                              |                  0.7076 |                     0.1178  |            12.64  |            0.4032  |
| energy_bin  | (13031.767, 15771.635] | 1d_cnn                              |                  0.7312 |                     0.07648 |            12.71  |            0.3016  |
| energy_bin  | (15771.635, 16000.0]   | 1d_cnn                              |                  0.7129 |                     0.1239  |            12.15  |            0.3391  |
| energy_bin  | (599.999, 13031.767]   | deltaE_over_E_likelihood_template   |                  0.6049 |                     0.09077 |            10.49  |            0.629   |
| energy_bin  | (13031.767, 15771.635] | deltaE_over_E_likelihood_template   |                  0.8182 |                     0.08265 |            10.9   |            0.619   |
| energy_bin  | (15771.635, 16000.0]   | deltaE_over_E_likelihood_template   |                  0.7428 |                     0.09673 |            10.68  |            0.5913  |
| energy_bin  | (599.999, 13031.767]   | gradient_boosted_trees              |                  0.7857 |                     0.09185 |             6.277 |            0.4677  |
| energy_bin  | (13031.767, 15771.635] | gradient_boosted_trees              |                  0.9283 |                     0.06376 |             6.758 |            0.3016  |
| energy_bin  | (15771.635, 16000.0]   | gradient_boosted_trees              |                  0.7856 |                     0.08866 |             8.616 |            0.3391  |
| energy_bin  | (599.999, 13031.767]   | joint_sequence_transformer          |                  0.5011 |                     0.1571  |            11.35  |            0.4355  |
| energy_bin  | (13031.767, 15771.635] | joint_sequence_transformer          |                  0.4583 |                     0.1048  |            11.51  |            0.3651  |
| energy_bin  | (15771.635, 16000.0]   | joint_sequence_transformer          |                  0.5151 |                     0.1709  |            12.5   |            0.4174  |
| energy_bin  | (599.999, 13031.767]   | mlp                                 |                  0.5737 |                     0.1766  |            17.79  |            0.4839  |
| energy_bin  | (13031.767, 15771.635] | mlp                                 |                  0.6904 |                     0.146   |            11.1   |            0.3492  |
| energy_bin  | (15771.635, 16000.0]   | mlp                                 |                  0.6936 |                     0.1261  |            11.49  |            0.3565  |
| energy_bin  | (599.999, 13031.767]   | ridge                               |                  0.7299 |                     0.07961 |            12.04  |            0.4839  |
| energy_bin  | (13031.767, 15771.635] | ridge                               |                  0.8017 |                     0.0754  |             9.778 |            0.2857  |
| energy_bin  | (15771.635, 16000.0]   | ridge                               |                  0.6969 |                     0.09479 |            10.48  |            0.3478  |
| energy_bin  | (599.999, 13031.767]   | template_residual_boosted_stack_new |                  0.7958 |                     0.08161 |             6.236 |            0.371   |
| energy_bin  | (13031.767, 15771.635] | template_residual_boosted_stack_new |                  0.9283 |                     0.08272 |             7.537 |            0.2698  |
| energy_bin  | (15771.635, 16000.0]   | template_residual_boosted_stack_new |                  0.8045 |                     0.1043  |             8.941 |            0.3043  |
| stave       | B2                     | 1d_cnn                              |                  0.7142 |                     0.1119  |            11.18  |            0.4853  |
| stave       | B4                     | 1d_cnn                              |                  0.6578 |                     0.1146  |            11.31  |            0.4     |
| stave       | B6                     | 1d_cnn                              |                  0.7357 |                     0.1116  |            12.31  |            0.2787  |
| stave       | B8                     | 1d_cnn                              |                  0.779  |                     0.08558 |             9.994 |            0.1964  |
| stave       | B2                     | deltaE_over_E_likelihood_template   |                  0.7235 |                     0.05019 |            15.45  |            0.7353  |
| stave       | B4                     | deltaE_over_E_likelihood_template   |                  0.6388 |                     0.1227  |            14.7   |            0.8182  |
| stave       | B6                     | deltaE_over_E_likelihood_template   |                  0.7443 |                     0.0789  |             8.753 |            0.4918  |
| stave       | B8                     | deltaE_over_E_likelihood_template   |                  0.8143 |                     0.0698  |             7.791 |            0.375   |
| stave       | B2                     | gradient_boosted_trees              |                  0.8148 |                     0.08585 |             9.039 |            0.5147  |
| stave       | B4                     | gradient_boosted_trees              |                  0.8324 |                     0.0812  |             4.946 |            0.3818  |
| stave       | B6                     | gradient_boosted_trees              |                  0.7944 |                     0.0882  |             6.207 |            0.2951  |
| stave       | B8                     | gradient_boosted_trees              |                  0.8314 |                     0.06666 |             6.287 |            0.2321  |
| stave       | B2                     | joint_sequence_transformer          |                  0.4953 |                     0.1826  |            12.02  |            0.5147  |
| stave       | B4                     | joint_sequence_transformer          |                  0.5049 |                     0.1657  |            11.26  |            0.4364  |
| stave       | B6                     | joint_sequence_transformer          |                  0.5425 |                     0.1408  |            10.02  |            0.377   |
| stave       | B8                     | joint_sequence_transformer          |                  0.4618 |                     0.1459  |            11.16  |            0.2857  |
| stave       | B2                     | mlp                                 |                  0.7153 |                     0.1994  |            15.44  |            0.5588  |
| stave       | B4                     | mlp                                 |                  0.5747 |                     0.1578  |             9.984 |            0.3636  |
| stave       | B6                     | mlp                                 |                  0.6854 |                     0.1614  |            10.04  |            0.3279  |
| stave       | B8                     | mlp                                 |                  0.7021 |                     0.1376  |            13.39  |            0.2679  |
| stave       | B2                     | ridge                               |                  0.7469 |                     0.06746 |            12.28  |            0.5147  |
| stave       | B4                     | ridge                               |                  0.7223 |                     0.06495 |             8.654 |            0.3636  |
| stave       | B6                     | ridge                               |                  0.7186 |                     0.1061  |             8.507 |            0.2623  |
| stave       | B8                     | ridge                               |                  0.7501 |                     0.07331 |             8.403 |            0.3036  |
| stave       | B2                     | template_residual_boosted_stack_new |                  0.8324 |                     0.1004  |             8.962 |            0.4706  |
| stave       | B4                     | template_residual_boosted_stack_new |                  0.8566 |                     0.09232 |             5.368 |            0.3455  |
| stave       | B6                     | template_residual_boosted_stack_new |                  0.7941 |                     0.09825 |             6.085 |            0.2459  |
| stave       | B8                     | template_residual_boosted_stack_new |                  0.8453 |                     0.05541 |             6.128 |            0.1607  |
| pid_truth   | deuteron_like          | 1d_cnn                              |                  0.6085 |                     0.1032  |            12.23  |            0.3554  |
| pid_truth   | proton_like            | 1d_cnn                              |                  0.8327 |                     0.1115  |            13.33  |            0.3361  |
| pid_truth   | deuteron_like          | deltaE_over_E_likelihood_template   |                  0.6511 |                     0.1061  |            12.03  |            0.6116  |
| pid_truth   | proton_like            | deltaE_over_E_likelihood_template   |                  0.8041 |                     0.07711 |             7.951 |            0.605   |
| pid_truth   | deuteron_like          | gradient_boosted_trees              |                  0.8383 |                     0.08608 |             7.677 |            0.3719  |
| pid_truth   | proton_like            | gradient_boosted_trees              |                  0.8    |                     0.07883 |             7.013 |            0.3529  |
| pid_truth   | deuteron_like          | joint_sequence_transformer          |                  0.1234 |                     0.1538  |            12.49  |            0.4215  |
| pid_truth   | proton_like            | joint_sequence_transformer          |                  0.8735 |                     0.1651  |            11.83  |            0.395   |
| pid_truth   | deuteron_like          | mlp                                 |                  0.4894 |                     0.1694  |            13.21  |            0.3719  |
| pid_truth   | proton_like            | mlp                                 |                  0.8449 |                     0.1166  |            12.32  |            0.4034  |
| pid_truth   | deuteron_like          | ridge                               |                  0.6255 |                     0.0774  |            10.21  |            0.3471  |
| pid_truth   | proton_like            | ridge                               |                  0.8449 |                     0.07771 |            10.85  |            0.3866  |
| pid_truth   | deuteron_like          | template_residual_boosted_stack_new |                  0.8681 |                     0.08603 |             7.151 |            0.3223  |
| pid_truth   | proton_like            | template_residual_boosted_stack_new |                  0.7959 |                     0.08981 |             7.904 |            0.3025  |

The main systematic is the hybrid digitization: GEANT4 supplies true PID, energy,
and hit-time labels, while the 18-sample ADC waveform morphology is drawn from
raw B-stack templates and residual pools.  The currently mounted GEANT4 source
ROOT does not itself contain DAQ keys; this ticket therefore persists the DAQ keys
at the GEANT4-to-HRD digitizer output boundary and makes downstream G4-08 joins
native to that keyed output.  This removes the prior run-keyed pseudo-bridge in
the analysis layer, but it is not a claim that the upstream generator already
knows DAQ event numbers.  The ADC/MeV scale is fixed for ranking, not an external
calibration.  Saturation truth is defined by the digitized corrected maximum
exceeding 14000 ADC, and pedestal truth is the pretrigger median inherited from
the raw residual event. Bootstrap intervals cover held-out run transfer, not
uncertainty in the GEANT4 physics list or detector material model.

Runtime was `69.9` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

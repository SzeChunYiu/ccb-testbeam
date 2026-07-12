# S29a: pulse-shape timing pile-up disentanglement bakeoff

## Abstract

Ticket `1783826036.4798.37744dd6` requests a raw-ROOT-reproduced benchmark comparing pulse-shape, timing,
and pile-up disentanglement methods under event-aligned PID, energy,
saturation, and pedestal sideband labels.  The raw selected-pulse reproduction gate
passes exactly: `640737` selected B-stave pulses versus
the reference `640737`, delta `0`.

The winner is **`gradient_boosted_trees`** by the predeclared held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy sigma68 `0.0841` with 95%
run-block bootstrap CI [0.071,
0.105], timing sigma68
`7.889` ns, and PID balanced accuracy
`0.8545`.

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
| gradient_boosted_trees              |         0.2266 |    0.9175 |                  0.8545 |           0.8962 |       0.8166 |                     0.0841  |                            0.071   |                              0.105  |             7.889 |                    7.279 |                     8.823 |             0.2879 |             0.2576 |
| template_residual_boosted_stack_new |         0.2328 |    0.9212 |                  0.8605 |           0.8994 |       0.8242 |                     0.09054 |                            0.07839 |                              0.1083 |             8.044 |                    7.364 |                     8.322 |             0.2848 |             0.2545 |
| ridge                               |         0.2772 |    0.8504 |                  0.7411 |           0.6635 |       0.7729 |                     0.09182 |                            0.08739 |                              0.1083 |             9.388 |                    8.268 |                    10.34  |             0.3182 |             0.2182 |
| deltaE_over_E_likelihood_template   |         0.3021 |    0.7841 |                  0.7772 |           0.7327 |       0.7925 |                     0.1194  |                            0.08159 |                              0.1565 |             8.757 |                    7.614 |                    10.81  |             0.6667 |             0.1212 |
| 1d_cnn                              |         0.3095 |    0.8001 |                  0.731  |           0.6258 |       0.7804 |                     0.09778 |                            0.07849 |                              0.1245 |            11.6   |                   10.54  |                    12.14  |             0.4242 |             0.1455 |
| mlp                                 |         0.3293 |    0.7703 |                  0.692  |           0.5975 |       0.7224 |                     0.1101  |                            0.09972 |                              0.1213 |            11.4   |                   10.63  |                    12.21  |             0.3242 |             0.2394 |
| joint_sequence_transformer          |         0.4058 |    0.5065 |                  0.516  |           0.1226 |       0.5571 |                     0.1313  |                            0.1159  |                              0.1487 |            12.5   |                   10.62  |                    13.77  |             0.3273 |             0.2424 |

Relative to the traditional baseline, `gradient_boosted_trees` changes energy sigma68 by
`-0.03528`,
timing sigma68 by `-0.8678` ns,
and PID balanced accuracy by `0.07738`.

## Run-held-out stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.7539 |          0.7049  |       0.7544 |                     0.1316  |            11.53  |             0.3939 |            0.1212  |
| 1d_cnn                              |            60 |                  0.6779 |          0.5636  |       0.6596 |                     0.06692 |             9.483 |             0.4091 |            0.1818  |
| 1d_cnn                              |            62 |                  0.7556 |          0.6111  |       0.88   |                     0.0867  |            13.34  |             0.4242 |            0.1515  |
| 1d_cnn                              |            64 |                  0.7288 |          0.629   |       0.7647 |                     0.1193  |            11.58  |             0.5758 |            0.1212  |
| 1d_cnn                              |            65 |                  0.7463 |          0.6176  |       0.84   |                     0.08967 |            11.6   |             0.3182 |            0.1515  |
| deltaE_over_E_likelihood_template   |            58 |                  0.7691 |          0.7213  |       0.7719 |                     0.1302  |             8.383 |             0.6364 |            0.1667  |
| deltaE_over_E_likelihood_template   |            60 |                  0.6649 |          0.5636  |       0.6327 |                     0.08716 |             7.583 |             0.5758 |            0.1212  |
| deltaE_over_E_likelihood_template   |            62 |                  0.7986 |          0.7639  |       0.8462 |                     0.1226  |             9.954 |             0.6818 |            0.07576 |
| deltaE_over_E_likelihood_template   |            64 |                  0.8085 |          0.7742  |       0.8136 |                     0.1621  |            10.33  |             0.7727 |            0.07576 |
| deltaE_over_E_likelihood_template   |            65 |                  0.8341 |          0.8088  |       0.8594 |                     0.1056  |             7.814 |             0.6667 |            0.1667  |
| gradient_boosted_trees              |            58 |                  0.8511 |          0.8852  |       0.806  |                     0.07526 |             7.541 |             0.2121 |            0.2727  |
| gradient_boosted_trees              |            60 |                  0.8377 |          0.9091  |       0.7353 |                     0.06788 |             6.75  |             0.303  |            0.2879  |
| gradient_boosted_trees              |            62 |                  0.8611 |          0.8889  |       0.8649 |                     0.07202 |             9.275 |             0.303  |            0.2727  |
| gradient_boosted_trees              |            64 |                  0.8364 |          0.8871  |       0.7857 |                     0.124   |             8.115 |             0.4091 |            0.1818  |
| gradient_boosted_trees              |            65 |                  0.8934 |          0.9118  |       0.8857 |                     0.09711 |             7.583 |             0.2121 |            0.2727  |
| joint_sequence_transformer          |            58 |                  0.5643 |          0.2131  |       0.6842 |                     0.1474  |            12.13  |             0.2576 |            0.2121  |
| joint_sequence_transformer          |            60 |                  0.561  |          0.2     |       0.6471 |                     0.1058  |            11.09  |             0.2424 |            0.2727  |
| joint_sequence_transformer          |            62 |                  0.4986 |          0.09722 |       0.5385 |                     0.1125  |            15.1   |             0.303  |            0.2879  |
| joint_sequence_transformer          |            64 |                  0.4813 |          0.04839 |       0.3333 |                     0.1578  |            10.59  |             0.5152 |            0.1818  |
| joint_sequence_transformer          |            65 |                  0.4821 |          0.07353 |       0.4167 |                     0.1288  |            11.06  |             0.3182 |            0.2576  |
| mlp                                 |            58 |                  0.7152 |          0.6557  |       0.7143 |                     0.114   |            12.15  |             0.2576 |            0.197   |
| mlp                                 |            60 |                  0.6766 |          0.6     |       0.6346 |                     0.1284  |            10.19  |             0.303  |            0.3485  |
| mlp                                 |            62 |                  0.725  |          0.5833  |       0.84   |                     0.1181  |            12.77  |             0.2576 |            0.2879  |
| mlp                                 |            64 |                  0.676  |          0.5806  |       0.6923 |                     0.1142  |             9.649 |             0.5    |            0.1818  |
| mlp                                 |            65 |                  0.6774 |          0.5735  |       0.7358 |                     0.08702 |            10.8   |             0.303  |            0.1818  |
| ridge                               |            58 |                  0.7691 |          0.7213  |       0.7719 |                     0.1109  |             9.597 |             0.2273 |            0.2121  |
| ridge                               |            60 |                  0.6766 |          0.6     |       0.6346 |                     0.07675 |             7.193 |             0.2727 |            0.2576  |
| ridge                               |            62 |                  0.7736 |          0.6806  |       0.8596 |                     0.08926 |             9.433 |             0.3182 |            0.2727  |
| ridge                               |            64 |                  0.7207 |          0.6129  |       0.76   |                     0.09761 |            10.73  |             0.5    |            0.197   |
| ridge                               |            65 |                  0.7675 |          0.6912  |       0.8246 |                     0.09275 |            10.04  |             0.2727 |            0.1515  |
| template_residual_boosted_stack_new |            58 |                  0.8663 |          0.9016  |       0.8209 |                     0.07678 |             6.703 |             0.2424 |            0.2576  |
| template_residual_boosted_stack_new |            60 |                  0.813  |          0.8727  |       0.7164 |                     0.08493 |             7.657 |             0.2424 |            0.303   |
| template_residual_boosted_stack_new |            62 |                  0.8917 |          0.9167  |       0.8919 |                     0.07755 |             8.391 |             0.3182 |            0.2879  |
| template_residual_boosted_stack_new |            64 |                  0.8203 |          0.8548  |       0.7794 |                     0.1459  |             7.35  |             0.3636 |            0.1515  |
| template_residual_boosted_stack_new |            65 |                  0.9159 |          0.9412  |       0.9014 |                     0.09002 |             7.64  |             0.2576 |            0.2727  |

## Strata, systematics, and caveats

| stratum     | value                  | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:-----------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]         | 1d_cnn                              |                  0.7063 |                     0.07609 |            11.36  |             0.6053 |
| spacing_bin | (10.0, 25.0]           | 1d_cnn                              |                  0.7817 |                     0.04796 |             7.632 |             0.6081 |
| spacing_bin | (25.0, 45.0]           | 1d_cnn                              |                  0.7006 |                     0.07441 |             8.802 |             0.2    |
| spacing_bin | (45.0, 70.0]           | 1d_cnn                              |                  0.7655 |                     0.1065  |            15.29  |             0.1667 |
| spacing_bin | (-0.001, 10.0]         | deltaE_over_E_likelihood_template   |                  0.7832 |                     0.1527  |            11.92  |             0.7982 |
| spacing_bin | (10.0, 25.0]           | deltaE_over_E_likelihood_template   |                  0.8218 |                     0.05041 |            13.17  |             0.7432 |
| spacing_bin | (25.0, 45.0]           | deltaE_over_E_likelihood_template   |                  0.794  |                     0.1257  |             7.19  |             0.5571 |
| spacing_bin | (45.0, 70.0]           | deltaE_over_E_likelihood_template   |                  0.7639 |                     0.106   |             7.701 |             0.4861 |
| spacing_bin | (-0.001, 10.0]         | gradient_boosted_trees              |                  0.9018 |                     0.07407 |             8.836 |             0.3947 |
| spacing_bin | (10.0, 25.0]           | gradient_boosted_trees              |                  0.8522 |                     0.06729 |             7.198 |             0.3514 |
| spacing_bin | (25.0, 45.0]           | gradient_boosted_trees              |                  0.8586 |                     0.08745 |             7.317 |             0.1857 |
| spacing_bin | (45.0, 70.0]           | gradient_boosted_trees              |                  0.8212 |                     0.08328 |             9.155 |             0.1528 |
| spacing_bin | (-0.001, 10.0]         | joint_sequence_transformer          |                  0.5157 |                     0.1076  |            16.25  |             0.4825 |
| spacing_bin | (10.0, 25.0]           | joint_sequence_transformer          |                  0.5233 |                     0.0925  |            12.1   |             0.4189 |
| spacing_bin | (25.0, 45.0]           | joint_sequence_transformer          |                  0.5294 |                     0.125   |             8.816 |             0.1571 |
| spacing_bin | (45.0, 70.0]           | joint_sequence_transformer          |                  0.5627 |                     0.1125  |            10.11  |             0.1528 |
| spacing_bin | (-0.001, 10.0]         | mlp                                 |                  0.7045 |                     0.1005  |            10.11  |             0.4474 |
| spacing_bin | (10.0, 25.0]           | mlp                                 |                  0.7146 |                     0.09907 |             9.623 |             0.4459 |
| spacing_bin | (25.0, 45.0]           | mlp                                 |                  0.6654 |                     0.1203  |            11.77  |             0.1857 |
| spacing_bin | (45.0, 70.0]           | mlp                                 |                  0.7051 |                     0.1178  |            12.17  |             0.1389 |
| spacing_bin | (-0.001, 10.0]         | ridge                               |                  0.7656 |                     0.08531 |            11.84  |             0.4561 |
| spacing_bin | (10.0, 25.0]           | ridge                               |                  0.7494 |                     0.06259 |             6.16  |             0.4595 |
| spacing_bin | (25.0, 45.0]           | ridge                               |                  0.7039 |                     0.09728 |             7.928 |             0.1286 |
| spacing_bin | (45.0, 70.0]           | ridge                               |                  0.7508 |                     0.09152 |            11.13  |             0.1389 |
| spacing_bin | (-0.001, 10.0]         | template_residual_boosted_stack_new |                  0.8843 |                     0.06912 |             9.62  |             0.4123 |
| spacing_bin | (10.0, 25.0]           | template_residual_boosted_stack_new |                  0.8683 |                     0.08148 |             6.836 |             0.3378 |
| spacing_bin | (25.0, 45.0]           | template_residual_boosted_stack_new |                  0.8714 |                     0.08817 |             6.987 |             0.1714 |
| spacing_bin | (45.0, 70.0]           | template_residual_boosted_stack_new |                  0.8622 |                     0.09157 |             9.922 |             0.1389 |
| energy_bin  | (599.999, 13258.847]   | 1d_cnn                              |                  0.7284 |                     0.09149 |            10.3   |             0.4146 |
| energy_bin  | (13258.847, 15360.134] | 1d_cnn                              |                  0.7552 |                     0.08007 |            11.75  |             0.4167 |
| energy_bin  | (15360.134, 16000.0]   | 1d_cnn                              |                  0.6913 |                     0.0953  |            11.33  |             0.4329 |
| energy_bin  | (599.999, 13258.847]   | deltaE_over_E_likelihood_template   |                  0.7131 |                     0.07214 |             6.846 |             0.6463 |
| energy_bin  | (13258.847, 15360.134] | deltaE_over_E_likelihood_template   |                  0.8123 |                     0.123   |            10.26  |             0.5952 |
| energy_bin  | (15360.134, 16000.0]   | deltaE_over_E_likelihood_template   |                  0.7631 |                     0.1397  |             9.657 |             0.7134 |
| energy_bin  | (599.999, 13258.847]   | gradient_boosted_trees              |                  0.8295 |                     0.08876 |             8.424 |             0.3659 |
| energy_bin  | (13258.847, 15360.134] | gradient_boosted_trees              |                  0.9727 |                     0.09078 |             8.941 |             0.2738 |
| energy_bin  | (15360.134, 16000.0]   | gradient_boosted_trees              |                  0.7979 |                     0.08389 |             7.349 |             0.2561 |
| energy_bin  | (599.999, 13258.847]   | joint_sequence_transformer          |                  0.5196 |                     0.1117  |            12.35  |             0.3171 |
| energy_bin  | (13258.847, 15360.134] | joint_sequence_transformer          |                  0.5447 |                     0.1344  |            11.04  |             0.3571 |
| energy_bin  | (15360.134, 16000.0]   | joint_sequence_transformer          |                  0.5034 |                     0.1346  |            12.34  |             0.3171 |
| energy_bin  | (599.999, 13258.847]   | mlp                                 |                  0.6983 |                     0.1048  |             8.45  |             0.4146 |
| energy_bin  | (13258.847, 15360.134] | mlp                                 |                  0.6996 |                     0.08038 |            10.19  |             0.2857 |
| energy_bin  | (15360.134, 16000.0]   | mlp                                 |                  0.6492 |                     0.1219  |            11.92  |             0.2988 |
| energy_bin  | (599.999, 13258.847]   | ridge                               |                  0.8131 |                     0.08941 |             8.976 |             0.3659 |
| energy_bin  | (13258.847, 15360.134] | ridge                               |                  0.7125 |                     0.09331 |             8.856 |             0.3095 |
| energy_bin  | (15360.134, 16000.0]   | ridge                               |                  0.6763 |                     0.105   |             9.478 |             0.2988 |
| energy_bin  | (599.999, 13258.847]   | template_residual_boosted_stack_new |                  0.8057 |                     0.08183 |             8.269 |             0.4024 |
| energy_bin  | (13258.847, 15360.134] | template_residual_boosted_stack_new |                  0.9633 |                     0.07612 |             8.553 |             0.2857 |
| energy_bin  | (15360.134, 16000.0]   | template_residual_boosted_stack_new |                  0.8251 |                     0.09486 |             7.664 |             0.2256 |
| stave       | B2                     | 1d_cnn                              |                  0.7055 |                     0.08821 |            13.25  |             0.625  |
| stave       | B4                     | 1d_cnn                              |                  0.6757 |                     0.07476 |            11.94  |             0.4217 |
| stave       | B6                     | 1d_cnn                              |                  0.7965 |                     0.105   |             9.933 |             0.3864 |
| stave       | B8                     | 1d_cnn                              |                  0.745  |                     0.09341 |            10.32  |             0.2989 |
| stave       | B2                     | deltaE_over_E_likelihood_template   |                  0.8105 |                     0.1098  |            16.26  |             0.7639 |
| stave       | B4                     | deltaE_over_E_likelihood_template   |                  0.7489 |                     0.07138 |            18.22  |             0.8916 |
| stave       | B6                     | deltaE_over_E_likelihood_template   |                  0.8236 |                     0.1303  |             8.499 |             0.6591 |
| stave       | B8                     | deltaE_over_E_likelihood_template   |                  0.732  |                     0.08108 |             5.498 |             0.3793 |
| stave       | B2                     | gradient_boosted_trees              |                  0.8549 |                     0.08112 |             9.782 |             0.5278 |
| stave       | B4                     | gradient_boosted_trees              |                  0.8407 |                     0.07306 |             7.244 |             0.3133 |
| stave       | B6                     | gradient_boosted_trees              |                  0.8791 |                     0.0851  |             6.593 |             0.2273 |
| stave       | B8                     | gradient_boosted_trees              |                  0.8393 |                     0.1065  |             6.988 |             0.1264 |
| stave       | B2                     | joint_sequence_transformer          |                  0.4938 |                     0.1247  |            15.49  |             0.5417 |
| stave       | B4                     | joint_sequence_transformer          |                  0.5496 |                     0.1394  |            12.98  |             0.3133 |
| stave       | B6                     | joint_sequence_transformer          |                  0.4947 |                     0.117   |            10.71  |             0.3068 |
| stave       | B8                     | joint_sequence_transformer          |                  0.5238 |                     0.1282  |            12.17  |             0.1839 |
| stave       | B2                     | mlp                                 |                  0.7084 |                     0.1142  |            12.43  |             0.5417 |
| stave       | B4                     | mlp                                 |                  0.6034 |                     0.1013  |            11.09  |             0.3373 |
| stave       | B6                     | mlp                                 |                  0.7524 |                     0.09989 |             9.948 |             0.2614 |
| stave       | B8                     | mlp                                 |                  0.719  |                     0.1241  |            10.87  |             0.1954 |
| stave       | B2                     | ridge                               |                  0.7385 |                     0.07999 |            11.84  |             0.5139 |
| stave       | B4                     | ridge                               |                  0.6859 |                     0.05946 |             9.491 |             0.3494 |
| stave       | B6                     | ridge                               |                  0.7939 |                     0.1028  |             8.621 |             0.25   |
| stave       | B8                     | ridge                               |                  0.746  |                     0.1065  |             8.973 |             0.1954 |
| stave       | B2                     | template_residual_boosted_stack_new |                  0.8534 |                     0.0742  |            10.44  |             0.4861 |
| stave       | B4                     | template_residual_boosted_stack_new |                  0.8546 |                     0.07837 |             7.213 |             0.3133 |
| stave       | B6                     | template_residual_boosted_stack_new |                  0.8965 |                     0.089   |             5.932 |             0.25   |
| stave       | B8                     | template_residual_boosted_stack_new |                  0.8341 |                     0.0964  |             7.623 |             0.1264 |
| pid_truth   | deuteron_like          | 1d_cnn                              |                  0.6258 |                     0.09721 |            11.88  |             0.4311 |
| pid_truth   | proton_like            | 1d_cnn                              |                  0.8363 |                     0.09984 |            10.83  |             0.4172 |
| pid_truth   | deuteron_like          | deltaE_over_E_likelihood_template   |                  0.7327 |                     0.09551 |             9.679 |             0.6707 |
| pid_truth   | proton_like            | deltaE_over_E_likelihood_template   |                  0.8216 |                     0.1513  |             7.496 |             0.6626 |
| pid_truth   | deuteron_like          | gradient_boosted_trees              |                  0.8962 |                     0.08657 |             8.737 |             0.2754 |
| pid_truth   | proton_like            | gradient_boosted_trees              |                  0.8129 |                     0.0869  |             7.507 |             0.3006 |
| pid_truth   | deuteron_like          | joint_sequence_transformer          |                  0.1226 |                     0.1257  |            13.46  |             0.2994 |
| pid_truth   | proton_like            | joint_sequence_transformer          |                  0.9094 |                     0.1358  |            11.12  |             0.3558 |
| pid_truth   | deuteron_like          | mlp                                 |                  0.5975 |                     0.1162  |            11.3   |             0.3174 |
| pid_truth   | proton_like            | mlp                                 |                  0.7865 |                     0.09567 |            11.49  |             0.3313 |
| pid_truth   | deuteron_like          | ridge                               |                  0.6635 |                     0.08509 |             9.369 |             0.3234 |
| pid_truth   | proton_like            | ridge                               |                  0.8187 |                     0.1027  |             9.512 |             0.3129 |
| pid_truth   | deuteron_like          | template_residual_boosted_stack_new |                  0.8994 |                     0.09979 |             8.349 |             0.2695 |
| pid_truth   | proton_like            | template_residual_boosted_stack_new |                  0.8216 |                     0.0841  |             7.801 |             0.3006 |

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

Runtime was `63.2` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

## Ticket-local scope

This wrapper is ticket-local to `1783826036.4798.37744dd6`.  It keeps the validated raw ROOT reproduction, controlled pile-up injection, pedestal-stratified sidebands, saturation masks, PID/energy sideband audits, run-heldout split, and run-block bootstrap confidence intervals from the reusable S29/S26 implementation, but all outputs in this directory were regenerated after the ticket was claimed by `testbeam-laptop-4`.

## Pedestal, saturation, energy, and PID sidebands

The ticket-named sideband audit is separated from the global winner rule. The saturation mask uses the digitized corrected waveform maximum, the pedestal slices use held-out pretrigger medians, energy sidebands use GEANT4 total Sci_bar energy, and PID sidebands use dominant Sci_bar PDG. Rows are held-out only and preserve the same run-disjoint model fits.

| sideband        | value       | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:----------------|:------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| energy_sideband | high_edep   | 1d_cnn                              |                  0.6584 |                     0.09311 |            10.95  |             0.4273 |            0.1364  |
| energy_sideband | high_edep   | deltaE_over_E_likelihood_template   |                  0.7199 |                     0.1039  |            10.16  |             0.7    |            0.09091 |
| energy_sideband | high_edep   | gradient_boosted_trees              |                  0.753  |                     0.09297 |             7.331 |             0.2636 |            0.2182  |
| energy_sideband | high_edep   | joint_sequence_transformer          |                  0.5069 |                     0.1255  |            12.01  |             0.3364 |            0.2182  |
| energy_sideband | high_edep   | mlp                                 |                  0.6305 |                     0.1174  |            11.4   |             0.3182 |            0.2455  |
| energy_sideband | high_edep   | ridge                               |                  0.6625 |                     0.1569  |             9.343 |             0.3273 |            0.1727  |
| energy_sideband | high_edep   | template_residual_boosted_stack_new |                  0.7844 |                     0.1015  |             7.58  |             0.2364 |            0.2     |
| energy_sideband | low_edep    | 1d_cnn                              |                  0.7495 |                     0.09472 |            11.78  |             0.4128 |            0.1532  |
| energy_sideband | low_edep    | deltaE_over_E_likelihood_template   |                  0.7316 |                     0.07247 |             6.613 |             0.6514 |            0.1441  |
| energy_sideband | low_edep    | gradient_boosted_trees              |                  0.8711 |                     0.09763 |             9.264 |             0.367  |            0.2523  |
| energy_sideband | low_edep    | joint_sequence_transformer          |                  0.5251 |                     0.1256  |            12.73  |             0.3303 |            0.2342  |
| energy_sideband | low_edep    | mlp                                 |                  0.7054 |                     0.09361 |            10.17  |             0.3853 |            0.1892  |
| energy_sideband | low_edep    | ridge                               |                  0.8359 |                     0.08939 |             9.744 |             0.3394 |            0.1892  |
| energy_sideband | low_edep    | template_residual_boosted_stack_new |                  0.851  |                     0.08489 |             8.472 |             0.3945 |            0.2523  |
| energy_sideband | mid_edep    | 1d_cnn                              |                  0.7728 |                     0.09278 |            10.84  |             0.4324 |            0.1468  |
| energy_sideband | mid_edep    | deltaE_over_E_likelihood_template   |                  0.8471 |                     0.1419  |            10.03  |             0.6486 |            0.1284  |
| energy_sideband | mid_edep    | gradient_boosted_trees              |                  0.9304 |                     0.07679 |             7.423 |             0.2342 |            0.3028  |
| energy_sideband | mid_edep    | joint_sequence_transformer          |                  0.5155 |                     0.1334  |            11.27  |             0.3153 |            0.2752  |
| energy_sideband | mid_edep    | mlp                                 |                  0.7224 |                     0.1154  |            11.77  |             0.2703 |            0.2844  |
| energy_sideband | mid_edep    | ridge                               |                  0.7286 |                     0.09336 |             8.372 |             0.2883 |            0.2936  |
| energy_sideband | mid_edep    | template_residual_boosted_stack_new |                  0.9356 |                     0.07931 |             8.242 |             0.2252 |            0.3119  |
| pedestal_slice  | high        | 1d_cnn                              |                  0.7283 |                     0.09993 |            11.44  |             0.275  |            0.18    |
| pedestal_slice  | high        | deltaE_over_E_likelihood_template   |                  0.7886 |                     0.1238  |             6.962 |             0.6083 |            0.14    |
| pedestal_slice  | high        | gradient_boosted_trees              |                  0.8654 |                     0.09005 |             7.096 |             0.2417 |            0.32    |
| pedestal_slice  | high        | joint_sequence_transformer          |                  0.5162 |                     0.1102  |            11.6   |             0.2333 |            0.25    |
| pedestal_slice  | high        | mlp                                 |                  0.679  |                     0.11    |            11.77  |             0.25   |            0.27    |
| pedestal_slice  | high        | ridge                               |                  0.7409 |                     0.1     |             9.559 |             0.225  |            0.29    |
| pedestal_slice  | high        | template_residual_boosted_stack_new |                  0.8696 |                     0.0949  |             7.455 |             0.2167 |            0.3     |
| pedestal_slice  | low         | 1d_cnn                              |                  0.7323 |                     0.1148  |            11.03  |             0.5524 |            0.09565 |
| pedestal_slice  | low         | deltaE_over_E_likelihood_template   |                  0.7726 |                     0.1259  |            13     |             0.6762 |            0.1217  |
| pedestal_slice  | low         | gradient_boosted_trees              |                  0.8278 |                     0.08963 |             7.537 |             0.3619 |            0.2261  |
| pedestal_slice  | low         | joint_sequence_transformer          |                  0.4942 |                     0.1304  |            11.69  |             0.419  |            0.2     |
| pedestal_slice  | low         | mlp                                 |                  0.6761 |                     0.15    |            12.3   |             0.4095 |            0.2174  |
| pedestal_slice  | low         | ridge                               |                  0.733  |                     0.1052  |             9.117 |             0.3905 |            0.1565  |
| pedestal_slice  | low         | template_residual_boosted_stack_new |                  0.841  |                     0.08438 |             7.414 |             0.3429 |            0.2348  |
| pedestal_slice  | middle      | 1d_cnn                              |                  0.7379 |                     0.08001 |            11.17  |             0.4667 |            0.1652  |
| pedestal_slice  | middle      | deltaE_over_E_likelihood_template   |                  0.7804 |                     0.07344 |             7.212 |             0.7238 |            0.1043  |
| pedestal_slice  | middle      | gradient_boosted_trees              |                  0.8697 |                     0.08571 |             9.108 |             0.2667 |            0.2348  |
| pedestal_slice  | middle      | joint_sequence_transformer          |                  0.534  |                     0.1499  |            12.57  |             0.3429 |            0.2783  |
| pedestal_slice  | middle      | mlp                                 |                  0.7332 |                     0.09303 |             9.444 |             0.3238 |            0.2348  |
| pedestal_slice  | middle      | ridge                               |                  0.7571 |                     0.08316 |             9.385 |             0.3524 |            0.2174  |
| pedestal_slice  | middle      | template_residual_boosted_stack_new |                  0.8694 |                     0.08132 |             8.206 |             0.3048 |            0.2348  |
| pid_name        | deuteron    | 1d_cnn                              |                  0.6258 |                     0.09721 |            11.88  |             0.4311 |            0.1589  |
| pid_name        | deuteron    | deltaE_over_E_likelihood_template   |                  0.7327 |                     0.09551 |             9.679 |             0.6707 |            0.1457  |
| pid_name        | deuteron    | gradient_boosted_trees              |                  0.8962 |                     0.08657 |             8.737 |             0.2754 |            0.2848  |
| pid_name        | deuteron    | joint_sequence_transformer          |                  0.1226 |                     0.1257  |            13.46  |             0.2994 |            0.2384  |
| pid_name        | deuteron    | mlp                                 |                  0.5975 |                     0.1162  |            11.3   |             0.3174 |            0.298   |
| pid_name        | deuteron    | ridge                               |                  0.6635 |                     0.08509 |             9.369 |             0.3234 |            0.2583  |
| pid_name        | deuteron    | template_residual_boosted_stack_new |                  0.8994 |                     0.09979 |             8.349 |             0.2695 |            0.2517  |
| pid_name        | proton      | 1d_cnn                              |                  0.8363 |                     0.09984 |            10.83  |             0.4172 |            0.1341  |
| pid_name        | proton      | deltaE_over_E_likelihood_template   |                  0.8216 |                     0.1513  |             7.496 |             0.6626 |            0.1006  |
| pid_name        | proton      | gradient_boosted_trees              |                  0.8129 |                     0.0869  |             7.507 |             0.3006 |            0.2346  |
| pid_name        | proton      | joint_sequence_transformer          |                  0.9094 |                     0.1358  |            11.12  |             0.3558 |            0.2458  |
| pid_name        | proton      | mlp                                 |                  0.7865 |                     0.09567 |            11.49  |             0.3313 |            0.1899  |
| pid_name        | proton      | ridge                               |                  0.8187 |                     0.1027  |             9.512 |             0.3129 |            0.1844  |
| pid_name        | proton      | template_residual_boosted_stack_new |                  0.8216 |                     0.0841  |             7.801 |             0.3006 |            0.257   |
| saturation_mask | saturated   | 1d_cnn                              |                  0.696  |                     0.06594 |            10.3   |             0.4539 |            0.1474  |
| saturation_mask | saturated   | deltaE_over_E_likelihood_template   |                  0.7972 |                     0.08965 |            12.07  |             0.7518 |            0.06316 |
| saturation_mask | saturated   | gradient_boosted_trees              |                  0.8393 |                     0.05046 |             6.915 |             0.227  |            0.3474  |
| saturation_mask | saturated   | joint_sequence_transformer          |                  0.4941 |                     0.09737 |            12.94  |             0.3546 |            0.2737  |
| saturation_mask | saturated   | mlp                                 |                  0.6561 |                     0.1049  |            10.44  |             0.2837 |            0.2737  |
| saturation_mask | saturated   | ridge                               |                  0.6794 |                     0.05562 |             8.566 |             0.3333 |            0.2105  |
| saturation_mask | saturated   | template_residual_boosted_stack_new |                  0.8684 |                     0.05607 |             7.322 |             0.2199 |            0.3263  |
| saturation_mask | unsaturated | 1d_cnn                              |                  0.751  |                     0.1167  |            11.97  |             0.4021 |            0.1447  |
| saturation_mask | unsaturated | deltaE_over_E_likelihood_template   |                  0.7678 |                     0.1234  |             7.439 |             0.6032 |            0.1447  |
| saturation_mask | unsaturated | gradient_boosted_trees              |                  0.8636 |                     0.1262  |             9.44  |             0.3333 |            0.2213  |
| saturation_mask | unsaturated | joint_sequence_transformer          |                  0.5275 |                     0.1352  |            11.94  |             0.3069 |            0.2298  |
| saturation_mask | unsaturated | mlp                                 |                  0.713  |                     0.1206  |            11.73  |             0.3545 |            0.2255  |
| saturation_mask | unsaturated | ridge                               |                  0.7757 |                     0.1224  |            10.01  |             0.3069 |            0.2213  |
| saturation_mask | unsaturated | template_residual_boosted_stack_new |                  0.8566 |                     0.1261  |             8.838 |             0.3333 |            0.2255  |

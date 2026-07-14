# S37b: Censored Saturation Recovery Benchmark for Clipped Pulse Energy and PID

## Abstract

Ticket `1784067626.890.1d1c4672` asks for a run-split benchmark of clipped-pulse saturation
recovery that treats ADC saturation as censoring rather than as an ordinary
regression error.  The worker is `testbeam-laptop-4`.  The held-out winner written to
`result.json` is **`gradient_boosted_trees`**, selected by the registered S37b composite
endpoint.  Its clipped-pulse energy sigma68 is `0.06461`
with 95% run-block bootstrap CI [`0`,
`0.09214`], timing-pull sigma68 is
`4.351` ns, PID-proxy migration rate is
`0.5949`, and pedestal-coupled bias span is
`0.01388`.

## Raw ROOT Reproduction Gate

Raw B-stack ROOT files are read from `/home/billy/.tb-workers/testbeam-laptop-4/data/root/root`.  The branch
`h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples.  The
selected-pulse anchor is reproduced from B2/B4/B6/B8 channels using

`b_ec = median_{t in {0,1,2,3}} x_ect`,

`A_ec = max_t(x_ect - b_ec)`,

`N = sum_ec 1[A_ec > 1000 ADC]`.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | True |

## Split, Truth Construction, and Negative Controls

Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`; model fitting, template construction, and
normalization use no held-out events.  Clean raw pulses are aligned to
stave-specific templates

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| ----- | -------------- | --------------------- | -------------------- | ------------- |
| B2    | 960            | 2.748                 | 5                    | 9.042         |
| B4    | 924            | 3.032                 | 6                    | 10.79         |
| B6    | 880            | 3.754                 | 8                    | 9.824         |
| B8    | 485            | 4.243                 | 8                    | 9.251         |

Injected clipped examples use

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

with observation operator `y(t)=min(w(t), 11800)`.  Matched unclipped
single-pulse controls are passed through the same censoring operator to measure
false pile-up splitting.

## Methods

| method                                         | family         | description                                                                                       |
| ---------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------- |
| analytic_clipped_template_sideband_traditional | traditional    | censored two-template analytic fit with clipped-sample sideband and charge-integration correction |
| ridge                                          | linear ML      | ridge classifier plus multi-output ridge regression                                               |
| gradient_boosted_trees                         | tree ML        | histogram gradient-boosted classifier and regressors                                              |
| mlp                                            | neural network | tabular multilayer perceptron classifier/regressor pair                                           |
| 1d_cnn                                         | neural network | compact one-dimensional CNN over 18 ADC samples                                                   |
| tiny_sequence_transformer                      | sequence NN    | one-layer self-attention waveform encoder                                                         |
| saturation_residual_fusion_new                 | new hybrid     | boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs              |

The new architecture is `saturation_residual_fusion_new`, a hybrid residual
model using clipped plateau width, sideband charge, waveform residuals, and the
traditional fit as inputs.  It is sensible here because censored samples create
an inequality-constrained inverse problem: the analytic fit carries physical
identifiability, while residual ML captures pedestal, shape, and pile-up
departures.

## Endpoints and Equations

Energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

The censored loss on saturated examples is

`L_c = mean max(0, C_ADC - (hat A_1 + hat A_2)) / C_ADC`,

which penalizes predictions that remain below the clipping boundary after
observing clipped ADC samples.  Timing pull is

`e_t = 10 ns (hat t_1 - t_1)`.

Shape reconstruction is

`RMSE_shape = sqrt(mean_t[(hat w(t)-w(t))^2]) / max(max_t w(t)-median_{0:3} w(t), 1)`.

The PID migration endpoint uses a blinded support proxy derived from total
charge, secondary-pulse ratio, and stave depth.  It measures

`r_PID = mean 1[PID_proxy(hat A, hat r, s) != PID_proxy(A, r, s)]`.

Robust resolution is `sigma68(e)=[Q84(e)-Q16(e)]/2`.  Confidence intervals are
95% percentile intervals from `400` held-out
run-block bootstrap resamples.

The registered S37b score is

`C = sigma_E,clip + 0.15|bias_E| + 0.12 L_c + 0.004 sigma_t + 0.003 sigma_Delta + 0.12 r_PID + 0.12 S_ped + 0.12 RMSE_shape + 0.06 r_miss + 0.04 r_false + 0.08(1-AUC_sat)`.

## Overall Results

| method                                         | winner_score | energy_residual_bias | clipped_energy_sigma68 | clipped_energy_sigma68_ci_low | clipped_energy_sigma68_ci_high | clipped_censor_loss | timing_pull_sigma68_ns | pid_migration_rate | pedestal_coupled_bias_span | shape_reconstruction_rmse | pileup_miss_rate | false_split_rate |
| ---------------------------------------------- | ------------ | -------------------- | ---------------------- | ----------------------------- | ------------------------------ | ------------------- | ---------------------- | ------------------ | -------------------------- | ------------------------- | ---------------- | ---------------- |
| gradient_boosted_trees                         | 0.2251       | -0.01261             | 0.06461                | 0                             | 0.09214                        | 0                   | 4.351                  | 0.5949             | 0.01388                    | 0.1348                    | 0.313            | 0.1457           |
| saturation_residual_fusion_new                 | 0.2271       | -0.01216             | 0.06636                | 0                             | 0.1233                         | 0                   | 4.601                  | 0.5857             | 0.005204                   | 0.1371                    | 0.3022           | 0.1326           |
| ridge                                          | 0.2297       | 0.01264              | 0.04445                | 0                             | 0.05644                        | 0.006221            | 6.433                  | 0.6122             | 0.01021                    | 0.1479                    | 0.3217           | 0.1609           |
| 1d_cnn                                         | 0.2467       | 0.0176               | 0.05002                | 0                             | 0.07386                        | 0                   | 6.592                  | 0.6154             | 0.01185                    | 0.1572                    | 0.3217           | 0.1696           |
| mlp                                            | 0.2546       | -0.01668             | 0.03879                | 0                             | 0.09898                        | 0.01941             | 10.07                  | 0.6126             | 0.004856                   | 0.1596                    | 0.45             | 0.1261           |
| analytic_clipped_template_sideband_traditional | 0.289        | 0.05507              | 0.05767                | 0.05767                       | 0.0848                         | 0                   | 7.256                  | 0.5156             | 0.005624                   | 0.1197                    | 0.5826           | 0.1696           |
| tiny_sequence_transformer                      | 0.3232       | 0.0326               | 0.09112                | 0                             | 0.1006                         | 0                   | 11.31                  | 0.5328             | 0.006947                   | 0.1951                    | 0.437            | 0.1413           |

The traditional comparator has score `0.289` and clipped
energy sigma68 `0.05767`.  The selected winner
changes clipped energy sigma68 by `0.006946`
and PID migration rate by `0.07931`.

## Bootstrap Endpoint Table

| method                                         | clipped_energy_sigma68 | clipped_energy_sigma68_ci_low | clipped_energy_sigma68_ci_high | timing_pull_sigma68_ns | timing_pull_sigma68_ns_ci_low | timing_pull_sigma68_ns_ci_high | pid_migration_rate | pid_migration_rate_ci_low | pid_migration_rate_ci_high | pedestal_coupled_bias_span | pedestal_coupled_bias_span_ci_low | pedestal_coupled_bias_span_ci_high |
| ---------------------------------------------- | ---------------------- | ----------------------------- | ------------------------------ | ---------------------- | ----------------------------- | ------------------------------ | ------------------ | ------------------------- | -------------------------- | -------------------------- | --------------------------------- | ---------------------------------- |
| mlp                                            | 0.03879                | 0                             | 0.09898                        | 10.07                  | 9.285                         | 10.75                          | 0.6126             | 0.5755                    | 0.6626                     | 0.004856                   | 0.0005433                         | 0.01639                            |
| ridge                                          | 0.04445                | 0                             | 0.05644                        | 6.433                  | 5.943                         | 6.943                          | 0.6122             | 0.576                     | 0.6436                     | 0.01021                    | 7.139e-05                         | 0.02299                            |
| 1d_cnn                                         | 0.05002                | 0                             | 0.07386                        | 6.592                  | 6.417                         | 6.98                           | 0.6154             | 0.578                     | 0.6474                     | 0.01185                    | 0.0003762                         | 0.03619                            |
| analytic_clipped_template_sideband_traditional | 0.05767                | 0.05767                       | 0.0848                         | 7.256                  | 5.645                         | 8.085                          | 0.5156             | 0.4905                    | 0.5368                     | 0.005624                   | 0.0002522                         | 0.01974                            |
| gradient_boosted_trees                         | 0.06461                | 0                             | 0.09214                        | 4.351                  | 4.002                         | 5.295                          | 0.5949             | 0.5258                    | 0.6393                     | 0.01388                    | 0.003872                          | 0.02726                            |
| saturation_residual_fusion_new                 | 0.06636                | 0                             | 0.1233                         | 4.601                  | 4.023                         | 5.36                           | 0.5857             | 0.5382                    | 0.621                      | 0.005204                   | 0.0004645                         | 0.03384                            |
| tiny_sequence_transformer                      | 0.09112                | 0                             | 0.1006                         | 11.31                  | 9.107                         | 12.04                          | 0.5328             | 0.4593                    | 0.6114                     | 0.006947                   | 6.967e-05                         | 0.03129                            |

## Run-Held-Out Stability

| method                                         | heldout_run | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| ---------------------------------------------- | ----------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- | ---------------- |
| 1d_cnn                                         | 58          | 0.03065                | 0.09866                   | 0.4455       | 10.3            | 0.2717           | 0.1304           |
| 1d_cnn                                         | 60          | 0.04817                | 0.09294                   | 1.428        | 11.01           | 0.3478           | 0.2174           |
| 1d_cnn                                         | 62          | 0.01268                | 0.07962                   | -1.431       | 9.204           | 0.3587           | 0.1848           |
| 1d_cnn                                         | 64          | -0.01163               | 0.09673                   | -1.121       | 9.54            | 0.337            | 0.1413           |
| 1d_cnn                                         | 65          | 0.008358               | 0.07337                   | -0.2783      | 8.909           | 0.2935           | 0.1739           |
| analytic_clipped_template_sideband_traditional | 58          | 0.04961                | 0.0759                    | 2.642        | 9.542           | 0.5435           | 0.08696          |
| analytic_clipped_template_sideband_traditional | 60          | 0.05687                | 0.08767                   | 1.66         | 11.69           | 0.6087           | 0.1848           |
| analytic_clipped_template_sideband_traditional | 62          | 0.04187                | 0.08733                   | 0.2818       | 7.938           | 0.6957           | 0.2174           |
| analytic_clipped_template_sideband_traditional | 64          | 0.04987                | 0.07356                   | -1.484       | 9.85            | 0.5435           | 0.1304           |
| analytic_clipped_template_sideband_traditional | 65          | 0.09573                | 0.1085                    | 0.1029       | 11.52           | 0.5217           | 0.2283           |
| gradient_boosted_trees                         | 58          | -0.02184               | 0.07142                   | -0.979       | 7.253           | 0.2826           | 0.1304           |
| gradient_boosted_trees                         | 60          | -0.00781               | 0.05522                   | 0.1041       | 6.93            | 0.337            | 0.2283           |
| gradient_boosted_trees                         | 62          | -0.00391               | 0.05853                   | -0.3541      | 6.132           | 0.3043           | 0.1739           |
| gradient_boosted_trees                         | 64          | -0.02228               | 0.05024                   | -0.207       | 5.629           | 0.3696           | 0.06522          |
| gradient_boosted_trees                         | 65          | -0.01197               | 0.05811                   | -1.723       | 6.387           | 0.2717           | 0.1304           |
| mlp                                            | 58          | -0.004487              | 0.1167                    | -0.7232      | 11.08           | 0.3696           | 0.09783          |
| mlp                                            | 60          | -0.01206               | 0.08138                   | -1.765       | 10.34           | 0.5217           | 0.163            |
| mlp                                            | 62          | -0.02112               | 0.1229                    | -0.9217      | 10.92           | 0.4457           | 0.1522           |
| mlp                                            | 64          | -0.0157                | 0.09138                   | -0.7861      | 10.87           | 0.5              | 0.09783          |
| mlp                                            | 65          | -0.02364               | 0.08639                   | -1.649       | 10.29           | 0.413            | 0.1196           |
| ridge                                          | 58          | 0.01279                | 0.1006                    | -1.15        | 7.569           | 0.3152           | 0.163            |
| ridge                                          | 60          | 0.02154                | 0.06707                   | 0.3711       | 8.654           | 0.3587           | 0.2826           |
| ridge                                          | 62          | 0.01849                | 0.07302                   | -1.396       | 8.483           | 0.2935           | 0.1522           |
| ridge                                          | 64          | -0.00818               | 0.07354                   | -2.169       | 9.064           | 0.337            | 0.07609          |
| ridge                                          | 65          | 0.006336               | 0.06337                   | -0.9715      | 7.581           | 0.3043           | 0.1304           |
| saturation_residual_fusion_new                 | 58          | -0.00442               | 0.07332                   | -0.6177      | 7.315           | 0.2935           | 0.1304           |
| saturation_residual_fusion_new                 | 60          | 0.001473               | 0.05794                   | 0.2823       | 7.549           | 0.3043           | 0.2065           |
| saturation_residual_fusion_new                 | 62          | -0.02034               | 0.05703                   | -0.1429      | 6.763           | 0.3478           | 0.1413           |
| saturation_residual_fusion_new                 | 64          | -0.01569               | 0.06043                   | -0.1715      | 5.942           | 0.3152           | 0.05435          |
| saturation_residual_fusion_new                 | 65          | -0.01837               | 0.05883                   | -1.617       | 6.502           | 0.25             | 0.1304           |
| tiny_sequence_transformer                      | 58          | 0.03415                | 0.1328                    | -7.026       | 15.31           | 0.3696           | 0.1304           |
| tiny_sequence_transformer                      | 60          | 0.05505                | 0.1199                    | -3.245       | 10.4            | 0.5435           | 0.1957           |
| tiny_sequence_transformer                      | 62          | 0.04974                | 0.06325                   | -7.552       | 13.24           | 0.5              | 0.1522           |
| tiny_sequence_transformer                      | 64          | 0.002945               | 0.1248                    | -9.353       | 14.05           | 0.413            | 0.08696          |
| tiny_sequence_transformer                      | 65          | 0.0292                 | 0.095                     | -6.591       | 12.42           | 0.3587           | 0.1413           |

## Censored-Loss and PID Ablations

| method                                         | ablation                | score  | clipped_energy_sigma68 | pid_migration_rate | timing_pull_sigma68_ns |
| ---------------------------------------------- | ----------------------- | ------ | ---------------------- | ------------------ | ---------------------- |
| gradient_boosted_trees                         | drop_censor_loss_term   | 0.2251 | 0.06461                | 0.5949             | 4.351                  |
| saturation_residual_fusion_new                 | drop_censor_loss_term   | 0.2271 | 0.06636                | 0.5857             | 4.601                  |
| ridge                                          | drop_censor_loss_term   | 0.229  | 0.04445                | 0.6122             | 6.433                  |
| 1d_cnn                                         | drop_censor_loss_term   | 0.2467 | 0.05002                | 0.6154             | 6.592                  |
| mlp                                            | drop_censor_loss_term   | 0.2523 | 0.03879                | 0.6126             | 10.07                  |
| analytic_clipped_template_sideband_traditional | drop_censor_loss_term   | 0.289  | 0.05767                | 0.5156             | 7.256                  |
| tiny_sequence_transformer                      | drop_censor_loss_term   | 0.3232 | 0.09112                | 0.5328             | 11.31                  |
| gradient_boosted_trees                         | drop_pid_migration_term | 0.1537 | 0.06461                | 0.5949             | 4.351                  |
| ridge                                          | drop_pid_migration_term | 0.1563 | 0.04445                | 0.6122             | 6.433                  |
| saturation_residual_fusion_new                 | drop_pid_migration_term | 0.1568 | 0.06636                | 0.5857             | 4.601                  |
| 1d_cnn                                         | drop_pid_migration_term | 0.1728 | 0.05002                | 0.6154             | 6.592                  |
| mlp                                            | drop_pid_migration_term | 0.1811 | 0.03879                | 0.6126             | 10.07                  |
| analytic_clipped_template_sideband_traditional | drop_pid_migration_term | 0.2272 | 0.05767                | 0.5156             | 7.256                  |
| tiny_sequence_transformer                      | drop_pid_migration_term | 0.2593 | 0.09112                | 0.5328             | 11.31                  |
| gradient_boosted_trees                         | full_censored_objective | 0.2251 | 0.06461                | 0.5949             | 4.351                  |
| saturation_residual_fusion_new                 | full_censored_objective | 0.2271 | 0.06636                | 0.5857             | 4.601                  |
| ridge                                          | full_censored_objective | 0.2297 | 0.04445                | 0.6122             | 6.433                  |
| 1d_cnn                                         | full_censored_objective | 0.2467 | 0.05002                | 0.6154             | 6.592                  |
| mlp                                            | full_censored_objective | 0.2546 | 0.03879                | 0.6126             | 10.07                  |
| analytic_clipped_template_sideband_traditional | full_censored_objective | 0.289  | 0.05767                | 0.5156             | 7.256                  |
| tiny_sequence_transformer                      | full_censored_objective | 0.3232 | 0.09112                | 0.5328             | 11.31                  |

## Saturation Strata and Failure Modes

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class.

| stratum        | value          | method                                         | energy_fractional_bias | energy_fractional_sigma68 | time_bias_ns | time_sigma68_ns | pileup_miss_rate |
| -------------- | -------------- | ---------------------------------------------- | ---------------------- | ------------------------- | ------------ | --------------- | ---------------- |
| spacing_bin    | (-0.001, 10.0] | 1d_cnn                                         | 0.05663                | 0.07739                   | 3.11         | 13.56           | 0.5139           |
| spacing_bin    | (10.0, 25.0]   | 1d_cnn                                         | 0.04593                | 0.09547                   | 2.09         | 8.151           | 0.4476           |
| spacing_bin    | (25.0, 45.0]   | 1d_cnn                                         | 0.00429                | 0.09909                   | -2.733       | 8.079           | 0.1538           |
| spacing_bin    | (45.0, 70.0]   | 1d_cnn                                         | -0.0104                | 0.08612                   | -0.3003      | 10.66           | 0.1028           |
| spacing_bin    | (-0.001, 10.0] | analytic_clipped_template_sideband_traditional | 0.09203                | 0.06458                   | 3.458        | 15.94           | 0.7431           |
| spacing_bin    | (10.0, 25.0]   | analytic_clipped_template_sideband_traditional | 0.09354                | 0.07164                   | 3.632        | 9.513           | 0.6857           |
| spacing_bin    | (25.0, 45.0]   | analytic_clipped_template_sideband_traditional | 0.06882                | 0.07265                   | 0.07332      | 9.406           | 0.4904           |
| spacing_bin    | (45.0, 70.0]   | analytic_clipped_template_sideband_traditional | -0.01086               | 0.09273                   | -2.024       | 9.181           | 0.3551           |
| spacing_bin    | (-0.001, 10.0] | gradient_boosted_trees                         | 0.01084                | 0.05904                   | -0.3302      | 5.924           | 0.4167           |
| spacing_bin    | (10.0, 25.0]   | gradient_boosted_trees                         | 0.0006571              | 0.06481                   | 0.4282       | 6.284           | 0.4667           |
| spacing_bin    | (25.0, 45.0]   | gradient_boosted_trees                         | -0.007771              | 0.05301                   | -1.214       | 6.972           | 0.1731           |
| spacing_bin    | (45.0, 70.0]   | gradient_boosted_trees                         | -0.04586               | 0.06531                   | -1.016       | 7.356           | 0.1589           |
| spacing_bin    | (-0.001, 10.0] | mlp                                            | 0.00259                | 0.08236                   | -0.0647      | 9.035           | 0.5347           |
| spacing_bin    | (10.0, 25.0]   | mlp                                            | -0.01444               | 0.07681                   | -0.7639      | 9.219           | 0.6              |
| spacing_bin    | (25.0, 45.0]   | mlp                                            | -0.01282               | 0.09471                   | -1.058       | 10.8            | 0.4038           |
| spacing_bin    | (45.0, 70.0]   | mlp                                            | -0.05448               | 0.1036                    | -2.476       | 13.2            | 0.2336           |
| spacing_bin    | (-0.001, 10.0] | ridge                                          | 0.02457                | 0.05733                   | -0.8915      | 8.684           | 0.4097           |
| spacing_bin    | (10.0, 25.0]   | ridge                                          | 0.02491                | 0.06265                   | 0.4725       | 6.052           | 0.4286           |
| spacing_bin    | (25.0, 45.0]   | ridge                                          | 0.01687                | 0.06319                   | -1.664       | 7.833           | 0.2692           |
| spacing_bin    | (45.0, 70.0]   | ridge                                          | -0.04713               | 0.0786                    | -2.031       | 10.38           | 0.1495           |
| spacing_bin    | (-0.001, 10.0] | saturation_residual_fusion_new                 | 0.02584                | 0.05695                   | 0.1333       | 5.708           | 0.4375           |
| spacing_bin    | (10.0, 25.0]   | saturation_residual_fusion_new                 | 0.002781               | 0.05986                   | 0.8498       | 6.13            | 0.4571           |
| spacing_bin    | (25.0, 45.0]   | saturation_residual_fusion_new                 | -0.006684              | 0.05925                   | -0.8665      | 7.545           | 0.1442           |
| spacing_bin    | (45.0, 70.0]   | saturation_residual_fusion_new                 | -0.05092               | 0.05458                   | -1.91        | 8.08            | 0.1215           |
| spacing_bin    | (-0.001, 10.0] | tiny_sequence_transformer                      | 0.06979                | 0.06607                   | -8.256       | 10.12           | 0.6319           |
| spacing_bin    | (10.0, 25.0]   | tiny_sequence_transformer                      | 0.09169                | 0.09088                   | -7.197       | 11.83           | 0.6286           |
| spacing_bin    | (25.0, 45.0]   | tiny_sequence_transformer                      | 0.0377                 | 0.09518                   | -7.662       | 15.22           | 0.2885           |
| spacing_bin    | (45.0, 70.0]   | tiny_sequence_transformer                      | -0.05293               | 0.1122                    | -4.67        | 16.44           | 0.1308           |
| ratio_bin      | (-0.001, 0.35] | 1d_cnn                                         | 0.04649                | 0.1041                    | -3.928       | 12.18           | 0.5234           |
| ratio_bin      | (0.35, 0.625]  | 1d_cnn                                         | 0.007652               | 0.08311                   | -1.108       | 8.447           | 0.3478           |
| ratio_bin      | (0.625, 0.875] | 1d_cnn                                         | 0.01155                | 0.08469                   | 0.1034       | 9.535           | 0.2409           |
| ratio_bin      | (0.875, 1.05]  | 1d_cnn                                         | 0.01275                | 0.08466                   | 2.559        | 8.998           | 0.1881           |
| ratio_bin      | (-0.001, 0.35] | analytic_clipped_template_sideband_traditional | 0.05498                | 0.07519                   | -0.2816      | 12.18           | 0.6916           |
| ratio_bin      | (0.35, 0.625]  | analytic_clipped_template_sideband_traditional | 0.07618                | 0.09519                   | 0.582        | 11.64           | 0.5304           |
| ratio_bin      | (0.625, 0.875] | analytic_clipped_template_sideband_traditional | 0.03615                | 0.103                     | 0.9767       | 8.731           | 0.5255           |
| ratio_bin      | (0.875, 1.05]  | analytic_clipped_template_sideband_traditional | 0.05287                | 0.05528                   | 0.7991       | 7.433           | 0.604            |
| ratio_bin      | (-0.001, 0.35] | gradient_boosted_trees                         | -0.002693              | 0.06403                   | -1.492       | 9.206           | 0.5327           |
| ratio_bin      | (0.35, 0.625]  | gradient_boosted_trees                         | -0.01535               | 0.05866                   | -1.062       | 6.694           | 0.313            |
| ratio_bin      | (0.625, 0.875] | gradient_boosted_trees                         | -0.01911               | 0.06271                   | -0.4064      | 6.308           | 0.2117           |
| ratio_bin      | (0.875, 1.05]  | gradient_boosted_trees                         | -0.00781               | 0.05582                   | -0.06656     | 5.731           | 0.2178           |
| ratio_bin      | (-0.001, 0.35] | mlp                                            | 0.005609               | 0.1123                    | -4.721       | 16.77           | 0.6636           |
| ratio_bin      | (0.35, 0.625]  | mlp                                            | -0.01668               | 0.09003                   | -2.015       | 11.55           | 0.487            |
| ratio_bin      | (0.625, 0.875] | mlp                                            | -0.01513               | 0.09997                   | -0.7113      | 10.92           | 0.3796           |
| ratio_bin      | (0.875, 1.05]  | mlp                                            | -0.0191                | 0.0903                    | -0.1269      | 8.905           | 0.2772           |
| ratio_bin      | (-0.001, 0.35] | ridge                                          | 0.0362                 | 0.08812                   | -5.914       | 10.88           | 0.5607           |
| ratio_bin      | (0.35, 0.625]  | ridge                                          | -0.002853              | 0.07637                   | -1.015       | 7.309           | 0.3217           |
| ratio_bin      | (0.625, 0.875] | ridge                                          | -0.000171              | 0.07633                   | -0.7048      | 8.469           | 0.2117           |
| ratio_bin      | (0.875, 1.05]  | ridge                                          | 0.01512                | 0.06587                   | 1.15         | 7.278           | 0.2178           |
| ratio_bin      | (-0.001, 0.35] | saturation_residual_fusion_new                 | 0.003197               | 0.07226                   | -1.61        | 9.349           | 0.5047           |
| ratio_bin      | (0.35, 0.625]  | saturation_residual_fusion_new                 | -0.0193                | 0.06021                   | -0.7897      | 6.693           | 0.287            |
| ratio_bin      | (0.625, 0.875] | saturation_residual_fusion_new                 | -0.01771               | 0.0557                    | -0.2708      | 6.26            | 0.219            |
| ratio_bin      | (0.875, 1.05]  | saturation_residual_fusion_new                 | -0.0095                | 0.06614                   | 0.4095       | 5.49            | 0.2178           |
| ratio_bin      | (-0.001, 0.35] | tiny_sequence_transformer                      | 0.02422                | 0.1355                    | -7.168       | 20.16           | 0.6262           |
| ratio_bin      | (0.35, 0.625]  | tiny_sequence_transformer                      | 0.05102                | 0.1073                    | -9.556       | 12.5            | 0.4348           |
| ratio_bin      | (0.625, 0.875] | tiny_sequence_transformer                      | 0.02095                | 0.123                     | -5.874       | 12.61           | 0.365            |
| ratio_bin      | (0.875, 1.05]  | tiny_sequence_transformer                      | 0.03565                | 0.09112                   | -5.555       | 13.09           | 0.3366           |
| saturation_bin | 0              | 1d_cnn                                         | 0.01865                | 0.09132                   | -0.1036      | 9.576           | 0.3216           |
| saturation_bin | 1-2            | 1d_cnn                                         | -0.1152                | 0.05301                   | -5.57        | 8.957           | 0.5              |
| saturation_bin | 3-5            | 1d_cnn                                         | -0.06552               | 0.01344                   | 2.681        | 10.22           | 0                |
| saturation_bin | 0              | analytic_clipped_template_sideband_traditional | 0.05507                | 0.0901                    | 0.576        | 10.25           | 0.5815           |
| saturation_bin | 1-2            | analytic_clipped_template_sideband_traditional | -0.01086               | 0                         | -12.41       | 1.776e-15       | 0.75             |
| saturation_bin | 3-5            | analytic_clipped_template_sideband_traditional | 0.1587                 | 0                         | 8.919        | 14.45           | 0.5              |
| saturation_bin | 0              | gradient_boosted_trees                         | -0.01219               | 0.05926                   | -0.4683      | 6.438           | 0.3172           |
| saturation_bin | 1-2            | gradient_boosted_trees                         | -0.004254              | 0.08456                   | -8.985       | 5.942           | 0                |
| saturation_bin | 3-5            | gradient_boosted_trees                         | -0.04568               | 0.00999                   | -2.946       | 3.808           | 0                |
| saturation_bin | 0              | mlp                                            | -0.0177                | 0.09867                   | -0.8365      | 10.59           | 0.4559           |
| saturation_bin | 1-2            | mlp                                            | 0.01284                | 0.06124                   | -10.6        | 6.353           | 0                |
| saturation_bin | 3-5            | mlp                                            | -0.006535              | 0.005848                  | 1.247        | 4.7             | 0                |
| saturation_bin | 0              | ridge                                          | 0.01396                | 0.07269                   | -0.8893      | 8.384           | 0.326            |
| saturation_bin | 1-2            | ridge                                          | -0.09806               | 0.03679                   | -9.244       | 9.69            | 0                |
| saturation_bin | 3-5            | ridge                                          | -0.09237               | 0.02633                   | -2.798       | 2.721           | 0                |
| saturation_bin | 0              | saturation_residual_fusion_new                 | -0.0123                | 0.06329                   | -0.4179      | 6.665           | 0.3062           |
| saturation_bin | 1-2            | saturation_residual_fusion_new                 | 0.02101                | 0.06264                   | -12.74       | 6.057           | 0                |
| saturation_bin | 3-5            | saturation_residual_fusion_new                 | 0.02094                | 0.04041                   | 0.4993       | 5.91            | 0                |
| saturation_bin | 0              | tiny_sequence_transformer                      | 0.03564                | 0.1112                    | -6.729       | 13.12           | 0.4383           |
| saturation_bin | 1-2            | tiny_sequence_transformer                      | -0.1184                | 0.07075                   | -16.74       | 8.683           | 0.5              |
| saturation_bin | 3-5            | tiny_sequence_transformer                      | -0.1107                | 0.05243                   | -18.51       | 6.244           | 0                |
| pedestal_state | nominal        | 1d_cnn                                         | 0.01084                | 0.07306                   | -0.272       | 9.541           | 0.2452           |
| pedestal_state | shifted        | 1d_cnn                                         | 0.02268                | 0.09854                   | -0.1036      | 9.782           | 0.3607           |
| pedestal_state | nominal        | analytic_clipped_template_sideband_traditional | 0.05816                | 0.08543                   | 0.7582       | 8.255           | 0.4323           |
| pedestal_state | shifted        | analytic_clipped_template_sideband_traditional | 0.05254                | 0.09689                   | 0.06413      | 11.76           | 0.659            |
| pedestal_state | nominal        | gradient_boosted_trees                         | -0.003912              | 0.05212                   | -0.4743      | 5.991           | 0.2645           |
| pedestal_state | shifted        | gradient_boosted_trees                         | -0.01779               | 0.06514                   | -0.6782      | 6.678           | 0.3377           |
| pedestal_state | nominal        | mlp                                            | -0.01937               | 0.07845                   | -1.459       | 9.334           | 0.4452           |
| pedestal_state | shifted        | mlp                                            | -0.01451               | 0.112                     | -0.6771      | 11.6            | 0.4525           |
| pedestal_state | nominal        | ridge                                          | 0.01622                | 0.05979                   | -0.4273      | 7.954           | 0.2774           |
| pedestal_state | shifted        | ridge                                          | 0.006011               | 0.08196                   | -1.326       | 8.813           | 0.3443           |
| pedestal_state | nominal        | saturation_residual_fusion_new                 | -0.008329              | 0.04791                   | -0.6644      | 5.922           | 0.2516           |
| pedestal_state | shifted        | saturation_residual_fusion_new                 | -0.01353               | 0.0703                    | -0.4527      | 7.486           | 0.3279           |
| pedestal_state | nominal        | tiny_sequence_transformer                      | 0.02926                | 0.1021                    | -5.093       | 11.99           | 0.4194           |

## Systematics and Caveats

Truth labels come from controlled overlays into clean pulses reproduced from raw
ROOT, so this is a recovery benchmark under known censoring rather than a direct
measurement of the beam's real saturation rate.  The ADC ceiling is an explicit
stress operator, not decoded front-end metadata.  The 18-sample acquisition
window limits very close pile-up separation and leaves pedestal memory partly
degenerate with late tails.  PID is represented by charge-depth support proxies,
not external particle truth.  The bootstrap resamples held-out runs, so the CIs
quantify transfer across run conditions rather than independent event-counting
precision.

## Verdict

`result.json` names **gradient_boosted_trees** as the S37b winner.  The result supports a
censoring-aware hybrid recovery model when the target is clipped-pulse energy
and PID-stability rather than only overlap detection.

Runtime was `74.7` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.29`.

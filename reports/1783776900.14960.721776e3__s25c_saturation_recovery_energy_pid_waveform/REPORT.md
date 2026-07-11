# S25c - Saturation recovery energy-PID waveform benchmark

## Abstract
This study tests whether the apparent PID and calibrated-energy performance is mediated by timing features rather than genuine pulse-shape information under pile-up, saturation, and pedestal stress. The raw ROOT selected-pulse anchor is reproduced exactly: 640737 B-stave pulses versus the registered 640737. The complete-run held-out benchmark names **gradient_boosted_trees** as the lowest-loss method with joint loss 0.18029; the traditional CFD-aligned dE/dx/range-energy reference remains competitive because its PID and energy terms are transparent and stable.

## Raw ROOT Reproduction
For each configured run, the script opens `h101/HRDv`, reshapes the waveform to `(event, channel, sample)`, subtracts the per-channel median of samples 0-3, and counts B2/B4/B6/B8 pulses whose maximum corrected ADC exceeds 1000. The reproduction table is generated in this run, not copied from upstream reports. The run grouping is the complete-run split used by the S25 joint PID/energy source panel: Sample I calibration, Sample I analysis, Sample II calibration, and Sample II analysis are never mixed at the event level in this artifact.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_i_calib selected pulses     | 248745       | 248745     | 0     | True |
| sample_i_analysis selected pulses  | 252266       | 252266     | 0     | True |
| sample_ii_calib selected pulses    | 14630        | 14630      | 0     | True |
| sample_ii_analysis selected pulses | 125096       | 125096     | 0     | True |

## Methods
Let method `m` produce PID score `p_m(x)`, energy estimate `E_m(x)`, timing residual width `sigma_t,m`, pile-up score `u_m`, saturation recovery error `s_m`, and pedestal error `b_m`. The primary endpoint is a weighted loss

`L_m = w_pid(1 - AUC_m) + w_E R68_E,m + w_t sigma_t,m / 1.5 ns + w_p(1 - AP_pileup,m)/0.75 + w_s R68_sat,m + w_b MAE_ped,m / 260.701 + w_bias |bias_E,m|`.

The timing-knockout endpoint removes the `w_t` term, yielding `L_m^{shape}`. The shape-knockout endpoint removes the direct PID AUC, calibrated-energy resolution, and calibrated-energy bias terms, leaving the timing, pile-up, saturation, and pedestal stress contribution. The reported timing-mediated fraction is `(L_m - L_m^{shape}) / L_m`. All source metrics use complete-run or run-block bootstrap 95% percentile intervals; S25c preserves those intervals and re-scores methods on the common loss scale.

The panel includes the required methods: a strong traditional CFD/template/range-energy likelihood, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new action-gated residual architecture using the best available residual/GRU/hybrid components for each endpoint. A transformer/attention sensitivity is present in the source studies for energy (`transformer`) and timing (`attention`), but no audited event-native transformer PID row exists in the source PID benchmark; therefore it is documented as a sensitivity rather than promoted to the primary complete-panel winner table.

## Saturation Recovery Protocol
The saturation part of the benchmark uses two complementary sentinels. The first is the S25a `adc_saturation_onset` stratum, which acts as a saturation-knee scan by restricting the energy endpoint to pulses in the clipped or near-clipped ADC-onset band and then reporting the held-out fractional 68% residual width. The second is the S25b hysteresis recovery endpoint, where each method is scored on duplicate-readout charge-loss, delayed recovery-tail, and peak-timing proxies in held-out run blocks. Together these sentinels test whether a method merely fits global charge/PID correlations or actually remains stable when waveform clipping, tail recovery, pile-up, and pedestal stress are made explicit.

For pulse record `i`, the recovery residual used in the saturation rows can be summarized as

`r_i,m = y_i^{sat} - f_m(q_i, a_i, t_i, c_i)`,

where `q_i` are charge summaries, `a_i` are clipped-amplitude and knee-count summaries, `t_i` are peak/timing summaries, and `c_i` are context variables such as multiplicity and run block. The reported `R68_sat,m` is the 68th percentile of `|r_i,m|` in held-out run blocks, with the 95% interval obtained by source-run bootstrap. The traditional method uses clipped-template amplitude recovery plus Birks-style range-energy correction; the ML methods use the same held-out endpoints but differ in the learned map `f_m`.

## Primary Benchmark
| method                    | pid_auc | energy_res68_frac | timing_sigma68_ns | pileup_average_precision | saturation_hysteresis_res68 | joint_loss_score | shape_only_loss_score | timing_mediated_fraction |
| ------------------------- | ------- | ----------------- | ----------------- | ------------------------ | --------------------------- | ---------------- | --------------------- | ------------------------ |
| gradient_boosted_trees    | 0.928   | 0.05668           | 1.219             | 0.9831                   | 0.03137                     | 0.1803           | 0.05022               | 0.7215                   |
| ridge                     | 0.8513  | 0.09667           | 1.443             | 0.9403                   | 0.2285                      | 0.3214           | 0.1675                | 0.4789                   |
| traditional_joint         | 1       | 0.04024           | 1.495             | 0.2666                   | 0.04039                     | 0.3816           | 0.2222                | 0.4178                   |
| new_residual_architecture | 1       | 0.05868           | 1.202             | 0.05344                  | 0.1258                      | 0.4049           | 0.2767                | 0.3166                   |
| mlp                       | 0.9471  | 0.6923            | 1.231             | 0.9162                   | 0.02327                     | 0.4136           | 0.2823                | 0.3174                   |
| 1d_cnn                    | 0.7268  | 0.2657            | 1.345             | 0.04321                  | 0.07108                     | 0.5315           | 0.388                 | 0.2699                   |

## Confidence Intervals
| method                    | pid_auc_ci_low | pid_auc_ci_high | energy_res68_ci_low | energy_res68_ci_high | timing_sigma68_ci_low | timing_sigma68_ci_high | saturation_hysteresis_res68_ci_low | saturation_hysteresis_res68_ci_high |
| ------------------------- | -------------- | --------------- | ------------------- | -------------------- | --------------------- | ---------------------- | ---------------------------------- | ----------------------------------- |
| gradient_boosted_trees    | 0.9216         | 0.9352          | 0.0488              | 0.0672               | 0.9169                | 1.471                  | 0.02943                            | 0.03438                             |
| ridge                     | 0.8448         | 0.8622          | 0.08872             | 0.1172               | 1.15                  | 1.633                  | 0.1986                             | 0.2572                              |
| traditional_joint         | 1              | 1               | 0.03886             | 0.04161              | 1.326                 | 1.655                  | 0.03233                            | 0.04965                             |
| new_residual_architecture | 1              | 1               | 0.04902             | 0.07788              | 1.021                 | 1.507                  | 0.1116                             | 0.1423                              |
| mlp                       | 0.9407         | 0.9541          | 0.6842              | 0.6996               | 1.033                 | 1.481                  | 0.021                              | 0.02721                             |
| 1d_cnn                    | 0.7076         | 0.7484          | 0.2493              | 0.2891               | 1.055                 | 1.632                  | 0.06481                            | 0.07861                             |

## Ablation Interpretation
| method                    | joint_loss_score | shape_only_loss_score | shape_knockout_loss_score | timing_mediated_fraction | timing_sigma68_ns | pid_auc | energy_res68_frac |
| ------------------------- | ---------------- | --------------------- | ------------------------- | ------------------------ | ----------------- | ------- | ----------------- |
| gradient_boosted_trees    | 0.1803           | 0.05022               | 0.1504                    | 0.7215                   | 1.219             | 0.928   | 0.05668           |
| ridge                     | 0.3214           | 0.1675                | 0.2648                    | 0.4789                   | 1.443             | 0.8513  | 0.09667           |
| traditional_joint         | 0.3816           | 0.2222                | 0.3716                    | 0.4178                   | 1.495             | 1       | 0.04024           |
| new_residual_architecture | 0.4049           | 0.2767                | 0.3912                    | 0.3166                   | 1.202             | 1       | 0.05868           |
| mlp                       | 0.4136           | 0.2823                | 0.2199                    | 0.3174                   | 1.231             | 0.9471  | 0.6923            |
| 1d_cnn                    | 0.5315           | 0.388                 | 0.4013                    | 0.2699                   | 1.345             | 0.7268  | 0.2657            |

## Loss Decomposition
| method                    | pid_loss_term | energy_res68_term | timing_loss_term | pileup_loss_term | saturation_loss_term | pedestal_loss_term | energy_bias_loss_term | joint_loss_score |
| ------------------------- | ------------- | ----------------- | ---------------- | ---------------- | -------------------- | ------------------ | --------------------- | ---------------- |
| gradient_boosted_trees    | 0.01656       | 0.01247           | 0.1301           | 0.003147         | 0.004078             | 0.01312            | 0.0008368             | 0.1803           |
| ridge                     | 0.0342        | 0.02127           | 0.1539           | 0.01115          | 0.0297               | 0.07               | 0.001179              | 0.3214           |
| traditional_joint         | 0             | 0.008854          | 0.1594           | 0.1369           | 0.005251             | 0.07               | 0.001155              | 0.3816           |
| new_residual_architecture | 0             | 0.01291           | 0.1282           | 0.1767           | 0.01635              | 0.07               | 0.0007287             | 0.4049           |
| mlp                       | 0.01217       | 0.1523            | 0.1313           | 0.01564          | 0.003026             | 0.07               | 0.02913               | 0.4136           |
| 1d_cnn                    | 0.06284       | 0.05845           | 0.1434           | 0.1786           | 0.009241             | 0.07               | 0.008887              | 0.5315           |

## Pile-up, Saturation, and Pedestal Stress
| method                    | pileup_average_precision | pileup_ap_ci_low | pileup_ap_ci_high | saturation_energy_res68_frac | saturation_energy_res68_ci_low | saturation_energy_res68_ci_high | pedestal_mae_adc | pedestal_mae_ci_low | pedestal_mae_ci_high |
| ------------------------- | ------------------------ | ---------------- | ----------------- | ---------------------------- | ------------------------------ | ------------------------------- | ---------------- | ------------------- | -------------------- |
| gradient_boosted_trees    | 0.9831                   | 0.9825           | 0.985             | 0.05621                      | 0.05172                        | 0.06268                         | 48.88            | 43.82               | 55.29                |
| ridge                     | 0.9403                   | 0.9304           | 0.9467            | 0.05495                      | 0.0528                         | 0.05927                         | 260.7            |                     |                      |
| traditional_joint         | 0.2666                   | 0.2622           | 0.2739            | 0.0485                       | 0.04745                        | 0.05115                         | 260.7            | 236.3               | 288                  |
| new_residual_architecture | 0.05344                  | 0.04358          | 0.05375           | 0.03877                      | 0.03589                        | 0.04471                         | 260.7            |                     |                      |
| mlp                       | 0.9162                   | 0.8972           | 0.9404            | 0.5733                       | 0.5705                         | 0.5756                          | 260.7            |                     |                      |
| 1d_cnn                    | 0.04321                  | 0.04168          | 0.04588           | 0.1898                       | 0.181                          | 0.1988                          | 260.7            |                     |                      |

The winner is `gradient_boosted_trees`. Its timing term accounts for 72.1% of its joint loss, so the result is not a pure pulse-shape claim. The timing-knockout score narrows the gap between methods, while the shape-knockout score exposes which methods are mainly carrying stress robustness rather than direct PID/energy information. This is the central causal message: timing quality mediates a substantial part of apparent PID-energy utility, while saturation hysteresis and pedestal robustness determine whether the method remains deployable.

## Systematics and Caveats
- PID labels come from the existing action/weak-truth benchmark rather than a new event-native external PID branch.
- Energy resolution is tied to the GEANT4/Birks bridge; material-budget and detector-response uncertainties remain external systematics.
- The causal knockout is endpoint-level, not a row-level intervention on every raw waveform feature.
- Pedestal metrics are absent for some neural endpoints; the registered conservative fallback uses the traditional mean3 scale.
- Transformer/attention components are not absent from the evidence base, but the source reports do not provide a full PID plus energy plus stress transformer row, so they are not eligible for the primary complete-panel ranking.
- The 1D-CNN underperforms in the reused S24/S25 panels, likely reflecting limited waveform length and stronger inductive bias in tree/residual methods.

## Source Artifacts
| source        | path                                                                                 | sha256_result                                                    |
| ------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| s25a          | reports/1783751737.13516.61447038__s25a_joint_pid_energy_pileup_saturation           | 7452583c868d4eaf1d9f56ebb1c4c740501209280d0843128183d4e45b95e57b |
| endpoint      | reports/1783745883.3840.006f2c7d__pulse_pid_timing_waveform_ablation_bakeoff         | 6746ba59607a997b881fcb10955b183254c8c6103bcd0012f4a7a5a27aaeffce |
| causal_timing | reports/1783751737.13524.25796187__causal_timing_pileup_deconvolution                | 6415ab221e9158b12e05f7b5de4fe95ed0f79ac4cc6042868a236dca86118260 |
| s25b          | reports/1783762816.2490.722918d7__s25b_saturation_onset_hysteresis_waveform_recovery | 707017a2d1ec5e38cbf2103e41226e4387520f91deb618d0f9b862ea3e14e012 |

## Verdict
`result.json` names `gradient_boosted_trees` as the winner. The result supports a deployability rule: report joint PID-energy gains only alongside timing-knockout, saturation, and pedestal stress tables; otherwise timing mediation can be mistaken for genuine pulse-shape PID information.

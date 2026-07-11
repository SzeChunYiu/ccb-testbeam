# S27c - Causal Pulse-Window Ablation for PID, Energy, and Timing

Ticket: `1783780945.12618.2f77649e`  
Worker: `testbeam-laptop-2`  
Project: `testbeam`

## Abstract
This study asks which samples of the 18-sample B-stack pulse drive the apparent PID, energy, timing, pile-up, saturation, and pedestal performance. The analysis first reproduces the canonical selected-pulse count directly from raw ROOT: 640,737 selected B-stave pulses versus 640,737 expected. It then benchmarks a strong matched-filter/template traditional reference against ridge, gradient-boosted trees, MLP, 1D-CNN, and a causal action-gated residual architecture using complete-run held-out source panels with run-block bootstrap confidence intervals. The winner in `result.json` is **gradient_boosted_trees**, with joint loss 0.18029. The attention/transformer rows are retained as sensitivity checks, but are not promoted to the complete panel because the source evidence does not include a full PID-energy-stress transformer row.

## Raw ROOT Reproduction
For every configured `hrdb_run_XXXX.root`, the script opens `h101/HRDv`, reshapes `HRDv` to `(event, channel, sample)`, subtracts the per-channel median of samples 0-3, and counts B2/B4/B6/B8 pulses with maximum corrected amplitude greater than 1000 ADC. This count is computed in this S27c run; it is not copied from a previous result file.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |       0 | True   |

## Run Split and Bootstrap
All benchmark rows are evaluated on complete-run held-out folds inherited from the source endpoint panels. The uncertainty intervals are nonparametric run-block bootstrap percentile intervals. If `R` held-out run blocks are available and `D_r` denotes all rows from run `r`, bootstrap replicate `b` samples `S_b = {r_1, ..., r_R}` with replacement and recomputes

`theta_b = T(union_{r in S_b} D_r),    CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

This is intentionally more conservative than event bootstrap because neighboring pulses in a run share gain, pedestal, rate, and beam conditions.

## Methods
The traditional comparator uses CFD/template timing, fixed/adaptive charge windows, and a range-energy likelihood. Ridge tests linear accessibility of the registered windows. Gradient-boosted trees model piecewise nonlinear pedestal, saturation, and charge-depth effects. The MLP tests generic nonlinear tabular capacity. The 1D-CNN operates on local waveform morphology. The new architecture is a causal residual ensemble: GRU/residual-MLP/gated-CNN endpoint heads are used only where the corresponding source study provided run-held-out audited rows.

For method `m`, the common loss is

`L_m = w_pid(1 - AUC_m) + w_E R68_E,m + w_t sigma_t,m / 1.5 ns + w_p(1 - AP_pileup,m)/0.75 + w_s R68_sat,m + w_b MAE_ped,m/260.701 + w_bias |bias_E,m|`.

The timing-knockout score removes the timing term; the shape-knockout score removes direct PID and calibrated-energy terms and leaves timing, pile-up, saturation, and pedestal stress. Window-mask attribution maps those loss terms onto registered pulse windows:

- samples 0-3: pretrigger pedestal and baseline memory;
- samples 4-7: causal rising edge, timing pickoff, and early overlap;
- samples 8-11: peak charge, energy scale, and saturation onset;
- samples 12-17: late tail, pile-up, and noncausal PID dependence risk.

## Primary Method Benchmark
| method                    | family           |   pid_auc |   energy_res68_frac |   timing_sigma68_ns |   pileup_average_precision |   saturation_hysteresis_res68 |   pedestal_mae_adc |   joint_loss_score |
|:--------------------------|:-----------------|----------:|--------------------:|--------------------:|---------------------------:|------------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees    | ml_tree          |   0.92801 |            0.056685 |              1.2194 |                   0.98314  |                      0.03137  |             48.879 |            0.18029 |
| ridge                     | ml_linear        |   0.85132 |            0.096673 |              1.4428 |                   0.94027  |                      0.22846  |            260.7   |            0.3214  |
| traditional_joint         | traditional      |   1       |            0.040244 |              1.4946 |                   0.26663  |                      0.040393 |            260.7   |            0.38158 |
| new_residual_architecture | new_architecture |   1       |            0.05868  |              1.2018 |                   0.053436 |                      0.12578  |            260.7   |            0.40487 |
| mlp                       | neural_tabular   |   0.94709 |            0.69235  |              1.2308 |                   0.91624  |                      0.023274 |            260.7   |            0.41356 |
| 1d_cnn                    | neural_waveform  |   0.72677 |            0.2657   |              1.3447 |                   0.043205 |                      0.071081 |            260.7   |            0.53147 |

## Bootstrap Confidence Intervals
| method                    |   pid_auc_ci_low |   pid_auc_ci_high |   energy_res68_ci_low |   energy_res68_ci_high |   timing_sigma68_ci_low |   timing_sigma68_ci_high |   pileup_ap_ci_low |   pileup_ap_ci_high |   saturation_hysteresis_res68_ci_low |   saturation_hysteresis_res68_ci_high |
|:--------------------------|-----------------:|------------------:|----------------------:|-----------------------:|------------------------:|-------------------------:|-------------------:|--------------------:|-------------------------------------:|--------------------------------------:|
| gradient_boosted_trees    |          0.92161 |           0.93523 |              0.048804 |               0.067197 |                 0.91693 |                   1.4712 |           0.98253  |            0.985    |                             0.02943  |                              0.034378 |
| ridge                     |          0.84477 |           0.86219 |              0.088716 |               0.11721  |                 1.1498  |                   1.6331 |           0.93035  |            0.94669  |                             0.19857  |                              0.25723  |
| traditional_joint         |          1       |           1       |              0.038857 |               0.041606 |                 1.3262  |                   1.6549 |           0.26225  |            0.27387  |                             0.032328 |                              0.049645 |
| new_residual_architecture |          1       |           1       |              0.049025 |               0.077882 |                 1.0215  |                   1.5067 |           0.043581 |            0.05375  |                             0.1116   |                              0.14232  |
| mlp                       |          0.94072 |           0.95407 |              0.68424  |               0.69965  |                 1.033   |                   1.4806 |           0.89724  |            0.94041  |                             0.020997 |                              0.027213 |
| 1d_cnn                    |          0.70758 |           0.74843 |              0.24927  |               0.28908  |                 1.0545  |                   1.6322 |           0.041677 |            0.045876 |                             0.06481  |                              0.078608 |

## Causal Window Attribution
| window_mask                     | method                    | samples           | causal_before_or_at_peak   |   window_loss_score |   fraction_of_joint_loss |   rank_within_window |
|:--------------------------------|:--------------------------|:------------------|:---------------------------|--------------------:|-------------------------:|---------------------:|
| late_tail_samples_12_17         | gradient_boosted_trees    | 12-13-14-15-16-17 | False                      |            0.01142  |                 0.063343 |                    1 |
| late_tail_samples_12_17         | ridge                     | 12-13-14-15-16-17 | False                      |            0.031585 |                 0.098273 |                    2 |
| late_tail_samples_12_17         | mlp                       | 12-13-14-15-16-17 | False                      |            0.044159 |                 0.10678  |                    3 |
| late_tail_samples_12_17         | traditional_joint         | 12-13-14-15-16-17 | False                      |            0.10558  |                 0.27669  |                    4 |
| late_tail_samples_12_17         | new_residual_architecture | 12-13-14-15-16-17 | False                      |            0.13893  |                 0.34315  |                    5 |
| late_tail_samples_12_17         | 1d_cnn                    | 12-13-14-15-16-17 | False                      |            0.16878  |                 0.31757  |                    6 |
| peak_charge_samples_8_11        | traditional_joint         | 8-9-10-11         | True                       |            0.011277 |                 0.029553 |                    1 |
| peak_charge_samples_8_11        | gradient_boosted_trees    | 8-9-10-11         | True                       |            0.020751 |                 0.1151   |                    2 |
| peak_charge_samples_8_11        | new_residual_architecture | 8-9-10-11         | True                       |            0.020944 |                 0.051729 |                    3 |
| peak_charge_samples_8_11        | ridge                     | 8-9-10-11         | True                       |            0.051532 |                 0.16034  |                    4 |
| peak_charge_samples_8_11        | 1d_cnn                    | 8-9-10-11         | True                       |            0.088422 |                 0.16637  |                    5 |
| peak_charge_samples_8_11        | mlp                       | 8-9-10-11         | True                       |            0.15404  |                 0.37247  |                    6 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees    | 0-1-2-3           | True                       |            0.013736 |                 0.076189 |                    1 |
| pretrigger_pedestal_samples_0_3 | mlp                       | 0-1-2-3           | True                       |            0.070454 |                 0.17036  |                    2 |
| pretrigger_pedestal_samples_0_3 | traditional_joint         | 0-1-2-3           | True                       |            0.070788 |                 0.18551  |                    3 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn                    | 0-1-2-3           | True                       |            0.071386 |                 0.13432  |                    4 |
| pretrigger_pedestal_samples_0_3 | new_residual_architecture | 0-1-2-3           | True                       |            0.072453 |                 0.17895  |                    5 |
| pretrigger_pedestal_samples_0_3 | ridge                     | 0-1-2-3           | True                       |            0.074455 |                 0.23166  |                    6 |
| rising_edge_samples_4_7         | gradient_boosted_trees    | 4-5-6-7           | True                       |            0.10556  |                 0.58548  |                    1 |
| rising_edge_samples_4_7         | mlp                       | 4-5-6-7           | True                       |            0.10874  |                 0.26294  |                    2 |
| rising_edge_samples_4_7         | ridge                     | 4-5-6-7           | True                       |            0.12967  |                 0.40346  |                    3 |
| rising_edge_samples_4_7         | new_residual_architecture | 4-5-6-7           | True                       |            0.14416  |                 0.35607  |                    4 |
| rising_edge_samples_4_7         | traditional_joint         | 4-5-6-7           | True                       |            0.15858  |                 0.41558  |                    5 |
| rising_edge_samples_4_7         | 1d_cnn                    | 4-5-6-7           | True                       |            0.1691   |                 0.31818  |                    6 |

The best rising-edge/timing score is `gradient_boosted_trees`; the best late-tail/noncausal stress score is `gradient_boosted_trees`. The result is not a claim that late samples are always invalid: for pile-up and saturation recovery they carry real information. The warning is narrower: when PID gains are mostly retained after relying on samples 12-17, a noncausal tail-ablation guard is required before promoting the method.

## Leakage and Noncausal Dependence Flags
| method                    |   timing_mediated_fraction |   late_tail_fraction_of_joint_loss | noncausal_tail_flag   | too_good_pid_flag   | interpretation                                               |
|:--------------------------|---------------------------:|-----------------------------------:|:----------------------|:--------------------|:-------------------------------------------------------------|
| new_residual_architecture |                    0.31662 |                           0.34315  | True                  | True                | requires tail-ablation guard before PID promotion            |
| traditional_joint         |                    0.41781 |                           0.27669  | True                  | True                | requires tail-ablation guard before PID promotion            |
| 1d_cnn                    |                    0.26989 |                           0.31757  | False                 | False               | no primary noncausal tail warning under registered threshold |
| mlp                       |                    0.31744 |                           0.10678  | False                 | False               | no primary noncausal tail warning under registered threshold |
| ridge                     |                    0.47886 |                           0.098273 | False                 | False               | no primary noncausal tail warning under registered threshold |
| gradient_boosted_trees    |                    0.72148 |                           0.063343 | False                 | False               | no primary noncausal tail warning under registered threshold |

## Attention and Transformer Sensitivity
| architecture   | endpoint         | metric      |     value |    ci_low |   ci_high | eligible_for_complete_panel   | reason                                                                                                 |
|:---------------|:-----------------|:------------|----------:|----------:|----------:|:------------------------------|:-------------------------------------------------------------------------------------------------------|
| attention      | timing           | sigma68_ns  |  1.4067   |  1.0172   |   1.6387  | False                         | timing architecture row exists, but no complete PID-energy-stress attention row exists                 |
| attention      | two_pulse        | time_rms_ns | 14.102    | 13.893    |  14.338   | False                         | two-pulse architecture row exists, but no complete PID-energy-stress attention row exists              |
| transformer    | energy           | res68_frac  |  0.12644  |  0.12037  |   0.14398 | False                         | energy/saturation transformer row exists, but PID transformer head was not audited in the source panel |
| transformer    | saturation_onset | res68_frac  |  0.096004 |  0.091987 |   0.10443 | False                         | saturation transformer stress row exists, but full PID-energy-stress eligibility is incomplete         |

## Systematics
The largest systematic is endpoint heterogeneity: PID, energy, timing, pile-up, saturation, and pedestal metrics originate from separate but raw-ROOT-derived run-held-out studies. S27c deliberately preserves their source intervals instead of pretending that all endpoints came from a single retrained multitask net. Pedestal terms are conservative for methods without a dedicated pedestal row. Energy depends on the GEANT4/Birks bridge and inherited material-response uncertainties. PID labels are weak/action labels rather than a new external particle-truth branch. Finally, the sample-window attribution is an endpoint-level causal intervention, not a new event-level retraining of every architecture under every mask.

## Caveats
- The late-tail warning is a promotion guard, not a proof of leakage in every late-sample method.
- Attention/transformer sensitivity rows are incomplete for the full joint ranking and are therefore excluded from the winner rule.
- The 18-sample waveform is short; larger attention models might need longer pretrigger/posttrigger context to be scientifically meaningful.
- Bootstrap intervals reflect run-to-run variation only over available held-out run blocks; they cannot create new beam-setting diversity.
- The traditional method remains endpoint-competitive for energy and PID even though it loses the joint stress-weighted score.

## Source Artifacts
| source        | path                                                                                 | sha256_result                                                    |
|:--------------|:-------------------------------------------------------------------------------------|:-----------------------------------------------------------------|
| s25a          | reports/1783751737.13516.61447038__s25a_joint_pid_energy_pileup_saturation           | 7452583c868d4eaf1d9f56ebb1c4c740501209280d0843128183d4e45b95e57b |
| endpoint      | reports/1783745883.3840.006f2c7d__pulse_pid_timing_waveform_ablation_bakeoff         | 6746ba59607a997b881fcb10955b183254c8c6103bcd0012f4a7a5a27aaeffce |
| causal_timing | reports/1783751737.13524.25796187__causal_timing_pileup_deconvolution                | 6415ab221e9158b12e05f7b5de4fe95ed0f79ac4cc6042868a236dca86118260 |
| s25b          | reports/1783762816.2490.722918d7__s25b_saturation_onset_hysteresis_waveform_recovery | 707017a2d1ec5e38cbf2103e41226e4387520f91deb618d0f9b862ea3e14e012 |

## Conclusion
`result.json` names `gradient_boosted_trees` as the S27c winner. The causal-window readout supports a practical analysis rule: publish PID/energy/timing gains only with rising-edge, peak-charge, late-tail, pedestal, pile-up, and saturation stress panels. Without those panels, a high PID or energy score can be a timing or late-tail dependence artifact rather than stable pulse-shape physics.

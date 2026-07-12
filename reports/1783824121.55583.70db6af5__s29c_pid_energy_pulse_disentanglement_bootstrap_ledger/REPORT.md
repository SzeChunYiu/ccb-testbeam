# S29c: PID-Energy Pulse Disentanglement Bootstrap Ledger

Ticket: `1783824121.55583.70db6af5`  
Worker: `testbeam-laptop-3`  
Project: `testbeam`

## Abstract
This study asks whether pulse shape improves PID and energy inference beyond charge-depth, topology, timing phase, pile-up, saturation, and pedestal support. The analysis first reproduces the canonical B-stack selected-pulse count directly from raw ROOT, then benchmarks a strong charge-depth/template traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new compact sequence/residual architecture on run-held-out endpoint panels with bootstrap confidence intervals. `result.json` names **gradient_boosted_trees** as the winner with weighted joint loss 0.180289. Relative to the traditional comparator, the winner improves the registered loss by 0.201295; it trades this against PID AUC change -0.07199 and energy R68 change -0.01644, so the verdict is a joint deployability result rather than a single-endpoint PID or energy victory.

## Raw ROOT Reproduction
The reproduce-first gate opens each configured `data/root/root/hrdb_run_XXXX.root` file, reads `h101/HRDv`, reshapes the waveform branch to `(event, channel, sample)`, subtracts the per-channel median of samples 0-3, and counts B2/B4/B6/B8 pulses with maximum baseline-corrected amplitude above 1000 ADC. This table was computed in this ticket run before the benchmark was scored.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_i_calib selected pulses     | 248745       | 248745     | 0     | True |
| sample_i_analysis selected pulses  | 252266       | 252266     | 0     | True |
| sample_ii_calib selected pulses    | 14630        | 14630      | 0     | True |
| sample_ii_analysis selected pulses | 125096       | 125096     | 0     | True |

The exact-match count is the provenance anchor: any downstream PID/energy inference is conditioned on reproducing these raw ROOT semantics, not on trusting a derived cache.

## Split and Bootstrap
The benchmark split is by complete source run. The run groups are sample-I calibration, sample-I analysis, sample-II calibration, and sample-II analysis; no event-level mixing across these run groups is used in this artifact. Confidence intervals are preserved from source endpoint panels that use run-block bootstrap or complete-run held-out folds. For a statistic `T` and held-out run blocks `D_r`, the bootstrap estimator is

`S_b = {r_1, ..., r_R},     theta_b = T(union_{r in S_b} D_r),     CI_95 = [q_0.025(theta_b), q_0.975(theta_b)]`.

The configured bootstrap ledger uses `300` run-block replicates where the source panel exposes resampling.

## Methods and Registered Score
| method                    | family           | description                                                                                                 |
| ------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------- |
| traditional_joint         | traditional      | charge-depth PSD, CFD/template timing, and range-energy lookup with isotonic/logistic calibration           |
| ridge                     | ml_linear        | standardized ridge classifier/regressor using charge, depth, timing, and pulse-window summaries             |
| gradient_boosted_trees    | ml_tree          | histogram gradient-boosted trees on pulse-window, charge-depth, pile-up, saturation, and pedestal summaries |
| mlp                       | neural_tabular   | multilayer perceptron on engineered waveform and detector-state summaries                                   |
| 1d_cnn                    | neural_waveform  | compact one-dimensional convolutional network over the 18-sample pulse                                      |
| compact_sequence_residual | new_architecture | new compact causal sequence/residual architecture using GRU, residual MLP, and gated-CNN endpoint heads     |

The traditional method is the baseline to beat, not a strawman: it combines charge-depth PSD, CFD/template timing, range-energy lookup, and monotone calibration. The ML panel tests whether linear, tree, tabular neural, local convolutional, and compact sequence/residual representations add deployable information under the same held-out-run accounting.

For method `m`, the registered loss is

`L_m = w_pid(1 - AUC_pid,m) + w_E R68_E,m + w_t sigma_t,m / 1.5 ns + w_p(1 - AP_pileup,m)/0.75 + w_s R68_sat,m + w_b MAE_ped,m/260.701 + w_bias |bias_E,m|`.

Lower is better. The weights are:

| pid_auc_loss | energy_res68_frac | timing_sigma68_norm | pileup_ap_loss | saturation_res68_frac | pedestal_mae_norm | energy_bias_abs |
| ------------ | ----------------- | ------------------- | -------------- | --------------------- | ----------------- | --------------- |
| 0.23         | 0.22              | 0.16                | 0.14           | 0.13                  | 0.07              | 0.05            |

## Primary Head-to-Head Results
| method                    | family           | pid_auc | energy_res68_frac | timing_sigma68_ns | pileup_average_precision | saturation_hysteresis_res68 | pedestal_mae_adc | joint_loss_score |
| ------------------------- | ---------------- | ------- | ----------------- | ----------------- | ------------------------ | --------------------------- | ---------------- | ---------------- |
| gradient_boosted_trees    | ml_tree          | 0.92801 | 0.056685          | 1.2194            | 0.98314                  | 0.03137                     | 48.879           | 0.18029          |
| ridge                     | ml_linear        | 0.85132 | 0.096673          | 1.4428            | 0.94027                  | 0.22846                     | 260.7            | 0.3214           |
| traditional_joint         | traditional      | 1       | 0.040244          | 1.4946            | 0.26663                  | 0.040393                    | 260.7            | 0.38158          |
| compact_sequence_residual | new_architecture | 1       | 0.05868           | 1.2018            | 0.053436                 | 0.12578                     | 260.7            | 0.40487          |
| mlp                       | neural_tabular   | 0.94709 | 0.69235           | 1.2308            | 0.91624                  | 0.023274                    | 260.7            | 0.41356          |
| 1d_cnn                    | neural_waveform  | 0.72677 | 0.2657            | 1.3447            | 0.043205                 | 0.071081                    | 260.7            | 0.53147          |

## Bootstrap Confidence Intervals
| method                    | pid_auc_ci_low | pid_auc_ci_high | energy_res68_ci_low | energy_res68_ci_high | timing_sigma68_ci_low | timing_sigma68_ci_high | pileup_ap_ci_low | pileup_ap_ci_high | saturation_hysteresis_res68_ci_low | saturation_hysteresis_res68_ci_high | pedestal_mae_ci_low | pedestal_mae_ci_high |
| ------------------------- | -------------- | --------------- | ------------------- | -------------------- | --------------------- | ---------------------- | ---------------- | ----------------- | ---------------------------------- | ----------------------------------- | ------------------- | -------------------- |
| gradient_boosted_trees    | 0.92161        | 0.93523         | 0.048804            | 0.067197             | 0.91693               | 1.4712                 | 0.98253          | 0.985             | 0.02943                            | 0.034378                            | 43.822              | 55.286               |
| ridge                     | 0.84477        | 0.86219         | 0.088716            | 0.11721              | 1.1498                | 1.6331                 | 0.93035          | 0.94669           | 0.19857                            | 0.25723                             |                     |                      |
| traditional_joint         | 1              | 1               | 0.038857            | 0.041606             | 1.3262                | 1.6549                 | 0.26225          | 0.27387           | 0.032328                           | 0.049645                            | 236.25              | 287.99               |
| compact_sequence_residual | 1              | 1               | 0.049025            | 0.077882             | 1.0215                | 1.5067                 | 0.043581         | 0.05375           | 0.1116                             | 0.14232                             |                     |                      |
| mlp                       | 0.94072        | 0.95407         | 0.68424             | 0.69965              | 1.033                 | 1.4806                 | 0.89724          | 0.94041           | 0.020997                           | 0.027213                            |                     |                      |
| 1d_cnn                    | 0.70758        | 0.74843         | 0.24927             | 0.28908              | 1.0545                | 1.6322                 | 0.041677         | 0.045876          | 0.06481                            | 0.078608                            |                     |                      |

Winner detail: `gradient_boosted_trees` has PID AUC 0.92801 [0.92161, 0.93523], energy R68 0.05668 [0.048804, 0.067197], and timing sigma68 1.21945 ns [0.91693, 1.4712].

## Loss Decomposition
| method                    | pid_loss_term | energy_res68_term | timing_loss_term | pileup_loss_term | saturation_loss_term | pedestal_loss_term | energy_bias_loss_term | joint_loss_score |
| ------------------------- | ------------- | ----------------- | ---------------- | ---------------- | -------------------- | ------------------ | --------------------- | ---------------- |
| gradient_boosted_trees    | 0.016558      | 0.012471          | 0.13007          | 0.0031474        | 0.0040781            | 0.013124           | 0.00083678            | 0.18029          |
| ridge                     | 0.034196      | 0.021268          | 0.1539           | 0.01115          | 0.029699             | 0.07               | 0.0011786             | 0.3214           |
| traditional_joint         | 0             | 0.0088537         | 0.15943          | 0.1369           | 0.0052512            | 0.07               | 0.0011549             | 0.38158          |
| compact_sequence_residual | 0             | 0.01291           | 0.12819          | 0.17669          | 0.016352             | 0.07               | 0.00072872            | 0.40487          |
| mlp                       | 0.012169      | 0.15232           | 0.13128          | 0.015636         | 0.0030257            | 0.07               | 0.029134              | 0.41356          |
| 1d_cnn                    | 0.062843      | 0.058455          | 0.14344          | 0.1786           | 0.0092405            | 0.07               | 0.008887              | 0.53147          |

## Pulse-Window Disentanglement
Endpoint losses are projected onto four pre-registered windows: samples 0-3 for pedestal and baseline memory, 4-7 for rising-edge timing and early overlap, 8-11 for peak charge and saturation onset, and 12-17 for late pile-up/tail information. This is an endpoint-level disentanglement ledger, not a claim that every source endpoint was retrained under every mask.

| window_mask                     | method                    | samples           | causal_before_or_at_peak | window_loss_score | fraction_of_joint_loss | rank_within_window |
| ------------------------------- | ------------------------- | ----------------- | ------------------------ | ----------------- | ---------------------- | ------------------ |
| late_tail_samples_12_17         | gradient_boosted_trees    | 12-13-14-15-16-17 | False                    | 0.01142           | 0.063343               | 1                  |
| late_tail_samples_12_17         | ridge                     | 12-13-14-15-16-17 | False                    | 0.031585          | 0.098273               | 2                  |
| late_tail_samples_12_17         | mlp                       | 12-13-14-15-16-17 | False                    | 0.044159          | 0.10678                | 3                  |
| late_tail_samples_12_17         | traditional_joint         | 12-13-14-15-16-17 | False                    | 0.10558           | 0.27669                | 4                  |
| late_tail_samples_12_17         | compact_sequence_residual | 12-13-14-15-16-17 | False                    | 0.13893           | 0.34315                | 5                  |
| late_tail_samples_12_17         | 1d_cnn                    | 12-13-14-15-16-17 | False                    | 0.16878           | 0.31757                | 6                  |
| peak_charge_samples_8_11        | traditional_joint         | 8-9-10-11         | True                     | 0.011277          | 0.029553               | 1                  |
| peak_charge_samples_8_11        | gradient_boosted_trees    | 8-9-10-11         | True                     | 0.020751          | 0.1151                 | 2                  |
| peak_charge_samples_8_11        | compact_sequence_residual | 8-9-10-11         | True                     | 0.020944          | 0.051729               | 3                  |
| peak_charge_samples_8_11        | ridge                     | 8-9-10-11         | True                     | 0.051532          | 0.16034                | 4                  |
| peak_charge_samples_8_11        | 1d_cnn                    | 8-9-10-11         | True                     | 0.088422          | 0.16637                | 5                  |
| peak_charge_samples_8_11        | mlp                       | 8-9-10-11         | True                     | 0.15404           | 0.37247                | 6                  |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees    | 0-1-2-3           | True                     | 0.013736          | 0.076189               | 1                  |
| pretrigger_pedestal_samples_0_3 | mlp                       | 0-1-2-3           | True                     | 0.070454          | 0.17036                | 2                  |
| pretrigger_pedestal_samples_0_3 | traditional_joint         | 0-1-2-3           | True                     | 0.070788          | 0.18551                | 3                  |
| pretrigger_pedestal_samples_0_3 | 1d_cnn                    | 0-1-2-3           | True                     | 0.071386          | 0.13432                | 4                  |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 0-1-2-3           | True                     | 0.072453          | 0.17895                | 5                  |
| pretrigger_pedestal_samples_0_3 | ridge                     | 0-1-2-3           | True                     | 0.074455          | 0.23166                | 6                  |
| rising_edge_samples_4_7         | gradient_boosted_trees    | 4-5-6-7           | True                     | 0.10556           | 0.58548                | 1                  |
| rising_edge_samples_4_7         | mlp                       | 4-5-6-7           | True                     | 0.10874           | 0.26294                | 2                  |
| rising_edge_samples_4_7         | ridge                     | 4-5-6-7           | True                     | 0.12967           | 0.40346                | 3                  |
| rising_edge_samples_4_7         | compact_sequence_residual | 4-5-6-7           | True                     | 0.14416           | 0.35607                | 4                  |
| rising_edge_samples_4_7         | traditional_joint         | 4-5-6-7           | True                     | 0.15858           | 0.41558                | 5                  |
| rising_edge_samples_4_7         | 1d_cnn                    | 4-5-6-7           | True                     | 0.1691            | 0.31818                | 6                  |

Window winners:

| window_mask                     | method                 | window_loss_score | fraction_of_joint_loss |
| ------------------------------- | ---------------------- | ----------------- | ---------------------- |
| late_tail_samples_12_17         | gradient_boosted_trees | 0.01142           | 0.063343               |
| peak_charge_samples_8_11        | traditional_joint      | 0.011277          | 0.029553               |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees | 0.013736          | 0.076189               |
| rising_edge_samples_4_7         | gradient_boosted_trees | 0.10556           | 0.58548                |

## Leakage, Systematics, and Caveats
| method                    | timing_mediated_fraction | late_tail_fraction_of_joint_loss | noncausal_tail_flag | too_good_pid_flag | interpretation                                               |
| ------------------------- | ------------------------ | -------------------------------- | ------------------- | ----------------- | ------------------------------------------------------------ |
| compact_sequence_residual | 0.31662                  | 0.34315                          | True                | True              | requires tail-ablation guard before PID promotion            |
| traditional_joint         | 0.41781                  | 0.27669                          | True                | True              | requires tail-ablation guard before PID promotion            |
| 1d_cnn                    | 0.26989                  | 0.31757                          | False               | False             | no primary noncausal tail warning under registered threshold |
| mlp                       | 0.31744                  | 0.10678                          | False               | False             | no primary noncausal tail warning under registered threshold |
| ridge                     | 0.47886                  | 0.098273                         | False               | False             | no primary noncausal tail warning under registered threshold |
| gradient_boosted_trees    | 0.72148                  | 0.063343                         | False               | False             | no primary noncausal tail warning under registered threshold |

Systematic uncertainties:

- PID labels are weak/action labels from the existing benchmark, not a newly observed external particle-truth branch.
- Energy resolution inherits GEANT4/Birks and material-response assumptions from the calibrated energy bridge.
- Source endpoint panels are compatible and raw-ROOT-derived, but not one monolithic multitask retraining job.
- Late-tail information is valid for pile-up and saturation recovery; it becomes a promotion risk only when PID gains depend on noncausal samples.
- Run-block bootstrap intervals cover observed run-to-run variation but cannot cover unobserved beam settings.
- Transformer/attention rows are retained as sensitivity evidence, but the local source panels do not contain a complete PID-energy-stress transformer row eligible for the primary winner rule.

## Transformer and Attention Sensitivity
| architecture | endpoint         | metric      | value    | ci_low   | ci_high | eligible_for_complete_panel | reason                                                                                                 |
| ------------ | ---------------- | ----------- | -------- | -------- | ------- | --------------------------- | ------------------------------------------------------------------------------------------------------ |
| attention    | timing           | sigma68_ns  | 1.4067   | 1.0172   | 1.6387  | False                       | timing architecture row exists, but no complete PID-energy-stress attention row exists                 |
| attention    | two_pulse        | time_rms_ns | 14.102   | 13.893   | 14.338  | False                       | two-pulse architecture row exists, but no complete PID-energy-stress attention row exists              |
| transformer  | energy           | res68_frac  | 0.12644  | 0.12037  | 0.14398 | False                       | energy/saturation transformer row exists, but PID transformer head was not audited in the source panel |
| transformer  | saturation_onset | res68_frac  | 0.096004 | 0.091987 | 0.10443 | False                       | saturation transformer stress row exists, but full PID-energy-stress eligibility is incomplete         |

## Calibration and Strata Ledger
The claim asks for calibration ECE and deltas across support strata. The table below records the PID calibration ECE from the source run-held-out PID benchmark and the energy R68/bias rows for saturation, pile-up, baseline, and late-shape/depth support strata. The support axes are ticket-local labels over source strata; they are included to prevent the winner from being interpreted as a single global score with no stress decomposition.

PID calibration:

| method                    | source_method                         | n     | primary_metric | metric_ci_low | metric_ci_high | secondary_metric | secondary_ci_low | secondary_ci_high |
| ------------------------- | ------------------------------------- | ----- | -------------- | ------------- | -------------- | ---------------- | ---------------- | ----------------- |
| traditional_joint         | traditional_charge_depth_logistic     | 19424 | 1              | 1             | 1              | 0.00015007       | 0.00014434       | 0.0001574         |
| ridge                     | ML_ridge_waveform                     | 19424 | 0.85132        | 0.84477       | 0.86219        | 0.031782         | 0.019691         | 0.057245          |
| gradient_boosted_trees    | ML_gradient_boosted_trees             | 19424 | 0.92801        | 0.92161       | 0.93523        | 0.034018         | 0.024732         | 0.050619          |
| mlp                       | ML_mlp                                | 19424 | 0.94709        | 0.94072       | 0.95407        | 0.013142         | 0.0094019        | 0.02526           |
| 1d_cnn                    | NN_1d_cnn                             | 19424 | 0.72677        | 0.70758       | 0.74843        | 0.14087          | 0.12165          | 0.15798           |
| compact_sequence_residual | NN_action_gated_residual_ensemble_new | 19424 | 1              | 1             | 1              | 0.0018029        | 0.0018029        | 0.001803          |

Energy/support strata:

| support_axis              | stratum                   | method                    | source_method          | n      | primary_metric | metric_ci_low | metric_ci_high | secondary_metric | secondary_ci_low | secondary_ci_high |
| ------------------------- | ------------------------- | ------------------------- | ---------------------- | ------ | -------------- | ------------- | -------------- | ---------------- | ---------------- | ----------------- |
| saturation                | adc_saturation_onset      | traditional_joint         | geant4_birks_lookup    | 106217 | 0.048498       | 0.047445      | 0.051147       | -0.040403        | -0.042047        | -0.039596         |
| pileup                    | pileup_or_multihit        | traditional_joint         | geant4_birks_lookup    | 27765  | 0.12595        | 0.10955       | 0.14223        | -0.019433        | -0.023166        | -0.017358         |
| baseline                  | pedestal_drift_proxy_high | traditional_joint         | geant4_birks_lookup    | 166426 | 0.033216       | 0.032506      | 0.034436       | -0.023258        | -0.024803        | -0.021672         |
| late_shape_or_stave_depth | late_pulse_shape          | traditional_joint         | geant4_birks_lookup    | 15256  | 0.11667        | 0.10323       | 0.13149        | -0.017026        | -0.019626        | -0.015245         |
| saturation                | adc_saturation_onset      | ridge                     | ridge                  | 106217 | 0.054955       | 0.052796      | 0.05927        | -0.025678        | -0.030184        | -0.015553         |
| pileup                    | pileup_or_multihit        | ridge                     | ridge                  | 27765  | 0.20977        | 0.20202       | 0.2239         | -0.035137        | -0.039369        | -0.030638         |
| baseline                  | pedestal_drift_proxy_high | ridge                     | ridge                  | 166426 | 0.095819       | 0.091919      | 0.1041         | -0.0394          | -0.050336        | -0.012709         |
| late_shape_or_stave_depth | late_pulse_shape          | ridge                     | ridge                  | 15256  | 0.21895        | 0.20795       | 0.22729        | -0.061874        | -0.066297        | -0.057852         |
| saturation                | adc_saturation_onset      | gradient_boosted_trees    | gradient_boosted_trees | 106217 | 0.056214       | 0.05172       | 0.062684       | -0.037918        | -0.040958        | -0.035405         |
| pileup                    | pileup_or_multihit        | gradient_boosted_trees    | gradient_boosted_trees | 27765  | 0.18875        | 0.18298       | 0.198          | -0.12668         | -0.13778         | -0.11759          |
| baseline                  | pedestal_drift_proxy_high | gradient_boosted_trees    | gradient_boosted_trees | 166426 | 0.034871       | 0.028878      | 0.047819       | -0.011291        | -0.013936        | -0.0081514        |
| late_shape_or_stave_depth | late_pulse_shape          | gradient_boosted_trees    | gradient_boosted_trees | 15256  | 0.21945        | 0.20667       | 0.23512        | -0.15082         | -0.16219         | -0.13591          |
| saturation                | adc_saturation_onset      | mlp                       | mlp                    | 106217 | 0.57333        | 0.57049       | 0.57559        | -0.5564          | -0.55931         | -0.55249          |
| pileup                    | pileup_or_multihit        | mlp                       | mlp                    | 27765  | 0.64683        | 0.58939       | 0.76738        | -0.24094         | -0.33681         | -0.19922          |
| baseline                  | pedestal_drift_proxy_high | mlp                       | mlp                    | 166426 | 0.71733        | 0.71127       | 0.72305        | -0.68222         | -0.69472         | -0.66161          |
| late_shape_or_stave_depth | late_pulse_shape          | mlp                       | mlp                    | 15256  | 0.65027        | 0.59105       | 0.70699        | -0.045602        | -0.22471         | 0.037297          |
| saturation                | adc_saturation_onset      | 1d_cnn                    | 1d_cnn                 | 106217 | 0.18976        | 0.18096       | 0.19881        | -0.16048         | -0.1659          | -0.15092          |
| pileup                    | pileup_or_multihit        | 1d_cnn                    | 1d_cnn                 | 27765  | 0.42682        | 0.4229        | 0.43316        | 0.016856         | -0.10573         | 0.071744          |
| baseline                  | pedestal_drift_proxy_high | 1d_cnn                    | 1d_cnn                 | 166426 | 0.27378        | 0.26298       | 0.28614        | -0.2061          | -0.21625         | -0.1891           |
| late_shape_or_stave_depth | late_pulse_shape          | 1d_cnn                    | 1d_cnn                 | 15256  | 0.51866        | 0.49317       | 0.55146        | 0.29179          | 0.22448          | 0.32479           |
| saturation                | adc_saturation_onset      | compact_sequence_residual | physics_residual_mlp   | 106217 | 0.03877        | 0.035885      | 0.044714       | -0.012757        | -0.017291        | -0.0064817        |
| pileup                    | pileup_or_multihit        | compact_sequence_residual | physics_residual_mlp   | 27765  | 0.1815         | 0.17434       | 0.18523        | -0.081669        | -0.09524         | -0.055665         |
| baseline                  | pedestal_drift_proxy_high | compact_sequence_residual | physics_residual_mlp   | 166426 | 0.062202       | 0.048004      | 0.085837       | -0.021071        | -0.025551        | -0.011432         |
| late_shape_or_stave_depth | late_pulse_shape          | compact_sequence_residual | physics_residual_mlp   | 15256  | 0.19093        | 0.18104       | 0.19726        | -0.075142        | -0.083523        | -0.058647         |

## Scientific Verdict and Next Test
The S29c winner is `gradient_boosted_trees`. The result favors a cautious interpretation: pulse shape appears useful only after timing, pile-up, saturation, pedestal, and late-tail support are reported together. The highest-information follow-up is an event-level masked-window retraining study that makes the compact transformer/sequence family eligible under the same complete-panel rule rather than treating it as endpoint sensitivity.

## Source Provenance
| source        | path                                                                                 | sha256_result                                                    |
| ------------- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| s25a          | reports/1783751737.13516.61447038__s25a_joint_pid_energy_pileup_saturation           | 7452583c868d4eaf1d9f56ebb1c4c740501209280d0843128183d4e45b95e57b |
| endpoint      | reports/1783745883.3840.006f2c7d__pulse_pid_timing_waveform_ablation_bakeoff         | 6746ba59607a997b881fcb10955b183254c8c6103bcd0012f4a7a5a27aaeffce |
| causal_timing | reports/1783751737.13524.25796187__causal_timing_pileup_deconvolution                | 6415ab221e9158b12e05f7b5de4fe95ed0f79ac4cc6042868a236dca86118260 |
| s25b          | reports/1783762816.2490.722918d7__s25b_saturation_onset_hysteresis_waveform_recovery | 707017a2d1ec5e38cbf2103e41226e4387520f91deb618d0f9b862ea3e14e012 |

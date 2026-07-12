# S29c - Causal Pulse-Window PID Energy Ablation

Ticket: `1783809165.2835.20015c6e`  
Worker: `testbeam-laptop-1`  
Project: `testbeam`

## Abstract
S29c asks which of the 18 B-stack pulse samples carry causal PID and energy information, and which instead behave like pedestal, saturation, pile-up, or late-tail nuisance support. The study first reproduces the canonical selected-pulse count directly from raw ROOT, then benchmarks a strong traditional charge/template method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact causal sequence/residual architecture on run-held-out endpoint panels with run-block bootstrap confidence intervals. The named winner in `result.json` is **gradient_boosted_trees**, with weighted joint loss 0.180289. Compared with S24-S28, this ticket is not another global waveform bakeoff: it isolates the sample windows responsible for PID/energy gain and reports late-tail and pedestal promotion guards.

## Pre-Registered Target
Before looking at S29c outputs, the winner rule was fixed as the minimum weighted joint loss over the complete method panel. The score combines PID AUC loss, fractional energy sigma68, timing sigma68, pile-up average-precision loss, saturation recovery width, pedestal MAE, and absolute energy bias. All intervals are inherited from or computed on held-out run blocks, not event-resampled rows.

The registered loss is

`L_m = w_pid(1-AUC_pid,m) + w_E R68_E,m + w_t sigma_t,m/1.5 + w_p(1-AP_pileup,m)/0.75 + w_s R68_sat,m + w_b MAE_ped,m/260.701 + w_bias |bias_E,m|`.

|   pid_auc_loss |   energy_res68_frac |   timing_sigma68_norm |   pileup_ap_loss |   saturation_res68_frac |   pedestal_mae_norm |   energy_bias_abs |
|---------------:|--------------------:|----------------------:|-----------------:|------------------------:|--------------------:|------------------:|
|           0.23 |                0.22 |                  0.16 |             0.14 |                    0.13 |                0.07 |              0.05 |

## Raw ROOT Reproduction
The analysis opens `h101/HRDv` in every configured `hrdb_run_XXXX.root`, reshapes the waveform branch to `(event, channel, sample)`, subtracts the median of samples 0-3 per channel, and counts B2/B4/B6/B8 pulses with maximum corrected amplitude above 1000 ADC. This is the reproduce-first gate for the ticket.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |       0 | True   |

## Run Split and Bootstrap
The split is by complete source runs. The four groups are sample-I calibration, sample-I analysis, sample-II calibration, and sample-II analysis; no event from a held-out run is used for fitting a method row. Bootstrap intervals are percentile intervals over run blocks:

`S_b = {r_1, ..., r_R},  theta_b = T(union_{r in S_b} D_r),  CI_95 = [q_0.025(theta_b), q_0.975(theta_b)]`.

This is intentionally conservative for gain, pedestal, and rate drifts that are coherent within a run.

## Method Panel
| method                    | family           | description                                                                                         |
|:--------------------------|:-----------------|:----------------------------------------------------------------------------------------------------|
| traditional_joint         | traditional      | matched-filter/template timing plus CFD-aligned charge-window and range-energy likelihood           |
| ridge                     | ml_linear        | standardized linear ridge waveform-window and tabular model                                         |
| gradient_boosted_trees    | ml_tree          | histogram gradient-boosted trees on causal pulse-window, charge, depth, and timing summaries        |
| mlp                       | neural_tabular   | multilayer perceptron on engineered pulse-window summaries                                          |
| 1d_cnn                    | neural_waveform  | one-dimensional convolutional waveform model over the 18-sample pulse                               |
| compact_sequence_residual | new_architecture | compact causal sequence/residual architecture using GRU, residual MLP, and gated-CNN endpoint heads |

The traditional comparator is a matched-filter/template and charge-depth likelihood method, not a strawman. Ridge tests linear accessibility of each registered pulse window. Gradient-boosted trees test nonlinear threshold and saturation interactions. The MLP and 1D-CNN test tabular and local waveform neural capacity. The compact sequence/residual architecture is the new architecture: it uses the source panel's GRU, residual MLP, and gated-CNN endpoint heads only where the complete run-held-out evidence exists.

## Primary Head-to-Head Results
| method                    | family           |   pid_auc |   energy_res68_frac |   timing_sigma68_ns |   pileup_average_precision |   saturation_hysteresis_res68 |   pedestal_mae_adc |   joint_loss_score |
|:--------------------------|:-----------------|----------:|--------------------:|--------------------:|---------------------------:|------------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees    | ml_tree          |   0.92801 |            0.056685 |              1.2194 |                   0.98314  |                      0.03137  |             48.879 |            0.18029 |
| ridge                     | ml_linear        |   0.85132 |            0.096673 |              1.4428 |                   0.94027  |                      0.22846  |            260.7   |            0.3214  |
| traditional_joint         | traditional      |   1       |            0.040244 |              1.4946 |                   0.26663  |                      0.040393 |            260.7   |            0.38158 |
| compact_sequence_residual | new_architecture |   1       |            0.05868  |              1.2018 |                   0.053436 |                      0.12578  |            260.7   |            0.40487 |
| mlp                       | neural_tabular   |   0.94709 |            0.69235  |              1.2308 |                   0.91624  |                      0.023274 |            260.7   |            0.41356 |
| 1d_cnn                    | neural_waveform  |   0.72677 |            0.2657   |              1.3447 |                   0.043205 |                      0.071081 |            260.7   |            0.53147 |

## Bootstrap Confidence Intervals
| method                    |   pid_auc_ci_low |   pid_auc_ci_high |   energy_res68_ci_low |   energy_res68_ci_high |   timing_sigma68_ci_low |   timing_sigma68_ci_high |   pileup_ap_ci_low |   pileup_ap_ci_high |   saturation_hysteresis_res68_ci_low |   saturation_hysteresis_res68_ci_high |
|:--------------------------|-----------------:|------------------:|----------------------:|-----------------------:|------------------------:|-------------------------:|-------------------:|--------------------:|-------------------------------------:|--------------------------------------:|
| gradient_boosted_trees    |          0.92161 |           0.93523 |              0.048804 |               0.067197 |                 0.91693 |                   1.4712 |           0.98253  |            0.985    |                             0.02943  |                              0.034378 |
| ridge                     |          0.84477 |           0.86219 |              0.088716 |               0.11721  |                 1.1498  |                   1.6331 |           0.93035  |            0.94669  |                             0.19857  |                              0.25723  |
| traditional_joint         |          1       |           1       |              0.038857 |               0.041606 |                 1.3262  |                   1.6549 |           0.26225  |            0.27387  |                             0.032328 |                              0.049645 |
| compact_sequence_residual |          1       |           1       |              0.049025 |               0.077882 |                 1.0215  |                   1.5067 |           0.043581 |            0.05375  |                             0.1116   |                              0.14232  |
| mlp                       |          0.94072 |           0.95407 |              0.68424  |               0.69965  |                 1.033   |                   1.4806 |           0.89724  |            0.94041  |                             0.020997 |                              0.027213 |
| 1d_cnn                    |          0.70758 |           0.74843 |              0.24927  |               0.28908  |                 1.0545  |                   1.6322 |           0.041677 |            0.045876 |                             0.06481  |                              0.078608 |

Winner detail: `gradient_boosted_trees` has PID AUC 0.92801 [0.92161, 0.93523], energy R68 0.05668 [0.048804, 0.067197], timing sigma68 1.21945 ns [0.91693, 1.4712].

## Causal Window Attribution
The endpoint losses are projected onto four pre-registered windows: samples 0-3 for pedestal and baseline memory, samples 4-7 for rising-edge timing and early overlap, samples 8-11 for peak charge and saturation onset, and samples 12-17 for late pile-up/tail information and noncausal PID risk.

| window_mask                     | method                    | samples           | causal_before_or_at_peak   |   window_loss_score |   fraction_of_joint_loss |   rank_within_window |
|:--------------------------------|:--------------------------|:------------------|:---------------------------|--------------------:|-------------------------:|---------------------:|
| late_tail_samples_12_17         | gradient_boosted_trees    | 12-13-14-15-16-17 | False                      |            0.01142  |                 0.063343 |                    1 |
| late_tail_samples_12_17         | ridge                     | 12-13-14-15-16-17 | False                      |            0.031585 |                 0.098273 |                    2 |
| late_tail_samples_12_17         | mlp                       | 12-13-14-15-16-17 | False                      |            0.044159 |                 0.10678  |                    3 |
| late_tail_samples_12_17         | traditional_joint         | 12-13-14-15-16-17 | False                      |            0.10558  |                 0.27669  |                    4 |
| late_tail_samples_12_17         | compact_sequence_residual | 12-13-14-15-16-17 | False                      |            0.13893  |                 0.34315  |                    5 |
| late_tail_samples_12_17         | 1d_cnn                    | 12-13-14-15-16-17 | False                      |            0.16878  |                 0.31757  |                    6 |
| peak_charge_samples_8_11        | traditional_joint         | 8-9-10-11         | True                       |            0.011277 |                 0.029553 |                    1 |
| peak_charge_samples_8_11        | gradient_boosted_trees    | 8-9-10-11         | True                       |            0.020751 |                 0.1151   |                    2 |
| peak_charge_samples_8_11        | compact_sequence_residual | 8-9-10-11         | True                       |            0.020944 |                 0.051729 |                    3 |
| peak_charge_samples_8_11        | ridge                     | 8-9-10-11         | True                       |            0.051532 |                 0.16034  |                    4 |
| peak_charge_samples_8_11        | 1d_cnn                    | 8-9-10-11         | True                       |            0.088422 |                 0.16637  |                    5 |
| peak_charge_samples_8_11        | mlp                       | 8-9-10-11         | True                       |            0.15404  |                 0.37247  |                    6 |
| pretrigger_pedestal_samples_0_3 | gradient_boosted_trees    | 0-1-2-3           | True                       |            0.013736 |                 0.076189 |                    1 |
| pretrigger_pedestal_samples_0_3 | mlp                       | 0-1-2-3           | True                       |            0.070454 |                 0.17036  |                    2 |
| pretrigger_pedestal_samples_0_3 | traditional_joint         | 0-1-2-3           | True                       |            0.070788 |                 0.18551  |                    3 |
| pretrigger_pedestal_samples_0_3 | 1d_cnn                    | 0-1-2-3           | True                       |            0.071386 |                 0.13432  |                    4 |
| pretrigger_pedestal_samples_0_3 | compact_sequence_residual | 0-1-2-3           | True                       |            0.072453 |                 0.17895  |                    5 |
| pretrigger_pedestal_samples_0_3 | ridge                     | 0-1-2-3           | True                       |            0.074455 |                 0.23166  |                    6 |
| rising_edge_samples_4_7         | gradient_boosted_trees    | 4-5-6-7           | True                       |            0.10556  |                 0.58548  |                    1 |
| rising_edge_samples_4_7         | mlp                       | 4-5-6-7           | True                       |            0.10874  |                 0.26294  |                    2 |
| rising_edge_samples_4_7         | ridge                     | 4-5-6-7           | True                       |            0.12967  |                 0.40346  |                    3 |
| rising_edge_samples_4_7         | compact_sequence_residual | 4-5-6-7           | True                       |            0.14416  |                 0.35607  |                    4 |
| rising_edge_samples_4_7         | traditional_joint         | 4-5-6-7           | True                       |            0.15858  |                 0.41558  |                    5 |
| rising_edge_samples_4_7         | 1d_cnn                    | 4-5-6-7           | True                       |            0.1691   |                 0.31818  |                    6 |

Window winners:

- Pretrigger/pedestal: `gradient_boosted_trees`.
- Rising-edge/timing: `gradient_boosted_trees`.
- Peak-charge PID/energy: `traditional_joint`.
- Late-tail stress: `gradient_boosted_trees`.

## Leakage and Promotion Guards
| method                    |   timing_mediated_fraction |   late_tail_fraction_of_joint_loss | noncausal_tail_flag   | too_good_pid_flag   | interpretation                                               |
|:--------------------------|---------------------------:|-----------------------------------:|:----------------------|:--------------------|:-------------------------------------------------------------|
| compact_sequence_residual |                    0.31662 |                           0.34315  | True                  | True                | requires tail-ablation guard before PID promotion            |
| traditional_joint         |                    0.41781 |                           0.27669  | True                  | True                | requires tail-ablation guard before PID promotion            |
| 1d_cnn                    |                    0.26989 |                           0.31757  | False                 | False               | no primary noncausal tail warning under registered threshold |
| mlp                       |                    0.31744 |                           0.10678  | False                 | False               | no primary noncausal tail warning under registered threshold |
| ridge                     |                    0.47886 |                           0.098273 | False                 | False               | no primary noncausal tail warning under registered threshold |
| gradient_boosted_trees    |                    0.72148 |                           0.063343 | False                 | False               | no primary noncausal tail warning under registered threshold |

The promotion rule is deliberately skeptical: a high PID score is not promoted as detector PID physics if it depends strongly on samples 12-17 or if it lacks a pedestal and saturation stress panel. Late samples are valid for pile-up and recovery; they are unsafe as the sole explanation of PID/energy gain.

## Compact Transformer / Attention Sensitivity
| architecture   | endpoint         | metric      |     value |    ci_low |   ci_high | eligible_for_complete_panel   | reason                                                                                                 |
|:---------------|:-----------------|:------------|----------:|----------:|----------:|:------------------------------|:-------------------------------------------------------------------------------------------------------|
| attention      | timing           | sigma68_ns  |  1.4067   |  1.0172   |   1.6387  | False                         | timing architecture row exists, but no complete PID-energy-stress attention row exists                 |
| attention      | two_pulse        | time_rms_ns | 14.102    | 13.893    |  14.338   | False                         | two-pulse architecture row exists, but no complete PID-energy-stress attention row exists              |
| transformer    | energy           | res68_frac  |  0.12644  |  0.12037  |   0.14398 | False                         | energy/saturation transformer row exists, but PID transformer head was not audited in the source panel |
| transformer    | saturation_onset | res68_frac  |  0.096004 |  0.091987 |   0.10443 | False                         | saturation transformer stress row exists, but full PID-energy-stress eligibility is incomplete         |

The 18-sample sequence is short enough for compact sequence models, but the available attention/transformer rows are endpoint-incomplete. They are retained as sensitivity evidence and excluded from the winner rule unless a future ticket retrains all masks event-level on the same complete run split.

## Systematic Uncertainties
- Endpoint heterogeneity: PID, energy, timing, pile-up, saturation, and pedestal rows come from compatible raw-ROOT-derived studies rather than one monolithic retraining job.
- Weak PID labels: PID is represented by calibrated charge/depth and waveform proxies, not new external particle-truth labels.
- Energy bridge: energy metrics inherit the GEANT4/Birks and material-response assumptions of the source panels.
- Window projection: the sample-window score is an endpoint-level causal attribution, not an event-level masked retraining for every architecture.
- Run-block support: bootstrap intervals reflect the available run groups and cannot cover unobserved beam or gain settings.

## Caveats
- S29c should be read as a promotion and ablation audit, not as a new definitive particle-ID calibration.
- A noncausal tail flag is a warning condition; it does not prove every late-tail feature is leakage.
- The traditional method remains scientifically valuable where interpretability or monotonic charge response matters, even though it does not win the composite score.
- The compact sequence/residual architecture is only promoted where the source rows were complete; incomplete transformer rows are sensitivity checks.

## Source Provenance
| source        | path                                                                                 | sha256_result                                                    |
|:--------------|:-------------------------------------------------------------------------------------|:-----------------------------------------------------------------|
| s25a          | reports/1783751737.13516.61447038__s25a_joint_pid_energy_pileup_saturation           | 7452583c868d4eaf1d9f56ebb1c4c740501209280d0843128183d4e45b95e57b |
| endpoint      | reports/1783745883.3840.006f2c7d__pulse_pid_timing_waveform_ablation_bakeoff         | 6746ba59607a997b881fcb10955b183254c8c6103bcd0012f4a7a5a27aaeffce |
| causal_timing | reports/1783751737.13524.25796187__causal_timing_pileup_deconvolution                | 6415ab221e9158b12e05f7b5de4fe95ed0f79ac4cc6042868a236dca86118260 |
| s25b          | reports/1783762816.2490.722918d7__s25b_saturation_onset_hysteresis_waveform_recovery | 707017a2d1ec5e38cbf2103e41226e4387520f91deb618d0f9b862ea3e14e012 |

## Conclusion
`result.json` names `gradient_boosted_trees` as the S29c winner. The causal-window result says the most defensible PID/energy gains are those that survive peak-charge, rising-edge, pedestal, saturation, pile-up, and late-tail audits together. The next highest-information experiment is an event-level masked retraining ticket that makes the compact transformer eligible for the same complete-panel winner rule.

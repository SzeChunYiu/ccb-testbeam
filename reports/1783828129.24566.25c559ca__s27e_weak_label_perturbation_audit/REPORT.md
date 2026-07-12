# S27e - Weak-Label Perturbation Audit for S27d Event-Level Mask Winners

Ticket: `1783828129.24566.25c559ca`  
Worker: `testbeam-laptop-1`

## Abstract
S27e repeats the S27d event-native masked benchmark under five alternative PID/stress weak-label definitions, including fixed-efficiency stress thresholds. The raw ROOT selected-pulse count is reproduced exactly before any modeling. The lowest held-out joint loss is obtained by **traditional_charge_depth_timewalk** in scenario `nominal_s27d` under mask `pretrigger_0_3` with score 0.09794. The audit separates architecture performance from proxy-label choice by requiring every method to retrain from the same raw-derived event table for each scenario.

## Raw ROOT Reproduction
The script opens `h101/HRDv`, reshapes each row to `(event, channel, sample)`, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with corrected peak above 1000 ADC.

| quantity                           | expected | reproduced | delta | pass |
| ---------------------------------- | -------- | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737   | 640737     | 0     | True |
| sample_i_calib selected pulses     | 248745   | 248745     | 0     | True |
| sample_i_analysis selected pulses  | 252266   | 252266     | 0     | True |
| sample_ii_calib selected pulses    | 14630    | 14630      | 0     | True |
| sample_ii_analysis selected pulses | 125096   | 125096     | 0     | True |

## Event Targets
For event `i`, corrected waveform `x_{ics}` is obtained from raw ADC waveform `a_{ics}` by

`x_{ics}=a_{ics}-median_{s in {0,1,2,3}} a_{ics}`.

The event-level energy and timing endpoints are unchanged from S27d, while PID and stress are recomputed per scenario from full-window raw observables and then predicted from masked windows:

`E_i = log(1 + sum_{c,s} max(x_{ics},0))` for energy closure;
`D_i=(Q_{B6}+Q_{B8}) / sum_c Q_c` and `A_i=((Q_{B6}+Q_{B8})-(Q_{B2}+Q_{B4})) / sum_c Q_c` define PID perturbations;
`T_i = min_c CFD50(x_{ic})` as a timing proxy in sample units;
`S_i = 1{tail_i > Q_alpha^train or peak_i > Q_beta^train}` or the tail-only variant defines fixed-efficiency stress labels.

These are not external particle-truth labels; they are raw-data, event-native weak targets used to test whether the S27d winner is robust to proxy-label choice.

## Split and Confidence Intervals
Training runs are groups `sample_i_calib, sample_i_analysis, sample_ii_calib`; held-out runs are `sample_ii_analysis`. Each run is a complete block. Bootstrap intervals resample the held-out runs with replacement for 80 replicates.

## Label Scenarios
| scenario                | pid_rule              | pid_positive_train_fraction | pid_positive_heldout_fraction | stress_rule  | stress_positive_train_fraction | stress_positive_heldout_fraction | pid_threshold | stress_late_threshold | stress_peak_threshold |
| ----------------------- | --------------------- | --------------------------- | ----------------------------- | ------------ | ------------------------------ | -------------------------------- | ------------- | --------------------- | --------------------- |
| nominal_s27d            | distal_median         | 0.5                         | 0.70612                       | late_or_peak | 0.2978                         | 0.36122                          | 0.0054191     | 0.34619               | 8905.5                |
| pid_strict_distal_q60   | distal_quantile       | 0.4                         | 0.61592                       | late_or_peak | 0.2978                         | 0.36122                          | 0.0071596     | 0.34619               | 8905.5                |
| pid_charge_balanced_q50 | distal_charge_balance | 0.5                         | 0.70612                       | late_or_peak | 0.2978                         | 0.36122                          | -0.48916      | 0.34619               | 8905.5                |
| stress_fixed_eff90      | distal_median         | 0.5                         | 0.70612                       | late_or_peak | 0.19725                        | 0.25265                          | 0.0054191     | 0.3677                | 8470                  |
| stress_tail_only_eff85  | distal_median         | 0.5                         | 0.70612                       | late_only    | 0.15                           | 0.29959                          | 0.0054191     | 0.35773               | inf                   |

## Methods
- `traditional_charge_depth_timewalk`: fixed charge-window, distal-charge, late-tail, and CFD50 formulas with no event-row training.
- `ridge`: standardized linear ridge/logistic models.
- `gradient_boosted_trees`: histogram gradient boosting for nonlinear tabular closure.
- `mlp`: two-layer tabular neural network.
- `cnn1d`: neural model on convolution-like local difference features from the masked waveform.
- `residual_cnn_gru_new`: new residual sequence architecture approximation using cumulative/residual features and random forests, retained as the novel architecture family under perturbation.
- `attention_transformer_small`: transformer-like attention summary features over masked samples with boosted heads; included in the complete winner rule.

The joint score minimized in `result.json` is

`L = 0.28(1-AUC_PID) + 0.30 R68_E + 0.20 R68_T/2 + 0.17(1-AUC_stress) + 0.05 |bias_E|`.

## Primary Results
| scenario                | mask             | method                            | family      | joint_score | pid_auc | energy_res68 | timing_res68_samples | stress_auc | energy_bias |
| ----------------------- | ---------------- | --------------------------------- | ----------- | ----------- | ------- | ------------ | -------------------- | ---------- | ----------- |
| nominal_s27d            | pretrigger_0_3   | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| nominal_s27d            | rising_edge_4_7  | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| nominal_s27d            | peak_charge_8_11 | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| nominal_s27d            | late_tail_12_17  | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| nominal_s27d            | causal_0_11      | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| pid_charge_balanced_q50 | rising_edge_4_7  | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| pid_charge_balanced_q50 | pretrigger_0_3   | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| pid_charge_balanced_q50 | peak_charge_8_11 | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| nominal_s27d            | all_0_17         | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| pid_charge_balanced_q50 | all_0_17         | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| pid_charge_balanced_q50 | late_tail_12_17  | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| pid_charge_balanced_q50 | causal_0_11      | traditional_charge_depth_timewalk | traditional | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          | -0.65722    |
| stress_fixed_eff90      | rising_edge_4_7  | traditional_charge_depth_timewalk | traditional | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    | -0.65722    |
| stress_fixed_eff90      | causal_0_11      | traditional_charge_depth_timewalk | traditional | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    | -0.65722    |
| stress_fixed_eff90      | all_0_17         | traditional_charge_depth_timewalk | traditional | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    | -0.65722    |
| stress_fixed_eff90      | late_tail_12_17  | traditional_charge_depth_timewalk | traditional | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    | -0.65722    |
| stress_fixed_eff90      | pretrigger_0_3   | traditional_charge_depth_timewalk | traditional | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    | -0.65722    |
| stress_fixed_eff90      | peak_charge_8_11 | traditional_charge_depth_timewalk | traditional | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    | -0.65722    |
| pid_strict_distal_q60   | rising_edge_4_7  | traditional_charge_depth_timewalk | traditional | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          | -0.65722    |
| pid_strict_distal_q60   | pretrigger_0_3   | traditional_charge_depth_timewalk | traditional | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          | -0.65722    |
| pid_strict_distal_q60   | peak_charge_8_11 | traditional_charge_depth_timewalk | traditional | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          | -0.65722    |
| pid_strict_distal_q60   | late_tail_12_17  | traditional_charge_depth_timewalk | traditional | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          | -0.65722    |
| pid_strict_distal_q60   | causal_0_11      | traditional_charge_depth_timewalk | traditional | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          | -0.65722    |
| pid_strict_distal_q60   | all_0_17         | traditional_charge_depth_timewalk | traditional | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          | -0.65722    |

## Bootstrap Intervals
| scenario                | mask             | method                            | energy_res68_ci_low | energy_res68_ci_high | timing_res68_samples_ci_low | timing_res68_samples_ci_high | pid_auc_ci_low | pid_auc_ci_high | stress_auc_ci_low | stress_auc_ci_high |
| ----------------------- | ---------------- | --------------------------------- | ------------------- | -------------------- | --------------------------- | ---------------------------- | -------------- | --------------- | ----------------- | ------------------ |
| nominal_s27d            | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.1274              | 0.15608              | 0                           | 0                            | 0.90786        | 0.92712         | 1                 | 1                  |
| nominal_s27d            | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.12457             | 0.15606              | 0                           | 0                            | 0.90453        | 0.9241          | 1                 | 1                  |
| nominal_s27d            | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.12618             | 0.15212              | 0                           | 0                            | 0.90635        | 0.92701         | 1                 | 1                  |
| nominal_s27d            | late_tail_12_17  | traditional_charge_depth_timewalk | 0.1264              | 0.15299              | 0                           | 0                            | 0.90587        | 0.92479         | 1                 | 1                  |
| nominal_s27d            | causal_0_11      | traditional_charge_depth_timewalk | 0.12713             | 0.15791              | 0                           | 0                            | 0.90938        | 0.9264          | 1                 | 1                  |
| pid_charge_balanced_q50 | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.12625             | 0.15514              | 0                           | 0                            | 0.9059         | 0.92452         | 1                 | 1                  |
| pid_charge_balanced_q50 | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.12734             | 0.15515              | 0                           | 0                            | 0.907          | 0.92506         | 1                 | 1                  |
| pid_charge_balanced_q50 | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.12387             | 0.15367              | 0                           | 0                            | 0.9072         | 0.92449         | 1                 | 1                  |
| nominal_s27d            | all_0_17         | traditional_charge_depth_timewalk | 0.12768             | 0.15259              | 0                           | 0                            | 0.90914        | 0.92411         | 1                 | 1                  |
| pid_charge_balanced_q50 | all_0_17         | traditional_charge_depth_timewalk | 0.12713             | 0.15171              | 0                           | 0                            | 0.9053         | 0.92303         | 1                 | 1                  |
| pid_charge_balanced_q50 | late_tail_12_17  | traditional_charge_depth_timewalk | 0.12712             | 0.1574               | 0                           | 0                            | 0.90605        | 0.92341         | 1                 | 1                  |
| pid_charge_balanced_q50 | causal_0_11      | traditional_charge_depth_timewalk | 0.12577             | 0.15552              | 0                           | 0                            | 0.90637        | 0.92471         | 1                 | 1                  |
| stress_fixed_eff90      | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.12472             | 0.15841              | 0                           | 0                            | 0.9069         | 0.9228          | 0.99244           | 0.99967            |
| stress_fixed_eff90      | causal_0_11      | traditional_charge_depth_timewalk | 0.12472             | 0.15078              | 0                           | 0                            | 0.90668        | 0.92466         | 0.99188           | 0.99871            |
| stress_fixed_eff90      | all_0_17         | traditional_charge_depth_timewalk | 0.12673             | 0.15968              | 0                           | 0                            | 0.90814        | 0.92397         | 0.9924            | 0.99849            |
| stress_fixed_eff90      | late_tail_12_17  | traditional_charge_depth_timewalk | 0.12734             | 0.15317              | 0                           | 0                            | 0.90601        | 0.92421         | 0.9924            | 0.99848            |
| stress_fixed_eff90      | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.12713             | 0.15415              | 0                           | 0                            | 0.90539        | 0.92594         | 0.99244           | 0.99896            |
| stress_fixed_eff90      | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.12741             | 0.15416              | 0                           | 0                            | 0.90763        | 0.92725         | 0.99194           | 0.99892            |
| pid_strict_distal_q60   | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.12233             | 0.15576              | 0                           | 0                            | 0.90015        | 0.9291          | 1                 | 1                  |
| pid_strict_distal_q60   | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.12294             | 0.16263              | 0                           | 0                            | 0.90043        | 0.92818         | 1                 | 1                  |
| pid_strict_distal_q60   | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.12582             | 0.16185              | 0                           | 0                            | 0.90081        | 0.92695         | 1                 | 1                  |
| pid_strict_distal_q60   | late_tail_12_17  | traditional_charge_depth_timewalk | 0.12548             | 0.15606              | 0                           | 0                            | 0.89762        | 0.92735         | 1                 | 1                  |
| pid_strict_distal_q60   | causal_0_11      | traditional_charge_depth_timewalk | 0.12641             | 0.16039              | 0                           | 0                            | 0.90104        | 0.92567         | 1                 | 1                  |
| pid_strict_distal_q60   | all_0_17         | traditional_charge_depth_timewalk | 0.12693             | 0.15397              | 0                           | 0                            | 0.89896        | 0.927           | 1                 | 1                  |

## Scenario Winners
| scenario                | mask            | method                            | joint_score | pid_auc | energy_res68 | timing_res68_samples | stress_auc |
| ----------------------- | --------------- | --------------------------------- | ----------- | ------- | ------------ | -------------------- | ---------- |
| nominal_s27d            | pretrigger_0_3  | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | causal_0_11     | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | all_0_17        | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| stress_fixed_eff90      | rising_edge_4_7 | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_tail_only_eff85  | causal_0_11     | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |

## Method Stability
| scenario                | method                            | mask             | joint_score | pid_auc | stress_auc |
| ----------------------- | --------------------------------- | ---------------- | ----------- | ------- | ---------- |
| nominal_s27d            | traditional_charge_depth_timewalk | pretrigger_0_3   | 0.097941    | 0.91637 | 1          |
| nominal_s27d            | gradient_boosted_trees            | all_0_17         | 0.10258     | 0.99178 | 0.98913    |
| nominal_s27d            | residual_cnn_gru_new              | all_0_17         | 0.10975     | 0.98214 | 0.98786    |
| nominal_s27d            | attention_transformer_small       | all_0_17         | 0.18869     | 0.9761  | 0.95513    |
| nominal_s27d            | ridge                             | all_0_17         | 0.23261     | 0.98899 | 0.98461    |
| nominal_s27d            | mlp                               | all_0_17         | 0.3087      | 0.98942 | 0.99065    |
| nominal_s27d            | cnn1d                             | all_0_17         | 0.33999     | 0.98745 | 0.97312    |
| pid_charge_balanced_q50 | traditional_charge_depth_timewalk | causal_0_11      | 0.097941    | 0.91637 | 1          |
| pid_charge_balanced_q50 | gradient_boosted_trees            | all_0_17         | 0.10258     | 0.99178 | 0.98913    |
| pid_charge_balanced_q50 | residual_cnn_gru_new              | all_0_17         | 0.10975     | 0.98214 | 0.98786    |
| pid_charge_balanced_q50 | attention_transformer_small       | all_0_17         | 0.18869     | 0.9761  | 0.95513    |
| pid_charge_balanced_q50 | ridge                             | all_0_17         | 0.23261     | 0.98899 | 0.98461    |
| pid_charge_balanced_q50 | mlp                               | all_0_17         | 0.3087      | 0.98942 | 0.99065    |
| pid_charge_balanced_q50 | cnn1d                             | all_0_17         | 0.33999     | 0.98745 | 0.97312    |
| pid_strict_distal_q60   | traditional_charge_depth_timewalk | all_0_17         | 0.098745    | 0.9135  | 1          |
| pid_strict_distal_q60   | gradient_boosted_trees            | all_0_17         | 0.10306     | 0.99008 | 0.98913    |
| pid_strict_distal_q60   | residual_cnn_gru_new              | all_0_17         | 0.10954     | 0.98288 | 0.98786    |
| pid_strict_distal_q60   | attention_transformer_small       | all_0_17         | 0.18863     | 0.97629 | 0.95513    |
| pid_strict_distal_q60   | ridge                             | all_0_17         | 0.23252     | 0.98931 | 0.98461    |
| pid_strict_distal_q60   | mlp                               | all_0_17         | 0.30754     | 0.99358 | 0.99065    |
| pid_strict_distal_q60   | cnn1d                             | all_0_17         | 0.34036     | 0.98611 | 0.97312    |
| stress_fixed_eff90      | traditional_charge_depth_timewalk | rising_edge_4_7  | 0.098647    | 0.91637 | 0.99585    |
| stress_fixed_eff90      | gradient_boosted_trees            | all_0_17         | 0.10231     | 0.99178 | 0.99072    |
| stress_fixed_eff90      | residual_cnn_gru_new              | all_0_17         | 0.10923     | 0.98214 | 0.99089    |
| stress_fixed_eff90      | attention_transformer_small       | all_0_17         | 0.1893      | 0.9761  | 0.95151    |
| stress_fixed_eff90      | ridge                             | all_0_17         | 0.23743     | 0.98899 | 0.95625    |
| stress_fixed_eff90      | mlp                               | all_0_17         | 0.30891     | 0.98942 | 0.98945    |
| stress_fixed_eff90      | cnn1d                             | all_0_17         | 0.3377      | 0.98745 | 0.98657    |
| stress_tail_only_eff85  | traditional_charge_depth_timewalk | causal_0_11      | 0.099465    | 0.91637 | 0.99103    |
| stress_tail_only_eff85  | gradient_boosted_trees            | all_0_17         | 0.10213     | 0.99178 | 0.99183    |
| stress_tail_only_eff85  | residual_cnn_gru_new              | all_0_17         | 0.10932     | 0.98214 | 0.99037    |
| stress_tail_only_eff85  | attention_transformer_small       | all_0_17         | 0.18763     | 0.9761  | 0.96136    |
| stress_tail_only_eff85  | ridge                             | all_0_17         | 0.23105     | 0.98899 | 0.99378    |
| stress_tail_only_eff85  | mlp                               | peak_charge_8_11 | 0.30882     | 0.9571  | 0.9191     |
| stress_tail_only_eff85  | cnn1d                             | all_0_17         | 0.33801     | 0.98745 | 0.98475    |

## Best Method by Mask
| scenario                | mask             | method                            | joint_score | pid_auc | energy_res68 | timing_res68_samples | stress_auc |
| ----------------------- | ---------------- | --------------------------------- | ----------- | ------- | ------------ | -------------------- | ---------- |
| nominal_s27d            | all_0_17         | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| nominal_s27d            | causal_0_11      | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| nominal_s27d            | late_tail_12_17  | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| nominal_s27d            | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| nominal_s27d            | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| nominal_s27d            | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | all_0_17         | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | causal_0_11      | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | late_tail_12_17  | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_charge_balanced_q50 | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.097941    | 0.91637 | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | all_0_17         | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | causal_0_11      | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | late_tail_12_17  | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| pid_strict_distal_q60   | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.098745    | 0.9135  | 0.13888      | 0                    | 1          |
| stress_fixed_eff90      | all_0_17         | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_fixed_eff90      | causal_0_11      | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_fixed_eff90      | late_tail_12_17  | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_fixed_eff90      | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_fixed_eff90      | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_fixed_eff90      | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.098647    | 0.91637 | 0.13888      | 0                    | 0.99585    |
| stress_tail_only_eff85  | all_0_17         | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |
| stress_tail_only_eff85  | causal_0_11      | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |
| stress_tail_only_eff85  | late_tail_12_17  | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |
| stress_tail_only_eff85  | peak_charge_8_11 | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |
| stress_tail_only_eff85  | pretrigger_0_3   | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |
| stress_tail_only_eff85  | rising_edge_4_7  | traditional_charge_depth_timewalk | 0.099465    | 0.91637 | 0.13888      | 0                    | 0.99103    |

## Per-Run Held-Out Diagnostics
| scenario     | mask             | method                      | run | n_events | pid_auc | energy_res68 | timing_res68_samples | stress_auc |
| ------------ | ---------------- | --------------------------- | --- | -------- | ------- | ------------ | -------------------- | ---------- |
| nominal_s27d | all_0_17         | attention_transformer_small | 58  | 350      | 0.99427 | 0.074655     | 1.2397               | 0.98703    |
| nominal_s27d | all_0_17         | attention_transformer_small | 59  | 350      | 0.97169 | 0.19952      | 1.1783               | 0.93443    |
| nominal_s27d | all_0_17         | attention_transformer_small | 60  | 350      | 0.96841 | 0.35102      | 1.2631               | 0.94945    |
| nominal_s27d | all_0_17         | attention_transformer_small | 61  | 350      | 0.96684 | 0.35499      | 1.44                 | 0.94175    |
| nominal_s27d | all_0_17         | attention_transformer_small | 62  | 350      | 0.97699 | 0.31913      | 1.5065               | 0.92171    |
| nominal_s27d | all_0_17         | attention_transformer_small | 63  | 350      | 0.97689 | 0.10738      | 1.165                | 0.97025    |
| nominal_s27d | all_0_17         | attention_transformer_small | 65  | 350      | 0.98176 | 0.082632     | 1.1162               | 0.98628    |
| nominal_s27d | causal_0_11      | attention_transformer_small | 58  | 350      | 0.94146 | 0.088527     | 1.2079               | 0.98639    |
| nominal_s27d | causal_0_11      | attention_transformer_small | 59  | 350      | 0.94197 | 0.28184      | 1.1119               | 0.8913     |
| nominal_s27d | causal_0_11      | attention_transformer_small | 60  | 350      | 0.93642 | 0.38532      | 1.3242               | 0.92434    |
| nominal_s27d | causal_0_11      | attention_transformer_small | 61  | 350      | 0.94489 | 0.3849       | 1.4462               | 0.92872    |
| nominal_s27d | causal_0_11      | attention_transformer_small | 62  | 350      | 0.94419 | 0.34874      | 1.4169               | 0.8978     |
| nominal_s27d | causal_0_11      | attention_transformer_small | 63  | 350      | 0.94399 | 0.11775      | 1.053                | 0.9759     |
| nominal_s27d | causal_0_11      | attention_transformer_small | 65  | 350      | 0.95107 | 0.10503      | 1.0056               | 0.97712    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 58  | 350      | 0.94505 | 0.11991      | 1.5783               | 0.96839    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 59  | 350      | 0.92865 | 0.36589      | 1.6205               | 0.89383    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 60  | 350      | 0.92424 | 0.44633      | 1.6167               | 0.92972    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 61  | 350      | 0.93895 | 0.43843      | 1.7853               | 0.90933    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 62  | 350      | 0.92891 | 0.41439      | 1.8771               | 0.91306    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 63  | 350      | 0.9294  | 0.21405      | 1.599                | 0.95696    |
| nominal_s27d | late_tail_12_17  | attention_transformer_small | 65  | 350      | 0.92873 | 0.18853      | 1.5921               | 0.96805    |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 58  | 350      | 0.9223  | 0.1003       | 1.591                | 0.9737     |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 59  | 350      | 0.92863 | 0.30683      | 1.4913               | 0.88761    |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 60  | 350      | 0.92557 | 0.41811      | 1.6034               | 0.91563    |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 61  | 350      | 0.93668 | 0.42235      | 1.7858               | 0.90706    |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 62  | 350      | 0.94512 | 0.38202      | 1.7614               | 0.88963    |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 63  | 350      | 0.93428 | 0.16457      | 1.3763               | 0.96421    |
| nominal_s27d | peak_charge_8_11 | attention_transformer_small | 65  | 350      | 0.93553 | 0.14183      | 1.4261               | 0.97157    |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 58  | 350      | 0.62859 | 0.45124      | 1.3152               | 0.56606    |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 59  | 350      | 0.62418 | 0.74053      | 1.4697               | 0.66468    |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 60  | 350      | 0.65255 | 0.71618      | 1.5623               | 0.72618    |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 61  | 350      | 0.66618 | 0.61106      | 1.7638               | 0.7412     |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 62  | 350      | 0.61857 | 0.7899       | 1.8203               | 0.64004    |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 63  | 350      | 0.6537  | 0.64163      | 1.4824               | 0.61765    |
| nominal_s27d | pretrigger_0_3   | attention_transformer_small | 65  | 350      | 0.58552 | 0.701        | 1.2927               | 0.56485    |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 58  | 350      | 0.84483 | 0.06196      | 1.5404               | 0.9689     |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 59  | 350      | 0.86483 | 0.34989      | 1.4922               | 0.85888    |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 60  | 350      | 0.88047 | 0.47128      | 1.6367               | 0.89789    |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 61  | 350      | 0.86769 | 0.43321      | 1.8076               | 0.89073    |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 62  | 350      | 0.89616 | 0.41509      | 1.6722               | 0.85417    |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 63  | 350      | 0.87576 | 0.14173      | 1.4827               | 0.92739    |
| nominal_s27d | rising_edge_4_7  | attention_transformer_small | 65  | 350      | 0.87473 | 0.1082       | 1.4315               | 0.93987    |
| nominal_s27d | all_0_17         | cnn1d                       | 58  | 350      | 0.99124 | 0.32293      | 1.4712               | 0.9919     |
| nominal_s27d | all_0_17         | cnn1d                       | 59  | 350      | 0.9861  | 0.78489      | 1.6676               | 0.97076    |
| nominal_s27d | all_0_17         | cnn1d                       | 60  | 350      | 0.98972 | 0.86899      | 1.7758               | 0.96622    |
| nominal_s27d | all_0_17         | cnn1d                       | 61  | 350      | 0.97974 | 0.85104      | 1.8579               | 0.96029    |
| nominal_s27d | all_0_17         | cnn1d                       | 62  | 350      | 0.98859 | 0.76618      | 1.7824               | 0.95135    |
| nominal_s27d | all_0_17         | cnn1d                       | 63  | 350      | 0.98677 | 0.45725      | 1.4583               | 0.98746    |
| nominal_s27d | all_0_17         | cnn1d                       | 65  | 350      | 0.98737 | 0.37961      | 1.527                | 0.9986     |
| nominal_s27d | causal_0_11      | cnn1d                       | 58  | 350      | 0.95121 | 0.30896      | 1.5049               | 0.97873    |

## Systematics
The dominant systematic is still target definition: PID and stress are weak proxies derived from B-stack waveform topology, not external truth. S27e turns that systematic into an explicit nuisance axis by changing PID topology thresholds, adding a charge-balance PID definition, and replacing the nominal stress rule with fixed-efficiency and tail-only thresholds. The subsample is stratified by run to limit compute while preserving complete-run split semantics. Bootstrap intervals quantify held-out run variability within each weak-label scenario; they do not cover gain calibration, channel mapping, or ROOT decoding alternatives.

## Caveats
- The perturbations are raw-derived weak labels, not external particle-identification truth.
- Fixed-efficiency stress thresholds are defined on the training groups and can shift held-out prevalence when the sample-II distribution drifts.
- Late-tail masks are noncausal for online PID/timing promotion even when predictive.
- The neural rows are compact sklearn approximations of waveform architectures; the study is a controlled benchmark audit, not a final high-capacity network training campaign.

## Conclusion
`result.json` names `traditional_charge_depth_timewalk` in scenario `nominal_s27d` on `pretrigger_0_3` as the S27e winner. The scenario table reports whether the S27d-style tree winner remains competitive when PID and stress weak-label choices are perturbed under the same ridge, GBT, MLP, 1D-CNN, residual sequence, attention, and traditional-method panel.

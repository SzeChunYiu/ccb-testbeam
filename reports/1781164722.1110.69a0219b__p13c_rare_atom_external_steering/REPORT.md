# P13c rare-atom external steering dry run

- **Study ID:** P13c
- **Ticket:** `1781164722.1110.69a0219b`
- **Author:** testbeam-laptop-1
- **Date:** 2026-07-10
- **Depends on:** P13b frozen rare-atom promotion gates
- **Config:** `configs/p13c_1781164722_1110_69a0219b_rare_atom_external_steering.json`
- **Git commit:** `0574a649d0919344642222dae9942c4b4ad50ad0`

## Abstract

This dry run asks whether the P13b rare-atom promotion gates remain conservative when a promoted atom is used as an external steering variable for exactly one downstream consumer at a time.  The raw B-stack selected-pulse number is reproduced from ROOT before modeling.  The frozen P13b support, stability, harm, CI-width, and sample-balance gates are not retuned.  The overall winner named in `result.json` is **gradient_boosted_trees** for the **pid** consumer with utility 1.186 [1.166, 1.241] and shuffled-atom false-steering rate 0.020.

## 1. Raw ROOT Reproduction

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| S00 selected B-stave pulse records | 640737 | 640737 | 0 | 0 | True |

The reproduced count scans `HRDv` in `data/root/root/hrdb_run_*.root`, subtracts the median of samples 0--3 per channel, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.  This matches the P13b/S00 selected-pulse anchor and prevents downstream steering results from being detached from the raw data.

## 2. Frozen Traditional Gate

For atom `a`, stave `s`, and run `r`, the support ledger uses `n_{a,s,r}` and the effective run count

`N_eff(a,s) = (sum_r n_{a,s,r})^2 / sum_r n_{a,s,r}^2`.

The P13b gate is frozen: total support >= 80, `N_eff >= 4.0`, runs present >= 5, max run fraction <= 0.45, exact-binomial support CI width <= 0.08, harm rate <= 0.22, harm CI high <= 0.34, and Sample-I/Sample-II support imbalance <= 0.35.  P13c only intersects that frozen gate with one consumer endpoint at a time.

| atom | stave | n_total | runs_present | effective_runs | max_run_fraction | support_ci_width | harm_rate | harm_ci | traditional_decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| saturation_boundary | B8 | 2467 | 32 | 9.31 | 0.179 | 0.0123 | 0.116 | [0.104, 0.129] | promote |
| saturation_boundary | B2 | 436614 | 33 | 19.50 | 0.104 | 0.0023 | 0.054 | [0.053, 0.055] | defer |
| secondary_delayed_peak | B2 | 137341 | 33 | 27.43 | 0.053 | 0.0019 | 0.339 | [0.337, 0.342] | defer |
| baseline_excursion | B2 | 23032 | 33 | 24.29 | 0.071 | 0.0009 | 0.896 | [0.892, 0.900] | defer |
| secondary_delayed_peak | B4 | 21144 | 33 | 12.23 | 0.145 | 0.0078 | 0.502 | [0.495, 0.509] | defer |
| rare_s03f_topology | B6 | 14820 | 33 | 10.38 | 0.156 | 0.0106 | 0.323 | [0.316, 0.331] | defer |
| rare_s03f_topology | B4 | 14681 | 33 | 10.35 | 0.157 | 0.0071 | 0.454 | [0.446, 0.462] | defer |
| dropout_subclass | B2 | 14633 | 33 | 23.02 | 0.080 | 0.0007 | 0.939 | [0.935, 0.943] | defer |
| qtemplate_shift_proxy | B2 | 13668 | 33 | 22.66 | 0.082 | 0.0007 | 0.964 | [0.961, 0.967] | defer |
| saturation_boundary | B4 | 10277 | 33 | 15.30 | 0.130 | 0.0062 | 0.127 | [0.121, 0.134] | defer |
| secondary_delayed_peak | B6 | 10095 | 33 | 11.52 | 0.147 | 0.0097 | 0.426 | [0.417, 0.436] | defer |
| delayed_peak | B2 | 6229 | 33 | 24.46 | 0.064 | 0.0005 | 0.187 | [0.177, 0.197] | defer |
| rare_s03f_topology | B8 | 5591 | 33 | 9.47 | 0.172 | 0.0159 | 0.397 | [0.385, 0.410] | defer |
| delayed_peak | B4 | 5433 | 33 | 27.30 | 0.052 | 0.0047 | 0.565 | [0.551, 0.578] | defer |

## 3. Consumer Targets

A held-out atom/run/stave cell is labelled steering-safe for consumer `c` only if it is rare, passes the frozen P13b gate, has at least 20 selected pulses in the held-out run cell, and satisfies the consumer endpoint limit.  Timing uses `timing_tail_rate <= 0.25`; pile-up uses `pileup_excess_proxy <= 1.30`; charge uses `charge_res68_proxy <= 0.38`; PID uses `qshape_abs_mean <= 0.30`.  These limits are declared in the config before training and are not fitted per method.

| consumer | winner_method | winner_variant | positive_cells | best_utility | utility_ci | false_control | shuffled_false_steer_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| timing | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 17 | 1.047 | [0.962, 1.130] | 0.000 | 0.006 |
| pileup | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.08 | 24 | 1.080 | [1.008, 1.158] | 0.000 | 0.009 |
| charge | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 25 | 1.186 | [1.166, 1.241] | 0.000 | 0.020 |
| pid | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 25 | 1.186 | [1.166, 1.241] | 0.000 | 0.020 |

## 4. Benchmarked Methods

Each consumer benchmark uses leave-one-run-out folds.  The tested families are the frozen traditional support scorecard, ridge logistic regression, histogram gradient-boosted trees, one-hidden-layer MLP, a 1D convolutional network over the mean normalized atom waveform, and a new support-gated CNN whose convolutional waveform embedding is multiplicatively gated by the scalar support vector.  Scalar features exclude run identifiers, event identifiers, and labels.

The primary utility is

`U = AP + 0.25 recall - 2 false_control - 0.25 ECE - 1 shuffled_false_steer`.

The shuffled term is evaluated by permuting atom identities within run/stave blocks and measuring how often a method would steer when the shuffled atom no longer satisfies the frozen gate and endpoint label.  Confidence intervals are run-block bootstrap intervals.

| consumer | method | method_variant | average_precision | promotion_utility | utility_ci | false_promotion_control_rate | shuffled_false_steer_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| charge | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.997 | 1.206 | [1.166, 1.241] | 0.000 | 0.020 |
| charge | ridge | ridge_C3 | 0.902 | 1.048 | [0.886, 1.167] | 0.000 | 0.015 |
| charge | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.545 | 0.678 | [0.439, 0.949] | 0.000 | 0.029 |
| charge | traditional_support_scorecard | traditional_support_scorecard | 0.643 | 0.637 | [0.463, 0.838] | 0.000 | 0.000 |
| charge | cnn_1d | cnn_1d_width8 | 0.138 | 0.209 | [0.126, 0.328] | 0.000 | 0.113 |
| charge | mlp | mlp_hidden16 | 0.106 | -0.333 | [-0.598, -0.063] | 0.262 | 0.305 |
| pid | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.997 | 1.206 | [1.166, 1.241] | 0.000 | 0.020 |
| pid | ridge | ridge_C3 | 0.902 | 1.048 | [0.886, 1.167] | 0.000 | 0.015 |
| pid | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.545 | 0.678 | [0.439, 0.949] | 0.000 | 0.029 |
| pid | traditional_support_scorecard | traditional_support_scorecard | 0.643 | 0.637 | [0.463, 0.838] | 0.000 | 0.000 |
| pid | cnn_1d | cnn_1d_width8 | 0.138 | 0.209 | [0.126, 0.328] | 0.000 | 0.113 |
| pid | mlp | mlp_hidden16 | 0.106 | -0.333 | [-0.598, -0.063] | 0.262 | 0.307 |
| pileup | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.08 | 0.976 | 1.090 | [1.008, 1.158] | 0.000 | 0.009 |
| pileup | ridge | ridge_C3 | 0.905 | 1.046 | [0.892, 1.152] | 0.000 | 0.014 |
| pileup | traditional_support_scorecard | traditional_support_scorecard | 0.668 | 0.662 | [0.499, 0.861] | 0.000 | 0.000 |
| pileup | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.463 | 0.570 | [0.358, 0.796] | 0.000 | 0.025 |
| pileup | cnn_1d | cnn_1d_width8 | 0.119 | 0.188 | [0.110, 0.291] | 0.000 | 0.116 |
| pileup | mlp | mlp_hidden16 | 0.123 | -0.313 | [-0.581, 0.004] | 0.269 | 0.302 |
| timing | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.966 | 1.053 | [0.962, 1.130] | 0.000 | 0.006 |
| timing | ridge | ridge_C3 | 0.800 | 0.941 | [0.753, 1.167] | 0.000 | 0.011 |
| timing | traditional_support_scorecard | traditional_support_scorecard | 0.933 | 0.929 | [0.785, 0.997] | 0.000 | 0.000 |
| timing | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.424 | 0.551 | [0.391, 0.800] | 0.000 | 0.027 |
| timing | cnn_1d | cnn_1d_width8 | 0.149 | 0.245 | [0.149, 0.380] | 0.000 | 0.087 |
| timing | mlp | mlp_hidden32 | 0.036 | -0.633 | [-0.888, -0.338] | 0.354 | 0.382 |

## 5. Shuffled-Atom Controls

| consumer | method | method_variant | shuffled_false_steer_rate | shuffled_ci | n_shuffled_negative |
| --- | --- | --- | --- | --- | --- |
| charge | traditional_support_scorecard | traditional_support_scorecard | 0.000 | [0.000, 0.000] | 848 |
| charge | ridge | ridge_C3 | 0.015 | [0.009, 0.021] | 848 |
| charge | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.020 | [0.013, 0.026] | 848 |
| charge | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.029 | [0.020, 0.041] | 848 |
| charge | cnn_1d | cnn_1d_width8 | 0.113 | [0.091, 0.133] | 848 |
| charge | mlp | mlp_hidden16 | 0.305 | [0.210, 0.393] | 848 |
| pid | traditional_support_scorecard | traditional_support_scorecard | 0.000 | [0.000, 0.000] | 851 |
| pid | ridge | ridge_C3 | 0.015 | [0.009, 0.021] | 851 |
| pid | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.020 | [0.013, 0.027] | 851 |
| pid | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.029 | [0.020, 0.039] | 851 |
| pid | cnn_1d | cnn_1d_width8 | 0.113 | [0.095, 0.134] | 851 |
| pid | mlp | mlp_hidden16 | 0.307 | [0.225, 0.400] | 851 |
| pileup | traditional_support_scorecard | traditional_support_scorecard | 0.000 | [0.000, 0.000] | 848 |
| pileup | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.08 | 0.009 | [0.005, 0.016] | 848 |
| pileup | ridge | ridge_C3 | 0.014 | [0.009, 0.022] | 848 |
| pileup | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.025 | [0.016, 0.035] | 848 |
| pileup | cnn_1d | cnn_1d_width8 | 0.116 | [0.099, 0.135] | 848 |
| pileup | mlp | mlp_hidden16 | 0.302 | [0.211, 0.398] | 848 |
| timing | traditional_support_scorecard | traditional_support_scorecard | 0.000 | [0.000, 0.000] | 851 |
| timing | gradient_boosted_trees | gradient_boosted_trees_learning_rate0.03 | 0.006 | [0.001, 0.011] | 851 |
| timing | ridge | ridge_C3 | 0.011 | [0.006, 0.016] | 851 |
| timing | support_gated_cnn_new | support_gated_cnn_new_width8 | 0.027 | [0.019, 0.035] | 851 |
| timing | cnn_1d | cnn_1d_width8 | 0.087 | [0.072, 0.103] | 851 |
| timing | mlp | mlp_hidden32 | 0.382 | [0.274, 0.471] | 851 |

## 6. Endpoint Systematics

Endpoint summaries are weighted over atom/run/stave cells and uncertainty is estimated by resampling complete runs.  The proxies are deliberately conservative: timing uses wide inter-stave timing spans, pile-up uses delayed secondary and late-area excess, charge uses within-cell log-amplitude spread, and PID uses q-template residual magnitude.

| consumer | n_cells | n_positive | metric | promoted_metric_mean | promoted_metric_ci_low | promoted_metric_ci_high | control_metric_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| timing | 1003 | 17 | timing_tail_rate | 0.092 | 0.064 | 0.154 | 0.009 |
| pileup | 1003 | 24 | pileup_excess_proxy | 1.171 | 1.158 | 1.199 | 0.938 |
| charge | 1003 | 25 | charge_res68_proxy | 0.158 | 0.152 | 0.163 | 0.307 |
| pid | 1003 | 25 | qshape_abs_mean | 0.183 | 0.173 | 0.215 | 0.185 |

## 7. Leakage And Caveats

| consumer | check | value | pass |
| --- | --- | --- | --- |
| timing | leave_one_run_out_train_test_overlap | 0 | True |
| timing | scalar_feature_identifier_label_exclusion |  | True |
| timing | nominal_control_present_for_false_promotion | 130 | True |
| timing | all_best_predictions_finite | 1 | True |
| pileup | leave_one_run_out_train_test_overlap | 0 | True |
| pileup | scalar_feature_identifier_label_exclusion |  | True |
| pileup | nominal_control_present_for_false_promotion | 130 | True |
| pileup | all_best_predictions_finite | 1 | True |
| charge | leave_one_run_out_train_test_overlap | 0 | True |
| charge | scalar_feature_identifier_label_exclusion |  | True |
| charge | nominal_control_present_for_false_promotion | 130 | True |
| charge | all_best_predictions_finite | 1 | True |
| pid | leave_one_run_out_train_test_overlap | 0 | True |
| pid | scalar_feature_identifier_label_exclusion |  | True |
| pid | nominal_control_present_for_false_promotion | 130 | True |
| pid | all_best_predictions_finite | 1 | True |

- The dry run is a consumer-level false-promotion bound, not a claim that any atom is a physical causal variable.
- The strongest protection is the frozen P13b gate; ML methods are rejected if they buy utility by increasing nominal-control or shuffled-atom false steering.
- Only one atom source is externally steered at a time.  Correlated multi-consumer steering remains outside this ticket.
- The positive label is sparse because the frozen gate is intentionally conservative; AP and utility are therefore more informative than accuracy.

## 8. Result

The named winner is **gradient_boosted_trees** (`gradient_boosted_trees_learning_rate0.03`) on **pid**.  The result does not append a new ticket; P13c is a closure dry run of the P13b promotion policy.

## 9. Reproducibility

Run command:

```bash
/home/billy/anaconda3/bin/python scripts/p13c_1781164722_1110_69a0219b_rare_atom_external_steering.py --config configs/p13c_1781164722_1110_69a0219b_rare_atom_external_steering.json
```

Artifacts include `result.json`, `REPORT.md`, `manifest.json`, `consumer_method_summary.csv`, `consumer_winners.csv`, `shuffled_atom_controls.csv`, `endpoint_systematics_by_consumer.csv`, `leakage_checks.csv`, raw reproduction tables, and per-consumer benchmark subdirectories.


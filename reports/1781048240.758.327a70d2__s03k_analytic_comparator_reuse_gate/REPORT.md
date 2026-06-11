# S03k: analytic comparator reuse gate for waveform consumers

- **Ticket:** `1781048240.758.327a70d2`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Primary data:** raw B-stack ROOT under `data/root/root`
- **Primary split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65

## Abstract

This study turns the S03 analytic timewalk correction into an explicit reuse gate for downstream waveform consumers. The gate asks whether each claimed waveform-latent or neural timing consumer beats the exact-fold S03 analytic comparator on the same held-out run and pairwise residual metric, rather than only beating weaker CFD20 or ridge-on-CFD baselines. The primary seven-run panel uses the frozen P03f timing consumer artifacts because they contain the required ridge, gradient-boosted tree, MLP, 1D-CNN, and feature-gated new architecture families on the same Sample-II folds.

The S03 comparator is `analytic_timewalk` with pooled sigma68 `1.551` ns. The winner is **hgb_waveform_amp_shape_stave** (gradient_boosted_trees) with sigma68 **1.107** ns, 95% CI **[1.075, 1.159]**, and ML-minus-S03 delta **-0.444** ns with paired bootstrap CI **[-0.842, -0.241]**.

## Raw-ROOT reproduction gate

The selected-pulse count was recomputed directly from the `HRDv` branch in every configured B-stack raw ROOT file. Each event is reshaped to `(8,18)`, samples 0-3 define the per-channel baseline, B2/B4/B6/B8 use even channels 0/2/4/6, and a selected pulse is one with baseline-subtracted maximum amplitude above 1000 ADC.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total_selected_pulses | 640737 | 640737 | 0 | 0 | True |
| sample_ii_analysis_selected_pulses | 125096 | 125096 | 0 | 0 | True |
| sample_ii_analysis_B2 | 88213 | 88213 | 0 | 0 | True |
| sample_ii_analysis_B4 | 21229 | 21229 | 0 | 0 | True |
| sample_ii_analysis_B6 | 11148 | 11148 | 0 | 0 | True |
| sample_ii_analysis_B8 | 4506 | 4506 | 0 | 0 | True |

The exact zero-delta match is used only as an entry condition; all model claims below still have to pass the S03 comparator gate.

## Estimand and equations

For event `e`, stave `i`, timing method `m`, and downstream coordinate `z_i`, the velocity-corrected time is

`t'_{i,e}(m) = t_{i,e}(m) - z_i / v`, with `v^{-1}=0.078 ns cm^{-1}`.

The same-particle pair residual for staves `a,b` is

`r_{ab,e}(m) = t'_{a,e}(m) - t'_{b,e}(m)`.

The robust width is

`sigma68(m) = (Q_84({r_ab,e}) - Q_16({r_ab,e})) / 2`.

For a consumer model `c`, the S03 reuse margin is

`Delta_c = sigma68(c) - sigma68(S03 analytic_timewalk)`.

A strict gate pass requires `Delta_c < 0` and an event-paired run-block bootstrap CI with upper endpoint below zero. The primary bootstrap resamples held-out runs and, inside each sampled run, event-paired residual blocks, preserving the run split and pair correlations.

## Frozen S03 comparator registry

| source | method | scope | value | ci | n_pair_residuals | role |
| --- | --- | --- | --- | --- | --- | --- |
| P03f exact-fold Sample-II | analytic_timewalk | runs 58,59,60,61,62,63,65 | 1.5511 | [1.364, 1.936] | 11460 | primary S03k comparator |
| S03f traditional registry | hgb_timewalk | runs 58,59,60,61,62,63,65 | 1.3942 | [1.256, 1.658] | 11460 | traditional registry context |
| S03f traditional registry | hierarchical_signed_shrinkage | runs 58,59,60,61,62,63,65 | 1.5681 | [1.341, 1.922] | 11460 | traditional registry context |
| S03f traditional registry | phys_signed_inverse_amp | runs 58,59,60,61,62,63,65 | 1.6044 | [1.385, 1.948] | 11460 | traditional registry context |
| S03f traditional registry | s03a_amp_only | runs 58,59,60,61,62,63,65 | 1.5511 | [1.366, 1.899] | 11460 | traditional registry context |
| S03f traditional registry | s03b_monotone_binned | runs 58,59,60,61,62,63,65 | 1.6451 | [1.322, 1.945] | 11460 | traditional registry context |
| S03f traditional registry | template_phase_base | runs 58,59,60,61,62,63,65 | 2.7414 | [2.684, 2.992] | 11460 | traditional registry context |
| S19a run-65 architecture screen | analytic_timewalk | run 65 | 1.4946 | [1.299, 1.666] | 198 | single-run cross-check comparator |
| S19a run-65 architecture screen | s02_ridge_cfd20 | run 65 | 1.7778 | [1.493, 2.070] | 198 | single-run cross-check comparator |
| S19a run-65 architecture screen | template_phase | run 65 | 2.8892 | [2.639, 3.277] | 198 | single-run cross-check comparator |

The primary comparator is the P03f exact-fold `analytic_timewalk` row because it is on the same folds and target residuals as the waveform consumers. S03f registry rows provide broader traditional context: HGB timewalk is a useful traditional/ML hybrid reference, but S03k's reuse gate is anchored to the analytic S03 row requested by the ticket.

## Primary consumer gate

| method | model_family | sigma68_ns | ci | full_rms_ns | delta_vs_traditional_ns | delta_ci | pass_s03_gate_ci |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hgb_waveform_amp_shape_stave | gradient_boosted_trees | 1.1074 | [1.075, 1.159] | 2.1317 | -0.4437 | [-0.842, -0.241] | True |
| mlp_waveform_amp_shape_stave | mlp | 1.1621 | [1.106, 1.235] | 2.4585 | -0.3890 | [-0.818, -0.167] | True |
| ridge_waveform_stave_onehot | ridge | 1.2444 | [1.173, 1.322] | 2.4073 | -0.3067 | [-0.739, -0.089] | True |
| feature_gated_waveform_amp_shape_stave | new_feature_gated_architecture | 1.2535 | [1.213, 1.308] | 2.4351 | -0.2976 | [-0.671, -0.095] | True |
| cnn1d_waveform_amp_shape_stave | 1d_cnn | 1.2639 | [1.212, 1.343] | 2.4360 | -0.2872 | [-0.686, -0.086] | True |
| analytic_timewalk | traditional_s03_analytic_timewalk | 1.5511 | [1.364, 1.936] | 2.6670 | 0.0000 | [0.000, 0.000] | False |

The strongest traditional method in this gate is the exact-fold S03 analytic timewalk comparator, not the older template-phase or CFD baselines. The best required-family ML/NN methods all use only same-pulse waveform, amplitude/shape summaries, and stave indicators; run id, event id, event order, other-stave timings, and held-out residuals are excluded by the source P03f feature audit.

The feature-gated row is the new architecture. It has separate waveform and auxiliary-feature branches, then learns an auxiliary-conditioned gate before predicting the residual correction. This is sensible for 18-sample pulses because it allows a small model to decide when local waveform evidence should be trusted relative to coarse amplitude/stave context.

## Per-run behavior

| heldout_run | 1d_cnn | gradient_boosted_trees | mlp | new_feature_gated_architecture | ridge | traditional_s03_analytic_timewalk |
| --- | --- | --- | --- | --- | --- | --- |
| 58 | 1.1911 | 1.0375 | 1.0278 | 1.1894 | 1.0326 | 1.1875 |
| 59 | 1.3374 | 1.0669 | 1.1419 | 1.3139 | 1.3067 | 1.4587 |
| 60 | 1.1909 | 1.0980 | 1.1720 | 1.2431 | 1.2243 | 1.3437 |
| 61 | 1.2647 | 1.0894 | 1.1161 | 1.2753 | 1.2367 | 2.1300 |
| 62 | 1.3101 | 1.1568 | 1.1557 | 1.2043 | 1.2928 | 1.4690 |
| 63 | 1.3404 | 1.1737 | 1.3150 | 1.2752 | 1.3471 | 1.3913 |
| 65 | 1.3523 | 1.2233 | 1.2832 | 1.4920 | 1.3912 | 1.4946 |

Run 61 is the decisive stress case: S03 analytic broadens to about 2.13 ns, while the stave-aware waveform consumers remain near 1.09-1.28 ns. Runs 58 and 65 are sparse, so their per-run intervals are wider and are interpreted as support checks rather than standalone discoveries.

## Cross-check architecture panels

The S19a timing architecture screen is a run-65 cross-check where models correct residuals left by the analytic comparator. It is not the primary S03k estimate because it has one held-out run, but it confirms that the requested architecture families were exercised on timing residuals.

| method | value | ci | n | note |
| --- | --- | --- | --- | --- |
| mlp | 1.1761 | [1.024, 1.386] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| gru | 1.2247 | [1.014, 1.462] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| gradient_boosted_trees | 1.2558 | [1.012, 1.438] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| resnet | 1.2989 | [1.087, 1.497] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| tcn | 1.3413 | [1.054, 1.560] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| cnn | 1.3626 | [1.030, 1.582] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| attention | 1.4349 | [1.079, 1.632] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| ridge | 1.4428 | [1.196, 1.635] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |
| analytic_timewalk | 1.4946 | [1.299, 1.666] | 198 | single held-out run cross-check; ML corrects residuals left by analytic_timewalk |

The T07 morphology panel is a separate consumer-style pulse-shape benchmark with a traditional Fisher/Gatti baseline and the same required ML/NN families plus residual-squeeze CNN. It is included as scope evidence, but it is not used to decide the S03 timing gate because its metric is ROC AUC on a morphology proxy.

| method | value | ci | n | note |
| --- | --- | --- | --- | --- |
| ML_gradient_boosted_trees | 1.0000 | [1.0000, 1.0000] | 9745 | consumer-style morphology task; not on S03 timing scale |
| ML_mlp | 0.9996 | [0.9993, 0.9998] | 9745 | consumer-style morphology task; not on S03 timing scale |
| traditional_fisher_gatti_all_features | 0.9950 | [0.9924, 0.9972] | 9745 | consumer-style morphology task; not on S03 timing scale |
| ML_ridge_classifier | 0.9935 | [0.9905, 0.9960] | 9745 | consumer-style morphology task; not on S03 timing scale |
| NN_residual_squeeze_cnn_new | 0.9844 | [0.9784, 0.9895] | 9745 | consumer-style morphology task; not on S03 timing scale |
| NN_1d_cnn | 0.9741 | [0.9662, 0.9807] | 9745 | consumer-style morphology task; not on S03 timing scale |

## Leakage, sentinels, and systematics

| check | value | pass | detail |
| --- | --- | --- | --- |
| raw_root_reproduction_all_rows_pass | 1.0000 | True | all registered selected-pulse count gates match exactly |
| primary_panel_contains_required_families | 1.0000 | True | traditional S03, ridge, GBT, MLP, 1D-CNN, and feature-gated new architecture are present |
| split_unit_is_run | 7.0000 | True | primary P03f panel leaves out each Sample-II analysis run |
| s03_gate_ci_pass_count | 5.0000 | True | number of required-family methods whose ML-minus-S03 delta CI is wholly below zero |
| shuffled_target_controls_near_s03 | 1.5669 | True | median shuffled-target control should sit near analytic comparator rather than the ML winner |
| best_shuffled_control_beats_s03_by_less_than_0p05_ns | 0.0067 | True | small negative shuffled deltas are treated as finite-sample stability caveats |

Target-shuffle controls cluster near the S03 analytic comparator instead of the best ML row, which is the expected behavior. A few shuffled rows can sit a few picoseconds below S03 because the bootstrap is finite and the analytic row is not a random-target optimum; those rows are treated as stability caveats and not as positive evidence.

Main caveats:

- The pairwise timing target is an internal same-particle consistency metric, not an external clock truth.
- Stave-aware models can exploit stable geometry or channel-response structure. That is useful for timing but means a model beating S03 is not automatically a portable physics correction.
- The primary result is a reuse gate over frozen artifacts, not new hyperparameter exploration. This is intentional: the question is whether existing consumer claims survive the stronger comparator.
- Bootstrap CIs cover held-out run/event variability better than model-selection uncertainty; architecture ranking should be frozen before production use.
- Consumer metrics such as charge, pile-up, PID, and energy are represented here by available timing and morphology consumer artifacts. They still need direct downstream retesting before any calibration-wide substitution.

## Verdict

`result.json` names **hgb_waveform_amp_shape_stave** as the S03k winner. It passes the strict S03 gate because the paired bootstrap upper endpoint for ML-minus-S03 is below zero. The ridge, MLP, 1D-CNN, and feature-gated rows also beat S03 by point estimate; ridge, MLP, feature-gated, and the amp/shape/stave 1D-CNN pass the strict CI gate in the primary P03f panel. Plain waveform-only variants do not consistently clear the gate, so S03 remains the required comparator for future waveform-consumer claims.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03k_1781048240_758_327a70d2_analytic_comparator_reuse_gate.py
```

Artifacts include `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `run_counts.csv`, `s03_comparator_registry.csv`, `primary_consumer_gate.csv`, `per_run_gate_summary.csv`, `architecture_cross_checks.csv`, `leakage_checks.csv`, `input_sha256.csv`, and `manifest.json`.

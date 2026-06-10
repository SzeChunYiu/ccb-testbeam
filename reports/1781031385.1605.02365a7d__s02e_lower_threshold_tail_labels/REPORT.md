# S02e: lower-threshold Sample-II LORO tail labels

- **Ticket:** `1781031385.1605.02365a7d`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out over `[58, 59, 60, 61, 62, 63, 65]`
- **Tail label:** downstream all-hit event with `D_t > 3.0 ns`
- **Git commit at run time:** `977989610fe120acfbf08633f164b1ee31b0fe79`

## 1. Question

The original S02/S02b timing-tail labels used very sparse extreme tails.  This ticket lowers the threshold to a preregistered `3 ns` in Sample II to increase statistical support, then asks whether a fixed S16f-style pre-trigger veto remains stable when scored strictly on held-out runs.  The scientific target is not a new timing calibration; it is a tail-risk screen whose labels are generated from raw ROOT waveforms and evaluated with run-block uncertainty.

## 2. Raw-ROOT Reproduction Gate

The selected-pulse gate is rebuilt directly from the `HRDv` branch before any labels or ML fits are made.  The reproduced count is the same anchor used by S00/S02/S19.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

All rows pass with zero tolerance.  The input hash table (`input_sha256.csv`) records `33` B-stack ROOT files.

## 3. Methods

For every Sample-II analysis fold, the held-out run `r` is excluded before building the template-phase timing reference.  For each downstream stave `i` in event `e`,

`t'_(i,e) = t_template(i,e) - x_i / v`,

where `x_i` is the downstream stave position and `v^-1 = 0.078 ns/cm`.  The lower-threshold event label is

`y_e = 1[max_i t'_(i,e) - min_i t'_(i,e) > 3.0 ns]`.

The traditional comparator is a fixed S16f-style scorecard built from pre-trigger range, pre-trigger absolute excursion, adaptive-pedestal lowering, tail area, and secondary-peak fraction.  Its veto threshold is chosen on non-held-out runs to retain `90%` of training clean events, then applied unchanged to the held-out run.

The ML/NN competitors are ridge-logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a small dilated temporal CNN (`tcn`) as the new architecture.  All receive only same-event waveform-shape and S16f morphology summaries.  No model receives run number, event id, event order, the timing span, or the label-defining corrected times.

Primary ranking metric: held-out average precision for `D_t > 3 ns`.  Operational veto metric: tail rejection at the train-calibrated 90% clean acceptance threshold.  Confidence intervals are non-parametric bootstraps over held-out run blocks.

## 4. Tail-Label Support

| heldout_run | n_heldout_events | n_heldout_tail | tail_fraction |
| --- | --- | --- | --- |
| 58.0 | 73.0 | 70.0 | 0.959 |
| 59.0 | 763.0 | 726.0 | 0.952 |
| 60.0 | 808.0 | 775.0 | 0.959 |
| 61.0 | 933.0 | 760.0 | 0.815 |
| 62.0 | 807.0 | 784.0 | 0.971 |
| 63.0 | 370.0 | 361.0 | 0.976 |
| 65.0 | 66.0 | 61.0 | 0.924 |

The lower threshold increases support to `3537` positive held-out events across `3820` all-hit downstream events.  The run-to-run variation is therefore part of the interval, not averaged away as row-level IID noise.

## 5. Head-to-Head Benchmark

| model | n_events | n_tail | average_precision_ci | roc_auc_ci | tail_rejection_at_90_clean_ci | clean_acceptance_ci |
| --- | --- | --- | --- | --- | --- | --- |
| ridge | 3820 | 3537 | 0.997 [0.992, 0.999] | 0.964 [0.951, 0.971] | 0.945 [0.899, 0.974] | 0.869 [0.804, 0.902] |
| tcn | 3820 | 3537 | 0.992 [0.985, 0.997] | 0.916 [0.846, 0.938] | 0.807 [0.722, 0.892] | 0.898 [0.731, 0.957] |
| cnn | 3820 | 3537 | 0.991 [0.982, 0.996] | 0.905 [0.836, 0.921] | 0.777 [0.697, 0.876] | 0.883 [0.723, 0.944] |
| gradient_boosted_trees | 3820 | 3537 | 0.990 [0.980, 0.999] | 0.902 [0.880, 0.965] | 1.000 [1.000, 1.000] | 0.014 [0.000, 0.053] |
| traditional_s16f_scorecard | 3820 | 3537 | 0.956 [0.920, 0.982] | 0.590 [0.549, 0.635] | 0.348 [0.325, 0.360] | 0.894 [0.823, 0.923] |
| mlp | 3820 | 3537 | 0.926 [0.881, 0.983] | 0.445 [0.384, 0.697] | 0.303 [0.239, 0.371] | 0.820 [0.752, 0.994] |

Winner by the preregistered point estimate is **`ridge`** with average precision `0.997` [0.992, 0.999].  The fixed traditional scorecard has average precision `0.956` [0.920, 0.982] and tail rejection `0.348` [0.325, 0.360] at the train-calibrated clean-acceptance operating point.

## 6. Leakage and Stability Checks

| check | value | pass |
| --- | --- | --- |
| loro_train_heldout_run_overlap_zero | 0 | yes |
| feature_names_exclude_identifiers_and_labels |  | yes |
| tail_label_defined_only_from_heldout_fold_template_timing | template_phase D_t > 3 ns | yes |
| all_models_have_oof_scores | 1 | yes |
| rounded_waveform_hash_cross_run_duplicates_reported | 0 | yes |

The decisive guard is the run split: template construction, score thresholds, and all model fits are repeated inside each leave-one-run-out fold.  Feature names are audited against identifier and label columns, and all reported scores are out-of-fold predictions.

## 7. Systematics and Caveats

- The `D_t > 3 ns` label is a timing-span proxy, not an external truth label.  It can include legitimate detector-resolution tails, residual timewalk, and pile-up-like waveform structure.
- Template-phase timing is rebuilt per fold, but the template family itself is fixed.  A different traditional timing definition would move some events across the 3 ns boundary.
- The S16f scorecard is intentionally transparent and may be conservative: it mixes pre-trigger excursions with post-trigger morphology because the raw HRD window is only 18 samples.
- Run-block bootstrap intervals cover finite run-to-run stability; they do not fully cover hyperparameter search or alternate label definitions.
- The CNN and TCN are small laptop-safe architectures.  A larger neural model could change the ordering, but that would be a separate capacity study rather than this stability check.

## 8. Verdict

The lower-threshold label set is reproducible from raw ROOT and materially less sparse than the older extreme-tail definition.  Under leave-one-run-out scoring, **`ridge`** is the point-estimate winner for identifying `D_t > 3 ns` tails.  The result supports using the ML score as a diagnostic ranker, while the fixed S16f scorecard remains the auditable veto baseline because its clean-acceptance operating point is explicit and fold-local.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels.py --config configs/s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels.yaml
```

Runtime in this execution was `91.78` s.  Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `heldout_fold_metrics.csv`, `run_block_bootstrap_summary.csv`, `oof_tail_predictions.csv`, and `leakage_checks.csv`.

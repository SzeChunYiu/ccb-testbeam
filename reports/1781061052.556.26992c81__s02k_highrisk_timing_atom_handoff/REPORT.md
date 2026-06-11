# S02k: high-risk timing atom handoff table

- **Ticket:** `1781061052.556.26992c81`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Primary target:** downstream all-hit `D_t > 3.0 ns`
- **Git commit at run time:** `9d994c7ef757af01e757f347b386fde05aac1fa6`

## 1. Question

S02e identified a high-support timing-risk population, but the downstream consumers need atom labels rather than a single opaque risk flag. This study asks which high-risk candidates are pulse-shape atoms worth handing to S03/S04/S10 consumers and which are charge-pair or topology artifacts that should remain diagnostic only.

## 2. Raw-ROOT Reproduction Gate

The first operation is an independent scan of `HRDv` in the raw ROOT files. Pulses are selected from B2/B4/B6/B8 with median baseline samples 0-3 and amplitude `A > 1000 ADC`.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The zero-tolerance count gate reproduces the S00 anchor before any atom labels, timing spans, or classifiers are fit.

## 3. Methods and Estimands

For event `e` and downstream stave `i`, the fold-local template time is geometry corrected as

`t'_(i,e) = t_template(i,e) - x_i / v`,

with `v^-1 = 0.078 ns/cm`. The timing-risk label is

`y_e = 1[max_i t'_(i,e) - min_i t'_(i,e) > 3.0 ns]`.

The traditional handoff method is a frozen S16f-style scorecard using q-template-like residuals, amplitude/log-amplitude imbalance, adaptive lowering, pre-trigger excursion, width, late fraction, secondary peak, stave identity, and downstream topology summaries. Its threshold is selected on non-held-out runs to retain `90%` of clean training events.

The ML/NN benchmark uses ridge logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a dilated temporal CNN (`tcn`) as the new architecture. Classifiers are trained strictly leave-one-run-out. They do not receive event id, event order, run id, the timing span, or corrected times. Sentinels score charge-only, topology-only, run-only, q-template-only, and shuffled-risk controls.

Atom classes are descriptive handoff strata: `delayed_peak_shape`, `broad_late_shape`, `pretrigger_baseline_shape`, `q_template_mismatch`, `low_charge_pair_artifact`, and `common_shape`. Reported confidence intervals are non-parametric run-block bootstraps, and ML-minus-traditional deltas are paired by event inside each sampled run block.

## 4. Model Benchmark

| model | n_events | n_tail | average_precision_ci | roc_auc_ci | tail_rejection_at_90_clean_ci | clean_acceptance_ci |
| --- | --- | --- | --- | --- | --- | --- |
| ridge | 3820 | 3537 | 0.997 [0.993, 0.999] | 0.964 [0.953, 0.973] | 0.945 [0.908, 0.973] | 0.869 [0.803, 0.905] |
| gradient_boosted_trees | 3820 | 3537 | 0.990 [0.978, 0.999] | 0.902 [0.879, 0.963] | 1.000 [1.000, 1.000] | 0.014 [0.000, 0.059] |
| cnn | 3820 | 3537 | 0.990 [0.979, 0.997] | 0.903 [0.862, 0.937] | 0.792 [0.635, 0.929] | 0.901 [0.773, 0.955] |
| tcn | 3820 | 3537 | 0.990 [0.978, 0.994] | 0.902 [0.875, 0.908] | 0.784 [0.636, 0.906] | 0.883 [0.738, 0.941] |
| traditional_s16f_scorecard | 3820 | 3537 | 0.956 [0.921, 0.982] | 0.590 [0.556, 0.635] | 0.348 [0.329, 0.363] | 0.894 [0.826, 0.921] |
| mlp | 3820 | 3537 | 0.940 [0.900, 0.988] | 0.500 [0.442, 0.732] | 0.378 [0.292, 0.477] | 0.781 [0.693, 1.000] |

Winner by held-out average precision is **`ridge`** with AP `0.997` [0.993, 0.999].

## 5. Sentinel Controls

| sentinel | average_precision_ci | roc_auc_ci |
| --- | --- | --- |
| q_template_only_sentinel | 0.967 [0.946, 0.986] | 0.670 [0.646, 0.706] |
| shuffled_risk_sentinel | 0.926 [0.855, 0.968] | 0.500 [0.450, 0.513] |
| topology_only_sentinel | 0.918 [0.851, 0.962] | 0.451 [0.405, 0.459] |
| charge_only_sentinel | 0.916 [0.866, 0.956] | 0.440 [0.302, 0.480] |
| run_only_sentinel | 0.884 [0.832, 0.968] | 0.292 [0.272, 0.525] |

The sentinels are not production candidates. They bound how much of the apparent signal is recoverable from nuisance-only summaries before waveform-shape models are credited.

## 6. Atom Handoff Ledger

| atom_class | n_events | prevalence | tail_precision | tail_enrichment | tail_rate_after_exclusion | kept_pair_fraction | max_pair_share_concentration | downstream_sigma68_delta_ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pretrigger_baseline_shape | 193 | 0.051 | 1.000 | 1.080 | 0.922 | 0.949 | 0.275 | 0.035 |
| q_template_mismatch | 24 | 0.006 | 1.000 | 1.080 | 0.925 | 0.994 | 0.333 | 0.000 |
| delayed_peak_shape | 382 | 0.100 | 0.950 | 1.026 | 0.923 | 0.900 | 0.270 | 0.005 |
| broad_late_shape | 542 | 0.142 | 0.935 | 1.010 | 0.924 | 0.858 | 0.284 | 0.033 |
| low_charge_pair_artifact | 245 | 0.064 | 0.918 | 0.992 | 0.926 | 0.936 | 0.229 | -0.000 |
| common_shape | 2434 | 0.637 | 0.914 | 0.987 | 0.947 | 0.363 | 0.240 | -0.707 |

`tail_rate_after_exclusion` and `downstream_sigma68_delta_ns` are recomputed after dropping the atom class. Negative sigma68 deltas mean the kept sample narrows after that atom is excluded.

## 7. Traditional vs ML Handoff Operating Point

| method | flagged_events | kept_pair_fraction | tail_precision | tail_rejection | tail_rate_after_exclusion | downstream_sigma68_delta_ns | max_pair_share_concentration |
| --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_s16f_scorecard | 1261 | 0.670 | 0.976 | 0.348 | 0.901 | 0.258 | 0.235 |
| ridge | 3381 | 0.115 | 0.989 | 0.945 | 0.440 | -0.072 | 0.229 |

Paired run-block bootstrap ML-minus-traditional deltas:

| metric | ml_minus_traditional | ci_low | ci_high |
| --- | --- | --- | --- |
| kept_pair_fraction | -0.558 | -0.616 | -0.483 |
| tail_precision | 0.013 | 0.005 | 0.022 |
| tail_rejection | 0.598 | 0.555 | 0.639 |
| tail_rate_after_exclusion | -0.448 | -0.493 | -0.393 |
| downstream_sigma68_delta_ns | -0.272 | -0.463 | -0.060 |
| max_pair_share_concentration | -0.012 | -0.059 | 0.029 |

## 8. Leakage Checks

| check | value | pass |
| --- | --- | --- |
| loro_train_heldout_run_overlap_zero | 0 | yes |
| feature_names_exclude_identifiers_and_labels |  | yes |
| tail_label_defined_only_from_heldout_fold_template_timing | template_phase D_t > 3 ns | yes |
| all_models_have_oof_scores | 1 | yes |
| rounded_waveform_hash_cross_run_duplicates_reported | 0 | yes |

## 9. Systematics and Caveats

- The `D_t > 3.0 ns` target is an internal timing-span label, not external truth. It is a risk label for triage, not proof of pile-up or bad detector response.
- The q-template residual in the atom table is a fold-independent descriptive proxy built from normalized downstream shapes; the classifier benchmark itself is split by run.
- The all-hit Sample-II support is only `3820` events, so run-block intervals dominate several atom classes.
- Charge-pair artifacts are identified from amplitude imbalance and should not be passed as pulse-shape vetoes without the proposed external control validation.
- CNN and TCN capacities are intentionally laptop-safe. Larger architectures are possible but would be a separate capacity study.

## 10. Verdict

The raw-count gate passes exactly and the best held-out classifier is `ridge`. The handoff table supports using delayed-peak, broad-late, pre-trigger/baseline, and q-template-mismatch classes as provisional pulse-shape atoms, while low-charge-pair rows should be treated as artifacts. The result names `ridge` as the benchmark winner in `result.json` and queues at most one follow-up: external validation of the frozen S02k atom table.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02k_1781061052_556_26992c81_highrisk_timing_atom_handoff.py --config configs/s02k_1781061052_556_26992c81_highrisk_timing_atom_handoff.yaml
```

Runtime in this execution was `786.89` s.

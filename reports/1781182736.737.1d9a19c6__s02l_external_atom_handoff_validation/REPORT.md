# S02l: External Atom Handoff Validation

- **Ticket:** `1781182736.737.1d9a19c6`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Primary target:** downstream all-hit `D_t > 3.0 ns`
- **Git commit at run time:** `cefa62c5d813c634f47ad70e5aca608dcd8f24b9`

## 1. Question

S02k froze a handoff table that labels high-risk downstream timing events as delayed-peak, broad-late, pre-trigger/baseline, q-template-mismatch, or low-charge-pair artifacts. S02l asks whether those atom classes survive two external controls before downstream consumers use them: visible forced/random acquisition records and independent duplicate-readout charge asymmetry.

## 2. Raw-ROOT Reproduction Gate

The first operation is a direct scan of the raw `HRDv` ROOT branch. The selected-pulse gate is B2/B4/B6/B8, median baseline over samples 0-3, and amplitude `A > 1000 ADC`.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The gate passes with the ticket's raw number reproduced before any machine-learning fit or atom-control calculation.

## 3. Statistical Methods

For event `e` and downstream stave `i`, the template pickoff is geometry corrected as

`t'_(i,e) = t_template(i,e) - x_i / v`,

where `v^-1 = 0.078 ns/cm`. The event label is

`y_e = 1[max_i t'_(i,e) - min_i t'_(i,e) > 3.0 ns]`.

The traditional method is the frozen S16f/S02k morphology scorecard calibrated on the training runs to retain `90%` of clean events. The ML/NN panel is ridge logistic regression, histogram gradient-boosted trees, one-hidden-layer MLP, 1D-CNN, and a dilated temporal CNN (`tcn`) as the new architecture. Every score is out-of-fold by complete run. Confidence intervals are non-parametric run-block bootstraps.

The duplicate-readout control computes, for each downstream stave,

`a_i = (Q_even,i - Q_odd,i) / max(Q_even,i + Q_odd,i, 1)`,

where `Q_odd` is the positive lobe of the inverted duplicate-readout channel. A reusable pulse-shape atom should not be explained mainly by extreme duplicate-readout asymmetry; a low-charge-pair artifact may be.

## 4. Model Benchmark

| model | n_events | n_tail | average_precision_ci | roc_auc_ci | tail_rejection_at_90_clean_ci | clean_acceptance_ci |
| --- | --- | --- | --- | --- | --- | --- |
| ridge | 3820 | 3537 | 0.997 [0.993, 0.999] | 0.964 [0.954, 0.973] | 0.945 [0.910, 0.974] | 0.869 [0.800, 0.899] |
| gradient_boosted_trees | 3820 | 3537 | 0.990 [0.978, 0.999] | 0.902 [0.879, 0.961] | 1.000 [1.000, 1.000] | 0.014 [0.000, 0.057] |
| tcn | 3820 | 3537 | 0.990 [0.975, 0.998] | 0.896 [0.841, 0.952] | 0.758 [0.571, 0.918] | 0.908 [0.739, 0.973] |
| cnn | 3820 | 3537 | 0.986 [0.971, 0.995] | 0.862 [0.803, 0.897] | 0.727 [0.586, 0.887] | 0.869 [0.759, 0.918] |
| traditional_s16f_scorecard | 3820 | 3537 | 0.956 [0.923, 0.982] | 0.590 [0.565, 0.637] | 0.348 [0.327, 0.363] | 0.894 [0.831, 0.920] |
| mlp | 3820 | 3537 | 0.934 [0.888, 0.987] | 0.474 [0.426, 0.710] | 0.370 [0.309, 0.458] | 0.784 [0.698, 1.000] |

Winner named in `result.json`: **`ridge`**, AP `0.997` [0.993, 0.999]. The traditional scorecard AP is `0.956` [0.923, 0.982].

## 5. Frozen Atom Ledger

| atom_class | n_events | prevalence | tail_precision | tail_enrichment | tail_rate_after_exclusion | kept_pair_fraction | max_pair_share_concentration | downstream_sigma68_delta_ns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pretrigger_baseline_shape | 193 | 0.051 | 1.000 | 1.080 | 0.922 | 0.949 | 0.275 | 0.035 |
| q_template_mismatch | 24 | 0.006 | 1.000 | 1.080 | 0.925 | 0.994 | 0.333 | 0.000 |
| delayed_peak_shape | 382 | 0.100 | 0.950 | 1.026 | 0.923 | 0.900 | 0.270 | 0.005 |
| broad_late_shape | 542 | 0.142 | 0.935 | 1.010 | 0.924 | 0.858 | 0.284 | 0.033 |
| low_charge_pair_artifact | 245 | 0.064 | 0.918 | 0.992 | 0.926 | 0.936 | 0.229 | -0.000 |
| common_shape | 2434 | 0.637 | 0.914 | 0.987 | 0.947 | 0.363 | 0.240 | -0.707 |

## 6. Duplicate-Readout External Control

| atom_class | n_events | prevalence_ci | tail_precision_ci | median_max_abs_charge_asymmetry_ci | p90_max_abs_charge_asymmetry_ci | median_log_odd_minus_even_ci |
| --- | --- | --- | --- | --- | --- | --- |
| pretrigger_baseline_shape | 193 | 0.051 [0.044, 0.055] | 1.000 [1.000, 1.000] | 0.726 [0.713, 0.762] | 0.856 [0.845, 0.860] | -1.519 [-1.627, -1.424] |
| q_template_mismatch | 24 | 0.006 [0.005, 0.009] | 1.000 [1.000, 1.000] | 0.626 [0.620, 0.637] | 0.674 [0.664, 0.681] | -1.265 [-1.292, -1.153] |
| delayed_peak_shape | 382 | 0.100 [0.086, 0.121] | 0.950 [0.904, 0.988] | 0.065 [0.052, 0.090] | 0.331 [0.263, 0.394] | 0.051 [0.028, 0.097] |
| broad_late_shape | 542 | 0.142 [0.115, 0.166] | 0.935 [0.869, 0.984] | 0.091 [0.063, 0.116] | 0.437 [0.401, 0.541] | -0.079 [-0.114, -0.052] |
| low_charge_pair_artifact | 245 | 0.064 [0.059, 0.075] | 0.918 [0.888, 0.955] | 0.032 [0.029, 0.033] | 0.424 [0.323, 0.581] | 0.022 [0.020, 0.024] |
| common_shape | 2434 | 0.637 [0.597, 0.675] | 0.914 [0.831, 0.965] | 0.016 [0.015, 0.017] | 0.172 [0.150, 0.207] | 0.018 [0.017, 0.020] |

The low-charge-pair artifact is interpreted as a charge/topology warning, not a pulse-shape veto. Delayed-peak, broad-late, pre-trigger/baseline, and q-template-mismatch rows remain provisional pulse-shape atoms when their duplicate-asymmetry intervals are not uniquely extreme relative to the artifact class.

## 7. Forced/Random Acquisition Control

The visible ROOT mirror does not expose a usable forced/random acquisition sample for this handoff test:

| quantity | value |
| --- | --- |
| files scanned | 33 |
| files with candidate tag branches | 33 |
| non-beam trigger entries | 0 |
| filename-tagged forced/random files | 0 |

Therefore S02l records the forced/random control as an availability audit, not as direct no-beam truth. The duplicate-readout control is the active independent evidence in this ticket.

## 8. Leakage, Systematics, and Caveats

| check | value | pass |
| --- | --- | --- |
| loro_train_heldout_run_overlap_zero | 0 | yes |
| feature_names_exclude_identifiers_and_labels | nan | yes |
| tail_label_defined_only_from_heldout_fold_template_timing | template_phase D_t > 3 ns | yes |
| all_models_have_oof_scores | 1 | yes |
| rounded_waveform_hash_cross_run_duplicates_reported | 0 | yes |

- The target is an internal downstream timing-span label, not external particle truth.
- The forced/random conclusion is limited by the visible data mirror: absence of tag branches or non-beam trigger entries is not proof that such data were never acquired.
- Duplicate readout is independent electronics information but shares the same event and scintillator path; it is an external control for charge asymmetry, not a full physical truth label.
- Run-block intervals are wide for rare atoms because the evaluation has seven held-out Sample-II analysis runs.
- CNN/TCN architectures are intentionally laptop-scale; the result is a handoff validation, not an architecture-capacity frontier.

## 9. Verdict

The raw count gate passes, the full traditional/ML/NN benchmark is split by run, and `result.json` names `ridge` as the winner. S02l validates the S02k table conditionally: pulse-shape atoms may be handed off provisionally, low-charge-pair rows should remain artifact controls, and true forced/random validation must wait for mirrored tagged ROOT.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02l_1781182736_737_1d9a19c6_external_atom_handoff_validation.py --config configs/s02l_1781182736_737_1d9a19c6_external_atom_handoff_validation.yaml
```

Runtime in this execution was `14.5` s.

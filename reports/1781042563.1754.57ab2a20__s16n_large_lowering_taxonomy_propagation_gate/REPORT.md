# S16n: large-lowering taxonomy propagation gate

- **Ticket:** `1781042563.1754.57ab2a20`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Git commit at run time:** `45f3ad1bc342cee4f817324f8f908b0ea4f952c3`

## Abstract

This study tests whether S16f large adaptive-baseline lowering is a reusable correction variable or a provenance atom that must be separated by mechanism before timing, charge, pile-up, PID, or energy consumers use it.  The analysis rebuilds selected pulses from raw ROOT, freezes a transparent S16f-style morphology taxonomy, computes class-matched propagation endpoints, and benchmarks a traditional scorecard against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new dilated temporal CNN.  The point-estimate benchmark winner recorded in `result.json` is **`mlp`**.

## 1. Raw-ROOT Reproduction

The reproduction gate scans `HRDv` in the immutable data folder, subtracts the first-four-sample median pedestal, applies the `A > 1000 ADC` selected-pulse cut, and compares counts to the S00/S16 report anchor.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

All rows pass at zero tolerance.  The file `input_sha256.csv` pins every raw B-stack ROOT input used for the gate.

## 2. Pre-Registered Estimands

Let `w_(e,s,k)` denote the baseline-subtracted waveform sample for event `e`, downstream stave `s`, and sample `k`.  The template-phase time is

`t_(e,s) = 10 ns * argmin_delta sum_k (w_(e,s,k)/A_(e,s) - T_s(k-delta))^2`,

where each template `T_s` is built only from non-held-out runs.  The geometry-corrected time is

`t'_(e,s) = t_(e,s) - x_s / v`, with `v^-1 = 0.078 ns/cm`.

The descriptive downstream-span label is

`y_e = 1[max_s t'_(e,s) - min_s t'_(e,s) > 3.0 ns]`.

For the head-to-head benchmark, the primary timing-tail propagation label is the stricter S16f-style pair residual endpoint

`z_e = 1[max_(a,b) |t'_(e,a) - t'_(e,b)| > 5.0 ns]`.

This is a timing-tail propagation screen, not external truth.  The propagation endpoint table also reports:

- timing `sigma68`, full RMS, and `|pair residual| > 5.0 ns` fractions;
- charge resolution and charge bias through log-amplitude balance and matched clean controls;
- pile-up enrichment through late secondary-peak and tail-area morphology scores;
- saturation support through high-amplitude support;
- dropout/anomaly support through post-peak negative excursions;
- support drift between held-out and fold-training class mixtures.

## 3. Frozen Traditional Taxonomy

The traditional method is a fixed S16f morphology scorecard.  It forms pretrigger, pile-up, amplitude/topology, and dropout scores from threshold-normalized waveform summaries.  The frozen taxonomy is assigned before fitting any ML model:

- `large_lowering_pretrigger_only`: large lowering with a pretrigger excursion and no pile-up score;
- `large_lowering_pileup_like`: large lowering with late secondary/tail morphology and no pretrigger score;
- `large_lowering_mixed_pretrigger_pileup`: both pretrigger and pile-up scores;
- `large_lowering_amplitude_topology`: large lowering without those two dominant mechanisms;
- `mild_lowering_amplitude_topology`, `high_amplitude_topology`, and `clean_reference` as support controls.

Matched clean controls are sampled exactly by held-out run and amplitude bin where available, falling back to same-run clean controls only when necessary.

## 4. ML and Calibration

All learned methods are trained in leave-one-run-out folds.  No model receives run number, event id, event order, the timing span, the tail label, or the taxonomy class as an input feature.  Ridge uses an L2 logistic model, gradient-boosted trees use histogram boosting, the MLP uses one hidden layer, the CNN receives only the 3 x 18 normalized downstream waveforms, and the new architecture is a dilated temporal CNN with dilation factors 1, 2, and 4.  Each raw score is calibrated by isotonic regression using only the non-held-out run scores in that fold.  The operating threshold is the fold-local 90% clean-acceptance quantile.

## 5. Head-to-Head Benchmark

| model | n_events | n_tail | average_precision_ci | roc_auc_ci | tail_capture_at_90_clean_ci | clean_acceptance_ci | ece_ci |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mlp | 3820 | 1259 | 0.915 [0.865, 0.947] | 0.957 [0.949, 0.961] | 0.904 [0.861, 0.932] | 0.860 [0.814, 0.899] | 0.026 [0.023, 0.037] |
| ridge | 3820 | 1259 | 0.844 [0.774, 0.920] | 0.929 [0.913, 0.945] | 0.854 [0.831, 0.873] | 0.874 [0.852, 0.895] | 0.027 [0.020, 0.048] |
| gradient_boosted_trees | 3820 | 1259 | 0.840 [0.750, 0.882] | 0.917 [0.901, 0.929] | 0.880 [0.825, 0.925] | 0.786 [0.737, 0.839] | 0.073 [0.060, 0.093] |
| dilated_tcn | 3820 | 1259 | 0.384 [0.224, 0.579] | 0.623 [0.532, 0.746] | 0.837 [0.743, 0.943] | 0.453 [0.339, 0.597] | 0.116 [0.055, 0.193] |
| cnn1d | 3820 | 1259 | 0.363 [0.238, 0.535] | 0.586 [0.495, 0.710] | 0.693 [0.415, 0.922] | 0.605 [0.400, 0.766] | 0.054 [0.029, 0.161] |
| traditional_scorecard | 3820 | 1259 | 0.292 [0.190, 0.425] | 0.435 [0.347, 0.561] | 0.977 [0.962, 0.990] | 0.052 [0.041, 0.077] | 0.003 [0.002, 0.122] |

The winner is **`mlp`** with held-out average precision `0.915` [0.865, 0.947].  The frozen traditional scorecard reaches `0.292` [0.190, 0.425], so the winner-minus-traditional AP delta is `0.624` [0.470, 0.741].  Calibration is reported as expected calibration error (ECE); lower is better.

## 6. Mechanism Controls

| control | n_features | average_precision | roc_auc | ece |
| --- | --- | --- | --- | --- |
| amplitude_only | 21 | 0.726 | 0.852 | 0.071 |
| topology_only | 8 | 0.620 | 0.798 | 0.057 |
| pileup_only | 8 | 0.562 | 0.725 | 0.096 |
| pretrigger_only | 10 | 0.438 | 0.663 | 0.131 |
| shuffled_label | 99 | 0.276 | 0.383 | 0.014 |

The family-restricted controls show which morphology block carries timing-tail information.  The shuffled-label control is the negative control; it should remain near the base positive rate and cannot be adopted as a physical model.

## 7. Propagation by Frozen Taxonomy Class

| taxonomy_class | n_events | event_fraction | tail_fraction_ci | timing_sigma68_ns | timing_full_rms_ns | charge_bias_logsum_vs_matched_clean | pileup_mean_ci | saturation_support_fraction | dropout_anomaly_fraction | support_drift_heldout_minus_train |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_amplitude_topology | 3118 | 0.816 | 0.394 [0.252, 0.495] | 2.946 | 3.376 | 0.911 | 3.13 [3.09, 3.15] | 0.189 | 0.000 | 0.000 |
| large_lowering_mixed_pretrigger_pileup | 362 | 0.095 | 0.050 [0.034, 0.065] | 2.651 | 5.417 | 0.105 | 3.09 [3.04, 3.12] | 0.061 | 0.514 | 0.000 |
| mild_lowering_amplitude_topology | 239 | 0.063 | 0.046 [0.036, 0.059] | 2.642 | 4.267 | 0.846 | 3.12 [3.07, 3.15] | 0.113 | 0.000 | 0.000 |
| clean_reference | 100 | 0.026 | 0.000 [0.000, 0.000] | 2.632 | 2.242 | 0.000 | 2.12 [1.93, 2.35] | 0.000 | 0.000 | 0.000 |
| large_lowering_pileup_like | 1 | 0.000 | 0.000 [0.000, 0.000] | 1.803 | 2.343 | -0.110 | 3.09 [3.09, 3.09] | 0.000 | 0.000 | 0.000 |

The largest timing-tail point estimate is in **`high_amplitude_topology`** with tail fraction `0.394`.  Large lowering therefore does not propagate as a single mechanism: the endpoint shifts depend on whether the waveform atom is pretrigger-like, pile-up-like, high-amplitude/topological, or mixed.

## 8. Systematics

- The timing-tail label is an internal pair-residual proxy.  It can contain residual timewalk and detector geometry effects, not only pile-up.
- The pile-up endpoint is a waveform morphology enrichment, not a calibrated beam pile-up probability.
- The charge bias endpoint is relative to matched clean controls and should not be read as an absolute deposited-energy scale.
- Saturation support uses high-amplitude support because the reduced HRD samples do not provide an independent electronics saturation truth flag.
- Run-block bootstrap intervals capture finite run-to-run instability across the Sample-II analysis runs, but they do not cover alternate taxonomy thresholds.
- The neural networks are intentionally laptop-safe.  Larger architectures are not needed to answer the gate question and would change the study into a capacity scan.

## 9. Leakage Checks

| check | value | pass |
| --- | --- | --- |
| raw_root_reproduction_before_modeling | see reproduction_match_table.csv | yes |
| feature_names_exclude_identifiers_labels_and_taxonomy_label |  | yes |
| leave_one_run_out_scores_complete | 1 | yes |
| isotonic_calibration_fold_local | fit on non-heldout run scores only | yes |
| forbidden_feature_policy | event id; taxonomy class label as a model feature; run id; event order; dt_span_ns; tail label | yes |

## 10. Verdict

The raw selected-pulse anchor is reproduced exactly.  The propagation table supports the conservative interpretation that S16f large lowering is a provenance atom, not a correction to be reused blindly downstream.  The strongest timing-tail ranker is **`mlp`**, but the physics-facing result is class separation: pretrigger-like, pile-up-like, amplitude/topology, and mixed large-lowering atoms have different timing, charge, pile-up, saturation, and dropout signatures.  Downstream timing, charge, PID, or energy consumers should therefore carry the taxonomy class or explicitly veto/condition on it rather than applying a monolithic baseline-lowering correction.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.py --config configs/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.json
```

Runtime in this execution was `118.32` s.  Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `input_sha256.csv`, `heldout_fold_metrics.csv`, `run_block_bootstrap_summary.csv`, `control_model_summary.csv`, `class_propagation_metrics.csv`, `run_class_endpoint_metrics.csv`, `oof_event_predictions.csv`, and `leakage_checks.csv`.

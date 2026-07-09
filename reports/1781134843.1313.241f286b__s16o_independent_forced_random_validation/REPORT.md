# S16o: independent forced-random validation of S16n large-lowering propagation classes

- **Ticket:** `1781134843.1313.241f286b`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-07-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Git commit at run time:** `86bafe676dade95b30d4c92630f6d93b4d930548`

## Abstract

This study tests the S16o ticket: do S16n pretrigger-like, pile-up-like, amplitude/topology, and mixed large-lowering classes persist when the available reference is forced-random/no-pulse data or, if no such labels are mounted, independent mirror-trigger held-out runs?  The visible checkout contains no forced-random/no-pulse/pedestal B-stack ROOT source, so direct electronics-pedestal validation is not claimed.  The analysis therefore rebuilds selected pulses from raw ROOT, audits the data tree for external labels, freezes a transparent S16n/S16f morphology taxonomy, computes class-matched propagation endpoints on held-out mirror-trigger runs, and benchmarks a traditional scorecard against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new dilated temporal CNN.  The point-estimate benchmark winner recorded in `result.json` is **`mlp`**.

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

## 1.1. Forced-Random / Mirror-Reference Source Audit

The current mounted data tree was scanned recursively, following the `data` symlink, for filenames containing `forced`, `random`, `no-pulse`, `nopulse`, `no_pulse`, `pedestal`, or `ped`.  The audit artifact `external_source_audit.csv` contains zero rows.  Consequently, this S16o execution cannot make a direct electronics-pedestal truth claim.  The reference used below is the independent mirror-trigger raw HRDv population split by source run: every fold trains without the held-out Sample-II run and then tests whether the S16n classes persist as timing, charge, pile-up, saturation, and dropout propagation atoms.

This distinction is part of the estimand.  A forced-random/no-pulse validation would estimate persistence against non-beam electronics labels.  The present mirror-trigger validation estimates whether the class separation survives run-held-out beam-triggered waveforms without using run id, event id, timing labels, or taxonomy labels as model inputs.

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
| mlp | 3820 | 1259 | 0.918 [0.878, 0.949] | 0.958 [0.953, 0.964] | 0.917 [0.881, 0.939] | 0.859 [0.814, 0.896] | 0.023 [0.021, 0.029] |
| ridge | 3820 | 1259 | 0.844 [0.768, 0.927] | 0.929 [0.915, 0.946] | 0.854 [0.830, 0.879] | 0.874 [0.853, 0.896] | 0.027 [0.021, 0.048] |
| gradient_boosted_trees | 3820 | 1259 | 0.840 [0.765, 0.884] | 0.917 [0.902, 0.930] | 0.880 [0.832, 0.924] | 0.786 [0.729, 0.839] | 0.073 [0.060, 0.094] |
| dilated_tcn | 3820 | 1259 | 0.414 [0.263, 0.626] | 0.648 [0.542, 0.771] | 0.693 [0.462, 0.891] | 0.645 [0.493, 0.778] | 0.035 [0.028, 0.170] |
| cnn1d | 3820 | 1259 | 0.364 [0.237, 0.556] | 0.593 [0.513, 0.709] | 0.664 [0.477, 0.846] | 0.596 [0.458, 0.699] | 0.071 [0.033, 0.182] |
| traditional_scorecard | 3820 | 1259 | 0.292 [0.191, 0.427] | 0.435 [0.346, 0.563] | 0.977 [0.961, 0.991] | 0.052 [0.040, 0.078] | 0.003 [0.003, 0.128] |

The winner is **`mlp`** with held-out average precision `0.918` [0.878, 0.949].  The frozen traditional scorecard reaches `0.292` [0.191, 0.427], so the winner-minus-traditional AP delta is `0.627` [0.475, 0.738].  Calibration is reported as expected calibration error (ECE); lower is better.

## 6. Mechanism Controls

| control | n_features | average_precision | roc_auc | ece |
| --- | --- | --- | --- | --- |
| amplitude_only | 21 | 0.726 | 0.852 | 0.071 |
| topology_only | 8 | 0.620 | 0.798 | 0.057 |
| pileup_only | 8 | 0.562 | 0.725 | 0.096 |
| pretrigger_only | 10 | 0.438 | 0.663 | 0.131 |
| shuffled_label | 99 | 0.271 | 0.382 | 0.005 |

The family-restricted controls show which morphology block carries timing-tail information.  The shuffled-label control is the negative control; it should remain near the base positive rate and cannot be adopted as a physical model.

## 7. Propagation by Frozen Taxonomy Class

| taxonomy_class | n_events | event_fraction | tail_fraction_ci | timing_sigma68_ns | timing_full_rms_ns | charge_bias_logsum_vs_matched_clean | pileup_mean_ci | saturation_support_fraction | dropout_anomaly_fraction | support_drift_heldout_minus_train |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_amplitude_topology | 3118 | 0.816 | 0.394 [0.278, 0.492] | 2.946 | 3.376 | 0.911 | 3.13 [3.09, 3.15] | 0.189 | 0.000 | 0.000 |
| large_lowering_mixed_pretrigger_pileup | 362 | 0.095 | 0.050 [0.033, 0.063] | 2.651 | 5.417 | 0.105 | 3.09 [3.03, 3.12] | 0.061 | 0.514 | 0.000 |
| mild_lowering_amplitude_topology | 239 | 0.063 | 0.046 [0.036, 0.058] | 2.642 | 4.267 | 0.846 | 3.12 [3.06, 3.15] | 0.113 | 0.000 | 0.000 |
| clean_reference | 100 | 0.026 | 0.000 [0.000, 0.000] | 2.632 | 2.242 | 0.000 | 2.12 [1.92, 2.31] | 0.000 | 0.000 | 0.000 |
| large_lowering_pileup_like | 1 | 0.000 | 0.000 [0.000, 0.000] | 1.803 | 2.343 | -0.110 | 3.09 [3.09, 3.09] | 0.000 | 0.000 | 0.000 |

The largest timing-tail point estimate is in **`high_amplitude_topology`** with tail fraction `0.394`.  Large lowering therefore does not propagate as a single mechanism: the endpoint shifts depend on whether the waveform atom is pretrigger-like, pile-up-like, high-amplitude/topological, or mixed.

## 8. Systematics

- No visible forced-random/no-pulse/pedestal B-stack ROOT source exists in the mounted data tree, so this is mirror-trigger persistence rather than direct electronics-pedestal truth.
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
| forbidden_feature_policy | tail label; event order; run id; dt_span_ns; event id; taxonomy class label as a model feature | yes |

## 10. Verdict

The raw selected-pulse anchor is reproduced exactly, and the external-source audit finds no direct forced-random/no-pulse B-stack ROOT labels in this checkout.  Under that constraint, the S16n classes persist on independent mirror-trigger held-out runs as non-monolithic propagation atoms.  The strongest timing-tail ranker is **`mlp`**, but the physics-facing result is class separation: pretrigger-like, pile-up-like, amplitude/topology, and mixed large-lowering atoms have different timing, charge, pile-up, saturation, and dropout signatures.  Downstream timing, charge, PID, or energy consumers should therefore carry the taxonomy class or explicitly veto/condition on it rather than applying a monolithic baseline-lowering correction.  Direct promotion to electronics-pedestal labels remains blocked until true forced-random/no-pulse ROOT records are mounted.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.py --config configs/s16o_1781134843_1313_241f286b_independent_forced_random_validation.json
```

Runtime in this execution was `120.15` s.  Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `input_sha256.csv`, `external_source_audit.csv`, `heldout_fold_metrics.csv`, `run_block_bootstrap_summary.csv`, `control_model_summary.csv`, `class_propagation_metrics.csv`, `run_class_endpoint_metrics.csv`, `oof_event_predictions.csv`, and `leakage_checks.csv`.

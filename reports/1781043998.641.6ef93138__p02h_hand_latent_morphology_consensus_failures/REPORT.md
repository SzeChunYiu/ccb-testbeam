# P02h: hand-latent morphology consensus failures

- **Study ID:** P02h
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-11
- **Ticket:** `1781043998.641.6ef93138`
- **Depends on:** P02e train-only embedding consumer stability; P09b adjudication gallery; P07 saturation recovery run summaries; S16h pretrigger-pedestal run summaries
- **Git commit:** `1ca9c0783d8270e52425f076d36773459dd98260`
- **Config:** `configs/p02h_1781043998_641_6ef93138_consensus_failures.json`

## 0. Question
Which waveform atoms explain cases where the frozen P02e traditional hand/PCA morphology, train-only AE latent, and forbidden all-data latent diagnostic disagree on manual morphology flags or peak-group morphology, and can any ML/NN model predict those consensus failures better than a strong transparent atom score under run-held-out evaluation?

The pre-registered primary metric is held-out **average precision** for the binary label `consensus_failure_any`, defined before model fitting as a disagreement among the three frozen P02e mapped predictions on either `manual_flag` or `peak_group`. Secondary metrics are ROC AUC, Brier score, ECE, atom enrichment, and charge/topology risk deltas. Significance uses paired run-block bootstrap 95% CIs versus the traditional atom score; six claim models were tried.

## 1. Reproduction
The raw B-stack ROOT files in `data/root/root` were scanned independently before using P02e artifacts. Baseline samples [0, 1, 2, 3], B staves B2, B4, B6, B8, and the amplitude cut A > 1000 ADC reproduce the selected-pulse gate.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00/P02e selected B-stave pulses | 640,737 | 640,737 | +0 | 0 | True |

The P02e benchmark sample was then reconstructed from the same raw scan by reusing the frozen seed and per-run/stave cap. The key digest is `565dc01daae5f666ea4444262cb9493678c4f113599131823d937c93f232bdfe` for 42,370 pulses over 33 runs.

## 2. Traditional Method
The traditional baseline is a fixed, transparent atom score:

`s = 0.85 I_early + 0.75 I_late + 0.65 I_low-area + 0.55 I_large-drop + 0.45 I_tail + 0.35 I_delayed + 0.25 I_saturation + 0.20 I_P09-curated + 0.10 min(N_staves-1,3)`.

All terms are frozen before fitting: peak/area/drop/tail atoms are hand waveform variables, `I_P09-curated` is joined only where the P09b gallery contains the same run/event/stave, saturation is the within-run/stave top 5% amplitude flag, and the pretrigger/delayed terms are waveform-shape summaries rather than learned latents. The score is calibrated with a Platt logistic layer using only the calibration run inside each outer split.

## 3. ML and Neural Methods
The ML comparison uses the same outer run splits for every method. For each held-out run block, one non-held-out run is reserved for probability calibration and the model is fit on the remaining runs. Ridge logistic, gradient-boosted trees, and MLP consume the atom/hand feature matrix. The 1D-CNN consumes only the 18-sample normalized waveform. The new architecture, `shape_gated_cnn`, is a late-fusion CNN that concatenates convolutional waveform features with standardized atom features before the classifier head. Run-only, amplitude-only, topology-only, and shuffled-label sentinels are included as leakage and nuisance controls.

## 4. Head-to-head Benchmark
| Method | Metric | Value | 95% run-block CI | Notes |
|---|---|---:|---:|---|
| gradient_boosted_trees | average_precision | 0.9212 | [0.8975, 0.9414] | nonlinear tabular ML |
| mlp | average_precision | 0.9019 | [0.8736, 0.9277] | tabular neural net |
| shape_gated_cnn | average_precision | 0.8848 | [0.8452, 0.9137] | new late-fusion waveform+atom architecture |
| 1d_cnn | average_precision | 0.8330 | [0.7936, 0.8706] | raw waveform neural net |
| ridge_logistic | average_precision | 0.8231 | [0.7831, 0.8584] | linear ridge classifier on hand/atom features |
| traditional_atom_score | average_precision | 0.5442 | [0.4732, 0.6086] | strong hand atom baseline |
| topology_only_sentinel | average_precision | 0.3337 | [0.2974, 0.3779] | nuisance control |
| amplitude_only_sentinel | average_precision | 0.3211 | [0.2823, 0.3619] | nuisance control |
| shuffled_label_sentinel | average_precision | 0.2924 | [0.2617, 0.3244] | null control |
| run_only_sentinel | average_precision | 0.2434 | [0.2200, 0.2663] | nuisance control |

Complete metric table:

| Method | ROC AUC | AP | Brier | ECE |
|---|---:|---:|---:|---:|
| gradient_boosted_trees | 0.9746 | 0.9212 | 0.0996 | 0.1207 |
| mlp | 0.9678 | 0.9019 | 0.0960 | 0.1213 |
| shape_gated_cnn | 0.9643 | 0.8848 | 0.1044 | 0.1283 |
| 1d_cnn | 0.9543 | 0.8330 | 0.1106 | 0.1289 |
| ridge_logistic | 0.9429 | 0.8231 | 0.1091 | 0.1267 |
| traditional_atom_score | 0.8248 | 0.5442 | 0.1574 | 0.1538 |
| topology_only_sentinel | 0.6345 | 0.3337 | 0.1740 | 0.0812 |
| amplitude_only_sentinel | 0.5963 | 0.3211 | 0.1794 | 0.0842 |
| shuffled_label_sentinel | 0.4645 | 0.2924 | 0.1922 | 0.1117 |
| run_only_sentinel | 0.5000 | 0.2434 | 0.1895 | 0.0826 |

Paired AP deltas versus the traditional baseline:

| Method | Delta AP | 95% CI |
|---|---:|---:|
| gradient_boosted_trees | +0.3770 | [+0.3088, +0.4448] |
| mlp | +0.3577 | [+0.2828, +0.4212] |
| shape_gated_cnn | +0.3406 | [+0.2713, +0.4050] |
| 1d_cnn | +0.2888 | [+0.2140, +0.3497] |
| ridge_logistic | +0.2789 | [+0.2177, +0.3350] |

**Winner:** `gradient_boosted_trees` on average precision 0.9212 [0.8975, 0.9414]. The winner's paired AP delta versus the traditional baseline is +0.3770 [+0.3088, +0.4448].

## 5. Falsification
The analysis would falsify an ML win if the best ML/NN model's paired run-block bootstrap CI for AP improvement over `traditional_atom_score` included zero after accounting for the six claim methods. The CI for the selected winner is reported above; because model selection among six claim methods was attempted, the report treats this as exploratory unless the lower bound remains positive with the family-wise interpretation. The shuffled-label sentinel also had to stay near the positive rate; otherwise the pipeline would be considered leaking.

## 6. Consensus-failure Anatomy
Consensus failures occur in 25.1% of the benchmark sample; manual-label disagreement contributes 15.6% and peak-group disagreement 23.0%.

Atom enrichment uses odds ratios for `consensus_failure_any` with 0.5 Haldane correction:

| Atom | Failure rate if atom=1 | Failure rate if atom=0 | Odds ratio |
|---|---:|---:|---:|
| pretrigger_proxy_atom | 0.8701 | 0.1990 | 26.93 |
| large_drop_atom | 0.8234 | 0.2393 | 14.78 |
| early_peak_atom | 0.7758 | 0.1974 | 14.06 |
| tail_atom | 0.5602 | 0.1648 | 6.46 |
| delayed_peak_atom | 0.5599 | 0.1656 | 6.41 |
| late_peak_atom | 0.5607 | 0.1663 | 6.40 |
| p09_curated_atom | 0.6783 | 0.2499 | 6.29 |
| low_area_atom | 0.4614 | 0.2251 | 2.95 |
| saturation_proxy_atom | 0.2175 | 0.2532 | 0.82 |

Charge/topology risk deltas are descriptive systematics, not truth labels:

| Quantity | Failure | Non-failure | Delta |
|---|---:|---:|---:|
| amplitude_adc | 3000.8387 | 3930.3377 | -929.4990 |
| log_amplitude | 7.8919 | 8.1463 | -0.2544 |
| event_selected_staves | 1.5346 | 1.3060 | +0.2286 |
| downstream_stave | 0.4169 | 0.3189 | +0.0980 |
| saturation_proxy_atom | 0.0446 | 0.0539 | -0.0093 |
| pretrigger_proxy_atom | 0.2699 | 0.0135 | +0.2564 |
| waveform_abs_second_diff | 2.0247 | 1.5893 | +0.4354 |

## 7. Threats to Validity
- **Benchmark/selection:** the baseline is a fixed hand atom score using the same variables that motivated P02/P09/P16/P07 diagnostics; the boosted and neural models are compared on identical held-out run blocks.
- **Data leakage:** the target is derived only from frozen P02e out-of-fold predictions. No event-level random split is used. Calibration uses a separate run within the training side of each fold. The forbidden release-style P02e output defines one disagreement source but is not used as a claim feature.
- **Metric misuse:** AP is primary because the failure class is imbalanced; ROC AUC, Brier, and ECE are secondary. Run-block bootstrap CIs resample runs, not events.
- **Post-hoc selection:** the target, metric, and method list are copied from the claimed ticket and this config. The architecture search is limited to one new architecture, `shape_gated_cnn`.

## 8. Leakage and Systematics Checks
| Check | Value | Pass | Note |
|---|---:|---|---|
| raw_reproduction_passed | 1.0 | True | raw ROOT selected-pulse count exactly matches S00/P02e gate |
| benchmark_key_match_p02e | 1.0 | True | reconstructed sample keys match frozen P02e labels |
| outer_split_run_overlap | 0.0 | True | outer folds are disjoint run blocks |
| p09b_gallery_join_fraction | 0.0034694359216426718 | True | curated gallery is partial by design |
| shuffled_label_ap_minus_positive_rate | 0.04111230413728256 | True | null sentinel should stay close to class prevalence |
| run_only_ap | 0.24335863468654526 | True | large run-only AP would indicate run nuisance dominance |
| p02e_forbidden_release_minus_trainonly_manual_ami | 0.02685448437341703 | True | copied from frozen P02e diagnostic |

The P09b gallery join covers only a curated subset, so P09 taxon enrichment is interpreted as an anchored stress-test rather than complete pulse taxonomy. S16 and P07 frozen artifacts are used at run-summary level and as waveform-derived proxies here; this is adequate for a consensus-failure atlas but not for a final causal timing or charge claim.

## 9. Findings and Next Step
The consensus-failure map shows that disagreement is concentrated in peak-phase and tail/curvature boundary atoms rather than in a pure run artifact. The best method is `gradient_boosted_trees` with AP 0.9212; the paired AP delta versus the transparent atom score is +0.3770 [+0.3088, +0.4448]. Because the target is constructed from frozen P02e method disagreements, this is an error-atlas result, not an independent physics label.

Hypothesis: consensus failures are primarily boundary cases in hand morphology space where peak phase, tail fraction, and saturation/pretrigger proxies move together; latent models help when waveform curvature carries extra information, but the release-style all-data latent mainly sharpens peak-group boundaries rather than exposing new physics.

One proposed follow-up is listed in `result.json`: a critic-facing replication that freezes the P02h target and tests the winner on a fresh, non-P02e sample with no reused cluster labels. Its expected information gain is high because it separates genuine morphology generalization from target construction artifacts.

## 10. Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p02h_1781043998_641_6ef93138_consensus_failures.py --config configs/p02h_1781043998_641_6ef93138_consensus_failures.json
```

Primary artifacts: `reproduction_match_table.csv`, `consensus_failure_table.csv`, `method_predictions.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `atom_enrichment.csv`, `risk_delta.csv`, `leakage_checks.csv`, `result.json`, and `manifest.json`.

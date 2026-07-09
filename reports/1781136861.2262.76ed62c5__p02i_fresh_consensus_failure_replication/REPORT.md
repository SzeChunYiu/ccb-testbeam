# P02i: Fresh-sample consensus-failure replication

- **Study ID:** P02i
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-07-09
- **Ticket:** `1781136861.2262.76ed62c5`
- **Depends on:** P02h consensus-failure atlas; P02e raw-root benchmark sample
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Git commit:** `a5f5deae273d4ee85ec30474031f3574b7202aed`
- **Config:** `configs/p02i_1781136861_2262_76ed62c5_fresh_consensus_replication.json`

## 0. Question
Does the P02h consensus-failure morphology target generalize to a fresh raw-root sample whose pulses were excluded from the P02e benchmark keys, and does the P02h gradient-boosted-tree winner remain competitive against ridge, MLP, 1D-CNN, and a late-fusion neural architecture under run-held-out evaluation?

The pre-registered primary metric is held-out average precision (AP) on run-block splits. The target is a frozen operational P02h replication target, not an independent hand-adjudicated truth label:

\[ y_i = 1\{I_{pretrigger,i} \lor I_{large\ drop,i} \lor I_{early\ peak,i} \lor (I_{tail,i} \land I_{late\ peak,i})\}. \]

This target was fixed from P02h atom enrichment before fitting P02i models. It tests whether the P02h morphology-boundary pattern, and the model ranking, survives a fresh raw-root sample; it cannot prove the underlying physical cause without new manual labels.

## 1. Reproduction
The B-stack raw ROOT files in `data/root/root` were rescanned with the P02e/S00 gate: baseline samples [0, 1, 2, 3], staves B2, B4, B6, B8, and A > 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00/P02e selected B-stave pulses | 640,737 | 640,737 | +0 | 0 | True |

After excluding all P02e benchmark keys, the fresh capped sample contains 16,234 pulses over 33 runs. The key digest is `80d1860c0555eb6d2890ead55861cb058f062ebbfa4c5fb7eba0983b5377ac98`.

## 2. Traditional Method
The traditional baseline is the same transparent P02h atom score, with Platt calibration inside each outer split:

\[ s_i = 0.85I_{early}+0.75I_{late}+0.65I_{lowarea}+0.55I_{drop}+0.45I_{tail}+0.35I_{delayed}+0.25I_{sat}+0.20I_{P09}+0.10\min(N_{staves}-1,3). \]

Because the fresh target is itself atom-derived, this baseline is deliberately strong: it represents the parsimonious hypothesis that P02h generalizes as a small set of interpretable waveform-boundary atoms.

## 3. ML and Neural Methods
All methods use identical run-held-out folds. In each fold, held-out runs are untouched; one training-side run is reserved for probability calibration. Ridge logistic, gradient-boosted trees, and MLP use the tabular hand/atom matrix. The 1D-CNN uses only normalized 18-sample waveforms. The new architecture, `shape_gated_cnn`, late-fuses convolutional waveform features with standardized tabular atoms. Run-only, amplitude-only, topology-only, and shuffled-label sentinels check leakage and nuisance dominance.

The logistic/ridge model optimizes penalized log loss, \(\ell + \lambda\|\beta\|_2^2\). The boosted-tree model optimizes additive logistic loss over shallow histogram trees. Neural models optimize weighted binary cross entropy with positive weight \(N_-/N_+\). CIs are nonparametric run-block bootstrap intervals over per-run metrics.

## 4. Head-to-head Benchmark
| Method | AP | 95% run-block CI | ROC AUC | Brier | ECE |
|---|---:|---:|---:|---:|---:|
| mlp | 1.0000 | [1.0000, 1.0000] | 1.0000 | 0.0006 | 0.0039 |
| ridge_logistic | 0.9999 | [0.9997, 1.0000] | 0.9999 | 0.0001 | 0.0002 |
| gradient_boosted_trees | 0.9999 | [0.9997, 1.0000] | 1.0000 | 0.0007 | 0.0012 |
| shape_gated_cnn | 0.9712 | [0.9613, 0.9791] | 0.9932 | 0.0189 | 0.0189 |
| traditional_atom_score | 0.9361 | [0.9205, 0.9499] | 0.9644 | 0.0353 | 0.0562 |
| 1d_cnn | 0.9275 | [0.9058, 0.9467] | 0.9793 | 0.0426 | 0.0635 |
| amplitude_only_sentinel | 0.3993 | [0.3448, 0.4459] | 0.6809 | 0.1563 | 0.0979 |
| shuffled_label_sentinel | 0.3570 | [0.2988, 0.4146] | 0.4640 | 0.1690 | 0.1084 |
| topology_only_sentinel | 0.3107 | [0.2514, 0.3665] | 0.6134 | 0.1478 | 0.0699 |
| run_only_sentinel | 0.2142 | [0.1814, 0.2462] | 0.5000 | 0.1697 | 0.0783 |

Paired AP deltas versus `traditional_atom_score`:

| Method | Delta AP | 95% CI |
|---|---:|---:|
| mlp | +0.0639 | [+0.0476, +0.0800] |
| ridge_logistic | +0.0638 | [+0.0474, +0.0778] |
| gradient_boosted_trees | +0.0638 | [+0.0490, +0.0802] |
| shape_gated_cnn | +0.0351 | [+0.0232, +0.0486] |
| 1d_cnn | -0.0086 | [-0.0313, +0.0132] |

**Winner:** `mlp` with AP 1.0000 [1.0000, 1.0000]. Its paired AP delta versus the traditional baseline is +0.0639 [+0.0476, +0.0800].

## 5. Falsification
The ML-generalization claim would fail if the best ML/NN model did not beat the strong atom baseline by a positive run-block bootstrap AP delta, or if a sentinel approached the claimed winner. The result is interpreted with five claim methods and four sentinels; no cut or target term was changed after seeing P02i model outcomes.

## 6. Target Anatomy and Systematics
| Atom | Fresh target rate if atom=1 | Fresh target rate if atom=0 | P02h failure rate if atom=1 |
|---|---:|---:|---:|
| pretrigger_proxy_atom | 1.0000 | 0.1707 | 0.8701 |
| large_drop_atom | 1.0000 | 0.2135 | 0.8234 |
| early_peak_atom | 1.0000 | 0.1537 | 0.7758 |
| tail_atom | 0.8574 | 0.1411 | 0.5602 |
| late_peak_atom | 0.8498 | 0.1430 | 0.5607 |
| delayed_peak_atom | 0.8387 | 0.1431 | 0.5599 |
| saturation_proxy_atom | 0.2134 | 0.2354 | 0.2175 |

The target prevalence is 0.234 on the fresh sample versus 0.251 in P02h. The shift is a systematic, not a failure: P02i excludes the exact P02e capped sample and therefore changes the run/stave event mix.

## 7. Threats to Validity
- **Benchmark/selection:** the baseline is strong because the replication target is atom-derived; an ML win must exceed this transparent rule on the same held-out runs.
- **Data leakage:** all P02e benchmark keys are excluded before sampling. Splits are by run, not by event. Calibration uses a training-side run only.
- **Metric misuse:** AP is primary because the positive class is imbalanced. ROC AUC, Brier score, and ECE are secondary. CIs resample runs, not individual pulses.
- **Post-hoc selection:** the atom target, methods, folds, and AP metric are fixed in the config and this script before model fitting.

## 8. Leakage Checks
| Check | Value | Pass | Note |
|---|---:|---|---|
| raw_reproduction_passed | 1.0 | True | raw ROOT selected-pulse count exactly matches P02e/S00 gate |
| fresh_sample_overlap_with_p02e_keys | 0.0 | True | fresh sample excludes all P02e benchmark keys |
| outer_split_run_overlap | 0.0 | True | outer folds are disjoint run blocks |
| shuffled_label_ap_minus_positive_rate | 0.12271359664275422 | False | null sentinel should stay near prevalence |
| run_only_ap | 0.2142045797268563 | True | large run-only AP would indicate run nuisance dominance |

The shuffled-label sentinel is elevated relative to the positive rate, so the near-perfect AP of the tabular models should not be read as a calibrated physics classifier. It remains far below the winning AP and the run-only sentinel is benign, but this failed nuisance check strengthens the caveat that P02i validates an operational morphology-boundary proxy rather than independent truth.

## 9. Findings and Next Steps
On the P02e-disjoint fresh raw sample, `mlp` wins with AP 1.0000 [1.0000, 1.0000]. The P02h GBT winner's fresh AP is 0.9999, compared with its original P02h AP 0.9212; this supports morphology-boundary generalization only for the frozen operational target, not for an independent physics label.

Hypothesis: P02h consensus failures are not merely P02e cluster-label artifacts; they are concentrated in recurring raw waveform boundary atoms. The falsifier is straightforward: new hand adjudication on the P02i high-score/low-score disagreement bands should erase the model advantage if the proxy target is just circular atom bookkeeping.

No new follow-up ticket is appended by this study; the most direct next step is already implied by the caveat: hand-adjudicate a small P02i disagreement band before downstream consumers use the predictor as a physics label.

## 10. Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p02i_1781136861_2262_76ed62c5_fresh_consensus_replication.py --config configs/p02i_1781136861_2262_76ed62c5_fresh_consensus_replication.json
```

Primary artifacts: `reproduction_match_table.csv`, `fresh_consensus_table.csv`, `method_predictions.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `leakage_checks.csv`, `atom_target_rates.csv`, `result.json`, and `manifest.json`.

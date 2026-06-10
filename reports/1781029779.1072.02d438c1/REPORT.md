# S16g: canonical HRD trigger-mode run map

- **Ticket:** `1781029779.1072.02d438c1`
- **Worker:** `testbeam-laptop-2`
- **Config:** `s16g_1781029779_1072_02d438c1_trigger_run_manifest.json`
- **Input hashes:** `input_sha256.csv`

## Question

Can a canonical `run_0000` through `run_0065` trigger-mode manifest be built from S16e plus recovered provenance, with per-stack ROOT availability, entries, trigger summaries, empty placeholders, missing runs, and confidence labels?

## Raw ROOT Reproduction First

| Quantity | Expected/provenance value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| S16e forced/random/non-beam ROOT entries | 0 | 0 | yes |
| HRD raw ROOT files in mirror | 110 | 110 | yes |
| Distinct run IDs represented in raw ROOT | 57 | 57 | yes |

S16e's no-forced/random result is reproduced from the raw `TRIGGER` branches before the run manifest is built. Every populated ROOT file has only `TRIGGER == 1`.

## Canonical Manifest

Primary machine-readable table: `canonical_run_0000_0065_trigger_manifest.csv` with a matching JSON-lines copy. It has `132` rows: two stack rows for each requested run.

| Root status | rows |
|---|---:|
| empty_placeholder | 8 |
| missing | 22 |
| populated | 102 |

| Confidence label | rows |
|---|---:|
| high_direct_root_empty | 8 |
| high_direct_root_trigger | 102 |
| high_for_absence_in_current_mirror | 22 |

A-stack has `57` raw ROOT files, including empty placeholders for runs 0000-0003, 0021, and 0022. B-stack has `53` raw ROOT files, starts at run 0012, and has empty placeholders for runs 0021 and 0022. Missing rows are labeled `not_available_in_current_mirror`; this is a statement about the local reduced ROOT/raw archive mirror, not proof that an acquisition never existed.

The direct S16g table cross-checks the prior S16f recovered run map on `132` of `132` rows; all compared availability, entry, and trigger fields match: `True`.

## Traditional Method

The traditional audit combines archive/file-system source inventory, ROOT trigger metadata, filename tokens, and a whole-run B-stack waveform rule for a pedestal/random acquisition: selected-event fraction <= 0.01, quiet-event fraction >= 0.9, and median event max <= 120.0 ADC.

Run-held-out summary for runs `[57, 65]`: mean source score 0.100 [-0.017, 0.217], candidate fraction 0.000 [0.000, 0.000]. No B-stack run passes as a forced/random or pedestal trigger-mode candidate.

Closest populated B-stack runs by traditional source score:

| Run | entries | quiet fraction | selected-event fraction | median event max [ADC] | score | candidate |
|---:|---:|---:|---:|---:|---:|---|
| 60 | 36074 | 0.560 | 0.281 | 68.5 | 0.272 | False |
| 61 | 36535 | 0.539 | 0.309 | 71.5 | 0.223 | False |
| 65 | 38424 | 0.534 | 0.310 | 73.0 | 0.217 | False |
| 62 | 37584 | 0.522 | 0.317 | 75.0 | 0.198 | False |
| 59 | 42303 | 0.521 | 0.328 | 75.0 | 0.185 | False |
| 64 | 35943 | 0.519 | 0.337 | 75.0 | 0.175 | False |
| 43 | 13 | 0.462 | 0.385 | 155.5 | 0.061 | False |
| 63 | 37030 | 0.467 | 0.399 | 93.5 | 0.058 | False |

## ML Method and Leakage

The ML probe is a run-held-out regularized logistic classifier trained to distinguish quiet-proxy events (`event max < 80.0 ADC`) from selected pulse events (`event max > 1000.0 ADC`) using only pre-trigger summaries. It is a hidden-mode leakage probe, not a truth-label trigger-mode classifier, because there are no non-beam trigger labels.

Best CV setting: `{'C': 10.0, 'cv_auc': 0.6911158609567069, 'cv_auc_std': 0.026728276718548095, 'cv_average_precision': 0.47430314736029794}`. Held-out runs `[57, 65]`: AUC 0.645 [0.584, 0.681], AP 0.648, mean quiet probability 0.404 [0.376, 0.431]. High ML scores do not coincide with any external provenance, filename, or ROOT trigger evidence for a hidden forced/random run.

| Check | value | pass? | Interpretation |
|---|---:|---|---|
| shuffled_training_labels | 0.418 | True | AUC should be near chance under shuffled labels. |
| repeated_shuffled_training_labels_mean_auc | 0.495 | True | Shuffle AUC 2.5/50/97.5% quantiles 0.388/0.487/0.630. |
| intentional_label_oracle | 1.000 | True | Direct label leakage would be visible. |
| real_feature_exclusion |  | True | ML excludes run id, file name, trigger, event id, event max, post-trigger samples, and labels. |

## Conclusion

Yes. The canonical trigger-mode manifest is now available as a compact table for downstream pedestal/timing studies. The populated ROOT evidence is high-confidence beam-trigger-only; empty placeholders are high-confidence zero-entry ROOT files; missing rows are high-confidence absence-in-current-mirror labels. No recovered S16e/S16f provenance or run-held-out traditional/ML audit identifies a true forced/random trigger-mode run.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781029779_1072_02d438c1_trigger_run_manifest.py --config configs/s16g_1781029779_1072_02d438c1_trigger_run_manifest.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `canonical_run_0000_0065_trigger_manifest.csv`, `canonical_run_0000_0065_trigger_manifest.jsonl`, `root_trigger_audit.csv`, `archive_member_inventory.csv`, `filesystem_inventory.csv`, `reproduction_match_table.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `traditional_heldout_summary.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.

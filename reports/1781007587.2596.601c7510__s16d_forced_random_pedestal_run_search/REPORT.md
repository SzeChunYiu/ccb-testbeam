# S16d: locate true forced/random HRD pedestal runs

- **Ticket:** 1781007587.2596.601c7510
- **Worker:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `6fb20b0b409b36d14664fac98e38296061685206`
- **Config:** `s16d_config.json`

## Question

Can we locate run-log or ROOT inputs with true forced/random HRD pedestal triggers for B-stack validation?

## Raw ROOT reproduction first

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | 640737 | 640737 | yes |
| forced/random-tagged ROOT entries | 0 | 0 | yes |

The explicit ROOT audit found `0` entries with `TRIGGER != 1` and `0` ROOT filename hits for forced/random/pedestal tokens. The filesystem scan found `0` likely run-log/metadata files under `/home/billy/ccb-data` and `0` forced/random/pedestal filename hits.

## Traditional method

The traditional locator combines explicit metadata (`TRIGGER != 1`, forced/random/pedestal filename tokens, run-log files) with a conservative waveform rule for a whole B-stack run: selected-event fraction <= 0.01, quiet-event fraction >= 0.9, and median event max <= 120.0 ADC.

No run passes this rule. The closest runs by score are:

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

## ML method

The ML method is a regularized logistic classifier trained on non-held-out runs to distinguish quiet-proxy events (`event max < 80.0 ADC`) from selected pulse events (`event max > 1000.0 ADC`) using only pre-trigger summaries. It excludes run, trigger, filenames, event IDs, event max, post-trigger amplitudes, and labels. Held-out runs are [57, 65]; calibration runs are [56, 64]. Best CV setting: `{'C': 10.0, 'cv_auc': 0.6934749018775012, 'cv_auc_std': 0.026723983192205102, 'cv_average_precision': 0.47819243576490916}`.

Held-out run performance: AUC 0.646 [0.564, 0.704], average precision 0.645, mean quiet probability 0.409 [0.382, 0.433].

The ML score also does not identify a true pedestal run: no run has explicit forced/random evidence, and the highest ML quiet-probability runs still have ordinary beam selected-event fractions rather than all-quiet pedestal behavior.

## Leakage checks

| Check | value | Interpretation |
|---|---:|---|
| shuffled_training_labels | 0.424 | AUC should fall near 0.5 when quiet/pulse labels are destroyed. |
| intentional_label_oracle | 1.000 | AUC near 1 confirms direct label leakage would be obvious and is not in real features. |
| real_feature_exclusion |  | ML features exclude run, event id, trigger, post-trigger amplitudes, event_max, selected/quiet labels, and filenames. |

## Conclusion

The current raw mirror does **not** contain true forced/random HRD pedestal inputs suitable for replacing the S16b quiet-event proxy. Every populated ROOT file has `TRIGGER == 1`, no run-log/metadata file is present under the local data mirror, and no B-stack run satisfies a whole-run pedestal signature. The highest quiet-proxy runs are beam runs with roughly one-third to one-half selected-event fraction, not random pedestal acquisitions.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781007587.2596.601c7510__s16d_forced_random_pedestal_run_search/s16d_forced_random_pedestal_run_search.py --config reports/1781007587.2596.601c7510__s16d_forced_random_pedestal_run_search/s16d_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `trigger_audit.csv`, `filesystem_runlog_scan.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.

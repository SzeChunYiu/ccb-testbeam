# S16e: external DAQ run-log acquisition audit

- **Ticket:** 1781013928.1528.29ac7cae
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Config:** `s16e_external_daq_run_log_config.json`
- **Input checksums:** `input_sha256.csv`
- **Git commit at runtime:** `659d2f8b652412017196ea66ca7f1d2068a11cb2`

## Question

Can the original DAQ logbook, trigger-mode spreadsheet, or acquisition scripts be located for runs `0000-0065` and matched to HRD ROOT run numbers?

## Raw ROOT Reproduction First

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| B-stack selected stave pulses, `A > 1000 ADC`, S00 runs | 640737 | 640737 | yes |
| HRD raw ROOT files in mirror | 110 | 110 | yes |
| distinct run ids represented in raw ROOT | 57 | 57 | yes |
| ROOT entries with `TRIGGER != 1` | 0 | 0 | yes |

The run map covers requested runs `0000-0065`, but not every run has both stacks. A-stack has 57 ROOT files including empty placeholder runs 0000-0003; B-stack has 53 ROOT files and starts at run 0012. Every populated raw ROOT file has only `TRIGGER == 1`.

## External Source Search

Archive member inventory and extracted filesystem inventory found `0` external-log candidates. The only non-ROOT document under the data mirror is `bstack_astack_report_with_timing_label_pileup_ml.pdf`; no DAQ logbook, trigger-mode spreadsheet, or acquisition script was found in the local mirror or raw zip member names.

## Traditional Method

The traditional method combines archive/file-system source inventory, ROOT trigger metadata, filename tokens, and a whole-run waveform rule for a pedestal/random acquisition: selected-event fraction <= 0.01, quiet-event fraction >= 0.9, and median event max <= 120.0 ADC.

No run passes as a true external-source or pedestal/random trigger-mode candidate. Closest B-stack runs by waveform score:

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

## ML Method

The ML probe is a run-held-out regularized logistic classifier trained to distinguish quiet-proxy events (`event max < 80.0 ADC`) from selected pulse events (`event max > 1000.0 ADC`) using only pre-trigger summaries. It excludes run id, file names, trigger, event ids, post-trigger samples, event max, and labels. It is not a truth-label classifier for DAQ mode; it is a leakage-audited check for hidden pre-trigger mode structure.

Best CV setting: `{'C': 10.0, 'cv_auc': 0.6965314745110529, 'cv_auc_std': 0.02126353293726922, 'cv_average_precision': 0.48057413335186966}`. Held-out runs `[57, 65]`: AUC 0.647 [0.586, 0.691], AP 0.645, mean quiet probability 0.417 [0.390, 0.444].

The ML ranking does not reveal a hidden forced/random run: high-score runs still have ordinary beam selected-event fractions, and there is no matching external-source or ROOT trigger evidence.

## Leakage Checks

| Check | value | Interpretation |
|---|---:|---|
| shuffled_training_labels | 0.592 | AUC should be near chance if the signal is not leakage. |
| repeated_shuffled_training_labels_mean_auc | 0.511 | Thirty shuffled-label fits gave 2.5/50/97.5% quantiles 0.385/0.521/0.613. |
| intentional_label_oracle | 1.000 | AUC near 1 shows direct label leakage would be visible. |
| real_feature_exclusion |  | ML excludes run id, file name, trigger, event id, event max, post-trigger samples, and quiet/pulse labels. |

## Conclusion

The requested external DAQ logbook/spreadsheet/acquisition scripts are not present in the current data mirror. The available raw ROOT can be matched across runs `0000-0065`, but it contains no forced/random trigger tags and no external trigger-mode source to resolve whether pedestal triggers were never archived versus absent from this reduced mirror. The evidence supports the narrower conclusion: **absent from the current reduced mirror and raw zip archives inspected here**.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781013928.1528.29ac7cae/s16e_external_daq_run_log.py --config reports/1781013928.1528.29ac7cae/s16e_external_daq_run_log_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `archive_member_inventory.csv`, `filesystem_inventory.csv`, `root_trigger_audit.csv`, `run_0000_0065_mapping.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.

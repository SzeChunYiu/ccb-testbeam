# S16f: recover DAQ provenance outside reduced mirror

- **Ticket:** 1781029779.1038.2ac4471f
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Config:** `s16f_1781029779_1038_2ac4471f_recover_daq_provenance_config.json`
- **Input checksums:** `input_sha256.csv`
- **Git commit at runtime:** `b5db501526ec495c03c62047b0f22cde66b0150e`

## Question

Can the original CCB DAQ logbook, trigger-mode spreadsheet, acquisition scripts, or operator notes be recovered from non-mirror sources and reconciled to HRD runs `0000-0065`? Start from S16e report `1781013928.1528.29ac7cae`, preserve source checksums, and record whether forced/random pedestal triggers were never archived or only absent from the reduced mirror.

## Raw ROOT Reproduction First

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| B-stack selected stave pulses, `A > 1000 ADC`, S00 runs | 640737 | 640737 | yes |
| HRD raw ROOT files in mirror | 110 | 110 | yes |
| distinct run ids represented in raw ROOT | 57 | 57 | yes |
| ROOT entries with `TRIGGER != 1` | 0 | 0 | yes |

The run map covers requested runs `0000-0065`, but not every run has both stacks. A-stack has 57 ROOT files including empty placeholder runs 0000-0003; B-stack has 53 ROOT files and starts at run 0012. Every populated raw ROOT file has only `TRIGGER == 1`.

## Source Root Search

| Source root | exists | symlink | resolved path | files to depth 5 |
|---|---:|---:|---|---:|
| desktop_data_originals | True | True | /home/billy/ccb-data/extracted | 216 |
| local_raw_archives | True | False | /home/billy/ccb-data/raw | 3 |
| local_extracted_mirror | True | False | /home/billy/ccb-data/extracted | 216 |
| local_collaboration_docs | True | False | /home/billy/ccb-data/docs | 1 |
| repo_derived_docs | True | False | /home/billy/Desktop/test_beam/docs | 12 |
| lunarc_canonical_archive | False | False | missing | 0 |
| home_onedrive | True | False | /home/billy/onedrive | 103 |
| claude_backup | True | False | /home/billy/claude-backup-20260504-112839 | 728 |
| claude_code_backups | True | False | /home/billy/claude-code-backups | 632 |

Archive member inventory and filesystem inventory found `0` original-like DAQ/run-log/source candidates after excluding derived repository docs. The non-ROOT source documents hashed for this study are `00_overview.md, 01_setup_and_detector.md, 02_data_and_runs.md, 03_pulse_reconstruction.md, 04_timing_calibration.md, 05_timing_resolution.md, 06_pileup.md, 07_ml_methods.md, 08_astack.md, 09_open_questions.md, bstack_astack_report_with_timing_label_pileup_ml.pdf, glossary.md, references.md`. No DAQ logbook, trigger-mode spreadsheet, forced/random run list, acquisition script, or operator note was recovered from the Desktop data path, raw archives, local docs, LUNARC path, OneDrive, or home backup roots available on this worker.

## Traditional Method

The traditional method combines source-root availability, archive/file-system provenance inventory, ROOT trigger metadata, filename tokens, and a whole-run waveform rule for a pedestal/random acquisition: selected-event fraction <= 0.01, quiet-event fraction >= 0.9, and median event max <= 120.0 ADC.

Run-held-out summary for runs `[57, 65]`: mean source score 0.100 [-0.017, 0.217], candidate fraction 0.000 [0.000, 0.000].

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

Best CV setting: `{'C': 10.0, 'cv_auc': 0.6932421614259378, 'cv_auc_std': 0.024100744838199822, 'cv_average_precision': 0.47494287383805783}`. Held-out runs `[57, 65]`: AUC 0.646 [0.571, 0.701], AP 0.653, mean quiet probability 0.399 [0.374, 0.423].

The ML ranking does not reveal a hidden forced/random run: high-score runs still have ordinary beam selected-event fractions, and there is no matching external-source or ROOT trigger evidence.

## Leakage Checks

| Check | value | Interpretation |
|---|---:|---|
| shuffled_training_labels | 0.421 | AUC should be near chance if the signal is not leakage. |
| repeated_shuffled_training_labels_mean_auc | 0.481 | Thirty shuffled-label fits gave 2.5/50/97.5% quantiles 0.375/0.469/0.597. |
| intentional_label_oracle | 1.000 | AUC near 1 shows direct label leakage would be visible. |
| real_feature_exclusion |  | ML excludes run id, file name, trigger, event id, event max, post-trigger samples, and quiet/pulse labels. |

## Conclusion

No original CCB DAQ logbook, trigger-mode spreadsheet, acquisition script, or operator note was recovered. The available raw ROOT can be reconciled across runs `0000-0065`, but it contains no forced/random trigger tags and no recovered external trigger-mode source. Therefore this study **does not prove forced/random pedestal triggers were never archived**; it supports only the narrower conclusion that they are absent from the reduced mirror, local raw zip archives, and the non-mirror source roots accessible on this worker. The LUNARC path listed in `DATA.md` is not mounted here, so it remains unresolved rather than positively searched.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781029779.1038.2ac4471f/s16f_1781029779_1038_2ac4471f_recover_daq_provenance.py --config reports/1781029779.1038.2ac4471f/s16f_1781029779_1038_2ac4471f_recover_daq_provenance_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `source_root_status.csv`, `archive_member_inventory.csv`, `filesystem_inventory.csv`, `provenance_candidates.csv`, `root_trigger_audit.csv`, `run_0000_0065_mapping.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `traditional_heldout_summary.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.

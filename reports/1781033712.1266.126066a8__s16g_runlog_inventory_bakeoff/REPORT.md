# S16g: Cross-Mirror Run-Log Inventory for CCB HRD Data

- **Study ID:** S16g
- **Ticket:** 1781033712.1266.126066a8
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction, S16g trigger/forced-random manifest audits
- **Input checksum(s):** `run_log_manifest.csv`
- **Git commit:** `2453b203bc4db1178d3d4e56e58cfeebf2220cd5`
- **Config:** `configs/s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.json`

## 0. Question

Can the visible laptop/canonical mirrors provide a versioned HRD run-log inventory linking run number, trigger mode, beam state, stack, and raw ROOT checksums for runs 1-65, and does any waveform-only ML/NN method improve on the deterministic metadata parser for this inventory task?

The atomic steps are: enumerate all visible ROOT/archive sources; reproduce the expected raw ROOT counts; write a checksum manifest; then benchmark stack assignment on held-out runs using the manifest parser versus ridge, gradient-boosted trees, MLP, 1D-CNN, and a new channel-attention CNN.

## 1. Reproduction (mandatory gate)

The script reads `h101` directly from `data/root/root/hrd[ab]_run_NNNN.root`. The inventory gate counts raw ROOT files, HRDA/HRDB split, B-stack selected pulses with median(samples 0-3) baseline subtraction and `A>1000` ADC, and non-beam trigger entries. The selected-pulse reproduction row uses the canonical S00 report-run set: Sample I calibration runs 31-37 and 39-42, Sample I analysis runs 44-57, Sample II calibration run 64, and Sample II analysis runs 58-63 and 65.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| ROOT files in raw bundle | 110 | 110 | 0 | 0 | yes |
| HRDA ROOT files | 57 | 57 | 0 | 0 | yes |
| HRDB ROOT files | 53 | 53 | 0 | 0 | yes |
| selected B-stave pulses on S00 report runs | 640737 | 640737 | 0 | 0 | yes |
| non-beam trigger entries | 0 | 0 | 0 | 0 | yes |

The resulting manifest has one row per raw ROOT file. All non-empty visible entries have `TRIGGER=1` only, so the locally inferable event-level beam state is `beam_triggered`; `8` zero-entry files are recorded as `empty_tree`. No separate forced/random or non-beam run-log record is present in the mounted mirrors.

Across all visible HRDB files, including early runs 12-30 outside the S00 report-run count, the same raw selector finds `1084018` B-stave pulses. This all-run count is reported as an inventory diagnostic, not as the S00 reproduction target.

| Stack | ROOT files | Entries | First run | Last run |
|---|---:|---:|---:|---:|
| A | 57 | 1652508 | 0 | 65 |
| B | 53 | 1649802 | 12 | 65 |

Potential run-log/archive token hits among visible mirrors:

None in the visible roots.

## 2. Traditional (non-ML) method

The strong traditional method is the inventory parser itself. For a file path \(f\), it applies the deterministic rule

\[
\hat s(f)=\begin{cases}
B, & \mathrm{basename}(f)\sim \texttt{hrdb\_run\_NNNN.root},\\
A, & \mathrm{basename}(f)\sim \texttt{hrda\_run\_NNNN.root}.
\end{cases}
\]

The trigger mode and beam state are not learned: they are read from the ROOT branch inventory as `TRIGGER=1 only` with zero non-beam entries. The uncertainty is therefore not a fit uncertainty but a provenance uncertainty: within the visible mirrors it is exact; relative to unknown external DAQ archives it remains conditional on mirror completeness. No chi-square/ndf is applicable because this is a deterministic manifest join, not a parametric fit.

## 3. ML method

The ML task is deliberately narrower than the manifest: predict stack (`A` vs `B`) from waveform content only, under grouped splits by run. It is a falsification-oriented benchmark asking whether ML can replace simple metadata for this inventory field. Each file contributes up to `80` raw events; the held-out unit is run number, so both A and B events from a held-out run are excluded from training. Features for ridge, gradient-boosted trees, and MLP are baseline-subtracted waveform summaries: pre-trigger moments, peak heights, peak locations, and early integrals by channel. CNN methods receive only the 8x18 baseline-subtracted waveform.

Ridge means L2-regularized logistic regression with train-run inner grouped CV over alpha. The fixed panel is ridge, `HistGradientBoostingClassifier`, MLP, 1D-CNN, and a new channel-attention CNN that learns per-channel gates before the temporal convolution. Probabilities are evaluated on held-out runs; confidence intervals resample held-out runs with replacement. Probability calibration is summarized by log loss, Brier score, and 10-bin expected calibration error (ECE); no probability calibration transform is fitted because the production decision is a deterministic manifest parse rather than calibrated stack probabilities.

Grouped CV/hyperparameter choices:

| Fold | Method | Choice |
|---:|---|---|
| 1 | traditional_filename_root_parser | parse hrd[a/b]_run_NNNN.root |
| 1 | ridge | alpha=0.01, inner_bal_acc=0.9921 |
| 1 | gradient_boosted_trees | fixed max_iter=90 lr=0.06 |
| 1 | mlp | hidden=[48, 16] |
| 1 | cnn1d | fixed small CNN |
| 1 | channel_attention_cnn | new architecture: channel-gated CNN |
| 2 | traditional_filename_root_parser | parse hrd[a/b]_run_NNNN.root |
| 2 | ridge | alpha=0.01, inner_bal_acc=0.9915 |
| 2 | gradient_boosted_trees | fixed max_iter=90 lr=0.06 |
| 2 | mlp | hidden=[48, 16] |
| 2 | cnn1d | fixed small CNN |
| 2 | channel_attention_cnn | new architecture: channel-gated CNN |
| 3 | traditional_filename_root_parser | parse hrd[a/b]_run_NNNN.root |
| 3 | ridge | alpha=0.01, inner_bal_acc=0.9919 |
| 3 | gradient_boosted_trees | fixed max_iter=90 lr=0.06 |
| 3 | mlp | hidden=[48, 16] |
| 3 | cnn1d | fixed small CNN |
| 3 | channel_attention_cnn | new architecture: channel-gated CNN |

## 4. Head-to-head benchmark (mandatory)

Primary metric: held-out event-level stack accuracy. Secondary metrics are balanced accuracy, ROC AUC, log loss, Brier score, and 10-bin ECE. CIs are run-block bootstrap intervals over held-out runs.

| Method | Accuracy [95% CI] | Balanced accuracy [95% CI] | AUC [95% CI] | Log loss [95% CI] | Brier [95% CI] | ECE10 [95% CI] | Runs |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional_filename_root_parser | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 51 |
| gradient_boosted_trees | 0.9969 [0.9956, 0.9980] | 0.9969 [0.9956, 0.9980] | 0.9998 [0.9997, 1.0000] | 0.0132 [0.0093, 0.0171] | 0.0026 [0.0017, 0.0036] | 0.0025 [0.0019, 0.0037] | 51 |
| ridge | 0.9935 [0.9921, 0.9952] | 0.9935 [0.9921, 0.9952] | 0.9994 [0.9988, 0.9998] | 0.0240 [0.0197, 0.0281] | 0.0052 [0.0041, 0.0063] | 0.0080 [0.0071, 0.0098] | 51 |
| mlp | 0.9890 [0.9868, 0.9910] | 0.9890 [0.9868, 0.9910] | 0.9986 [0.9978, 0.9992] | 0.0381 [0.0287, 0.0469] | 0.0088 [0.0072, 0.0105] | 0.0042 [0.0033, 0.0067] | 51 |
| cnn1d | 0.9090 [0.8991, 0.9180] | 0.9090 [0.8991, 0.9180] | 0.9645 [0.9589, 0.9693] | 0.2414 [0.2249, 0.2572] | 0.0706 [0.0652, 0.0765] | 0.0488 [0.0443, 0.0540] | 51 |
| channel_attention_cnn | 0.8849 [0.8713, 0.8984] | 0.8849 [0.8713, 0.8984] | 0.9463 [0.9400, 0.9530] | 0.2807 [0.2590, 0.3024] | 0.0857 [0.0774, 0.0933] | 0.0471 [0.0420, 0.0548] | 51 |

Winner named in `result.json`: **traditional_filename_root_parser**. The parser is exact because stack is encoded in the raw ROOT filename and cross-checked against the branch inventory. The ML/NN models are useful only as drift diagnostics; they do not improve the run-log manifest.

## 5. Falsification

Pre-registration: the manifest parser wins only if it achieves exact stack recovery, all ROOT files have sha256s, all ROOT entries have an explicit trigger summary, and train/held-out run overlap is zero for ML comparisons. A counterexample would be any malformed filename, missing checksum, mixed trigger mode, or ML model with strictly higher held-out accuracy than the parser after run-bootstrap uncertainty.

Multiple comparisons cover six methods. The family-wise conclusion is controlled by requiring a strict improvement over the deterministic parser; no ML/NN model can exceed 1.0 accuracy, so the exact parser cannot be beaten on this manifest field.

| Check | Value | Pass? |
|---|---:|---|
| fold_1_train_heldout_run_overlap | 0 | yes |
| fold_2_train_heldout_run_overlap | 0 | yes |
| fold_3_train_heldout_run_overlap | 0 | yes |
| all_root_files_have_sha256 | 110 | yes |
| no_nonbeam_trigger_entries | 0 | yes |
| empty_root_trees_recorded_not_modeled | 8 | yes |
| visible_runlog_token_hits | 0 | yes |
| features_exclude_filename_run_and_event_ids_for_ml | tabular waveform summaries and raw waveforms only | yes |
| traditional_parser_uses_inventory_metadata_only | filename plus ROOT branch inventory | yes |

## 6. Threats to validity

Benchmark/selection: the traditional baseline is intentionally strong because the ticket asks for an inventory, not waveform discovery. ML stack prediction is included to satisfy the required head-to-head, but it is not the right production mechanism for metadata that already exists in filenames and ROOT headers.

Data leakage: ML splits are by run. The waveform-only ML features exclude filename, run number, event number, trigger branch, stack label, and path metadata. The traditional parser is allowed to use filename metadata because that is the inventory field being audited.

Metric misuse: event-level stack accuracy is a diagnostic for waveform separability, not a physics result. Full probability metrics and run-bootstrap CIs are reported. Chi-square/ndf is not applicable to deterministic parsing or discriminative classifiers.

Post-hoc selection: expected counts, model families, split type, sample size, and bootstrap plan are fixed in the config before scoring. The winner rule is exact parser first, then held-out accuracy if the parser failed.

Systematics and caveats: absence of external run logs in the visible mirrors does not prove they do not exist. The LUNARC path is recorded as missing if not mounted. Trigger mode is inferred from the reduced ROOT `TRIGGER` branch, not from independent DAQ logbooks. Checksums identify byte-level ROOT files but do not recover acquisition conditions absent from those files. The MLP is capped at the configured iteration budget for laptop runtime; it is retained as a diagnostic comparator, not as a candidate winner over exact metadata.

## 7. Provenance manifest

`manifest.json` records the command, config, git commit, environment, random seed, input ROOT checksums, and output checksums. The main versioned inventory is `run_log_manifest.csv`.

## 8. Findings & next steps

The visible data provide a complete reduced-ROOT manifest: `110` files, `57` A-stack files, `53` B-stack files, and exact reproduction of the `640737` B-stave selected-pulse count. The visible mirrors do not provide an independent DAQ run-log file linking trigger mode and beam state; within ROOT, every non-empty entry is `TRIGGER=1`, while empty trees are recorded explicitly.

Hypothesis: the reduced HRD bundle is a beam-trigger-only analysis export, while richer run conditions, if they exist, live in DAQ-side logs or unmounted archives. The queued follow-up is `S16i: external DAQ run-log checksum join for HRD runs 1-65` because it tests the highest-value missing link: independent acquisition metadata rather than another waveform proxy.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.py --config configs/s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `run_log_manifest.csv`, `mirror_archive_inventory.csv`, `reproduction_match_table.csv`, `selected_b_stave_counts_by_run.csv`, `stack_benchmark_events.csv`, `stack_benchmark_waveforms.npy`, `heldout_stack_predictions.csv`, `model_cv_selections.csv`, `head_to_head_benchmark.csv`, and `leakage_and_inventory_checks.csv`.

# S16i: External DAQ Run-Log Checksum Join for HRD Runs 1-65

- **Study ID:** S16i
- **Ticket:** `1781110796.1578.28f051c2`
- **Author (worker label):** `testbeam-laptop-4`
- **Date:** 2026-07-09
- **Depends on:** S00 selected-pulse reproduction; S16g ROOT checksum manifest and run-log inventory
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `e0b0c12c9a46fcc5e134a5b4b6bef3b625eb323b`
- **Config:** `configs/s16i_1781110796_1578_28f051c2_external_daq_runlog_checksum_join.json`

## 0. Question and Deliverables

The claimed ticket asks whether DAQ-side logbooks or unmounted acquisition products contain independent trigger-mode, beam-state, or forced/random pedestal metadata for HRD runs 1-65, and whether those records can be joined to the ROOT checksum manifest without changing waveform-derived labels. This report delivers a bounded external-record census, an explicit checksum join table, a raw ROOT reproduction gate, and a run-held-out benchmark comparing a deterministic manifest parser against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new channel-attention CNN.

The benchmark is not used to invent missing DAQ truth. It is a falsification test: if an ML/NN method could beat the deterministic metadata parser at stack assignment under run-held-out splits, then waveform content would be carrying a metadata signal not captured by the manifest. It does not happen here.

## 1. Raw ROOT Reproduction Gate

For event \(i\), B-stack stave channel \(c\in\{B2,B4,B6,B8\}\), sample \(t\), and raw waveform \(x_{ict}\), the selected-pulse gate is

\[
p_{ic}=\operatorname{median}(x_{ic0},x_{ic1},x_{ic2},x_{ic3}),\qquad
I_{ic}=\mathbf{1}\left[\max_t(x_{ict}-p_{ic})>1000\ \mathrm{ADC}\right].
\]

The script reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root` before fitting or joining anything. The canonical S00 report-run set reproduces `640,737` selected B-stave pulses exactly.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| ROOT files in raw bundle | 110 | 110 | 0 | 0 | yes |
| HRDA ROOT files | 57 | 57 | 0 | 0 | yes |
| HRDB ROOT files | 53 | 53 | 0 | 0 | yes |
| selected B-stave pulses on S00 report runs | 640737 | 640737 | 0 | 0 | yes |
| non-beam trigger entries | 0 | 0 | 0 | 0 | yes |

Across all visible HRDB files, including early runs outside the S00 report-run count, the same raw selector finds `1,084,018` selected B-stave pulses. This is an inventory diagnostic, not the report target.

## 2. ROOT Checksum Manifest

Every raw ROOT file receives a SHA-256 checksum and a ROOT-branch trigger summary. The visible reduced bundle contains `110` files across runs `0`--`65`:

| stack   |   files |   entries |   first_run |   last_run |
|:--------|--------:|----------:|------------:|-----------:|
| A       |      57 |   1652508 |           0 |         65 |
| B       |      53 |   1649802 |          12 |         65 |

All non-empty visible entries have `TRIGGER=1` only. The direct non-beam/forced/random entry count is therefore `0`. Empty trees are retained in the manifest as `empty_tree` rather than being silently discarded.

## 3. External DAQ Join

The bounded search roots are the configured data mirror, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, and the canonical shared path if mounted. Candidate external records are filesystem files or zip members whose names contain DAQ/logbook/trigger/beam/pedestal/forced/random tokens and whose suffix is a parseable data or text type. The join key is `(run, stack, root_sha256)`, with ROOT-derived trigger mode and beam state retained separately from any external metadata.

Result: `0` manifest rows have an independent external acquisition record joined. The available join is therefore the ROOT checksum manifest only; no waveform-derived labels are changed.

Candidate external records:

_No rows._

Visible run-log token hits, including derived reports and missing roots:

| kind       | path                                                                                                                                         | member   | suffix   |   bytes |
|:-----------|:---------------------------------------------------------------------------------------------------------------------------------------------|:---------|:---------|--------:|
| filesystem | /home/billy/ccb-data/docs/figures/reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/fig_heldout_residual_distributions.png |          | .png     |   58447 |
| filesystem | /home/billy/ccb-data/docs/figures/reports/1781000826.539659.030b7796__s16b_independent_pedestal_estimator_closure/fig_head_to_head.png       |          | .png     |   38680 |
| filesystem | /home/billy/ccb-data/docs/latex/chapters/06_amplitude_energy_pedestal.tex                                                                    |          | .tex     |   14909 |

## 4. Traditional Method

The strong traditional method is the deterministic manifest parser

\[
\hat s(f)=
\begin{cases}
B,&\operatorname{basename}(f)\sim\texttt{hrdb\_run\_NNNN.root},\\
A,&\operatorname{basename}(f)\sim\texttt{hrda\_run\_NNNN.root}.
\end{cases}
\]

It is allowed to use filename and checksum metadata because the scientific object is a provenance join. Its trigger-mode estimate is not fitted; it is the ROOT branch census, \(N_{\mathrm{nonbeam}}=\sum_i \mathbf{1}[\mathrm{TRIGGER}_i\ne1]\). Within the visible mirror, this method has no statistical fit uncertainty: bootstrap intervals are degenerate at exact stack recovery. The caveat is provenance completeness, not estimator variance.

## 5. ML/NN Benchmark

All learned methods are trained and evaluated with grouped splits by run. The tabular models receive baseline-subtracted waveform summaries only: pretrigger moments, peak heights, peak locations, and early integrals by channel. The 1D-CNN receives only the 8x18 baseline-subtracted waveform. The new architecture is a channel-attention CNN:

\[
g=\sigma(W\bar x+b),\qquad z_0 = g\odot x,\qquad
\hat y=\sigma(h(\mathrm{Conv}_2(\mathrm{Conv}_1(z_0)))).
\]

Here \(g\) is an event-wise channel gate learned from channel means. Ridge is L2-regularized logistic regression with inner grouped-CV alpha selection. Gradient-boosted trees use histogram boosting. MLP uses two hidden layers. Confidence intervals resample held-out runs as blocks for every method.

Grouped CV/hyperparameter choices:

| Fold | Method | Choice |
|---:|---|---|
| 1 | traditional_filename_root_parser | parse hrd[a/b]_run_NNNN.root |
| 1 | ridge | alpha=0.01, inner_bal_acc=0.9906 |
| 1 | gradient_boosted_trees | fixed max_iter=90 lr=0.06 |
| 1 | mlp | hidden=[48, 16] |
| 1 | cnn1d | fixed small CNN |
| 1 | channel_attention_cnn | new architecture: channel-gated CNN |
| 2 | traditional_filename_root_parser | parse hrd[a/b]_run_NNNN.root |
| 2 | ridge | alpha=0.01, inner_bal_acc=0.9900 |
| 2 | gradient_boosted_trees | fixed max_iter=90 lr=0.06 |
| 2 | mlp | hidden=[48, 16] |
| 2 | cnn1d | fixed small CNN |
| 2 | channel_attention_cnn | new architecture: channel-gated CNN |
| 3 | traditional_filename_root_parser | parse hrd[a/b]_run_NNNN.root |
| 3 | ridge | alpha=0.01, inner_bal_acc=0.9917 |
| 3 | gradient_boosted_trees | fixed max_iter=90 lr=0.06 |
| 3 | mlp | hidden=[48, 16] |
| 3 | cnn1d | fixed small CNN |
| 3 | channel_attention_cnn | new architecture: channel-gated CNN |

## 6. Head-to-Head Results

Primary metric: held-out event-level stack accuracy. Secondary metrics are balanced accuracy, ROC AUC, log loss, Brier score, and 10-bin expected calibration error.

| Method | Accuracy [95% CI] | Balanced accuracy [95% CI] | AUC [95% CI] | Log loss [95% CI] | Brier [95% CI] | ECE10 [95% CI] | Runs |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional_filename_root_parser | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 0.0000 [0.0000, 0.0000] | 51 |
| gradient_boosted_trees | 0.9969 [0.9955, 0.9982] | 0.9969 [0.9955, 0.9982] | 0.9999 [0.9997, 1.0000] | 0.0124 [0.0090, 0.0162] | 0.0026 [0.0017, 0.0037] | 0.0022 [0.0018, 0.0037] | 51 |
| ridge | 0.9926 [0.9905, 0.9945] | 0.9926 [0.9905, 0.9945] | 0.9985 [0.9975, 0.9994] | 0.0315 [0.0238, 0.0396] | 0.0060 [0.0046, 0.0076] | 0.0094 [0.0080, 0.0110] | 51 |
| mlp | 0.9894 [0.9866, 0.9920] | 0.9894 [0.9866, 0.9920] | 0.9978 [0.9965, 0.9990] | 0.0428 [0.0312, 0.0537] | 0.0091 [0.0070, 0.0111] | 0.0027 [0.0022, 0.0054] | 51 |
| cnn1d | 0.8958 [0.8851, 0.9068] | 0.8958 [0.8851, 0.9068] | 0.9534 [0.9475, 0.9596] | 0.2623 [0.2459, 0.2800] | 0.0789 [0.0727, 0.0854] | 0.0340 [0.0304, 0.0414] | 51 |
| channel_attention_cnn | 0.8900 [0.8780, 0.9021] | 0.8900 [0.8780, 0.9021] | 0.9475 [0.9401, 0.9537] | 0.3017 [0.2854, 0.3179] | 0.0915 [0.0858, 0.0972] | 0.0820 [0.0763, 0.0884] | 51 |

Winner named in `result.json`: **traditional_filename_root_parser** with accuracy `1.0000` and run-block CI `[1.0000, 1.0000]`.

## 7. Systematics, Caveats, and Falsification

The central systematic is archive completeness. Absence of external DAQ records in the visible roots is not proof that the collaboration never recorded forced/random pedestals; it means this worker cannot join an independent acquisition record from the bounded mounted sources. The missing canonical path is reported in `result.json` when unmounted.

Data leakage controls: ML splits are by run; waveform-only ML features exclude filename, path, run id, event id, trigger branch, stack label, and checksums. The deterministic parser is deliberately metadata-aware because metadata parsing is the baseline being audited.

Metric caveat: stack prediction is an inventory diagnostic, not a physics endpoint. It answers whether ML can supersede a manifest parser for a metadata field. It cannot create trigger-mode or forced/random truth when the direct external record is absent.

Falsification rule: the conclusion changes if any independent DAQ logbook, acquisition script, trigger spreadsheet, or archive member with run-level trigger/beam/forced-random fields joins to the ROOT checksum manifest. A malformed ROOT filename, missing checksum, mixed non-beam trigger branch, or train/held-out run overlap would also invalidate the exact-parser conclusion.

| Check | Value | Pass? |
|---|---:|---|
| fold_1_train_heldout_run_overlap | 0 | yes |
| fold_2_train_heldout_run_overlap | 0 | yes |
| fold_3_train_heldout_run_overlap | 0 | yes |
| all_root_files_have_sha256 | 110 | yes |
| no_nonbeam_trigger_entries | 0 | yes |
| empty_root_trees_recorded_not_modeled | 8 | yes |
| visible_runlog_token_hits | 3 | yes |
| features_exclude_filename_run_and_event_ids_for_ml | tabular waveform summaries and raw waveforms only | yes |
| traditional_parser_uses_inventory_metadata_only | filename plus ROOT branch inventory | yes |

## 8. Conclusion

The raw ROOT gate reproduces the required number exactly: `640,737` selected B-stave pulses. The checksum join table covers all visible HRD ROOT files, but no independent external DAQ acquisition record is joined. The ROOT mirror itself shows `TRIGGER=1` only for non-empty entries, so direct forced/random pedestal closure remains blocked by missing provenance rather than by model choice.

The head-to-head benchmark names `traditional_filename_root_parser` as the winner. Learned waveform methods are strong drift diagnostics, but the deterministic checksum manifest is exact for stack metadata and remains the appropriate method for the S16i provenance question.

No novel follow-up ticket is appended from this worker; the current ticket was itself the S16i follow-up to the S16g inventory.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16i_1781110796_1578_28f051c2_external_daq_runlog_checksum_join.py --config configs/s16i_1781110796_1578_28f051c2_external_daq_runlog_checksum_join.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `run_log_manifest.csv`, `external_daq_runlog_checksum_join.csv`, `external_daq_candidate_records.csv`, `reproduction_match_table.csv`, `selected_b_stave_counts_by_run.csv`, `head_to_head_benchmark.csv`, `heldout_stack_predictions.csv`, `model_cv_selections.csv`, and `leakage_and_inventory_checks.csv`.

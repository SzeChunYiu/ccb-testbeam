# S16g: external HRD DAQ acquisition-record audit

- **Study ID:** S16g
- **Ticket:** `1781033977.1173.08a05a94`
- **Author (worker label):** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction; S16f/S16g pedestal-source audits; prior S16g proxy benchmark `reports/1781033528.1397.05213c6c__s16g_forced_random_truth_benchmark`
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `740e2e69da75d83e2c8fb40b3385adcd82b44616`
- **Config:** `configs/s16g_1781033977_1173_08a05a94_external_acquisition_records.json`

## 0. Question

Can any bounded external source visible from this worker identify true B-stack forced/random/pedestal DAQ acquisitions, distinguishing "not recorded" from "recorded but absent from the current ROOT/raw-zip mirror" for the S16e/S16f truth gate?

Atomic steps:

1. Reproduce the S00/S16 selected-pulse count directly from raw HRDB ROOT.
2. Re-audit ROOT trigger branches and archive member names for non-beam forced/random candidates.
3. Search bounded external documentation/report locations for DAQ logbooks, trigger-mode spreadsheets, acquisition scripts, or operator notes.
4. Carry forward the already completed run-held-out S16g proxy benchmark only as context; do not claim it as direct electronics truth.

## 1. Reproduction

For raw waveform \(x_{irct}\), event \(i\), B-stack stave channel \(c\in\{B2,B4,B6,B8\}\), and sample \(t\), the baseline and selection are

\[
p_{ic}=\operatorname{median}(x_{ic0},x_{ic1},x_{ic2},x_{ic3}), \qquad
I_{ic}=\mathbf{1}\left[ \max_t(x_{ict}-p_{ic}) > 1000\ \mathrm{ADC} \right].
\]

The gate is run from `data/root/root/hrdb_run_NNNN.root` only, before any external-record inference.

| Quantity                                 |   Report value |   Reproduced |   Delta |   Tolerance | Pass   |
|:-----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulses              |         640737 |       640737 |       0 |           0 | True   |
| forced/random/non-beam B-stack entries   |              0 |            0 |       0 |           0 | True   |
| independent external acquisition records |              0 |            0 |       0 |           0 | True   |

## 2. Traditional Acquisition Audit

The strong non-ML method is a deterministic provenance audit:

\[
N_{\mathrm{nonbeam}}=\sum_i \mathbf{1}[\mathrm{TRIGGER}_i \ne 1],
\]

plus strict filename/archive-member matching for forced/random/pedestal/no-pulse tokens and manual source classification into independent acquisition candidates versus derived project reports. It is the appropriate baseline because the primary target is provenance, not a latent waveform label.

ROOT trigger/branch summary:

| stack   |   files |   entries |   non_beam |   tag_like |
|:--------|--------:|----------:|-----------:|-----------:|
| hrda    |      57 |   1652508 |          0 |          0 |
| hrdb    |      53 |   1649802 |          0 |          0 |

Visible data/archive mirror summary:

| Quantity | Value |
|---|---:|
| filesystem/archive rows audited | 438 |
| strict forced/random ROOT/archive candidates | 0 |
| non-beam ROOT trigger entries | 0 |
| files with tag-like ROOT branches | 0 |

External-document source summary:

| source_class                    |   files |   candidate_files |   text_hits |
|:--------------------------------|--------:|------------------:|------------:|
| analysis_pdf_not_daq_logbook    |       1 |                 0 |         136 |
| derived_or_unsupported          |       4 |                 0 |          18 |
| derived_repo_document_or_report |      76 |                 0 |         440 |

Independent external acquisition candidates:

_No rows._

The only non-ROOT file under `/home/billy/ccb-data` is the 122-page analysis PDF, not a DAQ logbook or trigger-mode spreadsheet. The Desktop tree contributes derived project reports and docs. Those are useful corroboration of previous audits, but they are not independent acquisition records.

## 3. ML/NN Benchmark Context

This ticket's direct forced/random truth label is absent, so a new supervised ML benchmark would be post-hoc. The relevant benchmark was already completed in `reports/1781033528.1397.05213c6c__s16g_forced_random_truth_benchmark` and is carried forward here as context. It used Sample-II leave-one-run-out splitting and compared the traditional quantile baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, and a pair-symmetric `siamese_cnn_meta` architecture on the same held-out proxy timing-tail task.

The proxy label was

\[
y_i=\mathbf{1}\left(|r_i-m_{p(i)}|>5\ \mathrm{ns}\right),
\]

where \(r_i\) is the pair residual and \(m_{p(i)}\) is the train-run pair-center median. This is a timing-tail proxy, not forced/random electronics pedestal truth.

## 4. Head-To-Head Context

Primary proxy metric: held-out post-veto tail fraction. Run/event bootstrap confidence intervals are copied from the prior committed artifact.

| Method                 | Eff.                    | Tail capture            | Post-veto tail          | sigma68 ns           | AUC                  |
|:-----------------------|:------------------------|:------------------------|:------------------------|:---------------------|:---------------------|
| gradient_boosted_trees | 0.8965 [0.8862, 0.9054] | 0.5172 [0.4019, 0.6161] | 0.0082 [0.0049, 0.0108] | 1.626 [1.570, 1.669] | 0.747 [0.686, 0.793] |
| cnn1d                  | 0.9067 [0.8816, 0.9348] | 0.5115 [0.3976, 0.6294] | 0.0082 [0.0041, 0.0113] | 1.606 [1.545, 1.682] | 0.722 [0.658, 0.791] |
| siamese_cnn_meta       | 0.8983 [0.8822, 0.9126] | 0.5115 [0.3865, 0.6500] | 0.0083 [0.0046, 0.0116] | 1.607 [1.558, 1.670] | 0.742 [0.661, 0.808] |
| ridge                  | 0.8995 [0.8893, 0.9111] | 0.4885 [0.3547, 0.6658] | 0.0086 [0.0044, 0.0120] | 1.561 [1.520, 1.618] | 0.732 [0.646, 0.835] |
| mlp                    | 0.8985 [0.8842, 0.9118] | 0.4828 [0.4070, 0.6206] | 0.0087 [0.0053, 0.0114] | 1.646 [1.584, 1.699] | 0.712 [0.652, 0.793] |
| traditional_quantile   | 0.8997 [0.8807, 0.9175] | 0.3161 [0.2415, 0.4227] | 0.0115 [0.0071, 0.0147] | 1.565 [1.517, 1.608] | 0.701 [0.656, 0.763] |

Proxy-context winner: **gradient_boosted_trees** with post-veto tail fraction `0.008176` [0.004947, 0.010844]. Direct-truth winner for the current ticket: **none**, because no direct forced/random acquisition record or non-beam B-stack ROOT entry is visible.

## 5. Falsification

Pre-registration from the claimed ticket: an external DAQ logbook, trigger-mode spreadsheet, acquisition script, or operator note identifying forced/random/pedestal B-stack runs would falsify the current-mirror absence interpretation.

Falsification test: a candidate must be independent of derived project reports and must contain a forced/random/pedestal/no-pulse token in the source name or text. If such a candidate is found, the result changes from `blocked_missing_external_record` to `external_candidate_found` and direct S16f truth closure becomes the next task.

Result: zero independent candidates pass this test. No p-value is quoted because the audit is a census of bounded visible sources, not a random sample.

## 6. Threats To Validity

Benchmark/selection: the benchmark table is explicitly contextual and reused from a prior committed artifact. The current ticket's winner is not chosen by proxy ML performance; it is determined by the provenance gate.

Data leakage: the raw reproduction reads only HRDB ROOT waveforms. The proxy benchmark context used run-held-out splits and excluded run id, event id, residuals, labels, post-trigger samples, amplitudes, and peak locations from features.

Metric misuse: `sigma68` and post-veto tail fraction are meaningful only for the proxy timing-tail task. They do not validate a pedestal estimator against electronics truth.

Post-hoc selection: external roots are bounded in the config before scanning. Derived reports are classified separately from independent acquisition records so a prior conclusion cannot masquerade as new DAQ provenance.

Systematics and caveats: absence from the visible laptop and Desktop paths is not proof that CCB never recorded forced/random pedestal runs. The LUNARC canonical path is unmounted in this run. The analysis PDF may summarize acquisition conditions, but it is not a raw DAQ logbook and does not identify forced/random B-stack runs.

## 7. Provenance Manifest

`manifest.json` records the command, git commit, Python/platform metadata, input checksums, and output checksums. The primary tables are `external_record_inventory.csv`, `external_text_hits.csv`, `file_archive_inventory.csv`, `root_trigger_branch_audit.csv`, and `prior_proxy_head_to_head_benchmark.csv`.

## 8. Findings And Next Steps

No independent external HRD DAQ acquisition record is visible from the configured bounded sources. This supports the narrower conclusion that the S16e/S16f truth gate is blocked in the mounted mirrors and local documentation, not the stronger conclusion that forced/random runs were never recorded.

Hypothesis: if true forced/random pedestal acquisitions exist, they are in an unmounted DAQ/archive tier rather than in the reduced HRD ROOT mirror or local analysis notes.

No novel follow-up ticket is appended from this worker because the queue already contains downstream S16 pedestal-source uncertainty work, and the ticket budget permits at most one novel item.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033977_1173_08a05a94_external_acquisition_records.py --config configs/s16g_1781033977_1173_08a05a94_external_acquisition_records.json
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `selected_count_by_run.csv`, `reproduction_match_table.csv`, `root_trigger_branch_audit.csv`, `file_archive_inventory.csv`, `direct_nonbeam_entries.csv`, `external_record_inventory.csv`, `external_text_hits.csv`, and `prior_proxy_head_to_head_benchmark.csv`.

# Study report: S00a - sorted hrdMax vs raw HRDv selection semantics

- **Study ID:** S00a
- **Author (worker label):** testbeam-laptop-2
- **Date:** 2026-06-09
- **Depends on:** S00, S01b selected-table reproduction
- **Input checksum(s):** `input_sha256.csv` records all raw B ROOT and sorted-B ROOT files used.
- **Git commit:** `696daf4c4b7df48eae2ff23b7f6a08be4e0dcc1b`
- **Config:** S00 run/stave/cut definitions from `configs/s00_reproduction.yaml`; report-local executable is `run_s00a_analysis.py`.

## 0. Question
Why do even-channel sorted `hrdMax` counts exceed the raw `HRDv` S00 gate counts, and can downstream workers safely use a sorted branch as a count proxy?

Atomic steps:
- Reproduce the S00 raw gate count from raw `HRDv`: physical B channels 0, 2, 4, 6 and `max(HRDv) - median(samples 0..3) > 1000 ADC`.
- Compare it with naive sorted `hrdMax > 1000` on the same runs/events/channels.
- Test the deterministic correction implied by sorted waveform semantics: `hrdMax - median(sorted hrd samples 0..3) > 1000`.
- Benchmark that correction against a run-split calibrated ML classifier trained from sorted summary features.

## 1. Reproduction
The raw S00 gate reproduces the existing S00 total exactly.

| Quantity | Report value | Reproduced | delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| Raw S00 B-stave selected pulse records | 640,737 | 640,737 | 0 | 0 | yes |
| Naive sorted even-channel `hrdMax > 1000` | 640,737 | 706,373 | +65,636 | 0 | no |
| Corrected sorted `hrdMax - median(pre4) > 1000` | 640,737 | 640,737 | 0 | 0 | yes |
| Corrected sorted record-level mismatches vs raw gate | 0 | 0 | 0 | 0 | yes |

All raw `EVT` arrays matched sorted `hrdEvtNo` arrays batch-by-batch. The discrepancy is therefore not an event alignment problem. It is a branch-semantics problem: sorted `hrdMax` is effectively measured from the waveform minimum, while S00 raw amplitude is measured from the first-four-sample median baseline.

## 2. Traditional Method
The traditional method is the deterministic raw-gate reconstruction from the sorted waveform:

`A_corrected = hrdMax - median(sorted hrd samples 0..3)`

This uses the same baseline convention as S00 but reads only the sorted waveform representation. It exactly reproduced the raw gate on the full configured B-stack population: 1,096,728 events and 4,386,912 event-channel records. It had zero false positives, zero false negatives, and zero count delta.

There is no fit in this method, so chi2/ndf is not applicable. The full per-run distribution is in `counts_by_run.csv` and plotted in `fig_raw_vs_sorted_counts_by_run.png`.

## 3. ML Method
The ML method is a calibrated logistic classifier that predicts the raw S00 gate label from sorted-file features:

- Features: `hrdMax`, `median(sorted samples 0..3)`, `hrdMaxTS`, `hrdSum`, `hrdTrMax`, and stave index.
- Label: raw `HRDv` S00 gate on the same event/channel.
- Split: held-out runs 57 and 65; all CV splits are grouped by run.
- Hyperparameter scan: `C in {0.01, 0.1, 1.0, 10.0}` with 3-fold run-grouped CV. Best was `C=10.0`.
- Calibration: isotonic calibration on training-only calibration runs, then evaluated on runs 57 and 65.

CV accuracy improved monotonically with C: 0.9141, 0.9590, 0.9822, 0.9916. On held-out runs the calibrated model reached 0.999839 accuracy, but still made 45 mistakes: 16 false positives and 29 false negatives. Its reliability plot is `fig_ml_reliability.png`.

The ML output is only a proxy for the deterministic S00 gate. It is not a physics truth label.

## 4. Head-to-Head Benchmark
Same held-out data, same metric: record-level agreement with raw `HRDv` S00 gate on runs 57 and 65.

| Method | Metric | Value with 95% bootstrap CI | Notes |
|---|---:|---:|---|
| Naive sorted `hrdMax > 1000` | accuracy | 0.985446 [0.985025, 0.985929] | 4,058 false positives; no false negatives |
| Traditional corrected sorted gate | accuracy | 1.000000 [1.000000, 1.000000] | exact raw-gate reproduction |
| ML calibrated logistic | accuracy | 0.999839 [0.999788, 0.999882] | 16 false positives, 29 false negatives |

Verdict: ML does not beat the strong deterministic baseline. The right downstream rule is not to train a classifier; it is to use the corrected amplitude definition or read the S00 selected table.

## 5. Falsification
- **Pre-registration:** the decisive metric is corrected sorted gate count delta and record-level mismatch count versus the raw `HRDv` S00 gate. Tolerance is exactly zero.
- **Falsification test:** any nonzero corrected mismatch, any raw total other than 640,737, or any raw/sorted event-order mismatch would falsify the claim.
- **Result:** zero corrected mismatches and zero count delta. This is a full-population equality check, not a sampled significance test; no p-value is needed. Number of attempted deterministic corrections: 1.

## 6. Threats to Validity
- **Benchmark/selection:** the baseline is the exact algebraic correction implied by the two waveform definitions, not a weak cut. ML is compared against that baseline on the same held-out records.
- **Data leakage:** ML splits by run. The traditional result is deterministic and does not learn from labels. The ML feature `median(sorted samples 0..3)` is intentionally included because it is available in the sorted waveform and tests whether a model can learn the known correction; it is not used to claim superiority.
- **Metric misuse:** the metric is raw-gate agreement, which is the ticket's question. Timing or resolution metrics are not relevant here. Per-run full counts are reported rather than only an aggregate.
- **Post-hoc selection:** the cut is fixed by S00 at 1000 ADC. The only tested correction is the baseline-convention correction found before the full result scan.

## 7. Provenance Manifest
`manifest.json` records the command, random seed, input file checksums, and output hashes. The report-local command regenerates every artifact:

```bash
python reports/1780997954.15097.28a25ecb__s00a_sorted_hrdmax_semantics/run_s00a_analysis.py
```

## 8. Findings & Next Steps
The sorted `hrdMax` branch is not a safe count proxy for the S00 raw gate. It overcounts by 65,636 records because its baseline is the waveform minimum rather than S00's pre-trigger median. The corrected sorted waveform gate exactly reproduces S00, so downstream studies can use sorted waveforms safely only when they preserve this baseline convention.

This agrees with the rolling S00/S01b summary: the raw-ROOT selected table remains the source of truth. The new result explains why a tempting sorted-file shortcut silently overcounts.

Hypothesis: any downstream shape or q-template result that used naive `hrdMax` near threshold has an inflated low-amplitude selected population. The highest-information follow-ups are:
- `S00b`: add an integrator regression that rejects sorted `hrdMax` as a raw-gate proxy, preventing future count drift.
- `S01c`: compute q_template using the corrected sorted-waveform amplitude semantics and compare against the S00 selected table, testing whether the semantic correction is enough for shape-quality work.

## 9. Reproducibility
Artifacts written:

- `REPORT.md`
- `run_s00a_analysis.py`
- `counts_by_run.csv`
- `input_sha256.csv`
- `ml_sample.csv.gz`
- `ml_cv_scan.csv`
- `ml_benchmark.csv`
- `ml_reliability.csv`
- `fig_raw_vs_sorted_counts_by_run.png`
- `fig_ml_reliability.png`
- `result.json`
- `manifest.json`


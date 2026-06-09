# Study report: S00c - raw selector-count CI regression

- **Study ID:** S00c
- **Ticket:** 1781013145.1122.4ccc6db4
- **Author (worker label):** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv` records all raw B-stack ROOT files used.
- **Config:** `configs/s00c_1781013145_1122_4ccc6db4.json`
- **Executable:** `scripts/s00c_raw_selector_count_ci_regression.py`

## 0. Question
Can a lightweight raw-ROOT regression guard the S00 B-stave selector semantics by recomputing both selector counts directly from `HRDv`?

The fixed anchors are:

- `median_first_four_selected = 640737`
- `dynamic_range_selected = 706373`
- `dynamic_only = 65636`
- `median_only = 0`

## 1. Reproduction
The script first scans raw B-stack ROOT files only, before any modeling. Physical B staves are channels 0, 2, 4, and 6. The S00 selector is `max(HRDv) - median(samples 0..3) > 1000 ADC`; the semantic-change comparator is `max(HRDv) - min(HRDv) > 1000 ADC`.

| quantity                   |   expected |   reproduced |   delta |   tolerance | pass   |
|:---------------------------|-----------:|-------------:|--------:|------------:|:-------|
| median_first_four_selected |     640737 |       640737 |       0 |           0 | yes    |
| dynamic_range_selected     |     706373 |       706373 |       0 |           0 | yes    |
| dynamic_only               |      65636 |        65636 |       0 |           0 | yes    |
| median_only                |          0 |            0 |       0 |           0 | yes    |

Any nonzero delta exits the script with a failed assertion, making this usable as a CI regression.

## 2. Traditional Method
The traditional method is the explicit S00 median-first-four gate. It is deterministic, full-population, and exactly reproduces the 640737 selected-record anchor. The dynamic-range selector is included as a strong comparator because it is the known accidental semantic drift: it admits 65636 extra records and has zero median-only losses.

Run-held-out bootstrap intervals below resample whole runs and describe count stability, not anchor tolerance:

| quantity                   |   observed_total |   run_bootstrap_ci_low |   run_bootstrap_ci_high |
|:---------------------------|-----------------:|-----------------------:|------------------------:|
| median_first_four_selected |           640737 |               526512   |                762928   |
| dynamic_range_selected     |           706373 |               591330   |                829247   |
| dynamic_only               |            65636 |                52951.6 |                 79561.6 |
| median_only                |                0 |                    0   |                     0   |

## 3. ML Method
The ML method is a logistic classifier trained to predict the median-first-four selector from raw waveform summaries. The split is by run, with runs 57, 65 held out. Cross-validation on training runs is grouped by run.

| method                              |   accuracy |   accuracy_ci_low |   accuracy_ci_high |   false_positive |   false_negative | notes                                                   |
|:------------------------------------|-----------:|------------------:|-------------------:|-----------------:|-----------------:|:--------------------------------------------------------|
| traditional median-first-four gate  |   1        |          1        |           1        |                0 |                0 | deterministic raw selector definition                   |
| dynamic-range selector              |   0.985446 |          0.984998 |           0.985866 |             4058 |                0 | intentional semantic-change comparator                  |
| ML logistic honest raw summaries    |   0.99773  |          0.99754  |           0.997898 |              554 |               79 | run-group CV selected C=10.0                            |
| ML leakage sentinel with median_amp |   0.999788 |          0.999731 |           0.999839 |               59 |                0 | contains a direct monotone transform of the target rule |

The honest ML model uses raw summaries but does not receive `median_amp`. A separate leakage sentinel deliberately includes `median_amp`; its near-perfect behavior is treated as evidence that direct selector-rule features are leakage for any claimed ML generalization. The deterministic traditional gate remains the CI guardrail.

## 4. Leakage and Failure Checks
- Splits are by run for ML CV and held-out testing.
- The regression does not rely on ML to pass; it fails only on exact raw count deltas.
- The leakage sentinel verifies that a model can look too good if it is handed the selector formula as a feature.
- The dynamic-range comparator is the semantic-change alarm: it reproduces the documented overcount, not the accepted S00 selector.

## 5. Reproducibility
Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python scripts/s00c_raw_selector_count_ci_regression.py
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `reproduction_match_table.csv`, `run_bootstrap_ci.csv`, `ml_sample.csv.gz`, `ml_cv_scan.csv`, and `heldout_benchmark.csv`.

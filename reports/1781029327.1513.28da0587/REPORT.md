# Study report: S00c - raw ROOT selector-count CI gate

- **Study ID:** S00c
- **Ticket:** 1781029327.1513.28da0587
- **Worker:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Config:** `configs/s00c_1781029327_1513_28da0587.json`
- **Executable:** `scripts/s00c_1781029327_1513_28da0587_raw_selector_ci.py`

## Question
Add a raw-ROOT regression gate that recomputes the B-stack HRD selector counts and fails on accidental selector drift. The gate scans `HRDv` directly before any modeling.

## Reproduction Gate
Physical B staves are channels 0, 2, 4, and 6. The accepted selector is `max(HRDv) - median(samples 0..3) > 1000 ADC`; the dynamic-range comparator is `max(HRDv) - min(HRDv) > 1000 ADC`.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| median_first_four_selected | 640737 | 640737 | 0 | 0 | yes |
| dynamic_range_selected | 706373 | 706373 | 0 | 0 | yes |
| dynamic_only | 65636 | 65636 | 0 | 0 | yes |
| median_only | 0 | 0 | 0 | 0 | yes |

The script exits nonzero if any count has a nonzero delta.

## Traditional Method
The strong traditional method is the deterministic median-first-four selector, with the dynamic-range selector as the semantic-drift comparator. Whole-run bootstrap intervals below describe run-to-run count stability and are not tolerance bands for the gate.

| quantity | observed_total | run_bootstrap_ci_low | run_bootstrap_ci_high |
| --- | --- | --- | --- |
| median_first_four_selected | 640737 | 530586.15 | 764202.325 |
| dynamic_range_selected | 706373 | 584042.125 | 827534.625 |
| dynamic_only | 65636 | 52204.5 | 79250.9 |
| median_only | 0 | 0.0 | 0.0 |

## ML Method
A logistic classifier predicts the median-first-four selector from raw waveform summaries. Training and cross-validation are grouped by run; runs 57, 65 are held out. The accuracy intervals bootstrap held-out runs.

| method | accuracy | accuracy_ci_low | accuracy_ci_high | false_positive | false_negative | notes |
| --- | --- | --- | --- | --- | --- | --- |
| traditional median-first-four gate | 1.0 | 1.0 | 1.0 | 0 | 0 | deterministic raw selector definition |
| dynamic-range selector | 0.9854464336948413 | 0.9763537271448663 | 0.9928495211326255 | 4058 | 0 | intentional semantic-drift comparator |
| ML logistic honest raw summaries | 0.9977262294141275 | 0.9977162710805746 | 0.9977384605549162 | 556 | 78 | run-group CV selected C=10.0 |
| ML leakage sentinel with median_amp | 0.9997884030527343 | 0.9997332396418905 | 0.9998561565017261 | 59 | 0 | contains the direct selector-rule feature |

## Leakage Checks
The honest ML model excludes `median_amp`, run id, and event id. A sentinel model deliberately includes `median_amp`, a direct transform of the selector rule, so too-good performance there is treated as leakage rather than generalization. The regression gate itself never depends on ML; it passes only if exact raw selector counts match.

## Reproducibility
Run:

```bash
/home/billy/anaconda3/bin/python scripts/s00c_1781029327_1513_28da0587_raw_selector_ci.py
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `reproduction_match_table.csv`, `run_bootstrap_ci.csv`, `ml_cv_scan.csv`, `heldout_benchmark.csv`, `heldout_benchmark_by_run.csv`, and `leakage_checks.csv`.

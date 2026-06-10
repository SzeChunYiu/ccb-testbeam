# Study report: S10f - amplitude-binned two-pulse templates

- **Study ID:** S10f
- **Ticket:** `1781013481.902.5d6a5b89`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s10f_1781013481_902_5d6a5b89.json`

## 0. Question

Do amplitude-binned and asymmetric raw-pulse templates reduce the S10d constrained-fit resolvability delay below 60 ns? The metric is the first held-out delay where `abs(median timing bias) < 1 ns` and `abs(median total-area bias) < 0.20`, using run-held-out bootstrap intervals.

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first and passed: `640737` selected B-stave pulses versus `640737` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was rerun from raw ROOT before this benchmark. Reproduced AP values are `[0.982, 0.9719]` for `['S10 low_2nA injection ML AP', 'S10 high_20nA injection ML AP']` with the documented 0.006 absolute tolerance.

The S10b live-time gate was then rerun from raw ROOT. It reproduced `124.79 ns` for measured live10 and `3.05 MHz` for the measured-tau rescaled combined Rmax.

## 2. Methods

Training source runs are `[58, 59, 60, 61, 62]` and held-out source runs are `[63, 65]`. The injected benchmark uses S01-style empirical templates and real residuals derived from raw ROOT pulses; template construction excludes held-out runs.

The traditional method builds train-run-only template candidates by stave, amplitude quantile bin, and late-tail shape class. The two-pulse fit may use different primary and secondary candidates, scans first-pulse timing offsets and fixed separation hypotheses, and solves amplitudes plus baseline by least squares under configured ratio and baseline bounds. It wrote 36 candidates; 0 low-stat bins used a broader fallback.

The ML method is a compact MLP classifier plus MLP regressor trained on the same amplitude-binned overlay benchmark. It sees waveform-shape features and predicts overlap probability, two times, and two amplitudes.

## 3. Resolvability result

S10d's constrained-fit anchor delay was 60.0 ns. The amplitude-binned/asymmetric fit does not reduce the S10d constrained-fit delay below 60 ns in this held-out closure.

| Method | delay ns | bootstrap 95% CI ns | AP | time RMS ns | area bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| amp-binned asymmetric template fit | not stable | [50.0, 60.0] | 0.722 | 17.81 | -0.004 | 0.013 |
| compact ML | not stable | [22.5, 60.0] | 0.880 | 9.28 | -0.018 | 0.277 |

Detailed delay rows are in `resolvability_by_delay.csv`; run-held-out bootstrap intervals are in `resolvability_bootstrap_ci.csv`.

## 4. Held-out runs

| Run | Method | delay ns | positives |
|---:|---|---:|---:|
| 63 | amp_binned_asymmetric_template_fit | not stable | 300 |
| 65 | amp_binned_asymmetric_template_fit | not stable | 300 |
| 63 | compact_mlp_classifier_regressor | not stable | 300 |
| 65 | compact_mlp_classifier_regressor | not stable | 300 |

## 5. Leakage checks

Run splitting is strict, event ids do not overlap, and template source runs exclude held-out runs. A shuffled-label classifier gives held-out AP `0.494`. Too-good sentinels for time RMS < 5 ns or AP > 0.98 recorded 0 flags in `leakage_checks.csv`.

## 6. Threats to validity

This is a data-driven closure on synthetic overlaps from raw-pulse templates and residuals, not a direct measurement of real beam pile-up. It is appropriate for testing whether the richer fit improves the S10d template-like closure metric; it does not prove performance on all high-current pathologies.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s10f_1781013481_902_5d6a5b89_amp_binned_resolvability.py --config configs/s10f_1781013481_902_5d6a5b89.json
```

Runtime in this run was `169.56` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, delay tables, held-out metrics, leakage checks, and figures.

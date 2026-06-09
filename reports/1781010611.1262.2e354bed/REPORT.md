# Study report: S11c - amplitude-binned asymmetric two-pulse templates

- **Study ID:** S11c
- **Ticket:** `1781010611.1262.2e354bed`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s11c_amp_binned_asymmetric_templates.json`

## 0. Question

Can amplitude-binned, late-tail/asymmetric S01 template libraries plus a wider constrained scan close the S11a gap between the traditional two-pulse fit and the compact ML recovery model?

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first. It passed exactly: `640737` selected B-stave pulses versus `640737` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was also rerun from raw ROOT before the new benchmark. Reproduced AP values are `[0.982, 0.9719]` for `['S10 low_2nA injection ML AP', 'S10 high_20nA injection ML AP']` with the documented 0.006 absolute tolerance.

The S11a head-to-head anchor was then rerun from raw ROOT using the original single-template traditional fit and identical injection seed. It reproduced traditional time RMS **13.30 ns** and ML time RMS **10.67 ns**, versus expected 13.30 ns and 10.67 ns.

## 2. Methods

Injected events use the same S11a empirical template generator and random seed where possible, plus real single-pulse residuals from the source run/stave. Training runs are `[58, 59, 60, 61, 62]`; held-out runs are `[63, 65]`.

The S11c traditional method builds train-run-only templates by stave, three amplitude quantile bins, and three late-tail shape classes (`fast_tail`, `balanced`, `slow_tail`). The two-pulse fit may assign different primary and secondary templates, scans first-pulse timing offsets from -1.75 to 1.25 samples, scans separations from 0.25 to 7.0 samples, and solves amplitudes plus baseline by least squares under the configured ratio and baseline bounds. It wrote 36 template candidates; 0 low-stat bins used a broader fallback.

The ML method is a compact MLP classifier plus MLP regressor trained on the same injected mixtures. It sees only waveform-shape features and predicts overlap probability, two times, and two amplitudes.

## 3. Head-to-head held-out result

| Method | AP | time RMS ns | charge bias | charge res68 | failure rate |
|---|---:|---:|---:|---:|---:|
| amp-binned asymmetric template fit | 0.715 | 17.83 [17.28, 18.37] | 0.006 | 0.120 | 0.017 |
| compact ML | 0.851 | 10.67 [10.16, 11.14] | -0.014 | 0.078 | 0.295 |

The richer traditional fit does not close the ML recovery gap and is worse than the S11a traditional anchor on the primary held-out time-RMS metric. CIs in `head_to_head_overall.csv` are held-out run bootstraps.

## 4. Held-out runs

| Run | Method | AP | time RMS ns | charge res68 | failure rate |
|---:|---|---:|---:|---:|---:|
| 63 | amp_binned_asymmetric_template_fit | 0.729 | 18.37 | 0.125 | 0.023 |
| 63 | compact_mlp_classifier_regressor | 0.837 | 11.14 | 0.073 | 0.277 |
| 65 | amp_binned_asymmetric_template_fit | 0.705 | 17.28 | 0.116 | 0.010 |
| 65 | compact_mlp_classifier_regressor | 0.866 | 10.16 | 0.076 | 0.313 |

## 5. Separation and ratio dependence

Performance degrades sharply below about 10 ns separation. The detailed held-out breakdowns are in `metrics_by_separation.csv` and `metrics_by_ratio.csv`, with figures `fig_time_rms_by_separation.png` and `fig_charge_res68_by_ratio.png`.

## 6. Leakage checks

Run splitting is strict: no source run appears in both train and held-out sets, and event ids do not overlap. A shuffled-label classifier gives held-out AP `0.521`. Too-good sentinels for time RMS < 5 ns or AP > 0.98 did not flag if the leakage flag count is zero; observed leakage flags: **0**. Full checks are in `leakage_checks.csv`.

## 7. Threats to validity

The injections are data-driven but still synthetic: both methods are evaluated on pulses generated from the same empirical template family. Real beam pile-up can include pathology, saturation, and topology effects not represented by this closure test. The strongest claim supported here is therefore method ranking for template-like overlapping pulses, not a final beam pile-up decomposition.

## 8. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s11c_amp_binned_asymmetric_templates.py --config configs/s11c_amp_binned_asymmetric_templates.json
```

Runtime in this run was `84.73` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, metrics tables, leakage checks, and three figures.

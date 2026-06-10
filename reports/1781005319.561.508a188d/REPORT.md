# Study report: S11a - constrained two-pulse template-fit injection benchmark

- **Study ID:** S11a
- **Ticket:** `1781005319.561.508a188d`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s11a_two_pulse_template_ml.json`

## 0. Question

On injected overlapping pulses built from S01-style empirical B-stack templates, when does a constrained two-pulse template fit recover constituent time and charge better than a compact injection-trained ML pile-up classifier/regressor?

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first. It passed exactly: `640737` selected B-stave pulses versus `640737` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was also rerun from raw ROOT before the new benchmark. Reproduced AP values are `[0.982, 0.9719]` for `['S10 low_2nA injection ML AP', 'S10 high_20nA injection ML AP']` with the documented 0.006 absolute tolerance.

## 2. Methods

Templates are median S01-style empirical pulse shapes built from run-held-out training pulses only. Injected events use the same template library plus real single-pulse residuals from the source run/stave. Training runs are `[58, 59, 60, 61, 62]`; held-out runs are `[63, 65]`.

The traditional method is a bounded two-pulse template fit. It uses the S02 CFD20 timing initialization, scans first-pulse timing offsets and fixed separation hypotheses, solves amplitudes plus baseline by least squares, and counts constrained-fit failures. Its overlap score is the fractional SSE improvement over a one-pulse fit.

The ML method is a compact MLP classifier plus MLP regressor trained on the same injected mixtures. It sees only waveform-shape features and predicts overlap probability, two times, and two amplitudes.

## 3. Head-to-head held-out result

| Method | AP | time RMS ns | charge bias | charge res68 | failure rate |
|---|---:|---:|---:|---:|---:|
| constrained template fit | 0.767 | 13.30 [12.00, 14.56] | -0.022 | 0.098 | 0.168 |
| compact ML | 0.851 | 10.67 [9.62, 11.84] | -0.014 | 0.078 | 0.295 |

The compact ML method has the lower held-out constituent-time RMS, higher overlap AP, and lower charge spread on the primary aggregate metric. The constrained template fit has the lower failure rate and remains competitive in the easier high-ratio and larger-separation bins, but it does not beat ML overall in this closure. Bootstrap CIs are in `head_to_head_overall.csv`.

## 4. Separation and ratio dependence

Performance degrades sharply below about 10 ns separation. The detailed held-out breakdowns are in `metrics_by_separation.csv` and `metrics_by_ratio.csv`, with figures `fig_time_rms_by_separation.png` and `fig_charge_res68_by_ratio.png`.

## 5. Leakage checks

Run splitting is strict: no source run appears in both train and held-out sets. Event ids are generated per split and have no overlap. A shuffled-label classifier gives held-out AP `0.521`, recorded in `leakage_checks.csv`; this is consistent with no obvious label leakage.

## 6. Threats to validity

The injections are data-driven but still synthetic: both methods are evaluated on pulses generated from the same empirical template family. Real beam pile-up can include pathology, saturation, and topology effects not represented by this closure test. The strongest claim supported here is therefore method ranking for template-like overlapping pulses, not a final beam pile-up decomposition.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s11a_two_pulse_template_ml.py --config configs/s11a_two_pulse_template_ml.json
```

Runtime in this run was `28.76` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, metrics tables, leakage checks, and three figures.

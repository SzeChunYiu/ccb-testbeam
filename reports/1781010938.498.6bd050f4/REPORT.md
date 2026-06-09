# Study report: P05a - CNN two-pulse decomposition against S11a injections

- **Study ID:** P05a
- **Ticket:** `1781010938.498.6bd050f4`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/p05a_cnn_two_pulse_decomposition.json`

## 0. Question

After S11a showed a compact MLP could beat the bounded two-pulse fit on injected overlaps with a higher failure rate, can a compact 18-sample CNN decomposition head recover both constituent times and charges more stably across separation and amplitude ratio?

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first. It passed exactly: `640737` selected B-stave pulses versus `640737` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was also rerun from raw ROOT before the new benchmark. Reproduced AP values are `[0.982, 0.9719]` for `['S10 low_2nA injection ML AP', 'S10 high_20nA injection ML AP']` with the documented 0.006 absolute tolerance.

The S11a injected benchmark was reproduced on this raw-ROOT-derived sample before the CNN swap. The frozen template fit gives time RMS `13.90 ns`, AP `0.753`, and failure rate `0.168`; the S11a compact MLP gives time RMS `9.31 ns`, AP `0.839`, and failure rate `0.273`. These reproduce the S11a qualitative number: the MLP is faster in RMS but fails more often.

## 2. Methods

Templates are median S01-style empirical pulse shapes built from run-held-out training pulses only. Injected events use the same template library plus real single-pulse residuals from the source run/stave. Training runs are `[58, 59, 60, 61, 62]`; held-out runs are `[63, 65]`.

The traditional method is the frozen S11a bounded two-pulse template fit. It uses the S02 CFD20 timing initialization, scans first-pulse timing offsets and fixed separation hypotheses, solves amplitudes plus baseline by least squares, and counts constrained-fit failures. The scan has `81` hypotheses per event.

The ML method is a compact PyTorch 1D CNN over the 18 normalized waveform samples. It has two convolution layers, a shared dense layer, a detection head, and four decomposition outputs for `t1`, `t2`, `amp1/max_amp`, and `amp2/max_amp`. It is trained only on injected train runs.

## 3. Head-to-head held-out result

| Method | AP | time RMS ns | charge bias | charge res68 | failure rate |
|---|---:|---:|---:|---:|---:|
| constrained template fit | 0.753 | 13.90 [13.74, 14.05] | -0.026 | 0.092 | 0.168 |
| compact 18-sample CNN | 0.868 | 10.01 [9.88, 10.14] | 0.011 | 0.080 | 0.228 |

The CNN lowers the primary constituent-time RMS relative to the frozen bounded fit, but its failure-rate CI is clearly worse, so it does not satisfy the preregistered win condition. Bootstrap intervals are paired run-block intervals over held-out source runs and are in `head_to_head_overall.csv`.

## 4. Separation and ratio dependence

Performance degrades sharply below about 10 ns separation. The detailed held-out breakdowns are in `metrics_by_separation.csv` and `metrics_by_ratio.csv`, with figures `fig_time_rms_by_separation.png` and `fig_charge_res68_by_ratio.png`.

## 5. Leakage checks

Run splitting is strict: no source run appears in both train and held-out sets. Event ids are generated per split and have no overlap. A shuffled-label CNN gives held-out AP `0.471`. The source-run predictability sentinel has train-random-split accuracy `0.207`. The source-run sentinel does not flag strong run-identifying waveform leakage.

## 6. Threats to validity

The injections are data-driven but still synthetic: both methods are evaluated on pulses generated from the same empirical template family. Real beam pile-up can include pathology, saturation, and topology effects not represented by this closure test. The strongest claim supported here is method ranking for template-like overlapping pulses, not a final beam pile-up decomposition.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p05a_cnn_two_pulse_decomposition.py --config configs/p05a_cnn_two_pulse_decomposition.json
```

Runtime in this run was `46.34` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, S11a reproduction tables, metrics tables, leakage checks, and three figures.

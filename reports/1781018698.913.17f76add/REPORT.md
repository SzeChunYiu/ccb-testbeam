# Study report: P05b - CNN threshold utility curves

- **Study ID:** P05b
- **Ticket:** `1781018698.913.17f76add`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-10
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/p05b_1781018698_913_17f76add_threshold_utility.json`

## 0. Question

Follow up P05a by scanning the compact CNN overlap threshold versus true separation and secondary/primary amplitude ratio. The target is an operational utility curve for constituent time RMS versus failure rate, without hiding the failure-rate regression seen in P05a.

## 1. Reproduction gate

The raw `HRDv` count gate was run first from `data/root/root`. It reproduced `640737` selected B-stave pulses versus `640737` reported, with zero tolerance. The S10 raw-ROOT injection AP handle also passed with reproduced AP values `[0.982, 0.9719]`.

The same P05a/S11a injected benchmark was rebuilt with train runs `[58, 59, 60, 61, 62]` and held-out runs `[63, 65]`. At the P05a fixed 0.5 CNN threshold, the frozen template fit has held-out time RMS `13.90 ns` and failure rate `0.168`; the compact CNN has time RMS `10.01 ns` and failure rate `0.228`.

## 2. Methods

The traditional reference is the frozen bounded S01-style two-pulse template fit, scanned by its fractional SSE-improvement score. The ML method is the P05a compact 18-sample CNN, scanned by overlap probability. For each threshold, true overlaps below threshold are counted as failures; RMS and charge summaries are computed only on accepted true overlaps.

The displayed operating points are chosen on train runs only: minimize train RMS among thresholds with train failure rate <= `0.25`. Held-out uncertainty is a paired source-run bootstrap over runs 63 and 65. Full curves are in `threshold_utility_heldout.csv`, `threshold_utility_by_separation.csv`, and `threshold_utility_by_ratio.csv`.

## 3. Train-selected held-out operating points

| Method | threshold | held-out failure | held-out time RMS ns | charge bias | charge res68 |
|---|---:|---:|---:|---:|---:|
| bounded template score | -0.10 | 0.183 [0.183, 0.183] | 13.61 [13.56, 13.65] | -0.024 | 0.092 |
| compact CNN probability | 0.25 | 0.100 [0.100, 0.100] | 10.07 [10.06, 10.08] | 0.005 | 0.081 |

The train-selected CNN threshold is the better operating point on this closure: it lowers held-out RMS and failure rate relative to the scanned template-score threshold. The lowest held-out CNN RMS anywhere on the scanned curve is `8.96 ns` at threshold `0.95`, with failure rate `0.717`; this is post-hoc and is not the recommended operating point.

## 4. Separation and ratio dependence

The CNN threshold buys lower RMS mostly at larger separations. Below 10 ns true separation, failure rates rise rapidly as threshold tightens. Ratio scans show the same tradeoff: low secondary/primary ratios are the first to be rejected, which can improve accepted RMS while reducing usable overlap corrections.

## 5. Leakage checks

Run splitting is strict and event IDs do not overlap. The train-selected operating threshold does not use held-out labels. The P05a leakage battery was rerun; all checks pass: `True`. Details are in `leakage_checks.csv`.

## 6. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p05b_1781018698_913_17f76add_threshold_utility.py --config configs/p05b_1781018698_913_17f76add_threshold_utility.json
```

Runtime in this run was `141.22` s.

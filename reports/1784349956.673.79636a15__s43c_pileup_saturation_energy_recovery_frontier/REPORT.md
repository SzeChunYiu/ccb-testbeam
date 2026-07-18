# S43c: Pileup Saturation Energy Recovery Frontier

This ticket-scoped report mirrors the top-level `REPORT.md` for ticket `1784349956.673.79636a15`.

## Winner

The held-out winner is **`saturation_residual_fusion_new`**, selected by the registered composite score.  Energy residual sigma68 is `0.07110` with 95% run-block bootstrap CI `[0.05945, 0.07903]`; pile-up separation sigma68 is `10.56 ns` with CI `[9.613, 11.21]`.

## Raw ROOT Gate

Raw B-stack ROOT files from `data/root/root/hrdb_run_*.root` reproduced the selected-pulse anchor exactly: `640737` selected B-stave pulse records versus reference `640737`, delta `0`.  Sample-II analysis subcounts also matched exactly: B2 `88213`, B4 `21229`, B6 `11148`, B8 `4506`.

## Methods

The benchmark used run-disjoint splits: train runs `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs `[58, 60, 62, 64, 65]`.  The method panel covered the required traditional clipped-template comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, a tiny sequence transformer, and the new `saturation_residual_fusion_new` hybrid.

The primary residual was `e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.  Pile-up separation error was `e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`.  Robust resolution used `sigma68(e) = [Q84(e) - Q16(e)] / 2`.  CIs were percentile intervals from 400 held-out run-block bootstrap resamples.

## Ranking

| method | score | sigma68_E | sigma68_E CI | sigma68_Delta ns | miss | false |
|---|---:|---:|---|---:|---:|---:|
| saturation_residual_fusion_new | 0.1771 | 0.07110 | [0.05945, 0.07903] | 10.56 | 0.300 | 0.195 |
| gradient_boosted_trees | 0.1795 | 0.07109 | [0.05751, 0.07866] | 11.40 | 0.278 | 0.195 |
| ridge | 0.1803 | 0.06797 | [0.06179, 0.07188] | 13.15 | 0.263 | 0.198 |
| 1d_cnn | 0.2366 | 0.09933 | [0.08196, 0.1088] | 15.17 | 0.278 | 0.256 |
| analytic_clipped_template_sideband_traditional | 0.2444 | 0.08542 | [0.06603, 0.09771] | 15.00 | 0.585 | 0.183 |
| mlp | 0.2665 | 0.1237 | [0.1112, 0.1355] | 15.22 | 0.322 | 0.202 |
| tiny_sequence_transformer | 0.3029 | 0.08253 | [0.07244, 0.0940] | 25.48 | 0.412 | 0.149 |

## Systematics, Hand Scan, And Ablations

The local generated artifact bundle contains the detailed run-held-out table, stratum scan, failure-mode hand-scan ledger, and ablation metrics.  The hand scan prioritized missed close doublets, timing-swap or spacing errors, large energy residuals, and shifted-pedestal late-tail cases.  The fusion architecture was retrained with all inputs, without pedestal-subtraction information, and without clipped-tail-window features; this tests whether the winner relies on the ticket-requested sideband information.

## Caveats

Truth labels come from controlled injections into raw-ROOT-derived clean pulses.  The ADC ceiling is a benchmark stressor, not decoded electronics metadata.  PID dependence is represented by stave and charge-support proxies.  Bootstrap CIs quantify transfer across held-out runs, not asymptotic event-counting uncertainty.

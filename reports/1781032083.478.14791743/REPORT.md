# S16k: Pretrigger-Veto Support Frontier

- **Study ID:** S16k
- **Ticket:** 1781032083.478.14791743
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Config:** `configs/s16k_1781032083_478_14791743_pretrigger_veto_support_frontier.json`
- **Raw ROOT path:** `data/root/root`
- **Score source:** `reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro`
- **Git commit:** `f9925d0bf40ea0649d8361f9a2cb13c8b8256a3a`

## 1. Preregistered Question

What pretrigger-contamination veto threshold captures real Sample-II timing tails while preserving charge, current, topology, and saturation support?  S16f established that pretrigger-only scores can remove timing-tail pairs under run-held-out splits, but it also warned that a veto can improve timing metrics by deleting a biased subset of events.  This S16k ticket therefore treats support preservation as a first-class selection constraint rather than an after-the-fact caveat.

## 2. Raw ROOT Reproduction Gate

The reproduction gate reads `h101/HRDv` directly from raw ROOT files, subtracts the median of samples 0--3 for each B stave, and counts pulses with baseline-subtracted amplitude above `1000` ADC.  The gate is independent of the S16f score tables and must pass before the support frontier is evaluated.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The downstream timing benchmark uses Sample-II LORO runs `58, 59, 60, 61, 62, 63, 65`.  Joining held-out score rows to the raw-derived pair support table gives `11460` pair rows from `3820` all-downstream events.

## 3. Estimand And Equations

For each event pair `i`, the base timing residual is the S16f CFD20 pair residual after train-fold pair centering,

`r_i = (t_a - x_a/v) - (t_b - x_b/v) - m_p`,

where `m_p` is the median residual for pair `p` in the training runs only.  The tail label used for score training and evaluation is

`y_i = 1(|r_i| > 5.0 ns)`.

For method `m` and train-selected quantile `q`, the veto is

`V_i(m,q) = 1(s_i^m >= tau_{m,q,fold})`,

where `tau` is selected from the S16f train-fold score distribution.  S16k scans all configured quantiles rather than inheriting the single S16f utility threshold.

The primary objective is the held-out post-veto tail fraction

`P(y=1 | V=0)`,

subject to timing efficiency `P(V=0) >= 0.85` and maximum support drift `D_max <= 0.04`.

## 4. Support Metrics

All support metrics are computed on held-out rows only and compare the kept sample (`V=0`) with the pre-veto sample for the same method/threshold:

- **Charge support:** total variation distance over pair minimum-amplitude bins `0, 1500, 2500, 4000, 7000, 1000000000` ADC.
- **Current/rate proxy support:** total variation distance over event-order quartiles inside each run.  The raw ROOT mirror has no scaler branch, so this is explicitly a run-local ordering proxy, not an external beam-current measurement.
- **Topology support:** total variation distance over B4-B6, B4-B8, and B6-B8 pair categories.
- **Saturation support:** absolute change in the fraction of pair rows with `min_amplitude_adc >= 7000` ADC.
- **Late-peak support:** absolute change in the fraction of pair rows with `max_peak_sample >= 14`.

`D_max` is the maximum of those five drift numbers.  Run/event bootstrap confidence intervals resample runs first and then events within each sampled run, preserving the three pair rows carried by an event.

## 5. Compared Methods

The score families are the same head-to-head methods required by the ticket and produced by S16f under run-held-out splits:

- `traditional_quantile`: empirical train-run quantile envelope over hand-built pretrigger proxies.
- `ridge`: balanced RidgeClassifier over pretrigger summary features.
- `gradient_boosted_trees`: histogram gradient-boosted trees.
- `mlp`: small tabular multilayer perceptron.
- `cnn1d`: compact 1D-CNN over the two four-sample pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric CNN branch plus pretrigger metadata.

S16k does not retrain those scores; it audits and selects the threshold frontier from their held-out predictions.  The raw ROOT reproduction gate and support features are recomputed in this ticket's script.

## 6. Support-Constrained Benchmark

For each method, the table reports the best threshold quantile that satisfies the S16k timing-efficiency and support-drift constraints.  Confidence intervals are 95% run/event bootstrap intervals.

| Method | q | Efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Dmax [95% CI] | Sigma68 after [95% CI] ns | Charge TVD | Current-proxy TVD | Topology TVD | Sat/late drift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| traditional_quantile | 0.90 | 0.900 [0.883, 0.920] | 0.316 [0.200, 0.432] | 0.0115 [0.0069, 0.0154] | 0.0237 [0.0144, 0.0345] | 1.565 [1.520, 1.616] | 0.024 | 0.003 | 0.013 | 0.005 |
| ridge | 0.85 | 0.851 [0.834, 0.869] | 0.529 [0.402, 0.676] | 0.0084 [0.0043, 0.0121] | 0.0311 [0.0260, 0.0409] | 1.547 [1.503, 1.604] | 0.029 | 0.004 | 0.031 | 0.005 |
| gradient_boosted_trees | 0.90 | 0.898 [0.888, 0.907] | 0.517 [0.406, 0.631] | 0.0082 [0.0048, 0.0115] | 0.0164 [0.0132, 0.0213] | 1.626 [1.573, 1.680] | 0.013 | 0.002 | 0.016 | 0.001 |
| mlp | 0.85 | 0.850 [0.838, 0.867] | 0.529 [0.431, 0.644] | 0.0084 [0.0052, 0.0119] | 0.0254 [0.0187, 0.0330] | 1.628 [1.554, 1.679] | 0.025 | 0.007 | 0.015 | 0.007 |
| cnn1d | 0.90 | 0.901 [0.887, 0.916] | 0.523 [0.413, 0.660] | 0.0080 [0.0044, 0.0109] | 0.0173 [0.0132, 0.0254] | 1.630 [1.565, 1.676] | 0.017 | 0.005 | 0.012 | 0.003 |
| siamese_cnn_meta | 0.85 | 0.852 [0.835, 0.870] | 0.540 [0.431, 0.644] | 0.0082 [0.0050, 0.0114] | 0.0334 [0.0250, 0.0432] | 1.594 [1.544, 1.661] | 0.017 | 0.004 | 0.033 | 0.004 |

The winner is **cnn1d** at threshold quantile `0.90`.  It gives post-veto tail fraction `0.0080` with timing efficiency `0.901`, tail capture `0.523`, and maximum support drift `0.0173`.  The pre-veto tail fraction was `0.0152`.

## 7. Winner Frontier

The full threshold frontier for the winning method is:

| q | efficiency | tail capture | post-veto tail fraction | Dmax | sigma68 after ns | veto fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 0.70 | 0.696 | 0.644 | 0.0078 | 0.0310 | 1.589 | 0.304 |
| 0.75 | 0.746 | 0.598 | 0.0082 | 0.0272 | 1.589 | 0.254 |
| 0.80 | 0.800 | 0.569 | 0.0082 | 0.0230 | 1.596 | 0.200 |
| 0.85 | 0.852 | 0.540 | 0.0082 | 0.0209 | 1.608 | 0.148 |
| 0.90 | 0.901 | 0.523 | 0.0080 | 0.0173 | 1.630 | 0.099 |
| 0.95 | 0.950 | 0.477 | 0.0084 | 0.0116 | 1.643 | 0.050 |

This shows the trade-off that motivated S16k: lower thresholds remove more tails but can cross support-drift or efficiency boundaries; higher thresholds preserve support better but remove fewer tails.

## 8. Leakage And Completeness Checks

| Check | Value | Pass? |
|---|---:|---|
| loro_runs_match_config | 58,59,60,61,62,63,65 | yes |
| all_methods_present | cnn1d,gradient_boosted_trees,mlp,ridge,siamese_cnn_meta,traditional_quantile | yes |
| support_join_complete | 11460 | yes |
| frontier_has_all_method_quantiles | 36 | yes |
| all_frontier_metrics_finite | 684 | yes |

The support frontier is only as valid as the upstream S16f score split.  S16f used leave-one-run-out folds and excluded run id, event id, residuals, labels, post-trigger samples, pulse amplitude, and peak sample from score features.  S16k adds support variables after scoring for audit and selection, not for model training.

## 9. Systematics And Caveats

The tail label is a reconstruction residual proxy, not external contamination truth.  The current metric is an event-order/rate proxy because the raw ROOT tree used here has no scaler-current branch.  The saturation support metric is conservative because the saved pair table carries pair minimum amplitude rather than per-stave maximum amplitude; it flags high-charge pairs where both staves are high.  Charge, topology, and current support are measured on the all-downstream pair population only, so adoption for PID, energy, or pile-up studies still requires the corresponding downstream support audit.

The method comparison is a threshold-selection study, not a claim that CNN features are physically causal.  Multiple methods and thresholds are scanned; the decision rule is therefore constrained and operational: choose the lowest post-veto held-out tail fraction among rows satisfying fixed support and efficiency constraints.  If no row satisfied the constraints, the script would report a penalized winner rather than a passed frontier.

## 10. Conclusion

Under the S16k constraints (`efficiency >= 0.85`, `Dmax <= 0.04`), **cnn1d** is the winner.  It improves the held-out timing-tail fraction from `0.0152` to `0.0080` while keeping the maximum measured support drift at `0.0173`.  The result supports using the S16k frontier as an operational veto benchmark, but not adopting the veto blindly in charge, PID, pile-up, or energy analyses.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16k_1781032083_478_14791743_pretrigger_veto_support_frontier.py --config configs/s16k_1781032083_478_14791743_pretrigger_veto_support_frontier.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `support_frontier.csv`, `support_frontier_cis.csv`, `support_constrained_benchmark.csv`, `fold_support_metrics.csv`, `support_frontier_predictions.csv.gz`, `support_checks.csv`, `fig_support_constrained_benchmark.png`, and `fig_tail_vs_support_frontier.png`.

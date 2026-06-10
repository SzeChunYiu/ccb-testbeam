# S16f: Frozen Pre-Trigger Contamination Veto Under Sample-II LORO Timing Splits

- **Study ID:** S16f
- **Ticket:** 1781031083.1784.78066bc6
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction, S02/S02b downstream timing residual definitions, S16 pre-trigger baseline diagnostics
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `9ff8212c79ac901fb5ee8383249ee1efdc472662`
- **Config:** `configs/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.json`

## 0. Question

Can a veto frozen from train-run pre-trigger proxy quantiles remove S02b-style Sample-II downstream timing tails under leave-one-run-out (LORO) splits without sacrificing too much timing efficiency, and do ridge, gradient-boosted trees, MLP, 1D-CNN, or a pair-symmetric CNN+metadata architecture beat the strong traditional quantile veto?

## 1. Reproduction Gate From Raw ROOT

The gate reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root`, subtracts the median of samples 0-3 per B stave, and counts pulses with baseline-subtracted amplitude `A > 1000 ADC`. No sorted ROOT files or cached tables are used for this gate.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The timing-consumer table then requires B4, B6, and B8 all to pass the same amplitude cut in each Sample-II event. This produced `3820` all-downstream events and `11460` pair residuals across LORO runs [58, 59, 60, 61, 62, 63, 65].

## 2. Traditional Method

For event pair \(i\), the base residual is

\[
r_i = (t_a - x_a/v) - (t_b - x_b/v),
\]

where `t` is CFD20 time, `x` is the B-stack position at 2.0 cm spacing, and `1/v = 0.078` ns/cm. For each LORO fold, pair centers \(m_p\) are medians of train-run residuals only. The tail label used for training diagnostics is \(y_i = 1(|r_i-m_{p(i)}| > 5.0 ns)\).

The traditional veto score is a frozen train-run empirical quantile envelope:

\[
s_i^{trad} = \max_j \hat F_{j,train}(z_{ij}),
\]

where \(z_j\) are pre-trigger-only pair proxies: maximum absolute pre-trigger amplitude, peak-to-peak range, RMS, absolute slope, and last-minus-first excursion. The threshold is selected on train runs from quantiles [0.7, 0.75, 0.8, 0.85, 0.9, 0.95], with train timing efficiency constrained to at least 0.85.

## 3. ML And NN Methods

All ML methods use the same LORO folds and exclude run id, event id, residuals, tail labels, post-trigger samples, pulse amplitude, and peak sample. The tabular features are pair identity plus pre-trigger summaries from samples 0-3. The 1D-CNN receives only the two four-sample pre-trigger traces. The new architecture, `siamese_cnn_meta`, applies a shared convolutional branch to each stave's pre-trigger trace, combines both embeddings with their absolute difference, then concatenates the tabular pre-trigger summaries.

Models:

- `ridge`: balanced RidgeClassifier averaged over alpha grid [0.01, 0.1, 1.0, 10.0].
- `gradient_boosted_trees`: HistGradientBoostingClassifier with 60 boosting iterations.
- `mlp`: scikit-learn MLP with hidden layers [24, 12].
- `cnn1d`: compact Conv1d network over the two pre-trigger channels.
- `siamese_cnn_meta`: pair-symmetric Conv1d branch plus pre-trigger metadata.

For each model, the veto threshold is frozen from train-run scores by the same efficiency-constrained utility as the traditional score. Probability calibration is summarized by Brier score in `head_to_head_benchmark.csv`; AUC/AP are auxiliary ranking diagnostics, not the primary physics metric.

## 4. Head-To-Head Benchmark

Primary pre-registered metric: held-out post-veto `|residual| > 5 ns` tail fraction at train-selected support, with sigma68 movement and timing efficiency reported as co-primary safety metrics. CIs resample runs, then events within each sampled run.

| Method | Timing efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Sigma68 after [95% CI] ns | Delta sigma68 [95% CI] ns | AUC | AP |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional_quantile | 0.900 [0.883, 0.920] | 0.316 [0.219, 0.442] | 0.0115 [0.0071, 0.0151] | 1.565 [1.511, 1.613] | -0.126 [-0.149, -0.099] | 0.701 | 0.051 |
| ridge | 0.899 [0.889, 0.915] | 0.489 [0.369, 0.618] | 0.0086 [0.0039, 0.0119] | 1.561 [1.508, 1.600] | -0.130 [-0.155, -0.100] | 0.732 | 0.149 |
| gradient_boosted_trees | 0.898 [0.889, 0.907] | 0.517 [0.370, 0.619] | 0.0082 [0.0056, 0.0112] | 1.626 [1.564, 1.681] | -0.066 [-0.097, -0.051] | 0.745 | 0.248 |
| mlp | 0.899 [0.887, 0.910] | 0.500 [0.386, 0.613] | 0.0084 [0.0044, 0.0119] | 1.641 [1.596, 1.694] | -0.050 [-0.066, -0.029] | 0.742 | 0.290 |
| cnn1d | 0.902 [0.886, 0.919] | 0.523 [0.417, 0.619] | 0.0080 [0.0047, 0.0111] | 1.631 [1.546, 1.686] | -0.061 [-0.094, -0.035] | 0.739 | 0.316 |
| siamese_cnn_meta | 0.903 [0.887, 0.920] | 0.511 [0.424, 0.646] | 0.0082 [0.0044, 0.0118] | 1.607 [1.559, 1.662] | -0.085 [-0.111, -0.060] | 0.742 | 0.302 |

Winner by support-constrained post-veto tail fraction: **cnn1d**. The baseline pre-veto tail fraction was `0.0152`, and baseline sigma68 was `1.691 ns`.

Per-held-out-run metrics for the winner:

| Held-out run | n pairs | efficiency | tail capture | post-veto tail fraction | sigma68 after ns | delta sigma68 ns |
|---:|---:|---:|---:|---:|---:|---:|
| 58 | 219 | 0.950 | 1.000 | 0.0000 | 1.553 | -0.087 |
| 59 | 2289 | 0.924 | 0.611 | 0.0066 | 1.511 | -0.097 |
| 60 | 2424 | 0.880 | 0.436 | 0.0103 | 1.631 | -0.028 |
| 61 | 2799 | 0.904 | 0.526 | 0.0107 | 1.614 | -0.083 |
| 62 | 2421 | 0.892 | 0.522 | 0.0051 | 1.643 | -0.043 |
| 63 | 1110 | 0.909 | 0.471 | 0.0089 | 1.650 | -0.169 |
| 65 | 198 | 0.924 | 0.000 | 0.0000 | 1.583 | +0.019 |

## 5. Falsification

Pre-registration from the ticket: a useful veto must transfer under Sample-II LORO splits, reject S02b timing tails, preserve timing efficiency, and pass shuffled-proxy plus train/held-out leakage guards. The falsification test is the shuffled-proxy control: train each method after permuting train-run pre-trigger proxies relative to labels. A claimed method is rejected if its median tail-capture advantage over the shuffled-proxy version is below -0.05 or if the LORO split leaks event ids.

Multiple methods were tested (`N = 6`). The report therefore does not interpret nominal per-method p-values as discovery claims; the winner is an operational benchmark choice under a fixed metric. Shuffled-proxy deltas and leakage guards are tabulated below.

| Check | Value | Pass? |
|---|---:|---|
| loro_runs_match_config | 58,59,60,61,62,63,65 | yes |
| train_heldout_event_id_overlap_max | 0 | yes |
| features_exclude_run_event_residual_labels |  | yes |
| all_predictions_finite | 137520 | yes |
| one_row_per_method_fold_shuffled_state | 84 | yes |
| cnn1d_actual_tail_capture_ge_shuffled_proxy_median | 0.3913043478260869 | yes |
| gradient_boosted_trees_actual_tail_capture_ge_shuffled_proxy_median | 0.23529411764705885 | yes |
| mlp_actual_tail_capture_ge_shuffled_proxy_median | 0.38596491228070173 | yes |
| ridge_actual_tail_capture_ge_shuffled_proxy_median | 0.2352941176470588 | yes |
| siamese_cnn_meta_actual_tail_capture_ge_shuffled_proxy_median | 0.3055555555555556 | yes |
| traditional_quantile_actual_tail_capture_ge_shuffled_proxy_median | 0.1388888888888889 | yes |

## 6. Threats To Validity

Benchmark/selection: the traditional method is not a strawman; it uses a train-frozen empirical quantile envelope over the most direct pre-trigger contamination proxies and the same threshold utility as ML.

Data leakage: splits are by run. Features explicitly exclude run id, event id, residuals, labels, post-trigger waveform samples, amplitudes, and peak samples. Pair centers, empirical quantiles, scalers, neural normalizers, model fits, and thresholds are all trained inside the current LORO train runs.

Metric misuse: the report gives tail fraction, tail capture, timing efficiency, sigma68, full RMS, and score-ranking diagnostics. Sigma68 can improve simply by deleting hard events, so efficiency is always co-reported.

Post-hoc selection: the metric and threshold rule are fixed in the config before seeing held-out outcomes. The only post-hoc operation is naming the winner by the configured metric after all methods are evaluated.

Systematics and caveats: the label is a timing-tail proxy, not a truth label for contamination. The pre-trigger window has only four samples; CNN capacity is intentionally small. Pair residuals share events, which is why CIs bootstrap events within runs rather than individual pair rows. The method is a veto frontier, not a timing correction, and should not be adopted for charge, PID, or energy studies without a support-drift audit.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Input ROOT checksums are in `input_sha256.csv`; output checksums are in the manifest.

## 8. Findings And Next Steps

The strongest held-out method is **cnn1d**. Its result should be interpreted as a support-constrained pre-trigger veto benchmark: it names which score best removes timing-tail pairs under Sample-II LORO, not which score is physically causal. The shuffled-proxy controls determine whether the apparent tail capture follows real pre-trigger structure rather than a run or threshold artifact.

One natural follow-up is to propagate the winning veto into a charge/current/topology support audit before adoption, because deleting timing-tail events can bias downstream physics samples even when timing sigma68 improves.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py --config configs/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `sample_ii_pair_table.csv.gz`, `fold_metrics.csv`, `heldout_predictions.csv.gz`, `threshold_scans.csv`, `head_to_head_benchmark.csv`, `bootstrap_cis.csv`, `leakage_checks.csv`, `fig_head_to_head_tail_fraction.png`, and `fig_winner_residuals_kept_vetoed.png`.

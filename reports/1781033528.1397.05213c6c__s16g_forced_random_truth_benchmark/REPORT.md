# S16g: Forced/Random HRD Pedestal Truth Acquisition With Proxy Benchmark Fallback

- **Study ID:** S16g
- **Ticket:** 1781033528.1397.05213c6c
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction, S16f pre-trigger veto benchmark, S16g forced/random acquisition audit
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `0d8dacda1922e55413f3cbf9999da1ce40a50b2e`
- **Config:** `configs/s16g_1781033528_1397_05213c6c_forced_random_truth_benchmark.json`

## 0. Question

Can the mounted raw HRD ROOT data support a direct forced/random no-pulse pedestal truth rerun, and, if not, which frozen quiet-vs-beam proxy method is strongest under the same Sample-II leave-one-run-out split?

The decision has two atomic gates: first audit the visible ROOT and archive mirrors for true forced/random events; second benchmark the frozen proxy task with the same run-held-out split and explicitly label it as a fallback rather than direct truth.

## 1. Reproduction (mandatory gate)

The raw-ROOT gate reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root`, subtracts the median of samples 0-3 for B2/B4/B6/B8, and counts baseline-subtracted pulses with \(A>1000\) ADC.  This independently reproduces the S00/S16 selected-pulse count.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The forced/random acquisition gate inspected `110` HRDA/HRDB ROOT files and `438` filesystem/archive rows. It found `0` strict forced/random ROOT/archive candidates, `0` tag-like ROOT branch sets, and `0` B-stack non-beam entries. Thus the direct forced/random truth rerun is **blocked**; in this mounted data state it is not estimable.

## 2. Traditional (non-ML) method

The fallback benchmark uses the S16f quiet-vs-beam proxy target because the direct truth sample is absent. For event pair \(i\),

\[
r_i=(t_a-x_a/v)-(t_b-x_b/v),
\]

where `t` is CFD20 time, `x` is B-stack position at `2.0` cm spacing, and \(1/v=0.078\) ns/cm. In each leave-one-run-out fold, pair centers \(m_p\) are train-run medians and the proxy tail label is

\[
y_i = \mathbf{1}\left(|r_i-m_{p(i)}|>5.0\ \mathrm{ns}\right).
\]

The strong traditional score is a train-frozen empirical quantile envelope over pre-trigger-only summaries:

\[
s_i^{trad}=\max_j \hat F_{j,\mathrm{train}}(z_{ij}),
\]

where \(z_j\) are max absolute pre-trigger amplitude, peak-to-peak range, RMS, absolute slope, and last-minus-first excursion across the two staves. The threshold is selected inside the train runs only from quantiles `[0.7, 0.75, 0.8, 0.85, 0.9, 0.95]`, with train efficiency constrained to at least `0.85`.

## 3. ML method

The benchmark includes ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pair-symmetric architecture (`siamese_cnn_meta`). All methods use Sample-II leave-one-run-out by run. Features exclude run id, event id, residuals, labels, post-trigger waveform samples, amplitude, and peak sample. Scalers, empirical distributions, neural normalizers, model fits, pair centers, and thresholds are fit only on the training runs for each held-out run.

The tabular ML methods receive pair identity and pre-trigger summaries from samples 0-3. The 1D-CNN receives only the two four-sample pre-trigger traces. The new architecture applies a shared convolutional branch separately to the two stave pre-trigger traces, concatenates both embeddings and their absolute difference, then adds the tabular pre-trigger summaries before the binary head. Ridge scans alphas `[0.01, 0.1, 1.0, 10.0]`; the boosted tree, MLP, and NN hyperparameters are fixed in the config before held-out scoring.

## 4. Head-to-head benchmark

Primary metric: held-out post-veto proxy tail fraction \(\Pr(|r-m_p|>5\,\mathrm{ns}\mid\mathrm{kept})\). Timing efficiency, tail capture, sigma68, full RMS, AUC, AP, and Brier score are recorded as safety/diagnostic metrics. Confidence intervals bootstrap runs and then events within sampled runs.

| Method | Timing efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Sigma68 after [95% CI] ns | Delta sigma68 [95% CI] ns | AUC | AP |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional_quantile | 0.900 [0.881, 0.918] | 0.316 [0.242, 0.423] | 0.0115 [0.0071, 0.0147] | 1.565 [1.517, 1.608] | -0.126 [-0.148, -0.104] | 0.701 | 0.051 |
| ridge | 0.899 [0.889, 0.911] | 0.489 [0.355, 0.666] | 0.0086 [0.0044, 0.0120] | 1.561 [1.520, 1.618] | -0.130 [-0.152, -0.104] | 0.732 | 0.149 |
| gradient_boosted_trees | 0.897 [0.886, 0.905] | 0.517 [0.402, 0.616] | 0.0082 [0.0049, 0.0108] | 1.626 [1.570, 1.669] | -0.065 [-0.094, -0.040] | 0.747 | 0.248 |
| mlp | 0.899 [0.884, 0.912] | 0.483 [0.407, 0.621] | 0.0087 [0.0053, 0.0114] | 1.646 [1.584, 1.699] | -0.046 [-0.073, -0.018] | 0.712 | 0.248 |
| cnn1d | 0.907 [0.882, 0.935] | 0.511 [0.398, 0.629] | 0.0082 [0.0041, 0.0113] | 1.606 [1.545, 1.682] | -0.085 [-0.123, -0.044] | 0.722 | 0.322 |
| siamese_cnn_meta | 0.898 [0.882, 0.913] | 0.511 [0.386, 0.650] | 0.0083 [0.0046, 0.0116] | 1.607 [1.558, 1.670] | -0.085 [-0.109, -0.057] | 0.742 | 0.309 |

Winner for the fallback proxy benchmark: **gradient_boosted_trees**. The pre-veto proxy tail fraction was `0.0152` and the pre-veto sigma68 was `1.691` ns. Since direct forced/random truth entries are zero, `result.json` names both the direct-truth status and the proxy winner; the proxy winner must not be read as an electronics pedestal truth winner.

Per-held-out-run metrics for the proxy winner:

| Held-out run | n pairs | efficiency | tail capture | post-veto tail fraction | sigma68 after ns | delta sigma68 ns |
|---:|---:|---:|---:|---:|---:|---:|
| 58 | 219 | 0.868 | 1.000 | 0.0000 | 1.490 | -0.150 |
| 59 | 2289 | 0.899 | 0.583 | 0.0073 | 1.561 | -0.047 |
| 60 | 2424 | 0.887 | 0.462 | 0.0098 | 1.616 | -0.043 |
| 61 | 2799 | 0.909 | 0.526 | 0.0106 | 1.593 | -0.104 |
| 62 | 2421 | 0.895 | 0.565 | 0.0046 | 1.634 | -0.051 |
| 63 | 1110 | 0.890 | 0.353 | 0.0111 | 1.684 | -0.135 |
| 65 | 198 | 0.904 | 0.000 | 0.0000 | 1.556 | -0.008 |

## 5. Falsification

Pre-registration: direct forced/random truth would supersede the proxy benchmark if any non-beam/tagged B-stack truth entries existed. Because the truth count is zero, the falsification test for the fallback winner is the S16f shuffled-proxy control: train each method after permuting train-run pre-trigger proxies relative to labels. A claimed method fails if its median tail-capture advantage over shuffled proxy is below -0.05 or if any train/held-out event id overlaps.

Six methods were compared, so no nominal single-method p-value is interpreted as a discovery. The fixed operational winner is the method with the smallest held-out post-veto tail fraction subject to the efficiency penalty.

| Check | Value | Pass? |
|---|---:|---|
| loro_runs_match_config | 58,59,60,61,62,63,65 | yes |
| train_heldout_event_id_overlap_max | 0 | yes |
| features_exclude_run_event_residual_labels |  | yes |
| all_predictions_finite | 137520 | yes |
| one_row_per_method_fold_shuffled_state | 84 | yes |
| cnn1d_actual_tail_capture_ge_shuffled_proxy_median | 0.49122807017543857 | yes |
| gradient_boosted_trees_actual_tail_capture_ge_shuffled_proxy_median | 0.40350877192982454 | yes |
| mlp_actual_tail_capture_ge_shuffled_proxy_median | 0.34782608695652173 | yes |
| ridge_actual_tail_capture_ge_shuffled_proxy_median | 0.3684210526315789 | yes |
| siamese_cnn_meta_actual_tail_capture_ge_shuffled_proxy_median | 0.30434782608695654 | yes |
| traditional_quantile_actual_tail_capture_ge_shuffled_proxy_median | 0.19298245614035087 | yes |

## 6. Threats to validity

Benchmark/selection: the direct truth benchmark is blocked by missing truth rows, so the fallback task answers only which proxy score best removes timing-tail pairs. The traditional baseline is not a strawman; it uses the most direct pre-trigger summary envelope and the same threshold utility as ML.

Data leakage: all splits are by run. No label-defining fields, event identifiers, run identifiers, residuals, post-trigger samples, amplitudes, or peak locations enter the ML features. The direct forced/random gate is audited before the proxy winner is named.

Metric misuse: sigma68 can improve by discarding hard events, so timing efficiency, tail capture, post-veto tail fraction, full RMS, AUC, AP, and Brier score are recorded. No fit-based chi-square is applicable because the primary estimator is a distributional veto score, not a parametric residual fit.

Post-hoc selection: the direct-truth availability gate, LORO runs, model family list, efficiency rule, threshold grid, and bootstrap plan are fixed in the config before scoring. The report names the winner only after applying that fixed rule.

Systematics and caveats: absence in the mounted mirrors is not proof the DAQ never recorded forced/random pedestals. The LUNARC canonical path was not mounted locally if listed in `missing_search_roots`. The proxy target is a timing-tail label, not a physical contamination or electronics pedestal truth label. Pair residuals share events; CIs therefore bootstrap at run and event levels rather than individual pair rows.

## 7. Provenance manifest

`manifest.json` records the command, config, git commit, Python/platform metadata, input checksums, random seed, and output checksums. The raw ROOT checksums are in `input_sha256.csv`.

## 8. Findings & next steps

Direct forced/random S16g truth is blocked in the mounted data: `direct_nonbeam_entries = 0` and no strict forced/random ROOT/archive candidate was visible. The fallback proxy benchmark still separates methods under the same Sample-II LORO protocol; **gradient_boosted_trees** is the strongest proxy scorer by post-veto tail fraction.

Hypothesis: the current laptop mirror contains only beam-trigger HRD runs, while forced/random pedestal acquisitions, if they exist, live in an unmounted DAQ/archive tier or were never converted into the reduced HRD ROOT bundle. The most informative next experiment is to audit external run logs or archived DAQ products before spending more effort on proxy modeling.

Queued follow-up in `result.json`: `S16i: locate external forced/random HRD pedestal acquisition source`. Expected information gain: it determines whether direct no-proxy pedestal closure is feasible from external acquisition provenance or must be retired as unavailable.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033528_1397_05213c6c_forced_random_truth_benchmark.py --config configs/s16g_1781033528_1397_05213c6c_forced_random_truth_benchmark.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `root_trigger_branch_audit.csv`, `file_archive_inventory.csv`, `direct_nonbeam_entries.csv`, `sample_ii_pair_table.csv.gz`, `fold_metrics.csv`, `heldout_predictions.csv.gz`, `threshold_scans.csv`, `head_to_head_benchmark.csv`, `bootstrap_cis.csv`, `leakage_checks.csv`, `fig_head_to_head_tail_fraction.png`, and `fig_winner_residuals_kept_vetoed.png`.

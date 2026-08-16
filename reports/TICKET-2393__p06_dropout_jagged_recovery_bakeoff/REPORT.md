# Study report: TICKET-2393 / P06 -- Dropout and jagged recovery bakeoff

- **Study ID:** TICKET-2393
- **Author (worker label):** testbeam-laptop-4
- **Date:** 2026-08-16
- **Depends on:** S00 selected-pulse reproduction; P06/P-series dropout specification
- **Input checksum(s):** see `manifest.json` (`33` ROOT files)
- **Git commit:** `e911cfc59b772e150beb5dd2c080b020066a3bd4`
- **Config:** `configs/ticket_2393_p06_dropout_jagged_recovery_bakeoff.json`

## 0. Question
Can waveform dropout or jagged-sample corruption be repaired well enough to recover constant-fraction timing, and does a learned repair model beat a strong rule-based interpolation baseline on run-heldout injected corruptions?

Atomic steps: (i) reproduce the S00 selected B-stave pulse count from raw `HRDv` ROOT records; (ii) build a run-heldout injection panel from selected real waveforms; (iii) compare a rule-based jagged mask/interpolator with ridge, gradient-boosted trees, MLP, 1D-CNN, and a gated residual CNN; (iv) bootstrap uncertainty by run.

## 1. Reproduction

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |

The reproduction reads each raw `hrdb_run_####.root` file, reshapes `HRDv` into eight 18-sample channel waveforms, subtracts the median of samples 0--3, and counts physical B-stave channels `{0,2,4,6}` with maximum corrected amplitude above 1000 ADC. This is independent of the derived selected-pulse CSV.

## 2. Traditional method

The traditional comparator is the documented rule-based jagged repair: a sample is masked when it is a sharp local depression relative to both neighbours, then replaced by linear interpolation from non-masked samples. Timing is recomputed by a 20% constant-fraction crossing on the repaired waveform. In equations, for normalized waveform \(x_j\), interior sample \(j\) is masked when

\[x_j < \frac{x_{j-1}+x_{j+1}}{2} - 0.18\max(x_{j-1},x_{j+1})\quad\mathrm{and}\quad x_j < \min(x_{j-1},x_{j+1})-0.08.\]

This is intentionally stronger than a no-repair baseline because it uses the local pulse geometry, preserves unmasked samples, and abstains from using truth injection metadata.

## 3. ML methods

All learned models are trained only on `train_runs`, tuned on `val_runs`, and scored on `test_runs`. Inputs are the corrupted 18-sample normalized waveform, the rule mask, and six shape summaries. Targets are the original uncorrupted normalized 18-sample waveform. The model output is an inpainted waveform, not a truth label. Classifier-style dropout flag quality is reported only as a diagnostic from the rule mask because the main adoption metric is timing after repair.

The ML panel is ridge regression with validation-selected alpha, histogram gradient-boosted trees in a multi-output wrapper, an `MLPRegressor`, a compact 1D-CNN over waveform plus mask channels, and a new gated residual CNN. The new architecture is sensible here because local missing samples need both short-range interpolation and wider pulse-context gating; dilated residual convolutions provide the former, and a squeeze gate conditions repair on the whole pulse.

Metric definitions. For repaired waveform \(\hat{x}\) and original waveform \(x\), the reconstruction loss is \(18^{-1}\sum_j(\hat{x}_j-x_j)^2\). The timing target is the 20% CFD crossing \(t_{0.2}(x)\), computed by linear interpolation at the first rising-edge threshold crossing. The primary residual is \(r=10[t_{0.2}(\hat{x})-t_{0.2}(x)]\) ns because samples are 10 ns apart. The reported robust resolution is \(\sigma_{68}=(Q_{84}(r)-Q_{16}(r))/2\); MAE, RMS, and \(|r|>5\) ns tail fraction are secondary diagnostics.

## 4. Head-to-head benchmark

Primary metric: run-block bootstrap 95% CI for held-out timing sigma68 in ns. Lower is better.

| method | n | timing_bias_ns | timing_mae_ns | timing_sigma68_ns | timing_rms_ns | tail_frac_abs_gt5ns | reconstruction_mse | timing_bias_ns_ci95_low | timing_bias_ns_ci95_high | timing_mae_ns_ci95_low | timing_mae_ns_ci95_high | timing_sigma68_ns_ci95_low | timing_sigma68_ns_ci95_high | timing_rms_ns_ci95_low | timing_rms_ns_ci95_high | tail_frac_abs_gt5ns_ci95_low | tail_frac_abs_gt5ns_ci95_high | reconstruction_mse_ci95_low | reconstruction_mse_ci95_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_rule_interpolation | 12600 | 0.5196 | 0.9442 | 0.3397 | 3.1089 | 0.0748 | 0.0400 | 0.3390 | 0.7098 | 0.8714 | 1.0030 | 0.1674 | 0.4048 | 2.3379 | 4.1420 | 0.0640 | 0.0854 | 0.0243 | 0.0595 |
| ridge | 12600 | -0.8915 | 1.7513 | 0.8657 | 7.0624 | 0.0444 | 0.0036 | -1.1315 | -0.6807 | 1.5690 | 1.9617 | 0.6880 | 1.1222 | 5.9854 | 8.1916 | 0.0379 | 0.0519 | 0.0031 | 0.0043 |
| gradient_boosted_trees | 12600 | -0.1735 | 0.4263 | 0.2005 | 2.5224 | 0.0040 | 0.0009 | -0.2962 | -0.0859 | 0.2767 | 0.6005 | 0.1358 | 0.3089 | 1.3415 | 3.5605 | 0.0023 | 0.0054 | 0.0005 | 0.0014 |
| mlp | 12600 | -0.2451 | 0.7479 | 0.5617 | 2.8688 | 0.0083 | 0.0016 | -0.3474 | -0.1409 | 0.5822 | 0.9215 | 0.4294 | 0.7271 | 1.7186 | 3.9281 | 0.0050 | 0.0115 | 0.0011 | 0.0022 |
| cnn1d | 12600 | -0.1734 | 0.8460 | 0.7322 | 2.8454 | 0.0081 | 0.0013 | -0.2916 | -0.0320 | 0.7571 | 0.9438 | 0.6367 | 0.7811 | 1.7578 | 4.0093 | 0.0060 | 0.0101 | 0.0010 | 0.0015 |
| gated_residual_cnn | 12600 | -0.1957 | 0.8744 | 0.7332 | 2.3555 | 0.0095 | 0.0014 | -0.2566 | -0.1203 | 0.8344 | 0.9204 | 0.6883 | 0.7562 | 1.6185 | 3.1787 | 0.0055 | 0.0141 | 0.0011 | 0.0017 |

Verdict: `gradient_boosted_trees` wins the primary metric with sigma68 `0.2005` ns (95% CI `0.1358`, `0.3089`).

Regime split:

| method | regime | n | timing_sigma68_ns | timing_sigma68_ns_ci95_low | timing_sigma68_ns_ci95_high | timing_mae_ns | tail_frac_abs_gt5ns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cnn1d | leading_edge_destroyed | 6300 | 0.5688 | 0.5115 | 0.6102 | 0.7107 | 0.0068 |
| gated_residual_cnn | leading_edge_destroyed | 6300 | 0.8327 | 0.7414 | 0.9872 | 0.8924 | 0.0103 |
| gradient_boosted_trees | leading_edge_destroyed | 6300 | 0.2188 | 0.1574 | 0.3169 | 0.4418 | 0.0043 |
| mlp | leading_edge_destroyed | 6300 | 0.6071 | 0.4980 | 0.7806 | 0.7628 | 0.0098 |
| ridge | leading_edge_destroyed | 6300 | 1.6531 | 1.5314 | 2.1680 | 1.8002 | 0.0671 |
| traditional_rule_interpolation | leading_edge_destroyed | 6300 | 2.1117 | 1.3625 | 2.8563 | 1.6689 | 0.1460 |
| cnn1d | leading_edge_preserved | 6300 | 0.8308 | 0.6913 | 0.9202 | 0.9813 | 0.0094 |
| gated_residual_cnn | leading_edge_preserved | 6300 | 0.8550 | 0.8006 | 0.9002 | 0.8564 | 0.0087 |
| gradient_boosted_trees | leading_edge_preserved | 6300 | 0.1773 | 0.1131 | 0.2827 | 0.4109 | 0.0037 |
| mlp | leading_edge_preserved | 6300 | 0.5125 | 0.3711 | 0.7242 | 0.7330 | 0.0067 |
| ridge | leading_edge_preserved | 6300 | 0.6329 | 0.4478 | 0.8820 | 1.7023 | 0.0217 |
| traditional_rule_interpolation | leading_edge_preserved | 6300 | 0.0000 | 0.0000 | 0.0000 | 0.2195 | 0.0037 |

## 5. Falsification

Pre-registration: before fitting, the primary metric was fixed to `timing_sigma68_ns` at alpha=0.05 on run-heldout injected dropouts, with leading-edge-preserved and leading-edge-destroyed strata reported separately. The falsification test is that the best learned method must improve timing sigma68 over the rule interpolator by more than zero under paired run bootstrap. Six methods were tried, so method selection is treated as family-wise exploratory; the winner is named but not promoted as a production replacement without an external corruption sample.

Observed ML-minus-traditional sigma68 delta for the winner: `-0.1392` ns. Negative values favour ML.

Systematic uncertainty ledger:

| Source | Direction tested | Estimated impact | Treatment |
|---|---|---|---|
| Run composition | Train/validation/test are disjoint run sets; CIs resample whole test runs | Dominant width of CI bands | Included in run bootstrap |
| Injection mechanism | Zero/depressed single-sample dropout, not real electronics labels | Can overstate repairability for correlated glitches | Reported as external-validity caveat |
| Timing pickoff | Fixed CFD20 rather than scanning fractions | Affects all methods through same target and score | Held fixed by config; not tuned post hoc |
| Leading-edge information loss | Preserved/destroyed strata reported separately | Traditional wins preserved-tail sigma68; GBT wins combined and destroyed strata | Reported as regime table, not hidden by pooled score |
| Model selection | Six methods compared | Winner has selection optimism | Treated as exploratory family-wise result |

## 6. Threats to validity

- **Benchmark/selection:** the baseline is not a strawman; it uses a local jagged mask and interpolation. The injection panel is sampled from selected real waveforms, so it inherits the real pulse-shape distribution but not real electronics-failure mechanisms.
- **Data leakage:** train, validation, and test are disjoint by run. Injection metadata is not passed to any method. The rule mask is derived from corrupted samples only.
- **Metric misuse:** timing sigma68, MAE, RMS, tail fraction, and reconstruction MSE are all reported. There is no parametric fit, so chi2/ndf is not applicable.
- **Post-hoc selection:** hyperparameter grids and the primary metric are in the committed config. The architecture family was chosen from the ticket request before looking at held-out scores.

## 7. Provenance manifest

`manifest.json` records raw ROOT checksums, package versions, commands, random seeds, split runs, and output checksums.

Package versions used by the producer:

| numpy | pandas | scikit-learn | torch | uproot | awkward |
| --- | --- | --- | --- | --- | --- |
| 1.24.4 | 2.0.3 | 1.3.2 | 2.4.1+cpu | 5.4.2 | 2.6.10 |

## 8. Findings and next steps

The raw-count gate passes exactly: `640,737` selected B-stave pulses. The best held-out repair method is `gradient_boosted_trees`. The leading-edge-destroyed stratum remains much harder than tail-only corruption, which is the expected irrecoverability boundary: when the rising CFD crossing is removed, waveform priors can reduce damage but cannot restore all timing information.

Caveat on the pooled winner: the rule interpolator has exactly zero sigma68 in the leading-edge-preserved stratum because tail-only corruptions do not move the CFD20 crossing for most pulses. The GBT wins the pooled primary metric by reducing destroyed-leading-edge failures and high-tail residuals, not by improving every physical regime. A deployable policy should route preserved-tail cases to the rule repair and use learned repair only where the mask touches timing-critical samples.

Novel follow-up ticket appended by this worker, if any, is listed in `result.json`. The most informative next step is an external real-dropout validation set with reviewer labels, because injected zero-sample corruptions do not prove performance on real electronics failures.

## 9. Reproducibility

Regenerate with:

```bash
python3 scripts/ticket_2393_p06_dropout_jagged_recovery_bakeoff.py --config configs/ticket_2393_p06_dropout_jagged_recovery_bakeoff.json
```

Artifacts: `raw_count_by_run.csv`, `dataset_panel.csv`, `method_predictions.csv.gz`, `benchmark_summary.csv`, `regime_summary.csv`, `manifest.json`, `result.json`, and this report.

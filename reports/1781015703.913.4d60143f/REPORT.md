# S16h: matched lowering pile-up confound audit

- **Ticket:** 1781015703.913.4d60143f
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `236449a4c852e6278b3d0048e89195b8311a0d86`
- **Config:** `s16h_1781015703_913_4d60143f.json`

## Question

Is the high adaptive-lowering timing-tail fraction in Sample I caused by pedestal bias itself, or by matched pile-up, topology, saturation, and anomaly confounders?

## Raw-ROOT Reproduction First

The script starts from `h101/HRDv` raw ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | yes |
| adaptive post-correction violations | 0 | 0 | 0 | yes |
| sample_i_analysis selected_pulses | 252266 | 252266 | 0 | yes |
| sample_i_analysis B2 | 241422 | 241422 | 0 | yes |
| sample_i_analysis B4 | 6451 | 6451 | 0 | yes |
| sample_i_analysis B6 | 3094 | 3094 | 0 | yes |
| sample_i_analysis B8 | 1299 | 1299 | 0 | yes |

The S16d high-vs-low tail number is also reproduced before mechanism work:

| Quantity | Prior value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| s16d high_lowering_tail_fraction | 0.130435 | 0.130435 | 0 | yes |
| s16d low_lowering_tail_fraction | 0.0123796 | 0.0123796 | 0 | yes |
| s16d heldout_events | 250 | 250 | 0 | yes |
| s16d heldout_pair_residuals | 750 | 750 | 0 | yes |

Timing subset: train runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53] contain `400` events / `1200` pair residuals; held-out runs [54, 55, 56, 57] contain `250` events / `750` pair residuals.

## Methods

The target is the S02 `CFD20` pair residual after the 2 cm TOF correction, pair-centered and tailed at `|residual| > 5 ns`. The high-lowering threshold is selected on train runs only.

The matched audit coarsens only from train-run distributions, then matches held-out rows exactly on `run, pair, amp_bin, peak_bin, s10_pileup_bin, p09_anomaly_taxon, saturation_flag`. The S10 pile-up proxy is a waveform-shape score from late/tail width, late activity, and pretrigger activity. The P09 anomaly taxon is assigned from pretrigger, negative-dropout, broad-late, and late-activity morphology. Saturation is a high-amplitude proxy flag at the train-run 98th percentile.

Traditional method: Ridge residual correction using lowering, amplitude, peak-sample, area/amp, and pre/late anomaly terms plus pair identity.

ML method: fixed random-forest residual corrector plus a random-forest tail classifier for mechanism ranking. Splits are by run. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out runs, then events within each sampled run.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
| raw_cfd20 | 3.110 [2.955, 3.293] | 0.065 [0.047, 0.090] | 5.656 | 750 |
| traditional_ridge_lowering | 3.240 [3.007, 3.479] | 0.105 [0.065, 0.132] | 5.436 | 750 |
| ml_rf_lowering | 2.775 [2.574, 2.927] | 0.052 [0.032, 0.077] | 5.024 | 750 |
| ml_shuffled_target_control | 3.105 [2.973, 3.312] | 0.073 [0.049, 0.097] | 5.707 | 750 |

Train-selected high-lowering threshold: `817.67 ADC`. Held-out high-bin tail fraction `0.130` [0.000, 0.383], low-bin tail fraction `0.012` [0.000, 0.025].

## Mechanism Diagnostics

| Bin | n pairs | tail fraction [95% CI] | sigma68 ns | median peak sample | median area/amp | median pretrigger abs ADC | median late abs ADC | median tail-area frac |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| low | 727 | 0.012 [0.000, 0.025] | 1.608 | 10.0 | 7.04 | 18.0 | 2336.5 | 0.513 |
| high | 23 | 0.130 [0.000, 0.383] | 2.185 | 4.0 | 1.21 | 1690.5 | 1290.5 | 0.512 |

High-bin tails concentrate in run 56 B4-B8 (tail 0.400, n=5). RF tail classifier held-out AUC is `0.887` with shuffled-target AUC `0.606`; top RF features are `delta_positive_area_over_amp, delta_area_over_amp, delta_width20_samples, delta_late_abs_adc, s10_pileup_proxy_score`.

## Matched Confound Audit

| Comparison | effective high / low pairs | matched strata | tail odds ratio [95% CI] | sigma68 delta ns | full-RMS delta ns | pile-up score enrichment |
|---|---:|---:|---:|---:|---:|---:|
| unmatched | 23.0 / 727.0 | 233 | 12.91 [1.11, 87.72] | 0.626 [-0.386, 17.659] | 6.139 [-4.843, 15.249] | 0.012 [-0.752, 0.711] |
| matched_confound_strata | 7.0 / 7.0 | 6 | 1.00 [0.04, 10.82] | -1.314 [-5.044, 0.692] | -1.903 [-4.849, 0.657] | -0.218 [-1.437, 0.337] |

ML calibration ECE is `0.044` [0.035, 0.062] on the held-out runs.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
| split_by_run_heldout_runs_match_config | 54,55,56,57 | yes |
| ml_features_exclude_run_event_and_residual |  | yes |
| shuffled_target_not_better_than_actual_ml | 0.33061473233958516 | yes |
| intentional_oracle_is_obviously_leaky | 2.568940518633896 | yes |
| row_cv_not_much_better_than_run_cv | 0.010452033918856962 | yes |
| actual_ml_improvement_under_raw_one_ns | 0.3357607838712746 | yes |
| heldout_predictions_finite | 750 | yes |
| tail_classifier_shuffled_auc_not_too_high | 0.6061427280939476 | yes |

## Verdict

The elevated high-lowering tail rate is real on held-out runs but still behaves more like a proxy than a fixable pedestal-lowering error. Traditional correction improves sigma68 by -0.130 ns and RF correction by 0.336 ns, while the high-minus-low tail gap is 0.118. High-bin pairs have pretrigger medians 93.92x low-bin, late-window medians 0.55x low-bin, and tail-area-fraction medians 1.00x low-bin; the mechanism is most consistent with pileup/shape pathologies or residual timewalk correlated with lowering, not lowering propagation alone.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781015703_913_4d60143f_matched_lowering_audit.py --config configs/s16h_1781015703_913_4d60143f.json --out-dir reports/1781015703.913.4d60143f
```

Artifacts: `reproduction_match_table.csv`, `reproduction_target_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `mechanism_high_low_summary.csv`, `matched_effect_summary.csv`, `confound_strata_parameters.csv`, `mechanism_by_run_pair.csv`, `mechanism_by_stave.csv`, `ml_tail_classifier_summary.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.

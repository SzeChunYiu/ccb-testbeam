# S16c: pedestal-lowering nuisance propagation into timing residuals

- **Ticket:** 1781001221.625989.53423f03
- **Author:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Depends on:** S00, S02, S16
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `e1006f46a1f4c96682778a602dbb8d9a9deeb3df`
- **Config:** `s16c_config.json`

## Question

Does adaptive-pedestal lowering explain timing residual tails in the downstream S02 B4/B6/B8 timing benchmark?

## Raw-ROOT Reproduction

The script first reruns the S00/S16 raw ROOT gate from `h101/HRDv`, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | yes |
| adaptive post-correction violations | 0 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | yes |

The timing subset is the S02 Sample-II downstream all-hit subset. On held-out run 65 it has `66` events and `198` pair residuals.

## Methods

The primary reported metric is the S02 `CFD20` pair residual after the 2 cm TOF correction. Nuisance models train on pair-centered residuals so they do not get credit merely for reproducing fixed pair offsets, but the held-out benchmark applies their corrections back to the uncentered S02 residuals. Adaptive lowering is recomputed from the same raw waveforms as S16, but it is used only as a nuisance covariate.

The traditional method is an analytic Ridge residual correction using interpretable pair features: signed/absolute/summed lowering, log-amplitude difference, peak-sample difference, and pair identity. A separate train-only threshold scan defines a high-lowering bin for tail stratification.

The ML method is a fixed random-forest residual corrector using the same lowering features plus fractional lowering, min amplitude, and area/peak difference. It is checked by run-grouped CV on runs 58-63, then evaluated on held-out run 65. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out events, not individual duplicated pair rows.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
| raw_cfd20 | 2.993 [2.659, 3.370] | 0.066 [0.030, 0.111] | 2.781 | 198 |
| traditional_ridge_lowering | 3.251 [3.009, 3.617] | 0.061 [0.035, 0.126] | 3.026 | 198 |
| ml_rf_lowering | 2.921 [2.655, 3.266] | 0.020 [0.000, 0.066] | 2.598 | 198 |
| ml_shuffled_target_control | 2.985 [2.708, 3.399] | 0.056 [0.020, 0.101] | 2.768 | 198 |

Held-out high-lowering bin from the train scan: threshold `902.97 ADC`, high-bin tail fraction `0.000`, low-bin tail fraction `0.066`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
| split_by_run_train_58_63_heldout_65 | 1 | yes |
| ml_features_exclude_run_event_and_residual |  | yes |
| shuffled_target_not_better_than_actual_ml | 0.06440416577028296 | yes |
| actual_ml_improvement_under_raw_one_ns | 0.0728254176655665 | yes |
| heldout_predictions_finite | 198 | yes |

## Verdict

Adaptive lowering does not explain the S02 held-out timing tails strongly: high-vs-low tail fractions are 0.000 vs 0.066, and sigma68 gains are -0.258 ns traditional and 0.073 ns ML.

## Reproducibility

```bash
python reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance/s16c_pedestal_timing.py --config reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance/s16c_config.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `threshold_scan.csv`, `ml_cv_scan.csv`, `head_to_head_benchmark.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and two PNG figures.

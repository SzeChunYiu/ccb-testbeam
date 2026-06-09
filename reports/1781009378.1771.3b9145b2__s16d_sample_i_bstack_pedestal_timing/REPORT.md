# S16d: Sample-I B-stack pedestal-lowering timing-tail nuisance

- **Ticket:** 1781009378.1771.3b9145b2
- **Author:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `86e93ac25967ce93cdc3987324c1fab0aee64558`
- **Config:** `s16d_config.json`

## Question

Does adaptive-pedestal lowering explain timing residual tails in the higher-statistics Sample-I B-stack B4/B6/B8 residuals?

## Raw-ROOT Reproduction First

Before timing work, the script reruns the S00/S16 raw ROOT gate from `h101/HRDv`, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | yes |
| adaptive post-correction violations | 0 | 0 | 0 | yes |
| sample_i_analysis selected_pulses | 252266 | 252266 | 0 | yes |
| sample_i_analysis B2 | 241422 | 241422 | 0 | yes |
| sample_i_analysis B4 | 6451 | 6451 | 0 | yes |
| sample_i_analysis B6 | 3094 | 3094 | 0 | yes |
| sample_i_analysis B8 | 1299 | 1299 | 0 | yes |

The Sample-I timing subset is downstream all-hit B4/B6/B8. Held-out runs [54, 55, 56, 57] have `250` events and `750` pair residuals; train runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53] have `400` events and `1200` pair residuals.

## Methods

The target metric is the S02 `CFD20` pair residual after the 2 cm TOF correction. Adaptive lowering is recomputed from the same raw waveforms as S16 and used only as a nuisance covariate.

The traditional method is a Ridge residual correction using signed, absolute, and summed lowering, log-amplitude difference, peak-sample difference, and pair identity. A train-only threshold scan defines a high-lowering residual-tail bin.

The ML method is a fixed random-forest residual corrector using the same lowering features plus fractional lowering, minimum amplitude, and area/peak differences. Splits are by run: training runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53], held-out runs [54, 55, 56, 57]. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out runs, then events within each sampled run.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
| raw_cfd20 | 3.110 [2.961, 3.290] | 0.065 [0.045, 0.090] | 5.656 | 750 |
| traditional_ridge_lowering | 3.060 [2.881, 3.241] | 0.069 [0.048, 0.099] | 5.305 | 750 |
| ml_rf_lowering | 2.930 [2.790, 3.073] | 0.061 [0.041, 0.091] | 5.252 | 750 |
| ml_shuffled_target_control | 3.211 [3.064, 3.455] | 0.088 [0.059, 0.113] | 5.710 | 750 |

Train-selected high-lowering threshold: `817.67 ADC`. Held-out high-bin tail fraction `0.130`, low-bin tail fraction `0.012`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
| split_by_run_heldout_runs_match_config | 54,55,56,57 | yes |
| ml_features_exclude_run_event_and_residual |  | yes |
| shuffled_target_not_better_than_actual_ml | 0.2811530290107771 | yes |
| intentional_oracle_is_obviously_leaky | 2.568795348787759 | yes |
| row_cv_not_much_better_than_run_cv | -0.07077691571048317 | yes |
| actual_ml_improvement_under_raw_one_ns | 0.1801578443488836 | yes |
| heldout_predictions_finite | 750 | yes |

## Verdict

Adaptive lowering is not a strong explanation of the held-out Sample-I timing tails: traditional lowering correction changes sigma68 by 0.050 ns and ML by 0.180 ns versus raw CFD20. The high-lowering bin tail fraction is 0.130 versus 0.012 in the low-lowering bin.

## Reproducibility

```bash
python reports/1781009378.1771.3b9145b2__s16d_sample_i_bstack_pedestal_timing/s16d_sample_i_bstack_pedestal_timing.py --config reports/1781009378.1771.3b9145b2__s16d_sample_i_bstack_pedestal_timing/s16d_config.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `threshold_scan.csv`, `ml_cv_scan.csv`, `head_to_head_benchmark.csv`, `heldout_by_run.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and two PNG figures.

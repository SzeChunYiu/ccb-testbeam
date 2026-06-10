# S04b: adaptive-lowering covariates in full timing-resolution tail tables

- **Ticket:** 1781009378.1796.74af2d55
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `27379b139276ea7685e74910201b6c6c4392a26a`
- **Config:** `s04b_1781009378_adaptive_lowering_covariates.json`

## Question

Should adaptive-pedestal lowering enter the full S04 timing-resolution systematic tables as a nuisance covariate?

## Raw-ROOT Reproduction First

The script first rescans `h101/HRDv` from raw B-stack ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | yes |
| adaptive post-correction violations | 0 | 0 | 0 | yes |
| sample_i_analysis selected_pulses | 252266 | 252266 | 0 | yes |
| sample_i_analysis B2 | 241422 | 241422 | 0 | yes |
| sample_i_analysis B4 | 6451 | 6451 | 0 | yes |
| sample_i_analysis B6 | 3094 | 3094 | 0 | yes |
| sample_i_analysis B8 | 1299 | 1299 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | yes |

The full timing table then uses every Sample-I and Sample-II analysis event with at least two selected B staves, producing `65484` pair residuals across `21` held-out-by-run folds.

## Methods

The traditional method is the S04-style CFD20 inter-stave table after the 2 cm TOF correction: narrow-core Gaussian+constant sigma with chi2/ndf, sigma68, full RMS, abs(residual)>5 ns tail fraction, and adaptive-lowering strata. A Ridge residual correction on signed/absolute/summed lowering, log-amplitude and peak-sample differences, pair, and sample is included only as an interpretable nuisance-correction stress test.

The ML method is a random-forest residual corrector using the same lowering terms plus fractional lowering, amplitude, area/peak, pair, sample, and lowering-bin features. Every prediction is out-of-fold with folds grouped by run. Bootstrap CIs resample held-out runs and then events within sampled runs.

## Held-out Pooled Benchmark

| Method | sigma68 ns [95% CI] | tail frac [95% CI] | full RMS ns [95% CI] | core sigma ns | chi2/ndf | n pairs |
|---|---:|---:|---:|---:|---:|---:|
| raw_cfd20 | 3.724 [3.345, 9.960] | 0.176 [0.125, 0.300] | 20.755 [16.323, 28.814] | 4.339 | 123.65 | 65484 |
| traditional_ridge_lowering | 7.339 [6.267, 9.044] | 0.430 [0.393, 0.507] | 13.901 [12.473, 16.716] | 5.000 | 49.72 | 65484 |
| ml_rf_lowering | 3.468 [3.272, 3.834] | 0.158 [0.127, 0.210] | 7.717 [6.991, 9.051] | 3.956 | 113.97 | 65484 |
| ml_shuffled_target_control | 3.911 [3.493, 9.954] | 0.192 [0.140, 0.309] | 20.824 [16.402, 28.772] | 4.317 | 48.84 | 65484 |

## Sample Split

| Sample | Method | sigma68 ns | tail frac | full RMS ns | n pairs |
|---|---|---:|---:|---:|---:|
| sample_i | raw_cfd20 | 29.215 | 0.468 | 38.572 | 12445 |
| sample_i | ml_rf_lowering | 4.645 | 0.291 | 10.847 | 12445 |
| sample_ii | raw_cfd20 | 3.398 | 0.124 | 13.113 | 53039 |
| sample_ii | ml_rf_lowering | 3.300 | 0.128 | 6.768 | 53039 |

## Worst Raw Tail Strata

| Sample | Pair | Lowering bin | n pairs | sigma68 ns | tail frac | full RMS ns |
|---|---|---|---:|---:|---:|---:|
| sample_i | B2-B8 | none | 679 | 41.335 | 0.869 | 45.576 |
| sample_i | B2-B8 | large | 99 | 39.927 | 0.687 | 44.291 |
| sample_i | B2-B8 | small | 85 | 47.865 | 0.635 | 51.383 |
| sample_i | B2-B6 | none | 1641 | 37.274 | 0.598 | 43.558 |
| sample_i | B2-B6 | large | 274 | 24.722 | 0.595 | 41.520 |
| sample_i | B2-B6 | small | 253 | 44.294 | 0.522 | 48.172 |
| sample_i | B2-B4 | large | 835 | 16.372 | 0.489 | 39.663 |
| sample_i | B2-B4 | none | 4148 | 40.630 | 0.479 | 47.238 |

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
| all_predictions_are_run_heldout_oof | 21 | yes |
| ml_features_exclude_identifiers_and_labels |  | yes |
| shuffled_target_not_better_than_actual_ml | 0.44297956053669285 | yes |
| intentional_oracle_is_obviously_leaky | 2.677507661230082 | yes |
| row_cv_not_much_better_than_run_cv | 0.05994394511292134 | yes |
| actual_ml_improvement_under_raw_one_ns | 0.2567741360273512 | yes |

## Verdict

Adaptive lowering should enter S04 tail/systematic tables as a stratifying nuisance covariate, not as a correction. Large-lowering strata have weighted raw tail fraction 0.266 versus 0.131 elsewhere, while the ML residual correction gains only 0.257 ns and the Ridge nuisance correction worsens sigma68 by 3.614 ns.

## Reproducibility

```bash
python scripts/s04b_1781009378_adaptive_lowering_covariates.py --config configs/s04b_1781009378_adaptive_lowering_covariates.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_oof.csv`, `fold_metrics.csv`, `ml_cv_scan.csv`, `head_to_head_benchmark.csv`, `tail_tables.csv`, `heldout_by_run.csv`, `downstream_variance_reproduction.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.

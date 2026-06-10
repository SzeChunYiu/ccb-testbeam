# S04c: Pathology-Stratified Timing-Resolution Tail Table

- **Ticket:** `1781018820.3826.39cd42b6`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT `h101/HRDv` under `data/root/root`
- **Split:** grouped by run; five OOF folds, then run-block/event bootstrap CIs
- **Config:** `configs/s04c_1781018820_3826_39cd42b6_pathology_tail_table.json`

## Reproduction First

The first executable step rescans raw ROOT with the standard S00/S04 B-stave selection.

| quantity                            |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses       |         640737 |       640737 |       0 |           0 | True   |
| adaptive post-correction violations |              0 |            0 |       0 |           0 | True   |
| sample_i_analysis selected_pulses   |         252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2                |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4                |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6                |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8                |           1299 |         1299 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses  |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2               |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4               |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6               |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8               |           4506 |         4506 |       0 |           0 | True   |

## Methods

Residuals use all-downstream B4/B6/B8 pair CFD20 timing after the 2 cm TOF correction. The tail cut is fixed at `|pair-centered residual| > 5 ns`.

Traditional: the conventional S04 CFD20 pair-centered Gaussian-core/tail table, stratified by fixed pathology axes. A transparent Ridge pathology residual correction is included as a non-ML stress test, but it is not adopted if it worsens the conventional table.

ML: RandomForest residual correction and sigmoid-calibrated RandomForest tail probability using waveform/pathology summaries only. Features exclude run, event identifiers, residuals, and tail labels.

## Head-To-Head

| method                      |   n_pair_residuals |   sigma68_ns |   sigma68_ci_low |   sigma68_ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   tail_ci_low |   tail_ci_high |   core_chi2_ndf |   pull_width_ml_tail_prob |
|:----------------------------|-------------------:|-------------:|-----------------:|------------------:|--------------:|----------------------:|--------------:|---------------:|----------------:|--------------------------:|
| raw_cfd20_pair_centered     |              13410 |      1.68164 |          1.63113 |           1.74115 |       5.78949 |             0.0152871 |     0.0109031 |      0.0193482 |         4.57769 |                   35.8457 |
| traditional_ridge_pathology |              13410 |      2.00334 |          1.93834 |           2.09766 |       5.27783 |             0.0348993 |     0.0276907 |      0.0420125 |         1.40732 |                   42.5503 |
| ml_rf_pathology             |              13410 |      1.24894 |          1.20184 |           1.31105 |       4.01253 |             0.0143922 |     0.0103775 |      0.0178453 |         1.45348 |                   30.0564 |
| ml_shuffled_target_control  |              13410 |      1.75328 |          1.70757 |           1.8149  |       5.74029 |             0.0196868 |     0.0163164 |      0.0239545 |         5.34297 |                   37.6256 |

## Pathology Axes

| axis                | worst_stratum      |   worst_tail_frac | best_stratum   |   best_tail_frac |   tail_frac_range |   sigma68_range_ns |
|:--------------------|:-------------------|------------------:|:---------------|-----------------:|------------------:|-------------------:|
| s16_lowering_axis   | large              |         0.0508941 | none           |       0.00857366 |         0.0423204 |         0.531357   |
| p09_taxon_proxy     | baseline_excursion |         0.0311615 | ordinary_shape |       0.00235532 |         0.0288062 |         0.567342   |
| p07_saturation_axis | wide_plateau       |         0.0308422 | shoulder_wide  |       0.00735165 |         0.0234906 |         0.111387   |
| pretrigger_axis     | large              |         0.0311615 | quiet          |       0.00805868 |         0.0231028 |         0.487634   |
| dropout_jagged_axis | negative_dropout   |         0.027724  | not_dropout    |       0.011974   |         0.01575   |         0.267411   |
| s10_two_pulse_axis  | high_broad_late    |         0.0222309 | mid_broad_late |       0.00841992 |         0.013811  |        -0.00304484 |
| peak_phase_axis     | nominal_peak       |         0.0154972 | early_peak     |       0.00294551 |         0.0125517 |        -0.21148    |

The largest raw tail separation is `s16_lowering_axis`. Its raw strata are:

| stratum   |   n_pair_residuals |   n_events |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   tail_ci_low |   tail_ci_high |   mean_ml_tail_probability |
|:----------|-------------------:|-----------:|-------------:|--------------:|----------------------:|--------------:|---------------:|---------------------------:|
| large     |                727 |        279 |      2.00699 |      13.5765  |            0.0508941  |    0.0293181  |      0.0895902 |                  0.0818973 |
| medium    |                860 |        402 |      1.53728 |       9.42446 |            0.0325581  |    0.00735067 |      0.0518537 |                  0.0212462 |
| small     |               1559 |        776 |      1.83321 |       8.05193 |            0.0186017  |    0.0084576  |      0.0309092 |                  0.0164243 |
| none      |              10264 |       3752 |      1.47563 |       3.70854 |            0.00857366 |    0.00512266 |      0.012207  |                  0.0102643 |

## Leakage Checks

| check                                         | value                | pass   |
|:----------------------------------------------|:---------------------|:-------|
| all_rows_have_run_heldout_oof_predictions     | 13410                | True   |
| ml_features_exclude_identifiers_and_labels    |                      | True   |
| shuffled_regression_not_better_than_actual_ml | 0.5043400118110113   | True   |
| intentional_oracle_is_obviously_leaky         | 0.017593838208321555 | True   |
| row_cv_not_much_better_than_run_cv            | 0.008396562459034529 | True   |
| tail_classifier_shuffled_auc_near_random      | 0.2862991775961047   | True   |
| actual_ml_improvement_under_one_ns            | 0.4327017523980037   | True   |

Run-vs-row CV sentinel: ML run-CV sigma68 `1.243 ns`, row-CV sigma68 `1.234 ns`; calibrated tail AP `0.584`, Brier `0.0092`, shuffled AUC `0.286`.

## Verdict

The non-core timing tails are dominated by fixed morphology/pathology atoms rather than by a single correctable timing model. The strongest separator is s16_lowering_axis (large tail fraction 0.051 versus none 0.009). The conventional CFD20 S04 table gives sigma68 1.682 ns, the transparent Ridge stress test gives 2.003 ns, and ML gives 1.249 ns. S04 consumers should use the stratum table as a veto/uncertainty ledger, not replace the timing correction solely from this ML gain.

The ML residual correction is not adopted as a new timing baseline here: it changes sigma68 by `0.433 ns` versus the traditional CFD20 table and `0.754 ns` versus the Ridge stress-test correction, while the pathology tail ranking is the more useful output.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s04c_1781018820_3826_39cd42b6_pathology_tail_table.py --config configs/s04c_1781018820_3826_39cd42b6_pathology_tail_table.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_oof.csv.gz`, `head_to_head_benchmark.csv`, `pathology_tail_table.csv`, `axis_summary.csv`, `heldout_by_run.csv`, `ml_fold_diagnostics.csv`, `ml_tail_classifier_cv.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and figures.

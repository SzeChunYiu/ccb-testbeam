# Study report: S03d - Signed per-stave amplitude timewalk prior

- **Ticket:** 1781011359.887.074979d1
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03d_signed_timewalk_prior.yaml`

## 0. Question

Can a physically signed per-stave amplitude timewalk prior replace the flexible S03b isotonic fit without losing held-out timing resolution?

## 1. Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before the S03d comparison.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The run-65 S03a/S03b reference numbers were reproduced from the same raw-derived pulse table before accepting the new signed-prior result.

|   heldout_run | method                   | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | train_runs        | s03a_candidate   |   s03a_alpha | s03b_direction   |   s03b_n_bins | signed_candidate   |   signed_cv_sigma68_ns |   hgb_cv_sigma68_ns | reference_method     |   reference_value |   delta | pass   |
|--------------:|:-------------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:------------------|:-----------------|-------------:|:-----------------|--------------:|:-------------------|-----------------------:|--------------------:|:---------------------|------------------:|--------:|:-------|
|            65 | template_phase_base      | heldout_pairwise_sigma68_ns | 2.88915 |  2.63915 |   3.20541 |                198 |    -3.83043 |      2.88915 |       2.57669 |            0.0505051  |        0.442691 |    3.21363 | 58,59,60,61,62,63 | amp_only         |          100 | decreasing       |            10 | inv_amp            |                 1.6598 |             1.44514 | template_phase_base  |           2.88915 |       0 | True   |
|            65 | s03a_amp_only_ridge      | heldout_pairwise_sigma68_ns | 1.49464 |  1.33462 |   1.62481 |                198 |     1.17923 |      1.49464 |       1.69913 |            0.00505051 |        1.26115  |    2.03718 | 58,59,60,61,62,63 | amp_only         |          100 | decreasing       |            10 | inv_amp            |                 1.6598 |             1.44514 | s03a_amp_only        |           1.49464 |       0 | True   |
|            65 | s03b_isotonic_decreasing | heldout_pairwise_sigma68_ns | 1.56958 |  1.31958 |   1.81958 |                198 |     1.03364 |      1.56958 |       1.83396 |            0.00505051 |        0.325573 |    3.14128 | 58,59,60,61,62,63 | amp_only         |          100 | decreasing       |            10 | inv_amp            |                 1.6598 |             1.44514 | s03b_monotone_binned |           1.56958 |       0 | True   |

## 2. Methods

The signed prior fits per-stave intercepts plus nonnegative coefficients on inverse-amplitude basis terms. Positive coefficients mean lower-amplitude pulses receive a larger predicted delay correction; the sign is fixed by the downstream timewalk prior. Candidate bases were selected only by grouped CV on training runs.

| feature                   |   median_coeff |    min_coeff |    max_coeff |   at_bound_folds |
|:--------------------------|---------------:|-------------:|-------------:|-----------------:|
| B4_1000_over_amp_positive |    4.88278e-21 |  3.85696e-21 |  6.89242e-21 |                7 |
| B4_intercept              |   -4.10309     | -4.27592     | -3.9342      |                0 |
| B6_1000_over_amp_positive |    0.20858     |  2.82419e-15 |  0.56649     |                1 |
| B6_intercept              |    2.41759     |  2.28524     |  2.60341     |                0 |
| B8_1000_over_amp_positive |    2.79206     |  2.34986     |  3.14626     |                0 |
| B8_intercept              |    0.65504     |  0.562252    |  0.911126    |                0 |

## 3. Leave-one-run-out head-to-head

|   heldout_run | method                   |   value |   ci_low |   ci_high |   n_pair_residuals | signed_candidate   |   signed_cv_sigma68_ns |   hgb_cv_sigma68_ns |
|--------------:|:-------------------------|--------:|---------:|----------:|-------------------:|:-------------------|-----------------------:|--------------------:|
|            58 | hgb_timewalk_ml          | 1.09746 | 0.986309 |   1.32659 |                219 | inv_amp            |                1.65519 |             1.4526  |
|            58 | s03a_amp_only_ridge      | 1.18748 | 1.13794  |   1.37842 |                219 | inv_amp            |                1.65519 |             1.4526  |
|            58 | s03b_isotonic_decreasing | 1.3214  | 1.3214   |   1.58194 |                219 | inv_amp            |                1.65519 |             1.4526  |
|            58 | signed_physics_prior     | 1.23067 | 1.17603  |   1.33001 |                219 | inv_amp            |                1.65519 |             1.4526  |
|            58 | template_phase_base      | 2.6428  | 2.6428   |   2.77317 |                219 | inv_amp            |                1.65519 |             1.4526  |
|            59 | hgb_timewalk_ml          | 1.25688 | 1.21368  |   1.31107 |               2289 | inv_amp            |                1.63177 |             1.47146 |
|            59 | s03a_amp_only_ridge      | 1.45871 | 1.39706  |   1.5228  |               2289 | inv_amp            |                1.63177 |             1.47146 |
|            59 | s03b_isotonic_decreasing | 1.5     | 1.33737  |   1.56166 |               2289 | inv_amp            |                1.63177 |             1.47146 |
|            59 | signed_physics_prior     | 1.4595  | 1.38282  |   1.55733 |               2289 | inv_amp            |                1.63177 |             1.47146 |
|            59 | template_phase_base      | 2.99232 | 2.99232  |   3.12333 |               2289 | inv_amp            |                1.63177 |             1.47146 |
|            60 | hgb_timewalk_ml          | 1.24359 | 1.18274  |   1.29201 |               2424 | inv_amp            |                1.63872 |             1.46156 |
|            60 | s03a_amp_only_ridge      | 1.3437  | 1.28766  |   1.40338 |               2424 | inv_amp            |                1.63872 |             1.46156 |
|            60 | s03b_isotonic_decreasing | 1.23065 | 1.23065  |   1.25    |               2424 | inv_amp            |                1.63872 |             1.46156 |
|            60 | signed_physics_prior     | 1.38154 | 1.28923  |   1.44267 |               2424 | inv_amp            |                1.63872 |             1.46156 |
|            60 | template_phase_base      | 2.66393 | 2.66393  |   2.7113  |               2424 | inv_amp            |                1.63872 |             1.46156 |
|            61 | hgb_timewalk_ml          | 1.8278  | 1.75656  |   1.92915 |               2799 | inv_amp            |                1.55315 |             1.37692 |
|            61 | s03a_amp_only_ridge      | 2.12996 | 1.99814  |   2.19809 |               2799 | inv_amp            |                1.55315 |             1.37692 |
|            61 | s03b_isotonic_decreasing | 2.10176 | 2.10176  |   2.25    |               2799 | inv_amp            |                1.55315 |             1.37692 |
|            61 | signed_physics_prior     | 2.16735 | 2.0311   |   2.29604 |               2799 | inv_amp            |                1.55315 |             1.37692 |
|            61 | template_phase_base      | 2.70351 | 2.70351  |   2.70351 |               2799 | inv_amp            |                1.55315 |             1.37692 |
|            62 | hgb_timewalk_ml          | 1.29727 | 1.25438  |   1.35658 |               2421 | inv_amp            |                1.62752 |             1.47264 |
|            62 | s03a_amp_only_ridge      | 1.469   | 1.41525  |   1.51838 |               2421 | inv_amp            |                1.62752 |             1.47264 |
|            62 | s03b_isotonic_decreasing | 1.43743 | 1.39018  |   1.57559 |               2421 | inv_amp            |                1.62752 |             1.47264 |
|            62 | signed_physics_prior     | 1.50023 | 1.44567  |   1.55088 |               2421 | inv_amp            |                1.62752 |             1.47264 |
|            62 | template_phase_base      | 2.90117 | 2.90117  |   3.02631 |               2421 | inv_amp            |                1.62752 |             1.47264 |
|            63 | hgb_timewalk_ml          | 1.27044 | 1.18304  |   1.3313  |               1110 | inv_amp            |                1.63232 |             1.42911 |
|            63 | s03a_amp_only_ridge      | 1.39132 | 1.32099  |   1.46045 |               1110 | inv_amp            |                1.63232 |             1.42911 |
|            63 | s03b_isotonic_decreasing | 1.43311 | 1.31436  |   1.56436 |               1110 | inv_amp            |                1.63232 |             1.42911 |
|            63 | signed_physics_prior     | 1.34247 | 1.27636  |   1.45365 |               1110 | inv_amp            |                1.63232 |             1.42911 |
|            63 | template_phase_base      | 2.87872 | 2.87872  |   3.01249 |               1110 | inv_amp            |                1.63232 |             1.42911 |
|            65 | hgb_timewalk_ml          | 1.35637 | 1.17049  |   1.62207 |                198 | inv_amp            |                1.6598  |             1.44514 |
|            65 | s03a_amp_only_ridge      | 1.49464 | 1.3507   |   1.6303  |                198 | inv_amp            |                1.6598  |             1.44514 |
|            65 | s03b_isotonic_decreasing | 1.56958 | 1.3527   |   1.81958 |                198 | inv_amp            |                1.6598  |             1.44514 |
|            65 | signed_physics_prior     | 1.55529 | 1.3342   |   1.65786 |                198 | inv_amp            |                1.6598  |             1.44514 |
|            65 | template_phase_base      | 2.88915 | 2.63915  |   3.20541 |                198 | inv_amp            |                1.6598  |             1.44514 |

| method                   |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base      | 2.74141 |  2.68081 |   2.98617 |              11460 |             0.0813264 |
| s03a_amp_only_ridge      | 1.55109 |  1.36767 |   1.93148 |              11460 |             0.0191099 |
| s03b_isotonic_decreasing | 1.64515 |  1.31606 |   1.92454 |              11460 |             0.019459  |
| signed_physics_prior     | 1.60436 |  1.39663 |   1.94265 |              11460 |             0.0205934 |
| hgb_timewalk_ml          | 1.39297 |  1.25326 |   1.65455 |              11460 |             0.0155323 |

## 4. Leakage checks

All model selection is grouped by run. Final models are trained with the held-out run removed. Features exclude run number, event id, event order, other-stave timing, and held-out labels.

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                       |     2.67189 |        2.87453 |     2.99164 |
| s03b_isotonic_shuffled_target_sigma68             |     2.65443 |        2.82703 |     2.9894  |
| signed_prior_shuffled_target_sigma68              |     2.66361 |        2.75221 |     3.02375 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

## 5. Verdict

`result.json` verdict: `signed_prior_competitive_no_leakage_flag`.
The signed prior pooled sigma68 is `1.604 ns`; S03b isotonic is `1.645 ns`; S03a Ridge is `1.551 ns`; HGB ML is `1.393 ns`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03d_signed_timewalk_prior.py --config configs/s03d_signed_timewalk_prior.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `signed_prior_cv_scan.csv`, `signed_prior_coefficients.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

# Study report: S03d - Physically signed inverse-amplitude prior

- **Ticket:** 1781011005.945.02b95315
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03d_phys_signed_prior_1781011005.yaml`

## 0. Question

Does a low-DOF physically signed inverse-amplitude prior improve on S03b isotonic bins and S03a amp-only without leakage?

## 1. Raw-ROOT reproduction gate

The S00 selected-pulse count gate was rerun from raw ROOT before any model fitting.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The prior S03a/S03b run-65 headline numbers were then reproduced from the same raw-derived pulse table.

|   heldout_run | method               | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | train_runs        | s03a_candidate   |   s03a_alpha | s03b_mode   | s03b_direction   |   s03b_n_bins |   signed_prior_power |   signed_prior_cv_sigma68_ns |   hgb_cv_sigma68_ns |   reference_value |   delta | pass   |
|--------------:|:---------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:------------------|:-----------------|-------------:|:------------|:-----------------|--------------:|---------------------:|-----------------------------:|--------------------:|------------------:|--------:|:-------|
|            65 | template_phase_base  | heldout_pairwise_sigma68_ns | 2.88915 |  2.63915 |   3.20541 |                198 |    -3.83043 |      2.88915 |       2.57669 |            0.0505051  |        0.442691 |    3.21363 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |                    1 |                       1.6598 |             1.44514 |           2.88915 |       0 | True   |
|            65 | s03a_amp_only        | heldout_pairwise_sigma68_ns | 1.49464 |  1.33462 |   1.62481 |                198 |     1.17923 |      1.49464 |       1.69913 |            0.00505051 |        1.26115  |    2.03718 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |                    1 |                       1.6598 |             1.44514 |           1.49464 |       0 | True   |
|            65 | s03b_monotone_binned | heldout_pairwise_sigma68_ns | 1.56958 |  1.31958 |   1.81958 |                198 |     1.03364 |      1.56958 |       1.83396 |            0.00505051 |        0.325573 |    3.14128 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |                    1 |                       1.6598 |             1.44514 |           1.56958 |       0 | True   |

## 2. Methods

The signed-prior traditional model uses only same-pulse amplitude and stave identity. For each train fold it fits per-stave intercepts plus a nonnegative scale on a shared inverse-amplitude shape `(1000 / amplitude_adc)^p`; grouped train CV selects `p` from 0.5 and 1.0. Negative unconstrained slopes are clipped to zero before held-out evaluation.

|   heldout_run | stave   |   power |   intercept_ns |   signed_slope_ns |   unconstrained_slope_ns | slope_clipped_to_physical_sign   |   n_train_pulses |
|--------------:|:--------|--------:|---------------:|------------------:|-------------------------:|:---------------------------------|-----------------:|
|            58 | B4      |       1 |       -4.15456 |          0        |               -1.03545   | True                             |             3747 |
|            58 | B6      |       1 |        2.53065 |          0.259794 |                0.259794  | False                            |             3747 |
|            58 | B8      |       1 |        1.62392 |          2.71613  |                2.71613   | False                            |             3747 |
|            59 | B4      |       1 |       -4.05865 |          0        |               -1.4316    | True                             |             3057 |
|            59 | B6      |       1 |        2.54294 |          0.194297 |                0.194297  | False                            |             3057 |
|            59 | B8      |       1 |        1.51571 |          2.70443  |                2.70443   | False                            |             3057 |
|            60 | B4      |       1 |       -3.9342  |          0        |               -1.54571   | True                             |             3012 |
|            60 | B6      |       1 |        2.43059 |          0.20858  |                0.20858   | False                            |             3012 |
|            60 | B8      |       1 |        1.50361 |          2.82478  |                2.82478   | False                            |             3012 |
|            61 | B4      |       1 |       -4.27592 |          0        |               -0.936428  | True                             |             2887 |
|            61 | B6      |       1 |        2.60341 |          0        |               -0.0572728 | True                             |             2887 |
|            61 | B8      |       1 |        1.67251 |          2.34986  |                2.34986   | False                            |             2887 |
|            62 | B4      |       1 |       -4.10309 |          0        |               -1.15781   | True                             |             3013 |
|            62 | B6      |       1 |        2.53094 |          0.56649  |                0.56649   | False                            |             3013 |
|            62 | B8      |       1 |        1.57214 |          3.14626  |                3.14626   | False                            |             3013 |
|            63 | B4      |       1 |       -4.05543 |          0        |               -1.34474   | True                             |             3450 |
|            63 | B6      |       1 |        2.49401 |          0.223977 |                0.223977  | False                            |             3450 |
|            63 | B8      |       1 |        1.56142 |          2.95295  |                2.95295   | False                            |             3450 |
|            65 | B4      |       1 |       -4.15757 |          0        |               -1.16205   | True                             |             3754 |
|            65 | B6      |       1 |        2.53433 |          0.196713 |                0.196713  | False                            |             3754 |
|            65 | B8      |       1 |        1.62324 |          2.79206  |                2.79206   | False                            |             3754 |

## 3. Run-held-out head-to-head

Every row trains templates, S03a, S03b, signed prior, and HGB only on the other runs. Per-run intervals bootstrap pair residuals within the held-out run; pooled intervals resample held-out runs.

|   heldout_run | method                  |   value |   ci_low |   ci_high |   n_pair_residuals |   s03b_n_bins |   signed_prior_power |   signed_prior_cv_sigma68_ns |   hgb_cv_sigma68_ns |
|--------------:|:------------------------|--------:|---------:|----------:|-------------------:|--------------:|---------------------:|-----------------------------:|--------------------:|
|            58 | hgb_timewalk            | 1.09746 | 0.986309 |   1.32659 |                219 |            10 |                    1 |                      1.65519 |             1.4526  |
|            58 | phys_signed_inverse_amp | 1.23067 | 1.17603  |   1.33001 |                219 |            10 |                    1 |                      1.65519 |             1.4526  |
|            58 | s03a_amp_only           | 1.18748 | 1.13794  |   1.37842 |                219 |            10 |                    1 |                      1.65519 |             1.4526  |
|            58 | s03b_monotone_binned    | 1.3214  | 1.3214   |   1.58194 |                219 |            10 |                    1 |                      1.65519 |             1.4526  |
|            58 | template_phase_base     | 2.6428  | 2.6428   |   2.77317 |                219 |            10 |                    1 |                      1.65519 |             1.4526  |
|            59 | hgb_timewalk            | 1.25688 | 1.21368  |   1.31107 |               2289 |             8 |                    1 |                      1.63177 |             1.47146 |
|            59 | phys_signed_inverse_amp | 1.4595  | 1.38282  |   1.55733 |               2289 |             8 |                    1 |                      1.63177 |             1.47146 |
|            59 | s03a_amp_only           | 1.45871 | 1.39706  |   1.5228  |               2289 |             8 |                    1 |                      1.63177 |             1.47146 |
|            59 | s03b_monotone_binned    | 1.5     | 1.33737  |   1.56166 |               2289 |             8 |                    1 |                      1.63177 |             1.47146 |
|            59 | template_phase_base     | 2.99232 | 2.99232  |   3.12333 |               2289 |             8 |                    1 |                      1.63177 |             1.47146 |
|            60 | hgb_timewalk            | 1.24359 | 1.18274  |   1.29201 |               2424 |             8 |                    1 |                      1.63872 |             1.46156 |
|            60 | phys_signed_inverse_amp | 1.38154 | 1.28923  |   1.44267 |               2424 |             8 |                    1 |                      1.63872 |             1.46156 |
|            60 | s03a_amp_only           | 1.3437  | 1.28766  |   1.40338 |               2424 |             8 |                    1 |                      1.63872 |             1.46156 |
|            60 | s03b_monotone_binned    | 1.23065 | 1.23065  |   1.25    |               2424 |             8 |                    1 |                      1.63872 |             1.46156 |
|            60 | template_phase_base     | 2.66393 | 2.66393  |   2.7113  |               2424 |             8 |                    1 |                      1.63872 |             1.46156 |
|            61 | hgb_timewalk            | 1.8278  | 1.75656  |   1.92915 |               2799 |            12 |                    1 |                      1.55315 |             1.37692 |
|            61 | phys_signed_inverse_amp | 2.16735 | 2.0311   |   2.29604 |               2799 |            12 |                    1 |                      1.55315 |             1.37692 |
|            61 | s03a_amp_only           | 2.12996 | 1.99814  |   2.19809 |               2799 |            12 |                    1 |                      1.55315 |             1.37692 |
|            61 | s03b_monotone_binned    | 2.10176 | 2.10176  |   2.25    |               2799 |            12 |                    1 |                      1.55315 |             1.37692 |
|            61 | template_phase_base     | 2.70351 | 2.70351  |   2.70351 |               2799 |            12 |                    1 |                      1.55315 |             1.37692 |
|            62 | hgb_timewalk            | 1.29727 | 1.25438  |   1.35658 |               2421 |             8 |                    1 |                      1.62752 |             1.47264 |
|            62 | phys_signed_inverse_amp | 1.50023 | 1.44567  |   1.55088 |               2421 |             8 |                    1 |                      1.62752 |             1.47264 |
|            62 | s03a_amp_only           | 1.469   | 1.41525  |   1.51838 |               2421 |             8 |                    1 |                      1.62752 |             1.47264 |
|            62 | s03b_monotone_binned    | 1.43743 | 1.39018  |   1.57559 |               2421 |             8 |                    1 |                      1.62752 |             1.47264 |
|            62 | template_phase_base     | 2.90117 | 2.90117  |   3.02631 |               2421 |             8 |                    1 |                      1.62752 |             1.47264 |
|            63 | hgb_timewalk            | 1.27044 | 1.18304  |   1.3313  |               1110 |             8 |                    1 |                      1.63232 |             1.42911 |
|            63 | phys_signed_inverse_amp | 1.34247 | 1.27636  |   1.45365 |               1110 |             8 |                    1 |                      1.63232 |             1.42911 |
|            63 | s03a_amp_only           | 1.39132 | 1.32099  |   1.46045 |               1110 |             8 |                    1 |                      1.63232 |             1.42911 |
|            63 | s03b_monotone_binned    | 1.43311 | 1.31436  |   1.56436 |               1110 |             8 |                    1 |                      1.63232 |             1.42911 |
|            63 | template_phase_base     | 2.87872 | 2.87872  |   3.01249 |               1110 |             8 |                    1 |                      1.63232 |             1.42911 |
|            65 | hgb_timewalk            | 1.35637 | 1.17049  |   1.62207 |                198 |            10 |                    1 |                      1.6598  |             1.44514 |
|            65 | phys_signed_inverse_amp | 1.55529 | 1.3342   |   1.65786 |                198 |            10 |                    1 |                      1.6598  |             1.44514 |
|            65 | s03a_amp_only           | 1.49464 | 1.3507   |   1.6303  |                198 |            10 |                    1 |                      1.6598  |             1.44514 |
|            65 | s03b_monotone_binned    | 1.56958 | 1.3527   |   1.81958 |                198 |            10 |                    1 |                      1.6598  |             1.44514 |
|            65 | template_phase_base     | 2.88915 | 2.63915  |   3.20541 |                198 |            10 |                    1 |                      1.6598  |             1.44514 |

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base     | 2.74141 |  2.68081 |   2.98617 |              11460 |             0.0813264 |
| s03a_amp_only           | 1.55109 |  1.36063 |   1.84951 |              11460 |             0.0191099 |
| s03b_monotone_binned    | 1.64515 |  1.32559 |   1.9396  |              11460 |             0.019459  |
| phys_signed_inverse_amp | 1.60436 |  1.37085 |   1.96864 |              11460 |             0.0205934 |
| hgb_timewalk            | 1.39297 |  1.25326 |   1.65455 |              11460 |             0.0155323 |

## 4. Leakage checks

No fitted feature includes run number, event id, event order, other-stave timing, or held-out labels. Final models remove held-out rows. Shuffled-target controls are repeated for the signed prior, isotonic S03b, and HGB in every held-out fold.

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                       |     2.67189 |        2.87453 |     2.99164 |
| s03b_shuffled_target_sigma68                      |     2.65443 |        2.82703 |     2.9894  |
| signed_prior_shuffled_target_sigma68              |     2.53779 |        2.76612 |     3.00187 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

## 5. Verdict

`result.json` verdict: `signed_prior_beats_isotonic_no_leakage`.
Signed prior pooled sigma68 is `1.604 ns`; S03a amp-only is `1.551 ns`; S03b monotone-binned is `1.645 ns`; HGB is `1.393 ns`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03d_phys_signed_prior.py --config configs/s03d_phys_signed_prior_1781011005.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `s03a_amp_only_cv_scan.csv`, `s03b_monotone_cv_scan.csv`, `signed_prior_cv_scan.csv`, `signed_prior_model_table.csv`, `hgb_cv_scan.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

# Study report: S03f - Shared-stave shrinkage for monotone timewalk bins

- **Ticket:** 1781019517.3497.1b4352d9
- **Author:** testbeam-laptop-1
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03f_1781019517_3497_1b4352d9_shared_stave_shrinkage.yaml`

## 0. Question

Can the S03b monotone-binned correction be stabilized by a physically signed shared-stave shrinkage prior instead of independent per-stave isotonic fits?

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

The prior S03a/S03b run-65 headline numbers were then reproduced from the same raw-derived pulse table before fitting the new shrinkage or HGB comparison models.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

## 2. Methods

The traditional shrinkage model uses only same-pulse amplitude and stave identity. In each training fold it builds global log-amplitude bins, fits a shared decreasing isotonic timewalk curve across B4/B6/B8, shrinks each stave's bin medians toward that shared curve by a CV-selected pseudo-count, and then enforces the same decreasing physical sign per stave. This keeps the S03b monotone-bin structure but removes independent per-stave freedom when support is weak.

|   heldout_run | stave   |   n_bins |   shrink_strength |   fitted_min_ns |   fitted_max_ns |   train_bin_pulses |
|--------------:|:--------|---------:|------------------:|----------------:|----------------:|-------------------:|
|            58 | B4      |        6 |               320 |        -2.39012 |        -2.39012 |               3747 |
|            58 | B6      |        6 |               320 |         1.45895 |         2.17506 |               3747 |
|            58 | B8      |        6 |               320 |         1.37064 |         1.37064 |               3747 |
|            59 | B4      |       10 |                80 |        -3.04146 |        -3.04146 |               3057 |
|            59 | B6      |       10 |                80 |         1.19909 |         2.31407 |               3057 |
|            59 | B8      |       10 |                80 |         1.20044 |         1.33169 |               3057 |
|            60 | B4      |       10 |                80 |        -2.9449  |        -2.9449  |               3012 |
|            60 | B6      |       10 |                80 |         1.24551 |         2.19142 |               3012 |
|            60 | B8      |       10 |                80 |         1.28543 |         1.40853 |               3012 |
|            61 | B4      |        6 |                80 |        -3.45829 |        -3.45829 |               2887 |
|            61 | B6      |        6 |                80 |         1.96959 |         2.53207 |               2887 |
|            61 | B8      |        6 |                80 |         1.49512 |         1.49512 |               2887 |
|            62 | B4      |       10 |                80 |        -3.08133 |        -3.08133 |               3013 |
|            62 | B6      |       10 |                80 |         1.29471 |         2.34826 |               3013 |
|            62 | B8      |       10 |                80 |         1.24886 |         1.38419 |               3013 |
|            63 | B4      |       10 |                80 |        -3.18372 |        -3.18372 |               3450 |
|            63 | B6      |       10 |                80 |         1.32041 |         2.36041 |               3450 |
|            63 | B8      |       10 |                80 |         1.25448 |         1.3982  |               3450 |
|            65 | B4      |        6 |               320 |        -2.4049  |        -2.4049  |               3754 |
|            65 | B6      |        6 |               320 |         1.45157 |         2.17364 |               3754 |
|            65 | B8      |        6 |               320 |         1.38447 |         1.38447 |               3754 |

## 3. Run-held-out head-to-head

Every row trains templates, S03a, S03b, shared shrinkage, and HGB only on the other runs. Per-run intervals bootstrap pair residuals within the held-out run; pooled intervals resample held-out runs.

|   heldout_run | method                       |    value |   ci_low |   ci_high |   n_pair_residuals |   s03b_n_bins |   shrinkage_n_bins |   shrinkage_strength |   shrinkage_cv_sigma68_ns |   hgb_cv_sigma68_ns |
|--------------:|:-----------------------------|---------:|---------:|----------:|-------------------:|--------------:|-------------------:|---------------------:|--------------------------:|--------------------:|
|            58 | hgb_timewalk                 | 1.09746  | 0.982122 |  1.3145   |                219 |            10 |                  6 |                  320 |                   1.11649 |             1.4526  |
|            58 | phys_signed_shared_shrinkage | 0.556103 | 0.282582 |  0.750252 |                219 |            10 |                  6 |                  320 |                   1.11649 |             1.4526  |
|            58 | s03a_amp_only                | 1.18748  | 1.13483  |  1.35901  |                219 |            10 |                  6 |                  320 |                   1.11649 |             1.4526  |
|            58 | s03b_monotone_binned         | 1.3214   | 1.3214   |  1.57261  |                219 |            10 |                  6 |                  320 |                   1.11649 |             1.4526  |
|            58 | template_phase_base          | 2.6428   | 2.6428   |  2.77317  |                219 |            10 |                  6 |                  320 |                   1.11649 |             1.4526  |
|            59 | hgb_timewalk                 | 1.25688  | 1.21748  |  1.30951  |               2289 |             8 |                 10 |                   80 |                   1.10823 |             1.47146 |
|            59 | phys_signed_shared_shrinkage | 1.20326  | 1.09132  |  1.25352  |               2289 |             8 |                 10 |                   80 |                   1.10823 |             1.47146 |
|            59 | s03a_amp_only                | 1.45871  | 1.3928   |  1.52566  |               2289 |             8 |                 10 |                   80 |                   1.10823 |             1.47146 |
|            59 | s03b_monotone_binned         | 1.5      | 1.37046  |  1.56166  |               2289 |             8 |                 10 |                   80 |                   1.10823 |             1.47146 |
|            59 | template_phase_base          | 2.99232  | 2.99232  |  3.12333  |               2289 |             8 |                 10 |                   80 |                   1.10823 |             1.47146 |
|            60 | hgb_timewalk                 | 1.24359  | 1.18903  |  1.2872   |               2424 |             8 |                 10 |                   80 |                   1.11124 |             1.46156 |
|            60 | phys_signed_shared_shrinkage | 0.994186 | 0.862261 |  1.08841  |               2424 |             8 |                 10 |                   80 |                   1.11124 |             1.46156 |
|            60 | s03a_amp_only                | 1.3437   | 1.28895  |  1.4001   |               2424 |             8 |                 10 |                   80 |                   1.11124 |             1.46156 |
|            60 | s03b_monotone_binned         | 1.23065  | 1.23065  |  1.25006  |               2424 |             8 |                 10 |                   80 |                   1.11124 |             1.46156 |
|            60 | template_phase_base          | 2.66393  | 2.66393  |  2.7113   |               2424 |             8 |                 10 |                   80 |                   1.11124 |             1.46156 |
|            61 | hgb_timewalk                 | 1.8278   | 1.75361  |  1.93082  |               2799 |            12 |                  6 |                   80 |                   1.09046 |             1.37692 |
|            61 | phys_signed_shared_shrinkage | 1.6806   | 1.56014  |  1.78703  |               2799 |            12 |                  6 |                   80 |                   1.09046 |             1.37692 |
|            61 | s03a_amp_only                | 2.12996  | 1.98736  |  2.20065  |               2799 |            12 |                  6 |                   80 |                   1.09046 |             1.37692 |
|            61 | s03b_monotone_binned         | 2.10176  | 2.10176  |  2.24391  |               2799 |            12 |                  6 |                   80 |                   1.09046 |             1.37692 |
|            61 | template_phase_base          | 2.70351  | 2.70351  |  2.70351  |               2799 |            12 |                  6 |                   80 |                   1.09046 |             1.37692 |
|            62 | hgb_timewalk                 | 1.29727  | 1.25039  |  1.35762  |               2421 |             8 |                 10 |                   80 |                   1.1183  |             1.47264 |
|            62 | phys_signed_shared_shrinkage | 1.12895  | 1.06718  |  1.25311  |               2421 |             8 |                 10 |                   80 |                   1.1183  |             1.47264 |
|            62 | s03a_amp_only                | 1.469    | 1.41029  |  1.51026  |               2421 |             8 |                 10 |                   80 |                   1.1183  |             1.47264 |
|            62 | s03b_monotone_binned         | 1.43743  | 1.41759  |  1.56294  |               2421 |             8 |                 10 |                   80 |                   1.1183  |             1.47264 |
|            62 | template_phase_base          | 2.90117  | 2.90117  |  3.02631  |               2421 |             8 |                 10 |                   80 |                   1.1183  |             1.47264 |
|            63 | hgb_timewalk                 | 1.27044  | 1.17178  |  1.32092  |               1110 |             8 |                 10 |                   80 |                   1.1333  |             1.42911 |
|            63 | phys_signed_shared_shrinkage | 1.03314  | 0.929401 |  1.19835  |               1110 |             8 |                 10 |                   80 |                   1.1333  |             1.42911 |
|            63 | s03a_amp_only                | 1.39132  | 1.31708  |  1.45557  |               1110 |             8 |                 10 |                   80 |                   1.1333  |             1.42911 |
|            63 | s03b_monotone_binned         | 1.43311  | 1.31436  |  1.56436  |               1110 |             8 |                 10 |                   80 |                   1.1333  |             1.42911 |
|            63 | template_phase_base          | 2.87872  | 2.87872  |  3.01249  |               1110 |             8 |                 10 |                   80 |                   1.1333  |             1.42911 |
|            65 | hgb_timewalk                 | 1.35637  | 1.19409  |  1.5822   |                198 |            10 |                  6 |                  320 |                   1.11488 |             1.44514 |
|            65 | phys_signed_shared_shrinkage | 1.01656  | 0.762089 |  1.28246  |                198 |            10 |                  6 |                  320 |                   1.11488 |             1.44514 |
|            65 | s03a_amp_only                | 1.49464  | 1.33121  |  1.63359  |                198 |            10 |                  6 |                  320 |                   1.11488 |             1.44514 |
|            65 | s03b_monotone_binned         | 1.56958  | 1.31958  |  1.81958  |                198 |            10 |                  6 |                  320 |                   1.11488 |             1.44514 |
|            65 | template_phase_base          | 2.88915  | 2.63915  |  3.13915  |                198 |            10 |                  6 |                  320 |                   1.11488 |             1.44514 |

| method                       |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base          | 2.74141 |  2.68081 |   2.98617 |              11460 |             0.0813264 |
| s03a_amp_only                | 1.55109 |  1.37163 |   1.92525 |              11460 |             0.0191099 |
| s03b_monotone_binned         | 1.64515 |  1.32175 |   1.94446 |              11460 |             0.019459  |
| phys_signed_shared_shrinkage | 1.26727 |  1.00749 |   1.58377 |              11460 |             0.0180628 |
| hgb_timewalk                 | 1.39297 |  1.2531  |   1.65521 |              11460 |             0.0155323 |

## 4. Leakage checks

No fitted feature includes run number, event id, event order, other-stave timing, or held-out labels. Final models remove held-out rows. Shuffled-target controls are repeated for shared shrinkage, isotonic S03b, and HGB in every held-out fold.

The shared-shrinkage result is treated as a too-good leakage target because it beats HGB in the pooled run bootstrap (`shared_shrinkage_looks_too_good=True`). The direct checks remain clean: event-id overlap is `0`, held-out rows are excluded from final models, and the minimum shuffled-target sigma68 is `2.643 ns`, far above the true shared-shrinkage width.

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                       |     2.67189 |        2.87453 |     2.99164 |
| s03b_shuffled_target_sigma68                      |     2.65443 |        2.82703 |     2.9894  |
| shared_shrinkage_shuffled_target_sigma68          |     2.6428  |        2.86323 |     3.01776 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

## 5. Verdict

`result.json` verdict: `shared_shrinkage_beats_isotonic_no_leakage`.
Shared-shrinkage pooled sigma68 is `1.267 ns`; S03a amp-only is `1.551 ns`; S03b monotone-binned is `1.645 ns`; HGB is `1.393 ns`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781019517_3497_1b4352d9_shared_stave_shrinkage.py --config configs/s03f_1781019517_3497_1b4352d9_shared_stave_shrinkage.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `s03a_amp_only_cv_scan.csv`, `s03b_monotone_cv_scan.csv`, `shared_shrinkage_cv_scan.csv`, `shared_shrinkage_model_table.csv`, `hgb_cv_scan.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

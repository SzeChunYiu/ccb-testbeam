# Study report: S03d - Hierarchical analytic timewalk shrinkage vs S03b and ML

- **Ticket:** 1781020163.1096.2cf669f6
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03d_1781020163_1096_2cf669f6_hierarchical_s03b_ml.yaml`

## 0. Question

Does a run-level partial-pooling analytic timewalk model improve the S03c amp-only analytic correction while staying honest against S03b binned and ML comparators?

## 1. Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before any model fitting.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The run-65 S03a/S03b reference numbers were then reproduced from the same raw-derived pulse table before the main hierarchical and ML fits.

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   reference_value |       delta | pass   |
|:---------------------|--------:|---------:|----------:|-------------------:|------------------:|------------:|:-------|
| template_phase_base  | 2.88915 |  2.63915 |   3.20541 |                198 |           2.88915 | 0           | True   |
| s03a_amp_only_global | 1.49464 |  1.3359  |   1.63444 |                198 |           1.49464 | 5.55112e-15 | True   |
| s03b_binned_timewalk | 1.56958 |  1.31958 |   1.81958 |                198 |           1.56958 | 0           | True   |

## 2. Methods

The traditional references are the S03a amp-only Ridge correction and the S03b monotone amplitude-binned correction. The new traditional model uses the S03a amplitude/stave features but fits population coefficients plus run-specific coefficient deviations, with the deviations L2-shrunk and zeroed for unseen held-out runs. The ML comparator is an HGB residual corrector from the same template-phase base timing.

## 3. Held-out head-to-head

|   heldout_run | method                 |    value |   ci_low |   ci_high |   n_pair_residuals |   hier_alpha_global |   hier_alpha_dev |   hier_cv_sigma68_ns |   s03b_n_bins |   hgb_cv_sigma68_ns |
|--------------:|:-----------------------|---------:|---------:|----------:|-------------------:|--------------------:|-----------------:|---------------------:|--------------:|--------------------:|
|            58 | hgb_timewalk           | 1.0863   | 1.00328  |  1.31268  |                219 |                 100 |              100 |              1.16034 |            10 |             1.44907 |
|            58 | hierarchical_shrinkage | 0.766925 | 0.688813 |  0.991436 |                219 |                 100 |              100 |              1.16034 |            10 |             1.44907 |
|            58 | s03a_amp_only_global   | 1.18748  | 1.13422  |  1.3534   |                219 |                 100 |              100 |              1.16034 |            10 |             1.44907 |
|            58 | s03b_binned_timewalk   | 1.3214   | 1.3214   |  1.74628  |                219 |                 100 |              100 |              1.16034 |            10 |             1.44907 |
|            58 | template_phase_base    | 2.6428   | 2.6428   |  2.77317  |                219 |                 100 |              100 |              1.16034 |            10 |             1.44907 |
|            59 | hgb_timewalk           | 1.26298  | 1.21054  |  1.30766  |               2289 |                 100 |              100 |              1.16045 |             8 |             1.4637  |
|            59 | hierarchical_shrinkage | 1.22376  | 1.15715  |  1.24977  |               2289 |                 100 |              100 |              1.16045 |             8 |             1.4637  |
|            59 | s03a_amp_only_global   | 1.45871  | 1.39637  |  1.52093  |               2289 |                 100 |              100 |              1.16045 |             8 |             1.4637  |
|            59 | s03b_binned_timewalk   | 1.5      | 1.31166  |  1.56166  |               2289 |                 100 |              100 |              1.16045 |             8 |             1.4637  |
|            59 | template_phase_base    | 2.99232  | 2.99232  |  3.12333  |               2289 |                 100 |              100 |              1.16045 |             8 |             1.4637  |
|            60 | hgb_timewalk           | 1.22758  | 1.15518  |  1.27094  |               2424 |                 100 |              100 |              1.20608 |             8 |             1.45987 |
|            60 | hierarchical_shrinkage | 1.05251  | 1.00683  |  1.09946  |               2424 |                 100 |              100 |              1.20608 |             8 |             1.45987 |
|            60 | s03a_amp_only_global   | 1.3437   | 1.28997  |  1.40174  |               2424 |                 100 |              100 |              1.20608 |             8 |             1.45987 |
|            60 | s03b_binned_timewalk   | 1.23065  | 1.23065  |  1.25     |               2424 |                 100 |              100 |              1.20608 |             8 |             1.45987 |
|            60 | template_phase_base    | 2.66393  | 2.66393  |  2.7113   |               2424 |                 100 |              100 |              1.20608 |             8 |             1.45987 |
|            61 | hgb_timewalk           | 1.81739  | 1.74394  |  1.90927  |               2799 |                 100 |              100 |              1.07987 |            12 |             1.37105 |
|            61 | hierarchical_shrinkage | 1.63537  | 1.5525   |  1.67332  |               2799 |                 100 |              100 |              1.07987 |            12 |             1.37105 |
|            61 | s03a_amp_only_global   | 2.12996  | 2.00021  |  2.21033  |               2799 |                 100 |              100 |              1.07987 |            12 |             1.37105 |
|            61 | s03b_binned_timewalk   | 2.10176  | 2.10176  |  2.25329  |               2799 |                 100 |              100 |              1.07987 |            12 |             1.37105 |
|            61 | template_phase_base    | 2.70351  | 2.70351  |  2.70351  |               2799 |                 100 |              100 |              1.07987 |            12 |             1.37105 |
|            62 | hgb_timewalk           | 1.2974   | 1.24968  |  1.36981  |               2421 |                 100 |              100 |              1.14757 |             8 |             1.4747  |
|            62 | hierarchical_shrinkage | 1.18377  | 1.1078   |  1.25229  |               2421 |                 100 |              100 |              1.14757 |             8 |             1.4747  |
|            62 | s03a_amp_only_global   | 1.469    | 1.41746  |  1.51598  |               2421 |                 100 |              100 |              1.14757 |             8 |             1.4747  |
|            62 | s03b_binned_timewalk   | 1.43743  | 1.41452  |  1.57559  |               2421 |                 100 |              100 |              1.14757 |             8 |             1.4747  |
|            62 | template_phase_base    | 2.90117  | 2.90117  |  3.02631  |               2421 |                 100 |              100 |              1.14757 |             8 |             1.4747  |
|            63 | hgb_timewalk           | 1.27127  | 1.16638  |  1.33692  |               1110 |                 100 |              100 |              1.16078 |             8 |             1.42633 |
|            63 | hierarchical_shrinkage | 1.11004  | 1.02639  |  1.2081   |               1110 |                 100 |              100 |              1.16078 |             8 |             1.42633 |
|            63 | s03a_amp_only_global   | 1.39132  | 1.30584  |  1.46103  |               1110 |                 100 |              100 |              1.16078 |             8 |             1.42633 |
|            63 | s03b_binned_timewalk   | 1.43311  | 1.31436  |  1.56436  |               1110 |                 100 |              100 |              1.16078 |             8 |             1.42633 |
|            63 | template_phase_base    | 2.87872  | 2.87872  |  3.01249  |               1110 |                 100 |              100 |              1.16078 |             8 |             1.42633 |
|            65 | hgb_timewalk           | 1.36865  | 1.19206  |  1.62477  |                198 |                 100 |              100 |              1.16137 |            10 |             1.44745 |
|            65 | hierarchical_shrinkage | 1.21984  | 1.01706  |  1.42955  |                198 |                 100 |              100 |              1.16137 |            10 |             1.44745 |
|            65 | s03a_amp_only_global   | 1.49464  | 1.35107  |  1.6413   |                198 |                 100 |              100 |              1.16137 |            10 |             1.44745 |
|            65 | s03b_binned_timewalk   | 1.56958  | 1.31958  |  1.81958  |                198 |                 100 |              100 |              1.16137 |            10 |             1.44745 |
|            65 | template_phase_base    | 2.88915  | 2.63915  |  3.14337  |                198 |                 100 |              100 |              1.16137 |            10 |             1.44745 |

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base    | 2.74141 |  2.68243 |   2.99232 |              11460 |             0.0813264 |
| s03a_amp_only_global   | 1.55109 |  1.36966 |   1.94145 |              11460 |             0.0191099 |
| hierarchical_shrinkage | 1.251   |  1.08253 |   1.48477 |              11460 |             0.0153578 |
| s03b_binned_timewalk   | 1.64515 |  1.32559 |   1.94446 |              11460 |             0.019459  |
| hgb_timewalk           | 1.39397 |  1.23719 |   1.64765 |              11460 |             0.0156195 |

Run 61 rows:

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |
|:-----------------------|--------:|---------:|----------:|-------------------:|
| hgb_timewalk           | 1.81739 |  1.74394 |   1.90927 |               2799 |
| hierarchical_shrinkage | 1.63537 |  1.5525  |   1.67332 |               2799 |
| s03a_amp_only_global   | 2.12996 |  2.00021 |   2.21033 |               2799 |
| s03b_binned_timewalk   | 2.10176 |  2.10176 |   2.25329 |               2799 |
| template_phase_base    | 2.70351 |  2.70351 |   2.70351 |               2799 |

## 4. Drift diagnostic

The oracle adaptation is diagnostic only: it uses held-out labels to fit one extra run-specific deviation around the population coefficients, so it is not a deployable held-out score.

|   heldout_run |   population_sigma68_ns |   oracle_adapted_sigma68_ns |   oracle_gain_ns |   oracle_delta_l2_standardized |   n_heldout_pulses_for_oracle |
|--------------:|------------------------:|----------------------------:|-----------------:|-------------------------------:|------------------------------:|
|            58 |                0.766925 |                     1.35912 |        -0.592195 |                       0.45581  |                           219 |
|            59 |                1.22376  |                     1.60856 |        -0.3848   |                       0.606344 |                          2289 |
|            60 |                1.05251  |                     1.57488 |        -0.522371 |                       0.526635 |                          2424 |
|            61 |                1.63537  |                     1.55571 |         0.079661 |                       0.414593 |                          2799 |
|            62 |                1.18377  |                     1.61075 |        -0.426979 |                       0.419091 |                          2421 |
|            63 |                1.11004  |                     1.47121 |        -0.361172 |                       0.477044 |                          1110 |
|            65 |                1.21984  |                     1.3777  |        -0.157862 |                       0.352023 |                           198 |

## 5. Leakage checks

| check                                                 |   min_value |   median_value |   max_value |
|:------------------------------------------------------|------------:|---------------:|------------:|
| final_models_use_heldout_rows                         |     0       |        0       |     0       |
| hgb_features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| hgb_shuffled_target_sigma68                           |     2.66538 |        2.88812 |     3.0042  |
| hier_shuffled_target_sigma68                          |     2.62809 |        2.82072 |     3.05556 |
| hierarchical_heldout_run_deviation_zeroed             |     1       |        1       |     1       |
| s03a_shuffled_target_sigma68                          |     2.69439 |        2.83705 |     2.9801  |
| s03b_shuffled_target_sigma68                          |     2.65443 |        2.82703 |     2.9894  |
| train_heldout_event_id_overlap                        |     0       |        0       |     0       |

The HGB comparator excludes run number, event id, event order, other-stave timing, current, and held-out labels. The hierarchical analytic model intentionally has train-run deviation terms, but the held-out run deviation block is zeroed and no held-out rows or labels are used for promoted predictions. S03a, hierarchical, S03b, and HGB shuffled-target controls are repeated for every held-out run.

## 6. Verdict

`result.json` verdict: `run61_degradation_not_limited_stats_partial_coefficient_drift_no_leakage_flag`.
Hierarchical shrinkage pooled sigma68 is `1.251 ns`; global S03a is `1.551 ns`; S03b is `1.645 ns`; HGB is `1.394 ns`.
Run 61 has `2799` pair residuals, so the degradation is not a low-statistics fold; the diagnostic oracle gain is `0.080 ns`.

## 7. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03d_1781020163_1096_2cf669f6_hierarchical_s03b_ml.py --config configs/s03d_1781020163_1096_2cf669f6_hierarchical_s03b_ml.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hierarchical_cv_scan.csv`, `hierarchical_coefficients.csv`, `s03b_binned_cv_scan.csv`, `s03b_binned_model_table.csv`, `hgb_cv_scan.csv`, `run_drift_diagnostic.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

# Study report: S03d - Hierarchical analytic timewalk shrinkage

- **Ticket:** 1781011277.910.1e815d8f
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03d_1781011277_910_1e815d8f_hierarchical_timewalk.yaml`

## 0. Question

Does a run-level partial-pooling analytic timewalk model explain the run-61 degradation as coefficient drift, limited statistics, or model misspecification?

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

The run-65 S03a baseline numbers were then reproduced from the same raw-derived pulse table.

|   heldout_run | method               | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | train_runs        | s03a_candidate   |   s03a_alpha |   hier_alpha_global |   hier_alpha_dev |   hier_cv_sigma68_ns |   hgb_cv_sigma68_ns |   reference_value |       delta | pass   |
|--------------:|:---------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:------------------|:-----------------|-------------:|--------------------:|-----------------:|---------------------:|--------------------:|------------------:|------------:|:-------|
|            65 | template_phase_base  | heldout_pairwise_sigma68_ns | 2.88915 |  2.63915 |   3.20541 |                198 |    -3.83043 |      2.88915 |       2.57669 |            0.0505051  |        0.442691 |    3.21363 | 58,59,60,61,62,63 | amp_only         |          100 |                 100 |              100 |              1.16137 |             1.44745 |           2.88915 | 0           | True   |
|            65 | s03a_amp_only_global | heldout_pairwise_sigma68_ns | 1.49464 |  1.3359  |   1.63444 |                198 |     1.17923 |      1.49464 |       1.69913 |            0.00505051 |        1.26123  |    2.03718 | 58,59,60,61,62,63 | amp_only         |          100 |                 100 |              100 |              1.16137 |             1.44745 |           1.49464 | 5.55112e-15 | True   |

## 2. Methods

The traditional reference is the S03a amp-only Ridge correction. The hierarchical traditional model uses the same amplitude/stave features but fits population coefficients plus run-specific coefficient deviations, with the deviations L2-shrunk and zeroed for unseen held-out runs. The ML comparator is the HGB residual corrector from the same template-phase base timing.

## 3. Held-out head-to-head

|   heldout_run | method                 |    value |   ci_low |   ci_high |   n_pair_residuals |   hier_alpha_global |   hier_alpha_dev |   hier_cv_sigma68_ns |   hgb_cv_sigma68_ns |
|--------------:|:-----------------------|---------:|---------:|----------:|-------------------:|--------------------:|-----------------:|---------------------:|--------------------:|
|            58 | hgb_timewalk           | 1.0863   | 0.995626 |   1.31036 |                219 |                 100 |              100 |              1.16034 |             1.44907 |
|            58 | hierarchical_shrinkage | 0.766925 | 0.682991 |   1.02619 |                219 |                 100 |              100 |              1.16034 |             1.44907 |
|            58 | s03a_amp_only_global   | 1.18748  | 1.13617  |   1.35217 |                219 |                 100 |              100 |              1.16034 |             1.44907 |
|            58 | template_phase_base    | 2.6428   | 2.6428   |   2.77317 |                219 |                 100 |              100 |              1.16034 |             1.44907 |
|            59 | hgb_timewalk           | 1.26298  | 1.21579  |   1.30746 |               2289 |                 100 |              100 |              1.16045 |             1.4637  |
|            59 | hierarchical_shrinkage | 1.22376  | 1.16226  |   1.25401 |               2289 |                 100 |              100 |              1.16045 |             1.4637  |
|            59 | s03a_amp_only_global   | 1.45871  | 1.3968   |   1.51993 |               2289 |                 100 |              100 |              1.16045 |             1.4637  |
|            59 | template_phase_base    | 2.99232  | 2.99232  |   3.12333 |               2289 |                 100 |              100 |              1.16045 |             1.4637  |
|            60 | hgb_timewalk           | 1.22758  | 1.16009  |   1.26766 |               2424 |                 100 |              100 |              1.20608 |             1.45987 |
|            60 | hierarchical_shrinkage | 1.05251  | 1.01034  |   1.09988 |               2424 |                 100 |              100 |              1.20608 |             1.45987 |
|            60 | s03a_amp_only_global   | 1.3437   | 1.28684  |   1.3986  |               2424 |                 100 |              100 |              1.20608 |             1.45987 |
|            60 | template_phase_base    | 2.66393  | 2.66393  |   2.7113  |               2424 |                 100 |              100 |              1.20608 |             1.45987 |
|            61 | hgb_timewalk           | 1.81739  | 1.7489   |   1.92416 |               2799 |                 100 |              100 |              1.07987 |             1.37105 |
|            61 | hierarchical_shrinkage | 1.63537  | 1.53498  |   1.67597 |               2799 |                 100 |              100 |              1.07987 |             1.37105 |
|            61 | s03a_amp_only_global   | 2.12996  | 1.99877  |   2.20287 |               2799 |                 100 |              100 |              1.07987 |             1.37105 |
|            61 | template_phase_base    | 2.70351  | 2.70351  |   2.70351 |               2799 |                 100 |              100 |              1.07987 |             1.37105 |
|            62 | hgb_timewalk           | 1.2974   | 1.25529  |   1.36588 |               2421 |                 100 |              100 |              1.14757 |             1.4747  |
|            62 | hierarchical_shrinkage | 1.18377  | 1.10994  |   1.25899 |               2421 |                 100 |              100 |              1.14757 |             1.4747  |
|            62 | s03a_amp_only_global   | 1.469    | 1.41663  |   1.52029 |               2421 |                 100 |              100 |              1.14757 |             1.4747  |
|            62 | template_phase_base    | 2.90117  | 2.90117  |   3.02631 |               2421 |                 100 |              100 |              1.14757 |             1.4747  |
|            63 | hgb_timewalk           | 1.27127  | 1.17346  |   1.33548 |               1110 |                 100 |              100 |              1.16078 |             1.42633 |
|            63 | hierarchical_shrinkage | 1.11004  | 1.03051  |   1.20376 |               1110 |                 100 |              100 |              1.16078 |             1.42633 |
|            63 | s03a_amp_only_global   | 1.39132  | 1.31472  |   1.4536  |               1110 |                 100 |              100 |              1.16078 |             1.42633 |
|            63 | template_phase_base    | 2.87872  | 2.87872  |   3.01249 |               1110 |                 100 |              100 |              1.16078 |             1.42633 |
|            65 | hgb_timewalk           | 1.36865  | 1.17132  |   1.61234 |                198 |                 100 |              100 |              1.16137 |             1.44745 |
|            65 | hierarchical_shrinkage | 1.21984  | 1.01722  |   1.41556 |                198 |                 100 |              100 |              1.16137 |             1.44745 |
|            65 | s03a_amp_only_global   | 1.49464  | 1.35215  |   1.63019 |                198 |                 100 |              100 |              1.16137 |             1.44745 |
|            65 | template_phase_base    | 2.88915  | 2.63915  |   3.20541 |                198 |                 100 |              100 |              1.16137 |             1.44745 |

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base    | 2.74141 |  2.68081 |   2.98617 |              11460 |             0.0813264 |
| s03a_amp_only_global   | 1.55109 |  1.37843 |   1.88011 |              11460 |             0.0191099 |
| hierarchical_shrinkage | 1.251   |  1.07673 |   1.48553 |              11460 |             0.0153578 |
| hgb_timewalk           | 1.39397 |  1.24022 |   1.65627 |              11460 |             0.0156195 |

Run 61 rows:

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |
|:-----------------------|--------:|---------:|----------:|-------------------:|
| hgb_timewalk           | 1.81739 |  1.7489  |   1.92416 |               2799 |
| hierarchical_shrinkage | 1.63537 |  1.53498 |   1.67597 |               2799 |
| s03a_amp_only_global   | 2.12996 |  1.99877 |   2.20287 |               2799 |
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
| train_heldout_event_id_overlap                        |     0       |        0       |     0       |

The HGB comparator excludes run number, event id, event order, other-stave timing, current, and held-out labels. The hierarchical analytic model intentionally has train-run deviation terms, but the held-out run deviation block is zeroed and no held-out rows or labels are used for promoted predictions. Shuffled-target controls are repeated for every held-out run.

## 6. Verdict

`result.json` verdict: `run61_degradation_not_limited_stats_partial_coefficient_drift_no_leakage_flag`.
Hierarchical shrinkage pooled sigma68 is `1.251 ns`; global S03a is `1.551 ns`; HGB is `1.394 ns`.
Run 61 has `2799` pair residuals, so the degradation is not a low-statistics fold; the diagnostic oracle gain is `0.080 ns`.

## 7. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03d_1781011277_910_1e815d8f_hierarchical_timewalk.py --config configs/s03d_1781011277_910_1e815d8f_hierarchical_timewalk.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hierarchical_cv_scan.csv`, `hierarchical_coefficients.csv`, `hgb_cv_scan.csv`, `run_drift_diagnostic.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

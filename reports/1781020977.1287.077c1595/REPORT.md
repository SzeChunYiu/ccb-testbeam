# Study report: S03f - Hierarchical signed shrinkage

- **Ticket:** 1781020977.1287.077c1595
- **Author:** testbeam-laptop-1
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03f_hierarchical_signed_shrinkage_1781020977.yaml`

## 0. Question

Does partial pooling of physically signed inverse-amplitude slopes across staves and train runs rescue the B4 zero-slope clipping seen in S03d and improve the broad held-out run 61 without leakage?

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

The S03a/S03b run-65 reference numbers and the prior S03d pooled headline were reproduced from the same raw-derived pulse table before accepting S03f.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

| method                  | metric                                       | bootstrap_unit   |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf |   reference_value |        delta |   tolerance | pass   |
|:------------------------|:---------------------------------------------|:-----------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|------------------:|-------------:|------------:|:-------|
| hgb_timewalk            | pooled_leave_one_run_out_pairwise_sigma68_ns | heldout_run      | 1.39419 |  1.25643 |   1.65788 |              11460 |     1.38954 |      1.39419 |       2.37541 |             0.0155323 |         1.49108 |    40.0699 |           1.39297 |  0.00122327  |       0.005 | True   |
| phys_signed_inverse_amp | pooled_leave_one_run_out_pairwise_sigma68_ns | heldout_run      | 1.60436 |  1.38526 |   1.94837 |              11460 |     1.54428 |      1.60436 |       2.68732 |             0.0205934 |         1.68256 |    49.7334 |           1.60436 |  0           |       1e-09 | True   |
| s03a_amp_only           | pooled_leave_one_run_out_pairwise_sigma68_ns | heldout_run      | 1.55109 |  1.36625 |   1.89939 |              11460 |     1.49475 |      1.55109 |       2.66699 |             0.0191099 |         1.62138 |    47.0186 |           1.55109 | -2.22045e-16 |       1e-09 | True   |
| s03b_monotone_binned    | pooled_leave_one_run_out_pairwise_sigma68_ns | heldout_run      | 1.64515 |  1.32175 |   1.9446  |              11460 |     1.42566 |      1.64515 |       2.71603 |             0.019459  |         1.74012 |   116.704  |           1.64515 |  0           |       1e-09 | True   |
| template_phase_base     | pooled_leave_one_run_out_pairwise_sigma68_ns | heldout_run      | 2.74141 |  2.68422 |   2.99232 |              11460 |    -3.72262 |      2.74141 |       3.30837 |             0.0813264 |         1.43787 |   145.195  |           2.74141 |  0           |       1e-09 | True   |

## 2. Methods

The S03f traditional method fits per-stave intercepts, train-run offsets, and nonnegative inverse-amplitude slopes. Run/stave slopes are shrunk toward pooled stave slopes, which are shrunk toward a global signed slope; held-out runs never get run-specific slope terms and use only the pooled stave slope. Power and shrinkage strength are chosen by grouped train-run CV.

S03d B4 per-fold signed slopes:

|   heldout_run |   signed_slope_ns |   unconstrained_slope_ns | slope_clipped_to_physical_sign   |
|--------------:|------------------:|-------------------------:|:---------------------------------|
|            58 |                 0 |                -1.03545  | True                             |
|            59 |                 0 |                -1.4316   | True                             |
|            60 |                 0 |                -1.54571  | True                             |
|            61 |                 0 |                -0.936428 | True                             |
|            62 |                 0 |                -1.15781  | True                             |
|            63 |                 0 |                -1.34474  | True                             |
|            65 |                 0 |                -1.16205  | True                             |

S03f pooled stave slopes used for unseen held-out runs:

|   heldout_run | feature        |   coefficient | at_positive_bound   |   power |   shrink_lambda |
|--------------:|:---------------|--------------:|:--------------------|--------:|----------------:|
|            58 | slope_stave_B4 |     0.35392   | False               |     0.5 |             100 |
|            58 | slope_stave_B6 |     0.882616  | False               |     0.5 |             100 |
|            58 | slope_stave_B8 |     1.74963   | False               |     0.5 |             100 |
|            59 | slope_stave_B4 |     0.336767  | False               |     0.5 |             100 |
|            59 | slope_stave_B6 |     0.834801  | False               |     0.5 |             100 |
|            59 | slope_stave_B8 |     1.60533   | False               |     0.5 |             100 |
|            60 | slope_stave_B4 |     0.295605  | False               |     1   |             100 |
|            60 | slope_stave_B6 |     0.522641  | False               |     1   |             100 |
|            60 | slope_stave_B8 |     1.31809   | False               |     1   |             100 |
|            61 | slope_stave_B4 |     0.0959025 | False               |     1   |             100 |
|            61 | slope_stave_B6 |     0.371418  | False               |     1   |             100 |
|            61 | slope_stave_B8 |     1.0297    | False               |     1   |             100 |
|            62 | slope_stave_B4 |     0.631194  | False               |     0.5 |             100 |
|            62 | slope_stave_B6 |     1.208     | False               |     0.5 |             100 |
|            62 | slope_stave_B8 |     1.96617   | False               |     0.5 |             100 |
|            63 | slope_stave_B4 |     0.370931  | False               |     0.5 |             100 |
|            63 | slope_stave_B6 |     0.928325  | False               |     0.5 |             100 |
|            63 | slope_stave_B8 |     1.81694   | False               |     0.5 |             100 |
|            65 | slope_stave_B4 |     0.330473  | False               |     0.5 |             100 |
|            65 | slope_stave_B6 |     0.858453  | False               |     0.5 |             100 |
|            65 | slope_stave_B8 |     1.7625    | False               |     0.5 |             100 |

## 3. Run-held-out head-to-head

|   heldout_run | method                        |   value |   ci_low |   ci_high |   n_pair_residuals |   phys_signed_power |   hier_power |   hier_shrink_lambda |   hier_cv_sigma68_ns |   hgb_cv_sigma68_ns |
|--------------:|:------------------------------|--------:|---------:|----------:|-------------------:|--------------------:|-------------:|---------------------:|---------------------:|--------------------:|
|            58 | hgb_timewalk                  | 1.10725 |  1.01597 |   1.38827 |                219 |                   1 |          0.5 |                  100 |              1.57751 |             1.4526  |
|            58 | hierarchical_signed_shrinkage | 1.25028 |  1.20581 |   1.324   |                219 |                   1 |          0.5 |                  100 |              1.57751 |             1.4526  |
|            58 | phys_signed_inverse_amp       | 1.23067 |  1.17821 |   1.32347 |                219 |                   1 |          0.5 |                  100 |              1.57751 |             1.4526  |
|            58 | s03a_amp_only                 | 1.18748 |  1.13497 |   1.35223 |                219 |                   1 |          0.5 |                  100 |              1.57751 |             1.4526  |
|            58 | s03b_monotone_binned          | 1.3214  |  1.3214  |   1.58146 |                219 |                   1 |          0.5 |                  100 |              1.57751 |             1.4526  |
|            58 | template_phase_base           | 2.6428  |  2.6428  |   2.77317 |                219 |                   1 |          0.5 |                  100 |              1.57751 |             1.4526  |
|            59 | hgb_timewalk                  | 1.25688 |  1.21555 |   1.29932 |               2289 |                   1 |          0.5 |                  100 |              1.57832 |             1.47146 |
|            59 | hierarchical_signed_shrinkage | 1.4272  |  1.38752 |   1.51092 |               2289 |                   1 |          0.5 |                  100 |              1.57832 |             1.47146 |
|            59 | phys_signed_inverse_amp       | 1.4595  |  1.38146 |   1.55284 |               2289 |                   1 |          0.5 |                  100 |              1.57832 |             1.47146 |
|            59 | s03a_amp_only                 | 1.45871 |  1.39838 |   1.52326 |               2289 |                   1 |          0.5 |                  100 |              1.57832 |             1.47146 |
|            59 | s03b_monotone_binned          | 1.5     |  1.35407 |   1.56166 |               2289 |                   1 |          0.5 |                  100 |              1.57832 |             1.47146 |
|            59 | template_phase_base           | 2.99232 |  2.99232 |   3.12333 |               2289 |                   1 |          0.5 |                  100 |              1.57832 |             1.47146 |
|            60 | hgb_timewalk                  | 1.24359 |  1.18734 |   1.28753 |               2424 |                   1 |          1   |                  100 |              1.58641 |             1.46156 |
|            60 | hierarchical_signed_shrinkage | 1.32122 |  1.28576 |   1.45498 |               2424 |                   1 |          1   |                  100 |              1.58641 |             1.46156 |
|            60 | phys_signed_inverse_amp       | 1.38154 |  1.29808 |   1.43904 |               2424 |                   1 |          1   |                  100 |              1.58641 |             1.46156 |
|            60 | s03a_amp_only                 | 1.3437  |  1.28656 |   1.39985 |               2424 |                   1 |          1   |                  100 |              1.58641 |             1.46156 |
|            60 | s03b_monotone_binned          | 1.23065 |  1.23065 |   1.25    |               2424 |                   1 |          1   |                  100 |              1.58641 |             1.46156 |
|            60 | template_phase_base           | 2.66393 |  2.66393 |   2.7113  |               2424 |                   1 |          1   |                  100 |              1.58641 |             1.46156 |
|            61 | hgb_timewalk                  | 1.8278  |  1.74095 |   1.92138 |               2799 |                   1 |          1   |                  100 |              1.50315 |             1.37692 |
|            61 | hierarchical_signed_shrinkage | 2.13034 |  2.00254 |   2.22835 |               2799 |                   1 |          1   |                  100 |              1.50315 |             1.37692 |
|            61 | phys_signed_inverse_amp       | 2.16735 |  2.02283 |   2.29433 |               2799 |                   1 |          1   |                  100 |              1.50315 |             1.37692 |
|            61 | s03a_amp_only                 | 2.12996 |  1.99473 |   2.20671 |               2799 |                   1 |          1   |                  100 |              1.50315 |             1.37692 |
|            61 | s03b_monotone_binned          | 2.10176 |  2.10176 |   2.25    |               2799 |                   1 |          1   |                  100 |              1.50315 |             1.37692 |
|            61 | template_phase_base           | 2.70351 |  2.70351 |   2.70351 |               2799 |                   1 |          1   |                  100 |              1.50315 |             1.37692 |
|            62 | hgb_timewalk                  | 1.29727 |  1.25227 |   1.36362 |               2421 |                   1 |          0.5 |                  100 |              1.57317 |             1.47264 |
|            62 | hierarchical_signed_shrinkage | 1.44815 |  1.38205 |   1.54342 |               2421 |                   1 |          0.5 |                  100 |              1.57317 |             1.47264 |
|            62 | phys_signed_inverse_amp       | 1.50023 |  1.44545 |   1.55205 |               2421 |                   1 |          0.5 |                  100 |              1.57317 |             1.47264 |
|            62 | s03a_amp_only                 | 1.469   |  1.41694 |   1.52065 |               2421 |                   1 |          0.5 |                  100 |              1.57317 |             1.47264 |
|            62 | s03b_monotone_binned          | 1.43743 |  1.42027 |   1.57635 |               2421 |                   1 |          0.5 |                  100 |              1.57317 |             1.47264 |
|            62 | template_phase_base           | 2.90117 |  2.90117 |   3.02631 |               2421 |                   1 |          0.5 |                  100 |              1.57317 |             1.47264 |
|            63 | hgb_timewalk                  | 1.27226 |  1.16798 |   1.34402 |               1110 |                   1 |          0.5 |                  100 |              1.56721 |             1.42911 |
|            63 | hierarchical_signed_shrinkage | 1.31972 |  1.28556 |   1.42169 |               1110 |                   1 |          0.5 |                  100 |              1.56721 |             1.42911 |
|            63 | phys_signed_inverse_amp       | 1.34247 |  1.27669 |   1.44541 |               1110 |                   1 |          0.5 |                  100 |              1.56721 |             1.42911 |
|            63 | s03a_amp_only                 | 1.39132 |  1.30842 |   1.45859 |               1110 |                   1 |          0.5 |                  100 |              1.56721 |             1.42911 |
|            63 | s03b_monotone_binned          | 1.43311 |  1.31436 |   1.56436 |               1110 |                   1 |          0.5 |                  100 |              1.56721 |             1.42911 |
|            63 | template_phase_base           | 2.87872 |  2.87872 |   3.01249 |               1110 |                   1 |          0.5 |                  100 |              1.56721 |             1.42911 |
|            65 | hgb_timewalk                  | 1.34232 |  1.20659 |   1.56622 |                198 |                   1 |          0.5 |                  100 |              1.58462 |             1.44514 |
|            65 | hierarchical_signed_shrinkage | 1.53672 |  1.36319 |   1.70631 |                198 |                   1 |          0.5 |                  100 |              1.58462 |             1.44514 |
|            65 | phys_signed_inverse_amp       | 1.55529 |  1.35778 |   1.65447 |                198 |                   1 |          0.5 |                  100 |              1.58462 |             1.44514 |
|            65 | s03a_amp_only                 | 1.49464 |  1.35073 |   1.63634 |                198 |                   1 |          0.5 |                  100 |              1.58462 |             1.44514 |
|            65 | s03b_monotone_binned          | 1.56958 |  1.33531 |   1.81958 |                198 |                   1 |          0.5 |                  100 |              1.58462 |             1.44514 |
|            65 | template_phase_base           | 2.88915 |  2.63915 |   3.20513 |                198 |                   1 |          0.5 |                  100 |              1.58462 |             1.44514 |

| method                        |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base           | 2.74141 |  2.68422 |   2.99232 |              11460 |             0.0813264 |
| s03a_amp_only                 | 1.55109 |  1.36625 |   1.89939 |              11460 |             0.0191099 |
| s03b_monotone_binned          | 1.64515 |  1.32175 |   1.9446  |              11460 |             0.019459  |
| phys_signed_inverse_amp       | 1.60436 |  1.38526 |   1.94837 |              11460 |             0.0205934 |
| hierarchical_signed_shrinkage | 1.56809 |  1.34059 |   1.92228 |              11460 |             0.0211169 |
| hgb_timewalk                  | 1.39419 |  1.25643 |   1.65788 |              11460 |             0.0155323 |

## 4. Leakage checks

All model selection is grouped by run. Final models are trained with the held-out run removed. Features exclude run number, event id, event order, other-stave timing, and held-out labels; run offsets are fit only for train runs and are unavailable to held-out runs.

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                       |     2.67837 |        2.8732  |     3.03576 |
| hierarchical_shuffled_target_sigma68              |     2.67711 |        2.86253 |     2.96631 |
| phys_signed_shuffled_target_sigma68               |     2.54058 |        2.8559  |     3.00828 |
| s03b_shuffled_target_sigma68                      |     2.65183 |        2.89022 |     2.99265 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

## 5. Verdict

`result.json` verdict: `hierarchical_shrinkage_improves_signed_prior_no_leakage`.
Hierarchical signed shrinkage pooled sigma68 is `1.568 ns`; S03d signed prior is `1.604 ns`; S03b is `1.645 ns`; HGB is `1.394 ns`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781020977_1287_077c1595_hierarchical_signed_shrinkage.py --config configs/s03f_hierarchical_signed_shrinkage_1781020977.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `s03d_headline_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV scans, model tables, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

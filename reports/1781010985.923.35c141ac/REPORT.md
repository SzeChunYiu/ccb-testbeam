# Study report: S03d - Leave-one-run-out S03a/S03b stability

- **Ticket:** 1781010985.923.35c141ac
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03d_leave_one_run_s03ab_hgb_stability.yaml`

## 0. Question

Do the S03a amp-only and S03b monotone-binned/HGB corrections remain stable when every Sample-II analysis run is held out in turn instead of relying on run 65 only?

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

The run-65 S03a/S03b numbers were then reproduced from the same raw-derived pulse table.

|   heldout_run | method               | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | train_runs        | s03a_candidate   |   s03a_alpha | s03b_mode   | s03b_direction   |   s03b_n_bins |   hgb_cv_sigma68_ns |   reference_value |       delta | pass   |
|--------------:|:---------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:------------------|:-----------------|-------------:|:------------|:-----------------|--------------:|--------------------:|------------------:|------------:|:-------|
|            65 | template_phase_base  | heldout_pairwise_sigma68_ns | 2.88915 |  2.63915 |   3.20541 |                198 |    -3.83043 |      2.88915 |       2.57669 |            0.0505051  |        0.442691 |    3.21363 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |             1.44745 |           2.88915 | 0           | True   |
|            65 | s03a_amp_only        | heldout_pairwise_sigma68_ns | 1.49464 |  1.33462 |   1.62481 |                198 |     1.17923 |      1.49464 |       1.69913 |            0.00505051 |        1.26123  |    2.03718 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |             1.44745 |           1.49464 | 5.55112e-15 | True   |
|            65 | s03b_monotone_binned | heldout_pairwise_sigma68_ns | 1.56958 |  1.31958 |   1.81958 |                198 |     1.03364 |      1.56958 |       1.83396 |            0.00505051 |        0.325573 |    3.14128 | 58,59,60,61,62,63 | amp_only         |          100 | monotonic   | decreasing       |            10 |             1.44745 |           1.56958 | 0           | True   |

## 2. Leave-one-run-out head-to-head

For each fold, templates, S03a amp-only Ridge, S03b monotone-binned isotonic correction, and HGB residual correction were trained only on the other Sample-II analysis runs. Intervals on per-run rows bootstrap pair residuals within the held-out run; pooled intervals resample held-out runs.

|   heldout_run | method               |   value |   ci_low |   ci_high |   n_pair_residuals |   s03b_n_bins |   hgb_cv_sigma68_ns |
|--------------:|:---------------------|--------:|---------:|----------:|-------------------:|--------------:|--------------------:|
|            58 | hgb_timewalk         | 1.0863  | 0.996459 |   1.30403 |                219 |            10 |             1.44907 |
|            58 | s03a_amp_only        | 1.18748 | 1.13553  |   1.35784 |                219 |            10 |             1.44907 |
|            58 | s03b_monotone_binned | 1.3214  | 1.3214   |   1.58146 |                219 |            10 |             1.44907 |
|            58 | template_phase_base  | 2.6428  | 2.6428   |   2.77317 |                219 |            10 |             1.44907 |
|            59 | hgb_timewalk         | 1.26298 | 1.21446  |   1.30186 |               2289 |             8 |             1.4637  |
|            59 | s03a_amp_only        | 1.45871 | 1.39399  |   1.52665 |               2289 |             8 |             1.4637  |
|            59 | s03b_monotone_binned | 1.5     | 1.36798  |   1.56166 |               2289 |             8 |             1.4637  |
|            59 | template_phase_base  | 2.99232 | 2.99232  |   3.12333 |               2289 |             8 |             1.4637  |
|            60 | hgb_timewalk         | 1.22758 | 1.15971  |   1.27252 |               2424 |             8 |             1.45987 |
|            60 | s03a_amp_only        | 1.3437  | 1.28866  |   1.39704 |               2424 |             8 |             1.45987 |
|            60 | s03b_monotone_binned | 1.23065 | 1.23065  |   1.25003 |               2424 |             8 |             1.45987 |
|            60 | template_phase_base  | 2.66393 | 2.66393  |   2.7113  |               2424 |             8 |             1.45987 |
|            61 | hgb_timewalk         | 1.81739 | 1.7388   |   1.91557 |               2799 |            12 |             1.37105 |
|            61 | s03a_amp_only        | 2.12996 | 1.99445  |   2.20323 |               2799 |            12 |             1.37105 |
|            61 | s03b_monotone_binned | 2.10176 | 2.10176  |   2.24381 |               2799 |            12 |             1.37105 |
|            61 | template_phase_base  | 2.70351 | 2.70351  |   2.70351 |               2799 |            12 |             1.37105 |
|            62 | hgb_timewalk         | 1.2974  | 1.25456  |   1.36881 |               2421 |             8 |             1.4747  |
|            62 | s03a_amp_only        | 1.469   | 1.41563  |   1.5122  |               2421 |             8 |             1.4747  |
|            62 | s03b_monotone_binned | 1.43743 | 1.39031  |   1.5756  |               2421 |             8 |             1.4747  |
|            62 | template_phase_base  | 2.90117 | 2.90117  |   3.02631 |               2421 |             8 |             1.4747  |
|            63 | hgb_timewalk         | 1.27127 | 1.15852  |   1.33306 |               1110 |             8 |             1.42633 |
|            63 | s03a_amp_only        | 1.39132 | 1.30871  |   1.46124 |               1110 |             8 |             1.42633 |
|            63 | s03b_monotone_binned | 1.43311 | 1.31436  |   1.56436 |               1110 |             8 |             1.42633 |
|            63 | template_phase_base  | 2.87872 | 2.87872  |   3.01249 |               1110 |             8 |             1.42633 |
|            65 | hgb_timewalk         | 1.36865 | 1.18609  |   1.5998  |                198 |            10 |             1.44745 |
|            65 | s03a_amp_only        | 1.49464 | 1.34034  |   1.65326 |                198 |            10 |             1.44745 |
|            65 | s03b_monotone_binned | 1.56958 | 1.31958  |   1.81958 |                198 |            10 |             1.44745 |
|            65 | template_phase_base  | 2.88915 | 2.63915  |   3.13915 |                198 |            10 |             1.44745 |

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base  | 2.74141 |  2.68945 |   2.99232 |              11460 |             0.0813264 |
| s03a_amp_only        | 1.55109 |  1.3685  |   1.92529 |              11460 |             0.0191099 |
| s03b_monotone_binned | 1.64515 |  1.32175 |   1.93055 |              11460 |             0.019459  |
| hgb_timewalk         | 1.39397 |  1.24165 |   1.68228 |              11460 |             0.0156195 |

## 3. Leakage checks

No fitted feature includes run number, event id, event order, other-stave timing, or held-out labels. Every final model is fit with held-out rows removed. Shuffled-target controls are repeated independently for every held-out run.

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |      1      |
| final_models_use_heldout_rows                     |     0       |        0       |      0      |
| hgb_shuffled_target_sigma68                       |     2.66538 |        2.88812 |      3.0042 |
| s03b_shuffled_target_sigma68                      |     2.65443 |        2.82703 |      2.9894 |
| train_heldout_event_id_overlap                    |     0       |        0       |      0      |

## 4. Verdict

`result.json` verdict: `stable_no_leakage_flag`.
S03a amp-only pooled sigma68 is `1.551 ns`; S03b monotone-binned is `1.645 ns`; HGB is `1.394 ns`.

## 5. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03d_leave_one_run_s03ab_hgb_stability.py --config configs/s03d_leave_one_run_s03ab_hgb_stability.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `s03a_amp_only_cv_scan.csv`, `s03b_monotone_cv_scan.csv`, `hgb_cv_scan.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

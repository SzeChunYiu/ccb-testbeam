# Study report: S03c - Multi-heldout-run timewalk stability

- **Ticket:** 1781011005.880.1cb53153
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03c_1781011005_880_1cb53153.yaml`

## 0. Question

Does the S03a amp-only analytic advantage over the S03b binned monotonic timewalk method survive leave-one-run-out evaluation across Sample-II analysis runs instead of only held-out run 65?

## 1. Raw-ROOT reproduction gate

Before fitting, the S00 selected-pulse counts were rerun from the raw ROOT files.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The original S03a run-65 point estimates were then reproduced from the same raw pass.

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   s03a_report_value |   delta_ns | pass   |
|:---------------------------|--------:|---------:|----------:|-------------------:|--------------------:|-----------:|:-------|
| template_phase_base        | 2.88915 |  2.63915 |   3.20541 |                198 |             2.88915 |          0 | True   |
| analytic_timewalk          | 1.49464 |  1.33462 |   1.62481 |                198 |             1.49464 |          0 | True   |
| s03b_binned_timewalk       | 1.56958 |  1.31958 |   1.81958 |                198 |             1.56958 |          0 | True   |
| ml_ridge_on_template_phase | 1.39153 |  1.28857 |   1.60848 |                198 |             1.39153 |          0 | True   |

## 2. Leave-one-run-out results

For each held-out run, templates and residual-correction models were trained only on the other Sample-II analysis runs. Traditional comparators are the S03a analytic timewalk Ridge scan and the S03b per-stave amplitude-binned timewalk scan; the ML model is the waveform-feature Ridge residual corrector on template phase.

|   heldout_run | method                     |   value |   ci_low |   ci_high |   n_pair_residuals | analytic_candidate   |   analytic_alpha | binned_mode   | binned_direction   |   binned_n_bins |
|--------------:|:---------------------------|--------:|---------:|----------:|-------------------:|:---------------------|-----------------:|:--------------|:-------------------|----------------:|
|            58 | analytic_timewalk          | 1.18748 |  1.13553 |   1.35784 |                219 | amp_only             |              100 | unconstrained | none               |              10 |
|            58 | ml_ridge_on_template_phase | 1.27047 |  1.15242 |   1.42072 |                219 | amp_only             |              100 | unconstrained | none               |              10 |
|            58 | s03b_binned_timewalk       | 1.3214  |  1.3214  |   1.58146 |                219 | amp_only             |              100 | unconstrained | none               |              10 |
|            58 | template_phase_base        | 2.6428  |  2.6428  |   2.77317 |                219 | amp_only             |              100 | unconstrained | none               |              10 |
|            59 | analytic_timewalk          | 1.45871 |  1.39399 |   1.52665 |               2289 | amp_only             |              100 | unconstrained | none               |               8 |
|            59 | ml_ridge_on_template_phase | 1.49843 |  1.4307  |   1.55037 |               2289 | amp_only             |              100 | unconstrained | none               |               8 |
|            59 | s03b_binned_timewalk       | 1.5     |  1.36798 |   1.56166 |               2289 | amp_only             |              100 | unconstrained | none               |               8 |
|            59 | template_phase_base        | 2.99232 |  2.99232 |   3.12333 |               2289 | amp_only             |              100 | unconstrained | none               |               8 |
|            60 | analytic_timewalk          | 1.3437  |  1.28866 |   1.39704 |               2424 | amp_only             |              100 | unconstrained | none               |               8 |
|            60 | ml_ridge_on_template_phase | 1.30605 |  1.26441 |   1.35315 |               2424 | amp_only             |              100 | unconstrained | none               |               8 |
|            60 | s03b_binned_timewalk       | 1.23065 |  1.23065 |   1.25003 |               2424 | amp_only             |              100 | unconstrained | none               |               8 |
|            60 | template_phase_base        | 2.66393 |  2.66393 |   2.7113  |               2424 | amp_only             |              100 | unconstrained | none               |               8 |
|            61 | analytic_timewalk          | 2.12996 |  1.99445 |   2.20323 |               2799 | amp_only             |              100 | unconstrained | none               |              10 |
|            61 | ml_ridge_on_template_phase | 1.96998 |  1.89139 |   2.05697 |               2799 | amp_only             |              100 | unconstrained | none               |              10 |
|            61 | s03b_binned_timewalk       | 2.10176 |  2.10176 |   2.15729 |               2799 | amp_only             |              100 | unconstrained | none               |              10 |
|            61 | template_phase_base        | 2.70351 |  2.70351 |   2.70351 |               2799 | amp_only             |              100 | unconstrained | none               |              10 |
|            62 | analytic_timewalk          | 1.469   |  1.41563 |   1.5122  |               2421 | amp_only             |              100 | monotonic     | decreasing         |               8 |
|            62 | ml_ridge_on_template_phase | 1.44698 |  1.39225 |   1.50633 |               2421 | amp_only             |              100 | monotonic     | decreasing         |               8 |
|            62 | s03b_binned_timewalk       | 1.43743 |  1.39031 |   1.5756  |               2421 | amp_only             |              100 | monotonic     | decreasing         |               8 |
|            62 | template_phase_base        | 2.90117 |  2.90117 |   3.02631 |               2421 | amp_only             |              100 | monotonic     | decreasing         |               8 |
|            63 | analytic_timewalk          | 1.39132 |  1.30871 |   1.46124 |               1110 | amp_only             |              100 | unconstrained | none               |               8 |
|            63 | ml_ridge_on_template_phase | 1.37073 |  1.2903  |   1.4392  |               1110 | amp_only             |              100 | unconstrained | none               |               8 |
|            63 | s03b_binned_timewalk       | 1.43311 |  1.31436 |   1.56436 |               1110 | amp_only             |              100 | unconstrained | none               |               8 |
|            63 | template_phase_base        | 2.87872 |  2.87872 |   3.01249 |               1110 | amp_only             |              100 | unconstrained | none               |               8 |
|            65 | analytic_timewalk          | 1.49464 |  1.34034 |   1.65326 |                198 | amp_only             |              100 | monotonic     | decreasing         |              10 |
|            65 | ml_ridge_on_template_phase | 1.39153 |  1.29309 |   1.58727 |                198 | amp_only             |              100 | monotonic     | decreasing         |              10 |
|            65 | s03b_binned_timewalk       | 1.56958 |  1.31958 |   1.81958 |                198 | amp_only             |              100 | monotonic     | decreasing         |              10 |
|            65 | template_phase_base        | 2.88915 |  2.63915 |   3.13915 |                198 | amp_only             |              100 | monotonic     | decreasing         |              10 |

Pooled intervals resample held-out runs, not individual residuals.

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| analytic_timewalk          | 1.55109 |  1.37577 |   1.93416 |              11460 |             0.0191099 |
| ml_ridge_on_template_phase | 1.53692 |  1.34174 |   1.81815 |              11460 |             0.0173647 |
| s03b_binned_timewalk       | 1.58719 |  1.32175 |   1.85481 |              11460 |             0.0196335 |
| template_phase_base        | 2.74141 |  2.68945 |   2.99232 |              11460 |             0.0813264 |

## 3. Leakage checks

No model feature includes run number, event id, event order, other-stave timing, or held-out labels. Every split is by run, and event-id overlap is zero by construction and by audit. Shuffled-target controls were rerun independently per held-out run.

| check                                                |   min_sigma68_ns |   median_sigma68_ns |   max_sigma68_ns |
|:-----------------------------------------------------|-----------------:|--------------------:|-----------------:|
| analytic_timewalk_shuffled_target                    |          2.69439 |             2.83705 |          2.9801  |
| feature_audit_no_run_event_order_or_cross_stave_time |          0       |             0       |          0       |
| ml_ridge_shuffled_target                             |          2.46013 |             2.83216 |          2.99403 |
| s03b_binned_shuffled_target                          |          2.70351 |             2.88384 |          2.99232 |
| template_phase                                       |          2.6428  |             2.87872 |          2.99232 |
| train_heldout_event_id_overlap                       |          0       |             0       |          0       |

## 4. Verdict

The pooled template-phase baseline is `2.741 ns` with run-bootstrap CI `[2.689, 2.992] ns`.
The analytic correction is `1.551 ns` with CI `[1.376, 1.934] ns`, a gain of `1.190 ns`.
The S03b binned correction is `1.587 ns` with CI `[1.322, 1.855] ns`; analytic is `0.036 ns` narrower.
The ML Ridge correction is `1.537 ns` with CI `[1.342, 1.818] ns`, a gain of `1.204 ns`.

Conclusion: `analytic_closure_stable_across_sample_ii_runs`.

## 5. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03c_multi_heldout_timewalk_stability.py --config configs/s03c_1781011005_880_1cb53153.yaml
```

Artifacts: `reproduction_match_table.csv`, `s03a_run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, `binned_cv_scan.csv`, `binned_model_table.csv`, figures, `result.json`, and `manifest.json`.

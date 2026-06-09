# Study report: S03c - Multi-heldout-run timewalk stability

- **Ticket:** 1781005627.1877.378c7a87
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03c_multi_heldout_timewalk_stability.yaml`

## 0. Question

Does the S03a analytic over-closure survive leave-one-run-out evaluation across Sample-II analysis runs instead of only held-out run 65?

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
| ml_ridge_on_template_phase | 1.39153 |  1.30504 |   1.58045 |                198 |             1.39153 |          0 | True   |

## 2. Leave-one-run-out results

For each held-out run, templates and residual-correction models were trained only on the other Sample-II analysis runs. The traditional model is the S03a analytic timewalk Ridge scan; the ML model is the waveform-feature Ridge residual corrector on template phase.

|   heldout_run | method                     |   value |   ci_low |   ci_high |   n_pair_residuals | analytic_candidate   |   analytic_alpha |
|--------------:|:---------------------------|--------:|---------:|----------:|-------------------:|:---------------------|-----------------:|
|            58 | analytic_timewalk          | 1.18748 |  1.13483 |   1.35901 |                219 | amp_only             |              100 |
|            58 | ml_ridge_on_template_phase | 1.27047 |  1.15618 |   1.4264  |                219 | amp_only             |              100 |
|            58 | template_phase_base        | 2.6428  |  2.6428  |   2.77317 |                219 | amp_only             |              100 |
|            59 | analytic_timewalk          | 1.45871 |  1.39218 |   1.52655 |               2289 | amp_only             |              100 |
|            59 | ml_ridge_on_template_phase | 1.49843 |  1.43215 |   1.54957 |               2289 | amp_only             |              100 |
|            59 | template_phase_base        | 2.99232 |  2.99232 |   3.12333 |               2289 | amp_only             |              100 |
|            60 | analytic_timewalk          | 1.3437  |  1.28846 |   1.40106 |               2424 | amp_only             |              100 |
|            60 | ml_ridge_on_template_phase | 1.30605 |  1.27199 |   1.35411 |               2424 | amp_only             |              100 |
|            60 | template_phase_base        | 2.66393 |  2.66393 |   2.7113  |               2424 | amp_only             |              100 |
|            61 | analytic_timewalk          | 2.12996 |  1.99404 |   2.19833 |               2799 | amp_only             |              100 |
|            61 | ml_ridge_on_template_phase | 1.96998 |  1.89545 |   2.04918 |               2799 | amp_only             |              100 |
|            61 | template_phase_base        | 2.70351 |  2.70351 |   2.70351 |               2799 | amp_only             |              100 |
|            62 | analytic_timewalk          | 1.469   |  1.41421 |   1.51825 |               2421 | amp_only             |              100 |
|            62 | ml_ridge_on_template_phase | 1.44698 |  1.39359 |   1.50834 |               2421 | amp_only             |              100 |
|            62 | template_phase_base        | 2.90117 |  2.90117 |   3.02631 |               2421 | amp_only             |              100 |
|            63 | analytic_timewalk          | 1.39132 |  1.30301 |   1.45786 |               1110 | amp_only             |              100 |
|            63 | ml_ridge_on_template_phase | 1.37073 |  1.28854 |   1.43843 |               1110 | amp_only             |              100 |
|            63 | template_phase_base        | 2.87872 |  2.87872 |   3.01249 |               1110 | amp_only             |              100 |
|            65 | analytic_timewalk          | 1.49464 |  1.34608 |   1.62837 |                198 | amp_only             |              100 |
|            65 | ml_ridge_on_template_phase | 1.39153 |  1.28952 |   1.57731 |                198 | amp_only             |              100 |
|            65 | template_phase_base        | 2.88915 |  2.63915 |   3.20541 |                198 | amp_only             |              100 |

Pooled intervals resample held-out runs, not individual residuals.

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| analytic_timewalk          | 1.55109 |  1.36743 |   1.90344 |              11460 |             0.0191099 |
| ml_ridge_on_template_phase | 1.53692 |  1.33525 |   1.81912 |              11460 |             0.0173647 |
| template_phase_base        | 2.74141 |  2.68081 |   2.98617 |              11460 |             0.0813264 |

## 3. Leakage checks

No model feature includes run number, event id, event order, other-stave timing, or held-out labels. Every split is by run, and event-id overlap is zero by construction and by audit. Shuffled-target controls were rerun independently per held-out run.

| check                                                |   min_sigma68_ns |   median_sigma68_ns |   max_sigma68_ns |
|:-----------------------------------------------------|-----------------:|--------------------:|-----------------:|
| analytic_timewalk_shuffled_target                    |          2.69439 |             2.83705 |          2.9801  |
| feature_audit_no_run_event_order_or_cross_stave_time |          0       |             0       |          0       |
| ml_ridge_shuffled_target                             |          2.46013 |             2.83216 |          2.99403 |
| template_phase                                       |          2.6428  |             2.87872 |          2.99232 |
| train_heldout_event_id_overlap                       |          0       |             0       |          0       |

## 4. Verdict

The pooled template-phase baseline is `2.741 ns` with run-bootstrap CI `[2.681, 2.986] ns`.
The analytic correction is `1.551 ns` with CI `[1.367, 1.903] ns`, a gain of `1.190 ns`.
The ML Ridge correction is `1.537 ns` with CI `[1.335, 1.819] ns`, a gain of `1.204 ns`.

Conclusion: `analytic_closure_stable_across_sample_ii_runs`.

## 5. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03c_multi_heldout_timewalk_stability.py --config configs/s03c_multi_heldout_timewalk_stability.yaml
```

Artifacts: `reproduction_match_table.csv`, `s03a_run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, figures, `result.json`, and `manifest.json`.

# Study report: S03e - Blind Sample-I to Sample-II timewalk transfer

- **Ticket:** 1781011277.975.62a40408
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train/calibrate only Sample I runs 31-37, 39-42, 44-57; blind evaluation on Sample II analysis runs 58-63 and 65
- **Config:** `configs/s03e_blind_sample_i_to_ii_transfer.yaml`
- **Monte Carlo:** none

## 0. Question

Do the S03 analytic timewalk corrections trained on Sample I transfer blindly to Sample II timing runs, or was the S03c closure tuned to Sample II?

## 1. Raw-ROOT reproduction gate

Before fitting Sample-I transfer models, selected-pulse counts and the S03c Sample-II leave-one-run-out reference were rebuilt from raw ROOT.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   s03c_report_value |   delta_ns | pass   |
|:---------------------------|--------:|---------:|----------:|-------------------:|--------------------:|-----------:|:-------|
| analytic_timewalk          | 1.55109 |  1.37827 |   1.89773 |              11460 |             1.55109 |          0 | True   |
| ml_ridge_on_template_phase | 1.53692 |  1.34731 |   1.80471 |              11460 |             1.53692 |          0 | True   |
| template_phase_base        | 2.74141 |  2.68081 |   2.98617 |              11460 |             2.74141 |          0 | True   |

## 2. Blind transfer methods

All models used the fixed base pickoff `template_phase` with templates built only from Sample I train runs. The analytic traditional model selected `amp_only` with Ridge alpha `100` by GroupKFold over Sample-I runs. The constrained binned traditional model selected mode `monotonic`, direction `decreasing`, bins `4`. The ML comparator is the existing waveform-feature Ridge residual corrector, also selected only by Sample-I grouped CV.

## 3. Held-out Sample-II results

|   heldout_run | method                     |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|--------------:|:---------------------------|---------:|---------:|----------:|-------------------:|----------------------:|
|            58 | analytic_timewalk          | 1.33262  | 1.26893  |  1.37267  |                219 |            0.00913242 |
|            58 | ml_ridge_on_template_phase | 1.31124  | 1.1879   |  1.41548  |                219 |            0.00913242 |
|            58 | s03b_binned_timewalk       | 0.897972 | 0.897972 |  0.897972 |                219 |            0.00913242 |
|            58 | template_phase_base        | 1.79594  | 1.79594  |  1.79594  |                219 |            0.0410959  |
|            59 | analytic_timewalk          | 1.37481  | 1.34438  |  1.48005  |               2289 |            0.0187855  |
|            59 | ml_ridge_on_template_phase | 1.40438  | 1.3673   |  1.45688  |               2289 |            0.0174749  |
|            59 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.25     |               2289 |            0.0327654  |
|            59 | template_phase_base        | 2.25     | 2.04594  |  2.46358  |               2289 |            0.100044   |
|            60 | analytic_timewalk          | 1.41724  | 1.35967  |  1.50912  |               2424 |            0.019802   |
|            60 | ml_ridge_on_template_phase | 1.44071  | 1.39484  |  1.50083  |               2424 |            0.015264   |
|            60 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.39797  |               2424 |            0.0338284  |
|            60 | template_phase_base        | 1.79594  | 1.79594  |  2.04594  |               2424 |            0.102723   |
|            61 | analytic_timewalk          | 1.79299  | 1.74382  |  1.90758  |               2799 |            0.0239371  |
|            61 | ml_ridge_on_template_phase | 1.78197  | 1.71456  |  1.85072  |               2799 |            0.022508   |
|            61 | s03b_binned_timewalk       | 1.64797  | 1.5      |  1.73179  |               2799 |            0.0421579  |
|            61 | template_phase_base        | 2.25     | 2.04594  |  2.29594  |               2799 |            0.0957485  |
|            62 | analytic_timewalk          | 1.41333  | 1.36547  |  1.50702  |               2421 |            0.0181743  |
|            62 | ml_ridge_on_template_phase | 1.4394   | 1.40146  |  1.50183  |               2421 |            0.0144568  |
|            62 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.39797  |               2421 |            0.0338703  |
|            62 | template_phase_base        | 2        | 1.79594  |  2.04594  |               2421 |            0.101198   |
|            63 | analytic_timewalk          | 1.40432  | 1.36449  |  1.53383  |               1110 |            0.0261261  |
|            63 | ml_ridge_on_template_phase | 1.4475   | 1.39741  |  1.51602  |               1110 |            0.0243243  |
|            63 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.39797  |               1110 |            0.0423423  |
|            63 | template_phase_base        | 2.04594  | 1.79594  |  2.46358  |               1110 |            0.118919   |
|            65 | analytic_timewalk          | 1.30732  | 1.23391  |  1.45597  |                198 |            0.0151515  |
|            65 | ml_ridge_on_template_phase | 1.28907  | 1.18579  |  1.40541  |                198 |            0.00505051 |
|            65 | s03b_binned_timewalk       | 1        | 0.897972 |  1.39797  |                198 |            0.010101   |
|            65 | template_phase_base        | 1.79594  | 1.79594  |  2.29594  |                198 |            0.0555556  |

Pooled intervals resample held-out runs, not individual residuals.

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| analytic_timewalk          | 1.49467 |  1.37415 |   1.68429 |              11460 |             0.0207679 |
| ml_ridge_on_template_phase | 1.47404 |  1.40834 |   1.63447 |              11460 |             0.0178883 |
| s03b_binned_timewalk       | 1.39797 |  1.23179 |   1.5     |              11460 |             0.0356021 |
| template_phase_base        | 2.04594 |  1.79594 |   2.17838 |              11460 |             0.0997382 |

## 4. Leakage checks

No model input includes run number, event id, event order, other-stave timing, sample label, or held-out labels. Final fits use only Sample-I rows; Sample-II targets are computed only for evaluation diagnostics. Shuffled-target controls were fit on Sample I and evaluated on Sample II by run.

| check                                                |   min_value |   median_value |   max_value |
|:-----------------------------------------------------|------------:|---------------:|------------:|
| analytic_timewalk_shuffled_target                    |     1.83528 |        2.0012  |     2.28177 |
| feature_audit_no_run_event_order_or_cross_stave_time |     0       |        0       |     0       |
| ml_ridge_shuffled_target                             |     1.86676 |        2.06269 |     2.39296 |
| s03b_binned_shuffled_target                          |     1.79594 |        2       |     2.25    |
| train_heldout_event_id_overlap                       |     0       |        0       |     0       |
| train_heldout_run_overlap                            |     0       |        0       |     0       |

## 5. Verdict

Blind Sample-I template phase gives `2.046 ns` with run-bootstrap CI `[1.796, 2.178] ns`.
The analytic correction gives `1.495 ns` with CI `[1.374, 1.684] ns`, a gain of `0.551 ns`.
The binned traditional correction gives `1.398 ns`; the ML Ridge comparator gives `1.474 ns`.
Conclusion: `blind_sample_i_transfer_matches_sample_ii_training`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03e_blind_sample_i_to_ii_transfer.py --config configs/s03e_blind_sample_i_to_ii_transfer.yaml
```

Artifacts: `reproduction_match_table.csv`, `s03c_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV/model CSVs, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

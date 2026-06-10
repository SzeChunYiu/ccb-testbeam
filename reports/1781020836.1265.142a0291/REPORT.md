# Study report: S03g - Run 64 pure transfer diagnostic

- **Ticket:** `1781020836.1265.142a0291`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train/model-select only Sample I runs 31-37, 39-42, 44-57; evaluate Sample-II analysis runs 58-63 and 65 plus diagnostic run 64
- **Config:** `configs/s03g_1781020836_1265_142a0291_run64_transfer.yaml`
- **Monte Carlo:** none

## 0. Question

Does Sample-II calibration run 64 agree with the blind Sample-I-to-Sample-II S03e transfer pattern, or does it expose calibration-run drift?

## 1. Raw-ROOT reproduction gate

Before adding run 64, the S00 selected-pulse counts and the S03e/S03c Sample-II analysis reference numbers were rebuilt from raw ROOT.

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
| analytic_timewalk          | 1.55109 |  1.36848 |   1.9042  |              11460 |             1.55109 |          0 | True   |
| ml_ridge_on_template_phase | 1.53692 |  1.34329 |   1.82768 |              11460 |             1.53692 |          0 | True   |
| template_phase_base        | 2.74141 |  2.68413 |   2.98904 |              11460 |             2.74141 |          0 | True   |

## 2. Methods

The base timing is `template_phase`. Templates, the analytic traditional correction, the monotone binned traditional correction, and the ML Ridge residual corrector were all trained and selected only on Sample I runs. The selected analytic model was `amp_only` with Ridge alpha `100`; the binned traditional table used `4` monotone-decreasing amplitude bins.

## 3. Run-held diagnostics

|   heldout_run | method                     |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|--------------:|:---------------------------|---------:|---------:|----------:|-------------------:|----------------------:|
|            58 | analytic_timewalk          | 1.33262  | 1.26427  |  1.37505  |                219 |            0.00913242 |
|            58 | ml_ridge_on_template_phase | 1.31124  | 1.1922   |  1.40088  |                219 |            0.00913242 |
|            58 | s03b_binned_timewalk       | 0.897972 | 0.897972 |  0.897972 |                219 |            0.00913242 |
|            58 | template_phase_base        | 1.79594  | 1.79594  |  1.79594  |                219 |            0.0410959  |
|            59 | analytic_timewalk          | 1.37481  | 1.34343  |  1.48137  |               2289 |            0.0187855  |
|            59 | ml_ridge_on_template_phase | 1.40438  | 1.36561  |  1.45985  |               2289 |            0.0174749  |
|            59 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.25     |               2289 |            0.0327654  |
|            59 | template_phase_base        | 2.25     | 2.04594  |  2.46358  |               2289 |            0.100044   |
|            60 | analytic_timewalk          | 1.41724  | 1.35957  |  1.51078  |               2424 |            0.019802   |
|            60 | ml_ridge_on_template_phase | 1.44071  | 1.39611  |  1.49314  |               2424 |            0.015264   |
|            60 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.39797  |               2424 |            0.0338284  |
|            60 | template_phase_base        | 1.79594  | 1.79594  |  2.04594  |               2424 |            0.102723   |
|            61 | analytic_timewalk          | 1.79299  | 1.74267  |  1.89557  |               2799 |            0.0239371  |
|            61 | ml_ridge_on_template_phase | 1.78197  | 1.71919  |  1.85112  |               2799 |            0.022508   |
|            61 | s03b_binned_timewalk       | 1.64797  | 1.5      |  1.73179  |               2799 |            0.0421579  |
|            61 | template_phase_base        | 2.25     | 2.04594  |  2.29594  |               2799 |            0.0957485  |
|            62 | analytic_timewalk          | 1.41333  | 1.366    |  1.50173  |               2421 |            0.0181743  |
|            62 | ml_ridge_on_template_phase | 1.4394   | 1.39731  |  1.50194  |               2421 |            0.0144568  |
|            62 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.39797  |               2421 |            0.0338703  |
|            62 | template_phase_base        | 2        | 1.79594  |  2.04594  |               2421 |            0.101198   |
|            63 | analytic_timewalk          | 1.40432  | 1.36638  |  1.52934  |               1110 |            0.0261261  |
|            63 | ml_ridge_on_template_phase | 1.4475   | 1.39646  |  1.52871  |               1110 |            0.0243243  |
|            63 | s03b_binned_timewalk       | 1.25     | 1.14797  |  1.39797  |               1110 |            0.0423423  |
|            63 | template_phase_base        | 2.04594  | 1.79594  |  2.46358  |               1110 |            0.118919   |
|            64 | analytic_timewalk          | 1.33298  | 1.30386  |  1.37771  |                630 |            0.0206349  |
|            64 | ml_ridge_on_template_phase | 1.3537   | 1.31945  |  1.41987  |                630 |            0.0206349  |
|            64 | s03b_binned_timewalk       | 0.934702 | 0.897972 |  1.14797  |                630 |            0.0253968  |
|            64 | template_phase_base        | 1.79594  | 1.79594  |  2.04594  |                630 |            0.0777778  |
|            65 | analytic_timewalk          | 1.30732  | 1.25182  |  1.47807  |                198 |            0.0151515  |
|            65 | ml_ridge_on_template_phase | 1.28907  | 1.18964  |  1.41845  |                198 |            0.00505051 |
|            65 | s03b_binned_timewalk       | 1        | 0.897972 |  1.39797  |                198 |            0.010101   |
|            65 | template_phase_base        | 1.79594  | 1.79594  |  2.29594  |                198 |            0.0555556  |

Analysis-run pooled intervals resample held-out analysis runs 58-63 and 65.

| method                     |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| analytic_timewalk          | 1.49467 |  1.37377 |   1.71391 |              11460 |             0.0207679 |
| ml_ridge_on_template_phase | 1.47404 |  1.40714 |   1.66056 |              11460 |             0.0178883 |
| s03b_binned_timewalk       | 1.39797 |  1.23179 |   1.5     |              11460 |             0.0356021 |
| template_phase_base        | 2.04594 |  1.79594 |   2.04594 |              11460 |             0.0997382 |

The run64-minus-analysis contrast resamples analysis runs as blocks and resamples run64 pair residuals because run 64 is a single diagnostic run.

| method                     |   analysis_sigma68_ns |   run64_sigma68_ns |   delta_run64_minus_analysis_ns |    ci_low |    ci_high | bootstrap_unit                               |
|:---------------------------|----------------------:|-------------------:|--------------------------------:|----------:|-----------:|:---------------------------------------------|
| analytic_timewalk          |               1.49467 |           1.33298  |                       -0.161687 | -0.389224 | -0.0124393 | analysis_run_blocks_plus_run64_pair_resample |
| ml_ridge_on_template_phase |               1.47404 |           1.3537   |                       -0.120344 | -0.252533 | -0.0121944 | analysis_run_blocks_plus_run64_pair_resample |
| s03b_binned_timewalk       |               1.39797 |           0.934702 |                       -0.46327  | -0.583817 | -0.102028  | analysis_run_blocks_plus_run64_pair_resample |
| template_phase_base        |               2.04594 |           1.79594  |                       -0.25     | -0.255101 |  0.0480747 | analysis_run_blocks_plus_run64_pair_resample |

| method                     |   run64_sigma68_ns |   analysis_min_sigma68_ns |   analysis_median_sigma68_ns |   analysis_max_sigma68_ns |   run64_rank_ascending_among_8 |
|:---------------------------|-------------------:|--------------------------:|-----------------------------:|--------------------------:|-------------------------------:|
| analytic_timewalk          |           1.33298  |                  1.30732  |                      1.40432 |                   1.79299 |                              3 |
| ml_ridge_on_template_phase |           1.3537   |                  1.28907  |                      1.4394  |                   1.78197 |                              3 |
| s03b_binned_timewalk       |           0.934702 |                  0.897972 |                      1.25    |                   1.64797 |                              2 |
| template_phase_base        |           1.79594  |                  1.79594  |                      2       |                   2.25    |                              4 |

## 4. Leakage checks

No model input includes run number, event id, event order, cross-stave timing, sample label, or held-out labels. Final fits do not include run 64 or any Sample-II row. Shuffled-target controls were fit on Sample I and evaluated on every Sample-II run including 64.

| check                                                |   min_value |   median_value |   max_value |
|:-----------------------------------------------------|------------:|---------------:|------------:|
| analytic_timewalk_shuffled_target                    |     1.77423 |        1.91223 |     2.25831 |
| feature_audit_no_run_event_order_or_cross_stave_time |     0       |        0       |     0       |
| ml_ridge_shuffled_target                             |     1.78412 |        1.94913 |     2.29396 |
| s03b_binned_shuffled_target                          |     1.79594 |        1.89797 |     2.25    |
| train_heldout_event_id_overlap                       |     0       |        0       |     0       |
| train_heldout_run_overlap                            |     0       |        0       |     0       |

## 5. Verdict

| method                     |   analysis_sigma68_ns |   run64_sigma68_ns |   delta_run64_minus_analysis_ns |    ci_low |    ci_high |
|:---------------------------|----------------------:|-------------------:|--------------------------------:|----------:|-----------:|
| analytic_timewalk          |               1.49467 |            1.33298 |                       -0.161687 | -0.389224 | -0.0124393 |
| ml_ridge_on_template_phase |               1.47404 |            1.3537  |                       -0.120344 | -0.252533 | -0.0121944 |

`result.json` verdict: `run64_exposes_transfer_drift`.
Run 64 differs from the analysis-run pool for at least one primary correction after the held-out contrast.

No follow-up ticket was appended: this run64 diagnostic was itself the queued S03g follow-up, and nearby run-drift/topology variants already exist in completed S02/S03/P10 studies.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03g_1781020836_1265_142a0291_run64_transfer.py --config configs/s03g_1781020836_1265_142a0291_run64_transfer.yaml
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, transfer benchmarks, comparison tables, leakage checks, CV/model tables, pair residuals, and figures.

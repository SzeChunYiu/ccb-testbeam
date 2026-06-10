# Study report: S03e - Blind Sample-I to Sample-II signed-prior transfer

- **Ticket:** 1781022259.1306.086d3074
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train/calibrate only Sample I runs 31-37, 39-42, 44-57; blind evaluation on Sample II analysis runs 58-63 and 65
- **Config:** `configs/s03e_1781022259_1306_086d3074_signed_prior_blind_transfer.yaml`
- **Monte Carlo:** none

## 0. Question

Does the S03d signed per-stave inverse-amplitude prior learned on Sample-I calibration/analysis runs transfer blindly to Sample-II analysis runs, compared with S03a Ridge, S03b isotonic, and HGB?

## 1. Raw-ROOT reproduction gate

Before fitting Sample-I transfer models, selected-pulse counts and the prior run-65 S03a/S03b/template reference were rebuilt from raw ROOT.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   sample_ii_reference_value |    delta_ns | pass   |
|:---------------------|--------:|---------:|----------:|-------------------:|----------------------------:|------------:|:-------|
| analytic_timewalk    | 1.49464 |      nan |       nan |                198 |                     1.49464 | 5.55112e-15 | True   |
| s03b_binned_timewalk | 1.56958 |      nan |       nan |                198 |                     1.56958 | 0           | True   |
| template_phase_base  | 2.88915 |      nan |       nan |                198 |                     2.88915 | 0           | True   |

## 2. Blind transfer methods

All models used the fixed base pickoff `template_phase` with templates built only from Sample I train runs. S03a selected `amp_only` with Ridge alpha `100` by GroupKFold over Sample-I runs. S03b selected mode `monotonic`, direction `decreasing`, bins `4`. The S03d signed prior selected `inv_sqrt_amp` with nonnegative per-stave inverse-amplitude slopes and Sample-I grouped-CV sigma68 `1.402 ns`. The ML comparator is an HGB residual corrector selected only by Sample-I grouped CV, trained on a deterministic cap of `10000` Sample-I rows.

## 3. Held-out Sample-II results

|   heldout_run | method               |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|--------------:|:---------------------|---------:|---------:|----------:|-------------------:|----------------------:|
|            58 | analytic_timewalk    | 1.33262  | 1.27072  |  1.37542  |                219 |            0.00913242 |
|            58 | hgb_timewalk         | 0.916636 | 0.916636 |  1.00203  |                219 |            0.00913242 |
|            58 | s03b_binned_timewalk | 0.897972 | 0.897972 |  0.897972 |                219 |            0.00913242 |
|            58 | signed_physics_prior | 1.39337  | 1.34489  |  1.44275  |                219 |            0.00913242 |
|            58 | template_phase_base  | 1.79594  | 1.79594  |  1.79594  |                219 |            0.0410959  |
|            59 | analytic_timewalk    | 1.37481  | 1.34864  |  1.46252  |               2289 |            0.0187855  |
|            59 | hgb_timewalk         | 1.12369  | 1.04561  |  1.24083  |               2289 |            0.0235911  |
|            59 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               2289 |            0.0327654  |
|            59 | signed_physics_prior | 1.44833  | 1.37494  |  1.55127  |               2289 |            0.0192224  |
|            59 | template_phase_base  | 2.25     | 2.04594  |  2.46358  |               2289 |            0.100044   |
|            60 | analytic_timewalk    | 1.41724  | 1.3611   |  1.51908  |               2424 |            0.019802   |
|            60 | hgb_timewalk         | 1.19006  | 1.13566  |  1.24548  |               2424 |            0.0206271  |
|            60 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               2424 |            0.0338284  |
|            60 | signed_physics_prior | 1.50499  | 1.42638  |  1.59929  |               2424 |            0.0181518  |
|            60 | template_phase_base  | 1.79594  | 1.79594  |  2.04594  |               2424 |            0.102723   |
|            61 | analytic_timewalk    | 1.79299  | 1.73159  |  1.90491  |               2799 |            0.0239371  |
|            61 | hgb_timewalk         | 1.49887  | 1.42981  |  1.55256  |               2799 |            0.0250089  |
|            61 | s03b_binned_timewalk | 1.64797  | 1.5      |  1.75     |               2799 |            0.0421579  |
|            61 | signed_physics_prior | 1.85215  | 1.80286  |  1.94396  |               2799 |            0.0242944  |
|            61 | template_phase_base  | 2.25     | 2.04594  |  2.29594  |               2799 |            0.0957485  |
|            62 | analytic_timewalk    | 1.41333  | 1.36312  |  1.5044   |               2421 |            0.0181743  |
|            62 | hgb_timewalk         | 1.2016   | 1.08402  |  1.29638  |               2421 |            0.0190004  |
|            62 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               2421 |            0.0338703  |
|            62 | signed_physics_prior | 1.49906  | 1.42255  |  1.59477  |               2421 |            0.0165221  |
|            62 | template_phase_base  | 2        | 1.79594  |  2.04594  |               2421 |            0.101198   |
|            63 | analytic_timewalk    | 1.40432  | 1.36378  |  1.54319  |               1110 |            0.0261261  |
|            63 | hgb_timewalk         | 1.20776  | 1.04146  |  1.27909  |               1110 |            0.0306306  |
|            63 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               1110 |            0.0423423  |
|            63 | signed_physics_prior | 1.47768  | 1.39426  |  1.62483  |               1110 |            0.0243243  |
|            63 | template_phase_base  | 2.04594  | 1.79594  |  2.44387  |               1110 |            0.118919   |
|            65 | analytic_timewalk    | 1.30732  | 1.23613  |  1.45558  |                198 |            0.0151515  |
|            65 | hgb_timewalk         | 1.00203  | 0.944204 |  1.25056  |                198 |            0.0151515  |
|            65 | s03b_binned_timewalk | 1        | 0.897972 |  1.39797  |                198 |            0.010101   |
|            65 | signed_physics_prior | 1.38812  | 1.27993  |  1.63332  |                198 |            0.010101   |
|            65 | template_phase_base  | 1.79594  | 1.79594  |  2.29594  |                198 |            0.0555556  |

Pooled intervals resample held-out runs, not individual residuals.

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| analytic_timewalk    | 1.49467 |  1.37515 |   1.69641 |              11460 |             0.0207679 |
| hgb_timewalk         | 1.2212  |  1.11472 |   1.41074 |              11460 |             0.0225131 |
| s03b_binned_timewalk | 1.39797 |  1.23179 |   1.5     |              11460 |             0.0356021 |
| signed_physics_prior | 1.58668 |  1.43905 |   1.75848 |              11460 |             0.0212042 |
| template_phase_base  | 2.04594 |  1.79594 |   2.04594 |              11460 |             0.0997382 |

## 4. Leakage checks

No model input includes run number, event id, event order, other-stave timing, sample label, or held-out labels. Final fits use only Sample-I rows; Sample-II targets are computed only for evaluation diagnostics. Shuffled-target controls were fit on Sample I and evaluated on Sample II by run.

The too-good screen is `too_good_flag=True`. The leakage flag is `False` after train/held-out overlap and shuffled-target probes; the overall shuffled-target minimum is `1.774 ns`.

| check                                                |   min_value |   median_value |   max_value |
|:-----------------------------------------------------|------------:|---------------:|------------:|
| analytic_timewalk_shuffled_target                    |     1.77423 |        1.98864 |     2.25831 |
| feature_audit_no_run_event_order_or_cross_stave_time |     0       |        0       |     0       |
| hgb_shuffled_target                                  |     1.83054 |        1.99497 |     2.28248 |
| s03b_binned_shuffled_target                          |     1.79594 |        2       |     2.25    |
| signed_prior_shuffled_target                         |     1.90409 |        2.06305 |     2.37321 |
| train_heldout_event_id_overlap                       |     0       |        0       |     0       |
| train_heldout_run_overlap                            |     0       |        0       |     0       |

## 5. Verdict

Blind Sample-I template phase gives `2.046 ns` with run-bootstrap CI `[1.796, 2.046] ns`.
The analytic correction gives `1.495 ns` with CI `[1.375, 1.696] ns`, a gain of `0.551 ns`.
The S03b binned traditional correction gives `1.398 ns`; the signed S03d prior gives `1.587 ns`; the HGB ML comparator gives `1.221 ns`.
Conclusion: `signed_prior_transfer_has_gap_or_leakage_concern`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03e_1781022259_1306_086d3074_signed_prior_blind_transfer.py --config configs/s03e_1781022259_1306_086d3074_signed_prior_blind_transfer.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV/model CSVs, signed-prior coefficients, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

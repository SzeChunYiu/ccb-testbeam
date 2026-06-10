# Study report: S03e - Blind Sample-I to Sample-II timewalk transfer

- **Ticket:** 1781019517.3432.5852083f
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train/calibrate only Sample I runs 31-37, 39-42, 44-57; blind evaluation on Sample II analysis runs 58-63 and 65
- **Config:** `configs/s03e_1781019517_3432_5852083f_blind_sample_i_to_ii_hgb.yaml`
- **Monte Carlo:** none

## 0. Question

Do S03a amp-only, S03b monotone-binned, and HGB residual timewalk corrections trained on Sample-I analysis/calibration runs transfer blindly to Sample-II analysis runs without retuning?

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

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   sample_ii_reference_value |   delta_ns | pass   |
|:---------------------|--------:|---------:|----------:|-------------------:|----------------------------:|-----------:|:-------|
| analytic_timewalk    | 1.49464 |      nan |       nan |                198 |                     1.49464 |          0 | True   |
| s03b_binned_timewalk | 1.56958 |      nan |       nan |                198 |                     1.56958 |          0 | True   |
| template_phase_base  | 2.88915 |      nan |       nan |                198 |                     2.88915 |          0 | True   |

## 2. Blind transfer methods

All models used the fixed base pickoff `template_phase` with templates built only from Sample I train runs. The S03a analytic traditional model selected `amp_only` with Ridge alpha `100` by GroupKFold over Sample-I runs. The S03b constrained binned traditional model selected mode `monotonic`, direction `decreasing`, bins `4`. The ML comparator is an HGB residual corrector selected only by Sample-I grouped CV, trained on a deterministic cap of `10000` Sample-I rows.

## 3. Held-out Sample-II results

|   heldout_run | method               |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|--------------:|:---------------------|---------:|---------:|----------:|-------------------:|----------------------:|
|            58 | analytic_timewalk    | 1.33262  | 1.2659   |  1.37503  |                219 |            0.00913242 |
|            58 | hgb_timewalk         | 0.916563 | 0.916563 |  0.991592 |                219 |            0.00913242 |
|            58 | s03b_binned_timewalk | 0.897972 | 0.897972 |  0.897972 |                219 |            0.00913242 |
|            58 | template_phase_base  | 1.79594  | 1.79594  |  1.79594  |                219 |            0.0410959  |
|            59 | analytic_timewalk    | 1.37481  | 1.34856  |  1.45645  |               2289 |            0.0187855  |
|            59 | hgb_timewalk         | 1.12369  | 1.04155  |  1.23959  |               2289 |            0.0235911  |
|            59 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.25     |               2289 |            0.0327654  |
|            59 | template_phase_base  | 2.25     | 2.04594  |  2.46358  |               2289 |            0.100044   |
|            60 | analytic_timewalk    | 1.41724  | 1.35969  |  1.52493  |               2424 |            0.019802   |
|            60 | hgb_timewalk         | 1.18875  | 1.1494   |  1.24801  |               2424 |            0.0206271  |
|            60 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               2424 |            0.0338284  |
|            60 | template_phase_base  | 1.79594  | 1.79594  |  2.04594  |               2424 |            0.102723   |
|            61 | analytic_timewalk    | 1.79299  | 1.74553  |  1.91824  |               2799 |            0.0239371  |
|            61 | hgb_timewalk         | 1.4987   | 1.41656  |  1.54861  |               2799 |            0.0250089  |
|            61 | s03b_binned_timewalk | 1.64797  | 1.5      |  1.73179  |               2799 |            0.0421579  |
|            61 | template_phase_base  | 2.25     | 2.04594  |  2.29594  |               2799 |            0.0957485  |
|            62 | analytic_timewalk    | 1.41333  | 1.36465  |  1.49594  |               2421 |            0.0181743  |
|            62 | hgb_timewalk         | 1.20009  | 1.07486  |  1.29164  |               2421 |            0.0190004  |
|            62 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               2421 |            0.0338703  |
|            62 | template_phase_base  | 2        | 1.79594  |  2.04594  |               2421 |            0.101198   |
|            63 | analytic_timewalk    | 1.40432  | 1.36925  |  1.52326  |               1110 |            0.0261261  |
|            63 | hgb_timewalk         | 1.20781  | 1.07342  |  1.26887  |               1110 |            0.0306306  |
|            63 | s03b_binned_timewalk | 1.25     | 1.14797  |  1.39797  |               1110 |            0.0423423  |
|            63 | template_phase_base  | 2.04594  | 1.79594  |  2.46358  |               1110 |            0.118919   |
|            65 | analytic_timewalk    | 1.30732  | 1.23922  |  1.44904  |                198 |            0.0151515  |
|            65 | hgb_timewalk         | 1.00206  | 0.952151 |  1.25904  |                198 |            0.0151515  |
|            65 | s03b_binned_timewalk | 1        | 0.897972 |  1.39797  |                198 |            0.010101   |
|            65 | template_phase_base  | 1.79594  | 1.79594  |  2.29594  |                198 |            0.0555556  |

Pooled intervals resample held-out runs, not individual residuals.

| method               |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| analytic_timewalk    | 1.49467 |  1.3735  |   1.68971 |              11460 |             0.0207679 |
| hgb_timewalk         | 1.22114 |  1.10953 |   1.41456 |              11460 |             0.0225131 |
| s03b_binned_timewalk | 1.39797 |  1.14797 |   1.5     |              11460 |             0.0356021 |
| template_phase_base  | 2.04594 |  1.79594 |   2.04594 |              11460 |             0.0997382 |

## 4. Leakage checks

No model input includes run number, event id, event order, other-stave timing, sample label, or held-out labels. Final fits use only Sample-I rows; Sample-II targets are computed only for evaluation diagnostics. Shuffled-target controls were fit on Sample I and evaluated on Sample II by run.

The HGB result trips the too-good screen (`too_good_flag=True`) because it is `-0.173 ns` below the Sample-II LORO HGB reference. I therefore treated the shuffled-target controls and train/held-out overlap checks as gating leakage probes; the overall shuffled-target minimum remains `1.796 ns`, well above the HGB result.

| check                                                |   min_value |   median_value |   max_value |
|:-----------------------------------------------------|------------:|---------------:|------------:|
| analytic_timewalk_shuffled_target                    |     1.83528 |        2.0012  |     2.28177 |
| feature_audit_no_run_event_order_or_cross_stave_time |     0       |        0       |     0       |
| hgb_shuffled_target                                  |     1.81974 |        2.05355 |     2.34396 |
| s03b_binned_shuffled_target                          |     1.79594 |        2       |     2.25    |
| train_heldout_event_id_overlap                       |     0       |        0       |     0       |
| train_heldout_run_overlap                            |     0       |        0       |     0       |

## 5. Verdict

Blind Sample-I template phase gives `2.046 ns` with run-bootstrap CI `[1.796, 2.046] ns`.
The analytic correction gives `1.495 ns` with CI `[1.374, 1.690] ns`, a gain of `0.551 ns`.
The S03b binned traditional correction gives `1.398 ns`; the HGB ML comparator gives `1.221 ns`.
Conclusion: `blind_sample_i_transfer_matches_sample_ii_training`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03e_1781019517_3432_5852083f_blind_sample_i_to_ii_hgb.py --config configs/s03e_1781019517_3432_5852083f_blind_sample_i_to_ii_hgb.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV/model CSVs, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

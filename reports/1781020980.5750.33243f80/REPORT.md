# Study report: S03e - Sample-I-analysis population transfer

- **Ticket:** 1781020980.5750.33243f80
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train only Sample-I analysis runs 44-57; blind evaluation on Sample-II analysis runs 58-63 and 65
- **Config:** `configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml`
- **Monte Carlo:** none

## 0. Question

Do S03a global analytic coefficients and S03d hierarchical population coefficients trained only on Sample-I analysis runs transfer blindly to Sample-II analysis runs?

## 1. Raw-ROOT reproduction gate

The selected-pulse count gate was rebuilt from raw ROOT before any coefficient fitting.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Methods

Templates for `template_phase` were built only from Sample-I analysis runs. S03a is the amp-only global Ridge correction selected by grouped CV on runs 44-57. S03d fits population coefficients plus train-run deviations, but the transferred prediction uses only the population block for unseen Sample-II runs. The ML comparator is the existing HGB waveform-feature residual corrector trained on the same rows.

Selected raw timing checks at 2 cm:

| method         | split   |   sigma68_ns |   n_pair_residuals |
|:---------------|:--------|-------------:|-------------------:|
| template_phase | heldout |      2.5     |              11460 |
| cfd20          | heldout |      3.15027 |              11460 |
| le500          | heldout |      4.17084 |              11460 |
| template_phase | train   |      2.35907 |               1950 |
| cfd20          | train   |      3.14881 |               1950 |
| le500          | train   |      4.20316 |               1950 |

## 3. Held-out Sample-II results

|   heldout_run | method                       |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|--------------:|:-----------------------------|---------:|---------:|----------:|-------------------:|----------------------:|
|            58 | hgb_timewalk                 | 1.5056   | 1.35395  |  1.75305  |                219 |            0.0182648  |
|            58 | s03a_global_population       | 1.66707  | 1.56136  |  1.69753  |                219 |            0.00913242 |
|            58 | s03d_hierarchical_population | 0.532514 | 0.398668 |  0.734623 |                219 |            0.0136986  |
|            58 | template_phase_base          | 2.35907  | 2.35907  |  2.50242  |                219 |            0.100457   |
|            59 | hgb_timewalk                 | 1.62155  | 1.55905  |  1.69174  |               2289 |            0.0214067  |
|            59 | s03a_global_population       | 1.68126  | 1.66208  |  1.70024  |               2289 |            0.0222805  |
|            59 | s03d_hierarchical_population | 1.10106  | 0.996473 |  1.23457  |               2289 |            0.0345129  |
|            59 | template_phase_base          | 2.60907  | 2.35907  |  2.75242  |               2289 |            0.153342   |
|            60 | hgb_timewalk                 | 1.68974  | 1.62504  |  1.75101  |               2424 |            0.0243399  |
|            60 | s03a_global_population       | 1.69469  | 1.67339  |  1.80414  |               2424 |            0.0193894  |
|            60 | s03d_hierarchical_population | 1.10166  | 0.97689  |  1.24728  |               2424 |            0.0305281  |
|            60 | template_phase_base          | 2.35907  | 2.35907  |  2.60907  |               2424 |            0.151403   |
|            61 | hgb_timewalk                 | 1.88136  | 1.82965  |  1.94636  |               2799 |            0.035727   |
|            61 | s03a_global_population       | 2.1017   | 2.00883  |  2.17635  |               2799 |            0.0282244  |
|            61 | s03d_hierarchical_population | 1.31213  | 1.22848  |  1.433    |               2799 |            0.0335834  |
|            61 | template_phase_base          | 2.60907  | 2.35907  |  2.75     |               2799 |            0.130046   |
|            62 | hgb_timewalk                 | 1.57207  | 1.5191   |  1.63685  |               2421 |            0.0169352  |
|            62 | s03a_global_population       | 1.68767  | 1.66664  |  1.71871  |               2421 |            0.0185874  |
|            62 | s03d_hierarchical_population | 1.07976  | 0.923031 |  1.21612  |               2421 |            0.0334572  |
|            62 | template_phase_base          | 2.35907  | 2.35907  |  2.60907  |               2421 |            0.148699   |
|            63 | hgb_timewalk                 | 1.51654  | 1.46757  |  1.61364  |               1110 |            0.0279279  |
|            63 | s03a_global_population       | 1.69744  | 1.67163  |  1.73767  |               1110 |            0.0243243  |
|            63 | s03d_hierarchical_population | 1.18067  | 1.03344  |  1.4452   |               1110 |            0.0369369  |
|            63 | template_phase_base          | 2.75242  | 2.35907  |  3.00242  |               1110 |            0.16036    |
|            65 | hgb_timewalk                 | 1.53347  | 1.3353   |  1.74977  |                198 |            0.020202   |
|            65 | s03a_global_population       | 1.6526   | 1.59977  |  1.70456  |                198 |            0.0151515  |
|            65 | s03d_hierarchical_population | 0.725871 | 0.493232 |  1.19627  |                198 |            0.030303   |
|            65 | template_phase_base          | 2.35907  | 2.35907  |  2.75242  |                198 |            0.111111   |

Pooled intervals resample held-out runs, not individual residuals.

| method                       |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base          | 2.5     |  2.35907 |   2.60907 |              11460 |             0.149738  |
| s03a_global_population       | 1.72254 |  1.68138 |   1.94624 |              11460 |             0.0222513 |
| s03d_hierarchical_population | 1.14324 |  1.0243  |   1.24314 |              11460 |             0.0324607 |
| hgb_timewalk                 | 1.67331 |  1.57212 |   1.79832 |              11460 |             0.0259162 |

## 4. Leakage checks

Feature construction excludes run number, event id/order, sample label, current, and cross-stave timing. Sample-II targets are calculated only for evaluation diagnostics. Shuffled-target controls were trained on Sample-I analysis rows and evaluated blindly on Sample-II rows.

| check                                                 |   min_value |   median_value |   max_value |
|:------------------------------------------------------|------------:|---------------:|------------:|
| feature_audit_forbidden_run_event_current_identifiers |     0       |        0       |     0       |
| final_models_use_sample_ii_rows                       |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                           |     2.85217 |        2.85217 |     2.85217 |
| s03a_shuffled_target_sigma68                          |     2.56154 |        2.56154 |     2.56154 |
| s03d_heldout_run_deviation_terms_zero                 |     1       |        1       |     1       |
| s03d_hier_shuffled_target_sigma68                     |     2.52694 |        2.52694 |     2.52694 |
| train_heldout_event_id_overlap                        |     0       |        0       |     0       |
| train_heldout_run_overlap                             |     0       |        0       |     0       |

## 5. Verdict

`result.json` verdict: `sample_i_analysis_population_transfer_supported_no_leakage_flag`.
S03a global population sigma68 is `1.723 ns`; S03d hierarchical population is `1.143 ns`; HGB is `1.673 ns`.
The leakage flag is `False` and all split-overlap checks are zero.

## 6. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python /home/billy/.tb-workers/testbeam-laptop-2/scripts/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.py --config configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml
```

Artifacts: `reproduction_match_table.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `s03a_cv_scan.csv`, `s03a_coefficients.csv`, `s03d_hierarchical_cv_scan.csv`, `s03d_hierarchical_coefficients.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

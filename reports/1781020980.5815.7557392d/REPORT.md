# Study report: S03f - Robust heavy-tail analytic timewalk loss

- **Ticket:** 1781020980.5815.7557392d
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03f_1781020980_5815_7557392d_robust_heavytail_timewalk.yaml`

## 0. Question

Test whether the run-61 residual width left by S03d is mainly a heavy-tail loss problem rather than coefficient drift.

## 1. Raw-ROOT reproduction gate

Selected-pulse counts were rerun from raw ROOT before any robust fit.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03d run-61 reference numbers were then reproduced from the same raw-derived pulse table before scanning robust losses.

|   heldout_run | method                 | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | s03a_candidate   |   s03a_alpha |   hier_alpha_global |   hier_alpha_dev |   hgb_cv_sigma68_ns |   reference_value |        delta | pass   |
|--------------:|:-----------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:-----------------|-------------:|--------------------:|-----------------:|--------------------:|------------------:|-------------:|:-------|
|            61 | template_phase_base    | heldout_pairwise_sigma68_ns | 2.70351 |  2.70351 |   2.70351 |               2799 |    -2.62917 |      2.70351 |       3.20716 |             0.0428725 |        41.982   |    64.5067 | amp_only         |          100 |                 100 |              100 |             1.37105 |           2.70351 | -4.44089e-16 | True   |
|            61 | s03a_amp_only_global   | heldout_pairwise_sigma68_ns | 2.12996 |  1.99071 |   2.20164 |               2799 |     2.1181  |      2.12996 |       3.00806 |             0.0314398 |         2.46885 |    17.9529 | amp_only         |          100 |                 100 |              100 |             1.37105 |           2.12996 |  0           | True   |
|            61 | hierarchical_shrinkage | heldout_pairwise_sigma68_ns | 1.63537 |  1.53346 |   1.68065 |               2799 |     1.19958 |      1.63537 |       2.77569 |             0.0228653 |         1.58291 |    11.6531 | amp_only         |          100 |                 100 |              100 |             1.37105 |           1.63537 | -2.22045e-16 | True   |
|            61 | hgb_timewalk           | heldout_pairwise_sigma68_ns | 1.81739 |  1.75063 |   1.91533 |               2799 |     1.89728 |      1.81739 |       2.67476 |             0.022508  |         2.16933 |    13.0101 | amp_only         |          100 |                 100 |              100 |             1.37105 |           1.81739 |  2.22045e-16 | True   |

## 2. Methods

Traditional baselines are global S03a amp-only ridge and S03d hierarchical shrinkage. Robust traditional variants refit the same amp-only analytic residual target with Huber IRLS and trimmed-target ridge. The ML comparator is a HistGradientBoosting residual corrector with absolute-error loss. All scores are leave-one-run-out and bootstrapped on held-out residuals; pooled intervals resample held-out runs.

## 3. Held-out head-to-head

|   heldout_run | method                      |    value |   ci_low |   ci_high |   n_pair_residuals |   robust_huber_cv_sigma68_ns |   robust_trimmed_cv_sigma68_ns |   hgb_robust_cv_sigma68_ns |
|--------------:|:----------------------------|---------:|---------:|----------:|-------------------:|-----------------------------:|-------------------------------:|---------------------------:|
|            58 | ml_hgb_absolute_error       | 1.14473  | 1.14212  |   1.21001 |                219 |                      1.58093 |                        1.57258 |                    1.39376 |
|            58 | robust_huber_ridge          | 1.23466  | 1.19132  |   1.32459 |                219 |                      1.58093 |                        1.57258 |                    1.39376 |
|            58 | robust_trimmed_ridge        | 1.21828  | 1.16612  |   1.31722 |                219 |                      1.58093 |                        1.57258 |                    1.39376 |
|            58 | s03a_amp_only_global        | 1.18748  | 1.13462  |   1.37382 |                219 |                      1.58093 |                        1.57258 |                    1.39376 |
|            58 | s03d_hierarchical_shrinkage | 0.766925 | 0.691953 |   1.00998 |                219 |                      1.58093 |                        1.57258 |                    1.39376 |
|            58 | template_phase_base         | 2.6428   | 2.6428   |   2.77317 |                219 |                      1.58093 |                        1.57258 |                    1.39376 |
|            59 | ml_hgb_absolute_error       | 1.21924  | 1.17208  |   1.27533 |               2289 |                      1.54463 |                        1.53957 |                    1.42313 |
|            59 | robust_huber_ridge          | 1.42875  | 1.36782  |   1.5098  |               2289 |                      1.54463 |                        1.53957 |                    1.42313 |
|            59 | robust_trimmed_ridge        | 1.43853  | 1.36698  |   1.49989 |               2289 |                      1.54463 |                        1.53957 |                    1.42313 |
|            59 | s03a_amp_only_global        | 1.45871  | 1.39679  |   1.51912 |               2289 |                      1.54463 |                        1.53957 |                    1.42313 |
|            59 | s03d_hierarchical_shrinkage | 1.22376  | 1.1557   |   1.25263 |               2289 |                      1.54463 |                        1.53957 |                    1.42313 |
|            59 | template_phase_base         | 2.99232  | 2.9828   |   3.12333 |               2289 |                      1.54463 |                        1.53957 |                    1.42313 |
|            60 | ml_hgb_absolute_error       | 1.05963  | 1.05725  |   1.09376 |               2424 |                      1.53172 |                        1.53197 |                    1.35427 |
|            60 | robust_huber_ridge          | 1.3338   | 1.27299  |   1.3978  |               2424 |                      1.53172 |                        1.53197 |                    1.35427 |
|            60 | robust_trimmed_ridge        | 1.33579  | 1.27579  |   1.39442 |               2424 |                      1.53172 |                        1.53197 |                    1.35427 |
|            60 | s03a_amp_only_global        | 1.3437   | 1.2923   |   1.39789 |               2424 |                      1.53172 |                        1.53197 |                    1.35427 |
|            60 | s03d_hierarchical_shrinkage | 1.05251  | 1.0105   |   1.09789 |               2424 |                      1.53172 |                        1.53197 |                    1.35427 |
|            60 | template_phase_base         | 2.66393  | 2.66393  |   2.7113  |               2424 |                      1.53172 |                        1.53197 |                    1.35427 |
|            61 | ml_hgb_absolute_error       | 1.92486  | 1.87896  |   2.00836 |               2799 |                      1.49263 |                        1.48199 |                    1.29822 |
|            61 | robust_huber_ridge          | 2.13267  | 2.0168   |   2.23813 |               2799 |                      1.49263 |                        1.48199 |                    1.29822 |
|            61 | robust_trimmed_ridge        | 2.13632  | 2.00008  |   2.22326 |               2799 |                      1.49263 |                        1.48199 |                    1.29822 |
|            61 | s03a_amp_only_global        | 2.12996  | 1.98826  |   2.20721 |               2799 |                      1.49263 |                        1.48199 |                    1.29822 |
|            61 | s03d_hierarchical_shrinkage | 1.63537  | 1.53875  |   1.66595 |               2799 |                      1.49263 |                        1.48199 |                    1.29822 |
|            61 | template_phase_base         | 2.70351  | 2.70351  |   2.70351 |               2799 |                      1.49263 |                        1.48199 |                    1.29822 |
|            62 | ml_hgb_absolute_error       | 1.21176  | 1.16535  |   1.26766 |               2421 |                      1.55271 |                        1.55262 |                    1.39938 |
|            62 | robust_huber_ridge          | 1.44347  | 1.36988  |   1.52781 |               2421 |                      1.55271 |                        1.55262 |                    1.39938 |
|            62 | robust_trimmed_ridge        | 1.44621  | 1.38692  |   1.51521 |               2421 |                      1.55271 |                        1.55262 |                    1.39938 |
|            62 | s03a_amp_only_global        | 1.469    | 1.41593  |   1.52173 |               2421 |                      1.55271 |                        1.55262 |                    1.39938 |
|            62 | s03d_hierarchical_shrinkage | 1.18377  | 1.11039  |   1.25137 |               2421 |                      1.55271 |                        1.55262 |                    1.39938 |
|            62 | template_phase_base         | 2.90117  | 2.90117  |   3.02631 |               2421 |                      1.55271 |                        1.55262 |                    1.39938 |
|            63 | ml_hgb_absolute_error       | 1.1593   | 1.13344  |   1.2387  |               1110 |                      1.56604 |                        1.56178 |                    1.36387 |
|            63 | robust_huber_ridge          | 1.35597  | 1.29494  |   1.44152 |               1110 |                      1.56604 |                        1.56178 |                    1.36387 |
|            63 | robust_trimmed_ridge        | 1.3647   | 1.29461  |   1.44416 |               1110 |                      1.56604 |                        1.56178 |                    1.36387 |
|            63 | s03a_amp_only_global        | 1.39132  | 1.30905  |   1.45681 |               1110 |                      1.56604 |                        1.56178 |                    1.36387 |
|            63 | s03d_hierarchical_shrinkage | 1.11004  | 1.02222  |   1.21069 |               1110 |                      1.56604 |                        1.56178 |                    1.36387 |
|            63 | template_phase_base         | 2.87872  | 2.87872  |   3.01249 |               1110 |                      1.56604 |                        1.56178 |                    1.36387 |
|            65 | ml_hgb_absolute_error       | 1.14426  | 1.13588  |   1.40655 |                198 |                      1.58273 |                        1.58077 |                    1.40871 |
|            65 | robust_huber_ridge          | 1.47932  | 1.32488  |   1.64498 |                198 |                      1.58273 |                        1.58077 |                    1.40871 |
|            65 | robust_trimmed_ridge        | 1.48427  | 1.30028  |   1.64973 |                198 |                      1.58273 |                        1.58077 |                    1.40871 |
|            65 | s03a_amp_only_global        | 1.49464  | 1.34451  |   1.66169 |                198 |                      1.58273 |                        1.58077 |                    1.40871 |
|            65 | s03d_hierarchical_shrinkage | 1.21984  | 0.996838 |   1.41954 |                198 |                      1.58273 |                        1.58077 |                    1.40871 |
|            65 | template_phase_base         | 2.88915  | 2.63915  |   3.20541 |                198 |                      1.58273 |                        1.58077 |                    1.40871 |

| method                      |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:----------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base         | 2.74141 |  2.68422 |   2.99072 |              11460 |             0.0813264 |
| s03a_amp_only_global        | 1.55109 |  1.37402 |   1.9098  |              11460 |             0.0191099 |
| s03d_hierarchical_shrinkage | 1.251   |  1.07216 |   1.4866  |              11460 |             0.0153578 |
| robust_huber_ridge          | 1.54724 |  1.34075 |   1.89611 |              11460 |             0.0204188 |
| robust_trimmed_ridge        | 1.54516 |  1.3492  |   1.88381 |              11460 |             0.0200698 |
| ml_hgb_absolute_error       | 1.34364 |  1.14238 |   1.68587 |              11460 |             0.015445  |

Run 61 rows:

| method                      |   value |   ci_low |   ci_high |   n_pair_residuals |
|:----------------------------|--------:|---------:|----------:|-------------------:|
| ml_hgb_absolute_error       | 1.92486 |  1.87896 |   2.00836 |               2799 |
| robust_huber_ridge          | 2.13267 |  2.0168  |   2.23813 |               2799 |
| robust_trimmed_ridge        | 2.13632 |  2.00008 |   2.22326 |               2799 |
| s03a_amp_only_global        | 2.12996 |  1.98826 |   2.20721 |               2799 |
| s03d_hierarchical_shrinkage | 1.63537 |  1.53875 |   1.66595 |               2799 |
| template_phase_base         | 2.70351 |  2.70351 |   2.70351 |               2799 |

## 4. Leakage checks

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| hgb_abs_loss_shuffled_target_sigma68              |     2.6437  |        2.85064 |     2.99027 |
| robust_huber_shuffled_target_sigma68              |     2.63765 |        2.80672 |     3.05675 |
| robust_trimmed_shuffled_target_sigma68            |     2.62742 |        2.78543 |     3.06953 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

The analytic and HGB feature sets exclude run number, event id, event order, other-stave timing, current, and held-out labels. Shuffled-target controls were repeated for every held-out run.

## 5. Verdict

`result.json` verdict: `run61_not_primarily_heavy_tail_loss_no_leakage_flag`.
Best robust traditional method is `robust_trimmed_ridge` at `1.545 ns`; S03d hierarchical is `1.251 ns`; ML absolute-error HGB is `1.344 ns`.
On run 61, the best robust traditional score is `2.136 ns` versus S03d hierarchical `1.635 ns`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03f_1781020980_5815_7557392d_robust_heavytail_timewalk.py --config configs/s03f_1781020980_5815_7557392d_robust_heavytail_timewalk.yaml
```

Artifacts: `reproduction_match_table.csv`, `run61_reference_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hierarchical_cv_scan.csv`, `robust_cv_scan.csv`, `robust_coefficients.csv`, `hgb_robust_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

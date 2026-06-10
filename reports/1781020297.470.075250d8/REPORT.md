# Study report: S03g - HGB timewalk feature monotonicity audit

- **Ticket:** `1781020297.470.075250d8`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03g_1781020297_470_075250d8_hgb_monotonicity_audit.yaml`

## 0. Question

Does the S03d HGB gain come from legitimate amplitude/shape residual structure, or from non-monotone local features that fail run transfer?

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

The S03d pooled numbers named in the ticket were reproduced from the raw-derived pulse table before the audit.

| method                 |   reference_sigma68_ns |   reproduced_sigma68_ns |   delta_ns |   tolerance_ns | pass   |
|:-----------------------|-----------------------:|------------------------:|-----------:|---------------:|:-------|
| s03a_amp_only          |                1.55109 |                 1.55109 |          0 |          0.005 | True   |
| hgb_full_unconstrained |                1.39397 |                 1.39397 |          0 |          0.005 | True   |

## 2. Methods

Traditional references are the frozen S03a amp-only Ridge correction, a physically signed shared-stave inverse-amplitude shrinkage model, and the S03b monotone decreasing residual table. The ML audit compares the original HGB feature set with a log-amplitude monotonic constraint, amplitude-only, shape-only, and stave-only controls. No method uses run number, event id, event order, current, cross-stave timing, or held-out labels.

## 3. Held-out results

| method                  |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   full_rms_ns |   full_rms_ns_ci_low |   full_rms_ns_ci_high |   tail_frac_abs_gt5ns |   bias_vs_log_amp_slope_ns |   n_pair_residuals |
|:------------------------|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|----------------------:|---------------------------:|-------------------:|
| template_phase_base     |      2.74141 |             2.68422 |              2.98617 |       3.30837 |              3.25038 |               3.35805 |             0.0813264 |                   3.74095  |              11460 |
| s03a_amp_only           |      1.55109 |             1.36698 |              1.95444 |       2.66699 |              2.44734 |               2.87536 |             0.0191099 |                  -0.283729 |              11460 |
| signed_shared_shrinkage |      1.53985 |             1.26741 |              1.945   |       2.70053 |              2.49377 |               2.90759 |             0.022164  |                   0.247162 |              11460 |
| monotone_residual_table |      1.64515 |             1.32559 |              1.9317  |       2.71603 |              2.48691 |               2.93526 |             0.019459  |                  -0.62603  |              11460 |
| hgb_full_unconstrained  |      1.39397 |             1.24131 |              1.65384 |       2.38001 |              2.15714 |               2.57324 |             0.0156195 |                  -0.888168 |              11460 |
| full_monotone_log_amp   |      1.37252 |             1.20671 |              1.60012 |       2.42708 |              2.22485 |               2.57934 |             0.0150087 |                  -0.728472 |              11460 |
| amplitude_only          |      1.43646 |             1.28321 |              1.74896 |       2.54856 |              2.34619 |               2.71216 |             0.017801  |                  -0.977546 |              11460 |
| shape_only              |      1.3599  |             1.1764  |              1.62663 |       2.44264 |              2.2193  |               2.62026 |             0.0157068 |                  -0.556472 |              11460 |
| stave_only              |      1.37186 |             1.12186 |              1.7988  |       2.63832 |              2.4322  |               2.83878 |             0.0208551 |                   0.419832 |              11460 |

|   heldout_run | method                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_vs_log_amp_slope_ns |
|--------------:|:------------------------|-------------:|---------:|----------:|--------------:|----------------------:|---------------------------:|
|            58 | amplitude_only          |     1.16546  | 1.01056  |   1.59718 |       2.69643 |            0.0273973  |                 -0.718595  |
|            58 | full_monotone_log_amp   |     1.04612  | 0.953225 |   1.3399  |       2.55938 |            0.0182648  |                  0.23552   |
|            58 | hgb_full_unconstrained  |     1.0863   | 0.984964 |   1.29916 |       2.56038 |            0.0136986  |                  0.455704  |
|            58 | monotone_residual_table |     1.3214   | 1.3214   |   1.61026 |       2.78333 |            0.0319635  |                  0.0227206 |
|            58 | s03a_amp_only           |     1.18748  | 1.14022  |   1.33873 |       2.67793 |            0.0182648  |                  0.497825  |
|            58 | shape_only              |     1.13192  | 0.937471 |   1.30997 |       2.54574 |            0.0182648  |                  0.54667   |
|            58 | signed_shared_shrinkage |     1.1876   | 1.16728  |   1.2819  |       2.76003 |            0.0319635  |                  0.778252  |
|            58 | stave_only              |     0.977862 | 0.977862 |   1.00711 |       2.69645 |            0.0273973  |                  0.981195  |
|            58 | template_phase_base     |     2.6428   | 2.6428   |   2.77317 |       3.54397 |            0.0776256  |                  3.68782   |
|            59 | amplitude_only          |     1.29685  | 1.26866  |   1.41    |       2.45879 |            0.0122324  |                 -1.34559   |
|            59 | full_monotone_log_amp   |     1.24522  | 1.18154  |   1.31473 |       2.46477 |            0.0131062  |                 -1.31308   |
|            59 | hgb_full_unconstrained  |     1.26298  | 1.21789  |   1.31149 |       2.39764 |            0.0122324  |                 -1.42354   |
|            59 | monotone_residual_table |     1.5      | 1.34527  |   1.56166 |       2.59383 |            0.0157274  |                 -1.18636   |
|            59 | s03a_amp_only           |     1.45871  | 1.3968   |   1.52705 |       2.54019 |            0.0144168  |                 -0.959826  |
|            59 | shape_only              |     1.22855  | 1.17574  |   1.28848 |       2.46191 |            0.0126693  |                 -1.19138   |
|            59 | signed_shared_shrinkage |     1.31744  | 1.26121  |   1.49364 |       2.57631 |            0.0174749  |                 -0.513133  |
|            59 | stave_only              |     1.39106  | 1.10894  |   1.48467 |       2.52147 |            0.017038   |                 -0.323298  |
|            59 | template_phase_base     |     2.99232  | 2.99232  |   3.12333 |       3.34278 |            0.0677152  |                  3.06363   |
|            60 | amplitude_only          |     1.23953  | 1.20572  |   1.31915 |       2.30735 |            0.0123762  |                 -1.15111   |
|            60 | full_monotone_log_amp   |     1.17399  | 1.11974  |   1.23363 |       2.14627 |            0.0123762  |                 -0.723157  |
|            60 | hgb_full_unconstrained  |     1.22758  | 1.16203  |   1.26732 |       2.10963 |            0.0165017  |                 -0.978776  |
|            60 | monotone_residual_table |     1.23065  | 1.23065  |   1.25    |       2.42144 |            0.0156766  |                 -0.327281  |
|            60 | s03a_amp_only           |     1.3437   | 1.28855  |   1.39564 |       2.39529 |            0.015264   |                  0.179917  |
|            60 | shape_only              |     1.16215  | 1.11797  |   1.18809 |       2.15715 |            0.0140264  |                 -0.392422  |
|            60 | signed_shared_shrinkage |     1.26741  | 1.25     |   1.26741 |       2.4353  |            0.0165017  |                  0.817623  |
|            60 | stave_only              |     1.12186  | 1.12186  |   1.25    |       2.38599 |            0.0165017  |                  0.96696   |
|            60 | template_phase_base     |     2.66393  | 2.66393  |   2.7113  |       3.279   |            0.0944719  |                  4.08159   |
|            61 | amplitude_only          |     1.92439  | 1.85327  |   2.07695 |       2.84859 |            0.0278671  |                 -0.837736  |
|            61 | full_monotone_log_amp   |     1.84436  | 1.7755   |   1.90033 |       2.66994 |            0.0217935  |                 -0.487916  |
|            61 | hgb_full_unconstrained  |     1.81739  | 1.74881  |   1.92439 |       2.67476 |            0.022508   |                 -0.73385   |
|            61 | monotone_residual_table |     2.10176  | 2.10176  |   2.2466  |       3.07643 |            0.0310825  |                 -0.728796  |
|            61 | s03a_amp_only           |     2.12996  | 1.99343  |   2.20645 |       3.00806 |            0.0314398  |                 -0.267216  |
|            61 | shape_only              |     1.83097  | 1.78146  |   1.88087 |       2.73723 |            0.0232226  |                 -0.381994  |
|            61 | signed_shared_shrinkage |     2.12389  | 1.95025  |   2.20025 |       3.04553 |            0.035727   |                  0.282255  |
|            61 | stave_only              |     1.9666   | 1.77167  |   2.02167 |       2.96517 |            0.0307253  |                  0.465821  |
|            61 | template_phase_base     |     2.70351  | 2.70351  |   2.70351 |       3.20716 |            0.0428725  |                  4.29511   |
|            62 | amplitude_only          |     1.3579   | 1.29244  |   1.41739 |       2.47473 |            0.0115655  |                 -1.02894   |
|            62 | full_monotone_log_amp   |     1.28309  | 1.23173  |   1.36041 |       2.37521 |            0.0103263  |                 -0.913236  |
|            62 | hgb_full_unconstrained  |     1.2974   | 1.25258  |   1.35827 |       2.27287 |            0.00950021 |                 -1.01518   |
|            62 | monotone_residual_table |     1.43743  | 1.39953  |   1.57347 |       2.64762 |            0.0144568  |                 -0.743857  |
|            62 | s03a_amp_only           |     1.469    | 1.41226  |   1.51606 |       2.58419 |            0.0128046  |                 -0.453692  |
|            62 | shape_only              |     1.26318  | 1.20966  |   1.33248 |       2.36612 |            0.0103263  |                 -0.742871  |
|            62 | signed_shared_shrinkage |     1.37314  | 1.30899  |   1.49557 |       2.60374 |            0.0148699  |                  0.092849  |
|            62 | stave_only              |     1.25     | 1.25     |   1.47032 |       2.54375 |            0.0128046  |                  0.293683  |
|            62 | template_phase_base     |     2.90117  | 2.90117  |   3.02631 |       3.35891 |            0.0929368  |                  3.78351   |
|            63 | amplitude_only          |     1.27544  | 1.1791   |   1.37918 |       2.43213 |            0.0171171  |                 -1.28111   |
|            63 | full_monotone_log_amp   |     1.2464   | 1.13705  |   1.32044 |       2.3057  |            0.0171171  |                 -0.930846  |
|            63 | hgb_full_unconstrained  |     1.27127  | 1.1609   |   1.33122 |       2.22036 |            0.0171171  |                 -1.02767   |
|            63 | monotone_residual_table |     1.43311  | 1.31436  |   1.56436 |       2.68746 |            0.0198198  |                 -1.0538    |
|            63 | s03a_amp_only           |     1.39132  | 1.31     |   1.4636  |       2.62807 |            0.0207207  |                 -0.851434  |
|            63 | shape_only              |     1.2077   | 1.15423  |   1.31633 |       2.30113 |            0.018018   |                 -0.744303  |
|            63 | signed_shared_shrinkage |     1.11121  | 1.11121  |   1.48872 |       2.6404  |            0.0216216  |                 -0.284092  |
|            63 | stave_only              |     1.13298  | 1.05106  |   1.36702 |       2.58929 |            0.0198198  |                 -0.125315  |
|            63 | template_phase_base     |     2.87872  | 2.87872  |   3.01249 |       3.38179 |            0.0963964  |                  3.41413   |
|            65 | amplitude_only          |     1.35817  | 1.21229  |   1.58292 |       1.59163 |            0          |                 -0.660568  |
|            65 | full_monotone_log_amp   |     1.32552  | 1.12063  |   1.50674 |       1.53021 |            0.00505051 |                 -0.246787  |
|            65 | hgb_full_unconstrained  |     1.36865  | 1.20601  |   1.64043 |       1.54512 |            0.00505051 |                 -0.489704  |
|            65 | monotone_residual_table |     1.56958  | 1.33531  |   1.81958 |       1.83396 |            0.00505051 |                 -0.801151  |
|            65 | s03a_amp_only           |     1.49464  | 1.34535  |   1.64103 |       1.69913 |            0.00505051 |                 -0.674101  |
|            65 | shape_only              |     1.29789  | 1.08761  |   1.5732  |       1.50451 |            0          |                 -0.336838  |
|            65 | signed_shared_shrinkage |     1.44175  | 1.26762  |   1.67308 |       1.72997 |            0.00505051 |                 -0.31316   |
|            65 | stave_only              |     1.22728  | 1.06067  |   1.56991 |       1.619   |            0.00505051 |                 -0.0865046 |
|            65 | template_phase_base     |     2.88915  | 2.63915  |   3.24309 |       2.57669 |            0.0505051  |                  3.11219   |

## 4. Paired ML-minus-traditional deltas

| ml_method              | traditional_method      | metric                   |   delta_ml_minus_traditional |      ci_low |      ci_high | bootstrap_unit   |
|:-----------------------|:------------------------|:-------------------------|-----------------------------:|------------:|-------------:|:-----------------|
| hgb_full_unconstrained | monotone_residual_table | sigma68_ns               |                  -0.188262   | -0.322104   | -0.0691825   | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | full_rms_ns              |                  -0.335167   | -0.399561   | -0.251082    | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | tail_frac_abs_gt5ns      |                  -0.0045766  | -0.0112093  | -0.00123855  | heldout_run      |
| hgb_full_unconstrained | monotone_residual_table | bias_vs_log_amp_slope_ns |                  -0.262049   | -0.479341   | -0.043955    | heldout_run      |
| full_monotone_log_amp  | monotone_residual_table | sigma68_ns               |                  -0.21387    | -0.367187   | -0.103454    | heldout_run      |
| full_monotone_log_amp  | monotone_residual_table | full_rms_ns              |                  -0.289276   | -0.369738   | -0.203405    | heldout_run      |
| full_monotone_log_amp  | monotone_residual_table | tail_frac_abs_gt5ns      |                  -0.00442273 | -0.0111213  | -0.00293266  | heldout_run      |
| full_monotone_log_amp  | monotone_residual_table | bias_vs_log_amp_slope_ns |                  -0.0991923  | -0.296948   |  0.127279    | heldout_run      |
| amplitude_only         | monotone_residual_table | sigma68_ns               |                  -0.131663   | -0.267945   | -0.0117036   | heldout_run      |
| amplitude_only         | monotone_residual_table | full_rms_ns              |                  -0.170653   | -0.2138     | -0.135929    | heldout_run      |
| amplitude_only         | monotone_residual_table | tail_frac_abs_gt5ns      |                  -0.00313526 | -0.00814171 | -0.00134754  | heldout_run      |
| amplitude_only         | monotone_residual_table | bias_vs_log_amp_slope_ns |                  -0.344188   | -0.618055   | -0.123181    | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | sigma68_ns               |                  -0.124547   | -0.263084   | -0.0143006   | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | full_rms_ns              |                  -0.320363   | -0.377963   | -0.237876    | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | tail_frac_abs_gt5ns      |                  -0.00623017 | -0.0133963  | -0.00272057  | heldout_run      |
| hgb_full_unconstrained | signed_shared_shrinkage | bias_vs_log_amp_slope_ns |                  -1.12066    | -1.42983    | -0.855428    | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | sigma68_ns               |                  -0.162508   | -0.252829   | -0.125697    | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | full_rms_ns              |                  -0.288522   | -0.34723    | -0.210146    | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | tail_frac_abs_gt5ns      |                  -0.00343938 | -0.00708743 | -0.000422801 | heldout_run      |
| hgb_full_unconstrained | s03a_amp_only           | bias_vs_log_amp_slope_ns |                  -0.595705   | -0.855895   | -0.336       | heldout_run      |

## 5. Leakage checks

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| amplitude_only_shuffled_target_sigma68            |     2.67456 |        2.88915 |     3.005   |
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| full_monotone_log_amp_shuffled_target_sigma68     |     2.68173 |        2.8487  |     3.0104  |
| full_unconstrained_shuffled_target_sigma68        |     2.68756 |        2.83371 |     3.01676 |
| monotone_log_amp_best_direction                   |    -1       |       -1       |     1       |
| shape_only_shuffled_target_sigma68                |     2.6962  |        2.8537  |     2.99896 |
| stave_only_shuffled_target_sigma68                |     2.65388 |        2.83138 |     2.99863 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

## 6. Verdict

`result.json` verdict: `hgb_gain_partly_nonmonotone_or_control_limited`.
Original HGB sigma68 is `1.394 ns` versus S03a `1.551 ns`, signed shrinkage `1.540 ns`, and monotone table `1.645 ns`.
The monotone-log-amplitude HGB is `1.373 ns`; shape-only is `1.360 ns`; stave-only is `1.372 ns`.

## 7. Reproducibility

Generated by:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03g_1781020297_470_075250d8_hgb_monotonicity_audit.py --config configs/s03g_1781020297_470_075250d8_hgb_monotonicity_audit.yaml
```

Artifacts: `reproduction_match_table.csv`, `reference_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `paired_deltas.csv`, `pairwise_residuals.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

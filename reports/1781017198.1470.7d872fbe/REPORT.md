# P06a: amplitude-binned timing resolution atom table

- **Ticket:** `1781017198.1470.7d872fbe`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo
- **Split:** leave-one-run-out over Sample-II analysis runs 58-63 and 65

## Reproduction first

The S00 selected-pulse count gate and the S03a analytic timewalk closure were rerun from raw ROOT before this study.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals | best_candidate   |   best_alpha |
|:------------------------|--------:|---------:|----------:|-------------------:|:-----------------|-------------:|
| s02_template_phase_base | 2.88915 |  2.66602 |   3.08093 |                198 | amp_only         |          100 |
| s03a_analytic_timewalk  | 1.49464 |  1.39584 |   1.59282 |                198 | amp_only         |          100 |

## Methods

The traditional method freezes the S02 template-phase pickoff and the S03a amplitude-only analytic timewalk form (`amp_only`, Ridge alpha 100), refit inside each training-run pool and evaluated only on the held-out run.

The ML method is a per-pulse Ridge residual model plus a Ridge absolute-residual uncertainty model. Features are waveform summaries, train-fold PCA latent summaries, charge proxy, template-shape residual, and saturation summaries. It excludes run id, event ids, event order, timing columns, pair residuals, and labels.

CIs are event-paired run-block bootstrap intervals. Pair strata use pair-mean amplitude/charge, max peak sample, any saturation flag, and the non-common P09-like class when present.

## Overall Timing

Pairwise residuals:

| pair   | method      |    n |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   pull_width68 |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_ns |
|:-------|:------------|-----:|-------------:|--------------------:|---------------------:|---------------:|--------------:|----------------------:|----------:|
| B4-B6  | ml          | 3820 |      1.53136 |            1.39794  |              1.59741 |       0.339547 |       2.44552 |             0.0151832 | -3.68981  |
| B4-B8  | ml          | 3820 |      1.64458 |            1.55529  |              1.72506 |       0.384963 |       2.90927 |             0.0282723 | -2.66375  |
| B6-B8  | ml          | 3820 |      1.58155 |            1.50835  |              1.64789 |       0.392355 |       2.24671 |             0.015445  |  1.02606  |
| B4-B6  | traditional | 3820 |      1.19699 |            0.99922  |              1.3001  |     nan        |       2.39108 |             0.0149215 |  2.17497  |
| B4-B8  | traditional | 3820 |      1.20294 |            0.988703 |              1.31273 |     nan        |       2.80217 |             0.0196335 |  1.86625  |
| B6-B8  | traditional | 3820 |      1.0236  |            0.950638 |              1.08986 |     nan        |       2.02589 |             0.0091623 | -0.308718 |

Single-stave residuals:

| stave   | method      |    n |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   pull_width68 |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_ns |
|:--------|:------------|-----:|-------------:|--------------------:|---------------------:|---------------:|--------------:|----------------------:|----------:|
| B4      | ml          | 3820 |     1.39799  |            1.28625  |              1.45234 |       0.473468 |       2.44137 |             0.0172775 | -3.17678  |
| B6      | ml          | 3820 |     1.31979  |            1.24665  |              1.39293 |       0.391985 |       1.84341 |             0.013089  |  2.35793  |
| B8      | ml          | 3820 |     1.4251   |            1.34759  |              1.48191 |       0.547198 |       2.29361 |             0.0204188 |  0.818849 |
| B4      | traditional | 3820 |     1.06758  |            0.88466  |              1.19616 |     nan        |       2.39972 |             0.0162304 |  2.02061  |
| B6      | traditional | 3820 |     0.955571 |            0.839214 |              1.0245  |     nan        |       1.71689 |             0.0136126 | -1.24184  |
| B8      | traditional | 3820 |     0.940059 |            0.808541 |              1.02135 |     nan        |       2.13281 |             0.0157068 | -0.778768 |

## Largest Traditional Atomic Widths

| dimension         | stratum                       | pair   |    n |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_ns |
|:------------------|:------------------------------|:-------|-----:|-------------:|--------------:|----------------------:|----------:|
| p09_anomaly_class | novel_broad_template_mismatch | B4-B6  |    8 |     10.4985  |      13.7472  |             0.625     |  2.24022  |
| p09_anomaly_class | novel_broad_template_mismatch | B4-B8  |   12 |     10.3374  |      14.4583  |             0.5       | -1.30652  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  |   19 |      8.23939 |      11.9818  |             0.526316  |  5.65949  |
| charge_bin        | charge[40000,80000)           | B4-B8  |   15 |      7.43592 |      12.945   |             0.533333  |  5.54433  |
| p09_anomaly_class | dropout                       | B4-B8  |   13 |      3.51709 |       9.96555 |             0.230769  | -2.12264  |
| p09_anomaly_class | novel_broad_template_mismatch | B6-B8  |    6 |      3.16724 |      10.9022  |             0.166667  | -5.51873  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B8  |  213 |      2.39596 |       5.46402 |             0.103286  |  4.04915  |
| charge_bin        | charge[40000,80000)           | B4-B6  |    8 |      2.32291 |       4.64753 |             0.125     |  3.1245   |
| amplitude_bin     | amp_adc[4000,7000)            | B6-B8  |  260 |      1.81079 |       2.36394 |             0.0307692 |  0.910402 |
| charge_bin        | charge[40000,80000)           | B6-B8  |    7 |      1.64889 |       4.78986 |             0.285714  | -0.182897 |
| charge_bin        | charge[24000,40000)           | B4-B6  |  362 |      1.5847  |       4.94893 |             0.0745856 |  2.83928  |
| charge_bin        | charge[24000,40000)           | B4-B8  | 1619 |      1.47958 |       2.76581 |             0.0290303 |  2.21708  |

## ML Minus Traditional

| granularity   | dimension         | stratum                       | stave   |   traditional_sigma68_ns |   ml_sigma68_ns |   ml_minus_traditional_sigma68_ns | method               | pair   |
|:--------------|:------------------|:------------------------------|:--------|-------------------------:|----------------:|----------------------------------:|:---------------------|:-------|
| single_stave  | charge_bin        | charge[40000,80000)           | B4      |                16.8618   |      14.9276    |                        -1.93414   | ml_minus_traditional | nan    |
| single_stave  | p09_anomaly_class | novel_broad_template_mismatch | B4      |                11.4387   |      10.7462    |                        -0.692407  | ml_minus_traditional | nan    |
| pairwise      | saturation_flag   | True                          | nan     |                 5.14988  |       4.60732   |                        -0.542564  | ml_minus_traditional | B4-B8  |
| single_stave  | peak_sample_bin   | peak_10                       | B4      |                 1.34198  |       1.20267   |                        -0.139309  | ml_minus_traditional | nan    |
| pairwise      | p09_anomaly_class | novel_broad_template_mismatch | nan     |                10.4985   |      10.3634    |                        -0.135111  | ml_minus_traditional | B4-B6  |
| single_stave  | peak_sample_bin   | peak_9                        | B4      |                 1.5863   |       1.46734   |                        -0.118965  | ml_minus_traditional | nan    |
| pairwise      | peak_sample_bin   | peakmax_11                    | nan     |                 1.64847  |       1.55865   |                        -0.089815  | ml_minus_traditional | B4-B8  |
| single_stave  | amplitude_bin     | amp_adc[4000,7000)            | B6      |                 4.18281  |       4.09577   |                        -0.0870384 | ml_minus_traditional | nan    |
| pairwise      | p09_anomaly_class | novel_broad_template_mismatch | nan     |                10.3374   |      10.2969    |                        -0.0405883 | ml_minus_traditional | B4-B8  |
| single_stave  | p09_anomaly_class | pileup_or_long_tail           | B6      |                 0.086668 |       0.0472348 |                        -0.0394332 | ml_minus_traditional | nan    |
| single_stave  | charge_bin        | charge[40000,80000)           | B8      |                 1.48228  |       1.45446   |                        -0.0278165 | ml_minus_traditional | nan    |
| single_stave  | p09_anomaly_class | novel_broad_template_mismatch | B6      |                 0        |       0         |                         0         | ml_minus_traditional | nan    |
| single_stave  | p09_anomaly_class | dropout                       | B8      |                 0        |       0         |                         0         | ml_minus_traditional | nan    |
| single_stave  | p09_anomaly_class | dropout                       | B6      |                 0        |       0         |                         0         | ml_minus_traditional | nan    |
| pairwise      | saturation_flag   | True                          | nan     |                 0        |       0         |                         0         | ml_minus_traditional | B4-B6  |
| single_stave  | amplitude_bin     | amp_adc[7000,12000)           | B4      |                 0        |       0         |                         0         | ml_minus_traditional | nan    |

## Leakage Audit

| check                                   |    value | pass   | note                                                                                                                                   |
|:----------------------------------------|---------:|:-------|:---------------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_event_id_overlap          | 0        | True   | event_id includes run, EVENTNO, EVT, and loader offset                                                                                 |
| ml_forbidden_feature_audit              | 0        | True   | ML feature matrix excludes run, event id, event order, labels, timing columns, pair residuals, and traditional residual target columns |
| ml_vs_traditional_pair_sigma68_delta_ns | 0.444656 | True   | positive means ML is wider than the frozen S03 analytic method                                                                         |

## Artifacts

`single_stave_strata.csv` and `pairwise_strata.csv` are the main atom tables. Delta tables, residual-row tables, fold metadata, `result.json`, and `manifest.json` are in the same report folder.

`result.json` verdict: `atomic_tables_written_ml_not_better_than_frozen_s03a`.

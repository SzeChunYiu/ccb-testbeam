# S05e-rate: run-level A/B coincidence-rate model

- **Ticket:** 1781017418.11875.10723959
- **Worker:** testbeam-laptop-4
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05e_1781017418_11875_10723959_run_level_ab_rate_model.yaml`
- **Raw input:** `data/root/root`

## Question

Build a run-level A/B coincidence-rate model across current and target settings, then compare it against B-stack residual covariance summaries to test whether beam-rate effects can explain the S05 B2-local covariance.

## Reproduction first

The raw ROOT gate was run before modeling: `h101/HRDv`, median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, physical A channels `A1/A3 = 0/4`, and `A > 1000 ADC`.

| quantity                                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses                         |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses            |         125096 |       125096 |       0 |           0 | True   |
| astack_sample_iii_analysis_events_with_selected |           7168 |         7168 |       0 |           0 | True   |
| astack_sample_iii_analysis_selected_pulses      |           9682 |         9682 |       0 |           0 | True   |
| astack_sample_iv_analysis_events_with_selected  |            767 |          767 |       0 |           0 | True   |
| astack_sample_iv_analysis_selected_pulses       |            894 |          894 |       0 |           0 | True   |

The S05 raw covariance anchors were also reproduced from the same B pair residual table before rate interpretation:

| quantity                               |   report_value |   reproduced |        delta |   tolerance | pass   |
|:---------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S05_raw_b2_containing_mean_abs_cov_ns2 |        1041.84 |    1041.84   |  7.49073e-05 |        0.05 | True   |
| S05_raw_downstream_mean_abs_cov_ns2    |          15.99 |      15.9882 | -0.00178499  |        0.05 | True   |

## Methods

Target: per-run `P(A_any selected | B_any selected)` with a Jeffreys-smoothed logit response. Run 46 and 47 are the 2 nA low-current controls; the other analysis runs are 20 nA. Target setting is Sample I (`sample_i_cd2`) versus Sample II (`sample_ii_p_enriched`).

Traditional method: weighted-logit Ridge using current, target setting, their interaction, and B-only topology/rate proxies (`b_multi_frac`, `b_downstream_frac`, `b_pair_rows_per_b_any`, `b2_share`, `log_b_any_events`). Alpha is selected by inner run-group CV inside each held-out fold.

ML method: ExtraTrees on the same allowed run-level features, with depth and leaf size selected by inner run-group CV. Features exclude run id, event id, all A-stack counts, and label columns. Evaluation is leave-one-run-held-out with run-block bootstrap CIs.

## Held-out rate benchmark

| method                           |   n_runs |   weighted_rmse_pp |   weighted_rmse_ci_low_pp |   weighted_rmse_ci_high_pp |   weighted_mae_pp |   weighted_mae_ci_low_pp |   weighted_mae_ci_high_pp |
|:---------------------------------|---------:|-------------------:|--------------------------:|---------------------------:|------------------:|-------------------------:|--------------------------:|
| traditional_weighted_logit_ridge |       21 |          10.4282   |                  0.628038 |                   19.787   |           1.91639 |                 0.362999 |                   5.26142 |
| ml_extra_trees_rate              |       21 |           0.906665 |                  0.485375 |                    1.29483 |           0.56194 |                 0.302087 |                   0.93892 |
| ml_shuffled_target_control       |       21 |           1.79212  |                  1.10359  |                    2.44824 |           1.13403 |                 0.579027 |                   1.86448 |

ML minus traditional RMSE is `-8.129` percentage points with 95% CI `[-18.044, 0.002]` and p=`0.052`. Shuffled-target minus ML RMSE is `0.889` percentage points with CI `[0.436, 1.287]`.

Held-out run predictions, in percent:

|   run | target_setting       |   current_nA |   b_any_events |   target_rate |   pred_traditional_rate |   pred_ml_rate |   resid_ml_rate_pp |
|------:|:---------------------|-------------:|---------------:|--------------:|------------------------:|---------------:|-------------------:|
|    44 | sample_i_cd2         |           20 |           1912 |      3.94668  |               6.43928   |       2.79255  |          1.15413   |
|    45 | sample_i_cd2         |           20 |          23004 |      3.92741  |               1.70735   |       1.67429  |          2.25311   |
|    46 | sample_i_cd2         |            2 |            661 |      2.94562  |               0.0160281 |       0.243961 |          2.70166   |
|    47 | sample_i_cd2         |            2 |           5141 |      3.56865  |              87.0148    |       0.563822 |          3.00483   |
|    48 | sample_i_cd2         |           20 |          13167 |      4.24894  |               1.84137   |       2.58705  |          1.66189   |
|    49 | sample_i_cd2         |           20 |          13919 |      3.95474  |               2.98646   |       2.58754  |          1.3672    |
|    50 | sample_i_cd2         |           20 |          34251 |      0.480264 |               0.216105  |       0.26061  |          0.219654  |
|    51 | sample_i_cd2         |           20 |          14291 |      0.297369 |               0.403921  |       0.521806 |         -0.224437  |
|    52 | sample_i_cd2         |           20 |           6933 |      0.151428 |               0.131688  |       0.405563 |         -0.254135  |
|    53 | sample_i_cd2         |           20 |          31385 |      0.116294 |               0.362347  |       0.45451  |         -0.338216  |
|    54 | sample_i_cd2         |           20 |          29638 |      0.163636 |               0.482736  |       0.282055 |         -0.118419  |
|    55 | sample_i_cd2         |           20 |          16820 |      0.270495 |               0.358516  |       0.413527 |         -0.143032  |
|    56 | sample_i_cd2         |           20 |          38913 |      0.558925 |               0.248043  |       0.329797 |          0.229128  |
|    57 | sample_i_cd2         |           20 |          12925 |      4.10413  |               7.39388   |       2.76476  |          1.33937   |
|    58 | sample_ii_p_enriched |           20 |          15890 |      0.437354 |               0.170992  |       0.951912 |         -0.514558  |
|    59 | sample_ii_p_enriched |           20 |          13863 |      0.155078 |               0.340457  |       0.300297 |         -0.145219  |
|    60 | sample_ii_p_enriched |           20 |          10139 |      0.20217  |               0.283298  |       0.180484 |          0.0216857 |
|    61 | sample_ii_p_enriched |           20 |          11282 |      0.226004 |               0.0512019 |       0.17099  |          0.0550136 |
|    62 | sample_ii_p_enriched |           20 |          11902 |      0.155423 |               0.286244  |       0.196628 |         -0.0412045 |
|    63 | sample_ii_p_enriched |           20 |          14756 |      0.545504 |               0.30866   |       0.432986 |          0.112518  |
|    65 | sample_ii_p_enriched |           20 |          11875 |      0.509431 |               1.09358   |       1.04201  |         -0.53258   |

## B covariance comparison

The rate model was compared to raw B-stack pair-residual covariance recomputed per run. Selected rank correlations against B2-containing covariance:

| covariance_metric                  | rate_or_topology_metric   |   spearman_rho |   spearman_ci_low |   spearman_ci_high |   n_runs |
|:-----------------------------------|:--------------------------|---------------:|------------------:|-------------------:|---------:|
| raw_b2_containing_mean_abs_cov_ns2 | pred_ml_rate              |       0.291729 |         -0.25467  |           0.739607 |       20 |
| raw_b2_containing_mean_abs_cov_ns2 | resid_ml_rate_pp          |       0.192481 |         -0.252315 |           0.555903 |       20 |
| raw_b2_containing_mean_abs_cov_ns2 | b_downstream_frac         |      -0.84812  |         -0.962153 |          -0.480956 |       20 |
| raw_b2_containing_mean_abs_cov_ns2 | b2_share                  |       0.723308 |          0.337811 |           0.937648 |       20 |

The large S05 B2 covariance anchor remains much larger than downstream-only covariance after the rate model is built. The ML predicted rate and ML rate residual do not form a stable explanatory axis for B2 covariance; topology terms such as B2 share remain the more plausible local handle.

## Leakage checks

| check                                 |    value | pass   | interpretation                                                                              |
|:--------------------------------------|---------:|:-------|:--------------------------------------------------------------------------------------------|
| run_split_overlap                     | 0        | True   | each prediction holds out one complete run                                                  |
| features_exclude_forbidden_columns    | 0        | True   | rate-model features exclude run id, event id, A-stack counts, and label columns             |
| shuffled_target_control_worse_than_ml | 0.885458 | True   | ExtraTrees trained on shuffled run-rate targets should not match the nominal held-out model |
| ml_not_suspiciously_perfect           | 0.906665 | True   | a near-zero held-out run-level rate error would imply leakage or a deterministic target     |

The nominal ML rate result is not adopted as a physics improvement unless it beats the traditional method with a CI below zero and the shuffled-target control is worse. Here the useful conclusion is the covariance separation, not an ML win.

## Finding

The run-level A/B coincidence rate is real and strongly run-dependent, but it does not explain the S05 B2-local residual covariance. The covariance reproduction gives B2-containing mean absolute covariance near `1041.84` ns^2 versus downstream-only `15.99` ns^2, while the held-out rate model mainly tracks current/target/topology acceptance. This supports interpreting the S05 excess as detector-local B2/topology covariance rather than a beam-rate common mode.

## Artifacts

`reproduction_match_table.csv`, `s05_covariance_reproduction.csv`, `run_level_rates.csv`, `rate_oof_predictions.csv`, `rate_cv_scan.csv`, `rate_method_metrics.csv`, `rate_method_deltas.csv`, `b_pair_residual_rows.csv.gz`, `pair_covariance_by_run.csv`, `run_covariance_summary.csv`, `rate_covariance_comparison.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05e_1781017418_11875_10723959_run_level_ab_rate_model.py --config configs/s05e_1781017418_11875_10723959_run_level_ab_rate_model.yaml
```

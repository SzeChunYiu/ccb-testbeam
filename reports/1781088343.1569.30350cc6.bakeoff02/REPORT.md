# Study report: BAKEOFF02 - external boosting and compact transformer near-tie audit

- **Study ID:** BAKEOFF02
- **Ticket:** `1781088343.1569.30350cc6`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-07-09
- **Base study:** `reports/0000000002.1.bakeoff01`
- **Raw ROOT directory:** `data/root/root`
- **Git commit at run time:** `45f821246a6d42b7fbbae84a716a32a5a15e5af1`

## 0. Question

BAKEOFF01 found close tree/NN results on some waveform tasks. This audit asks whether two external boosted-tree implementations, XGBoost and LightGBM, or a compact waveform transformer changes any BAKEOFF01 recommendation where the top two bootstrap confidence bands overlap. The audit deliberately does not rerun settled tasks whose leading CI bands do not overlap.

## 1. Raw-ROOT reproduction gate

The raw `HRDv` selection gate was rerun before model fitting using the BAKEOFF01 configuration: subtract the median of samples 0-3 per channel, keep physical B-stave channels B2/B4/B6/B8, and require corrected amplitude greater than 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Near-tie task selection

Task eligibility is defined mechanically: sort BAKEOFF01 rows by the primary held-out metric, then require overlap between the top two 95% bootstrap confidence intervals. This selected timing and anomaly classification. Charge, amplitude, and two-pulse recovery were excluded from new training because their top-two primary CIs did not overlap.

| task      | primary_metric   | direction   | top_model              | second_model   |   top_value |   second_value |   top_ci_low |   top_ci_high |   second_ci_low |   second_ci_high | selected   |
|:----------|:-----------------|:------------|:-----------------------|:---------------|------------:|---------------:|-------------:|--------------:|----------------:|-----------------:|:-----------|
| timing    | sigma68_ns       | lower       | gradient_boosted_trees | extra_trees    |  1.12663    |     1.26276    |   0.834468   |    1.40617    |      0.958592   |       1.46318    | True       |
| anomaly   | roc_auc          | higher      | hist_gradient_boosting | random_forest  |  0.868129   |     0.858243   |   0.860884   |    0.87576    |      0.847755   |       0.868617   | True       |
| two_pulse | time_rms_ns      | lower       | gradient_boosted_trees | ridge          |  6.99597    |     9.48554    |   6.80059    |    7.17913    |      8.79211    |      10.2073     | False      |
| amplitude | res68_abs_frac   | lower       | random_forest          | extra_trees    |  0.00349561 |     0.00511687 |   0.00331238 |    0.00376629 |      0.00461756 |       0.00577515 | False      |
| charge    | res68_abs_frac   | lower       | random_forest          | extra_trees    |  0.00710024 |     0.00892688 |   0.00673984 |    0.00752208 |      0.00878401 |       0.00908285 | False      |

## 3. Methods

### Timing

The timing task uses the identical BAKEOFF01 downstream run split: train runs 58-63 and held-out run 65. The traditional reference is `analytic_timewalk`, the same analytic amplitude/timewalk correction selected in BAKEOFF01. External models predict only the residual left by that baseline:

`hat t_i = t_{analytic,i} - f_theta(x_i)`,

where `x_i` contains the same-pulse normalized 18-sample waveform, log amplitude, peak/area/tail summaries, and stave one-hot indicators. The residual target is the BAKEOFF01 same-particle pair target

`r_i = t'_{i,analytic} - (1/2) sum_{j != i} t'_{j,analytic}`.

XGBoost and LightGBM use shallow histogram-boosted trees. The compact transformer embeds each waveform sample, adds learned positional parameters, applies one one-layer two-head encoder, mean-pools over samples, concatenates the stave one-hot vector, and regresses the analytic residual. Hyperparameters are fixed in the BAKEOFF02 config; model selection is limited to grouped run CV diagnostics, not a broad search.

### Anomaly classification

The anomaly task reuses the BAKEOFF01 two-pulse injection source-run split: train runs 58-61 and held-out runs 63 and 65. Labels are injected-truth overlap indicators, not real pile-up tags. XGBoost/LightGBM use BAKEOFF01 waveform summary features. The compact transformer receives normalized 18-sample waveforms and predicts overlap probability with weighted binary cross-entropy.

For both tasks, confidence intervals bootstrap held-out run blocks or source-run blocks, matching BAKEOFF01's finite-sample convention. No model receives run id, event id, injected delay/scale, other-stave times, or label-defining variables.

## 4. Run-split CV diagnostics

Timing grouped CV:

| model               |   sigma68_ns |
|:--------------------|-------------:|
| lightgbm            |      1.15628 |
| xgboost             |      1.16909 |
| compact_transformer |      1.26119 |

Anomaly grouped CV:

| model               |   roc_auc |
|:--------------------|----------:|
| lightgbm            |  0.83034  |
| xgboost             |  0.830156 |
| compact_transformer |  0.768826 |

## 5. Held-out head-to-head

### Timing external candidates

| model               |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |   cv_sigma68_ns |   train_seconds |   n_parameters |
|:--------------------|-------------:|---------:|----------:|--------------:|-------------------:|----------------:|----------------:|---------------:|
| xgboost             |      1.14605 | 0.936055 |   1.47904 |       1.24329 |                198 |         1.16909 |        0.221751 |             26 |
| compact_transformer |      1.26041 | 1.04069  |   1.62395 |       1.31426 |                198 |         1.26119 |       23.8182   |           2919 |
| lightgbm            |      1.28044 | 0.971986 |   1.43201 |       1.23354 |                198 |         1.15628 |        0.340177 |             26 |
| analytic_timewalk   |      1.49464 | 1.32816  |   1.67075 |       1.69913 |                198 |       nan       |      nan        |            nan |

### Timing combined BAKEOFF01 + BAKEOFF02

| source    | model                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |
|:----------|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------:|
| BAKEOFF01 | gradient_boosted_trees |      1.12663 | 0.834468 |   1.40617 |       1.19963 |                198 |
| BAKEOFF02 | xgboost                |      1.14605 | 0.936055 |   1.47904 |       1.24329 |                198 |
| BAKEOFF02 | compact_transformer    |      1.26041 | 1.04069  |   1.62395 |       1.31426 |                198 |
| BAKEOFF01 | extra_trees            |      1.26276 | 0.958592 |   1.46318 |       1.2444  |                198 |
| BAKEOFF01 | mlp                    |      1.26699 | 1.10125  |   1.56279 |       1.3247  |                198 |
| BAKEOFF02 | lightgbm               |      1.28044 | 0.971986 |   1.43201 |       1.23354 |                198 |
| BAKEOFF01 | gru                    |      1.31381 | 1.05603  |   1.5677  |       1.36573 |                198 |
| BAKEOFF01 | attention              |      1.35081 | 1.06215  |   1.6217  |       1.39685 |                198 |
| BAKEOFF01 | resnet                 |      1.35966 | 1.08504  |   1.63467 |       1.3825  |                198 |
| BAKEOFF01 | cnn                    |      1.35966 | 1.06725  |   1.62386 |       1.39834 |                198 |
| BAKEOFF01 | tcn                    |      1.36021 | 1.06517  |   1.62063 |       1.39764 |                198 |
| BAKEOFF01 | ridge                  |      1.44284 | 1.18886  |   1.6448  |       1.41159 |                198 |
| BAKEOFF01 | analytic_timewalk      |      1.49464 | 1.29766  |   1.67284 |       1.69913 |                198 |
| BAKEOFF02 | analytic_timewalk      |      1.49464 | 1.32816  |   1.67075 |       1.69913 |                198 |
| BAKEOFF01 | s02_ridge_cfd20        |      1.77781 | 1.46176  |   2.06093 |       1.71577 |                198 |
| BAKEOFF01 | template_phase         |      2.88915 | 2.63915  |   3.27718 |       2.57669 |                198 |
| BAKEOFF01 | cfd20                  |      2.99339 | 2.70997  |   3.41139 |       2.74268 |                198 |

Timing winner by point estimate remains `gradient_boosted_trees` from `BAKEOFF01` with sigma68 `1.1266` ns and CI `[0.8345, 1.4062]`.

### Anomaly external candidates

| model               |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |    brier |   cv_roc_auc |   train_seconds |   n_parameters |
|:--------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|---------:|-------------:|----------------:|---------------:|
| lightgbm            |  0.845658 |         0.814331 |          0.87585  |            0.853212 |                   0.821585 |                    0.885663 | 0.160075 |     0.83034  |        0.192714 |             25 |
| xgboost             |  0.843328 |         0.819977 |          0.866621 |            0.845937 |                   0.824706 |                    0.869185 | 0.160565 |     0.830156 |        0.132945 |             25 |
| compact_transformer |  0.798997 |         0.751701 |          0.847596 |            0.793365 |                   0.753995 |                    0.843377 | 0.18659  |     0.768826 |        3.50173  |           2865 |

### Anomaly combined BAKEOFF01 + BAKEOFF02

| source    | model                  |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |    brier |
|:----------|:-----------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|---------:|
| BAKEOFF01 | hist_gradient_boosting |  0.868129 |         0.860884 |          0.87576  |            0.876477 |                   0.871844 |                    0.881875 | 0.156534 |
| BAKEOFF01 | random_forest          |  0.858243 |         0.847755 |          0.868617 |            0.872059 |                   0.860836 |                    0.883056 | 0.154411 |
| BAKEOFF02 | lightgbm               |  0.845658 |         0.814331 |          0.87585  |            0.853212 |                   0.821585 |                    0.885663 | 0.160075 |
| BAKEOFF02 | xgboost                |  0.843328 |         0.819977 |          0.866621 |            0.845937 |                   0.824706 |                    0.869185 | 0.160565 |
| BAKEOFF01 | logistic               |  0.839076 |         0.833968 |          0.842766 |            0.839057 |                   0.839057 |                    0.842397 | 0.163839 |
| BAKEOFF01 | mlp                    |  0.804065 |         0.79873  |          0.807982 |            0.806299 |                   0.797299 |                    0.817891 | 0.193815 |
| BAKEOFF02 | compact_transformer    |  0.798997 |         0.751701 |          0.847596 |            0.793365 |                   0.753995 |                    0.843377 | 0.18659  |

Anomaly winner by point estimate is `hist_gradient_boosting` from `BAKEOFF01` with ROC AUC `0.8681` and CI `[0.8609, 0.8758]`.

## 6. Leakage controls

| check                            |   value | pass   | detail                                                                                                 |
|:---------------------------------|--------:|:-------|:-------------------------------------------------------------------------------------------------------|
| timing_train_heldout_run_overlap |       0 | True   | nan                                                                                                    |
| timing_feature_audit             |       0 | True   | same-pulse waveform, amplitude summaries, and stave one-hot only; no run id/event id/other-stave times |
| timing_target_base               |       0 | True   | external models correct residuals left by BAKEOFF01 analytic_timewalk                                  |

| check                             |   value | pass   | detail                                                                                                          |
|:----------------------------------|--------:|:-------|:----------------------------------------------------------------------------------------------------------------|
| anomaly_train_heldout_run_overlap |     0   | True   | nan                                                                                                             |
| anomaly_feature_audit             |     0   | True   | features are normalized waveform shape summaries or normalized samples; no injected delay/scale/run id/event id |
| anomaly_heldout_truth_balance     |     0.5 | True   | nan                                                                                                             |

## 7. Systematics and caveats

- Timing labels remain same-particle residual proxies, not external truth. Improvements can reflect better residual equalization rather than absolute time accuracy.
- The anomaly task is injected-truth closure. It is informative for waveform overlap separability but not a direct measurement of real high-current pile-up prevalence.
- The compact transformer is intentionally small and laptop-safe. A null result does not rule out larger sequence models, but it does test the architecture class at the complexity scale BAKEOFF01 considered practical.
- XGBoost and LightGBM are external dependencies available in this worker environment; the config and manifest pin the actual package versions used at runtime.
- BAKEOFF02 performs a targeted near-tie audit, not a new global bakeoff. Non-overlap tasks are carried forward from BAKEOFF01 without retraining.

## 8. Verdict

On BAKEOFF01 near-tie timing, the combined point-estimate winner is gradient_boosted_trees from BAKEOFF01 at sigma68 1.127 ns; the best BAKEOFF02 external candidate is xgboost at 1.146 ns. On injected-truth anomaly classification, the combined point-estimate winner is hist_gradient_boosting from BAKEOFF01 at ROC AUC 0.868; the best BAKEOFF02 external candidate is lightgbm at 0.846. Therefore the BAKEOFF01 recommendation table is stable under this XGBoost/LightGBM/compact-transformer audit.

## 9. Reproducibility

```bash
.venv/bin/python scripts/bakeoff02_1781088343_1569_30350cc6_external_boost_transformer.py --config configs/bakeoff02_1781088343_1569_30350cc6_external_boost_transformer.yaml
```

Runtime in this execution was `108.08` s. Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `near_tie_task_selection.csv`, `timing_external_head_to_head.csv`, `timing_combined_head_to_head.csv`, `anomaly_external_head_to_head.csv`, and `anomaly_combined_head_to_head.csv`.

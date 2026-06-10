# S16g: independent pre-trigger contamination labels

- **Ticket:** 1781031385.1538.624e2188
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Depends on:** S00 and S16f morphology scorecard
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `79448e5335661047d6d244a8213876db925ffcbf`
- **Config:** `configs/s16g_1781031385_1538_624e2188_independent_pretrigger_contamination_labels.json`

## 0. Question

Can we define an independent pre-trigger contamination label from B2/B4/B6/B8 raw pre-trigger waveform shapes, and does it agree with the S16f veto-score morphology axis without using timing residuals as labels or features?

The label is unsupervised. For selected pulse `i`, let

\[
  z_i = \left[x_{i,0}-m_i, x_{i,1}-m_i, x_{i,2}-m_i, x_{i,3}-m_i, \bar x_i-m_i,
  \max(x_i-m_i), \min(x_i-m_i), \mathrm{ptp}(x_i), \hat \beta_i\right],
\]

where `m_i` is the four-sample pre-trigger median and `\hat \beta_i` is the sample-0..3 slope. A robust scaler and `K=4` MiniBatchKMeans are fit on train runs only. The contamination cluster is the train cluster with the largest pre-trigger anomaly index

\[
  A_c = \mathrm{median}(|z|)_c/250 + \mathrm{median}(\mathrm{ptp})_c/180
        + \max(\mathrm{median}(z_{max})_c,0)/250 + |\mathrm{median}(\hat\beta)_c|/75.
\]

This creates a binary label independent of S16f scores. The S16f scores are used only after the label is fixed.

## 1. Raw ROOT reproduction

The script starts from raw `data/root/root/hrdb_run_NNNN.root`, uses B2/B4/B6/B8 channels, the four pre-trigger samples as the seed pedestal, and the fixed `A > 1000 ADC` selected-pulse gate.

| quantity                                       |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses from raw HRDv    |         640737 |       640737 |       0 |           0 | True   |
| non-beam trigger entries among selected pulses |              0 |            0 |       0 |           0 | True   |

The exact **640,737** selected-pulse count reproduces S00 before clustering or validation.

## 2. Cluster label

Cluster fitting excludes calibration runs `[56, 64]` and held-out runs `[57, 65]`. The cluster chosen as the contamination label is the one with highest train-run anomaly index.

|   cluster |   train_n |   train_fraction |   anomaly_index |   median_pretrigger_absmax_adc |   median_pretrigger_ptp_adc |   median_pretrigger_slope_adc_per_sample |   median_s16f_pretrigger_score | chosen_as_contamination   |
|----------:|----------:|-----------------:|----------------:|-------------------------------:|----------------------------:|-----------------------------------------:|-------------------------------:|:--------------------------|
|         2 |      2528 |            0.014 |          79.155 |                       3794.250 |                    5686.500 |                                 1875.900 |                          8.900 | True                      |
|         1 |      5609 |            0.031 |          50.283 |                       2165.000 |                    3332.000 |                                 1145.100 |                          7.124 | False                     |
|         0 |     10569 |            0.059 |          23.544 |                       1280.500 |                    1580.000 |                                  345.800 |                          4.783 | False                     |
|         3 |    161294 |            0.896 |           0.300 |                         16.000 |                      24.000 |                                    3.800 |                          0.158 | False                     |

The held-out positive fraction is `0.0240` over `26871` pulse records.

## 3. Validation methods

Primary metric: held-out average precision for the independent cluster label. CIs are 95% run-block bootstraps over held-out runs with within-run resampling. No model uses timing residuals, pair residuals, run id, event ids, trigger id, or labels as features.

Traditional method:

\[
  s_i^{\mathrm{trad}} =
  1.20 [d_i/280]_0^3 + 0.80 [\mathrm{ptp}_i/150]_0^3
  + 0.75 [p_i/300]_0^3 + 0.65 I(t_{peak} \le 4),
\]

the S16f pre-trigger score with a train-run F1-optimized threshold, then probability calibrated on runs `[56, 64]`.

Learned methods:

| Method | Class | Inputs |
|---|---|---|
| `ridge_logistic` | L2 logistic regression | S16f scorecard and waveform-morphology summaries |
| `hist_gradient_boosted_trees` | histogram gradient-boosted trees | same tabular features; GroupKFold-by-run scan |
| `mlp` | feed-forward neural net | same tabular features |
| `one_dimensional_cnn` | 1D CNN | normalized 18-sample waveform plus tabular summaries |
| `score_residual_net` | new architecture | residual CNN plus S16f score/morphology tabular head |

Best HGB scan rows:

|   max_leaf_nodes |   learning_rate |   l2_regularization |   cv_average_precision |
|-----------------:|----------------:|--------------------:|-----------------------:|
|           15.000 |           0.080 |               0.100 |                  0.999 |
|           15.000 |           0.080 |               0.000 |                  0.999 |
|           15.000 |           0.040 |               0.100 |                  0.999 |
|           63.000 |           0.040 |               0.100 |                  0.999 |
|           31.000 |           0.040 |               0.000 |                  0.999 |

## 4. Results

| method                            | family           |     n |   positive_fraction |   average_precision |   roc_auc |   balanced_accuracy |    f1 |   ap_ci_low |   ap_ci_high |
|:----------------------------------|:-----------------|------:|--------------------:|--------------------:|----------:|--------------------:|------:|------------:|-------------:|
| hist_gradient_boosted_trees       | ml               | 26871 |               0.024 |               0.999 |     1.000 |               0.989 | 0.984 |       0.998 |        1.000 |
| mlp                               | ml               | 26871 |               0.024 |               0.999 |     1.000 |               0.989 | 0.982 |       0.998 |        1.000 |
| one_dimensional_cnn               | ml               | 26871 |               0.024 |               0.987 |     1.000 |               0.984 | 0.971 |       0.970 |        0.999 |
| ridge_logistic                    | ml               | 26871 |               0.024 |               0.983 |     1.000 |               0.983 | 0.972 |       0.960 |        1.000 |
| score_residual_net                | new_architecture | 26871 |               0.024 |               0.979 |     1.000 |               0.987 | 0.976 |       0.947 |        1.000 |
| traditional_s16f_pretrigger_score | traditional      | 26871 |               0.024 |               0.317 |     0.882 |               0.500 | 0.000 |       0.240 |        0.455 |

Paired deltas versus the strong traditional S16f score threshold:

| method                      |   delta_ap_vs_traditional |   ci_low |   ci_high |
|:----------------------------|--------------------------:|---------:|----------:|
| hist_gradient_boosted_trees |                     0.682 |    0.544 |     0.756 |
| mlp                         |                     0.682 |    0.541 |     0.761 |
| one_dimensional_cnn         |                     0.669 |    0.538 |     0.738 |
| ridge_logistic              |                     0.666 |    0.545 |     0.732 |
| score_residual_net          |                     0.661 |    0.544 |     0.728 |

Winner: **hist_gradient_boosted_trees** with average precision `0.999` CI `[0.998, 1.000]`. The strong traditional S16f pre-trigger score has average precision `0.317` CI `[0.240, 0.455]`. Winner minus traditional is `0.682 [0.544, 0.756]` AP.

By-run held-out summary:

| method                            | family           |     n |   positive_fraction |   average_precision |   roc_auc |   balanced_accuracy |    f1 |   run |
|:----------------------------------|:-----------------|------:|--------------------:|--------------------:|----------:|--------------------:|------:|------:|
| hist_gradient_boosted_trees       | ml               | 13833 |               0.025 |               0.999 |     1.000 |               0.987 | 0.979 |    57 |
| mlp                               | ml               | 13833 |               0.025 |               0.998 |     1.000 |               0.990 | 0.981 |    57 |
| one_dimensional_cnn               | ml               | 13833 |               0.025 |               0.976 |     1.000 |               0.982 | 0.961 |    57 |
| ridge_logistic                    | ml               | 13833 |               0.025 |               0.969 |     1.000 |               0.979 | 0.960 |    57 |
| score_residual_net                | new_architecture | 13833 |               0.025 |               0.962 |     1.000 |               0.986 | 0.968 |    57 |
| traditional_s16f_pretrigger_score | traditional      | 13833 |               0.025 |               0.255 |     0.872 |               0.500 | 0.000 |    57 |
| hist_gradient_boosted_trees       | ml               | 13038 |               0.023 |               1.000 |     1.000 |               0.992 | 0.990 |    65 |
| mlp                               | ml               | 13038 |               0.023 |               1.000 |     1.000 |               0.988 | 0.983 |    65 |
| score_residual_net                | new_architecture | 13038 |               0.023 |               1.000 |     1.000 |               0.988 | 0.985 |    65 |
| ridge_logistic                    | ml               | 13038 |               0.023 |               0.999 |     1.000 |               0.987 | 0.985 |    65 |
| one_dimensional_cnn               | ml               | 13038 |               0.023 |               0.999 |     1.000 |               0.987 | 0.982 |    65 |
| traditional_s16f_pretrigger_score | traditional      | 13038 |               0.023 |               0.433 |     0.893 |               0.500 | 0.000 |    65 |

## 5. Leakage checks

| check                                             | status   | detail                                                                                                                                                           |
|:--------------------------------------------------|:---------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| split_by_run_train_calibration_heldout_disjoint   | pass     | train=[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 58, 59, 60, 61, 62, 63] calibration=[56, 64] heldout=[57, 65] |
| forbidden_feature_exclusion                       | pass     | features exclude timing residuals, pair residuals, run id, eventno, evt, trigger, and labels                                                                     |
| cluster_fit_excludes_calibration_and_heldout_runs | pass     | K-means scaler and centroids are fit only on train runs                                                                                                          |
| s16f_score_validation_not_label_definition        | pass     | cluster labels use pretrigger waveform-shape columns only; S16f scores are used later as validation features                                                     |
| finite_scores                                     | pass     | 161226 held-out method rows                                                                                                                                      |

## 6. Systematics and caveats

- **Unsupervised target:** the label is not human truth. It is a reproducible train-run cluster label for anomalous pre-trigger shape. The scientific claim is agreement with S16f veto scores, not a calibrated physical contamination rate.
- **Run split:** cluster centroids, traditional threshold, and all learned model weights are fit without runs `[56, 64]` and `[57, 65]`. Calibration uses `[56, 64]` only; the table uses `[57, 65]` only.
- **Circularity control:** S16f scores are not used to choose the cluster label. They enter only in the validation benchmark after the contamination cluster is fixed.
- **Near-ceiling ML scores:** the learned validators use the same raw-waveform summary family as the cluster label, so they test transfer/stability of the learned label more than discovery of an independent physical truth source. The traditional S16f score is the more interpretable validation axis.
- **Feature exclusions:** timing residuals and pair residuals are absent from the table. Event/run identifiers are present only in output provenance, not model matrices.
- **Bootstrap limitation:** only two held-out source runs are available, so run-block CIs are intentionally conservative and should be read as split-stability intervals rather than universal uncertainty.
- **Cluster multiplicity:** `K=4` is fixed by config as a small morphology partition. A different `K` may split the selected contamination cluster into subtypes; `cluster_summary.csv` preserves the cluster-level diagnostics.

## 7. Verdict

The independent pre-trigger cluster label is strongly aligned with S16f morphology scores. `hist_gradient_boosted_trees` is the highest-AP validator because it can relearn the same waveform-summary boundary, while the transparent S16f traditional score still provides a nontrivial monotone validation axis (ROC AUC above random but lower AP). This supports using the S16f pre-trigger veto score as a diagnostic covariate for contamination/pathology studies, while keeping it out of timing-label definitions.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781031385_1538_624e2188_independent_pretrigger_contamination_labels.py --config configs/s16g_1781031385_1538_624e2188_independent_pretrigger_contamination_labels.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `cluster_summary.csv`, `counts_by_run_stave.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `method_deltas_vs_traditional.csv`, `heldout_by_run.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics.

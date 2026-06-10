# P09e: broad-mismatch low-positive audit

**Ticket:** `1781032068.1446.13fd5bb1`

## Abstract
P09c reported a suspiciously high recover/veto average precision for `novel_broad_template_mismatch`, but the decisive charge-outlier support came from a single held-out positive. This study re-runs the raw ROOT reproduction gate, recreates the P09c low-positive count, expands held-out coverage to eleven runs, and benchmarks a strong traditional score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a gated hybrid CNN+tabular architecture.

## Raw reproduction
The ROOT inputs were read from `data/root/root`. The S00/P09a selection is even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC. This scan is executed before taxonomy, propagation labels, or model fitting.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

## Label definitions
Let \(x_i(t)\) be the 18-sample peak-normalized waveform for pulse \(i\). P09a broad candidates are the union of width-broad pulses and q-template-only pulses, where the thresholds are fitted only on non-held-out runs. Propagation sentinels are robust z scores fitted on the same train runs:

\[ z_f(i) = \frac{f_i - \operatorname{median}_{j \in T} f_j}{1.4826\operatorname{MAD}_{j \in T}(f_j)}. \]

The primary endpoint is `broad_veto_like`: a broad candidate with at least one charge, baseline, pile-up, timing-tail, dropout, or saturation sentinel. The specific low-positive endpoint is `broad_charge_outlier`: a broad candidate with charge-area robust z above the train q99.5 threshold.

## P09c low-positive reproduction
| scope                    | heldout_runs   |   broad_candidates |   broad_veto_like |   broad_charge_outlier |
|:-------------------------|:---------------|-------------------:|------------------:|-----------------------:|
| p09c_reference_four_runs | 42,57,64,65    |                170 |                 5 |                      1 |

## Expanded held-out support
The expanded split holds out runs `37, 40, 42, 49, 52, 57, 58, 60, 62, 64, 65` and trains thresholds/models on all other configured B-stack runs.

|   run |   heldout_rows |   broad_candidates |   broad_veto_like |   broad_charge_outlier |   p09a_taxon_broad |
|------:|---------------:|-------------------:|------------------:|-----------------------:|-------------------:|
|    37 |          24537 |                 94 |                 2 |                      0 |                 83 |
|    40 |          14708 |                 46 |                 0 |                      0 |                 43 |
|    42 |          18112 |                 43 |                 3 |                      1 |                 37 |
|    49 |          14815 |                 54 |                 1 |                      1 |                 52 |
|    52 |           7152 |                 30 |                 0 |                      0 |                 28 |
|    57 |          13833 |                 44 |                 1 |                      0 |                 43 |
|    58 |          16781 |                 37 |                 0 |                      0 |                 35 |
|    60 |          17029 |                 25 |                 2 |                      0 |                 20 |
|    62 |          19089 |                 50 |                 0 |                      0 |                 46 |
|    64 |          14630 |                 53 |                 0 |                      0 |                 53 |
|    65 |          13038 |                 30 |                 1 |                      0 |                 29 |

## Benchmark methods
All models exclude run, event, stave, and source-index identifiers. Ridge and gradient-boosted trees use standardized scalar pulse-shape features. The MLP uses the same scalar features. The 1D-CNN uses only the normalized waveform. The new architecture is a gated hybrid: a waveform convolutional branch is multiplicatively gated by a scalar-feature branch before the final classifier. The traditional comparator is a frozen robust score combining q-template/width evidence with charge, baseline, pile-up, and duplicate timing sentinels.

For held-out predictions \(s_i\), the primary ranking metric is average precision, with ROC-AUC, balanced accuracy at the median score, and top-1% recall/precision reported as diagnostics. CIs are bootstrap intervals over held-out runs, not row bootstraps.

## Held-out benchmark
| method                        | target          |   n_eval |   n_positive |   average_precision |   roc_auc |   balanced_accuracy |   recall_at_1pct |   precision_at_1pct | average_precision_ci   | roc_auc_ci     | balanced_accuracy_ci   | recall_at_1pct_ci   | precision_at_1pct_ci   |
|:------------------------------|:----------------|---------:|-------------:|--------------------:|----------:|--------------------:|-----------------:|--------------------:|:-----------------------|:---------------|:-----------------------|:--------------------|:-----------------------|
| traditional_robust_broad_veto | broad_veto_like |     2024 |           10 |            0.990909 |  0.99995  |            0.751241 |              1   |           0.47619   | [0.978, 1]             | [1, 1]         | [0.75, 0.752]          | [1, 1]              | [0.2, 0.8]             |
| ridge_scalar                  | broad_veto_like |     2024 |           10 |            0.990909 |  0.99995  |            0.751241 |              1   |           0.47619   | [0.977, 1]             | [1, 1]         | [0.75, 0.752]          | [1, 1]              | [0.211, 0.778]         |
| gradient_boosted_trees        | broad_veto_like |     2024 |           10 |            0.93152  |  0.999454 |            0.715492 |              1   |           0.47619   | [0.892, 1]             | [0.999, 1]     | [0.707, 0.751]         | [0.833, 1]          | [0.222, 0.75]          |
| mlp_scalar_nn                 | broad_veto_like |     2024 |           10 |            0.412502 |  0.994538 |            0.751241 |              0.6 |           0.285714  | [0.231, 0.666]         | [0.992, 0.997] | [0.75, 0.752]          | [0.312, 1]          | [0.136, 0.444]         |
| cnn1d_waveform_nn             | broad_veto_like |     2024 |           10 |            0.217566 |  0.816832 |            0.751241 |              0.2 |           0.0952381 | [0.0132, 0.504]        | [0.653, 0.951] | [0.597, 0.752]         | [0, 0.5]            | [0, 0.227]             |
| hybrid_gated_cnn_tabular      | broad_veto_like |     2024 |           10 |            0.704078 |  0.998461 |            0.751241 |              1   |           0.47619   | [0.404, 1]             | [0.996, 1]     | [0.75, 0.752]          | [0.727, 1]          | [0.2, 0.714]           |

## Per-run diagnostics
|   run | method                        |   n_eval |   n_positive |   average_precision |    roc_auc |   balanced_accuracy |   recall_at_1pct |   precision_at_1pct |
|------:|:------------------------------|---------:|-------------:|--------------------:|-----------:|--------------------:|-----------------:|--------------------:|
|    37 | traditional_robust_broad_veto |      306 |            2 |           1         |   1        |            0.751645 |         1        |            0.5      |
|    37 | ridge_scalar                  |      306 |            2 |           1         |   1        |            0.751645 |         1        |            0.5      |
|    37 | gradient_boosted_trees        |      306 |            2 |           1         |   1        |            0.713816 |         1        |            0.5      |
|    37 | mlp_scalar_nn                 |      306 |            2 |           0.325     |   0.990132 |            0.751645 |         0.5      |            0.25     |
|    37 | cnn1d_waveform_nn             |      306 |            2 |           0.0972222 |   0.955592 |            0.751645 |         0        |            0        |
|    37 | hybrid_gated_cnn_tabular      |      306 |            2 |           0.333333  |   0.990132 |            0.751645 |         0.5      |            0.25     |
|    40 | traditional_robust_broad_veto |      176 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    40 | ridge_scalar                  |      176 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    40 | gradient_boosted_trees        |      176 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    40 | mlp_scalar_nn                 |      176 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    40 | cnn1d_waveform_nn             |      176 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    40 | hybrid_gated_cnn_tabular      |      176 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    42 | traditional_robust_broad_veto |      209 |            3 |           1         |   1        |            0.752427 |         1        |            1        |
|    42 | ridge_scalar                  |      209 |            3 |           1         |   1        |            0.752427 |         1        |            1        |
|    42 | gradient_boosted_trees        |      209 |            3 |           1         |   1        |            0.713592 |         1        |            1        |
|    42 | mlp_scalar_nn                 |      209 |            3 |           0.7       |   0.993528 |            0.752427 |         0.333333 |            0.333333 |
|    42 | cnn1d_waveform_nn             |      209 |            3 |           0.37381   |   0.875405 |            0.752427 |         0.333333 |            0.333333 |
|    42 | hybrid_gated_cnn_tabular      |      209 |            3 |           1         |   1        |            0.752427 |         1        |            1        |
|    49 | traditional_robust_broad_veto |      194 |            1 |           1         |   1        |            0.751295 |         1        |            0.5      |
|    49 | ridge_scalar                  |      194 |            1 |           1         |   1        |            0.751295 |         1        |            0.5      |
|    49 | gradient_boosted_trees        |      194 |            1 |           1         |   1        |            0.696891 |         1        |            0.5      |
|    49 | mlp_scalar_nn                 |      194 |            1 |           1         |   1        |            0.751295 |         1        |            0.5      |
|    49 | cnn1d_waveform_nn             |      194 |            1 |           1         |   1        |            0.751295 |         1        |            0.5      |
|    49 | hybrid_gated_cnn_tabular      |      194 |            1 |           1         |   1        |            0.751295 |         1        |            0.5      |
|    52 | traditional_robust_broad_veto |      100 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    52 | ridge_scalar                  |      100 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    52 | gradient_boosted_trees        |      100 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    52 | mlp_scalar_nn                 |      100 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    52 | cnn1d_waveform_nn             |      100 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    52 | hybrid_gated_cnn_tabular      |      100 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    57 | traditional_robust_broad_veto |      163 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    57 | ridge_scalar                  |      163 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    57 | gradient_boosted_trees        |      163 |            1 |           1         |   1        |            0.746914 |         1        |            0.5      |
|    57 | mlp_scalar_nn                 |      163 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    57 | cnn1d_waveform_nn             |      163 |            1 |           0.0217391 |   0.722222 |            0.75     |         0        |            0        |
|    57 | hybrid_gated_cnn_tabular      |      163 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    58 | traditional_robust_broad_veto |      198 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    58 | ridge_scalar                  |      198 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    58 | gradient_boosted_trees        |      198 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    58 | mlp_scalar_nn                 |      198 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    58 | cnn1d_waveform_nn             |      198 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    58 | hybrid_gated_cnn_tabular      |      198 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    60 | traditional_robust_broad_veto |      161 |            2 |           1         |   1        |            0.751572 |         1        |            1        |
|    60 | ridge_scalar                  |      161 |            2 |           1         |   1        |            0.751572 |         1        |            1        |
|    60 | gradient_boosted_trees        |      161 |            2 |           1         |   1        |            0.732704 |         1        |            1        |
|    60 | mlp_scalar_nn                 |      161 |            2 |           0.5       |   0.990566 |            0.751572 |         0.5      |            0.5      |
|    60 | cnn1d_waveform_nn             |      161 |            2 |           0.0145762 |   0.380503 |            0.498428 |         0        |            0        |
|    60 | hybrid_gated_cnn_tabular      |      161 |            2 |           1         |   1        |            0.751572 |         1        |            1        |
|    62 | traditional_robust_broad_veto |      215 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    62 | ridge_scalar                  |      215 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    62 | gradient_boosted_trees        |      215 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    62 | mlp_scalar_nn                 |      215 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    62 | cnn1d_waveform_nn             |      215 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    62 | hybrid_gated_cnn_tabular      |      215 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    64 | traditional_robust_broad_veto |      171 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    64 | ridge_scalar                  |      171 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    64 | gradient_boosted_trees        |      171 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    64 | mlp_scalar_nn                 |      171 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    64 | cnn1d_waveform_nn             |      171 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    64 | hybrid_gated_cnn_tabular      |      171 |            0 |         nan         | nan        |          nan        |       nan        |          nan        |
|    65 | traditional_robust_broad_veto |      131 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    65 | ridge_scalar                  |      131 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    65 | gradient_boosted_trees        |      131 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |
|    65 | mlp_scalar_nn                 |      131 |            1 |           0.5       |   0.992308 |            0.75     |         1        |            0.5      |
|    65 | cnn1d_waveform_nn             |      131 |            1 |           0.166667  |   0.961538 |            0.75     |         0        |            0        |
|    65 | hybrid_gated_cnn_tabular      |      131 |            1 |           1         |   1        |            0.75     |         1        |            0.5      |

## Leakage and systematics checks
| check                                 |   value | pass   | note                                                                                  |
|:--------------------------------------|--------:|:-------|:--------------------------------------------------------------------------------------|
| raw_reproduction_before_models        |  640737 | True   | script raises before taxonomy/model work if this fails                                |
| train_heldout_run_overlap             |       0 | True   | all templates, thresholds, scalers, and models fit on non-held-out runs               |
| identifier_features_used              |       0 | True   | run, event, eventno, evt, stave, and source index are excluded from model matrices    |
| eval_waveform_hash_seen_in_train_rate |       0 | True   | rounded normalized waveform hashes at 1e-3 precision                                  |
| p09c_charge_outlier_positive_count    |       1 | True   | documents the original low-positive bottleneck rather than treating high AP as robust |
| expanded_charge_outlier_runs          |       2 | True   | number of expanded held-out runs with at least one broad charge-outlier positive      |

## Result
The winner by primary average precision is `traditional_robust_broad_veto` with AP 0.9909 (95% run-bootstrap CI [0.978, 1]). The expanded charge-outlier count determines whether the P09c single-row support was a low-count artifact; the table above reports both the original four-run count and the expanded eleven-run count.

## Caveats
The propagation endpoints are deterministic audit labels, not new hand-scanned physics truth. Since charge, width, and timing quantities participate in both the labels and some tabular features, high tabular AP should be read as closure of the operational veto definition rather than proof of a new waveform class. The CNN-only comparator is a useful non-tabular stress test: if it wins, waveform morphology alone carries the endpoint; if it loses, the endpoint is mostly scalar-quality information. Bootstrap intervals cover run-to-run composition but not threshold-definition uncertainty outside the selected runs.

## Provenance
Runtime was 51.0 s on `billy` with Python `3.7.6`. Torch device for neural models was `cpu`. `manifest.json` records command, input, code, and output hashes.

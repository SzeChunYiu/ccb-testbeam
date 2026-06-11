# P09i: broad-width reviewer-disagreement propagation

**Ticket:** `1781058292.535.650c13f1`

## Abstract
This study asks whether P09 broad-width anomaly cases, especially cases where the P09b/P09c fixed review rubrics disagree, propagate into timing, charge, pile-up, or baseline-lowering sentinels. The analysis re-runs the raw ROOT reproduction gate, freezes all thresholds on non-held-out runs, treats reviewer disagreement as a nuisance stratum rather than a truth label, and benchmarks a strong traditional broad-veto score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a gated CNN+tabular architecture.

## Raw reproduction
The ROOT inputs were read from `data/root/root`. The S00/P09a selection is even B2/B4/B6/B8 channels, baseline median samples 0-3, and amplitude >1000 ADC. This scan is executed before taxonomy, propagation labels, or model fitting.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | True |

## Label definitions
Let \(x_i(t)\), \(t=0,\ldots,17\), be the peak-normalized waveform for pulse \(i\). P09a templates, broad-width thresholds, and propagation thresholds are fitted only on the training-run set \(T\). Robust sentinel coordinates use

\[ z_f(i) = \frac{f_i - \operatorname{median}_{j \in T} f_j}{1.4826\operatorname{MAD}_{j \in T}(f_j)}. \]

The primary endpoint is `broad_downstream_risk`: a broad-width source pulse with at least one of timing-tail, charge-residual, pile-up-like, or baseline-lowering sentinels above train-run quantile thresholds. Reviewer disagreement is measured from the P09b dual fixed rubrics, the P09c external dual rubrics, and their consensus-label mismatch; it is never used as the target label.

## P09c low-positive reproduction
| scope                    | heldout_runs   |   broad_candidates |   broad_veto_like |   broad_charge_outlier |   broad_downstream_risk |
|:-------------------------|:---------------|-------------------:|------------------:|-----------------------:|------------------------:|
| p09c_reference_four_runs | 42,57,64,65    |                170 |                 5 |                      1 |                       4 |

## Expanded held-out support
The expanded split holds out runs `37, 40, 42, 49, 52, 57, 58, 60, 62, 64, 65` and trains thresholds/models on all other configured B-stack runs.

|   run |   heldout_rows |   broad_candidates |   broad_veto_like |   broad_charge_outlier |   broad_downstream_risk |   baseline_lowering |   p09a_taxon_broad |
|------:|---------------:|-------------------:|------------------:|-----------------------:|------------------------:|--------------------:|-------------------:|
|    37 |          24537 |                 94 |                 3 |                      0 |                       0 |                 338 |                 83 |
|    40 |          14708 |                 46 |                 0 |                      0 |                       0 |                 227 |                 43 |
|    42 |          18112 |                 43 |                 3 |                      1 |                       2 |                 214 |                 37 |
|    49 |          14815 |                 54 |                 1 |                      1 |                       0 |                 217 |                 52 |
|    52 |           7152 |                 30 |                 0 |                      0 |                       0 |                  35 |                 28 |
|    57 |          13833 |                 44 |                 1 |                      0 |                       1 |                 203 |                 43 |
|    58 |          16781 |                 37 |                 0 |                      0 |                       0 |                  21 |                 35 |
|    60 |          17029 |                 25 |                 2 |                      0 |                       2 |                  52 |                 20 |
|    62 |          19089 |                 50 |                 0 |                      0 |                       0 |                  35 |                 46 |
|    64 |          14630 |                 53 |                 0 |                      0 |                       0 |                  17 |                 53 |
|    65 |          13038 |                 30 |                 1 |                      0 |                       1 |                  22 |                 29 |

## Benchmark methods
All models exclude run, event, stave, source-index, and reviewer-label identifiers. Ridge and gradient-boosted trees use standardized scalar pulse-shape features. The MLP uses the same scalar features. The 1D-CNN uses only \(x_i(t)\). The new architecture is a gated hybrid: a waveform convolutional branch is multiplicatively gated by a scalar-feature branch before the final classifier. The traditional comparator is a frozen robust score combining q-template/width evidence with charge, baseline, pile-up, and duplicate timing sentinels.

For held-out predictions \(s_i\), the ranking target is downstream risk. Average precision is the model-selection metric, with ROC-AUC, balanced accuracy at the median score, and top-1% recall/precision as diagnostics. Separately, fixed-coverage selections take the top `8` pulses per held-out run/stave and report the propagation metrics requested in the ticket. CIs are bootstrap intervals over held-out runs, not row bootstraps.

## Held-out ranking benchmark
| method                        | target                |   n_eval |   n_positive |   average_precision |   roc_auc |   balanced_accuracy |   recall_at_1pct |   precision_at_1pct | average_precision_ci   | roc_auc_ci   | balanced_accuracy_ci   | recall_at_1pct_ci   | precision_at_1pct_ci   |
|:------------------------------|:----------------------|---------:|-------------:|--------------------:|----------:|--------------------:|-----------------:|--------------------:|:-----------------------|:-------------|:-----------------------|:--------------------|:-----------------------|
| traditional_robust_broad_veto | broad_downstream_risk |     2024 |            6 |            0.594048 |  0.999009 |            0.750743 |                1 |            0.285714 | [0.252, 1]             | [0.997, 1]   | [0.75, 0.751]          | [1, 1]              | [0.0833, 0.55]         |
| ridge_scalar                  | broad_downstream_risk |     2024 |            6 |            1        |  1        |            0.750743 |                1 |            0.285714 | [1, 1]                 | [1, 1]       | [0.75, 0.751]          | [1, 1]              | [0.0565, 0.571]        |
| gradient_boosted_trees        | broad_downstream_risk |     2024 |            6 |            1        |  1        |            0.749257 |                1 |            0.285714 | [1, 1]                 | [1, 1]       | [0.512, 0.751]         | [1, 1]              | [0.0833, 0.579]        |
| mlp_scalar_nn                 | broad_downstream_risk |     2024 |            6 |            0.734524 |  0.999504 |            0.750743 |                1 |            0.285714 | [0.383, 1]             | [0.999, 1]   | [0.75, 0.751]          | [1, 1]              | [0.0809, 0.577]        |
| cnn1d_waveform_nn             | broad_downstream_risk |     2024 |            6 |            0.9      |  0.999257 |            0.750743 |                1 |            0.285714 | [0.715, 1]             | [0.998, 1]   | [0.75, 0.751]          | [0.818, 1]          | [0.0833, 0.55]         |
| hybrid_gated_cnn_tabular      | broad_downstream_risk |     2024 |            6 |            1        |  1        |            0.750743 |                1 |            0.285714 | [1, 1]                 | [1, 1]       | [0.75, 0.751]          | [1, 1]              | [0.0611, 0.555]        |

## Fixed-coverage propagation
| method                        |   n_selected |   curated_broad_precision |   reviewer_disagreement_rate |   method_disagreement_rate_vs_traditional |   downstream_risk_rate |   timing_sigma68_shift |   charge_res68_shift |   pileup_excess_shift |   baseline_lowering_enrichment | curated_broad_precision_ci   | reviewer_disagreement_rate_ci   | method_disagreement_rate_vs_traditional_ci   | timing_sigma68_shift_ci   | charge_res68_shift_ci   | pileup_excess_shift_ci   | baseline_lowering_enrichment_ci   |
|:------------------------------|-------------:|--------------------------:|-----------------------------:|------------------------------------------:|-----------------------:|-----------------------:|---------------------:|----------------------:|-------------------------------:|:-----------------------------|:--------------------------------|:---------------------------------------------|:--------------------------|:------------------------|:-------------------------|:----------------------------------|
| traditional_robust_broad_veto |          226 |                  0.769912 |                     0.238938 |                                  0        |              0.0265487 |                2.72439 |            0.823708  |                     0 |                        8.95575 | [0.707, 0.828]               | [0.167, 0.308]                  | [0, 0]                                       | [0, 2.95]                 | [0.378, 1.67]           | [0, 0]                   | [7.52, 10.7]                      |
| ridge_scalar                  |          226 |                  0.769912 |                     0.216814 |                                  0.367257 |              0.0265487 |                2.92886 |            0.803411  |                     0 |                        6.96559 | [0.714, 0.822]               | [0.175, 0.265]                  | [0.367, 0.367]                               | [0, 2.95]                 | [0.214, 1.69]           | [0, 0]                   | [4.68, 8.86]                      |
| gradient_boosted_trees        |          226 |                  0.765487 |                     0.212389 |                                  0.318584 |              0.0265487 |                1.07158 |            0.690266  |                     0 |                        8.95575 | [0.693, 0.833]               | [0.164, 0.258]                  | [0.319, 0.319]                               | [0, 2.92]                 | [0.403, 1.57]           | [0, 0]                   | [7.48, 10.6]                      |
| mlp_scalar_nn                 |          226 |                  0.712389 |                     0.207965 |                                  0.318584 |              0.0265487 |                0       |            0.630476  |                     0 |                        8.95575 | [0.655, 0.763]               | [0.138, 0.268]                  | [0.319, 0.319]                               | [0, 2.93]                 | [0.322, 0.81]           | [0, 0]                   | [7.42, 10.6]                      |
| cnn1d_waveform_nn             |          226 |                  0.743363 |                     0.146018 |                                  0.438053 |              0.0265487 |                0       |            0.549625  |                     0 |                        5.9705  | [0.647, 0.821]               | [0.105, 0.187]                  | [0.438, 0.438]                               | [0, 0]                    | [0.487, 0.746]          | [0, 0]                   | [2.88, 7.72]                      |
| hybrid_gated_cnn_tabular      |          226 |                  0.725664 |                     0.19469  |                                  0.5      |              0.0265487 |                0       |            0.0998825 |                     0 |                        5.9705  | [0.634, 0.794]               | [0.144, 0.238]                  | [0.5, 0.5]                                   | [0, 0]                    | [-0.0991, 0.37]         | [0, 0]                   | [2.67, 7.63]                      |

## Per-run diagnostics
|   run | method                        |   n_eval |   n_positive |   average_precision |    roc_auc |   balanced_accuracy |   recall_at_1pct |   precision_at_1pct |
|------:|:------------------------------|---------:|-------------:|--------------------:|-----------:|--------------------:|-----------------:|--------------------:|
|    37 | traditional_robust_broad_veto |      305 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    37 | ridge_scalar                  |      305 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    37 | gradient_boosted_trees        |      305 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    37 | mlp_scalar_nn                 |      305 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    37 | cnn1d_waveform_nn             |      305 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    37 | hybrid_gated_cnn_tabular      |      305 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    40 | traditional_robust_broad_veto |      169 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    40 | ridge_scalar                  |      169 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    40 | gradient_boosted_trees        |      169 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    40 | mlp_scalar_nn                 |      169 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    40 | cnn1d_waveform_nn             |      169 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    40 | hybrid_gated_cnn_tabular      |      169 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    42 | traditional_robust_broad_veto |      210 |            2 |            1        |   1        |            0.752404 |              1   |            0.666667 |
|    42 | ridge_scalar                  |      210 |            2 |            1        |   1        |            0.752404 |              1   |            0.666667 |
|    42 | gradient_boosted_trees        |      210 |            2 |            1        |   1        |            0.519231 |              1   |            0.666667 |
|    42 | mlp_scalar_nn                 |      210 |            2 |            1        |   1        |            0.752404 |              1   |            0.666667 |
|    42 | cnn1d_waveform_nn             |      210 |            2 |            1        |   1        |            0.752404 |              1   |            0.666667 |
|    42 | hybrid_gated_cnn_tabular      |      210 |            2 |            1        |   1        |            0.752404 |              1   |            0.666667 |
|    49 | traditional_robust_broad_veto |      180 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    49 | ridge_scalar                  |      180 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    49 | gradient_boosted_trees        |      180 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    49 | mlp_scalar_nn                 |      180 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    49 | cnn1d_waveform_nn             |      180 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    49 | hybrid_gated_cnn_tabular      |      180 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    52 | traditional_robust_broad_veto |       81 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    52 | ridge_scalar                  |       81 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    52 | gradient_boosted_trees        |       81 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    52 | mlp_scalar_nn                 |       81 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    52 | cnn1d_waveform_nn             |       81 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    52 | hybrid_gated_cnn_tabular      |       81 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    57 | traditional_robust_broad_veto |      169 |            1 |            1        |   1        |            0.75     |              1   |            0.5      |
|    57 | ridge_scalar                  |      169 |            1 |            1        |   1        |            0.75     |              1   |            0.5      |
|    57 | gradient_boosted_trees        |      169 |            1 |            1        |   1        |            0.75     |              1   |            0.5      |
|    57 | mlp_scalar_nn                 |      169 |            1 |            1        |   1        |            0.75     |              1   |            0.5      |
|    57 | cnn1d_waveform_nn             |      169 |            1 |            1        |   1        |            0.75     |              1   |            0.5      |
|    57 | hybrid_gated_cnn_tabular      |      169 |            1 |            1        |   1        |            0.75     |              1   |            0.5      |
|    58 | traditional_robust_broad_veto |      194 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    58 | ridge_scalar                  |      194 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    58 | gradient_boosted_trees        |      194 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    58 | mlp_scalar_nn                 |      194 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    58 | cnn1d_waveform_nn             |      194 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    58 | hybrid_gated_cnn_tabular      |      194 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    60 | traditional_robust_broad_veto |      155 |            2 |            1        |   1        |            0.751634 |              1   |            1        |
|    60 | ridge_scalar                  |      155 |            2 |            1        |   1        |            0.751634 |              1   |            1        |
|    60 | gradient_boosted_trees        |      155 |            2 |            1        |   1        |            0.715686 |              1   |            1        |
|    60 | mlp_scalar_nn                 |      155 |            2 |            1        |   1        |            0.751634 |              1   |            1        |
|    60 | cnn1d_waveform_nn             |      155 |            2 |            0.833333 |   0.996732 |            0.751634 |              0.5 |            0.5      |
|    60 | hybrid_gated_cnn_tabular      |      155 |            2 |            1        |   1        |            0.751634 |              1   |            1        |
|    62 | traditional_robust_broad_veto |      219 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    62 | ridge_scalar                  |      219 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    62 | gradient_boosted_trees        |      219 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    62 | mlp_scalar_nn                 |      219 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    62 | cnn1d_waveform_nn             |      219 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    62 | hybrid_gated_cnn_tabular      |      219 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    64 | traditional_robust_broad_veto |      188 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    64 | ridge_scalar                  |      188 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    64 | gradient_boosted_trees        |      188 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    64 | mlp_scalar_nn                 |      188 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    64 | cnn1d_waveform_nn             |      188 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    64 | hybrid_gated_cnn_tabular      |      188 |            0 |          nan        | nan        |          nan        |            nan   |          nan        |
|    65 | traditional_robust_broad_veto |      154 |            1 |            1        |   1        |            0.751634 |              1   |            0.5      |
|    65 | ridge_scalar                  |      154 |            1 |            1        |   1        |            0.751634 |              1   |            0.5      |
|    65 | gradient_boosted_trees        |      154 |            1 |            1        |   1        |            0.751634 |              1   |            0.5      |
|    65 | mlp_scalar_nn                 |      154 |            1 |            1        |   1        |            0.751634 |              1   |            0.5      |
|    65 | cnn1d_waveform_nn             |      154 |            1 |            1        |   1        |            0.751634 |              1   |            0.5      |
|    65 | hybrid_gated_cnn_tabular      |      154 |            1 |            1        |   1        |            0.751634 |              1   |            0.5      |

## Leakage and systematics checks
| check                                 |   value | pass   | note                                                                                                |
|:--------------------------------------|--------:|:-------|:----------------------------------------------------------------------------------------------------|
| raw_reproduction_before_models        |  640737 | True   | script raises before taxonomy/model work if this fails                                              |
| train_heldout_run_overlap             |       0 | True   | all templates, thresholds, scalers, and models fit on non-held-out runs                             |
| identifier_features_used              |       0 | True   | run, event, eventno, evt, stave, source index, and reviewer labels are excluded from model matrices |
| eval_waveform_hash_seen_in_train_rate |       0 | True   | rounded normalized waveform hashes at 1e-3 precision                                                |
| p09c_charge_outlier_positive_count    |       1 | True   | documents the original low-positive bottleneck rather than treating high AP as robust               |
| expanded_downstream_risk_runs         |       4 | True   | number of expanded held-out runs with at least one broad downstream-risk positive                   |
| reviewer_disagreement_used_as_target  |       0 | True   | reviewer disagreement is computed only after scoring for nuisance reporting                         |

## Result
The winner by primary downstream-risk average precision is `ridge_scalar` with AP 1.0000 (95% run-bootstrap CI [1, 1]). At fixed coverage, the same method has curated broad precision 0.7699 and reviewer-disagreement rate 0.2168. The fixed-coverage table gives timing sigma68 shift, charge res68 shift, pile-up excess shift, and baseline-lowering enrichment with run-bootstrap CIs.

## Caveats
The propagation endpoints are deterministic audit labels, not new hand-scanned physics truth. Reviewer disagreement is a nuisance diagnostic from fixed rubrics, not an adjudicated ground truth. Since charge, width, and timing quantities participate in both some labels and tabular features, high tabular AP should be read as closure of the operational veto definition rather than proof of a new waveform class. The CNN-only comparator is the least scalar-coupled stress test. Bootstrap intervals cover run-to-run composition but not uncertainty in the rule family itself.

## Provenance
Runtime was 619.4 s on `billy` with Python `3.7.6`. Torch device for neural models was `cpu`. `manifest.json` records command, input, code, and output hashes.

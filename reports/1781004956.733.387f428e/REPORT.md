# S10c: stratified current-dependent pile-up excess

- **Ticket:** `1781004956.733.387f428e`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** all ML predictions are leave-one-run-out; CIs resample runs within current group.

## Reproduction first

S10 reproduces from raw ROOT before stratification: downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA. All six documented S10 topology fractions pass the +/-0.0015 tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Traditional stratified method

Events with at least one selected B pulse are stratified by the maximum selected-pulse amplitude, the S16 adaptive-pedestal-lowering diagnostic, and a P02-style pulse topology flag (normal, early/pathological, broad/late).  Strata absent or too small in either current group are excluded; 8 matched strata remain.  The frozen S10 global high-minus-low downstream excess is 0.01029 per selected event.

Matched stratified downstream excess: **0.02025** per selected event with run-bootstrap 95% CI **[0.01875, 0.02847]**.  The excess survives stratification, but is not uniform across strata.

| amp_bin       | baseline_bin       | p02_topology        |   low_n |   high_n |   low_downstream_fraction |   high_downstream_fraction |   high_minus_low |   match_weight |
|:--------------|:-------------------|:--------------------|--------:|---------:|--------------------------:|---------------------------:|-----------------:|---------------:|
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |    2982 |   172450 |                 0.0127431 |                  0.018214  |       0.00547085 |     0.519603   |
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |    1685 |    32818 |                 0.0237389 |                  0.0791334 |       0.0553945  |     0.293605   |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |     779 |    12463 |                 0.0397946 |                  0.0445318 |       0.00473721 |     0.135738   |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |     132 |     6010 |                 0.0454545 |                  0.0472546 |       0.00180003 |     0.0230005  |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |      51 |     2499 |                 0.0392157 |                  0.0616246 |       0.022409   |     0.00888657 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |      45 |     1427 |                 0.0222222 |                  0.0525578 |       0.0303356  |     0.00784109 |

## ML methods

The injection score is a leave-one-run-out logistic classifier trained on synthetic two-pulse overlays made only from other runs.  The weak-current score is a separate leave-one-run-out classifier for 20 nA versus 2 nA using waveform and S16/P02 diagnostic features.  Its C/calibration step uses group-CV when both current classes have at least two training runs; for held-out low-current runs, only one low-current training run remains, so that step falls back to stratified row folds while the reported prediction is still for a completely held-out run.

Injection pile-up score high-minus-low: **0.02363** [0.01651, 0.03494].  Weak-current score high-minus-low: **0.02975** [0.02460, 0.03582], with run-held-out current-label AUC **0.640**.

Per-stratum probability checks are in `ml_injection_calibration_by_stratum.csv` and `ml_current_calibration_by_stratum.csv`.

## Leakage review

| check                               |    value | flag   | note                                                                                            |
|:------------------------------------|---------:|:-------|:------------------------------------------------------------------------------------------------|
| heldout_runs_excluded_from_training | 1        | False  | Every ML prediction is produced by a model trained with that run removed.                       |
| identifier_features_excluded        | 1        | False  | Feature list excludes run, event number, current, group, downstream label, and n-selected.      |
| row_split_current_auc               | 0.665234 | False  | Random row split is expected to be optimistic; compare with run-held-out weak-current AUC.      |
| run_heldout_current_auc             | 0.639692 | False  | Flagged if the current classifier is implausibly separable under run holdout.                   |
| row_minus_run_current_auc           | 0.025542 | False  | Large row-split advantage would indicate run/row leakage sensitivity.                           |
| injection_score_downstream_auc      | 0.697746 | False  | Flagged if the synthetic pile-up score almost directly predicts the downstream occupancy label. |

The weak-current classifier is useful as a diagnostic, not as a pile-up truth label.  It can learn detector-pathology and run-period differences that co-vary with current, so the physics conclusion is based on the downstream occupancy excess and uses the ML scores only as shape/pathology handles.

## Conclusion

The S10 high-current downstream excess remains after matching on amplitude, S16 lowering, and P02 topology: 0.02025 per selected event with run-bootstrap CI [0.01875, 0.02847]. The largest positive stratum is amp_2500_4500 / s16_no_lowering / p02_broad_late, so the excess is heterogeneous and partly concentrated in pulse-pathology-like regions rather than being a uniform beam-current scale factor. ML scores support that interpretation as diagnostics, but they are not treated as truth labels.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stratum_excess_table.csv`, `matched_summary.csv`, `run_heldout_summary.csv`, `ml_score_by_event.csv`, `ml_stratum_scores.csv`, calibration/leakage CSVs, and PNG diagnostics are in this folder.

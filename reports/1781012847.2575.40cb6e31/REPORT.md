# S07e: archive provenance search for App.A training table

- **Ticket:** `1781012847.2575.40cb6e31`
- **Worker:** `testbeam-laptop-1`
- **Question:** can the App.A 12,147 labelled-event table be recovered from external archives, old notebooks, or non-repo derived data?
- **Inputs:** raw B-stack `HRDv` ROOT, mirrored/external filesystem candidates, S01 q_template artifact.

## Raw-ROOT Reproduction First

| quantity        | documented | raw_cfd20 | delta | matches |
| --------------- | ---------- | --------- | ----- | ------- |
| labelled_events | 12147      | 9897      | -2250 | False   |
| clean           | 10636      | 7583      | -3053 | False   |
| violating       | 1511       | 2314      | 803   | False   |

The documented App.A count is not reproduced from raw `HRDv`: the raw CFD20 definition gives `9897` labelled events (`7583` clean, `2314` violating), not `12,147` (`10,636` clean, `1,511` violating). The benchmark below therefore uses the raw-reproducible labels and treats the historical number as a provenance target, not as a detector result.

## Archive Provenance Search

| check                           | value | pass  | notes                                                                          |
| ------------------------------- | ----- | ----- | ------------------------------------------------------------------------------ |
| table_like_files_scanned        | 1905  | True  | Candidate table-like files with App.A/S07/label/training/timing names.         |
| exact_12147_row_tables          | 0     | False | Any table with exactly the documented labelled-event row count.                |
| plausible_recovered_label_table | 0     | False | Exact 12,147 rows plus label/run/event-like columns.                           |
| semantic_text_hits              | 574   | True  | Mostly docs/notebooks/PDF text; table recovery requires a plausible table hit. |

Top table-like candidates:

| path                                                                                                                                   | row_count | exact_12147_rows | plausible_label_table | labelish_columns |
| -------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---------------- | --------------------- | ---------------- |
| /home/billy/.tb-workers/tb-planner/configs/p01e_strict_latent_timing_audit.json                                                        |           | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/configs/s07e_1781012659_1186_11c940a0.json                                                          |           | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/configs/s07f_1781012109_1290_18206042.json                                                          |           | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/configs/s11b_1781012659_s07d_two_pulse_fit.json                                                     |           | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_per_pulse.csv.gz           | 640737    | False            | False                 | run|eventno|evt  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_summary_by_group_stave.csv | 16        | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15157.07ef03cf__s02_timing_pickoff/head_to_head_benchmark.csv                    | 3         | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15157.07ef03cf__s02_timing_pickoff/manifest.json                                 |           | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15157.07ef03cf__s02_timing_pickoff/ml_residual_calibration.csv                   | 7         | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15157.07ef03cf__s02_timing_pickoff/ml_ridge_cv.csv                               | 20        | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15157.07ef03cf__s02_timing_pickoff/reproduction_match_table.csv                  | 6         | False            | False                 |                  |
| /home/billy/.tb-workers/tb-planner/reports/1780997954.15157.07ef03cf__s02_timing_pickoff/result.json                                   |           | False            | False                 |                  |

The semantically relevant text hits are documentation or mirrors of the same documentation. Numeric-only hits in unrelated GNN/HIBEAM logs were excluded from the source-table claim. No table with exactly 12,147 rows and run/event/label-like columns was recovered.

## Traditional And ML Methods

Evaluation is by run-held-out folds with run-bootstrap 95% CIs over out-of-fold predictions.

| method                      | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | note                                                       | brier      | brier_ci_low | brier_ci_high |
| --------------------------- | -------- | -------------- | --------------- | ----------------- | ------------------------ | ------------------------- | ---------------------------------------------------------- | ---------- | ------------ | ------------- |
| traditional_span_q_template | 0.912455 | 0.883556       | 0.928962        | 0.960624          | 0.916883                 | 0.976804                  | Uses downstream span; overlaps weak-label definition.      |            |              |               |
| traditional_q_template_only | 0.716918 | 0.690182       | 0.740096        | 0.88189           | 0.822533                 | 0.909617                  | No timing-span feature.                                    |            |              |               |
| rf_clean_timing             | 0.993539 | 0.991518       | 0.995229        | 0.997808          | 0.995906                 | 0.998622                  | RF excludes timing spans, pair residuals, run, and sample. | 0.0260794  | 0.0235895    | 0.0294905     |
| leaky_rf_control            | 1        | 1              | 1               | 1                 | 1                        | 1                         | RF with forbidden label-defining timing spans.             | 0.00249969 | 0.00217208   | 0.00303721    |

The strong traditional span+q_template method is intentionally partly label-overlapping and reaches ROC AUC `0.912`. The de-leaked q_template-only baseline reaches `0.717`. The RF reaches `0.994` while excluding timing spans, pair residuals, run, and sample.

## Leakage Hunt

| check                               | value | pass  |
| ----------------------------------- | ----- | ----- |
| rf_forbidden_feature_intersection   |       | True  |
| leaky_control_auc_is_ceiling        | 1     | True  |
| archive_plausible_label_table_found | 0     | False |
| qtemplate_unmatched_events          | 2     | True  |

The near-perfect leaky control confirms that timing-span features can trivially recover the weak label. The main RF has no forbidden timing/run features, but because the historical table was not recovered, it remains a weak-label screen only.

## Finding

I do not recover the App.A 12,147 labelled-event training table from the external/mirrored archives searched here. The only durable source of the number remains documentation; raw HRDv produces a different count. The supported action is to retire `12,147` unless a future, byte-identifiable derived label table is found.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/1781012847.2575.40cb6e31/s07e_app_a_archive_provenance_search.py
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `archive_table_inventory.csv`, `archive_text_hits.csv`, `archive_provenance_summary.csv`, `scoreboard.csv`, `leakage_checks.csv`.

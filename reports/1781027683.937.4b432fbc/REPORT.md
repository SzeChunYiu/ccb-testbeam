# S07k: raw-HRDv App.A label-definition sensitivity grid

- **Ticket:** `1781027683.937.4b432fbc`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack `HRDv` ROOT plus S01 `q_template`; checksums in `input_sha256.csv`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s07k_1781027683_937_4b432fbc_label_definition_sensitivity.py --config configs/s07k_1781027683_937_4b432fbc_label_definition_sensitivity.json`

## Raw ROOT reproduction first

The exact App.A-style CFD20 definition is `cfd20_ds2_app_a_qnone_ambexclude`: at least two downstream staves, clean if downstream span <5 ns and all-span <10 ns, violating if downstream span >10 ns or B2 displacement >20 ns, ambiguous events excluded.

| quantity        | documented | raw_grid_appa | delta | matches |
| --------------- | ---------- | ------------- | ----- | ------- |
| labelled_events | 12147      | 9897          | -2250 | False   |
| clean           | 10636      | 7583          | -3053 | False   |
| violating       | 1511       | 2314          | 803   | False   |

This reproduces the current raw-HRDv number (`9,897` labelled events), not the documented `12,147` table.

## Sensitivity grid

The deterministic grid varied CFD fraction (`0.15`, `0.20`, `0.25`), downstream multiplicity (`>=2`, `>=3`), strict/App.A/loose timing thresholds, q_template quality (`none`, `q_downstream_max <= 0.06`), and ambiguity handling (`exclude`, `as_violating`). It produced 72 label definitions.

Closest definitions by labelled-count delta:

| definition_id                          | labelled_events | clean | violating | ambiguous_promoted | labelled_delta_to_12147 | clean_delta_to_10636 | violating_delta_to_1511 |
| -------------------------------------- | --------------- | ----- | --------- | ------------------ | ----------------------- | -------------------- | ----------------------- |
| cfd15_ds2_loose_qnone_ambexclude       | 12002           | 9816  | 2186      | 0                  | -145                    | -820                 | 675                     |
| cfd20_ds2_loose_qnone_ambexclude       | 12307           | 10153 | 2154      | 0                  | 160                     | -483                 | 643                     |
| cfd25_ds2_loose_qnone_ambexclude       | 12490           | 10368 | 2122      | 0                  | 343                     | -268                 | 611                     |
| cfd25_ds2_app_a_qnone_ambexclude       | 9951            | 7661  | 2290      | 0                  | -2196                   | -2975                | 779                     |
| cfd20_ds2_app_a_qnone_ambexclude       | 9897            | 7583  | 2314      | 0                  | -2250                   | -3053                | 803                     |
| cfd15_ds2_app_a_qnone_ambexclude       | 9739            | 7386  | 2353      | 0                  | -2408                   | -3250                | 842                     |
| cfd20_ds2_strict_qnone_ambas_violating | 15354           | 4854  | 10500     | 7848               | 3207                    | -5782                | 8989                    |
| cfd15_ds2_strict_qnone_ambas_violating | 15354           | 5101  | 10253     | 7524               | 3207                    | -5535                | 8742                    |
| cfd20_ds2_app_a_qnone_ambas_violating  | 15354           | 7583  | 7771      | 5457               | 3207                    | -3053                | 6260                    |
| cfd15_ds2_app_a_qnone_ambas_violating  | 15354           | 7386  | 7968      | 5615               | 3207                    | -3250                | 6457                    |

Full documented tuple matched by any grid point: **False**. Exact labelled-count hit ignoring clean/violating composition: **False**.

## Traditional and ML benchmark

For every valid grid point I used run-held-out folds and run-block bootstrap 95% CIs. The traditional scores are `q_template_only` and a stronger span+q score that is explicitly marked as timing-overlapping. The ML score is the same shape random forest for every definition, excluding run, event ids, and timing-span/displacement features. Leaky and shuffled-label RF controls were run alongside it.

Metrics for the fixed CFD20/App.A raw reproduction:

| method             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | brier      | brier_ci_low | brier_ci_high | tail_rejection_at_90pct_clean_eff | tail_rejection_ci_low | tail_rejection_ci_high | forbidden_timing_features_used |
| ------------------ | -------- | -------------- | --------------- | ----------------- | ------------------------ | ------------------------- | ---------- | ------------ | ------------- | --------------------------------- | --------------------- | ---------------------- | ------------------------------ |
| q_template_only    | 0.716945 | 0.691433       | 0.738183        | 0.8819            | 0.824828                 | 0.905746                  | 0.163389   | 0.136171     | 0.211264      | 0.302506                          | 0.25671               | 0.355813               | False                          |
| traditional_span_q | 0.952886 | 0.936982       | 0.961585        | 0.981715          | 0.966721                 | 0.988695                  | 0.036346   | 0.0310644    | 0.0449653     | 0.982282                          | 0.975624              | 0.989762               | True                           |
| rf_shape           | 0.993414 | 0.991186       | 0.995217        | 0.997799          | 0.995889                 | 0.998542                  | 0.0262919  | 0.0239656    | 0.0299715     | 0.985739                          | 0.978969              | 0.991126               | False                          |
| leaky_rf           | 1        | 1              | 1               | 1                 | 1                        | 1                         | 0.00147492 | 0.00133777   | 0.00168277    | 1                                 | 1                     | 1                      | True                           |
| shuffled_label_rf  | 0.403319 | 0.370818       | 0.440462        | 0.712579          | 0.586391                 | 0.792743                  | 0.245333   | 0.241359     | 0.253216      | 0.0384615                         | 0.0255273             | 0.0546788              | False                          |

## Leakage hunt

- Admissible RF feature sets exclude `run`, `eventno`, `evt`, active downstream span, active all-span, and active B2 displacement.
- The leaky RF deliberately includes active timing spans/displacement; it is a ceiling control, not an admissible method.
- Shuffled-label RF controls train on permuted training labels in the same run-held-out folds.
- RF AUC >= 0.98 occurred for 35 definitions; these are not accepted as truth because leaky controls are at/near ceiling and labels are timing-derived weak labels.
- Shuffled-control failures outside [0.35, 0.65] AUC: 1.

## Finding

The raw CFD20 App.A reproduction remains `9,897` labelled events (`7,583` clean, `2,314` violating), while the closest sensitivity-grid count still fails the documented clean/violating composition. I find no raw-HRDv-clean label-definition variation in this grid that explains `12,147`; downstream consumers should treat the App.A table as retired or as a bounded weak-label systematic rather than as a reproducible detector-result count.

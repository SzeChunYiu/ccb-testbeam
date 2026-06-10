# S05d: sorted ROOT quality-variable A-control repeat

- **Ticket:** 1781017418.11811.0f2442d1
- **Worker:** testbeam-laptop-1
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05d_1781017418_11811_0f2442d1_sorted_quality_a_control.yaml`
- **Raw input:** `data/root/root`
- **Sorted A input:** `data/sorted-a`

## Question

Repeat the loose-tier A-stack external-control test using sorted ROOT quality variables (`hrdMaxTS`, `hrdTrMax`, `hrdMax`, trap summaries, and baseline summaries). The test asks whether sorted pulse-shape quality cuts isolate cleaner A/B coincidences than raw low-threshold amplitude tiers. No Monte Carlo was used.

## Reproduction first

The raw ROOT count gate was run before reading sorted quality variables.

| quantity                                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses                         |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses            |         125096 |       125096 |       0 |           0 | True   |
| astack_sample_iii_analysis_events_with_selected |           7168 |         7168 |       0 |           0 | True   |
| astack_sample_iii_analysis_selected_pulses      |           9682 |         9682 |       0 |           0 | True   |
| astack_sample_iv_analysis_events_with_selected  |            767 |          767 |       0 |           0 | True   |
| astack_sample_iv_analysis_selected_pulses       |            894 |          894 |       0 |           0 | True   |

## Sorted quality tiers

All tiers use loose B-pair rows with both B staves above `500` ADC. Sorted A tiers then require event-matched A quality in `data/sorted-a`; the sorted tree is joined to raw A by entry order, with `hrdEvtNo` retained as a diagnostic only.

| tier                  |   n_pair_rows |   n_runs |   n_unique_events |   n_a_raw_any_pair_rows |   n_a_raw_both_pair_rows |
|:----------------------|--------------:|---------:|------------------:|------------------------:|-------------------------:|
| raw_loose500          |         74176 |       21 |             32207 |                     452 |                      140 |
| sorted_any_trmax1000  |           893 |       20 |               457 |                     452 |                      140 |
| sorted_any_clean1000  |           794 |       20 |               406 |                     452 |                      140 |
| sorted_both_clean1000 |           180 |       14 |               106 |                     161 |                      140 |
| sorted_any_trmax2000  |           734 |       20 |               371 |                     452 |                      140 |

## Traditional and ML methods

Traditional method: grouped-run-heldout Ridge using pair identity and B-pair amplitude/shape features; the sorted-A version adds `hrdMax`, `hrdMaxTS`, `hrdTrMax`, trap-window, trap-tail, and baseline summaries. ML method: grouped-run-heldout bounded ExtraTrees with the same B-only and B-plus-sorted-A split. Feature lists exclude run id, event id, `A_sorted_evt`, raw times, and the target residual.

| tier                 | method                         | subset             |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                                    |
|:---------------------|:-------------------------------|:-------------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:------------------------------------------------------------------------|
| raw_loose500         | traditional_b_only             | all                |         74176 |       21 |      7.98329 |             7.27916 |              9.21816 |      12.8512  |             0.494742  | run-held-out Ridge using B pair waveform features                       |
| raw_loose500         | traditional_b_only             | raw_A_any_selected |           452 |       20 |      9.70295 |             7.24271 |             11.8798  |      14.3202  |             0.55531   | run-held-out Ridge using B pair waveform features                       |
| raw_loose500         | traditional_b_only             | downstream_only    |         23815 |       21 |      7.60764 |             7.08871 |              8.41509 |       9.61134 |             0.485114  | run-held-out Ridge using B pair waveform features                       |
| raw_loose500         | traditional_b_plus_sorted_a    | all                |         74176 |       21 |      7.98742 |             7.34891 |              9.26971 |      12.8537  |             0.495888  | same Ridge plus sorted A quality controls                               |
| raw_loose500         | traditional_b_plus_sorted_a    | raw_A_any_selected |           452 |       20 |     10.0216  |             7.53537 |             11.7057  |      14.4812  |             0.588496  | same Ridge plus sorted A quality controls                               |
| raw_loose500         | traditional_b_plus_sorted_a    | downstream_only    |         23815 |       21 |      7.61453 |             7.0852  |              8.4439  |       9.61934 |             0.484065  | same Ridge plus sorted A quality controls                               |
| raw_loose500         | ml_extra_trees_b_only          | all                |         74176 |       21 |      2.59748 |             2.23535 |              4.08734 |       9.60975 |             0.190533  | run-held-out bounded ExtraTrees using B features only                   |
| raw_loose500         | ml_extra_trees_b_only          | raw_A_any_selected |           452 |       20 |      3.77918 |             2.74441 |              5.18827 |       9.39552 |             0.25885   | run-held-out bounded ExtraTrees using B features only                   |
| raw_loose500         | ml_extra_trees_b_only          | downstream_only    |         23815 |       21 |      1.61241 |             1.49867 |              1.98154 |       5.5645  |             0.0490027 | run-held-out bounded ExtraTrees using B features only                   |
| raw_loose500         | ml_extra_trees_b_plus_sorted_a | all                |         74176 |       21 |      2.66114 |             2.2846  |              4.51314 |       9.79713 |             0.196681  | run-held-out bounded ExtraTrees using B features plus sorted A controls |
| raw_loose500         | ml_extra_trees_b_plus_sorted_a | raw_A_any_selected |           452 |       20 |      3.84755 |             2.94151 |              4.92945 |       9.79633 |             0.24115   | run-held-out bounded ExtraTrees using B features plus sorted A controls |
| raw_loose500         | ml_extra_trees_b_plus_sorted_a | downstream_only    |         23815 |       21 |      1.68196 |             1.52833 |              2.20072 |       5.68383 |             0.0587445 | run-held-out bounded ExtraTrees using B features plus sorted A controls |
| sorted_any_clean1000 | traditional_b_only             | all                |           794 |       20 |      8.16957 |             7.01129 |              9.7233  |      13.1708  |             0.492443  | run-held-out Ridge using B pair waveform features                       |
| sorted_any_clean1000 | traditional_b_only             | raw_A_any_selected |           452 |       20 |      8.86566 |             7.1319  |             10.1171  |      14.2526  |             0.530973  | run-held-out Ridge using B pair waveform features                       |
| sorted_any_clean1000 | traditional_b_only             | downstream_only    |           223 |       18 |      6.4995  |             5.40978 |              8.36161 |       8.09188 |             0.443946  | run-held-out Ridge using B pair waveform features                       |
| sorted_any_clean1000 | traditional_b_plus_sorted_a    | all                |           794 |       20 |      8.92198 |             7.87255 |              9.70286 |      13.4602  |             0.535264  | same Ridge plus sorted A quality controls                               |
| sorted_any_clean1000 | traditional_b_plus_sorted_a    | raw_A_any_selected |           452 |       20 |      9.41122 |             7.57886 |             10.9505  |      14.5938  |             0.570796  | same Ridge plus sorted A quality controls                               |
| sorted_any_clean1000 | traditional_b_plus_sorted_a    | downstream_only    |           223 |       18 |      6.89557 |             5.52568 |              8.85137 |       8.45099 |             0.470852  | same Ridge plus sorted A quality controls                               |
| sorted_any_clean1000 | ml_extra_trees_b_only          | all                |           794 |       20 |      9.85449 |             5.613   |             15.1193  |      18.6157  |             0.462217  | run-held-out bounded ExtraTrees using B features only                   |
| sorted_any_clean1000 | ml_extra_trees_b_only          | raw_A_any_selected |           452 |       20 |     12.3693  |             5.80241 |             17.1551  |      20.0055  |             0.502212  | run-held-out bounded ExtraTrees using B features only                   |
| sorted_any_clean1000 | ml_extra_trees_b_only          | downstream_only    |           223 |       18 |      7.65405 |             4.64811 |              8.84677 |       8.70988 |             0.399103  | run-held-out bounded ExtraTrees using B features only                   |
| sorted_any_clean1000 | ml_extra_trees_b_plus_sorted_a | all                |           794 |       20 |      9.99141 |             5.79321 |             13.6338  |      17.9648  |             0.469773  | run-held-out bounded ExtraTrees using B features plus sorted A controls |
| sorted_any_clean1000 | ml_extra_trees_b_plus_sorted_a | raw_A_any_selected |           452 |       20 |     11.7042  |             6.39009 |             15.186   |      19.0471  |             0.524336  | run-held-out bounded ExtraTrees using B features plus sorted A controls |
| sorted_any_clean1000 | ml_extra_trees_b_plus_sorted_a | downstream_only    |           223 |       18 |      7.20216 |             4.66237 |              8.89943 |       8.42927 |             0.421525  | run-held-out bounded ExtraTrees using B features plus sorted A controls |

Bootstrap deltas are sorted-A minus B-only on sigma68; negative means sorted A controls narrowed held-out B residuals.

| tier                 | comparison                             |   ci_low_ns |   ci_high_ns |   p_value |
|:---------------------|:---------------------------------------|------------:|-------------:|----------:|
| raw_loose500         | traditional_sorted_a_minus_b_only      | -0.0172118  |    0.0386067 |  0.513333 |
| raw_loose500         | ml_sorted_a_minus_ml_b_only            | -0.00484661 |    0.236869  |  0.08     |
| raw_loose500         | ml_sorted_a_minus_traditional_sorted_a | -5.73503    |   -4.87323   |  0        |
| sorted_any_clean1000 | traditional_sorted_a_minus_b_only      | -0.34683    |    1.3912    |  0.113333 |
| sorted_any_clean1000 | ml_sorted_a_minus_ml_b_only            | -2.15788    |    2.23733   |  0.926667 |
| sorted_any_clean1000 | ml_sorted_a_minus_traditional_sorted_a | -3.1342     |    4.68757   |  0.693333 |

Primary tier `sorted_any_clean1000` deltas:

| tier                 | comparison                             |   ci_low_ns |   ci_high_ns |   p_value |
|:---------------------|:---------------------------------------|------------:|-------------:|----------:|
| sorted_any_clean1000 | traditional_sorted_a_minus_b_only      |    -0.34683 |      1.3912  |  0.113333 |
| sorted_any_clean1000 | ml_sorted_a_minus_ml_b_only            |    -2.15788 |      2.23733 |  0.926667 |
| sorted_any_clean1000 | ml_sorted_a_minus_traditional_sorted_a |    -3.1342  |      4.68757 |  0.693333 |

Run-held-out fold summary:

| tier                 | heldout_runs      |   n_pair_rows |   ridge_alpha_b |   ridge_alpha_b_plus_a |   ml_train_rows |   extra_trees_rmse_b |   extra_trees_rmse_b_plus_a |
|:---------------------|:------------------|--------------:|----------------:|-----------------------:|----------------:|---------------------:|----------------------------:|
| raw_loose500         | 47 52 58 61       |         14917 |              10 |                     10 |            9000 |              8.5946  |                     8.53783 |
| raw_loose500         | 46 53 55 59       |         14798 |              10 |                     10 |            9000 |              9.02263 |                     9.49905 |
| raw_loose500         | 48 57 62          |         14817 |              10 |                     10 |            9000 |              9.12025 |                     9.13836 |
| raw_loose500         | 44 50 54 60       |         14786 |              10 |                     10 |            9000 |              8.49089 |                     8.40184 |
| raw_loose500         | 45 49 51 56 63 65 |         14858 |              10 |                     10 |            9000 |             12.2247  |                    12.6913  |
| sorted_any_clean1000 | 47 56 57          |           158 |              10 |                     10 |             636 |             23.4379  |                    21.5258  |
| sorted_any_clean1000 | 44 45 50 58       |           158 |              10 |                     10 |             636 |             18.4842  |                    18.885   |
| sorted_any_clean1000 | 49 51 53 60       |           160 |              10 |                     10 |             634 |             20.5281  |                    20.1608  |
| sorted_any_clean1000 | 54 55 62 63 65    |           159 |              10 |                     10 |             635 |             13.5303  |                    13.0518  |
| sorted_any_clean1000 | 46 48 59 61       |           159 |              10 |                     10 |             635 |             14.7337  |                    14.0211  |

## Leakage checks

| tier                  | check                              | value             | pass   | interpretation                                                                     |
|:----------------------|:-----------------------------------|:------------------|:-------|:-----------------------------------------------------------------------------------|
| raw_loose500          | not_triggered                      | n/a               | True   | ML sorted-A delta CI was not wholly below zero; primary tier checked separately    |
| sorted_any_clean1000  | run_split_event_overlap            | 0.0               | True   | all model folds are grouped by held-out run                                        |
| sorted_any_clean1000  | features_exclude_forbidden_columns | 1.0               | True   | feature lists exclude run/event ids, A_sorted_evt, raw times, and target residuals |
| sorted_any_clean1000  | actual_ml_b_plus_sorted_a_sigma68  | 9.991406356063296 | True   | nominal run-held-out ML residual width                                             |
| sorted_any_clean1000  | runwise_shuffled_sorted_a_sigma68  | 9.34827750405357  | True   | sorted A controls lose event matching but preserve run marginals                   |
| sorted_any_clean1000  | intentional_target_echo_sigma68    | 0.0               | True   | positive leakage sentinel; should be unrealistically small                         |
| sorted_both_clean1000 | not_modeled_low_statistics         | 180.0             | True   | tier has too few rows or runs for grouped held-out model                           |

The primary tier is always checked with runwise shuffled sorted-A controls. Any other tier also gets this check if the ML sorted-A improvement CI is wholly below zero.

## Residual covariance

| tier                 | method                         |   n_covariances |   median_abs_cov_ns2 |   max_abs_cov_ns2 |
|:---------------------|:-------------------------------|----------------:|---------------------:|------------------:|
| raw_loose500         | ml_extra_trees_b_only          |             300 |              9.96135 |           438.446 |
| raw_loose500         | ml_extra_trees_b_plus_sorted_a |             300 |             11.444   |           440.704 |
| raw_loose500         | raw_pair_median                |             300 |             22.5524  |          2548.15  |
| raw_loose500         | traditional_b_only             |             300 |             46.2101  |           538.31  |
| raw_loose500         | traditional_b_plus_sorted_a    |             300 |             46.2076  |           538.969 |
| sorted_any_clean1000 | ml_extra_trees_b_only          |              75 |             37.8143  |          1182.67  |
| sorted_any_clean1000 | ml_extra_trees_b_plus_sorted_a |              75 |             38.0738  |           992.382 |
| sorted_any_clean1000 | raw_pair_median                |              75 |              7.78101 |          2273.35  |
| sorted_any_clean1000 | traditional_b_only             |              75 |             30.2843  |           784.693 |
| sorted_any_clean1000 | traditional_b_plus_sorted_a    |              75 |             32.1085  |           776.508 |

## Finding

Sorted A quality cuts substantially enrich rows with raw selected A controls, but the held-out B-residual widths do not show a secure event-level external-control gain. The primary sorted-A tier should therefore be treated as another null A-control result rather than evidence for a clean A/B coincidence selector.

## Artifacts

`reproduction_match_table.csv`, `tier_counts.csv`, `sorted_quality_pair_table.csv.gz`, `oof_predictions.csv`, `run_heldout_folds.csv`, `heldout_metrics.csv`, `bootstrap_deltas.csv`, `leakage_checks.csv`, `pair_covariance_by_run.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05d_1781017418_11811_0f2442d1_sorted_quality_a_control.py --config configs/s05d_1781017418_11811_0f2442d1_sorted_quality_a_control.yaml
```

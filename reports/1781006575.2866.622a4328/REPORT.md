# Study report: S07d - recover historical App.A label table

- **Ticket:** 1781006575.2866.622a4328
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, S01 q_template table, and App.A documentation; checksums in `input_sha256.csv`
- **Command:** `/home/billy/anaconda3/bin/python reports/1781006575.2866.622a4328/s07d_app_a_label_recovery.py`
- **Git commit at run:** `076f9e4f7ae6dba0efb7c7c7ef2cb28335ef0753`

## 0. Question
Can the source table or exact timing definition behind the documented App.A 12,147 labelled events be recovered from the repository and raw ROOT, or should that number be retired?

## 1. Reproduction first
The raw S00 selected-pulse gate still reproduces exactly:

| quantity              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_pulses |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib        |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis     |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib       |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis    |         125096 |       125096 |       0 |           0 | True   |

Recomputing the documented App.A weak labels directly from raw `HRDv` with median-4 baseline, amplitude >1000 ADC, CFD20 timing, >=2 downstream staves, clean = downstream span <5 ns and all-span <10 ns, and violating = downstream span >10 ns or B2 displacement >20 ns gives:

| quantity        |   documented |   raw_cfd20 |   delta | matches   |
|:----------------|-------------:|------------:|--------:|:----------|
| labelled_events |        12147 |        9897 |   -2250 | False     |
| clean           |        10636 |        7583 |   -3053 | False     |
| violating       |         1511 |        2314 |     803 | False     |

This is not the historical 12,147-event table.

## 2. Source-table search
I searched repo docs, scripts, configs, studies, and reports for `App.A`, `12,147`, `12147`, `10636`, `1511`, and `clean-timing`. The only durable numeric source is `docs/07_ml_methods.md`, plus later reports that quote or challenge it. No candidate source label table was found.

## 3. Timing-definition scan
I scanned raw B-stack ROOT over baseline mode (`median4`, `mean4`), amplitude cut (500, 750, 1000, 1250, 1500 ADC), timing pickoff (CFD 0.10-0.80, leading-edge 250-2000 ADC, peak sample), and run scope (`doc_32_runs`, `analysis_21_runs`, `sample_i_25_runs`, `sample_ii_8_runs`, `all_b_53_runs`). The best raw definition was:

| baseline   |   amp_cut_adc | pickoff_kind   |   pickoff_value |   events_total |   selected_pulses |   downstream_ge2 |   clean |   violating |   ambiguous |   labelled_events | scope       |   delta_labelled |   delta_clean |   delta_violating |   target_l1_distance | target_exact_match   |
|:-----------|--------------:|:---------------|----------------:|---------------:|------------------:|-----------------:|--------:|------------:|------------:|------------------:|:------------|-----------------:|--------------:|------------------:|---------------------:|:---------------------|
| mean4      |           500 | cfd            |             0.1 |        1096728 |            688328 |            17431 |    9095 |        2927 |        5409 |             12022 | doc_32_runs |             -125 |         -1541 |              1416 |                 3082 | False                |

No scanned definition matched all three documented numbers exactly (`labelled=12147`, `clean=10636`, `violating=1511`).

## 4. Held-out benchmark
Using the raw-CFD20 reproducible labels, I reran the S07c-style run-held-out benchmark. Metrics use run-bootstrap 95% CIs over out-of-fold predictions:

| method                      |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high | note                                                      |       brier |   brier_ci_low |   brier_ci_high |
|:----------------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|:----------------------------------------------------------|------------:|---------------:|----------------:|
| traditional_span_q_template |  0.912455 |         0.884565 |          0.928422 |            0.960624 |                   0.914884 |                    0.976462 | Uses downstream span; overlaps weak-label definition      | nan         |   nan          |    nan          |
| traditional_q_template_only |  0.716918 |         0.690092 |          0.739703 |            0.88189  |                   0.814855 |                    0.908382 | No timing-span feature                                    | nan         |   nan          |    nan          |
| rf_clean_timing             |  0.993618 |         0.991553 |          0.995308 |            0.997848 |                   0.996007 |                    0.998577 | RF excludes timing spans, pair residuals, run, and sample |   0.0260003 |     0.023482   |      0.029358   |
| leaky_rf_control            |  1        |         1        |          1        |            1        |                   1        |                    1        | RF with forbidden label-defining timing spans             |   0.0023351 |     0.00208224 |      0.00263331 |

The strong traditional method uses downstream span plus q_template and is label-overlapping by construction. The de-leaked traditional method uses q_template only. The ML method is a random forest on amplitude/shape/q_template features, excluding run, sample, timing spans, pair residuals, and B2 displacement.

## 5. Leakage hunt
| check                              | value              | pass   |
|:-----------------------------------|:-------------------|:-------|
| rf_forbidden_feature_intersection  |                    | True   |
| leaky_control_auc_is_ceiling       | 0.9999999999999999 | True   |
| historical_source_table_found      | 0                  | False  |
| definition_grid_exact_target_match | 0                  | False  |

The near-perfect leaky control confirms that including label-defining timing quantities trivially solves the weak-label task. The admissible RF still looks very strong, so I treat it as a proxy ranking only, not independent truth.

## 6. Verdict
The App.A 12,147 labelled-event count should be retired from detector-result status unless an external derived label table is recovered. It is not reproduced by the documented raw definition, no source table is present in this repo, and a broad raw timing-definition scan found no exact match. The supported replacement statement is: raw HRDv CFD20 labels produce 9897 labelled events (7583 clean, 2314 violating) in the documented 32-run scope.

## 7. Follow-ups
- S07e: archive provenance search for the App.A training table outside this repo; expected information gain: determines whether 12,147 came from a lost derived table rather than raw HRDv.
- S03d: independent timing-tail validation of q_template-only clean-timing cuts; expected information gain: replaces App.A weak labels with an external held-out timing-tail gate.

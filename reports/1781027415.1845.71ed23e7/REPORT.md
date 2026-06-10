# S03f: q_template-only plus external timing-tail validation

- **Ticket:** `1781027415.1845.71ed23e7`
- **Worker:** `testbeam-laptop-4`
- **Question:** can q_template-only plus external held-out timing-tail validation replace the unrecovered App.A weak-label table for S03/S04/S09 consumers?
- **Inputs:** raw B-stack `HRDv` ROOT and the S01 q_template table; checksums are in `input_sha256.csv`.

## Raw ROOT Reproduction First

| quantity        | documented | raw_reconstructed | delta | matches |
| --------------- | ---------- | ----------------- | ----- | ------- |
| labelled_events | 12147      | 9897              | -2250 | False   |
| clean           | 10636      | 7583              | -3053 | False   |
| violating       | 1511       | 2314              | 803   | False   |

The current raw `HRDv` CFD20 reconstruction gives `9897` labelled events (`7583` clean, `2314` violating), not the documented App.A tuple `12,147` (`10,636` clean, `1,511` violating). The downstream-ge2 candidate population has `15354` events, with `5457` ambiguous events excluded from clean-vs-violating scoring.

## Run-Held-Out Benchmark

Rows below use held-out run predictions with run-bootstrap 95% CIs. The traditional method is q_template-only: each fold chooses only a q_template event score and retention gate from train runs, then applies it to held-out runs. The ML method is a random forest using q_template, amplitude, hit-count, and waveform-shape summaries; it excludes run/event ids and all timing-tail defining columns. The two ablation RF rows are leakage-hunt probes, not replacement candidates.

| method                            | target                               | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | external_non_tail_auc | external_non_tail_auc_ci_low | external_non_tail_auc_ci_high | brier      | brier_ci_low | brier_ci_high |
| --------------------------------- | ------------------------------------ | -------- | -------------- | --------------- | ----------------- | ------------------------ | ------------------------- | --------------------- | ---------------------------- | ----------------------------- | ---------- | ------------ | ------------- |
| traditional_q_template_only       | raw_reconstructed_clean_vs_violating | 0.660094 | 0.608053       | 0.704357        | 0.862194          | 0.743027                 | 0.914259                  | 0.660094              | 0.6099                       | 0.699072                      |            |              |               |
| ml_shape_q_random_forest          | raw_reconstructed_clean_vs_violating | 0.993737 | 0.991691       | 0.995454        | 0.997896          | 0.995967                 | 0.998671                  | 0.993737              | 0.991713                     | 0.995508                      | 0.0253607  | 0.0228169    | 0.0286468     |
| ablation_q_amp_random_forest      | raw_reconstructed_clean_vs_violating | 0.964853 | 0.954644       | 0.970366        | 0.987827          | 0.970814                 | 0.99248                   | 0.964853              | 0.953627                     | 0.970234                      | 0.0705684  | 0.0583723    | 0.0896569     |
| ablation_shape_no_q_random_forest | raw_reconstructed_clean_vs_violating | 0.984081 | 0.97867        | 0.988852        | 0.99382           | 0.989869                 | 0.995655                  | 0.984081              | 0.978533                     | 0.988993                      | 0.0413895  | 0.0376507    | 0.0451102     |
| leaky_timing_control              | raw_reconstructed_clean_vs_violating | 1        | 1              | 1               | 1                 | 1                        | 1                         | 1                     | 1                            | 1                             | 0.00267843 | 0.00240391   | 0.00301273    |

## External Timing-Tail Gate Validation

The q_template-only gate is evaluated on independent held-out timing-tail gates, not on the unrecovered App.A table.

| subset                   | n    | fraction | external_gross_tail_rate | external_gross_tail_ci_low | external_gross_tail_ci_high | external_clean_rate | external_clean_ci_low | external_clean_ci_high |
| ------------------------ | ---- | -------- | ------------------------ | -------------------------- | --------------------------- | ------------------- | --------------------- | ---------------------- |
| q_template_gate_accepted | 5728 | 0.578761 | 0.141236                 | 0.0806593                  | 0.271386                    | 0.858764            | 0.737164              | 0.918558               |
| q_template_gate_rejected | 4169 | 0.421239 | 0.360998                 | 0.290359                   | 0.47924                     | 0.639002            | 0.523202              | 0.718054               |

Accepted q_template-gate events have gross-tail rate `0.1412` versus `0.3610` for rejected events, and clean-gate rate `0.8588` versus `0.6390`.

## Leakage Hunt

| check                                | value       | flag  | note                                                                                                                |
| ------------------------------------ | ----------- | ----- | ------------------------------------------------------------------------------------------------------------------- |
| raw_count_matches_documented_appa    | False       | False | Flag true would mean the unrecovered App.A tuple reproduced exactly; it does not.                                   |
| ml_forbidden_feature_intersection    |             | False | ML excludes run/event identifiers and timing-tail label-defining columns.                                           |
| leaky_timing_control_near_ceiling    | 1           | True  | Expected leakage ceiling when timing spans and B2 displacement are supplied.                                        |
| ml_too_good_vs_qtemplate             | 0.333643    | True  | Would trigger extra suspicion if non-timing ML nearly recovers clean labels.                                        |
| shape_no_q_ablation_near_full_ml     | -0.00965546 | True  | If true, high ML performance survives without q_template and is likely same-waveform timing-tail proxy information. |
| q_amp_ablation_vs_qtemplate          | 0.304759    | True  | Checks whether amplitude/hit-count structure, not q_template alone, carries most of the ML gain.                    |
| qtemplate_unmatched_candidate_events | 2           | False | Events with no S01 q_template match before median fill.                                                             |

The leaky timing control is intentionally near the ceiling because it receives downstream span, all-span, and B2 displacement. The production ML feature set has no timing-span, displacement, run, or event identifier columns. The no-q_template waveform ablation is the critical same-waveform proxy check: if it remains near the full ML score, the high ML result is not independent support for replacing App.A; it is largely recovery of timing-tail information from the same pulse shapes used by CFD timing.

## Finding

Verdict: `do_not_replace_appa_with_qtemplate_only`. The q_template-only gate is useful as a conservative event-quality gate when paired with held-out timing-tail validation, but it should not recreate the unrecovered App.A weak-label probability table. S03/S04/S09 consumers can use the gate plus the external validation rates, not the historical 12,147-row label source.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.py --config configs/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.json
```

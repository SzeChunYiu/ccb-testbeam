# S11h: blinded ML-only gallery expansion

- **Ticket:** `1781145663.1956.09ad79dc`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-07-09
- **Depends on:** S11f frozen event scores, S11b raw B-stack ROOT loader, S10f morphology gallery.
- **Inputs:** `data/root/root`, `reports/1781046807.583.64755f71__s11f_two_pulse_method_disagreement_taxonomy`, `reports/1781030296.1752.37d47174/morphology_scores.csv`.
- **Config:** `configs/s11h_1781145663_1956_09ad79dc_blinded_ml_only_gallery_expansion.json`
- **Git commit:** `55865bd941438ec6063357eb98d8c92ef3ae8d66`

## 1. Question

Are the S11f consensus ML-only high-current rows that carry a positive run-bootstrap excess genuine two-pulse morphology or detector-shape artifacts? The analysis freezes the S11f bounded-fit, ridge, gradient-boosted-tree, MLP, 1D-CNN, and consensus scores. These scores are used for selection and benchmarking only; the blinded morphology labels are derived from external gallery labels where available plus traditional fit and shape diagnostics that do not inspect learned probabilities.

## 2. Raw-ROOT Reproduction Gate

The S11b raw loader was rerun on the local ROOT files and rebuilt 5838 low-current selected events and 237295 high-current selected events before any S11h gallery scoring.

| quantity                                 | report_value | reproduced | delta      | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| low_2nA multi_stave_per_selected_event   | 0.0156       | 0.015588   | -1.247e-05 | 0.0015    | True |
| low_2nA three_stave_per_selected_event   | 0.0041       | 0.004111   | 1.0997e-05 | 0.0015    | True |
| low_2nA downstream_per_selected_event    | 0.0231       | 0.023124   | 2.4358e-05 | 0.0015    | True |
| high_20nA multi_stave_per_selected_event | 0.0268       | 0.026806   | 6.296e-06  | 0.0015    | True |
| high_20nA three_stave_per_selected_event | 0.0085       | 0.0085379  | 3.7896e-05 | 0.0015    | True |
| high_20nA downstream_per_selected_event  | 0.0334       | 0.033414   | 1.4105e-05 | 0.0015    | True |

## 3. Sampling Design

Let `G_i` denote the gallery arm. The high arm is

`G_i = high_ml_only` iff the frozen S11f consensus-abstention action accepted row `i`, the frozen traditional bounded fit did not accept it, and the row came from a 20 nA source run.

For each high-arm row, a low-current control was chosen from the same S11f stratum when possible, otherwise from the nearest amplitude/topology cell by log-amplitude and log-lowering distance. The final gallery order is blinded by a random `S11H-*` identifier. Bootstrap resampling uses source runs within arm as the block unit.

| gallery_arm         | n   | runs                                | two_pulse_like_rate | artifact_like_rate | prior_gallery_overlap |
| ------------------- | --- | ----------------------------------- | ------------------- | ------------------ | --------------------- |
| high_ml_only        | 303 | 44,45,48,49,50,51,52,53,54,55,56,57 | 0.0033003           | 0.93069            | 0.61056               |
| matched_low_control | 303 | 46,47                               | 0.059406            | 0.92739            | 0.9538                |

Primary blinded-label high-minus-control two-pulse-like delta: **-0.05611** [-0.14035, -0.03373] over 800 source-run bootstrap draws.

## 4. Blinded Label Model

Three deterministic reviewer views emulate blinded morphology review. Reviewer A accepts an external S10f two-pulse-like label when present or a clean bounded two-pulse fit. Reviewer B requires a bounded fit plus downstream topology or sufficient amplitude. Reviewer C requires non-pathological residual shape and a plausible 10-70 ns separation. Artifact votes are assigned by external artifact labels, early-pathology topology, extreme one-pulse residuals, strongly negative late residuals, or very large adaptive lowering. The final label is

`y_i = 1{V_i >= 2 and A_i <= 1}`,

where `V_i` is the number of two-pulse reviewer votes and `A_i` is the artifact vote count. This is a morphology-review endpoint, not a truth-level decomposition.

## 5. Method Benchmark

Every method is evaluated as a frozen binary action against the blinded labels. Precision is `TP/(TP+FP)`, recall is `TP/P`, artifact fraction is the blinded artifact rate among accepted rows, and topology-excess coverage is the method accepted high-minus-control contrast divided by the S11f matched downstream excess.

| method                        | precision | precision_ci_low | precision_ci_high | recall   | recall_ci_low | recall_ci_high | artifact_fraction | artifact_fraction_ci_low | artifact_fraction_ci_high | accepted_high_minus_control | accepted_high_minus_control_ci_low | accepted_high_minus_control_ci_high | topology_excess_coverage | selection_score |
| ----------------------------- | --------- | ---------------- | ----------------- | -------- | ------------- | -------------- | ----------------- | ------------------------ | ------------------------- | --------------------------- | ---------------------------------- | ----------------------------------- | ------------------------ | --------------- |
| traditional_template_fit      | 0.51852   | 0.5              | 0.52632           | 0.73684  | 0.42105       | 1              | 0.59259           | 0.5                      | 0.63158                   | -0.089109                   | -0.14035                           | -0.077236                           | -4.4008                  | 0.32721         |
| cnn_1d_dual_head              | 0.04      | 0                | 0.33333           | 0.052632 | 0             | 0.15789        | 0.72              | 0.36288                  | 0.81818                   | 0.082508                    | 0.015476                           | 0.21906                             | 4.0748                   | -0.030545       |
| mlp                           | 0.035382  | 0.02985          | 0.045921          | 1        | 1             | 1              | 0.91993           | 0.87599                  | 0.94445                   | 0.22772                     | 0                                  | 0.28049                             | 11.247                   | -0.08901        |
| ridge_linear                  | 0.010101  | 0                | 0.029703          | 0.052632 | 0             | 0.15789        | 0.91919           | 0.85292                  | 0.97562                   | 0.22112                     | 0.1187                             | 0.33054                             | 10.921                   | -0.1477         |
| gradient_boosted_trees        | 0.0032258 | 0                | 0.01031           | 0.052632 | 0             | 0.15789        | 0.93226           | 0.89849                  | 0.96025                   | 0.9769                      | 0.96491                            | 0.97967                             | 48.246                   | -0.16586        |
| consensus_abstention_ensemble | 0.0030769 | 0                | 0.0095854         | 0.052632 | 0             | 0.14286        | 0.93538           | 0.90106                  | 0.96154                   | 0.92739                     | 0.73684                            | 0.97154                             | 45.801                   | -0.16742        |

Named winner: **traditional_template_fit** with selection score 0.32721.

## 6. Leakage and Systematics

| check                              | value   | pass | note                                                                                                             |
| ---------------------------------- | ------- | ---- | ---------------------------------------------------------------------------------------------------------------- |
| raw_root_reproduction_pass         | 1       | True | S10 topology fractions rebuilt directly from local ROOT files.                                                   |
| all_required_methods_present       | 1       | True | Traditional, ridge, GBT, MLP, 1D-CNN, and consensus actions are present.                                         |
| labels_do_not_use_ml_probabilities | 1       | True | Blinded label columns are functions of external labels, bounded-fit diagnostics, and shape/topology fields only. |
| source_run_bootstrap_used          | 800     | True | Intervals resample source runs within gallery arm.                                                               |
| prior_gallery_overlap_not_complete | 0.78218 | True | External S10f labels are used where available but S11h is an expanded deterministic blinded gallery.             |

- The label construction intentionally excludes GBT, MLP, CNN, ridge, and consensus probabilities.
- Run-block bootstrap intervals cover run-to-run variation inside the selected support, not the full uncertainty of human morphology adjudication.
- The S10f gallery overlap is incomplete; external labels stabilize some rows but do not make this a complete hand-scan.
- The matched controls are low-current rows from only runs 46 and 47, so low-arm bootstrap uncertainty is necessarily coarse.
- Because the high arm is selected from consensus ML-only rows, this is a validation of that support region rather than a population-wide pile-up-rate estimate.

## 7. Conclusion

The expanded blinded gallery does not turn the S11f consensus ML-only excess into a clean two-pulse sample: the high-minus-control blinded two-pulse-like delta is -0.0561 [-0.1404, -0.0337], while artifact-like labels remain common. The best frozen action is traditional_template_fit with precision 0.519, recall 0.737, and artifact fraction 0.593; therefore the S11f caveat survives as support-dependent morphology rather than a validated clean pile-up recovery.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11h_1781145663_1956_09ad79dc_blinded_ml_only_gallery_expansion.py --config configs/s11h_1781145663_1956_09ad79dc_blinded_ml_only_gallery_expansion.json
```

Runtime in this run was 120.31 s. Outputs include `result.json`, `manifest.json`, `raw_root_reproduction.csv`, `blinded_gallery.csv`, `method_summary.csv`, `arm_summary.csv`, `bootstrap_delta_summary.json`, `leakage_checks.csv`, and figures.

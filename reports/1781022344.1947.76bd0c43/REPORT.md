# S02f: composition-stable timing-tail closure cut

**Ticket:** `1781022344.1947.76bd0c43`

## Reproduction first
The raw B-stack ROOT files were scanned before any timing labels, model fits, or prior report outputs were consumed. The S00/S02 selected-pulse gates reproduced exactly.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Pre-registered split and cut rule
Training runs were all configured B-stack runs except held-out runs `42, 57, 64, 65`. The fixed residual center was the train-pair median `-1.185456 ns`; the tail threshold was the train-run 95th percentile of absolute residuals, `4.007616 ns`.
Candidate cuts were registered on train runs only: deterministic P09a class exclusions, ML pair-risk quantiles, and class-or-ML hybrids. The selected cut minimized train tail rate subject to median log-charge drift <= `0.02`, max pair-composition drift <= `0.01`, and kept-pair fraction >= `0.8`.

Selected pre-registered action: `hybrid_baseline_excursion_or_ml_q0p9`.

## Held-out comparison
| action                                          | family      |   n_pairs |   tail_rate |   full_rms_ns |   q95_abs_ns |   kept_pair_fraction |   abs_median_log_amp_delta |   max_pair_composition_drift | all_constraints_pass   |
|:------------------------------------------------|:------------|----------:|------------:|--------------:|-------------:|---------------------:|---------------------------:|-----------------------------:|:-----------------------|
| baseline                                        | baseline    |      2178 |   0.0518825 |       4.27983 |      4.04776 |             1        |                0           |                  0           | True                   |
| p09a_exclude_novel_broad_template_mismatch      | p09a_class  |      2177 |   0.0514469 |       4.24205 |      4.04324 |             0.999541 |                4.79317e-05 |                  0.000183275 | True                   |
| p09a_exclude_dropout                            | p09a_class  |      2178 |   0.0518825 |       4.27983 |      4.04776 |             1        |                0           |                  0           | True                   |
| p09a_exclude_baseline_excursion                 | p09a_class  |      2172 |   0.0520258 |       4.28305 |      4.05271 |             0.997245 |                0.000143809 |                  0.000181372 | True                   |
| p09a_exclude_pileup_or_long_tail                | p09a_class  |      2132 |   0.0520638 |       4.31736 |      4.05271 |             0.97888  |                0.00470843  |                  0.00311748  | True                   |
| p09a_exclude_novel_early_pretrigger             | p09a_class  |      2123 |   0.0522845 |       4.26014 |      4.06015 |             0.974747 |                0.00540167  |                  0.00261922  | True                   |
| p09a_exclude_novel_delayed_peak                 | p09a_class  |      1833 |   0.0529187 |       3.56532 |      4.06317 |             0.841598 |                0.000527111 |                  0.00423142  | True                   |
| ml_pair_risk_q0p9                               | ml_quantile |      2002 |   0.036963  |       2.47446 |      3.70896 |             0.919192 |                0.0140881   |                  0.00630178  | True                   |
| ml_pair_risk_q0p95                              | ml_quantile |      2100 |   0.0433333 |       3.561   |      3.84446 |             0.964187 |                0.00773495  |                  0.00471337  | True                   |
| ml_pair_risk_q0p975                             | ml_quantile |      2150 |   0.0488372 |       3.80942 |      3.98289 |             0.987144 |                0.00229808  |                  0.00202234  | True                   |
| hybrid_pileup_or_long_tail_or_ml_q0p9           | hybrid      |      1957 |   0.036791  |       2.48749 |      3.71057 |             0.898531 |                0.0119591   |                  0.0071714   | True                   |
| hybrid_dropout_or_ml_q0p9                       | hybrid      |      2002 |   0.036963  |       2.47446 |      3.70896 |             0.919192 |                0.0140881   |                  0.00630178  | True                   |
| hybrid_novel_broad_template_mismatch_or_ml_q0p9 | hybrid      |      2002 |   0.036963  |       2.47446 |      3.70896 |             0.919192 |                0.0140881   |                  0.00630178  | True                   |
| hybrid_novel_early_pretrigger_or_ml_q0p9        | hybrid      |      1947 |   0.03698   |       2.36542 |      3.71359 |             0.893939 |                0.020542    |                  0.00828003  | False                  |
| hybrid_baseline_excursion_or_ml_q0p9            | hybrid      |      1996 |   0.0370741 |       2.47313 |      3.71087 |             0.916437 |                0.0140881   |                  0.00639387  | True                   |
| hybrid_novel_delayed_peak_or_ml_q0p9            | hybrid      |      1681 |   0.0386675 |       2.58361 |      3.76115 |             0.771809 |                0.0140408   |                  0.0053108   | False                  |
| hybrid_pileup_or_long_tail_or_ml_q0p95          | hybrid      |      2054 |   0.0433301 |       3.59018 |      3.84587 |             0.943067 |                0.00411366  |                  0.00594419  | True                   |
| hybrid_dropout_or_ml_q0p95                      | hybrid      |      2100 |   0.0433333 |       3.561   |      3.84446 |             0.964187 |                0.00773495  |                  0.00471337  | True                   |

The selected held-out cut changed tail rate from `0.0519` to `0.0371`, q95 from `4.048` to `3.711 ns`, and kept `0.916` of pairs. Its held-out charge drift was `0.01409` and max pair-composition drift was `0.00639`.

## Held-out run bootstrap CIs
CIs resample held-out runs with replacement.

| action                                     | family      | metric                     |     ci_low |     ci_high |
|:-------------------------------------------|:------------|:---------------------------|-----------:|------------:|
| baseline                                   | baseline    | tail_rate                  | 0.0420757  | 0.0566553   |
| baseline                                   | baseline    | full_rms_ns                | 2.38042    | 5.15695     |
| baseline                                   | baseline    | q95_abs_ns                 | 3.85749    | 4.15262     |
| baseline                                   | baseline    | sigma68_ns                 | 1.97073    | 2.06891     |
| baseline                                   | baseline    | kept_pair_fraction         | 1          | 1           |
| baseline                                   | baseline    | abs_median_log_amp_delta   | 0          | 0           |
| baseline                                   | baseline    | max_pair_composition_drift | 0          | 0           |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | tail_rate                  | 0.0420757  | 0.0560109   |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | full_rms_ns                | 2.38042    | 4.94359     |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | q95_abs_ns                 | 3.85749    | 4.12652     |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | sigma68_ns                 | 1.97073    | 2.06891     |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | kept_pair_fraction         | 0.999159   | 1           |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | abs_median_log_amp_delta   | 0          | 0.000594236 |
| p09a_exclude_novel_broad_template_mismatch | p09a_class  | max_pair_composition_drift | 0          | 0.000348547 |
| ml_pair_risk_q0p9                          | ml_quantile | tail_rate                  | 0.0309278  | 0.0452646   |
| ml_pair_risk_q0p9                          | ml_quantile | full_rms_ns                | 1.93146    | 2.84406     |
| ml_pair_risk_q0p9                          | ml_quantile | q95_abs_ns                 | 3.62463    | 3.79582     |
| ml_pair_risk_q0p9                          | ml_quantile | sigma68_ns                 | 1.89993    | 1.9842      |
| ml_pair_risk_q0p9                          | ml_quantile | kept_pair_fraction         | 0.897689   | 0.955214    |
| ml_pair_risk_q0p9                          | ml_quantile | abs_median_log_amp_delta   | 0.00734614 | 0.0241548   |
| ml_pair_risk_q0p9                          | ml_quantile | max_pair_composition_drift | 0.00557356 | 0.00880561  |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | tail_rate                  | 0.0310192  | 0.0439259   |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | full_rms_ns                | 1.92607    | 2.84414     |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | q95_abs_ns                 | 3.62463    | 3.79331     |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | sigma68_ns                 | 1.87882    | 1.97453     |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | kept_pair_fraction         | 0.895434   | 0.953877    |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | abs_median_log_amp_delta   | 0.00813948 | 0.0235328   |
| hybrid_baseline_excursion_or_ml_q0p9       | hybrid      | max_pair_composition_drift | 0.00499873 | 0.00894972  |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | tail_rate                  | 0.0292308  | 0.0436917   |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | full_rms_ns                | 1.9338     | 2.85479     |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | q95_abs_ns                 | 3.60911    | 3.79331     |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | sigma68_ns                 | 1.90717    | 1.97547     |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | kept_pair_fraction         | 0.885899   | 0.915639    |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | abs_median_log_amp_delta   | 0.00694594 | 0.023339    |
| hybrid_pileup_or_long_tail_or_ml_q0p9      | hybrid      | max_pair_composition_drift | 0.00152799 | 0.0116042   |

## ML diagnostics
The RandomForest tail-risk model used P09a scores/taxa and train-fit PCA waveform latents, with no run id, event id, source index, or stave id features.

| split                          |    n |   positive_rate |   average_precision |    roc_auc | selection                   |   n_selected |   selected_fraction |   precision |   baseline_tail_pulse_rate |
|:-------------------------------|-----:|----------------:|--------------------:|-----------:|:----------------------------|-------------:|--------------------:|------------:|---------------------------:|
| heldout_all                    | 6187 |       0.0341038 |            0.101401 |   0.698996 | nan                         |          nan |         nan         |  nan        |                nan         |
| heldout_fixed_threshold_scores | 6187 |       0.0341038 |            0.101401 |   0.698996 | fixed_train_pulse_threshold |          706 |           0.11411   |    0.103399 |                  0.0341038 |
| heldout_pair_q0p9              | 2178 |       0.0518825 |          nan        | nan        | pair_max_score_q0.9         |          176 |           0.0808081 |    0.221591 |                  0.0341038 |
| heldout_pair_q0p95             | 2178 |       0.0518825 |          nan        | nan        | pair_max_score_q0.95        |           78 |           0.0358127 |    0.282051 |                  0.0341038 |
| heldout_pair_q0p975            | 2178 |       0.0518825 |          nan        | nan        | pair_max_score_q0.975       |           28 |           0.0128558 |    0.285714 |                  0.0341038 |

## Leakage checks
| check                                        |     value | pass   | note                                                                          |
|:---------------------------------------------|----------:|:-------|:------------------------------------------------------------------------------|
| train_heldout_run_overlap                    | 0         | True   | run-disjoint split                                                            |
| train_heldout_event_id_overlap               | 0         | True   | event ids include run and raw event counters                                  |
| model_features_include_run_event_or_stave_id | 0         | True   | none                                                                          |
| rounded_waveform_hash_overlap_train_heldout  | 0         | True   | normalized waveforms rounded to 1e-3                                          |
| stave_only_proxy_average_precision           | 0.0465062 | True   | proxy should underperform full no-id model                                    |
| suspicious_result_triggered_extra_checks     | 0         | True   | triggered if selected cut reduces heldout tail rate by >50 pct or below 1 pct |

## Verdict
A composition-stable timing-tail cut is possible, but the constraints matter. Deterministic P09a class exclusions alone barely move the held-out tail, while the ML q90 pair-risk cut supplies most of the mitigation and remains inside the configured charge and pair-mix limits on this split. The selected hybrid is train-registered rather than held-out-picked; its improvement is useful but modest, so it should be treated as a cut recommendation rather than a new calibration model.

## Provenance
Runtime was `448.0 s` on `billy`. `manifest.json` records input, code, and output hashes.

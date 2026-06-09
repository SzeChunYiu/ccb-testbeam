# S11b: real high-current two-pulse recovery

- **Ticket:** `1781010611.1197.028b141a`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** high-current events are predicted from low-current template/ML training only; low-current control events leave their own source run out. CIs resample held-out source runs within current group.

## Reproduction first

The S10c raw-ROOT gate was reproduced before the amplitude study. Downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA; all six documented topology fractions pass the +/-0.0015 tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Strata and event scoring

The S10c strata are reused exactly: maximum selected-pulse amplitude, S16 adaptive-lowering bin, and P02-style topology. Full raw-ROOT counts define the matched-stratum weights; a capped within-run/within-stratum sample of 140 events supplies waveform-level scores. 8 matched strata pass the low/high count floor.

## Traditional method

For each held-out run, median empirical templates are built from low-current source runs only, excluding the held-out run when it is a low-current control. A bounded two-pulse fit scans first-pulse timing and pulse separation, solves primary amplitude, secondary amplitude, and baseline by least squares, and reports the secondary fraction A2/(A1+A2).

Matched high-minus-low secondary fraction: **0.01806** with run-bootstrap 95% CI **[-0.01679, 0.05414]**.

| amp_bin       | baseline_bin       | p02_topology        |   low_n_scored |   high_n_scored |   low_mean |   high_mean |   high_minus_low |   match_weight |
|:--------------|:-------------------|:--------------------|---------------:|----------------:|-----------:|------------:|-----------------:|---------------:|
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |            280 |            1680 |  0.147448  | 0.180387    |      0.0329397   |     0.519603   |
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |            280 |            1680 |  0.3599    | 0.358862    |     -0.00103783  |     0.293605   |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |            239 |            1680 |  0.574618  | 0.5848      |      0.0101819   |     0.135738   |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |            132 |            1637 |  0         | 0.000729566 |      0.000729566 |     0.0230005  |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |             51 |            1412 |  0.0102562 | 0.00730858  |     -0.00294763  |     0.00888657 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |             45 |            1151 |  0.140652  | 0.0845733   |     -0.0560788   |     0.00784109 |
| amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |             38 |             820 |  0.517477  | 0.509593    |     -0.00788448  |     0.00662136 |
| amp_ge_4500   | s16_large_lowering | p02_broad_late      |             27 |            1465 |  0.0408047 | 0.120086    |      0.0792811   |     0.00470465 |

## ML residual diagnostic

The ML method is a compact run-held-out random-forest classifier/regressor trained on synthetic two-pulse overlays made only from low-current training-run raw pulses. Features are normalized waveform samples and one-pulse template residual summaries; identifiers and current labels are excluded.

ML secondary-fraction high-minus-low: **0.00437** [-0.00138, 0.01206]. ML overlap-score high-minus-low: **0.02007** [-0.01143, 0.05186]. Mean synthetic held-out AUC is 0.926; shuffled-label AUC is 0.518.

## Leakage review

| check                                              |    value | flag   | note                                                                                             |
|:---------------------------------------------------|---------:|:-------|:-------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training | 1        | False  | Each source run is scored only by templates and ML trained with that run removed.                |
| identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.     |
| synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used to generate synthetic ML training overlays.         |
| mean_synthetic_holdout_auc                         | 0.925521 | False  | Very high synthetic AUC would be suspicious because held-out runs contain independent residuals. |
| mean_shuffled_label_synthetic_auc                  | 0.518107 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                    |
| actual_current_auc_from_ml_secondary_fraction      | 0.567954 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                   |

## Conclusion

Applying the S11a-style low-current template baseline to real high-current candidate windows gives a matched high-current minus low-current secondary fraction of 0.01806 [-0.01679, 0.05414] from the traditional template fit. The ML residual diagnostic gives 0.00437 [-0.00138, 0.01206] for secondary fraction and 0.02007 [-0.01143, 0.05186] for overlap score. The largest traditional positive stratum is amp_ge_4500 / s16_large_lowering / p02_broad_late. Leakage probes do not flag identifier or source-run leakage, but the estimate remains a pulse-shape diagnostic rather than a truth-labelled pile-up decomposition.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stratum_table.csv`, `method_summary.csv`, `method_stratum_summary.csv`, `sampled_event_scores.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this folder.

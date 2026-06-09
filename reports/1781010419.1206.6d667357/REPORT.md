# S10d: two-pulse template pile-up amplitude by stratum

- **Ticket:** `1781010419.1206.6d667357`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** every scored event is predicted by a model/template library with that event's source run held out; CIs resample held-out source runs within current group.

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

For each held-out run, median empirical templates are built from all other runs. A bounded two-pulse fit scans first-pulse timing and pulse separation, solves primary amplitude, secondary amplitude, and baseline by least squares, and reports the secondary fraction A2/(A1+A2).

Matched high-minus-low secondary fraction: **0.03159** with run-bootstrap 95% CI **[0.01889, 0.04396]**.

| amp_bin       | baseline_bin       | p02_topology        |   low_n_scored |   high_n_scored |   low_mean |   high_mean |   high_minus_low |   match_weight |
|:--------------|:-------------------|:--------------------|---------------:|----------------:|-----------:|------------:|-----------------:|---------------:|
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |            280 |            1680 | 0.205179   | 0.243038    |      0.0378593   |     0.519603   |
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |            280 |            1680 | 0.466538   | 0.501131    |      0.0345928   |     0.293605   |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |            239 |            1680 | 0.573677   | 0.584917    |      0.0112398   |     0.135738   |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |            132 |            1637 | 0          | 0.000341321 |      0.000341321 |     0.0230005  |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |             51 |            1412 | 0.00242648 | 0.0136965   |      0.0112701   |     0.00888657 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |             45 |            1151 | 0.0637277  | 0.0765413   |      0.0128136   |     0.00784109 |
| amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |             38 |             820 | 0.559832   | 0.516421    |     -0.0434109   |     0.00662136 |
| amp_ge_4500   | s16_large_lowering | p02_broad_late      |             27 |            1465 | 0.0298381  | 0.0957884   |      0.0659503   |     0.00470465 |

## ML residual diagnostic

The ML method is a run-held-out random-forest classifier/regressor trained on synthetic two-pulse overlays made only from training-run raw pulses. Features are normalized waveform samples and one-pulse template residual summaries; identifiers and current labels are excluded.

ML secondary-fraction high-minus-low: **0.00729** [0.00349, 0.01190]. ML overlap-score high-minus-low: **0.02446** [0.00678, 0.04182]. Mean synthetic held-out AUC is 0.946; shuffled-label AUC is 0.505.

## Leakage review

| check                                              |    value | flag   | note                                                                                             |
|:---------------------------------------------------|---------:|:-------|:-------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training | 1        | False  | Each source run is scored only by templates and ML trained with that run removed.                |
| identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.     |
| synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used to generate synthetic ML training overlays.         |
| mean_synthetic_holdout_auc                         | 0.946127 | False  | Very high synthetic AUC would be suspicious because held-out runs contain independent residuals. |
| mean_shuffled_label_synthetic_auc                  | 0.505297 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                    |
| actual_current_auc_from_ml_secondary_fraction      | 0.602726 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                   |

## Conclusion

Replacing the S10c binary downstream label with a constrained two-pulse amplitude estimate gives a matched high-current minus low-current secondary fraction of 0.03159 [0.01889, 0.04396] from the traditional template fit. The ML residual diagnostic gives 0.00729 [0.00349, 0.01190] for secondary fraction and 0.02446 [0.00678, 0.04182] for overlap score. The largest traditional positive stratum is amp_ge_4500 / s16_large_lowering / p02_broad_late. Leakage probes do not flag identifier or source-run leakage, but the estimate remains a pulse-shape diagnostic rather than a truth-labelled pile-up decomposition.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stratum_table.csv`, `method_summary.csv`, `method_stratum_summary.csv`, `sampled_event_scores.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this folder.

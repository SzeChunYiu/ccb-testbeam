# S10f: P09a anomaly labels in S10e charge strata

- **Ticket:** `1781020051.1266.2a535acd`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** all ML predictions leave out the source run; intervals bootstrap held-out runs within current group.

## Reproduction first

The S10e P04/P07 charge-stratified model was rebuilt from raw ROOT before adding anomaly labels. All documented S10/S10c topology gates pass, and the reproduced uncorrected/P07 downstream excess values match the S10e reference within numerical precision.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Traditional propagation

Adding deterministic P09a taxon labels to the P04 charge x S16 lowering x P07 saturation strata gives uncorrected downstream excess **0.00412** [0.00227, 0.00689] versus the S10e base **0.00676** [0.00527, 0.00882]. P07-corrected taxon strata give **0.00412** [0.00205, 0.00649] versus base **0.00676** [0.00554, 0.00873].

| base_strata   | taxon_strata                  | metric                                |   base_value |   taxon_value |   taxon_minus_base |   fractional_attenuation |   base_ci_low |   base_ci_high |   taxon_ci_low |   taxon_ci_high |   base_n_strata |   taxon_n_strata |
|:--------------|:------------------------------|:--------------------------------------|-------------:|--------------:|-------------------:|-------------------------:|--------------:|---------------:|---------------:|----------------:|----------------:|-----------------:|
| uncorrected   | uncorrected_plus_p09a_taxon   | downstream_high_minus_low             |   0.00676266 |    0.00412245 |       -0.00264021  |               0.39041    |    0.00526902 |     0.00881625 |     0.00226648 |      0.00688945 |               9 |               11 |
| p07_corrected | p07_corrected_plus_p09a_taxon | downstream_high_minus_low             |   0.00676254 |    0.00412237 |       -0.00264016  |               0.39041    |    0.00553784 |     0.00872798 |     0.00205291 |      0.006493   |               9 |               11 |
| uncorrected   | uncorrected_plus_p09a_taxon   | p04_duplicate_charge_median_log_shift |   0.0476435  |    0.0481128  |        0.000469287 |              -0.00984997 |    0.023482   |     0.0568662  |     0.0237616  |      0.0604222  |               9 |               11 |
| p07_corrected | p07_corrected_plus_p09a_taxon | p07_corrected_charge_median_log_shift |   0.0476112  |    0.0480778  |        0.000466601 |              -0.00980023 |    0.0204082  |     0.0579968  |     0.0232565  |      0.0614802  |               9 |               11 |

## ML propagation

The ML arm trains run-held-out downstream logistic and P04 duplicate-charge ridge models. The taxon model adds only P09a deterministic labels/booleans to the same charge-stratum features; run, event id, current label, and downstream target are excluded.

Run-held-out downstream residual high-minus-low changes from **-0.00511** [-0.01190, 0.00241] without taxa to **0.00122** [-0.00635, 0.00901] with taxa. P04 log-charge residual high-minus-low changes from **0.01825** [0.01012, 0.02659] to **0.01240** [0.00307, 0.01947].

| metric                                        |       value |      ci_low |    ci_high |   n_strata |   n_bootstrap | bootstrap_unit           |
|:----------------------------------------------|------------:|------------:|-----------:|-----------:|--------------:|:-------------------------|
| observed_downstream_high_minus_low            |  0.00676266 |  0.00546277 | 0.00897061 |          9 |           400 | run_within_current_group |
| predicted_downstream_base_high_minus_low      |  0.0118727  |  0.00278896 | 0.0210118  |          9 |           400 | run_within_current_group |
| residual_downstream_base_high_minus_low       | -0.00511007 | -0.0119003  | 0.00241494 |          9 |           400 | run_within_current_group |
| predicted_downstream_taxon_high_minus_low     |  0.00553858 | -0.00436976 | 0.0160105  |          9 |           400 | run_within_current_group |
| residual_downstream_taxon_high_minus_low      |  0.00122408 | -0.00635074 | 0.00900608 |          9 |           400 | run_within_current_group |
| log_p04_charge_high_minus_low                 |  0.0357673  |  0.0202433  | 0.0510536  |          9 |           400 | run_within_current_group |
| predicted_log_p04_charge_base_high_minus_low  |  0.0175152  |  0.0105231  | 0.0242811  |          9 |           400 | run_within_current_group |
| residual_log_p04_charge_base_high_minus_low   |  0.0182521  |  0.0101196  | 0.0265941  |          9 |           400 | run_within_current_group |
| predicted_log_p04_charge_taxon_high_minus_low |  0.023364   |  0.0144888  | 0.0324126  |          9 |           400 | run_within_current_group |
| residual_log_p04_charge_taxon_high_minus_low  |  0.0124033  |  0.00306895 | 0.0194726  |          9 |           400 | run_within_current_group |

## Taxon prevalence

| group     | taxon                         |      n |   group_rate |   downstream_rate |   median_log_p04_charge |
|:----------|:------------------------------|-------:|-------------:|------------------:|------------------------:|
| high_20nA | unassigned_common             | 227905 |  0.960429    |        0.0277616  |                10.7335  |
| high_20nA | novel_early_pretrigger        |   4790 |  0.0201858   |        0.0480167  |                 6.96268 |
| high_20nA | baseline_excursion            |   1745 |  0.00735372  |        0.0269341  |                 7.82025 |
| high_20nA | novel_delayed_peak            |   1427 |  0.00601361  |        0.514366   |                 9.70701 |
| high_20nA | novel_broad_template_mismatch |    882 |  0.00371689  |        0.481859   |                10.9982  |
| high_20nA | pileup_or_long_tail           |    269 |  0.00113361  |        0.609665   |                 9.73683 |
| high_20nA | dropout                       |    264 |  0.00111254  |        0.00378788 |                 7.81003 |
| high_20nA | saturation                    |     13 |  5.47841e-05 |        0.0769231  |                11.1997  |
| low_2nA   | unassigned_common             |   5659 |  0.969339    |        0.0212052  |                10.4662  |
| low_2nA   | novel_early_pretrigger        |    112 |  0.0191847   |        0.0267857  |                 6.97255 |
| low_2nA   | baseline_excursion            |     39 |  0.00668037  |        0.025641   |                 7.63129 |
| low_2nA   | novel_delayed_peak            |     14 |  0.00239808  |        0.571429   |                 9.33587 |
| low_2nA   | dropout                       |      6 |  0.00102775  |        0          |                 7.78235 |
| low_2nA   | pileup_or_long_tail           |      5 |  0.000856458 |        0.4        |                10.0501  |
| low_2nA   | novel_broad_template_mismatch |      3 |  0.000513875 |        0.333333   |                10.9761  |

## Leakage review

| check                                                    |      value | flag   | note                                                                                                  |
|:---------------------------------------------------------|-----------:|:-------|:------------------------------------------------------------------------------------------------------|
| ml_heldout_runs_excluded_from_training                   | 1          | False  | Each ML prediction is made by a model trained without that source run.                                |
| identifier_current_and_downstream_excluded_from_features | 1          | False  | Feature matrices exclude run, event number, group/current, and downstream target.                     |
| p09a_labels_are_deterministic_taxa_not_ml_truth          | 1          | False  | Only P09a rule labels and booleans enter the propagation; P09a anomaly scores are not used as labels. |
| pred_downstream_base_current_auc                         | 0.580782   | False  | Flags if a propagated score almost identifies beam current.                                           |
| pred_downstream_taxon_current_auc                        | 0.568749   | False  | Flags if a propagated score almost identifies beam current.                                           |
| resid_log_p04_charge_base_current_auc                    | 0.57031    | False  | Flags if a propagated score almost identifies beam current.                                           |
| resid_log_p04_charge_taxon_current_auc                   | 0.555379   | False  | Flags if a propagated score almost identifies beam current.                                           |
| heldout_downstream_taxon_model_mean_auc                  | 0.882983   | False  | Flags an implausibly strong downstream classifier under run holdout.                                  |
| curated_taxon_rate_high_minus_low                        | 0.00890981 | False  | Flags if deterministic taxa nearly encode current by prevalence alone.                                |

## Conclusion

P09a deterministic anomaly taxa do not explain away the S10e matched current excess. Traditional P04 strata plus taxa give downstream high-minus-low 0.00412 [0.00227, 0.00689] against the base 0.00676; P07-corrected strata plus taxa give 0.00412 against the base 0.00676. The P04 duplicate-charge log shift changes from 0.04764 to 0.04811. Run-held-out ML gives the same direction: adding taxa changes downstream residual high-minus-low from -0.00511 to 0.00122 and P04 log-charge residual high-minus-low from 0.01825 to 0.01240. Leakage flags: 0. The taxa are useful explanatory handles, but they are not sufficient truth labels for the remaining matched downstream or charge-proxy excess.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, traditional, ML, taxon, and leakage CSVs are in this folder.

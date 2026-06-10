# S10g: P09b-adjudicated anomaly labels in S10e charge strata

- **Ticket:** `1781026939.1501.725b716d`
- **Worker:** `testbeam-laptop-4`
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

The base uncorrected matched-strata downstream high-minus-low is **0.00676** [0.00541, 0.00893]. Adding deterministic P09a labels gives **0.00412** [0.00209, 0.00609], while adding P09b adjudicated labels gives **0.00409** [0.00200, 0.00612]. With P07-corrected charge strata the corresponding values are base **0.00676**, P09a **0.00412**, and P09b **0.00409**.

| base_strata   | taxon_strata                        | metric                                |   base_value |   taxon_value |   taxon_minus_base |   fractional_attenuation |   base_ci_low |   base_ci_high |   taxon_ci_low |   taxon_ci_high |   base_n_strata |   taxon_n_strata |
|:--------------|:------------------------------------|:--------------------------------------|-------------:|--------------:|-------------------:|-------------------------:|--------------:|---------------:|---------------:|----------------:|----------------:|-----------------:|
| uncorrected   | uncorrected_plus_p09a_taxon         | downstream_high_minus_low             |   0.00676266 |    0.00412245 |       -0.00264021  |               0.39041    |    0.00540909 |     0.00892935 |     0.00209075 |      0.006087   |               9 |               11 |
| p07_corrected | p07_corrected_plus_p09a_taxon       | downstream_high_minus_low             |   0.00676254 |    0.00412237 |       -0.00264016  |               0.39041    |    0.00535722 |     0.00935485 |     0.00201773 |      0.00603903 |               9 |               11 |
| uncorrected   | uncorrected_plus_p09b_adjudicated   | downstream_high_minus_low             |   0.00676266 |    0.00408704 |       -0.00267562  |               0.395646   |    0.00540909 |     0.00892935 |     0.00199928 |      0.00612094 |               9 |               11 |
| p07_corrected | p07_corrected_plus_p09b_adjudicated | downstream_high_minus_low             |   0.00676254 |    0.00408696 |       -0.00267558  |               0.395647   |    0.00535722 |     0.00935485 |     0.00189855 |      0.00614784 |               9 |               11 |
| uncorrected   | uncorrected_plus_p09a_taxon         | p04_duplicate_charge_median_log_shift |   0.0476435  |    0.0481128  |        0.000469287 |              -0.00984997 |    0.021792   |     0.0567277  |     0.0216324  |      0.0614783  |               9 |               11 |
| p07_corrected | p07_corrected_plus_p09a_taxon       | p07_corrected_charge_median_log_shift |   0.0476112  |    0.0480778  |        0.000466601 |              -0.00980023 |    0.0250076  |     0.0575552  |     0.0219988  |      0.0597845  |               9 |               11 |
| uncorrected   | uncorrected_plus_p09b_adjudicated   | p04_duplicate_charge_median_log_shift |   0.0476435  |    0.0469754  |       -0.000668137 |               0.0140237  |    0.021792   |     0.0567277  |     0.0217337  |      0.0581246  |               9 |               11 |
| p07_corrected | p07_corrected_plus_p09b_adjudicated | p07_corrected_charge_median_log_shift |   0.0476112  |    0.0469404  |       -0.00067083  |               0.0140898  |    0.0250076  |     0.0575552  |     0.0239224  |      0.0582907  |               9 |               11 |

## P09a versus P09b labels

| scope                     | metric                                |           value |   numerator |   denominator |
|:--------------------------|:--------------------------------------|----------------:|------------:|--------------:|
| all_s10_events            | n_events                              | 243133          |      243133 |        243133 |
| all_s10_events            | exact_label_match_rate                |      0.976585   |      237440 |        243133 |
| all_s10_events            | target_any_match_rate                 |      0.976688   |      237465 |        243133 |
| all_s10_events            | p09a_target_rate                      |      0.0297286  |        7228 |        243133 |
| all_s10_events            | p09b_target_rate                      |      0.00644092 |        1566 |        243133 |
| all_s10_events            | p09b_review_agreement_rate            |      0.961729   |      233828 |        243133 |
| exact_gallery_ref_overlap | n_events                              |     42          |          42 |           256 |
| exact_gallery_ref_overlap | script_p09b_matches_gallery_consensus |      1          |          42 |            42 |
| exact_gallery_ref_overlap | p09a_matches_gallery_taxon            |      0.952381   |          40 |            42 |

## ML propagation

The ML arm trains run-held-out downstream logistic and P04 duplicate-charge ridge models. The P09a and P09b models add only their respective labels/booleans to the same charge-stratum features; run, event id, current label, and downstream target are excluded.

Run-held-out downstream residual high-minus-low changes from **-0.00116** [-0.00790, 0.00518] without labels to **0.00574** [-0.00363, 0.01256] with P09a and **0.00369** [-0.00475, 0.00923] with P09b. P04 log-charge residual high-minus-low changes from **0.01903** [0.00952, 0.02672] to **0.01185** [0.00383, 0.01833] with P09a and **0.01369** [0.00451, 0.02020] with P09b.

| metric                                       |       value |      ci_low |    ci_high |   n_strata |   n_bootstrap | bootstrap_unit           |
|:---------------------------------------------|------------:|------------:|-----------:|-----------:|--------------:|:-------------------------|
| observed_downstream_high_minus_low           |  0.00676266 |  0.00537817 | 0.00924135 |          9 |           400 | run_within_current_group |
| predicted_downstream_base_high_minus_low     |  0.00791839 |  0.00146311 | 0.0177703  |          9 |           400 | run_within_current_group |
| residual_downstream_base_high_minus_low      | -0.00115573 | -0.00789574 | 0.00518101 |          9 |           400 | run_within_current_group |
| predicted_downstream_p09a_high_minus_low     |  0.00101989 | -0.00617422 | 0.0122528  |          9 |           400 | run_within_current_group |
| residual_downstream_p09a_high_minus_low      |  0.00574277 | -0.00363309 | 0.0125622  |          9 |           400 | run_within_current_group |
| predicted_downstream_p09b_high_minus_low     |  0.00307048 | -0.00416287 | 0.0124887  |          9 |           400 | run_within_current_group |
| residual_downstream_p09b_high_minus_low      |  0.00369218 | -0.00475019 | 0.00922622 |          9 |           400 | run_within_current_group |
| log_p04_charge_high_minus_low                |  0.0357673  |  0.0182376  | 0.050927   |          9 |           400 | run_within_current_group |
| predicted_log_p04_charge_base_high_minus_low |  0.0167384  |  0.0104341  | 0.0262912  |          9 |           400 | run_within_current_group |
| residual_log_p04_charge_base_high_minus_low  |  0.0190289  |  0.00951713 | 0.0267238  |          9 |           400 | run_within_current_group |
| predicted_log_p04_charge_p09a_high_minus_low |  0.0239158  |  0.0141244  | 0.0347515  |          9 |           400 | run_within_current_group |
| residual_log_p04_charge_p09a_high_minus_low  |  0.0118515  |  0.00382755 | 0.0183335  |          9 |           400 | run_within_current_group |
| predicted_log_p04_charge_p09b_high_minus_low |  0.022074   |  0.0129642  | 0.0325721  |          9 |           400 | run_within_current_group |
| residual_log_p04_charge_p09b_high_minus_low  |  0.0136933  |  0.0045093  | 0.0202045  |          9 |           400 | run_within_current_group |

## Taxon prevalence

| label_source   | group     | label                         |      n |   group_rate |   downstream_rate |   median_log_p04_charge |
|:---------------|:----------|:------------------------------|-------:|-------------:|------------------:|------------------------:|
| p09a           | high_20nA | unassigned_common             | 227905 |  0.960429    |        0.0277616  |                10.7335  |
| p09a           | high_20nA | novel_early_pretrigger        |   4790 |  0.0201858   |        0.0480167  |                 6.96268 |
| p09a           | high_20nA | baseline_excursion            |   1745 |  0.00735372  |        0.0269341  |                 7.82025 |
| p09a           | high_20nA | novel_delayed_peak            |   1427 |  0.00601361  |        0.514366   |                 9.70701 |
| p09a           | high_20nA | novel_broad_template_mismatch |    882 |  0.00371689  |        0.481859   |                10.9982  |
| p09a           | high_20nA | pileup_or_long_tail           |    269 |  0.00113361  |        0.609665   |                 9.73683 |
| p09a           | high_20nA | dropout                       |    264 |  0.00111254  |        0.00378788 |                 7.81003 |
| p09a           | high_20nA | saturation                    |     13 |  5.47841e-05 |        0.0769231  |                11.1997  |
| p09a           | low_2nA   | unassigned_common             |   5659 |  0.969339    |        0.0212052  |                10.4662  |
| p09a           | low_2nA   | novel_early_pretrigger        |    112 |  0.0191847   |        0.0267857  |                 6.97255 |
| p09a           | low_2nA   | baseline_excursion            |     39 |  0.00668037  |        0.025641   |                 7.63129 |
| p09a           | low_2nA   | novel_delayed_peak            |     14 |  0.00239808  |        0.571429   |                 9.33587 |
| p09a           | low_2nA   | dropout                       |      6 |  0.00102775  |        0          |                 7.78235 |
| p09a           | low_2nA   | pileup_or_long_tail           |      5 |  0.000856458 |        0.4        |                10.0501  |
| p09a           | low_2nA   | novel_broad_template_mismatch |      3 |  0.000513875 |        0.333333   |                10.9761  |
| p09b           | high_20nA | unassigned_common             | 227903 |  0.960421    |        0.027753   |                10.7335  |
| p09b           | high_20nA | dropout                       |   4416 |  0.0186097   |        0.0396286  |                 6.88961 |
| p09b           | high_20nA | baseline_excursion            |   2106 |  0.00887503  |        0.0337132  |                 7.79237 |
| p09b           | high_20nA | pileup_or_long_tail           |   1298 |  0.00546998  |        0.371341   |                10.1009  |
| p09b           | high_20nA | novel_delayed_peak            |   1212 |  0.00510757  |        0.575083   |                 9.50114 |
| p09b           | high_20nA | novel_broad_template_mismatch |    328 |  0.00138225  |        0.527439   |                10.9397  |
| p09b           | high_20nA | saturation                    |     19 |  8.00691e-05 |        0.105263   |                11.1843  |
| p09b           | high_20nA | novel_early_pretrigger        |     13 |  5.47841e-05 |        0.307692   |                 9.96762 |
| p09b           | low_2nA   | unassigned_common             |   5659 |  0.969339    |        0.0212052  |                10.4662  |
| p09b           | low_2nA   | dropout                       |    104 |  0.0178143   |        0.0288462  |                 6.87292 |
| p09b           | low_2nA   | baseline_excursion            |     46 |  0.00787941  |        0.0217391  |                 7.67252 |
| p09b           | low_2nA   | pileup_or_long_tail           |     16 |  0.00274066  |        0.25       |                 9.32839 |
| p09b           | low_2nA   | novel_delayed_peak            |     12 |  0.0020555   |        0.583333   |                 9.27219 |
| p09b           | low_2nA   | novel_broad_template_mismatch |      1 |  0.000171292 |        0          |                10.881   |

## Leakage review

| check                                                    |       value | flag   | note                                                                                                         |
|:---------------------------------------------------------|------------:|:-------|:-------------------------------------------------------------------------------------------------------------|
| ml_heldout_runs_excluded_from_training                   |  1          | False  | Each ML prediction is made by a model trained without that source run.                                       |
| identifier_current_and_downstream_excluded_from_features |  1          | False  | Feature matrices exclude run, event number, group/current, and downstream target.                            |
| p09a_and_p09b_labels_are_not_ml_truth                    |  1          | False  | P09a deterministic taxa and P09b fixed adjudication-rubric labels enter only as explanatory strata/features. |
| pred_downstream_base_current_auc                         |  0.563838   | False  | Flags if a propagated score almost identifies beam current.                                                  |
| pred_downstream_p09a_current_auc                         |  0.550157   | False  | Flags if a propagated score almost identifies beam current.                                                  |
| pred_downstream_p09b_current_auc                         |  0.552893   | False  | Flags if a propagated score almost identifies beam current.                                                  |
| resid_log_p04_charge_base_current_auc                    |  0.571176   | False  | Flags if a propagated score almost identifies beam current.                                                  |
| resid_log_p04_charge_p09a_current_auc                    |  0.557564   | False  | Flags if a propagated score almost identifies beam current.                                                  |
| resid_log_p04_charge_p09b_current_auc                    |  0.561295   | False  | Flags if a propagated score almost identifies beam current.                                                  |
| heldout_downstream_p09a_model_mean_auc                   |  0.883064   | False  | Flags an implausibly strong downstream classifier under run holdout.                                         |
| heldout_downstream_p09b_model_mean_auc                   |  0.882798   | False  | Flags an implausibly strong downstream classifier under run holdout.                                         |
| p09a_curated_rate_high_minus_low                         |  0.00890981 | False  | Flags if label prevalence nearly encodes current.                                                            |
| p09b_curated_rate_high_minus_low                         |  0.00891824 | False  | Flags if label prevalence nearly encodes current.                                                            |
| p09a_exactly_equals_p09b_rate                            |  0.976585   | False  | Flags if P09b adjudicated labels are effectively a copy of P09a.                                             |
| p09b_gallery_ref_overlap_rows                            | 42          | False  | Only gallery pulses matching the S10 reference stave can be compared exactly.                                |
| p09b_script_matches_gallery_consensus                    |  1          | False  | Checks full-sample rubric reproduces stored P09b labels on exact overlap.                                    |

## Conclusion

P09b adjudicated labels attenuate the matched downstream excess similarly to, but slightly less than, deterministic P09a labels. Traditional P04 strata give base downstream high-minus-low 0.00676, P09a 0.00412 [0.00209, 0.00609], and P09b 0.00409 [0.00200, 0.00612]. P07-corrected strata give base 0.00676, P09a 0.00412, and P09b 0.00409. The P04 duplicate-charge log shift changes from 0.04764 to P09a 0.04811 and P09b 0.04698. Run-held-out ML changes downstream residual high-minus-low from -0.00116 to P09a 0.00574 and P09b 0.00369; P04 log-charge residual high-minus-low changes from 0.01903 to P09a 0.01185 and P09b 0.01369. Leakage flags: 0.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, traditional, ML, taxon, and leakage CSVs are in this folder.

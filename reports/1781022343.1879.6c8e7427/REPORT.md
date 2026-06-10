# S02e: manual audit of ML high-risk timing-tail pulses

**Ticket:** `1781022343.1879.6c8e7427`

## Reproduction first
Before reading the prior high-risk table, the B-stack raw ROOT files were scanned with the same S00/S02 gate. The selected-pulse counts and the prior S02d high-risk/tail numbers then reproduced exactly.

| quantity                               |   report_value |     reproduced |   delta |   tolerance | pass   |
|:---------------------------------------|---------------:|---------------:|--------:|------------:|:-------|
| raw total selected B-stave pulses      | 640737         | 640737         |       0 |       0     | True   |
| raw sample_ii_analysis selected_pulses | 125096         | 125096         |       0 |       0     | True   |
| raw sample_ii_analysis B2              |  88213         |  88213         |       0 |       0     | True   |
| raw sample_ii_analysis B4              |  21229         |  21229         |       0 |       0     | True   |
| raw sample_ii_analysis B6              |  11148         |  11148         |       0 |       0     | True   |
| raw sample_ii_analysis B8              |   4506         |   4506         |       0 |       0     | True   |
| prior heldout pair rows                |   2178         |   2178         |       0 |       0     | True   |
| prior ML high-risk pair rows           |    515         |    515         |       0 |       0     | True   |
| prior baseline tail rate               |      0.0486685 |      0.0486685 |       0 |       1e-12 | True   |
| prior exclude-ML tail rate             |      0.0282622 |      0.0282622 |       0 |       1e-12 | True   |

## Question
The prior S02d ML flag removed 515 of 2,178 held-out downstream B-stack pair residuals and lowered the retained-pair tail rate from 0.0487 to 0.0283. This audit asks whether those flagged pairs share waveform-shape failure modes or are mainly a charge/stave mixture.

## Methods
Waveforms were joined back to the freshly scanned raw ROOT table through S02d source indices. The traditional method scanned one-dimensional, hand-engineered shape rules on training runs only and applied the selected rule to the held-out run. The ML method used leave-one-run-out RandomForest scores from pair-level waveform-shape features only; run/event/stave identifiers were excluded. CIs bootstrap the held-out runs.

| method                         |   n_pairs |   n_selected |   selected_fraction |   high_risk_precision |   high_risk_enrichment |   tail_precision |   tail_enrichment |   tail_rate_after_exclusion |   kept_pair_fraction |   median_log_amp_delta_selected |   max_pair_share_selected |
|:-------------------------------|----------:|-------------:|--------------------:|----------------------:|-----------------------:|-----------------:|------------------:|----------------------------:|---------------------:|--------------------------------:|--------------------------:|
| prior_ml_high_risk_flag        |      2178 |          515 |            0.236455 |              1        |                4.22913 |        0.128155  |           2.47011 |                   0.0282622 |             0.763545 |                       -0.167695 |                  0.563107 |
| trad_q_template_rmse_absdiff   |      2178 |          233 |            0.106979 |              0.562232 |                2.37775 |        0.180258  |           3.47434 |                   0.0365039 |             0.893021 |                       -0.299592 |                  0.536481 |
| loro_ml_shape_recover_highrisk |      2178 |          515 |            0.236455 |              0.673786 |                2.84953 |        0.108738  |           2.09585 |                   0.0342754 |             0.763545 |                       -0.256429 |                  0.576699 |
| charge_pair_matched_null       |      2178 |          515 |            0.236455 |              0.341748 |                1.44529 |        0.0776699 |           1.49704 |                   0.0438966 |             0.763545 |                       -0.169965 |                  0.563107 |

Selected traditional rule: `trad_q_template_rmse_absdiff`. It captures high-risk pairs with precision 0.562, versus 1.000 for the original S02d ML flag and 0.674 for the LORO ML shape recovery.

## Held-Out Bootstrap CIs
| method                         | metric                    |    ci_low |   ci_high |
|:-------------------------------|:--------------------------|----------:|----------:|
| prior_ml_high_risk_flag        | high_risk_precision       | 1         | 1         |
| prior_ml_high_risk_flag        | tail_precision            | 0.0898204 | 0.151899  |
| prior_ml_high_risk_flag        | tail_rate_after_exclusion | 0.0223398 | 0.0378151 |
| prior_ml_high_risk_flag        | kept_pair_fraction        | 0.731058  | 0.830295  |
| trad_q_template_rmse_absdiff   | high_risk_precision       | 0.491228  | 0.590361  |
| trad_q_template_rmse_absdiff   | tail_precision            | 0.09375   | 0.213018  |
| trad_q_template_rmse_absdiff   | tail_rate_after_exclusion | 0.031555  | 0.0460763 |
| trad_q_template_rmse_absdiff   | kept_pair_fraction        | 0.859386  | 0.962132  |
| loro_ml_shape_recover_highrisk | high_risk_precision       | 0.622754  | 0.700965  |
| loro_ml_shape_recover_highrisk | tail_precision            | 0.0614334 | 0.12963   |
| loro_ml_shape_recover_highrisk | tail_rate_after_exclusion | 0.0273179 | 0.0392879 |
| loro_ml_shape_recover_highrisk | kept_pair_fraction        | 0.731058  | 0.830295  |
| charge_pair_matched_null       | high_risk_precision       | 0.239669  | 0.390365  |
| charge_pair_matched_null       | tail_precision            | 0.07173   | 0.0918919 |
| charge_pair_matched_null       | tail_rate_after_exclusion | 0.0340314 | 0.0500189 |
| charge_pair_matched_null       | kept_pair_fraction        | 0.731058  | 0.830295  |

## ML Folds
|   heldout_run |    n |   positive_rate |   average_precision |   roc_auc |
|--------------:|-----:|----------------:|--------------------:|----------:|
|            42 |  366 |        0.15847  |            0.656921 |  0.867891 |
|            57 |  347 |        0.181556 |            0.701593 |  0.875363 |
|            64 | 1067 |        0.27179  |            0.799444 |  0.90679  |
|            65 |  398 |        0.261307 |            0.657232 |  0.831044 |

## Shape Atoms
|   cluster |   n_pulses |     share | dominant_stave   | dominant_taxon     |   median_amp_adc |   median_late_fraction |   median_width_half |   median_timing_span_dup |
|----------:|-----------:|----------:|:-----------------|:-------------------|-----------------:|-----------------------:|--------------------:|-------------------------:|
|         0 |        435 | 0.536375  | B6               | unassigned_common  |          2037.5  |               0.32995  |                   7 |                       18 |
|         2 |        158 | 0.194821  | B4               | unassigned_common  |          2070.25 |               0.206601 |                   7 |                       18 |
|         4 |         87 | 0.107275  | B6               | novel_delayed_peak |          1939    |               0.991105 |                   2 |                       18 |
|         1 |         70 | 0.0863132 | B4               | novel_delayed_peak |          2588.75 |               0.971034 |                   5 |                       18 |
|         3 |         61 | 0.0752158 | B4               | unassigned_common  |          2516.5  |               0.611808 |                   7 |                       18 |

Pair-level enrichment by atom:

| method       |   n_pairs |   n_selected |   selected_fraction |   high_risk_precision |   high_risk_enrichment |   tail_precision |   tail_enrichment |   tail_rate_after_exclusion |   kept_pair_fraction |   median_log_amp_delta_selected |   max_pair_share_selected |
|:-------------|----------:|-------------:|--------------------:|----------------------:|-----------------------:|-----------------:|------------------:|----------------------------:|---------------------:|--------------------------------:|--------------------------:|
| shape_atom_1 |      2178 |           53 |           0.0243343 |              0.886792 |                3.75036 |         0.113208 |           2.182   |                   0.0503529 |             0.975666 |                      -0.0823381 |                  0.641509 |
| shape_atom_4 |      2178 |           67 |           0.0307622 |              0.850746 |                3.59791 |         0.104478 |           2.01374 |                   0.0502132 |             0.969238 |                      -0.185769  |                  0.492537 |
| shape_atom_0 |      2178 |          380 |           0.174472  |              0.826316 |                3.49459 |         0.118421 |           2.28249 |                   0.0378198 |             0.825528 |                      -0.152564  |                  0.471053 |
| shape_atom_3 |      2178 |           53 |           0.0243343 |              0.811321 |                3.43118 |         0.113208 |           2.182   |                   0.0503529 |             0.975666 |                      -0.0586793 |                  0.54717  |
| shape_atom_2 |      2178 |          145 |           0.0665748 |              0.8      |                3.3833  |         0.151724 |           2.92438 |                   0.0447614 |             0.933425 |                      -0.144499  |                  0.544828 |

## Leakage And Proxy Checks
| check                                    |    value | pass   | note                                                            |
|:-----------------------------------------|---------:|:-------|:----------------------------------------------------------------|
| train_heldout_run_overlap_loro           | 0        | True   | each ML fold leaves out one run                                 |
| model_features_include_ids               | 0        | True   | none                                                            |
| raw_source_index_join_missing            | 0        | True   | zero means every prior source index was found in fresh raw scan |
| ml_selected_max_run_pair_share           | 0.312621 | True   | guards against one run/pair stratum dominating the result       |
| charge_pair_matched_null_precision       | 0.341748 | True   | matched random selection should underperform ML shape score     |
| ml_average_precision                     | 0.72975  | True   | LORO score versus prior high-risk pair labels                   |
| suspicious_result_triggered_extra_checks | 0        | True   | triggered if precision >0.90 or enrichment >3                   |

## Verdict
The high-risk flag is not just a charge/stave mixture: a run-held-out ML shape model recovers much of the flag, and the dominant shape atoms are delayed/broad or high late-fraction pulses. The simpler traditional rule is directionally useful but much weaker, so the S02d ML flag appears to encode a real waveform-failure family rather than a production-ready cut.

## Provenance
Runtime was 97.9 s on `billy`. `manifest.json` records input and output hashes.

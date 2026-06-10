# P04d A/B Charge-Transfer Null Controls By A-Topology

- **Ticket:** `1781023046.3598.1ff04de7`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Split:** B2-source leave-one-run-out by run; every topology prediction is trained on other runs.
- **Targets:** `A1_only`, `A3_only`, and `A1A3` event-matched selected positive-lobe charge.

## Raw Reproduction First

B-stack S00 selected-pulse count reproduced exactly: `640,737`.

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

P04c broad target reproduction: `4055` rows, ridge res68 `0.519271`, waveform ExtraTrees res68 `0.519965`.

## Topology Support

| topology   |    n |   runs |   median_target_charge |   median_b2_charge |   a_mult |
|:-----------|-----:|-------:|-----------------------:|-------------------:|---------:|
| A1A3       | 1342 |     31 |                32295.5 |              41470 |        2 |
| A1_only    |  149 |     25 |                11564   |              50750 |        1 |
| A3_only    | 2564 |     32 |                15329   |              40653 |        1 |

## Held-Out Benchmark

| topology   | method                      |    n |   bias_median_frac | bias_ci95                                      |   res68_abs_frac | res68_ci95                                 |   within_25pct |
|:-----------|:----------------------------|-----:|-------------------:|:-----------------------------------------------|-----------------:|:-------------------------------------------|---------------:|
| A1A3       | a_mult_median               | 1342 |        -0.0008686  | [-0.02526740792662038, 0.026232366460611823]   |         0.263636 | [0.2541017452997524, 0.2744938095025254]   |       0.646796 |
| A1A3       | topology_median             | 1342 |        -0.0008686  | [-0.023864464415836773, 0.02708696766728824]   |         0.263636 | [0.25408946922046727, 0.27305966590561265] |       0.646796 |
| A1A3       | topology_b_charge_ridge     | 1342 |        -0.020917   | [-0.040300712888279557, -0.003118696145842088] |         0.267386 | [0.2606110218780793, 0.27319383414450915]  |       0.636364 |
| A1A3       | waveform_extra_trees        | 1342 |        -0.022995   | [-0.04675879217134636, -0.0037640106567531774] |         0.269829 | [0.2606449587869361, 0.27842452755280905]  |       0.632638 |
| A1A3       | waveform_hgb                | 1342 |        -0.0247384  | [-0.04933682966582055, -0.0018776698100149527] |         0.268497 | [0.2592201438947308, 0.2773134919021932]   |       0.636364 |
| A1A3       | shuffled_target_extra_trees | 1342 |        -0.0274404  | [-0.04934489213921522, -0.003414635267263055]  |         0.271686 | [0.2557999586055473, 0.2806146115650155]   |       0.64456  |
| A1_only    | a_mult_median               |  149 |         0.291292   | [0.1961361106694228, 0.4438311059461553]       |         0.724971 | [0.5500777596916838, 0.9023620058102817]   |       0.38255  |
| A1_only    | topology_median             |  149 |         0.0131875  | [-0.10096994752742884, 0.12547106000579766]    |         0.490675 | [0.3847539888279849, 0.584092126405999]    |       0.416107 |
| A1_only    | topology_b_charge_ridge     |  149 |        -0.0994346  | [-0.20917255593286985, 0.058799173797364726]   |         0.485523 | [0.3808816812363628, 0.5907470969585983]   |       0.315436 |
| A1_only    | waveform_extra_trees        |  149 |        -0.0872741  | [-0.16875115385331965, 0.0581938666856632]     |         0.491016 | [0.42446298907045604, 0.5709959703993064]  |       0.302013 |
| A1_only    | waveform_hgb                |  149 |        -0.0508935  | [-0.140321040708133, 0.06118988367414119]      |         0.488377 | [0.457162716250366, 0.5742467208271607]    |       0.422819 |
| A1_only    | shuffled_target_extra_trees |  149 |        -0.123844   | [-0.17355897599028933, 0.0787027866187068]     |         0.496531 | [0.4217770015086783, 0.5603474142216426]   |       0.355705 |
| A3_only    | a_mult_median               | 2564 |        -0.0201069  | [-0.050518879789398494, 0.022362189947300704]  |         0.398734 | [0.3850998843889381, 0.41220312332596415]  |       0.418877 |
| A3_only    | topology_median             | 2564 |         0.00242751 | [-0.027570943698575663, 0.03736428306771968]   |         0.399084 | [0.3851138800794051, 0.4145159451138394]   |       0.427457 |
| A3_only    | topology_b_charge_ridge     | 2564 |        -0.0536146  | [-0.08620362236970787, -0.021798240878873533]  |         0.395999 | [0.3857119972948841, 0.409116562775884]    |       0.406786 |
| A3_only    | waveform_extra_trees        | 2564 |        -0.0534879  | [-0.08559174570957262, -0.020471225298850503]  |         0.393368 | [0.3823176114718592, 0.4049040375571206]   |       0.407566 |
| A3_only    | waveform_hgb                | 2564 |        -0.0578324  | [-0.08464921415724501, -0.022741368140740886]  |         0.398486 | [0.38808459810622803, 0.41188815015724983] |       0.400156 |
| A3_only    | shuffled_target_extra_trees | 2564 |        -0.0496651  | [-0.07900545735202777, -0.022507118784455996]  |         0.399187 | [0.3871798431972045, 0.4097529218064626]   |       0.397036 |

## Leakage Checks

| topology   | split             |   train_heldout_run_overlap | features_exclude                                            |   exact_b_waveform_hash_train_test_overlaps |   best_real_ml_res68 |   shuffled_target_extra_trees_res68 |   ml_to_shuffled_res68_ratio | looks_too_good   |
|:-----------|:------------------|----------------------------:|:------------------------------------------------------------|--------------------------------------------:|---------------------:|------------------------------------:|-----------------------------:|:-----------------|
| A1A3       | leave-one-run-out |                           0 | run, evt, A selected flags, A charge columns, target_charge |                                           0 |             0.268497 |                            0.271686 |                     0.988263 | False            |
| A1_only    | leave-one-run-out |                           0 | run, evt, A selected flags, A charge columns, target_charge |                                           0 |             0.488377 |                            0.496531 |                     0.983579 | False            |
| A3_only    | leave-one-run-out |                           0 | run, evt, A selected flags, A charge columns, target_charge |                                           0 |             0.393368 |                            0.399187 |                     0.985423 | False            |

No topology has a real ML res68 below `0.25` or below `75%` of the shuffled-target sentinel, so no extra target-echo model was promoted beyond the exact waveform-hash and shuffled-target checks.

## Finding

Topology mixing contributes to the broad P04c transfer, but the remaining widths are still far from a useful duplicate-readout-like closure. A1A3: best real `a_mult_median` res68 0.2636; ridge 0.2674 [0.2606, 0.2732], ExtraTrees 0.2698, shuffled 0.2717 A1_only: best real `topology_b_charge_ridge` res68 0.4855; ridge 0.4855 [0.3809, 0.5907], ExtraTrees 0.4910, shuffled 0.4965 A3_only: best real `waveform_extra_trees` res68 0.3934; ridge 0.3960 [0.3857, 0.4091], ExtraTrees 0.3934, shuffled 0.3992

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `p04c_reproduction_summary.csv`, `ab_topology_counts_by_run.csv`, `target_topology_counts.csv`, `topology_summary.csv`, `topology_by_run.csv`, `topology_predictions.csv`, and `leakage_checks.csv`.

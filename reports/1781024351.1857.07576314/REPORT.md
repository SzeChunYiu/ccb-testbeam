# P04e External Downstream Validation For P04d Closure

- **Ticket:** `1781024351.1857.07576314`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Split:** leave-one-run-out by run; every prediction excludes the held-out run.
- **External target:** Sample II penetrating rows with B2/B4/B6/B8 selected; target is B4+B6+B8 even positive charge.
- **Features:** B2 even waveform and B2 even summaries only. Odd duplicate channels are never features.

## Raw Reproduction First

B-stack S00 selected-pulse count: `640,737` vs expected `640,737` (delta `+0`).

P04d upstream reproduction: P04c matched rows `4055` vs expected `4055`; ridge res68 `0.519271` vs expected `0.519271`.

## External Sample

Valid B2 duplicate rows after odd-charge quality cut: `579,227`. Penetrating external rows: `3,774` across `7` runs.

## Same-Event Duplicate Closure On External Rows

| method                   |    n |   bias_median_frac | bias_ci95                                      |   res68_abs_frac | res68_ci95                                   |   full_rms_frac |   within_10pct |
|:-------------------------|-----:|-------------------:|:-----------------------------------------------|-----------------:|:---------------------------------------------|----------------:|---------------:|
| strong_traditional_huber | 3774 |        0.0320328   | [0.030000577880770367, 0.033188500054956056]   |        0.0684983 | [0.06009468356398364, 0.0965421781965887]    |       0.899599  |       0.711977 |
| extra_trees_odd_closure  | 3774 |        0.000940627 | [0.0005339352623644373, 0.0016459746632236673] |        0.0119121 | [0.010092380828704499, 0.015372504582681426] |       0.0684228 |       0.95893  |

## External Downstream Target

| method                           |    n |   bias_median_frac | bias_ci95                                     |   res68_abs_frac | res68_ci95                                 |   full_rms_frac |   within_25pct |
|:---------------------------------|-----:|-------------------:|:----------------------------------------------|-----------------:|:-------------------------------------------|----------------:|---------------:|
| huber_odd_closure_transfer       | 3774 |        -0.0083804  | [-0.06714693442226148, 0.08722414243590096]   |         0.244481 | [0.227357982984056, 0.28174599290916114]   |        0.552424 |       0.691309 |
| extra_trees_odd_closure_transfer | 3774 |        -0.00856145 | [-0.06530940590056174, 0.0708701125034864]    |         0.240736 | [0.22408338113017384, 0.2695656531795641]  |        0.562749 |       0.697933 |
| direct_external_huber            | 3774 |        -0.00792124 | [-0.062206610456447535, 0.06652462107170294]  |         0.225931 | [0.21217267908190904, 0.24562572444861808] |        0.37806  |       0.7292   |
| direct_external_extra_trees      | 3774 |        -0.012433   | [-0.055470809740587185, 0.039767855099857176] |         0.209636 | [0.19828622505852805, 0.22816760938070285] |        0.260566 |       0.768151 |
| shuffled_external_extra_trees    | 3774 |        -0.0604796  | [-0.11730902816680494, 0.010318792498876607]  |         0.271892 | [0.24897384757307897, 0.289615259788523]   |        0.587235 |       0.63858  |

## Run Checks

|   run | target                     | method                           |   n |   bias_median_frac |   res68_abs_frac |   within_25pct |
|------:|:---------------------------|:---------------------------------|----:|-------------------:|-----------------:|---------------:|
|    58 | same_event_B2_odd_charge   | strong_traditional_huber         |  72 |        0.0221757   |       0.0776185  |       0.805556 |
|    58 | same_event_B2_odd_charge   | extra_trees_odd_closure          |  72 |        0.00152641  |       0.0136714  |       1        |
|    58 | external_downstream_charge | huber_odd_closure_transfer       |  72 |        0.101811    |       0.467702   |       0.5      |
|    58 | external_downstream_charge | extra_trees_odd_closure_transfer |  72 |        0.147774    |       0.469717   |       0.5      |
|    58 | external_downstream_charge | direct_external_huber            |  72 |       -0.01185     |       0.262498   |       0.652778 |
|    58 | external_downstream_charge | direct_external_extra_trees      |  72 |       -0.0269625   |       0.246584   |       0.680556 |
|    58 | external_downstream_charge | shuffled_external_extra_trees    |  72 |        0.0579045   |       0.402242   |       0.472222 |
|    59 | same_event_B2_odd_charge   | strong_traditional_huber         | 749 |        0.0289359   |       0.105895   |       0.755674 |
|    59 | same_event_B2_odd_charge   | extra_trees_odd_closure          | 749 |        0.00196479  |       0.0172891  |       0.978638 |
|    59 | external_downstream_charge | huber_odd_closure_transfer       | 749 |        0.0853193   |       0.268507   |       0.6502   |
|    59 | external_downstream_charge | extra_trees_odd_closure_transfer | 749 |        0.0887576   |       0.273293   |       0.636849 |
|    59 | external_downstream_charge | direct_external_huber            | 749 |        0.0950187   |       0.260983   |       0.672897 |
|    59 | external_downstream_charge | direct_external_extra_trees      | 749 |        0.0487168   |       0.230514   |       0.708945 |
|    59 | external_downstream_charge | shuffled_external_extra_trees    | 749 |        0.0118491   |       0.242133   |       0.691589 |
|    60 | same_event_B2_odd_charge   | strong_traditional_huber         | 802 |        0.0341574   |       0.0627616  |       0.795511 |
|    60 | same_event_B2_odd_charge   | extra_trees_odd_closure          | 802 |        0.000406471 |       0.00914247 |       0.991272 |
|    60 | external_downstream_charge | huber_odd_closure_transfer       | 802 |       -0.118107    |       0.252822   |       0.669576 |
|    60 | external_downstream_charge | extra_trees_odd_closure_transfer | 802 |       -0.110688    |       0.248418   |       0.687032 |
|    60 | external_downstream_charge | direct_external_huber            | 802 |       -0.101817    |       0.230567   |       0.72818  |
|    60 | external_downstream_charge | direct_external_extra_trees      | 802 |       -0.0945635   |       0.208779   |       0.802993 |
|    60 | external_downstream_charge | shuffled_external_extra_trees    | 802 |       -0.158627    |       0.297546   |       0.552369 |
|    61 | same_event_B2_odd_charge   | strong_traditional_huber         | 925 |        0.0324842   |       0.0569552  |       0.816216 |
|    61 | same_event_B2_odd_charge   | extra_trees_odd_closure          | 925 |        0.000457834 |       0.00998975 |       0.997838 |
|    61 | external_downstream_charge | huber_odd_closure_transfer       | 925 |       -0.0598999   |       0.220765   |       0.742703 |
|    61 | external_downstream_charge | extra_trees_odd_closure_transfer | 925 |       -0.0563201   |       0.216845   |       0.756757 |
|    61 | external_downstream_charge | direct_external_huber            | 925 |       -0.0465277   |       0.20891    |       0.777297 |
|    61 | external_downstream_charge | direct_external_extra_trees      | 925 |       -0.0338256   |       0.201237   |       0.801081 |
|    61 | external_downstream_charge | shuffled_external_extra_trees    | 925 |       -0.114039    |       0.272364   |       0.625946 |
|    62 | same_event_B2_odd_charge   | strong_traditional_huber         | 798 |        0.0332913   |       0.0696251  |       0.79198  |
|    62 | same_event_B2_odd_charge   | extra_trees_odd_closure          | 798 |        0.00114977  |       0.0122376  |       0.991228 |
|    62 | external_downstream_charge | huber_odd_closure_transfer       | 798 |        0.00320076  |       0.212767   |       0.753133 |
|    62 | external_downstream_charge | extra_trees_odd_closure_transfer | 798 |        0.00493049  |       0.211726   |       0.754386 |
|    62 | external_downstream_charge | direct_external_huber            | 798 |        0.00741021  |       0.204814   |       0.761905 |
|    62 | external_downstream_charge | direct_external_extra_trees      | 798 |        0.0169667   |       0.190582   |       0.785714 |
|    62 | external_downstream_charge | shuffled_external_extra_trees    | 798 |       -0.0378004   |       0.24325    |       0.692982 |
|    63 | same_event_B2_odd_charge   | strong_traditional_huber         | 365 |        0.0303665   |       0.132366   |       0.747945 |
|    63 | same_event_B2_odd_charge   | extra_trees_odd_closure          | 365 |        0.00123629  |       0.0185813  |       0.986301 |
|    63 | external_downstream_charge | huber_odd_closure_transfer       | 365 |        0.107903    |       0.30706    |       0.630137 |
|    63 | external_downstream_charge | extra_trees_odd_closure_transfer | 365 |        0.0978605   |       0.272296   |       0.649315 |
|    63 | external_downstream_charge | direct_external_huber            | 365 |        0.0803892   |       0.245471   |       0.687671 |
|    63 | external_downstream_charge | direct_external_extra_trees      | 365 |        0.0277645   |       0.225662   |       0.728767 |
|    63 | external_downstream_charge | shuffled_external_extra_trees    | 365 |        0.0335444   |       0.255348   |       0.671233 |
|    65 | same_event_B2_odd_charge   | strong_traditional_huber         |  63 |        0.0275082   |       0.0629322  |       0.904762 |
|    65 | same_event_B2_odd_charge   | extra_trees_odd_closure          |  63 |        0.00241059  |       0.0167721  |       0.984127 |
|    65 | external_downstream_charge | huber_odd_closure_transfer       |  63 |        0.257973    |       0.380841   |       0.492063 |
|    65 | external_downstream_charge | extra_trees_odd_closure_transfer |  63 |        0.245392    |       0.399434   |       0.492063 |
|    65 | external_downstream_charge | direct_external_huber            |  63 |        0.119515    |       0.308701   |       0.619048 |
|    65 | external_downstream_charge | direct_external_extra_trees      |  63 |        0.100777    |       0.267189   |       0.650794 |
|    65 | external_downstream_charge | shuffled_external_extra_trees    |  63 |        0.146517    |       0.311879   |       0.603175 |

## B2-Amplitude Checks

| b2_amp_bin   | target                     | method                           |    n |   bias_median_frac |   res68_abs_frac |   within_25pct |
|:-------------|:---------------------------|:---------------------------------|-----:|-------------------:|-----------------:|---------------:|
| 1000_2000    | same_event_B2_odd_charge   | strong_traditional_huber         |  516 |        0.419603    |       1.33745    |       0.45155  |
| 1000_2000    | same_event_B2_odd_charge   | extra_trees_odd_closure          |  516 |        0.00263222  |       0.0387698  |       0.97093  |
| 1000_2000    | external_downstream_charge | huber_odd_closure_transfer       |  516 |        0.0935905   |       0.322272   |       0.571705 |
| 1000_2000    | external_downstream_charge | extra_trees_odd_closure_transfer |  516 |        0.0970138   |       0.289093   |       0.614341 |
| 1000_2000    | external_downstream_charge | direct_external_huber            |  516 |        0.0968255   |       0.2944     |       0.612403 |
| 1000_2000    | external_downstream_charge | direct_external_extra_trees      |  516 |        0.00359806  |       0.237281   |       0.709302 |
| 1000_2000    | external_downstream_charge | shuffled_external_extra_trees    |  516 |        0.296617    |       0.550316   |       0.430233 |
| 2000_3000    | same_event_B2_odd_charge   | strong_traditional_huber         | 1932 |        0.0271095   |       0.0480334  |       0.828675 |
| 2000_3000    | same_event_B2_odd_charge   | extra_trees_odd_closure          | 1932 |        0.000824906 |       0.00935245 |       0.992754 |
| 2000_3000    | external_downstream_charge | huber_odd_closure_transfer       | 1932 |       -0.0429938   |       0.218418   |       0.759834 |
| 2000_3000    | external_downstream_charge | extra_trees_odd_closure_transfer | 1932 |       -0.0291331   |       0.223588   |       0.743789 |
| 2000_3000    | external_downstream_charge | direct_external_huber            | 1932 |       -0.025696    |       0.207301   |       0.782609 |
| 2000_3000    | external_downstream_charge | direct_external_extra_trees      | 1932 |       -0.0136351   |       0.205146   |       0.787267 |
| 2000_3000    | external_downstream_charge | shuffled_external_extra_trees    | 1932 |       -0.0655656   |       0.231593   |       0.716874 |
| 3000_5000    | same_event_B2_odd_charge   | strong_traditional_huber         | 1121 |        0.0356075   |       0.0564041  |       0.873327 |
| 3000_5000    | same_event_B2_odd_charge   | extra_trees_odd_closure          | 1121 |        0.000841221 |       0.00846312 |       0.99554  |
| 3000_5000    | external_downstream_charge | huber_odd_closure_transfer       | 1121 |       -0.0372554   |       0.237593   |       0.70116  |
| 3000_5000    | external_downstream_charge | extra_trees_odd_closure_transfer | 1121 |       -0.0537606   |       0.237194   |       0.706512 |
| 3000_5000    | external_downstream_charge | direct_external_huber            | 1121 |       -0.0467726   |       0.223552   |       0.733274 |
| 3000_5000    | external_downstream_charge | direct_external_extra_trees      | 1121 |       -0.0130366   |       0.204564   |       0.781445 |
| 3000_5000    | external_downstream_charge | shuffled_external_extra_trees    | 1121 |       -0.158466    |       0.284037   |       0.595004 |
| 5000_7000    | same_event_B2_odd_charge   | strong_traditional_huber         |  132 |        0.0443482   |       0.130298   |       0.810606 |
| 5000_7000    | same_event_B2_odd_charge   | extra_trees_odd_closure          |  132 |        0.00303428  |       0.0380983  |       0.992424 |
| 5000_7000    | external_downstream_charge | huber_odd_closure_transfer       |  132 |        0.342531    |       0.564978   |       0.310606 |
| 5000_7000    | external_downstream_charge | extra_trees_odd_closure_transfer |  132 |        0.229118    |       0.42464    |       0.44697  |
| 5000_7000    | external_downstream_charge | direct_external_huber            |  132 |        0.190823    |       0.377837   |       0.545455 |
| 5000_7000    | external_downstream_charge | direct_external_extra_trees      |  132 |       -0.0142624   |       0.28445    |       0.613636 |
| 5000_7000    | external_downstream_charge | shuffled_external_extra_trees    |  132 |       -0.0258045   |       0.276238   |       0.636364 |
| 7000_inf     | same_event_B2_odd_charge   | strong_traditional_huber         |   73 |        0.0254183   |       0.0949812  |       0.808219 |
| 7000_inf     | same_event_B2_odd_charge   | extra_trees_odd_closure          |   73 |        0.00168835  |       0.0338735  |       0.958904 |
| 7000_inf     | external_downstream_charge | huber_odd_closure_transfer       |   73 |        0.474906    |       0.621722   |       0.260274 |
| 7000_inf     | external_downstream_charge | extra_trees_odd_closure_transfer |   73 |        0.323333    |       0.478493   |       0.39726  |
| 7000_inf     | external_downstream_charge | direct_external_huber            |   73 |        0.282484    |       0.427619   |       0.410959 |
| 7000_inf     | external_downstream_charge | direct_external_extra_trees      |   73 |       -0.00677002  |       0.227779   |       0.753425 |
| 7000_inf     | external_downstream_charge | shuffled_external_extra_trees    |   73 |        0.0305214   |       0.233615   |       0.712329 |

## Leakage Sentinels

| heldout_run   |   train_rows_duplicate_closure |   train_rows_external_calibration |   test_rows_external |   train_heldout_run_overlap |   exact_b2_waveform_hash_train_test_overlap | features_exclude                                                                           | odd_duplicate_channels_used_as_features   | downstream_target_used_as_feature   |   shuffled_external_res68 |   best_real_external_res68 |   best_to_shuffled_res68_ratio |   looks_too_good |
|:--------------|-------------------------------:|----------------------------------:|---------------------:|----------------------------:|--------------------------------------------:|:-------------------------------------------------------------------------------------------|:------------------------------------------|:------------------------------------|--------------------------:|---------------------------:|-------------------------------:|-----------------:|
| 58            |                         563437 |                              3702 |                   72 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| 59            |                         565664 |                              3025 |                  749 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| 60            |                         569361 |                              2972 |                  802 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| 61            |                         568212 |                              2849 |                  925 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| 62            |                         567593 |                              2976 |                  798 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| 63            |                         564663 |                              3409 |                  365 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| 65            |                         567459 |                              3711 |                   63 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                nan        |                 nan        |                     nan        |              nan |
| overall       |                         579227 |                              3774 |                 3774 |                           0 |                                           0 | run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge | False                                     | False                               |                  0.271892 |                   0.209636 |                       0.771027 |                0 |

## Finding

The odd-readout closure still looks excellent on the penetrating rows: Huber duplicate-charge res68 0.0685 and ExtraTrees duplicate-charge res68 0.0119. Against the external B4+B6+B8 target, the closure transfers are much broader: Huber-transfer res68 0.2445 [0.227357982984056, 0.28174599290916114] and ExtraTrees-transfer res68 0.2407 [0.22408338113017384, 0.2695656531795641]. The best even-only external model is direct_external_extra_trees at res68 0.2096, while the shuffled-target sentinel is 0.2719. This validates the P04d/P04e caution: same-event duplicate-readout closure does not become a precise penetrating-charge measurement when odd duplicate channels are excluded from features.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `p04d_reproduction_summary.csv`, `counts_by_run.csv`, `external_summary.csv`, `external_by_run.csv`, `external_by_b2_amp.csv`, `external_predictions.csv`, and `leakage_checks.csv`.

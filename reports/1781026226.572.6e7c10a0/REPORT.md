# P04j Charge-Transfer Conformal Uncertainty Calibration

- **Ticket:** `1781026226.572.6e7c10a0`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Split:** held-out run predictions; conformal residual quantiles use calibration runs only, never the held-out run.
- **Target:** selected A1/A3 positive-lobe charge on `(run, EVT)` rows with selected B2 and selected A1 or A3.

## Raw Reproduction First

B-stack S00 selected-pulse anchor: `640,737` vs `640,737`.

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

Event-matched A/B rows: `4,055` vs expected `4,055`. P04c reproduces broad point-transfer res68: traditional `0.5193` and waveform ExtraTrees `0.5202`.

## Point And Interval Metrics

| method                      | method_family   |    n |   bias_median_frac |   res68_abs_frac |   full_rms_frac |   within_25pct_rate |   coverage68 |   mean_width68_frac |   coverage90 |   mean_width90_frac |   abstention_rate |   retained_coverage90 |
|:----------------------------|:----------------|-----:|-------------------:|-----------------:|----------------:|--------------------:|-------------:|--------------------:|-------------:|--------------------:|------------------:|----------------------:|
| frozen_peak_loglinear       | traditional     | 4055 |        -0.0541561  |         0.519106 |        0.83982  |            0.345006 |     0.679901 |             1.04227 |     0.899383 |             2.16784 |          0.634525 |              0.883266 |
| integral_topology_ridge     | traditional     | 4055 |        -0.0550208  |         0.518408 |        0.837877 |            0.344266 |     0.681134 |             1.0456  |     0.90111  |             2.16472 |          0.604932 |              0.887016 |
| adaptive_template_ridge     | traditional     | 4055 |        -0.0554263  |         0.524897 |        0.849629 |            0.339581 |     0.683847 |             1.05693 |     0.899137 |             2.18055 |          0.616523 |              0.877814 |
| support_huber               | traditional     | 4055 |        -0.0280468  |         0.526058 |        0.880261 |            0.338348 |     0.684587 |             1.06232 |     0.896917 |             2.29462 |          0.78397  |              0.865297 |
| b_waveform_extra_trees      | ml              | 4055 |        -0.054387   |         0.518027 |        0.845653 |            0.344266 |     0.681874 |             1.04705 |     0.898397 |             2.15527 |          0.606905 |              0.880803 |
| topology_only_sentinel      | sentinel        | 4055 |        -0.0534165  |         0.519105 |        0.840477 |            0.339827 |   nan        |           nan       |   nan        |           nan       |        nan        |            nan        |
| run_family_sentinel         | sentinel        | 4055 |        -0.00402867 |         0.520743 |        0.894276 |            0.351665 |   nan        |           nan       |   nan        |           nan       |        nan        |            nan        |
| shuffled_target_extra_trees | sentinel        | 4055 |        -0.0580817  |         0.521997 |        0.853624 |            0.348459 |   nan        |           nan       |   nan        |           nan       |        nan        |            nan        |

ML-minus-adaptive-template run-block bootstrap CIs:

| delta                      | metric            |   ci95_low |    ci95_high |   point_delta |
|:---------------------------|:------------------|-----------:|-------------:|--------------:|
| ml_minus_adaptive_template | res68_abs_frac    | -0.0114827 | -0.000841191 |  -0.00687084  |
| ml_minus_adaptive_template | coverage90        | -0.0046953 |  0.00285958  |  -0.000739827 |
| ml_minus_adaptive_template | mean_width90_frac | -0.0543861 |  0.00129935  |  -0.0252745   |
| ml_minus_adaptive_template | abstention_rate   | -0.106262  |  0.0936615   |  -0.00961776  |

## Abstention Curve

| method                  |   max_half_width90_frac |   retained_n |   abstention_rate |   coverage90 |   mean_width90_frac |   res68_abs_frac |   within_25pct_rate |
|:------------------------|------------------------:|-------------:|------------------:|-------------:|--------------------:|-----------------:|--------------------:|
| adaptive_template_ridge |                    0.75 |          138 |         0.965968  |     0.869565 |             1.35678 |         0.471866 |            0.355072 |
| adaptive_template_ridge |                    1    |         1555 |         0.616523  |     0.877814 |             1.82458 |         0.52018  |            0.346624 |
| adaptive_template_ridge |                    1.25 |         3184 |         0.214797  |     0.885364 |             2.00478 |         0.52417  |            0.340138 |
| adaptive_template_ridge |                    1.5  |         3927 |         0.031566  |     0.896613 |             2.14888 |         0.525133 |            0.33919  |
| adaptive_template_ridge |                    2    |         4055 |         0         |     0.899137 |             2.18055 |         0.524897 |            0.339581 |
| b_waveform_extra_trees  |                    0.75 |          125 |         0.969174  |     0.872    |             1.39073 |         0.472506 |            0.336    |
| b_waveform_extra_trees  |                    1    |         1594 |         0.606905  |     0.880803 |             1.82196 |         0.5021   |            0.35069  |
| b_waveform_extra_trees  |                    1.25 |         3253 |         0.197781  |     0.887181 |             2.00367 |         0.516343 |            0.349216 |
| b_waveform_extra_trees  |                    1.5  |         3938 |         0.0288533 |     0.89614  |             2.12688 |         0.518571 |            0.343575 |
| b_waveform_extra_trees  |                    2    |         4055 |         0         |     0.898397 |             2.15527 |         0.518027 |            0.344266 |

## Support/Topology Summary

| stratum_category       | stratum               |    n |   n_runs |   traditional_res68_abs_frac |   traditional_coverage90 |   ml_res68_abs_frac |   ml_coverage90 |   ml_width90_frac | support_call          |
|:-----------------------|:----------------------|-----:|---------:|-----------------------------:|-------------------------:|--------------------:|----------------:|------------------:|:----------------------|
| anomaly_stratum        | broad_saturation_like | 2271 |       32 |                     0.526826 |                 0.899163 |            0.523987 |        0.896081 |           2.14379 | support_only_or_broad |
| anomaly_stratum        | late_tail_high        | 1349 |       32 |                     0.51748  |                 0.901408 |            0.510581 |        0.902891 |           2.21779 | support_only_or_broad |
| anomaly_stratum        | dropout_like          |  401 |       26 |                     0.534113 |                 0.897756 |            0.516906 |        0.902743 |           2.02572 | support_only_or_broad |
| b2_amp_bin             | 3000_5000             | 1212 |       31 |                     0.514945 |                 0.898515 |            0.51129  |        0.891914 |           2.17151 | support_only_or_broad |
| b2_amp_bin             | 5000_7000             |  953 |       30 |                     0.5268   |                 0.894019 |            0.526943 |        0.896118 |           2.03772 | support_only_or_broad |
| b2_amp_bin             | 7000_inf              |  920 |       28 |                     0.544392 |                 0.907609 |            0.536996 |        0.909783 |           2.39694 | support_only_or_broad |
| b2_amp_bin             | 1000_2000             |  496 |       26 |                     0.513391 |                 0.897177 |            0.503501 |        0.891129 |           1.93259 | calibrated_candidate  |
| b2_amp_bin             | 2000_3000             |  474 |       28 |                     0.521058 |                 0.896624 |            0.513378 |        0.905063 |           2.11407 | support_only_or_broad |
| downstream_coincidence | downstream_none       | 3889 |       32 |                     0.525762 |                 0.899203 |            0.518519 |        0.898431 |           2.15197 | support_only_or_broad |
| downstream_coincidence | downstream_one        |  109 |       21 |                     0.490939 |                 0.889908 |            0.510163 |        0.899083 |           2.21582 | low_support           |
| downstream_coincidence | downstream_multi      |   57 |       19 |                     0.514214 |                 0.912281 |            0.509818 |        0.894737 |           2.26469 | low_support           |
| saturation_stratum     | all_B_amp_lt7000      | 3134 |       32 |                     0.519264 |                 0.896618 |            0.515627 |        0.895022 |           2.08438 | support_only_or_broad |
| saturation_stratum     | any_B_amp_ge7000      |  921 |       28 |                     0.544362 |                 0.907709 |            0.536168 |        0.909881 |           2.39651 | support_only_or_broad |
| topology_pattern       | B2_only               | 3889 |       32 |                     0.525762 |                 0.899203 |            0.518519 |        0.898431 |           2.15197 | support_only_or_broad |
| topology_pattern       | B2_B4                 |  102 |       21 |                     0.482536 |                 0.892157 |            0.505595 |        0.901961 |           2.21721 | low_support           |
| topology_pattern       | B2_multi_downstream   |   57 |       19 |                     0.514214 |                 0.912281 |            0.509818 |        0.894737 |           2.26469 | low_support           |

## Leakage Audit

- Train/held-out run overlap: `0`.
- Conformal calibration residuals are computed on calibration runs excluded from both model fitting and held-out evaluation.
- Feature matrices exclude run id, event id, A-stack selected flags, A-stack charge, and the target.
- Topology-only sentinel res68: `0.5191`.
- Run-family sentinel res68: `0.5207`.
- Shuffled-target ExtraTrees res68: `0.5220`.
- Too-good flag: `False`.

## Finding

Conformal calibration gives high nominal coverage only by admitting very broad intervals. The global adaptive-template traditional model has res68 0.5249, 90% coverage 0.899, and mean 90% width 2.181 of charge. The ML waveform ExtraTrees model has res68 0.5180, coverage 0.898, and width 2.155. Candidate calibrated strata are ['B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none', '1000_2000', 'B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none'], but these are support-limited.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `p04j_method_metrics.csv`, `p04j_metric_ci.csv`, `p04j_ml_minus_traditional_ci.csv`, `p04j_abstention_curve.csv`, `p04j_support_summary.csv`, `p04j_fold_diagnostics.csv`, and `p04j_predictions.csv`.

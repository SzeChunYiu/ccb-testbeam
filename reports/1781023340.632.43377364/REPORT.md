# P12a: pulse-axis covariance atom table across pathology flags

- **Ticket:** 1781023340.632.43377364
- **Worker:** testbeam-laptop-4
- **Input:** raw B-stack ROOT plus frozen completed report artifacts
- **No Monte Carlo:** all atoms are computed from data or frozen report-derived thresholds

## Raw ROOT reproduction first

The script scans raw `h101/HRDv` before loading or writing study metrics. It uses even B-stack channels B2/B4/B6/B8, median samples 0-3 baseline, and `A > 1000 ADC`.

| quantity                                      |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses                 |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib events with selected pulse     |         239559 |       239559 |       0 |           0 | True   |
| sample_i_calib selected pulses                |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis events with selected pulse  |         243133 |       243133 |       0 |           0 | True   |
| sample_i_analysis selected pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2 selected pulses          |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4 selected pulses          |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6 selected pulses          |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8 selected pulses          |           1299 |         1299 |       0 |           0 | True   |
| sample_ii_calib events with selected pulse    |          12103 |        12103 |       0 |           0 | True   |
| sample_ii_calib selected pulses               |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis events with selected pulse |          89807 |        89807 |       0 |           0 | True   |
| sample_ii_analysis selected pulses            |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2 selected pulses         |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4 selected pulses         |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6 selected pulses         |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8 selected pulses         |           4506 |         4506 |       0 |           0 | True   |

## Axis prevalences

| axis                      |      n |    fraction |
|:--------------------------|-------:|------------:|
| pileup_score              | 359963 | 0.561795    |
| high_amplitude            | 183303 | 0.286081    |
| early_pretrigger_activity |  82028 | 0.128021    |
| adaptive_lowering         |  36057 | 0.0562743   |
| charge_transfer_error     |  32333 | 0.0504622   |
| timing_tail               |  19757 | 0.0308348   |
| saturation_boundary       |  16607 | 0.0259186   |
| delayed_peak              |  14713 | 0.0229626   |
| broad_template_mismatch   |    121 | 0.000188845 |

## Traditional covariance and matched contingency

Binary pathology axes are assigned in leave-one-run-out folds; charge-transfer thresholds are fit only on non-held-out runs. The traditional readout uses matched binary contingency odds ratios, mutual information, nuisance-residual robust covariance, and run/stave/amplitude-bin partial correlations.

Largest run-block bootstrapped log-odds associations:
| axis_a                    | axis_b                    |    value |   ci_low |   ci_high |
|:--------------------------|:--------------------------|---------:|---------:|----------:|
| adaptive_lowering         | early_pretrigger_activity | 13.6836  | 13.4711  |  13.8614  |
| saturation_boundary       | high_amplitude            | 11.4202  | 11.277   |  11.5621  |
| delayed_peak              | pileup_score              |  6.47069 |  6.04813 |   7.18001 |
| broad_template_mismatch   | pileup_score              | -5.74194 | -6.03477 |  -5.41346 |
| high_amplitude            | pileup_score              | -4.53684 | -4.73576 |  -4.27944 |
| early_pretrigger_activity | charge_transfer_error     |  3.38418 |  3.16387 |   3.58179 |
| adaptive_lowering         | charge_transfer_error     |  3.3072  |  3.03179 |   3.5858  |
| high_amplitude            | delayed_peak              | -2.67856 | -2.88254 |  -2.33314 |

Largest nuisance-residual partial correlations:
| axis_a                | axis_b                    |   partial_correlation |
|:----------------------|:--------------------------|----------------------:|
| adaptive_lowering     | early_pretrigger_activity |              0.515989 |
| high_amplitude        | pileup_score              |             -0.308804 |
| charge_transfer_error | early_pretrigger_activity |              0.229812 |
| adaptive_lowering     | charge_transfer_error     |              0.203206 |
| delayed_peak          | pileup_score              |              0.124599 |
| high_amplitude        | saturation_boundary       |              0.114869 |
| adaptive_lowering     | pileup_score              |             -0.111868 |
| charge_transfer_error | delayed_peak              |              0.08679  |

Downstream timing/charge deltas with run-block bootstrap CIs:
| axis                      | metric                           |     value |    ci_low |   ci_high |
|:--------------------------|:---------------------------------|----------:|----------:|----------:|
| charge_transfer_error     | charge_abs_residual_median_delta |  4.37379  |  4.27323  |  4.49101  |
| adaptive_lowering         | charge_abs_residual_median_delta |  2.48996  |  2.25507  |  2.73187  |
| early_pretrigger_activity | charge_abs_residual_median_delta |  1.49105  |  1.34511  |  1.64479  |
| broad_template_mismatch   | charge_abs_residual_median_delta | -0.901526 | -0.986535 |  1.42411  |
| charge_transfer_error     | downstream_sigma68_delta_ns      |  0.584771 |  0.520079 |  0.703249 |
| pileup_score              | downstream_sigma68_delta_ns      | -0.574667 | -0.635376 | -0.523735 |
| adaptive_lowering         | downstream_sigma68_delta_ns      | -0.51645  | -0.606133 | -0.416235 |
| broad_template_mismatch   | downstream_sigma68_delta_ns      | -0.487599 | -0.733132 |  0.23074  |
| timing_tail               | downstream_sigma68_delta_ns      | -0.426142 | -0.467437 | -0.377912 |
| saturation_boundary       | charge_abs_residual_median_delta |  0.374653 |  0.310547 |  0.428813 |

## ML method

The ML method is a sparse graphical model on nuisance-residualized axes plus a leave-one-run-out calibrated multi-label logistic classifier. Classifiers use the other axes only; target-defining continuous features, run id, event id, and pulse id are excluded. Shuffled-axis sentinels are trained with identical splits.

| target                    |    value |
|:--------------------------|---------:|
| adaptive_lowering         | 0.983111 |
| high_amplitude            | 0.885743 |
| saturation_boundary       | 0.88133  |
| charge_transfer_error     | 0.877161 |
| pileup_score              | 0.851317 |
| broad_template_mismatch   | 0.796916 |
| early_pretrigger_activity | 0.794369 |
| delayed_peak              | 0.77601  |
| timing_tail               | 0.582028 |

Calibration ECE and shuffled-axis sentinels are in `ml_multilabel_metrics.csv`; sparse precision edges are in `sparse_graphical_edges.csv`.

## Leakage audit

| check                                       |         value | pass   |
|:--------------------------------------------|--------------:|:-------|
| raw_reproduction_before_analysis            | 640737        | True   |
| leave_one_run_out_axis_assignment           |     33        | True   |
| ml_features_exclude_run_event_target_scores |      1        | True   |
| max_shuffled_axis_auc                       |      0.486287 | True   |
| max_nominal_auc                             |      0.983111 | True   |
| input_files_hashed                          |     41        | True   |

## Finding

The covariance is not one dominant pathology axis. The strongest associations are expected local ones: high amplitude with saturation-boundary structure, delayed peaks with pile-up-like secondary structure, and pretrigger/adaptive-lowering with charge residual tails. Broad-template mismatch is rare and anti-correlated with pile-up by construction because the P09-style broad flag excludes pile-up and saturation candidates. Nuisance-residual partial correlations are materially smaller than raw odds ratios, so downstream consumers should treat these flags as a coupled nuisance table rather than independent cuts.

Runtime: 472.9 s.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python3.7 scripts/p12a_1781023340_632_43377364_pulse_axis_covariance.py --config configs/p12a_1781023340_632_43377364_pulse_axis_covariance.json
```

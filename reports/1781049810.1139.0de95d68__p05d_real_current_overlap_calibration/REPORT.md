# P05d: real-current overlap score calibration curve

- **Ticket:** `1781049810.1139.0de95d68`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw HRD ROOT files in `data/root/root`; no simulation truth and no sorted-table shortcuts.
- **Split:** each source run is held out. High-current runs are scored with models trained only from low-current runs 46/47; low-current controls leave their own run out.
- **Winner rule:** lowest source-run-bootstrap mean synthetic secondary-fraction RMSE; real high-minus-low and leakage sentinels are reported as transfer diagnostics, not optimized.

## Reproduction gates

The P05a injected anchor and S10/S11 real-candidate gate were rerun from raw ROOT before the calibration benchmark. P05a reproduced a traditional time RMS of 13.902 ns and a compact-CNN time RMS of 9.496 ns with detection AP 0.8706.

| quantity                              |   report_value |    reproduced |       delta |   tolerance | pass   |
|:--------------------------------------|---------------:|--------------:|------------:|------------:|:-------|
| P05a selected B-stave pulses          |  640737        | 640737        |  0          |        0    | True   |
| P05a traditional heldout time RMS ns  |      13.8993   |     13.9019   |  0.00258964 |        0.05 | True   |
| P05a compact CNN heldout time RMS ns  |      10.0093   |      9.49613  | -0.51314    |        0.6  | True   |
| P05a compact CNN heldout detection AP |       0.868415 |      0.870599 |  0.00218439 |        0.01 | True   |

The P05a CNN time RMS is a retrained neural anchor and is kept as an environment-sensitivity diagnostic; the raw selected-pulse count gate remains exact.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

| quantity                                                   |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S11b traditional matched secondary fraction high-minus-low |      0.0180645 |    0.0171913 | -0.000873198 |       0.003 | True   |

## Estimands and equations

For an event waveform `x`, each method emits an overlap score `s(x)` and a secondary-fraction estimate `f(x)`. On synthetic held-out overlays the truth is `y in {0,1}` and `q = A2 / (A1 + A2)`. The primary calibration estimands are

```text
Brier = n^{-1} sum_i (s_i - y_i)^2
RMSE_q = sqrt(n^{-1} sum_i (f_i - q_i)^2)
q_i = alpha + beta f_i + epsilon_i
HML_f = sum_z w_z [ E(f | current=20 nA, z) - E(f | current=2 nA, z) ]
D = n^{-1} sum_i |rank(s_i) - rank(f_i)|
```

where `z` is the matched amplitude/lowering/topology stratum and `w_z` is the raw-count matching weight. CIs resample held-out source runs.

## Methods

- **Traditional:** frozen bounded two-pulse template fit. The first-pulse time and pulse separation are scanned; amplitudes and baseline are solved by least squares; the score is one-pulse to two-pulse SSE improvement.
- **Ridge:** logistic overlap classifier plus ridge secondary-fraction regressor on normalized samples and one-pulse residual features.
- **Gradient-boosted trees:** histogram gradient-boosted classifier/regressor on the same feature set.
- **MLP:** two-layer perceptron classifier/regressor on standardized features.
- **1D-CNN:** compact convolutional network over 18 normalized samples with detection and decomposition heads.
- **New architecture:** residual-shape ExtraTrees ensemble, chosen because it targets non-linear residual morphology without assuming smooth calibration.

## Calibration benchmark

Synthetic held-out secondary-fraction RMSE:

| method_label                               |    value |   ci_low |   ci_high |
|:-------------------------------------------|---------:|---------:|----------:|
| Histogram gradient-boosted trees           | 0.116159 | 0.108798 |  0.121065 |
| Multilayer perceptron                      | 0.187074 | 0.172198 |  0.201946 |
| Compact 1D-CNN                             | 0.138768 | 0.130513 |  0.144897 |
| Residual-shape ExtraTrees ensemble         | 0.122449 | 0.116137 |  0.126633 |
| Ridge/logistic linear calibration          | 0.171326 | 0.161112 |  0.181446 |
| Traditional bounded two-pulse template fit | 0.361434 | 0.354395 |  0.369227 |

Synthetic held-out overlap Brier score:

| method_label                               |    value |   ci_low |   ci_high |
|:-------------------------------------------|---------:|---------:|----------:|
| Histogram gradient-boosted trees           | 0.116008 | 0.105337 |  0.123421 |
| Multilayer perceptron                      | 0.137728 | 0.125714 |  0.148988 |
| Compact 1D-CNN                             | 0.149039 | 0.132549 |  0.160798 |
| Residual-shape ExtraTrees ensemble         | 0.145962 | 0.134824 |  0.153562 |
| Ridge/logistic linear calibration          | 0.171577 | 0.158469 |  0.181008 |
| Traditional bounded two-pulse template fit | 0.476494 | 0.47208  |  0.481025 |

Calibration slope `q = alpha + beta f`:

| method_label                               |     value |    ci_low |   ci_high |
|:-------------------------------------------|----------:|----------:|----------:|
| Histogram gradient-boosted trees           |  0.971737 |  0.94636  |  0.994796 |
| Multilayer perceptron                      |  0.511651 |  0.454339 |  0.575571 |
| Compact 1D-CNN                             |  0.848639 |  0.811836 |  0.888213 |
| Residual-shape ExtraTrees ensemble         |  1.08493  |  1.06091  |  1.10475  |
| Ridge/logistic linear calibration          |  0.614269 |  0.549178 |  0.67783  |
| Traditional bounded two-pulse template fit | -0.147294 | -0.160031 | -0.135102 |

Accepted-event recovery RMSE for `s >= 0.5`:

| method_label                               |    value |   ci_low |   ci_high |
|:-------------------------------------------|---------:|---------:|----------:|
| Histogram gradient-boosted trees           | 0.115969 | 0.107133 |  0.124879 |
| Multilayer perceptron                      | 0.210464 | 0.191007 |  0.229367 |
| Compact 1D-CNN                             | 0.128187 | 0.118443 |  0.136512 |
| Residual-shape ExtraTrees ensemble         | 0.109056 | 0.102942 |  0.114586 |
| Ridge/logistic linear calibration          | 0.197182 | 0.181326 |  0.211615 |
| Traditional bounded two-pulse template fit | 0.502157 | 0.499327 |  0.504734 |

## Real-current transfer

Matched high-minus-low secondary-fraction estimates:

| method_label                               |       value |      ci_low |    ci_high |   n_scored_events |
|:-------------------------------------------|------------:|------------:|-----------:|------------------:|
| Traditional bounded two-pulse template fit |  0.0171913  | -0.0139789  | 0.0459435  |              9522 |
| Ridge/logistic linear calibration          |  0.0181076  |  0.00771903 | 0.026739   |              9522 |
| Histogram gradient-boosted trees           |  0.00633135 |  0.00322051 | 0.00979252 |              9522 |
| Multilayer perceptron                      | -0.00242134 | -0.0105504  | 0.00603646 |              9522 |
| Compact 1D-CNN                             |  0.0175371  |  0.00917215 | 0.0244497  |              9522 |
| Residual-shape ExtraTrees ensemble         |  0.0071429  |  0.00263798 | 0.0126796  |              9522 |

Matched high-minus-low overlap-score estimates:

| method_label                               |      value |      ci_low |   ci_high |
|:-------------------------------------------|-----------:|------------:|----------:|
| Traditional bounded two-pulse template fit | 0.00854119 | -0.0279552  | 0.0444393 |
| Ridge/logistic linear calibration          | 0.0448231  |  0.0271002  | 0.063106  |
| Histogram gradient-boosted trees           | 0.0198312  |  0.00755644 | 0.0311988 |
| Multilayer perceptron                      | 0.00465981 | -0.0384263  | 0.0437316 |
| Compact 1D-CNN                             | 0.0562588  |  0.0226879  | 0.0888775 |
| Residual-shape ExtraTrees ensemble         | 0.0265032  |  0.011867   | 0.0414154 |

Overlap-score versus secondary-fraction rank discordance on real windows:

| method_label                               |     value |    ci_low |   ci_high |
|:-------------------------------------------|----------:|----------:|----------:|
| Traditional bounded two-pulse template fit | 0.0313246 | 0.0296291 | 0.0332458 |
| Ridge/logistic linear calibration          | 0.112512  | 0.104477  | 0.12058   |
| Histogram gradient-boosted trees           | 0.116528  | 0.112373  | 0.120996  |
| Multilayer perceptron                      | 0.236634  | 0.223828  | 0.248999  |
| Compact 1D-CNN                             | 0.0295    | 0.0256999 | 0.0350141 |
| Residual-shape ExtraTrees ensemble         | 0.0823953 | 0.0786681 | 0.0864741 |

## Systematics and leakage sentinels

| check                                                                | method                    |    value | flag   | note                                                                                                 |
|:---------------------------------------------------------------------|:--------------------------|---------:|:-------|:-----------------------------------------------------------------------------------------------------|
| traditional_template_fit_actual_current_auc_from_overlap_score       | traditional_template_fit  | 0.431737 | False  | Flagged if the score nearly identifies beam current by itself.                                       |
| traditional_template_fit_actual_current_auc_from_secondary_fraction  | traditional_template_fit  | 0.452428 | False  | Flagged if the secondary-fraction estimate nearly identifies beam current by itself.                 |
| ridge_actual_current_auc_from_overlap_score                          | ridge                     | 0.581243 | False  | Flagged if the score nearly identifies beam current by itself.                                       |
| ridge_actual_current_auc_from_secondary_fraction                     | ridge                     | 0.590833 | False  | Flagged if the secondary-fraction estimate nearly identifies beam current by itself.                 |
| gradient_boosted_trees_actual_current_auc_from_overlap_score         | gradient_boosted_trees    | 0.671231 | False  | Flagged if the score nearly identifies beam current by itself.                                       |
| gradient_boosted_trees_actual_current_auc_from_secondary_fraction    | gradient_boosted_trees    | 0.61572  | False  | Flagged if the secondary-fraction estimate nearly identifies beam current by itself.                 |
| mlp_actual_current_auc_from_overlap_score                            | mlp                       | 0.593327 | False  | Flagged if the score nearly identifies beam current by itself.                                       |
| mlp_actual_current_auc_from_secondary_fraction                       | mlp                       | 0.502848 | False  | Flagged if the secondary-fraction estimate nearly identifies beam current by itself.                 |
| one_d_cnn_actual_current_auc_from_overlap_score                      | one_d_cnn                 | 0.668315 | False  | Flagged if the score nearly identifies beam current by itself.                                       |
| one_d_cnn_actual_current_auc_from_secondary_fraction                 | one_d_cnn                 | 0.671803 | False  | Flagged if the secondary-fraction estimate nearly identifies beam current by itself.                 |
| residual_shape_extratrees_actual_current_auc_from_overlap_score      | residual_shape_extratrees | 0.617127 | False  | Flagged if the score nearly identifies beam current by itself.                                       |
| residual_shape_extratrees_actual_current_auc_from_secondary_fraction | residual_shape_extratrees | 0.621685 | False  | Flagged if the secondary-fraction estimate nearly identifies beam current by itself.                 |
| heldout_run_excluded_from_training                                   | all                       | 1        | False  | High-current runs are never in training; low-current controls leave the scored run out.              |
| identifier_features_excluded                                         | all                       | 1        | False  | Tabular/NN features exclude run, event number, current, group, downstream label, and stratum labels. |
| synthetic_train_source_runs_exclude_heldout                          | all                       | 1        | False  | Fold diagnostics record raw source runs used to make synthetic overlays.                             |

Main caveats: synthetic overlays are made from raw pulses and therefore test calibration closure, not particle-level truth; high-current pile-up can include support mixtures absent from low-current overlays; and the real high-minus-low metric is a transfer diagnostic rather than a direct truth-labelled secondary fraction.

## Verdict

Winner by the predeclared calibration criterion is Histogram gradient-boosted trees with synthetic secondary-fraction RMSE 0.11616 [0.10880, 0.12107]. On real matched windows its secondary-fraction high-minus-low transfer estimate is 0.00633 [0.00322, 0.00979], compared with the traditional template-fit estimate 0.01719 [-0.01398, 0.04594]. Raw-root reproduction gates pass and 0 leakage/current-identification sentinels flag. The result supports using the winner as a calibrated overlap diagnostic under this support policy, not as an unqualified particle-truth pile-up correction.

## Reproducibility

```bash
/home/billy/.tb-workers/testbeam-laptop-3/.venv-s04g-sys/bin/python scripts/p05d_1781049810_1139_0de95d68_real_current_overlap_calibration.py --config configs/p05d_1781049810_1139_0de95d68_real_current_overlap_calibration.json
```

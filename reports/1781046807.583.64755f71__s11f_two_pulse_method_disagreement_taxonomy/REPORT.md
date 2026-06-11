# S11f: two-pulse method-disagreement taxonomy

- **Ticket:** `1781046807.583.64755f71`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-11
- **Depends on:** S10c/S10f/S11b/S11d/S11e/P05c artifacts and raw B-stack ROOT.
- **Inputs:** raw B-stack ROOT runs 44-57 in `data/root/root`; no detector Monte Carlo.
- **Config:** `configs/s11f_1781046807_583_64755f71_disagreement_taxonomy.json`
- **Git commit:** `01aecae3ef2a27e7e64b2fb783b28393b90589d0`

## 0. Question

When traditional bounded-template two-pulse fits and low-current synthetic-overlay ML methods disagree on real high-current S10/S11 candidate windows, which class (traditional-only, ML-only, joint, or neither) carries the current-dependent topology excess, and is any ML/NN method worth using over the strong traditional baseline?

The primary endpoint was preregistered in the ticket before analysis: candidate-rate excess by disagreement class, recovered delay/area stability, topology-excess coverage, gallery precision/recall where available, and ML-minus-traditional deltas with source-run bootstrap 95% CIs.

## 1. Reproduction

The raw ROOT scan rebuilt 5838 selected low-current events and 237295 selected high-current events. The documented S10 topology fractions pass the +/-0.0015 tolerance before any model scoring.

| quantity                                 |   report_value |   reproduced |       delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.015588  | -1.247e-05  |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.0997e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.023124  |  2.4358e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.026806  |  6.296e-06  |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.7896e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.033414  |  1.4105e-05 |      0.0015 | True   |

## 2. Methods

Let `x_i` be an 18-sample, baseline-subtracted candidate waveform and `s_i` its source run. All learned methods are trained on low-current synthetic overlays only; predictions for every event in run `s_i` are made by a model for which `s_i` is excluded from the training set when it is a low-current run.

Traditional bounded fit. For stave `k`, a low-current empirical template `T_k(t)` is built from training runs. The one-pulse model minimizes

`SSE_1 = min_{a,b,t_1} ||x_i - a T_k(t_1) - b||_2^2`,

and the two-pulse model minimizes

`SSE_2 = min_{a_1,a_2,b,t_1,Delta} ||x_i - a_1 T_k(t_1) - a_2 T_k(t_1 + Delta) - b||_2^2`,

over the frozen S11b delay grid. The traditional score is `D_i = max(0, (SSE_1 - SSE_2) / SSE_1)` and the area proxy is `a_2/(a_1+a_2)`. The fixed candidate rule is `D_i >= 0.015` and secondary fraction >= 0.05.

ML/NN comparators. Ridge uses standardized logistic/ridge heads; gradient-boosted trees use shallow classifier/regressor pairs; MLP uses two hidden layers; the 1D-CNN uses two convolution blocks with dual probability/fraction heads. The new architecture is a consensus abstention ensemble that averages GBT/MLP/CNN probabilities and accepts only when the cross-model secondary-fraction standard deviation is in the lower 75% for the held-out run.

Calibration layer. Each ML method chooses its probability threshold on a source-run-held-out synthetic calibration subset using a conformal-style rule: accept the widest set whose synthetic bad fractional-error rate is <= 0.15, where bad means `|hat y_i - y_i| > 0.12`. That threshold is frozen before scoring real current windows.

Disagreement taxonomy. For each ML method, every real event is assigned to one of four mutually exclusive classes: `joint`, `traditional_only`, `ml_only`, or `neither`, comparing the fixed traditional accept flag to the fixed calibrated ML accept flag. Class rates are matched over the S10c amplitude x lowering x topology strata.

## 3. Head-to-head Method Benchmark

The winner is selected by the same operational score used in the precursor abstention benchmark: lower accepted one-pulse residual RMS proxy and bad-proxy rate are rewarded, while coverage and retention of the high-amplitude/large-lowering/broad-late support region are also rewarded. This is an operating-rule score, not a truth-level pile-up decomposition.

| method                        |   coverage |   coverage_ci_low |   coverage_ci_high |   accepted_time_residual_proxy_rms_ns |   accepted_time_residual_proxy_rms_ns_ci_low |   accepted_time_residual_proxy_rms_ns_ci_high |   bad_proxy_rate |   bad_proxy_rate_ci_low |   bad_proxy_rate_ci_high |   risk_coverage_delta_vs_traditional |   risk_coverage_delta_vs_traditional_ci_low |   risk_coverage_delta_vs_traditional_ci_high |
|:------------------------------|-----------:|------------------:|-------------------:|--------------------------------------:|---------------------------------------------:|----------------------------------------------:|-----------------:|------------------------:|-------------------------:|-------------------------------------:|--------------------------------------------:|---------------------------------------------:|
| cnn_1d_dual_head              |   0.079509 |         0.0022322 |           0.23666  |                                8.9629 |                                       7.052  |                                       27.479  |        0.014469  |               0         |                0.015531  |                             -0.35697 |                                    -0.43549 |                                     -0.19859 |
| consensus_abstention_ensemble |   0.066471 |         0.051378  |           0.084359 |                               11.581  |                                       9.7772 |                                       12.868  |        0.044231  |               0.016256  |                0.076093  |                             -0.36644 |                                    -0.38414 |                                     -0.34667 |
| gradient_boosted_trees        |   0.9063   |         0.88209   |           0.92987  |                                6.806  |                                       6.5763 |                                        7.1008 |        0.022708  |               0.019379  |                0.025688  |                              0.4549  |                                     0.43109 |                                      0.47833 |
| mlp                           |   0.97507  |         0.96399   |           0.98655  |                                6.3154 |                                       5.9435 |                                        6.7245 |        0.021369  |               0.018201  |                0.024385  |                              0.52355 |                                     0.51337 |                                      0.5362  |
| ridge_linear                  |   0.041289 |         0.035326  |           0.047723 |                               12.291  |                                      10.309  |                                       14.501  |        0.049536  |               0.02113   |                0.080543  |                             -0.39164 |                                    -0.4031  |                                     -0.37924 |
| traditional_template_fit      |   0.43385  |         0.42132   |           0.44704  |                                2.0931 |                                       2.0791 |                                        2.1101 |        0.0070713 |               0.0045993 |                0.0097106 |                              0       |                                     0       |                                      0       |

Named winner: **traditional_template_fit** with selection score 1.3309.

## 4. Disagreement-Class Bootstrap CIs

Rates below are matched-stratum high-current minus low-current contrasts. `topology_excess_coverage` is the class contrast divided by the matched S10 downstream excess of 0.02025.

| method                        | disagreement_class   |   low_rate |   high_rate |   high_minus_low |      ci_low |    ci_high |   topology_excess_coverage |
|:------------------------------|:---------------------|-----------:|------------:|-----------------:|------------:|-----------:|---------------------------:|
| cnn_1d_dual_head              | joint                |  0         |   0.043796  |       0.043796   |  0          |  0.13124   |                  2.163     |
| cnn_1d_dual_head              | ml_only              |  0         |   0.041849  |       0.041849   |  0.0011234  |  0.12165   |                  2.0668    |
| cnn_1d_dual_head              | neither              |  0.45068   |   0.41224   |      -0.03844    | -0.11584    |  0.021893  |                 -1.8984    |
| cnn_1d_dual_head              | traditional_only     |  0.54932   |   0.50212   |      -0.047205   | -0.15487    |  0.017692  |                 -2.3313    |
| consensus_abstention_ensemble | joint                |  0.0096369 |   0.021186  |       0.011549   | -0.00047248 |  0.024788  |                  0.57035   |
| consensus_abstention_ensemble | ml_only              |  0.0058733 |   0.016783  |       0.01091    |  0.0040365  |  0.014615  |                  0.53882   |
| consensus_abstention_ensemble | neither              |  0.44481   |   0.4373    |      -0.007501   | -0.038782   |  0.022118  |                 -0.37045   |
| consensus_abstention_ensemble | traditional_only     |  0.53968   |   0.52473   |      -0.014958   | -0.038753   |  0.0085145 |                 -0.73872   |
| gradient_boosted_trees        | joint                |  0.0080502 |   0.54591   |       0.53786    |  0.51602    |  0.56728   |                 26.563     |
| gradient_boosted_trees        | ml_only              |  0.003596  |   0.45409   |       0.45049    |  0.42375    |  0.4776    |                 22.248     |
| gradient_boosted_trees        | neither              |  0.44708   |   0         |      -0.44708    | -0.45704    | -0.43623   |                -22.08      |
| gradient_boosted_trees        | traditional_only     |  0.54127   |   0         |      -0.54127    | -0.54634    | -0.53602   |                -26.732     |
| mlp                           | joint                |  0.54932   |   0.54443   |      -0.0048922  | -0.033683   |  0.028874  |                 -0.24161   |
| mlp                           | ml_only              |  0.43898   |   0.45158   |       0.012595   | -0.027559   |  0.044767  |                  0.62202   |
| mlp                           | neither              |  0.011695  |   0.0025095 |      -0.0091857  | -0.012763   |  0.0031695 |                 -0.45365   |
| mlp                           | traditional_only     |  0         |   0.0014831 |       0.0014831  |  0          |  0.0041665 |                  0.073245  |
| ridge_linear                  | joint                |  0.0036701 |   0.0036991 |       2.9049e-05 | -0.0024683  |  0.0033652 |                  0.0014346 |
| ridge_linear                  | ml_only              |  0.0021168 |   0.007419  |       0.0053022  |  0.0028766  |  0.0070951 |                  0.26186   |
| ridge_linear                  | neither              |  0.44856   |   0.44667   |      -0.0018931  | -0.031719   |  0.024296  |                 -0.093493  |
| ridge_linear                  | traditional_only     |  0.54565   |   0.54221   |      -0.0034382  | -0.031289   |  0.026679  |                 -0.1698    |

## 5. Delay/Area Stability

The traditional delay is only physically defined for rows where the bounded fit converges; ML-only rows therefore use the learned secondary-fraction/area proxy for stability. Broad IQRs or NaN delays mean the class should be interpreted as a morphology score, not a resolved two-pulse recovery.

| method                        | disagreement_class   | group     |    n |   downstream_rate |   trad_delay_median_ns |   trad_delay_iqr_ns |   secondary_area_proxy_median |   secondary_area_proxy_iqr |
|:------------------------------|:---------------------|:----------|-----:|------------------:|-----------------------:|--------------------:|------------------------------:|---------------------------:|
| cnn_1d_dual_head              | joint                | high_20nA |  234 |          0.042735 |                     20 |         10          |                     0.5792    |                  0.097508  |
| cnn_1d_dual_head              | ml_only              | high_20nA |  388 |          0.043814 |                     30 |         20          |                     0.076144  |                  0.10176   |
| cnn_1d_dual_head              | neither              | high_20nA | 3695 |          0.08065  |                     30 |         20          |                     0.10538   |                  0.093236  |
| cnn_1d_dual_head              | neither              | low_2nA   |  346 |          0.040462 |                     30 |         10          |                     0.099239  |                  0.087265  |
| cnn_1d_dual_head              | traditional_only     | high_20nA | 2764 |          0.048842 |                     20 |         10          |                     0.58812   |                  0.10143   |
| cnn_1d_dual_head              | traditional_only     | low_2nA   |  396 |          0.020202 |                     20 |         10          |                     0.58586   |                  0.080397  |
| consensus_abstention_ensemble | joint                | high_20nA |   90 |          0.15556  |                     30 |          7.1054e-15 |                     0.59534   |                  0.056474  |
| consensus_abstention_ensemble | joint                | low_2nA   |    7 |          0        |                     20 |         10          |                     0.60151   |                  0.032465  |
| consensus_abstention_ensemble | ml_only              | high_20nA |  410 |          0.10976  |                     40 |         30          |                     0.12279   |                  0.079416  |
| consensus_abstention_ensemble | ml_only              | low_2nA   |   13 |          0.15385  |                    nan |        nan          |                     0.10465   |                  0.0087524 |
| consensus_abstention_ensemble | neither              | high_20nA | 3673 |          0.073509 |                     30 |         20          |                     0.066199  |                  0.062196  |
| consensus_abstention_ensemble | neither              | low_2nA   |  333 |          0.036036 |                     30 |         10          |                     0.049578  |                  0.036953  |
| consensus_abstention_ensemble | traditional_only     | high_20nA | 2908 |          0.045048 |                     20 |         10          |                     0.58697   |                  0.10289   |
| consensus_abstention_ensemble | traditional_only     | low_2nA   |  389 |          0.020566 |                     20 |         10          |                     0.58514   |                  0.081188  |
| gradient_boosted_trees        | joint                | high_20nA | 2998 |          0.048366 |                     20 |         10          |                     0.58737   |                  0.10185   |
| gradient_boosted_trees        | joint                | low_2nA   |    6 |          0        |                     30 |          7.5        |                     0.60036   |                  0.10527   |
| gradient_boosted_trees        | ml_only              | high_20nA | 4083 |          0.077149 |                     30 |         20          |                     0.093927  |                  0.0769    |
| gradient_boosted_trees        | ml_only              | low_2nA   |    3 |          0.66667  |                    nan |        nan          |                     0.29945   |                  0.098391  |
| gradient_boosted_trees        | neither              | low_2nA   |  343 |          0.034985 |                     30 |         10          |                     0.079918  |                  0.084392  |
| gradient_boosted_trees        | traditional_only     | low_2nA   |  390 |          0.020513 |                     20 |         10          |                     0.5855    |                  0.0792    |
| mlp                           | joint                | high_20nA | 2991 |          0.047476 |                     20 |         10          |                     0.58714   |                  0.10203   |
| mlp                           | joint                | low_2nA   |  396 |          0.020202 |                     20 |         10          |                     0.58586   |                  0.080397  |
| mlp                           | ml_only              | high_20nA | 3948 |          0.077508 |                     30 |         20          |                     0.04367   |                  0.18116   |
| mlp                           | ml_only              | low_2nA   |  293 |          0.044369 |                     30 |         10          |                     0.027451  |                  0.12312   |
| mlp                           | neither              | high_20nA |  135 |          0.066667 |                     50 |          7.5        |                     0.0031426 |                  0.37784   |
| mlp                           | neither              | low_2nA   |   53 |          0.018868 |                     50 |          0          |                     0         |                  0         |
| mlp                           | traditional_only     | high_20nA |    7 |          0.42857  |                     30 |          5          |                     0.61504   |                  0.015689  |
| ridge_linear                  | joint                | high_20nA |   18 |          0.33333  |                     30 |          7.1054e-15 |                     0.59069   |                  0.091035  |
| ridge_linear                  | joint                | low_2nA   |    2 |          0.5      |                     40 |         10          |                     0.56244   |                  0.072324  |
| ridge_linear                  | ml_only              | high_20nA |  293 |          0.12287  |                     40 |         12.5        |                     0.5244    |                  0.42354   |
| ridge_linear                  | ml_only              | low_2nA   |   10 |          0.1      |                     50 |          0          |                     0.45245   |                  0.3419    |
| ridge_linear                  | neither              | high_20nA | 3790 |          0.073615 |                     30 |         20          |                     0.058716  |                  0.12502   |
| ridge_linear                  | neither              | low_2nA   |  336 |          0.03869  |                     30 |         10          |                     0.050282  |                  0.10327   |
| ridge_linear                  | traditional_only     | high_20nA | 2980 |          0.046644 |                     20 |         10          |                     0.58737   |                  0.10192   |
| ridge_linear                  | traditional_only     | low_2nA   |  394 |          0.017766 |                     20 |         10          |                     0.58586   |                  0.0792    |

## 6. Gallery Precision/Recall Where Available

The available gallery is the S10f blinded morphology scan. It is not a complete truth table, so these rows are an external morphology cross-check only.

| method                        | disagreement_class   |   n_gallery |   two_pulse_like_precision |   two_pulse_like_recall |   artifact_like_fraction | note                                                                           |
|:------------------------------|:---------------------|------------:|---------------------------:|------------------------:|-------------------------:|:-------------------------------------------------------------------------------|
| cnn_1d_dual_head              | joint                |          82 |                   0.060976 |               0.0029326 |                  0.93902 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| cnn_1d_dual_head              | ml_only              |         222 |                   0.099099 |               0.012903  |                  0.9009  | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| cnn_1d_dual_head              | neither              |        2270 |                   0.10352  |               0.13783   |                  0.89648 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| cnn_1d_dual_head              | traditional_only     |        1283 |                   0.061574 |               0.046334  |                  0.93843 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| consensus_abstention_ensemble | joint                |          20 |                   0        |               0         |                  1       | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| consensus_abstention_ensemble | ml_only              |         256 |                   0.035156 |               0.0052786 |                  0.96484 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| consensus_abstention_ensemble | neither              |        2236 |                   0.11091  |               0.14545   |                  0.88909 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| consensus_abstention_ensemble | traditional_only     |        1345 |                   0.062454 |               0.049267  |                  0.93755 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| gradient_boosted_trees        | joint                |        1152 |                   0.056424 |               0.038123  |                  0.94358 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| gradient_boosted_trees        | ml_only              |        2253 |                   0.10919  |               0.14428   |                  0.89081 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| gradient_boosted_trees        | neither              |         239 |                   0.046025 |               0.0064516 |                  0.95397 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| gradient_boosted_trees        | traditional_only     |         213 |                   0.089202 |               0.011144  |                  0.9108  | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| mlp                           | joint                |        1365 |                   0.061538 |               0.049267  |                  0.93846 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| mlp                           | ml_only              |        2359 |                   0.10555  |               0.14604   |                  0.89445 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| mlp                           | neither              |         133 |                   0.06015  |               0.0046921 |                  0.93985 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| ridge_linear                  | joint                |           7 |                   0        |               0         |                  1       | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| ridge_linear                  | ml_only              |         197 |                   0.055838 |               0.0064516 |                  0.94416 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| ridge_linear                  | neither              |        2295 |                   0.10719  |               0.14428   |                  0.89281 | S10f blinded morphology gallery join by event_index/run; not full truth labels |
| ridge_linear                  | traditional_only     |        1358 |                   0.061856 |               0.049267  |                  0.93814 | S10f blinded morphology gallery join by event_index/run; not full truth labels |

## 7. Falsification and Leakage Checks

Falsification target: the joint class would have supported a redundant two-pulse interpretation only if its 95% CI covered a substantial fraction of the matched S10 downstream excess and the gallery precision was not dominated by artifact-like labels. A current-identifier leakage failure would also invalidate the learned methods.

| check                                                               |   value | pass   | note                                                                                                       |
|:--------------------------------------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------------------------------|
| raw_root_reproduction_pass                                          | 1       | True   | S10 topology fractions are rebuilt directly from raw ROOT before any scoring.                              |
| source_run_heldout_scoring                                          | 1       | True   | High-current folds train only on low-current runs; low-current controls leave their source run out.        |
| identifier_features_excluded                                        | 1       | True   | ML features are waveform and residual summaries; run/event/current labels are added only after prediction. |
| cnn_1d_dual_head_current_auc_from_secondary_prediction              | 0.47124 | True   | Fails if the method score is almost a current identifier.                                                  |
| consensus_abstention_ensemble_current_auc_from_secondary_prediction | 0.51318 | True   | Fails if the method score is almost a current identifier.                                                  |
| gradient_boosted_trees_current_auc_from_secondary_prediction        | 0.59966 | True   | Fails if the method score is almost a current identifier.                                                  |
| mlp_current_auc_from_secondary_prediction                           | 0.56682 | True   | Fails if the method score is almost a current identifier.                                                  |
| ridge_linear_current_auc_from_secondary_prediction                  | 0.57529 | True   | Fails if the method score is almost a current identifier.                                                  |
| traditional_template_fit_current_auc_from_secondary_prediction      | 0.44793 | True   | Fails if the method score is almost a current identifier.                                                  |
| cnn_1d_dual_head_synthetic_cal_auc_not_perfect                      | 0.86122 | True   | Near-perfect synthetic calibration AUC would trigger leakage review.                                       |
| gradient_boosted_trees_synthetic_cal_auc_not_perfect                | 0.96701 | True   | Near-perfect synthetic calibration AUC would trigger leakage review.                                       |
| mlp_synthetic_cal_auc_not_perfect                                   | 0.98567 | True   | Near-perfect synthetic calibration AUC would trigger leakage review.                                       |
| ridge_linear_synthetic_cal_auc_not_perfect                          | 0.94873 | True   | Near-perfect synthetic calibration AUC would trigger leakage review.                                       |

The p-value analogue used here is the run-block bootstrap CI against zero for each preregistered class contrast. Four classes times five ML comparators were examined; interpreting any individual positive class as discovery therefore requires Bonferroni-aware caution. The conclusion is based on the pattern of classes and support, not a post-hoc single-bin discovery claim.

## 8. Systematics and Caveats

- Benchmark/selection: the traditional comparator is the reviewed bounded two-pulse fit, not a weak threshold. The consensus method is selected by a frozen composite score inherited from the precursor real-current transfer benchmark.
- Data leakage: source-run holdout is enforced; identifiers/current labels are not model features; current-separability sentinels are reported.
- Metric misuse: real data have no constituent truth, so the residual RMS, bad-proxy rate, and gallery morphology are diagnostics rather than calibrated physical errors.
- Post-hoc selection: the disagreement classes and bootstrap unit are the ticket endpoints; all method families in the config are reported.
- Systematic uncertainty: bootstrap CIs cover run-to-run variation. They do not cover the full uncertainty of synthetic-overlay realism, gallery incompleteness, or the S16 lowering proxy.

## 9. Findings and Next Steps

The strongest operating-rule method is traditional_template_fit; its risk-coverage delta versus the traditional template fit is 0.0000 [0.0000, 0.0000]. The strongest supported disagreement class in the consensus learned comparator is ml_only with high-minus-low rate 0.01091 [0.00404, 0.01461], covering 0.54 of the matched S10 downstream excess. The joint class remains small and gallery precision is artifact-dominated, so the traditional and learned methods are not redundant views of a clean two-pulse population; the learned excess remains support-dependent morphology until a larger blinded gallery validates it.

Hypothesis: the positive current-dependent excess is mostly a support-dependent broad/late waveform morphology picked up by learned residual models, while the small joint class implies that clean template-resolved double pulses are not the dominant explanation of the S10 topology excess. A decisive falsification would require a larger blinded hand-scan targeted at ML-only high-current rows and matched low controls.

Queued follow-up proposed in `result.json`: S11h blinded ML-only gallery expansion, because it directly tests whether the class carrying the learned excess is genuine two-pulse morphology or detector-shape artifact.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11f_1781046807_583_64755f71_disagreement_taxonomy.py --config configs/s11f_1781046807_583_64755f71_disagreement_taxonomy.json
```

Runtime in this run was 557.61 s. Outputs: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_ranking.csv`, `disagreement_taxonomy_ci.csv`, `stability_by_class.csv`, `covariate_balance_by_class.csv`, `gallery_precision_recall.csv`, `event_method_scores.csv`, `taxonomy_event_pairs.csv`, and figures.

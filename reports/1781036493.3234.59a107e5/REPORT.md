# P05c: real-current abstention transfer

- **Ticket:** `1781036493.3234.59a107e5`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack ROOT files `data/root/root/hrdb_run_0044.root` through `hrdb_run_0057.root`; no Monte Carlo.
- **Split:** every score is produced for one held-out source run. High-current runs are scored from low-current runs 46 and 47; low-current controls leave their own source run out.
- **Bootstrap:** 500 resamples of held-out source runs within current group.

## Abstract

This study tests whether abstention ideas from P05b injection closures transfer to real high-current candidate windows. The primary observable is not truth-labelled pile-up recovery, because real data lack constituent truth. Instead, methods are compared on raw-ROOT candidate windows with run-held-out training, synthetic low-current calibration, matched high-minus-low secondary-fraction contrasts, and explicit retention of the high-amplitude/large-lowering/broad-late support region that a useful gate must not hide.

## Reproduction Gate

The raw ROOT loader rebuilt 5838 selected low-current events and 237295 selected high-current events. The documented S10 topology fractions are reproduced within the preregistered +/-0.0015 tolerance.

| quantity                                 | report_value | reproduced | delta      | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| low_2nA multi_stave_per_selected_event   | 0.0156       | 0.015588   | -1.247e-05 | 0.0015    | True |
| low_2nA three_stave_per_selected_event   | 0.0041       | 0.004111   | 1.0997e-05 | 0.0015    | True |
| low_2nA downstream_per_selected_event    | 0.0231       | 0.023124   | 2.4358e-05 | 0.0015    | True |
| high_20nA multi_stave_per_selected_event | 0.0268       | 0.026806   | 6.296e-06  | 0.0015    | True |
| high_20nA three_stave_per_selected_event | 0.0085       | 0.0085379  | 3.7896e-05 | 0.0015    | True |
| high_20nA downstream_per_selected_event  | 0.0334       | 0.033414   | 1.4105e-05 | 0.0015    | True |

## Methods

Let x_i be the normalized 18-sample candidate waveform and z_i the template-residual feature vector. For ML methods, low-current pulses are synthetically overlaid to form labels y_i in [0, 1], the injected secondary charge fraction, and c_i in {0,1}, the overlap indicator.

Traditional template fit. A low-current median template T_s(t) is built by stave s. For a candidate waveform w, the one-pulse model minimizes ||w - aT_s(t_1) - b||_2^2, and the two-pulse model minimizes ||w - a_1T_s(t_1) - a_2T_s(t_1 + Delta) - b||_2^2 over the frozen S11b delay grid. The score is (SSE_1 - SSE_2)/SSE_1, and the reported secondary fraction is a_2/(a_1+a_2).

Ridge. A standardized linear ridge regressor estimates y_i from [x_i, z_i], with a logistic linear classifier for the overlap probability p_i.

Gradient-boosted trees. Shallow gradient-boosted classifier/regressor pairs model p_i and y_i with nonlinear residual interactions.

MLP. A two-hidden-layer perceptron classifier/regressor pair sees the same waveform and residual features.

1D-CNN. A small dual-head convolutional network applies two 1D convolution blocks to the normalized waveform samples, then predicts p_i and y_i with shared latent features.

Consensus abstention ensemble. The new architecture combines the tree, MLP, CNN, and traditional secondary-fraction predictions. It accepts only when the mean overlap probability is at least 0.5 and the model-disagreement standard deviation is in the lower 75% for the held-out run.

Synthetic calibration chooses each ML method's probability threshold on low-current synthetic calibration windows to target bad fractional-error rate <= 0.15, where bad means |hat y_i - y_i| > 0.12. These thresholds are then frozen before scoring real held-out windows.

## Metrics

For real windows, accepted-candidate secondary fraction is E[hat y | accept]. The time-residual proxy is 10 sqrt(mean(one_sse_norm)) ns over accepted events. The bad-recovery proxy rate is the accepted fraction simultaneously downstream, large-lowering (>200 ADC), and broad-late; it is a stress proxy, not truth. Charge-bias proxy is the high-current minus low-current accepted secondary contribution. The risk-coverage score is coverage x (1 - bad_proxy_rate), and the ML-minus-traditional delta subtracts the traditional template-fit score in each bootstrap draw.

## Overall Method Table

| method                        | coverage | abstention_rate | accepted_candidate_secondary_fraction | accepted_time_residual_proxy_rms_ns | bad_recovery_proxy_rate | high_amp_large_lowering_broad_late_retention |
| ----------------------------- | -------- | --------------- | ------------------------------------- | ----------------------------------- | ----------------------- | -------------------------------------------- |
| cnn_1d_dual_head              | 0.015566 | 0.98443         | 0.34942                               | 16.709                              | 0.022222                | 0.005923                                     |
| consensus_abstention_ensemble | 0.062839 | 0.93716         | 0.15565                               | 8.4762                              | 0.036697                | 0.1155                                       |
| gradient_boosted_trees        | 1        | 0               | 0.089213                              | 6.7912                              | 0.021561                | 1                                            |
| mlp                           | 0.96529  | 0.034705        | 0.097506                              | 6.0218                              | 0.022217                | 0.99112                                      |
| ridge_linear                  | 0.037703 | 0.9623          | 0.48364                               | 11.224                              | 0.045872                | 0.093781                                     |
| traditional_template_fit      | 0.43768  | 0.56232         | 0.52755                               | 2.0842                              | 0.0063224               | 0.25765                                      |

## Run-Block Bootstrap Contrasts

| method                        | accepted_secondary_high_minus_low | accepted_secondary_high_minus_low_ci_low | accepted_secondary_high_minus_low_ci_high | coverage_high_minus_low | coverage_high_minus_low_ci_low | coverage_high_minus_low_ci_high |
| ----------------------------- | --------------------------------- | ---------------------------------------- | ----------------------------------------- | ----------------------- | ------------------------------ | ------------------------------- |
| cnn_1d_dual_head              | 0.0057839                         | 0.0011195                                | 0.011349                                  | 0.0166                  | 0.0040623                      | 0.032134                        |
| consensus_abstention_ensemble | 0.0015909                         | -0.0039537                               | 0.0076153                                 | -0.026004               | -0.084228                      | 0.036864                        |
| gradient_boosted_trees        | 0.015627                          | 0.0021383                                | 0.031497                                  | 0                       | 0                              | 0                               |
| mlp                           | 0.015358                          | -0.0075139                               | 0.04372                                   | -0.026574               | -0.043466                      | -0.011505                       |
| ridge_linear                  | 0.0084583                         | 0.0038855                                | 0.012587                                  | 0.016762                | 0.0069656                      | 0.025929                        |
| traditional_template_fit      | -0.059838                         | -0.10095                                 | -0.027804                                 | -0.10213                | -0.17825                       | -0.043766                       |

## Metric Bootstrap CIs

| method                        | coverage | coverage_ci_low | coverage_ci_high | accepted_time_residual_proxy_rms_ns | accepted_time_residual_proxy_rms_ns_ci_low | accepted_time_residual_proxy_rms_ns_ci_high | bad_recovery_proxy_rate | bad_recovery_proxy_rate_ci_low | bad_recovery_proxy_rate_ci_high | charge_bias_proxy_high_minus_low | charge_bias_proxy_high_minus_low_ci_low | charge_bias_proxy_high_minus_low_ci_high | ml_minus_traditional_risk_coverage_delta | ml_minus_traditional_risk_coverage_delta_ci_low | ml_minus_traditional_risk_coverage_delta_ci_high |
| ----------------------------- | -------- | --------------- | ---------------- | ----------------------------------- | ------------------------------------------ | ------------------------------------------- | ----------------------- | ------------------------------ | ------------------------------- | -------------------------------- | --------------------------------------- | ---------------------------------------- | ---------------------------------------- | ----------------------------------------------- | ------------------------------------------------ |
| cnn_1d_dual_head              | 0.015566 | 0.0042025       | 0.031985         | 16.709                              | 8.6421                                     | 19.271                                      | 0.022222                | 0                              | 0.044463                        | 0.0059187                        | 0.0013878                               | 0.01209                                  | -0.41978                                 | -0.4348                                         | -0.40316                                         |
| consensus_abstention_ensemble | 0.062839 | 0.05376         | 0.071501         | 8.4762                              | 6.9857                                     | 9.6004                                      | 0.036697                | 0.017843                       | 0.056296                        | 0.0012019                        | -0.0039499                              | 0.007513                                 | -0.37421                                 | -0.39092                                        | -0.35778                                         |
| gradient_boosted_trees        | 1        | 1               | 1                | 6.7912                              | 6.5602                                     | 7.0495                                      | 0.021561                | 0.018651                       | 0.024165                        | 0.015008                         | 0.0018215                               | 0.031518                                 | 0.5437                                   | 0.5321                                          | 0.5555                                           |
| mlp                           | 0.96529  | 0.95248         | 0.97837          | 6.0218                              | 5.6131                                     | 6.4595                                      | 0.022217                | 0.0191                         | 0.025022                        | 0.014241                         | -0.0085035                              | 0.042702                                 | 0.50905                                  | 0.49615                                         | 0.52153                                          |
| ridge_linear                  | 0.037703 | 0.029735        | 0.046065         | 11.224                              | 9.1188                                     | 13.345                                      | 0.045872                | 0.0071796                      | 0.079768                        | 0.0087078                        | 0.0049638                               | 0.012537                                 | -0.39863                                 | -0.41205                                        | -0.38355                                         |
| traditional_template_fit      | 0.43768  | 0.42577         | 0.44906          | 2.0842                              | 2.0678                                     | 2.1014                                      | 0.0063224               | 0.004238                       | 0.0089007                       | -0.060841                        | -0.10233                                | -0.028059                                | 0                                        | 0                                               | 0                                                |

## Synthetic Calibration Diagnostics

| method                        | mean_threshold | mean_synthetic_cal_ap | mean_synthetic_cal_auc | mean_synthetic_frac_mae |
| ----------------------------- | -------------- | --------------------- | ---------------------- | ----------------------- |
| cnn_1d_dual_head              | 0.84747        | 0.9022                | 0.87667                | 0.11551                 |
| consensus_abstention_ensemble | 0.5            |                       |                        |                         |
| gradient_boosted_trees        | 0.05           | 0.9729                | 0.96701                | 0.064392                |
| mlp                           | 1.8853e-06     | 0.98854               | 0.98687                | 0.052079                |
| ridge_linear                  | 0.9714         | 0.95179               | 0.9451                 | 0.081038                |
| traditional_template_fit      | 0.015          |                       |                        |                         |

## Leakage and Systematics

| check                                                     | value   | pass | note                                                                                                                    |
| --------------------------------------------------------- | ------- | ---- | ----------------------------------------------------------------------------------------------------------------------- |
| raw_root_reproduction_pass                                | 1       | True | S10 topology fractions are rebuilt from raw ROOT before scoring.                                                        |
| heldout_run_scoring_policy                                | 1       | True | Each row is scored in a source-run-held-out fold; high-current folds train only on low-current runs.                    |
| identifier_features_excluded_from_ml                      | 1       | True | Model features are waveform and template residual features; run, event number, group, and current are not model inputs. |
| cnn_1d_dual_head_current_auc_from_prediction              | 0.27154 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| consensus_abstention_ensemble_current_auc_from_prediction | 0.43471 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| gradient_boosted_trees_current_auc_from_prediction        | 0.56801 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| mlp_current_auc_from_prediction                           | 0.52178 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| ridge_linear_current_auc_from_prediction                  | 0.58392 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| traditional_template_fit_current_auc_from_prediction      | 0.45374 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |

The dominant systematic is label mismatch: ML thresholds are calibrated on synthetic overlays, while the real-current sample has no constituent truth. The bootstrap captures run-to-run variation but not all model-form uncertainty. The support-retention column is therefore critical: an apparently clean gate that rejects the high-amplitude, large-lowering, broad-late support would not be operationally acceptable.

## Conclusion

The selected winner is **traditional_template_fit** by the prespecified composite of low accepted time-residual proxy, low bad-proxy rate, useful coverage, and retention of high-amplitude/large-lowering/broad-late support. The result supports cautious transfer of P05b-style abstention only as a real-data operating rule; it is not a truth-level decomposition of high-current pile-up.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p05c_1781036493_3234_59a107e5_real_current_abstention_transfer.py --config configs/p05c_1781036493_3234_59a107e5_real_current_abstention_transfer.json
```

Runtime in this run was 228.83 s.

# S11g: residual-pool two-pulse real-current transfer gate

- **Ticket:** `1781048230.616.2d7e4b56`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack ROOT files `data/root/root/hrdb_run_0044.root` through `hrdb_run_0057.root`; all synthetic labels are data overlays, not Monte Carlo.
- **Depends on:** S11e residual-pool conditioning (`reports/1781018533.1179.60a328c5`).
- **Split:** every real-window score is produced for one held-out source run. High-current runs are scored from low-current runs 46 and 47; low-current controls leave their own source run out.
- **Bootstrap:** 500 resamples of held-out source runs within current group.

## 0. Question

Do S11e's conditioned residual-pool gains on injected two-pulse recovery transfer to real high-current candidate windows without inflating failure, charge-bias, or support-drift proxies? The operational answer is a run-held-out gate, not a truth-level decomposition, because real high-current windows do not carry constituent labels.

## 1. Reproduction gate

The raw ROOT loader rebuilt 5838 selected low-current events and 237295 selected high-current events. The documented S10 topology fractions are reproduced within the preregistered +/-0.0015 tolerance.

| quantity                                 | report_value | reproduced | delta      | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| low_2nA multi_stave_per_selected_event   | 0.0156       | 0.015588   | -1.247e-05 | 0.0015    | True |
| low_2nA three_stave_per_selected_event   | 0.0041       | 0.004111   | 1.0997e-05 | 0.0015    | True |
| low_2nA downstream_per_selected_event    | 0.0231       | 0.023124   | 2.4358e-05 | 0.0015    | True |
| high_20nA multi_stave_per_selected_event | 0.0268       | 0.026806   | 6.296e-06  | 0.0015    | True |
| high_20nA three_stave_per_selected_event | 0.0085       | 0.0085379  | 3.7896e-05 | 0.0015    | True |
| high_20nA downstream_per_selected_event  | 0.0334       | 0.033414   | 1.4105e-05 | 0.0015    | True |

The S11e dependency is reproduced in its own raw-ROOT artifact: conditioned residual pools give traditional held-out RMS 17.36 ns and compact-MLP RMS 9.07 ns, gap 8.28 ns. S11g tests whether that synthetic advantage is usable on the real high-minus-low current candidate surface.

## 2. Traditional method

For stave s, amplitude tertile a, and tail-shape class h, the train-run-only empirical template is T_sah(j)=median_k[w_k(j+t_hat_k-t0)/max_j w_k(j)]. The one-pulse model is y(j)=A T_sah(j-t1)+b+epsilon_j. The two-pulse model is y(j)=A1 T_p(j-t1)+A2 T_q(j-t1-Delta)+b+epsilon_j, with p and q drawn from nearby amplitude/tail candidates, Delta scanned over the frozen S11e/S11c grid, and amplitudes plus baseline solved by constrained least squares. The gate score is (SSE_1-SSE_2)/SSE_1; the secondary-fraction estimator is A2/(A1+A2). A chi2/ndf proxy is recorded as SSE_2/(18-3) because per-sample electronic noise variance is not separately known in these reduced ROOT files.

## 3. ML and NN methods

Let x_i be the normalized 18-sample candidate waveform and z_i the one-pulse template-residual feature vector. Low-current pulses are synthetically overlaid to form labels y_i in [0,1], the injected secondary charge fraction, and c_i in {0,1}, the overlap indicator. Source run, event number, current, and stratum labels are excluded from model inputs.

Ridge uses a standardized logistic classifier for c_i and a ridge regressor for y_i.

Gradient-boosted trees use shallow boosted classifier/regressor pairs on the same feature set.

MLP uses two-hidden-layer classifier/regressor pairs.

The 1D-CNN is a dual-head convolutional network over the 18 normalized samples.

The new architecture is a consensus abstention ensemble: it averages the tree, MLP, CNN, and traditional secondary-fraction predictions, then accepts only when mean overlap probability is at least 0.5 and prediction-disagreement is in the lower 75% for the held-out run.

Synthetic calibration chooses each ML method's probability threshold on low-current synthetic calibration windows to target bad fractional-error rate <= 0.15, where bad means |hat y_i - y_i| > 0.12. These thresholds are then frozen before scoring real held-out windows.

## 4. Head-to-head metrics

For real windows, accepted-candidate secondary fraction is E[hat y | accept]. The time-residual proxy is 10 sqrt(mean(one_sse_norm)) ns over accepted events. The bad-recovery proxy rate is the accepted fraction simultaneously downstream, large-lowering (>200 ADC), and broad-late; it is a stress proxy, not truth. Charge-bias proxy is the high-current minus low-current accepted secondary contribution. The risk-coverage score is coverage x (1 - bad_proxy_rate), and the ML-minus-traditional delta subtracts the traditional template-fit score in each bootstrap draw.

## Overall Method Table

| method                        | coverage  | abstention_rate | accepted_candidate_secondary_fraction | accepted_time_residual_proxy_rms_ns | bad_recovery_proxy_rate | high_amp_large_lowering_broad_late_retention |
| ----------------------------- | --------- | --------------- | ------------------------------------- | ----------------------------------- | ----------------------- | -------------------------------------------- |
| cnn_1d_dual_head              | 0.0079557 | 0.99204         | 0.21239                               | 15.414                              | 0.072464                | 0.011846                                     |
| consensus_abstention_ensemble | 0.053384  | 0.94662         | 0.17105                               | 11.206                              | 0.034557                | 0.088845                                     |
| gradient_boosted_trees        | 0.77147   | 0.22853         | 0.086258                              | 6.9578                              | 0.021671                | 0.76111                                      |
| mlp                           | 0.84884   | 0.15116         | 0.097961                              | 6.5408                              | 0.022412                | 0.85884                                      |
| ridge_linear                  | 0.047273  | 0.95273         | 0.39705                               | 13.091                              | 0.043902                | 0.091807                                     |
| traditional_template_fit      | 0.59172   | 0.40828         | 0.48855                               | 3.298                               | 0.020265                | 0.47779                                      |

## Run-Block Bootstrap Contrasts

| method                        | accepted_secondary_high_minus_low | accepted_secondary_high_minus_low_ci_low | accepted_secondary_high_minus_low_ci_high | coverage_high_minus_low | coverage_high_minus_low_ci_low | coverage_high_minus_low_ci_high |
| ----------------------------- | --------------------------------- | ---------------------------------------- | ----------------------------------------- | ----------------------- | ------------------------------ | ------------------------------- |
| cnn_1d_dual_head              | 0.0017644                         | 0.00028798                               | 0.0038319                                 | 0.0081826               | 0.00080246                     | 0.020135                        |
| consensus_abstention_ensemble | 0.0071036                         | 0.0048259                                | 0.010059                                  | 0.043776                | 0.028027                       | 0.06432                         |
| gradient_boosted_trees        | -0.0041054                        | -0.029665                                | 0.022927                                  | -0.24554                | -0.50099                       | 0                               |
| mlp                           | 0.071595                          | 0.037178                                 | 0.10213                                   | 0.43785                 | -0.22043                       | 0.96664                         |
| ridge_linear                  | 0.013953                          | 0.0085348                                | 0.018824                                  | 0.012676                | -0.011206                      | 0.043933                        |
| traditional_template_fit      | -0.078074                         | -0.13133                                 | -0.032332                                 | -0.16335                | -0.28674                       | -0.057016                       |

## Metric Bootstrap CIs

| method                        | coverage  | coverage_ci_low | coverage_ci_high | accepted_time_residual_proxy_rms_ns | accepted_time_residual_proxy_rms_ns_ci_low | accepted_time_residual_proxy_rms_ns_ci_high | bad_recovery_proxy_rate | bad_recovery_proxy_rate_ci_low | bad_recovery_proxy_rate_ci_high | charge_bias_proxy_high_minus_low | charge_bias_proxy_high_minus_low_ci_low | charge_bias_proxy_high_minus_low_ci_high | ml_minus_traditional_risk_coverage_delta | ml_minus_traditional_risk_coverage_delta_ci_low | ml_minus_traditional_risk_coverage_delta_ci_high |
| ----------------------------- | --------- | --------------- | ---------------- | ----------------------------------- | ------------------------------------------ | ------------------------------------------- | ----------------------- | ------------------------------ | ------------------------------- | -------------------------------- | --------------------------------------- | ---------------------------------------- | ---------------------------------------- | ----------------------------------------------- | ------------------------------------------------ |
| cnn_1d_dual_head              | 0.0079557 | 0.00068969      | 0.019474         | 15.414                              | 5.5209                                     | 16.494                                      | 0.072464                | 0                              | 0.3                             | 0.0018062                        | 0.00028543                              | 0.00406                                  | -0.57278                                 | -0.58704                                        | -0.55901                                         |
| consensus_abstention_ensemble | 0.053384  | 0.038935        | 0.06973          | 11.206                              | 8.684                                      | 13.041                                      | 0.034557                | 0.014356                       | 0.060993                        | 0.007059                         | 0.0047504                               | 0.0098925                                | -0.52862                                 | -0.54562                                        | -0.50768                                         |
| gradient_boosted_trees        | 0.77147   | 0.53992         | 1                | 6.9578                              | 6.5903                                     | 7.3183                                      | 0.021671                | 0.017875                       | 0.026045                        | -0.0050719                       | -0.030732                               | 0.021675                                 | 0.172                                    | -0.053978                                       | 0.38913                                          |
| mlp                           | 0.84884   | 0.707           | 0.97308          | 6.5408                              | 6.0154                                     | 7.1278                                      | 0.022412                | 0.018948                       | 0.026102                        | 0.072331                         | 0.038013                                | 0.10024                                  | 0.2507                                   | 0.11164                                         | 0.36316                                          |
| ridge_linear                  | 0.047273  | 0.036269        | 0.059538         | 13.091                              | 10.736                                     | 15.027                                      | 0.043902                | 0.021044                       | 0.067828                        | 0.013732                         | 0.0087256                               | 0.018313                                 | -0.53484                                 | -0.55134                                        | -0.5164                                          |
| traditional_template_fit      | 0.59172   | 0.58034         | 0.60272          | 3.298                               | 3.2588                                     | 3.3388                                      | 0.020265                | 0.016497                       | 0.024233                        | -0.076247                        | -0.13067                                | -0.032436                                | 0                                        | 0                                               | 0                                                |

## Selection Score

The primary operating score is RMS + 18*bad_proxy_rate - 1.5*coverage - support_retention. This intentionally gives a low residual proxy and support retention priority over raw risk-coverage AUC. For example, MLP has a positive risk-coverage delta, but its accepted residual proxy RMS is roughly twice the traditional fit's value.

| method                        | selection_score | accepted_time_residual_proxy_rms_ns | bad_recovery_proxy_rate | coverage  | high_amp_large_lowering_broad_late_retention |
| ----------------------------- | --------------- | ----------------------------------- | ----------------------- | --------- | -------------------------------------------- |
| traditional_template_fit      | 2.2974          | 3.298                               | 0.020265                | 0.59172   | 0.47779                                      |
| mlp                           | 4.8121          | 6.5408                              | 0.022412                | 0.84884   | 0.85884                                      |
| gradient_boosted_trees        | 5.4296          | 6.9578                              | 0.021671                | 0.77147   | 0.76111                                      |
| consensus_abstention_ensemble | 11.659          | 11.206                              | 0.034557                | 0.053384  | 0.088845                                     |
| ridge_linear                  | 13.719          | 13.091                              | 0.043902                | 0.047273  | 0.091807                                     |
| cnn_1d_dual_head              | 16.695          | 15.414                              | 0.072464                | 0.0079557 | 0.011846                                     |

## Held-out Source-run Split

| run | group     | method                        | n_events | coverage  | accepted_secondary_fraction_mean | mean_probability |
| --- | --------- | ----------------------------- | -------- | --------- | -------------------------------- | ---------------- |
| 44  | high_20nA | cnn_1d_dual_head              | 473      | 0         |                                  | 0.27175          |
| 44  | high_20nA | consensus_abstention_ensemble | 473      | 0.038055  | 0.21352                          | 0.20188          |
| 44  | high_20nA | gradient_boosted_trees        | 473      | 1         | 0.084284                         | 0.25292          |
| 44  | high_20nA | mlp                           | 473      | 1         | 0.094281                         | 0.080969         |
| 44  | high_20nA | ridge_linear                  | 473      | 0.040169  | 0.41093                          | 0.21772          |
| 44  | high_20nA | traditional_template_fit      | 473      | 0.60465   | 0.48663                          | 0.59374          |
| 45  | high_20nA | cnn_1d_dual_head              | 720      | 0         |                                  | 0.25991          |
| 45  | high_20nA | consensus_abstention_ensemble | 720      | 0.031944  | 0.15509                          | 0.2147           |
| 45  | high_20nA | gradient_boosted_trees        | 720      | 1         | 0.090808                         | 0.24104          |
| 45  | high_20nA | mlp                           | 720      | 0.97639   | 0.10598                          | 0.14317          |
| 45  | high_20nA | ridge_linear                  | 720      | 0.047222  | 0.46945                          | 0.22921          |
| 45  | high_20nA | traditional_template_fit      | 720      | 0.59167   | 0.48723                          | 0.57834          |
| 46  | low_2nA   | cnn_1d_dual_head              | 308      | 0         |                                  | 0.26916          |
| 46  | low_2nA   | consensus_abstention_ensemble | 308      | 0.016234  | 0.18301                          | 0.16947          |
| 46  | low_2nA   | gradient_boosted_trees        | 308      | 1         | 0.056293                         | 0.20249          |
| 46  | low_2nA   | mlp                           | 308      | 1         | 0.041073                         | 0.036776         |
| 46  | low_2nA   | ridge_linear                  | 308      | 0.012987  | 0.59566                          | 0.15208          |
| 46  | low_2nA   | traditional_template_fit      | 308      | 0.86039   | 0.47712                          | 0.84792          |
| 47  | low_2nA   | cnn_1d_dual_head              | 504      | 0         |                                  | 0.34494          |
| 47  | low_2nA   | consensus_abstention_ensemble | 504      | 0.011905  | 0.20994                          | 0.21662          |
| 47  | low_2nA   | gradient_boosted_trees        | 504      | 1         | 0.082315                         | 0.24723          |
| 47  | low_2nA   | mlp                           | 504      | 0.0059524 | 0                                | 0.057693         |
| 47  | low_2nA   | ridge_linear                  | 504      | 0.051587  | 0.096355                         | 0.20258          |
| 47  | low_2nA   | traditional_template_fit      | 504      | 0.63889   | 0.49673                          | 0.63099          |
| 48  | high_20nA | cnn_1d_dual_head              | 720      | 0.016667  | 0.30781                          | 0.28551          |
| 48  | high_20nA | consensus_abstention_ensemble | 720      | 0.0625    | 0.17554                          | 0.21012          |
| 48  | high_20nA | gradient_boosted_trees        | 720      | 1         | 0.089728                         | 0.25814          |
| 48  | high_20nA | mlp                           | 720      | 0.99306   | 0.067268                         | 0.086721         |
| 48  | high_20nA | ridge_linear                  | 720      | 0.054167  | 0.44775                          | 0.24625          |
| 48  | high_20nA | traditional_template_fit      | 720      | 0.58194   | 0.48522                          | 0.57062          |
| 49  | high_20nA | cnn_1d_dual_head              | 720      | 0.069444  | 0.1683                           | 0.30188          |
| 49  | high_20nA | consensus_abstention_ensemble | 720      | 0.079167  | 0.14153                          | 0.23807          |
| 49  | high_20nA | gradient_boosted_trees        | 720      | 1         | 0.089626                         | 0.26116          |
| 49  | high_20nA | mlp                           | 720      | 0.93889   | 0.081957                         | 0.15118          |
| 49  | high_20nA | ridge_linear                  | 720      | 0.070833  | 0.50792                          | 0.26631          |
| 49  | high_20nA | traditional_template_fit      | 720      | 0.58194   | 0.50159                          | 0.56414          |
| 50  | high_20nA | cnn_1d_dual_head              | 672      | 0.0014881 | 0.40972                          | 0.21723          |
| 50  | high_20nA | consensus_abstention_ensemble | 672      | 0.034226  | 0.19722                          | 0.1933           |
| 50  | high_20nA | gradient_boosted_trees        | 672      | 1         | 0.090098                         | 0.24359          |
| 50  | high_20nA | mlp                           | 672      | 0.96131   | 0.15304                          | 0.11907          |
| 50  | high_20nA | ridge_linear                  | 672      | 0.041667  | 0.41629                          | 0.22006          |
| 50  | high_20nA | traditional_template_fit      | 672      | 0.57292   | 0.49265                          | 0.54503          |
| 51  | high_20nA | cnn_1d_dual_head              | 660      | 0         |                                  | 0.26421          |
| 51  | high_20nA | consensus_abstention_ensemble | 660      | 0.048485  | 0.17508                          | 0.197            |
| 51  | high_20nA | gradient_boosted_trees        | 660      | 1         | 0.073143                         | 0.23653          |
| 51  | high_20nA | mlp                           | 660      | 0.88182   | 0.079803                         | 0.090256         |
| 51  | high_20nA | ridge_linear                  | 660      | 0.040909  | 0.46445                          | 0.22603          |
| 51  | high_20nA | traditional_template_fit      | 660      | 0.57273   | 0.49843                          | 0.55744          |
| 52  | high_20nA | cnn_1d_dual_head              | 525      | 0.0019048 | 0.35136                          | 0.31114          |
| 52  | high_20nA | consensus_abstention_ensemble | 525      | 0.1219    | 0.12732                          | 0.27287          |
| 52  | high_20nA | gradient_boosted_trees        | 525      | 1         | 0.088533                         | 0.27547          |
| 52  | high_20nA | mlp                           | 525      | 0.97905   | 0.087722                         | 0.23201          |
| 52  | high_20nA | ridge_linear                  | 525      | 0.038095  | 0.56436                          | 0.2352           |
| 52  | high_20nA | traditional_template_fit      | 525      | 0.59238   | 0.49051                          | 0.57602          |
| 53  | high_20nA | cnn_1d_dual_head              | 636      | 0.0031447 | 0.37327                          | 0.28834          |
| 53  | high_20nA | consensus_abstention_ensemble | 636      | 0.12736   | 0.18402                          | 0.25839          |
| 53  | high_20nA | gradient_boosted_trees        | 636      | 0.028302  | 0.27932                          | 0.24914          |
| 53  | high_20nA | mlp                           | 636      | 0.10849   | 0.31335                          | 0.23769          |
| 53  | high_20nA | ridge_linear                  | 636      | 0.11006   | 0.25445                          | 0.32419          |
| 53  | high_20nA | traditional_template_fit      | 636      | 0.56761   | 0.47707                          | 0.53698          |
| 54  | high_20nA | cnn_1d_dual_head              | 656      | 0.0030488 | 0.31844                          | 0.26525          |
| 54  | high_20nA | consensus_abstention_ensemble | 656      | 0.02439   | 0.20684                          | 0.19578          |
| 54  | high_20nA | gradient_boosted_trees        | 656      | 1         | 0.084428                         | 0.23664          |
| 54  | high_20nA | mlp                           | 656      | 1         | 0.10961                          | 0.085451         |
| 54  | high_20nA | ridge_linear                  | 656      | 0.0060976 | 0.37356                          | 0.20734          |
| 54  | high_20nA | traditional_template_fit      | 656      | 0.57317   | 0.47756                          | 0.55137          |
| 55  | high_20nA | cnn_1d_dual_head              | 657      | 0         |                                  | 0.28938          |
| 55  | high_20nA | consensus_abstention_ensemble | 657      | 0.045662  | 0.14312                          | 0.21966          |
| 55  | high_20nA | gradient_boosted_trees        | 657      | 1         | 0.082623                         | 0.22939          |
| 55  | high_20nA | mlp                           | 657      | 0.99848   | 0.076091                         | 0.1402           |
| 55  | high_20nA | ridge_linear                  | 657      | 0.041096  | 0.3977                           | 0.20668          |
| 55  | high_20nA | traditional_template_fit      | 657      | 0.55251   | 0.48362                          | 0.53348          |
| 56  | high_20nA | cnn_1d_dual_head              | 702      | 0.0014245 | 0.40144                          | 0.28174          |
| 56  | high_20nA | consensus_abstention_ensemble | 702      | 0.049858  | 0.19305                          | 0.20607          |
| 56  | high_20nA | gradient_boosted_trees        | 702      | 0.011396  | 0.26714                          | 0.21827          |
| 56  | high_20nA | mlp                           | 702      | 0.9359    | 0.090685                         | 0.11821          |
| 56  | high_20nA | ridge_linear                  | 702      | 0.045584  | 0.38105                          | 0.20005          |
| 56  | high_20nA | traditional_template_fit      | 702      | 0.5755    | 0.49363                          | 0.55272          |
| 57  | high_20nA | cnn_1d_dual_head              | 720      | 0         |                                  | 0.25846          |
| 57  | high_20nA | consensus_abstention_ensemble | 720      | 0.038889  | 0.21756                          | 0.22275          |
| 57  | high_20nA | gradient_boosted_trees        | 720      | 0.069444  | 0.23622                          | 0.25212          |
| 57  | high_20nA | mlp                           | 720      | 0.97778   | 0.13142                          | 0.15767          |
| 57  | high_20nA | ridge_linear                  | 720      | 0.040278  | 0.44992                          | 0.26188          |
| 57  | high_20nA | traditional_template_fit      | 720      | 0.57917   | 0.48745                          | 0.56565          |

## Synthetic Calibration Diagnostics

| method                        | mean_threshold | mean_synthetic_cal_ap | mean_synthetic_cal_auc | mean_synthetic_frac_mae |
| ----------------------------- | -------------- | --------------------- | ---------------------- | ----------------------- |
| cnn_1d_dual_head              | 0.89012        | 0.8862                | 0.85714                | 0.11996                 |
| consensus_abstention_ensemble | 0.5            |                       |                        |                         |
| gradient_boosted_trees        | 0.17938        | 0.96859               | 0.96067                | 0.064521                |
| mlp                           | 0.14286        | 0.98676               | 0.9872                 | 0.05327                 |
| ridge_linear                  | 0.96526        | 0.94794               | 0.93982                | 0.081021                |
| traditional_template_fit      | 0.015          |                       |                        |                         |

## 5. Falsification, leakage, and systematics

| check                                                     | value   | pass | note                                                                                                                    |
| --------------------------------------------------------- | ------- | ---- | ----------------------------------------------------------------------------------------------------------------------- |
| raw_root_reproduction_pass                                | 1       | True | S10 topology fractions are rebuilt from raw ROOT before scoring.                                                        |
| heldout_run_scoring_policy                                | 1       | True | Each row is scored in a source-run-held-out fold; high-current folds train only on low-current runs.                    |
| identifier_features_excluded_from_ml                      | 1       | True | Model features are waveform and template residual features; run, event number, group, and current are not model inputs. |
| cnn_1d_dual_head_current_auc_from_prediction              | 0.35067 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| consensus_abstention_ensemble_current_auc_from_prediction | 0.44364 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| gradient_boosted_trees_current_auc_from_prediction        | 0.58018 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| mlp_current_auc_from_prediction                           | 0.56546 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| ridge_linear_current_auc_from_prediction                  | 0.60168 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |
| traditional_template_fit_current_auc_from_prediction      | 0.43449 | True | High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.              |

Pre-registered falsification: if an ML/NN gate improves the risk-coverage score but rejects the high-amplitude, large-lowering, broad-late support region or shows current-identification AUC above 0.95, the transfer claim is rejected. The dominant systematic is label mismatch: ML thresholds are calibrated on synthetic overlays, while the real-current sample has no constituent truth. The bootstrap captures run-to-run variation but not all model-form uncertainty, and proxy RMS is not a substitute for true constituent timing on real unresolved pile-up.

## 6. Findings and caveats

The selected winner is **traditional_template_fit** by the prespecified composite of low accepted time-residual proxy, low bad-proxy rate, useful coverage, and retention of high-amplitude/large-lowering/broad-late support. This is a real-data gate for downstream timing/charge consumers, not evidence that any model has measured the physical pile-up constituent distribution.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11g_1781048230_616_2d7e4b56_residual_pool_real_current_transfer.py --config configs/s11g_1781048230_616_2d7e4b56_residual_pool_real_current_transfer.json
```

Runtime in this run was 506.60 s.

# P06f: calibration-run frozen support thresholds for consumer deployment

**Ticket:** `1783640227.9868.547c3cd0`  
**Worker:** `testbeam-laptop-4`  
**Input raw ROOT:** `/home/billy/Desktop/test_beam/data/root/root`  
**S06b interval source:** `reports/1781054026.2063.38d35ceb__s06b_amplitude_energy_timing_support_closure`  
**Threshold calibration runs:** [58, 59, 60]  
**Deployment runs:** [61, 62, 63, 65] with run-block bootstrap CIs  
**Primary nominal calibration budget:** 10%

## Abstract

P06f tests whether the P06e consumer-score gains survive a deployable threshold policy: each method's support interval scale threshold is frozen on a calibration block before deployment rows are scored. The raw ROOT selected-pulse count is reproduced first. The frozen thresholds are then applied to disjoint deployment runs, benchmarked for a strong traditional support method and ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-conformal gated CNN, and joined to the existing PID and energy consumer scoreboards. The winner named in `result.json` is **phase_conformal_gated_cnn** with composite consumer loss **0.1256** under the calibration-frozen 10% nominal threshold policy.

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv`, reshapes each event into 8 channels by 18 samples, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Methods And Estimands

For event pair residuals from S06b, `r_i = tau_{i,a} - tau_{i,b}`, with `tau_{i,s}=t_{i,s}-x_s v_TOF`. Each method supplies an interval scale `sigma_hat_i`; the pull is `z_i=r_i/sigma_hat_i`. The interval metrics are

`sigma68(r) = (Q84(r)-Q16(r))/2`, `C68 = P(|z| <= 1)`, `C95 = P(|z| <= 1.96)`,

and the calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`, where ECE is a sigma-quantile coverage error. For method `m` and nominal budget `b`, P06f computes `theta_m(b)=Q_{1-b}({sigma_hat_i: i in calibration runs, method=m})` and applies `I(sigma_hat_i <= theta_m)` unchanged to deployment runs. The deployment abstention fraction is therefore an observed consequence, not forced to equal `b`.

The strong traditional comparator is S06b's S02/S03 analytic timing plus S04-style atom robust-width interval lookup. Learned comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-conformal gated CNN. PID propagation uses P08e all-pre-action run-held-out PID metrics; energy propagation uses P07k charge-closure/action-band metrics. The method map is stored in the config and in `consumer_method_map.csv`.

## Primary Calibration-Frozen 10% Benchmark

| method                    |    n |   calibration_abstain_fraction |   abstain_fraction |   sigma_hat_threshold_ns |   coverage68 |   coverage68_ci_low |   coverage68_ci_high |   coverage95 |   coverage95_ci_low |   coverage95_ci_high |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |
|:--------------------------|-----:|-------------------------------:|-------------------:|-------------------------:|-------------:|--------------------:|---------------------:|-------------:|--------------------:|---------------------:|-------------------:|--------------------------:|---------------------------:|-------------:|
| traditional               | 5951 |                       0.097729 |           0.088388 |                   1.768  |      0.34011 |             0.26052 |              0.41807 |      0.56797 |             0.46944 |              0.6555  |           0.77755  |                  0.68857  |                   0.84838  |       1.7003 |
| ridge                     | 5111 |                       0.10016  |           0.21706  |                   2.1195 |      0.43905 |             0.32714 |              0.57126 |      0.83682 |             0.76393 |              0.93156 |           0.18534  |                  0.065691 |                   0.26976  |       1.7061 |
| gradient_boosted_trees    | 5096 |                       0.10016  |           0.21936  |                   2.1871 |      0.45644 |             0.34512 |              0.59385 |      0.82025 |             0.74609 |              0.90986 |           0.20325  |                  0.055694 |                   0.30929  |       1.6837 |
| mlp                       | 5613 |                       0.10016  |           0.14017  |                   2.5142 |      0.47746 |             0.39269 |              0.55925 |      0.85979 |             0.80695 |              0.91955 |           0.15865  |                  0.061856 |                   0.23419  |       1.7174 |
| cnn1d                     | 5653 |                       0.10016  |           0.13404  |                   2.6355 |      0.43729 |             0.33818 |              0.52938 |      0.92694 |             0.90338 |              0.94837 |           0.13138  |                  0.064974 |                   0.22208  |       1.4    |
| phase_conformal_gated_cnn | 5433 |                       0.10016  |           0.16774  |                   2.8441 |      0.61403 |             0.54733 |              0.70653 |      0.95877 |             0.94727 |              0.97145 |           0.038586 |                  0.030405 |                   0.060468 |       1.402  |

## PID And Energy Consumer Join

| method                    | energy_method                         |   energy_charge_res68 |   energy_harm_rate | pid_method                            |   pid_roc_auc |   pid_average_precision |    pid_ece |
|:--------------------------|:--------------------------------------|----------------------:|-------------------:|:--------------------------------------|--------------:|------------------------:|-----------:|
| traditional               | traditional_run_family_duplicate_gate |              0.015407 |         0          | traditional_charge_depth_logistic     |       1       |                 1       | 0.00015007 |
| ridge                     | ML_ridge_logistic                     |              0.013098 |         0.0025238  | ML_ridge_waveform                     |       0.85132 |                 0.77875 | 0.031782   |
| gradient_boosted_trees    | ML_gradient_boosted_trees             |              0.013921 |         0.00014647 | ML_gradient_boosted_trees             |       0.92801 |                 0.89427 | 0.034018   |
| mlp                       | ML_mlp                                |              0.015574 |         5.6335e-05 | ML_mlp                                |       0.94709 |                 0.92213 | 0.013142   |
| cnn1d                     | NN_1d_cnn                             |              0.019434 |         0.057028   | NN_1d_cnn                             |       0.72677 |                 0.6389  | 0.14087    |
| phase_conformal_gated_cnn | NN_residual_gated_cnn_new             |              0.012581 |         0.016906   | NN_action_gated_residual_ensemble_new |       1       |                 1       | 0.0018029  |

## Winner Score

| method                    |   consumer_loss |   calibration_loss |   coverage68_error |   coverage95_error |   energy_charge_res68 |   energy_harm_rate |   pid_roc_auc |    pid_ece |
|:--------------------------|----------------:|-------------------:|-------------------:|-------------------:|----------------------:|-------------------:|--------------:|-----------:|
| phase_conformal_gated_cnn |         0.12556 |           0.038586 |           0.068664 |          0.0087705 |              0.012581 |         0.016906   |       1       | 0.0018029  |
| mlp                       |         0.39582 |           0.15865  |           0.20523  |          0.09021   |              0.015574 |         5.6335e-05 |       0.94709 | 0.013142   |
| ridge                     |         0.48084 |           0.18534  |           0.24364  |          0.11318   |              0.013098 |         0.0025238  |       0.85132 | 0.031782   |
| gradient_boosted_trees    |         0.50813 |           0.20325  |           0.22625  |          0.12975   |              0.013921 |         0.00014647 |       0.92801 | 0.034018   |
| cnn1d                     |         0.63713 |           0.13138  |           0.2454   |          0.023059  |              0.019434 |         0.057028   |       0.72677 | 0.14087    |
| traditional               |         1.3618  |           0.77755  |           0.34258  |          0.38203   |              0.015407 |         0          |       1       | 0.00015007 |

**Winner:** `phase_conformal_gated_cnn`. It is selected at the preregistered calibration-frozen 10% nominal threshold by minimum composite consumer loss, not by timing calibration alone.

## Retrospective Equal-Support Comparator

This table reuses the deployment rows to set an equal-support cutoff. It is not the deployment winner criterion; it quantifies how much the older P06e-style pooled thresholding helped or hurt relative to frozen calibration thresholds.

| method                    |    n |   abstain_fraction |   coverage68 |   coverage95 |   calibration_loss |   sigma68_ns |
|:--------------------------|-----:|-------------------:|-------------:|-------------:|-------------------:|-------------:|
| traditional               | 5896 |           0.096814 |      0.34006 |      0.56598 |           0.78811  |       1.695  |
| ridge                     | 5875 |           0.10003  |      0.45906 |      0.85294 |           0.13927  |       1.6892 |
| gradient_boosted_trees    | 5875 |           0.10003  |      0.47609 |      0.84085 |           0.16065  |       1.6282 |
| mlp                       | 5875 |           0.10003  |      0.488   |      0.86468 |           0.14278  |       1.7129 |
| cnn1d                     | 5875 |           0.10003  |      0.43472 |      0.9297  |           0.12781  |       1.4276 |
| phase_conformal_gated_cnn | 5875 |           0.10003  |      0.6177  |      0.96068 |           0.044498 |       1.4516 |

## Fixed-Budget Coverage Sensitivity

| method                    |   abstention_budget |   abstain_fraction |   coverage68 |   coverage68_minus_budget0 |   coverage95 |   coverage95_minus_budget0 |   calibration_loss |   calibration_loss_minus_budget0 |
|:--------------------------|--------------------:|-------------------:|-------------:|---------------------------:|-------------:|---------------------------:|-------------------:|---------------------------------:|
| traditional               |                 0   |           0        |      0.35524 |                  0         |      0.59467 |                  0         |           0.69896  |                        0         |
| ridge                     |                 0   |           0        |      0.47748 |                  0         |      0.85754 |                  0         |           0.11763  |                        0         |
| gradient_boosted_trees    |                 0   |           0        |      0.4856  |                  0         |      0.84988 |                  0         |           0.13789  |                        0         |
| mlp                       |                 0   |           0        |      0.51333 |                  0         |      0.8727  |                  0         |           0.11404  |                        0         |
| cnn1d                     |                 0   |           0        |      0.43214 |                  0         |      0.93367 |                  0         |           0.11447  |                        0         |
| phase_conformal_gated_cnn |                 0   |           0        |      0.62485 |                  0         |      0.96186 |                  0         |           0.051487 |                        0         |
| traditional               |                 0.1 |           0.088388 |      0.34011 |                 -0.015128  |      0.56797 |                 -0.026697  |           0.77755  |                        0.078592  |
| ridge                     |                 0.1 |           0.21706  |      0.43905 |                 -0.038429  |      0.83682 |                 -0.020714  |           0.18534  |                        0.06771   |
| gradient_boosted_trees    |                 0.1 |           0.21936  |      0.45644 |                 -0.029164  |      0.82025 |                 -0.029626  |           0.20325  |                        0.065358  |
| mlp                       |                 0.1 |           0.14017  |      0.47746 |                 -0.035864  |      0.85979 |                 -0.012912  |           0.15865  |                        0.044612  |
| cnn1d                     |                 0.1 |           0.13404  |      0.43729 |                  0.0051515 |      0.92694 |                 -0.0067289 |           0.13138  |                        0.016909  |
| phase_conformal_gated_cnn |                 0.1 |           0.16774  |      0.61403 |                 -0.010821  |      0.95877 |                 -0.0030861 |           0.038586 |                       -0.012901  |
| traditional               |                 0.2 |           0.17816  |      0.32712 |                 -0.028119  |      0.53719 |                 -0.057484  |           0.86788  |                        0.16892   |
| ridge                     |                 0.2 |           0.34452  |      0.43562 |                 -0.041866  |      0.83174 |                 -0.0258    |           0.20657  |                        0.088937  |
| gradient_boosted_trees    |                 0.2 |           0.34727  |      0.44497 |                 -0.040635  |      0.79089 |                 -0.058983  |           0.25467  |                        0.11678   |
| mlp                       |                 0.2 |           0.27191  |      0.45824 |                 -0.05509   |      0.84052 |                 -0.03218   |           0.20378  |                        0.089745  |
| cnn1d                     |                 0.2 |           0.23162  |      0.4376  |                  0.0054612 |      0.91866 |                 -0.01501   |           0.14728  |                        0.032809  |
| phase_conformal_gated_cnn |                 0.2 |           0.28278  |      0.59761 |                 -0.027239  |      0.95301 |                 -0.0088451 |           0.045856 |                       -0.0056315 |

## Per-Run Stability

|   run | method                    |   abstain_fraction |   coverage68 |   coverage95 |   calibration_loss |   tail_frac_abs_gt5ns |
|------:|:--------------------------|-------------------:|-------------:|-------------:|-------------------:|----------------------:|
|    61 | cnn1d                     |           0.15434  |      0.33249 |      0.89945 |           0.22838  |            0.0046472  |
|    61 | gradient_boosted_trees    |           0.093605 |      0.33071 |      0.7367  |           0.32675  |            0.026803   |
|    61 | mlp                       |           0.080743 |      0.38399 |      0.80218 |           0.24124  |            0.026428   |
|    61 | phase_conformal_gated_cnn |           0.17685  |      0.5434  |      0.96788 |           0.062164 |            0.0052083  |
|    61 | ridge                     |           0.081458 |      0.31544 |      0.75418 |           0.28232  |            0.047063   |
|    61 | traditional               |           0.033583 |      0.25693 |      0.4658  |           0.84962  |            0.079852   |
|    62 | cnn1d                     |           0.13383  |      0.53743 |      0.94659 |           0.064179 |            0.0028612  |
|    62 | gradient_boosted_trees    |           0.33251  |      0.57364 |      0.89913 |           0.081877 |            0.0043317  |
|    62 | mlp                       |           0.18587  |      0.55657 |      0.90259 |           0.091592 |            0.007103   |
|    62 | phase_conformal_gated_cnn |           0.17059  |      0.70618 |      0.94522 |           0.042213 |            0.00099602 |
|    62 | ridge                     |           0.35523  |      0.56502 |      0.91352 |           0.085567 |            0.0057655  |
|    62 | traditional               |           0.14829  |      0.40446 |      0.65276 |           0.70264  |            0.014064   |
|    63 | cnn1d                     |           0.09009  |      0.47921 |      0.94554 |           0.1024   |            0.0029703  |
|    63 | gradient_boosted_trees    |           0.28468  |      0.59446 |      0.91058 |           0.056957 |            0.0025189  |
|    63 | mlp                       |           0.18288  |      0.56119 |      0.92613 |           0.061872 |            0.0088203  |
|    63 | phase_conformal_gated_cnn |           0.13964  |      0.57382 |      0.96021 |           0.051964 |            0.0052356  |
|    63 | ridge                     |           0.27477  |      0.5764  |      0.93665 |           0.058145 |            0.0012422  |
|    63 | traditional               |           0.095495 |      0.41733 |      0.65737 |           0.67482  |            0.018924   |

The complete per-run table is written to `interval_by_run.csv`; the displayed rows show that the bootstrap is over runs, not IID pulse pairs.

## Systematics And Caveats

- The timing intervals are frozen S06b intervals. P06f tests deployable thresholding and consumer propagation, not retraining.
- PID labels are P08e beamline/range enriched proxies, not hidden particle truth. Energy is a duplicate-charge closure proxy, not a calorimetric truth scale.
- Upstream S06b interval rows are only available for Sample-II analysis runs. Run 64 raw ROOT counts are reproduced, but no method-level run-64 sigma_hat rows exist in the frozen upstream table; therefore this study freezes thresholds on the early analysis calibration block 58-60 and deploys to runs 61-63 and 65.
- The abstention thresholds are fixed by calibration-run `sigma_hat`; they are not optimized against deployment residuals, PID, or energy scores. The deployment abstention fraction can drift away from the nominal budget.
- The deployment timing interval rows provide four run blocks. Bootstrap intervals quantify finite run sensitivity and should not be read as asymptotic standard errors.
- The new architecture is included because S06b already established phase/support gating as a sensible timing-interval architecture; P06f checks whether that advantage survives frozen-threshold consumer deployment.

## Conclusion

At the calibration-frozen 10% nominal support-threshold budget, phase_conformal_gated_cnn has the lowest composite consumer loss (0.1256) versus traditional 1.3618. Its timing interval calibration loss is 0.0386 [0.0304, 0.0605], with PID AUC 1.0000 and energy charge res68 0.0126. The result supports propagating the S06b support-conditioned gated timing intervals under a frozen deployment threshold, while keeping PID/energy interpretation proxy-limited.

No new follow-up ticket is appended by this study; the direct next step would be a prospective run-64 interval-scoring release so calibration thresholds can be frozen on the nominal calibration run rather than on the available early-analysis proxy block.

## Artifacts

`result.json`, `manifest.json`, `reproduction_match_table.csv`, `calibration_frozen_interval_summary.csv`, `retrospective_equal_support_summary.csv`, `interval_by_run.csv`, `coverage_improvement_by_budget.csv`, `consumer_method_map.csv`, `consumer_scoreboard.csv`, `winner_scoreboard.csv`, and `REPORT.md`.

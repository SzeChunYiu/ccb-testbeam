# P06e: support-conditioned timing interval propagation to PID and energy consumers

**Ticket:** `1781158601.1510.50fe016d`  
**Worker:** `testbeam-laptop-4`  
**Input raw ROOT:** `/home/billy/Desktop/test_beam/data/root/root`  
**S06b interval source:** `reports/1781054026.2063.38d35ceb__s06b_amplitude_energy_timing_support_closure`  
**Primary split:** complete held-out runs [58, 59, 60, 61, 62, 63, 65] with run-block bootstrap CIs  
**Primary abstention budget:** 10%

## Abstract

P06e asks whether the S06b support-conditioned timing intervals can be propagated into downstream PID and energy consumers without retuning the consumers. The raw ROOT selected-pulse count is reproduced before any consumer scoring. The fixed interval-abstention budgets are applied to the frozen S06b pair-residual panel, then the same method families are joined to the current PID and energy/action-band consumer scoreboards. The winner named in `result.json` is **phase_conformal_gated_cnn** with composite consumer loss **0.1298** at the 10% interval-abstention budget.

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

and the calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`, where ECE is a sigma-quantile coverage error. Fixed abstention budgets remove the largest `sigma_hat` rows for each method; the thresholds are frozen after choosing the budget and are not tuned to PID or energy outcomes.

The strong traditional comparator is S06b's S02/S03 analytic timing plus S04-style atom robust-width interval lookup. Learned comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and the new phase-conformal gated CNN. PID propagation uses P08e all-pre-action run-held-out PID metrics; energy propagation uses P07k charge-closure/action-band metrics. The method map is stored in the config and in `consumer_method_map.csv`.

## Primary 10% Interval-Abstention Benchmark

| method                    |     n |   abstain_fraction |   coverage68 |   coverage68_ci_low |   coverage68_ci_high |   coverage95 |   coverage95_ci_low |   coverage95_ci_high |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |
|:--------------------------|------:|-------------------:|-------------:|--------------------:|---------------------:|-------------:|--------------------:|---------------------:|-------------------:|--------------------------:|---------------------------:|-------------:|
| traditional               | 10336 |            0.09808 |      0.36784 |             0.30668 |              0.42014 |      0.60342 |             0.52657 |              0.66211 |           0.73935  |                  0.66662  |                   0.8201   |       1.5302 |
| ridge                     | 10314 |            0.1     |      0.46548 |             0.37931 |              0.55609 |      0.86814 |             0.80822 |              0.92259 |           0.13025  |                  0.066459 |                   0.21193  |       1.5513 |
| gradient_boosted_trees    | 10314 |            0.1     |      0.49263 |             0.40167 |              0.57668 |      0.8629  |             0.79646 |              0.91288 |           0.1295   |                  0.064152 |                   0.23338  |       1.5227 |
| mlp                       | 10314 |            0.1     |      0.49195 |             0.42938 |              0.54907 |      0.86882 |             0.83129 |              0.90674 |           0.13254  |                  0.078336 |                   0.19251  |       1.6285 |
| cnn1d                     | 10314 |            0.1     |      0.45676 |             0.37461 |              0.52821 |      0.93242 |             0.91678 |              0.94542 |           0.11136  |                  0.073292 |                   0.1746   |       1.381  |
| phase_conformal_gated_cnn | 10314 |            0.1     |      0.62372 |             0.56597 |              0.67264 |      0.95986 |             0.95292 |              0.96842 |           0.046535 |                  0.035361 |                   0.064538 |       1.387  |

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
| phase_conformal_gated_cnn |         0.12975 |           0.046535 |           0.058974 |          0.0098604 |              0.012581 |         0.016906   |       1       | 0.0018029  |
| mlp                       |         0.35343 |           0.13254  |           0.19074  |          0.081181  |              0.015574 |         5.6335e-05 |       0.94709 | 0.013142   |
| gradient_boosted_trees    |         0.37363 |           0.1295   |           0.19006  |          0.087095  |              0.013921 |         0.00014647 |       0.92801 | 0.034018   |
| ridge                     |         0.38121 |           0.13025  |           0.21721  |          0.08186   |              0.013098 |         0.0025238  |       0.85132 | 0.031782   |
| cnn1d                     |         0.6019  |           0.11136  |           0.22593  |          0.017578  |              0.019434 |         0.057028   |       0.72677 | 0.14087    |
| traditional               |         1.2743  |           0.73935  |           0.31485  |          0.34658   |              0.015407 |         0          |       1       | 0.00015007 |

**Winner:** `phase_conformal_gated_cnn`. It is selected at the preregistered 10% interval-abstention budget by minimum composite consumer loss, not by timing calibration alone.

## Fixed-Budget Coverage Sensitivity

| method                    |   abstention_budget |   abstain_fraction |   coverage68 |   coverage68_minus_budget0 |   coverage95 |   coverage95_minus_budget0 |   calibration_loss |   calibration_loss_minus_budget0 |
|:--------------------------|--------------------:|-------------------:|-------------:|---------------------------:|-------------:|---------------------------:|-------------------:|---------------------------------:|
| traditional               |                 0   |            0       |      0.38499 |                 0          |      0.63159 |                  0         |           0.65906  |                        0         |
| ridge                     |                 0   |            0       |      0.48106 |                 0          |      0.87173 |                  0         |           0.11002  |                        0         |
| gradient_boosted_trees    |                 0   |            0       |      0.50279 |                 0          |      0.86972 |                  0         |           0.10957  |                        0         |
| mlp                       |                 0   |            0       |      0.51693 |                 0          |      0.876   |                  0         |           0.10507  |                        0         |
| cnn1d                     |                 0   |            0       |      0.45454 |                 0          |      0.93613 |                  0         |           0.098049 |                        0         |
| phase_conformal_gated_cnn |                 0   |            0       |      0.63194 |                 0          |      0.96099 |                  0         |           0.053678 |                        0         |
| traditional               |                 0.1 |            0.09808 |      0.36784 |                -0.017151   |      0.60342 |                 -0.028163  |           0.73935  |                        0.080286  |
| ridge                     |                 0.1 |            0.1     |      0.46548 |                -0.015581   |      0.86814 |                 -0.0035874 |           0.13025  |                        0.020225  |
| gradient_boosted_trees    |                 0.1 |            0.1     |      0.49263 |                -0.010161   |      0.8629  |                 -0.006816  |           0.1295   |                        0.01993   |
| mlp                       |                 0.1 |            0.1     |      0.49195 |                -0.024976   |      0.86882 |                 -0.0071844 |           0.13254  |                        0.027462  |
| cnn1d                     |                 0.1 |            0.1     |      0.45676 |                 0.0022203  |      0.93242 |                 -0.0037037 |           0.11136  |                        0.013312  |
| phase_conformal_gated_cnn |                 0.1 |            0.1     |      0.62372 |                -0.0082218  |      0.95986 |                 -0.0011344 |           0.046535 |                       -0.0071438 |
| traditional               |                 0.2 |            0.1959  |      0.35355 |                -0.031437   |      0.57276 |                 -0.058826  |           0.84687  |                        0.18781   |
| ridge                     |                 0.2 |            0.2     |      0.45157 |                -0.029494   |      0.85918 |                 -0.012544  |           0.16237  |                        0.052353  |
| gradient_boosted_trees    |                 0.2 |            0.2     |      0.48211 |                -0.020681   |      0.84882 |                 -0.020899  |           0.16046  |                        0.050887  |
| mlp                       |                 0.2 |            0.2     |      0.47502 |                -0.041907   |      0.85493 |                 -0.021073  |           0.16618  |                        0.061106  |
| cnn1d                     |                 0.2 |            0.2     |      0.4555  |                 0.00095986 |      0.92463 |                 -0.011497  |           0.12641  |                        0.028365  |
| phase_conformal_gated_cnn |                 0.2 |            0.2     |      0.61366 |                -0.018281   |      0.95561 |                 -0.0053883 |           0.036134 |                       -0.017545  |

## Per-Run Stability

|   run | method                    |   abstain_fraction |   coverage68 |   coverage95 |   calibration_loss |   tail_frac_abs_gt5ns |
|------:|:--------------------------|-------------------:|-------------:|-------------:|-------------------:|----------------------:|
|    58 | cnn1d                     |           0.063927 |      0.37073 |      0.9561  |           0.13607  |             0         |
|    58 | gradient_boosted_trees    |           0.12785  |      0.46597 |      0.89529 |           0.10338  |             0.015707  |
|    58 | mlp                       |           0.13242  |      0.40526 |      0.87895 |           0.13089  |             0.0052632 |
|    58 | phase_conformal_gated_cnn |           0.077626 |      0.5297  |      0.9802  |           0.08531  |             0         |
|    58 | ridge                     |           0.03653  |      0.38389 |      0.90995 |           0.14754  |             0.0094787 |
|    58 | traditional               |           0.059361 |      0.3301  |      0.54854 |           1.1119   |             0.014563  |
|    59 | cnn1d                     |           0.072521 |      0.42581 |      0.93594 |           0.1241   |             0.0032972 |
|    59 | gradient_boosted_trees    |           0.034513 |      0.49457 |      0.88416 |           0.099749 |             0.0058824 |
|    59 | mlp                       |           0.073394 |      0.50354 |      0.87412 |           0.11358  |             0.008958  |
|    59 | phase_conformal_gated_cnn |           0.067278 |      0.637   |      0.95363 |           0.032018 |             0.0023419 |
|    59 | ridge                     |           0.021407 |      0.45179 |      0.87679 |           0.1457   |             0.0089286 |
|    59 | traditional               |           0.13805  |      0.43436 |      0.67663 |           0.62716  |             0.019767  |
|    60 | cnn1d                     |           0.092409 |      0.55136 |      0.93682 |           0.073835 |             0.0022727 |
|    60 | gradient_boosted_trees    |           0.075908 |      0.54955 |      0.9067  |           0.073679 |             0.0058036 |
|    60 | mlp                       |           0.087046 |      0.51197 |      0.87754 |           0.11283  |             0.0063263 |
|    60 | phase_conformal_gated_cnn |           0.072195 |      0.63895 |      0.96221 |           0.071548 |             0.0044464 |
|    60 | ridge                     |           0.082921 |      0.51777 |      0.90733 |           0.090504 |             0.0040486 |
|    60 | traditional               |           0.089934 |      0.38667 |      0.63871 |           0.71822  |             0.019039  |

The complete per-run table is written to `interval_by_run.csv`; the displayed rows show that the bootstrap is over runs, not IID pulse pairs.

## Systematics And Caveats

- The timing intervals are frozen S06b intervals. P06e tests propagation and abstention, not retraining.
- PID labels are P08e beamline/range enriched proxies, not hidden particle truth. Energy is a duplicate-charge closure proxy, not a calorimetric truth scale.
- The abstention thresholds are fixed by budget and `sigma_hat`; they are not optimized against PID or energy scores. This makes the test conservative but can hide a more efficient consumer-specific policy.
- The Sample-II timing interval rows provide seven held-out run blocks. Bootstrap intervals quantify finite run sensitivity and should not be read as asymptotic standard errors.
- The new architecture is included because S06b already established phase/support gating as a sensible timing-interval architecture; P06e only checks whether that advantage survives consumer propagation.

## Conclusion

At the fixed 10% interval-abstention budget, phase_conformal_gated_cnn has the lowest composite consumer loss (0.1298) versus traditional 1.2743. Its timing interval calibration loss is 0.0465 [0.0354, 0.0645], with PID AUC 1.0000 and energy charge res68 0.0126. The result supports propagating the S06b support-conditioned gated timing intervals as a consumer dry-run gate, while keeping PID/energy interpretation proxy-limited.

No new follow-up ticket is appended by this study; the direct next step would be a prospective consumer retraining with the P06e interval gate frozen, but the current evidence is sufficient for the claimed propagation dry run.

## Artifacts

`result.json`, `manifest.json`, `reproduction_match_table.csv`, `interval_abstention_summary.csv`, `interval_by_run.csv`, `coverage_improvement_by_budget.csv`, `consumer_method_map.csv`, `consumer_scoreboard.csv`, `winner_scoreboard.csv`, and `REPORT.md`.

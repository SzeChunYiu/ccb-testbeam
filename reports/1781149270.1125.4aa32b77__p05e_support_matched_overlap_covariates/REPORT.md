# P05e: support-matched overlap calibration with acquisition covariates

- **Ticket:** `1781149270.1125.4aa32b77`
- **Worker:** `testbeam-laptop-2`
- **Inputs:** raw B-stack HRD ROOT under `data/root/root` for reproduction; P05d run-heldout prediction artifacts for method scores.
- **Split:** source-run held-out P05d folds; uncertainty bootstraps held-out source runs.
- **Winner rule:** lowest source-run bootstrap support-conditioned loss: synthetic secondary-fraction RMSE plus absolute acquisition-covariate-adjusted high-minus-low transfer plus half the support-adjustment shift; leakage sentinels must not flag.

## Raw ROOT Reproduction

The S10 current/topology anchors were rebuilt directly from `HRDv` in raw ROOT using the same B2/B4/B6/B8 selected-pulse rule as P05d. The exact selected-event and selected-pulse totals are also compared with the upstream P05d raw-root artifact.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

| quantity                   |   upstream_p05d |   reproduced_from_raw_root |   delta |   tolerance | pass   |
|:---------------------------|----------------:|---------------------------:|--------:|------------:|:-------|
| P05d selected events total |          243133 |                     243133 |       0 |           0 | True   |
| P05d selected pulses total |          252266 |                     252266 |       0 |           0 | True   |

## Estimands

Let `x_i` be a selected-pulse waveform, `m` a method, `f_m(x_i)` its secondary-fraction estimate, and `s_m(x_i)` its overlap score. The synthetic closure term is inherited from the P05d run-heldout overlay benchmark:

```text
RMSE_m = sqrt(n^{-1} sum_i (f_m(x_i) - q_i)^2)
```

where `q_i = A2/(A1+A2)` is known only for synthetic overlays. The real support-transfer terms are

```text
Delta_support,m = sum_z w_z [ E(f_m | high, z) - E(f_m | low, z) ]
f_m = alpha + beta_m I_high + gamma_z + eta_r + b^T a_r + epsilon
L_m = RMSE_m + |beta_m| + 0.5 |beta_m - Delta_support,m|
```

Here `z` is the exact support cell `(amplitude bin, S16 lowering atom, P02 topology)`, `w_z` is the low/high overlap support weight, `eta_r` is a run-family fixed effect, and `a_r` are raw acquisition covariates from ROOT run counts: selected fraction, multi-stave fraction, downstream fraction, and log total events. The coefficient `beta_m` is the acquisition-covariate-adjusted high-minus-low transfer residual.

## Methods

- **Traditional:** constrained two-pulse template calibration within exact support cells.
- **Ridge:** logistic/ridge linear calibration from P05d.
- **Gradient-boosted trees:** histogram gradient-boosted classifier/regressor from P05d.
- **MLP:** two-layer perceptron from P05d.
- **1D-CNN:** compact 18-sample convolutional model from P05d.
- **New architecture:** monotone support-gated ensemble, `g(z) * GBT + (1-g(z)) * traditional`, where `g(z)` decreases for large S16 lowering, early pathology, and low-amplitude support and increases with matched support weight.

## Benchmark Results

| method_label                                            |   synthetic_secondary_fraction_rmse |   synthetic_rmse_ci_low |   synthetic_rmse_ci_high |   support_matched_high_minus_low |   support_matched_ci_low |   support_matched_ci_high |   acquisition_adjusted_high_minus_low |   adjusted_ci_low |   adjusted_ci_high |   support_conditioned_loss |   loss_ci_low |   loss_ci_high |
|:--------------------------------------------------------|------------------------------------:|------------------------:|-------------------------:|---------------------------------:|-------------------------:|--------------------------:|--------------------------------------:|------------------:|-------------------:|---------------------------:|--------------:|---------------:|
| Histogram gradient-boosted trees                        |                             0.11616 |                 0.1088  |                  0.12107 |                        0.0063314 |               0.003393   |                 0.0099728 |                              0.03884  |         -0.010139 |            0.1612  |                    0.17125 |       0.12269 |        0.39607 |
| Compact 1D-CNN                                          |                             0.13877 |                 0.13051 |                  0.1449  |                        0.017537  |               0.0085748  |                 0.025583  |                              0.047749 |         -0.34781  |            0.26759 |                    0.20162 |       0.14811 |        1.0949  |
| Ridge/logistic linear calibration                       |                             0.17133 |                 0.16111 |                  0.18145 |                        0.018108  |               0.0074417  |                 0.026686  |                              0.054891 |         -0.1758   |            0.21528 |                    0.24461 |       0.1836  |        0.70736 |
| Monotone support-gated ensemble                         |                             0.20953 |                 0.20229 |                  0.21553 |                        0.0081835 |              -0.00023533 |                 0.016522  |                              0.028324 |         -0.017768 |            0.12707 |                    0.24792 |       0.21724 |        0.47146 |
| Multilayer perceptron                                   |                             0.18707 |                 0.1722  |                  0.20195 |                       -0.0024213 |              -0.010979   |                 0.0058736 |                              0.10355  |         -0.85759  |            0.44778 |                    0.34361 |       0.1967  |        2.9109  |
| Traditional constrained two-pulse support-cell template |                             0.36143 |                 0.35439 |                  0.36923 |                        0.017191  |              -0.01204    |                 0.044659  |                              0.040485 |         -0.035967 |            0.14189 |                    0.41357 |       0.37075 |        0.61983 |

The winner is **Histogram gradient-boosted trees** with support-conditioned loss 0.17125 [0.12269, 0.39607].

## Support Atoms

| amp_bin       | baseline_bin       | p02_topology        |   n_low |   n_high |   winner_low_mean |   winner_high_mean |   winner_high_minus_low |   mean_support_gate |
|:--------------|:-------------------|:--------------------|--------:|---------:|------------------:|-------------------:|------------------------:|--------------------:|
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |     200 |     1200 |          0.024019 |           0.033792 |               0.0097733 |             0.77419 |
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |     200 |     1200 |          0.012576 |           0.015443 |               0.0028668 |             0.79208 |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |     199 |     1200 |          0.019243 |           0.030789 |               0.011546  |             0.70684 |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |     121 |     1200 |          0.11574  |           0.13914  |               0.023402  |             0.44517 |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |      51 |     1091 |          0.12775  |           0.097266 |              -0.030484  |             0.48943 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |      45 |      937 |          0.064601 |           0.069421 |               0.0048197 |             0.48885 |
| amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |      38 |      727 |          0.024846 |           0.040661 |               0.015815  |             0.59814 |
| amp_ge_4500   | s16_large_lowering | p02_broad_late      |      27 |     1086 |          0.096852 |           0.095829 |              -0.0010221 |             0.56686 |

## Systematics And Caveats

| check                                                               | method                          |    value | flag   | note                                                                                                                                                  |
|:--------------------------------------------------------------------|:--------------------------------|---------:|:-------|:------------------------------------------------------------------------------------------------------------------------------------------------------|
| traditional_template_fit_current_auc_from_overlap_score             | traditional_template_fit        | 0.431737 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| traditional_template_fit_current_auc_from_secondary_fraction        | traditional_template_fit        | 0.452428 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| ridge_current_auc_from_overlap_score                                | ridge                           | 0.581243 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| ridge_current_auc_from_secondary_fraction                           | ridge                           | 0.590833 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| gradient_boosted_trees_current_auc_from_overlap_score               | gradient_boosted_trees          | 0.671231 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| gradient_boosted_trees_current_auc_from_secondary_fraction          | gradient_boosted_trees          | 0.61572  | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| mlp_current_auc_from_overlap_score                                  | mlp                             | 0.593327 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| mlp_current_auc_from_secondary_fraction                             | mlp                             | 0.502848 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| one_d_cnn_current_auc_from_overlap_score                            | one_d_cnn                       | 0.668315 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| one_d_cnn_current_auc_from_secondary_fraction                       | one_d_cnn                       | 0.671803 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| monotone_support_gated_ensemble_current_auc_from_overlap_score      | monotone_support_gated_ensemble | 0.5573   | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| monotone_support_gated_ensemble_current_auc_from_secondary_fraction | monotone_support_gated_ensemble | 0.505298 | False  | Flag if a score is effectively a current/run identifier after support matching.                                                                       |
| identifier_features_excluded                                        | all                             | 1        | False  | P05d model features excluded run, event number, current, group, downstream label, and stratum labels; P05e uses these only for post-hoc conditioning. |

- The P05e adjustment does not create particle-truth labels; it tests whether P05d calibration is stable after raw support and acquisition conditioning.
- The monotone support-gated ensemble has a conservative synthetic RMSE bound because only P05d aggregate fold metrics, not row-level synthetic predictions, were materialized.
- Exact support matching reduces but does not remove unobserved current-dependent DAQ effects; therefore the adjusted high-minus-low term is a residual diagnostic, not a direct pile-up fraction.
- The high-current sample is much larger than the low-current reference support, so CIs are run-bootstrap intervals and do not include all model-retraining variance.

## Verdict

After exact support-cell matching and acquisition-covariate adjustment, Histogram gradient-boosted trees wins the P05e criterion with loss 0.17125 [0.12269, 0.39607]. The P05d winner (gradient_boosted_trees) remains calibrated enough to win: its adjusted secondary-fraction high-minus-low residual is 0.03884 [-0.01014, 0.16120], compared with the traditional support-cell template residual 0.04048 [-0.03597, 0.14189]. Raw-root reproduction gates pass, and 0 current-identification sentinels flag.

## Reproducibility

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/p05e_1781149270_1125_4aa32b77_support_matched_overlap_covariates.py --config configs/p05e_1781149270_1125_4aa32b77_support_matched_overlap_covariates.json
```

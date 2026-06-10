# S10m: overlap-secondary discordance audit

- **Ticket:** `1781032084.526.56a43973`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT `HRDv` under `data/root/root`.
- **Split:** all benchmark predictions are leave-one-low-current-run-out; real windows are scored by models that exclude the source run when the source run is low-current. Intervals use run-block bootstrap CIs.
- **Winner named in result.json:** `gradient_boosted_trees`.

## Abstract

The motivating discrepancy is that previous S10/S11 studies found a positive high-current excess in an ML overlap score, while the ML-estimated secondary fraction stayed near zero and the bounded two-pulse template fit reported a positive secondary-fraction excess. This audit separates three quantities: an overlap probability-like score \(p_i\), a recovered secondary fraction \(f_i = A_{2,i}/(A_{1,i}+A_{2,i})\), and a discordance indicator \(d_i = I[p_i \ge 0.5 \land f_i < 0.05]\). The headline result is that `gradient_boosted_trees` is the best synthetic run-held-out recovery model by the preregistered composite score, but the real-current discordance persists across methods and is concentrated in high-amplitude, adaptive-lowering, broad-late support.

## Raw-ROOT Reproduction Gate

The analysis first rebuilds the S10 current-topology counts directly from raw ROOT. Downstream selected-event fractions reproduce as 0.02312 at 2 nA and 0.03341 at 20 nA. The gate tolerance is +/-0.0015 against the documented S10 fractions; scoring aborts if any row fails.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

The S10f selected-pulse count gate is also rerun before fitting the S10f bounded-template baseline.

| quantity                                |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10f total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| S10f sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| S10f sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| S10f sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| S10f sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| S10f sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Methods

For event \(i\), waveform samples \(x_{it}\), and a train-run template \(T_s(t-\tau)\), the traditional one-pulse and two-pulse sums of squared error are

\[
SSE_1 = \min_{A,b,\tau} \sum_t [x_{it} - A T_s(t-\tau) - b]^2,
\]

\[
SSE_2 = \min_{A_1,A_2,b,\tau,\Delta} \sum_t [x_{it} - A_1 T_s(t-\tau) - A_2 T_s(t-\tau-\Delta) - b]^2,
\]

with positive amplitudes, bounded baseline, and the S10f amplitude-binned/asymmetric template library. The traditional score is the fractional SSE improvement and the traditional secondary fraction is \(A_2/(A_1+A_2)\), damped below the frozen S10g score threshold.

The ML methods use the same low-current synthetic overlays and exclude run id, event number, current group, downstream labels, and stratum labels:

- `ridge`: standardized waveform/residual features with ridge heads for overlap score and secondary fraction.
- `gradient_boosted_trees`: gradient-boosted classifier and regressor on the same tabular features.
- `mlp`: two-layer MLP classifier and regressor.
- `cnn_1d`: compact one-dimensional convolutional network on the normalized 18-sample waveform.
- `residual_cnn`: new architecture for this audit; it gives the CNN two channels, normalized waveform and one-pulse-template residual, so broad overlap-like residual morphology is explicit.

The run-block high-minus-low estimator for a metric \(m_i\) in matched stratum \(k\) is

\[
\Delta_m = \sum_k w_k\left(\bar m_{k,20\,nA}-\bar m_{k,2\,nA}\right),\qquad
w_k = \frac{\min(n_{k,20}, n_{k,2})}{\sum_j \min(n_{j,20}, n_{j,2})}.
\]

Bootstrap CIs resample source runs within current group, recomputing the weighted stratum contrast.

## Synthetic Run-Held-Out Benchmark

| method                       |   overlap_auc |   overlap_auc_ci_low |   overlap_auc_ci_high |    brier |   log_loss |   secondary_fraction_mae |   secondary_fraction_mae_ci_low |   secondary_fraction_mae_ci_high |   rank_score |
|:-----------------------------|--------------:|---------------------:|----------------------:|---------:|-----------:|-------------------------:|--------------------------------:|---------------------------------:|-------------:|
| gradient_boosted_trees       |      0.848567 |             0.845432 |              0.870593 | 0.160756 |   0.492142 |                 0.129076 |                        0.126898 |                         0.130159 |     0.719609 |
| ridge                        |      0.808157 |             0.808157 |              0.853495 | 0.179295 |   0.628676 |                 0.127941 |                        0.124892 |                         0.134072 |     0.676343 |
| mlp                          |      0.797426 |             0.787029 |              0.884534 | 0.186614 |   0.553918 |                 0.138386 |                        0.132178 |                         0.141474 |     0.656314 |
| traditional_bounded_template |      0.624322 |             0.601011 |              0.639316 | 0.229708 |   0.649761 |                 0.175528 |                        0.158197 |                         0.184146 |     0.446734 |
| residual_cnn                 |      0.647374 |             0.647374 |              0.690235 | 0.241277 |   0.675405 |                 0.207327 |                        0.172253 |                         0.224766 |     0.443623 |
| cnn_1d                       |      0.590821 |             0.590821 |              0.705176 | 0.248794 |   0.690726 |                 0.183941 |                        0.181044 |                         0.185382 |     0.403106 |

Per-fold metrics:

| method                       |   test_run |   n_test |   overlap_auc |   average_precision |    brier |   log_loss |   secondary_fraction_mae |   secondary_fraction_bias |
|:-----------------------------|-----------:|---------:|--------------:|--------------------:|---------:|-----------:|-------------------------:|--------------------------:|
| traditional_bounded_template |         47 |      720 |      0.601011 |            0.613133 | 0.233677 |   0.65881  |                 0.184146 |               -0.064753   |
| ridge                        |         47 |      720 |      0.815664 |            0.798937 | 0.182114 |   0.684296 |                 0.124892 |               -0.0371687  |
| gradient_boosted_trees       |         47 |      720 |      0.845432 |            0.859782 | 0.160439 |   0.49239  |                 0.130159 |               -0.00534387 |
| mlp                          |         47 |      720 |      0.787029 |            0.78612  | 0.200396 |   0.595804 |                 0.141474 |               -0.00499509 |
| cnn_1d                       |         47 |      720 |      0.672353 |            0.63342  | 0.249068 |   0.691267 |                 0.185382 |               -0.0527318  |
| residual_cnn                 |         47 |      720 |      0.657052 |            0.659931 | 0.245165 |   0.683449 |                 0.224766 |                0.167416   |
| traditional_bounded_template |         46 |      358 |      0.639316 |            0.639674 | 0.221726 |   0.631562 |                 0.158197 |               -0.0624232  |
| ridge                        |         46 |      358 |      0.853495 |            0.849877 | 0.173624 |   0.516815 |                 0.134072 |                0.040497   |
| gradient_boosted_trees       |         46 |      358 |      0.870593 |            0.873033 | 0.161394 |   0.491644 |                 0.126898 |                0.0277661  |
| mlp                          |         46 |      358 |      0.884534 |            0.899983 | 0.158897 |   0.469677 |                 0.132178 |                0.0442117  |
| cnn_1d                       |         46 |      358 |      0.705176 |            0.641835 | 0.248245 |   0.689637 |                 0.181044 |                0.00457811 |
| residual_cnn                 |         46 |      358 |      0.690235 |            0.664632 | 0.233457 |   0.659228 |                 0.172253 |               -0.0158651  |

The winner is `gradient_boosted_trees` with overlap AUC 0.849 [0.845, 0.871], Brier 0.1608, and secondary-fraction MAE 0.1291 [0.1269, 0.1302].

## Real High/Low-Current Discordance

| method                       | metric                 |         value |         ci_low |      ci_high |   n_scored_events |
|:-----------------------------|:-----------------------|--------------:|---------------:|-------------:|------------------:|
| traditional_bounded_template | secondary_fraction     |   0.0155618   |   -0.00851937  |   0.0361792  |              1745 |
| traditional_bounded_template | overlap_score          |   0.0360669   |   -0.00181802  |   0.0725269  |              1745 |
| traditional_bounded_template | candidate              |   0.0588905   |   -0.0095109   |   0.126932   |              1745 |
| traditional_bounded_template | discordant             |   0           |    0           |   0          |              1745 |
| traditional_bounded_template | secondary_charge_proxy | 167.457       |  -49.7197      | 393.595      |              1745 |
| ridge                        | secondary_fraction     |   0.0135836   |    0.0107615   |   0.016348   |              1745 |
| ridge                        | overlap_score          |   0.0262616   |    0.00435537  |   0.0490317  |              1745 |
| ridge                        | candidate              |   0.135497    |    0.0790518   |   0.199449   |              1745 |
| ridge                        | discordant             |   0.000132079 |   -0.00289957  |   0.00425073 |              1745 |
| ridge                        | secondary_charge_proxy |  91.4914      |   56.3751      | 126.057      |              1745 |
| gradient_boosted_trees       | secondary_fraction     |   0.00623119  |    0.000261074 |   0.0122846  |              1745 |
| gradient_boosted_trees       | overlap_score          |   0.0133957   |   -0.0154543   |   0.0445325  |              1745 |
| gradient_boosted_trees       | candidate              |   0.0297755   |    0.0129615   |   0.0464766  |              1745 |
| gradient_boosted_trees       | discordant             |   0           |    0           |   0          |              1745 |
| gradient_boosted_trees       | secondary_charge_proxy |  24.4107      |  -21.6769      |  68.0977     |              1745 |
| mlp                          | secondary_fraction     |   0.00749899  |   -0.0424017   |   0.0584299  |              1745 |
| mlp                          | overlap_score          |   0.0144912   |   -0.0444371   |   0.0729459  |              1745 |
| mlp                          | candidate              |   0.0387275   |   -0.0671239   |   0.14395    |              1745 |
| mlp                          | discordant             |  -0.0657042   |   -0.145931    |   0.0121245  |              1745 |
| mlp                          | secondary_charge_proxy |  73.2286      | -280.79        | 420.778      |              1745 |
| cnn_1d                       | secondary_fraction     |   0.000940387 |   -0.0219548   |   0.0232457  |              1745 |
| cnn_1d                       | overlap_score          |   0.000381124 |   -0.0163364   |   0.016505   |              1745 |
| cnn_1d                       | candidate              |  -0.420805    |   -0.846807    |   0          |              1745 |
| cnn_1d                       | discordant             |   0           |    0           |   0          |              1745 |
| cnn_1d                       | secondary_charge_proxy |  19.7995      | -115.788       | 157.322      |              1745 |
| residual_cnn                 | secondary_fraction     |  -0.00310566  |   -0.0817901   |   0.0781595  |              1745 |
| residual_cnn                 | overlap_score          |   0.00154683  |   -0.0431902   |   0.0458736  |              1745 |
| residual_cnn                 | candidate              |  -0.0783302   |   -0.285654    |   0.123701   |              1745 |
| residual_cnn                 | discordant             |   0           |    0           |   0          |              1745 |
| residual_cnn                 | secondary_charge_proxy |  10.3603      | -319.989       | 353.68       |              1745 |

Winner real-window diagnostics:

| method                 | metric             |      value |       ci_low |   ci_high |   n_scored_events |
|:-----------------------|:-------------------|-----------:|-------------:|----------:|------------------:|
| gradient_boosted_trees | secondary_fraction | 0.00623119 |  0.000261074 | 0.0122846 |              1745 |
| gradient_boosted_trees | overlap_score      | 0.0133957  | -0.0154543   | 0.0445325 |              1745 |
| gradient_boosted_trees | discordant         | 0          |  0           | 0         |              1745 |

Largest discordance-positive strata:

| method   | amp_bin       | baseline_bin       | p02_topology        |   low_n_scored |   high_n_scored |   high_minus_low |   match_weight |
|:---------|:--------------|:-------------------|:--------------------|---------------:|----------------:|-----------------:|---------------:|
| ridge    | amp_1000_2500 | s16_large_lowering | p02_early_pathology |             32 |             192 |       0.0520833  |     0.0230005  |
| mlp      | amp_ge_4500   | s16_large_lowering | p02_broad_late      |             19 |             192 |       0.0364583  |     0.00470465 |
| mlp      | amp_2500_4500 | s16_large_lowering | p02_early_pathology |             19 |             192 |       0.0104167  |     0.00888657 |
| mlp      | amp_1000_2500 | s16_no_lowering    | p02_broad_late      |             32 |             192 |       0.00520833 |     0.135738   |
| cnn_1d   | amp_ge_4500   | s16_large_lowering | p02_early_pathology |             22 |             192 |       0          |     0.00784109 |
| mlp      | amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |             21 |             192 |       0          |     0.00662136 |
| cnn_1d   | amp_ge_4500   | s16_no_lowering    | p02_broad_late      |             32 |             192 |       0          |     0.519603   |
| cnn_1d   | amp_2500_4500 | s16_no_lowering    | p02_broad_late      |             32 |             192 |       0          |     0.293605   |
| cnn_1d   | amp_1000_2500 | s16_no_lowering    | p02_broad_late      |             32 |             192 |       0          |     0.135738   |
| cnn_1d   | amp_1000_2500 | s16_large_lowering | p02_early_pathology |             32 |             192 |       0          |     0.0230005  |

## Run Stability

|   run | group     | method      |   candidate_rate |   mean_secondary_fraction |   mean_total_area_proxy_adc |
|------:|:----------|:------------|-----------------:|--------------------------:|----------------------------:|
|    44 | high_20nA | ml          |         0.28125  |                 0.180977  |                 1.40692e+07 |
|    45 | high_20nA | ml          |         0.265625 |                 0.177398  |                 1.1162e+07  |
|    48 | high_20nA | ml          |         0.273438 |                 0.170676  |                 1.2105e+07  |
|    49 | high_20nA | ml          |         0.25     |                 0.175074  |                 1.59075e+07 |
|    50 | high_20nA | ml          |         0.234375 |                 0.161772  |                 1.30706e+07 |
|    51 | high_20nA | ml          |         0.265625 |                 0.182663  |                 1.49434e+07 |
|    52 | high_20nA | ml          |         0.265625 |                 0.174796  |                 1.50217e+07 |
|    53 | high_20nA | ml          |         0.328125 |                 0.191101  |                 1.57122e+07 |
|    54 | high_20nA | ml          |         0.273438 |                 0.174875  |                 1.54447e+07 |
|    55 | high_20nA | ml          |         0.25     |                 0.172157  |                 1.58725e+07 |
|    56 | high_20nA | ml          |         0.320312 |                 0.202312  |                 1.39681e+07 |
|    57 | high_20nA | ml          |         0.28125  |                 0.186994  |                 1.29926e+07 |
|    46 | low_2nA   | ml          |         0.358025 |                 0.316828  |                 6.34268e+06 |
|    47 | low_2nA   | ml          |         0.304688 |                 0.0859271 |                 2.0848e+07  |
|    44 | high_20nA | traditional |         0.578125 |                 0.279882  |              3619.37        |
|    45 | high_20nA | traditional |         0.570312 |                 0.261478  |              3604.04        |
|    48 | high_20nA | traditional |         0.609375 |                 0.304354  |              3661.08        |
|    49 | high_20nA | traditional |         0.5625   |                 0.279473  |              3432.18        |
|    50 | high_20nA | traditional |         0.578125 |                 0.295615  |              3489.73        |
|    51 | high_20nA | traditional |         0.585938 |                 0.291891  |              3666.73        |
|    52 | high_20nA | traditional |         0.570312 |                 0.278027  |              3621.88        |
|    53 | high_20nA | traditional |         0.554688 |                 0.258994  |              3571.31        |
|    54 | high_20nA | traditional |         0.609375 |                 0.292611  |              3580.95        |
|    55 | high_20nA | traditional |         0.5625   |                 0.296366  |              3597.76        |

## Systematics and Leakage Checks

| check                                                 |    value | flag   | note                                                                                                                                 |
|:------------------------------------------------------|---------:|:-------|:-------------------------------------------------------------------------------------------------------------------------------------|
| ridge_current_auc_from_overlap_score                  | 0.519808 | False  | Flags near-perfect current identification on real windows.                                                                           |
| gradient_boosted_trees_current_auc_from_overlap_score | 0.507647 | False  | Flags near-perfect current identification on real windows.                                                                           |
| mlp_current_auc_from_overlap_score                    | 0.508118 | False  | Flags near-perfect current identification on real windows.                                                                           |
| cnn_1d_current_auc_from_overlap_score                 | 0.561329 | False  | Flags near-perfect current identification on real windows.                                                                           |
| residual_cnn_current_auc_from_overlap_score           | 0.553638 | False  | Flags near-perfect current identification on real windows.                                                                           |
| raw_root_s10_topology_reproduction_required           | 1        | False  | Script aborts before scoring unless all S10 documented topology fractions reproduce.                                                 |
| model_training_current_source                         | 1        | False  | ML/NN training uses only synthetic overlays made from low-current runs 46/47; high-current real runs are scored only after training. |
| identifier_features_excluded                          | 1        | False  | Model features exclude run, event number, current group, downstream label, and matched-stratum labels.                               |
| best_model_brier                                      | 0.160756 | False  | Extremely small Brier would indicate an unrealistic synthetic classification shortcut.                                               |

Dominant systematics are template support, synthetic-to-real transfer, the two low-current training runs, and the fact that real high-current pile-up has no truth labels. The bootstrap covers run-to-run instability but not all waveform-model misspecification. Brier/log-loss are therefore used only on the synthetic held-out benchmark; real-current conclusions use matched high-minus-low contrasts and discordance rates, not a truth claim.

## Caveats

1. The real-current secondary fraction is an estimator, not a labelled pile-up truth.
2. The low-current synthetic overlays are necessary for supervised training, but they may underrepresent broad-late morphology and adaptive-lowering artifacts.
3. Only two 2 nA runs exist for low-current leave-one-run-out calibration, so run-block CIs are intentionally conservative and discrete.
4. The residual-CNN architecture is useful as a morphology diagnostic, but it should not be adopted for correction until candidate-level calibration is validated against an independent observable.

## Conclusion

gradient_boosted_trees wins the supervised run-held-out synthetic benchmark by the composite score (AUC 0.849, Brier 0.1608, secondary-fraction MAE 0.1291). On real matched high/low-current windows, the winner's overlap-score high-minus-low is 0.01340 [-0.01545, 0.04453], but its secondary-fraction contrast is 0.00623 [0.00026, 0.01228]. The traditional bounded-template secondary-fraction contrast is 0.01556 [-0.00852, 0.03618]. Therefore the previous ML-overlap versus secondary-fraction disagreement is not a single-model artifact; it is a support-dependent morphology effect, strongest in broad-late/adaptive-lowering strata, and should remain diagnostic rather than a physics correction until independent candidate truth is available.

Artifacts in this directory include `result.json`, `manifest.json`, `input_sha256.csv`, `synthetic_benchmark_summary.csv`, `synthetic_event_predictions.csv`, `real_method_summary.csv`, `real_method_stratum_summary.csv`, `real_event_scores.csv`, `run_stability_summary.csv`, `leakage_checks.csv`, and figures.

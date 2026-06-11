# S11i: bounded-fit score calibration audit

- **Ticket:** `1781065299.555.20535839`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT `HRDv` from the S07f configuration.
- **Target:** S07f/S11e all-three injected two-pulse truth, Sample-II analysis runs, B2+B4+B6+B8 selected, `A>1000` ADC, clean sideband `D_t<3 ns`.
- **Split:** leave-one-run-out. All intervals in the global table are run-block bootstrap 95% CIs.
- **Winner recorded in `result.json`:** `MLP`.

## Raw ROOT Reproduction

The first gate re-reads the ROOT files and rebuilds the all-three control population before any model is trained.

| quantity                             | report_value | reproduced | delta        | tolerance | pass |
| ------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- |
| parent App.I guarded gross D_t>51 ns | 72           | 72         | 0            | 0         | True |
| all-three control events             | 3774         | 3774       | 0            | 0         | True |
| all-three clean events D_t<3 ns      |              | 579        |              |           | True |
| all-three guarded gross D_t>51 ns    | 22           | 22         | 0            | 0         | True |
| S07f traditional injected ROC AUC    | 0.605954     | 0.605954   | -3.7261e-07  | 0.002     | True |
| S07f shape-only RF injected ROC AUC  | 0.822118     | 0.822118   | -4.78575e-07 | 0.002     | True |

The exact-count gates reproduce the parent App.I gross tail, the all-three control sample, and the all-three guarded gross tail. The S07f traditional and RF AUC reproductions verify that this ticket uses the same injected target as the earlier all-three validation.

## Dataset

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 9         | 9        | 18    |
| 59  | 93        | 93       | 186   |
| 60  | 129       | 129      | 258   |
| 61  | 176       | 176      | 352   |
| 62  | 111       | 111      | 222   |
| 63  | 57        | 57       | 114   |
| 65  | 4         | 4        | 8     |

Each clean event `i` is paired with one injected copy. If `x[i,c,s]` is channel `c`, sample `s`, and `k_i` is the selected downstream channel, the injected waveform is

`x_prime[i,k,s] = x[i,k,s] + alpha_i x[i,k,s-d_i]`,

with delay `d_i` in `[2, 3, 4, 5, 6]` samples and secondary scale `alpha_i` in the S07f range. Pair members share the same run and are therefore always held out together.

## Methods

The strong traditional method is the S11e constrained one-pulse versus two-pulse fit. For a normalized downstream waveform `z`, each training-run template `t`, and candidate delay `d`, the one-pulse model is

`z_s = a t_s + b + eps_s`,

and the bounded two-pulse model is

`z_s = a t_s + c t_shifted(s,d) + b + eps_s`, with `a>0`, `c>=0`, `0 <= c/(a+c) <= 0.65`, and `|b| <= 0.25`.

The traditional scalar score is chosen inside each training fold from secondary fraction, secondary amplitude, delay, chi2/ndf, two-pulse SSE, and fractional SSE improvement. Its calibrated probability is fold-local isotonic regression:

`p_hat(x) = I_f(score_fit(x))`,

where `I_f` is fit only on runs other than held-out fold `f`.

Calibration layers test whether the interpretable fit outputs can support reliable abstention or recovery. Logistic calibration uses `logit p = beta_0 + beta^T g(x)`. ExtraTrees calibration is a nonlinear layer on the same fit-output vector `g(x)`. The fit-plus-shape-residual layer appends the out-of-fold shape RF score, `score_RF - p_hat_fit`, and their product to ask whether black-box residual information repairs calibration without hiding the bounded-fit diagnostics.

The ML/NN competitors use only waveform-shape features or normalized waveforms: shape-only random forest, ridge classifier, gradient-boosted trees, MLP, 1D-CNN, and a channel-attention CNN. Timing values, run/event identifiers, pair identifiers, injected delay/scale/target, absolute amplitudes, and fit outputs are excluded from these waveform-only baselines. Scores are out-of-fold; probabilities use model probabilities or fold-local scaling for methods without native calibrated probabilities.

Traditional fit fold choices:

| heldout_run | candidate            | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | frac_sse_improvement | 1    | 0.607629  | 0.46869      | 0.738699  | 1140    | 18     |
| 59          | frac_sse_improvement | 1    | 0.604032  | 0.470814     | 0.731985  | 972     | 186    |
| 60          | frac_sse_improvement | 1    | 0.60263   | 0.458436     | 0.734061  | 900     | 258    |
| 61          | frac_sse_improvement | 1    | 0.622496  | 0.466038     | 0.742642  | 806     | 352    |
| 62          | frac_sse_improvement | 1    | 0.613319  | 0.46967      | 0.741311  | 936     | 222    |
| 63          | frac_sse_improvement | 1    | 0.609748  | 0.4679       | 0.744578  | 1044    | 114    |
| 65          | frac_sse_improvement | 1    | 0.61092   | 0.474937     | 0.74189   | 1150    | 8      |

## Calibration And Classification Results

| method                             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | ece       | ece_ci_low | ece_ci_high | fixed_95_clean_rejection | fixed_95_clean_rejection_ci_low | fixed_95_clean_rejection_ci_high |
| ---------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | --------- | ---------- | ----------- | ------------------------ | ------------------------------- | -------------------------------- |
| MLP                                | 0.901372 | 0.873242       | 0.924911        | 0.898318          | 0.863758  | 0.924201   | 0.130108 | 0.109801     | 0.15064       | 0.064904  | 0.0513295  | 0.0936947   | 0.623489                 | 0.524599                        | 0.706215                         |
| gradient-boosted trees             | 0.854884 | 0.836506       | 0.87831         | 0.860256          | 0.837773  | 0.888045   | 0.158608 | 0.145704     | 0.169483      | 0.0526283 | 0.0452484  | 0.0869218   | 0.452504                 | 0.384183                        | 0.595447                         |
| ridge                              | 0.837329 | 0.8216         | 0.861382        | 0.81931           | 0.797141  | 0.848774   | 0.186183 | 0.182686     | 0.190098      | 0.116515  | 0.107704   | 0.150069    | 0.443869                 | 0.405988                        | 0.503852                         |
| fit-plus-shape-residual ExtraTrees | 0.83555  | 0.818564       | 0.862272        | 0.840202          | 0.827946  | 0.859448   | 0.173052 | 0.166658     | 0.178898      | 0.0825626 | 0.0699359  | 0.132737    | 0.462867                 | 0.390981                        | 0.510264                         |
| shape-only RF                      | 0.822396 | 0.799272       | 0.846377        | 0.833273          | 0.81219   | 0.86104    | 0.175849 | 0.161832     | 0.193233      | 0.0529279 | 0.0409784  | 0.0881354   | 0.419689                 | 0.357614                        | 0.471751                         |
| channel-attention CNN              | 0.819276 | 0.814272       | 0.844684        | 0.819614          | 0.799161  | 0.845384   | 0.177101 | 0.173332     | 0.179864      | 0.0578674 | 0.0479772  | 0.117419    | 0.405872                 | 0.338645                        | 0.486098                         |
| 1D-CNN                             | 0.731644 | 0.714615       | 0.761797        | 0.736464          | 0.715191  | 0.770574   | 0.215366 | 0.200414     | 0.235623      | 0.0668628 | 0.0426975  | 0.152427    | 0.300518                 | 0.227339                        | 0.362492                         |
| fit-output ExtraTrees calibration  | 0.731272 | 0.715735       | 0.753189        | 0.75144           | 0.731779  | 0.776771   | 0.216075 | 0.212181     | 0.219372      | 0.0709101 | 0.0607081  | 0.0889231   | 0.305699                 | 0.244675                        | 0.349447                         |
| fit-output logistic calibration    | 0.65286  | 0.640746       | 0.672383        | 0.675294          | 0.643063  | 0.712778   | 0.230138 | 0.225893     | 0.235422      | 0.042648  | 0.0236093  | 0.0914431   | 0.207254                 | 0.127007                        | 0.290131                         |
| bounded two-pulse fit isotonic     | 0.607549 | 0.594747       | 0.62306         | 0.632821          | 0.601152  | 0.657924   | 0.239429 | 0.234307     | 0.246575      | 0.0249579 | 0.0152219  | 0.0433093   | 0.153713                 | 0.084911                        | 0.202195                         |

The winner by global ROC AUC is `MLP` with AUC 0.901. The bounded-fit isotonic traditional baseline has AUC 0.608; the winner-minus-traditional AUC difference is 0.294. Brier and ECE are calibration losses, so lower is better. Fixed-95%-clean rejection reports the fraction of injected pulses rejected above the 95th percentile of clean scores.

## Accepted Recovery Bias

| method                             | accepted_injected_count | accepted_injected_coverage | accepted_delay_bias_samples | accepted_delay_rmse_samples | accepted_secondary_scale_bias | accepted_secondary_scale_rmse |
| ---------------------------------- | ----------------------- | -------------------------- | --------------------------- | --------------------------- | ----------------------------- | ----------------------------- |
| MLP                                | 361                     | 0.623489                   | 0.214765                    | 1.50391                     | -0.0107163                    | 0.217515                      |
| gradient-boosted trees             | 262                     | 0.452504                   | 0.309417                    | 1.40307                     | 0.0182462                     | 0.2217                        |
| ridge                              | 257                     | 0.443869                   | 0.258883                    | 1.49958                     | -0.0344375                    | 0.225717                      |
| fit-plus-shape-residual ExtraTrees | 268                     | 0.462867                   | 0.3361                      | 1.44756                     | 0.0400886                     | 0.214599                      |
| shape-only RF                      | 243                     | 0.419689                   | 0.370732                    | 1.51094                     | 0.0199671                     | 0.222603                      |
| channel-attention CNN              | 235                     | 0.405872                   | 0.336788                    | 1.52526                     | -0.00782624                   | 0.221334                      |
| 1D-CNN                             | 174                     | 0.300518                   | 0.306667                    | 1.44684                     | 0.0239725                     | 0.22332                       |
| fit-output ExtraTrees calibration  | 177                     | 0.305699                   | -0.0564972                  | 0.89569                     | -0.00907454                   | 0.115114                      |
| fit-output logistic calibration    | 120                     | 0.207254                   | 0.262712                    | 1.14611                     | 0.0460876                     | 0.160707                      |
| bounded two-pulse fit isotonic     | 89                      | 0.153713                   | -0.179775                   | 0.703123                    | 0.0330716                     | 0.10797                       |

The accepted recovery rows evaluate only injected events above each method's fixed-95%-clean operating point. Delay bias uses `d_fit - d_true` in samples. Secondary-scale bias uses the bounded fit's recovered secondary fraction minus the injected scale; it is reported even for black-box scores because abstention decisions still rely on whether the accepted bounded-fit recovery is physically useful.

## Delay/Scale Frontier

Frontier pass is defined per delay/scale cell as `(AUC_real - AUC_shuffled) > 0.05` and fixed-95%-clean injected rejection at least 0.80. The fixed-clean threshold is the 95th percentile of clean scores in the same cell, so the reported rejection is the fraction of injected events above that threshold.

| delay_samples | scale_bin | n_injected | roc_auc  | average_precision | fixed_95_clean_rejection | real_minus_shuffled_auc | frontier_pass | fit_delay_bias_samples | fit_delay_rms_samples | fit_failure_rate |
| ------------- | --------- | ---------- | -------- | ----------------- | ------------------------ | ----------------------- | ------------- | ---------------------- | --------------------- | ---------------- |
| 2             | high      | 30         | 0.954444 | 0.962226          | 0.833333                 | 0.48                    | True          | 1.63636                | 2.46798               | 0.266667         |
| 2             | low       | 41         | 0.730518 | 0.768755          | 0.292683                 | 0.234979                | False         | 2.23077                | 2.84199               | 0.365854         |
| 2             | mid       | 38         | 0.885388 | 0.911884          | 0.631579                 | 0.422091                | False         | 1.3125                 | 2.09165               | 0.157895         |
| 3             | high      | 46         | 0.966446 | 0.916743          | 0.934783                 | 0.504253                | True          | 0.315789               | 1.33771               | 0.173913         |
| 3             | low       | 47         | 0.836125 | 0.854599          | 0.489362                 | 0.337709                | False         | 1.31429                | 2.13809               | 0.255319         |
| 3             | mid       | 45         | 0.941235 | 0.926235          | 0.644444                 | 0.424691                | False         | 0.857143               | 1.69031               | 0.222222         |
| 4             | high      | 37         | 0.948868 | 0.962087          | 0.891892                 | 0.53214                 | True          | 0.333333               | 1.19024               | 0.351351         |
| 4             | low       | 34         | 0.944637 | 0.92718           | 0.823529                 | 0.413495                | True          | -0.107143              | 1.32288               | 0.176471         |
| 4             | mid       | 33         | 0.918274 | 0.908614          | 0.606061                 | 0.447199                | False         | 0.173913               | 1.28537               | 0.30303          |
| 5             | high      | 41         | 0.985128 | 0.985318          | 0.902439                 | 0.51517                 | True          | 0.0322581              | 0.740532              | 0.243902         |
| 5             | low       | 39         | 0.834977 | 0.871168          | 0.538462                 | 0.283366                | False         | -0.458333              | 1.51383               | 0.384615         |
| 5             | mid       | 36         | 0.935185 | 0.941452          | 0.75                     | 0.460648                | False         | -0.354839              | 1.25724               | 0.138889         |
| 6             | high      | 44         | 0.942665 | 0.936522          | 0.659091                 | 0.5625                  | False         | -0.95                  | 1.70294               | 0.0909091        |
| 6             | low       | 37         | 0.774288 | 0.745528          | 0.351351                 | 0.304602                | False         | -0.318182              | 0.92932               | 0.405405         |
| 6             | mid       | 31         | 0.931322 | 0.937597          | 0.774194                 | 0.439646                | False         | -0.833333              | 1.50923               | 0.419355         |

The fit-delay columns are evaluated on injected events in the same cells. They show whether the traditional fit recovers the injected delay, not merely whether a classifier separates injected from clean.

## Sentinels, Leakage, And Systematics

| probe                                  | roc_auc  | average_precision | notes                                                 |
| -------------------------------------- | -------- | ----------------- | ----------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same for clean/injected pairs; should be chance.      |
| fit-output-only logistic sentinel      | 0.65286  | 0.675294          | Interpretable bounded-fit variables only.             |
| fit-output-only ExtraTrees sentinel    | 0.731272 | 0.75144           | Nonlinear fit-output-only calibration.                |
| shape-only RF sentinel                 | 0.822396 | 0.833273          | Waveform-shape baseline without fit outputs.          |
| topology-only RF                       | 0.5      | 0.5               | All-three topology should carry no label information. |
| absolute-amplitude-only RF             | 0.562903 | 0.569827          | Excluded nuisance; injection changes peak height.     |
| shape RF with shuffled training labels | 0.477671 | 0.480534          | Null for frontier pass rule.                          |
| pair split violations                  | 0        |                   | Must be 0.                                            |
| main feature count                     | 173      |                   | Shape-only tabular features used by ridge/HGB/MLP.    |

Fit-output-only, shape-only, shuffled-label, amplitude-only, and topology-only sentinels are all retained. Run-block bootstrap addresses the limited number of independent runs, but it cannot create more run diversity than exists in the Sample-II all-three sideband. The smallest cells, especially run 58 and run 65 contributions, should be treated as frontier hints rather than precision measurements. The amplitude-only sentinel is reported because injection changes peak height; it is excluded from the main ML/NN comparisons. The shuffled-label sentinel is the null used in the frontier rule.

## Caveats

This is an injected-recovery study, not a direct beam pile-up rate measurement. The injected second pulse is a delayed scaled copy of the same waveform, so it under-represents independent pulse-shape variation and electronics correlations that would appear in real overlapping particles. Calibration is assessed on only seven run blocks, so ECE and Brier intervals should be interpreted as stability diagnostics rather than asymptotic coverage statements. Neural models are intentionally small to keep leave-one-run-out training deterministic on CPU; larger architectures would need a separate pre-registered capacity scan.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11i_1781065299_555_20535839_bounded_fit_score_calibration_audit.py --config configs/s11i_1781065299_555_20535839_bounded_fit_score_calibration_audit.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `global_scoreboard.csv`, `method_cell_metrics.csv`, `fit_output_fold_choices.csv`, `two_pulse_fit_oof.csv`, `leakage_checks.csv`, `fit_calibration_feature_columns.csv`, `fit_plus_shape_feature_columns.csv`, and `oof_predictions.csv`.

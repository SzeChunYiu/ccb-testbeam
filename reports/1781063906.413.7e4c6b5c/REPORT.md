# S11h: all-three delay-scale recovery frontier

- **Ticket:** `1781063906.413.7e4c6b5c`
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

## Data Set

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

`x_prime[i,k,s] = x[i,k,s] + alpha_i * x[i,k,s-d_i]`,

with delay `d_i` in `[2, 3, 4, 5, 6]` samples and secondary scale `alpha_i` in the S07f range. Pair members share the same run and are therefore always held out together.

## Methods

The strong traditional method is the S11e constrained one-pulse versus two-pulse fit. For a normalized downstream waveform \(z\), each training-run template \(t\), and candidate delay \(d\), the one-pulse model is `z = a t + b 1 + eps`; the two-pulse model is `z = a t + c shift_d(t) + b 1 + eps`, constrained to positive amplitudes and bounded secondary fraction. The fold-local score is selected from secondary fraction, secondary amplitude, delay, chi2/ndf, SSE improvement, and related fit outputs using training runs only.

The ML/NN competitors use only waveform-shape features or normalized waveforms: shape-only random forest, ridge classifier, gradient-boosted trees, MLP, 1D-CNN, and a channel-attention CNN. Timing values, run/event identifiers, pair identifiers, injected delay/scale/target, absolute amplitudes, and fit outputs are excluded from the ML/NN feature sets. Scores are out-of-fold; probabilities use either model probabilities or fold-local score scaling for methods without calibrated probabilities.

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

## Global Results

| method                 | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high |
| ---------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- |
| MLP                    | 0.903563 | 0.880892       | 0.931411        | 0.893504          | 0.863369  | 0.928727   | 0.123565 | 0.104436     | 0.142624      |
| gradient-boosted trees | 0.854884 | 0.837588       | 0.878407        | 0.860256          | 0.839868  | 0.888757   | 0.158608 | 0.146603     | 0.169588      |
| channel-attention CNN  | 0.838522 | 0.825233       | 0.858189        | 0.838645          | 0.816121  | 0.86162    | 0.167731 | 0.160261     | 0.178562      |
| ridge                  | 0.837329 | 0.821104       | 0.860461        | 0.81931           | 0.80014   | 0.858391   | 0.186183 | 0.183121     | 0.19022       |
| shape-only RF          | 0.821761 | 0.799276       | 0.845022        | 0.834947          | 0.812454  | 0.862275   | 0.177922 | 0.165679     | 0.192141      |
| 1D-CNN                 | 0.730725 | 0.708737       | 0.764562        | 0.721152          | 0.699618  | 0.761621   | 0.224151 | 0.207499     | 0.242141      |
| bounded two-pulse fit  | 0.607549 | 0.592979       | 0.622803        | 0.632821          | 0.58884   | 0.656127   | 0.239429 | 0.234063     | 0.246469      |

The winner by preregistered global ROC AUC is `MLP` with AUC 0.904. The best traditional-fit AUC is 0.608; the winner-minus-traditional AUC difference is 0.296.

## Delay/Scale Frontier

Frontier pass is defined per delay/scale cell as `(AUC_real - AUC_shuffled) > 0.05` and fixed-95%-clean injected rejection at least 0.80. The fixed-clean threshold is the 95th percentile of clean scores in the same cell, so the reported rejection is the fraction of injected events above that threshold.

| delay_samples | scale_bin | n_injected | roc_auc  | average_precision | fixed_95_clean_rejection | real_minus_shuffled_auc | frontier_pass | fit_delay_bias_samples | fit_delay_rms_samples | fit_failure_rate |
| ------------- | --------- | ---------- | -------- | ----------------- | ------------------------ | ----------------------- | ------------- | ---------------------- | --------------------- | ---------------- |
| 2             | high      | 30         | 0.94     | 0.950573          | 0.733333                 | 0.434444                | False         | 1.63636                | 2.46798               | 0.266667         |
| 2             | low       | 41         | 0.713861 | 0.732915          | 0.195122                 | 0.198096                | False         | 2.23077                | 2.84199               | 0.365854         |
| 2             | mid       | 38         | 0.88608  | 0.911138          | 0.684211                 | 0.404086                | False         | 1.3125                 | 2.09165               | 0.157895         |
| 3             | high      | 46         | 0.955104 | 0.918977          | 0.913043                 | 0.400756                | True          | 0.315789               | 1.33771               | 0.173913         |
| 3             | low       | 47         | 0.827071 | 0.810662          | 0.297872                 | 0.314169                | False         | 1.31429                | 2.13809               | 0.255319         |
| 3             | mid       | 45         | 0.933827 | 0.928447          | 0.688889                 | 0.417284                | False         | 0.857143               | 1.69031               | 0.222222         |
| 4             | high      | 37         | 0.956903 | 0.929742          | 0.756757                 | 0.441563                | False         | 0.333333               | 1.19024               | 0.351351         |
| 4             | low       | 34         | 0.936851 | 0.9196            | 0.617647                 | 0.471453                | False         | -0.107143              | 1.32288               | 0.176471         |
| 4             | mid       | 33         | 0.926538 | 0.9195            | 0.69697                  | 0.412305                | False         | 0.173913               | 1.28537               | 0.30303          |
| 5             | high      | 41         | 0.982748 | 0.978554          | 1                        | 0.441999                | True          | 0.0322581              | 0.740532              | 0.243902         |
| 5             | low       | 39         | 0.855358 | 0.877402          | 0.589744                 | 0.327416                | False         | -0.458333              | 1.51383               | 0.384615         |
| 5             | mid       | 36         | 0.929784 | 0.940999          | 0.861111                 | 0.447531                | True          | -0.354839              | 1.25724               | 0.138889         |
| 6             | high      | 44         | 0.951963 | 0.943871          | 0.772727                 | 0.370351                | False         | -0.95                  | 1.70294               | 0.0909091        |
| 6             | low       | 37         | 0.827611 | 0.794957          | 0.486486                 | 0.298758                | False         | -0.318182              | 0.92932               | 0.405405         |
| 6             | mid       | 31         | 0.916753 | 0.927897          | 0.709677                 | 0.413632                | False         | -0.833333              | 1.50923               | 0.419355         |

The fit-delay columns are evaluated on injected events in the same cells. They show whether the traditional fit recovers the injected delay, not merely whether a classifier separates injected from clean.

## Leakage And Systematics

| probe                                  | roc_auc  | average_precision | notes                                                 |
| -------------------------------------- | -------- | ----------------- | ----------------------------------------------------- |
| pre-injection D_t                      | 0.5      | 0.5               | Same for clean/injected pairs; should be chance.      |
| topology-only RF                       | 0.5      | 0.5               | All-three topology should carry no label information. |
| absolute-amplitude-only RF             | 0.563501 | 0.568836          | Excluded nuisance; injection changes peak height.     |
| shape RF with shuffled training labels | 0.519781 | 0.507552          | Null for frontier pass rule.                          |
| pair split violations                  | 0        |                   | Must be 0.                                            |
| main feature count                     | 173      |                   | Shape-only tabular features used by ridge/HGB/MLP.    |

Run-block bootstrap addresses the limited number of independent runs, but it cannot create more run diversity than exists in the Sample-II all-three sideband. The smallest cells, especially run 58 and run 65 contributions, should be treated as frontier hints rather than precision measurements. The amplitude-only sentinel is reported because injection changes peak height; it is excluded from the main ML/NN comparisons. The shuffled-label sentinel is the null used in the frontier rule.

## Caveats

This is an injected-recovery study, not a direct beam pile-up rate measurement. The injected second pulse is a delayed scaled copy of the same waveform, so it under-represents independent pulse-shape variation and electronics correlations that would appear in real overlapping particles. Neural models are intentionally small to keep leave-one-run-out training deterministic on CPU; larger architectures would need a separate pre-registered capacity scan. CIs are run-block intervals and are therefore sensitive to the seven-run support.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11h_1781063906_413_7e4c6b5c_delay_scale_recovery_frontier.py --config configs/s11h_1781063906_413_7e4c6b5c_delay_scale_recovery_frontier.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `global_scoreboard.csv`, `method_cell_metrics.csv`, `fit_output_fold_choices.csv`, `two_pulse_fit_oof.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

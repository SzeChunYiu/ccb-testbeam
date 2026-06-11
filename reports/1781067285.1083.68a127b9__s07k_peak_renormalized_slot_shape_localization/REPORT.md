# S07k: peak-renormalized slot-shape localization

- **Ticket:** `1781067285.1083.68a127b9`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65
- **Split:** leave-one-run-out; intervals are run-block bootstrap 95% confidence intervals.
- **Winner:** `MLP`

## Abstract

This study asks which per-stave waveform slots and time samples drive the peak-renormalized all-three injected shape signal. The analysis first reproduces the parent App.I and all-three raw-ROOT numbers, then forms a paired peak-preserved injection dataset from clean all-three events. A strong transparent atom/template selector is benchmarked against a permissive slot-shape RF, ridge/logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a new feature-fused WaveAtomNet architecture. The best method is MLP with ROC AUC 0.897 [0.874, 0.922], compared with the traditional selector 0.607 [0.599, 0.622].

## Raw-ROOT Reproduction

| quantity                                | report_value | reproduced | delta      | tolerance | pass |
| --------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| parent App.I guarded gross D_t>51 ns    | 72           | 72         | 0          | 0         | True |
| parent App.I documented gross D_t>50 ns |              | 74         |            |           | True |
| all-three control events                | 3774         | 3774       | 0          | 0         | True |
| all-three clean events D_t<3 ns         |              | 579        |            |           | True |
| all-three guarded gross D_t>51 ns       | 22           | 22         | 0          | 0         | True |
| all-three S07e shape RF ROC AUC         | 0.992778     | 0.994426   | 0.00164861 | 0.002     | True |
| S07f unnormalized injection RF ROC AUC  | 0.822118     | 0.822118   | 0          | 0.001     | True |

The reproduction gate reads `EVENTNO`, `EVT`, and `HRDv` from the raw B-stack ROOT files. For each selected run, the four analysis channels B2, B4, B6, and B8 are reshaped to 18 samples, baseline-subtracted by the median of samples 0--3, thresholded at 1000 ADC, and timed with CFD20. The reproduced all-three population is the prerequisite for all downstream injection and model claims.

## Dataset Construction

Let \(x_{r,e,s,t}\) be the baseline-subtracted waveform for run \(r\), event \(e\), stave \(s\), and sample \(t\). Starting from all-three clean events with \(D_t<3\) ns, one selected downstream waveform receives a delayed copy:

\[
z_{s,t}=x_{s,t}+a\,x_{s,t-d},
\]

where \(d\in[2,6]\) samples and \(a\in[0.12,0.38]\). The target waveform is then scaled by

\[
\alpha=\frac{\max_t x_{s,t}}{\max_t z_{s,t}}
\]

so the target-stave peak is restored. Raw and injected pair members share a run and are therefore always held out together.

| run | raw_clean | injected | total |
| --- | --------- | -------- | ----- |
| 58  | 9         | 9        | 18    |
| 59  | 93        | 93       | 186   |
| 60  | 129       | 129      | 258   |
| 61  | 176       | 176      | 352   |
| 62  | 111       | 111      | 222   |
| 63  | 57        | 57       | 114   |
| 65  | 4         | 4        | 8     |

## Methods

The traditional comparator is selected inside each training fold from transparent one-dimensional atom families: \(D_t\), \(|C_t|\), downstream tail/late charge fractions, area-over-peak, peak sample, derivative drop, terminal fraction, and a train-run-only delayed-template residual. The selected score is standardized on training runs and applied unchanged to the held-out run.

The slot-shape RF is the deliberately permissive per-stave waveform-slot probe from the ticket. Ridge denotes an L2-penalized logistic regression on the same amplitude-normalized slot-shape features. Gradient-boosted trees are `HistGradientBoostingClassifier` models on those features. The MLP is a two-hidden-layer feed-forward network. The 1D-CNN consumes the normalized four-stave waveform tensor directly. WaveAtomNet is the new architecture: a small convolutional waveform branch fused with dense slot-shape atoms before a logistic head.

All model selection and preprocessing are fold-local. Features exclude run, event id, pair id, injected delay/scale/target, absolute amplitudes, topology flags, and timing variables for the ML/NN models.

## Benchmark

| method                             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | fixed_95_clean_rejection | fixed_95_clean_rejection_ci_low | fixed_95_clean_rejection_ci_high | notes                                                                                                                                             |
| ---------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------ | ------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| MLP                                | 0.896914 | 0.873614       | 0.92214         | 0.888722          | 0.856136  | 0.916363   | 0.129109 | 0.113352     | 0.145456      | 0.588946                 | 0.504602                        | 0.667919                         | Two-hidden-layer feed-forward network on permissive normalized slot-shape features.                                                               |
| gradient-boosted trees             | 0.883517 | 0.864207       | 0.906948        | 0.889308          | 0.869229  | 0.916049   | 0.143438 | 0.125747     | 0.162161      | 0.544041                 | 0.47305                         | 0.661534                         | HistGradientBoostingClassifier on permissive normalized slot-shape features.                                                                      |
| slot-shape RF                      | 0.850066 | 0.825553       | 0.87917         | 0.854268          | 0.832545  | 0.88314    | 0.180674 | 0.174998     | 0.186766      | 0.455959                 | 0.412385                        | 0.504762                         | RandomForestClassifier grid-selected on permissive slot-shape features; best params={'n_estimators': 500, 'max_depth': 7, 'min_samples_leaf': 8}. |
| ridge logistic                     | 0.838401 | 0.823747       | 0.858664        | 0.820608          | 0.795792  | 0.859803   | 0.162358 | 0.150748     | 0.171694      | 0.433506                 | 0.367632                        | 0.518191                         | L2 logistic regression on permissive normalized slot-shape features.                                                                              |
| WaveAtomNet                        | 0.794308 | 0.758512       | 0.83827         | 0.806877          | 0.767356  | 0.860887   | 0.186895 | 0.168954     | 0.200978      | 0.378238                 | 0.307569                        | 0.503856                         | New feature-fused convolutional waveform plus slot-shape atom network.                                                                            |
| traditional atom/template selector | 0.606899 | 0.599341       | 0.621719        | 0.570991          | 0.563143  | 0.583206   | 0.317798 | 0.310887     | 0.324228      | 0.0569948                | 0.0508565                       | 0.107822                         | Fold-local transparent selector over timing, shape atoms, and delayed-template residuals.                                                         |
| 1D-CNN                             | 0.569945 | 0.556863       | 0.597256        | 0.570204          | 0.561472  | 0.634589   | 0.24882  | 0.248446     | 0.249069      | 0.0880829                | 0.0754422                       | 0.20751                          | Compact convolutional network on normalized four-stave waveform tensors.                                                                          |

Fold diagnostics:

| method                             | heldout_run | n_train | n_test | fold_auc |
| ---------------------------------- | ----------- | ------- | ------ | -------- |
| traditional atom/template selector | 58          | 1140    | 18     | 0.537037 |
| traditional atom/template selector | 59          | 972     | 186    | 0.63331  |
| traditional atom/template selector | 60          | 900     | 258    | 0.603359 |
| traditional atom/template selector | 61          | 806     | 352    | 0.60174  |
| traditional atom/template selector | 62          | 936     | 222    | 0.604862 |
| traditional atom/template selector | 63          | 1044    | 114    | 0.619729 |
| traditional atom/template selector | 65          | 1150    | 8      | 0.65625  |
| ridge logistic                     | 58          | 1140    | 18     | 0.839506 |
| ridge logistic                     | 59          | 972     | 186    | 0.853162 |
| ridge logistic                     | 60          | 900     | 258    | 0.812121 |
| ridge logistic                     | 61          | 806     | 352    | 0.833549 |
| ridge logistic                     | 62          | 936     | 222    | 0.872413 |
| ridge logistic                     | 63          | 1044    | 114    | 0.848261 |
| ridge logistic                     | 65          | 1150    | 8      | 0.9375   |
| gradient-boosted trees             | 58          | 1140    | 18     | 0.895062 |
| gradient-boosted trees             | 59          | 972     | 186    | 0.904382 |
| gradient-boosted trees             | 60          | 900     | 258    | 0.890662 |
| gradient-boosted trees             | 61          | 806     | 352    | 0.854597 |
| gradient-boosted trees             | 62          | 936     | 222    | 0.916484 |
| gradient-boosted trees             | 63          | 1044    | 114    | 0.88458  |

Traditional fold choices:

| heldout_run | candidate                  | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | max_downstream_peak_sample | 1    | 0.60811   | 6            | 3         | 1140    | 18     |
| 59          | max_downstream_peak_sample | 1    | 0.602546  | 6            | 3         | 972     | 186    |
| 60          | max_downstream_peak_sample | 1    | 0.608094  | 6            | 3         | 900     | 258    |
| 61          | max_downstream_peak_sample | 1    | 0.611213  | 6            | 3         | 806     | 352    |
| 62          | max_downstream_peak_sample | 1    | 0.607707  | 6            | 3         | 936     | 222    |
| 63          | max_downstream_peak_sample | 1    | 0.605285  | 6            | 3         | 1044    | 114    |
| 65          | max_downstream_peak_sample | 1    | 0.606828  | 6            | 3         | 1150    | 8      |

## Shape-Cue Localization

Localization uses fold-local gradient-boosted trees as a stable nonparametric probe. For each held-out run, a trained model is evaluated normally and with a stave slot, sample window, or atom family replaced by the corresponding training-run mean. The table reports the resulting AUC loss.

| group                    | n_columns | baseline_auc | dropout_auc | delta_auc  | mean_fold_delta_auc | min_fold_delta_auc | max_fold_delta_auc |
| ------------------------ | --------- | ------------ | ----------- | ---------- | ------------------- | ------------------ | ------------------ |
| peak_samples_08_11       | 28        | 0.883517     | 0.744187    | 0.13933    | 0.125666            | 0                  | 0.186827           |
| rise_samples_04_07       | 28        | 0.883517     | 0.815721    | 0.067796   | 0.0473701           | -0.0625            | 0.104561           |
| shape_width_atoms        | 21        | 0.883517     | 0.830204    | 0.0533124  | 0.066142            | -0.0123457         | 0.1875             |
| B4_slot_all_samples      | 24        | 0.883517     | 0.835435    | 0.0480818  | 0.0268611           | -0.125             | 0.0693937          |
| B6_slot_all_samples      | 24        | 0.883517     | 0.83916     | 0.0443561  | 0.0265402           | -0.125             | 0.0864198          |
| B8_slot_all_samples      | 24        | 0.883517     | 0.854408    | 0.0291089  | 0.0327093           | 0                  | 0.0864198          |
| pretrigger_samples_00_03 | 28        | 0.883517     | 0.860035    | 0.0234816  | 0.0253122           | 0                  | 0.0617284          |
| terminal_samples_16_17   | 14        | 0.883517     | 0.86353     | 0.0199871  | 0.0190966           | 0                  | 0.037037           |
| tail_samples_12_15       | 28        | 0.883517     | 0.877114    | 0.00640286 | 0.00781352          | -0.00150116        | 0.0134006          |
| tail_fraction_atoms      | 22        | 0.883517     | 0.878568    | 0.00494868 | -0.00693299         | -0.0625            | 0.0129271          |

The largest losses identify the most informative regions after peak renormalization. Feature-level permutation importance provides a higher-resolution cross-check:

| feature                    | mean_auc_importance | min_auc_importance | max_auc_importance | stability_std |
| -------------------------- | ------------------- | ------------------ | ------------------ | ------------- |
| B8_area_over_peak          | 0.029685            | -0.0078125         | 0.0455201          | 0.0173245     |
| ds_shape_std_norm_s04      | 0.0257842           | -0.046875          | 0.0547985          | 0.0335099     |
| B4_norm_s09                | 0.0222061           | -0.078125          | 0.0477839          | 0.0445639     |
| B6_norm_s10                | 0.0165763           | -0.078125          | 0.0546707          | 0.0435084     |
| ds_shape_std_peak_sample   | 0.0154926           | -0.0390625         | 0.0308941          | 0.0244966     |
| ds_shape_mean_norm_s03     | 0.0121901           | 0                  | 0.0486111          | 0.0166678     |
| B4_area_over_peak          | 0.0110036           | 0.00287117         | 0.03125            | 0.00975214    |
| B6_norm_s17                | 0.00794579          | 0                  | 0.0192901          | 0.00722593    |
| B8_norm_s06                | 0.00736934          | 0                  | 0.0401235          | 0.0145119     |
| B8_max_down_step           | 0.00671449          | 0                  | 0.0185185          | 0.00635096    |
| B6_area_over_peak          | 0.00607245          | 0                  | 0.0100918          | 0.00354979    |
| ds_shape_std_max_down_step | 0.00595313          | -0.00157743        | 0.0270062          | 0.0098915     |
| ds_shape_mean_norm_s06     | 0.0047743           | 0                  | 0.0223765          | 0.00788319    |
| B4_norm_s06                | 0.00472215          | -0.00134657        | 0.0169753          | 0.00604697    |
| ds_shape_mean_norm_s17     | 0.00449464          | -7.69468e-05       | 0.0185185          | 0.00658695    |

## Target-Blind And Downstream-Dropout Ablations

| ablation                     | n_columns | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | fixed_95_clean_rejection | delta_auc_vs_primary_slot_gbt | delta_auc_ci_low | delta_auc_ci_high | notes                                                                                  |
| ---------------------------- | --------- | -------- | -------------- | --------------- | ----------------- | ------------------------ | ----------------------------- | ---------------- | ----------------- | -------------------------------------------------------------------------------------- |
| drop_B8_slot                 | 145       | 0.87925  | 0.859908       | 0.900539        | 0.878286          | 0.566494                 | -0.00426708                   | -0.0122596       | -0.00063164       | Slot-shape GBT with all B8 columns replaced by omission and retraining.                |
| drop_B4_slot                 | 145       | 0.867897 | 0.846818       | 0.886754        | 0.874454          | 0.495682                 | -0.0156201                    | -0.0211313       | -0.0126357        | Slot-shape GBT with all B4 columns replaced by omission and retraining.                |
| drop_B6_slot                 | 145       | 0.866047 | 0.845744       | 0.884575        | 0.876685          | 0.502591                 | -0.0174695                    | -0.0268434       | -0.0129014        | Slot-shape GBT with all B6 columns replaced by omission and retraining.                |
| target_stave_blind_aggregate | 72        | 0.846625 | 0.827649       | 0.868725        | 0.852069          | 0.455959                 | -0.0368914                    | -0.0481913       | -0.0310574        | B2 plus downstream aggregate shape means/stds; no individual downstream slot identity. |

`target_stave_blind_aggregate` removes individual downstream slot identity by using only B2 plus downstream aggregate shape means/stds. The one-downstream-stave rows retrain the same GBT after removing all columns for that slot. Negative deltas show how much the permissive slot-shape probe depends on the omitted support.

## Leakage And Systematics

| probe                                       | roc_auc  | average_precision | notes                                                                               |
| ------------------------------------------- | -------- | ----------------- | ----------------------------------------------------------------------------------- |
| pre-injection D_t                           | 0.5      | 0.5               | Same for pair members; should be chance.                                            |
| topology-only GBT                           | 0.5      | 0.5               | All-three topology should carry no injected label information.                      |
| absolute-amplitude-only GBT                 | 0.5      | 0.5               | Excluded nuisance channel; peak renormalization should reduce but not force chance. |
| slot-shape RF with shuffled training labels | 0.479689 | 0.481064          | Null/leakage sanity check for the permissive representation.                        |
| pair split violations                       | 0        |                   | Must be 0.                                                                          |
| forbidden slot-shape columns                | 0        |                   | slot_shape_columns raised on violations before model fitting.                       |

Primary systematics are: (1) the injected target is data-driven, not an independently labelled real pile-up sample; (2) peak renormalization removes the direct peak-height nuisance but can still alter charge and local slope; (3) seven held-out runs limit bootstrap granularity; (4) neural nets are intentionally compact to avoid fitting run-specific artifacts; and (5) localization is model-dependent, so it is interpreted as an operational cue map rather than a unique physical decomposition.

## Verdict

The winner recorded in `result.json` is `MLP`. It beats the traditional atom/template selector by 0.290 AUC on out-of-fold predictions. The S07g permissive slot-shape signal therefore survives peak renormalization and is localized mainly to the ranked groups shown above, but it remains injection-recovery evidence rather than a direct real-beam pile-up-rate measurement.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07k_1781067285_1083_68a127b9_peak_renormalized_slot_shape_localization.py --config configs/s07k_1781067285_1083_68a127b9_peak_renormalized_slot_shape_localization.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `scoreboard.csv`, `fold_scores.csv`, `localization_dropout.csv`, `permutation_importance.csv`, `support_ablation.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

# S07m: charge-preserved shape-cue localization

- **Ticket:** `1781063920.486.09951fba`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65
- **Split:** leave-one-run-out; intervals are run-block bootstrap 95% confidence intervals.
- **Winner:** `gradient-boosted trees`

## Abstract

This study asks whether the all-three pile-up signal in S07g remains recoverable when the injected target waveform is explicitly charge-preserved, and which normalized waveform regions carry that signal. The analysis first reproduces the parent App.I and all-three raw-ROOT numbers, then forms a paired charge-preserved injection dataset from clean all-three events. A strong transparent atom/template selector is benchmarked against ridge/logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a new feature-fused WaveAtomNet architecture. The best method is gradient-boosted trees with ROC AUC 0.845 [0.826, 0.869], compared with the traditional selector 0.605 [0.598, 0.617].

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
\alpha=\frac{\sum_t \max(x_{s,t},0)}{\sum_t \max(z_{s,t},0)}
\]

so the positive charge is preserved. Raw and injected pair members share a run and are therefore always held out together.

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

Ridge denotes an L2-penalized logistic regression on amplitude-normalized strict-shape features. Gradient-boosted trees are `HistGradientBoostingClassifier` models on the same features. The MLP is a two-hidden-layer feed-forward network. The 1D-CNN consumes the normalized four-stave waveform tensor directly. WaveAtomNet is the new architecture: a small convolutional waveform branch fused with a dense strict-shape atom branch before a logistic head.

All model selection and preprocessing are fold-local. Features exclude run, event id, pair id, injected delay/scale/target, absolute amplitudes, topology flags, and timing variables for the ML/NN models.

## Benchmark

| method                             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                     |
| ---------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ----------------------------------------------------------------------------------------- |
| gradient-boosted trees             | 0.844903 | 0.825664       | 0.868782        | 0.852042          | 0.82937   | 0.882985   | 0.16524  | 0.145934     | 0.180986      | HistGradientBoostingClassifier on strict normalized shape features.                       |
| MLP                                | 0.82591  | 0.806921       | 0.842021        | 0.838229          | 0.821859  | 0.854827   | 0.170339 | 0.16224      | 0.181228      | Two-hidden-layer feed-forward network on strict normalized shape features.                |
| ridge logistic                     | 0.797704 | 0.785013       | 0.809366        | 0.781307          | 0.758065  | 0.808096   | 0.184693 | 0.180091     | 0.190612      | L2 logistic regression on strict normalized shape features.                               |
| WaveAtomNet                        | 0.7588   | 0.740998       | 0.780987        | 0.763399          | 0.736449  | 0.807169   | 0.201693 | 0.193774     | 0.208701      | New feature-fused convolutional waveform plus strict-shape atom network.                  |
| traditional atom/template selector | 0.605008 | 0.597928       | 0.617395        | 0.570376          | 0.561957  | 0.582417   | 0.318239 | 0.310982     | 0.325185      | Fold-local transparent selector over timing, shape atoms, and delayed-template residuals. |
| 1D-CNN                             | 0.569942 | 0.556426       | 0.598526        | 0.570203          | 0.561698  | 0.630584   | 0.24882  | 0.248474     | 0.249084      | Compact convolutional network on normalized four-stave waveform tensors.                  |

Fold diagnostics:

| method                             | heldout_run | n_train | n_test | fold_auc |
| ---------------------------------- | ----------- | ------- | ------ | -------- |
| traditional atom/template selector | 58          | 1140    | 18     | 0.537037 |
| traditional atom/template selector | 59          | 972     | 186    | 0.626489 |
| traditional atom/template selector | 60          | 900     | 258    | 0.599213 |
| traditional atom/template selector | 61          | 806     | 352    | 0.60174  |
| traditional atom/template selector | 62          | 936     | 222    | 0.604862 |
| traditional atom/template selector | 63          | 1044    | 114    | 0.619729 |
| traditional atom/template selector | 65          | 1150    | 8      | 0.65625  |
| ridge logistic                     | 58          | 1140    | 18     | 0.740741 |
| ridge logistic                     | 59          | 972     | 186    | 0.811539 |
| ridge logistic                     | 60          | 900     | 258    | 0.787693 |
| ridge logistic                     | 61          | 806     | 352    | 0.796036 |
| ridge logistic                     | 62          | 936     | 222    | 0.819739 |
| ridge logistic                     | 63          | 1044    | 114    | 0.783318 |
| ridge logistic                     | 65          | 1150    | 8      | 0.9375   |
| gradient-boosted trees             | 58          | 1140    | 18     | 0.833333 |
| gradient-boosted trees             | 59          | 972     | 186    | 0.862412 |
| gradient-boosted trees             | 60          | 900     | 258    | 0.851181 |
| gradient-boosted trees             | 61          | 806     | 352    | 0.820119 |
| gradient-boosted trees             | 62          | 936     | 222    | 0.880123 |
| gradient-boosted trees             | 63          | 1044    | 114    | 0.831641 |

Traditional fold choices:

| heldout_run | candidate                  | sign | train_auc | train_median | train_iqr | n_train | n_test |
| ----------- | -------------------------- | ---- | --------- | ------------ | --------- | ------- | ------ |
| 58          | max_downstream_peak_sample | 1    | 0.60619   | 6            | 3         | 1140    | 18     |
| 59          | max_downstream_peak_sample | 1    | 0.601454  | 6            | 3         | 972     | 186    |
| 60          | max_downstream_peak_sample | 1    | 0.606869  | 6            | 3         | 900     | 258    |
| 61          | max_downstream_peak_sample | 1    | 0.608368  | 6            | 3         | 806     | 352    |
| 62          | max_downstream_peak_sample | 1    | 0.605388  | 6            | 3         | 936     | 222    |
| 63          | max_downstream_peak_sample | 1    | 0.603208  | 6            | 3         | 1044    | 114    |
| 65          | max_downstream_peak_sample | 1    | 0.604916  | 6            | 3         | 1150    | 8      |

## Shape-Cue Localization

Localization uses fold-local gradient-boosted trees as a stable nonparametric probe. For each held-out run, a trained model is evaluated normally and with a sample window or atom family replaced by the corresponding training-run mean. The table reports the resulting AUC loss.

| group                    | n_columns | baseline_auc | dropout_auc | delta_auc  | mean_fold_delta_auc | min_fold_delta_auc | max_fold_delta_auc |
| ------------------------ | --------- | ------------ | ----------- | ---------- | ------------------- | ------------------ | ------------------ |
| peak_samples_08_11       | 12        | 0.844903     | 0.725472    | 0.11943    | 0.112202            | 0                  | 0.174823           |
| rise_samples_04_07       | 12        | 0.844903     | 0.777402    | 0.0675007  | 0.0816566           | 0.028932           | 0.135802           |
| shape_width_atoms        | 9         | 0.844903     | 0.793996    | 0.0509067  | 0.0723688           | -0.037037          | 0.25               |
| pretrigger_samples_00_03 | 12        | 0.844903     | 0.815163    | 0.0297398  | 0.0485589           | 0.0238895          | 0.125              |
| terminal_samples_16_17   | 6         | 0.844903     | 0.821303    | 0.0235994  | 0.0165583           | -0.0493827         | 0.0625             |
| tail_samples_12_15       | 12        | 0.844903     | 0.826966    | 0.0179364  | 0.011997            | 0                  | 0.0293853          |
| tail_fraction_atoms      | 9         | 0.844903     | 0.840369    | 0.00453405 | 0.01072             | -0.0123457         | 0.0625             |

The largest losses identify the most informative regions after charge preservation. Feature-level permutation importance provides a higher-resolution cross-check:

| feature                      | mean_auc_importance | min_auc_importance | max_auc_importance | stability_std |
| ---------------------------- | ------------------- | ------------------ | ------------------ | ------------- |
| ds_shape_mean_area_over_peak | 0.0473762           | 0.0100309          | 0.125              | 0.0379627     |
| ds_shape_std_norm_s04        | 0.037196            | -0.0234375         | 0.0733025          | 0.0303356     |
| ds_shape_mean_norm_s09       | 0.0321166           | -0.03125           | 0.0882195          | 0.0384371     |
| ds_shape_mean_norm_s08       | 0.0285473           | 0.0107462          | 0.0546875          | 0.0171469     |
| ds_shape_mean_norm_s17       | 0.025342            | 0.00277008         | 0.09375            | 0.0313869     |
| ds_shape_std_peak_sample     | 0.0244582           | -0.00462963        | 0.0357114          | 0.0144601     |
| ds_shape_mean_norm_s06       | 0.019918            | 0.00234131         | 0.0625             | 0.0213059     |
| ds_shape_mean_norm_s05       | 0.0152546           | 0.00397362         | 0.046875           | 0.014798      |
| ds_shape_std_norm_s16        | 0.0151231           | -0.000639153       | 0.0625             | 0.0219976     |
| ds_shape_std_max_down_step   | 0.0139909           | 0.00446563         | 0.0390625          | 0.0115929     |
| ds_shape_mean_norm_s00       | 0.0136166           | 0.00215958         | 0.0625             | 0.0218593     |
| ds_shape_mean_norm_s03       | 0.0119128           | 0                  | 0.0223765          | 0.00755155    |
| ds_shape_std_norm_s06        | 0.0114661           | 0.00102467         | 0.0390625          | 0.0133631     |
| ds_shape_mean_norm_s02       | 0.0113101           | 0.00109293         | 0.0625             | 0.0226015     |
| ds_shape_std_norm_s07        | 0.0112831           | 1.01453e-05        | 0.046875           | 0.0176781     |

## Leakage And Systematics

| probe                          | roc_auc  | average_precision | notes                                                                              |
| ------------------------------ | -------- | ----------------- | ---------------------------------------------------------------------------------- |
| pre-injection D_t              | 0.5      | 0.5               | Same for pair members; should be chance.                                           |
| absolute-amplitude-only GBT    | 0.527359 | 0.52123           | Excluded nuisance channel; charge preservation should reduce but not force chance. |
| pair split violations          | 0        |                   | Must be 0.                                                                         |
| forbidden strict-shape columns | 0        |                   | strict_shape_columns raised on violations before model fitting.                    |

Primary systematics are: (1) the injected target is data-driven, not an independently labelled real pile-up sample; (2) charge preservation removes the positive-charge nuisance but can still alter local peak shape; (3) seven held-out runs limit bootstrap granularity; (4) neural nets are intentionally compact to avoid fitting run-specific artifacts; and (5) localization is model-dependent, so it is interpreted as an operational cue map rather than a unique physical decomposition.

## Verdict

The winner recorded in `result.json` is `gradient-boosted trees`. It beats the traditional atom/template selector by 0.240 AUC on out-of-fold predictions. The S07g shape signal therefore survives a charge-preserved target and is localized mainly to the ranked groups shown above, but it remains injection-recovery evidence rather than a direct real-beam pile-up-rate measurement.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07m_1781063920_486_09951fba_charge_preserved_shape_cue_localization.py --config configs/s07m_1781063920_486_09951fba_charge_preserved_shape_cue_localization.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `scoreboard.csv`, `fold_scores.csv`, `localization_dropout.csv`, `permutation_importance.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.

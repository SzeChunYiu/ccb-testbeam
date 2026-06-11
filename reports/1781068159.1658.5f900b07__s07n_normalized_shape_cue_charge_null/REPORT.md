# S07n: normalized shape-cue charge null

- **Ticket:** `1781068159.1658.5f900b07`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65
- **Primary split:** leave-one-run-out; intervals are run-block bootstrap 95% CIs.
- **Winner:** `gradient-boosted trees`

## Abstract

S07n tests whether the S07 all-three injected-pile-up shape cue survives after residual charge normalization is made stricter. The analysis first reproduces the parent raw-ROOT App.I and all-three counts, then constructs paired clean/injected all-three events where the injected target stave is normalized to preserve positive charge. The primary benchmark compares a transparent q-template/early-late/derivative/peak-tail selector with ridge logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, a random-forest shape probe, and the new WaveAtomNet fused waveform/atom architecture. Additional peak-preserved, signed-area-preserved, and run-plus-charge-bin nulls test whether the signal is only an amplitude or charge-renormalization artifact.

The winner is **gradient-boosted trees** with AUC 0.845 [0.825, 0.869], AP 0.852, and fixed-95%-clean injected rejection 0.478. The traditional selector obtains AUC 0.605 [0.598, 0.618].

## Raw-ROOT Reproduction

| quantity                                | report_value | reproduced | delta       | tolerance | pass  |
| --------------------------------------- | ------------ | ---------- | ----------- | --------- | ----- |
| parent App.I guarded gross D_t>51 ns    | 72           | 72         | 0           | 0         | True  |
| parent App.I documented gross D_t>50 ns |              | 74         |             |           | True  |
| all-three control events                | 3774         | 3774       | 0           | 0         | True  |
| all-three clean events D_t<3 ns         |              | 579        |             |           | True  |
| all-three guarded gross D_t>51 ns       | 22           | 22         | 0           | 0         | True  |
| all-three S07e shape RF ROC AUC         | 0.992778     | 0.990736   | -0.00204114 | 0.002     | False |
| S07f unnormalized injection RF ROC AUC  | 0.822118     | 0.794484   | -0.0276339  | 0.001     | False |

The reproduction gate reads `EVENTNO`, `EVT`, and `HRDv` from raw `hrdb_run_*.root`, reshapes the B-stack channels to four 18-sample staves, subtracts the samples 0--3 median baseline, applies the `A>1000` ADC selection, and recomputes CFD20 timing. No injected, ML, or report-local artifact is used until these raw counts pass.

The final two rows are inherited S07e/S07f model-anchor diagnostics, not the raw-count gate. They are retained to expose scorer drift under the current software stack; the ticket's required raw ROOT reproduction is the exact-count block above.

## Dataset And Equations

For clean all-three event \(i\), stave \(s\), and sample \(t\), let \(x_{i,s,t}\) be the baseline-subtracted waveform. The injected copy is

\[
z_{i,s,t}=x_{i,s,t}+a_i x_{i,s,t-d_i},
\]

with \(d_i\in\{2,\dots,6\}\) samples and \(a_i\in[0.12,0.38]\). In the primary positive-charge-preserved null the target stave is renormalized by

\[
\alpha_i = \frac{\sum_t \max(x_{i,s,t},0)}{\sum_t \max(z_{i,s,t},0)},\qquad
\tilde z_{i,s,t}=\alpha_i z_{i,s,t}.
\]

The paired clean and injected rows have the same event, run, and base charge and are held out together by run.

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

The traditional method is selected inside each training fold from conventional one-dimensional atoms: \(D_t\), \(|C_t|\), downstream tail and late fractions, area-over-peak, peak sample, derivative drop, final fraction, and a fold-local delayed q-template residual. Each candidate and sign is chosen only by training-run AUC, then standardized on training runs before scoring the held-out run.

ML/NN methods use only normalized shape atoms or normalized waveforms. Forbidden inputs include run, event id, pair id, injected delay/scale/target, absolute amplitudes, topology/present flags, and timing variables. WaveAtomNet is the new architecture: a compact convolutional branch over the four normalized staves is fused with a dense normalized-atom branch before a logistic head.

## Primary Benchmark

| method                             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | fixed95_clean_rejection | fixed95_ci_low | fixed95_ci_high | brier    | auc_minus_traditional | delta_ci_low | delta_ci_high | fold_auc_min | fold_auc_max | support_drift_auc_range | notes                                                                                                               |
| ---------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | ----------------------- | -------------- | --------------- | -------- | --------------------- | ------------ | ------------- | ------------ | ------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------- |
| gradient-boosted trees             | 0.844903 | 0.825166       | 0.868953        | 0.852042          | 0.830657  | 0.882249   | 0.478411                | 0.399586       | 0.518655        | 0.16524  | 0.239895              | 0.220668     | 0.265076      | 0.820119     | 0.880123     | 0.0600046               | HistGradientBoostingClassifier on strict normalized shape atoms.                                                    |
| MLP                                | 0.82591  | 0.806871       | 0.842132        | 0.838229          | 0.822322  | 0.855016   | 0.466321                | 0.425651       | 0.556529        | 0.170339 | 0.220902              | 0.203372     | 0.234159      | 0.802469     | 0.85825      | 0.0557804               | Two-hidden-layer neural net on strict normalized shape atoms.                                                       |
| ridge logistic                     | 0.797704 | 0.782997       | 0.810223        | 0.781307          | 0.761656  | 0.811129   | 0.362694                | 0.267372       | 0.433099        | 0.184693 | 0.192696              | 0.177058     | 0.203042      | 0.740741     | 0.9375       | 0.196759                | L2 logistic regression on strict normalized shape atoms.                                                            |
| shape-only RF probe                | 0.793926 | 0.77152        | 0.819204        | 0.808998          | 0.782327  | 0.839648   | 0.404145                | 0.335628       | 0.442291        | 0.18892  | 0.188918              | 0.168        | 0.218432      | 0.734568     | 0.875        | 0.140432                | Random-forest shape probe requested by ticket; excludes amplitude, IDs, timing, topology, and injection parameters. |
| WaveAtomNet                        | 0.711945 | 0.704117       | 0.731483        | 0.71387           | 0.696528  | 0.753679   | 0.291883                | 0.188918       | 0.362754        | 0.237085 | 0.106937              | 0.0955258    | 0.124435      | 0.6875       | 0.752617     | 0.0651175               | New fused architecture: convolutional waveform branch plus normalized atom branch.                                  |
| traditional atom/template selector | 0.605008 | 0.597947       | 0.617895        | 0.570376          | 0.562687  | 0.583029   | 0.0569948               | 0.050705       | 0.108889        | 0.318239 | 0                     | 0            | 0             | 0.537037     | 0.65625      | 0.119213                | Fold-local q/template, timing-spread, early/late, derivative, and peak-tail conventional selector.                  |
| 1D-CNN                             | 0.535609 | 0.527702       | 0.559204        | 0.53954           | 0.533896  | 0.576956   | 0.0604491               | 0.0521916      | 0.11424         | 0.249647 | -0.0693993            | -0.0782271   | -0.0494268    | 0.524146     | 0.8125       | 0.288354                | Compact convolutional net on per-stave peak-normalized waveforms.                                                   |

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
| gradient-boosted trees             | 65          | 1150    | 8      | 0.875    |
| MLP                                | 58          | 1140    | 18     | 0.802469 |
| MLP                                | 59          | 972     | 186    | 0.85825  |
| MLP                                | 60          | 900     | 258    | 0.807403 |

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

## Stricter Charge Nulls

| mode                  | method                             | roc_auc  | average_precision | fixed95_clean_rejection | support_drift_auc_range | median_renormalization_factor | median_preserved_quantity_ratio |
| --------------------- | ---------------------------------- | -------- | ----------------- | ----------------------- | ----------------------- | ----------------------------- | ------------------------------- |
| peak_preserved        | traditional atom/template selector | 0.606899 | 0.570991          | 0.0569948               | 0.119213                | 0.974146                      | 1                               |
| peak_preserved        | ridge logistic                     | 0.801668 | 0.783573          | 0.360967                | 0.196759                | 0.974146                      | 1                               |
| peak_preserved        | gradient-boosted trees             | 0.846625 | 0.852069          | 0.455959                | 0.0681915               | 0.974146                      | 1                               |
| signed_area_preserved | traditional atom/template selector | 0.600352 | 0.568061          | 0.0569948               | 0.119213                | 0.80849                       | 1                               |
| signed_area_preserved | ridge logistic                     | 0.778541 | 0.767262          | 0.340242                | 0.196759                | 0.80849                       | 1                               |
| signed_area_preserved | gradient-boosted trees             | 0.846239 | 0.851836          | 0.450777                | 0.0593448               | 0.80849                       | 1                               |

The signed-area rows preserve the baseline-subtracted target-stave integral rather than positive charge. The peak-preserved rows reproduce the earlier amplitude-null logic. The charge-bin permutation below destroys labels within run and base-charge strata while retaining the score distribution:

| probe                                 | observed_auc | null_auc_mean | null_auc_ci_low | null_auc_ci_high | charge_null_auc_loss | n_permutations |
| ------------------------------------- | ------------ | ------------- | --------------- | ---------------- | -------------------- | -------------- |
| run_plus_charge_bin_label_permutation | 0.844903     | 0.499176      | 0.468636        | 0.526682         | 0.345727             | 40             |

## Shape-Cue Localization

Grouped dropout replaces each held-out group by its training-run mean before scoring a fold-local GBT. Positive values are AUC lost by removing that region or atom family.

| group                    | n_columns | baseline_auc | dropout_auc | delta_auc  | mean_fold_delta_auc | min_fold_delta_auc | max_fold_delta_auc |
| ------------------------ | --------- | ------------ | ----------- | ---------- | ------------------- | ------------------ | ------------------ |
| peak_samples_08_11       | 12        | 0.844903     | 0.725472    | 0.11943    | 0.112202            | 0                  | 0.174823           |
| rise_samples_04_07       | 12        | 0.844903     | 0.777402    | 0.0675007  | 0.0816566           | 0.028932           | 0.135802           |
| shape_width_atoms        | 9         | 0.844903     | 0.793996    | 0.0509067  | 0.0723688           | -0.037037          | 0.25               |
| pretrigger_samples_00_03 | 12        | 0.844903     | 0.815163    | 0.0297398  | 0.0485589           | 0.0238895          | 0.125              |
| terminal_samples_16_17   | 6         | 0.844903     | 0.821303    | 0.0235994  | 0.0165583           | -0.0493827         | 0.0625             |
| tail_samples_12_15       | 12        | 0.844903     | 0.826966    | 0.0179364  | 0.011997            | 0                  | 0.0293853          |
| tail_fraction_atoms      | 9         | 0.844903     | 0.840369    | 0.00453405 | 0.01072             | -0.0123457         | 0.0625             |

Feature-level permutation importance cross-check:

| feature                      | mean_auc_importance | min_auc_importance | max_auc_importance | stability_std |
| ---------------------------- | ------------------- | ------------------ | ------------------ | ------------- |
| ds_shape_std_peak_sample     | 0.0462231           | 0                  | 0.125              | 0.0382833     |
| ds_shape_mean_area_over_peak | 0.0377041           | -0.0185185         | 0.125              | 0.0440211     |
| ds_shape_mean_norm_s06       | 0.0243759           | -0.0200062         | 0.125              | 0.0481024     |
| ds_shape_std_norm_s04        | 0.0237727           | -0.0185185         | 0.0517082          | 0.026481      |
| ds_shape_mean_norm_s09       | 0.0216466           | -0.125             | 0.091105           | 0.0690511     |
| ds_shape_std_max_down_step   | 0.0157959           | 0                  | 0.0555556          | 0.0184939     |
| ds_shape_std_area_over_peak  | 0.0103009           | 0                  | 0.0308642          | 0.0102512     |
| ds_shape_std_norm_s06        | 0.00978591          | -0.00170441        | 0.0432099          | 0.0153245     |
| ds_shape_mean_norm_s07       | 0.00882271          | 0                  | 0.0308642          | 0.0107239     |
| ds_shape_std_norm_s15        | 0.00760159          | -0.0308642         | 0.0625             | 0.0276066     |
| ds_shape_mean_norm_s03       | 0.0062664           | -0.0185185         | 0.0221573          | 0.0130341     |
| ds_shape_std_norm_s17        | 0.00606529          | 0                  | 0.0185185          | 0.00719721    |
| ds_shape_std_norm_s16        | 0.00599634          | 0                  | 0.0142846          | 0.00499058    |
| ds_shape_mean_norm_s00       | 0.0053483           | 0                  | 0.0153775          | 0.00536067    |
| ds_shape_std_norm_s05        | 0.00504926          | -0.00307787        | 0.0123457          | 0.00545643    |

## Leakage And Systematics

| probe                                     | value    | notes                                                                  |
| ----------------------------------------- | -------- | ---------------------------------------------------------------------- |
| pre-injection D_t                         | 0.5      | Same for clean/injected pair members; should be near chance.           |
| absolute-amplitude-only GBT               | 0.527359 | Excluded nuisance channel; should be below the shape winner.           |
| run+charge-bin label permutation mean AUC | 0.499176 | Destroys labels within run and target-charge strata.                   |
| pair split violations                     | 0        | Must be zero.                                                          |
| forbidden strict-shape columns            | 0        | strict_shape_columns raises before fitting if forbidden inputs appear. |
| charge-bin count                          | 5        | Used for charge-pair-matched null permutations.                        |

Systematic limitations: injected overlap is not an external real-beam pile-up label; positive-charge and signed-area preservation still alter local curvature and noise correlations; only seven run blocks are available for CIs; neural models are deliberately laptop-scale; and localization is model-dependent. The result supports a normalized injected-recovery shape cue, not a calibrated pile-up rate.

## Verdict

`result.json` names `gradient-boosted trees` as the winner. Its AUC advantage over the traditional selector is 0.240 with bootstrap CI [0.220, 0.265]. The run-plus-charge-bin permutation mean AUC is 0.499; the winner's observed-minus-null AUC is 0.346. Therefore the all-three normalized shape cue does not vanish under the stricter charge-preserving nulls tested here, although adoption should remain limited to injection-recovery support until real pile-up truth is available.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07n_1781068159_1658_5f900b07_normalized_shape_charge_null.py --config configs/s07n_1781068159_1658_5f900b07_normalized_shape_charge_null.json
```

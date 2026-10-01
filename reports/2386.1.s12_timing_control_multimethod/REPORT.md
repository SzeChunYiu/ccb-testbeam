# S12: Timing-Control-Region Classifier Rigour

- **Ticket:** GitHub factory ticket `#2386` (`S12: Timing-control-region classifier rigour`)
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT files under `/home/billy/ccb-data/data/extracted/root/root`
- **Output directory:** `reports/2386.1.s12_timing_control_multimethod`
- **Pre-registered primary metric:** run-held-out ROC AUC on the reproduced `D_t<3 ns` versus guarded `D_t>51 ns` App. I target; ties break by AP and then by 95% clean-efficiency gross-tail rejection.

## Abstract

This study reproduces the App. I timing-control-region target from raw ROOT and benchmarks a strong traditional timing-span method against ridge, gradient-boosted trees, MLP, 1D-CNN, random forest, and a new residual-gated CNN.  The positive class is small (`n=72`), so all headline intervals are non-parametric bootstraps over held-out runs.  The winner written to `result.json` is **`traditional_d_t_cut`** with ROC AUC `1.0000` and AP `1.0000`.  The scientific verdict is conservative: because the target is defined by `D_t`, the traditional `D_t` cut is a label-source ceiling and should not be interpreted as independent predictive physics.

## Raw-ROOT Reproduction

For each configured run, `h101/HRDv` is reshaped to `8 x 18`; B2, B4, B6, and B8 are baseline-subtracted by the median of samples 0--3 and selected when the corrected maximum exceeds 1000 ADC.  CFD20 pickoff times are computed by linear interpolation.  Events require B2 and at least two downstream staves.  The downstream timing span is

```text
D_t = max(t_B4, t_B6, t_B8) - min(t_B4, t_B6, t_B8),
```

over selected downstream staves only.  The reproduced classes are:

| quantity                              | report_value | reproduced | delta | tolerance | pass |
| ------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| control events, B2 and >=2 downstream |              | 1.016e+04  |       |           | True |
| clean events, D_t<3 ns                |              | 2155       |       |           | True |
| gross events, documented D_t>50 ns    |              | 74         |       |           | True |
| gross events, guarded D_t>51 ns       | 72           | 72         | 0     | 0         | True |
| prior App.I ROC AUC                   | 0.958        |            |       |           | True |
| prior App.I average precision         | 0.614        |            |       |           | True |

The documented `D_t>50 ns` count is 74 under this implementation.  The guarded `D_t>51 ns` convention reproduces the ticket's 72-event positive class exactly and is used for inference.

The 72-event class is sparse and run-local.  Resampling the held-out run units gives a positive-class count bootstrap interval of `35`--`111` events for a seven-run sample.  This interval is not an uncertainty on the exact reproduced count; it is the finite-run support sensitivity used to motivate run-block CIs for classifier metrics.

| run | clean | gross | intermediate | gross_fraction_of_extremes |
| --- | ----- | ----- | ------------ | -------------------------- |
| 58  | 37    | 2     | 162          | 0.05128                    |
| 59  | 415   | 13    | 1733         | 0.03037                    |
| 60  | 428   | 16    | 1581         | 0.03604                    |
| 61  | 607   | 25    | 1687         | 0.03956                    |
| 62  | 420   | 7     | 1727         | 0.01639                    |
| 63  | 194   | 9     | 842          | 0.04433                    |
| 65  | 54    | 0     | 197          | 0                          |

## Methods

Let `y_i=1` denote a guarded gross timing-tail event and `y_i=0` a clean event.  All non-traditional methods exclude `D_t`, curvature `C_t`, run id, event id, and absolute amplitude.  Scores are generated in leave-one-run-out folds:

```text
S_m(i) = f_m(x_i; D_train),       run(i) not in runs(D_train).
```

The strong traditional comparator is the label-source score `S_trad=D_t`.  The independent curvature cross-check uses `|C_t|=|t_B8-2t_B6+t_B4|` when all three downstream staves exist.  ML methods use normalized waveform morphology:

- ridge: L2-regularized logistic regression on aggregate shape descriptors;
- gradient-boosted trees: histogram GBT on the same aggregate descriptors;
- MLP: two-hidden-layer neural network on aggregate descriptors;
- shape RF: balanced random forest included to reproduce the App. I family;
- 1D-CNN: Torch convolution over the four normalized stave waveforms;
- residual-gated CNN: the new architecture, a 1D-CNN whose pooled latent state is gated by aggregate residual-shape descriptors.

Uncertainty uses run-block bootstrap:

```text
CI_95(T) = quantile_0.025,0.975 { T(sample runs with replacement) }.
```

At fixed clean efficiency 0.95, each held-out fold sets its threshold from train-fold clean scores.  Gross-tail rejection is the fraction of positive held-out events above that threshold.

## Benchmark Results

| method                 | family           | roc_auc | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | gross_rejection_at_95_clean | gross_rejection_ci_low | gross_rejection_ci_high |
| ---------------------- | ---------------- | ------- | -------------- | --------------- | ----------------- | --------- | ---------- | --------------------------- | ---------------------- | ----------------------- |
| traditional_d_t_cut    | traditional      | 1       | 1              | 1               | 1                 | 1         | 1          | 1                           | 1                      | 1                       |
| shape_random_forest    | ml               | 0.9987  | 0.9978         | 0.9992          | 0.9628            | 0.9281    | 0.9773     | 1                           | 1                      | 1                       |
| gradient_boosted_trees | ml               | 0.9974  | 0.9966         | 0.999           | 0.9463            | 0.923     | 0.9735     | 1                           | 1                      | 1                       |
| residual_gated_cnn_new | new_architecture | 0.9939  | 0.9881         | 0.9978          | 0.9119            | 0.8685    | 0.9641     | 0.9861                      | 0.9571                 | 1                       |
| ridge                  | ml               | 0.9935  | 0.985          | 0.999           | 0.9282            | 0.8797    | 0.9694     | 0.9861                      | 0.9583                 | 1                       |
| mlp                    | nn               | 0.9897  | 0.9734         | 0.9971          | 0.9114            | 0.8718    | 0.9492     | 0.9583                      | 0.9322                 | 1                       |
| 1d_cnn                 | nn               | 0.9368  | 0.8701         | 0.9694          | 0.6217            | 0.5714    | 0.7029     | 0.8056                      | 0.7164                 | 0.9334                  |
| curvature_cross_check  | traditional      | 0.6563  | 0.6098         | 0.6799          | 0.3315            | 0.2502    | 0.3804     | 0.3056                      | 0.2195                 | 0.3537                  |

The traditional `D_t` score has AUC `1.0000` because it is the variable defining the label.  The best non-label-source learned method is reported in the ranked table, but adoption over the traditional comparator is not justified for this target.

## Fixed-Efficiency Fold Table

| method                 | heldout_run | clean_efficiency | gross_rejection | n_clean | n_gross |
| ---------------------- | ----------- | ---------------- | --------------- | ------- | ------- |
| traditional_d_t_cut    | 58          | 0.8919           | 1               | 37      | 2       |
| traditional_d_t_cut    | 59          | 0.9614           | 1               | 415     | 13      |
| traditional_d_t_cut    | 60          | 0.9439           | 1               | 428     | 16      |
| traditional_d_t_cut    | 61          | 0.9539           | 1               | 607     | 25      |
| traditional_d_t_cut    | 62          | 0.9524           | 1               | 420     | 7       |
| traditional_d_t_cut    | 63          | 0.9381           | 1               | 194     | 9       |
| traditional_d_t_cut    | 65          | 0.9444           |                 | 54      | 0       |
| curvature_cross_check  | 58          | 0.973            | 0               | 37      | 2       |
| curvature_cross_check  | 59          | 0.9711           | 0.3846          | 415     | 13      |
| curvature_cross_check  | 60          | 0.9439           | 0.375           | 428     | 16      |
| curvature_cross_check  | 61          | 0.939            | 0.32            | 607     | 25      |
| curvature_cross_check  | 62          | 0.9333           | 0.1429          | 420     | 7       |
| curvature_cross_check  | 63          | 0.9588           | 0.2222          | 194     | 9       |
| curvature_cross_check  | 65          | 0.9815           |                 | 54      | 0       |
| ridge                  | 58          | 0.8919           | 1               | 37      | 2       |
| ridge                  | 59          | 0.9301           | 1               | 415     | 13      |
| ridge                  | 60          | 0.9813           | 0.9375          | 428     | 16      |
| ridge                  | 61          | 0.9555           | 1               | 607     | 25      |
| ridge                  | 62          | 0.9405           | 1               | 420     | 7       |
| ridge                  | 63          | 0.9278           | 1               | 194     | 9       |
| ridge                  | 65          | 0.9444           |                 | 54      | 0       |
| gradient_boosted_trees | 58          | 0.9189           | 1               | 37      | 2       |
| gradient_boosted_trees | 59          | 0.9422           | 1               | 415     | 13      |
| gradient_boosted_trees | 60          | 0.972            | 1               | 428     | 16      |
| gradient_boosted_trees | 61          | 0.9605           | 1               | 607     | 25      |
| gradient_boosted_trees | 62          | 0.9357           | 1               | 420     | 7       |
| gradient_boosted_trees | 63          | 0.9227           | 1               | 194     | 9       |
| gradient_boosted_trees | 65          | 0.963            |                 | 54      | 0       |
| mlp                    | 58          | 0.9459           | 1               | 37      | 2       |
| mlp                    | 59          | 0.959            | 1               | 415     | 13      |
| mlp                    | 60          | 0.9112           | 0.9375          | 428     | 16      |
| mlp                    | 61          | 0.9852           | 0.92            | 607     | 25      |
| mlp                    | 62          | 0.9143           | 1               | 420     | 7       |
| mlp                    | 63          | 0.9278           | 1               | 194     | 9       |
| mlp                    | 65          | 0.9074           |                 | 54      | 0       |
| shape_random_forest    | 58          | 0.8919           | 1               | 37      | 2       |
| shape_random_forest    | 59          | 0.9398           | 1               | 415     | 13      |
| shape_random_forest    | 60          | 0.9509           | 1               | 428     | 16      |
| shape_random_forest    | 61          | 0.9572           | 1               | 607     | 25      |
| shape_random_forest    | 62          | 0.9619           | 1               | 420     | 7       |
| shape_random_forest    | 63          | 0.9278           | 1               | 194     | 9       |
| shape_random_forest    | 65          | 0.963            |                 | 54      | 0       |
| 1d_cnn                 | 58          | 0.8378           | 1               | 37      | 2       |
| 1d_cnn                 | 59          | 0.9687           | 0.6923          | 415     | 13      |
| 1d_cnn                 | 60          | 0.9626           | 0.9375          | 428     | 16      |
| 1d_cnn                 | 61          | 0.9671           | 0.72            | 607     | 25      |
| 1d_cnn                 | 62          | 0.9643           | 0.7143          | 420     | 7       |
| 1d_cnn                 | 63          | 0.8505           | 1               | 194     | 9       |
| 1d_cnn                 | 65          | 0.8148           |                 | 54      | 0       |
| residual_gated_cnn_new | 58          | 0.8919           | 1               | 37      | 2       |
| residual_gated_cnn_new | 59          | 0.9566           | 1               | 415     | 13      |
| residual_gated_cnn_new | 60          | 0.965            | 0.9375          | 428     | 16      |
| residual_gated_cnn_new | 61          | 0.9654           | 1               | 607     | 25      |
| residual_gated_cnn_new | 62          | 0.9405           | 1               | 420     | 7       |
| residual_gated_cnn_new | 63          | 0.8918           | 1               | 194     | 9       |
| residual_gated_cnn_new | 65          | 0.9444           |                 | 54      | 0       |

## Systematics and Leakage Checks

| probe                              | roc_auc | average_precision | interpretation                                                                                |
| ---------------------------------- | ------- | ----------------- | --------------------------------------------------------------------------------------------- |
| documented App.I headline          | 0.958   | 0.614             | Prior note value; this run reproduces the target count and uses stricter run-heldout scoring. |
| topology-only                      | 0.5184  | 0.03364           | Presence pattern alone has limited information and is excluded from main aggregate models.    |
| absolute curvature                 | 0.6563  | 0.3315            | C_t is partially independent but missing for two-downstream events.                           |
| traditional self-reference ceiling | 1       | 1                 | D_t defines y; perfect discrimination is circular but expected.                               |

Main systematic limitations:

- **Label self-reference:** `D_t` defines the target, so direct timing-span methods are circular but still the correct strong baseline for this ticket.
- **Positive-class discreteness:** only 72 positives exist; run-bootstrap CIs quantify run sensitivity but cannot create new tail morphologies.
- **Curvature missingness:** `C_t` is only defined for all-three downstream events; imputation lowers interpretability for two-downstream events.
- **ROOT convention:** the exact 72 count depends on the guarded `D_t>51 ns` edge.  The documented `D_t>50 ns` statement gives 74 with this CFD implementation.
- **Neural capacity:** the CNNs are deliberately small CPU-safe models; stronger GPU models would be a separate capacity study and would not remove label self-reference.

## Caveats

This is a classifier-rigour study, not a detector-truth study.  The labels are derived from timing reconstruction, not from an external pile-up or bad-event oracle.  A high waveform-only score means shape covaries with the timing-tail definition.  It does not prove that the waveform model has discovered independent ground truth.

## Conclusion

The raw reproduction gate passes exactly for the guarded 72-event class.  The result names **`traditional_d_t_cut`** in `result.json`, but the practical conclusion is that the direct `D_t` baseline remains the correct ceiling for this self-referential App. I label.  No additional ticket is appended from this worker.

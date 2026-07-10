# S23: P02f critic replication on fresh non-P02d exemplar labels

- **Ticket:** 1783449285.17291.7d2e0caa
- **Worker:** testbeam-laptop-4
- **Date:** 2026-07-10
- **Input:** raw B-stack `HRDv` ROOT files in `data/root/root`
- **Runs:** 58, 59, 60, 61, 62, 63, 65

## Abstract
This study repeats the P02f critic question without reusing the P02d latent-distance artifact or any P02d cluster label.  The fresh target is built directly from raw clean Sample-II events: every event with pre-injection `D_t < 3.0 ns` contributes one raw-clean exemplar and one independently injected two-pulse exemplar.  The task is therefore a controlled morphology-generalization target rather than a consumer of P02d's artifact interface.

## Raw-ROOT Reproduction Gate
Before fitting any model, the script rebuilds the P02d/S07 parent quantities from raw ROOT using the existing raw loader.

| quantity                                   | report_value | reproduced | delta        | tolerance | pass | sample_size |
| ------------------------------------------ | ------------ | ---------- | ------------ | --------- | ---- | ----------- |
| P02 early-peak pulse rate, peak_sample<=3  | 0.044        | 0.0438833  | -0.000116667 | 0.002     | True | 60000       |
| S07 parent guarded gross events, D_t>51 ns | 72           | 72         | 0            | 0         | True | 10156       |
| P02d transparent morphology ROC AUC        | 0.692169     | 0.692169   | 0            | 1e-12     | True | 2227        |

The gate verifies the selected-control raw event population and the published transparent P02d AUC.  Failure of any row aborts the benchmark.

## Fresh Exemplar Label Construction
For each clean raw event, one positive exemplar is created by adding a delayed, scaled copy of one selected downstream waveform to itself:

\[
x'_{s,j}=x_{s,j}+\alpha x_{s,j-\Delta},\quad
\Delta\sim U(2,\ldots,6),\quad
\alpha\sim U(0.12,0.38).
\]

The negative exemplar is the untouched raw waveform.  Labels are known from this construction, not from `D_t`, P02d clusters, q-template atoms, or downstream artifact columns.

| run | raw_clean | fresh_injected_exemplar | total |
| --- | --------- | ----------------------- | ----- |
| 58  | 37        | 37                      | 74    |
| 59  | 415       | 415                     | 830   |
| 60  | 428       | 428                     | 856   |
| 61  | 607       | 607                     | 1214  |
| 62  | 420       | 420                     | 840   |
| 63  | 194       | 194                     | 388   |
| 65  | 54        | 54                      | 108   |

## Models
Evaluation is leave-one-run-out.  All tabular models receive normalized waveform-shape summaries and presence flags only; absolute amplitude is excluded from the primary features because injection can alter peak height.  The traditional comparator is a run-held-out nearest-neighbor consumer:

\[
s(x)=\min_{z\in\mathcal N_0}\|\tilde x-z\|_2-\min_{z\in\mathcal N_1}\|\tilde x-z\|_2,
\]

where standardization and exemplar pools are fitted on training runs only.  Positive scores mean closer to positive injected exemplars than to raw-clean exemplars.  ML competitors are ridge regression on the binary label, histogram gradient-boosted trees, one-hidden-layer MLP, a 1D-CNN over the four B-stave waveforms, and a compact attention encoder.  The attention encoder is the new architecture beyond the requested ridge/GBT/MLP/CNN set.

## Head-to-Head Results
Metrics are computed from held-out predictions.  Brackets are 95% run-block bootstrap confidence intervals.

| method                       | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high | notes                                                                                       |
| ---------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- | ------------------------------------------------------------------------------------------- |
| gradient_boosted_trees       | 0.929616 | 0.916973       | 0.943561        | 0.932107          | 0.919078  | 0.947941   | 0.107863 | 0.0974643    | 0.119521      | Histogram gradient-boosted classifier on normalized morphology features.                    |
| mlp                          | 0.90956  | 0.897757       | 0.924178        | 0.909862          | 0.892743  | 0.92656    | 0.120265 | 0.110741     | 0.128894      | One-hidden-layer MLP classifier on normalized morphology features.                          |
| ridge                        | 0.832014 | 0.812672       | 0.843573        | 0.830862          | 0.809814  | 0.854003   | 0.212046 | 0.210148     | 0.215166      | Linear ridge regression score on normalized morphology features.                            |
| traditional_nearest_neighbor | 0.824245 | 0.801704       | 0.840525        | 0.846113          | 0.823853  | 0.861904   | 0.212302 | 0.208963     | 0.21597       | Standardized training-run nearest-neighbor distance to fresh clean/injected exemplar pools. |
| cnn                          | 0.761306 | 0.735508       | 0.796731        | 0.769764          | 0.741571  | 0.802734   | 0.197762 | 0.18293      | 0.209555      | Small 1D-CNN over four normalized B-stave waveforms.                                        |
| attention                    | 0.712082 | 0.686262       | 0.744426        | 0.739875          | 0.71548   | 0.76802    | 0.215114 | 0.204026     | 0.223988      | Compact self-attention encoder over waveform samples; new architecture in this study.       |

By-run held-out metrics:

| method                       | heldout_run | roc_auc  | average_precision | n_negative | n_positive |
| ---------------------------- | ----------- | -------- | ----------------- | ---------- | ---------- |
| traditional_nearest_neighbor | 58          | 0.79401  | 0.828518          | 37         | 37         |
| traditional_nearest_neighbor | 59          | 0.804512 | 0.824202          | 415        | 415        |
| traditional_nearest_neighbor | 60          | 0.835346 | 0.860026          | 428        | 428        |
| traditional_nearest_neighbor | 61          | 0.834498 | 0.855005          | 607        | 607        |
| traditional_nearest_neighbor | 62          | 0.857137 | 0.875622          | 420        | 420        |
| traditional_nearest_neighbor | 63          | 0.775029 | 0.795563          | 194        | 194        |
| traditional_nearest_neighbor | 65          | 0.774005 | 0.803994          | 54         | 54         |
| ridge                        | 58          | 0.796932 | 0.846717          | 37         | 37         |
| ridge                        | 59          | 0.831314 | 0.842281          | 415        | 415        |
| ridge                        | 60          | 0.847667 | 0.840187          | 428        | 428        |
| ridge                        | 61          | 0.851187 | 0.834542          | 607        | 607        |
| ridge                        | 62          | 0.850499 | 0.87356           | 420        | 420        |
| ridge                        | 63          | 0.791955 | 0.784922          | 194        | 194        |
| ridge                        | 65          | 0.759602 | 0.762025          | 54         | 54         |
| gradient_boosted_trees       | 58          | 0.923667 | 0.923772          | 37         | 37         |
| gradient_boosted_trees       | 59          | 0.93129  | 0.936343          | 415        | 415        |
| gradient_boosted_trees       | 60          | 0.949027 | 0.952485          | 428        | 428        |
| gradient_boosted_trees       | 61          | 0.921307 | 0.925136          | 607        | 607        |
| gradient_boosted_trees       | 62          | 0.945785 | 0.951647          | 420        | 420        |
| gradient_boosted_trees       | 63          | 0.919479 | 0.914492          | 194        | 194        |
| gradient_boosted_trees       | 65          | 0.900549 | 0.881705          | 54         | 54         |
| mlp                          | 58          | 0.891892 | 0.894324          | 37         | 37         |
| mlp                          | 59          | 0.922206 | 0.927707          | 415        | 415        |
| mlp                          | 60          | 0.911783 | 0.912515          | 428        | 428        |
| mlp                          | 61          | 0.918493 | 0.918687          | 607        | 607        |
| mlp                          | 62          | 0.935629 | 0.940634          | 420        | 420        |
| mlp                          | 63          | 0.897173 | 0.877791          | 194        | 194        |
| mlp                          | 65          | 0.829561 | 0.811062          | 54         | 54         |
| cnn                          | 58          | 0.758218 | 0.773594          | 37         | 37         |
| cnn                          | 59          | 0.750129 | 0.759379          | 415        | 415        |
| cnn                          | 60          | 0.825645 | 0.830046          | 428        | 428        |
| cnn                          | 61          | 0.761126 | 0.770737          | 607        | 607        |
| cnn                          | 62          | 0.773129 | 0.778693          | 420        | 420        |
| cnn                          | 63          | 0.703901 | 0.70036           | 194        | 194        |
| cnn                          | 65          | 0.717078 | 0.721505          | 54         | 54         |
| attention                    | 58          | 0.706355 | 0.750311          | 37         | 37         |
| attention                    | 59          | 0.701594 | 0.731081          | 415        | 415        |
| attention                    | 60          | 0.770973 | 0.791677          | 428        | 428        |
| attention                    | 61          | 0.685976 | 0.719038          | 607        | 607        |
| attention                    | 62          | 0.715901 | 0.754937          | 420        | 420        |
| attention                    | 63          | 0.727083 | 0.73173           | 194        | 194        |
| attention                    | 65          | 0.728052 | 0.72535           | 54         | 54         |

## Leakage And Systematics
| check                             | value | pass | detail                                                      |
| --------------------------------- | ----- | ---- | ----------------------------------------------------------- |
| train_test_pair_id_overlap        | 0     | True | Raw/injected paired variants stay in the same held-out run. |
| p02d_artifact_columns_used        | 0     | True | No P02d latent artifact or cluster-label columns are read.  |
| forbidden_primary_feature_columns | 0     | True | None.                                                       |
| raw_reproduction_gate             | 1     | True | All parent raw-ROOT numbers matched.                        |

Primary systematics are: finite run count for bootstrap resampling; injected positives are controlled morphology exemplars rather than measured beam pile-up; downstream-only shape information is physically expected to dominate because the corruption is injected downstream; and the NN/ML models operate on short 18-sample waveforms, so larger architectures are not excluded by a compact sweep.

## Verdict
The winner is **gradient_boosted_trees** by held-out ROC AUC.  In this fresh non-P02d exemplar replication, the winning method reaches ROC AUC 0.930 [0.917, 0.944] and AP 0.932 [0.919, 0.948].  This supports morphology generalization for controlled fresh exemplars while separating it from P02d artifact-interface reuse.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.py --config configs/s23_1783449285_17291_7d2e0caa_p02f_fresh_exemplar_bakeoff.json
```

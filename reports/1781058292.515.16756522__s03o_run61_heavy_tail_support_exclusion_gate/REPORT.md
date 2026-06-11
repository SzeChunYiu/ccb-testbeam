# Study report: S03o - Run-61 heavy-tail support exclusion gate

- **Ticket:** 1781058292.515.16756522
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-11
- **Input:** reduced raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs [58, 59, 60, 61, 62, 63, 65]
- **Config:** `configs/s03o_1781058292_515_16756522_run61_support_exclusion.yaml`
- **Winner named in `result.json`:** `traditional_hier_amp` with excluded-support sigma68 = 1.892 ns, run-block 95% CI [1.588, 2.335] ns.

## 0. Question

Does the run-61-like heavy-tail timewalk gain survive the stricter condition that candidate heavy-tail support atoms are excluded from every training fold and evaluated only as a blinded transfer set? The atomic decision is whether a transparent analytic timewalk model, or one of several ML/NN residual correctors, has the smallest held-out pairwise timing width on that excluded support without leakage.

## 1. Reproduction from raw ROOT

The S00 selected-pulse count was reproduced directly from raw `HRDv` branches before fitting any model. The gate passes with exact zero tolerance:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The model table used for the benchmark is also raw-derived: downstream B4/B6/B8 events are loaded from the same ROOT files, baseline-subtracted with samples 0--3, cut at amplitude > 1000 ADC, and timed with templates built only from the current fold's non-support training rows.

## 2. Candidate support atom

The excluded atom is predeclared from waveform observables only:

\[
I_i = 1[L_i > 5.85,\; p_i \ge 9,\; s_i > 0.25],
\]

where \(L_i=\sum_{j=9}^{17} w_{ij}/A_i\) is late normalized charge, \(p_i\) is peak sample, and \(s_i=\overline{w/A}_{10:14}-\overline{w/A}_{5:8}\). An event is in the blinded support if any downstream pulse satisfies \(I_i=1\). These quantities do not use residual labels, same-event partner times, event order, or run identity.

|   run |   pulses |   events |   support_pulses |   support_events |   median_late_norm |   p90_late_norm |   support_event_fraction |
|------:|---------:|---------:|-----------------:|-----------------:|-------------------:|----------------:|-------------------------:|
|    58 |      219 |       73 |               57 |               23 |             5.0682 |          6.6019 |                 0.31507  |
|    59 |     2289 |      763 |              122 |               80 |             4.8474 |          6.1789 |                 0.10485  |
|    60 |     2424 |      808 |              116 |               76 |             4.959  |          6.2181 |                 0.094059 |
|    61 |     2799 |      933 |              203 |              123 |             5.1071 |          6.323  |                 0.13183  |
|    62 |     2421 |      807 |              135 |               90 |             4.8967 |          6.2544 |                 0.11152  |
|    63 |     1110 |      370 |               76 |               44 |             4.7445 |          6.1869 |                 0.11892  |
|    65 |      198 |       66 |               29 |               12 |             4.8992 |          6.4872 |                 0.18182  |

## 3. Traditional method

The strong non-ML comparator is a frozen analytic amplitude timewalk model with stave-specific partial pooling. For pulse \(i\), the residual target is the base corrected time minus the mean of the other two downstream staves:

\[
y_i = \left(t_i^0 - x_i/v\right) - \frac12\sum_{k\ne i} \left(t_k^0 - x_k/v\right).
\]

The model is

\[
\hat y_i = \alpha_{s(i)} + \beta_1 \log(1+A_i) + \beta_2 \frac{1000}{A_i} + \beta_3 \sqrt{\frac{1000}{A_i}} + \sum_m \gamma_{m,s(i)} z_{im},
\]

fit by ridge regression after standardization. Candidate support events are removed from the training rows. Held-out run coefficients are never fit; deployment uses only the population and stave terms learned from other non-support runs. Coefficient drift is measured by refitting the same traditional model with support rows included in the training side and computing the L2 distance between standardized coefficients.

Coefficient-drift summary:

| quantity                               |   median |    min |    max |
|:---------------------------------------|---------:|-------:|-------:|
| standardized_coefficient_l2_drift      |   3.0468 | 2.3375 | 3.3424 |
| max_abs_standardized_coefficient_drift |   1.7042 | 1.3272 | 1.8083 |

## 4. ML and NN methods

All methods predict the same residual target \(y_i\), train on the same non-support rows from the other runs, and are evaluated on the same excluded-support events in the held-out run.

- `ridge_waveform`: standardized ridge on 18 normalized samples, log amplitude, inverse-amplitude terms, peak, area/amp, support-score covariates, and stave indicators.
- `gradient_boosted_trees`: histogram gradient-boosted trees over the same waveform feature vector.
- `mlp_waveform`: feed-forward neural network (`MLPRegressor`) over the waveform feature vector.
- `tiny_1d_cnn`: a trainable one-dimensional convolutional regressor with 5 filters of width 5, ReLU activation, global-average pooling, scalar metadata, and a linear head. It is intentionally small because the local ROOT-capable environment has no PyTorch/TensorFlow.
- `support_gated_ensemble`: a new architecture for this ticket; it blends the transparent traditional correction and the nonlinear boosted-tree correction with a raw waveform support gate, \(g=\sigma(q)\): \(\hat y=(1-g)\hat y_{trad}+g\hat y_{gbt}\). The gate uses the predeclared support score only and is not fit on held-out support labels.

The hyperparameter scan used run-group CV inside each outer training fold. The complete CV table is in `model_cv_scan.csv`; best fold-mean MSE rows are:

| model                  |   score_mse |   n_train | matrix      | params                                                                                                                                                                                                       |
|:-----------------------|------------:|----------:|:------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| gradient_boosted_trees |      2.9126 |      7686 | waveform    | {"l2_regularization": 0.1, "learning_rate": 0.05, "max_bins": 64, "max_iter": 80, "max_leaf_nodes": 7, "random_state": 20260746}                                                                             |
| gradient_boosted_trees |      3.1859 |      9138 | waveform    | {"l2_regularization": 0.1, "learning_rate": 0.05, "max_bins": 64, "max_iter": 80, "max_leaf_nodes": 7, "random_state": 20260748}                                                                             |
| mlp_waveform           |      2.9481 |      7686 | waveform    | {"activation": "relu", "alpha": 0.001, "early_stopping": true, "hidden_layer_sizes": [32], "learning_rate_init": 0.001, "max_iter": 250, "n_iter_no_change": 20, "random_state": 20260783, "solver": "adam"} |
| mlp_waveform           |      3.1662 |      9966 | waveform    | {"activation": "relu", "alpha": 0.001, "early_stopping": true, "hidden_layer_sizes": [32], "learning_rate_init": 0.001, "max_iter": 250, "n_iter_no_change": 20, "random_state": 20260780, "solver": "adam"} |
| ridge_waveform         |      3.1619 |      7686 | waveform    | {"alpha": 10.0}                                                                                                                                                                                              |
| ridge_waveform         |      3.1785 |      7686 | waveform    | {"alpha": 1.0}                                                                                                                                                                                               |
| tiny_1d_cnn            |      3.1458 |      7686 | cnn         | {"epochs": 100, "kernel_size": 5, "l2": 0.0005, "learning_rate": 0.015, "n_filters": 5, "random_state": 20264920}                                                                                            |
| tiny_1d_cnn            |      3.4499 |      9966 | cnn         | {"epochs": 100, "kernel_size": 5, "l2": 0.0005, "learning_rate": 0.015, "n_filters": 5, "random_state": 20264917}                                                                                            |
| traditional_hier_amp   |      3.2399 |      7686 | traditional | {"alpha": 1.0}                                                                                                                                                                                               |
| traditional_hier_amp   |      3.2709 |      7686 | traditional | {"alpha": 10.0}                                                                                                                                                                                              |

## 5. Head-to-head benchmark

Primary metric: pairwise residual sigma68 on excluded held-out support. Secondary metrics are full RMS, 95th percentile absolute residual, >5 ns tail fraction, and bias-vs-log-amplitude slope. Intervals are 95% run-block bootstrap CIs over the seven leave-one-run-out folds.

| method                 |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   full_rms_ns |   full_rms_ns_ci_low |   full_rms_ns_ci_high |   p95_abs_residual_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:-----------------------|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|----------------------:|----------------------:|-------------------:|
| traditional_hier_amp   |       1.8917 |              1.5882 |               2.3349 |        3.8982 |               3.321  |                4.3764 |                4.9844 |              0.049851 |               1344 |
| tiny_1d_cnn            |       1.9229 |              1.6396 |               2.2851 |        3.8402 |               3.1439 |                4.4443 |                4.549  |              0.043155 |               1344 |
| gradient_boosted_trees |       1.9439 |              1.6984 |               2.225  |        3.6083 |               3.0284 |                4.0881 |                4.5183 |              0.042411 |               1344 |
| support_gated_ensemble |       1.9992 |              1.7213 |               2.3493 |        3.6795 |               3.136  |                4.1991 |                4.8183 |              0.046131 |               1344 |
| mlp_waveform           |       2.014  |              1.7816 |               2.1847 |        3.4198 |               2.8249 |                3.947  |                4.4416 |              0.039435 |               1344 |
| ridge_waveform         |       2.0784 |              1.7071 |               2.437  |        3.8606 |               3.2637 |                4.427  |                4.6463 |              0.046875 |               1344 |
| template_phase_base    |       3.3558 |              3.1874 |               3.6838 |        4.4354 |               3.8967 |                4.9156 |                6.456  |              0.22024  |               1344 |

Per-run excluded-support sigma68:

|   heldout_run | method                 |   sigma68_ns |   full_rms_ns |   p95_abs_residual_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:-----------------------|-------------:|--------------:|----------------------:|----------------------:|-------------------:|
|            58 | support_gated_ensemble |       1.2241 |        4.0628 |                2.9755 |              0.028986 |                 69 |
|            58 | traditional_hier_amp   |       1.3134 |        4.3203 |                2.9433 |              0.043478 |                 69 |
|            58 | gradient_boosted_trees |       1.4541 |        4.0711 |                4.3985 |              0.057971 |                 69 |
|            58 | tiny_1d_cnn            |       1.4654 |        4.1293 |                3.0056 |              0.043478 |                 69 |
|            58 | ridge_waveform         |       1.7123 |        4.8141 |                3.1741 |              0.028986 |                 69 |
|            58 | mlp_waveform           |       2.571  |        4.3457 |                5.8331 |              0.10145  |                 69 |
|            58 | template_phase_base    |       3.1248 |        5.3362 |                5.5031 |              0.31884  |                 69 |
|            59 | gradient_boosted_trees |       1.7027 |        4.5345 |                4.1671 |              0.045833 |                240 |
|            59 | support_gated_ensemble |       1.846  |        4.5917 |                4.2956 |              0.045833 |                240 |
|            59 | tiny_1d_cnn            |       1.9163 |        4.8807 |                5.3253 |              0.054167 |                240 |
|            59 | ridge_waveform         |       1.9361 |        4.83   |                4.9905 |              0.05     |                240 |
|            59 | traditional_hier_amp   |       1.939  |        4.8248 |                4.8172 |              0.05     |                240 |
|            59 | mlp_waveform           |       2.1054 |        4.4691 |                4.9248 |              0.05     |                240 |
|            59 | template_phase_base    |       3.8013 |        5.1856 |                7.1276 |              0.22083  |                240 |
|            60 | traditional_hier_amp   |       1.6293 |        3.7286 |                4.6258 |              0.04386  |                228 |
|            60 | tiny_1d_cnn            |       1.6965 |        3.5881 |                3.8778 |              0.04386  |                228 |
|            60 | gradient_boosted_trees |       1.7423 |        3.5059 |                6.5177 |              0.057018 |                228 |
|            60 | mlp_waveform           |       1.7656 |        3.0949 |                4.0674 |              0.039474 |                228 |
|            60 | support_gated_ensemble |       1.7987 |        3.5907 |                6.1754 |              0.057018 |                228 |
|            60 | ridge_waveform         |       1.8995 |        3.5064 |                4.3179 |              0.048246 |                228 |
|            60 | template_phase_base    |       3.3402 |        4.5539 |                7.448  |              0.25     |                228 |
|            61 | mlp_waveform           |       2.1696 |        2.7804 |                3.8878 |              0.0271   |                369 |
|            61 | gradient_boosted_trees |       2.5503 |        3.0618 |                4.7751 |              0.04336  |                369 |
|            61 | tiny_1d_cnn            |       2.5908 |        3.289  |                5.0765 |              0.059621 |                369 |
|            61 | traditional_hier_amp   |       2.6286 |        3.3691 |                5.8861 |              0.065041 |                369 |
|            61 | support_gated_ensemble |       2.6458 |        3.1566 |                5.1004 |              0.054201 |                369 |
|            61 | ridge_waveform         |       2.6817 |        3.3787 |                5.0726 |              0.054201 |                369 |
|            61 | template_phase_base    |       3.2511 |        3.743  |                6.5023 |              0.073171 |                369 |
|            62 | mlp_waveform           |       1.5804 |        3.7495 |                3.9692 |              0.033333 |                270 |
|            62 | gradient_boosted_trees |       1.6358 |        3.9378 |                3.4917 |              0.025926 |                270 |
|            62 | traditional_hier_amp   |       1.7202 |        4.294  |                4.2404 |              0.033333 |                270 |
|            62 | tiny_1d_cnn            |       1.7281 |        4.2702 |                4.1928 |              0.02963  |                270 |
|            62 | ridge_waveform         |       1.7461 |        4.1529 |                4.0664 |              0.033333 |                270 |
|            62 | support_gated_ensemble |       1.7596 |        4.0175 |                3.7634 |              0.02963  |                270 |
|            62 | template_phase_base    |       3.7578 |        4.8061 |                6.0283 |              0.20741  |                270 |
|            63 | mlp_waveform           |       1.6499 |        1.9514 |                4.1468 |              0.030303 |                132 |
|            63 | tiny_1d_cnn            |       1.7659 |        2.4093 |                4.803  |              0.05303  |                132 |
|            63 | traditional_hier_amp   |       1.8119 |        2.5328 |                4.7518 |              0.05303  |                132 |
|            63 | ridge_waveform         |       1.8421 |        2.4445 |                4.0188 |              0.045455 |                132 |
|            63 | support_gated_ensemble |       1.8482 |        2.033  |                3.9705 |              0.030303 |                132 |
|            63 | gradient_boosted_trees |       1.8779 |        1.9023 |                3.6873 |              0.022727 |                132 |
|            63 | template_phase_base    |       3.4714 |        3.1406 |                5.4686 |              0.20455  |                132 |
|            65 | traditional_hier_amp   |       1.1421 |        1.163  |                2.3025 |              0        |                 36 |
|            65 | tiny_1d_cnn            |       1.157  |        1.1776 |                2.5468 |              0        |                 36 |
|            65 | ridge_waveform         |       1.2055 |        1.1687 |                2.0165 |              0        |                 36 |
|            65 | support_gated_ensemble |       1.3102 |        1.3523 |                2.5266 |              0        |                 36 |
|            65 | gradient_boosted_trees |       1.4731 |        1.4216 |                2.6683 |              0        |                 36 |
|            65 | mlp_waveform           |       2.162  |        2.2439 |                4.4716 |              0        |                 36 |
|            65 | template_phase_base    |       3.1458 |        2.8302 |                5.555  |              0.33333  |                 36 |

Paired deltas versus the traditional comparator:

| method                 | reference            | metric              |   delta_method_minus_reference |     ci_low |   ci_high | bootstrap_unit   |
|:-----------------------|:---------------------|:--------------------|-------------------------------:|-----------:|----------:|:-----------------|
| tiny_1d_cnn            | traditional_hier_amp | sigma68_ns          |                      0.043248  | -0.052364  | 0.12191   | heldout_run      |
| gradient_boosted_trees | traditional_hier_amp | sigma68_ns          |                      0.049793  | -0.091231  | 0.20312   | heldout_run      |
| support_gated_ensemble | traditional_hier_amp | sigma68_ns          |                      0.10105   | -0.0091983 | 0.21129   | heldout_run      |
| mlp_waveform           | traditional_hier_amp | sigma68_ns          |                      0.11983   | -0.20099   | 0.4416    | heldout_run      |
| ridge_waveform         | traditional_hier_amp | sigma68_ns          |                      0.1774    |  0.019255  | 0.27666   | heldout_run      |
| template_phase_base    | traditional_hier_amp | sigma68_ns          |                      1.4957    |  0.93009   | 1.8922    | heldout_run      |
| mlp_waveform           | traditional_hier_amp | tail_frac_abs_gt5ns |                     -0.0088674 | -0.025725  | 0.014231  | heldout_run      |
| gradient_boosted_trees | traditional_hier_amp | tail_frac_abs_gt5ns |                     -0.0070265 | -0.016908  | 0.005396  | heldout_run      |
| tiny_1d_cnn            | traditional_hier_amp | tail_frac_abs_gt5ns |                     -0.0060834 | -0.012381  | 0.0037037 | heldout_run      |
| ridge_waveform         | traditional_hier_amp | tail_frac_abs_gt5ns |                     -0.0033289 | -0.012223  | 0.002446  | heldout_run      |
| support_gated_ensemble | traditional_hier_amp | tail_frac_abs_gt5ns |                     -0.0033188 | -0.010614  | 0.0048272 | heldout_run      |
| template_phase_base    | traditional_hier_amp | tail_frac_abs_gt5ns |                      0.17073   |  0.097539  | 0.21258   | heldout_run      |

Verdict: `traditional_hier_amp` wins the predeclared primary metric. The result is adoption-safe only as a support-gate conclusion: all models were trained without the candidate atoms, so the comparison measures extrapolative transfer to the atom rather than ordinary in-distribution performance.

## 6. Falsification and multiple comparisons

Pre-registration from the ticket: compare sigma68, full RMS, 95th-percentile absolute residual, coefficient drift, and tail-fraction delta on the excluded support with run-block bootstrap CIs. The falsification test was: if the best ML/NN method did not improve sigma68 over the frozen traditional comparator, or if the improvement CI included zero after accounting for the five non-traditional contenders, the support-transfer ML claim would be rejected.

Five non-traditional methods were compared with the traditional reference. The result table stores Bonferroni-aware interpretation in `paired_deltas_vs_traditional.csv`; CIs are reported unadjusted but the report interprets a method as clearly better only when the two-sided 95% CI excludes zero with margin large enough to survive the five-comparison family.

## 7. Threats to validity

**Benchmark/selection.** The baseline is not a strawman: it is the S03 analytic inverse-amplitude family with stave interactions and ridge shrinkage, refit under the same support-exclusion rule as the ML methods.

**Data leakage.** The outer split is by run. Training removes all candidate-support events in the training runs. Features exclude run number, event id, event order, and partner-stave corrected times. Template timing is rebuilt inside each fold using non-support training rows only.

**Metric misuse.** The primary metric is sigma68, but the report also includes full RMS, p95 absolute residuals, and >5 ns tail fraction. The target is a residual proxy from same-particle downstream consistency, not a truth timestamp.

**Post-hoc selection.** Support thresholds and metrics are fixed in the YAML config. Hyperparameters are selected inside training folds only. The new gated ensemble was specified before seeing the output as a physics/ML hybrid to test whether a raw support gate helps extrapolation.

## 8. Systematics and caveats

Run 58 and run 65 have smaller event counts and stronger late-tail occupancy than the central Sample-II runs, so run-block intervals are wider than pair bootstrap intervals would be. The tiny CNN is a real trainable convolutional model, but intentionally small and CPU-friendly; a larger PyTorch CNN could change the NN ranking. The support atom is based on waveform shape rather than external truth, so it should be treated as an operational gate, not a physical particle class.

Leakage checks:

|   heldout_run | check                           |   value | unit   |
|--------------:|:--------------------------------|--------:|:-------|
|            58 | train_rows_on_candidate_support |       0 | rows   |
|            58 | heldout_support_rows            |      69 | rows   |
|            58 | train_heldout_event_overlap     |       0 | events |
|            59 | train_rows_on_candidate_support |       0 | rows   |
|            59 | heldout_support_rows            |     240 | rows   |
|            59 | train_heldout_event_overlap     |       0 | events |
|            60 | train_rows_on_candidate_support |       0 | rows   |
|            60 | heldout_support_rows            |     228 | rows   |
|            60 | train_heldout_event_overlap     |       0 | events |
|            61 | train_rows_on_candidate_support |       0 | rows   |
|            61 | heldout_support_rows            |     369 | rows   |
|            61 | train_heldout_event_overlap     |       0 | events |
|            62 | train_rows_on_candidate_support |       0 | rows   |
|            62 | heldout_support_rows            |     270 | rows   |
|            62 | train_heldout_event_overlap     |       0 | events |
|            63 | train_rows_on_candidate_support |       0 | rows   |
|            63 | heldout_support_rows            |     132 | rows   |
|            63 | train_heldout_event_overlap     |       0 | events |
|            65 | train_rows_on_candidate_support |       0 | rows   |
|            65 | heldout_support_rows            |      36 | rows   |
|            65 | train_heldout_event_overlap     |       0 | events |

## 9. Provenance and reproducibility

Command:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03o_1781058292_515_16756522_run61_support_exclusion.py --config configs/s03o_1781058292_515_16756522_run61_support_exclusion.yaml
```

Artifacts: `reproduction_match_table.csv`, `support_summary.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `paired_deltas_vs_traditional.csv`, `pairwise_residuals_excluded_support.csv`, `model_cv_scan.csv`, `traditional_coefficients.csv`, `coefficient_drift.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

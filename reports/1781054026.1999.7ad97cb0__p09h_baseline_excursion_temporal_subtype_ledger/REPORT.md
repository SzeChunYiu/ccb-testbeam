# P09h: baseline-excursion temporal subtype ledger

- **Ticket:** `1781054026.1999.7ad97cb0`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT in `data/root/root`; no simulation or sorted side-table inputs.
- **Split:** leave-one-run-out over the current-comparison baseline-excursion rows; uncertainty is a run-block bootstrap.

## 1. Preregistered question and endpoint

The ticket asks whether P09 baseline-excursion candidates are one nuisance class or a separable set of temporal subtypes that differently explain pile-up residuals, dropout recovery harm, charge bias, and timing tails. The primary benchmark metric was fixed as macro-F1 against a train-run-frozen operational subtype ledger. Physics interpretation is based on subtype endpoint enrichment, not on macro-F1 alone.

## 2. Raw-ROOT reproduction gate

The script first scans the raw B-stack ROOT files through the P09a/S00 selected-pulse gate: baseline median over samples 0--3, even channels B2/B4/B6/B8, and amplitude \(A>1000\) ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |

The per-run counts and raw file hashes are in `reproduction_counts_by_run.csv` and `input_sha256.csv`. The program raises before model fitting if the exact count fails.

## 3. Methods

For each baseline-excursion pulse \(i\), the waveform \(x_i(t)\) is peak-normalized after the raw pedestal subtraction used by P09a. The duplicate-channel charge-bias proxy is

\[ b_i = \log(1+A_i) - \log(1+A_i^{dup}), \]

the dropout proxy is \(d_i=\max(0,-m_i^{post})\), and the secondary/pile-up proxy is

\[ s_i = m_i^{(2)} f_i^{late}. \]

For each held-out run \(r\), subtype thresholds are fitted only on \(R\setminus r\). The deterministic comparator assigns the first matching subtype in this priority order: pretrigger slope, early-sample offset, rising-edge distortion, late peak phase, tail/dropout recovery, downstream topology, and nominal baseline excursion. Quantile thresholds are recorded in `fold_subtype_thresholds.csv`.

The ML/NN methods learn the same train-run-frozen subtype labels and are evaluated on the held-out run: class-balanced ridge, histogram gradient-boosted trees, a two-layer MLP, a 1D-CNN, and a new `temporal_gate_cnn_new` that gates early-window and tail-window convolution features with the scalar pretrigger/tail/dropout summaries. Features exclude run id, event ids, current group, and labels.

For method \(m\),

\[ \mathrm{macroF1}_m = \frac{1}{K}\sum_{k=1}^{K} \frac{2P_{mk}R_{mk}}{P_{mk}+R_{mk}}, \]

with \(K=7\) subtypes. Bootstrap confidence intervals resample held-out runs with replacement.

## 4. Head-to-head benchmark

| method                        |   n_eval |   macro_f1 |   balanced_accuracy |   accuracy |   ledger_utility | macro_f1_ci95   | balanced_accuracy_ci95   | accuracy_ci95   | ledger_utility_ci95   |
|:------------------------------|---------:|-----------:|--------------------:|-----------:|-----------------:|:----------------|:-------------------------|:----------------|:----------------------|
| traditional_train_frozen_cuts |     1577 |   0.857143 |            1        |   1        |         0.857143 | [0.857, 0.857]  | [1.000, 1.000]           | [1.000, 1.000]  | [0.857, 0.857]        |
| ridge                         |     1577 |   0.489343 |            0.71128  |   0.81357  |         0.489343 | [0.452, 0.533]  | [0.669, 0.865]           | [0.792, 0.844]  | [0.452, 0.533]        |
| gradient_boosted_trees        |     1577 |   0.699232 |            0.812769 |   0.994927 |         0.699232 | [0.691, 0.708]  | [0.793, 0.833]           | [0.993, 0.998]  | [0.691, 0.708]        |
| mlp                           |     1577 |   0.527947 |            0.590023 |   0.942295 |         0.527947 | [0.487, 0.573]  | [0.557, 0.647]           | [0.931, 0.961]  | [0.487, 0.573]        |
| cnn_1d                        |     1577 |   0.336117 |            0.572849 |   0.61319  |         0.336117 | [0.321, 0.351]  | [0.543, 0.643]           | [0.570, 0.647]  | [0.321, 0.351]        |
| temporal_gate_cnn_new         |     1577 |   0.318721 |            0.532207 |   0.553583 |         0.318721 | [0.291, 0.350]  | [0.490, 0.585]           | [0.518, 0.603]  | [0.291, 0.350]        |

ML-minus-traditional deltas:

| method                 |   macro_f1_minus_traditional |   macro_f1_minus_traditional_ci_low |   macro_f1_minus_traditional_ci_high |   balanced_accuracy_minus_traditional |   balanced_accuracy_minus_traditional_ci_low |   balanced_accuracy_minus_traditional_ci_high |   accuracy_minus_traditional |   accuracy_minus_traditional_ci_low |   accuracy_minus_traditional_ci_high |   ledger_utility_minus_traditional |   ledger_utility_minus_traditional_ci_low |   ledger_utility_minus_traditional_ci_high |
|:-----------------------|-----------------------------:|------------------------------------:|-------------------------------------:|--------------------------------------:|---------------------------------------------:|----------------------------------------------:|-----------------------------:|------------------------------------:|-------------------------------------:|-----------------------------------:|------------------------------------------:|-------------------------------------------:|
| ridge                  |                    -0.3678   |                           -0.395088 |                            -0.272033 |                             -0.28872  |                                    -0.331993 |                                     -0.233571 |                  -0.18643    |                         -0.2075     |                          -0.15561    |                          -0.3678   |                                 -0.39647  |                                 -0.273837  |
| gradient_boosted_trees |                    -0.157911 |                           -0.166885 |                            -0.145869 |                             -0.187231 |                                    -0.204293 |                                     -0.166863 |                  -0.00507292 |                         -0.00848267 |                          -0.00247932 |                          -0.157911 |                                 -0.169095 |                                 -0.0214052 |
| mlp                    |                    -0.329195 |                           -0.367766 |                            -0.233866 |                             -0.409977 |                                    -0.450864 |                                     -0.357356 |                  -0.0577045  |                         -0.0682903  |                          -0.0422944  |                          -0.329195 |                                 -0.36407  |                                 -0.194536  |
| cnn_1d                 |                    -0.521026 |                           -0.536238 |                            -0.503781 |                             -0.427151 |                                    -0.452463 |                                     -0.359773 |                  -0.38681    |                         -0.435548   |                          -0.357907   |                          -0.521026 |                                 -0.532526 |                                 -0.497137  |
| temporal_gate_cnn_new  |                    -0.538422 |                           -0.562453 |                            -0.439854 |                             -0.467793 |                                    -0.511829 |                                     -0.405165 |                  -0.446417   |                         -0.481469   |                          -0.380385   |                          -0.538422 |                                 -0.558636 |                                 -0.41183   |

The winner named in `result.json` is **traditional_train_frozen_cuts** with macro-F1 0.857 (CI [0.857, 0.857]).

## 5. Subtype endpoint ledger

Subtype counts by held-out truth label:

|   run | current_group   | subtype_true               |   n |
|------:|:----------------|:---------------------------|----:|
|    44 | high_20nA       | early_sample_offset        |  21 |
|    44 | high_20nA       | pretrigger_slope           |   6 |
|    44 | high_20nA       | rising_edge_distortion     |   6 |
|    44 | high_20nA       | tail_recovery_dropout      |   1 |
|    45 | high_20nA       | early_sample_offset        | 252 |
|    45 | high_20nA       | peak_phase_late            |   4 |
|    45 | high_20nA       | pretrigger_slope           |  63 |
|    45 | high_20nA       | rising_edge_distortion     |  68 |
|    45 | high_20nA       | tail_recovery_dropout      |   6 |
|    47 | low_2nA         | early_sample_offset        |  17 |
|    47 | low_2nA         | pretrigger_slope           |   4 |
|    47 | low_2nA         | rising_edge_distortion     |   4 |
|    47 | low_2nA         | tail_recovery_dropout      |   2 |
|    48 | high_20nA       | early_sample_offset        | 126 |
|    48 | high_20nA       | nominal_baseline_excursion |   1 |
|    48 | high_20nA       | peak_phase_late            |   1 |
|    48 | high_20nA       | pretrigger_slope           |  25 |
|    48 | high_20nA       | rising_edge_distortion     |  43 |
|    48 | high_20nA       | tail_recovery_dropout      |   5 |
|    49 | high_20nA       | early_sample_offset        | 139 |
|    49 | high_20nA       | peak_phase_late            |   2 |
|    49 | high_20nA       | pretrigger_slope           |  36 |
|    49 | high_20nA       | rising_edge_distortion     |  51 |
|    49 | high_20nA       | tail_recovery_dropout      |   8 |
|    50 | high_20nA       | early_sample_offset        |  57 |
|    50 | high_20nA       | peak_phase_late            |   2 |
|    50 | high_20nA       | pretrigger_slope           |  13 |
|    50 | high_20nA       | rising_edge_distortion     |  20 |
|    50 | high_20nA       | tail_recovery_dropout      |   5 |
|    51 | high_20nA       | early_sample_offset        |  48 |
|    51 | high_20nA       | pretrigger_slope           |   9 |
|    51 | high_20nA       | rising_edge_distortion     |  15 |
|    51 | high_20nA       | tail_recovery_dropout      |   1 |
|    52 | high_20nA       | early_sample_offset        |  15 |
|    52 | high_20nA       | pretrigger_slope           |   4 |
|    52 | high_20nA       | rising_edge_distortion     |  13 |
|    52 | high_20nA       | tail_recovery_dropout      |   1 |
|    53 | high_20nA       | early_sample_offset        |  56 |
|    53 | high_20nA       | nominal_baseline_excursion |   1 |
|    53 | high_20nA       | pretrigger_slope           |   7 |
|    53 | high_20nA       | rising_edge_distortion     |  11 |
|    54 | high_20nA       | early_sample_offset        |  37 |
|    54 | high_20nA       | peak_phase_late            |   1 |
|    54 | high_20nA       | pretrigger_slope           |   8 |
|    54 | high_20nA       | rising_edge_distortion     |   6 |
|    55 | high_20nA       | early_sample_offset        |  52 |
|    55 | high_20nA       | pretrigger_slope           |  10 |
|    55 | high_20nA       | rising_edge_distortion     |  12 |
|    55 | high_20nA       | tail_recovery_dropout      |   3 |
|    56 | high_20nA       | early_sample_offset        |  66 |
|    56 | high_20nA       | peak_phase_late            |   2 |
|    56 | high_20nA       | pretrigger_slope           |   9 |
|    56 | high_20nA       | rising_edge_distortion     |  20 |
|    56 | high_20nA       | tail_recovery_dropout      |   3 |
|    57 | high_20nA       | early_sample_offset        | 106 |
|    57 | high_20nA       | nominal_baseline_excursion |   1 |
|    57 | high_20nA       | peak_phase_late            |   1 |
|    57 | high_20nA       | pretrigger_slope           |  30 |
|    57 | high_20nA       | rising_edge_distortion     |  31 |
|    57 | high_20nA       | tail_recovery_dropout      |  10 |

For the selected winner, the high-minus-low endpoint ledger is:

| method                        | subtype                    |   prevalence_within_method_current_rows_high_minus_low |   timing_tail_gt5_rate_high_minus_low |   charge_bias_abs_mean_high_minus_low |   charge_bias_abs_res68_high_minus_low |   dropout_harm_rate_high_minus_low |   secondary_fraction_mean_high_minus_low |   downstream_topology_rate_high_minus_low | prevalence_within_method_current_rows_high_minus_low_ci95   | timing_tail_gt5_rate_high_minus_low_ci95   | charge_bias_abs_mean_high_minus_low_ci95   | charge_bias_abs_res68_high_minus_low_ci95   | dropout_harm_rate_high_minus_low_ci95   | secondary_fraction_mean_high_minus_low_ci95   | downstream_topology_rate_high_minus_low_ci95   |
|:------------------------------|:---------------------------|-------------------------------------------------------:|--------------------------------------:|--------------------------------------:|---------------------------------------:|-----------------------------------:|-----------------------------------------:|------------------------------------------:|:------------------------------------------------------------|:-------------------------------------------|:-------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------------|:-----------------------------------------------|
| traditional_train_frozen_cuts | nominal_baseline_excursion |                                               1        |                           nan         |                          nan          |                            nan         |                        nan         |                             nan          |                               nan         | [1, 1]                                                      |                                            |                                            |                                             |                                         |                                               |                                                |
| traditional_train_frozen_cuts | peak_phase_late            |                                               1        |                           nan         |                          nan          |                            nan         |                        nan         |                             nan          |                               nan         | [1, 1]                                                      |                                            |                                            |                                             |                                         |                                               |                                                |
| traditional_train_frozen_cuts | rising_edge_distortion     |                                               0.973333 |                            -0.0810811 |                            0.0389771  |                              0.0849479 |                         -0.0641892 |                              -0.0289398  |                                 0.0304054 | [0.9, 1]                                                    | [-0.117, -0.0529]                          | [0.0156, 0.0701]                           | [0.0577, 0.107]                             | [-0.0964, -0.0278]                      | [-0.0341, -0.0177]                            | [0.0174, 0.051]                                |
| traditional_train_frozen_cuts | early_sample_offset        |                                               0.965726 |                             0.0980392 |                            0.00961193 |                              0.004419  |                         -0.131282  |                               0.00182315 |                                 0.0461538 | [0.869, 1]                                                  | [0.0818, 0.123]                            | [-0.0131, 0.0244]                          | [-0.0233, 0.0241]                           | [-0.153, -0.116]                        | [-0.000973, 0.00508]                          | [0.0366, 0.0558]                               |
| traditional_train_frozen_cuts | pretrigger_slope           |                                               0.964286 |                            -0.181818  |                            0.0758894  |                              0.0756308 |                         -0.15      |                               0.0134123  |                                 0.0545455 | [0.86, 1]                                                   | [-0.24, -0.133]                            | [0.043, 0.108]                             | [0.0567, 0.106]                             | [-0.185, -0.108]                        | [0.00889, 0.0212]                             | [0.0352, 0.0809]                               |
| traditional_train_frozen_cuts | tail_recovery_dropout      |                                               0.911111 |                            -0.0465116 |                            0.102181   |                              0.119688  |                          0.162791  |                               0.01485    |                                 0.0465116 | [0.719, 1]                                                  | [-0.0909, 0]                               | [0.0603, 0.138]                            | [0.0853, 0.129]                             | [0.0975, 0.211]                         | [0.00525, 0.0279]                             | [0, 0.139]                                     |

The high-minus-low columns report prevalence, timing-tail rate \(P(|\Delta t_{dup}|>5)\), mean absolute charge bias, charge-bias 68% residual width, dropout-harm rate, secondary-fraction mean, and downstream-topology rate; adjacent `_ci95` columns are run-block bootstrap 95% intervals. These are descriptive endpoint ledgers; the labels remain operational pseudo-labels until visually or externally calibrated.

## 6. Systematics and leakage checks

| check                                   |   value | pass   | note                                                                               |
|:----------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------|
| raw_reproduction_before_modeling        |  640737 | True   | script raises before subtype fitting if selected-pulse count mismatches            |
| leave_one_run_train_test_overlap        |       0 | True   | held-out run never appears in the train sample                                     |
| all_methods_same_eval_rows              |       1 | True   | all methods score the same baseline-excursion pulses                               |
| identifier_columns_absent_from_features |       0 | True   | run, event id, current group, and subtype labels are excluded from SCALAR_FEATURES |

Systematic limitations are direct. First, the subtype truth is an operational ledger frozen from raw waveform observables, not an external detector truth label. Second, the low-current side has only runs 46 and 47, so high-minus-low prevalence intervals are wide for sparse subtypes. Third, several endpoints share waveform ingredients with the subtype cuts; the endpoint table therefore supports mechanism triage, not independent causal proof. Fourth, the CNN models were intentionally small to keep this worker CPU/GPU bounded; a larger architecture is not justified until a blinded visual subtype calibration exists.

## 7. Conclusion

Baseline-excursion candidates are not a single homogeneous nuisance under this operational ledger: the frozen cuts split them into pretrigger, early-offset, rising-edge, late-phase, tail/dropout, downstream-topology, and nominal subtypes with different timing-tail, charge-bias, dropout, and secondary-fraction profiles. The strong traditional train-frozen subtype scorecard wins the head-to-head benchmark because it is exactly aligned with the auditable subtype definition; the ML/NN models are useful as smoothness and leakage sentinels but do not add a defensible discovery claim. The next useful experiment is blinded visual calibration of the ledger, not a larger neural net.

## 8. Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `baseline_excursion_current_rows.csv.gz`, `heldout_subtype_predictions.csv.gz`, `method_metrics.csv`, `run_bootstrap_ci.csv`, `ml_minus_traditional.csv`, `subtype_ledger_by_current.csv`, `subtype_ledger_high_minus_low.csv`, `subtype_ledger_high_minus_low_ci.csv`, `fold_audit.csv`, `fold_subtype_thresholds.csv`, and `leakage_checks.csv` are in this folder.

Runtime: 448.8 s.

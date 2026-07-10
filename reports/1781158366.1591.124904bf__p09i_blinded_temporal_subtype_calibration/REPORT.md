# P09i: blinded visual calibration of baseline-excursion temporal subtypes

- **Ticket:** `1781158366.1591.124904bf`
- **Worker:** `testbeam-laptop-2`
- **Upstream frozen ledger:** `reports/1781054026.1999.7ad97cb0__p09h_baseline_excursion_temporal_subtype_ledger`
- **Primary endpoint:** calibrated F1 against blinded reviewer consensus, split by held-out run with run-block bootstrap CIs.

## 1. Question and design

P09h found that baseline-excursion candidates split into temporal subtypes, but its labels were operational pseudo-labels. P09i asks which of those subtypes look physical enough for downstream veto or recovery policy under a blinded calibration. The gallery rows are sampled from the P09h held-out current-comparison ledger, balanced by subtype and current group. Reviewers are deterministic blinded rubrics: they see morphology and endpoint summaries but not the P09h subtype name or any method prediction.

## 2. Raw ROOT reproduction

Before loading P09h predictions, the script reruns the B-stack raw ROOT selected-pulse gate through the P09a/P09d scanner. The gate uses the same selected-pulse definition as P09h: raw B-stack ROOT files, even B2/B4/B6/B8 channels, baseline subtraction from early samples, and amplitude above the frozen selected-pulse threshold.

| Quantity | Expected | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |

Per-run counts and raw file hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`. The program raises before calibration if the exact raw ROOT count does not match.

## 3. Blinded reviewer calibration

For pulse \(i\), the shape reviewer score is

\[ S_i = 0.26 z(MAD_i) + 0.24 z(|slope_i|) + 0.18 z(f_i^{early}) + 0.16 z(|\Delta t_i|) + 0.16 z(d_i), \]

and the endpoint reviewer score is

\[ E_i = 0.28 z(f_i^{late}) + 0.24 z(|b_i|) + 0.22 z(d_i) + 0.16 z(q_i^{secondary}) + 0.10 I_i^{downstream}. \]

The hybrid reviewer uses \(H_i = 0.34S_i + 0.34E_i + 0.22I(|\Delta t_i|>5) + 0.10I(d_i>0.18)\). A row is reviewer-positive when at least two of the three reviewers pass their frozen thresholds. These scores are deterministic stand-ins for blinded visual scoring, so the report treats them as calibration evidence rather than human truth.

Gallery composition:

| current_group   | subtype_true               |   n |
|:----------------|:---------------------------|----:|
| high_20nA       | early_sample_offset        |  36 |
| high_20nA       | nominal_baseline_excursion |   3 |
| high_20nA       | peak_phase_late            |  13 |
| high_20nA       | pretrigger_slope           |  36 |
| high_20nA       | rising_edge_distortion     |  36 |
| high_20nA       | tail_recovery_dropout      |  36 |
| low_2nA         | early_sample_offset        |  17 |
| low_2nA         | pretrigger_slope           |   4 |
| low_2nA         | rising_edge_distortion     |   4 |
| low_2nA         | tail_recovery_dropout      |   2 |

Inter-reviewer agreement:

| pair               |   agreement |   cohen_kappa |
|:-------------------|------------:|--------------:|
| shape_vs_endpoint  |    0.636364 |     -0.117006 |
| shape_vs_hybrid    |    0.786096 |      0.352381 |
| endpoint_vs_hybrid |    0.828877 |      0.141956 |
| unanimous_fraction |    0.625668 |    nan        |

## 4. Benchmark methods

The traditional method is P09h's train-run-frozen temporal subtype cut set. The ML/NN competitors are the P09h ridge classifier, histogram gradient-boosted trees, MLP, 1D-CNN, and new temporal-gated CNN. For method \(m\), its held-out subtype prediction is mapped to a policy score \(p_{im}\) using the frozen subtype-policy table in the config. The binary policy action is \(a_{im}=I(p_{im}\ge0.60)\). The primary metric is

\[ F1_m = \frac{2 P_m R_m}{P_m+R_m}, \quad P_m=Pr(y_i=1|a_{im}=1), \quad R_m=Pr(a_{im}=1|y_i=1). \]

Average precision uses the continuous subtype policy score. Confidence intervals resample runs with replacement.

Head-to-head benchmark:

| method                        |   n_eval |   n_runs |   calibrated_f1 |   balanced_accuracy |   curated_precision |   curated_recall |   average_precision |   action_rate | calibrated_f1_ci95   | balanced_accuracy_ci95   | curated_precision_ci95   | curated_recall_ci95   | average_precision_ci95   |
|:------------------------------|---------:|---------:|----------------:|--------------------:|--------------------:|-----------------:|--------------------:|--------------:|:---------------------|:-------------------------|:-------------------------|:----------------------|:-------------------------|
| traditional_train_frozen_cuts |      187 |       13 |        0.227979 |            0.548485 |            0.128655 |         1        |            0.189116 |      0.914439 | [0.093, 0.329]       | [0.530, 0.567]           | [0.049, 0.197]           | [1.000, 1.000]        | [0.080, 0.273]           |
| ridge                         |      187 |       13 |        0.224599 |            0.540909 |            0.127273 |         0.954545 |            0.163117 |      0.882353 | [0.097, 0.315]       | [0.514, 0.589]           | [0.051, 0.189]           | [0.917, 1.000]        | [0.074, 0.241]           |
| gradient_boosted_trees        |      187 |       13 |        0.22335  |            0.536364 |            0.125714 |         1        |            0.170369 |      0.935829 | [0.091, 0.323]       | [0.519, 0.556]           | [0.048, 0.193]           | [1.000, 1.000]        | [0.065, 0.268]           |
| temporal_gate_cnn_new         |      187 |       13 |        0.221053 |            0.531818 |            0.125    |         0.954545 |            0.181101 |      0.898396 | [0.082, 0.328]       | [0.438, 0.566]           | [0.043, 0.196]           | [0.764, 1.000]        | [0.048, 0.222]           |
| cnn_1d                        |      187 |       13 |        0.217143 |            0.525758 |            0.124183 |         0.863636 |            0.176842 |      0.818182 | [0.097, 0.304]       | [0.488, 0.604]           | [0.051, 0.186]           | [0.786, 1.000]        | [0.057, 0.259]           |
| mlp                           |      187 |       13 |        0.211538 |            0.50303  |            0.11828  |         1        |            0.1568   |      0.994652 | [0.086, 0.304]       | [0.500, 0.511]           | [0.045, 0.179]           | [1.000, 1.000]        | [0.048, 0.238]           |

ML/NN minus traditional deltas:

| method                 |   calibrated_f1_minus_traditional |   calibrated_f1_minus_traditional_ci_low |   calibrated_f1_minus_traditional_ci_high |   balanced_accuracy_minus_traditional |   balanced_accuracy_minus_traditional_ci_low |   balanced_accuracy_minus_traditional_ci_high |   curated_precision_minus_traditional |   curated_precision_minus_traditional_ci_low |   curated_precision_minus_traditional_ci_high |   curated_recall_minus_traditional |   curated_recall_minus_traditional_ci_low |   curated_recall_minus_traditional_ci_high |   average_precision_minus_traditional |   average_precision_minus_traditional_ci_low |   average_precision_minus_traditional_ci_high |
|:-----------------------|----------------------------------:|-----------------------------------------:|------------------------------------------:|--------------------------------------:|---------------------------------------------:|----------------------------------------------:|--------------------------------------:|---------------------------------------------:|----------------------------------------------:|-----------------------------------:|------------------------------------------:|-------------------------------------------:|--------------------------------------:|---------------------------------------------:|----------------------------------------------:|
| ridge                  |                       -0.00338034 |                              -0.0176058  |                                0.0105241  |                           -0.00757576 |                                   -0.0326543 |                                    0.0315849  |                           -0.00138224 |                                  -0.00958799 |                                    0.006413   |                         -0.0454545 |                                -0.0833333 |                                          0 |                           -0.0259992  |                                   -0.0506558 |                                   -0.00107707 |
| gradient_boosted_trees |                       -0.00462902 |                              -0.00823222 |                               -0.00132441 |                           -0.0121212  |                                   -0.020469  |                                   -0.00362319 |                           -0.00294069 |                                  -0.00552273 |                                   -0.00081922 |                          0         |                                 0         |                                          0 |                           -0.0187471  |                                   -0.0556459 |                                    0.00295427 |
| mlp                    |                       -0.0164408  |                              -0.0271381  |                               -0.00674734 |                           -0.0454545  |                                   -0.0617284 |                                   -0.0283006  |                           -0.0103754  |                                  -0.0188109  |                                   -0.00377663 |                          0         |                                 0         |                                          0 |                           -0.0323163  |                                   -0.130581  |                                    0.00012493 |
| cnn_1d                 |                       -0.0108364  |                              -0.0339713  |                                0.0157153  |                           -0.0227273  |                                   -0.0629688 |                                    0.0531267  |                           -0.00447196 |                                  -0.0169367  |                                    0.00969443 |                         -0.136364  |                                -0.214286  |                                          0 |                           -0.012274   |                                   -0.113376  |                                    0.0288084  |
| temporal_gate_cnn_new  |                       -0.00692664 |                              -0.0337284  |                                0.0057384  |                           -0.0166667  |                                   -0.115402  |                                    0.0155461  |                           -0.00365497 |                                  -0.0185228  |                                    0.00393263 |                         -0.0454545 |                                -0.235662  |                                          0 |                           -0.00801532 |                                   -0.128516  |                                    0.00949489 |

The winner named in `result.json` is **traditional_train_frozen_cuts** with calibrated F1 0.228 (CI [0.093, 0.329]).

## 5. Endpoint enrichment

| subtype                    |   n |   reviewer_positive_rate |   timing_tail_rate |   dropout_harm_rate |   mean_abs_charge_bias |   mean_secondary_fraction |   downstream_topology_rate |
|:---------------------------|----:|-------------------------:|-------------------:|--------------------:|-----------------------:|--------------------------:|---------------------------:|
| early_sample_offset        |  53 |                0.0188679 |           0.301887 |            0.886792 |               0.477362 |                 0.0292555 |                  0.0188679 |
| nominal_baseline_excursion |   3 |                0         |           0.666667 |            0.666667 |               0.28909  |                 0.0160633 |                  0.333333  |
| peak_phase_late            |  13 |                0         |           0.615385 |            0.461538 |               0.274829 |                 0.015061  |                  0         |
| pretrigger_slope           |  40 |                0.4       |           0.55     |            0.775    |               0.292476 |                 0.0314611 |                  0.025     |
| rising_edge_distortion     |  40 |                0.05      |           0.9      |            0.15     |               0.357082 |                 0.127598  |                  0         |
| tail_recovery_dropout      |  38 |                0.0789474 |           0.947368 |            0.157895 |               0.283617 |                 0.095418  |                  0.0526316 |

Endpoint enrichment is descriptive. Several reviewer inputs are derived from the same waveform summaries that motivated P09h, so enrichment supports subtype triage but does not establish independent detector truth.

## 6. Systematics and caveats

| check                                 |   value | pass   | note                                                                                    |
|:--------------------------------------|--------:|:-------|:----------------------------------------------------------------------------------------|
| raw_reproduction_before_calibration   |  640737 | True   | fresh raw ROOT scan must match the frozen selected-pulse count exactly                  |
| upstream_p09h_reproduction_consistent |  640737 | True   | P09h ledger count is identical to the fresh P09i raw ROOT count                         |
| all_methods_cover_gallery             |       1 | True   | every method scores the same blinded gallery rows                                       |
| reviewer_blinded_to_subtype           |       0 | True   | reviewer score equations use endpoint columns only and not subtype_true or subtype_pred |
| run_split_inherited_from_p09h         |      13 | True   | method predictions are P09h leave-one-run-out held-out predictions                      |

Key caveats: first, reviewer labels are deterministic blinded rubrics, not newly collected human labels. Second, the gallery is balanced for calibration and is not a prevalence estimate. Third, low-current support is small, so run-block CIs are intentionally wider than row bootstrap CIs. Fourth, P09h model predictions are frozen; P09i evaluates calibration transfer and does not retrain the ML/NN models on reviewer labels.

## 7. Conclusion

The blinded calibration supports a nonuniform physicality ranking across P09h baseline-excursion temporal subtypes. Pretrigger-slope candidates carry the clearest reviewer-positive signal in this balanced gallery, while tail-recovery and rising-edge candidates mostly express endpoint-risk structure rather than reviewer consensus. Downstream-topology is absent from the held-out balanced gallery and remains uncalibrated here. The best calibrated benchmark is `traditional_train_frozen_cuts`; the result should be used as an uncertainty layer over P09h rather than as a replacement for real visual labels.

## 8. Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_counts_by_run.csv`, `balanced_blinded_gallery.csv`, `reviewer_calibrated_gallery.csv`, `reviewer_agreement.csv`, `method_scoreboard.csv`, `benchmark_run_bootstrap_ci.csv`, `ml_minus_traditional.csv`, `endpoint_enrichment_by_subtype.csv`, `benchmark_per_run_metrics.csv`, and `leakage_checks.csv` are in this folder.

Runtime: 17.0 s.

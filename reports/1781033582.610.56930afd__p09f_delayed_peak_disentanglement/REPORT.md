# P09f: delayed-peak pile-up charge-bias disentanglement

- **Study ID:** P09f
- **Ticket:** `1781033582.610.56930afd`
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Depends on:** P09a/P09b/P09c delayed-peak taxonomy and P09d recovery refit
- **Config:** `configs/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.json`

## 0. Question
For the P09c delayed-peak morphology, can a frozen conventional rule or run-held-out ML/NN models distinguish overlap-like secondary structure from charge-bias/dropout-like delayed peaks strongly enough to decide recover, bias-correct, or abstain?

The preregistered endpoint is a three-way operational decision: `overlap_like`, `charge_bias_like`, or `abstain`. The primary model-selection metric is `decision_utility`, a fixed weighted score combining binary overlap average precision, non-abstained balanced accuracy, abstention F1, and the signs of the two physics deltas.

## 1. Reproduction
The first executable step scans raw B-stack ROOT files in `data/root/root` using the S00/P09a gate: even B2/B4/B6/B8 channels, baseline median over samples 0-3, and amplitude >1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |

Per-run selected counts and raw ROOT SHA-256 hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`. Model training is skipped if this exact-count reproduction fails.

## 2. Operational Definitions
For a selected delayed candidate \(i\), the even-channel normalized waveform is \(x_i(t)\), the duplicate-channel log charge is \(q_i^{dup}=\log(1+A_i^{dup})\), and the even-channel log charge is \(q_i=\log(1+A_i)\). The charge-bias proxy is

\[ b_i = q_i - q_i^{dup}. \]

The recovered secondary-fraction proxy is

\[ s_i = m_i^{(2)} f_i^{late}, \]

where \(m_i^{(2)}\) is the largest positive sample outside the main peak neighborhood and \(f_i^{late}\) is the positive area fraction in samples 12-17. For each held-out run, robust z scores and the label thresholds are fitted only on non-held-out delayed candidates:

\[ z_f(i)=\frac{f_i-\mathrm{median}_{j\in T} f_j}{1.4826\,\mathrm{MAD}_{j\in T} f_j}. \]

`overlap_like` requires high secondary/late/timing-span evidence without a stronger charge/dropout/baseline score. `charge_bias_like` requires high charge-bias, dropout, or baseline evidence without stronger overlap evidence. Conflicts and weak-evidence delayed peaks are labeled `ambiguous_abstain`.

## 3. Methods
The traditional method is a frozen score margin, \(p_i=\sigma(O_i-B_i)\), where \(O_i\) is the train-thresholded overlap score and \(B_i\) is the train-thresholded charge/dropout/baseline score. This is the strongest conventional comparator because it directly encodes the morphology and charge-bias diagnostics named in the ticket while keeping every threshold train-run-only.

The ML/NN methods use the same held-out folds and the same delayed-candidate evaluation rows. Ridge is a class-balanced ridge classifier. Gradient-boosted trees use histogram boosting. The MLP is a two-layer ReLU classifier. The 1D-CNN uses waveform samples plus scalar summaries. The new architecture, `charge_gated_cnn_new`, gates early convolution channels by the scalar charge/dropout/pretrigger feature vector before the final classifier.

Features exclude run, event, channel, stave, and label columns. Scores in `[0.4,0.6]` are abstentions; lower scores are charge-bias-like and higher scores are overlap-like.

## 4. Candidate Support
|   run | stave   |   delayed_candidates |   selected_pulses |
|------:|:--------|---------------------:|------------------:|
|    37 | B2      |                   19 |             22956 |
|    37 | B4      |                    2 |               997 |
|    37 | B6      |                    0 |               423 |
|    37 | B8      |                    0 |               161 |
|    40 | B2      |                   10 |             13575 |
|    40 | B4      |                    0 |               707 |
|    40 | B6      |                    0 |               310 |
|    40 | B8      |                    0 |               116 |
|    42 | B2      |                    9 |             16977 |
|    42 | B4      |                    0 |               711 |
|    42 | B6      |                    0 |               307 |
|    42 | B8      |                    0 |               117 |
|    49 | B2      |                   10 |             13779 |
|    49 | B4      |                    2 |               640 |
|    49 | B6      |                    0 |               281 |
|    49 | B8      |                    0 |               115 |
|    52 | B2      |                    0 |              6893 |
|    52 | B4      |                    0 |               148 |
|    52 | B6      |                    0 |                76 |
|    52 | B8      |                    0 |                35 |
|    57 | B2      |                    3 |             12774 |
|    57 | B4      |                    0 |               656 |
|    57 | B6      |                    0 |               273 |
|    57 | B8      |                    0 |               130 |
|    58 | B2      |                    0 |             15791 |
|    58 | B4      |                    0 |               591 |
|    58 | B6      |                    0 |               285 |
|    58 | B8      |                    0 |               114 |
|    60 | B2      |                    4 |              9873 |
|    60 | B4      |                    0 |              4040 |
|    60 | B6      |                    0 |              2189 |
|    60 | B8      |                    0 |               927 |
|    62 | B2      |                    3 |             11635 |
|    62 | B4      |                    1 |              4183 |
|    62 | B6      |                    0 |              2342 |
|    62 | B8      |                    0 |               929 |
|    64 | B2      |                    4 |             11907 |
|    64 | B4      |                    0 |              1689 |
|    64 | B6      |                    0 |               763 |
|    64 | B8      |                    0 |               271 |
|    65 | B2      |                    2 |             11768 |
|    65 | B4      |                    0 |               842 |
|    65 | B6      |                    0 |               323 |
|    65 | B8      |                    0 |               105 |

## 5. Split and Fold Audit
|   test_run |   n_train_delayed |   n_train_binary_sampled |   n_train_overlap |   n_train_charge_bias |   n_test_delayed |   n_test_overlap |   n_test_charge_bias |   n_test_ambiguous | test_run_in_train   | cnn_1d_device   | charge_gated_cnn_new_device   |   cnn_1d_final_loss |   charge_gated_cnn_new_final_loss |
|-----------:|------------------:|-------------------------:|------------------:|----------------------:|-----------------:|-----------------:|---------------------:|-------------------:|:--------------------|:----------------|:------------------------------|--------------------:|----------------------------------:|
|         37 |               137 |                       64 |                16 |                    48 |               21 |                2 |                    7 |                 12 | False               | cpu             | cpu                           |            0.919958 |                          0.882736 |
|         40 |               148 |                       72 |                18 |                    54 |               10 |                1 |                    2 |                  7 | False               | cpu             | cpu                           |            0.899738 |                          0.895046 |
|         42 |               149 |                       72 |                18 |                    54 |                9 |                2 |                    2 |                  5 | False               | cpu             | cpu                           |            0.875396 |                          0.947732 |
|         49 |               146 |                       75 |                20 |                    55 |               12 |                1 |                    7 |                  4 | False               | cpu             | cpu                           |            0.824507 |                          0.903118 |
|         57 |               155 |                       78 |                20 |                    58 |                3 |                0 |                    0 |                  3 | False               | cpu             | cpu                           |            0.890524 |                          0.870659 |
|         60 |               154 |                       76 |                19 |                    57 |                4 |                0 |                    2 |                  2 | False               | cpu             | cpu                           |            0.922668 |                          0.877497 |
|         62 |               154 |                       76 |                19 |                    57 |                4 |                0 |                    2 |                  2 | False               | cpu             | cpu                           |            0.873485 |                          0.93066  |
|         64 |               154 |                       72 |                18 |                    54 |                4 |                0 |                    3 |                  1 | False               | cpu             | cpu                           |            0.88834  |                          0.903922 |
|         65 |               156 |                       76 |                19 |                    57 |                2 |                0 |                    2 |                  0 | False               | cpu             | cpu                           |            0.87624  |                          0.900954 |

## 6. Head-to-head Benchmark
| method                  |   n_eval |   n_overlap_true |   n_charge_bias_true |   n_ambiguous_true |   average_precision | average_precision_ci95   |   balanced_accuracy | balanced_accuracy_ci95   |   secondary_fraction_delta | secondary_fraction_delta_ci95   |   charge_bias_delta | charge_bias_delta_ci95   |   abstention_precision | abstention_precision_ci95   |   abstention_recall | abstention_recall_ci95   |   decision_utility | decision_utility_ci95   |
|:------------------------|---------:|-----------------:|---------------------:|-------------------:|--------------------:|:-------------------------|--------------------:|:-------------------------|---------------------------:|:--------------------------------|--------------------:|:-------------------------|-----------------------:|:----------------------------|--------------------:|:-------------------------|-------------------:|:------------------------|
| traditional_frozen_cuts |       69 |                6 |                   27 |                 36 |            0.97619  | [0.917, 1]               |            1        | [1, 1]                   |                  0.156171  | [0.125, 0.201]                  |            0.305906 | [0.113, 0.481]           |               0.823529 | [0.461, 1]                  |            0.388889 | [0.16, 0.562]            |           0.877448 | [0.813, 0.915]          |
| ridge                   |       69 |                6 |                   27 |                 36 |            0.596825 | [0.333, 1]               |            0.925    | [0.781, 1]               |                  0.0676734 | [0.0122, 0.113]                 |            0.400916 | [0.251, 0.662]           |               0.652174 | [0.4, 1]                    |            0.416667 | [0.333, 0.537]           |           0.702949 | [0.492, 0.892]          |
| gradient_boosted_trees  |       69 |                6 |                   27 |                 36 |            0.948413 | [0.833, 1]               |            0.980769 | [0.948, 1]               |                  0.0255491 | [-0.0323, 0.0918]               |            0.280037 | [0.173, 0.439]           |               0.8      | [0, 1]                      |            0.111111 | [0, 0.216]               |           0.727816 | [0.683, 0.777]          |
| mlp                     |       69 |                6 |                   27 |                 36 |            0.408628 | [0.209, 0.75]            |            0.475    | [0.393, 0.5]             |                 -0.194488  | [-0.23, -0.159]                 |           -0.520469 | [-0.593, -0.406]         |               0.538462 | [0.37, 0.719]               |            0.388889 | [0.229, 0.667]           |           0.352092 | [0.169, 0.476]          |
| cnn_1d                  |       69 |                6 |                   27 |                 36 |            0.736111 | [0.643, 1]               |          nan        |                          |                  0.290154  | [0.229, 0.352]                  |            0.431035 | [0.0257, 0.71]           |               0.57377  | [0.427, 0.7]                |            0.972222 | [0.895, 1]               |           0.595663 | [0.411, 0.683]          |
| charge_gated_cnn_new    |       69 |                6 |                   27 |                 36 |            0.594949 | [0.278, 0.911]           |            0.875    | [0.75, 1]                |                 -0.274024  | [-0.313, -0.19]                 |           -0.102007 | [-0.399, 0.514]          |               0.564516 | [0.439, 0.643]              |            0.972222 | [0.893, 1]               |           0.569839 | [0.258, 0.681]          |

The two physics deltas are defined on each method's hard decisions as

\[ \Delta_s = E[s_i \mid \hat y_i=\mathrm{overlap}]-E[s_i \mid \hat y_i=\mathrm{charge\ bias}], \]

\[ \Delta_b = E[|b_i| \mid \hat y_i=\mathrm{charge\ bias}]-E[|b_i| \mid \hat y_i=\mathrm{overlap}]. \]

Positive values are therefore in the expected direction: overlap decisions carry more recovered secondary structure, while charge-bias decisions carry larger charge disagreement with the duplicate channel.

## 7. Leakage and Falsification
| check                                   |   value | pass   | note                                                                                               |
|:----------------------------------------|--------:|:-------|:---------------------------------------------------------------------------------------------------|
| raw_reproduction_before_modeling        |  640737 | True   | script raises before model fitting if selected-pulse count mismatches                              |
| leave_one_run_train_test_overlap        |       0 | True   | held-out run never appears in the train sample                                                     |
| identifier_columns_absent_from_features |       0 | True   | run/event/stave identifiers are not in SCALAR_FEATURES and waveform columns are positional samples |
| all_methods_same_eval_rows              |       1 | True   | head-to-head methods score the same delayed candidates                                             |
| finite_scores                           |       1 | True   | non-finite classifier scores invalidate ranking metrics                                            |

The falsification criterion was fixed before fitting: the claimed winner must have positive bootstrap-median `secondary_fraction_delta`, positive bootstrap-median `charge_bias_delta`, and nonzero abstention recall. A model with high AP but negative physics deltas would be rejected as a ranker that does not disentangle the requested mechanisms. Six methods were tried, so the report treats the winner as a benchmark result rather than a discovery p-value.

## 8. Systematics and Caveats
- The labels are operational proxy labels, not external truth. They test consistency among delayed morphology, duplicate-channel charge, dropout depth, and baseline behavior.
- Charge bias uses the duplicate channel as a reference. A correlated failure of even and duplicate channels would not be visible.
- The delayed-candidate cut rejects saturated two-sample plateaus and strong secondaries above the P09d ceiling, so it is conservative for genuine pile-up.
- Bootstrap intervals resample held-out runs and therefore cover run composition; they do not include alternative threshold quantiles except through the documented caveat.
- Because the endpoint is partly constructed from scalar diagnostics, high tabular performance should be read as a validated decision boundary, not as proof of a new latent physics class.

## 9. Verdict
The winner by preregistered `decision_utility` is **traditional_frozen_cuts** with utility 0.877 (95% run-bootstrap CI [0.813, 0.915]). Its secondary-fraction delta is 0.156 (CI [0.125, 0.201]) and charge-bias delta is 0.306 (CI [0.113, 0.481]). Abstention precision/recall are 0.824/0.389 (CIs [0.461, 1]/[0.16, 0.562]).

This supports treating delayed peaks as a mixed operational class: some carry separable overlap-like secondary structure, while a distinct subset is better handled as charge-bias/dropout risk or abstained. The recommended downstream action is to use the winning boundary as a triage layer before applying P09d-style recovery.

## 10. Reproducibility
Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python scripts/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.py --config configs/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.json
```

Runtime was 257.0 s on `billy` with Python `3.7.6`. `manifest.json` records commands, inputs, seeds, and output hashes.

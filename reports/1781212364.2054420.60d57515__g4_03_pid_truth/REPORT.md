# G4-03 Proton/deuteron PID: GEANT4 truth vs dE-E and waveform/ML PID

- **Ticket:** `1781212364.2054420.60d57515`
- **Worker:** `testbeam-laptop-3`
- **Winner:** `gradient_boosted_trees`
- **GEANT4 ROOT:** `/home/billy/ccb-geant4/output_krakow_1M.root`
- **Experimental raw ROOT:** `data/root/root`

## Abstract

The benchmark reproduces the raw selected-pulse anchor and the GEANT4 proton/deuteron truth inventory, then compares a transparent dE/dx range-band classifier with ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and a new hybrid CNN-tabular architecture. The winner is **gradient_boosted_trees**, balanced accuracy 0.9955 [0.9936, 0.9970], versus the traditional method at 0.9794 [0.9770, 0.9813].

## Raw ROOT Reproduction

The HRD B-stack scan subtracts the median of samples 0-3 from each waveform and selects a pulse when the corrected maximum exceeds 1000 ADC. It reproduces **640,737** selected B-stave pulses versus expected **640,737** (delta +0) over 33 runs and 1,096,728 events.

|   run |   events |   selected_pulses |    B2 |   B4 |   B6 |   B8 |
|------:|---------:|------------------:|------:|-----:|-----:|-----:|
|    31 |    39990 |             27871 | 26948 |  592 |  237 |   94 |
|    32 |    41921 |             28240 | 27316 |  605 |  224 |   95 |
|    33 |    57173 |             48737 | 47724 |  559 |  318 |  136 |
|    34 |    39765 |             34118 | 33373 |  412 |  244 |   89 |
|    35 |    27786 |             11667 | 11029 |  403 |  163 |   72 |
|    36 |    21764 |             10391 |  9847 |  340 |  143 |   61 |
|    37 |    50513 |             24537 | 22956 |  997 |  423 |  161 |
|    39 |    30321 |             14218 | 13174 |  663 |  273 |  108 |
|    40 |    32613 |             14708 | 13575 |  707 |  310 |  116 |
|    41 |    33997 |             16146 | 14963 |  758 |  298 |  127 |
|    42 |    33972 |             18112 | 16977 |  711 |  307 |  117 |
|    44 |     4294 |              2038 |  1884 |   93 |   44 |   17 |

## GEANT4 Truth Reproduction

The checked simulation summary reproduces **836,534** truth protons and **314,646** truth deuterons in 1,000,000 simulated events. Deltas to the ticket claim are proton +0 and deuteron +0.

|   layer |   hits |   hits_gt10MeV |   mean_edep_MeV |   p_frac |   d_frac |
|--------:|-------:|---------------:|----------------:|---------:|---------:|
|       0 | 371089 |         311247 |         23.3447 |   0.4954 |   0.3925 |
|       1 | 288230 |         245197 |         20.9074 |   0.5485 |   0.3633 |
|       2 | 175489 |         148042 |         20.535  |   0.6921 |   0.2014 |
|       3 | 143580 |         122023 |         17.7176 |   0.7274 |   0.1897 |
|       4 | 100797 |          86361 |         16.9448 |   0.8952 |   0.008  |
|       5 |  95953 |          81368 |         23.225  |   0.8851 |   0.0053 |
|       6 |  69737 |          58409 |         22.5939 |   0.9019 |   0.0036 |
|       7 |  34565 |          28013 |         19.9052 |   0.8865 |   0.0042 |

## Label Definition and Split

For benchmark labels, Sci_bar hits with `LayerID1 == 2` define the B-stack. For each event, deposited energy is summed by true PDG and depth layer; the event label is the dominant proton or deuteron when that species contributes at least 60 percent of B-stack deposited energy. The run split is leave-one-contiguous-simulation-block-held-out because the GEANT4 tree has no acquisition-run branch. Confidence intervals are nonparametric bootstraps over held-out blocks.

| truth_class   |   truth_pdg |   available_events |   used_events |
|:--------------|------------:|-------------------:|--------------:|
| deuteron      |  1000010020 |               5379 |          5000 |
| proton        |        2212 |              63852 |          5000 |

## Methods

Traditional comparator: robust dE/dx/range bands using train-fold medians, IQR scales, and class priors over charge-depth, active-layer, centroid, spread, timing, path-length, dE/dx, and position features. Learned comparators: L2 ridge logistic regression, histogram gradient-boosted trees, a two-hidden-layer MLP, a 1D CNN over ordered layer sequences, and `hybrid_cnn_tabular`, which concatenates a CNN embedding with global physics features.

## Equations and Metrics

Let `E_ik` be the B-stack deposited energy in depth layer `k` for event `i`, and let `E_i = sum_k E_ik`. The sequence input is `[log(1 + E_ik), E_ik / E_i, T_ik / 100]`; the main range observables are the centroid `mu_i = sum_k k E_ik / E_i` and spread `sigma_i^2 = sum_k (k - mu_i)^2 E_ik / E_i`. The traditional band classifier chooses the class with the smallest robust diagonal distance

`D_c(x_i) = sum_j ((x_ij - m_cj) / s_cj)^2 - 2 log pi_c`,

where `m_cj`, `s_cj`, and `pi_c` are train-fold class medians, IQR-derived scales, and priors. Ridge logistic regression minimizes penalized cross entropy,

`L(beta) = -sum_i log p_beta(y_i | x_i) + lambda ||beta||_2^2`.

The primary reporting metric is balanced accuracy,

`BA = 0.5 * (TP / (TP + FN) + TN / (TN + FP))`,

with deuteron purity `TP / (TP + FP)` and deuteron efficiency `TP / (TP + FN)`. Bootstrap CIs are the 2.5 and 97.5 percentiles of the metric after resampling held-out simulation blocks with replacement.

## Results

| method                 |   balanced_accuracy |   balanced_accuracy_ci_low |   balanced_accuracy_ci_high |   macro_f1 |   macro_f1_ci_low |   macro_f1_ci_high |
|:-----------------------|--------------------:|---------------------------:|----------------------------:|-----------:|------------------:|-------------------:|
| gradient_boosted_trees |              0.9955 |                     0.9936 |                      0.997  |     0.9955 |            0.9936 |             0.997  |
| hybrid_cnn_tabular     |              0.9952 |                     0.9939 |                      0.9964 |     0.9952 |            0.994  |             0.9964 |
| ridge                  |              0.9947 |                     0.9925 |                      0.9962 |     0.9947 |            0.9925 |             0.9962 |
| mlp                    |              0.9945 |                     0.9922 |                      0.9962 |     0.9945 |            0.9922 |             0.9962 |
| traditional_bands      |              0.9794 |                     0.977  |                      0.9813 |     0.9794 |            0.977  |             0.9811 |
| cnn1d                  |              0.8572 |                     0.8543 |                      0.86   |     0.8544 |            0.8508 |             0.8569 |

Hard-label ROC operating points, with deuteron as positive class:

| method                 |    fpr |    tpr |   balanced_accuracy |
|:-----------------------|-------:|-------:|--------------------:|
| gradient_boosted_trees | 0.0032 | 0.9942 |              0.9955 |
| hybrid_cnn_tabular     | 0.0026 | 0.993  |              0.9952 |
| ridge                  | 0.0026 | 0.992  |              0.9947 |
| mlp                    | 0.0022 | 0.9912 |              0.9945 |
| traditional_bands      | 0      | 0.9588 |              0.9794 |
| cnn1d                  | 0.2814 | 0.9958 |              0.8572 |

Winner purity and efficiency:

| species   |   truth_n |   pred_n |   purity |   purity_ci_low |   purity_ci_high |   efficiency |   efficiency_ci_low |   efficiency_ci_high |
|:----------|----------:|---------:|---------:|----------------:|-----------------:|-------------:|--------------------:|---------------------:|
| proton    |      5000 |     5013 |   0.9942 |          0.9904 |           0.9972 |       0.9968 |              0.9959 |               0.998  |
| deuteron  |      5000 |     4987 |   0.9968 |          0.9955 |           0.998  |       0.9942 |              0.9903 |               0.9972 |

Winner fold stability:

|   sim_run |    n |   balanced_accuracy |
|----------:|-----:|--------------------:|
|         0 | 2530 |              0.9972 |
|         1 | 2504 |              0.9968 |
|         2 | 2433 |              0.9947 |
|         3 | 2533 |              0.9933 |

## Data-Control Agreement and Transfer Caveat

The real raw ROOT control region validates selected B-stack waveform support, not event-level PID truth. Real HRD files have waveform and event-counter branches but no PDG, external PID, or time-of-flight PID label. Therefore the data-side conclusion is limited to support consistency and selected-pulse reproduction; no real-data efficiency or purity is claimed.

## Leakage Checks

For binary p/d, chance balanced accuracy is 0.5, so a 0.55 threshold is used for identifier-only and shuffled-label sentinels.

| check                                           |   value |   threshold | pass   |
|:------------------------------------------------|--------:|------------:|:-------|
| identifier_only_group_heldout_balanced_accuracy |  0.4903 |        0.55 | True   |
| shuffled_label_ridge_balanced_accuracy          |  0.4945 |        0.55 | True   |

## Systematics and Caveats

- GEANT4 truth labels are simulation truth, not real-data labels.
- Dominant-deposit labeling excludes ambiguous mixed events.
- Simulation blocks are run analogues, not acquisition runs.
- GEANT4 deposits are not digitized ADC waveforms and omit response, quenching, saturation, trigger, and reconstruction effects.
- Deuteron range-out and charge-sharing tails can move events across the p/d boundary, so the reported deuteron purity is conditional on the simulated B-stack stopping/range model.
- The domain gap between GEANT4 deposited-energy truth and real HRD ADC waveforms remains the dominant limitation for applying this PID model directly to data.
- `LayerID1 == 2` is treated as B-stack geometry support.
- ROC artifacts are hard-label operating points because the reusable benchmark records class labels rather than calibrated probabilities.

## Conclusion

G4-03 supports a simulation-truth proton/deuteron PID bridge: `gradient_boosted_trees` wins the held-out block benchmark, while the traditional dE/dx/range method remains strong and interpretable. PID for real events should remain data-driven until an external PID label or validated digitized simulation-to-data response bridge is available.

## Artifacts

`REPORT.md`, `result.json`, `raw_reproduction_by_run.csv`, `class_counts.csv`, `method_metrics.csv`, `per_species_metrics.csv`, `fold_metrics.csv`, `confusion_matrix_winner.csv`, `leakage_checks.csv`, `roc_operating_points.csv`, `pid_model_card.json`, `pid_model.json`, and figures under `figures/`. This report is mirrored at `docs/reports/G4_03_pid_truth.md`.

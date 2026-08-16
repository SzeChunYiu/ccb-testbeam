# S15 ticket #2385: event-by-event deltaE-E particle ID bakeoff

- **Ticket:** `#2385`
- **Worker:** `testbeam-laptop-1`
- **Raw ROOT input:** `/home/billy/ccb-data/data/extracted/root/root`
- **MC p/d event table:** `reports/paper_618_species_penetration_2m_20260814T1449Z/deltaE_E_events_mc.parquet`
- **Beam-data diagnostic table:** `reports/paper_618_species_penetration_20260814T1615Z/deltaE_E_events_data.parquet`

## Executive result

The winner is **gradient_boosted_trees** on run-held-out GEANT4 p/d labels, with balanced accuracy 0.9374 [0.9348, 0.9401] and macro-F1 0.9199 [0.9157, 0.9241].

This is a supervised MC-truth benchmark for S15 method comparison, not a claim that the real beam-data events have externally validated p/d labels. The data table is used to document the real amplitude-support domain and the raw ROOT gate verifies that the HRD input stream is the expected one.

## Raw-ROOT reproduction gate

The script rescanned the HRD B-stack ROOT files and reproduced the S00 selected-pulse count: 640,737 selected B-stave pulse records versus 640,737 expected (delta 0). The selector is median baseline over samples 0-3, B-stave channels B2/B4/B6/B8 = 0/2/4/6, and `max(waveform - median_baseline) > 1000 ADC`.

## Problem definition

For event \(i\), the class label is \(y_i \in \{p,d\}\) from the MC truth species. The data vector is the four B-stack readout energy deposits \(\mathbf{x}_i=(B2_i,B4_i,B6_i,B8_i)\). We define \(E_i=\sum_j x_{ij}\), fractions \(f_{ij}=x_{ij}/\max(E_i,\epsilon)\), upstream loss \(\Delta E_i=x_{i,B2}\), downstream residual \(E_i^{\mathrm{down}}=x_{i,B4}+x_{i,B6}+x_{i,B8}\), and a penetration index \(L_i=\max\{\ell:E_{i\ell}>0.02\,\mathrm{MeV}\}\) with sentinel 8 if no layer crosses threshold.

## Methods

The traditional method is a train-fold-only robust dE-E band classifier. For each class \(c\), medians \(m_c\), IQR scales \(s_c\), and priors \(\pi_c\) are estimated in the handcrafted variables \((\log E, \log \Delta E, \log E^{\mathrm{down}}, E^{\mathrm{down}}/\Delta E, \mu_{B}, \sigma_{B}, L)\). Prediction minimizes the diagonal robust distance \(D_c(x)=\frac12\sum_k ((x_k-m_{ck})/s_{ck})^2-\log\pi_c\).

The ML/NN panel is ridge classification, histogram gradient-boosted trees with class-balanced weights, a two-layer MLP, a 1D-CNN over the four B-stack sequence positions with channels \([\log(1+x_j), f_j, 1_{x_j>0}]\), and a new `hybrid_cnn_tabular` architecture that concatenates the CNN embedding with standardized global dE-E/penetration variables.

Evaluation is leave-one-block-held-out. If the MC table exposes multiple `run_id` values these are used directly; this artifact has degenerate `run_id=0`, so deterministic contiguous `eval_run` blocks are used instead. Confidence intervals are nonparametric bootstrap intervals that resample held-out blocks with replacement, preserving event membership within each block.

## Class balance and beam-data support

| truth_species | available_events | used_events |
| ------------- | ---------------- | ----------- |
| d             | 2660             | 2660        |
| p             | 11415            | 5000        |

| data_events | sample_i_events | sample_ii_events | b2_saturation_fraction | multi_stave_fraction |
| ----------- | --------------- | ---------------- | ---------------------- | -------------------- |
| 216448      | 147274          | 69174            | 0.0000                 | 0.1331               |

## Method scoreboard

| method                 | balanced_accuracy | balanced_accuracy_ci_low | balanced_accuracy_ci_high | macro_f1 | macro_f1_ci_low | macro_f1_ci_high |
| ---------------------- | ----------------- | ------------------------ | ------------------------- | -------- | --------------- | ---------------- |
| gradient_boosted_trees | 0.9374            | 0.9348                   | 0.9401                    | 0.9199   | 0.9157          | 0.9241           |
| hybrid_cnn_tabular     | 0.9284            | 0.9264                   | 0.9302                    | 0.9135   | 0.9097          | 0.9181           |
| mlp                    | 0.9260            | 0.9229                   | 0.9294                    | 0.9167   | 0.9124          | 0.9208           |
| ridge                  | 0.9102            | 0.9051                   | 0.9149                    | 0.8848   | 0.8790          | 0.8903           |
| cnn1d                  | 0.8977            | 0.8915                   | 0.9039                    | 0.8726   | 0.8648          | 0.8795           |
| traditional_bands      | 0.8028            | 0.7536                   | 0.8308                    | 0.8020   | 0.7655          | 0.8217           |

## Winner purity and efficiency

| species | truth_n | pred_n | purity | purity_ci_low | purity_ci_high | efficiency | efficiency_ci_low | efficiency_ci_high |
| ------- | ------- | ------ | ------ | ------------- | -------------- | ---------- | ----------------- | ------------------ |
| p       | 5000    | 4535   | 0.9877 | 0.9837        | 0.9913         | 0.8958     | 0.8869            | 0.9048             |
| d       | 2660    | 3125   | 0.8333 | 0.8223        | 0.8445         | 0.9789     | 0.9725            | 0.9853             |

## Fold stability

| eval_run | n    | balanced_accuracy |
| -------- | ---- | ----------------- |
| 0        | 1532 | 0.9337            |
| 1        | 1532 | 0.9378            |
| 2        | 1532 | 0.9405            |
| 3        | 1532 | 0.9416            |
| 4        | 1532 | 0.9332            |

## Controls

| check                                         | value  | threshold | pass |
| --------------------------------------------- | ------ | --------- | ---- |
| identifier_only_run_heldout_balanced_accuracy | 0.4889 | 0.6500    | True |
| shuffled_label_ridge_balanced_accuracy        | 0.5077 | 0.6000    | True |

Identifier-only and shuffled-label controls are falsifiers for trivial run/event leakage and label-vector mistakes. They do not exclude all simulation artifacts.

## Systematics and caveats

- The supervised labels come from MC truth, not the real HRD beam data. Without S17-grade externally validated truth transfer, purity and efficiency are method-comparison quantities only.
- The MC event table uses deposited-energy/readout proxies. It does not include the full electronics response, noise, saturation transfer, trigger efficiency, or waveform-level pedestal model of the HRD data.
- The raw ROOT reproduction gate validates the selected-pulse input count and channel/baseline semantics, but it does not by itself validate p/d truth labels.
- The MC table has degenerate `run_id=0`; the benchmark therefore uses deterministic contiguous event-index blocks labelled `eval_run` as run-like held-out source blocks. This satisfies leakage-resistant blocked evaluation for the available artifact, but it is weaker than a true multi-acquisition-run split.
- Bootstrap intervals resample `eval_run` blocks, so they measure fold stability under the available generated source segmentation. They do not include material-budget, physics-list, Birks/quenching, calibration, or source-composition uncertainty.
- The traditional bands are interpretable and train-fold frozen. Any global dE-E band drawn from all data would be an optimistic baseline and is intentionally avoided here.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_by_run.csv`, `class_counts.csv`, `data_support_summary.csv`, `method_metrics.csv`, `per_species_metrics.csv`, `fold_metrics.csv`, `confusion_matrix_winner.csv`, `leakage_checks.csv`, and this `REPORT.md` are in the report directory. Root-level `REPORT.md` and `result.json` mirror the report and summary for the ticket runner.

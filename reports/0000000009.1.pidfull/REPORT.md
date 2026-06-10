# Study report: PID-full GEANT4-truth B-stave particle ID

- **Ticket:** `0000000009.1.pidfull`
- **Worker:** `testbeam-laptop-4`
- **Raw reproduction input:** `data/root/root`
- **GEANT4 truth input:** `/home/billy/ccb-geant4/output_krakow_1M.root`

## Executive result

The winner is **gradient_boosted_trees** with run-block held-out balanced accuracy 0.9092 [0.8865, 0.9328] and macro-F1 0.8798 [0.8470, 0.9175].

The labels are not inferred from test-beam data. They are GEANT4 hit-truth labels: for every simulated event, Sci_bar hits with `LayerID1 == 2` are treated as the B-stack, hit energy deposits are summed by true PDG, and an event is retained when one target PDG contributes at least 60% of the B-stack deposited energy. The target classes are proton (`2212`), deuteron (`1000010020`), alpha (`1000020040`), and carbon-12 (`1000060120`).

## Raw-ROOT reproduction gate

Before truth modeling, the script rescanned HRD B-stack raw ROOT and reproduced the shared S00 selected-pulse count: 640,737 selected pulses versus expected 640,737 (delta 0). The selector is median baseline samples 0-3, physical B channels B2/B4/B6/B8 = 0/2/4/6, and `max(waveform-baseline) > 1000 ADC`.

## Methods

For event \(i\), let \(E_{ik}\) be the GEANT4 B-stack energy deposit in scintillator layer \(k\in\{0,\dots,7\}\), \(T_{ik}\) its energy-weighted time, and \(E_i=\sum_k E_{ik}\). The common sequence input is \([\log(1+E_{ik}), E_{ik}/E_i, T_{ik}/100]\). Tabular features add \(\log(1+E_i)\), first-layer charge, tail charge, tail/first ratio, layer centroid \(\mu_i=\sum_k kE_{ik}/E_i\), spread \(\sigma_i^2=\sum_k (k-\mu_i)^2E_{ik}/E_i\), active-layer count, time moments, path-length sums, dE/dx proxy, and energy-weighted positions.

The traditional method is a charge-comparison PSD / dE/dx band classifier: each species is represented by robust train-fold medians and IQR-derived diagonal scales in the handcrafted charge-shape variables, and the predicted species minimizes the robust squared band distance with train-fold class priors. Ridge is L2 multinomial logistic regression. Gradient-boosted trees use histogram gradient boosting with class-balanced sample weights. MLP is a scaled two-hidden-layer neural net. The 1D-CNN learns local layer-pattern filters over the sequence input. The new architecture, `hybrid_cnn_tabular`, concatenates the CNN embedding with standardized global tabular features before classification.

Evaluation is leave-one-simulation-block-held-out. The GEANT4 file has no acquisition run field, so deterministic contiguous event-index blocks are used as run-like groups; all intervals are nonparametric bootstrap intervals over these held-out groups.

## Class balance

| truth_class | truth_pdg  | available_events | used_events |
| ----------- | ---------- | ---------------- | ----------- |
| alpha       | 1000020040 | 80               | 80          |
| carbon12    | 1000060120 | 28               | 28          |
| deuteron    | 1000010020 | 5379             | 1500        |
| proton      | 2212       | 63852            | 1500        |

## Method scoreboard

| method                 | balanced_accuracy | balanced_accuracy_ci_low | balanced_accuracy_ci_high | macro_f1 | macro_f1_ci_low | macro_f1_ci_high |
| ---------------------- | ----------------- | ------------------------ | ------------------------- | -------- | --------------- | ---------------- |
| gradient_boosted_trees | 0.9092            | 0.8865                   | 0.9328                    | 0.8798   | 0.8470          | 0.9175           |
| ridge                  | 0.9085            | 0.8922                   | 0.9263                    | 0.7820   | 0.7648          | 0.8124           |
| hybrid_cnn_tabular     | 0.8512            | 0.8439                   | 0.8602                    | 0.7065   | 0.6925          | 0.7200           |
| traditional_bands      | 0.8061            | 0.7730                   | 0.8294                    | 0.6810   | 0.6658          | 0.6939           |
| mlp                    | 0.7259            | 0.6914                   | 0.7671                    | 0.7449   | 0.7126          | 0.7771           |
| cnn1d                  | 0.3015            | 0.2534                   | 0.4006                    | 0.2678   | 0.1872          | 0.3669           |

## Purity and efficiency

| species  | truth_n | pred_n | purity | purity_ci_low | purity_ci_high | efficiency | efficiency_ci_low | efficiency_ci_high |
| -------- | ------- | ------ | ------ | ------------- | -------------- | ---------- | ----------------- | ------------------ |
| proton   | 1500    | 1487   | 0.9818 | 0.9773        | 0.9868         | 0.9733     | 0.9695            | 0.9786             |
| deuteron | 1500    | 1487   | 0.9953 | 0.9919        | 0.9993         | 0.9867     | 0.9761            | 0.9945             |
| alpha    | 80      | 104    | 0.5481 | 0.4336        | 0.6667         | 0.7125     | 0.6579            | 0.7763             |
| carbon12 | 28      | 30     | 0.9000 | 0.8333        | 1.0000         | 0.9643     | 0.8889            | 1.0000             |

## Fold stability

| sim_run | n   | balanced_accuracy |
| ------- | --- | ----------------- |
| 0       | 755 | 0.9444            |
| 1       | 799 | 0.9221            |
| 2       | 773 | 0.8999            |
| 3       | 781 | 0.8710            |

## Leakage controls

| check                                           | value  | threshold | pass |
| ----------------------------------------------- | ------ | --------- | ---- |
| identifier_only_group_heldout_balanced_accuracy | 0.2304 | 0.4500    | True |
| shuffled_label_ridge_balanced_accuracy          | 0.2316 | 0.4000    | True |

Identifier-only and shuffled-label controls are intentionally weak baselines. They do not prove absence of every simulation artifact, but they check that the reported accuracy is not a trivial event-index or block-label leak and that the pipeline is not scoring against a misaligned label vector.

## Systematics and caveats

- The study is a GEANT4 truth benchmark, not a claim that real test-beam events can be labeled without external truth.
- `LayerID1 == 2` is used as the simulated B-stack index. A geometry-label mismatch would alter absolute performance; the raw HRD reproduction gate checks only detector-data parsing, not simulation geometry naming.
- The event label is dominant deposited energy in the B-stack, so mixed showers and secondaries below the 60% dominance threshold are excluded rather than forced into a species.
- GEANT4 deposits are amplitude proxies, not digitized waveforms. The sequence input captures longitudinal charge/time shape but not electronics response, thresholding, saturation, or noise in the real HRD waveforms.
- Bootstrap intervals resample the deterministic simulation blocks. They measure block-to-block stability, not full uncertainty from beamline modeling, material budget, or physics-list variations.
- Traditional dE/dx bands remain interpretable and competitive, but the winner should be re-tested after a digitization layer or external calibration labels are available.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_by_run.csv`, `class_counts.csv`, `method_metrics.csv`, `per_species_metrics.csv`, `fold_metrics.csv`, `confusion_matrix_winner.csv`, `leakage_checks.csv`, and this `REPORT.md` are in the report directory.

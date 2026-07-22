# Study report: PID-full GEANT4-truth B-stave particle ID

- **Ticket:** `1783744185.18861.10947fe9`
- **Worker:** `testbeam-laptop-2`
- **Raw reproduction input:** `data/root/root`
- **GEANT4 truth input:** `/home/billy/ccb-geant4/output_krakow_1M.root`

## Executive result

The winner is **gradient_boosted_trees** with run-block held-out balanced accuracy 0.9240 [0.8983, 0.9388] and macro-F1 0.9034 [0.8753, 0.9243].

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
| gradient_boosted_trees | 0.9240            | 0.8983                   | 0.9388                    | 0.9034   | 0.8753          | 0.9243           |
| ridge                  | 0.8955            | 0.8581                   | 0.9343                    | 0.7791   | 0.7575          | 0.8057           |
| hybrid_cnn_tabular     | 0.8638            | 0.8366                   | 0.8885                    | 0.7450   | 0.7267          | 0.7713           |
| traditional_bands      | 0.8059            | 0.7702                   | 0.8430                    | 0.6840   | 0.6591          | 0.7075           |
| mlp                    | 0.7966            | 0.7407                   | 0.8349                    | 0.8234   | 0.7637          | 0.8649           |
| cnn1d                  | 0.5851            | 0.5430                   | 0.6477                    | 0.5717   | 0.5262          | 0.6071           |

## Purity and efficiency

| species  | truth_n | pred_n | purity | purity_ci_low | purity_ci_high | efficiency | efficiency_ci_low | efficiency_ci_high |
| -------- | ------- | ------ | ------ | ------------- | -------------- | ---------- | ----------------- | ------------------ |
| proton   | 1500    | 1487   | 0.9906 | 0.9849        | 0.9953         | 0.9820     | 0.9745            | 0.9876             |
| deuteron | 1500    | 1493   | 0.9900 | 0.9844        | 0.9954         | 0.9853     | 0.9798            | 0.9905             |
| alpha    | 80      | 100    | 0.6400 | 0.5827        | 0.7308         | 0.8000     | 0.7349            | 0.8901             |
| carbon12 | 28      | 28     | 0.9286 | 0.8333        | 1.0000         | 0.9286     | 0.8182            | 1.0000             |

## Fold stability

| sim_run | n   | balanced_accuracy |
| ------- | --- | ----------------- |
| 0       | 537 | 0.9307            |
| 1       | 542 | 0.9033            |
| 2       | 498 | 0.9393            |
| 3       | 500 | 0.9254            |
| 4       | 525 | 0.8609            |
| 5       | 506 | 0.9344            |

## Leakage controls

| check                                           | value  | threshold | pass |
| ----------------------------------------------- | ------ | --------- | ---- |
| identifier_only_group_heldout_balanced_accuracy | 0.2497 | 0.4500    | True |
| shuffled_label_ridge_balanced_accuracy          | 0.2161 | 0.4000    | True |

Identifier-only and shuffled-label controls are intentionally weak baselines. They do not prove absence of every simulation artifact, but they check that the reported accuracy is not a trivial event-index or block-label leak and that the pipeline is not scoring against a misaligned label vector.

## Systematics and caveats

- The study is a GEANT4 truth benchmark, not a claim that real test-beam events can be labeled without external truth.
- `LayerID1 == 2` is used as the simulated B-stack index. A geometry-label mismatch would alter absolute performance; the raw HRD reproduction gate checks only detector-data parsing, not simulation geometry naming.
- The event label is dominant deposited energy in the B-stack, so mixed showers and secondaries below the 60% dominance threshold are excluded rather than forced into a species.
- GEANT4 deposits are amplitude proxies, not digitized waveforms. The sequence input captures longitudinal charge/time shape but not electronics response, thresholding, saturation, or noise in the real HRD waveforms.
- Bootstrap intervals resample the deterministic simulation blocks. They measure block-to-block stability, not full uncertainty from beamline modeling, material budget, or physics-list variations.
- Traditional dE/dx bands remain interpretable and competitive, but the winner should be re-tested after a digitization layer or external calibration labels are available.


## Ticket-specific control ledger

This ticket asks for waveform PID under pedestal, pile-up, and energy controls. The benchmark is therefore interpreted as a two-anchor study: real HRD ROOT data provide the detector-count and run-occupancy anchor, while GEANT4 truth provides particle labels for the supervised PID task. The two anchors are deliberately not conflated. The raw count gate demonstrates that the real waveform parsing and pedestal-subtracted threshold reproduce the shared population exactly; the model scoreboard measures truth-label separability in simulated B-stack energy/time patterns.

| control | quantity | value | interval/range | verdict |
| --- | --- | ---: | ---: | --- |
| raw_root_reproduction | selected B-stave pulses | 640737.0000 |  | pass |
| pedestal_threshold_gate | amplitude threshold after median baseline | 1000.0000 |  | controlled in reproduction gate |
| pileup_occupancy_proxy | selected pulses per raw event, run mean range | 0.5682 | [0.3393, 0.8580] | bounded as raw run heterogeneity |
| run_split_stability | winner balanced accuracy fold range | 0.9157 | [0.8609, 0.9393] | weakest held-out block reported |
| traditional_baseline_margin | winner minus traditional balanced accuracy | 0.1180 |  | winner exceeds traditional baseline |
| energy_dependence_proxy | energy features included | 1.0000 |  | modeled, not separately stress-scanned |
| pulse_shape_timing_proxy | layer time features included | 1.0000 |  | modeled, no real timing claim |
| saturation_breakdown | electronics saturation model present | 0.0000 |  | caveated |


The raw run-family occupancy proxy is:

| family | runs | selected pulses | selected/event mean | selected/event min-max | mean B2 frac | mean B8 frac |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sample_i | 25 | 501011 | 0.6001 | [0.4199, 0.8580] | 0.9517 | 0.0055 |
| sample_ii | 8 | 139726 | 0.4688 | [0.3393, 0.5191] | 0.7295 | 0.0324 |


### Equations for controls

The raw pedestal-subtracted pulse amplitude for event `i`, stave channel `c`, and sample `t` is

`a_ict = HRDv_ict - median_{u in {0,1,2,3}} HRDv_icu`,

and the reproduction selector is `max_t a_ict > 1000 ADC` for B2/B4/B6/B8. The pile-up/occupancy proxy reported above is

`rho_r = N_selected,r / N_events,r`,

which measures raw selected-pulse multiplicity per acquisition event. It is not a resolved two-pulse truth label. The GEANT4 truth class is

`y_i = argmax_s sum_{hits h in B-stack, PDG_h=s} E_h`,

with the additional dominance requirement `max_s E_is / sum_s E_is >= 0.6`. The traditional-band score for class `s` is the diagonal robust distance

`D_s(x) = sum_j ((x_j - m_sj) / sigma_sj)^2 - 2 log pi_s`,

where `m_sj` and `sigma_sj` are train-fold median and IQR-derived scales and `pi_s` is the train-fold class prior; the predicted class minimizes `D_s`.

## Method deltas versus the traditional baseline

| method | balanced accuracy | 95% CI | delta vs traditional | macro-F1 | macro-F1 delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| gradient_boosted_trees | 0.9240 | [0.8983, 0.9388] | 0.1180 | 0.9034 | 0.2194 |
| ridge | 0.8955 | [0.8581, 0.9343] | 0.0896 | 0.7791 | 0.0951 |
| hybrid_cnn_tabular | 0.8638 | [0.8366, 0.8885] | 0.0579 | 0.7450 | 0.0611 |
| traditional_bands | 0.8059 | [0.7702, 0.8430] | 0.0000 | 0.6840 | 0.0000 |
| mlp | 0.7966 | [0.7407, 0.8349] | -0.0093 | 0.8234 | 0.1394 |
| cnn1d | 0.5851 | [0.5430, 0.6477] | -0.2208 | 0.5717 | -0.1123 |


## Interpretation of requested stress axes

- **Pedestal robustness:** the only real-data pedestal operation is the median of pre-pulse samples 0-3. Because the raw count reproduces exactly, the benchmark is anchored to the same pedestal convention as the rest of the project. No alternate pedestal estimator is promoted here.
- **Pile-up rejection:** raw selected-pulse multiplicity varies by run and is reported as an occupancy proxy. The GEANT4 truth sample does not contain digitized unresolved pile-up waveforms, so the PID winner should not be read as a validated pile-up rejector.
- **Energy dependence:** the supervised inputs contain total energy, first/tail charge, range/centroid/spread, and dE/dx proxies. This controls for energy-like covariates inside each train fold, but a dedicated energy-bin transfer table would require retaining per-event predictions and is a recommended follow-up rather than an asserted closure.
- **Pulse-shape timing shifts:** GEANT4 layer time moments are present in the sequence and tabular inputs. They are not equivalent to HRD same-particle timing residuals, so this report does not claim a timing-resolution improvement.
- **Saturation breakdown:** no electronics saturation or ADC clipping response is simulated in the label benchmark. Saturation remains a caveated extrapolation axis.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_by_run.csv`, `class_counts.csv`, `method_metrics.csv`, `per_species_metrics.csv`, `fold_metrics.csv`, `confusion_matrix_winner.csv`, `leakage_checks.csv`, `systematics_controls.csv`, `method_vs_traditional_delta.csv`, `raw_run_family_controls.csv`, and this `REPORT.md` are in the report directory.

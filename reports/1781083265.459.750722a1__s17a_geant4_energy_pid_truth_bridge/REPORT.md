# S17a GEANT4 Energy and PID Truth Bridge

- **Study ID:** `1781083265.459.750722a1`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-07-08
- **Git commit:** `0efd268407a6fc4e6d270390b7f455265a87cfcf`
- **Config:** `configs/s17a_1781083265_459_750722a1_g4_energy_pid_truth_bridge.json`
- **GEANT4 input:** `/home/billy/ccb-geant4/output_30k.root`
- **Experimental raw-count anchor:** `reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv`

## 1. Question and Scope

This ticket asks whether GEANT4 truth can bridge the selected-pulse support to per-event energy and proton/deuteron PID labels, and whether conventional charge-depth/range handles are competitive against ML/NN residual handles under run-like splits. The benchmark target is the truth deuteron label on primary Sci_bar-depositing tracks. The energy component is treated as a validation bridge rather than an absolute ADC-to-MeV calibration, because the simulation lacks the full electronics, quenching, trigger, and selected-pulse response chain.

## 2. Raw ROOT Reproduction Gate

The selected-pulse anchor is the S00 raw-ROOT reproduction. It reads `h101/HRDv` from `data/extracted/root/root/hrdb_run_NNNN.root`, subtracts a median pedestal from samples 0--3, uses even physical B-stave channels, and applies `A > 1000 ADC`. In this worker the experimental ROOT files themselves were not mounted under the inspected local data paths, so this S17a run imports the S00 machine-readable raw-ROOT count artifact rather than rerunning the 6.4 GB bundle. The artifact is still a raw-ROOT reproduction, and the total count is exact.

| quantity | reference_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses from experimental raw ROOT | 640737 | 640737 | 0 | 0 | True |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| sample_i_calib events with selected pulse | 239559 | 239559 | 0 | 0 | True |
| sample_i_calib selected pulses | 248745 | 248745 | 0 | 0 | True |
| sample_i_analysis events with selected pulse | 243133 | 243133 | 0 | 0 | True |
| sample_i_analysis selected pulses | 252266 | 252266 | 0 | 0 | True |
| sample_i_analysis B2 selected pulses | 241422 | 241422 | 0 | 0 | True |

## 3. GEANT4 Truth Dataset

The GEANT4 `hibeam` tree is read from `/home/billy/ccb-geant4/output_30k.root`. The analysis keeps primary proton and deuteron tracks with nonzero Sci_bar deposited energy and excludes secondary p/d fragments from labels. Because this file has no experimental run branch, contiguous event-id blocks define ten pseudo-runs; all model fitting holds out one pseudo-run at a time and all confidence intervals use block bootstrap resampling over those units.

| quantity | reference_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| hibeam tree entries | 30000 | 30000 | 0 | 0 | True |
| Sci_bar truth hits |  | 37666 |  | descriptive | True |
| primary p/d tracks with Sci_bar deposit |  | 8957 |  | descriptive | True |

For a track with per-layer deposited energies \(E_l\), the ordered truth vector is \(x=(\log(1+E_0),\ldots,\log(1+E_7))\). Engineered features include \(E_\mathrm{tot}\), early energy \(E_0+E_1\), downstream energy \(\sum_{l=2}^7E_l\), early fraction \((E_0+E_1)/E_\mathrm{tot}\), deepest hit layer \(L_\max\), layer multiplicity, centroid \(\sum_l lE_l/E_\mathrm{tot}\), and B2/B4/B6/B8 mapped sums.

## 4. Methods

The strong traditional method is a fold-local DeltaE/range score,

```text
s = f_early - 0.060 L_max - 0.035 log(1 + E_downstream) + 0.020 log(1 + E_early),
```

with threshold chosen on the training pseudo-runs by maximizing deuteron F1. This is the transparent range-telescope comparator: deuterons should stop earlier and deposit a larger early fraction.

The ML/NN comparators are ridge/logistic L2 classification, histogram gradient-boosted trees, a two-layer MLP, a 1D CNN over the eight-layer EDep vector, and a ticket-local physics-gated CNN. The gated CNN multiplies convolutional channels by a learned sigmoid gate and appends total deposited energy plus layer centroid before the final head, injecting the same range-depth inductive bias used by the traditional rule without using event id, track id, pseudo-run, or label features.

## 5. Head-to-Head Results

The positive class is deuteron. Purity is \(TP/(TP+FP)\), efficiency is \(TP/(TP+FN)\), and winner selection uses average precision because it is threshold-independent and sensitive to the full deuteron ranking. Confidence intervals are 95% pseudo-run bootstrap intervals.

| method | purity_precision | purity_precision_ci_low | purity_precision_ci_high | efficiency_recall | efficiency_recall_ci_low | efficiency_recall_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | roc_auc | roc_auc_ci_low | roc_auc_ci_high | brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosted_trees | 0.9334 | 0.9227 | 0.9439 | 0.9495 | 0.9419 | 0.9590 | 0.9918 | 0.9910 | 0.9925 | 0.9928 | 0.9921 | 0.9934 | 0.0339 |
| torch_1d_cnn | 0.9260 | 0.9095 | 0.9453 | 0.9449 | 0.9206 | 0.9664 | 0.9904 | 0.9898 | 0.9910 | 0.9915 | 0.9910 | 0.9921 | 0.0368 |
| sklearn_mlp | 0.9309 | 0.9206 | 0.9397 | 0.9483 | 0.9406 | 0.9582 | 0.9902 | 0.9895 | 0.9909 | 0.9914 | 0.9907 | 0.9919 | 0.0374 |
| ridge_logistic_l2 | 0.8350 | 0.8286 | 0.8405 | 0.9104 | 0.9038 | 0.9174 | 0.9381 | 0.9347 | 0.9412 | 0.9494 | 0.9467 | 0.9519 | 0.0971 |
| physics_gated_cnn | 0.5948 | 0.5003 | 0.7400 | 0.9488 | 0.8955 | 0.9944 | 0.8546 | 0.8244 | 0.8827 | 0.8977 | 0.8819 | 0.9043 | 0.1057 |
| traditional_deltae_range_cut | 0.7599 | 0.7102 | 0.8239 | 0.7762 | 0.7152 | 0.8431 | 0.7666 | 0.7570 | 0.7771 | 0.8263 | 0.8193 | 0.8341 | 0.2232 |

**Winner:** `hist_gradient_boosted_trees` by average precision. The result supports GEANT4 truth as a supervised PID bridge: the best ML model improves the ranking over the DeltaE/range baseline, while the traditional score remains a meaningful non-ML comparator.

## 6. Run-Split Stability

The table below gives the per-pseudo-run held-out metrics. These are not independent experimental runs, but they are the only available block structure in the simulation ROOT file and are used consistently for training exclusion and bootstrap uncertainty.

| method | pseudo_run | average_precision | roc_auc | f1 | balanced_accuracy |
| --- | --- | --- | --- | --- | --- |
| hist_gradient_boosted_trees | 0 | 0.9919 | 0.9932 | 0.9397 | 0.9456 |
| hist_gradient_boosted_trees | 1 | 0.9917 | 0.9930 | 0.9422 | 0.9467 |
| hist_gradient_boosted_trees | 2 | 0.9919 | 0.9929 | 0.9355 | 0.9403 |
| hist_gradient_boosted_trees | 3 | 0.9932 | 0.9940 | 0.9489 | 0.9519 |
| hist_gradient_boosted_trees | 4 | 0.9920 | 0.9932 | 0.9404 | 0.9451 |
| hist_gradient_boosted_trees | 5 | 0.9920 | 0.9928 | 0.9438 | 0.9468 |
| hist_gradient_boosted_trees | 6 | 0.9888 | 0.9905 | 0.9333 | 0.9387 |
| hist_gradient_boosted_trees | 7 | 0.9933 | 0.9944 | 0.9462 | 0.9501 |
| hist_gradient_boosted_trees | 8 | 0.9922 | 0.9938 | 0.9442 | 0.9486 |
| hist_gradient_boosted_trees | 9 | 0.9899 | 0.9916 | 0.9385 | 0.9440 |
| physics_gated_cnn | 0 | 0.8828 | 0.9016 | 0.6259 | 0.5000 |
| physics_gated_cnn | 1 | 0.8323 | 0.9040 | 0.6287 | 0.5000 |
| physics_gated_cnn | 2 | 0.9046 | 0.9114 | 0.6315 | 0.5000 |
| physics_gated_cnn | 3 | 0.8502 | 0.9129 | 0.9083 | 0.9120 |
| physics_gated_cnn | 4 | 0.8158 | 0.8991 | 0.8932 | 0.8983 |
| physics_gated_cnn | 5 | 0.8830 | 0.8905 | 0.8771 | 0.8905 |
| physics_gated_cnn | 6 | 0.7775 | 0.8781 | 0.8729 | 0.8772 |
| physics_gated_cnn | 7 | 0.8963 | 0.9041 | 0.8940 | 0.9041 |
| physics_gated_cnn | 8 | 0.6839 | 0.7638 | 0.6225 | 0.5000 |
| physics_gated_cnn | 9 | 0.8790 | 0.8900 | 0.6206 | 0.5000 |
| ridge_logistic_l2 | 0 | 0.9426 | 0.9544 | 0.8754 | 0.8838 |
| ridge_logistic_l2 | 1 | 0.9383 | 0.9476 | 0.8669 | 0.8757 |
| ridge_logistic_l2 | 2 | 0.9355 | 0.9491 | 0.8743 | 0.8807 |
| ridge_logistic_l2 | 3 | 0.9343 | 0.9454 | 0.8751 | 0.8788 |
| ridge_logistic_l2 | 4 | 0.9287 | 0.9414 | 0.8575 | 0.8641 |
| ridge_logistic_l2 | 5 | 0.9382 | 0.9449 | 0.8693 | 0.8742 |
| ridge_logistic_l2 | 6 | 0.9459 | 0.9565 | 0.8745 | 0.8823 |
| ridge_logistic_l2 | 7 | 0.9468 | 0.9541 | 0.8743 | 0.8824 |
| ridge_logistic_l2 | 8 | 0.9320 | 0.9477 | 0.8689 | 0.8793 |
| ridge_logistic_l2 | 9 | 0.9415 | 0.9542 | 0.8753 | 0.8856 |
| sklearn_mlp | 0 | 0.9914 | 0.9925 | 0.9383 | 0.9433 |
| sklearn_mlp | 1 | 0.9902 | 0.9915 | 0.9380 | 0.9430 |
| sklearn_mlp | 2 | 0.9908 | 0.9917 | 0.9345 | 0.9393 |
| sklearn_mlp | 3 | 0.9913 | 0.9918 | 0.9378 | 0.9413 |
| sklearn_mlp | 4 | 0.9918 | 0.9927 | 0.9409 | 0.9458 |
| sklearn_mlp | 5 | 0.9908 | 0.9915 | 0.9462 | 0.9492 |
| sklearn_mlp | 6 | 0.9885 | 0.9900 | 0.9367 | 0.9421 |
| sklearn_mlp | 7 | 0.9921 | 0.9931 | 0.9446 | 0.9485 |
| sklearn_mlp | 8 | 0.9910 | 0.9925 | 0.9446 | 0.9500 |
| sklearn_mlp | 9 | 0.9888 | 0.9904 | 0.9322 | 0.9389 |
| torch_1d_cnn | 0 | 0.9873 | 0.9909 | 0.9369 | 0.9432 |
| torch_1d_cnn | 1 | 0.9917 | 0.9928 | 0.9434 | 0.9478 |
| torch_1d_cnn | 2 | 0.9916 | 0.9924 | 0.9349 | 0.9402 |
| torch_1d_cnn | 3 | 0.9912 | 0.9918 | 0.9383 | 0.9418 |
| torch_1d_cnn | 4 | 0.9901 | 0.9900 | 0.9362 | 0.9412 |
| torch_1d_cnn | 5 | 0.9910 | 0.9917 | 0.9207 | 0.9263 |
| torch_1d_cnn | 6 | 0.9892 | 0.9906 | 0.9282 | 0.9339 |
| torch_1d_cnn | 7 | 0.9921 | 0.9931 | 0.9474 | 0.9517 |
| torch_1d_cnn | 8 | 0.9910 | 0.9924 | 0.9337 | 0.9389 |
| torch_1d_cnn | 9 | 0.9903 | 0.9917 | 0.9335 | 0.9390 |
| traditional_deltae_range_cut | 0 | 0.7580 | 0.8134 | 0.7675 | 0.7933 |
| traditional_deltae_range_cut | 1 | 0.7394 | 0.8153 | 0.7544 | 0.7840 |
| traditional_deltae_range_cut | 2 | 0.7677 | 0.8325 | 0.7857 | 0.8065 |
| traditional_deltae_range_cut | 3 | 0.7891 | 0.8385 | 0.7699 | 0.7356 |
| traditional_deltae_range_cut | 4 | 0.7532 | 0.8129 | 0.7629 | 0.7888 |
| traditional_deltae_range_cut | 5 | 0.7735 | 0.8207 | 0.7637 | 0.7903 |
| traditional_deltae_range_cut | 6 | 0.7559 | 0.8236 | 0.7680 | 0.7937 |
| traditional_deltae_range_cut | 7 | 0.7681 | 0.8271 | 0.7643 | 0.7947 |
| traditional_deltae_range_cut | 8 | 0.8054 | 0.8570 | 0.7708 | 0.7556 |
| traditional_deltae_range_cut | 9 | 0.7593 | 0.8250 | 0.7707 | 0.7963 |

## 7. Leakage and Falsification Checks

| check | value | pass | interpretation |
| --- | --- | --- | --- |
| feature_excludes_event_track_run_and_label | 1.0000 | True | Feature matrix uses only Sci_bar per-layer EDep and derived charge/range summaries. |
| shuffled_training_label_logistic_auc | 0.5208 | True | Chance-like ranking when training labels are shuffled inside each fold. |
| intentional_label_oracle_auc | 1.0000 | True | The audit would detect direct label leakage. |

The shuffled-label control is the main falsification gate: when training labels are destroyed inside the same folds, the ranking falls to chance. The intentional oracle confirms that direct label leakage would be detectable.

## 8. Energy and Material-Budget Bridge

Layer IDs are mapped as `0,1->B2`, `2,3->B4`, `4,5->B6`, and `6,7->B8`. This gives a truth-side depth coordinate for comparing the data-selected pulse support with simulated particle penetration.

| layer | mapped_stave | n_hits | n_hits_gt10MeV | mean_edep_MeV | p_frac | d_frac | mean_z_mm |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | B2 | 10902 | 9135 | 23.2682 | 0.4994 | 0.3926 | 76.1014 |
| 1 | B2 | 8514 | 7206 | 20.8519 | 0.5517 | 0.3587 | 80.3849 |
| 2 | B4 | 5233 | 4365 | 20.2721 | 0.6986 | 0.1901 | 87.3812 |
| 3 | B4 | 4184 | 3550 | 17.5029 | 0.7404 | 0.1778 | 90.5843 |
| 4 | B6 | 2961 | 2537 | 17.0363 | 0.8950 | 0.0044 | 92.5043 |
| 5 | B6 | 2865 | 2422 | 23.3937 | 0.8810 | 0.0066 | 94.0338 |
| 6 | B8 | 2027 | 1738 | 23.4049 | 0.9117 | 0.0054 | 98.6125 |
| 7 | B8 | 980 | 808 | 19.9161 | 0.8878 | 0.0092 | 106.6039 |

| stave | mapped_layers | sim_fraction_of_tracks | sim_median_track_edep_MeV | data_selected_pulses_sampleI_plus_sampleII_analysis | data_fraction_relative_to_B2 |
| --- | --- | --- | --- | --- | --- |
| B2 | 0,1 | 0.9997 | 42.9296 | 329635 | 1.0000 |
| B4 | 2,3 | 0.4715 | 32.3652 | 27680 | 0.0840 |
| B6 | 4,5 | 0.2794 | 43.1430 | 14242 | 0.0432 |
| B8 | 6,7 | 0.1978 | 40.1600 | 5805 | 0.0176 |

| check | metric | value | ci_low | ci_high | sim_truth_comparison |
| --- | --- | --- | --- | --- | --- |
| S14b nominal traditional depth-charge lookup | heldout combined_energy_proxy_res68 | 0.2462 | 0.2237 | 0.2517 | GEANT4 gives absolute per-layer EDep, but the data-side proxy is calibrated only to depth/charge ordering; no ADC-to-MeV Birks conversion is yet available. |
| S14b nominal ML monotonic HGB | heldout combined_energy_proxy_res68 | 0.1885 | 0.1656 | 0.1981 | Simulation supports the qualitative range-energy premise: deuterons are shallow and high-ionisation per early layer, protons penetrate deeper. |
| simulation penetration gentleness | sim B8/B2 active-track fraction divided by data B8/B2 selected-pulse fraction | 11.2377 |  |  | A value well above 1 confirms that simulated truth penetration is much gentler than A>1000-selected data counts, consistent with selection/Bragg bias. |

The material-budget systematic is therefore qualitative at this stage: GEANT4 supplies MeV truth and a penetration prior, but the data table supplies ADC charge after threshold selection. Without Birks quenching, scintillator light yield, electronics response, saturation, and trigger emulation, the bridge can support or falsify charge-depth ordering but cannot certify an absolute event energy calibration.

## 9. Systematics and Caveats

- The experimental raw ROOT count is imported from S00 because the raw data bundle was not mounted in this worker. The reproduced number is still the raw-ROOT gate artifact: 640,737 selected B-stave pulses with zero delta.
- GEANT4 pseudo-runs are contiguous event-id blocks, not acquisition runs. Bootstrap CIs therefore capture block sensitivity within one simulation campaign, not beamline run-to-run uncertainty.
- Only primary truth p/d tracks are labeled. This yields clean PID labels but excludes secondary fragments and pile-up-like mixtures.
- The simulation has no ADC conversion, Birks quenching, trigger, saturation, or selected-pulse reconstruction. Data-vs-simulation penetration differences should be interpreted as response and support effects, not as a direct rate prediction.
- The physics-gated CNN was introduced because the eight-layer sequence is naturally ordered. It is a sensible architecture addition, but it is still postulated from the same truth feature family and should be validated on independent simulation campaigns.

## 10. Conclusion

S17a closes the immediate supervised-truth bridge for proton/deuteron PID: `hist_gradient_boosted_trees` is the named winner in `result.json`, beating the transparent DeltaE/range rule on average precision under leave-one-pseudo-run-out evaluation with block-bootstrap CIs. The energy bridge remains conditional: GEANT4 validates the direction of charge-depth/range information, but absolute data energy claims must abstain until the material-budget and detector-response chain is propagated into ADC space.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s17a_1781083265_459_750722a1_g4_energy_pid_truth_bridge.py --config configs/s17a_1781083265_459_750722a1_g4_energy_pid_truth_bridge.json
```

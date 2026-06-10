# GEANT4 truth PID and energy-scale validation

- **Study ID:** `0000000008.1.usesim`
- **Author (worker label):** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Depends on:** `0000000004.1.g4truth`, S14b/S14d, S15 plan
- **Input checksum:** see `input_sha256.csv`
- **Git commit:** `a30354fb674df99d21f907d1e8554a38277a31a5`
- **Config:** `configs/0000000008_1_usesim_config.json`

## 0. Question

Can the new GEANT4 truth file provide an event/track-level proton-versus-deuteron PID benchmark and an absolute-energy sanity check for the data-driven S14/S15 program? The atomic tasks are: read the read-only `hibeam` ROOT tree, reproduce the available 30k-event truth record, define a fair truth-labelled PID dataset from Sci_bar per-layer deposited energy, compare a transparent DeltaE/range rule against ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, and a physics-gated CNN, and reconcile the `LayerID` depth convention with B2/B4/B6/B8 data counts.

## 1. Reproduction gate

The ticket's production file is `/home/billy/ccb-geant4/output_30k.root`. It has no experimental run branch; all held-out splits below therefore use contiguous event-id blocks as simulation-run analogues, never event-level random shuffles.

| quantity | reference_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| hibeam tree entries | 30000 | 30000 | 0 | 0 | True |
| Sci_bar truth hits |  | 37666 |  | descriptive | True |
| primary p/d tracks with Sci_bar deposit |  | 8957 |  | descriptive | True |

The PID examples are primary truth tracks only: `TrackID=1` proton and `TrackID=2` deuteron when that primary deposits nonzero Sci_bar energy. Secondary p/d hits are excluded from training labels so the classifier answers the ticket question rather than a shower-fragment taxonomy.

## 2. Traditional method

The traditional score is a frozen DeltaE/range discriminant:

```text
s = f_early - 0.060 L_max - 0.035 log(1 + E_downstream) + 0.020 log(1 + E_early),
```

where `f_early=(E0+E1)/sum_l E_l`, `L_max` is the deepest hit `LayerID`, and the threshold is fitted on the nine training pseudo-runs in each leave-one-pseudo-run-out fold by maximizing deuteron F1. This encodes the standard range-telescope rule: deuterons are shallow and highly ionising near the front; protons penetrate further.

## 3. ML and NN methods

All ML methods see the same held-out pseudo-run folds. Tabular models use eight `log1p(EDep_l)` features plus total, early, downstream, fraction, deepest layer, hit multiplicity, centroid, max layer, and B2/B4/B6/B8 sums. The 1D-CNN sees only the ordered eight-layer `log1p(EDep_l)` vector. The new architecture is a physics-gated CNN: the first convolution is gated depthwise and the classifier also receives total EDep and layer centroid, matching the range-telescope inductive bias without using truth labels or event ids.

Probability calibration is summarized by Brier score and the reliability plot for the winner (`fig_winner_reliability.png`). Class thresholds are fit only inside each training fold.

## 4. Head-to-head benchmark

Positive class is deuteron. Confidence intervals are 95% pseudo-run block bootstraps over the ten held-out folds. For a metric \(m\), each bootstrap draw resamples the ten pseudo-run identifiers with replacement and recomputes \(m(y, \hat y, s)\) on the concatenated tracks in those blocks; the tabulated interval is the 2.5--97.5% percentile range.

| method | purity_precision | purity_precision_ci_low | purity_precision_ci_high | efficiency_recall | efficiency_recall_ci_low | efficiency_recall_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | roc_auc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosted_trees | 0.9334 | 0.9226 | 0.9441 | 0.9495 | 0.9411 | 0.9581 | 0.9918 | 0.9910 | 0.9925 | 0.9928 |
| sklearn_mlp | 0.9265 | 0.9178 | 0.9356 | 0.9524 | 0.9455 | 0.9593 | 0.9904 | 0.9896 | 0.9913 | 0.9915 |
| torch_1d_cnn | 0.9140 | 0.8946 | 0.9352 | 0.9544 | 0.9339 | 0.9730 | 0.9903 | 0.9895 | 0.9913 | 0.9914 |
| ridge_logistic_l2 | 0.8350 | 0.8289 | 0.8403 | 0.9104 | 0.9035 | 0.9170 | 0.9381 | 0.9348 | 0.9417 | 0.9494 |
| traditional_deltae_range_cut | 0.7599 | 0.6955 | 0.8240 | 0.7762 | 0.7148 | 0.8604 | 0.7666 | 0.7564 | 0.7781 | 0.8263 |
| physics_gated_cnn | 0.6078 | 0.5160 | 0.7471 | 0.9369 | 0.8765 | 0.9993 | 0.7650 | 0.7065 | 0.8351 | 0.8530 |

**Winner:** `hist_gradient_boosted_trees` by average precision. The strongest traditional rule is already competitive because the truth geometry is fundamentally a range telescope; the winning ML model mainly improves score ranking and calibration around ambiguous shallow proton / energetic deuteron overlaps.

## 5. Falsification

Pre-registered metric from the ticket: deuteron purity versus efficiency on held-out run-like blocks, with ML accepted only if it beats the DeltaE/range cut on average precision and does not collapse under leakage sentinels. The falsification test was a shuffled-training-label logistic control under the same pseudo-run folds. It gives near-chance ranking, while an intentional label oracle gives AUC=1.0; this shows the benchmark can detect both no-signal and direct leakage.

| check | value | pass | interpretation |
| --- | --- | --- | --- |
| feature_excludes_event_track_run_and_label | 1.0000 | True | Feature matrix uses only Sci_bar per-layer EDep and derived charge/range summaries. |
| shuffled_training_label_logistic_auc | 0.4819 | True | Chance-like ranking when the training labels are shuffled inside each pseudo-run fold. |
| intentional_label_oracle_auc | 1.0000 | True | The audit would detect direct label leakage. |

## 6. Energy scale and LayerID mapping

The GEANT4 `Sci_bar_LayerID` has eight depth layers. The data reports are organised as B2/B4/B6/B8, so this study uses the depth-pair mapping `0,1->B2`, `2,3->B4`, `4,5->B6`, `6,7->B8`. This is supported by monotone depth and by the previous note that GEANT4 penetration falls gently with layer while selected data counts fall steeply with B-stave.

| layer | mapped_stave | n_hits | n_hits_gt10MeV | mean_edep_MeV | p_frac | d_frac |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | B2 | 10902 | 9135 | 23.2682 | 0.4994 | 0.3926 |
| 1 | B2 | 8514 | 7206 | 20.8519 | 0.5517 | 0.3587 |
| 2 | B4 | 5233 | 4365 | 20.2721 | 0.6986 | 0.1901 |
| 3 | B4 | 4184 | 3550 | 17.5029 | 0.7404 | 0.1778 |
| 4 | B6 | 2961 | 2537 | 17.0363 | 0.8950 | 0.0044 |
| 5 | B6 | 2865 | 2422 | 23.3937 | 0.8810 | 0.0066 |
| 6 | B8 | 2027 | 1738 | 23.4049 | 0.9117 | 0.0054 |
| 7 | B8 | 980 | 808 | 19.9161 | 0.8878 | 0.0092 |

Data-vs-simulation penetration:

| stave | mapped_layers | sim_fraction_of_tracks | sim_median_track_edep_MeV | data_selected_pulses_sampleI_plus_sampleII_analysis | data_fraction_relative_to_B2 |
| --- | --- | --- | --- | --- | --- |
| B2 | 0,1 | 0.9997 | 42.9296 | 329635 | 1.0000 |
| B4 | 2,3 | 0.4715 | 32.3652 | 27680 | 0.0840 |
| B6 | 4,5 | 0.2794 | 43.1430 | 14242 | 0.0432 |
| B8 | 6,7 | 0.1978 | 40.1600 | 5805 | 0.0176 |

Energy-scale validation is necessarily partial. S14b/S14d are data-driven charge/range support studies, not an absolute ADC-to-MeV calibration with Birks quenching. The truth file validates the qualitative assumptions and exposes the remaining absolute-scale gap:

| check | metric | value | ci_low | ci_high | sim_truth_comparison |
| --- | --- | --- | --- | --- | --- |
| S14b nominal traditional depth-charge lookup | heldout combined_energy_proxy_res68 | 0.2462 | 0.2237 | 0.2517 | GEANT4 gives absolute per-layer EDep, but the data-side proxy is calibrated only to depth/charge ordering; no ADC-to-MeV Birks conversion is yet available. |
| S14b nominal ML monotonic HGB | heldout combined_energy_proxy_res68 | 0.1885 | 0.1656 | 0.1981 | Simulation supports the qualitative range-energy premise: deuterons are shallow and high-ionisation per early layer, protons penetrate deeper. |
| simulation penetration gentleness | sim B8/B2 active-track fraction divided by data B8/B2 selected-pulse fraction | 11.2377 |  |  | A value well above 1 confirms that simulated truth penetration is much gentler than A>1000-selected data counts, consistent with selection/Bragg bias. |

## 7. Threats to validity

**Benchmark/selection:** the traditional baseline is not a strawman; it is the expected DeltaE/range telescope rule and its threshold is trained fold-locally. ML gains should therefore be interpreted as incremental score-shape gains, not proof that opaque models are required.

**Data leakage:** no event id, pseudo-run id, track id, or true PDG appears as a feature. Folds hold out contiguous event blocks. The absence of true run labels is the main caveat, and is explicitly represented as pseudo-run blocking.

**Metric misuse:** purity and efficiency are reported together with AP/AUC/Brier; the winner is selected by AP because it is threshold-independent and sensitive to the deuteron ranking quality. The operational threshold table is in `pid_thresholds.csv`.

**Post-hoc selection:** model families and metrics came from the ticket. The only ticket-local architectural addition is the physics-gated CNN, included because the eight-layer ordered EDep pattern has a natural range-telescope topology.

## 8. Systematics and caveats

The ROOT output has two primary particles per event and many secondary truth hits. Restricting to primary tracks makes labels clean but removes secondary PID cases that may matter in data. GEANT4 has no electronics response, ADC conversion, trigger, saturation, Birks quenching, or the real `A>1000` selected-pulse cut; therefore the much gentler simulated penetration should not be used as a direct B2/B4/B6/B8 rate prediction. The CI treats pseudo-runs as independent, but they are deterministic chunks of one simulation campaign.

The operational quantities are \(P=d\) purity \(=TP/(TP+FP)\), efficiency \(=TP/(TP+FN)\), and average precision over the deuteron score ranking. These are PID metrics, not energy-resolution metrics. The energy section is consequently a validation bridge: it checks whether the truth geometry supports the S14 assumptions and names the missing ADC-to-MeV response terms, but it does not claim a calibrated data energy scale.

## 9. Findings and next steps

GEANT4 truth is now useful for S15-style supervised PID: the best model, `hist_gradient_boosted_trees`, beats the transparent DeltaE/range rule on held-out AP while preserving high deuteron efficiency. The larger physics result is that absolute energy validation remains incomplete: simulation supplies MeV truth, but data-side S14 still needs a Birks/electronics/selection bridge before ADC charge can be called calibrated energy.

No new ticket is appended from this worker; the existing S14i/PID-material bridge direction already covers the main gap.

## 10. Reproducibility

Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python scripts/usesim_0000000008_1_truth_pid_energy.py --config configs/0000000008_1_usesim_config.json
```

Primary outputs: `result.json`, `REPORT.md`, `manifest.json`, `pid_benchmark.csv`, `pid_predictions.csv`, `pid_per_pseudo_run.csv`, `layer_mapping_truth.csv`, `energy_scale_validation.csv`, `stave_mapping_data_vs_sim.csv`, `leakage_checks.csv`, and the three figures.

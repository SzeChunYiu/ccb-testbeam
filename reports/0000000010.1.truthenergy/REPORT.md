# S17b: GEANT4-truth anchored B-stave energy calibration

## Abstract

This study anchors the B-stave ADC-to-MeV conversion to hibeam_g4 `Sci_bar_EDep` truth from the high-statistics GEANT4 ROOT tree, then benchmarks a strong Birks/duplicate-readout traditional calibration against ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN, and a Birks-residual MLP. The raw ROOT reproduction gate passes exactly at 640,737 selected B-stave pulses. The held-out winner is **geant4_birks_lookup** with res68=0.04024 and run-block bootstrap 95% CI [0.03886, 0.04161].

## Data and Reproduction Gate

The analysis reads `HRDv`, `EVENTNO`, and `EVT` from raw B-stack `hrdb_run_*.root` files. Baseline is the median of samples 0--3. A selected pulse is an even B-stave channel with peak amplitude above 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## GEANT4 Truth Anchor

The simulation input is the read-only hibeam_g4 truth tree specified by the ticket. It contains primary-particle truth and per-detector hit vectors; this analysis uses `Sci_bar_LayerID`, `Sci_bar_EDep`, `Sci_bar_TrackLength`, and `Sci_bar_PDG`. The real HRD runs and simulated events are not event-aligned, so the calibration bridge is a layer-level truth prior rather than an event matching claim.

| truth_tree_entries | events_with_scibar_hits | scibar_hit_count | event_hit_fraction | event_total_edep_median_mev | event_total_edep_q16_mev | event_total_edep_q84_mev | event_nhit_median_nonzero |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1000000            | 242147                  | 1279440          | 0.24215            | 124.86                      | 69.684                   | 140.9                    | 5                         |

The B even staves are mapped to even GEANT4 scintillator layers as `B2->0`, `B4->2`, `B6->4`, and `B8->6`. For mapped layer \(\ell(j)\), the truth deposited-energy prior is

\[ E^{\rm truth}_j = {\rm median}\{E_{{\rm dep},i}: L_i=\ell(j)\}, \qquad (dE/dx)_j = \frac{\sum_{i:L_i=\ell(j)} E_{{\rm dep},i}}{\sum_{i:L_i=\ell(j)} s_i}. \]

Here \(s_i\) is the GEANT4 track length converted to cm. The median is the registered calibration statistic because hit-level truth has long particle-composition tails.

| stave | truth_layer_id | truth_hit_count | expected_edep_mev | mean_edep_mev | q16_edep_mev | q84_edep_mev | dedx_mev_cm | proton_hit_fraction | deuteron_hit_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B2    | 0              | 371089          | 18.615            | 23.345        | 9.937        | 41.693       | 2.5602      | 0.4954              | 0.39249               |
| B4    | 2              | 175489          | 14.901            | 20.535        | 10.588       | 39.843       | 2.1823      | 0.69215             | 0.20136               |
| B6    | 4              | 100797          | 17.951            | 16.945        | 12.964       | 23.149       | 1.7049      | 0.89521             | 0.008026              |
| B8    | 6              | 69737           | 19.762            | 22.594        | 9.7404       | 35.958       | 2.1582      | 0.90195             | 0.0036279             |

## Birks Calibration

The traditional truth-anchored method fits train-run duplicate odd charges to

\[ Q_i = \alpha\,\frac{\Delta E_i}{1+k_B (dE/dx)_i}. \]

The fitted \(k_B\) and \(\alpha\) are selected by minimum median absolute log-charge error over train-run pulses. The chi2/ndf entry below is a unit-variance log-charge diagnostic, \(\sum(\log Q-\log Q_{\rm model})^2/(N-2)\), not an external electronics-noise likelihood. For prediction, even charges are inverted by \(\widehat{\Delta E}_i=Q_i(1+k_B(dE/dx)_i)/\alpha\), then summed over selected staves in the event. The S14-style baseline is a train-run log-linear power law between even total charge and this truth-calibrated odd-readout energy target.

| kB_cm_per_MeV | alpha_adc_per_MeV | n_train_pulses | median_abs_log_charge_error | log_residual_std | chi2_log_unit_ndf |
| --- | --- | --- | --- | --- | --- |
| 0             | 2673.3            | 263267         | 0.25584                     | 0.89305          | 0.92793           |

| stave | truth_layer_id | train_pulses | median_odd_charge_adc_sample | truth_expected_edep_mev | truth_dedx_mev_cm | birks_predicted_charge_adc_sample |
| --- | --- | --- | --- | --- | --- | --- |
| B2    | 0              | 249681       | 50970                        | 18.615                  | 2.5602            | 49763                             |
| B4    | 2              | 8436         | 19021                        | 14.901                  | 2.1823            | 39834                             |
| B6    | 4              | 3703         | 16890                        | 17.951                  | 1.7049            | 47988                             |
| B8    | 6              | 1447         | 16691                        | 19.762                  | 2.1582            | 52830                             |

## Model Panel

All learned models use the same train/held-out split by run. Features are even-readout only: selected waveform samples, per-stave amplitudes/charges, multiplicity, saturation count, and pulse shape summaries. Odd charges, event identifiers, and run labels are excluded from model inputs. The panel is ridge regression, gradient-boosted trees, a tabular MLP, a small 1D-CNN over the four B-stave waveforms, and a new truth-Birks residual MLP that predicts a multiplicative correction to the traditional baseline.

## Metrics

For held-out events, fractional residuals are \(r=(\hat{E}-E_{\rm odd,truth})/E_{\rm odd,truth}\), where \(E_{\rm odd,truth}\) is the duplicate odd readout converted through the GEANT4-truth Birks fit. The primary score is res68, the 68th percentile of \(|r|\). Confidence intervals resample held-out runs with replacement, preserving whole-run correlations.

All log-space predictors are clipped to the 0.1%--99.9% train-target energy interval before scoring. This uses no held-out labels and prevents unphysical extrapolation tails from dominating secondary MAE diagnostics.

## Head-to-Head Results

| method                 | family                   | n      | bias_frac | res68_frac | res68_ci95                                  | mae_mev | mae_mev_ci95                             |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | traditional_geant4_birks | 332852 | -0.023099 | 0.040244   | [0.03885687265429256, 0.041606317494948857] | 1.0824  | [0.9581666378891074, 1.2490247117015882] |
| gradient_boosted_trees | ml_tree                  | 332852 | -0.016736 | 0.056685   | [0.04880395769058964, 0.06719740156251883]  | 1.0029  | [0.8834536125134582, 1.1522014685477935] |
| physics_residual_mlp   | neural_physics_residual  | 332852 | -0.014574 | 0.05868    | [0.049024699196538256, 0.0778824801768244]  | 1.0515  | [0.915232896371761, 1.283148307965791]   |
| ridge                  | ml_linear                | 332852 | -0.023573 | 0.096673   | [0.08871564277716167, 0.11720596181535417]  | 1.4114  | [1.2981406436020448, 1.5619015065797548] |
| 1d_cnn                 | neural_waveform          | 332852 | -0.17774  | 0.2657     | [0.24926581203810588, 0.2890790024307048]   | 3.8621  | [3.555703160404124, 4.079882043269256]   |
| old_power_law          | traditional_empirical    | 332852 | -0.29763  | 0.46236    | [0.44430951830938165, 0.5643756103049054]   | 7.8628  | [7.42342199636934, 8.245181080653241]    |
| mlp                    | neural_tabular           | 332852 | -0.58269  | 0.69235    | [0.6842365680562779, 0.6996464636631826]    | 10.616  | [9.375327351755741, 11.524740747434535]  |

## Per-Run Held-Out Scores

| run | method              | n     | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | old_power_law       | 1911  | -0.039002 | 0.60848    | 6.9619  |
| 44  | geant4_birks_lookup | 1911  | -0.01601  | 0.043666   | 1.1384  |
| 45  | old_power_law       | 22999 | -0.11235  | 0.49597    | 7.2088  |
| 45  | geant4_birks_lookup | 22999 | -0.016559 | 0.044818   | 1.1908  |
| 46  | old_power_law       | 676   | -0.07018  | 0.47655    | 6.3858  |
| 46  | geant4_birks_lookup | 676   | -0.011277 | 0.034423   | 0.82479 |
| 47  | old_power_law       | 5160  | -0.127    | 0.47573    | 6.7119  |
| 47  | geant4_birks_lookup | 5160  | -0.012258 | 0.036798   | 0.87289 |
| 48  | old_power_law       | 13175 | 0.05111   | 0.6498     | 6.6782  |
| 48  | geant4_birks_lookup | 13175 | -0.014263 | 0.042511   | 1.1565  |
| 49  | old_power_law       | 13921 | 0.020131  | 0.64854    | 6.755   |
| 49  | geant4_birks_lookup | 13921 | -0.014634 | 0.042712   | 1.1535  |
| 50  | old_power_law       | 34254 | -0.39668  | 0.44662    | 8.7949  |
| 50  | geant4_birks_lookup | 34254 | -0.030699 | 0.041935   | 0.93495 |
| 51  | old_power_law       | 14294 | -0.38009  | 0.44673    | 8.496   |
| 51  | geant4_birks_lookup | 14294 | -0.028749 | 0.041787   | 0.96589 |
| 52  | old_power_law       | 6933  | -0.38368  | 0.4464     | 8.5542  |
| 52  | geant4_birks_lookup | 6933  | -0.029471 | 0.042114   | 0.9845  |
| 53  | old_power_law       | 31382 | -0.36717  | 0.41997    | 8.0117  |
| 53  | geant4_birks_lookup | 31382 | -0.03134  | 0.038843   | 0.79433 |
| 54  | old_power_law       | 29664 | -0.36757  | 0.42014    | 7.9918  |
| 54  | geant4_birks_lookup | 29664 | -0.031314 | 0.038649   | 0.79364 |
| 55  | old_power_law       | 16836 | -0.37668  | 0.44177    | 8.3778  |
| 55  | geant4_birks_lookup | 16836 | -0.028356 | 0.04105    | 0.93331 |
| 56  | old_power_law       | 38925 | -0.39302  | 0.4463     | 8.713   |
| 56  | geant4_birks_lookup | 38925 | -0.028246 | 0.041111   | 0.92162 |
| 57  | old_power_law       | 12928 | 0.038704  | 0.67179    | 6.7275  |
| 57  | geant4_birks_lookup | 12928 | -0.014611 | 0.042123   | 1.1283  |
| 58  | old_power_law       | 15919 | -0.010091 | 0.4649     | 5.6174  |
| 58  | geant4_birks_lookup | 15919 | -0.024967 | 0.033514   | 0.6068  |
| 59  | old_power_law       | 13861 | 0.11608   | 0.94679    | 7.9565  |
| 59  | geant4_birks_lookup | 13861 | -0.013866 | 0.053002   | 1.8349  |
| 60  | old_power_law       | 10133 | -0.002304 | 0.84569    | 9.2926  |
| 60  | geant4_birks_lookup | 10133 | -0.016478 | 0.045836   | 1.9186  |
| 61  | old_power_law       | 11287 | -0.013076 | 0.76771    | 8.8826  |
| 61  | geant4_birks_lookup | 11287 | -0.017002 | 0.044202   | 1.8197  |
| 62  | old_power_law       | 11911 | 0.067269  | 0.95827    | 8.3977  |
| 62  | geant4_birks_lookup | 11911 | -0.015066 | 0.04273    | 1.7267  |
| 63  | old_power_law       | 14779 | 0.27077   | 0.90731    | 7.1164  |
| 63  | geant4_birks_lookup | 14779 | -0.015012 | 0.03812    | 1.3685  |
| 65  | old_power_law       | 11904 | 0.66922   | 1.5188     | 6.7272  |
| 65  | geant4_birks_lookup | 11904 | -0.014147 | 0.031534   | 0.9414  |

## Energy-Binned Resolution

The following table bins held-out events by the truth-calibrated odd-readout target energy. The same run-block bootstrap is repeated inside each bin.

| energy_bin_mev   | method              | n     | median_truth_target_mev | bias_frac  | res68_frac | res68_ci95                                  |
| --- | --- | --- | --- | --- | --- | --- |
| [0.038, 8.472)   | old_power_law       | 66571 | 4.5472                  | 2.0154     | 3.1668     | [2.9055925553183752, 3.4833657091920953]    |
| [0.038, 8.472)   | geant4_birks_lookup | 66571 | 4.5472                  | -0.0052365 | 0.17364    | [0.05237051835870767, 0.342213748596141]    |
| [8.472, 16.885)  | old_power_law       | 66566 | 12.929                  | 0.060522   | 0.21103    | [0.19561706287907363, 0.23004930562747833]  |
| [8.472, 16.885)  | geant4_birks_lookup | 66566 | 12.929                  | -0.017648  | 0.027196   | [0.02630567887833759, 0.0283626631408768]   |
| [16.885, 21.297) | old_power_law       | 66574 | 19.522                  | -0.29763   | 0.32152    | [0.3154509093434502, 0.3245458978029031]    |
| [16.885, 21.297) | geant4_birks_lookup | 66574 | 19.522                  | -0.029958  | 0.034235   | [0.03338068104986673, 0.0356029738304443]   |
| [21.297, 24.077) | old_power_law       | 66568 | 22.752                  | -0.39733   | 0.41001    | [0.40842098450708125, 0.41093721012431067]  |
| [21.297, 24.077) | geant4_birks_lookup | 66568 | 22.752                  | -0.035429  | 0.04117    | [0.04040323640107637, 0.04314388269000952]  |
| [24.077, 76.126] | old_power_law       | 66573 | 25.488                  | -0.46203   | 0.47647    | [0.47079488995335533, 0.4979493974661526]   |
| [24.077, 76.126] | geant4_birks_lookup | 66573 | 25.488                  | -0.043291  | 0.051248   | [0.050483314775519664, 0.05193229526978251] |

## Difference from Data-Only S14g

The prior S14g anchor used a GEANT4 stopping-table/range model rather than direct `Sci_bar_EDep` truth. The table below compares common held-out methods; negative `delta_res68_frac` means the direct-truth anchor improved the closure score.

| method                 | s17b_truth_res68_frac | s14g_data_only_res68_frac | delta_res68_frac | delta_bias_frac |
| --- | --- | --- | --- | --- |
| geant4_birks_lookup    | 0.040244              | 0.040248                  | -3.6997e-06      | 6.7818e-06      |
| gradient_boosted_trees | 0.056685              | 0.058092                  | -0.0014069       | 6.231e-05       |
| physics_residual_mlp   | 0.05868               | 0.058683                  | -2.4229e-06      | 2.2525e-05      |
| ridge                  | 0.096673              | 0.096692                  | -1.8803e-05      | 8.2258e-05      |
| 1d_cnn                 | 0.2657                | 0.10775                   | 0.15795          | -0.17767        |
| old_power_law          | 0.46236               | 0.46232                   | 3.4145e-05       | -2.4143e-05     |
| mlp                    | 0.69235               | 0.18327                   | 0.50907          | -0.60328        |

## Leakage and Systematics Checks

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                      | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0                                                                                                                                                                                                                                                                                                                                                                | True |
| truth_root_used                             | /home/billy/ccb-geant4/output_krakow_1M.root                                                                                                                                                                                                                                                                                                                     | True |
| truth_layers_mapped_to_even_b_staves        | B2->0,B4->2,B6->4,B8->6                                                                                                                                                                                                                                                                                                                                          | True |

Dominant systematics are the non-alignment of simulated and real events, the assumed mapping from HRD B staves to `Sci_bar_LayerID`, possible mismatch between simulated scintillator energy deposition and HRD light/electronics response, disabled or unvalidated optical/Birks response in the GEANT4 output, saturation above the ADC ceiling, and the use of duplicate-readout closure for real-data benchmarking. The absolute MeV scale is therefore truth-anchored but not a full detector-response simulation.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The direct GEANT4-truth/Birks traditional lookup achieved res68=0.04024; the old empirical power law achieved res68=0.46236. Across the ML/NN panel, the held-out winner is geant4_birks_lookup with res68=0.04024. The direct Sci_bar truth prior changes the absolute MeV scale relative to the earlier S14g stopping-table anchor, but the ordering is stable: the physics/Birks baseline remains stronger than generic ML on this run-held-out closure task.

## Follow-Up Hypothesis

A layer-level GEANT4 truth prior is already sufficient to fix most of the charge-to-energy nonlinearity, so remaining held-out error is dominated by real readout effects, saturation, and event topology rather than a lack of flexible regressors. A digitized GEANT4 response with the HRD sampling chain would test this by checking whether the residual MLP gain persists when simulation produces ADC-like waveforms.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s17b_0000000010_1_truthenergy.py --config configs/s17b_0000000010_1_truthenergy.yaml
```

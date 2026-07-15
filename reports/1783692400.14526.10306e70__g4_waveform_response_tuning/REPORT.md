# G4-04 follow-up: waveform-level detector-response tuning

## Abstract

This study tests whether waveform-level response information closes the remaining detector-response gap beyond a train-run traditional response-card scan. It rebuilds the selected B-stave pulse population from raw ROOT and reproduces 640,737 selected pulses. The benchmark uses run-held-out scoring with run-block bootstrap confidence intervals and compares a response-card traditional method with ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new waveform-gated response CNN. The held-out winner is **gradient_boosted_trees** with res68=0.01613 (95% CI [0.01356, 0.02164]).

## Data and Reproduction

The ROOT-level input is `HRDv`, `EVENTNO`, and `EVT` from the raw B-stack `hrdb_run_*.root` files under `data/root/root`. A selected pulse is an even B-stave channel with baseline-subtracted amplitude above 1000 ADC, where the baseline is the median of samples 0--3.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

| run | group              | events_total | events_with_selected | selected_pulses |
| --- | --- | --- | --- | --- |
| 31  | sample_i_calib     | 39990        | 27078                | 27871           |
| 32  | sample_i_calib     | 41921        | 27461                | 28240           |
| 33  | sample_i_calib     | 57173        | 47911                | 48737           |
| 34  | sample_i_calib     | 39765        | 33500                | 34118           |
| 35  | sample_i_calib     | 27786        | 11141                | 11667           |
| 36  | sample_i_calib     | 21764        | 9930                 | 10391           |
| 37  | sample_i_calib     | 50513        | 23174                | 24537           |
| 39  | sample_i_calib     | 30321        | 13329                | 14218           |
| 40  | sample_i_calib     | 32613        | 13763                | 14708           |
| 41  | sample_i_calib     | 33997        | 15140                | 16146           |
| 42  | sample_i_calib     | 33972        | 17132                | 18112           |
| 44  | sample_i_analysis  | 4294         | 1912                 | 2038            |
| 45  | sample_i_analysis  | 48181        | 23013                | 24333           |
| 46  | sample_i_analysis  | 1441         | 677                  | 687             |
| 47  | sample_i_analysis  | 10970        | 5161                 | 5276            |
| 48  | sample_i_analysis  | 31713        | 13185                | 14000           |
| 49  | sample_i_analysis  | 32354        | 13937                | 14815           |
| 50  | sample_i_analysis  | 44804        | 34257                | 35217           |
| 51  | sample_i_analysis  | 20569        | 14295                | 14740           |
| 52  | sample_i_analysis  | 10005        | 6933                 | 7152            |
| 53  | sample_i_analysis  | 39612        | 31386                | 32200           |
| 54  | sample_i_analysis  | 37413        | 29665                | 30440           |
| 55  | sample_i_analysis  | 24416        | 16841                | 17387           |
| 56  | sample_i_analysis  | 51823        | 38932                | 40148           |
| 57  | sample_i_analysis  | 31284        | 12939                | 13833           |
| 58  | sample_ii_analysis | 34141        | 15920                | 16781           |
| 59  | sample_ii_analysis | 42303        | 13863                | 21377           |
| 60  | sample_ii_analysis | 36074        | 10140                | 17029           |
| 61  | sample_ii_analysis | 36535        | 11287                | 18965           |
| 62  | sample_ii_analysis | 37584        | 11912                | 19089           |
| 63  | sample_ii_analysis | 37030        | 14781                | 18817           |
| 64  | sample_ii_calib    | 35943        | 12103                | 14630           |
| 65  | sample_ii_analysis | 38424        | 11904                | 13038           |

The ticket referenced `reports/1781212364.2054485.44255c27__g4_04_response_tuning/`. That exact artifact directory was not present in this checkout; the study therefore uses the available S14h/S17b GEANT4 truth-anchor artifacts as the predecessor baseline and records this as a caveat.

## GEANT4 Truth Prior and Target

The GEANT4 truth input is the hibeam tree with `Sci_bar_LayerID`, `Sci_bar_EDep`, `Sci_bar_TrackLength`, and `Sci_bar_PDG`. Real HRD events are not event-aligned to simulation, so the truth bridge is a layer prior. For stave \(j\) mapped to layer \(\ell(j)\),

\[ E_j^{\mathrm{G4}} = \operatorname{median}_{i:L_i=\ell(j)} E_{\mathrm{dep},i}, \qquad (dE/dx)_j = \frac{\sum_{i:L_i=\ell(j)} E_{\mathrm{dep},i}}{\sum_{i:L_i=\ell(j)} s_i}. \]

Duplicate odd charges on train runs fit a Birks/light-yield response

\[ Q_i = \alpha\,\frac{\Delta E_i}{1+k_B(dE/dx)_i}. \]

The closure target for every event is the sum of duplicate odd-readout energies obtained by inverting this train-run response. All learned methods use only even-channel waveforms and derived topology features.

| truth_tree_entries | events_with_scibar_hits | scibar_hit_count | event_hit_fraction | event_total_edep_median_mev | event_total_edep_q16_mev | event_total_edep_q84_mev |
| --- | --- | --- | --- | --- | --- | --- |
| 1000000            | 242147                  | 1279440          | 0.24215            | 124.86                      | 69.684                   | 140.9                    |

| stave | truth_layer_id | truth_hit_count | expected_edep_mev | dedx_mev_cm | proton_hit_fraction | deuteron_hit_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| B2    | 0              | 371089          | 18.615            | 2.5602      | 0.4954              | 0.39249               |
| B4    | 2              | 175489          | 14.901            | 2.1823      | 0.69215             | 0.20136               |
| B6    | 4              | 100797          | 17.951            | 1.7049      | 0.89521             | 0.008026              |
| B8    | 6              | 69737           | 19.762            | 2.1582      | 0.90195             | 0.0036279             |

| stave | train_pulses | median_odd_charge_adc_sample | truth_expected_edep_mev | truth_dedx_mev_cm | birks_predicted_charge_adc_sample |
| --- | --- | --- | --- | --- | --- |
| B2    | 249681       | 50970                        | 18.615                  | 2.5602            | 49763                             |
| B4    | 8436         | 19021                        | 14.901                  | 2.1823            | 39834                             |
| B6    | 3703         | 16890                        | 17.951                  | 1.7049            | 47988                             |
| B8    | 1447         | 16691                        | 19.762                  | 2.1582            | 52830                             |

## Response-Card Scan

The strong traditional comparator scans a low-dimensional detector-response card on train runs only:

\[ \widehat E_{ij}=E^{\mathrm{even}}_{ij}\,L\,[1+m(s_j-1.5)]\,[1+c\,u_{ij}(1+v_{ij})], \]

where \(E^{\mathrm{even}}_{ij}\) is the even-channel Birks-inverted pulse energy, \(L\) is light-yield scale, \(m\) is a material-depth slope over stave index \(s_j\), \(u\) is ADC saturation excess above 6500 ADC, and \(v\) is a late-peak proxy. The first rows are the best train cards.

| light_yield_scale | material_depth_slope | saturation_smear_correction | train_res68_frac | train_bias_frac |
| --- | --- | --- | --- | --- |
| 1.02              | 0                    | 0.02                        | 0.020327         | 0.0042632       |
| 0.96              | -0.04                | 0.02                        | 0.020837         | 0.0016033       |
| 1.08              | 0.04                 | 0.02                        | 0.021205         | -1.0182e-05     |
| 1                 | -0.02                | 0                           | 0.023956         | 0.0045531       |
| 0.92              | -0.08                | 0                           | 0.024306         | 0.0047193       |
| 0.98              | -0.02                | 0.02                        | 0.024448         | -0.0064197      |
| 1.06              | 0.02                 | 0                           | 0.024461         | 0.0036149       |
| 0.94              | -0.06                | 0.02                        | 0.024546         | 0.0084616       |
| 1.04              | 0.02                 | 0.02                        | 0.024698         | -0.0064513      |
| 0.94              | -0.06                | 0                           | 0.025298         | -0.00089656     |
| 1.02              | 0                    | 0                           | 0.026168         | -0.0046799      |
| 1.06              | 0.02                 | 0.02                        | 0.027312         | 0.012655        |

## ML and Neural Panel

Ridge and gradient-boosted trees receive standardized waveform summaries, per-stave charge/amplitude/peak features, multiplicity, saturation count, pretrigger statistics, and the log response-card prediction. The MLP uses the same tabular representation. The 1D-CNN consumes the four selected even-channel 18-sample waveforms plus tabular features. The new architecture, `waveform_gated_response_cnn`, predicts a multiplicative residual on top of the response-card baseline; its convolution channels are gated by waveform maxima before pooling, then concatenated with tabular features and \(\log E_{\mathrm{card}}\).

No method receives run id, event id, odd charge, odd waveform, or held-out target information as an input. Splits are by run: calibration runs 31--42 and 64 train the models; analysis runs 44--63 and 65 are held out.

## Metrics

The primary residual is \(r=(\widehat E-E_{\mathrm{odd,Birks}})/E_{\mathrm{odd,Birks}}\). The primary score is \(\operatorname{res68}=P_{68}(|r|)\). Confidence intervals resample held-out runs with replacement, preserving whole-run correlations.

## Head-to-Head Results

| method                      | family                       | n      | bias_frac  | res68_frac | res68_ci95                                   | mae_mev | mae_mev_ci95                               |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees      | ml_tree                      | 332852 | -0.0011678 | 0.016135   | [0.01355739654824799, 0.021641595785234544]  | 0.31787 | [0.27588942362858554, 0.38047775591039673] |
| traditional_response_scan   | traditional_response_card    | 332852 | 0.0053264  | 0.021762   | [0.019134222177713642, 0.026408114391088165] | 0.8826  | [0.7445481146165387, 1.1063074855742019]   |
| waveform_gated_response_cnn | new_neural_waveform_response | 332852 | 0.0040642  | 0.027717   | [0.024205184502086342, 0.034551492078083605] | 0.47928 | [0.42791344507985324, 0.5573384437071933]  |
| geant4_birks_lookup         | traditional_geant4_birks     | 332852 | -0.023099  | 0.040244   | [0.03875381586441233, 0.04158657347812534]   | 1.0824  | [0.9600408253376245, 1.2502300276864127]   |
| ridge                       | ml_linear                    | 332852 | 0.016603   | 0.07231    | [0.06084712626357862, 0.09286671264267854]   | 1.0854  | [0.9606877851961897, 1.2564536245913738]   |
| 1d_cnn                      | neural_waveform              | 332852 | 0.01975    | 0.10539    | [0.08591761133702475, 0.14102097470520525]   | 1.4683  | [1.3476625422137998, 1.64766932802878]     |
| mlp                         | neural_tabular               | 332852 | 0.0020608  | 0.11667    | [0.10948217218329336, 0.12553687295320898]   | 1.6848  | [1.526348133205722, 1.801762469535381]     |

## Gate Test

The ticket gate asks for more than 50% divergence reduction relative to `traditional_response_scan`. Reduction is computed as \((R_{\mathrm{trad}}-R_m)/R_{\mathrm{trad}}\), where \(R\) is held-out res68.

| method                      | res68_frac | relative_reduction_vs_traditional_response_scan | clears_50pct_gate |
| --- | --- | --- | --- |
| gradient_boosted_trees      | 0.016135   | 0.25858                                         | False             |
| traditional_response_scan   | 0.021762   | 0                                               | False             |
| waveform_gated_response_cnn | 0.027717   | -0.27364                                        | False             |
| geant4_birks_lookup         | 0.040244   | -0.84927                                        | False             |
| ridge                       | 0.07231    | -2.3228                                         | False             |
| 1d_cnn                      | 0.10539    | -3.8428                                         | False             |
| mlp                         | 0.11667    | -4.3612                                         | False             |

Gate result: **FAIL**. `docs/reports/tuned_params.json` was not updated because the gate did not clear.

## Per-Run Held-Out Checks

| run | method                    | n     | bias_frac   | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | geant4_birks_lookup       | 1911  | -0.01601    | 0.043666   | 1.1384  |
| 44  | traditional_response_scan | 1911  | 0.0066958   | 0.033457   | 1.0105  |
| 44  | gradient_boosted_trees    | 1911  | 0.00027839  | 0.020476   | 0.32502 |
| 45  | geant4_birks_lookup       | 22999 | -0.016559   | 0.044818   | 1.1908  |
| 45  | traditional_response_scan | 22999 | 0.0075153   | 0.037132   | 1.0672  |
| 45  | gradient_boosted_trees    | 22999 | -0.00067215 | 0.019389   | 0.30366 |
| 46  | geant4_birks_lookup       | 676   | -0.011277   | 0.034423   | 0.82479 |
| 46  | traditional_response_scan | 676   | 0.011827    | 0.033113   | 0.77275 |
| 46  | gradient_boosted_trees    | 676   | 3.4616e-05  | 0.01545    | 0.21637 |
| 47  | geant4_birks_lookup       | 5160  | -0.012258   | 0.036798   | 0.87289 |
| 47  | traditional_response_scan | 5160  | 0.011237    | 0.033154   | 0.79812 |
| 47  | gradient_boosted_trees    | 5160  | -0.00034772 | 0.01562    | 0.22662 |
| 48  | geant4_birks_lookup       | 13175 | -0.014263   | 0.042511   | 1.1565  |
| 48  | traditional_response_scan | 13175 | 0.0070021   | 0.033757   | 1.0529  |
| 48  | gradient_boosted_trees    | 13175 | 0.00034724  | 0.020802   | 0.29686 |
| 49  | geant4_birks_lookup       | 13921 | -0.014634   | 0.042712   | 1.1535  |
| 49  | traditional_response_scan | 13921 | 0.0069805   | 0.033713   | 1.0443  |
| 49  | gradient_boosted_trees    | 13921 | 5.7282e-05  | 0.020432   | 0.2882  |
| 50  | geant4_birks_lookup       | 34254 | -0.030699   | 0.041935   | 0.93495 |
| 50  | traditional_response_scan | 34254 | 0.0080466   | 0.023567   | 0.67585 |
| 50  | gradient_boosted_trees    | 34254 | -0.0026676  | 0.01258    | 0.27949 |
| 51  | geant4_birks_lookup       | 14294 | -0.028749   | 0.041787   | 0.96589 |
| 51  | traditional_response_scan | 14294 | 0.0074008   | 0.024204   | 0.74438 |
| 51  | gradient_boosted_trees    | 14294 | -0.0021572  | 0.012751   | 0.27229 |
| 52  | geant4_birks_lookup       | 6933  | -0.029471   | 0.042114   | 0.9845  |
| 52  | traditional_response_scan | 6933  | 0.0073979   | 0.024784   | 0.74843 |
| 52  | gradient_boosted_trees    | 6933  | -0.0023693  | 0.013261   | 0.28851 |
| 53  | geant4_birks_lookup       | 31382 | -0.03134    | 0.038843   | 0.79433 |
| 53  | traditional_response_scan | 31382 | 0.0010499   | 0.015514   | 0.45077 |
| 53  | gradient_boosted_trees    | 31382 | -0.0023647  | 0.010599   | 0.22803 |
| 54  | geant4_birks_lookup       | 29664 | -0.031314   | 0.038649   | 0.79364 |
| 54  | traditional_response_scan | 29664 | 0.0010032   | 0.015406   | 0.44735 |
| 54  | gradient_boosted_trees    | 29664 | -0.0023691  | 0.010601   | 0.22545 |
| 55  | geant4_birks_lookup       | 16836 | -0.028356   | 0.04105    | 0.93331 |
| 55  | traditional_response_scan | 16836 | 0.0069832   | 0.022783   | 0.7078  |
| 55  | gradient_boosted_trees    | 16836 | -0.0023417  | 0.013005   | 0.26782 |
| 56  | geant4_birks_lookup       | 38925 | -0.028246   | 0.041111   | 0.92162 |
| 56  | traditional_response_scan | 38925 | 0.0092597   | 0.026871   | 0.73363 |
| 56  | gradient_boosted_trees    | 38925 | -0.002585   | 0.012792   | 0.28339 |
| 57  | geant4_birks_lookup       | 12928 | -0.014611   | 0.042123   | 1.1283  |
| 57  | traditional_response_scan | 12928 | 0.0068082   | 0.032873   | 1.0231  |
| 57  | gradient_boosted_trees    | 12928 | -7.1384e-05 | 0.020885   | 0.28662 |
| 58  | geant4_birks_lookup       | 15919 | -0.024967   | 0.033514   | 0.6068  |
| 58  | traditional_response_scan | 15919 | -0.0036607  | 0.013571   | 0.33411 |
| 58  | gradient_boosted_trees    | 15919 | -8.6507e-05 | 0.014114   | 0.21536 |
| 59  | geant4_birks_lookup       | 13861 | -0.013866   | 0.053002   | 1.8349  |
| 59  | traditional_response_scan | 13861 | 0.0062098   | 0.04565    | 1.7568  |
| 59  | gradient_boosted_trees    | 13861 | 0.0045351   | 0.041696   | 0.61702 |
| 60  | geant4_birks_lookup       | 10133 | -0.016478   | 0.045836   | 1.9186  |
| 60  | traditional_response_scan | 10133 | 0.003447    | 0.028491   | 1.7767  |
| 60  | gradient_boosted_trees    | 10133 | 0.0024857   | 0.037975   | 0.60054 |
| 61  | geant4_birks_lookup       | 11287 | -0.017002   | 0.044202   | 1.8197  |
| 61  | traditional_response_scan | 11287 | 0.0030026   | 0.026879   | 1.6718  |
| 61  | gradient_boosted_trees    | 11287 | 0.00288     | 0.037872   | 0.56786 |
| 62  | geant4_birks_lookup       | 11911 | -0.015066   | 0.04273    | 1.7267  |
| 62  | traditional_response_scan | 11911 | 0.0049156   | 0.027185   | 1.6128  |
| 62  | gradient_boosted_trees    | 11911 | 0.0034782   | 0.037405   | 0.55241 |
| 63  | geant4_birks_lookup       | 14779 | -0.015012   | 0.03812    | 1.3685  |
| 63  | traditional_response_scan | 14779 | 0.005068    | 0.01934    | 1.2429  |
| 63  | gradient_boosted_trees    | 14779 | 0.0025452   | 0.02757    | 0.43783 |
| 65  | geant4_birks_lookup       | 11904 | -0.014147   | 0.031534   | 0.9414  |
| 65  | traditional_response_scan | 11904 | 0.005697    | 0.016757   | 0.84266 |
| 65  | gradient_boosted_trees    | 11904 | 0.0032535   | 0.023221   | 0.2418  |

## Leakage and Systematics

| check                                    | value                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | pass  |
| --- | --- | --- |
| train_heldout_run_overlap                | []                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | True  |
| raw_reproduction_exact                   | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | True  |
| features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction,log_traditional_response_scan,pretrigger_mean,pretrigger_std,tail_charge_fraction,mean_halfheight_width,max_halfheight_width,deep_minus_shallow_charge_asymmetry | True  |
| cnn_status                               | trained                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | True  |
| waveform_gated_response_cnn_status       | trained                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | True  |
| requested_prior_artifact_present         | reports/1781212364.2054485.44255c27__g4_04_response_tuning                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | False |
| truth_root_used                          | /home/billy/ccb-geant4/output_krakow_1M.root                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | True  |
| truth_layers_mapped_to_even_b_staves     | B2->0,B4->2,B6->4,B8->6                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | True  |

## Caveats

Dominant caveats are the absent exact G4-04 predecessor directory in this checkout, the non-event-aligned GEANT4-to-real-data bridge, the use of duplicate odd readout as the closure target, possible optical/electronics response mismatches not modeled by `Sci_bar_EDep`, and limited CPU/GPU training budgets for neural methods. The response-card search is deliberately low-dimensional; a full digitizer with pedestal, time sampling, threshold, saturation, and optical transport would be needed before claiming detector-response closure in absolute simulation space.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The response-card traditional baseline achieved res68=0.02176. The held-out winner was gradient_boosted_trees with res68=0.01613, a 25.9% reduction relative to the response-card baseline. The 50% gate therefore did not clear.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_followup_1783692400_14526_10306e70_waveform_response_tuning.py --config configs/g4_followup_1783692400_14526_10306e70_waveform_response_tuning.yaml
```

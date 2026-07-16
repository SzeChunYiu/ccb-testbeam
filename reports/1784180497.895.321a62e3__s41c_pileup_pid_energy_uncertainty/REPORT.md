# S41c: Pile-up-aware PID and energy uncertainty calibration

## Abstract

This study claims ticket `1784180497.895.321a62e3`.  The raw `h101/HRDv` B-stack ROOT scan reproduces **640,737** selected pulses, exactly matching the S00 count.  A GEANT4/Birks duplicate-readout closure is benchmarked against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pile-up transformer with quantile heads.  Splits are by run and 95% confidence intervals resample held-out runs.  The winner named in `result.json` is **traditional_template_birks**, with composite loss 0.05365, energy res68 0.04025, interval coverage 0.88957, and weak-label PID ROC AUC 0.99703.

## Reproduction from raw ROOT

For event `e`, channel `c`, and sample `s`, the pedestal is `b_ec = median(HRDv_ecs, s in {0,1,2,3})`.  The corrected waveform is `x_ecs = HRDv_ecs - b_ec`.  B2/B4/B6/B8 are physical even channels 0/2/4/6, and a pulse is selected when `max_s x_ecs > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulses | 640,737 | 640,737 | +0 | true |

## Run inventory and pile-up proxy

Pile-up support is represented by selected-stave multiplicity, a binary multi-stave overlap flag, late charge fraction, saturation count, and per-stave waveform samples.  These are proxies for overlapping pulses because the real HRD files do not contain injected pile-up truth.

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

## Energy target and traditional method

The duplicate odd readout is used only as a closure target.  A range table is formed from the GEANT4 stopping-power file as `R(E)=int_0^E (dE/dx)^(-1)dE`.  With the nominal B-stave centers, a train-run Birks calibration fits

`Q_i = alpha DeltaE_i / (1 + kB (dE/dx)_i)`.

The strong traditional energy comparator inverts this expression for even charges and sums selected staves per event.  The traditional PID comparator is a Gaussian likelihood ratio on the even-readout charge-depth-pileup coordinate, with parameters fitted only on train runs.

| stave | center_cm | residual_energy_mev | dedx_mev_cm | expected_edep_mev |
| --- | --- | --- | --- | --- |
| B2    | 2         | 182.28              | 3.9065      | 3.9032            |
| B4    | 6         | 166.2               | 4.1477      | 4.1437            |
| B6    | 10        | 148.97              | 4.5199      | 4.5152            |
| B8    | 14        | 130.03              | 4.9817      | 4.9831            |

## Learned models

All learned methods exclude run number, event identifiers, odd readout charge, and duplicate-readout labels from inputs.  Ridge and gradient-boosted trees use engineered even-readout topology and waveform summaries.  The MLP uses the same tabular matrix.  The 1D-CNN consumes four selected B-stave waveforms plus tabular features.  The new architecture is a pile-up transformer: each selected-stave waveform is embedded as a token, a one-layer self-attention encoder mixes stave tokens, and three quantile heads estimate 5%, 50%, and 95% log-energy.  Its point prediction is the median head and its interval is the direct quantile interval.

## Metrics

The primary energy score is `res68 = percentile_68(|(Ehat-Eodd)/Eodd|)`.  Bias is the median fractional residual.  Conformal intervals for non-quantile models use the train-run absolute residual quantile at nominal 90% coverage.  The PID score is ROC AUC on the held-out weak labels.  The composite ranking minimizes `res68 + |coverage-0.90| + (1-AUC_PID)` among methods with both endpoints.

## Energy benchmark

| method                          | family                                | n      | res68_frac | res68_ci95                                 | bias_frac  | coverage | coverage_ci95                            | mae_mev |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees          | ml_tree                               | 332852 | 0.036483   | [0.03178121179776639, 0.04489487064409587] | -0.0093394 | 0.86803  | [0.835889474631727, 0.8916410131280755]  | 0.15926 |
| traditional_template_birks      | traditional_template_likelihood_birks | 332852 | 0.040248   | [0.03888449205648855, 0.04178609239424126] | -0.023105  | 0.88957  | [0.852772107239899, 0.9174148792957014]  | 0.22821 |
| pileup_transformer_quantile_new | neural_attention_quantile             | 332852 | 0.070875   | [0.05724660692463909, 0.09648241993032777] | 0.018004   | 0.8722   | [0.8587507418313037, 0.882675237052157]  | 0.24016 |
| 1d_cnn                          | neural_waveform                       | 332852 | 0.095887   | [0.07621763301728846, 0.13637479701973473] | -0.028909  | 0.86534  | [0.8276237164034558, 0.8975057548385572] | 0.31638 |
| ridge                           | ml_linear                             | 332852 | 0.10074    | [0.08991528899051876, 0.12377972478535391] | -0.021923  | 0.86369  | [0.8222719720020453, 0.8939907067017285] | 0.29979 |
| mlp                             | neural_tabular                        | 332852 | 0.10755    | [0.09518398257451989, 0.13136797320455187] | -0.047474  | 0.86493  | [0.8319296016861712, 0.8905818794652377] | 0.36295 |

## PID benchmark

| method                          | n      | roc_auc | roc_auc_ci95                             | average_precision | balanced_accuracy | balanced_accuracy_ci95                   | tn     | fp   | fn  | tp     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees          | 249408 | 0.99989 | [0.9998413368465312, 0.9999276866482663] | 0.99976           | 0.99841           | [0.9980528179110264, 0.9986897702296736] | 131541 | 326  | 83  | 117458 |
| pileup_transformer_quantile_new | 249408 | 0.99985 | [0.9997897338108246, 0.9998861833334824] | 0.99914           | 0.99833           | [0.9980359913503513, 0.9985791536715845] | 131468 | 399  | 38  | 117503 |
| 1d_cnn                          | 249408 | 0.99948 | [0.9994068741067554, 0.9995720399140484] | 0.99839           | 0.99724           | [0.9967774222595284, 0.9976496084737132] | 131192 | 675  | 48  | 117493 |
| mlp                             | 249408 | 0.99935 | [0.9992361487570949, 0.9994585061705274] | 0.9982            | 0.99704           | [0.996551200847766, 0.9974860986475614]  | 131130 | 737  | 38  | 117503 |
| ridge                           | 249408 | 0.99927 | [0.9991093949317047, 0.9994119032032296] | 0.99787           | 0.99693           | [0.9965076401210596, 0.9973929836994389] | 131104 | 763  | 41  | 117500 |
| traditional_template_birks      | 249408 | 0.99703 | [0.9962471704499987, 0.9975815429889301] | 0.99368           | 0.99276           | [0.9913967008973391, 0.9937345599055496] | 130548 | 1319 | 527 | 117014 |

## Pile-up strata and systematics

| stratum                  | method                     | n      | res68_frac | coverage | pid_roc_auc |
| --- | --- | --- | --- | --- | --- |
| single_pulse_proxy       | traditional_template_birks | 305087 | 0.03914    | 0.92155  | 0.99654     |
| multi_stave_pileup_proxy | traditional_template_birks | 27765  | 0.12598    | 0.53816  | 0.99861     |
| unsaturated              | traditional_template_birks | 226635 | 0.033522   | 0.88077  | 0.99852     |
| saturated                | traditional_template_birks | 106217 | 0.048498   | 0.90834  | 0.85597     |

Important systematics are explicit: the MeV scale is conditional on B-stave geometry and duplicate-readout closure; PID is weak-label, not species truth; multi-stave multiplicity is a pile-up proxy and not a resolved two-pulse truth label; saturation can bias both even and odd charge; and bootstrap CIs are run-block intervals, so they quantify run-to-run variation but not all detector-model uncertainty.

## Leakage checks

| check                                  | value                                                                                                                                                                                                                                                                           | pass |
| --- | --- | --- |
| raw_reproduction_exact                 | 640737 of 640737                                                                                                                                                                                                                                                                | True |
| train_heldout_run_overlap              | []                                                                                                                                                                                                                                                                              | True |
| features_exclude_run_event_odd_readout | multiplicity,pileup_proxy,depth_idx,even_total_charge,even_max_amp,saturated_count,late_fraction,log_charge_B0,log_charge_B1,log_charge_B2,log_charge_B3,log_amp_B0,log_amp_B1,log_amp_B2,log_amp_B3,hit_B0,hit_B1,hit_B2,hit_B3,peak_B0,peak_B1,peak_B2,peak_B3,early_fraction | True |
| pid_truth_branch_absent                | h101 branches used: EVENTNO,EVT,HRDv; no species/PID truth                                                                                                                                                                                                                      | True |
| nominal_interval_level                 | 0.9                                                                                                                                                                                                                                                                             | True |

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses.  The held-out run-block benchmark winner is traditional_template_birks with energy res68=0.04025, coverage=0.88957, and weak-label PID ROC AUC=0.99703.  The conclusion is a pile-up-aware calibration closure result, not a hidden species-truth PID claim.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.py --config configs/s41c_1784180497_895_321a62e3_pileup_pid_energy_uncertainty.yaml
```

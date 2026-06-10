# S14d: saturated charge correction acceptance bands

## Abstract

Raw B-stack ROOT reproduction passes exactly at 640,737 selected pulses. The primary held-out saturated-event winner is **gradient_boosted_trees** with energy-proxy res68 0.01828 and run-bootstrap 95% CI [0.017168, 0.020764]. Acceptance bands compare saturated rows to unsaturated controls matched by current family, run, and depth, then aggregate by current/depth/saturated-stave with run-block bootstrap intervals.

## 0. Question

When a selected B-stack event contains saturated even-readout charge, under which run/depth/stave/current conditions should a saturation correction be applied rather than leaving observed charge untouched?

## 1. Reproduction Gate

The first operation rebuilds selected B2/B4/B6/B8 pulses directly from raw `HRDv`: median samples 0--3 define the baseline and the gate is peak amplitude above 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|:---|
| S14c/S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | 0 | true |

## 2. Methods

The closure target is the same-event odd duplicate readout, restricted to valid positive charge. This target is not external calorimetry; it tests whether even-channel saturation correction is self-consistent under run-disjoint calibration.

For each event and method, charge is mapped to a monotonic range-energy proxy by a train-only depth-charge quantile map. If \(Q\) is corrected even charge and depth is \(d\), the score uses \(\hat E=f_d(\log Q)\), where \(f_d\) maps train-run charge quantiles onto the PSTAR depth bin \([E_{d,lo},E_{d,hi}]\). The target is the analogous \(E=f_d(\log Q_{odd})\).

Traditional rising-edge correction uses train-run amplitude-binned median templates. For a saturated pulse, unclipped samples are fit by a shifted normalized template and the recovered amplitude rescales the template charge. The P07/P04 method first learns artificial fixed-ceiling amplitude recovery from train-run clean pulses, then predicts duplicate odd charge from even waveform features. Additional ML/NN comparators are ridge regression, gradient-boosted trees, tabular MLP, 1D-CNN over the four B-stave waveforms, and a template-residual MLP that learns a multiplicative correction to the traditional template estimate.

The pre-registered primary metric is saturated held-out energy-proxy res68, the 68th percentile of \(|(\hat E-E)/E|\), with 95% CIs from held-out-run bootstrap. Secondary diagnostics are bias, full RMS, MAE, and tails beyond 10% and 25%.

## 3. Head-to-Head Benchmark

| method                         | family                           | n_saturated | saturated_bias_frac | saturated_energy_res68 | saturated_energy_res68_ci95 | saturated_full_rms_frac | saturated_tail_gt25pct | all_heldout_energy_res68 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees         | ml_tree                          | 106217      | -0.0017659          | 0.018277               | [0.017168, 0.020764]        | 0.046337                | 0.0058183              | 0.013138                 |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 106217      | 0                   | 0.026961               | [0.026353, 0.028122]        | 0.055179                | 0.0083508              | 0.020523                 |
| mlp                            | neural_tabular                   | 106217      | -0.015136           | 0.04599                | [0.04359, 0.049833]         | 0.077906                | 0.0078613              | 0.032031                 |
| ridge                          | ml_linear                        | 106217      | -0.0069886          | 0.052323               | [0.051066, 0.054833]        | 0.068421                | 0.010055               | 0.046076                 |
| 1d_cnn                         | neural_waveform                  | 106217      | -0.025377           | 0.15065                | [0.14455, 0.16296]          | 0.1719                  | 0.16958                | 0.098942                 |
| observed_even_charge           | traditional_observed             | 106217      | -0.37672            | 0.39784                | [0.39082, 0.40225]          | 0.36976                 | 0.95762                | 0.29853                  |
| traditional_template_corrected | traditional_rising_edge_template | 106217      | -0.37672            | 0.39784                | [0.39168, 0.40196]          | 0.36981                 | 0.95899                | 0.29858                  |
| template_residual_mlp          | neural_template_residual         | 106217      | -0.37672            | 0.39784                | [0.39135, 0.40247]          | 0.36981                 | 0.95899                | 0.29858                  |

The named S14c correction families on the same saturated held-out rows are:

| method                         | family                           | n_saturated | saturated_energy_res68 | saturated_energy_res68_ci95 | saturated_charge_res68 | traditional_worsens_observed |
| --- | --- | --- | --- | --- | --- | --- |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 106217      | 0.026961               | [0.026353, 0.028122]        | 0.54353                | False                        |
| observed_even_charge           | traditional_observed             | 106217      | 0.39784                | [0.39082, 0.40225]          | 2.7676e+298            | False                        |
| traditional_template_corrected | traditional_rising_edge_template | 106217      | 0.39784                | [0.39168, 0.40196]          | 1.7986e+273            | False                        |

## 4. Acceptance Bands

A band is accepted when its saturated-event res68 is no more than `acceptance_margin_res68` above matched unsaturated controls. Controls are matched within held-out run, current family, and depth stave; the aggregate CI resamples held-out runs.

| current_family | depth_stave | saturated_stave | method                 | n_saturated | n_runs | saturated_energy_res68 | saturated_energy_res68_ci95 | matched_unsat_energy_res68 | sat_minus_unsat_res68 | accepted_with_margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_20nA      | B8          | B2              | gradient_boosted_trees | 354         | 19     | 0.0077467              | [0.0074106, 0.0088301]      | 0.0063888                  | 0.0013579             | True                 |
| high_20nA      | B8          | B2              | p07_p04_corrected      | 354         | 19     | 0.0093687              | [0.007652, 0.010758]        | 0.0067328                  | 0.0026359             | True                 |
| high_20nA      | B6          | B2              | gradient_boosted_trees | 703         | 19     | 0.0094421              | [0.0086898, 0.010392]       | 0.0074045                  | 0.0020376             | True                 |
| high_20nA      | B4          | B4              | gradient_boosted_trees | 73          | 16     | 0.010985               | [0.0074264, 0.016549]       | 0.012568                   | -0.0015837            | True                 |
| high_20nA      | B6          | B2              | p07_p04_corrected      | 703         | 19     | 0.011019               | [0.009448, 0.01232]         | 0.0098946                  | 0.0011247             | True                 |
| high_20nA      | B4          | B2              | gradient_boosted_trees | 1564        | 19     | 0.015425               | [0.014419, 0.01677]         | 0.014705                   | 0.00072002            | True                 |
| high_20nA      | B4          | B4              | p07_p04_corrected      | 73          | 16     | 0.016674               | [0.012631, 0.026152]        | 0.017351                   | -0.00067629           | True                 |
| high_20nA      | B2          | B2              | gradient_boosted_trees | 102060      | 19     | 0.018346               | [0.017148, 0.021071]        | 0.01353                    | 0.0048162             | True                 |
| low_2nA        | B2          | B2              | gradient_boosted_trees | 1389        | 2      | 0.023598               | [0.023598, 0.026107]        | 0.0089842                  | 0.014614              | True                 |
| high_20nA      | B4          | B2              | p07_p04_corrected      | 1564        | 19     | 0.026254               | [0.024602, 0.027521]        | 0.016204                   | 0.010051              | True                 |
| high_20nA      | B2          | B2              | p07_p04_corrected      | 102060      | 19     | 0.0271                 | [0.026572, 0.028243]        | 0.02055                    | 0.00655               | True                 |
| low_2nA        | B2          | B2              | p07_p04_corrected      | 1389        | 2      | 0.027253               | [0.026718, 0.031368]        | 0.013429                   | 0.013824              | True                 |

## 5. Per-Run Diagnostics

| run | current_family | method                         | n_saturated | saturated_energy_res68 | saturated_charge_res68 |
| --- | --- | --- | --- | --- | --- |
| 44  | high_20nA      | observed_even_charge           | 334         | 0.39556                | 2.7991e+298            |
| 44  | high_20nA      | traditional_template_corrected | 334         | 0.39556                | 1.8188e+273            |
| 44  | high_20nA      | p07_p04_corrected              | 334         | 0.029063               | 0.5489                 |
| 44  | high_20nA      | gradient_boosted_trees         | 334         | 0.027419               | 0.069368               |
| 45  | high_20nA      | observed_even_charge           | 5472        | 0.40663                | 2.7635e+298            |
| 45  | high_20nA      | traditional_template_corrected | 5472        | 0.40663                | 1.7962e+273            |
| 45  | high_20nA      | p07_p04_corrected              | 5472        | 0.027697               | 0.55174                |
| 45  | high_20nA      | gradient_boosted_trees         | 5472        | 0.023598               | 0.072653               |
| 46  | low_2nA        | observed_even_charge           | 144         | 0.40663                | 2.7537e+298            |
| 46  | low_2nA        | traditional_template_corrected | 144         | 0.40663                | 1.7893e+273            |
| 46  | low_2nA        | p07_p04_corrected              | 144         | 0.030488               | 0.54923                |
| 46  | low_2nA        | gradient_boosted_trees         | 144         | 0.02473                | 0.07251                |
| 47  | low_2nA        | observed_even_charge           | 1268        | 0.40704                | 2.7731e+298            |
| 47  | low_2nA        | traditional_template_corrected | 1268        | 0.40704                | 1.8019e+273            |
| 47  | low_2nA        | p07_p04_corrected              | 1268        | 0.026671               | 0.54971                |
| 47  | low_2nA        | gradient_boosted_trees         | 1268        | 0.023598               | 0.06542                |
| 48  | high_20nA      | observed_even_charge           | 1991        | 0.3965                 | 2.8064e+298            |
| 48  | high_20nA      | traditional_template_corrected | 1991        | 0.3965                 | 1.8254e+273            |
| 48  | high_20nA      | p07_p04_corrected              | 1991        | 0.032321               | 0.54659                |
| 48  | high_20nA      | gradient_boosted_trees         | 1991        | 0.027108               | 0.067902               |
| 49  | high_20nA      | observed_even_charge           | 2154        | 0.39867                | 2.8028e+298            |
| 49  | high_20nA      | traditional_template_corrected | 2154        | 0.39867                | 1.8218e+273            |
| 49  | high_20nA      | p07_p04_corrected              | 2154        | 0.031675               | 0.548                  |
| 49  | high_20nA      | gradient_boosted_trees         | 2154        | 0.02795                | 0.070567               |
| 50  | high_20nA      | observed_even_charge           | 19492       | 0.40413                | 2.7372e+298            |
| 50  | high_20nA      | traditional_template_corrected | 19492       | 0.40413                | 1.7786e+273            |
| 50  | high_20nA      | p07_p04_corrected              | 19492       | 0.025927               | 0.54722                |
| 50  | high_20nA      | gradient_boosted_trees         | 19492       | 0.01748                | 0.056246               |
| 51  | high_20nA      | observed_even_charge           | 7248        | 0.40231                | 2.7489e+298            |
| 51  | high_20nA      | traditional_template_corrected | 7248        | 0.40231                | 1.7863e+273            |
| 51  | high_20nA      | p07_p04_corrected              | 7248        | 0.027127               | 0.54579                |
| 51  | high_20nA      | gradient_boosted_trees         | 7248        | 0.01805                | 0.054356               |
| 52  | high_20nA      | observed_even_charge           | 3625        | 0.40162                | 2.7503e+298            |
| 52  | high_20nA      | traditional_template_corrected | 3625        | 0.40162                | 1.7873e+273            |
| 52  | high_20nA      | p07_p04_corrected              | 3625        | 0.026833               | 0.54516                |
| 52  | high_20nA      | gradient_boosted_trees         | 3625        | 0.018549               | 0.053871               |
| 53  | high_20nA      | observed_even_charge           | 13961       | 0.38746                | 2.7886e+298            |
| 53  | high_20nA      | traditional_template_corrected | 13961       | 0.38746                | 1.812e+273             |
| 53  | high_20nA      | p07_p04_corrected              | 13961       | 0.025851               | 0.5359                 |
| 53  | high_20nA      | gradient_boosted_trees         | 13961       | 0.015283               | 0.039596               |
| 54  | high_20nA      | observed_even_charge           | 13282       | 0.38732                | 2.7919e+298            |
| 54  | high_20nA      | traditional_template_corrected | 13282       | 0.38732                | 1.8141e+273            |
| 54  | high_20nA      | p07_p04_corrected              | 13282       | 0.025525               | 0.53579                |
| 54  | high_20nA      | gradient_boosted_trees         | 13282       | 0.015147               | 0.039627               |
| 55  | high_20nA      | observed_even_charge           | 8330        | 0.39832                | 2.7617e+298            |
| 55  | high_20nA      | traditional_template_corrected | 8330        | 0.39832                | 1.7945e+273            |
| 55  | high_20nA      | p07_p04_corrected              | 8330        | 0.026728               | 0.54281                |
| 55  | high_20nA      | gradient_boosted_trees         | 8330        | 0.01748                | 0.049528               |
| 56  | high_20nA      | observed_even_charge           | 21645       | 0.4029                 | 2.742e+298             |
| 56  | high_20nA      | traditional_template_corrected | 21645       | 0.4029                 | 1.7817e+273            |
| 56  | high_20nA      | p07_p04_corrected              | 21645       | 0.027248               | 0.54598                |
| 56  | high_20nA      | gradient_boosted_trees         | 21645       | 0.018533               | 0.05477                |
| 57  | high_20nA      | observed_even_charge           | 1843        | 0.39535                | 2.8139e+298            |
| 57  | high_20nA      | traditional_template_corrected | 1843        | 0.39535                | 1.8303e+273            |
| 57  | high_20nA      | p07_p04_corrected              | 1843        | 0.033111               | 0.54767                |
| 57  | high_20nA      | gradient_boosted_trees         | 1843        | 0.026928               | 0.071513               |
| 58  | high_20nA      | observed_even_charge           | 1618        | 0.37688                | 2.8519e+298            |
| 58  | high_20nA      | traditional_template_corrected | 1618        | 0.37688                | 1.8539e+273            |
| 58  | high_20nA      | p07_p04_corrected              | 1618        | 0.029469               | 0.53346                |
| 58  | high_20nA      | gradient_boosted_trees         | 1618        | 0.022864               | 0.043912               |
| 59  | high_20nA      | observed_even_charge           | 809         | 0.36694                | 2.8313e+298            |
| 59  | high_20nA      | traditional_template_corrected | 809         | 0.36694                | 1.8441e+273            |
| 59  | high_20nA      | p07_p04_corrected              | 809         | 0.041334               | 0.59456                |
| 59  | high_20nA      | gradient_boosted_trees         | 809         | 0.035709               | 0.17414                |
| 60  | high_20nA      | observed_even_charge           | 382         | 0.35178                | 2.8929e+298            |
| 60  | high_20nA      | traditional_template_corrected | 382         | 0.35178                | 1.8909e+273            |
| 60  | high_20nA      | p07_p04_corrected              | 382         | 0.044099               | 0.54109                |
| 60  | high_20nA      | gradient_boosted_trees         | 382         | 0.033702               | 0.08226                |
| 61  | high_20nA      | observed_even_charge           | 420         | 0.36086                | 2.8982e+298            |
| 61  | high_20nA      | traditional_template_corrected | 420         | 0.36086                | 1.887e+273             |
| 61  | high_20nA      | p07_p04_corrected              | 420         | 0.039836               | 0.539                  |
| 61  | high_20nA      | gradient_boosted_trees         | 420         | 0.032386               | 0.073327               |
| 62  | high_20nA      | observed_even_charge           | 513         | 0.36756                | 2.8678e+298            |
| 62  | high_20nA      | traditional_template_corrected | 513         | 0.36756                | 1.8674e+273            |
| 62  | high_20nA      | p07_p04_corrected              | 513         | 0.04308                | 0.55923                |
| 62  | high_20nA      | gradient_boosted_trees         | 513         | 0.035869               | 0.14668                |
| 63  | high_20nA      | observed_even_charge           | 1232        | 0.37177                | 2.8263e+298            |
| 63  | high_20nA      | traditional_template_corrected | 1232        | 0.37177                | 1.8374e+273            |
| 63  | high_20nA      | p07_p04_corrected              | 1232        | 0.032765               | 0.55687                |
| 63  | high_20nA      | gradient_boosted_trees         | 1232        | 0.025962               | 0.11166                |

## 6. Geometry/Systematic Envelope

The explicit S14c-style warning is the `traditional_worsens_observed` flag: the rising-edge template correction is worse than observed charge for the same geometry and saturated held-out rows.

| geometry   | method                         | saturated_energy_res68 | saturated_energy_res68_ci95 | traditional_minus_observed_res68 | traditional_worsens_observed |
| --- | --- | --- | --- | --- | --- |
| center_4cm | observed_even_charge           | 0.39784                | [0.39269, 0.40229]          | 0                                | False                        |
| center_4cm | traditional_template_corrected | 0.39784                | [0.39241, 0.40209]          | 0                                | False                        |
| center_4cm | p07_p04_corrected              | 0.026961               | [0.026403, 0.028061]        | 0                                | False                        |
| center_4cm | gradient_boosted_trees         | 0.018277               | [0.01677, 0.02037]          | 0                                | False                        |
| center_2cm | observed_even_charge           | 0.37271                | [0.36769, 0.37705]          | 0                                | False                        |
| center_2cm | traditional_template_corrected | 0.37271                | [0.36741, 0.37686]          | 0                                | False                        |
| center_2cm | p07_p04_corrected              | 0.025224               | [0.024707, 0.026273]        | 0                                | False                        |
| center_2cm | gradient_boosted_trees         | 0.017077               | [0.015674, 0.019055]        | 0                                | False                        |
| zero_4cm   | observed_even_charge           | 0.69256                | [0.68736, 0.69647]          | -4.4511e-05                      | False                        |
| zero_4cm   | traditional_template_corrected | 0.69251                | [0.68667, 0.69656]          | -4.4511e-05                      | False                        |
| zero_4cm   | p07_p04_corrected              | 0.047767               | [0.046804, 0.050313]        | -4.4511e-05                      | False                        |
| zero_4cm   | gradient_boosted_trees         | 0.032723               | [0.030423, 0.036908]        | -4.4511e-05                      | False                        |

Rows where the traditional template worsens observed charge:

| geometry | method | saturated_energy_res68 | traditional_minus_observed_res68 | traditional_worsens_observed |
| --- | --- | --- | --- | --- |

## 7. Leakage and Caveats

| check                                        | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                    | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                       | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| train_heldout_event_key_overlap              | 0                                                                                                                                                                                                                                                                                                                                                                | True |
| ml_features_exclude_odd_charge_run_event_ids | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                   | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| shuffled_p04_unsaturated_charge_res68        | 0.514099                                                                                                                                                                                                                                                                                                                                                         | True |

The main caveat is target scope: duplicate odd-readout closure is an electronics self-consistency test, not deposited-energy truth. The PSTAR/depth map supplies an ordering proxy, while Birks quenching, material budget, geometry, and particle identity remain external systematics. Current labels use the documented low-current runs 46--47 versus the otherwise high-current B-stack runs; Sample-II runs are treated as high-current for this acceptance audit.

## 8. Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. On saturated held-out events, the winner is gradient_boosted_trees with energy-proxy res68 0.01828 [0.017168, 0.020764]. The strong traditional rising-edge template has res68 0.39784, observed charge has 0.39784, so traditional template correction does not worsen the nominal saturated geometry proxy. Accepted current/depth/stave bands at margin 0.020: 12. Traditional-worsening geometries: []. The result is an odd-readout closure and range-order proxy; it does not establish absolute deposited-energy truth.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14d_1781033028_1769_29f13a58_saturation_acceptance_bands.py --config configs/s14d_1781033028_1769_29f13a58_saturation_acceptance_bands.yaml
```

Artifacts: `result.json`, `manifest.json`, `method_metrics.csv`, `acceptance_bands.csv`, `per_run_acceptance.csv`, `geometry_systematics.csv`, `leakage_checks.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, and `fig_s14d_saturated_res68.png`.

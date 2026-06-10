# S14f: saturation energy-ordering geometry stress map

## Abstract

Raw B-stack ROOT reproduction passes exactly at 640,737 selected pulses. The geometry-stress winner is **gradient_boosted_trees** with worst-geometry saturated energy-proxy res68 0.03272. The nominal center-4cm res68 is 0.01828 with run-bootstrap 95% CI [0.017168, 0.020764]. Support-bin tables expose depth-order inversions, energy-proxy res68, and saturated-minus-unsaturated log-charge deltas across the 2 cm, 4 cm, and zero-offset geometry envelopes.

## 0. Question

Does the S14c saturation-corrected charge proxy preserve energy ordering under the 2 cm, 4 cm, and zero-offset geometry envelopes after saturation, anomaly, and topology support restrictions are applied?

## 1. Reproduction Gate

The first operation rebuilds selected B2/B4/B6/B8 pulses directly from raw `HRDv`: median samples 0--3 define the baseline and the gate is peak amplitude above 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|:---|
| S14c/S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | 0 | true |

## 2. Methods

The closure target is the same-event odd duplicate readout, restricted to valid positive charge. This target is not external calorimetry; it tests whether even-channel saturation correction is self-consistent under run-disjoint calibration.

For each event and method, charge is mapped to a monotonic range-energy proxy by a train-only depth-charge quantile map. If \(Q\) is corrected even charge and depth is \(d\), the score uses \(\hat E=f_d(\log Q)\), where \(f_d\) maps train-run charge quantiles onto the PSTAR depth bin \([E_{d,lo},E_{d,hi}]\). The target is the analogous \(E=f_d(\log Q_{odd})\).

For a held-out support bin \(b\), the main resolution is \(R_{68,b}=P_{68}(|(\hat E-E)/E|)\). The log-charge systematic is \(\Delta_{\log Q,b}=\operatorname{median}_{sat,b}\log(\hat Q/Q_{odd})-\operatorname{median}_{unsat,b}\log(\hat Q/Q_{odd})\), with unsaturated controls matched by run, current family, and depth. The depth-order violation rate is the fraction of adjacent depth-bin median pairs with \(\operatorname{median}(\hat E_{d+1}) < \operatorname{median}(\hat E_d)\). All CIs resample held-out runs with replacement.

Traditional rising-edge correction uses train-run amplitude-binned median templates. For a saturated pulse, unclipped samples are fit by a shifted normalized template and the recovered amplitude rescales the template charge. The P07/P04 method first learns artificial fixed-ceiling amplitude recovery from train-run clean pulses, then predicts duplicate odd charge from even waveform features. Additional ML/NN comparators are ridge regression, gradient-boosted trees, tabular MLP, 1D-CNN over the four B-stave waveforms, and a template-residual MLP that learns a multiplicative correction to the traditional template estimate.

The primary S14f selection metric is worst-geometry saturated energy-proxy res68. Nominal center-4cm saturated res68 is retained for comparison with S14d, while ordering and log-charge deltas are treated as systematics.

## 3. Head-to-Head Benchmark

| method                         | family                           | n_saturated | saturated_bias_frac | saturated_energy_res68 | saturated_energy_res68_ci95 | saturated_full_rms_frac | saturated_tail_gt25pct | all_heldout_energy_res68 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees         | ml_tree                          | 106217      | -0.0017659          | 0.018277               | [0.017168, 0.020764]        | 0.046337                | 0.0058183              | 0.013138                 |
| observed_even_charge           | traditional_observed             | 106217      | -0.0021747          | 0.020494               | [0.018879, 0.025401]        | 0.077203                | 0.012936               | 0.021189                 |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 106217      | 0                   | 0.026961               | [0.026353, 0.028122]        | 0.055179                | 0.0083508              | 0.020523                 |
| template_residual_mlp          | neural_template_residual         | 106217      | -0.0033363          | 0.030224               | [0.028956, 0.033144]        | 0.044392                | 0.0033987              | 0.015253                 |
| mlp                            | neural_tabular                   | 106217      | -0.015136           | 0.04599                | [0.04359, 0.049833]         | 0.077906                | 0.0078613              | 0.032031                 |
| ridge                          | ml_linear                        | 106217      | -0.0069886          | 0.052323               | [0.051066, 0.054833]        | 0.068421                | 0.010055               | 0.046076                 |
| traditional_template_corrected | traditional_rising_edge_template | 106217      | 0.0004913           | 0.08155                | [0.079653, 0.084263]        | 0.096629                | 0.013567               | 0.028894                 |
| 1d_cnn                         | neural_waveform                  | 106217      | -0.025377           | 0.15065                | [0.14455, 0.16296]          | 0.1719                  | 0.16958                | 0.098942                 |

The named S14c correction families on the same saturated held-out rows are:

| method                         | family                           | n_saturated | saturated_energy_res68 | saturated_energy_res68_ci95 | saturated_charge_res68 | traditional_worsens_observed |
| --- | --- | --- | --- | --- | --- | --- |
| observed_even_charge           | traditional_observed             | 106217      | 0.020494               | [0.018879, 0.025401]        | 0.57154                | False                        |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 106217      | 0.026961               | [0.026353, 0.028122]        | 0.56965                | False                        |
| traditional_template_corrected | traditional_rising_edge_template | 106217      | 0.08155                | [0.079653, 0.084263]        | 0.56477                | True                         |

## 4. Geometry Stress Summary

The winner is chosen by the smallest maximum saturated res68 across all geometry envelopes.

| method                         | family                           | worst_geometry_saturated_energy_res68 | best_geometry_saturated_energy_res68 | max_depth_order_violation_rate | max_abs_log_charge_delta |
| --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees         | ml_tree                          | 0.032723                              | 0.017077                             | 0                              | 0.21742                  |
| observed_even_charge           | traditional_observed             | 0.037313                              | 0.019142                             | 0                              | 1.0193                   |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 0.047767                              | 0.025224                             | 0                              | 1.0147                   |
| template_residual_mlp          | neural_template_residual         | 0.054418                              | 0.028234                             | 0                              | 0.082511                 |
| mlp                            | neural_tabular                   | 0.08238                               | 0.043011                             | 0                              | 0.16341                  |
| ridge                          | ml_linear                        | 0.093932                              | 0.048905                             | 0                              | 0.062248                 |
| traditional_template_corrected | traditional_rising_edge_template | 0.14558                               | 0.076251                             | 0                              | 1.0021                   |
| 1d_cnn                         | neural_waveform                  | 0.27838                               | 0.14055                              | 0                              | 0.77595                  |

Per-geometry saturated-event metrics:

| geometry   | method                         | saturated_energy_res68 | saturated_energy_res68_ci95 | traditional_minus_observed_res68 | traditional_worsens_observed |
| --- | --- | --- | --- | --- | --- |
| center_4cm | observed_even_charge           | 0.020494               | [0.018589, 0.02523]         | 0.061056                         | True                         |
| center_4cm | traditional_template_corrected | 0.08155                | [0.079989, 0.084435]        | 0.061056                         | True                         |
| center_4cm | p07_p04_corrected              | 0.026961               | [0.026403, 0.028061]        | 0.061056                         | True                         |
| center_4cm | ridge                          | 0.052323               | [0.051261, 0.05561]         | 0.061056                         | True                         |
| center_4cm | gradient_boosted_trees         | 0.018277               | [0.01677, 0.02037]          | 0.061056                         | True                         |
| center_4cm | mlp                            | 0.04599                | [0.043272, 0.050065]        | 0.061056                         | True                         |
| center_4cm | 1d_cnn                         | 0.15065                | [0.14421, 0.16193]          | 0.061056                         | True                         |
| center_4cm | template_residual_mlp          | 0.030224               | [0.028916, 0.033399]        | 0.061056                         | True                         |
| center_2cm | observed_even_charge           | 0.019142               | [0.017346, 0.023596]        | 0.057109                         | True                         |
| center_2cm | traditional_template_corrected | 0.076251               | [0.074736, 0.078959]        | 0.057109                         | True                         |
| center_2cm | p07_p04_corrected              | 0.025224               | [0.024707, 0.026273]        | 0.057109                         | True                         |
| center_2cm | ridge                          | 0.048905               | [0.04789, 0.051958]         | 0.057109                         | True                         |
| center_2cm | gradient_boosted_trees         | 0.017077               | [0.015674, 0.019055]        | 0.057109                         | True                         |
| center_2cm | mlp                            | 0.043011               | [0.040478, 0.046783]        | 0.057109                         | True                         |
| center_2cm | 1d_cnn                         | 0.14055                | [0.13459, 0.15124]          | 0.057109                         | True                         |
| center_2cm | template_residual_mlp          | 0.028234               | [0.027015, 0.031159]        | 0.057109                         | True                         |
| zero_4cm   | observed_even_charge           | 0.037313               | [0.034788, 0.044863]        | 0.10827                          | True                         |
| zero_4cm   | traditional_template_corrected | 0.14558                | [0.14269, 0.1502]           | 0.10827                          | True                         |
| zero_4cm   | p07_p04_corrected              | 0.047767               | [0.046804, 0.050313]        | 0.10827                          | True                         |
| zero_4cm   | ridge                          | 0.093932               | [0.091705, 0.09921]         | 0.10827                          | True                         |
| zero_4cm   | gradient_boosted_trees         | 0.032723               | [0.030423, 0.036908]        | 0.10827                          | True                         |
| zero_4cm   | mlp                            | 0.08238                | [0.077008, 0.090126]        | 0.10827                          | True                         |
| zero_4cm   | 1d_cnn                         | 0.27838                | [0.26786, 0.29388]          | 0.10827                          | True                         |
| zero_4cm   | template_residual_mlp          | 0.054418               | [0.051873, 0.060191]        | 0.10827                          | True                         |

## 5. Support-Bin Stress Map

A band is accepted when its saturated-event res68 is no more than `acceptance_margin_res68` above matched unsaturated controls. Controls are matched within held-out run, current family, and depth stave; the aggregate CI resamples held-out runs.

| current_family | depth_stave | saturated_stave | method                         | n_saturated | n_runs | saturated_energy_res68 | saturated_energy_res68_ci95 | matched_unsat_energy_res68 | sat_minus_unsat_res68 | accepted_with_margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| high_20nA      | B8          | B2              | gradient_boosted_trees         | 354         | 19     | 0.0077467              | [0.0074106, 0.0088301]      | 0.0063888                  | 0.0013579             | True                 |
| high_20nA      | B8          | B2              | observed_even_charge           | 354         | 19     | 0.0087966              | [0.0077576, 0.0098594]      | 0.0085995                  | 0.00019711            | True                 |
| high_20nA      | B8          | B2              | p07_p04_corrected              | 354         | 19     | 0.0093687              | [0.007652, 0.010758]        | 0.0067328                  | 0.0026359             | True                 |
| high_20nA      | B6          | B2              | gradient_boosted_trees         | 703         | 19     | 0.0094421              | [0.0086898, 0.010392]       | 0.0074045                  | 0.0020376             | True                 |
| high_20nA      | B4          | B4              | gradient_boosted_trees         | 73          | 16     | 0.010985               | [0.0074264, 0.016549]       | 0.012568                   | -0.0015837            | True                 |
| high_20nA      | B6          | B2              | p07_p04_corrected              | 703         | 19     | 0.011019               | [0.009448, 0.01232]         | 0.0098946                  | 0.0011247             | True                 |
| high_20nA      | B6          | B2              | observed_even_charge           | 703         | 19     | 0.011175               | [0.0095736, 0.012281]       | 0.013443                   | -0.0022672            | True                 |
| high_20nA      | B4          | B4              | observed_even_charge           | 73          | 16     | 0.013186               | [0.0092456, 0.030547]       | 0.02962                    | -0.016434             | True                 |
| high_20nA      | B6          | B2              | traditional_template_corrected | 703         | 19     | 0.014404               | [0.012556, 0.0165]          | 0.015071                   | -0.00066769           | True                 |
| high_20nA      | B8          | B2              | traditional_template_corrected | 354         | 19     | 0.014919               | [0.011203, 0.020006]        | 0.011032                   | 0.0038866             | True                 |
| high_20nA      | B4          | B2              | gradient_boosted_trees         | 1564        | 19     | 0.015425               | [0.014419, 0.01677]         | 0.014705                   | 0.00072002            | True                 |
| high_20nA      | B4          | B4              | p07_p04_corrected              | 73          | 16     | 0.016674               | [0.012631, 0.026152]        | 0.017351                   | -0.00067629           | True                 |
| high_20nA      | B2          | B2              | gradient_boosted_trees         | 102060      | 19     | 0.018346               | [0.017148, 0.021071]        | 0.01353                    | 0.0048162             | True                 |
| high_20nA      | B2          | B2              | observed_even_charge           | 102060      | 19     | 0.020459               | [0.01876, 0.025281]         | 0.018837                   | 0.0016213             | True                 |
| low_2nA        | B2          | B2              | gradient_boosted_trees         | 1389        | 2      | 0.023598               | [0.023598, 0.026107]        | 0.0089842                  | 0.014614              | True                 |
| high_20nA      | B4          | B2              | observed_even_charge           | 1564        | 19     | 0.025796               | [0.023689, 0.026997]        | 0.037518                   | -0.011722             | True                 |
| high_20nA      | B4          | B2              | p07_p04_corrected              | 1564        | 19     | 0.026254               | [0.024602, 0.027521]        | 0.016204                   | 0.010051              | True                 |
| high_20nA      | B2          | B2              | p07_p04_corrected              | 102060      | 19     | 0.0271                 | [0.026572, 0.028243]        | 0.02055                    | 0.00655               | True                 |
| low_2nA        | B2          | B2              | p07_p04_corrected              | 1389        | 2      | 0.027253               | [0.026718, 0.031368]        | 0.013429                   | 0.013824              | True                 |
| high_20nA      | B4          | B4              | traditional_template_corrected | 73          | 16     | 0.027357               | [0.019499, 0.065358]        | 0.02997                    | -0.0026121            | True                 |
| high_20nA      | B4          | B2              | traditional_template_corrected | 1564        | 19     | 0.029642               | [0.026961, 0.032493]        | 0.038032                   | -0.0083901            | True                 |
| low_2nA        | B2          | B2              | observed_even_charge           | 1389        | 2      | 0.036536               | [0.035618, 0.042475]        | 0.020012                   | 0.016524              | True                 |

The S14f support map adds geometry and log-charge stress terms. The displayed rows are the strongest winner-method support cells by res68.

| geometry   | current_family | depth_stave | saturated_stave | method                 | n_saturated | energy_res68 | energy_res68_ci95      | sat_minus_unsat_log_charge_delta | sat_minus_unsat_log_charge_delta_ci95 | passes_log_delta_limit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| center_2cm | high_20nA      | B8          | B2              | gradient_boosted_trees | 354         | 0.007696     | [0.0074455, 0.0089536] | -0.21742                         | [-0.26008, -0.18699]                  | False                  |
| center_4cm | high_20nA      | B8          | B2              | gradient_boosted_trees | 354         | 0.0077467    | [0.0074115, 0.0091812] | -0.21742                         | [-0.26685, -0.17426]                  | False                  |
| zero_4cm   | high_20nA      | B8          | B2              | gradient_boosted_trees | 354         | 0.0091183    | [0.0086968, 0.010479]  | -0.21742                         | [-0.26202, -0.18488]                  | False                  |
| center_2cm | high_20nA      | B6          | B2              | gradient_boosted_trees | 703         | 0.0093006    | [0.008557, 0.010114]   | -0.17018                         | [-0.19061, -0.15037]                  | True                   |
| center_4cm | high_20nA      | B6          | B2              | gradient_boosted_trees | 703         | 0.0094421    | [0.0087669, 0.010368]  | -0.17018                         | [-0.19012, -0.14659]                  | True                   |
| center_2cm | high_20nA      | B4          | B4              | gradient_boosted_trees | 73          | 0.010588     | [0.0073988, 0.015332]  | -0.14559                         | [-0.24858, -0.1379]                   | True                   |
| center_4cm | high_20nA      | B4          | B4              | gradient_boosted_trees | 73          | 0.010985     | [0.0079497, 0.017019]  | -0.14559                         | [-0.24964, -0.1379]                   | True                   |
| zero_4cm   | high_20nA      | B6          | B2              | gradient_boosted_trees | 703         | 0.011694     | [0.010855, 0.012711]   | -0.17018                         | [-0.19014, -0.14359]                  | True                   |
| center_2cm | high_20nA      | B4          | B2              | gradient_boosted_trees | 1564        | 0.014864     | [0.013831, 0.01643]    | -0.11779                         | [-0.14126, -0.10388]                  | True                   |
| zero_4cm   | high_20nA      | B4          | B4              | gradient_boosted_trees | 73          | 0.015154     | [0.010567, 0.023232]   | -0.14559                         | [-0.24721, -0.1379]                   | True                   |
| center_4cm | high_20nA      | B4          | B2              | gradient_boosted_trees | 1564        | 0.015425     | [0.01422, 0.017183]    | -0.11779                         | [-0.14226, -0.1047]                   | True                   |
| center_2cm | high_20nA      | B2          | B2              | gradient_boosted_trees | 102060      | 0.017136     | [0.01595, 0.019528]    | -0.030505                        | [-0.033607, -0.022061]                | True                   |
| center_4cm | high_20nA      | B2          | B2              | gradient_boosted_trees | 102060      | 0.018346     | [0.017042, 0.020964]   | -0.030505                        | [-0.033248, -0.02197]                 | True                   |
| zero_4cm   | high_20nA      | B4          | B2              | gradient_boosted_trees | 1564        | 0.021381     | [0.01983, 0.023505]    | -0.11779                         | [-0.14717, -0.10262]                  | True                   |
| center_2cm | low_2nA        | B2          | B2              | gradient_boosted_trees | 1389        | 0.02217      | [0.02217, 0.024374]    | -0.057591                        | [-0.06261, -0.057305]                 | True                   |
| center_4cm | low_2nA        | B2          | B2              | gradient_boosted_trees | 1389        | 0.023598     | [0.023598, 0.026107]   | -0.057591                        | [-0.06261, -0.057305]                 | True                   |
| zero_4cm   | high_20nA      | B2          | B2              | gradient_boosted_trees | 102060      | 0.032967     | [0.030901, 0.037389]   | -0.030505                        | [-0.033466, -0.021983]                | True                   |
| zero_4cm   | low_2nA        | B2          | B2              | gradient_boosted_trees | 1389        | 0.043531     | [0.04327, 0.047892]    | -0.057591                        | [-0.06261, -0.057305]                 | True                   |

## 6. Depth-Order Stress

Rows show support bins with at least two depth staves. A zero rate means adjacent depth-bin medians remain nondecreasing for that method and geometry.

| geometry   | current_family | saturated_stave | method                         | n_saturated | n_depth_bins | depth_order_violation_rate | depth_order_violation_rate_ci95 | target_depth_order_violation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| center_2cm | high_20nA      | B2              | 1d_cnn                         | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | 1d_cnn                         | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | 1d_cnn                         | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | 1d_cnn                         | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | gradient_boosted_trees         | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | gradient_boosted_trees         | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | gradient_boosted_trees         | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | gradient_boosted_trees         | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | mlp                            | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | mlp                            | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | mlp                            | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | mlp                            | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | observed_even_charge           | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | observed_even_charge           | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | observed_even_charge           | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | observed_even_charge           | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | p07_p04_corrected              | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | p07_p04_corrected              | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | p07_p04_corrected              | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | p07_p04_corrected              | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | ridge                          | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | ridge                          | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | ridge                          | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | ridge                          | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | template_residual_mlp          | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | template_residual_mlp          | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | template_residual_mlp          | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | template_residual_mlp          | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2              | traditional_template_corrected | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B2+B4           | traditional_template_corrected | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | high_20nA      | B4              | traditional_template_corrected | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_2cm | low_2nA        | B2              | traditional_template_corrected | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | 1d_cnn                         | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | 1d_cnn                         | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | 1d_cnn                         | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | 1d_cnn                         | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | gradient_boosted_trees         | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | gradient_boosted_trees         | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | gradient_boosted_trees         | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | gradient_boosted_trees         | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | mlp                            | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | mlp                            | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | mlp                            | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | mlp                            | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | observed_even_charge           | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | observed_even_charge           | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | observed_even_charge           | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | observed_even_charge           | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | p07_p04_corrected              | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | p07_p04_corrected              | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | p07_p04_corrected              | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | p07_p04_corrected              | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | ridge                          | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | ridge                          | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | ridge                          | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | ridge                          | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | template_residual_mlp          | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | template_residual_mlp          | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | template_residual_mlp          | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | template_residual_mlp          | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2              | traditional_template_corrected | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B2+B4           | traditional_template_corrected | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | high_20nA      | B4              | traditional_template_corrected | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| center_4cm | low_2nA        | B2              | traditional_template_corrected | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2              | 1d_cnn                         | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2+B4           | 1d_cnn                         | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B4              | 1d_cnn                         | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | low_2nA        | B2              | 1d_cnn                         | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2              | gradient_boosted_trees         | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2+B4           | gradient_boosted_trees         | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B4              | gradient_boosted_trees         | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | low_2nA        | B2              | gradient_boosted_trees         | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2              | mlp                            | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2+B4           | mlp                            | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B4              | mlp                            | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | low_2nA        | B2              | mlp                            | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2              | observed_even_charge           | 104681      | 4            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B2+B4           | observed_even_charge           | 20          | 2            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | high_20nA      | B4              | observed_even_charge           | 82          | 3            | 0                          | [0, 0]                          | 0                                 |
| zero_4cm   | low_2nA        | B2              | observed_even_charge           | 1411        | 4            | 0                          | [0, 0]                          | 0                                 |

## 7. Per-Run Diagnostics

| run | current_family | method                         | n_saturated | saturated_energy_res68 | saturated_charge_res68 |
| --- | --- | --- | --- | --- | --- |
| 44  | high_20nA      | observed_even_charge           | 334         | 0.033083               | 0.5769                 |
| 44  | high_20nA      | traditional_template_corrected | 334         | 0.091328               | 0.57122                |
| 44  | high_20nA      | p07_p04_corrected              | 334         | 0.029063               | 0.57491                |
| 44  | high_20nA      | gradient_boosted_trees         | 334         | 0.027419               | 0.069368               |
| 45  | high_20nA      | observed_even_charge           | 5472        | 0.034247               | 0.58054                |
| 45  | high_20nA      | traditional_template_corrected | 5472        | 0.090568               | 0.57384                |
| 45  | high_20nA      | p07_p04_corrected              | 5472        | 0.027697               | 0.57849                |
| 45  | high_20nA      | gradient_boosted_trees         | 5472        | 0.023598               | 0.072653               |
| 46  | low_2nA        | observed_even_charge           | 144         | 0.042431               | 0.57792                |
| 46  | low_2nA        | traditional_template_corrected | 144         | 0.087971               | 0.57124                |
| 46  | low_2nA        | p07_p04_corrected              | 144         | 0.030488               | 0.57594                |
| 46  | low_2nA        | gradient_boosted_trees         | 144         | 0.02473                | 0.07251                |
| 47  | low_2nA        | observed_even_charge           | 1268        | 0.03555                | 0.57877                |
| 47  | low_2nA        | traditional_template_corrected | 1268        | 0.093224               | 0.57174                |
| 47  | low_2nA        | p07_p04_corrected              | 1268        | 0.026671               | 0.57683                |
| 47  | low_2nA        | gradient_boosted_trees         | 1268        | 0.023598               | 0.06542                |
| 48  | high_20nA      | observed_even_charge           | 1991        | 0.038675               | 0.57542                |
| 48  | high_20nA      | traditional_template_corrected | 1991        | 0.092541               | 0.5686                 |
| 48  | high_20nA      | p07_p04_corrected              | 1991        | 0.032321               | 0.57339                |
| 48  | high_20nA      | gradient_boosted_trees         | 1991        | 0.027108               | 0.067902               |
| 49  | high_20nA      | observed_even_charge           | 2154        | 0.037252               | 0.57663                |
| 49  | high_20nA      | traditional_template_corrected | 2154        | 0.09204                | 0.5703                 |
| 49  | high_20nA      | p07_p04_corrected              | 2154        | 0.031675               | 0.57475                |
| 49  | high_20nA      | gradient_boosted_trees         | 2154        | 0.02795                | 0.070567               |
| 50  | high_20nA      | observed_even_charge           | 19492       | 0.018035               | 0.57547                |
| 50  | high_20nA      | traditional_template_corrected | 19492       | 0.081198               | 0.56876                |
| 50  | high_20nA      | p07_p04_corrected              | 19492       | 0.025927               | 0.57355                |
| 50  | high_20nA      | gradient_boosted_trees         | 19492       | 0.01748                | 0.056246               |
| 51  | high_20nA      | observed_even_charge           | 7248        | 0.019875               | 0.5739                 |
| 51  | high_20nA      | traditional_template_corrected | 7248        | 0.081628               | 0.5672                 |
| 51  | high_20nA      | p07_p04_corrected              | 7248        | 0.027127               | 0.5719                 |
| 51  | high_20nA      | gradient_boosted_trees         | 7248        | 0.01805                | 0.054356               |
| 52  | high_20nA      | observed_even_charge           | 3625        | 0.019498               | 0.57353                |
| 52  | high_20nA      | traditional_template_corrected | 3625        | 0.082578               | 0.56681                |
| 52  | high_20nA      | p07_p04_corrected              | 3625        | 0.026833               | 0.5715                 |
| 52  | high_20nA      | gradient_boosted_trees         | 3625        | 0.018549               | 0.053871               |
| 53  | high_20nA      | observed_even_charge           | 13961       | 0.0173                 | 0.56313                |
| 53  | high_20nA      | traditional_template_corrected | 13961       | 0.077626               | 0.55626                |
| 53  | high_20nA      | p07_p04_corrected              | 13961       | 0.025851               | 0.56125                |
| 53  | high_20nA      | gradient_boosted_trees         | 13961       | 0.015283               | 0.039596               |
| 54  | high_20nA      | observed_even_charge           | 13282       | 0.016851               | 0.56288                |
| 54  | high_20nA      | traditional_template_corrected | 13282       | 0.077378               | 0.55606                |
| 54  | high_20nA      | p07_p04_corrected              | 13282       | 0.025525               | 0.56102                |
| 54  | high_20nA      | gradient_boosted_trees         | 13282       | 0.015147               | 0.039627               |
| 55  | high_20nA      | observed_even_charge           | 8330        | 0.019293               | 0.57106                |
| 55  | high_20nA      | traditional_template_corrected | 8330        | 0.079581               | 0.56422                |
| 55  | high_20nA      | p07_p04_corrected              | 8330        | 0.026728               | 0.56914                |
| 55  | high_20nA      | gradient_boosted_trees         | 8330        | 0.01748                | 0.049528               |
| 56  | high_20nA      | observed_even_charge           | 21645       | 0.020915               | 0.57459                |
| 56  | high_20nA      | traditional_template_corrected | 21645       | 0.082338               | 0.56774                |
| 56  | high_20nA      | p07_p04_corrected              | 21645       | 0.027248               | 0.57267                |
| 56  | high_20nA      | gradient_boosted_trees         | 21645       | 0.018533               | 0.05477                |
| 57  | high_20nA      | observed_even_charge           | 1843        | 0.037637               | 0.57564                |
| 57  | high_20nA      | traditional_template_corrected | 1843        | 0.092779               | 0.56845                |
| 57  | high_20nA      | p07_p04_corrected              | 1843        | 0.033111               | 0.57372                |
| 57  | high_20nA      | gradient_boosted_trees         | 1843        | 0.026928               | 0.071513               |
| 58  | high_20nA      | observed_even_charge           | 1618        | 0.02861                | 0.55883                |
| 58  | high_20nA      | traditional_template_corrected | 1618        | 0.068637               | 0.55204                |
| 58  | high_20nA      | p07_p04_corrected              | 1618        | 0.029469               | 0.55709                |
| 58  | high_20nA      | gradient_boosted_trees         | 1618        | 0.022864               | 0.043912               |
| 59  | high_20nA      | observed_even_charge           | 809         | 0.049206               | 0.61069                |
| 59  | high_20nA      | traditional_template_corrected | 809         | 0.099099               | 0.60559                |
| 59  | high_20nA      | p07_p04_corrected              | 809         | 0.041334               | 0.60959                |
| 59  | high_20nA      | gradient_boosted_trees         | 809         | 0.035709               | 0.17414                |
| 60  | high_20nA      | observed_even_charge           | 382         | 0.043603               | 0.56864                |
| 60  | high_20nA      | traditional_template_corrected | 382         | 0.077465               | 0.56371                |
| 60  | high_20nA      | p07_p04_corrected              | 382         | 0.044099               | 0.56683                |
| 60  | high_20nA      | gradient_boosted_trees         | 382         | 0.033702               | 0.08226                |
| 61  | high_20nA      | observed_even_charge           | 420         | 0.042764               | 0.56338                |
| 61  | high_20nA      | traditional_template_corrected | 420         | 0.080187               | 0.55785                |
| 61  | high_20nA      | p07_p04_corrected              | 420         | 0.039836               | 0.5617                 |
| 61  | high_20nA      | gradient_boosted_trees         | 420         | 0.032386               | 0.073327               |
| 62  | high_20nA      | observed_even_charge           | 513         | 0.04494                | 0.58516                |
| 62  | high_20nA      | traditional_template_corrected | 513         | 0.10022                | 0.57877                |
| 62  | high_20nA      | p07_p04_corrected              | 513         | 0.04308                | 0.58264                |
| 62  | high_20nA      | gradient_boosted_trees         | 513         | 0.035869               | 0.14668                |
| 63  | high_20nA      | observed_even_charge           | 1232        | 0.03414                | 0.58328                |
| 63  | high_20nA      | traditional_template_corrected | 1232        | 0.085404               | 0.57576                |
| 63  | high_20nA      | p07_p04_corrected              | 1232        | 0.032765               | 0.58162                |
| 63  | high_20nA      | gradient_boosted_trees         | 1232        | 0.025962               | 0.11166                |

## 8. Traditional-Systematic Caveat

The explicit S14c-style warning is the `traditional_worsens_observed` flag: the rising-edge template correction is worse than observed charge for the same geometry and saturated held-out rows.

Rows where the traditional template worsens observed charge:

| geometry   | method                         | saturated_energy_res68 | traditional_minus_observed_res68 | traditional_worsens_observed |
| --- | --- | --- | --- | --- |
| center_4cm | traditional_template_corrected | 0.08155                | 0.061056                         | True                         |
| center_2cm | traditional_template_corrected | 0.076251               | 0.057109                         | True                         |
| zero_4cm   | traditional_template_corrected | 0.14558                | 0.10827                          | True                         |

## 9. Leakage and Caveats

| check                                        | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                    | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                       | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| train_heldout_event_key_overlap              | 0                                                                                                                                                                                                                                                                                                                                                                | True |
| ml_features_exclude_odd_charge_run_event_ids | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                   | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| shuffled_p04_unsaturated_charge_res68        | 0.514066                                                                                                                                                                                                                                                                                                                                                         | True |

The main caveat is target scope: duplicate odd-readout closure is an electronics self-consistency test, not deposited-energy truth. The PSTAR/depth map supplies an ordering proxy, while Birks quenching, material budget, geometry, and particle identity remain external systematics. Geometry variants are therefore stress envelopes, not calibrated detector survey alternatives. Current labels use the documented low-current runs 46--47 versus the otherwise high-current B-stack runs; Sample-II runs are treated as high-current for this audit.

## 10. Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. The geometry-stress winner is gradient_boosted_trees with worst-geometry saturated energy-proxy res68 0.03272; its nominal center-4cm res68 is 0.01828 [0.017168, 0.020764]. The strong traditional rising-edge template has res68 0.08155, observed charge has 0.02049, so traditional template correction worsens the nominal saturated geometry proxy. Accepted nominal current/depth/stave bands at margin 0.020: 22. Maximum winner depth-order violation rate is 0.000; maximum absolute winner saturated-minus-unsaturated log-charge delta is 0.217. Traditional-worsening geometries: ['center_4cm', 'center_2cm', 'zero_4cm']. The result is an odd-readout closure and range-order proxy; it does not establish absolute deposited-energy truth.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.py --config configs/s14f_1781033587_678_10103f5a_saturation_geometry_stress_map.yaml
```

Artifacts: `result.json`, `manifest.json`, `method_metrics.csv`, `acceptance_bands.csv`, `support_stress_map.csv`, `ordering_stress.csv`, `method_geometry_summary.csv`, `per_run_acceptance.csv`, `geometry_systematics.csv`, `leakage_checks.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, and `fig_s14f_saturated_res68.png`.

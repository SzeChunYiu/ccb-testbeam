# P11b: Pretrigger Atom Charge-transfer Gate

- **Ticket:** `1781061059.627.4bc647a3`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files `h101/HRDv`; no simulation and no derived pulse table.
- **Config:** `configs/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.json`
- **Git commit:** `330f2bfc0c52b8f1c164407ac39b4f0d2b0e9cfc`

## Abstract

Raw selected-pulse reproduction passes exactly (640737 vs 640737). The held-out duplicate-charge winner is `ML_hgb_pretrigger_wave_atoms` with res68 0.0164 [0.0130, 0.0190], compared with the strongest traditional method `traditional_p11a_atom_cell_corrected` at 0.0276. Matched P11a atom effects are small relative to the main amplitude/dropout/saturation structure, so adaptive-lowering/spike atoms are best used as support and abstention flags rather than as independent charge-correction variables.

## 1. Reproduction Gate

| quantity | report value | reproduced | delta | tolerance | pass |
|---|---:|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | 0 | true |

The script subtracts the per-channel median over samples 0--3, reshapes each raw `HRDv` record to `(8,18)`, and selects even-channel B2/B4/B6/B8 pulse records with peak amplitude greater than 1000 ADC. Duplicate-target quality cuts are applied only after this raw reproduction gate.

## 2. Estimands

The paired odd-channel charge target is

\[ y_i^{dup}=\sum_t \max[-o_i(t),0], \]

where `o_i(t)` is the baseline-subtracted odd readout paired with the selected even-channel waveform. A charge estimator returns `hat y_i`; the fractional residual is

\[ r_i=(\hat y_i-y_i^{dup})/\max(y_i^{dup},1). \]

The primary width metric is `Q_0.68(|r_i|)`. Secondary quantities are median signed bias, charge-bias-tail rate `P(|r_i|>0.25)`, support coverage, abstention harm reduction, calibration ECE, and matched atom deltas. Confidence intervals are non-parametric run-block bootstraps over the seven held-out Sample-II runs.

## 3. Methods

P11a atoms are frozen from train-run pretrigger samples 0--3 with the same precedence as P11a: `quiet`, `noisy_rms`, `sloped`, `early_asym`, `adaptive_lowering`, then `spike`. Matching controls are run family, stave, amplitude bin, P07-style saturation flag, dropout atom, and P09 anomaly quantile.

Traditional estimators are P04-style peak and integral log calibrations, shifted adaptive-template scaling, a Huber model on hand-built waveform/charge/pathology summaries, and a P11a atom-cell residual correction of the integral estimator. ML/NN estimators are ridge, histogram gradient-boosted trees, a tabular MLP, a waveform-only 1D-CNN, and the new `NN_pretrigger_gated_residual_cnn_new`, which gates a temporal convolution branch by pretrigger atom summaries.

## 4. Held-out Charge Benchmark

| method                               |      n |   bias_median_frac | bias_ci95                                        |   res68_abs_frac | res68_ci95                                   |   charge_bias_tail_rate | charge_bias_tail_rate_ci95                    |
|:-------------------------------------|-------:|-------------------:|:-------------------------------------------------|-----------------:|:---------------------------------------------|------------------------:|:----------------------------------------------|
| ML_hgb_pretrigger_wave_atoms         | 125078 |        0.000738926 | [0.0006318997267847757, 0.0008722101820373653]   |        0.0163609 | [0.013044337664879838, 0.018973468547217133] |              0.00488495 | [0.003163448156383828, 0.0063847580263971205] |
| ML_ridge_pretrigger_wave_atoms       | 125078 |        0.000764174 | [-0.0010458750068210064, 0.0029813497967552376]  |        0.0230651 | [0.02000800536759198, 0.025882752537727396]  |              0.0421417  | [0.029123610519184513, 0.05057449859302132]   |
| traditional_p11a_atom_cell_corrected | 125078 |       -0.00244682  | [-0.0036989592610894894, -0.0014413984757306064] |        0.0275901 | [0.023071286414143848, 0.032232400824979926] |              0.0940853  | [0.06700725514112371, 0.11220417633410673]    |
| NN_mlp_pretrigger_wave_atoms         | 125078 |       -0.00262391  | [-0.005528905079700053, -0.000187617628216688]   |        0.042296  | [0.032926912885159254, 0.04943307259306312]  |              0.0253442  | [0.01740784565961521, 0.030710831344057412]   |
| NN_pretrigger_gated_residual_cnn_new | 125078 |        0.0186299   | [0.01673798537813127, 0.02023493153974414]       |        0.0632303 | [0.05308643942698836, 0.07114225036650897]   |              0.0623531  | [0.0452746588641233, 0.07338052343937086]     |
| traditional_huber_p11a_support       | 125078 |        0.0195019   | [0.009476631607185915, 0.028104798057971322]     |        0.148243  | [0.11310929421663181, 0.1745570245811665]    |              0.222445   | [0.1877795577856004, 0.24908463224990965]     |
| traditional_integral_logcal          | 125078 |       -0.107371    | [-0.11274091014553228, -0.09991318860519519]     |        0.186395  | [0.16933236364094534, 0.20109595379614892]   |              0.21202    | [0.17053348940669552, 0.23975130314677331]    |
| traditional_peak_logcal              | 125078 |       -0.232842    | [-0.23614883694788974, -0.2304930350519653]      |        0.318023  | [0.2881248591528306, 0.33466744032668444]    |              0.553271   | [0.5038139488913778, 0.5826841425439676]      |
| NN_1d_cnn_waveform                   | 125078 |       -0.0249297   | [-0.07526148315519095, 0.023910524183884257]     |        0.367032  | [0.2994892506599427, 0.43400519117713]       |              0.459425   | [0.39532446633857465, 0.5027509082684177]     |
| traditional_adaptive_template_logcal | 125078 |        0.13834     | [0.07952131828063858, 0.20611800647470452]       |        0.538691  | [0.4644465162906966, 0.6291823273113432]     |              0.560274   | [0.48856124870059275, 0.5982835322233806]     |

Winner by held-out charge res68: `ML_hgb_pretrigger_wave_atoms`. Strongest traditional comparator: `traditional_p11a_atom_cell_corrected`.

## 5. ML-minus-traditional Deltas

| method                               | traditional_reference                |   delta_res68_abs_frac | delta_res68_abs_frac_ci95                      |   delta_charge_bias_tail_rate | delta_charge_bias_tail_rate_ci95              |
|:-------------------------------------|:-------------------------------------|-----------------------:|:-----------------------------------------------|------------------------------:|:----------------------------------------------|
| ML_hgb_pretrigger_wave_atoms         | traditional_p11a_atom_cell_corrected |            -0.0112292  | [-0.013425114443101162, -0.00955074635215249]  |                    -0.0892003 | [-0.10517760884074195, -0.06514334183196813]  |
| ML_ridge_pretrigger_wave_atoms       | traditional_p11a_atom_cell_corrected |            -0.00452495 | [-0.006355488611916999, -0.002593654856295732] |                    -0.0519436 | [-0.06282062073400277, -0.03677396586414435]  |
| NN_mlp_pretrigger_wave_atoms         | traditional_p11a_atom_cell_corrected |             0.0147059  | [0.010468998107968983, 0.01704894896893442]    |                    -0.0687411 | [-0.08167145700865916, -0.04860680946475893]  |
| NN_pretrigger_gated_residual_cnn_new | traditional_p11a_atom_cell_corrected |             0.0356402  | [0.029983324353290267, 0.040116043201661566]   |                    -0.0317322 | [-0.037710261564699664, -0.02190198917229756] |
| NN_1d_cnn_waveform                   | traditional_p11a_atom_cell_corrected |             0.339442   | [0.27631455886463563, 0.4016372782882379]      |                     0.36534   | [0.32915975438496486, 0.39227072170350763]    |

Negative deltas favor the ML/NN method. The bootstrap unit is the held-out run, not individual pulse records.

## 6. Per-run Stability

| method                               |   run |     n |   res68_abs_frac |   charge_bias_tail_rate |   bias_median_frac |
|:-------------------------------------|------:|------:|-----------------:|------------------------:|-------------------:|
| traditional_p11a_atom_cell_corrected |    58 | 16780 |       0.0174831  |             0.0188319   |       -0.00500038  |
| traditional_p11a_atom_cell_corrected |    59 | 21374 |       0.0350364  |             0.121971    |       -0.000592216 |
| traditional_p11a_atom_cell_corrected |    60 | 17021 |       0.0322839  |             0.114271    |       -0.00171454  |
| traditional_p11a_atom_cell_corrected |    61 | 18963 |       0.0309345  |             0.104572    |       -0.00281626  |
| traditional_p11a_atom_cell_corrected |    62 | 19088 |       0.0316194  |             0.10724     |       -0.00158498  |
| traditional_p11a_atom_cell_corrected |    63 | 18814 |       0.0275299  |             0.0966833   |       -0.00208021  |
| traditional_p11a_atom_cell_corrected |    65 | 13038 |       0.0261062  |             0.0806105   |       -0.00374614  |
| ML_hgb_pretrigger_wave_atoms         |    58 | 16780 |       0.00948099 |             0.000893921 |        0.000559312 |
| ML_hgb_pretrigger_wave_atoms         |    59 | 21374 |       0.0194083  |             0.00776645  |        0.000922151 |
| ML_hgb_pretrigger_wave_atoms         |    60 | 17021 |       0.0182086  |             0.00399506  |        0.000635481 |
| ML_hgb_pretrigger_wave_atoms         |    61 | 18963 |       0.0204465  |             0.00485155  |        0.000812835 |
| ML_hgb_pretrigger_wave_atoms         |    62 | 19088 |       0.0183565  |             0.00534367  |        0.000940164 |
| ML_hgb_pretrigger_wave_atoms         |    63 | 18814 |       0.0156985  |             0.00664399  |        0.000528694 |
| ML_hgb_pretrigger_wave_atoms         |    65 | 13038 |       0.0136012  |             0.00329805  |        0.000916793 |
| NN_1d_cnn_waveform                   |    58 | 16780 |       0.237026   |             0.277175    |       -0.125797    |
| NN_1d_cnn_waveform                   |    59 | 21374 |       0.463429   |             0.51179     |        0.0508425   |
| NN_1d_cnn_waveform                   |    60 | 17021 |       0.389953   |             0.494037    |       -0.0312614   |
| NN_1d_cnn_waveform                   |    61 | 18963 |       0.383822   |             0.501608    |       -0.0217698   |
| NN_1d_cnn_waveform                   |    62 | 19088 |       0.415111   |             0.501886    |        0.00876293  |
| NN_1d_cnn_waveform                   |    63 | 18814 |       0.361092   |             0.436483    |       -0.00719615  |
| NN_1d_cnn_waveform                   |    65 | 13038 |       0.450452   |             0.472542    |        0.0458398   |

## 7. Atom-stratified Outcomes

| p11a_atom         |     n |    fraction |   bias_median_frac |   res68_abs_frac |   charge_bias_tail_rate |   saturation_fraction |   dropout_atom_fraction |
|:------------------|------:|------------:|-------------------:|-----------------:|------------------------:|----------------------:|------------------------:|
| quiet             | 96187 | 0.769016    |        0.000650243 |        0.0119532 |             0.000103964 |                     1 |              0.00185056 |
| spike             | 12359 | 0.0988103   |        0.00216136  |        0.0806254 |             0.0388381   |                     1 |              0.503358   |
| adaptive_lowering | 10343 | 0.0826924   |        0.000169488 |        0.0505891 |             0.0116987   |                     1 |              0.299333   |
| early_asym        |  6090 | 0.0486896   |        0.00368841  |        0.0230948 |             0           |                     1 |              0.00591133 |
| sloped            |    70 | 0.000559651 |        0.00231321  |        0.0154612 |             0           |                     1 |              0          |
| noisy_rms         |    29 | 0.000231855 |        0.00122732  |        0.0142286 |             0           |                     1 |              0          |

## 8. Matched Atom Effects

| method                               | p11a_atom         |   n_cells |   delta_abs_frac_mean | delta_abs_frac_mean_ci95                       |   delta_signed_bias |   delta_charge_bias_tail_rate | delta_charge_bias_tail_rate_ci95                 |
|:-------------------------------------|:------------------|----------:|----------------------:|:-----------------------------------------------|--------------------:|------------------------------:|:-------------------------------------------------|
| traditional_p11a_atom_cell_corrected | early_asym        |       128 |            0.0106705  | [0.0057778868577598496, 0.014344428695645317]  |          0.0300288  |                  -0.0443903   | [-0.05263606408430137, -0.038359855392150685]    |
| traditional_p11a_atom_cell_corrected | adaptive_lowering |       109 |            0.0887273  | [0.06391936305676835, 0.10448557037567739]     |          0.0258874  |                   0.138795    | [0.09960605510022459, 0.1640766347910397]        |
| traditional_p11a_atom_cell_corrected | spike             |        85 |            0.422199   | [0.39168386336940775, 0.4578966300434899]      |          0.0214205  |                   0.392264    | [0.37701681274825927, 0.4113199168959928]        |
| ML_hgb_pretrigger_wave_atoms         | early_asym        |       128 |            0.00305015 | [0.0017911690547006201, 0.0038955784621103177] |          0.00489835 |                  -7.80781e-05 | [-0.0001685218126314033, -1.031302614157812e-05] |
| ML_hgb_pretrigger_wave_atoms         | adaptive_lowering |       109 |            0.0187439  | [0.014902193742668225, 0.020955317338895527]   |          0.00106847 |                   0.00309048  | [0.0012873025861322956, 0.004628008310159623]    |
| ML_hgb_pretrigger_wave_atoms         | spike             |        85 |            0.050513   | [0.04527835309924465, 0.05652302296775483]     |          0.00788584 |                   0.024165    | [0.01906114154986083, 0.030268252485147445]      |

Positive matched deltas mean the P11a atom has worse charge residuals than quiet records after conditioning on amplitude, saturation, dropout, anomaly, stave, and run family.

## 9. Harm Classifier Calibration and Controls

| task             | method                       |      n |   positive_rate |   roc_auc |   average_precision |        ece | coverage_retained_at_80pct_low_risk   | harm_rate_retained   |
|:-----------------|:-----------------------------|-------:|----------------:|----------:|--------------------:|-----------:|:--------------------------------------|:---------------------|
| charge_harm_tail | traditional_p11a_atom_only   | 125078 |         0.19232 |  0.891441 |            0.718292 | 0.128055   | 0.769808                              | 0.0408782            |
| charge_harm_tail | ML_hgb_pretrigger_wave_atoms | 125078 |         0.19232 |  0.990787 |            0.957813 | 0.00588055 | 0.799997                              | 0.0181288            |
| charge_harm_tail | control_pretrigger_knockout  | 125078 |         0.19232 |  0.989566 |            0.953244 | 0.00648243 | 0.799997                              | 0.0186684            |
| charge_harm_tail | control_saturation_only      | 125078 |         0.19232 |  0.836278 |            0.706979 | 0.0287556  | 0.799821                              | 0.0854058            |
| charge_harm_tail | control_dropout_only         | 125078 |         0.19232 |  0.971593 |            0.886641 | 0.00751463 | 0.799989                              | 0.0395958            |
| charge_harm_tail | control_amplitude_only       | 125078 |         0.19232 |  0.939714 |            0.857915 | 0.0276709  | 0.799997                              | 0.04832              |
| charge_harm_tail | control_run_only             | 125078 |         0.19232 |  0.48638  |            0.1883   | 0.00525664 | 0.558875                              | 0.199891             |
| charge_harm_tail | control_shuffled_harm_labels | 125078 |         0.19232 |  0.57928  |            0.265913 | 0.0927383  |                                       |                      |

The controls test whether the pretrigger/waveform model is only rediscovering saturation, dropout, amplitude, run family, or shuffled harm labels. ECE is computed in ten probability bins on held-out runs.

## 10. Support Model and Abstention

| task                     | method                                     |      n |   positive_rate |   roc_auc |   average_precision |         ece |   coverage_retained_at_80pct_high_support |   support_valid_rate_retained |
|:-------------------------|:-------------------------------------------|-------:|----------------:|----------:|--------------------:|------------:|------------------------------------------:|------------------------------:|
| duplicate_target_support | support_traditional_pretrigger_huber_proxy | 125096 |        0.999856 |  0.277961 |            0.999396 | 0.000423101 |                                  0.145992 |                      0.999288 |
| duplicate_target_support | support_ML_hgb_full                        | 125096 |        0.999856 |  0.777993 |            0.999807 | 0.000474819 |                                  0.202005 |                      0.999842 |
| duplicate_target_support | support_amplitude_only                     | 125096 |        0.999856 |  0.363674 |            0.999584 | 0.00103469  |                                  0.126639 |                      0.999306 |

| quantity | value |
|---|---:|
| train q90 harm threshold | 0.0223892 |
| pretrigger abstention threshold | 330.623 |
| support coverage retained | 0.792617 |
| support loss | 0.207383 |
| harm rate before abstention | 0.228881 |
| harm rate after abstention | 0.115535 |
| abstention harm reduction | 0.113346 |
| retained res68 | 0.0120732 |

## 11. Systematics and Caveats

- The split is by run: Sample I plus run 64 train, Sample-II analysis runs 58, 59, 60, 61, 62, 63, 65 held out.
- The target is duplicate-readout charge closure, not absolute deposited-energy truth. It is an electronics-transfer proxy.
- P11a atoms are support labels from pretrigger samples, not interventions. Matched deltas are residual associations.
- Neural models are laptop-scale probes with fixed epochs; the claim is comparative under a common split, not an exhaustive architecture search.
- Run-block CIs dominate because only seven held-out runs define the external uncertainty scale.

## 12. Conclusion

P11a pretrigger atoms do carry charge-transfer support information, but after explicit matching on amplitude, P07 saturation, dropout/anomaly taxa, stave, and run family they behave primarily as electronics-support labels. The operational rule is therefore pass quiet records, abstain or down-weight high pretrigger-score records near support boundaries, and avoid a hard veto unless downstream consumers require the lowest charge-tail rate.

No follow-up ticket was appended from this run; P11b closes with an abstain/veto recommendation rather than opening a new branch.

## 13. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.py --config configs/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `benchmark.csv`, `benchmark_by_run.csv`, `ml_minus_traditional.csv`, `atom_outcome_summary.csv`, `matched_p11a_atom_effects.csv`, `harm_classifier_metrics.csv`, and `support_model_metrics.csv`.

# P04n: Forced-random pedestal validation of P04m pretrigger abstention

- **Ticket:** `1781101446.892.139c702a`
- **Worker:** `testbeam-laptop-2`
- **Inputs:** raw B-stack ROOT under `data/root/root`, P04m predecessor artifacts, and S16f forced/random inventory context.
- **Primary split:** leave-one-run-out over Sample-II analysis runs `58, 59, 60, 61, 62, 63, 65`.

## Abstract

Raw ROOT reproduction passes exactly (640,737 selected B-stave pulses; delta +0). No accessible forced/random pedestal B-stack ROOT source was found: 53 B-stack files carry only trigger code(s) [1] and keyword search found 0 candidate ROOT files. On the external downstream charge proxy, extra_trees_with_pretrigger wins with res68 0.2098 [0.1976, 0.2261], versus the traditional comparator traditional_huber_ridge at 0.2198. This validates P04m only as a physics-event pretrigger support diagnostic, not as a true forced/random pedestal veto.

## 1. Pre-registered question

The ticket asks whether P04m high-pretrigger abstention regions correspond to independently measured forced/random pedestal disturbances and whether those regions predict external charge-proxy failure after amplitude, saturation, run, and topology matching. The primary decision rule is: first establish whether a dedicated forced/random B-stack pedestal ROOT source exists; if absent, do not promote the pretrigger map to a true pedestal validation and instead quantify its external charge-proxy behavior as a physics-event pretrigger support diagnostic.

## 2. Raw ROOT reproduction

The reproduction gate directly reads `h101/HRDv` from `data/root/root/hrdb_run_NNNN.root`, reshapes every event to 8 channels by 18 samples, subtracts the per-channel median of samples 0--3, and counts even B-stave channels B2, B4, B6, and B8 whose baseline-subtracted peak exceeds 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

Per-run reproduction counts are in `raw_reproduction_counts.csv`; the total matches the predecessor raw-ROOT count exactly.

## 3. Forced/random pedestal source audit

The B-stack ROOT trigger inventory was rerun from the accessible raw files. All non-empty B-stack ROOT files carry trigger code 1 only, and the keyword search found no ROOT file with forced/random/pedestal/no-pulse naming in the accessible mirror.

| audit item | value |
|---|---:|
| B-stack raw ROOT files | 53 |
| nonempty B-stack raw ROOT files | 51 |
| unique trigger codes | 1 |
| files with TRIGGER != 1 | 0 |
| keyword ROOT files for forced/random/pedestal | 0 |
| dedicated forced/random pedestal ROOT found | false |

This is the key systematic limit: P04n cannot be a direct electronics-pedestal validation until such a source is mirrored or acquired. The remaining benchmark is therefore an external charge-proxy transfer test of the P04m support map.

## 4. Estimands and equations

For penetrating B2 events, the external charge proxy is

`y_i^ext = sum_{s in {B4,B6,B8}} sum_t max(x_{i,s,t} - median(x_{i,s,0:3}), 0)`.

Each predictor is scored by fractional residual

`r_i = (hat y_i - y_i^ext) / max(y_i^ext, 1)`.

The primary metric is `Q_0.68(|r_i|)`, with median bias, full RMS, catastrophic rate `P(|r_i|>0.25)`, and `P(|r_i|<0.10)` reported as secondary metrics. Confidence intervals use a non-parametric run-block bootstrap: sample the seven held-out runs with replacement, concatenate their events, and recompute the metric.

## 5. External charge-proxy benchmark

| method                                  |    n |   bias_median_frac |   res68_abs_frac | res68_ci95           |   full_rms_frac |   catastrophic_rate | catastrophic_rate_ci95   |   within_10pct |
|:----------------------------------------|-----:|-------------------:|-----------------:|:---------------------|----------------:|--------------------:|:-------------------------|---------------:|
| extra_trees_with_pretrigger             | 3774 |        -0.0132384  |         0.209761 | [0.197623, 0.226071] |        0.272763 |            0.237414 | [0.211774, 0.273585]     |       0.351086 |
| gradient_boosted_trees_with_pretrigger  | 3774 |        -0.016913   |         0.212039 | [0.20264, 0.22682]   |        0.270881 |            0.237414 | [0.213388, 0.27603]      |       0.335188 |
| gradient_boosted_trees_no_pretrigger    | 3774 |        -0.0165154  |         0.212872 | [0.205064, 0.230373] |        0.266739 |            0.238474 | [0.216275, 0.276719]     |       0.347377 |
| traditional_huber_ridge                 | 3774 |        -0.00587118 |         0.219784 | [0.202316, 0.2453]   |        0.316197 |            0.257817 | [0.220204, 0.312421]     |       0.337573 |
| duplicate_transfer_hgb_new_architecture | 3774 |         2.75382    |         3.82999  | [0.943766, 4.29871]  |        3.50132  |            0.840488 | [0.535684, 0.997514]     |       0.072867 |

Winner by external charge-proxy `Q_0.68(|r|)`: **extra_trees_with_pretrigger**. Best traditional comparator: **traditional_huber_ridge**.

Per-run winner and traditional comparator rows:

| method                      |   run |   n |   res68_abs_frac |   full_rms_frac |   catastrophic_rate |   within_10pct |
|:----------------------------|------:|----:|-----------------:|----------------:|--------------------:|---------------:|
| traditional_huber_ridge     |    58 |  72 |         0.240426 |        0.526218 |            0.319444 |       0.333333 |
| traditional_huber_ridge     |    59 | 749 |         0.261814 |        0.372981 |            0.341789 |       0.317757 |
| traditional_huber_ridge     |    60 | 802 |         0.223229 |        0.267759 |            0.236908 |       0.30798  |
| traditional_huber_ridge     |    61 | 925 |         0.197638 |        0.232325 |            0.205405 |       0.340541 |
| traditional_huber_ridge     |    62 | 798 |         0.197182 |        0.304419 |            0.215539 |       0.379699 |
| traditional_huber_ridge     |    63 | 365 |         0.260905 |        0.402072 |            0.328767 |       0.356164 |
| traditional_huber_ridge     |    65 |  63 |         0.284494 |        0.450909 |            0.349206 |       0.269841 |
| extra_trees_with_pretrigger |    58 |  72 |         0.232269 |        0.464494 |            0.277778 |       0.236111 |
| extra_trees_with_pretrigger |    59 | 749 |         0.233816 |        0.298055 |            0.29506  |       0.333778 |
| extra_trees_with_pretrigger |    60 | 802 |         0.212005 |        0.228444 |            0.214464 |       0.32793  |
| extra_trees_with_pretrigger |    61 | 925 |         0.196737 |        0.214538 |            0.198919 |       0.363243 |
| extra_trees_with_pretrigger |    62 | 798 |         0.187907 |        0.249331 |            0.220551 |       0.384712 |
| extra_trees_with_pretrigger |    63 | 365 |         0.21791  |        0.352797 |            0.276712 |       0.364384 |
| extra_trees_with_pretrigger |    65 |  63 |         0.280464 |        0.552683 |            0.349206 |       0.301587 |

## 6. Pretrigger risk stratification

| method                                  | pretrigger_risk_group   |    n |   bias_median_frac |   res68_abs_frac |   full_rms_frac |   catastrophic_rate |   within_10pct |
|:----------------------------------------|:------------------------|-----:|-------------------:|-----------------:|----------------:|--------------------:|---------------:|
| traditional_huber_ridge                 | high_pretrigger         |  757 |          0.0201136 |         0.252688 |        0.368679 |            0.327609 |      0.272127  |
| traditional_huber_ridge                 | quiet_reference         | 3017 |         -0.0125802 |         0.212607 |        0.301599 |            0.240305 |      0.353994  |
| gradient_boosted_trees_no_pretrigger    | high_pretrigger         |  757 |         -0.0141975 |         0.230191 |        0.292606 |            0.281374 |      0.336856  |
| gradient_boosted_trees_no_pretrigger    | quiet_reference         | 3017 |         -0.0169603 |         0.208546 |        0.259845 |            0.22771  |      0.350017  |
| gradient_boosted_trees_with_pretrigger  | high_pretrigger         |  757 |         -0.0134024 |         0.229436 |        0.292781 |            0.282695 |      0.331572  |
| gradient_boosted_trees_with_pretrigger  | quiet_reference         | 3017 |         -0.0176643 |         0.207485 |        0.265102 |            0.226052 |      0.336095  |
| extra_trees_with_pretrigger             | high_pretrigger         |  757 |         -0.0110996 |         0.227379 |        0.274932 |            0.277411 |      0.335535  |
| extra_trees_with_pretrigger             | quiet_reference         | 3017 |         -0.0132809 |         0.205233 |        0.272216 |            0.227378 |      0.354988  |
| duplicate_transfer_hgb_new_architecture | high_pretrigger         |  757 |         -0.938033  |         0.965181 |        2.05297  |            0.844122 |      0.0739762 |
| duplicate_transfer_hgb_new_architecture | quiet_reference         | 3017 |          3.37306   |         4.09688  |        3.77859  |            0.839576 |      0.0725887 |

In the P04m matched-cell duplicate-readout test, high-pretrigger cells have positive excess absolute fractional error even after run, stave, amplitude-bin, peak-bin, and saturation matching:

| method                             | contrast                              | matched_controls                        |   n_cells |   delta_abs_frac | delta_abs_frac_ci95    |
|:-----------------------------------|:--------------------------------------|:----------------------------------------|----------:|-----------------:|:-----------------------|
| ML_extratrees_without_pretrigger   | high_pretrigger_minus_quiet_reference | run+stave+amp_bin+peak_bin+is_saturated |       177 |        0.0516936 | [0.0440058, 0.0588332] |
| traditional_dropout_cell_corrected | high_pretrigger_minus_quiet_reference | run+stave+amp_bin+peak_bin+is_saturated |       177 |        1.35763   | [1.25173, 1.45962]     |
| ML_hgb_with_pretrigger             | high_pretrigger_minus_quiet_reference | run+stave+amp_bin+peak_bin+is_saturated |       177 |        0.0422818 | [0.0348425, 0.0508669] |
| ML_hgb_without_pretrigger          | high_pretrigger_minus_quiet_reference | run+stave+amp_bin+peak_bin+is_saturated |       177 |        0.0420967 | [0.034843, 0.0487959]  |

## 7. Required method-family context

The predecessor P04m raw-ROOT benchmark contains the full method family requested by the fleet prompt. P04n uses it as context and reranks the external validation endpoint above.

| p04n_method_family                     | method                             |      n |   res68_abs_frac | res68_ci95             |   full_rms_frac |   catastrophic_rate |
|:---------------------------------------|:-----------------------------------|-------:|-----------------:|:-----------------------|----------------:|--------------------:|
| gradient_boosted_trees_with_pretrigger | ML_hgb_with_pretrigger             | 125078 |        0.0161867 | [0.0134494, 0.0183962] |       0.0472092 |          0.00486896 |
| ridge_with_pretrigger                  | ML_ridge_with_pretrigger           | 125078 |        0.0249422 | [0.021863, 0.028134]   |       0.168785  |          0.0436847  |
| traditional_dropout_cell_corrected     | traditional_dropout_cell_corrected | 125078 |        0.0310563 | [0.025365, 0.0367393]  |       1.03899   |          0.125706   |
| mlp                                    | ML_mlp                             | 125078 |        0.0357687 | [0.0289788, 0.0414706] |       0.10536   |          0.0246086  |
| new_pretrigger_gated_wave_net          | NN_pretrigger_gated_wave_net_new   | 125078 |        0.0533973 | [0.041239, 0.0629326]  |       0.222596  |          0.0552855  |
| 1d_cnn                                 | NN_1d_cnn                          | 125078 |        0.374689  | [0.307653, 0.438488]   |       1.63052   |          0.456467   |

The new architecture row is `NN_pretrigger_gated_wave_net_new`: a temporal convolution whose waveform embedding is gated by train-fold pretrigger summary features. It did not beat the tree methods on the P04m duplicate endpoint and has no direct forced/random truth target here because the pedestal source is absent.

## 8. Systematics and caveats

- The direct forced/random pedestal validation is blocked by missing non-beam B-stack ROOT, not by model choice.
- The external endpoint is a downstream charge proxy, not deposited-energy truth.
- P04m/P04n high-pretrigger labels are derived from physics-event samples 0--3; they are support diagnostics, not causal forced-pedestal labels.
- The seven-run held-out set is small; run-block bootstrap CIs are therefore the correct uncertainty scale and remain broad for the external proxy.
- P04m duplicate closure can overstate performance because the target is a same-event duplicate readout. The external proxy is intentionally harsher.

## 9. Verdict and hypothesis

The high-pretrigger P04m cells are likely electronics-support boundary markers that expose charge-transfer fragility, but without true forced/random pedestal rows they cannot be interpreted as independently measured pedestal disturbances. The external proxy still favors tree-based waveform/context models over the traditional Huber comparator, while the same-event duplicate closure remains much sharper than downstream transfer.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.py --config configs/p04n_1781101446_892_139c702a_forced_random_pedestal_validation.json
```

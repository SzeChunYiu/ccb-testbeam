# P04m: Pretrigger-mode charge-transfer abstention map

- **Ticket:** `1781032084.548.4ccc082b`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Primary split:** train on Sample I plus run 64, hold out Sample II analysis runs `58, 59, 60, 61, 62, 63, 65`.

## Abstract

Raw selected-pulse reproduction passes exactly (640737 vs 640737). The duplicate-readout winner is ML_extratrees_without_pretrigger with res68 0.0074 [0.0053, 0.0092], while the strongest traditional method is traditional_dropout_cell_corrected at 0.0311. The best external downstream-charge proxy is external_extratrees_with_pretrigger with res68 0.2098, much wider than duplicate closure, so pretrigger support should be treated as a nuisance/abstention map rather than evidence of external energy recovery.

## 1. Raw ROOT reproduction gate

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

The gate subtracts each channel's median over samples 0--3, reshapes `HRDv` to `(8,18)`, and selects B2/B4/B6/B8 even-channel records with peak amplitude greater than 1000 ADC. This reproduces the P04/S00 count before invalid duplicate targets are removed.

## 2. Estimands and equations

For selected pulse `i`, the duplicate-readout charge target is

`y_i^dup = sum_t max(-o_i(t), 0)`,

where `o_i(t)` is the paired odd-channel waveform after the same baseline subtraction. For penetrating B2 events, the external proxy is

`y_i^ext = sum_{s in {B4,B6,B8}} sum_t max(x_{i,s}(t), 0)`.

Every method is scored by fractional residual `r_i = (hat y_i - y_i) / max(y_i, 1)`. The primary metric is `Q_0.68(|r|)`; full RMS, median bias, and `P(|r|>0.25)` are secondary. Confidence intervals resample held-out runs with replacement.

## 3. Methods

Traditional estimators include peak, positive integral, shifted adaptive-template scale, Huber regression on hand-built pulse and pretrigger summaries, and a frozen dropout-cell correction. ML/NN estimators include ridge, histogram gradient-boosted trees, ExtraTrees, a tabular MLP, waveform-only 1D-CNN, the prior wave-atom net, and the new `NN_pretrigger_gated_wave_net_new`, which gates a temporal convolution by pretrigger summary features. Pretrigger modes are frozen train-run quantile bins of baseline score, slope, and range.

## 4. Duplicate-readout benchmark

| method                              |      n |   bias_median_frac |   res68_abs_frac | res68_ci95                                    |   full_rms_frac |   catastrophic_rate | catastrophic_rate_ci95                        |
|:------------------------------------|-------:|-------------------:|-----------------:|:----------------------------------------------|----------------:|--------------------:|:----------------------------------------------|
| ML_extratrees_without_pretrigger    | 125078 |        0.000295516 |       0.00737763 | [0.0052856926842323425, 0.009176343084954786] |       0.0813901 |          0.00731544 | [0.00513341478041411, 0.008972716696226169]   |
| ML_extratrees_with_pretrigger       | 125078 |        0.000350408 |       0.0074429  | [0.005044777472859754, 0.009425023644912751]  |       0.0573659 |          0.00596428 | [0.004072053453364042, 0.007440606106322676]  |
| ML_hgb_with_pretrigger              | 125078 |        0.000903492 |       0.0161867  | [0.013449432337012667, 0.018396167658845802]  |       0.0472092 |          0.00486896 | [0.003314694869275303, 0.006159193794785278]  |
| ML_hgb_without_pretrigger           | 125078 |        0.000960666 |       0.0163059  | [0.01334181115810893, 0.018592249982590545]   |       0.0494975 |          0.00466909 | [0.0030663023648214607, 0.005925773688150513] |
| ML_ridge_with_pretrigger            | 125078 |        0.000917046 |       0.0249422  | [0.021862959422171122, 0.02813398219645024]   |       0.168785  |          0.0436847  | [0.03147135670860432, 0.0517259741258709]     |
| traditional_dropout_cell_corrected  | 125078 |       -0.00295366  |       0.0310563  | [0.025364953261856015, 0.036739308678197614]  |       1.03899   |          0.125706   | [0.08705830905086823, 0.1506709570264118]     |
| ML_mlp                              | 125078 |        0.00299468  |       0.0357687  | [0.028978814253583562, 0.041470635045319816]  |       0.10536   |          0.0246086  | [0.017107064504720798, 0.029989567261539073]  |
| NN_wave_atom_net                    | 125078 |        0.0101244   |       0.046404   | [0.03626166321337223, 0.05508614218607545]    |       0.15235   |          0.041726   | [0.030193165090619627, 0.049526562255141585]  |
| NN_pretrigger_gated_wave_net_new    | 125078 |        0.00195332  |       0.0533973  | [0.04123901575803757, 0.0629325732588768]     |       0.222596  |          0.0552855  | [0.03911122804162077, 0.06601673720672627]    |
| traditional_strong_huber_pretrigger | 125078 |        0.0251891   |       0.156465   | [0.1224431278084567, 0.1822680515226422]      |       0.653157  |          0.232223   | [0.20123831178242427, 0.25833247649182994]    |
| traditional_integral_logcal         | 125078 |       -0.107371    |       0.186395   | [0.16537060222399833, 0.20063321922652366]    |       1.75017   |          0.21202    | [0.15688109892892899, 0.24006155742941426]    |
| traditional_peak_logcal             | 125078 |       -0.232842    |       0.318023   | [0.28906381052944824, 0.334897733209477]      |       1.97456   |          0.553271   | [0.5074193719133167, 0.5837693420365554]      |
| NN_1d_cnn                           | 125078 |       -0.0254384   |       0.374689   | [0.30765259191393857, 0.4384879775345325]     |       1.63052   |          0.456467   | [0.39570405986234614, 0.4960809271480172]     |
| traditional_adaptive_template       | 125078 |        0.13834     |       0.538691   | [0.4615396874536814, 0.6335739515467035]      |       2.78926   |          0.560274   | [0.4885486129570595, 0.5994162429257608]      |

Winner by held-out duplicate res68: `ML_extratrees_without_pretrigger`. Best traditional comparator: `traditional_dropout_cell_corrected`.

## 5. Run stability

| method                             |   run |     n |   res68_abs_frac |   full_rms_frac |   catastrophic_rate |
|:-----------------------------------|------:|------:|-----------------:|----------------:|--------------------:|
| traditional_dropout_cell_corrected |    58 | 16780 |       0.0198562  |       0.274898  |          0.0247318  |
| traditional_dropout_cell_corrected |    59 | 21374 |       0.0418019  |       1.14929   |          0.166464   |
| traditional_dropout_cell_corrected |    60 | 17021 |       0.0369028  |       1.29673   |          0.148052   |
| traditional_dropout_cell_corrected |    61 | 18963 |       0.0351752  |       1.30795   |          0.141855   |
| traditional_dropout_cell_corrected |    62 | 19088 |       0.0364141  |       0.901886  |          0.144646   |
| traditional_dropout_cell_corrected |    63 | 18814 |       0.0308192  |       0.970375  |          0.129478   |
| traditional_dropout_cell_corrected |    65 | 13038 |       0.0288211  |       0.927631  |          0.103007   |
| ML_hgb_with_pretrigger             |    58 | 16780 |       0.00964593 |       0.0216272 |          0.00101311 |
| ML_hgb_with_pretrigger             |    59 | 21374 |       0.0189535  |       0.055652  |          0.00664359 |
| ML_hgb_with_pretrigger             |    60 | 17021 |       0.0179853  |       0.0536095 |          0.00464133 |
| ML_hgb_with_pretrigger             |    61 | 18963 |       0.0198779  |       0.0456963 |          0.00453515 |
| ML_hgb_with_pretrigger             |    62 | 19088 |       0.0181712  |       0.0489287 |          0.00555323 |
| ML_hgb_with_pretrigger             |    63 | 18814 |       0.0155672  |       0.0499582 |          0.00722866 |
| ML_hgb_with_pretrigger             |    65 | 13038 |       0.0140263  |       0.0424968 |          0.00329805 |
| ML_extratrees_without_pretrigger   |    58 | 16780 |       0.00302812 |       0.0353498 |          0.00202622 |
| ML_extratrees_without_pretrigger   |    59 | 21374 |       0.0100599  |       0.0964145 |          0.0103865  |
| ML_extratrees_without_pretrigger   |    60 | 17021 |       0.00864242 |       0.111617  |          0.0062276  |
| ML_extratrees_without_pretrigger   |    61 | 18963 |       0.00983888 |       0.0940067 |          0.00901756 |
| ML_extratrees_without_pretrigger   |    62 | 19088 |       0.00877598 |       0.0742822 |          0.00859179 |
| ML_extratrees_without_pretrigger   |    63 | 18814 |       0.0069573  |       0.0652199 |          0.00855746 |
| ML_extratrees_without_pretrigger   |    65 | 13038 |       0.0056716  |       0.0580366 |          0.00437184 |
| NN_1d_cnn                          |    58 | 16780 |       0.238711   |       0.63873   |          0.272825   |
| NN_1d_cnn                          |    59 | 21374 |       0.481235   |       1.8183    |          0.510574   |
| NN_1d_cnn                          |    60 | 17021 |       0.388672   |       1.88213   |          0.485165   |
| NN_1d_cnn                          |    61 | 18963 |       0.385756   |       1.86095   |          0.495755   |
| NN_1d_cnn                          |    62 | 19088 |       0.423312   |       1.72227   |          0.498009   |
| NN_1d_cnn                          |    63 | 18814 |       0.374119   |       1.51751   |          0.437281   |
| NN_1d_cnn                          |    65 | 13038 |       0.46763    |       1.49418   |          0.476377   |

## 6. Pretrigger-mode support effects

| method                             | contrast                              |   n_cells |   delta_abs_frac | delta_abs_frac_ci95                        |
|:-----------------------------------|:--------------------------------------|----------:|-----------------:|:-------------------------------------------|
| ML_extratrees_without_pretrigger   | high_pretrigger_minus_quiet_reference |       177 |        0.0516936 | [0.0440058113051316, 0.05883319741495225]  |
| traditional_dropout_cell_corrected | high_pretrigger_minus_quiet_reference |       177 |        1.35763   | [1.2517341506439645, 1.4596159938769548]   |
| ML_hgb_with_pretrigger             | high_pretrigger_minus_quiet_reference |       177 |        0.0422818 | [0.03484249581417634, 0.05086687676669042] |
| ML_hgb_without_pretrigger          | high_pretrigger_minus_quiet_reference |       177 |        0.0420967 | [0.03484295584798306, 0.0487958508324434]  |

Positive `delta_abs_frac` means high-pretrigger records have larger absolute fractional charge error after matching on run, stave, amplitude bin, peak bin, and saturation.

## 7. Conformal abstention

| quantity | value |
|---|---:|
| conformal abs-frac threshold | 0.0127775 |
| nominal coverage | 0.9 |
| coverage without abstention | 0.780233 |
| coverage after pretrigger abstention | 0.919282 |
| support loss | 0.20811 |
| retained res68 | 0.00448008 |

This is a diagnostic abstention map, not a deployed uncertainty guarantee: the nonconformity threshold is learned on train-run residuals for the winning model and the abstention rule is a frozen pretrigger-score quantile.

## 8. External downstream charge proxy

| method                              |    n |   bias_median_frac |   res68_abs_frac | res68_ci95                                 |   full_rms_frac |   catastrophic_rate | catastrophic_rate_ci95                     |
|:------------------------------------|-----:|-------------------:|-----------------:|:-------------------------------------------|----------------:|--------------------:|:-------------------------------------------|
| external_extratrees_with_pretrigger | 3774 |        -0.0132384  |         0.209761 | [0.19937421911692257, 0.22559365655126268] |        0.272763 |            0.237414 | [0.21161244258889192, 0.27433669172545555] |
| external_hgb_with_pretrigger        | 3774 |        -0.016913   |         0.212039 | [0.2028801016517608, 0.22606976229059841]  |        0.270881 |            0.237414 | [0.2136323983627662, 0.2747426567553685]   |
| external_hgb_without_pretrigger     | 3774 |        -0.0165154  |         0.212872 | [0.20501066661930756, 0.23052849227168934] |        0.266739 |            0.238474 | [0.2166751648323456, 0.2782060630254838]   |
| external_traditional_ridge          | 3774 |        -0.00587118 |         0.219784 | [0.20230116474162405, 0.2619237048403918]  |        0.316197 |            0.257817 | [0.2202034119420692, 0.3325873800285322]   |
| external_duplicate_transfer_hgb     | 3774 |         2.75382    |         3.82999  | [0.9327823794698599, 4.293110479791567]    |        3.50132  |            0.840488 | [0.5342623285805105, 0.9974399868371674]   |

External proxy stratified by pretrigger risk group:

| method                              | pretrigger_risk_group   |    n |   bias_median_frac |   res68_abs_frac |   full_rms_frac |   catastrophic_rate |
|:------------------------------------|:------------------------|-----:|-------------------:|-----------------:|----------------:|--------------------:|
| external_traditional_ridge          | high_pretrigger         |  757 |          0.0201136 |         0.252688 |        0.368679 |            0.327609 |
| external_traditional_ridge          | quiet_reference         | 3017 |         -0.0125802 |         0.212607 |        0.301599 |            0.240305 |
| external_hgb_without_pretrigger     | high_pretrigger         |  757 |         -0.0141975 |         0.230191 |        0.292606 |            0.281374 |
| external_hgb_without_pretrigger     | quiet_reference         | 3017 |         -0.0169603 |         0.208546 |        0.259845 |            0.22771  |
| external_hgb_with_pretrigger        | high_pretrigger         |  757 |         -0.0134024 |         0.229436 |        0.292781 |            0.282695 |
| external_hgb_with_pretrigger        | quiet_reference         | 3017 |         -0.0176643 |         0.207485 |        0.265102 |            0.226052 |
| external_extratrees_with_pretrigger | high_pretrigger         |  757 |         -0.0110996 |         0.227379 |        0.274932 |            0.277411 |
| external_extratrees_with_pretrigger | quiet_reference         | 3017 |         -0.0132809 |         0.205233 |        0.272216 |            0.227378 |
| external_duplicate_transfer_hgb     | high_pretrigger         |  757 |         -0.938033  |         0.965181 |        2.05297  |            0.844122 |
| external_duplicate_transfer_hgb     | quiet_reference         | 3017 |          3.37306   |         4.09688  |        3.77859  |            0.839576 |

The external target is not deposited-energy truth; it is a downstream charge proxy in penetrating Sample-II events. It tests whether duplicate-readout charge closure transfers to an independently located charge observable.

## 9. Systematics and caveats

- Splits are by run; event identifiers and odd/downstream target samples are excluded from model features.
- Duplicate-readout closure can be excellent because the target is same-event electronics, not absolute energy.
- Pretrigger modes are derived from samples 0--3. They are support variables and nuisance diagnostics, not causal interventions.
- The held-out run count is seven, so run-block CIs are the relevant uncertainty scale.
- Neural rows are intentionally laptop-scale probes; they test whether extra capacity changes the conclusion, not whether an exhaustive NN search is complete.

## 10. Hypothesis and next step

Pretrigger hidden modes mark electronics support boundaries: within the B-stack duplicate channel they mostly identify where ordinary charge estimators need abstention or correction, but they do not by themselves make same-event duplicate closure transfer to downstream charge. A forced/random pedestal or independently blinded energy proxy should confirm whether the high-pretrigger support loss is an electronics-only nuisance.

Proposed follow-up ticket: `P04n: forced-random pedestal validation of P04m pretrigger abstention` (`1781101446.892.139c702a`)

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.py --config configs/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.json
```

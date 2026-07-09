# P04n External Calibration Charge-Proxy Validation of P04f Anomaly Bias

- **Ticket:** `1781105308.1461.12695cf1`
- **Worker:** `testbeam-laptop-1`
- **Question:** do P04f baseline-excursion and early-pretrigger bias deltas persist against a detector-external charge scale rather than same-event B/A charge transfer?
- **External charge scales available:** P04b downstream B4+B6+B8 charge and P04c selected A1/A3 charge. A true forced/random calibration-pulse B-stack ROOT source is not present in the accessible mirror.
- **Split:** leave-one-run-out; every scored run is predicted by a fit that excludes that run.
- **CIs:** percentile bootstrap over run blocks.

## Abstract

Raw ROOT selected-pulse reproduction passes exactly (640,737 vs 640,737; delta +0). The accessible data mirror has no dedicated forced/random calibration-pulse B-stack ROOT source (0 keyword ROOT candidates; trigger codes [1]), so the independent validation endpoint is the detector-external charge-proxy pair from P04b/P04c. Across traditional_strong, ridge, gradient_boosted_trees, mlp, cnn1d, and residual_cnn_meta, the cross-target winner is residual_cnn_meta; its P04b/P04c res68 values are p04b_downstream=0.2111 [0.1973, 0.2287], p04c_ab_charge=0.5199 [0.5093, 0.5375].

## 1. Raw ROOT Reproduction

The raw reproduction was rerun from `data/root/root/hrdb_run_NNNN.root`, reading `h101/HRDv`, reshaping each event to 8 channels by 18 samples, subtracting the median of samples 0--3 per channel, and counting B2/B4/B6/B8 pulses whose baseline-subtracted peak exceeds 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulses | 640,737 | 640,737 | +0 | true |

Per-run counts are in `raw_reproduction_counts.csv`.

## 2. Calibration/Forced-Random Source Audit

The predecessor forced/random audit found no dedicated non-beam B-stack ROOT source. The available ROOT files contain only trigger code 1, so this ticket cannot claim a direct electronics-pedestal calibration-pulse validation.

| audit item | value |
|---|---:|
| B-stack raw ROOT files | 53 |
| nonempty B-stack raw ROOT files | 51 |
| unique trigger codes | 1 |
| files with TRIGGER != 1 | 0 |
| keyword ROOT files for forced/random/pedestal | 0 |
| dedicated forced/random pedestal ROOT found | false |

The scientifically defensible interpretation is therefore external charge-proxy validation, not forced/random pedestal truth.

## 3. Methods and Equations

For each external target charge \(y_i\), predictions \(\hat y_i\) are evaluated with fractional residual

\[ r_i = \frac{\hat y_i - y_i}{\max(y_i, 1)}. \]

The primary resolution metric is

\[ \mathrm{res68} = Q_{0.68}(|r_i|), \]

with median bias, full RMS, \(P(|r_i|>0.25)\), and within-10/25% rates as diagnostics. Matched anomaly deltas are

\[ \Delta_m = m(\mathcal{A}) - m(\mathcal{C}), \]

where \(\mathcal{C}\) is sampled within the same run, source stave, B2 amplitude bin, and saturation bin.

The benchmark panel is: strong traditional log-linear charge transfer, Ridge regression, histogram gradient-boosted trees, MLP, 1D-CNN, and the new `residual_cnn_meta` architecture. The new architecture learns a log-residual correction to the traditional predictor using a compact convolutional waveform encoder plus metadata.

## 4. Run-Held-Out Benchmark

| dataset         | method                 |    n |   bias_median_frac | bias_ci95          |   res68_abs_frac | res68_ci95       |   high_bias_tail_fraction | high_bias_tail_ci95   |   within_25pct |
|:----------------|:-----------------------|-----:|-------------------:|:-------------------|-----------------:|:-----------------|--------------------------:|:----------------------|---------------:|
| p04b_downstream | cnn1d                  | 3774 |         -0.010968  | [-0.0492, 0.0367]  |          0.21035 | [0.2013, 0.2275] |                   0.23185 | [0.2096, 0.2655]      |        0.76815 |
| p04b_downstream | residual_cnn_meta      | 3774 |         -0.0079639 | [-0.0487, 0.0449]  |          0.21111 | [0.1973, 0.2287] |                   0.23397 | [0.2037, 0.2780]      |        0.76603 |
| p04b_downstream | ridge                  | 3774 |         -0.019337  | [-0.0581, 0.0371]  |          0.21258 | [0.2000, 0.2282] |                   0.24669 | [0.2211, 0.2826]      |        0.75331 |
| p04b_downstream | gradient_boosted_trees | 3774 |         -0.015913  | [-0.0608, 0.0320]  |          0.21404 | [0.2035, 0.2282] |                   0.2337  | [0.2101, 0.2699]      |        0.7663  |
| p04b_downstream | traditional_strong     | 3774 |         -0.025152  | [-0.0827, 0.0362]  |          0.22688 | [0.2155, 0.2461] |                   0.26895 | [0.2349, 0.3118]      |        0.73105 |
| p04b_downstream | mlp                    | 3774 |         -0.02237   | [-0.0610, 0.0199]  |          0.36241 | [0.3367, 0.3912] |                   0.48119 | [0.4524, 0.5254]      |        0.51881 |
| p04c_ab_charge  | residual_cnn_meta      | 4055 |         -0.029386  | [-0.0483, 0.0104]  |          0.51989 | [0.5093, 0.5375] |                   0.65672 | [0.6365, 0.6779]      |        0.34328 |
| p04c_ab_charge  | traditional_strong     | 4055 |         -0.050383  | [-0.0691, -0.0220] |          0.51996 | [0.5064, 0.5376] |                   0.65746 | [0.6369, 0.6763]      |        0.34254 |
| p04c_ab_charge  | cnn1d                  | 4055 |         -0.022786  | [-0.0451, 0.0052]  |          0.52076 | [0.5089, 0.5388] |                   0.65425 | [0.6376, 0.6711]      |        0.34575 |
| p04c_ab_charge  | ridge                  | 4055 |         -0.04909   | [-0.0669, -0.0172] |          0.52502 | [0.5087, 0.5394] |                   0.66042 | [0.6424, 0.6784]      |        0.33958 |
| p04c_ab_charge  | gradient_boosted_trees | 4055 |         -0.035728  | [-0.0640, -0.0103] |          0.53066 | [0.5167, 0.5495] |                   0.66609 | [0.6478, 0.6848]      |        0.33391 |
| p04c_ab_charge  | mlp                    | 4055 |         -0.029261  | [-0.0539, 0.0094]  |          0.62995 | [0.6118, 0.6450] |                   0.72947 | [0.7166, 0.7435]      |        0.27053 |

Winner by mean rank across the two external targets: **residual_cnn_meta**. Best traditional comparator: **traditional_strong**.

## 5. Matched P04f Anomaly Deltas

Positive deltas mean the anomaly stratum is worse than matched normal controls.

| dataset         | anomaly_stratum        | control_stratum                           | method                 |   n_anomaly |   n_control |   delta_bias_median_frac |   delta_res68_abs_frac | delta_res68_ci95   |   delta_high_bias_tail_fraction | delta_high_bias_tail_ci95   |
|:----------------|:-----------------------|:------------------------------------------|:-----------------------|------------:|------------:|-------------------------:|-----------------------:|:-------------------|--------------------------------:|:----------------------------|
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | cnn1d                  |          18 |          18 |               0.023392   |             -0.020318  | [-0.0732, 0.0612]  |                       -0.055556 | [-0.2000, 0.1538]           |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | gradient_boosted_trees |          18 |          18 |              -0.0040359  |             -0.041185  | [-0.1241, 0.0638]  |                       -0.11111  | [-0.4091, 0.4004]           |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | mlp                    |          18 |          18 |              -0.25809    |              0.42056   | [0.0491, 2.8570]   |                        0        | [-0.2000, 0.1037]           |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | residual_cnn_meta      |          18 |          18 |               0.0066141  |              0.011919  | [-0.1213, 0.2110]  |                        0.055556 | [-0.3000, 0.5833]           |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | ridge                  |          18 |          18 |              -0.051492   |              0.10413   | [0.0235, 0.2019]   |                        0.22222  | [0.1000, 0.2692]            |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | traditional_strong     |          18 |          18 |              -0.15737    |              0.030252  | [-0.1039, 0.2892]  |                        0        | [-0.5000, 0.2609]           |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | cnn1d                  |          74 |          74 |               0.00032917 |             -0.0013727 | [-0.0572, 0.0715]  |                       -0.027027 | [-0.1205, 0.0889]           |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | gradient_boosted_trees |          74 |          74 |              -0.0025208  |             -0.023891  | [-0.0601, 0.0434]  |                       -0.027027 | [-0.1136, 0.1461]           |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | mlp                    |          74 |          74 |              -0.037616   |              0.29658   | [0.1067, 0.4458]   |                        0.16216  | [0.0278, 0.3080]            |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | residual_cnn_meta      |          74 |          74 |              -0.012196   |             -0.030478  | [-0.0951, 0.0410]  |                       -0.040541 | [-0.1548, 0.1489]           |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | ridge                  |          74 |          74 |               0.050491   |              0.060425  | [0.0125, 0.1599]   |                        0.040541 | [-0.1529, 0.2182]           |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | traditional_strong     |          74 |          74 |               0.16469    |              0.082091  | [-0.0492, 0.3293]  |                        0.17568  | [-0.0607, 0.5002]           |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | cnn1d                  |          54 |          53 |               0.020748   |              0.15476   | [-0.0694, 0.3938]  |                        0.080014 | [-0.0701, 0.1897]           |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | gradient_boosted_trees |          54 |          53 |               0.13074    |              0.090659  | [-0.0352, 0.4333]  |                        0.042628 | [-0.1000, 0.1756]           |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | mlp                    |          54 |          53 |              -0.15039    |              0.30748   | [-0.0515, 1.7054]  |                        0.078267 | [-0.0600, 0.2031]           |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | residual_cnn_meta      |          54 |          53 |               0.048499   |              0.1326    | [-0.0249, 0.3966]  |                        0.080363 | [-0.0715, 0.2132]           |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | ridge                  |          54 |          53 |               0.049454   |              0.096965  | [-0.0270, 0.3792]  |                        0.098882 | [-0.0870, 0.2326]           |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | traditional_strong     |          54 |          53 |               0.065037   |              0.14158   | [-0.0450, 0.4860]  |                        0.061146 | [-0.1165, 0.2131]           |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | cnn1d                  |         182 |         179 |               0.055668   |             -0.038003  | [-0.1215, 0.0160]  |                       -0.01059  | [-0.0915, 0.0888]           |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | gradient_boosted_trees |         182 |         179 |              -0.0015582  |             -0.081358  | [-0.1548, -0.0104] |                       -0.077261 | [-0.1667, 0.0398]           |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | mlp                    |         182 |         179 |               0.21722    |              0.11677   | [0.0205, 0.2948]   |                        0.065596 | [-0.0213, 0.1535]           |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | residual_cnn_meta      |         182 |         179 |               0.024933   |             -0.039977  | [-0.1219, 0.0509]  |                       -0.038247 | [-0.1242, 0.0750]           |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | ridge                  |         182 |         179 |               0.087209   |             -0.033562  | [-0.1149, 0.0105]  |                       -0.049604 | [-0.1215, 0.0343]           |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | traditional_strong     |         182 |         179 |              -0.024631   |             -0.039431  | [-0.1042, 0.0099]  |                       -0.021855 | [-0.1049, 0.0749]           |

## 6. Run-Level Stability and Fold Audit

| dataset         |   run | method             |   n |   bias_median_frac |   res68_abs_frac |   high_bias_tail_fraction |   baseline_excursion_n |   novel_early_pretrigger_n |
|:----------------|------:|:-------------------|----:|-------------------:|-----------------:|--------------------------:|-----------------------:|---------------------------:|
| p04b_downstream |    58 | traditional_strong |  72 |          0.053398  |          0.32112 |                   0.41667 |                      0 |                          2 |
| p04b_downstream |    58 | residual_cnn_meta  |  72 |          0.013321  |          0.23772 |                   0.29167 |                      0 |                          2 |
| p04b_downstream |    59 | traditional_strong | 749 |          0.04821   |          0.23464 |                   0.28838 |                      4 |                         14 |
| p04b_downstream |    59 | residual_cnn_meta  | 749 |          0.05718   |          0.23797 |                   0.29773 |                      4 |                         14 |
| p04b_downstream |    60 | traditional_strong | 802 |         -0.12092   |          0.24537 |                   0.31047 |                      0 |                         21 |
| p04b_downstream |    60 | residual_cnn_meta  | 802 |         -0.090256  |          0.2115  |                   0.21696 |                      0 |                         21 |
| p04b_downstream |    61 | traditional_strong | 925 |         -0.062456  |          0.21256 |                   0.23243 |                      1 |                         19 |
| p04b_downstream |    61 | residual_cnn_meta  | 925 |         -0.038195  |          0.19306 |                   0.19568 |                      1 |                         19 |
| p04b_downstream |    62 | traditional_strong | 798 |         -0.0053559 |          0.21087 |                   0.21053 |                      4 |                         12 |
| p04b_downstream |    62 | residual_cnn_meta  | 798 |          0.019761  |          0.1974  |                   0.19549 |                      4 |                         12 |
| p04b_downstream |    63 | traditional_strong | 365 |          0.045173  |          0.22511 |                   0.29863 |                      7 |                          6 |
| p04b_downstream |    63 | residual_cnn_meta  | 365 |          0.036992  |          0.22474 |                   0.28493 |                      7 |                          6 |
| p04b_downstream |    65 | traditional_strong |  63 |          0.15539   |          0.316   |                   0.44444 |                      2 |                          0 |
| p04b_downstream |    65 | residual_cnn_meta  |  63 |          0.11985   |          0.26311 |                   0.38095 |                      2 |                          0 |
| p04c_ab_charge  |    31 | traditional_strong | 229 |         -0.047989  |          0.56517 |                   0.69432 |                      4 |                          9 |
| p04c_ab_charge  |    31 | residual_cnn_meta  | 229 |         -0.032956  |          0.57141 |                   0.68996 |                      4 |                          9 |
| p04c_ab_charge  |    32 | traditional_strong | 207 |          0.010101  |          0.57481 |                   0.68116 |                      1 |                          4 |
| p04c_ab_charge  |    32 | residual_cnn_meta  | 207 |          0.051111  |          0.57181 |                   0.69565 |                      1 |                          4 |
| p04c_ab_charge  |    33 | traditional_strong |   8 |          0.22577   |          0.44218 |                   0.75    |                      0 |                          0 |
| p04c_ab_charge  |    33 | residual_cnn_meta  |   8 |          0.21772   |          0.4689  |                   0.625   |                      0 |                          0 |
| p04c_ab_charge  |    34 | traditional_strong |  16 |          0.055226  |          0.5272  |                   0.75    |                      0 |                          0 |
| p04c_ab_charge  |    34 | residual_cnn_meta  |  16 |          0.088894  |          0.55318 |                   0.6875  |                      0 |                          0 |
| p04c_ab_charge  |    35 | traditional_strong | 221 |          0.031073  |          0.52111 |                   0.66968 |                      4 |                         10 |
| p04c_ab_charge  |    35 | residual_cnn_meta  | 221 |          0.064808  |          0.51942 |                   0.66516 |                      4 |                         10 |
| p04c_ab_charge  |    36 | traditional_strong | 295 |         -0.023166  |          0.48819 |                   0.61356 |                      5 |                         13 |
| p04c_ab_charge  |    36 | residual_cnn_meta  | 295 |         -0.039286  |          0.49801 |                   0.61017 |                      5 |                         13 |
| p04c_ab_charge  |    37 | traditional_strong | 292 |         -0.071027  |          0.49043 |                   0.60274 |                      3 |                         17 |
| p04c_ab_charge  |    37 | residual_cnn_meta  | 292 |         -0.079156  |          0.48303 |                   0.61644 |                      3 |                         17 |
| p04c_ab_charge  |    39 | traditional_strong | 324 |         -0.091006  |          0.47508 |                   0.66049 |                      5 |                         20 |
| p04c_ab_charge  |    39 | residual_cnn_meta  | 324 |         -0.080337  |          0.47893 |                   0.64198 |                      5 |                         20 |
| p04c_ab_charge  |    40 | traditional_strong | 265 |         -0.058649  |          0.48758 |                   0.61132 |                      6 |                         18 |
| p04c_ab_charge  |    40 | residual_cnn_meta  | 265 |         -0.026386  |          0.49067 |                   0.60755 |                      6 |                         18 |
| p04c_ab_charge  |    41 | traditional_strong | 295 |         -0.11657   |          0.53222 |                   0.69831 |                      8 |                         15 |
| p04c_ab_charge  |    41 | residual_cnn_meta  | 295 |         -0.090326  |          0.53188 |                   0.69153 |                      8 |                         15 |
| p04c_ab_charge  |    42 | traditional_strong | 279 |         -0.051354  |          0.50952 |                   0.64158 |                      1 |                         11 |
| p04c_ab_charge  |    42 | residual_cnn_meta  | 279 |         -0.011135  |          0.51102 |                   0.63799 |                      1 |                         11 |
| p04c_ab_charge  |    44 | traditional_strong |  30 |         -0.15407   |          0.47446 |                   0.7     |                      0 |                          3 |
| p04c_ab_charge  |    44 | residual_cnn_meta  |  30 |         -0.10474   |          0.5115  |                   0.73333 |                      0 |                          3 |
| p04c_ab_charge  |    45 | traditional_strong | 302 |          0.0079484 |          0.51814 |                   0.69205 |                      4 |                         12 |
| p04c_ab_charge  |    45 | residual_cnn_meta  | 302 |          0.014489  |          0.52011 |                   0.70861 |                      4 |                         12 |
| p04c_ab_charge  |    47 | traditional_strong |  92 |         -0.017857  |          0.49746 |                   0.66304 |                      0 |                          4 |
| p04c_ab_charge  |    47 | residual_cnn_meta  |  92 |          0.029522  |          0.50678 |                   0.66304 |                      0 |                          4 |
| p04c_ab_charge  |    48 | traditional_strong | 260 |         -0.10164   |          0.47716 |                   0.62692 |                      5 |                         14 |
| p04c_ab_charge  |    48 | residual_cnn_meta  | 260 |         -0.10066   |          0.48003 |                   0.61154 |                      5 |                         14 |
| p04c_ab_charge  |    49 | traditional_strong | 288 |         -0.095307  |          0.53804 |                   0.69444 |                      3 |                          7 |
| p04c_ab_charge  |    49 | residual_cnn_meta  | 288 |         -0.077661  |          0.53644 |                   0.70139 |                      3 |                          7 |
| p04c_ab_charge  |    50 | traditional_strong |  61 |          0.080195  |          0.592   |                   0.67213 |                      0 |                          2 |
| p04c_ab_charge  |    50 | residual_cnn_meta  |  61 |          0.10516   |          0.6241  |                   0.67213 |                      0 |                          2 |
| p04c_ab_charge  |    51 | traditional_strong |  25 |         -0.029826  |          0.6815  |                   0.72    |                      0 |                          1 |
| p04c_ab_charge  |    51 | residual_cnn_meta  |  25 |         -0.026292  |          0.67123 |                   0.72    |                      0 |                          1 |
| p04c_ab_charge  |    52 | traditional_strong |   6 |         -0.22717   |          0.36272 |                   0.66667 |                      0 |                          0 |
| p04c_ab_charge  |    52 | residual_cnn_meta  |   6 |         -0.20657   |          0.35484 |                   0.5     |                      0 |                          0 |
| p04c_ab_charge  |    53 | traditional_strong |  17 |          0.43117   |          1.0493  |                   0.76471 |                      0 |                          0 |
| p04c_ab_charge  |    53 | residual_cnn_meta  |  17 |          0.43299   |          1.158   |                   0.76471 |                      0 |                          0 |
| p04c_ab_charge  |    54 | traditional_strong |  18 |          0.40621   |          0.65207 |                   0.77778 |                      0 |                          0 |
| p04c_ab_charge  |    54 | residual_cnn_meta  |  18 |          0.45049   |          0.71754 |                   0.77778 |                      0 |                          0 |
| p04c_ab_charge  |    55 | traditional_strong |  27 |         -0.1159    |          0.4721  |                   0.7037  |                      0 |                          1 |
| p04c_ab_charge  |    55 | residual_cnn_meta  |  27 |         -0.11492   |          0.54542 |                   0.66667 |                      0 |                          1 |
| p04c_ab_charge  |    56 | traditional_strong |  68 |          0.068209  |          0.64661 |                   0.72059 |                      0 |                          0 |
| p04c_ab_charge  |    56 | residual_cnn_meta  |  68 |          0.064745  |          0.64729 |                   0.72059 |                      0 |                          0 |
| p04c_ab_charge  |    57 | traditional_strong | 276 |         -0.13441   |          0.54052 |                   0.69928 |                      2 |                         18 |
| p04c_ab_charge  |    57 | residual_cnn_meta  | 276 |         -0.089768  |          0.51344 |                   0.69928 |                      2 |                         18 |
| p04c_ab_charge  |    58 | traditional_strong |  34 |          0.0019196 |          0.50501 |                   0.64706 |                      0 |                          0 |
| p04c_ab_charge  |    58 | residual_cnn_meta  |  34 |          0.034269  |          0.57164 |                   0.64706 |                      0 |                          0 |
| p04c_ab_charge  |    59 | traditional_strong |   9 |         -0.11388   |          0.31205 |                   0.44444 |                      0 |                          0 |
| p04c_ab_charge  |    59 | residual_cnn_meta  |   9 |         -0.093755  |          0.35041 |                   0.55556 |                      0 |                          0 |
| p04c_ab_charge  |    60 | traditional_strong |  10 |          1.4564    |          1.9176  |                   0.9     |                      0 |                          0 |
| p04c_ab_charge  |    60 | residual_cnn_meta  |  10 |          1.2407    |          2.0992  |                   0.9     |                      0 |                          0 |
| p04c_ab_charge  |    61 | traditional_strong |   6 |         -0.064633  |          0.53532 |                   0.33333 |                      0 |                          1 |
| p04c_ab_charge  |    61 | residual_cnn_meta  |   6 |         -0.03883   |          0.6914  |                   0.5     |                      0 |                          1 |
| p04c_ab_charge  |    62 | traditional_strong |   8 |          0.19223   |          0.44192 |                   0.5     |                      1 |                          0 |
| p04c_ab_charge  |    62 | residual_cnn_meta  |   8 |          0.20882   |          0.50733 |                   0.625   |                      1 |                          0 |
| p04c_ab_charge  |    63 | traditional_strong |  39 |         -0.071461  |          0.24363 |                   0.30769 |                      1 |                          2 |
| p04c_ab_charge  |    63 | residual_cnn_meta  |  39 |         -0.059744  |          0.23882 |                   0.30769 |                      1 |                          2 |
| p04c_ab_charge  |    64 | traditional_strong |  35 |          0.10552   |          0.74961 |                   0.51429 |                      1 |                          0 |
| p04c_ab_charge  |    64 | residual_cnn_meta  |  35 |          0.10958   |          0.75061 |                   0.51429 |                      1 |                          0 |
| p04c_ab_charge  |    65 | traditional_strong |  13 |          0.052814  |          0.51015 |                   0.46154 |                      0 |                          0 |
| p04c_ab_charge  |    65 | residual_cnn_meta  |  13 |          0.063939  |          0.56524 |                   0.46154 |                      0 |                          0 |

| dataset         |   heldout_run |   n_train |   n_fit |   n_heldout |   train_heldout_run_overlap |
|:----------------|--------------:|----------:|--------:|------------:|----------------------------:|
| p04b_downstream |            58 |      3702 |    3702 |          72 |                           0 |
| p04b_downstream |            59 |      3025 |    3025 |         749 |                           0 |
| p04b_downstream |            60 |      2972 |    2972 |         802 |                           0 |
| p04b_downstream |            61 |      2849 |    2849 |         925 |                           0 |
| p04b_downstream |            62 |      2976 |    2976 |         798 |                           0 |
| p04b_downstream |            63 |      3409 |    3409 |         365 |                           0 |
| p04b_downstream |            65 |      3711 |    3711 |          63 |                           0 |
| p04c_ab_charge  |            31 |      3826 |    3826 |         229 |                           0 |
| p04c_ab_charge  |            32 |      3848 |    3848 |         207 |                           0 |
| p04c_ab_charge  |            33 |      4047 |    4047 |           8 |                           0 |
| p04c_ab_charge  |            34 |      4039 |    4039 |          16 |                           0 |
| p04c_ab_charge  |            35 |      3834 |    3834 |         221 |                           0 |
| p04c_ab_charge  |            36 |      3760 |    3760 |         295 |                           0 |
| p04c_ab_charge  |            37 |      3763 |    3763 |         292 |                           0 |
| p04c_ab_charge  |            39 |      3731 |    3731 |         324 |                           0 |
| p04c_ab_charge  |            40 |      3790 |    3790 |         265 |                           0 |
| p04c_ab_charge  |            41 |      3760 |    3760 |         295 |                           0 |
| p04c_ab_charge  |            42 |      3776 |    3776 |         279 |                           0 |
| p04c_ab_charge  |            44 |      4025 |    4025 |          30 |                           0 |
| p04c_ab_charge  |            45 |      3753 |    3753 |         302 |                           0 |
| p04c_ab_charge  |            47 |      3963 |    3963 |          92 |                           0 |
| p04c_ab_charge  |            48 |      3795 |    3795 |         260 |                           0 |
| p04c_ab_charge  |            49 |      3767 |    3767 |         288 |                           0 |
| p04c_ab_charge  |            50 |      3994 |    3994 |          61 |                           0 |
| p04c_ab_charge  |            51 |      4030 |    4030 |          25 |                           0 |
| p04c_ab_charge  |            52 |      4049 |    4049 |           6 |                           0 |
| p04c_ab_charge  |            53 |      4038 |    4038 |          17 |                           0 |
| p04c_ab_charge  |            54 |      4037 |    4037 |          18 |                           0 |
| p04c_ab_charge  |            55 |      4028 |    4028 |          27 |                           0 |
| p04c_ab_charge  |            56 |      3987 |    3987 |          68 |                           0 |
| p04c_ab_charge  |            57 |      3779 |    3779 |         276 |                           0 |
| p04c_ab_charge  |            58 |      4021 |    4021 |          34 |                           0 |
| p04c_ab_charge  |            59 |      4046 |    4046 |           9 |                           0 |
| p04c_ab_charge  |            60 |      4045 |    4045 |          10 |                           0 |
| p04c_ab_charge  |            61 |      4049 |    4049 |           6 |                           0 |
| p04c_ab_charge  |            62 |      4047 |    4047 |           8 |                           0 |
| p04c_ab_charge  |            63 |      4016 |    4016 |          39 |                           0 |
| p04c_ab_charge  |            64 |      4020 |    4020 |          35 |                           0 |
| p04c_ab_charge  |            65 |      4042 |    4042 |          13 |                           0 |

## 7. Systematics and Caveats

- The forced/random calibration-pulse premise is limited by missing non-beam B-stack ROOT data in the accessible mirror.
- P04b downstream and P04c A-stack charges are detector-external charge proxies, not beam-truth energy.
- P04c has broader residuals because it is topology-limited by event-matched selected A-stack support.
- The P04f anomaly labels are deterministic products of the P09a waveform taxonomy; bootstrap CIs capture run-to-run variation, not taxonomy-threshold uncertainty.
- Baseline-excursion strata are small in P04b, so matched anomaly delta intervals are broad and should be treated as bounds.
- Shuffled-target sentinels and zero train/held-out run overlap from the predecessor audit are required safeguards against leakage.

## 8. Verdict

P04f baseline-excursion and early-pretrigger effects are not purely artifacts of same-event duplicate transfer: they can be tested against downstream and A-stack external charge proxies, but the matched deltas are small or broad. The result supports retaining the anomaly labels as external-proxy risk covariates while abstaining from a stronger calibration-pulse or forced-random pedestal claim until true non-beam ROOT data are available.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04n_1781105308_1461_12695cf1_external_calibration_charge_proxy_anomaly_bias.py --config configs/p04n_1781105308_1461_12695cf1_external_calibration_charge_proxy_anomaly_bias.json
```

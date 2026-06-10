# P04n B2 Transfer Saturation Support Frontier

- **Ticket:** `1781036493.3330.4f5f1b60`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack `data/root/root/hrdb_run_*.root` loaded through the P04 ROOT reader.
- **Target:** B2 paired odd-channel positive-lobe charge, `q^- = sum(max(-odd, 0))`.
- **Externalization split:** train on selected B4/B6/B8 rows in non-held-out runs; evaluate on selected B2 rows in held-out Sample-II analysis runs.
- **Uncertainty:** 95 percent CIs resample held-out run blocks with replacement.

## 1. Raw-ROOT Reproduction

The entry gate is the original P04/S00 selected-pulse count, rebuilt from `HRDv` before any modeling. For each configured run, the script subtracts the channel median over samples 0--3, selects even B staves B2/B4/B6/B8 with corrected peak amplitude above 1000 ADC, and sums selected pulse records.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| B-stack selected pulse records | 640,737 | 640,737 | +0 | true |

This exactly reproduces the ticket-local raw ROOT number and fixes the analysis population before model fitting.

## 2. Estimand And Split

For pulse record i with corrected even waveform x_i in R^18 and paired inverted duplicate odd waveform o_i, the target is

`y_i = sum_t max(-o_it, 0)`.

All fitted models use x_i and even-channel summaries only. The training index is

`T = {i: stave_i in {B4, B6, B8}, run_i not in heldout}`

and the evaluation index is

`E = {i: stave_i = B2, run_i in heldout}`.

Thus no model is calibrated on B2 rows from the held-out run family. The held-out runs are 58, 59, 60, 61, 62, 63, 65.

## 3. Models

The traditional family intentionally contains high-capacity but physically interpretable estimators: log-linear peak calibration, log-linear integral calibration, shifted median-template scale calibration, and a Huber transfer model on amplitude, integral, width, baseline, saturation, and template-mismatch features. The machine-learning family contains ridge regression, gradient-boosted trees, and a tabular MLP on waveform plus engineered features. The neural-network family contains a 1D-CNN on normalized waveforms with scalar auxiliaries. The new architecture, `template_residual_cnn`, is sensible for this ticket because the support frontier is explicitly about saturation-boundary and q-template departures: it sends both normalized waveform and fold-local template residual channels through a small CNN and gates the latent representation with scalar saturation, baseline, and template-shift features.

For every method m the reported error is fractional, `e_i(m) = (hat y_i(m) - y_i) / max(y_i, 1)`. The primary score is `Q_0.68(|e_i|)`; lower is better. Run-block CIs resample the seven held-out runs rather than individual pulses.

## 4. Head-To-Head Results

| method                   | family           |     n |   bias_median_frac | bias_ci95                                        |   res68_abs_frac | res68_ci95                                   |   full_rms_frac | full_rms_ci95                              |   within_10pct |   within_25pct |
|:-------------------------|:-----------------|------:|-------------------:|:-------------------------------------------------|-----------------:|:---------------------------------------------|----------------:|:-------------------------------------------|---------------:|---------------:|
| gradient_boosted_trees   | ml               | 88196 |        0.00285163  | [0.0023555376309372356, 0.00327395588598776]     |        0.0213192 | [0.019245861336278036, 0.023812690191499827] |        0.310167 | [0.18850881914835158, 0.41968700301858153] |      0.936448  |       0.982539 |
| mlp                      | ml               | 88196 |       -0.000483504 | [-0.0017594321638800892, 0.0006719149269679057]  |        0.0236539 | [0.022301559271929075, 0.02533935931644216]  |        1.51931  | [0.7608751662859159, 2.1481203432259615]   |      0.935723  |       0.979614 |
| ridge                    | ml               | 88196 |       -0.0026458   | [-0.0037595995475697896, -0.0013303149827813214] |        0.0267347 | [0.024838558408778702, 0.029057382399286562] |       28.6268   | [14.476609301680005, 42.438711364805684]   |      0.906504  |       0.962833 |
| saturation_knockout_hgb  | negative_control | 88196 |        0.00191274  | [0.0012805048749690675, 0.0024972617554685993]   |        0.0229537 | [0.020818180930033806, 0.025503245473498574] |        0.279426 | [0.1783771771860242, 0.367210130808132]    |      0.929883  |       0.981156 |
| shuffled_target_hgb      | negative_control | 88196 |       -0.431441    | [-0.5064487271403996, -0.3583783870490831]       |        0.67273   | [0.6565701304198317, 0.6862217889017923]     |        3.69708  | [2.8586880686331906, 4.340942905764851]    |      0.0682911 |       0.180076 |
| template_residual_cnn    | new_architecture | 88196 |       -0.0160673   | [-0.018159190749946454, -0.013494025314515115]   |        0.0486058 | [0.04455892348213033, 0.05337070515256745]   |        0.254089 | [0.1925405153287962, 0.32943025040080015]  |      0.826681  |       0.92401  |
| 1d_cnn                   | nn               | 88196 |       -0.00584049  | [-0.008487634418525417, -0.0034330942412810995]  |        0.0661374 | [0.06059802897072771, 0.07121497014920695]   |        0.426176 | [0.2470076654782294, 0.5985169566603883]   |      0.811227  |       0.911039 |
| strong_huber_transfer    | traditional      | 88196 |        0.00643509  | [0.003607204865931263, 0.009578253163781697]     |        0.041355  | [0.03666243382304092, 0.04604249872197759]   |        0.295938 | [0.2356295687954002, 0.3376690123188991]   |      0.878872  |       0.926777 |
| integral_loglinear       | traditional      | 88196 |       -0.123638    | [-0.1324019544710527, -0.1179866419986454]       |        0.158464  | [0.15582435781322168, 0.16025289074838334]   |        1.68987  | [1.3241889875314627, 1.9841636186797922]   |      0.154134  |       0.862023 |
| peak_loglinear           | traditional      | 88196 |       -0.223415    | [-0.22969201205411274, -0.2165257666781825]      |        0.344059  | [0.2983223554475517, 0.3814249485292356]     |        1.98884  | [1.5280793509210235, 2.34562314252919]     |      0.115822  |       0.462311 |
| template_scale_loglinear | traditional      | 88196 |       -0.270336    | [-0.3330143337558446, -0.22308212033546104]      |        0.498021  | [0.4871167918905953, 0.5044306064360767]     |        1.51526  | [1.2295200306897087, 1.717907723708541]    |      0.140052  |       0.254002 |

The winner by held-out B2 res68 is `gradient_boosted_trees` (`ml`) with res68 `0.02132` and run-block 95 percent CI `[0.019245861336278036, 0.023812690191499827]`. The best traditional method is `strong_huber_transfer` at `0.04135`; the best ML/NN method is `gradient_boosted_trees` at `0.02132`.

## 5. Run-Level Behavior

|   run | method                 |     n |   bias_median_frac |   res68_abs_frac |   full_rms_frac |   within_25pct |
|------:|:-----------------------|------:|-------------------:|-----------------:|----------------:|---------------:|
|    58 | strong_huber_transfer  | 15790 |         0.012846   |        0.0328069 |        0.126541 |       0.974858 |
|    58 | gradient_boosted_trees | 15790 |         0.00304263 |        0.0173275 |        0.089903 |       0.994364 |
|    58 | shuffled_target_hgb    | 15790 |        -0.603357   |        0.698548  |        1.23056  |       0.126662 |
|    59 | strong_huber_transfer  | 13562 |         0.00160613 |        0.051352  |        0.352303 |       0.883498 |
|    59 | gradient_boosted_trees | 13562 |         0.00204317 |        0.0261148 |        0.333994 |       0.96822  |
|    59 | shuffled_target_hgb    | 13562 |        -0.357867   |        0.667502  |        4.18748  |       0.19385  |
|    60 | strong_huber_transfer  |  9865 |         0.00396646 |        0.0432488 |        0.350177 |       0.931475 |
|    60 | gradient_boosted_trees |  9865 |         0.00343839 |        0.0221932 |        0.510645 |       0.987025 |
|    60 | shuffled_target_hgb    |  9865 |        -0.401591   |        0.652227  |        4.90083  |       0.161987 |
|    61 | strong_huber_transfer  | 11013 |         0.00582529 |        0.0442029 |        0.341165 |       0.930173 |
|    61 | gradient_boosted_trees | 11013 |         0.00337323 |        0.0223126 |        0.519425 |       0.985926 |
|    61 | shuffled_target_hgb    | 11013 |        -0.40113    |        0.650884  |        4.40212  |       0.175611 |
|    62 | strong_huber_transfer  | 11634 |         0.00395039 |        0.0450308 |        0.341829 |       0.914819 |
|    62 | gradient_boosted_trees | 11634 |         0.0033841  |        0.0229963 |        0.161711 |       0.979199 |
|    62 | shuffled_target_hgb    | 11634 |        -0.36917    |        0.654412  |        4.37734  |       0.194    |
|    63 | strong_huber_transfer  | 14564 |         0.00552073 |        0.0431056 |        0.286993 |       0.908061 |
|    63 | gradient_boosted_trees | 14564 |         0.0018557  |        0.0230768 |        0.192889 |       0.97432  |
|    63 | shuffled_target_hgb    | 14564 |        -0.42502    |        0.678638  |        3.2541   |       0.189783 |
|    65 | strong_huber_transfer  | 11768 |         0.00540775 |        0.0379305 |        0.250349 |       0.940007 |
|    65 | gradient_boosted_trees | 11768 |         0.00297932 |        0.0182303 |        0.196511 |       0.989718 |
|    65 | shuffled_target_hgb    | 11768 |        -0.303272   |        0.664431  |        3.14346  |       0.229436 |

Run-level spread is the dominant uncertainty source. This is why the headline interval is a run-block bootstrap rather than a row bootstrap.

## 6. Support Frontier

Support cells cross saturation depth, q-template mismatch, baseline excursion, and peak phase. A B2 cell is `strong` when B4/B6/B8 train rows exceed both the strong row and strong run thresholds, `frontier` when it exceeds the weaker thresholds, and `unsupported` otherwise. The accepted B2 fraction is the share of held-out B2 rows in the displayed stratum.

| frontier       | value          |   accepted_b2_fraction |     n |   bias_median_frac |   res68_abs_frac | res68_ci95                                   |   within_25pct |
|:---------------|:---------------|-----------------------:|------:|-------------------:|-----------------:|:---------------------------------------------|---------------:|
| support_tier   | frontier       |              0.20332   | 17932 |        0.0039535   |        0.0243383 | [0.020531007452148153, 0.029190294593107652] |       0.964756 |
| support_tier   | strong         |              0.665212  | 58669 |        0.00390209  |        0.0186254 | [0.016584626387786412, 0.020763165247941334] |       0.990813 |
| support_tier   | unsupported    |              0.131469  | 11595 |       -0.0117361   |        0.0346409 | [0.03000483745994699, 0.04082466542644016]   |       0.968176 |
| saturation_bin | deep_500_1500  |              0.0257835 |  2274 |       -0.0345097   |        0.0479418 | [0.04329379952111331, 0.05893885914466397]   |       0.948109 |
| saturation_bin | edge_0_500     |              0.0185269 |  1634 |       -0.0288852   |        0.0409698 | [0.03693944961525983, 0.04892698766182693]   |       0.958384 |
| saturation_bin | extreme_ge1500 |              0.0163386 |  1441 |       -0.0817949   |        0.144438  | [0.09447748996373367, 0.17190880758551383]   |       0.92297  |
| saturation_bin | none           |              0.939351  | 82847 |        0.00402545  |        0.0196595 | [0.017455486583518177, 0.022088380898594134] |       0.984996 |
| q_template_bin | extreme        |              0.2716    | 23954 |       -0.0174039   |        0.0673062 | [0.05271274764022602, 0.07901977988018662]   |       0.936128 |
| q_template_bin | high           |              0.483639  | 42655 |        0.00664505  |        0.0180728 | [0.016751648041532743, 0.019456086288093855] |       0.999789 |
| q_template_bin | low            |              0.0048755 |   430 |        0.00350895  |        0.0130618 | [0.011876539766608912, 0.014075203445737886] |       1        |
| q_template_bin | moderate       |              0.239886  | 21157 |        0.0026453   |        0.0130079 | [0.012732695315418737, 0.013280415684272694] |       0.999953 |
| baseline_bin   | active         |              0.0200803 |  1771 |        0.000999439 |        0.0217069 | [0.020747541090589752, 0.0231518734283076]   |       0.992095 |
| baseline_bin   | large          |              0.198773  | 17531 |       -0.0281674   |        0.0876034 | [0.08114587628288723, 0.0960780196839002]    |       0.920712 |
| baseline_bin   | mild           |              0.1175    | 10363 |        0.00498691  |        0.0176147 | [0.016892873313256902, 0.0182642831381247]   |       0.997781 |
| baseline_bin   | quiet          |              0.663647  | 58531 |        0.00464089  |        0.0164822 | [0.015817887332003608, 0.01683025861270692]  |       0.998069 |
| peak_phase_bin | central_9_11   |              0.0436528 |  3850 |        0.00580524  |        0.0201241 | [0.019554687892540695, 0.021079606702266232] |       0.988312 |
| peak_phase_bin | early_le5      |              0.121933  | 10754 |       -0.0366027   |        0.0837883 | [0.08180124086817757, 0.08604148830250125]   |       0.941975 |
| peak_phase_bin | late_ge12      |              0.0298426 |  2632 |       -0.0044908   |        0.0273246 | [0.02583407562041758, 0.02864755755622808]   |       0.976064 |
| peak_phase_bin | rising_6_8     |              0.804572  | 70960 |        0.00428492  |        0.0179649 | [0.0168494306406435, 0.0191275577509896]     |       0.988613 |

Top train support cells:

| support_cell                     | support_tier   |   b2_eval_rows |   b2_eval_runs |   train_cell_rows |   train_cell_runs |   median_saturation_depth_adc |   median_q_template_mismatch |
|:---------------------------------|:---------------|---------------:|---------------:|------------------:|------------------:|------------------------------:|-----------------------------:|
| none|moderate|quiet|central_9_11 | frontier       |           1217 |              7 |               987 |                25 |                             0 |                    0.0390628 |
| none|high|quiet|central_9_11     | frontier       |           1241 |              7 |               937 |                25 |                             0 |                    0.0710039 |
| none|extreme|mild|late_ge12      | frontier       |            341 |              7 |               715 |                25 |                             0 |                    0.682862  |
| none|high|mild|rising_6_8        | frontier       |           5402 |              7 |               687 |                25 |                             0 |                    0.0698457 |
| none|high|large|rising_6_8       | frontier       |           2059 |              7 |               614 |                25 |                             0 |                    0.0745823 |
| none|moderate|large|rising_6_8   | frontier       |            507 |              7 |               581 |                26 |                             0 |                    0.0433473 |
| none|moderate|mild|rising_6_8    | frontier       |           2539 |              7 |               508 |                26 |                             0 |                    0.0425723 |
| none|extreme|large|rising_6_8    | frontier       |           3338 |              7 |               325 |                25 |                             0 |                    0.189254  |
| none|high|active|rising_6_8      | frontier       |            976 |              7 |               274 |                25 |                             0 |                    0.0711175 |
| none|moderate|active|rising_6_8  | frontier       |            312 |              7 |               225 |                25 |                             0 |                    0.0431908 |
| none|extreme|quiet|late_ge12     | strong         |           1960 |              7 |              6071 |                26 |                             0 |                    0.641759  |
| none|high|quiet|rising_6_8       | strong         |          29651 |              7 |              3392 |                26 |                             0 |                    0.0707571 |
| none|extreme|large|early_le5     | strong         |           9018 |              7 |              3241 |                25 |                             0 |                    0.334572  |
| none|moderate|quiet|rising_6_8   | strong         |          16325 |              7 |              2358 |                26 |                             0 |                    0.0418709 |
| none|high|large|early_le5        | strong         |           1255 |              7 |              1343 |                25 |                             0 |                    0.0798047 |
| none|extreme|quiet|central_9_11  | strong         |            460 |              7 |              1038 |                25 |                             0 |                    0.165212  |
| none|moderate|mild|central_9_11  | unsupported    |            219 |              7 |               146 |                22 |                             0 |                    0.0397353 |
| none|extreme|mild|central_9_11   | unsupported    |             89 |              7 |               142 |                24 |                             0 |                    0.1616    |
| none|high|mild|central_9_11      | unsupported    |            236 |              7 |               110 |                23 |                             0 |                    0.0678811 |
| none|low|quiet|central_9_11      | unsupported    |             62 |              6 |                97 |                23 |                             0 |                    0.0233121 |

## 7. Systematics And Negative Controls

- Held-out B2 rows used for scoring: `88,196`.
- Training rows before caps: `24,428` from staves `B4, B6, B8`.
- Held-out run overlap with training rows: `0`.
- B2 rows in training matrix: `0`.
- Event/run ids and odd-channel target samples in model features: `False`.
- Shuffled-target HGB res68: `0.67273`.
- Saturation-feature knockout HGB res68: `0.02295`.

The shuffled-target sentinel should be broad and is not eligible to win. The saturation-feature knockout tests whether the explicit saturation-depth and baseline-excursion covariates carry useful support-frontier information beyond raw waveform samples.

## 8. Caveats

This is a duplicate-readout transfer closure, not an absolute energy calibration. The odd channel shares event timing and electronics context with the even waveform, so very small residuals do not imply a physics-energy resolution. The B2 extrapolation also remains support limited in rare cells with deep saturation, high template mismatch, or unusual peak phase. CIs cover run-to-run variation among the selected held-out runs; they do not cover alternate threshold choices, alternate baseline definitions, or systematic readout nonlinearity not represented in the B4/B6/B8 source staves.

## 9. Verdict

`gradient_boosted_trees` wins the held-out B2 transfer benchmark with res68 0.02132 and run-block 95 percent CI [0.019245861336278036, 0.023812690191499827]. The best strong traditional method is `strong_huber_transfer` at 0.04135; the shuffled-target sentinel is 0.67273. The B2 transfer is most trustworthy in support cells with strong B4/B6/B8 train coverage and low-to-moderate template mismatch; deep saturation and unsupported cells remain systematic frontiers rather than validated closure regions.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04n_1781036493_3330_4f5f1b60_b2_transfer_support_frontier.py --config configs/p04n_1781036493_3330_4f5f1b60_b2_transfer_support_frontier.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `method_summary.csv`, `method_by_run.csv`, `support_frontier_metrics.csv`, `support_cells.csv`, `heldout_prediction_sample.csv`, and `leakage_checks.csv`.

# P04 Ticket #2398 - Multimodel Amplitude and Charge Regression Bakeoff

- **Study ID:** P04
- **Ticket:** #2398 - amplitude and deposited-charge regression multimodel bakeoff
- **Author:** testbeam-laptop-4
- **Date:** 2026-08-16
- **Depends on:** S00
- **Git commit:** cfc84ffc12926fe2fca17b0a32418b9557a5054d
- **Config:** `configs/p04_2398_multimodel_charge_bakeoff.json`

## 0. Question

Does waveform-level ML improve independent duplicate-readout amplitude and positive-charge closure over strong non-ML charge estimators on run-held-out B-stack data, especially in high-amplitude B2-like regimes?

## 1. Reproduction Gate

The raw ROOT `h101/HRDv` arrays were scanned before any model fitting. For each event, samples 0-3 define the channel pedestal by median; B2/B4/B6/B8 even channels are selected when `A=max(w-b)>1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640737 | 640737 | 0 | 0 | True |

The reproduced number is the canonical S00 count, rebuilt directly from `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.

## 2. Methods

Target definition: for a selected even B-stave waveform `x_i in R^18`, the independent target is the paired odd duplicate readout after sign inversion: `A_odd=max(-o_i)` and `Q_odd=sum_j max(-o_ij,0)`. The loss is fitted in log-space so all predictors are positive.

Let `r_i=(yhat_i-y_i)/max(y_i,1)` denote fractional residual. The primary width is `q_0.68(|r|)`, with full-distribution cross-checks `q_0.95(|r|)`, `sqrt(mean(r^2))`, and `mean(|r|<0.10)`. Run-block bootstrap intervals sample the held-out run labels with replacement and recompute each metric on the concatenated selected pulses.

Traditional estimators: peak calibration, integral calibration, shifted amplitude-binned template scale calibration, and a strong Huber regressor on engineered peak/integral/tail/width/template features. The calibrators solve `log y = a_s + b_s log u` separately for each stave `s`; `u` is even peak, even positive charge, or shifted-template scale. The Huber objective is `min_w sum_i rho_epsilon(log y_i - w^T z_i) + alpha ||w||_2^2`, fitted separately by stave with `epsilon=1.35` and `alpha=1e-4`.

ML and NN estimators: ridge regression (`alpha=10`) on waveform and engineered features, histogram gradient-boosted trees (`max_iter=220`, `max_leaf_nodes=31`), scikit-learn MLP (`64,32` hidden units, early stopping), a 1D-CNN over the 18-sample waveform with metadata head, and `residual_cnn`, a new residual architecture that learns an additive log-space correction to the Huber traditional prediction `log yhat = log yhat_Huber + f_theta(x,z)`.

Split: validation runs `[56, 64]`, held-out test runs `[57, 65]`, all other runs used for training. Bootstrap CIs resample held-out runs with replacement (`B=300`). Sklearn and NN training are capped by row count in the config after the run split, not by random event-level train/test leakage.

Primary metric: `res68_abs_frac = percentile_68(|(prediction-target)/target|)`. Lower is better. Secondary metrics are median bias, 95th-percentile absolute error, full RMS, MAE, and fraction within 10%.

## 3. Amplitude Results

| method                   |     n |   bias_median_frac |   res68_abs_frac | res68_abs_frac_ci95                          |   res95_abs_frac |   full_rms_frac |   within_10pct |
|:-------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|-----------------:|----------------:|---------------:|
| strong_traditional_huber | 26857 |        8.7122e-05  |       0.00615469 | [0.005442475041003748, 0.007228671812739816] |        0.386429  |       0.29833   |       0.894813 |
| gradient_boosted_trees   | 26857 |        0.000295466 |       0.00793515 | [0.007450707509543945, 0.008509892829242726] |        0.0460141 |       0.0342821 |       0.985106 |
| ridge                    | 26857 |        0.00288384  |       0.0209503  | [0.02083883182523249, 0.021047423718007684]  |        0.13047   |       0.112542  |       0.927617 |
| residual_cnn             | 26857 |       -0.00323008  |       0.0319739  | [0.031083837550421708, 0.03284491722762696]  |        0.294652  |       0.343826  |       0.885989 |
| mlp                      | 26857 |        0.00233312  |       0.0374788  | [0.03665316807110038, 0.03837282880104475]   |        0.14562   |      15.5002    |       0.913207 |
| peak_calibrated          | 26857 |       -0.0676074   |       0.125671   | [0.10324207777092369, 0.1416401762574858]    |        0.854753  |       0.525036  |       0.573407 |
| integral_calibrated      | 26857 |        0.0610195   |       0.132042   | [0.12231806043690412, 0.14118688390049905]   |        0.840183  |       0.46793   |       0.546152 |
| cnn_1d                   | 26857 |        0.0235776   |       0.210999   | [0.18511335282851263, 0.24696749718995878]   |        0.630121  |       0.657815  |       0.464907 |
| template_fit_calibrated  | 26857 |        0.237651    |       0.579475   | [0.42543184337383655, 0.7547894294503429]    |        1.89252   |       0.949213  |       0.16748  |
| context_only_median      | 26857 |        0.606031    |       1.20081    | [0.8461279110505485, 1.602283105022831]      |        4.44057   |       2.9508    |       0.118479 |

## 4. Charge Results

| method                   |     n |   bias_median_frac |   res68_abs_frac | res68_abs_frac_ci95                          |   res95_abs_frac |   full_rms_frac |   within_10pct |
|:-------------------------|------:|-------------------:|-----------------:|:---------------------------------------------|-----------------:|----------------:|---------------:|
| gradient_boosted_trees   | 26857 |        0.000697133 |        0.0150872 | [0.014697827088675302, 0.015390786547935919] |        0.0703228 |       0.0450637 |       0.972633 |
| strong_traditional_huber | 26857 |        8.79603e-05 |        0.0153015 | [0.01402861601886058, 0.017524116648509055]  |        0.526568  |       0.655667  |       0.872547 |
| ridge                    | 26857 |        0.0022685   |        0.0350275 | [0.0336497809852258, 0.036137640323889095]   |        0.263072  |       0.175729  |       0.878467 |
| residual_cnn             | 26857 |        0.000696041 |        0.0409007 | [0.038469426060842, 0.04321279536754774]     |        0.358376  |       0.636061  |       0.868675 |
| mlp                      | 26857 |        0.00807536  |        0.0508623 | [0.05080865311777564, 0.05089538991212415]   |        0.179567  |      23.2651    |       0.87493  |
| integral_calibrated      | 26857 |       -0.0920356   |        0.197404  | [0.16544326543403187, 0.21741042845912986]   |        1.68506   |       1.6609    |       0.400045 |
| cnn_1d                   | 26857 |        0.0745841   |        0.228777  | [0.20487728548398118, 0.2632444039008655]    |        0.685324  |      19.4794    |       0.40388  |
| peak_calibrated          | 26857 |       -0.213415    |        0.283677  | [0.2661657807231381, 0.31105559042552394]    |        2.92712   |       2.56188   |       0.129203 |
| template_fit_calibrated  | 26857 |        0.0922502   |        0.548742  | [0.39597392224743505, 0.6994637528335754]    |        1.9551    |       2.4636    |       0.185203 |
| context_only_median      | 26857 |        0.775594    |        1.86841   | [1.272476367895808, 2.388494746000937]       |       18.0501    |      16.1172    |       0.128607 |

## 5. High-Amplitude and B2 Systematics

| subset                | method                   |     n |   bias_median_frac |   res68_abs_frac |   res95_abs_frac |   within_10pct |
|:----------------------|:-------------------------|------:|-------------------:|-----------------:|-----------------:|---------------:|
| high_amplitude_ge7000 | gradient_boosted_trees   |  2299 |        0.000401957 |       0.00787097 |        0.0303935 |      0.994345  |
| high_amplitude_ge7000 | ridge                    |  2299 |        0.00117795  |       0.010193   |        0.0836729 |      0.959983  |
| high_amplitude_ge7000 | strong_traditional_huber |  2299 |       -0.000376935 |       0.0121673  |        0.143915  |      0.900826  |
| high_amplitude_ge7000 | peak_calibrated          |  2299 |        0.00880936  |       0.0260111  |        0.211026  |      0.887777  |
| high_amplitude_ge7000 | residual_cnn             |  2299 |       -0.00379817  |       0.0316652  |        0.133935  |      0.928665  |
| high_amplitude_ge7000 | mlp                      |  2299 |        0.00802362  |       0.0377649  |        0.185162  |      0.899522  |
| high_amplitude_ge7000 | integral_calibrated      |  2299 |       -0.119815    |       0.159751   |        0.327596  |      0.341018  |
| high_amplitude_ge7000 | cnn_1d                   |  2299 |       -0.0358275   |       0.189445   |        0.427176  |      0.397564  |
| high_amplitude_ge7000 | template_fit_calibrated  |  2299 |       -0.272309    |       0.31545    |        0.44759   |      0.0195737 |
| high_amplitude_ge7000 | context_only_median      |  2299 |       -0.280838    |       0.330904   |        0.407988  |      0.0178338 |
| stave_B2              | strong_traditional_huber | 24528 |        0.000107862 |       0.00526976 |        0.407949  |      0.895018  |
| stave_B2              | gradient_boosted_trees   | 24528 |        0.000228478 |       0.00767529 |        0.0453841 |      0.984997  |
| stave_B2              | ridge                    | 24528 |        0.00299013  |       0.02015    |        0.125444  |      0.934646  |
| stave_B2              | residual_cnn             | 24528 |       -0.00413158  |       0.0307139  |        0.296001  |      0.890492  |
| stave_B2              | mlp                      | 24528 |        0.00152758  |       0.0350255  |        0.135572  |      0.924291  |
| stave_B2              | peak_calibrated          | 24528 |       -0.0661449   |       0.120985   |        0.831861  |      0.591813  |
| stave_B2              | integral_calibrated      | 24528 |        0.0655779   |       0.126893   |        0.803693  |      0.559809  |
| stave_B2              | cnn_1d                   | 24528 |        0.0281045   |       0.207898   |        0.631117  |      0.476884  |
| stave_B2              | template_fit_calibrated  | 24528 |        0.266524    |       0.606051   |        1.89514   |      0.164954  |
| stave_B2              | context_only_median      | 24528 |        0.672487    |       1.29676    |        4.46667   |      0.107714  |

Systematic uncertainty is not collapsed into a single scalar because the dominant effects are regime-dependent. The high-amplitude and B2 tables quantify the largest known amplitude-support shift; the context-only median and shuffled-target controls quantify trivial run/stave and label-leakage floors; the full RMS and 95th-percentile columns expose rare failures hidden by the robust core metric.

| Systematic source | Probe | Interpretation |
|---|---|---|
| Run-family dependence | Held-out runs 57 and 65, run-block bootstrap | Statistical CI is intentionally conservative but only spans two held-out run labels. |
| High-amplitude non-linearity | `even_amp >= 7000 ADC` subset | Tests the high-B2/saturation-like region named in the ticket. |
| Target leakage | Odd samples excluded; shuffled-target GBT | Shuffled-target width must be broad compared with the winner. |
| Context leakage | Stave-local median predictor | Measures how much run/stave composition alone can explain. |
| Tail risk | `res95` and full RMS | Flags methods with good core error but unacceptable rare outliers. |

The result is a duplicate-readout electronics closure, not an external deposited-energy truth calibration.

## 6. Falsification and Winner

Pre-registered winner rule: choose the method with the lowest held-out amplitude `res68_abs_frac`; require its run-bootstrap CI to lie below the strongest traditional baseline CI for an adoption-strength win. Winner: `strong_traditional_huber`.

The strongest traditional amplitude method is `strong_traditional_huber` with res68 0.006155. The winner has res68 0.006155 with 95% CI [0.005442475, 0.0072286718].

Shuffled-target GBT amplitude res68 is 0.793003; context-only median amplitude res68 is 1.200811. Both are much worse than the winner, arguing against trivial run/stave or label-shuffle leakage.

## 7. Threats to Validity

- Benchmark/selection: all methods use the same held-out runs and independent odd-readout targets; the Huber/template baselines are intentionally strong and stave-local.
- Data leakage: run and event identifiers are excluded from features; held-out runs are absent from all calibrators, scalers, templates, and neural training.
- Metric misuse: the report includes robust core width, bias, 95th percentile, full RMS, and high-amplitude/B2 subsets; no chi-squared fit is used except least-squares template scale selection.
- Post-hoc selection: the primary metric and winner rule are fixed in the config/report before interpretation; model families are the named methods requested by the ticket.

## 8. Caveats

The odd duplicate channel is a stringent electronics closure target but is still not a direct deposited-energy truth label. A model can exploit shared physical energy deposition and channel-correlated pulse morphology, so the result should not be promoted to absolute energy calibration without external A-stack, GEANT4, or stopping-depth validation. The run-block CI has only two held-out runs, so the interval measures run-family stability coarsely rather than all possible operating conditions. The MLP and CNN rows also show large full-RMS outliers despite moderate robust widths; these architectures are therefore not acceptable replacements even where their core `res68` is competitive.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04_2398_multimodel_charge_bakeoff.py --config configs/p04_2398_multimodel_charge_bakeoff.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `benchmark.csv`, `benchmark_by_subset.csv`, `predictions.csv.gz`, `counts_by_run.csv`, `input_sha256.csv`.

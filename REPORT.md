# Ticket 0307: raw-ROOT run-heldout regression benchmark

## Abstract

Ticket 0307 was claimed by `testbeam-laptop-3` and analyzed from the B-stack raw ROOT files under `data/root/root`. The raw reproduction scan applies the repository's standard four-stave selection: subtract the per-channel median of samples 0--3 from each 18-sample waveform and select a pulse when the primary even channel for B2, B4, B6, or B8 exceeds 1000 ADC. This reproduces 640,737 selected pulses, matching the canonical repository anchor of 640,737.

The prediction task is deliberately local to the raw detector data: predict the negative duplicate-readout peak amplitude from the corresponding primary-channel pulse shape and engineered pulse features. The validation is leave-one-run-out over runs 31, 42, 50, 57, 64, 65; the uncertainty intervals are non-parametric bootstraps over held-out runs.

## Raw Data and Reproduction

The scan used the TTree `h101` branches `EVENTNO`, `EVT`, and `HRDv`. For event `i`, channel `c`, and sample `s`, the baseline-corrected waveform is

`x_{i,c,s} = HRDv_{i,c,s} - median_{t in {0,1,2,3}} HRDv_{i,c,t}`.

For stave `k`, the selected-pulse indicator is

`I_{i,k} = 1[max_s x_{i,c(k),s} > 1000]`,

where `c(k)` is the primary even channel. The reproduced count is `sum_{i,k} I_{i,k}`.

| run | group | events_total | events_with_selected | selected_pulses | B2 | B4 | B6 | B8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 31 | sample_i_calib | 39990 | 27078 | 27871 | 26948 | 592 | 237 | 94 |
| 32 | sample_i_calib | 41921 | 27461 | 28240 | 27316 | 605 | 224 | 95 |
| 33 | sample_i_calib | 57173 | 47911 | 48737 | 47724 | 559 | 318 | 136 |
| 34 | sample_i_calib | 39765 | 33500 | 34118 | 33373 | 412 | 244 | 89 |
| 35 | sample_i_calib | 27786 | 11141 | 11667 | 11029 | 403 | 163 | 72 |
| 36 | sample_i_calib | 21764 | 9930 | 10391 | 9847 | 340 | 143 | 61 |
| 37 | sample_i_calib | 50513 | 23174 | 24537 | 22956 | 997 | 423 | 161 |
| 39 | sample_i_calib | 30321 | 13329 | 14218 | 13174 | 663 | 273 | 108 |
| 40 | sample_i_calib | 32613 | 13763 | 14708 | 13575 | 707 | 310 | 116 |
| 41 | sample_i_calib | 33997 | 15140 | 16146 | 14963 | 758 | 298 | 127 |
| 42 | sample_i_calib | 33972 | 17132 | 18112 | 16977 | 711 | 307 | 117 |
| 44 | sample_i_analysis | 4294 | 1912 | 2038 | 1884 | 93 | 44 | 17 |
| 45 | sample_i_analysis | 48181 | 23013 | 24333 | 22786 | 969 | 401 | 177 |
| 46 | sample_i_analysis | 1441 | 677 | 687 | 675 | 7 | 3 | 2 |
| 47 | sample_i_analysis | 10970 | 5161 | 5276 | 5116 | 85 | 50 | 25 |
| 48 | sample_i_analysis | 31713 | 13185 | 14000 | 13044 | 599 | 245 | 112 |
| 49 | sample_i_analysis | 32354 | 13937 | 14815 | 13779 | 640 | 281 | 115 |
| 50 | sample_i_analysis | 44804 | 34257 | 35217 | 34088 | 659 | 330 | 140 |
| 51 | sample_i_analysis | 20569 | 14295 | 14740 | 14200 | 303 | 177 | 60 |
| 52 | sample_i_analysis | 10005 | 6933 | 7152 | 6893 | 148 | 76 | 35 |
| 53 | sample_i_analysis | 39612 | 31386 | 32200 | 31225 | 559 | 296 | 120 |
| 54 | sample_i_analysis | 37413 | 29665 | 30440 | 29493 | 536 | 298 | 113 |
| 55 | sample_i_analysis | 24416 | 16841 | 17387 | 16735 | 372 | 199 | 81 |
| 56 | sample_i_analysis | 51823 | 38932 | 40148 | 38730 | 825 | 421 | 172 |
| 57 | sample_i_analysis | 31284 | 12939 | 13833 | 12774 | 656 | 273 | 130 |
| 58 | sample_ii_analysis | 34141 | 15920 | 16781 | 15791 | 591 | 285 | 114 |
| 59 | sample_ii_analysis | 42303 | 13863 | 21377 | 13565 | 4527 | 2366 | 919 |
| 60 | sample_ii_analysis | 36074 | 10140 | 17029 | 9873 | 4040 | 2189 | 927 |
| 61 | sample_ii_analysis | 36535 | 11287 | 18965 | 11015 | 4401 | 2490 | 1059 |
| 62 | sample_ii_analysis | 37584 | 11912 | 19089 | 11635 | 4183 | 2342 | 929 |
| 63 | sample_ii_analysis | 37030 | 14781 | 18817 | 14566 | 2645 | 1153 | 453 |
| 64 | sample_ii_calib | 35943 | 12103 | 14630 | 11907 | 1689 | 763 | 271 |
| 65 | sample_ii_analysis | 38424 | 11904 | 13038 | 11768 | 842 | 323 | 105 |

## Prediction Target and Features

For each selected pulse in the benchmark runs, the response variable is the duplicate-channel negative peak

`y_i = max_s(-x_{i,d(k),s})`,

where `d(k)` is the odd duplicate channel paired with the selected stave. This is a stringent cross-readout charge proxy: the model sees the primary pulse shape and has to infer the matched duplicate response without using the duplicate waveform itself.

The tabular feature vector contains primary amplitude, integral, peak sample, half-maximum width, interpolated 10/50/90 percent threshold-crossing samples, the 18 normalized waveform samples, and a stave one-hot code. Neural models receive the same tabular features and the normalized 18-sample sequence.

## Models

The traditional baseline is ridge regression with standardized features and cross-validated `alpha`. The machine-learning panel consists of histogram gradient-boosted trees and a scikit-learn MLP. The neural-network panel consists of a 1D convolutional regressor and a new attentive residual MLP. The attentive residual MLP learns sample weights over the normalized waveform, combines weighted pulse summaries with tabular features, and predicts the residual response through a compact feed-forward head.

For a model `f_m`, the held-out predictions are generated as

`hat(y)_i = f_m(z_i; D_{train}),  run(i) = r_{heldout}`,

with all rows from the held-out run excluded from training. The primary metric is run-mean RMSE,

`RMSE_r = sqrt(n_r^-1 sum_{i in r} (hat(y)_i - y_i)^2)`,

and the reported confidence interval resamples the set of held-out runs with replacement.

## Main Results

Winner by run-mean RMSE: **gradient_boosted_trees**.

| method | run mean RMSE | 95% CI RMSE | run mean MAE | 95% CI MAE | run mean R2 |
| --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 125.193 | [102.518, 145.714] | 50.648 | [44.577, 55.676] | 0.995 |
| mlp | 157.393 | [138.139, 177.227] | 75.984 | [66.291, 86.678] | 0.991 |
| ridge | 189.514 | [177.517, 199.895] | 104.979 | [98.643, 111.643] | 0.988 |
| one_dimensional_cnn | 1424.715 | [1221.908, 1630.362] | 1052.147 | [932.848, 1180.695] | 0.406 |
| attentive_residual_mlp | 1780.510 | [1631.387, 1916.690] | 1431.321 | [1347.837, 1509.062] | 0.025 |

## Held-Out Run Detail

| heldout_run | method | n_test | rmse | mae | bias | r2 |
| --- | --- | --- | --- | --- | --- | --- |
| 31 | attentive_residual_mlp | 851 | 1987.706 | 1531.854 | -112.931 | 0.230 |
| 31 | gradient_boosted_trees | 851 | 97.783 | 48.187 | 5.660 | 0.998 |
| 31 | mlp | 851 | 116.926 | 66.783 | -14.322 | 0.997 |
| 31 | one_dimensional_cnn | 851 | 1716.090 | 1216.733 | -475.692 | 0.426 |
| 31 | ridge | 851 | 168.872 | 102.444 | 2.402 | 0.994 |
| 42 | attentive_residual_mlp | 897 | 1803.391 | 1400.586 | 197.595 | 0.228 |
| 42 | gradient_boosted_trees | 897 | 139.539 | 58.244 | 0.220 | 0.995 |
| 42 | mlp | 897 | 162.798 | 75.262 | -1.048 | 0.994 |
| 42 | one_dimensional_cnn | 897 | 1506.708 | 1062.222 | -259.091 | 0.461 |
| 42 | ridge | 897 | 204.604 | 117.220 | -1.816 | 0.990 |
| 50 | attentive_residual_mlp | 920 | 2054.040 | 1580.962 | -346.620 | 0.198 |
| 50 | gradient_boosted_trees | 920 | 127.472 | 58.033 | -7.632 | 0.997 |
| 50 | mlp | 920 | 127.023 | 56.924 | 4.949 | 0.997 |
| 50 | one_dimensional_cnn | 920 | 1828.444 | 1315.302 | -676.870 | 0.365 |
| 50 | ridge | 920 | 188.814 | 111.492 | -7.702 | 0.993 |
| 57 | attentive_residual_mlp | 910 | 1540.493 | 1245.788 | 635.748 | 0.111 |
| 57 | gradient_boosted_trees | 910 | 151.605 | 54.083 | 2.378 | 0.991 |
| 57 | mlp | 910 | 175.778 | 89.998 | 2.781 | 0.988 |
| 57 | one_dimensional_cnn | 910 | 1169.357 | 868.319 | 108.139 | 0.488 |
| 57 | ridge | 910 | 191.467 | 108.298 | 15.024 | 0.986 |
| 64 | attentive_residual_mlp | 1040 | 1667.019 | 1436.543 | 1102.309 | -0.313 |
| 64 | gradient_boosted_trees | 1040 | 82.300 | 38.747 | 10.099 | 0.997 |
| 64 | mlp | 1040 | 188.235 | 96.008 | -7.917 | 0.983 |
| 64 | one_dimensional_cnn | 1040 | 1141.291 | 902.386 | 501.212 | 0.385 |
| 64 | ridge | 1040 | 176.757 | 95.069 | -5.345 | 0.985 |
| 65 | attentive_residual_mlp | 885 | 1630.410 | 1392.193 | 1045.516 | -0.306 |
| 65 | gradient_boosted_trees | 885 | 152.460 | 46.593 | -7.947 | 0.989 |
| 65 | mlp | 885 | 173.598 | 70.928 | -6.739 | 0.985 |
| 65 | one_dimensional_cnn | 885 | 1186.399 | 947.920 | 505.579 | 0.309 |
| 65 | ridge | 885 | 206.572 | 95.349 | -5.642 | 0.979 |

## Systematic Checks

* **Run leakage control:** validation leaves out complete runs, not random events, so the score is sensitive to run-level gain and baseline shifts.
* **Readout leakage control:** the duplicate waveform is excluded from the feature set; only the primary waveform and primary-derived summaries are used.
* **Selection reproducibility:** the raw selection count exactly matches the canonical 640,737 selected pulses.
* **Finite-run uncertainty:** only six runs enter the benchmark panel; the bootstrap CIs therefore quantify between-run instability but remain coarse.
* **Target limitation:** the duplicate negative peak is a charge proxy, not an external calorimetric truth label. It tests cross-readout calibration, not absolute deposited energy.
* **Hyperparameter limitation:** neural networks are intentionally compact CPU models with early stopping. Larger sweeps may change small rank differences but would not remove the run-heldout systematic floor.

## Caveats

The result is preliminary and should be read as a method comparison for raw-waveform duplicate-charge inference. The reported CIs do not include uncertainty from the amplitude threshold choice, from alternative baseline windows, or from possible time-dependent detector conditions within a run. The benchmark is nevertheless useful because every method sees the same rows, the same leave-one-run-out splits, and the same raw-ROOT-derived target.

## Reproducibility

Run with:

```bash
.venv/bin/python scripts/analyze_0307.py
```

Important constants: random seed `3072026`, amplitude cut `1000.0`, benchmark runs `[31, 42, 50, 57, 64, 65]`, maximum `260` selected pulses per run and stave, and `500` bootstrap replicates. The script writes `result.json`, `reports/0307/summary.json`, `reports/0307/reproduction_counts_by_run.csv`, `reports/0307/heldout_per_run_metrics.csv`, and `reports/0307/heldout_predictions.csv.gz`.

# S18l: Fixed-Efficiency CFD Fraction Interpolation-Noise Scan

- **Ticket:** `1783808361.8863.6df51b41`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-07-12
- **Input:** raw A-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18l_1783808361_8863_6df51b41_fixed_efficiency_cfd_fraction_scan.py --config configs/s18l_1783808361_8863_6df51b41_fixed_efficiency_cfd_fraction_scan.json`
- **Split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on Sample IV analysis runs `58,59,60,61,62,63,65`.
- **CFD grid:** `0.10, 0.15, 0.20, 0.25, 0.30, 0.35`.
- **Primary estimand:** held-out Sample IV A3-A1 percentile-68 residual width after correction, with run-bootstrap 95% confidence intervals.

## Abstract

S18k showed that gradient-boosted trees won under fixed-efficiency A-stack amplitude gates, but the support and interpolation pieces remained partially entangled. This S18l study freezes the retained-event fraction by run and scans the CFD fraction itself. The raw A1/A3 pair count and the historical Sample-IV S18 number are reproduced directly from ROOT before any model is trained. At each CFD fraction, the same per-run fixed-efficiency amplitude thresholds are applied, then a strong traditional constrained timewalk correction is benchmarked against ridge regression, histogram gradient-boosted trees, MLP, 1D-CNN, and the new gated residual CNN.

The `result.json` winner is **fixed_efficiency_cfd0.30 / gradient_boosted_trees**, with width **10.429 ns** and run-bootstrap CI **[9.879, 11.326] ns**. The interpolation-noise verdict is **CFD_fraction_matters_after_fixed_efficiency_support**.

## Raw ROOT Reproduction

For each event the ROOT branch `HRDv` is reshaped as `(8, 18)`. Samples 0-3 estimate the pedestal. For channel `c`,

`b_c = median(v_c[0:4])`, `x_c[k] = v_c[k] - b_c`, and `A_c = max_k x_c[k]`.

At CFD fraction `f`, the threshold is `h_c = f A_c`; the crossing time is the first pre-peak linear interpolation satisfying `x_c(t_c) = h_c`. The target residual is

`y_i = t_{A3,i}(f) - t_{A1,i}(f)`.

The historical reproduction gate is evaluated at CFD20/cut1000 using the S18 run64 calibration definition:

| quantity                            |   expected |   reproduced |       delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs               |  127       |    127       | 0           |       0     | True   |
| sample_iv_run64_ols_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_run64_ols_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

Standard-gate A-stack counts:

| sample              |   events_total |   events_with_selected |   A1_A3_pairs |   selected_pulses |   A1 |    A3 |
|:--------------------|---------------:|-----------------------:|--------------:|------------------:|-----:|------:|
| sample_iii_calib    |         409803 |                  11067 |          3816 |             14883 | 4111 | 10772 |
| sample_iii_analysis |         388848 |                   7168 |          2514 |              9682 | 2799 |  6883 |
| sample_iv_calib     |          35985 |                    161 |            16 |               177 |   20 |   157 |
| sample_iv_analysis  |         262189 |                    767 |           127 |               894 |  167 |   727 |

## Fixed-Efficiency CFD Scan

Let `s_i = min(A1_i, A3_i)` on positive-amplitude support. The reference efficiency is computed once from the pooled Sample-III train plus Sample-IV held-out positive support under the standard cut:

`epsilon_0 = N(s_i > 1000 ADC) / N(s_i > 0) = 0.006091`.

For each run `r`,

`tau_r = Q_{1 - epsilon_0}({s_i : run_i = r})`,

and event `i` is retained when `s_i >= tau_r`. These thresholds are independent of the residual value and are frozen across the CFD scan, so changes with `f` measure timing-pickoff interpolation and waveform-shape behavior at comparable support.

Run-local thresholds:

|   run |   events_in_positive_support |   target_pair_efficiency |   threshold_adc |   selected_pairs |   achieved_efficiency |
|------:|-----------------------------:|-------------------------:|----------------:|-----------------:|----------------------:|
|    31 |                        39968 |                0.0060915 |       1149.54   |              244 |            0.00610488 |
|    32 |                        41879 |                0.0060915 |       1259      |              257 |            0.00613673 |
|    33 |                        57129 |                0.0060915 |         68.5    |              362 |            0.00633654 |
|    34 |                        39664 |                0.0060915 |         69.5    |              243 |            0.00612646 |
|    35 |                        27740 |                0.0060915 |       1625.51   |              169 |            0.00609229 |
|    36 |                        21739 |                0.0060915 |       1604.66   |              133 |            0.00611804 |
|    37 |                        50479 |                0.0060915 |       1702.03   |              308 |            0.00610155 |
|    39 |                        30308 |                0.0060915 |       1738.19   |              185 |            0.006104   |
|    40 |                        32615 |                0.0060915 |       1722      |              199 |            0.00610149 |
|    41 |                        33988 |                0.0060915 |       1676.97   |              208 |            0.00611981 |
|    42 |                        33943 |                0.0060915 |       1668.24   |              207 |            0.00609846 |
|    44 |                         4296 |                0.0060915 |       1738.91   |               27 |            0.00628492 |
|    45 |                        48168 |                0.0060915 |       1661.3    |              294 |            0.00610364 |
|    46 |                         1444 |                0.0060915 |        889.299  |                9 |            0.00623269 |
|    47 |                        10976 |                0.0060915 |       1519.24   |               67 |            0.00610423 |
|    48 |                        31650 |                0.0060915 |       1808      |              194 |            0.00612954 |
|    49 |                        32301 |                0.0060915 |       1738.47   |              197 |            0.00609888 |
|    50 |                        44787 |                0.0060915 |         75.5931 |              273 |            0.00609552 |
|    51 |                        20543 |                0.0060915 |         73      |              127 |            0.00618215 |
|    52 |                        10002 |                0.0060915 |         73.5395 |               61 |            0.00609878 |
|    53 |                        39594 |                0.0060915 |         73.5    |              249 |            0.00628883 |
|    54 |                        37362 |                0.0060915 |         75      |              237 |            0.00634334 |
|    55 |                        24384 |                0.0060915 |         76.5    |              151 |            0.00619259 |
|    56 |                        51787 |                0.0060915 |         83      |              329 |            0.00635295 |
|    57 |                        31256 |                0.0060915 |       1734.31   |              191 |            0.00611083 |
|    58 |                        34157 |                0.0060915 |         78      |              214 |            0.00626519 |
|    59 |                        42280 |                0.0060915 |         76.5    |              262 |            0.00619678 |
|    60 |                        36061 |                0.0060915 |         76.5    |              222 |            0.00615624 |
|    61 |                        36528 |                0.0060915 |         76      |              225 |            0.00615966 |
|    62 |                        37567 |                0.0060915 |         75.5    |              232 |            0.00617563 |
|    63 |                        37006 |                0.0060915 |         79      |              234 |            0.0063233  |
|    65 |                        38401 |                0.0060915 |         76.5    |              238 |            0.00619776 |

Raw fixed-efficiency widths by CFD fraction:

|   cfd_fraction |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|---------------:|----------:|------------------:|-------------------:|--------------------:|--------------:|---------------------------:|
|           0.1  |      1627 |           33.7556 |            30.3861 |             36.5849 |       37.8834 |                   0.754763 |
|           0.15 |      1627 |           36.5214 |            32.7861 |             39.8592 |       39.985  |                   0.755378 |
|           0.2  |      1627 |           38.6681 |            35.0512 |             42.191  |       41.2304 |                   0.771358 |
|           0.25 |      1627 |           40.31   |            36.8183 |             43.6775 |       42.137  |                   0.779963 |
|           0.3  |      1627 |           40.7458 |            38.7093 |             44.4062 |       42.9348 |                   0.771973 |
|           0.35 |      1627 |           41.7082 |            39.1467 |             45.6566 |       43.7092 |                   0.775046 |

The best raw CFD settings are:

|   cfd_fraction |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |
|---------------:|----------:|------------------:|-------------------:|--------------------:|
|           0.1  |      1627 |           33.7556 |            30.3861 |             36.5849 |
|           0.15 |      1627 |           36.5214 |            32.7861 |             39.8592 |
|           0.2  |      1627 |           38.6681 |            35.0512 |             42.191  |
|           0.25 |      1627 |           40.31   |            36.8183 |             43.6775 |
|           0.3  |      1627 |           40.7458 |            38.7093 |             44.4062 |
|           0.35 |      1627 |           41.7082 |            39.1467 |             45.6566 |

## Model Panel and Equations

The traditional comparator is an additive monotone timewalk model,

`hat y_i = beta_0 + d_R(log A_{R,i}) - d_L(log A_{L,i})`,

where `d_L` and `d_R` are non-increasing isotonic functions fitted only on training runs. It is a strong traditional baseline because CFD timewalk is expected to vary monotonically with amplitude and it avoids run or event identifiers.

The learned methods use the same held-out run split. Ridge, gradient-boosted trees, and MLP consume engineered log-amplitude, area, peak, tail, normalized-waveform, and waveform-difference features. The 1D-CNN consumes the two normalized 18-sample A1/A3 waveforms plus auxiliary pulse-shape features. The new `gated_residual_cnn_new` adds residual temporal convolutions with an auxiliary squeeze gate; this is sensible here because CFD interpolation noise is local to the leading edge, while the support-normalized scan can still expose tail and amplitude-shape couplings.

No model input includes run number, event number, raw target residual, or per-channel CFD times.

## Benchmark Results

Winner at each CFD fraction:

|   cfd_fraction | method                 |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |
|---------------:|:-----------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|
|           0.1  | gradient_boosted_trees |      1627 |           12.4873 |            11.9246 |             13.2512 |         2.96775 |       18.9112 |
|           0.15 | gradient_boosted_trees |      1627 |           11.2265 |            10.5572 |             11.9085 |         1.80297 |       17.5344 |
|           0.2  | gradient_boosted_trees |      1627 |           10.5046 |            10.0182 |             11.1369 |         2.11941 |       16.37   |
|           0.25 | gradient_boosted_trees |      1627 |           10.8149 |            10.0767 |             11.4053 |         3.8286  |       15.1843 |
|           0.3  | gradient_boosted_trees |      1627 |           10.4288 |             9.8793 |             11.3256 |         4.04279 |       15.2658 |
|           0.35 | gradient_boosted_trees |      1627 |           11.5832 |            10.3125 |             12.5648 |         2.40444 |       15.8824 |

Primary winner gate `fixed_efficiency_cfd0.30`:

| method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| gradient_boosted_trees        |      1627 |           10.4288 |             9.8793 |             11.3256 |         4.04279 |       15.2658 |                   0.572219 |
| mlp                           |      1627 |           11.5472 |            10.3891 |             12.9167 |         3.18353 |       15.1706 |                   0.574063 |
| ridge                         |      1627 |           16.3244 |            14.8227 |             18.1541 |         7.13472 |       20.9898 |                   0.711125 |
| gated_residual_cnn_new        |      1627 |           19.2883 |            16.4246 |             21.5456 |       nan       |       25.1223 |                   0.682852 |
| cnn_1d                        |      1627 |           38.2166 |            35.1744 |             40.5126 |         3.24718 |       39.9059 |                   0.786724 |
| constrained_monotone_timewalk |      1627 |           40.791  |            38.0421 |             43.8146 |         4.9063  |       42.9056 |                   0.802704 |

Method stability over the CFD scan:

| method                        |   gates |   median_width_ns |   min_width_ns |   max_width_ns |   mean_n_pairs |
|:------------------------------|--------:|------------------:|---------------:|---------------:|---------------:|
| gradient_boosted_trees        |       6 |           11.0207 |        10.4288 |        12.4873 |           1627 |
| mlp                           |       6 |           12.4405 |        11.5472 |        15.7489 |           1627 |
| ridge                         |       6 |           17.1302 |        16.2658 |        21.2824 |           1627 |
| gated_residual_cnn_new        |       6 |           20.4034 |        18.3002 |        23.658  |           1627 |
| cnn_1d                        |       6 |           37.5012 |        32.2264 |        38.5619 |           1627 |
| constrained_monotone_timewalk |       6 |           39.4721 |        33.6957 |        41.6201 |           1627 |

Per-run primary-gate widths:

| method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------------------|------:|----------:|------------------:|--------------:|
| cnn_1d                        |    58 |       214 |          30.6613  |       37.3642 |
| cnn_1d                        |    59 |       262 |          37.2059  |       40.0842 |
| cnn_1d                        |    60 |       222 |          38.478   |       40.8981 |
| cnn_1d                        |    61 |       225 |          42.5991  |       42.6438 |
| cnn_1d                        |    62 |       232 |          41.889   |       41.0463 |
| cnn_1d                        |    63 |       234 |          34.1561  |       36.7706 |
| cnn_1d                        |    65 |       238 |          33.4307  |       39.7524 |
| constrained_monotone_timewalk |    58 |       214 |          35.3577  |       40.2378 |
| constrained_monotone_timewalk |    59 |       262 |          40.982   |       43.2392 |
| constrained_monotone_timewalk |    60 |       222 |          41.0082  |       43.9154 |
| constrained_monotone_timewalk |    61 |       225 |          45.797   |       45.6283 |
| constrained_monotone_timewalk |    62 |       232 |          47.0942  |       44.3064 |
| constrained_monotone_timewalk |    63 |       234 |          35.5425  |       39.4025 |
| constrained_monotone_timewalk |    65 |       238 |          35.9252  |       42.8582 |
| gated_residual_cnn_new        |    58 |       214 |          15.9665  |       22.2273 |
| gated_residual_cnn_new        |    59 |       262 |          19.6447  |       27.2603 |
| gated_residual_cnn_new        |    60 |       222 |          23.0888  |       27.0327 |
| gated_residual_cnn_new        |    61 |       225 |          24.0513  |       28.5202 |
| gated_residual_cnn_new        |    62 |       232 |          19.8079  |       23.7963 |
| gated_residual_cnn_new        |    63 |       234 |          18.5512  |       22.8307 |
| gated_residual_cnn_new        |    65 |       238 |          14.8955  |       23.0232 |
| gradient_boosted_trees        |    58 |       214 |           9.46021 |       12.6513 |
| gradient_boosted_trees        |    59 |       262 |          11.6669  |       18.0896 |
| gradient_boosted_trees        |    60 |       222 |          11.1621  |       14.4473 |
| gradient_boosted_trees        |    61 |       225 |          11.9378  |       17.013  |
| gradient_boosted_trees        |    62 |       232 |          10.3402  |       14.6458 |
| gradient_boosted_trees        |    63 |       234 |           9.1038  |       12.0947 |
| gradient_boosted_trees        |    65 |       238 |           9.79721 |       16.2568 |
| mlp                           |    58 |       214 |           9.8008  |       13.1909 |
| mlp                           |    59 |       262 |          12.2345  |       17.8771 |
| mlp                           |    60 |       222 |          13.5039  |       16.1759 |
| mlp                           |    61 |       225 |          14.8298  |       16.7661 |
| mlp                           |    62 |       232 |          12.4346  |       14.1668 |
| mlp                           |    63 |       234 |          10.3278  |       13.2708 |
| mlp                           |    65 |       238 |           9.43214 |       13.6717 |
| ridge                         |    58 |       214 |          13.3052  |       20.5347 |
| ridge                         |    59 |       262 |          18.7307  |       22.5894 |
| ridge                         |    60 |       222 |          17.7457  |       21.5765 |
| ridge                         |    61 |       225 |          19.1366  |       23.4126 |
| ridge                         |    62 |       232 |          18.0694  |       20.9037 |
| ridge                         |    63 |       234 |          14.1604  |       16.613  |
| ridge                         |    65 |       238 |          13.823   |       20.3312 |

## Bootstrap Confidence Intervals and Deltas

Each delta is `W68(method) - W68(constrained_monotone_timewalk)` at the same CFD fraction and fixed-efficiency gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

|   cfd_fraction | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|---------------:|:-----------------------------------------------------------|------------:|-------------:|----------:|
|           0.1  | cnn_1d_minus_constrained_monotone_timewalk                 |    -2.38968 |    -0.656773 |         0 |
|           0.1  | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -12.3002  |    -8.26961  |         0 |
|           0.1  | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -23.6987  |   -17.5634   |         0 |
|           0.1  | mlp_minus_constrained_monotone_timewalk                    |   -19.8881  |   -15.4689   |         0 |
|           0.1  | ridge_minus_constrained_monotone_timewalk                  |   -14.3789  |   -10.5935   |         0 |
|           0.15 | cnn_1d_minus_constrained_monotone_timewalk                 |    -2.68171 |    -0.933104 |         0 |
|           0.15 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -16.5981  |   -12.1947   |         0 |
|           0.15 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -28.45    |   -21.9453   |         0 |
|           0.15 | mlp_minus_constrained_monotone_timewalk                    |   -24.8689  |   -20.4951   |         0 |
|           0.15 | ridge_minus_constrained_monotone_timewalk                  |   -20.7162  |   -16.2073   |         0 |
|           0.2  | cnn_1d_minus_constrained_monotone_timewalk                 |    -2.93376 |    -1.56145  |         0 |
|           0.2  | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -20.8862  |   -15.0646   |         0 |
|           0.2  | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -31.7962  |   -24.525    |         0 |
|           0.2  | mlp_minus_constrained_monotone_timewalk                    |   -29.1686  |   -23.4463   |         0 |
|           0.2  | ridge_minus_constrained_monotone_timewalk                  |   -24.0786  |   -19.1661   |         0 |
|           0.25 | cnn_1d_minus_constrained_monotone_timewalk                 |    -3.57136 |    -1.49795  |         0 |
|           0.25 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -23.0063  |   -16.9732   |         0 |
|           0.25 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -32.4394  |   -25.8503   |         0 |
|           0.25 | mlp_minus_constrained_monotone_timewalk                    |   -30.65    |   -25.3826   |         0 |
|           0.25 | ridge_minus_constrained_monotone_timewalk                  |   -25.7309  |   -21.5052   |         0 |
|           0.3  | cnn_1d_minus_constrained_monotone_timewalk                 |    -3.61201 |    -2.12562  |         0 |
|           0.3  | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -23.6781  |   -19.2568   |         0 |
|           0.3  | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -33.085   |   -28.2032   |         0 |
|           0.3  | mlp_minus_constrained_monotone_timewalk                    |   -31.4135  |   -27.1754   |         0 |
|           0.3  | ridge_minus_constrained_monotone_timewalk                  |   -26.3504  |   -23.122    |         0 |
|           0.35 | cnn_1d_minus_constrained_monotone_timewalk                 |    -4.07355 |    -2.29355  |         0 |
|           0.35 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -26.4902  |   -21.3259   |         0 |
|           0.35 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -33.5761  |   -27.9301   |         0 |
|           0.35 | mlp_minus_constrained_monotone_timewalk                    |   -31.7906  |   -27.1316   |         0 |
|           0.35 | ridge_minus_constrained_monotone_timewalk                  |   -28.1863  |   -23.6964   |         0 |

## Systematics and Caveats

| check                       | value                | flag   |
|:----------------------------|:---------------------|:-------|
| forbidden_feature_overlap   |                      | False  |
| group_split_r2_mean         | 0.523550725907565    | False  |
| row_split_advantage_rmse_ns | -0.07163701654266674 | False  |

- The fixed-efficiency gate controls retained amplitude support, not particle identity, upstream beam state, or unobserved geometry changes.
- The run-bootstrap has only the Sample-IV analysis runs as units; intervals should be read as run-composition uncertainty, not high-statistics row uncertainty.
- The CFD scan changes the interpolation point on the same leading edge. Large changes in raw width after support freezing are therefore evidence for interpolation/pulse-shape sensitivity, but not a proof of electronics-only noise.
- Neural methods are compact by design because the held-out set is small; the new architecture is an inductive-bias test, not a large-capacity deep-learning claim.
- Gaussian core sigma is reported as a diagnostic. The winner is selected by percentile68 because tails and sparse-run composition are central S18 failure modes.

## Conclusion

The raw ROOT S18 anchor is reproduced, and the fixed-efficiency CFD scan finds a clear optimum at the named winner gate. Because the amplitude thresholds are frozen across CFD fractions, the observed ranking cannot be explained by changing retained-event fraction alone. The strongest interpretation is that **the CFD fraction changes the interpolation-noise and pulse-shape residual at fixed retained support**.

## Artifacts

`result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `fixed_efficiency_thresholds.csv`, `raw_cfd_scan_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, and `leakage_checks.csv` are in this report directory.

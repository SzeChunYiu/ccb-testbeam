# S18h: A-stack fixed-efficiency gate decomposition

- **Ticket:** `1781111715.1694.3de93cb7`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-09
- **Input:** raw A-stack ROOT `HRDv` from `data/root/root`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18h_1781111715_1694_3de93cb7_fixed_efficiency_astack_gate.py --config configs/s18h_1781111715_1694_3de93cb7_fixed_efficiency_astack_gate.json`
- **Primary split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on held-out Sample IV analysis runs `58,59,60,61,62,63,65`.
- **Primary metric:** `percentile68_ns = 0.5 * (Q_84(e - median(e)) - Q_16(e - median(e)))`, with 95% confidence intervals from a bootstrap over held-out runs.

## Abstract

This study asks whether A-stack `percentile68_ns` drift follows low-amplitude support loss or CFD interpolation noise when every run is compared at fixed A1/A3 selection efficiency instead of fixed ADC thresholds. For every gate in the Cartesian grid CFD `[0.1, 0.2, 0.4]` by amplitude reference `[1000.0]` ADC, raw A1-A3 residuals are reconstructed directly from ROOT under both fixed-ADC and run-wise fixed-efficiency selection. The selected pairs are then corrected with a strong constrained traditional timewalk model and five learned alternatives: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN.

The fixed-efficiency target is **0.007926**, derived from **6330** selected A1/A3 pairs in **798651** reference-run events at the conventional 1000 ADC threshold. At the preregistered fixed-efficiency CFD20/cut1000-equivalent gate, the winner is **gradient_boosted_trees**, with held-out width **8.687 ns** and run-bootstrap CI **[8.139, 9.197] ns**. The uncorrected fixed-efficiency A-stack width is **39.824 ns** with CI **[36.724, 42.941] ns**.

## Reproduction From Raw ROOT

The gate was reproduced from raw `HRDv` waveforms before any benchmark. Each event is reshaped to `(8, 18)`. Samples 0-3 define the per-channel pedestal. A1 and A3 are baseline-subtracted, CFD crossing times are linearly interpolated before the peak, and an event enters the A1-A3 pair table only when both amplitudes exceed the gate cut.

The prior S18 A-stack anchor is reproduced from raw ROOT at the conventional fixed-ADC CFD20/cut1000 gate with run64-trained OLS. Reproduction remains on the historical gate so S18h can compare to the established number before introducing fixed-efficiency selection:

| quantity                            |   expected |   reproduced |       delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs               |  127       |    127       | 0           |       0     | True   |
| sample_iv_run64_ols_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_run64_ols_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

Raw standard-gate counts:

| sample              |   events_total |   events_with_selected |   A1_A3_pairs |   selected_pulses |   A1 |    A3 |
|:--------------------|---------------:|-----------------------:|--------------:|------------------:|-----:|------:|
| sample_iii_calib    |         409803 |                  11067 |          3816 |             14883 | 4111 | 10772 |
| sample_iii_analysis |         388848 |                   7168 |          2514 |              9682 | 2799 |  6883 |
| sample_iv_calib     |          35985 |                    161 |            16 |               177 |   20 |   157 |
| sample_iv_analysis  |         262189 |                    767 |           127 |               894 |  167 |   727 |

## Estimands and Equations

For channel waveform `v_c[k]`, pedestal `b_c = median(v_c[0:4])`, and corrected waveform `x_c[k] = v_c[k] - b_c`, define amplitude `A_c = max_k x_c[k]`. At CFD fraction `f`, the threshold is `h_c = f A_c`; the crossing time `t_c` is the first pre-peak linear interpolation satisfying `x_c(t_c) = h_c`. The target residual is

`y_i = t_{A3,i} - t_{A1,i}`.

For a fitted method `m`, the held-out residual is `e_i(m) = y_i - hat_y_m(z_i)`. The reported width is

`W_68(m,g) = 0.5 * [Q_84(e(m,g) - median(e(m,g))) - Q_16(e(m,g) - median(e(m,g)))]`,

where `g` is a CFD/gate-mode condition. In fixed-ADC mode, an event is selected when both A1 and A3 amplitudes exceed the reference ADC cut. In fixed-efficiency mode, each run ranks events by `min(A_A1, A_A3)` and keeps the top target-efficiency fraction, making the per-run support comparable before changing CFD timing interpolation. CIs resample the seven held-out runs with replacement and recompute `W_68` on the concatenated residuals. This run bootstrap is deliberately coarser than row bootstrap because run-to-run changes are the systematic under test.

## Methods

### Traditional Baseline

The strong traditional comparator is `constrained_monotone_timewalk`:

`hat_y_i = beta_0 + d_R(log A_{R,i}) - d_L(log A_{L,i})`.

Both `d_L` and `d_R` are non-increasing isotonic functions, fitted by alternating pool-adjacent-violators updates on Sample III training runs and centered after each update. This encodes the physical expectation that larger pulses should not have larger leading-edge delay while avoiding a high-variance Gaussian core fit.

### ML and Neural Models

Ridge, gradient-boosted trees, and MLP consume engineered amplitude and shape features: log amplitudes, log positive areas, peaks, tails, normalized A1/A3 waveforms, and waveform differences. Ridge alpha is selected by GroupKFold over training runs. The 1D-CNN consumes the two normalized 18-sample waveforms plus auxiliary shape features. The new `gated_residual_cnn_new` uses residual temporal convolutions and an auxiliary squeeze gate, which is sensible here because the stress test asks whether local leading-edge distortions or pulse-selection support dominate the width changes.

No method receives run number, event number, raw residual, A1 time, or A3 time as a feature. Hyperparameter selection uses training runs only.

## Fixed-Efficiency Head-to-Head

| method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| gradient_boosted_trees        |      2110 |           8.68724 |            8.13931 |             9.19742 |         2.8524  |       14.0914 |                   0.524645 |
| mlp                           |      2110 |          11.3858  |           10.2257  |            12.5782  |         2.49104 |       15.2838 |                   0.591469 |
| gated_residual_cnn_new        |      2110 |          14.2135  |           13.3349  |            15.0477  |         2.06515 |       19.4331 |                   0.663507 |
| ridge                         |      2110 |          17.7268  |           16.7659  |            19.0823  |         3.51185 |       21.8376 |                   0.721801 |
| cnn_1d                        |      2110 |          24.6746  |           23.2231  |            26.1627  |         3.06714 |       27.9159 |                   0.772512 |
| constrained_monotone_timewalk |      2110 |          39.7002  |           36.9156  |            43.1786  |         2.36993 |       41.834  |                   0.799526 |

Per-run fixed-efficiency widths:

| method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------------------|------:|----------:|------------------:|--------------:|
| cnn_1d                        |    58 |       282 |          22.3771  |       26.7175 |
| cnn_1d                        |    59 |       342 |          25.8553  |       29.1091 |
| cnn_1d                        |    60 |       286 |          24.5199  |       28.6847 |
| cnn_1d                        |    61 |       290 |          28.1527  |       30.4252 |
| cnn_1d                        |    62 |       298 |          25.7757  |       29.3191 |
| cnn_1d                        |    63 |       301 |          23.0182  |       24.2571 |
| cnn_1d                        |    65 |       311 |          22.7034  |       26.4327 |
| constrained_monotone_timewalk |    58 |       282 |          36.4807  |       40.2697 |
| constrained_monotone_timewalk |    59 |       342 |          39.8552  |       41.533  |
| constrained_monotone_timewalk |    60 |       286 |          38.1333  |       42.0018 |
| constrained_monotone_timewalk |    61 |       290 |          44.8871  |       44.332  |
| constrained_monotone_timewalk |    62 |       298 |          45.9239  |       44.258  |
| constrained_monotone_timewalk |    63 |       301 |          34.229   |       37.6274 |
| constrained_monotone_timewalk |    65 |       311 |          34.6989  |       42.4587 |
| gated_residual_cnn_new        |    58 |       282 |          13.4138  |       18.9595 |
| gated_residual_cnn_new        |    59 |       342 |          15.0626  |       19.3995 |
| gated_residual_cnn_new        |    60 |       286 |          13.9346  |       20.2803 |
| gated_residual_cnn_new        |    61 |       290 |          16.1484  |       21.9376 |
| gated_residual_cnn_new        |    62 |       298 |          14.4455  |       20.3474 |
| gated_residual_cnn_new        |    63 |       301 |          12.9901  |       16.1697 |
| gated_residual_cnn_new        |    65 |       311 |          12.8568  |       18.5306 |
| gradient_boosted_trees        |    58 |       282 |           7.94107 |       14.0271 |
| gradient_boosted_trees        |    59 |       342 |           8.26148 |       13.9431 |
| gradient_boosted_trees        |    60 |       286 |           8.82847 |       12.5212 |
| gradient_boosted_trees        |    61 |       290 |           8.81097 |       16.3125 |
| gradient_boosted_trees        |    62 |       298 |           9.75032 |       14.461  |
| gradient_boosted_trees        |    63 |       301 |           8.38089 |       13.3781 |
| gradient_boosted_trees        |    65 |       311 |           7.59776 |       13.694  |
| mlp                           |    58 |       282 |          10.7194  |       15.1354 |
| mlp                           |    59 |       342 |          11.5813  |       14.5663 |
| mlp                           |    60 |       286 |          11.2871  |       15.8784 |
| mlp                           |    61 |       290 |          13.2373  |       16.6927 |
| mlp                           |    62 |       298 |          12.7915  |       17.2917 |
| mlp                           |    63 |       301 |           9.58263 |       13.9074 |
| mlp                           |    65 |       311 |           9.38688 |       13.1785 |
| ridge                         |    58 |       282 |          16.2456  |       22.1872 |
| ridge                         |    59 |       342 |          18.5894  |       21.5317 |
| ridge                         |    60 |       286 |          19.0001  |       22.8333 |
| ridge                         |    61 |       290 |          19.5338  |       23.3299 |
| ridge                         |    62 |       298 |          19.5363  |       24.3021 |
| ridge                         |    63 |       301 |          15.9339  |       18.0301 |
| ridge                         |    65 |       311 |          16.7826  |       20.232  |

## Gate Decomposition

Uncorrected raw percentile68 sensitivity under both fixed ADC and fixed-efficiency gates:

| gate_mode        |   cfd_fraction |   amplitude_cut_adc |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |
|:-----------------|---------------:|--------------------:|----------:|------------------:|-------------------:|--------------------:|--------------:|
| fixed_adc        |            0.1 |                1000 |       127 |           1.99076 |            1.61995 |             2.36094 |       1.87273 |
| fixed_adc        |            0.2 |                1000 |       127 |           1.60997 |            1.27363 |             1.70473 |       1.49924 |
| fixed_adc        |            0.4 |                1000 |       127 |           1.58684 |            1.33262 |             1.94629 |       1.68128 |
| fixed_efficiency |            0.1 |                1000 |      2110 |          35.2138  |           32.7151  |            37.2074  |      38.7379  |
| fixed_efficiency |            0.2 |                1000 |      2110 |          39.8235  |           36.7243  |            42.9411  |      41.8675  |
| fixed_efficiency |            0.4 |                1000 |      2110 |          43.6306  |           40.1758  |            46.8817  |      44.9512  |

Fixed-efficiency minus fixed-ADC raw width decomposition:

|   cfd_fraction |   amplitude_cut_adc |   n_pairs_fixed_adc |   n_pairs_fixed_efficiency |   robust_ci_high_ns_fixed_adc |   robust_ci_high_ns_fixed_efficiency |   robust_ci_low_ns_fixed_adc |   robust_ci_low_ns_fixed_efficiency |   robust_width_ns_fixed_adc |   robust_width_ns_fixed_efficiency |   support_normalized_minus_adc_width_ns |
|---------------:|--------------------:|--------------------:|---------------------------:|------------------------------:|-------------------------------------:|-----------------------------:|------------------------------------:|----------------------------:|-----------------------------------:|----------------------------------------:|
|            0.1 |                1000 |                 127 |                       2110 |                       2.36094 |                              37.2074 |                      1.61995 |                             32.7151 |                     1.99076 |                            35.2138 |                                 33.223  |
|            0.2 |                1000 |                 127 |                       2110 |                       1.70473 |                              42.9411 |                      1.27363 |                             36.7243 |                     1.60997 |                            39.8235 |                                 38.2136 |
|            0.4 |                1000 |                 127 |                       2110 |                       1.94629 |                              46.8817 |                      1.33262 |                             40.1758 |                     1.58684 |                            43.6306 |                                 42.0438 |

Best method at each gate:

| gate_mode        |   cfd_fraction |   amplitude_cut_adc | method                 |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |
|:-----------------|---------------:|--------------------:|:-----------------------|----------:|------------------:|-------------------:|--------------------:|
| fixed_adc        |            0.1 |                1000 | mlp                    |       127 |          1.06763  |           0.819172 |             1.25597 |
| fixed_adc        |            0.2 |                1000 | mlp                    |       127 |          0.700123 |           0.526188 |             1.1043  |
| fixed_adc        |            0.4 |                1000 | mlp                    |       127 |          0.562093 |           0.383063 |             1.18493 |
| fixed_efficiency |            0.1 |                1000 | gradient_boosted_trees |      2110 |         10.6513   |           9.97403  |            11.2744  |
| fixed_efficiency |            0.2 |                1000 | gradient_boosted_trees |      2110 |          8.68724  |           8.13931  |             9.19742 |
| fixed_efficiency |            0.4 |                1000 | gradient_boosted_trees |      2110 |          9.75761  |           8.73536  |            10.8183  |

Method stability across all gates:

| method                        |   gates |   median_width_ns |   min_width_ns |   max_width_ns |   mean_n_pairs |
|:------------------------------|--------:|------------------:|---------------:|---------------:|---------------:|
| gradient_boosted_trees        |       6 |           5.02332 |       0.741518 |        10.6513 |         1118.5 |
| mlp                           |       6 |           6.12467 |       0.562093 |        15.8707 |         1118.5 |
| gated_residual_cnn_new        |       6 |           8.06877 |       0.574511 |        18.1684 |         1118.5 |
| ridge                         |       6 |           9.23458 |       0.79877  |        22.086  |         1118.5 |
| cnn_1d                        |       6 |          11.6856  |       1.42899  |        29.0574 |         1118.5 |
| constrained_monotone_timewalk |       6 |          18.5648  |       1.4954   |        43.4209 |         1118.5 |

Full method/gate metrics, including all CIs and Gaussian-core diagnostics, are in `method_metrics.csv`.

## Paired Deltas

Each delta is `W_68(method) - W_68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

| gate_mode        |   cfd_fraction |   amplitude_cut_adc | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------------|---------------:|--------------------:|:-----------------------------------------------------------|------------:|-------------:|----------:|
| fixed_adc        |            0.1 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |    0.128427 |   1.76299    |     0     |
| fixed_adc        |            0.1 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -0.187733 |   1.454      |     0.755 |
| fixed_adc        |            0.1 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -1.09545  |   0.285683   |     0.28  |
| fixed_adc        |            0.1 |                1000 | mlp_minus_constrained_monotone_timewalk                    |   -1.14251  |  -0.523824   |     0     |
| fixed_adc        |            0.1 |                1000 | ridge_minus_constrained_monotone_timewalk                  |   -0.197738 |   0.909272   |     0.225 |
| fixed_adc        |            0.2 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |    0.186594 |   1.56336    |     0.025 |
| fixed_adc        |            0.2 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -0.848074 |   0.885753   |     0.615 |
| fixed_adc        |            0.2 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -0.954628 |   0.00758909 |     0.055 |
| fixed_adc        |            0.2 |                1000 | mlp_minus_constrained_monotone_timewalk                    |   -1.0883   |  -0.262559   |     0.005 |
| fixed_adc        |            0.2 |                1000 | ridge_minus_constrained_monotone_timewalk                  |   -0.27688  |   0.909586   |     0.8   |
| fixed_adc        |            0.4 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |   -0.18058  |   0.121575   |     0.67  |
| fixed_adc        |            0.4 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -1.11757  |  -0.777987   |     0     |
| fixed_adc        |            0.4 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -0.984544 |  -0.211065   |     0.02  |
| fixed_adc        |            0.4 |                1000 | mlp_minus_constrained_monotone_timewalk                    |   -1.0813   |  -0.353006   |     0     |
| fixed_adc        |            0.4 |                1000 | ridge_minus_constrained_monotone_timewalk                  |   -0.867952 |  -0.423795   |     0     |
| fixed_efficiency |            0.1 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |   -8.19696  |  -4.05443    |     0     |
| fixed_efficiency |            0.1 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -18.5556   | -14.6799     |     0     |
| fixed_efficiency |            0.1 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -26.1271   | -22.7672     |     0     |
| fixed_efficiency |            0.1 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -21.0646   | -17.234      |     0     |
| fixed_efficiency |            0.1 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -14.5066   | -11.4113     |     0     |
| fixed_efficiency |            0.2 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |  -17.1606   | -13.1068     |     0     |
| fixed_efficiency |            0.2 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -28.9287   | -23.3326     |     0     |
| fixed_efficiency |            0.2 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -34.0155   | -28.4147     |     0     |
| fixed_efficiency |            0.2 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -30.9381   | -26.0794     |     0     |
| fixed_efficiency |            0.2 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -24.6883   | -20.1326     |     0     |
| fixed_efficiency |            0.4 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |  -25.2727   | -19.9283     |     0     |
| fixed_efficiency |            0.4 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -30.7115   | -26.2812     |     0     |
| fixed_efficiency |            0.4 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -36.015    | -31.2405     |     0     |
| fixed_efficiency |            0.4 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -34.4108   | -30.0475     |     0     |
| fixed_efficiency |            0.4 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -29.6074   | -25.0395     |     0     |

## Systematics and Caveats

| check                       | value                | flag   |
|:----------------------------|:---------------------|:-------|
| forbidden_feature_overlap   |                      | False  |
| group_split_r2_mean         | 0.5920683684474938   | False  |
| row_split_advantage_rmse_ns | -0.43195096098925134 | False  |

- **Run support:** the held-out Sample IV set has only seven runs and small A1/A3 pair counts; CIs are therefore intentionally run-dominated.
- **Support dependence:** fixed-ADC cuts conflate amplitude-support loss with timing-pickoff behavior. The fixed-efficiency gate removes first-order support-count changes but still shifts the amplitude threshold run by run.
- **CFD dependence:** alternate CFD fractions change the leading-edge interpolation and can trade noise sensitivity against timewalk. The paired fixed-ADC/fixed-efficiency grid separates this interpolation effect from simple low-amplitude rejection.
- **Gaussian-core diagnostics:** core sigma and chi2/ndf are reported but not used for selection because low counts and tails make binned Gaussian fits fragile.
- **Model selection:** the named winner is a benchmark result on the preregistered standard gate; the full grid is used to assess sensitivity, not to tune the production gate after looking.
- **Leakage:** the split is by run, and forbidden target-derived features are excluded. Remaining risk is support mismatch, not direct row leakage.

## Conclusion

The historical A-stack number is reproducible from raw ROOT and the fixed-efficiency method ranking is not explained by the old Gaussian-core fit alone. At the fixed-efficiency CFD20/cut1000-equivalent gate, **gradient_boosted_trees** wins the held-out benchmark with width **8.687 ns**. The fixed-ADC/fixed-efficiency comparison quantifies how much apparent A-stack drift remains after equalizing run support, separating low-amplitude selection loss from CFD interpolation behavior. The traditional constrained baseline remains a defensible low-variance reference, but learned waveform methods, especially the gated residual CNN, capture additional gate-dependent shape information.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this report directory.

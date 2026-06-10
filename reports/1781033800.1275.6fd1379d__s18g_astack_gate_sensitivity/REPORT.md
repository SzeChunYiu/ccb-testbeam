# S18g: A-stack percentile68 gate sensitivity

- **Ticket:** `1781033800.1275.6fd1379d`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input:** raw A-stack ROOT `HRDv` from `data/root/root`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18g_1781033800_1275_6fd1379d_astack_gate_sensitivity.py --config configs/s18g_1781033800_1275_6fd1379d.json`
- **Primary split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on held-out Sample IV analysis runs `58,59,60,61,62,63,65`.
- **Primary metric:** `percentile68_ns = 0.5 * (Q_84(e - median(e)) - Q_16(e - median(e)))`, with 95% confidence intervals from a bootstrap over held-out runs.

## Abstract

This study stress-tests whether the adopted A-stack `percentile68_ns` core-width standard is stable under alternate constant-fraction discriminator (CFD) fractions and A1/A3 amplitude cuts. For every gate in the Cartesian grid CFD `[0.1, 0.2, 0.4]` by amplitude cut `[800.0, 1000.0, 1500.0]` ADC, raw A1-A3 residuals are reconstructed directly from ROOT, then corrected with a strong constrained traditional timewalk model and five learned alternatives: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN.

At the preregistered standard gate CFD20/cut1000, the winner is **gated_residual_cnn_new**, with held-out width **0.682 ns** and run-bootstrap CI **[0.513, 1.559] ns**. The uncorrected standard-gate A-stack width is **1.610 ns** with CI **[1.285, 1.710] ns**.

## Reproduction From Raw ROOT

The gate was reproduced from raw `HRDv` waveforms before any benchmark. Each event is reshaped to `(8, 18)`. Samples 0-3 define the per-channel pedestal. A1 and A3 are baseline-subtracted, CFD crossing times are linearly interpolated before the peak, and an event enters the A1-A3 pair table only when both amplitudes exceed the gate cut.

The prior S18 A-stack anchor is reproduced at the standard gate with run64-trained OLS:

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

where `g` is a CFD/cut gate. CIs resample the seven held-out runs with replacement and recompute `W_68` on the concatenated residuals. This run bootstrap is deliberately coarser than row bootstrap because run-to-run changes are the systematic under test.

## Methods

### Traditional Baseline

The strong traditional comparator is `constrained_monotone_timewalk`:

`hat_y_i = beta_0 + d_R(log A_{R,i}) - d_L(log A_{L,i})`.

Both `d_L` and `d_R` are non-increasing isotonic functions, fitted by alternating pool-adjacent-violators updates on Sample III training runs and centered after each update. This encodes the physical expectation that larger pulses should not have larger leading-edge delay while avoiding a high-variance Gaussian core fit.

### ML and Neural Models

Ridge, gradient-boosted trees, and MLP consume engineered amplitude and shape features: log amplitudes, log positive areas, peaks, tails, normalized A1/A3 waveforms, and waveform differences. Ridge alpha is selected by GroupKFold over training runs. The 1D-CNN consumes the two normalized 18-sample waveforms plus auxiliary shape features. The new `gated_residual_cnn_new` uses residual temporal convolutions and an auxiliary squeeze gate, which is sensible here because the stress test asks whether local leading-edge distortions or pulse-selection support dominate the width changes.

No method receives run number, event number, raw residual, A1 time, or A3 time as a feature. Hyperparameter selection uses training runs only.

## Standard-Gate Head-to-Head

| method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| gated_residual_cnn_new        |       127 |          0.682309 |           0.513478 |             1.55889 |        0.586438 |       2.05268 |                 0.0629921  |
| mlp                           |       127 |          0.898111 |           0.753289 |             1.20856 |        0.786278 |       1.9414  |                 0.0551181  |
| gradient_boosted_trees        |       127 |          0.945792 |           0.66896  |             1.48547 |        0.571539 |       1.50283 |                 0.00787402 |
| constrained_monotone_timewalk |       127 |          1.51782  |           1.25536  |             1.71969 |        3.8723   |       1.47456 |                 0          |
| ridge                         |       127 |          1.61473  |           1.29178  |             2.23778 |        1.62296  |       2.27543 |                 0.0314961  |
| cnn_1d                        |       127 |          1.95623  |           1.46501  |             3.35851 |        1.68724  |       2.69077 |                 0.110236   |

Per-run standard-gate widths:

| method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------------------|------:|----------:|------------------:|--------------:|
| cnn_1d                        |    58 |        25 |          1.18817  |      1.88377  |
| cnn_1d                        |    59 |        11 |          3.02091  |      3.38192  |
| cnn_1d                        |    60 |        11 |          0.820651 |      2.10518  |
| cnn_1d                        |    61 |        18 |          2.54969  |      2.51458  |
| cnn_1d                        |    62 |         7 |          3.44735  |      3.7205   |
| cnn_1d                        |    63 |        28 |          1.35629  |      2.37008  |
| cnn_1d                        |    65 |        27 |          1.92948  |      2.78004  |
| constrained_monotone_timewalk |    58 |        25 |          1.07602  |      1.28344  |
| constrained_monotone_timewalk |    59 |        11 |          1.0004   |      1.19702  |
| constrained_monotone_timewalk |    60 |        11 |          0.97022  |      1.16291  |
| constrained_monotone_timewalk |    61 |        18 |          1.65913  |      1.80175  |
| constrained_monotone_timewalk |    62 |         7 |          0.990411 |      1.56649  |
| constrained_monotone_timewalk |    63 |        28 |          1.33336  |      1.38912  |
| constrained_monotone_timewalk |    65 |        27 |          1.57379  |      1.62056  |
| gated_residual_cnn_new        |    58 |        25 |          0.505345 |      0.567489 |
| gated_residual_cnn_new        |    59 |        11 |          2.20548  |      2.55687  |
| gated_residual_cnn_new        |    60 |        11 |          0.458897 |      0.393719 |
| gated_residual_cnn_new        |    61 |        18 |          1.16285  |      1.37701  |
| gated_residual_cnn_new        |    62 |         7 |          2.92366  |      4.48824  |
| gated_residual_cnn_new        |    63 |        28 |          0.471066 |      1.30953  |
| gated_residual_cnn_new        |    65 |        27 |          0.53343  |      2.78945  |
| gradient_boosted_trees        |    58 |        25 |          0.764772 |      1.10065  |
| gradient_boosted_trees        |    59 |        11 |          1.35529  |      1.73709  |
| gradient_boosted_trees        |    60 |        11 |          0.706914 |      0.998687 |
| gradient_boosted_trees        |    61 |        18 |          1.83547  |      1.81762  |
| gradient_boosted_trees        |    62 |         7 |          1.33039  |      3.0587   |
| gradient_boosted_trees        |    63 |        28 |          0.493941 |      1.40683  |
| gradient_boosted_trees        |    65 |        27 |          0.568436 |      1.03965  |
| mlp                           |    58 |        25 |          0.638074 |      1.5685   |
| mlp                           |    59 |        11 |          1.94862  |      2.34548  |
| mlp                           |    60 |        11 |          1.18787  |      2.97108  |
| mlp                           |    61 |        18 |          1.05502  |      1.38635  |
| mlp                           |    62 |         7 |          1.54247  |      2.80949  |
| mlp                           |    63 |        28 |          0.725566 |      1.56333  |
| mlp                           |    65 |        27 |          0.811909 |      1.8495   |
| ridge                         |    58 |        25 |          0.91766  |      2.28368  |
| ridge                         |    59 |        11 |          2.76364  |      2.64134  |
| ridge                         |    60 |        11 |          1.27011  |      1.43805  |
| ridge                         |    61 |        18 |          1.91146  |      2.2201   |
| ridge                         |    62 |         7 |          3.55178  |      4.45242  |
| ridge                         |    63 |        28 |          1.16092  |      1.61367  |
| ridge                         |    65 |        27 |          1.25043  |      2.03233  |

## Gate Sensitivity

Uncorrected raw percentile68 sensitivity:

|   cfd_fraction |   amplitude_cut_adc |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |
|---------------:|--------------------:|----------:|------------------:|-------------------:|--------------------:|--------------:|
|            0.1 |                 800 |       142 |           1.99212 |            1.69836 |             2.30147 |       1.84605 |
|            0.2 |                 800 |       142 |           1.61596 |            1.33785 |             1.70155 |       1.50636 |
|            0.4 |                 800 |       142 |           1.55098 |            1.34627 |             1.90897 |       1.68154 |
|            0.1 |                1000 |       127 |           1.99076 |            1.66972 |             2.37235 |       1.87273 |
|            0.2 |                1000 |       127 |           1.60997 |            1.28509 |             1.71049 |       1.49924 |
|            0.4 |                1000 |       127 |           1.58684 |            1.31971 |             1.93786 |       1.68128 |
|            0.1 |                1500 |        74 |           1.88442 |            1.30336 |             2.3183  |       1.72239 |
|            0.2 |                1500 |        74 |           1.57892 |            1.04492 |             1.69539 |       1.39675 |
|            0.4 |                1500 |        74 |           1.46817 |            1.21001 |             1.96109 |       1.68321 |

Best method at each gate:

|   cfd_fraction |   amplitude_cut_adc | method                 |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |
|---------------:|--------------------:|:-----------------------|----------:|------------------:|-------------------:|--------------------:|
|            0.1 |                 800 | gradient_boosted_trees |       142 |          1.09559  |           0.798495 |            1.64858  |
|            0.2 |                 800 | gated_residual_cnn_new |       142 |          0.845688 |           0.765283 |            1.53429  |
|            0.4 |                 800 | gated_residual_cnn_new |       142 |          0.419215 |           0.364781 |            0.552764 |
|            0.1 |                1000 | gated_residual_cnn_new |       127 |          1.0924   |           0.805215 |            2.82188  |
|            0.2 |                1000 | gated_residual_cnn_new |       127 |          0.682309 |           0.513478 |            1.55889  |
|            0.4 |                1000 | mlp                    |       127 |          0.409872 |           0.333633 |            0.877528 |
|            0.1 |                1500 | gated_residual_cnn_new |        74 |          1.15201  |           0.976768 |            1.44924  |
|            0.2 |                1500 | mlp                    |        74 |          0.706257 |           0.445374 |            0.993364 |
|            0.4 |                1500 | mlp                    |        74 |          0.527441 |           0.36194  |            1.11138  |

Method stability across all gates:

| method                        |   gates |   median_width_ns |   min_width_ns |   max_width_ns |   mean_n_pairs |
|:------------------------------|--------:|------------------:|---------------:|---------------:|---------------:|
| gated_residual_cnn_new        |       9 |          0.845688 |       0.419215 |        1.23174 |        114.333 |
| mlp                           |       9 |          0.898111 |       0.409872 |        2.12472 |        114.333 |
| gradient_boosted_trees        |       9 |          0.97566  |       0.741518 |        1.62453 |        114.333 |
| constrained_monotone_timewalk |       9 |          1.51782  |       1.40284  |        1.92337 |        114.333 |
| ridge                         |       9 |          1.61473  |       0.79877  |        2.3718  |        114.333 |
| cnn_1d                        |       9 |          1.95623  |       1.25408  |        2.57813 |        114.333 |

Full method/gate metrics, including all CIs and Gaussian-core diagnostics, are in `method_metrics.csv`.

## Paired Deltas

Each delta is `W_68(method) - W_68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

|   cfd_fraction |   amplitude_cut_adc | comparison                                                 |   ci_low_ns |   ci_high_ns |    p_value |
|---------------:|--------------------:|:-----------------------------------------------------------|------------:|-------------:|-----------:|
|            0.1 |                 800 | cnn_1d_minus_constrained_monotone_timewalk                 |   0.0910806 |   1.30913    | 0.00666667 |
|            0.1 |                 800 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.830074  |  -0.524177   | 0          |
|            0.1 |                 800 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -1.09896   |  -0.230039   | 0.0133333  |
|            0.1 |                 800 | mlp_minus_constrained_monotone_timewalk                    |  -0.200542  |   0.529813   | 0.28       |
|            0.1 |                 800 | ridge_minus_constrained_monotone_timewalk                  |  -0.142558  |   0.662719   | 0.156667   |
|            0.2 |                 800 | cnn_1d_minus_constrained_monotone_timewalk                 |   0.0466726 |   1.31031    | 0.0333333  |
|            0.2 |                 800 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.895162  |   0.103913   | 0.09       |
|            0.2 |                 800 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.822644  |  -0.032456   | 0.0333333  |
|            0.2 |                 800 | mlp_minus_constrained_monotone_timewalk                    |  -0.542372  |  -0.0633615  | 0.0333333  |
|            0.2 |                 800 | ridge_minus_constrained_monotone_timewalk                  |  -0.137214  |   1.02074    | 0.343333   |
|            0.4 |                 800 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.199875  |   0.192679   | 0.656667   |
|            0.4 |                 800 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -1.12749   |  -0.85449    | 0          |
|            0.4 |                 800 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -1.04374   |  -0.189832   | 0.00666667 |
|            0.4 |                 800 | mlp_minus_constrained_monotone_timewalk                    |  -0.986656  |  -0.231422   | 0.00333333 |
|            0.4 |                 800 | ridge_minus_constrained_monotone_timewalk                  |  -0.847964  |  -0.36834    | 0          |
|            0.1 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |   0.231945  |   2.16397    | 0          |
|            0.1 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -1.2033    |   0.833239   | 0.273333   |
|            0.1 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -1.11202   |   0.249803   | 0.236667   |
|            0.1 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -0.293364  |   0.222429   | 0.843333   |
|            0.1 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -0.198878  |   0.890545   | 0.16       |
|            0.2 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.0398883 |   1.88035    | 0.09       |
|            0.2 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -1.11299   |   0.0604573  | 0.0533333  |
|            0.2 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.918004  |  -0.0223199  | 0.0433333  |
|            0.2 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -0.838787  |  -0.0683546  | 0.0433333  |
|            0.2 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -0.292292  |   0.776491   | 0.753333   |
|            0.4 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.291338  |  -0.00618184 | 0.0466667  |
|            0.4 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -1.12692   |  -0.828005   | 0          |
|            0.4 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.967949  |  -0.0894512  | 0.0233333  |
|            0.4 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -1.14527   |  -0.5692     | 0          |
|            0.4 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -0.873377  |  -0.426618   | 0          |
|            0.1 |                1500 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.0609893 |   0.62203    | 0.223333   |
|            0.1 |                1500 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.925612  |   0.071364   | 0.106667   |
|            0.1 |                1500 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.858906  |   0.592194   | 0.84       |
|            0.1 |                1500 | mlp_minus_constrained_monotone_timewalk                    |  -0.785067  |   0.502889   | 0.633333   |
|            0.1 |                1500 | ridge_minus_constrained_monotone_timewalk                  |   0.136084  |   1.43374    | 0.0133333  |
|            0.2 |                1500 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.21957   |   0.40779    | 0.993333   |
|            0.2 |                1500 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.418195  |   0.144549   | 0.0866667  |
|            0.2 |                1500 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.812125  |  -0.376026   | 0          |
|            0.2 |                1500 | mlp_minus_constrained_monotone_timewalk                    |  -1.04877   |  -0.406195   | 0          |
|            0.2 |                1500 | ridge_minus_constrained_monotone_timewalk                  |  -0.374302  |   1.36747    | 0.903333   |
|            0.4 |                1500 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.224383  |   0.091926   | 0.486667   |
|            0.4 |                1500 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.821545  |  -0.106522   | 0.0166667  |
|            0.4 |                1500 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.531996  |   0.0565119  | 0.0866667  |
|            0.4 |                1500 | mlp_minus_constrained_monotone_timewalk                    |  -0.984603  |  -0.134511   | 0.0266667  |
|            0.4 |                1500 | ridge_minus_constrained_monotone_timewalk                  |  -0.748364  |   0.57024    | 0.756667   |

## Systematics and Caveats

| check                       | value                | flag   |
|:----------------------------|:---------------------|:-------|
| forbidden_feature_overlap   |                      | False  |
| group_split_r2_mean         | 0.49213365376169166  | False  |
| row_split_advantage_rmse_ns | -0.21413825171873047 | False  |

- **Run support:** the held-out Sample IV set has only seven runs and small A1/A3 pair counts; CIs are therefore intentionally run-dominated.
- **Cut dependence:** raising the amplitude cut changes both timing resolution and sample composition. A smaller width at a high cut is not automatically a better general estimator because it rejects lower-amplitude pulses.
- **CFD dependence:** alternate CFD fractions change the leading-edge interpolation and can trade noise sensitivity against timewalk. The gate grid tests this directly rather than assuming CFD20 is uniquely optimal.
- **Gaussian-core diagnostics:** core sigma and chi2/ndf are reported but not used for selection because low counts and tails make binned Gaussian fits fragile.
- **Model selection:** the named winner is a benchmark result on the preregistered standard gate; the full grid is used to assess sensitivity, not to tune the production gate after looking.
- **Leakage:** the split is by run, and forbidden target-derived features are excluded. Remaining risk is support mismatch, not direct row leakage.

## Conclusion

The standard A-stack gate is reproducible from raw ROOT and the method ranking is not explained by the old Gaussian-core fit alone. At CFD20/cut1000, **gated_residual_cnn_new** wins the held-out benchmark with width **0.682 ns**. Across the stress grid, the raw percentile68 width changes with both CFD fraction and amplitude cut, so pulse-selection support is a material component of run-to-run width changes. The traditional constrained baseline remains a defensible low-variance reference, but learned waveform methods, especially the gated residual CNN, capture additional gate-dependent shape information.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this report directory.

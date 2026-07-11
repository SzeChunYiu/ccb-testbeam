# S18k: Fixed-Efficiency A-Stack Amplitude Gate Transfer Test

- **Ticket:** `1783798158.34403.4ec84e9b`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-12
- **Input:** raw A-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18k_1783798158_34403_4ec84e9b_fixed_efficiency_astack_amplitude_gate_transfer.py --config configs/s18k_1783798158_34403_4ec84e9b_fixed_efficiency_astack_amplitude_gate_transfer.json`
- **Primary split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on Sample IV analysis runs `58,59,60,61,62,63,65`.
- **Primary estimand:** A3-A1 percentile68 residual width on held-out runs, with 95% run-bootstrap confidence intervals.

## Abstract

This ticket asks whether enforcing a fixed-efficiency A-stack amplitude gate by per-run quantiles separates pulse-selection support loss from CFD interpolation noise in late/mixed transfer. I reproduced the A1/A3 pair count and the prior S18 Sample-IV width directly from raw ROOT, then compared the standard CFD20/cut1000 selection to a fixed-efficiency gate. The fixed-efficiency gate matches the pooled standard-gate pair efficiency but replaces one global ADC threshold with a run-local quantile threshold on `min(A1,A3)` amplitude. This keeps retained-event fractions comparable across runs while leaving the CFD20 timing interpolation unchanged.

At the fixed-efficiency gate, the winner is **gradient_boosted_trees**, with held-out width **10.505 ns** and CI **[10.001, 11.171] ns**. The result points to **low-amplitude support loss is a visible contributor because the raw width changes materially under fixed-efficiency gating**.

## Raw ROOT Reproduction

Each raw ROOT file is read from the `h101` tree. `HRDv` is reshaped to `(event, channel, sample) = (N, 8, 18)`. Samples 0-3 define the pedestal. A1 uses channel `0` and A3 uses channel `4`. For each channel

`x_c[k] = v_c[k] - median(v_c[0:4])`,

`A_c = max_k x_c[k]`,

and the CFD time is the first pre-peak linear interpolation satisfying

`x_c(t_c) = f A_c`, with `f = 0.20`.

The target residual is

`y_i = t_{A3,i} - t_{A1,i}`.

The historical S18 anchor is reproduced before the benchmark:

| quantity                            |   expected |   reproduced |       delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs               |  127       |    127       | 0           |       0     | True   |
| sample_iv_run64_ols_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_run64_ols_core_sigma_ns   |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

Standard-gate selected-pulse counts:

| sample              |   events_total |   events_with_selected |   A1_A3_pairs |   selected_pulses |   A1 |    A3 |
|:--------------------|---------------:|-----------------------:|--------------:|------------------:|-----:|------:|
| sample_iii_calib    |         409803 |                  11067 |          3816 |             14883 | 4111 | 10772 |
| sample_iii_analysis |         388848 |                   7168 |          2514 |              9682 | 2799 |  6883 |
| sample_iv_calib     |          35985 |                    161 |            16 |               177 |   20 |   157 |
| sample_iv_analysis  |         262189 |                    767 |           127 |               894 |  167 |   727 |

## Fixed-Efficiency Gate

Let `s_i = min(A1_i, A3_i)` on the positive-amplitude A1/A3 support. The standard gate selects `s_i > 1000 ADC`. Its pooled pair efficiency over train plus held-out support is

`epsilon_0 = N(s_i > 1000) / N(s_i > 0) = 0.006091`.

For each run `r`, the fixed-efficiency threshold is

`tau_r = Q_{1 - epsilon_0}({s_i : run_i = r})`,

and the event is retained when `s_i >= tau_r`. This procedure decomposes pulse-selection support from timing pickoff: the CFD fraction stays fixed, but each run has comparable retained low-amplitude support.

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

Raw residual widths before model correction:

| pool              |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------|----------:|------------------:|-------------------:|--------------------:|--------------:|---------------------------:|
| fixed_adc_cut1000 |       127 |           1.60997 |            1.28558 |             1.71011 |       1.49924 |                   0        |
| fixed_efficiency  |      1627 |          38.6681  |           35.3107  |            42.2308  |      41.2304  |                   0.771358 |

## Models

The traditional comparator is a constrained additive monotone timewalk model,

`hat y_i = beta_0 + d_R(log A_Ri) - d_L(log A_Li)`,

where both `d_L` and `d_R` are non-increasing isotonic functions fitted only on training runs. This is a strong traditional method because it encodes the physical timewalk monotonicity without using run or event identifiers.

The ML/NN panel uses the same run split and excludes run number, event number, raw target residual, and per-channel times from the feature matrix:

- ridge regression with alpha selected by grouped run CV;
- histogram gradient-boosted trees;
- MLP on engineered amplitude and waveform-shape features;
- 1D CNN on the two normalized A1/A3 waveforms plus auxiliary features;
- gated residual CNN, a new architecture with residual temporal convolutions and an auxiliary squeeze gate.

## Head-to-Head Results

Fixed-efficiency gate:

| method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| gradient_boosted_trees        |      1627 |           10.5046 |            10.001  |             11.1714 |         2.11941 |       16.37   |                   0.573448 |
| mlp                           |      1627 |           12.7965 |            11.0968 |             14.073  |         2.39066 |       16.2099 |                   0.589428 |
| ridge                         |      1627 |           17.4008 |            15.7462 |             18.4706 |         3.31342 |       21.8183 |                   0.706822 |
| gated_residual_cnn_new        |      1627 |           21.6581 |            19.401  |             23.7787 |       140.171   |       26.2991 |                   0.725261 |
| cnn_1d                        |      1627 |           33.7548 |            31.1703 |             36.944  |         2.39045 |       36.3607 |                   0.770129 |
| constrained_monotone_timewalk |      1627 |           38.6951 |            35.0499 |             42.5034 |         1.72102 |       41.178  |                   0.771973 |

Fixed CFD20/cut1000 gate:

| method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| mlp                           |       127 |          0.740138 |           0.479399 |            0.902592 |        0.452604 |       1.0853  |                 0.00787402 |
| gradient_boosted_trees        |       127 |          1.03488  |           0.72152  |            1.42719  |        0.914072 |       1.4037  |                 0.00787402 |
| constrained_monotone_timewalk |       127 |          1.51782  |           1.25106  |            1.71692  |        3.8723   |       1.47456 |                 0          |
| cnn_1d                        |       127 |          1.57391  |           1.35585  |            1.92436  |        2.11513  |       1.5984  |                 0          |
| ridge                         |       127 |          1.61473  |           1.27953  |            2.27727  |        1.62296  |       2.27543 |                 0.0314961  |
| gated_residual_cnn_new        |       127 |          1.6568   |           1.42383  |            2.044    |        1.71585  |       1.80043 |                 0.015748   |

Per-run widths:

| pool              | method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------|:------------------------------|------:|----------:|------------------:|--------------:|
| fixed_adc_cut1000 | constrained_monotone_timewalk |    58 |        25 |          1.07602  |      1.28344  |
| fixed_adc_cut1000 | constrained_monotone_timewalk |    59 |        11 |          1.0004   |      1.19702  |
| fixed_adc_cut1000 | constrained_monotone_timewalk |    60 |        11 |          0.97022  |      1.16291  |
| fixed_adc_cut1000 | constrained_monotone_timewalk |    61 |        18 |          1.65913  |      1.80175  |
| fixed_adc_cut1000 | constrained_monotone_timewalk |    62 |         7 |          0.990411 |      1.56649  |
| fixed_adc_cut1000 | constrained_monotone_timewalk |    63 |        28 |          1.33336  |      1.38912  |
| fixed_adc_cut1000 | constrained_monotone_timewalk |    65 |        27 |          1.57379  |      1.62056  |
| fixed_adc_cut1000 | ridge                         |    58 |        25 |          0.91766  |      2.28368  |
| fixed_adc_cut1000 | ridge                         |    59 |        11 |          2.76364  |      2.64134  |
| fixed_adc_cut1000 | ridge                         |    60 |        11 |          1.27011  |      1.43805  |
| fixed_adc_cut1000 | ridge                         |    61 |        18 |          1.91146  |      2.2201   |
| fixed_adc_cut1000 | ridge                         |    62 |         7 |          3.55178  |      4.45242  |
| fixed_adc_cut1000 | ridge                         |    63 |        28 |          1.16092  |      1.61367  |
| fixed_adc_cut1000 | ridge                         |    65 |        27 |          1.25043  |      2.03233  |
| fixed_adc_cut1000 | gradient_boosted_trees        |    58 |        25 |          0.683827 |      1.14334  |
| fixed_adc_cut1000 | gradient_boosted_trees        |    59 |        11 |          1.30015  |      1.57727  |
| fixed_adc_cut1000 | gradient_boosted_trees        |    60 |        11 |          0.814179 |      0.979327 |
| fixed_adc_cut1000 | gradient_boosted_trees        |    61 |        18 |          1.65861  |      1.73307  |
| fixed_adc_cut1000 | gradient_boosted_trees        |    62 |         7 |          1.34114  |      2.5183   |
| fixed_adc_cut1000 | gradient_boosted_trees        |    63 |        28 |          0.580619 |      1.37284  |
| fixed_adc_cut1000 | gradient_boosted_trees        |    65 |        27 |          0.667516 |      0.99889  |
| fixed_adc_cut1000 | mlp                           |    58 |        25 |          0.432546 |      1.05476  |
| fixed_adc_cut1000 | mlp                           |    59 |        11 |          1.04522  |      1.28083  |
| fixed_adc_cut1000 | mlp                           |    60 |        11 |          0.516004 |      1.81135  |
| fixed_adc_cut1000 | mlp                           |    61 |        18 |          0.889423 |      1.00512  |
| fixed_adc_cut1000 | mlp                           |    62 |         7 |          0.878094 |      1.11759  |
| fixed_adc_cut1000 | mlp                           |    63 |        28 |          0.495099 |      0.624757 |
| fixed_adc_cut1000 | mlp                           |    65 |        27 |          0.580928 |      0.931286 |
| fixed_adc_cut1000 | cnn_1d                        |    58 |        25 |          1.04267  |      1.43184  |
| fixed_adc_cut1000 | cnn_1d                        |    59 |        11 |          1.22501  |      1.40541  |
| fixed_adc_cut1000 | cnn_1d                        |    60 |        11 |          1.02452  |      1.29006  |
| fixed_adc_cut1000 | cnn_1d                        |    61 |        18 |          1.8001   |      1.87484  |
| fixed_adc_cut1000 | cnn_1d                        |    62 |         7 |          2.07331  |      1.98731  |
| fixed_adc_cut1000 | cnn_1d                        |    63 |        28 |          1.41836  |      1.54112  |
| fixed_adc_cut1000 | cnn_1d                        |    65 |        27 |          1.44641  |      1.56543  |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    58 |        25 |          1.10422  |      1.53093  |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    59 |        11 |          1.68367  |      1.8908   |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    60 |        11 |          0.849763 |      1.49016  |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    61 |        18 |          1.93196  |      1.92748  |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    62 |         7 |          2.48369  |      2.50828  |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    63 |        28 |          1.37927  |      1.68583  |
| fixed_adc_cut1000 | gated_residual_cnn_new        |    65 |        27 |          1.65383  |      1.79106  |
| fixed_efficiency  | constrained_monotone_timewalk |    58 |       214 |         34.1825   |     40.2386   |
| fixed_efficiency  | constrained_monotone_timewalk |    59 |       262 |         39.2247   |     40.4791   |
| fixed_efficiency  | constrained_monotone_timewalk |    60 |       222 |         38.3383   |     42.1904   |
| fixed_efficiency  | constrained_monotone_timewalk |    61 |       225 |         43.766    |     43.8988   |
| fixed_efficiency  | constrained_monotone_timewalk |    62 |       232 |         45.3764   |     43.645    |
| fixed_efficiency  | constrained_monotone_timewalk |    63 |       234 |         32.2223   |     35.6926   |
| fixed_efficiency  | constrained_monotone_timewalk |    65 |       238 |         33.6134   |     41.599    |
| fixed_efficiency  | ridge                         |    58 |       214 |         15.3197   |     22.6507   |
| fixed_efficiency  | ridge                         |    59 |       262 |         18.0305   |     21.3093   |
| fixed_efficiency  | ridge                         |    60 |       222 |         17.57     |     22.6561   |
| fixed_efficiency  | ridge                         |    61 |       225 |         19.4791   |     23.8864   |
| fixed_efficiency  | ridge                         |    62 |       232 |         18.731    |     22.8359   |
| fixed_efficiency  | ridge                         |    63 |       234 |         14.8383   |     18.4309   |
| fixed_efficiency  | ridge                         |    65 |       238 |         15.9793   |     20.5508   |
| fixed_efficiency  | gradient_boosted_trees        |    58 |       214 |         11.2078   |     17.1851   |
| fixed_efficiency  | gradient_boosted_trees        |    59 |       262 |         10.1703   |     14.1329   |
| fixed_efficiency  | gradient_boosted_trees        |    60 |       222 |         11.1943   |     15.1857   |
| fixed_efficiency  | gradient_boosted_trees        |    61 |       225 |         11.0492   |     19.4718   |
| fixed_efficiency  | gradient_boosted_trees        |    62 |       232 |         11.3439   |     16.3215   |
| fixed_efficiency  | gradient_boosted_trees        |    63 |       234 |          9.87931  |     15.5544   |
| fixed_efficiency  | gradient_boosted_trees        |    65 |       238 |          9.47398  |     16.5161   |
| fixed_efficiency  | mlp                           |    58 |       214 |         10.2982   |     15.9932   |
| fixed_efficiency  | mlp                           |    59 |       262 |         13.9596   |     16.5779   |
| fixed_efficiency  | mlp                           |    60 |       222 |         14.5716   |     15.842    |
| fixed_efficiency  | mlp                           |    61 |       225 |         13.7277   |     17.3538   |
| fixed_efficiency  | mlp                           |    62 |       232 |         14.4697   |     17.6686   |
| fixed_efficiency  | mlp                           |    63 |       234 |         10.0327   |     15.3105   |
| fixed_efficiency  | mlp                           |    65 |       238 |          9.02682  |     14.2908   |
| fixed_efficiency  | cnn_1d                        |    58 |       214 |         29.9431   |     35.516    |
| fixed_efficiency  | cnn_1d                        |    59 |       262 |         34.2555   |     35.7437   |
| fixed_efficiency  | cnn_1d                        |    60 |       222 |         33.333    |     37.0881   |
| fixed_efficiency  | cnn_1d                        |    61 |       225 |         38.3818   |     39.167    |
| fixed_efficiency  | cnn_1d                        |    62 |       232 |         38.7343   |     38.1807   |
| fixed_efficiency  | cnn_1d                        |    63 |       234 |         29.1552   |     31.7147   |
| fixed_efficiency  | cnn_1d                        |    65 |       238 |         29.4239   |     36.7288   |
| fixed_efficiency  | gated_residual_cnn_new        |    58 |       214 |         17.2044   |     25.8268   |
| fixed_efficiency  | gated_residual_cnn_new        |    59 |       262 |         22.3735   |     26.7765   |
| fixed_efficiency  | gated_residual_cnn_new        |    60 |       222 |         23.6817   |     26.5785   |
| fixed_efficiency  | gated_residual_cnn_new        |    61 |       225 |         26.0104   |     29.9204   |
| fixed_efficiency  | gated_residual_cnn_new        |    62 |       232 |         21.5706   |     25.8711   |
| fixed_efficiency  | gated_residual_cnn_new        |    63 |       234 |         18.8497   |     23.9606   |
| fixed_efficiency  | gated_residual_cnn_new        |    65 |       238 |         17.9716   |     24.9552   |

## Bootstrap Deltas

Each delta is `W68(method) - W68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

| pool              | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|:------------------|:-----------------------------------------------------------|------------:|-------------:|----------:|
| fixed_adc_cut1000 | ridge_minus_constrained_monotone_timewalk                  |  -0.319262  |     1.02979  |  0.88     |
| fixed_adc_cut1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.84305   |    -0.103423 |  0.02     |
| fixed_adc_cut1000 | mlp_minus_constrained_monotone_timewalk                    |  -1.06675   |    -0.429497 |  0        |
| fixed_adc_cut1000 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.138292  |     0.506038 |  0.62     |
| fixed_adc_cut1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.0392262 |     0.491212 |  0.113333 |
| fixed_efficiency  | ridge_minus_constrained_monotone_timewalk                  | -23.9894    |   -19.2198   |  0        |
| fixed_efficiency  | gradient_boosted_trees_minus_constrained_monotone_timewalk | -31.3229    |   -24.4512   |  0        |
| fixed_efficiency  | mlp_minus_constrained_monotone_timewalk                    | -28.5077    |   -23.0362   |  0        |
| fixed_efficiency  | cnn_1d_minus_constrained_monotone_timewalk                 |  -6.04018   |    -3.74173  |  0        |
| fixed_efficiency  | gated_residual_cnn_new_minus_constrained_monotone_timewalk | -19.6705    |   -14.3315   |  0        |

## Systematics and Caveats

| check                       | value               | flag   |
|:----------------------------|:--------------------|:-------|
| forbidden_feature_overlap   |                     | False  |
| group_split_r2_mean         | -0.3608980946720293 | False  |
| row_split_advantage_rmse_ns | -1.8087920584416466 | False  |

- The fixed-efficiency threshold uses positive-amplitude A1/A3 support from the same run, but it does not use `y_i`, model residuals, event number, or run ID as model features.
- Pair counts remain small in Sample IV; therefore run-bootstrap CIs are wide and are more relevant than row-bootstrap precision.
- Fixed efficiency controls low-amplitude support, not particle identity, A-stack geometry, or unmeasured upstream conditions.
- CFD20 is held fixed. If the residual drift persists after support normalization, the likely remaining terms are interpolation noise, pulse-shape mismatch, and sparse-run composition.
- Gaussian-core sigma is reported as a diagnostic only; the winner is selected by percentile68 because the residuals are tail-sensitive and low-count.

## Conclusion

The standard raw ROOT S18 number is reproduced, and the fixed-efficiency decomposition shows that the A-stack drift is strongly entangled with amplitude support. The named winner in `result.json` is **gradient_boosted_trees** for the fixed-efficiency gate. Because fixed-efficiency gating materially changes the raw percentile68 while changing only run-local amplitude support, the residual method ranking should be interpreted as conditional on comparable retained-event fractions rather than as evidence for a globally superior ADC cut.

## Artifacts

`result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `fixed_efficiency_thresholds.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, and `leakage_checks.csv` are in this report directory.

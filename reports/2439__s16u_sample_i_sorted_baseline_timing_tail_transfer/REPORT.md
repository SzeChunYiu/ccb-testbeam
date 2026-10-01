# S16u: Sample-I Transfer of Sorted-Baseline Timing-Tail Nuisance

## Abstract

Ticket `#2439` asks for the sorted-baseline residual timing-tail nuisance test on Sample-I runs with the same S02/S04 controls used in S16t, plus a comparison of proxy coefficient signs across Sample-I and Sample-II. Raw ROOT selected-pulse counts reproduce exactly, then downstream S02 CFD20 pair residuals are refit in leave-one-run-out Sample-I folds. The named winner in `result.json` is **gradient_boosted_trees_controls_only**. The direct transfer audit is the sign agreement table between standardized Sample-I and Sample-II ridge coefficients on sorted-baseline proxy features.

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv` from `/home/billy/ccb-data/data/extracted/root/root`, applies the B-stack stave map, four-sample median pedestal, and the `> 1000` ADC selected-pulse threshold. Sorted ROOT files are used only after this gate to compute nuisance covariates. The Sample-I analysis subset is runs `[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]`.

| quantity                          |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses     |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis B2              |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4              |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6              |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8              |           1299 |         1299 |       0 |           0 | True   |
| sample_i_analysis selected_pulses |         252266 |       252266 |       0 |           0 | True   |

## Estimand and Equations

For downstream pair `(a,b)` in event `i`,

`r_i = (t_i,a^CFD20 - t_i,b^CFD20) - (x_a - x_b) tau`,

where `tau = 0.078` ns/cm and CFD20 uses the original raw four-sample median baseline. A correction model estimates `c_i = E[r_i | z_i]`; the scored residual is `r_i - c_i`. The robust width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The sorted-baseline residual proxy for pulse `p` is

`u_p = b_p^sorted - median(x_p,0:3)`.

Pair-level nuisance features use `max(|u_a|, |u_b|)`, `0.5(|u_a| + |u_b|)`, and `u_a - u_b`, plus sorted trapezoid sidebands. The control-only ablation removes all sorted/proxy terms while keeping pair identity, amplitudes, amplitude ratio/sum, peak samples, and raw pretrigger dispersion.

## Methods

The traditional comparator is a run-excluded hierarchical binned median correction over pair identity, amplitude-ratio bin, raw pretrigger-dispersion bin, and sorted-proxy magnitude bin, with fallbacks to coarser cells. ML/NN methods are ridge, histogram gradient-boosted trees, MLP, a 1D pair CNN over raw waveform pairs, and the new nuisance-gated pair CNN. Additional ridge and boosted-tree ablations are trained twice: controls only and controls plus sorted proxy. Model training and standardization are refit inside each leave-one-run-out fold.

Bootstrap intervals resample held-out Sample-I runs with replacement and preserve paired method predictions within each sampled run. For coefficient-transfer signs, a standardized ridge model is fit once on Sample-I pair rows and once on the Sample-II S16t companion rows using only sorted-proxy features; the sign comparison is diagnostic and not used to select the winner.

## Proxy Distribution

| quantity                                           |      value |
|:---------------------------------------------------|-----------:|
| selected Sample-I pulses with sorted proxy         | 252266     |
| median abs sorted-baseline residual ADC            |      8     |
| p90 abs sorted-baseline residual ADC               |     65     |
| mean signed sorted-baseline residual ADC           |   -305.837 |
| timing pairs                                       |   3430     |
| Sample-II companion timing pairs for sign transfer |  18098     |

## Primary Results

| method                                   |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |   tail_abs_gt_0p5_ns_ci_low |   tail_abs_gt_0p5_ns_ci_high |     bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |
|:-----------------------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|----------------------------:|-----------------------------:|------------:|-----------------:|------------------:|
| gradient_boosted_trees_controls_only     |      3430 |      1.45424 |             1.38677 |              1.51406 |             0.725073 |                    0.715819 |                     0.734796 | -0.00796019 |        -0.296004 |         0.273137  |
| gradient_boosted_trees                   |      3430 |      1.46745 |             1.42277 |              1.53018 |             0.723032 |                    0.702255 |                     0.74067  | -0.0199686  |        -0.300586 |         0.286144  |
| gradient_boosted_trees_plus_sorted_proxy |      3430 |      1.46745 |             1.42277 |              1.53018 |             0.723032 |                    0.702255 |                     0.74067  | -0.0199686  |        -0.300586 |         0.286144  |
| mlp                                      |      3430 |      1.5673  |             1.46633 |              1.68948 |             0.74519  |                    0.720203 |                     0.768563 |  0.0258437  |        -0.312514 |         0.332228  |
| traditional_binned_median                |      3430 |      1.56837 |             1.53164 |              1.61546 |             0.752478 |                    0.740602 |                     0.763463 | -0.347447   |        -0.668409 |        -0.0349088 |
| one_dimensional_cnn                      |      3430 |      1.68592 |             1.61392 |              1.75811 |             0.760641 |                    0.750233 |                     0.774158 | -0.165392   |        -0.518359 |         0.199748  |
| nuisance_gated_pair_cnn                  |      3430 |      1.76616 |             1.69729 |              1.82641 |             0.767638 |                    0.752768 |                     0.780713 | -0.226802   |        -0.548418 |         0.0779252 |
| ridge_controls_only                      |      3430 |      2.11462 |             2.03938 |              2.16483 |             0.815743 |                    0.800729 |                     0.82914  |  0.0061235  |        -0.325811 |         0.291123  |
| ridge                                    |      3430 |      2.14255 |             2.04356 |              2.2423  |             0.801458 |                    0.785387 |                     0.814694 | -0.00968408 |        -0.350645 |         0.275396  |
| ridge_plus_sorted_proxy                  |      3430 |      2.14255 |             2.04356 |              2.2423  |             0.801458 |                    0.785387 |                     0.814694 | -0.00968408 |        -0.350645 |         0.275396  |
| uncorrected                              |      3430 |      2.83781 |             2.7564  |              2.93297 |             0.929738 |                    0.920963 |                     0.938875 | -3.57508    |        -3.89918  |        -3.27422   |

## Paired Ablations

Negative deltas mean the sorted-proxy or gated method improved the robust residual width relative to its paired baseline.

| augmented_method                         | baseline_method                      |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |
|:-----------------------------------------|:-------------------------------------|-------------------:|--------------------------:|---------------------------:|
| ridge_plus_sorted_proxy                  | ridge_controls_only                  |          0.0279322 |               -0.0568283  |                  0.122886  |
| gradient_boosted_trees_plus_sorted_proxy | gradient_boosted_trees_controls_only |          0.0132046 |               -0.0410736  |                  0.0662451 |
| traditional_binned_median                | uncorrected                          |         -1.26944   |               -1.33969    |                 -1.19757   |
| nuisance_gated_pair_cnn                  | one_dimensional_cnn                  |          0.0802388 |               -0.00355222 |                  0.131629  |

## Sample-I/Sample-II Coefficient Sign Transfer

The table compares standardized ridge coefficients for sorted-baseline proxy features only. A transferred sign supports a period-stable recoverability diagnostic; a sign flip suggests the proxy is more period-local or confounded with period-specific timing structure.

| feature                            |   standardized_ridge_coef_ns_Sample-I | sign_Sample-I   |   standardized_ridge_coef_ns_Sample-II | sign_Sample-II   | sign_transfers   |
|:-----------------------------------|--------------------------------------:|:----------------|---------------------------------------:|:-----------------|:-----------------|
| nuisance_abs_max_adc               |                             -5.15314  | negative        |                              -6.5968   | negative         | True             |
| nuisance_abs_mean_adc              |                              1.21306  | positive        |                               1.54665  | positive         | True             |
| nuisance_signed_diff_adc           |                              0.562109 | positive        |                               0.987616 | positive         | True             |
| sorted_baseline_abs_residual_adc_a |                              0.940793 | positive        |                               1.14522  | positive         | True             |
| sorted_baseline_abs_residual_adc_b |                              1.38159  | positive        |                               1.75739  | positive         | True             |
| sorted_baseline_residual_adc_a     |                             -0.940793 | negative        |                              -1.14522  | negative         | True             |
| sorted_baseline_residual_adc_b     |                             -1.38159  | negative        |                              -1.75739  | negative         | True             |

## Run-Held-Out Stability

| method                                   |   run |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |    bias_ns |
|:-----------------------------------------|------:|----------:|-------------:|---------------------:|-----------:|
| gradient_boosted_trees                   |    44 |        45 |     1.66803  |             0.8      |  0.621093  |
| gradient_boosted_trees                   |    45 |       494 |     1.45692  |             0.734818 | -0.0418521 |
| gradient_boosted_trees                   |    46 |         3 |     0.982129 |             1        | -0.887846  |
| gradient_boosted_trees                   |    47 |        44 |     1.08684  |             0.681818 | -0.0583331 |
| gradient_boosted_trees                   |    48 |       306 |     1.35963  |             0.666667 |  0.382266  |
| gradient_boosted_trees                   |    49 |       322 |     1.39658  |             0.708075 | -0.0150525 |
| gradient_boosted_trees                   |    50 |       335 |     1.52021  |             0.713433 |  0.455193  |
| gradient_boosted_trees                   |    51 |       174 |     1.44788  |             0.666667 | -1.4616    |
| gradient_boosted_trees                   |    52 |        95 |     1.36598  |             0.747368 |  1.20127   |
| gradient_boosted_trees                   |    53 |       307 |     1.50989  |             0.71987  | -0.166159  |
| gradient_boosted_trees                   |    54 |       281 |     1.49854  |             0.747331 | -0.40952   |
| gradient_boosted_trees                   |    55 |       217 |     1.3259   |             0.714286 |  0.626915  |
| gradient_boosted_trees                   |    56 |       460 |     1.44148  |             0.726087 | -0.683324  |
| gradient_boosted_trees                   |    57 |       347 |     1.67401  |             0.778098 |  0.430602  |
| gradient_boosted_trees_controls_only     |    44 |        45 |     1.53863  |             0.666667 |  0.696914  |
| gradient_boosted_trees_controls_only     |    45 |       494 |     1.55494  |             0.730769 |  0.166901  |
| gradient_boosted_trees_controls_only     |    46 |         3 |     0.129384 |             0.666667 |  0.580487  |
| gradient_boosted_trees_controls_only     |    47 |        44 |     1.00876  |             0.659091 |  0.435925  |
| gradient_boosted_trees_controls_only     |    48 |       306 |     1.25399  |             0.705882 |  0.162543  |
| gradient_boosted_trees_controls_only     |    49 |       322 |     1.44656  |             0.723602 | -0.0867152 |
| gradient_boosted_trees_controls_only     |    50 |       335 |     1.49109  |             0.704478 |  0.544027  |
| gradient_boosted_trees_controls_only     |    51 |       174 |     1.45069  |             0.758621 | -1.55309   |
| gradient_boosted_trees_controls_only     |    52 |        95 |     1.39157  |             0.778947 |  0.776073  |
| gradient_boosted_trees_controls_only     |    53 |       307 |     1.51598  |             0.723127 |  0.0426817 |
| gradient_boosted_trees_controls_only     |    54 |       281 |     1.55608  |             0.725979 | -0.34541   |
| gradient_boosted_trees_controls_only     |    55 |       217 |     1.42032  |             0.732719 |  0.485694  |
| gradient_boosted_trees_controls_only     |    56 |       460 |     1.3399   |             0.715217 | -0.675098  |
| gradient_boosted_trees_controls_only     |    57 |       347 |     1.61559  |             0.74928  |  0.344429  |
| gradient_boosted_trees_plus_sorted_proxy |    44 |        45 |     1.66803  |             0.8      |  0.621093  |
| gradient_boosted_trees_plus_sorted_proxy |    45 |       494 |     1.45692  |             0.734818 | -0.0418521 |
| gradient_boosted_trees_plus_sorted_proxy |    46 |         3 |     0.982129 |             1        | -0.887846  |
| gradient_boosted_trees_plus_sorted_proxy |    47 |        44 |     1.08684  |             0.681818 | -0.0583331 |
| gradient_boosted_trees_plus_sorted_proxy |    48 |       306 |     1.35963  |             0.666667 |  0.382266  |
| gradient_boosted_trees_plus_sorted_proxy |    49 |       322 |     1.39658  |             0.708075 | -0.0150525 |
| gradient_boosted_trees_plus_sorted_proxy |    50 |       335 |     1.52021  |             0.713433 |  0.455193  |
| gradient_boosted_trees_plus_sorted_proxy |    51 |       174 |     1.44788  |             0.666667 | -1.4616    |
| gradient_boosted_trees_plus_sorted_proxy |    52 |        95 |     1.36598  |             0.747368 |  1.20127   |
| gradient_boosted_trees_plus_sorted_proxy |    53 |       307 |     1.50989  |             0.71987  | -0.166159  |
| gradient_boosted_trees_plus_sorted_proxy |    54 |       281 |     1.49854  |             0.747331 | -0.40952   |
| gradient_boosted_trees_plus_sorted_proxy |    55 |       217 |     1.3259   |             0.714286 |  0.626915  |
| gradient_boosted_trees_plus_sorted_proxy |    56 |       460 |     1.44148  |             0.726087 | -0.683324  |
| gradient_boosted_trees_plus_sorted_proxy |    57 |       347 |     1.67401  |             0.778098 |  0.430602  |
| mlp                                      |    44 |        45 |     1.73731  |             0.822222 | -0.222571  |
| mlp                                      |    45 |       494 |     1.4293   |             0.674089 |  0.232432  |
| mlp                                      |    46 |         3 |     1.7707   |             1        | -1.47111   |
| mlp                                      |    47 |        44 |     1.40314  |             0.795455 | -0.18385   |
| mlp                                      |    48 |       306 |     1.54787  |             0.751634 |  0.150091  |
| mlp                                      |    49 |       322 |     1.33931  |             0.71118  | -0.0149782 |
| mlp                                      |    50 |       335 |     1.39986  |             0.734328 |  1.0777    |
| mlp                                      |    51 |       174 |     1.62427  |             0.775862 | -1.59844   |
| mlp                                      |    52 |        95 |     1.35836  |             0.736842 |  0.395334  |
| mlp                                      |    53 |       307 |     1.70195  |             0.778502 |  0.350315  |
| mlp                                      |    54 |       281 |     1.93596  |             0.807829 | -0.443949  |
| mlp                                      |    55 |       217 |     1.53224  |             0.718894 |  0.233718  |
| mlp                                      |    56 |       460 |     1.46271  |             0.741304 | -0.568286  |
| mlp                                      |    57 |       347 |     1.82766  |             0.792507 |  0.180626  |
| nuisance_gated_pair_cnn                  |    44 |        45 |     2.12931  |             0.755556 | -0.308308  |
| nuisance_gated_pair_cnn                  |    45 |       494 |     1.74912  |             0.730769 | -0.408081  |
| nuisance_gated_pair_cnn                  |    46 |         3 |     1.8792   |             1        | -1.16968   |
| nuisance_gated_pair_cnn                  |    47 |        44 |     1.5238   |             0.75     | -0.130956  |
| nuisance_gated_pair_cnn                  |    48 |       306 |     1.71371  |             0.745098 |  0.104127  |
| nuisance_gated_pair_cnn                  |    49 |       322 |     1.65164  |             0.770186 | -0.31489   |
| nuisance_gated_pair_cnn                  |    50 |       335 |     1.67293  |             0.749254 |  0.287966  |
| nuisance_gated_pair_cnn                  |    51 |       174 |     2.00143  |             0.787356 | -1.85587   |
| nuisance_gated_pair_cnn                  |    52 |        95 |     1.57066  |             0.747368 |  1.04177   |
| nuisance_gated_pair_cnn                  |    53 |       307 |     1.80793  |             0.80456  |  0.278574  |
| nuisance_gated_pair_cnn                  |    54 |       281 |     1.87259  |             0.782918 | -0.220274  |
| nuisance_gated_pair_cnn                  |    55 |       217 |     1.64081  |             0.760369 |  0.215728  |
| nuisance_gated_pair_cnn                  |    56 |       460 |     1.59067  |             0.78913  | -0.875314  |
| nuisance_gated_pair_cnn                  |    57 |       347 |     1.76256  |             0.783862 | -0.0690832 |
| one_dimensional_cnn                      |    44 |        45 |     1.94148  |             0.822222 | -0.353893  |
| one_dimensional_cnn                      |    45 |       494 |     1.6663   |             0.738866 | -0.162084  |
| one_dimensional_cnn                      |    46 |         3 |     2.21005  |             1        | -1.34901   |
| one_dimensional_cnn                      |    47 |        44 |     1.47473  |             0.772727 | -0.0920457 |
| one_dimensional_cnn                      |    48 |       306 |     1.40184  |             0.77451  |  0.296334  |
| one_dimensional_cnn                      |    49 |       322 |     1.84021  |             0.754658 | -0.33183   |
| one_dimensional_cnn                      |    50 |       335 |     1.65292  |             0.770149 |  0.437729  |
| one_dimensional_cnn                      |    51 |       174 |     1.74094  |             0.810345 | -1.89134   |
| one_dimensional_cnn                      |    52 |        95 |     1.72192  |             0.778947 |  1.31306   |
| one_dimensional_cnn                      |    53 |       307 |     1.71135  |             0.76873  |  0.0254911 |
| one_dimensional_cnn                      |    54 |       281 |     1.71717  |             0.725979 | -0.58244   |
| one_dimensional_cnn                      |    55 |       217 |     1.67725  |             0.792627 |  0.580525  |
| one_dimensional_cnn                      |    56 |       460 |     1.60766  |             0.743478 | -1.01698   |
| one_dimensional_cnn                      |    57 |       347 |     1.78418  |             0.757925 |  0.31228   |
| ridge                                    |    44 |        45 |     2.32261  |             0.777778 | -0.426326  |
| ridge                                    |    45 |       494 |     2.27318  |             0.797571 |  0.14907   |
| ridge                                    |    46 |         3 |     0.913343 |             0.666667 | -2.10626   |
| ridge                                    |    47 |        44 |     1.64826  |             0.75     |  0.184103  |
| ridge                                    |    48 |       306 |     1.88687  |             0.816993 | -0.0858774 |
| ridge                                    |    49 |       322 |     2.065    |             0.779503 | -0.345909  |
| ridge                                    |    50 |       335 |     1.7881   |             0.802985 |  0.68459   |
| ridge                                    |    51 |       174 |     2.56552  |             0.862069 | -1.56065   |
| ridge                                    |    52 |        95 |     2.00647  |             0.736842 |  0.626596  |
| ridge                                    |    53 |       307 |     2.08829  |             0.76873  |  0.293617  |
| ridge                                    |    54 |       281 |     2.19423  |             0.829181 | -0.14404   |
| ridge                                    |    55 |       217 |     2.0993   |             0.746544 |  0.692587  |
| ridge                                    |    56 |       460 |     2.21731  |             0.826087 | -0.621147  |
| ridge                                    |    57 |       347 |     2.15429  |             0.818444 |  0.336216  |
| ridge_controls_only                      |    44 |        45 |     2.09063  |             0.888889 | -0.309828  |
| ridge_controls_only                      |    45 |       494 |     2.20559  |             0.819838 |  0.150031  |
| ridge_controls_only                      |    46 |         3 |     1.22212  |             0.666667 | -1.70922   |
| ridge_controls_only                      |    47 |        44 |     2.07419  |             0.931818 | -0.0172334 |
| ridge_controls_only                      |    48 |       306 |     2.13724  |             0.797386 |  0.179954  |
| ridge_controls_only                      |    49 |       322 |     2.16408  |             0.813665 | -0.0606296 |
| ridge_controls_only                      |    50 |       335 |     1.93438  |             0.776119 |  0.51295   |
| ridge_controls_only                      |    51 |       174 |     2.05577  |             0.816092 | -1.79675   |
| ridge_controls_only                      |    52 |        95 |     1.8981   |             0.757895 |  0.713574  |
| ridge_controls_only                      |    53 |       307 |     2.16033  |             0.807818 |  0.229984  |
| ridge_controls_only                      |    54 |       281 |     2.03253  |             0.843416 | -0.19114   |
| ridge_controls_only                      |    55 |       217 |     2.03822  |             0.778802 |  0.978526  |
| ridge_controls_only                      |    56 |       460 |     2.04865  |             0.841304 | -0.740543  |
| ridge_controls_only                      |    57 |       347 |     2.03427  |             0.832853 |  0.333128  |
| ridge_plus_sorted_proxy                  |    44 |        45 |     2.32261  |             0.777778 | -0.426326  |
| ridge_plus_sorted_proxy                  |    45 |       494 |     2.27318  |             0.797571 |  0.14907   |
| ridge_plus_sorted_proxy                  |    46 |         3 |     0.913343 |             0.666667 | -2.10626   |
| ridge_plus_sorted_proxy                  |    47 |        44 |     1.64826  |             0.75     |  0.184103  |
| ridge_plus_sorted_proxy                  |    48 |       306 |     1.88687  |             0.816993 | -0.0858774 |
| ridge_plus_sorted_proxy                  |    49 |       322 |     2.065    |             0.779503 | -0.345909  |
| ridge_plus_sorted_proxy                  |    50 |       335 |     1.7881   |             0.802985 |  0.68459   |
| ridge_plus_sorted_proxy                  |    51 |       174 |     2.56552  |             0.862069 | -1.56065   |
| ridge_plus_sorted_proxy                  |    52 |        95 |     2.00647  |             0.736842 |  0.626596  |
| ridge_plus_sorted_proxy                  |    53 |       307 |     2.08829  |             0.76873  |  0.293617  |
| ridge_plus_sorted_proxy                  |    54 |       281 |     2.19423  |             0.829181 | -0.14404   |
| ridge_plus_sorted_proxy                  |    55 |       217 |     2.0993   |             0.746544 |  0.692587  |
| ridge_plus_sorted_proxy                  |    56 |       460 |     2.21731  |             0.826087 | -0.621147  |
| ridge_plus_sorted_proxy                  |    57 |       347 |     2.15429  |             0.818444 |  0.336216  |
| traditional_binned_median                |    44 |        45 |     2.29948  |             0.755556 | -0.369309  |
| traditional_binned_median                |    45 |       494 |     1.6106   |             0.759109 | -0.186048  |
| traditional_binned_median                |    46 |         3 |     1.22719  |             1        | -1.16828   |
| traditional_binned_median                |    47 |        44 |     1.17487  |             0.727273 |  0.0381642 |
| traditional_binned_median                |    48 |       306 |     1.47906  |             0.738562 | -0.0242188 |
| traditional_binned_median                |    49 |       322 |     1.48782  |             0.745342 | -0.544923  |
| traditional_binned_median                |    50 |       335 |     1.58195  |             0.737313 | -0.153198  |
| traditional_binned_median                |    51 |       174 |     1.61881  |             0.741379 | -2.0708    |
| traditional_binned_median                |    52 |        95 |     1.75094  |             0.789474 |  1.94559   |
| traditional_binned_median                |    53 |       307 |     1.57655  |             0.745928 | -0.0807237 |
| traditional_binned_median                |    54 |       281 |     1.45703  |             0.786477 | -0.758694  |
| traditional_binned_median                |    55 |       217 |     1.60481  |             0.751152 |  0.319419  |
| traditional_binned_median                |    56 |       460 |     1.52846  |             0.728261 | -1.0607    |
| traditional_binned_median                |    57 |       347 |     1.57627  |             0.783862 | -0.0435677 |
| uncorrected                              |    44 |        45 |     3.27746  |             0.866667 | -3.70525   |
| uncorrected                              |    45 |       494 |     2.94064  |             0.917004 | -3.45879   |
| uncorrected                              |    46 |         3 |     2.65999  |             0.666667 | -4.86485   |
| uncorrected                              |    47 |        44 |     2.5728   |             0.909091 | -3.27046   |
| uncorrected                              |    48 |       306 |     2.77081  |             0.918301 | -3.129     |
| uncorrected                              |    49 |       322 |     2.61914  |             0.931677 | -3.75887   |
| uncorrected                              |    50 |       335 |     2.77875  |             0.931343 | -3.25099   |
| uncorrected                              |    51 |       174 |     3.11159  |             0.95977  | -5.3064    |
| uncorrected                              |    52 |        95 |     3.15536  |             0.894737 | -1.76642   |
| uncorrected                              |    53 |       307 |     2.79905  |             0.912052 | -3.26165   |
| uncorrected                              |    54 |       281 |     2.59401  |             0.935943 | -4.0171    |
| uncorrected                              |    55 |       217 |     3.06053  |             0.967742 | -2.93454   |
| uncorrected                              |    56 |       460 |     2.77743  |             0.932609 | -4.23353   |
| uncorrected                              |    57 |       347 |     2.66173  |             0.945245 | -3.36095   |

## Systematics and Caveats

The study is run-split, not event-split. No method receives run number, event identifiers, or peer residuals as features. The response is pairwise residual symmetry, not external time-of-flight truth. The sorted residual proxy uses raw pretrigger samples for diagnostic labeling, so it tests whether recoverability metadata predicts timing tails; it does not justify substituting sorted pedestals into CFD timing. Sample-I has more held-out run units than Sample-II but much lower downstream support in several runs, so the bootstrap is dominated by high-support runs 45, 50, 53, 54, and 56. The coefficient sign table is descriptive; it is not a causal proof because Sample-I and Sample-II differ in current state, penetration topology, and B2 dominance. The CNNs are intentionally compact and CPU reproducible, so they are capacity checks rather than exhaustive architecture searches.

## Conclusion

The decisive ticket question is whether the Sample-I proxy relation has the same sign structure as Sample-II and whether it improves timing residuals beyond amplitude and peak-time controls. The result table and `result.json` name `gradient_boosted_trees_controls_only` as the lowest-sigma68 Sample-I correction method, while the paired-ablation and coefficient-transfer tables quantify the incremental sorted-baseline information gain and its period stability.

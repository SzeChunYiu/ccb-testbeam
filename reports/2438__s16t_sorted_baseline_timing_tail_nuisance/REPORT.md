# S16t: Sorted-Baseline Residual Timing-Tail Nuisance

## Abstract

Ticket `#2438` asks whether the S16 sorted-baseline residual proxy explains S02/S04 timing tails beyond amplitude and peak-time controls. Raw ROOT selected-pulse counts reproduce exactly, then downstream S02 CFD20 pair residuals are refit in leave-one-run-out Sample-II folds. The named winner in `result.json` is **mlp**. The direct causal ablation is the paired bootstrap delta between control-only fits and fits augmented with the sorted-baseline recoverability proxy.

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv` from `/home/billy/ccb-data/data/extracted/root/root`, applies the B-stack stave map, four-sample median pedestal, and the `> 1000` ADC selected-pulse threshold. Sorted ROOT files are used only after this gate to compute nuisance covariates.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |

## Estimand and Equations

For downstream pair `(a,b)` in event `i`,

`r_i = (t_i,a^CFD20 - t_i,b^CFD20) - (x_a - x_b) tau`,

where `tau = 0.078` ns/cm and CFD20 uses the original raw four-sample median baseline. A correction model estimates `c_i = E[r_i | z_i]`; the scored residual is `r_i - c_i`. The robust width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The sorted-baseline residual proxy for pulse `p` is

`u_p = b_p^sorted - median(x_p,0:3)`.

Pair-level nuisance features use `max(|u_a|, |u_b|)`, `0.5(|u_a| + |u_b|)`, and `u_a - u_b`, plus sorted trapezoid sidebands. The control-only ablation removes all sorted/proxy terms while keeping pair identity, amplitudes, amplitude ratio/sum, peak samples, and raw pretrigger dispersion.

## Methods

The traditional comparator is a run-excluded hierarchical binned median correction over pair identity, amplitude-ratio bin, raw pretrigger-dispersion bin, and sorted-proxy magnitude bin, with fallbacks to coarser cells. ML/NN methods are ridge, histogram gradient-boosted trees, MLP, a 1D pair CNN over raw waveform pairs, and the new nuisance-gated pair CNN. Additional ridge and boosted-tree ablations are trained twice: controls only and controls plus sorted proxy.

Bootstrap intervals resample held-out runs with replacement and preserve paired method predictions within each sampled run.

## Proxy Distribution

| quantity                                    |      value |
|:--------------------------------------------|-----------:|
| selected Sample-II pulses with sorted proxy | 125096     |
| median abs sorted-baseline residual ADC     |      9.5   |
| p90 abs sorted-baseline residual ADC        |    568.25  |
| mean signed sorted-baseline residual ADC    |   -239.486 |
| timing pairs                                |  18098     |

## Primary Results

| method                                   |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |   tail_abs_gt_0p5_ns_ci_low |   tail_abs_gt_0p5_ns_ci_high |     bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |
|:-----------------------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|----------------------------:|-----------------------------:|------------:|-----------------:|------------------:|
| mlp                                      |     18098 |      1.13856 |             1.09167 |              1.18842 |             0.63554  |                    0.620327 |                     0.65674  |  0.00663444 |        -0.263255 |         0.273618  |
| gradient_boosted_trees                   |     18098 |      1.21155 |             1.1743  |              1.25101 |             0.667974 |                    0.653569 |                     0.684841 | -0.0276432  |        -0.117464 |         0.0883964 |
| gradient_boosted_trees_plus_sorted_proxy |     18098 |      1.21155 |             1.1743  |              1.25101 |             0.667974 |                    0.653569 |                     0.684841 | -0.0276432  |        -0.117464 |         0.0883964 |
| gradient_boosted_trees_controls_only     |     18098 |      1.22608 |             1.19231 |              1.26777 |             0.669521 |                    0.658743 |                     0.682038 | -0.0107802  |        -0.103597 |         0.115557  |
| nuisance_gated_pair_cnn                  |     18098 |      1.32913 |             1.30415 |              1.35717 |             0.692728 |                    0.686409 |                     0.700224 | -0.41209    |        -0.501362 |        -0.295596  |
| one_dimensional_cnn                      |     18098 |      1.336   |             1.31919 |              1.36571 |             0.698972 |                    0.691457 |                     0.707546 | -0.292571   |        -0.35388  |        -0.193998  |
| traditional_binned_median                |     18098 |      1.37693 |             1.34114 |              1.41168 |             0.714554 |                    0.698208 |                     0.726225 | -0.44507    |        -0.568471 |        -0.304012  |
| ridge_controls_only                      |     18098 |      2.38402 |             2.27314 |              2.50699 |             0.826279 |                    0.813088 |                     0.839428 | -0.0206157  |        -0.232775 |         0.269115  |
| ridge_plus_sorted_proxy                  |     18098 |      2.39388 |             2.29381 |              2.51603 |             0.823848 |                    0.814895 |                     0.833071 | -0.00766272 |        -0.237159 |         0.293854  |
| ridge                                    |     18098 |      2.39388 |             2.29381 |              2.51603 |             0.823848 |                    0.814895 |                     0.833071 | -0.00766272 |        -0.237159 |         0.293854  |
| uncorrected                              |     18098 |      2.94278 |             2.84853 |              3.04781 |             0.922643 |                    0.91729  |                     0.929879 | -3.41237    |        -3.5347   |        -3.30866   |

## Paired Ablations

Negative deltas mean the sorted-proxy or gated method improved the robust residual width relative to its paired baseline.

| augmented_method                         | baseline_method                      |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |
|:-----------------------------------------|:-------------------------------------|-------------------:|--------------------------:|---------------------------:|
| ridge_plus_sorted_proxy                  | ridge_controls_only                  |         0.00986801 |                -0.0604617 |                 0.0810687  |
| gradient_boosted_trees_plus_sorted_proxy | gradient_boosted_trees_controls_only |        -0.0145361  |                -0.0425757 |                 0.00442118 |
| traditional_binned_median                | uncorrected                          |        -1.56585    |                -1.66549   |                -1.4633     |
| nuisance_gated_pair_cnn                  | one_dimensional_cnn                  |        -0.0068704  |                -0.021396  |                 0.00511826 |

## Run-Held-Out Stability

| method                                   |   run |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |     bias_ns |
|:-----------------------------------------|------:|----------:|-------------:|---------------------:|------------:|
| gradient_boosted_trees                   |    58 |       353 |      1.45732 |             0.708215 |  1.28703    |
| gradient_boosted_trees                   |    59 |      3753 |      1.1481  |             0.642686 | -0.161332   |
| gradient_boosted_trees                   |    60 |      3700 |      1.17154 |             0.65027  | -0.00176078 |
| gradient_boosted_trees                   |    61 |      4245 |      1.15881 |             0.687397 |  0.0166767  |
| gradient_boosted_trees                   |    62 |      3833 |      1.21857 |             0.676494 |  0.0069416  |
| gradient_boosted_trees                   |    63 |      1816 |      1.22986 |             0.667952 | -0.27004    |
| gradient_boosted_trees                   |    65 |       398 |      1.48866 |             0.746231 |  0.126576   |
| gradient_boosted_trees_controls_only     |    58 |       353 |      1.55047 |             0.711048 |  1.42871    |
| gradient_boosted_trees_controls_only     |    59 |      3753 |      1.14715 |             0.64988  | -0.121177   |
| gradient_boosted_trees_controls_only     |    60 |      3700 |      1.2204  |             0.66973  | -0.00742854 |
| gradient_boosted_trees_controls_only     |    61 |      4245 |      1.20114 |             0.685041 |  0.0127905  |
| gradient_boosted_trees_controls_only     |    62 |      3833 |      1.21264 |             0.65797  |  0.0430102  |
| gradient_boosted_trees_controls_only     |    63 |      1816 |      1.24488 |             0.669604 | -0.283035   |
| gradient_boosted_trees_controls_only     |    65 |       398 |      1.50347 |             0.761307 |  0.195143   |
| gradient_boosted_trees_plus_sorted_proxy |    58 |       353 |      1.45732 |             0.708215 |  1.28703    |
| gradient_boosted_trees_plus_sorted_proxy |    59 |      3753 |      1.1481  |             0.642686 | -0.161332   |
| gradient_boosted_trees_plus_sorted_proxy |    60 |      3700 |      1.17154 |             0.65027  | -0.00176078 |
| gradient_boosted_trees_plus_sorted_proxy |    61 |      4245 |      1.15881 |             0.687397 |  0.0166767  |
| gradient_boosted_trees_plus_sorted_proxy |    62 |      3833 |      1.21857 |             0.676494 |  0.0069416  |
| gradient_boosted_trees_plus_sorted_proxy |    63 |      1816 |      1.22986 |             0.667952 | -0.27004    |
| gradient_boosted_trees_plus_sorted_proxy |    65 |       398 |      1.48866 |             0.746231 |  0.126576   |
| mlp                                      |    58 |       353 |      1.42947 |             0.688385 |  1.28039    |
| mlp                                      |    59 |      3753 |      1.11957 |             0.632827 |  0.172188   |
| mlp                                      |    60 |      3700 |      1.03202 |             0.601081 |  0.311769   |
| mlp                                      |    61 |      4245 |      1.12754 |             0.648292 | -0.459674   |
| mlp                                      |    62 |      3833 |      1.09945 |             0.628489 |  0.095795   |
| mlp                                      |    63 |      1816 |      1.16586 |             0.668502 | -0.233014   |
| mlp                                      |    65 |       398 |      1.42535 |             0.71608  | -0.31253    |
| nuisance_gated_pair_cnn                  |    58 |       353 |      1.3323  |             0.70255  |  0.441737   |
| nuisance_gated_pair_cnn                  |    59 |      3753 |      1.33873 |             0.70397  | -0.476015   |
| nuisance_gated_pair_cnn                  |    60 |      3700 |      1.27694 |             0.684595 | -0.596651   |
| nuisance_gated_pair_cnn                  |    61 |      4245 |      1.34848 |             0.689988 | -0.329749   |
| nuisance_gated_pair_cnn                  |    62 |      3833 |      1.31105 |             0.693191 | -0.322313   |
| nuisance_gated_pair_cnn                  |    63 |      1816 |      1.36046 |             0.676762 | -0.532978   |
| nuisance_gated_pair_cnn                  |    65 |       398 |      1.54296 |             0.751256 | -0.0420935  |
| one_dimensional_cnn                      |    58 |       353 |      1.36185 |             0.685552 |  0.678407   |
| one_dimensional_cnn                      |    59 |      3753 |      1.34879 |             0.691713 | -0.29447    |
| one_dimensional_cnn                      |    60 |      3700 |      1.30218 |             0.715946 | -0.372134   |
| one_dimensional_cnn                      |    61 |      4245 |      1.35446 |             0.697998 | -0.297536   |
| one_dimensional_cnn                      |    62 |      3833 |      1.31372 |             0.6958   | -0.250948   |
| one_dimensional_cnn                      |    63 |      1816 |      1.38169 |             0.685573 | -0.501528   |
| one_dimensional_cnn                      |    65 |       398 |      1.48467 |             0.723618 |  0.209318   |
| ridge                                    |    58 |       353 |      3.26775 |             0.88102  |  2.24594    |
| ridge                                    |    59 |      3753 |      2.17973 |             0.811617 | -0.126214   |
| ridge                                    |    60 |      3700 |      2.348   |             0.827297 |  0.251815   |
| ridge                                    |    61 |      4245 |      2.43617 |             0.836749 | -0.40989    |
| ridge                                    |    62 |      3833 |      2.41038 |             0.816332 |  0.17727    |
| ridge                                    |    63 |      1816 |      2.29247 |             0.806718 | -0.310532   |
| ridge                                    |    65 |       398 |      2.97865 |             0.869347 |  0.590205   |
| ridge_controls_only                      |    58 |       353 |      3.25825 |             0.88102  |  1.92425    |
| ridge_controls_only                      |    59 |      3753 |      2.15863 |             0.803357 | -0.0771177  |
| ridge_controls_only                      |    60 |      3700 |      2.44135 |             0.839189 |  0.137451   |
| ridge_controls_only                      |    61 |      4245 |      2.51461 |             0.840518 | -0.385042   |
| ridge_controls_only                      |    62 |      3833 |      2.29819 |             0.813984 |  0.189724   |
| ridge_controls_only                      |    63 |      1816 |      2.29905 |             0.823238 | -0.353424   |
| ridge_controls_only                      |    65 |       398 |      3.00789 |             0.854271 |  0.697484   |
| ridge_plus_sorted_proxy                  |    58 |       353 |      3.26775 |             0.88102  |  2.24594    |
| ridge_plus_sorted_proxy                  |    59 |      3753 |      2.17973 |             0.811617 | -0.126214   |
| ridge_plus_sorted_proxy                  |    60 |      3700 |      2.348   |             0.827297 |  0.251815   |
| ridge_plus_sorted_proxy                  |    61 |      4245 |      2.43617 |             0.836749 | -0.40989    |
| ridge_plus_sorted_proxy                  |    62 |      3833 |      2.41038 |             0.816332 |  0.17727    |
| ridge_plus_sorted_proxy                  |    63 |      1816 |      2.29247 |             0.806718 | -0.310532   |
| ridge_plus_sorted_proxy                  |    65 |       398 |      2.97865 |             0.869347 |  0.590205   |
| traditional_binned_median                |    58 |       353 |      1.38754 |             0.696884 |  0.197775   |
| traditional_binned_median                |    59 |      3753 |      1.31247 |             0.682121 | -0.518544   |
| traditional_binned_median                |    60 |      3700 |      1.33023 |             0.716486 | -0.608007   |
| traditional_binned_median                |    61 |      4245 |      1.36243 |             0.722733 | -0.22466    |
| traditional_binned_median                |    62 |      3833 |      1.36418 |             0.726585 | -0.423575   |
| traditional_binned_median                |    63 |      1816 |      1.44158 |             0.729626 | -0.71804    |
| traditional_binned_median                |    65 |       398 |      1.58763 |             0.746231 | -0.119993   |
| uncorrected                              |    58 |       353 |      2.8642  |             0.923513 | -2.85184    |
| uncorrected                              |    59 |      3753 |      2.95704 |             0.928324 | -3.47279    |
| uncorrected                              |    60 |      3700 |      2.96349 |             0.917027 | -3.51308    |
| uncorrected                              |    61 |      4245 |      2.7526  |             0.912603 | -3.26935    |
| uncorrected                              |    62 |      3833 |      3.00859 |             0.926689 | -3.32187    |
| uncorrected                              |    63 |      1816 |      3.18528 |             0.932269 | -3.71769    |
| uncorrected                              |    65 |       398 |      2.58048 |             0.944724 | -3.40749    |

## Systematics and Caveats

The study is run-split, not event-split. No method receives run number, event identifiers, or peer residuals as features. The response is pairwise residual symmetry, not external time-of-flight truth. The sorted residual proxy uses raw pretrigger samples for diagnostic labeling, so it tests whether recoverability metadata predicts timing tails; it does not justify substituting sorted pedestals into CFD timing. Bootstrap intervals have seven run units and should be read as run-transfer intervals. The CNNs are intentionally compact and CPU reproducible, so they are capacity checks rather than exhaustive architecture searches.

## Conclusion

The decisive ticket question is whether proxy-augmented corrections improve over amplitude and peak-time controls with paired run-bootstrap support. The result table and `result.json` name `mlp` as the lowest-sigma68 correction method, while the paired-ablation table quantifies the incremental sorted-baseline information gain.

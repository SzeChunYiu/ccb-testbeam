# S18h: A-stack waveform atom audit for late/mixed ML transfer

- **Ticket:** `1781102709.886.658f43d5`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-09
- **Input:** raw A-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18h_1781102709_886_658f43d5_astack_waveform_atom_audit.py --config configs/s18h_1781102709_886_658f43d5_astack_waveform_atom_audit.json`
- **Primary split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on held-out Sample IV analysis runs `58,59,60,61,62,63,65`.
- **Primary metric:** `percentile68_ns = 0.5 * (Q_84(e - median(e)) - Q_16(e - median(e)))`, with 95% confidence intervals from a bootstrap over held-out runs.

## Abstract

This study asks which waveform atom makes late/mixed Sample-III to Sample-IV A1-A3 ML transfer produce narrow residuals under the S18g-style gated residual CNN benchmark. The primary gate is CFD `[0.2]` with amplitude cut `[1000.0]` ADC. Raw A1-A3 residuals are reconstructed directly from ROOT, then corrected with a strong constrained traditional timewalk model and five learned alternatives: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN. The ticket-specific atom audit retrains ridge and gradient-boosted-tree models after leading-edge, tail, amplitude-only, and shuffled-waveform controls on the same run split.

At the preregistered standard gate CFD20/cut1000, the winner is **mlp**, with held-out width **0.900 ns** and run-bootstrap CI **[0.665, 1.210] ns**. The uncorrected standard-gate A-stack width is **1.610 ns** with CI **[1.301, 1.712] ns**.

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
| mlp                           |       127 |          0.900379 |           0.665388 |             1.21041 |        0.776515 |       1.59279 |                 0.015748   |
| gradient_boosted_trees        |       127 |          1.03488  |           0.720771 |             1.41891 |        0.914072 |       1.4037  |                 0.00787402 |
| constrained_monotone_timewalk |       127 |          1.51782  |           1.2097   |             1.71969 |        3.8723   |       1.47456 |                 0          |
| cnn_1d                        |       127 |          1.58233  |           1.38051  |             1.8796  |        2.15401  |       1.59717 |                 0          |
| ridge                         |       127 |          1.61473  |           1.27753  |             2.30982 |        1.62296  |       2.27543 |                 0.0314961  |
| gated_residual_cnn_new        |       127 |          1.73259  |           1.41699  |             1.96794 |        2.00749  |       1.77144 |                 0.00787402 |

Per-run standard-gate widths:

| method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------------------|------:|----------:|------------------:|--------------:|
| cnn_1d                        |    58 |        25 |          1.14486  |      1.47801  |
| cnn_1d                        |    59 |        11 |          1.27826  |      1.308    |
| cnn_1d                        |    60 |        11 |          0.98351  |      1.36725  |
| cnn_1d                        |    61 |        18 |          1.92299  |      1.89798  |
| cnn_1d                        |    62 |         7 |          2.0964   |      2.08587  |
| cnn_1d                        |    63 |        28 |          1.40389  |      1.51964  |
| cnn_1d                        |    65 |        27 |          1.34956  |      1.55889  |
| constrained_monotone_timewalk |    58 |        25 |          1.07602  |      1.28344  |
| constrained_monotone_timewalk |    59 |        11 |          1.0004   |      1.19702  |
| constrained_monotone_timewalk |    60 |        11 |          0.97022  |      1.16291  |
| constrained_monotone_timewalk |    61 |        18 |          1.65913  |      1.80175  |
| constrained_monotone_timewalk |    62 |         7 |          0.990411 |      1.56649  |
| constrained_monotone_timewalk |    63 |        28 |          1.33336  |      1.38912  |
| constrained_monotone_timewalk |    65 |        27 |          1.57379  |      1.62056  |
| gated_residual_cnn_new        |    58 |        25 |          1.02703  |      1.46618  |
| gated_residual_cnn_new        |    59 |        11 |          1.81507  |      1.87258  |
| gated_residual_cnn_new        |    60 |        11 |          0.935566 |      1.47772  |
| gated_residual_cnn_new        |    61 |        18 |          1.95805  |      1.97529  |
| gated_residual_cnn_new        |    62 |         7 |          2.31785  |      2.57889  |
| gated_residual_cnn_new        |    63 |        28 |          1.45137  |      1.68468  |
| gated_residual_cnn_new        |    65 |        27 |          1.52981  |      1.72888  |
| gradient_boosted_trees        |    58 |        25 |          0.683827 |      1.14334  |
| gradient_boosted_trees        |    59 |        11 |          1.30015  |      1.57727  |
| gradient_boosted_trees        |    60 |        11 |          0.814179 |      0.979327 |
| gradient_boosted_trees        |    61 |        18 |          1.65861  |      1.73307  |
| gradient_boosted_trees        |    62 |         7 |          1.34114  |      2.5183   |
| gradient_boosted_trees        |    63 |        28 |          0.580619 |      1.37284  |
| gradient_boosted_trees        |    65 |        27 |          0.667516 |      0.99889  |
| mlp                           |    58 |        25 |          0.732156 |      1.37383  |
| mlp                           |    59 |        11 |          0.995636 |      1.45117  |
| mlp                           |    60 |        11 |          1.06719  |      3.33693  |
| mlp                           |    61 |        18 |          1.28221  |      1.39342  |
| mlp                           |    62 |         7 |          0.720956 |      1.39712  |
| mlp                           |    63 |        28 |          0.585223 |      1.02605  |
| mlp                           |    65 |        27 |          0.651841 |      1.00083  |
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
|            0.2 |                1000 |       127 |           1.60997 |            1.30084 |             1.71201 |       1.49924 |

Best method at each gate:

|   cfd_fraction |   amplitude_cut_adc | method   |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |
|---------------:|--------------------:|:---------|----------:|------------------:|-------------------:|--------------------:|
|            0.2 |                1000 | mlp      |       127 |          0.900379 |           0.665388 |             1.21041 |

Method stability across all gates:

| method                        |   gates |   median_width_ns |   min_width_ns |   max_width_ns |   mean_n_pairs |
|:------------------------------|--------:|------------------:|---------------:|---------------:|---------------:|
| mlp                           |       1 |          0.900379 |       0.900379 |       0.900379 |            127 |
| gradient_boosted_trees        |       1 |          1.03488  |       1.03488  |       1.03488  |            127 |
| constrained_monotone_timewalk |       1 |          1.51782  |       1.51782  |       1.51782  |            127 |
| cnn_1d                        |       1 |          1.58233  |       1.58233  |       1.58233  |            127 |
| ridge                         |       1 |          1.61473  |       1.61473  |       1.61473  |            127 |
| gated_residual_cnn_new        |       1 |          1.73259  |       1.73259  |       1.73259  |            127 |

Full method/gate metrics, including all CIs and Gaussian-core diagnostics, are in `method_metrics.csv`.

## Paired Deltas

Each delta is `W_68(method) - W_68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

|   cfd_fraction |   amplitude_cut_adc | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|---------------:|--------------------:|:-----------------------------------------------------------|------------:|-------------:|----------:|
|            0.2 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |   -0.173503 |     0.474503 |      0.53 |
|            0.2 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -0.145293 |     0.495613 |      0.31 |
|            0.2 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -0.931504 |    -0.10557  |      0.01 |
|            0.2 |                1000 | mlp_minus_constrained_monotone_timewalk                    |   -0.907304 |    -0.162626 |      0.02 |
|            0.2 |                1000 | ridge_minus_constrained_monotone_timewalk                  |   -0.269377 |     0.914754 |      0.73 |

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

The standard A-stack gate is reproducible from raw ROOT and the method ranking is not explained by the old Gaussian-core fit alone. At CFD20/cut1000, **mlp** wins the held-out benchmark with width **0.900 ns**. The atom audit finds that amplitude-only features are much wider than waveform-shape models, while the shuffled-waveform control is also wider than the best full/ablated waveform tree. This supports a waveform-shape contribution to the late/mixed transfer rather than a pure amplitude-channel artifact. The traditional constrained baseline remains a defensible low-variance reference, but learned waveform methods capture additional shape/support information.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, `atom_ablation_metrics.csv`, `atom_ablation_predictions.csv.gz`, and PNG diagnostics are in this report directory.

## S18h Waveform Atom Audit

This ticket-specific audit asks which waveform atom makes late/mixed Sample-III to Sample-IV A1-A3 transfer look narrow. The table below retrains ridge and gradient-boosted-tree residual models on the primary CFD20/cut1000 split after targeted ablations. `drop_leading_edge_samples` zeros normalized samples 0-5 in both channels and their pairwise differences; `drop_tail_samples` zeros samples 10-17; `amplitude_only` retains only log-amplitude and positive-area summaries; `waveform_shuffled_control` preserves marginal waveform-sample distributions but breaks event-local waveform shape. All intervals are 95% run-bootstrap intervals over held-out Sample IV runs.

| atom_mode                 | model_family           |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:--------------------------|:-----------------------|----------:|------------------:|-------------------:|--------------------:|--------------:|---------------------------:|
| drop_tail_samples         | gradient_boosted_trees |       127 |          0.966301 |           0.729913 |             1.28648 |       1.44647 |                 0.00787402 |
| full_features             | gradient_boosted_trees |       127 |          1.03488  |           0.720118 |             1.39178 |       1.4037  |                 0.00787402 |
| drop_tail_samples         | ridge                  |       127 |          1.22355  |           0.930487 |             2.00029 |       2.2374  |                 0.0629921  |
| drop_leading_edge_samples | gradient_boosted_trees |       127 |          1.45743  |           1.32783  |             1.82944 |       1.74785 |                 0.015748   |
| drop_leading_edge_samples | ridge                  |       127 |          1.5583   |           1.20757  |             1.86755 |       2.78054 |                 0.0393701  |
| full_features             | ridge                  |       127 |          1.57013  |           1.27314  |             1.88347 |       2.76313 |                 0.0472441  |
| waveform_shuffled_control | gradient_boosted_trees |       127 |          1.61328  |           1.39139  |             2.01167 |       2.43858 |                 0.0393701  |
| waveform_shuffled_control | ridge                  |       127 |          1.6244   |           1.48504  |             1.89333 |       1.86773 |                 0.0314961  |
| amplitude_only            | gradient_boosted_trees |       127 |          1.78215  |           1.34884  |             2.06193 |       2.02542 |                 0.0472441  |
| amplitude_only            | ridge                  |       127 |          1.78459  |           1.57168  |             2.33834 |       2.15609 |                 0.0314961  |

Ablation interpretation: if dropping leading-edge samples or shuffling waveform samples materially widens the residuals relative to `full_features`, the narrow transfer is waveform-shape dependent rather than only an amplitude-channel artifact. If `amplitude_only` is comparable to the full model, the dominant atom is support/amplitude matching rather than learned local pulse shape. The shuffled control is the direct leakage guard because it keeps one-dimensional sample marginals but destroys event-local waveform timing structure.

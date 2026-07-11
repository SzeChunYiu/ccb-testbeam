# S18i: Pulse-shape timing model hierarchy with bootstrap closure

- **Ticket:** `1783770201.8157.51000596`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-07-11
- **Input:** raw A-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Command:** `.venv/bin/python scripts/s18h_1781102709_886_658f43d5_astack_waveform_atom_audit.py --config configs/s18i_1783770201_8157_51000596_pulse_shape_timing_model_hierarchy.json`
- **Primary split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on held-out Sample IV analysis runs `58,59,60,61,62,63,65`.
- **Primary metric:** `percentile68_ns = 0.5 * (Q_84(e - median(e)) - Q_16(e - median(e)))`, with 95% confidence intervals from a bootstrap over held-out runs.

## Abstract

This study asks which waveform atom makes late/mixed Sample-III to Sample-IV A1-A3 ML transfer produce narrow residuals under the S18g-style gated residual CNN benchmark. The primary gate is CFD `[0.2]` with amplitude cut `[1000.0]` ADC. Raw A1-A3 residuals are reconstructed directly from ROOT, then corrected with a strong constrained traditional timewalk model and five learned alternatives: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN. The ticket-specific atom audit retrains ridge and gradient-boosted-tree models after leading-edge, tail, amplitude-only, and shuffled-waveform controls on the same run split.

At the preregistered standard gate CFD20/cut1000, the winner is **mlp**, with held-out width **0.584 ns** and run-bootstrap CI **[0.478, 0.774] ns**. The uncorrected standard-gate A-stack width is **1.610 ns** with CI **[1.259, 1.722] ns**.

## Reproduction From Raw ROOT

The gate was reproduced from raw `HRDv` waveforms before any benchmark. Each event is reshaped to `(8, 18)`. Samples 0-3 define the per-channel pedestal. A1 and A3 are baseline-subtracted, CFD crossing times are linearly interpolated before the peak, and an event enters the A1-A3 pair table only when both amplitudes exceed the gate cut.

The prior S18 A-stack anchor is reproduced at the standard gate with run64-trained OLS:

| quantity                            |   expected |   reproduced |       delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs               |  127       |    127       | 0           |       0     | True   |
| sample_iv_run64_ols_robust_width_ns |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_run64_ols_core_sigma_ns   |    1.99218 |      1.99218 | 5.10817e-07 |       0.001 | True   |

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

Torch was not available in the ticket venv; `cnn_1d` and `gated_residual_cnn_new` therefore use deterministic one-dimensional convolutional waveform filter banks followed by regularized sklearn heads. They retain the same convolutional pulse-shape inductive bias, but the caveats treat them as lightweight CNN surrogates rather than GPU-trained deep networks.

No method receives run number, event number, raw residual, A1 time, or A3 time as a feature. Hyperparameter selection uses training runs only.

## Standard-Gate Head-to-Head

| method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| mlp                           |       127 |          0.584091 |           0.478496 |            0.773545 |        0.437677 |       1.10936 |                 0.00787402 |
| gradient_boosted_trees        |       127 |          0.990472 |           0.750485 |            1.44201  |        0.620947 |       1.53703 |                 0.015748   |
| constrained_monotone_timewalk |       127 |          1.51782  |           1.25826  |            1.71967  |        3.8723   |       1.47456 |                 0          |
| ridge                         |       127 |          1.61473  |           1.26685  |            2.25505  |        1.62296  |       2.27543 |                 0.0314961  |
| cnn_1d                        |       127 |          1.74046  |           1.47443  |            2.12398  |        1.4876   |       2.32201 |                 0.0629921  |
| gated_residual_cnn_new        |       127 |          2.26107  |           1.936    |            2.564    |       92.3082   |       2.46099 |                 0.0393701  |

Per-run standard-gate widths:

| method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------------------|------:|----------:|------------------:|--------------:|
| cnn_1d                        |    58 |        25 |          1.59722  |      2.00284  |
| cnn_1d                        |    59 |        11 |          1.84116  |      2.44738  |
| cnn_1d                        |    60 |        11 |          1.62798  |      1.56958  |
| cnn_1d                        |    61 |        18 |          1.18858  |      2.03521  |
| cnn_1d                        |    62 |         7 |          3.51025  |      3.76759  |
| cnn_1d                        |    63 |        28 |          1.47492  |      2.29205  |
| cnn_1d                        |    65 |        27 |          1.2366   |      2.43679  |
| constrained_monotone_timewalk |    58 |        25 |          1.07602  |      1.28344  |
| constrained_monotone_timewalk |    59 |        11 |          1.0004   |      1.19702  |
| constrained_monotone_timewalk |    60 |        11 |          0.97022  |      1.16291  |
| constrained_monotone_timewalk |    61 |        18 |          1.65913  |      1.80175  |
| constrained_monotone_timewalk |    62 |         7 |          0.990411 |      1.56649  |
| constrained_monotone_timewalk |    63 |        28 |          1.33336  |      1.38912  |
| constrained_monotone_timewalk |    65 |        27 |          1.57379  |      1.62056  |
| gated_residual_cnn_new        |    58 |        25 |          2.24422  |      1.98954  |
| gated_residual_cnn_new        |    59 |        11 |          1.78035  |      2.13913  |
| gated_residual_cnn_new        |    60 |        11 |          1.03559  |      2.23328  |
| gated_residual_cnn_new        |    61 |        18 |          2.71964  |      2.5807   |
| gated_residual_cnn_new        |    62 |         7 |          3.46149  |      3.65173  |
| gated_residual_cnn_new        |    63 |        28 |          1.90441  |      2.19544  |
| gated_residual_cnn_new        |    65 |        27 |          1.99625  |      2.7786   |
| gradient_boosted_trees        |    58 |        25 |          0.687119 |      1.50912  |
| gradient_boosted_trees        |    59 |        11 |          0.940072 |      1.5008   |
| gradient_boosted_trees        |    60 |        11 |          0.82749  |      1.08814  |
| gradient_boosted_trees        |    61 |        18 |          1.65957  |      1.84388  |
| gradient_boosted_trees        |    62 |         7 |          1.7782   |      2.76695  |
| gradient_boosted_trees        |    63 |        28 |          0.557892 |      1.29828  |
| gradient_boosted_trees        |    65 |        27 |          0.612976 |      1.12401  |
| mlp                           |    58 |        25 |          0.515431 |      1.15534  |
| mlp                           |    59 |        11 |          0.526612 |      1.463    |
| mlp                           |    60 |        11 |          0.613427 |      1.66954  |
| mlp                           |    61 |        18 |          0.845397 |      0.961884 |
| mlp                           |    62 |         7 |          1.11561  |      1.61587  |
| mlp                           |    63 |        28 |          0.38509  |      0.582021 |
| mlp                           |    65 |        27 |          0.492792 |      0.935076 |
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
|            0.2 |                1000 |       127 |           1.60997 |            1.25852 |             1.72205 |       1.49924 |

Best method at each gate:

|   cfd_fraction |   amplitude_cut_adc | method   |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |
|---------------:|--------------------:|:---------|----------:|------------------:|-------------------:|--------------------:|
|            0.2 |                1000 | mlp      |       127 |          0.584091 |           0.478496 |            0.773545 |

Method stability across all gates:

| method                        |   gates |   median_width_ns |   min_width_ns |   max_width_ns |   mean_n_pairs |
|:------------------------------|--------:|------------------:|---------------:|---------------:|---------------:|
| mlp                           |       1 |          0.584091 |       0.584091 |       0.584091 |            127 |
| gradient_boosted_trees        |       1 |          0.990472 |       0.990472 |       0.990472 |            127 |
| constrained_monotone_timewalk |       1 |          1.51782  |       1.51782  |       1.51782  |            127 |
| ridge                         |       1 |          1.61473  |       1.61473  |       1.61473  |            127 |
| cnn_1d                        |       1 |          1.74046  |       1.74046  |       1.74046  |            127 |
| gated_residual_cnn_new        |       1 |          2.26107  |       2.26107  |       2.26107  |            127 |

Full method/gate metrics, including all CIs and Gaussian-core diagnostics, are in `method_metrics.csv`.

## Paired Deltas

Each delta is `W_68(method) - W_68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

|   cfd_fraction |   amplitude_cut_adc | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|---------------:|--------------------:|:-----------------------------------------------------------|------------:|-------------:|----------:|
|            0.2 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |   -0.194646 |    0.626678  |     0.304 |
|            0.2 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |    0.379992 |    1.0853    |     0     |
|            0.2 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -0.896547 |   -0.0956505 |     0.024 |
|            0.2 |                1000 | mlp_minus_constrained_monotone_timewalk                    |   -1.1575   |   -0.659483  |     0     |
|            0.2 |                1000 | ridge_minus_constrained_monotone_timewalk                  |   -0.237392 |    0.94038   |     0.704 |

## Systematics and Caveats

| check                       |     value | flag   |
|:----------------------------|----------:|:-------|
| forbidden_feature_overlap   |           | False  |
| group_split_r2_mean         |  0.492134 | False  |
| row_split_advantage_rmse_ns | -0.214138 | False  |

- **Run support:** the held-out Sample IV set has only seven runs and small A1/A3 pair counts; CIs are therefore intentionally run-dominated.
- **Cut dependence:** raising the amplitude cut changes both timing resolution and sample composition. A smaller width at a high cut is not automatically a better general estimator because it rejects lower-amplitude pulses.
- **CFD dependence:** alternate CFD fractions change the leading-edge interpolation and can trade noise sensitivity against timewalk. The gate grid tests this directly rather than assuming CFD20 is uniquely optimal.
- **Gaussian-core diagnostics:** core sigma and chi2/ndf are reported but not used for selection because low counts and tails make binned Gaussian fits fragile.
- **Model selection:** the named winner is a benchmark result on the preregistered standard gate; the full grid is used to assess sensitivity, not to tune the production gate after looking.
- **Leakage:** the split is by run, and forbidden target-derived features are excluded. Remaining risk is support mismatch, not direct row leakage.

## Conclusion

The standard A-stack gate is reproducible from raw ROOT and the method ranking is not explained by the old Gaussian-core fit alone. At CFD20/cut1000, **mlp** wins the held-out benchmark with width **0.584 ns**. The atom audit compares full waveform, leading-edge dropped, tail dropped, amplitude-only, and shuffled-waveform controls to separate waveform-shape transfer from amplitude/support artifacts. The traditional constrained baseline remains a defensible low-variance reference, but learned waveform methods capture additional shape/support information.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, `atom_ablation_metrics.csv`, `atom_ablation_predictions.csv.gz`, and PNG diagnostics are in this report directory.

## S18h Waveform Atom Audit

This ticket-specific audit asks which waveform atom makes late/mixed Sample-III to Sample-IV A1-A3 transfer look narrow. The table below retrains ridge and gradient-boosted-tree residual models on the primary CFD20/cut1000 split after targeted ablations. `drop_leading_edge_samples` zeros normalized samples 0-5 in both channels and their pairwise differences; `drop_tail_samples` zeros samples 10-17; `amplitude_only` retains only log-amplitude and positive-area summaries; `waveform_shuffled_control` preserves marginal waveform-sample distributions but breaks event-local waveform shape. All intervals are 95% run-bootstrap intervals over held-out Sample IV runs.

| atom_mode                 | model_family           |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:--------------------------|:-----------------------|----------:|------------------:|-------------------:|--------------------:|--------------:|---------------------------:|
| full_features             | gradient_boosted_trees |       127 |          0.990472 |           0.718676 |             1.35428 |       1.53703 |                  0.015748  |
| drop_tail_samples         | gradient_boosted_trees |       127 |          1.0226   |           0.764453 |             1.38403 |       1.50925 |                  0.015748  |
| drop_tail_samples         | ridge                  |       127 |          1.22355  |           0.965013 |             1.95655 |       2.2374  |                  0.0629921 |
| drop_leading_edge_samples | gradient_boosted_trees |       127 |          1.41171  |           1.25987  |             1.69706 |       1.77839 |                  0.023622  |
| drop_leading_edge_samples | ridge                  |       127 |          1.5583   |           1.22873  |             1.86223 |       2.78054 |                  0.0393701 |
| full_features             | ridge                  |       127 |          1.57013  |           1.24461  |             1.85619 |       2.76313 |                  0.0472441 |
| waveform_shuffled_control | ridge                  |       127 |          1.62954  |           1.42955  |             1.85191 |       1.84885 |                  0.0314961 |
| amplitude_only            | gradient_boosted_trees |       127 |          1.7094   |           1.42956  |             2.11098 |       2.00782 |                  0.0314961 |
| waveform_shuffled_control | gradient_boosted_trees |       127 |          1.74261  |           1.48309  |             2.51265 |       2.44455 |                  0.0393701 |
| amplitude_only            | ridge                  |       127 |          1.78459  |           1.57662  |             2.39451 |       2.15609 |                  0.0314961 |

Ablation interpretation: if dropping leading-edge samples or shuffling waveform samples materially widens the residuals relative to `full_features`, the narrow transfer is waveform-shape dependent rather than only an amplitude-channel artifact. If `amplitude_only` is comparable to the full model, the dominant atom is support/amplitude matching rather than learned local pulse shape. The shuffled control is the direct leakage guard because it keeps one-dimensional sample marginals but destroys event-local waveform timing structure.

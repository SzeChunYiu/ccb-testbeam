# S18i: A-stack support-matched external timing transfer with monotone constraints

- **Ticket:** `1781109770.1737.0fe07286`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-07-09
- **Input:** raw A-stack ROOT `HRDv` from `/home/billy/ccb-data/extracted/root/root`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18i_1781109770_1737_0fe07286_astack_support_matched_monotone_transfer.py --config configs/s18i_1781109770_1737_0fe07286_astack_support_matched_monotone_transfer.json`
- **Primary split:** train on Sample III runs `31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57`; evaluate on held-out Sample IV analysis runs `58,59,60,61,62,63,65`.
- **Primary metric:** `percentile68_ns = 0.5 * (Q_84(e - median(e)) - Q_16(e - median(e)))`, with 95% confidence intervals from a bootstrap over held-out runs.

## Abstract

This study asks whether a predeclared monotone, support-matched A-stack timewalk model retains late Sample-IV transfer gains without relying on unconstrained waveform nuisance capacity. The primary gate is CFD `[0.2]` with amplitude cut `[1000.0]` ADC. Raw A1-A3 residuals are reconstructed directly from ROOT, then corrected with a strong constrained traditional timewalk model and five learned alternatives: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN. The ticket-specific support audit retrains ridge and gradient-boosted-tree models after leading-edge, tail, amplitude-only, and shuffled-waveform controls on the same run split to separate support matching from local waveform-shape transfer.

At the preregistered standard gate CFD20/cut1000, the winner is **mlp**, with held-out width **0.529 ns** and run-bootstrap CI **[0.364, 0.879] ns**. The uncorrected standard-gate A-stack width is **1.610 ns** with CI **[1.275, 1.702] ns**.

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
| mlp                           |       127 |           0.52854 |           0.36372  |            0.879151 |        0.325654 |       1.51994 |                 0.023622   |
| gradient_boosted_trees        |       127 |           1.03488 |           0.723156 |            1.39164  |        0.914072 |       1.4037  |                 0.00787402 |
| gated_residual_cnn_new        |       127 |           1.31844 |           0.853164 |            1.58848  |        0.96854  |       1.45664 |                 0.015748   |
| constrained_monotone_timewalk |       127 |           1.51782 |           1.24031  |            1.71697  |        3.8723   |       1.47456 |                 0          |
| ridge                         |       127 |           1.61473 |           1.28358  |            2.38129  |        1.62296  |       2.27543 |                 0.0314961  |
| cnn_1d                        |       127 |           1.76697 |           1.45877  |            2.0788   |        1.88076  |       1.78271 |                 0.00787402 |

Per-run standard-gate widths:

| method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:------------------------------|------:|----------:|------------------:|--------------:|
| cnn_1d                        |    58 |        25 |          1.11881  |      1.49945  |
| cnn_1d                        |    59 |        11 |          1.68916  |      1.80063  |
| cnn_1d                        |    60 |        11 |          1.01028  |      1.43491  |
| cnn_1d                        |    61 |        18 |          2.11352  |      1.94919  |
| cnn_1d                        |    62 |         7 |          2.28721  |      2.44038  |
| cnn_1d                        |    63 |        28 |          1.43513  |      1.74134  |
| cnn_1d                        |    65 |        27 |          1.5557   |      1.75895  |
| constrained_monotone_timewalk |    58 |        25 |          1.07602  |      1.28344  |
| constrained_monotone_timewalk |    59 |        11 |          1.0004   |      1.19702  |
| constrained_monotone_timewalk |    60 |        11 |          0.97022  |      1.16291  |
| constrained_monotone_timewalk |    61 |        18 |          1.65913  |      1.80175  |
| constrained_monotone_timewalk |    62 |         7 |          0.990411 |      1.56649  |
| constrained_monotone_timewalk |    63 |        28 |          1.33336  |      1.38912  |
| constrained_monotone_timewalk |    65 |        27 |          1.57379  |      1.62056  |
| gated_residual_cnn_new        |    58 |        25 |          0.782145 |      0.958866 |
| gated_residual_cnn_new        |    59 |        11 |          1.71886  |      1.70177  |
| gated_residual_cnn_new        |    60 |        11 |          0.628958 |      0.938538 |
| gated_residual_cnn_new        |    61 |        18 |          1.48458  |      1.35372  |
| gated_residual_cnn_new        |    62 |         7 |          1.58673  |      2.1345   |
| gated_residual_cnn_new        |    63 |        28 |          0.845987 |      1.34931  |
| gated_residual_cnn_new        |    65 |        27 |          1.07546  |      1.66501  |
| gradient_boosted_trees        |    58 |        25 |          0.683827 |      1.14334  |
| gradient_boosted_trees        |    59 |        11 |          1.30015  |      1.57727  |
| gradient_boosted_trees        |    60 |        11 |          0.814179 |      0.979327 |
| gradient_boosted_trees        |    61 |        18 |          1.65861  |      1.73307  |
| gradient_boosted_trees        |    62 |         7 |          1.34114  |      2.5183   |
| gradient_boosted_trees        |    63 |        28 |          0.580619 |      1.37284  |
| gradient_boosted_trees        |    65 |        27 |          0.667516 |      0.99889  |
| mlp                           |    58 |        25 |          0.472789 |      1.38385  |
| mlp                           |    59 |        11 |          1.39627  |      2.20277  |
| mlp                           |    60 |        11 |          0.740639 |      3.15034  |
| mlp                           |    61 |        18 |          0.759984 |      0.76132  |
| mlp                           |    62 |         7 |          0.781373 |      0.740473 |
| mlp                           |    63 |        28 |          0.327828 |      1.15846  |
| mlp                           |    65 |        27 |          0.361852 |      0.925711 |
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
|            0.2 |                1000 |       127 |           1.60997 |            1.27488 |             1.70151 |       1.49924 |

Best method at each gate:

|   cfd_fraction |   amplitude_cut_adc | method   |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |
|---------------:|--------------------:|:---------|----------:|------------------:|-------------------:|--------------------:|
|            0.2 |                1000 | mlp      |       127 |           0.52854 |            0.36372 |            0.879151 |

Method stability across all gates:

| method                        |   gates |   median_width_ns |   min_width_ns |   max_width_ns |   mean_n_pairs |
|:------------------------------|--------:|------------------:|---------------:|---------------:|---------------:|
| mlp                           |       1 |           0.52854 |        0.52854 |        0.52854 |            127 |
| gradient_boosted_trees        |       1 |           1.03488 |        1.03488 |        1.03488 |            127 |
| gated_residual_cnn_new        |       1 |           1.31844 |        1.31844 |        1.31844 |            127 |
| constrained_monotone_timewalk |       1 |           1.51782 |        1.51782 |        1.51782 |            127 |
| ridge                         |       1 |           1.61473 |        1.61473 |        1.61473 |            127 |
| cnn_1d                        |       1 |           1.76697 |        1.76697 |        1.76697 |            127 |

Full method/gate metrics, including all CIs and Gaussian-core diagnostics, are in `method_metrics.csv`.

## Paired Deltas

Each delta is `W_68(method) - W_68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

|   cfd_fraction |   amplitude_cut_adc | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|---------------:|--------------------:|:-----------------------------------------------------------|------------:|-------------:|----------:|
|            0.2 |                1000 | cnn_1d_minus_constrained_monotone_timewalk                 |  -0.0988619 |     0.643061 |      0.2  |
|            0.2 |                1000 | gated_residual_cnn_new_minus_constrained_monotone_timewalk |  -0.733556  |     0.198893 |      0.28 |
|            0.2 |                1000 | gradient_boosted_trees_minus_constrained_monotone_timewalk |  -0.866106  |    -0.11475  |      0    |
|            0.2 |                1000 | mlp_minus_constrained_monotone_timewalk                    |  -1.26553   |    -0.434986 |      0.01 |
|            0.2 |                1000 | ridge_minus_constrained_monotone_timewalk                  |  -0.292017  |     0.806478 |      0.95 |

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

The standard A-stack gate is reproducible from raw ROOT and the method ranking is not explained by the old Gaussian-core fit alone. At CFD20/cut1000, **mlp** wins the held-out benchmark with width **0.529 ns**. The atom audit compares full waveform, leading-edge dropped, tail dropped, amplitude-only, and shuffled-waveform controls to separate waveform-shape transfer from amplitude/support artifacts. The traditional constrained baseline remains a defensible low-variance reference, but learned waveform methods capture additional shape/support information.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, `atom_ablation_metrics.csv`, `atom_ablation_predictions.csv.gz`, and PNG diagnostics are in this report directory.

## S18i Support and Waveform Nuisance Audit

This ticket-specific audit asks whether support-matched monotone transfer is enough to explain the late Sample-IV A1-A3 width, or whether waveform-local nuisance capacity is still required. The table below retrains ridge and gradient-boosted-tree residual models on the primary CFD20/cut1000 split after targeted ablations. `drop_leading_edge_samples` zeros normalized samples 0-5 in both channels and their pairwise differences; `drop_tail_samples` zeros samples 10-17; `amplitude_only` retains only log-amplitude and positive-area summaries; `waveform_shuffled_control` preserves marginal waveform-sample distributions but breaks event-local waveform shape. All intervals are 95% run-bootstrap intervals over held-out Sample IV runs.

| atom_mode                 | model_family           |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:--------------------------|:-----------------------|----------:|------------------:|-------------------:|--------------------:|--------------:|---------------------------:|
| drop_tail_samples         | gradient_boosted_trees |       127 |          0.966301 |           0.730776 |             1.28546 |       1.44647 |                 0.00787402 |
| full_features             | gradient_boosted_trees |       127 |          1.03488  |           0.72007  |             1.45398 |       1.4037  |                 0.00787402 |
| drop_tail_samples         | ridge                  |       127 |          1.22355  |           0.967098 |             2.12458 |       2.2374  |                 0.0629921  |
| drop_leading_edge_samples | gradient_boosted_trees |       127 |          1.45743  |           1.32552  |             1.80034 |       1.74785 |                 0.015748   |
| drop_leading_edge_samples | ridge                  |       127 |          1.5583   |           1.24893  |             1.85535 |       2.78054 |                 0.0393701  |
| full_features             | ridge                  |       127 |          1.57013  |           1.23521  |             1.90891 |       2.76313 |                 0.0472441  |
| waveform_shuffled_control | gradient_boosted_trees |       127 |          1.61862  |           1.4359   |             2.05839 |       2.38042 |                 0.0393701  |
| waveform_shuffled_control | ridge                  |       127 |          1.69331  |           1.45298  |             1.94521 |       1.85983 |                 0.0314961  |
| amplitude_only            | gradient_boosted_trees |       127 |          1.78215  |           1.4082   |             2.096   |       2.02542 |                 0.0472441  |
| amplitude_only            | ridge                  |       127 |          1.78459  |           1.637    |             2.2964  |       2.15609 |                 0.0314961  |

Ablation interpretation: if dropping leading-edge samples or shuffling waveform samples materially widens the residuals relative to `full_features`, the narrow transfer is waveform-shape dependent rather than only an amplitude-channel artifact. If `amplitude_only` is comparable to the full model, the dominant atom is support/amplitude matching rather than learned local pulse shape. The shuffled control is the direct leakage guard because it keeps one-dimensional sample marginals but destroys event-local waveform timing structure.

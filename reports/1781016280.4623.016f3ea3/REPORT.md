# S05d: per-stave timing priors from B-stack covariance

- **Ticket:** 1781016280.4623.016f3ea3
- **Worker:** testbeam-laptop-3
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05d_1781016280_4623_016f3ea3_twoended_priors.yaml`
- **Raw input:** `data/root/root`

## Question

Convert the S05c covariance decomposition into per-stave timing-resolution priors for the two-ended projection, and test whether the large B2-local component can be downweighted without biasing downstream timing.

## Reproduction from raw ROOT

This gate was run first from `h101/HRDv` with the same B-stack channel map, CFD20 timing, and `A > 1000 ADC` selector as S05c. It reproduces both the selected-pulse anchors and the S05c raw event-level covariance-decomposition numbers.

| quantity                                                      |   report_value |   reproduced |        delta |   tolerance | pass   |
|:--------------------------------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| total_selected_b_pulses                                       |    640737      |  640737      |  0           |        0    | True   |
| sample_i_analysis_b_selected_pulses                           |    252266      |  252266      |  0           |        0    | True   |
| sample_ii_analysis_b_selected_pulses                          |    125096      |  125096      |  0           |        0    | True   |
| s05c_event_level_pooled_var_B2                                |       166.497  |     166.497  | -0.000524206 |        0.01 | True   |
| s05c_event_level_pooled_var_B4                                |        34.2436 |      34.2436 |  2.49423e-05 |        0.01 | True   |
| s05c_event_level_pooled_var_B6                                |        35.0676 |      35.0676 |  3.77733e-05 |        0.01 | True   |
| s05c_event_level_pooled_var_B8                                |        43.1141 |      43.1141 | -4.68959e-06 |        0.01 | True   |
| s05c_event_level_pooled_B2_variance_minus_downstream_mean_ns2 |       129.022  |     129.022  | -0.000542881 |        0.01 | True   |

Raw-pair-median covariance decomposition rebuilt from ROOT:

|    var_B2 |   cov_B2_B4 |   cov_B2_B6 |   cov_B2_B8 |   var_B4 |   cov_B4_B6 |   cov_B4_B8 |    var_B6 |   cov_B6_B8 |    var_B8 |   offdiag_rmse_ns2 |   n_offdiag_covariances | method          | scope              |   B2_variance_minus_downstream_mean_ns2 |
|----------:|------------:|------------:|------------:|---------:|------------:|------------:|----------:|------------:|----------:|-------------------:|------------------------:|:----------------|:-------------------|----------------------------------------:|
| 166.497   |  -100.696   |  -113.321   |  -118.976   | 34.2436  |    21.3232  |    10.8859  | 35.0676   |    21.8624  | 43.1141   |            10.4259 |                      15 | raw_pair_median | event_level_pooled |                                 129.022 |
|   5.40607 |    -3.33382 |    -3.81215 |    -3.66618 |  0.78651 |     0.93462 |     0.82618 |  0.786241 |     1.30505 |  0.767476 |             1.4413 |                      15 | raw_pair_median | run_median_level   |                                   4.626 |

## Methods

For each held-out run, all priors and offsets are fit only on the other runs. Projection residuals are self-consistency tests on held-out downstream targets (`B4/B6/B8`): predict one downstream corrected time from the other selected staves and score the held-out residual. This is not an absolute time calibration, but it directly tests whether B2 weight changes perturb downstream timing.

Traditional: train-run pair robust widths give an NNLS independent-stave prior, and the main S05d prior converts the S05c event/run covariance decomposition into a conservative two-ended variance `run_corr_floor + event_uncorrelated/2`. That keeps slow/common components while applying the two-ended sqrt(2) reduction only to the local end variance.

ML: an ExtraTrees reliability model predicts an own-stave absolute timing-error proxy from that stave's waveform summaries only. It excludes run, event, raw time, residual, target-stave identity, and other-stave timing. The dynamic weights sit on top of the S05c static prior and are evaluated only on held-out runs.

## Per-stave Priors

| stave   |   robust_two_end_var_ns2 |   s05c_two_end_var_ns2 |   s05c_two_end_sigma_ns |
|:--------|-------------------------:|-----------------------:|------------------------:|
| B2      |                8.6938    |                86.3301 |                 9.28527 |
| B4      |                0.300485  |                17.5797 |                 4.19087 |
| B6      |                0.0472465 |                17.9903 |                 4.23968 |
| B8      |                3.35953   |                22.0022 |                 4.68933 |

## Held-out Projection Benchmark

| method                       | target_stave   |   n_residuals |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   median_bias_ns |   median_bias_ci_low_ns |   median_bias_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   mean_b2_weight_share |
|:-----------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|-----------------:|------------------------:|-------------------------:|--------------:|----------------------:|-----------------------:|
| equal_twoend_projection      | B4             |         12089 |       21 |      2.32487 |             1.84258 |              8.02044 |       -4.14782   |               -4.36509  |               -3.76249   |      10.6499  |             0.140458  |             0.436581   |
| equal_twoend_projection      | B6             |         12190 |       21 |      2.53008 |             2.086   |              7.87846 |       -2.89025   |               -3.07389  |               -2.49984   |      11.2812  |             0.158409  |             0.437107   |
| equal_twoend_projection      | B8             |          4695 |       21 |      2.27923 |             1.89281 |              6.99308 |       -2.67121   |               -2.7962   |               -2.22478   |      10.2282  |             0.1459    |             0.336706   |
| ml_dynamic_twoend_prior      | B4             |         12089 |       21 |      1.99978 |             1.86752 |              2.38029 |       -1.39551   |               -1.6154   |               -1.04845   |       6.56039 |             0.0556704 |             0.104305   |
| ml_dynamic_twoend_prior      | B6             |         12190 |       21 |      1.87374 |             1.7317  |              2.35869 |       -0.0122557 |               -0.259666 |                0.289372  |       6.08462 |             0.0644791 |             0.108485   |
| ml_dynamic_twoend_prior      | B8             |          4695 |       21 |      1.72584 |             1.62155 |              2.05069 |       -0.446994  |               -0.585005 |               -0.0872115 |       6.98324 |             0.0374867 |             0.0680572  |
| robust_nnls_twoend_prior     | B4             |         12089 |       21 |      1.82394 |             1.78388 |              1.86615 |       -0.858018  |               -1.04254  |               -0.601399  |       6.63583 |             0.0194392 |             0.00593476 |
| robust_nnls_twoend_prior     | B6             |         12190 |       21 |      1.98193 |             1.89998 |              2.34354 |        0.794515  |                0.60794  |                1.04824   |       6.25965 |             0.0415094 |             0.0298264  |
| robust_nnls_twoend_prior     | B8             |          4695 |       21 |      1.46019 |             1.36779 |              1.50392 |       -0.183136  |               -0.34404  |               -0.0232163 |       6.80163 |             0.0176784 |             0.00378153 |
| s05c_covariance_twoend_prior | B4             |         12089 |       21 |      2.08459 |             1.90437 |              3.13072 |       -1.66743   |               -1.86445  |               -1.26539   |       6.79978 |             0.0834643 |             0.14419    |
| s05c_covariance_twoend_prior | B6             |         12190 |       21 |      2.03347 |             1.80747 |              3.4579  |       -0.262235  |               -0.469007 |                0.0494105 |       6.62688 |             0.0962264 |             0.142547   |
| s05c_covariance_twoend_prior | B8             |          4695 |       21 |      1.88127 |             1.70736 |              2.7503  |       -0.632205  |               -0.769919 |               -0.253081  |       7.285   |             0.0707135 |             0.0945206  |
| equal_twoend_projection      | all_downstream |         28974 |       21 |      2.51991 |             2.08409 |              7.96143 |       -3.3897    |               -3.50889  |               -3.03702   |      10.8798  |             0.147166  |             0.420618   |
| ml_dynamic_twoend_prior      | all_downstream |         28974 |       21 |      2.02102 |             1.86358 |              2.53873 |       -0.621021  |               -0.730548 |               -0.289512  |       6.49182 |             0.0571202 |             0.10019    |
| robust_nnls_twoend_prior     | all_downstream |         28974 |       21 |      1.99486 |             1.88564 |              2.12652 |       -0.0731964 |               -0.152461 |                0.013539  |       6.58189 |             0.031511  |             0.0156376  |
| s05c_covariance_twoend_prior | all_downstream |         28974 |       21 |      2.14725 |             1.945   |              3.57121 |       -0.87028   |               -0.974348 |               -0.519723  |       6.85954 |             0.0857665 |             0.13545    |

The S05c static prior minus equal-weight sigma68 delta is `-0.373` ns with held-out-run bootstrap CI `[-4.758, -0.155]`. The ML dynamic prior minus equal-weight delta is `-0.499` ns with CI `[-5.788, -0.220]`.

Pairwise deltas:

| comparison                                                 | target_stave   |   paired_rows |   delta_sigma68_ns |   ci_low_ns |   ci_high_ns |   p_two_sided |
|:-----------------------------------------------------------|:---------------|--------------:|-------------------:|------------:|-------------:|--------------:|
| robust_nnls_twoend_prior_minus_equal_twoend_projection     | all_downstream |         28974 |          -0.525054 |    -6.79395 |   -0.161425  |    0.00333333 |
| robust_nnls_twoend_prior_minus_equal_twoend_projection     | B4             |         12089 |          -0.50093  |    -5.18397 |   -0.0400166 |    0.0233333  |
| robust_nnls_twoend_prior_minus_equal_twoend_projection     | B6             |         12190 |          -0.548155 |    -6.51672 |   -0.159272  |    0          |
| robust_nnls_twoend_prior_minus_equal_twoend_projection     | B8             |          4695 |          -0.819044 |    -5.1549  |   -0.422874  |    0          |
| s05c_covariance_twoend_prior_minus_equal_twoend_projection | all_downstream |         28974 |          -0.372662 |    -4.75799 |   -0.154593  |    0          |
| s05c_covariance_twoend_prior_minus_equal_twoend_projection | B4             |         12089 |          -0.240283 |    -4.36869 |    0.0376157 |    0.18       |
| s05c_covariance_twoend_prior_minus_equal_twoend_projection | B6             |         12190 |          -0.496606 |    -5.3018  |   -0.277872  |    0          |
| s05c_covariance_twoend_prior_minus_equal_twoend_projection | B8             |          4695 |          -0.397956 |    -4.01497 |   -0.181104  |    0          |
| ml_dynamic_twoend_prior_minus_equal_twoend_projection      | all_downstream |         28974 |          -0.498889 |    -5.78775 |   -0.219587  |    0          |
| ml_dynamic_twoend_prior_minus_equal_twoend_projection      | B4             |         12089 |          -0.325089 |    -4.84658 |    0.0265703 |    0.0933333  |
| ml_dynamic_twoend_prior_minus_equal_twoend_projection      | B6             |         12190 |          -0.656343 |    -5.38655 |   -0.359955  |    0          |
| ml_dynamic_twoend_prior_minus_equal_twoend_projection      | B8             |          4695 |          -0.553386 |    -5.66046 |   -0.264402  |    0          |

## Leakage And Bias Checks

| check                                 |   value | pass   | interpretation                                                                                                     |
|:--------------------------------------|--------:|:-------|:-------------------------------------------------------------------------------------------------------------------|
| raw_reproduction_gate                 | 1       | True   | S00 counts and S05c raw covariance anchor were rebuilt before projection                                           |
| run_split_event_overlap               | 0       | True   | folds hold out whole runs; no train rows from the held-out run enter priors or ML reliability training             |
| ml_feature_policy                     | 1       | True   | ML reliability inputs are own-stave waveform summaries only; no run, event, time, residual, or target-stave labels |
| s05c_b2_downweighted                  | 4.49853 | True   | B2 two-ended prior variance is larger than the downstream mean, so B2 receives less projection weight              |
| best_method_not_unphysical_zero_width | 1.99486 | True   | guards against a target echo or accidental direct residual feature                                                 |
| ml_downstream_bias_small_vs_sigma     | 0.30728 | False  | large residual-width gains are not accepted if they shift the downstream median strongly                           |

## Finding

The S05c conversion does what it should mechanically: B2 receives a much larger two-ended prior variance than B4/B6/B8, so B2 is downweighted in the projection. On the held-out downstream self-consistency benchmark, static S05c downweighting improves the pooled residual width versus equal weights, but the gain is not uniform by target stave and the robust NNLS prior is at least as competitive. The dynamic ML prior is useful as a diagnostic reliability gate, but it should not replace the static prior here because its downstream median-bias check fails.

## Artifacts

`reproduction_match_table.csv`, `s05c_raw_covariance_reproduction.csv`, `per_fold_twoended_priors.csv`, `projection_residuals.csv`, `projection_metrics.csv`, `projection_delta_bootstrap.csv`, `ml_training_summary.csv`, `ml_training_preview.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

## Follow-up tickets

Skipped: S05f already exists as the non-duplicate next study for matched B2-local covariance confound separation before stronger two-ended projection claims.

# S18l: External A-gate transfer validation on independent B covariance endpoint

- **Ticket:** `1783599792.40950.61bc08c7`
- **Worker:** `testbeam-laptop-1`
- **Source raw-root reconstruction:** `reports/1781125119.10600.08d70fd7__s18k_fixed_efficiency_astack_covariance_transfer`
- **Endpoint:** later `sample_ii_analysis` B-stack runs, non-B2 pairs `B4-B6, B4-B8, B6-B8`
- **No Monte Carlo:** raw HRD ROOT-derived tables only

## Abstract

This study performs the requested external validation of the S18k per-run fixed-efficiency A-stack gate. The A1/A3 thresholds, A robust-width summaries, method panel, and adoption rule are frozen from S18k. S18l does not tune a new A threshold. It evaluates the frozen residual predictors on an orthogonal B-stack covariance endpoint: later `sample_ii_analysis` runs and only B4/B6/B8 pair covariances, excluding all B2-containing pairs used most directly in earlier B-stack transfer diagnostics. Confidence intervals are run-block bootstraps over held-out runs.

The winner named in `result.json` is **extra_trees_s18e_style**, selected by lowest held-out mean absolute pair covariance among non-control methods on this external endpoint. Its covariance is **5.199 ns^2** with 95% run-block CI **[2.971, 7.580]**. The frozen traditional A-width gate Ridge gives **30.269 ns^2** with CI **[25.800, 35.760]**. The safety verdict remains **benchmark_winner_not_adopted_as_safe_gate** because the endpoint is small and the validation is an external diagnostic rather than a new production threshold.

## Raw ROOT Reproduction

S18l inherits the raw ROOT reconstruction from S18k and verifies the exact raw-derived anchors before applying the external endpoint filter. The source S18k script rebuilt A-stack and B-stack pair tables from `/home/billy/ccb-data/extracted/root/root` with `uproot`; this report records the input checksums in `input_sha256.csv` and the source artifact checksums in `inherited_raw_derived_inputs.csv`.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total_selected_b_pulses | 640737 | 640737 | 0 | 0 | true |
| sample_i_analysis_b_selected_pulses | 252266 | 252266 | 0 | 0 | true |
| sample_ii_analysis_b_selected_pulses | 125096 | 125096 | 0 | 0 | true |
| fixed_efficiency_reference_events | 798651 | 798651 | 0 | 0 | true |
| fixed_efficiency_reference_pairs | 6377 | 6377 | 0 | 0 | true |
| sample_iv_fixed_efficiency_a1_a3_pairs | 2110 | 2110 | 0 | 0 | true |
| sample_iv_fixed_efficiency_a1_a3_robust_width_ns | 39.7132 | 39.7132 | 0 | 1e+06 | true |

## Methods

Let run `u` be the split unit. S18k defined an A-stack fixed-efficiency score

`s_i = min(A1_i, A3_i)`,

and selected a per-run threshold `tau_u` as the empirical `(1 - epsilon)` quantile, where `epsilon` is the frozen target efficiency. A pairs satisfying `s_i >= tau_u` define the A robust-width vector `a_u`. S18l freezes these `tau_u`, `a_u`, the S18k model classes, and the adoption rule.

For each B pair row, the residual target is

`r_ij = (t_j - t_i) - TOF_ij`.

Each method `m` supplies a leave-one-run-held-out prediction `hat r_m(x_i)` from the S18k folds. S18l evaluates

`e_i(m) = r_i - hat r_m(x_i)`

on the external endpoint only. The width metric is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

The covariance endpoint pivots residuals by event and B pair within each run. The primary score is

`C_m = mean_u mean_{p<q} |Cov_u(e_p(m), e_q(m))|`.

Bootstrap intervals resample held-out runs with replacement. This preserves the run-level uncertainty that matters for an external gate. Negative controls are kept from S18k: waveform-only MLP, pool-label control, and shuffled-target ExtraTrees.

## Endpoint Definition

The independent endpoint contains `sample_ii_analysis` runs only and excludes B2-containing pairs. It has `7` runs, `10045` unique run-events, and `18098` pair rows. Pairs are `B4-B6, B4-B8, B6-B8`.

## Held-out Benchmark

| method | method_class | n_pair_rows | n_runs | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | mean_abs_pair_cov_ns2 | mean_abs_pair_cov_ci_low_ns2 | mean_abs_pair_cov_ci_high_ns2 | correlated_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pair_median | traditional | 18098 | 7 | 1.74722 | 1.70814 | 1.79038 | 13.2031 | 7.86802 | 19.0145 | 0.340698 |
| traditional_a_width_gate_ridge | traditional | 18098 | 7 | 7.04214 | 6.583 | 7.53144 | 30.2689 | 25.8004 | 35.7603 | 0.433717 |
| ridge | ml | 18098 | 7 | 6.1103 | 5.48732 | 6.86132 | 24.7323 | 20.4904 | 29.7498 | 0.401579 |
| gradient_boosted_trees | ml | 18098 | 7 | 3.34481 | 3.20362 | 3.4312 | 8.31537 | 5.16721 | 11.122 | 0.340402 |
| extra_trees_s18e_style | ml | 18098 | 7 | 1.52814 | 1.48122 | 1.65972 | 5.19932 | 2.97055 | 7.58 | 0.322163 |
| mlp | ml | 18098 | 7 | 2.69715 | 2.57361 | 2.8445 | 12.4934 | 7.57299 | 17.7336 | 0.335362 |
| cnn_1d | ml | 18098 | 7 | 4.92775 | 3.08517 | 5.89219 | 13.5376 | 8.38893 | 18.805 | 0.32463 |
| support_gated_cnn_new | ml | 18098 | 7 | 3.33188 | 2.9476 | 3.70755 | 13.1325 | 8.06145 | 18.7316 | 0.344748 |
| waveform_only_mlp | control | 18098 | 7 | 2.92869 | 2.79916 | 3.13486 | 14.008 | 9.74322 | 18.2753 | 0.381246 |
| pool_label_control | control | 18098 | 7 | 1.91885 | 1.77842 | 2.05016 | 13.2031 | 7.86802 | 19.0145 | 0.340698 |
| ml_shuffled_target_control | control | 18098 | 7 | 4.09851 | 3.44843 | 4.42259 | 16.0056 | 11.8262 | 21.0937 | 0.354055 |

## Winner Deltas

| method | baseline | comparison | delta_sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | delta_mean_abs_pair_cov_ns2 | cov_ci_low_ns2 | cov_ci_high_ns2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| extra_trees_s18e_style | pair_median | winner_minus_pair_median | -0.213021 | -0.260465 | -0.0553519 | -8.03763 | -12.7873 | -2.87234 |
| extra_trees_s18e_style | traditional_a_width_gate_ridge | winner_minus_traditional_gate | -5.5487 | -5.96804 | -5.03897 | -24.952 | -28.2733 | -21.7031 |

## A-gate Strata

The frozen A percentile-68 width ranks are split into tertiles among the later endpoint runs. This is a diagnostic for whether A-stack width ordering transfers monotonically to orthogonal B covariance support.

| method | a_gate_stratum | n_runs | n_pair_rows | sigma68_ns | mean_abs_pair_cov_ns2 | correlated_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| pair_median | low_A_width_gate | 3 | 2567 | 1.78345 | 10.0643 | 0.129279 |
| pair_median | mid_A_width_gate | 2 | 7453 | 1.70432 | 17.5154 | 0.444211 |
| pair_median | high_A_width_gate | 2 | 8078 | 1.73989 | 13.5991 | 0.334604 |
| traditional_a_width_gate_ridge | low_A_width_gate | 3 | 2567 | 7.12971 | 32.7256 | 0.440933 |
| traditional_a_width_gate_ridge | mid_A_width_gate | 2 | 7453 | 6.61147 | 25.1446 | 0.427745 |
| traditional_a_width_gate_ridge | high_A_width_gate | 2 | 8078 | 7.47009 | 31.7083 | 0.417043 |
| ridge | low_A_width_gate | 3 | 2567 | 6.01011 | 25.0724 | 0.373567 |
| ridge | mid_A_width_gate | 2 | 7453 | 6.01942 | 22.3898 | 0.412824 |
| ridge | high_A_width_gate | 2 | 8078 | 6.31953 | 26.5647 | 0.405121 |
| gradient_boosted_trees | low_A_width_gate | 3 | 2567 | 3.23684 | 6.73891 | 0.099326 |
| gradient_boosted_trees | mid_A_width_gate | 2 | 7453 | 3.39008 | 9.19832 | 0.416355 |
| gradient_boosted_trees | high_A_width_gate | 2 | 8078 | 3.31354 | 9.79713 | 0.376626 |
| extra_trees_s18e_style | low_A_width_gate | 3 | 2567 | 1.79575 | 5.57868 | 0.090224 |
| extra_trees_s18e_style | mid_A_width_gate | 2 | 7453 | 1.49253 | 4.00196 | 0.402178 |
| extra_trees_s18e_style | high_A_width_gate | 2 | 8078 | 1.4875 | 5.82766 | 0.367466 |
| mlp | low_A_width_gate | 3 | 2567 | 2.86077 | 9.85644 | 0.130031 |
| mlp | mid_A_width_gate | 2 | 7453 | 2.65588 | 16.0469 | 0.439736 |
| mlp | high_A_width_gate | 2 | 8078 | 2.67225 | 12.8952 | 0.333884 |
| cnn_1d | low_A_width_gate | 3 | 2567 | 3.09158 | 9.99677 | 0.128136 |
| cnn_1d | mid_A_width_gate | 2 | 7453 | 3.80384 | 17.8286 | 0.439729 |
| cnn_1d | high_A_width_gate | 2 | 8078 | 6.04073 | 14.5579 | 0.329877 |
| support_gated_cnn_new | low_A_width_gate | 3 | 2567 | 3.28651 | 10.2749 | 0.131587 |
| support_gated_cnn_new | mid_A_width_gate | 2 | 7453 | 3.21088 | 17.1279 | 0.435118 |
| support_gated_cnn_new | high_A_width_gate | 2 | 8078 | 2.87211 | 13.4233 | 0.333291 |
| waveform_only_mlp | low_A_width_gate | 3 | 2567 | 3.21619 | 13.5936 | 0.168443 |
| waveform_only_mlp | mid_A_width_gate | 2 | 7453 | 2.9094 | 15.8819 | 0.435949 |
| waveform_only_mlp | high_A_width_gate | 2 | 8078 | 2.81126 | 12.7558 | 0.331896 |
| pool_label_control | low_A_width_gate | 3 | 2567 | 1.99711 | 10.0643 | 0.129279 |
| pool_label_control | mid_A_width_gate | 2 | 7453 | 1.75662 | 17.5154 | 0.444211 |
| pool_label_control | high_A_width_gate | 2 | 8078 | 1.91268 | 13.5991 | 0.334604 |
| ml_shuffled_target_control | low_A_width_gate | 3 | 2567 | 4.39667 | 14.1064 | 0.164593 |
| ml_shuffled_target_control | mid_A_width_gate | 2 | 7453 | 3.62679 | 17.7734 | 0.417402 |
| ml_shuffled_target_control | high_A_width_gate | 2 | 8078 | 4.39416 | 17.0865 | 0.343306 |

## Leakage Controls

| check | value | flag |
| --- | --- | --- |
| s18k_reproduction_all_pass | true | false |
| endpoint_uses_later_sample_ii_runs_only | 58,59,60,61,62,63,65 | false |
| endpoint_excludes_B2_pairs | B4-B6,B4-B8,B6-B8 | false |
| frozen_s18k_gate_no_new_threshold_tuning | true | false |
| claimed_ticket | 1783599792.40950.61bc08c7 | false |
| winner_cov_minus_waveform_only_control_ns2 | -8.80868 | false |
| winner_cov_minus_shuffled_control_ns2 | -10.8062 | false |

## Systematics and Caveats

The main systematic is limited external-support size: by excluding B2-containing pairs and using only later sample-II analysis runs, S18l gains orthogonality but loses row count and run diversity. The run-block intervals are therefore the primary uncertainty statement; row-only intervals would be anti-conservative.

The ML/NN methods are not retrained or retuned in S18l. This is intentional: the ticket asks for a frozen transfer validation. The drawback is that the models may not be optimal for the B4/B6/B8-only endpoint, especially the CNNs whose waveform support was learned on the broader S18k pair table.

The traditional comparator is strong but not purely hand-calibrated: it is the frozen S18k A-width gate Ridge with B shape summaries. Pair-median centering is also reported as a non-parametric traditional baseline because it is robust for width but can leave pair-covariance structure.

The adoption rule is conservative. Even when a learned method wins the benchmark covariance metric, S18l does not declare the A gate production-safe unless the winner is stable against the traditional A-width gate and negative controls on the external endpoint. The result is a benchmark winner and external validation artifact, not an unconditional production gate.

## Conclusion

On the orthogonal later B4/B6/B8 covariance endpoint, **extra_trees_s18e_style** has the lowest held-out mean absolute pair covariance among non-control methods. The frozen A-gate transfer signal is therefore reproducible outside the original S18k endpoint, but the safety decision remains conditional and non-adopted because the external endpoint is intentionally narrow and the strongest conclusion is comparative, not causal.

## Artifacts

`REPORT.md`, `result.json`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `gate_stratum_summary.csv`, `external_endpoint_residuals.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, `inherited_raw_derived_inputs.csv`, and `leakage_checks.csv` are in this folder.

# S10e: pile-up excess transfer to charge-energy proxies

- **Ticket:** `1781010955.636.68b17313`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** ML predictions are leave-one-run-out; CIs resample held-out runs within current group.

## Reproduction first

Raw ROOT reproduction passes before modeling: downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA. All six documented S10/S10c topology fractions pass the +/-0.0015 tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Traditional charge-energy transfer

Each selected event is represented by its maximum selected B pulse. The traditional controls use `integral_charge`, a template-scale charge proxy, the P04 paired odd-readout duplicate charge, and a bounded P07-style corrected B2 saturation-proxy charge. Strata are charge bin x S16 lowering x B2 saturation state.

Matched downstream excess is **0.00676** [0.00531, 0.00916] in uncorrected P04 charge strata and **0.00676** [0.00552, 0.00925] after P07 B2 correction. The matched P04 duplicate-charge median log shift is **0.04764** [0.02463, 0.05835].

| strata_definition   | metric                                |      value |     ci_low |    ci_high |   n_strata | bootstrap_unit           |   n_bootstrap |
|:--------------------|:--------------------------------------|-----------:|-----------:|-----------:|-----------:|:-------------------------|--------------:|
| uncorrected         | downstream_high_minus_low             | 0.00676266 | 0.00530842 | 0.00915972 |          9 | run_within_current_group |           250 |
| uncorrected         | integral_charge_median_log_shift      | 0.0301705  | 0.00814969 | 0.0384408  |          9 | run_within_current_group |           250 |
| uncorrected         | template_charge_median_log_shift      | 0.03464    | 0.0128978  | 0.0433936  |          9 | run_within_current_group |           250 |
| uncorrected         | p04_duplicate_charge_median_log_shift | 0.0476435  | 0.024625   | 0.0583542  |          9 | run_within_current_group |           250 |
| uncorrected         | uncorrected_charge_median_log_shift   | 0.0476435  | 0.0202277  | 0.0573401  |          9 | run_within_current_group |           250 |
| p07_corrected       | downstream_high_minus_low             | 0.00676254 | 0.00551731 | 0.0092545  |          9 | run_within_current_group |           250 |
| p07_corrected       | integral_charge_median_log_shift      | 0.0301705  | 0.00710005 | 0.0376693  |          9 | run_within_current_group |           250 |
| p07_corrected       | template_charge_median_log_shift      | 0.0346384  | 0.0102787  | 0.0420955  |          9 | run_within_current_group |           250 |
| p07_corrected       | p04_duplicate_charge_median_log_shift | 0.0476435  | 0.0208258  | 0.0574632  |          9 | run_within_current_group |           250 |
| p07_corrected       | p07_corrected_charge_median_log_shift | 0.0476112  | 0.0217121  | 0.0571774  |          9 | run_within_current_group |           250 |

Top matched uncorrected strata:

| stratum                               |   low_n |   high_n |   match_weight_raw |   low_downstream_fraction |   high_downstream_fraction |   downstream_high_minus_low |   match_weight |
|:--------------------------------------|--------:|---------:|-------------------:|--------------------------:|---------------------------:|----------------------------:|---------------:|
| q_ge_32k|s16_no_lowering|B2_unsat     |    2254 |    87971 |               2254 |                0.00576752 |                  0.0148344 |                 0.00906691  |     0.396691   |
| q_ge_32k|s16_no_lowering|B2_sat_proxy |    1371 |    97108 |               1371 |                0.0131291  |                  0.0162808 |                 0.00315174  |     0.241288   |
| q_16k_32k|s16_no_lowering|B2_unsat    |    1139 |    20083 |               1139 |                0.00877963 |                  0.019768  |                 0.0109883   |     0.200458   |
| q_8k_16k|s16_no_lowering|B2_unsat     |     561 |     8785 |                561 |                0.0124777  |                  0.0114969 |                -0.000980849 |     0.0987328  |
| q_lt_8k|s16_large_lowering|B2_unsat   |     189 |     8133 |                189 |                0.010582   |                  0.0179516 |                 0.00736954  |     0.0332629  |
| q_lt_8k|s16_no_lowering|B2_unsat      |      75 |     1208 |                 75 |                0          |                  0.0165563 |                 0.0165563   |     0.0131996  |
| q_8k_16k|s16_large_lowering|B2_unsat  |      35 |     1998 |                 35 |                0.0857143  |                  0.041041  |                -0.0446732   |     0.0061598  |
| q_16k_32k|s16_no_lowering|non_B2      |      29 |     1229 |                 29 |                1          |                  1         |                 0           |     0.00510384 |

## ML diagnostics

The ML pile-up/current scores are trained leave-one-run-out on the same selected events. The charge-residual score is a leave-one-run-out P04 duplicate-charge regressor using even-channel waveform and traditional charge summaries only; odd charge is the target, not a feature.

| metric                                                             |       value |     ci_low |    ci_high |   n_bootstrap | bootstrap_unit           |
|:-------------------------------------------------------------------|------------:|-----------:|-----------:|--------------:|:-------------------------|
| matched_stratified_injection_pileup_score_high_minus_low           |  0.0263974  |  0.0202    |  0.0305978 |           250 | run_within_current_group |
| matched_stratified_weak_current_score_high_minus_low               |  0.0301251  |  0.0226794 |  0.0410653 |           250 | run_within_current_group |
| matched_stratified_charge_regression_residual_score_high_minus_low | -0.00768313 | -0.0093758 | -0.0059309 |           250 | run_within_current_group |

The matched charge-regression residual high-minus-low is **-0.00768** [-0.00938, -0.00593]. It is diagnostic; it is not promoted above the matched traditional downstream/charge excess unless it predicts held-out excess beyond those controls.

## Leakage review

| check                                  |     value | flag   | note                                                                                          |
|:---------------------------------------|----------:|:-------|:----------------------------------------------------------------------------------------------|
| heldout_runs_excluded_from_training    | 1         | False  | Every ML score is predicted for a source run held out from fitting.                           |
| identifier_and_label_features_excluded | 1         | False  | Features exclude run, event number, current, group, downstream label, and odd charge samples. |
| row_split_current_auc                  | 0.675883  | False  | Random row split is an optimistic leakage stress test.                                        |
| run_heldout_current_auc                | 0.64622   | False  | Flagged if current is nearly identified under run holdout.                                    |
| row_minus_run_current_auc              | 0.0296629 | False  | Large row/run gap would indicate run-local leakage sensitivity.                               |
| injection_score_downstream_auc         | 0.677756  | False  | Flagged if synthetic pile-up score nearly recovers the downstream label.                      |
| charge_residual_current_auc            | 0.415171  | False  | Flagged if charge residual alone nearly identifies beam current.                              |

## Conclusion

The S10c high-current downstream excess remains after replacing the amplitude/topology-only control with P04 charge and P07 saturation-energy strata: uncorrected matched downstream excess is 0.00676 [0.00531, 0.00916], and P07-corrected B2 strata give 0.00676 [0.00552, 0.00925]. The P04 duplicate-charge median log shift is 0.04764 [0.02463, 0.05835], while the ML charge-residual delta is -0.00768 [-0.00938, -0.00593]. ML supports a current-coupled pulse/charge pathology diagnostic, but the traditional matched excess remains the physics-facing result.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, stratum, traditional, ML, leakage CSVs, and PNG diagnostics are in this folder.

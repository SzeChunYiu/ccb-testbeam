# S02e: pre-timing current/rate constrained run drift

Ticket `1781022084.1663.391b2fbf`. Worker `testbeam-laptop-2`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts before modeling. Total selected pulses: `640737` with delta `0`.

The run-65 S02/S02b anchor numbers were rebuilt from raw ROOT before the LORO scan:

| quantity                                       |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |            65 |                 2.88915 |                2.88915 | 0           | True   |
| S02 ML ridge                                   |            65 |                 1.84611 |                1.84611 | 2.88658e-14 | True   |
| S02b binned-template timewalk                  |            65 |                 3.4037  |                3.4037  | 0           | True   |
| S02b global-template timewalk                  |            65 |                 1.63542 |                1.63542 | 0           | True   |

## Method

The split is Sample II leave-one-run-out over runs `[58, 59, 60, 61, 62, 63, 65]`; run 64 remains calibration-only and is not a held-out analysis target. For each fold, templates, ML residual correction, and current/rate drift models are fit only on the other Sample-II analysis runs.

The drift nuisance uses documented beam current plus raw-derived trigger/event-density and amplitude-rate proxies: `current_nA, trigger_entry_density, entries_per_eventno, selected_multiplicity_per_event, downstream_allhit_fraction`. These covariates are derived from `TRIGGER`, `EVENTNO`, and amplitude gates before any timing labels or pair residual targets are built, then centered/scaled on the train runs for each fold. The basis contains no run one-hot, chronological run-z, event id, or held-out target feature.

Grouped train-run CV selections by fold:

|   heldout_run | method                      | base_method    |   drift_order |   mean_cv_sigma68_ns |   folds |
|--------------:|:----------------------------|:---------------|--------------:|---------------------:|--------:|
|            58 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              3.08498 |       3 |
|            58 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |              3.51134 |       3 |
|            58 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |            136.492   |       3 |
|            58 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.7507  |       3 |
|            58 | s02e_global_timewalk_drift1 | template_phase |             1 |              1.98367 |       3 |
|            58 | s02e_global_timewalk_drift2 | template_phase |             2 |            166.395   |       3 |
|            59 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              3.38545 |       3 |
|            59 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |             22.1103  |       3 |
|            59 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |             45.8427  |       3 |
|            59 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.75977 |       3 |
|            59 | s02e_global_timewalk_drift1 | template_phase |             1 |             10.4453  |       3 |
|            59 | s02e_global_timewalk_drift2 | template_phase |             2 |             17.8513  |       3 |
|            60 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              2.55793 |       3 |
|            60 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |              3.29897 |       3 |
|            60 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |              3.41829 |       3 |
|            60 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.73391 |       3 |
|            60 | s02e_global_timewalk_drift1 | template_phase |             1 |              2.52703 |       3 |
|            60 | s02e_global_timewalk_drift2 | template_phase |             2 |              5.61097 |       3 |
|            61 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              2.939   |       3 |
|            61 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |              2.99715 |       3 |
|            61 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |             18.417   |       3 |
|            61 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.68704 |       3 |
|            61 | s02e_global_timewalk_drift1 | template_phase |             1 |              1.78326 |       3 |
|            61 | s02e_global_timewalk_drift2 | template_phase |             2 |             30.6002  |       3 |
|            62 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              2.89376 |       3 |
|            62 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |             10.0259  |       3 |
|            62 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |             24.3448  |       3 |
|            62 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.72964 |       3 |
|            62 | s02e_global_timewalk_drift1 | template_phase |             1 |              7.52931 |       3 |
|            62 | s02e_global_timewalk_drift2 | template_phase |             2 |             18.9115  |       3 |
|            63 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              2.89888 |       3 |
|            63 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |             11.1241  |       3 |
|            63 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |             16.1912  |       3 |
|            63 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.73988 |       3 |
|            63 | s02e_global_timewalk_drift1 | template_phase |             1 |             13.33    |       3 |
|            63 | s02e_global_timewalk_drift2 | template_phase |             2 |             21.9779  |       3 |
|            65 | s02e_binned_timewalk_drift0 | s02b_template  |             0 |              3.10247 |       3 |
|            65 | s02e_binned_timewalk_drift1 | s02b_template  |             1 |              3.57683 |       3 |
|            65 | s02e_binned_timewalk_drift2 | s02b_template  |             2 |             23.9876  |       3 |
|            65 | s02e_global_timewalk_drift0 | template_phase |             0 |              1.74655 |       3 |
|            65 | s02e_global_timewalk_drift1 | template_phase |             1 |              2.7248  |       3 |
|            65 | s02e_global_timewalk_drift2 | template_phase |             2 |             21.6394  |       3 |

## Held-out results

Per-run event bootstrap results:

|   heldout_run | method                                          |   value |   ci_low |   ci_high |   n_heldout_events |   tail_frac_abs_gt5ns |
|--------------:|:------------------------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
|            58 | S02 train-best global template (template_phase) | 2.6428  |  2.6428  |   2.77317 |                 73 |            0.0776256  |
|            58 | S02b binned timewalk no covariate               | 3.63484 |  3.10354 |   4.08506 |                 73 |            0.191781   |
|            58 | S02e binned current/rate selected power 0       | 3.63484 |  3.12331 |   4.09119 |                 73 |            0.191781   |
|            58 | S02b global timewalk no covariate               | 1.52279 |  1.26152 |   1.86424 |                 73 |            0.0228311  |
|            58 | S02e global current/rate selected power 0       | 1.52279 |  1.26255 |   1.87971 |                 73 |            0.0228311  |
|            58 | S02 ML ridge                                    | 1.91964 |  1.64157 |   2.18314 |                 73 |            0.0228311  |
|            59 | S02 train-best global template (template_phase) | 2.99232 |  2.87333 |   3.12333 |                763 |            0.0677152  |
|            59 | S02b binned timewalk no covariate               | 3.63793 |  3.47788 |   3.79931 |                763 |            0.158148   |
|            59 | S02e binned current/rate selected power 0       | 3.63793 |  3.48338 |   3.79946 |                763 |            0.158148   |
|            59 | S02b global timewalk no covariate               | 1.59676 |  1.54867 |   1.65049 |                763 |            0.0126693  |
|            59 | S02e global current/rate selected power 0       | 1.59676 |  1.54186 |   1.65037 |                763 |            0.0126693  |
|            59 | S02 ML ridge                                    | 1.88049 |  1.80565 |   1.96757 |                763 |            0.0192224  |
|            60 | S02 train-best global template (template_phase) | 2.66393 |  2.66393 |   2.7113  |                808 |            0.0944719  |
|            60 | S02b binned timewalk no covariate               | 2.12741 |  2.04474 |   2.2002  |                808 |            0.0383663  |
|            60 | S02e binned current/rate selected power 0       | 2.12741 |  2.05083 |   2.20272 |                808 |            0.0383663  |
|            60 | S02b global timewalk no covariate               | 1.4719  |  1.42633 |   1.52379 |                808 |            0.0107261  |
|            60 | S02e global current/rate selected power 0       | 1.4719  |  1.42397 |   1.52188 |                808 |            0.0107261  |
|            60 | S02 ML ridge                                    | 1.81993 |  1.73516 |   1.91219 |                808 |            0.0189769  |
|            61 | S02 train-best global template (template_phase) | 2.70351 |  2.70351 |   2.70351 |                933 |            0.0428725  |
|            61 | S02b binned timewalk no covariate               | 3.06904 |  2.92728 |   3.17036 |                933 |            0.110397   |
|            61 | S02e binned current/rate selected power 0       | 3.06904 |  2.91237 |   3.1707  |                933 |            0.110397   |
|            61 | S02b global timewalk no covariate               | 2.18842 |  2.08933 |   2.26788 |                933 |            0.0275098  |
|            61 | S02e global current/rate selected power 0       | 2.18842 |  2.08516 |   2.26464 |                933 |            0.0275098  |
|            61 | S02 ML ridge                                    | 2.24243 |  2.15605 |   2.3404  |                933 |            0.0214362  |
|            62 | S02 train-best global template (template_phase) | 2.90117 |  2.90117 |   3.02631 |                807 |            0.0929368  |
|            62 | S02b binned timewalk no covariate               | 2.962   |  2.80611 |   3.08661 |                807 |            0.0912846  |
|            62 | S02e binned current/rate selected power 0       | 2.962   |  2.8445  |   3.07729 |                807 |            0.0912846  |
|            62 | S02b global timewalk no covariate               | 1.62995 |  1.57677 |   1.675   |                807 |            0.0111524  |
|            62 | S02e global current/rate selected power 0       | 1.62995 |  1.577   |   1.67588 |                807 |            0.0111524  |
|            62 | S02 ML ridge                                    | 1.86001 |  1.77156 |   1.94043 |                807 |            0.0144568  |
|            63 | S02 train-best global template (template_phase) | 2.87872 |  2.87872 |   3.01249 |                370 |            0.0963964  |
|            63 | S02b binned timewalk no covariate               | 3.20453 |  3.01995 |   3.43219 |                370 |            0.123423   |
|            63 | S02e binned current/rate selected power 0       | 3.20453 |  3.00087 |   3.43878 |                370 |            0.123423   |
|            63 | S02b global timewalk no covariate               | 1.54092 |  1.47551 |   1.59832 |                370 |            0.0171171  |
|            63 | S02e global current/rate selected power 0       | 1.54092 |  1.47984 |   1.61062 |                370 |            0.0171171  |
|            63 | S02 ML ridge                                    | 1.76984 |  1.61262 |   1.90256 |                370 |            0.0234234  |
|            65 | S02 train-best global template (template_phase) | 2.88915 |  2.63915 |   3.27718 |                 66 |            0.0505051  |
|            65 | S02b binned timewalk no covariate               | 3.4037  |  2.89453 |   4.0098  |                 66 |            0.141414   |
|            65 | S02e binned current/rate selected power 0       | 3.4037  |  2.8981  |   4.0201  |                 66 |            0.141414   |
|            65 | S02b global timewalk no covariate               | 1.63542 |  1.46243 |   1.91718 |                 66 |            0.00505051 |
|            65 | S02e global current/rate selected power 0       | 1.63542 |  1.47515 |   1.92971 |                 66 |            0.00505051 |
|            65 | S02 ML ridge                                    | 1.84611 |  1.45828 |   2.01789 |                 66 |            0          |

Run-block bootstrap over the seven held-out runs:

| method                                          |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:------------------------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| S02b global timewalk no covariate               |           1.65516 |  1.53341 |   1.84285 |              1.4719  |              2.18842 |
| S02e global current/rate selected power 0       |           1.65516 |  1.53023 |   1.8445  |              1.4719  |              2.18842 |
| S02 ML ridge                                    |           1.90549 |  1.82373 |   2.02608 |              1.76984 |              2.24243 |
| S02 train-best global template (template_phase) |           2.81023 |  2.71607 |   2.90263 |              2.6428  |              2.99232 |
| S02b binned timewalk no covariate               |           3.14849 |  2.77926 |   3.45593 |              2.12741 |              3.63793 |
| S02e binned current/rate selected power 0       |           3.14849 |  2.75413 |   3.46085 |              2.12741 |              3.63793 |

The current/rate drift term changes the amplitude-binned branch by `+0.000 ns` versus no covariate and the global-template branch by `+0.000 ns` versus no covariate on the run-block mean. The strongest traditional comparator is `S02b global timewalk no covariate` at `1.655 ns`; the ML ridge comparator averages `1.905 ns`.

## Leakage checks

|   heldout_run | check                                        |   value | pass   |
|--------------:|:---------------------------------------------|--------:|:-------|
|            58 | train_heldout_run_overlap                    | 0       | True   |
|            58 | train_heldout_event_id_overlap               | 0       | True   |
|            58 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            58 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            58 | covariates_derived_before_timing_labels      | 1       | True   |
|            58 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            58 | final_fit_train_rows_only                    | 1       | True   |
|            58 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            58 | binned_selected_shuffled_target_sigma68_ns   | 3.00567 | False  |
|            58 | global_selected_shuffled_target_sigma68_ns   | 3.04025 | True   |
|            58 | forbidden_heldout_oracle_binned_sigma68_ns   | 2.51266 | True   |
|            59 | train_heldout_run_overlap                    | 0       | True   |
|            59 | train_heldout_event_id_overlap               | 0       | True   |
|            59 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            59 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            59 | covariates_derived_before_timing_labels      | 1       | True   |
|            59 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            59 | final_fit_train_rows_only                    | 1       | True   |
|            59 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            59 | binned_selected_shuffled_target_sigma68_ns   | 5.41304 | True   |
|            59 | global_selected_shuffled_target_sigma68_ns   | 2.85787 | True   |
|            59 | forbidden_heldout_oracle_binned_sigma68_ns   | 3.78865 | False  |
|            60 | train_heldout_run_overlap                    | 0       | True   |
|            60 | train_heldout_event_id_overlap               | 0       | True   |
|            60 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            60 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            60 | covariates_derived_before_timing_labels      | 1       | True   |
|            60 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            60 | final_fit_train_rows_only                    | 1       | True   |
|            60 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            60 | binned_selected_shuffled_target_sigma68_ns   | 3.09826 | True   |
|            60 | global_selected_shuffled_target_sigma68_ns   | 2.71924 | True   |
|            60 | forbidden_heldout_oracle_binned_sigma68_ns   | 2.20856 | False  |
|            61 | train_heldout_run_overlap                    | 0       | True   |
|            61 | train_heldout_event_id_overlap               | 0       | True   |
|            61 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            61 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            61 | covariates_derived_before_timing_labels      | 1       | True   |
|            61 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            61 | final_fit_train_rows_only                    | 1       | True   |
|            61 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            61 | binned_selected_shuffled_target_sigma68_ns   | 2.92561 | False  |
|            61 | global_selected_shuffled_target_sigma68_ns   | 2.72416 | True   |
|            61 | forbidden_heldout_oracle_binned_sigma68_ns   | 2.39302 | True   |
|            62 | train_heldout_run_overlap                    | 0       | True   |
|            62 | train_heldout_event_id_overlap               | 0       | True   |
|            62 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            62 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            62 | covariates_derived_before_timing_labels      | 1       | True   |
|            62 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            62 | final_fit_train_rows_only                    | 1       | True   |
|            62 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            62 | binned_selected_shuffled_target_sigma68_ns   | 3.57238 | True   |
|            62 | global_selected_shuffled_target_sigma68_ns   | 3.01785 | True   |
|            62 | forbidden_heldout_oracle_binned_sigma68_ns   | 2.68415 | True   |
|            63 | train_heldout_run_overlap                    | 0       | True   |
|            63 | train_heldout_event_id_overlap               | 0       | True   |
|            63 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            63 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            63 | covariates_derived_before_timing_labels      | 1       | True   |
|            63 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            63 | final_fit_train_rows_only                    | 1       | True   |
|            63 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            63 | binned_selected_shuffled_target_sigma68_ns   | 4.51022 | True   |
|            63 | global_selected_shuffled_target_sigma68_ns   | 2.88209 | True   |
|            63 | forbidden_heldout_oracle_binned_sigma68_ns   | 3.672   | False  |
|            65 | train_heldout_run_overlap                    | 0       | True   |
|            65 | train_heldout_event_id_overlap               | 0       | True   |
|            65 | covariate_basis_contains_run_one_hot         | 0       | True   |
|            65 | covariate_basis_contains_chronological_run_z | 0       | True   |
|            65 | covariates_derived_before_timing_labels      | 1       | True   |
|            65 | covariate_basis_uses_heldout_targets         | 0       | True   |
|            65 | final_fit_train_rows_only                    | 1       | True   |
|            65 | normalized_waveform_exact_hash_overlap       | 0       | True   |
|            65 | binned_selected_shuffled_target_sigma68_ns   | 4.02347 | True   |
|            65 | global_selected_shuffled_target_sigma68_ns   | 2.84102 | True   |
|            65 | forbidden_heldout_oracle_binned_sigma68_ns   | 2.87299 | True   |

The forbidden-oracle rows are not production methods; they show how much held-out targets could move the binned metric if leaked. Non-oracle leakage checks pass: `False`.

## Conclusion

Pre-timing current/rate covariates do not rescue the S02d drift nuisance: train-run CV selects the zero-covariate branch in every fold, so the constrained current/rate basis is rejected rather than adopted. The global-template traditional comparator is the best mean held-out sigma68 in this split, while ML ridge is competitive but worse on the run-block mean. The shuffled-target failures are confined to the binned branch and are reported as instability diagnostics, not as evidence of train/held-out leakage.

## Follow-up tickets

No new follow-up ticket is proposed here; the obvious external-scaler follow-up already appears in prior S02e/S02d follow-up text, and this ROOT-only ticket has no additional calibrated rate source.

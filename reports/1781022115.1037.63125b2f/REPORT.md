# S02g: external scaler rate covariate audit

Ticket `1781022115.1037.63125b2f`. Worker `testbeam-laptop-3`.

## Reproduction first

The raw HRD-B ROOT gate was reproduced before any modeling: `reproduction_match_table.csv` matches the expected selected-pulse count with zero delta. The S02/S02b run-65 anchors were also rebuilt from raw ROOT:

| quantity                                       |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |            65 |                 2.88915 |                2.88915 | 0           | True   |
| S02 ML ridge                                   |            65 |                 1.84611 |                1.84611 | 7.54952e-15 | True   |
| S02b binned-template timewalk                  |            65 |                 3.4037  |                3.4037  | 2.08709e-10 | True   |
| S02b global-template timewalk                  |            65 |                 1.63542 |                1.63542 | 2.20047e-09 | True   |

## External metadata audit

I scanned the linked data mirror (`data -> /home/billy/ccb-data/extracted`), `/home/billy/ccb-data/raw`, and `/home/billy/ccb-data/docs` for scaler, spill-clock, DAQ live-time, detector-current, run-log, and metadata tokens, and inspected member names in the raw zip archives.

| quantity                                 |   value |
|:-----------------------------------------|--------:|
| filesystem_files_scanned                 |     220 |
| filesystem_external_metadata_candidates  |       0 |
| archive_members_scanned                  |     217 |
| archive_external_metadata_candidates     |       0 |
| non_root_document_files_seen             |       1 |
| calibrated_external_covariates_available |       0 |

No calibrated external spill-clock/scaler/live-time/current table is present in this mirror. The only non-ROOT document found is the existing analysis PDF, and the raw archives contain ROOT members rather than auxiliary log files. Therefore the S02e rerun uses the same pre-timing raw ROOT proxies (`TRIGGER`, `EVENTNO`, and amplitude-gate rates) plus the documented default current field; there is no external covariate to add.

## Run-held-out methods

The split is Sample II leave-one-run-out over runs `[58, 59, 60, 61, 62, 63, 65]`. Each fold fits templates, the traditional current/rate nuisance, and the ML ridge comparator on the other runs only. Event bootstrap CIs are reported per held-out run, and run-block bootstrap CIs summarize the seven held-out folds.

Grouped train-run CV for the current/rate nuisance:

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
|            62 | s02e_global_timewalk_drift1 | template_phase |             1 |              7.52932 |       3 |
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

Run-block bootstrap summary:

| method                                          |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:------------------------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| S02b global timewalk no covariate               |           1.65516 |  1.53341 |   1.84285 |              1.4719  |              2.18842 |
| S02e global current/rate selected power 0       |           1.65516 |  1.53023 |   1.8445  |              1.4719  |              2.18842 |
| S02 ML ridge                                    |           1.90549 |  1.82373 |   2.02608 |              1.76984 |              2.24243 |
| S02 train-best global template (template_phase) |           2.81023 |  2.71607 |   2.90263 |              2.6428  |              2.99232 |
| S02b binned timewalk no covariate               |           3.14849 |  2.77926 |   3.45593 |              2.12741 |              3.63793 |
| S02e binned current/rate selected power 0       |           3.14849 |  2.75413 |   3.46085 |              2.12741 |              3.63793 |

Best traditional result: `S02b global timewalk no covariate` at `1.655 ns` mean sigma68 (`1.533`, `1.843` run-block CI). ML ridge averages `1.905 ns`. The selected global current/rate branch changes the no-covariate global branch by `+0.000 ns`; the selected binned branch changes the binned no-covariate branch by `+0.000 ns`.

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

Non-oracle leakage checks pass: `False`. The two shuffled-target failures occur in the binned branch where train-CV already rejects covariate powers above zero, so I treat them as instability diagnostics rather than adopting that branch. The forbidden-oracle rows deliberately use held-out targets and are included only to bound how a leaking correction would behave.

## Conclusion

The requested external scaler/rate covariate source is absent from the current data mirror and raw archives, so there is no calibrated external covariate to add to S02e. Re-running S02e with the available pre-timing ROOT proxies again selects zero covariate power in every fold. The strong traditional global timewalk branch remains best on run-held-out mean sigma68, and the ML ridge comparator is worse but in the same scale. No follow-up ticket is appended because another external-source search would duplicate this audit unless new files are added to the mirror.

# S02d: leave-one-run-out run-drift nuisance scan over Sample II

Ticket `1781011483.1166.290e6be7`. Worker `testbeam-laptop-4`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts before modeling. Total selected pulses: `640737` with delta `0`.

The run-65 S02c anchor numbers were rebuilt from raw ROOT before the LORO scan:

| quantity                                       |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |            65 |                 2.88915 |                2.88915 | 0           | True   |
| S02 ML ridge                                   |            65 |                 1.84611 |                1.84611 | 7.54952e-15 | True   |
| S02b binned-template timewalk                  |            65 |                 3.4037  |                3.4037  | 2.08709e-10 | True   |
| S02b global-template timewalk                  |            65 |                 1.63542 |                1.63542 | 2.20047e-09 | True   |

## Method

The LORO runs are Sample II analysis runs `[58, 59, 60, 61, 62, 63, 65]`; run 64 remains calibration-only and is not used in the timing metric. For each fold, one run is held out, templates and timewalk/drift models are fit only on the other Sample II analysis runs, and CIs are event-level bootstraps inside that held-out run. The drift basis is the S02c train-only per-stave chronological `run_z`/`run_z^2` basis, with no run one-hot, event id, or held-out target features.

Grouped train-run CV selections by fold:

|   heldout_run | method                      | base_method    |   drift_order |   mean_cv_sigma68_ns |   folds |
|--------------:|:----------------------------|:---------------|--------------:|---------------------:|--------:|
|            58 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              3.08498 |       3 |
|            58 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              3.1018  |       3 |
|            58 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              3.17135 |       3 |
|            58 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.7507  |       3 |
|            58 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.7547  |       3 |
|            58 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.90467 |       3 |
|            59 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              3.21677 |       3 |
|            59 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              3.28358 |       3 |
|            59 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              3.38545 |       3 |
|            59 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.63422 |       3 |
|            59 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.69677 |       3 |
|            59 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.75977 |       3 |
|            60 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              2.54503 |       3 |
|            60 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              2.55793 |       3 |
|            60 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              2.58884 |       3 |
|            60 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.73054 |       3 |
|            60 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.73391 |       3 |
|            60 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.76409 |       3 |
|            61 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              2.939   |       3 |
|            61 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              2.95714 |       3 |
|            61 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              2.99413 |       3 |
|            61 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.68704 |       3 |
|            61 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.70556 |       3 |
|            61 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.72763 |       3 |
|            62 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              2.89376 |       3 |
|            62 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              2.93283 |       3 |
|            62 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              3.01338 |       3 |
|            62 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.72964 |       3 |
|            62 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.78442 |       3 |
|            62 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.89992 |       3 |
|            63 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              2.89888 |       3 |
|            63 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              2.92251 |       3 |
|            63 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              2.9711  |       3 |
|            63 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.73988 |       3 |
|            63 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.77584 |       3 |
|            63 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.83077 |       3 |
|            65 | s02d_binned_timewalk_drift0 | s02b_template  |             0 |              3.10247 |       3 |
|            65 | s02d_binned_timewalk_drift1 | s02b_template  |             1 |              3.10771 |       3 |
|            65 | s02d_binned_timewalk_drift2 | s02b_template  |             2 |              3.20923 |       3 |
|            65 | s02d_global_timewalk_drift0 | template_phase |             0 |              1.74655 |       3 |
|            65 | s02d_global_timewalk_drift1 | template_phase |             1 |              1.75993 |       3 |
|            65 | s02d_global_timewalk_drift2 | template_phase |             2 |              1.97954 |       3 |

## Held-out results

Per-run event bootstrap results:

|   heldout_run | method                                          |   value |   ci_low |   ci_high |   n_heldout_events |   tail_frac_abs_gt5ns |
|--------------:|:------------------------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
|            58 | S02 train-best global template (template_phase) | 2.6428  |  2.6428  |   2.77317 |                 73 |            0.0776256  |
|            58 | S02b binned timewalk no drift                   | 3.63484 |  3.12173 |   4.1626  |                 73 |            0.191781   |
|            58 | S02d binned selected drift                      | 3.63484 |  3.13085 |   4.07051 |                 73 |            0.191781   |
|            58 | S02b global timewalk no drift                   | 1.52279 |  1.26943 |   1.86821 |                 73 |            0.0228311  |
|            58 | S02d global selected drift                      | 1.52279 |  1.26444 |   1.87286 |                 73 |            0.0228311  |
|            58 | S02 ML ridge                                    | 1.91964 |  1.66413 |   2.17053 |                 73 |            0.0228311  |
|            59 | S02 train-best global template (template_phase) | 2.99232 |  2.87333 |   3.12333 |                763 |            0.0677152  |
|            59 | S02b binned timewalk no drift                   | 3.63793 |  3.47726 |   3.7773  |                763 |            0.158148   |
|            59 | S02d binned selected drift                      | 3.86253 |  3.70029 |   4.01407 |                763 |            0.173438   |
|            59 | S02b global timewalk no drift                   | 1.59676 |  1.54746 |   1.65551 |                763 |            0.0126693  |
|            59 | S02d global selected drift                      | 1.61463 |  1.5752  |   1.66641 |                763 |            0.0139799  |
|            59 | S02 ML ridge                                    | 1.88049 |  1.81319 |   1.95946 |                763 |            0.0192224  |
|            60 | S02 train-best global template (template_phase) | 2.66393 |  2.66393 |   2.7113  |                808 |            0.0944719  |
|            60 | S02b binned timewalk no drift                   | 2.12741 |  2.04226 |   2.20294 |                808 |            0.0383663  |
|            60 | S02d binned selected drift                      | 2.13066 |  2.04235 |   2.21086 |                808 |            0.0383663  |
|            60 | S02b global timewalk no drift                   | 1.4719  |  1.42758 |   1.51964 |                808 |            0.0107261  |
|            60 | S02d global selected drift                      | 1.47659 |  1.4319  |   1.52943 |                808 |            0.0107261  |
|            60 | S02 ML ridge                                    | 1.81993 |  1.73366 |   1.9036  |                808 |            0.0189769  |
|            61 | S02 train-best global template (template_phase) | 2.70351 |  2.70351 |   2.70351 |                933 |            0.0428725  |
|            61 | S02b binned timewalk no drift                   | 3.06904 |  2.91915 |   3.17575 |                933 |            0.110397   |
|            61 | S02d binned selected drift                      | 3.06904 |  2.9308  |   3.1805  |                933 |            0.110397   |
|            61 | S02b global timewalk no drift                   | 2.18842 |  2.09432 |   2.27266 |                933 |            0.0275098  |
|            61 | S02d global selected drift                      | 2.18842 |  2.08882 |   2.27403 |                933 |            0.0275098  |
|            61 | S02 ML ridge                                    | 2.24243 |  2.14452 |   2.33859 |                933 |            0.0214362  |
|            62 | S02 train-best global template (template_phase) | 2.90117 |  2.90117 |   3.02631 |                807 |            0.0929368  |
|            62 | S02b binned timewalk no drift                   | 2.962   |  2.82809 |   3.08585 |                807 |            0.0912846  |
|            62 | S02d binned selected drift                      | 2.962   |  2.83439 |   3.08593 |                807 |            0.0912846  |
|            62 | S02b global timewalk no drift                   | 1.62995 |  1.57995 |   1.67559 |                807 |            0.0111524  |
|            62 | S02d global selected drift                      | 1.62995 |  1.5786  |   1.67422 |                807 |            0.0111524  |
|            62 | S02 ML ridge                                    | 1.86001 |  1.7797  |   1.93299 |                807 |            0.0144568  |
|            63 | S02 train-best global template (template_phase) | 2.87872 |  2.87872 |   3.01249 |                370 |            0.0963964  |
|            63 | S02b binned timewalk no drift                   | 3.20453 |  3.00121 |   3.43995 |                370 |            0.123423   |
|            63 | S02d binned selected drift                      | 3.20453 |  3.00609 |   3.41925 |                370 |            0.123423   |
|            63 | S02b global timewalk no drift                   | 1.54092 |  1.47909 |   1.60114 |                370 |            0.0171171  |
|            63 | S02d global selected drift                      | 1.54092 |  1.47547 |   1.60861 |                370 |            0.0171171  |
|            63 | S02 ML ridge                                    | 1.76984 |  1.61076 |   1.90108 |                370 |            0.0234234  |
|            65 | S02 train-best global template (template_phase) | 2.88915 |  2.63915 |   3.27718 |                 66 |            0.0505051  |
|            65 | S02b binned timewalk no drift                   | 3.4037  |  2.85562 |   4.12878 |                 66 |            0.141414   |
|            65 | S02d binned selected drift                      | 3.4037  |  2.84333 |   3.96246 |                 66 |            0.141414   |
|            65 | S02b global timewalk no drift                   | 1.63542 |  1.50061 |   1.90515 |                 66 |            0.00505051 |
|            65 | S02d global selected drift                      | 1.63542 |  1.47528 |   1.90719 |                 66 |            0.00505051 |
|            65 | S02 ML ridge                                    | 1.84611 |  1.4655  |   2.02882 |                 66 |            0          |

Run-block bootstrap over the seven held-out runs:

| method                                          |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:------------------------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| S02b global timewalk no drift                   |           1.65516 |  1.53211 |   1.84275 |              1.4719  |              2.18842 |
| S02d global selected drift                      |           1.65839 |  1.53698 |   1.84387 |              1.47659 |              2.18842 |
| S02 ML ridge                                    |           1.90549 |  1.82415 |   2.0254  |              1.76984 |              2.24243 |
| S02 train-best global template (template_phase) |           2.81023 |  2.71624 |   2.90285 |              2.6428  |              2.99232 |
| S02b binned timewalk no drift                   |           3.14849 |  2.75082 |   3.46085 |              2.12741 |              3.63793 |
| S02d binned selected drift                      |           3.18104 |  2.77482 |   3.53776 |              2.13066 |              3.86253 |

The amplitude-binned selected drift branch does not improve versus no drift on the run-block mean (`3.181` ns vs `3.148` ns). The strongest traditional branch is still the global-template timewalk with no drift (`1.655` ns), while the ML ridge comparator averages `1.905` ns.

## Leakage checks

|   heldout_run | check                                      |   value | pass   |
|--------------:|:-------------------------------------------|--------:|:-------|
|            58 | train_heldout_run_overlap                  | 0       | True   |
|            58 | train_heldout_event_id_overlap             | 0       | True   |
|            58 | drift_basis_contains_run_one_hot           | 0       | True   |
|            58 | drift_basis_uses_heldout_targets           | 0       | True   |
|            58 | final_fit_train_rows_only                  | 1       | True   |
|            58 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            58 | binned_selected_shuffled_target_sigma68_ns | 3.00567 | False  |
|            58 | global_selected_shuffled_target_sigma68_ns | 3.04025 | True   |
|            58 | forbidden_heldout_oracle_binned_sigma68_ns | 2.51266 | True   |
|            59 | train_heldout_run_overlap                  | 0       | True   |
|            59 | train_heldout_event_id_overlap             | 0       | True   |
|            59 | drift_basis_contains_run_one_hot           | 0       | True   |
|            59 | drift_basis_uses_heldout_targets           | 0       | True   |
|            59 | final_fit_train_rows_only                  | 1       | True   |
|            59 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            59 | binned_selected_shuffled_target_sigma68_ns | 4.9127  | True   |
|            59 | global_selected_shuffled_target_sigma68_ns | 2.96166 | True   |
|            59 | forbidden_heldout_oracle_binned_sigma68_ns | 3.78865 | True   |
|            60 | train_heldout_run_overlap                  | 0       | True   |
|            60 | train_heldout_event_id_overlap             | 0       | True   |
|            60 | drift_basis_contains_run_one_hot           | 0       | True   |
|            60 | drift_basis_uses_heldout_targets           | 0       | True   |
|            60 | final_fit_train_rows_only                  | 1       | True   |
|            60 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            60 | binned_selected_shuffled_target_sigma68_ns | 3.17026 | True   |
|            60 | global_selected_shuffled_target_sigma68_ns | 2.60299 | True   |
|            60 | forbidden_heldout_oracle_binned_sigma68_ns | 2.20856 | False  |
|            61 | train_heldout_run_overlap                  | 0       | True   |
|            61 | train_heldout_event_id_overlap             | 0       | True   |
|            61 | drift_basis_contains_run_one_hot           | 0       | True   |
|            61 | drift_basis_uses_heldout_targets           | 0       | True   |
|            61 | final_fit_train_rows_only                  | 1       | True   |
|            61 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            61 | binned_selected_shuffled_target_sigma68_ns | 2.92561 | False  |
|            61 | global_selected_shuffled_target_sigma68_ns | 2.72416 | True   |
|            61 | forbidden_heldout_oracle_binned_sigma68_ns | 2.39302 | True   |
|            62 | train_heldout_run_overlap                  | 0       | True   |
|            62 | train_heldout_event_id_overlap             | 0       | True   |
|            62 | drift_basis_contains_run_one_hot           | 0       | True   |
|            62 | drift_basis_uses_heldout_targets           | 0       | True   |
|            62 | final_fit_train_rows_only                  | 1       | True   |
|            62 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            62 | binned_selected_shuffled_target_sigma68_ns | 3.57238 | True   |
|            62 | global_selected_shuffled_target_sigma68_ns | 3.01785 | True   |
|            62 | forbidden_heldout_oracle_binned_sigma68_ns | 2.68415 | True   |
|            63 | train_heldout_run_overlap                  | 0       | True   |
|            63 | train_heldout_event_id_overlap             | 0       | True   |
|            63 | drift_basis_contains_run_one_hot           | 0       | True   |
|            63 | drift_basis_uses_heldout_targets           | 0       | True   |
|            63 | final_fit_train_rows_only                  | 1       | True   |
|            63 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            63 | binned_selected_shuffled_target_sigma68_ns | 4.51022 | True   |
|            63 | global_selected_shuffled_target_sigma68_ns | 2.88209 | True   |
|            63 | forbidden_heldout_oracle_binned_sigma68_ns | 3.672   | False  |
|            65 | train_heldout_run_overlap                  | 0       | True   |
|            65 | train_heldout_event_id_overlap             | 0       | True   |
|            65 | drift_basis_contains_run_one_hot           | 0       | True   |
|            65 | drift_basis_uses_heldout_targets           | 0       | True   |
|            65 | final_fit_train_rows_only                  | 1       | True   |
|            65 | normalized_waveform_exact_hash_overlap     | 0       | True   |
|            65 | binned_selected_shuffled_target_sigma68_ns | 4.02347 | True   |
|            65 | global_selected_shuffled_target_sigma68_ns | 2.84102 | True   |
|            65 | forbidden_heldout_oracle_binned_sigma68_ns | 2.87299 | True   |

The forbidden-oracle rows are not production methods; they show that held-out targets could move the binned metric if leaked. Non-oracle leakage checks pass: `False`.

The failed non-oracle rows are shuffled-target controls on the binned branch, not train/held-out overlap or feature contamination. I therefore do not use the binned selected-drift improvement as an adoption claim; it is reported as an instability diagnostic.

## Conclusion

Run 65 is not the whole story: the no-drift global-template conventional method is the most stable traditional method across Sample II LORO folds, while the S02c drift basis generally fails to produce a robust amplitude-binned rescue. ML remains competitive, but its advantage is fold-dependent rather than a uniformly dramatic improvement.

## Follow-up tickets

- S02e: constrain run drift with pre-timing detector-current or trigger-rate covariates and rerun the same Sample II LORO leakage controls.
- S02f: repeat S02d with run 64 included only as a calibration-source stress test, never as a held-out analysis target.

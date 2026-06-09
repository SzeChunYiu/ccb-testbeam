# S02e: current/rate-constrained drift in amplitude-binned template/timewalk closure

Ticket `1781011483.1234.10c43e9a`. Worker `testbeam-laptop-1`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts before modeling. Total selected pulses: `640737` with delta `0`.

The S02/S02b reference numbers were rebuilt from raw ROOT before the S02e covariate drift test:

| quantity                                       |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |                 2.88915 |                2.88915 | 0           | True   |
| S02 ML ridge                                   |                 1.84611 |                1.84611 | 7.54952e-15 | True   |
| S02b binned-template timewalk                  |                 3.4037  |                3.4037  | 2.08709e-10 | True   |
| S02b global-template timewalk                  |                 1.63542 |                1.63542 | 2.20047e-09 | True   |

## Method

The drift nuisance is a train-only, low-dimensional current/rate basis. It uses documented beam current plus raw-derived trigger/event-density and amplitude-rate proxies (`trigger_entry_density`, `entries_per_eventno`, `selected_multiplicity_per_event`, `downstream_allhit_fraction`). Each covariate is centered/scaled using only train runs `[58, 59, 60, 61, 62, 63]` and evaluated once on held-out run `[65]`. There is no chronological `run_z`, no run one-hot column, no event id column, and no pairwise timing target in the covariate derivation.

Grouped train-run CV selected `S02b binned timewalk no covariate` for the amplitude-binned branch and `S02b global timewalk no covariate` for the global-template branch:

| method                      | base_method    |   drift_order |   mean_cv_sigma68_ns |   folds |   total_pair_residuals |
|:----------------------------|:---------------|--------------:|---------------------:|--------:|-----------------------:|
| s02e_binned_timewalk_drift0 | s02b_template  |             0 |              3.10247 |       3 |                  11262 |
| s02e_binned_timewalk_drift1 | s02b_template  |             1 |              3.57683 |       3 |                  11262 |
| s02e_binned_timewalk_drift2 | s02b_template  |             2 |             23.9876  |       3 |                  11262 |
| s02e_global_timewalk_drift0 | template_phase |             0 |              1.74655 |       3 |                  11262 |
| s02e_global_timewalk_drift1 | template_phase |             1 |              2.7248  |       3 |                  11262 |
| s02e_global_timewalk_drift2 | template_phase |             2 |             21.6394  |       3 |                  11262 |

## Held-out result

CIs are event-level bootstrap intervals over held-out events.

| method                            |   value |   ci_low |   ci_high |   n_heldout_events |   full_rms_ns |   tail_frac_abs_gt5ns |
|:----------------------------------|--------:|---------:|----------:|-------------------:|--------------:|----------------------:|
| S02 global template               | 2.88915 |  2.63915 |   3.27718 |                 66 |       2.57669 |            0.0505051  |
| S02b binned timewalk no covariate | 3.4037  |  2.91807 |   4.02445 |                 66 |       3.72618 |            0.141414   |
| S02b global timewalk no covariate | 1.63542 |  1.46235 |   1.91057 |                 66 |       1.77195 |            0.00505051 |
| S02 ML ridge                      | 1.84611 |  1.46754 |   2.03514 |                 66 |       1.7098  |            0          |

By run:

|   run | method                            |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|------:|:----------------------------------|-------------:|--------------:|----------------------:|-------------------:|
|    65 | S02 global template               |      2.88915 |       2.57669 |            0.0505051  |                198 |
|    65 | S02b binned timewalk no covariate |      3.4037  |       3.72618 |            0.141414   |                198 |
|    65 | S02b global timewalk no covariate |      1.63542 |       1.77195 |            0.00505051 |                198 |
|    65 | S02 ML ridge                      |      1.84611 |       1.7098  |            0          |                198 |

For the amplitude-binned branch, the selected covariate model changes sigma68 by `+0.000 ns` versus the no-covariate branch, so the covariate drift term `does not improve`. For the stronger global-template traditional branch, the selected covariate model changes sigma68 by `+0.000 ns`. The S02 ML ridge comparator is `1.846 ns`.

## Leakage checks

| check                                        |   value | pass   |
|:---------------------------------------------|--------:|:-------|
| train_heldout_run_overlap                    | 0       | True   |
| train_heldout_event_id_overlap               | 0       | True   |
| covariate_basis_contains_run_one_hot         | 0       | True   |
| covariate_basis_contains_chronological_run_z | 0       | True   |
| covariates_derived_before_timing_labels      | 1       | True   |
| covariate_basis_uses_heldout_targets         | 0       | True   |
| final_fit_train_rows_only                    | 1       | True   |
| normalized_waveform_exact_hash_overlap       | 0       | True   |
| binned_selected_shuffled_target_sigma68_ns   | 3.96323 | True   |
| global_selected_shuffled_target_sigma68_ns   | 2.86503 | True   |
| forbidden_heldout_oracle_binned_sigma68_ns   | 2.87299 | True   |

The forbidden-oracle row is intentionally not a production method: it uses held-out targets to show how much a leaking run-specific correction could move the metric. The reported S02e models do not use that information.

## Conclusion

A train-only current/rate-constrained drift nuisance tests whether the S02c chronological drift result was just a proxy for detector conditions. The main amplitude-binned branch is compared against its no-covariate version on held-out run 65, while the global-template traditional closure remains the stronger conventional comparator.

## Follow-up tickets

- S02f: repeat current/rate-constrained drift with leave-one-run-out over all Sample-II runs, not only run 65.
- S02g: add an external spill-clock or scaler source if available; current Sample-II ROOT counters provide only trigger-density proxies, not calibrated wall-clock rates.

# S02e: selector-semantics LORO current/rate strata

Ticket `1781029327.1448.72f21509`. Worker `testbeam-laptop-1`.

## Reproduction first

The raw ROOT selector gate was rerun before any timing model. S00 median-first-four and S00a dynamic-range counts reproduce exactly:

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 median-first-four selected pulses |         640737 |       640737 |       0 |           0 | True   |
| S00a dynamic-range equivalent count   |         706373 |       706373 |       0 |           0 | True   |
| Dynamic-only excess pulses            |          65636 |        65636 |       0 |           0 | True   |
| Median-only pulses                    |              0 |            0 |       0 |           0 | True   |

## Method

Held-out runs are `[58, 59, 60, 61, 62, 63, 65]`. Detector current is constant in the Sample-II docs, so the rate-family split uses the pre-label raw proxy `downstream_allhit_fraction`. Train runs are selected by same current/rate stratum first, then expanded to the nearest raw-rate neighbors only when needed to keep at least `3` train runs for grouped CV and ML.

|   heldout_run | heldout_stratum   | stratum_basis              |   heldout_stratum_value | same_stratum_train_runs   | train_runs   |   n_train_runs | expanded_to_min_train_runs   |
|--------------:|:------------------|:---------------------------|------------------------:|:--------------------------|:-------------|---------------:|:-----------------------------|
|            58 | low_rate          | downstream_allhit_fraction |              0.00213819 | 63 65                     | 59 63 65     |              3 | True                         |
|            59 | mid_rate          | downstream_allhit_fraction |              0.0180365  | 62                        | 60 61 62     |              3 | True                         |
|            60 | high_rate         | downstream_allhit_fraction |              0.0223984  | 61                        | 59 61 62     |              3 | True                         |
|            61 | high_rate         | downstream_allhit_fraction |              0.0255372  | 60                        | 59 60 62     |              3 | True                         |
|            62 | mid_rate          | downstream_allhit_fraction |              0.0214719  | 59                        | 59 60 61     |              3 | True                         |
|            63 | low_rate          | downstream_allhit_fraction |              0.0099919  | 58 65                     | 58 59 65     |              3 | True                         |
|            65 | low_rate          | downstream_allhit_fraction |              0.00171768 | 58 63                     | 58 59 63     |              3 | True                         |

For every selector and held-out run, templates, amplitude-binned templates, current/rate timewalk closures, and the Ridge ML comparator are refit only on the selected train runs. Event-level CIs are bootstrapped inside folds; selector deltas use a paired run-block bootstrap across held-out runs.

Downstream all-hit event counts by selector and run are in `loro_selector_pulse_counts_by_run.csv`; totals:

| selector      |   total_events |   total_pulses |
|:--------------|---------------:|---------------:|
| dynamic_range |           4492 |          13476 |
| median_first4 |           3820 |          11460 |

## Results

Headline per-run held-out results:

| selector      |   heldout_run | method                            |   value |   ci_low |   ci_high |   n_heldout_events |   tail_frac_abs_gt5ns |
|:--------------|--------------:|:----------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| median_first4 |            58 | S02b global timewalk no covariate | 1.53345 |  1.30436 |   1.94578 |                 73 |            0.0228311  |
| median_first4 |            58 | S02e global current/rate selected | 1.53345 |  1.33412 |   1.94397 |                 73 |            0.0228311  |
| median_first4 |            58 | S02 ML ridge                      | 1.82682 |  1.67401 |   2.16426 |                 73 |            0.0182648  |
| median_first4 |            59 | S02b global timewalk no covariate | 1.58158 |  1.53513 |   1.63442 |                763 |            0.013543   |
| median_first4 |            59 | S02e global current/rate selected | 1.58158 |  1.53599 |   1.6335  |                763 |            0.013543   |
| median_first4 |            59 | S02 ML ridge                      | 1.86106 |  1.77264 |   1.93545 |                763 |            0.0187855  |
| median_first4 |            60 | S02b global timewalk no covariate | 1.47009 |  1.42483 |   1.5302  |                808 |            0.0107261  |
| median_first4 |            60 | S02e global current/rate selected | 1.47009 |  1.42578 |   1.52797 |                808 |            0.0107261  |
| median_first4 |            60 | S02 ML ridge                      | 1.80346 |  1.70523 |   1.88377 |                808 |            0.0189769  |
| median_first4 |            61 | S02b global timewalk no covariate | 2.18828 |  2.08278 |   2.27473 |                933 |            0.026438   |
| median_first4 |            61 | S02e global current/rate selected | 2.18828 |  2.07777 |   2.2691  |                933 |            0.026438   |
| median_first4 |            61 | S02 ML ridge                      | 2.20593 |  2.10844 |   2.28514 |                933 |            0.021079   |
| median_first4 |            62 | S02b global timewalk no covariate | 1.60696 |  1.54757 |   1.64869 |                807 |            0.0111524  |
| median_first4 |            62 | S02e global current/rate selected | 1.60696 |  1.55039 |   1.65425 |                807 |            0.0111524  |
| median_first4 |            62 | S02 ML ridge                      | 1.83569 |  1.75749 |   1.91429 |                807 |            0.0140438  |
| median_first4 |            63 | S02b global timewalk no covariate | 1.57034 |  1.49199 |   1.66216 |                370 |            0.018018   |
| median_first4 |            63 | S02e global current/rate selected | 1.57034 |  1.48116 |   1.66601 |                370 |            0.018018   |
| median_first4 |            63 | S02 ML ridge                      | 1.77046 |  1.63759 |   1.92702 |                370 |            0.0189189  |
| median_first4 |            65 | S02b global timewalk no covariate | 1.85113 |  1.56452 |   2.10312 |                 66 |            0.00505051 |
| median_first4 |            65 | S02e global current/rate selected | 1.85113 |  1.56114 |   2.08912 |                 66 |            0.00505051 |
| median_first4 |            65 | S02 ML ridge                      | 1.77449 |  1.40938 |   1.97203 |                 66 |            0          |
| dynamic_range |            58 | S02b global timewalk no covariate | 1.64371 |  1.49928 |   1.88388 |                 90 |            0.0333333  |
| dynamic_range |            58 | S02e global current/rate selected | 1.64371 |  1.49696 |   1.88713 |                 90 |            0.0333333  |
| dynamic_range |            58 | S02 ML ridge                      | 2.30923 |  1.82261 |   2.80575 |                 90 |            0.0555556  |
| dynamic_range |            59 | S02b global timewalk no covariate | 1.80672 |  1.74648 |   1.88701 |                900 |            0.032963   |
| dynamic_range |            59 | S02e global current/rate selected | 1.80672 |  1.75384 |   1.88592 |                900 |            0.032963   |
| dynamic_range |            59 | S02 ML ridge                      | 2.19272 |  2.03986 |   2.3072  |                900 |            0.0514815  |
| dynamic_range |            60 | S02b global timewalk no covariate | 1.63438 |  1.58232 |   1.68105 |                955 |            0.025829   |
| dynamic_range |            60 | S02e global current/rate selected | 1.63438 |  1.58038 |   1.68142 |                955 |            0.025829   |
| dynamic_range |            60 | S02 ML ridge                      | 2.23486 |  2.11326 |   2.36421 |                955 |            0.0537522  |
| dynamic_range |            61 | S02b global timewalk no covariate | 2.25275 |  2.15573 |   2.33548 |               1075 |            0.0443411  |
| dynamic_range |            61 | S02e global current/rate selected | 2.25275 |  2.15871 |   2.33371 |               1075 |            0.0443411  |
| dynamic_range |            61 | S02 ML ridge                      | 2.28545 |  2.19343 |   2.40114 |               1075 |            0.052093   |
| dynamic_range |            62 | S02b global timewalk no covariate | 1.82762 |  1.76774 |   1.91688 |                941 |            0.0350691  |
| dynamic_range |            62 | S02e global current/rate selected | 1.82762 |  1.76351 |   1.91199 |                941 |            0.0350691  |
| dynamic_range |            62 | S02 ML ridge                      | 2.20118 |  2.08688 |   2.34234 |                941 |            0.0421537  |
| dynamic_range |            63 | S02b global timewalk no covariate | 1.63601 |  1.53872 |   1.72974 |                441 |            0.0234316  |
| dynamic_range |            63 | S02e global current/rate selected | 1.63601 |  1.53913 |   1.72671 |                441 |            0.0234316  |
| dynamic_range |            63 | S02 ML ridge                      | 2.23761 |  1.99328 |   2.44623 |                441 |            0.0634921  |
| dynamic_range |            65 | S02b global timewalk no covariate | 1.9111  |  1.65697 |   2.02945 |                 90 |            0.0222222  |
| dynamic_range |            65 | S02e global current/rate selected | 1.9111  |  1.67398 |   2.02815 |                 90 |            0.0222222  |
| dynamic_range |            65 | S02 ML ridge                      | 2.60678 |  2.05725 |   3.19271 |                 90 |            0.0925926  |

Headline run-block summary:

| selector      | method                            |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:--------------|:----------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| dynamic_range | S02 ML ridge                      |           2.29541 |  2.22043 |   2.4107  |              2.19272 |              2.60678 |
| median_first4 | S02 ML ridge                      |           1.86827 |  1.79369 |   1.9877  |              1.77046 |              2.20593 |
| dynamic_range | S02b global timewalk no covariate |           1.81604 |  1.68674 |   1.98817 |              1.63438 |              2.25275 |
| median_first4 | S02b global timewalk no covariate |           1.68598 |  1.54326 |   1.87162 |              1.47009 |              2.18828 |
| dynamic_range | S02e global current/rate selected |           1.81604 |  1.68651 |   1.98188 |              1.63438 |              2.25275 |
| median_first4 | S02e global current/rate selected |           1.68598 |  1.5378  |   1.87143 |              1.47009 |              2.18828 |

Paired dynamic-range minus median-first-four run-block deltas:

| method                            |   dynamic_minus_median_mean_ns |    ci_low |   ci_high |   min_run_delta_ns |   max_run_delta_ns |
|:----------------------------------|-------------------------------:|----------:|----------:|-------------------:|-------------------:|
| S02b global timewalk no covariate |                       0.130065 | 0.0836183 |  0.181598 |          0.0599659 |           0.22514  |
| S02e global current/rate selected |                       0.130065 | 0.0839825 |  0.182576 |          0.0599659 |           0.22514  |
| S02 ML ridge                      |                       0.427135 | 0.276338  |  0.586838 |          0.0795201 |           0.832295 |

The strong traditional method (`S02b global timewalk no covariate`) has dynamic-minus-median delta `+0.130 ns` [+0.084, +0.182]. The current/rate selected traditional branch has delta `+0.130 ns` [+0.084, +0.183]. The ML comparator has delta `+0.427 ns` [+0.276, +0.587].

## Leakage checks

Failed non-oracle checks:

| selector      |   heldout_run | check                                      |   value | pass   |
|:--------------|--------------:|:-------------------------------------------|--------:|:-------|
| median_first4 |            61 | binned_selected_shuffled_target_sigma68_ns | 3.10003 | False  |
| dynamic_range |            58 | binned_selected_shuffled_target_sigma68_ns | 3.93768 | False  |
| dynamic_range |            59 | binned_selected_shuffled_target_sigma68_ns | 4.44028 | False  |
| dynamic_range |            60 | binned_selected_shuffled_target_sigma68_ns | 3.41295 | False  |
| dynamic_range |            61 | binned_selected_shuffled_target_sigma68_ns | 3.25814 | False  |
| dynamic_range |            62 | binned_selected_shuffled_target_sigma68_ns | 3.93485 | False  |
| dynamic_range |            63 | binned_selected_shuffled_target_sigma68_ns | 3.99465 | False  |
| dynamic_range |            65 | binned_selected_shuffled_target_sigma68_ns | 4.02757 | False  |

All non-oracle leakage checks pass: `False`. Headline-method leakage checks pass after excluding the non-adopted binned diagnostic branch: `True`. The forbidden-oracle rows are deliberate held-out-target probes and are not production methods. Shuffled-target failures, if present, are treated as instability diagnostics rather than adoption evidence.

## Conclusion

Current/rate-family matching does not turn dynamic-range selector semantics into a timing gain. Under run-disjoint refits, dynamic-range selection worsens the strong traditional branch by `0.130 ns`, the current/rate-selected traditional branch by `0.130 ns`, and the ML branch by `0.427 ns` on paired run-block means. The result supports keeping selector semantics as a controlled nuisance rather than adopting the dynamic-range gate for timing.

## Follow-up tickets

No new follow-up ticket is proposed; external-scaler and selector-count CI follow-ups already exist in prior S02/S00 reports.

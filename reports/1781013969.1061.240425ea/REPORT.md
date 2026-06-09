# S16f: pre-trigger contamination veto versus timing tails

Ticket `1781013969.1061.240425ea`. Worker `testbeam-laptop-3`.

## Reproduction first

Raw ROOT was read from `h101/HRDv` before timing-tail labels or veto models were built. The S00 B-stave selected-pulse gate again reproduces exactly:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S16f all-four-stave event gate (`B2/B4/B6/B8` each with median-baseline `A > 1000 ADC`) gives:

| run   |   all_four_selected_events |
|:------|---------------------------:|
| 58    |                         72 |
| 59    |                        749 |
| 60    |                        802 |
| 61    |                        925 |
| 62    |                        798 |
| 63    |                        365 |
| 65    |                         63 |
| total |                       3774 |

## Method

Every Sample-II analysis run `[58, 59, 60, 61, 62, 63, 65]` is held out once. For each fold, S02 global-template timing and the S02b-style timewalk closure are rebuilt from the other runs only. Tail labels are event-level: an event is a tail if any B4/B6/B8 pair residual differs from the train-run median by more than `5.0` ns.

The traditional veto is a train-chosen threshold on a hand-built early-sample proxy score, `log1p(max line3 residual) + 0.5*log1p(max range)`. The ML veto is balanced logistic regression on B2/B4/B6/B8 early-sample proxy terms only. Neither method sees run id, event id, timing values, residuals, or tail labels as features.

## Held-out LORO result

|   heldout_run | method                           |   n_heldout_events |   n_heldout_tail_events |   tail_capture_efficiency |   tail_capture_efficiency_ci_low |   tail_capture_efficiency_ci_high |   veto_fraction |   precision |   score_auc |   kept_pair_sigma68_ns |   kept_tail_frac_abs_gt5ns |
|--------------:|:---------------------------------|-------------------:|------------------------:|--------------------------:|---------------------------------:|----------------------------------:|----------------:|------------:|------------:|-----------------------:|---------------------------:|
|            58 | no_veto_s02b_timewalk            |                 72 |                       3 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                1.52254 |                 0.0277778  |
|            58 | traditional_proxy_threshold_veto |                 72 |                       3 |                  0.333333 |                        0         |                          1        |        0.208333 |   0.0666667 |    0.603865 |                1.36616 |                 0.0233918  |
|            58 | ml_logistic_proxy_veto           |                 72 |                       3 |                  0.333333 |                        0         |                          1        |        0.180556 |   0.0769231 |    0.811594 |                1.46697 |                 0.0225989  |
|            58 | ml_shuffled_label_control        |                 72 |                       3 |                  0        |                        0         |                          0        |        0.222222 |   0         |    0.352657 |                1.57217 |                 0.0357143  |
|            59 | no_veto_s02b_timewalk            |                749 |                      18 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                1.59736 |                 0.0137962  |
|            59 | traditional_proxy_threshold_veto |                749 |                      18 |                  0.333333 |                        0.117647  |                          0.55     |        0.315087 |   0.0254237 |    0.44642  |                1.63508 |                 0.0116959  |
|            59 | ml_logistic_proxy_veto           |                749 |                      18 |                  0.388889 |                        0.142857  |                          0.600278 |        0.296395 |   0.0315315 |    0.569387 |                1.64098 |                 0.0101202  |
|            59 | ml_shuffled_label_control        |                749 |                      18 |                  0.277778 |                        0.0588235 |                          0.5      |        0.233645 |   0.0285714 |    0.585879 |                1.64183 |                 0.0116144  |
|            60 | no_veto_s02b_timewalk            |                802 |                      19 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                1.48672 |                 0.0128845  |
|            60 | traditional_proxy_threshold_veto |                802 |                      19 |                  0.157895 |                        0         |                          0.352941 |        0.239401 |   0.015625  |    0.521274 |                1.44279 |                 0.0136612  |
|            60 | ml_logistic_proxy_veto           |                802 |                      19 |                  0.578947 |                        0.333333  |                          0.800238 |        0.27182  |   0.0504587 |    0.658197 |                1.48722 |                 0.00684932 |
|            60 | ml_shuffled_label_control        |                802 |                      19 |                  0.526316 |                        0.307609  |                          0.764819 |        0.206983 |   0.060241  |    0.659071 |                1.46114 |                 0.00733753 |
|            61 | no_veto_s02b_timewalk            |                925 |                      44 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                2.13175 |                 0.0241441  |
|            61 | traditional_proxy_threshold_veto |                925 |                      44 |                  0.181818 |                        0.0769231 |                          0.3      |        0.204324 |   0.042328  |    0.494441 |                2.30495 |                 0.0226449  |
|            61 | ml_logistic_proxy_veto           |                925 |                      44 |                  0.409091 |                        0.263158  |                          0.560063 |        0.225946 |   0.0861244 |    0.638195 |                2.07719 |                 0.018622   |
|            61 | ml_shuffled_label_control        |                925 |                      44 |                  0.295455 |                        0.166591  |                          0.433983 |        0.285405 |   0.0492424 |    0.489114 |                2.19567 |                 0.0237015  |
|            62 | no_veto_s02b_timewalk            |                798 |                      17 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                1.59531 |                 0.0112782  |
|            62 | traditional_proxy_threshold_veto |                798 |                      17 |                  0.470588 |                        0.227146  |                          0.6925   |        0.241855 |   0.0414508 |    0.632296 |                1.61883 |                 0.0077135  |
|            62 | ml_logistic_proxy_veto           |                798 |                      17 |                  0.352941 |                        0.111111  |                          0.6      |        0.290727 |   0.0258621 |    0.488966 |                1.59453 |                 0.0106007  |
|            62 | ml_shuffled_label_control        |                798 |                      17 |                  0.235294 |                        0.0588235 |                          0.454545 |        0.264411 |   0.0189573 |    0.430293 |                1.61265 |                 0.0113572  |
|            63 | no_veto_s02b_timewalk            |                365 |                      13 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                1.52441 |                 0.0182648  |
|            63 | traditional_proxy_threshold_veto |                365 |                      13 |                  0.307692 |                        0.0666667 |                          0.6      |        0.328767 |   0.0333333 |    0.560424 |                1.56604 |                 0.0190476  |
|            63 | ml_logistic_proxy_veto           |                365 |                      13 |                  0.461538 |                        0.176225  |                          0.75     |        0.249315 |   0.0659341 |    0.609484 |                1.5095  |                 0.0121655  |
|            63 | ml_shuffled_label_control        |                365 |                      13 |                  0.461538 |                        0.2       |                          0.75     |        0.30411  |   0.0540541 |    0.597247 |                1.58252 |                 0.0144357  |
|            65 | no_veto_s02b_timewalk            |                 63 |                       0 |                  0        |                      nan         |                        nan        |        0        |   0         |  nan        |                1.59677 |                 0          |
|            65 | traditional_proxy_threshold_veto |                 63 |                       0 |                  0        |                        0         |                          0        |        0.142857 |   0         |  nan        |                1.52477 |                 0          |
|            65 | ml_logistic_proxy_veto           |                 63 |                       0 |                  0        |                        0         |                          0        |        0.31746  |   0         |  nan        |                1.63928 |                 0          |
|            65 | ml_shuffled_label_control        |                 63 |                       0 |                  0        |                        0         |                          0        |        0.253968 |   0         |  nan        |                1.64151 |                 0          |

Pooled held-out summary:

| method                           |   pooled_tail_capture_efficiency |   pooled_veto_fraction |   pooled_precision |   pooled_clean_keep_efficiency |   mean_fold_auc |   n_pooled_events |   n_pooled_tail_events |
|:---------------------------------|---------------------------------:|-----------------------:|-------------------:|-------------------------------:|----------------:|------------------:|-----------------------:|
| ml_logistic_proxy_veto           |                         0.429825 |               0.266296 |          0.0487562 |                       0.738798 |        0.629304 |              3774 |                    114 |
| ml_shuffled_label_control        |                         0.333333 |               0.254107 |          0.0396246 |                       0.748361 |        0.519043 |              3774 |                    114 |
| traditional_proxy_threshold_veto |                         0.263158 |               0.252782 |          0.0314465 |                       0.747541 |        0.54312  |              3774 |                    114 |

## Leakage checks

| check                                                     |    value | pass   |     actual |
|:----------------------------------------------------------|---------:|:-------|-----------:|
| fold_58_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_58_train_heldout_event_overlap                       | 0        | True   | nan        |
| fold_59_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_59_train_heldout_event_overlap                       | 0        | True   | nan        |
| fold_60_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_60_train_heldout_event_overlap                       | 0        | True   | nan        |
| fold_61_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_61_train_heldout_event_overlap                       | 0        | True   | nan        |
| fold_62_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_62_train_heldout_event_overlap                       | 0        | True   | nan        |
| fold_63_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_63_train_heldout_event_overlap                       | 0        | True   | nan        |
| fold_65_train_heldout_run_overlap                         | 0        | True   | nan        |
| fold_65_train_heldout_event_overlap                       | 0        | True   | nan        |
| features_exclude_run_event_target_residual_tail_pair_time | 0        | True   | nan        |
| ml_shuffled_control_not_better_auc                        | 0.519043 | True   |   0.629304 |
| ml_shuffled_control_not_better_tail_capture               | 0.333333 | True   |   0.429825 |

The ML result is useful only as a weak tag: pooled tail capture is `0.430` at veto fraction `0.266` and precision `0.049`. The shuffled-label control is reported beside it; when the control is close, this report treats the veto as diagnostic rather than corrective.

## Conclusion

The pre-trigger veto does not cleanly solve S02 timing tails in leave-one-run-out Sample II. The traditional veto is more conservative; the ML veto catches more tails but at low precision and with leakage checks showing limited separation from shuffled-label behavior. I would not apply this veto as a timing-quality cut without an independent contamination label or a higher-statistics tail definition.

## Follow-up tickets

- S16g: build an independent contamination label from pre-trigger waveform-shape clustering and validate against S16f veto scores without using timing residuals.
- S02e: repeat S02/S02b tail labeling with a lower, pre-registered 3 ns tail threshold to increase Sample-II LORO statistics and re-evaluate S16f veto stability.

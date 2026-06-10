# S02c: template timing sensitivity to selector semantics

Ticket `1781006678.1312.2d7d140a`. Worker `testbeam-laptop-3`.

## Reproduction first

The S00/S00a selector counts and S02/S02b timing references were rebuilt from raw B-stack ROOT before the selector comparison.

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 median-first-four selected pulses |         640737 |       640737 |       0 |           0 | True   |
| S00a dynamic-range equivalent count   |         706373 |       706373 |       0 |           0 | True   |
| Dynamic-only excess pulses            |          65636 |        65636 |       0 |           0 | True   |
| Median-only pulses                    |              0 |            0 |       0 |           0 | True   |

| quantity                                       |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |                 2.88915 |                2.88915 | 0           | True   |
| S02b global-template timewalk                  |                 1.63542 |                1.63542 | 2.20047e-09 | True   |
| S03a ML ridge on template_phase                |                 1.39153 |                1.39153 | 0           | True   |

## Method

The comparison uses train runs `[58, 59, 60, 61, 62, 63]` and held-out run `[65]`. For each selector, templates and the train-only timewalk Ridge closure are refit from that selector's train events. Dynamic-range selection changes only the pulse/event gate; timing waveforms and correction features still use the median-first-four baseline-subtracted waveform.

## Held-out benchmark

| selector      | method                     |   value |   ci_low |   ci_high |   n_heldout_events |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:--------------|:---------------------------|--------:|---------:|----------:|-------------------:|--------------:|----------------------:|-------------------:|
| median_first4 | global_template_phase      | 2.88915 |  2.63915 |   3.27718 |                 66 |       2.57669 |            0.0505051  |                198 |
| median_first4 | strong_template_timewalk   | 1.63542 |  1.49126 |   1.90991 |                 66 |       1.77195 |            0.00505051 |                198 |
| median_first4 | ml_ridge_on_template_phase | 1.39153 |  1.276   |   1.61978 |                 66 |       1.67232 |            0.00505051 |                198 |
| dynamic_range | global_template_phase      | 2.55221 |  2.55221 |   2.80791 |                 90 |       3.5509  |            0.0518519  |                270 |
| dynamic_range | strong_template_timewalk   | 1.8058  |  1.66178 |   2.03217 |                 90 |       2.97488 |            0.0259259  |                270 |
| dynamic_range | ml_ridge_on_template_phase | 1.41874 |  1.3242  |   1.61145 |                 90 |       3.03465 |            0.0111111  |                270 |

By run:

| selector      |   run | method                     |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:--------------|------:|:---------------------------|-------------:|--------------:|----------------------:|-------------------:|
| median_first4 |    65 | global_template_phase      |      2.88915 |       2.57669 |            0.0505051  |                198 |
| median_first4 |    65 | strong_template_timewalk   |      1.63542 |       1.77195 |            0.00505051 |                198 |
| median_first4 |    65 | ml_ridge_on_template_phase |      1.39153 |       1.67232 |            0.00505051 |                198 |
| dynamic_range |    65 | global_template_phase      |      2.55221 |       3.5509  |            0.0518519  |                270 |
| dynamic_range |    65 | strong_template_timewalk   |      1.8058  |       2.97488 |            0.0259259  |                270 |
| dynamic_range |    65 | ml_ridge_on_template_phase |      1.41874 |       3.03465 |            0.0111111  |                270 |

The strong traditional timing result moves from `1.635 ns` [1.491, 1.910] under median-first-four to `1.806 ns` [1.662, 2.032] under dynamic-range selection. The selector-induced traditional delta is `+0.170 ns`.

The ML comparator moves from `1.392 ns` to `1.419 ns`, with selector delta `+0.027 ns`.

## Leakage checks

| selector      | check                                        |   value | pass   |
|:--------------|:---------------------------------------------|--------:|:-------|
| median_first4 | train_heldout_run_overlap                    | 0       | True   |
| median_first4 | train_heldout_event_id_overlap               | 0       | True   |
| median_first4 | normalized_waveform_exact_hash_overlap       | 0       | True   |
| median_first4 | features_exclude_run_event_other_stave_times | 1       | True   |
| median_first4 | traditional_shuffled_target_sigma68_ns       | 2.92078 | True   |
| median_first4 | ml_shuffled_target_sigma68_ns                | 2.75096 | True   |
| dynamic_range | train_heldout_run_overlap                    | 0       | True   |
| dynamic_range | train_heldout_event_id_overlap               | 0       | True   |
| dynamic_range | normalized_waveform_exact_hash_overlap       | 0       | True   |
| dynamic_range | features_exclude_run_event_other_stave_times | 1       | True   |
| dynamic_range | traditional_shuffled_target_sigma68_ns       | 2.75367 | True   |
| dynamic_range | ml_shuffled_target_sigma68_ns                | 2.66    | True   |

The split is by run, train/held-out event identifiers do not overlap, and the shuffled-target controls do not reproduce the selected timing widths. The ML features exclude run id, event id, other-stave times, pair residuals, and selector-defining dynamic amplitude.

## Conclusion

Dynamic-range selection adds low-amplitude all-hit events, but the adoption-ready global-template/timewalk timing method remains in the same band as the median-first-four result on held-out run 65. The result bounds the S00b CFD20 selector drift for the stronger template/timewalk method rather than motivating a dynamic-range selector change.

## Follow-up tickets

- S02d: leave-one-run-out selector-semantics timing over all Sample-II analysis runs, with templates and closures refit per held-out run.
- S00c: CI regression that recomputes median and dynamic-range selected counts directly from raw ROOT and fails on accidental selector changes.

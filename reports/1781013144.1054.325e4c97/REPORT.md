# S02d: leave-one-run-out selector-semantics timing

Ticket `1781013144.1054.325e4c97`. Worker `testbeam-laptop-3`.

## Reproduction first

The raw ROOT selector gate was rerun before any timing model. The S00 median-first-four count and S00a dynamic-range count both reproduce exactly:

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 median-first-four selected pulses |         640737 |       640737 |       0 |           0 | True   |
| S00a dynamic-range equivalent count   |         706373 |       706373 |       0 |           0 | True   |
| Dynamic-only excess pulses            |          65636 |        65636 |       0 |           0 | True   |
| Median-only pulses                    |              0 |            0 |       0 |           0 | True   |

The median-first-four run-65 S02/S02b anchors were also rebuilt from raw ROOT before the LORO selector scan:

| quantity                                       |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |            65 |                 2.88915 |                2.88915 | 0           | True   |
| S02 ML ridge                                   |            65 |                 1.84611 |                1.84611 | 7.54952e-15 | True   |
| S02b binned-template timewalk                  |            65 |                 3.4037  |                3.4037  | 2.08709e-10 | True   |
| S02b global-template timewalk                  |            65 |                 1.63542 |                1.63542 | 2.20047e-09 | True   |

Sample-II LORO downstream event counts by selector are in `loro_selector_pulse_counts_by_run.csv`; the per-run event totals range from `66` to `1075`.

| selector      |   total_events |   total_pulses |
|:--------------|---------------:|---------------:|
| dynamic_range |           4492 |          13476 |
| median_first4 |           3820 |          11460 |

## Method

Held-out runs are `[58, 59, 60, 61, 62, 63, 65]`. For every held-out run and selector, templates, amplitude-binned templates, timewalk/drift closures, and the Ridge ML comparator are fit only on the other Sample-II analysis runs. The split key is run; event ids and waveform hashes are checked between train and held-out sets. CIs inside each fold are event bootstraps; selector deltas use a paired run-block bootstrap over the seven held-out runs.

## Results

Headline per-run held-out bootstrap results:

| selector      |   heldout_run | method                        |   value |   ci_low |   ci_high |   n_heldout_events |   tail_frac_abs_gt5ns |
|:--------------|--------------:|:------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| median_first4 |            58 | S02b global timewalk no drift | 1.52279 |  1.26943 |   1.86821 |                 73 |            0.0228311  |
| median_first4 |            58 | S02 ML ridge                  | 1.91964 |  1.66413 |   2.17053 |                 73 |            0.0228311  |
| median_first4 |            59 | S02b global timewalk no drift | 1.59676 |  1.54746 |   1.65551 |                763 |            0.0126693  |
| median_first4 |            59 | S02 ML ridge                  | 1.88049 |  1.81319 |   1.95946 |                763 |            0.0192224  |
| median_first4 |            60 | S02b global timewalk no drift | 1.4719  |  1.42758 |   1.51964 |                808 |            0.0107261  |
| median_first4 |            60 | S02 ML ridge                  | 1.81993 |  1.73366 |   1.9036  |                808 |            0.0189769  |
| median_first4 |            61 | S02b global timewalk no drift | 2.18842 |  2.09432 |   2.27266 |                933 |            0.0275098  |
| median_first4 |            61 | S02 ML ridge                  | 2.24243 |  2.14452 |   2.33859 |                933 |            0.0214362  |
| median_first4 |            62 | S02b global timewalk no drift | 1.62995 |  1.57995 |   1.67559 |                807 |            0.0111524  |
| median_first4 |            62 | S02 ML ridge                  | 1.86001 |  1.7797  |   1.93299 |                807 |            0.0144568  |
| median_first4 |            63 | S02b global timewalk no drift | 1.54092 |  1.47909 |   1.60114 |                370 |            0.0171171  |
| median_first4 |            63 | S02 ML ridge                  | 1.76984 |  1.61076 |   1.90108 |                370 |            0.0234234  |
| median_first4 |            65 | S02b global timewalk no drift | 1.63542 |  1.50061 |   1.90515 |                 66 |            0.00505051 |
| median_first4 |            65 | S02 ML ridge                  | 1.84611 |  1.4655  |   2.02882 |                 66 |            0          |
| dynamic_range |            58 | S02b global timewalk no drift | 1.7778  |  1.54718 |   2.09913 |                 90 |            0.0444444  |
| dynamic_range |            58 | S02 ML ridge                  | 2.4086  |  1.94418 |   2.86213 |                 90 |            0.0888889  |
| dynamic_range |            59 | S02b global timewalk no drift | 1.83842 |  1.75891 |   1.90431 |                900 |            0.0325926  |
| dynamic_range |            59 | S02 ML ridge                  | 2.18395 |  2.03254 |   2.2964  |                900 |            0.0525926  |
| dynamic_range |            60 | S02b global timewalk no drift | 1.61564 |  1.56218 |   1.66359 |                955 |            0.026178   |
| dynamic_range |            60 | S02 ML ridge                  | 2.242   |  2.08633 |   2.37664 |                955 |            0.0541012  |
| dynamic_range |            61 | S02b global timewalk no drift | 2.31804 |  2.23142 |   2.39542 |               1075 |            0.0431008  |
| dynamic_range |            61 | S02 ML ridge                  | 2.27652 |  2.19102 |   2.3924  |               1075 |            0.0474419  |
| dynamic_range |            62 | S02b global timewalk no drift | 1.83517 |  1.77231 |   1.90971 |                941 |            0.0308183  |
| dynamic_range |            62 | S02 ML ridge                  | 2.19935 |  2.08835 |   2.34502 |                941 |            0.0421537  |
| dynamic_range |            63 | S02b global timewalk no drift | 1.7595  |  1.67552 |   1.84695 |                441 |            0.0249433  |
| dynamic_range |            63 | S02 ML ridge                  | 2.30726 |  2.04934 |   2.50568 |                441 |            0.0559335  |
| dynamic_range |            65 | S02b global timewalk no drift | 1.8058  |  1.65195 |   2.03636 |                 90 |            0.0259259  |
| dynamic_range |            65 | S02 ML ridge                  | 2.59512 |  2.09833 |   3.2389  |                 90 |            0.1        |

Headline run-block summary:

| selector      | method                        |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:--------------|:------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| dynamic_range | S02 ML ridge                  |           2.31612 |  2.23093 |   2.4253  |              2.18395 |              2.59512 |
| median_first4 | S02 ML ridge                  |           1.90549 |  1.82373 |   2.02539 |              1.76984 |              2.24243 |
| dynamic_range | S02b global timewalk no drift |           1.85005 |  1.72869 |   2.02357 |              1.61564 |              2.31804 |
| median_first4 | S02b global timewalk no drift |           1.65516 |  1.53197 |   1.84354 |              1.4719  |              2.18842 |

Paired dynamic-range minus median-first-four deltas for headline methods:

| method                        |   dynamic_minus_median_mean_ns |   ci_low |   ci_high |   min_run_delta_ns |   max_run_delta_ns |
|:------------------------------|-------------------------------:|---------:|----------:|-------------------:|-------------------:|
| S02b global timewalk no drift |                       0.194888 | 0.161197 |  0.22679  |          0.129619  |           0.255008 |
| S02 ML ridge                  |                       0.410622 | 0.254861 |  0.557995 |          0.0340896 |           0.749009 |

The strong traditional method (`S02b global timewalk no drift`) has dynamic-minus-median delta `+0.195 ns` [+0.161, +0.227]. The ML comparator (`S02 ML ridge`) has delta `+0.411 ns` [+0.255, +0.558].

Traditional summaries:

| selector      |   mean_sigma68_ns |   ci_low |   ci_high |
|:--------------|------------------:|---------:|----------:|
| dynamic_range |           1.85005 |  1.72869 |   2.02357 |
| median_first4 |           1.65516 |  1.53197 |   1.84354 |

ML summaries:

| selector      |   mean_sigma68_ns |   ci_low |   ci_high |
|:--------------|------------------:|---------:|----------:|
| dynamic_range |           2.31612 |  2.23093 |   2.4253  |
| median_first4 |           1.90549 |  1.82373 |   2.02539 |

Full method and diagnostic tables are in `heldout_loro_selector_benchmark.csv`, `selector_run_block_bootstrap_summary.csv`, `selector_delta_run_bootstrap.csv`, and `leakage_checks.csv`.

## Leakage checks

Failed non-oracle checks:

| selector      |   heldout_run | check                                      |   value | pass   |
|:--------------|--------------:|:-------------------------------------------|--------:|:-------|
| median_first4 |            58 | binned_selected_shuffled_target_sigma68_ns | 3.00567 | False  |
| median_first4 |            61 | binned_selected_shuffled_target_sigma68_ns | 2.92561 | False  |
| dynamic_range |            58 | binned_selected_shuffled_target_sigma68_ns | 3.80465 | False  |
| dynamic_range |            59 | binned_selected_shuffled_target_sigma68_ns | 4.48551 | False  |
| dynamic_range |            60 | binned_selected_shuffled_target_sigma68_ns | 3.2901  | False  |
| dynamic_range |            61 | binned_selected_shuffled_target_sigma68_ns | 3.6366  | False  |
| dynamic_range |            62 | binned_selected_shuffled_target_sigma68_ns | 3.87581 | False  |
| dynamic_range |            63 | binned_selected_shuffled_target_sigma68_ns | 4.48558 | False  |
| dynamic_range |            65 | binned_selected_shuffled_target_sigma68_ns | 4.47825 | False  |

Non-oracle leakage checks pass: `False`. Reported-method leakage checks pass after excluding the non-adopted binned branch: `True`. The forbidden-oracle rows are deliberately not production methods; they show how much better the metric could look if held-out targets leaked into a correction. The binned branch has shuffled-target failures and is not used for the headline selector claim.

## Conclusion

Dynamic-range selection increases the raw selected-pulse population, but under run-disjoint refits it worsens the strong traditional method by `0.195 ns` and worsens the ML comparator by `0.411 ns` on the paired run-block mean. The selector semantics are therefore a gate-composition nuisance rather than an adoption-ready timing gain.

## Follow-up tickets

- S02e: constrain selector-semantics LORO by detector-current or trigger-rate strata before timing fits.
- S00c: add a raw-ROOT CI gate that recomputes median-first-four and dynamic-range selected counts and fails on selector drift.

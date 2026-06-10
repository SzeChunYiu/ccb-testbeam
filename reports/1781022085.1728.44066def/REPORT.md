# S02f: run-64 calibration-source stress test for S02d

Ticket `1781022085.1728.44066def`. Worker `testbeam-laptop-4`.

## Reproduction first

The raw ROOT gate was rerun before any timing fit. Counts reproduce the S00 selected-pulse number exactly:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

Downstream event counts used for LORO scoring and run-64 calibration are:

|   run |   n_pulses |   n_events |
|------:|-----------:|-----------:|
|    58 |        219 |         73 |
|    59 |       2289 |        763 |
|    60 |       2424 |        808 |
|    61 |       2799 |        933 |
|    62 |       2421 |        807 |
|    63 |       1110 |        370 |
|    64 |        630 |        210 |
|    65 |        198 |         66 |

## Method

Held-out targets are only Sample II analysis runs `[58, 59, 60, 61, 62, 63, 65]`. Run 64 is included in every fold's train/calibration source and is never a held-out target. The concrete train-run sets are:

|   heldout_run | train_runs           |
|--------------:|:---------------------|
|            58 | 59 60 61 62 63 65 64 |
|            59 | 58 60 61 62 63 65 64 |
|            60 | 58 59 61 62 63 65 64 |
|            61 | 58 59 60 62 63 65 64 |
|            62 | 58 59 60 61 63 65 64 |
|            63 | 58 59 60 61 62 65 64 |
|            65 | 58 59 60 61 62 63 64 |

Traditional templates, amplitude-binned templates, timewalk/drift candidates, and the Ridge ML comparator are refit inside each run-disjoint fold. Event bootstrap CIs are reported within each held-out run; the headline summary is a run-block bootstrap across the seven held-out analysis runs.

## Results

Headline held-out folds:

|   heldout_run | method                        |   value |   ci_low |   ci_high |   n_heldout_events |   tail_frac_abs_gt5ns |
|--------------:|:------------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
|            58 | S02b global timewalk no drift | 1.5485  |  1.29597 |   1.86306 |                 73 |            0.0273973  |
|            58 | S02 ML ridge                  | 1.84557 |  1.66894 |   2.15213 |                 73 |            0.0182648  |
|            59 | S02b global timewalk no drift | 1.58359 |  1.52966 |   1.64053 |                763 |            0.0139799  |
|            59 | S02 ML ridge                  | 1.88566 |  1.81335 |   1.96162 |                763 |            0.0187855  |
|            60 | S02b global timewalk no drift | 1.45885 |  1.41402 |   1.50675 |                808 |            0.0111386  |
|            60 | S02 ML ridge                  | 1.84771 |  1.74503 |   1.92347 |                808 |            0.0185644  |
|            61 | S02b global timewalk no drift | 2.18749 |  2.09174 |   2.27859 |                933 |            0.0275098  |
|            61 | S02 ML ridge                  | 2.1908  |  2.11943 |   2.28232 |                933 |            0.0203644  |
|            62 | S02b global timewalk no drift | 1.60984 |  1.56138 |   1.65718 |                807 |            0.0115655  |
|            62 | S02 ML ridge                  | 1.8616  |  1.78379 |   1.94512 |                807 |            0.0123916  |
|            63 | S02b global timewalk no drift | 1.52116 |  1.46575 |   1.60354 |                370 |            0.0171171  |
|            63 | S02 ML ridge                  | 1.79615 |  1.64244 |   1.90677 |                370 |            0.0225225  |
|            65 | S02b global timewalk no drift | 1.6139  |  1.45847 |   1.91327 |                 66 |            0.00505051 |
|            65 | S02 ML ridge                  | 1.78142 |  1.42065 |   2.02934 |                 66 |            0          |

Run-block bootstrap summary:

| method                                           |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:-------------------------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| S02f global selected drift                       |           1.62905 |  1.46209 |   1.79602 |              1.46209 |              1.79602 |
| S02b global timewalk no drift                    |           1.64619 |  1.52428 |   1.83656 |              1.45885 |              2.18749 |
| S02 ML ridge                                     |           1.88699 |  1.81572 |   1.99643 |              1.78142 |              2.1908  |
| S02f train-best global template (template_phase) |           2.78685 |  2.69443 |   2.88187 |              2.61172 |              2.99341 |
| S02f binned selected drift                       |           2.81844 |  2.10246 |   3.53441 |              2.10246 |              3.53441 |
| S02b binned timewalk no drift                    |           2.92878 |  2.58973 |   3.2336  |              2.08154 |              3.51143 |

The strong traditional branch (`S02b global timewalk no drift`) averages `1.646` ns [1.524, 1.837]. The ML Ridge comparator averages `1.887` ns [1.816, 1.996]. The no-drift binned template branch averages `2.929` ns. Selected-drift rows in the run-block table are diagnostics only when `n_runs < 7`; the best selected global-drift diagnostic has `n_runs=2` and mean `1.629` ns.

## Leakage checks

Failed non-oracle checks:

|   heldout_run | check                                      |   value | pass   |
|--------------:|:-------------------------------------------|--------:|:-------|
|            58 | binned_selected_shuffled_target_sigma68_ns | 3.42376 | False  |
|            61 | binned_selected_shuffled_target_sigma68_ns | 2.85965 | False  |

Non-oracle leakage checks pass across all diagnostic branches: `False`. Headline-method checks pass after excluding the non-adopted binned selected-drift shuffled-target control: `True`. The explicit run-64 checks pass in every fold, and the forbidden-oracle rows in `leakage_checks.csv` are retained only as a sensitivity bound for what held-out target leakage could buy.

## Conclusion

With run 64 used as a train-only calibration/template source, the conventional global-template timewalk remains the strongest headline method by run-block mean. ML is competitive but does not dominate the traditional branch under this stress test. The result supports treating run 64 as a calibration stressor, not as an analysis target.

## Follow-up tickets

None appended; this ticket already executes the S02f follow-up proposed by S02d, and I did not find a non-duplicative next study needed from these results.

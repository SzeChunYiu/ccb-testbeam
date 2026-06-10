# S02d: LORO S02b timing plus S16e proxy terms

Ticket `1781013969.1084.3b973f5f`. Worker `testbeam-laptop-1`.

## Reproduction first

Raw ROOT was read from `h101/HRDv` before modeling. The S00 selected B-stave gate was reproduced first:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The previous S16e run-65 point estimates were then reproduced from the same raw ROOT selection:

| quantity                                |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |   delta_ns | pass   |
|:----------------------------------------|--------------:|------------------------:|-----------------------:|-----------:|:-------|
| run65 S02b global template timewalk     |            65 |                 1.63542 |                1.63542 |          0 | True   |
| run65 traditional S16e proxy timewalk   |            65 |                 1.44513 |                1.44513 |          0 | True   |
| run65 ML waveform plus S16e proxy ridge |            65 |                 1.38749 |                1.38749 |          0 | True   |

## Method

Runs `[58, 59, 60, 61, 62, 63, 65]` are evaluated leave-one-run-out. In every fold, S02b global-template/timewalk and both S16e proxy corrections are fit only on the other Sample-II analysis runs, then scored on the held-out run. The traditional method is a Ridge residual correction on hand-built S02b timewalk features plus S16e pre-trigger proxy terms. The ML method is a Ridge residual correction on normalized waveform summaries plus the same proxy terms. Run id, event id, pair residuals, target residuals, and held-out timing labels are excluded from features.

## Held-out Results

Per-run event-bootstrap CIs:

|   heldout_run | method                            |   value |   ci_low |   ci_high |   tail_frac_abs_gt5ns |   tail_ci_low |   tail_ci_high |   n_heldout_events |
|--------------:|:----------------------------------|--------:|---------:|----------:|----------------------:|--------------:|---------------:|-------------------:|
|            58 | S02b global template timewalk     | 1.52279 |  1.27311 |   1.8888  |            0.0228311  |    0          |      0.0547945 |                 73 |
|            58 | traditional S16e proxy timewalk   | 1.23163 |  1.11813 |   1.3943  |            0.0228311  |    0          |      0.0503425 |                 73 |
|            58 | ML waveform plus S16e proxy ridge | 1.24755 |  1.14154 |   1.42246 |            0.0182648  |    0          |      0.0456621 |                 73 |
|            59 | S02b global template timewalk     | 1.59676 |  1.54319 |   1.64308 |            0.0126693  |    0.00698995 |      0.0200961 |                763 |
|            59 | traditional S16e proxy timewalk   | 1.34365 |  1.2891  |   1.40942 |            0.0122324  |    0.00697903 |      0.0183486 |                763 |
|            59 | ML waveform plus S16e proxy ridge | 1.4991  |  1.4262  |   1.55658 |            0.0139799  |    0.0078637  |      0.0205439 |                763 |
|            60 | S02b global template timewalk     | 1.4719  |  1.43124 |   1.51918 |            0.0107261  |    0.00577558 |      0.0177393 |                808 |
|            60 | traditional S16e proxy timewalk   | 1.38212 |  1.32004 |   1.45948 |            0.0111386  |    0.00618812 |      0.0177393 |                808 |
|            60 | ML waveform plus S16e proxy ridge | 1.31012 |  1.25839 |   1.36092 |            0.0136139  |    0.00824051 |      0.019802  |                808 |
|            61 | S02b global template timewalk     | 2.18842 |  2.09981 |   2.27118 |            0.0275098  |    0.0200071  |      0.0350125 |                933 |
|            61 | traditional S16e proxy timewalk   | 1.29349 |  1.24318 |   1.35312 |            0.0146481  |    0.00857449 |      0.0214362 |                933 |
|            61 | ML waveform plus S16e proxy ridge | 2.01771 |  1.93479 |   2.12367 |            0.0253662  |    0.0189353  |      0.0332262 |                933 |
|            62 | S02b global template timewalk     | 1.62995 |  1.57904 |   1.67645 |            0.0111524  |    0.00619579 |      0.0177613 |                807 |
|            62 | traditional S16e proxy timewalk   | 1.33667 |  1.25613 |   1.38837 |            0.0103263  |    0.00578273 |      0.0165221 |                807 |
|            62 | ML waveform plus S16e proxy ridge | 1.46811 |  1.40272 |   1.52909 |            0.0119785  |    0.00660884 |      0.0185977 |                807 |
|            63 | S02b global template timewalk     | 1.54092 |  1.48549 |   1.60522 |            0.0171171  |    0.00810811 |      0.0288288 |                370 |
|            63 | traditional S16e proxy timewalk   | 1.37181 |  1.27076 |   1.48536 |            0.0144144  |    0.00630631 |      0.0252477 |                370 |
|            63 | ML waveform plus S16e proxy ridge | 1.35965 |  1.26621 |   1.43996 |            0.018018   |    0.00900901 |      0.0288739 |                370 |
|            65 | S02b global template timewalk     | 1.63542 |  1.47576 |   1.91423 |            0.00505051 |    0          |      0.0151515 |                 66 |
|            65 | traditional S16e proxy timewalk   | 1.44513 |  1.18819 |   1.71104 |            0          |    0          |      0.0151515 |                 66 |
|            65 | ML waveform plus S16e proxy ridge | 1.38749 |  1.25927 |   1.63431 |            0.00505051 |    0          |      0.020202  |                 66 |

Run-block bootstrap across held-out runs:

| method                            |   mean_sigma68_ns |   ci_low |   ci_high |   mean_tail_frac_abs_gt5ns |   tail_ci_low |   tail_ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:----------------------------------|------------------:|---------:|----------:|---------------------------:|--------------:|---------------:|---------------------:|---------------------:|
| traditional S16e proxy timewalk   |           1.3435  |  1.29767 |   1.38949 |                  0.0122273 |    0.00725159 |      0.0166142 |              1.23163 |              1.44513 |
| ML waveform plus S16e proxy ridge |           1.46996 |  1.33248 |   1.66955 |                  0.0151817 |    0.0108045  |      0.0195589 |              1.24755 |              2.01771 |
| S02b global template timewalk     |           1.65516 |  1.53203 |   1.84464 |                  0.0152938 |    0.010356   |      0.020806  |              1.4719  |              2.18842 |

Mean sigma68 deltas versus S02b global-template/timewalk: traditional proxy `-0.312` ns; ML proxy `-0.185` ns. The best mean branch is `traditional S16e proxy timewalk` at `1.343` ns, but the leakage verdict is `leakage guards passed`.

## Proxy Tail Diagnostic

Mean held-out tail fraction by pre-trigger proxy bin:

| method                            | proxy_bin   |   mean_tail_frac_abs_gt5ns |   mean_sigma68_ns |   n_events |
|:----------------------------------|:------------|---------------------------:|------------------:|-----------:|
| ML waveform plus S16e proxy ridge | high        |                 0.0174638  |           1.16209 |       1272 |
| ML waveform plus S16e proxy ridge | low         |                 0.0118855  |           1.68272 |       1284 |
| ML waveform plus S16e proxy ridge | mid         |                 0.0162915  |           1.66886 |       1264 |
| S02b global template timewalk     | high        |                 0.0179814  |           1.52743 |       1272 |
| S02b global template timewalk     | low         |                 0.014083   |           1.70103 |       1284 |
| S02b global template timewalk     | mid         |                 0.0137891  |           1.7316  |       1264 |
| traditional S16e proxy timewalk   | high        |                 0.0168526  |           1.06009 |       1272 |
| traditional S16e proxy timewalk   | low         |                 0.0129963  |           1.51665 |       1284 |
| traditional S16e proxy timewalk   | mid         |                 0.00671526 |           1.45127 |       1264 |

## Leakage Checks

|   heldout_run | check                                           |   value |    actual | pass   |
|--------------:|:------------------------------------------------|--------:|----------:|:-------|
|            58 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            58 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            58 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            58 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            58 | traditional_shuffled_target_not_better          | 1.56333 |   1.23163 | True   |
|            58 | ml_shuffled_target_not_better                   | 2.70311 |   1.24755 | True   |
|            59 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            59 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            59 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            59 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            59 | traditional_shuffled_target_not_better          | 1.62069 |   1.34365 | True   |
|            59 | ml_shuffled_target_not_better                   | 3.01312 |   1.4991  | True   |
|            60 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            60 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            60 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            60 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            60 | traditional_shuffled_target_not_better          | 1.49108 |   1.38212 | True   |
|            60 | ml_shuffled_target_not_better                   | 2.68248 |   1.31012 | True   |
|            61 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            61 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            61 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            61 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            61 | traditional_shuffled_target_not_better          | 2.16609 |   1.29349 | True   |
|            61 | ml_shuffled_target_not_better                   | 2.6044  |   2.01771 | True   |
|            62 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            62 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            62 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            62 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            62 | traditional_shuffled_target_not_better          | 1.68877 |   1.33667 | True   |
|            62 | ml_shuffled_target_not_better                   | 3.04972 |   1.46811 | True   |
|            63 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            63 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            63 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            63 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            63 | traditional_shuffled_target_not_better          | 1.5692  |   1.37181 | True   |
|            63 | ml_shuffled_target_not_better                   | 3.01739 |   1.35965 | True   |
|            65 | train_heldout_run_overlap                       | 0       | nan       | True   |
|            65 | train_heldout_event_id_overlap                  | 0       | nan       | True   |
|            65 | normalized_waveform_exact_hash_overlap          | 0       | nan       | True   |
|            65 | features_exclude_run_event_target_pair_residual | 0       | nan       | True   |
|            65 | traditional_shuffled_target_not_better          | 1.66736 |   1.44513 | True   |
|            65 | ml_shuffled_target_not_better                   | 2.74866 |   1.38749 | True   |

Hard split and feature checks pass: `True`. Shuffled-target rows are reported separately because they test whether a too-good correction survives a negative-control target. Any shuffled-target failure blocks adoption even when the raw point estimate improves.

## Conclusion

The run-65 S16e improvement reproduces and the all-run LORO extension remains favorable under the leakage controls used here. The traditional S16e proxy correction is the strongest branch on the run-block mean and improves every held-out fold relative to S02b global-template/timewalk. The ML proxy branch is competitive but less stable, with run 61 remaining broad. Treat the proxy terms as a leakage-audited timing nuisance correction candidate, not yet as a detector-independent causal explanation for timing tails.

## Follow-up Tickets

- S16f: build a frozen pre-trigger contamination veto using only train-run proxy quantiles, then measure S02b tail rejection and timing efficiency under the same Sample-II LORO splits.
- P03f: run an early-sample waveform ablation against S02b residuals with shuffled-target and run-family controls to decide whether samples 0-3 carry causal timing information or only nuisance/run structure.

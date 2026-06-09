# S05f: B2-local covariance confound matched audit

- **Ticket:** 1781017203.1538.0ce44cf7
- **Worker:** testbeam-laptop-1
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05f_1781017203_1538_0ce44cf7_b2_local_covariance_audit.yaml`
- **Raw input:** `data/root/root`

## Question

Is the large B2 component in S05c covariance a true correlated timing mode, or a local confound from B2 saturation, amplitude, topology, peak sample, and P09-style anomaly strata? No Monte Carlo was used.

## Reproduction first

The frozen S05c/S05e ROOT gate was run before fitting: `h101/HRDv`, median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, and CFD20 pair residuals.

| quantity                             |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses              |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses |         125096 |       125096 |       0 |           0 | True   |

Pair-row counts:

| pair   |   n_pair_rows |
|:-------|--------------:|
| B2-B4  |         26387 |
| B2-B6  |         12626 |
| B2-B8  |          4943 |
| B4-B6  |         12196 |
| B4-B8  |          4542 |
| B6-B8  |          4790 |

The S05c covariance headline was reproduced before the matched audit:

| quantity                                |   report_value |   reproduced |        delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S05c_raw_b2_containing_mean_abs_cov_ns2 |        1041.84 |    1041.84   |  7.49073e-05 |        0.05 | True   |
| S05c_raw_downstream_mean_abs_cov_ns2    |          15.99 |      15.9882 | -0.00178499  |        0.05 | True   |

## Methods

Traditional methods are frozen S05c pair-median CFD20 residuals, a winsorized robust covariance estimator, and the S05e saturation-aware Ridge residuals. Covariances are computed inside matched cells keyed by run, B2 amplitude bin, B2 saturation bin, B2 peak-sample bin, topology count, and P09-style anomaly stratum; only cells containing both B2-containing and downstream-only off-diagonal covariance rows enter the primary contrast.

ML methods are leave-one-run-held-out ExtraTrees residual predictors: `ml_with_b2_local` includes B2-local waveform/saturation features from S05e; `ml_no_b2_local` removes explicit B2-local waveform, saturation, and anomaly inputs; `ml_shuffled_run_control` replaces train targets with targets sampled from other train runs; `downstream_only_control` trains on downstream-only pairs. Inputs exclude run id, event id, raw time, raw residual, target residual, and held-out labels.

P09-style thresholds used for matching:

| threshold              | value                              |
|:-----------------------|:-----------------------------------|
| B2_amp_edges           | 1002,2737,3322,4213.5,7011.6,13789 |
| B2_tail_q99            | 1.0150303640621192                 |
| B2_recovery_tail_q99   | 5161.479999999994                  |
| B2_post_peak_fall_q01  | 0.0                                |
| B2_near_peak_count_q99 | 3.0                                |

## Primary matched covariance

Metric: B2-containing minus downstream-only signed off-diagonal covariance, with stratified run-block bootstrap 95% CIs. The inferred correlated fraction is `delta / B2_signed_cov`.

| method                       | estimator       |   n_shared_cells |   n_b2_covariances |   n_downstream_covariances |   b2_signed_cov_ns2 |   downstream_signed_cov_ns2 |   b2_minus_downstream_cov_ns2 |   inferred_correlated_fraction |   delta_ci_low_ns2 |   delta_ci_high_ns2 |   fraction_ci_low |   fraction_ci_high |   bootstrap_shared_cells_median |   bootstrap_resamples_used |
|:-----------------------------|:----------------|-----------------:|-------------------:|---------------------------:|--------------------:|----------------------------:|------------------------------:|-------------------------------:|-------------------:|--------------------:|------------------:|-------------------:|--------------------------------:|---------------------------:|
| downstream_only_control      | winsor_mad      |               56 |                168 |                        168 |            43.3338  |                    0.53237  |                      42.8014  |                       0.987715 |           18.5606  |           107.114   |          0.972179 |           0.994767 |                              35 |                        500 |
| ml_no_b2_local               | winsor_mad      |               56 |                168 |                        168 |             9.45026 |                    0.553435 |                       8.89682 |                       0.941437 |            6.80423 |            12.8836  |          0.904922 |           0.961021 |                              35 |                        500 |
| ml_shuffled_run_control      | winsor_mad      |               56 |                168 |                        168 |           133.011   |                    2.03781  |                     130.973   |                       0.984679 |           57.0541  |           430.996   |          0.965424 |           0.995119 |                              35 |                        500 |
| ml_with_b2_local             | winsor_mad      |               56 |                168 |                        168 |             3.93605 |                    0.383911 |                       3.55214 |                       0.902463 |            1.86459 |             6.34919 |          0.812135 |           0.942333 |                              37 |                        500 |
| raw_pair_median              | median_centered |               56 |                168 |                        168 |           186.656   |                   11.4043   |                     175.252   |                       0.938902 |           80.049   |           518.37    |          0.85922  |           0.984038 |                              36 |                        500 |
| raw_pair_median              | pearson         |               56 |                168 |                        168 |           170.653   |                   10.8966   |                     159.756   |                       0.936147 |           79.4457  |           448.725   |          0.871583 |           0.982298 |                              35 |                        500 |
| raw_pair_median              | winsor_mad      |               56 |                168 |                        168 |            12.8013  |                    0.983944 |                      11.8173  |                       0.923137 |            5.55721 |            27.6161  |          0.852722 |           0.964222 |                              36 |                        500 |
| traditional_saturation_ridge | winsor_mad      |               56 |                168 |                        168 |            30.2347  |                   11.7879   |                      18.4468  |                       0.61012  |           10.4974  |            36.3276  |          0.453931 |           0.736017 |                              36 |                        500 |

The robust matched raw baseline has delta `11.82` ns^2 with CI `[5.56, 27.62]`. The B2-local ML model has delta `3.55` ns^2 with CI `[1.86, 6.35]`; without B2-local inputs the ML delta is `8.90` ns^2.

## Secondary residual metrics

| method                       | subset          |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |
|:-----------------------------|:----------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|---------------------:|----------------------:|
| raw_pair_median              | all             |         65484 |       21 |      2.08184 |            1.81025  |              9.92382 |      20.675   |             16.0721  |              28.902   |
| raw_pair_median              | B2_containing   |         43956 |       21 |      3.51234 |            1.90349  |             21.3933  |      24.817   |             19.2529  |              35.6561  |
| raw_pair_median              | downstream_only |         21528 |       21 |      1.73256 |            1.69993  |              1.75638 |       6.53666 |              5.76787 |               7.30522 |
| traditional_saturation_ridge | all             |         65484 |       21 |      6.6249  |            6.12977  |              7.97878 |      11.5773  |             10.4916  |              13.9034  |
| traditional_saturation_ridge | B2_containing   |         43956 |       21 |      7.04995 |            6.30754  |              8.94113 |      13.0679  |             11.6242  |              15.4376  |
| traditional_saturation_ridge | downstream_only |         21528 |       21 |      5.66287 |            5.15161  |              6.51133 |       7.78701 |              7.1131  |               8.62013 |
| ml_with_b2_local             | all             |         65484 |       21 |      1.35808 |            1.22173  |              1.92879 |       5.56879 |              5.05822 |               6.87136 |
| ml_with_b2_local             | B2_containing   |         43956 |       21 |      1.61957 |            1.36984  |              2.57167 |       6.1932  |              5.51601 |               7.31622 |
| ml_with_b2_local             | downstream_only |         21528 |       21 |      1.03111 |            0.996042 |              1.09547 |       4.00684 |              3.1144  |               5.24267 |
| ml_no_b2_local               | all             |         65484 |       21 |      1.84971 |            1.63574  |              2.65863 |       8.11529 |              7.13063 |              10.2456  |
| ml_no_b2_local               | B2_containing   |         43956 |       21 |      2.49691 |            2.06427  |              4.08749 |       9.36735 |              8.15347 |              11.5538  |
| ml_no_b2_local               | downstream_only |         21528 |       21 |      1.16959 |            1.12486  |              1.26587 |       4.61347 |              3.72571 |               5.7916  |
| ml_shuffled_run_control      | all             |         65484 |       21 |      4.63017 |            4.10959  |              9.69493 |      20.9196  |             16.5004  |              29.6776  |
| ml_shuffled_run_control      | B2_containing   |         43956 |       21 |      5.46981 |            4.18808  |             20.5594  |      25.2421  |             19.7879  |              35.3019  |
| ml_shuffled_run_control      | downstream_only |         21528 |       21 |      3.56663 |            3.46543  |              3.65575 |       7.1842  |              6.39484 |               7.99428 |
| downstream_only_control      | all             |         65484 |       21 |      3.31584 |            3.08354  |              8.05521 |      13.6536  |             10.9568  |              18.5566  |
| downstream_only_control      | B2_containing   |         43956 |       21 |      4.27942 |            3.4444   |             14.3922  |      16.5051  |             13.3921  |              21.6791  |
| downstream_only_control      | downstream_only |         21528 |       21 |      1.1697  |            1.12906  |              1.26897 |       5.11956 |              4.30299 |               6.43951 |

All-run ML sigma68 is `1.358` ns with full RMS `5.569` ns. Removing B2-local inputs gives sigma68 `1.850` ns.

## Leave-one-run stability and interval coverage

Leave-one-run stability rows are written to `leave_one_run_stability.csv`; the range of the primary winsorized ML delta is `2.92` to `4.40` ns^2.

| method                       | estimator       |   primary_delta_ns2 |   delta_ci_low_ns2 |   delta_ci_high_ns2 | interval_excludes_zero   |   n_shared_cells | coverage_note                                   |
|:-----------------------------|:----------------|--------------------:|-------------------:|--------------------:|:-------------------------|-----------------:|:------------------------------------------------|
| downstream_only_control      | winsor_mad      |            42.8014  |           18.5606  |           107.114   | True                     |               56 | run-block bootstrap interval over matched cells |
| ml_no_b2_local               | winsor_mad      |             8.89682 |            6.80423 |            12.8836  | True                     |               56 | run-block bootstrap interval over matched cells |
| ml_shuffled_run_control      | winsor_mad      |           130.973   |           57.0541  |           430.996   | True                     |               56 | run-block bootstrap interval over matched cells |
| ml_with_b2_local             | winsor_mad      |             3.55214 |            1.86459 |             6.34919 | True                     |               56 | run-block bootstrap interval over matched cells |
| raw_pair_median              | median_centered |           175.252   |           80.049   |           518.37    | True                     |               56 | run-block bootstrap interval over matched cells |
| raw_pair_median              | pearson         |           159.756   |           79.4457  |           448.725   | True                     |               56 | run-block bootstrap interval over matched cells |
| raw_pair_median              | winsor_mad      |            11.8173  |            5.55721 |            27.6161  | True                     |               56 | run-block bootstrap interval over matched cells |
| traditional_saturation_ridge | winsor_mad      |            18.4468  |           10.4974  |            36.3276  | True                     |               56 | run-block bootstrap interval over matched cells |

## Leakage checks

| check                                           |   value | pass   | interpretation                                                                                           |
|:------------------------------------------------|--------:|:-------|:---------------------------------------------------------------------------------------------------------|
| run_split_event_overlap                         | 0       | True   | all fitted predictions are leave-one-run-held-out                                                        |
| features_exclude_forbidden_columns              | 1       | True   | ML feature lists exclude run/event ids, raw times, residual targets, and pair residuals                  |
| shuffled_run_control_sigma68_worse_than_nominal | 3.27208 | True   | targets sampled from other train runs should not reproduce nominal ML width                              |
| downstream_only_control_not_better_on_b2        | 2.65985 | True   | a model trained only on downstream pairs should not outperform the B2-local model on B2-containing pairs |

The nominal ML width is not adopted alone: the shuffled-run control must be worse, the downstream-only control must not explain B2-containing residuals suspiciously well, and the matched covariance contrast must be interpreted only inside shared run/local strata.

## Finding

The raw S05c B2 covariance headline reproduces, but matching on B2-local amplitude/saturation/peak/topology/anomaly strata collapses most of the apparent B2 excess. The remaining matched covariance should be treated as B2-local residual structure, not as evidence for a detector-wide common timing mode for two-ended timing projections.

## Artifacts

`reproduction_match_table.csv`, `s05c_covariance_reproduction.csv`, `pair_counts.csv`, `p09_style_thresholds.csv`, `heldout_pair_residuals.csv`, `matched_covariance_rows.csv`, `matched_covariance_summary.csv`, `matched_covariance_bootstrap.csv`, `leave_one_run_stability.csv`, `residual_metrics.csv`, `covariance_interval_coverage.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

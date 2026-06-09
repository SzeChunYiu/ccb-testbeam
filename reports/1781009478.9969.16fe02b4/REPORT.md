# S05c: hierarchical B-stack run/stave covariance model

- **Ticket:** 1781009478.9969.16fe02b4
- **Worker:** testbeam-laptop-3
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `configs/s05c_hierarchical_bstack_covariance.yaml`
- **Raw input:** `data/root/root`

## Question

Fit a hierarchical run/stave covariance model for B-stack pair residuals, with B2-containing pairs separated from downstream-only pairs, without using A-stack coincidences or Monte Carlo.

## Reproduction from raw ROOT

The gate was run first from `h101/HRDv`: median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, CFD20 timing, and the configured analysis runs.

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

## Methods

The target is the B-stack pair residual `t_right - t_left - TOF`, using 2 cm layer spacing and 0.078 ns/cm. All model comparisons are leave-one-run-out; the held-out run is never used for fitting or hyperparameter selection.

Traditional: pair-median centered CFD20 residuals, followed by a covariance model that decomposes pair residual covariance into an event-level stave covariance and a run-median covariance by matching off-diagonal pair covariances to `L Sigma_stave L^T`. A Ridge nuisance correction is also reported as a diagnostic, but it is not the selected traditional baseline because it broadens held-out residuals.

ML: ExtraTrees over the same pair features plus all four B-stave waveform summaries. It excludes run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels. The hyperparameters are fixed in the config before evaluation, and every prediction is for a held-out run.

## Held-out residual benchmark

| method                 | subset          |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                              |
|:-----------------------|:----------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:------------------------------------------------------------------|
| raw_pair_median        | all             |         65484 |       21 |      2.08184 |             1.78587 |              7.53262 |      20.675   |             0.141653  | pair-median centered raw CFD20 residual                           |
| raw_pair_median        | B2_containing   |         43956 |       21 |      3.51234 |             1.89074 |             19.9006  |      24.817   |             0.202612  | pair-median centered raw CFD20 residual                           |
| raw_pair_median        | downstream_only |         21528 |       21 |      1.73256 |             1.69354 |              1.76721 |       6.53666 |             0.0171869 | pair-median centered raw CFD20 residual                           |
| traditional_hier_ridge | all             |         65484 |       21 |      7.74507 |             7.07807 |              9.6228  |      12.6115  |             0.478514  | leave-run-out Ridge residual correction before covariance fit     |
| traditional_hier_ridge | B2_containing   |         43956 |       21 |      7.81865 |             6.85659 |             11.8347  |      14.0196  |             0.475635  | leave-run-out Ridge residual correction before covariance fit     |
| traditional_hier_ridge | downstream_only |         21528 |       21 |      7.27777 |             6.7597  |              8.28207 |       9.18574 |             0.466973  | leave-run-out Ridge residual correction before covariance fit     |
| ml_extra_trees         | all             |         65484 |       21 |      1.44892 |             1.31416 |              1.95744 |       5.61909 |             0.0898693 | leave-run-out ExtraTrees residual model on waveform-only features |
| ml_extra_trees         | B2_containing   |         43956 |       21 |      1.74922 |             1.46072 |              2.71248 |       6.31955 |             0.124989  | leave-run-out ExtraTrees residual model on waveform-only features |
| ml_extra_trees         | downstream_only |         21528 |       21 |      1.09885 |             1.06874 |              1.16658 |       3.81429 |             0.0183017 | leave-run-out ExtraTrees residual model on waveform-only features |

The run-bootstrap ML minus traditional sigma68 delta is `-0.633` ns with 95% CI `[-8.271, -0.451]` and two-sided p=`0.000`.

## Hierarchical covariance

Pair-pair covariance summaries from held-out residuals:

| method                 | subset               |   n_covariances |   n_runs |   mean_abs_cov_ns2 |   mean_abs_cov_ci_low_ns2 |   mean_abs_cov_ci_high_ns2 |   median_abs_cov_ns2 |   signed_mean_cov_ns2 |
|:-----------------------|:---------------------|----------------:|---------:|-------------------:|--------------------------:|---------------------------:|---------------------:|----------------------:|
| ml_extra_trees         | all_pair_covariances |             300 |       20 |           13.7193  |                   7.94986 |                    23.4932 |             2.40449  |              7.58585  |
| ml_extra_trees         | both_B2_containing   |              60 |       20 |           28.5664  |                  20.8076  |                    36.5064 |            26.2345   |             27.6648   |
| ml_extra_trees         | both_downstream_only |              60 |       20 |           10.6376  |                   1.8469  |                    27.0571 |             0.902131 |              9.93024  |
| ml_extra_trees         | mixed_B2_downstream  |             180 |       20 |            9.79753 |                   4.014   |                    19.0805 |             2.04276  |              0.111407 |
| raw_pair_median        | all_pair_covariances |             300 |       20 |          228.535   |                 172.186   |                   290.464  |            15.0688   |            223.089    |
| raw_pair_median        | both_B2_containing   |              60 |       20 |         1041.84    |                 748.083   |                  1311.91   |          1189        |           1041.84     |
| raw_pair_median        | both_downstream_only |              60 |       20 |           15.9882  |                   4.758   |                    37.1279 |             1.63686  |             15.411    |
| raw_pair_median        | mixed_B2_downstream  |             180 |       20 |           28.2816  |                  16.1324  |                    44.8278 |            10.4275   |             19.3972   |
| traditional_hier_ridge | all_pair_covariances |             300 |       20 |           81.8546  |                  67.155   |                    95.9489 |            45.0287   |             39.7229   |
| traditional_hier_ridge | both_B2_containing   |              60 |       20 |          235.514   |                 184.198   |                   289.397  |           222.826    |            235.514    |
| traditional_hier_ridge | both_downstream_only |              60 |       20 |           43.2984  |                  33.9146  |                    58.2121 |            33.9054   |             42.1112   |
| traditional_hier_ridge | mixed_B2_downstream  |             180 |       20 |           43.487   |                  34.1241  |                    54.002  |            34.6394   |            -26.3368   |

The traditional CFD20 covariance baseline has B2-containing pair covariance `1041.84` ns^2 with run-bootstrap CI `[748.08, 1311.91]`; downstream-only pair covariance is `15.99` ns^2 with CI `[4.76, 37.13]`.

Stave-covariance decomposition:

|      var_B2 |     cov_B2_B4 |    cov_B2_B6 |    cov_B2_B8 |     var_B4 |   cov_B4_B6 |   cov_B4_B8 |     var_B6 |   cov_B6_B8 |     var_B8 |   offdiag_rmse_ns2 |   n_offdiag_covariances | method                 | scope              |   B2_variance_minus_downstream_mean_ns2 |
|------------:|--------------:|-------------:|-------------:|-----------:|------------:|------------:|-----------:|------------:|-----------:|-------------------:|------------------------:|:-----------------------|:-------------------|----------------------------------------:|
| 166.497     | -100.696      | -113.321     | -118.976     | 34.2436    |  21.3232    |  10.8859    | 35.0676    |  21.8624    | 43.1141    |          10.4259   |                      15 | raw_pair_median        | event_level_pooled |                            129.022      |
|   5.40607   |   -3.33382    |   -3.81215   |   -3.66618   |  0.78651   |   0.93462   |   0.82618   |  0.786241  |   1.30505   |  0.767476  |           1.4413   |                      15 | raw_pair_median        | run_median_level   |                              4.626      |
|  51.4606    |  -36.8972     |  -29.3874    |  -36.6366    | 30.3479    |  -4.22556   | -19.5731    | 19.1482    |  -4.68345   | 30.4466    |           5.86343  |                      15 | traditional_hier_ridge | event_level_pooled |                             24.813      |
|   0.929758  |   -1.21351    |   -0.300002  |   -0.346008  |  1.2012    |   0.263015  |  -1.45192   | -0.065358  |   0.167703  |  0.815112  |           0.785921 |                      15 | traditional_hier_ridge | run_median_level   |                              0.279438   |
|   8.48548   |   -5.3372     |   -5.81286   |   -5.82091   |  5.06324   |  -1.85785   |  -2.93143   |  3.90926   |  -0.147819  |  4.45008   |           1.03064  |                      15 | ml_extra_trees         | event_level_pooled |                              4.01129    |
|   0.0412728 |   -0.00661611 |   -0.0363236 |   -0.0396058 |  0.0555153 |  -0.0549901 |  -0.0494244 |  0.0376172 |   0.0160792 |  0.0364755 |           0.040566 |                      15 | ml_extra_trees         | run_median_level   |                             -0.00192991 |

## Leakage checks

| check                                 |   value | pass   | interpretation                                                                                       |
|:--------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------------------------|
| run_split_event_overlap               | 0       | True   | train and held-out event ids are disjoint because whole runs are held out                            |
| ml_features_exclude_forbidden_columns | 1       | True   | ML inputs exclude run, event, time_ns, raw residual, target residual, and pair-derived timing labels |
| actual_ml_sigma68_ns                  | 1.44892 | True   | nominal leave-run-out ML residual width                                                              |
| shuffled_train_target_ml_sigma68_ns   | 4.49179 | True   | target permutation inside train folds should not reproduce the nominal ML width                      |
| intentional_target_echo_sigma68_ns    | 0       | True   | positive leakage sentinel; a leaked target would be unrealistically narrow                           |

The shuffled-target ML control and intentional target-echo sentinel are leakage probes. The ML gain is not adopted unless its paired run-bootstrap CI is wholly below zero and the probes do not show an obvious split or target echo leak.

## Finding

The held-out covariance is detector-local/topology dominated: B2-containing pair covariances are far larger than downstream-only covariances in the traditional CFD20 hierarchical fit. The run/stave decomposition assigns the largest excess variance to the B2 node. ExtraTrees gives a leakage-checked residual-width reduction, but the covariance decomposition still keeps B2 as the dominant local component rather than turning the problem into a detector-wide common mode.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

## Follow-up tickets

- S05d: convert the S05c covariance decomposition into per-stave timing-resolution priors for the two-ended projection; expected information gain is testing whether B2-local variance can be downweighted without biasing downstream timing.
- S05e: rerun the S05c covariance model after explicit saturation-recovery features for B2; expected information gain is separating high-amplitude B2 waveform pathology from irreducible detector-local covariance.

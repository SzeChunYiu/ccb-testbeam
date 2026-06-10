# S10g: S10f real-current two-pulse validation

- **Ticket:** `1781029288.941.6912528c`
- **Worker:** `testbeam-laptop-3`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** every scored event is predicted by source-run-held-out low-current templates/ML models; CIs resample held-out runs within current group.

## Reproduction first

The S10/S10d topology gate was reproduced from raw ROOT before scoring real windows. Downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA; all six documented topology fractions pass the +/-0.0015 tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

The S10f raw selected-pulse count gate was also rerun before the real-window analysis.

| quantity                                |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10f total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| S10f sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| S10f sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| S10f sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| S10f sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| S10f sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Strata and event scoring

The S10c strata are reused exactly: maximum selected-pulse amplitude, S16 adaptive-lowering bin, and P02-style topology. Full raw-ROOT counts define the matched-stratum weights; a capped within-run/within-stratum sample of 20 events supplies waveform-level scores. 8 matched strata pass the low/high count floor.

## Traditional method

For each held-out run, S10f amplitude-binned/asymmetric template candidates are built only from low-current raw pulses, excluding the held-out run when the held-out run is itself low-current. The fit scans primary/secondary candidate pairs, timing, and separation, then solves amplitudes plus baseline by least squares.

Matched high-minus-low secondary fraction: **-0.03088** with run-bootstrap 95% CI **[-0.05045, -0.00938]**. Candidate-rate excess at score >0.015: **-0.01047** [-0.09733, 0.07765].

| amp_bin       | baseline_bin       | p02_topology        |   low_n_scored |   high_n_scored |   low_mean |   high_mean |   high_minus_low |   match_weight |
|:--------------|:-------------------|:--------------------|---------------:|----------------:|-----------:|------------:|-----------------:|---------------:|
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |             40 |             240 |  0.297076  |    0.288373 |     -0.00870293  |     0.519603   |
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |             40 |             240 |  0.491034  |    0.409306 |     -0.0817281   |     0.293605   |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |             40 |             240 |  0.616442  |    0.600493 |     -0.0159486   |     0.135738   |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |             40 |             240 |  0         |    0        |      0           |     0.0230005  |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |             23 |             240 |  0.0852687 |    0.047149 |     -0.0381197   |     0.00888657 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |             26 |             240 |  0.0712265 |    0.120023 |      0.0487968   |     0.00784109 |
| amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |             25 |             240 |  0.602292  |    0.602246 |     -4.61629e-05 |     0.00662136 |
| amp_ge_4500   | s16_large_lowering | p02_broad_late      |             23 |             240 |  0.30242   |    0.252081 |     -0.0503389   |     0.00470465 |

## ML residual diagnostic

The ML method is a compact MLP classifier/regressor trained on low-current synthetic overlays. Two low-current leave-one-run-out models calibrate on the other low-current run; high-current windows are scored by averaging those two models. Features are waveform-shape summaries only; identifiers and current labels are excluded.

ML secondary-fraction high-minus-low: **0.00817** [-0.02230, 0.04002]. ML overlap-score high-minus-low: **-0.00122** [-0.01006, 0.01123]. Candidate-rate excess at score >0.50: **0.02310** [-0.02345, 0.08018]. Mean low-run held-out AUC is 0.745; shuffled-label AUC is 0.457.

## Run Stability

|   run | group     | method   |   candidate_rate |   mean_recovered_delay_ns |   mean_secondary_fraction |   mean_total_area_proxy_adc |
|------:|:----------|:---------|-----------------:|--------------------------:|--------------------------:|----------------------------:|
|    44 | high_20nA | ml       |         0.35625  |                  19.1239  |                  0.189182 |                 1.81521e+07 |
|    45 | high_20nA | ml       |         0.31875  |                  15.6488  |                  0.181492 |                 1.43325e+07 |
|    48 | high_20nA | ml       |         0.30625  |                  26.5569  |                  0.171472 |                 1.23324e+07 |
|    49 | high_20nA | ml       |         0.3375   |                  21.5642  |                  0.1792   |                 1.33529e+07 |
|    50 | high_20nA | ml       |         0.33125  |                  17.4776  |                  0.167024 |                 1.62626e+07 |
|    51 | high_20nA | ml       |         0.30625  |                  19.7994  |                  0.159427 |                 1.30391e+07 |
|    52 | high_20nA | ml       |         0.325    |                  22.8399  |                  0.172034 |                 1.42858e+07 |
|    53 | high_20nA | ml       |         0.31875  |                  16.6723  |                  0.186734 |                 2.22895e+07 |
|    54 | high_20nA | ml       |         0.3      |                  21.9253  |                  0.161871 |                 1.5397e+07  |
|    55 | high_20nA | ml       |         0.3375   |                  21.2087  |                  0.178125 |                 1.65848e+07 |
|    56 | high_20nA | ml       |         0.375    |                  24.4498  |                  0.185926 |                 1.48093e+07 |
|    57 | high_20nA | ml       |         0.36875  |                  27.0407  |                  0.185392 |                 1.30627e+07 |
|    46 | low_2nA   | ml       |         0.278351 |                   7.44682 |                  0.287424 |                 1.37432e+07 |
|    47 | low_2nA   | ml       |         0.4875   |                  32.9532  |                  0.119179 |                 1.09542e+07 |

## Leakage review

| check                                                  |    value | flag   | note                                                                                                                                               |
|:-------------------------------------------------------|---------:|:-------|:---------------------------------------------------------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training     | 1        | False  | Low-current controls are scored only by templates and ML models excluding that source run; high-current runs are absent from low-current training. |
| identifier_features_excluded                           | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.                                                       |
| low_current_only_template_and_ml_sources               | 1        | False  | Traditional templates and overlay ML models are derived from low-current raw pulses only.                                                          |
| mean_synthetic_holdout_auc                             | 0.744994 | False  | Very high synthetic AUC would be suspicious because held-out runs contain independent residuals.                                                   |
| mean_shuffled_label_synthetic_auc                      | 0.456713 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                                                                      |
| actual_current_auc_from_ml_secondary_fraction          | 0.571015 | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                                                                     |
| actual_current_auc_from_traditional_secondary_fraction | 0.478928 | False  | Flagged if the traditional amplitude estimate nearly identifies beam current by itself.                                                            |

## Conclusion

Applying S10f low-current amplitude-binned/asymmetric templates to real candidate windows gives a matched high-current minus low-current secondary fraction of -0.03088 [-0.05045, -0.00938] and candidate-rate excess -0.01047 [-0.09733, 0.07765]. The low-current overlay-calibrated ML diagnostic gives secondary-fraction excess 0.00817 [-0.02230, 0.04002] for secondary fraction and -0.00122 [-0.01006, 0.01123] for overlap score, with candidate-rate excess 0.02310 [-0.02345, 0.08018]. The largest traditional positive stratum is amp_ge_4500 / s16_large_lowering / p02_early_pathology. Leakage probes do not flag identifier, current-label, or source-run leakage, but the estimate remains a pulse-shape diagnostic rather than a truth-labelled pile-up decomposition.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, `stratum_table.csv`, `method_summary.csv`, `method_stratum_summary.csv`, `run_stability_summary.csv`, `sampled_event_scores.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this folder.

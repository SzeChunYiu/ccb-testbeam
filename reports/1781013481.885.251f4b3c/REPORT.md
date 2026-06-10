# S10e: real-candidate two-pulse validation

- **Ticket:** `1781013481.885.251f4b3c`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw B-stack ROOT scoring runs 44-57 plus S10d reproduction/calibration runs 31-42 and 58-65; no Monte Carlo.
- **Split:** every scored event is predicted by a model/template library with that event's source run held out; CIs resample held-out source runs within current group.

## Reproduction first

The S10 raw-ROOT topology gate was reproduced before the real-candidate study. Downstream selected-event fraction is 0.02312 at 2 nA and 0.03341 at 20 nA; all six documented topology fractions pass the +/-0.0015 tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

The S10b live-time and S10d resolvability gates were rerun from raw ROOT before scoring real candidates.

| quantity                              |   report_value |   reproduced |        delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S10 assumed tau_eff combined Rmax MHz |        4.22222 |      4.22222 |  0           |        0.05 | True   |
| S10b measured traditional live10 ns   |      124.79    |    124.79    |  0.000183943 |        1    | True   |
| S10b measured-tau rescaled Rmax MHz   |        3.05    |      3.04511 | -0.00488869  |        0.05 | True   |

| quantity                                                  |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10d constrained_template_fit resolvable delay ns         |             60 |           60 |       0 |       1e-09 | True   |
| S10d compact_mlp_classifier_regressor resolvable delay ns |             20 |           20 |       0 |       1e-09 | True   |

## Strata and event scoring

The S10c strata are reused exactly: maximum selected-pulse amplitude, S16 adaptive-lowering bin, and P02-style topology. Full raw-ROOT counts define the matched-stratum weights; a capped within-run/within-stratum sample of 140 events supplies waveform-level scores. 8 matched strata pass the low/high count floor.

## Traditional method

For each held-out run, median empirical templates are built from all other runs. A bounded two-pulse fit scans first-pulse timing and pulse separation, solves primary amplitude, secondary amplitude, and baseline by least squares, and reports the secondary fraction A2/(A1+A2).

Matched high-minus-low secondary fraction: **0.03511** with run-bootstrap 95% CI **[0.01695, 0.05364]**.

| amp_bin       | baseline_bin       | p02_topology        |   low_n_scored |   high_n_scored |   low_mean |   high_mean |   high_minus_low |   match_weight |
|:--------------|:-------------------|:--------------------|---------------:|----------------:|-----------:|------------:|-----------------:|---------------:|
| amp_ge_4500   | s16_no_lowering    | p02_broad_late      |            280 |            1680 | 0.210865   | 0.251868    |      0.0410031   |     0.519603   |
| amp_2500_4500 | s16_no_lowering    | p02_broad_late      |            280 |            1680 | 0.461653   | 0.504589    |      0.0429361   |     0.293605   |
| amp_1000_2500 | s16_no_lowering    | p02_broad_late      |            239 |            1680 | 0.580824   | 0.588141    |      0.00731734  |     0.135738   |
| amp_1000_2500 | s16_large_lowering | p02_early_pathology |            132 |            1637 | 0          | 0.000527167 |      0.000527167 |     0.0230005  |
| amp_2500_4500 | s16_large_lowering | p02_early_pathology |             51 |            1412 | 0.00242648 | 0.0122227   |      0.00979624  |     0.00888657 |
| amp_ge_4500   | s16_large_lowering | p02_early_pathology |             45 |            1151 | 0.0637277  | 0.0762136   |      0.0124859   |     0.00784109 |
| amp_1000_2500 | s16_mild_lowering  | p02_broad_late      |             38 |             820 | 0.559832   | 0.517659    |     -0.0421728   |     0.00662136 |
| amp_ge_4500   | s16_large_lowering | p02_broad_late      |             27 |            1465 | 0.0298381  | 0.0901481   |      0.0603101   |     0.00470465 |

## ML residual diagnostic

The ML method is a run-held-out random-forest classifier/regressor trained on synthetic two-pulse overlays made only from training-run raw pulses. Features are normalized waveform samples and one-pulse template residual summaries; identifiers and current labels are excluded.

ML secondary-fraction high-minus-low: **0.00470** [-0.00037, 0.01077]. ML overlap-score high-minus-low: **0.02132** [0.00646, 0.03631]. Mean synthetic held-out AUC is 0.948; shuffled-label AUC is 0.472; delay MAE is 9.04 ns.

## Threshold validation

Each event is scored only by models/templates with that source run held out. The table below summarizes real-candidate rate and recovered delay/area behavior against the reproduced S10d resolvability thresholds.

| method      | group     | metric                                     |       value |      ci_low |    ci_high |   s10d_threshold_ns |
|:------------|:----------|:-------------------------------------------|------------:|------------:|-----------:|--------------------:|
| traditional | high_20nA | candidate_rate                             |  0.476703   |  0.466983   |  0.485816  |                  60 |
| traditional | high_20nA | candidate_fraction_delay_ge_s10d_threshold |  0.0127412  |  0.0100064  |  0.0158355 |                  60 |
| traditional | high_20nA | candidate_mean_recovered_delay_ns          | 26.6136     | 26.3551     | 26.846     |                  60 |
| traditional | high_20nA | candidate_mean_secondary_fraction          |  0.527584   |  0.523588   |  0.53137   |                  60 |
| traditional | low_2nA   | candidate_rate                             |  0.619048   |  0.586928   |  0.647436  |                  60 |
| traditional | low_2nA   | candidate_fraction_delay_ge_s10d_threshold |  0.00887574 |  0.00295858 |  0.0148299 |                  60 |
| traditional | low_2nA   | candidate_mean_recovered_delay_ns          | 27.1413     | 26.3158     | 27.9191    |                  60 |
| traditional | low_2nA   | candidate_mean_secondary_fraction          |  0.520539   |  0.510859   |  0.530748  |                  60 |
| ml          | high_20nA | candidate_rate                             |  0.0555315  |  0.0517072  |  0.0597831 |                  20 |
| ml          | high_20nA | candidate_fraction_delay_ge_s10d_threshold |  0.407813   |  0.373398   |  0.446875  |                  20 |
| ml          | high_20nA | candidate_mean_recovered_delay_ns          | 22.0868     | 21.0345     | 23.1008    |                  20 |
| ml          | high_20nA | candidate_mean_secondary_fraction          |  0.226943   |  0.220637   |  0.233381  |                  20 |
| ml          | low_2nA   | candidate_rate                             |  0.0283883  |  0.018315   |  0.0384615 |                  20 |
| ml          | low_2nA   | candidate_fraction_delay_ge_s10d_threshold |  0.0967742  |  0          |  0.225806  |                  20 |
| ml          | low_2nA   | candidate_mean_recovered_delay_ns          | 14.993      | 11.1688     | 19.5819    |                  20 |
| ml          | low_2nA   | candidate_mean_secondary_fraction          |  0.251118   |  0.222724   |  0.277157  |                  20 |

Run-level held-out stability is in `run_stability_summary.csv`; grouped ranges for the core delay/area rows are:

| group     | metric                  |   n_runs |   mean_value |   min_value |   max_value |   median_ci_width |
|:----------|:------------------------|---------:|-------------:|------------:|------------:|------------------:|
| high_20nA | ml_recovered_delay_ns   |       12 |    7.3183    |   5.49715   |   8.62816   |        0.943141   |
| high_20nA | ml_secondary_fraction   |       12 |    0.0623767 |   0.0507886 |   0.0701475 |        0.00740679 |
| high_20nA | trad_recovered_delay_ns |       12 |   30.0162    |  27.5661    |  32.7405    |        2.11934    |
| high_20nA | trad_secondary_fraction |       12 |    0.256569  |   0.225874  |   0.3262    |        0.0356748  |
| low_2nA   | ml_recovered_delay_ns   |        2 |    4.79989   |   3.23713   |   6.36266   |        0.886329   |
| low_2nA   | ml_secondary_fraction   |        2 |    0.0490555 |   0.0419871 |   0.0561238 |        0.00921165 |
| low_2nA   | trad_recovered_delay_ns |        2 |   28.3023    |  28.1374    |  28.4672    |        2.37784    |
| low_2nA   | trad_secondary_fraction |        2 |    0.330915  |   0.295385  |   0.366445  |        0.0440802  |

## Leakage review

| check                                              |    value | flag   | note                                                                                             |
|:---------------------------------------------------|---------:|:-------|:-------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training | 1        | False  | Each source run is scored only by templates and ML trained with that run removed.                |
| identifier_features_excluded                       | 1        | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.     |
| synthetic_train_source_runs_exclude_heldout        | 1        | False  | Fold diagnostics record the source runs used to generate synthetic ML training overlays.         |
| mean_synthetic_holdout_auc                         | 0.947997 | False  | Very high synthetic AUC would be suspicious because held-out runs contain independent residuals. |
| mean_shuffled_label_synthetic_auc                  | 0.472055 | False  | Shuffled-label training should not classify held-out synthetic overlays well.                    |
| actual_current_auc_from_ml_secondary_fraction      | 0.57115  | False  | Flagged if the ML amplitude estimate nearly identifies beam current by itself.                   |

## Conclusion

Replacing the S10c binary downstream label with a constrained two-pulse amplitude estimate gives a matched high-current minus low-current secondary fraction of 0.03511 [0.01695, 0.05364] from the traditional template fit. The ML residual diagnostic gives 0.00470 [-0.00037, 0.01077] for secondary fraction and 0.02132 [0.00646, 0.03631] for overlap score. The largest traditional positive stratum is amp_ge_4500 / s16_large_lowering / p02_broad_late. Run-held-out threshold validation is reported by current group and source run. Leakage probes do not flag identifier or source-run leakage, but the estimate remains a pulse-shape diagnostic rather than a truth-labelled pile-up decomposition.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, `stratum_table.csv`, `method_summary.csv`, `method_stratum_summary.csv`, `sampled_event_scores.csv`, `fold_diagnostics.csv`, `run_stability_summary.csv`, `threshold_validation_summary.csv`, `leakage_checks.csv`, and figures are in this folder.

# Study report: S03b - q_template-only timing-tail cuts

- **Ticket:** 1781006575.2877.41492e09
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT files plus S01 `q_template_per_pulse.csv.gz`
- **Split:** 5-fold GroupKFold by run across analysis runs; all metrics are out-of-fold
- **Command:** `.venv/bin/python /home/billy/.tb-workers/testbeam-laptop-2/reports/1781006575.2877.41492e09/s03b_qtemplate_timing_tail_cuts.py`

## Question
Do q_template-only clean-timing cuts predict held-out downstream timing tails without using downstream span, all-span, pair residuals, or B2 displacement as model inputs?

## Raw-ROOT reproduction first
The S00 selected-pulse gate was rerun from raw ROOT before joining `q_template`.

| quantity              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_pulses |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib        |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis     |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib       |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis    |         125096 |       125096 |       0 |           0 | True   |

The downstream-tail labels were then freshly derived from raw CFD20 times: events with at least two downstream B4/B6/B8 hits are clean if downstream span `<5 ns`, tail if downstream span `>10 ns`, and otherwise excluded. This produced 9201 labelled events across all scanned runs. The head-to-head benchmark uses only analysis-run labels, where the S01 q_template input is out-of-sample with respect to calibration-template construction: 7579 labelled events, 7389 clean and 190 tail.

## Methods
Traditional: a fold-local q_template-only cut scan over downstream/all mean, max, and p90 summaries. Thresholds are chosen on train runs for about 95% clean retention, then applied unchanged to held-out runs.

ML: a random forest on q_template-only summaries (`q_B2, q_B4, q_B6, q_B8, q_downstream_mean, q_downstream_max, q_downstream_p90, q_downstream_std, q_all_mean, q_all_max`), with hyperparameters selected by out-of-fold run CV. Missing q values are filled with train-fold medians only.

Best ML grid row:

|   max_depth |   min_samples_leaf |   n_estimators |   roc_auc |   average_precision |    brier |
|------------:|-------------------:|---------------:|----------:|--------------------:|---------:|
|           5 |                 20 |            300 |  0.842535 |            0.303658 | 0.108256 |

Fold cuts:

|   fold | test_runs               |   test_tail |   test_clean | traditional_cut_feature   |   traditional_cut_direction |   traditional_cut_threshold |
|-------:|:------------------------|------------:|-------------:|:--------------------------|----------------------------:|----------------------------:|
|      1 | 61                      |          45 |         1614 | q_downstream_max          |                           1 |                    0.509297 |
|      2 | 44,48,51,59             |          37 |         1446 | q_downstream_max          |                           1 |                    0.505023 |
|      3 | 47,55,58,62             |          28 |         1453 | q_downstream_max          |                           1 |                    0.487694 |
|      4 | 49,53,60                |          38 |         1436 | q_downstream_max          |                           1 |                    0.484421 |
|      5 | 45,50,52,54,56,57,63,65 |          42 |         1440 | q_downstream_max          |                           1 |                    0.504297 |

## Held-out benchmark
Metrics are run-bootstrap 95% CIs over out-of-fold predictions.

| method                        |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high | note                                                                    |     brier |   brier_ci_low |   brier_ci_high |
|:------------------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|:------------------------------------------------------------------------|----------:|---------------:|----------------:|
| traditional_q_template_only   |  0.740797 |         0.685844 |          0.770695 |           0.0830552 |                  0.0595399 |                   0.126669  | q_template-only standardized score plus fold-local clean-retention cuts |           |                |                 |
| ml_q_template_rf              |  0.842535 |         0.780163 |          0.877523 |           0.303658  |                  0.224493  |                   0.39363   | random forest using q_template-only event summaries                     | 0.108256  |      0.105441  |       0.110989  |
| leaky_downstream_span_control |  1        |         1        |          1        |           1         |                  1         |                   1         | deliberate forbidden-feature control using downstream span              | 0.0196809 |      0.0180075 |       0.0212575 |
| shuffled_label_control        |  0.508924 |         0.400123 |          0.608051 |           0.0330969 |                  0.022032  |                   0.0493448 | q_template RF trained on shuffled train labels                          | 0.222993  |      0.219863  |       0.226377  |

Operational q cut: tail rejection 0.137 [0.068, 0.203] at clean retention 0.950 [0.941, 0.959].

ML minus traditional q-template AUC = 0.102 [0.075, 0.121].

## Leakage hunt
| check                               | value              |
|:------------------------------------|:-------------------|
| q_feature_forbidden_columns         | none               |
| train_test_run_overlap_across_folds | 0                  |
| qtemplate_unmatched_events          | 0                  |
| leaky_downstream_span_auc           | 1.0                |
| shuffled_label_auc                  | 0.5089243612482282 |

The deliberate downstream-span control is near-perfect because it uses the label-defining variable. The admissible q-template methods are much weaker, and the shuffled-label control is near chance, so the result does not look suspiciously too good.

## Verdict
q_template alone is a weak but nonzero downstream-tail predictor. It rejects a minority of held-out timing tails at high clean retention and does not approach the forbidden downstream-span oracle. Treat q_template as a conservative shape-quality veto, not as a replacement for timing residual diagnostics.

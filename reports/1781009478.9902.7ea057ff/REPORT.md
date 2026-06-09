# Study report: S05b - A-stack external-control covariance on loose tiers

- **Study ID:** S05b
- **Ticket:** 1781009478.9902.7ea057ff
- **Author (worker label):** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `86e93ac25967ce93cdc3987324c1fab0aee64558`
- **Config:** `configs/s05b_loose_astack_external_control.yaml`

## 0. Question

Does the S05a null external-control result come from low A/B coincidence statistics rather than a true absence of event-level A-stack control information?

The analysis uses raw ROOT only. Before modeling, it reproduces the original S05a/S18 raw count anchors at the nominal `>1000 ADC` pulse gate. It then rebuilds matched `(run, EVENTNO)` A/B pulse features and counts nested raw pulse-quality tiers: `500`, `750`, and `1000 ADC`. The run-held-out model comparison is run on the primary loose tier (`500 ADC`) and the nominal comparison tier (`1000 ADC`).

## 1. Raw reproduction gate

| quantity                                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses                         |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses            |         125096 |       125096 |       0 |           0 | True   |
| astack_sample_iii_analysis_events_with_selected |           7168 |         7168 |       0 |           0 | True   |
| astack_sample_iii_analysis_selected_pulses      |           9682 |         9682 |       0 |           0 | True   |
| astack_sample_iv_analysis_events_with_selected  |            767 |          767 |       0 |           0 | True   |
| astack_sample_iv_analysis_selected_pulses       |            894 |          894 |       0 |           0 | True   |

## 2. Low-threshold tier statistics

| tier        |   amplitude_cut_adc |   n_pair_rows |   n_runs |   n_unique_events |   n_a_any_pair_rows |   n_a_both_pair_rows |   n_a_any_events |   n_a_both_events |
|:------------|--------------------:|--------------:|---------:|------------------:|--------------------:|---------------------:|-----------------:|------------------:|
| loose500    |                 500 |         74176 |       21 |             32207 |                 614 |                  158 |              307 |                94 |
| loose750    |                 750 |         69081 |       21 |             29449 |                 478 |                  128 |              225 |                74 |
| nominal1000 |                1000 |         65457 |       21 |             27751 |                 380 |                  114 |              187 |                62 |

The loose `500 ADC` tier is the primary stress test because it maximizes A/B coincidence statistics while preserving the same raw waveform feature extraction and run-held-out evaluation. The `750 ADC` tier is included as an intermediate count check but not modeled to keep the held-out ML workload bounded.

## 3. Traditional and ML methods

Traditional method: grouped-run-heldout Ridge regression with pair identity plus B-pair amplitude/shape features. The A-control version adds event-matched A1/A3 amplitude, peak, tail, CFD20 time, A3-A1 residual, mean A time, and A amplitude-balance terms. It receives no run id or event id.

ML method: grouped-run-heldout bounded ExtraTrees regression with the same B-only and B-plus-A feature split. Each ML fit uses a deterministic cap of 6,000 training rows per fold; all reported metrics are still computed on complete held-out runs.

| tier        | method                  | subset         |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                             |
|:------------|:------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:-----------------------------------------------------------------|
| loose500    | traditional_b_only      | all            |         74176 |       21 |      7.98329 |             7.41863 |              9.34187 |       12.8512 |              0.494742 | run-held-out Ridge using B pair amplitude/shape features         |
| loose500    | traditional_b_only      | A_any_selected |           614 |       20 |      9.08632 |             7.17619 |             10.7422  |       13.5466 |              0.540717 | run-held-out Ridge using B pair amplitude/shape features         |
| loose500    | traditional_b_plus_a    | all            |         74176 |       21 |      7.98416 |             7.32265 |              9.09043 |       12.8526 |              0.494607 | same Ridge plus event-matched A-stack controls                   |
| loose500    | traditional_b_plus_a    | A_any_selected |           614 |       20 |      9.13151 |             7.03435 |             10.9995  |       13.5872 |              0.550489 | same Ridge plus event-matched A-stack controls                   |
| loose500    | ml_extra_trees_b_only   | all            |         74176 |       21 |      2.97572 |             2.51684 |              4.34815 |       11.1595 |              0.216431 | run-held-out bounded ExtraTrees using B features only            |
| loose500    | ml_extra_trees_b_only   | A_any_selected |           614 |       20 |      5.19827 |             3.26192 |              7.223   |       12.1293 |              0.312704 | run-held-out bounded ExtraTrees using B features only            |
| loose500    | ml_extra_trees_b_plus_a | all            |         74176 |       21 |      3.11474 |             2.60441 |              7.29193 |       11.1422 |              0.230748 | run-held-out bounded ExtraTrees using B features plus A controls |
| loose500    | ml_extra_trees_b_plus_a | A_any_selected |           614 |       20 |      5.07948 |             3.58809 |              6.53538 |       11.4357 |              0.31759  | run-held-out bounded ExtraTrees using B features plus A controls |
| nominal1000 | traditional_b_only      | all            |         65457 |       21 |      7.6175  |             6.92764 |              9.06104 |       12.6251 |              0.471317 | run-held-out Ridge using B pair amplitude/shape features         |
| nominal1000 | traditional_b_only      | A_any_selected |           380 |       17 |      9.06092 |             7.27791 |             13.0526  |       15.2912 |              0.557895 | run-held-out Ridge using B pair amplitude/shape features         |
| nominal1000 | traditional_b_plus_a    | all            |         65457 |       21 |      7.61508 |             6.91943 |              9.48509 |       12.6272 |              0.471118 | same Ridge plus event-matched A-stack controls                   |
| nominal1000 | traditional_b_plus_a    | A_any_selected |           380 |       17 |      8.95612 |             7.23429 |             14.1841  |       15.2989 |              0.560526 | same Ridge plus event-matched A-stack controls                   |
| nominal1000 | ml_extra_trees_b_only   | all            |         65457 |       21 |      2.7156  |             2.34015 |              4.45771 |       11.0561 |              0.200605 | run-held-out bounded ExtraTrees using B features only            |
| nominal1000 | ml_extra_trees_b_only   | A_any_selected |           380 |       17 |      5.24069 |             3.53224 |              8.03144 |       15.2436 |              0.339474 | run-held-out bounded ExtraTrees using B features only            |
| nominal1000 | ml_extra_trees_b_plus_a | all            |         65457 |       21 |      2.62873 |             2.29332 |              3.59061 |       10.5471 |              0.192691 | run-held-out bounded ExtraTrees using B features plus A controls |
| nominal1000 | ml_extra_trees_b_plus_a | A_any_selected |           380 |       17 |      5.02683 |             3.21951 |              6.721   |       11.9197 |              0.331579 | run-held-out bounded ExtraTrees using B features plus A controls |

Bootstrap deltas are B-plus-A minus B-only on sigma68; negative means A controls narrowed held-out residuals.

| tier        | comparison                             |   ci_low_ns |   ci_high_ns |   p_value |
|:------------|:---------------------------------------|------------:|-------------:|----------:|
| loose500    | traditional_b_plus_a_minus_b_only      |  -0.021555  |   0.0194212  |      0.9  |
| loose500    | ml_b_plus_a_minus_ml_b_only            |   0.0481534 |   0.615461   |      0    |
| loose500    | ml_b_plus_a_minus_traditional_b_plus_a |  -5.1427    |  -3.71261    |      0    |
| nominal1000 | traditional_b_plus_a_minus_b_only      |  -0.0205974 |   0.018869   |      0.95 |
| nominal1000 | ml_b_plus_a_minus_ml_b_only            |  -0.380756  |  -0.00276543 |      0.04 |
| nominal1000 | ml_b_plus_a_minus_traditional_b_plus_a |  -5.61071   |  -4.45938    |      0    |

Run-held-out fold sizes and Ridge settings:

| tier        | heldout_runs      |   n_pair_rows |   ridge_alpha_b |   ridge_alpha_b_plus_a |   ml_train_rows |   extra_trees_rmse_b |   extra_trees_rmse_b_plus_a |
|:------------|:------------------|--------------:|----------------:|-----------------------:|----------------:|---------------------:|----------------------------:|
| loose500    | 47 52 58 61       |         14917 |              10 |                     10 |            6000 |              9.47663 |                     9.22802 |
| loose500    | 46 53 55 59       |         14798 |              10 |                     10 |            6000 |             10.4276  |                    10.5629  |
| loose500    | 48 57 62          |         14817 |              10 |                     10 |            6000 |             10.7824  |                    10.6103  |
| loose500    | 44 50 54 60       |         14786 |              10 |                     10 |            6000 |              9.57612 |                     9.54103 |
| loose500    | 45 49 51 56 63 65 |         14858 |              10 |                     10 |            6000 |             14.5971  |                    14.7571  |
| nominal1000 | 47 48 61          |         13105 |              10 |                     10 |            6000 |              8.22089 |                     8.84027 |
| nominal1000 | 46 49 51 59       |         13002 |              10 |                     10 |            6000 |             10.151   |                    10.6492  |
| nominal1000 | 52 55 58 62       |         13209 |              10 |                     10 |            6000 |              9.95587 |                     9.53253 |
| nominal1000 | 44 50 53 60       |         13101 |              10 |                     10 |            6000 |              8.7682  |                     8.80198 |
| nominal1000 | 45 54 56 57 63 65 |         13040 |              10 |                     10 |            6000 |             16.1717  |                    13.9224  |

## 4. Leakage checks

| tier        | check                       |   sigma68_ns | interpretation                                             | trigger                    |
|:------------|:----------------------------|-------------:|:-----------------------------------------------------------|:---------------------------|
| loose500    | actual_ml_b_plus_a          |      3.11474 | nominal run-held-out ML residual width                     | primary_loose_tier         |
| loose500    | runwise_shuffled_a_controls |      3.01806 | A controls lose event matching but preserve run marginals  | primary_loose_tier         |
| loose500    | intentional_target_echo     |      0       | positive leakage sentinel; should be unrealistically small | primary_loose_tier         |
| nominal1000 | actual_ml_b_plus_a          |      2.62873 | nominal run-held-out ML residual width                     | ml_a_control_ci_below_zero |
| nominal1000 | runwise_shuffled_a_controls |      2.664   | A controls lose event matching but preserve run marginals  | ml_a_control_ci_below_zero |
| nominal1000 | intentional_target_echo     |      0       | positive leakage sentinel; should be unrealistically small | ml_a_control_ci_below_zero |

The primary loose tier always gets a runwise shuffled-A control. Other tiers trigger that heavier leakage hunt only if the ML A-control delta CI is wholly below zero. The shuffled-A control preserves run marginals but breaks event matching.

## 5. Residual covariance

Compact covariance summary by tier and method; the full table is `pair_covariance_by_run.csv`.

| tier        | method                  |   n_covariances |   median_abs_cov_ns2 |   max_abs_cov_ns2 |
|:------------|:------------------------|----------------:|---------------------:|------------------:|
| loose500    | ml_extra_trees_b_only   |             300 |              18.1949 |           609.336 |
| loose500    | ml_extra_trees_b_plus_a |             300 |              17.5448 |           496.573 |
| loose500    | raw_pair_median         |             300 |              22.5524 |          2548.15  |
| loose500    | traditional_b_only      |             300 |              46.2101 |           538.31  |
| loose500    | traditional_b_plus_a    |             300 |              46.2519 |           538.672 |
| nominal1000 | ml_extra_trees_b_only   |             300 |              14.0543 |           727.528 |
| nominal1000 | ml_extra_trees_b_plus_a |             300 |              13.7613 |           773.011 |
| nominal1000 | raw_pair_median         |             300 |              15.1896 |          2219.75  |
| nominal1000 | traditional_b_only      |             300 |              44.7011 |           605.708 |
| nominal1000 | traditional_b_plus_a    |             300 |              44.6026 |           605.719 |

## 6. Finding

The loose tiers increase A/B coincidence statistics, but they do not convert A-stack controls into a statistically secure held-out reduction of B-stack pair residual width. The primary `500 ADC` tier remains consistent with the S05a null: A controls do not materially outperform B-only features, and the leakage control does not reveal a hidden event-matched A advantage. This supports a true null external-control result more than a low-statistics-only explanation.

## 7. Follow-up tickets

- S05d: repeat the loose-tier A-control test with sorted ROOT quality variables such as `hrdMaxTS` and trap summaries to test whether sorted pulse-shape cuts isolate better A/B coincidences.
- S05e: build a run-level A/B coincidence-rate model across current and target settings to separate beam-rate effects from detector-local B covariance.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05b_loose_astack_external_control.py --config configs/s05b_loose_astack_external_control.yaml
```

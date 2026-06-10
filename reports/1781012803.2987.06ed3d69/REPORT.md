# S01f: fold-local q_template leakage audit

- **Ticket:** 1781012803.2987.06ed3d69
- **Worker:** testbeam-laptop-1
- **Inputs:** raw B-stack ROOT only; no global S01 q_template table is read
- **Command:** `/home/billy/anaconda3/bin/python scripts/s01f_1781012803_fold_local_qtemplate.py --config configs/s01f_1781012803_2987_06ed3d69_fold_local_qtemplate.yaml`

## Question

Does the S03d q_template timing-tail signal survive when q_template median templates are rebuilt from train runs only inside each held-out-run fold?

## Raw-ROOT reproduction first

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The prior S03 run-65 timing references were regenerated from the same raw-derived pulse table before accepting the fold-local q-template benchmark.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

## Methods

For each Sample-II analysis run, the held-out run is excluded before building the q_template library. The library is the S01-style conventional median template: CFD20-aligned, peak-normalized waveforms binned by stave and fixed amplitude edges, with a train-stave fallback for sparse bins. Held-out q_template values are then scored against only that fold-local train-run library.

Traditional method: S03b monotone decreasing amplitude-bin timewalk residuals plus a train-run q-threshold scan constrained to keep at least 90% of train pairs.

ML method: RandomForest tail-veto score trained on train-run q summaries and pair identity only. It uses run-grouped OOF threshold selection, excludes run/event ids, amplitudes, timing values, waveform samples, and residual labels as features, and includes a shuffled-label control.

## Held-out fold-local q-template veto benchmark

| residual_method      | veto_method              |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|:-------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| s03b_monotone_binned | ml_q_rf                  | 1.67043 |  1.32175 |   1.95916 |              10328 |             0.0118125 |
| s03b_monotone_binned | no_veto                  | 1.64515 |  1.32175 |   1.9355  |              11460 |             0.019459  |
| s03b_monotone_binned | shuffled_ml_q_rf_control | 1.58852 |  1.31852 |   1.94446 |              11016 |             0.0196986 |
| s03b_monotone_binned | traditional_q_threshold  | 1.6905  |  1.41606 |   2.02277 |              10284 |             0.012252  |

Veto deltas are veto minus no-veto sigma68; negative means the veto narrowed the pair-residual table.

| residual_method      | veto_method              | metric                        |      value |     ci_low |   ci_high |
|:---------------------|:-------------------------|:------------------------------|-----------:|-----------:|----------:|
| s03b_monotone_binned | ml_q_rf                  | veto_minus_no_veto_sigma68_ns |  0.0252846 | -0.012965  | 0.0846256 |
| s03b_monotone_binned | shuffled_ml_q_rf_control | veto_minus_no_veto_sigma68_ns | -0.0566248 | -0.124881  | 0.0593891 |
| s03b_monotone_binned | traditional_q_threshold  | veto_minus_no_veto_sigma68_ns |  0.0453543 |  0.0227976 | 0.128505  |

Per-run held-out table:

|   heldout_run | residual_method      | veto_method              |   keep_fraction |   value |   ci_low |   ci_high |   tail_frac_abs_gt5ns |
|--------------:|:---------------------|:-------------------------|----------------:|--------:|---------:|----------:|----------------------:|
|            58 | s03b_monotone_binned | ml_q_rf                  |        0.922374 | 1.3214  |  1.3214  |   1.57985 |            0.019802   |
|            58 | s03b_monotone_binned | no_veto                  |        1        | 1.3214  |  1.3214  |   1.58688 |            0.0319635  |
|            58 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.990868 | 1.3214  |  1.3214  |   1.57879 |            0.0322581  |
|            58 | s03b_monotone_binned | traditional_q_threshold  |        0.917808 | 1.3214  |  1.3214  |   1.66534 |            0.0199005  |
|            59 | s03b_monotone_binned | ml_q_rf                  |        0.86588  | 1.5     |  1.37116 |   1.56166 |            0.00706357 |
|            59 | s03b_monotone_binned | no_veto                  |        1        | 1.5     |  1.36742 |   1.56166 |            0.0157274  |
|            59 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.894714 | 1.31166 |  1.31166 |   1.49275 |            0.0151367  |
|            59 | s03b_monotone_binned | traditional_q_threshold  |        0.898646 | 1.56166 |  1.4405  |   1.56296 |            0.00826446 |
|            60 | s03b_monotone_binned | ml_q_rf                  |        0.917079 | 1.23065 |  1.23065 |   1.26935 |            0.00539811 |
|            60 | s03b_monotone_binned | no_veto                  |        1        | 1.23065 |  1.23065 |   1.25    |            0.0156766  |
|            60 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.990099 | 1.23065 |  1.23065 |   1.25    |            0.0158333  |
|            60 | s03b_monotone_binned | traditional_q_threshold  |        0.901815 | 1.25    |  1.23065 |   1.36684 |            0.00548948 |
|            61 | s03b_monotone_binned | ml_q_rf                  |        0.896749 | 2.13818 |  2.10176 |   2.32123 |            0.0219124  |
|            61 | s03b_monotone_binned | no_veto                  |        1        | 2.10176 |  2.10176 |   2.25051 |            0.0310825  |
|            61 | s03b_monotone_binned | shuffled_ml_q_rf_control |        1        | 2.10176 |  2.10176 |   2.25    |            0.0310825  |
|            61 | s03b_monotone_binned | traditional_q_threshold  |        0.898535 | 2.20103 |  2.10176 |   2.35176 |            0.0222664  |
|            62 | s03b_monotone_binned | ml_q_rf                  |        0.931846 | 1.5     |  1.43743 |   1.63816 |            0.010195   |
|            62 | s03b_monotone_binned | no_veto                  |        1        | 1.43743 |  1.41232 |   1.58875 |            0.0144568  |
|            62 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.933499 | 1.5     |  1.43743 |   1.63816 |            0.0146018  |
|            62 | s03b_monotone_binned | traditional_q_threshold  |        0.897563 | 1.6134  |  1.44665 |   1.63816 |            0.00644271 |
|            63 | s03b_monotone_binned | ml_q_rf                  |        0.874775 | 1.5     |  1.31816 |   1.56436 |            0.0092688  |
|            63 | s03b_monotone_binned | no_veto                  |        1        | 1.43311 |  1.31436 |   1.56436 |            0.0198198  |
|            63 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.991892 | 1.43311 |  1.31436 |   1.56436 |            0.0199818  |
|            63 | s03b_monotone_binned | traditional_q_threshold  |        0.878378 | 1.52129 |  1.39797 |   1.56436 |            0.0102564  |
|            65 | s03b_monotone_binned | ml_q_rf                  |        0.929293 | 1.48068 |  1.31958 |   1.77024 |            0.00543478 |
|            65 | s03b_monotone_binned | no_veto                  |        1        | 1.56958 |  1.35928 |   1.81958 |            0.00505051 |
|            65 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.964646 | 1.47239 |  1.31958 |   1.79845 |            0.0052356  |
|            65 | s03b_monotone_binned | traditional_q_threshold  |        0.893939 | 1.48896 |  1.31958 |   1.81958 |            0.00564972 |

## Veto policies

|   heldout_run | residual_method      | veto_method              | feature          |   threshold |   threshold_quantile |   train_keep_fraction |   train_tail_frac_abs_gt5ns |   train_sigma68_ns |    oof_auc |   shuffled |
|--------------:|:---------------------|:-------------------------|:-----------------|------------:|---------------------:|----------------------:|----------------------------:|-------------------:|-----------:|-----------:|
|            58 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.185317 |                0.9   |              0.900009 |                  0.0107739  |            1.72937 | nan        |        nan |
|            58 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.490711 |                0.9   |              0.900009 |                  0.00978551 |            1.68338 |   0.792045 |          0 |
|            58 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.542211 |                0.975 |              0.975002 |                  0.0180657  |            1.68482 |   0.463144 |          1 |
|            59 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.184709 |                0.9   |              0.900011 |                  0.00993458 |            1.6905  | nan        |        nan |
|            59 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.478107 |                0.9   |              0.900011 |                  0.00944996 |            1.54833 |   0.807053 |          0 |
|            59 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.50294  |                0.9   |              0.900011 |                  0.0178095  |            1.56166 |   0.485459 |          1 |
|            60 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.172754 |                0.9   |              0.900066 |                  0.0100824  |            1.52893 | nan        |        nan |
|            60 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.544855 |                0.925 |              0.924967 |                  0.0108878  |            1.5     |   0.793029 |          0 |
|            60 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.563567 |                0.99  |              0.989929 |                  0.0179989  |            1.48871 |   0.459139 |          1 |
|            61 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.184291 |                0.9   |              0.900012 |                  0.00949326 |            1.55554 | nan        |        nan |
|            61 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.535026 |                0.9   |              0.900012 |                  0.00833868 |            1.50369 |   0.840461 |          0 |
|            61 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.599805 |                0.99  |              0.989955 |                  0.0169116  |            1.5     |   0.49716  |          1 |
|            62 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.181112 |                0.9   |              0.9001   |                  0.0120452  |            1.68743 | nan        |        nan |
|            62 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.514664 |                0.925 |              0.924992 |                  0.0105251  |            1.64074 |   0.801844 |          0 |
|            62 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.555014 |                0.95  |              0.949994 |                  0.0192151  |            1.68743 |   0.532623 |          1 |
|            63 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.181702 |                0.9   |              0.900097 |                  0.0110562  |            1.68311 | nan        |        nan |
|            63 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.495806 |                0.9   |              0.9      |                  0.00987654 |            1.61165 |   0.802878 |          0 |
|            63 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.567552 |                0.99  |              0.990048 |                  0.0189324  |            1.59366 |   0.474694 |          1 |
|            65 | s03b_monotone_binned | traditional_q_threshold  | q_downstream_max |    0.231222 |                0.9   |              0.900107 |                  0.0124297  |            1.68098 | nan        |        nan |
|            65 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.540311 |                0.925 |              0.924969 |                  0.0104637  |            1.62043 |   0.803195 |          0 |
|            65 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.532385 |                0.925 |              0.924969 |                  0.0188154  |            1.68098 |   0.508405 |          1 |

## Leakage checks

|   heldout_run | residual_method      | check                              |        value | flag   |
|--------------:|:---------------------|:-----------------------------------|-------------:|:-------|
|            58 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            58 | all                  | q_template_train_rows_only         | 11241        | False  |
|            58 | all                  | q_template_heldout_rows_scored     |   219        | False  |
|            58 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            58 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.65443  | False  |
|            58 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            58 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.792045 | False  |
|            58 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.463144 | False  |
|            59 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            59 | all                  | q_template_train_rows_only         |  9171        | False  |
|            59 | all                  | q_template_heldout_rows_scored     |  2289        | False  |
|            59 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            59 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.9894   | False  |
|            59 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            59 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.807053 | False  |
|            59 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.485459 | False  |
|            60 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            60 | all                  | q_template_train_rows_only         |  9036        | False  |
|            60 | all                  | q_template_heldout_rows_scored     |  2424        | False  |
|            60 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            60 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.74865  | False  |
|            60 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            60 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.793029 | False  |
|            60 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.459139 | False  |
|            61 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            61 | all                  | q_template_train_rows_only         |  8661        | False  |
|            61 | all                  | q_template_heldout_rows_scored     |  2799        | False  |
|            61 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            61 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.70351  | False  |
|            61 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            61 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.840461 | False  |
|            61 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.49716  | False  |
|            62 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            62 | all                  | q_template_train_rows_only         |  9039        | False  |
|            62 | all                  | q_template_heldout_rows_scored     |  2421        | False  |
|            62 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            62 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.94815  | False  |
|            62 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            62 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.801844 | False  |
|            62 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.532623 | False  |
|            63 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            63 | all                  | q_template_train_rows_only         | 10350        | False  |
|            63 | all                  | q_template_heldout_rows_scored     |  1110        | False  |
|            63 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            63 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.82703  | False  |
|            63 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            63 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.802878 | False  |
|            63 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.474694 | False  |
|            65 | all                  | s03_train_heldout_event_id_overlap |     0        | False  |
|            65 | all                  | q_template_train_rows_only         | 11262        | False  |
|            65 | all                  | q_template_heldout_rows_scored     |   198        | False  |
|            65 | all                  | q_veto_forbidden_feature_overlap   |     0        | False  |
|            65 | s03b_monotone_binned | s03b_shuffled_target_sigma68       |     2.90565  | False  |
|            65 | s03b_monotone_binned | train_heldout_event_id_overlap     |     0        | False  |
|            65 | s03b_monotone_binned | ml_q_rf_oof_auc                    |     0.803195 | False  |
|            65 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           |     0.508405 | False  |

## Verdict

Fold-local q_template construction removes the global S01 calibration dependency and does not yield a statistically secure S03b timing-tail improvement. S03b no-veto sigma68 is 1.645 ns; traditional fold-local q-veto delta is 0.045 ns [0.023, 0.129], and ML fold-local q-veto delta is 0.025 ns [-0.013, 0.085]. Leakage flags: 0.

## Artifacts

`reproduction_match_table.csv`, `run65_reproduction.csv`, `q_veto_per_run_metrics.csv`, `q_veto_pooled_run_bootstrap.csv`, `q_veto_delta_bootstrap.csv`, `q_veto_policy_by_fold.csv`, `fold_local_template_bin_counts.csv`, `heldout_pair_q_veto_residuals.csv`, `leakage_checks.csv`, CV scans, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

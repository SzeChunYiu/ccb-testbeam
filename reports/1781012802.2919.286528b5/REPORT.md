# Study report: S03d - q_template pair-residual veto

- **Ticket:** 1781012802.2919.286528b5
- **Worker:** testbeam-laptop-2
- **Inputs:** raw B-stack ROOT plus S01 q_template table
- **Command:** `/home/billy/anaconda3/bin/python scripts/s03d_1781012802_qtemplate_pair_veto.py --config configs/s03d_1781012802_qtemplate_pair_veto.yaml`

## Question

Do q_template veto thresholds improve S03/S04-style pair-residual resolution tail tables when evaluated at pair level with run-held-out bootstrap CIs?

## Raw-ROOT reproduction first

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The prior S03 run-65 reference numbers were then regenerated from the same raw-derived pulse table.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

## Methods

Each Sample-II analysis run is held out in turn. The residual table is built from downstream B4/B6/B8 all-hit events and the three downstream pairs. The strong traditional residual model is the S03b monotone decreasing amplitude-bin timewalk correction. q_template vetoes are trained only on the other runs and applied unchanged to the held-out run.

Traditional q veto: train-run threshold scan over pair and downstream q_template summaries, constrained to keep at least 90% of train pairs.

ML method: a run-CV RandomForest q-template veto score using q_template summaries plus pair identity only. It excludes run, event id, residual value, timing columns, amplitudes, and waveform samples. The score threshold is selected on train-run out-of-fold scores with the same 90% keep constraint.

## Held-out q-template veto benchmark

| residual_method      | veto_method              |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|:-------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| s03b_monotone_binned | ml_q_rf                  | 1.58011 |  1.32175 |   1.90729 |              10221 |             0.0121319 |
| s03b_monotone_binned | no_veto                  | 1.64515 |  1.32175 |   1.94411 |              11460 |             0.019459  |
| s03b_monotone_binned | shuffled_ml_q_rf_control | 1.62884 |  1.32175 |   1.94188 |              11275 |             0.0193348 |
| s03b_monotone_binned | traditional_q_threshold  | 1.72406 |  1.42272 |   2.06081 |              10344 |             0.0131477 |

Veto deltas are veto minus no-veto sigma68; negative would mean the veto narrowed the pair-residual table.

| residual_method      | veto_method              | metric                        |      value |     ci_low |   ci_high |
|:---------------------|:-------------------------|:------------------------------|-----------:|-----------:|----------:|
| s03b_monotone_binned | ml_q_rf                  | veto_minus_no_veto_sigma68_ns | -0.0650436 | -0.0733132 | 0.0967579 |
| s03b_monotone_binned | shuffled_ml_q_rf_control | veto_minus_no_veto_sigma68_ns | -0.01631   | -0.032813  | 0.042293  |
| s03b_monotone_binned | traditional_q_threshold  | veto_minus_no_veto_sigma68_ns |  0.0789124 |  0.0459977 | 0.227884  |

Per-run held-out table:

|   heldout_run | residual_method      | veto_method              |   keep_fraction |   value |   ci_low |   ci_high |   tail_frac_abs_gt5ns |
|--------------:|:---------------------|:-------------------------|----------------:|--------:|---------:|----------:|----------------------:|
|            58 | s03b_monotone_binned | ml_q_rf                  |        0.86758  | 1.3214  |  1.3214  |   1.41775 |            0.0263158  |
|            58 | s03b_monotone_binned | no_veto                  |        1        | 1.3214  |  1.3214  |   1.60064 |            0.0319635  |
|            58 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.995434 | 1.3214  |  1.3214  |   1.62276 |            0.0321101  |
|            58 | s03b_monotone_binned | traditional_q_threshold  |        0.890411 | 1.3214  |  1.3214  |   1.73484 |            0.0205128  |
|            59 | s03b_monotone_binned | ml_q_rf                  |        0.85059  | 1.5     |  1.31166 |   1.57002 |            0.00873138 |
|            59 | s03b_monotone_binned | no_veto                  |        1        | 1.5     |  1.37518 |   1.56166 |            0.0157274  |
|            59 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.991699 | 1.5     |  1.33146 |   1.56166 |            0.0145374  |
|            59 | s03b_monotone_binned | traditional_q_threshold  |        0.903014 | 1.56166 |  1.5     |   1.62116 |            0.00870827 |
|            60 | s03b_monotone_binned | ml_q_rf                  |        0.887376 | 1.23065 |  1.23065 |   1.36726 |            0.0055788  |
|            60 | s03b_monotone_binned | no_veto                  |        1        | 1.23065 |  1.23065 |   1.25    |            0.0156766  |
|            60 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.983498 | 1.23065 |  1.23065 |   1.28082 |            0.0159396  |
|            60 | s03b_monotone_binned | traditional_q_threshold  |        0.912129 | 1.25    |  1.23065 |   1.37977 |            0.0108548  |
|            61 | s03b_monotone_binned | ml_q_rf                  |        0.91497  | 2.13222 |  2.10176 |   2.16524 |            0.021476   |
|            61 | s03b_monotone_binned | no_veto                  |        1        | 2.10176 |  2.10176 |   2.23922 |            0.0310825  |
|            61 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.994641 | 2.10176 |  2.10176 |   2.24742 |            0.0308908  |
|            61 | s03b_monotone_binned | traditional_q_threshold  |        0.900679 | 2.25739 |  2.1021  |   2.40729 |            0.0226101  |
|            62 | s03b_monotone_binned | ml_q_rf                  |        0.91615  | 1.5     |  1.35747 |   1.54771 |            0.00901713 |
|            62 | s03b_monotone_binned | no_veto                  |        1        | 1.43743 |  1.36958 |   1.57595 |            0.0144568  |
|            62 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.963238 | 1.509   |  1.43743 |   1.63816 |            0.0150086  |
|            62 | s03b_monotone_binned | traditional_q_threshold  |        0.894672 | 1.62858 |  1.5     |   1.68049 |            0.00923361 |
|            63 | s03b_monotone_binned | ml_q_rf                  |        0.864865 | 1.43311 |  1.31436 |   1.56317 |            0.0104167  |
|            63 | s03b_monotone_binned | no_veto                  |        1        | 1.43311 |  1.31436 |   1.56436 |            0.0198198  |
|            63 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.999099 | 1.43311 |  1.31436 |   1.56436 |            0.0198377  |
|            63 | s03b_monotone_binned | traditional_q_threshold  |        0.893694 | 1.56341 |  1.43311 |   1.56689 |            0.0131048  |
|            65 | s03b_monotone_binned | ml_q_rf                  |        0.979798 | 1.57786 |  1.33049 |   1.81958 |            0.00515464 |
|            65 | s03b_monotone_binned | no_veto                  |        1        | 1.56958 |  1.33531 |   1.81958 |            0.00505051 |
|            65 | s03b_monotone_binned | shuffled_ml_q_rf_control |        0.89899  | 1.56958 |  1.31958 |   1.81958 |            0.00561798 |
|            65 | s03b_monotone_binned | traditional_q_threshold  |        0.969697 | 1.59994 |  1.38859 |   1.81958 |            0.00520833 |

## Veto policies

|   heldout_run | residual_method      | veto_method              | feature          |   threshold |   threshold_quantile |   train_keep_fraction |   train_tail_frac_abs_gt5ns |   train_sigma68_ns |    oof_auc |   shuffled |
|--------------:|:---------------------|:-------------------------|:-----------------|------------:|---------------------:|----------------------:|----------------------------:|-------------------:|-----------:|-----------:|
|            58 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.159787 |                0.9   |              0.900098 |                   0.0116624 |            1.75    | nan        |        nan |
|            58 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.487758 |                0.9   |              0.900009 |                   0.0111693 |            1.61584 |   0.771933 |          0 |
|            58 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.57076  |                0.975 |              0.975002 |                   0.0183394 |            1.59722 |   0.497517 |          1 |
|            59 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.162548 |                0.9   |              0.900011 |                   0.0111461 |            1.6905  | nan        |        nan |
|            59 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.47787  |                0.9   |              0.900011 |                   0.0115096 |            1.56166 |   0.763748 |          0 |
|            59 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.565678 |                0.99  |              0.989968 |                   0.0179535 |            1.56449 |   0.496799 |          1 |
|            60 | s03b_monotone_binned | traditional_q_threshold  | q_downstream_max |    0.215129 |                0.9   |              0.900066 |                   0.0119267 |            1.5542  | nan        |        nan |
|            60 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.526459 |                0.925 |              0.924967 |                   0.0107681 |            1.5     |   0.783997 |          0 |
|            60 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.580773 |                0.99  |              0.989929 |                   0.0181107 |            1.48065 |   0.493906 |          1 |
|            61 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.16103  |                0.9   |              0.900012 |                   0.0105196 |            1.67377 | nan        |        nan |
|            61 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.491195 |                0.9   |              0.900012 |                   0.0100064 |            1.58993 |   0.778733 |          0 |
|            61 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.568796 |                0.99  |              0.989955 |                   0.016795  |            1.5     |   0.534801 |          1 |
|            62 | s03b_monotone_binned | traditional_q_threshold  | q_downstream_max |    0.199626 |                0.9   |              0.9001   |                   0.0135202 |            1.68743 | nan        |        nan |
|            62 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.48453  |                0.925 |              0.924992 |                   0.0124387 |            1.58672 |   0.774911 |          0 |
|            62 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.537731 |                0.95  |              0.949994 |                   0.0196809 |            1.62548 |   0.50707  |          1 |
|            63 | s03b_monotone_binned | traditional_q_threshold  | q_pair_max       |    0.158444 |                0.9   |              0.9      |                   0.0117016 |            1.69187 | nan        |        nan |
|            63 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.48165  |                0.9   |              0.9      |                   0.0115942 |            1.56436 |   0.772484 |          0 |
|            63 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.57468  |                0.99  |              0.989952 |                   0.018739  |            1.57925 |   0.485263 |          1 |
|            65 | s03b_monotone_binned | traditional_q_threshold  | q_downstream_max |    0.208916 |                0.9   |              0.900107 |                   0.0131203 |            1.69543 | nan        |        nan |
|            65 | s03b_monotone_binned | ml_q_rf                  | nan              |    0.498599 |                0.925 |              0.924969 |                   0.0123836 |            1.67591 |   0.767992 |          0 |
|            65 | s03b_monotone_binned | shuffled_ml_q_rf_control | nan              |    0.528034 |                0.925 |              0.924969 |                   0.0184314 |            1.65657 |   0.484325 |          1 |

## Leakage checks

|   heldout_run | residual_method      | check                              |    value | flag   |
|--------------:|:---------------------|:-----------------------------------|---------:|:-------|
|            58 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            58 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            58 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.65443  | False  |
|            58 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            58 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.771933 | False  |
|            58 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.497517 | False  |
|            59 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            59 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            59 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.9894   | False  |
|            59 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            59 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.763748 | False  |
|            59 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.496799 | False  |
|            60 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            60 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            60 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.74865  | False  |
|            60 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            60 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.783997 | False  |
|            60 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.493906 | False  |
|            61 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            61 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            61 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.70351  | False  |
|            61 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            61 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.778733 | False  |
|            61 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.534801 | False  |
|            62 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            62 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            62 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.94815  | False  |
|            62 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            62 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.774911 | False  |
|            62 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.50707  | False  |
|            63 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            63 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            63 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.82703  | False  |
|            63 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            63 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.772484 | False  |
|            63 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.485263 | False  |
|            65 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            65 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            65 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.90565  | False  |
|            65 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            65 | s03b_monotone_binned | ml_q_rf_oof_auc                    | 0.767992 | False  |
|            65 | s03b_monotone_binned | shuffled_ml_q_rf_oof_auc           | 0.484325 | False  |

No admissible q-veto feature contains run id, event id, timing values, pair residuals, or residual labels. The shuffled-label RF q-veto control is included for every fold because any strong q-template improvement would otherwise be suspicious.

## Verdict

The pair-level q_template veto does not produce a statistically secure residual-tail improvement. S03b no-veto sigma68 is 1.645 ns; traditional q-veto delta is 0.079 ns [0.046, 0.228], and ML q-veto delta is -0.065 ns [-0.073, 0.097]. Leakage flags: 0.

## Artifacts

`reproduction_match_table.csv`, `run65_reproduction.csv`, `q_veto_per_run_metrics.csv`, `q_veto_pooled_run_bootstrap.csv`, `q_veto_delta_bootstrap.csv`, `q_veto_policy_by_fold.csv`, `heldout_pair_q_veto_residuals.csv`, `leakage_checks.csv`, CV scans, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

## Follow-up tickets

- S04e: apply the same q-template veto table to full B2-containing S04/S05 pair residuals and report topology-specific tail migration.
- P02f: replace scalar q_template with learned shape-atom veto scores and test whether any gain survives the same pair-level run-held-out protocol.

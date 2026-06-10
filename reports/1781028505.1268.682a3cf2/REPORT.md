# P02f: learned shape-atom veto scores versus q_template tails

- **Ticket:** 1781028505.1268.682a3cf2
- **Worker:** testbeam-laptop-4
- **Inputs:** raw B-stack ROOT plus S01 q_template/autoencoder table
- **Command:** `/home/billy/anaconda3/bin/python scripts/p02f_1781028505_1268_682a3cf2_shape_atom_veto.py --config configs/p02f_1781028505_1268_682a3cf2_shape_atom_veto.yaml`

## Question

Do learned shape-atom or anomaly scores outperform scalar q_template as vetoes for pair-level timing residual tails without timing leakage?

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

Each Sample-II analysis run is held out in turn. The residual table is built from downstream B4/B6/B8 all-hit events and the three downstream pairs. The strong timing baseline is the S03b monotone decreasing amplitude-bin timewalk correction. Veto thresholds are selected only on the other runs and applied unchanged to the held-out run.

Traditional method: train-run threshold scan over scalar q_template plus hand-built peak-edge, late-tail, saturation, secondary-peak, and combined shape scores, constrained to keep at least 90% of train pairs.

ML methods: a run-CV RandomForest tail score over learned/derived shape atoms and an unsupervised IsolationForest anomaly score on the same atoms. Features exclude run, event id, residual value, timing columns, raw amplitudes, and scalar q_template; shuffled-label RF and topology-only RF controls are included.

## Held-out shape-veto benchmark

| residual_method      | veto_method                  |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:---------------------|:-----------------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| s03b_monotone_binned | ml_shape_iforest             | 1.69002 |  1.34491 |   2       |              10522 |             0.0131154 |
| s03b_monotone_binned | ml_shape_rf                  | 1.56166 |  1.31436 |   1.90729 |              10235 |             0.0104543 |
| s03b_monotone_binned | no_veto                      | 1.64515 |  1.32175 |   1.94338 |              11460 |             0.019459  |
| s03b_monotone_binned | shuffled_ml_shape_rf_control | 1.60778 |  1.32157 |   1.91413 |              11238 |             0.0196654 |
| s03b_monotone_binned | topology_only_rf_control     | 1.62467 |  1.32175 |   1.93835 |              11387 |             0.0194081 |
| s03b_monotone_binned | traditional_q_hand_threshold | 1.72406 |  1.42898 |   2.05297 |              10344 |             0.0131477 |

Veto deltas are veto minus no-veto sigma68; negative would mean the veto narrowed the pair-residual table.

| residual_method      | veto_method                  | metric                        |      value |      ci_low |   ci_high |
|:---------------------|:-----------------------------|:------------------------------|-----------:|------------:|----------:|
| s03b_monotone_binned | ml_shape_iforest             | veto_minus_no_veto_sigma68_ns |  0.0448724 |  0.00124514 | 0.188366  |
| s03b_monotone_binned | ml_shape_rf                  | veto_minus_no_veto_sigma68_ns | -0.0834861 | -0.12884    | 0.0623202 |
| s03b_monotone_binned | shuffled_ml_shape_rf_control | veto_minus_no_veto_sigma68_ns | -0.0373739 | -0.0441183  | 0.0184018 |
| s03b_monotone_binned | topology_only_rf_control     | veto_minus_no_veto_sigma68_ns | -0.0204819 | -0.0535777  | 0.0226888 |
| s03b_monotone_binned | traditional_q_hand_threshold | veto_minus_no_veto_sigma68_ns |  0.0789124 |  0.0395743  | 0.234734  |

Per-run held-out table:

|   heldout_run | residual_method      | veto_method                  |   keep_fraction |    value |   ci_low |   ci_high |   tail_frac_abs_gt5ns |
|--------------:|:---------------------|:-----------------------------|----------------:|---------:|---------:|----------:|----------------------:|
|            58 | s03b_monotone_binned | ml_shape_iforest             |        0.680365 | 1.36999  | 1.3214   |  1.84061  |            0.0268456  |
|            58 | s03b_monotone_binned | ml_shape_rf                  |        0.917808 | 1.3214   | 1.3214   |  1.5      |            0.0199005  |
|            58 | s03b_monotone_binned | no_veto                      |        1        | 1.3214   | 1.3214   |  1.59178  |            0.0319635  |
|            58 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        0.990868 | 1.3214   | 1.3214   |  1.64612  |            0.0322581  |
|            58 | s03b_monotone_binned | topology_only_rf_control     |        0.666667 | 0.684815 | 0.438639 |  0.907949 |            0.0273973  |
|            58 | s03b_monotone_binned | traditional_q_hand_threshold |        0.890411 | 1.3214   | 1.3214   |  1.65782  |            0.0205128  |
|            59 | s03b_monotone_binned | ml_shape_iforest             |        0.935343 | 1.51261  | 1.4405   |  1.62116  |            0.00934143 |
|            59 | s03b_monotone_binned | ml_shape_rf                  |        0.861948 | 1.31166  | 1.31166  |  1.37116  |            0.00405474 |
|            59 | s03b_monotone_binned | no_veto                      |        1        | 1.5      | 1.38061  |  1.56166  |            0.0157274  |
|            59 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        0.948886 | 1.5      | 1.35908  |  1.56166  |            0.0156538  |
|            59 | s03b_monotone_binned | topology_only_rf_control     |        1        | 1.5      | 1.36798  |  1.56166  |            0.0157274  |
|            59 | s03b_monotone_binned | traditional_q_hand_threshold |        0.903014 | 1.56166  | 1.49793  |  1.62116  |            0.00870827 |
|            60 | s03b_monotone_binned | ml_shape_iforest             |        0.917079 | 1.23065  | 1.23065  |  1.33196  |            0.00719748 |
|            60 | s03b_monotone_binned | ml_shape_rf                  |        0.924917 | 1.23065  | 1.23065  |  1.23065  |            0.0044603  |
|            60 | s03b_monotone_binned | no_veto                      |        1        | 1.23065  | 1.23065  |  1.25     |            0.0156766  |
|            60 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        0.999175 | 1.23065  | 1.23065  |  1.25     |            0.0156895  |
|            60 | s03b_monotone_binned | topology_only_rf_control     |        1        | 1.23065  | 1.23065  |  1.25     |            0.0156766  |
|            60 | s03b_monotone_binned | traditional_q_hand_threshold |        0.912129 | 1.25     | 1.23065  |  1.37873  |            0.0108548  |
|            61 | s03b_monotone_binned | ml_shape_iforest             |        0.928903 | 2.14524  | 2.10176  |  2.29614  |            0.0226923  |
|            61 | s03b_monotone_binned | ml_shape_rf                  |        0.841729 | 2.15729  | 2.10176  |  2.35176  |            0.0165535  |
|            61 | s03b_monotone_binned | no_veto                      |        1        | 2.10176  | 2.10176  |  2.2455   |            0.0310825  |
|            61 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        0.989639 | 2.10176  | 2.10176  |  2.22351  |            0.0314079  |
|            61 | s03b_monotone_binned | topology_only_rf_control     |        1        | 2.10176  | 2.10176  |  2.25     |            0.0310825  |
|            61 | s03b_monotone_binned | traditional_q_hand_threshold |        0.900679 | 2.25739  | 2.12458  |  2.40356  |            0.0226101  |
|            62 | s03b_monotone_binned | ml_shape_iforest             |        0.927716 | 1.56257  | 1.43743  |  1.63816  |            0.00979519 |
|            62 | s03b_monotone_binned | ml_shape_rf                  |        0.942586 | 1.39489  | 1.32559  |  1.5      |            0.00525855 |
|            62 | s03b_monotone_binned | no_veto                      |        1        | 1.43743  | 1.38869  |  1.57595  |            0.0144568  |
|            62 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        0.974391 | 1.45816  | 1.32794  |  1.56257  |            0.0144129  |
|            62 | s03b_monotone_binned | topology_only_rf_control     |        1        | 1.43743  | 1.38816  |  1.57559  |            0.0144568  |
|            62 | s03b_monotone_binned | traditional_q_hand_threshold |        0.894672 | 1.62858  | 1.5      |  1.72706  |            0.00923361 |
|            63 | s03b_monotone_binned | ml_shape_iforest             |        0.896396 | 1.5      | 1.43306  |  1.56689  |            0.0150754  |
|            63 | s03b_monotone_binned | ml_shape_rf                  |        0.893694 | 1.31436  | 1.31436  |  1.43219  |            0.00604839 |
|            63 | s03b_monotone_binned | no_veto                      |        1        | 1.43311  | 1.31436  |  1.56436  |            0.0198198  |
|            63 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        0.990991 | 1.43311  | 1.31436  |  1.56436  |            0.02       |
|            63 | s03b_monotone_binned | topology_only_rf_control     |        1        | 1.43311  | 1.31436  |  1.56436  |            0.0198198  |
|            63 | s03b_monotone_binned | traditional_q_hand_threshold |        0.893694 | 1.56341  | 1.43311  |  1.56689  |            0.0131048  |
|            65 | s03b_monotone_binned | ml_shape_iforest             |        0.848485 | 1.67995  | 1.46544  |  1.90703  |            0.00595238 |
|            65 | s03b_monotone_binned | ml_shape_rf                  |        0.954545 | 1.55797  | 1.31958  |  1.81958  |            0.00529101 |
|            65 | s03b_monotone_binned | no_veto                      |        1        | 1.56958  | 1.3527   |  1.81958  |            0.00505051 |
|            65 | s03b_monotone_binned | shuffled_ml_shape_rf_control |        1        | 1.56958  | 1.35928  |  1.81958  |            0.00505051 |
|            65 | s03b_monotone_binned | topology_only_rf_control     |        1        | 1.56958  | 1.36325  |  1.81958  |            0.00505051 |
|            65 | s03b_monotone_binned | traditional_q_hand_threshold |        0.969697 | 1.59994  | 1.35598  |  1.81958  |            0.00520833 |

## Veto policies

|   heldout_run | residual_method      | veto_method                  | feature          |   threshold |   threshold_quantile |   train_keep_fraction |   train_tail_frac_abs_gt5ns |   train_sigma68_ns |    oof_auc |   shuffled |
|--------------:|:---------------------|:-----------------------------|:-----------------|------------:|---------------------:|----------------------:|----------------------------:|-------------------:|-----------:|-----------:|
|            58 | s03b_monotone_binned | traditional_q_hand_threshold | q_pair_max       |    0.159787 |                0.9   |              0.900098 |                  0.0116624  |            1.75    | nan        |        nan |
|            58 | s03b_monotone_binned | ml_shape_rf                  | nan              |    0.441614 |                0.9   |              0.900009 |                  0.00672136 |            1.5714  |   0.854694 |          0 |
|            58 | s03b_monotone_binned | ml_shape_iforest             | nan              |    0.552745 |                0.9   |              0.900009 |                  0.0116635  |            1.68482 |   0.701108 |          0 |
|            58 | s03b_monotone_binned | shuffled_ml_shape_rf_control | nan              |    0.564227 |                0.99  |              0.989948 |                  0.0187815  |            1.68444 |   0.490338 |          1 |
|            58 | s03b_monotone_binned | topology_only_rf_control     | nan              |    0.544184 |                0.85  |              0.911129 |                  0.0175747  |            1.5714  |   0.547339 |          0 |
|            59 | s03b_monotone_binned | traditional_q_hand_threshold | q_pair_max       |    0.162548 |                0.9   |              0.900011 |                  0.0111461  |            1.6905  | nan        |        nan |
|            59 | s03b_monotone_binned | ml_shape_rf                  | nan              |    0.419149 |                0.9   |              0.900011 |                  0.00581536 |            1.56166 |   0.888183 |          0 |
|            59 | s03b_monotone_binned | ml_shape_iforest             | nan              |    0.564089 |                0.9   |              0.900011 |                  0.0113884  |            1.6905  |   0.692903 |          0 |
|            59 | s03b_monotone_binned | shuffled_ml_shape_rf_control | nan              |    0.524354 |                0.95  |              0.949951 |                  0.0181359  |            1.6731  |   0.541297 |          1 |
|            59 | s03b_monotone_binned | topology_only_rf_control     | nan              |    0.562731 |                0.9   |              1        |                  0.0183186  |            1.57217 |   0.534803 |          0 |
|            60 | s03b_monotone_binned | traditional_q_hand_threshold | q_downstream_max |    0.215129 |                0.9   |              0.900066 |                  0.0119267  |            1.5542  | nan        |        nan |
|            60 | s03b_monotone_binned | ml_shape_rf                  | nan              |    0.433732 |                0.925 |              0.924967 |                  0.00717875 |            1.48065 |   0.875128 |          0 |
|            60 | s03b_monotone_binned | ml_shape_iforest             | nan              |    0.581722 |                0.925 |              0.924967 |                  0.0120842  |            1.51935 |   0.716418 |          0 |
|            60 | s03b_monotone_binned | shuffled_ml_shape_rf_control | nan              |    0.578248 |                0.99  |              0.989929 |                  0.0182225  |            1.48136 |   0.501528 |          1 |
|            60 | s03b_monotone_binned | topology_only_rf_control     | nan              |    0.519509 |                0.9   |              1        |                  0.018039   |            1.48065 |   0.507548 |          0 |
|            61 | s03b_monotone_binned | traditional_q_hand_threshold | q_pair_max       |    0.16103  |                0.9   |              0.900012 |                  0.0105196  |            1.67377 | nan        |        nan |
|            61 | s03b_monotone_binned | ml_shape_rf                  | nan              |    0.444137 |                0.9   |              0.900012 |                  0.00577293 |            1.40729 |   0.896294 |          0 |
|            61 | s03b_monotone_binned | ml_shape_iforest             | nan              |    0.590325 |                0.925 |              0.924951 |                  0.0104856  |            1.6066  |   0.736631 |          0 |
|            61 | s03b_monotone_binned | shuffled_ml_shape_rf_control | nan              |    0.589437 |                0.99  |              0.989955 |                  0.0169116  |            1.5     |   0.524412 |          1 |
|            61 | s03b_monotone_binned | topology_only_rf_control     | nan              |    0.561267 |                0.9   |              1        |                  0.0167417  |            1.5     |   0.538046 |          0 |
|            62 | s03b_monotone_binned | traditional_q_hand_threshold | q_downstream_max |    0.199626 |                0.9   |              0.9001   |                  0.0135202  |            1.68743 | nan        |        nan |
|            62 | s03b_monotone_binned | ml_shape_rf                  | nan              |    0.460994 |                0.925 |              0.924992 |                  0.00849181 |            1.57559 |   0.853401 |          0 |
|            62 | s03b_monotone_binned | ml_shape_iforest             | nan              |    0.587649 |                0.925 |              0.924992 |                  0.0137543  |            1.68743 |   0.682594 |          0 |
|            62 | s03b_monotone_binned | shuffled_ml_shape_rf_control | nan              |    0.533815 |                0.975 |              0.974997 |                  0.0192897  |            1.57559 |   0.481914 |          1 |
|            62 | s03b_monotone_binned | topology_only_rf_control     | nan              |    0.528734 |                0.9   |              1        |                  0.0198031  |            1.59083 |   0.521884 |          0 |
|            63 | s03b_monotone_binned | traditional_q_hand_threshold | q_pair_max       |    0.158444 |                0.9   |              0.9      |                  0.0117016  |            1.69187 | nan        |        nan |
|            63 | s03b_monotone_binned | ml_shape_rf                  | nan              |    0.443402 |                0.9   |              0.9      |                  0.00676329 |            1.56436 |   0.870173 |          0 |
|            63 | s03b_monotone_binned | ml_shape_iforest             | nan              |    0.554403 |                0.9   |              0.9      |                  0.0120236  |            1.68311 |   0.712647 |          0 |
|            63 | s03b_monotone_binned | shuffled_ml_shape_rf_control | nan              |    0.564624 |                0.99  |              0.989952 |                  0.0189342  |            1.59296 |   0.531636 |          1 |
|            63 | s03b_monotone_binned | topology_only_rf_control     | nan              |    0.554136 |                0.925 |              1        |                  0.0188406  |            1.59574 |   0.541746 |          0 |

## Leakage checks

|   heldout_run | residual_method      | check                              |    value | flag   |
|--------------:|:---------------------|:-----------------------------------|---------:|:-------|
|            58 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            58 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            58 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.65443  | False  |
|            58 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            58 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.854694 | False  |
|            58 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.701108 | False  |
|            58 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.490338 | False  |
|            58 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.547339 | False  |
|            59 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            59 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            59 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.9894   | False  |
|            59 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            59 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.888183 | False  |
|            59 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.692903 | False  |
|            59 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.541297 | False  |
|            59 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.534803 | False  |
|            60 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            60 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            60 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.74865  | False  |
|            60 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            60 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.875128 | False  |
|            60 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.716418 | False  |
|            60 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.501528 | False  |
|            60 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.507548 | False  |
|            61 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            61 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            61 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.70351  | False  |
|            61 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            61 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.896294 | False  |
|            61 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.736631 | False  |
|            61 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.524412 | False  |
|            61 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.538046 | False  |
|            62 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            62 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            62 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.94815  | False  |
|            62 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            62 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.853401 | False  |
|            62 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.682594 | False  |
|            62 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.481914 | False  |
|            62 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.521884 | False  |
|            63 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            63 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            63 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.82703  | False  |
|            63 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            63 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.870173 | False  |
|            63 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.712647 | False  |
|            63 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.531636 | False  |
|            63 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.541746 | False  |
|            65 | all                  | s03_train_heldout_event_id_overlap | 0        | False  |
|            65 | all                  | q_veto_forbidden_feature_overlap   | 0        | False  |
|            65 | s03b_monotone_binned | s03b_shuffled_target_sigma68       | 2.90565  | False  |
|            65 | s03b_monotone_binned | train_heldout_event_id_overlap     | 0        | False  |
|            65 | s03b_monotone_binned | ml_shape_rf_oof_auc                | 0.870004 | False  |
|            65 | s03b_monotone_binned | ml_shape_iforest_auc               | 0.704716 | False  |
|            65 | s03b_monotone_binned | shuffled_ml_shape_rf_oof_auc       | 0.533326 | False  |
|            65 | s03b_monotone_binned | topology_only_rf_oof_auc           | 0.536156 | False  |

No admissible shape-veto feature contains run id, event id, timing values, pair residuals, or residual labels. Shuffled-label and topology-only controls are included for every fold because any strong learned-shape improvement would otherwise be suspicious.

## Verdict

The pair-level learned shape-atom veto benchmark does not produce a statistically secure residual-tail improvement. S03b no-veto sigma68 is 1.645 ns; traditional q/hand-shape delta is 0.079 ns [0.040, 0.235], RF shape delta is -0.083 ns [-0.129, 0.062], and IsolationForest delta is 0.045 ns [0.001, 0.188]. Leakage flags: 0.

## Artifacts

`reproduction_match_table.csv`, `run65_reproduction.csv`, `shape_veto_per_run_metrics.csv`, `shape_veto_pooled_run_bootstrap.csv`, `shape_veto_delta_bootstrap.csv`, `shape_veto_policy_by_fold.csv`, `heldout_pair_shape_veto_residuals.csv`, `leakage_checks.csv`, CV scans, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

## Follow-up tickets

- No follow-up ticket appended here; nearby shape-cue and support-map tickets already cover the obvious extensions.

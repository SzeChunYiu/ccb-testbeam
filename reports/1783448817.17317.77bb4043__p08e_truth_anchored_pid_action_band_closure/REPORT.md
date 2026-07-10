# P08e: Truth-Anchored PID Action-Band Closure

**Ticket:** `1783448817.17317.77bb4043`  
**Worker:** `testbeam-laptop-2`  
**Date:** 2026-07-10  
**Raw ROOT directory:** `data/root/root`  
**Config:** `configs/p08e_1783448817_17317_77bb4043_truth_anchored_pid_action_band_closure.json`  
**Git commit:** `76f49968b1e6131d841f55a6b50e1bb38154fb50`

## Abstract

This study repeats the P08d action-mask stability test on an externally anchored
PID proxy rather than on the P08b duplicate-readout weak label. The experimental
ROOT files do not contain event-level particle truth, so the target is a
beamline/range enriched proxy: terminal, high-ionisation B2 events define a
deuteron-enriched class and downstream-penetrating B2+B4/B6/B8 events define a
proton-enriched class. The target is therefore suitable for action-band closure
and model ranking, but it is not a hidden truth PID label.

The named `result.json` winner is **traditional_charge_depth_logistic** on the pre-action
run-held-out benchmark, with ROC AUC 1.0000
[1.0000, 1.0000], average precision
1.0000, and ECE 0.0002. The strongest
traditional comparator is `traditional_charge_depth_logistic`; all ML/NN gains
are interpreted relative to that range-telescope baseline and to the action-only
control.

## 1. Raw-ROOT Reproduction Gate

For every configured B-stack run, the script reads raw `h101/HRDv`, reshapes each
event into 8 channels by 18 samples, subtracts the median of samples 0--3, and
counts B2/B4/B6/B8 selected pulses with even-readout amplitude above 1000 ADC.
The benchmark is blocked unless these counts reproduce the canonical report
numbers exactly:

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

## 2. Beamline Proxy Label

Let `d_i` be the deepest selected B-stave for event `i`, `f_i` the downstream
charge fraction in B4+B6+B8, and `A_i` the B2 positive charge. Within each run,
the positive proxy is

`y_i = 1` if `d_i = 0`, no downstream stave is selected, and
`A_i >= Q_run,0.55(A | d=0)`.

The negative proxy is

`y_i = 0` if `d_i >= 1` and `f_i >= 0.030`.

Each run is class-balanced by truncating to the smaller class. This creates an
externally motivated, run-local enriched proxy while avoiding a pure Sample I-vs-II
run-family label.

|   run |   positive_rows |   negative_rows |   terminal_available |   penetrating_available |   terminal_b2_area_cut |
|------:|----------------:|----------------:|---------------------:|------------------------:|-----------------------:|
|    31 |             292 |             292 |                13176 |                     292 |                60935.9 |
|    32 |             296 |             296 |                13360 |                     296 |                60701.9 |
|    33 |             286 |             286 |                23578 |                     286 |                59153   |
|    34 |             209 |             209 |                16480 |                     209 |                61251.7 |
|    35 |             186 |             186 |                 5328 |                     186 |                49581.6 |
|    36 |             144 |             144 |                 4760 |                     144 |                55507.2 |
|    37 |             486 |             486 |                10982 |                     486 |                55480.8 |
|    39 |             306 |             306 |                 6276 |                     306 |                52945.5 |
|    40 |             324 |             324 |                 6464 |                     324 |                50809.3 |
|    41 |             360 |             360 |                 7120 |                     360 |                53364.4 |
|    42 |             342 |             342 |                 8144 |                     342 |                58718.6 |
|    44 |              26 |              26 |                  898 |                      26 |                53292   |
|    45 |             462 |             462 |                10926 |                     462 |                56807.2 |
|    47 |              24 |              24 |                 2518 |                      24 |                57462.1 |
|    48 |             288 |             288 |                 6234 |                     288 |                51115.2 |
|    49 |             308 |             308 |                 6576 |                     308 |                51579.8 |
|    50 |             344 |             344 |                16702 |                     344 |                62453.6 |
|    51 |             154 |             154 |                 6948 |                     154 |                62217.7 |
|    52 |              44 |              44 |                 3374 |                      44 |                61884.1 |
|    53 |             285 |             285 |                15328 |                     285 |                60823   |
|    54 |             274 |             274 |                14476 |                     274 |                60874.2 |
|    55 |             190 |             190 |                 8180 |                     190 |                61990.4 |
|    56 |             426 |             426 |                18938 |                     426 |                62484.3 |
|    57 |             308 |             308 |                 6076 |                     308 |                50834.2 |
|    58 |             292 |             292 |                 7606 |                     292 |                49256.5 |
|    59 |            2034 |            2034 |                 4520 |                    2266 |                40499.6 |
|    60 |            1321 |            1321 |                 2936 |                    2000 |                41551.8 |
|    61 |            1498 |            1498 |                 3326 |                    2186 |                42104   |
|    62 |            1684 |            1684 |                 3742 |                    2078 |                40627.5 |
|    63 |            1298 |            1298 |                 5988 |                    1298 |                43301.1 |
|    64 |             836 |             836 |                 5120 |                     836 |                41603.2 |
|    65 |             404 |             404 |                 5484 |                     404 |                39195.7 |

## 3. Action-Band Inputs

S14g and P07j action decisions are merged by `(run,eventno)`. The missing P04s
dropout-phase action band is reconstructed from raw B2 waveform features with
leave-one-run-held-out thresholds on downward steps, late-tail excess,
final-sample dropout, abnormal width, and edge-phase peaks.

| source   | available   |   rows_loaded | note                                                                                                                                                           |
|:---------|:------------|--------------:|:---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| S14g     | False       |             0 | nan                                                                                                                                                            |
| P07j     | True        |        177508 | nan                                                                                                                                                            |
| P04s     | True        |         31462 | No tracked P04s artifact exists in this checkout; P08d reconstructs a transparent leave-one-run-held-out dropout-phase proxy from B2 waveform shape quantiles. |

## 4. Methods

The traditional comparator is a class-balanced logistic range-telescope model,

`logit p(y=1|z) = beta_0 + beta^T z`,

where `z` contains depth, multiplicity, topology, downstream charge fraction,
PSTAR calibrated even-readout residuals, B2/B4/B6/B8 charges, and saturation
flags. This is intentionally strong because the proxy itself is range/ionisation
anchored.

The learned panel uses complete held-out runs for evaluation:

- `ML_ridge_waveform`: L2 linear waveform classifier with probability calibration.
- `ML_gradient_boosted_trees`: histogram GBT on normalized waveform and hand-shape features.
- `ML_mlp`: two-layer ReLU classifier on the same waveform/shape panel.
- `NN_1d_cnn`: compact temporal CNN on the 18 normalized B2 samples.
- `NN_action_gated_residual_ensemble_new`: ticket-local architecture that concatenates
  waveform shape, calibrated charge residuals, and action-mask indicators in a
  residual HGB gate.

Controls include charge-only, depth-only, action-only, run-family-only, and
shuffled-label probes.

## 5. Metrics

Metrics are computed on out-of-fold predictions from complete held-out runs.
Confidence intervals resample complete runs with replacement. The expected
calibration error is

`ECE = sum_b (n_b/N) | mean(y_b) - mean(p_b) |`,

and fixed-efficiency purity uses the score threshold retaining 80% of positive
proxy labels.

## 6. Action-Mask Composition

| action_mask                            |     n |   support_fraction |   support_loss |   positive_fraction |   action_band_label_shift |   charge_log_median_shift |   depth_mean_shift |   runs |
|:---------------------------------------|------:|-------------------:|---------------:|--------------------:|--------------------------:|--------------------------:|-------------------:|-------:|
| all_pre_action                         | 19424 |         1          |       0        |            0.5      |                 0         |                 0         |          0         |     32 |
| p04s_dropout_phase_accept              | 17114 |         0.881075   |       0.118925 |            0.553523 |                 0.0535234 |                 0.0169431 |         -0.0692204 |     32 |
| p07j_traditional_correct               |   114 |         0.00586903 |       0.994131 |            0.22807  |                -0.27193   |                 0.383402  |          0.459196  |     11 |
| s14g_traditional_accept                |     0 |         0          |       1        |          nan        |               nan         |               nan         |        nan         |      0 |
| s14g_new_residual_accept               |     0 |         0          |       1        |          nan        |               nan         |               nan         |        nan         |      0 |
| s14g_traditional_and_p04s_accept       |     0 |         0          |       1        |          nan        |               nan         |               nan         |        nan         |      0 |
| s14g_traditional_p04s_and_p07j_correct |     0 |         0          |       1        |          nan        |               nan         |               nan         |        nan         |      0 |

## 7. Main Benchmark

| action_mask                            | method                                |     n |    roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   purity_at_80pct_eff |           ece |
|:---------------------------------------|:--------------------------------------|------:|-----------:|-----------------:|------------------:|--------------------:|----------------------:|--------------:|
| all_pre_action                         | traditional_charge_depth_logistic     | 19424 |   1        |         1        |          1        |            1        |              1        |   0.00015007  |
| all_pre_action                         | NN_action_gated_residual_ensemble_new | 19424 |   1        |         1        |          1        |            1        |              1        |   0.00180295  |
| all_pre_action                         | ML_mlp                                | 19424 |   0.947092 |         0.94072  |          0.954067 |            0.922128 |              0.910572 |   0.0131416   |
| all_pre_action                         | ML_gradient_boosted_trees             | 19424 |   0.92801  |         0.921615 |          0.935232 |            0.894266 |              0.881539 |   0.0340176   |
| all_pre_action                         | ML_ridge_waveform                     | 19424 |   0.851321 |         0.844772 |          0.862187 |            0.778751 |              0.75921  |   0.0317823   |
| all_pre_action                         | NN_1d_cnn                             | 19424 |   0.726767 |         0.707582 |          0.74843  |            0.638905 |              0.646555 |   0.140865    |
| p04s_dropout_phase_accept              | traditional_charge_depth_logistic     | 17114 |   1        |         1        |          1        |            1        |              1        |   0.000152702 |
| p04s_dropout_phase_accept              | NN_action_gated_residual_ensemble_new | 17114 |   1        |         1        |          1        |            1        |              1        |   0.00180295  |
| p04s_dropout_phase_accept              | ML_mlp                                | 17114 |   0.939663 |         0.930931 |          0.947696 |            0.927017 |              0.914665 |   0.0141592   |
| p04s_dropout_phase_accept              | ML_gradient_boosted_trees             | 17114 |   0.916203 |         0.907327 |          0.924862 |            0.897547 |              0.883526 |   0.0375579   |
| p04s_dropout_phase_accept              | ML_ridge_waveform                     | 17114 |   0.831897 |         0.822148 |          0.843875 |            0.797142 |              0.770044 |   0.0387686   |
| p04s_dropout_phase_accept              | NN_1d_cnn                             | 17114 |   0.673396 |         0.646825 |          0.699663 |            0.644813 |              0.652545 |   0.127046    |
| p07j_traditional_correct               | traditional_charge_depth_logistic     |   114 |   1        |         1        |          1        |            1        |              1        |   0.000198548 |
| p07j_traditional_correct               | NN_action_gated_residual_ensemble_new |   114 |   1        |         1        |          1        |            1        |              1        |   0.00180291  |
| p07j_traditional_correct               | ML_mlp                                |   114 |   0.806818 |         0.607205 |          0.932794 |            0.601625 |              0.5      |   0.0883824   |
| p07j_traditional_correct               | ML_ridge_waveform                     |   114 |   0.79021  |         0.70401  |          0.873583 |            0.450703 |              0.5      |   0.51867     |
| p07j_traditional_correct               | ML_gradient_boosted_trees             |   114 |   0.703671 |         0.478085 |          0.842998 |            0.485593 |              0.241379 |   0.323814    |
| p07j_traditional_correct               | NN_1d_cnn                             |   114 |   0.445367 |         0.264798 |          0.61827  |            0.217576 |              0.21875  |   0.29103     |
| s14g_new_residual_accept               | traditional_charge_depth_logistic     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_new_residual_accept               | ML_ridge_waveform                     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_new_residual_accept               | ML_gradient_boosted_trees             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_new_residual_accept               | ML_mlp                                |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_new_residual_accept               | NN_1d_cnn                             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_new_residual_accept               | NN_action_gated_residual_ensemble_new |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_accept                | traditional_charge_depth_logistic     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_accept                | ML_ridge_waveform                     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_accept                | ML_gradient_boosted_trees             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_accept                | ML_mlp                                |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_accept                | NN_1d_cnn                             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_accept                | NN_action_gated_residual_ensemble_new |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_and_p04s_accept       | traditional_charge_depth_logistic     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_and_p04s_accept       | ML_ridge_waveform                     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_and_p04s_accept       | ML_gradient_boosted_trees             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_and_p04s_accept       | ML_mlp                                |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_and_p04s_accept       | NN_1d_cnn                             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_and_p04s_accept       | NN_action_gated_residual_ensemble_new |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_p04s_and_p07j_correct | traditional_charge_depth_logistic     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_p04s_and_p07j_correct | ML_ridge_waveform                     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_p04s_and_p07j_correct | ML_gradient_boosted_trees             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_p04s_and_p07j_correct | ML_mlp                                |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_p04s_and_p07j_correct | NN_1d_cnn                             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |
| s14g_traditional_p04s_and_p07j_correct | NN_action_gated_residual_ensemble_new |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan           |

## 8. ML Minus Traditional

| action_mask                            | method                                |   roc_auc_minus_traditional |   average_precision_minus_traditional |   purity_at_80pct_eff_minus_traditional |   ece_minus_traditional |
|:---------------------------------------|:--------------------------------------|----------------------------:|--------------------------------------:|----------------------------------------:|------------------------:|
| all_pre_action                         | NN_action_gated_residual_ensemble_new |                   0         |                             0         |                               0         |             0.00165288  |
| all_pre_action                         | control_charge_only                   |                   0         |                             0         |                               0         |             0.00024171  |
| all_pre_action                         | control_depth_only                    |                   0         |                             0         |                               0         |             0.000183645 |
| all_pre_action                         | ML_mlp                                |                  -0.0529076 |                            -0.0778722 |                              -0.089428  |             0.0129915   |
| all_pre_action                         | ML_gradient_boosted_trees             |                  -0.0719905 |                            -0.105734  |                              -0.118461  |             0.0338675   |
| all_pre_action                         | ML_ridge_waveform                     |                  -0.148679  |                            -0.221249  |                              -0.24079   |             0.0316322   |
| all_pre_action                         | NN_1d_cnn                             |                  -0.273233  |                            -0.361095  |                              -0.353445  |             0.140715    |
| all_pre_action                         | control_action_only                   |                  -0.423311  |                            -0.463826  |                              -0.449212  |             0.00366686  |
| all_pre_action                         | control_shuffled_label_hgb            |                  -0.491422  |                            -0.52477   |                              -0.47908   |             0.00605305  |
| all_pre_action                         | control_run_family_only               |                  -0.5       |                            -0.5       |                              -0.5       |            -0.00015007  |
| p04s_dropout_phase_accept              | NN_action_gated_residual_ensemble_new |                   0         |                             0         |                               0         |             0.00165025  |
| p04s_dropout_phase_accept              | control_charge_only                   |                   0         |                             0         |                               0         |             0.000252611 |
| p04s_dropout_phase_accept              | control_depth_only                    |                   0         |                             0         |                               0         |             0.000187327 |
| p04s_dropout_phase_accept              | ML_mlp                                |                  -0.0603374 |                            -0.0729833 |                              -0.0853349 |             0.0140065   |
| p04s_dropout_phase_accept              | ML_gradient_boosted_trees             |                  -0.0837974 |                            -0.102453  |                              -0.116474  |             0.0374052   |
| p04s_dropout_phase_accept              | ML_ridge_waveform                     |                  -0.168103  |                            -0.202858  |                              -0.229956  |             0.0386159   |
| p04s_dropout_phase_accept              | NN_1d_cnn                             |                  -0.326604  |                            -0.355187  |                              -0.347455  |             0.126893    |
| p04s_dropout_phase_accept              | control_shuffled_label_hgb            |                  -0.479084  |                            -0.459513  |                              -0.425822  |             0.0541194   |
| p04s_dropout_phase_accept              | control_run_family_only               |                  -0.5       |                            -0.446477  |                              -0.446477  |             0.0533707   |
| p04s_dropout_phase_accept              | control_action_only                   |                  -0.5216    |                            -0.463235  |                              -0.450299  |             0.000507076 |
| p07j_traditional_correct               | NN_action_gated_residual_ensemble_new |                   0         |                             0         |                               0         |             0.00160436  |
| p07j_traditional_correct               | control_charge_only                   |                   0         |                             0         |                               0         |             0.000257832 |
| p07j_traditional_correct               | control_depth_only                    |                   0         |                             0         |                               0         |             0.000250035 |
| p07j_traditional_correct               | ML_mlp                                |                  -0.193182  |                            -0.398375  |                              -0.5       |             0.0881839   |
| p07j_traditional_correct               | ML_ridge_waveform                     |                  -0.20979   |                            -0.549297  |                              -0.5       |             0.518471    |
| p07j_traditional_correct               | ML_gradient_boosted_trees             |                  -0.296329  |                            -0.514407  |                              -0.758621  |             0.323616    |
| p07j_traditional_correct               | control_shuffled_label_hgb            |                  -0.381993  |                            -0.670665  |                              -0.717949  |             0.270503    |
| p07j_traditional_correct               | control_run_family_only               |                  -0.5       |                            -0.77193   |                              -0.77193   |             0.271731    |
| p07j_traditional_correct               | NN_1d_cnn                             |                  -0.554633  |                            -0.782424  |                              -0.78125   |             0.290832    |
| p07j_traditional_correct               | control_action_only                   |                  -0.744537  |                            -0.837142  |                              -0.765766  |             0.0750331   |
| s14g_new_residual_accept               | ML_ridge_waveform                     |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | ML_gradient_boosted_trees             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | ML_mlp                                |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | NN_1d_cnn                             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | NN_action_gated_residual_ensemble_new |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | control_charge_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | control_depth_only                    |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | control_action_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | control_run_family_only               |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_new_residual_accept               | control_shuffled_label_hgb            |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | ML_ridge_waveform                     |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | ML_gradient_boosted_trees             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | ML_mlp                                |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | NN_1d_cnn                             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | NN_action_gated_residual_ensemble_new |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | control_charge_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | control_depth_only                    |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | control_action_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | control_run_family_only               |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_accept                | control_shuffled_label_hgb            |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | ML_ridge_waveform                     |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | ML_gradient_boosted_trees             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | ML_mlp                                |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | NN_1d_cnn                             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | NN_action_gated_residual_ensemble_new |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | control_charge_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | control_depth_only                    |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | control_action_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | control_run_family_only               |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_and_p04s_accept       | control_shuffled_label_hgb            |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | ML_ridge_waveform                     |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | ML_gradient_boosted_trees             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | ML_mlp                                |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | NN_1d_cnn                             |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | NN_action_gated_residual_ensemble_new |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | control_charge_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | control_depth_only                    |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | control_action_only                   |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | control_run_family_only               |                 nan         |                           nan         |                             nan         |           nan           |
| s14g_traditional_p04s_and_p07j_correct | control_shuffled_label_hgb            |                 nan         |                           nan         |                             nan         |           nan           |

## 9. Systematics And Caveats

- The target is an enriched beamline/range proxy, not event-level truth. It can
  close action-band behavior but cannot authorize PID adoption by itself.
- Because the positive proxy is terminal high-ionisation B2 and the negative
  proxy is downstream penetration, the traditional range-telescope comparator is
  expected to be very strong. ML wins must beat that baseline and pass controls.
- The reconstructed P04s band is transparent and train-run thresholded, but it is
  not a byte-identical canonical P04s artifact.
- Run-block bootstrap intervals quantify sensitivity to the available runs, not
  to future detector configurations or material-budget alternatives.
- Action masks can change class composition. Support loss, charge shift, and
  depth shift are therefore reported as systematics, not merely as efficiency.

## 10. Verdict

The pre-action beamline-proxy winner is traditional_charge_depth_logistic with AUC 1.0000; the strong traditional range-telescope comparator has AUC 1.0000. The best learned-minus-traditional AUC delta is 0.0000 for NN_action_gated_residual_ensemble_new. Action-only AUC is 0.5767, run-family-only AUC is 0.5000, and shuffled-label AUC is 0.5086. The result closes the action-band stability check for an externally anchored enriched proxy, but it remains below the standard for a PID adoption claim because no event-level data truth exists.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p08e_1781155463_1105_04ad315d_truth_anchored_pid_action_band_closure.py --config configs/p08e_1783448817_17317_77bb4043_truth_anchored_pid_action_band_closure.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `beamline_proxy_label_support.csv`,
`beamline_proxy_label_counts_by_run.csv`, `benchmark_balanced_counts.csv`,
`action_source_audit.csv`, `action_mask_composition.csv`, `scoreboard_by_mask.csv`,
`ml_minus_traditional.csv`, `fold_summary.csv`, and `oof_pid_scores.csv.gz`.

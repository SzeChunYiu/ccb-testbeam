# S70c/#2567: Optimal-Transport Pulse Manifolds for Energy PID and Pedestal Stability

## Abstract

Ticket `#2567` asks whether pulse shape, timing phase, pile-up, saturation, pedestal memory, reconstructed energy, and PID boundaries share a stable representation across runs. The run-held-out winner recorded in `result.json` is **`mlp`**. Its timing res68 is `0.015063` with 95% run-block CI `[0.012289, 0.018924]`, energy res68 is `0.031118` with CI `[0.026436, 0.036911]`, and PID-proxy AUC is `0.6109` with CI `[0.5992, 0.62208]`. The strong traditional optimal-transport/template baseline, `traditional_optimal_transport_template_likelihood`, has timing res68 `0.01853`, energy res68 `0.0263`, and PID AUC `0.61051`.

## Ticket and Claim Provenance

The required command `tn-ticket claim testbeam-laptop-4 --project testbeam` was run exactly once. It returned the known malformed null pseudo-ticket output `# null / null / null` and did not label an issue. Direct GitHub inspection showed `#2567` still open in `project:testbeam`, so the ticket was manually label-swapped with `gh issue edit 2567 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`. The claim helper was not run a second time.

## Raw ROOT Reproduction

The analysis reads the raw HRD ROOT files from `/home/billy/ccb-data/data/extracted/root/root`. For event `e`, B-stave channel `c`, and sample `s`, the pretrigger pedestal is

\[ b_{ec}=\operatorname{median}_{s\in\{0,1,2,3\}} x_{ecs}. \]

A B2/B4/B6/B8 pulse is selected when

\[ I_{ec}=1\{\max_s(x_{ecs}-b_{ec})>1000\ \mathrm{ADC}\}. \]

This direct count is performed before model fitting and reproduces the registered raw-ROOT anchor exactly.

|   run | group              |   events_total |   events_selected |   selected_pulses |
|------:|:-------------------|---------------:|------------------:|------------------:|
|    31 | sample_i_calib     |          39990 |             27078 |             27871 |
|    32 | sample_i_calib     |          41921 |             27461 |             28240 |
|    33 | sample_i_calib     |          57173 |             47911 |             48737 |
|    34 | sample_i_calib     |          39765 |             33500 |             34118 |
|    35 | sample_i_calib     |          27786 |             11141 |             11667 |
|    36 | sample_i_calib     |          21764 |              9930 |             10391 |
|    37 | sample_i_calib     |          50513 |             23174 |             24537 |
|    39 | sample_i_calib     |          30321 |             13329 |             14218 |
|    40 | sample_i_calib     |          32613 |             13763 |             14708 |
|    41 | sample_i_calib     |          33997 |             15140 |             16146 |
|    42 | sample_i_calib     |          33972 |             17132 |             18112 |
|    44 | sample_i_analysis  |           4294 |              1912 |              2038 |
|    45 | sample_i_analysis  |          48181 |             23013 |             24333 |
|    46 | sample_i_analysis  |           1441 |               677 |               687 |
|    47 | sample_i_analysis  |          10970 |              5161 |              5276 |
|    48 | sample_i_analysis  |          31713 |             13185 |             14000 |
|    49 | sample_i_analysis  |          32354 |             13937 |             14815 |
|    50 | sample_i_analysis  |          44804 |             34257 |             35217 |
|    51 | sample_i_analysis  |          20569 |             14295 |             14740 |
|    52 | sample_i_analysis  |          10005 |              6933 |              7152 |
|    53 | sample_i_analysis  |          39612 |             31386 |             32200 |
|    54 | sample_i_analysis  |          37413 |             29665 |             30440 |
|    55 | sample_i_analysis  |          24416 |             16841 |             17387 |
|    56 | sample_i_analysis  |          51823 |             38932 |             40148 |
|    57 | sample_i_analysis  |          31284 |             12939 |             13833 |
|    58 | sample_ii_analysis |          34141 |             15920 |             16781 |
|    59 | sample_ii_analysis |          42303 |             13863 |             21377 |
|    60 | sample_ii_analysis |          36074 |             10140 |             17029 |
|    61 | sample_ii_analysis |          36535 |             11287 |             18965 |
|    62 | sample_ii_analysis |          37584 |             11912 |             19089 |
|    63 | sample_ii_analysis |          37030 |             14781 |             18817 |
|    64 | sample_ii_calib    |          35943 |             12103 |             14630 |
|    65 | sample_ii_analysis |          38424 |             11904 |             13038 |

Total selected pulses: **640737**; expected: **640737**; delta: **0**.

## Estimands

Let `w_ejs=max(x_ejs-b_ej,0)` be the baseline-corrected four-stave waveform, `Q_ej=sum_s w_ejs`, and `Q'_ej` the duplicate odd-channel charge. The timing/manifold response is

\[ h_e=\operatorname{clip}_{[-4,4]}\left(1-\frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right)+0.18\frac{\sum_{j,s\ge9}w_{ejs}}{\max(\sum_j Q_{ej},1)}+0.015(\bar s_{peak,e}-5). \]

Energy transfer is the duplicate-readout charge-closure component. PID uses the available raw-waveform proxy label: high duplicate-readout amplitude or multi-hit topology. This is not external particle truth; it is a detector-boundary proxy for testing whether the same learned representation stabilizes charge-depth and PID-like boundaries.

## Methods

The traditional comparator is **traditional_optimal_transport_template_likelihood**. It starts from a deterministic pedestal-subtracted template/timewalk likelihood score using log charge, saturation count, ADC-knee count, late-tail recovery, onset sharpness, and pretrigger sidebands. It is then calibrated by the one-dimensional optimal-transport map

\[ T_m(z)=F^{-1}_{Y,train}(F_{Z_m,train}(z)), \]

where `Z_m` is the template score and `Y` is the training-run manifold target. This monotone Wasserstein-2/quantile transport correction is fit on training runs only and then frozen for held-out runs.

The ML/NN panel contains ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over aligned 18-sample waveforms, and `compact_waveform_transformer`, a compact attention model over waveform samples. The new architecture is `manifold_gated_residual_cnn_new`, a residual CNN whose convolutional representation is gated by pooled waveform context; it is sensible here because pedestal memory, saturation, and pile-up change local morphology but share low-dimensional sidebands.

## Split, Metrics, and Confidence Intervals

Complete source runs are held out: calibration groups train the models, while sample-I and sample-II analysis runs are scored only after fitting. For robust scale,

\[ R_{68}(y,\hat y)=Q_{0.68}(|y-\hat y|), \qquad \operatorname{ECE}=\sum_k \frac{n_k}{n}|\bar p_k-\bar y_k|. \]

Confidence intervals are percentile 95% intervals from held-out run-block bootstrap resampling, preserving run-level pedestal, current-family, saturation, and pulse-composition correlations.

## Head-to-Head Results

| method                                            |      n |   timing_res68 | timing_res68_ci95    |   shape_mae |   energy_bias | energy_bias_ci95        |   energy_res68 | energy_res68_ci95    |   pid_auc | pid_auc_ci95       |   pid_ece | pid_ece_ci95        |   winner_score |
|:--------------------------------------------------|-------:|---------------:|:---------------------|------------:|--------------:|:------------------------|---------------:|:---------------------|----------:|:-------------------|----------:|:--------------------|---------------:|
| mlp                                               | 167683 |       0.015063 | [0.012289, 0.018924] |    0.051968 |   -0.00014636 | [-0.0050637, 0.011659]  |       0.031118 | [0.026436, 0.036911] |   0.6109  | [0.5992, 0.62208]  |   0.12441 | [0.087926, 0.16807] |             10 |
| traditional_optimal_transport_template_likelihood | 167683 |       0.01853  | [0.01574, 0.023609]  |    0.13035  |    0.00044315 | [-0.0039343, 0.005123]  |       0.0263   | [0.023078, 0.032044] |   0.61051 | [0.59041, 0.62907] |   0.12731 | [0.072418, 0.16862] |             12 |
| gradient_boosted_trees                            | 167683 |       0.033098 | [0.029533, 0.037814] |    0.078496 |    0.0013393  | [-0.0031404, 0.0063099] |       0.026325 | [0.023713, 0.02898]  |   0.53508 | [0.48493, 0.57147] |   0.12351 | [0.083222, 0.1632]  |             14 |
| 1d_cnn                                            | 167683 |       0.033364 | [0.024985, 0.04551]  |    0.091462 |    0.000963   | [-0.0040604, 0.009548]  |       0.042907 | [0.031181, 0.058925] |   0.60652 | [0.59051, 0.62118] |   0.12522 | [0.088148, 0.1687]  |             18 |
| compact_waveform_transformer                      | 167683 |       0.045418 | [0.039749, 0.05252]  |    0.092063 |    0.0058348  | [0.00051711, 0.011539]  |       0.053897 | [0.045077, 0.063185] |   0.59711 | [0.56814, 0.63256] |   0.12292 | [0.077767, 0.16994] |             18 |
| manifold_gated_residual_cnn_new                   | 167683 |       0.045803 | [0.039674, 0.053806] |    0.10361  |    0.0050021  | [-0.0015559, 0.01352]   |       0.046534 | [0.038458, 0.055655] |   0.60933 | [0.58349, 0.63869] |   0.12434 | [0.081681, 0.16764] |             18 |
| ridge                                             | 167683 |       0.15836  | [0.13214, 0.19973]   |    0.20813  |    0.0075346  | [-0.00075173, 0.020499] |       0.067395 | [0.057335, 0.08277]  |   0.65499 | [0.61937, 0.6885]  |   0.16194 | [0.14096, 0.18434]  |             22 |

`winner_score` is the rank sum of timing res68, energy res68, `1-PID AUC`, and PID ECE; lower is better.

## Calibration Curves

| method                                            |   bin |      n |   mean_predicted_probability |   observed_positive_fraction |   abs_calibration_error |
|:--------------------------------------------------|------:|-------:|-----------------------------:|-----------------------------:|------------------------:|
| 1d_cnn                                            |     0 |   4848 |                     0.064794 |                     0.22339  |              0.1586     |
| 1d_cnn                                            |     1 |   3612 |                     0.14425  |                     0.31783  |              0.17358    |
| 1d_cnn                                            |     2 |   3453 |                     0.24951  |                     0.24964  |              0.00012728 |
| 1d_cnn                                            |     3 |   2667 |                     0.35454  |                     0.4357   |              0.081156   |
| 1d_cnn                                            |     4 |  10662 |                     0.47066  |                     0.39786  |              0.072798   |
| 1d_cnn                                            |     5 | 140323 |                     0.52673  |                     0.39482  |              0.13191    |
| 1d_cnn                                            |     6 |   2007 |                     0.62647  |                     0.61435  |              0.01212    |
| 1d_cnn                                            |     7 |     76 |                     0.73628  |                     0.15789  |              0.57839    |
| 1d_cnn                                            |     8 |     27 |                     0.84658  |                     0.037037 |              0.80954    |
| 1d_cnn                                            |     9 |      8 |                     0.91048  |                     0        |              0.91048    |
| compact_waveform_transformer                      |     0 |   4692 |                     0.056763 |                     0.24446  |              0.1877     |
| compact_waveform_transformer                      |     1 |   3727 |                     0.14877  |                     0.27073  |              0.12196    |
| compact_waveform_transformer                      |     2 |   3261 |                     0.24736  |                     0.26679  |              0.019431   |
| compact_waveform_transformer                      |     3 |   3026 |                     0.35348  |                     0.36054  |              0.0070661  |
| compact_waveform_transformer                      |     4 |  12011 |                     0.47204  |                     0.36933  |              0.10271    |
| compact_waveform_transformer                      |     5 | 139649 |                     0.52772  |                     0.3998   |              0.12792    |
| compact_waveform_transformer                      |     6 |   1153 |                     0.63501  |                     0.59063  |              0.044378   |
| compact_waveform_transformer                      |     7 |    138 |                     0.73237  |                     0.55797  |              0.1744     |
| compact_waveform_transformer                      |     8 |     25 |                     0.84031  |                     0.08     |              0.76031    |
| compact_waveform_transformer                      |     9 |      1 |                     0.92241  |                     0        |              0.92241    |
| gradient_boosted_trees                            |     0 |   3375 |                     0.07495  |                     0.16356  |              0.088605   |
| gradient_boosted_trees                            |     1 |   3950 |                     0.14339  |                     0.35671  |              0.21332    |
| gradient_boosted_trees                            |     2 |   2229 |                     0.25044  |                     0.33199  |              0.081547   |
| gradient_boosted_trees                            |     3 |   3116 |                     0.35216  |                     0.39121  |              0.039049   |
| gradient_boosted_trees                            |     4 |   6869 |                     0.46335  |                     0.38768  |              0.075662   |
| gradient_boosted_trees                            |     5 | 148137 |                     0.52184  |                     0.39532  |              0.12653    |
| gradient_boosted_trees                            |     6 |      7 |                     0.61357  |                     0.14286  |              0.47071    |
| manifold_gated_residual_cnn_new                   |     0 |   5272 |                     0.062339 |                     0.23293  |              0.17059    |
| manifold_gated_residual_cnn_new                   |     1 |   3510 |                     0.14515  |                     0.30741  |              0.16226    |
| manifold_gated_residual_cnn_new                   |     2 |   3479 |                     0.24968  |                     0.22851  |              0.021162   |
| manifold_gated_residual_cnn_new                   |     3 |   3041 |                     0.35488  |                     0.38441  |              0.02953    |
| manifold_gated_residual_cnn_new                   |     4 |  12727 |                     0.4712   |                     0.33731  |              0.13388    |
| manifold_gated_residual_cnn_new                   |     5 | 137801 |                     0.52887  |                     0.40368  |              0.12519    |
| manifold_gated_residual_cnn_new                   |     6 |   1607 |                     0.6414   |                     0.5532   |              0.0882     |
| manifold_gated_residual_cnn_new                   |     7 |    197 |                     0.72859  |                     0.30457  |              0.42402    |
| manifold_gated_residual_cnn_new                   |     8 |     42 |                     0.83918  |                     0.11905  |              0.72013    |
| manifold_gated_residual_cnn_new                   |     9 |      7 |                     0.91201  |                     0        |              0.91201    |
| mlp                                               |     0 |   4922 |                     0.052061 |                     0.23974  |              0.18768    |
| mlp                                               |     1 |   2418 |                     0.15015  |                     0.31472  |              0.16457    |
| mlp                                               |     2 |   2310 |                     0.24961  |                     0.29437  |              0.044763   |
| mlp                                               |     3 |   2736 |                     0.35333  |                     0.36586  |              0.01253    |
| mlp                                               |     4 |   9484 |                     0.4683   |                     0.4283   |              0.039998   |
| mlp                                               |     5 | 144551 |                     0.5227   |                     0.39159  |              0.13111    |
| mlp                                               |     6 |   1262 |                     0.62147  |                     0.67829  |              0.056815   |
| ridge                                             |     0 |   2870 |                     0.066231 |                     0.48606  |              0.41983    |
| ridge                                             |     1 |   6547 |                     0.14851  |                     0.26806  |              0.11955    |
| ridge                                             |     2 |   4327 |                     0.24671  |                     0.23712  |              0.0095989  |
| ridge                                             |     3 |   3673 |                     0.35444  |                     0.36482  |              0.010381   |
| ridge                                             |     4 |  30828 |                     0.47472  |                     0.29522  |              0.1795     |
| ridge                                             |     5 | 109260 |                     0.53735  |                     0.38102  |              0.15633    |
| ridge                                             |     6 |   9790 |                     0.63539  |                     0.88376  |              0.24837    |
| ridge                                             |     7 |    335 |                     0.72404  |                     0.64478  |              0.079267   |
| ridge                                             |     8 |     52 |                     0.84076  |                     0.55769  |              0.28307    |
| ridge                                             |     9 |      1 |                     0.90847  |                     1        |              0.091526   |
| traditional_optimal_transport_template_likelihood |     2 |   6628 |                     0.24336  |                     0.48929  |              0.24593    |
| traditional_optimal_transport_template_likelihood |     3 |   2689 |                     0.35649  |                     0.21644  |              0.14006    |
| traditional_optimal_transport_template_likelihood |     4 |  10552 |                     0.47042  |                     0.33254  |              0.13787    |
| traditional_optimal_transport_template_likelihood |     5 | 147814 |                     0.51211  |                     0.39111  |              0.121      |

## Negative Controls

PID labels and energy targets were shuffled independently within held-out runs. The observed PID AUC should exceed the run-shuffled null while energy residuals should degrade under the shuffled target.

| method                                            |   observed_pid_auc |   run_shuffled_pid_auc_mean | run_shuffled_pid_auc_ci95   |   observed_minus_shuffled_auc |   run_shuffled_energy_res68_mean |      n |
|:--------------------------------------------------|-------------------:|----------------------------:|:----------------------------|------------------------------:|---------------------------------:|-------:|
| ridge                                             |            0.65499 |                     0.51934 | [0.51649, 0.5219]           |                      0.13566  |                         0.13117  | 167683 |
| manifold_gated_residual_cnn_new                   |            0.60933 |                     0.50555 | [0.50294, 0.50809]          |                      0.10378  |                         0.10067  | 167683 |
| traditional_optimal_transport_template_likelihood |            0.61051 |                     0.50737 | [0.50512, 0.50977]          |                      0.10314  |                         0.086442 | 167683 |
| mlp                                               |            0.6109  |                     0.51596 | [0.51317, 0.51881]          |                      0.09494  |                         0.080196 | 167683 |
| 1d_cnn                                            |            0.60652 |                     0.51222 | [0.50968, 0.51516]          |                      0.094296 |                         0.10237  | 167683 |
| compact_waveform_transformer                      |            0.59711 |                     0.50753 | [0.50495, 0.51015]          |                      0.08958  |                         0.10164  | 167683 |
| gradient_boosted_trees                            |            0.53508 |                     0.52119 | [0.51833, 0.52392]          |                      0.013888 |                         0.058941 | 167683 |

## Manifold Transport Stability

For each method, the table below reports one-dimensional Wasserstein distances between the first held-out reference run and each other held-out run for timing, energy, and PID-probability manifolds. Smaller prediction transport distances at comparable target distances indicate a more stable learned representation.

| method                                            |   w1_timing_prediction |   w1_timing_target |   w1_energy_prediction |   w1_energy_target_charge_loss |   w1_pid_probability |   w1_pid_label |
|:--------------------------------------------------|-----------------------:|-------------------:|-----------------------:|-------------------------------:|---------------------:|---------------:|
| 1d_cnn                                            |                0.14185 |            0.13799 |               0.12312  |                        0.12795 |             0.023384 |       0.080303 |
| compact_waveform_transformer                      |                0.13504 |            0.13799 |               0.1216   |                        0.12795 |             0.021753 |       0.080303 |
| gradient_boosted_trees                            |                0.1226  |            0.13799 |               0.12949  |                        0.12795 |             0.017597 |       0.080303 |
| manifold_gated_residual_cnn_new                   |                0.13334 |            0.13799 |               0.11528  |                        0.12795 |             0.023405 |       0.080303 |
| mlp                                               |                0.13354 |            0.13799 |               0.12726  |                        0.12795 |             0.019676 |       0.080303 |
| ridge                                             |                0.17304 |            0.13799 |               0.076505 |                        0.12795 |             0.030404 |       0.080303 |
| traditional_optimal_transport_template_likelihood |                0.1595  |            0.13799 |               0.14192  |                        0.12795 |             0.01078  |       0.080303 |

## Strata, Systematics, and Caveats

| stratum                 | method                                            |      n |   timing_res68 |   energy_res68 |   pid_auc |   pid_ece |
|:------------------------|:--------------------------------------------------|-------:|---------------:|---------------:|----------:|----------:|
| all_heldout             | mlp                                               | 167683 |      0.015063  |       0.031118 |   0.6109  |  0.12441  |
| all_heldout             | traditional_optimal_transport_template_likelihood | 167683 |      0.01853   |       0.0263   |   0.61051 |  0.12731  |
| all_heldout             | gradient_boosted_trees                            | 167683 |      0.033098  |       0.026325 |   0.53508 |  0.12351  |
| all_heldout             | 1d_cnn                                            | 167683 |      0.033364  |       0.042907 |   0.60652 |  0.12522  |
| all_heldout             | compact_waveform_transformer                      | 167683 |      0.045418  |       0.053897 |   0.59711 |  0.12292  |
| all_heldout             | manifold_gated_residual_cnn_new                   | 167683 |      0.045803  |       0.046534 |   0.60933 |  0.12434  |
| all_heldout             | ridge                                             | 167683 |      0.15836   |       0.067395 |   0.65499 |  0.16194  |
| hard_saturated          | mlp                                               |  42197 |      0.0087602 |       0.02362  |   0.65892 |  0.17188  |
| hard_saturated          | 1d_cnn                                            |  42197 |      0.012855  |       0.019821 |   0.64542 |  0.16987  |
| hard_saturated          | traditional_optimal_transport_template_likelihood |  42197 |      0.016423  |       0.026342 |   0.51265 |  0.18108  |
| hard_saturated          | gradient_boosted_trees                            |  42197 |      0.028882  |       0.030592 |   0.50039 |  0.17313  |
| hard_saturated          | manifold_gated_residual_cnn_new                   |  42197 |      0.032578  |       0.031026 |   0.77503 |  0.16912  |
| hard_saturated          | compact_waveform_transformer                      |  42197 |      0.034801  |       0.036262 |   0.71699 |  0.17022  |
| hard_saturated          | ridge                                             |  42197 |      0.11263   |       0.048319 |   0.53191 |  0.16787  |
| high_pedestal_drift     | mlp                                               |  41266 |      0.071565  |       0.086553 |   0.58624 |  0.14081  |
| high_pedestal_drift     | traditional_optimal_transport_template_likelihood |  41266 |      0.096444  |       0.20604  |   0.55414 |  0.16867  |
| high_pedestal_drift     | gradient_boosted_trees                            |  41266 |      0.12795   |       0.090867 |   0.55576 |  0.13286  |
| high_pedestal_drift     | compact_waveform_transformer                      |  41266 |      0.15457   |       0.14447  |   0.58738 |  0.13286  |
| high_pedestal_drift     | 1d_cnn                                            |  41266 |      0.16115   |       0.15884  |   0.58206 |  0.13721  |
| high_pedestal_drift     | manifold_gated_residual_cnn_new                   |  41266 |      0.17635   |       0.15856  |   0.58398 |  0.1351   |
| high_pedestal_drift     | ridge                                             |  41266 |      0.3666    |       0.19217  |   0.60347 |  0.16481  |
| high_recovery_tail      | mlp                                               |  52263 |      0.014963  |       0.036528 |   0.66804 |  0.058855 |
| high_recovery_tail      | traditional_optimal_transport_template_likelihood |  52263 |      0.02029   |       0.030926 |   0.65431 |  0.042402 |
| high_recovery_tail      | gradient_boosted_trees                            |  52263 |      0.037606  |       0.016916 |   0.6119  |  0.050758 |
| high_recovery_tail      | compact_waveform_transformer                      |  52263 |      0.040994  |       0.053281 |   0.58294 |  0.064705 |
| high_recovery_tail      | 1d_cnn                                            |  52263 |      0.044238  |       0.063647 |   0.60956 |  0.069594 |
| high_recovery_tail      | manifold_gated_residual_cnn_new                   |  52263 |      0.046656  |       0.050439 |   0.56163 |  0.069639 |
| high_recovery_tail      | ridge                                             |  52263 |      0.17365   |       0.084142 |   0.74957 |  0.17107  |
| pileup_multiplicity_ge2 | mlp                                               |  18924 |      0.063733  |       0.10165  | nan       |  0.53487  |
| pileup_multiplicity_ge2 | gradient_boosted_trees                            |  18924 |      0.082484  |       0.075395 | nan       |  0.53678  |
| pileup_multiplicity_ge2 | traditional_optimal_transport_template_likelihood |  18924 |      0.083773  |       0.12716  | nan       |  0.53764  |
| pileup_multiplicity_ge2 | manifold_gated_residual_cnn_new                   |  18924 |      0.1106    |       0.11094  | nan       |  0.52906  |
| pileup_multiplicity_ge2 | compact_waveform_transformer                      |  18924 |      0.11654   |       0.11023  | nan       |  0.52904  |
| pileup_multiplicity_ge2 | 1d_cnn                                            |  18924 |      0.13812   |       0.15888  | nan       |  0.53027  |
| pileup_multiplicity_ge2 | ridge                                             |  18924 |      0.46982   |       0.20586  | nan       |  0.51194  |

The stratum scan isolates multi-hit pile-up, saturation knees, high recovery tail, and high pedestal drift. These are diagnostics, not randomized interventions. The bootstrap captures observed run-to-run variation but not unobserved electronics modes. The PID endpoint is a raw-waveform proxy rather than external particle identity. The energy endpoint is duplicate-readout charge closure rather than absolute MeV calibration. Neural models are intentionally compact for reproducibility; the winner should be treated as the best audited representation on this raw-ROOT support, not as a final detector-production calibration.

## Recommendation

Use `mlp` as the S70c representation for follow-up manifold-transfer studies, with run-block CIs, calibration-curve checks, and explicit pedestal/saturation strata. Use `traditional_optimal_transport_template_likelihood` as the transparent fallback when monotone quantile transport and template-sideband interpretability are more important than the multimetric rank gain.

## Artifact Index

`result.json`, `REPORT.md`, `transfer_summary.csv`, `strata_summary.csv`, `calibration_curves.csv`, `negative_controls.csv`, `manifold_transport.csv`, `event_predictions.csv`, `run_counts.csv`, `input_sha256.csv`, `manifest.json`, and `claimed_ticket.txt` are written in this report directory.

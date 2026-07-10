# P06f Consumer-Specific Dropout Veto Utility

Ticket `1781195579.1351.08f479c9` asks whether the P06e dropout-phase frontier is useful when the action is consumer-specific recover versus veto rather than unconditional correction. The raw B-stack ROOT reproduction gate passes at **640,737** selected B-stave pulses, exactly matching the registered anchor **640,737**.

## Methods

Let `e_{im}=10(t_hat_{im}-t_i)` ns be the held-out timing error for injected dropout row `i` and recovery method `m`. A policy `pi_c(i,m)` for consumer `c` either accepts the recovered pulse or vetoes it. For accepted rows `A_c,m`, the primary robust scale is

`sigma68_c,m = quantile_0.68(|e_i - median(e)| : i in A_c,m)`.

The consumer utility minimized in this audit is

`L_c,m = sigma68 + w_rms RMS(e) + w_tail P(|e|>10 ns) + w_veto P(veto)`.

Thresholds and weights differ by timing, charge, pile-up, PID, and energy consumers. The strong traditional arm is the P06e case-selected interpolation/template refit. ML/NN arms are ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-gated CNN new architecture. Confidence intervals are non-parametric run-block bootstraps over held-out Sample-II runs 58-63 and 65.

## Raw ROOT Reproduction

|   run |   events |   selected_pulses |    B2 |   B4 |   B6 |   B8 |
|------:|---------:|------------------:|------:|-----:|-----:|-----:|
|    31 |    39990 |             27871 | 26948 |  592 |  237 |   94 |
|    32 |    41921 |             28240 | 27316 |  605 |  224 |   95 |
|    33 |    57173 |             48737 | 47724 |  559 |  318 |  136 |
|    34 |    39765 |             34118 | 33373 |  412 |  244 |   89 |
|    35 |    27786 |             11667 | 11029 |  403 |  163 |   72 |
|    36 |    21764 |             10391 |  9847 |  340 |  143 |   61 |
|    37 |    50513 |             24537 | 22956 |  997 |  423 |  161 |
|    39 |    30321 |             14218 | 13174 |  663 |  273 |  108 |
|    40 |    32613 |             14708 | 13575 |  707 |  310 |  116 |
|    41 |    33997 |             16146 | 14963 |  758 |  298 |  127 |
|    42 |    33972 |             18112 | 16977 |  711 |  307 |  117 |
|    44 |     4294 |              2038 |  1884 |   93 |   44 |   17 |
|    45 |    48181 |             24333 | 22786 |  969 |  401 |  177 |
|    46 |     1441 |               687 |   675 |    7 |    3 |    2 |
|    47 |    10970 |              5276 |  5116 |   85 |   50 |   25 |
|    48 |    31713 |             14000 | 13044 |  599 |  245 |  112 |
|    49 |    32354 |             14815 | 13779 |  640 |  281 |  115 |
|    50 |    44804 |             35217 | 34088 |  659 |  330 |  140 |
|    51 |    20569 |             14740 | 14200 |  303 |  177 |   60 |
|    52 |    10005 |              7152 |  6893 |  148 |   76 |   35 |
|    53 |    39612 |             32200 | 31225 |  559 |  296 |  120 |
|    54 |    37413 |             30440 | 29493 |  536 |  298 |  113 |
|    55 |    24416 |             17387 | 16735 |  372 |  199 |   81 |
|    56 |    51823 |             40148 | 38730 |  825 |  421 |  172 |
|    57 |    31284 |             13833 | 12774 |  656 |  273 |  130 |
|    58 |    34141 |             16781 | 15791 |  591 |  285 |  114 |
|    59 |    42303 |             21377 | 13565 | 4527 | 2366 |  919 |
|    60 |    36074 |             17029 |  9873 | 4040 | 2189 |  927 |
|    61 |    36535 |             18965 | 11015 | 4401 | 2490 | 1059 |
|    62 |    37584 |             19089 | 11635 | 4183 | 2342 |  929 |
|    63 |    37030 |             18817 | 14566 | 2645 | 1153 |  453 |
|    64 |    35943 |             14630 | 11907 | 1689 |  763 |  271 |
|    65 |    38424 |             13038 | 11768 |  842 |  323 |  105 |

## Overall Consumer Scoreboard

| consumer   | method_label                     | policy             |   n_accepted |   veto_fraction |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   bad_tail_frac_abs_gt10ns |   consumer_utility_loss |
|:-----------|:---------------------------------|:-------------------|-------------:|----------------:|-------------:|--------------------:|---------------------:|---------------------------:|------------------------:|
| charge     | traditional                      | phase_recover_veto |        13880 |          0.1667 |       0.1658 |              0.1504 |               0.1806 |                   0.00562  |                  0.7176 |
| charge     | gradient_boosted_trees           | recover_all        |        16656 |          0      |       0.3535 |              0.3455 |               0.3613 |                   0.01105  |                  0.7666 |
| charge     | gradient_boosted_trees           | phase_recover_veto |        16656 |          0      |       0.3535 |              0.3457 |               0.3608 |                   0.01105  |                  0.7666 |
| charge     | traditional                      | recover_all        |        16656 |          0      |       0.218  |              0.2033 |               0.2366 |                   0.008646 |                  0.7804 |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto |         2776 |          0.8333 |       0.9379 |              0.895  |               0.9785 |                   0.01729  |                  1.599  |
| charge     | 1d_cnn                           | phase_recover_veto |         2776 |          0.8333 |       0.9783 |              0.9515 |               1.031  |                   0.01981  |                  1.692  |
| charge     | phase_gated_cnn_new_architecture | recover_all        |        16656 |          0      |       0.9988 |              0.9627 |               1.035  |                   0.02221  |                  1.714  |
| charge     | 1d_cnn                           | recover_all        |        16656 |          0      |       1.081  |              1.048  |               1.114  |                   0.0251   |                  1.867  |
| charge     | mlp                              | recover_all        |        16656 |          0      |       1.625  |              1.588  |               1.66   |                   0.01813  |                  2.213  |
| charge     | ridge                            | recover_all        |        16656 |          0      |       3.628  |              3.523  |               3.709  |                   0.04629  |                  4.893  |
| charge     | ridge                            | phase_recover_veto |            0 |          1      |     nan      |            nan      |             nan      |                 nan        |                nan      |
| charge     | mlp                              | phase_recover_veto |            0 |          1      |     nan      |            nan      |             nan      |                 nan        |                nan      |
| energy     | traditional                      | phase_recover_veto |        13880 |          0.1667 |       0.1658 |              0.1497 |               0.1807 |                   0.00562  |                  0.7289 |
| energy     | gradient_boosted_trees           | recover_all        |        16656 |          0      |       0.3535 |              0.3456 |               0.3611 |                   0.01105  |                  0.7887 |
| energy     | gradient_boosted_trees           | phase_recover_veto |        16656 |          0      |       0.3535 |              0.3451 |               0.3608 |                   0.01105  |                  0.7887 |
| energy     | traditional                      | recover_all        |        16656 |          0      |       0.218  |              0.2016 |               0.2367 |                   0.008646 |                  0.7977 |
| energy     | phase_gated_cnn_new_architecture | phase_recover_veto |         2776 |          0.8333 |       0.9379 |              0.8959 |               0.9837 |                   0.01729  |                  1.633  |
| energy     | 1d_cnn                           | phase_recover_veto |         2776 |          0.8333 |       0.9783 |              0.9503 |               1.035  |                   0.01981  |                  1.731  |
| energy     | phase_gated_cnn_new_architecture | recover_all        |        16656 |          0      |       0.9988 |              0.9666 |               1.034  |                   0.02221  |                  1.759  |
| energy     | 1d_cnn                           | recover_all        |        16656 |          0      |       1.081  |              1.044  |               1.118  |                   0.0251   |                  1.917  |
| energy     | mlp                              | recover_all        |        16656 |          0      |       1.625  |              1.588  |               1.662  |                   0.01813  |                  2.249  |
| energy     | ridge                            | recover_all        |        16656 |          0      |       3.628  |              3.525  |               3.711  |                   0.04629  |                  4.986  |
| energy     | ridge                            | phase_recover_veto |            0 |          1      |     nan      |            nan      |             nan      |                 nan        |                nan      |
| energy     | mlp                              | phase_recover_veto |            0 |          1      |     nan      |            nan      |             nan      |                 nan        |                nan      |
| pid        | traditional                      | recover_all        |        16656 |          0      |       0.218  |              0.2006 |               0.2356 |                   0.008646 |                  0.5295 |
| pid        | traditional                      | phase_recover_veto |        16656 |          0      |       0.218  |              0.2029 |               0.2358 |                   0.008646 |                  0.5295 |
| pid        | gradient_boosted_trees           | recover_all        |        16656 |          0      |       0.3535 |              0.3454 |               0.3612 |                   0.01105  |                  0.6292 |
| pid        | gradient_boosted_trees           | phase_recover_veto |        16656 |          0      |       0.3535 |              0.3454 |               0.3612 |                   0.01105  |                  0.6292 |
| pid        | phase_gated_cnn_new_architecture | phase_recover_veto |        11104 |          0.3333 |       0.8991 |              0.8614 |               0.9372 |                   0.02107  |                  1.421  |
| pid        | 1d_cnn                           | phase_recover_veto |         5552 |          0.6667 |       0.9106 |              0.8805 |               0.9373 |                   0.02233  |                  1.485  |
| pid        | phase_gated_cnn_new_architecture | recover_all        |        16656 |          0      |       0.9988 |              0.9644 |               1.033  |                   0.02221  |                  1.507  |
| pid        | 1d_cnn                           | recover_all        |        16656 |          0      |       1.081  |              1.041  |               1.117  |                   0.0251   |                  1.646  |
| pid        | mlp                              | phase_recover_veto |        13880 |          0.1667 |       1.532  |              1.501  |               1.564  |                   0.01751  |                  1.954  |
| pid        | mlp                              | recover_all        |        16656 |          0      |       1.625  |              1.588  |               1.655  |                   0.01813  |                  2.041  |
| pid        | ridge                            | recover_all        |        16656 |          0      |       3.628  |              3.517  |               3.72   |                   0.04629  |                  4.597  |
| pid        | ridge                            | phase_recover_veto |            0 |          1      |     nan      |            nan      |             nan      |                 nan        |                nan      |
| pileup     | traditional                      | phase_recover_veto |        13880 |          0.1667 |       0.1658 |              0.1502 |               0.1806 |                   0.00562  |                  0.4316 |
| pileup     | traditional                      | recover_all        |        16656 |          0      |       0.218  |              0.2021 |               0.236  |                   0.008646 |                  0.5553 |
| pileup     | gradient_boosted_trees           | recover_all        |        16656 |          0      |       0.3535 |              0.3449 |               0.3615 |                   0.01105  |                  0.7233 |
| pileup     | gradient_boosted_trees           | phase_recover_veto |        16656 |          0      |       0.3535 |              0.3447 |               0.3608 |                   0.01105  |                  0.7233 |

## Per-Consumer Winners

| consumer   | method_label   | policy             |   n_accepted |   veto_fraction |   sigma68_ns |   bad_tail_frac_abs_gt10ns |   consumer_utility_loss |
|:-----------|:---------------|:-------------------|-------------:|----------------:|-------------:|---------------------------:|------------------------:|
| charge     | traditional    | phase_recover_veto |        13880 |          0.1667 |       0.1658 |                   0.00562  |                  0.7176 |
| energy     | traditional    | phase_recover_veto |        13880 |          0.1667 |       0.1658 |                   0.00562  |                  0.7289 |
| pid        | traditional    | recover_all        |        16656 |          0      |       0.218  |                   0.008646 |                  0.5295 |
| pileup     | traditional    | phase_recover_veto |        13880 |          0.1667 |       0.1658 |                   0.00562  |                  0.4316 |
| timing     | traditional    | recover_all        |        16656 |          0      |       0.218  |                   0.008646 |                  0.443  |

## Recover-Versus-Veto Deltas

| consumer   | method_label                     |   delta_utility_veto_minus_recover_all |   delta_sigma68_veto_minus_recover_all_ns |   delta_bad_tail_veto_minus_recover_all |   delta_veto_fraction |
|:-----------|:---------------------------------|---------------------------------------:|------------------------------------------:|----------------------------------------:|----------------------:|
| charge     | 1d_cnn                           |                               -0.1753  |                                  -0.1024  |                              -0.005283  |                0.8333 |
| charge     | phase_gated_cnn_new_architecture |                               -0.1152  |                                  -0.06098 |                              -0.004923  |                0.8333 |
| charge     | traditional                      |                               -0.06279 |                                  -0.05223 |                              -0.003026  |                0.1667 |
| charge     | gradient_boosted_trees           |                                0       |                                   0       |                               0         |                0      |
| charge     | ridge                            |                              nan       |                                 nan       |                             nan         |                1      |
| charge     | mlp                              |                              nan       |                                 nan       |                             nan         |                1      |
| energy     | 1d_cnn                           |                               -0.1859  |                                  -0.1024  |                              -0.005283  |                0.8333 |
| energy     | phase_gated_cnn_new_architecture |                               -0.1251  |                                  -0.06098 |                              -0.004923  |                0.8333 |
| energy     | traditional                      |                               -0.06884 |                                  -0.05223 |                              -0.003026  |                0.1667 |
| energy     | gradient_boosted_trees           |                                0       |                                   0       |                               0         |                0      |
| energy     | ridge                            |                              nan       |                                 nan       |                             nan         |                1      |
| energy     | mlp                              |                              nan       |                                 nan       |                             nan         |                1      |
| pid        | 1d_cnn                           |                               -0.1617  |                                  -0.1702  |                              -0.002762  |                0.6667 |
| pid        | mlp                              |                               -0.08764 |                                  -0.09312 |                              -0.0006244 |                0.1667 |
| pid        | phase_gated_cnn_new_architecture |                               -0.08643 |                                  -0.09976 |                              -0.001141  |                0.3333 |
| pid        | traditional                      |                                0       |                                   0       |                               0         |                0      |
| pid        | gradient_boosted_trees           |                                0       |                                   0       |                               0         |                0      |
| pid        | ridge                            |                              nan       |                                 nan       |                             nan         |                1      |
| pileup     | mlp                              |                               -0.3095  |                                  -0.3524  |                              -0.0008405 |                0.8333 |
| pileup     | phase_gated_cnn_new_architecture |                               -0.1532  |                                  -0.06098 |                              -0.004923  |                0.8333 |
| pileup     | traditional                      |                               -0.1237  |                                  -0.05223 |                              -0.003026  |                0.1667 |
| pileup     | gradient_boosted_trees           |                                0       |                                   0       |                               0         |                0      |
| pileup     | ridge                            |                              nan       |                                 nan       |                             nan         |                1      |
| pileup     | 1d_cnn                           |                              nan       |                                 nan       |                             nan         |                1      |
| timing     | 1d_cnn                           |                               -0.1249  |                                  -0.2659  |                               0.0001201 |                0.6667 |
| timing     | phase_gated_cnn_new_architecture |                               -0.1115  |                                  -0.2536  |                               0.0001201 |                0.6667 |
| timing     | traditional                      |                                0       |                                   0       |                               0         |                0      |
| timing     | gradient_boosted_trees           |                                0       |                                   0       |                               0         |                0      |
| timing     | ridge                            |                              nan       |                                 nan       |                             nan         |                1      |
| timing     | mlp                              |                              nan       |                                 nan       |                             nan         |                1      |

## Phase and Case Diagnostics

| consumer   | method_label                     | policy             | dropout_phase   | dropout_case        |   n_accepted |   veto_fraction |   sigma68_ns |   bad_tail_frac_abs_gt10ns |
|:-----------|:---------------------------------|:-------------------|:----------------|:--------------------|-------------:|----------------:|-------------:|---------------------------:|
| charge     | 1d_cnn                           | phase_recover_veto | leading_edge    | cfd_crossing_single |         2776 |               0 |       0.9783 |                   0.01981  |
| charge     | 1d_cnn                           | phase_recover_veto | tail            | early_tail_pair     |            0 |               1 |     nan      |                 nan        |
| charge     | 1d_cnn                           | phase_recover_veto | tail            | late_tail_pair      |            0 |               1 |     nan      |                 nan        |
| charge     | 1d_cnn                           | phase_recover_veto | leading_edge    | leading_edge_pair   |            0 |               1 |     nan      |                 nan        |
| charge     | 1d_cnn                           | phase_recover_veto | peak            | peak_contiguous     |            0 |               1 |     nan      |                 nan        |
| charge     | 1d_cnn                           | phase_recover_veto | peak            | peak_single         |            0 |               1 |     nan      |                 nan        |
| charge     | 1d_cnn                           | recover_all        | leading_edge    | cfd_crossing_single |         2776 |               0 |       0.9783 |                   0.01981  |
| charge     | 1d_cnn                           | recover_all        | tail            | early_tail_pair     |         2776 |               0 |       0.8357 |                   0.02486  |
| charge     | 1d_cnn                           | recover_all        | tail            | late_tail_pair      |         2776 |               0 |       0.7823 |                   0.02558  |
| charge     | 1d_cnn                           | recover_all        | leading_edge    | leading_edge_pair   |         2776 |               0 |       2.007  |                   0.0245   |
| charge     | 1d_cnn                           | recover_all        | peak            | peak_contiguous     |         2776 |               0 |       1.233  |                   0.02702  |
| charge     | 1d_cnn                           | recover_all        | peak            | peak_single         |         2776 |               0 |       1.138  |                   0.02882  |
| charge     | gradient_boosted_trees           | phase_recover_veto | leading_edge    | cfd_crossing_single |         2776 |               0 |       0.3308 |                   0.008646 |
| charge     | gradient_boosted_trees           | phase_recover_veto | tail            | early_tail_pair     |         2776 |               0 |       0.2955 |                   0.01117  |
| charge     | gradient_boosted_trees           | phase_recover_veto | tail            | late_tail_pair      |         2776 |               0 |       0.3146 |                   0.01045  |
| charge     | gradient_boosted_trees           | phase_recover_veto | leading_edge    | leading_edge_pair   |         2776 |               0 |       0.6174 |                   0.009366 |
| charge     | gradient_boosted_trees           | phase_recover_veto | peak            | peak_contiguous     |         2776 |               0 |       0.357  |                   0.01297  |
| charge     | gradient_boosted_trees           | phase_recover_veto | peak            | peak_single         |         2776 |               0 |       0.3202 |                   0.01369  |
| charge     | gradient_boosted_trees           | recover_all        | leading_edge    | cfd_crossing_single |         2776 |               0 |       0.3308 |                   0.008646 |
| charge     | gradient_boosted_trees           | recover_all        | tail            | early_tail_pair     |         2776 |               0 |       0.2955 |                   0.01117  |
| charge     | gradient_boosted_trees           | recover_all        | tail            | late_tail_pair      |         2776 |               0 |       0.3146 |                   0.01045  |
| charge     | gradient_boosted_trees           | recover_all        | leading_edge    | leading_edge_pair   |         2776 |               0 |       0.6174 |                   0.009366 |
| charge     | gradient_boosted_trees           | recover_all        | peak            | peak_contiguous     |         2776 |               0 |       0.357  |                   0.01297  |
| charge     | gradient_boosted_trees           | recover_all        | peak            | peak_single         |         2776 |               0 |       0.3202 |                   0.01369  |
| charge     | mlp                              | phase_recover_veto | leading_edge    | cfd_crossing_single |            0 |               1 |     nan      |                 nan        |
| charge     | mlp                              | phase_recover_veto | tail            | early_tail_pair     |            0 |               1 |     nan      |                 nan        |
| charge     | mlp                              | phase_recover_veto | tail            | late_tail_pair      |            0 |               1 |     nan      |                 nan        |
| charge     | mlp                              | phase_recover_veto | leading_edge    | leading_edge_pair   |            0 |               1 |     nan      |                 nan        |
| charge     | mlp                              | phase_recover_veto | peak            | peak_contiguous     |            0 |               1 |     nan      |                 nan        |
| charge     | mlp                              | phase_recover_veto | peak            | peak_single         |            0 |               1 |     nan      |                 nan        |
| charge     | mlp                              | recover_all        | leading_edge    | cfd_crossing_single |         2776 |               0 |       1.532  |                   0.01657  |
| charge     | mlp                              | recover_all        | tail            | early_tail_pair     |         2776 |               0 |       1.272  |                   0.01729  |
| charge     | mlp                              | recover_all        | tail            | late_tail_pair      |         2776 |               0 |       1.557  |                   0.01873  |
| charge     | mlp                              | recover_all        | leading_edge    | leading_edge_pair   |         2776 |               0 |       2.231  |                   0.02125  |
| charge     | mlp                              | recover_all        | peak            | peak_contiguous     |         2776 |               0 |       1.554  |                   0.01585  |
| charge     | mlp                              | recover_all        | peak            | peak_single         |         2776 |               0 |       1.613  |                   0.01909  |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto | leading_edge    | cfd_crossing_single |         2776 |               0 |       0.9379 |                   0.01729  |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto | tail            | early_tail_pair     |            0 |               1 |     nan      |                 nan        |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto | tail            | late_tail_pair      |            0 |               1 |     nan      |                 nan        |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto | leading_edge    | leading_edge_pair   |            0 |               1 |     nan      |                 nan        |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto | peak            | peak_contiguous     |            0 |               1 |     nan      |                 nan        |
| charge     | phase_gated_cnn_new_architecture | phase_recover_veto | peak            | peak_single         |            0 |               1 |     nan      |                 nan        |
| charge     | phase_gated_cnn_new_architecture | recover_all        | leading_edge    | cfd_crossing_single |         2776 |               0 |       0.9379 |                   0.01729  |
| charge     | phase_gated_cnn_new_architecture | recover_all        | tail            | early_tail_pair     |         2776 |               0 |       0.7502 |                   0.02197  |
| charge     | phase_gated_cnn_new_architecture | recover_all        | tail            | late_tail_pair      |         2776 |               0 |       0.7372 |                   0.02269  |
| charge     | phase_gated_cnn_new_architecture | recover_all        | leading_edge    | leading_edge_pair   |         2776 |               0 |       1.826  |                   0.02341  |
| charge     | phase_gated_cnn_new_architecture | recover_all        | peak            | peak_contiguous     |         2776 |               0 |       1.071  |                   0.02233  |
| charge     | phase_gated_cnn_new_architecture | recover_all        | peak            | peak_single         |         2776 |               0 |       0.9783 |                   0.02558  |
| charge     | ridge                            | phase_recover_veto | leading_edge    | cfd_crossing_single |            0 |               1 |     nan      |                 nan        |
| charge     | ridge                            | phase_recover_veto | tail            | early_tail_pair     |            0 |               1 |     nan      |                 nan        |
| charge     | ridge                            | phase_recover_veto | tail            | late_tail_pair      |            0 |               1 |     nan      |                 nan        |
| charge     | ridge                            | phase_recover_veto | leading_edge    | leading_edge_pair   |            0 |               1 |     nan      |                 nan        |
| charge     | ridge                            | phase_recover_veto | peak            | peak_contiguous     |            0 |               1 |     nan      |                 nan        |
| charge     | ridge                            | phase_recover_veto | peak            | peak_single         |            0 |               1 |     nan      |                 nan        |
| charge     | ridge                            | recover_all        | leading_edge    | cfd_crossing_single |         2776 |               0 |       3.321  |                   0.03206  |
| charge     | ridge                            | recover_all        | tail            | early_tail_pair     |         2776 |               0 |       3.427  |                   0.04611  |
| charge     | ridge                            | recover_all        | tail            | late_tail_pair      |         2776 |               0 |       3.404  |                   0.04467  |
| charge     | ridge                            | recover_all        | leading_edge    | leading_edge_pair   |         2776 |               0 |       4.648  |                   0.05728  |
| charge     | ridge                            | recover_all        | peak            | peak_contiguous     |         2776 |               0 |       3.422  |                   0.05151  |
| charge     | ridge                            | recover_all        | peak            | peak_single         |         2776 |               0 |       3.49   |                   0.04611  |

## Systematics and Caveats

- The consumer tasks are operational utilities over the P06e injected-dropout rows, not independent PID or calorimetric truth labels.
- Veto penalties are explicit and finite; a detector operation with much higher dead-time cost should rescale `w_veto` before adoption.
- Phase gates are frozen from P06e method/case recoverability metrics and evaluated on held-out Sample-II rows; the row population is still inherited from the P06e injection design.
- The raw ROOT gate fixes the selected pulse population, but it does not validate downstream non-timing truth labels.
- Correlated rows from the same event can remain after injection; run-block bootstrap is the relevant uncertainty unit, but it cannot remove all within-run dependence.

## Verdict

`result.json` names **traditional** under **phase_recover_veto** as the overall winner with mean consumer utility loss `0.5701`. The central result is conservative: the traditional recovery remains the strongest general policy, while phase recover/veto is useful only when the consumer places enough weight on rare tails to justify lost acceptance.

Artifacts are in `reports/1781195579.1351.08f479c9__p06f_consumer_dropout_veto` and root-level `result.json` mirrors the machine-readable verdict.

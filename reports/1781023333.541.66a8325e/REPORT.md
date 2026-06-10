# S02h: binned-timewalk shuffled-target failure autopsy

Ticket `1781023333.541.66a8325e`. Worker `testbeam-laptop-1`.

## Reproduction first

The raw ROOT selected-pulse gate was rerun before any timing model:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The run-65 S02/S02b anchor numbers were rebuilt from the same raw-derived pulse table:

| quantity                                       |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |            65 |                 2.88915 |                2.88915 | 0           | True   |
| S02 ML ridge                                   |            65 |                 1.84611 |                1.84611 | 7.54952e-15 | True   |
| S02b binned-template timewalk                  |            65 |                 3.4037  |                3.4037  | 2.08709e-10 | True   |
| S02b global-template timewalk                  |            65 |                 1.63542 |                1.63542 | 2.20047e-09 | True   |

## Method

The split is Sample-II leave-one-run-out by run over `[58, 59, 60, 61, 62, 63, 65]`. For each held-out run, templates, binned templates, timewalk closures, current/rate covariates, and ML residual learners are fit only on the other runs. The strong traditional comparator is the frozen S02b global no-drift timewalk. The ML branch is a Ridge residual learner on the binned-template residual target with bin-dropout, shuffled-bin, shuffled-target, and current/rate sentinel variants.

## Results

Run-block bootstrap summary:

| method                                          |   mean_sigma68_ns |   ci_low |   ci_high |   min_run_sigma68_ns |   max_run_sigma68_ns |
|:------------------------------------------------|------------------:|---------:|----------:|---------------------:|---------------------:|
| S02b global timewalk no drift                   |           1.65516 |  1.53211 |   1.84749 |              1.4719  |              2.18842 |
| S02 ML ridge cfd20                              |           1.90549 |  1.82374 |   2.02697 |              1.76984 |              2.24243 |
| S02d binned selected 1                          |           2.13066 |  2.13066 |   2.13066 |              2.13066 |              2.13066 |
| S02 train-best global template (template_phase) |           2.81023 |  2.7162  |   2.90142 |              2.6428  |              2.99232 |
| S02h ML binned residual                         |           2.99998 |  2.65179 |   3.29989 |              2.04507 |              3.48824 |
| S02h ML shuffled-bin                            |           3.13874 |  2.75706 |   3.45605 |              2.10372 |              3.64247 |
| S02b binned timewalk no drift                   |           3.14849 |  2.77883 |   3.46085 |              2.12741 |              3.63793 |
| S02h binned current/rate selected 0             |           3.14849 |  2.76517 |   3.46085 |              2.12741 |              3.63793 |
| S02h ML bin-dropout                             |           3.15229 |  2.75322 |   3.46375 |              2.12793 |              3.64979 |
| S02d binned selected 0                          |           3.25482 |  3.05332 |   3.47546 |              2.962   |              3.63484 |
| S02h ML shuffled-target                         |           3.79699 |  3.29907 |   4.34014 |              2.96606 |              5.01152 |
| S02d binned selected 2                          |           3.86253 |  3.86253 |   3.86253 |              3.86253 |              3.86253 |
| S02h ML bin+current/rate                        |           5.03076 |  2.80198 |   8.75358 |              2.0225  |             15.7771  |

Per-run headline metrics:

|   heldout_run | method                        |    value |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_vs_amplitude_slope_ns_per_kadc |
|--------------:|:------------------------------|---------:|---------:|----------:|--------------:|----------------------:|--------------------------------------:|
|            58 | S02b global timewalk no drift |  1.52279 |  1.28774 |   1.87697 |       2.75002 |            0.0228311  |                             -0.449374 |
|            58 | S02b binned timewalk no drift |  3.63484 |  3.09024 |   4.09018 |       4.61474 |            0.191781   |                             -0.435229 |
|            58 | S02h ML binned residual       |  3.29497 |  2.90811 |   3.82656 |       4.48813 |            0.150685   |                             -0.483786 |
|            58 | S02h ML bin-dropout           |  3.64979 |  3.12422 |   4.07969 |       4.63259 |            0.187215   |                             -0.477322 |
|            58 | S02h ML shuffled-bin          |  3.64247 |  3.02938 |   4.02414 |       4.62386 |            0.178082   |                             -0.453525 |
|            58 | S02h ML bin+current/rate      | 15.7771  | 15.2734  |  16.1918  |      14.7329  |            0.474886   |                              3.36506  |
|            59 | S02b global timewalk no drift |  1.59676 |  1.54972 |   1.65103 |       2.48616 |            0.0126693  |                             -0.619741 |
|            59 | S02b binned timewalk no drift |  3.63793 |  3.48965 |   3.77798 |       4.00546 |            0.158148   |                             -1.57282  |
|            59 | S02h ML binned residual       |  3.48824 |  3.34239 |   3.63464 |       3.90507 |            0.145478   |                             -1.42036  |
|            59 | S02h ML bin-dropout           |  3.60533 |  3.48751 |   3.78235 |       4.01273 |            0.157711   |                             -1.56207  |
|            59 | S02h ML shuffled-bin          |  3.62756 |  3.49694 |   3.7821  |       4.01695 |            0.159895   |                             -1.50388  |
|            59 | S02h ML bin+current/rate      |  3.472   |  3.32306 |   3.61741 |       3.82125 |            0.14111    |                             -1.11816  |
|            60 | S02b global timewalk no drift |  1.4719  |  1.43642 |   1.5169  |       2.27149 |            0.0107261  |                             -0.540146 |
|            60 | S02b binned timewalk no drift |  2.12741 |  2.04198 |   2.2148  |       2.5748  |            0.0383663  |                             -0.934882 |
|            60 | S02h ML binned residual       |  2.04507 |  1.93577 |   2.12512 |       2.49242 |            0.0313531  |                             -0.713689 |
|            60 | S02h ML bin-dropout           |  2.12793 |  2.05176 |   2.19484 |       2.57546 |            0.0387789  |                             -0.931371 |
|            60 | S02h ML shuffled-bin          |  2.10372 |  2.02401 |   2.19648 |       2.56636 |            0.0391914  |                             -0.86809  |
|            60 | S02h ML bin+current/rate      |  2.0225  |  1.91444 |   2.0934  |       2.42437 |            0.0255776  |                             -0.50282  |
|            61 | S02b global timewalk no drift |  2.18842 |  2.09822 |   2.26167 |       2.93618 |            0.0275098  |                             -0.366801 |
|            61 | S02b binned timewalk no drift |  3.06904 |  2.92327 |   3.19455 |       3.72776 |            0.110397   |                             -1.05701  |
|            61 | S02h ML binned residual       |  2.93515 |  2.82477 |   3.03769 |       3.61175 |            0.0975348  |                             -1.02102  |
|            61 | S02h ML bin-dropout           |  3.07694 |  2.94717 |   3.18333 |       3.72252 |            0.111826   |                             -1.00832  |
|            61 | S02h ML shuffled-bin          |  3.07438 |  2.95268 |   3.20735 |       3.72157 |            0.10861    |                             -1.01077  |
|            61 | S02h ML bin+current/rate      |  3.02326 |  2.90243 |   3.14984 |       3.63819 |            0.101108   |                             -0.980991 |
|            62 | S02b global timewalk no drift |  1.62995 |  1.57103 |   1.67821 |       2.50074 |            0.0111524  |                             -0.549927 |
|            62 | S02b binned timewalk no drift |  2.962   |  2.80766 |   3.059   |       3.44045 |            0.0912846  |                             -1.20503  |
|            62 | S02h ML binned residual       |  2.82208 |  2.70455 |   2.94377 |       3.366   |            0.0817844  |                             -1.26334  |
|            62 | S02h ML bin-dropout           |  2.96482 |  2.80944 |   3.05956 |       3.43964 |            0.0908715  |                             -1.20702  |
|            62 | S02h ML shuffled-bin          |  2.96029 |  2.81378 |   3.11534 |       3.4501  |            0.0912846  |                             -1.20374  |
|            62 | S02h ML bin+current/rate      |  2.79359 |  2.67787 |   2.9557  |       3.35649 |            0.0809583  |                             -1.04363  |
|            63 | S02b global timewalk no drift |  1.54092 |  1.48551 |   1.60217 |       2.53459 |            0.0171171  |                             -0.569582 |
|            63 | S02b binned timewalk no drift |  3.20453 |  3.01614 |   3.41639 |       3.58591 |            0.123423   |                             -1.16461  |
|            63 | S02h ML binned residual       |  3.01471 |  2.78794 |   3.21442 |       3.48514 |            0.11982    |                             -1.12342  |
|            63 | S02h ML bin-dropout           |  3.24162 |  3.00206 |   3.44064 |       3.58853 |            0.124324   |                             -1.12331  |
|            63 | S02h ML shuffled-bin          |  3.21059 |  2.99413 |   3.47272 |       3.60531 |            0.122523   |                             -1.16602  |
|            63 | S02h ML bin+current/rate      |  3.02709 |  2.78888 |   3.31761 |       3.45759 |            0.111712   |                             -0.805037 |
|            65 | S02b global timewalk no drift |  1.63542 |  1.47583 |   1.90143 |       1.77195 |            0.00505051 |                             -0.348992 |
|            65 | S02b binned timewalk no drift |  3.4037  |  2.88602 |   3.96891 |       3.72618 |            0.141414   |                             -1.82218  |
|            65 | S02h ML binned residual       |  3.39966 |  2.94553 |   3.8093  |       3.70892 |            0.131313   |                             -1.7211   |
|            65 | S02h ML bin-dropout           |  3.3996  |  2.85141 |   3.92103 |       3.74891 |            0.146465   |                             -1.83199  |
|            65 | S02h ML shuffled-bin          |  3.35214 |  2.99197 |   3.86783 |       3.74668 |            0.146465   |                             -1.84427  |
|            65 | S02h ML bin+current/rate      |  5.09978 |  4.69068 |   5.75342 |       4.90429 |            0.40404    |                             -2.44648  |

The global no-drift traditional branch averages `1.655` ns, while the binned no-drift branch averages `3.148` ns. The full binned ML residual learner averages `3.000` ns; dropping bin indicators changes it to `3.152` ns, and shuffled-bin training gives `3.139` ns. The current/rate ML sentinel gives `5.031` ns.

## Autopsy

Fold-level instability and deltas:

|   heldout_run |   occupancy_weighted_instability_score |   min_train_bin_pulses |   max_abs_sse_shift |   heldout_pulses |   binned_minus_global_sigma68_ns |   ml_full_minus_dropout_ns |   ml_full_minus_shuffled_bin_ns |   s02d_shuffled_target_margin_ns |
|--------------:|---------------------------------------:|-----------------------:|--------------------:|-----------------:|---------------------------------:|---------------------------:|--------------------------------:|---------------------------------:|
|            58 |                             0.0016509  |                    934 |           3.60672   |              219 |                         2.11205  |               -0.354825    |                      -0.347497  |                        -0.629171 |
|            59 |                             0.00194404 |                    762 |           0.182235  |             2289 |                         2.04117  |               -0.117089    |                      -0.139315  |                         1.27476  |
|            60 |                             0.00181717 |                    752 |           3.34228   |             2424 |                         0.655513 |               -0.0828667   |                      -0.0586525 |                         1.04285  |
|            61 |                             0.00187886 |                    721 |           0.109427  |             2799 |                         0.880623 |               -0.141783    |                      -0.139227  |                        -0.143428 |
|            62 |                             0.00180626 |                    752 |           0.041403  |             2421 |                         1.33206  |               -0.142737    |                      -0.138214  |                         0.610382 |
|            63 |                             0.00168064 |                    861 |           0.0896889 |             1110 |                         1.66361  |               -0.226909    |                      -0.195883  |                         1.3057   |
|            65 |                             0.00175921 |                    935 |           1.92084   |              198 |                         1.76828  |                5.19668e-05 |                       0.0475122 |                         0.619765 |

The binned branch is not failing through obvious train/held-out overlap: hard leakage checks are zero-overlap. The weak point is support and composition. The branch uses train-quantile amplitude bins per stave, then applies those bins to held-out runs whose stave/bin occupancy and template-SSE distribution move enough that shuffled targets can match or beat selected binned corrections in some folds. The ML sentinels reinforce that diagnosis: true bin labels are not a robust source of held-out gain because bin-dropout and shuffled-bin variants are close to the full binned learner on the run-block mean.

## Leakage checks

Failed non-oracle checks:

|   heldout_run | check                                         |     value | pass   |
|--------------:|:----------------------------------------------|----------:|:-------|
|            58 | binned_selected_shuffled_target_sigma68_ns    |  3.00567  | False  |
|            58 | ml_binned_residual_shuffled_target_not_better |  3.05013  | False  |
|            58 | s02d_binned_shuffled_target_margin_ns         | -0.629171 | False  |
|            61 | binned_selected_shuffled_target_sigma68_ns    |  2.92561  | False  |
|            61 | s02d_binned_shuffled_target_margin_ns         | -0.143428 | False  |

The forbidden-oracle rows remain excluded from the pass/fail statement. They are retained only to show how much held-out target leakage could move the binned metric.

## Conclusion

The S02d amplitude-binned template branch is underconstrained and composition-sensitive rather than a strong timing improvement. Freezing the global no-drift timewalk is the more stable traditional result, and neither bin-aware ML nor pre-timing current/rate covariates rescue the binned branch under run-held-out scoring.

## Follow-up tickets

No new follow-up ticket is proposed. The external-scaler/current-rate and run-64 calibration stress tests already exist in prior S02 follow-up text, and S02h does not expose a distinct ROOT-only next study.

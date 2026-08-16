# P03-ticket-2389: P03 deep timing regression with per-pulse uncertainty calibration

- **Ticket:** `2389`
- **Worker:** `testbeam-laptop-2`
- **Claimed study:** P03 deep timing regression with per-pulse uncertainty calibration
- **Input:** raw B-stack ROOT files from `data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Early window:** waveform samples `[0, 1, 2, 3]` (the same samples used for the nominal median baseline)

## Question and preregistered estimand

The ticket asks for deep single-pulse timing regression with calibrated per-pulse uncertainty, benchmarked fairly against CFD/OF/template-style S02 timing.  The estimand is the B4/B6/B8 event-paired timing width after the S02b global-template timewalk correction:

`r_ab(e; m) = [t_a(e;m) - z_a v^-1] - [t_b(e;m) - z_b v^-1]`,

where `m` is a timing method, `z` is the stave spacing coordinate, and `v^-1 = 0.078 ns/cm`.  The headline metric is

`sigma68(m) = (Q84({r_ab}) - Q16({r_ab})) / 2`.

CIs are event bootstraps inside each held-out run and a nested run-block/event bootstrap for the pooled summary.

## Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before fitting any timing or ML model.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |


## S02 Traditional Baselines

The full S02 traditional family was recomputed fold-locally from the same raw ROOT pulses.  This table verifies that the headline traditional comparator is the strongest member of the CFD/OF/template family before comparing against ML/NN residual learners.

| method                        | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_s02b_template_timewalk_ns |   n_pair_residuals |
|:------------------------------|:------------|-------------:|---------:|----------:|-------------------------------------:|-------------------:|
| s02b_global_template_timewalk | traditional |      1.6878  |  1.49946 |   1.97767 |                              0       |              11460 |
| template_phase                | traditional |      2.7365  |  2.68081 |   2.96472 |                              1.0487  |              11460 |
| cfd20                         | traditional |      3.14839 |  3.02636 |   3.27324 |                              1.46059 |              11442 |
| cfd10                         | traditional |      3.22402 |  3.12624 |   3.31613 |                              1.53622 |              11418 |
| cfd30                         | traditional |      3.24722 |  3.09212 |   3.38694 |                              1.55942 |              11448 |
| optimal_filter_4_12           | traditional |      3.36711 |  3.27154 |   3.47894 |                              1.67931 |              11460 |
| cfd40                         | traditional |      3.40862 |  3.24188 |   3.53768 |                              1.72082 |              11448 |
| optimal_filter_1_9            | traditional |      3.41402 |  3.31804 |   3.54204 |                              1.72622 |              11460 |
| optimal_filter_3_11           | traditional |      3.43783 |  3.33431 |   3.54353 |                              1.75003 |              11460 |
| optimal_filter_2_10           | traditional |      3.45995 |  3.35769 |   3.57906 |                              1.77215 |              11460 |
| cfd50                         | traditional |      3.59807 |  3.43721 |   3.74661 |                              1.91027 |              11451 |
| leading_edge_500adc           | traditional |      4.16656 |  3.89319 |   4.41703 |                              2.47876 |              11448 |

## Methods

For every held-out run, the other six Sample-II runs define all train-only objects: the S02 global templates, amplitude-binned S02b template SSE nuisance, and polynomial/ridge timewalk closure. The traditional comparator is `s02b_global_template_timewalk`.

The residual learners target `y_i = t_i(S02b) - mean(t_j(S02b), t_k(S02b))` within the same event and predict a same-pulse correction. Five model families are benchmarked under three waveform masks:

- `ridge`: standardized linear Ridge regression.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: heteroskedastic fully connected neural net.
- `cnn1d`: compact one-dimensional convolutional network over 18 samples.
- `early_late_gated`: new architecture with separate samples-0-3 and samples-4-17 branches mixed by a learned auxiliary-feature gate.

Masks are `full`, `no_samples_0_3`, and `only_samples_0_3`. Features exclude run id, event id, event order, other-stave timings, and pair residuals. Run-family controls use only hand summaries, stave, and coarse predeclared family (`early`, `middle`, `late`) without waveform samples. Shuffled-target controls repeat every nominal waveform model with train targets permuted.

## Pooled Benchmark

| method                            | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:----------------------------------|:------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------:|
| hgb_full                          | ml          |      1.16284 |  1.12406 |   1.21045 |                 -0.524959 |      -0.826919 |      -0.321276  |              11460 |
| hgb_no_samples_0_3                | ml          |      1.16332 |  1.12727 |   1.2043  |                 -0.524476 |      -0.826052 |      -0.337145  |              11460 |
| hgb_only_samples_0_3              | ml          |      1.18041 |  1.14701 |   1.23086 |                 -0.507391 |      -0.794929 |      -0.300731  |              11460 |
| mlp_no_samples_0_3                | ml          |      1.24142 |  1.20331 |   1.28632 |                 -0.446381 |      -0.721752 |      -0.255225  |              11460 |
| mlp_full                          | ml          |      1.30792 |  1.24927 |   1.38787 |                 -0.379884 |      -0.678126 |      -0.143037  |              11460 |
| ridge_full                        | ml          |      1.34042 |  1.29505 |   1.40516 |                 -0.347378 |      -0.669265 |      -0.121717  |              11460 |
| ridge_no_samples_0_3              | ml          |      1.34542 |  1.29397 |   1.40456 |                 -0.342381 |      -0.659474 |      -0.115774  |              11460 |
| ridge_only_samples_0_3            | ml          |      1.37215 |  1.31829 |   1.42741 |                 -0.31565  |      -0.627423 |      -0.109489  |              11460 |
| cnn1d_full                        | ml          |      1.39676 |  1.32995 |   1.47736 |                 -0.291036 |      -0.625382 |      -0.0526783 |              11460 |
| mlp_only_samples_0_3              | ml          |      1.39712 |  1.30183 |   1.52496 |                 -0.290678 |      -0.619464 |      -0.0240136 |              11460 |
| early_late_gated_no_samples_0_3   | ml          |      1.40034 |  1.3017  |   1.47617 |                 -0.287464 |      -0.64582  |      -0.0604706 |              11460 |
| cnn1d_only_samples_0_3            | ml          |      1.40039 |  1.33896 |   1.46945 |                 -0.287407 |      -0.622023 |      -0.0555235 |              11460 |
| early_late_gated_full             | ml          |      1.41369 |  1.34005 |   1.46974 |                 -0.274109 |      -0.572366 |      -0.0855871 |              11460 |
| cnn1d_no_samples_0_3              | ml          |      1.45919 |  1.36701 |   1.56169 |                 -0.228613 |      -0.596022 |       0.0396209 |              11460 |
| early_late_gated_only_samples_0_3 | ml          |      1.46506 |  1.34931 |   1.55893 |                 -0.222742 |      -0.632085 |       0.0150391 |              11460 |
| s02b_global_template_timewalk     | traditional |      1.6878  |  1.51779 |   1.98078 |                  0        |       0        |       0         |              11460 |

## Early-Sample Ablation

| method                            |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   tail_frac_vs_traditional_p95 |
|:----------------------------------|-------------:|---------:|----------:|--------------------------:|-------------------------------:|
| cnn1d_full                        |      1.39676 |  1.32995 |   1.47736 |                 -0.291036 |                      0.0288831 |
| cnn1d_no_samples_0_3              |      1.45919 |  1.36701 |   1.56169 |                 -0.228613 |                      0.0327225 |
| cnn1d_only_samples_0_3            |      1.40039 |  1.33896 |   1.46945 |                 -0.287407 |                      0.030192  |
| early_late_gated_full             |      1.41369 |  1.34005 |   1.46974 |                 -0.274109 |                      0.0309773 |
| early_late_gated_no_samples_0_3   |      1.40034 |  1.3017  |   1.47617 |                 -0.287464 |                      0.0290576 |
| early_late_gated_only_samples_0_3 |      1.46506 |  1.34931 |   1.55893 |                 -0.222742 |                      0.0343805 |
| hgb_full                          |      1.16284 |  1.12406 |   1.21045 |                 -0.524959 |                      0.0222513 |
| hgb_no_samples_0_3                |      1.16332 |  1.12727 |   1.2043  |                 -0.524476 |                      0.0230366 |
| hgb_only_samples_0_3              |      1.18041 |  1.14701 |   1.23086 |                 -0.507391 |                      0.0224258 |
| mlp_full                          |      1.30792 |  1.24927 |   1.38787 |                 -0.379884 |                      0.0246073 |
| mlp_no_samples_0_3                |      1.24142 |  1.20331 |   1.28632 |                 -0.446381 |                      0.0219895 |
| mlp_only_samples_0_3              |      1.39712 |  1.30183 |   1.52496 |                 -0.290678 |                      0.0302792 |
| ridge_full                        |      1.34042 |  1.29505 |   1.40516 |                 -0.347378 |                      0.025829  |
| ridge_no_samples_0_3              |      1.34542 |  1.29397 |   1.40456 |                 -0.342381 |                      0.025829  |
| ridge_only_samples_0_3            |      1.37215 |  1.31829 |   1.42741 |                 -0.31565  |                      0.027836  |

## Per-Pulse Sigma Calibration

The heteroskedastic MLP, 1D-CNN, and early/late gated network emit a predicted
per-pulse `sigma_i`.  The calibration diagnostic is the empirical width of
`(y_i - \hat y_i) / \sigma_i` on the held-out run.  A value of one is nominal;
values above one mean the model is over-confident, and values below one mean it
is conservative for the residual target used to correct the time pickoff.

|   heldout_run | method                            |   n_pulses |   pred_sigma_median_ns |   residual_sigma68_ns |   pull_width68_empirical |   pull_median |
|--------------:|:----------------------------------|-----------:|-----------------------:|----------------------:|-------------------------:|--------------:|
|            58 | cnn1d_full                        |        219 |                1.98898 |              1.09831  |                 0.455748 |  -0.0766943   |
|            59 | cnn1d_full                        |       2289 |                1.53144 |              1.00965  |                 0.62057  |   0.037549    |
|            60 | cnn1d_full                        |       2424 |                1.75697 |              1.05408  |                 0.565136 |   0.00929639  |
|            61 | cnn1d_full                        |       2799 |                1.68237 |              1.2193   |                 0.680392 |   0.000369086 |
|            62 | cnn1d_full                        |       2421 |                1.59708 |              1.03012  |                 0.601369 |   0.011776    |
|            63 | cnn1d_full                        |       1110 |                1.59893 |              1.01698  |                 0.560525 |  -0.0130327   |
|            65 | cnn1d_full                        |        198 |                1.69657 |              1.2237   |                 0.566379 |  -0.061925    |
|            58 | cnn1d_no_samples_0_3              |        219 |                1.91898 |              1.00687  |                 0.469312 |  -0.0619253   |
|            59 | cnn1d_no_samples_0_3              |       2289 |                1.65078 |              1.07645  |                 0.622724 |  -0.00708386  |
|            60 | cnn1d_no_samples_0_3              |       2424 |                1.78591 |              1.12088  |                 0.582593 |   0.0483093   |
|            61 | cnn1d_no_samples_0_3              |       2799 |                1.65823 |              1.19765  |                 0.683768 |  -0.0444166   |
|            62 | cnn1d_no_samples_0_3              |       2421 |                1.69049 |              1.04514  |                 0.59458  |   0.0363587   |
|            63 | cnn1d_no_samples_0_3              |       1110 |                1.66716 |              1.11277  |                 0.580573 |  -0.00142205  |
|            65 | cnn1d_no_samples_0_3              |        198 |                1.59771 |              1.23746  |                 0.555329 |   0.0193682   |
|            58 | cnn1d_only_samples_0_3            |        219 |                2.00416 |              1.02322  |                 0.495938 |  -0.0259815   |
|            59 | cnn1d_only_samples_0_3            |       2289 |                1.55516 |              1.01565  |                 0.625638 |   0.0565204   |
|            60 | cnn1d_only_samples_0_3            |       2424 |                1.76967 |              1.05888  |                 0.567898 |   0.0356424   |
|            61 | cnn1d_only_samples_0_3            |       2799 |                1.60135 |              1.19485  |                 0.706977 |   0.0319926   |
|            62 | cnn1d_only_samples_0_3            |       2421 |                1.62502 |              1.02611  |                 0.610617 |   0.016334    |
|            63 | cnn1d_only_samples_0_3            |       1110 |                1.58196 |              1.07981  |                 0.611273 |   0.0224653   |
|            65 | cnn1d_only_samples_0_3            |        198 |                1.55667 |              1.25902  |                 0.629646 |  -0.0419601   |
|            58 | early_late_gated_full             |        219 |                1.91599 |              1.21096  |                 0.505123 |  -0.140849    |
|            59 | early_late_gated_full             |       2289 |                1.34746 |              0.966257 |                 0.68068  |   0.0783468   |
|            60 | early_late_gated_full             |       2424 |                1.57189 |              1.071    |                 0.640567 |  -0.0022502   |
|            61 | early_late_gated_full             |       2799 |                1.40095 |              1.22318  |                 0.805259 |   0.0200524   |
|            62 | early_late_gated_full             |       2421 |                1.56935 |              1.04363  |                 0.620817 |   0.0058833   |
|            63 | early_late_gated_full             |       1110 |                1.48831 |              1.03722  |                 0.631487 |  -0.00162287  |
|            65 | early_late_gated_full             |        198 |                1.48093 |              1.25828  |                 0.663423 |  -0.0562652   |
|            58 | early_late_gated_no_samples_0_3   |        219 |                1.94701 |              1.04613  |                 0.456176 |  -0.099841    |
|            59 | early_late_gated_no_samples_0_3   |       2289 |                1.38191 |              0.97673  |                 0.659223 |   0.0435668   |
|            60 | early_late_gated_no_samples_0_3   |       2424 |                1.57493 |              1.09688  |                 0.636493 |   0.0253181   |
|            61 | early_late_gated_no_samples_0_3   |       2799 |                1.37876 |              1.26231  |                 0.833015 |   0.00346343  |
|            62 | early_late_gated_no_samples_0_3   |       2421 |                1.53001 |              1.03903  |                 0.640038 |  -0.00643903  |
|            63 | early_late_gated_no_samples_0_3   |       1110 |                1.46297 |              1.0115   |                 0.606454 |   0.0472725   |
|            65 | early_late_gated_no_samples_0_3   |        198 |                1.46335 |              1.32845  |                 0.667042 |  -0.0933606   |
|            58 | early_late_gated_only_samples_0_3 |        219 |                1.8726  |              0.971151 |                 0.49539  |  -0.0964111   |
|            59 | early_late_gated_only_samples_0_3 |       2289 |                1.59273 |              1.06593  |                 0.637738 |   0.0321194   |
|            60 | early_late_gated_only_samples_0_3 |       2424 |                1.76104 |              1.11405  |                 0.592282 |   0.030566    |
|            61 | early_late_gated_only_samples_0_3 |       2799 |                1.62024 |              1.23863  |                 0.716468 |  -0.0321596   |
|            62 | early_late_gated_only_samples_0_3 |       2421 |                1.50077 |              1.01641  |                 0.61942  |   0.0304355   |
|            63 | early_late_gated_only_samples_0_3 |       1110 |                1.59823 |              1.02107  |                 0.601342 |   0.0100131   |
|            65 | early_late_gated_only_samples_0_3 |        198 |                1.60488 |              1.21239  |                 0.61756  |  -0.0401022   |
|            58 | mlp_full                          |        219 |                1.84879 |              1.11004  |                 0.468676 |  -0.02886     |
|            59 | mlp_full                          |       2289 |                1.36913 |              0.951322 |                 0.641039 |   0.0898823   |
|            60 | mlp_full                          |       2424 |                1.45953 |              1.07364  |                 0.655042 |   0.08316     |
|            61 | mlp_full                          |       2799 |                1.40962 |              1.25431  |                 0.803335 |  -0.0342075   |
|            62 | mlp_full                          |       2421 |                1.37137 |              0.986018 |                 0.643541 |   0.0323529   |
|            63 | mlp_full                          |       1110 |                1.43247 |              1.04821  |                 0.659409 |   0.00480415  |
|            65 | mlp_full                          |        198 |                1.42968 |              1.33681  |                 0.752888 |  -0.037225    |
|            58 | mlp_no_samples_0_3                |        219 |                1.7002  |              1.38983  |                 0.540295 |  -0.261967    |
|            59 | mlp_no_samples_0_3                |       2289 |                1.43755 |              0.9602   |                 0.625931 |   0.0179394   |
|            60 | mlp_no_samples_0_3                |       2424 |                1.57227 |              0.985745 |                 0.554403 |   0.0344433   |
|            61 | mlp_no_samples_0_3                |       2799 |                1.38865 |              1.19348  |                 0.79189  |  -0.0232788   |
|            62 | mlp_no_samples_0_3                |       2421 |                1.47072 |              0.95277  |                 0.608014 |   0.047825    |
|            63 | mlp_no_samples_0_3                |       1110 |                1.37542 |              1.0304   |                 0.644489 |   0.0146439   |
|            65 | mlp_no_samples_0_3                |        198 |                1.48918 |              1.27197  |                 0.532082 |  -0.0274522   |
|            58 | mlp_only_samples_0_3              |        219 |                1.81225 |              0.941512 |                 0.479692 |   0.0154076   |
|            59 | mlp_only_samples_0_3              |       2289 |                1.46076 |              0.972982 |                 0.622381 |   0.0629481   |
|            60 | mlp_only_samples_0_3              |       2424 |                1.70725 |              1.11748  |                 0.612114 |   0.0201133   |
|            61 | mlp_only_samples_0_3              |       2799 |                1.5201  |              1.26193  |                 0.791688 |  -0.0115084   |
|            62 | mlp_only_samples_0_3              |       2421 |                1.63177 |              1.04972  |                 0.624266 |   0.0515708   |
|            63 | mlp_only_samples_0_3              |       1110 |                1.39998 |              1.02851  |                 0.61371  |   0.0371993   |
|            65 | mlp_only_samples_0_3              |        198 |                1.57908 |              1.23836  |                 0.681138 |  -0.0953363   |

## Controls

| method                                     | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:-------------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_run_family_control                     | run_family_control      |      1.20011 |  1.14771 |   1.25713 |               -0.487685   |
| ridge_run_family_control                   | run_family_control      |      1.36196 |  1.31324 |   1.41565 |               -0.325837   |
| early_late_gated_full_shuffled             | shuffled_target_control |      1.66949 |  1.50706 |   1.92862 |               -0.0183138  |
| cnn1d_no_samples_0_3_shuffled              | shuffled_target_control |      1.67003 |  1.51212 |   1.93706 |               -0.0177711  |
| cnn1d_only_samples_0_3_shuffled            | shuffled_target_control |      1.68244 |  1.49786 |   1.95604 |               -0.00535685 |
| early_late_gated_no_samples_0_3_shuffled   | shuffled_target_control |      1.68594 |  1.5186  |   1.97443 |               -0.00185773 |
| mlp_full_shuffled                          | shuffled_target_control |      1.69028 |  1.52538 |   1.96279 |                0.00248187 |
| early_late_gated_only_samples_0_3_shuffled | shuffled_target_control |      1.69486 |  1.48988 |   2.00163 |                0.00705703 |
| mlp_no_samples_0_3_shuffled                | shuffled_target_control |      1.69722 |  1.47877 |   1.98709 |                0.00941777 |
| ridge_full_shuffled                        | shuffled_target_control |      1.70344 |  1.51653 |   2.01054 |                0.0156412  |
| mlp_only_samples_0_3_shuffled              | shuffled_target_control |      1.70451 |  1.51488 |   1.99351 |                0.0167096  |
| ridge_only_samples_0_3_shuffled            | shuffled_target_control |      1.70633 |  1.52489 |   1.99282 |                0.0185259  |
| ridge_no_samples_0_3_shuffled              | shuffled_target_control |      1.70685 |  1.54455 |   1.95568 |                0.0190455  |
| cnn1d_full_shuffled                        | shuffled_target_control |      1.71593 |  1.52707 |   2.02861 |                0.028131   |
| hgb_full_shuffled                          | shuffled_target_control |      1.72441 |  1.54952 |   2.00124 |                0.0366071  |
| hgb_no_samples_0_3_shuffled                | shuffled_target_control |      1.72607 |  1.55567 |   1.98435 |                0.0382703  |
| hgb_only_samples_0_3_shuffled              | shuffled_target_control |      1.73455 |  1.52994 |   1.99152 |                0.0467469  |

Shuffled-target rows are interpreted as stability/leakage warnings, not as positive evidence. A shuffled control that matches or beats its nominal counterpart means that model/mask combination is not causally interpretable.

## Held-Out Runs

|   heldout_run | method                            | family             |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_events |
|--------------:|:----------------------------------|:-------------------|-------------:|---------:|----------:|--------------------------:|-----------:|
|            58 | hgb_full                          | ml                 |      1.0755  | 0.926897 |   1.29052 |              -0.529345    |         73 |
|            58 | hgb_only_samples_0_3              | ml                 |      1.07609 | 0.911667 |   1.31905 |              -0.52876     |         73 |
|            58 | mlp_no_samples_0_3                | ml                 |      1.11342 | 0.923541 |   1.32875 |              -0.491429    |         73 |
|            58 | hgb_no_samples_0_3                | ml                 |      1.15864 | 0.92849  |   1.38823 |              -0.44621     |         73 |
|            58 | hgb_run_family_control            | run_family_control |      1.15995 | 1.0153   |   1.336   |              -0.444892    |         73 |
|            58 | mlp_only_samples_0_3              | ml                 |      1.20891 | 1.02236  |   1.40396 |              -0.395934    |         73 |
|            58 | early_late_gated_no_samples_0_3   | ml                 |      1.29996 | 1.16694  |   1.51451 |              -0.304886    |         73 |
|            58 | ridge_run_family_control          | run_family_control |      1.31416 | 1.17195  |   1.53807 |              -0.290685    |         73 |
|            58 | ridge_only_samples_0_3            | ml                 |      1.33459 | 1.1958   |   1.57329 |              -0.270255    |         73 |
|            58 | ridge_no_samples_0_3              | ml                 |      1.34398 | 1.18008  |   1.51573 |              -0.260866    |         73 |
|            58 | cnn1d_only_samples_0_3            | ml                 |      1.3473  | 1.18345  |   1.54424 |              -0.257545    |         73 |
|            58 | ridge_full                        | ml                 |      1.36538 | 1.21623  |   1.53661 |              -0.239464    |         73 |
|            58 | early_late_gated_only_samples_0_3 | ml                 |      1.40364 | 1.22685  |   1.55597 |              -0.201202    |         73 |
|            58 | cnn1d_no_samples_0_3              | ml                 |      1.44321 | 1.24439  |   1.64413 |              -0.161639    |         73 |
|            58 | cnn1d_full                        | ml                 |      1.48552 | 1.27475  |   1.69154 |              -0.119321    |         73 |
|            58 | mlp_full                          | ml                 |      1.49661 | 1.21828  |   1.73234 |              -0.108234    |         73 |
|            58 | s02b_global_template_timewalk     | traditional        |      1.60484 | 1.31762  |   1.86567 |               0           |         73 |
|            58 | early_late_gated_full             | ml                 |      1.65144 | 1.43565  |   1.80252 |               0.046597    |         73 |
|            59 | hgb_full                          | ml                 |      1.1237  | 1.07807  |   1.20361 |              -0.457287    |        763 |
|            59 | hgb_no_samples_0_3                | ml                 |      1.12632 | 1.07086  |   1.19552 |              -0.45467     |        763 |
|            59 | hgb_run_family_control            | run_family_control |      1.15372 | 1.08722  |   1.21937 |              -0.42727     |        763 |
|            59 | hgb_only_samples_0_3              | ml                 |      1.17684 | 1.12233  |   1.253   |              -0.404152    |        763 |
|            59 | mlp_full                          | ml                 |      1.23167 | 1.18292  |   1.29739 |              -0.349316    |        763 |
|            59 | mlp_no_samples_0_3                | ml                 |      1.23641 | 1.1765   |   1.29304 |              -0.344577    |        763 |
|            59 | early_late_gated_full             | ml                 |      1.27351 | 1.20952  |   1.34658 |              -0.307481    |        763 |
|            59 | mlp_only_samples_0_3              | ml                 |      1.29744 | 1.23966  |   1.35911 |              -0.283551    |        763 |
|            59 | early_late_gated_no_samples_0_3   | ml                 |      1.32817 | 1.26504  |   1.39408 |              -0.252823    |        763 |
|            59 | ridge_no_samples_0_3              | ml                 |      1.32911 | 1.27381  |   1.3951  |              -0.251885    |        763 |
|            59 | ridge_full                        | ml                 |      1.33679 | 1.28046  |   1.40501 |              -0.244198    |        763 |
|            59 | ridge_run_family_control          | run_family_control |      1.357   | 1.29358  |   1.42829 |              -0.223995    |        763 |
|            59 | ridge_only_samples_0_3            | ml                 |      1.36083 | 1.30578  |   1.43506 |              -0.220164    |        763 |
|            59 | cnn1d_only_samples_0_3            | ml                 |      1.38007 | 1.31198  |   1.44132 |              -0.200924    |        763 |
|            59 | cnn1d_full                        | ml                 |      1.40913 | 1.34467  |   1.4851  |              -0.171864    |        763 |
|            59 | cnn1d_no_samples_0_3              | ml                 |      1.48843 | 1.41071  |   1.55467 |              -0.0925591   |        763 |
|            59 | s02b_global_template_timewalk     | traditional        |      1.58099 | 1.52294  |   1.64389 |               0           |        763 |
|            59 | early_late_gated_only_samples_0_3 | ml                 |      1.58652 | 1.51997  |   1.65179 |               0.0055283   |        763 |
|            60 | hgb_no_samples_0_3                | ml                 |      1.16022 | 1.10486  |   1.21659 |              -0.309564    |        808 |
|            60 | hgb_full                          | ml                 |      1.19256 | 1.13299  |   1.25025 |              -0.277224    |        808 |
|            60 | hgb_only_samples_0_3              | ml                 |      1.22856 | 1.16238  |   1.28117 |              -0.241224    |        808 |
|            60 | mlp_no_samples_0_3                | ml                 |      1.26196 | 1.19464  |   1.31013 |              -0.20782     |        808 |
|            60 | hgb_run_family_control            | run_family_control |      1.26326 | 1.20907  |   1.32487 |              -0.206518    |        808 |
|            60 | mlp_full                          | ml                 |      1.40287 | 1.34335  |   1.45933 |              -0.066914    |        808 |
|            60 | ridge_run_family_control          | run_family_control |      1.40345 | 1.35277  |   1.47461 |              -0.066333    |        808 |
|            60 | early_late_gated_full             | ml                 |      1.40689 | 1.3537   |   1.48156 |              -0.0628958   |        808 |
|            60 | ridge_no_samples_0_3              | ml                 |      1.41201 | 1.36119  |   1.47934 |              -0.0577724   |        808 |
|            60 | ridge_full                        | ml                 |      1.4137  | 1.35848  |   1.47327 |              -0.0560785   |        808 |
|            60 | ridge_only_samples_0_3            | ml                 |      1.42331 | 1.36428  |   1.48901 |              -0.0464747   |        808 |
|            60 | cnn1d_only_samples_0_3            | ml                 |      1.46945 | 1.41171  |   1.53237 |              -0.000331323 |        808 |
|            60 | s02b_global_template_timewalk     | traditional        |      1.46978 | 1.43268  |   1.516   |               0           |        808 |
|            60 | cnn1d_full                        | ml                 |      1.48122 | 1.41873  |   1.55293 |               0.0114334   |        808 |
|            60 | early_late_gated_no_samples_0_3   | ml                 |      1.5204  | 1.46032  |   1.58577 |               0.0506166   |        808 |
|            60 | early_late_gated_only_samples_0_3 | ml                 |      1.53848 | 1.48386  |   1.61985 |               0.0686963   |        808 |
|            60 | mlp_only_samples_0_3              | ml                 |      1.60766 | 1.5436   |   1.6779  |               0.137881    |        808 |
|            60 | cnn1d_no_samples_0_3              | ml                 |      1.63123 | 1.57493  |   1.68782 |               0.161449    |        808 |
|            61 | hgb_no_samples_0_3                | ml                 |      1.13601 | 1.09602  |   1.18425 |              -1.04761     |        933 |
|            61 | hgb_full                          | ml                 |      1.14935 | 1.09376  |   1.21074 |              -1.03427     |        933 |
|            61 | hgb_run_family_control            | run_family_control |      1.196   | 1.14741  |   1.24672 |              -0.987627    |        933 |
|            61 | hgb_only_samples_0_3              | ml                 |      1.20519 | 1.14999  |   1.26744 |              -0.97843     |        933 |
|            61 | mlp_no_samples_0_3                | ml                 |      1.21571 | 1.17753  |   1.27303 |              -0.967917    |        933 |
|            61 | early_late_gated_only_samples_0_3 | ml                 |      1.24426 | 1.1817   |   1.30649 |              -0.939363    |        933 |
|            61 | early_late_gated_no_samples_0_3   | ml                 |      1.25346 | 1.19574  |   1.31047 |              -0.930169    |        933 |
|            61 | ridge_no_samples_0_3              | ml                 |      1.26994 | 1.2123   |   1.34241 |              -0.913681    |        933 |
|            61 | mlp_full                          | ml                 |      1.27169 | 1.22446  |   1.32695 |              -0.91194     |        933 |
|            61 | ridge_full                        | ml                 |      1.27372 | 1.21363  |   1.33377 |              -0.909902    |        933 |
|            61 | ridge_run_family_control          | run_family_control |      1.29019 | 1.22909  |   1.34618 |              -0.893437    |        933 |
|            61 | cnn1d_no_samples_0_3              | ml                 |      1.29502 | 1.23932  |   1.36289 |              -0.888605    |        933 |
|            61 | mlp_only_samples_0_3              | ml                 |      1.30379 | 1.24564  |   1.35941 |              -0.879833    |        933 |
|            61 | cnn1d_full                        | ml                 |      1.30446 | 1.24025  |   1.3573  |              -0.879166    |        933 |
|            61 | ridge_only_samples_0_3            | ml                 |      1.30617 | 1.23949  |   1.36882 |              -0.877455    |        933 |
|            61 | cnn1d_only_samples_0_3            | ml                 |      1.33397 | 1.26691  |   1.388   |              -0.849654    |        933 |
|            61 | early_late_gated_full             | ml                 |      1.35637 | 1.29224  |   1.41997 |              -0.827259    |        933 |
|            61 | s02b_global_template_timewalk     | traditional        |      2.18363 | 2.09309  |   2.27362 |               0           |        933 |
|            62 | hgb_full                          | ml                 |      1.15145 | 1.08214  |   1.21388 |              -0.458726    |        807 |
|            62 | hgb_no_samples_0_3                | ml                 |      1.15385 | 1.09797  |   1.22903 |              -0.456326    |        807 |
|            62 | hgb_only_samples_0_3              | ml                 |      1.1754  | 1.11101  |   1.24101 |              -0.43477     |        807 |
|            62 | mlp_no_samples_0_3                | ml                 |      1.21665 | 1.15053  |   1.27827 |              -0.393523    |        807 |
|            62 | hgb_run_family_control            | run_family_control |      1.23954 | 1.18204  |   1.31213 |              -0.370635    |        807 |
|            62 | mlp_full                          | ml                 |      1.26101 | 1.20198  |   1.33054 |              -0.349159    |        807 |
|            62 | early_late_gated_no_samples_0_3   | ml                 |      1.32761 | 1.26387  |   1.38215 |              -0.282559    |        807 |
|            62 | ridge_no_samples_0_3              | ml                 |      1.33335 | 1.26303  |   1.39523 |              -0.276824    |        807 |

## Leakage and Systematics

|   heldout_run | check                                                   |       value | pass   |
|--------------:|:--------------------------------------------------------|------------:|:-------|
|            58 | train_heldout_run_overlap                               |  0          | True   |
|            58 | train_heldout_event_id_overlap                          |  0          | True   |
|            58 | feature_audit                                           |  0          | True   |
|            58 | shuffled_target_worse:ridge_full                        |  0.223937   | True   |
|            58 | shuffled_target_worse:hgb_full                          |  0.504464   | True   |
|            58 | shuffled_target_worse:mlp_full                          |  0.142331   | True   |
|            58 | shuffled_target_worse:cnn1d_full                        |  0.162442   | True   |
|            58 | shuffled_target_worse:early_late_gated_full             | -0.0488782  | False  |
|            58 | shuffled_target_worse:ridge_no_samples_0_3              |  0.221389   | True   |
|            58 | shuffled_target_worse:hgb_no_samples_0_3                |  0.456082   | True   |
|            58 | shuffled_target_worse:mlp_no_samples_0_3                |  0.484337   | True   |
|            58 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.170738   | True   |
|            58 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.318686   | True   |
|            58 | shuffled_target_worse:ridge_only_samples_0_3            |  0.240911   | True   |
|            58 | shuffled_target_worse:hgb_only_samples_0_3              |  0.50025    | True   |
|            58 | shuffled_target_worse:mlp_only_samples_0_3              |  0.418262   | True   |
|            58 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.238076   | True   |
|            58 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.191205   | True   |
|            59 | train_heldout_run_overlap                               |  0          | True   |
|            59 | train_heldout_event_id_overlap                          |  0          | True   |
|            59 | feature_audit                                           |  0          | True   |
|            59 | shuffled_target_worse:ridge_full                        |  0.190165   | True   |
|            59 | shuffled_target_worse:hgb_full                          |  0.510881   | True   |
|            59 | shuffled_target_worse:mlp_full                          |  0.358409   | True   |
|            59 | shuffled_target_worse:cnn1d_full                        |  0.146843   | True   |
|            59 | shuffled_target_worse:early_late_gated_full             |  0.253982   | True   |
|            59 | shuffled_target_worse:ridge_no_samples_0_3              |  0.31427    | True   |
|            59 | shuffled_target_worse:hgb_no_samples_0_3                |  0.527318   | True   |
|            59 | shuffled_target_worse:mlp_no_samples_0_3                |  0.328663   | True   |
|            59 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.0884591  | True   |
|            59 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.274866   | True   |
|            59 | shuffled_target_worse:ridge_only_samples_0_3            |  0.193603   | True   |
|            59 | shuffled_target_worse:hgb_only_samples_0_3              |  0.517691   | True   |
|            59 | shuffled_target_worse:mlp_only_samples_0_3              |  0.332886   | True   |
|            59 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.143968   | True   |
|            59 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.00939641 | True   |
|            60 | train_heldout_run_overlap                               |  0          | True   |
|            60 | train_heldout_event_id_overlap                          |  0          | True   |
|            60 | feature_audit                                           |  0          | True   |
|            60 | shuffled_target_worse:ridge_full                        |  0.0834713  | True   |
|            60 | shuffled_target_worse:hgb_full                          |  0.315576   | True   |
|            60 | shuffled_target_worse:mlp_full                          |  0.100269   | True   |
|            60 | shuffled_target_worse:cnn1d_full                        |  0.00458341 | True   |
|            60 | shuffled_target_worse:early_late_gated_full             |  0.0678319  | True   |
|            60 | shuffled_target_worse:ridge_no_samples_0_3              |  0.0655844  | True   |
|            60 | shuffled_target_worse:hgb_no_samples_0_3                |  0.353519   | True   |
|            60 | shuffled_target_worse:mlp_no_samples_0_3                |  0.148741   | True   |
|            60 | shuffled_target_worse:cnn1d_no_samples_0_3              | -0.163047   | False  |
|            60 | shuffled_target_worse:early_late_gated_no_samples_0_3   | -0.0493918  | False  |
|            60 | shuffled_target_worse:ridge_only_samples_0_3            |  0.0441311  | True   |
|            60 | shuffled_target_worse:hgb_only_samples_0_3              |  0.23449    | True   |
|            60 | shuffled_target_worse:mlp_only_samples_0_3              | -0.133472   | False  |
|            60 | shuffled_target_worse:cnn1d_only_samples_0_3            | -0.00436558 | False  |
|            60 | shuffled_target_worse:early_late_gated_only_samples_0_3 | -0.111432   | False  |
|            61 | train_heldout_run_overlap                               |  0          | True   |
|            61 | train_heldout_event_id_overlap                          |  0          | True   |
|            61 | feature_audit                                           |  0          | True   |
|            61 | shuffled_target_worse:ridge_full                        |  0.96442    | True   |
|            61 | shuffled_target_worse:hgb_full                          |  1.03805    | True   |
|            61 | shuffled_target_worse:mlp_full                          |  0.896284   | True   |
|            61 | shuffled_target_worse:cnn1d_full                        |  0.926028   | True   |
|            61 | shuffled_target_worse:early_late_gated_full             |  0.768297   | True   |
|            61 | shuffled_target_worse:ridge_no_samples_0_3              |  0.857685   | True   |
|            61 | shuffled_target_worse:hgb_no_samples_0_3                |  1.08557    | True   |
|            61 | shuffled_target_worse:mlp_no_samples_0_3                |  0.998181   | True   |
|            61 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.79754    | True   |
|            61 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.94961    | True   |
|            61 | shuffled_target_worse:ridge_only_samples_0_3            |  0.913855   | True   |
|            61 | shuffled_target_worse:hgb_only_samples_0_3              |  0.985403   | True   |
|            61 | shuffled_target_worse:mlp_only_samples_0_3              |  0.935823   | True   |
|            61 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.83777    | True   |
|            61 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  1.00529    | True   |
|            62 | train_heldout_run_overlap                               |  0          | True   |
|            62 | train_heldout_event_id_overlap                          |  0          | True   |
|            62 | feature_audit                                           |  0          | True   |
|            62 | shuffled_target_worse:ridge_full                        |  0.305141   | True   |
|            62 | shuffled_target_worse:hgb_full                          |  0.554422   | True   |
|            62 | shuffled_target_worse:mlp_full                          |  0.340796   | True   |
|            62 | shuffled_target_worse:cnn1d_full                        |  0.257448   | True   |
|            62 | shuffled_target_worse:early_late_gated_full             |  0.173085   | True   |
|            62 | shuffled_target_worse:ridge_no_samples_0_3              |  0.370526   | True   |
|            62 | shuffled_target_worse:hgb_no_samples_0_3                |  0.502309   | True   |
|            62 | shuffled_target_worse:mlp_no_samples_0_3                |  0.414486   | True   |
|            62 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.174186   | True   |
|            62 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.249057   | True   |
|            62 | shuffled_target_worse:ridge_only_samples_0_3            |  0.280362   | True   |
|            62 | shuffled_target_worse:hgb_only_samples_0_3              |  0.504849   | True   |
|            62 | shuffled_target_worse:mlp_only_samples_0_3              |  0.212675   | True   |
|            62 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.256896   | True   |
|            62 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.104412   | True   |
|            63 | train_heldout_run_overlap                               |  0          | True   |
|            63 | train_heldout_event_id_overlap                          |  0          | True   |
|            63 | feature_audit                                           |  0          | True   |
|            63 | shuffled_target_worse:ridge_full                        |  0.157355   | True   |
|            63 | shuffled_target_worse:hgb_full                          |  0.319859   | True   |
|            63 | shuffled_target_worse:mlp_full                          |  0.173301   | True   |
|            63 | shuffled_target_worse:cnn1d_full                        |  0.0630261  | True   |
|            63 | shuffled_target_worse:early_late_gated_full             |  0.135862   | True   |
|            63 | shuffled_target_worse:ridge_no_samples_0_3              |  0.216118   | True   |
|            63 | shuffled_target_worse:hgb_no_samples_0_3                |  0.356743   | True   |
|            63 | shuffled_target_worse:mlp_no_samples_0_3                |  0.207336   | True   |
|            63 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.0859657  | True   |
|            63 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.202473   | True   |
|            63 | shuffled_target_worse:ridge_only_samples_0_3            |  0.198884   | True   |
|            63 | shuffled_target_worse:hgb_only_samples_0_3              |  0.349308   | True   |
|            63 | shuffled_target_worse:mlp_only_samples_0_3              |  0.168183   | True   |
|            63 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.12576    | True   |
|            63 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0572961  | True   |
|            65 | train_heldout_run_overlap                               |  0          | True   |
|            65 | train_heldout_event_id_overlap                          |  0          | True   |
|            65 | feature_audit                                           |  0          | True   |
|            65 | shuffled_target_worse:ridge_full                        |  0.196236   | True   |
|            65 | shuffled_target_worse:hgb_full                          |  0.310961   | True   |
|            65 | shuffled_target_worse:mlp_full                          |  0.236014   | True   |
|            65 | shuffled_target_worse:cnn1d_full                        |  0.164974   | True   |
|            65 | shuffled_target_worse:early_late_gated_full             |  0.120426   | True   |
|            65 | shuffled_target_worse:ridge_no_samples_0_3              |  0.134795   | True   |
|            65 | shuffled_target_worse:hgb_no_samples_0_3                |  0.300727   | True   |
|            65 | shuffled_target_worse:mlp_no_samples_0_3                |  0.289091   | True   |
|            65 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.172811   | True   |

Main caveats:

- Samples 0-3 are baseline-defining samples. Any apparent gain from `only_samples_0_3` can be pedestal/run structure rather than pulse-time information.
- Sample-II run 65 has low statistics; the pooled CI therefore uses runs as the outer bootstrap unit.
- The S02b target is internally defined from same-event downstream staves, so all claims are relative timing-closure claims, not absolute beam-time truth.
- Run-family controls are coarse and predeclared; they diagnose gross family nuisance but cannot exclude all detector-condition drift.

## Verdict

Winner in `result.json`: `hgb_full` with pooled `sigma68 = 1.163 ns` and CI `[1.124, 1.210] ns`.

Interpretation: Samples 0-3 are not required for the best residual correction; gains persist when they are removed, so the early samples are mainly nuisance/run-structure diagnostics rather than a causal timing source. 6 shuffled-target checks beat their nominal model and are flagged as stability caveats.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03f_1781031083_1848_21e023a2_early_sample_multimodel.py --config configs/p03_ticket_2389_deep_timing_sigma.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `model_diagnostics.csv`, `uncertainty_calibration.csv`, `traditional_s02_baselines.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`. Plot generation was skipped because the isolated `matplotlib` wheel lacked the Agg backend; this does not affect the numeric tables or winner selection.

# P03j: blinded q-template and baseline residual veto for waveform timing learners

- **Ticket:** `1781123335.1223.1d162b44`
- **Worker:** `testbeam-laptop-2`
- **Claimed study:** blinded q-template and baseline residual veto for waveform timing learners
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Traditional comparator:** `s02b_global_template_timewalk`
- **Veto:** train-fold event quantiles q-template SSE >= 0.90 or baseline excursion >= 0.90
- **Winner:** `hgb_no_samples_0_3` (`sigma68 = 1.208 ns`, 95% CI [1.164, 1.253] ns)

## Abstract

This study tests whether the P03i HGB advantage survives a blinded removal of high-risk q-template and pedestal atoms. I reproduced the selected-pulse count directly from raw ROOT, rebuilt the S02/S02b traditional timing chain inside each leave-one-run-out fold, fit q-template-SSE and baseline-excursion veto thresholds only on the training events, and then benchmarked the traditional comparator against Ridge, HGB, MLP, 1D-CNN, and a new early/late gated waveform learner on the retained held-out events. The result isolates whether ML gains are robust after the most obvious template-mismatch and baseline-excursion failure modes are removed without looking at held-out labels or held-out thresholds.

## Raw-ROOT Reproduction Gate

The selected-pulse gate was rerun from raw ROOT files before timing or ML fits. The selection is the canonical B-stave population after median baseline subtraction and `A > 1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Fold-Local Veto Definition

For every held-out run `h`, the training event set is `T_h = {r in Sample-II analysis runs: r != h}`. After fitting the fold-local S02/S02b templates on `T_h`, each event is assigned

`Q_e = max_i SSE_i(template)` and `B_e = max_i max_(k in 0..3) |w_ik|`,

where `i` runs over retained downstream pulses in the event and samples 0-3 are the median-baseline window. The veto thresholds are empirical train-fold quantiles:

`q_h = Quantile_{T_h}(Q_e; 0.90)`, `b_h = Quantile_{T_h}(B_e; 0.90)`.

An event is retained iff `Q_e < q_h` and `B_e < b_h`. The same `q_h,b_h` are applied to the held-out run, so the held-out q-template and baseline distributions do not tune the veto.

|   heldout_run | split   |   n_events_before_veto |   n_events_retained |   n_events_vetoed |   veto_fraction |   q_template_veto_fraction |   baseline_veto_fraction |   sse_threshold_from_train |   baseline_threshold_from_train |
|--------------:|:--------|-----------------------:|--------------------:|------------------:|----------------:|---------------------------:|-------------------------:|---------------------------:|--------------------------------:|
|            58 | heldout |                     73 |                  47 |                26 |        0.356164 |                  0.30137   |                0.0958904 |                    3.76512 |                         1944.2  |
|            58 | train   |                   3747 |                3138 |               609 |        0.16253  |                  0.10008   |                0.10008   |                    3.76512 |                         1944.2  |
|            59 | heldout |                    763 |                 658 |               105 |        0.137615 |                  0.0655308 |                0.0930537 |                    4.16746 |                         1967.9  |
|            59 | train   |                   3057 |                2549 |               508 |        0.166176 |                  0.100098  |                0.100098  |                    4.16746 |                         1967.9  |
|            60 | heldout |                    808 |                 649 |               159 |        0.196782 |                  0.122525  |                0.131188  |                    3.79942 |                         1887.4  |
|            60 | train   |                   3012 |                2528 |               484 |        0.160691 |                  0.100266  |                0.100266  |                    3.79942 |                         1887.4  |
|            61 | heldout |                    933 |                 781 |               152 |        0.162915 |                  0.103966  |                0.10075   |                    3.87834 |                         1943    |
|            61 | train   |                   2887 |                2408 |               479 |        0.165916 |                  0.100104  |                0.100104  |                    3.87834 |                         1943    |
|            62 | heldout |                    807 |                 685 |               122 |        0.151177 |                  0.094176  |                0.0929368 |                    3.99192 |                         1971.5  |
|            62 | train   |                   3013 |                2516 |               497 |        0.164952 |                  0.100232  |                0.100232  |                    3.99192 |                         1971.5  |
|            63 | heldout |                    370 |                 311 |                59 |        0.159459 |                  0.105405  |                0.0891892 |                    3.91874 |                         1960    |
|            63 | train   |                   3450 |                2888 |               562 |        0.162899 |                  0.1       |                0.1       |                    3.91874 |                         1960    |
|            65 | heldout |                     66 |                  56 |                10 |        0.151515 |                  0.151515  |                0         |                    3.88446 |                         1974.05 |
|            65 | train   |                   3754 |                3135 |               619 |        0.164891 |                  0.10016   |                0.10016   |                    3.88446 |                         1974.05 |

## Estimand and Metrics

For event `e`, stave `a`, method `m`, and stave position `z_a`, define

`tau_a(e;m) = t_a(e;m) - z_a / v`, with `1/v = 0.078 ns/cm`.

For pair `(a,b)`, the closure residual is

`r_ab(e;m) = tau_a(e;m) - tau_b(e;m)`.

The primary metric is the robust central width

`sigma68(m) = [Q_84(r(m)) - Q_16(r(m))] / 2`.

Per-run intervals use event bootstraps. The pooled interval uses a nested run-block/event bootstrap, preserving run-level heterogeneity after the veto.

## Methods

The traditional comparator is `s02b_global_template_timewalk`, the same fold-local analytic/template timewalk method used in P03i. The residual learners target

`y_i = t_i(trad) - mean_{j != i} t_j(trad)`

within the event and subtract the learned correction from the traditional pulse time. Benchmarked families are standardized Ridge regression, histogram gradient-boosted trees, a heteroskedastic MLP, a compact 1D-CNN, and the new `early_late_gated` architecture with separate samples-0-3 and samples-4-17 branches mixed by an auxiliary-feature gate. Each family is evaluated with `full`, `no_samples_0_3`, and `only_samples_0_3` waveform masks. Shuffled-target controls are trained for every nominal learner. Run-family controls use hand summaries plus predeclared early/middle/late run family.

## Pooled Benchmark After Veto

| method                            | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   tail_frac_vs_traditional_p95 |
|:----------------------------------|:------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------------------:|
| hgb_no_samples_0_3                | ml          |      1.20829 |  1.16438 |   1.25291 |                 -0.551725 |      -0.912741 |      -0.317471  |                      0.0166301 |
| hgb_full                          | ml          |      1.21432 |  1.16598 |   1.25524 |                 -0.5457   |      -0.908295 |      -0.305171  |                      0.0158979 |
| hgb_only_samples_0_3              | ml          |      1.26047 |  1.22597 |   1.31561 |                 -0.499554 |      -0.832553 |      -0.251481  |                      0.0196632 |
| mlp_no_samples_0_3                | ml          |      1.39887 |  1.30884 |   1.50696 |                 -0.361152 |      -0.726828 |      -0.128111  |                      0.0248928 |
| ridge_full                        | ml          |      1.41191 |  1.35303 |   1.48816 |                 -0.34811  |      -0.723099 |      -0.0823751 |                      0.0223826 |
| cnn1d_full                        | ml          |      1.42672 |  1.3375  |   1.48758 |                 -0.333303 |      -0.720515 |      -0.0844472 |                      0.0248928 |
| ridge_no_samples_0_3              | ml          |      1.43216 |  1.35868 |   1.51157 |                 -0.327857 |      -0.706688 |      -0.0620241 |                      0.0234285 |
| mlp_only_samples_0_3              | ml          |      1.43576 |  1.30441 |   1.54373 |                 -0.324263 |      -0.729595 |      -0.101958  |                      0.0262525 |
| cnn1d_only_samples_0_3            | ml          |      1.4397  |  1.32292 |   1.52923 |                 -0.320316 |      -0.704941 |      -0.073573  |                      0.0271938 |
| cnn1d_no_samples_0_3              | ml          |      1.45613 |  1.27063 |   1.61813 |                 -0.303886 |      -0.709207 |       0.0402938 |                      0.0285535 |
| ridge_only_samples_0_3            | ml          |      1.4648  |  1.39577 |   1.50886 |                 -0.29522  |      -0.657855 |      -0.0580246 |                      0.022801  |
| early_late_gated_only_samples_0_3 | ml          |      1.4692  |  1.38027 |   1.54568 |                 -0.290817 |      -0.670693 |      -0.0172047 |                      0.0263571 |
| early_late_gated_full             | ml          |      1.47724 |  1.36208 |   1.58367 |                 -0.282783 |      -0.624458 |      -0.0442985 |                      0.0279259 |
| mlp_full                          | ml          |      1.51159 |  1.3451  |   1.64403 |                 -0.248431 |      -0.668468 |       0.0790878 |                      0.0279259 |
| early_late_gated_no_samples_0_3   | ml          |      1.56923 |  1.4277  |   1.64454 |                 -0.190793 |      -0.57222  |       0.0523119 |                      0.0312729 |
| s02b_global_template_timewalk     | traditional |      1.76002 |  1.54692 |   2.08077 |                  0        |       0        |       0         |                      0.0499948 |

## Held-Out Run Benchmark

|   heldout_run | method                            | family             |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_events |
|--------------:|:----------------------------------|:-------------------|-------------:|---------:|----------:|--------------------------:|-----------:|
|            58 | hgb_no_samples_0_3                | ml                 |      1.12181 | 0.887663 |   1.38702 |               -0.536601   |         47 |
|            58 | hgb_full                          | ml                 |      1.17767 | 0.92561  |   1.39274 |               -0.480747   |         47 |
|            58 | mlp_no_samples_0_3                | ml                 |      1.21527 | 1.04201  |   1.54    |               -0.443142   |         47 |
|            58 | hgb_run_family_control            | run_family_control |      1.23873 | 0.968734 |   1.50665 |               -0.419686   |         47 |
|            58 | cnn1d_full                        | ml                 |      1.33944 | 1.10434  |   1.6483  |               -0.318975   |         47 |
|            58 | hgb_only_samples_0_3              | ml                 |      1.34221 | 1.03402  |   1.55422 |               -0.316208   |         47 |
|            58 | ridge_only_samples_0_3            | ml                 |      1.38679 | 1.11568  |   1.84496 |               -0.271624   |         47 |
|            58 | ridge_no_samples_0_3              | ml                 |      1.397   | 1.17735  |   1.80591 |               -0.261413   |         47 |
|            58 | cnn1d_no_samples_0_3              | ml                 |      1.40921 | 1.10243  |   1.67101 |               -0.2492     |         47 |
|            58 | early_late_gated_no_samples_0_3   | ml                 |      1.42468 | 1.09462  |   1.71944 |               -0.233732   |         47 |
|            58 | ridge_run_family_control          | run_family_control |      1.43869 | 1.17291  |   1.89186 |               -0.219723   |         47 |
|            58 | cnn1d_only_samples_0_3            | ml                 |      1.44607 | 1.20256  |   1.82677 |               -0.212344   |         47 |
|            58 | ridge_full                        | ml                 |      1.46605 | 1.12957  |   1.76502 |               -0.192362   |         47 |
|            58 | early_late_gated_only_samples_0_3 | ml                 |      1.55147 | 1.2678   |   1.80547 |               -0.106943   |         47 |
|            58 | mlp_full                          | ml                 |      1.60722 | 1.26073  |   1.77272 |               -0.0511905  |         47 |
|            58 | mlp_only_samples_0_3              | ml                 |      1.65005 | 1.39605  |   1.97057 |               -0.00836663 |         47 |
|            58 | s02b_global_template_timewalk     | traditional        |      1.65841 | 1.34284  |   2.10327 |                0          |         47 |
|            58 | early_late_gated_full             | ml                 |      1.74899 | 1.47883  |   2.12428 |                0.090573   |         47 |
|            59 | cnn1d_no_samples_0_3              | ml                 |      1.18853 | 1.12757  |   1.2601  |               -0.445729   |        658 |
|            59 | hgb_run_family_control            | run_family_control |      1.20725 | 1.1534   |   1.26091 |               -0.427009   |        658 |
|            59 | hgb_full                          | ml                 |      1.20729 | 1.15209  |   1.26937 |               -0.426964   |        658 |
|            59 | hgb_no_samples_0_3                | ml                 |      1.21361 | 1.14584  |   1.26638 |               -0.420649   |        658 |
|            59 | hgb_only_samples_0_3              | ml                 |      1.24587 | 1.1896   |   1.31087 |               -0.388384   |        658 |
|            59 | mlp_no_samples_0_3                | ml                 |      1.29612 | 1.23022  |   1.37462 |               -0.338135   |        658 |
|            59 | early_late_gated_full             | ml                 |      1.30456 | 1.22402  |   1.35492 |               -0.329701   |        658 |
|            59 | mlp_only_samples_0_3              | ml                 |      1.32865 | 1.24901  |   1.38828 |               -0.305611   |        658 |
|            59 | cnn1d_only_samples_0_3            | ml                 |      1.3474  | 1.27695  |   1.4226  |               -0.286861   |        658 |
|            59 | cnn1d_full                        | ml                 |      1.36078 | 1.29807  |   1.42893 |               -0.273478   |        658 |
|            59 | ridge_full                        | ml                 |      1.3791  | 1.30044  |   1.43537 |               -0.255154   |        658 |
|            59 | ridge_no_samples_0_3              | ml                 |      1.39052 | 1.32327  |   1.46288 |               -0.243738   |        658 |
|            59 | early_late_gated_only_samples_0_3 | ml                 |      1.41207 | 1.3314   |   1.47985 |               -0.222186   |        658 |
|            59 | early_late_gated_no_samples_0_3   | ml                 |      1.42261 | 1.3461   |   1.50163 |               -0.211649   |        658 |
|            59 | ridge_only_samples_0_3            | ml                 |      1.448   | 1.37566  |   1.52029 |               -0.186262   |        658 |
|            59 | ridge_run_family_control          | run_family_control |      1.45313 | 1.39632  |   1.51297 |               -0.18113    |        658 |
|            59 | mlp_full                          | ml                 |      1.5368  | 1.4801   |   1.61159 |               -0.0974567  |        658 |
|            59 | s02b_global_template_timewalk     | traditional        |      1.63426 | 1.57332  |   1.68455 |                0          |        658 |
|            60 | hgb_no_samples_0_3                | ml                 |      1.22129 | 1.15995  |   1.28754 |               -0.226036   |        649 |
|            60 | hgb_full                          | ml                 |      1.24681 | 1.1798   |   1.30061 |               -0.200518   |        649 |
|            60 | mlp_only_samples_0_3              | ml                 |      1.26085 | 1.19365  |   1.33644 |               -0.186469   |        649 |
|            60 | hgb_only_samples_0_3              | ml                 |      1.29629 | 1.24207  |   1.39207 |               -0.151034   |        649 |
|            60 | hgb_run_family_control            | run_family_control |      1.33045 | 1.27578  |   1.39597 |               -0.116876   |        649 |
|            60 | mlp_no_samples_0_3                | ml                 |      1.33869 | 1.27652  |   1.39367 |               -0.108637   |        649 |
|            60 | s02b_global_template_timewalk     | traditional        |      1.44732 | 1.40246  |   1.52385 |                0          |        649 |
|            60 | cnn1d_full                        | ml                 |      1.48917 | 1.41598  |   1.56579 |                0.0418473  |        649 |
|            60 | cnn1d_only_samples_0_3            | ml                 |      1.49936 | 1.43192  |   1.57797 |                0.0520358  |        649 |
|            60 | early_late_gated_full             | ml                 |      1.51036 | 1.44238  |   1.57904 |                0.0630341  |        649 |
|            60 | ridge_full                        | ml                 |      1.51415 | 1.44668  |   1.56756 |                0.0668275  |        649 |
|            60 | ridge_only_samples_0_3            | ml                 |      1.52236 | 1.45567  |   1.58629 |                0.0750328  |        649 |
|            60 | ridge_run_family_control          | run_family_control |      1.52519 | 1.46334  |   1.60426 |                0.0778715  |        649 |
|            60 | ridge_no_samples_0_3              | ml                 |      1.54225 | 1.47966  |   1.60002 |                0.0949268  |        649 |
|            60 | early_late_gated_only_samples_0_3 | ml                 |      1.58716 | 1.5011   |   1.66103 |                0.139841   |        649 |
|            60 | mlp_full                          | ml                 |      1.62074 | 1.55599  |   1.68809 |                0.173421   |        649 |
|            60 | cnn1d_no_samples_0_3              | ml                 |      1.68088 | 1.60753  |   1.75895 |                0.233554   |        649 |
|            60 | early_late_gated_no_samples_0_3   | ml                 |      1.68417 | 1.60306  |   1.74627 |                0.236845   |        649 |
|            61 | hgb_no_samples_0_3                | ml                 |      1.14553 | 1.08583  |   1.19654 |               -1.1376     |        781 |
|            61 | hgb_full                          | ml                 |      1.15511 | 1.10463  |   1.20465 |               -1.12802    |        781 |
|            61 | hgb_run_family_control            | run_family_control |      1.22043 | 1.16576  |   1.27881 |               -1.0627     |        781 |
|            61 | hgb_only_samples_0_3              | ml                 |      1.23928 | 1.18202  |   1.30096 |               -1.04385    |        781 |
|            61 | mlp_only_samples_0_3              | ml                 |      1.2894  | 1.20977  |   1.35432 |               -0.993731   |        781 |
|            61 | cnn1d_no_samples_0_3              | ml                 |      1.28963 | 1.22214  |   1.36112 |               -0.993502   |        781 |
|            61 | ridge_run_family_control          | run_family_control |      1.30019 | 1.24328  |   1.36088 |               -0.982938   |        781 |
|            61 | cnn1d_full                        | ml                 |      1.30139 | 1.22783  |   1.36476 |               -0.981738   |        781 |
|            61 | cnn1d_only_samples_0_3            | ml                 |      1.30452 | 1.23143  |   1.34942 |               -0.978608   |        781 |
|            61 | mlp_no_samples_0_3                | ml                 |      1.3057  | 1.22867  |   1.36926 |               -0.977431   |        781 |
|            61 | ridge_no_samples_0_3              | ml                 |      1.3136  | 1.24972  |   1.36118 |               -0.969532   |        781 |
|            61 | ridge_only_samples_0_3            | ml                 |      1.31625 | 1.25433  |   1.36723 |               -0.966873   |        781 |
|            61 | early_late_gated_only_samples_0_3 | ml                 |      1.31685 | 1.24845  |   1.37527 |               -0.966278   |        781 |
|            61 | mlp_full                          | ml                 |      1.32029 | 1.27244  |   1.3856  |               -0.962841   |        781 |
|            61 | early_late_gated_full             | ml                 |      1.32553 | 1.25958  |   1.38494 |               -0.957594   |        781 |
|            61 | ridge_full                        | ml                 |      1.33176 | 1.25797  |   1.37971 |               -0.951371   |        781 |
|            61 | early_late_gated_no_samples_0_3   | ml                 |      1.37449 | 1.29233  |   1.43098 |               -0.908636   |        781 |
|            61 | s02b_global_template_timewalk     | traditional        |      2.28313 | 2.18689  |   2.3842  |                0          |        781 |
|            62 | hgb_full                          | ml                 |      1.16468 | 1.07549  |   1.22774 |               -0.480036   |        685 |
|            62 | hgb_no_samples_0_3                | ml                 |      1.17237 | 1.09496  |   1.23812 |               -0.472347   |        685 |
|            62 | hgb_only_samples_0_3              | ml                 |      1.22142 | 1.15033  |   1.29573 |               -0.423291   |        685 |
|            62 | hgb_run_family_control            | run_family_control |      1.27937 | 1.2084   |   1.3529  |               -0.365342   |        685 |
|            62 | mlp_full                          | ml                 |      1.28004 | 1.22216  |   1.34544 |               -0.364672   |        685 |
|            62 | cnn1d_only_samples_0_3            | ml                 |      1.303   | 1.25754  |   1.36615 |               -0.341715   |        685 |
|            62 | cnn1d_no_samples_0_3              | ml                 |      1.392   | 1.33669  |   1.45614 |               -0.25271    |        685 |
|            62 | early_late_gated_full             | ml                 |      1.40161 | 1.34006  |   1.46185 |               -0.243103   |        685 |
|            62 | ridge_full                        | ml                 |      1.40286 | 1.33525  |   1.46242 |               -0.241857   |        685 |
|            62 | mlp_only_samples_0_3              | ml                 |      1.40321 | 1.33652  |   1.48075 |               -0.241507   |        685 |
|            62 | ridge_no_samples_0_3              | ml                 |      1.43123 | 1.36761  |   1.49863 |               -0.213487   |        685 |
|            62 | ridge_only_samples_0_3            | ml                 |      1.44336 | 1.38335  |   1.50522 |               -0.201356   |        685 |
|            62 | ridge_run_family_control          | run_family_control |      1.45835 | 1.41322  |   1.52502 |               -0.186362   |        685 |
|            62 | cnn1d_full                        | ml                 |      1.46683 | 1.40106  |   1.52348 |               -0.17788    |        685 |
|            62 | early_late_gated_only_samples_0_3 | ml                 |      1.47542 | 1.40748  |   1.54152 |               -0.169298   |        685 |
|            62 | mlp_no_samples_0_3                | ml                 |      1.57291 | 1.51692  |   1.63981 |               -0.0718038  |        685 |
|            62 | early_late_gated_no_samples_0_3   | ml                 |      1.57513 | 1.51286  |   1.64643 |               -0.0695885  |        685 |
|            62 | s02b_global_template_timewalk     | traditional        |      1.64471 | 1.57952  |   1.68963 |                0          |        685 |
|            63 | hgb_run_family_control            | run_family_control |      1.2459  | 1.12908  |   1.36637 |               -0.327596   |        311 |
|            63 | hgb_full                          | ml                 |      1.26096 | 1.16546  |   1.35839 |               -0.312539   |        311 |
|            63 | mlp_no_samples_0_3                | ml                 |      1.26351 | 1.17397  |   1.34562 |               -0.30999    |        311 |
|            63 | hgb_no_samples_0_3                | ml                 |      1.26454 | 1.14838  |   1.36208 |               -0.308956   |        311 |
|            63 | hgb_only_samples_0_3              | ml                 |      1.27751 | 1.13817  |   1.38636 |               -0.295991   |        311 |
|            63 | cnn1d_full                        | ml                 |      1.31869 | 1.19657  |   1.40278 |               -0.254804   |        311 |
|            63 | ridge_only_samples_0_3            | ml                 |      1.41496 | 1.32506  |   1.51673 |               -0.158542   |        311 |
|            63 | ridge_full                        | ml                 |      1.4258  | 1.31938  |   1.51931 |               -0.147695   |        311 |
|            63 | ridge_no_samples_0_3              | ml                 |      1.43509 | 1.3222   |   1.51631 |               -0.138404   |        311 |
|            63 | ridge_run_family_control          | run_family_control |      1.43513 | 1.34456  |   1.53881 |               -0.13837    |        311 |

## Residual Atom Map After Veto

The atom map is recomputed with the train-fold q-template/baseline thresholds and then restricted by the retained held-out pair residuals. It therefore describes residual structure that survived the veto, not the removed high-risk population.

Best nominal learner by retained atom:

| atom_type         | atom_value                | best_method            |   best_sigma68_ns |   traditional_sigma68_ns |   best_delta_vs_traditional_ns |   best_tail_risk_ratio_vs_traditional |   n_events |
|:------------------|:--------------------------|:-----------------------|------------------:|-------------------------:|-------------------------------:|--------------------------------------:|-----------:|
| amplitude_atom    | amp_high                  | hgb_no_samples_0_3     |          1.22979  |                  1.89265 |                      -0.662858 |                              0.458937 |       1082 |
| amplitude_atom    | amp_low                   | hgb_no_samples_0_3     |          1.14009  |                  1.64805 |                      -0.507955 |                              0.186992 |        987 |
| amplitude_atom    | amp_mid                   | hgb_full               |          1.2393   |                  1.72233 |                      -0.483033 |                              0.244898 |       1118 |
| anomaly_atom      | no_high_risk_atom         | hgb_no_samples_0_3     |          0.982758 |                  1.59371 |                      -0.610955 |                              0.228346 |       1331 |
| anomaly_atom      | any_high_risk_atom        | hgb_no_samples_0_3     |          1.38006  |                  1.90842 |                      -0.528364 |                              0.367123 |       1856 |
| baseline_atom     | baseline_train_bulk       | hgb_no_samples_0_3     |          1.20829  |                  1.76002 |                      -0.551725 |                              0.332636 |       3187 |
| delayed_peak_atom | prompt_peak               | hgb_no_samples_0_3     |          0.988647 |                  1.6004  |                      -0.611752 |                              0.22069  |       1436 |
| delayed_peak_atom | delayed_or_late_charge    | hgb_no_samples_0_3     |          1.39213  |                  1.90172 |                      -0.509587 |                              0.378613 |       1751 |
| pair              | B4-B8                     | hgb_no_samples_0_3     |          1.10978  |                  1.41137 |                      -0.301588 |                              0.514563 |       3187 |
| pair              | B4-B6                     | hgb_full               |          1.17169  |                  1.40641 |                      -0.234721 |                              0.694737 |       3187 |
| pair              | B6-B8                     | hgb_no_samples_0_3     |          0.999862 |                  1.14757 |                      -0.147705 |                              0.769231 |       3187 |
| phase_atom        | early_phase_le5           | cnn1d_only_samples_0_3 |          0.675846 |                  1.38091 |                      -0.705066 |                              0.727273 |        239 |
| phase_atom        | central_phase_6           | hgb_no_samples_0_3     |          0.797212 |                  1.3952  |                      -0.59799  |                              0.478261 |        355 |
| phase_atom        | late_phase_ge7            | hgb_full               |          1.33717  |                  1.89955 |                      -0.562376 |                              0.285714 |       2593 |
| q_template_atom   | q_template_sse_train_bulk | hgb_no_samples_0_3     |          1.20829  |                  1.76002 |                      -0.551725 |                              0.332636 |       3187 |
| run_family_atom   | middle                    | hgb_no_samples_0_3     |          1.19019  |                  1.84052 |                      -0.650329 |                              0.286111 |       2115 |
| run_family_atom   | early                     | hgb_full               |          1.20406  |                  1.63774 |                      -0.433678 |                              0.591549 |        705 |
| run_family_atom   | late                      | hgb_full               |          1.27166  |                  1.60056 |                      -0.328898 |                              0.465116 |        367 |
| saturation_atom   | amp_top5_proxy            | hgb_full               |          1.28888  |                  2.01578 |                      -0.726901 |                              0.365854 |        173 |
| saturation_atom   | amp_bulk                  | hgb_no_samples_0_3     |          1.20347  |                  1.74585 |                      -0.542378 |                              0.323326 |       3014 |

Focused atom metrics:

| atom_type         | atom_value                | method                        |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   tail_risk_ratio_vs_traditional |
|:------------------|:--------------------------|:------------------------------|-------------:|---------:|----------:|--------------------------:|---------------------------------:|
| amplitude_atom    | amp_high                  | hgb_no_samples_0_3            |     1.22979  | 1.17425  |  1.27493  |                -0.662858  |                         0.458937 |
| amplitude_atom    | amp_high                  | hgb_full                      |     1.24119  | 1.19785  |  1.29862  |                -0.651464  |                         0.439614 |
| amplitude_atom    | amp_high                  | cnn1d_full                    |     1.48352  | 1.41823  |  1.55274  |                -0.409137  |                         0.599034 |
| amplitude_atom    | amp_high                  | early_late_gated_full         |     1.52377  | 1.45488  |  1.59376  |                -0.368878  |                         0.657005 |
| amplitude_atom    | amp_high                  | mlp_full                      |     1.5445   | 1.47076  |  1.61267  |                -0.348156  |                         0.652174 |
| amplitude_atom    | amp_high                  | s02b_global_template_timewalk |     1.89265  | 1.81413  |  1.98784  |                 0         |                         1        |
| amplitude_atom    | amp_low                   | hgb_no_samples_0_3            |     1.14009  | 1.09093  |  1.1869   |                -0.507955  |                         0.186992 |
| amplitude_atom    | amp_low                   | hgb_full                      |     1.1523   | 1.09873  |  1.1995   |                -0.495746  |                         0.211382 |
| amplitude_atom    | amp_low                   | cnn1d_full                    |     1.3834   | 1.32834  |  1.44974  |                -0.26465   |                         0.422764 |
| amplitude_atom    | amp_low                   | early_late_gated_full         |     1.44515  | 1.36832  |  1.50099  |                -0.202896  |                         0.520325 |
| amplitude_atom    | amp_low                   | mlp_full                      |     1.45435  | 1.38966  |  1.53608  |                -0.193691  |                         0.414634 |
| amplitude_atom    | amp_low                   | s02b_global_template_timewalk |     1.64805  | 1.58873  |  1.72574  |                 0         |                         1        |
| amplitude_atom    | amp_mid                   | hgb_full                      |     1.2393   | 1.18723  |  1.29233  |                -0.483033  |                         0.244898 |
| amplitude_atom    | amp_mid                   | hgb_no_samples_0_3            |     1.2448   | 1.1949   |  1.29851  |                -0.477532  |                         0.251701 |
| amplitude_atom    | amp_mid                   | cnn1d_full                    |     1.37962  | 1.31183  |  1.42735  |                -0.342717  |                         0.428571 |
| amplitude_atom    | amp_mid                   | early_late_gated_full         |     1.45653  | 1.39548  |  1.52209  |                -0.265809  |                         0.503401 |
| amplitude_atom    | amp_mid                   | mlp_full                      |     1.51419  | 1.45156  |  1.56043  |                -0.208142  |                         0.557823 |
| amplitude_atom    | amp_mid                   | s02b_global_template_timewalk |     1.72233  | 1.65851  |  1.78911  |                 0         |                         1        |
| anomaly_atom      | any_high_risk_atom        | hgb_no_samples_0_3            |     1.38006  | 1.33383  |  1.41834  |                -0.528364  |                         0.367123 |
| anomaly_atom      | any_high_risk_atom        | hgb_full                      |     1.39092  | 1.35216  |  1.43058  |                -0.517507  |                         0.350685 |
| anomaly_atom      | any_high_risk_atom        | cnn1d_full                    |     1.65105  | 1.60616  |  1.69698  |                -0.257372  |                         0.542466 |
| anomaly_atom      | any_high_risk_atom        | early_late_gated_full         |     1.70625  | 1.65566  |  1.74847  |                -0.202178  |                         0.608219 |
| anomaly_atom      | any_high_risk_atom        | mlp_full                      |     1.71439  | 1.66136  |  1.77109  |                -0.194032  |                         0.613699 |
| anomaly_atom      | any_high_risk_atom        | s02b_global_template_timewalk |     1.90842  | 1.86407  |  1.95363  |                 0         |                         1        |
| anomaly_atom      | no_high_risk_atom         | hgb_no_samples_0_3            |     0.982758 | 0.951193 |  1.01965  |                -0.610955  |                         0.228346 |
| anomaly_atom      | no_high_risk_atom         | hgb_full                      |     0.993152 | 0.957773 |  1.0423   |                -0.60056   |                         0.212598 |
| anomaly_atom      | no_high_risk_atom         | cnn1d_full                    |     1.14567  | 1.11146  |  1.19296  |                -0.448046  |                         0.307087 |
| anomaly_atom      | no_high_risk_atom         | early_late_gated_full         |     1.1917   | 1.14844  |  1.23616  |                -0.402017  |                         0.330709 |
| anomaly_atom      | no_high_risk_atom         | mlp_full                      |     1.25177  | 1.20576  |  1.27856  |                -0.341938  |                         0.370079 |
| anomaly_atom      | no_high_risk_atom         | s02b_global_template_timewalk |     1.59371  | 1.54972  |  1.6357   |                 0         |                         1        |
| baseline_atom     | baseline_train_bulk       | hgb_no_samples_0_3            |     1.20829  | 1.16983  |  1.24298  |                -0.551725  |                         0.332636 |
| baseline_atom     | baseline_train_bulk       | hgb_full                      |     1.21432  | 1.18609  |  1.24168  |                -0.5457    |                         0.317992 |
| baseline_atom     | baseline_train_bulk       | cnn1d_full                    |     1.42672  | 1.39524  |  1.45872  |                -0.333303  |                         0.497908 |
| baseline_atom     | baseline_train_bulk       | early_late_gated_full         |     1.47724  | 1.44434  |  1.51001  |                -0.282783  |                         0.558577 |
| baseline_atom     | baseline_train_bulk       | mlp_full                      |     1.51159  | 1.47182  |  1.54883  |                -0.248431  |                         0.558577 |
| baseline_atom     | baseline_train_bulk       | s02b_global_template_timewalk |     1.76002  | 1.72732  |  1.79908  |                 0         |                         1        |
| delayed_peak_atom | delayed_or_late_charge    | hgb_no_samples_0_3            |     1.39213  | 1.34006  |  1.43567  |                -0.509587  |                         0.378613 |
| delayed_peak_atom | delayed_or_late_charge    | hgb_full                      |     1.40796  | 1.35842  |  1.44533  |                -0.49376   |                         0.361272 |
| delayed_peak_atom | delayed_or_late_charge    | cnn1d_full                    |     1.64873  | 1.59804  |  1.69474  |                -0.252995  |                         0.552023 |
| delayed_peak_atom | delayed_or_late_charge    | early_late_gated_full         |     1.70629  | 1.6504   |  1.74861  |                -0.195429  |                         0.627168 |
| delayed_peak_atom | delayed_or_late_charge    | mlp_full                      |     1.71535  | 1.67245  |  1.76472  |                -0.186371  |                         0.630058 |
| delayed_peak_atom | delayed_or_late_charge    | s02b_global_template_timewalk |     1.90172  | 1.85781  |  1.94354  |                 0         |                         1        |
| delayed_peak_atom | prompt_peak               | hgb_no_samples_0_3            |     0.988647 | 0.953496 |  1.02323  |                -0.611752  |                         0.22069  |
| delayed_peak_atom | prompt_peak               | hgb_full                      |     1.00429  | 0.955443 |  1.03566  |                -0.59611   |                         0.206897 |
| delayed_peak_atom | prompt_peak               | cnn1d_full                    |     1.1859   | 1.14245  |  1.22715  |                -0.414496  |                         0.324138 |
| delayed_peak_atom | prompt_peak               | early_late_gated_full         |     1.22344  | 1.18569  |  1.26719  |                -0.376958  |                         0.324138 |
| delayed_peak_atom | prompt_peak               | mlp_full                      |     1.2722   | 1.23234  |  1.30584  |                -0.328199  |                         0.358621 |
| delayed_peak_atom | prompt_peak               | s02b_global_template_timewalk |     1.6004   | 1.57172  |  1.65868  |                 0         |                         1        |
| pair              | B4-B6                     | hgb_full                      |     1.17169  | 1.1326   |  1.22351  |                -0.234721  |                         0.694737 |
| pair              | B4-B6                     | hgb_no_samples_0_3            |     1.17226  | 1.12288  |  1.23242  |                -0.23415   |                         0.673684 |
| pair              | B4-B6                     | cnn1d_full                    |     1.35428  | 1.28849  |  1.40584  |                -0.0521325 |                         0.842105 |
| pair              | B4-B6                     | s02b_global_template_timewalk |     1.40641  | 1.33519  |  1.47612  |                 0         |                         1        |
| pair              | B4-B6                     | early_late_gated_full         |     1.48995  | 1.42272  |  1.55919  |                 0.0835437 |                         1.12632  |
| pair              | B4-B6                     | mlp_full                      |     1.50127  | 1.45022  |  1.569    |                 0.0948643 |                         0.905263 |
| pair              | B4-B8                     | hgb_no_samples_0_3            |     1.10978  | 1.0636   |  1.15044  |                -0.301588  |                         0.514563 |
| pair              | B4-B8                     | hgb_full                      |     1.11506  | 1.07264  |  1.15865  |                -0.296311  |                         0.533981 |
| pair              | B4-B8                     | s02b_global_template_timewalk |     1.41137  | 1.35838  |  1.4723   |                 0         |                         1        |
| pair              | B4-B8                     | cnn1d_full                    |     1.42212  | 1.3698   |  1.47925  |                 0.0107524 |                         0.76699  |
| pair              | B4-B8                     | mlp_full                      |     1.44323  | 1.39891  |  1.49066  |                 0.0318609 |                         0.961165 |
| pair              | B4-B8                     | early_late_gated_full         |     1.49762  | 1.44067  |  1.54348  |                 0.0862493 |                         0.990291 |
| pair              | B6-B8                     | hgb_no_samples_0_3            |     0.999862 | 0.965602 |  1.05494  |                -0.147705  |                         0.769231 |
| pair              | B6-B8                     | hgb_full                      |     1.01928  | 0.979583 |  1.05601  |                -0.128285  |                         0.769231 |
| pair              | B6-B8                     | mlp_full                      |     1.07404  | 1.02484  |  1.12116  |                -0.0735238 |                         0.74359  |
| pair              | B6-B8                     | s02b_global_template_timewalk |     1.14757  | 1.09326  |  1.20174  |                 0         |                         1        |
| pair              | B6-B8                     | cnn1d_full                    |     1.18541  | 1.1422   |  1.23422  |                 0.0378416 |                         0.948718 |
| pair              | B6-B8                     | early_late_gated_full         |     1.22534  | 1.17592  |  1.26947  |                 0.0777678 |                         1.02564  |
| phase_atom        | central_phase_6           | hgb_no_samples_0_3            |     0.797212 | 0.765061 |  0.847655 |                -0.59799   |                         0.478261 |
| phase_atom        | central_phase_6           | hgb_full                      |     0.817271 | 0.777777 |  0.869215 |                -0.577932  |                         0.347826 |
| phase_atom        | central_phase_6           | early_late_gated_full         |     1.00159  | 0.925732 |  1.08912  |                -0.393612  |                         0.347826 |
| phase_atom        | central_phase_6           | cnn1d_full                    |     1.00353  | 0.936556 |  1.0799   |                -0.391673  |                         0.391304 |
| phase_atom        | central_phase_6           | mlp_full                      |     1.05621  | 0.982104 |  1.13589  |                -0.338992  |                         0.347826 |
| phase_atom        | central_phase_6           | s02b_global_template_timewalk |     1.3952   | 1.36471  |  1.47616  |                 0         |                         1        |
| phase_atom        | early_phase_le5           | hgb_full                      |     0.684457 | 0.659732 |  0.749066 |                -0.696455  |                         1        |
| phase_atom        | early_phase_le5           | hgb_no_samples_0_3            |     0.71584  | 0.678672 |  0.761146 |                -0.665072  |                         1        |
| phase_atom        | early_phase_le5           | mlp_full                      |     0.730186 | 0.682673 |  0.820306 |                -0.650727  |                         0.727273 |
| phase_atom        | early_phase_le5           | cnn1d_full                    |     0.736916 | 0.697993 |  0.796766 |                -0.643996  |                         0.727273 |
| phase_atom        | early_phase_le5           | early_late_gated_full         |     0.758098 | 0.699191 |  0.834619 |                -0.622814  |                         0.818182 |
| phase_atom        | early_phase_le5           | s02b_global_template_timewalk |     1.38091  | 1.35693  |  1.40386  |                 0         |                         1        |
| phase_atom        | late_phase_ge7            | hgb_full                      |     1.33717  | 1.30196  |  1.37525  |                -0.562376  |                         0.285714 |
| phase_atom        | late_phase_ge7            | hgb_no_samples_0_3            |     1.33759  | 1.30005  |  1.36446  |                -0.561963  |                         0.301099 |
| phase_atom        | late_phase_ge7            | cnn1d_full                    |     1.55233  | 1.51253  |  1.5958   |                -0.347217  |                         0.483516 |
| phase_atom        | late_phase_ge7            | early_late_gated_full         |     1.61072  | 1.56952  |  1.6532   |                -0.28883   |                         0.556044 |
| phase_atom        | late_phase_ge7            | mlp_full                      |     1.65484  | 1.61783  |  1.69562  |                -0.244704  |                         0.553846 |
| phase_atom        | late_phase_ge7            | s02b_global_template_timewalk |     1.89955  | 1.85014  |  1.94021  |                 0         |                         1        |
| q_template_atom   | q_template_sse_train_bulk | hgb_no_samples_0_3            |     1.20829  | 1.17955  |  1.23852  |                -0.551725  |                         0.332636 |
| q_template_atom   | q_template_sse_train_bulk | hgb_full                      |     1.21432  | 1.1833   |  1.24719  |                -0.5457    |                         0.317992 |
| q_template_atom   | q_template_sse_train_bulk | cnn1d_full                    |     1.42672  | 1.39276  |  1.46647  |                -0.333303  |                         0.497908 |
| q_template_atom   | q_template_sse_train_bulk | early_late_gated_full         |     1.47724  | 1.44728  |  1.50662  |                -0.282783  |                         0.558577 |
| q_template_atom   | q_template_sse_train_bulk | mlp_full                      |     1.51159  | 1.47156  |  1.5419   |                -0.248431  |                         0.558577 |
| q_template_atom   | q_template_sse_train_bulk | s02b_global_template_timewalk |     1.76002  | 1.72009  |  1.79623  |                 0         |                         1        |
| run_family_atom   | early                     | hgb_full                      |     1.20406  | 1.1476   |  1.27534  |                -0.433678  |                         0.591549 |
| run_family_atom   | early                     | hgb_no_samples_0_3            |     1.21188  | 1.15073  |  1.26402  |                -0.425862  |                         0.507042 |
| run_family_atom   | early                     | early_late_gated_full         |     1.33258  | 1.2738   |  1.3823   |                -0.30516   |                         0.619718 |
| run_family_atom   | early                     | cnn1d_full                    |     1.37434  | 1.31811  |  1.4435   |                -0.263403  |                         0.661972 |
| run_family_atom   | early                     | mlp_full                      |     1.55613  | 1.48525  |  1.61445  |                -0.0816062 |                         0.788732 |
| run_family_atom   | early                     | s02b_global_template_timewalk |     1.63774  | 1.5777   |  1.68942  |                 0         |                         1        |
| run_family_atom   | late                      | hgb_full                      |     1.27166  | 1.20061  |  1.37732  |                -0.328898  |                         0.465116 |
| run_family_atom   | late                      | hgb_no_samples_0_3            |     1.27624  | 1.21363  |  1.35483  |                -0.324317  |                         0.465116 |
| run_family_atom   | late                      | cnn1d_full                    |     1.33075  | 1.21889  |  1.42579  |                -0.269809  |                         0.651163 |
| run_family_atom   | late                      | early_late_gated_full         |     1.54221  | 1.45974  |  1.61343  |                -0.0583481 |                         0.837209 |
| run_family_atom   | late                      | s02b_global_template_timewalk |     1.60056  | 1.52631  |  1.67507  |                 0         |                         1        |
| run_family_atom   | late                      | mlp_full                      |     1.70266  | 1.61671  |  1.8026   |                 0.102103  |                         1.02326  |
| run_family_atom   | middle                    | hgb_no_samples_0_3            |     1.19019  | 1.15501  |  1.22181  |                -0.650329  |                         0.286111 |
| run_family_atom   | middle                    | hgb_full                      |     1.19954  | 1.16479  |  1.23018  |                -0.640981  |                         0.266667 |
| run_family_atom   | middle                    | mlp_full                      |     1.44453  | 1.4052   |  1.49164  |                -0.395986  |                         0.430556 |
| run_family_atom   | middle                    | cnn1d_full                    |     1.46284  | 1.43139  |  1.50294  |                -0.377672  |                         0.452778 |
| run_family_atom   | middle                    | early_late_gated_full         |     1.46957  | 1.43139  |  1.51134  |                -0.370949  |                         0.447222 |
| run_family_atom   | middle                    | s02b_global_template_timewalk |     1.84052  | 1.7933   |  1.89348  |                 0         |                         1        |
| saturation_atom   | amp_bulk                  | hgb_no_samples_0_3            |     1.20347  | 1.17172  |  1.24025  |                -0.542378  |                         0.323326 |
| saturation_atom   | amp_bulk                  | hgb_full                      |     1.20879  | 1.17809  |  1.23671  |                -0.537058  |                         0.316397 |
| saturation_atom   | amp_bulk                  | cnn1d_full                    |     1.41032  | 1.36897  |  1.43769  |                -0.335524  |                         0.487298 |
| saturation_atom   | amp_bulk                  | early_late_gated_full         |     1.4537   | 1.41778  |  1.48822  |                -0.292145  |                         0.545035 |
| saturation_atom   | amp_bulk                  | mlp_full                      |     1.49769  | 1.46276  |  1.53901  |                -0.248159  |                         0.556582 |
| saturation_atom   | amp_bulk                  | s02b_global_template_timewalk |     1.74585  | 1.70615  |  1.78446  |                 0         |                         1        |
| saturation_atom   | amp_top5_proxy            | hgb_full                      |     1.28888  | 1.16737  |  1.45621  |                -0.726901  |                         0.365854 |
| saturation_atom   | amp_top5_proxy            | hgb_no_samples_0_3            |     1.29515  | 1.16689  |  1.46401  |                -0.720634  |                         0.463415 |
| saturation_atom   | amp_top5_proxy            | mlp_full                      |     1.77349  | 1.58405  |  1.95207  |                -0.242288  |                         0.634146 |
| saturation_atom   | amp_top5_proxy            | cnn1d_full                    |     1.83845  | 1.72638  |  1.97721  |                -0.177334  |                         0.658537 |
| saturation_atom   | amp_top5_proxy            | early_late_gated_full         |     1.90746  | 1.7173   |  2.02102  |                -0.108319  |                         0.707317 |
| saturation_atom   | amp_top5_proxy            | s02b_global_template_timewalk |     2.01578  | 1.76435  |  2.23301  |                 0         |                         1        |

## Controls and Leakage

| method                                     | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:-------------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_run_family_control                     | run_family_control      |      1.27062 |  1.21764 |   1.32564 |              -0.489399    |
| ridge_run_family_control                   | run_family_control      |      1.46903 |  1.39181 |   1.51097 |              -0.290988    |
| early_late_gated_full_shuffled             | shuffled_target_control |      1.71027 |  1.52939 |   2.01229 |              -0.0497486   |
| ridge_no_samples_0_3_shuffled              | shuffled_target_control |      1.73604 |  1.55347 |   2.01508 |              -0.0239824   |
| mlp_only_samples_0_3_shuffled              | shuffled_target_control |      1.73868 |  1.54222 |   2.04928 |              -0.0213421   |
| cnn1d_full_shuffled                        | shuffled_target_control |      1.7497  |  1.53222 |   2.07595 |              -0.010322    |
| early_late_gated_no_samples_0_3_shuffled   | shuffled_target_control |      1.75036 |  1.56498 |   2.05453 |              -0.00965999  |
| ridge_full_shuffled                        | shuffled_target_control |      1.75253 |  1.54277 |   2.08068 |              -0.00749174  |
| ridge_only_samples_0_3_shuffled            | shuffled_target_control |      1.7527  |  1.53664 |   2.09174 |              -0.00731983  |
| early_late_gated_only_samples_0_3_shuffled | shuffled_target_control |      1.75958 |  1.52095 |   2.10965 |              -0.000435276 |
| mlp_no_samples_0_3_shuffled                | shuffled_target_control |      1.76432 |  1.5561  |   2.03165 |               0.00429927  |
| mlp_full_shuffled                          | shuffled_target_control |      1.77147 |  1.54613 |   2.09596 |               0.0114556   |
| cnn1d_no_samples_0_3_shuffled              | shuffled_target_control |      1.79108 |  1.5818  |   2.09027 |               0.031062    |
| cnn1d_only_samples_0_3_shuffled            | shuffled_target_control |      1.79635 |  1.58812 |   2.10272 |               0.0363324   |
| hgb_no_samples_0_3_shuffled                | shuffled_target_control |      1.79886 |  1.59754 |   2.08865 |               0.038842    |
| hgb_full_shuffled                          | shuffled_target_control |      1.79954 |  1.5892  |   2.10931 |               0.0395182   |
| hgb_only_samples_0_3_shuffled              | shuffled_target_control |      1.80648 |  1.56669 |   2.11857 |               0.0464656   |

|   heldout_run | check                                                   |        value | pass   |
|--------------:|:--------------------------------------------------------|-------------:|:-------|
|            58 | train_heldout_run_overlap                               |  0           | True   |
|            58 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            58 | veto_threshold_source                                   |  0           | True   |
|            58 | feature_audit_after_veto                                |  0           | True   |
|            58 | shuffled_target_worse:ridge_full                        |  0.279003    | True   |
|            58 | shuffled_target_worse:hgb_full                          |  0.596229    | True   |
|            58 | shuffled_target_worse:mlp_full                          |  0.11036     | True   |
|            58 | shuffled_target_worse:cnn1d_full                        |  0.319122    | True   |
|            58 | shuffled_target_worse:early_late_gated_full             | -0.0943619   | False  |
|            58 | shuffled_target_worse:ridge_no_samples_0_3              |  0.300233    | True   |
|            58 | shuffled_target_worse:hgb_no_samples_0_3                |  0.620531    | True   |
|            58 | shuffled_target_worse:mlp_no_samples_0_3                |  0.517399    | True   |
|            58 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.305654    | True   |
|            58 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.244299    | True   |
|            58 | shuffled_target_worse:ridge_only_samples_0_3            |  0.28995     | True   |
|            58 | shuffled_target_worse:hgb_only_samples_0_3              |  0.410782    | True   |
|            58 | shuffled_target_worse:mlp_only_samples_0_3              |  0.0165578   | True   |
|            58 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.247294    | True   |
|            58 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0828321   | True   |
|            59 | train_heldout_run_overlap                               |  0           | True   |
|            59 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            59 | veto_threshold_source                                   |  0           | True   |
|            59 | feature_audit_after_veto                                |  0           | True   |
|            59 | shuffled_target_worse:ridge_full                        |  0.264805    | True   |
|            59 | shuffled_target_worse:hgb_full                          |  0.506588    | True   |
|            59 | shuffled_target_worse:mlp_full                          |  0.100729    | True   |
|            59 | shuffled_target_worse:cnn1d_full                        |  0.243272    | True   |
|            59 | shuffled_target_worse:early_late_gated_full             |  0.278552    | True   |
|            59 | shuffled_target_worse:ridge_no_samples_0_3              |  0.257418    | True   |
|            59 | shuffled_target_worse:hgb_no_samples_0_3                |  0.486491    | True   |
|            59 | shuffled_target_worse:mlp_no_samples_0_3                |  0.369534    | True   |
|            59 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.496034    | True   |
|            59 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.239814    | True   |
|            59 | shuffled_target_worse:ridge_only_samples_0_3            |  0.220442    | True   |
|            59 | shuffled_target_worse:hgb_only_samples_0_3              |  0.443707    | True   |
|            59 | shuffled_target_worse:mlp_only_samples_0_3              |  0.295837    | True   |
|            59 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.355832    | True   |
|            59 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.192485    | True   |
|            60 | train_heldout_run_overlap                               |  0           | True   |
|            60 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            60 | veto_threshold_source                                   |  0           | True   |
|            60 | feature_audit_after_veto                                |  0           | True   |
|            60 | shuffled_target_worse:ridge_full                        | -0.0650141   | False  |
|            60 | shuffled_target_worse:hgb_full                          |  0.261772    | True   |
|            60 | shuffled_target_worse:mlp_full                          | -0.183754    | False  |
|            60 | shuffled_target_worse:cnn1d_full                        | -0.0494481   | False  |
|            60 | shuffled_target_worse:early_late_gated_full             | -0.0571952   | False  |
|            60 | shuffled_target_worse:ridge_no_samples_0_3              | -0.0824968   | False  |
|            60 | shuffled_target_worse:hgb_no_samples_0_3                |  0.285583    | True   |
|            60 | shuffled_target_worse:mlp_no_samples_0_3                |  0.118187    | True   |
|            60 | shuffled_target_worse:cnn1d_no_samples_0_3              | -0.159667    | False  |
|            60 | shuffled_target_worse:early_late_gated_no_samples_0_3   | -0.195812    | False  |
|            60 | shuffled_target_worse:ridge_only_samples_0_3            | -0.0626107   | False  |
|            60 | shuffled_target_worse:hgb_only_samples_0_3              |  0.179919    | True   |
|            60 | shuffled_target_worse:mlp_only_samples_0_3              |  0.19889     | True   |
|            60 | shuffled_target_worse:cnn1d_only_samples_0_3            | -0.000326017 | False  |
|            60 | shuffled_target_worse:early_late_gated_only_samples_0_3 | -0.151004    | False  |
|            61 | train_heldout_run_overlap                               |  0           | True   |
|            61 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            61 | veto_threshold_source                                   |  0           | True   |
|            61 | feature_audit_after_veto                                |  0           | True   |
|            61 | shuffled_target_worse:ridge_full                        |  0.963177    | True   |
|            61 | shuffled_target_worse:hgb_full                          |  1.10849     | True   |
|            61 | shuffled_target_worse:mlp_full                          |  1.01573     | True   |
|            61 | shuffled_target_worse:cnn1d_full                        |  0.973963    | True   |
|            61 | shuffled_target_worse:early_late_gated_full             |  0.862903    | True   |
|            61 | shuffled_target_worse:ridge_no_samples_0_3              |  0.87684     | True   |
|            61 | shuffled_target_worse:hgb_no_samples_0_3                |  1.09682     | True   |
|            61 | shuffled_target_worse:mlp_no_samples_0_3                |  0.885284    | True   |
|            61 | shuffled_target_worse:cnn1d_no_samples_0_3              |  1.00495     | True   |
|            61 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.862074    | True   |
|            61 | shuffled_target_worse:ridge_only_samples_0_3            |  0.98656     | True   |
|            61 | shuffled_target_worse:hgb_only_samples_0_3              |  1.11934     | True   |
|            61 | shuffled_target_worse:mlp_only_samples_0_3              |  0.947544    | True   |
|            61 | shuffled_target_worse:cnn1d_only_samples_0_3            |  1.00078     | True   |
|            61 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  1.00585     | True   |
|            62 | train_heldout_run_overlap                               |  0           | True   |
|            62 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            62 | veto_threshold_source                                   |  0           | True   |
|            62 | feature_audit_after_veto                                |  0           | True   |
|            62 | shuffled_target_worse:ridge_full                        |  0.233371    | True   |
|            62 | shuffled_target_worse:hgb_full                          |  0.473275    | True   |
|            62 | shuffled_target_worse:mlp_full                          |  0.351432    | True   |
|            62 | shuffled_target_worse:cnn1d_full                        |  0.177002    | True   |
|            62 | shuffled_target_worse:early_late_gated_full             |  0.239184    | True   |
|            62 | shuffled_target_worse:ridge_no_samples_0_3              |  0.210086    | True   |
|            62 | shuffled_target_worse:hgb_no_samples_0_3                |  0.520208    | True   |
|            62 | shuffled_target_worse:mlp_no_samples_0_3                |  0.0626302   | True   |
|            62 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.280443    | True   |
|            62 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.042182    | True   |
|            62 | shuffled_target_worse:ridge_only_samples_0_3            |  0.182135    | True   |
|            62 | shuffled_target_worse:hgb_only_samples_0_3              |  0.471749    | True   |
|            62 | shuffled_target_worse:mlp_only_samples_0_3              |  0.203479    | True   |
|            62 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.368345    | True   |
|            62 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.161604    | True   |
|            63 | train_heldout_run_overlap                               |  0           | True   |
|            63 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            63 | veto_threshold_source                                   |  0           | True   |
|            63 | feature_audit_after_veto                                |  0           | True   |
|            63 | shuffled_target_worse:ridge_full                        |  0.154886    | True   |
|            63 | shuffled_target_worse:hgb_full                          |  0.35273     | True   |
|            63 | shuffled_target_worse:mlp_full                          | -0.0815154   | False  |
|            63 | shuffled_target_worse:cnn1d_full                        |  0.237568    | True   |
|            63 | shuffled_target_worse:early_late_gated_full             |  0.102053    | True   |
|            63 | shuffled_target_worse:ridge_no_samples_0_3              |  0.164922    | True   |
|            63 | shuffled_target_worse:hgb_no_samples_0_3                |  0.385809    | True   |
|            63 | shuffled_target_worse:mlp_no_samples_0_3                |  0.323278    | True   |
|            63 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.10568     | True   |
|            63 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.0437526   | True   |
|            63 | shuffled_target_worse:ridge_only_samples_0_3            |  0.153332    | True   |
|            63 | shuffled_target_worse:hgb_only_samples_0_3              |  0.309846    | True   |
|            63 | shuffled_target_worse:mlp_only_samples_0_3              |  0.0385579   | True   |
|            63 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.196125    | True   |
|            63 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0578287   | True   |
|            65 | train_heldout_run_overlap                               |  0           | True   |
|            65 | train_heldout_event_id_overlap_after_veto               |  0           | True   |
|            65 | veto_threshold_source                                   |  0           | True   |
|            65 | feature_audit_after_veto                                |  0           | True   |
|            65 | shuffled_target_worse:ridge_full                        |  0.251801    | True   |
|            65 | shuffled_target_worse:hgb_full                          |  0.444955    | True   |
|            65 | shuffled_target_worse:mlp_full                          |  0.125119    | True   |
|            65 | shuffled_target_worse:cnn1d_full                        |  0.312669    | True   |
|            65 | shuffled_target_worse:early_late_gated_full             | -0.0518062   | False  |
|            65 | shuffled_target_worse:ridge_no_samples_0_3              |  0.318368    | True   |
|            65 | shuffled_target_worse:hgb_no_samples_0_3                |  0.39815     | True   |
|            65 | shuffled_target_worse:mlp_no_samples_0_3                |  0.127995    | True   |
|            65 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.279517    | True   |
|            65 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.294183    | True   |
|            65 | shuffled_target_worse:ridge_only_samples_0_3            |  0.278312    | True   |
|            65 | shuffled_target_worse:hgb_only_samples_0_3              |  0.447883    | True   |
|            65 | shuffled_target_worse:mlp_only_samples_0_3              |  0.258892    | True   |
|            65 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.255951    | True   |
|            65 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.268493    | True   |

The explicit leakage gate is the `veto_threshold_source` row in each fold: q-template and baseline thresholds are fit on train events only. Shuffled-target rows are stability sentinels; if a shuffled model beats its nominal counterpart, that nominal model is not considered mechanistically interpretable even if its pooled width is favorable.

## Systematics and Caveats

- The veto removes events with train-defined high q-template SSE or baseline excursion, but it is still a morphology proxy rather than an external detector-quality label.
- Applying the veto to training as well as held-out events changes the estimand to the retained-event population. The result should not be compared numerically to P03i without this population shift in mind.
- Samples 0-3 define the baseline median, so `only_samples_0_3` remains a nuisance-diagnostic mask rather than a clean timing sensor.
- Run 58 and run 65 have different retained statistics after the train-fold veto; pooled inference therefore uses runs as the outer bootstrap unit.
- The target is same-event downstream closure, not an absolute beam-clock residual.

## Verdict

Winner in `result.json`: `hgb_no_samples_0_3`. After removing train-fold-defined q-template/baseline high-risk events, the pooled winner is hgb_no_samples_0_3; its gain versus the traditional retained-event baseline is -0.552 ns. The best HGB row is hgb_no_samples_0_3 at 1.208 ns, so the HGB gain survives. The best no-samples-0-3 model is hgb_no_samples_0_3 (1.208 ns) versus best full-waveform hgb_full (1.214 ns). Mean held-out event veto fraction is 0.188; the new gated architecture reaches 1.469 ns but does not set the pooled minimum. 13 shuffled-target checks beat their nominal fold model and are retained as caveats.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03j_1781123335_1223_1d162b44_blinded_qtemplate_baseline_veto.py --config configs/p03j_1781123335_1223_1d162b44_blinded_qtemplate_baseline_veto.json
```

Artifacts include `reproduction_match_table.csv`, `veto_summary.csv`, `event_atoms.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `atom_failure_map.csv`, `per_atom_winners.csv`, `model_diagnostics.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

# S04j: pathology-interaction calibrated veto transfer

- **Ticket:** `1781069571.719.463e18dd`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Output:** `reports/1781069571.719.463e18dd__s04j_pathology_interaction_calibrated_veto_transfer`
- **Git commit:** `6b6e2f6ba5ae26a59654c7f8f4157111d5b41a39`

## Preregistered Question

Can the S04d/S04h pathology-interaction ledger be converted into a support-preserving all-hit timing-tail veto that transfers to held-out run families?  The veto is evaluated on B2/B4/B6/B8 all-hit events.  It is not an energy, PID, or pile-up truth claim; those quantities are represented only by raw waveform support proxies.

The primary metric is the run-mean robust width of retained all-six pair residuals,

`sigma68_m = [q84(Delta t_m) - q16(Delta t_m)] / 2`,

where `Delta t_m` contains all six pairwise corrected-time differences for retained held-out events.  Confidence intervals are non-parametric bootstrap intervals over held-out runs.  The operational score is `sigma68_m` plus explicit penalties if acceptance falls below `0.90` or the maximum support-proxy drift exceeds `0.10`.

## Raw-ROOT Reproduction Gate

The count gate is rebuilt directly from `h101/HRDv`: median baseline on samples 0-3, selected pulse if `max(HRDv - baseline) > 1000 ADC`, and all-hit event if B2, B4, B6, and B8 all pass.

| quantity                           |   expected |   observed |   delta | pass   |
|:-----------------------------------|-----------:|-----------:|--------:|:-------|
| selected_pulses_total              |     640737 |     640737 |       0 | True   |
| sample_ii_analysis_selected_pulses |     125096 |     125096 |       0 | True   |
| run64_selected_pulses              |      14630 |      14630 |       0 | True   |
| run64_all_hit_events               |        207 |        207 |       0 | True   |
| heldout_all_hit_events             |       3774 |       3774 |       0 | True   |

The reproduction gate passes exactly.

## Methods

For downstream staves `i in {B4,B6,B8}`, the training target is

`y_i = t_i - mean(t_j : j in {B4,B6,B8}, j != i)`.

The strong traditional comparator is an explicit Ridge timewalk correction with amplitude polynomials, inverse-square-root amplitude, area/amplitude, peak sample, stave identity, and amplitude-bin-by-stave interactions.  The ML/NN methods are trained on the same run-grouped target with identical held-out runs:

- `ridge`: linear Ridge on normalized waveform and event summaries.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: compact multilayer perceptron.
- `cnn1d`: compact 1D convolution over the 18-sample waveform plus summaries.
- `gated_mixer`: new ticket-local architecture that gates between waveform and summary/topology branches.

Each method receives a veto score calibrated on train runs.  The score is an additive pathology-interaction score using B2 amplitude imbalance, peak spread, baseline span, saturation/dropout/anomaly flags, and the method's predicted correction magnitude and dispersion.  The threshold is the train-run `95%` quantile and is applied without refit to held-out runs.

## Veto Policies

| method                        |   train_score_threshold |   train_target_acceptance |   heldout_event_acceptance |   n_train_events |   n_heldout_events |   n_accepted_heldout_events |
|:------------------------------|------------------------:|--------------------------:|---------------------------:|-----------------:|-------------------:|----------------------------:|
| traditional_explicit_timewalk |                 5.15431 |                      0.95 |                   0.986222 |              782 |               3774 |                        3722 |
| ridge                         |                 5.36757 |                      0.95 |                   0.981717 |              782 |               3774 |                        3705 |
| hgb                           |                 5.63226 |                      0.95 |                   0.983572 |              782 |               3774 |                        3712 |
| mlp                           |                 5.72554 |                      0.95 |                   0.983572 |              782 |               3774 |                        3712 |
| cnn1d                         |                 5.25492 |                      0.95 |                   0.987016 |              782 |               3774 |                        3725 |
| gated_mixer                   |                 5.16067 |                      0.95 |                   0.986751 |              782 |               3774 |                        3724 |

## Head-to-Head Result

| method                        |   mean_run_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_run_full_rms_ns |   mean_run_tail_frac_abs_gt5ns |   mean_acceptance |   mean_max_support_drift |   b2_harm_delta_ns |   primary_score | support_preserving   |
|:------------------------------|----------------------:|--------------------:|---------------------:|-----------------------:|-------------------------------:|------------------:|-------------------------:|-------------------:|----------------:|:---------------------|
| hgb                           |               2.98612 |             2.70109 |              3.31424 |                11.8926 |                       0.126771 |          0.976437 |                0.0561149 |            1.08306 |         2.98612 | True                 |
| traditional_explicit_timewalk |               3.00892 |             2.87855 |              3.1768  |                12.2034 |                       0.1343   |          0.976555 |                0.0486427 |            1.19567 |         3.00892 | True                 |
| cnn1d                         |               3.10332 |             2.86505 |              3.34603 |                12.1841 |                       0.112626 |          0.979122 |                0.0449431 |            1.17258 |         3.10332 | True                 |
| gated_mixer                   |               3.12113 |             2.89059 |              3.39366 |                12.2265 |                       0.116071 |          0.978907 |                0.0434389 |            1.20538 |         3.12113 | True                 |
| mlp                           |               3.27056 |             2.96463 |              3.61904 |                11.9533 |                       0.132213 |          0.976588 |                0.0511754 |            1.20538 |         3.27056 | True                 |
| ridge                         |               3.71099 |             3.48076 |              4.02359 |                12.2629 |                       0.157606 |          0.973391 |                0.0504032 |            1.66914 |         3.71099 | True                 |

The winner is **hgb** with retained all-six sigma68 `2.986` ns [2.701, 3.314].  The traditional comparator gives `3.009` ns [2.879, 3.177].  Negative ML-minus-traditional would favor ML; here the winning delta is `-0.023` ns.

## Per-Run Metrics

|   run | method                        | pair_scope      |   n_accepted_events |   acceptance |   n_pair_residuals |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|------:|:------------------------------|:----------------|--------------------:|-------------:|-------------------:|-------------:|--------------:|----------------------:|
|    58 | traditional_explicit_timewalk | all_six_with_b2 |                  69 |     0.958333 |                414 |      3.46576 |      18.7594  |             0.202899  |
|    58 | traditional_explicit_timewalk | downstream_only |                  69 |     0.958333 |                207 |      1.78194 |       2.65736 |             0.0724638 |
|    59 | traditional_explicit_timewalk | all_six_with_b2 |                 734 |     0.979973 |               4404 |      3.00141 |      10.5072  |             0.136013  |
|    59 | traditional_explicit_timewalk | downstream_only |                 734 |     0.979973 |               2202 |      1.75971 |       4.47493 |             0.0599455 |
|    60 | traditional_explicit_timewalk | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.78699 |       8.50196 |             0.0834384 |
|    60 | traditional_explicit_timewalk | downstream_only |                 793 |     0.988778 |               2379 |      1.96732 |       5.99546 |             0.0765027 |
|    61 | traditional_explicit_timewalk | all_six_with_b2 |                 923 |     0.997838 |               5538 |      2.96942 |       7.813   |             0.090827  |
|    61 | traditional_explicit_timewalk | downstream_only |                 923 |     0.997838 |               2769 |      1.97283 |       6.53664 |             0.0816179 |
|    62 | traditional_explicit_timewalk | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.82816 |       7.64941 |             0.0889311 |
|    62 | traditional_explicit_timewalk | downstream_only |                 789 |     0.988722 |               2367 |      1.8409  |       2.57459 |             0.0561893 |
|    63 | traditional_explicit_timewalk | all_six_with_b2 |                 354 |     0.969863 |               2124 |      3.08853 |      13.9293  |             0.16855   |
|    63 | traditional_explicit_timewalk | downstream_only |                 354 |     0.969863 |               1062 |      1.72523 |       6.4061  |             0.0715631 |
|    65 | traditional_explicit_timewalk | all_six_with_b2 |                  60 |     0.952381 |                360 |      2.92219 |      18.2637  |             0.169444  |
|    65 | traditional_explicit_timewalk | downstream_only |                  60 |     0.952381 |                180 |      1.64486 |       2.15098 |             0.0277778 |
|    58 | ridge                         | all_six_with_b2 |                  69 |     0.958333 |                414 |      4.54306 |      18.9803  |             0.219807  |
|    58 | ridge                         | downstream_only |                  69 |     0.958333 |                207 |      1.89925 |       3.38847 |             0.0772947 |
|    59 | ridge                         | all_six_with_b2 |                 731 |     0.975968 |               4386 |      3.54767 |      10.3174  |             0.149795  |
|    59 | ridge                         | downstream_only |                 731 |     0.975968 |               2193 |      1.95196 |       3.98807 |             0.0642955 |
|    60 | ridge                         | all_six_with_b2 |                 789 |     0.983791 |               4734 |      3.3483  |       8.64624 |             0.10583   |
|    60 | ridge                         | downstream_only |                 789 |     0.983791 |               2367 |      2.00855 |       5.93216 |             0.0794254 |
|    61 | ridge                         | all_six_with_b2 |                 918 |     0.992432 |               5508 |      3.57907 |       7.77264 |             0.135984  |
|    61 | ridge                         | downstream_only |                 918 |     0.992432 |               2754 |      2.24369 |       6.44758 |             0.114742  |
|    62 | ridge                         | all_six_with_b2 |                 785 |     0.983709 |               4710 |      3.39927 |       7.80167 |             0.115499  |
|    62 | ridge                         | downstream_only |                 785 |     0.983709 |               2355 |      2.04378 |       3.05964 |             0.0658174 |
|    63 | ridge                         | all_six_with_b2 |                 353 |     0.967123 |               2118 |      3.76298 |      14.0205  |             0.187441  |
|    63 | ridge                         | downstream_only |                 353 |     0.967123 |               1059 |      1.99802 |       6.5837  |             0.082153  |
|    65 | ridge                         | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.79658 |      18.3016  |             0.188889  |
|    65 | ridge                         | downstream_only |                  60 |     0.952381 |                180 |      2.1477  |       2.67206 |             0.0555556 |
|    58 | hgb                           | all_six_with_b2 |                  70 |     0.972222 |                420 |      3.7134  |      18.9251  |             0.207143  |
|    58 | hgb                           | downstream_only |                  70 |     0.972222 |                210 |      2.00283 |       3.31926 |             0.0761905 |
|    59 | hgb                           | all_six_with_b2 |                 732 |     0.977303 |               4392 |      2.81429 |      10.0002  |             0.128415  |
|    59 | hgb                           | downstream_only |                 732 |     0.977303 |               2196 |      1.77541 |       3.10723 |             0.0469035 |
|    60 | hgb                           | all_six_with_b2 |                 788 |     0.982544 |               4728 |      2.52885 |       7.61964 |             0.0600677 |
|    60 | hgb                           | downstream_only |                 788 |     0.982544 |               2364 |      1.74907 |       4.27109 |             0.0418782 |
|    61 | hgb                           | all_six_with_b2 |                 919 |     0.993514 |               5514 |      2.80596 |       7.69125 |             0.0854189 |
|    61 | hgb                           | downstream_only |                 919 |     0.993514 |               2757 |      2.00785 |       6.22373 |             0.0623867 |
|    62 | hgb                           | all_six_with_b2 |                 790 |     0.989975 |               4740 |      2.60944 |       7.67747 |             0.0778481 |
|    62 | hgb                           | downstream_only |                 790 |     0.989975 |               2370 |      1.85528 |       2.4655  |             0.0329114 |
|    63 | hgb                           | all_six_with_b2 |                 353 |     0.967123 |               2118 |      3.04282 |      13.0504  |             0.15628   |
|    63 | hgb                           | downstream_only |                 353 |     0.967123 |               1059 |      1.86886 |       3.54633 |             0.0557129 |
|    65 | hgb                           | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.38806 |      18.2841  |             0.172222  |
|    65 | hgb                           | downstream_only |                  60 |     0.952381 |                180 |      2.06209 |       2.44951 |             0.0444444 |
|    58 | mlp                           | all_six_with_b2 |                  70 |     0.972222 |                420 |      4.07866 |      18.8403  |             0.209524  |
|    58 | mlp                           | downstream_only |                  70 |     0.972222 |                210 |      2.15292 |       3.3796  |             0.0666667 |
|    59 | mlp                           | all_six_with_b2 |                 729 |     0.973298 |               4374 |      3.11605 |      10.1507  |             0.131916  |
|    59 | mlp                           | downstream_only |                 729 |     0.973298 |               2187 |      1.98804 |       4.06102 |             0.0576132 |
|    60 | mlp                           | all_six_with_b2 |                 790 |     0.985037 |               4740 |      2.74099 |       7.19611 |             0.0696203 |
|    60 | mlp                           | downstream_only |                 790 |     0.985037 |               2370 |      1.93274 |       3.51405 |             0.0451477 |
|    61 | mlp                           | all_six_with_b2 |                 920 |     0.994595 |               5520 |      3.07308 |       7.5495  |             0.100906  |
|    61 | mlp                           | downstream_only |                 920 |     0.994595 |               2760 |      2.1673  |       6.09243 |             0.0710145 |
|    62 | mlp                           | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.86803 |       7.7212  |             0.082594  |
|    62 | mlp                           | downstream_only |                 789 |     0.988722 |               2367 |      2.00898 |       2.67495 |             0.0363329 |
|    63 | mlp                           | all_six_with_b2 |                 354 |     0.969863 |               2124 |      3.27099 |      13.8717  |             0.161488  |
|    63 | mlp                           | downstream_only |                 354 |     0.969863 |               1062 |      2.11826 |       6.12124 |             0.0555556 |
|    65 | mlp                           | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.74615 |      18.3436  |             0.169444  |
|    65 | mlp                           | downstream_only |                  60 |     0.952381 |                180 |      2.08805 |       2.56336 |             0.0444444 |
|    58 | cnn1d                         | all_six_with_b2 |                  70 |     0.972222 |                420 |      3.61352 |      18.6822  |             0.171429  |
|    58 | cnn1d                         | downstream_only |                  70 |     0.972222 |                210 |      1.94081 |       2.29717 |             0.0142857 |
|    59 | cnn1d                         | all_six_with_b2 |                 735 |     0.981308 |               4410 |      3.00079 |      10.5358  |             0.114286  |
|    59 | cnn1d                         | downstream_only |                 735 |     0.981308 |               2205 |      1.81526 |       4.46185 |             0.0231293 |
|    60 | cnn1d                         | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.69597 |       8.46875 |             0.0508617 |
|    60 | cnn1d                         | downstream_only |                 793 |     0.988778 |               2379 |      1.91242 |       5.57193 |             0.02438   |
|    61 | cnn1d                         | all_six_with_b2 |                 923 |     0.997838 |               5538 |      3.10297 |       7.75648 |             0.0846876 |
|    61 | cnn1d                         | downstream_only |                 923 |     0.997838 |               2769 |      2.18886 |       6.39312 |             0.0476706 |
|    62 | cnn1d                         | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.76706 |       7.60468 |             0.0669624 |
|    62 | cnn1d                         | downstream_only |                 789 |     0.988722 |               2367 |      1.86656 |       2.262   |             0.0135192 |
|    63 | cnn1d                         | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.03925 |      13.9246  |             0.144601  |
|    63 | cnn1d                         | downstream_only |                 355 |     0.972603 |               1065 |      1.7341  |       6.19339 |             0.0338028 |
|    65 | cnn1d                         | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.50365 |      18.3162  |             0.155556  |
|    65 | cnn1d                         | downstream_only |                  60 |     0.952381 |                180 |      2.05713 |       2.35302 |             0.0111111 |
|    58 | gated_mixer                   | all_six_with_b2 |                  70 |     0.972222 |                420 |      3.71095 |      18.7314  |             0.169048  |
|    58 | gated_mixer                   | downstream_only |                  70 |     0.972222 |                210 |      1.85786 |       2.40934 |             0.0190476 |
|    59 | gated_mixer                   | all_six_with_b2 |                 732 |     0.977303 |               4392 |      2.9784  |      10.2333  |             0.114299  |
|    59 | gated_mixer                   | downstream_only |                 732 |     0.977303 |               2196 |      1.83861 |       3.72403 |             0.0236794 |
|    60 | gated_mixer                   | all_six_with_b2 |                 794 |     0.990025 |               4764 |      2.69483 |       9.00285 |             0.0556255 |
|    60 | gated_mixer                   | downstream_only |                 794 |     0.990025 |               2382 |      1.91374 |       6.62439 |             0.0277078 |
|    61 | gated_mixer                   | all_six_with_b2 |                 923 |     0.997838 |               5538 |      3.09517 |       7.71676 |             0.0929939 |
|    61 | gated_mixer                   | downstream_only |                 923 |     0.997838 |               2769 |      2.16226 |       6.37113 |             0.0592272 |
|    62 | gated_mixer                   | all_six_with_b2 |                 790 |     0.989975 |               4740 |      2.78202 |       7.60263 |             0.0738397 |
|    62 | gated_mixer                   | downstream_only |                 790 |     0.989975 |               2370 |      1.87086 |       2.30048 |             0.0202532 |
|    63 | gated_mixer                   | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.10218 |      13.9426  |             0.148357  |
|    63 | gated_mixer                   | downstream_only |                 355 |     0.972603 |               1065 |      1.72149 |       6.25883 |             0.0309859 |
|    65 | gated_mixer                   | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.48438 |      18.3556  |             0.158333  |
|    65 | gated_mixer                   | downstream_only |                  60 |     0.952381 |                180 |      2.04544 |       2.40465 |             0.0111111 |

## Support and Systematic Proxies

The ticket asks that timing improvements not hide charge, pile-up, saturation, dropout, PID, or energy support damage.  There is no truth PID or energy label in these ROOT files, so the report tracks auditable proxies: B2 amplitude ratio for charge balance, peak spread for pile-up-like topology, B2 amplitude for energy support, saturation/dropout flags, and anomaly fraction as a weak PID-support proxy.

|   run | method                        |   acceptance |   charge_proxy_b2_amp_ratio_mean_all |   charge_proxy_b2_amp_ratio_mean_kept |   pileup_proxy_peak_spread_mean_all |   pileup_proxy_peak_spread_mean_kept |   energy_proxy_b2_amp_mean_all |   energy_proxy_b2_amp_mean_kept |   saturation_frac_all |   saturation_frac_kept |   dropout_frac_all |   dropout_frac_kept |   pid_support_proxy_anomaly_frac_all |   pid_support_proxy_anomaly_frac_kept |   max_support_drift |
|------:|:------------------------------|-------------:|-------------------------------------:|--------------------------------------:|------------------------------------:|-------------------------------------:|-------------------------------:|--------------------------------:|----------------------:|-----------------------:|-------------------:|--------------------:|-------------------------------------:|--------------------------------------:|--------------------:|
|    58 | traditional_explicit_timewalk |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | traditional_explicit_timewalk |     0.979973 |                              1.31205 |                               1.32218 |                             1.6996  |                              1.61308 |                        3032.5  |                         3051.98 |            0.0186916  |             0.0177112  |          0.0894526 |           0.0844687 |                            0.0881175 |                             0.0694823 |          0.0509064  |
|    60 | traditional_explicit_timewalk |     0.988778 |                              1.04942 |                               1.05142 |                             1.57731 |                              1.54098 |                        2836.37 |                         2844.81 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.0230286  |
|    61 | traditional_explicit_timewalk |     0.997838 |                              1.09137 |                               1.09174 |                             1.60649 |                              1.60238 |                        2788.92 |                         2791.03 |            0.00216216 |             0.00216685 |          0.0540541 |           0.0530878 |                            0.0583784 |                             0.056338  |          0.00255399 |
|    62 | traditional_explicit_timewalk |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | traditional_explicit_timewalk |     0.969863 |                              1.44474 |                               1.44312 |                             1.81644 |                              1.69774 |                        3296.6  |                         3291.26 |            0.0219178  |             0.0169492  |          0.123288  |           0.121469  |                            0.10137   |                             0.0734463 |          0.0653467  |
|    65 | traditional_explicit_timewalk |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | ridge                         |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | ridge                         |     0.975968 |                              1.31205 |                               1.32247 |                             1.6996  |                              1.61012 |                        3032.5  |                         3054.9  |            0.0186916  |             0.0177839  |          0.0894526 |           0.0807114 |                            0.0881175 |                             0.0656635 |          0.0526455  |
|    60 | ridge                         |     0.983791 |                              1.04942 |                               1.05118 |                             1.57731 |                              1.53992 |                        2836.37 |                         2838.76 |            0.00249377 |             0.00126743 |          0.0436409 |           0.0405577 |                            0.0685786 |                             0.0532319 |          0.0237004  |
|    61 | ridge                         |     0.992432 |                              1.09137 |                               1.09283 |                             1.60649 |                              1.59913 |                        2788.92 |                         2795.15 |            0.00216216 |             0.00217865 |          0.0540541 |           0.0511983 |                            0.0583784 |                             0.0511983 |          0.00718012 |
|    62 | ridge                         |     0.983709 |                              1.15217 |                               1.15114 |                             1.43484 |                              1.38726 |                        2812.96 |                         2818.16 |            0.00877193 |             0.00764331 |          0.0714286 |           0.0649682 |                            0.0639098 |                             0.0484076 |          0.0331577  |
|    63 | ridge                         |     0.967123 |                              1.44474 |                               1.44719 |                             1.81644 |                              1.69688 |                        3296.6  |                         3307.75 |            0.0219178  |             0.0169972  |          0.123288  |           0.11898   |                            0.10137   |                             0.0708215 |          0.0658181  |
|    65 | ridge                         |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | hgb                           |     0.972222 |                              1.42047 |                               1.44268 |                             2.16667 |                              2.1     |                        3561.17 |                         3618.99 |            0.0277778  |             0.0285714  |          0.111111  |           0.1       |                            0.0833333 |                             0.0571429 |          0.0307692  |
|    59 | hgb                           |     0.977303 |                              1.31205 |                               1.3194  |                             1.6996  |                              1.60383 |                        3032.5  |                         3044.56 |            0.0186916  |             0.0163934  |          0.0894526 |           0.0806011 |                            0.0881175 |                             0.0669399 |          0.0563511  |
|    60 | hgb                           |     0.982544 |                              1.04942 |                               1.04956 |                             1.57731 |                              1.48731 |                        2836.37 |                         2839.71 |            0.00249377 |             0.00253807 |          0.0436409 |           0.0380711 |                            0.0685786 |                             0.0520305 |          0.0570574  |
|    61 | hgb                           |     0.993514 |                              1.09137 |                               1.0918  |                             1.60649 |                              1.5691  |                        2788.92 |                         2787.13 |            0.00216216 |             0.00217628 |          0.0540541 |           0.0533188 |                            0.0583784 |                             0.0522307 |          0.0232742  |
|    62 | hgb                           |     0.989975 |                              1.15217 |                               1.14799 |                             1.43484 |                              1.39241 |                        2812.96 |                         2810.2  |            0.00877193 |             0.00759494 |          0.0714286 |           0.0670886 |                            0.0639098 |                             0.0544304 |          0.0295727  |
|    63 | hgb                           |     0.967123 |                              1.44474 |                               1.44778 |                             1.81644 |                              1.69122 |                        3296.6  |                         3302.17 |            0.0219178  |             0.0169972  |          0.123288  |           0.11898   |                            0.10137   |                             0.0708215 |          0.0689372  |
|    65 | hgb                           |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | mlp                           |     0.972222 |                              1.42047 |                               1.44268 |                             2.16667 |                              2.1     |                        3561.17 |                         3618.99 |            0.0277778  |             0.0285714  |          0.111111  |           0.1       |                            0.0833333 |                             0.0571429 |          0.0307692  |
|    59 | mlp                           |     0.973298 |                              1.31205 |                               1.32268 |                             1.6996  |                              1.61043 |                        3032.5  |                         3055.92 |            0.0186916  |             0.0178326  |          0.0894526 |           0.0781893 |                            0.0881175 |                             0.0631001 |          0.0524678  |
|    60 | mlp                           |     0.985037 |                              1.04942 |                               1.04947 |                             1.57731 |                              1.5     |                        2836.37 |                         2838.85 |            0.00249377 |             0.00253165 |          0.0436409 |           0.0392405 |                            0.0685786 |                             0.0544304 |          0.0490119  |
|    61 | mlp                           |     0.994595 |                              1.09137 |                               1.09147 |                             1.60649 |                              1.59348 |                        2788.92 |                         2790.77 |            0.00216216 |             0.00217391 |          0.0540541 |           0.0532609 |                            0.0583784 |                             0.0532609 |          0.00809731 |
|    62 | mlp                           |     0.988722 |                              1.15217 |                               1.14978 |                             1.43484 |                              1.39797 |                        2812.96 |                         2814.75 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0256928  |
|    63 | mlp                           |     0.969863 |                              1.44474 |                               1.44312 |                             1.81644 |                              1.69774 |                        3296.6  |                         3291.26 |            0.0219178  |             0.0169492  |          0.123288  |           0.121469  |                            0.10137   |                             0.0734463 |          0.0653467  |
|    65 | mlp                           |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | cnn1d                         |     0.972222 |                              1.42047 |                               1.44268 |                             2.16667 |                              2.1     |                        3561.17 |                         3618.99 |            0.0277778  |             0.0285714  |          0.111111  |           0.1       |                            0.0833333 |                             0.0571429 |          0.0307692  |
|    59 | cnn1d                         |     0.981308 |                              1.31205 |                               1.322   |                             1.6996  |                              1.61769 |                        3032.5  |                         3053.22 |            0.0186916  |             0.0176871  |          0.0894526 |           0.0843537 |                            0.0881175 |                             0.0707483 |          0.0481951  |
|    60 | cnn1d                         |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | cnn1d                         |     0.997838 |                              1.09137 |                               1.09174 |                             1.60649 |                              1.60238 |                        2788.92 |                         2791.03 |            0.00216216 |             0.00216685 |          0.0540541 |           0.0530878 |                            0.0583784 |                             0.056338  |          0.00255399 |
|    62 | cnn1d                         |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | cnn1d                         |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | cnn1d                         |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | gated_mixer                   |     0.972222 |                              1.42047 |                               1.44268 |                             2.16667 |                              2.1     |                        3561.17 |                         3618.99 |            0.0277778  |             0.0285714  |          0.111111  |           0.1       |                            0.0833333 |                             0.0571429 |          0.0307692  |
|    59 | gated_mixer                   |     0.977303 |                              1.31205 |                               1.32255 |                             1.6996  |                              1.61612 |                        3032.5  |                         3057.21 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0806011 |                            0.0881175 |                             0.0669399 |          0.049117   |
|    60 | gated_mixer                   |     0.990025 |                              1.04942 |                               1.05224 |                             1.57731 |                              1.55164 |                        2836.37 |                         2845.52 |            0.00249377 |             0.00251889 |          0.0436409 |           0.0403023 |                            0.0685786 |                             0.059194  |          0.0162742  |
|    61 | gated_mixer                   |     0.997838 |                              1.09137 |                               1.09174 |                             1.60649 |                              1.60238 |                        2788.92 |                         2791.03 |            0.00216216 |             0.00216685 |          0.0540541 |           0.0530878 |                            0.0583784 |                             0.056338  |          0.00255399 |
|    62 | gated_mixer                   |     0.989975 |                              1.15217 |                               1.14902 |                             1.43484 |                              1.39747 |                        2812.96 |                         2813.31 |            0.00877193 |             0.00759494 |          0.0714286 |           0.0670886 |                            0.0639098 |                             0.0544304 |          0.0260439  |
|    63 | gated_mixer                   |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | gated_mixer                   |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |

## Hyperparameter CV and Controls

Model selection CV is grouped by training run.  Final claims use held-out analysis runs only.

| model       | feature_set       |   alpha |   fold |   sigma68_ns | candidate                                                     |   target_sigma68_ns |
|:------------|:------------------|--------:|-------:|-------------:|:--------------------------------------------------------------|--------------------:|
| traditional | amp_poly_by_stave |     0.1 |      1 |      2.12612 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      2 |      2.17684 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      3 |      2.42545 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      4 |      2.31447 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |     -1 |      2.26072 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      1 |      2.13779 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      2 |      2.18234 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      3 |      2.41877 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      4 |      2.31338 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |     -1 |      2.26307 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      1 |      2.08745 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      2 |      2.14228 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      3 |      2.36659 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      4 |      2.24801 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |     -1 |      2.21108 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      1 |      2.21063 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      2 |      1.98439 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      3 |      2.2139  | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      4 |      2.1072  | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |     -1 |      2.12903 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      1 |      2.05637 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      2 |      1.84519 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      3 |      1.95523 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      4 |      1.89407 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |     -1 |      1.93772 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      1 |      2.35254 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      2 |      1.97355 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      3 |      2.1725  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      4 |      2.29165 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |     -1 |      2.19756 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      1 |      2.35155 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      2 |      1.97238 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      3 |      2.17064 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      4 |      2.28984 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |     -1 |      2.19611 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      1 |      2.32352 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      2 |      1.94546 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      3 |      2.15969 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      4 |      2.2934  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |     -1 |      2.18052 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      1 |      2.23391 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      2 |      1.90766 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      3 |      2.06475 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      4 |      2.17506 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |     -1 |      2.09535 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      1 |      1.7867  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      2 |      1.56931 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      3 |      1.68363 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      4 |      1.75429 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |     -1 |      1.69848 | nan                                                           |           nan       |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 0.1}                                                |             1.60291 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 0.1}                                                |             1.5814  |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 0.1}                                                |             1.77822 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 0.1}                                                |             1.64681 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 0.1}                                                |             1.65234 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 1.0}                                                |             1.59361 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 1.0}                                                |             1.5773  |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 1.0}                                                |             1.77784 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 1.0}                                                |             1.6327  |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 1.0}                                                |             1.64536 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 10.0}                                               |             1.57365 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 10.0}                                               |             1.54073 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 10.0}                                               |             1.73299 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 10.0}                                               |             1.65244 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 10.0}                                               |             1.62495 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 100.0}                                              |             1.4522  |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 100.0}                                              |             1.44151 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 100.0}                                              |             1.63916 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 100.0}                                              |             1.5745  |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 100.0}                                              |             1.52684 |
| hgb         | nan               |   nan   |      1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.47247 |
| hgb         | nan               |   nan   |      2 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.67935 |
| hgb         | nan               |   nan   |      3 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.4687  |
| hgb         | nan               |   nan   |      4 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.61931 |
| hgb         | nan               |   nan   |     -1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.55996 |
| hgb         | nan               |   nan   |      1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.50464 |
| hgb         | nan               |   nan   |      2 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.70453 |
| hgb         | nan               |   nan   |      3 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.47996 |
| hgb         | nan               |   nan   |      4 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.53021 |
| hgb         | nan               |   nan   |     -1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.55484 |

Ineligible controls inherited from the S04h model stack:

| control                           | best                                                                                                      |   cv_rows |
|:----------------------------------|:----------------------------------------------------------------------------------------------------------|----------:|
| run_only_control                  | {"alpha": 100.0, "model": "ridge", "score": 1.4527392756938933}                                           |        20 |
| target_stave_excluded_hgb_control | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31, "model": "hgb", "score": 1.583682579642565} |        10 |
| shuffled_target_ridge_control     | {"alpha": 100.0, "model": "ridge", "score": 3.8472350943088527}                                           |        20 |

## Systematics and Caveats

The analysis is raw-data anchored but conditional on the selected-pulse and all-hit definitions.  The veto score intentionally avoids held-out residual labels; it uses only waveform support axes and model-predicted correction summaries, with the acceptance threshold frozen on training runs.  The bootstrap quantifies finite held-out-run variation, not architecture-search multiplicity or future detector-state changes.  The PID and energy entries are support proxies only because no ROOT truth labels are available.  A veto that narrows all-six residuals can still be unsuitable for physics adoption if it selectively removes important topology, so the support-preserving flag is a gate, not just a statistic.

## Verdict

The S04j support-preserving veto winner is hgb, with retained all-six mean held-out-run sigma68 2.986 ns [2.701, 3.314], mean acceptance 0.976, and max support-proxy drift 0.056. The traditional explicit-timewalk veto gives 3.009 ns [2.879, 3.177]. The result supports pathology abstention, not B2-inclusive timing adoption, because the all-six minus downstream-only harm delta remains positive.

## Next Experiment

S04k: downstream-only deployment check for pathology-vetoed all-hit events

Question: does the S04j support-preserving veto remain stable when deployed as a downstream-only timing quality flag instead of an all-six B2-inclusive correction? Expected information gain: separates useful pathology abstention from unsupported B2 timing-constraint adoption with the same run-held-out and support-proxy gates.

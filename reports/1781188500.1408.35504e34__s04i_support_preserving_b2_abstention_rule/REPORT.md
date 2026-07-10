# S04i: support-preserving B2 abstention rule for all-hit timing closure

- **Ticket:** `1781188500.1408.35504e34`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Output:** `reports/1781188500.1408.35504e34__s04i_support_preserving_b2_abstention_rule`
- **Git commit:** `6fce8edc68a587e914ed0be5b1eee939618440a4`

## Preregistered Question

Can a preregistered B2 abstention rule based only on B2 amplitude imbalance, peak-spread, and baseline-excursion atoms recover downstream-like closure while retaining a useful fraction of all-hit events?  The abstention rule is evaluated on B2/B4/B6/B8 all-hit events.  It is not an energy, PID, or pile-up truth claim; those quantities are represented only by raw waveform support proxies.

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

Each method receives the same abstention score calibrated on train runs.  The score is atom-only and intentionally excludes timing residuals, detector flags, and model predictions:

`a_e = |log(max(r_e, 1e-6))| + s_e / 6 + b_e / 800`,

where `r_e` is the B2 amplitude ratio from the all-hit event record, `s_e` is peak spread in samples, and `b_e` is baseline span in ADC counts.  The threshold `tau_0.95` is the train-run `95%` quantile of `a_e`; held-out event `e` is retained if and only if `a_e <= tau_0.95`.  Because the abstention score is independent of method predictions, differences among methods reflect timing correction behavior on an identical retained event support.

## Abstention Policies

| method                        |   train_score_threshold |   train_target_acceptance |   heldout_event_acceptance |   n_train_events |   n_heldout_events |   n_accepted_heldout_events |
|:------------------------------|------------------------:|--------------------------:|---------------------------:|-----------------:|-------------------:|----------------------------:|
| traditional_explicit_timewalk |                 3.44303 |                      0.95 |                   0.985692 |              782 |               3774 |                        3720 |
| ridge                         |                 3.44303 |                      0.95 |                   0.985692 |              782 |               3774 |                        3720 |
| hgb                           |                 3.44303 |                      0.95 |                   0.985692 |              782 |               3774 |                        3720 |
| mlp                           |                 3.44303 |                      0.95 |                   0.985692 |              782 |               3774 |                        3720 |
| cnn1d                         |                 3.44303 |                      0.95 |                   0.985692 |              782 |               3774 |                        3720 |
| gated_mixer                   |                 3.44303 |                      0.95 |                   0.985692 |              782 |               3774 |                        3720 |

## Head-to-Head Result

| method                        |   mean_run_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_run_full_rms_ns |   mean_run_tail_frac_abs_gt5ns |   mean_acceptance |   mean_max_support_drift |   b2_harm_delta_ns |   primary_score | support_preserving   |
|:------------------------------|----------------------:|--------------------:|---------------------:|-----------------------:|-------------------------------:|------------------:|-------------------------:|-------------------:|----------------:|:---------------------|
| hgb                           |               2.99803 |             2.72008 |              3.32356 |                12.1566 |                       0.129099 |          0.976411 |                0.0474226 |            1.08722 |         2.99803 | True                 |
| traditional_explicit_timewalk |               3.00969 |             2.87805 |              3.17633 |                12.1872 |                       0.13447  |          0.976411 |                0.0474226 |            1.19494 |         3.00969 | True                 |
| cnn1d                         |               3.11372 |             2.88389 |              3.40177 |                12.1733 |                       0.112703 |          0.976411 |                0.0474226 |            1.19144 |         3.11372 | True                 |
| gated_mixer                   |               3.12731 |             2.88716 |              3.39721 |                12.1844 |                       0.116471 |          0.976411 |                0.0474226 |            1.21224 |         3.12731 | True                 |
| mlp                           |               3.27799 |             2.96946 |              3.61961 |                12.1674 |                       0.133955 |          0.976411 |                0.0474226 |            1.21118 |         3.27799 | True                 |
| ridge                         |               3.72279 |             3.50113 |              4.0213  |                12.2912 |                       0.159144 |          0.976411 |                0.0474226 |            1.67528 |         3.72279 | True                 |

The winner is **hgb** with retained all-six sigma68 `2.998` ns [2.720, 3.324].  The traditional comparator gives `3.010` ns [2.878, 3.176].  Negative ML-minus-traditional would favor ML; here the winning delta is `-0.012` ns.

## Per-Run Metrics

|   run | method                        | pair_scope      |   n_accepted_events |   acceptance |   n_pair_residuals |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|------:|:------------------------------|:----------------|--------------------:|-------------:|-------------------:|-------------:|--------------:|----------------------:|
|    58 | traditional_explicit_timewalk | all_six_with_b2 |                  69 |     0.958333 |                414 |      3.46576 |      18.7594  |             0.202899  |
|    58 | traditional_explicit_timewalk | downstream_only |                  69 |     0.958333 |                207 |      1.78194 |       2.65736 |             0.0724638 |
|    59 | traditional_explicit_timewalk | all_six_with_b2 |                 732 |     0.977303 |               4392 |      2.98934 |      10.327   |             0.135018  |
|    59 | traditional_explicit_timewalk | downstream_only |                 732 |     0.977303 |               2196 |      1.75792 |       4.18751 |             0.0601093 |
|    60 | traditional_explicit_timewalk | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.78773 |       8.55452 |             0.0836486 |
|    60 | traditional_explicit_timewalk | downstream_only |                 793 |     0.988778 |               2379 |      1.96732 |       5.78668 |             0.0765027 |
|    61 | traditional_explicit_timewalk | all_six_with_b2 |                 922 |     0.996757 |               5532 |      2.96948 |       7.8167  |             0.0909255 |
|    61 | traditional_explicit_timewalk | downstream_only |                 922 |     0.996757 |               2766 |      1.9703  |       6.53922 |             0.0817064 |
|    62 | traditional_explicit_timewalk | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.82816 |       7.64941 |             0.0889311 |
|    62 | traditional_explicit_timewalk | downstream_only |                 789 |     0.988722 |               2367 |      1.8409  |       2.57459 |             0.0561893 |
|    63 | traditional_explicit_timewalk | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.10515 |      13.9394  |             0.170423  |
|    63 | traditional_explicit_timewalk | downstream_only |                 355 |     0.972603 |               1065 |      1.73995 |       6.41698 |             0.0732394 |
|    65 | traditional_explicit_timewalk | all_six_with_b2 |                  60 |     0.952381 |                360 |      2.92218 |      18.2637  |             0.169444  |
|    65 | traditional_explicit_timewalk | downstream_only |                  60 |     0.952381 |                180 |      1.64486 |       2.15098 |             0.0277778 |
|    58 | ridge                         | all_six_with_b2 |                  69 |     0.958333 |                414 |      4.54062 |      18.9811  |             0.219807  |
|    58 | ridge                         | downstream_only |                  69 |     0.958333 |                207 |      1.89932 |       3.38917 |             0.0772947 |
|    59 | ridge                         | all_six_with_b2 |                 732 |     0.977303 |               4392 |      3.56921 |      10.4068  |             0.151867  |
|    59 | ridge                         | downstream_only |                 732 |     0.977303 |               2196 |      1.95488 |       4.2508  |             0.0673953 |
|    60 | ridge                         | all_six_with_b2 |                 793 |     0.988778 |               4758 |      3.36625 |       8.68865 |             0.108449  |
|    60 | ridge                         | downstream_only |                 793 |     0.988778 |               2379 |      2.01991 |       6.03025 |             0.0828079 |
|    61 | ridge                         | all_six_with_b2 |                 922 |     0.996757 |               5532 |      3.59141 |       7.83373 |             0.137925  |
|    61 | ridge                         | downstream_only |                 922 |     0.996757 |               2766 |      2.2492  |       6.56373 |             0.117498  |
|    62 | ridge                         | all_six_with_b2 |                 789 |     0.988722 |               4734 |      3.4102  |       7.8289  |             0.117871  |
|    62 | ridge                         | downstream_only |                 789 |     0.988722 |               2367 |      2.05295 |       3.21377 |             0.069286  |
|    63 | ridge                         | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.78509 |      13.997   |             0.189202  |
|    63 | ridge                         | downstream_only |                 355 |     0.972603 |               1065 |      2.00903 |       6.61332 |             0.085446  |
|    65 | ridge                         | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.79677 |      18.3021  |             0.188889  |
|    65 | ridge                         | downstream_only |                  60 |     0.952381 |                180 |      2.14732 |       2.67242 |             0.0555556 |
|    58 | hgb                           | all_six_with_b2 |                  69 |     0.958333 |                414 |      3.72325 |      19.0603  |             0.210145  |
|    58 | hgb                           | downstream_only |                  69 |     0.958333 |                207 |      2.00455 |       3.33198 |             0.0772947 |
|    59 | hgb                           | all_six_with_b2 |                 732 |     0.977303 |               4392 |      2.82492 |      10.2507  |             0.130009  |
|    59 | hgb                           | downstream_only |                 732 |     0.977303 |               2196 |      1.78637 |       4.12988 |             0.0505464 |
|    60 | hgb                           | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.54683 |       8.39146 |             0.0647331 |
|    60 | hgb                           | downstream_only |                 793 |     0.988778 |               2379 |      1.76278 |       5.37086 |             0.0462379 |
|    61 | hgb                           | all_six_with_b2 |                 922 |     0.996757 |               5532 |      2.82069 |       7.76686 |             0.0887563 |
|    61 | hgb                           | downstream_only |                 922 |     0.996757 |               2766 |      2.02007 |       6.34407 |             0.065799  |
|    62 | hgb                           | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.6074  |       7.60171 |             0.0777355 |
|    62 | hgb                           | downstream_only |                 789 |     0.988722 |               2367 |      1.8569  |       2.61411 |             0.034643  |
|    63 | hgb                           | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.07502 |      13.741   |             0.160094  |
|    63 | hgb                           | downstream_only |                 355 |     0.972603 |               1065 |      1.88289 |       5.94869 |             0.0600939 |
|    65 | hgb                           | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.38806 |      18.2841  |             0.172222  |
|    65 | hgb                           | downstream_only |                  60 |     0.952381 |                180 |      2.06209 |       2.44951 |             0.0444444 |
|    58 | mlp                           | all_six_with_b2 |                  69 |     0.958333 |                414 |      4.07777 |      18.9719  |             0.210145  |
|    58 | mlp                           | downstream_only |                  69 |     0.958333 |                207 |      2.12831 |       3.36717 |             0.0628019 |
|    59 | mlp                           | all_six_with_b2 |                 732 |     0.977303 |               4392 |      3.13494 |      10.2858  |             0.135701  |
|    59 | mlp                           | downstream_only |                 732 |     0.977303 |               2196 |      2.00079 |       3.95049 |             0.0619308 |
|    60 | mlp                           | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.75484 |       8.33644 |             0.0733501 |
|    60 | mlp                           | downstream_only |                 793 |     0.988778 |               2379 |      1.94354 |       5.26438 |             0.04876   |
|    61 | mlp                           | all_six_with_b2 |                 922 |     0.996757 |               5532 |      3.08067 |       7.6112  |             0.102856  |
|    61 | mlp                           | downstream_only |                 922 |     0.996757 |               2766 |      2.17581 |       6.20769 |             0.0730296 |
|    62 | mlp                           | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.86941 |       7.73495 |             0.0828052 |
|    62 | mlp                           | downstream_only |                 789 |     0.988722 |               2367 |      2.01362 |       2.73144 |             0.0371779 |
|    63 | mlp                           | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.28215 |      13.8878  |             0.16338   |
|    63 | mlp                           | downstream_only |                 355 |     0.972603 |               1065 |      2.11755 |       6.14955 |             0.057277  |
|    65 | mlp                           | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.74615 |      18.3436  |             0.169444  |
|    65 | mlp                           | downstream_only |                  60 |     0.952381 |                180 |      2.08805 |       2.56336 |             0.0444444 |
|    58 | cnn1d                         | all_six_with_b2 |                  69 |     0.958333 |                414 |      3.70852 |      18.8158  |             0.173913  |
|    58 | cnn1d                         | downstream_only |                  69 |     0.958333 |                207 |      1.88164 |       2.30394 |             0.0144928 |
|    59 | cnn1d                         | all_six_with_b2 |                 732 |     0.977303 |               4392 |      2.97847 |      10.3228  |             0.11225   |
|    59 | cnn1d                         | downstream_only |                 732 |     0.977303 |               2196 |      1.81544 |       4.10046 |             0.0223133 |
|    60 | cnn1d                         | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.69597 |       8.46875 |             0.0508617 |
|    60 | cnn1d                         | downstream_only |                 793 |     0.988778 |               2379 |      1.91242 |       5.57193 |             0.02438   |
|    61 | cnn1d                         | all_six_with_b2 |                 922 |     0.996757 |               5532 |      3.10308 |       7.76043 |             0.0847795 |
|    61 | cnn1d                         | downstream_only |                 922 |     0.996757 |               2766 |      2.18864 |       6.39613 |             0.0477223 |
|    62 | cnn1d                         | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.76706 |       7.60468 |             0.0669624 |
|    62 | cnn1d                         | downstream_only |                 789 |     0.988722 |               2367 |      1.86656 |       2.262   |             0.0135192 |
|    63 | cnn1d                         | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.03925 |      13.9246  |             0.144601  |
|    63 | cnn1d                         | downstream_only |                 355 |     0.972603 |               1065 |      1.7341  |       6.19339 |             0.0338028 |
|    65 | cnn1d                         | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.50365 |      18.3162  |             0.155556  |
|    65 | cnn1d                         | downstream_only |                  60 |     0.952381 |                180 |      2.05713 |       2.35302 |             0.0111111 |
|    58 | gated_mixer                   | all_six_with_b2 |                  69 |     0.958333 |                414 |      3.75352 |      18.8656  |             0.171498  |
|    58 | gated_mixer                   | downstream_only |                  69 |     0.958333 |                207 |      1.85331 |       2.42399 |             0.0193237 |
|    59 | gated_mixer                   | all_six_with_b2 |                 732 |     0.977303 |               4392 |      2.98553 |      10.3016  |             0.115437  |
|    59 | gated_mixer                   | downstream_only |                 732 |     0.977303 |               2196 |      1.83981 |       3.97427 |             0.0250455 |
|    60 | gated_mixer                   | all_six_with_b2 |                 793 |     0.988778 |               4758 |      2.68886 |       8.4985  |             0.054855  |
|    60 | gated_mixer                   | downstream_only |                 793 |     0.988778 |               2379 |      1.91335 |       5.6868  |             0.0269021 |
|    61 | gated_mixer                   | all_six_with_b2 |                 922 |     0.996757 |               5532 |      3.09823 |       7.72084 |             0.0930947 |
|    61 | gated_mixer                   | downstream_only |                 922 |     0.996757 |               2766 |      2.16279 |       6.37443 |             0.0592914 |
|    62 | gated_mixer                   | all_six_with_b2 |                 789 |     0.988722 |               4734 |      2.77847 |       7.60627 |             0.073722  |
|    62 | gated_mixer                   | downstream_only |                 789 |     0.988722 |               2367 |      1.86932 |       2.29928 |             0.0202788 |
|    63 | gated_mixer                   | all_six_with_b2 |                 355 |     0.972603 |               2130 |      3.10218 |      13.9426  |             0.148357  |
|    63 | gated_mixer                   | downstream_only |                 355 |     0.972603 |               1065 |      1.72149 |       6.25883 |             0.0309859 |
|    65 | gated_mixer                   | all_six_with_b2 |                  60 |     0.952381 |                360 |      3.48438 |      18.3556  |             0.158333  |
|    65 | gated_mixer                   | downstream_only |                  60 |     0.952381 |                180 |      2.04544 |       2.40465 |             0.0111111 |

## Support and Systematic Proxies

The ticket asks that timing improvements not hide charge, pile-up, saturation, dropout, PID, or energy support damage.  There is no truth PID or energy label in these ROOT files, so the report tracks auditable proxies: B2 amplitude ratio for charge balance, peak spread for pile-up-like topology, B2 amplitude for energy support, saturation/dropout flags, and anomaly fraction as a weak PID-support proxy.

|   run | method                        |   acceptance |   charge_proxy_b2_amp_ratio_mean_all |   charge_proxy_b2_amp_ratio_mean_kept |   pileup_proxy_peak_spread_mean_all |   pileup_proxy_peak_spread_mean_kept |   energy_proxy_b2_amp_mean_all |   energy_proxy_b2_amp_mean_kept |   saturation_frac_all |   saturation_frac_kept |   dropout_frac_all |   dropout_frac_kept |   pid_support_proxy_anomaly_frac_all |   pid_support_proxy_anomaly_frac_kept |   max_support_drift |
|------:|:------------------------------|-------------:|-------------------------------------:|--------------------------------------:|------------------------------------:|-------------------------------------:|-------------------------------:|--------------------------------:|----------------------:|-----------------------:|-------------------:|--------------------:|-------------------------------------:|--------------------------------------:|--------------------:|
|    58 | traditional_explicit_timewalk |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | traditional_explicit_timewalk |     0.977303 |                              1.31205 |                               1.32205 |                             1.6996  |                              1.61066 |                        3032.5  |                         3055.77 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0833333 |                            0.0881175 |                             0.0669399 |          0.0523322  |
|    60 | traditional_explicit_timewalk |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | traditional_explicit_timewalk |     0.996757 |                              1.09137 |                               1.09229 |                             1.60649 |                              1.60304 |                        2788.92 |                         2792.42 |            0.00216216 |             0.0021692  |          0.0540541 |           0.0531453 |                            0.0583784 |                             0.0553145 |          0.00306384 |
|    62 | traditional_explicit_timewalk |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | traditional_explicit_timewalk |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | traditional_explicit_timewalk |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | ridge                         |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | ridge                         |     0.977303 |                              1.31205 |                               1.32205 |                             1.6996  |                              1.61066 |                        3032.5  |                         3055.77 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0833333 |                            0.0881175 |                             0.0669399 |          0.0523322  |
|    60 | ridge                         |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | ridge                         |     0.996757 |                              1.09137 |                               1.09229 |                             1.60649 |                              1.60304 |                        2788.92 |                         2792.42 |            0.00216216 |             0.0021692  |          0.0540541 |           0.0531453 |                            0.0583784 |                             0.0553145 |          0.00306384 |
|    62 | ridge                         |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | ridge                         |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | ridge                         |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | hgb                           |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | hgb                           |     0.977303 |                              1.31205 |                               1.32205 |                             1.6996  |                              1.61066 |                        3032.5  |                         3055.77 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0833333 |                            0.0881175 |                             0.0669399 |          0.0523322  |
|    60 | hgb                           |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | hgb                           |     0.996757 |                              1.09137 |                               1.09229 |                             1.60649 |                              1.60304 |                        2788.92 |                         2792.42 |            0.00216216 |             0.0021692  |          0.0540541 |           0.0531453 |                            0.0583784 |                             0.0553145 |          0.00306384 |
|    62 | hgb                           |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | hgb                           |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | hgb                           |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | mlp                           |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | mlp                           |     0.977303 |                              1.31205 |                               1.32205 |                             1.6996  |                              1.61066 |                        3032.5  |                         3055.77 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0833333 |                            0.0881175 |                             0.0669399 |          0.0523322  |
|    60 | mlp                           |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | mlp                           |     0.996757 |                              1.09137 |                               1.09229 |                             1.60649 |                              1.60304 |                        2788.92 |                         2792.42 |            0.00216216 |             0.0021692  |          0.0540541 |           0.0531453 |                            0.0583784 |                             0.0553145 |          0.00306384 |
|    62 | mlp                           |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | mlp                           |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | mlp                           |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | cnn1d                         |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | cnn1d                         |     0.977303 |                              1.31205 |                               1.32205 |                             1.6996  |                              1.61066 |                        3032.5  |                         3055.77 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0833333 |                            0.0881175 |                             0.0669399 |          0.0523322  |
|    60 | cnn1d                         |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | cnn1d                         |     0.996757 |                              1.09137 |                               1.09229 |                             1.60649 |                              1.60304 |                        2788.92 |                         2792.42 |            0.00216216 |             0.0021692  |          0.0540541 |           0.0531453 |                            0.0583784 |                             0.0553145 |          0.00306384 |
|    62 | cnn1d                         |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | cnn1d                         |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | cnn1d                         |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |
|    58 | gated_mixer                   |     0.958333 |                              1.42047 |                               1.44353 |                             2.16667 |                              2.07246 |                        3561.17 |                         3638.49 |            0.0277778  |             0.0289855  |          0.111111  |           0.0869565 |                            0.0833333 |                             0.0434783 |          0.0434783  |
|    59 | gated_mixer                   |     0.977303 |                              1.31205 |                               1.32205 |                             1.6996  |                              1.61066 |                        3032.5  |                         3055.77 |            0.0186916  |             0.0177596  |          0.0894526 |           0.0833333 |                            0.0881175 |                             0.0669399 |          0.0523322  |
|    60 | gated_mixer                   |     0.988778 |                              1.04942 |                               1.05217 |                             1.57731 |                              1.5372  |                        2836.37 |                         2845.01 |            0.00249377 |             0.00252207 |          0.0436409 |           0.0403531 |                            0.0685786 |                             0.0580076 |          0.025427   |
|    61 | gated_mixer                   |     0.996757 |                              1.09137 |                               1.09229 |                             1.60649 |                              1.60304 |                        2788.92 |                         2792.42 |            0.00216216 |             0.0021692  |          0.0540541 |           0.0531453 |                            0.0583784 |                             0.0553145 |          0.00306384 |
|    62 | gated_mixer                   |     0.988722 |                              1.15217 |                               1.14908 |                             1.43484 |                              1.39417 |                        2812.96 |                         2812.57 |            0.00877193 |             0.00760456 |          0.0714286 |           0.0671736 |                            0.0639098 |                             0.0532319 |          0.0283428  |
|    63 | gated_mixer                   |     0.972603 |                              1.44474 |                               1.44677 |                             1.81644 |                              1.72113 |                        3296.6  |                         3304.04 |            0.0219178  |             0.0169014  |          0.123288  |           0.121127  |                            0.10137   |                             0.0760563 |          0.0524717  |
|    65 | gated_mixer                   |     0.952381 |                              1.39258 |                               1.39049 |                             1.50794 |                              1.31667 |                        3078.13 |                         3105.83 |            0.015873   |             0.0166667  |          0.142857  |           0.133333  |                            0.0952381 |                             0.05      |          0.126842   |

## Hyperparameter CV and Controls

Model selection CV is grouped by training run.  Final claims use held-out analysis runs only.

| model       | feature_set       |   alpha |   fold |   sigma68_ns | candidate                                                     |   target_sigma68_ns |
|:------------|:------------------|--------:|-------:|-------------:|:--------------------------------------------------------------|--------------------:|
| traditional | amp_poly_by_stave |     0.1 |      1 |      2.12627 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      2 |      2.16174 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      3 |      2.41232 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      4 |      2.31143 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |     -1 |      2.25294 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      1 |      2.13706 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      2 |      2.15268 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      3 |      2.39568 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      4 |      2.3109  | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |     -1 |      2.24908 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      1 |      2.09173 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      2 |      2.13438 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      3 |      2.36553 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      4 |      2.28467 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |     -1 |      2.21908 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      1 |      2.21425 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      2 |      1.9922  | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      3 |      2.22021 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      4 |      2.10717 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |     -1 |      2.13346 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      1 |      2.05637 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      2 |      1.84519 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      3 |      1.95524 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      4 |      1.89407 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |     -1 |      1.93772 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      1 |      2.35254 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      2 |      1.97367 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      3 |      2.17266 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      4 |      2.29165 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |     -1 |      2.19763 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      1 |      2.35156 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      2 |      1.9725  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      3 |      2.17079 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      4 |      2.28985 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |     -1 |      2.19618 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      1 |      2.32353 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      2 |      1.94548 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      3 |      2.1598  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      4 |      2.29338 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |     -1 |      2.18055 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      1 |      2.2339  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      2 |      1.9076  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      3 |      2.06478 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      4 |      2.17506 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |     -1 |      2.09533 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      1 |      1.7867  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      2 |      1.56931 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      3 |      1.68363 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      4 |      1.75429 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |     -1 |      1.69848 | nan                                                           |           nan       |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 0.1}                                                |             1.6106  |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 0.1}                                                |             1.5817  |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 0.1}                                                |             1.78897 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 0.1}                                                |             1.64354 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 0.1}                                                |             1.6562  |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 1.0}                                                |             1.59318 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 1.0}                                                |             1.57758 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 1.0}                                                |             1.78019 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 1.0}                                                |             1.62894 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 1.0}                                                |             1.64497 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 10.0}                                               |             1.57329 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 10.0}                                               |             1.54048 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 10.0}                                               |             1.73249 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 10.0}                                               |             1.65227 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 10.0}                                               |             1.62463 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 100.0}                                              |             1.45333 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 100.0}                                              |             1.44139 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 100.0}                                              |             1.63923 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 100.0}                                              |             1.5727  |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 100.0}                                              |             1.52666 |
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
| shuffled_target_ridge_control     | {"alpha": 100.0, "model": "ridge", "score": 3.848638626337052}                                            |        20 |

## Systematics and Caveats

The analysis is raw-data anchored but conditional on the selected-pulse and all-hit definitions.  The abstention score intentionally avoids held-out residual labels and uses only the three preregistered B2 support atoms, with the acceptance threshold frozen on training runs.  The bootstrap quantifies finite held-out-run variation, not architecture-search multiplicity or future detector-state changes.  The PID and energy entries are support proxies only because no ROOT truth labels are available.  An abstention rule that narrows all-six residuals can still be unsuitable for physics adoption if it selectively removes important topology, so the support-preserving flag is a gate, not just a statistic.

## Verdict

The S04i B2-atom abstention winner is hgb, with retained all-six mean held-out-run sigma68 2.998 ns [2.720, 3.324], mean acceptance 0.976, and max support-proxy drift 0.047. The traditional explicit-timewalk abstention result gives 3.010 ns [2.878, 3.176]. The result supports B2 support-based abstention as a timing-quality boundary; it does not claim unconditional B2-inclusive timing adoption.

## Next Experiment

No novel follow-up ticket appended.



# S03q: Run64-only calibration acceptance gate

- **Ticket:** `1781065299.451.065636a1`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train production corrections on run 64 only; evaluate held-out Sample-II analysis runs 58-63 and 65; bootstrap by held-out run
- **Config:** `configs/s03q_1781065299_451_065636a1_run64_acceptance_gate.yaml`

## 0. Preregistered question

The question is whether a run64-only downstream timewalk calibration can be turned from a global veto into an atom-level acceptance rule. The tested atoms are held-out run, stave, amplitude bin, and waveform-shape bin. A support atom is accepted only when the winning run64-only correction is non-inferior to the best run64-only traditional comparator within the preregistered margin, does not increase the tail fraction beyond the margin, has controlled median bias, and has enough support. Other atoms are diagnostic-only.

## 1. Raw-ROOT reproduction gate

The selected-pulse counts were rebuilt directly from `h101/HRDv`. Baselines use samples 0-3 and selection requires baseline-subtracted amplitude above 1000 ADC.

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses         |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses    |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2                 |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4                 |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6                 |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8                 |           4506 |         4506 |       0 |           0 | True   |
| sample_ii_calib run64 selected_pulses |          14630 |        14630 |       0 |           0 | True   |

## 2. Estimand and equations

For event `e`, stave `s`, and raw pickoff `t0`, the geometry-corrected time is

`tau_{e,s} = t0_{e,s} - z_s v^{-1}`, with `v^{-1}=0.078 ns cm^{-1}`.

The supervised correction target is the same-pulse closure residual

`r_{e,s} = tau_{e,s} - (1/2) sum_{u != s} tau_{e,u}`

over B4, B6, and B8. A model estimates `f(x_{e,s})` from same-pulse features and applies `t_{e,s}=t0_{e,s}-f(x_{e,s})`. Held-out pair residuals use all B4-B6, B4-B8, and B6-B8 differences after the same geometry correction.

`sigma68 = (Q84(Delta tau) - Q16(Delta tau)) / 2`.

The benchmark delta is `Delta_m = sigma68(m) - sigma68(best traditional)`. Negative values favor the tested model.

## 3. Methods

The base pickoff is the run64-trained template-phase time. Traditional comparators are an amplitude-only analytic ridge timewalk model and a monotone amplitude-binned timewalk model, both trained on run 64 only. ML/NN methods are ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new gated dilated TCN. Same-pulse features include normalized waveform samples, amplitude summaries, template residual/correlation summaries, pretrigger samples, stave one-hot terms, and compact shape summaries. No event id, event order, held-out target, cross-stave time, or held-out run label is used as a model input.

Model audit:

| method                            | training_scope      |   n_features |   n_train_rows |   train_rmse_ns |
|:----------------------------------|:--------------------|-------------:|---------------:|----------------:|
| cnn1d_run64                       | run64_only          |           42 |            630 |         3.04159 |
| gated_tcn_new_run64               | run64_only          |           42 |            630 |         2.8118  |
| hgb_mixed_sample_i_run64_sentinel | sample_i_plus_run64 |           42 |           4410 |         1.52837 |
| hgb_run64                         | run64_only          |           42 |            630 |         1.10717 |
| hgb_shuffled_target_sentinel      | run64_only          |           42 |            630 |         2.29582 |
| mlp_run64                         | run64_only          |           42 |            630 |         1.42087 |
| ridge_run64                       | run64_only          |           42 |            630 |         1.56376 |
| run64_analytic_amp_only           | nan                 |            6 |            630 |       nan       |
| run64_monotone_binned_timewalk    | nan                 |            1 |            630 |       nan       |

## 4. Head-to-head benchmark

| method                            |   value |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   full_rms_ns |   full_rms_delta_vs_traditional_ns |   tail_frac_abs_gt5ns |   tail_delta_vs_traditional |   n_pair_residuals |
|:----------------------------------|--------:|---------:|----------:|--------------------------:|---------------:|----------------:|--------------:|-----------------------------------:|----------------------:|----------------------------:|-------------------:|
| run64_analytic_amp_only           | 1.40822 |  1.23614 |   1.72021 |                 0         |      0         |       0         |       2.62971 |                          0         |             0.0205934 |                  0          |              11460 |
| ridge_run64                       | 1.42056 |  1.30329 |   1.61196 |                 0.0123463 |     -0.0891175 |       0.0892596 |       2.5076  |                         -0.122116  |             0.0176265 |                 -0.00296684 |              11460 |
| hgb_mixed_sample_i_run64_sentinel | 1.43241 |  1.32251 |   1.63984 |                 0.0241931 |     -0.0918062 |       0.112479  |       2.40914 |                         -0.220577  |             0.0175393 |                 -0.0030541  |              11460 |
| hgb_run64                         | 1.46628 |  1.34731 |   1.58598 |                 0.0580638 |     -0.124134  |       0.173302  |       2.47557 |                         -0.154145  |             0.0147469 |                 -0.00584642 |              11460 |
| run64_monotone_binned_timewalk    | 1.52566 |  1.34099 |   1.84099 |                 0.117439  |      0.0555324 |       0.160741  |       2.68494 |                          0.0552297 |             0.0250436 |                  0.00445026 |              11460 |
| mlp_run64                         | 1.61592 |  1.49037 |   1.7516  |                 0.207703  |      0.051792  |       0.3239    |       2.47547 |                         -0.154248  |             0.0133508 |                 -0.00724258 |              11460 |
| gated_tcn_new_run64               | 2.17642 |  2.10975 |   2.22807 |                 0.768203  |      0.464313  |       0.98154   |       2.95818 |                          0.328469  |             0.0376091 |                  0.0170157  |              11460 |
| template_phase_base               | 2.35131 |  2.28197 |   2.53197 |                 0.943095  |      0.602896  |       1.29338   |       3.14254 |                          0.512821  |             0.0624782 |                  0.0418848  |              11460 |
| cnn1d_run64                       | 2.36629 |  2.26486 |   2.47763 |                 0.958074  |      0.626235  |       1.22893   |       3.12048 |                          0.490766  |             0.0487784 |                  0.028185   |              11460 |
| hgb_shuffled_target_sentinel      | 3.1118  |  3.00115 |   3.1949  |                 1.70359   |      1.30737   |       1.95363   |       3.57144 |                          0.941729  |             0.093281  |                  0.0726876  |              11460 |

Per-run benchmark:

|   heldout_run | method                            |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:----------------------------------|-------------:|--------------:|----------------------:|-------------------:|
|            58 | run64_analytic_amp_only           |     0.997697 |       2.64237 |            0.0228311  |                219 |
|            58 | run64_monotone_binned_timewalk    |     1.09099  |       2.70437 |            0.0228311  |                219 |
|            58 | ridge_run64                       |     1.17008  |       2.66387 |            0.0273973  |                219 |
|            58 | hgb_mixed_sample_i_run64_sentinel |     1.19853  |       2.76015 |            0.0273973  |                219 |
|            58 | hgb_run64                         |     1.21374  |       2.52843 |            0.0182648  |                219 |
|            58 | mlp_run64                         |     1.51039  |       2.47    |            0.0228311  |                219 |
|            58 | gated_tcn_new_run64               |     1.91482  |       3.00038 |            0.0593607  |                219 |
|            58 | template_phase_base               |     2.28197  |       3.34157 |            0.0639269  |                219 |
|            58 | cnn1d_run64                       |     2.37889  |       3.2125  |            0.0593607  |                219 |
|            58 | hgb_shuffled_target_sentinel      |     2.96922  |       3.86992 |            0.0958904  |                219 |
|            59 | run64_analytic_amp_only           |     1.34218  |       2.5382  |            0.017038   |               2289 |
|            59 | ridge_run64                       |     1.34328  |       2.45137 |            0.0152905  |               2289 |
|            59 | run64_monotone_binned_timewalk    |     1.34556  |       2.59324 |            0.0179118  |               2289 |
|            59 | hgb_mixed_sample_i_run64_sentinel |     1.36977  |       2.28797 |            0.0139799  |               2289 |
|            59 | hgb_run64                         |     1.40673  |       2.39206 |            0.0122324  |               2289 |
|            59 | mlp_run64                         |     1.49136  |       2.41687 |            0.0113587  |               2289 |
|            59 | gated_tcn_new_run64               |     2.22006  |       2.96339 |            0.0397554  |               2289 |
|            59 | cnn1d_run64                       |     2.48555  |       3.20472 |            0.0498034  |               2289 |
|            59 | template_phase_base               |     2.60131  |       3.14971 |            0.0712101  |               2289 |
|            59 | hgb_shuffled_target_sentinel      |     3.15312  |       3.61089 |            0.104849   |               2289 |
|            60 | run64_analytic_amp_only           |     1.2458   |       2.41839 |            0.0173267  |               2424 |
|            60 | ridge_run64                       |     1.29489  |       2.32746 |            0.0140264  |               2424 |
|            60 | hgb_mixed_sample_i_run64_sentinel |     1.33086  |       2.17857 |            0.015264   |               2424 |
|            60 | run64_monotone_binned_timewalk    |     1.34099  |       2.46562 |            0.0202145  |               2424 |
|            60 | hgb_run64                         |     1.45192  |       2.32485 |            0.0127888  |               2424 |
|            60 | mlp_run64                         |     1.61325  |       2.32771 |            0.0144389  |               2424 |
|            60 | gated_tcn_new_run64               |     2.2254   |       2.9121  |            0.0453795  |               2424 |
|            60 | template_phase_base               |     2.35131  |       3.111   |            0.084571   |               2424 |
|            60 | cnn1d_run64                       |     2.40975  |       3.05348 |            0.054868   |               2424 |
|            60 | hgb_shuffled_target_sentinel      |     3.15186  |       3.48106 |            0.089934   |               2424 |
|            61 | hgb_run64                         |     1.69221  |       2.70249 |            0.0196499  |               2799 |
|            61 | hgb_mixed_sample_i_run64_sentinel |     1.76614  |       2.68255 |            0.0253662  |               2799 |
|            61 | ridge_run64                       |     1.77758  |       2.76898 |            0.0257235  |               2799 |
|            61 | run64_analytic_amp_only           |     1.86401  |       2.92427 |            0.0317971  |               2799 |
|            61 | mlp_run64                         |     1.86453  |       2.68942 |            0.0175063  |               2799 |
|            61 | gated_tcn_new_run64               |     2.02379  |       2.93008 |            0.0300107  |               2799 |
|            61 | run64_monotone_binned_timewalk    |     2.02566  |       2.98813 |            0.0360843  |               2799 |
|            61 | cnn1d_run64                       |     2.16565  |       3.02972 |            0.0425152  |               2799 |
|            61 | template_phase_base               |     2.28197  |       3.09445 |            0.0392997  |               2799 |
|            61 | hgb_shuffled_target_sentinel      |     2.91946  |       3.49782 |            0.0735977  |               2799 |
|            62 | run64_analytic_amp_only           |     1.27615  |       2.56723 |            0.0136307  |               2421 |
|            62 | run64_monotone_binned_timewalk    |     1.34099  |       2.62095 |            0.0144568  |               2421 |
|            62 | ridge_run64                       |     1.36567  |       2.41286 |            0.0111524  |               2421 |
|            62 | hgb_mixed_sample_i_run64_sentinel |     1.40415  |       2.44948 |            0.0148699  |               2421 |
|            62 | hgb_run64                         |     1.40667  |       2.46892 |            0.0107394  |               2421 |
|            62 | mlp_run64                         |     1.56057  |       2.4741  |            0.00908715 |               2421 |
|            62 | gated_tcn_new_run64               |     2.22371  |       2.99424 |            0.0367617  |               2421 |
|            62 | cnn1d_run64                       |     2.39089  |       3.15538 |            0.0462619  |               2421 |
|            62 | template_phase_base               |     2.53197  |       3.16477 |            0.0772408  |               2421 |
|            62 | hgb_shuffled_target_sentinel      |     3.19705  |       3.62816 |            0.101611   |               2421 |
|            63 | run64_analytic_amp_only           |     1.16095  |       2.61427 |            0.0198198  |               1110 |
|            63 | hgb_run64                         |     1.26238  |       2.45958 |            0.0171171  |               1110 |
|            63 | hgb_mixed_sample_i_run64_sentinel |     1.26663  |       2.27306 |            0.0171171  |               1110 |
|            63 | run64_monotone_binned_timewalk    |     1.28421  |       2.66267 |            0.0198198  |               1110 |
|            63 | ridge_run64                       |     1.30811  |       2.51818 |            0.0198198  |               1110 |
|            63 | mlp_run64                         |     1.39284  |       2.408   |            0.0162162  |               1110 |
|            63 | gated_tcn_new_run64               |     2.22917  |       3.04078 |            0.0423423  |               1110 |
|            63 | cnn1d_run64                       |     2.53974  |       3.22207 |            0.054955   |               1110 |
|            63 | template_phase_base               |     2.60131  |       3.23253 |            0.0837838  |               1110 |
|            63 | hgb_shuffled_target_sentinel      |     3.27458  |       3.68017 |            0.115315   |               1110 |
|            65 | run64_monotone_binned_timewalk    |     1.12935  |       1.6806  |            0.010101   |                198 |
|            65 | run64_analytic_amp_only           |     1.17414  |       1.58601 |            0.00505051 |                198 |
|            65 | hgb_run64                         |     1.25688  |       1.46249 |            0.00505051 |                198 |
|            65 | ridge_run64                       |     1.27285  |       1.47029 |            0          |                198 |
|            65 | hgb_mixed_sample_i_run64_sentinel |     1.31042  |       1.71866 |            0.010101   |                198 |
|            65 | mlp_run64                         |     1.33325  |       1.5063  |            0          |                198 |
|            65 | gated_tcn_new_run64               |     2.00227  |       1.97137 |            0.010101   |                198 |
|            65 | cnn1d_run64                       |     2.34361  |       2.23799 |            0.030303   |                198 |
|            65 | template_phase_base               |     2.53197  |       2.33438 |            0.030303   |                198 |
|            65 | hgb_shuffled_target_sentinel      |     3.17594  |       2.95962 |            0.0909091  |                198 |

## 5. Acceptance gate

The winner accepts `9` of `46` support atoms, covering `0.291` of evaluated pulses. The gate is conservative: it requires at least `80` pulses per stave/amplitude/shape support atom, delta CI high <= `0.15` ns, tail fraction no more than `0.02` above traditional, absolute tail fraction <= `0.05`, full RMS <= `3.0` ns, and absolute median bias <= `1.0` ns.

| stave   |   amplitude_atom | shape_atom         |   n_pulses |   n_runs |   winner_sigma68_ns |   traditional_sigma68_ns |   delta_ci_low |   delta_ci_high |   winner_tail_frac_abs_gt5ns |   winner_median_bias_ns | decision        |
|:--------|-----------------:|:-------------------|-----------:|---------:|--------------------:|-------------------------:|---------------:|----------------:|-----------------------------:|------------------------:|:----------------|
| B6      |        1000_1500 | low_template_corr  |         90 |        7 |           0.0601625 |                0.0601625 |              0 |               0 |                   0.0111111  |               -0.783085 | accept          |
| B6      |        1500_2200 | low_template_corr  |        419 |        7 |           0.0367404 |                0.0367404 |              0 |               0 |                   0.0167064  |               -0.867141 | accept          |
| B6      |        1500_2200 | mid_template_corr  |        345 |        7 |           1.48068   |                1.48068   |              0 |               0 |                   0.0057971  |               -0.833254 | accept          |
| B6      |        2200_3200 | low_template_corr  |        645 |        7 |           0.017354  |                0.017354  |              0 |               0 |                   0.0108527  |               -0.868579 | accept          |
| B6      |        2200_3200 | mid_template_corr  |        746 |        7 |           1.2467    |                1.2467    |              0 |               0 |                   0.00670241 |               -0.865372 | accept          |
| B8      |        1500_2200 | mid_template_corr  |         92 |        7 |           1.45652   |                1.45652   |              0 |               0 |                   0.0108696  |               -0.447253 | accept          |
| B8      |        2200_3200 | high_template_corr |        412 |        7 |           1.24324   |                1.24324   |              0 |               0 |                   0.00970874 |               -0.969069 | accept          |
| B8      |        2200_3200 | mid_template_corr  |        428 |        7 |           1.12715   |                1.12715   |              0 |               0 |                   0.00700935 |               -0.963123 | accept          |
| B8      |        3200_4700 | high_template_corr |        157 |        7 |           0.99913   |                0.99913   |              0 |               0 |                   0.00636943 |               -0.956695 | accept          |
| B4      |        1000_1500 | high_template_corr |         52 |        6 |           1.95281   |                1.95281   |              0 |               0 |                   0          |                2.42863  | diagnostic_only |
| B4      |        1000_1500 | low_template_corr  |        224 |        7 |           0.0528682 |                0.0528682 |              0 |               0 |                   0.0133929  |                2.17834  | diagnostic_only |
| B4      |        1000_1500 | mid_template_corr  |         67 |        6 |           1.59215   |                1.59215   |              0 |               0 |                   0          |                2.67103  | diagnostic_only |
| B4      |        1500_2200 | high_template_corr |        367 |        7 |           1.49023   |                1.49023   |              0 |               0 |                   0          |                2.07356  | diagnostic_only |
| B4      |        1500_2200 | low_template_corr  |        449 |        7 |           0.0273446 |                0.0273446 |              0 |               0 |                   0.00445434 |                2.08046  | diagnostic_only |
| B4      |        1500_2200 | mid_template_corr  |        355 |        7 |           1.49728   |                1.49728   |              0 |               0 |                   0.0056338  |                2.56777  | diagnostic_only |
| B4      |        2200_3200 | high_template_corr |        851 |        7 |           1.36159   |                1.36159   |              0 |               0 |                   0.00117509 |                2.06583  | diagnostic_only |
| B4      |        2200_3200 | low_template_corr  |        514 |        7 |           0.0171149 |                0.0171149 |              0 |               0 |                   0.0194553  |                2.05702  | diagnostic_only |
| B4      |        2200_3200 | mid_template_corr  |        794 |        7 |           1.36971   |                1.36971   |              0 |               0 |                   0.00377834 |                2.30275  | diagnostic_only |
| B4      |        3200_4700 | high_template_corr |          7 |        3 |           1.53425   |                1.53425   |              0 |               0 |                   0          |                1.56001  | diagnostic_only |
| B4      |        3200_4700 | low_template_corr  |         43 |        6 |           6.08011   |                6.08011   |              0 |               0 |                   0.44186    |                2.09547  | diagnostic_only |
| B4      |        3200_4700 | mid_template_corr  |         76 |        7 |           1.89482   |                1.89482   |              0 |               0 |                   0.131579   |                2.41769  | diagnostic_only |
| B4      |        4700_6800 | low_template_corr  |         10 |        5 |           6.03482   |                6.03482   |              0 |               0 |                   0.5        |                2.16018  | diagnostic_only |
| B4      |        4700_6800 | mid_template_corr  |         10 |        5 |          13.2154    |               13.2154    |              0 |               0 |                   0.6        |                0.44986  | diagnostic_only |
| B4      |       6800_10000 | low_template_corr  |          1 |        1 |           0         |                0         |              0 |               0 |                   0          |               32.1901   | diagnostic_only |
| B6      |        1000_1500 | high_template_corr |         55 |        6 |           1.65743   |                1.65743   |              0 |               0 |                   0          |               -1.25215  | diagnostic_only |
| B6      |        1000_1500 | mid_template_corr  |         43 |        7 |           1.29202   |                1.29202   |              0 |               0 |                   0          |               -0.772341 | diagnostic_only |
| B6      |        1500_2200 | high_template_corr |        340 |        7 |           1.49253   |                1.49253   |              0 |               0 |                   0.00882353 |               -1.08029  | diagnostic_only |
| B6      |        2200_3200 | high_template_corr |        838 |        7 |           1.25689   |                1.25689   |              0 |               0 |                   0.00835322 |               -1.11056  | diagnostic_only |
| B6      |        3200_4700 | high_template_corr |         31 |        5 |           1.18011   |                1.18011   |              0 |               0 |                   0          |               -1.0996   | diagnostic_only |
| B6      |        3200_4700 | low_template_corr  |         75 |        7 |           0.0217061 |                0.0217061 |              0 |               0 |                   0.146667   |               -0.858942 | diagnostic_only |
| B6      |        3200_4700 | mid_template_corr  |        186 |        6 |           1.17925   |                1.17925   |              0 |               0 |                   0.0322581  |               -1.10866  | diagnostic_only |
| B6      |        4700_6800 | low_template_corr  |          3 |        2 |           0.512972  |                0.512972  |              0 |               0 |                   0          |               -0.831301 | diagnostic_only |
| B6      |        4700_6800 | mid_template_corr  |          3 |        3 |           6.095     |                6.095     |              0 |               0 |                   0.333333   |                3.42166  | diagnostic_only |
| B6      |       6800_10000 | mid_template_corr  |          1 |        1 |           0         |                0         |              0 |               0 |                   0          |               -7.02679  | diagnostic_only |
| B8      |        1000_1500 | high_template_corr |         21 |        6 |           1.44771   |                1.44771   |              0 |               0 |                   0          |               -1.09409  | diagnostic_only |
| B8      |        1000_1500 | low_template_corr  |         39 |        7 |           0.124232  |                0.124232  |              0 |               0 |                   0.0769231  |               -1.108    | diagnostic_only |
| B8      |        1000_1500 | mid_template_corr  |         34 |        6 |           1.29534   |                1.29534   |              0 |               0 |                   0.0588235  |               -1.73874  | diagnostic_only |
| B8      |        1500_2200 | high_template_corr |         66 |        7 |           1.27056   |                1.27056   |              0 |               0 |                   0          |               -1.15845  | diagnostic_only |
| B8      |        1500_2200 | low_template_corr  |        145 |        7 |           0.0705063 |                0.0705063 |              0 |               0 |                   0.0275862  |               -1.25172  | diagnostic_only |
| B8      |        2200_3200 | low_template_corr  |        433 |        7 |           0.0444092 |                0.0444092 |              0 |               0 |                   0.00692841 |               -1.23319  | diagnostic_only |
| B8      |        3200_4700 | low_template_corr  |        472 |        7 |           0.0271447 |                0.0271447 |              0 |               0 |                   0.0275424  |               -1.20536  | diagnostic_only |
| B8      |        3200_4700 | mid_template_corr  |       1034 |        7 |           1.23262   |                1.23262   |              0 |               0 |                   0.0135397  |               -1.20295  | diagnostic_only |
| B8      |        4700_6800 | low_template_corr  |        165 |        7 |           0.103811  |                0.103811  |              0 |               0 |                   0.0181818  |               -1.15417  | diagnostic_only |
| B8      |        4700_6800 | mid_template_corr  |        310 |        6 |           1.41654   |                1.41654   |              0 |               0 |                   0.0129032  |               -3.65839  | diagnostic_only |
| B8      |       6800_10000 | low_template_corr  |          4 |        4 |           1.57613   |                1.57613   |              0 |               0 |                   0.25       |               -1.07657  | diagnostic_only |
| B8      |       6800_10000 | mid_template_corr  |          8 |        4 |           0.71388   |                0.71388   |              0 |               0 |                   0.125      |               -6.08121  | diagnostic_only |

Run/stave/amplitude/shape diagnostic table excerpt:

|   run | stave   |   amplitude_atom | shape_atom         | method                            |   n_pulses |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|------:|:--------|-----------------:|:-------------------|:----------------------------------|-----------:|-------------:|--------------:|----------------------:|
|    58 | B4      |        1000_1500 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          6 |   2.41318    |     8.17538   |             0.166667  |
|    58 | B4      |        1000_1500 | low_template_corr  | hgb_shuffled_target_sentinel      |          6 |   3.2715     |     9.53958   |             0.166667  |
|    58 | B4      |        1000_1500 | low_template_corr  | run64_analytic_amp_only           |          6 |   2.33681    |     8.62389   |             0.166667  |
|    58 | B4      |        1500_2200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          3 |   1.21382    |     1.45752   |             0         |
|    58 | B4      |        1500_2200 | high_template_corr | hgb_shuffled_target_sentinel      |          3 |   1.6846     |     2.29587   |             0         |
|    58 | B4      |        1500_2200 | high_template_corr | run64_analytic_amp_only           |          3 |   1.85959    |     2.24541   |             0         |
|    58 | B4      |        1500_2200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         17 |   0.238553   |     1.64619   |             0.0588235 |
|    58 | B4      |        1500_2200 | low_template_corr  | hgb_shuffled_target_sentinel      |         17 |   1.82202    |     1.77652   |             0         |
|    58 | B4      |        1500_2200 | low_template_corr  | run64_analytic_amp_only           |         17 |   0.0290535  |     0.0334808 |             0         |
|    58 | B4      |        1500_2200 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          4 |   0.888772   |     1.05672   |             0         |
|    58 | B4      |        1500_2200 | mid_template_corr  | hgb_shuffled_target_sentinel      |          4 |   1.62126    |     2.14386   |             0         |
|    58 | B4      |        1500_2200 | mid_template_corr  | run64_analytic_amp_only           |          4 |   1.237      |     1.44459   |             0         |
|    58 | B4      |        2200_3200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |         12 |   0.467496   |     0.877433  |             0         |
|    58 | B4      |        2200_3200 | high_template_corr | hgb_shuffled_target_sentinel      |         12 |   1.37746    |     1.51121   |             0         |
|    58 | B4      |        2200_3200 | high_template_corr | run64_analytic_amp_only           |         12 |   0.685655   |     1.15683   |             0         |
|    58 | B4      |        2200_3200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         18 |   0.156582   |     0.165388  |             0         |
|    58 | B4      |        2200_3200 | low_template_corr  | hgb_shuffled_target_sentinel      |         18 |   1.2678     |     1.16117   |             0         |
|    58 | B4      |        2200_3200 | low_template_corr  | run64_analytic_amp_only           |         18 |   0.00960679 |     0.0109828 |             0         |
|    58 | B4      |        2200_3200 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          9 |   0.506087   |     0.466284  |             0         |
|    58 | B4      |        2200_3200 | mid_template_corr  | hgb_shuffled_target_sentinel      |          9 |   1.36764    |     1.32527   |             0         |
|    58 | B4      |        2200_3200 | mid_template_corr  | run64_analytic_amp_only           |          9 |   0.592821   |     0.704321  |             0         |
|    58 | B4      |        3200_4700 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B4      |        3200_4700 | low_template_corr  | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B4      |        3200_4700 | low_template_corr  | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B4      |        3200_4700 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          2 |   3.58211    |     5.26781   |             1         |
|    58 | B4      |        3200_4700 | mid_template_corr  | hgb_shuffled_target_sentinel      |          2 |   1.7741     |     2.60897   |             0         |
|    58 | B4      |        3200_4700 | mid_template_corr  | run64_analytic_amp_only           |          2 |   2.63077    |     3.86877   |             0         |
|    58 | B4      |        4700_6800 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B4      |        4700_6800 | mid_template_corr  | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B4      |        4700_6800 | mid_template_corr  | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B6      |        1000_1500 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B6      |        1000_1500 | high_template_corr | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B6      |        1000_1500 | high_template_corr | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B6      |        1000_1500 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          3 |   0.505949   |     0.631962  |             0         |
|    58 | B6      |        1000_1500 | low_template_corr  | hgb_shuffled_target_sentinel      |          3 |   0.157977   |     0.21712   |             0         |
|    58 | B6      |        1000_1500 | low_template_corr  | run64_analytic_amp_only           |          3 |   0.0790353  |     0.0956706 |             0         |
|    58 | B6      |        1000_1500 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B6      |        1000_1500 | mid_template_corr  | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B6      |        1000_1500 | mid_template_corr  | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B6      |        1500_2200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          2 |   0.0177249  |     0.0260661 |             0         |
|    58 | B6      |        1500_2200 | high_template_corr | hgb_shuffled_target_sentinel      |          2 |   0.22345    |     0.328604  |             0         |
|    58 | B6      |        1500_2200 | high_template_corr | run64_analytic_amp_only           |          2 |   0.26723    |     0.392985  |             0         |
|    58 | B6      |        1500_2200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         15 |   0.196205   |     1.03646   |             0         |
|    58 | B6      |        1500_2200 | low_template_corr  | hgb_shuffled_target_sentinel      |         15 |   1.3417     |     1.33848   |             0         |
|    58 | B6      |        1500_2200 | low_template_corr  | run64_analytic_amp_only           |         15 |   0.0301829  |     0.0369573 |             0         |
|    58 | B6      |        1500_2200 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B6      |        1500_2200 | mid_template_corr  | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B6      |        1500_2200 | mid_template_corr  | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B6      |        2200_3200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |         12 |   1.59603    |     1.31018   |             0         |
|    58 | B6      |        2200_3200 | high_template_corr | hgb_shuffled_target_sentinel      |         12 |   1.82704    |     2.52201   |             0.0833333 |
|    58 | B6      |        2200_3200 | high_template_corr | run64_analytic_amp_only           |         12 |   1.7296     |     1.94891   |             0.0833333 |
|    58 | B6      |        2200_3200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         21 |   0.168376   |     0.220197  |             0         |
|    58 | B6      |        2200_3200 | low_template_corr  | hgb_shuffled_target_sentinel      |         21 |   1.13522    |     1.04328   |             0         |
|    58 | B6      |        2200_3200 | low_template_corr  | run64_analytic_amp_only           |         21 |   0.012189   |     0.019318  |             0         |
|    58 | B6      |        2200_3200 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          9 |   0.842618   |     3.88247   |             0.222222  |
|    58 | B6      |        2200_3200 | mid_template_corr  | hgb_shuffled_target_sentinel      |          9 |   2.24847    |     3.76404   |             0.111111  |
|    58 | B6      |        2200_3200 | mid_template_corr  | run64_analytic_amp_only           |          9 |   0.854839   |     3.3203    |             0.111111  |
|    58 | B6      |        3200_4700 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B6      |        3200_4700 | high_template_corr | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B6      |        3200_4700 | high_template_corr | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B6      |        3200_4700 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          2 |   0.163892   |     0.241018  |             0         |
|    58 | B6      |        3200_4700 | low_template_corr  | hgb_shuffled_target_sentinel      |          2 |   0.44996    |     0.661706  |             0         |
|    58 | B6      |        3200_4700 | low_template_corr  | run64_analytic_amp_only           |          2 |   0.00732224 |     0.010768  |             0         |
|    58 | B6      |        3200_4700 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          5 |   1.27506    |     1.25348   |             0         |
|    58 | B6      |        3200_4700 | mid_template_corr  | hgb_shuffled_target_sentinel      |          5 |   2.11557    |     1.93664   |             0         |
|    58 | B6      |        3200_4700 | mid_template_corr  | run64_analytic_amp_only           |          5 |   1.14015    |     1.18624   |             0         |
|    58 | B8      |        1000_1500 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          2 |   0.0211263  |     0.031068  |             0         |
|    58 | B8      |        1000_1500 | low_template_corr  | hgb_shuffled_target_sentinel      |          2 |   0.43064    |     0.633295  |             0         |
|    58 | B8      |        1000_1500 | low_template_corr  | run64_analytic_amp_only           |          2 |   0.0413535  |     0.0608139 |             0         |
|    58 | B8      |        1000_1500 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          2 |   1.11395    |     1.63816   |             0         |
|    58 | B8      |        1000_1500 | mid_template_corr  | hgb_shuffled_target_sentinel      |          2 |   1.23967    |     1.82305   |             0         |
|    58 | B8      |        1000_1500 | mid_template_corr  | run64_analytic_amp_only           |          2 |   0.890696   |     1.30985   |             0         |
|    58 | B8      |        1500_2200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B8      |        1500_2200 | high_template_corr | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B8      |        1500_2200 | high_template_corr | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B8      |        1500_2200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          3 |   0.074134   |     0.0892491 |             0         |
|    58 | B8      |        1500_2200 | low_template_corr  | hgb_shuffled_target_sentinel      |          3 |   0.809546   |     0.978401  |             0         |
|    58 | B8      |        1500_2200 | low_template_corr  | run64_analytic_amp_only           |          3 |   0.0149415  |     0.0181845 |             0         |
|    58 | B8      |        1500_2200 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          3 |   4.43837    |     5.75597   |             0.333333  |
|    58 | B8      |        1500_2200 | mid_template_corr  | hgb_shuffled_target_sentinel      |          3 |   5.10724    |     6.52956   |             0.333333  |
|    58 | B8      |        1500_2200 | mid_template_corr  | run64_analytic_amp_only           |          3 |   4.55351    |     6.09011   |             0.333333  |
|    58 | B8      |        2200_3200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          3 |   0.978534   |     1.20727   |             0         |
|    58 | B8      |        2200_3200 | high_template_corr | hgb_shuffled_target_sentinel      |          3 |   1.45809    |     1.83956   |             0         |
|    58 | B8      |        2200_3200 | high_template_corr | run64_analytic_amp_only           |          3 |   0.851024   |     1.08076   |             0         |
|    58 | B8      |        2200_3200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         14 |   0.193215   |     0.257219  |             0         |
|    58 | B8      |        2200_3200 | low_template_corr  | hgb_shuffled_target_sentinel      |         14 |   1.42752    |     1.4377    |             0         |
|    58 | B8      |        2200_3200 | low_template_corr  | run64_analytic_amp_only           |         14 |   0.0226599  |     0.0321507 |             0         |
|    58 | B8      |        2200_3200 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          5 |   1.53677    |     2.5074    |             0.2       |
|    58 | B8      |        2200_3200 | mid_template_corr  | hgb_shuffled_target_sentinel      |          5 |   1.16058    |     1.13952   |             0         |
|    58 | B8      |        2200_3200 | mid_template_corr  | run64_analytic_amp_only           |          5 |   1.2097     |     1.59403   |             0         |
|    58 | B8      |        3200_4700 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |          1 |   0          |     0         |             0         |
|    58 | B8      |        3200_4700 | high_template_corr | hgb_shuffled_target_sentinel      |          1 |   0          |     0         |             0         |
|    58 | B8      |        3200_4700 | high_template_corr | run64_analytic_amp_only           |          1 |   0          |     0         |             0         |
|    58 | B8      |        3200_4700 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         17 |   0.165568   |     0.68497   |             0         |
|    58 | B8      |        3200_4700 | low_template_corr  | hgb_shuffled_target_sentinel      |         17 |   1.75319    |     1.66076   |             0         |
|    58 | B8      |        3200_4700 | low_template_corr  | run64_analytic_amp_only           |         17 |   0.0371706  |     0.0406057 |             0         |
|    58 | B8      |        3200_4700 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |         12 |   1.163      |     0.982737  |             0         |
|    58 | B8      |        3200_4700 | mid_template_corr  | hgb_shuffled_target_sentinel      |         12 |   1.59963    |     1.81687   |             0         |
|    58 | B8      |        3200_4700 | mid_template_corr  | run64_analytic_amp_only           |         12 |   1.06085    |     1.08151   |             0         |
|    58 | B8      |        4700_6800 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |          6 |   0.271915   |     0.374136  |             0         |
|    58 | B8      |        4700_6800 | low_template_corr  | hgb_shuffled_target_sentinel      |          6 |   1.98395    |     2.10567   |             0         |
|    58 | B8      |        4700_6800 | low_template_corr  | run64_analytic_amp_only           |          6 |   0.172128   |     0.540926  |             0         |
|    58 | B8      |        4700_6800 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |          4 |   1.04793    |     1.39357   |             0         |
|    58 | B8      |        4700_6800 | mid_template_corr  | hgb_shuffled_target_sentinel      |          4 |   0.90581    |     1.08737   |             0         |
|    58 | B8      |        4700_6800 | mid_template_corr  | run64_analytic_amp_only           |          4 |   0.566783   |     0.617793  |             0         |
|    59 | B4      |        1000_1500 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |         15 |   0.713167   |     1.20561   |             0         |
|    59 | B4      |        1000_1500 | high_template_corr | hgb_shuffled_target_sentinel      |         15 |   1.01206    |     1.18239   |             0         |
|    59 | B4      |        1000_1500 | high_template_corr | run64_analytic_amp_only           |         15 |   1.05306    |     1.34901   |             0         |
|    59 | B4      |        1000_1500 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         44 |   0.437565   |     0.531892  |             0         |
|    59 | B4      |        1000_1500 | low_template_corr  | hgb_shuffled_target_sentinel      |         44 |   1.46169    |     1.42686   |             0         |
|    59 | B4      |        1000_1500 | low_template_corr  | run64_analytic_amp_only           |         44 |   0.0476599  |     0.0518612 |             0         |
|    59 | B4      |        1000_1500 | mid_template_corr  | hgb_mixed_sample_i_run64_sentinel |         19 |   1.0236     |     1.12809   |             0         |
|    59 | B4      |        1000_1500 | mid_template_corr  | hgb_shuffled_target_sentinel      |         19 |   1.42187    |     1.65362   |             0         |
|    59 | B4      |        1000_1500 | mid_template_corr  | run64_analytic_amp_only           |         19 |   1.42808    |     1.42939   |             0         |
|    59 | B4      |        1500_2200 | high_template_corr | hgb_mixed_sample_i_run64_sentinel |        118 |   1.24254    |     1.22584   |             0         |
|    59 | B4      |        1500_2200 | high_template_corr | hgb_shuffled_target_sentinel      |        118 |   1.79325    |     1.99631   |             0.0254237 |
|    59 | B4      |        1500_2200 | high_template_corr | run64_analytic_amp_only           |        118 |   1.30219    |     1.52817   |             0         |
|    59 | B4      |        1500_2200 | low_template_corr  | hgb_mixed_sample_i_run64_sentinel |         94 |   0.122291   |     0.261951  |             0         |
|    59 | B4      |        1500_2200 | low_template_corr  | hgb_shuffled_target_sentinel      |         94 |   1.21709    |     1.37534   |             0         |
|    59 | B4      |        1500_2200 | low_template_corr  | run64_analytic_amp_only           |         94 |   0.0251852  |     0.0308734 |             0         |

False-accept controls:

| sentinel_method                   |   accepted_atoms |   tested_atoms |   false_accept_rate |
|:----------------------------------|-----------------:|---------------:|--------------------:|
| hgb_shuffled_target_sentinel      |                0 |             46 |           0         |
| hgb_mixed_sample_i_run64_sentinel |                4 |             46 |           0.0869565 |

## 6. Leakage, systematics, and caveats

| check                                          |     value | pass   | detail                                                                                    |
|:-----------------------------------------------|----------:|:-------|:------------------------------------------------------------------------------------------|
| production_train_heldout_run_overlap           | 0         | True   | production corrections train on run64 and evaluate on disjoint runs 58-63,65              |
| feature_audit_no_event_order_cross_stave_time  | 0         | True   | features are same-pulse waveform/amplitude/template/pretrigger/stave/shape summaries only |
| shuffled_target_worse_than_winner_sigma68_ns   | 1.70359   | True   | shuffled run64 target should not beat the selected production winner                      |
| mixed_calibration_sentinel_not_used_for_winner | 0.0241931 | True   | Sample-I plus run64 fit is a sentinel, not an eligible production method                  |
| raw_reproduction_all_pass                      | 1         | True   | S00, Sample-II analysis, and run64 count gates pass exactly                               |

The dominant systematic is calibration transfer from a single calibration run to neighboring Sample-II analysis runs. The run-block bootstrap captures between-run variability but has only seven held-out units, so interval endpoints are coarse. The per-atom gate uses run-block intervals for stave/amplitude/shape support atoms and reports the run-resolved atom table separately; individual run atoms should be treated as diagnostic when support is small. The residual target is an internal same-particle closure residual rather than an external clock truth. The mixed-calibration sentinel is not a production candidate; it is included because earlier work found that mixed Sample-I/run64 calibration can look plausible internally while degrading Sample-II portability.

## 7. Verdict

The named winner in `result.json` is **run64_analytic_amp_only** with pooled pairwise sigma68 `1.408 ns` and CI `[1.236, 1.720] ns`.
The best traditional comparator is **run64_analytic_amp_only** with sigma68 `1.408 ns`.
Overall verdict: `run64_only_accept_with_atom_gate`.

## 8. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s03q_1781065299_451_065636a1_run64_acceptance_gate.py --config configs/s03q_1781065299_451_065636a1_run64_acceptance_gate.yaml
```

Artifacts: `reproduction_match_table.csv`, `traditional_scan_metrics.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `pulse_atom_metrics.csv`, `atom_acceptance_gate.csv`, `false_accept_controls.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

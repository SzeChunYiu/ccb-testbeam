# S03p: HGB transfer feature-leakage null grid

- **Ticket:** `1781062439.500.63591f99`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train on Sample I runs 31-37, 39-42, and 44-57; blind evaluation on Sample II analysis runs 58-63 and 65
- **Config:** `configs/s03p_1781062439_500_63591f99_hgb_feature_leakage_null_grid.yaml`
- **Primary metric:** held-out Sample-II pair-residual `sigma68` at 2 cm spacing, with held-out-run bootstrap 95% CIs

## 0. Question and preregistration

The preregistered question is whether the blind Sample-I to Sample-II HGB timewalk gain survives after removing potentially leaky feature families one at a time: pretrigger, amplitude, q-template, stave, and run-family atoms. The traditional comparators are the signed inverse-amplitude S03a analytic model and the S03b monotone binned timewalk. The ML/null panel contains HGB feature dropouts, ridge, MLP, 1D-CNN, a gated dilated-TCN architecture, a shuffled-target HGB sentinel, and a run-family-only sentinel.

The claim would be falsified if `hgb_all` no longer beat `analytic_timewalk`, if any single family removal erased the HGB gain, or if the shuffled-target/run-family-only sentinels matched the HGB result. Familywise interpretation uses Bonferroni alpha `0.05 / 6` = `0.0083` for the 6 HGB feature-family tests; the report still shows unadjusted 95% intervals for readability.

## 1. Raw-ROOT reproduction gate

The selected-pulse counts were rebuilt directly from `HRDv` in the raw ROOT files before model fitting. Baselines use samples 0-3, the B-stack channels are B2/B4/B6/B8 = 0/2/4/6, and selection is baseline-subtracted amplitude above 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

A run-65 S03 reference gate was also rebuilt from the raw-derived downstream pulse table:

| method               |   value |   reference_value |     delta_ns |   n_pair_residuals | pass   |
|:---------------------|--------:|------------------:|-------------:|-------------------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |  0           |                198 | True   |
| analytic_timewalk    | 1.49464 |           1.49464 | -7.32747e-15 |                198 | True   |
| s03b_binned_timewalk | 1.56958 |           1.56958 |  0           |                198 | True   |

## 2. Estimand and equations

For event `e`, stave `s`, and base pickoff `t0`, the geometry-corrected time is

`tau_{e,s} = t0_{e,s} - z_s v^{-1}`, with `v^{-1}=0.078 ns cm^{-1}`.

The supervised residual target for pulse `(e,s)` is

`r_{e,s} = tau_{e,s} - (1/2) sum_{u != s} tau_{e,u}`

over the other two downstream staves B4, B6, and B8. A correction model estimates `f(x_{e,s})` from same-pulse features on Sample I only and the corrected time is

`t_{e,s} = t0_{e,s} - f(x_{e,s})`.

The held-out residuals are pair differences after geometry correction, and

`sigma68 = (Q84({Delta tau_ab}) - Q16({Delta tau_ab})) / 2`.

The benchmark delta is `Delta_m = sigma68(m) - sigma68(analytic_timewalk)`. Negative values favor the tested model.

## 3. Methods

Templates and all fitted corrections are trained only on Sample I. The S03a analytic model selects among amplitude-only, amplitude/shape, and stave-interaction Ridge designs by GroupKFold over Sample-I runs. The S03b comparator selects a monotone amplitude-binned model. HGB uses grouped CV over Sample-I runs and then a fixed final training cap of `22000` rows to keep the fit deterministic and laptop-safe. Ridge, MLP, 1D-CNN, and the new TCN share the same train/evaluation split and target.

Feature families are same-pulse normalized waveform samples; amplitude summaries; q-template residual/correlation summaries; pretrigger samples and slope; stave one-hot; run-family one-hot; and extra shape summaries. No event id, run number, event order, cross-stave time, pair residual, Sample-II target, or downstream consumer label is used as a feature.

Model fit audit:

| method                       | families                                                              |   n_features |   n_train_rows |
|:-----------------------------|:----------------------------------------------------------------------|-------------:|---------------:|
| cnn1d_all                    | waveform,amplitude,q_template,pretrigger,stave,run_family,shape_extra |           45 |           3780 |
| hgb_all                      | waveform,amplitude,q_template,pretrigger,stave,run_family,shape_extra |           45 |           3780 |
| hgb_amplitude_only_control   | amplitude                                                             |            5 |           3780 |
| hgb_no_amplitude             | waveform,q_template,pretrigger,stave,run_family,shape_extra           |           40 |           3780 |
| hgb_no_pretrigger            | waveform,amplitude,q_template,stave,run_family,shape_extra            |           38 |           3780 |
| hgb_no_q_template            | waveform,amplitude,pretrigger,stave,run_family,shape_extra            |           42 |           3780 |
| hgb_no_run_family            | waveform,amplitude,q_template,pretrigger,stave,shape_extra            |           42 |           3780 |
| hgb_no_stave                 | waveform,amplitude,q_template,pretrigger,run_family,shape_extra       |           42 |           3780 |
| hgb_no_waveform              | amplitude,q_template,pretrigger,stave,run_family,shape_extra          |           27 |           3780 |
| hgb_run_family_only_sentinel | run_family                                                            |            3 |           3780 |
| hgb_shuffled_target_sentinel | waveform,amplitude,q_template,pretrigger,stave,run_family,shape_extra |           45 |           3780 |
| mlp_all                      | waveform,amplitude,q_template,pretrigger,stave,run_family,shape_extra |           45 |           3780 |
| ridge_all                    | waveform,amplitude,q_template,pretrigger,stave,run_family,shape_extra |           45 |           3780 |
| tcn_new_architecture_all     | waveform,amplitude,q_template,pretrigger,stave,run_family,shape_extra |           45 |           3780 |

## 4. Head-to-head benchmark

| method                       |   value |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:-----------------------------|--------:|---------:|----------:|--------------------------:|---------------:|----------------:|--------------:|----------------:|-----------:|----------------------:|-------------------:|
| hgb_no_amplitude             | 1.30395 |  1.21805 |   1.47098 |                -0.190719  |    -0.24053    |      -0.136003  |       2.46792 |        1.66868  |   87.7071  |             0.0164921 |              11460 |
| hgb_all                      | 1.3625  |  1.25889 |   1.48644 |                -0.132165  |    -0.202285   |      -0.0605006 |       2.45462 |        1.64902  |   72.2623  |             0.0170157 |              11460 |
| hgb_no_run_family            | 1.36435 |  1.2607  |   1.46573 |                -0.130316  |    -0.226219   |      -0.0794954 |       2.44653 |        1.65448  |   71.8934  |             0.0170157 |              11460 |
| hgb_no_pretrigger            | 1.36931 |  1.26984 |   1.50433 |                -0.125355  |    -0.210098   |      -0.0679548 |       2.44845 |        1.64683  |   73.9643  |             0.0165794 |              11460 |
| hgb_no_q_template            | 1.38295 |  1.2842  |   1.50668 |                -0.111719  |    -0.21567    |      -0.0474022 |       2.4321  |        1.65632  |   72.2045  |             0.0151832 |              11460 |
| hgb_no_waveform              | 1.38646 |  1.25357 |   1.49137 |                -0.108202  |    -0.175307   |      -0.0575147 |       2.43626 |        1.63735  |   70.2973  |             0.0151832 |              11460 |
| s03b_binned_timewalk         | 1.39797 |  1.18778 |   1.5     |                -0.096695  |    -0.223157   |      -0.0859718 |       2.70304 |        1.54699  |  193.294   |             0.0356021 |              11460 |
| analytic_timewalk            | 1.49467 |  1.3744  |   1.67387 |                 0         |     0          |       0         |       2.68147 |        1.50648  |  134.216   |             0.0207679 |              11460 |
| ridge_all                    | 1.55194 |  1.4803  |   1.63964 |                 0.0572693 |    -0.046377   |       0.150433  |       2.62177 |        1.46885  |   46.5678  |             0.0168412 |              11460 |
| mlp_all                      | 1.5822  |  1.48002 |   1.68951 |                 0.0875287 |     0.00814581 |       0.138036  |       2.49188 |        1.54922  |   15.6923  |             0.0149215 |              11460 |
| cnn1d_all                    | 1.65128 |  1.56089 |   1.72867 |                 0.156614  |    -0.0500593  |       0.345271  |       3.05385 |        1.06153  |   12.7752  |             0.0653578 |              11460 |
| tcn_new_architecture_all     | 1.88785 |  1.82925 |   1.96046 |                 0.393183  |     0.161906   |       0.578915  |       3.15995 |        1.84105  |   67.3225  |             0.0812391 |              11460 |
| template_phase_base          | 2.04594 |  1.79594 |   2.04594 |                 0.551276  |     0.35305    |       0.673208  |       3.36203 |        0.781805 |  229.847   |             0.0997382 |              11460 |
| hgb_run_family_only_sentinel | 2.04594 |  1.79594 |   2.04594 |                 0.551276  |     0.387319   |       0.669811  |       3.36203 |        0.781805 |  229.847   |             0.0997382 |              11460 |
| hgb_no_stave                 | 2.32096 |  2.17069 |   2.39552 |                 0.826289  |     0.456009   |       1.01719   |       3.05889 |        2.28512  |    5.45028 |             0.0514834 |              11460 |
| hgb_shuffled_target_sentinel | 2.38909 |  2.3152  |   2.48044 |                 0.894427  |     0.632692   |       1.09438   |       3.5077  |        3.05902  |   84.1282  |             0.10986   |              11460 |
| hgb_amplitude_only_control   | 2.5309  |  2.42152 |   2.65379 |                 1.03623   |     0.741993   |       1.26952   |       3.26823 |        2.03923  |   11.8621  |             0.0743455 |              11460 |

Per-run held-out scores:

|   heldout_run | method                       |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:-----------------------------|-------------:|--------------:|----------------------:|-------------------:|
|            58 | s03b_binned_timewalk         |     0.897972 |       1.42503 |            0.00913242 |                219 |
|            58 | hgb_no_amplitude             |     1.19776  |       1.71327 |            0.0136986  |                219 |
|            58 | hgb_no_waveform              |     1.24395  |       1.6307  |            0.0182648  |                219 |
|            58 | hgb_no_run_family            |     1.24537  |       1.6908  |            0.0182648  |                219 |
|            58 | hgb_no_q_template            |     1.25811  |       1.64062 |            0.0136986  |                219 |
|            58 | hgb_all                      |     1.26103  |       1.69144 |            0.0182648  |                219 |
|            58 | hgb_no_pretrigger            |     1.27404  |       1.70245 |            0.0182648  |                219 |
|            58 | ridge_all                    |     1.3103   |       1.54116 |            0.00913242 |                219 |
|            58 | analytic_timewalk            |     1.33262  |       1.54652 |            0.00913242 |                219 |
|            58 | cnn1d_all                    |     1.34426  |       1.7397  |            0.0136986  |                219 |
|            58 | mlp_all                      |     1.47014  |       1.81001 |            0.0136986  |                219 |
|            58 | tcn_new_architecture_all     |     1.50128  |       1.85849 |            0.0228311  |                219 |
|            58 | template_phase_base          |     1.79594  |       2.27067 |            0.0410959  |                219 |
|            58 | hgb_run_family_only_sentinel |     1.79594  |       2.27067 |            0.0410959  |                219 |
|            58 | hgb_shuffled_target_sentinel |     2.04964  |       2.36679 |            0.0319635  |                219 |
|            58 | hgb_amplitude_only_control   |     2.26073  |       2.4622  |            0.0228311  |                219 |
|            58 | hgb_no_stave                 |     2.38022  |       2.576   |            0.0273973  |                219 |
|            59 | hgb_no_amplitude             |     1.23935  |       2.38372 |            0.013543   |               2289 |
|            59 | s03b_binned_timewalk         |     1.25     |       2.65506 |            0.0327654  |               2289 |
|            59 | hgb_no_run_family            |     1.29599  |       2.35473 |            0.0122324  |               2289 |
|            59 | hgb_all                      |     1.31302  |       2.35975 |            0.0122324  |               2289 |
|            59 | hgb_no_pretrigger            |     1.3231   |       2.35638 |            0.0117955  |               2289 |
|            59 | hgb_no_waveform              |     1.32719  |       2.32798 |            0.0117955  |               2289 |
|            59 | hgb_no_q_template            |     1.32786  |       2.32358 |            0.0109218  |               2289 |
|            59 | analytic_timewalk            |     1.37481  |       2.61794 |            0.0187855  |               2289 |
|            59 | ridge_all                    |     1.48005  |       2.57078 |            0.0157274  |               2289 |
|            59 | mlp_all                      |     1.54504  |       2.39863 |            0.0113587  |               2289 |
|            59 | cnn1d_all                    |     1.7489   |       3.10225 |            0.0672783  |               2289 |
|            59 | tcn_new_architecture_all     |     2.01514  |       3.18902 |            0.0764526  |               2289 |
|            59 | hgb_run_family_only_sentinel |     2.25     |       3.38254 |            0.100044   |               2289 |
|            59 | template_phase_base          |     2.25     |       3.38254 |            0.100044   |               2289 |
|            59 | hgb_no_stave                 |     2.3973   |       3.03976 |            0.051114   |               2289 |
|            59 | hgb_shuffled_target_sentinel |     2.56208  |       3.54123 |            0.117955   |               2289 |
|            59 | hgb_amplitude_only_control   |     2.70401  |       3.31815 |            0.075142   |               2289 |
|            60 | s03b_binned_timewalk         |     1.25     |       2.91601 |            0.0338284  |               2424 |
|            60 | hgb_no_amplitude             |     1.26561  |       2.51767 |            0.015264   |               2424 |
|            60 | hgb_no_pretrigger            |     1.34812  |       2.50983 |            0.0144389  |               2424 |
|            60 | hgb_no_run_family            |     1.3509   |       2.50738 |            0.0148515  |               2424 |
|            60 | hgb_all                      |     1.36503  |       2.5184  |            0.0136139  |               2424 |
|            60 | hgb_no_q_template            |     1.36729  |       2.49999 |            0.0144389  |               2424 |
|            60 | hgb_no_waveform              |     1.37226  |       2.53224 |            0.0127888  |               2424 |
|            60 | analytic_timewalk            |     1.41724  |       2.87284 |            0.019802   |               2424 |
|            60 | mlp_all                      |     1.50697  |       2.58119 |            0.0144389  |               2424 |
|            60 | ridge_all                    |     1.5677   |       2.70857 |            0.015264   |               2424 |
|            60 | cnn1d_all                    |     1.6105   |       3.277   |            0.0676568  |               2424 |
|            60 | template_phase_base          |     1.79594  |       3.57695 |            0.102723   |               2424 |
|            60 | hgb_run_family_only_sentinel |     1.79594  |       3.57695 |            0.102723   |               2424 |
|            60 | tcn_new_architecture_all     |     1.85318  |       3.40786 |            0.0878713  |               2424 |
|            60 | hgb_no_stave                 |     2.32345  |       3.21143 |            0.0507426  |               2424 |
|            60 | hgb_shuffled_target_sentinel |     2.37945  |       3.71829 |            0.115099   |               2424 |
|            60 | hgb_amplitude_only_control   |     2.49116  |       3.48875 |            0.0804455  |               2424 |
|            61 | hgb_no_amplitude             |     1.57821  |       2.61388 |            0.0207217  |               2799 |
|            61 | hgb_all                      |     1.57944  |       2.59046 |            0.0221508  |               2799 |
|            61 | hgb_no_pretrigger            |     1.57985  |       2.58426 |            0.0228653  |               2799 |
|            61 | cnn1d_all                    |     1.58614  |       2.96354 |            0.060736   |               2799 |
|            61 | hgb_no_run_family            |     1.58649  |       2.58097 |            0.0217935  |               2799 |
|            61 | hgb_no_waveform              |     1.587    |       2.55829 |            0.0200071  |               2799 |
|            61 | hgb_no_q_template            |     1.5919   |       2.57766 |            0.0196499  |               2799 |
|            61 | s03b_binned_timewalk         |     1.64797  |       2.75721 |            0.0421579  |               2799 |
|            61 | mlp_all                      |     1.76218  |       2.60684 |            0.0182208  |               2799 |
|            61 | ridge_all                    |     1.7754   |       2.73802 |            0.022508   |               2799 |
|            61 | analytic_timewalk            |     1.79299  |       2.77092 |            0.0239371  |               2799 |
|            61 | tcn_new_architecture_all     |     1.84363  |       3.06169 |            0.0725259  |               2799 |
|            61 | hgb_no_stave                 |     2.07836  |       2.87517 |            0.0375134  |               2799 |
|            61 | hgb_run_family_only_sentinel |     2.25     |       3.25709 |            0.0957485  |               2799 |
|            61 | template_phase_base          |     2.25     |       3.25709 |            0.0957485  |               2799 |
|            61 | hgb_amplitude_only_control   |     2.31073  |       3.06997 |            0.0582351  |               2799 |
|            61 | hgb_shuffled_target_sentinel |     2.31137  |       3.38588 |            0.0932476  |               2799 |
|            62 | hgb_no_amplitude             |     1.23998  |       2.31528 |            0.0132177  |               2421 |
|            62 | s03b_binned_timewalk         |     1.25     |       2.49509 |            0.0338703  |               2421 |
|            62 | hgb_no_run_family            |     1.26804  |       2.27071 |            0.0136307  |               2421 |
|            62 | hgb_no_pretrigger            |     1.27041  |       2.27384 |            0.0132177  |               2421 |
|            62 | hgb_no_waveform              |     1.27076  |       2.24895 |            0.0123916  |               2421 |
|            62 | hgb_all                      |     1.27181  |       2.2755  |            0.0132177  |               2421 |
|            62 | hgb_no_q_template            |     1.28168  |       2.23537 |            0.0107394  |               2421 |
|            62 | analytic_timewalk            |     1.41333  |       2.45205 |            0.0181743  |               2421 |
|            62 | mlp_all                      |     1.48712  |       2.33137 |            0.0111524  |               2421 |
|            62 | ridge_all                    |     1.54823  |       2.45657 |            0.0119785  |               2421 |
|            62 | cnn1d_all                    |     1.66968  |       2.92414 |            0.0714581  |               2421 |
|            62 | tcn_new_architecture_all     |     1.92364  |       3.03046 |            0.0888063  |               2421 |
|            62 | template_phase_base          |     2        |       3.27138 |            0.101198   |               2421 |
|            62 | hgb_run_family_only_sentinel |     2        |       3.27138 |            0.101198   |               2421 |
|            62 | hgb_shuffled_target_sentinel |     2.33685  |       3.42107 |            0.116481   |               2421 |
|            62 | hgb_no_stave                 |     2.39105  |       2.97278 |            0.0561751  |               2421 |
|            62 | hgb_amplitude_only_control   |     2.59982  |       3.18028 |            0.0801322  |               2421 |
|            63 | hgb_no_amplitude             |     1.21358  |       2.68175 |            0.018018   |               1110 |
|            63 | hgb_no_waveform              |     1.21679  |       2.71689 |            0.0207207  |               1110 |
|            63 | hgb_all                      |     1.22588  |       2.7306  |            0.0225225  |               1110 |
|            63 | hgb_no_pretrigger            |     1.22676  |       2.71168 |            0.0198198  |               1110 |
|            63 | hgb_no_run_family            |     1.23266  |       2.71955 |            0.0225225  |               1110 |
|            63 | s03b_binned_timewalk         |     1.25     |       2.9057  |            0.0423423  |               1110 |
|            63 | hgb_no_q_template            |     1.27     |       2.73665 |            0.0198198  |               1110 |
|            63 | analytic_timewalk            |     1.40432  |       2.89989 |            0.0261261  |               1110 |
|            63 | mlp_all                      |     1.47353  |       2.70257 |            0.0207207  |               1110 |
|            63 | ridge_all                    |     1.57547  |       2.83488 |            0.0225225  |               1110 |
|            63 | cnn1d_all                    |     1.83838  |       3.22714 |            0.072973   |               1110 |
|            63 | tcn_new_architecture_all     |     1.99282  |       3.34765 |            0.0918919  |               1110 |
|            63 | template_phase_base          |     2.04594  |       3.55848 |            0.118919   |               1110 |
|            63 | hgb_run_family_only_sentinel |     2.04594  |       3.55848 |            0.118919   |               1110 |
|            63 | hgb_no_stave                 |     2.44411  |       3.4196  |            0.0792793  |               1110 |
|            63 | hgb_shuffled_target_sentinel |     2.5484   |       3.71464 |            0.130631   |               1110 |
|            63 | hgb_amplitude_only_control   |     2.72685  |       3.44686 |            0.0981982  |               1110 |
|            65 | s03b_binned_timewalk         |     1        |       1.55783 |            0.010101   |                198 |
|            65 | hgb_no_amplitude             |     1.14988  |       1.50615 |            0.0151515  |                198 |
|            65 | hgb_no_run_family            |     1.17142  |       1.56603 |            0.020202   |                198 |
|            65 | hgb_all                      |     1.17408  |       1.57005 |            0.020202   |                198 |
|            65 | hgb_no_waveform              |     1.17466  |       1.58193 |            0.0151515  |                198 |
|            65 | hgb_no_pretrigger            |     1.24074  |       1.58862 |            0.020202   |                198 |
|            65 | hgb_no_q_template            |     1.24339  |       1.54504 |            0.0151515  |                198 |
|            65 | analytic_timewalk            |     1.30732  |       1.56619 |            0.0151515  |                198 |
|            65 | mlp_all                      |     1.31016  |       1.6343  |            0.0151515  |                198 |
|            65 | ridge_all                    |     1.34982  |       1.5361  |            0.00505051 |                198 |
|            65 | cnn1d_all                    |     1.60002  |       2.02248 |            0.0252525  |                198 |
|            65 | tcn_new_architecture_all     |     1.66049  |       2.17644 |            0.040404   |                198 |
|            65 | template_phase_base          |     1.79594  |       2.46924 |            0.0555556  |                198 |
|            65 | hgb_run_family_only_sentinel |     1.79594  |       2.46924 |            0.0555556  |                198 |
|            65 | hgb_amplitude_only_control   |     2.27292  |       2.55822 |            0.0505051  |                198 |
|            65 | hgb_no_stave                 |     2.2839   |       2.39044 |            0.0505051  |                198 |
|            65 | hgb_shuffled_target_sentinel |     2.29031  |       2.68064 |            0.0707071  |                198 |

## 5. Feature-family null grid

| dropped_family   | method            |   sigma68_ns |   loss_when_dropped_ns |   delta_vs_analytic_ns |   delta_ci_low |   delta_ci_high | interpretation    |
|:-----------------|:------------------|-------------:|-----------------------:|-----------------------:|---------------:|----------------:|:------------------|
| pretrigger       | hgb_no_pretrigger |      1.36931 |             0.00681006 |              -0.125355 |      -0.210098 |      -0.0679548 | survives_ci       |
| amplitude        | hgb_no_amplitude  |      1.30395 |            -0.0585539  |              -0.190719 |      -0.24053  |      -0.136003  | survives_ci       |
| q_template       | hgb_no_q_template |      1.38295 |             0.0204465  |              -0.111719 |      -0.21567  |      -0.0474022 | survives_ci       |
| stave            | hgb_no_stave      |      2.32096 |             0.958454   |               0.826289 |       0.456009 |       1.01719   | does_not_clear_ci |
| run_family       | hgb_no_run_family |      1.36435 |             0.00184931 |              -0.130316 |      -0.226219 |      -0.0794954 | survives_ci       |
| waveform         | hgb_no_waveform   |      1.38646 |             0.0239628  |              -0.108202 |      -0.175307 |      -0.0575147 | survives_ci       |

Positive `loss_when_dropped_ns` means the removed family helped HGB; near-zero or negative values mean the family was redundant or harmful. The critical leakage question is whether HGB still beats the analytic comparator after each potentially leaky family is removed.

## 6. Leakage, systematics, and caveats

| check                                            |      value | pass   | detail                                                                                                                                                                 |
|:-------------------------------------------------|-----------:|:-------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_run_overlap                        |  0         | True   | final fits use Sample-I runs only; held-out Sample-II run list is disjoint                                                                                             |
| feature_audit_no_run_event_cross_stave_time      |  0         | True   | features are same-pulse waveform/amplitude/template/pretrigger/stave/run-family indicators; no event id, run number, event order, other-stave time, or target residual |
| hgb_shuffled_target_sentinel_delta_vs_hgb_all_ns |  1.02659   | True   | shuffled Sample-I target should not match the true HGB correction on Sample II                                                                                         |
| hgb_run_family_only_sentinel_delta_vs_hgb_all_ns |  0.683442  | True   | run-family atom alone should not reproduce the HGB correction                                                                                                          |
| hgb_all_beats_analytic_ci                        | -0.0605006 | True   | upper endpoint of paired run-bootstrap delta vs analytic_timewalk must be below zero                                                                                   |
| all_family_dropouts_beat_analytic_ci             |  1.01719   | False  | each feature-family removal must retain a CI win over analytic_timewalk to claim robust survival                                                                       |

The main systematic is sample transfer, not event statistics: Sample I and Sample II occupy different run families and amplitude/topology supports. The run-family feature is therefore included as an explicit sentinel, and the final claim is not allowed to rely on it. The bootstrap resamples held-out runs, so it reflects between-run transfer variability better than an event bootstrap, but with seven runs it remains coarse. The target is an internal same-particle closure residual, not an external time reference. The q-template and pretrigger families are same-pulse features and can still be source-adjacent to morphology labels in downstream consumers; this study only tests timing-residual leakage/null behavior.

Full distributions are reported through full RMS, core Gaussian fit sigma, chi2/ndf, and tail fraction above the preregistered 5 ns threshold. The Gaussian core is diagnostic only because the residuals have non-Gaussian tails.

## 7. Verdict

The named winner in `result.json` is **hgb_no_amplitude** with sigma68 `1.304 ns` and CI `[1.218, 1.471] ns`.
The best traditional comparator is **s03b_binned_timewalk** with sigma68 `1.398 ns`.
The preregistered HGB row `hgb_all` has sigma68 `1.363 ns`, delta vs analytic `-0.132 ns`, and delta CI `[-0.202, -0.061] ns`.
Overall verdict: `hgb_gain_is_not_robust_to_feature_leakage_null_grid`.

Hypothesis: the blind HGB gain is mostly a same-pulse waveform/amplitude transfer correction rather than a pure run-family leak, but the support change between Sample I and Sample II means it should be consumed only after direct downstream substitution tests.

## 8. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s03p_1781062439_500_63591f99_hgb_feature_leakage_null_grid.py --config configs/s03p_1781062439_500_63591f99_hgb_feature_leakage_null_grid.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hgb_feature_family_dropout.csv`, `leakage_checks.csv`, `model_fit_audit.csv`, `model_cv_audit.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

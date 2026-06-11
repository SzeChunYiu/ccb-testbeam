# S03r: stave-only HGB leakage dissection

- **Ticket:** `1781066704.631.13c7784e`
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train on Sample I runs 31-37, 39-42, and 44-57; blind evaluation on Sample II analysis runs 58-63 and 65
- **Config:** `configs/s03r_1781066704_631_13c7784e_stave_only_hgb_leakage_dissection.yaml`
- **Primary metric:** held-out Sample-II pair-residual `sigma68` at 2 cm spacing, with held-out-run bootstrap 95% CIs

## 0. Question and preregistration

The preregistered question is whether the S03h/S03p HGB timewalk gain is a genuine same-pulse timing correction or whether it is carried by stave/support labels. The traditional comparators are frozen S03a analytic timewalk and S03b monotone binned timewalk. The ML/NN panel contains ridge, HGB, MLP, 1D-CNN, and a gated dilated-TCN architecture on the same run split.

The positive HGB timing claim is rejected as stave leakage if a stave-only sentinel approaches the full HGB gain, if removing stave labels destroys the gain, or if the support-excluded model no longer beats the analytic baseline. Feature-family knockouts are stave, peak phase, pretrigger, q-template, saturation, and anomaly atoms. Familywise interpretation uses Bonferroni alpha `0.05 / 6` = `0.0083` for the 6 HGB feature-family tests; the report still shows unadjusted 95% intervals for readability.

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

Feature families are same-pulse normalized waveform samples; amplitude summaries; q-template residual/correlation summaries; pretrigger samples and slope; peak-phase summaries; saturation flags; anomaly/support summaries; stave one-hot; run-family one-hot; and extra shape summaries. No event id, run number, event order, cross-stave time, pair residual, Sample-II target, or downstream consumer label is used as a feature.

Model fit audit:

| method                        | families                                                                                            |   n_features |   n_train_rows |
|:------------------------------|:----------------------------------------------------------------------------------------------------|-------------:|---------------:|
| cnn1d_all                     | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra |           56 |           3780 |
| hgb_all                       | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra |           56 |           3780 |
| hgb_amplitude_only_control    | amplitude                                                                                           |            4 |           3780 |
| hgb_no_anomaly                | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,stave,run_family,shape_extra         |           52 |           3780 |
| hgb_no_peak_phase             | waveform,amplitude,q_template,pretrigger,saturation,anomaly,stave,run_family,shape_extra            |           52 |           3780 |
| hgb_no_pretrigger             | waveform,amplitude,q_template,peak_phase,saturation,anomaly,stave,run_family,shape_extra            |           49 |           3780 |
| hgb_no_q_template             | waveform,amplitude,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra            |           53 |           3780 |
| hgb_no_saturation             | waveform,amplitude,q_template,pretrigger,peak_phase,anomaly,stave,run_family,shape_extra            |           52 |           3780 |
| hgb_no_stave                  | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,run_family,shape_extra       |           53 |           3780 |
| hgb_run_family_only_sentinel  | run_family                                                                                          |            3 |           3780 |
| hgb_shuffled_target_sentinel  | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra |           56 |           3780 |
| hgb_single_stave_B4           | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,shape_extra                  |           50 |           1260 |
| hgb_single_stave_B6           | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,shape_extra                  |           50 |           1260 |
| hgb_single_stave_B8           | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,shape_extra                  |           50 |           1260 |
| hgb_stave_only_sentinel       | stave                                                                                               |            3 |           3780 |
| hgb_support_excluded_sentinel | waveform,amplitude,shape_extra                                                                      |           28 |           3780 |
| mlp_all                       | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra |           56 |           3780 |
| ridge_all                     | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra |           56 |           3780 |
| tcn_new_architecture_all      | waveform,amplitude,q_template,pretrigger,peak_phase,saturation,anomaly,stave,run_family,shape_extra |           56 |           3780 |

## 4. Head-to-head benchmark

| method                        |   value |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   full_rms_ns |   core_sigma_ns |   chi2_ndf |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:------------------------------|--------:|---------:|----------:|--------------------------:|---------------:|----------------:|--------------:|----------------:|-----------:|----------------------:|-------------------:|
| hgb_single_stave_B4           | 1.15308 |  1       |   1.25    |               -0.341588   |     -0.428888  |      -0.264043  |       2.54102 |        0.885436 |   118.702  |             0.0249564 |              11460 |
| hgb_no_saturation             | 1.33133 |  1.23209 |   1.47467 |               -0.163336   |     -0.247621  |      -0.09427   |       2.41381 |        1.59695  |    70.8468 |             0.0145724 |              11460 |
| hgb_all                       | 1.34062 |  1.22744 |   1.46408 |               -0.154047   |     -0.230066  |      -0.0960498 |       2.42579 |        1.6205   |    69.9824 |             0.0147469 |              11460 |
| hgb_no_peak_phase             | 1.34202 |  1.23817 |   1.47784 |               -0.152646   |     -0.244108  |      -0.109326  |       2.42689 |        1.64561  |    71.3465 |             0.0150087 |              11460 |
| hgb_no_pretrigger             | 1.34271 |  1.23644 |   1.49234 |               -0.151956   |     -0.233118  |      -0.095615  |       2.42536 |        1.63519  |    73.8894 |             0.0146597 |              11460 |
| hgb_no_anomaly                | 1.36513 |  1.25785 |   1.5188  |               -0.129534   |     -0.191163  |      -0.0704112 |       2.44649 |        1.64707  |    71.1732 |             0.0165794 |              11460 |
| hgb_no_q_template             | 1.37473 |  1.28124 |   1.47226 |               -0.119932   |     -0.219403  |      -0.0498606 |       2.43198 |        1.6398   |    71.4866 |             0.0141361 |              11460 |
| s03b_binned_timewalk          | 1.39797 |  1.14797 |   1.5     |               -0.096695   |     -0.225817  |      -0.0842496 |       2.70304 |        1.54699  |   193.294  |             0.0356021 |              11460 |
| analytic_timewalk             | 1.49467 |  1.3744  |   1.67387 |                0          |      0         |       0         |       2.68147 |        1.50648  |   134.216  |             0.0207679 |              11460 |
| hgb_stave_only_sentinel       | 1.5     |  1.35051 |   1.75    |                0.00533345 |     -0.0530163 |       0.0946326 |       2.70489 |        1.39963  |   220.128  |             0.0239965 |              11460 |
| ridge_all                     | 1.5349  |  1.47112 |   1.62311 |                0.0402322  |     -0.0579407 |       0.116983  |       2.56785 |        1.52768  |    50.2702 |             0.0169284 |              11460 |
| hgb_single_stave_B6           | 1.63589 |  1.5     |   1.76163 |                0.141222   |      0.0799646 |       0.201442  |       2.61238 |        1.44305  |   144.189  |             0.0187609 |              11460 |
| mlp_all                       | 1.71556 |  1.61353 |   1.84233 |                0.220891   |      0.145065  |       0.275528  |       2.5964  |        1.76972  |    25.8069 |             0.0201571 |              11460 |
| tcn_new_architecture_all      | 1.85273 |  1.76557 |   1.92289 |                0.358067   |      0.0953632 |       0.538664  |       3.09633 |        1.24457  |    12.0381 |             0.0707679 |              11460 |
| hgb_run_family_only_sentinel  | 2.04594 |  1.79594 |   2.04594 |                0.551276   |      0.387319  |       0.669811  |       3.36203 |        0.781805 |   229.847  |             0.0997382 |              11460 |
| template_phase_base           | 2.04594 |  1.79594 |   2.04594 |                0.551276   |      0.368054  |       0.671008  |       3.36203 |        0.781805 |   229.847  |             0.0997382 |              11460 |
| cnn1d_all                     | 2.19677 |  2.09823 |   2.26931 |                0.702103   |      0.448422  |       0.880729  |       3.32937 |        1.99356  |    39.9661 |             0.0911867 |              11460 |
| hgb_shuffled_target_sentinel  | 2.37661 |  2.30941 |   2.44434 |                0.881946   |      0.654032  |       1.06095   |       3.42159 |        2.64643  |    74.3446 |             0.102182  |              11460 |
| hgb_no_stave                  | 2.38073 |  2.25321 |   2.49059 |                0.886066   |      0.580686  |       1.10911   |       3.14286 |        2.30766  |     4.0696 |             0.0629145 |              11460 |
| hgb_support_excluded_sentinel | 2.60372 |  2.48972 |   2.68761 |                1.10905    |      0.80853   |       1.29687   |       3.23195 |        2.56081  |    12.1048 |             0.0666667 |              11460 |
| hgb_amplitude_only_control    | 2.6429  |  2.52236 |   2.76879 |                1.14824    |      0.859369  |       1.37908   |       3.4457  |        2.34506  |    23.9463 |             0.097993  |              11460 |
| hgb_single_stave_B8           | 2.67074 |  2.67    |   2.81795 |                1.17607    |      0.961197  |       1.43041   |       3.5503  |      303.156    |   183.173  |             0.0954625 |              11460 |

Per-run held-out scores:

|   heldout_run | method                        |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:------------------------------|-------------:|--------------:|----------------------:|-------------------:|
|            58 | hgb_single_stave_B4           |     0.749985 |       1.27872 |            0.00913242 |                219 |
|            58 | s03b_binned_timewalk          |     0.897972 |       1.42503 |            0.00913242 |                219 |
|            58 | hgb_single_stave_B6           |     1.12796  |       1.55657 |            0.00913242 |                219 |
|            58 | hgb_no_anomaly                |     1.18738  |       1.62714 |            0.0182648  |                219 |
|            58 | hgb_no_peak_phase             |     1.21608  |       1.63636 |            0.0136986  |                219 |
|            58 | hgb_no_q_template             |     1.22065  |       1.56709 |            0.00913242 |                219 |
|            58 | hgb_no_saturation             |     1.22232  |       1.57655 |            0.0136986  |                219 |
|            58 | hgb_all                       |     1.24257  |       1.57793 |            0.0136986  |                219 |
|            58 | hgb_no_pretrigger             |     1.24595  |       1.5896  |            0.0136986  |                219 |
|            58 | ridge_all                     |     1.31631  |       1.72418 |            0.00913242 |                219 |
|            58 | hgb_stave_only_sentinel       |     1.33128  |       1.55098 |            0.00913242 |                219 |
|            58 | analytic_timewalk             |     1.33262  |       1.54652 |            0.00913242 |                219 |
|            58 | tcn_new_architecture_all      |     1.52986  |       1.95149 |            0.0273973  |                219 |
|            58 | mlp_all                       |     1.54149  |       1.99838 |            0.0182648  |                219 |
|            58 | template_phase_base           |     1.79594  |       2.27067 |            0.0410959  |                219 |
|            58 | hgb_run_family_only_sentinel  |     1.79594  |       2.27067 |            0.0410959  |                219 |
|            58 | cnn1d_all                     |     1.87063  |       2.09749 |            0.0273973  |                219 |
|            58 | hgb_shuffled_target_sentinel  |     1.96622  |       2.37512 |            0.0410959  |                219 |
|            58 | hgb_support_excluded_sentinel |     2.29729  |       2.54492 |            0.0228311  |                219 |
|            58 | hgb_amplitude_only_control    |     2.31888  |       2.47657 |            0.0410959  |                219 |
|            58 | hgb_no_stave                  |     2.4162   |       2.43805 |            0.0273973  |                219 |
|            58 | hgb_single_stave_B8           |     2.66302  |       2.79663 |            0.0319635  |                219 |
|            59 | hgb_single_stave_B4           |     1        |       2.44069 |            0.024028   |               2289 |
|            59 | s03b_binned_timewalk          |     1.25     |       2.65506 |            0.0327654  |               2289 |
|            59 | hgb_no_peak_phase             |     1.27436  |       2.33375 |            0.0122324  |               2289 |
|            59 | hgb_no_saturation             |     1.28527  |       2.33728 |            0.0109218  |               2289 |
|            59 | hgb_all                       |     1.28871  |       2.34724 |            0.0113587  |               2289 |
|            59 | hgb_no_pretrigger             |     1.2921   |       2.34222 |            0.0122324  |               2289 |
|            59 | hgb_no_anomaly                |     1.30128  |       2.36948 |            0.013543   |               2289 |
|            59 | hgb_no_q_template             |     1.32454  |       2.33035 |            0.0113587  |               2289 |
|            59 | hgb_stave_only_sentinel       |     1.35051  |       2.64401 |            0.0209699  |               2289 |
|            59 | analytic_timewalk             |     1.37481  |       2.61794 |            0.0187855  |               2289 |
|            59 | ridge_all                     |     1.45572  |       2.4877  |            0.013543   |               2289 |
|            59 | hgb_single_stave_B6           |     1.5      |       2.56771 |            0.0192224  |               2289 |
|            59 | mlp_all                       |     1.6771   |       2.48422 |            0.0152905  |               2289 |
|            59 | tcn_new_architecture_all      |     2.00318  |       3.11493 |            0.0698995  |               2289 |
|            59 | hgb_run_family_only_sentinel  |     2.25     |       3.38254 |            0.100044   |               2289 |
|            59 | template_phase_base           |     2.25     |       3.38254 |            0.100044   |               2289 |
|            59 | cnn1d_all                     |     2.30069  |       3.36991 |            0.0939275  |               2289 |
|            59 | hgb_no_stave                  |     2.50301  |       3.14957 |            0.0598515  |               2289 |
|            59 | hgb_shuffled_target_sentinel  |     2.5037   |       3.42355 |            0.105286   |               2289 |
|            59 | hgb_support_excluded_sentinel |     2.61567  |       3.2142  |            0.0664045  |               2289 |
|            59 | hgb_amplitude_only_control    |     2.79757  |       3.48289 |            0.103539   |               2289 |
|            59 | hgb_single_stave_B8           |     2.89614  |       3.60824 |            0.104412   |               2289 |
|            60 | hgb_single_stave_B4           |     1.22619  |       2.71949 |            0.0247525  |               2424 |
|            60 | s03b_binned_timewalk          |     1.25     |       2.91601 |            0.0338284  |               2424 |
|            60 | hgb_no_peak_phase             |     1.29958  |       2.48103 |            0.0119637  |               2424 |
|            60 | hgb_no_pretrigger             |     1.31028  |       2.48334 |            0.0119637  |               2424 |
|            60 | hgb_no_saturation             |     1.3131   |       2.47872 |            0.0115512  |               2424 |
|            60 | hgb_all                       |     1.32644  |       2.49213 |            0.0119637  |               2424 |
|            60 | hgb_no_anomaly                |     1.34791  |       2.51299 |            0.0136139  |               2424 |
|            60 | hgb_no_q_template             |     1.36625  |       2.50007 |            0.0119637  |               2424 |
|            60 | hgb_stave_only_sentinel       |     1.39835  |       2.90916 |            0.0222772  |               2424 |
|            60 | analytic_timewalk             |     1.41724  |       2.87284 |            0.019802   |               2424 |
|            60 | ridge_all                     |     1.56052  |       2.65595 |            0.0144389  |               2424 |
|            60 | mlp_all                       |     1.63843  |       2.64704 |            0.0173267  |               2424 |
|            60 | hgb_single_stave_B6           |     1.64287  |       2.84505 |            0.0189769  |               2424 |
|            60 | tcn_new_architecture_all      |     1.76493  |       3.34061 |            0.0783828  |               2424 |
|            60 | template_phase_base           |     1.79594  |       3.57695 |            0.102723   |               2424 |
|            60 | hgb_run_family_only_sentinel  |     1.79594  |       3.57695 |            0.102723   |               2424 |
|            60 | cnn1d_all                     |     2.15236  |       3.59288 |            0.100248   |               2424 |
|            60 | hgb_shuffled_target_sentinel  |     2.30568  |       3.61274 |            0.102723   |               2424 |
|            60 | hgb_no_stave                  |     2.38782  |       3.33754 |            0.0660066  |               2424 |
|            60 | hgb_amplitude_only_control    |     2.61796  |       3.67037 |            0.103548   |               2424 |
|            60 | hgb_support_excluded_sentinel |     2.61943  |       3.39767 |            0.0726073  |               2424 |
|            60 | hgb_single_stave_B8           |     2.66963  |       3.71798 |            0.0965347  |               2424 |
|            61 | hgb_single_stave_B4           |     1.42118  |       2.59257 |            0.0289389  |               2799 |
|            61 | hgb_no_saturation             |     1.55109  |       2.54861 |            0.0196499  |               2799 |
|            61 | hgb_all                       |     1.57169  |       2.56307 |            0.0207217  |               2799 |
|            61 | hgb_no_q_template             |     1.57542  |       2.57402 |            0.0185781  |               2799 |
|            61 | hgb_no_peak_phase             |     1.57626  |       2.5666  |            0.0203644  |               2799 |
|            61 | hgb_no_pretrigger             |     1.57968  |       2.56057 |            0.0196499  |               2799 |
|            61 | hgb_no_anomaly                |     1.59485  |       2.57475 |            0.0214362  |               2799 |
|            61 | s03b_binned_timewalk          |     1.64797  |       2.75721 |            0.0421579  |               2799 |
|            61 | tcn_new_architecture_all      |     1.78267  |       2.96546 |            0.0618078  |               2799 |
|            61 | ridge_all                     |     1.78508  |       2.68748 |            0.022508   |               2799 |
|            61 | analytic_timewalk             |     1.79299  |       2.77092 |            0.0239371  |               2799 |
|            61 | hgb_stave_only_sentinel       |     1.85051  |       2.78919 |            0.0300107  |               2799 |
|            61 | hgb_single_stave_B6           |     1.90712  |       2.67722 |            0.0196499  |               2799 |
|            61 | mlp_all                       |     1.95084  |       2.71899 |            0.0267953  |               2799 |
|            61 | cnn1d_all                     |     2.08367  |       3.15485 |            0.0796713  |               2799 |
|            61 | hgb_no_stave                  |     2.14401  |       2.9108  |            0.0400143  |               2799 |
|            61 | hgb_run_family_only_sentinel  |     2.25     |       3.25709 |            0.0957485  |               2799 |
|            61 | template_phase_base           |     2.25     |       3.25709 |            0.0957485  |               2799 |
|            61 | hgb_shuffled_target_sentinel  |     2.35675  |       3.34468 |            0.0868167  |               2799 |
|            61 | hgb_support_excluded_sentinel |     2.40271  |       3.06749 |            0.0450161  |               2799 |
|            61 | hgb_amplitude_only_control    |     2.45564  |       3.2568  |            0.0757413  |               2799 |
|            61 | hgb_single_stave_B8           |     2.67037  |       3.36369 |            0.0671668  |               2799 |
|            62 | hgb_single_stave_B4           |     1        |       2.35915 |            0.0264354  |               2421 |
|            62 | hgb_all                       |     1.23054  |       2.21468 |            0.0111524  |               2421 |
|            62 | hgb_no_saturation             |     1.23187  |       2.20693 |            0.0115655  |               2421 |
|            62 | hgb_no_pretrigger             |     1.23431  |       2.22519 |            0.0111524  |               2421 |
|            62 | hgb_no_peak_phase             |     1.24619  |       2.24048 |            0.0123916  |               2421 |
|            62 | s03b_binned_timewalk          |     1.25     |       2.49509 |            0.0338703  |               2421 |
|            62 | hgb_no_q_template             |     1.27528  |       2.21746 |            0.00991326 |               2421 |
|            62 | hgb_no_anomaly                |     1.27615  |       2.24903 |            0.0128046  |               2421 |
|            62 | hgb_stave_only_sentinel       |     1.35051  |       2.47362 |            0.0210657  |               2421 |
|            62 | analytic_timewalk             |     1.41333  |       2.45205 |            0.0181743  |               2421 |
|            62 | ridge_all                     |     1.49913  |       2.47739 |            0.0111524  |               2421 |
|            62 | hgb_single_stave_B6           |     1.53167  |       2.36465 |            0.015696   |               2421 |
|            62 | mlp_all                       |     1.62324  |       2.48213 |            0.0144568  |               2421 |
|            62 | tcn_new_architecture_all      |     1.82413  |       2.98118 |            0.0747625  |               2421 |
|            62 | template_phase_base           |     2        |       3.27138 |            0.101198   |               2421 |
|            62 | hgb_run_family_only_sentinel  |     2        |       3.27138 |            0.101198   |               2421 |
|            62 | cnn1d_all                     |     2.23822  |       3.23584 |            0.0974804  |               2421 |
|            62 | hgb_shuffled_target_sentinel  |     2.35068  |       3.33956 |            0.105741   |               2421 |
|            62 | hgb_no_stave                  |     2.44898  |       3.06871 |            0.0677406  |               2421 |
|            62 | hgb_support_excluded_sentinel |     2.65909  |       3.1718  |            0.0739364  |               2421 |
|            62 | hgb_single_stave_B8           |     2.6688   |       3.51187 |            0.108633   |               2421 |
|            62 | hgb_amplitude_only_control    |     2.74099  |       3.39587 |            0.107394   |               2421 |
|            63 | hgb_single_stave_B4           |     1.08976  |       2.85585 |            0.0297297  |               1110 |
|            63 | hgb_no_saturation             |     1.18674  |       2.70814 |            0.0189189  |               1110 |
|            63 | hgb_all                       |     1.20024  |       2.72166 |            0.0189189  |               1110 |
|            63 | hgb_no_pretrigger             |     1.20109  |       2.73197 |            0.0198198  |               1110 |
|            63 | hgb_no_peak_phase             |     1.20292  |       2.72293 |            0.018018   |               1110 |
|            63 | hgb_no_anomaly                |     1.22064  |       2.73688 |            0.0207207  |               1110 |
|            63 | s03b_binned_timewalk          |     1.25     |       2.9057  |            0.0423423  |               1110 |
|            63 | hgb_no_q_template             |     1.2537   |       2.76352 |            0.0198198  |               1110 |
|            63 | hgb_stave_only_sentinel       |     1.35051  |       2.9053  |            0.0306306  |               1110 |
|            63 | analytic_timewalk             |     1.40432  |       2.89989 |            0.0261261  |               1110 |

## 5. Feature-family null grid

| dropped_family   | method            |   sigma68_ns |   loss_when_dropped_ns |   delta_vs_analytic_ns |   delta_ci_low |   delta_ci_high | interpretation    |
|:-----------------|:------------------|-------------:|-----------------------:|-----------------------:|---------------:|----------------:|:------------------|
| pretrigger       | hgb_no_pretrigger |      1.34271 |             0.00209139 |              -0.151956 |      -0.233118 |      -0.095615  | survives_ci       |
| q_template       | hgb_no_q_template |      1.37473 |             0.0341153  |              -0.119932 |      -0.219403 |      -0.0498606 | survives_ci       |
| stave            | hgb_no_stave      |      2.38073 |             1.04011    |               0.886066 |       0.580686 |       1.10911   | does_not_clear_ci |
| peak_phase       | hgb_no_peak_phase |      1.34202 |             0.0014014  |              -0.152646 |      -0.244108 |      -0.109326  | survives_ci       |
| saturation       | hgb_no_saturation |      1.33133 |            -0.00928897 |              -0.163336 |      -0.247621 |      -0.09427   | survives_ci       |
| anomaly          | hgb_no_anomaly    |      1.36513 |             0.0245127  |              -0.129534 |      -0.191163 |      -0.0704112 | survives_ci       |

Positive `loss_when_dropped_ns` means the removed family helped HGB; near-zero or negative values mean the family was redundant or harmful. The critical leakage question is whether HGB still beats the analytic comparator after each potentially leaky family is removed.

Single-stave-only fits are included in the benchmark table. They train a separate HGB correction on only B4, B6, or B8 and leave the other downstream staves at the template-phase base time, which tests whether one stave can dominate the apparent closure improvement.

## 6. Support matching diagnostics

| family     | feature                      |     train_mean |   heldout_mean |   standardized_shift |    train_p10 |     train_p90 |   heldout_p10 |   heldout_p90 |
|:-----------|:-----------------------------|---------------:|---------------:|---------------------:|-------------:|--------------:|--------------:|--------------:|
| amplitude  | area_over_amp                |     5.98053    |     7.10519    |            0.448301  |  2.21982     |    8.40775    |   5.30853     |    8.78415    |
| amplitude  | inv_amp_1000                 |     0.4114     |     0.405668   |           -0.0403163 |  0.260257    |    0.595646   |   0.251975    |    0.584454   |
| amplitude  | inv_sqrt_amp_1000            |     0.632692   |     0.628294   |           -0.0417419 |  0.510154    |    0.771781   |   0.501971    |    0.764496   |
| amplitude  | log_amp                      |     7.85059    |     7.86472    |            0.0432418 |  7.42646     |    8.2541     |   7.44542     |    8.28643    |
| anomaly    | late_over_early_charge       | 40872.6        | 24427.6        |           -0.0356909 |  1.21574     | 2486.66       |   0.798826    |  978.445      |
| anomaly    | max_abs_adjacent_sample_jump |     0.484464   |     0.48632    |            0.01584   |  0.383602    |    0.618087   |   0.382432    |    0.621662   |
| anomaly    | negative_pretrigger_floor    |    -0.040133   |    -0.0539673  |           -0.0896659 | -0.0380499   |   -0.00084458 |  -0.123576    |   -0.00092471 |
| anomaly    | pretrigger_std               |     0.0548848  |     0.0751305  |            0.13782   |  0.000919884 |    0.189118   |   0.00101145  |    0.307412   |
| pretrigger | pre0                         |    -0.0351711  |    -0.0501384  |           -0.0945719 | -0.033567    |    0.00434803 |  -0.121104    |    0.00389297 |
| pretrigger | pre1                         |    -0.0228503  |    -0.0325782  |           -0.114769  | -0.0329673   |    0.00212654 |  -0.112669    |    0.00222352 |
| pretrigger | pre2                         |     0.0225236  |     0.0321642  |            0.113638  | -0.00262795  |    0.0311041  |  -0.00255944  |    0.112435   |
| pretrigger | pre3                         |     0.091394   |     0.1289     |            0.160451  | -0.00370828  |    0.410369   |  -0.00372773  |    0.625736   |
| pretrigger | pre_mean                     |     0.013974   |     0.019587   |            0.150786  | -0.000713238 |    0.0736226  |  -0.000748654 |    0.0992112  |
| pretrigger | pre_slope_per_ns             |     0.00421884 |     0.00596796 |            0.141687  | -0.000246396 |    0.0150858  |  -0.000231204 |    0.0251175  |
| pretrigger | pre_std                      |     0.0548848  |     0.0751305  |            0.13782   |  0.000919884 |    0.189118   |   0.00101145  |    0.307412   |
| q_template | template_corr                |     0.443015   |     0.603895   |            0.431026  | -0.02968     |    0.933471   |  -0.0479096   |    0.953453   |
| q_template | template_mse                 |     0.146818   |     0.123393   |           -0.166162  |  0.0442034   |    0.204829   |   0.0383882   |    0.234135   |
| q_template | template_tail_mse            |     0.165488   |     0.0940969  |           -0.322598  |  0.0219921   |    0.327858   |   0.0195311   |    0.233816   |
| stave      | stave_B4                     |     0.333333   |     0.333333   |            0         |  0           |    1          |   0           |    1          |
| stave      | stave_B6                     |     0.333333   |     0.333333   |            0         |  0           |    1          |   0           |    1          |
| stave      | stave_B8                     |     0.333333   |     0.333333   |            0         |  0           |    1          |   0           |    1          |

These rows are not reweighting factors; they are the audit surface for the matched-support caveat. Large standardized shifts identify where Sample-II support differs from the Sample-I fit domain and where a feature-family gain can be a transfer shortcut rather than a stable timing correction.

## 7. Leakage, systematics, and caveats

| check                                            |      value | pass   | detail                                                                                                                                                                 |
|:-------------------------------------------------|-----------:|:-------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_run_overlap                        |  0         | True   | final fits use Sample-I runs only; held-out Sample-II run list is disjoint                                                                                             |
| feature_audit_no_run_event_cross_stave_time      |  0         | True   | features are same-pulse waveform/amplitude/template/pretrigger/stave/run-family indicators; no event id, run number, event order, other-stave time, or target residual |
| hgb_shuffled_target_sentinel_delta_vs_hgb_all_ns |  1.03599   | True   | shuffled Sample-I target should not match the true HGB correction on Sample II                                                                                         |
| hgb_run_family_only_sentinel_delta_vs_hgb_all_ns |  0.705324  | True   | run-family atom alone should not reproduce the HGB correction                                                                                                          |
| hgb_stave_only_sentinel_delta_vs_hgb_all_ns      |  0.159381  | True   | stave label alone should not reproduce the full HGB correction                                                                                                         |
| hgb_no_stave_beats_analytic_ci                   |  1.10911   | False  | HGB without stave labels must still beat analytic_timewalk to reject a stave shortcut                                                                                  |
| hgb_support_excluded_beats_analytic_ci           |  1.29687   | False  | support-excluded HGB uses waveform, amplitude, and generic shape only; its CI win is required for a robust non-support claim                                           |
| hgb_all_beats_analytic_ci                        | -0.0960498 | True   | upper endpoint of paired run-bootstrap delta vs analytic_timewalk must be below zero                                                                                   |
| all_family_dropouts_beat_analytic_ci             |  1.10911   | False  | each feature-family removal must retain a CI win over analytic_timewalk to claim robust survival                                                                       |

The main systematic is sample transfer, not event statistics: Sample I and Sample II occupy different run families and amplitude/topology supports. The run-family and stave-only features are therefore included as explicit sentinels, and the final claim is not allowed to rely on them. The bootstrap resamples held-out runs, so it reflects between-run transfer variability better than an event bootstrap, but with seven runs it remains coarse. The target is an internal same-particle closure residual, not an external time reference. The q-template, pretrigger, peak-phase, saturation, and anomaly families are same-pulse features, but they can still be source-adjacent to morphology/support labels in downstream consumers; this study only tests timing-residual leakage/null behavior.

Full distributions are reported through full RMS, core Gaussian fit sigma, chi2/ndf, and tail fraction above the preregistered 5 ns threshold. The Gaussian core is diagnostic only because the residuals have non-Gaussian tails.

## 8. Verdict

The named winner in `result.json` is **hgb_single_stave_B4** with sigma68 `1.153 ns` and CI `[1.000, 1.250] ns`.
The best traditional comparator is **s03b_binned_timewalk** with sigma68 `1.398 ns`.
The preregistered HGB row `hgb_all` has sigma68 `1.341 ns`, delta vs analytic `-0.154 ns`, and delta CI `[-0.230, -0.096] ns`.
Overall verdict: `hgb_gain_not_safe_against_stave_support_leakage`.

Stave-only false-gain status: `stave_only_worse_than_full_hgb`; support-excluded status: `does_not_clear_analytic_ci`.

Hypothesis: any surviving HGB gain must be interpreted as a same-pulse waveform/support correction only if stave-only and run-only sentinels remain far worse than the full model and support-excluded HGB still improves over the analytic baseline.

## 9. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s03r_1781066704_631_13c7784e_stave_only_hgb_leakage_dissection.py --config configs/s03r_1781066704_631_13c7784e_stave_only_hgb_leakage_dissection.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hgb_feature_family_dropout.csv`, `support_match_diagnostics.csv`, `leakage_checks.csv`, `model_fit_audit.csv`, `model_cv_audit.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.

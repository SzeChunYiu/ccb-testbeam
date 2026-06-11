# S03n: Hierarchical timewalk coefficient atom attribution

- **Ticket:** 1781056877.507.6c6921d4
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/s03n_1781056877_507_6c6921d4_hierarchical_timewalk_atom_attribution.yaml`

## 1. Preregistered question

S03e/S03f showed that timewalk corrections can materially reduce downstream pairwise timing residuals. S03n asks which atomic components drive that gain, whether they have physically plausible signs, and whether learned residual models improve on a strong traditional hierarchical comparator without support leakage.

## 2. Raw-ROOT reproduction gate

The selected-pulse counts were recomputed directly from the ROOT files before model fitting. The gate is exact: all tolerances are zero.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

A second gate reproduces the run-65 S03a/S03b reference numbers from the raw-derived pulse table.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

## 3. Estimand and equations

For pulse `i` on stave `s`, the train-template pickoff is `t0_i = t_template_phase_i`. The residual target used for fitted corrections is

`r_i = (t0_i - x_s v^-1) - mean_{u != s}(t0_u - x_u v^-1)`,

where the mean is over the other two downstream staves in the same event, `x_s` is the stave position, and `v^-1 = 0.078 ns/cm`. A model predicts `f(x_i)` on training runs only and the corrected time is

`t_i = t0_i - f(x_i)`.

The primary score is `sigma68 = (Q84(e) - Q16(e))/2`, evaluated on held-out pair residuals `e_ab = t_a - t_b - (x_a - x_b)v^-1`. Pooled confidence intervals resample whole held-out runs with replacement.

## 4. Methods

Traditional comparators are: the template-phase baseline, S03a analytic amplitude Ridge, S03b monotone binned timewalk, and the S03f-style hierarchical shared-bin correction with fixed eight log-amplitude bins, run shrinkage 80, and deployment population weight 4. The atom ablation replaces a method's correction by the template baseline for one held-out atom and records the sigma68 loss.

ML/NN comparators are Ridge, histogram gradient-boosted trees, MLP, a two-layer 1D-CNN, and a small dilated 1D-TCN as the new architecture. Controls are amplitude-only, topology-only, and shuffled-residual HGB. Features exclude run id, event id, event order, other-stave times, and held-out labels.

Atoms are grouped by stave, log-amplitude quartile, rise-time tertile, and within-event amplitude topology rank. Permutation attribution shuffles one feature group inside the held-out run and reports the sigma68 increase.

## 5. Head-to-head results

| method                        |   value |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:------------------------------|--------:|---------:|----------:|--------------:|----------------------:|-------------------:|
| template_phase_base           | 2.74141 |  2.68945 |   2.99232 |       3.30837 |             0.0813264 |              11460 |
| analytic_amp_ridge            | 1.55109 |  1.35898 |   1.83263 |       2.66699 |             0.0191099 |              11460 |
| monotone_binned               | 1.64515 |  1.32559 |   1.96343 |       2.71603 |             0.019459  |              11460 |
| hierarchical_shared_bins      | 1.35811 |  1.0597  |   1.50131 |       2.55347 |             0.0179756 |              11460 |
| ridge                         | 1.60127 |  1.4461  |   1.90826 |       2.60759 |             0.0157068 |              11460 |
| gradient_boosted_trees        | 1.49582 |  1.3421  |   1.70754 |       2.3317  |             0.0153578 |              11460 |
| mlp                           | 1.63473 |  1.46711 |   1.82022 |       2.37693 |             0.0125654 |              11460 |
| cnn                           | 2.80334 |  2.6679  |   2.9336  |       3.29125 |             0.0616056 |              11460 |
| tcn_new_architecture          | 2.80352 |  2.65587 |   2.92362 |       3.29196 |             0.0618674 |              11460 |
| amplitude_only_control        | 1.56151 |  1.37555 |   1.85485 |       2.66956 |             0.0182373 |              11460 |
| topology_only_control         | 1.53351 |  1.25961 |   1.92091 |       2.70099 |             0.0220768 |              11460 |
| shuffled_residual_hgb_control | 2.78645 |  2.70351 |   2.93902 |       3.32065 |             0.0764398 |              11460 |

Per-run scores:

|   heldout_run | method                        |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:------------------------------|-------------:|--------------:|----------------------:|-------------------:|
|            58 | hierarchical_shared_bins      |     0.915304 |       2.66376 |            0.0182648  |                219 |
|            58 | analytic_amp_ridge            |     1.18748  |       2.67793 |            0.0182648  |                219 |
|            58 | topology_only_control         |     1.19311  |       2.74484 |            0.0319635  |                219 |
|            58 | amplitude_only_control        |     1.21817  |       2.71379 |            0.0273973  |                219 |
|            58 | monotone_binned               |     1.3214   |       2.78333 |            0.0319635  |                219 |
|            58 | ridge                         |     1.43044  |       2.99595 |            0.0182648  |                219 |
|            58 | gradient_boosted_trees        |     1.46517  |       2.68733 |            0.0182648  |                219 |
|            58 | mlp                           |     1.66406  |       2.99691 |            0.0273973  |                219 |
|            58 | template_phase_base           |     2.6428   |       3.54397 |            0.0776256  |                219 |
|            58 | shuffled_residual_hgb_control |     2.69273  |       3.55065 |            0.0776256  |                219 |
|            58 | tcn_new_architecture          |     2.99263  |       3.5869  |            0.0593607  |                219 |
|            58 | cnn                           |     2.99273  |       3.58381 |            0.0593607  |                219 |
|            59 | hierarchical_shared_bins      |     1.18219  |       2.44944 |            0.013543   |               2289 |
|            59 | topology_only_control         |     1.31206  |       2.57809 |            0.017038   |               2289 |
|            59 | gradient_boosted_trees        |     1.36574  |       2.30549 |            0.0117955  |               2289 |
|            59 | amplitude_only_control        |     1.4358   |       2.53378 |            0.0148536  |               2289 |
|            59 | analytic_amp_ridge            |     1.45871  |       2.54019 |            0.0144168  |               2289 |
|            59 | monotone_binned               |     1.5      |       2.59383 |            0.0157274  |               2289 |
|            59 | mlp                           |     1.50994  |       2.36683 |            0.0109218  |               2289 |
|            59 | ridge                         |     1.55247  |       2.4696  |            0.013543   |               2289 |
|            59 | tcn_new_architecture          |     2.91796  |       3.33689 |            0.0633464  |               2289 |
|            59 | cnn                           |     2.92331  |       3.33821 |            0.0633464  |               2289 |
|            59 | shuffled_residual_hgb_control |     2.98443  |       3.34982 |            0.0821319  |               2289 |
|            59 | template_phase_base           |     2.99232  |       3.34278 |            0.0677152  |               2289 |
|            60 | hierarchical_shared_bins      |     1.00281  |       2.31033 |            0.0148515  |               2424 |
|            60 | monotone_binned               |     1.23065  |       2.42144 |            0.0156766  |               2424 |
|            60 | topology_only_control         |     1.25961  |       2.43409 |            0.0165017  |               2424 |
|            60 | gradient_boosted_trees        |     1.33296  |       2.03617 |            0.0144389  |               2424 |
|            60 | amplitude_only_control        |     1.34014  |       2.39784 |            0.0148515  |               2424 |
|            60 | analytic_amp_ridge            |     1.3437   |       2.39529 |            0.015264   |               2424 |
|            60 | ridge                         |     1.40077  |       2.29163 |            0.0144389  |               2424 |
|            60 | mlp                           |     1.41609  |       1.98781 |            0.0115512  |               2424 |
|            60 | template_phase_base           |     2.66393  |       3.279   |            0.0944719  |               2424 |
|            60 | cnn                           |     2.71234  |       3.31414 |            0.0882838  |               2424 |
|            60 | tcn_new_architecture          |     2.71268  |       3.31441 |            0.0882838  |               2424 |
|            60 | shuffled_residual_hgb_control |     2.73762  |       3.32499 |            0.095297   |               2424 |
|            61 | hierarchical_shared_bins      |     1.67412  |       2.84861 |            0.0242944  |               2799 |
|            61 | gradient_boosted_trees        |     1.90396  |       2.7234  |            0.0250089  |               2799 |
|            61 | mlp                           |     1.95516  |       2.7972  |            0.0164344  |               2799 |
|            61 | ridge                         |     2.0375   |       3.02898 |            0.0267953  |               2799 |
|            61 | monotone_binned               |     2.10176  |       3.07643 |            0.0310825  |               2799 |
|            61 | amplitude_only_control        |     2.11622  |       3.01305 |            0.0310825  |               2799 |
|            61 | topology_only_control         |     2.11756  |       3.04417 |            0.0339407  |               2799 |
|            61 | analytic_amp_ridge            |     2.12996  |       3.00806 |            0.0314398  |               2799 |
|            61 | cnn                           |     2.6154   |       3.15622 |            0.0439443  |               2799 |
|            61 | tcn_new_architecture          |     2.61871  |       3.15848 |            0.0439443  |               2799 |
|            61 | shuffled_residual_hgb_control |     2.69969  |       3.20639 |            0.0468024  |               2799 |
|            61 | template_phase_base           |     2.70351  |       3.20716 |            0.0428725  |               2799 |
|            62 | hierarchical_shared_bins      |     1.25175  |       2.4893  |            0.0128046  |               2421 |
|            62 | topology_only_control         |     1.35342  |       2.60911 |            0.0144568  |               2421 |
|            62 | gradient_boosted_trees        |     1.40868  |       2.21397 |            0.00908715 |               2421 |
|            62 | monotone_binned               |     1.43743  |       2.64762 |            0.0144568  |               2421 |
|            62 | amplitude_only_control        |     1.45247  |       2.59435 |            0.0128046  |               2421 |
|            62 | analytic_amp_ridge            |     1.469    |       2.58419 |            0.0128046  |               2421 |
|            62 | ridge                         |     1.52499  |       2.47245 |            0.0103263  |               2421 |
|            62 | mlp                           |     1.58469  |       2.28577 |            0.00908715 |               2421 |
|            62 | tcn_new_architecture          |     2.87071  |       3.2801  |            0.0574143  |               2421 |
|            62 | cnn                           |     2.87709  |       3.27824 |            0.0561751  |               2421 |
|            62 | template_phase_base           |     2.90117  |       3.35891 |            0.0929368  |               2421 |
|            62 | shuffled_residual_hgb_control |     2.92569  |       3.35701 |            0.0830235  |               2421 |
|            63 | topology_only_control         |     1.15582  |       2.64123 |            0.0198198  |               1110 |
|            63 | hierarchical_shared_bins      |     1.19949  |       2.55241 |            0.0198198  |               1110 |
|            63 | gradient_boosted_trees        |     1.30246  |       2.07034 |            0.0153153  |               1110 |
|            63 | amplitude_only_control        |     1.38806  |       2.62444 |            0.0171171  |               1110 |
|            63 | analytic_amp_ridge            |     1.39132  |       2.62807 |            0.0207207  |               1110 |
|            63 | monotone_binned               |     1.43311  |       2.68746 |            0.0198198  |               1110 |
|            63 | ridge                         |     1.43376  |       2.52028 |            0.0207207  |               1110 |
|            63 | mlp                           |     1.55977  |       2.07413 |            0.0135135  |               1110 |
|            63 | template_phase_base           |     2.87872  |       3.38179 |            0.0963964  |               1110 |
|            63 | shuffled_residual_hgb_control |     2.92408  |       3.40303 |            0.090991   |               1110 |
|            63 | tcn_new_architecture          |     3.01404  |       3.42871 |            0.0828829  |               1110 |
|            63 | cnn                           |     3.01521  |       3.42821 |            0.0828829  |               1110 |
|            65 | hierarchical_shared_bins      |     1.19105  |       1.56928 |            0.00505051 |                198 |
|            65 | topology_only_control         |     1.41753  |       1.73203 |            0.00505051 |                198 |
|            65 | gradient_boosted_trees        |     1.45373  |       1.63463 |            0.00505051 |                198 |
|            65 | amplitude_only_control        |     1.47947  |       1.69259 |            0.00505051 |                198 |
|            65 | analytic_amp_ridge            |     1.49464  |       1.69913 |            0.00505051 |                198 |
|            65 | ridge                         |     1.52011  |       1.66612 |            0.00505051 |                198 |
|            65 | monotone_binned               |     1.56958  |       1.83396 |            0.00505051 |                198 |
|            65 | mlp                           |     1.61236  |       1.6774  |            0.00505051 |                198 |
|            65 | tcn_new_architecture          |     2.65222  |       2.49758 |            0.020202   |                198 |
|            65 | cnn                           |     2.65338  |       2.49807 |            0.020202   |                198 |
|            65 | shuffled_residual_hgb_control |     2.838    |       2.57813 |            0.040404   |                198 |
|            65 | template_phase_base           |     2.88915  |       2.57669 |            0.0505051  |                198 |

## 6. Atom attribution

| method                        | atom_scope    |   median_contribution_ns |   max_contribution_ns |   median_support |   median_bias_ns |
|:------------------------------|:--------------|-------------------------:|----------------------:|-----------------:|-----------------:|
| amplitude_only_control        | amp_atom      |              0.695288    |             1.53286   |            418   |      -0.0335152  |
| amplitude_only_control        | shape_atom    |              0.892521    |             1.31026   |            634.5 |      -0.0304466  |
| amplitude_only_control        | stave         |              0.188786    |             0.766979  |            763   |      -0.057903   |
| amplitude_only_control        | topology_atom |              0.783993    |             1.00534   |            763   |      -0.0229766  |
| analytic_amp_ridge            | amp_atom      |              0.694698    |             1.47021   |            418   |      -0.010604   |
| analytic_amp_ridge            | shape_atom    |              0.857907    |             1.2389    |            634.5 |      -0.0165866  |
| analytic_amp_ridge            | stave         |              0.136842    |             0.798161  |            763   |      -0.0240783  |
| analytic_amp_ridge            | topology_atom |              0.702268    |             0.985498  |            763   |      -0.00612682 |
| cnn                           | amp_atom      |              0.0204577   |             0.155171  |            418   |       0.954072   |
| cnn                           | shape_atom    |              0.00787632  |             0.217596  |            634.5 |       0.949916   |
| cnn                           | stave         |              0.0145759   |             0.334116  |            763   |       0.964862   |
| cnn                           | topology_atom |              0.0526081   |             0.29609   |            763   |       0.912035   |
| gradient_boosted_trees        | amp_atom      |              0.70099     |             1.67446   |            418   |       0.0342727  |
| gradient_boosted_trees        | shape_atom    |              0.850846    |             1.2384    |            634.5 |       0.0319505  |
| gradient_boosted_trees        | stave         |              0.285552    |             0.683891  |            763   |       0.0128535  |
| gradient_boosted_trees        | topology_atom |              0.73882     |             0.939308  |            763   |       0.0242777  |
| hierarchical_shared_bins      | amp_atom      |              0.773289    |             1.4938    |            418   |       0.0359111  |
| hierarchical_shared_bins      | shape_atom    |              0.860967    |             1.25594   |            634.5 |       0.0453723  |
| hierarchical_shared_bins      | stave         |              0.431237    |             0.737802  |            763   |       0.0592991  |
| hierarchical_shared_bins      | topology_atom |              0.738089    |             1.15003   |            763   |       0.0345121  |
| mlp                           | amp_atom      |              0.622763    |             1.59998   |            418   |       0.0295784  |
| mlp                           | shape_atom    |              0.744695    |             1.18197   |            634.5 |       0.0255364  |
| mlp                           | stave         |              0.156269    |             0.722591  |            763   |       0.0124576  |
| mlp                           | topology_atom |              0.656707    |             0.924799  |            763   |       0.00049992 |
| monotone_binned               | amp_atom      |              0.766099    |             1.48423   |            418   |       0          |
| monotone_binned               | shape_atom    |              0.942717    |             1.3056    |            634.5 |       0          |
| monotone_binned               | stave         |              0.0132956   |             0.78459   |            763   |       0          |
| monotone_binned               | topology_atom |              0.713155    |             0.933277  |            763   |       0          |
| ridge                         | amp_atom      |              0.626158    |             1.53956   |            418   |       0.00144606 |
| ridge                         | shape_atom    |              0.832921    |             1.30352   |            634.5 |      -0.0329376  |
| ridge                         | stave         |              0.223429    |             0.781747  |            763   |      -0.0244698  |
| ridge                         | topology_atom |              0.704456    |             0.934356  |            763   |       0.00480604 |
| shuffled_residual_hgb_control | amp_atom      |             -0.000350853 |             0.0218863 |            418   |       1.35188    |
| shuffled_residual_hgb_control | shape_atom    |             -0.00328127  |             0.0386615 |            634.5 |       1.43699    |
| shuffled_residual_hgb_control | stave         |             -0.00200575  |             0.0988349 |            763   |       1.52196    |
| shuffled_residual_hgb_control | topology_atom |              0.000687075 |             0.0325776 |            763   |       1.48102    |
| tcn_new_architecture          | amp_atom      |              0.0221264   |             0.155648  |            418   |       0.959437   |
| tcn_new_architecture          | shape_atom    |              0.00777686  |             0.222775  |            634.5 |       0.954072   |
| tcn_new_architecture          | stave         |              0.018033    |             0.347352  |            763   |       0.968704   |
| tcn_new_architecture          | topology_atom |              0.0478674   |             0.298249  |            763   |       0.908896   |
| topology_only_control         | amp_atom      |              0.743668    |             1.60667   |            418   |      -0.0178785  |
| topology_only_control         | shape_atom    |              0.948014    |             1.36065   |            634.5 |      -0.0162963  |
| topology_only_control         | stave         |              0.189478    |             0.7697    |            763   |      -0.0195805  |
| topology_only_control         | topology_atom |              0.735108    |             1.10667   |            763   |      -0.0339939  |

Positive contribution means the method worsened when that held-out atom's correction was removed, so the atom carries useful correction information. Negative or near-zero contribution means the atom is weak, noisy, or redundant with other atoms.

## 7. ML attribution and controls

| method                 | feature_group   |   median_importance_ns |   max_importance_ns |
|:-----------------------|:----------------|-----------------------:|--------------------:|
| cnn                    | stave           |            0.179993    |          0.460092   |
| cnn                    | waveform_shape  |            0.0001887   |          0.0175398  |
| cnn                    | pulse_shape     |           -0.00993201  |          0.0145465  |
| cnn                    | topology        |           -0.112631    |          0.00741596 |
| cnn                    | amplitude       |           -0.115579    |          0.0763435  |
| gradient_boosted_trees | stave           |            3.46225     |          4.00252    |
| gradient_boosted_trees | waveform_shape  |            0.309275    |          0.438094   |
| gradient_boosted_trees | pulse_shape     |            0.263762    |          0.376495   |
| gradient_boosted_trees | topology        |            0.0666534   |          0.113743   |
| gradient_boosted_trees | amplitude       |            0.0532654   |          0.184359   |
| mlp                    | stave           |            3.05121     |          3.37873    |
| mlp                    | waveform_shape  |            0.469299    |          0.919128   |
| mlp                    | pulse_shape     |            0.268467    |          0.432946   |
| mlp                    | topology        |            0.0889165   |          0.295194   |
| mlp                    | amplitude       |            0.0237625   |          0.158752   |
| ridge                  | stave           |            3.12212     |          4.4591     |
| ridge                  | waveform_shape  |            0.224905    |          0.435368   |
| ridge                  | topology        |            0.0170764   |          0.028093   |
| ridge                  | amplitude       |            0.0163572   |          0.0368127  |
| ridge                  | pulse_shape     |            0.01112     |          0.125441   |
| tcn_new_architecture   | stave           |            0.162373    |          0.433012   |
| tcn_new_architecture   | waveform_shape  |            0.00380205  |          0.00790796 |
| tcn_new_architecture   | pulse_shape     |            0.000345809 |          0.0857476  |
| tcn_new_architecture   | topology        |           -0.0706639   |          0.0502394  |
| tcn_new_architecture   | amplitude       |           -0.114835    |         -0.0226107  |

| method                        | stave   |   median_violation_fraction |   median_low_minus_high_pred_ns |
|:------------------------------|:--------|----------------------------:|--------------------------------:|
| amplitude_only_control        | B4      |                   0.152778  |                      -4.08423   |
| amplitude_only_control        | B6      |                   0.152778  |                       2.5242    |
| amplitude_only_control        | B8      |                   0.0520446 |                       1.87546   |
| analytic_amp_ridge            | B4      |                   0.258584  |                      -4.06338   |
| analytic_amp_ridge            | B6      |                   0.181141  |                       2.54888   |
| analytic_amp_ridge            | B8      |                   0.0780669 |                       1.89474   |
| cnn                           | B4      |                   0.50062   |                      -0.794239  |
| cnn                           | B6      |                   0.509186  |                      -0.330926  |
| cnn                           | B8      |                   0.503937  |                       0.0425032 |
| gradient_boosted_trees        | B4      |                   0.486877  |                      -4.14545   |
| gradient_boosted_trees        | B6      |                   0.478908  |                       2.37064   |
| gradient_boosted_trees        | B8      |                   0.487124  |                       1.92903   |
| hierarchical_shared_bins      | B4      |                   0         |                      -3.42845   |
| hierarchical_shared_bins      | B6      |                   0         |                       2.48025   |
| hierarchical_shared_bins      | B8      |                   0         |                       1.48997   |
| mlp                           | B4      |                   0.507511  |                      -4.14986   |
| mlp                           | B6      |                   0.5       |                       2.57542   |
| mlp                           | B8      |                   0.492126  |                       1.86947   |
| monotone_binned               | B4      |                   0.0459318 |                      -4.17672   |
| monotone_binned               | B6      |                   0         |                       2.63915   |
| monotone_binned               | B8      |                   0         |                       1.53391   |
| ridge                         | B4      |                   0.513123  |                      -4.28402   |
| ridge                         | B6      |                   0.48263   |                       2.48289   |
| ridge                         | B8      |                   0.502481  |                       1.96631   |
| shuffled_residual_hgb_control | B4      |                   0.486111  |                      -0.0115368 |
| shuffled_residual_hgb_control | B6      |                   0.488189  |                      -0.014129  |
| shuffled_residual_hgb_control | B8      |                   0.488197  |                      -0.0206708 |
| tcn_new_architecture          | B4      |                   0.498927  |                      -0.786532  |
| tcn_new_architecture          | B6      |                   0.505365  |                      -0.343981  |
| tcn_new_architecture          | B8      |                   0.495935  |                       0.0285868 |
| topology_only_control         | B4      |                   0.239157  |                      -4.05515   |
| topology_only_control         | B6      |                   0.254743  |                       2.55728   |
| topology_only_control         | B8      |                   0.101611  |                       1.64605   |

The monotonicity table is diagnostic, not a hard constraint for unconstrained ML: a physically clean timewalk correction should generally predict larger delays at lower amplitude, but waveform nuisance terms can break strict monotonicity.

Leakage and control checks:

| check                            |     min |   median |     max |
|:---------------------------------|--------:|---------:|--------:|
| features_include_run_or_event_id | 0       |    0     | 0       |
| fit_models_use_heldout_rows      | 0       |    0     | 0       |
| shuffled_control_sigma68_ns      | 2.69273 |    2.838 | 2.98443 |
| train_heldout_event_id_overlap   | 0       |    0     | 0       |
| train_heldout_run_overlap        | 0       |    0     | 0       |

## 8. Systematics and caveats

Run-block uncertainty is limited by seven Sample-II analysis runs, so CIs are coarse and sensitive to run 62/63 support. The event residual target is internally defined from downstream stave closure, not an external beam-time truth. Atom ablations are conditional interventions on the fitted correction, not causal statements about detector hardware. The CNN and TCN are deliberately laptop-scale; failure to win does not rule out larger architectures. Conversely, a point-estimate ML win is not a production adoption claim unless controls, monotonicity, and support behavior remain acceptable.

The strongest traditional comparator is constrained by amplitude monotonicity and shared-bin shrinkage. It is less flexible than HGB/MLP/TCN but more interpretable; therefore the winner is named as a benchmark result, while the report separately records whether the gain is physically plausible.

## 9. Verdict

The pooled point-estimate winner is **hierarchical_shared_bins**, sigma68 `1.358 ns` with run-bootstrap CI `[1.060, 1.501] ns`.
The best traditional method is **hierarchical_shared_bins**, sigma68 `1.358 ns`.
`result.json` verdict: `winner_named_with_no_split_leakage`.

## 10. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03n_1781056877_507_6c6921d4_hierarchical_timewalk_atom_attribution.py --config configs/s03n_1781056877_507_6c6921d4_hierarchical_timewalk_atom_attribution.yaml
```

Artifacts include `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `heldout_pair_residuals.csv`, `atom_ablation_attribution.csv`, `ml_permutation_attribution.csv`, `monotonicity_audit.csv`, `leakage_checks.csv`, model/coefficients tables, figures, `result.json`, and `manifest.json`.

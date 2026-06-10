# Study report: P03g - detector-label permutation stress test for stave-aware residual timing

- **Ticket:** 1781034623.1447.4a243444
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo labels or simulated timing targets
- **Split:** leave one Sample-II analysis run out across runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/p03g_1781034623_1447_4a243444_detector_label_permutation.yaml`

## Abstract

The benchmark winner named in `result.json` is **gradient_boosted_trees_real_stave**, with mean run-heldout pairwise sigma68 `1.0953` ns. The purpose is not only to minimize timing width, but to test whether explicit detector labels carry real waveform-shape information or merely static per-stave offsets.

## Raw-ROOT reproduction gate

Before fitting timing models, the selected-pulse count was recomputed directly from the B-stack ROOT files. The gate is amplitude > 1000 ADC after baseline subtraction on the four B staves.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimand and metrics

For each pulse in event `e` and stave `s`, the base corrected time is

`u_es = t_es - z_s v_TOF`,

where `z_s` is the nominal 2 cm-spaced downstream stave position and `v_TOF = 0.078 ns/cm`. The residual-learning target is

`r_es = u_es - (1/2) sum_{q != s} u_eq`,

using the other two downstream staves in the same event. A model predicts `rhat_es`; the final time is `t'_es = t_es - rhat_es`. Methods are scored on the three same-event pairwise differences after time-of-flight subtraction. The headline width is `sigma68 = (Q84 - Q16)/2`; event-block bootstraps provide 95% CIs within a held-out run, and run-block bootstraps provide label-policy CIs across the seven held-out runs.

## Methods

The traditional reference is template-phase timing followed by a transparent analytic timewalk ridge model. Candidate analytic models were `amp_only`, `amp_rise_shape`, and `amp_rise_shape_by_stave`; the selected candidate and alpha were chosen inside each training split by grouped-run CV.

The ML/NN benchmark contains ridge regression, histogram gradient-boosted trees, a heteroskedastic MLP, a 1D-CNN, and a new gated label-fusion CNN. Ridge and boosted-tree hyperparameters were selected by grouped-run CV on the real-stave policy and then frozen for all detector-label policies in that fold. Neural nets used the same fixed capacities across policies so policy effects are not confounded with architecture search.

Detector-label policies:

- `no_stave`: waveform and scalar shape features, no detector identity.
- `real_stave`: true downstream stave one-hot.
- `train_label_permutation`: training labels are randomly permuted; held-out labels are true.
- `heldout_label_permutation`: training labels are true; held-out labels are randomly permuted.
- `label_offset_*`: label-only train-run mean residual offsets, with no waveform samples.

## Real-stave head-to-head

| method                            | family                 | label_policy   |   mean_sigma68_ns |   median_sigma68_ns |   min_sigma68_ns |   max_sigma68_ns |   mean_full_rms_ns |   n_heldout_runs |
|:----------------------------------|:-----------------------|:---------------|------------------:|--------------------:|-----------------:|-----------------:|-------------------:|-----------------:|
| gradient_boosted_trees_real_stave | gradient_boosted_trees | real_stave     |           1.09533 |             1.09312 |         0.887566 |          1.2927  |            1.98802 |                7 |
| mlp_real_stave                    | mlp                    | real_stave     |           1.20674 |             1.22458 |         0.916518 |          1.39308 |            2.23944 |                7 |
| label_offset_real_stave           | label_only_offset      | real_stave     |           1.25209 |             1.31307 |         0.970774 |          1.37438 |            2.33729 |                7 |
| ridge_real_stave                  | ridge                  | real_stave     |           1.30152 |             1.3094  |         1.10729  |          1.43121 |            2.31849 |                7 |
| gated_label_fusion_real_stave     | new_gated_label_fusion | real_stave     |           1.32367 |             1.35937 |         1.14886  |          1.51636 |            2.3291  |                7 |
| cnn_real_stave                    | cnn                    | real_stave     |           1.3607  |             1.33062 |         1.28166  |          1.54419 |            2.32124 |                7 |
| traditional_analytic_timewalk     | traditional            | none           |           1.4964  |             1.45871 |         1.18748  |          2.12996 |            2.50469 |                7 |

## Detector-label policy summary

| method                                           | family                 | label_policy              |   mean_sigma68_ns |   median_sigma68_ns |   mean_full_rms_ns |   n_heldout_runs |
|:-------------------------------------------------|:-----------------------|:--------------------------|------------------:|--------------------:|-------------------:|-----------------:|
| cnn_real_stave                                   | cnn                    | real_stave                |           1.3607  |             1.33062 |            2.32124 |                7 |
| cnn_no_stave                                     | cnn                    | no_stave                  |           1.73289 |             1.67515 |            2.51765 |                7 |
| cnn_train_label_permutation                      | cnn                    | train_label_permutation   |           1.79502 |             1.76198 |            2.62293 |                7 |
| cnn_heldout_label_permutation                    | cnn                    | heldout_label_permutation |           2.46264 |             2.37419 |            3.07175 |                7 |
| gradient_boosted_trees_real_stave                | gradient_boosted_trees | real_stave                |           1.09533 |             1.09312 |            1.98802 |                7 |
| gradient_boosted_trees_train_label_permutation   | gradient_boosted_trees | train_label_permutation   |           1.45608 |             1.41673 |            2.15833 |                7 |
| gradient_boosted_trees_no_stave                  | gradient_boosted_trees | no_stave                  |           1.46291 |             1.41358 |            2.17036 |                7 |
| gradient_boosted_trees_heldout_label_permutation | gradient_boosted_trees | heldout_label_permutation |           2.49342 |             2.43406 |            3.00619 |                7 |
| label_offset_real_stave                          | label_only_offset      | real_stave                |           1.25209 |             1.31307 |            2.33729 |                7 |
| label_offset_train_label_permutation             | label_only_offset      | train_label_permutation   |           1.497   |             1.45126 |            2.51077 |                7 |
| label_offset_heldout_label_permutation           | label_only_offset      | heldout_label_permutation |           2.5957  |             2.53619 |            3.21877 |                7 |
| mlp_real_stave                                   | mlp                    | real_stave                |           1.20674 |             1.22458 |            2.23944 |                7 |
| mlp_train_label_permutation                      | mlp                    | train_label_permutation   |           1.59276 |             1.56262 |            2.54179 |                7 |
| mlp_no_stave                                     | mlp                    | no_stave                  |           1.65052 |             1.56176 |            2.58604 |                7 |
| mlp_heldout_label_permutation                    | mlp                    | heldout_label_permutation |           2.38466 |             2.37817 |            3.06789 |                7 |
| gated_label_fusion_real_stave                    | new_gated_label_fusion | real_stave                |           1.32367 |             1.35937 |            2.3291  |                7 |
| gated_label_fusion_train_label_permutation       | new_gated_label_fusion | train_label_permutation   |           1.65954 |             1.61054 |            2.5141  |                7 |
| gated_label_fusion_no_stave                      | new_gated_label_fusion | no_stave                  |           1.71798 |             1.71313 |            2.57042 |                7 |
| gated_label_fusion_heldout_label_permutation     | new_gated_label_fusion | heldout_label_permutation |           2.45298 |             2.5818  |            3.04155 |                7 |
| ridge_real_stave                                 | ridge                  | real_stave                |           1.30152 |             1.3094  |            2.31849 |                7 |
| ridge_train_label_permutation                    | ridge                  | train_label_permutation   |           1.72959 |             1.66485 |            2.5657  |                7 |
| ridge_no_stave                                   | ridge                  | no_stave                  |           1.73193 |             1.69066 |            2.56548 |                7 |
| ridge_heldout_label_permutation                  | ridge                  | heldout_label_permutation |           2.51931 |             2.4461  |            3.14537 |                7 |

## Run-bootstrap label stress gaps

Negative real-minus-control values mean the true detector labels beat that control; intervals covering zero indicate weak evidence that true labels are doing more than the control.

| comparison                                                                               | method                            | control                                          |   n_runs |   mean_delta_sigma68_ns |   run_bootstrap_ci_low |   run_bootstrap_ci_high |   leave_one_run_min |   leave_one_run_max |
|:-----------------------------------------------------------------------------------------|:----------------------------------|:-------------------------------------------------|---------:|------------------------:|-----------------------:|------------------------:|--------------------:|--------------------:|
| gradient_boosted_trees_real_stave_minus_gradient_boosted_trees_heldout_label_permutation | gradient_boosted_trees_real_stave | gradient_boosted_trees_heldout_label_permutation |        7 |               -1.39808  |              -1.58515  |               -1.23197  |           -1.45292  |           -1.32043  |
| label_offset_real_stave_minus_label_offset_heldout_label_permutation                     | label_offset_real_stave           | label_offset_heldout_label_permutation           |        7 |               -1.34361  |              -1.54298  |               -1.16702  |           -1.41137  |           -1.25781  |
| ridge_real_stave_minus_ridge_heldout_label_permutation                                   | ridge_real_stave                  | ridge_heldout_label_permutation                  |        7 |               -1.21779  |              -1.39271  |               -1.07246  |           -1.25959  |           -1.13854  |
| mlp_real_stave_minus_mlp_heldout_label_permutation                                       | mlp_real_stave                    | mlp_heldout_label_permutation                    |        7 |               -1.17792  |              -1.41874  |               -0.98132  |           -1.2521   |           -1.07786  |
| gated_label_fusion_real_stave_minus_gated_label_fusion_heldout_label_permutation         | gated_label_fusion_real_stave     | gated_label_fusion_heldout_label_permutation     |        7 |               -1.12931  |              -1.43377  |               -0.753815 |           -1.2815   |           -1.04621  |
| cnn_real_stave_minus_cnn_heldout_label_permutation                                       | cnn_real_stave                    | cnn_heldout_label_permutation                    |        7 |               -1.10194  |              -1.36509  |               -0.861191 |           -1.18661  |           -0.992156 |
| mlp_real_stave_minus_mlp_no_stave                                                        | mlp_real_stave                    | mlp_no_stave                                     |        7 |               -0.44378  |              -0.618999 |               -0.305888 |           -0.475932 |           -0.366197 |
| cnn_real_stave_minus_cnn_train_label_permutation                                         | cnn_real_stave                    | cnn_train_label_permutation                      |        7 |               -0.434326 |              -0.624854 |               -0.300286 |           -0.470852 |           -0.34536  |
| ridge_real_stave_minus_ridge_no_stave                                                    | ridge_real_stave                  | ridge_no_stave                                   |        7 |               -0.430409 |              -0.600124 |               -0.301305 |           -0.459589 |           -0.353812 |
| ridge_real_stave_minus_ridge_train_label_permutation                                     | ridge_real_stave                  | ridge_train_label_permutation                    |        7 |               -0.428072 |              -0.602376 |               -0.297207 |           -0.457354 |           -0.351291 |
| gated_label_fusion_real_stave_minus_gated_label_fusion_no_stave                          | gated_label_fusion_real_stave     | gated_label_fusion_no_stave                      |        7 |               -0.394314 |              -0.566975 |               -0.262132 |           -0.431534 |           -0.317012 |
| mlp_real_stave_minus_mlp_train_label_permutation                                         | mlp_real_stave                    | mlp_train_label_permutation                      |        7 |               -0.386027 |              -0.542265 |               -0.239801 |           -0.434399 |           -0.331462 |
| cnn_real_stave_minus_cnn_no_stave                                                        | cnn_real_stave                    | cnn_no_stave                                     |        7 |               -0.372196 |              -0.584989 |               -0.207834 |           -0.412402 |           -0.276551 |
| gradient_boosted_trees_real_stave_minus_gradient_boosted_trees_no_stave                  | gradient_boosted_trees_real_stave | gradient_boosted_trees_no_stave                  |        7 |               -0.367581 |              -0.536367 |               -0.233943 |           -0.408698 |           -0.297172 |
| gradient_boosted_trees_real_stave_minus_gradient_boosted_trees_train_label_permutation   | gradient_boosted_trees_real_stave | gradient_boosted_trees_train_label_permutation   |        7 |               -0.360744 |              -0.511784 |               -0.235068 |           -0.400197 |           -0.300805 |
| gated_label_fusion_real_stave_minus_gated_label_fusion_train_label_permutation           | gated_label_fusion_real_stave     | gated_label_fusion_train_label_permutation       |        7 |               -0.335867 |              -0.524206 |               -0.171358 |           -0.384623 |           -0.260306 |
| label_offset_real_stave_minus_label_offset_train_label_permutation                       | label_offset_real_stave           | label_offset_train_label_permutation             |        7 |               -0.244914 |              -0.470063 |               -0.100704 |           -0.285519 |           -0.138871 |

## Per-heldout-run metrics

|   heldout_run | method                                           |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_baseline_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|--------------:|:-------------------------------------------------|-------------:|---------:|----------:|--------------:|-----------------------:|---------------:|----------------:|-------------------:|
|            58 | gradient_boosted_trees_real_stave                |     0.887566 | 0.719018 |   1.13845 |       2.28743 |            -0.299917   |   -0.532863    |     -0.0759503  |                219 |
|            58 | mlp_real_stave                                   |     0.916518 | 0.77874  |   1.04485 |       2.30117 |            -0.270965   |   -0.513741    |     -0.16463    |                219 |
|            58 | label_offset_real_stave                          |     0.970774 | 0.862814 |   1.12468 |       2.61396 |            -0.216709   |   -0.404537    |     -0.0628074  |                219 |
|            58 | ridge_real_stave                                 |     1.10729  | 0.972222 |   1.32793 |       2.7138  |            -0.0801939  |   -0.294722    |      0.101198   |                219 |
|            58 | label_offset_train_label_permutation             |     1.17525  | 1.12624  |   1.42669 |       2.67264 |            -0.0122365  |   -0.030224    |      0.00598992 |                219 |
|            58 | traditional_analytic_timewalk                    |     1.18748  | 1.1367   |   1.45037 |       2.67793 |             0          |    0           |      0          |                219 |
|            58 | gated_label_fusion_real_stave                    |     1.26072  | 1.11695  |   1.43809 |       2.57279 |             0.0732394  |   -0.15502     |      0.260907   |                219 |
|            58 | cnn_real_stave                                   |     1.38498  | 1.22316  |   1.53748 |       2.73372 |             0.197494   |   -0.0958758   |      0.366153   |                219 |
|            58 | gated_label_fusion_no_stave                      |     1.43171  | 1.27382  |   1.56611 |       2.89894 |             0.24423    |    0.0856223   |      0.314162   |                219 |
|            58 | mlp_no_stave                                     |     1.51041  | 1.35489  |   1.67907 |       2.81777 |             0.322923   |    0.142545    |      0.411107   |                219 |
|            58 | cnn_no_stave                                     |     1.52795  | 1.37555  |   1.79781 |       2.56573 |             0.340467   |    0.21001     |      0.508271   |                219 |
|            58 | mlp_train_label_permutation                      |     1.56262  | 1.44109  |   1.77189 |       2.79557 |             0.375135   |    0.241029    |      0.495769   |                219 |
|            58 | gradient_boosted_trees_train_label_permutation   |     1.60794  | 1.38323  |   1.8173  |       2.55552 |             0.420458   |    0.14492     |      0.601184   |                219 |
|            58 | gated_label_fusion_train_label_permutation       |     1.61054  | 1.4678   |   1.88421 |       2.75772 |             0.423054   |    0.279604    |      0.578972   |                219 |
|            58 | ridge_train_label_permutation                    |     1.63935  | 1.36631  |   1.82956 |       2.97364 |             0.451868   |    0.168347    |      0.581573   |                219 |
|            58 | ridge_no_stave                                   |     1.64649  | 1.37617  |   1.8423  |       2.97693 |             0.459011   |    0.180506    |      0.592499   |                219 |
|            58 | gradient_boosted_trees_no_stave                  |     1.6776   | 1.47784  |   1.89399 |       2.64073 |             0.490121   |    0.239119    |      0.670487   |                219 |
|            58 | cnn_train_label_permutation                      |     1.76198  | 1.51243  |   2.0756  |       2.97224 |             0.5745     |    0.305029    |      0.78888    |                219 |
|            58 | cnn_heldout_label_permutation                    |     1.97892  | 1.66857  |   2.36878 |       3.19327 |             0.791434   |    0.441048    |      1.14615    |                219 |
|            58 | mlp_heldout_label_permutation                    |     2.05054  | 1.75638  |   2.38047 |       3.46397 |             0.863057   |    0.56739     |      1.17224    |                219 |
|            58 | ridge_heldout_label_permutation                  |     2.30005  | 1.92381  |   2.9109  |       3.54625 |             1.11257    |    0.709573    |      1.67944    |                219 |
|            58 | gradient_boosted_trees_heldout_label_permutation |     2.37396  | 2.00897  |   2.68705 |       3.20833 |             1.18647    |    0.7795      |      1.49713    |                219 |
|            58 | label_offset_heldout_label_permutation           |     2.436    | 1.98141  |   3.11165 |       3.22379 |             1.24852    |    0.788327    |      1.84973    |                219 |
|            58 | gated_label_fusion_heldout_label_permutation     |     2.48161  | 2.04789  |   2.77709 |       3.42756 |             1.29412    |    0.833821    |      1.57919    |                219 |
|            59 | gradient_boosted_trees_real_stave                |     1.04117  | 0.97929  |   1.10635 |       2.04462 |            -0.417534   |   -0.512013    |     -0.31727    |               2289 |
|            59 | mlp_real_stave                                   |     1.22458  | 1.16257  |   1.29709 |       2.35651 |            -0.234127   |   -0.328406    |     -0.123936   |               2289 |
|            59 | cnn_real_stave                                   |     1.28693  | 1.2344   |   1.34946 |       2.34288 |            -0.171782   |   -0.248534    |     -0.0824286  |               2289 |
|            59 | ridge_real_stave                                 |     1.31335  | 1.25201  |   1.37017 |       2.31197 |            -0.145362   |   -0.245675    |     -0.045516   |               2289 |
|            59 | label_offset_real_stave                          |     1.32039  | 1.29134  |   1.36275 |       2.43134 |            -0.138319   |   -0.218988    |     -0.0531071  |               2289 |
|            59 | gradient_boosted_trees_no_stave                  |     1.36059  | 1.31614  |   1.41561 |       2.28958 |            -0.0981143  |   -0.182522    |     -0.0125939  |               2289 |
|            59 | gated_label_fusion_real_stave                    |     1.36372  | 1.29974  |   1.43427 |       2.49597 |            -0.0949855  |   -0.12089     |     -0.0611463  |               2289 |
|            59 | gradient_boosted_trees_train_label_permutation   |     1.36773  | 1.31394  |   1.41939 |       2.28266 |            -0.0909823  |   -0.181219    |     -0.0101675  |               2289 |
|            59 | label_offset_train_label_permutation             |     1.45126  | 1.38167  |   1.52323 |       2.53741 |            -0.00744855 |   -0.0157388   |      0.00357541 |               2289 |
|            59 | traditional_analytic_timewalk                    |     1.45871  | 1.38869  |   1.5326  |       2.54019 |             0          |    0           |      0          |               2289 |
|            59 | mlp_train_label_permutation                      |     1.48449  | 1.43309  |   1.54588 |       2.53451 |             0.0257817  |   -0.0138839   |      0.0677742  |               2289 |
|            59 | gated_label_fusion_train_label_permutation       |     1.53331  | 1.477    |   1.59072 |       2.55036 |             0.0746047  |    0.0286775   |      0.121402   |               2289 |
|            59 | mlp_no_stave                                     |     1.647    | 1.59221  |   1.71682 |       2.55829 |             0.188287   |    0.136534    |      0.254766   |               2289 |
|            59 | ridge_train_label_permutation                    |     1.66485  | 1.60125  |   1.73169 |       2.51626 |             0.20614    |    0.148054    |      0.276761   |               2289 |
|            59 | cnn_train_label_permutation                      |     1.68743  | 1.63946  |   1.73664 |       2.53241 |             0.228718   |    0.179852    |      0.280637   |               2289 |
|            59 | ridge_no_stave                                   |     1.69149  | 1.62261  |   1.7555  |       2.52778 |             0.232778   |    0.165443    |      0.296445   |               2289 |
|            59 | gated_label_fusion_no_stave                      |     1.71313  | 1.65533  |   1.76882 |       2.54393 |             0.254419   |    0.206561    |      0.312759   |               2289 |
|            59 | cnn_no_stave                                     |     1.77734  | 1.71075  |   1.82183 |       2.56338 |             0.318636   |    0.25812     |      0.365718   |               2289 |
|            59 | mlp_heldout_label_permutation                    |     2.28514  | 2.18955  |   2.39631 |       2.97623 |             0.826436   |    0.724405    |      0.956103   |               2289 |
|            59 | gradient_boosted_trees_heldout_label_permutation |     2.39068  | 2.27638  |   2.51373 |       2.93266 |             0.931974   |    0.81511     |      1.0673     |               2289 |
|            59 | ridge_heldout_label_permutation                  |     2.50605  | 2.40687  |   2.65556 |       3.03964 |             1.04734    |    0.938904    |      1.19486    |               2289 |
|            59 | cnn_heldout_label_permutation                    |     2.53242  | 2.40032  |   2.64768 |       3.05545 |             1.07372    |    0.961477    |      1.19531    |               2289 |
|            59 | label_offset_heldout_label_permutation           |     2.61461  | 2.48593  |   2.7865  |       3.22791 |             1.1559     |    1.03578     |      1.32353    |               2289 |
|            59 | gated_label_fusion_heldout_label_permutation     |     2.62482  | 2.50838  |   2.7411  |       3.10642 |             1.16611    |    1.06233     |      1.27758    |               2289 |
|            60 | gradient_boosted_trees_real_stave                |     1.11683  | 1.06178  |   1.19002 |       1.95103 |            -0.226877   |   -0.306729    |     -0.135755   |               2424 |
|            60 | label_offset_real_stave                          |     1.17212  | 1.10716  |   1.30367 |       2.34921 |            -0.171584   |   -0.247744    |     -0.0339236  |               2424 |
|            60 | mlp_real_stave                                   |     1.1748   | 1.10788  |   1.24981 |       2.16618 |            -0.168909   |   -0.254783    |     -0.0833952  |               2424 |
|            60 | gated_label_fusion_real_stave                    |     1.19732  | 1.1402   |   1.2522  |       2.1878  |            -0.146389   |   -0.201447    |     -0.0816381  |               2424 |
|            60 | cnn_real_stave                                   |     1.28166  | 1.21881  |   1.33943 |       2.21123 |            -0.0620454  |   -0.13815     |      0.017163   |               2424 |
|            60 | ridge_real_stave                                 |     1.3094   | 1.26014  |   1.3672  |       2.22879 |            -0.0342997  |   -0.104705    |      0.0500259  |               2424 |
|            60 | label_offset_train_label_permutation             |     1.32791  | 1.26159  |   1.3864  |       2.38703 |            -0.0157975  |   -0.0283914   |     -0.00595047 |               2424 |
|            60 | gradient_boosted_trees_train_label_permutation   |     1.33546  | 1.28621  |   1.39789 |       1.95166 |            -0.00824814 |   -0.0904157   |      0.0625134  |               2424 |
|            60 | traditional_analytic_timewalk                    |     1.3437   | 1.27706  |   1.40483 |       2.39529 |             0          |    0           |      0          |               2424 |
|            60 | gradient_boosted_trees_no_stave                  |     1.35041  | 1.28285  |   1.39547 |       1.9502  |             0.00670932 |   -0.0806281   |      0.0692475  |               2424 |
|            60 | mlp_train_label_permutation                      |     1.43664  | 1.39488  |   1.49846 |       2.37874 |             0.0929392  |    0.0451792   |      0.147015   |               2424 |
|            60 | mlp_no_stave                                     |     1.48732  | 1.44013  |   1.55092 |       2.44441 |             0.143611   |    0.0960627   |      0.194816   |               2424 |
|            60 | gated_label_fusion_no_stave                      |     1.50724  | 1.45191  |   1.55685 |       2.36006 |             0.163536   |    0.110676    |      0.207175   |               2424 |
|            60 | ridge_train_label_permutation                    |     1.56798  | 1.51556  |   1.6334  |       2.32573 |             0.224276   |    0.161025    |      0.289436   |               2424 |
|            60 | cnn_no_stave                                     |     1.56994  | 1.50864  |   1.63273 |       2.37583 |             0.226232   |    0.168613    |      0.286824   |               2424 |
|            60 | ridge_no_stave                                   |     1.59508  | 1.53799  |   1.65162 |       2.34061 |             0.251374   |    0.186093    |      0.311416   |               2424 |
|            60 | gated_label_fusion_train_label_permutation       |     1.63201  | 1.58626  |   1.69766 |       2.41808 |             0.288309   |    0.234334    |      0.359161   |               2424 |
|            60 | cnn_train_label_permutation                      |     1.63946  | 1.56955  |   1.69274 |       2.46647 |             0.295751   |    0.228334    |      0.352307   |               2424 |
|            60 | cnn_heldout_label_permutation                    |     2.37419  | 2.26797  |   2.46093 |       2.89239 |             1.03048    |    0.903992    |      1.11736    |               2424 |
|            60 | mlp_heldout_label_permutation                    |     2.37817  | 2.27059  |   2.50023 |       2.90808 |             1.03447    |    0.929763    |      1.17542    |               2424 |
|            60 | label_offset_heldout_label_permutation           |     2.44078  | 2.30029  |   2.60765 |       3.08997 |             1.09707    |    0.942699    |      1.25026    |               2424 |
|            60 | ridge_heldout_label_permutation                  |     2.4461   | 2.33929  |   2.55853 |       2.92103 |             1.1024     |    0.972966    |      1.21464    |               2424 |
|            60 | gradient_boosted_trees_heldout_label_permutation |     2.62603  | 2.50515  |   2.74681 |       3.00635 |             1.28233    |    1.15829     |      1.41369    |               2424 |
|            60 | gated_label_fusion_heldout_label_permutation     |     2.65022  | 2.55706  |   2.7772  |       3.11667 |             1.30651    |    1.20279     |      1.43805    |               2424 |
|            61 | gradient_boosted_trees_real_stave                |     1.07778  | 1.00716  |   1.13477 |       2.39352 |            -1.05219    |   -1.14036     |     -0.907268   |               2799 |
|            61 | mlp_real_stave                                   |     1.23695  | 1.17197  |   1.2772  |       2.74661 |            -0.893019   |   -0.971231    |     -0.759166   |               2799 |
|            61 | label_offset_real_stave                          |     1.25958  | 1.20551  |   1.29756 |       2.57022 |            -0.870382   |   -0.938919    |     -0.744776   |               2799 |
|            61 | ridge_real_stave                                 |     1.28457  | 1.2207   |   1.34908 |       2.81904 |            -0.845393   |   -0.918496    |     -0.707248   |               2799 |
|            61 | cnn_real_stave                                   |     1.29188  | 1.231    |   1.33701 |       2.6144  |            -0.838082   |   -0.915568    |     -0.696544   |               2799 |
|            61 | gated_label_fusion_real_stave                    |     1.35937  | 1.29248  |   1.41686 |       2.65329 |            -0.770594   |   -0.83606     |     -0.654686   |               2799 |
|            61 | gradient_boosted_trees_no_stave                  |     1.60578  | 1.55259  |   1.65907 |       2.53058 |            -0.524185   |   -0.611166    |     -0.38197    |               2799 |
|            61 | gradient_boosted_trees_train_label_permutation   |     1.61715  | 1.55445  |   1.66845 |       2.53435 |            -0.512809   |   -0.606783    |     -0.372672   |               2799 |
|            61 | mlp_train_label_permutation                      |     1.95036  | 1.86948  |   2.02458 |       3.08209 |            -0.179607   |   -0.226711    |     -0.0695664  |               2799 |
|            61 | traditional_analytic_timewalk                    |     2.12996  | 1.98647  |   2.21114 |       3.00806 |             0          |    0           |      0          |               2799 |
|            61 | label_offset_train_label_permutation             |     2.14076  | 2.01267  |   2.23208 |       3.01965 |             0.0107927  |    0.00399165  |      0.0331587  |               2799 |
|            61 | mlp_no_stave                                     |     2.14622  | 2.05482  |   2.21954 |       3.09166 |             0.016258   |   -0.0362385   |      0.123417   |               2799 |
|            61 | gated_label_fusion_train_label_permutation       |     2.14861  | 2.05872  |   2.24765 |       3.02236 |             0.0186411  |   -0.0127973   |      0.106727   |               2799 |
|            61 | ridge_train_label_permutation                    |     2.17332  | 2.07633  |   2.25671 |       3.28694 |             0.0433589  |   -0.0313916   |      0.165963   |               2799 |
|            61 | ridge_no_stave                                   |     2.17456  | 2.07776  |   2.25815 |       3.2872  |             0.0445961  |   -0.0305558   |      0.167154   |               2799 |
|            61 | gated_label_fusion_no_stave                      |     2.21749  | 2.12044  |   2.30588 |       3.14811 |             0.0875305  |    0.0254794   |      0.21469    |               2799 |
|            61 | cnn_no_stave                                     |     2.23795  | 2.15387  |   2.31688 |       3.14681 |             0.107986   |    0.0534433   |      0.21983    |               2799 |
|            61 | cnn_train_label_permutation                      |     2.26001  | 2.17677  |   2.32912 |       3.16067 |             0.130042   |    0.0633081   |      0.253358   |               2799 |
|            61 | gradient_boosted_trees_heldout_label_permutation |     2.94179  | 2.80138  |   3.06296 |       3.51783 |             0.811827   |    0.652566    |      1.01061    |               2799 |
|            61 | ridge_heldout_label_permutation                  |     2.97787  | 2.85915  |   3.07139 |       3.77897 |             0.847903   |    0.730776    |      1.02443    |               2799 |
|            61 | gated_label_fusion_heldout_label_permutation     |     2.98729  | 2.8626   |   3.10877 |       3.6771  |             0.857326   |    0.734782    |      1.0524     |               2799 |
|            61 | mlp_heldout_label_permutation                    |     3.01524  | 2.90826  |   3.13302 |       3.7351  |             0.885279   |    0.780671    |      1.07152    |               2799 |
|            61 | cnn_heldout_label_permutation                    |     3.05256  | 2.94117  |   3.17519 |       3.63441 |             0.922594   |    0.796492    |      1.11924    |               2799 |
|            61 | label_offset_heldout_label_permutation           |     3.11798  | 3.02002  |   3.2037  |       3.69081 |             0.98802    |    0.882249    |      1.15127    |               2799 |
|            62 | gradient_boosted_trees_real_stave                |     1.09312  | 1.0472   |   1.15041 |       2.11647 |            -0.375887   |   -0.441494    |     -0.303958   |               2421 |
|            62 | gated_label_fusion_real_stave                    |     1.14886  | 1.08431  |   1.23969 |       2.46968 |            -0.320146   |   -0.391292    |     -0.241538   |               2421 |
|            62 | mlp_real_stave                                   |     1.2206   | 1.16565  |   1.27271 |       2.26272 |            -0.248405   |   -0.325507    |     -0.173509   |               2421 |
|            62 | ridge_real_stave                                 |     1.28909  | 1.2286   |   1.34701 |       2.33217 |            -0.179912   |   -0.25638     |     -0.116734   |               2421 |
|            62 | label_offset_real_stave                          |     1.31307  | 1.24148  |   1.36893 |       2.47166 |            -0.155939   |   -0.231394    |     -0.087772   |               2421 |
|            62 | cnn_real_stave                                   |     1.33062  | 1.26261  |   1.39707 |       2.39486 |            -0.138384   |   -0.221167    |     -0.0508378  |               2421 |
|            62 | gradient_boosted_trees_train_label_permutation   |     1.39809  | 1.34347  |   1.45822 |       2.28011 |            -0.0709167  |   -0.134668    |      0.0159093  |               2421 |
|            62 | gradient_boosted_trees_no_stave                  |     1.4032   | 1.34453  |   1.46891 |       2.26905 |            -0.0658093  |   -0.131178    |      0.0293139  |               2421 |
|            62 | traditional_analytic_timewalk                    |     1.469    | 1.41088  |   1.51941 |       2.58419 |             0          |    0           |      0          |               2421 |
|            62 | label_offset_train_label_permutation             |     1.48115  | 1.42588  |   1.53803 |       2.5925  |             0.0121475  |    0.00536111  |      0.0216597  |               2421 |
|            62 | mlp_no_stave                                     |     1.56176  | 1.49806  |   1.62022 |       2.60556 |             0.0927516  |    0.0597477   |      0.129847   |               2421 |
|            62 | mlp_train_label_permutation                      |     1.59402  | 1.52554  |   1.65846 |       2.64122 |             0.125012   |    0.0833508   |      0.16022    |               2421 |
|            62 | gated_label_fusion_train_label_permutation       |     1.62275  | 1.57766  |   1.68873 |       2.58546 |             0.153746   |    0.12324     |      0.202223   |               2421 |
|            62 | gated_label_fusion_no_stave                      |     1.64884  | 1.5949   |   1.71243 |       2.47677 |             0.179838   |    0.136227    |      0.228927   |               2421 |
|            62 | ridge_no_stave                                   |     1.69066  | 1.62883  |   1.7541  |       2.53338 |             0.221658   |    0.167001    |      0.282976   |               2421 |
|            62 | cnn_no_stave                                     |     1.69634  | 1.64089  |   1.75261 |       2.54298 |             0.227331   |    0.178291    |      0.277135   |               2421 |
|            62 | ridge_train_label_permutation                    |     1.71056  | 1.64571  |   1.77777 |       2.5453  |             0.241559   |    0.186093    |      0.303705   |               2421 |
|            62 | cnn_train_label_permutation                      |     1.77484  | 1.73097  |   1.83804 |       2.69282 |             0.305838   |    0.266696    |      0.359789   |               2421 |
|            62 | mlp_heldout_label_permutation                    |     2.45813  | 2.37802  |   2.60454 |       3.04371 |             0.989129   |    0.896791    |      1.14005    |               2421 |
|            62 | gradient_boosted_trees_heldout_label_permutation |     2.46014  | 2.35731  |   2.60135 |       3.11184 |             0.991137   |    0.868436    |      1.12805    |               2421 |
|            62 | label_offset_heldout_label_permutation           |     2.53619  | 2.38785  |   2.70092 |       3.33451 |             1.06718    |    0.924417    |      1.23332    |               2421 |
|            62 | gated_label_fusion_heldout_label_permutation     |     2.5818   | 2.44285  |   2.66255 |       3.0823  |             1.1128     |    0.974383    |      1.19007    |               2421 |
|            62 | cnn_heldout_label_permutation                    |     2.58946  | 2.44473  |   2.71373 |       3.17303 |             1.12045    |    0.97627     |      1.24262    |               2421 |
|            62 | ridge_heldout_label_permutation                  |     2.60569  | 2.44735  |   2.72461 |       3.18296 |             1.13669    |    0.992617    |      1.2459     |               2421 |
|            63 | gradient_boosted_trees_real_stave                |     1.15817  | 1.06516  |   1.24755 |       1.91238 |            -0.233156   |   -0.343121    |     -0.109996   |               1110 |
|            63 | mlp_real_stave                                   |     1.28065  | 1.21352  |   1.36783 |       2.34495 |            -0.110672   |   -0.216108    |      0.00714434 |               1110 |
|            63 | label_offset_real_stave                          |     1.37438  | 1.24732  |   1.44422 |       2.52939 |            -0.0169447  |   -0.144089    |      0.0807819  |               1110 |
|            63 | label_offset_train_label_permutation             |     1.37566  | 1.29029  |   1.44957 |       2.61894 |            -0.0156596  |   -0.0381131   |      0.006749   |               1110 |
|            63 | ridge_real_stave                                 |     1.37572  | 1.29064  |   1.45616 |       2.41305 |            -0.0156016  |   -0.120796    |      0.0926526  |               1110 |
|            63 | traditional_analytic_timewalk                    |     1.39132  | 1.30277  |   1.4704  |       2.62807 |             0          |    0           |      0          |               1110 |
|            63 | cnn_real_stave                                   |     1.40462  | 1.31671  |   1.49098 |       2.44082 |             0.0132999  |   -0.105267    |      0.140073   |               1110 |
|            63 | gradient_boosted_trees_no_stave                  |     1.42923  | 1.35254  |   1.50663 |       2.03745 |             0.0379074  |   -0.0562518   |      0.144173   |               1110 |
|            63 | gradient_boosted_trees_train_label_permutation   |     1.44944  | 1.37224  |   1.53505 |       2.06593 |             0.0581188  |   -0.043746    |      0.166494   |               1110 |
|            63 | gated_label_fusion_real_stave                    |     1.51636  | 1.41951  |   1.61806 |       2.5014  |             0.125041   |    0.00317659  |      0.266727   |               1110 |
|            63 | mlp_no_stave                                     |     1.55699  | 1.49295  |   1.61453 |       2.75641 |             0.165666   |    0.0956815   |      0.246508   |               1110 |
|            63 | gated_label_fusion_train_label_permutation       |     1.5597   | 1.48715  |   1.62993 |       2.62438 |             0.168375   |    0.0951957   |      0.231425   |               1110 |
|            63 | cnn_train_label_permutation                      |     1.61979  | 1.54235  |   1.69721 |       2.60054 |             0.22847    |    0.152213    |      0.321421   |               1110 |
|            63 | ridge_train_label_permutation                    |     1.6281   | 1.53603  |   1.73169 |       2.57347 |             0.236778   |    0.150102    |      0.35387    |               1110 |
|            63 | ridge_no_stave                                   |     1.63105  | 1.53724  |   1.72938 |       2.57318 |             0.239725   |    0.150196    |      0.350306   |               1110 |
|            63 | mlp_train_label_permutation                      |     1.63236  | 1.55903  |   1.71727 |       2.65185 |             0.241035   |    0.162693    |      0.344287   |               1110 |
|            63 | cnn_no_stave                                     |     1.64558  | 1.58156  |   1.73685 |       2.62045 |             0.25426    |    0.185248    |      0.351863   |               1110 |
|            63 | gated_label_fusion_heldout_label_permutation     |     1.73254  | 1.6476   |   1.81764 |       2.65794 |             0.341223   |    0.257094    |      0.447956   |               1110 |
|            63 | gated_label_fusion_no_stave                      |     1.7515   | 1.68361  |   1.85794 |       2.70281 |             0.360177   |    0.282173    |      0.474416   |               1110 |
|            63 | gradient_boosted_trees_heldout_label_permutation |     2.22724  | 2.08382  |   2.3827  |       2.84554 |             0.835919   |    0.698601    |      1.00899    |               1110 |
|            63 | cnn_heldout_label_permutation                    |     2.33706  | 2.18151  |   2.47734 |       3.12888 |             0.945738   |    0.808796    |      1.09668    |               1110 |
|            63 | mlp_heldout_label_permutation                    |     2.37945  | 2.19261  |   2.49426 |       3.01099 |             0.988125   |    0.818121    |      1.09607    |               1110 |
|            63 | ridge_heldout_label_permutation                  |     2.40118  | 2.27465  |   2.5574  |       3.11936 |             1.00986    |    0.893265    |      1.15738    |               1110 |
|            63 | label_offset_heldout_label_permutation           |     2.73299  | 2.42162  |   2.97729 |       3.34671 |             1.34167    |    1.02721     |      1.58114    |               1110 |
|            65 | gradient_boosted_trees_real_stave                |     1.2927   | 0.934562 |   1.44285 |       1.21069 |            -0.201939   |   -0.538734    |      0.017987   |                198 |
|            65 | label_offset_real_stave                          |     1.3543   | 1.06455  |   1.6088  |       1.39524 |            -0.140337   |   -0.462418    |      0.169596   |                198 |
|            65 | mlp_real_stave                                   |     1.39308  | 1.15952  |   1.78653 |       1.49795 |            -0.101563   |   -0.364641    |      0.3514     |                198 |
|            65 | gradient_boosted_trees_no_stave                  |     1.41358  | 1.11454  |   1.68024 |       1.47493 |            -0.0810578  |   -0.406586    |      0.215413   |                198 |
|            65 | gradient_boosted_trees_train_label_permutation   |     1.41673  | 1.15509  |   1.71272 |       1.43806 |            -0.0779145  |   -0.372205    |      0.230116   |                198 |
|            65 | gated_label_fusion_real_stave                    |     1.41933  | 1.13127  |   1.63015 |       1.42279 |            -0.0753129  |   -0.402252    |      0.175826   |                198 |
|            65 | ridge_real_stave                                 |     1.43121  | 1.23789  |   1.66043 |       1.41062 |            -0.063435   |   -0.292252    |      0.236601   |                198 |
|            65 | mlp_train_label_permutation                      |     1.48887  | 1.29185  |   1.74598 |       1.70854 |            -0.00576902 |   -0.0878644   |      0.0974132  |                198 |
|            65 | traditional_analytic_timewalk                    |     1.49464  | 1.32186  |   1.6868  |       1.69913 |             0          |    0           |      0          |                198 |
|            65 | gated_label_fusion_train_label_permutation       |     1.50983  | 1.29196  |   1.73905 |       1.64031 |             0.0151946  |   -0.124152    |      0.145814   |                198 |
|            65 | label_offset_train_label_permutation             |     1.52703  | 1.3474   |   1.7289  |       1.74724 |             0.0323875  |    0.000291173 |      0.088492   |                198 |
|            65 | cnn_real_stave                                   |     1.54419  | 1.29776  |   1.71263 |       1.51074 |             0.0495464  |   -0.258687    |      0.297619   |                198 |
|            65 | mlp_no_stave                                     |     1.64394  | 1.48916  |   1.89262 |       1.82817 |             0.149305   |    0.00626433  |      0.333813   |                198 |
|            65 | cnn_no_stave                                     |     1.67515  | 1.49856  |   1.83929 |       1.80842 |             0.180508   |    0.0276287   |      0.310949   |                198 |
|            65 | ridge_no_stave                                   |     1.69416  | 1.46704  |   1.81657 |       1.71931 |             0.199523   |   -0.0420829   |      0.362412   |                198 |
|            65 | ridge_train_label_permutation                    |     1.72296  | 1.49494  |   1.84022 |       1.73855 |             0.228322   |   -0.0107251   |      0.384917   |                198 |
|            65 | gated_label_fusion_no_stave                      |     1.75596  | 1.52045  |   1.9501  |       1.86233 |             0.261318   |    0.0611917   |      0.402124   |                198 |
|            65 | cnn_train_label_permutation                      |     1.82165  | 1.63738  |   2.06069 |       1.93534 |             0.327012   |    0.153851    |      0.564216   |                198 |
|            65 | gated_label_fusion_heldout_label_permutation     |     2.1126   | 1.82982  |   2.64168 |       2.22285 |             0.617964   |    0.368698    |      1.09076    |                198 |
|            65 | mlp_heldout_label_permutation                    |     2.12592  | 1.91956  |   2.47836 |       2.33715 |             0.631285   |    0.43187     |      0.938904   |                198 |
|            65 | label_offset_heldout_label_permutation           |     2.29134  | 1.99218  |   2.90419 |       2.61766 |             0.796696   |    0.512505    |      1.36695    |                198 |
|            65 | cnn_heldout_label_permutation                    |     2.37388  | 2.03272  |   2.74991 |       2.4248  |             0.879242   |    0.537319    |      1.23453    |                198 |
|            65 | ridge_heldout_label_permutation                  |     2.39823  | 2.03778  |   2.87307 |       2.42939 |             0.903594   |    0.560565    |      1.31917    |                198 |
|            65 | gradient_boosted_trees_heldout_label_permutation |     2.43406  | 2.07223  |   2.75412 |       2.42077 |             0.939423   |    0.58906     |      1.26599    |                198 |

## Calibration, leakage, and systematics

|   heldout_run | method                                       |   n_pulses |   pred_sigma_median_ns |   abs_error_median_ns |   pull_width_sigma68 |   pull_rms |
|--------------:|:---------------------------------------------|-----------:|-----------------------:|----------------------:|---------------------:|-----------:|
|            58 | mlp_no_stave                                 |        219 |                2.45143 |              1.40125  |             0.663372 |   0.896227 |
|            58 | cnn_no_stave                                 |        219 |                2.45228 |              1.37016  |             0.638517 |   0.8529   |
|            58 | gated_label_fusion_no_stave                  |        219 |                2.58442 |              1.29904  |             0.604622 |   0.802086 |
|            58 | mlp_real_stave                               |        219 |                1.89179 |              0.842339 |             0.42261  |   0.985835 |
|            58 | cnn_real_stave                               |        219 |                2.06204 |              0.641188 |             0.431856 |   0.863602 |
|            58 | gated_label_fusion_real_stave                |        219 |                2.21846 |              0.588555 |             0.415156 |   0.83537  |
|            58 | mlp_train_label_permutation                  |        219 |                2.40972 |              1.38021  |             0.692546 |   0.89821  |
|            58 | cnn_train_label_permutation                  |        219 |                2.47099 |              1.37587  |             0.674201 |   0.845139 |
|            58 | gated_label_fusion_train_label_permutation   |        219 |                2.52518 |              1.42194  |             0.644602 |   0.855803 |
|            58 | mlp_heldout_label_permutation                |        219 |                1.94666 |              1.58291  |             0.923075 |   1.62925  |
|            58 | cnn_heldout_label_permutation                |        219 |                2.20383 |              1.28963  |             0.955194 |   1.28803  |
|            58 | gated_label_fusion_heldout_label_permutation |        219 |                2.26991 |              1.13635  |             1.05704  |   1.28815  |
|            59 | mlp_no_stave                                 |       2289 |                2.12516 |              1.24151  |             0.747253 |   0.898279 |
|            59 | cnn_no_stave                                 |       2289 |                2.04794 |              1.26128  |             0.776477 |   0.959608 |
|            59 | gated_label_fusion_no_stave                  |       2289 |                2.17116 |              1.29319  |             0.723816 |   0.896411 |
|            59 | mlp_real_stave                               |       2289 |                1.55616 |              0.641565 |             0.614583 |   0.972825 |
|            59 | cnn_real_stave                               |       2289 |                1.60542 |              0.600051 |             0.585343 |   1.02785  |
|            59 | gated_label_fusion_real_stave                |       2289 |                2.11191 |              1.00796  |             0.691827 |   0.928918 |
|            59 | mlp_train_label_permutation                  |       2289 |                2.14226 |              1.16799  |             0.780187 |   0.90812  |
|            59 | cnn_train_label_permutation                  |       2289 |                2.17203 |              1.18103  |             0.710043 |   0.891881 |
|            59 | gated_label_fusion_train_label_permutation   |       2289 |                2.26484 |              1.19952  |             0.713397 |   0.893303 |
|            59 | mlp_heldout_label_permutation                |       2289 |                1.45074 |              1.39884  |             1.40853  |   1.4604   |
|            59 | cnn_heldout_label_permutation                |       2289 |                1.54419 |              1.44795  |             1.38485  |   1.49858  |
|            59 | gated_label_fusion_heldout_label_permutation |       2289 |                1.7565  |              1.51516  |             1.25722  |   1.33849  |
|            60 | mlp_no_stave                                 |       2424 |                2.06318 |              1.08538  |             0.746453 |   0.862617 |
|            60 | cnn_no_stave                                 |       2424 |                2.09507 |              1.12562  |             0.722078 |   0.872157 |
|            60 | gated_label_fusion_no_stave                  |       2424 |                2.19124 |              1.1407   |             0.706929 |   0.852522 |
|            60 | mlp_real_stave                               |       2424 |                1.49908 |              0.65234  |             0.59217  |   0.867297 |
|            60 | cnn_real_stave                               |       2424 |                1.68556 |              0.620535 |             0.543907 |   0.846505 |
|            60 | gated_label_fusion_real_stave                |       2424 |                1.90864 |              0.66807  |             0.51754  |   0.8091   |
|            60 | mlp_train_label_permutation                  |       2424 |                1.902   |              1.12832  |             0.782688 |   0.917693 |
|            60 | cnn_train_label_permutation                  |       2424 |                2.13193 |              1.10122  |             0.755139 |   0.883757 |
|            60 | gated_label_fusion_train_label_permutation   |       2424 |                2.17661 |              1.19472  |             0.713803 |   0.845816 |
|            60 | mlp_heldout_label_permutation                |       2424 |                1.58051 |              1.41723  |             1.32212  |   1.35708  |
|            60 | cnn_heldout_label_permutation                |       2424 |                1.699   |              1.36631  |             1.22011  |   1.29399  |
|            60 | gated_label_fusion_heldout_label_permutation |       2424 |                1.90165 |              1.56428  |             1.14354  |   1.23743  |
|            61 | mlp_no_stave                                 |       2799 |                2.10133 |              1.70288  |             1.05003  |   1.18608  |
|            61 | cnn_no_stave                                 |       2799 |                2.09767 |              1.7052   |             1.07826  |   1.22775  |
|            61 | gated_label_fusion_no_stave                  |       2799 |                2.10952 |              1.66337  |             1.05521  |   1.20546  |
|            61 | mlp_real_stave                               |       2799 |                1.44931 |              0.699496 |             0.724551 |   1.19893  |
|            61 | cnn_real_stave                               |       2799 |                1.5922  |              0.703817 |             0.703359 |   1.08345  |
|            61 | gated_label_fusion_real_stave                |       2799 |                1.87949 |              0.995013 |             0.716869 |   0.999601 |
|            61 | mlp_train_label_permutation                  |       2799 |                2.00628 |              1.63503  |             1.09094  |   1.22078  |
|            61 | cnn_train_label_permutation                  |       2799 |                2.23092 |              1.66287  |             0.995634 |   1.14911  |
|            61 | gated_label_fusion_train_label_permutation   |       2799 |                2.19957 |              1.82795  |             1.10367  |   1.2294   |
|            61 | mlp_heldout_label_permutation                |       2799 |                1.5222  |              1.9765   |             2.0763   |   2.04315  |
|            61 | cnn_heldout_label_permutation                |       2799 |                1.61904 |              2.00119  |             1.88209  |   1.87617  |
|            61 | gated_label_fusion_heldout_label_permutation |       2799 |                1.88394 |              2.0036   |             1.50237  |   1.57486  |
|            62 | mlp_no_stave                                 |       2421 |                1.96389 |              1.18704  |             0.842071 |   1.07931  |
|            62 | cnn_no_stave                                 |       2421 |                2.14701 |              1.19198  |             0.771635 |   0.930609 |
|            62 | gated_label_fusion_no_stave                  |       2421 |                2.19124 |              1.10748  |             0.769078 |   0.961183 |
|            62 | mlp_real_stave                               |       2421 |                1.48047 |              0.585937 |             0.607417 |   1.06388  |
|            62 | cnn_real_stave                               |       2421 |                1.62373 |              0.599624 |             0.571586 |   1.11171  |
|            62 | gated_label_fusion_real_stave                |       2421 |                1.91524 |              0.753034 |             0.567309 |   0.954859 |
|            62 | mlp_train_label_permutation                  |       2421 |                2.16269 |              1.16649  |             0.778123 |   0.952279 |
|            62 | cnn_train_label_permutation                  |       2421 |                2.20749 |              1.25083  |             0.779666 |   0.947998 |
|            62 | gated_label_fusion_train_label_permutation   |       2421 |                2.28217 |              1.24676  |             0.785072 |   0.962512 |
|            62 | mlp_heldout_label_permutation                |       2421 |                1.39888 |              1.55182  |             1.56018  |   1.68051  |
|            62 | cnn_heldout_label_permutation                |       2421 |                1.58736 |              1.5307   |             1.42999  |   1.63468  |
|            62 | gated_label_fusion_heldout_label_permutation |       2421 |                1.7893  |              1.56022  |             1.19592  |   1.33841  |
|            63 | mlp_no_stave                                 |       1110 |                2.08549 |              1.10898  |             0.752727 |   0.959333 |
|            63 | cnn_no_stave                                 |       1110 |                2.10065 |              1.18468  |             0.6972   |   0.989887 |
|            63 | gated_label_fusion_no_stave                  |       1110 |                2.27605 |              1.1888   |             0.673732 |   0.921702 |
|            63 | mlp_real_stave                               |       1110 |                1.40705 |              0.635956 |             0.639718 |   1.07063  |
|            63 | cnn_real_stave                               |       1110 |                1.61423 |              0.63504  |             0.559285 |   1.05114  |
|            63 | gated_label_fusion_real_stave                |       1110 |                1.82346 |              0.667758 |             0.5308   |   0.956434 |
|            63 | mlp_train_label_permutation                  |       1110 |                2.0127  |              1.1784   |             0.742925 |   0.94174  |
|            63 | cnn_train_label_permutation                  |       1110 |                2.03374 |              1.10893  |             0.741739 |   1.05469  |
|            63 | gated_label_fusion_train_label_permutation   |       1110 |                2.1327  |              1.06729  |             0.687782 |   0.966911 |
|            63 | mlp_heldout_label_permutation                |       1110 |                1.49563 |              1.29499  |             1.35201  |   1.48882  |
|            63 | cnn_heldout_label_permutation                |       1110 |                1.75538 |              1.33063  |             1.13226  |   1.30455  |
|            63 | gated_label_fusion_heldout_label_permutation |       1110 |                2.14117 |              1.21097  |             0.775066 |   1.00071  |
|            65 | mlp_no_stave                                 |        198 |                2.07769 |              1.20163  |             0.73922  |   0.824425 |
|            65 | cnn_no_stave                                 |        198 |                2.34198 |              1.33951  |             0.681399 |   0.751336 |
|            65 | gated_label_fusion_no_stave                  |        198 |                2.35127 |              1.34651  |             0.656591 |   0.72888  |
|            65 | mlp_real_stave                               |        198 |                1.57194 |              0.827179 |             0.660428 |   0.750616 |
|            65 | cnn_real_stave                               |        198 |                1.61899 |              0.643408 |             0.573525 |   0.735    |
|            65 | gated_label_fusion_real_stave                |        198 |                2.02893 |              0.666621 |             0.509149 |   0.58998  |
|            65 | mlp_train_label_permutation                  |        198 |                2.35237 |              1.03039  |             0.660339 |   0.716157 |
|            65 | cnn_train_label_permutation                  |        198 |                2.27692 |              1.36157  |             0.691345 |   0.756461 |
|            65 | gated_label_fusion_train_label_permutation   |        198 |                2.42363 |              1.21287  |             0.609773 |   0.676083 |
|            65 | mlp_heldout_label_permutation                |        198 |                1.54494 |              1.46693  |             1.05956  |   1.3384   |
|            65 | cnn_heldout_label_permutation                |        198 |                1.85536 |              1.32558  |             1.03929  |   1.16134  |
|            65 | gated_label_fusion_heldout_label_permutation |        198 |                2.15569 |              1.06186  |             0.811426 |   0.896796 |

|   heldout_run | check                          |   value | detail                                                                                                                                                                                                                                                                  |
|--------------:|:-------------------------------|--------:|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|            58 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            58 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            58 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |
|            59 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            59 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            59 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |
|            60 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            60 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            60 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |
|            61 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            61 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            61 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |
|            62 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            62 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            62 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |
|            63 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            63 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            63 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |
|            65 | feature_audit                  |      24 | models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used |
|            65 | traditional_analytic_choice    |     100 | amp_only                                                                                                                                                                                                                                                                |
|            65 | train_heldout_event_id_overlap |       0 | must be zero                                                                                                                                                                                                                                                            |

Systematic limitations: the run-block CI has only seven blocks, so it is a stability diagnostic rather than an asymptotic interval; the permutation controls preserve the marginal stave frequencies but not every possible run/stave correlation; and the residual target is self-supervised from downstream timing closure rather than an external truth time. A method that improves under `heldout_label_permutation` is treated cautiously because it can be exploiting waveform or amplitude features rather than detector labels. Conversely, large gains by `label_offset_real_stave` would indicate static per-stave offsets rather than waveform-shape learning.

## Verdict

`result.json` verdict: `real_stave_labels_help_but_waveform_controls_required`. Winner: `gradient_boosted_trees_real_stave`. Best real-stave ML/NN method: `gradient_boosted_trees_real_stave`. Label-only real-stave offset mean sigma68: `1.2521` ns.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03g_1781034623_1447_4a243444_detector_label_permutation.py --config configs/p03g_1781034623_1447_4a243444_detector_label_permutation.yaml
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `downstream_counts_by_run.csv`, `heldout_run_summary.csv`, `pooled_summary.csv`, `run_label_policy_gap_summary.csv`, `heldout_pair_residuals.csv`, `traditional_scan_metrics.csv`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, `ml_cv_scan.csv`, `ml_calibration.csv`, `model_feature_audit.csv`, `model_choices_by_run.csv`, `label_offset_table.csv`, `leakage_checks.csv`, and PNG figures.

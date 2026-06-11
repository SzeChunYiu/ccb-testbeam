# S05n: Pretrigger-atom covariance projection stress

- **Ticket:** `1781062443.571.1e7346af`
- **Worker:** `testbeam-laptop-2`
- **Raw input:** `/home/billy/ccb-data/extracted/root/root`
- **No Monte Carlo:** raw HRD ROOT only

## Question

After conditioning on P11a-style pretrigger atoms, B2 saturation, pair topology, amplitude, and anomaly flags, is the B-stack correlated timing floor still a real common covariance term or a projection artifact?

## Abstract

This study rebuilds the S05 B-stack pair table and the P11a-style pretrigger atom table directly from raw `h101/HRDv`.  Each selected B pulse receives a pretrigger atom (`quiet`, `noisy_rms`, `sloped`, `early_asym`, `adaptive_lowering`, or `spike`) from samples 0-3. Pair residual models are then trained with whole runs held out. The benchmark includes a strong traditional `pair_median` baseline, a pretrigger-atom-stratified Ridge comparator, and the required learned panel: `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, plus the new `pretrigger_support_gated_cnn_new`.

The winner named in `result.json` is **ridge**, selected by the smallest supported pretrigger-conditioned B2-minus-downstream covariance delta among non-control methods, with sigma68 used as the tie-breaker. Its held-out sigma68 is **7.285 ns** (95% CI `[6.741, 8.759]`) and its projected two-ended sigma68 is **5.151 ns**. The corresponding conditioned common-covariance fraction is **-0.477**.

## Reproduction First

| quantity                             |     expected |   reproduced |       delta |   tolerance | pass   |
|:-------------------------------------|-------------:|-------------:|------------:|------------:|:-------|
| total_selected_b_pulses              | 640737       | 640737       | 0           |       0     | True   |
| sample_i_analysis_b_selected_pulses  | 252266       | 252266       | 0           |       0     | True   |
| sample_ii_analysis_b_selected_pulses | 125096       | 125096       | 0           |       0     | True   |
| sample_iv_a1_a3_pairs                |    127       |    127       | 0           |       0     | True   |
| sample_iv_a1_a3_robust_width_ns      |      1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |

## Methods

Let `x_ij` denote the raw waveform and pretrigger atom features for B staves `i,j` in an event. The target residual is

`r_ij = [t_j(CFD20) - t_i(CFD20)] - (z_j-z_i) v_TOF`,

with `v_TOF = 0.078 ns/cm` and `z` spacing `2.0 cm`. For method `m`, the held-out residual is `e_ij(m)=r_ij-f_m(x_ij)`.

The robust residual width is

`W_68(m)=0.5 [Q_84(e_ij - median(e)) - Q_16(e_ij - median(e))]`,

and the two-ended projection reported here is `W_68/sqrt(2)`. Pull width is the sigma68 of `e_ij/W_68(train)` for each held-out run. Pair covariance is computed by pivoting residuals to `(run,event) x pair` and averaging off-diagonal covariances:

`C_m = mean_run mean_p<q |Cov(e_p(m), e_q(m))|`.

The projection-stress estimand is evaluated inside support cells:

`cell = run_family x pretrigger_bin x saturation_bin x amplitude_bin x anomaly_flag`.

For each populated cell, the conditional covariance delta is

`Delta C_cell(m) = C_B2-containing,cell(m) - C_downstream-only,cell(m)`.

If the weighted common-covariance fraction remains positive after this conditioning, the floor is not explained away by the tested pretrigger/saturation/topology projection axes.

## Held-Out Benchmark

| method                            | method_class   |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   projected_twoended_sigma68_ns |   full_rms_ns |   full_rms_ci_low_ns |   full_rms_ci_high_ns |   pull_width |   tail_fraction_abs_gt_5ns |   mean_abs_pair_cov_ns2 |   correlated_fraction |
|:----------------------------------|:---------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------------------------:|--------------:|---------------------:|----------------------:|-------------:|---------------------------:|------------------------:|----------------------:|
| pair_median                       | traditional    |        104464 |       21 |      2.29158 |             1.89945 |             16.1474  |                         1.62039 |       22.579  |             15.7522  |               34.1508 |     0.915451 |                   0.165378 |                228.535  |              0.366419 |
| traditional_atom_stratified_ridge | traditional    |        104464 |       21 |      8.23399 |             7.70699 |              9.17382 |                         5.82231 |       11.0589 |              9.86565 |               13.6668 |     0.988478 |                   0.504987 |                 56.8027 |              0.392572 |
| ridge                             | ml             |        104464 |       21 |      7.28526 |             6.74067 |              8.75911 |                         5.15146 |       11.5642 |             10.2006  |               14.7979 |     0.982924 |                   0.463107 |                 92.2391 |              0.497018 |
| gradient_boosted_trees            | ml             |        104464 |       21 |      4.15614 |             3.7412  |             10.287   |                         2.93883 |       12.5486 |             10.8997  |               17.3402 |     0.972324 |                   0.236694 |                 63.4646 |              0.325697 |
| mlp                               | ml             |        104464 |       21 |      4.93789 |             4.39249 |             13.6016  |                         3.49162 |       19.3444 |             15.3082  |               26.6138 |     0.967658 |                   0.32124  |                197.603  |              0.404406 |
| cnn_1d                            | ml             |        104464 |       21 |      5.63656 |             4.45091 |             17.2657  |                         3.98565 |       22.0529 |             18.1109  |               32.3649 |     0.971356 |                   0.369812 |                230.229  |              0.374377 |
| pretrigger_support_gated_cnn_new  | ml             |        104464 |       21 |      5.35589 |             4.41339 |             13.7164  |                         3.78719 |       22.1604 |             17.71    |               29.9332 |     0.970501 |                   0.341907 |                228.115  |              0.373401 |
| pool_label_control                | control        |        104464 |       21 |      6.63243 |             4.85991 |             15.7778  |                         4.68984 |       20.8809 |             15.9448  |               29.779  |     0.802493 |                   0.440774 |                228.535  |              0.366419 |
| ml_shuffled_target_control        | control        |        104464 |       21 |      5.7375  |             4.77598 |             17.0727  |                         4.05702 |       22.8148 |             17.2591  |               30.6581 |     0.968106 |                   0.372435 |                237.473  |              0.373308 |

The pair-median baseline has sigma68 `2.292` ns and the pretrigger-stratified traditional Ridge has sigma68 `8.234` ns. The winner has sigma68 `7.285` ns and mean absolute pair covariance `92.239` ns^2.

## Conditional Covariance

| method                            |   n_conditioning_cells |   weighted_conditional_cov_delta_ns2 |   delta_ci_low_ns2 |   delta_ci_high_ns2 |   weighted_common_covariance_fraction |   fraction_ci_low |   fraction_ci_high |
|:----------------------------------|-----------------------:|-------------------------------------:|-------------------:|--------------------:|--------------------------------------:|------------------:|-------------------:|
| cnn_1d                            |                     18 |                             107.86   |           37.7896  |            248.97   |                              0.531685 |         0.224681  |           0.871605 |
| gradient_boosted_trees            |                     18 |                              54.8811 |           24.164   |            152.425  |                              0.358848 |        -0.319776  |           0.829391 |
| ml_shuffled_target_control        |                     18 |                             106.464  |           29.0932  |            277.083  |                              0.605246 |         0.380044  |           0.810158 |
| mlp                               |                     18 |                              93.2534 |           29.3011  |            221.289  |                              0.603483 |         0.332363  |           0.896859 |
| pair_median                       |                     18 |                             106.096  |           35.3775  |            226.147  |                              0.446441 |        -0.265621  |           0.906848 |
| pool_label_control                |                     18 |                             106.096  |           40.5741  |            309.373  |                              0.446441 |        -0.0771196 |           0.918599 |
| pretrigger_support_gated_cnn_new  |                     18 |                             101.801  |           53.6609  |            292.914  |                              0.386912 |        -0.267275  |           0.885155 |
| ridge                             |                     18 |                              21.6207 |           -1.97713 |             67.8005 |                             -0.477228 |        -0.866235  |           0.129032 |
| traditional_atom_stratified_ridge |                     18 |                              28.2355 |           -1.8932  |             97.8523 |                             -0.422512 |        -0.862913  |           0.14596  |

Largest supported cells:

| method                            | conditioning_cell                                                    |   n_b2_rows |   n_downstream_rows |   n_runs |   b2_mean_abs_pair_cov_ns2 |   downstream_mean_abs_pair_cov_ns2 |   conditional_cov_delta_ns2 |   common_covariance_fraction |
|:----------------------------------|:---------------------------------------------------------------------|------------:|--------------------:|---------:|---------------------------:|-----------------------------------:|----------------------------:|-----------------------------:|
| ridge                             | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    7.93597 |                          15.9991   |                   -8.06317  |                    -1.01603  |
| pretrigger_support_gated_cnn_new  | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    5.3702  |                           1.22022  |                    4.14998  |                     0.77278  |
| traditional_atom_stratified_ridge | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    8.09792 |                          12.3314   |                   -4.23344  |                    -0.52278  |
| mlp                               | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    5.41009 |                           1.25586  |                    4.15423  |                     0.767868 |
| cnn_1d                            | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    5.97648 |                           1.32938  |                    4.6471   |                     0.777565 |
| ml_shuffled_target_control        | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    6.70687 |                           2.73438  |                    3.97248  |                     0.592301 |
| pool_label_control                | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    5.29002 |                           1.04033  |                    4.24969  |                     0.803342 |
| pair_median                       | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    5.29002 |                           1.04033  |                    4.24969  |                     0.803342 |
| gradient_boosted_trees            | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=mid|anom=nominal  |       11784 |                6970 |        7 |                    4.22198 |                           0.972755 |                    3.24922  |                     0.769597 |
| mlp                               | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    3.41841 |                           3.88262  |                   -0.464217 |                    -0.135799 |
| gradient_boosted_trees            | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    2.32622 |                           5.63314  |                   -3.30692  |                    -1.42158  |
| cnn_1d                            | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    4.00693 |                           5.95296  |                   -1.94603  |                    -0.485667 |
| traditional_atom_stratified_ridge | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                   11.503   |                          28.594    |                  -17.091    |                    -1.48578  |
| pair_median                       | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    2.76368 |                           5.64727  |                   -2.88359  |                    -1.04339  |
| ridge                             | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                   10.7617  |                          25.5388   |                  -14.7771   |                    -1.37312  |
| pretrigger_support_gated_cnn_new  | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    2.7697  |                           6.27624  |                   -3.50655  |                    -1.26604  |
| ml_shuffled_target_control        | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    5.52302 |                           4.37618  |                    1.14684  |                     0.207646 |
| pool_label_control                | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=high|anom=nominal |       11491 |                3070 |        7 |                    2.76368 |                           5.64727  |                   -2.88359  |                    -1.04339  |
| pool_label_control                | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=low|anom=nominal  |        7402 |                5841 |        7 |                   38.8627  |                           1.4394   |                   37.4233   |                     0.962962 |
| cnn_1d                            | sample_ii_analysis|pre=quiet_or_shape|sat=none|amp=low|anom=nominal  |        7402 |                5841 |        7 |                   45.4164  |                           2.51495  |                   42.9014   |                     0.944625 |

## ML-Minus-Traditional Calibration

| method                           | baseline                          |   delta_sigma68_ns |   delta_projected_twoended_sigma68_ns |   delta_pull_width |   delta_conditioned_cov_ns2 |
|:---------------------------------|:----------------------------------|-------------------:|--------------------------------------:|-------------------:|----------------------------:|
| ridge                            | pair_median                       |           4.99368  |                              3.53106  |         0.0674735  |                   -84.4756  |
| ridge                            | traditional_atom_stratified_ridge |          -0.948729 |                             -0.670853 |        -0.00555426 |                    -6.61476 |
| gradient_boosted_trees           | pair_median                       |           1.86455  |                              1.31844  |         0.0568733  |                   -51.2152  |
| gradient_boosted_trees           | traditional_atom_stratified_ridge |          -4.07785  |                             -2.88348  |        -0.0161544  |                    26.6456  |
| mlp                              | pair_median                       |           2.64631  |                              1.87122  |         0.0522078  |                   -12.8429  |
| mlp                              | traditional_atom_stratified_ridge |          -3.29609  |                             -2.33069  |        -0.0208199  |                    65.0179  |
| cnn_1d                           | pair_median                       |           3.34498  |                              2.36526  |         0.0559058  |                     1.76389 |
| cnn_1d                           | traditional_atom_stratified_ridge |          -2.59742  |                             -1.83666  |        -0.0171219  |                    79.6247  |
| pretrigger_support_gated_cnn_new | pair_median                       |           3.06431  |                              2.16679  |         0.0550504  |                    -4.29514 |
| pretrigger_support_gated_cnn_new | traditional_atom_stratified_ridge |          -2.8781   |                             -2.03512  |        -0.0179774  |                    73.5657  |

## Leakage Checks

| check                                   | value               | pass   |
|:----------------------------------------|:--------------------|:-------|
| forbidden_feature_overlap               |                     | True   |
| train_heldout_run_overlap               | 0                   | True   |
| pretrigger_atoms_joined_fraction        | 1.0                 | True   |
| shuffled_target_worse_than_winner_width | 0.38160771821802886 | True   |

## Systematics And Caveats

The pretrigger atoms are P11a-style deterministic nuisance strata derived only from samples 0-3. Their thresholds are frozen globally from raw pretrigger summaries and do not use timing targets, but they are not external pedestal truth. The anomaly flag is a support coordinate combining late-tail/pile-up proxies and pretrigger spike/noisy atoms; it is not a particle label. Sparse support cells are excluded, so the conclusion applies only to cells with at least `120` rows per topology and `3` runs.

The neural methods use a short CPU budget, matching the laptop-fleet convention for light studies. A weak CNN result should therefore be read as a reproducible benchmark result under this budget, not as a proof against all possible convolutional models.

## Conclusion

The S05n stress test weakens, but does not conclusively retire, the B2 covariance-floor interpretation. Ridge gives the smallest supported pretrigger-conditioned B2-minus-downstream covariance delta, and its bootstrap interval overlaps zero; however, several learned and neural alternatives still retain positive deltas in the same support ledger. The winner is therefore a projection-stress benchmark winner, not a production replacement for the conservative S05 support-frontier treatment.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `method_metrics.csv`, `conditional_covariance_ledger.csv`, `conditional_covariance_summary.csv`, `method_deltas.csv`, `heldout_pair_residuals.csv`, `selected_pulse_pretrigger_table.csv.gz`, `input_sha256.csv`, and diagnostic figures are in this report directory.

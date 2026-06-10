# S18g: constrained timewalk transfer ranking

- **Ticket:** `1781032542.1057.75a00912`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input:** raw A-stack ROOT `HRDv`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18g_1781032542_1057_75a00912_constrained_timewalk_transfer.py --config configs/s18g_1781032542_1057_75a00912.json`
- **Primary metric:** Sample IV A1-A3 robust residual width, with 95% bootstrap intervals resampling held-out Sample IV runs.

## Abstract

This study tests whether the S18e early/late/mixed Sample III transfer ranking was driven by unconstrained ordinary least squares extrapolation. The ordinary polynomial is replaced by a monotonic additive timewalk model and benchmarked against five learned residual correctors: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN. The winner by point estimate is **sample_iii_mixed / gated_residual_cnn_new**, with robust width **0.273 ns** and run-bootstrap CI **[0.215, 0.331] ns**.

## Reproduction Gate

The raw ROOT files were rescanned before modeling. For each event, `HRDv` was reshaped to `(8, 18)`, samples 0-3 supplied the per-channel pedestal, A1/A3 were baseline-subtracted, and a pair entered the timing table when both maxima exceeded 1000 ADC. The S18e Sample IV run64-OLS anchor was then reproduced from raw data:

| quantity                            |   expected |   reproduced |       delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs               |  127       |    127       | 0           |       0     | True   |
| sample_iv_run64_ols_robust_width_ns |    1.79363 |      1.79363 | 3.40883e-07 |       0.001 | True   |
| sample_iv_run64_ols_core_sigma_ns   |    1.99218 |      1.99218 | 5.23655e-07 |       0.001 | True   |

Counts from the raw scan:

| sample              |   events_total |   events_with_selected |   A1_A3_pairs |   selected_pulses |   A1 |    A3 |
|:--------------------|---------------:|-----------------------:|--------------:|------------------:|-----:|------:|
| sample_iii_calib    |         409803 |                  11067 |          3816 |             14883 | 4111 | 10772 |
| sample_iii_analysis |         388848 |                   7168 |          2514 |              9682 | 2799 |  6883 |
| sample_iv_calib     |          35985 |                    161 |            16 |               177 |   20 |   157 |
| sample_iv_analysis  |         262189 |                    767 |           127 |               894 |  167 |   727 |

## Data Split

Training pools are:

| pool | runs | description |
|---|---|---|
| sample_iii_early | 31,32,33,34,35,36,37,39,40,41,42 | Early Sample III calibration-period A-stack runs only. |
| sample_iii_late | 44,45,46,47,48,49,50,51,52,53,54,55,56,57 | Late Sample III analysis-period A-stack runs only. |
| sample_iii_mixed | 31,32,33,34,35,36,37,39,40,41,42,44,45,46,47,48,49,50,51,52,53,54,55,56,57 | All available Sample III A-stack runs, combining early and late run families. |

The held-out evaluation set is Sample IV analysis runs `58,59,60,61,62,63,65`. No model is trained on these held-out runs. Confidence intervals are run bootstraps: if `R` is the set of held-out runs, each bootstrap replicate samples `|R|` runs with replacement and recomputes the pooled robust width on the concatenated residuals.

## Methods

Let `t_L` and `t_R` be CFD20 times for A1 and A3 after linear threshold interpolation, and let `y=t_R-t_L`. The baseline correction estimates a prediction `hat y(x_L,x_R)` from training-pool amplitudes and scores held-out residuals `e_i=y_i-hat y_i`.

### Constrained Traditional Timewalk

The constrained model uses monotone one-dimensional timewalk curves:

`hat y_i = beta_0 + d_R(log A_{R,i}) - d_L(log A_{L,i})`,

where both `d_L` and `d_R` are constrained non-increasing in log amplitude. The functions are fit by alternating pool-adjacent-violators isotonic regressions on the training pool, centering each function after every update. This preserves the physical sign that larger pulses should not have larger leading-edge delay and removes the unconstrained OLS extrapolation tested by this ticket.

Traditional constrained results:

| pool             | method                        |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:-----------------|:------------------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| sample_iii_mixed | constrained_monotone_timewalk |       127 |           1.51782 |            1.24923 |             1.71967 |         3.8723  |       1.47456 |                          0 |
| sample_iii_early | constrained_monotone_timewalk |       127 |           1.53085 |            1.29753 |             1.71977 |         2.02568 |       1.48753 |                          0 |
| sample_iii_late  | constrained_monotone_timewalk |       127 |           1.58276 |            1.27703 |             1.69477 |         2.08768 |       1.47512 |                          0 |

### ML/NN Panel

Ridge, gradient-boosted trees, and MLP receive engineered waveform/amplitude features: log amplitudes, peak samples, positive areas, tail fractions, normalized A1/A3 waveforms, and pairwise waveform differences. They receive no run id, event id, CFD time, or residual target feature. Ridge alpha is chosen by train-pool GroupKFold over runs.

The 1D-CNN receives the two normalized 18-sample waveforms as a two-channel sequence plus a small auxiliary amplitude/shape vector. The new architecture, `gated_residual_cnn_new`, is sensible for this ticket because it has residual temporal convolutions, global average/max pooling, and an auxiliary squeeze gate; it can represent local leading-edge distortions and pulse-wide tail changes with a small parameter count.

ML/NN results:

| pool             | method                 |   n_pairs |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   core_sigma_ns |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:-----------------|:-----------------------|----------:|------------------:|-------------------:|--------------------:|----------------:|--------------:|---------------------------:|
| sample_iii_mixed | gated_residual_cnn_new |       127 |          0.273432 |           0.215139 |            0.330993 |        0.266482 |      0.334638 |                 0          |
| sample_iii_early | gated_residual_cnn_new |       127 |          0.36766  |           0.303498 |            0.480454 |        0.328469 |      0.890447 |                 0          |
| sample_iii_late  | gated_residual_cnn_new |       127 |          0.463026 |           0.414186 |            0.527092 |        0.501508 |      0.610824 |                 0          |
| sample_iii_mixed | cnn_1d                 |       127 |          0.716329 |           0.575085 |            1.01952  |        0.645996 |      2.03723  |                 0.0472441  |
| sample_iii_early | cnn_1d                 |       127 |          0.811461 |           0.651666 |            1.41139  |        0.638887 |      2.15737  |                 0.0472441  |
| sample_iii_late  | gradient_boosted_trees |       127 |          0.855303 |           0.579832 |            1.33124  |        0.428088 |      1.87785  |                 0.0314961  |
| sample_iii_early | gradient_boosted_trees |       127 |          0.892595 |           0.706373 |            1.03694  |        1.01139  |      1.1824   |                 0.00787402 |
| sample_iii_mixed | gradient_boosted_trees |       127 |          0.90915  |           0.602987 |            1.23664  |        0.460435 |      1.39994  |                 0.00787402 |
| sample_iii_early | mlp                    |       127 |          1.17099  |           0.916967 |            1.60057  |        0.981768 |      1.68435  |                 0.015748   |
| sample_iii_early | ridge                  |       127 |          1.34343  |           1.00102  |            1.73537  |        1.56869  |      2.01449  |                 0.0472441  |
| sample_iii_late  | mlp                    |       127 |          1.53128  |           1.04494  |            2.19667  |        1.20998  |      2.19297  |                 0.0472441  |
| sample_iii_late  | ridge                  |       127 |          1.57965  |           1.38704  |            2.1251   |        1.92626  |      2.4617   |                 0.0708661  |
| sample_iii_late  | cnn_1d                 |       127 |          1.61234  |           1.34926  |            1.90114  |        2.46075  |      2.86584  |                 0.0629921  |
| sample_iii_mixed | ridge                  |       127 |          1.61473  |           1.26783  |            2.33566  |        1.62296  |      2.27543  |                 0.0314961  |
| sample_iii_mixed | mlp                    |       127 |          1.7184   |           1.04668  |            2.41645  |        0.95097  |      2.19492  |                 0.0551181  |

Ridge CV scan:

|   alpha |   cv_rmse_ns |   cv_rmse_std_ns | method   | selected   | pool             |
|--------:|-------------:|-----------------:|:---------|:-----------|:-----------------|
| 1000    |      1.75272 |         1.20786  | ridge    | True       | sample_iii_early |
|  100    |      1.78316 |         1.09951  | ridge    | False      | sample_iii_early |
|   10    |      1.92744 |         1.11494  | ridge    | False      | sample_iii_early |
|    1    |      1.93921 |         1.15213  | ridge    | False      | sample_iii_early |
|    0.1  |      1.96051 |         1.10919  | ridge    | False      | sample_iii_early |
|    0.01 |      1.96589 |         1.09978  | ridge    | False      | sample_iii_early |
|    0.01 |      1.68094 |         0.503016 | ridge    | True       | sample_iii_late  |
|    0.1  |      1.68407 |         0.520224 | ridge    | False      | sample_iii_late  |
|    1    |      1.78081 |         0.676745 | ridge    | False      | sample_iii_late  |
|   10    |      2.20417 |         1.06738  | ridge    | False      | sample_iii_late  |
|  100    |      2.42058 |         1.42624  | ridge    | False      | sample_iii_late  |
| 1000    |      2.49796 |         1.8805   | ridge    | False      | sample_iii_late  |
|    0.1  |      1.49611 |         0.438741 | ridge    | True       | sample_iii_mixed |
|    0.01 |      1.49736 |         0.430806 | ridge    | False      | sample_iii_mixed |
|    1    |      1.4999  |         0.499585 | ridge    | False      | sample_iii_mixed |
|   10    |      1.67518 |         0.701058 | ridge    | False      | sample_iii_mixed |
|  100    |      1.90594 |         0.926201 | ridge    | False      | sample_iii_mixed |
| 1000    |      2.00004 |         1.13321  | ridge    | False      | sample_iii_mixed |

## Head-to-Head Deltas

Each row is a paired held-out-run bootstrap delta relative to the constrained traditional model in the same calibration pool. Negative intervals favor the ML/NN method.

| pool             | comparison                                                 |   ci_low_ns |   ci_high_ns |   p_value |
|:-----------------|:-----------------------------------------------------------|------------:|-------------:|----------:|
| sample_iii_early | ridge_minus_constrained_monotone_timewalk                  |   -0.559819 |     0.263453 |     0.374 |
| sample_iii_early | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -0.892788 |    -0.410548 |     0     |
| sample_iii_early | mlp_minus_constrained_monotone_timewalk                    |   -0.631694 |     0.107334 |     0.15  |
| sample_iii_early | cnn_1d_minus_constrained_monotone_timewalk                 |   -0.894079 |    -0.13429  |     0.02  |
| sample_iii_early | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -1.33846  |    -0.907093 |     0     |
| sample_iii_late  | ridge_minus_constrained_monotone_timewalk                  |   -0.262937 |     0.671976 |     0.95  |
| sample_iii_late  | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -1.02996  |    -0.23048  |     0.03  |
| sample_iii_late  | mlp_minus_constrained_monotone_timewalk                    |   -0.415768 |     0.682314 |     0.914 |
| sample_iii_late  | cnn_1d_minus_constrained_monotone_timewalk                 |   -0.141767 |     0.415318 |     0.59  |
| sample_iii_late  | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -1.26637  |    -0.783416 |     0     |
| sample_iii_mixed | ridge_minus_constrained_monotone_timewalk                  |   -0.288616 |     0.805955 |     0.838 |
| sample_iii_mixed | gradient_boosted_trees_minus_constrained_monotone_timewalk |   -1.02359  |    -0.256099 |     0.002 |
| sample_iii_mixed | mlp_minus_constrained_monotone_timewalk                    |   -0.370883 |     0.965759 |     0.59  |
| sample_iii_mixed | cnn_1d_minus_constrained_monotone_timewalk                 |   -1.02546  |    -0.340888 |     0     |
| sample_iii_mixed | gated_residual_cnn_new_minus_constrained_monotone_timewalk |   -1.48071  |    -0.950833 |     0     |

## Per-Run Stability

| pool             | method                        |   run |   n_pairs |   robust_width_ns |   full_rms_ns |
|:-----------------|:------------------------------|------:|----------:|------------------:|--------------:|
| sample_iii_early | constrained_monotone_timewalk |    58 |        25 |          1.1137   |      1.32605  |
| sample_iii_early | constrained_monotone_timewalk |    59 |        11 |          0.997175 |      1.13647  |
| sample_iii_early | constrained_monotone_timewalk |    60 |        11 |          0.997871 |      1.16227  |
| sample_iii_early | constrained_monotone_timewalk |    61 |        18 |          1.65545  |      1.81473  |
| sample_iii_early | constrained_monotone_timewalk |    62 |         7 |          0.877121 |      1.49814  |
| sample_iii_early | constrained_monotone_timewalk |    63 |        28 |          1.30202  |      1.42433  |
| sample_iii_early | constrained_monotone_timewalk |    65 |        27 |          1.66371  |      1.62126  |
| sample_iii_early | ridge                         |    58 |        25 |          0.860492 |      1.4138   |
| sample_iii_early | ridge                         |    59 |        11 |          2.43547  |      2.91309  |
| sample_iii_early | ridge                         |    60 |        11 |          0.733085 |      0.968161 |
| sample_iii_early | ridge                         |    61 |        18 |          1.70097  |      1.76924  |
| sample_iii_early | ridge                         |    62 |         7 |          2.60177  |      2.63122  |
| sample_iii_early | ridge                         |    63 |        28 |          0.982302 |      1.82675  |
| sample_iii_early | ridge                         |    65 |        27 |          1.30479  |      2.15318  |
| sample_iii_early | gradient_boosted_trees        |    58 |        25 |          0.589478 |      1.53344  |
| sample_iii_early | gradient_boosted_trees        |    59 |        11 |          0.809337 |      0.964577 |
| sample_iii_early | gradient_boosted_trees        |    60 |        11 |          0.654409 |      0.77652  |
| sample_iii_early | gradient_boosted_trees        |    61 |        18 |          1.25734  |      1.41822  |
| sample_iii_early | gradient_boosted_trees        |    62 |         7 |          0.805868 |      1.24161  |
| sample_iii_early | gradient_boosted_trees        |    63 |        28 |          0.607884 |      1.06321  |
| sample_iii_early | gradient_boosted_trees        |    65 |        27 |          0.508797 |      0.905355 |
| sample_iii_early | mlp                           |    58 |        25 |          0.818479 |      1.68262  |
| sample_iii_early | mlp                           |    59 |        11 |          1.63607  |      1.89744  |
| sample_iii_early | mlp                           |    60 |        11 |          0.940394 |      2.4624   |
| sample_iii_early | mlp                           |    61 |        18 |          1.59931  |      1.76477  |
| sample_iii_early | mlp                           |    62 |         7 |          1.48346  |      2.39388  |
| sample_iii_early | mlp                           |    63 |        28 |          0.834322 |      1.11736  |
| sample_iii_early | mlp                           |    65 |        27 |          0.782388 |      1.16554  |
| sample_iii_early | cnn_1d                        |    58 |        25 |          0.645718 |      1.39586  |
| sample_iii_early | cnn_1d                        |    59 |        11 |          0.565351 |      2.11498  |
| sample_iii_early | cnn_1d                        |    60 |        11 |          0.650256 |      0.593016 |
| sample_iii_early | cnn_1d                        |    61 |        18 |          1.57099  |      1.50952  |
| sample_iii_early | cnn_1d                        |    62 |         7 |          4.06475  |      5.15293  |
| sample_iii_early | cnn_1d                        |    63 |        28 |          0.661992 |      1.29463  |
| sample_iii_early | cnn_1d                        |    65 |        27 |          0.794553 |      2.84415  |
| sample_iii_early | gated_residual_cnn_new        |    58 |        25 |          0.284695 |      0.505897 |
| sample_iii_early | gated_residual_cnn_new        |    59 |        11 |          0.32026  |      0.774342 |
| sample_iii_early | gated_residual_cnn_new        |    60 |        11 |          0.207409 |      0.915746 |
| sample_iii_early | gated_residual_cnn_new        |    61 |        18 |          0.511639 |      0.879265 |
| sample_iii_early | gated_residual_cnn_new        |    62 |         7 |          0.555267 |      1.87438  |
| sample_iii_early | gated_residual_cnn_new        |    63 |        28 |          0.311182 |      0.556873 |
| sample_iii_early | gated_residual_cnn_new        |    65 |        27 |          0.310095 |      1.04769  |
| sample_iii_late  | constrained_monotone_timewalk |    58 |        25 |          1.01822  |      1.27204  |
| sample_iii_late  | constrained_monotone_timewalk |    59 |        11 |          1.07265  |      1.15475  |
| sample_iii_late  | constrained_monotone_timewalk |    60 |        11 |          0.981705 |      1.17361  |
| sample_iii_late  | constrained_monotone_timewalk |    61 |        18 |          1.65124  |      1.75287  |
| sample_iii_late  | constrained_monotone_timewalk |    62 |         7 |          1.01152  |      1.49252  |
| sample_iii_late  | constrained_monotone_timewalk |    63 |        28 |          1.37729  |      1.38915  |
| sample_iii_late  | constrained_monotone_timewalk |    65 |        27 |          1.64313  |      1.67249  |
| sample_iii_late  | ridge                         |    58 |        25 |          0.797566 |      1.9956   |
| sample_iii_late  | ridge                         |    59 |        11 |          2.285    |      2.67397  |
| sample_iii_late  | ridge                         |    60 |        11 |          1.3135   |      1.23702  |
| sample_iii_late  | ridge                         |    61 |        18 |          2.12078  |      2.77895  |
| sample_iii_late  | ridge                         |    62 |         7 |          3.48101  |      5.40308  |
| sample_iii_late  | ridge                         |    63 |        28 |          1.31402  |      1.61504  |
| sample_iii_late  | ridge                         |    65 |        27 |          1.35451  |      2.18464  |
| sample_iii_late  | gradient_boosted_trees        |    58 |        25 |          0.585448 |      1.19722  |
| sample_iii_late  | gradient_boosted_trees        |    59 |        11 |          1.52425  |      2.39646  |
| sample_iii_late  | gradient_boosted_trees        |    60 |        11 |          0.831889 |      0.770005 |
| sample_iii_late  | gradient_boosted_trees        |    61 |        18 |          1.44949  |      1.71052  |
| sample_iii_late  | gradient_boosted_trees        |    62 |         7 |          2.48821  |      3.54596  |
| sample_iii_late  | gradient_boosted_trees        |    63 |        28 |          0.392572 |      1.4391   |
| sample_iii_late  | gradient_boosted_trees        |    65 |        27 |          0.449453 |      2.31474  |
| sample_iii_late  | mlp                           |    58 |        25 |          0.538926 |      1.05992  |
| sample_iii_late  | mlp                           |    59 |        11 |          2.77763  |      3.28665  |
| sample_iii_late  | mlp                           |    60 |        11 |          1.14502  |      1.31316  |
| sample_iii_late  | mlp                           |    61 |        18 |          1.87492  |      2.06765  |
| sample_iii_late  | mlp                           |    62 |         7 |          2.04003  |      2.93371  |
| sample_iii_late  | mlp                           |    63 |        28 |          1.1512   |      2.00042  |
| sample_iii_late  | mlp                           |    65 |        27 |          1.76309  |      2.55515  |
| sample_iii_late  | cnn_1d                        |    58 |        25 |          1.06632  |      1.26037  |
| sample_iii_late  | cnn_1d                        |    59 |        11 |          2.77409  |      3.53945  |
| sample_iii_late  | cnn_1d                        |    60 |        11 |          1.05353  |      1.01633  |
| sample_iii_late  | cnn_1d                        |    61 |        18 |          1.72801  |      2.35032  |
| sample_iii_late  | cnn_1d                        |    62 |         7 |          2.60967  |      5.77286  |
| sample_iii_late  | cnn_1d                        |    63 |        28 |          1.52088  |      2.53719  |
| sample_iii_late  | cnn_1d                        |    65 |        27 |          1.81553  |      3.57415  |
| sample_iii_late  | gated_residual_cnn_new        |    58 |        25 |          0.468066 |      0.596477 |
| sample_iii_late  | gated_residual_cnn_new        |    59 |        11 |          0.437516 |      0.485548 |
| sample_iii_late  | gated_residual_cnn_new        |    60 |        11 |          0.3858   |      0.593824 |
| sample_iii_late  | gated_residual_cnn_new        |    61 |        18 |          0.447482 |      0.682184 |
| sample_iii_late  | gated_residual_cnn_new        |    62 |         7 |          0.431759 |      0.838917 |
| sample_iii_late  | gated_residual_cnn_new        |    63 |        28 |          0.449638 |      0.453098 |
| sample_iii_late  | gated_residual_cnn_new        |    65 |        27 |          0.322362 |      0.650711 |
| sample_iii_mixed | constrained_monotone_timewalk |    58 |        25 |          1.07602  |      1.28344  |
| sample_iii_mixed | constrained_monotone_timewalk |    59 |        11 |          1.0004   |      1.19702  |
| sample_iii_mixed | constrained_monotone_timewalk |    60 |        11 |          0.97022  |      1.16291  |
| sample_iii_mixed | constrained_monotone_timewalk |    61 |        18 |          1.65913  |      1.80175  |
| sample_iii_mixed | constrained_monotone_timewalk |    62 |         7 |          0.990411 |      1.56649  |
| sample_iii_mixed | constrained_monotone_timewalk |    63 |        28 |          1.33336  |      1.38912  |
| sample_iii_mixed | constrained_monotone_timewalk |    65 |        27 |          1.57379  |      1.62056  |
| sample_iii_mixed | ridge                         |    58 |        25 |          0.91766  |      2.28368  |
| sample_iii_mixed | ridge                         |    59 |        11 |          2.76364  |      2.64134  |
| sample_iii_mixed | ridge                         |    60 |        11 |          1.27011  |      1.43805  |
| sample_iii_mixed | ridge                         |    61 |        18 |          1.91146  |      2.2201   |
| sample_iii_mixed | ridge                         |    62 |         7 |          3.55178  |      4.45242  |
| sample_iii_mixed | ridge                         |    63 |        28 |          1.16092  |      1.61367  |
| sample_iii_mixed | ridge                         |    65 |        27 |          1.25043  |      2.03233  |
| sample_iii_mixed | gradient_boosted_trees        |    58 |        25 |          0.714728 |      1.02823  |
| sample_iii_mixed | gradient_boosted_trees        |    59 |        11 |          1.3749   |      1.56691  |
| sample_iii_mixed | gradient_boosted_trees        |    60 |        11 |          0.564462 |      0.691061 |
| sample_iii_mixed | gradient_boosted_trees        |    61 |        18 |          1.41661  |      1.78102  |
| sample_iii_mixed | gradient_boosted_trees        |    62 |         7 |          1.31014  |      3.49018  |
| sample_iii_mixed | gradient_boosted_trees        |    63 |        28 |          0.394522 |      1.15521  |
| sample_iii_mixed | gradient_boosted_trees        |    65 |        27 |          0.490316 |      0.844735 |
| sample_iii_mixed | mlp                           |    58 |        25 |          0.606921 |      1.28194  |
| sample_iii_mixed | mlp                           |    59 |        11 |          2.78652  |      3.17475  |
| sample_iii_mixed | mlp                           |    60 |        11 |          1.09318  |      1.48023  |
| sample_iii_mixed | mlp                           |    61 |        18 |          1.97727  |      2.21651  |
| sample_iii_mixed | mlp                           |    62 |         7 |          2.36754  |      2.88405  |
| sample_iii_mixed | mlp                           |    63 |        28 |          1.05786  |      1.89706  |
| sample_iii_mixed | mlp                           |    65 |        27 |          1.65971  |      2.45493  |
| sample_iii_mixed | cnn_1d                        |    58 |        25 |          0.589719 |      1.78912  |
| sample_iii_mixed | cnn_1d                        |    59 |        11 |          0.948632 |      1.55717  |
| sample_iii_mixed | cnn_1d                        |    60 |        11 |          0.5439   |      2.19282  |
| sample_iii_mixed | cnn_1d                        |    61 |        18 |          0.848364 |      1.91948  |
| sample_iii_mixed | cnn_1d                        |    62 |         7 |          2.08319  |      4.55326  |
| sample_iii_mixed | cnn_1d                        |    63 |        28 |          0.478202 |      0.722015 |
| sample_iii_mixed | cnn_1d                        |    65 |        27 |          0.612354 |      2.19019  |
| sample_iii_mixed | gated_residual_cnn_new        |    58 |        25 |          0.268817 |      0.29973  |
| sample_iii_mixed | gated_residual_cnn_new        |    59 |        11 |          0.296517 |      0.262473 |
| sample_iii_mixed | gated_residual_cnn_new        |    60 |        11 |          0.218809 |      0.384403 |
| sample_iii_mixed | gated_residual_cnn_new        |    61 |        18 |          0.251011 |      0.346784 |
| sample_iii_mixed | gated_residual_cnn_new        |    62 |         7 |          0.359185 |      0.369482 |
| sample_iii_mixed | gated_residual_cnn_new        |    63 |        28 |          0.203377 |      0.250697 |
| sample_iii_mixed | gated_residual_cnn_new        |    65 |        27 |          0.223652 |      0.406925 |

## Systematics and Leakage Checks

| check                       | value                | flag   |
|:----------------------------|:---------------------|:-------|
| forbidden_feature_overlap   |                      | False  |
| group_split_r2_mean         | 0.49213365376169166  | False  |
| row_split_advantage_rmse_ns | -0.21413825171873047 | False  |

Main systematic limitations:

- **Low Sample IV statistics:** only 127 held-out A1-A3 pairs are available, so per-run intervals are wide and ranking precision is limited.
- **Transfer support:** early, late, and mixed Sample III pools have many more pairs than Sample IV but different amplitude/run-family support; the constrained model reduces extrapolation freedom but cannot make the support identical.
- **Metric robustness:** robust width is the primary metric; Gaussian core sigma, full RMS, within-2 ns efficiency, and >5 ns tail fraction are co-reported because core-only fits can hide tails.
- **Model selection:** five ML/NN families plus the constrained traditional baseline are compared. The named winner is therefore a benchmark ranking, not a discovery p-value.
- **Leakage control:** splits are by run; features exclude run number, event id, raw residuals, and the two CFD times used to form the target residual.

## Conclusion

The constrained monotonic model changes the S18e interpretation from an OLS-specific pool ranking to a broader benchmark: **sample_iii_mixed / gated_residual_cnn_new** has the smallest Sample IV robust width. The strongest traditional constrained pool is **sample_iii_mixed** at **1.518 ns**. The strongest learned method is **sample_iii_mixed / gated_residual_cnn_new** at **0.273 ns**. Adoption should remain cautious because the run-bootstrap intervals are dominated by seven small held-out runs.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this report directory.

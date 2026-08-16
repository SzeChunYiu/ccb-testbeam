# S50c: Pedestal-State PID Energy Transfer with Interpretable Waveform Representations

## Abstract

Ticket `2451` asks whether pretrigger pedestal memory explains cross-run PID
and energy calibration shifts better than static charge corrections.  This
worker (`testbeam-laptop-3`) reproduced the raw ROOT selected-pulse number, then compared
a strong traditional AR(1)-pedestal charge-ratio/likelihood calibration against
ridge, gradient-boosted trees, MLP, 1D-CNN, a self-attention transformer, and a
new pedestal-memory fusion architecture.  The held-out winner written to
`result.json` is **`pedestal_memory_fusion_new`**.  Its calibrated energy sigma68 is
`0.07374` with run-block 95% CI
[`0.06826`,
`0.07647`], PID-proxy AUC is
`0.9909`, and the verdict is: **pedestal memory is mostly removable nuisance in this controlled benchmark, not standalone physics signal**.

## Raw ROOT Reproduction

Raw B-stack ROOT files are read from `/home/billy/ccb-data/data/extracted/root/root`.  The `h101/HRDv`
branch is reshaped to `(event, channel, sample)` with 18 samples per channel.
For B2/B4/B6/B8, the pedestal-subtracted selection is

`b_ec = median_{t in {0,1,2,3}} x_ect`,  
`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

The reproduction gate was evaluated before model training:

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Split, Truth Construction, and Counterfactuals

Training and testing are disjoint by run.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]`; held-out runs are
`[58, 60, 62, 64, 65]`.  Clean pulse templates are estimated only
from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              832 |                   2.638 |                      5 |           9.164 |
| B4      |              812 |                   2.986 |                      6 |          10.8   |
| B6      |              779 |                   3.758 |                      6 |           9.779 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

Controlled doublets are generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a run-local residual and `p` is a sampled pedestal
offset.  The observed waveform is clipped as `min(w(t), 11800)`.
Pedestal-state counterfactuals are evaluated by comparing held-out nominal and
shifted pretrigger states at fixed source-run splits and the same endpoint
definitions.

## Methods

| method                                  | family         | description                                                                                        |
|:----------------------------------------|:---------------|:---------------------------------------------------------------------------------------------------|
| ar1_charge_ratio_likelihood_traditional | traditional    | clipped template fit with AR(1)-style pedestal sideband correction and charge-ratio PID proxy      |
| ridge                                   | linear ML      | ridge classifier plus multi-output ridge regression                                                |
| gradient_boosted_trees                  | tree ML        | histogram gradient-boosted classifier/regressor ensemble                                           |
| mlp                                     | neural network | tabular multilayer perceptron classifier/regressor pair                                            |
| 1d_cnn                                  | neural network | compact one-dimensional CNN over 18 ADC samples                                                    |
| tiny_sequence_transformer               | attention NN   | one-layer self-attention sequence encoder                                                          |
| pedestal_memory_fusion_new              | new hybrid     | boosted residual fusion of waveform summaries, saturation sidebands, and AR(1) traditional outputs |

The traditional comparator is the existing bounded two-template likelihood fit,
augmented with saturation sideband correction.  We interpret its pretrigger
baseline as an AR(1)-style memory proxy: the median of samples 0--3 estimates
the latent baseline state, and clipped plateau/late-tail terms correct static
charge-ratio bias.  The new `pedestal_memory_fusion_new` is sensible because the
failure mode is not purely neural: analytic pulse constituents, pedestal memory,
saturation sidebands, and residual waveform morphology are all identifiable
low-dimensional signals.

## Endpoint Definitions

For accepted held-out doublets, calibrated energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

The robust resolution is

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

The PID target is the available raw-ROOT-derived proxy
`inner_high_charge = 1[stave in {B2,B4} and A_1+A_2 > 9000 ADC]`; no external
particle labels are present in these reduced ROOT files.  We report PID AUC,
balanced accuracy, and off-diagonal confusion rate.  Pedestal offset recovery is
the absolute nominal-versus-shifted median energy-bias span.  Shape-latent
stability is the median energy-bias span across late-tail morphology states.
Confidence intervals are percentile 95% intervals from
`360` held-out run-block bootstrap resamples.

The registered winner minimizes

`C = sigma_E + 0.16 r_conf + 0.08(1-AUC_PID) + 0.10 S_ped + 0.06 S_false + 0.04 S_shape + 0.004 sigma_t + 0.05 r_miss + 0.05 r_false`.

## Overall Results

| method                                  |   winner_score |   pid_auc |   pid_confusion_offdiag_rate |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   timing_sigma68_ns |   pedestal_offset_recovery_error |   pedestal_false_split_span |   shape_latent_stability_span |
|:----------------------------------------|---------------:|----------:|-----------------------------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|--------------------:|---------------------------------:|----------------------------:|------------------------------:|
| pedestal_memory_fusion_new              |         0.1357 |    0.9909 |                      0.01361 |               0.00445  |                   0.07374 |                          0.06826 |                           0.07647 |               7.592 |                        0.01131   |                    0.01937  |                      0.008686 |
| gradient_boosted_trees                  |         0.1398 |    0.9889 |                      0.01718 |               0.002428 |                   0.07366 |                          0.06573 |                           0.08428 |               8.439 |                        0.0002752 |                    0.01474  |                      0.01508  |
| ridge                                   |         0.1512 |    0.9896 |                      0.02013 |               0.008654 |                   0.08077 |                          0.07092 |                           0.09343 |               8.795 |                        0.014     |                    0.04857  |                      0.008588 |
| 1d_cnn                                  |         0.1676 |    0.9853 |                      0.01449 |              -0.01928  |                   0.08671 |                          0.07539 |                           0.09749 |              10.91  |                        0.03442   |                    0.01563  |                      0.000964 |
| ar1_charge_ratio_likelihood_traditional |         0.189  |    0.9892 |                      0.02532 |               0.06702  |                   0.1011  |                          0.08833 |                           0.1137  |               8.674 |                        0.002315  |                    0.1004   |                      0.02901  |
| mlp                                     |         0.1936 |    0.9902 |                      0.02007 |               0.003197 |                   0.1078  |                          0.09298 |                           0.1193  |              12.36  |                        0.02005   |                    0.02372  |                      0.0132   |
| tiny_sequence_transformer               |         0.2024 |    0.9837 |                      0.02767 |               0.00272  |                   0.1061  |                          0.09764 |                           0.119   |              14.55  |                        0.003362  |                    0.006176 |                      0.0423   |

The traditional comparator score is `0.189` with energy
sigma68 `0.1011` and pedestal offset recovery
error `0.002315`.  The winner changes the
energy sigma68 by `-0.02732`.

## Endpoint Table with CIs

| method                                  |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   pid_balanced_accuracy |   pid_confusion_offdiag_rate |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   saturated_energy_residual_sigma68 |   timing_pull_width |   pedestal_offset_recovery_error |   pedestal_false_split_span |   shape_latent_stability_span |
|:----------------------------------------|----------:|-----------------:|------------------:|------------------------:|-----------------------------:|--------------------------:|---------------------------------:|----------------------------------:|------------------------------------:|--------------------:|---------------------------------:|----------------------------:|------------------------------:|
| gradient_boosted_trees                  |    0.9889 |           0.9776 |            0.9959 |                  0.9717 |                      0.01718 |                   0.07366 |                          0.06573 |                           0.08428 |                             0.118   |              0.8439 |                        0.0002752 |                    0.01474  |                      0.01508  |
| pedestal_memory_fusion_new              |    0.9909 |           0.9825 |            0.9969 |                  0.9744 |                      0.01361 |                   0.07374 |                          0.06826 |                           0.07647 |                             0.09519 |              0.7592 |                        0.01131   |                    0.01937  |                      0.008686 |
| ridge                                   |    0.9896 |           0.9845 |            0.9961 |                  0.9708 |                      0.02013 |                   0.08077 |                          0.07092 |                           0.09343 |                             0.06348 |              0.8795 |                        0.014     |                    0.04857  |                      0.008588 |
| 1d_cnn                                  |    0.9853 |           0.9716 |            0.994  |                  0.9714 |                      0.01449 |                   0.08671 |                          0.07539 |                           0.09749 |                             0.04121 |              1.091  |                        0.03442   |                    0.01563  |                      0.000964 |
| ar1_charge_ratio_likelihood_traditional |    0.9892 |           0.9687 |            1      |                  0.9865 |                      0.02532 |                   0.1011  |                          0.08833 |                           0.1137  |                             0.04978 |              0.8674 |                        0.002315  |                    0.1004   |                      0.02901  |
| tiny_sequence_transformer               |    0.9837 |           0.9771 |            0.9915 |                  0.9643 |                      0.02767 |                   0.1061  |                          0.09764 |                           0.119   |                             0.07605 |              1.455  |                        0.003362  |                    0.006176 |                      0.0423   |
| mlp                                     |    0.9902 |           0.979  |            0.9965 |                  0.9692 |                      0.02007 |                   0.1078  |                          0.09298 |                           0.1193  |                             0.1565  |              1.236  |                        0.02005   |                    0.02372  |                      0.0132   |

## Run-Held-Out Stability

| method                                  |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:----------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                  |            58 |                -0.03594  |                     0.09437 |       -0.1751  |            10.26  |             0.3023 |             0.2442 |
| 1d_cnn                                  |            60 |                 0.008326 |                     0.09533 |        1.376   |            12.05  |             0.3605 |             0.2442 |
| 1d_cnn                                  |            62 |                -0.008519 |                     0.0839  |        0.3265  |            10.99  |             0.407  |             0.3256 |
| 1d_cnn                                  |            64 |                -0.04816  |                     0.07747 |        0.8632  |             9.9   |             0.407  |             0.1279 |
| 1d_cnn                                  |            65 |                -0.02509  |                     0.06752 |        0.09213 |            11.36  |             0.314  |             0.1977 |
| ar1_charge_ratio_likelihood_traditional |            58 |                 0.04599  |                     0.07256 |        1.123   |            10.08  |             0.6744 |             0.2093 |
| ar1_charge_ratio_likelihood_traditional |            60 |                 0.1453   |                     0.1014  |        0.6891  |             8.384 |             0.6628 |             0.1279 |
| ar1_charge_ratio_likelihood_traditional |            62 |                 0.07348  |                     0.0981  |        1.734   |             6.805 |             0.6628 |             0.186  |
| ar1_charge_ratio_likelihood_traditional |            64 |                 0.04212  |                     0.08811 |        0.5637  |             7.757 |             0.5814 |             0.1395 |
| ar1_charge_ratio_likelihood_traditional |            65 |                 0.08776  |                     0.08113 |        1.379   |             9.689 |             0.5814 |             0.2674 |
| gradient_boosted_trees                  |            58 |                -0.01476  |                     0.08212 |       -0.4462  |             7.066 |             0.3023 |             0.2442 |
| gradient_boosted_trees                  |            60 |                 0.03624  |                     0.06949 |        0.8246  |             9.731 |             0.2907 |             0.2791 |
| gradient_boosted_trees                  |            62 |                 0.006562 |                     0.05821 |       -0.1718  |             6.924 |             0.3605 |             0.2791 |
| gradient_boosted_trees                  |            64 |                -0.01122  |                     0.06254 |       -0.2304  |             6.594 |             0.3837 |             0.1279 |
| gradient_boosted_trees                  |            65 |                -0.01551  |                     0.07091 |       -1.503   |             9.75  |             0.2791 |             0.1744 |
| mlp                                     |            58 |                -0.01595  |                     0.1072  |       -0.9979  |            12.39  |             0.2558 |             0.3605 |
| mlp                                     |            60 |                 0.0304   |                     0.1023  |       -1.926   |            12.95  |             0.2674 |             0.2558 |
| mlp                                     |            62 |                -0.003876 |                     0.1144  |       -0.4934  |            12.51  |             0.3372 |             0.3372 |
| mlp                                     |            64 |                 0.007353 |                     0.08058 |       -2       |            11.08  |             0.4186 |             0.1512 |
| mlp                                     |            65 |                -0.01078  |                     0.1131  |       -1.208   |            13.05  |             0.2442 |             0.2209 |
| pedestal_memory_fusion_new              |            58 |                -0.01689  |                     0.07252 |       -0.2335  |             6.598 |             0.314  |             0.2791 |
| pedestal_memory_fusion_new              |            60 |                 0.04105  |                     0.06992 |        0.2297  |             8.006 |             0.2791 |             0.1977 |
| pedestal_memory_fusion_new              |            62 |                 0.004628 |                     0.07601 |       -0.2568  |             6.98  |             0.3372 |             0.2326 |
| pedestal_memory_fusion_new              |            64 |                 0.006366 |                     0.06344 |       -0.6742  |             6.953 |             0.3837 |             0.1395 |
| pedestal_memory_fusion_new              |            65 |                -0.01136  |                     0.06905 |       -1.461   |             8.32  |             0.2674 |             0.1744 |
| ridge                                   |            58 |                -0.005848 |                     0.07411 |       -0.5589  |             7.71  |             0.3023 |             0.3023 |
| ridge                                   |            60 |                 0.0495   |                     0.08861 |        0.6083  |             9.802 |             0.2674 |             0.1977 |
| ridge                                   |            62 |                 0.02065  |                     0.0843  |        0.3429  |             8.37  |             0.3256 |             0.3023 |
| ridge                                   |            64 |                -0.006786 |                     0.06517 |        0.6388  |             8.563 |             0.3605 |             0.1395 |
| ridge                                   |            65 |                 0.004638 |                     0.07811 |       -0.1411  |             9.809 |             0.2791 |             0.1744 |
| tiny_sequence_transformer               |            58 |                -0.02095  |                     0.09508 |      -16.9     |            15.42  |             0.3372 |             0.1744 |
| tiny_sequence_transformer               |            60 |                 0.05108  |                     0.1052  |      -12.93    |            14.11  |             0.4186 |             0.1977 |
| tiny_sequence_transformer               |            62 |                 0.001206 |                     0.1121  |      -16.57    |            13.46  |             0.4302 |             0.3023 |
| tiny_sequence_transformer               |            64 |                 0.001072 |                     0.09882 |      -16.16    |            14.39  |             0.4651 |             0.1163 |
| tiny_sequence_transformer               |            65 |                -0.01007  |                     0.1005  |      -13.84    |            15.27  |             0.407  |             0.1512 |

## Pedestal-State Counterfactual Table

| method                                  | pedestal_state   |   n |   energy_bias |   energy_sigma68 |   pid_positive_rate |
|:----------------------------------------|:-----------------|----:|--------------:|-----------------:|--------------------:|
| 1d_cnn                                  | nominal          | 104 |    -0.04321   |          0.06778 |             0.02885 |
| 1d_cnn                                  | shifted          | 172 |    -0.008785  |          0.09917 |             0.1105  |
| ar1_charge_ratio_likelihood_traditional | nominal          |  78 |     0.06655   |          0.1     |             0.02564 |
| ar1_charge_ratio_likelihood_traditional | shifted          |  80 |     0.06887   |          0.09684 |             0.1     |
| gradient_boosted_trees                  | nominal          | 114 |     0.002292  |          0.05634 |             0.02632 |
| gradient_boosted_trees                  | shifted          | 177 |     0.002568  |          0.08492 |             0.1186  |
| mlp                                     | nominal          | 112 |     0.01401   |          0.07862 |             0.02679 |
| mlp                                     | shifted          | 187 |    -0.006036  |          0.1258  |             0.107   |
| pedestal_memory_fusion_new              | nominal          | 111 |     0.001707  |          0.05511 |             0.02703 |
| pedestal_memory_fusion_new              | shifted          | 183 |     0.01302   |          0.08249 |             0.1202  |
| ridge                                   | nominal          | 115 |     0.001261  |          0.0612  |             0.02609 |
| ridge                                   | shifted          | 183 |     0.01526   |          0.1059  |             0.1202  |
| tiny_sequence_transformer               | nominal          |  96 |     0.0001166 |          0.0901  |             0.03125 |
| tiny_sequence_transformer               | shifted          | 157 |     0.003479  |          0.1285  |             0.121   |

## Stratified Systematics

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class:

| stratum        | value          | method                                  |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:---------------|:---------------|:----------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin    | (-0.001, 10.0] | 1d_cnn                                  |                0.004357  |                   0.09159   |        2.221   |             9.671 |             0.5672 |
| spacing_bin    | (10.0, 25.0]   | 1d_cnn                                  |                0.001096  |                   0.08715   |        1.259   |             7.021 |             0.4343 |
| spacing_bin    | (25.0, 45.0]   | 1d_cnn                                  |               -0.02655   |                   0.0788    |       -2.393   |             9.238 |             0.2136 |
| spacing_bin    | (45.0, 70.0]   | 1d_cnn                                  |               -0.03703   |                   0.07996   |       -0.3025  |            14.35  |             0.1383 |
| spacing_bin    | (-0.001, 10.0] | ar1_charge_ratio_likelihood_traditional |                0.1344    |                   0.0988    |        3.286   |            13.97  |             0.7985 |
| spacing_bin    | (10.0, 25.0]   | ar1_charge_ratio_likelihood_traditional |                0.07539   |                   0.09306   |        0.932   |             6.745 |             0.6667 |
| spacing_bin    | (25.0, 45.0]   | ar1_charge_ratio_likelihood_traditional |                0.08091   |                   0.07512   |        1.789   |             8.062 |             0.6117 |
| spacing_bin    | (45.0, 70.0]   | ar1_charge_ratio_likelihood_traditional |                0.0225    |                   0.1011    |       -0.2425  |             8.749 |             0.383  |
| spacing_bin    | (-0.001, 10.0] | gradient_boosted_trees                  |                0.0414    |                   0.06374   |        1.523   |             8.879 |             0.4776 |
| spacing_bin    | (10.0, 25.0]   | gradient_boosted_trees                  |                0.02059   |                   0.07188   |        0.4098  |             6.926 |             0.3434 |
| spacing_bin    | (25.0, 45.0]   | gradient_boosted_trees                  |               -0.01621   |                   0.07077   |       -1.602   |             8.289 |             0.233  |
| spacing_bin    | (45.0, 70.0]   | gradient_boosted_trees                  |               -0.02666   |                   0.0619    |       -0.6483  |             8.852 |             0.1809 |
| spacing_bin    | (-0.001, 10.0] | mlp                                     |                0.03357   |                   0.1135    |        0.3325  |            11.42  |             0.4478 |
| spacing_bin    | (10.0, 25.0]   | mlp                                     |                0.009981  |                   0.1248    |       -1.088   |             8.881 |             0.3838 |
| spacing_bin    | (25.0, 45.0]   | mlp                                     |               -0.01478   |                   0.09259   |       -4.797   |            11.3   |             0.1845 |
| spacing_bin    | (45.0, 70.0]   | mlp                                     |               -0.00146   |                   0.1051    |       -1.198   |            16.63  |             0.1489 |
| spacing_bin    | (-0.001, 10.0] | pedestal_memory_fusion_new              |                0.02614   |                   0.07112   |        2.026   |             7.345 |             0.4627 |
| spacing_bin    | (10.0, 25.0]   | pedestal_memory_fusion_new              |                0.01992   |                   0.06374   |       -0.7699  |             6.609 |             0.3535 |
| spacing_bin    | (25.0, 45.0]   | pedestal_memory_fusion_new              |                0.007673  |                   0.07519   |       -1.607   |             7.672 |             0.2136 |
| spacing_bin    | (45.0, 70.0]   | pedestal_memory_fusion_new              |               -0.02557   |                   0.06577   |       -1.14    |             8.745 |             0.1809 |
| spacing_bin    | (-0.001, 10.0] | ridge                                   |                0.04761   |                   0.07602   |        1.351   |             9.255 |             0.403  |
| spacing_bin    | (10.0, 25.0]   | ridge                                   |                0.01374   |                   0.06542   |        0.3975  |             8.309 |             0.3434 |
| spacing_bin    | (25.0, 45.0]   | ridge                                   |                0.007134  |                   0.07506   |       -0.7142  |             8.566 |             0.2233 |
| spacing_bin    | (45.0, 70.0]   | ridge                                   |               -0.04093   |                   0.06248   |        0.1087  |            10.66  |             0.2234 |
| spacing_bin    | (-0.001, 10.0] | tiny_sequence_transformer               |                0.06298   |                   0.1078    |      -12.57    |             9.112 |             0.6045 |
| spacing_bin    | (10.0, 25.0]   | tiny_sequence_transformer               |                0.05677   |                   0.1097    |      -16.58    |             8.959 |             0.5152 |
| spacing_bin    | (25.0, 45.0]   | tiny_sequence_transformer               |               -0.0009726 |                   0.08216   |      -20.25    |            15.42  |             0.2718 |
| spacing_bin    | (45.0, 70.0]   | tiny_sequence_transformer               |               -0.08079   |                   0.1001    |      -14.43    |            18.64  |             0.1809 |
| ratio_bin      | (-0.001, 0.35] | 1d_cnn                                  |               -0.04167   |                   0.08725   |       -4.028   |            13.47  |             0.62   |
| ratio_bin      | (0.35, 0.625]  | 1d_cnn                                  |               -0.01976   |                   0.09378   |       -0.5298  |            10.59  |             0.3478 |
| ratio_bin      | (0.625, 0.875] | 1d_cnn                                  |               -0.01518   |                   0.07252   |        0.7127  |            10.41  |             0.29   |
| ratio_bin      | (0.875, 1.05]  | 1d_cnn                                  |               -0.01249   |                   0.08994   |        2.548   |            10.65  |             0.2    |
| ratio_bin      | (-0.001, 0.35] | ar1_charge_ratio_likelihood_traditional |                0.04123   |                   0.09959   |       -4.201   |            14.14  |             0.77   |
| ratio_bin      | (0.35, 0.625]  | ar1_charge_ratio_likelihood_traditional |                0.06748   |                   0.09684   |       -0.3627  |             9.85  |             0.5391 |
| ratio_bin      | (0.625, 0.875] | ar1_charge_ratio_likelihood_traditional |                0.05155   |                   0.112     |        1.817   |             7.437 |             0.64   |
| ratio_bin      | (0.875, 1.05]  | ar1_charge_ratio_likelihood_traditional |                0.08414   |                   0.08084   |        1.801   |             7.389 |             0.6    |
| ratio_bin      | (-0.001, 0.35] | gradient_boosted_trees                  |               -0.01308   |                   0.08859   |       -5.332   |             9.795 |             0.57   |
| ratio_bin      | (0.35, 0.625]  | gradient_boosted_trees                  |               -0.003732  |                   0.07763   |       -1.425   |             8.334 |             0.2696 |
| ratio_bin      | (0.625, 0.875] | gradient_boosted_trees                  |                0.008209  |                   0.06802   |        0.9738  |             7.248 |             0.33   |
| ratio_bin      | (0.875, 1.05]  | gradient_boosted_trees                  |                0.005096  |                   0.06658   |        1.951   |             6.852 |             0.1565 |
| ratio_bin      | (-0.001, 0.35] | mlp                                     |               -0.01208   |                   0.1205    |       -4.326   |            14.48  |             0.54   |
| ratio_bin      | (0.35, 0.625]  | mlp                                     |               -0.007842  |                   0.1183    |       -4.298   |            10.89  |             0.287  |
| ratio_bin      | (0.625, 0.875] | mlp                                     |               -0.01642   |                   0.1143    |       -0.4273  |            13.56  |             0.26   |
| ratio_bin      | (0.875, 1.05]  | mlp                                     |                0.02678   |                   0.08553   |        1.191   |            11.64  |             0.1565 |
| ratio_bin      | (-0.001, 0.35] | pedestal_memory_fusion_new              |               -0.001886  |                   0.08621   |       -4.731   |             8.99  |             0.55   |
| ratio_bin      | (0.35, 0.625]  | pedestal_memory_fusion_new              |                0.007673  |                   0.07395   |       -1.784   |             7.258 |             0.2609 |
| ratio_bin      | (0.625, 0.875] | pedestal_memory_fusion_new              |                0.004785  |                   0.06088   |        1.279   |             6.891 |             0.32   |
| ratio_bin      | (0.875, 1.05]  | pedestal_memory_fusion_new              |                0.00445   |                   0.07026   |        1.796   |             6.521 |             0.1652 |
| ratio_bin      | (-0.001, 0.35] | ridge                                   |                0.005113  |                   0.0871    |       -4.571   |             9.531 |             0.59   |
| ratio_bin      | (0.35, 0.625]  | ridge                                   |                0.0006902 |                   0.08196   |       -1.323   |             8.96  |             0.2783 |
| ratio_bin      | (0.625, 0.875] | ridge                                   |                0.01568   |                   0.08228   |        1.526   |             7.712 |             0.27   |
| ratio_bin      | (0.875, 1.05]  | ridge                                   |                0.01007   |                   0.07019   |        3.544   |             8.533 |             0.1217 |
| ratio_bin      | (-0.001, 0.35] | tiny_sequence_transformer               |                0.0233    |                   0.1099    |      -18.89    |            21.13  |             0.69   |
| ratio_bin      | (0.35, 0.625]  | tiny_sequence_transformer               |                0.001293  |                   0.1179    |      -15.81    |            13.37  |             0.4087 |
| ratio_bin      | (0.625, 0.875] | tiny_sequence_transformer               |                0.005212  |                   0.09457   |      -15.6     |            14.21  |             0.34   |
| ratio_bin      | (0.875, 1.05]  | tiny_sequence_transformer               |               -0.001837  |                   0.1069    |      -14.15    |            14.68  |             0.2348 |
| saturation_bin | 0              | 1d_cnn                                  |               -0.01404   |                   0.08711   |        0.7301  |            10.89  |             0.3628 |
| saturation_bin | 1-2            | 1d_cnn                                  |               -0.05071   |                   0.002835  |      -11.21    |             3.086 |             0.5    |
| saturation_bin | 3-5            | 1d_cnn                                  |               -0.1019    |                   0.03417   |       -0.6438  |            10.98  |             0      |
| saturation_bin | 6+             | 1d_cnn                                  |                0.02512   |                   0.07758   |       13.78    |            11.98  |             0      |
| saturation_bin | 0              | ar1_charge_ratio_likelihood_traditional |                0.06462   |                   0.09988   |        0.932   |             8.35  |             0.6325 |
| saturation_bin | 1-2            | ar1_charge_ratio_likelihood_traditional |                0.09978   |                   0         |        0.8089  |            11.9   |             0.75   |
| saturation_bin | 3-5            | ar1_charge_ratio_likelihood_traditional |                0.1762    |                   0.04109   |        0.9134  |            16.95  |             0.4    |
| saturation_bin | 6+             | ar1_charge_ratio_likelihood_traditional |              nan         |                 nan         |      nan       |           nan     |             1      |
| saturation_bin | 0              | gradient_boosted_trees                  |                0.003758  |                   0.07069   |       -0.2278  |             8.495 |             0.3317 |
| saturation_bin | 1-2            | gradient_boosted_trees                  |                0.05711   |                   0.08765   |       -2.247   |             7.172 |             0      |
| saturation_bin | 3-5            | gradient_boosted_trees                  |               -0.1233    |                   0.05465   |       -1.987   |             5.495 |             0      |
| saturation_bin | 6+             | gradient_boosted_trees                  |               -0.03564   |                   0.07611   |       -0.5114  |             3.882 |             0      |
| saturation_bin | 0              | mlp                                     |                0.003197  |                   0.1062    |       -1.491   |            12.45  |             0.3103 |
| saturation_bin | 1-2            | mlp                                     |                0.1906    |                   0.09734   |        6.23    |             9.413 |             0.25   |
| saturation_bin | 3-5            | mlp                                     |               -0.08478   |                   0.1068    |       -0.603   |             9.22  |             0      |
| saturation_bin | 6+             | mlp                                     |               -0.02785   |                   0.09767   |        1.382   |             3.017 |             0      |
| saturation_bin | 0              | pedestal_memory_fusion_new              |                0.005471  |                   0.0722    |       -0.3884  |             7.608 |             0.3246 |
| saturation_bin | 1-2            | pedestal_memory_fusion_new              |                0.06608   |                   0.0595    |       -1.881   |             6.478 |             0      |
| saturation_bin | 3-5            | pedestal_memory_fusion_new              |               -0.07676   |                   0.05279   |       -2.1     |             4.214 |             0      |
| saturation_bin | 6+             | pedestal_memory_fusion_new              |               -0.04757   |                   0.06555   |        0.2726  |             2.441 |             0      |
| saturation_bin | 0              | ridge                                   |                0.009556  |                   0.08192   |        0.3391  |             8.854 |             0.315  |
| saturation_bin | 1-2            | ridge                                   |               -0.06439   |                   0.03954   |       -3.184   |             4.734 |             0      |
| saturation_bin | 3-5            | ridge                                   |               -0.1266    |                   0.03678   |       -1.235   |             6.025 |             0      |
| saturation_bin | 6+             | ridge                                   |               -0.07559   |                   0.06062   |        2.758   |             5.887 |             0      |
| saturation_bin | 0              | tiny_sequence_transformer               |                0.005212  |                   0.1025    |      -15.37    |            14.58  |             0.4177 |
| saturation_bin | 1-2            | tiny_sequence_transformer               |               -0.06819   |                   0.0001264 |      -24.11    |            13.27  |             0.5    |
| saturation_bin | 3-5            | tiny_sequence_transformer               |               -0.1749    |                   0.05815   |      -17.75    |             9.785 |             0      |
| saturation_bin | 6+             | tiny_sequence_transformer               |               -0.143     |                   0.06646   |       -7.535   |             7.471 |             0      |
| pedestal_state | nominal        | 1d_cnn                                  |               -0.04321   |                   0.06778   |        2.277   |             9.787 |             0.3203 |
| pedestal_state | shifted        | 1d_cnn                                  |               -0.008785  |                   0.09917   |       -1.327   |            11.2   |             0.3791 |
| pedestal_state | nominal        | ar1_charge_ratio_likelihood_traditional |                0.06655   |                   0.1       |        1.972   |             7.591 |             0.4902 |
| pedestal_state | shifted        | ar1_charge_ratio_likelihood_traditional |                0.06887   |                   0.09684   |       -0.05032 |             8.772 |             0.7112 |
| pedestal_state | nominal        | gradient_boosted_trees                  |                0.002292  |                   0.05634   |        0.5781  |             7.336 |             0.2549 |
| pedestal_state | shifted        | gradient_boosted_trees                  |                0.002568  |                   0.08492   |       -1.102   |             9.142 |             0.361  |


## Calibration, Confusion, and Interpretability Diagnostics

The winner-specific calibration curve is written to
`calibration_curve_winner.csv`; it bins held-out predicted energy and compares
the bin mean to injected truth, while also reporting the PID-proxy positive
rate.  The corresponding `confusion_matrix_winner.csv` records the
outer/low-charge versus inner/high-charge PID-proxy migration.  The file
`feature_attention_diagnostics.csv` ties the winner's residual behavior back to
pretrigger pedestal strata, late-tail morphology states, and waveform sample
regions.  These diagnostics are intentionally proxy-qualified because the raw
ROOT files do not contain external particle-identity labels.


## Systematics and Caveats

The truth labels are controlled overlays into clean pulses selected from raw
ROOT, so the study tests transfer under known injected truth rather than the
beam's natural pile-up rate.  The PID endpoint is a charge/stave proxy because
the reduced ROOT reproduction gate lacks external particle truth.  ADC clipping
is an explicit benchmark stressor rather than decoded electronics metadata.
Pedestal counterfactuals use observed pretrigger-state strata, not randomized
hardware interventions.  Bootstrap intervals resample held-out runs and
therefore quantify run-transfer uncertainty more than event-counting precision.

## Hypothesis and Next Test

The result suggests that pretrigger pedestal memory is primarily a transfer
nuisance that can be modeled away with waveform-sideband information, while the
apparent PID gain may partly reflect charge/stave support rather than particle
identity.  A decisive falsification would join external PID labels or
digitized-Geant4 event truth and show that the pedestal-memory fusion model no
longer improves true PID confusion after conditioning on charge and stave.  The
single proposed next ticket is `S53a: external PID-label validation for pedestal-state waveform transfer`.

## Verdict

`result.json` names **pedestal_memory_fusion_new** as the S50c winner.  The pedestal-memory
conclusion is: **pedestal memory is mostly removable nuisance in this controlled benchmark, not standalone physics signal**.  Static charge corrections are insufficient when
pedestal-state spans exceed the run-block uncertainty; the preferred workflow is
to model pedestal memory explicitly and to keep PID claims proxy-qualified until
external labels are joined.

Runtime was `317.5` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

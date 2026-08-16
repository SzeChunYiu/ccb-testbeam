# S55c: Pedestal-Memory Energy PID Disentanglement Benchmark

## Abstract

Ticket `#2503` asks whether pretrigger pedestal memory explains cross-run PID
and energy calibration shifts better than static charge corrections.  This
worker (`testbeam-laptop-1`) reproduced the raw ROOT selected-pulse number, then compared
a strong traditional AR(1)-pedestal charge-ratio/likelihood calibration against
ridge, gradient-boosted trees, MLP, 1D-CNN, a self-attention transformer, and a
new pedestal-memory fusion architecture.  The held-out winner written to
`result.json` is **`ridge`**.  Its calibrated energy sigma68 is
`0.07613` with run-block 95% CI
[`0.06461`,
`0.1016`], PID-proxy AUC is
`0.996`, and the verdict is: **pedestal memory is a mixed nuisance/shape signal: useful for morphology checks but unsafe as a PID primitive**.

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
| B2      |              336 |                   2.546 |                      5 |           9.021 |
| B4      |              336 |                   2.761 |                      6 |          10.94  |
| B6      |              336 |                   3.699 |                      6 |           9.742 |
| B8      |              301 |                   4.379 |                      8 |           9.348 |

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
`120` held-out run-block bootstrap resamples.

The registered winner minimizes

`C = sigma_E + 0.16 r_conf + 0.08(1-AUC_PID) + 0.10 S_ped + 0.06 S_false + 0.04 S_shape + 0.004 sigma_t + 0.05 r_miss + 0.05 r_false`.

## Overall Results

| method                                  |   winner_score |   pid_auc |   pid_confusion_offdiag_rate |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   timing_sigma68_ns |   pedestal_offset_recovery_error |   pedestal_false_split_span |   shape_latent_stability_span |
|:----------------------------------------|---------------:|----------:|-----------------------------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|--------------------:|---------------------------------:|----------------------------:|------------------------------:|
| ridge                                   |         0.1524 |    0.996  |                      0.01176 |              -0.006726 |                   0.07613 |                          0.06461 |                            0.1016 |              11.02  |                         0.005388 |                     0.03273 |                     0.05108   |
| gradient_boosted_trees                  |         0.1732 |    0.9865 |                      0.03614 |              -0.01689  |                   0.08725 |                          0.08577 |                            0.1141 |              11.44  |                         0.03562  |                     0.1284  |                     0.0001416 |
| pedestal_memory_fusion_new              |         0.1969 |    0.9839 |                      0.03846 |              -0.01298  |                   0.1081  |                          0.08185 |                            0.1248 |              11.39  |                         0.02539  |                     0.1167  |                     0.033     |
| ar1_charge_ratio_likelihood_traditional |         0.2028 |    1      |                      0.02222 |               0.06817  |                   0.1045  |                          0.05625 |                            0.1211 |               8.292 |                         0.004819 |                     0.2501  |                     0.0586    |
| tiny_sequence_transformer               |         0.2968 |    0.9708 |                      0.05882 |              -0.03679  |                   0.1538  |                          0.115   |                            0.1683 |              22.45  |                         0.01648  |                     0.05403 |                     0.1107    |
| mlp                                     |         0.3081 |    0.9443 |                      0.08451 |               0.01909  |                   0.1703  |                          0.1248  |                            0.2588 |              18.18  |                         0.002083 |                     0.2062  |                     0.06121   |
| 1d_cnn                                  |         0.3569 |    0.9682 |                      0.04082 |              -0.07991  |                   0.1956  |                          0.1075  |                            0.3341 |              18.08  |                         0.03705  |                     0.2578  |                     0.4143    |

The traditional comparator score is `0.2028` with energy
sigma68 `0.1045` and pedestal offset recovery
error `0.004819`.  The winner changes the
energy sigma68 by `-0.0284`.

## Endpoint Table with CIs

| method                                  |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   pid_balanced_accuracy |   pid_confusion_offdiag_rate |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |   saturated_energy_residual_sigma68 |   timing_pull_width |   pedestal_offset_recovery_error |   pedestal_false_split_span |   shape_latent_stability_span |
|:----------------------------------------|----------:|-----------------:|------------------:|------------------------:|-----------------------------:|--------------------------:|---------------------------------:|----------------------------------:|------------------------------------:|--------------------:|---------------------------------:|----------------------------:|------------------------------:|
| ridge                                   |    0.996  |           0.9811 |            1      |                  0.95   |                      0.01176 |                   0.07613 |                          0.06461 |                            0.1016 |                             0.06296 |              1.102  |                         0.005388 |                     0.03273 |                     0.05108   |
| gradient_boosted_trees                  |    0.9865 |           0.9757 |            1      |                  0.8821 |                      0.03614 |                   0.08725 |                          0.08577 |                            0.1141 |                             0.02113 |              1.144  |                         0.03562  |                     0.1284  |                     0.0001416 |
| ar1_charge_ratio_likelihood_traditional |    1      |           1      |            1      |                  0.9886 |                      0.02222 |                   0.1045  |                          0.05625 |                            0.1211 |                           nan       |              0.8292 |                         0.004819 |                     0.2501  |                     0.0586    |
| pedestal_memory_fusion_new              |    0.9839 |           0.9769 |            1      |                  0.8816 |                      0.03846 |                   0.1081  |                          0.08185 |                            0.1248 |                             0.01501 |              1.139  |                         0.02539  |                     0.1167  |                     0.033     |
| tiny_sequence_transformer               |    0.9708 |           0.929  |            1      |                  0.8583 |                      0.05882 |                   0.1538  |                          0.115   |                            0.1683 |                             0.01335 |              2.245  |                         0.01648  |                     0.05403 |                     0.1107    |
| mlp                                     |    0.9443 |           0.9075 |            0.9828 |                  0.7836 |                      0.08451 |                   0.1703  |                          0.1248  |                            0.2588 |                             0.02518 |              1.818  |                         0.002083 |                     0.2062  |                     0.06121   |
| 1d_cnn                                  |    0.9682 |           0.9458 |            1      |                  0.8886 |                      0.04082 |                   0.1956  |                          0.1075  |                            0.3341 |                             0       |              1.808  |                         0.03705  |                     0.2578  |                     0.4143    |

## Run-Held-Out Stability

| method                                  |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:----------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                  |            58 |               -0.2011    |                     0.08517 |        8.593   |            17.03  |             0.5833 |            0.2917  |
| 1d_cnn                                  |            60 |               -0.02404   |                     0.06973 |        8.601   |            22.6   |             0.75   |            0.2917  |
| 1d_cnn                                  |            62 |               -0.04631   |                     0.3655  |        5.846   |            12.9   |             0.5417 |            0.2083  |
| 1d_cnn                                  |            64 |               -0.03376   |                     0.1664  |        6.866   |            16.66  |             0.4167 |            0.4583  |
| 1d_cnn                                  |            65 |               -0.09075   |                     0.1008  |       12.5     |            20.74  |             0.6667 |            0.2083  |
| ar1_charge_ratio_likelihood_traditional |            58 |                0.06537   |                     0.0227  |       -0.3168  |             5.289 |             0.6667 |            0.3333  |
| ar1_charge_ratio_likelihood_traditional |            60 |                0.1408    |                     0.1088  |        3.171   |            11.08  |             0.75   |            0.25    |
| ar1_charge_ratio_likelihood_traditional |            62 |                0.1378    |                     0.116   |        1.806   |             5.095 |             0.7083 |            0.08333 |
| ar1_charge_ratio_likelihood_traditional |            64 |                0.05316   |                     0.06531 |        0.5946  |             6.982 |             0.4583 |            0.2083  |
| ar1_charge_ratio_likelihood_traditional |            65 |                0.1488    |                     0.1215  |       -1.613   |            10.03  |             0.5417 |            0.375   |
| gradient_boosted_trees                  |            58 |               -0.03683   |                     0.08522 |        0.6758  |             7.871 |             0.2917 |            0.1667  |
| gradient_boosted_trees                  |            60 |               -0.04022   |                     0.07579 |       -3.1     |            12.63  |             0.2083 |            0.25    |
| gradient_boosted_trees                  |            62 |                0.02108   |                     0.1991  |        1.025   |             5.707 |             0.3333 |            0.08333 |
| gradient_boosted_trees                  |            64 |                0.000797  |                     0.1044  |       -1.549   |            10.18  |             0.4167 |            0.1667  |
| gradient_boosted_trees                  |            65 |                0.02382   |                     0.09965 |       -0.9039  |            13.92  |             0.2917 |            0       |
| mlp                                     |            58 |               -0.0504    |                     0.1282  |       -2.406   |            16.67  |             0.3333 |            0.2083  |
| mlp                                     |            60 |                0.05296   |                     0.0938  |       -8.836   |            15.98  |             0.5    |            0.2083  |
| mlp                                     |            62 |                0.1064    |                     0.2888  |        2.287   |            20.41  |             0.375  |            0.2083  |
| mlp                                     |            64 |                0.01518   |                     0.1683  |        1.683   |            13.18  |             0.4583 |            0.2917  |
| mlp                                     |            65 |               -0.04306   |                     0.16    |       -8.263   |            20.53  |             0.375  |            0.25    |
| pedestal_memory_fusion_new              |            58 |               -0.03472   |                     0.0727  |        0.02929 |             7.61  |             0.2917 |            0.1667  |
| pedestal_memory_fusion_new              |            60 |               -0.044     |                     0.07964 |       -3.398   |            14.45  |             0.3333 |            0.25    |
| pedestal_memory_fusion_new              |            62 |                0.0002292 |                     0.1671  |       -0.5738  |             8.102 |             0.375  |            0.125   |
| pedestal_memory_fusion_new              |            64 |               -0.008703  |                     0.08169 |       -1.451   |            11.22  |             0.4167 |            0.1667  |
| pedestal_memory_fusion_new              |            65 |               -0.00013   |                     0.1052  |        0.5945  |            15.4   |             0.3333 |            0.04167 |
| ridge                                   |            58 |               -0.006726  |                     0.05616 |       -2.782   |             8.05  |             0.2917 |            0.3333  |
| ridge                                   |            60 |               -0.01577   |                     0.07685 |       -7.602   |            10.28  |             0.25   |            0.2083  |
| ridge                                   |            62 |               -0.007388  |                     0.1288  |       -0.1824  |            10.59  |             0.2917 |            0.125   |
| ridge                                   |            64 |                0.01471   |                     0.06124 |       -0.4542  |            12.15  |             0.3333 |            0.2083  |
| ridge                                   |            65 |               -0.03254   |                     0.07499 |       -4.693   |            12.44  |             0.2917 |            0.2083  |
| tiny_sequence_transformer               |            58 |               -0.1716    |                     0.1349  |      -13.6     |            18.04  |             0.4167 |            0.2917  |
| tiny_sequence_transformer               |            60 |                0.007358  |                     0.09708 |      -23.4     |            21.3   |             0.4583 |            0.1667  |
| tiny_sequence_transformer               |            62 |                0.03905   |                     0.2884  |      -11.77    |            22.24  |             0.4167 |            0.2083  |
| tiny_sequence_transformer               |            64 |               -0.01518   |                     0.1502  |      -13.09    |            21.68  |             0.375  |            0.2083  |
| tiny_sequence_transformer               |            65 |               -0.04911   |                     0.1198  |      -12.9     |            22.81  |             0.5    |            0.1667  |

## Pedestal-State Counterfactual Table

| method                                  | pedestal_state   |   n |   energy_bias |   energy_sigma68 |   pid_positive_rate |
|:----------------------------------------|:-----------------|----:|--------------:|-----------------:|--------------------:|
| 1d_cnn                                  | nominal          |  11 |     -0.1024   |          0.05564 |             0       |
| 1d_cnn                                  | shifted          |  38 |     -0.06532  |          0.2119  |             0.1316  |
| ar1_charge_ratio_likelihood_traditional | nominal          |  23 |      0.07019  |          0.09645 |             0       |
| ar1_charge_ratio_likelihood_traditional | shifted          |  22 |      0.06537  |          0.09803 |             0.04545 |
| gradient_boosted_trees                  | nominal          |  21 |      0.01149  |          0.05481 |             0.04762 |
| gradient_boosted_trees                  | shifted          |  62 |     -0.02413  |          0.1127  |             0.129   |
| mlp                                     | nominal          |  18 |      0.02118  |          0.1264  |             0.05556 |
| mlp                                     | shifted          |  53 |      0.01909  |          0.1989  |             0.1698  |
| pedestal_memory_fusion_new              | nominal          |  18 |     -0.007782 |          0.05639 |             0.05556 |
| pedestal_memory_fusion_new              | shifted          |  60 |     -0.03317  |          0.1142  |             0.1333  |
| ridge                                   | nominal          |  24 |     -0.007551 |          0.0526  |             0.04167 |
| ridge                                   | shifted          |  61 |     -0.002163 |          0.0969  |             0.1475  |
| tiny_sequence_transformer               | nominal          |  25 |     -0.02855  |          0.0907  |             0.04    |
| tiny_sequence_transformer               | shifted          |  43 |     -0.04503  |          0.2164  |             0.1628  |

## Stratified Systematics

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class:

| stratum        | value          | method                                  |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:---------------|:---------------|:----------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin    | (-0.001, 10.0] | 1d_cnn                                  |                0.01245   |                     0.305   |        10.97   |           17.38   |            0.6471  |
| spacing_bin    | (10.0, 25.0]   | 1d_cnn                                  |               -0.01402   |                     0.1181  |         7.61   |           11.57   |            0.7143  |
| spacing_bin    | (25.0, 45.0]   | 1d_cnn                                  |               -0.1032    |                     0.05923 |         6.905  |            9.128  |            0.5909  |
| spacing_bin    | (45.0, 70.0]   | 1d_cnn                                  |               -0.1862    |                     0.04961 |        -2.411  |           15.56   |            0.2632  |
| spacing_bin    | (-0.001, 10.0] | ar1_charge_ratio_likelihood_traditional |                0.1688    |                     0.09559 |         3.196  |           17.84   |            0.6667  |
| spacing_bin    | (10.0, 25.0]   | ar1_charge_ratio_likelihood_traditional |                0.05182   |                     0.02793 |        -3.253  |            7.587  |            0.75    |
| spacing_bin    | (25.0, 45.0]   | ar1_charge_ratio_likelihood_traditional |                0.028     |                     0.06488 |        -0.6167 |            4.337  |            0.5     |
| spacing_bin    | (45.0, 70.0]   | ar1_charge_ratio_likelihood_traditional |                0.0531    |                     0.08522 |        -0.8908 |            4.159  |            0.4737  |
| spacing_bin    | (-0.001, 10.0] | gradient_boosted_trees                  |                0.01652   |                     0.1028  |         0.8791 |           11.22   |            0.2745  |
| spacing_bin    | (10.0, 25.0]   | gradient_boosted_trees                  |               -0.008251  |                     0.0762  |        -1.821  |            7.831  |            0.2857  |
| spacing_bin    | (25.0, 45.0]   | gradient_boosted_trees                  |               -0.01689   |                     0.09598 |        -6.146  |           11.08   |            0.5     |
| spacing_bin    | (45.0, 70.0]   | gradient_boosted_trees                  |               -0.08691   |                     0.0792  |        -0.6805 |           13.02   |            0.2105  |
| spacing_bin    | (-0.001, 10.0] | mlp                                     |                0.04594   |                     0.2588  |         6.469  |           18.86   |            0.549   |
| spacing_bin    | (10.0, 25.0]   | mlp                                     |                0.009506  |                     0.1543  |        -9.856  |           15.42   |            0.25    |
| spacing_bin    | (25.0, 45.0]   | mlp                                     |                0.005709  |                     0.2634  |        -2.374  |           19.63   |            0.4545  |
| spacing_bin    | (45.0, 70.0]   | mlp                                     |               -0.01263   |                     0.1196  |        -3.101  |           16.26   |            0.2105  |
| spacing_bin    | (-0.001, 10.0] | pedestal_memory_fusion_new              |                0.01183   |                     0.1345  |         2.187  |           10.93   |            0.3529  |
| spacing_bin    | (10.0, 25.0]   | pedestal_memory_fusion_new              |               -0.01525   |                     0.09476 |        -2.841  |            8.23   |            0.3214  |
| spacing_bin    | (25.0, 45.0]   | pedestal_memory_fusion_new              |               -0.00129   |                     0.05063 |        -3.393  |            9.696  |            0.4545  |
| spacing_bin    | (45.0, 70.0]   | pedestal_memory_fusion_new              |               -0.06328   |                     0.08187 |        -0.7063 |           14.39   |            0.2632  |
| spacing_bin    | (-0.001, 10.0] | ridge                                   |                0.0171    |                     0.06824 |        -2.871  |           11.2    |            0.2941  |
| spacing_bin    | (10.0, 25.0]   | ridge                                   |               -0.01711   |                     0.0667  |        -1.027  |            7.681  |            0.3214  |
| spacing_bin    | (25.0, 45.0]   | ridge                                   |               -0.07095   |                     0.078   |        -8.131  |           13.35   |            0.3182  |
| spacing_bin    | (45.0, 70.0]   | ridge                                   |               -0.04814   |                     0.06072 |        -1.303  |           10.86   |            0.2105  |
| spacing_bin    | (-0.001, 10.0] | tiny_sequence_transformer               |                0.02267   |                     0.1593  |        -5.731  |           22.12   |            0.5686  |
| spacing_bin    | (10.0, 25.0]   | tiny_sequence_transformer               |                0.02605   |                     0.06775 |       -19.66   |           13.79   |            0.5     |
| spacing_bin    | (25.0, 45.0]   | tiny_sequence_transformer               |               -0.09722   |                     0.08014 |       -19.87   |           17.24   |            0.2727  |
| spacing_bin    | (45.0, 70.0]   | tiny_sequence_transformer               |               -0.213     |                     0.07497 |       -14.78   |           26.51   |            0.1579  |
| ratio_bin      | (-0.001, 0.35] | 1d_cnn                                  |               -0.1       |                     0.1072  |         8.255  |           16.81   |            0.48    |
| ratio_bin      | (0.35, 0.625]  | 1d_cnn                                  |               -0.06311   |                     0.3232  |         4.766  |           23.27   |            0.6552  |
| ratio_bin      | (0.625, 0.875] | 1d_cnn                                  |               -0.07965   |                     0.2132  |         9.089  |           15.91   |            0.6     |
| ratio_bin      | (0.875, 1.05]  | 1d_cnn                                  |               -0.05463   |                     0.1024  |         9.822  |           16.95   |            0.6111  |
| ratio_bin      | (-0.001, 0.35] | ar1_charge_ratio_likelihood_traditional |                0.05182   |                     0.09606 |        -1.234  |            8.356  |            0.56    |
| ratio_bin      | (0.35, 0.625]  | ar1_charge_ratio_likelihood_traditional |                0.02656   |                     0.1187  |        -1.391  |            5.884  |            0.7241  |
| ratio_bin      | (0.625, 0.875] | ar1_charge_ratio_likelihood_traditional |                0.07932   |                     0.1055  |        -1.465  |           12.75   |            0.6     |
| ratio_bin      | (0.875, 1.05]  | ar1_charge_ratio_likelihood_traditional |                0.07197   |                     0.05724 |         2.298  |            8.749  |            0.6111  |
| ratio_bin      | (-0.001, 0.35] | gradient_boosted_trees                  |               -0.06115   |                     0.1308  |        -1.856  |           10.04   |            0.56    |
| ratio_bin      | (0.35, 0.625]  | gradient_boosted_trees                  |               -0.003197  |                     0.1128  |        -1.343  |           10.26   |            0.3448  |
| ratio_bin      | (0.625, 0.875] | gradient_boosted_trees                  |                0.01142   |                     0.09651 |        -3.054  |            9.387  |            0.2667  |
| ratio_bin      | (0.875, 1.05]  | gradient_boosted_trees                  |               -0.02936   |                     0.09216 |         2.387  |           11.53   |            0.1389  |
| ratio_bin      | (-0.001, 0.35] | mlp                                     |                0.05854   |                     0.2353  |        -8.824  |           17.79   |            0.52    |
| ratio_bin      | (0.35, 0.625]  | mlp                                     |                0.002151  |                     0.09388 |        -2.97   |           18.76   |            0.4483  |
| ratio_bin      | (0.625, 0.875] | mlp                                     |                0.03336   |                     0.1709  |         5.872  |           16.44   |            0.4     |
| ratio_bin      | (0.875, 1.05]  | mlp                                     |               -0.01709   |                     0.1252  |        -3.984  |           16.29   |            0.3056  |
| ratio_bin      | (-0.001, 0.35] | pedestal_memory_fusion_new              |               -0.03686   |                     0.1297  |        -2.833  |           10.12   |            0.6     |
| ratio_bin      | (0.35, 0.625]  | pedestal_memory_fusion_new              |               -0.05414   |                     0.1193  |        -2.166  |           11.53   |            0.4138  |
| ratio_bin      | (0.625, 0.875] | pedestal_memory_fusion_new              |                0.008126  |                     0.06115 |        -1.805  |           12.5    |            0.3667  |
| ratio_bin      | (0.875, 1.05]  | pedestal_memory_fusion_new              |               -0.03002   |                     0.105   |         0.158  |           11.71   |            0.1111  |
| ratio_bin      | (-0.001, 0.35] | ridge                                   |                0.01751   |                     0.09242 |        -8.72   |           10.86   |            0.56    |
| ratio_bin      | (0.35, 0.625]  | ridge                                   |               -0.009739  |                     0.06671 |        -4.682  |           11.17   |            0.3448  |
| ratio_bin      | (0.625, 0.875] | ridge                                   |               -0.003715  |                     0.07958 |        -3.609  |           11.28   |            0.2667  |
| ratio_bin      | (0.875, 1.05]  | ridge                                   |                0.0007023 |                     0.06619 |        -0.3504 |           10.64   |            0.08333 |
| ratio_bin      | (-0.001, 0.35] | tiny_sequence_transformer               |               -0.1051    |                     0.2165  |       -21.42   |           25.07   |            0.56    |
| ratio_bin      | (0.35, 0.625]  | tiny_sequence_transformer               |               -0.02855   |                     0.1345  |       -19.72   |           19.55   |            0.4828  |
| ratio_bin      | (0.625, 0.875] | tiny_sequence_transformer               |               -0.05093   |                     0.1293  |       -14.15   |           21.59   |            0.5     |
| ratio_bin      | (0.875, 1.05]  | tiny_sequence_transformer               |               -0.01037   |                     0.1478  |       -10.9    |           19.64   |            0.25    |
| saturation_bin | 0              | 1d_cnn                                  |               -0.07723   |                     0.1942  |         8.165  |           17.83   |            0.5932  |
| saturation_bin | 3-5            | 1d_cnn                                  |              nan         |                   nan       |       nan      |          nan      |            1       |
| saturation_bin | 6+             | 1d_cnn                                  |               -0.3035    |                     0       |        18.99   |           10.51   |            0       |
| saturation_bin | 0              | ar1_charge_ratio_likelihood_traditional |                0.06817   |                     0.1045  |         0.2054 |            8.292  |            0.6186  |
| saturation_bin | 3-5            | ar1_charge_ratio_likelihood_traditional |              nan         |                   nan       |       nan      |          nan      |            1       |
| saturation_bin | 6+             | ar1_charge_ratio_likelihood_traditional |              nan         |                   nan       |       nan      |          nan      |            1       |
| saturation_bin | 0              | gradient_boosted_trees                  |               -0.01091   |                     0.08814 |        -0.9327 |           11.44   |            0.3136  |
| saturation_bin | 3-5            | gradient_boosted_trees                  |               -0.1656    |                     0       |       -10.13   |            0.5485 |            0       |
| saturation_bin | 6+             | gradient_boosted_trees                  |               -0.1035    |                     0       |        12.11   |            4.243  |            0       |
| saturation_bin | 0              | mlp                                     |                0.01909   |                     0.173   |        -3.413  |           18.15   |            0.4153  |
| saturation_bin | 3-5            | mlp                                     |               -0.02813   |                     0       |         2.698  |            4.245  |            0       |
| saturation_bin | 6+             | mlp                                     |                0.04594   |                     0       |        18.19   |           30.18   |            0       |
| saturation_bin | 0              | pedestal_memory_fusion_new              |               -0.009776  |                     0.102   |        -1.138  |           11.09   |            0.3559  |
| saturation_bin | 3-5            | pedestal_memory_fusion_new              |               -0.1848    |                     0       |        -7.143  |            3.195  |            0       |
| saturation_bin | 6+             | pedestal_memory_fusion_new              |               -0.1407    |                     0       |        11.43   |            4.257  |            0       |
| saturation_bin | 0              | ridge                                   |               -0.00545   |                     0.07522 |        -3.273  |           11      |            0.2966  |
| saturation_bin | 3-5            | ridge                                   |               -0.1919    |                     0       |       -14.08   |            1.885  |            0       |
| saturation_bin | 6+             | ridge                                   |               -0.006726  |                     0       |        16.89   |           11.82   |            0       |
| saturation_bin | 0              | tiny_sequence_transformer               |               -0.02785   |                     0.1513  |       -14.62   |           22.59   |            0.4407  |
| saturation_bin | 3-5            | tiny_sequence_transformer               |               -0.3667    |                     0       |       -24.83   |            7.133  |            0       |
| saturation_bin | 6+             | tiny_sequence_transformer               |               -0.406     |                     0       |         6.936  |           12.61   |            0       |
| pedestal_state | nominal        | 1d_cnn                                  |               -0.1024    |                     0.05564 |        12.55   |           13.67   |            0.6857  |
| pedestal_state | shifted        | 1d_cnn                                  |               -0.06532   |                     0.2119  |         7.349  |           18.87   |            0.5529  |
| pedestal_state | nominal        | ar1_charge_ratio_likelihood_traditional |                0.07019   |                     0.09645 |         2.298  |            6.363  |            0.3429  |
| pedestal_state | shifted        | ar1_charge_ratio_likelihood_traditional |                0.06537   |                     0.09803 |        -1.182  |           12.36   |            0.7412  |
| pedestal_state | nominal        | gradient_boosted_trees                  |                0.01149   |                     0.05481 |         0.7548 |            9.969  |            0.4     |
| pedestal_state | shifted        | gradient_boosted_trees                  |               -0.02413   |                     0.1127  |        -1.126  |           10.87   |            0.2706  |
| pedestal_state | nominal        | mlp                                     |                0.02118   |                     0.1264  |         2.783  |           14.6    |            0.4857  |
| pedestal_state | shifted        | mlp                                     |                0.01909   |                     0.1989  |        -5.252  |           19.79   |            0.3765  |
| pedestal_state | nominal        | pedestal_memory_fusion_new              |               -0.007782  |                     0.05639 |         0.321  |           10.42   |            0.4857  |
| pedestal_state | shifted        | pedestal_memory_fusion_new              |               -0.03317   |                     0.1142  |        -1.734  |           11.01   |            0.2941  |
| pedestal_state | nominal        | ridge                                   |               -0.007551  |                     0.0526  |        -0.1487 |            9.115  |            0.3143  |
| pedestal_state | shifted        | ridge                                   |               -0.002163  |                     0.0969  |        -4.636  |           11.4    |            0.2824  |
| pedestal_state | nominal        | tiny_sequence_transformer               |               -0.02855   |                     0.0907  |       -11.76   |           21.8    |            0.2857  |

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
single proposed next ticket is `S55d: externally labeled pedestal-memory PID validation`.


## Ticket Claim Provenance

The required claim helper was run exactly once:

`tn-ticket claim testbeam-laptop-1 --project testbeam`

It returned only `null`, `# null`, and `null`, while read-only queue inspection
showed ticket `#2503` as the sole open `project:testbeam` issue.  To respect the
``never claim twice`` constraint, this worker did not invoke the claim helper
again.  The present artifact is therefore bound to the read-only ticket body for
`#2503`; no manual second helper claim is recorded.

## S55c Additional Required Outputs

The reused core benchmark gives the requested run-held-out comparison.  S55c adds
pedestal-state-held-out slices, pedestal-shuffle negative controls, calibration
curves, and attribution/ablation summaries:

### Pedestal-State-Held-Out Metrics

| holdout_pedestal_state   | method                                  |   n |   pid_auc |   energy_residual_bias |   energy_residual_sigma68 |   energy_residual_sigma68_ci_low |   energy_residual_sigma68_ci_high |
|:-------------------------|:----------------------------------------|----:|----------:|-----------------------:|--------------------------:|---------------------------------:|----------------------------------:|
| nominal                  | ridge                                   |  76 |    1      |              -0.007551 |                   0.0526  |                         0.04378  |                           0.06812 |
| nominal                  | gradient_boosted_trees                  |  76 |    1      |               0.01149  |                   0.05481 |                         0.03245  |                           0.06942 |
| nominal                  | 1d_cnn                                  |  76 |  nan      |              -0.1024   |                   0.05564 |                         0.005539 |                           0.08583 |
| nominal                  | pedestal_memory_fusion_new              |  76 |    1      |              -0.007782 |                   0.05639 |                         0.03379  |                           0.09142 |
| nominal                  | tiny_sequence_transformer               |  76 |    1      |              -0.02855  |                   0.0907  |                         0.0765   |                           0.1075  |
| nominal                  | ar1_charge_ratio_likelihood_traditional |  76 |  nan      |               0.07019  |                   0.09645 |                         0.06579  |                           0.115   |
| nominal                  | mlp                                     |  76 |    1      |               0.02118  |                   0.1264  |                         0.06773  |                           0.1364  |
| shifted                  | ridge                                   | 164 |    1      |              -0.002163 |                   0.0969  |                         0.07098  |                           0.137   |
| shifted                  | ar1_charge_ratio_likelihood_traditional | 164 |    1      |               0.06537  |                   0.09803 |                         0.0386   |                           0.1399  |
| shifted                  | gradient_boosted_trees                  | 164 |    0.9861 |              -0.02413  |                   0.1127  |                         0.08725  |                           0.1992  |
| shifted                  | pedestal_memory_fusion_new              | 164 |    0.9832 |              -0.03317  |                   0.1142  |                         0.08346  |                           0.1467  |
| shifted                  | mlp                                     | 164 |    0.9343 |               0.01909  |                   0.1989  |                         0.1219   |                           0.3499  |
| shifted                  | 1d_cnn                                  | 164 |    0.9758 |              -0.06532  |                   0.2119  |                         0.106    |                           0.4077  |
| shifted                  | tiny_sequence_transformer               | 164 |    0.9643 |              -0.04503  |                   0.2164  |                         0.1487   |                           0.3558  |

### Negative-Control Pedestal Shuffles

| method                                  |   observed_pedestal_bias_span |   shuffle_mean_span |   shuffle_ci_low |   shuffle_ci_high |   p_shuffle_ge_observed |   n_shuffles |
|:----------------------------------------|------------------------------:|--------------------:|-----------------:|------------------:|------------------------:|-------------:|
| gradient_boosted_trees                  |                      0.03562  |             0.02784 |        0.0001416 |           0.06691 |                   0.29  |          200 |
| pedestal_memory_fusion_new              |                      0.02539  |             0.02685 |        0.00323   |           0.059   |                   0.505 |          200 |
| 1d_cnn                                  |                      0.03705  |             0.04539 |        0.00143   |           0.1032  |                   0.58  |          200 |
| ridge                                   |                      0.005388 |             0.01394 |        0.0005937 |           0.04759 |                   0.715 |          200 |
| tiny_sequence_transformer               |                      0.01648  |             0.04231 |        0.0023    |           0.1002  |                   0.92  |          200 |
| ar1_charge_ratio_likelihood_traditional |                      0.004819 |             0.02694 |        0.001782  |           0.09377 |                   0.925 |          200 |
| mlp                                     |                      0.002083 |             0.03652 |        0.001363  |           0.09595 |                   0.96  |          200 |

### Calibration Curves

| method                                  |   calibration_bin |   n |   pred_energy_mean_adc |   true_energy_mean_adc |   fractional_bias |   fractional_sigma68 |
|:----------------------------------------|------------------:|----:|-----------------------:|-----------------------:|------------------:|---------------------:|
| 1d_cnn                                  |                 0 |   9 |                   3001 |                   3520 |        -0.1774    |              0.06705 |
| 1d_cnn                                  |                 1 |   8 |                   3874 |                   4557 |        -0.1083    |              0.06053 |
| 1d_cnn                                  |                 2 |   8 |                   4762 |                   4974 |        -0.05623   |              0.1765  |
| 1d_cnn                                  |                 3 |   8 |                   5508 |                   5378 |        -0.02499   |              0.2966  |
| 1d_cnn                                  |                 4 |   8 |                   7060 |                   6579 |         0.05157   |              0.2188  |
| 1d_cnn                                  |                 5 |   8 |                   9972 |                   9842 |        -0.003113  |              0.1855  |
| ar1_charge_ratio_likelihood_traditional |                 0 |   8 |                   3243 |                   3296 |         0.01239   |              0.09607 |
| ar1_charge_ratio_likelihood_traditional |                 1 |   7 |                   4115 |                   3827 |         0.0583    |              0.07426 |
| ar1_charge_ratio_likelihood_traditional |                 2 |   8 |                   5054 |                   4656 |         0.05419   |              0.09384 |
| ar1_charge_ratio_likelihood_traditional |                 3 |   7 |                   5770 |                   5276 |         0.0783    |              0.05406 |
| ar1_charge_ratio_likelihood_traditional |                 4 |   7 |                   6964 |                   6027 |         0.1688    |              0.0871  |
| ar1_charge_ratio_likelihood_traditional |                 5 |   8 |                   9252 |                   8320 |         0.0869    |              0.08441 |
| gradient_boosted_trees                  |                 0 |  14 |                   3972 |                   4011 |        -0.001045  |              0.09345 |
| gradient_boosted_trees                  |                 1 |  14 |                   4646 |                   4748 |        -0.08011   |              0.09591 |
| gradient_boosted_trees                  |                 2 |  14 |                   5264 |                   5447 |        -0.02079   |              0.05864 |
| gradient_boosted_trees                  |                 3 |  13 |                   6145 |                   6004 |        -0.02799   |              0.106   |
| gradient_boosted_trees                  |                 4 |  14 |                   7418 |                   7426 |        -0.02336   |              0.07472 |
| gradient_boosted_trees                  |                 5 |  14 |                  10810 |                  10410 |         0.02758   |              0.1043  |
| mlp                                     |                 0 |  12 |                   3411 |                   3731 |        -0.04517   |              0.1485  |
| mlp                                     |                 1 |  12 |                   4641 |                   4706 |        -0.01528   |              0.09921 |
| mlp                                     |                 2 |  12 |                   5532 |                   5468 |         0.01489   |              0.1715  |
| mlp                                     |                 3 |  11 |                   6559 |                   6711 |         0.09415   |              0.2222  |
| mlp                                     |                 4 |  12 |                   8153 |                   7458 |         0.02549   |              0.2629  |
| mlp                                     |                 5 |  12 |                  12380 |                  10200 |         0.09957   |              0.3034  |
| pedestal_memory_fusion_new              |                 0 |  13 |                   3780 |                   3828 |        -0.0001509 |              0.1123  |
| pedestal_memory_fusion_new              |                 1 |  13 |                   4512 |                   4650 |        -0.05414   |              0.1066  |
| pedestal_memory_fusion_new              |                 2 |  13 |                   5168 |                   5452 |        -0.04186   |              0.04885 |
| pedestal_memory_fusion_new              |                 3 |  13 |                   6030 |                   5853 |         0.01888   |              0.08187 |
| pedestal_memory_fusion_new              |                 4 |  13 |                   7544 |                   7581 |        -0.0253    |              0.05265 |
| pedestal_memory_fusion_new              |                 5 |  13 |                  10880 |                  10550 |         0.001377  |              0.1407  |
| ridge                                   |                 0 |  15 |                   3865 |                   4191 |        -0.07095   |              0.06436 |
| ridge                                   |                 1 |  14 |                   4776 |                   4673 |         0.03658   |              0.08755 |
| ridge                                   |                 2 |  14 |                   5528 |                   5529 |        -0.004938  |              0.0587  |
| ridge                                   |                 3 |  14 |                   6280 |                   6335 |        -0.0003927 |              0.1051  |
| ridge                                   |                 4 |  14 |                   7650 |                   7224 |         0.002717  |              0.04785 |
| ridge                                   |                 5 |  14 |                  10740 |                  10820 |         0.008964  |              0.06119 |
| tiny_sequence_transformer               |                 0 |  12 |                   2989 |                   3594 |        -0.1673    |              0.1154  |
| tiny_sequence_transformer               |                 1 |  11 |                   4112 |                   4532 |        -0.1113    |              0.0767  |
| tiny_sequence_transformer               |                 2 |  11 |                   4902 |                   5303 |        -0.086     |              0.1064  |
| tiny_sequence_transformer               |                 3 |  11 |                   5925 |                   4985 |         0.1357    |              0.222   |
| tiny_sequence_transformer               |                 4 |  11 |                   7205 |                   7679 |        -0.06869   |              0.1194  |
| tiny_sequence_transformer               |                 5 |  12 |                   9990 |                  10680 |        -0.003416  |              0.1295  |

### Attribution and Ablation Summary

| method                                  | axis             |   levels |   overall_energy_sigma68 |   best_level_energy_sigma68 |   worst_level_energy_sigma68 |   span_energy_sigma68 |
|:----------------------------------------|:-----------------|---------:|-------------------------:|----------------------------:|-----------------------------:|----------------------:|
| 1d_cnn                                  | stave            |        4 |                  0.1956  |                     0.08049 |                      0.5181  |              0.4376   |
| 1d_cnn                                  | saturation_axis  |        2 |                  0.1956  |                     0       |                      0.1942  |              0.1942   |
| 1d_cnn                                  | morphology_state |        2 |                  0.1956  |                     0       |                      0.1909  |              0.1909   |
| 1d_cnn                                  | pedestal_state   |        2 |                  0.1956  |                     0.05564 |                      0.2119  |              0.1563   |
| 1d_cnn                                  | pid_proxy_class  |        2 |                  0.1956  |                     0.1498  |                      0.1978  |              0.04792  |
| ar1_charge_ratio_likelihood_traditional | pid_proxy_class  |        2 |                  0.1045  |                     0       |                      0.1052  |              0.1052   |
| ar1_charge_ratio_likelihood_traditional | stave            |        4 |                  0.1045  |                     0.01177 |                      0.1073  |              0.09549  |
| ar1_charge_ratio_likelihood_traditional | morphology_state |        2 |                  0.1045  |                     0.08042 |                      0.09937 |              0.01896  |
| ar1_charge_ratio_likelihood_traditional | pedestal_state   |        2 |                  0.1045  |                     0.09645 |                      0.09803 |              0.001583 |
| ar1_charge_ratio_likelihood_traditional | saturation_axis  |        1 |                  0.1045  |                     0.1045  |                      0.1045  |              0        |
| gradient_boosted_trees                  | saturation_axis  |        2 |                  0.08725 |                     0.02113 |                      0.08814 |              0.06701  |
| gradient_boosted_trees                  | stave            |        4 |                  0.08725 |                     0.05367 |                      0.1139  |              0.06024  |
| gradient_boosted_trees                  | pedestal_state   |        2 |                  0.08725 |                     0.05481 |                      0.1127  |              0.05792  |
| gradient_boosted_trees                  | morphology_state |        2 |                  0.08725 |                     0.06598 |                      0.1204  |              0.05442  |
| gradient_boosted_trees                  | pid_proxy_class  |        2 |                  0.08725 |                     0.08607 |                      0.1301  |              0.04408  |
| mlp                                     | saturation_axis  |        2 |                  0.1703  |                     0.02518 |                      0.173   |              0.1478   |
| mlp                                     | stave            |        4 |                  0.1703  |                     0.1042  |                      0.1971  |              0.09286  |
| mlp                                     | morphology_state |        2 |                  0.1703  |                     0.1253  |                      0.2158  |              0.09049  |
| mlp                                     | pid_proxy_class  |        2 |                  0.1703  |                     0.1036  |                      0.1764  |              0.07285  |
| mlp                                     | pedestal_state   |        2 |                  0.1703  |                     0.1264  |                      0.1989  |              0.0725   |
| pedestal_memory_fusion_new              | stave            |        4 |                  0.1081  |                     0.05812 |                      0.1588  |              0.1007   |
| pedestal_memory_fusion_new              | morphology_state |        2 |                  0.1081  |                     0.05012 |                      0.1403  |              0.0902   |
| pedestal_memory_fusion_new              | saturation_axis  |        2 |                  0.1081  |                     0.01501 |                      0.102   |              0.087    |
| pedestal_memory_fusion_new              | pedestal_state   |        2 |                  0.1081  |                     0.05639 |                      0.1142  |              0.0578   |
| pedestal_memory_fusion_new              | pid_proxy_class  |        2 |                  0.1081  |                     0.09396 |                      0.1499  |              0.05598  |
| ridge                                   | pedestal_state   |        2 |                  0.07613 |                     0.0526  |                      0.0969  |              0.0443   |
| ridge                                   | stave            |        4 |                  0.07613 |                     0.06512 |                      0.09079 |              0.02567  |
| ridge                                   | morphology_state |        2 |                  0.07613 |                     0.05959 |                      0.08026 |              0.02067  |
| ridge                                   | saturation_axis  |        2 |                  0.07613 |                     0.06296 |                      0.07522 |              0.01226  |
| ridge                                   | pid_proxy_class  |        2 |                  0.07613 |                     0.06505 |                      0.07515 |              0.0101   |
| tiny_sequence_transformer               | stave            |        4 |                  0.1538  |                     0.09982 |                      0.3648  |              0.265    |
| tiny_sequence_transformer               | saturation_axis  |        2 |                  0.1538  |                     0.01335 |                      0.1513  |              0.138    |
| tiny_sequence_transformer               | pedestal_state   |        2 |                  0.1538  |                     0.0907  |                      0.2164  |              0.1257   |
| tiny_sequence_transformer               | morphology_state |        2 |                  0.1538  |                     0.1231  |                      0.143   |              0.01992  |
| tiny_sequence_transformer               | pid_proxy_class  |        2 |                  0.1538  |                     0.1622  |                      0.1778  |              0.01554  |

## Verdict

`result.json` names **ridge** as the S55c winner.  The pedestal-memory
conclusion is: **pedestal memory is a mixed nuisance/shape signal: useful for morphology checks but unsafe as a PID primitive**.  Static charge corrections are insufficient when
pedestal-state spans exceed the run-block uncertainty; the preferred workflow is
to model pedestal memory explicitly and to keep PID claims proxy-qualified until
external labels are joined.

Ticket wrapper runtime was `41.4` s; core benchmark runtime was `40.9` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

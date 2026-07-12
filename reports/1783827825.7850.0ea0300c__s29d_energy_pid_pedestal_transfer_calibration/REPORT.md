# S29d energy-PID pedestal transfer calibration study

## Abstract

Ticket `1783827825.7850.0ea0300c` asks for a raw-ROOT-reproduced benchmark of joint PID, energy,
and timing inference.  The worker was `testbeam-laptop-4`.  The raw selected-pulse anchor
is reproduced directly from ROOT before any model comparison: `640737`
selected B-stave pulses versus the reference `640737`,
with delta `0`.

The winner is `gradient_boosted_trees` by the declared held-out score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy fractional sigma68 `0.1084`
with 95% run-block bootstrap CI [0.09225,
0.1212], timing sigma68
`10.53` ns, PID balanced accuracy
`0.9688`, PID efficiency `0.9375`,
and PID purity `1`.

## Raw ROOT reproduction

Raw files were read from `/home/billy/ccb-data/extracted/root/root`.  Each `h101/HRDv` branch was
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8, pedestal `b_c = median(x_c[0:4])`, corrected waveform
`y_c(t)=x_c(t)-b_c`, and `max_t y_c(t)>1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Truth model and split

The benchmark uses controlled two-pulse injections into raw single-pulse residuals.
Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`; no source run appears in both sets.  Clean
templates are built from train runs only.

The PID endpoint is a deterministic raw-waveform proxy, not external particle
truth.  It defines a deuteron-like high-dE/dx-depth class by a threshold in total
injected energy proxy, stave depth, and area-over-peak shape.  The label is used
only to compare architecture families under identical controlled truth.

For injected doublets,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{r,s}(t) + p`,

where `epsilon_{r,s}` is a residual sampled from raw clean pulses in the same
run/stave and `p` is a pedestal offset.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              256 |                   2.411 |                      5 |           9.237 |
| B4      |              256 |                   3.044 |                      6 |          10.81  |
| B6      |              256 |                   3.714 |                      6 |           9.559 |
| B8      |              246 |                   4.364 |                      8 |           9.387 |

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`.  It combines a
bounded two-pulse template/CFD fit for energy and timing with a diagonal Gaussian
likelihood-ratio PID model over deltaE/E-like raw features: log amplitude,
area-over-peak, tail fraction, late fraction, peak sample, pulse widths, stave
depth, and dE/dx proxy.  For class `y`, the PID score is

`log p(x|y) = -1/2 sum_j [(x_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains ridge classifiers/regressors, histogram gradient-boosted
trees, MLP classifiers/regressors, a compact 1D-CNN plus PID head, a
`joint_sequence_transformer`, and a new physics-residual boosted stack that feeds
the traditional fit estimates into boosted residual PID and recovery heads.

Timing and energy metrics use only injected doublets accepted by the method:

`e_t = 10 ns * (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`,

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`180` held-out run-block bootstrap resamples.

## Overall held-out results

| method                              |   winner_score |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|----------:|------------------------:|-----------------:|-------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees              |         0.2529 |    1      |                  0.9688 |           0.9375 |       1      |                     0.1084  |                            0.09225 |                              0.1212 |            10.53  |                    8.34  |                     11.37 |             0.2818 |             0.3455 |
| template_residual_boosted_stack_new |         0.2585 |    0.9985 |                  0.8725 |           0.75   |       0.9231 |                     0.102   |                            0.08872 |                              0.1102 |             9.506 |                    7.628 |                     10.67 |             0.2727 |             0.3182 |
| ridge                               |         0.2681 |    0.9975 |                  0.75   |           0.5    |       1      |                     0.07325 |                            0.05565 |                              0.1033 |            10.19  |                    8.582 |                     11.86 |             0.3545 |             0.2545 |
| deltaE_over_E_likelihood_template   |         0.2917 |    0.9265 |                  0.6415 |           0.3125 |       0.4545 |                     0.07021 |                            0.0588  |                              0.1005 |             9.737 |                    6.326 |                     12.4  |             0.5364 |             0.1545 |
| 1d_cnn                              |         0.4233 |    0.8058 |                  0.6538 |           0.3125 |       0.8333 |                     0.1074  |                            0.0897  |                              0.1229 |            18.8   |                   16.09  |                     22.75 |             0.2182 |             0.6091 |
| joint_sequence_transformer          |         0.4598 |    0.7923 |                  0.5    |           0      |       0      |                     0.1249  |                            0.1044  |                              0.2042 |            17.63  |                   15.78  |                     19.56 |             0.3091 |             0.3636 |
| mlp                                 |         0.6732 |    0.898  |                  0.6562 |           0.3125 |       1      |                     0.3901  |                            0.2172  |                              0.4729 |            15.22  |                   10.23  |                     29.83 |             0.8    |             0.1    |

Relative to the traditional baseline, `gradient_boosted_trees` changes energy sigma68 by
`0.0382`,
timing sigma68 by `0.7963` ns,
and PID balanced accuracy by `0.3272`.

## Run-held-out stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.6    |             0.2  |       1      |                     0.0835  |            12.93  |            0.3182  |            0.5909  |
| 1d_cnn                              |            60 |                  0.6    |             0.2  |       1      |                     0.1317  |            20.26  |            0.1364  |            0.6364  |
| 1d_cnn                              |            62 |                  0.75   |             0.5  |       1      |                     0.07365 |            21.68  |            0.3636  |            0.5909  |
| 1d_cnn                              |            64 |                  1      |             1    |       1      |                     0.08704 |            18.68  |            0.1364  |            0.5909  |
| 1d_cnn                              |            65 |                  0.4884 |             0    |       0      |                     0.1202  |            17.45  |            0.1364  |            0.6364  |
| deltaE_over_E_likelihood_template   |            58 |                  0.4872 |             0    |       0      |                     0.07998 |             6.238 |            0.5455  |            0.2273  |
| deltaE_over_E_likelihood_template   |            60 |                  0.6744 |             0.4  |       0.5    |                     0.09982 |            12.62  |            0.3182  |            0.1818  |
| deltaE_over_E_likelihood_template   |            62 |                  0.7375 |             0.5  |       0.6667 |                     0.07117 |             4.615 |            0.6818  |            0.09091 |
| deltaE_over_E_likelihood_template   |            64 |                  0.9767 |             1    |       0.3333 |                     0.03859 |             9.624 |            0.5455  |            0.04545 |
| deltaE_over_E_likelihood_template   |            65 |                  0.5    |             0    |       0      |                     0.03369 |            10.32  |            0.5909  |            0.2273  |
| gradient_boosted_trees              |            58 |                  0.9    |             0.8  |       1      |                     0.1093  |             7.034 |            0.3636  |            0.4545  |
| gradient_boosted_trees              |            60 |                  1      |             1    |       1      |                     0.103   |             9.93  |            0.1818  |            0.5909  |
| gradient_boosted_trees              |            62 |                  1      |             1    |       1      |                     0.1102  |            11.34  |            0.3182  |            0.2273  |
| gradient_boosted_trees              |            64 |                  1      |             1    |       1      |                     0.1002  |             9.593 |            0.3636  |            0.1364  |
| gradient_boosted_trees              |            65 |                  1      |             1    |       1      |                     0.07436 |             8.091 |            0.1818  |            0.3182  |
| joint_sequence_transformer          |            58 |                  0.5    |             0    |       0      |                     0.1184  |            17.9   |            0.2727  |            0.3636  |
| joint_sequence_transformer          |            60 |                  0.5    |             0    |       0      |                     0.1029  |            15.67  |            0.2273  |            0.4545  |
| joint_sequence_transformer          |            62 |                  0.5    |             0    |       0      |                     0.2234  |            17.63  |            0.3182  |            0.2727  |
| joint_sequence_transformer          |            64 |                  0.5    |             0    |       0      |                     0.05768 |            19.57  |            0.4091  |            0.3636  |
| joint_sequence_transformer          |            65 |                  0.5    |             0    |       0      |                     0.1713  |            15.05  |            0.3182  |            0.3636  |
| mlp                                 |            58 |                  0.6    |             0.2  |       1      |                     0       |             6.225 |            0.9545  |            0.09091 |
| mlp                                 |            60 |                  0.7    |             0.4  |       1      |                     0.3397  |            17.48  |            0.7273  |            0.1364  |
| mlp                                 |            62 |                  0.75   |             0.5  |       1      |                     0.2255  |            36.85  |            0.8636  |            0.09091 |
| mlp                                 |            64 |                  0.5    |             0    |       0      |                     0.3074  |             7.527 |            0.7273  |            0.09091 |
| mlp                                 |            65 |                  0.5    |             0    |       0      |                     0.284   |            20.38  |            0.7273  |            0.09091 |
| ridge                               |            58 |                  0.7    |             0.4  |       1      |                     0.05247 |             6.111 |            0.3182  |            0.1818  |
| ridge                               |            60 |                  0.7    |             0.4  |       1      |                     0.07605 |            10.26  |            0.2727  |            0.5455  |
| ridge                               |            62 |                  0.875  |             0.75 |       1      |                     0.1036  |            11.28  |            0.3636  |            0.2273  |
| ridge                               |            64 |                  1      |             1    |       1      |                     0.04023 |             7.663 |            0.5     |            0.1364  |
| ridge                               |            65 |                  0.5    |             0    |       0      |                     0.0686  |            11.01  |            0.3182  |            0.1818  |
| template_residual_boosted_stack_new |            58 |                  0.9    |             0.8  |       1      |                     0.1039  |             6.183 |            0.3182  |            0.4545  |
| template_residual_boosted_stack_new |            60 |                  0.8    |             0.6  |       1      |                     0.09622 |             8.993 |            0.2273  |            0.5909  |
| template_residual_boosted_stack_new |            62 |                  1      |             1    |       1      |                     0.07013 |             8.669 |            0.4091  |            0.1818  |
| template_residual_boosted_stack_new |            64 |                  0.9884 |             1    |       0.5    |                     0.099   |             8.956 |            0.3182  |            0.1364  |
| template_residual_boosted_stack_new |            65 |                  0.5    |             0    |       0      |                     0.07659 |             7.712 |            0.09091 |            0.2273  |

## Strata and systematics

The stratum scan covers pulse spacing, total energy proxy, stave/depth, and PID
truth class.  It is designed to expose whether a method wins only by rejecting
difficult pile-up, only in one stave, or only in one ionization regime.

| stratum     | value               | method                              |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |
|:------------|:--------------------|:------------------------------------|------------------------:|----------------------------:|------------------:|-------------------:|
| spacing_bin | (-0.001, 10.0]      | 1d_cnn                              |                  0.625  |                     0.08581 |            21.08  |            0.2826  |
| spacing_bin | (10.0, 25.0]        | 1d_cnn                              |                  0.75   |                     0.1535  |            16.09  |            0.1538  |
| spacing_bin | (25.0, 45.0]        | 1d_cnn                              |                  0.75   |                     0.04112 |            15.16  |            0.1     |
| spacing_bin | (45.0, 70.0]        | 1d_cnn                              |                  0.5    |                     0.06602 |            15.01  |            0.2778  |
| spacing_bin | (-0.001, 10.0]      | deltaE_over_E_likelihood_template   |                  0.5893 |                     0.04346 |            16.16  |            0.6304  |
| spacing_bin | (10.0, 25.0]        | deltaE_over_E_likelihood_template   |                  0.75   |                     0.06408 |             7.359 |            0.6923  |
| spacing_bin | (25.0, 45.0]        | deltaE_over_E_likelihood_template   |                  0.625  |                     0.05759 |             6.023 |            0.35    |
| spacing_bin | (45.0, 70.0]        | deltaE_over_E_likelihood_template   |                  0.5893 |                     0.1297  |             8.732 |            0.2778  |
| spacing_bin | (-0.001, 10.0]      | gradient_boosted_trees              |                  0.875  |                     0.05179 |            13.87  |            0.3913  |
| spacing_bin | (10.0, 25.0]        | gradient_boosted_trees              |                  1      |                     0.1037  |             7.772 |            0.1538  |
| spacing_bin | (25.0, 45.0]        | gradient_boosted_trees              |                  1      |                     0.07967 |            10.99  |            0.3     |
| spacing_bin | (45.0, 70.0]        | gradient_boosted_trees              |                  1      |                     0.1261  |             7.42  |            0.1667  |
| spacing_bin | (-0.001, 10.0]      | joint_sequence_transformer          |                  0.5    |                     0.1369  |            18.85  |            0.413   |
| spacing_bin | (10.0, 25.0]        | joint_sequence_transformer          |                  0.5    |                     0.1642  |            13.91  |            0.3077  |
| spacing_bin | (25.0, 45.0]        | joint_sequence_transformer          |                  0.5    |                     0.05029 |            13.19  |            0.25    |
| spacing_bin | (45.0, 70.0]        | joint_sequence_transformer          |                  0.5    |                     0.06855 |            18.83  |            0.1111  |
| spacing_bin | (-0.001, 10.0]      | mlp                                 |                  0.625  |                     0.4647  |            22.98  |            0.7826  |
| spacing_bin | (10.0, 25.0]        | mlp                                 |                  0.625  |                     0.122   |             9.259 |            0.8846  |
| spacing_bin | (25.0, 45.0]        | mlp                                 |                  0.5    |                     0.2689  |            13.7   |            0.75    |
| spacing_bin | (45.0, 70.0]        | mlp                                 |                  0.875  |                     0.2532  |             9.279 |            0.7778  |
| spacing_bin | (-0.001, 10.0]      | ridge                               |                  0.625  |                     0.0511  |            12.86  |            0.4565  |
| spacing_bin | (10.0, 25.0]        | ridge                               |                  0.75   |                     0.07875 |             8.212 |            0.2692  |
| spacing_bin | (25.0, 45.0]        | ridge                               |                  0.875  |                     0.0638  |             9.797 |            0.35    |
| spacing_bin | (45.0, 70.0]        | ridge                               |                  0.75   |                     0.0788  |            11.32  |            0.2222  |
| spacing_bin | (-0.001, 10.0]      | template_residual_boosted_stack_new |                  0.875  |                     0.07233 |            13.47  |            0.3913  |
| spacing_bin | (10.0, 25.0]        | template_residual_boosted_stack_new |                  1      |                     0.1082  |             6.478 |            0.1538  |
| spacing_bin | (25.0, 45.0]        | template_residual_boosted_stack_new |                  0.8438 |                     0.06454 |            10.34  |            0.25    |
| spacing_bin | (45.0, 70.0]        | template_residual_boosted_stack_new |                  0.75   |                     0.09381 |             7.799 |            0.1667  |
| energy_bin  | (1547.999, 2951.75] | 1d_cnn                              |                  1      |                     0.09175 |            14.37  |            0.3333  |
| energy_bin  | (2951.75, 3830.75]  | 1d_cnn                              |                  1      |                     0.1392  |            15.11  |            0.25    |
| energy_bin  | (3830.75, 5070.5]   | 1d_cnn                              |                  0.9821 |                     0.1348  |            18.3   |            0.1786  |
| energy_bin  | (5070.5, 10660.0]   | 1d_cnn                              |                  0.6562 |                     0.1041  |            19.74  |            0.2041  |
| energy_bin  | (1547.999, 2951.75] | deltaE_over_E_likelihood_template   |                  1      |                     0.01586 |            26.91  |            0.6667  |
| energy_bin  | (2951.75, 3830.75]  | deltaE_over_E_likelihood_template   |                  0.9818 |                     0.08229 |             9.047 |            0.5833  |
| energy_bin  | (3830.75, 5070.5]   | deltaE_over_E_likelihood_template   |                  1      |                     0.08228 |            14.33  |            0.6071  |
| energy_bin  | (5070.5, 10660.0]   | deltaE_over_E_likelihood_template   |                  0.5905 |                     0.06851 |             6.307 |            0.449   |
| energy_bin  | (1547.999, 2951.75] | gradient_boosted_trees              |                  1      |                     0       |             7.003 |            0.8889  |
| energy_bin  | (2951.75, 3830.75]  | gradient_boosted_trees              |                  1      |                     0.1339  |            11.9   |            0.375   |
| energy_bin  | (3830.75, 5070.5]   | gradient_boosted_trees              |                  1      |                     0.08186 |             9.325 |            0.3214  |
| energy_bin  | (5070.5, 10660.0]   | gradient_boosted_trees              |                  0.9688 |                     0.0947  |             9.905 |            0.102   |
| energy_bin  | (1547.999, 2951.75] | joint_sequence_transformer          |                  1      |                     0.09553 |            30.71  |            0.6667  |
| energy_bin  | (2951.75, 3830.75]  | joint_sequence_transformer          |                  1      |                     0.1431  |            19.03  |            0.2917  |
| energy_bin  | (3830.75, 5070.5]   | joint_sequence_transformer          |                  1      |                     0.1073  |            16.95  |            0.3214  |
| energy_bin  | (5070.5, 10660.0]   | joint_sequence_transformer          |                  0.5    |                     0.113   |            15.3   |            0.2449  |
| energy_bin  | (1547.999, 2951.75] | mlp                                 |                  1      |                     0.7207  |            19.2   |            0.7778  |
| energy_bin  | (2951.75, 3830.75]  | mlp                                 |                  1      |                     0.2159  |            12.37  |            0.75    |
| energy_bin  | (3830.75, 5070.5]   | mlp                                 |                  1      |                     0.1354  |            13.33  |            0.8214  |
| energy_bin  | (5070.5, 10660.0]   | mlp                                 |                  0.6562 |                     0.2474  |            19.07  |            0.8163  |
| energy_bin  | (1547.999, 2951.75] | ridge                               |                  1      |                   nan       |           nan     |            1       |
| energy_bin  | (2951.75, 3830.75]  | ridge                               |                  1      |                     0.1262  |            13.9   |            0.7083  |
| energy_bin  | (3830.75, 5070.5]   | ridge                               |                  1      |                     0.07627 |            10.49  |            0.2857  |
| energy_bin  | (5070.5, 10660.0]   | ridge                               |                  0.75   |                     0.06819 |             9.215 |            0.102   |
| energy_bin  | (1547.999, 2951.75] | template_residual_boosted_stack_new |                  1      |                   nan       |           nan     |            1       |
| energy_bin  | (2951.75, 3830.75]  | template_residual_boosted_stack_new |                  1      |                     0.1337  |            10.8   |            0.3333  |
| energy_bin  | (3830.75, 5070.5]   | template_residual_boosted_stack_new |                  1      |                     0.08629 |             7.96  |            0.25    |
| energy_bin  | (5070.5, 10660.0]   | template_residual_boosted_stack_new |                  0.8618 |                     0.09194 |             9.388 |            0.1224  |
| stave       | B2                  | 1d_cnn                              |                  0.9861 |                     0.3065  |            19.23  |            0.6     |
| stave       | B4                  | 1d_cnn                              |                  1      |                     0.1594  |            16.72  |            0.3333  |
| stave       | B6                  | 1d_cnn                              |                  0.5    |                     0.08168 |            19.02  |            0.09375 |
| stave       | B8                  | 1d_cnn                              |                  0.6429 |                     0.07072 |            19.34  |            0.06061 |
| stave       | B2                  | deltaE_over_E_likelihood_template   |                  0.9167 |                     0.0342  |            21.49  |            0.6     |
| stave       | B4                  | deltaE_over_E_likelihood_template   |                  1      |                     0.06903 |            15.15  |            0.8     |
| stave       | B6                  | deltaE_over_E_likelihood_template   |                  0.5    |                     0.04673 |             7.713 |            0.5625  |
| stave       | B8                  | deltaE_over_E_likelihood_template   |                  0.6429 |                     0.1002  |             5.508 |            0.2424  |
| stave       | B2                  | gradient_boosted_trees              |                  1      |                     0.1499  |            10.12  |            0.5333  |
| stave       | B4                  | gradient_boosted_trees              |                  1      |                     0.08175 |             9.944 |            0.2667  |
| stave       | B6                  | gradient_boosted_trees              |                  1      |                     0.09984 |            10.47  |            0.3438  |
| stave       | B8                  | gradient_boosted_trees              |                  0.9643 |                     0.09251 |             6.685 |            0.1212  |
| stave       | B2                  | joint_sequence_transformer          |                  0.5    |                     0.4802  |            23.42  |            0.4     |
| stave       | B4                  | joint_sequence_transformer          |                  1      |                     0.1415  |            17.25  |            0.4     |
| stave       | B6                  | joint_sequence_transformer          |                  0.5    |                     0.09406 |            16.03  |            0.375   |
| stave       | B8                  | joint_sequence_transformer          |                  0.5    |                     0.08582 |            15.08  |            0.1212  |
| stave       | B2                  | mlp                                 |                  1      |                     0.4527  |            17.02  |            0.5333  |
| stave       | B4                  | mlp                                 |                  1      |                     0.3394  |            10.96  |            0.7667  |
| stave       | B6                  | mlp                                 |                  0.5    |                     0.2268  |            17.22  |            0.8125  |
| stave       | B8                  | mlp                                 |                  0.6429 |                     0.1186  |             5.849 |            0.9394  |
| stave       | B2                  | ridge                               |                  1      |                     0.05585 |            11.73  |            0.6667  |
| stave       | B4                  | ridge                               |                  1      |                     0.05218 |            10.42  |            0.3667  |
| stave       | B6                  | ridge                               |                  0.5    |                     0.1044  |             9.01  |            0.4062  |
| stave       | B8                  | ridge                               |                  0.75   |                     0.06703 |             6.21  |            0.1515  |
| stave       | B2                  | template_residual_boosted_stack_new |                  1      |                     0.1439  |            10.6   |            0.5333  |
| stave       | B4                  | template_residual_boosted_stack_new |                  1      |                     0.1051  |            10.66  |            0.2667  |
| stave       | B6                  | template_residual_boosted_stack_new |                  0.5    |                     0.06885 |             8.742 |            0.3438  |
| stave       | B8                  | template_residual_boosted_stack_new |                  0.8832 |                     0.08605 |             6.534 |            0.09091 |
| pid_truth   | deuteron_like       | 1d_cnn                              |                  0.3125 |                     0.07342 |            15.73  |            0.25    |
| pid_truth   | proton_like         | 1d_cnn                              |                  0.9951 |                     0.1075  |            19.51  |            0.2128  |
| pid_truth   | deuteron_like       | deltaE_over_E_likelihood_template   |                  0.3125 |                     0.06164 |             2.564 |            0.125   |
| pid_truth   | proton_like         | deltaE_over_E_likelihood_template   |                  0.9706 |                     0.07184 |            12.39  |            0.6064  |
| pid_truth   | deuteron_like       | gradient_boosted_trees              |                  0.9375 |                     0.0951  |             6.772 |            0.0625  |
| pid_truth   | proton_like         | gradient_boosted_trees              |                  1      |                     0.1096  |            10.58  |            0.3191  |
| pid_truth   | deuteron_like       | joint_sequence_transformer          |                  0      |                     0.08507 |            15.84  |            0       |
| pid_truth   | proton_like         | joint_sequence_transformer          |                  1      |                     0.178   |            17.77  |            0.3617  |
| pid_truth   | deuteron_like       | mlp                                 |                  0.3125 |                     0.2179  |            15.37  |            0.875   |
| pid_truth   | proton_like         | mlp                                 |                  1      |                     0.4003  |            15.91  |            0.7872  |
| pid_truth   | deuteron_like       | ridge                               |                  0.5    |                     0.06043 |             8.632 |            0       |
| pid_truth   | proton_like         | ridge                               |                  1      |                     0.08297 |            10.05  |            0.4149  |
| pid_truth   | deuteron_like       | template_residual_boosted_stack_new |                  0.75   |                     0.07482 |             6.421 |            0.0625  |
| pid_truth   | proton_like         | template_residual_boosted_stack_new |                  0.9951 |                     0.1048  |            10.08  |            0.3085  |

Systematic limitations are material.  The PID label is a proxy derived from raw
waveform observables and controlled injections, so it is suitable for architecture
ranking but not for a final particle-identification claim.  The saturation and
pile-up truths are controlled-injection truths, not hardware truth flags.  The
18-sample B-stack window limits separations below one sample and makes pedestal
excursions partially degenerate with late tails.  The bootstrap resamples source
runs, so intervals quantify run-transfer uncertainty rather than asymptotic
event-level precision.

## Caveats

This report names a winner for the controlled raw-ROOT-derived benchmark.  A
physics deployment would need external PID anchors, hand-scanned real pile-up
candidates, and electronics saturation metadata.  The analysis nevertheless keeps
the requested ingredients together: a strong traditional method, ridge, boosted
trees, MLP, 1D-CNN, and a new joint architecture, all split by run with bootstrap
CIs and raw ROOT reproduction.

Runtime was `163.8` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.


## S29d transfer calibration synthesis

The S29d ticket asks whether waveform-derived energy and PID calibration remains
stable across pedestal regimes, saturation bands, pile-up load, and pulse-shape
families.  The primary winner retained in `result.json` is the overall
held-out composite-score winner `gradient_boosted_trees`.  A stricter transfer-only
stress score, computed from worst-case strata, selects `gradient_boosted_trees`.

The stress score is

`T_m = R68_E,worst + 0.01 sigma_t,worst + 0.25(1-BAcc_PID,worst) + 0.05 r_miss,worst + 0.10 |bias_E|_max`.

This stress score is not a replacement for the primary winner rule; it is the
ticket-specific systematic guard for calibration transfer.

### Method panel

| method                              | family                  | role                                                                      |
|:------------------------------------|:------------------------|:--------------------------------------------------------------------------|
| deltaE_over_E_likelihood_template   | strong traditional      | charge-integration, template timing, and deltaE/E Gaussian PID likelihood |
| ridge                               | linear ML               | regularized linear accessibility test                                     |
| gradient_boosted_trees              | tree ML                 | nonlinear threshold and saturation interactions                           |
| mlp                                 | tabular neural network  | dense nonlinear pulse-summary model                                       |
| 1d_cnn                              | waveform neural network | local 18-sample convolutional waveform model                              |
| joint_sequence_transformer          | new architecture        | compact full-context waveform transformer with PID and energy heads       |
| template_residual_boosted_stack_new | new architecture        | physics residual stack using traditional estimates as residual features   |

### Overall versus transfer ranking

| method                              |   winner_score |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   transfer_score |   worst_pid_balanced_accuracy |   worst_energy_fractional_sigma68 |   max_abs_energy_bias |
|:------------------------------------|---------------:|------------------------:|----------------------------:|------------------:|-----------------:|------------------------------:|----------------------------------:|----------------------:|
| gradient_boosted_trees              |        0.25292 |                 0.96875 |                    0.10841  |           10.533  |          0.33367 |                       0.9     |                           0.14993 |              0.13192  |
| template_residual_boosted_stack_new |        0.2585  |                 0.87255 |                    0.10203  |            9.5058 |          0.42337 |                       0.5     |                           0.14393 |              0.088479 |
| ridge                               |        0.26807 |                 0.75    |                    0.073248 |           10.187  |          0.44657 |                       0.5     |                           0.14841 |              0.073627 |
| deltaE_over_E_likelihood_template   |        0.29174 |                 0.64154 |                    0.070209 |            9.7368 |          0.49364 |                       0.48718 |                           0.10502 |              0.055355 |
| 1d_cnn                              |        0.42329 |                 0.6538  |                    0.1074   |           18.798  |          0.6942  |                       0.48837 |                           0.30648 |              0.12994  |
| joint_sequence_transformer          |        0.45983 |                 0.5     |                    0.1249   |           17.629  |          0.92688 |                       0.5     |                           0.48017 |              0.16328  |
| mlp                                 |        0.67315 |                 0.65625 |                    0.39006  |           15.215  |          1.1663  |                       0.5     |                           0.55905 |              0.63728  |

### Worst-case transfer summary

| method                              |   transfer_score |   worst_pid_balanced_accuracy |   worst_energy_fractional_sigma68 |   max_abs_energy_bias |   worst_time_sigma68_ns |   worst_pileup_miss_rate |   n_transfer_cells |
|:------------------------------------|-----------------:|------------------------------:|----------------------------------:|----------------------:|------------------------:|-------------------------:|-------------------:|
| gradient_boosted_trees              |          0.33367 |                       0.9     |                           0.14993 |              0.13192  |                  11.34  |                  0.64286 |                 21 |
| template_residual_boosted_stack_new |          0.42337 |                       0.5     |                           0.14393 |              0.088479 |                  10.987 |                  0.71429 |                 21 |
| ridge                               |          0.44657 |                       0.5     |                           0.14841 |              0.073627 |                  12.294 |                  0.85714 |                 21 |
| deltaE_over_E_likelihood_template   |          0.49364 |                       0.48718 |                           0.10502 |              0.055355 |                  21.489 |                  0.8     |                 21 |
| 1d_cnn                              |          0.6942  |                       0.48837 |                           0.30648 |              0.12994  |                  21.682 |                  0.6     |                 21 |
| joint_sequence_transformer          |          0.92688 |                       0.5     |                           0.48017 |              0.16328  |                  26.19  |                  0.86957 |                 21 |
| mlp                                 |          1.1663  |                       0.5     |                           0.55905 |              0.63728  |                  36.852 |                  1       |                 21 |

### Transfer-axis table with bootstrap intervals

| transfer_axis   | stratum              | method                              |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |
|:----------------|:---------------------|:------------------------------------|------------------------:|-------------------------------:|--------------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|
| pedestal_regime | high_area_over_peak  | 1d_cnn                              |                 0.64206 |                        0.55177 |                         0.74434 |                    0.21441  |                          0.20318   |                            0.25854  |           15.534  |                 12.851   |                   16.292  |
| pedestal_regime | high_area_over_peak  | deltaE_over_E_likelihood_template   |                 0.71032 |                        0.62268 |                         0.86762 |                    0.091133 |                          0.055388  |                            0.11074  |           10.939  |                  7.8798  |                   14.781  |
| pedestal_regime | high_area_over_peak  | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.12823  |                          0.10658   |                            0.14506  |            9.6524 |                  8.1549  |                   13.259  |
| pedestal_regime | high_area_over_peak  | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.21419  |                          0.14988   |                            0.27737  |           17.084  |                 16.499   |                   19.842  |
| pedestal_regime | high_area_over_peak  | mlp                                 |                 0.7     |                        0.575   |                         0.85    |                    0.39266  |                          0.22209   |                            0.48355  |           19.608  |                 13.581   |                   36.352  |
| pedestal_regime | high_area_over_peak  | ridge                               |                 0.8     |                        0.71905 |                         0.93492 |                    0.085144 |                          0.07469   |                            0.13233  |           12.16   |                  9.0595  |                   14.6    |
| pedestal_regime | high_area_over_peak  | template_residual_boosted_stack_new |                 0.9     |                        0.73    |                         1       |                    0.10702  |                          0.087609  |                            0.12734  |            9.2441 |                  7.6342  |                   11.815  |
| pedestal_regime | low_area_over_peak   | 1d_cnn                              |                 1       |                        1       |                         1       |                    0.080085 |                          0.065311  |                            0.11841  |           12.329  |                 10.352   |                   16.113  |
| pedestal_regime | low_area_over_peak   | deltaE_over_E_likelihood_template   |                 1       |                        1       |                         1       |                    0.034938 |                          0.0134    |                            0.042719 |            3.3026 |                  1.25    |                   30.682  |
| pedestal_regime | low_area_over_peak   | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.070823 |                          0.037655  |                            0.098962 |            8.0466 |                  6.7866  |                    9.8129 |
| pedestal_regime | low_area_over_peak   | joint_sequence_transformer          |                 1       |                        1       |                         1       |                    0.017136 |                          0         |                            0.018988 |            8.3078 |                  2.1785  |                   16.588  |
| pedestal_regime | low_area_over_peak   | mlp                                 |                 1       |                        1       |                         1       |                  nan        |                        nan         |                          nan        |          nan      |                nan       |                  nan      |
| pedestal_regime | low_area_over_peak   | ridge                               |                 1       |                        1       |                         1       |                    0.065617 |                          0.0087533 |                            0.084858 |            4.5103 |                  2.4017  |                    5.9748 |
| pedestal_regime | low_area_over_peak   | template_residual_boosted_stack_new |                 0.98649 |                        0.95645 |                         1       |                    0.080406 |                          0.047613  |                            0.10114  |            7.4252 |                  5.5921  |                    8.9844 |
| pedestal_regime | mid_area_over_peak   | 1d_cnn                              |                 0.66667 |                        0.56    |                         0.75    |                    0.055722 |                          0.051762  |                            0.096825 |           16.005  |                 13.084   |                   16.914  |
| pedestal_regime | mid_area_over_peak   | deltaE_over_E_likelihood_template   |                 0.49254 |                        0.48441 |                         0.5     |                    0.060226 |                          0.037275  |                            0.091195 |            7.0577 |                  4.5912  |                   10.259  |
| pedestal_regime | mid_area_over_peak   | gradient_boosted_trees              |                 0.91667 |                        0.84762 |                         1       |                    0.083235 |                          0.07333   |                            0.11157  |            8.9123 |                  5.8257  |                   11.426  |
| pedestal_regime | mid_area_over_peak   | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.047348 |                          0.027875  |                            0.10312  |           17.76   |                 14.754   |                   19.011  |
| pedestal_regime | mid_area_over_peak   | mlp                                 |                 0.58333 |                        0.5     |                         1       |                    0.19536  |                          0         |                            0.36625  |            2.8499 |                  0.75551 |                    3.62   |
| pedestal_regime | mid_area_over_peak   | ridge                               |                 0.66667 |                        0.55    |                         0.75    |                    0.048091 |                          0.023965  |                            0.082585 |            7.5012 |                  4.9381  |                   10.275  |
| pedestal_regime | mid_area_over_peak   | template_residual_boosted_stack_new |                 0.83333 |                        0.5     |                         0.95714 |                    0.091274 |                          0.057376  |                            0.09907  |            7.9459 |                  5.8831  |                    8.9472 |
| pileup_load     | high_overlap         | 1d_cnn                              |                 0.66667 |                        0.53    |                         0.89167 |                    0.085481 |                          0.066004  |                            0.14844  |           20.705  |                 17.155   |                   23.038  |
| pileup_load     | high_overlap         | deltaE_over_E_likelihood_template   |                 0.63889 |                        0.44589 |                         0.79455 |                    0.045488 |                          0.034049  |                            0.068892 |           14.394  |                  7.0337  |                   18.976  |
| pileup_load     | high_overlap         | gradient_boosted_trees              |                 0.91667 |                        0.78    |                         1       |                    0.081133 |                          0.053186  |                            0.10726  |           11.029  |                  7.9301  |                   13.766  |
| pileup_load     | high_overlap         | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.14644  |                          0.07316   |                            0.18093  |           17.412  |                 13.401   |                   18.75   |
| pileup_load     | high_overlap         | mlp                                 |                 0.58333 |                        0.5     |                         0.7125  |                    0.42009  |                          0.31858   |                            0.88954  |           21.576  |                  4.7418  |                   30.534  |
| pileup_load     | high_overlap         | ridge                               |                 0.66667 |                        0.55972 |                         0.9     |                    0.050503 |                          0.036635  |                            0.080043 |           12.294  |                 10.858   |                   13.577  |
| pileup_load     | high_overlap         | template_residual_boosted_stack_new |                 0.91667 |                        0.8     |                         1       |                    0.085202 |                          0.067051  |                            0.1007   |           10.987  |                  7.9233  |                   14.54   |
| pileup_load     | low_overlap          | 1d_cnn                              |                 0.64286 |                        0.5     |                         0.85    |                    0.062704 |                          0.055418  |                            0.13672  |           13.941  |                 12.444   |                   16.965  |
| pileup_load     | low_overlap          | deltaE_over_E_likelihood_template   |                 0.61905 |                        0.47246 |                         0.73636 |                    0.087656 |                          0.066624  |                            0.13984  |            9.3583 |                  5.818   |                   17.427  |
| pileup_load     | low_overlap          | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.10383  |                          0.081154  |                            0.13141  |            8.5072 |                  7.2901  |                    9.6353 |
| pileup_load     | low_overlap          | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.068597 |                          0.060906  |                            0.10108  |           18.738  |                 16.933   |                   23.662  |
| pileup_load     | low_overlap          | mlp                                 |                 0.71429 |                        0.66667 |                         0.75    |                    0.40222  |                          0.094974  |                            0.45212  |           13.616  |                  9.3282  |                   28.071  |
| pileup_load     | low_overlap          | ridge                               |                 0.85714 |                        0.76667 |                         1       |                    0.08684  |                          0.066038  |                            0.17323  |           10.66   |                  7.4306  |                   14.197  |
| pileup_load     | low_overlap          | template_residual_boosted_stack_new |                 0.85714 |                        0.75    |                         1       |                    0.080196 |                          0.057254  |                            0.12751  |            8.8657 |                  7.0623  |                   10.978  |
| pileup_load     | mid_overlap          | 1d_cnn                              |                 0.66667 |                        0.5     |                         1       |                    0.1116   |                          0.050548  |                            0.2396   |           17.036  |                 11.964   |                   19.847  |
| pileup_load     | mid_overlap          | deltaE_over_E_likelihood_template   |                 0.66667 |                        0.5     |                         1       |                    0.060578 |                          0.038384  |                            0.10765  |            7.4331 |                  3.8524  |                    9.8318 |
| pileup_load     | mid_overlap          | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.08985  |                          0.076106  |                            0.1551   |            8.524  |                  6.3121  |                   10.12   |
| pileup_load     | mid_overlap          | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.10363  |                          0.043436  |                            0.21746  |           14.701  |                  8.4244  |                   16.112  |
| pileup_load     | mid_overlap          | mlp                                 |                 0.66667 |                        0.5     |                         1       |                    0.15954  |                          0         |                            0.22708  |            7.1305 |                  5.5534  |                    9.4238 |
| pileup_load     | mid_overlap          | ridge                               |                 0.66667 |                        0.5     |                         1       |                    0.067911 |                          0.035812  |                            0.084842 |            7.7646 |                  5.4665  |                   12.478  |
| pileup_load     | mid_overlap          | template_residual_boosted_stack_new |                 0.80702 |                        0.45516 |                         1       |                    0.087551 |                          0.057546  |                            0.12853  |            8.2507 |                  6.4462  |                   11.65   |
| run_family      | heldout_run_family_1 | 1d_cnn                              |                 0.6     |                      nan       |                       nan       |                    0.0835   |                        nan         |                          nan        |           12.934  |                nan       |                  nan      |
| run_family      | heldout_run_family_1 | deltaE_over_E_likelihood_template   |                 0.48718 |                      nan       |                       nan       |                    0.07998  |                        nan         |                          nan        |            6.2378 |                nan       |                  nan      |
| run_family      | heldout_run_family_1 | gradient_boosted_trees              |                 0.9     |                      nan       |                       nan       |                    0.10929  |                        nan         |                          nan        |            7.0336 |                nan       |                  nan      |
| run_family      | heldout_run_family_1 | joint_sequence_transformer          |                 0.5     |                      nan       |                       nan       |                    0.11841  |                        nan         |                          nan        |           17.904  |                nan       |                  nan      |
| run_family      | heldout_run_family_1 | mlp                                 |                 0.6     |                      nan       |                       nan       |                    0        |                        nan         |                          nan        |            6.2252 |                nan       |                  nan      |
| run_family      | heldout_run_family_1 | ridge                               |                 0.7     |                      nan       |                       nan       |                    0.052467 |                        nan         |                          nan        |            6.1106 |                nan       |                  nan      |
| run_family      | heldout_run_family_1 | template_residual_boosted_stack_new |                 0.9     |                      nan       |                       nan       |                    0.10392  |                        nan         |                          nan        |            6.1834 |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | 1d_cnn                              |                 0.6     |                      nan       |                       nan       |                    0.13173  |                        nan         |                          nan        |           20.259  |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | deltaE_over_E_likelihood_template   |                 0.67436 |                      nan       |                       nan       |                    0.099818 |                        nan         |                          nan        |           12.616  |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | gradient_boosted_trees              |                 1       |                      nan       |                       nan       |                    0.10299  |                        nan         |                          nan        |            9.9304 |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | joint_sequence_transformer          |                 0.5     |                      nan       |                       nan       |                    0.10295  |                        nan         |                          nan        |           15.666  |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | mlp                                 |                 0.7     |                      nan       |                       nan       |                    0.33965  |                        nan         |                          nan        |           17.482  |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | ridge                               |                 0.7     |                      nan       |                       nan       |                    0.07605  |                        nan         |                          nan        |           10.259  |                nan       |                  nan      |
| run_family      | heldout_run_family_2 | template_residual_boosted_stack_new |                 0.8     |                      nan       |                       nan       |                    0.096224 |                        nan         |                          nan        |            8.9934 |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | 1d_cnn                              |                 0.75    |                      nan       |                       nan       |                    0.073652 |                        nan         |                          nan        |           21.682  |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | deltaE_over_E_likelihood_template   |                 0.7375  |                      nan       |                       nan       |                    0.071166 |                        nan         |                          nan        |            4.6154 |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | gradient_boosted_trees              |                 1       |                      nan       |                       nan       |                    0.11021  |                        nan         |                          nan        |           11.34   |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | joint_sequence_transformer          |                 0.5     |                      nan       |                       nan       |                    0.22338  |                        nan         |                          nan        |           17.628  |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | mlp                                 |                 0.75    |                      nan       |                       nan       |                    0.2255   |                        nan         |                          nan        |           36.852  |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | ridge                               |                 0.875   |                      nan       |                       nan       |                    0.10359  |                        nan         |                          nan        |           11.285  |                nan       |                  nan      |
| run_family      | heldout_run_family_3 | template_residual_boosted_stack_new |                 1       |                      nan       |                       nan       |                    0.070128 |                        nan         |                          nan        |            8.6693 |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | 1d_cnn                              |                 1       |                      nan       |                       nan       |                    0.087044 |                        nan         |                          nan        |           18.679  |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | deltaE_over_E_likelihood_template   |                 0.97674 |                      nan       |                       nan       |                    0.038587 |                        nan         |                          nan        |            9.6238 |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | gradient_boosted_trees              |                 1       |                      nan       |                       nan       |                    0.10022  |                        nan         |                          nan        |            9.5932 |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | joint_sequence_transformer          |                 0.5     |                      nan       |                       nan       |                    0.057682 |                        nan         |                          nan        |           19.574  |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | mlp                                 |                 0.5     |                      nan       |                       nan       |                    0.30744  |                        nan         |                          nan        |            7.5268 |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | ridge                               |                 1       |                      nan       |                       nan       |                    0.040234 |                        nan         |                          nan        |            7.6628 |                nan       |                  nan      |
| run_family      | heldout_run_family_4 | template_residual_boosted_stack_new |                 0.98837 |                      nan       |                       nan       |                    0.098997 |                        nan         |                          nan        |            8.9556 |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | 1d_cnn                              |                 0.48837 |                      nan       |                       nan       |                    0.12018  |                        nan         |                          nan        |           17.454  |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | deltaE_over_E_likelihood_template   |                 0.5     |                      nan       |                       nan       |                    0.033686 |                        nan         |                          nan        |           10.321  |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | gradient_boosted_trees              |                 1       |                      nan       |                       nan       |                    0.074363 |                        nan         |                          nan        |            8.0912 |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | joint_sequence_transformer          |                 0.5     |                      nan       |                       nan       |                    0.17133  |                        nan         |                          nan        |           15.05   |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | mlp                                 |                 0.5     |                      nan       |                       nan       |                    0.28399  |                        nan         |                          nan        |           20.376  |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | ridge                               |                 0.5     |                      nan       |                       nan       |                    0.0686   |                        nan         |                          nan        |           11.007  |                nan       |                  nan      |
| run_family      | heldout_run_family_5 | template_residual_boosted_stack_new |                 0.5     |                      nan       |                       nan       |                    0.076587 |                        nan         |                          nan        |            7.7116 |                nan       |                  nan      |
| saturation_band | high_energy          | 1d_cnn                              |                 0.64748 |                        0.58756 |                         0.82296 |                    0.097915 |                          0.070622  |                            0.13678  |           19.871  |                 15.639   |                   21.125  |
| saturation_band | high_energy          | deltaE_over_E_likelihood_template   |                 0.61239 |                        0.5189  |                         0.70498 |                    0.065143 |                          0.040478  |                            0.10233  |            6.7321 |                  3.6784  |                   10.665  |
| saturation_band | high_energy          | gradient_boosted_trees              |                 0.96875 |                        0.94167 |                         1       |                    0.091439 |                          0.08017   |                            0.10986  |            9.996  |                  7.1607  |                   10.982  |
| saturation_band | high_energy          | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.13075  |                          0.095586  |                            0.22033  |           15.245  |                 14.055   |                   16.568  |
| saturation_band | high_energy          | mlp                                 |                 0.65625 |                        0.61503 |                         0.73048 |                    0.22831  |                          0.1136    |                            0.39071  |           19.119  |                 15.304   |                   27.37   |
| saturation_band | high_energy          | ridge                               |                 0.75    |                        0.70184 |                         0.84545 |                    0.068672 |                          0.052118  |                            0.10146  |            9.8436 |                  7.5797  |                   11.735  |
| saturation_band | high_energy          | template_residual_boosted_stack_new |                 0.86623 |                        0.79636 |                         0.94391 |                    0.091185 |                          0.082199  |                            0.097294 |            9.4225 |                  6.9014  |                   11.07   |
| saturation_band | low_energy           | 1d_cnn                              |                 1       |                        1       |                         1       |                    0.13859  |                          0.043351  |                            0.23     |           15.237  |                 12.463   |                   17.291  |
| saturation_band | low_energy           | deltaE_over_E_likelihood_template   |                 1       |                        1       |                         1       |                    0.073299 |                          0.013038  |                            0.158    |           19.707  |                 10.485   |                   29.665  |
| saturation_band | low_energy           | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.13277  |                          0.087946  |                            0.15029  |           10.888  |                  6.2914  |                   17.61   |
| saturation_band | low_energy           | joint_sequence_transformer          |                 1       |                        1       |                         1       |                    0.16339  |                          0.067039  |                            0.20709  |           26.19   |                 13.02    |                   33.874  |
| saturation_band | low_energy           | mlp                                 |                 1       |                        1       |                         1       |                    0.55905  |                          0         |                            0.72075  |           19.532  |                  5.2143  |                   37.247  |
| saturation_band | low_energy           | ridge                               |                 1       |                        1       |                         1       |                    0.14841  |                          0.14841   |                            0.21825  |            8.5068 |                  8.5068  |                   14.718  |
| saturation_band | low_energy           | template_residual_boosted_stack_new |                 1       |                        1       |                         1       |                    0.12639  |                          0.072602  |                            0.15641  |           10.971  |                  3.8384  |                   17.849  |
| saturation_band | mid_energy           | 1d_cnn                              |                 1       |                        1       |                         1       |                    0.11937  |                          0.093968  |                            0.23699  |           18.827  |                 14.947   |                   21.383  |
| saturation_band | mid_energy           | deltaE_over_E_likelihood_template   |                 0.9863  |                        0.96707 |                         1       |                    0.10502  |                          0.064293  |                            0.11296  |           10.554  |                  8.3347  |                   16.101  |
| saturation_band | mid_energy           | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.11155  |                          0.049868  |                            0.1566   |            9.4698 |                  7.5201  |                   12.615  |
| saturation_band | mid_energy           | joint_sequence_transformer          |                 1       |                        1       |                         1       |                    0.11285  |                          0.078788  |                            0.24445  |           17.335  |                  6.8249  |                   17.811  |
| saturation_band | mid_energy           | mlp                                 |                 1       |                        1       |                         1       |                    0.23746  |                          0.012446  |                            0.46365  |           11.056  |                  7.9355  |                   14.025  |
| saturation_band | mid_energy           | ridge                               |                 1       |                        1       |                         1       |                    0.073925 |                          0.038957  |                            0.090138 |           10.415  |                  8.5649  |                   13.42   |
| saturation_band | mid_energy           | template_residual_boosted_stack_new |                 1       |                        1       |                         1       |                    0.11814  |                          0.066396  |                            0.22303  |            7.4115 |                  7.1358  |                   11.571  |
| shape_family    | broad_tail           | 1d_cnn                              |                 0.64206 |                        0.54708 |                         0.76078 |                    0.21441  |                          0.20246   |                            0.25924  |           15.534  |                 12.873   |                   16.557  |
| shape_family    | broad_tail           | deltaE_over_E_likelihood_template   |                 0.71032 |                        0.48507 |                         0.8203  |                    0.091133 |                          0.062051  |                            0.11797  |           10.939  |                  6.3264  |                   13.791  |
| shape_family    | broad_tail           | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.12823  |                          0.10425   |                            0.14755  |            9.6524 |                  7.7614  |                   13.133  |
| shape_family    | broad_tail           | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.21419  |                          0.17432   |                            0.27927  |           17.084  |                 16.629   |                   20.017  |
| shape_family    | broad_tail           | mlp                                 |                 0.7     |                        0.56667 |                         0.79643 |                    0.39266  |                          0.17762   |                            0.47615  |           19.608  |                 12.69    |                   36.352  |
| shape_family    | broad_tail           | ridge                               |                 0.8     |                        0.71667 |                         1       |                    0.085144 |                          0.074885  |                            0.10918  |           12.16   |                 10.132   |                   14.634  |
| shape_family    | broad_tail           | template_residual_boosted_stack_new |                 0.9     |                        0.76364 |                         0.97    |                    0.10702  |                          0.087372  |                            0.11976  |            9.2441 |                  7.6615  |                   10.816  |
| shape_family    | narrow_high_peak     | 1d_cnn                              |                 1       |                        1       |                         1       |                    0.080085 |                          0.065299  |                            0.099242 |           12.329  |                 10.938   |                   16.927  |
| shape_family    | narrow_high_peak     | deltaE_over_E_likelihood_template   |                 1       |                        1       |                         1       |                    0.034938 |                          0.016023  |                            0.038755 |            3.3026 |                  0.92069 |                   29.132  |
| shape_family    | narrow_high_peak     | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.070823 |                          0.052525  |                            0.10358  |            8.0466 |                  4.0784  |                    9.6482 |
| shape_family    | narrow_high_peak     | joint_sequence_transformer          |                 1       |                        1       |                         1       |                    0.017136 |                          0         |                            0.021081 |            8.3078 |                  4.0043  |                   18.192  |
| shape_family    | narrow_high_peak     | mlp                                 |                 1       |                        1       |                         1       |                  nan        |                        nan         |                          nan        |          nan      |                nan       |                  nan      |
| shape_family    | narrow_high_peak     | ridge                               |                 1       |                        1       |                         1       |                    0.065617 |                          0.021028  |                            0.080128 |            4.5103 |                  2.4793  |                    5.6576 |
| shape_family    | narrow_high_peak     | template_residual_boosted_stack_new |                 0.9863  |                        0.95248 |                         1       |                    0.080406 |                          0.022789  |                            0.10907  |            7.4252 |                  4.6863  |                    8.5714 |
| shape_family    | nominal_shape        | 1d_cnn                              |                 0.66667 |                        0.575   |                         0.72    |                    0.055722 |                          0.051969  |                            0.096825 |           16.005  |                 10.866   |                   19.114  |
| shape_family    | nominal_shape        | deltaE_over_E_likelihood_template   |                 0.49265 |                        0.48283 |                         0.5     |                    0.060226 |                          0.040457  |                            0.080346 |            7.0577 |                  1.8995  |                   10.259  |
| shape_family    | nominal_shape        | gradient_boosted_trees              |                 0.91667 |                        0.84333 |                         1       |                    0.083235 |                          0.07333   |                            0.10463  |            8.9123 |                  6.2063  |                   11.777  |
| shape_family    | nominal_shape        | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.047348 |                          0.035062  |                            0.095338 |           17.76   |                 14.37    |                   19.011  |
| shape_family    | nominal_shape        | mlp                                 |                 0.58333 |                        0.5     |                         0.77    |                    0.19536  |                          0         |                            0.36625  |            2.8499 |                  0.75551 |                    3.58   |
| shape_family    | nominal_shape        | ridge                               |                 0.66667 |                        0.6     |                         0.70571 |                    0.048091 |                          0.034675  |                            0.093339 |            7.5012 |                  4.1696  |                   11.616  |
| shape_family    | nominal_shape        | template_residual_boosted_stack_new |                 0.83333 |                        0.5     |                         1       |                    0.091274 |                          0.053939  |                            0.096483 |            7.9459 |                  5.6901  |                   10.252  |
| stave           | B2                   | 1d_cnn                              |                 0.98611 |                        0.9441  |                         1       |                    0.30648  |                          0         |                            0.58892  |           19.23   |                  9.9428  |                   24.962  |
| stave           | B2                   | deltaE_over_E_likelihood_template   |                 0.91667 |                        0.72673 |                         0.96611 |                    0.034203 |                          0         |                            0.041548 |           21.489  |                 12.334   |                   22.847  |
| stave           | B2                   | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.14993  |                          0.056778  |                            0.40195  |           10.123  |                  7.7206  |                   17.047  |
| stave           | B2                   | joint_sequence_transformer          |                 0.5     |                        0.5     |                         1       |                    0.48017  |                          0.046906  |                            0.60032  |           23.418  |                  8.4637  |                   25.259  |
| stave           | B2                   | mlp                                 |                 1       |                        1       |                         1       |                    0.45267  |                          0         |                            0.47761  |           17.022  |                  7.4162  |                   24.439  |
| stave           | B2                   | ridge                               |                 1       |                        1       |                         1       |                    0.055848 |                          0         |                            0.0823   |           11.727  |                  2.1884  |                   15.446  |
| stave           | B2                   | template_residual_boosted_stack_new |                 1       |                        1       |                         1       |                    0.14393  |                          0.053545  |                            0.40843  |           10.597  |                  8.3609  |                   14.711  |
| stave           | B4                   | 1d_cnn                              |                 1       |                        1       |                         1       |                    0.15935  |                          0.097473  |                            0.27904  |           16.724  |                 14.471   |                   23.107  |
| stave           | B4                   | deltaE_over_E_likelihood_template   |                 1       |                        1       |                         1       |                    0.069026 |                          0         |                            0.088543 |           15.155  |                 10.9     |                   20.117  |
| stave           | B4                   | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.081751 |                          0.058697  |                            0.10134  |            9.9444 |                  7.9946  |                   11.213  |
| stave           | B4                   | joint_sequence_transformer          |                 1       |                        1       |                         1       |                    0.14154  |                          0.12547   |                            0.20946  |           17.25   |                 12.31    |                   18.675  |
| stave           | B4                   | mlp                                 |                 1       |                        1       |                         1       |                    0.33941  |                          0.11284   |                            0.90363  |           10.959  |                  3.2881  |                   31.53   |
| stave           | B4                   | ridge                               |                 1       |                        1       |                         1       |                    0.052179 |                          0.042341  |                            0.072091 |           10.416  |                  8.7353  |                   13.077  |
| stave           | B4                   | template_residual_boosted_stack_new |                 1       |                        1       |                         1       |                    0.10508  |                          0.061889  |                            0.11571  |           10.661  |                  8.8695  |                   11.131  |
| stave           | B6                   | 1d_cnn                              |                 0.5     |                        0.5     |                         1       |                    0.081682 |                          0.060637  |                            0.099832 |           19.016  |                 15.794   |                   22.653  |
| stave           | B6                   | deltaE_over_E_likelihood_template   |                 0.5     |                        0.5     |                         1       |                    0.046733 |                          0.028207  |                            0.10703  |            7.7125 |                  6.1583  |                   14.03   |
| stave           | B6                   | gradient_boosted_trees              |                 1       |                        1       |                         1       |                    0.099844 |                          0.081465  |                            0.1126   |           10.468  |                  5.7611  |                   10.99   |
| stave           | B6                   | joint_sequence_transformer          |                 0.5     |                        0.5     |                         1       |                    0.094055 |                          0.035537  |                            0.14912  |           16.025  |                 11.918   |                   19.649  |
| stave           | B6                   | mlp                                 |                 0.5     |                        0.5     |                         1       |                    0.22681  |                          0.11794   |                            0.3561   |           17.223  |                  9.7315  |                   31.879  |
| stave           | B6                   | ridge                               |                 0.5     |                        0.5     |                         1       |                    0.10442  |                          0.034322  |                            0.13964  |            9.01   |                  6.211   |                   12.276  |
| stave           | B6                   | template_residual_boosted_stack_new |                 0.5     |                        0.5     |                         1       |                    0.068848 |                          0.061196  |                            0.096415 |            8.7421 |                  2.9621  |                   10.127  |
| stave           | B8                   | 1d_cnn                              |                 0.64286 |                        0.6     |                         0.73636 |                    0.070719 |                          0.049672  |                            0.092666 |           19.336  |                 15.379   |                   24.156  |
| stave           | B8                   | deltaE_over_E_likelihood_template   |                 0.64286 |                        0.56721 |                         0.775   |                    0.1002   |                          0.050969  |                            0.10299  |            5.5083 |                  2.8335  |                   10.784  |
| stave           | B8                   | gradient_boosted_trees              |                 0.96429 |                        0.92308 |                         1       |                    0.092513 |                          0.062277  |                            0.12263  |            6.6851 |                  5.7826  |                    8.8279 |
| stave           | B8                   | joint_sequence_transformer          |                 0.5     |                        0.5     |                         0.5     |                    0.085822 |                          0.065765  |                            0.10089  |           15.077  |                  9.7867  |                   18.387  |
| stave           | B8                   | mlp                                 |                 0.64286 |                        0.58371 |                         0.71875 |                    0.11856  |                          0         |                            0.14506  |            5.8492 |                  2.6094  |                    7.9085 |
| stave           | B8                   | ridge                               |                 0.75    |                        0.64    |                         0.81429 |                    0.067027 |                          0.059124  |                            0.096033 |            6.2103 |                  4.9131  |                   12.98   |
| stave           | B8                   | template_residual_boosted_stack_new |                 0.88324 |                        0.78909 |                         0.96644 |                    0.086051 |                          0.049276  |                            0.10699  |            6.5345 |                  5.4836  |                    8.6716 |

## S29d systematics and caveats

The pedestal axis is derived from held-out pulse area-over-peak quantiles after
raw pedestal subtraction; it therefore tests transfer across waveform pedestal
and shape regimes, not a dedicated electronics pedestal scan.  The saturation
axis is a controlled-injection energy-proxy band.  Pile-up load is the injected
two-pulse separation, with high-overlap events forming the hardest recovery
cell.  Pulse-shape families are narrow, nominal, and broad-tail quantiles of the
same held-out waveform-shape observable.  The run-family split uses complete
held-out source runs, and all quoted intervals in the transfer table are
percentile run-block bootstrap intervals.

The PID endpoint remains a deterministic raw-waveform high-dE/dx-depth proxy.
This makes the benchmark appropriate for architecture ranking and calibration
stress testing, but not a final external particle-ID measurement.  The strong
traditional method is retained as an interpretable calibration baseline even
where neural or hybrid methods win the composite objective.

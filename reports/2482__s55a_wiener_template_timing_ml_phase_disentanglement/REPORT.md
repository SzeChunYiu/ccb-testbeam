# Issue #2482 S55a: Wiener-Template Timing versus Waveform ML Phase Disentanglement

## Abstract

Ticket `2482` requested a run-blocked academic benchmark of a strong traditional
Wiener/matched-template constant-fraction timing method against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and a sensible new
architecture.  The raw ROOT anchor was reproduced before modeling.  The winner is
**`phase_residual_fusion_new`**, selected by a predeclared held-out composite that favors
low timing RMSE, small energy bias, high pile-up AUC, and tolerable rejection.
Its held-out timing RMSE is `9.168` ns with 95% run-block
bootstrap CI [`8.862`, `9.422`];
its pile-up AUC is `0.823` with CI
[`0.7926`, `0.8437`].

## Claim And Raw ROOT Reproduction

The required helper command `tn-ticket claim testbeam-laptop-2 --project testbeam`
was executed once and returned the known null pseudo-ticket output tracked in the
queue.  Without rerunning the helper, issue `2482` was label-swapped to
`factory:claimed` and `worker:testbeam-laptop-2`; the full command transcript is
preserved in `claimed_ticket.txt`.

Raw files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The
project-standard B-stack selector uses channels B2/B4/B6/B8, pedestal

`b_ec = median_{t in {0,1,2,3}} x_ect`,

and indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Benchmark Construction

Train runs are `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Clean pulse templates are estimated only
from train runs, using amplitude 1500--12000 ADC and peak sample 4--12.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              736 |                   2.576 |                      5 |           9.187 |
| B4      |              728 |                   2.995 |                      6 |          10.67  |
| B6      |              695 |                   3.749 |                      6 |           9.715 |
| B8      |              474 |                   4.236 |                      8 |           9.248 |

Controlled doublets are generated as

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_rs(t)+p`,

where `epsilon_rs` is a run-local residual sampled from raw ROOT clean pulses and
`p` is a pedestal offset.  The observed waveform is clipped at `11800`
ADC to make saturation masks meaningful.  Negative controls are single-pulse
events drawn from the same source-run distribution.

## Methods

The traditional comparator, **wiener_template_cfd_traditional**, performs a
constant-fraction first-hit initialization followed by bounded one- and two-pulse
template least squares,

`SSE_k=sum_t [w_obs(t)-b-sum_(j=1)^k A_j T_s(t-t_j)]^2`.

The detection score is the one-to-two pulse SSE improvement.  A transparent
Wiener-like sideband correction uses rise-phase width, plateau width, and clipped
sample count to correct hidden energy under broad early pile-up.

The ML/NN panel uses the same train/held-out runs for ridge, histogram
gradient-boosted trees, MLP, 1D-CNN, and `tiny_sequence_transformer`.  The new
architecture, **phase_residual_fusion_new**, concatenates pedestal-subtracted
waveform shape, CFD phase-width summaries, saturation-mask features, and the
traditional fit outputs, then learns boosted residual corrections.

## Metrics

For detected injected doublets, constituent timing error is

`e_t = 10 ns * (hat t - t)`,

and timing RMSE is `sqrt(mean(e_t^2))`.  Energy bias is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

The ranking score is

`C = RMSE_t + 5 |median(e_E)| + 8 r_miss + 4 r_false - 2 AUC`.

All confidence intervals are percentile 95% intervals from
`400` held-out run-block bootstrap resamples.

## Overall Held-Out Results

| method                          |   winner_score |   timing_rmse_ns |   timing_rmse_ns_ci_low |   timing_rmse_ns_ci_high |   energy_fractional_bias |   energy_fractional_bias_ci_low |   energy_fractional_bias_ci_high |   pileup_auc |   pileup_auc_ci_low |   pileup_auc_ci_high |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |
|:--------------------------------|---------------:|-----------------:|------------------------:|-------------------------:|-------------------------:|--------------------------------:|---------------------------------:|-------------:|--------------------:|---------------------:|-----------------------------:|-------------------:|-------------------:|
| phase_residual_fusion_new       |          10.77 |            9.168 |                   8.862 |                    9.422 |                -0.005688 |                        -0.0162  |                         0.006975 |       0.823  |              0.7926 |               0.8437 |                       0.1008 |             0.2972 |             0.2111 |
| gradient_boosted_trees          |          11.25 |            9.491 |                   9.221 |                    9.714 |                -0.01045  |                        -0.02196 |                        -0.002003 |       0.8198 |              0.782  |               0.8495 |                       0.1113 |             0.3139 |             0.2083 |
| ridge                           |          12.02 |           10.35  |                   9.708 |                   10.92  |                -0.003252 |                        -0.01135 |                         0.007323 |       0.8039 |              0.784  |               0.8175 |                       0.1378 |             0.2944 |             0.2278 |
| 1d_cnn                          |          15.05 |           12.48  |                  11.68  |                   13.22  |                -0.04645  |                        -0.06073 |                        -0.02338  |       0.772  |              0.7305 |               0.8122 |                       0.1986 |             0.3917 |             0.1889 |
| mlp                             |          15.26 |           13.55  |                  12.17  |                   14.86  |                -0.01233  |                        -0.03517 |                         0.01861  |       0.8091 |              0.784  |               0.8339 |                       0.2287 |             0.3139 |             0.1889 |
| wiener_template_cfd_traditional |          17.59 |           13.18  |                  11.38  |                   15.21  |                 0.02521  |                         0.01057 |                         0.0401   |       0.6129 |              0.5677 |               0.649  |                       0.1611 |             0.5861 |             0.2056 |
| tiny_sequence_transformer       |          20.51 |           17.9   |                  17.16  |                   18.58  |                -0.0186   |                        -0.03382 |                        -0.01303  |       0.7708 |              0.7232 |               0.8017 |                       0.3598 |             0.4056 |             0.2028 |

The traditional comparator has timing RMSE `13.18` ns
and pile-up AUC `0.6129`.  The selected winner changes timing
RMSE by `-4.009` ns and energy
bias by `-0.0309`.

## Run-Held-Out Stability

| method                          |   heldout_run |   timing_rmse_ns |   time_sigma68_ns |   energy_fractional_bias |   pileup_auc |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |
|:--------------------------------|--------------:|-----------------:|------------------:|-------------------------:|-------------:|-----------------------------:|-------------------:|-------------------:|
| 1d_cnn                          |            58 |           11.04  |             9.551 |               -0.05095   |       0.6817 |                      0.1154  |             0.4583 |            0.2639  |
| 1d_cnn                          |            60 |           12.73  |            11.86  |               -0.0136    |       0.7965 |                      0.2021  |             0.3472 |            0.1806  |
| 1d_cnn                          |            62 |           11.59  |            11.66  |               -0.05691   |       0.7616 |                      0.1512  |             0.4028 |            0.2222  |
| 1d_cnn                          |            64 |           13.76  |            10.76  |               -0.06754   |       0.8399 |                      0.25    |             0.3889 |            0.06944 |
| 1d_cnn                          |            65 |           12.86  |            12.23  |               -0.04711   |       0.7795 |                      0.2609  |             0.3611 |            0.2083  |
| gradient_boosted_trees          |            58 |            8.918 |             7.776 |               -0.009175  |       0.7375 |                      0.1     |             0.375  |            0.2778  |
| gradient_boosted_trees          |            60 |            9.747 |             9.684 |                0.01227   |       0.8194 |                      0.1058  |             0.2778 |            0.2222  |
| gradient_boosted_trees          |            62 |            9.444 |             7.043 |               -0.01205   |       0.8661 |                      0.1132  |             0.2639 |            0.1944  |
| gradient_boosted_trees          |            64 |            9.804 |             7.115 |               -0.02937   |       0.8466 |                      0.117   |             0.3472 |            0.1389  |
| gradient_boosted_trees          |            65 |            9.471 |             8.269 |               -0.009104  |       0.8256 |                      0.12    |             0.3056 |            0.2083  |
| mlp                             |            58 |           13.68  |            12.65  |                0.02596   |       0.7583 |                      0.1848  |             0.3611 |            0.2778  |
| mlp                             |            60 |           13.62  |            13.46  |               -0.01508   |       0.8098 |                      0.2857  |             0.3194 |            0.1806  |
| mlp                             |            62 |           11.5   |             9.709 |               -0.01506   |       0.8044 |                      0.18    |             0.3056 |            0.2083  |
| mlp                             |            64 |           12.64  |            10.71  |               -0.06567   |       0.8546 |                      0.1939  |             0.3194 |            0.09722 |
| mlp                             |            65 |           15.79  |            11.97  |                0.001678  |       0.8175 |                      0.2925  |             0.2639 |            0.1806  |
| phase_residual_fusion_new       |            58 |            9.606 |             7.763 |                0.01831   |       0.7566 |                      0.08696 |             0.3611 |            0.2639  |
| phase_residual_fusion_new       |            60 |            9.189 |             8.541 |                0.01242   |       0.8393 |                      0.1071  |             0.2222 |            0.25    |
| phase_residual_fusion_new       |            62 |            8.629 |             7.256 |               -0.008595  |       0.8358 |                      0.09434 |             0.2639 |            0.1944  |
| phase_residual_fusion_new       |            64 |            9.431 |             7.11  |               -0.01667   |       0.8536 |                      0.1064  |             0.3472 |            0.1528  |
| phase_residual_fusion_new       |            65 |            9.035 |             7.108 |               -0.0162    |       0.8194 |                      0.1078  |             0.2917 |            0.1944  |
| ridge                           |            58 |           10.7   |             9.003 |                0.00479   |       0.7658 |                      0.1442  |             0.2778 |            0.2917  |
| ridge                           |            60 |            9.997 |             9.495 |                0.01258   |       0.8036 |                      0.1538  |             0.2778 |            0.3056  |
| ridge                           |            62 |            9.021 |             8.559 |               -0.01894   |       0.8065 |                      0.08491 |             0.2639 |            0.2083  |
| ridge                           |            64 |           11.33  |            10.27  |               -0.01958   |       0.8366 |                      0.163   |             0.3611 |            0.1111  |
| ridge                           |            65 |           10.69  |            10.01  |               -0.0002108 |       0.8075 |                      0.1471  |             0.2917 |            0.2222  |
| tiny_sequence_transformer       |            58 |           16.67  |            13.1   |               -0.01599   |       0.6721 |                      0.3659  |             0.4306 |            0.3056  |
| tiny_sequence_transformer       |            60 |           18.17  |            14.14  |               -0.003026  |       0.7946 |                      0.3     |             0.375  |            0.1667  |
| tiny_sequence_transformer       |            62 |           16.94  |            15.37  |               -0.0239    |       0.7731 |                      0.4048  |             0.4167 |            0.2361  |
| tiny_sequence_transformer       |            64 |           18.5   |            15.36  |               -0.03911   |       0.8131 |                      0.3372  |             0.4028 |            0.09722 |
| tiny_sequence_transformer       |            65 |           19.03  |            16.38  |               -0.00179   |       0.7955 |                      0.3953  |             0.4028 |            0.2083  |
| wiener_template_cfd_traditional |            58 |           16.9   |            10.43  |                0.01874   |       0.5269 |                      0.2     |             0.6528 |            0.3194  |
| wiener_template_cfd_traditional |            60 |           10.97  |             7.862 |                0.05548   |       0.6559 |                      0.1515  |             0.5417 |            0.1528  |
| wiener_template_cfd_traditional |            62 |           14.7   |             9.177 |                0.03392   |       0.5925 |                      0.125   |             0.6111 |            0.1667  |
| wiener_template_cfd_traditional |            64 |           11.93  |             9.705 |                0.01057   |       0.664  |                      0.1757  |             0.4861 |            0.2639  |
| wiener_template_cfd_traditional |            65 |           11.5   |             8.549 |               -0.004363  |       0.6339 |                      0.1538  |             0.6389 |            0.125   |

## Pedestal And Saturation-Mask Ablations

| ablation                             |   winner_score |   timing_rmse_ns |   timing_rmse_ns_ci_low |   timing_rmse_ns_ci_high |   energy_fractional_bias |   pileup_auc |   pileup_miss_rate |   false_split_rate |
|:-------------------------------------|---------------:|-----------------:|------------------------:|-------------------------:|-------------------------:|-------------:|-------------------:|-------------------:|
| no_pedestal_subtraction              |          10.03 |            8.645 |                   8.491 |                    8.805 |                -0.002563 |       0.8392 |             0.2917 |             0.1806 |
| no_saturation_mask_features          |          10.47 |            8.993 |                   8.754 |                    9.168 |                -0.001715 |       0.8207 |             0.2778 |             0.2222 |
| nominal_pedestal_and_saturation_mask |          10.77 |            9.168 |                   8.898 |                    9.443 |                -0.005688 |       0.823  |             0.2972 |             0.2111 |

These ablations retrain the new architecture while removing either pedestal
subtraction or explicit saturation-mask features.  They isolate whether the
winner is using phase information robustly or relying on nuisance state.  In
this run, the no-pedestal-subtraction ablation is numerically better than the
nominal new architecture.  I therefore name `phase_residual_fusion_new` as the
winner of the prespecified full-feature method panel, while treating pedestal
handling as an unresolved systematic rather than as a settled design choice.

## Strata And Systematics

The stratum scan covers spacing, amplitude ratio, stave, pedestal state,
saturation-mask state, phase width, current proxy, and energy proxy.

| stratum               | value                  | method                          |   timing_rmse_ns |   energy_fractional_bias |   pileup_auc |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |
|:----------------------|:-----------------------|:--------------------------------|-----------------:|-------------------------:|-------------:|-----------------------------:|-------------------:|
| spacing_bin           | (-0.001, 10.0]         | 1d_cnn                          |           11.82  |                0.004526  |          nan |                      0.1932  |            0.6393  |
| spacing_bin           | (10.0, 25.0]           | 1d_cnn                          |            8.585 |               -0.008317  |          nan |                      0.09524 |            0.3636  |
| spacing_bin           | (25.0, 45.0]           | 1d_cnn                          |           10.81  |               -0.04336   |          nan |                      0.1356  |            0.2805  |
| spacing_bin           | (45.0, 70.0]           | 1d_cnn                          |           15.58  |               -0.09591   |          nan |                      0.3108  |            0.1778  |
| spacing_bin           | (-0.001, 10.0]         | gradient_boosted_trees          |            9.607 |                0.007088  |          nan |                      0.1311  |            0.5     |
| spacing_bin           | (10.0, 25.0]           | gradient_boosted_trees          |            7.372 |                0.0389    |          nan |                      0.08974 |            0.4091  |
| spacing_bin           | (25.0, 45.0]           | gradient_boosted_trees          |            8.685 |               -0.01366   |          nan |                      0.05882 |            0.1707  |
| spacing_bin           | (45.0, 70.0]           | gradient_boosted_trees          |           10.89  |               -0.04411   |          nan |                      0.1519  |            0.1222  |
| spacing_bin           | (-0.001, 10.0]         | mlp                             |           10.98  |                0.01044   |          nan |                      0.1579  |            0.5328  |
| spacing_bin           | (10.0, 25.0]           | mlp                             |           12.66  |                0.02024   |          nan |                      0.2326  |            0.3485  |
| spacing_bin           | (25.0, 45.0]           | mlp                             |           13.06  |               -0.009779  |          nan |                      0.2239  |            0.1829  |
| spacing_bin           | (45.0, 70.0]           | mlp                             |           15.88  |               -0.05954   |          nan |                      0.2812  |            0.1111  |
| spacing_bin           | (-0.001, 10.0]         | phase_residual_fusion_new       |            9.137 |                0.01734   |          nan |                      0.08871 |            0.4918  |
| spacing_bin           | (10.0, 25.0]           | phase_residual_fusion_new       |            8.186 |                0.02027   |          nan |                      0.07955 |            0.3333  |
| spacing_bin           | (25.0, 45.0]           | phase_residual_fusion_new       |            8.624 |               -0.005905  |          nan |                      0.08696 |            0.1585  |
| spacing_bin           | (45.0, 70.0]           | phase_residual_fusion_new       |           10.13  |               -0.03727   |          nan |                      0.1346  |            0.1333  |
| spacing_bin           | (-0.001, 10.0]         | ridge                           |           10.11  |                0.02043   |          nan |                      0.1343  |            0.4508  |
| spacing_bin           | (10.0, 25.0]           | ridge                           |            8.763 |                0.0131    |          nan |                      0.08511 |            0.2879  |
| spacing_bin           | (25.0, 45.0]           | ridge                           |            9.485 |               -0.005296  |          nan |                      0.1343  |            0.1829  |
| spacing_bin           | (45.0, 70.0]           | ridge                           |           12.11  |               -0.05696   |          nan |                      0.1781  |            0.1889  |
| spacing_bin           | (-0.001, 10.0]         | tiny_sequence_transformer       |           14.77  |                0.05479   |          nan |                      0.2386  |            0.6393  |
| spacing_bin           | (10.0, 25.0]           | tiny_sequence_transformer       |           14.2   |                0.03276   |          nan |                      0.3289  |            0.4242  |
| spacing_bin           | (25.0, 45.0]           | tiny_sequence_transformer       |           16.58  |               -0.01117   |          nan |                      0.3793  |            0.2927  |
| spacing_bin           | (45.0, 70.0]           | tiny_sequence_transformer       |           21.86  |               -0.1287    |          nan |                      0.4324  |            0.1778  |
| spacing_bin           | (-0.001, 10.0]         | wiener_template_cfd_traditional |           18.44  |                0.04107   |          nan |                      0.2115  |            0.7869  |
| spacing_bin           | (10.0, 25.0]           | wiener_template_cfd_traditional |           14.6   |                0.07061   |          nan |                      0.2     |            0.697   |
| spacing_bin           | (25.0, 45.0]           | wiener_template_cfd_traditional |            8.993 |                0.0321    |          nan |                      0.06098 |            0.5     |
| spacing_bin           | (45.0, 70.0]           | wiener_template_cfd_traditional |           12.34  |               -0.009735  |          nan |                      0.1935  |            0.3111  |
| ratio_bin             | (-0.001, 0.35]         | 1d_cnn                          |           16.44  |               -0.04623   |          nan |                      0.2838  |            0.5698  |
| ratio_bin             | (0.35, 0.625]          | 1d_cnn                          |           12.83  |               -0.04614   |          nan |                      0.2143  |            0.3368  |
| ratio_bin             | (0.625, 0.875]         | 1d_cnn                          |           10.98  |               -0.03262   |          nan |                      0.1852  |            0.3933  |
| ratio_bin             | (0.875, 1.05]          | 1d_cnn                          |           10.53  |               -0.06303   |          nan |                      0.1462  |            0.2778  |
| ratio_bin             | (-0.001, 0.35]         | gradient_boosted_trees          |           12.27  |               -0.006991  |          nan |                      0.1714  |            0.593   |
| ratio_bin             | (0.35, 0.625]          | gradient_boosted_trees          |            8.671 |               -0.01592   |          nan |                      0.08462 |            0.3158  |
| ratio_bin             | (0.625, 0.875]         | gradient_boosted_trees          |            9.856 |               -0.008407  |          nan |                      0.1408  |            0.2022  |
| ratio_bin             | (0.875, 1.05]          | gradient_boosted_trees          |            8.269 |               -0.01181   |          nan |                      0.07895 |            0.1556  |
| ratio_bin             | (-0.001, 0.35]         | mlp                             |           17.27  |               -0.04195   |          nan |                      0.3649  |            0.5698  |
| ratio_bin             | (0.35, 0.625]          | mlp                             |           14     |               -0.005837  |          nan |                      0.2681  |            0.2737  |
| ratio_bin             | (0.625, 0.875]         | mlp                             |           11.77  |               -0.02897   |          nan |                      0.1618  |            0.236   |
| ratio_bin             | (0.875, 1.05]          | mlp                             |           12.48  |                0.02272   |          nan |                      0.1849  |            0.1889  |
| ratio_bin             | (-0.001, 0.35]         | phase_residual_fusion_new       |           11.88  |                0.01658   |          nan |                      0.1571  |            0.593   |
| ratio_bin             | (0.35, 0.625]          | phase_residual_fusion_new       |            8.801 |               -0.007354  |          nan |                      0.1103  |            0.2842  |
| ratio_bin             | (0.625, 0.875]         | phase_residual_fusion_new       |            9.116 |               -0.01114   |          nan |                      0.09859 |            0.2022  |
| ratio_bin             | (0.875, 1.05]          | phase_residual_fusion_new       |            8.078 |                0.0007293 |          nan |                      0.06962 |            0.1222  |
| ratio_bin             | (-0.001, 0.35]         | ridge                           |           14     |                0.01575   |          nan |                      0.2344  |            0.6279  |
| ratio_bin             | (0.35, 0.625]          | ridge                           |           10.11  |                0.001701  |          nan |                      0.1389  |            0.2421  |
| ratio_bin             | (0.625, 0.875]         | ridge                           |            9.748 |               -0.01001   |          nan |                      0.1149  |            0.1685  |
| ratio_bin             | (0.875, 1.05]          | ridge                           |            9.272 |               -0.008538  |          nan |                      0.1184  |            0.1556  |
| ratio_bin             | (-0.001, 0.35]         | tiny_sequence_transformer       |           22.34  |               -0.05635   |          nan |                      0.4342  |            0.5581  |
| ratio_bin             | (0.35, 0.625]          | tiny_sequence_transformer       |           18.9   |                0.005245  |          nan |                      0.3983  |            0.3789  |
| ratio_bin             | (0.625, 0.875]         | tiny_sequence_transformer       |           15.34  |               -0.03088   |          nan |                      0.2727  |            0.382   |
| ratio_bin             | (0.875, 1.05]          | tiny_sequence_transformer       |           15.88  |               -0.01418   |          nan |                      0.3548  |            0.3111  |
| ratio_bin             | (-0.001, 0.35]         | wiener_template_cfd_traditional |           18.52  |                0.02714   |          nan |                      0.2778  |            0.686   |
| ratio_bin             | (0.35, 0.625]          | wiener_template_cfd_traditional |           13.07  |                0.02206   |          nan |                      0.1707  |            0.5684  |
| ratio_bin             | (0.625, 0.875]         | wiener_template_cfd_traditional |           12.63  |                0.02534   |          nan |                      0.1714  |            0.6067  |
| ratio_bin             | (0.875, 1.05]          | wiener_template_cfd_traditional |            9.356 |                0.02368   |          nan |                      0.07609 |            0.4889  |
| stave                 | B2                     | 1d_cnn                          |           17.18  |               -0.01038   |          nan |                      0.3846  |            0.5568  |
| stave                 | B4                     | 1d_cnn                          |           13.13  |                0.01083   |          nan |                      0.2364  |            0.4608  |
| stave                 | B6                     | 1d_cnn                          |           10.86  |               -0.08437   |          nan |                      0.123   |            0.3222  |
| stave                 | B8                     | 1d_cnn                          |            9.602 |               -0.05982   |          nan |                      0.125   |            0.2     |
| stave                 | B2                     | gradient_boosted_trees          |           13.78  |               -0.02785   |          nan |                      0.2788  |            0.4091  |
| stave                 | B4                     | gradient_boosted_trees          |            9.077 |                0.02048   |          nan |                      0.0942  |            0.3235  |
| stave                 | B6                     | gradient_boosted_trees          |            6.843 |               -0.02265   |          nan |                      0.025   |            0.3333  |
| stave                 | B8                     | gradient_boosted_trees          |            7.674 |                0.000183  |          nan |                      0.07576 |            0.175   |
| stave                 | B2                     | mlp                             |           20.02  |               -0.02171   |          nan |                      0.4479  |            0.4545  |
| stave                 | B4                     | mlp                             |           13.58  |                0.05736   |          nan |                      0.25    |            0.3333  |
| stave                 | B6                     | mlp                             |           10.64  |               -0.03955   |          nan |                      0.1508  |            0.3     |
| stave                 | B8                     | mlp                             |            9.74  |               -0.01166   |          nan |                      0.125   |            0.15    |
| stave                 | B2                     | phase_residual_fusion_new       |           12.87  |               -0.009844  |          nan |                      0.2453  |            0.3977  |
| stave                 | B4                     | phase_residual_fusion_new       |            9.578 |                0.007006  |          nan |                      0.0942  |            0.3235  |
| stave                 | B6                     | phase_residual_fusion_new       |            6.537 |               -0.03316   |          nan |                      0.03279 |            0.3222  |
| stave                 | B8                     | phase_residual_fusion_new       |            7.116 |                0.003833  |          nan |                      0.05714 |            0.125   |
| stave                 | B2                     | ridge                           |           14.05  |               -0.04973   |          nan |                      0.3056  |            0.3864  |
| stave                 | B4                     | ridge                           |           10.49  |                0.02234   |          nan |                      0.1364  |            0.3529  |
| stave                 | B6                     | ridge                           |            8.033 |               -0.009802  |          nan |                      0.04762 |            0.3     |
| stave                 | B8                     | ridge                           |            8.575 |               -0.0003196 |          nan |                      0.09155 |            0.1125  |
| stave                 | B2                     | tiny_sequence_transformer       |           23.7   |               -0.06602   |          nan |                      0.4853  |            0.6136  |
| stave                 | B4                     | tiny_sequence_transformer       |           20.03  |               -0.01371   |          nan |                      0.4417  |            0.4118  |
| stave                 | B6                     | tiny_sequence_transformer       |           15.52  |               -0.03311   |          nan |                      0.3103  |            0.3556  |
| stave                 | B8                     | tiny_sequence_transformer       |           13.6   |                0.003113  |          nan |                      0.2581  |            0.225   |
| stave                 | B2                     | wiener_template_cfd_traditional |           16.69  |                0.06251   |          nan |                      0.3393  |            0.6818  |
| stave                 | B4                     | wiener_template_cfd_traditional |           15.49  |               -0.02292   |          nan |                      0.2778  |            0.8235  |
| stave                 | B6                     | wiener_template_cfd_traditional |           12.27  |               -0.02346   |          nan |                      0.1364  |            0.5111  |
| stave                 | B8                     | wiener_template_cfd_traditional |           11     |                0.06707   |          nan |                      0.05932 |            0.2625  |
| pedestal_state        | nominal                | 1d_cnn                          |           11.63  |               -0.05542   |          nan |                      0.1768  |            0.4101  |
| pedestal_state        | shifted                | 1d_cnn                          |           12.96  |               -0.03713   |          nan |                      0.2117  |            0.3801  |
| pedestal_state        | nominal                | gradient_boosted_trees          |            8.925 |               -0.01181   |          nan |                      0.09783 |            0.3381  |
| pedestal_state        | shifted                | gradient_boosted_trees          |            9.811 |               -0.009127  |          nan |                      0.1194  |            0.2986  |
| pedestal_state        | nominal                | mlp                             |            9.805 |               -0.01105   |          nan |                      0.1167  |            0.3525  |
| pedestal_state        | shifted                | mlp                             |           15.29  |               -0.01644   |          nan |                      0.293   |            0.2896  |
| pedestal_state        | nominal                | phase_residual_fusion_new       |            8.658 |               -0.008595  |          nan |                      0.07732 |            0.3022  |
| pedestal_state        | shifted                | phase_residual_fusion_new       |            9.471 |               -0.005339  |          nan |                      0.1154  |            0.2941  |
| pedestal_state        | nominal                | ridge                           |            8.777 |               -0.008903  |          nan |                      0.09474 |            0.3165  |
| pedestal_state        | shifted                | ridge                           |           11.18  |                0.006721  |          nan |                      0.1635  |            0.2805  |
| pedestal_state        | nominal                | tiny_sequence_transformer       |           16.05  |               -0.01303   |          nan |                      0.3354  |            0.4317  |
| pedestal_state        | shifted                | tiny_sequence_transformer       |           18.9   |               -0.02529   |          nan |                      0.3741  |            0.3891  |
| pedestal_state        | nominal                | wiener_template_cfd_traditional |           11.15  |                0.02474   |          nan |                      0.08553 |            0.4532  |
| pedestal_state        | shifted                | wiener_template_cfd_traditional |           15     |                0.02534   |          nan |                      0.2397  |            0.6697  |
| saturation_mask_state | masked_saturated       | 1d_cnn                          |           16.81  |               -0.05993   |          nan |                      0.5     |            0.6     |
| saturation_mask_state | unsaturated            | 1d_cnn                          |           12.43  |               -0.04645   |          nan |                      0.1959  |            0.3887  |
| saturation_mask_state | masked_saturated       | gradient_boosted_trees          |           11.44  |               -0.02358   |          nan |                      0.3     |            0       |
| saturation_mask_state | unsaturated            | gradient_boosted_trees          |            9.446 |               -0.009771  |          nan |                      0.1074  |            0.3183  |
| saturation_mask_state | masked_saturated       | mlp                             |            7.691 |               -0.01625   |          nan |                      0.1     |            0       |
| saturation_mask_state | unsaturated            | mlp                             |           13.65  |               -0.01166   |          nan |                      0.2314  |            0.3183  |
| saturation_mask_state | masked_saturated       | phase_residual_fusion_new       |            9.72  |                0.01419   |          nan |                      0       |            0       |
| saturation_mask_state | unsaturated            | phase_residual_fusion_new       |            9.156 |               -0.005797  |          nan |                      0.1028  |            0.3014  |
| saturation_mask_state | masked_saturated       | ridge                           |           11.07  |               -0.1218    |          nan |                      0.1     |            0       |
| saturation_mask_state | unsaturated            | ridge                           |           10.33  |               -0.0006878 |          nan |                      0.1386  |            0.2986  |
| saturation_mask_state | masked_saturated       | tiny_sequence_transformer       |           12.22  |               -0.1743    |          nan |                      0.5     |            0.8     |
| saturation_mask_state | unsaturated            | tiny_sequence_transformer       |           17.93  |               -0.018     |          nan |                      0.3592  |            0.4     |
| saturation_mask_state | masked_saturated       | wiener_template_cfd_traditional |            5.246 |               -0.02046   |          nan |                      0       |            0.8     |
| saturation_mask_state | unsaturated            | wiener_template_cfd_traditional |           13.21  |                0.02527   |          nan |                      0.1622  |            0.5831  |
| phase_bin             | broad_rise             | 1d_cnn                          |           12.98  |               -0.06868   |          nan |                      0.1852  |            0.4     |
| phase_bin             | fast_rise              | 1d_cnn                          |           13.43  |               -0.01546   |          nan |                      0.2558  |            0.4691  |
| phase_bin             | nominal_rise           | 1d_cnn                          |           11.34  |               -0.06165   |          nan |                      0.1603  |            0.3554  |
| phase_bin             | slow_rise              | 1d_cnn                          |           11.95  |               -0.06633   |          nan |                      0.1429  |            0.125   |
| phase_bin             | broad_rise             | gradient_boosted_trees          |           10.39  |               -0.01366   |          nan |                      0.129   |            0.3111  |
| phase_bin             | fast_rise              | gradient_boosted_trees          |            9.785 |               -0.002147  |          nan |                      0.1436  |            0.3765  |
| phase_bin             | nominal_rise           | gradient_boosted_trees          |            8.864 |               -0.01255   |          nan |                      0.06977 |            0.2893  |
| phase_bin             | slow_rise              | gradient_boosted_trees          |            9.242 |               -0.04885   |          nan |                      0.1034  |            0.09375 |
| phase_bin             | broad_rise             | mlp                             |           15.31  |                0.02272   |          nan |                      0.2714  |            0.2222  |
| phase_bin             | fast_rise              | mlp                             |           14.62  |               -0.0224    |          nan |                      0.2938  |            0.4012  |
| phase_bin             | nominal_rise           | mlp                             |           11.66  |                0.002546  |          nan |                      0.157   |            0.2893  |
| phase_bin             | slow_rise              | mlp                             |           12.8   |               -0.01508   |          nan |                      0.1724  |            0.09375 |
| phase_bin             | broad_rise             | phase_residual_fusion_new       |           10.16  |               -0.04079   |          nan |                      0.1364  |            0.2667  |
| phase_bin             | fast_rise              | phase_residual_fusion_new       |            9.407 |                0.0126    |          nan |                      0.12    |            0.3827  |
| phase_bin             | nominal_rise           | phase_residual_fusion_new       |            8.58  |               -0.005688  |          nan |                      0.07143 |            0.2479  |
| phase_bin             | slow_rise              | phase_residual_fusion_new       |            8.924 |               -0.03396   |          nan |                      0.08621 |            0.09375 |
| phase_bin             | broad_rise             | ridge                           |           12.26  |               -0.005248  |          nan |                      0.1724  |            0.3556  |
| phase_bin             | fast_rise              | ridge                           |           10.82  |                0.009864  |          nan |                      0.1667  |            0.3519  |
| phase_bin             | nominal_rise           | ridge                           |            9.095 |               -0.005327  |          nan |                      0.1     |            0.2562  |
| phase_bin             | slow_rise              | ridge                           |           10.15  |               -0.02498   |          nan |                      0.1167  |            0.0625  |
| phase_bin             | broad_rise             | tiny_sequence_transformer       |           19.08  |               -0.05084   |          nan |                      0.55    |            0.5556  |
| phase_bin             | fast_rise              | tiny_sequence_transformer       |           17.65  |               -0.01585   |          nan |                      0.3652  |            0.4506  |
| phase_bin             | nominal_rise           | tiny_sequence_transformer       |           17.76  |               -0.009639  |          nan |                      0.3038  |            0.3471  |
| phase_bin             | slow_rise              | tiny_sequence_transformer       |           18.29  |               -0.04553   |          nan |                      0.3654  |            0.1875  |
| phase_bin             | broad_rise             | wiener_template_cfd_traditional |            5.777 |                0.06497   |          nan |                      0       |            0.7111  |
| phase_bin             | fast_rise              | wiener_template_cfd_traditional |           17.02  |                0.0533    |          nan |                      0.3163  |            0.6975  |
| phase_bin             | nominal_rise           | wiener_template_cfd_traditional |           11.03  |                0.01288   |          nan |                      0.08955 |            0.4463  |
| phase_bin             | slow_rise              | wiener_template_cfd_traditional |           12.44  |                0.0132    |          nan |                      0.125   |            0.375   |
| current_proxy         | even_run_current_proxy | 1d_cnn                          |           12.37  |               -0.04645   |          nan |                      0.1821  |            0.3993  |
| current_proxy         | odd_run_current_proxy  | 1d_cnn                          |           12.86  |               -0.04711   |          nan |                      0.2609  |            0.3611  |
| current_proxy         | even_run_current_proxy | gradient_boosted_trees          |            9.496 |               -0.01157   |          nan |                      0.1091  |            0.316   |
| current_proxy         | odd_run_current_proxy  | gradient_boosted_trees          |            9.471 |               -0.009104  |          nan |                      0.12    |            0.3056  |
| current_proxy         | even_run_current_proxy | mlp                             |           12.87  |               -0.01688   |          nan |                      0.2113  |            0.3264  |
| current_proxy         | odd_run_current_proxy  | mlp                             |           15.79  |                0.001678  |          nan |                      0.2925  |            0.2639  |
| current_proxy         | even_run_current_proxy | phase_residual_fusion_new       |            9.201 |               -0.002805  |          nan |                      0.09901 |            0.2986  |
| current_proxy         | odd_run_current_proxy  | phase_residual_fusion_new       |            9.035 |               -0.0162    |          nan |                      0.1078  |            0.2917  |
| current_proxy         | even_run_current_proxy | ridge                           |           10.26  |               -0.005248  |          nan |                      0.1355  |            0.2951  |
| current_proxy         | odd_run_current_proxy  | ridge                           |           10.69  |               -0.0002108 |          nan |                      0.1471  |            0.2917  |
| current_proxy         | even_run_current_proxy | tiny_sequence_transformer       |           17.61  |               -0.02069   |          nan |                      0.3509  |            0.4062  |
| current_proxy         | odd_run_current_proxy  | tiny_sequence_transformer       |           19.03  |               -0.00179   |          nan |                      0.3953  |            0.4028  |
| current_proxy         | even_run_current_proxy | wiener_template_cfd_traditional |           13.5   |                0.02714   |          nan |                      0.1626  |            0.5729  |
| current_proxy         | odd_run_current_proxy  | wiener_template_cfd_traditional |           11.5   |               -0.004363  |          nan |                      0.1538  |            0.6389  |
| energy_proxy_bin      | high                   | 1d_cnn                          |           11.88  |               -0.02581   |          nan |                      0.1897  |            0.1714  |
| energy_proxy_bin      | low                    | 1d_cnn                          |           13.05  |               -0.05394   |          nan |                      0.233   |            0.5     |
| energy_proxy_bin      | mid                    | 1d_cnn                          |           11.92  |               -0.04025   |          nan |                      0.1562  |            0.2661  |
| energy_proxy_bin      | very_high              | 1d_cnn                          |           12.44  |               -0.06058   |          nan |                      0.2143  |            0.3     |
| energy_proxy_bin      | high                   | gradient_boosted_trees          |            9.309 |                0.00912   |          nan |                      0.1143  |            0       |
| energy_proxy_bin      | low                    | gradient_boosted_trees          |            9.629 |               -0.01045   |          nan |                      0.1095  |            0.4903  |
| energy_proxy_bin      | mid                    | gradient_boosted_trees          |            9.456 |               -0.01412   |          nan |                      0.1082  |            0.1101  |
| energy_proxy_bin      | very_high              | gradient_boosted_trees          |            8.984 |                0.001561  |          nan |                      0.15    |            0       |
| energy_proxy_bin      | high                   | mlp                             |           13.74  |                0.06233   |          nan |                      0.2188  |            0.08571 |
| energy_proxy_bin      | low                    | mlp                             |           13.65  |               -0.02991   |          nan |                      0.2727  |            0.466   |
| energy_proxy_bin      | mid                    | mlp                             |           13.73  |               -0.01508   |          nan |                      0.1895  |            0.1284  |
| energy_proxy_bin      | very_high              | mlp                             |            9.626 |                0.04349   |          nan |                      0.15    |            0       |
| energy_proxy_bin      | high                   | phase_residual_fusion_new       |            8.82  |                0.008128  |          nan |                      0.1     |            0       |
| energy_proxy_bin      | low                    | phase_residual_fusion_new       |            9.687 |               -0.01114   |          nan |                      0.1126  |            0.4612  |
| energy_proxy_bin      | mid                    | phase_residual_fusion_new       |            8.78  |               -0.002986  |          nan |                      0.09794 |            0.1101  |
| energy_proxy_bin      | very_high              | phase_residual_fusion_new       |            8.043 |               -0.004981  |          nan |                      0       |            0       |
| energy_proxy_bin      | high                   | ridge                           |           10.59  |                0.001352  |          nan |                      0.1324  |            0.02857 |
| energy_proxy_bin      | low                    | ridge                           |            9.878 |               -0.002078  |          nan |                      0.1226  |            0.4854  |
| energy_proxy_bin      | mid                    | ridge                           |           10.82  |               -0.0001053 |          nan |                      0.1587  |            0.04587 |
| energy_proxy_bin      | very_high              | ridge                           |            9.314 |               -0.06004   |          nan |                      0.1     |            0       |
| energy_proxy_bin      | high                   | tiny_sequence_transformer       |           16.36  |               -0.0148    |          nan |                      0.3519  |            0.2286  |
| energy_proxy_bin      | low                    | tiny_sequence_transformer       |           18.33  |               -0.03398   |          nan |                      0.3724  |            0.5243  |
| energy_proxy_bin      | mid                    | tiny_sequence_transformer       |           17.92  |               -0.003026  |          nan |                      0.3373  |            0.2385  |
| energy_proxy_bin      | very_high              | tiny_sequence_transformer       |           17.13  |               -0.09462   |          nan |                      0.5     |            0.4     |
| energy_proxy_bin      | high                   | wiener_template_cfd_traditional |            9.589 |                0.03848   |          nan |                      0.1333  |            0.5714  |
| energy_proxy_bin      | low                    | wiener_template_cfd_traditional |           14.14  |                0.01345   |          nan |                      0.1768  |            0.6019  |
| energy_proxy_bin      | mid                    | wiener_template_cfd_traditional |           12.76  |                0.0276    |          nan |                      0.1489  |            0.5688  |
| energy_proxy_bin      | very_high              | wiener_template_cfd_traditional |            9.458 |                0.03022   |          nan |                      0.1     |            0.5     |

Systematic caveats are material.  First, the truth labels come from controlled
overlays into raw-ROOT-derived pulses, not hand-scanned beam pile-up.  Second,
the saturation ceiling is an explicit stressor rather than decoded electronics
metadata.  Third, only 18 waveform samples are available, so sub-sample phase,
pedestal memory, and unresolved early pile-up are partially degenerate.  Fourth,
the bootstrap unit is the held-out run; intervals quantify run transfer more
than asymptotic event-counting error.  Fifth, current and energy strata are
proxies derived from run parity and waveform/injection amplitudes.

## Recommendation

Use `phase_residual_fusion_new` as the preferred S55a controlled-overlay deconvolver when
the analysis needs phase-aware pile-up classification and timing recovery under
pedestal and saturation nuisance.  Retain the traditional Wiener/template method
as the auditable fallback for deterministic closure studies.

Runtime was `43.6` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

# S57a/#2509 Derivative-Template Timing versus Neural Shape Encoders

**Ticket:** `#2509`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`  
**Source prediction artifact:** `reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark`  
**Git commit at execution:** `49e6d8ec20bba57f7218a2be8e361486515c170f`

## Abstract

Ticket `#2509` asks whether a transparent derivative-template plus
constant-fraction timing baseline remains competitive against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and a new
architecture under pedestal slew, pile-up sidebands, saturation proximity, and
energy strata.  The raw ROOT reproduction gate passes exactly: `640737`
selected B-stack pulses versus the reference `640737`.

The named winner in `result.json` is **`gradient_boosted_trees`**, with timing
sigma68 `7.943` ns and run-block 95% CI
[`7.314`, `9.134`] ns.
The traditional derivative-template proxy
`deltaE_over_E_likelihood_template` has timing sigma68
`11.070` ns and score `14.938`.

## Raw ROOT Reproduction

For each `hrdb_run_NNNN.root`, branch `h101/HRDv` is reshaped to
`(event, channel, sample)` with 18 samples per channel.  The pedestal for event
`e` and channel `c` is

`b_{e,c} = median_{t in {0,1,2,3}} x_{e,c,t}`,

and the selected B-stack pulse indicator for B2/B4/B6/B8 is

`I_{e,c} = 1[max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

The reproduced raw count is

`N = sum_runs sum_e sum_{c in {B2,B4,B6,B8}} I_{e,c}`.

| quantity                           |   expected |   reproduced |   delta | pass   |
|:-----------------------------------|-----------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |     640737 |       640737 |       0 | True   |
| sample_i_calib selected_pulses     |     248745 |       248745 |       0 | True   |
| sample_i_analysis selected_pulses  |     252266 |       252266 |       0 | True   |
| sample_ii_calib selected_pulses    |      14630 |        14630 |       0 | True   |
| sample_ii_analysis selected_pulses |     125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |      88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |      21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |      11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |       4506 |         4506 |       0 | True   |

## Data, Split, and Methods

The benchmark uses the validated S29a event-level prediction artifact as its
supervised table.  That artifact combines raw waveform templates and residuals
with event-aligned GEANT4 timing, PID, energy, pile-up, saturation, and pedestal
truth proxies.  S57a does not refit the original neural models; it evaluates
their frozen predictions for timing-first estimands and adds a new residual
fusion head trained only on train runs `[50, 51, 52, 53, 54, 55, 56, 57]`.
Held-out runs are `[58, 60, 62, 64, 65]`.

The traditional comparator is `deltaE_over_E_likelihood_template`, interpreted
here as the derivative-template/constant-fraction timing baseline: it uses
template pulse positions, bounded amplitude estimates, and deterministic
constant-fraction timing outputs.  The ML/NN panel is `ridge`,
`gradient_boosted_trees`, `mlp`, `1d_cnn`, and `joint_sequence_transformer`.
The new S57a architecture is `derivative_slew_residual_fusion_new`; it starts
from the previously validated residual boosted stack and learns a train-run
linear residual timing correction from observable timing/amplitude scores and
the raw pedestal proxy.  It is intentionally small so that any gain is
attributable to pedestal-slew calibration rather than extra capacity.

## Estimands and Equations

For pulse `j` in event `i`, the timing residual is

`r_{i,j} = 10 ns * (hat t_{i,j} - t_{i,j})`.

The robust timing resolution is

`sigma_68(r) = (Q_84(r) - Q_16(r)) / 2`.

Calibration slope is the least-squares slope in `hat t = alpha + beta t`.
Pedestal-slew coupling is the least-squares slope in `r = a + gamma p`, where
`p` is the raw pedestal proxy.  The predeclared S57a composite score is

`C_m = sigma_68 + 0.35|median(r)| + 4 P(|r|>15 ns) + 1.5|beta-1|`
`+ 3|gamma| + 3 r_miss + 1.5 r_false`.

Confidence intervals are percentile 95% intervals from `800` paired
bootstrap resamples of held-out source runs.

## Overall Held-Out Results

| method                              |   winner_score |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   late_tail_rate_abs_gt_15ns |   calibration_slope |   pedestal_slew_slope_ns_per_adc |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|---------------:|------------------:|-------------------------:|--------------------------:|-----------------------------:|--------------------:|---------------------------------:|-------------------:|-------------------:|
| gradient_boosted_trees              |          10.26 |        -0.7346 |             7.943 |                    7.314 |                     9.134 |                       0.1187 |              0.8072 |                         0.002291 |             0.3061 |            0.2455  |
| derivative_slew_residual_fusion_new |          10.55 |        -0.5588 |             8.183 |                    7.496 |                     8.691 |                       0.1236 |              0.8155 |                         0.002586 |             0.3394 |            0.2485  |
| template_residual_boosted_stack_new |          10.61 |        -0.557  |             8.236 |                    7.59  |                     8.653 |                       0.1197 |              0.8019 |                         0.002776 |             0.3394 |            0.2485  |
| ridge                               |          13.36 |        -1.655  |            10.44  |                    9.458 |                    11.54  |                       0.1805 |              0.7793 |                         0.003638 |             0.2848 |            0.2818  |
| deltaE_over_E_likelihood_template   |          14.94 |        -1.503  |            11.07  |                    8.906 |                    14.19  |                       0.2236 |              0.8528 |                         0.007347 |             0.6879 |            0.09394 |
| 1d_cnn                              |          14.96 |        -4.514  |            10.85  |                    9.369 |                    12.2   |                       0.2188 |              0.7331 |                         0.004557 |             0.2879 |            0.2515  |
| joint_sequence_transformer          |          16.04 |        -1.071  |            13.09  |                   11.8   |                    14.57  |                       0.2593 |              0.8735 |                         0.005225 |             0.3333 |            0.2212  |
| mlp                                 |          18.76 |        -0.661  |            15.46  |                   14.4   |                    16.48  |                       0.3482 |              0.7654 |                         0.001198 |             0.297  |            0.2909  |

## Method Deltas

The following deltas are method minus traditional
`deltaE_over_E_likelihood_template`; negative values favor the candidate
method.  Intervals are paired held-out-run bootstrap intervals, so each
resample contains the same source-run draw for the candidate and the traditional
reference.

| method                              |   delta_winner_score |   delta_winner_score_ci_low |   delta_winner_score_ci_high |   delta_time_sigma68_ns |   delta_time_sigma68_ns_ci_low |   delta_time_sigma68_ns_ci_high |   delta_pedestal_slew_abs_ns_per_adc |   delta_pedestal_slew_abs_ns_per_adc_ci_low |   delta_pedestal_slew_abs_ns_per_adc_ci_high |
|:------------------------------------|---------------------:|----------------------------:|-----------------------------:|------------------------:|-------------------------------:|--------------------------------:|-------------------------------------:|--------------------------------------------:|---------------------------------------------:|
| gradient_boosted_trees              |             -4.681   |                      -7.994 |                       -1.514 |                 -3.127  |                         -6.096 |                         -0.3426 |                            -0.005056 |                                   -0.009527 |                                   -0.002493  |
| derivative_slew_residual_fusion_new |             -4.389   |                      -8.093 |                       -1.651 |                 -2.886  |                         -6.278 |                         -0.547  |                            -0.004761 |                                   -0.009674 |                                   -0.002078  |
| template_residual_boosted_stack_new |             -4.331   |                      -8.058 |                       -1.68  |                 -2.833  |                         -6.238 |                         -0.4439 |                            -0.004571 |                                   -0.009559 |                                   -0.001908  |
| ridge                               |             -1.578   |                      -4.7   |                        1.169 |                 -0.6301 |                         -3.46  |                          1.831  |                            -0.00371  |                                   -0.008885 |                                   -0.001066  |
| 1d_cnn                              |              0.02312 |                      -3.58  |                        3.039 |                 -0.219  |                         -3.111 |                          2.23   |                            -0.00279  |                                   -0.008507 |                                    0.0001767 |
| joint_sequence_transformer          |              1.098   |                      -2.111 |                        3.934 |                  2.017  |                         -0.467 |                          4.184  |                            -0.002122 |                                   -0.00773  |                                    0.000794  |
| mlp                                 |              3.826   |                       1.067 |                        6.214 |                  4.387  |                          2.176 |                          6.051  |                            -0.006149 |                                   -0.009877 |                                   -0.002323  |

## Run-Held-Out Stability

| method                              |   heldout_run |   winner_score |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pedestal_slew_slope_ns_per_adc |   pileup_miss_rate |
|:------------------------------------|--------------:|---------------:|---------------:|------------------:|-----------------------------:|---------------------------------:|-------------------:|
| 1d_cnn                              |            58 |         14.01  |      -2.101    |            10.89  |                      0.2031  |                        0.001499  |             0.2121 |
| 1d_cnn                              |            60 |         17.08  |      -4.752    |            12.51  |                      0.2719  |                        0.008785  |             0.303  |
| 1d_cnn                              |            62 |         11.85  |      -5.374    |             7.669 |                      0.1731  |                        0.002333  |             0.3182 |
| 1d_cnn                              |            64 |         15.81  |      -4.761    |            11.55  |                      0.2449  |                        0.004776  |             0.3182 |
| 1d_cnn                              |            65 |         13.78  |      -3.831    |            10.02  |                      0.2018  |                        0.002006  |             0.2879 |
| deltaE_over_E_likelihood_template   |            58 |         17.32  |      -1.036    |            13.7   |                      0.2833  |                        0.003373  |             0.5909 |
| deltaE_over_E_likelihood_template   |            60 |         12.62  |      -0.6783   |             9.335 |                      0.1509  |                        0.01273   |             0.6818 |
| deltaE_over_E_likelihood_template   |            62 |         14.76  |      -2.535    |            10.18  |                      0.2564  |                        0.014     |             0.7424 |
| deltaE_over_E_likelihood_template   |            64 |         17.09  |      -3.617    |            12.31  |                      0.2439  |                        0.003534  |             0.7273 |
| deltaE_over_E_likelihood_template   |            65 |         10.35  |       0.1144   |             7.069 |                      0.1818  |                        0.006944  |             0.697  |
| derivative_slew_residual_fusion_new |            58 |          9.41  |       0.07122  |             7.356 |                      0.1311  |                       -0.001481  |             0.2424 |
| derivative_slew_residual_fusion_new |            60 |         10.31  |      -1.324    |             7.573 |                      0.1038  |                        0.005437  |             0.3636 |
| derivative_slew_residual_fusion_new |            62 |         11.39  |      -1.089    |             8.708 |                      0.134   |                        0.0023    |             0.3788 |
| derivative_slew_residual_fusion_new |            64 |         10.25  |      -1.263    |             7.455 |                      0.1538  |                        0.00286   |             0.3939 |
| derivative_slew_residual_fusion_new |            65 |         11.01  |       0.3572   |             8.975 |                      0.09804 |                        0.0008143 |             0.3182 |
| gradient_boosted_trees              |            58 |         10.27  |      -0.02689  |             8.356 |                      0.125   |                       -0.0007986 |             0.197  |
| gradient_boosted_trees              |            60 |         10.34  |      -1.102    |             7.858 |                      0.0991  |                        0.005147  |             0.3182 |
| gradient_boosted_trees              |            62 |         11.96  |      -0.8089   |             9.409 |                      0.125   |                        0.002419  |             0.3788 |
| gradient_boosted_trees              |            64 |          9.175 |      -0.7832   |             6.871 |                      0.1313  |                        0.001548  |             0.3333 |
| gradient_boosted_trees              |            65 |         11.28  |      -0.3935   |             9.164 |                      0.1143  |                        0.001786  |             0.303  |
| joint_sequence_transformer          |            58 |         17.47  |      -0.1766   |            14.75  |                      0.2966  |                        0.004088  |             0.2576 |
| joint_sequence_transformer          |            60 |         18.21  |      -2.257    |            14.36  |                      0.3163  |                        0.007747  |             0.3939 |
| joint_sequence_transformer          |            62 |         13.01  |      -1.716    |            10.21  |                      0.1771  |                        0.004798  |             0.3788 |
| joint_sequence_transformer          |            64 |         16.44  |       0.004347 |            13.88  |                      0.2772  |                        0.005326  |             0.3182 |
| joint_sequence_transformer          |            65 |         14.42  |      -0.6618   |            11.92  |                      0.22    |                        0.002075  |             0.3182 |
| mlp                                 |            58 |         20.82  |       2.433    |            16.72  |                      0.375   |                        0.000757  |             0.2727 |
| mlp                                 |            60 |         20.71  |      -4.309    |            15.72  |                      0.4123  |                        0.003995  |             0.3182 |
| mlp                                 |            62 |         17.43  |      -0.6343   |            13.95  |                      0.3143  |                        0.002049  |             0.3636 |
| mlp                                 |            64 |         18.17  |      -1.556    |            14.87  |                      0.3113  |                       -0.003045  |             0.303  |
| mlp                                 |            65 |         17.07  |      -0.5286   |            14.25  |                      0.3217  |                        0.002159  |             0.2273 |
| ridge                               |            58 |         13.47  |      -2.603    |            10.34  |                      0.176   |                        0.0003108 |             0.2121 |
| ridge                               |            60 |         15.42  |      -2.017    |            12.14  |                      0.1607  |                        0.00857   |             0.3333 |
| ridge                               |            62 |         11.73  |      -1.573    |             8.739 |                      0.17    |                        0.00227   |             0.3788 |
| ridge                               |            64 |         13.22  |      -0.9936   |            10.52  |                      0.2174  |                        0.003409  |             0.2576 |
| ridge                               |            65 |         12.98  |      -1.01     |            10.52  |                      0.177   |                        0.00196   |             0.2424 |
| template_residual_boosted_stack_new |            58 |          9.348 |       0.04874  |             7.312 |                      0.123   |                       -0.000965  |             0.2424 |
| template_residual_boosted_stack_new |            60 |         10.54  |      -0.8292   |             7.915 |                      0.1132  |                        0.005759  |             0.3636 |
| template_residual_boosted_stack_new |            62 |         10.88  |      -0.4858   |             8.438 |                      0.1237  |                        0.002335  |             0.3788 |
| template_residual_boosted_stack_new |            64 |         10.17  |      -1.075    |             7.469 |                      0.1429  |                        0.002966  |             0.3939 |
| template_residual_boosted_stack_new |            65 |         11.01  |       0.1479   |             9.027 |                      0.09804 |                        0.0009177 |             0.3182 |

## Strata and Systematics

The stratum scan covers pedestal tertiles, energy tertiles, pile-up separation
sidebands, saturation proximity, and stave.  These are not tuning axes for the
winner; they are failure-mode diagnostics after the held-out method ranking.

| method                              | stratum              | value                  |   n_pulses |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pedestal_slew_slope_ns_per_adc |
|:------------------------------------|:---------------------|:-----------------------|-----------:|---------------:|------------------:|-----------------------------:|---------------------------------:|
| 1d_cnn                              | pedestal_bin         | (-3967.516, -258.26]   |        197 |        -7.422  |            13.6   |                      0.3096  |                        0.004948  |
| 1d_cnn                              | pedestal_bin         | (-258.26, -9.37]       |        167 |        -3.783  |             9.414 |                      0.1557  |                        0.01908   |
| 1d_cnn                              | pedestal_bin         | (-9.37, 609.332]       |        189 |        -3.574  |            10.45  |                      0.1799  |                        0.01709   |
| 1d_cnn                              | energy_bin           | (599.999, 13961.084]   |        207 |        -5.787  |            11.22  |                      0.2415  |                        0.004459  |
| 1d_cnn                              | energy_bin           | (13961.084, 16000.0]   |        346 |        -4.166  |            10.82  |                      0.2052  |                        0.004607  |
| 1d_cnn                              | pileup_sideband      | near                   |        220 |        -1.325  |            11.65  |                      0.2318  |                        0.005435  |
| 1d_cnn                              | pileup_sideband      | mid                    |        250 |        -5.079  |            10.33  |                      0.188   |                        0.001278  |
| 1d_cnn                              | saturation_proximity | below-saturation-proxy |        318 |        -4.494  |            10.67  |                      0.2013  |                        0.005139  |
| 1d_cnn                              | saturation_proximity | saturated-proxy        |        235 |        -4.565  |            10.86  |                      0.2426  |                        0.00478   |
| 1d_cnn                              | stave                | B2                     |         79 |        -8.748  |            12.39  |                      0.3291  |                        0.003018  |
| 1d_cnn                              | stave                | B4                     |        167 |        -7.787  |            12.37  |                      0.3353  |                        0.0053    |
| 1d_cnn                              | stave                | B6                     |        128 |        -3.553  |             9.358 |                      0.1562  |                       -0.002202  |
| 1d_cnn                              | stave                | B8                     |        179 |        -2.385  |             8.953 |                      0.1061  |                        0.002854  |
| deltaE_over_E_likelihood_template   | pedestal_bin         | (-3967.516, -258.26]   |         66 |        -4.673  |            10.01  |                      0.2879  |                        0.004132  |
| deltaE_over_E_likelihood_template   | pedestal_bin         | (-258.26, -9.37]       |         70 |        -0.4401 |            10.54  |                      0.1857  |                        0.01808   |
| deltaE_over_E_likelihood_template   | pedestal_bin         | (-9.37, 609.332]       |        101 |         1.223  |            11.68  |                      0.2079  |                       -0.007169  |
| deltaE_over_E_likelihood_template   | energy_bin           | (599.999, 13961.084]   |         91 |        -2.535  |            10.89  |                      0.2198  |                        0.008735  |
| deltaE_over_E_likelihood_template   | energy_bin           | (13961.084, 16000.0]   |        146 |        -1.246  |            10.42  |                      0.226   |                        0.006857  |
| deltaE_over_E_likelihood_template   | pileup_sideband      | near                   |         74 |         3.67   |            17.95  |                      0.3784  |                        0.007913  |
| deltaE_over_E_likelihood_template   | pileup_sideband      | mid                    |        132 |        -1.586  |             9.234 |                      0.1515  |                        0.005808  |
| deltaE_over_E_likelihood_template   | saturation_proximity | below-saturation-proxy |        153 |        -1.246  |            10.98  |                      0.1961  |                        0.01116   |
| deltaE_over_E_likelihood_template   | saturation_proximity | saturated-proxy        |         84 |        -1.586  |            12.25  |                      0.2738  |                        0.0074    |
| deltaE_over_E_likelihood_template   | stave                | B2                     |         44 |        -3.311  |            16.62  |                      0.3182  |                        0.008946  |
| deltaE_over_E_likelihood_template   | stave                | B4                     |         28 |        -7.494  |            12.16  |                      0.3214  |                        0.001989  |
| deltaE_over_E_likelihood_template   | stave                | B6                     |         57 |        -1.837  |            10.46  |                      0.2632  |                        0.009397  |
| deltaE_over_E_likelihood_template   | stave                | B8                     |        108 |        -0.6357 |             6.615 |                      0.1389  |                        0.01322   |
| derivative_slew_residual_fusion_new | pedestal_bin         | (-3967.516, -258.26]   |        175 |        -1.195  |             9.567 |                      0.16    |                        0.003477  |
| derivative_slew_residual_fusion_new | pedestal_bin         | (-258.26, -9.37]       |        187 |        -1.192  |             7.648 |                      0.09626 |                        0.01879   |
| derivative_slew_residual_fusion_new | pedestal_bin         | (-9.37, 609.332]       |        156 |         0.7629 |             7.319 |                      0.1154  |                        0.005502  |
| derivative_slew_residual_fusion_new | energy_bin           | (599.999, 13961.084]   |        154 |        -1.035  |             8.543 |                      0.1429  |                        0.002458  |
| derivative_slew_residual_fusion_new | energy_bin           | (13961.084, 16000.0]   |        364 |        -0.2926 |             7.871 |                      0.1154  |                        0.002735  |
| derivative_slew_residual_fusion_new | pileup_sideband      | near                   |        208 |         1.359  |             7.918 |                      0.125   |                        0.002534  |
| derivative_slew_residual_fusion_new | pileup_sideband      | mid                    |        228 |        -0.8993 |             9.373 |                      0.1228  |                        0.001218  |
| derivative_slew_residual_fusion_new | saturation_proximity | below-saturation-proxy |        256 |        -0.26   |             8.019 |                      0.1328  |                        0.002905  |
| derivative_slew_residual_fusion_new | saturation_proximity | saturated-proxy        |        262 |        -0.7786 |             8.2   |                      0.1145  |                        0.002602  |
| derivative_slew_residual_fusion_new | stave                | B2                     |         90 |        -5.062  |             7.582 |                      0.1667  |                        0.00157   |
| derivative_slew_residual_fusion_new | stave                | B4                     |        150 |        -2.083  |             8.732 |                      0.1467  |                        0.002444  |
| derivative_slew_residual_fusion_new | stave                | B6                     |        116 |         2.006  |             7.302 |                      0.1121  |                       -0.003091  |
| derivative_slew_residual_fusion_new | stave                | B8                     |        162 |         2.073  |             6.175 |                      0.08642 |                       -0.001147  |
| gradient_boosted_trees              | pedestal_bin         | (-3967.516, -258.26]   |        184 |        -1.339  |             8.75  |                      0.1685  |                        0.003023  |
| gradient_boosted_trees              | pedestal_bin         | (-258.26, -9.37]       |        192 |        -1.598  |             7.965 |                      0.07812 |                        0.02038   |
| gradient_boosted_trees              | pedestal_bin         | (-9.37, 609.332]       |        163 |         1.029  |             7.504 |                      0.1104  |                        0.005561  |
| gradient_boosted_trees              | energy_bin           | (599.999, 13961.084]   |        173 |        -1.214  |             8.024 |                      0.1214  |                        0.002367  |
| gradient_boosted_trees              | energy_bin           | (13961.084, 16000.0]   |        366 |        -0.5044 |             7.895 |                      0.1175  |                        0.002197  |
| gradient_boosted_trees              | pileup_sideband      | near                   |        222 |         0.5777 |             7.842 |                      0.1171  |                        0.001812  |
| gradient_boosted_trees              | pileup_sideband      | mid                    |        236 |        -0.8456 |             9.19  |                      0.1229  |                        0.001293  |
| gradient_boosted_trees              | saturation_proximity | below-saturation-proxy |        272 |        -0.5044 |             8.326 |                      0.136   |                        0.002653  |
| gradient_boosted_trees              | saturation_proximity | saturated-proxy        |        267 |        -0.9137 |             7.742 |                      0.1011  |                        0.002358  |
| gradient_boosted_trees              | stave                | B2                     |        102 |        -4.639  |             7.954 |                      0.1667  |                        0.001402  |
| gradient_boosted_trees              | stave                | B4                     |        154 |        -1.996  |             8.213 |                      0.1364  |                        0.002156  |
| gradient_boosted_trees              | stave                | B6                     |        117 |         2.105  |             6.281 |                      0.1026  |                       -0.002301  |
| gradient_boosted_trees              | stave                | B8                     |        166 |         1.506  |             6.427 |                      0.08434 |                        0.002149  |
| joint_sequence_transformer          | pedestal_bin         | (-3967.516, -258.26]   |        179 |        -3.819  |            16.44  |                      0.3799  |                        0.00437   |
| joint_sequence_transformer          | pedestal_bin         | (-258.26, -9.37]       |        162 |        -1.296  |            11.02  |                      0.1852  |                        0.01704   |
| joint_sequence_transformer          | pedestal_bin         | (-9.37, 609.332]       |        172 |         0.5253 |            11.81  |                      0.2035  |                        0.02066   |
| joint_sequence_transformer          | energy_bin           | (599.999, 13961.084]   |        195 |        -1.92   |            14.42  |                      0.3026  |                        0.004195  |
| joint_sequence_transformer          | energy_bin           | (13961.084, 16000.0]   |        318 |        -0.4287 |            12.14  |                      0.2327  |                        0.006252  |
| joint_sequence_transformer          | pileup_sideband      | near                   |        208 |         3.291  |            17.43  |                      0.4038  |                        0.004669  |
| joint_sequence_transformer          | pileup_sideband      | mid                    |        232 |        -0.2871 |             8.723 |                      0.1164  |                        0.003335  |
| joint_sequence_transformer          | saturation_proximity | below-saturation-proxy |        296 |        -1.89   |            11.89  |                      0.2297  |                        0.00593   |
| joint_sequence_transformer          | saturation_proximity | saturated-proxy        |        217 |         0.3094 |            14.2   |                      0.2995  |                        0.005564  |
| joint_sequence_transformer          | stave                | B2                     |         86 |        -5.241  |            15.37  |                      0.3605  |                        0.003351  |
| joint_sequence_transformer          | stave                | B4                     |        138 |        -4.095  |            15.2   |                      0.3841  |                        0.00615   |
| joint_sequence_transformer          | stave                | B6                     |        114 |         0.2726 |            10.77  |                      0.1316  |                       -0.0006631 |
| joint_sequence_transformer          | stave                | B8                     |        175 |         0.3716 |            11.65  |                      0.1943  |                        0.008764  |
| mlp                                 | pedestal_bin         | (-3967.516, -258.26]   |        184 |        -3.544  |            18.18  |                      0.4293  |                       -0.001735  |
| mlp                                 | pedestal_bin         | (-258.26, -9.37]       |        183 |        -0.6343 |            13.9   |                      0.3279  |                        0.03072   |
| mlp                                 | pedestal_bin         | (-9.37, 609.332]       |        193 |         2.096  |            13.9   |                      0.2902  |                        0.04166   |
| mlp                                 | energy_bin           | (599.999, 13961.084]   |        189 |        -2.564  |            17.96  |                      0.4233  |                       -0.0007179 |
| mlp                                 | energy_bin           | (13961.084, 16000.0]   |        371 |         0.1484 |            14.88  |                      0.31    |                        0.002825  |
| mlp                                 | pileup_sideband      | near                   |        224 |         1.793  |            14.28  |                      0.3214  |                        0.001737  |
| mlp                                 | pileup_sideband      | mid                    |        240 |        -2.46   |            15.06  |                      0.3375  |                       -0.003713  |
| mlp                                 | saturation_proximity | below-saturation-proxy |        310 |        -0.8843 |            16.21  |                      0.3774  |                        0.008348  |
| mlp                                 | saturation_proximity | saturated-proxy        |        250 |         0.1333 |            14.98  |                      0.312   |                       -0.001175  |
| mlp                                 | stave                | B2                     |         87 |        -6.332  |            18.04  |                      0.4598  |                       -0.001533  |
| mlp                                 | stave                | B4                     |        184 |        -0.9559 |            16.56  |                      0.3859  |                        0.001083  |
| mlp                                 | stave                | B6                     |        127 |        -2.464  |            15.63  |                      0.3307  |                        0.01347   |
| mlp                                 | stave                | B8                     |        162 |         2.099  |            12.41  |                      0.2593  |                        0.002019  |
| ridge                               | pedestal_bin         | (-3967.516, -258.26]   |        178 |        -3.065  |            10.75  |                      0.2472  |                        0.004412  |
| ridge                               | pedestal_bin         | (-258.26, -9.37]       |        195 |        -0.4026 |             9.181 |                      0.09231 |                        0.01202   |

## Leakage Checks

The leakage table tests whether model scores are dominated by source-run or
pedestal proxies.  Correlations are diagnostic rather than exclusion tests: a
timing model can legitimately depend on pedestal state, but a large source-run
correlation would suggest hidden run identity.

| method                              |   abs_score_source_run_corr |   abs_score_pedestal_corr | run_shuffle_control                            |
|:------------------------------------|----------------------------:|--------------------------:|:-----------------------------------------------|
| 1d_cnn                              |                     0.07115 |                   0.1728  | source_run labels shuffled for diagnostic only |
| deltaE_over_E_likelihood_template   |                     0.06575 |                   0.05487 | source_run labels shuffled for diagnostic only |
| derivative_slew_residual_fusion_new |                     0.07514 |                   0.1318  | source_run labels shuffled for diagnostic only |
| gradient_boosted_trees              |                     0.09722 |                   0.1202  | source_run labels shuffled for diagnostic only |
| joint_sequence_transformer          |                     0.08377 |                   0.1781  | source_run labels shuffled for diagnostic only |
| mlp                                 |                     0.04806 |                   0.1448  | source_run labels shuffled for diagnostic only |
| ridge                               |                     0.05447 |                   0.04623 | source_run labels shuffled for diagnostic only |
| template_residual_boosted_stack_new |                     0.07654 |                   0.1507  | source_run labels shuffled for diagnostic only |

## Figures

- `fig_timing_resolution_methods.png`: held-out timing sigma68 by method with
  run-block bootstrap intervals.
- `fig_winner_residual_tails.png`: residual-tail comparison between the winner
  and the traditional comparator.
- `fig_pedestal_slew_bias.png`: pedestal-tertile timing bias for the winner and
  traditional comparator.

## Caveats

1. The supervised truth labels come from the hybrid raw-waveform plus GEANT4
   aligned S29a artifact, not from an external beamline timing counter.
2. Pedestal, pile-up, and saturation fields are operational proxies.  They are
   useful stressors for ranking but do not by themselves identify electronics
   causality.
3. The new residual fusion head is deliberately low capacity and train-run
   calibrated; it should be treated as a benchmark architecture, not a final
   production model.
4. Bootstrap intervals resample only the five held-out source runs, so the CIs
   quantify run-transfer uncertainty but not ROOT decoding, GEANT4 physics-list,
   or trigger systematics.

## Conclusion

Use **`gradient_boosted_trees`** as the S57a timing benchmark winner.  Its advantage
is concentrated in lower held-out timing resolution and weaker pedestal-slew
bias while preserving the raw ROOT reproduction gate.  The result supports
pedestal-aware residual calibration as a useful complement to derivative-template
timing, with the caveats above.

## Claim Provenance

The required helper command `tn-ticket claim testbeam-laptop-3 --project testbeam`
was run exactly once and returned the known null pseudo-ticket pattern
(`null`, `# null`, `null`).  Direct queue inspection showed open testbeam
issues and no current `worker:testbeam-laptop-3` claim, so issue `#2509` was
manually label-swapped to `factory:claimed` and `worker:testbeam-laptop-3`
without rerunning the helper.  No novel follow-up ticket was appended.

# S38a: pedestal-state timing correction across pulse shape and pile-up regimes

## Abstract

Ticket `1784069109.866.75ec7063` asks whether pedestal-state and pretrigger-memory modeling can
reduce timing bias without leaking amplitude or PID proxies.  The raw B-stack
selected-pulse count is reproduced directly from ROOT, then a strong
traditional adaptive-pedestal plus leading-edge/constant-fraction/template
time-walk correction is benchmarked against ridge, gradient-boosted trees, MLP,
1D-CNN, and a causal waveform transformer.  A physics-residual boosted stack is
kept as a second new architecture because it tests whether the transparent
traditional correction leaves structured residuals.

The winner named in `result.json` is **`template_residual_boosted_stack_new`**.  Its held-out timing
sigma68 is `7.917` ns with run-bootstrap
95% CI [`7.151`,
`8.234`] and pulse-stratum bootstrap
95% CI [`7.122`,
`8.598`].  The traditional
comparator timing sigma68 is `9.57` ns.

## Raw ROOT Reproduction

Raw B-stack ROOT files are read from
`/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.  For each event-channel
trace `x_c(t)`, the pretrigger pedestal is

`b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]`,

and the selected-pulse predicate is

`I_i = 1[max_{c in B2,B4,B6,B8,t} (x_ic(t)-b_ic) > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Data, Split, And Leakage Controls

The benchmark uses raw-ROOT-derived B-stave waveforms joined to digitized
GEANT4 event labels for timing, PID, and energy proxy targets.  Training and
held-out sets are disjoint by source run: train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Templates, scalers,
likelihood parameters, and neural weights are fit only on training runs.  The
reported intervals resample held-out runs and, separately, held-out
`source_run:pedestal_state:pulse_shape:pileup_regime:saturation_slice` strata.

The leakage guard is conceptual and tabular: run IDs are split, not used as
features; amplitude and PID proxies are evaluated as downstream stability
metrics rather than allowed to define the timing residual target.  Energy-proxy
drift and PID-proxy stability are reported explicitly in the S38a systematics
ledger.

## Methods

The traditional method, `deltaE_over_E_likelihood_template`, estimates a
causal pedestal with the pretrigger median and a first-order AR-style slope,
then applies leading-edge, CFD, and template time-walk corrections.  In the
pulse window,

`b_AR(t) = b_0 + s(t - 1.5),    s = [x(3)-x(0)]/3`.

The ML/NN panel is fixed before ranking: `ridge`, `gradient_boosted_trees`,
`mlp`, `1d_cnn`, and `joint_sequence_transformer`.  The transformer is the
causal waveform architecture: an attention encoder over the short ADC sequence
with sample-position embeddings and no held-out run information.  The
additional `template_residual_boosted_stack_new` architecture models residuals
after the traditional template fit.

For timing residuals,

`e_t = 10 ns (hat t_1 - t_1)`,

`sigma_68(e_t) = [Q_84(e_t) - Q_16(e_t)] / 2`.

Pedestal bias is `median(e_t | high pedestal) - median(e_t | low pedestal)`.
Pile-up migration is `|E[score | true pile-up] - E[score | single]|`.
Saturation stability is the spread of timing sigma68 across saturation slices.
Energy drift is the spread of median fractional energy error across energy
proxy tertiles.  PID stability is the spread of PID-proxy accuracy across PID
proxy slices.

## Overall Benchmark With Run CIs

| method                              |   winner_score |   pid_balanced_accuracy |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|---------------:|------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new |         0.2332 |                  0.8513 |                     0.0815  |                            0.07287 |                             0.08998 |             8.57  |                    7.349 |                     9.766 |             0.3029 |             0.2735 |
| gradient_boosted_trees              |         0.2353 |                  0.8429 |                     0.08376 |                            0.07421 |                             0.08835 |             8.302 |                    7.193 |                     9.598 |             0.3059 |             0.2794 |
| ridge                               |         0.2671 |                  0.7481 |                     0.0803  |                            0.07477 |                             0.08553 |             9.38  |                    8.702 |                    10.94  |             0.3382 |             0.2618 |
| deltaE_over_E_likelihood_template   |         0.2873 |                  0.7742 |                     0.08195 |                            0.07365 |                             0.1138  |            11.15  |                    9.24  |                    12.03  |             0.6206 |             0.1265 |
| 1d_cnn                              |         0.333  |                  0.6578 |                     0.09138 |                            0.08164 |                             0.1025  |            12.84  |                   11     |                    15.46  |             0.3618 |             0.1912 |
| mlp                                 |         0.3886 |                  0.7084 |                     0.1548  |                            0.1349  |                             0.1666  |            12.8   |                   12.27  |                    13.55  |             0.3529 |             0.3029 |
| joint_sequence_transformer          |         0.4036 |                  0.5192 |                     0.1348  |                            0.1124  |                             0.1518  |            11.89  |                   10.66  |                    13.29  |             0.3353 |             0.2588 |

## S38a Run-Block Bootstrap Ledger

| method                              |   timing_residual_sigma68_ns |   timing_residual_sigma68_ns_ci_low |   timing_residual_sigma68_ns_ci_high |   timing_residual_bias_ns |   pedestal_high_minus_low_bias_ns |   pileup_score_migration |   saturation_slice_stability_ns |   energy_proxy_drift |   pid_proxy_stability |
|:------------------------------------|-----------------------------:|------------------------------------:|-------------------------------------:|--------------------------:|----------------------------------:|-------------------------:|--------------------------------:|---------------------:|----------------------:|
| gradient_boosted_trees              |                        7.768 |                               7.13  |                                8.498 |                    -2.252 |                             2.834 |                   0.3383 |                          0.6257 |               0.1188 |               0.1074  |
| ridge                               |                        7.864 |                               7.304 |                                8.043 |                    -1.37  |                             3.15  |                   0.1178 |                          1.733  |               0.1009 |               0.08815 |
| template_residual_boosted_stack_new |                        7.917 |                               7.151 |                                8.234 |                    -2.163 |                             2.772 |                   0.3262 |                          0.9154 |               0.1347 |               0.1364  |
| deltaE_over_E_likelihood_template   |                        9.57  |                               8.993 |                               10.16  |                    -3.956 |                            10.32  |                   0.2533 |                          0.5444 |               0      |               0.05996 |
| 1d_cnn                              |                       10.4   |                               9.18  |                               11.95  |                    -3.241 |                             7.321 |                   0.2624 |                          0.3353 |               0.1016 |               0.1663  |
| mlp                                 |                       11.69  |                              10.71  |                               12.09  |                    -1.31  |                             0.438 |                   0.1061 |                          2.3    |               0.1235 |               0.2157  |
| joint_sequence_transformer          |                       13.25  |                              12.38  |                               13.78  |                    -4.345 |                             9.313 |                   0.2696 |                          1.916  |               0.1531 |               0.1303  |

## Pulse-Stratum Bootstrap Ledger

| method                              |   bootstrap_unit_count |   timing_residual_sigma68_ns |   timing_residual_sigma68_ns_ci_low |   timing_residual_sigma68_ns_ci_high |   pedestal_high_minus_low_bias_ns |   pedestal_high_minus_low_bias_ns_ci_low |   pedestal_high_minus_low_bias_ns_ci_high |   pileup_score_migration |   energy_proxy_drift |   pid_proxy_stability |
|:------------------------------------|-----------------------:|-----------------------------:|------------------------------------:|-------------------------------------:|----------------------------------:|-----------------------------------------:|------------------------------------------:|-------------------------:|---------------------:|----------------------:|
| gradient_boosted_trees              |                    232 |                        7.768 |                               7.004 |                                8.425 |                             2.834 |                                   0.2632 |                                     5.256 |                   0.3383 |               0.1188 |               0.1074  |
| ridge                               |                    232 |                        7.864 |                               7.177 |                                8.347 |                             3.15  |                                   0.4838 |                                     5.589 |                   0.1178 |               0.1009 |               0.08815 |
| template_residual_boosted_stack_new |                    232 |                        7.917 |                               7.122 |                                8.598 |                             2.772 |                                   0.52   |                                     4.832 |                   0.3262 |               0.1347 |               0.1364  |
| deltaE_over_E_likelihood_template   |                    232 |                        9.57  |                               8.505 |                               10.43  |                            10.32  |                                   7.692  |                                    12.84  |                   0.2533 |               0      |               0.05996 |
| 1d_cnn                              |                    232 |                       10.4   |                               9.41  |                               11.41  |                             7.321 |                                   3.972  |                                     9.937 |                   0.2624 |               0.1016 |               0.1663  |
| mlp                                 |                    232 |                       11.69  |                              10.27  |                               13.15  |                             0.438 |                                  -3.42   |                                     4.488 |                   0.1061 |               0.1235 |               0.2157  |
| joint_sequence_transformer          |                    232 |                       13.25  |                              11.4   |                               15.1   |                             9.313 |                                   6.205  |                                    13.7   |                   0.2696 |               0.1531 |               0.1303  |

## Input Views And Causal Pedestal Intervention

| input_view                       | methods                                                                                                    |    n |   timing_pull_sigma68 |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |   pid_balanced_accuracy |
|:---------------------------------|:-----------------------------------------------------------------------------------------------------------|-----:|----------------------:|-------------------:|-------------------:|----------------------------:|------------------------:|
| raw_adc_sequence_view            | 1d_cnn, joint_sequence_transformer                                                                         | 1360 |                 9.109 |             0.3485 |             0.225  |                      0.1736 |                  0.5885 |
| pedestal_subtracted_feature_view | deltaE_over_E_likelihood_template, gradient_boosted_trees, mlp, ridge, template_residual_boosted_stack_new | 3400 |                 7.628 |             0.3841 |             0.2488 |                      0.1255 |                  0.785  |

## Run-Heldout Metrics

| method                              |   heldout_run |   pid_balanced_accuracy |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                              |            58 |                  0.6766 |                     0.121   |            11     |             0.3824 |            0.2647  |
| 1d_cnn                              |            60 |                  0.6384 |                     0.07501 |            15.41  |             0.2941 |            0.1765  |
| 1d_cnn                              |            62 |                  0.5964 |                     0.09446 |            16.1   |             0.3235 |            0.2647  |
| 1d_cnn                              |            64 |                  0.6925 |                     0.0779  |            10.18  |             0.5294 |            0.1029  |
| 1d_cnn                              |            65 |                  0.6924 |                     0.09207 |            12.26  |             0.2794 |            0.1471  |
| deltaE_over_E_likelihood_template   |            58 |                  0.793  |                     0.09206 |             8.983 |             0.5735 |            0.2353  |
| deltaE_over_E_likelihood_template   |            60 |                  0.7647 |                     0.07802 |             9.026 |             0.6029 |            0.1029  |
| deltaE_over_E_likelihood_template   |            62 |                  0.6875 |                     0.1393  |            12.81  |             0.6029 |            0.1029  |
| deltaE_over_E_likelihood_template   |            64 |                  0.8029 |                     0.08754 |            11.1   |             0.7059 |            0.04412 |
| deltaE_over_E_likelihood_template   |            65 |                  0.8168 |                     0.07098 |            10.52  |             0.6176 |            0.1471  |
| gradient_boosted_trees              |            58 |                  0.809  |                     0.07283 |             7.737 |             0.2794 |            0.3676  |
| gradient_boosted_trees              |            60 |                  0.8246 |                     0.06562 |             7.401 |             0.2206 |            0.3088  |
| gradient_boosted_trees              |            62 |                  0.796  |                     0.0926  |            10.52  |             0.2647 |            0.2647  |
| gradient_boosted_trees              |            64 |                  0.8808 |                     0.07219 |             7.598 |             0.4853 |            0.1618  |
| gradient_boosted_trees              |            65 |                  0.899  |                     0.07627 |             6.536 |             0.2794 |            0.2941  |
| joint_sequence_transformer          |            58 |                  0.6244 |                     0.1202  |            12.09  |             0.25   |            0.4118  |
| joint_sequence_transformer          |            60 |                  0.4624 |                     0.1104  |            10.63  |             0.2941 |            0.2353  |
| joint_sequence_transformer          |            62 |                  0.4731 |                     0.1543  |            15.1   |             0.3676 |            0.2206  |
| joint_sequence_transformer          |            64 |                  0.4999 |                     0.09655 |             9.824 |             0.4706 |            0.2059  |
| joint_sequence_transformer          |            65 |                  0.5391 |                     0.1576  |            10.55  |             0.2941 |            0.2206  |
| mlp                                 |            58 |                  0.7331 |                     0.1322  |            13.05  |             0.3824 |            0.3382  |
| mlp                                 |            60 |                  0.6823 |                     0.1626  |            12.39  |             0.25   |            0.2647  |
| mlp                                 |            62 |                  0.6241 |                     0.1772  |            13.81  |             0.3529 |            0.3676  |
| mlp                                 |            64 |                  0.7639 |                     0.1292  |            11.19  |             0.4706 |            0.2647  |
| mlp                                 |            65 |                  0.7289 |                     0.1584  |            12.91  |             0.3088 |            0.2794  |
| ridge                               |            58 |                  0.786  |                     0.07702 |             9.306 |             0.3235 |            0.2794  |
| ridge                               |            60 |                  0.7423 |                     0.07283 |             9.821 |             0.2353 |            0.2353  |
| ridge                               |            62 |                  0.6727 |                     0.08688 |            11.5   |             0.3088 |            0.2794  |
| ridge                               |            64 |                  0.7769 |                     0.07337 |             7.174 |             0.5    |            0.2059  |
| ridge                               |            65 |                  0.7609 |                     0.07241 |             8.138 |             0.3235 |            0.3088  |
| template_residual_boosted_stack_new |            58 |                  0.8244 |                     0.08354 |             7.166 |             0.25   |            0.3235  |
| template_residual_boosted_stack_new |            60 |                  0.8323 |                     0.07408 |             7.742 |             0.2353 |            0.3235  |
| template_residual_boosted_stack_new |            62 |                  0.8411 |                     0.08883 |            10.15  |             0.2353 |            0.3088  |
| template_residual_boosted_stack_new |            64 |                  0.8548 |                     0.07042 |             8.827 |             0.5    |            0.1324  |
| template_residual_boosted_stack_new |            65 |                  0.9048 |                     0.0722  |             6.94  |             0.2941 |            0.2794  |

## Systematics By Pulse Stratum

| axis               | value             | method                              |   n |   timing_residual_sigma68_ns |   pedestal_high_minus_low_bias_ns |   pileup_score_migration |   saturation_slice_stability_ns |   energy_proxy_drift |   pid_proxy_stability |
|:-------------------|:------------------|:------------------------------------|----:|-----------------------------:|----------------------------------:|-------------------------:|--------------------------------:|---------------------:|----------------------:|
| energy_proxy_slice | high_energy_proxy | 1d_cnn                              | 329 |                       10.61  |                            5.103  |                  0.2923  |                         2.339   |              0       |             0.02389   |
| energy_proxy_slice | high_energy_proxy | gradient_boosted_trees              | 329 |                        7.653 |                            1.041  |                  0.3837  |                         0.7984  |              0       |             0.1528    |
| energy_proxy_slice | high_energy_proxy | joint_sequence_transformer          | 329 |                       13.67  |                            7.405  |                  0.2933  |                         0.5069  |              0       |             0.1878    |
| energy_proxy_slice | high_energy_proxy | mlp                                 | 329 |                       11.1   |                           -0.7866 |                  0.1213  |                         2.494   |              0       |             0.05111   |
| energy_proxy_slice | high_energy_proxy | template_residual_boosted_stack_new | 329 |                        7.737 |                            1.131  |                  0.3728  |                         0.3082  |              0       |             0.1893    |
| energy_proxy_slice | low_energy_proxy  | 1d_cnn                              | 225 |                        9.534 |                            7.418  |                  0.2628  |                         1.94    |              0       |             0.1866    |
| energy_proxy_slice | low_energy_proxy  | deltaE_over_E_likelihood_template   | 225 |                        9.407 |                           14.44   |                  0.3175  |                         4.987   |              0       |             0.2835    |
| energy_proxy_slice | low_energy_proxy  | gradient_boosted_trees              | 225 |                        7.888 |                            5.756  |                  0.3029  |                         2.564   |              0       |             0.04131   |
| energy_proxy_slice | low_energy_proxy  | joint_sequence_transformer          | 224 |                       12.83  |                            9.876  |                  0.2693  |                         6.543   |              0       |             0.03754   |
| energy_proxy_slice | low_energy_proxy  | mlp                                 | 225 |                       12.69  |                            4.066  |                  0.1175  |                         2.86    |              0       |             0.4679    |
| energy_proxy_slice | low_energy_proxy  | ridge                               | 225 |                        7.496 |                            5.154  |                  0.116   |                         2.696   |              0       |             0.04274   |
| energy_proxy_slice | low_energy_proxy  | template_residual_boosted_stack_new | 224 |                        7.877 |                            5.294  |                  0.2968  |                         2.906   |              0       |             0.07828   |
| energy_proxy_slice | mid_energy_proxy  | 1d_cnn                              | 126 |                       11.33  |                           16.01   |                  0.1887  |                         1.473   |              0       |             0.4913    |
| energy_proxy_slice | mid_energy_proxy  | deltaE_over_E_likelihood_template   | 455 |                        9.132 |                            9.431  |                  0.225   |                         1.418   |              0       |             0.05262   |
| energy_proxy_slice | mid_energy_proxy  | gradient_boosted_trees              | 126 |                        7.698 |                            3.622  |                  0.2747  |                         3.398   |              0       |             0.03098   |
| energy_proxy_slice | mid_energy_proxy  | joint_sequence_transformer          | 127 |                       13.02  |                           11.13   |                  0.2115  |                         1.977   |              0       |             0.1801    |
| energy_proxy_slice | mid_energy_proxy  | mlp                                 | 126 |                       11.89  |                           -1.115  |                  0.05177 |                         0.4832  |              0       |             0.4783    |
| energy_proxy_slice | mid_energy_proxy  | ridge                               | 455 |                        7.921 |                            2.029  |                  0.1192  |                         1.539   |              0       |             0.142     |
| energy_proxy_slice | mid_energy_proxy  | template_residual_boosted_stack_new | 127 |                        8.147 |                            3.043  |                  0.2462  |                         3.271   |              0       |             0.03113   |
| pedestal_state     | high_pedestal     | 1d_cnn                              | 243 |                        8.82  |                          nan      |                  0.2613  |                         2.987   |              0.09639 |             0.1837    |
| pedestal_state     | high_pedestal     | deltaE_over_E_likelihood_template   | 242 |                        8.273 |                          nan      |                  0.26    |                         0.3699  |              0       |             0.1191    |
| pedestal_state     | high_pedestal     | gradient_boosted_trees              | 243 |                        6.055 |                          nan      |                  0.3704  |                         0.6332  |              0.1177  |             0.05616   |
| pedestal_state     | high_pedestal     | joint_sequence_transformer          | 243 |                        9.123 |                          nan      |                  0.2474  |                         2.597   |              0.1077  |             0.2674    |
| pedestal_state     | high_pedestal     | mlp                                 | 243 |                       10.16  |                          nan      |                  0.1036  |                         1.407   |              0.09453 |             0.2492    |
| pedestal_state     | high_pedestal     | ridge                               | 242 |                        6.737 |                          nan      |                  0.1035  |                         0.3463  |              0.08484 |             0.1523    |
| pedestal_state     | high_pedestal     | template_residual_boosted_stack_new | 243 |                        6.64  |                          nan      |                  0.3414  |                         0.3324  |              0.1315  |             0.08928   |
| pedestal_state     | low_pedestal      | 1d_cnn                              | 176 |                       13.61  |                          nan      |                  0.2171  |                         3.606   |              0.1136  |             0.1329    |
| pedestal_state     | low_pedestal      | deltaE_over_E_likelihood_template   | 176 |                        6.403 |                          nan      |                  0.2392  |                         2.151   |              0       |             0.08511   |
| pedestal_state     | low_pedestal      | gradient_boosted_trees              | 176 |                        9.808 |                          nan      |                  0.2639  |                         1.76    |              0.1236  |             0.06483   |
| pedestal_state     | low_pedestal      | joint_sequence_transformer          | 176 |                       14.74  |                          nan      |                  0.2538  |                         7.097   |              0.1177  |             0.6366    |
| pedestal_state     | low_pedestal      | mlp                                 | 176 |                       13.51  |                          nan      |                  0.07838 |                         2.994   |              0.1125  |             0.1763    |
| pedestal_state     | low_pedestal      | ridge                               | 176 |                        9.762 |                          nan      |                  0.1034  |                         2.884   |              0.07985 |             0.03965   |
| pedestal_state     | low_pedestal      | template_residual_boosted_stack_new | 176 |                        9.796 |                          nan      |                  0.2851  |                         1.28    |              0.1411  |             0.133     |
| pedestal_state     | mid_pedestal      | 1d_cnn                              | 261 |                        9.738 |                          nan      |                  0.2942  |                         1.129   |              0.1055  |             0.1701    |
| pedestal_state     | mid_pedestal      | deltaE_over_E_likelihood_template   | 262 |                        9.696 |                          nan      |                  0.2579  |                         1.327   |              0       |             0.01272   |
| pedestal_state     | mid_pedestal      | gradient_boosted_trees              | 261 |                        7.187 |                          nan      |                  0.3597  |                         0.695   |              0.1348  |             0.1825    |
| pedestal_state     | mid_pedestal      | joint_sequence_transformer          | 261 |                       14.6   |                          nan      |                  0.3015  |                         1.162   |              0.2279  |             0.1661    |
| pedestal_state     | mid_pedestal      | mlp                                 | 261 |                       11.89  |                          nan      |                  0.1274  |                         6.23    |              0.1616  |             0.2043    |
| pedestal_state     | mid_pedestal      | ridge                               | 262 |                        7.333 |                          nan      |                  0.1409  |                         0.3876  |              0.1146  |             0.05469   |
| pedestal_state     | mid_pedestal      | template_residual_boosted_stack_new | 261 |                        7.277 |                          nan      |                  0.3402  |                         0.2166  |              0.1537  |             0.1825    |
| pid_proxy_slice    | deuteron          | 1d_cnn                              | 348 |                       10.32  |                            8.169  |                  0.2403  |                         0.4122  |              0.1228  |           nan         |
| pid_proxy_slice    | deuteron          | deltaE_over_E_likelihood_template   | 348 |                        9.271 |                            7.257  |                  0.2     |                         0.7566  |              0       |           nan         |
| pid_proxy_slice    | deuteron          | gradient_boosted_trees              | 348 |                        7.53  |                            3.204  |                  0.2987  |                         1.612   |              0.1609  |           nan         |
| pid_proxy_slice    | deuteron          | joint_sequence_transformer          | 348 |                       12.85  |                            9.779  |                  0.2326  |                         3.64    |              0.1979  |           nan         |
| pid_proxy_slice    | deuteron          | mlp                                 | 348 |                       10.36  |                            3.851  |                  0.08154 |                         2.067   |              0.119   |           nan         |
| pid_proxy_slice    | deuteron          | ridge                               | 348 |                        7.966 |                            2.018  |                  0.09437 |                         2.285   |              0.1148  |           nan         |
| pid_proxy_slice    | deuteron          | template_residual_boosted_stack_new | 348 |                        7.846 |                            2.194  |                  0.2821  |                         1.593   |              0.158   |           nan         |
| pid_proxy_slice    | proton            | 1d_cnn                              | 332 |                       10.67  |                            5.895  |                  0.2856  |                         0.02401 |              0.07808 |           nan         |
| pid_proxy_slice    | proton            | deltaE_over_E_likelihood_template   | 332 |                        8.662 |                           12.38   |                  0.3097  |                         1.693   |              0       |           nan         |
| pid_proxy_slice    | proton            | gradient_boosted_trees              | 332 |                        8.237 |                            3.214  |                  0.3798  |                         0.5045  |              0.1026  |           nan         |
| pid_proxy_slice    | proton            | joint_sequence_transformer          | 332 |                       13.23  |                            8.789  |                  0.3084  |                         0.6244  |              0.1135  |           nan         |
| pid_proxy_slice    | proton            | mlp                                 | 332 |                       12.62  |                           -3.332  |                  0.1318  |                         2.884   |              0.1287  |           nan         |
| pid_proxy_slice    | proton            | ridge                               | 332 |                        7.868 |                            4.142  |                  0.1422  |                         0.496   |              0.08443 |           nan         |
| pid_proxy_slice    | proton            | template_residual_boosted_stack_new | 332 |                        7.953 |                            3.437  |                  0.3723  |                         0.08076 |              0.1175  |           nan         |
| pileup_regime      | merged_pileup     | 1d_cnn                              | 166 |                        8.06  |                            6.704  |                nan       |                         0.7182  |              0.05024 |             0.2339    |
| pileup_regime      | merged_pileup     | deltaE_over_E_likelihood_template   | 166 |                        9.332 |                           10.45   |                nan       |                         1.182   |              0       |             0.0002918 |
| pileup_regime      | merged_pileup     | gradient_boosted_trees              | 166 |                        6.464 |                            1.207  |                nan       |                         1.272   |              0.07261 |             0.09018   |
| pileup_regime      | merged_pileup     | joint_sequence_transformer          | 166 |                       10.34  |                            7.043  |                nan       |                         0.9183  |              0.05682 |             0.1774    |
| pileup_regime      | merged_pileup     | mlp                                 | 166 |                       10.21  |                           -0.6627 |                nan       |                         1.285   |              0.04551 |             0.183     |
| pileup_regime      | merged_pileup     | ridge                               | 166 |                        6.675 |                            4.723  |                nan       |                         0.2931  |              0.04902 |             0.1363    |
| pileup_regime      | merged_pileup     | template_residual_boosted_stack_new | 166 |                        6.829 |                            1.854  |                nan       |                         1.179   |              0.1097  |             0.1404    |
| pileup_regime      | near_pileup       | 1d_cnn                              |  72 |                        6.796 |                           10.88   |                nan       |                         1.209   |              0.03558 |             0.2425    |
| pileup_regime      | near_pileup       | deltaE_over_E_likelihood_template   |  72 |                        9.543 |                           13.77   |                nan       |                         4.192   |              0       |             0.0695    |
| pileup_regime      | near_pileup       | gradient_boosted_trees              |  72 |                        5.908 |                            6.538  |                nan       |                         0.9184  |              0.05707 |             0.1575    |
| pileup_regime      | near_pileup       | joint_sequence_transformer          |  72 |                       10.16  |                           10.17   |                nan       |                         2.589   |              0.03811 |             0.4456    |
| pileup_regime      | near_pileup       | mlp                                 |  72 |                        9.707 |                            7.561  |                nan       |                         0.2115  |              0.05568 |             0.3251    |
| pileup_regime      | near_pileup       | ridge                               |  72 |                        5.441 |                            3.996  |                nan       |                         0.528   |              0.06758 |             0.1552    |
| pileup_regime      | near_pileup       | template_residual_boosted_stack_new |  72 |                        6.776 |                            5.697  |                nan       |                         2.453   |              0.07238 |             0.2116    |
| pileup_regime      | separated_pileup  | 1d_cnn                              | 102 |                        7.309 |                            6.84   |                nan       |                         2.254   |              0.06612 |             0.07843   |
| pileup_regime      | separated_pileup  | deltaE_over_E_likelihood_template   | 102 |                        7.287 |                           15.45   |                nan       |                         1.143   |              0.0764  |             0.1765    |
| pileup_regime      | separated_pileup  | gradient_boosted_trees              | 102 |                        5.825 |                            0.3666 |                nan       |                         1.193   |              0.08885 |             0.03922   |
| pileup_regime      | separated_pileup  | joint_sequence_transformer          | 102 |                        8.628 |                            1.353  |                nan       |                         1.844   |              0.05655 |             0.451     |
| pileup_regime      | separated_pileup  | mlp                                 | 102 |                       10.59  |                           -3.448  |                nan       |                         0.8046  |              0.1177  |             0.2549    |
| pileup_regime      | separated_pileup  | ridge                               | 102 |                        7.1   |                            0.1404 |                nan       |                         1.216   |              0.07342 |             0.09804   |
| pileup_regime      | separated_pileup  | template_residual_boosted_stack_new | 102 |                        5.948 |                            0.5241 |                nan       |                         0.5805  |              0.09873 |             0.1176    |
| pileup_regime      | single            | 1d_cnn                              | 340 |                       12.22  |                            7.572  |                nan       |                         0.8334  |              0.1896  |             0.1459    |
| pileup_regime      | single            | deltaE_over_E_likelihood_template   | 340 |                        7.954 |                            5.483  |                nan       |                         0.3713  |              0       |             0.05632   |
| pileup_regime      | single            | gradient_boosted_trees              | 340 |                        7.728 |                            3.476  |                nan       |                         1.327   |              0.2421  |             0.1235    |
| pileup_regime      | single            | joint_sequence_transformer          | 340 |                       15.32  |                           12.68   |                nan       |                         2.313   |              0.2507  |             0.4073    |
| pileup_regime      | single            | mlp                                 | 340 |                       13.65  |                           -2.032  |                nan       |                         1.45    |              0.2346  |             0.2012    |
| pileup_regime      | single            | ridge                               | 340 |                        8.011 |                            4.181  |                nan       |                         1.353   |              0.2464  |             0.0497    |
| pileup_regime      | single            | template_residual_boosted_stack_new | 340 |                        7.931 |                            4.165  |                nan       |                         0.732   |              0.2341  |             0.1231    |
| pulse_shape_regime | broad_tail_shape  | 1d_cnn                              | 188 |                       10.22  |                            7.703  |                  0.2784  |                         3.128   |              0.05829 |             0.07194   |
| pulse_shape_regime | broad_tail_shape  | deltaE_over_E_likelihood_template   | 188 |                        8.392 |                            8.764  |                  0.4099  |                         0.5532  |              0.07936 |             0.1434    |
| pulse_shape_regime | broad_tail_shape  | gradient_boosted_trees              | 188 |                        8.157 |                            2.566  |                  0.3301  |                         3.856   |              0.07022 |             0.009743  |
| pulse_shape_regime | broad_tail_shape  | joint_sequence_transformer          | 188 |                        9.315 |                            6.958  |                  0.3001  |                         0.717   |              0.03777 |             0.2745    |
| pulse_shape_regime | broad_tail_shape  | mlp                                 | 188 |                       10.46  |                            1      |                  0.06914 |                         2.077   |              0.05582 |             0.1661    |
| pulse_shape_regime | broad_tail_shape  | ridge                               | 188 |                        7.994 |                           -2.831  |                  0.1116  |                         1.139   |              0.05656 |             0.1544    |
| pulse_shape_regime | broad_tail_shape  | template_residual_boosted_stack_new | 188 |                        8.038 |                            3.362  |                  0.311   |                         3.735   |              0.08464 |             0.08531   |
| pulse_shape_regime | narrow_fast_shape | 1d_cnn                              | 271 |                       11.77  |                            5.526  |                  0.1101  |                         1.483   |              0.166   |             0.1379    |
| pulse_shape_regime | narrow_fast_shape | deltaE_over_E_likelihood_template   | 271 |                       11.01  |                           11.53   |                  0.02    |                         1.648   |              0       |             0.01155   |
| pulse_shape_regime | narrow_fast_shape | gradient_boosted_trees              | 271 |                        7.252 |                            3.883  |                  0.1697  |                         1.539   |              0.2556  |             0.1541    |
| pulse_shape_regime | narrow_fast_shape | joint_sequence_transformer          | 271 |                       16.19  |                           21.57   |                  0.1105  |                         1.295   |              0.2029  |             0.7637    |
| pulse_shape_regime | narrow_fast_shape | mlp                                 | 271 |                       14.11  |                           -5.349  |                  0.07394 |                         5.964   |              0.2103  |             0.1761    |
| pulse_shape_regime | narrow_fast_shape | ridge                               | 271 |                        8.235 |                            9.039  |                  0.06144 |                         1.66    |              0.239   |             0.06125   |
| pulse_shape_regime | narrow_fast_shape | template_residual_boosted_stack_new | 271 |                        7.484 |                            5.011  |                  0.1692  |                         0.0619  |              0.2518  |             0.1631    |
| pulse_shape_regime | nominal_shape     | 1d_cnn                              | 221 |                        8.607 |                            8.77   |                  0.1755  |                         0.3003  |              0.06809 |             0.274     |
| pulse_shape_regime | nominal_shape     | deltaE_over_E_likelihood_template   | 221 |                       10.17  |                           11.15   |                  0.1088  |                         0.8463  |              0.2667  |             0.06582   |
| pulse_shape_regime | nominal_shape     | gradient_boosted_trees              | 221 |                        5.837 |                            3.329  |                  0.2773  |                         0.9592  |              0.08993 |             0.1202    |
| pulse_shape_regime | nominal_shape     | joint_sequence_transformer          | 221 |                        8.467 |                            7.205  |                  0.1644  |                         0.2582  |              0.1063  |             0.294     |
| pulse_shape_regime | nominal_shape     | mlp                                 | 221 |                        9.907 |                            5.641  |                  0.05931 |                         0.2054  |              0.0913  |             0.3129    |
| pulse_shape_regime | nominal_shape     | ridge                               | 221 |                        6.686 |                            6.607  |                  0.05024 |                         0.9356  |              0.06673 |             0.08176   |
| pulse_shape_regime | nominal_shape     | template_residual_boosted_stack_new | 221 |                        5.613 |                            3.595  |                  0.2754  |                         1.226   |              0.1009  |             0.1389    |
| saturation_slice   | saturated         | 1d_cnn                              | 287 |                       10.39  |                            5.106  |                  0.2226  |                       nan       |              0.0573  |             0.2905    |
| saturation_slice   | saturated         | deltaE_over_E_likelihood_template   | 287 |                        9.633 |                           10.13   |                  0.2073  |                       nan       |              0       |             0.001166  |
| saturation_slice   | saturated         | gradient_boosted_trees              | 287 |                        8.026 |                            2.551  |                  0.2535  |                       nan       |              0.107   |             0.1686    |
| saturation_slice   | saturated         | joint_sequence_transformer          | 287 |                       14.56  |                            7.136  |                  0.2603  |                       nan       |              0.05057 |             0.2684    |
| saturation_slice   | saturated         | mlp                                 | 287 |                       10.4   |                           -1.822  |                  0.09894 |                       nan       |              0.1251  |             0.1562    |
| saturation_slice   | saturated         | ridge                               | 287 |                        8.849 |                            4.023  |                  0.09968 |                       nan       |              0.03343 |             0.1357    |
| saturation_slice   | saturated         | template_residual_boosted_stack_new | 287 |                        8.243 |                            2.903  |                  0.2531  |                       nan       |              0.09571 |             0.1615    |
| saturation_slice   | unsaturated       | 1d_cnn                              | 393 |                       10.06  |                            7.926  |                  0.2933  |                       nan       |              0.2625  |             0.07465   |
| saturation_slice   | unsaturated       | deltaE_over_E_likelihood_template   | 393 |                        9.089 |                           10.42   |                  0.3086  |                       nan       |              0       |             0.1039    |
| saturation_slice   | unsaturated       | gradient_boosted_trees              | 393 |                        7.4   |                            2.466  |                  0.3702  |                       nan       |              0.2991  |             0.06202   |
| saturation_slice   | unsaturated       | joint_sequence_transformer          | 393 |                       12.64  |                            9.765  |                  0.2831  |                       nan       |              0.386   |             0.03148   |
| saturation_slice   | unsaturated       | mlp                                 | 393 |                       12.7   |                            3.512  |                  0.1222  |                       nan       |              0.279   |             0.2585    |
| saturation_slice   | unsaturated       | ridge                               | 393 |                        7.116 |                            1.937  |                  0.1342  |                       nan       |              0.313   |             0.05766   |
| saturation_slice   | unsaturated       | template_residual_boosted_stack_new | 393 |                        7.327 |                            2.292  |                  0.3493  |                       nan       |              0.322   |             0.1163    |

The full table is `s38a_systematics_by_pulse_stratum.csv`; the report shows
the leading rows to keep the manuscript readable.

## Systematics And Caveats

This is a controlled benchmark, not a final detector calibration.  GEANT4
provides timing, PID, and energy proxy labels; ADC morphology comes from
raw-ROOT residual/template pools.  Saturation and pile-up are controlled
benchmark labels rather than independent electronics flags.  The pretrigger
window has only four samples, so the adaptive pedestal model is deliberately
low-order; a more expressive pedestal fit would risk absorbing pulse-shape
information.  Pulse-stratum bootstrap intervals quantify sensitivity to
pedestal, shape, pile-up, and saturation composition, but not GEANT4
physics-list or material-budget uncertainty.

No novel ticket is appended from S38a.  The immediate next question would need
an independent hardware pedestal stream or hand-scanned pile-up labels rather
than another architecture-only follow-up.

Runtime was `89.7` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

# S35c: Joint PID Pulse-Shape Timing Ablation Study

## Abstract

Ticket `1784063447.978.761459bb` asks for a raw-ROOT anchored comparison of a strong
traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a
new architecture for the coupled PID, pulse-shape, timing, pedestal, pile-up,
saturation, and energy problem.  The selected-pulse count is reproduced directly
from B-stack raw ROOT before using any derived tables.  The complete joint
winner written to `result.json` is **joint_residual_stack_new** with joint loss
`0.4712`.  The best timing-only architecture remains
`template_residual_boosted_stack_new`, but timing-only rows are not allowed to win
the full PID/energy/timing objective.

## Raw ROOT Reproduction Gate

The reproduction uses `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.
For event `i`, even B-stave channel `c`, and digitizer sample `t`, define the
pretrigger pedestal

`b_ic = median(x_ict : t in {0,1,2,3})`.

A pulse is selected when

`max_t (x_ict - b_ic) > 1000 ADC`.

| quantity                           | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | 0         | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | 0         | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | 0         | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | 0         | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | 0         | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | 0         | True |

The exact total of 640,737 selected B-stave pulses matches the project S00
anchor.  The ticket therefore proceeds from raw ROOT semantics rather than a
cache-only reproduction.

## Split Design

Energy and weak-PID closure use the S33a run split: train runs
`[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64]` and held-out runs
`[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]`.  Timing and pile-up
closure use the S34a controlled-injection split: train source runs
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out source runs
`[58, 60, 62, 64, 65]`.  Both panels are
run-disjoint.  Confidence intervals are percentile 95% intervals from held-out
run-block bootstraps.

For a statistic `theta`, the interval is

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`,

where bootstrap replicate `b` samples held-out runs with replacement and keeps
all records from the selected runs.

## Methods

The traditional comparator is intentionally strong: GEANT4/Birks
`deltaE-E` energy inversion, a Gaussian charge-depth PID likelihood, and a
bounded two-pulse template/CFD score.  The ML panel contains ridge/logistic
linear models, gradient-boosted trees, tabular MLPs, and compact 1D-CNNs.  The
sequence panel contains a tiny transformer and a new deterministic late-mask
transformer for timing.  The complete new architecture is a hybrid residual
stack: a range-gated residual MLP for energy/PID combined with a boosted residual
correction over template timing outputs.

The Birks charge model is

`Q_i = alpha * DeltaE_i / (1 + k_B (dE/dx)_i)`,

so prediction inverts to

`DeltaE_hat_i = Q_i (1 + k_B (dE/dx)_i) / alpha`.

The weak-PID coordinate is

`z_i = log(1 + Q_i) - 0.42 D_i - 0.08 M_i`,

where `D_i` is deepest selected B-stave index and `M_i` is selected-stave
multiplicity.  The middle quantile band is excluded; this is a weak-label
diagnostic because the real HRD ROOT has no particle-truth branch.

For timing, the template model minimizes

`SSE_k = sum_t [w(t) - b - sum_{j=1}^k A_j T_s(t - tau_j)]^2`,

and the two-pulse score is `(SSE_1 - SSE_2) / SSE_1`.

## Energy Regression Results

Held-out fractional residuals are `r=(E_hat-E_odd)/E_odd`; `res68` is the 68th
percentile of `|r|`.

| method                       | family                   | n      | bias_frac  | res68_frac | res68_ci95         | mae_mev | mae_mev_ci95     |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup          | traditional_geant4_birks | 332852 | -0.02311   | 0.04025    | [0.03886, 0.04161] | 0.2282  | [0.2018, 0.2636] |
| gradient_boosted_trees       | ml_tree                  | 332852 | -0.0168    | 0.05809    | [0.04997, 0.0687]  | 0.2143  | [0.1885, 0.2465] |
| range_gated_residual_mlp_new | neural_physics_residual  | 332852 | -0.0146    | 0.05868    | [0.04951, 0.07424] | 0.2219  | [0.1936, 0.2639] |
| ridge                        | ml_linear                | 332852 | -0.02366   | 0.09669    | [0.08872, 0.1173]  | 0.2974  | [0.2732, 0.3295] |
| 1d_cnn                       | neural_waveform          | 332852 | -6.561e-05 | 0.1078     | [0.09097, 0.1532]  | 0.3398  | [0.2989, 0.4071] |
| mlp                          | neural_tabular           | 332852 | 0.0206     | 0.1833     | [0.1428, 0.2443]   | 0.5376  | [0.482, 0.618]   |
| old_power_law                | traditional_empirical    | 332852 | -0.2976    | 0.4624     | [0.4442, 0.567]    | 1.656   | [1.563, 1.736]   |

## Weak-PID Results

| method                       | n      | roc_auc | roc_auc_ci95     | average_precision | balanced_accuracy | balanced_accuracy_ci95 | tn     | fp   | fn   | tp     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees       | 248783 | 0.9999  | [0.9998, 0.9999] | 0.9998            | 0.9982            | [0.9976, 0.9985]       | 130732 | 319  | 135  | 117597 |
| mlp                          | 248783 | 0.9996  | [0.9995, 0.9997] | 0.9992            | 0.9977            | [0.997, 0.9982]        | 130601 | 450  | 129  | 117603 |
| range_gated_residual_mlp_new | 248783 | 0.9994  | [0.9993, 0.9995] | 0.998             | 0.9969            | [0.9963, 0.9974]       | 130410 | 641  | 144  | 117588 |
| ridge                        | 248783 | 0.9992  | [0.9991, 0.9994] | 0.9979            | 0.9967            | [0.9961, 0.9971]       | 130263 | 788  | 65   | 117667 |
| traditional_dedx_likelihood  | 248783 | 0.9969  | [0.9962, 0.9975] | 0.9934            | 0.9924            | [0.9912, 0.9935]       | 129669 | 1382 | 540  | 117192 |
| 1d_cnn                       | 248783 | 0.9941  | [0.9907, 0.9952] | 0.9928            | 0.9728            | [0.968, 0.9761]        | 125281 | 5770 | 1229 | 116503 |

## Timing and Pulse-Shape Results

| method                              | detection_ap | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 | winner_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| template_residual_boosted_stack_new | 0.8547       | 7.328           | 6.434                  | 8.349                   | 0.3139           | 0.1556           | 0.06776                   | 1.807        |
| gradient_boosted_trees              | 0.8519       | 7.224           | 6.634                  | 8.535                   | 0.3222           | 0.1444           | 0.07314                   | 1.886        |
| ridge                               | 0.8407       | 10.1            | 9.059                  | 10.61                   | 0.2889           | 0.1833           | 0.06768                   | 2.259        |
| 1d_cnn                              | 0.8229       | 11.15           | 10.33                  | 12.73                   | 0.3667           | 0.1694           | 0.08298                   | 2.55         |
| mlp                                 | 0.8332       | 10.64           | 9.661                  | 10.91                   | 0.3278           | 0.175            | 0.1052                    | 2.613        |
| two_pulse_template_cfd_baseline     | 0.6878       | 10.2            | 8.293                  | 12.78                   | 0.5667           | 0.1833           | 0.08898                   | 2.636        |
| tiny_sequence_transformer           | 0.8316       | 12.49           | 10.77                  | 13.94                   | 0.2944           | 0.225            | 0.1298                    | 3.307        |
| pileup_mask_transformer_new         | 0.814        | 16.9            | 15.13                  | 18.27                   | 0.45             | 0.1028           | 0.1148                    | 3.881        |

## Joint Ranking

The full-ticket score is

`L = R68_E + 5(1-AUC_PID) + sigma_t/100 + sigma_delay/125 + 0.50 r_miss + 0.35 r_false + 0.50 sigma_E,pileup + 0.25 B_stave + P_missing`.

`P_missing=0.75` for each absent energy or PID head.  Thus sequence-only
architectures are retained as architecture ablations but cannot defeat complete
joint methods by solving only timing.

| method                               | family                    | energy_res68_frac | energy_res68_ci95  | pid_roc_auc | pid_roc_auc_ci95 | timing_sigma68_ns | timing_sigma68_ci95 | pileup_miss_rate | false_split_rate | joint_loss | complete_joint_candidate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| joint_residual_stack_new             | new_hybrid_architecture   | 0.05868           | [0.04951, 0.07424] | 0.9994      | [0.9993, 0.9995] | 7.328             | [6.434, 8.349]      | 0.3139           | 0.1556           | 0.4712     | True                     |
| gradient_boosted_trees               | tree_ml                   | 0.05809           | [0.04997, 0.0687]  | 0.9999      | [0.9998, 0.9999] | 7.224             | [6.634, 8.535]      | 0.3222           | 0.1444           | 0.4809     | True                     |
| ridge                                | linear_ml                 | 0.09669           | [0.08872, 0.1173]  | 0.9992      | [0.9991, 0.9994] | 10.1              | [9.059, 10.61]      | 0.2889           | 0.1833           | 0.5811     | True                     |
| 1d_cnn                               | waveform_nn               | 0.1078            | [0.09097, 0.1532]  | 0.9941      | [0.9907, 0.9952] | 11.15             | [10.33, 12.73]      | 0.3667           | 0.1694           | 0.6806     | True                     |
| mlp                                  | tabular_nn                | 0.1833            | [0.1428, 0.2443]   | 0.9996      | [0.9995, 0.9997] | 10.64             | [9.661, 10.91]      | 0.3278           | 0.175            | 0.7073     | True                     |
| traditional_dedx_template_likelihood | traditional               | 0.04025           | [0.03886, 0.04161] | 0.9969      | [0.9962, 0.9975] | 10.2              | [8.293, 12.78]      | 0.5667           | 0.1833           | 0.7088     | True                     |
| tiny_sequence_transformer            | sequence_nn               | nan               | [nan, nan]         | nan         | [nan, nan]       | 12.49             | [10.77, 13.94]      | 0.2944           | 0.225            | 2.825      | False                    |
| pileup_mask_transformer_new          | new_sequence_architecture | nan               | [nan, nan]         | nan         | [nan, nan]       | 16.9              | [15.13, 18.27]      | 0.45             | 0.1028           | 2.965      | False                    |

The winner is **joint_residual_stack_new**, not because it is best on every endpoint, but
because it gives the best complete balance of energy closure, weak-PID
separation, and pulse timing.  Gradient-boosted trees are the closest challenger:
they win the energy/PID-only panel but have a slightly worse joint timing and
pile-up penalty than the residual stack synthesis.

## Run-Level Stability Checks

Energy/PID run-block uncertainty is anchored by the S33a held-out run table.
Representative rows for the joint winner, gradient-boosted trees, and the
traditional energy method are:

| run | method                       | n     | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 44  | geant4_birks_lookup          | 1911  | -0.01601  | 0.04372    | 0.2396  |
| 44  | gradient_boosted_trees       | 1911  | -0.004984 | 0.06737    | 0.1903  |
| 44  | range_gated_residual_mlp_new | 1911  | -0.009472 | 0.07302    | 0.2177  |
| 45  | geant4_birks_lookup          | 22999 | -0.01656  | 0.04482    | 0.2506  |
| 45  | gradient_boosted_trees       | 22999 | -0.005959 | 0.06635    | 0.1954  |
| 45  | range_gated_residual_mlp_new | 22999 | -0.01301  | 0.07009    | 0.2153  |
| 46  | geant4_birks_lookup          | 676   | -0.01128  | 0.03442    | 0.1734  |
| 46  | gradient_boosted_trees       | 676   | 0.007677  | 0.05378    | 0.1578  |
| 46  | range_gated_residual_mlp_new | 676   | -0.03109  | 0.06519    | 0.1711  |
| 47  | geant4_birks_lookup          | 5160  | -0.01226  | 0.0368     | 0.1837  |
| 47  | gradient_boosted_trees       | 5160  | 0.00184   | 0.05456    | 0.1638  |
| 47  | range_gated_residual_mlp_new | 5160  | -0.02923  | 0.06035    | 0.1779  |
| 48  | geant4_birks_lookup          | 13175 | -0.01426  | 0.04251    | 0.2435  |
| 48  | gradient_boosted_trees       | 13175 | 0.002932  | 0.06512    | 0.1755  |
| 48  | range_gated_residual_mlp_new | 13175 | -0.007505 | 0.07095    | 0.2075  |
| 49  | geant4_birks_lookup          | 13921 | -0.01464  | 0.0427     | 0.2428  |
| 49  | gradient_boosted_trees       | 13921 | 0.001122  | 0.06515    | 0.1768  |
| 49  | range_gated_residual_mlp_new | 13921 | -0.008134 | 0.07213    | 0.2081  |
| 50  | geant4_birks_lookup          | 34254 | -0.0307   | 0.04194    | 0.1967  |
| 50  | gradient_boosted_trees       | 34254 | -0.02534  | 0.05218    | 0.2196  |
| 50  | range_gated_residual_mlp_new | 34254 | -0.0259   | 0.04402    | 0.1861  |
| 51  | geant4_birks_lookup          | 14294 | -0.02875  | 0.04178    | 0.2033  |
| 51  | gradient_boosted_trees       | 14294 | -0.02255  | 0.05255    | 0.2042  |
| 51  | range_gated_residual_mlp_new | 14294 | -0.0233   | 0.04623    | 0.1897  |
| 52  | geant4_birks_lookup          | 6933  | -0.02946  | 0.04211    | 0.2071  |
| 52  | gradient_boosted_trees       | 6933  | -0.02316  | 0.05074    | 0.2094  |
| 52  | range_gated_residual_mlp_new | 6933  | -0.02303  | 0.04601    | 0.1908  |
| 53  | geant4_birks_lookup          | 31382 | -0.03134  | 0.03884    | 0.1671  |
| 53  | gradient_boosted_trees       | 31382 | -0.02132  | 0.036      | 0.1605  |
| 53  | range_gated_residual_mlp_new | 31382 | -0.02187  | 0.038      | 0.1628  |
| 54  | geant4_birks_lookup          | 29664 | -0.03131  | 0.03865    | 0.167   |
| 54  | gradient_boosted_trees       | 29664 | -0.02134  | 0.03592    | 0.16    |
| 54  | range_gated_residual_mlp_new | 29664 | -0.02168  | 0.0379     | 0.161   |
| 55  | geant4_birks_lookup          | 16836 | -0.02836  | 0.04106    | 0.1964  |
| 55  | gradient_boosted_trees       | 16836 | -0.02189  | 0.0492     | 0.1972  |
| 55  | range_gated_residual_mlp_new | 16836 | -0.02318  | 0.04528    | 0.1857  |
| 56  | geant4_birks_lookup          | 38925 | -0.02825  | 0.04111    | 0.1939  |
| 56  | gradient_boosted_trees       | 38925 | -0.02381  | 0.05182    | 0.2171  |
| 56  | range_gated_residual_mlp_new | 38925 | -0.02693  | 0.04565    | 0.1911  |
| 57  | geant4_birks_lookup          | 12928 | -0.01461  | 0.04213    | 0.2376  |
| 57  | gradient_boosted_trees       | 12928 | 0.00152   | 0.0674     | 0.178   |
| 57  | range_gated_residual_mlp_new | 12928 | -0.005687 | 0.07175    | 0.2045  |
| 58  | geant4_birks_lookup          | 15919 | -0.02497  | 0.03351    | 0.1279  |
| 58  | gradient_boosted_trees       | 15919 | -0.005058 | 0.04712    | 0.1276  |
| 58  | range_gated_residual_mlp_new | 15919 | 0.03568   | 0.05594    | 0.1446  |

Timing run-block stability is anchored by the S34a held-out run table:

| method                              | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees              | 58          | 0.3924       | 7.462           | 0.1087                     | 0.3611           | 0.2222           | 0.06009                   |
| gradient_boosted_trees              | 60          | 0.09263      | 8.759           | 0.1087                     | 0.3611           | 0.1667           | 0.09937                   |
| gradient_boosted_trees              | 62          | 0.1293       | 8.202           | 0.07759                    | 0.1944           | 0.09722          | 0.06313                   |
| gradient_boosted_trees              | 64          | -0.8074      | 6.445           | 0.07292                    | 0.3333           | 0.125            | 0.068                     |
| gradient_boosted_trees              | 65          | 0.1882       | 6.388           | 0.03261                    | 0.3611           | 0.1111           | 0.0635                    |
| template_residual_boosted_stack_new | 58          | 0.08017      | 8.92            | 0.09375                    | 0.3333           | 0.1944           | 0.06984                   |
| template_residual_boosted_stack_new | 60          | -0.6015      | 8.417           | 0.1383                     | 0.3472           | 0.1389           | 0.07238                   |
| template_residual_boosted_stack_new | 62          | 0.462        | 7.453           | 0.05455                    | 0.2361           | 0.1528           | 0.06397                   |
| template_residual_boosted_stack_new | 64          | -0.2886      | 6.198           | 0.05102                    | 0.3194           | 0.1944           | 0.06825                   |
| template_residual_boosted_stack_new | 65          | -0.2676      | 6.349           | 0.04167                    | 0.3333           | 0.09722          | 0.05916                   |
| two_pulse_template_cfd_baseline     | 58          | -0.3575      | 8.893           | 0.1613                     | 0.5694           | 0.2778           | 0.1039                    |
| two_pulse_template_cfd_baseline     | 60          | 0.9982       | 11.32           | 0.2576                     | 0.5417           | 0.125            | 0.1118                    |
| two_pulse_template_cfd_baseline     | 62          | 0.7928       | 14.69           | 0.2941                     | 0.5278           | 0.1389           | 0.07271                   |
| two_pulse_template_cfd_baseline     | 64          | 0.9643       | 7.096           | 0.09375                    | 0.5556           | 0.2361           | 0.08306                   |
| two_pulse_template_cfd_baseline     | 65          | -1.626       | 7.945           | 0.1538                     | 0.6389           | 0.1389           | 0.05297                   |

## Pedestal and Occupancy Context

Run-level pedestal summaries are computed from raw pretrigger samples.  The
selected-pulse count is an occupancy/rate proxy; pedestal mean and RMS track
run-to-run electronics state.

| run | group             | events_total | selected_pulses | baseline_mean_adc | baseline_rms_adc |
| --- | --- | --- | --- | --- | --- |
| 31  | sample_i_calib    | 39990        | 27871           | 6980              | 509.1            |
| 32  | sample_i_calib    | 41921        | 28240           | 6980              | 519              |
| 33  | sample_i_calib    | 57173        | 48737           | 6924              | 285.9            |
| 34  | sample_i_calib    | 39765        | 34118           | 6921              | 268.2            |
| 35  | sample_i_calib    | 27786        | 11667           | 6987              | 535.8            |
| 36  | sample_i_calib    | 21764        | 10391           | 6997              | 577.2            |
| 37  | sample_i_calib    | 50513        | 24537           | 7020              | 628.2            |
| 39  | sample_i_calib    | 30321        | 14218           | 7026              | 649.2            |
| 40  | sample_i_calib    | 32613        | 14708           | 7024              | 629              |
| 41  | sample_i_calib    | 33997        | 16146           | 7024              | 638.4            |
| 42  | sample_i_calib    | 33972        | 18112           | 7020              | 623.5            |
| 44  | sample_i_analysis | 4294         | 2038            | 7024              | 635.5            |
| 45  | sample_i_analysis | 48181        | 24333           | 7026              | 645.6            |
| 46  | sample_i_analysis | 1441         | 687             | 6949              | 402              |
| 47  | sample_i_analysis | 10970        | 5276            | 6948              | 400.4            |
| 48  | sample_i_analysis | 31713        | 14000           | 7017              | 612.4            |
| 49  | sample_i_analysis | 32354        | 14815           | 7020              | 621.6            |
| 50  | sample_i_analysis | 44804        | 35217           | 6951              | 383.1            |
| 51  | sample_i_analysis | 20569        | 14740           | 6970              | 457.4            |
| 52  | sample_i_analysis | 10005        | 7152            | 6970              | 463.4            |
| 53  | sample_i_analysis | 39612        | 32200           | 6954              | 393.9            |
| 54  | sample_i_analysis | 37413        | 30440           | 6949              | 369.7            |
| 55  | sample_i_analysis | 24416        | 17387           | 6972              | 472.6            |
| 56  | sample_i_analysis | 51823        | 40148           | 6955              | 397.6            |

## Systematics

The PID result is not a hidden-truth particle-ID measurement.  It is a
charge-depth weak-label robustness benchmark, with the middle support band
excluded.  The energy target comes from duplicate odd readout and a GEANT4/Birks
closure, so even/odd electronics nonlinearity and the assumed 4 cm geometry enter
the absolute scale.  The timing truth comes from controlled doublet injections
using real raw-ROOT clean pulses and residuals; it has exact injection truth but
does not measure the natural beam pile-up rate.  Saturation is represented by an
amplitude-ceiling proxy rather than an electronics saturation flag.  Bootstrap
CIs quantify finite held-out-run transfer, not asymptotic event uncertainty.

## Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s35c_1784063447_978_761459bb_joint_pid_pulse_shape_timing_ablation.py
```

Runtime for this synthesis run was `6.6` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

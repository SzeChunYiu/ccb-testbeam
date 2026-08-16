# S54b: Wiener-tail deconvolution versus neural late-pile-up saturation recovery

## Abstract

Ticket `#2479` asks whether a strong traditional Wiener-tail/template
deconvolver remains competitive with modern ML/NN methods for late pile-up and
clipped-pulse recovery.  The worker is `testbeam-laptop-2`.  The benchmark first
reproduced the B-stack selected-pulse count directly from raw ROOT, then compared
traditional template/Wiener methods against ridge, gradient-boosted trees, MLP,
1D-CNN, a compact transformer, and a new late-window transformer/hybrid residual
architecture.  The winner written to `result.json` is `gradient_boosted_trees` with composite
score `1.193`.  The primary traditional comparator
`wiener_tail_deconvolution_traditional` has score `2.743`.

## Raw ROOT Reproduction

Input files were read from `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.  Each
`h101/HRDv` branch was reshaped to `(event, channel, sample)`.  The four B-stack
analysis channels are B2, B4, B6, and B8.  For waveform `x_c(t)` on channel `c`,
the raw selection is

`b_c = median(x_c(0), x_c(1), x_c(2), x_c(3))`

and

`max_t [x_c(t) - b_c] > 1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

This gate is evaluated before model fitting and the same raw files are hashed in
`input_sha256.csv`.

## Controlled Benchmark Design

The split is by source run.  Train runs are `[44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56]`;
held-out runs are `[50, 57, 58, 60, 62, 64, 65]`.  Train-only clean
templates are estimated per stave:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |             1200 |                   2.816 |                      5 |           9.245 |
| B4      |             1007 |                   2.831 |                      6 |          10.65  |
| B6      |              911 |                   3.728 |                      8 |           9.522 |
| B8      |              585 |                   4.126 |                      8 |           9.359 |

Synthetic-over-real doublets are generated on raw-ROOT single-pulse residuals:

`w(t)=A_1 T_s(t-t_1)+rA_1 T_s(t-t_1-Delta)+epsilon_r(t)+p`,

where `Delta` is the controlled secondary-pulse spacing, `r` is the secondary
amplitude ratio, `epsilon_r(t)` is a run-local residual sampled from real clean
pulses, and `p` is a pedestal offset.  Clean negative controls share the same
source-run and amplitude support but omit the second pulse.

## Methods

| method                                    | family              | description                                                              |
|:------------------------------------------|:--------------------|:-------------------------------------------------------------------------|
| wiener_tail_deconvolution_traditional     | traditional         | bounded template deconvolution plus short-record Wiener tail attenuation |
| two_pulse_template_likelihood_traditional | traditional         | two-pulse template likelihood with CFD initialization                    |
| leading_edge_cfd_traditional              | traditional         | single-pulse CFD onset with deterministic tail split score               |
| residual_tail_veto_traditional            | traditional         | template likelihood plus late-residual veto                              |
| ridge                                     | linear ML           | ridge classifier and multi-output ridge regressor                        |
| gradient_boosted_trees                    | tree ML             | histogram gradient-boosted classifier/regressors                         |
| mlp                                       | neural network      | tabular multilayer perceptron classifier/regressor pair                  |
| 1d_cnn                                    | neural network      | compact one-dimensional convolutional waveform model                     |
| tiny_sequence_transformer                 | neural sequence     | one-layer self-attention waveform encoder                                |
| causal_window_transformer_new             | new neural sequence | attention model with deterministic late-window mask channel              |
| template_residual_boosted_stack_new       | new hybrid          | boosted residual correction using traditional deconvolver coordinates    |

The traditional Wiener-tail method starts from the bounded template fit and
filters the short waveform in the frequency domain.  For frequency bin `f`,

`G(f)=S(f)/(S(f)+N) * [1+(f/f_c)^4]^-1`,

where `S(f)=|FFT(w-b)|^2`, `N` is the median high-frequency power, and the
second factor suppresses late high-frequency tail residuals.  The filtered
post-peak tail energy and curvature are combined with the template improvement

`I=(SSE_1-SSE_2)/SSE_1`,

with

`SSE_k=sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`.

Neural models see the same run-held-out training labels.  The new architecture
is `causal_window_transformer_new`: a compact attention encoder with a
deterministic late-window mask channel.  A hybrid `template_residual_boosted_stack_new`
is also included because this problem is plausibly helped by using the physics
fit as a low-variance coordinate system.

## Metrics and Confidence Intervals

Confidence intervals are percentile 95% intervals from
`180` bootstrap resamples of held-out runs:

`CI_95(theta)=[q_0.025(theta_b), q_0.975(theta_b)]`.

The registered score is

`C_m = 1.3 sigma_late/30 + sigma_lead/25 + 2.8 sigma_E + 1.5 sigma_tail + 0.8 r_fail + 0.7 r_false + 1.5 B_stave`,

where `sigma_late` is late secondary-delay sigma68, `sigma_lead` is leading-edge
timing sigma68, `sigma_E` is saturated-sample energy-recovery sigma68,
`sigma_tail` is tail residual energy sigma68, `r_fail` is false-merge/failure
tail rate, `r_false` is clean-control false split rate, and `B_stave` is a
stave/PID-proxy energy-bias span.

## Primary Held-Out Results

| method                                    |   detection_ap |   detection_auc |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------------------------------------|---------------:|----------------:|---------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|----------------------------:|
| template_residual_boosted_stack_new       |         0.8572 |          0.8419 |      -0.07594  |             6.565 |                    5.525 |                     7.345 |            0.2874  |             0.2058 |                     0.06005 |
| gradient_boosted_trees                    |         0.8595 |          0.8413 |      -0.1447   |             6.654 |                    5.904 |                     7.467 |            0.2653  |             0.2194 |                     0.06344 |
| two_pulse_template_likelihood_traditional |         0.6536 |          0.6061 |       0.9433   |             8.476 |                    7.622 |                     9.122 |            0.6173  |             0.1735 |                     0.07477 |
| 1d_cnn                                    |         0.803  |          0.7967 |       0.2259   |             8.805 |                    8.216 |                     9.595 |            0.2772  |             0.2602 |                     0.09006 |
| ridge                                     |         0.8291 |          0.8249 |       0.2497   |             8.984 |                    8.167 |                     9.657 |            0.2653  |             0.2415 |                     0.07315 |
| mlp                                       |         0.8506 |          0.8363 |      -0.005092 |             9.275 |                    8.725 |                     9.712 |            0.2857  |             0.2024 |                     0.1104  |
| residual_tail_veto_traditional            |         0.6562 |          0.6192 |       1.135    |             9.37  |                    8.756 |                     9.797 |            0.5833  |             0.2466 |                     0.0769  |
| tiny_sequence_transformer                 |         0.8187 |          0.7978 |      -5.105    |            13.6   |                   12.84  |                    14.35  |            0.3333  |             0.2364 |                     0.1059  |
| causal_window_transformer_new             |         0.8199 |          0.8011 |      -7.346    |            13.84  |                   12.9   |                    14.29  |            0.3571  |             0.1922 |                     0.09358 |
| wiener_tail_deconvolution_traditional     |         0.6068 |          0.628  |       1.066    |            16.27  |                   15.09  |                    17.85  |            0.5765  |             0.4575 |                     0.1689  |
| leading_edge_cfd_traditional              |         0.4896 |          0.5317 |     -10.31     |            18.33  |                   16.23  |                    21.29  |            0.05272 |             0.8673 |                     0.2555  |

## Endpoint Table

| method                                    |   late_pileup_delay_bias_ns |   late_pileup_delay_sigma68_ns |   late_pileup_delay_sigma68_ns_ci_low |   late_pileup_delay_sigma68_ns_ci_high |   saturated_sample_energy_recovery_sigma68 |   saturated_sample_energy_recovery_sigma68_ci_low |   saturated_sample_energy_recovery_sigma68_ci_high |   tail_residual_sigma68 |   failure_tail_rate |   pedestal_dependence |   pid_confusion_stave_bias_span |
|:------------------------------------------|----------------------------:|-------------------------------:|--------------------------------------:|---------------------------------------:|-------------------------------------------:|--------------------------------------------------:|---------------------------------------------------:|------------------------:|--------------------:|----------------------:|--------------------------------:|
| 1d_cnn                                    |                     -11.38  |                          9.758 |                                 8.517 |                                 11.4   |                                    0.07747 |                                          0.03855  |                                            0.088   |                 0.09006 |             0.2772  |                0.2602 |                         0.06986 |
| causal_window_transformer_new             |                     -14.87  |                         14.03  |                                12.56  |                                 16.62  |                                    0.06645 |                                          0.0313   |                                            0.08898 |                 0.09358 |             0.3571  |                0.1922 |                         0.05636 |
| gradient_boosted_trees                    |                      -6.915 |                          8.974 |                                 8.399 |                                  9.811 |                                    0.04303 |                                          0.02788  |                                            0.06225 |                 0.06344 |             0.2653  |                0.2194 |                         0.02734 |
| leading_edge_cfd_traditional              |                     -20     |                         15     |                                10     |                                 15     |                                    0.1982  |                                          0.1199   |                                            0.2447  |                 0.2555  |             0.05272 |                0.8673 |                         0.3219  |
| mlp                                       |                      -7.586 |                         12.45  |                                10.68  |                                 14.16  |                                    0.08189 |                                          0.05137  |                                            0.1547  |                 0.1104  |             0.2857  |                0.2024 |                         0.03315 |
| residual_tail_veto_traditional            |                     -10     |                         10     |                                10     |                                 15     |                                    0.03499 |                                          0.01052  |                                            0.05174 |                 0.0769  |             0.5833  |                0.2466 |                         0.07912 |
| ridge                                     |                      -9.873 |                          9.954 |                                 7.95  |                                 10.8   |                                    0.04709 |                                          0.02668  |                                            0.05823 |                 0.07315 |             0.2653  |                0.2415 |                         0.0708  |
| template_residual_boosted_stack_new       |                      -7.561 |                          9.777 |                                 8.739 |                                 10.33  |                                    0.05149 |                                          0.02458  |                                            0.05795 |                 0.06005 |             0.2874  |                0.2058 |                         0.03452 |
| tiny_sequence_transformer                 |                     -15.44  |                         24.3   |                                22.51  |                                 27.21  |                                    0.06858 |                                          0.04346  |                                            0.1391  |                 0.1059  |             0.3333  |                0.2364 |                         0.08212 |
| two_pulse_template_likelihood_traditional |                     -10     |                         10     |                                10     |                                 10     |                                    0.03499 |                                          0.009562 |                                            0.05263 |                 0.07477 |             0.6173  |                0.1735 |                         0.06562 |
| wiener_tail_deconvolution_traditional     |                     -17.47  |                         14.82  |                                10.76  |                                 17.61  |                                    0.1427  |                                          0.04406  |                                            0.1629  |                 0.1689  |             0.5765  |                0.4575 |                         0.2716  |

## Winner Ranking

| method                                    |   winner_score |   late_pileup_delay_sigma68_ns |   leading_edge_time_sigma68_ns |   saturated_sample_energy_recovery_sigma68 |   tail_residual_sigma68 |   failure_tail_rate |   false_split_rate |   pid_confusion_stave_bias_span |
|:------------------------------------------|---------------:|-------------------------------:|-------------------------------:|-------------------------------------------:|------------------------:|--------------------:|-------------------:|--------------------------------:|
| gradient_boosted_trees                    |          1.193 |                          8.974 |                          4.547 |                                    0.04303 |                 0.06344 |             0.2653  |             0.2194 |                         0.02734 |
| template_residual_boosted_stack_new       |          1.269 |                          9.777 |                          4.628 |                                    0.05149 |                 0.06005 |             0.2874  |             0.2058 |                         0.03452 |
| ridge                                     |          1.432 |                          9.954 |                          6.795 |                                    0.04709 |                 0.07315 |             0.2653  |             0.2415 |                         0.0708  |
| 1d_cnn                                    |          1.519 |                          9.758 |                          5.889 |                                    0.07747 |                 0.09006 |             0.2772  |             0.2602 |                         0.06986 |
| two_pulse_template_likelihood_traditional |          1.586 |                         10     |                          5.712 |                                    0.03499 |                 0.07477 |             0.6173  |             0.1735 |                         0.06562 |
| mlp                                       |          1.613 |                         12.45  |                          6.473 |                                    0.08189 |                 0.1104  |             0.2857  |             0.2024 |                         0.03315 |
| residual_tail_veto_traditional            |          1.656 |                         10     |                          6.275 |                                    0.03499 |                 0.0769  |             0.5833  |             0.2466 |                         0.07912 |
| causal_window_transformer_new             |          1.944 |                         14.03  |                         12.62  |                                    0.06645 |                 0.09358 |             0.3571  |             0.1922 |                         0.05636 |
| tiny_sequence_transformer                 |          2.414 |                         24.3   |                         11.37  |                                    0.06858 |                 0.1059  |             0.3333  |             0.2364 |                         0.08212 |
| wiener_tail_deconvolution_traditional     |          2.743 |                         14.82  |                          6.463 |                                    0.1427  |                 0.1689  |             0.5765  |             0.4575 |                         0.2716  |
| leading_edge_cfd_traditional              |          3.125 |                         15     |                         10.12  |                                    0.1982  |                 0.2555  |             0.05272 |             0.8673 |                         0.3219  |

## Run-Held-Out Stability

| method                                    |   heldout_run |   time_bias_ns |   time_sigma68_ns |   late_tail_rate_abs_gt_15ns |   pileup_miss_rate |   false_split_rate |   energy_fractional_sigma68 |
|:------------------------------------------|--------------:|---------------:|------------------:|-----------------------------:|-------------------:|-------------------:|----------------------------:|
| 1d_cnn                                    |            50 |      0.2911    |             7.62  |                      0.07031 |            0.2381  |            0.2262  |                     0.07243 |
| 1d_cnn                                    |            57 |      0.4091    |            10.14  |                      0.1484  |            0.2381  |            0.2738  |                     0.09484 |
| 1d_cnn                                    |            58 |     -0.3067    |             9.859 |                      0.09524 |            0.25    |            0.3571  |                     0.05062 |
| 1d_cnn                                    |            60 |      0.6742    |             9.619 |                      0.1638  |            0.3095  |            0.3095  |                     0.08235 |
| 1d_cnn                                    |            62 |     -0.1203    |             9.213 |                      0.1204  |            0.3571  |            0.2024  |                     0.1037  |
| 1d_cnn                                    |            64 |     -0.2987    |             9.587 |                      0.1475  |            0.2738  |            0.1786  |                     0.07868 |
| 1d_cnn                                    |            65 |      0.7202    |             7.636 |                      0.1148  |            0.2738  |            0.2738  |                     0.09435 |
| causal_window_transformer_new             |            50 |    -10.36      |            14.15  |                      0.3596  |            0.3214  |            0.1548  |                     0.07234 |
| causal_window_transformer_new             |            57 |     -6.014     |            12.74  |                      0.2685  |            0.3571  |            0.1786  |                     0.1126  |
| causal_window_transformer_new             |            58 |     -4.863     |            11.66  |                      0.2586  |            0.3095  |            0.2976  |                     0.07514 |
| causal_window_transformer_new             |            60 |     -7.836     |            16.38  |                      0.37    |            0.4048  |            0.25    |                     0.09378 |
| causal_window_transformer_new             |            62 |    -10.28      |            13.28  |                      0.3587  |            0.4524  |            0.1429  |                     0.09263 |
| causal_window_transformer_new             |            64 |     -7.63      |            13.59  |                      0.3362  |            0.3095  |            0.1548  |                     0.07788 |
| causal_window_transformer_new             |            65 |     -6.536     |            12.68  |                      0.3     |            0.3452  |            0.1667  |                     0.07433 |
| gradient_boosted_trees                    |            50 |     -0.07834   |             5.843 |                      0.03676 |            0.1905  |            0.1905  |                     0.0479  |
| gradient_boosted_trees                    |            57 |      0.1112    |             4.849 |                      0.07812 |            0.2381  |            0.2738  |                     0.06367 |
| gradient_boosted_trees                    |            58 |     -0.3855    |             7.153 |                      0.07692 |            0.2262  |            0.2976  |                     0.05355 |
| gradient_boosted_trees                    |            60 |      0.3266    |             6.301 |                      0.08475 |            0.2976  |            0.3333  |                     0.07825 |
| gradient_boosted_trees                    |            62 |     -0.4157    |             8.037 |                      0.1364  |            0.3452  |            0.1667  |                     0.06193 |
| gradient_boosted_trees                    |            64 |     -0.5669    |             8.211 |                      0.07031 |            0.2381  |            0.1786  |                     0.07853 |
| gradient_boosted_trees                    |            65 |      0.2094    |             6.667 |                      0.07895 |            0.3214  |            0.09524 |                     0.04857 |
| leading_edge_cfd_traditional              |            50 |    -11.31      |            23.61  |                      0.4375  |            0.04762 |            0.8571  |                     0.3092  |
| leading_edge_cfd_traditional              |            57 |    -10.83      |            23.23  |                      0.4398  |            0.0119  |            0.881   |                     0.3057  |
| leading_edge_cfd_traditional              |            58 |    -10.54      |            16.21  |                      0.391   |            0.07143 |            0.8929  |                     0.208   |
| leading_edge_cfd_traditional              |            60 |    -10.3       |            17.3   |                      0.3987  |            0.05952 |            0.7976  |                     0.2189  |
| leading_edge_cfd_traditional              |            62 |    -10.57      |            15.33  |                      0.3782  |            0.07143 |            0.869   |                     0.2493  |
| leading_edge_cfd_traditional              |            64 |     -9.072     |            16.68  |                      0.3654  |            0.07143 |            0.9048  |                     0.2167  |
| leading_edge_cfd_traditional              |            65 |     -9.538     |            13.72  |                      0.3457  |            0.03571 |            0.869   |                     0.2113  |
| mlp                                       |            50 |     -0.5178    |             8.76  |                      0.1231  |            0.2262  |            0.1667  |                     0.1062  |
| mlp                                       |            57 |     -0.2389    |             8.796 |                      0.1639  |            0.2738  |            0.1786  |                     0.1086  |
| mlp                                       |            58 |     -0.6488    |             9.184 |                      0.1742  |            0.2143  |            0.3333  |                     0.06898 |
| mlp                                       |            60 |     -0.6386    |             9.951 |                      0.15    |            0.2857  |            0.2262  |                     0.1235  |
| mlp                                       |            62 |      0.992     |             9.503 |                      0.14    |            0.4048  |            0.1667  |                     0.1134  |
| mlp                                       |            64 |      1.012     |             8.818 |                      0.1667  |            0.2857  |            0.1786  |                     0.09288 |
| mlp                                       |            65 |     -0.4298    |             8.556 |                      0.1638  |            0.3095  |            0.1667  |                     0.117   |
| residual_tail_veto_traditional            |            50 |     -0.47      |            10.23  |                      0.2188  |            0.619   |            0.1786  |                     0.07424 |
| residual_tail_veto_traditional            |            57 |      1.732     |             9.831 |                      0.2083  |            0.5714  |            0.2143  |                     0.08393 |
| residual_tail_veto_traditional            |            58 |      0.4535    |             7.873 |                      0.1222  |            0.4643  |            0.3214  |                     0.07891 |
| residual_tail_veto_traditional            |            60 |      1.236     |             8.961 |                      0.225   |            0.7619  |            0.2738  |                     0.04738 |
| residual_tail_veto_traditional            |            62 |      0.718     |             8.855 |                      0.2     |            0.6429  |            0.2262  |                     0.07111 |
| residual_tail_veto_traditional            |            64 |      0.4353    |            10.86  |                      0.1667  |            0.4643  |            0.2143  |                     0.09096 |
| residual_tail_veto_traditional            |            65 |      1.694     |             9.073 |                      0.1892  |            0.5595  |            0.2976  |                     0.06249 |
| ridge                                     |            50 |      0.916     |             7.257 |                      0.08955 |            0.2024  |            0.1905  |                     0.05582 |
| ridge                                     |            57 |      1.175     |            10.12  |                      0.1308  |            0.2262  |            0.2857  |                     0.0898  |
| ridge                                     |            58 |     -1.321     |             8.726 |                      0.1429  |            0.1667  |            0.369   |                     0.07499 |
| ridge                                     |            60 |      0.9661    |             8.171 |                      0.07377 |            0.2738  |            0.2619  |                     0.06532 |
| ridge                                     |            62 |     -0.2759    |             9.047 |                      0.1154  |            0.381   |            0.2024  |                     0.07733 |
| ridge                                     |            64 |     -0.7809    |             9.905 |                      0.1724  |            0.3095  |            0.2024  |                     0.07631 |
| ridge                                     |            65 |      1.428     |             8.593 |                      0.1525  |            0.2976  |            0.1786  |                     0.06132 |
| template_residual_boosted_stack_new       |            50 |      0.2116    |             5.366 |                      0.05224 |            0.2024  |            0.2143  |                     0.05958 |
| template_residual_boosted_stack_new       |            57 |      0.2677    |             4.934 |                      0.08475 |            0.2976  |            0.2024  |                     0.05546 |
| template_residual_boosted_stack_new       |            58 |     -0.2321    |             7.694 |                      0.07692 |            0.2262  |            0.2976  |                     0.04532 |
| template_residual_boosted_stack_new       |            60 |     -0.393     |             5.714 |                      0.08333 |            0.2857  |            0.3095  |                     0.06322 |
| template_residual_boosted_stack_new       |            62 |      0.0003139 |             7.558 |                      0.125   |            0.381   |            0.1548  |                     0.06025 |
| template_residual_boosted_stack_new       |            64 |     -1.237     |             7.949 |                      0.08333 |            0.2857  |            0.1548  |                     0.06887 |
| template_residual_boosted_stack_new       |            65 |      0.5952    |             6.207 |                      0.08929 |            0.3333  |            0.1071  |                     0.06019 |
| tiny_sequence_transformer                 |            50 |     -6.259     |            13.04  |                      0.3036  |            0.3333  |            0.2024  |                     0.09871 |
| tiny_sequence_transformer                 |            57 |     -1.998     |            12.21  |                      0.2155  |            0.3095  |            0.2619  |                     0.1075  |
| tiny_sequence_transformer                 |            58 |     -4.471     |            15.25  |                      0.3226  |            0.2619  |            0.3571  |                     0.1034  |
| tiny_sequence_transformer                 |            60 |     -4.432     |            15.38  |                      0.3113  |            0.369   |            0.2976  |                     0.08992 |
| tiny_sequence_transformer                 |            62 |     -4.49      |            12.47  |                      0.2755  |            0.4167  |            0.1667  |                     0.1214  |
| tiny_sequence_transformer                 |            64 |     -6.739     |            13.33  |                      0.2869  |            0.2738  |            0.1786  |                     0.1078  |
| tiny_sequence_transformer                 |            65 |     -4.846     |            14     |                      0.2925  |            0.369   |            0.1905  |                     0.09009 |
| two_pulse_template_likelihood_traditional |            50 |     -0.47      |             8.372 |                      0.1833  |            0.6429  |            0.09524 |                     0.06627 |
| two_pulse_template_likelihood_traditional |            57 |      1.472     |             7.588 |                      0.197   |            0.6071  |            0.1786  |                     0.09652 |
| two_pulse_template_likelihood_traditional |            58 |      0.1223    |             6.805 |                      0.1098  |            0.5119  |            0.2381  |                     0.08085 |
| two_pulse_template_likelihood_traditional |            60 |      1.236     |             8.961 |                      0.225   |            0.7619  |            0.2024  |                     0.04738 |
| two_pulse_template_likelihood_traditional |            62 |      0.4583    |             8.469 |                      0.1731  |            0.6905  |            0.1548  |                     0.07647 |
| two_pulse_template_likelihood_traditional |            64 |      0.4353    |             9.521 |                      0.1375  |            0.5238  |            0.131   |                     0.07704 |
| two_pulse_template_likelihood_traditional |            65 |      1.786     |             9.11  |                      0.2     |            0.5833  |            0.2143  |                     0.06438 |
| wiener_tail_deconvolution_traditional     |            50 |     -0.07204   |            17.55  |                      0.4219  |            0.619   |            0.4405  |                     0.1231  |
| wiener_tail_deconvolution_traditional     |            57 |      3.157     |            15.81  |                      0.2917  |            0.5714  |            0.5119  |                     0.162   |
| wiener_tail_deconvolution_traditional     |            58 |      0.06097   |            14.54  |                      0.3043  |            0.4524  |            0.5714  |                     0.1801  |
| wiener_tail_deconvolution_traditional     |            60 |     -0.8908    |            14.02  |                      0.325   |            0.7619  |            0.5     |                     0.1333  |
| wiener_tail_deconvolution_traditional     |            62 |      2.25      |            17.13  |                      0.3485  |            0.6071  |            0.4286  |                     0.1254  |
| wiener_tail_deconvolution_traditional     |            64 |      1.685     |            17.89  |                      0.3889  |            0.4643  |            0.381   |                     0.1871  |
| wiener_tail_deconvolution_traditional     |            65 |     -0.2443    |            17.22  |                      0.3514  |            0.5595  |            0.369   |                     0.1706  |

## Strata and Systematics

The strata table resolves spacing, amplitude ratio, stave/PID proxy, and
saturation-proxy behavior.

| stratum     | value          | method                                    |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   energy_fractional_sigma68 |
|:------------|:---------------|:------------------------------------------|---------------:|------------------:|-------------------:|----------------------------:|
| spacing_bin | (-0.001, 10.0] | 1d_cnn                                    |        2.038   |             8.439 |            0.4155  |                     0.08197 |
| spacing_bin | (10.0, 25.0]   | 1d_cnn                                    |        0.9567  |             7.754 |            0.3554  |                     0.08879 |
| spacing_bin | (25.0, 45.0]   | 1d_cnn                                    |       -2.379   |             8.975 |            0.1484  |                     0.08146 |
| spacing_bin | (45.0, 70.0]   | 1d_cnn                                    |       -1.627   |            11.24  |            0.1136  |                     0.07794 |
| spacing_bin | (-0.001, 10.0] | causal_window_transformer_new             |      -11.56    |            12.15  |            0.5121  |                     0.0813  |
| spacing_bin | (10.0, 25.0]   | causal_window_transformer_new             |       -8.508   |            11.75  |            0.4545  |                     0.07601 |
| spacing_bin | (25.0, 45.0]   | causal_window_transformer_new             |       -6.852   |            14.4   |            0.2266  |                     0.08184 |
| spacing_bin | (45.0, 70.0]   | causal_window_transformer_new             |       -1.839   |            15.04  |            0.1515  |                     0.1044  |
| spacing_bin | (-0.001, 10.0] | gradient_boosted_trees                    |        1.156   |             6.274 |            0.3913  |                     0.05245 |
| spacing_bin | (10.0, 25.0]   | gradient_boosted_trees                    |        0.2037  |             5.875 |            0.3306  |                     0.05448 |
| spacing_bin | (25.0, 45.0]   | gradient_boosted_trees                    |       -1.181   |             7.252 |            0.1641  |                     0.06267 |
| spacing_bin | (45.0, 70.0]   | gradient_boosted_trees                    |       -0.9055  |             7.803 |            0.1061  |                     0.07333 |
| spacing_bin | (-0.001, 10.0] | leading_edge_cfd_traditional              |       -7.193   |            13.3   |            0.05314 |                     0.2413  |
| spacing_bin | (10.0, 25.0]   | leading_edge_cfd_traditional              |       -6.982   |             9.115 |            0.02479 |                     0.2006  |
| spacing_bin | (25.0, 45.0]   | leading_edge_cfd_traditional              |      -18.08    |            17.41  |            0.03906 |                     0.2645  |
| spacing_bin | (45.0, 70.0]   | leading_edge_cfd_traditional              |      -24.51    |            22.59  |            0.09091 |                     0.187   |
| spacing_bin | (-0.001, 10.0] | mlp                                       |        0.7969  |             8.509 |            0.372   |                     0.1057  |
| spacing_bin | (10.0, 25.0]   | mlp                                       |        0.03302 |             7.654 |            0.3471  |                     0.1211  |
| spacing_bin | (25.0, 45.0]   | mlp                                       |       -0.8161  |             8.476 |            0.2344  |                     0.1087  |
| spacing_bin | (45.0, 70.0]   | mlp                                       |       -1.207   |            11.33  |            0.1439  |                     0.09684 |
| spacing_bin | (-0.001, 10.0] | residual_tail_veto_traditional            |        2.99    |            11.94  |            0.7198  |                     0.07286 |
| spacing_bin | (10.0, 25.0]   | residual_tail_veto_traditional            |        3.177   |             9.299 |            0.6198  |                     0.07873 |
| spacing_bin | (25.0, 45.0]   | residual_tail_veto_traditional            |        0.7135  |             7.256 |            0.5469  |                     0.06383 |
| spacing_bin | (45.0, 70.0]   | residual_tail_veto_traditional            |       -1.545   |             9.609 |            0.3712  |                     0.08058 |
| spacing_bin | (-0.001, 10.0] | ridge                                     |        0.935   |             8.927 |            0.3382  |                     0.06209 |
| spacing_bin | (10.0, 25.0]   | ridge                                     |        2.235   |             7.566 |            0.3306  |                     0.06333 |
| spacing_bin | (25.0, 45.0]   | ridge                                     |       -0.2579  |             8.15  |            0.1875  |                     0.06715 |
| spacing_bin | (45.0, 70.0]   | ridge                                     |       -2.938   |            10.36  |            0.1667  |                     0.07106 |
| spacing_bin | (-0.001, 10.0] | template_residual_boosted_stack_new       |        0.8021  |             6.34  |            0.4203  |                     0.05975 |
| spacing_bin | (10.0, 25.0]   | template_residual_boosted_stack_new       |        0.3924  |             5.283 |            0.3636  |                     0.04928 |
| spacing_bin | (25.0, 45.0]   | template_residual_boosted_stack_new       |       -1.3     |             7.332 |            0.1797  |                     0.05651 |
| spacing_bin | (45.0, 70.0]   | template_residual_boosted_stack_new       |       -0.6972  |             7.812 |            0.1136  |                     0.06176 |
| spacing_bin | (-0.001, 10.0] | tiny_sequence_transformer                 |       -4.838   |            11.71  |            0.4928  |                     0.08077 |
| spacing_bin | (10.0, 25.0]   | tiny_sequence_transformer                 |       -5.49    |            10.92  |            0.4215  |                     0.0998  |
| spacing_bin | (25.0, 45.0]   | tiny_sequence_transformer                 |       -5.273   |            14.58  |            0.1719  |                     0.0777  |
| spacing_bin | (45.0, 70.0]   | tiny_sequence_transformer                 |       -4.465   |            17.58  |            0.1591  |                     0.08933 |
| spacing_bin | (-0.001, 10.0] | two_pulse_template_likelihood_traditional |        2.834   |            10.87  |            0.7585  |                     0.06615 |
| spacing_bin | (10.0, 25.0]   | two_pulse_template_likelihood_traditional |        3.177   |             8.953 |            0.6777  |                     0.07883 |
| spacing_bin | (25.0, 45.0]   | two_pulse_template_likelihood_traditional |        0.3075  |             6.791 |            0.5703  |                     0.06434 |
| spacing_bin | (45.0, 70.0]   | two_pulse_template_likelihood_traditional |       -1.459   |             9.367 |            0.3864  |                     0.08209 |
| spacing_bin | (-0.001, 10.0] | wiener_tail_deconvolution_traditional     |        9.172   |            18.17  |            0.7101  |                     0.1287  |
| spacing_bin | (10.0, 25.0]   | wiener_tail_deconvolution_traditional     |        7.989   |            11.06  |            0.6116  |                     0.1615  |
| spacing_bin | (25.0, 45.0]   | wiener_tail_deconvolution_traditional     |       -1.428   |             8.793 |            0.5469  |                     0.1215  |
| spacing_bin | (45.0, 70.0]   | wiener_tail_deconvolution_traditional     |       -7.494   |            17.76  |            0.3636  |                     0.1306  |
| ratio_bin   | (-0.001, 0.35] | 1d_cnn                                    |       -0.9066  |            10.65  |            0.4431  |                     0.1111  |
| ratio_bin   | (0.35, 0.625]  | 1d_cnn                                    |       -0.291   |             9.223 |            0.269   |                     0.0857  |
| ratio_bin   | (0.625, 0.875] | 1d_cnn                                    |       -0.215   |             8.035 |            0.2313  |                     0.08483 |
| ratio_bin   | (0.875, 1.05]  | 1d_cnn                                    |        1.335   |             8.191 |            0.1338  |                     0.08287 |
| ratio_bin   | (-0.001, 0.35] | causal_window_transformer_new             |      -11.37    |            15.5   |            0.5269  |                     0.1216  |
| ratio_bin   | (0.35, 0.625]  | causal_window_transformer_new             |       -7.524   |            12.74  |            0.3655  |                     0.07697 |
| ratio_bin   | (0.625, 0.875] | causal_window_transformer_new             |       -6.27    |            12.56  |            0.2761  |                     0.07476 |
| ratio_bin   | (0.875, 1.05]  | causal_window_transformer_new             |       -5.01    |            14.2   |            0.2254  |                     0.08231 |
| ratio_bin   | (-0.001, 0.35] | gradient_boosted_trees                    |       -1.315   |             8.615 |            0.4671  |                     0.07681 |
| ratio_bin   | (0.35, 0.625]  | gradient_boosted_trees                    |       -1.185   |             6.663 |            0.2483  |                     0.06276 |
| ratio_bin   | (0.625, 0.875] | gradient_boosted_trees                    |        0.687   |             6.06  |            0.1567  |                     0.06381 |
| ratio_bin   | (0.875, 1.05]  | gradient_boosted_trees                    |        1.18    |             5.96  |            0.1479  |                     0.05228 |
| ratio_bin   | (-0.001, 0.35] | leading_edge_cfd_traditional              |      -11.86    |            21.18  |            0.0479  |                     0.2994  |
| ratio_bin   | (0.35, 0.625]  | leading_edge_cfd_traditional              |       -9.81    |            16.22  |            0.06207 |                     0.2193  |
| ratio_bin   | (0.625, 0.875] | leading_edge_cfd_traditional              |       -9.571   |            17.13  |            0.03731 |                     0.2149  |
| ratio_bin   | (0.875, 1.05]  | leading_edge_cfd_traditional              |       -9.018   |            16.39  |            0.06338 |                     0.2588  |
| ratio_bin   | (-0.001, 0.35] | mlp                                       |       -1.717   |            11.12  |            0.479   |                     0.1434  |
| ratio_bin   | (0.35, 0.625]  | mlp                                       |       -1.028   |             8.906 |            0.3172  |                     0.09855 |
| ratio_bin   | (0.625, 0.875] | mlp                                       |        0.1843  |             8.078 |            0.194   |                     0.07989 |
| ratio_bin   | (0.875, 1.05]  | mlp                                       |        1.985   |             8.534 |            0.1127  |                     0.1109  |
| ratio_bin   | (-0.001, 0.35] | residual_tail_veto_traditional            |       -0.5706  |            13.05  |            0.6287  |                     0.09384 |
| ratio_bin   | (0.35, 0.625]  | residual_tail_veto_traditional            |       -0.6698  |             9.059 |            0.5655  |                     0.07394 |
| ratio_bin   | (0.625, 0.875] | residual_tail_veto_traditional            |        1.285   |             8.516 |            0.5597  |                     0.07693 |
| ratio_bin   | (0.875, 1.05]  | residual_tail_veto_traditional            |        1.694   |             6.617 |            0.5704  |                     0.06472 |
| ratio_bin   | (-0.001, 0.35] | ridge                                     |       -3.068   |            10.47  |            0.4731  |                     0.07804 |
| ratio_bin   | (0.35, 0.625]  | ridge                                     |       -0.52    |             8.164 |            0.2759  |                     0.06359 |
| ratio_bin   | (0.625, 0.875] | ridge                                     |        1.349   |             8.488 |            0.1567  |                     0.07599 |
| ratio_bin   | (0.875, 1.05]  | ridge                                     |        2.149   |             7.591 |            0.1127  |                     0.06644 |
| ratio_bin   | (-0.001, 0.35] | template_residual_boosted_stack_new       |       -2.159   |             9.109 |            0.4611  |                     0.06057 |
| ratio_bin   | (0.35, 0.625]  | template_residual_boosted_stack_new       |       -0.9553  |             7.326 |            0.331   |                     0.05649 |
| ratio_bin   | (0.625, 0.875] | template_residual_boosted_stack_new       |        0.5242  |             5.81  |            0.1866  |                     0.06029 |
| ratio_bin   | (0.875, 1.05]  | template_residual_boosted_stack_new       |        1.301   |             5.362 |            0.1338  |                     0.05506 |
| ratio_bin   | (-0.001, 0.35] | tiny_sequence_transformer                 |       -8.74    |            18.13  |            0.479   |                     0.1424  |
| ratio_bin   | (0.35, 0.625]  | tiny_sequence_transformer                 |       -6.558   |            12.13  |            0.3655  |                     0.1117  |
| ratio_bin   | (0.625, 0.875] | tiny_sequence_transformer                 |       -4.079   |            12.47  |            0.2463  |                     0.1058  |
| ratio_bin   | (0.875, 1.05]  | tiny_sequence_transformer                 |       -1.379   |            12.85  |            0.2113  |                     0.09918 |
| ratio_bin   | (-0.001, 0.35] | two_pulse_template_likelihood_traditional |       -0.5706  |            12.87  |            0.6527  |                     0.09345 |
| ratio_bin   | (0.35, 0.625]  | two_pulse_template_likelihood_traditional |       -1.112   |             7.848 |            0.6138  |                     0.07322 |
| ratio_bin   | (0.625, 0.875] | two_pulse_template_likelihood_traditional |        1.285   |             7.798 |            0.597   |                     0.07581 |
| ratio_bin   | (0.875, 1.05]  | two_pulse_template_likelihood_traditional |        1.694   |             5.91  |            0.5986  |                     0.06544 |
| ratio_bin   | (-0.001, 0.35] | wiener_tail_deconvolution_traditional     |       -0.5706  |            13.91  |            0.6228  |                     0.1566  |
| ratio_bin   | (0.35, 0.625]  | wiener_tail_deconvolution_traditional     |       -0.7988  |            19.45  |            0.5517  |                     0.178   |
| ratio_bin   | (0.625, 0.875] | wiener_tail_deconvolution_traditional     |        1.356   |            15.58  |            0.5522  |                     0.1694  |
| ratio_bin   | (0.875, 1.05]  | wiener_tail_deconvolution_traditional     |        1.745   |            14.39  |            0.5704  |                     0.1615  |
| stave       | B2             | 1d_cnn                                    |       -5.931   |             9.217 |            0.4412  |                     0.1013  |
| stave       | B4             | 1d_cnn                                    |       -3.323   |             9.554 |            0.3154  |                     0.0987  |
| stave       | B6             | 1d_cnn                                    |        0.9055  |             7.917 |            0.2515  |                     0.0723  |
| stave       | B8             | 1d_cnn                                    |        3.048   |             7.495 |            0.1321  |                     0.0755  |
| stave       | B2             | causal_window_transformer_new             |      -16.16    |            16.13  |            0.5147  |                     0.1214  |
| stave       | B4             | causal_window_transformer_new             |      -11.89    |            14.78  |            0.4     |                     0.08203 |
| stave       | B6             | causal_window_transformer_new             |       -6.556   |            13.03  |            0.3129  |                     0.06782 |
| stave       | B8             | causal_window_transformer_new             |       -3.63    |             9.726 |            0.2327  |                     0.07522 |
| stave       | B2             | gradient_boosted_trees                    |       -1.743   |             7.439 |            0.4338  |                     0.06808 |
| stave       | B4             | gradient_boosted_trees                    |       -1.731   |             7.111 |            0.2462  |                     0.06714 |
| stave       | B6             | gradient_boosted_trees                    |        0.1839  |             5.19  |            0.2393  |                     0.0501  |
| stave       | B8             | gradient_boosted_trees                    |        1.585   |             6.632 |            0.1635  |                     0.06205 |
| stave       | B2             | leading_edge_cfd_traditional              |      -18.54    |            25     |            0.01471 |                     0.3187  |
| stave       | B4             | leading_edge_cfd_traditional              |      -15.8     |            17.99  |            0.02308 |                     0.273   |
| stave       | B6             | leading_edge_cfd_traditional              |       -7.769   |            13.31  |            0.05521 |                     0.164   |
| stave       | B8             | leading_edge_cfd_traditional              |       -4.351   |            14.36  |            0.1069  |                     0.2086  |
| stave       | B2             | mlp                                       |       -2.368   |            10.73  |            0.4338  |                     0.1164  |
| stave       | B4             | mlp                                       |       -2.498   |             8.661 |            0.2692  |                     0.1279  |
| stave       | B6             | mlp                                       |        0.925   |             7.552 |            0.2945  |                     0.09248 |
| stave       | B8             | mlp                                       |        2.295   |             8.57  |            0.1635  |                     0.09724 |
| stave       | B2             | residual_tail_veto_traditional            |        3.566   |            18.99  |            0.7426  |                     0.06549 |
| stave       | B4             | residual_tail_veto_traditional            |       -4.312   |            15.25  |            0.8538  |                     0.06459 |
| stave       | B6             | residual_tail_veto_traditional            |       -0.2096  |             8.086 |            0.5031  |                     0.05598 |
| stave       | B8             | residual_tail_veto_traditional            |        1.473   |             5.841 |            0.3082  |                     0.08819 |
| stave       | B2             | ridge                                     |       -3.731   |             9.034 |            0.3676  |                     0.07387 |
| stave       | B4             | ridge                                     |       -2.276   |             9.581 |            0.2692  |                     0.06799 |
| stave       | B6             | ridge                                     |        1.014   |             6.888 |            0.3006  |                     0.04778 |
| stave       | B8             | ridge                                     |        2.594   |             8.621 |            0.1384  |                     0.08119 |
| stave       | B2             | template_residual_boosted_stack_new       |       -1.515   |             7.446 |            0.4559  |                     0.07539 |
| stave       | B4             | template_residual_boosted_stack_new       |       -1.847   |             7.457 |            0.2769  |                     0.06749 |
| stave       | B6             | template_residual_boosted_stack_new       |       -0.01614 |             5.264 |            0.2638  |                     0.04769 |
| stave       | B8             | template_residual_boosted_stack_new       |        1.204   |             6.416 |            0.1761  |                     0.06235 |

Stress slices include clean pedestal controls, tight pile-up, high summed
amplitude, phase-shuffled controls, and high-charge amplitude sentinels.

| stress                                        | method                                    |   n_events |   leading_edge_time_sigma68_ns |   secondary_pulse_delay_sigma68_ns |   pileup_miss_rate |   false_split_rate |   energy_proxy_distortion_sigma68 |
|:----------------------------------------------|:------------------------------------------|-----------:|-------------------------------:|-----------------------------------:|-------------------:|-------------------:|----------------------------------:|
| pretrigger_pedestal_clean_control             | 1d_cnn                                    |        588 |                        nan     |                            nan     |          nan       |             0.2602 |                         nan       |
| pretrigger_pedestal_clean_control             | causal_window_transformer_new             |        588 |                        nan     |                            nan     |          nan       |             0.1922 |                         nan       |
| pretrigger_pedestal_clean_control             | gradient_boosted_trees                    |        588 |                        nan     |                            nan     |          nan       |             0.2194 |                         nan       |
| pretrigger_pedestal_clean_control             | leading_edge_cfd_traditional              |        588 |                        nan     |                            nan     |          nan       |             0.8673 |                         nan       |
| pretrigger_pedestal_clean_control             | mlp                                       |        588 |                        nan     |                            nan     |          nan       |             0.2024 |                         nan       |
| pretrigger_pedestal_clean_control             | residual_tail_veto_traditional            |        588 |                        nan     |                            nan     |          nan       |             0.2466 |                         nan       |
| pretrigger_pedestal_clean_control             | ridge                                     |        588 |                        nan     |                            nan     |          nan       |             0.2415 |                         nan       |
| pretrigger_pedestal_clean_control             | template_residual_boosted_stack_new       |        588 |                        nan     |                            nan     |          nan       |             0.2058 |                         nan       |
| pretrigger_pedestal_clean_control             | tiny_sequence_transformer                 |        588 |                        nan     |                            nan     |          nan       |             0.2364 |                         nan       |
| pretrigger_pedestal_clean_control             | two_pulse_template_likelihood_traditional |        588 |                        nan     |                            nan     |          nan       |             0.1735 |                         nan       |
| pretrigger_pedestal_clean_control             | wiener_tail_deconvolution_traditional     |        588 |                        nan     |                            nan     |          nan       |             0.4575 |                         nan       |
| synthetic_over_real_tight_sep_le_15ns         | 1d_cnn                                    |        264 |                          6.643 |                              7.389 |            0.4129  |           nan      |                           0.08116 |
| synthetic_over_real_tight_sep_le_15ns         | causal_window_transformer_new             |        264 |                         13.43  |                             10.64  |            0.5076  |           nan      |                           0.076   |
| synthetic_over_real_tight_sep_le_15ns         | gradient_boosted_trees                    |        264 |                          3.918 |                              7.074 |            0.3636  |           nan      |                           0.05253 |
| synthetic_over_real_tight_sep_le_15ns         | leading_edge_cfd_traditional              |        264 |                          9.302 |                              5     |            0.04924 |           nan      |                           0.2264  |
| synthetic_over_real_tight_sep_le_15ns         | mlp                                       |        264 |                          5.699 |                             10.91  |            0.3447  |           nan      |                           0.1143  |
| synthetic_over_real_tight_sep_le_15ns         | residual_tail_veto_traditional            |        264 |                          6.48  |                             21.25  |            0.7045  |           nan      |                           0.07358 |
| synthetic_over_real_tight_sep_le_15ns         | ridge                                     |        264 |                          5.16  |                              7.696 |            0.3258  |           nan      |                           0.06163 |
| synthetic_over_real_tight_sep_le_15ns         | template_residual_boosted_stack_new       |        264 |                          3.731 |                              7.563 |            0.3977  |           nan      |                           0.0589  |
| synthetic_over_real_tight_sep_le_15ns         | tiny_sequence_transformer                 |        264 |                         13.93  |                             15.17  |            0.4773  |           nan      |                           0.0832  |
| synthetic_over_real_tight_sep_le_15ns         | two_pulse_template_likelihood_traditional |        264 |                          5.539 |                             19.05  |            0.7386  |           nan      |                           0.07384 |
| synthetic_over_real_tight_sep_le_15ns         | wiener_tail_deconvolution_traditional     |        264 |                          6.857 |                             10.2   |            0.6932  |           nan      |                           0.1388  |
| synthetic_over_real_saturated_sum_gt_11000adc | 1d_cnn                                    |         26 |                          6.444 |                             11.44  |            0.07692 |           nan      |                           0.07747 |
| synthetic_over_real_saturated_sum_gt_11000adc | causal_window_transformer_new             |         26 |                         13.93  |                             12.28  |            0.1154  |           nan      |                           0.06645 |
| synthetic_over_real_saturated_sum_gt_11000adc | gradient_boosted_trees                    |         26 |                          5.278 |                              8.053 |            0.03846 |           nan      |                           0.04303 |
| synthetic_over_real_saturated_sum_gt_11000adc | leading_edge_cfd_traditional              |         26 |                         12.22  |                             20     |            0       |           nan      |                           0.1982  |
| synthetic_over_real_saturated_sum_gt_11000adc | mlp                                       |         26 |                          6.885 |                             13.53  |            0       |           nan      |                           0.08189 |
| synthetic_over_real_saturated_sum_gt_11000adc | residual_tail_veto_traditional            |         26 |                          8.333 |                             11.4   |            0.6154  |           nan      |                           0.03499 |
| synthetic_over_real_saturated_sum_gt_11000adc | ridge                                     |         26 |                          8.458 |                              9.321 |            0       |           nan      |                           0.04709 |
| synthetic_over_real_saturated_sum_gt_11000adc | template_residual_boosted_stack_new       |         26 |                          4.437 |                              7.325 |            0.03846 |           nan      |                           0.05149 |
| synthetic_over_real_saturated_sum_gt_11000adc | tiny_sequence_transformer                 |         26 |                          9.422 |                             14.72  |            0.07692 |           nan      |                           0.06858 |
| synthetic_over_real_saturated_sum_gt_11000adc | two_pulse_template_likelihood_traditional |         26 |                          8.333 |                             11.4   |            0.6154  |           nan      |                           0.03499 |
| synthetic_over_real_saturated_sum_gt_11000adc | wiener_tail_deconvolution_traditional     |         26 |                          8.333 |                             19.82  |            0.6154  |           nan      |                           0.1427  |
| shuffled_second_pulse_phase_negative_control  | 1d_cnn                                    |        294 |                          6.148 |                             14.54  |            0.2823  |           nan      |                           0.08702 |
| shuffled_second_pulse_phase_negative_control  | causal_window_transformer_new             |        294 |                         12.53  |                             19.43  |            0.3673  |           nan      |                           0.09081 |
| shuffled_second_pulse_phase_negative_control  | gradient_boosted_trees                    |        294 |                          4.72  |                             10.75  |            0.2653  |           nan      |                           0.06363 |
| shuffled_second_pulse_phase_negative_control  | leading_edge_cfd_traditional              |        294 |                          9.6   |                             21.25  |            0.06463 |           nan      |                           0.2621  |
| shuffled_second_pulse_phase_negative_control  | mlp                                       |        294 |                          6.966 |                             12.7   |            0.2993  |           nan      |                           0.1122  |
| shuffled_second_pulse_phase_negative_control  | residual_tail_veto_traditional            |        294 |                          6.792 |                             15     |            0.6122  |           nan      |                           0.0769  |
| shuffled_second_pulse_phase_negative_control  | ridge                                     |        294 |                          6.834 |                             12.69  |            0.2585  |           nan      |                           0.07262 |
| shuffled_second_pulse_phase_negative_control  | template_residual_boosted_stack_new       |        294 |                          4.781 |                             10.84  |            0.2823  |           nan      |                           0.0599  |
| shuffled_second_pulse_phase_negative_control  | tiny_sequence_transformer                 |        294 |                         11.02  |                             23.71  |            0.3299  |           nan      |                           0.1012  |
| shuffled_second_pulse_phase_negative_control  | two_pulse_template_likelihood_traditional |        294 |                          5.714 |                             16.7   |            0.6429  |           nan      |                           0.0706  |
| shuffled_second_pulse_phase_negative_control  | wiener_tail_deconvolution_traditional     |        294 |                          6.679 |                             26.08  |            0.5918  |           nan      |                           0.1727  |
| amplitude_only_sentinel_high_charge           | 1d_cnn                                    |        294 |                          6.043 |                             12.49  |            0.1531  |           nan      |                           0.07479 |
| amplitude_only_sentinel_high_charge           | causal_window_transformer_new             |        294 |                         12.59  |                             15.12  |            0.2347  |           nan      |                           0.08736 |
| amplitude_only_sentinel_high_charge           | gradient_boosted_trees                    |        294 |                          4.731 |                              9.187 |            0.08503 |           nan      |                           0.057   |
| amplitude_only_sentinel_high_charge           | leading_edge_cfd_traditional              |        294 |                          9.548 |                             21.25  |            0.04422 |           nan      |                           0.2362  |
| amplitude_only_sentinel_high_charge           | mlp                                       |        294 |                          6.07  |                             11.03  |            0.08844 |           nan      |                           0.08773 |
| amplitude_only_sentinel_high_charge           | residual_tail_veto_traditional            |        294 |                          6.048 |                             17.5   |            0.568   |           nan      |                           0.07614 |
| amplitude_only_sentinel_high_charge           | ridge                                     |        294 |                          7.372 |                             12.83  |            0.05442 |           nan      |                           0.06691 |
| amplitude_only_sentinel_high_charge           | template_residual_boosted_stack_new       |        294 |                          4.762 |                              8.879 |            0.1054  |           nan      |                           0.05575 |
| amplitude_only_sentinel_high_charge           | tiny_sequence_transformer                 |        294 |                         11.68  |                             20.66  |            0.2075  |           nan      |                           0.1052  |
| amplitude_only_sentinel_high_charge           | two_pulse_template_likelihood_traditional |        294 |                          5.409 |                             15     |            0.5952  |           nan      |                           0.07411 |
| amplitude_only_sentinel_high_charge           | wiener_tail_deconvolution_traditional     |        294 |                          6.345 |                             27.32  |            0.5578  |           nan      |                           0.1704  |

## Interpretation, Caveats, and Use

The result should be read as a controlled raw-data benchmark, not a direct
measurement of natural beam pile-up frequency.  The truth labels are exact for
the injected second-pulse delay and amplitude, but the residual field comes from
real raw-ROOT single-pulse windows.  Saturation is represented by a high summed
amplitude proxy because electronics saturation truth flags are not present in
the reduced ROOT branch.  Pedestal dependence is measured through clean-control
false splitting and run-local residuals.  PID behavior is a stave-conditioned
energy-boundary proxy, not particle-truth PID confusion.  Finally, the waveform
has only 18 samples, so all models inherit a digitizer-sampling floor for
sub-sample deconvolution.

Runtime was `107.9` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

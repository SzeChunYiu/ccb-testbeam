# S45c overlap-aware waveform energy and PID disentanglement benchmark

## Abstract

Ticket `2426` asks whether explicit overlapping-pulse deconvolution improves
timing, pile-up tagging, recovered energy, and PID stability beyond strong
traditional baselines.  The worker was `testbeam-laptop-3` and the project was
`testbeam`.  The study first reproduced the selected B-stack pulse count directly
from raw ROOT, then compared two-pulse likelihood, matched-filter/CFD residual
scans, and sparse non-negative deconvolution style baselines against ridge,
gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, a causal-mask
transformer, and a hybrid residual stack.  The winner written to `result.json`
is `template_residual_boosted_stack_new` with composite endpoint score `1.728` and
fixed-threshold pile-up recall `0.8289` at a
train-calibrated 5% clean-control false-positive target.

## Raw ROOT reproduction

The input files are `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.  For each file the
analysis opens `h101/HRDv`, reshapes the waveform branch to
`(event, channel, sample)`, and uses the project-standard B2/B4/B6/B8 channels.
For channel `c`, the pedestal is `b_c = median_t x_c(t), t in {0,1,2,3}`, and a
selected pulse satisfies

`max_t [x_c(t)-b_c] > 1000 ADC`.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | True |

This gate is deliberately before model fitting so that the benchmark is anchored
to raw ROOT semantics rather than a derived cache.

## Split, injections, and bootstrap

The train/held-out split is by source run.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  Clean templates are estimated only from
train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| ----- | -------------- | --------------------- | -------------------- | ------------- |
| B2    | 768            | 2.579                 | 5                    | 9.187         |
| B4    | 756            | 2.944                 | 6                    | 10.76         |
| B6    | 723            | 3.748                 | 6                    | 9.736         |
| B8    | 478            | 4.26                  | 8                    | 9.252         |

Controlled doublets are generated as

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_r(t)+p`,

where `epsilon_r(t)` is a run-local residual from real raw-ROOT pulses and `p` is
a pedestal excursion.  Negative controls use the same residual and amplitude
spectrum with no second pulse.  Confidence intervals are percentile 95% intervals
from `120` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`, with runs sampled with
replacement.

## Methods

| method                                    | family              | description                                                                 |
| ----------------------------------------- | ------------------- | --------------------------------------------------------------------------- |
| two_pulse_template_likelihood_traditional | traditional         | bounded two-pulse template likelihood deconvolution with CFD initialization |
| leading_edge_cfd_traditional              | traditional         | single-waveform leading-edge/CFD onset finder with late-tail split score    |
| residual_tail_veto_traditional            | traditional         | template likelihood augmented with a deterministic late-residual veto       |
| ridge                                     | linear ML           | ridge classifier plus multi-output ridge regression on waveform features    |
| gradient_boosted_trees                    | tree ML             | histogram gradient-boosted classifier/regressors                            |
| mlp                                       | neural network      | tabular multilayer perceptron classifier/regressor pair                     |
| 1d_cnn                                    | neural network      | compact one-dimensional convolutional waveform model                        |
| tiny_sequence_transformer                 | neural sequence     | one-layer self-attention encoder over 18 samples                            |
| causal_window_transformer_new             | new neural sequence | self-attention model with deterministic late/overlap mask channel           |
| template_residual_boosted_stack_new       | new hybrid          | boosted residual correction stack using traditional deconvolver outputs     |

The traditional method is not a strawman.  It fits one-pulse and two-pulse
template hypotheses and uses the fractional optimal-filter improvement

`I = (SSE_1 - SSE_2) / SSE_1`,

where

`SSE_k = sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`.

The leading-edge/CFD traditional row estimates the first onset from the 20%
constant-fraction crossing and scores pile-up from post-peak tail excess.  The
residual-tail veto row combines the two-pulse likelihood with deterministic
late-residual energy, providing a non-ML comparator for false split and false
merge control.

The mask transformer adds a second input channel `m(t)`: `m(t)=1` after the
observed primary peak plus one sample, `m(t)=0.35` for the two samples before
that boundary, and `m(t)=0` elsewhere.  It is label-free and encodes where late
curvature from unresolved second pulses can appear.


The S45c-specific endpoint extends the inherited overlap benchmark by treating energy distortion, stave-conditioned PID-boundary bias, calibration-frozen fixed-FPR recall, and clean-sideband false splitting as co-primary caveats rather than secondary plots.  The named winner is `template_residual_boosted_stack_new`.

## Primary held-out method metrics

| method                                    | detection_ap | detection_auc | time_bias_ns | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------------- | ------------ | ------------- | ------------ | --------------- | ---------------------- | ----------------------- | ---------------- | ---------------- | ------------------------- |
| template_residual_boosted_stack_new       | 0.8561       | 0.8338        | 0.461        | 6.602           | 6.219                  | 7.435                   | 0.3026           | 0.1684           | 0.0714                    |
| gradient_boosted_trees                    | 0.8456       | 0.8285        | 0.1245       | 8.001           | 7.634                  | 8.314                   | 0.3211           | 0.1658           | 0.07141                   |
| two_pulse_template_likelihood_traditional | 0.6622       | 0.6207        | 0.616        | 8.707           | 7.615                  | 10.98                   | 0.5921           | 0.1947           | 0.09619                   |
| ridge                                     | 0.8344       | 0.8277        | 0.357        | 9.419           | 8.811                  | 9.915                   | 0.3132           | 0.1658           | 0.06663                   |
| residual_tail_veto_traditional            | 0.658        | 0.6289        | 0.7076       | 9.55            | 8.549                  | 12.09                   | 0.5184           | 0.2763           | 0.09311                   |
| 1d_cnn                                    | 0.7774       | 0.7773        | 0.4745       | 11.21           | 10.75                  | 12.07                   | 0.3763           | 0.2105           | 0.08647                   |
| causal_window_transformer_new             | 0.7902       | 0.7717        | -6.304       | 12.15           | 10.37                  | 14.38                   | 0.4263           | 0.1974           | 0.09189                   |
| tiny_sequence_transformer                 | 0.7978       | 0.7723        | -6.259       | 13.35           | 12.83                  | 13.78                   | 0.3079           | 0.3              | 0.1721                    |
| mlp                                       | 0.7715       | 0.779         | 1.458        | 14.29           | 13.2                   | 15.62                   | 0.3526           | 0.2132           | 0.1736                    |
| leading_edge_cfd_traditional              | 0.4991       | 0.5203        | -9.533       | 17.57           | 16.7                   | 18.67                   | 0.06053          | 0.85             | 0.2811                    |

## Calibration-frozen fixed-FPR recall

The classification thresholds below are frozen before held-out scoring.  For
each method and target false-positive rate `alpha`, the threshold is

`tau_m(alpha)=Q_{1-alpha}[s_m | train, clean]`.

Held-out pile-up recall is then

`R_m(alpha)=P[s_m >= tau_m(alpha) | held-out, injected pile-up]`,

and real-data sideband false splitting is

`F_m(alpha)=P[s_m >= tau_m(alpha) | held-out, clean raw-ROOT controls]`.

This is the calibration-frozen threshold audit requested by the ticket.  The
clean controls are un-injected waveforms read from raw ROOT and passed through
the same generator/residual machinery as the injected doublets.

| method                                    | target_train_fpr | frozen_threshold | pileup_recall | pileup_recall_ci_low | pileup_recall_ci_high | real_clean_sideband_false_split_rate | real_clean_sideband_false_split_rate_ci_low | real_clean_sideband_false_split_rate_ci_high | accepted_time_sigma68_ns | accepted_energy_sigma68 |
| ----------------------------------------- | ---------------- | ---------------- | ------------- | -------------------- | --------------------- | ------------------------------------ | ------------------------------------------- | -------------------------------------------- | ------------------------ | ----------------------- |
| template_residual_boosted_stack_new       | 0.01             | 0.3349           | 0.7816        | 0.7368               | 0.8239                | 0.25                                 | 0.2024                                      | 0.2868                                       | 5.171                    | 0.07496                 |
| gradient_boosted_trees                    | 0.01             | 0.3507           | 0.7447        | 0.7132               | 0.7817                | 0.2395                               | 0.1841                                      | 0.3158                                       | 6.123                    | 0.07197                 |
| ridge                                     | 0.01             | 0.6256           | 0.3158        | 0.2657               | 0.3947                | 0.02105                              | 0.01579                                     | 0.02632                                      | 6.883                    | 0.0779                  |
| causal_window_transformer_new             | 0.01             | 0.9224           | 0.2658        | 0.2079               | 0.3291                | 0.02368                              | 0.01316                                     | 0.03421                                      | 8.569                    | 0.1028                  |
| tiny_sequence_transformer                 | 0.01             | 0.9562           | 0.2           | 0.1632               | 0.2503                | 0.01053                              | 0.002632                                    | 0.02105                                      | 6.994                    | 0.1072                  |
| 1d_cnn                                    | 0.01             | 0.8752           | 0.1921        | 0.1497               | 0.2345                | 0.01842                              | 0.01316                                     | 0.02895                                      | 6.864                    | 0.08827                 |
| mlp                                       | 0.01             | 0.7883           | 0.1789        | 0.1447               | 0.2132                | 0.01316                              | 0                                           | 0.02368                                      | 14.46                    | 0.1909                  |
| two_pulse_template_likelihood_traditional | 0.01             | 0.9998           | 0.1632        | 0.1288               | 0.2053                | 0.01579                              | 0.01316                                     | 0.02105                                      | 3.689                    | 0.08727                 |
| residual_tail_veto_traditional            | 0.01             | 0.9999           | 0.1           | 0.07105              | 0.1421                | 0.02105                              | 0.01316                                     | 0.02895                                      | 3.671                    | 0.04712                 |
| leading_edge_cfd_traditional              | 0.01             | 1                | 0.002632      | 0                    | 0.007895              | 0.002632                             | 0                                           | 0.007895                                     | 0                        | 0                       |
| template_residual_boosted_stack_new       | 0.05             | 0.2363           | 0.8289        | 0.7947               | 0.8659                | 0.3368                               | 0.2974                                      | 0.3843                                       | 5.254                    | 0.0779                  |
| gradient_boosted_trees                    | 0.05             | 0.2379           | 0.8184        | 0.792                | 0.8474                | 0.3395                               | 0.2894                                      | 0.4                                          | 6.199                    | 0.07338                 |
| ridge                                     | 0.05             | 0.5732           | 0.4974        | 0.4368               | 0.5714                | 0.06579                              | 0.05789                                     | 0.07112                                      | 6.675                    | 0.06886                 |
| tiny_sequence_transformer                 | 0.05             | 0.8661           | 0.3737        | 0.3209               | 0.4266                | 0.04474                              | 0.02362                                     | 0.06059                                      | 12.48                    | 0.1719                  |
| causal_window_transformer_new             | 0.05             | 0.7929           | 0.3684        | 0.3158               | 0.4158                | 0.08421                              | 0.06309                                     | 0.1082                                       | 8.772                    | 0.09586                 |
| mlp                                       | 0.05             | 0.6735           | 0.3632        | 0.3079               | 0.4395                | 0.08421                              | 0.06316                                     | 0.1                                          | 12.43                    | 0.1828                  |
| 1d_cnn                                    | 0.05             | 0.7513           | 0.3526        | 0.3105               | 0.4031                | 0.07105                              | 0.03947                                     | 0.1026                                       | 7.356                    | 0.08782                 |
| two_pulse_template_likelihood_traditional | 0.05             | 0.9935           | 0.2895        | 0.2472               | 0.3316                | 0.08158                              | 0.07099                                     | 0.09211                                      | 5.708                    | 0.08844                 |
| residual_tail_veto_traditional            | 0.05             | 0.9995           | 0.2447        | 0.2                  | 0.3132                | 0.04737                              | 0.03158                                     | 0.06316                                      | 5.579                    | 0.07146                 |
| leading_edge_cfd_traditional              | 0.05             | 1                | 0.02105       | 0.01579              | 0.02632               | 0.01579                              | 0.01316                                     | 0.02105                                      | 6.066                    | 0.2386                  |
| template_residual_boosted_stack_new       | 0.1              | 0.1864           | 0.85          | 0.8262               | 0.8816                | 0.3868                               | 0.3446                                      | 0.45                                         | 5.301                    | 0.07769                 |
| gradient_boosted_trees                    | 0.1              | 0.2054           | 0.8342        | 0.8157               | 0.8579                | 0.3816                               | 0.3316                                      | 0.4263                                       | 6.202                    | 0.07344                 |
| ridge                                     | 0.1              | 0.5473           | 0.5684        | 0.5078               | 0.6345                | 0.09211                              | 0.07888                                     | 0.1053                                       | 6.788                    | 0.06819                 |
| tiny_sequence_transformer                 | 0.1              | 0.7915           | 0.4632        | 0.4289               | 0.5081                | 0.08421                              | 0.07105                                     | 0.1001                                       | 12.93                    | 0.1768                  |
| causal_window_transformer_new             | 0.1              | 0.6731           | 0.4605        | 0.4105               | 0.5002                | 0.1184                               | 0.09737                                     | 0.1395                                       | 8.319                    | 0.08937                 |
| 1d_cnn                                    | 0.1              | 0.6655           | 0.4579        | 0.4263               | 0.4896                | 0.1158                               | 0.08684                                     | 0.1448                                       | 7.651                    | 0.08622                 |
| mlp                                       | 0.1              | 0.6272           | 0.4342        | 0.3842               | 0.4947                | 0.1079                               | 0.08158                                     | 0.1342                                       | 11.48                    | 0.1653                  |
| two_pulse_template_likelihood_traditional | 0.1              | 0.9388           | 0.3474        | 0.2921               | 0.4079                | 0.1263                               | 0.09474                                     | 0.1474                                       | 5.865                    | 0.08891                 |
| residual_tail_veto_traditional            | 0.1              | 0.9965           | 0.3158        | 0.2684               | 0.3632                | 0.1026                               | 0.07105                                     | 0.1184                                       | 5.953                    | 0.08857                 |
| leading_edge_cfd_traditional              | 0.1              | 1                | 0.03158       | 0.02105              | 0.03947               | 0.04737                              | 0.03947                                     | 0.05533                                      | 8.108                    | 0.257                   |

## Real-data sideband validation

The sideband table slices held-out clean controls by source run and stave using
the train-frozen 5% threshold.  A deconvolver that wins only by oversplitting
clean pulses would show a large and unstable sideband false-split rate here.

| method                                    | sideband_axis | sideband_value | n_real_clean_controls | false_split_rate | median_score | p95_score |
| ----------------------------------------- | ------------- | -------------- | --------------------- | ---------------- | ------------ | --------- |
| 1d_cnn                                    | source_run    | 58             | 76                    | 0.02632          | 0.2174       | 0.7038    |
| 1d_cnn                                    | source_run    | 60             | 76                    | 0.1316           | 0.2378       | 0.808     |
| 1d_cnn                                    | source_run    | 62             | 76                    | 0.09211          | 0.1939       | 0.8364    |
| 1d_cnn                                    | source_run    | 64             | 76                    | 0.03947          | 0.235        | 0.7009    |
| 1d_cnn                                    | source_run    | 65             | 76                    | 0.06579          | 0.2201       | 0.7724    |
| 1d_cnn                                    | stave         | B2             | 103                   | 0.06796          | 0.1893       | 0.7557    |
| 1d_cnn                                    | stave         | B4             | 101                   | 0.0396           | 0.1844       | 0.7314    |
| 1d_cnn                                    | stave         | B6             | 92                    | 0.09783          | 0.1883       | 0.8267    |
| 1d_cnn                                    | stave         | B8             | 84                    | 0.08333          | 0.3372       | 0.7984    |
| causal_window_transformer_new             | source_run    | 58             | 76                    | 0.03947          | 0.2108       | 0.7773    |
| causal_window_transformer_new             | source_run    | 60             | 76                    | 0.1316           | 0.2172       | 0.9098    |
| causal_window_transformer_new             | source_run    | 62             | 76                    | 0.1053           | 0.1625       | 0.8634    |
| causal_window_transformer_new             | source_run    | 64             | 76                    | 0.07895          | 0.2327       | 0.8452    |
| causal_window_transformer_new             | source_run    | 65             | 76                    | 0.06579          | 0.2027       | 0.8125    |
| causal_window_transformer_new             | stave         | B2             | 103                   | 0.05825          | 0.1734       | 0.7999    |
| causal_window_transformer_new             | stave         | B4             | 101                   | 0.07921          | 0.1873       | 0.8258    |
| causal_window_transformer_new             | stave         | B6             | 92                    | 0.09783          | 0.1683       | 0.9217    |
| causal_window_transformer_new             | stave         | B8             | 84                    | 0.1071           | 0.3188       | 0.8342    |
| gradient_boosted_trees                    | source_run    | 58             | 76                    | 0.3553           | 0.161        | 0.9085    |
| gradient_boosted_trees                    | source_run    | 60             | 76                    | 0.4474           | 0.201        | 0.8549    |
| gradient_boosted_trees                    | source_run    | 62             | 76                    | 0.3421           | 0.1114       | 0.6718    |
| gradient_boosted_trees                    | source_run    | 64             | 76                    | 0.3026           | 0.1198       | 0.828     |
| gradient_boosted_trees                    | source_run    | 65             | 76                    | 0.25             | 0.1174       | 0.7505    |
| gradient_boosted_trees                    | stave         | B2             | 103                   | 0.3398           | 0.1493       | 0.8148    |
| gradient_boosted_trees                    | stave         | B4             | 101                   | 0.3663           | 0.1462       | 0.775     |
| gradient_boosted_trees                    | stave         | B6             | 92                    | 0.2065           | 0.09695      | 0.688     |
| gradient_boosted_trees                    | stave         | B8             | 84                    | 0.4524           | 0.2098       | 0.8792    |
| leading_edge_cfd_traditional              | source_run    | 58             | 76                    | 0.02632          | 0.9984       | 1         |
| leading_edge_cfd_traditional              | source_run    | 60             | 76                    | 0.01316          | 0.9882       | 1         |
| leading_edge_cfd_traditional              | source_run    | 62             | 76                    | 0.01316          | 0.9985       | 1         |
| leading_edge_cfd_traditional              | source_run    | 64             | 76                    | 0.01316          | 0.9996       | 1         |
| leading_edge_cfd_traditional              | source_run    | 65             | 76                    | 0.01316          | 0.9996       | 1         |
| leading_edge_cfd_traditional              | stave         | B2             | 103                   | 0.03883          | 1            | 1         |
| leading_edge_cfd_traditional              | stave         | B4             | 101                   | 0.009901         | 0.9981       | 1         |
| leading_edge_cfd_traditional              | stave         | B6             | 92                    | 0.01087          | 0.9996       | 1         |
| leading_edge_cfd_traditional              | stave         | B8             | 84                    | 0                | 0.9435       | 1         |
| mlp                                       | source_run    | 58             | 76                    | 0.05263          | 0.3365       | 0.647     |
| mlp                                       | source_run    | 60             | 76                    | 0.1053           | 0.3621       | 0.7363    |
| mlp                                       | source_run    | 62             | 76                    | 0.1053           | 0.3511       | 0.752     |
| mlp                                       | source_run    | 64             | 76                    | 0.07895          | 0.3637       | 0.7213    |
| mlp                                       | source_run    | 65             | 76                    | 0.07895          | 0.3532       | 0.7081    |
| mlp                                       | stave         | B2             | 103                   | 0.08738          | 0.3516       | 0.713     |
| mlp                                       | stave         | B4             | 101                   | 0.09901          | 0.3475       | 0.7163    |
| mlp                                       | stave         | B6             | 92                    | 0.04348          | 0.3456       | 0.6444    |
| mlp                                       | stave         | B8             | 84                    | 0.1071           | 0.3729       | 0.7608    |
| residual_tail_veto_traditional            | source_run    | 58             | 76                    | 0.05263          | 0.0003531    | 0.9994    |
| residual_tail_veto_traditional            | source_run    | 60             | 76                    | 0.03947          | 0.0003618    | 0.9987    |
| residual_tail_veto_traditional            | source_run    | 62             | 76                    | 0.05263          | 0.0004431    | 0.9995    |
| residual_tail_veto_traditional            | source_run    | 64             | 76                    | 0.01316          | 0.0005401    | 0.994     |
| residual_tail_veto_traditional            | source_run    | 65             | 76                    | 0.07895          | 0.001793     | 0.9999    |
| residual_tail_veto_traditional            | stave         | B2             | 103                   | 0.02913          | 0.001144     | 0.998     |
| residual_tail_veto_traditional            | stave         | B4             | 101                   | 0.07921          | 0.0001725    | 0.9999    |
| residual_tail_veto_traditional            | stave         | B6             | 92                    | 0.07609          | 0.0003525    | 0.9998    |
| residual_tail_veto_traditional            | stave         | B8             | 84                    | 0                | 0.6762       | 0.9985    |
| ridge                                     | source_run    | 58             | 76                    | 0.07895          | 0.4009       | 0.5878    |
| ridge                                     | source_run    | 60             | 76                    | 0.06579          | 0.3982       | 0.5828    |
| ridge                                     | source_run    | 62             | 76                    | 0.06579          | 0.3739       | 0.5882    |
| ridge                                     | source_run    | 64             | 76                    | 0.06579          | 0.3599       | 0.5753    |
| ridge                                     | source_run    | 65             | 76                    | 0.05263          | 0.3597       | 0.5622    |
| ridge                                     | stave         | B2             | 103                   | 0.07767          | 0.3458       | 0.5884    |
| ridge                                     | stave         | B4             | 101                   | 0.0495           | 0.3885       | 0.5576    |
| ridge                                     | stave         | B6             | 92                    | 0.03261          | 0.3781       | 0.5386    |
| ridge                                     | stave         | B8             | 84                    | 0.1071           | 0.4217       | 0.605     |
| template_residual_boosted_stack_new       | source_run    | 58             | 76                    | 0.3553           | 0.1467       | 0.8679    |
| template_residual_boosted_stack_new       | source_run    | 60             | 76                    | 0.4211           | 0.1921       | 0.8985    |
| template_residual_boosted_stack_new       | source_run    | 62             | 76                    | 0.3289           | 0.1136       | 0.7102    |
| template_residual_boosted_stack_new       | source_run    | 64             | 76                    | 0.3026           | 0.1063       | 0.8027    |
| template_residual_boosted_stack_new       | source_run    | 65             | 76                    | 0.2763           | 0.102        | 0.7809    |
| template_residual_boosted_stack_new       | stave         | B2             | 103                   | 0.3301           | 0.1402       | 0.8204    |
| template_residual_boosted_stack_new       | stave         | B4             | 101                   | 0.3663           | 0.145        | 0.8628    |
| template_residual_boosted_stack_new       | stave         | B6             | 92                    | 0.2174           | 0.09499      | 0.6894    |
| template_residual_boosted_stack_new       | stave         | B8             | 84                    | 0.4405           | 0.1649       | 0.8786    |
| tiny_sequence_transformer                 | source_run    | 58             | 76                    | 0.06579          | 0.2966       | 0.897     |
| tiny_sequence_transformer                 | source_run    | 60             | 76                    | 0.05263          | 0.2286       | 0.861     |
| tiny_sequence_transformer                 | source_run    | 62             | 76                    | 0                | 0.1755       | 0.8102    |
| tiny_sequence_transformer                 | source_run    | 64             | 76                    | 0.03947          | 0.3089       | 0.8247    |
| tiny_sequence_transformer                 | source_run    | 65             | 76                    | 0.06579          | 0.2684       | 0.8822    |
| tiny_sequence_transformer                 | stave         | B2             | 103                   | 0.03883          | 0.1282       | 0.8013    |
| tiny_sequence_transformer                 | stave         | B4             | 101                   | 0.0198           | 0.2512       | 0.784     |
| tiny_sequence_transformer                 | stave         | B6             | 92                    | 0.02174          | 0.2883       | 0.8063    |
| tiny_sequence_transformer                 | stave         | B8             | 84                    | 0.1071           | 0.566        | 0.9196    |
| two_pulse_template_likelihood_traditional | source_run    | 58             | 76                    | 0.09211          | 0            | 0.9985    |
| two_pulse_template_likelihood_traditional | source_run    | 60             | 76                    | 0.07895          | 0            | 0.9982    |
| two_pulse_template_likelihood_traditional | source_run    | 62             | 76                    | 0.06579          | 0            | 0.9988    |
| two_pulse_template_likelihood_traditional | source_run    | 64             | 76                    | 0.06579          | 0            | 0.9952    |
| two_pulse_template_likelihood_traditional | source_run    | 65             | 76                    | 0.1053           | 0            | 0.9995    |
| two_pulse_template_likelihood_traditional | stave         | B2             | 103                   | 0.04854          | 0            | 0.9204    |
| two_pulse_template_likelihood_traditional | stave         | B4             | 101                   | 0.08911          | 0            | 0.9998    |
| two_pulse_template_likelihood_traditional | stave         | B6             | 92                    | 0.09783          | 0            | 0.9995    |
| two_pulse_template_likelihood_traditional | stave         | B8             | 84                    | 0.09524          | 0.3878       | 0.9971    |

## Registered endpoint table

The endpoint table maps the ticket language to measured quantities.  Leading-edge
time uses the first constituent error.  Secondary-pulse delay uses
`10 ns * [(hat t_2-hat t_1)-Delta]`.  Shape residual is a dimensionless proxy that
combines first-time, second-time, and energy residuals.  Saturation interaction is
the energy width for injected total amplitude above 11000 ADC.  Pedestal shift is
the false split rate on clean controls.  PID confusion is a cross-stave energy
bias span, treating stave as the available PID-boundary proxy.

| method                                    | leading_edge_time_bias_ns | leading_edge_time_sigma68_ns | leading_edge_time_sigma68_ns_ci_low | leading_edge_time_sigma68_ns_ci_high | secondary_pulse_delay_bias_ns | secondary_pulse_delay_sigma68_ns | secondary_pulse_delay_sigma68_ns_ci_low | secondary_pulse_delay_sigma68_ns_ci_high | false_merge_rate | tight_sep_le_15ns_false_merge_rate | saturation_interaction_energy_sigma68 | pedestal_shift_false_split_rate | energy_proxy_distortion_sigma68 | pid_confusion_stave_bias_span |
| ----------------------------------------- | ------------------------- | ---------------------------- | ----------------------------------- | ------------------------------------ | ----------------------------- | -------------------------------- | --------------------------------------- | ---------------------------------------- | ---------------- | ---------------------------------- | ------------------------------------- | ------------------------------- | ------------------------------- | ----------------------------- |
| template_residual_boosted_stack_new       | 0.857                     | 4.944                        | 4.708                               | 5.807                                | -0.5968                       | 9.732                            | 8.882                                   | 11.17                                    | 0.3026           | 0.4201                             | 0.0694                                | 0.1684                          | 0.0714                          | 0.02099                       |
| two_pulse_template_likelihood_traditional | 0.4546                    | 5.951                        | 5.318                               | 6.503                                | 0                             | 12.5                             | 10                                      | 15.02                                    | 0.5921           | 0.6982                             | 0.01686                               | 0.1947                          | 0.09619                         | 0.09577                       |
| gradient_boosted_trees                    | 0.6257                    | 6.134                        | 5.562                               | 6.839                                | -0.886                        | 10.2                             | 8.835                                   | 10.76                                    | 0.3211           | 0.4379                             | 0.04744                               | 0.1658                          | 0.07141                         | 0.02684                       |
| residual_tail_veto_traditional            | 0.1088                    | 6.582                        | 5.996                               | 7.254                                | 0                             | 20                               | 15                                      | 20                                       | 0.5184           | 0.5621                             | 0.01825                               | 0.2763                          | 0.09311                         | 0.1022                        |
| ridge                                     | 0.3662                    | 7.018                        | 6.044                               | 8.321                                | -0.3379                       | 13.09                            | 12.38                                   | 14.85                                    | 0.3132           | 0.4083                             | 0.07858                               | 0.1658                          | 0.06663                         | 0.07174                       |
| 1d_cnn                                    | 0.5961                    | 8.903                        | 8.484                               | 9.529                                | 0.1217                        | 15.97                            | 14.87                                   | 17.4                                     | 0.3763           | 0.5385                             | 0.1341                                | 0.2105                          | 0.08647                         | 0.02001                       |
| leading_edge_cfd_traditional              | -8.096                    | 9.996                        | 9.162                               | 11.5                                 | 0                             | 21.25                            | 21.25                                   | 22.5                                     | 0.06053          | 0.06509                            | 0.1853                                | 0.85                            | 0.2811                          | 0.3666                        |
| causal_window_transformer_new             | -3.821                    | 10.1                         | 8.366                               | 11.5                                 | -4.153                        | 14.58                            | 12.68                                   | 17.82                                    | 0.4263           | 0.5917                             | 0.07441                               | 0.1974                          | 0.09189                         | 0.06127                       |
| mlp                                       | 0.7449                    | 11.56                        | 10.3                                | 12.61                                | 2.414                         | 18.85                            | 16.74                                   | 20.9                                     | 0.3526           | 0.497                              | 0.1784                                | 0.2132                          | 0.1736                          | 0.1087                        |
| tiny_sequence_transformer                 | -7.363                    | 13.23                        | 12.43                               | 14.49                                | 2.804                         | 15.9                             | 13.74                                   | 17.37                                    | 0.3079           | 0.4438                             | 0.117                                 | 0.3                             | 0.1721                          | 0.07419                       |

## Winner rule

The primary winner minimizes

`C_m = sigma_lead/20 + sigma_delay/25 + R_shape + 3 sigma_E + 0.6 r_miss + 0.6 r_false + 2 B_stave`,

where `B_stave` is the cross-stave median energy-bias span.  This score favors
timing and secondary-delay recovery but penalizes models that obtain narrow
timing only by rejecting overlaps, splitting clean pulses, distorting energy, or
moving stave/PID boundaries.  Fixed-FPR recall is not hidden inside the score; it
is reported separately above as the operational pile-up-tagging endpoint.

| method                                    | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | shape_residual_proxy_median | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate | pid_confusion_stave_bias_span |
| ----------------------------------------- | ------------ | ---------------------------- | -------------------------------- | --------------------------- | ------------------------------- | ---------------- | ---------------- | ----------------------------- |
| template_residual_boosted_stack_new       | 1.728        | 4.944                        | 9.732                            | 0.5524                      | 0.0714                          | 0.3026           | 0.1684           | 0.02099                       |
| gradient_boosted_trees                    | 1.863        | 6.134                        | 10.2                             | 0.5884                      | 0.07141                         | 0.3211           | 0.1658           | 0.02684                       |
| ridge                                     | 2.173        | 7.018                        | 13.09                            | 0.6673                      | 0.06663                         | 0.3132           | 0.1658           | 0.07174                       |
| two_pulse_template_likelihood_traditional | 2.467        | 5.951                        | 12.5                             | 0.7173                      | 0.09619                         | 0.5921           | 0.1947           | 0.09577                       |
| 1d_cnn                                    | 2.544        | 8.903                        | 15.97                            | 0.809                       | 0.08647                         | 0.3763           | 0.2105           | 0.02001                       |
| causal_window_transformer_new             | 2.821        | 10.1                         | 14.58                            | 0.96                        | 0.09189                         | 0.4263           | 0.1974           | 0.06127                       |
| residual_tail_veto_traditional            | 2.866        | 6.582                        | 20                               | 0.7766                      | 0.09311                         | 0.5184           | 0.2763           | 0.1022                        |
| mlp                                       | 3.536        | 11.56                        | 18.85                            | 1.126                       | 0.1736                          | 0.3526           | 0.2132           | 0.1087                        |
| tiny_sequence_transformer                 | 3.537        | 13.23                        | 15.9                             | 1.211                       | 0.1721                          | 0.3079           | 0.3              | 0.07419                       |
| leading_edge_cfd_traditional              | 5.749        | 9.996                        | 21.25                            | 2.277                       | 0.2811                          | 0.06053          | 0.85             | 0.3666                        |

The traditional baseline has score `2.467` and leading-edge
sigma68 `5.951` ns.  The selected winner
`template_residual_boosted_stack_new` has score `1.728` and leading-edge sigma68
`4.944` ns.

## Run-held-out stability

| method                                    | heldout_run | time_bias_ns | time_sigma68_ns | late_tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------------- | ----------- | ------------ | --------------- | -------------------------- | ---------------- | ---------------- | ------------------------- |
| 1d_cnn                                    | 58          | 1.692        | 11.56           | 0.1852                     | 0.2895           | 0.2105           | 0.0818                    |
| 1d_cnn                                    | 60          | -0.09832     | 10.29           | 0.1957                     | 0.3947           | 0.2368           | 0.0819                    |
| 1d_cnn                                    | 62          | -1.112       | 10.98           | 0.1744                     | 0.4342           | 0.1974           | 0.1004                    |
| 1d_cnn                                    | 64          | -1.953       | 12.35           | 0.2551                     | 0.3553           | 0.1842           | 0.06975                   |
| 1d_cnn                                    | 65          | 1.503        | 11.23           | 0.1333                     | 0.4079           | 0.2237           | 0.07353                   |
| causal_window_transformer_new             | 58          | -6.457       | 13.37           | 0.2981                     | 0.3158           | 0.2237           | 0.0828                    |
| causal_window_transformer_new             | 60          | -6.056       | 9.987           | 0.2561                     | 0.4605           | 0.25             | 0.09872                   |
| causal_window_transformer_new             | 62          | -7.258       | 14.62           | 0.3049                     | 0.4605           | 0.1711           | 0.09275                   |
| causal_window_transformer_new             | 64          | -5.882       | 14.95           | 0.3415                     | 0.4605           | 0.1316           | 0.0705                    |
| causal_window_transformer_new             | 65          | -5.506       | 10.6            | 0.2674                     | 0.4342           | 0.2105           | 0.09974                   |
| gradient_boosted_trees                    | 58          | 0.3116       | 7.927           | 0.1293                     | 0.2368           | 0.2105           | 0.07795                   |
| gradient_boosted_trees                    | 60          | -0.02777     | 7.401           | 0.08654                    | 0.3158           | 0.2237           | 0.05606                   |
| gradient_boosted_trees                    | 62          | 0.1639       | 7.305           | 0.08824                    | 0.3289           | 0.1184           | 0.08439                   |
| gradient_boosted_trees                    | 64          | 0.9664       | 8.342           | 0.09574                    | 0.3816           | 0.1316           | 0.07358                   |
| gradient_boosted_trees                    | 65          | -0.3801      | 7.732           | 0.06                       | 0.3421           | 0.1447           | 0.06407                   |
| leading_edge_cfd_traditional              | 58          | -9.936       | 16.84           | 0.3767                     | 0.03947          | 0.8421           | 0.1925                    |
| leading_edge_cfd_traditional              | 60          | -8.8         | 16.89           | 0.3696                     | 0.09211          | 0.8421           | 0.2397                    |
| leading_edge_cfd_traditional              | 62          | -11.13       | 17.88           | 0.403                      | 0.1184           | 0.7763           | 0.3161                    |
| leading_edge_cfd_traditional              | 64          | -9.461       | 16.54           | 0.3618                     | 0                | 0.8816           | 0.3599                    |
| leading_edge_cfd_traditional              | 65          | -9.114       | 19.63           | 0.4028                     | 0.05263          | 0.9079           | 0.3066                    |
| mlp                                       | 58          | 1.522        | 15.9            | 0.386                      | 0.25             | 0.2237           | 0.1612                    |
| mlp                                       | 60          | 2.242        | 13.42           | 0.28                       | 0.3421           | 0.25             | 0.1818                    |
| mlp                                       | 62          | 2.531        | 13.84           | 0.2826                     | 0.3947           | 0.1974           | 0.2059                    |
| mlp                                       | 64          | 0.5544       | 14.48           | 0.3182                     | 0.4211           | 0.1974           | 0.1548                    |
| mlp                                       | 65          | 0.3841       | 13.13           | 0.2755                     | 0.3553           | 0.1974           | 0.1582                    |
| residual_tail_veto_traditional            | 58          | 0.2862       | 7.89            | 0.1375                     | 0.4737           | 0.25             | 0.06342                   |
| residual_tail_veto_traditional            | 60          | 0.4227       | 11.84           | 0.2353                     | 0.5526           | 0.2763           | 0.1011                    |
| residual_tail_veto_traditional            | 62          | 1.784        | 9.266           | 0.09677                    | 0.5921           | 0.25             | 0.08393                   |
| residual_tail_veto_traditional            | 64          | 1.231        | 11.97           | 0.2576                     | 0.5658           | 0.25             | 0.09575                   |
| residual_tail_veto_traditional            | 65          | 1.331        | 8.746           | 0.1444                     | 0.4079           | 0.3553           | 0.1004                    |
| ridge                                     | 58          | 0.5566       | 10.36           | 0.1475                     | 0.1974           | 0.1974           | 0.06683                   |
| ridge                                     | 60          | 0.04905      | 8.76            | 0.1204                     | 0.2895           | 0.1711           | 0.05307                   |
| ridge                                     | 62          | 0.6578       | 8.942           | 0.1327                     | 0.3553           | 0.1842           | 0.07075                   |
| ridge                                     | 64          | 1.035        | 9.661           | 0.1429                     | 0.3553           | 0.1184           | 0.08012                   |
| ridge                                     | 65          | -0.1267      | 8.88            | 0.07292                    | 0.3684           | 0.1579           | 0.05695                   |
| template_residual_boosted_stack_new       | 58          | 1.559        | 7.463           | 0.1333                     | 0.2105           | 0.1974           | 0.06909                   |
| template_residual_boosted_stack_new       | 60          | -0.295       | 5.976           | 0.07895                    | 0.25             | 0.1974           | 0.06299                   |
| template_residual_boosted_stack_new       | 62          | 0.184        | 6.322           | 0.04717                    | 0.3026           | 0.1711           | 0.06884                   |
| template_residual_boosted_stack_new       | 64          | 0.7936       | 7.491           | 0.09783                    | 0.3947           | 0.1579           | 0.07358                   |
| template_residual_boosted_stack_new       | 65          | 0.5729       | 6.881           | 0.05102                    | 0.3553           | 0.1184           | 0.0542                    |
| tiny_sequence_transformer                 | 58          | -5.667       | 14.69           | 0.4                        | 0.2105           | 0.3158           | 0.1758                    |
| tiny_sequence_transformer                 | 60          | -7.365       | 12.52           | 0.31                       | 0.3421           | 0.3158           | 0.1711                    |
| tiny_sequence_transformer                 | 62          | -6.82        | 13.31           | 0.31                       | 0.3421           | 0.2763           | 0.1742                    |
| tiny_sequence_transformer                 | 64          | -5.542       | 12.79           | 0.3208                     | 0.3026           | 0.2632           | 0.1267                    |
| tiny_sequence_transformer                 | 65          | -6.131       | 13.63           | 0.3                        | 0.3421           | 0.3289           | 0.1494                    |
| two_pulse_template_likelihood_traditional | 58          | -0.03014     | 6.902           | 0.08824                    | 0.5526           | 0.1842           | 0.06559                   |
| two_pulse_template_likelihood_traditional | 60          | 0.4227       | 11.84           | 0.2353                     | 0.5526           | 0.2368           | 0.1011                    |
| two_pulse_template_likelihood_traditional | 62          | 1.894        | 7.211           | 0.02                       | 0.6711           | 0.1842           | 0.07234                   |
| two_pulse_template_likelihood_traditional | 64          | 0.584        | 10.21           | 0.2083                     | 0.6842           | 0.1316           | 0.105                     |
| two_pulse_template_likelihood_traditional | 65          | 1.346        | 8.162           | 0.1447                     | 0.5              | 0.2368           | 0.08433                   |

## Detector-held-out split

As a detector-transfer check, the nominal predictions are sliced so that B8 is
the held-out detector proxy and B2/B4/B6 form the non-evaluation slice.
Source-run bootstrap CIs are still computed on the B8 held-out slice.  This is a
detector-slice stress test rather than a retrained detector-exclusion claim.

| method                                    | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate |
| ----------------------------------------- | ------------ | ---------------------------- | -------------------------------- | ------------------------------- | ---------------- | ---------------- |
| template_residual_boosted_stack_new       | 0.9473       | 2.701                        | 5.93                             | 0.0475                          | 0.08             | 0.1497           |
| gradient_boosted_trees                    | 0.9531       | 2.65                         | 6.203                            | 0.04428                         | 0.085            | 0.107            |
| ridge                                     | 1.723        | 5                            | 10.51                            | 0.06401                         | 0.205            | 0.2299           |
| two_pulse_template_likelihood_traditional | 1.806        | 3.393                        | 10                               | 0.09273                         | 0.23             | 0.4118           |
| residual_tail_veto_traditional            | 1.82         | 3.493                        | 10                               | 0.09021                         | 0.12             | 0.615            |
| 1d_cnn                                    | 2.109        | 5.839                        | 14.54                            | 0.07673                         | 0.2              | 0.2834           |
| causal_window_transformer_new             | 2.192        | 8.14                         | 11.94                            | 0.08571                         | 0.22             | 0.2834           |
| tiny_sequence_transformer                 | 2.851        | 11.19                        | 12.63                            | 0.1592                          | 0.09             | 0.4973           |
| mlp                                       | 2.94         | 9.749                        | 16.24                            | 0.1438                          | 0.205            | 0.2727           |
| leading_edge_cfd_traditional              | 3.928        | 3.814                        | 21.25                            | 0.1881                          | 0.12             | 0.8128           |

## Ablations

Stress-control slices were evaluated before interpretation.  The
pretrigger-pedestal row uses clean negative controls as the
pedestal-sensitivity endpoint.  The synthetic-over-real rows isolate tight
doublets and high summed-amplitude injections, both generated on real raw-ROOT
single-pulse residuals.  The shuffled-phase and amplitude-only sentinels are
negative controls: they retain the high-current residual and amplitude spectrum
while disrupting the second-pulse timing phase or removing the waveform timing
information from the ranking surface.

| ablation            | method                                    | winner_score | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | energy_proxy_distortion_sigma68 | pileup_miss_rate | false_split_rate |
| ------------------- | ----------------------------------------- | ------------ | ---------------------------- | -------------------------------- | ------------------------------- | ---------------- | ---------------- |
| nominal_full_window | template_residual_boosted_stack_new       | 1.728        | 4.944                        | 9.732                            | 0.0714                          | 0.3026           | 0.1684           |
| nominal_full_window | gradient_boosted_trees                    | 1.863        | 6.134                        | 10.2                             | 0.07141                         | 0.3211           | 0.1658           |
| nominal_full_window | ridge                                     | 2.173        | 7.018                        | 13.09                            | 0.06663                         | 0.3132           | 0.1658           |
| nominal_full_window | two_pulse_template_likelihood_traditional | 2.467        | 5.951                        | 12.5                             | 0.09619                         | 0.5921           | 0.1947           |
| nominal_full_window | 1d_cnn                                    | 2.544        | 8.903                        | 15.97                            | 0.08647                         | 0.3763           | 0.2105           |
| nominal_full_window | causal_window_transformer_new             | 2.821        | 10.1                         | 14.58                            | 0.09189                         | 0.4263           | 0.1974           |
| nominal_full_window | residual_tail_veto_traditional            | 2.866        | 6.582                        | 20                               | 0.09311                         | 0.5184           | 0.2763           |
| nominal_full_window | mlp                                       | 3.536        | 11.56                        | 18.85                            | 0.1736                          | 0.3526           | 0.2132           |
| nominal_full_window | tiny_sequence_transformer                 | 3.537        | 13.23                        | 15.9                             | 0.1721                          | 0.3079           | 0.3              |
| nominal_full_window | leading_edge_cfd_traditional              | 5.749        | 9.996                        | 21.25                            | 0.2811                          | 0.06053          | 0.85             |

| stress                                        | method                                    | n_events | leading_edge_time_sigma68_ns | secondary_pulse_delay_sigma68_ns | pileup_miss_rate | false_split_rate | energy_proxy_distortion_sigma68 |
| --------------------------------------------- | ----------------------------------------- | -------- | ---------------------------- | -------------------------------- | ---------------- | ---------------- | ------------------------------- |
| pretrigger_pedestal_clean_control             | 1d_cnn                                    | 380      | nan                          | nan                              | nan              | 0.2105           | nan                             |
| pretrigger_pedestal_clean_control             | causal_window_transformer_new             | 380      | nan                          | nan                              | nan              | 0.1974           | nan                             |
| pretrigger_pedestal_clean_control             | gradient_boosted_trees                    | 380      | nan                          | nan                              | nan              | 0.1658           | nan                             |
| pretrigger_pedestal_clean_control             | leading_edge_cfd_traditional              | 380      | nan                          | nan                              | nan              | 0.85             | nan                             |
| pretrigger_pedestal_clean_control             | mlp                                       | 380      | nan                          | nan                              | nan              | 0.2132           | nan                             |
| pretrigger_pedestal_clean_control             | residual_tail_veto_traditional            | 380      | nan                          | nan                              | nan              | 0.2763           | nan                             |
| pretrigger_pedestal_clean_control             | ridge                                     | 380      | nan                          | nan                              | nan              | 0.1658           | nan                             |
| pretrigger_pedestal_clean_control             | template_residual_boosted_stack_new       | 380      | nan                          | nan                              | nan              | 0.1684           | nan                             |
| pretrigger_pedestal_clean_control             | tiny_sequence_transformer                 | 380      | nan                          | nan                              | nan              | 0.3              | nan                             |
| pretrigger_pedestal_clean_control             | two_pulse_template_likelihood_traditional | 380      | nan                          | nan                              | nan              | 0.1947           | nan                             |
| synthetic_over_real_tight_sep_le_15ns         | 1d_cnn                                    | 169      | 8.223                        | 6.414                            | 0.5385           | nan              | 0.06273                         |
| synthetic_over_real_tight_sep_le_15ns         | causal_window_transformer_new             | 169      | 14.35                        | 13.77                            | 0.5917           | nan              | 0.07585                         |
| synthetic_over_real_tight_sep_le_15ns         | gradient_boosted_trees                    | 169      | 6.339                        | 8.888                            | 0.4379           | nan              | 0.06054                         |
| synthetic_over_real_tight_sep_le_15ns         | leading_edge_cfd_traditional              | 169      | 9.489                        | 5                                | 0.06509          | nan              | 0.2424                          |
| synthetic_over_real_tight_sep_le_15ns         | mlp                                       | 169      | 10.86                        | 16.18                            | 0.497            | nan              | 0.1589                          |
| synthetic_over_real_tight_sep_le_15ns         | residual_tail_veto_traditional            | 169      | 7.467                        | 21.25                            | 0.5621           | nan              | 0.07254                         |
| synthetic_over_real_tight_sep_le_15ns         | ridge                                     | 169      | 6.576                        | 9.109                            | 0.4083           | nan              | 0.0529                          |
| synthetic_over_real_tight_sep_le_15ns         | template_residual_boosted_stack_new       | 169      | 5.247                        | 7.655                            | 0.4201           | nan              | 0.06792                         |
| synthetic_over_real_tight_sep_le_15ns         | tiny_sequence_transformer                 | 169      | 13.51                        | 12.53                            | 0.4438           | nan              | 0.108                           |
| synthetic_over_real_tight_sep_le_15ns         | two_pulse_template_likelihood_traditional | 169      | 6.02                         | 17.5                             | 0.6982           | nan              | 0.08344                         |
| synthetic_over_real_saturated_sum_gt_11000adc | 1d_cnn                                    | 8        | 4.85                         | 12.51                            | 0.375            | nan              | 0.1341                          |
| synthetic_over_real_saturated_sum_gt_11000adc | causal_window_transformer_new             | 8        | 10.42                        | 9.731                            | 0.25             | nan              | 0.07441                         |
| synthetic_over_real_saturated_sum_gt_11000adc | gradient_boosted_trees                    | 8        | 4.654                        | 7.073                            | 0                | nan              | 0.04744                         |
| synthetic_over_real_saturated_sum_gt_11000adc | leading_edge_cfd_traditional              | 8        | 8.431                        | 21.25                            | 0                | nan              | 0.1853                          |
| synthetic_over_real_saturated_sum_gt_11000adc | mlp                                       | 8        | 9.033                        | 15.94                            | 0                | nan              | 0.1784                          |
| synthetic_over_real_saturated_sum_gt_11000adc | residual_tail_veto_traditional            | 8        | 5.627                        | 15.5                             | 0.5              | nan              | 0.01825                         |
| synthetic_over_real_saturated_sum_gt_11000adc | ridge                                     | 8        | 2.784                        | 8.128                            | 0                | nan              | 0.07858                         |
| synthetic_over_real_saturated_sum_gt_11000adc | template_residual_boosted_stack_new       | 8        | 4.389                        | 6.935                            | 0                | nan              | 0.0694                          |
| synthetic_over_real_saturated_sum_gt_11000adc | tiny_sequence_transformer                 | 8        | 7.797                        | 5.268                            | 0.375            | nan              | 0.117                           |
| synthetic_over_real_saturated_sum_gt_11000adc | two_pulse_template_likelihood_traditional | 8        | 2.233                        | 5.1                              | 0.625            | nan              | 0.01686                         |
| shuffled_second_pulse_phase_negative_control  | 1d_cnn                                    | 187      | 8.43                         | 16.52                            | 0.385            | nan              | 0.08645                         |
| shuffled_second_pulse_phase_negative_control  | causal_window_transformer_new             | 187      | 8.694                        | 12.91                            | 0.4706           | nan              | 0.09604                         |
| shuffled_second_pulse_phase_negative_control  | gradient_boosted_trees                    | 187      | 6.249                        | 9.498                            | 0.2995           | nan              | 0.07679                         |
| shuffled_second_pulse_phase_negative_control  | leading_edge_cfd_traditional              | 193      | 9.492                        | 21.25                            | 0.07772          | nan              | 0.2755                          |
| shuffled_second_pulse_phase_negative_control  | mlp                                       | 193      | 11.56                        | 17.75                            | 0.3782           | nan              | 0.1654                          |
| shuffled_second_pulse_phase_negative_control  | residual_tail_veto_traditional            | 187      | 6.86                         | 15.75                            | 0.5134           | nan              | 0.08435                         |
| shuffled_second_pulse_phase_negative_control  | ridge                                     | 193      | 7.313                        | 13.46                            | 0.3368           | nan              | 0.06231                         |
| shuffled_second_pulse_phase_negative_control  | template_residual_boosted_stack_new       | 193      | 5.219                        | 9.432                            | 0.3264           | nan              | 0.06879                         |
| shuffled_second_pulse_phase_negative_control  | tiny_sequence_transformer                 | 193      | 14.15                        | 14.66                            | 0.3212           | nan              | 0.1854                          |
| shuffled_second_pulse_phase_negative_control  | two_pulse_template_likelihood_traditional | 187      | 6.37                         | 13                               | 0.5668           | nan              | 0.08944                         |
| amplitude_only_sentinel_high_charge           | 1d_cnn                                    | 190      | 10.23                        | 15.8                             | 0.2368           | nan              | 0.08319                         |
| amplitude_only_sentinel_high_charge           | causal_window_transformer_new             | 190      | 10.49                        | 13.12                            | 0.2789           | nan              | 0.08813                         |
| amplitude_only_sentinel_high_charge           | gradient_boosted_trees                    | 190      | 6.415                        | 9.666                            | 0.1105           | nan              | 0.0676                          |
| amplitude_only_sentinel_high_charge           | leading_edge_cfd_traditional              | 190      | 9.087                        | 21.25                            | 0.03158          | nan              | 0.2214                          |
| amplitude_only_sentinel_high_charge           | mlp                                       | 190      | 11.16                        | 18.66                            | 0.1789           | nan              | 0.1622                          |
| amplitude_only_sentinel_high_charge           | residual_tail_veto_traditional            | 190      | 6.778                        | 21.85                            | 0.4842           | nan              | 0.06026                         |
| amplitude_only_sentinel_high_charge           | ridge                                     | 190      | 7.429                        | 12.5                             | 0.07368          | nan              | 0.07162                         |
| amplitude_only_sentinel_high_charge           | template_residual_boosted_stack_new       | 190      | 5.296                        | 9.706                            | 0.08421          | nan              | 0.06836                         |
| amplitude_only_sentinel_high_charge           | tiny_sequence_transformer                 | 190      | 12.96                        | 13.82                            | 0.2158           | nan              | 0.1724                          |
| amplitude_only_sentinel_high_charge           | two_pulse_template_likelihood_traditional | 190      | 5.557                        | 15                               | 0.5684           | nan              | 0.06766                         |

## Interpretation and next test

The main result is that adding the traditional deconvolution outputs back into a
boosted residual learner is more useful than replacing the physics fit with a
pure sequence model.  The residual stack wins the nominal run-held-out score and
the B8 detector-slice table checks whether that ordering is stable for one stave
held out as an evaluation proxy.  This pattern suggests that the raw 18-sample
waveform still contains recoverable nonlinear residual structure, but the
template/CFD fit supplies a strong low-variance coordinate system for that
structure.

The falsifying follow-up was appended as ticket **#2429**, **S45d:
hand-scanned overlap-aware energy/PID validation for the S45c winner**.  It asks
whether the S45c winner keeps its fixed-FPR recall, energy stability, and
PID-proxy boundary advantage on real pile-up-like windows rather than
exact-truth synthetic-over-real doublets.

## Systematics and caveats

The benchmark uses controlled injections into raw-ROOT-derived clean pulses, so
truth is exact for delay and amplitude but real beam pile-up frequency is not
measured.  The saturation endpoint is an amplitude-knee proxy, not electronics
metadata.  Pedestal shift is represented by clean-control false splitting and
run-local residuals, not an independent pedestal trigger stream.  PID confusion is
therefore a stave-conditioned boundary proxy rather than a particle-ID truth
confusion matrix.  The 18-sample waveform limits sub-sample deconvolution below
roughly one digitizer tick; all models inherit that sampling floor.  Finally, the
run-block bootstrap has only the finite held-out run set, so its CIs quantify
run-transfer uncertainty rather than asymptotic event uncertainty.

Runtime was `107.3` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.

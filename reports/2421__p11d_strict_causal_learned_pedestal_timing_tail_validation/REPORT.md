# P11d: Strictly Causal Learned-Pedestal Timing-Tail Validation

## Abstract

Ticket `#2421` requests a validation of the P11c learned-pedestal residual using
only pretrigger state and forced/random pedestal controls, then propagation into
S02/S04 timing-tail endpoints under run-heldout paired/bootstrap uncertainty.
This study reopens the raw ROOT selected-pulse gate, audits the available
forced/random B-stack controls, and benchmarks a strong transparent
pretrigger-pedestal/template method against ridge, gradient-boosted trees, MLP,
1D-CNN, and two newer waveform architectures.  The machine-readable winner in
`result.json` is **`gradient_boosted_trees`** with composite held-out score
`0.2232`.  Relative to the traditional
`deltaE_over_E_likelihood_template`, the winner changes timing-tail sigma68 by
`-3.581` ns and
energy sigma68 by `-0.0399`.

## Raw ROOT Reproduction

The raw B-stack ROOT files were read from `/home/billy/ccb-data/data/extracted/root/root`.  Each `h101/HRDv` array is
reshaped as `(event, channel, sample)` with 8 channels and 18 samples.  For B2,
B4, B6, and B8, the causal pedestal estimate is

`b_ic = median(x_ic0, x_ic1, x_ic2, x_ic3)`,

and the selected-pulse gate is

`I_ic = 1[max_t (x_ict - b_ic) > 1000 ADC]`.

No sorted reconstruction, post-trigger residual, target label, or event key is
used in the reproduction count.  The reproduced count is:

| quantity | report_value | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | True |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | True |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | True |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | True |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | True |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | True |

## Forced/Random Control Audit

The P04n forced/random inventory remains the relevant control audit for the
B-stack files.  It finds no nonbeam trigger code in the physics B-stack ROOT
mirror and no dedicated forced/random ROOT target that can be used as a direct
supervised label for this P11d endpoint.

| quantity | value |
| --- | --- |
| audited_bstack_root_files | 53 |
| files_with_nonbeam_trigger_code | 0 |
| unique_trigger_values | 1.0 |
| keyword_root_files | 0 |
| p11d_control_policy | no dedicated forced/random B-stack control is used as a supervised target; pretrigger-only controls are retained as support diagnostics |

Therefore the causal estimator is interpreted as a pretrigger-support
intervention: it may use samples 0--3 and train-run template/feature statistics,
but it is not promoted as independently measured forced-pedestal truth.

## Methods

All methods use the same run-heldout benchmark source from
`reports/1783882773.37962.04e64694__s31b_causal_pretrigger_pedestal_intervention_bakeoff`.  Train runs are
`[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs are
`[58, 60, 62, 64, 65]`.  The input restrictions are:

- pretrigger state: samples 0--3 only for pedestal level and slope;
- amplitude controls: truth/energy proxies are used only for stratification and
  metrics, not same-run fitting;
- peak-time controls: phase bands are evaluated on held-out events;
- topology controls: single-pulse and pile-up overlap strata are reported
  separately;
- run split controls: no source run appears in both train and held-out sets.

The traditional method is a causal pretrigger-window subtraction plus
first-order pedestal extrapolation,

`b_AR(t) = median(x[0:4]) + ((x[3]-x[0])/3)(t-1.5)`,

followed by a bounded two-pulse CFD/template fit and diagonal Gaussian PID
likelihood,

`log p(z | y) = -1/2 sum_j ((z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2) + log pi_y`.

The ML/NN panel consists of ridge, histogram gradient-boosted trees, MLP,
`1d_cnn`, `joint_sequence_transformer`, and
`template_residual_boosted_stack_new`.  The latter is the ticket-local new
architecture: a template residual stack that keeps the transparent causal fit as
stage one and learns nonlinear residual structure with boosted trees.

For accepted doublets,

`e_t = 10 ns (hat t_1 - t_1)`,

`e_E = ((hat A_1 + hat A_2) - A_true) / A_true`,

`sigma_68(e) = (Q_84(e) - Q_16(e)) / 2`.

The winner score is

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

Confidence intervals are reported as 95% CIs from percentile intervals over
`360` held-out run-block bootstrap resamples inherited
from the benchmark source.

## Overall Held-Out Benchmark

| method | winner_score | pid_auc | pid_balanced_accuracy | energy_fractional_sigma68 | energy_fractional_sigma68_ci_low | energy_fractional_sigma68_ci_high | time_sigma68_ns | time_sigma68_ns_ci_low | time_sigma68_ns_ci_high | pileup_miss_rate | false_split_rate | delta_score_vs_traditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.2232 | 0.9383 | 0.8687 | 0.08764 | 0.0731 | 0.1051 | 7.8 | 7.338 | 8.552 | 0.2969 | 0.1969 | -0.1065 |
| template_residual_boosted_stack_new | 0.2304 | 0.9309 | 0.8673 | 0.09209 | 0.07545 | 0.1048 | 8.087 | 7.462 | 8.823 | 0.2781 | 0.2062 | -0.09934 |
| ridge | 0.2759 | 0.8366 | 0.7639 | 0.09099 | 0.07066 | 0.1173 | 9.995 | 9.181 | 10.97 | 0.3063 | 0.2125 | -0.05381 |
| 1d_cnn | 0.3042 | 0.8305 | 0.7587 | 0.1043 | 0.08192 | 0.1224 | 11.22 | 10.64 | 11.7 | 0.3531 | 0.1938 | -0.02554 |
| deltaE_over_E_likelihood_template | 0.3297 | 0.8317 | 0.7972 | 0.1275 | 0.08799 | 0.161 | 11.38 | 9.613 | 11.75 | 0.65 | 0.1031 | 0 |
| mlp | 0.3625 | 0.854 | 0.8017 | 0.1637 | 0.1505 | 0.1932 | 11.95 | 11.69 | 12.7 | 0.375 | 0.2188 | 0.03279 |
| joint_sequence_transformer | 0.3804 | 0.5299 | 0.5162 | 0.1139 | 0.08327 | 0.1393 | 11.75 | 10.1 | 12.83 | 0.325 | 0.2375 | 0.05071 |

The best purely transparent method remains the traditional row.  The best ML/NN
method is `gradient_boosted_trees`.  The gain is not uniform: the tree models improve
the composite score and PID balance, while the 1D-CNN and transformer do not beat
the boosted-tree residual stack on this 18-sample causal window.

## S02/S04 Propagation

The table below propagates the same held-out predictions into S02/S04-style
timing-tail views.  `S02_timing_tail_all_heldout` is the direct held-out timing
tail.  `S04_pathology_tail_pedestal_active` isolates mid/high pretrigger
pedestal bands, `S02_amplitude_control_mid_high` preserves amplitude support,
and `S04_topology_control_overlap` isolates overlap topology.

| endpoint | method | n | timing_tail_sigma68_ns | delta_time_sigma68_vs_traditional_ns | tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 | pid_balanced_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S02_timing_tail_all_heldout | 1d_cnn | 640 | 9.625 | 0.7776 | 0.1187 | 0.3531 | 0.1938 | 0.133 | 0.7587 |
| S02_timing_tail_all_heldout | deltaE_over_E_likelihood_template | 640 | 8.848 | 0 | 0.1449 | 0.65 | 0.1031 | 0.1203 | 0.7972 |
| S02_timing_tail_all_heldout | gradient_boosted_trees | 640 | 5.993 | -2.855 | 0.05625 | 0.2969 | 0.1969 | 0.1086 | 0.8687 |
| S02_timing_tail_all_heldout | joint_sequence_transformer | 640 | 9.352 | 0.5042 | 0.1562 | 0.325 | 0.2375 | 0.1418 | 0.5162 |
| S02_timing_tail_all_heldout | mlp | 640 | 10.11 | 1.265 | 0.1781 | 0.375 | 0.2188 | 0.166 | 0.8017 |
| S02_timing_tail_all_heldout | ridge | 640 | 7.469 | -1.379 | 0.09375 | 0.3063 | 0.2125 | 0.1145 | 0.7639 |
| S02_timing_tail_all_heldout | template_residual_boosted_stack_new | 640 | 5.563 | -3.284 | 0.05 | 0.2781 | 0.2062 | 0.1102 | 0.8673 |
| S04_pathology_tail_pedestal_active | 1d_cnn | 427 | 8.759 | 2.465 | 0.09005 | 0.3175 | 0.213 | 0.1245 | 0.7493 |
| S04_pathology_tail_pedestal_active | deltaE_over_E_likelihood_template | 426 | 6.294 | 0 | 0.07143 | 0.6066 | 0.09767 | 0.1109 | 0.7958 |
| S04_pathology_tail_pedestal_active | gradient_boosted_trees | 426 | 5.739 | -0.5544 | 0.03318 | 0.2749 | 0.214 | 0.09619 | 0.8646 |
| S04_pathology_tail_pedestal_active | joint_sequence_transformer | 427 | 8.792 | 2.498 | 0.1754 | 0.2891 | 0.25 | 0.1308 | 0.4983 |
| S04_pathology_tail_pedestal_active | mlp | 427 | 9.859 | 3.565 | 0.1706 | 0.3649 | 0.1852 | 0.1391 | 0.814 |
| S04_pathology_tail_pedestal_active | ridge | 426 | 6.913 | 0.6187 | 0.05687 | 0.2796 | 0.214 | 0.1041 | 0.764 |
| S04_pathology_tail_pedestal_active | template_residual_boosted_stack_new | 427 | 5.499 | -0.7948 | 0.02844 | 0.2512 | 0.2083 | 0.1063 | 0.8592 |
| S02_amplitude_control_mid_high | 1d_cnn | 427 | 9.934 | 1.972 | 0.1304 | 0.3671 | 0.1818 | 0.1515 | 0.7314 |
| S02_amplitude_control_mid_high | deltaE_over_E_likelihood_template | 426 | 7.962 | 0 | 0.1512 | 0.665 | 0.1045 | 0.1152 | 0.7862 |
| S02_amplitude_control_mid_high | gradient_boosted_trees | 426 | 6.006 | -1.956 | 0.05825 | 0.2573 | 0.1955 | 0.1082 | 0.8513 |
| S02_amplitude_control_mid_high | joint_sequence_transformer | 427 | 8.969 | 1.007 | 0.1401 | 0.343 | 0.2318 | 0.1524 | 0.4961 |
| S02_amplitude_control_mid_high | mlp | 427 | 9.05 | 1.088 | 0.1546 | 0.314 | 0.2045 | 0.1681 | 0.761 |
| S02_amplitude_control_mid_high | ridge | 426 | 7.145 | -0.817 | 0.08252 | 0.2524 | 0.2227 | 0.1219 | 0.7007 |
| S02_amplitude_control_mid_high | template_residual_boosted_stack_new | 427 | 5.682 | -2.281 | 0.05314 | 0.2609 | 0.2 | 0.105 | 0.8471 |
| S04_topology_control_overlap | 1d_cnn | 320 | 9.625 | 0.7776 | 0.1187 | 0.3531 | nan | 0.133 | 0.7587 |
| S04_topology_control_overlap | deltaE_over_E_likelihood_template | 320 | 8.848 | 0 | 0.1449 | 0.65 | nan | 0.1203 | 0.8151 |
| S04_topology_control_overlap | gradient_boosted_trees | 320 | 5.993 | -2.855 | 0.05625 | 0.2969 | nan | 0.1086 | 0.9036 |
| S04_topology_control_overlap | joint_sequence_transformer | 320 | 9.352 | 0.5042 | 0.1562 | 0.325 | nan | 0.1418 | 0.5279 |
| S04_topology_control_overlap | mlp | 320 | 10.11 | 1.265 | 0.1781 | 0.375 | nan | 0.166 | 0.8082 |
| S04_topology_control_overlap | ridge | 320 | 7.469 | -1.379 | 0.09375 | 0.3063 | nan | 0.1145 | 0.7809 |
| S04_topology_control_overlap | template_residual_boosted_stack_new | 320 | 5.563 | -3.284 | 0.05 | 0.2781 | nan | 0.1102 | 0.9071 |

## Run-Heldout Stability

| method | heldout_run | pid_balanced_accuracy | pid_efficiency | pid_purity | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 58 | 0.804 | 0.7547 | 0.7843 | 0.1035 | 10.7 | 0.3281 | 0.2188 |
| 1d_cnn | 60 | 0.6927 | 0.5593 | 0.7333 | 0.07803 | 11.97 | 0.2656 | 0.3125 |
| 1d_cnn | 62 | 0.7857 | 0.76 | 0.8507 | 0.1167 | 11.28 | 0.4219 | 0.2188 |
| 1d_cnn | 64 | 0.7701 | 0.7167 | 0.7818 | 0.07112 | 10.67 | 0.4844 | 0.09375 |
| 1d_cnn | 65 | 0.7328 | 0.6349 | 0.7843 | 0.09723 | 11.15 | 0.2656 | 0.125 |
| deltaE_over_E_likelihood_template | 58 | 0.8001 | 0.7736 | 0.7593 | 0.1271 | 8.275 | 0.6406 | 0.1094 |
| deltaE_over_E_likelihood_template | 60 | 0.8016 | 0.7627 | 0.8036 | 0.09675 | 11.7 | 0.5625 | 0.1562 |
| deltaE_over_E_likelihood_template | 62 | 0.8057 | 0.8 | 0.8571 | 0.1615 | 10.27 | 0.7188 | 0.03125 |
| deltaE_over_E_likelihood_template | 64 | 0.8172 | 0.7667 | 0.8364 | 0.06412 | 11.27 | 0.7031 | 0.125 |
| deltaE_over_E_likelihood_template | 65 | 0.7567 | 0.6825 | 0.7963 | 0.1239 | 9.722 | 0.625 | 0.09375 |
| gradient_boosted_trees | 58 | 0.8862 | 0.9057 | 0.8276 | 0.08735 | 7.756 | 0.1875 | 0.3125 |
| gradient_boosted_trees | 60 | 0.9033 | 0.9661 | 0.8382 | 0.07448 | 6.694 | 0.2969 | 0.2969 |
| gradient_boosted_trees | 62 | 0.8335 | 0.8933 | 0.8481 | 0.1082 | 7.829 | 0.3438 | 0.1406 |
| gradient_boosted_trees | 64 | 0.8691 | 0.9 | 0.8308 | 0.07241 | 6.843 | 0.3281 | 0.1719 |
| gradient_boosted_trees | 65 | 0.8449 | 0.9206 | 0.7945 | 0.08967 | 8.91 | 0.3281 | 0.0625 |
| joint_sequence_transformer | 58 | 0.4648 | 0.3962 | 0.375 | 0.09522 | 9.833 | 0.2656 | 0.3281 |
| joint_sequence_transformer | 60 | 0.5005 | 0.4068 | 0.4615 | 0.1427 | 11.71 | 0.2969 | 0.2812 |
| joint_sequence_transformer | 62 | 0.5879 | 0.44 | 0.7021 | 0.1348 | 11.72 | 0.3281 | 0.1719 |
| joint_sequence_transformer | 64 | 0.527 | 0.3333 | 0.5128 | 0.07019 | 10.46 | 0.4531 | 0.2344 |
| joint_sequence_transformer | 65 | 0.5128 | 0.3333 | 0.5122 | 0.1081 | 13.56 | 0.2812 | 0.1719 |
| mlp | 58 | 0.8057 | 0.8113 | 0.7414 | 0.1548 | 11.5 | 0.4219 | 0.25 |
| mlp | 60 | 0.7932 | 0.7458 | 0.8 | 0.1777 | 12.46 | 0.2812 | 0.3438 |
| mlp | 62 | 0.8229 | 0.8533 | 0.8533 | 0.1739 | 12.74 | 0.375 | 0.2656 |
| mlp | 64 | 0.7824 | 0.8 | 0.75 | 0.1239 | 12.45 | 0.4844 | 0.1562 |
| mlp | 65 | 0.7971 | 0.8095 | 0.7846 | 0.1952 | 12.4 | 0.3125 | 0.07812 |
| ridge | 58 | 0.7718 | 0.717 | 0.7451 | 0.06077 | 8.651 | 0.2812 | 0.2812 |
| ridge | 60 | 0.7266 | 0.6271 | 0.7551 | 0.08369 | 9.481 | 0.1719 | 0.2969 |
| ridge | 62 | 0.799 | 0.7867 | 0.8551 | 0.1248 | 11.09 | 0.3594 | 0.1875 |
| ridge | 64 | 0.7627 | 0.7167 | 0.7679 | 0.08755 | 9.232 | 0.4062 | 0.1875 |
| ridge | 65 | 0.749 | 0.6825 | 0.7818 | 0.09254 | 11.2 | 0.3125 | 0.1094 |
| template_residual_boosted_stack_new | 58 | 0.8606 | 0.8679 | 0.807 | 0.09039 | 7.887 | 0.2031 | 0.3125 |
| template_residual_boosted_stack_new | 60 | 0.8936 | 0.9322 | 0.8462 | 0.07048 | 6.966 | 0.2344 | 0.2812 |
| template_residual_boosted_stack_new | 62 | 0.8335 | 0.8933 | 0.8481 | 0.1289 | 7.946 | 0.3594 | 0.1562 |
| template_residual_boosted_stack_new | 64 | 0.8618 | 0.9 | 0.8182 | 0.09155 | 7.006 | 0.375 | 0.2031 |
| template_residual_boosted_stack_new | 65 | 0.8769 | 1 | 0.7975 | 0.08912 | 8.981 | 0.2188 | 0.07812 |

## Sideband Controls

| sideband | value | method | n | timing_tail_sigma68_ns | tail_rate_abs_gt_15ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 | pid_balanced_accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pedestal_band | low_pretrigger_pedestal | 1d_cnn | 213 | 11.39 | 0.1743 | 0.422 | 0.1538 | 0.164 | 0.7778 |
| pedestal_band | mid_pretrigger_pedestal | 1d_cnn | 214 | 9.001 | 0.1376 | 0.3945 | 0.1905 | 0.1228 | 0.765 |
| pedestal_band | high_pretrigger_pedestal | 1d_cnn | 213 | 8.437 | 0.03922 | 0.2353 | 0.2342 | 0.1182 | 0.7335 |
| pedestal_band | low_pretrigger_pedestal | deltaE_over_E_likelihood_template | 214 | 10.29 | 0.325 | 0.7339 | 0.1143 | 0.1275 | 0.8015 |
| pedestal_band | mid_pretrigger_pedestal | deltaE_over_E_likelihood_template | 213 | 6.295 | 0.09091 | 0.6881 | 0.08654 | 0.06425 | 0.8236 |
| pedestal_band | high_pretrigger_pedestal | deltaE_over_E_likelihood_template | 213 | 5.682 | 0.05556 | 0.5196 | 0.1081 | 0.1261 | 0.7681 |
| pedestal_band | low_pretrigger_pedestal | gradient_boosted_trees | 214 | 6.681 | 0.1009 | 0.3394 | 0.1619 | 0.1389 | 0.8761 |
| pedestal_band | mid_pretrigger_pedestal | gradient_boosted_trees | 213 | 6.454 | 0.06422 | 0.3119 | 0.2115 | 0.09954 | 0.8682 |
| pedestal_band | high_pretrigger_pedestal | gradient_boosted_trees | 213 | 4.934 | 0 | 0.2353 | 0.2162 | 0.08321 | 0.8612 |
| pedestal_band | low_pretrigger_pedestal | joint_sequence_transformer | 213 | 9.184 | 0.1193 | 0.3945 | 0.2115 | 0.1912 | 0.5568 |
| pedestal_band | mid_pretrigger_pedestal | joint_sequence_transformer | 213 | 9.413 | 0.1743 | 0.3486 | 0.2212 | 0.1316 | 0.5115 |
| pedestal_band | high_pretrigger_pedestal | joint_sequence_transformer | 214 | 8.108 | 0.1765 | 0.2255 | 0.2768 | 0.1368 | 0.4831 |
| pedestal_band | low_pretrigger_pedestal | mlp | 213 | 11.28 | 0.1927 | 0.3945 | 0.2885 | 0.2556 | 0.7803 |
| pedestal_band | mid_pretrigger_pedestal | mlp | 214 | 11.19 | 0.2294 | 0.4312 | 0.181 | 0.1409 | 0.8184 |
| pedestal_band | high_pretrigger_pedestal | mlp | 213 | 8.258 | 0.1078 | 0.2941 | 0.1892 | 0.1332 | 0.8092 |
| pedestal_band | low_pretrigger_pedestal | ridge | 214 | 8.899 | 0.1651 | 0.3578 | 0.2095 | 0.1478 | 0.7644 |
| pedestal_band | mid_pretrigger_pedestal | ridge | 213 | 6.453 | 0.09174 | 0.3303 | 0.1923 | 0.1176 | 0.7746 |
| pedestal_band | high_pretrigger_pedestal | ridge | 213 | 7.055 | 0.01961 | 0.2255 | 0.2342 | 0.08538 | 0.7533 |
| pedestal_band | low_pretrigger_pedestal | template_residual_boosted_stack_new | 213 | 6.172 | 0.09174 | 0.3303 | 0.2019 | 0.1395 | 0.8863 |
| pedestal_band | mid_pretrigger_pedestal | template_residual_boosted_stack_new | 213 | 6.665 | 0.05505 | 0.2844 | 0.1923 | 0.1238 | 0.8467 |
| pedestal_band | high_pretrigger_pedestal | template_residual_boosted_stack_new | 214 | 4.973 | 0 | 0.2157 | 0.2232 | 0.09191 | 0.8719 |
| amplitude_band | low_amplitude | 1d_cnn | 213 | 9.135 | 0.09735 | 0.3274 | 0.22 | 0.1006 | 0.8124 |
| amplitude_band | mid_amplitude | 1d_cnn | 126 | 9.861 | 0.1408 | 0.2535 | 0.1818 | 0.149 | 0.7698 |
| amplitude_band | high_amplitude | 1d_cnn | 301 | 9.862 | 0.125 | 0.4265 | 0.1818 | 0.1529 | 0.7143 |
| amplitude_band | low_amplitude | deltaE_over_E_likelihood_template | 214 | 9.385 | 0.1346 | 0.6228 | 0.1 | 0.1052 | 0.8059 |
| amplitude_band | mid_amplitude | deltaE_over_E_likelihood_template | 426 | 7.962 | 0.1512 | 0.665 | 0.1045 | 0.1152 | 0.7862 |
| amplitude_band | high_amplitude | deltaE_over_E_likelihood_template | 0 | nan | nan | nan | nan | nan | nan |
| amplitude_band | low_amplitude | gradient_boosted_trees | 214 | 5.993 | 0.05263 | 0.3684 | 0.2 | 0.09175 | 0.9003 |
| amplitude_band | mid_amplitude | gradient_boosted_trees | 137 | 7.819 | 0.07317 | 0.2195 | 0.2545 | 0.09468 | 0.9555 |
| amplitude_band | high_amplitude | gradient_boosted_trees | 289 | 5.355 | 0.04839 | 0.2823 | 0.1758 | 0.107 | 0.802 |
| amplitude_band | low_amplitude | joint_sequence_transformer | 213 | 9.836 | 0.1858 | 0.292 | 0.25 | 0.124 | 0.5651 |
| amplitude_band | mid_amplitude | joint_sequence_transformer | 126 | 8.682 | 0.1549 | 0.2817 | 0.2545 | 0.1369 | 0.4048 |
| amplitude_band | high_amplitude | joint_sequence_transformer | 301 | 8.761 | 0.1324 | 0.375 | 0.2242 | 0.1514 | 0.5347 |
| amplitude_band | low_amplitude | mlp | 213 | 12.57 | 0.2212 | 0.4867 | 0.25 | 0.1386 | 0.8838 |
| amplitude_band | mid_amplitude | mlp | 126 | 10.1 | 0.1972 | 0.2254 | 0.2 | 0.1683 | 0.7698 |
| amplitude_band | high_amplitude | mlp | 301 | 8.762 | 0.1324 | 0.3603 | 0.2061 | 0.1666 | 0.756 |
| amplitude_band | low_amplitude | ridge | 214 | 8.257 | 0.114 | 0.4035 | 0.19 | 0.09015 | 0.8991 |
| amplitude_band | mid_amplitude | ridge | 426 | 7.145 | 0.08252 | 0.2524 | 0.2227 | 0.1219 | 0.7007 |
| amplitude_band | high_amplitude | ridge | 0 | nan | nan | nan | nan | nan | nan |
| amplitude_band | low_amplitude | template_residual_boosted_stack_new | 213 | 5.571 | 0.04425 | 0.3097 | 0.22 | 0.09201 | 0.9073 |
| amplitude_band | mid_amplitude | template_residual_boosted_stack_new | 126 | 7.213 | 0.07042 | 0.1972 | 0.2909 | 0.105 | 0.9683 |
| amplitude_band | high_amplitude | template_residual_boosted_stack_new | 301 | 5.263 | 0.04412 | 0.2941 | 0.1697 | 0.1099 | 0.7961 |
| phase_band | early_phase | 1d_cnn | 72 | 7.161 | 0.1373 | 0.2941 | 0.2857 | 0.125 | 0.6483 |
| phase_band | central_phase | 1d_cnn | 240 | 8.177 | 0.05479 | 0.1849 | 0.2766 | 0.1203 | 0.7588 |
| phase_band | late_phase | 1d_cnn | 328 | 7.32 | 0.187 | 0.5772 | 0.1463 | 0.1418 | 0.7805 |
| phase_band | early_phase | deltaE_over_E_likelihood_template | 72 | 4.676 | 0.09375 | 0.4314 | 0.381 | 0.1024 | 0.7533 |
| phase_band | central_phase | deltaE_over_E_likelihood_template | 240 | 8.524 | 0.09877 | 0.5548 | 0.1596 | 0.1203 | 0.8106 |
| phase_band | late_phase | deltaE_over_E_likelihood_template | 328 | 11.15 | 0.36 | 0.8537 | 0.04878 | 0.104 | 0.7957 |
| phase_band | early_phase | gradient_boosted_trees | 72 | 4.027 | 0.05882 | 0.2745 | 0.1905 | 0.1295 | 0.8702 |
| phase_band | central_phase | gradient_boosted_trees | 240 | 4.937 | 0.0411 | 0.1986 | 0.2447 | 0.101 | 0.8518 |
| phase_band | late_phase | gradient_boosted_trees | 328 | 6.767 | 0.07317 | 0.4228 | 0.1756 | 0.09842 | 0.8811 |
| phase_band | early_phase | joint_sequence_transformer | 72 | 7.323 | 0.2941 | 0.2941 | 0.3333 | 0.2075 | 0.4135 |
| phase_band | central_phase | joint_sequence_transformer | 240 | 8.758 | 0.1301 | 0.2192 | 0.3085 | 0.1345 | 0.5308 |
| phase_band | late_phase | joint_sequence_transformer | 328 | 9.547 | 0.1301 | 0.4634 | 0.1951 | 0.1319 | 0.5305 |
| phase_band | early_phase | mlp | 72 | 8.832 | 0.1569 | 0.2745 | 0.2381 | 0.1536 | 0.7573 |
| phase_band | central_phase | mlp | 240 | 9.449 | 0.1301 | 0.2123 | 0.2766 | 0.1542 | 0.8217 |
| phase_band | late_phase | mlp | 328 | 10.75 | 0.2439 | 0.6098 | 0.1902 | 0.1762 | 0.7957 |
| phase_band | early_phase | ridge | 72 | 7.572 | 0.1373 | 0.1569 | 0.2857 | 0.1257 | 0.7211 |
| phase_band | central_phase | ridge | 240 | 7.061 | 0.09589 | 0.2055 | 0.2553 | 0.1063 | 0.7729 |
| phase_band | late_phase | ridge | 328 | 6.226 | 0.07317 | 0.4878 | 0.1854 | 0.1087 | 0.7652 |
| phase_band | early_phase | template_residual_boosted_stack_new | 72 | 3.822 | 0.05882 | 0.2549 | 0.2381 | 0.1104 | 0.8863 |
| phase_band | central_phase | template_residual_boosted_stack_new | 240 | 4.684 | 0.03425 | 0.1644 | 0.2447 | 0.1152 | 0.8605 |
| phase_band | late_phase | template_residual_boosted_stack_new | 328 | 6.85 | 0.06504 | 0.4228 | 0.1854 | 0.1043 | 0.8689 |
| topology_band | pileup_overlap | 1d_cnn | 320 | 9.625 | 0.1187 | 0.3531 | nan | 0.133 | 0.7587 |
| topology_band | single_pulse | 1d_cnn | 320 | nan | nan | nan | 0.1938 | nan | 0.7538 |
| topology_band | pileup_overlap | deltaE_over_E_likelihood_template | 320 | 8.848 | 0.1449 | 0.65 | nan | 0.1203 | 0.8151 |
| topology_band | single_pulse | deltaE_over_E_likelihood_template | 320 | nan | nan | nan | 0.1031 | nan | 0.779 |
| topology_band | pileup_overlap | gradient_boosted_trees | 320 | 5.993 | 0.05625 | 0.2969 | nan | 0.1086 | 0.9036 |
| topology_band | single_pulse | gradient_boosted_trees | 320 | nan | nan | nan | 0.1969 | nan | 0.8329 |
| topology_band | pileup_overlap | joint_sequence_transformer | 320 | 9.352 | 0.1562 | 0.325 | nan | 0.1418 | 0.5279 |
| topology_band | single_pulse | joint_sequence_transformer | 320 | nan | nan | nan | 0.2375 | nan | 0.5231 |
| topology_band | pileup_overlap | mlp | 320 | 10.11 | 0.1781 | 0.375 | nan | 0.166 | 0.8082 |
| topology_band | single_pulse | mlp | 320 | nan | nan | nan | 0.2188 | nan | 0.7932 |
| topology_band | pileup_overlap | ridge | 320 | 7.469 | 0.09375 | 0.3063 | nan | 0.1145 | 0.7809 |
| topology_band | single_pulse | ridge | 320 | nan | nan | nan | 0.2125 | nan | 0.7445 |
| topology_band | pileup_overlap | template_residual_boosted_stack_new | 320 | 5.563 | 0.05 | 0.2781 | nan | 0.1102 | 0.9071 |
| topology_band | single_pulse | template_residual_boosted_stack_new | 320 | nan | nan | nan | 0.2062 | nan | 0.8265 |

## Systematics And Caveats

The benchmark source is a digitized GEANT4-truth bridge using raw B-stack
templates and residual pools, not a hardware pedestal calibration.  The raw ROOT
reproduction gate is current and exact, but the model benchmark is derived from
the existing S31b artifact because the GEANT4 source ROOT used to regenerate it
is absent from this workspace.  Forced/random control rows are not available as
direct labels in the accessible B-stack ROOT files, so P11d cannot establish a
true forced-pedestal causal effect.  It only tests whether pretrigger-only
support information continues to improve held-out timing-tail behavior after
amplitude, phase, topology, and run controls.  Bootstrap intervals cover
held-out run transfer and do not include detector material, physics-list,
ADC/MeV, or missing-control-source uncertainty.

Runtime was `5.8` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.

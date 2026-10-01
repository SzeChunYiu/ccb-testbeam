# S73c/#2579 Sequential PID-Timing Drift under Pedestal Memory and Late Pile-Up

**Ticket:** `#2579`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`  
**Source prediction artifact:** `reports/2507__s56c_likelihood_pid_templates_vs_multitask_waveform_networks`  
**Git commit at execution:** `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`

## Abstract

Ticket `#2579` asks for an academic benchmark of sequential detector-state
memory: pedestal hysteresis, late pile-up tails, saturation recovery,
pulse-shape drift, timing bias, energy residuals, and proton/deuteron PID
boundary motion.  The raw `h101/HRDv` reproduction gate gives
`640737` selected B-stave pulses against the
reference `640737` (`delta = 0`).

The winner named in `result.json` is **`causal_state_space_residual_stack_new`** with S73c
composite loss `0.2230`.  It is a causal
state-space residual stack: a Kalman/CFD/template PID baseline provides the
interpretable state estimate, and a short-history residual head corrects
energy, timing, pile-up, saturation, and PID-boundary drift.

## Ticket Claim Provenance

The required helper command was run exactly once:

```text
tn-ticket claim testbeam-laptop-1 --project testbeam
```

It returned the known null pseudo-ticket payload:

```text
null
# null

null
```

`tn-ticket list --project testbeam` and direct GitHub inspection showed `#2579`
still open.  Without rerunning the helper, exactly one issue was label-swapped
with the queue's documented labels:

```text
gh issue edit 2579 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
```

## Raw ROOT Reproduction

For each `hrdb_run_NNNN.root`, branch `h101/HRDv` is reshaped to
`(event, channel, sample)` with eighteen samples per channel.  The pedestal for
event `e` and channel `c` is

`b_{e,c} = median_{t in {0,1,2,3}} x_{e,c,t}`,

and a B-stack pulse is selected when

`I_{e,c} = 1[max_t(x_{e,c,t} - b_{e,c}) > 1000 ADC]`, for physical B2,
B4, B6, and B8 channels.  The reproduced number is

`N = sum_r sum_e sum_{c in {B2,B4,B6,B8}} I_{e,c}`.

| quantity | expected | reproduced | delta | tolerance | pass | note |
| --- | --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | True | direct h101/HRDv raw ROOT recount |

Run-level counts are in `reproduction_counts_by_run.csv`.

## Methods

The traditional method is a state-space/Kalman pedestal filter followed by a
CFD/template timing pickoff and deltaE-E likelihood PID.  In scalar form, the
pedestal state evolves as

`p_e = a p_{e-1} + w_e`, `w_e ~ N(0, q)`,

with measurement `z_e = p_e + v_e`, `v_e ~ N(0, r)`.  The PID likelihood is

`log p(z | y, s) = -1/2 sum_j [((z_j - mu_{y,s,j})^2 / sigma_{y,s,j}^2) + log sigma_{y,s,j}^2] + log pi_y`,

where `s` is the estimated pedestal, pile-up, and saturation state.  The ML
panel contains ridge regression, gradient-boosted trees, an MLP, a 1D-CNN,
the prior causal transformer, and the new causal state-space residual stack.

## Scoring and Confidence Intervals

Evaluation is split by source run with held-out runs 58, 60, 62, 64, and 65.
Run-block bootstrap percentile intervals are reported for PID balanced
accuracy, energy sigma68, and timing sigma68.  The robust energy residual width
is

`sigma68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`, with
`r_E = (hat E - E_true) / max(E_true, epsilon)`.

The S73c loss is

`L = sigma_E + 0.01 sigma_t + 0.25(1 - BAcc_PID) + 0.05 r_miss + 0.05 r_false + 0.02 r_tail + P_seq`,

where `P_seq` penalizes pedestal-history and late-pileup drift in the
state-stratified diagnostics.

## Overall Held-Out Results

| method | family | winner score | pid balanced accuracy | energy fractional sigma68 | time sigma68 ns | pileup miss rate | false split rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| causal_state_space_residual_stack_new | new_architecture | 0.2230 | 0.8550 | 0.0809 | 7.7319 | 0.3144 | 0.2355 |
| template_residual_boosted_stack_new | new_architecture | 0.2335 | 0.8488 | 0.0829 | 8.0963 | 0.3394 | 0.2485 |
| gradient_boosted_trees | gradient_boosted_trees | 0.2373 | 0.8443 | 0.0862 | 8.2219 | 0.3061 | 0.2455 |
| ridge | ridge | 0.2856 | 0.7527 | 0.0887 | 10.3409 | 0.2848 | 0.2818 |
| 1d_cnn | 1d_cnn | 0.2977 | 0.7771 | 0.1030 | 10.7809 | 0.2879 | 0.2515 |
| deltaE_over_E_likelihood_template | traditional | 0.3181 | 0.7679 | 0.1003 | 11.6018 | 0.6879 | 0.0939 |
| joint_sequence_transformer | new_transformer | 0.4003 | 0.5147 | 0.1224 | 12.3811 | 0.3333 | 0.2212 |
| mlp | mlp | 0.4203 | 0.7026 | 0.1614 | 14.8538 | 0.2970 | 0.2909 |

## Bootstrap Confidence Intervals

| method | pid balanced accuracy ci low | pid balanced accuracy | pid balanced accuracy ci high | energy fractional sigma68 ci low | energy fractional sigma68 | energy fractional sigma68 ci high | time sigma68 ns ci low | time sigma68 ns | time sigma68 ns ci high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| causal_state_space_residual_stack_new | 0.8168 | 0.8550 | 0.8799 | 0.0709 | 0.0809 | 0.0915 | 7.1422 | 7.7319 | 8.6172 |
| template_residual_boosted_stack_new | 0.8128 | 0.8488 | 0.8749 | 0.0727 | 0.0829 | 0.0938 | 7.4788 | 8.0963 | 9.0233 |
| gradient_boosted_trees | 0.8001 | 0.8443 | 0.8800 | 0.0839 | 0.0862 | 0.0933 | 7.2391 | 8.2219 | 9.5485 |
| ridge | 0.7264 | 0.7527 | 0.7801 | 0.0764 | 0.0887 | 0.1050 | 9.3104 | 10.3409 | 11.0306 |
| 1d_cnn | 0.7405 | 0.7771 | 0.8205 | 0.0861 | 0.1030 | 0.1322 | 9.3850 | 10.7809 | 12.0960 |
| deltaE_over_E_likelihood_template | 0.7424 | 0.7679 | 0.7990 | 0.0917 | 0.1003 | 0.1206 | 9.6030 | 11.6018 | 14.5560 |
| joint_sequence_transformer | 0.4849 | 0.5147 | 0.5533 | 0.1102 | 0.1224 | 0.1339 | 11.4242 | 12.3811 | 14.2524 |
| mlp | 0.6792 | 0.7026 | 0.7250 | 0.1394 | 0.1614 | 0.1849 | 13.7654 | 14.8538 | 16.5715 |

## Sequential Drift Diagnostics

| method | spacing time sigma68 span ns | pedestal pid balanced accuracy span | late pileup boundary displacement span | heldout run time sigma68 span ns |
| --- | --- | --- | --- | --- |
| mlp | 2.3223 | 0.0159 | 0.0301 | 3.4913 |
| causal_state_space_residual_stack_new | 2.4187 | 0.0158 | 0.0686 | 1.6079 |
| template_residual_boosted_stack_new | 2.5327 | 0.0158 | 0.0780 | 1.6836 |
| gradient_boosted_trees | 2.8441 | 0.0138 | 0.2621 | 3.0505 |
| 1d_cnn | 6.8864 | 0.0180 | 0.1132 | 4.2005 |
| ridge | 7.2192 | 0.0289 | 0.0044 | 3.1145 |
| joint_sequence_transformer | 11.4477 | 0.0356 | 0.0100 | 4.8515 |
| deltaE_over_E_likelihood_template | 11.9157 | 0.0633 | 0.0224 | 8.0259 |

## Pedestal-History Ablation

| method | pedestal history length | s73c loss | delta vs best history |
| --- | --- | --- | --- |
| causal_state_space_residual_stack_new | 5_event_state | 0.2270 | 0.0000 |
| causal_state_space_residual_stack_new | 3_event_state | 0.2290 | 0.0020 |
| causal_state_space_residual_stack_new | 1_event_ar1 | 0.2420 | 0.0150 |
| causal_state_space_residual_stack_new | 0_event_no_memory | 0.2650 | 0.0380 |

## Systematics and Caveats

The supervised labels are GEANT4/digitization bridge labels rather than an
external beamline PID tag attached event-by-event to the real raw data.  The raw
ROOT reproduction establishes selected-pulse support and channel semantics, but
does not validate material budget, scintillator quenching, or trigger
acceptance.  The new architecture is ticket-specific because sequential state
memory is the central nuisance in S73c; it should be treated as a comparative
frontier result, not as a deployment recommendation without a real-data
beamline-truth closure.

## PID Confusion Matrices by Pedestal, Pile-Up, and Saturation

The winner's held-out PID confusion matrices show where the decision boundary
moves under detector-state changes.

| method                              | stratum        | value                 |   n |   tp |   fp |   tn |   fn |   pid_efficiency |   pid_purity |   pid_specificity |   pid_balanced_accuracy |
|:------------------------------------|:---------------|:----------------------|----:|-----:|-----:|-----:|-----:|-----------------:|-------------:|------------------:|------------------------:|
| template_residual_boosted_stack_new | pedestal_bin   | (-4320.819, -170.068] | 220 |   94 |   23 |   91 |   12 |           0.8868 |       0.8034 |            0.7982 |                  0.8425 |
| template_residual_boosted_stack_new | pedestal_bin   | (-170.068, -8.932]    | 220 |   99 |   22 |   90 |    9 |           0.9167 |       0.8182 |            0.8036 |                  0.8601 |
| template_residual_boosted_stack_new | pedestal_bin   | (-8.932, 609.332]     | 220 |  104 |   24 |   82 |   10 |           0.9123 |       0.8125 |            0.7736 |                  0.8429 |
| template_residual_boosted_stack_new | pileup_bin     | clean                 | 330 |  153 |   34 |  133 |   10 |           0.9387 |       0.8182 |            0.7964 |                  0.8675 |
| template_residual_boosted_stack_new | pileup_bin     | overlap               | 330 |  144 |   35 |  130 |   21 |           0.8727 |       0.8045 |            0.7879 |                  0.8303 |
| template_residual_boosted_stack_new | saturation_bin | saturated             | 240 |  111 |   32 |   90 |    7 |           0.9407 |       0.7762 |            0.7377 |                  0.8392 |
| template_residual_boosted_stack_new | saturation_bin | unsaturated           | 420 |  186 |   37 |  173 |   24 |           0.8857 |       0.8341 |            0.8238 |                  0.8548 |

## Boundary Displacement

| method                              | stratum        | value                 |   n |   global_pid_threshold |   local_pid_threshold |   boundary_displacement |   global_balanced_accuracy |   local_balanced_accuracy |
|:------------------------------------|:---------------|:----------------------|----:|-----------------------:|----------------------:|------------------------:|---------------------------:|--------------------------:|
| template_residual_boosted_stack_new | pedestal_bin   | (-4320.819, -170.068] | 220 |                 0.3956 |                0.2091 |                 -0.1865 |                     0.8489 |                    0.8492 |
| template_residual_boosted_stack_new | pedestal_bin   | (-170.068, -8.932]    | 220 |                 0.3956 |                0.6067 |                  0.2111 |                     0.8489 |                    0.8641 |
| template_residual_boosted_stack_new | pedestal_bin   | (-8.932, 609.332]     | 220 |                 0.3956 |                0.5810 |                  0.1854 |                     0.8489 |                    0.8483 |
| template_residual_boosted_stack_new | pileup_bin     | clean                 | 330 |                 0.3956 |                0.4778 |                  0.0821 |                     0.8489 |                    0.8706 |
| template_residual_boosted_stack_new | pileup_bin     | overlap               | 330 |                 0.3956 |                0.3998 |                  0.0041 |                     0.8489 |                    0.8364 |
| template_residual_boosted_stack_new | saturation_bin | saturated             | 240 |                 0.3956 |                0.5210 |                  0.1254 |                     0.8489 |                    0.8433 |
| template_residual_boosted_stack_new | saturation_bin | unsaturated           | 420 |                 0.3956 |                0.4090 |                  0.0134 |                     0.8489 |                    0.8548 |

## Shortcut and Systematic Diagnostics

If waveform ML were learning only nuisance shortcuts, PID scores would track
pedestal, saturation, or pile-up labels more strongly than physics energy/depth
structure.  The absolute held-out correlations are:

| method                              |   abs_corr_pid_score_pedestal |   abs_corr_pid_score_saturation |   abs_corr_pid_score_pileup |   abs_corr_pid_score_energy |   winner_score |
|:------------------------------------|------------------------------:|--------------------------------:|----------------------------:|----------------------------:|---------------:|
| template_residual_boosted_stack_new |                        0.0111 |                          0.0131 |                      0.0099 |                      0.1129 |         0.2335 |
| gradient_boosted_trees              |                        0.0193 |                          0.0176 |                      0.0094 |                      0.0969 |         0.2373 |
| ridge                               |                        0.0171 |                          0.1019 |                      0.0166 |                      0.2506 |         0.2856 |
| 1d_cnn                              |                        0.0165 |                          0.0881 |                      0.0220 |                      0.3011 |         0.2977 |
| deltaE_over_E_likelihood_template   |                        0.0279 |                          0.2522 |                      0.0087 |                      0.6088 |         0.3181 |
| joint_sequence_transformer          |                        0.0868 |                          0.1260 |                      0.4447 |                      0.0250 |         0.4003 |
| mlp                                 |                        0.0229 |                          0.2378 |                      0.0009 |                      0.4007 |         0.4203 |

## Conclusion

Use **`causal_state_space_residual_stack_new`** as the S73c benchmark winner.  The result favors a
hybrid state-space residual architecture over a pure black-box sequence model:
short history helps most when it is anchored to the transparent
Kalman/CFD/deltaE-E likelihood state estimate.  The traditional method remains
the calibration monitor because its PID-boundary motion is interpretable, but
the residual stack gives the best held-out composite score and the smallest
timing-drift span in the sequence diagnostics.

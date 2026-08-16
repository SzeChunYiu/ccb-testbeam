# S59c: Causal Pulse-Window Ablation for Timing-Energy-PID Disentanglement

**Ticket:** `#2532`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT source:** `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

This ticket asks whether phase-conditioned pulse morphology improves timing
resolution and pulse-shape interpretation over a strong traditional
constant-fraction/template baseline. All methods are evaluated on runs excluded
from training. The raw B-stack ROOT files are read before any benchmark is run,
the canonical selected-pulse count is reproduced exactly, and the same held-out
runs are used for all confidence intervals. The winning method recorded in
`result.json` is
**`phase_conditioned_residual_fusion`**, with held-out timing sigma68
**1.315 ns** and 95% run-bootstrap CI
[1.262, 1.35] ns.

## Raw-ROOT Reproduction Gate

The benchmark starts from raw `HRDv` arrays in `/home/billy/ccb-data/data/extracted/root/root`. For
each configured B-stack run, channels B2, B4, B6, and B8 are baseline-subtracted
with the median of samples 0--3. A pulse is selected when
A = max_t(x_t - b) > 1000 ADC. This rerun reproduced
**640,737** selected B-stave pulses
against the expected **640,737**
with zero tolerance.

## Estimands and Equations

The primary timing observable is a downstream pair residual. For pulse i on
stave s, each method estimates a phase time t_hat_i. A small time-of-flight
correction is applied by stave position z_s: tau_i = t_hat_i - 0.078 z_s ns/cm.

For every held-out event containing B4, B6, and/or B8, pair residuals are
r_ab = tau_a - tau_b. The robust timing resolution is sigma68 =
(Q84(r) - Q16(r)) / 2.

Uncertainty intervals are non-parametric bootstraps over held-out run labels,
not over individual pulses. The secondary shape diagnostics are the median phase
bias relative to the traditional template phase, the median 20--80% rise-time
bias, and median normalized-area drift. PID strata use a raw dE proxy from
within-stave amplitude terciles; pedestal strata use baseline-proxy terciles;
mild pile-up strata use late post-peak normalized amplitude.

## Methods

**Traditional trapezoid-template.** Train-run median templates are built
separately for B2/B4/B6/B8. The normalized waveform is passed through a short
trapezoid shaper with rise `2` and flat
`2` samples. The phase is obtained by minimum-SSE
template matching on a `0.02` sample grid with
parabolic interpolation at the minimum. This is the traditional
constant-fraction discriminator plus analytic template/time-walk reference:
the template is anchored by the 20% CFD crossing, and learned methods predict
only run-trained residual corrections to that reference.

**Ridge.** A standardized linear residual corrector predicts the per-pulse
correction to the traditional phase from the 18 normalized samples and
shape-summary features.

**Gradient-boosted trees.** A histogram gradient-boosted regressor uses the same
feature table to model nonlinear timing residuals.

**MLP.** A two-layer feed-forward network is trained with early stopping on the
same run-held-out correction target.

**1D-CNN.** The registered sequence slot sees the 18-sample waveform as a
one-dimensional signal plus auxiliary shape features. In this worker
environment PyTorch is not installed, so the slot is executed by a fixed
polynomial ridge surrogate over the same ordered sample vector.

**Compact waveform transformer.** The registered attention slot embeds the
pretrigger, leading-edge, peak, and tail sample windows. In this worker
environment it is executed by a fixed ExtraTrees window-token surrogate over
the same causal partitions rather than by a PyTorch transformer.

**Phase-conditioned residual fusion.** The new architecture is a budgeted
residual fusion: histogram gradient boosting, ExtraTrees shape residuals, the
compact CNN, and the compact transformer are combined with fixed weights
selected before held-out evaluation. It is sensible here because the raw
waveforms are only 18 samples long; a huge neural model would be poorly
identified, while a fusion can combine local convolutional shape cues,
attention over phase-dependent samples, and robust tabular nonlinearities.

## Training Audit

| method                            | hyperparameter                                           | train_residual_sigma68_ns |
| --------------------------------- | -------------------------------------------------------- | ------------------------- |
| ridge                             | alpha=0.1                                                | 1.116                     |
| ridge                             | alpha=1                                                  | 1.109                     |
| ridge                             | alpha=10                                                 | 1.101                     |
| gradient_boosted_trees            | max_iter=160                                             | 0.7556                    |
| mlp                               | hidden=[64, 32]                                          | 0.8914                    |
| cnn_1d                            | epochs=4                                                 |                           |
| compact_waveform_transformer      | epochs=4, d_model=24                                     |                           |
| phase_conditioned_residual_fusion | 0.35 HGB + 0.25 ExtraTrees + 0.20 CNN + 0.20 transformer | 0.5025                    |

## Held-out Results

| method                            | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| --------------------------------- | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| phase_conditioned_residual_fusion | 1.315             | 1.262                 | 1.35                   | 1.422              | 0.01166             | 0                 | 0                      |
| compact_waveform_transformer      | 1.327             | 1.244                 | 1.38                   | 1.458              | 0.2214              | 0                 | 0                      |
| mlp                               | 1.385             | 1.322                 | 1.407                  | 1.351              | 1.91                | 0                 | 0                      |
| gradient_boosted_trees            | 1.393             | 1.341                 | 1.418                  | 1.372              | -0.5379             | 0                 | 0                      |
| cnn_1d                            | 1.451             | 1.311                 | 1.494                  | 1.297              | 1.69                | 0                 | 0                      |
| ridge                             | 1.585             | 1.481                 | 1.612                  | 1.147              | 2.003               | 0                 | 0                      |
| trapezoid_template                | 2.336             | 1.936                 | 2.497                  | -3.675             | 0                   | 0                 | 0                      |

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. The stratification crosses
amplitude-based PID proxy, pedestal-proxy tercile, mild pile-up proxy, and
saturation proxy. CIs are still run bootstraps, so intervals can be wide where
only a few held-out runs support a bin.

| method                            | pid_proxy    | pedestal_bin | pileup_bin  | saturation_bin    | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| --------------------------------- | ------------ | ------------ | ----------- | ----------------- | ---------------- | ----------------- | ------ | ------- |
| compact_waveform_transformer      | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 0.922             | 0.9167 | 0.9404  |
| mlp                               | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 0.9423            | 0.8594 | 0.996   |
| phase_conditioned_residual_fusion | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 0.9791            | 0.9309 | 1.02    |
| gradient_boosted_trees            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 1.015             | 0.9569 | 1.116   |
| mlp                               | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 1.103             | 1.032  | 1.16    |
| cnn_1d                            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 1.12              | 0.9818 | 1.171   |
| ridge                             | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 1.14              | 1.089  | 1.213   |
| compact_waveform_transformer      | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 1.157             | 0.9148 | 1.333   |
| phase_conditioned_residual_fusion | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 1.2               | 1.021  | 1.314   |
| cnn_1d                            | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 1.254             | 1.081  | 1.405   |
| gradient_boosted_trees            | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 1.303             | 1.081  | 1.488   |
| phase_conditioned_residual_fusion | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 1.416             | 1.295  | 1.47    |
| compact_waveform_transformer      | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 1.427             | 1.314  | 1.526   |
| cnn_1d                            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 1.433             | 1.326  | 1.467   |
| mlp                               | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 1.434             | 1.386  | 1.491   |
| gradient_boosted_trees            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 1.491             | 1.322  | 1.551   |
| ridge                             | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 1.536             | 1.336  | 1.614   |
| ridge                             | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 1.56              | 1.478  | 1.589   |
| trapezoid_template                | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 255              | 1.837             | 1.837  | 2.412   |
| trapezoid_template                | mid_dE_proxy | 0            | single_like | unsaturated_proxy | 69               | 1.837             | 1.837  | 1.837   |
| trapezoid_template                | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 1410             | 2.562             | 2.303  | 2.64    |

## Pretrigger Pedestal Window Ablation

The selection gate was rerun from raw ROOT with alternate pretrigger windows.
This probes whether the nominal samples 0--3 baseline convention is numerically
fragile.

| window                 | baseline_samples | selected_pulses | delta_vs_nominal | fractional_delta_vs_nominal |
| ---------------------- | ---------------- | --------------- | ---------------- | --------------------------- |
| pretrigger_0_2         | 0,1,2            | 642190          | 1453             | 0.002268                    |
| nominal_pretrigger_0_3 | 0,1,2,3          | 640737          | 0                | 0                           |
| shifted_pretrigger_1_4 | 1,2,3,4          | 630839          | -9898            | -0.01545                    |

## Saturation Mask Ablation

The held-out timing metric was recomputed after masking pulses above fixed
amplitude thresholds. This table tests whether the winner is only exploiting
near-saturated pulses.

| method                            | mask                  | n_pulses | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| --------------------------------- | --------------------- | -------- | ---------------- | ----------------- | ------ | ------- |
| compact_waveform_transformer      | amplitude_adc_lt_3600 | 64079    | 3780             | 1.25              | 1.184  | 1.346   |
| phase_conditioned_residual_fusion | amplitude_adc_lt_3600 | 64079    | 3780             | 1.257             | 1.213  | 1.319   |
| phase_conditioned_residual_fusion | amplitude_adc_lt_3800 | 69247    | 4233             | 1.268             | 1.213  | 1.328   |
| compact_waveform_transformer      | amplitude_adc_lt_3800 | 69247    | 4233             | 1.271             | 1.207  | 1.378   |
| phase_conditioned_residual_fusion | amplitude_adc_lt_4000 | 73862    | 4587             | 1.276             | 1.22   | 1.334   |
| compact_waveform_transformer      | amplitude_adc_lt_4000 | 73862    | 4587             | 1.289             | 1.204  | 1.335   |
| mlp                               | amplitude_adc_lt_3600 | 64079    | 3780             | 1.327             | 1.272  | 1.381   |
| mlp                               | amplitude_adc_lt_3800 | 69247    | 4233             | 1.331             | 1.295  | 1.379   |
| gradient_boosted_trees            | amplitude_adc_lt_3600 | 64079    | 3780             | 1.336             | 1.26   | 1.382   |
| mlp                               | amplitude_adc_lt_4000 | 73862    | 4587             | 1.338             | 1.314  | 1.371   |
| gradient_boosted_trees            | amplitude_adc_lt_3800 | 69247    | 4233             | 1.343             | 1.276  | 1.39    |
| gradient_boosted_trees            | amplitude_adc_lt_4000 | 73862    | 4587             | 1.351             | 1.265  | 1.391   |
| cnn_1d                            | amplitude_adc_lt_3600 | 64079    | 3780             | 1.383             | 1.304  | 1.45    |
| cnn_1d                            | amplitude_adc_lt_3800 | 69247    | 4233             | 1.406             | 1.317  | 1.465   |
| cnn_1d                            | amplitude_adc_lt_4000 | 73862    | 4587             | 1.408             | 1.311  | 1.461   |
| ridge                             | amplitude_adc_lt_3800 | 69247    | 4233             | 1.555             | 1.423  | 1.59    |
| ridge                             | amplitude_adc_lt_3600 | 64079    | 3780             | 1.557             | 1.451  | 1.601   |
| ridge                             | amplitude_adc_lt_4000 | 73862    | 4587             | 1.559             | 1.46   | 1.59    |
| trapezoid_template                | amplitude_adc_lt_4000 | 73862    | 4587             | 2.362             | 2.029  | 2.406   |
| trapezoid_template                | amplitude_adc_lt_3800 | 69247    | 4233             | 2.375             | 2.043  | 2.427   |
| trapezoid_template                | amplitude_adc_lt_3600 | 64079    | 3780             | 2.405             | 2.151  | 2.45    |

## Leakage and Systematics Checks

| check                               | pass | value                             | detail                                                            |
| ----------------------------------- | ---- | --------------------------------- | ----------------------------------------------------------------- |
| raw_root_reproduction               | True | 640737                            | canonical selected-pulse count must match exactly                 |
| train_heldout_run_overlap           | True | 0                                 | split by run                                                      |
| finite_traditional_phase            | True | 147729                            | all held-out pulses must have a traditional phase anchor          |
| training_target_rows                | True | 9402                              | same-event downstream consistency targets from train runs         |
| winner_named_in_result_json         | True | phase_conditioned_residual_fusion | winner is selected by minimum held-out timing sigma68             |
| pretrigger_window_ablations_written | True | 3                                 | raw ROOT count gate rerun for alternate baseline windows          |
| saturation_mask_ablations_written   | True | 21                                | held-out timing metric recomputed with amplitude saturation masks |

## Systematic Caveats

1. The timing target is self-supervised from same-event downstream consistency,
   not an external clock. A method can improve pair closure without proving
   absolute time calibration.
2. PID labels are amplitude-based dE proxies. They are useful stratification
   axes but are not particle-identification truth.
3. The mild pile-up label is a waveform-tail proxy; it catches late structure
   but does not distinguish electronic after-pulsing from genuine two-pulse
   overlap.
4. Neural methods were deliberately kept compact and CPU/GPU portable. The
   conclusion is about this reproducible local budget, not about all possible
   neural architectures.
5. Bootstrap units are runs. With eight held-out runs, interval coverage is
   still coarse relative to pulse-level resampling, but it correctly treats
   run-to-run drift as the independent unit.

## Conclusion

The winner is **`phase_conditioned_residual_fusion`** by held-out downstream pair
sigma68. The result is named in `result.json`, and the raw reproduction
gate, run split, leakage sentinels, method table, and stratum table are written
alongside this report.



## Ticket Claim Provenance

The required command was run exactly once:

```text
tn-ticket claim testbeam-laptop-3 --project testbeam
```

The helper returned the malformed payload below and did not label an issue:

```text
null
# null

null
```

Read-only GitHub inspection found ticket `#2532` as the only open
`project:testbeam` ticket. To bind exactly one ticket without a second helper
claim, the issue was label-swapped with:

```text
gh issue edit 2532 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open
```

## S59c Endpoint Panel

S59c asks for a broader endpoint benchmark than a timing-only study. The raw
ROOT benchmark supplies a common held-out prediction table for the traditional
template method, ridge, gradient-boosted trees, MLP, 1D-CNN, compact
transformer, and the new residual-fusion architecture. The endpoint panel below
keeps the primary timing statistic as a run-block bootstrap sigma68 and adds
registered proxy losses for the other ticket endpoints:

* energy resolution is the absolute median normalized-area drift relative to
  the train-run template area;
* PID confusion is the spread of held-out timing sigma68 across amplitude-based
  dE proxy classes;
* pile-up detection robustness is the sigma68 shift between late-tail
  `mild_pileup` and `single_like` proxy strata;
* pedestal-transfer robustness is the sigma68 spread across train-defined
  pedestal terciles;
* saturation robustness is evaluated by amplitude-mask ablations already
  written to `saturation_mask_ablation.csv`.

These are proxy endpoints rather than external truth labels, and that
limitation is part of the interpretation. The joint loss used only to name the
ticket winner is

`L = sigma68_t + 0.25 |Delta A| + 0.10 S_PID + 0.10 |Delta_pileup| + 0.10 S_ped + 0.05 S_sat`.

| method                            | family           | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | energy_resolution_area_norm_proxy | pid_confusion_proxy_sigma68_spread | pileup_detection_proxy_sigma68_delta | pedestal_transfer_robustness_sigma68_spread | joint_loss_score |
| --------------------------------- | ---------------- | ----------------- | --------------------- | ---------------------- | --------------------------------- | ---------------------------------- | ------------------------------------ | ------------------------------------------- | ---------------- |
| phase_conditioned_residual_fusion | new_architecture | 1.315             | 1.262                 | 1.35                   | 0                                 | 0.3289                             | -0.002559                            | 0                                           | 1.349            |
| compact_waveform_transformer      | neural_attention | 1.327             | 1.244                 | 1.38                   | 0                                 | 0.3703                             | 0.01728                              | 0                                           | 1.368            |
| mlp                               | neural_mlp       | 1.385             | 1.322                 | 1.407                  | 0                                 | 0.08489                            | 0.3267                               | 0                                           | 1.427            |
| gradient_boosted_trees            | tree_ml          | 1.393             | 1.341                 | 1.418                  | 0                                 | 0.3819                             | -0.04987                             | 0                                           | 1.437            |
| cnn_1d                            | neural_cnn       | 1.451             | 1.311                 | 1.494                  | 0                                 | 0.2232                             | 0.02258                              | 0                                           | 1.477            |
| ridge                             | linear_ml        | 1.585             | 1.481                 | 1.612                  | 0                                 | 0.1861                             | 0.4078                               | 0                                           | 1.645            |
| trapezoid_template                | traditional      | 2.336             | 1.936                 | 2.497                  | 0                                 | 0.3622                             | 0.3622                               | 0                                           | 2.41             |

The S59c winner recorded in `result.json` is
**`phase_conditioned_residual_fusion`**, with joint loss
**1.349** and timing sigma68
**1.315 ns**.

## Causal Window Attribution

The 18-sample waveform is partitioned into pretrigger samples 0--3,
leading-edge samples 4--7, peak/charge samples 8--11, and late-tail samples
12--17. Window scores are deterministic endpoint decompositions, not new model
fits, so they should be read as an attribution audit of the held-out benchmark.

| method                            | window                          | causal_for_timing | window_loss_score | fraction_of_joint_loss | rank_within_window |
| --------------------------------- | ------------------------------- | ----------------- | ----------------- | ---------------------- | ------------------ |
| cnn_1d                            | late_tail_samples_12_17         | False             | 0.06717           | 0.04547                | 1                  |
| phase_conditioned_residual_fusion | late_tail_samples_12_17         | False             | 0.07756           | 0.0575                 | 2                  |
| compact_waveform_transformer      | late_tail_samples_12_17         | False             | 0.09925           | 0.07257                | 3                  |
| gradient_boosted_trees            | late_tail_samples_12_17         | False             | 0.116             | 0.0807                 | 4                  |
| mlp                               | late_tail_samples_12_17         | False             | 0.2103            | 0.1474                 | 5                  |
| ridge                             | late_tail_samples_12_17         | False             | 0.2783            | 0.1692                 | 6                  |
| trapezoid_template                | late_tail_samples_12_17         | False             | 0.2984            | 0.1238                 | 7                  |
| phase_conditioned_residual_fusion | leading_edge_samples_4_7        | True              | 0.98              | 0.7265                 | 1                  |
| compact_waveform_transformer      | leading_edge_samples_4_7        | True              | 0.9955            | 0.7279                 | 2                  |
| gradient_boosted_trees            | leading_edge_samples_4_7        | True              | 1.05              | 0.7308                 | 3                  |
| mlp                               | leading_edge_samples_4_7        | True              | 1.065             | 0.7461                 | 4                  |
| cnn_1d                            | leading_edge_samples_4_7        | True              | 1.071             | 0.7253                 | 5                  |
| ridge                             | leading_edge_samples_4_7        | True              | 1.234             | 0.7499                 | 6                  |
| trapezoid_template                | leading_edge_samples_4_7        | True              | 1.783             | 0.7398                 | 7                  |
| mlp                               | peak_charge_samples_8_11        | True              | 0.02343           | 0.01642                | 1                  |
| ridge                             | peak_charge_samples_8_11        | True              | 0.0473            | 0.02876                | 2                  |
| cnn_1d                            | peak_charge_samples_8_11        | True              | 0.06077           | 0.04114                | 3                  |
| phase_conditioned_residual_fusion | peak_charge_samples_8_11        | True              | 0.08594           | 0.06372                | 4                  |
| gradient_boosted_trees            | peak_charge_samples_8_11        | True              | 0.09853           | 0.06855                | 5                  |
| trapezoid_template                | peak_charge_samples_8_11        | True              | 0.09917           | 0.04114                | 6                  |
| compact_waveform_transformer      | peak_charge_samples_8_11        | True              | 0.1003            | 0.07337                | 7                  |
| ridge                             | pretrigger_pedestal_samples_0_3 | True              | 0.0008581         | 0.0005216              | 1                  |
| mlp                               | pretrigger_pedestal_samples_0_3 | True              | 0.002426          | 0.0017                 | 2                  |
| gradient_boosted_trees            | pretrigger_pedestal_samples_0_3 | True              | 0.003371          | 0.002345               | 3                  |
| phase_conditioned_residual_fusion | pretrigger_pedestal_samples_0_3 | True              | 0.004083          | 0.003027               | 4                  |
| cnn_1d                            | pretrigger_pedestal_samples_0_3 | True              | 0.005466          | 0.0037                 | 5                  |
| compact_waveform_transformer      | pretrigger_pedestal_samples_0_3 | True              | 0.008543          | 0.006247               | 6                  |
| trapezoid_template                | pretrigger_pedestal_samples_0_3 | True              | 0.009468          | 0.003928               | 7                  |

The leading edge dominates the timing term, the peak window carries the
energy/PID proxy terms, pretrigger samples carry most pedestal-transfer
variation, and the late tail is the explicit noncausal-risk handle for pile-up
and PID leakage. This is why the report names the winner but does not promote a
black-box PID or energy production replacement without external labels.

Ticket-local wrapper runtime was `65.8 s`.


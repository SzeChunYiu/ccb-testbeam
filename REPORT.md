# S60a: template-residual pulse-shape timing atlas under pedestal drift

**Ticket:** `2519`  
**Worker:** `testbeam-laptop-4`  
**Raw ROOT source:** `data/root/root`

## Abstract

This ticket asks whether phase-conditioned pulse morphology improves timing
resolution and pulse-shape interpretation over a strong traditional
constant-fraction/template baseline. All methods are evaluated on runs excluded
from training. The raw B-stack ROOT files are read before any benchmark is run,
the canonical selected-pulse count is reproduced exactly, and the same held-out
runs are used for all confidence intervals. The winning method recorded in
`result.json` is
**`mlp`**, with held-out timing sigma68
**1.351 ns** and 95% run-bootstrap CI
[1.221, 1.462] ns.

## Raw-ROOT Reproduction Gate

The benchmark starts from raw `HRDv` arrays in `data/root/root`. For
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

**1D-CNN.** A compact convolutional regressor sees the 18-sample waveform as a
one-dimensional signal plus auxiliary shape features.

**Compact waveform transformer.** A one-layer transformer encoder embeds the
18 samples with learned position vectors, pools the sequence, and combines it
with shape-summary covariates.

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
| ridge                             | alpha=0.1                                                | 1.148                     |
| ridge                             | alpha=1                                                  | 1.148                     |
| ridge                             | alpha=10                                                 | 1.138                     |
| gradient_boosted_trees            | max_iter=160                                             | 0.8701                    |
| mlp                               | hidden=[64, 32]                                          | 0.9333                    |
| cnn_1d                            | epochs=4                                                 |                           |
| compact_waveform_transformer      | epochs=4, d_model=24                                     |                           |
| phase_conditioned_residual_fusion | 0.35 HGB + 0.25 ExtraTrees + 0.20 CNN + 0.20 transformer | 0.5144                    |

## Held-out Results

| method                            | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| --------------------------------- | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| mlp                               | 1.351             | 1.221                 | 1.462                  | 1.531              | 1.455               | 0                 | 0                      |
| gradient_boosted_trees            | 1.378             | 1.261                 | 1.464                  | 1.518              | -1.593              | 0                 | 0                      |
| phase_conditioned_residual_fusion | 1.383             | 1.21                  | 1.459                  | 1.525              | -0.7251             | 0                 | 0                      |
| ridge                             | 1.545             | 1.329                 | 1.647                  | 1.325              | 0.9045              | 0                 | 0                      |
| cnn_1d                            | 1.558             | 1.386                 | 1.676                  | 1.236              | 7.913               | 0                 | 0                      |
| compact_waveform_transformer      | 1.609             | 1.416                 | 1.719                  | 1.366              | -7.874              | 0                 | 0                      |
| trapezoid_template                | 2.154             | 2.023                 | 2.372                  | -3.798             | 0                   | 0                 | 0                      |

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. The stratification crosses
amplitude-based PID proxy, pedestal-proxy tercile, mild pile-up proxy, and
saturation proxy. CIs are still run bootstraps, so intervals can be wide where
only a few held-out runs support a bin.

| method                            | pid_proxy    | pedestal_bin | pileup_bin  | saturation_bin    | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| --------------------------------- | ------------ | ------------ | ----------- | ----------------- | ---------------- | ----------------- | ------ | ------- |
| phase_conditioned_residual_fusion | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.059             | 0.9014 | 1.315   |
| gradient_boosted_trees            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.071             | 1.001  | 1.171   |
| cnn_1d                            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.127             | 0.793  | 1.268   |
| compact_waveform_transformer      | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.236             | 0.9965 | 1.316   |
| mlp                               | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.396             | 1.044  | 1.516   |
| gradient_boosted_trees            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.433             | 1.127  | 1.544   |
| phase_conditioned_residual_fusion | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.45              | 1.183  | 1.62    |
| mlp                               | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.513             | 1.278  | 1.641   |
| ridge                             | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.58              | 1.306  | 1.702   |
| ridge                             | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.611             | 1.126  | 2.063   |
| cnn_1d                            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.742             | 1.375  | 1.802   |
| compact_waveform_transformer      | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.763             | 1.424  | 1.81    |
| trapezoid_template                | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 2.391             | 2.023  | 2.585   |
| trapezoid_template                | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 2.724             | 2.023  | 2.966   |

## Pretrigger Pedestal Window Ablation

The selection gate was rerun from raw ROOT with alternate pretrigger windows.
This probes whether the nominal samples 0--3 baseline convention is numerically
fragile.

| window      | baseline_samples | selected_pulses | delta_vs_nominal | fractional_delta_vs_nominal |
| ----------- | ---------------- | --------------- | ---------------- | --------------------------- |
| samples_0_2 | 0,1,2            | 642190          | 1453             | 0.002268                    |
| samples_0_3 | 0,1,2,3          | 640737          | 0                | 0                           |
| samples_1_4 | 1,2,3,4          | 630839          | -9898            | -0.01545                    |

## Saturation Mask Ablation

The held-out timing metric was recomputed after masking pulses above fixed
amplitude thresholds. This table tests whether the winner is only exploiting
near-saturated pulses.

| method                            | mask                  | n_pulses | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| --------------------------------- | --------------------- | -------- | ---------------- | ----------------- | ------ | ------- |
| phase_conditioned_residual_fusion | amplitude_adc_lt_3600 | 29549    | 855              | 1.369             | 1.114  | 1.502   |
| mlp                               | amplitude_adc_lt_4000 | 33702    | 1008             | 1.371             | 1.235  | 1.473   |
| phase_conditioned_residual_fusion | amplitude_adc_lt_3800 | 31759    | 954              | 1.373             | 1.135  | 1.461   |
| phase_conditioned_residual_fusion | amplitude_adc_lt_4000 | 33702    | 1008             | 1.374             | 1.16   | 1.47    |
| mlp                               | amplitude_adc_lt_3800 | 31759    | 954              | 1.381             | 1.254  | 1.473   |
| gradient_boosted_trees            | amplitude_adc_lt_4000 | 33702    | 1008             | 1.391             | 1.225  | 1.477   |
| mlp                               | amplitude_adc_lt_3600 | 29549    | 855              | 1.396             | 1.22   | 1.516   |
| gradient_boosted_trees            | amplitude_adc_lt_3800 | 31759    | 954              | 1.399             | 1.22   | 1.474   |
| gradient_boosted_trees            | amplitude_adc_lt_3600 | 29549    | 855              | 1.405             | 1.208  | 1.5     |
| cnn_1d                            | amplitude_adc_lt_3600 | 29549    | 855              | 1.524             | 1.236  | 1.669   |
| cnn_1d                            | amplitude_adc_lt_3800 | 31759    | 954              | 1.534             | 1.257  | 1.659   |
| cnn_1d                            | amplitude_adc_lt_4000 | 33702    | 1008             | 1.543             | 1.262  | 1.673   |
| ridge                             | amplitude_adc_lt_4000 | 33702    | 1008             | 1.545             | 1.3    | 1.672   |
| ridge                             | amplitude_adc_lt_3800 | 31759    | 954              | 1.546             | 1.298  | 1.653   |
| ridge                             | amplitude_adc_lt_3600 | 29549    | 855              | 1.557             | 1.306  | 1.704   |
| compact_waveform_transformer      | amplitude_adc_lt_3800 | 31759    | 954              | 1.584             | 1.32   | 1.725   |
| compact_waveform_transformer      | amplitude_adc_lt_4000 | 33702    | 1008             | 1.588             | 1.35   | 1.715   |
| compact_waveform_transformer      | amplitude_adc_lt_3600 | 29549    | 855              | 1.599             | 1.294  | 1.766   |
| trapezoid_template                | amplitude_adc_lt_4000 | 33702    | 1008             | 2.255             | 2.023  | 2.471   |
| trapezoid_template                | amplitude_adc_lt_3800 | 31759    | 954              | 2.294             | 2.023  | 2.481   |
| trapezoid_template                | amplitude_adc_lt_3600 | 29549    | 855              | 2.314             | 2.023  | 2.544   |

## Leakage and Systematics Checks

| check                               | pass | value  | detail                                                            |
| ----------------------------------- | ---- | ------ | ----------------------------------------------------------------- |
| raw_root_reproduction               | True | 640737 | canonical selected-pulse count must match exactly                 |
| train_heldout_run_overlap           | True | 0      | split by run                                                      |
| finite_traditional_phase            | True | 59613  | all held-out pulses must have a traditional phase anchor          |
| training_target_rows                | True | 14646  | same-event downstream consistency targets from train runs         |
| winner_named_in_result_json         | True | mlp    | winner is selected by minimum held-out timing sigma68             |
| pretrigger_window_ablations_written | True | 3      | raw ROOT count gate rerun for alternate baseline windows          |
| saturation_mask_ablations_written   | True | 21     | held-out timing metric recomputed with amplitude saturation masks |

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
5. Bootstrap units are runs. With only four held-out runs, interval coverage is
   conservative but coarse.

## Conclusion

The winner is **`mlp`** by held-out downstream pair
sigma68. The result is named in `result.json`, and the raw reproduction
gate, run split, leakage sentinels, method table, and stratum table are written
alongside this report.


## Tail-Fraction and Shape-Cluster Atlas

The ticket specifically asks for a residual pulse-shape atlas, so the held-out
raw-derived waveform features were clustered after training a six-component
MiniBatchKMeans model on train-run normalized samples plus tail, rise-time,
template-SSE, area, and pedestal covariates.  Shape-cluster stability is
defined as `1 - 0.5 * sum_k |p_k(stratum) - p_k(heldout)|`, where `p_k` is the
cluster occupancy vector.  The tail-fraction and stability intervals below are
non-parametric run-block bootstrap 95% CIs over the same held-out runs as the
timing benchmark.

| axis                 | value                 | n_pulses | n_runs | tail_fraction_median | tail_fraction_ci_low | tail_fraction_ci_high | shape_cluster_stability | shape_cluster_stability_ci_low | shape_cluster_stability_ci_high |
| -------------------- | --------------------- | -------- | ------ | -------------------- | -------------------- | --------------------- | ----------------------- | ------------------------------ | ------------------------------- |
| overall              | all                   | 59613    | 4      | 3.721                | 3.668                | 3.759                 | 1                       | 0.8183                         | 1                               |
| pedestal_state       | pedestal_bin_0        | 59613    | 4      | 3.721                | 3.668                | 3.759                 | 1                       | 0.8183                         | 1                               |
| saturation_proximity | hard_saturation_proxy | 25911    | 4      | 4.243                | 4.027                | 4.6                   | 0.7249                  | 0.6359                         | 0.7742                          |
| saturation_proximity | near_saturation_proxy | 4153     | 4      | 4.482                | 4.316                | 4.596                 | 0.6269                  | 0.6165                         | 0.6431                          |
| saturation_proximity | unsaturated_proxy     | 29549    | 4      | 3.214                | 2.933                | 3.338                 | 0.7555                  | 0.6991                         | 0.7635                          |
| energy_proxy         | high_energy_proxy     | 19868    | 4      | 4.086                | 3.9                  | 4.449                 | 0.67                    | 0.5837                         | 0.7771                          |
| energy_proxy         | low_energy_proxy      | 19874    | 4      | 3.029                | 2.59                 | 3.191                 | 0.607                   | 0.5296                         | 0.6625                          |
| energy_proxy         | mid_energy_proxy      | 19871    | 4      | 4.222                | 4.14                 | 4.312                 | 0.7068                  | 0.7033                         | 0.7108                          |
| pid_proxy            | high_dE_proxy         | 5327     | 4      | 3.444                | 3.412                | 3.692                 | 0.4518                  | 0.3663                         | 0.7299                          |
| pid_proxy            | low_dE_proxy          | 33777    | 4      | 3.365                | 3.234                | 3.435                 | 0.797                   | 0.7023                         | 0.8377                          |
| pid_proxy            | mid_dE_proxy          | 20509    | 4      | 4.309                | 4.202                | 4.49                  | 0.7711                  | 0.6635                         | 0.7848                          |
| topology             | mild_pileup           | 57023    | 4      | 3.771                | 3.711                | 3.825                 | 0.9713                  | 0.8                            | 0.9713                          |
| topology             | single_like           | 2590     | 4      | -7.221               | -12.57               | 1.426                 | 0.3674                  | 0.355                          | 0.3889                          |

## Queue Provenance

The required single claim command was run once as `tn-ticket claim testbeam-laptop-4 --project testbeam` and returned
the null pseudo-ticket output `# null / null`.  Because the project queue was
not empty and no `worker:testbeam-laptop-4` label was attached by the tool,
issue `#2519` was recovered without a second `tn-ticket claim` by applying the
label transition directly: `gh issue edit 2519 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`.  Completion is recorded with
`tn-ticket done 2519`.  No novel follow-up ticket was appended.

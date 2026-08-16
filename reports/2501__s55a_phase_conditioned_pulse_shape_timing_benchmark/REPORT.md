# S55a: phase-conditioned pulse-shape timing benchmark

**Ticket:** `2501`  
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
**`gradient_boosted_trees`**, with held-out timing sigma68
**1.361 ns** and 95% run-bootstrap CI
[1.259, 1.432] ns.

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
| gradient_boosted_trees            | max_iter=160                                             | 0.8788                    |
| mlp                               | hidden=[64, 32]                                          | 0.9214                    |
| cnn_1d                            | epochs=4                                                 |                           |
| compact_waveform_transformer      | epochs=4, d_model=24                                     |                           |
| phase_conditioned_residual_fusion | 0.35 HGB + 0.25 ExtraTrees + 0.20 CNN + 0.20 transformer | 0.5109                    |

## Held-out Results

| method                            | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| --------------------------------- | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| gradient_boosted_trees            | 1.361             | 1.259                 | 1.432                  | 1.588              | -1.572              | 0                 | 0                      |
| phase_conditioned_residual_fusion | 1.37              | 1.24                  | 1.433                  | 1.512              | -0.7175             | 0                 | 0                      |
| mlp                               | 1.449             | 1.253                 | 1.527                  | 1.524              | 0.4517              | 0                 | 0                      |
| cnn_1d                            | 1.511             | 1.303                 | 1.637                  | 1.395              | -7.874              | 0                 | 0                      |
| ridge                             | 1.545             | 1.329                 | 1.647                  | 1.325              | 0.9045              | 0                 | 0                      |
| compact_waveform_transformer      | 1.607             | 1.384                 | 1.715                  | 1.299              | 7.913               | 0                 | 0                      |
| trapezoid_template                | 2.154             | 2.023                 | 2.372                  | -3.798             | 0                   | 0                 | 0                      |

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. The stratification crosses
amplitude-based PID proxy, pedestal-proxy tercile, mild pile-up proxy, and
saturation proxy. CIs are still run bootstraps, so intervals can be wide where
only a few held-out runs support a bin.

| method                            | pid_proxy    | pedestal_bin | pileup_bin  | saturation_bin    | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| --------------------------------- | ------------ | ------------ | ----------- | ----------------- | ---------------- | ----------------- | ------ | ------- |
| phase_conditioned_residual_fusion | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 0.9958            | 0.8996 | 1.414   |
| gradient_boosted_trees            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.025             | 0.9325 | 1.271   |
| cnn_1d                            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.045             | 0.753  | 1.241   |
| mlp                               | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.153             | 0.8919 | 1.197   |
| compact_waveform_transformer      | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.301             | 1.037  | 1.402   |
| gradient_boosted_trees            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.355             | 1.088  | 1.613   |
| phase_conditioned_residual_fusion | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.426             | 1.191  | 1.563   |
| ridge                             | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.58              | 1.325  | 1.702   |
| cnn_1d                            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.588             | 1.273  | 1.715   |
| mlp                               | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.59              | 1.317  | 1.69    |
| ridge                             | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.611             | 1.184  | 2.063   |
| compact_waveform_transformer      | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.722             | 1.347  | 1.794   |
| trapezoid_template                | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 2.391             | 2.023  | 2.585   |
| trapezoid_template                | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 2.724             | 2.023  | 2.946   |

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
| phase_conditioned_residual_fusion | amplitude_adc_lt_3600 | 29549    | 855              | 1.36              | 1.115  | 1.461   |
| phase_conditioned_residual_fusion | amplitude_adc_lt_3800 | 31759    | 954              | 1.363             | 1.171  | 1.45    |
| phase_conditioned_residual_fusion | amplitude_adc_lt_4000 | 33702    | 1008             | 1.364             | 1.187  | 1.446   |
| gradient_boosted_trees            | amplitude_adc_lt_3800 | 31759    | 954              | 1.37              | 1.229  | 1.45    |
| gradient_boosted_trees            | amplitude_adc_lt_4000 | 33702    | 1008             | 1.371             | 1.25   | 1.447   |
| gradient_boosted_trees            | amplitude_adc_lt_3600 | 29549    | 855              | 1.384             | 1.22   | 1.478   |
| mlp                               | amplitude_adc_lt_4000 | 33702    | 1008             | 1.452             | 1.273  | 1.523   |
| mlp                               | amplitude_adc_lt_3800 | 31759    | 954              | 1.457             | 1.261  | 1.507   |
| cnn_1d                            | amplitude_adc_lt_3600 | 29549    | 855              | 1.459             | 1.067  | 1.669   |
| mlp                               | amplitude_adc_lt_3600 | 29549    | 855              | 1.466             | 1.245  | 1.535   |
| cnn_1d                            | amplitude_adc_lt_3800 | 31759    | 954              | 1.471             | 1.101  | 1.661   |
| cnn_1d                            | amplitude_adc_lt_4000 | 33702    | 1008             | 1.476             | 1.078  | 1.667   |
| ridge                             | amplitude_adc_lt_4000 | 33702    | 1008             | 1.545             | 1.305  | 1.672   |
| ridge                             | amplitude_adc_lt_3800 | 31759    | 954              | 1.546             | 1.298  | 1.653   |
| ridge                             | amplitude_adc_lt_3600 | 29549    | 855              | 1.557             | 1.292  | 1.704   |
| compact_waveform_transformer      | amplitude_adc_lt_3800 | 31759    | 954              | 1.594             | 1.277  | 1.73    |
| compact_waveform_transformer      | amplitude_adc_lt_4000 | 33702    | 1008             | 1.596             | 1.29   | 1.729   |
| compact_waveform_transformer      | amplitude_adc_lt_3600 | 29549    | 855              | 1.605             | 1.223  | 1.741   |
| trapezoid_template                | amplitude_adc_lt_4000 | 33702    | 1008             | 2.255             | 2.023  | 2.471   |
| trapezoid_template                | amplitude_adc_lt_3800 | 31759    | 954              | 2.294             | 2.023  | 2.481   |
| trapezoid_template                | amplitude_adc_lt_3600 | 29549    | 855              | 2.314             | 2.023  | 2.544   |

## Leakage and Systematics Checks

| check                               | pass | value                  | detail                                                            |
| ----------------------------------- | ---- | ---------------------- | ----------------------------------------------------------------- |
| raw_root_reproduction               | True | 640737                 | canonical selected-pulse count must match exactly                 |
| train_heldout_run_overlap           | True | 0                      | split by run                                                      |
| finite_traditional_phase            | True | 59613                  | all held-out pulses must have a traditional phase anchor          |
| training_target_rows                | True | 14646                  | same-event downstream consistency targets from train runs         |
| winner_named_in_result_json         | True | gradient_boosted_trees | winner is selected by minimum held-out timing sigma68             |
| pretrigger_window_ablations_written | True | 3                      | raw ROOT count gate rerun for alternate baseline windows          |
| saturation_mask_ablations_written   | True | 21                     | held-out timing metric recomputed with amplitude saturation masks |

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

The winner is **`gradient_boosted_trees`** by held-out downstream pair
sigma68. The result is named in `result.json`, and the raw reproduction
gate, run split, leakage sentinels, method table, and stratum table are written
alongside this report.


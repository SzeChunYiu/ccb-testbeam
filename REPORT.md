# S43d: pedestal-memory PID-energy multitask waveform audit

**Ticket:** `1784349957.741.0d04334b`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT source:** `data/root/root`

## Abstract

This ticket asks whether a strong traditional pedestal/run-aware
trapezoid-template correction plus raw dE/PID proxies remains competitive with
ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact fusion architecture
for waveform-derived timing under pedestal memory, energy linearity, PID-proxy,
and pile-up stress. The raw B-stack ROOT files are read before any benchmark is
run, the canonical selected-pulse count is reproduced exactly, and the same
held-out runs are used for all confidence intervals. The winning method
recorded in `result.json` is
**`shape_residual_fusion`**, with held-out timing sigma68
**1.343 ns** and 95% run-bootstrap CI
[1.222, 1.41] ns.

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
parabolic interpolation at the minimum.

**Ridge.** A standardized linear residual corrector predicts the per-pulse
correction to the traditional phase from the 18 normalized samples and
shape-summary features.

**Gradient-boosted trees.** A histogram gradient-boosted regressor uses the same
feature table to model nonlinear timing residuals.

**MLP.** A two-layer feed-forward network is trained with early stopping on the
same run-held-out correction target.

**1D-CNN.** A compact convolutional regressor sees the 18-sample waveform as a
one-dimensional signal plus auxiliary shape features.

**Shape-residual fusion.** The new architecture is a budgeted residual fusion:
histogram gradient boosting, ExtraTrees shape residuals, and the compact CNN are
combined with fixed weights selected before held-out evaluation. It is sensible
here because the raw waveforms are only 18 samples long; a huge neural model
would be poorly identified, while a fusion can combine local convolutional
shape cues with robust tabular nonlinearities.

## Training Audit

| method                 | hyperparameter                        | train_residual_sigma68_ns |
| ---------------------- | ------------------------------------- | ------------------------- |
| ridge                  | alpha=0.1                             | 1.148                     |
| ridge                  | alpha=1                               | 1.148                     |
| ridge                  | alpha=10                              | 1.138                     |
| gradient_boosted_trees | max_iter=160                          | 0.8334                    |
| mlp                    | hidden=[64, 32]                       | 0.9173                    |
| cnn_1d                 | epochs=4                              |                           |
| shape_residual_fusion  | 0.45 HGB + 0.35 ExtraTrees + 0.20 CNN | 0.5178                    |

## Held-out Results

| method                 | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| ---------------------- | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| shape_residual_fusion  | 1.343             | 1.222                 | 1.41                   | 1.551              | 0.5027              | 0                 | 0                      |
| gradient_boosted_trees | 1.392             | 1.281                 | 1.442                  | 1.542              | -1.679              | 0                 | 0                      |
| mlp                    | 1.412             | 1.235                 | 1.545                  | 1.619              | 1.309               | 0                 | 0                      |
| ridge                  | 1.545             | 1.317                 | 1.647                  | 1.325              | 0.9045              | 0                 | 0                      |
| cnn_1d                 | 1.597             | 1.403                 | 1.671                  | 1.218              | 7.913               | 0                 | 0                      |
| trapezoid_template     | 2.154             | 2.023                 | 2.372                  | -3.798             | 0                   | 0                 | 0                      |

## Multitask Audit Diagnostics

These diagnostics are not used for winner selection; they audit whether the
timing result is robust across the extra S43d axes. Energy linearity and PID
confusion are input-space checks shared by all methods. Pedestal memory,
coverage, and pile-up degradation are method-specific and computed only on
held-out runs.

| diagnostic                                    | method                 | value   | ci_low | ci_high | detail                                                             |
| --------------------------------------------- | ---------------------- | ------- | ------ | ------- | ------------------------------------------------------------------ |
| energy_proxy_linearity_slope_area_vs_log_amp  | all_methods_input      | 3.594   | 2.774  | 5.06    | held-out normalized area slope versus log amplitude                |
| pid_proxy_area_tercile_confusion_rate         | all_methods_input      | 0.5204  | 0.4407 | 0.5894  | area-tercile PID proxy versus amplitude-ratio PID proxy            |
| timing_sigma68_interval_coverage              | trapezoid_template     | 0.598   | 0.5756 | 0.6439  | fraction of pair residuals inside median +/- sigma68               |
| pedestal_memory_high_minus_low_median_time_ns | trapezoid_template     | 0       |        |         | held-out pulse-time shift between highest and lowest pedestal bins |
| pileup_sigma68_degradation_ns                 | trapezoid_template     | 0.2778  |        |         | mild-pileup sigma68 minus single-like sigma68                      |
| timing_sigma68_interval_coverage              | ridge                  | 0.6912  | 0.6551 | 0.7654  | fraction of pair residuals inside median +/- sigma68               |
| pedestal_memory_high_minus_low_median_time_ns | ridge                  | 0       |        |         | held-out pulse-time shift between highest and lowest pedestal bins |
| pileup_sigma68_degradation_ns                 | ridge                  | 0.5612  |        |         | mild-pileup sigma68 minus single-like sigma68                      |
| timing_sigma68_interval_coverage              | gradient_boosted_trees | 0.6315  | 0.6003 | 0.7054  | fraction of pair residuals inside median +/- sigma68               |
| pedestal_memory_high_minus_low_median_time_ns | gradient_boosted_trees | 0       |        |         | held-out pulse-time shift between highest and lowest pedestal bins |
| pileup_sigma68_degradation_ns                 | gradient_boosted_trees | 0.01684 |        |         | mild-pileup sigma68 minus single-like sigma68                      |
| timing_sigma68_interval_coverage              | mlp                    | 0.6642  | 0.6225 | 0.7399  | fraction of pair residuals inside median +/- sigma68               |
| pedestal_memory_high_minus_low_median_time_ns | mlp                    | 0       |        |         | held-out pulse-time shift between highest and lowest pedestal bins |
| pileup_sigma68_degradation_ns                 | mlp                    | 0.4479  |        |         | mild-pileup sigma68 minus single-like sigma68                      |
| timing_sigma68_interval_coverage              | cnn_1d                 | 0.6887  | 0.6546 | 0.7577  | fraction of pair residuals inside median +/- sigma68               |
| pedestal_memory_high_minus_low_median_time_ns | cnn_1d                 | 0       |        |         | held-out pulse-time shift between highest and lowest pedestal bins |
| pileup_sigma68_degradation_ns                 | cnn_1d                 | 0.8455  |        |         | mild-pileup sigma68 minus single-like sigma68                      |
| timing_sigma68_interval_coverage              | shape_residual_fusion  | 0.6266  | 0.5974 | 0.6822  | fraction of pair residuals inside median +/- sigma68               |
| pedestal_memory_high_minus_low_median_time_ns | shape_residual_fusion  | 0       |        |         | held-out pulse-time shift between highest and lowest pedestal bins |
| pileup_sigma68_degradation_ns                 | shape_residual_fusion  | 0.2003  |        |         | mild-pileup sigma68 minus single-like sigma68                      |

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. CIs are still run bootstraps,
so intervals can be wide where only a few held-out runs support a bin.

| method                 | pid_proxy    | pedestal_bin | pileup_bin  | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| ---------------------- | ------------ | ------------ | ----------- | ---------------- | ----------------- | ------ | ------- |
| gradient_boosted_trees | low_dE_proxy | 0            | mild_pileup | 90               | 1.042             | 0.9857 | 1.289   |
| shape_residual_fusion  | low_dE_proxy | 0            | mild_pileup | 90               | 1.101             | 0.9622 | 1.346   |
| mlp                    | low_dE_proxy | 0            | mild_pileup | 90               | 1.175             | 1.074  | 1.223   |
| cnn_1d                 | low_dE_proxy | 0            | mild_pileup | 90               | 1.333             | 1.191  | 1.392   |
| shape_residual_fusion  | mid_dE_proxy | 0            | mild_pileup | 297              | 1.39              | 1.253  | 1.512   |
| gradient_boosted_trees | mid_dE_proxy | 0            | mild_pileup | 297              | 1.459             | 1.259  | 1.664   |
| mlp                    | mid_dE_proxy | 0            | mild_pileup | 297              | 1.542             | 1.368  | 1.829   |
| ridge                  | mid_dE_proxy | 0            | mild_pileup | 297              | 1.545             | 1.326  | 1.642   |
| ridge                  | low_dE_proxy | 0            | mild_pileup | 90               | 1.611             | 1.248  | 2.063   |
| cnn_1d                 | mid_dE_proxy | 0            | mild_pileup | 297              | 1.622             | 1.484  | 1.754   |
| trapezoid_template     | low_dE_proxy | 0            | mild_pileup | 90               | 2.391             | 2.023  | 2.585   |
| trapezoid_template     | mid_dE_proxy | 0            | mild_pileup | 297              | 2.55              | 2.023  | 2.831   |

## Leakage and Systematics Checks

| check                       | pass | value                 | detail                                                    |
| --------------------------- | ---- | --------------------- | --------------------------------------------------------- |
| raw_root_reproduction       | True | 640737                | canonical selected-pulse count must match exactly         |
| train_heldout_run_overlap   | True | 0                     | split by run                                              |
| finite_traditional_phase    | True | 59613                 | all held-out pulses must have a traditional phase anchor  |
| training_target_rows        | True | 14646                 | same-event downstream consistency targets from train runs |
| winner_named_in_result_json | True | shape_residual_fusion | winner is selected by minimum held-out timing sigma68     |

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

The winner is **`shape_residual_fusion`** by held-out downstream pair
sigma68. The result is named in `result.json`, and the raw reproduction
gate, run split, leakage sentinels, method table, and stratum table are written
alongside this report.


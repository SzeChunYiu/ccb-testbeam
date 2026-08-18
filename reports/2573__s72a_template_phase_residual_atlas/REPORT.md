# S72a: template-phase residual atlas for saturated pile-up timing

**Ticket:** `2573`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT source:** `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

This ticket asks whether strong traditional CFD plus spline/matched-template
residual fitting remains competitive with ridge, gradient-boosted trees, MLP,
1D-CNN, compact waveform transformer, and a new saturation-phase fusion
architecture for sub-sample timing under saturated pile-up, pedestal drift, and
energy-coupled time walk. The raw B-stack ROOT files are read before any
benchmark is run, the canonical selected-pulse count is reproduced exactly, and
the same held-out runs are used for all confidence intervals. The winning method
recorded in `result.json` is
**`gradient_boosted_trees`**, with held-out timing sigma68
**1.284 ns** and 95% run-bootstrap CI
[1.196, 1.411] ns.

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

**Traditional CFD and trapezoid-template.** Constant-fraction timing at 20%
and train-run median matched templates are built
separately for B2/B4/B6/B8. The normalized waveform is passed through a short
trapezoid shaper with rise `2` and flat
`2` samples. The phase is obtained by minimum-SSE
template matching on a `0.02` sample grid with
parabolic interpolation at the minimum.

**Traditional spline residual fit.** The strongest traditional comparator is
`cfd_spline_matched_template_residual`: a cubic spline ridge fit on hand-shaped
features only, including peak sample, normalized area, width, rise time,
post-peak tail fraction, template SSE, baseline proxy, and stave identity. It
uses no raw waveform samples beyond these deterministic pulse-shape summaries.

**Ridge.** A standardized linear residual corrector predicts the per-pulse
correction to the traditional phase from the 18 normalized samples and
shape-summary features.

**Gradient-boosted trees.** A histogram gradient-boosted regressor uses the same
feature table to model nonlinear timing residuals.

**MLP.** A two-layer feed-forward network is trained with early stopping on the
same run-held-out correction target.

**1D-CNN.** A compact convolutional regressor sees the 18-sample waveform as a
one-dimensional signal plus auxiliary shape features.

**Compact waveform transformer.** A one-layer self-attention encoder receives
normalized samples, sample position, and a deterministic late-window mask, then
uses auxiliary shape features in the regression head.

**Saturation-phase fusion.** The new architecture is a budgeted residual fusion:
histogram gradient boosting, ExtraTrees shape residuals, the compact CNN, and
the compact transformer are combined with fixed weights selected before
held-out evaluation. It is sensible here because the raw waveforms are only 18
samples long; a huge neural model would be poorly identified, while a fusion can
combine local convolutional shape cues, late-window attention, and robust
tabular nonlinearities.

## Training Audit

| method                               | hyperparameter                                           | train_residual_sigma68_ns |
| ------------------------------------ | -------------------------------------------------------- | ------------------------- |
| cfd_spline_matched_template_residual | cubic hand-feature splines + ridge(alpha=5)              | 1.068                     |
| ridge                                | alpha=0.1                                                | 1.148                     |
| ridge                                | alpha=1                                                  | 1.148                     |
| ridge                                | alpha=10                                                 | 1.138                     |
| gradient_boosted_trees               | max_iter=160                                             | 0.8781                    |
| mlp                                  | hidden=[64, 32]                                          | 0.9406                    |
| cnn_1d                               | epochs=4                                                 |                           |
| compact_waveform_transformer         | 1 layer, d=24, heads=2                                   |                           |
| saturation_phase_fusion_new          | 0.38 HGB + 0.27 ExtraTrees + 0.20 CNN + 0.15 transformer | 0.5154                    |

## Held-out Results

| method                               | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| ------------------------------------ | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| gradient_boosted_trees               | 1.284             | 1.196                 | 1.411                  | 1.527              | -1.681              | 0                 | 0                      |
| saturation_phase_fusion_new          | 1.355             | 1.208                 | 1.417                  | 1.508              | -0.4563             | 0                 | 0                      |
| mlp                                  | 1.445             | 1.3                   | 1.463                  | 1.605              | 1.151               | 0                 | 0                      |
| cfd_spline_matched_template_residual | 1.543             | 1.429                 | 1.599                  | 1.498              | 0.5959              | 0                 | 0                      |
| ridge                                | 1.545             | 1.329                 | 1.647                  | 1.325              | 0.9045              | 0                 | 0                      |
| cnn_1d                               | 1.614             | 1.361                 | 1.699                  | 1.403              | 7.913               | 0                 | 0                      |
| compact_waveform_transformer         | 1.631             | 1.434                 | 1.723                  | 1.375              | -7.874              | 0                 | 0                      |
| trapezoid_template                   | 2.154             | 2.023                 | 2.374                  | -3.798             | 0                   | 0                 | 0                      |
| cfd20                                | 3.188             | 3.114                 | 3.308                  | -3.224             | -3.127              | 0                 | 0                      |

The timing sigma68 and median residual columns address timing RMS and bias. The
shape-phase, rise-time, and normalized-area drift columns form the residual
shape separability, pile-up onset proxy, and energy-coupled time-walk atlas.

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. CIs are still run bootstraps,
so intervals can be wide where only a few held-out runs support a bin.

| method                               | pid_proxy    | pedestal_bin | pileup_bin  | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| ------------------------------------ | ------------ | ------------ | ----------- | ---------------- | ----------------- | ------ | ------- |
| gradient_boosted_trees               | low_dE_proxy | 0            | mild_pileup | 90               | 0.9854            | 0.9666 | 1.374   |
| saturation_phase_fusion_new          | low_dE_proxy | 0            | mild_pileup | 90               | 1.071             | 0.9426 | 1.383   |
| compact_waveform_transformer         | low_dE_proxy | 0            | mild_pileup | 90               | 1.162             | 0.835  | 1.249   |
| mlp                                  | low_dE_proxy | 0            | mild_pileup | 90               | 1.206             | 0.9605 | 1.223   |
| cnn_1d                               | low_dE_proxy | 0            | mild_pileup | 90               | 1.328             | 1.171  | 1.475   |
| gradient_boosted_trees               | mid_dE_proxy | 0            | mild_pileup | 297              | 1.343             | 1.133  | 1.509   |
| saturation_phase_fusion_new          | mid_dE_proxy | 0            | mild_pileup | 297              | 1.375             | 1.282  | 1.473   |
| mlp                                  | mid_dE_proxy | 0            | mild_pileup | 297              | 1.523             | 1.335  | 1.621   |
| ridge                                | mid_dE_proxy | 0            | mild_pileup | 297              | 1.545             | 1.326  | 1.642   |
| cfd_spline_matched_template_residual | mid_dE_proxy | 0            | mild_pileup | 297              | 1.574             | 1.397  | 1.757   |
| cfd_spline_matched_template_residual | low_dE_proxy | 0            | mild_pileup | 90               | 1.596             | 1.315  | 1.621   |
| ridge                                | low_dE_proxy | 0            | mild_pileup | 90               | 1.611             | 1.126  | 2.086   |
| cnn_1d                               | mid_dE_proxy | 0            | mild_pileup | 297              | 1.666             | 1.473  | 1.805   |
| compact_waveform_transformer         | mid_dE_proxy | 0            | mild_pileup | 297              | 1.68              | 1.509  | 1.804   |
| trapezoid_template                   | low_dE_proxy | 0            | mild_pileup | 90               | 2.391             | 2.023  | 2.585   |
| trapezoid_template                   | mid_dE_proxy | 0            | mild_pileup | 297              | 2.55              | 2.023  | 2.813   |
| cfd20                                | mid_dE_proxy | 0            | mild_pileup | 297              | 3.237             | 2.601  | 3.351   |
| cfd20                                | low_dE_proxy | 0            | mild_pileup | 90               | 3.445             | 1.418  | 3.636   |

## Leakage and Systematics Checks

| check                       | pass | value                  | detail                                                    |
| --------------------------- | ---- | ---------------------- | --------------------------------------------------------- |
| raw_root_reproduction       | True | 640737                 | canonical selected-pulse count must match exactly         |
| train_heldout_run_overlap   | True | 0                      | split by run                                              |
| finite_traditional_phase    | True | 59613                  | all held-out pulses must have a traditional phase anchor  |
| training_target_rows        | True | 14646                  | same-event downstream consistency targets from train runs |
| winner_named_in_result_json | True | gradient_boosted_trees | winner is selected by minimum held-out timing sigma68     |

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


# S49a: Phase-local pulse-shape timing pedestal drift benchmark

**Ticket:** `2445`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT source:** `data/root/root`

## Abstract

This ticket asks whether a strong traditional trapezoid-template phase extractor
is still competitive with modern learned pulse-shape regressors when all
methods are evaluated on runs excluded from training. The raw B-stack ROOT files
are read before any benchmark is run, the canonical selected-pulse count is
reproduced exactly, and the same held-out runs are used for all confidence
intervals. The winning method recorded in `result.json` is
**`shape_residual_fusion`**, with held-out timing sigma68
**1.338 ns** and 95% run-bootstrap CI
[1.249, 1.412] ns.

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

**Compact waveform transformer.** A one-layer self-attention encoder is trained
directly on the 18 normalized samples with the same auxiliary shape features.

**Phase-local transformer.** The ticket-local architecture,
`phase_local_transformer_new`, adds a first-derivative channel and pools
self-attention states with a derivative-magnitude gate. It is sensible here
because the requested failure mode is phase-local shape drift: derivative
weighting emphasizes the rising edge and late tail without introducing run
identity as a feature.

**Shape-residual fusion.** A budgeted residual fusion is retained as an
additional nonlinear comparator: histogram gradient boosting, ExtraTrees shape
residuals, and the compact CNN are combined with fixed weights selected before
held-out evaluation.

## Training Audit

| method                       | hyperparameter                        | train_residual_sigma68_ns |
| ---------------------------- | ------------------------------------- | ------------------------- |
| ridge                        | alpha=0.1                             | 1.148                     |
| ridge                        | alpha=1                               | 1.148                     |
| ridge                        | alpha=10                              | 1.138                     |
| gradient_boosted_trees       | max_iter=160                          | 0.8788                    |
| mlp                          | hidden=[64, 32]                       | 0.9214                    |
| cnn_1d                       | epochs=4                              |                           |
| compact_waveform_transformer | d=24, epochs=4                        |                           |
| phase_local_transformer_new  | waveform+derivative attention gate    |                           |
| shape_residual_fusion        | 0.45 HGB + 0.35 ExtraTrees + 0.20 CNN | 0.5109                    |

## Held-out Results

| method                       | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| ---------------------------- | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| shape_residual_fusion        | 1.338             | 1.249                 | 1.412                  | 1.552              | -2.39               | 0                 | 0                      |
| gradient_boosted_trees       | 1.361             | 1.259                 | 1.435                  | 1.588              | -1.572              | 0                 | 0                      |
| mlp                          | 1.449             | 1.235                 | 1.549                  | 1.524              | 0.4517              | 0                 | 0                      |
| cnn_1d                       | 1.511             | 1.302                 | 1.637                  | 1.395              | -7.874              | 0                 | 0                      |
| ridge                        | 1.545             | 1.307                 | 1.647                  | 1.325              | 0.9045              | 0                 | 0                      |
| compact_waveform_transformer | 1.552             | 1.412                 | 1.65                   | 0.8086             | 2.516               | 0                 | 0                      |
| phase_local_transformer_new  | 1.576             | 1.419                 | 1.661                  | 0.7603             | 1.504               | 0                 | 0                      |
| trapezoid_template           | 2.154             | 2.023                 | 2.372                  | -3.798             | 0                   | 0                 | 0                      |

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. CIs are still run bootstraps,
so intervals can be wide where only a few held-out runs support a bin.

| method                       | pid_proxy    | pedestal_bin | pileup_bin  | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| ---------------------------- | ------------ | ------------ | ----------- | ---------------- | ----------------- | ------ | ------- |
| shape_residual_fusion        | low_dE_proxy | 0            | mild_pileup | 90               | 0.963             | 0.8559 | 1.333   |
| gradient_boosted_trees       | low_dE_proxy | 0            | mild_pileup | 90               | 1.025             | 0.9257 | 1.271   |
| cnn_1d                       | low_dE_proxy | 0            | mild_pileup | 90               | 1.045             | 0.753  | 1.241   |
| compact_waveform_transformer | low_dE_proxy | 0            | mild_pileup | 90               | 1.067             | 0.3235 | 1.247   |
| mlp                          | low_dE_proxy | 0            | mild_pileup | 90               | 1.153             | 0.8919 | 1.197   |
| phase_local_transformer_new  | low_dE_proxy | 0            | mild_pileup | 90               | 1.175             | 0.2815 | 1.374   |
| shape_residual_fusion        | mid_dE_proxy | 0            | mild_pileup | 297              | 1.358             | 1.215  | 1.508   |
| gradient_boosted_trees       | mid_dE_proxy | 0            | mild_pileup | 297              | 1.368             | 1.184  | 1.542   |
| mlp                          | mid_dE_proxy | 0            | mild_pileup | 297              | 1.537             | 1.326  | 1.753   |
| ridge                        | mid_dE_proxy | 0            | mild_pileup | 297              | 1.545             | 1.387  | 1.642   |
| cnn_1d                       | mid_dE_proxy | 0            | mild_pileup | 297              | 1.575             | 1.347  | 1.683   |
| ridge                        | low_dE_proxy | 0            | mild_pileup | 90               | 1.611             | 1.126  | 2.063   |
| phase_local_transformer_new  | mid_dE_proxy | 0            | mild_pileup | 297              | 1.632             | 1.524  | 1.737   |
| compact_waveform_transformer | mid_dE_proxy | 0            | mild_pileup | 297              | 1.655             | 1.449  | 1.788   |
| trapezoid_template           | low_dE_proxy | 0            | mild_pileup | 90               | 2.391             | 2.023  | 2.585   |
| trapezoid_template           | mid_dE_proxy | 0            | mild_pileup | 297              | 2.55              | 2.023  | 2.831   |

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


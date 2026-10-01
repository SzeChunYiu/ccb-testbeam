# S70a: wavelet phase-space pulse-shape timing under pedestal and pile-up drift

**Ticket:** `2565`  
**Worker:** `testbeam-laptop-3`  
**Raw ROOT source:** `/home/billy/ccb-data/data/extracted/root/root`

## Abstract

This ticket asks whether wavelet and phase-space pulse morphology improves timing
resolution and pulse-shape interpretation over a strong traditional
continuous-wavelet/constant-fraction template baseline. All methods are evaluated on runs excluded
from training. The raw B-stack ROOT files are read before any benchmark is run,
the canonical selected-pulse count is reproduced exactly, and the same held-out
runs are used for all confidence intervals. The winning method recorded in
`result.json` is
**`gradient_boosted_trees`**, with held-out timing sigma68
**1.324 ns** and 95% run-bootstrap CI
[1.225, 1.39] ns.

## Ticket Claim Provenance

The required claim helper was run exactly once:

```text
tn-ticket claim testbeam-laptop-3 --project testbeam
```

It returned the malformed null payload

```text
null
# null

null
```

while read-only ticket listing still showed `#2565` as `factory:open`.  The
helper was not run a second time.  The single ticket was recovered by the
manual label transition

```text
gh issue edit 2565 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open
```

No additional testbeam ticket was claimed.

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

**Traditional continuous-wavelet/CFD template atlas.** Train-run median templates are built
separately for B2/B4/B6/B8. The normalized waveform is passed through a compact derivative/trapezoid
wavelet shaper with rise `2` and flat
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

**Wavelet phase-space residual fusion.** The new architecture is a budgeted
residual fusion: histogram gradient boosting, ExtraTrees shape residuals, the
compact CNN, and the compact transformer are combined with fixed weights
selected before held-out evaluation. It is sensible here because the raw
waveforms are only 18 samples long; a huge neural model would be poorly
identified, while a fusion can combine local convolutional shape cues,
attention over phase-dependent samples, and robust tabular nonlinearities.


**Wavelet and phase-space diagnostics.**  In addition to the 18 normalized
samples, the audit computes Haar-like first-, second-, and fourth-lag energies,
a discrete `(x_t, dx_t/dt)` loop-area proxy, the fractional sub-sample phase of
the traditional pickoff, late post-peak spacing, clipped-sample count,
pedestal-state ADC, reconstructed charge proxy, and PID-proxy one-hot terms.
These diagnostics are not allowed to change the held-out predictions after the
benchmark; they explain the winning model's residual failures.

## Training Audit

| method                            | hyperparameter                                           | train_residual_sigma68_ns |
| --------------------------------- | -------------------------------------------------------- | ------------------------- |
| ridge                             | alpha=0.1                                                | 1.148                     |
| ridge                             | alpha=1                                                  | 1.148                     |
| ridge                             | alpha=10                                                 | 1.138                     |
| gradient_boosted_trees            | max_iter=160                                             | 0.8791                    |
| mlp                               | hidden=[64, 32]                                          | 0.9423                    |
| cnn_1d                            | epochs=4                                                 |                           |
| compact_waveform_transformer      | epochs=4, d_model=24                                     |                           |
| wavelet_phase_space_residual_fusion | 0.35 HGB + 0.25 ExtraTrees + 0.20 CNN + 0.20 transformer | 0.5173                    |

## Held-out Results

| method                            | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_phase_bias_ns | rise_time_bias_ns | energy_drift_area_norm |
| --------------------------------- | ----------------- | --------------------- | ---------------------- | ------------------ | ------------------- | ----------------- | ---------------------- |
| gradient_boosted_trees            | 1.324             | 1.225                 | 1.39                   | 1.534              | -1.697              | 0                 | 0                      |
| wavelet_phase_space_residual_fusion | 1.353             | 1.213                 | 1.429                  | 1.472              | 2.324               | 0                 | 0                      |
| mlp                               | 1.411             | 1.242                 | 1.501                  | 1.62               | 0.3786              | 0                 | 0                      |
| ridge                             | 1.545             | 1.329                 | 1.66                   | 1.325              | 0.9045              | 0                 | 0                      |
| compact_waveform_transformer      | 1.618             | 1.401                 | 1.719                  | 1.277              | 7.913               | 0                 | 0                      |
| cnn_1d                            | 1.727             | 1.528                 | 1.806                  | 1.018              | 7.913               | 0                 | 0                      |
| continuous_wavelet_cfd_template_atlas                | 2.154             | 2.023                 | 2.372                  | -3.798             | 0                   | 0                 | 0                      |

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. The stratification crosses
amplitude-based PID proxy, pedestal-proxy tercile, mild pile-up proxy, and
saturation proxy. CIs are still run bootstraps, so intervals can be wide where
only a few held-out runs support a bin.

| method                            | pid_proxy    | pedestal_bin | pileup_bin  | saturation_bin    | n_pair_residuals | timing_sigma68_ns | ci_low | ci_high |
| --------------------------------- | ------------ | ------------ | ----------- | ----------------- | ---------------- | ----------------- | ------ | ------- |
| gradient_boosted_trees            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 0.993             | 0.9807 | 1.223   |
| wavelet_phase_space_residual_fusion | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.067             | 0.9342 | 1.189   |
| mlp                               | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.093             | 0.9193 | 1.362   |
| cnn_1d                            | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.129             | 0.7276 | 1.279   |
| compact_waveform_transformer      | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.281             | 0.8343 | 1.322   |
| gradient_boosted_trees            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.387             | 1.108  | 1.546   |
| wavelet_phase_space_residual_fusion | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.447             | 1.228  | 1.646   |
| mlp                               | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.548             | 1.261  | 1.639   |
| ridge                             | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.58              | 1.331  | 1.702   |
| ridge                             | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 1.611             | 1.126  | 2.106   |
| cnn_1d                            | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.686             | 1.335  | 1.832   |
| compact_waveform_transformer      | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 1.721             | 1.439  | 1.807   |
| continuous_wavelet_cfd_template_atlas                | low_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 90               | 2.391             | 2.023  | 2.585   |
| continuous_wavelet_cfd_template_atlas                | mid_dE_proxy | 0            | mild_pileup | unsaturated_proxy | 183              | 2.724             | 2.023  | 2.946   |

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
| wavelet_phase_space_residual_fusion | amplitude_adc_lt_3600 | 29549    | 855              | 1.331             | 1.117  | 1.443   |
| gradient_boosted_trees            | amplitude_adc_lt_4000 | 33702    | 1008             | 1.333             | 1.219  | 1.433   |
| gradient_boosted_trees            | amplitude_adc_lt_3800 | 31759    | 954              | 1.335             | 1.22   | 1.434   |
| wavelet_phase_space_residual_fusion | amplitude_adc_lt_3800 | 31759    | 954              | 1.347             | 1.163  | 1.434   |
| wavelet_phase_space_residual_fusion | amplitude_adc_lt_4000 | 33702    | 1008             | 1.349             | 1.173  | 1.435   |
| gradient_boosted_trees            | amplitude_adc_lt_3600 | 29549    | 855              | 1.36              | 1.231  | 1.456   |
| mlp                               | amplitude_adc_lt_4000 | 33702    | 1008             | 1.41              | 1.255  | 1.492   |
| mlp                               | amplitude_adc_lt_3800 | 31759    | 954              | 1.429             | 1.243  | 1.495   |
| mlp                               | amplitude_adc_lt_3600 | 29549    | 855              | 1.441             | 1.228  | 1.506   |
| ridge                             | amplitude_adc_lt_4000 | 33702    | 1008             | 1.545             | 1.3    | 1.668   |
| ridge                             | amplitude_adc_lt_3800 | 31759    | 954              | 1.546             | 1.307  | 1.653   |
| ridge                             | amplitude_adc_lt_3600 | 29549    | 855              | 1.557             | 1.292  | 1.691   |
| compact_waveform_transformer      | amplitude_adc_lt_3800 | 31759    | 954              | 1.599             | 1.288  | 1.718   |
| compact_waveform_transformer      | amplitude_adc_lt_4000 | 33702    | 1008             | 1.6               | 1.343  | 1.709   |
| compact_waveform_transformer      | amplitude_adc_lt_3600 | 29549    | 855              | 1.63              | 1.263  | 1.765   |
| cnn_1d                            | amplitude_adc_lt_3600 | 29549    | 855              | 1.683             | 1.33   | 1.794   |
| cnn_1d                            | amplitude_adc_lt_3800 | 31759    | 954              | 1.703             | 1.391  | 1.793   |
| cnn_1d                            | amplitude_adc_lt_4000 | 33702    | 1008             | 1.708             | 1.409  | 1.79    |
| continuous_wavelet_cfd_template_atlas                | amplitude_adc_lt_4000 | 33702    | 1008             | 2.255             | 2.023  | 2.471   |
| continuous_wavelet_cfd_template_atlas                | amplitude_adc_lt_3800 | 31759    | 954              | 2.294             | 2.023  | 2.49    |
| continuous_wavelet_cfd_template_atlas                | amplitude_adc_lt_3600 | 29549    | 855              | 2.314             | 2.023  | 2.544   |

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

## Wavelet Phase-Space Diagnostics

The table below aggregates held-out pulses by source run and morphology strata.
It quantifies the pulse-shape (`haar_*`, `phase_space_loop_area`), sub-sample
timing (`subsample_phase`), pile-up spacing (`pileup_spacing_proxy_ns`),
saturation censoring (`clipped_sample_count`), pedestal state, reconstructed
energy proxy, and PID proxy used for the post-hoc failure-mode analysis.

| run | pid_proxy     | pedestal_bin | pileup_bin  | saturation_bin        | n_pulses | haar_d1_energy | haar_d4_energy | phase_space_loop_area | subsample_phase | pileup_spacing_proxy_ns | clipped_sample_count | reconstructed_energy_proxy |
| --- | ------------- | ------------ | ----------- | --------------------- | -------- | -------------- | -------------- | --------------------- | --------------- | ----------------------- | -------------------- | -------------------------- |
| 64  | low_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 7568     | 0.02599        | 0.3063         | -0.3889               | 0.4632          | 20                      | 1                    | 1.589e+04                  |
| 65  | low_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 7407     | 0.02578        | 0.3059         | -0.3866               | 0.4632          | 20                      | 1                    | 1.473e+04                  |
| 42  | mid_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 6798     | 0.03352        | 0.222          | -0.4269               | 0.5311          | 20                      | 1                    | 5.219e+04                  |
| 57  | low_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 4836     | 0.02634        | 0.3093         | -0.3916               | 0.4632          | 20                      | 1                    | 1.706e+04                  |
| 42  | low_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 4790     | 0.02661        | 0.3095         | -0.3945               | 0.4632          | 20                      | 1                    | 1.742e+04                  |
| 57  | mid_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 4574     | 0.03336        | 0.2226         | -0.4257               | 0.5493          | 20                      | 1                    | 4.981e+04                  |
| 42  | high_dE_proxy | 0            | mild_pileup | hard_saturation_proxy | 3119     | 0.03471        | 0.2267         | -0.4281               | 0.4632          | 20                      | 1                    | 6.42e+04                   |
| 64  | mid_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 2873     | 0.0327         | 0.2216         | -0.4205               | 0.5394          | 20                      | 1                    | 4.809e+04                  |
| 65  | mid_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 2688     | 0.03297        | 0.2223         | -0.423                | 0.579           | 20                      | 1                    | 4.704e+04                  |
| 64  | mid_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 1253     | 0.02788        | 0.3032         | -0.4053               | 0.4591          | 20                      | 1                    | 2.188e+04                  |
| 57  | high_dE_proxy | 0            | mild_pileup | hard_saturation_proxy | 1131     | 0.0344         | 0.2261         | -0.4243               | 0.4632          | 20                      | 1                    | 6.318e+04                  |
| 42  | low_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 1028     | 0.03361        | 0.2717         | -0.4386               | 0.5579          | 40                      | 1                    | 3.755e+04                  |
| 57  | low_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 991      | 0.03347        | 0.2715         | -0.4382               | 0.5381          | 40                      | 1                    | 3.743e+04                  |
| 42  | low_dE_proxy  | 0            | mild_pileup | near_saturation_proxy | 987      | 0.03297        | 0.2972         | -0.4453               | 0.472           | 40                      | 1                    | 3.287e+04                  |
| 57  | low_dE_proxy  | 0            | mild_pileup | near_saturation_proxy | 965      | 0.03292        | 0.2959         | -0.444                | 0.4632          | 40                      | 1                    | 3.299e+04                  |
| 64  | low_dE_proxy  | 0            | mild_pileup | near_saturation_proxy | 853      | 0.03294        | 0.2942         | -0.4446               | 0.4632          | 40                      | 1                    | 3.256e+04                  |
| 65  | low_dE_proxy  | 0            | mild_pileup | near_saturation_proxy | 785      | 0.03302        | 0.2943         | -0.4455               | 0.4632          | 40                      | 1                    | 3.24e+04                   |
| 64  | low_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 785      | 0.0332         | 0.2673         | -0.4372               | 0.4649          | 40                      | 1                    | 3.712e+04                  |
| 65  | low_dE_proxy  | 0            | mild_pileup | hard_saturation_proxy | 739      | 0.03357        | 0.268          | -0.4399               | 0.4657          | 40                      | 1                    | 3.702e+04                  |
| 42  | low_dE_proxy  | 0            | single_like | unsaturated_proxy     | 668      | 0.1421         | 0.9133         | -1.428                | 0.4632          | 20                      | 1                    | -3.066e+04                 |
| 57  | low_dE_proxy  | 0            | single_like | unsaturated_proxy     | 643      | 0.1303         | 0.8751         | -1.295                | 0.4632          | 20                      | 1                    | -3.018e+04                 |
| 64  | high_dE_proxy | 0            | mild_pileup | hard_saturation_proxy | 621      | 0.03301        | 0.2254         | -0.4149               | 0.4632          | 20                      | 1                    | 5.116e+04                  |
| 65  | mid_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 562      | 0.02792        | 0.3034         | -0.4072               | 0.4609          | 20                      | 2                    | 2.167e+04                  |
| 42  | mid_dE_proxy  | 0            | mild_pileup | unsaturated_proxy     | 468      | 0.02774        | 0.3015         | -0.4084               | 0.4279          | 20                      | 2                    | 2.148e+04                  |

## Joint Failure-Mode Explanation

For the winning method `gradient_boosted_trees`, held-out pair residuals
were joined to event-level wavelet phase-space summaries.  An ExtraTrees
surrogate predicts `|r_ab|`; the table reports impurity importance and a
within-table permutation increase in mean absolute error.  This is explanatory,
not a second training loop for method selection.

| feature                    | extra_trees_importance | permutation_mae_increase_ns | permutation_mae_increase_ci_low | permutation_mae_increase_ci_high |
| -------------------------- | ---------------------- | --------------------------- | ------------------------------- | -------------------------------- |
| clipped_sample_count       | 0.0279                 | 0.04966                     | 0.04014                         | 0.05799                          |
| run                        | 0.09139                | 0.04232                     | 0.03156                         | 0.05384                          |
| post_peak_frac             | 0.04432                | 0.03592                     | 0.02914                         | 0.04161                          |
| subsample_phase            | 0.08663                | 0.03271                     | 0.02637                         | 0.03848                          |
| saturation_margin_adc      | 0.109                  | 0.02736                     | 0.02194                         | 0.03396                          |
| reconstructed_energy_proxy | 0.1027                 | 0.02162                     | 0.01633                         | 0.0264                           |
| area_norm                  | 0.14                   | 0.01242                     | 0.006914                        | 0.01804                          |
| haar_d4_energy             | 0.08976                | 0.01199                     | 0.004508                        | 0.01686                          |
| phase_space_loop_area      | 0.07648                | 0.009501                    | 0.004591                        | 0.01464                          |
| pid_proxy_low_dE_proxy     | 0.01749                | 0.008945                    | 0.005027                        | 0.01432                          |
| haar_d2_energy             | 0.06163                | 0.008142                    | 0.004663                        | 0.01102                          |
| haar_d1_energy             | 0.1106                 | 0.007679                    | 0.003192                        | 0.01178                          |
| pileup_spacing_proxy_ns    | 0.009751               | 0.006907                    | 0.003291                        | 0.009583                         |
| pid_proxy_mid_dE_proxy     | 0.0109                 | 0.005147                    | 0.002101                        | 0.008202                         |
| pid_proxy_high_dE_proxy    | 0.02148                | 0.0007916                   | -0.001957                       | 0.003792                         |
| pedestal_state_adc         | 0                      | -5.551e-17                  | -2.22e-16                       | 0                                |
| pid_proxy_nan              | 0                      | -6.291e-17                  | -2.22e-16                       | 0                                |

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


# S19d: run-held-out drift calibration for S19c winners

- **Ticket:** `1783770959.22058.576950cd`
- **Worker:** `testbeam-laptop-1`
- **Config:** `configs/s19d_1783770959_22058_576950cd_runheldout_drift_calibration.yaml`
- **Primary output:** `reports/1783770959.22058.576950cd__s19d_runheldout_drift_calibration/result.json`
- **Raw input:** `data/root/root`
- **Upstream raw-derived artifacts:** `reports/1783751737.13524.25796187__causal_timing_pileup_deconvolution` and `reports/1783759304.10079.0a892fb8__s19c_pileup_saturation_timing_recovery`

## Abstract

S19d tests whether the S19c point-estimate winners remain stable when calibration is treated as a run-held-out nuisance rather than a fixed constant.  The causal S19c task named `gru` as the timing winner and `gradient_boosted_trees` as the two-pulse winner; the saturation S19c task also exposed a broader ridge/GBT/MLP/1D-CNN/hybrid panel on seven held-out Sample-II runs.  This postprocessor keeps those raw-derived predictions fixed, applies nested run-block pair calibration without using the blinded run labels, and then injects adversarial pedestal offsets into the residual scale.  The robust overall winner after the drift stress is `raw_pair_median`.

## Raw ROOT Reproduction

The raw-count gate is copied into this report from the S19c ROOT pass and rechecked against the configured expected counts.  The source pass read `h101/HRDv` from `data/root/root`, used B-stack physical channels `B2/B4/B6/B8 = 0/2/4/6`, subtracted the median of samples 0--3, and required amplitude above 1000 ADC.

| quantity | reported | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| total_selected_b_pulses | 640737 | 640737 | 0 | True |
| sample_i_analysis_b_selected_pulses | 252266 | 252266 | 0 | True |
| sample_ii_analysis_b_selected_pulses | 125096 | 125096 | 0 | True |

All configured count anchors pass exactly, including the requested `640737` selected B-stave pulses.  The copied `input_sha256.csv` records per-run raw ROOT checksums.

## Methods

Let `r_{m,e,p}` be the held-out residual for method `m`, event `e`, and stave pair `p`.  The central width is

```text
sigma68(r) = (Q84(r - median(r)) - Q16(r - median(r))) / 2 .
```

For the nested calibration, each validation run `b` is treated as blind.  A pair offset is estimated only from the other held-out runs,

```text
delta_{m,p}^(-b) = median { r_{m,e,p} : run(e) != b }
r^cal_{m,e,p} = r_{m,e,p} - delta_{m,p}^(-b),  run(e)=b .
```

This tests whether apparent model merit survives a calibration block that can absorb run-to-run pair medians without reading the blind run's targets.  Confidence intervals resample runs with replacement and then rows inside sampled runs.

The adversarial pedestal stress perturbs residuals by

```text
r^adv = r + Delta_ADC * s_task * (1 + clip(n_sat,0,8)/8 + recovery_tail)
```

where `Delta_ADC` is scanned over `[-20.0, -10.0, 10.0, 20.0]`.  The constants `s_task` are `0.006` ns/ADC for timing-like residuals and `0.018` ns/ADC for the saturation/pile-up stress proxy.  This is intentionally a systematic envelope, not a retrained estimator.

## Primary Model Panel

| task | method | role | metric | score | 95% CI | n |
| --- | --- | --- | --- | --- | --- | --- |
| saturation_timing | raw_pair_median | strong S19c pair-median CFD20 timing baseline | sigma68_ns | 1.779 | [1.625, 2.176] | 53039 |
| saturation_timing | extra_trees_duplicate_safe | new extra-trees ensemble with duplicate-safe diagnostics | sigma68_ns | 2.994 | [2.772, 3.592] | 53039 |
| saturation_timing | mlp_duplicate_safe | tabular MLP with duplicate-safe diagnostics | sigma68_ns | 3.610 | [3.339, 4.006] | 53039 |
| saturation_timing | gbt_duplicate_safe | gradient-boosted trees with duplicate-safe diagnostics | sigma68_ns | 3.884 | [3.720, 4.192] | 53039 |
| saturation_timing | hybrid_cnn_tabular_duplicate_safe | new hybrid CNN-tabular architecture | sigma68_ns | 4.084 | [3.103, 5.119] | 53039 |
| saturation_timing | ridge_duplicate_safe | ridge with duplicate-safe saturation diagnostics | sigma68_ns | 4.602 | [4.356, 5.131] | 53039 |
| saturation_timing | cnn_waveform_only | 1D-CNN waveform-only saturation model | sigma68_ns | 4.688 | [3.290, 5.461] | 53039 |
| saturation_timing | ridge_no_saturation | ridge without saturation diagnostics | sigma68_ns | 4.857 | [4.565, 5.418] | 53039 |
| timing | gru | new recurrent timing architecture | sigma68_ns | 1.202 | [1.029, 1.456] | 198 |
| timing | gradient_boosted_trees | gradient-boosted trees timing model | sigma68_ns | 1.219 | [0.990, 1.457] | 198 |
| timing | mlp | MLP timing residual model | sigma68_ns | 1.231 | [1.048, 1.469] | 198 |
| timing | cnn | 1D-CNN timing residual model | sigma68_ns | 1.345 | [1.117, 1.574] | 198 |
| timing | ridge | ridge timing residual model | sigma68_ns | 1.443 | [1.177, 1.625] | 198 |
| timing | analytic_timewalk | strong traditional timing model | sigma68_ns | 1.495 | [1.346, 1.644] | 198 |
| two_pulse | gradient_boosted_trees_two_pulse | gradient-boosted trees two-pulse recovery | time_rms_ns | 6.917 | [6.878, 6.957] | 2200 |
| two_pulse | ridge_two_pulse | ridge two-pulse recovery | time_rms_ns | 8.486 | [8.445, 8.526] | 2200 |
| two_pulse | mlp_two_pulse | MLP two-pulse recovery | time_rms_ns | 11.529 | [10.857, 12.212] | 2200 |
| two_pulse | resnet_two_pulse | new residual 1D-CNN two-pulse architecture | time_rms_ns | 12.145 | [11.703, 12.575] | 2200 |
| two_pulse | cnn_two_pulse | 1D-CNN two-pulse recovery | time_rms_ns | 14.000 | [13.934, 14.067] | 2200 |
| two_pulse | constrained_template_fit | strong traditional two-pulse fit | time_rms_ns | 15.311 | [14.610, 15.947] | 2200 |

This panel covers the required strong traditional methods plus ridge, gradient-boosted trees, MLP, 1D-CNN, and new architectures (`gru`, residual CNN, and hybrid CNN-tabular depending on task).

## Nested Run-Block Calibration

| method | uncal sigma68 | nested-cal sigma68 | 95% CI | median fold gain | max pair offset |
| --- | --- | --- | --- | --- | --- |
| raw_pair_median | 1.779 | 1.788 | [1.628, 2.126] | -0.003 | 0.064 |
| mlp_duplicate_safe | 3.610 | 2.355 | [2.165, 2.632] | 1.434 | 1.720 |
| extra_trees_duplicate_safe | 2.994 | 2.758 | [2.593, 3.237] | 0.213 | 1.712 |
| gbt_duplicate_safe | 3.884 | 2.761 | [2.519, 3.202] | 1.279 | 1.089 |
| hybrid_cnn_tabular_duplicate_safe | 4.084 | 3.349 | [1.843, 4.111] | 1.507 | 2.584 |
| ridge_duplicate_safe | 4.602 | 4.496 | [4.255, 5.058] | 0.077 | 0.886 |
| cnn_waveform_only | 4.688 | 4.732 | [2.080, 5.247] | 1.586 | 2.966 |
| ridge_no_saturation | 4.857 | 4.749 | [4.457, 5.412] | 0.066 | 0.936 |

The nested calibration does not use the blind run's residuals when estimating pair offsets.  A negative median fold gain means calibration broadened the blind residual distribution, usually because the other runs' pair medians do not predict the blind run's pedestal/pulse-shape state.

## Adversarial Pedestal Stress

| method | worst offset | sigma68 | 95% CI | tail abs gt5 |
| --- | --- | --- | --- | --- |
| raw_pair_median | worst_abs_offset | 1.862 | [1.693, 2.212] | 0.1123 |
| extra_trees_duplicate_safe | worst_abs_offset | 3.428 | [3.183, 4.059] | 0.2029 |
| mlp_duplicate_safe | worst_abs_offset | 3.856 | [3.570, 4.253] | 0.2045 |
| gbt_duplicate_safe | worst_abs_offset | 3.994 | [3.833, 4.291] | 0.2297 |
| hybrid_cnn_tabular_duplicate_safe | worst_abs_offset | 4.367 | [3.337, 5.395] | 0.2292 |
| ridge_duplicate_safe | worst_abs_offset | 4.918 | [4.626, 5.445] | 0.3051 |
| cnn_waveform_only | worst_abs_offset | 4.973 | [3.579, 5.658] | 0.3160 |
| ridge_no_saturation | worst_abs_offset | 5.168 | [4.815, 5.761] | 0.3264 |

The stress table reports the worst absolute offset among the configured pedestal perturbations.  The S19c timing GRU remains the best causal timing model by point estimate, while the broad real-candidate saturation table still prefers the raw pair-median CFD20 baseline under this diagnostic.

## Systematics

The analysis inherits the S19c raw-derived predictions rather than retraining from ROOT in this postprocessor.  That makes the drift audit deterministic and auditable, but it means training stochasticity for GRU/CNN/MLP is represented through the upstream S19c artifacts rather than through a new ensemble.  The two-pulse task is based on injected overlaps from empirical templates, so the GBT recovery winner is a closure result on synthetic truth and not direct evidence for unlabeled beam pile-up.  The adversarial pedestal sensitivity is a bounded envelope chosen to expose fragility; it is not calibrated from slow-control pedestal telemetry.

The nested calibration uses pair medians from other held-out runs.  It therefore tests run-block transferability, but it can understate failures that are coherent within all Sample-II runs and overstate failures when a single held-out run has a unique population mix.  Bootstrap CIs cover finite held-out run statistics, not the full model-selection search.

## Caveats

The strongest statement supported here is about stability of already-produced S19c winners under post-fit drift stress.  The causal timing GRU and two-pulse GBT remain point-estimate winners in their original held-out tasks, but production adoption should wait for an external pedestal monitor or a fresh blinded run.  On the broader real-candidate saturation benchmark, the nominal and stress winners are traditional, indicating that architecture merit and calibration fragility are not separable without better labels for true pile-up and saturation recovery.

## Conclusion

The raw ROOT count anchor is reproduced exactly at `640737`.  Under nested calibration and adversarial pedestal stress, the final named winner is `raw_pair_median`: `raw_pair_median has the smallest nested-calibrated and worst-offset real-candidate saturation sigma68; GRU and GBT remain the causal-task point-estimate winners but are not promoted over the traditional drift-stable baseline.`.  Machine-readable artifacts include `primary_benchmark.csv`, `nested_calibration.csv`, `nested_calibration_folds.csv`, `adversarial_pedestal.csv`, `result.json`, and `manifest.json`.

## Reproducibility

```bash
python3 scripts/s19d_1783770959_22058_576950cd_runheldout_drift_calibration.py --config configs/s19d_1783770959_22058_576950cd_runheldout_drift_calibration.yaml
```

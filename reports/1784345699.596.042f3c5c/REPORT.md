# S44a: Derivative-Integral Pulse-Shape Timing Pedestal Benchmark

**Ticket:** `1784345699.596.042f3c5c`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT source:** `data/root/root`

## Abstract

This study tests whether derivative and charge-integral pulse-shape observables carry timing-walk and pedestal-state information beyond amplitude-only calibration. The analysis starts from raw B-stack ROOT files, reproduces the canonical selected-pulse count exactly, and compares a strong traditional constant-fraction plus derivative/integral timing estimator with ridge regression, gradient-boosted trees, an MLP, a 1D-CNN, and a compact waveform attention model. The winner recorded in `result.json` is **`compact_waveform_attention`**, with held-out downstream pair sigma68 **1.853 ns** and 95% run-bootstrap CI [1.774, 1.952] ns.

## Raw-ROOT Reproduction Gate

The input is the `HRDv` branch of the raw B-stack files. For B2, B4, B6, and B8, the pedestal is the median of samples 0--3, and a pulse is selected when

`A_i = max_t (x_it - median(x_i0, ..., x_i3)) > 1000 ADC`.

This rerun reproduced **640,737** selected B-stave pulses against the expected **640,737** with zero tolerance.

## Estimands and Equations

For a normalized waveform `w_it`, the traditional phase is

`t_trad = 0.62 t_CFD(0.2) + 0.23 t_CFD(0.5) + 0.15 t_d0 - 0.9 I_asym + 0.18 I_tail - 0.015 (b - median(b)) - 0.04 (log(1+A) - median(log(1+A)))`.

Here `t_d0` is the derivative zero crossing near the peak, `I_asym = (I_late - I_early)/(I_late + I_early)`, and `I_tail` is the positive tail integral fraction. Learned methods predict a residual correction `delta_hat` from the waveform and observables, giving `t_hat = t_trad - delta_hat`.

For every held-out event with at least two downstream staves, pair residuals are `r_ab = (t_hat,a - 0.078 z_a) - (t_hat,b - 0.078 z_b)`. The primary metric is `sigma68 = (Q84(r) - Q16(r))/2`. Confidence intervals are non-parametric bootstraps over run labels.

## Methods

The traditional baseline combines constant-fraction timing, derivative zero-crossing, charge-integration asymmetry, tail integral fraction, and a pedestal proxy. Ridge regression supplies the linear amplitude-and-shape reference; histogram gradient-boosted trees model nonlinear tabular structure; the MLP uses the same engineered and waveform inputs; the 1D-CNN treats the 18-sample pulse as a short signal with auxiliary features; and the compact waveform attention model is a one-layer, four-head transformer encoder. The attention architecture is sensible here because derivative and integral cues are phase-local but pedestal contamination is global over the short trace.

## Training Audit

| method | hyperparameter | train_residual_sigma68_ns |
| --- | --- | --- |
| ridge | alpha=0.1 | 1.675 |
| ridge | alpha=1 | 1.670 |
| ridge | alpha=10 | 1.645 |
| gradient_boosted_trees | max_iter=180 | 1.432 |
| mlp | hidden=[64, 32] | 1.489 |
| cnn_1d | epochs=4 |  |
| compact_waveform_attention | epochs=5, d_model=24, heads=4 |  |

## Held-out Method Table

| method | timing_sigma68_ns | timing_sigma68_ci_low | timing_sigma68_ci_high | median_residual_ns | shape_residual_abs_ns | phase_bias_vs_traditional_ns | energy_pid_delta_integral_asym |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| compact_waveform_attention | 1.853 | 1.774 | 1.952 | 0.7634 | 18.32 | 15.69 | 0.6293 |
| cnn_1d | 1.891 | 1.757 | 1.982 | 0.7433 | 18.32 | 15.69 | 0.6293 |
| ridge | 1.932 | 1.834 | 2.006 | 1.198 | 18.32 | 2.405 | 0.6293 |
| gradient_boosted_trees | 1.996 | 1.884 | 2.194 | 1.003 | 18.32 | 0.5112 | 0.6293 |
| mlp | 2.186 | 2.093 | 2.262 | 1.376 | 18.32 | 3.183 | 0.6293 |
| derivative_integral_cfd | 3.305 | 3.142 | 3.468 | -2.614 | 18.32 | 0 | 0.6293 |

## Pedestal-Stratified Failure Rates

Failure is defined as an absolute downstream pair residual above 10 ns. Rows are held-out run bootstraps.

| method | pid_proxy | pedestal_bin | pileup_bin | n_pair_residuals | failure_rate_abs_res_gt_10ns | failure_ci_low | failure_ci_high | timing_sigma68_ns |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| derivative_integral_cfd | low_dE_proxy | 0 | single_like | 93 | 0 | 0 | 0 | 2.577 |
| ridge | low_dE_proxy | 0 | single_like | 93 | 0 | 0 | 0 | 1.719 |
| compact_waveform_attention | low_dE_proxy | 0 | single_like | 93 | 0 | 0 | 0 | 1.642 |
| cnn_1d | low_dE_proxy | 0 | single_like | 93 | 0 | 0 | 0 | 1.758 |
| compact_waveform_attention | low_dE_proxy | 0 | mild_pileup | 897 | 0.008919 | 0 | 0.01441 | 1.852 |
| cnn_1d | low_dE_proxy | 0 | mild_pileup | 897 | 0.008919 | 0 | 0.01434 | 1.900 |
| ridge | low_dE_proxy | 0 | mild_pileup | 897 | 0.008919 | 0 | 0.01441 | 1.852 |
| mlp | low_dE_proxy | 0 | mild_pileup | 897 | 0.008919 | 0 | 0.01441 | 2.030 |
| gradient_boosted_trees | low_dE_proxy | 0 | mild_pileup | 897 | 0.01003 | 0 | 0.01452 | 1.833 |
| derivative_integral_cfd | low_dE_proxy | 0 | mild_pileup | 897 | 0.01003 | 0 | 0.01633 | 3.166 |
| mlp | low_dE_proxy | 0 | single_like | 93 | 0.01075 | 0 | 0.02988 | 2.116 |
| gradient_boosted_trees | low_dE_proxy | 0 | single_like | 93 | 0.01075 | 0 | 0.02941 | 2.917 |

## Leakage and Systematics Checks

| check | pass | value | detail |
| --- | --- | --- | --- |
| raw_root_reproduction | True | 640737 | canonical selected-pulse count |
| train_heldout_run_overlap | True | 0 | split by run |
| finite_traditional_phase | True | 59613 | traditional anchor for all held-out pulses |
| training_target_rows | True | 14646 | downstream closure residual targets |
| model_panel_complete | True | derivative_integral_cfd,ridge,gradient_boosted_trees,mlp,cnn_1d,compact_waveform_attention | traditional plus requested ML/NN panel |

## Systematics and Caveats

1. The timing target is self-supervised from downstream same-event closure, so it is a relative timing benchmark rather than an external-clock calibration.
2. The PID downstream delta is an amplitude/integral proxy, not truth PID.
3. Pedestal bins are built from train-run quantiles and transferred to held-out runs; this makes drift visible but does not identify its electronics cause.
4. The waveform is only 18 samples long. The compact attention model is deliberately small to avoid a high-variance architecture search.
5. Bootstrap units are held-out runs. The interval is appropriate for run transfer, but with four held-out runs it is necessarily coarse.

## Conclusion

The winner is **`compact_waveform_attention`** by held-out run-split downstream timing sigma68. The derivative/integral observables are retained in every learned model input and in the traditional reference, allowing the benchmark to isolate whether ML/NN models add value beyond those physically interpretable observables.

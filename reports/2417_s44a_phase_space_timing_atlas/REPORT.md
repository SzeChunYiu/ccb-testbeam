# S44a: Phase-Space Pulse-Shape Timing Atlas

**Ticket:** `#2417`  
**Worker:** `testbeam-laptop-1`  
**Raw ROOT source:** `/home/billy/ccb-data/data/extracted/root/root`  
**Primary artifact:** `reports/2417_s44a_phase_space_timing_atlas/result.json`

## Abstract

This study benchmarks a physically interpretable timing baseline against a fixed ML/NN panel on B-stack raw ROOT waveforms. The traditional method is a constant-fraction timing estimator augmented with derivative, integral-asymmetry, tail, pedestal, and amplitude terms. The learned comparators are ridge regression, gradient-boosted trees, MLP, 1D-CNN, and a compact waveform-attention model. The train/test split is by run; confidence intervals are non-parametric bootstraps over held-out runs.

The raw ROOT reproduction gate matched exactly: **640,737** selected B-stave pulses were reproduced against the expected **640,737**. The winner recorded in `result.json` is **`compact_waveform_attention`**, with held-out downstream pair timing `sigma68 = 1.853 ns` and 95% run-bootstrap CI `[1.774, 1.952] ns`. The best traditional baseline, `derivative_integral_cfd`, gives `sigma68 = 3.305 ns` with CI `[3.142, 3.468] ns`.

## Raw ROOT Reproduction

The ROOT branch `HRDv` is reshaped event-by-event to `(8, 18)`. For each even B-stave channel B2/B4/B6/B8, the pedestal is the median of samples 0--3. A pulse is selected when the pedestal-subtracted maximum exceeds 1000 ADC:

`A_{i,c} = max_t [v_{i,c}(t) - median(v_{i,c}(0),...,v_{i,c}(3))] > 1000`.

Independent verification in this worker produced:

| quantity | expected | reproduced | delta | pass |
| --- | ---: | ---: | ---: | --- |
| total selected B-stave pulses | 640,737 | 640,737 | 0 | true |

The first and last checked run totals were `(31, 27871), (32, 28240), (33, 48737)` and `(63, 18817), (64, 14630), (65, 13038)`, confirming that the count comes from raw run files rather than a cached summary.

## Split And Estimand

Training runs are `31,32,33,34,35,36,37,39,40,41,44,45,46,47,48,49,50,51,52,53,54,55,56,58,59,60,61,62,63`. Held-out runs are `42,57,64,65`. This split leaves **581,124** selected training pulses and **59,613** selected held-out pulses. The timing target is built from downstream same-event closure pairs, yielding **1,224** held-out pair residuals.

For stave/channel `c`, define a corrected waveform `x_c(t)=v_c(t)-b_c`, amplitude `A_c=max_t x_c(t)`, and constant-fraction crossing `t_f(c)` by linear interpolation before the peak at threshold `f A_c`. The traditional phase estimate is

`t_trad = 0.62 t_CFD(0.2) + 0.23 t_CFD(0.5) + 0.15 t_d0 - 0.9 I_asym + 0.18 I_tail - 0.015 (b - median(b)) - 0.04 (log(1+A) - median(log(1+A)))`.

Here `t_d0` is a derivative zero crossing near the peak, `I_asym=(I_late-I_early)/(I_late+I_early)`, and `I_tail` is the positive tail fraction. Learned methods predict a correction `delta_hat_m(z_i)`, and the corrected time is

`t_hat_m = t_trad - delta_hat_m(z_i)`.

For downstream staves `a,b`, the residual is

`r_{i,ab}(m) = [t_hat_{i,a}(m) - tau z_a] - [t_hat_{i,b}(m) - tau z_b]`,

with `tau = 0.078 ns/cm`. The primary width is

`sigma68(m) = 0.5 * [Q84(r(m) - median(r(m))) - Q16(r(m) - median(r(m)))]`.

The 95% confidence interval resamples held-out runs with replacement 500 times and recomputes `sigma68` on each pooled bootstrap sample. This run-block bootstrap is the appropriate unit because the main systematic is run-to-run support and pedestal drift, not independent waveform noise.

## Methods

The traditional comparator, `derivative_integral_cfd`, is intentionally strong: it combines constant-fraction phase, derivative curvature, early/late charge balance, tail charge, pedestal level, and amplitude time-walk terms. It is not a bare CFD baseline.

Ridge regression is the linear ML reference and uses L2 regularization over waveform and engineered features. Gradient-boosted trees model nonlinear tabular interactions among amplitude, pedestal, derivative, and integral terms. The MLP uses the same tabular and waveform feature set with two hidden layers. The 1D-CNN treats the 18-sample pulse as a short sequence with local temporal filters. The new architecture, `compact_waveform_attention`, is a small one-layer attention model over waveform tokens; it is sensible here because the waveform is short enough for attention to compare leading-edge, peak, and tail samples without a large parameter count.

All methods use the same run split. Run number, event number, and held-out residuals are excluded from model inputs.

## Primary Results

| method | held-out pairs | sigma68 ns | 95% CI ns | median residual ns | phase bias vs traditional ns |
| --- | ---: | ---: | ---: | ---: | ---: |
| compact_waveform_attention | 1,224 | 1.853 | [1.774, 1.952] | 0.763 | 15.691 |
| cnn_1d | 1,224 | 1.891 | [1.757, 1.982] | 0.743 | 15.691 |
| ridge | 1,224 | 1.932 | [1.834, 2.006] | 1.198 | 2.405 |
| gradient_boosted_trees | 1,224 | 1.996 | [1.884, 2.194] | 1.003 | 0.511 |
| mlp | 1,224 | 2.186 | [2.093, 2.262] | 1.376 | 3.183 |
| derivative_integral_cfd | 1,224 | 3.305 | [3.142, 3.468] | -2.614 | 0.000 |

The attention and CNN rows are close, and their CIs overlap. The practical conclusion is therefore not that attention is categorically superior, but that compact sequence models using local pulse-shape information beat the derivative/integral traditional baseline under the registered held-out split. Ridge and boosted trees also improve substantially over the traditional baseline, showing that much of the gain is available from regularized amplitude-shape calibration rather than deep capacity alone.

## Pedestal And Failure-Stratum Checks

Failure is defined as `|r| > 10 ns`. The full stratum table is in `pedestal_failure_rates.csv`; representative held-out rows are:

| method | PID proxy | pedestal bin | pileup bin | pairs | failure rate | CI | sigma68 ns |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| derivative_integral_cfd | low_dE_proxy | 0 | single_like | 93 | 0.0000 | [0.0000, 0.0000] | 2.577 |
| ridge | low_dE_proxy | 0 | single_like | 93 | 0.0000 | [0.0000, 0.0000] | 1.719 |
| compact_waveform_attention | low_dE_proxy | 0 | single_like | 93 | 0.0000 | [0.0000, 0.0000] | 1.642 |
| compact_waveform_attention | low_dE_proxy | 0 | mild_pileup | 897 | 0.0089 | [0.0000, 0.0144] | 1.852 |
| gradient_boosted_trees | low_dE_proxy | 0 | mild_pileup | 897 | 0.0100 | [0.0000, 0.0145] | 1.833 |
| derivative_integral_cfd | low_dE_proxy | 0 | mild_pileup | 897 | 0.0100 | [0.0000, 0.0163] | 3.166 |

Physics-like pulse-shape degrees of freedom are those that retain timing improvement across mild-pileup and single-like strata: leading-edge phase, local curvature, and short-tail charge balance. Artifact-like degrees of freedom are pedestal-bin and pileup-bin movements that change support without a stable timing gain. The stable energy/PID proxy delta across methods indicates that the primary winner is not driven by a different downstream charge population.

## Leakage Checks

| check | pass | value | interpretation |
| --- | --- | ---: | --- |
| raw_root_reproduction | true | 640737 | canonical selected-pulse count reproduced from ROOT |
| train_heldout_run_overlap | true | 0 | no same-run leakage |
| finite_traditional_phase | true | 59613 | traditional anchor available for all held-out pulses |
| training_target_rows | true | 14646 | sufficient downstream closure targets for fitting |
| model_panel_complete | true | 6 methods | requested traditional plus ML/NN panel present |

The most important leakage control is the split by run. A row-random split would overstate performance because events from the same run share pedestal, trigger, and operating-state structure.

## Systematics And Caveats

The target is self-supervised from downstream timing closure, not an external clock. Therefore the absolute phase is not established; the result ranks relative residual correction methods. Held-out CIs use only four held-out runs, so intervals should be read as run-transfer uncertainty estimates, not asymptotic event-level errors. The compact attention architecture is deliberately small; the ticket tests whether a sensible short-sequence architecture helps, not whether large transformer scaling is useful. Pedestal bins use train-run quantiles transferred to held-out runs; this exposes drift but does not identify the electronics cause. Finally, the S44a generator script is not present in this checkout, so this worker independently revalidated the raw ROOT reproduction and preserved the tracked benchmark tables as generated artifacts.

## Verdict

`result.json` names **`compact_waveform_attention`** as the winner. It gives the smallest held-out downstream pair timing width, `1.853 ns [1.774, 1.952]`, compared with `3.305 ns [3.142, 3.468]` for the strong traditional derivative/integral CFD baseline. The result supports a cautious conclusion: compact waveform sequence models add timing information beyond derivative/integral CFD features, but the CNN result is close enough that the robust claim is sequence-shape value, not attention-specific dominance.

## Artifacts

- `result.json`
- `method_summary.csv`
- `pedestal_failure_rates.csv`
- `reproduction_counts_by_run.csv`
- `reproduction_match_table.csv`
- `leakage_checks.csv`
- `training_summary.csv`
- `input_sha256.csv`

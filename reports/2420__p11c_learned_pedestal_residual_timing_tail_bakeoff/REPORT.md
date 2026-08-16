# P11c - Learned-Pedestal Residual as a Timing-Tail Nuisance
- Study ID:      P11c
- Title:         learned-pedestal residual as a timing-tail nuisance
- Date:          2026-08-16
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S02/S04 timing fits, P11/S16 pedestal diagnostics
- Data anchor:   640,737 selected B-pulses reproduced from raw ROOT

**ML wins: sigma68 1.717 ns vs 2.061 ns (Delta=-0.344 ns, CI [-0.563, -0.095]), survives the implemented shuffle control.**

## Ticket claim provenance

`tn-ticket claim testbeam-laptop-3 --project testbeam` was run exactly once. The local helper returned `null|null|null` because the empty existing-claim query is string-interpolated, so issue #2420 was manually label-repaired to `factory:claimed`/`worker:testbeam-laptop-3` without running claim again.

## Reproduction gate

Command: `MPLCONFIGDIR=/tmp/matplotlib-p11c uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with pyarrow --with matplotlib --with torch python reports/2420__p11c_learned_pedestal_residual_timing_tail_bakeoff/run_p11c_bakeoff.py`

Expected: 640,737 selected B-stave pulses with baseline = median(samples 0-3), amplitude cut A > 1000 ADC, B staves {B2,B4,B6,B8}.

Seed: numpy/sklearn/torch random_state = 242011. Raw ROOT and sorted ROOT entries were required to satisfy `EVT == hrdEvtNo` in every loaded chunk.

| quantity                           | expected | reproduced | delta | pass |
| ---------------------------------- | -------- | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737   | 640737     | 0     | True |
| sample II analysis selected pulses | 125096   | 125096     | 0     | True |
| sample II analysis B2              | 88213    | 88213      | 0     | True |
| sample II analysis B4              | 21229    | 21229      | 0     | True |
| sample II analysis B6              | 11148    | 11148      | 0     | True |
| sample II analysis B8              | 4506     | 4506       | 0     | True |

## Key metrics table

Primary metric is held-out event-bootstrap pair-residual sigma68 in ns on runs [57, 65]. Delta is method minus the traditional binned CFD20 nuisance model; negative favors the candidate.

| method                      | family           | n_events | n_pair_residuals | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns | full_rms_ns | tail_frac_abs_gt5ns |
| --------------------------- | ---------------- | -------- | ---------------- | ---------- | ----------------- | ------------------ | ----------- | ------------------- |
| one_dimensional_cnn         | ml               | 130      | 390              | 1.717      | 1.511             | 1.888              | 1.722       | 0.007692            |
| gated_cnn_residual          | new_architecture | 130      | 390              | 1.749      | 1.607             | 1.917              | 1.824       | 0.007692            |
| ridge                       | ml               | 130      | 390              | 1.848      | 1.717             | 2.061              | 1.866       | 0.007692            |
| traditional_binned_cfd20    | traditional      | 130      | 390              | 2.061      | 1.863             | 2.242              | 1.963       | 0.005128            |
| hist_gradient_boosted_trees | ml               | 130      | 390              | 2.228      | 1.998             | 2.42               | 2.53        | 0.04872             |
| mlp                         | ml               | 130      | 390              | 2.415      | 2.194             | 2.635              | 2.442       | 0.03846             |

| method                      | delta_sigma68_vs_traditional_ns | ci_low_ns | ci_high_ns |
| --------------------------- | ------------------------------- | --------- | ---------- |
| one_dimensional_cnn         | -0.344                          | -0.5631   | -0.09511   |
| gated_cnn_residual          | -0.3115                         | -0.4916   | -0.05522   |
| ridge                       | -0.2122                         | -0.3725   | 0.03804    |
| hist_gradient_boosted_trees | 0.1677                          | -0.0441   | 0.4186     |
| mlp                         | 0.3542                          | 0.1623    | 0.6053     |

## Physics motivation

The timing endpoint is limited not only by pulse amplitude and peak phase but also by recoverability of the local pedestal after previous activity. S16h showed that the sorted `hrd.baseline` branch is not a perfect surrogate for the raw pretrigger pedestal. P11c tests whether the learned-pedestal residual proxy `b = median(raw samples 0-3) - hrd.baseline` explains the long timing tails after the usual S02 amplitude and peak-time controls.

## Methodology

### Data selection

The reproduction gate scans all configured B-stack reduced ROOT files and applies the S00 selector
\[
A_{is} = \max_t\left(x_{ist} - \mathrm{median}(x_{is0},x_{is1},x_{is2},x_{is3})\right) > 1000\ \mathrm{ADC},
\]
for event `i`, stave `s`, and sample `t`. Timing fits use downstream staves B4/B6/B8 and require all three downstream staves to pass the same cut in the same event. The timing table contains 14,040 selected downstream pulse rows and 4,680 complete three-stave events.

### Feature set

The nuisance feature set contains `log_amplitude`, `peak_sample`, `area_over_amp`, raw pretrigger median and peak-to-peak spread, sorted baseline, learned-pedestal residual `b`, sorted `hrdMax`, `hrdTrMax`, `hrdMaxTS`, trap pretrigger mean/spread, trap integral, trap standard deviation, and stave identity. The CNN methods additionally consume the 18-sample baseline-subtracted raw waveform.

### Traditional baseline

The incumbent is CFD20 plus a binned nuisance correction. The uncorrected time is
\[
t_{is} = 10\ \mathrm{ns}\,\tau_{0.20}(x_{is}),
\]
where `tau_0.20` is the linearly interpolated 20% constant-fraction crossing. Geometry correction subtracts `0.078 ns/cm` times a 2 cm stave spacing. The conventional nuisance model estimates
\[
\hat r_{is} = \mathrm{median}(r \mid s,\ \mathrm{amp\ bin},\ \mathrm{peak\ bin})
\]
on training runs, with stave-level fallback, and reports `t - rhat`. This is a strong, transparent S02/S04-style baseline because it directly models the known amplitude and phase timing covariates without allowing a high-capacity fit to memorize run structure.

### ML and NN methods

All ML methods predict the same leave-stave residual target
\[
r_{is} = t^c_{is} - \frac{1}{2}\sum_{q \ne s} t^c_{iq},
\]
where `tc` is the geometry-corrected CFD20 time. Training runs are [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 58, 59, 60, 61, 62, 63]; calibration runs are [56, 64]; held-out runs are [57, 65]. The fitted prediction is subtracted from CFD20 before pair residuals are recomputed. The benchmark includes Ridge(alpha=10.0), HistGradientBoostingRegressor(max_iter=180, max_leaf_nodes=31), MLPRegressor(hidden=(64, 32)), a two-layer 1D CNN over the waveform plus tabular features, and a new gated CNN residual model that multiplicatively gates convolution channels by tabular nuisance state.

### Leakage controls

The main leakage control is a target-shuffle ridge refit: the residual labels are permuted inside training rows, refit with the same features, calibrated on the same calibration runs, and evaluated on held-out runs. The run-family control is built into the split: no held-out run contributes training rows. Event leakage is limited by event-level bootstrap and by computing all reported pair metrics only from event identifiers absent from the training runs. The remaining caveat is that calibration runs share detector conditions with held-out runs, so the calibration offset is a nuisance centering operation, not proof of physics generalization.

| control                   | slice   | value | interpretation                                                  |
| ------------------------- | ------- | ----- | --------------------------------------------------------------- |
| runwise nuisance location | run_44  | 11.5  | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_45  | 11.5  | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_46  | 8.5   | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_47  | 8     | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_48  | 12.25 | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_49  | 10.25 | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_50  | 12.75 | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_51  | 12    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_52  | 15    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_53  | 13    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_54  | 11.5  | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_55  | 11.5  | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_56  | 11.75 | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_57  | 12    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_58  | 11.5  | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_59  | 10.5  | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_60  | 11    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_61  | 11    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_62  | 11    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_63  | 11    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_64  | 11    | reported as systematic, not a pass/fail leakage gate            |
| runwise nuisance location | run_65  | 10    | reported as systematic, not a pass/fail leakage gate            |
| target shuffle            | heldout | 3.145 | permuted training target; should not beat the unpermuted winner |

## Results

Run-level held-out results:

| run | method                      | n_events | n_pair_residuals | sigma68_ns | sigma68_ci_low_ns | sigma68_ci_high_ns |
| --- | --------------------------- | -------- | ---------------- | ---------- | ----------------- | ------------------ |
| 57  | traditional_binned_cfd20    | 64       | 192              | 2.062      | 1.689             | 2.27               |
| 65  | traditional_binned_cfd20    | 66       | 198              | 1.973      | 1.778             | 2.3                |
| 57  | ridge                       | 64       | 192              | 1.853      | 1.629             | 2.083              |
| 65  | ridge                       | 66       | 198              | 1.799      | 1.612             | 2.122              |
| 57  | hist_gradient_boosted_trees | 64       | 192              | 2.37       | 2.074             | 2.67               |
| 65  | hist_gradient_boosted_trees | 66       | 198              | 2.04       | 1.785             | 2.375              |
| 57  | mlp                         | 64       | 192              | 2.556      | 2.212             | 2.893              |
| 65  | mlp                         | 66       | 198              | 2.309      | 1.988             | 2.541              |
| 57  | one_dimensional_cnn         | 64       | 192              | 1.671      | 1.469             | 1.952              |
| 65  | one_dimensional_cnn         | 66       | 198              | 1.732      | 1.385             | 1.974              |
| 57  | gated_cnn_residual          | 64       | 192              | 1.669      | 1.464             | 1.883              |
| 65  | gated_cnn_residual          | 66       | 198              | 1.829      | 1.605             | 2.089              |

The winner written to `result.json` is `one_dimensional_cnn`. The comparison uses paired event bootstrap CIs, so the uncertainty reflects event-level resampling rather than treating three pair residuals per event as independent primary events.

## Interpretation

If the winner is an ML method, the result should be read as evidence that the learned-pedestal residual carries timing-tail nuisance information beyond amplitude and peak phase. If the traditional binned correction wins or ties, the result says the sorted-baseline residual is useful as a systematic diagnostic but not an adoptable high-capacity correction under this run split. In either case, the observable is a data-only timing-tail diagnostic; it does not establish an absolute per-particle time truth.

## MC verdict

MC validation not yet run - required to close this open question. Proposed: MV-S16i, inject recoverable pedestal offsets and sorted-baseline reconstruction errors into the electronics response, then repeat the same train/calibration/held-out split on truth-known simulated pulse trains.

## Open questions

1. MV-S16i: Does a GEANT4 plus electronics simulation with injected pedestal recoverability reproduce the observed learned-pedestal residual distribution and its timing-tail coupling?
2. P11d: Does a strictly causal learned-pedestal residual, trained only on pretrigger state and forced/random controls, improve held-out tails without post-trigger leakage?
3. S04m: Are the largest residual tails concentrated in high-current blocks after conditioning on amplitude, peak phase, and learned-pedestal residual?

## Provenance

Git commit:        68374937a0026eba71394446c496390ef51afa18
Data SHA256:       recorded in `manifest.json` for each raw and sorted ROOT input
Python:            3.13.12
scikit-learn:      imported at runtime by the runner
numpy / torch:     numpy 2.5.2; torch 2.13.0+cpu
Run host / job:    billy
Elapsed:           87.1 s
Artifacts:         `reports/2420__p11c_learned_pedestal_residual_timing_tail_bakeoff/{REPORT.md,result.json,manifest.json,*.csv,figures/*.png}`

## Systematics and caveats

The analysis intentionally uses held-out runs 57 and 65 because they sample the end of Sample I and Sample II rather than random event fragments. Bootstrap CIs are therefore conditional on these held-out runs and do not claim to cover all possible beam conditions. The sorted ROOT branches are reconstruction products, so any production use of the nuisance correction must preserve causal availability; this study uses raw pretrigger quantities for diagnostics and explicitly treats them as nuisance observables, not as deployable online inputs. The 1D-CNN and gated CNN are small by design to reduce run memorization, but they are still higher-capacity models than the binned baseline; lack of a CI-excluding win should be interpreted as non-adoption, not as absence of pedestal physics.

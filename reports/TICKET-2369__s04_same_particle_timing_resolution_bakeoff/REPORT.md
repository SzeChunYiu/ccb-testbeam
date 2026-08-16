# S04: Same-Particle Timing Resolution Rigorous Bakeoff

- **Ticket:** #2369
- **Author:** testbeam-laptop-1
- **Date:** 2026-08-16
- **Depends on:** S00, S03, frozen S05h residual panel
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `cfc84ffc12926fe2fca17b0a32418b9557a5054d`
- **Config:** `configs/s04_2369_same_particle_timing_resolution_bakeoff.yaml`

## 0. Question

Can the downstream same-particle timing resolution numbers in the notes be reproduced from raw ROOT anchors, and does any learned per-event residual model improve the run-held-out S04 resolution/coverage benchmark over a strong traditional pair-median variance-decomposition baseline?

## 1. Reproduction Gate

The raw gate rescans `HRDv` in the B-stack ROOT files under the S00 selector: B2/B4/B6/B8 physical channels 0/2/4/6, median pedestal from samples 0--3, and `max(waveform-pedestal)>1000 ADC`. The A-stack anchor is retained from the same raw scan as an independent timing-width sanity check.

| quantity | expected | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total_selected_b_pulses | 640737 | 640737 | 0 | 0 | True |
| sample_i_analysis_b_selected_pulses | 252266 | 252266 | 0 | 0 | True |
| sample_ii_analysis_b_selected_pulses | 125096 | 125096 | 0 | 0 | True |
| sample_iv_a1_a3_pairs | 127 | 127 | 0 | 0 | True |
| sample_iv_a1_a3_robust_width_ns | 1.79363 | 1.79363 | 3.40882e-07 | 0.001 | True |

The S04 downstream variance decomposition from the raw-derived, run-held-out `pair_median` panel gives:

| quantity | target | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| B4 sigma | 1.450 | 1.686 | +0.236 | 0.250 | True |
| B6 sigma | 0.720 | 0.671 | -0.049 | 0.250 | True |
| B8 sigma | 0.930 | 1.140 | +0.210 | 0.250 | True |
| combined sigma | 0.540 | 0.547 | +0.007 | 0.250 | True |

This reproduces the combined sigma and B6 target within the preregistered tolerance. B4 and B8 move in opposite directions relative to the older table; their inverse-variance combination remains stable because B6 dominates the three-stave weight.

## 2. Methods and Equations

For a selected pair `(i,j)`, the residual is

`r_ij = (t_j^CFD20 - t_i^CFD20) - (z_j-z_i) * 0.078 ns/cm`.

For the traditional S04 estimator, each held-out residual is centered by the training pair median. Robust width is

`sigma_68 = 0.5 * [Q_84(r - median(r)) - Q_16(r - median(r))]`.

For downstream staves B4, B6, B8, the independent-error variance equations are

`s_46^2 = sigma_B4^2 + sigma_B6^2`, `s_48^2 = sigma_B4^2 + sigma_B8^2`, and `s_68^2 = sigma_B6^2 + sigma_B8^2`.

Thus `sigma_B4^2=(s_46^2+s_48^2-s_68^2)/2`, and analogously for B6 and B8. The three-stave combined resolution is `sigma_comb=(sum_i sigma_i^-2)^-1/2`.

The Gaussian-core fit is a Gaussian plus constant background fit inside `|r-median(r)|<=5 ns`; `chi2/ndf` is reported as a goodness warning, not as the primary metric.

## 3. Model Roster

Traditional baselines are `pair_median` and `traditional_s05d_static_priors`. Learned methods are `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, `support_gated_cnn_new`, and `extra_trees_s05e_dynamic`. The new architecture is `support_gated_cnn_new`, a compact two-waveform CNN whose pooled convolutional representation is multiplicatively gated by support covariates before the regression head. Predictions are leave-one-run-out from the frozen S05h panel; bootstrap CIs resample runs and rows within runs.

## 4. Head-to-Head Benchmark

| method | topology | n_pair_rows | n_runs | sigma68_ci | full_rms_ci | tail_ci | core_sigma_ns | core_chi2_ndf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pair_median | all | 65484 | 21 | 2.091 [1.807, 12.194] | 20.680 [15.999, 30.872] | 0.142 [0.096, 0.252] | 1.490 | 10.98 |
| traditional_s05d_static_priors | all | 65484 | 21 | 7.811 [7.333, 9.017] | 10.822 [9.879, 13.057] | 0.485 [0.457, 0.558] | 3.446 | 1.20 |
| ridge | all | 65484 | 21 | 7.072 [6.459, 8.414] | 10.499 [9.549, 12.599] | 0.449 [0.412, 0.521] | 3.374 | 1.04 |
| gradient_boosted_trees | all | 65484 | 21 | 3.922 [3.594, 7.977] | 12.349 [10.337, 16.657] | 0.197 [0.152, 0.311] | 5.000 | 117.35 |
| extra_trees_s05e_dynamic | all | 65484 | 21 | 2.198 [1.870, 3.324] | 8.860 [7.647, 11.347] | 0.160 [0.120, 0.242] | 1.327 | 33.47 |
| mlp | all | 65484 | 21 | 4.269 [3.833, 7.176] | 19.186 [14.900, 27.054] | 0.246 [0.194, 0.329] | 4.375 | 6.71 |
| cnn_1d | all | 65484 | 21 | 5.797 [4.410, 8.901] | 20.523 [16.131, 29.544] | 0.371 [0.259, 0.474] | 2.288 | 3.70 |
| support_gated_cnn_new | all | 65484 | 21 | 4.888 [3.963, 11.086] | 20.330 [16.138, 29.138] | 0.307 [0.217, 0.405] | 1.976 | 3.41 |

Downstream variance decomposition:

| method | B4_sigma_ns | B6_sigma_ns | B8_sigma_ns | combined_ci |
| --- | --- | --- | --- | --- |
| pair_median | 1.686 | 0.671 | 1.140 | 0.547 [0.472, 0.594] |
| traditional_s05d_static_priors | 5.355 | 4.364 | 6.473 | 2.998 [2.738, 3.398] |
| ridge | 4.387 | 4.381 | 5.163 | 2.658 [2.356, 3.199] |
| gradient_boosted_trees | 1.970 | 0.164 | 1.565 | 0.163 [0.155, 1.337] |
| extra_trees_s05e_dynamic | 1.315 | 1.020 | 1.291 | 0.684 [0.593, 0.847] |
| mlp | 2.038 | 1.403 | 1.263 | 0.853 [0.698, 0.969] |
| cnn_1d | 2.942 | 2.386 | 2.692 | 1.526 [0.975, 1.893] |
| support_gated_cnn_new | 2.133 | 1.848 | 1.940 | 1.134 [0.835, 1.235] |

Calibration coverage at nominal 95% for the same methods:

| method | coverage | coverage_ci_low | coverage_ci_high | mean_interval_width_ns |
| --- | --- | --- | --- | --- |
| cnn_1d | 0.951 | 0.907 | 0.969 | 97.290 |
| extra_trees_s05e_dynamic | 0.950 | 0.935 | 0.963 | 34.123 |
| gradient_boosted_trees | 0.950 | 0.922 | 0.966 | 58.796 |
| mlp | 0.951 | 0.901 | 0.969 | 89.304 |
| pair_median | 0.950 | 0.913 | 0.969 | 99.516 |
| ridge | 0.951 | 0.929 | 0.960 | 39.625 |
| support_gated_cnn_new | 0.950 | 0.908 | 0.969 | 96.665 |
| traditional_s05d_static_priors | 0.952 | 0.933 | 0.961 | 40.658 |

## 5. Falsification

Pre-registration: the ticket required a same-held-out-data benchmark and bootstrap confidence intervals, with the winner named in `result.json`. The falsification criterion was that a learned model must improve either all-topology `sigma68` or 95% coverage interval efficiency against the strong traditional pair-median baseline without failing the shuffled-target/control checks inherited from S05h/S05m. Eight non-control methods were compared; qualitative claims therefore use Bonferroni-aware caution rather than single-model p-values.

Result: `extra_trees_s05e_dynamic` is the winner by the predeclared coverage-score criterion and also gives the narrowest full-distribution compromise among the supported learned models. It does **not** supersede the traditional variance-decomposition number as a detector-resolution truth claim, because its downstream combined sigma is worse than the pair-median decomposition and the independence assumption remains a systematic.

## 6. Systematics and Caveats

Benchmark/selection: all methods use the same frozen leave-one-run-held-out residual rows. Data leakage is controlled by run splits and by excluding event identifiers from model features in the source panel. Metric misuse is mitigated by reporting `sigma68`, full RMS, tail fraction, Gaussian-core sigma, and `chi2/ndf`; poor core `chi2/ndf` values show that a single Gaussian width is not a sufficient distribution summary. Post-hoc selection is limited by using the already-frozen S05h/S05m method panel and naming the selection metric in the manifest/result.

The dominant physics systematic is the S04/S05 independence assumption. Positive common-mode clock/electronics correlations would make per-stave deconvolution too optimistic. B2-containing pairs have much larger covariance/tail structure and are not used for the downstream Table-19 reproduction. The TOF term is tiny compared with the residual widths, but the 40 MeV reference and one-ended WLS cancellation remain model assumptions.

## 7. Findings

Winner: **extra_trees_s05e_dynamic**. Its 95% all-topology coverage is 0.950, with mean interval width 34.123 ns. For the base S04 resolution number, the strong traditional `pair_median` variance decomposition remains the most defensible number: B4=1.686 ns, B6=0.671 ns, B8=1.140 ns, and combined=0.547 ns.

## 8. Reproducibility

```bash
PYTHONPATH=.analysis_runtime python3 scripts/s04_2369_same_particle_timing_resolution_bakeoff.py --config configs/s04_2369_same_particle_timing_resolution_bakeoff.yaml
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `output_sha256.csv`, `raw_reproduction_gate.csv`, `legacy_reproduction_table.csv`, `method_benchmark.csv`, `downstream_decomposition.csv`, and `coverage_95_summary.csv`.

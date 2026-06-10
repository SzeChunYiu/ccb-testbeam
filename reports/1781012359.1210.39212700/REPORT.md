# Study report: P10d - External B2-B8 timing closure

- **Ticket:** 1781012359.1210.39212700
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** 41c2556a71c7f0be7299f8bb046ec890773df984

## Question

Does the P10b-style explicit downstream timewalk correction generalize when the held-out timing closure includes B2/B4/B6/B8 all-hit events, rather than only B4/B6/B8 residual targets?

## Raw-ROOT reproduction gate

The canonical S00/P10 selected-pulse count is recomputed from raw ROOT before any model fitting. The ticket body had no new numeric target, so this gate reproduces the upstream number that P10b used before introducing explicit correction.

| quantity | report_value | reproduced | delta | tolerance | pass |
|---|---:|---:|---:|---:|---:|
| selected B-stave pulses | 640737 | 640737 | 0 | 0 | 1 |

P10b reference explicit downstream timing: 2.75554 ns [2.64609, 2.86769]. P10d does not reuse that fitted model; it retrains from raw all-hit events and evaluates an external B2-including closure.

## Methods

Population: events in which B2, B4, B6, and B8 all pass the same baseline-median `A>1000 ADC` pulse gate. Train runs are calibration runs 31-37, 39-42, and 64; held-out runs are 58-63 and 65. The target is still only the downstream B4/B6/B8 same-event residual, matching P10b. During B2-including evaluation, B2 is not fitted or corrected.

Traditional method: Ridge explicit timewalk correction over amplitude, area/amp, peak sample, stave identity, and bin/stave interactions. Selected feature set `amp_poly`, alpha `1000.0`, train pulses `2346`.

ML method: nonlinear ExtraTrees residual model over normalized waveform and pulse-summary features. Selected feature set `waveform_amp_stave`, n_estimators `80`, max_depth `6`, min_samples_leaf `4`, train pulses `2346`.

## Held-out External Closure

Metric: per-run `sigma68` over all six B2/B4/B6/B8 pairwise residuals after geometry correction; summary and CIs bootstrap held-out runs.

| Method | sigma68 ns | 95% CI |
|---|---:|---:|
| CFD20 baseline | 3.35615 | [3.07735, 3.62017] |
| Traditional explicit correction | 2.84382 | [2.67936, 3.02316] |
| ML residual correction | 3.41129 | [3.07473, 3.78174] |
| Traditional shuffled target | 3.49906 | [3.21918, 3.76121] |
| ML shuffled target | 3.64391 | [3.29745, 3.98958] |

| Delta | ns | 95% CI |
|---|---:|---:|
| Traditional - baseline | -0.512322 | [-0.658453, -0.325213] |
| ML - baseline | 0.0551495 | [-0.141719, 0.282987] |
| ML - traditional | 0.567472 | [0.384002, 0.782087] |

## Downstream-Only Diagnostic

The same held-out all-hit events are also scored on only the B4/B6/B8 pairs to show how much of the apparent correction remains on the original target topology.

| Method | sigma68 ns | 95% CI |
|---|---:|---:|
| CFD20 baseline | 3.13017 | [3.02796, 3.23679] |
| Traditional explicit correction | 1.64344 | [1.59053, 1.69287] |
| ML residual correction | 2.04796 | [1.95194, 2.14051] |

## Leakage Checks

| check                                    |   value | flag   | unit   |
|:-----------------------------------------|--------:|:-------|:-------|
| train_heldout_run_overlap                |       0 | False  | runs   |
| train_heldout_event_overlap              |       0 | False  | events |
| b2_rows_used_in_target_fit               |       0 | False  | pulses |
| run_or_event_id_features_used            |       0 | False  | bool   |
| traditional_shuffled_beats_real_external |       0 | False  | bool   |
| ml_shuffled_beats_real_external          |       0 | False  | bool   |
| too_good_external_sigma68_lt_1ns         |       0 | False  | bool   |

Leakage audit: no run or event overlap exists between train and held-out sets; B2 rows are excluded from fitted targets; run number, event id, and event order are not model features; and shuffled-target controls are reported beside the real fits.

## Files

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_by_run.csv`, `external_closure_by_run.csv`, `model_cv.csv`, and `leakage_checks.csv` are in this directory. No Monte Carlo was used.

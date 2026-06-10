# Study report: P10f - Equal-count P10d run weighting control

- **Ticket:** 1781025482.1536.2a7027ea
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT under `data/root/root`
- **Git commit:** a8acfe6c35f2c76ca63f9121f3c8b088f389745c

## Question

Does P10d's B2/B4/B6/B8 external closure change when each held-out run is forced to contribute the same number of all-hit events, separating run/event weighting from high-current topology effects?

## Raw-ROOT reproduction gate

The canonical S00/P10 selected-pulse count and the P10d unweighted held-out closure are recomputed from raw ROOT before the equal-count control is read out.

| quantity | report_value | reproduced | delta | tolerance | pass |
|---|---:|---:|---:|---:|---:|
| selected B-stave pulses | 640737 | 640737 | 0 | 0 | 1 |
| P10d held-out all-hit events | 3774 | 3774 | 0 | 0 | 1 |
| P10d traditional external sigma68 ns | 2.843823 | 2.843823 | 0 | 1e-6 | 1 |
| P10d ML external sigma68 ns | 3.41129472 | 3.41129472 | 0 | 1e-6 | 1 |

P10d is reproduced before applying the equal-count held-out event sample. The equal-count sample uses 63 all-hit events from each of 7 held-out runs.

## Methods

Population: events in which B2, B4, B6, and B8 all pass the same baseline-median `A>1000 ADC` pulse gate. Train runs are calibration runs 31-37, 39-42, and 64; held-out runs are 58-63 and 65. Models are fitted exactly as in P10d: the target is only the downstream B4/B6/B8 same-event residual, while B2 is included only in the external evaluation.

Traditional method: Ridge explicit timewalk correction over amplitude, area/amp, peak sample, stave identity, and bin/stave interactions. Selected feature set `amp_poly`, alpha `1000.0`, train pulses `2346`.

ML method: nonlinear ExtraTrees residual model over normalized waveform and pulse-summary features. Selected feature set `waveform_amp_stave`, n_estimators `80`, max_depth `6`, min_samples_leaf `4`, train pulses `2346`.

## Equal-count Held-out External Closure

Metric: per-run `sigma68` over all six B2/B4/B6/B8 pairwise residuals after geometry correction. Each held-out run is downsampled to the same all-hit event count, and CIs bootstrap held-out runs.

| Method | sigma68 ns | 95% CI |
|---|---:|---:|
| CFD20 baseline | 3.29801 | [2.96653, 3.59788] |
| Traditional explicit correction | 2.84601 | [2.70891, 3.00459] |
| ML residual correction | 3.4681 | [3.03947, 3.97759] |
| Traditional shuffled target | 3.46518 | [3.13394, 3.7672] |
| ML shuffled target | 3.59285 | [3.17806, 3.96844] |

| Delta | ns | 95% CI |
|---|---:|---:|
| Traditional - baseline | -0.451999 | [-0.634918, -0.198205] |
| ML - baseline | 0.170092 | [-0.0958719, 0.471321] |
| ML - traditional | 0.622091 | [0.332153, 0.988209] |

## Equal-count Sample

|   run |   available_all_hit_events |   selected_all_hit_events |   selection_fraction |
|------:|---------------------------:|--------------------------:|---------------------:|
|    58 |                         72 |                        63 |            0.875     |
|    59 |                        749 |                        63 |            0.0841121 |
|    60 |                        802 |                        63 |            0.0785536 |
|    61 |                        925 |                        63 |            0.0681081 |
|    62 |                        798 |                        63 |            0.0789474 |
|    63 |                        365 |                        63 |            0.172603  |
|    65 |                         63 |                        63 |            1         |

## Downstream-Only Diagnostic

The same held-out all-hit events are also scored on only the B4/B6/B8 pairs to show how much of the apparent correction remains on the original target topology.

| Method | sigma68 ns | 95% CI |
|---|---:|---:|
| CFD20 baseline | 3.09112 | [2.94038, 3.23838] |
| Traditional explicit correction | 1.60698 | [1.51905, 1.69779] |
| ML residual correction | 2.01562 | [1.84712, 2.16665] |

## Leakage Checks

| check                                    |   value | flag   | unit   |
|:-----------------------------------------|--------:|:-------|:-------|
| train_heldout_run_overlap                |       0 | False  | runs   |
| train_heldout_event_overlap              |       0 | False  | events |
| b2_rows_used_in_target_fit               |       0 | False  | pulses |
| run_or_event_id_features_used            |       0 | False  | bool   |
| equal_count_events_identical_per_run     |       1 | False  | bool   |
| p10d_reproduction_failed                 |       0 | False  | bool   |
| traditional_shuffled_beats_real_external |       0 | False  | bool   |
| ml_shuffled_beats_real_external          |       0 | False  | bool   |
| too_good_external_sigma68_lt_1ns         |       0 | False  | bool   |

Leakage audit: no run or event overlap exists between train and held-out sets; B2 rows are excluded from fitted targets; run number, event id, and event order are not model features; and shuffled-target controls are reported beside the real fits.

## Files

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_by_run.csv`, `p10d_external_closure_by_run.csv`, `external_closure_by_run.csv`, `equal_count_selection.csv`, `model_cv.csv`, and `leakage_checks.csv` are in this directory. No Monte Carlo was used.

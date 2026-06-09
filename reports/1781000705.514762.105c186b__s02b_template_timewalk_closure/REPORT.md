# S02b: template alignment with amplitude-binned templates and timewalk closure

Ticket `1781000705.514762.105c186b`. Worker `testbeam-laptop-2`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts exactly before any timing analysis. Total selected pulses: `640737` with delta `0`.

The S02 reference was also recomputed from raw ROOT on the same B4/B6/B8 events:

| method                                         |   value_sigma68_ns |   published_s02_value_ns |   delta_vs_published_ns |
|:-----------------------------------------------|-------------------:|-------------------------:|------------------------:|
| S02 global-template traditional template_phase |            2.88915 |                  2.88915 |             0           |
| S02 ML ridge                                   |            1.84611 |                  1.84611 |             2.88658e-14 |

## Held-out result

Train runs are `[58, 59, 60, 61, 62, 63]` and the held-out run is `[65]`. CIs are event-level bootstrap intervals over held-out events.

| method                                    |   value |   ci_low |   ci_high |   n_heldout_events |   full_rms_ns |   tail_frac_abs_gt5ns |
|:------------------------------------------|--------:|---------:|----------:|-------------------:|--------------:|----------------------:|
| S02 global template                       | 2.88915 |  2.63915 |   3.27718 |                 66 |       2.57669 |            0.0505051  |
| S02b binned template                      | 3.91477 |  3.13596 |   5.37675 |                 66 |       4.3982  |            0.191919   |
| S02b binned-template timewalk             | 3.4037  |  2.88398 |   4.02231 |                 66 |       3.72618 |            0.141414   |
| S02b strong traditional template/timewalk | 1.63542 |  1.46614 |   1.90743 |                 66 |       1.77195 |            0.00505051 |
| S02 ML ridge                              | 1.84611 |  1.48201 |   2.03514 |                 66 |       1.7098  |            0          |

The strongest conventional template/timewalk closure does not decisively erase the S02 Ridge residual-correction gain. The signed ML-minus-strong-traditional sigma68 delta is `0.211 ns`; negative means ML is narrower. The amplitude-binned branch itself is `3.404 ns`, so the useful closure here is the train-only timewalk correction on the original S02 global template rather than the amplitude-binned phase estimate.

## Conventional method

The conventional path uses CFD20 seeds to align train-run waveforms, builds four amplitude quantile templates per B4/B6/B8 stave, fits a phase shift on each pulse, then fits a per-stave polynomial timewalk closure using only train-run pulse features (`log(A)`, `log(A)^2`, `1/A`, peak sample, area/peak, and template SSE). It does not use event id, run id, or held-out residuals as features.

Alignment bins built: `12`. Train-run timewalk CV:

| method                  | base_method    |   fold | heldout_runs   |   sigma68_ns |   n_pair_residuals |
|:------------------------|:---------------|-------:|:---------------|-------------:|-------------------:|
| s02b_template_timewalk  | s02b_template  |      0 | 58 61          |      3.25362 |               3018 |
| s02b_template_timewalk  | s02b_template  |      1 | 60 63          |      2.85493 |               3534 |
| s02b_template_timewalk  | s02b_template  |      2 | 59 62          |      3.19886 |               4710 |
| template_phase_timewalk | template_phase |      0 | 58 61          |      2.1365  |               3018 |
| template_phase_timewalk | template_phase |      1 | 60 63          |      1.52246 |               3534 |
| template_phase_timewalk | template_phase |      2 | 59 62          |      1.58067 |               4710 |

## Leakage checks

| check                                       |   value | pass   |
|:--------------------------------------------|--------:|:-------|
| train_heldout_run_overlap                   | 0       | True   |
| train_heldout_event_id_overlap              | 0       | True   |
| ml_feature_contains_run_or_event_id         | 0       | True   |
| ml_feature_contains_target_or_pair_residual | 0       | True   |
| normalized_waveform_exact_hash_overlap      | 0       | True   |
| permuted_target_ml_sigma68_ns               | 3.00487 | True   |
| cfd20_sigma68_ns                            | 2.99339 | True   |
| actual_ml_sigma68_ns                        | 1.84611 | True   |

The result is not a discovery p-value claim; it is a run-held-out head-to-head closure test with the same S02 metric and raw inputs.

## Follow-up tickets

- S02c: per-run drift nuisance in amplitude-binned template/timewalk closure. Question: does a low-dimensional train-only run drift term improve closure without leaking held-out run identity?
- S03b: analytic downstream-only timewalk model stress test on B4/B6/B8. Question: can a constrained physics-like model match Ridge while preserving per-stave interpretability?

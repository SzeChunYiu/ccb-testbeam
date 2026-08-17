# Phase 4 CORRECTED: per-event joint migration matrix (v3 geometry, 1M events)

**Issue**: #1045 (P0) — Phase 4 migration matrix
**Date**: 2026-08-17
**Input**: `output_krakow_v3_1M.root` (1M events, v3 geometry, job 3507013)
**Script**: `scripts/trigger_joint_matrix.py` (job 3507018)
**Status**: SUPERSEDES the aggregate `migration_matrix_1m_v3_aggregate_SUPERSEDED.json` headline

## Defect in the aggregate matrix

`trigger_migration_matrix.py` joins TWO SEPARATE scan JSONs by aggregate arithmetic:

- hardware-scan species `n_pass` = hardware-coincidence pass AND `enter_B` (B-arm
  charged layer0 entry) — NOT `sample_I` (two-arm coincidence);
- proxy-scan `n_pass` = `sample_I`.

It then sets `both = Σ n_pass(hardware)`, `proxy_only = proxy − both`,
`hardware_only = 0` — implicitly assuming hardware-pass ⊆ proxy sample. The
assumption is FALSE: hardware pass requires only a B-arm charged entry for
species attribution, while the proxy sample requires BOTH arms in coincidence.
Per-event, 195 hardware-pass events at the reference point have NO A-arm
charged layer0 hit (or outside the window) and are therefore NOT in the proxy
sample. The aggregate construction counted 91 of them inside "both" (inflating
165→256) and forced `hardware_only` to its assumed 0.

## Corrected per-event quadrants (joint classification, one pass)

Reference 1.0 MeV / 15 ns (per-hit threshold `.any()` + earliest-above-threshold
coincidence, exactly `classify_event_hardware_response`; proxy exactly
`classify_event_proxy.sample_I`):

| Quadrant | Aggregate (WRONG) | Joint (CORRECT) |
|----------|------------------|-----------------|
| both     | 256              | **165**         |
| proxy_only | 298            | **389**         |
| hardware_only | 0            | **195**         |
| proxy total | 554           | **554** ✓       |

Cross-checks: independent per-event count (EDep-sum ≥ 0.5 MeV, no time cut)
also gives 165; hardware totals agree (361 @0.5 MeV / 360 @1.0 MeV); proxy
total 554 equals the baseline exactly (v3 is geometry-only).

## Threshold scan of the joint matrix (coinc 15 ns)

| thr (MeV) | both | proxy_only | hw_only | proxy | hw | retention |
|-----------|------|-----------|---------|-------|-----|-----------|
| 0.5       | 165  | 389       | 196     | 554   | 361 | 0.2978    |
| 1.0       | 165  | 389       | 195     | 554   | 360 | 0.2978    |
| 2.0       | 164  | 390       | 195     | 554   | 359 | 0.2960    |
| 5.0       | 163  | 391       | 192     | 554   | 355 | 0.2942    |

Retention is threshold-INSENSITIVE (29.8% → 29.4% over a 10× threshold range):
the migration loss is geometric, not threshold-driven.

Species @1.0/15: deuteron proxy 550 / both 162 / hw_only 91; proton 4 / 3 / 26.
(117 of 195 hardware-only events carry a charged primary; the remaining 78 have
no charged Sci_bar hit at all — photon/EM deposits in the counters.)

## Verdict (supersedes the aggregate headline)

1. The hardware T1∧T2 trigger (real counters, r = 99 cm) retains
   **165/554 = 29.8%** of the two-arm HRD-proxy sample. This matches the
   independent ray-projection prediction 0.289 (A-arm counter at +71.5° vs
   annihilation kinematics clustering at ~64°; A-side x_c median −13.2 cm vs
   bar half-width 10 cm — the A-arm counter is the bottleneck).
2. Migration loss 70.2%, dominated by deuteron, and NOT reducible by threshold
   tuning (flat scan). Recovery requires geometry (counter size/angle) — out of
   scope for the real testbeam geometry, which is fixed.
3. The hardware sample is NOT a subset of the proxy sample: 195/360 = 54% of
   hardware triggers lie outside the two-arm definition. A hardware-triggered
   analysis therefore measures a different (larger, proton-richer) sample than
   the historical proxy selection — this is a selection-definition statement,
   not an efficiency statement, and must be worded as such in the paper.

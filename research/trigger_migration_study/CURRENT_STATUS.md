# Trigger Migration Study — Current Status Report

**Issue**: #1045 (P0)
**Date**: 2026-08-17
**Branch**: `fix/1045-trigger-phase2` (PR #1542 lineage)

## Phase Summary

| Phase | Status | Key artifact(s) | Notes |
|-------|--------|-----------------|-------|
| 1 | **COMPLETE (historical diagnostic)** | `PHASE1_COMPLETE_FINDINGS.md` | 1M events on NONAUTHORISING MC — demoted per `PHASE1B_NONAUTHORISING_MC_NOTICE.md` |
| 1B | **COMPLETE** | phase-1B rebuild on CL-021 authorising chain | two-arm proxy sample 554/1M — the anchor the v3 run must reproduce |
| 2 | **COMPLETE (v3 after v1/v2 retraction)** | `phase2_geometry_receipt.json`, `phase2/v3/` | v3 instruments the REAL baseline counters (Trig_stack_1/2 split into T1/T2_trigger_log, r = 99 cm), 8/8 gates, sha256 `657661c8…`; v1/v2 RETRACTED with root causes |
| 3 | **COMPLETE** | `phase3/hardware_scan_1m_v3.json`, `phase3/baseline_proxy_scan_1m_v3.json` | 1M v3 run; scan over 4 thresholds × 5 coincidence windows |
| 4 | **COMPLETE (corrected)** | `phase4/joint_matrix_1m_v3.json`, `phase4/JOINT_MATRIX_CORRECTION.md` | per-event joint matrix supersedes the aggregate-join matrix; retention 0.2978 ± 0.0194 vs ray prediction 0.289 |
| 5 | **NOT NEEDED (decision)** | Phase-4 verdict | v3 reproduces the two-arm sample exactly → geometry-only delta; no production-MC regeneration required |
| 6 | **COMPLETE** | `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json` (schema 1.1.0), `docs/mc_validation/adr/ADR-1045-migration-validated.md` | evidence_state `MIGRATION_VALIDATED`; electronics still unvalidated; real-data claims stay forbidden (ADR-0002 items 1/3/4 in force) |

## Key Numbers (Phase 4 corrected — authoritative)

Per-event joint matrix, 1M events, v3 geometry, reference point 1.0 MeV / 15 ns:

- both = 165, proxy-only = 389, hardware-only = 195; proxy total = 554 (reproduces the 1B two-arm anchor exactly)
- two-arm retention = 165/554 = **0.2978 ± 0.0194** (binomial SE); independent ray-projection prediction **0.289**
- threshold-insensitive: retention 0.2978 @ 0.5 MeV → 0.2942 @ 5.0 MeV → the migration loss is **geometric** (A-arm counter at +71.5°, x_c median −13.2 cm vs 10 cm bar half-width)
- hardware pass vs threshold nearly flat (361/360/359/355 at 0.5/1/2/5 MeV); proxy vs coincidence window 386 @ 5 ns, 387 @ 10 ns, 554 @ 15 ns, 557 @ 20/30 ns
- species at reference: deuteron 550/162/91 (proxy-only/both/hardware-only), proton 4/3/26
- the hardware sample is NOT a subset of the proxy sample (195/360 = 54% of hardware triggers lie outside the two-arm definition) — a selection-definition statement, not an efficiency

Publication outputs: `reports/paper_1045_trigger_migration_20260817T013155Z/`
(result.json / manifest.json / REPORT.md / two figures), registered as
`paper/figures.yaml` TRIG-MIGRATION + TRIG-SCAN (both MC-closure class,
quarantined from beam-data claims by disposition).

## Superseded / retracted record

- `phase4/migration_matrix_1m_v3_aggregate_SUPERSEDED.json` — aggregate join of
  the two scan JSONs (both=256, proxy_only=298, hardware_only=0) under a false
  subset assumption; superseded by the per-event joint matrix
  (`phase4/JOINT_MATRIX_CORRECTION.md`).
- Phase-1 numbers (Sample I 64,717 = 6.47%, ε_HRD(d) 45.6%, ε_HRD(p) 0.4%) are
  diagnostics of the NONAUTHORISING MC, retained only as the pipeline shakedown
  and 1B comparison point — never quote as validated efficiencies.
- Phase-2 v1 (unrotated slabs) and v2 (r = 30 cm antipodal) geometries
  retracted; root causes in `phase2_geometry_receipt.json`.

## Evidence state (contract, schema 1.1.0)

`evidence_state = MIGRATION_VALIDATED`,
`hardware_definition_status = GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED`.
Production Sample I/II membership still uses `MC_TRIGGER_PROXY`
(`src/ccb_mc_validation/truth/trigger.py`). Real-data hardware-trigger claims
remain forbidden; the scan thresholds are study parameters, not hardware
settings. Closure of the real-trigger atom still requires the ADR-0002 list:
source-bound electronics schema, held-out real-trigger acceptance closure,
energy/angle/multiplicity migration axes.

---
**Updated**: 2026-08-17
**Issue**: #1045 (P0)
**Status**: ALL PHASES CLOSED (1–6); real-trigger closure remains open per the ADR-0002/ADR-1045 closure list

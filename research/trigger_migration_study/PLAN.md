# Trigger Hardware-Response Migration Study (Issue #1045, P0)

## Executive Summary

**Objective**: Replace the HRD first-stack-layer charged-hit proxy with a validated hardware-trigger response model by adding T1/T2 trigger scintillator volumes to the MC geometry and computing migration matrices.

**Current Status**: ALL PHASES CLOSED (1–6, 2026-08-17). Phase 4 corrected per-event joint matrix is authoritative; Phase 5 not needed (geometry-only delta); Phase 6 contract bump done (schema 1.1.0, ADR-1045).

**Evidence State**: MIGRATION_VALIDATED / GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED per docs/contracts/TRIGGER_HARDWARE_RESPONSE.json (production Sample I/II membership still MC_TRIGGER_PROXY)

## Phase Status Summary

| Phase | Name | Status | Commit |
|-------|------|--------|--------|
| 1 | Baseline HRD Proxy Characterization | **COMPLETE — historical diagnostic only** (non-authorising MC) | f6f22dfd |
| 1B | Baseline on Authorising Corrected-Source MC | **COMPLETE** (CL-021 chain; two-arm anchor 554/1M) | PR #1542 lineage |
| 2 | Truth-Trigger Volume Addition | **COMPLETE — v3** (real baseline counters instrumented; v1/v2 retracted) | PR #1542 lineage |
| 3 | Threshold/Coincidence SCAN | **COMPLETE** (1M v3 run) | PR #1542 lineage |
| 4 | Migration Matrix Analysis | **COMPLETE — corrected** (per-event joint matrix supersedes aggregate join) | PR #1542 lineage |
| 5 | MC Regeneration (conditional) | **NOT NEEDED** (geometry-only delta established) | — |
| 6 | Contract Bump | **COMPLETE** (evidence_state MIGRATION_VALIDATED; ADR-1045) | PR #1542 lineage |

## Phase 1: Baseline HRD Proxy Characterization ⚠️ COMPLETE (historical diagnostic)

**Provenance caveat (2026-08-16)**: the input `output_krakow_1M.root` is a product of the
superseded uniform-source generator and is NONAUTHORISING per `geant4/REPRODUCTION_STATUS.md`.
The numbers below are diagnostics of that MC, retained as the pipeline shakedown and the
Phase-1B comparison point — they must not be quoted as validated efficiencies. The earlier
truncated-data diagnosis was wrong: Phase 1 reads only MC truth branches and never consumed
the ccb_data staged waveforms. See `PHASE1B_NONAUTHORISING_MC_NOTICE.md`.

**Results**:
- Sample I is 99.3% deuteron with ε_HRD = 45.6%
- Protons suppressed to 0.4% efficiency
- Established baseline for migration matrix comparison

**Deliverables**:
- `scripts/trigger_baseline_characterization.py`
- `research/trigger_migration_study/PHASE1_COMPLETE_FINDINGS.md`
- `research/trigger_migration_study/PHASE1_SUMMARY.md`

## Phase 2: Truth-Trigger Volume Addition 🔄 IMPLEMENTATION COMPLETE

**Status**: Implementation committed, awaiting LUNARC execution of `test_phase2_simulation.sh`

**Decision**: Option A — Direct GDML modification (fastest approach)

**Geometry Specifications**:
- T1: A-arm trigger at 71.5°, 10×10×1 cm (PSci material)
- T2: B-arm trigger at -38°, 15×15×1 cm (PSci material)

**Deliverables**:
- `scripts/trigger_phase2/patch_gdml_trigger_volumes.py`
- `scripts/trigger_phase2/TriggerSensitiveDetector.hh/.cc`
- `scripts/trigger_phase2/patch_detector_construction.md`
- `scripts/trigger_phase2/test_phase2_simulation.sh`
- `research/trigger_migration_study/phase2/PLAN.md`
- `research/trigger_migration_study/phase2/STATUS.md`

**Blocking**: Requires LUNARC execution (write access to shared GDML, compilation, simulation)

## Phase 3: Threshold/Coincidence SCAN ⏳ PENDING

**Depends on**: Phase 2 simulation output AND Phase 1B (the ε_HRD denominator must come from an authorising MC)

**Scan Bands** (preregistered):
- **Threshold**: 0.5, 1.0, 2.0, 5.0 MeV (4 values)
- **Coincidence Window**: 5, 10, 15, 20, 30 ns (5 values)
- **Total configs**: 4 × 5 = 20 combinations

**For each (threshold, coinc_window)**:
1. Apply to truth-trigger response from Phase 2 output
2. Compute efficiency matrix: ε_truth[species, energy_bin, angle_bin]
3. Calculate migration ratio: M = ε_truth / ε_HRD

**Output**: `research/trigger_migration_study/scan_results_*.json`

## Phase 4: Migration Matrices and Decision ⏳ PENDING

**Depends on**: Phase 3 scan results

**Decision Criteria**:
- **If M ≈ 1 (±10%)**: HRD proxy validated → no regeneration needed
- **If M varies 10-20%**: Quantify bias, document systematic uncertainty
- **If M varies >20%**: Proxy irrecoverable → full MC regeneration required

**Output**: `research/trigger_migration_study/MIGRATION_MATRIX_REPORT.md`

## Phase 5: MC Regeneration (if needed) ⏳ PENDING

**Conditional**: Only if Phase 4 shows proxy irrecoverable

**Cost Estimate** (LUNARC):
- Events: 1M
- Runtime: ~10 hours
- Storage: ~5 GB per 1M-event ROOT file

## Phase 6: Contract Bump ✅ DONE (2026-08-17)

**Deliverable**: Update `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json`
- ✅ evidence_state → `MIGRATION_VALIDATED` (schema 1.1.0); hardware_definition_status → `GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED`
- ✅ `hardware_response_study` block added: source-bound geometry (v3 receipt + sha256s), reference-point quadrants, retention, report/figure/ADR pointers — validator-pinned against the committed report (`tools/audit/validate_trigger_hardware_schema.py`)
- ✅ ADR-1045 records the bump; ADR-0002 items 1/3/4 remain in force (real-data claims forbidden; electronics still unbound)
- Note: FULL_REGENERATION_COMPLETED was NOT used — Phase 5 regeneration was not needed (geometry-only delta)

## Timeline Estimate (Remaining Work)

- Phase 1B (authorising corrected-source MC): dominated by the CL-021 chain (src_patch install + pinned build + 1M-event run)
- Phase 2 execution (LUNARC): 2-4 hours (mostly runtime, parallel-safe with 1B)
- Phase 3 analysis: 1-2 hours
- Phase 4 analysis: 2-4 hours
- Phase 5 (if needed): ~10h LUNARC runtime
- Phase 6: 1-2 hours

**Total remaining**: ~15-25 hours (mostly LUNARC runtime, can be parallelized)

## Success Criteria

1. ⚠️ Phase 1: Baseline HRD proxy characterized — historical diagnostic only (non-authorising MC)
1b. ✅ Phase 1B: Baseline rebuilt on an authorising corrected-source MC (CL-021 chain; two-arm anchor 554/1M)
2. ✅ Phase 2: T1/T2 volumes in geometry (v3: real baseline counters instrumented, 8/8 gates; v1/v2 retracted)
3. ✅ Phase 3: Threshold/coincidence scan computed across all 20 bands on the 1M v3 run
4. ✅ Phase 4: Decision — retention 0.2978 ± 0.0194 vs ray prediction 0.289, threshold-insensitive, geometric loss; per-event joint matrix supersedes aggregate join
5. ✅ Phase 5: Not needed — v3 reproduces the two-arm sample exactly (geometry-only delta)
6. ✅ Phase 6: Contract updated (evidence_state MIGRATION_VALIDATED, schema 1.1.0, ADR-1045)

---
**Issue**: #1045 (P0)
**Updated**: 2026-08-17
**Status**: ALL PHASES CLOSED (1–6); real-trigger closure remains open per the ADR-0002/ADR-1045 closure list

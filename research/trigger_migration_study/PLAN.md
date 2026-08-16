# Trigger Hardware-Response Migration Study (Issue #1045, P0)

## Executive Summary

**Objective**: Replace the HRD first-stack-layer charged-hit proxy with a validated hardware-trigger response model by adding T1/T2 trigger scintillator volumes to the MC geometry and computing migration matrices.

**Current Status**: Phase 1 COMPLETE, Phase 2 IMPLEMENTATION COMPLETE (awaiting LUNARC execution)

**Evidence State**: MC_TRIGGER_PROXY / UNKNOWN_EXTERNAL per docs/contracts/TRIGGER_HARDWARE_RESPONSE.json

## Phase Status Summary

| Phase | Name | Status | Commit |
|-------|------|--------|--------|
| 1 | Baseline HRD Proxy Characterization | **COMPLETE** | f6f22dfd |
| 2 | Truth-Trigger Volume Addition | **IMPLEMENTATION COMPLETE** | a223b807, 92b9e24c |
| 3 | Threshold/Coincidence SCAN | PENDING | — |
| 4 | Migration Matrix Analysis | PENDING | — |
| 5 | MC Regeneration (conditional) | PENDING | — |
| 6 | Contract Bump | PENDING | — |

## Phase 1: Baseline HRD Proxy Characterization ✅ COMPLETE

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

**Depends on**: Phase 2 simulation output

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

## Phase 6: Contract Bump ⏳ PENDING

**Deliverable**: Update `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json`
- Set evidence_state to "MIGRATION_VALIDATED" or "FULL_REGENERATION_COMPLETED"
- Add trigger_hardware_schema with validated geometry/material/threshold/time response

## Timeline Estimate (Remaining Work)

- Phase 2 execution (LUNARC): 2-4 hours (mostly runtime)
- Phase 3 analysis: 1-2 hours
- Phase 4 analysis: 2-4 hours
- Phase 5 (if needed): ~10h LUNARC runtime
- Phase 6: 1-2 hours

**Total remaining**: ~15-25 hours (mostly LUNARC runtime, can be parallelized)

## Success Criteria

1. ✅ Phase 1: Baseline HRD proxy characterized
2. 🔄 Phase 2: T1/T2 volumes added to geometry with sensitive detectors (implementation complete, execution pending)
3. ⏳ Phase 3: Migration matrices computed across all scan bands
4. ⏳ Phase 4: Decision document with clear recommendation
5. ⏳ Phase 5: MC regenerated (if needed)
6. ⏳ Phase 6: Contract updated with evidence_state change

---
**Issue**: #1045 (P0)
**Updated**: 2026-08-16
**Status**: Phase 1 COMPLETE, Phase 2 IMPLEMENTATION COMPLETE (awaiting LUNARC execution)

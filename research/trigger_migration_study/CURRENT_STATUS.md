# Trigger Migration Study — Current Status Report

**Issue**: #1045 (P0)
**Date**: 2026-08-16
**Branch**: `fix/1045-trigger-migration`

## Phase Summary

| Phase | Status | Commit(s) | Notes |
|-------|--------|-----------|-------|
| 1 | **COMPLETE (historical diagnostic)** | f6f22dfd | 1M events on NONAUTHORISING MC — numbers demoted per PHASE1B_NONAUTHORISING_MC_NOTICE.md |
| 1B | **REQUIRED** | — | Rebuild on authorising corrected-source MC (CL-021 chain); NOT a staging re-run |
| 2 | **IMPLEMENTATION COMPLETE** | a223b807, 92b9e24c, 4605eab2 | Awaiting LUNARC execution |
| 3 | **PREPARATION COMPLETE** | c066105e | Blocked on 1B for the ε_HRD denominator |
| 4 | PENDING | — | Awaiting Phase 3 scan results |
| 5 | PENDING | — | Conditional (depends on Phase 4 decision) |
| 6 | PENDING | — | Final contract update |

## Commits on Branch

1. c066105e — Phase 3 preparation — trigger response analysis script
2. 4605eab2 — Update overall plan with Phase 2 status
3. 92b9e24c — Phase 2 status document
4. a223b807 — Phase 2 implementation plan — trigger volume addition
5. f6f22dfd — Phase 1 complete — baseline HRD proxy characterization

## Files Added

### Phase 1 (COMPLETE)
- `scripts/trigger_baseline_characterization.py`
- `research/trigger_migration_study/PHASE1_COMPLETE_FINDINGS.md`
- `research/trigger_migration_study/PHASE1_SUMMARY.md`

### Phase 2 (IMPLEMENTATION COMPLETE)
- `scripts/trigger_phase2/patch_gdml_trigger_volumes.py` — GDML patch script
- `scripts/trigger_phase2/TriggerSensitiveDetector.hh/.cc` — C++ sensitive detector
- `scripts/trigger_phase2/patch_detector_construction.md` — Detector construction instructions
- `scripts/trigger_phase2/test_phase2_simulation.sh` — Test simulation script
- `research/trigger_migration_study/phase2/PLAN.md`
- `research/trigger_migration_study/phase2/STATUS.md`

### Phase 3 (PREPARATION COMPLETE)
- `scripts/trigger_phase3/analyze_trigger_response.py` — Analysis script placeholder

## Blocking Items

### Phase 2 Execution
Requires LUNARC access to:
1. Patch `hibeam_wasa_geom.gdml` (write access to shared directory)
2. Recompile HIBEAM simulation (build environment)
3. Run 50k event test simulation (Geant4 runtime)

**Action**: Run `test_phase2_simulation.sh` on LUNARC

### Phase 3 Execution
Requires Phase 2 simulation output to:
1. Analyze trigger response at various thresholds/coincidence windows
2. Compute efficiency matrices and migration ratios

**Action**: Run `analyze_trigger_response.py` on Phase 2 output

## Next Steps (Priority Order)

1. **On LUNARC**: Execute `test_phase2_simulation.sh`
2. **Verify**: T1/T2 volumes appear in geometry without errors
3. **Verify**: Sensitive detectors register successfully
4. **Analyze**: Run `analyze_trigger_response.py` on output
5. **Phase 4**: Compute migration matrices and decision
6. **Phase 5-6**: MC regeneration (if needed) and contract update

## Key Numbers (from Phase 1)

- Sample I (A+B coincidence): 64,717 events (6.47%)
- Sample II (B only): 237,043 events (23.70%)
- Deuteron efficiency: 45.6% (Sample I)
- Proton efficiency: 0.4% (Sample I)
- Coincidence window: 15 ns

## Geometry Specifications (Phase 2)

| Parameter | T1 (A-arm) | T2 (B-arm) |
|-----------|------------|------------|
| Material | PSci (polystyrene) | PSci (polystyrene) |
| Size (cm) | 10×10×1 (L×W×T) | 15×15×1 (L×W×T) |
| Angle | 71.5° from beam | -38° from beam |
| Position | ~30 cm upstream of HRD | ~30 cm upstream of HRD |

---
**Updated**: 2026-08-16
**Issue**: #1045 (P0)
**Status**: Phase 1 COMPLETE, Phase 2/3 IMPLEMENTATION COMPLETE (awaiting LUNARC)

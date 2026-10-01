# Phase 2 Status — Truth-Trigger Volume Addition

**Date**: 2026-08-16
**Status**: IMPLEMENTATION COMPLETE — AWAITING LUNARC EXECUTION

## Completed

1. **GDML Patch Script**: `scripts/trigger_phase2/patch_gdml_trigger_volumes.py`
   - Adds T1 (A-arm) and T2 (B-arm) trigger volumes to GDML
   - Uses existing PSci material
   - Proper positioning and rotation for each arm

2. **Trigger Sensitive Detector**: C++ class for recording trigger response
   - `TriggerSensitiveDetector.hh` — Header file
   - `TriggerSensitiveDetector.cc` — Implementation
   - Records EDep, earliest time, and hit count per event

3. **Documentation**:
   - `patch_detector_construction.md` — Instructions for modifying detector construction
   - `PLAN.md` — Full implementation plan
   - `STATUS.md` — This file

4. **Test Script**: `test_phase2_simulation.sh`
   - Patches GDML
   - Copies files
   - Recompiles
   - Submits 50k event test simulation

## Blocking

Phase 2 requires LUNARC execution of `test_phase2_simulation.sh`:
- Patch the GDML file (requires write access to shared directory)
- Recompile HIBEAM simulation (requires build environment)
- Run 50k event simulation (requires Geant4 runtime)

## Geometry Specifications Confirmed

| Parameter | T1 (A-arm) | T2 (B-arm) |
|-----------|------------|------------|
| Material | PSci (polystyrene) | PSci (polystyrene) |
| Size (cm) | 10×10×1 (L×W×T) | 15×15×1 (L×W×T) |
| Angle | 71.5° from beam | -38° from beam |
| Position | ~30 cm upstream of HRD | ~30 cm upstream of HRD |
| Purpose | A-arm trigger for Sample I | B-arm trigger for Sample II |

## Decision: Option A — Direct GDML Modification

Chose Option A (modify base GDML directly) because:
- Fastest approach (6-8h vs 8-16h for other options)
- GDML file is accessible and well-structured
- Geometry is shared among all users anyway
- Minimal impact on existing code

## Next Steps

1. Execute `test_phase2_simulation.sh` on LUNARC
2. Verify T1/T2 volumes appear in geometry
3. Verify sensitive detectors register successfully
4. Analyze 50k event output for trigger response
5. Proceed to Phase 3 (Threshold/Coincidence SCAN)

## Commit

- Commit hash: `a223b807`
- Branch: `fix/1045-trigger-migration`
- Files: 6 added, 502 insertions

---
**Issue**: #1045 (P0)
**Phase**: 2/6
**Created**: 2026-08-16

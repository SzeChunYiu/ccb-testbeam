# Phase 2: Truth-Trigger Volume Addition — Implementation Plan

**Issue**: #1045 (P0)  
**Date**: 2026-08-16  
**Status**: IN PROGRESS

## Objective

Add T1/T2 trigger scintillator volumes to the HIBEAM geometry to enable truth-trigger response measurements for migration matrix computation.

## Geometry Specifications

### T1 (A-arm Trigger)
- **Material**: PSci (polystyrene, ρ=1.032 g/cm³) — already in GDML
- **Position**: 71.5° from beam, ~30 cm upstream of HRD
- **Size**: 10 cm × 10 cm × 1 cm (L × W × T)
- **Purpose**: A-arm trigger for Sample I coincidence

### T2 (B-arm Trigger)
- **Material**: PSci (polystyrene, ρ=1.032 g/cm³) — already in GDML
- **Position**: -38° from beam, ~30 cm upstream of HRD
- **Size**: 15 cm × 15 cm × 1 cm (L × W × T)
- **Purpose**: B-arm trigger for Sample II selection

## Implementation Steps

### 1. Patch GDML File (Option A — direct modification)

**File**: `/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build/geometry/hibeam_wasa_geom.gdml`

**Script**: `scripts/trigger_phase2/patch_gdml_trigger_volumes.py`

**Changes**:
- Add T1_trigger_box solid (10×10×1 cm)
- Add T2_trigger_box solid (15×15×1 cm)
- Add T1_trigger_log volume (PSci material)
- Add T2_trigger_log volume (PSci material)
- Add position/rotation definitions
- Add physical volumes in MOTHER (world)

**Execution**:
```bash
cd /projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build/geometry
cp hibeam_wasa_geom.gdml hibeam_wasa_geom.gdml.backup
python3 ~/ccb-wt-1045/scripts/trigger_phase2/patch_gdml_trigger_volumes.py hibeam_wasa_geom.gdml
```

### 2. Create Trigger Sensitive Detector

**Files**:
- `scripts/trigger_phase2/TriggerSensitiveDetector.hh`
- `scripts/trigger_phase2/TriggerSensitiveDetector.cc`

**Functionality**:
- Record energy deposit per event
- Record earliest hit time (global time)
- Count number of hits
- Inherit from SD_Det base class

### 3. Modify Detector Construction

**File**: `/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4-main/src/WasaDetectorConstruction.cc`

**Changes**:
- Include `TriggerSensitiveDetector.hh`
- In `ConstructSDandField()`: register T1/T2 sensitive detectors

**Reference**: `scripts/trigger_phase2/patch_detector_construction.md`

### 4. Copy Files and Recompile

```bash
# Copy header to include directory
cp ~/ccb-wt-1045/scripts/trigger_phase2/TriggerSensitiveDetector.hh \
   /projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4-main/include/

# Copy source to src directory
cp ~/ccb-wt-1045/scripts/trigger_phase2/TriggerSensitiveDetector.cc \
   /projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4-main/src/

# Recompile
cd /projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build
mkdir -p build && cd build
cmake ..
make -j4
```

### 5. Test Simulation (50k events)

**Config**: Use existing production config with reduced events

**Expected Output**:
- ROOT file with T1/T2 hit information
- Console output showing trigger SD registration
- Per-event EDep and time for trigger volumes

## Success Criteria

1. T1/T2 volumes appear in geometry (no overlap errors)
2. Sensitive detectors register successfully
3. 50k events simulate without errors
4. T1/T2 EDep and time recorded in output

## Next Phase

Phase 3: Threshold/Coincidence SCAN — Analyze 50k events at various threshold/coincidence settings

## Files Created

- `scripts/trigger_phase2/patch_gdml_trigger_volumes.py`
- `scripts/trigger_phase2/TriggerSensitiveDetector.hh`
- `scripts/trigger_phase2/TriggerSensitiveDetector.cc`
- `scripts/trigger_phase2/patch_detector_construction.md`

---
**Created**: 2026-08-16
**Issue**: #1045
**Phase**: 2/6

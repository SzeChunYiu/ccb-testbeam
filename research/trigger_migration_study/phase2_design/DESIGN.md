# Phase 2 Design: T1/T2 Trigger Volume Addition

**Issue**: #1045 (P0)
**Date**: 2026-08-16
**Branch**: fix/1045-trigger-phase2
**Worktree**: ccb-wt-1045p2 (LUNARC, fs10 paths only)

## Executive Summary

**Objective**: Add T1/T2 trigger scintillator volumes to HIBEAM geometry.

**Key Finding**: MATTHIAS_RESPONSE.md contains FALSE CLAIM — T1/T2 volumes are NOT present.

**Status**: Design phase only — NO builds/runs until mc-1045-1b pinned source exists.

---

## Investigation Findings

### 1. MATTHIAS_RESPONSE.md Contradiction

MATTHIAS_RESPONSE.md (2026-07-01) claims:
- T1 trigger scintillator (PSci, 1 cm) — 1.032 g/cm² — "In source since 2026-01-26"
- T2 trigger scintillator (PSci, 1 cm) — 1.032 g/cm² — "In source since 2026-01-26"

**Phase 1 GDML Audit CONFIRMED**:
- File: hibeam_wasa_geom.gdml (401 KB, 912 volumes)
- NO T1 or T2 volume definitions exist
- PSci material exists ONLY for CV bars
- ZERO trigger volumes in geometry

**Conclusion**: MATTHIAS_RESPONSE.md claim is CONTRADICTED. Trigger scintillators must be ADDED.

### 2. Geometry Structure Analysis

**Current GDML**: hibeam_wasa_geom.gdml (912 volumes)

**Key Positions**:
- Target: z=2.5 cm
- Beam pipe: present (Al, 5 mm wall)
- HRD stacks: at 109 cm from target

**Arm Angles**:
- A-arm: 71.5 degrees from beam (4 bars)
- B-arm: -38 degrees from beam (8 bars)

---

## T1/T2 Trigger Volume Design

### Geometry Specifications

T1 (A-arm):
- Material: PSci (polystyrene, rho=1.032 g/cm3)
- Size: 10x10x1 cm (LxWxT)
- Position: ~30 cm upstream of HRD
- Angle: 71.5 degrees from beam

T2 (B-arm):
- Material: PSci (polystyrene, rho=1.032 g/cm3)
- Size: 15x15x1 cm (LxWxT)
- Position: ~30 cm upstream of HRD
- Angle: -38 degrees from beam

### GDML Insertion Design

T1 Volume Addition:
- Add position: x=10.5 cm, y=0, z=-30 cm (relative to beam)
- Add rotation: 71.5 degrees around Y axis
- Add box solid: 10x10x1 cm
- Add logical volume with PSci material
- Add physical volume in MOTHER world

T2 Volume Addition:
- Add position: x=-12.0 cm, y=0, z=-30 cm (relative to beam)
- Add rotation: -38 degrees around Y axis
- Add box solid: 15x15x1 cm
- Add logical volume with PSci material
- Add physical volume in MOTHER world

---

## Sensitive Detector Design

### TriggerSensitiveDetector Class

Purpose: Record energy deposit and time per event.

Output branches:
- T1_EDep (Float_t): Energy deposit in T1 (MeV)
- T1_Time (Float_t): Earliest hit time in T1 (ns)
- T2_EDep (Float_t): Energy deposit in T2 (MeV)
- T2_Time (Float_t): Earliest hit time in T2 (ns)

Implementation: Inherits from SD_Det base class.

---

## Validation Plan

### Phase 2A: Geometry Validation (after mc-1045-1b)

1. Apply GDML patch to pinned geometry
2. Visualize in GEANT4 viewer
3. Check for overlaps
4. Verify positioning

### Phase 2B: Sensitive Detector Validation

1. Compile with TriggerSensitiveDetector
2. Register in ConstructSDandField
3. Run 1k event test
4. Verify T1/T2 branches in output

### Phase 2C: Physics Validation

1. Run 50k event simulation
2. Analyze trigger response
3. Verify timing distributions
4. Check EDep values

---

## Material Budget Impact

T1: 103.2 g (1.032 g/cm2 areal density)
T2: 232.2 g (1.032 g/cm2 areal density)

Total added: ~0.33 kg of polystyrene

Minimal scattering impact (low-Z material).

---

## Deliverables

This design document (DESIGN.md)

Implementation files (from Phase 2 groundwork):
- patch_gdml_trigger_volumes.py
- TriggerSensitiveDetector.hh/.cc
- patch_detector_construction.md
- test_phase2_simulation.sh

---

## References

- Issue: #1045 (P0)
- MATTHIAS_RESPONSE.md docs/MATTHIAS_RESPONSE.md
- Phase 1 findings PHASE1_COMPLETE_FINDINGS.md
- Setup docs docs/01_setup_and_detector.md

---
**Created**: 2026-08-16
**Phase**: 2 Design only
**Branch**: fix/1045-trigger-phase2
**Worktree**: ccb-wt-1045p2

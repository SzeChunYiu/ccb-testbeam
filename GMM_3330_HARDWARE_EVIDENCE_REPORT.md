# CCB Test-Beam Hardware Evidence Search Report
**Date:** 2026-08-14
**Issue:** #1296
**Worktree:** ccb-wt-1296

## Search Scope
- Repo: ccb-testbeam
- LUNARC: ~/nnbar, ~/nnbar_local, /projects/hep/fs10/shared/nnbar/

## Evidence Located

### 1. Stave Geometry (DESIGN_SPEC)
- Source: docs/stave_sim/STAVE_SIM_ENERGY_MODEL.md (issue #796)
- Content: 50cm x 5.18cm x 2.0cm extruded polystyrene
- SHA-256: bd2f6948c6a3c00c9ae2643c07c48bffa48bbe37162338d326000a887136105f
- Status: DESIGN_SPEC

### 2. Geometry Schematics (DESIGN_SPEC)
- Source: figures/geometry/
- Status: DESIGN_SPEC

### 3. Run Ledger (SOURCE_BOUND_CONFIG)
- Source: configs/daq/run_ledger.yaml
- Status: SOURCE_BOUND_CONFIG

### 4. Channel Map (SOURCE_BOUND_CONFIG)
- Source: configs/channel_polarity_v1.json
- Content: B2=0, B4=2, B6=4, B8=6
- Status: SOURCE_BOUND_CONFIG

### 5. Geant4 Config (SIM_CONFIG)
- Source: geant4/configs/krakow.geoconf
- SHA-256: a2bfda12d722d07ea8993bfd765bf8f43e2921715cced9b1b739fd5ffd3871c7
- Status: SIM_CONFIG (not survey-grade)

## Evidence NOT Found (UNKNOWN_EXTERNAL)

1. Primary CAD/build sheets
2. Assembly drawings with scale
3. Photos with scale/build annotations
4. Manufacturer spec sheets (Y-11 grade/lot, SiPM operating point)
5. CD2 target hardware record
6. Beam energy hardware record (190 MeV)
7. Trigger scintillator hardware
8. Survey/layout notes (109cm, -38deg, +71.5deg)
9. Elog/logbook exports

## Conflict Resolution

### 5cm vs 2.0cm thickness
- Issue #796: 2.0 cm supersedes early 5cm phrase
- Status: RESOLVED

### 50cm vs ~1m length
- Issue #796/#991: 50cm design spec; ~1m UNKNOWN_EXTERNAL
- Status: RESOLVED

### BC-408 vs extruded polystyrene
- Issue #796: Extruded polystyrene design spec; BC-408 UNKNOWN_EXTERNAL
- Status: RESOLVED

### One-fibre vs two-fibre
- Issue #987: One-fibre one-end readout
- Status: RESOLVED

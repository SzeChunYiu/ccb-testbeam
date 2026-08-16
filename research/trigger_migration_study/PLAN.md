# Trigger Hardware-Response Migration Study (Issue #1045, P0)

## Executive Summary

**Objective**: Replace the HRD first-stack-layer charged-hit proxy with a validated hardware-trigger response model by adding T1/T2 trigger scintillator volumes to the MC geometry and computing migration matrices.

**Current Status**: BLOCKED - HRD proxy is diagnostic only, not validated hardware trigger reproduction.

**Evidence State**: MC_TRIGGER_PROXY / UNKNOWN_EXTERNAL per docs/contracts/TRIGGER_HARDWARE_RESPONSE.json

## Current Proxy Implementation

### HRD_FIRST_STACK_LAYER_CHARGED_HIT
- **Definition**: ENTER B = any charged hit in first B-stack layer; ENTER A = any charged hit in first A-stack layer; Sample I additionally requires |min(t_A)-min(t_B)| < coinc_ns
- **Code Surface**: src/ccb_mc_validation/truth/trigger.py (lines 63-197)
- **Semantics**:
  - Sample II: charged B first-layer hit
  - Sample I: charged B AND charged A with |tA - tB| < coinc_ns (default 15 ns)
- **Provenance**: trigger_provenance() returns BLOCKED state

### Known Issues
1. **Geometry**: T1/T2 trigger scintillators NOT in any G4 geometry (only CV bars use PSci material)
2. **MC Output**: ROOT files record only HRDv_digitized (no trigger EDep/times)
3. **Run Ledger**: Has trigger semantics but NO hardware parameters (threshold, discriminator, coincidence window)
4. **External Source**: MATTHIAS_RESPONSE.md claims "In source since 2026-01-26" - UNVERIFIED (LUNARC not a git repo)

## Migration Study Design

### Phase 1: Baseline HRD Proxy Characterization
**Objective**: Quantify current proxy acceptance vs species, energy, angle, multiplicity

**Steps**:
1. Process existing 1M-event MC (output_krakow_1M.root) at coinc_ns = 15 ns
2. Compute efficiency matrix ε_HRD[species, energy_bin, angle_bin]
3. Document reference distributions for:
   - Species: p, d, α, ¹²C (primary contributors)
   - Energy: 0-50, 50-100, 100-150, 150-200 MeV
   - Angle: Lab θ bins (0-30°, 30-60°, 60-90° for B arm)
   - Multiplicity: 1, 2, 3+ hits per event

**Output**: research/trigger_migration_study/baseline_hrd_proxy.json

### Phase 2: Truth-Trigger Volume Addition
**Objective**: Add T1/T2 trigger scintillator volumes to LUNARC HIBEAM geometry

**Geometry Specifications** (from MATTHIAS_RESPONSE.md):
- T1: 1 cm thick PSci at A-arm position (71.5° from beam)
- T2: 1 cm thick PSci at B-arm position (-38° from beam)
- Material: PSci (ρ=1.032 g/cm³, C/H composition - already in GDML)
- Position: Upstream of HRD stacks, covering beam spot

**Implementation**:
1. Modify hibeam_wasa_geom.gdml (LUNARC) or create new geometry file
2. Add sensitive detectors for trigger volumes
3. Record per-event: T1_EDep, T1_Time, T2_EDep, T2_Time, T1_optical_photons, T2_optical_photons
4. Re-compile HIBEAM simulation on LUNARC

**Test**: 50k events (statistical sufficiency for migration matrices)

### Phase 3: Threshold/Coincidence Window SCAN
**Objective**: Scan hardware parameter space to find optimal values

**Scan Bands** (preregistered):
- **Threshold**: 0.5, 1.0, 2.0, 5.0 MeV (4 values)
- **Coincidence Window**: 5, 10, 15, 20, 30 ns (5 values)
- **Total configs**: 4 × 5 = 20 combinations

**For each (threshold, coinc_window)**:
1. Apply to truth-trigger response: ENTER T1 = T1_EDep > threshold, ENTER T2 = T2_EDep > threshold
2. Compute coincidence: |T1_Time - T2_Time| < coinc_window
3. Compute efficiency matrix: ε_truth[species, energy_bin, angle_bin]
4. Calculate migration ratio: M = ε_truth / ε_HRD

**Output**: research/trigger_migration_study/scan_results_*.json

### Phase 4: Migration Matrices and Decision
**Objective**: Quantify proxy bias and decide on MC regeneration

**Decision Criteria**:
- **If M ≈ 1 (±10%)**: HRD proxy validated → no regeneration needed
- **If M varies 10-20%**: Quantify bias, document systematic uncertainty
- **If M varies >20%**: Proxy irrecoverable → full MC regeneration required

**Output**: research/trigger_migration_study/MIGRATION_MATRIX_REPORT.md

### Phase 5: MC Regeneration (if needed)
**Objective**: Regenerate 1M events with validated trigger geometry

**Cost Estimate** (LUNARC):
- Events: 1M
- Runtime: ~10 hours
- Storage: ~5 GB per 1M-event ROOT file

## Contract Bump

Upon completion, update docs/contracts/TRIGGER_HARDWARE_RESPONSE.json:
- Set evidence_state to "MIGRATION_VALIDATED" or "FULL_REGENERATION_COMPLETED"
- Add trigger_hardware_schema with validated geometry/material/threshold/time response

## Timeline Estimate

- Phase 1 (Baseline): 2-4 hours
- Phase 2 (Geometry): 4-8 hours (including compilation)
- Phase 3 (Scan): 1-2 hours (analysis) + ~40h LUNARC runtime
- Phase 4 (Analysis): 2-4 hours
- Phase 5 (Regeneration): ~10h LUNARC (if needed)

**Total**: ~55-70 hours (mostly LUNARC runtime, can be parallelized)

## Success Criteria

1. T1/T2 trigger volumes added to geometry with sensitive detectors
2. Per-event trigger quantities recorded in MC output
3. Migration matrices computed across all scan bands
4. Decision document with clear recommendation on MC regeneration
5. Contract updated with evidence_state change

---
**Created**: 2026-08-16
**Issue**: #1045
**Status**: PLANNING → IMPLEMENTATION

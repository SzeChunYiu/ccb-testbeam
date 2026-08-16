# Phase 1: Baseline HRD Proxy Characterization - COMPLETE

## Execution Summary

**Date**: 2026-08-16
**MC File**: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
**Events Processed**: 1,000,000
**Processing Time**: ~2-3 minutes on LUNARC

> **HISTORICAL DIAGNOSTIC (2026-08-16)**: this MC is NONAUTHORISING (superseded uniform-source
> generator; see `geant4/REPRODUCTION_STATUS.md` and `PHASE1B_NONAUTHORISING_MC_NOTICE.md`).
> All numbers below are diagnostics of that MC, pending the Phase-1B authorising rebuild.

## Results

### Overall Statistics
- **Enter B (Sample II)**: 237,043 events (23.70%)
- **Sample I (A∧B coincidence)**: 64,717 events (6.47%)
- **Coincidence Rate**: 27.3% of Enter B events (64,717 / 237,043)
- **Coincidence Window**: 15 ns (default proxy parameter)

### Species Breakdown (Enter B events)

| Species | Enter B | Sample I | Coincidence Rate | Sample I Fraction |
|---------|---------|----------|------------------|-------------------|
| Deuteron | 140,853 | 64,283 | 45.6% | 99.3% of Sample I |
| Proton | 96,081 | 371 | 0.4% | 0.6% of Sample I |
| Alpha | 31 | 18 | 58% | 0.03% of Sample I |
| C12 | 0 | 0 | N/A | 0% |

### Key Findings

1. **Deuteron Enrichment**: Sample I is 99.3% deuteron-dominated, confirming the p+d conjugate kinematics prediction
2. **Proton Suppression**: Only 0.4% of protons entering B satisfy the A coincidence (as expected)
3. **Alpha Enrichment**: Alphas show 58% coincidence rate but contribute negligibly to total Sample I
4. **Validation**: Results match expected values from previous reports (~23.7% Enter B, ~6.5% Sample I)

### HRD Proxy Baseline Reference

This baseline establishes the reference efficiency matrix `ε_HRD[species, energy, angle]` for comparison against future truth-trigger response:

- `ε_HRD[deuteron, all, all]`: 45.6% coincidence rate
- `ε_HRD[proton, all, all]`: 0.4% coincidence rate
- `ε_HRD[alpha, all, all]`: 58% coincidence rate

## Data Files

- **Raw output**: `research/trigger_migration_study/baseline_hrd_proxy.json` (on LUNARC)
- **Log file**: `research/trigger_migration_study/baseline_run.log` (on LUNARC)

## Next Steps

**Phase 2**: Truth-Trigger Volume Addition
- Add T1/T2 trigger scintillator volumes to HIBEAM geometry
- Implement sensitive detectors for trigger volumes
- Re-simulate 50k events for migration matrix computation

---
**Status**: COMPLETE
**Issue**: #1045
**Phase**: 1/6 Complete

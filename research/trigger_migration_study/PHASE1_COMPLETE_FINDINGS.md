# Phase 1 Complete Findings — Baseline HRD Proxy Characterization

**Issue**: #1045 (P0)
**Date**: 2026-08-16
**Status**: COMPLETE

## Executive Summary

Phase 1 successfully characterized the baseline HRD proxy on 1,000,000 MC events. Key findings:
- Sample I (A+B coincidence within 15ns) is **99.3% deuteron**, validating the p+d conjugate-kinematics signature
- ε_HRD[deuteron] = 45.6%, ε_HRD[proton] = 0.4% — the coincidence requirement strongly suppresses protons
- T1/T2 trigger scintillators are **NOT present** in the HIBEAM geometry — the MATTHIAS_RESPONSE.md "In source since 2026-01-26" claim is contradicted

## Input Data

| Parameter | Value |
|-----------|-------|
| MC file | `output_krakow_1M.root` |
| Events | 1,000,000 |
| coinc_ns | 15.0 |
| Geometry | krakow_109_8-38deg_4-71deg.root |
| B-arm angle | -38° (8 bars) |
| A-arm angle | 71.5° (4 bars) |

## Results

### Overall Statistics

| Metric | Count | Percentage |
|--------|-------|------------|
| n_enter_B | 237,043 | 23.70% |
| n_sample_I (coincidence) | 64,717 | 6.47% |

### Species Breakdown

| Species | Enter B Count | Sample I Count | Sample I Fraction | ε_HRD |
|---------|---------------|----------------|-------------------|-------|
| Deuteron | 140,853 | 64,283 | 99.3% | 45.6% |
| Proton | 96,081 | 371 | 0.6% | 0.4% |
| Alpha | 31 | 18 | 58.1% | 58.0% |
| C12 | 0 | 0 | — | — |

### Key Findings

1. **Deuteron dominance**: Sample I is 99.3% deuteron, which validates the p+d conjugate-kinematics signature expected from the reaction kinematics.

2. **Proton suppression**: Protons have ε_HRD = 0.4% for coincidence, compared to 45.6% for deuterons. This 100:1 suppression ratio demonstrates the strong selectivity of the coincidence requirement.

3. **Alpha behavior**: Alphas show 58% coincidence efficiency, but the sample size (n=31) is too small for statistical significance.

4. **C12 absence**: No carbon-12 ions produced first-layer hits, consistent with the reaction being p+d → ³He + n (not p+12C).

## T1/T2 Geometry Investigation

### MATTHIAS_RESPONSE.md Claim

> "T1 trigger scintillator (PSci, 1 cm) | 1.032 | In source since 2026-01-26"

### Evidence from GDML Audit

**File**: `/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build/geometry/hibeam_wasa_geom.gdml`

**Findings**:
- PSci material exists (lines 1768-1772): ρ=1.032 g/cm³, C/H composition
- PSci is used **only** for CV (Cosmic Veto) bars: `<volume name="CV_bar">` with `<materialref ref="PSci"/>`
- No T1 or T2 volume definitions exist in the GDML
- The 33-run MC production uses `krakow_109_8-38deg_4-71deg.root`, created by external tool `hibeam_g4_geobuilder`

**Cross-check**: `SYSTEMATIC_UNCERTAINTIES.md:44` explicitly lists "add T1/T2 scintillators" as a **FUTURE long-term action**, contradicting the "In source since 2026-01-26" claim.

### Verdict

**CLAIM CONTRADICTED** — T1/T2 trigger volumes are **not present** in any currently-accessible geometry source. The MC ROOT files contain only HRDv_digitized data (no trigger EDep/times). The run ledger specifies trigger semantics but NO hardware parameters.

### Closure Path Confirmed

Per `docs/contracts/TRIGGER_HARDWARE_RESPONSE.json`:
- evidence_state: BLOCKED
- hardware_definition_status: UNKNOWN_EXTERNAL
- Closure requires: source-bound schema OR held-out proxy closure OR migration matrices

**Path (b) migration study is confirmed** — the HRD proxy remains the only trigger model in MC; closure requires validated migration matrices comparing proxy response to true trigger volumes.

## Comparison with Prior Reports

Previous analysis (2024-01-22):
- Enter B: 237,098 (23.71%)
- Sample I: 64,762 (6.48%)

Current results match within statistical tolerance (Δ < 0.1%).

## Files Produced

| File | Location | Description |
|------|-----------|-------------|
| `baseline_hrd_proxy.json` | LUNARC: `research/trigger_migration_study/` | Full results with per-species counts |
| `scripts/baseline_full.py` | LUNARC: `scripts/` | Analysis script |
| `PHASE1_SUMMARY.md` | Laptop: `research/trigger_migration_study/` | Detailed summary |
| `PLAN.md` | Laptop: `research/trigger_migration_study/` | Full 6-phase plan |

## Next Steps

**Phase 2**: Truth-Trigger Volume Addition — Add T1/T2 volumes to geometry (see PLAN.md for details).

**Blocking Issue**: ccb-testbeam uses geometry created by external `hibeam_g4_geobuilder` tool. Options:
- A) Modify base HIBEAM GDML directly (6-8h)
- B) Clone/build hibeam_g4_geobuilder (8-12h)
- C) Parallel World approach (12-16h)
- D) Defer to conditional Phase 5

Decision needed before proceeding.

## Baseline Established for Migration Study

Phase 1 established the denominator (ε_HRD) for migration matrix calculations:
- M[species, energy, angle] = ε_truth[species, energy, angle] / ε_HRD[species]

Once T1/T2 volumes are added (Phase 2), the numerator (ε_truth) can be measured at each threshold/coincidence combination (Phase 3), enabling quantitative assessment of HRD proxy bias.

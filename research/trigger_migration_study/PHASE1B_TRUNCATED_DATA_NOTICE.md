# Phase 1B: Baseline Rebuild on Corrected Staging — REQUIRED

**Issue**: #1045 (P0)
**Date**: 2026-08-16
**Status**: REQUIRED — Phase 1 baseline used truncated data

## Critical Finding

Phase 1 baseline (`f6f22dfd`) used `output_krakow_1M.root` created on **2026-07-09**, which predates the corrected 144-word staging (CL-001 PR #1508 opened **2026-08-16**, still OPEN).

**Conclusion**: Phase 1 consumed the OLD truncated 8×16 product, not the corrected 144-word raw ROOT files.

## Impact

All Phase 1 results are potentially biased:
- ε_HRD[deuteron] = 45.6% — MAY BE AFFECTED
- ε_HRD[proton] = 0.4% — MAY BE AFFECTED
- Migration matrix denominator — NEEDS REBUILD

## Required Action: Phase 1B

**Re-run baseline HRD proxy characterization on corrected staging:**

1. **Generate new MC file** on corrected 144-word input:
   - Input: `/projects/hep/fs10/shared/nnbar/billy/ccb-data/data/extracted/root/root` (144-word)
   - Output: `output_krakow_1M_corrected.root`
   - Events: 1,000,000

2. **Re-run analysis**:
   - Script: `scripts/trigger_baseline_characterization.py`
   - Input: `output_krakow_1M_corrected.root`
   - Output: `baseline_hrd_proxy_corrected.json`

3. **Compare results**:
   - ε_HRD_corrected vs ε_HRD_truncated
   - Quantify bias from truncated waveform
   - Document any significant differences

## Deliverables

- `scripts/trigger_baseline_characterization.py` (existing, reusable)
- `research/trigger_migration_study/PHASE1B_COMPLETE_FINDINGS.md` (new)
- `research/trigger_migration_study/baseline_hrd_proxy_corrected.json` (new)
- Comparison report: ε_HRD_corrected vs ε_HRD_truncated

## Blocking

- Requires corrected MC generation on LUNARC
- Requires access to corrected 144-word raw ROOT files
- Must complete BEFORE Phase 3 (uses ε_HRD as denominator)

## Updated Phase Sequence

| Phase | Name | Status |
|-------|------|--------|
| 1 | Baseline HRD Proxy Characterization | ⚠️ **NEEDS REBUILD** |
| 1B | Baseline on Corrected Staging | 🔥 **REQUIRED** |
| 2 | Truth-Trigger Volume Addition | Implementation complete |
| 3 | Threshold/Coincidence SCAN | Awaiting corrected baseline |
| 4 | Migration Matrix Analysis | Awaiting Phase 3 |
| 5 | MC Regeneration (conditional) | Awaiting Phase 4 |
| 6 | Contract Bump | Awaiting Phase 5 |

---
**Created**: 2026-08-16
**Issue**: #1045 (P0)
**Severity**: P0 — Baseline rebuild required before migration matrices can be computed
